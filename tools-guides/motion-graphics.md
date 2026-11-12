# Motion graphics, screens, subtitles and 3D text

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender edition (Blender 5.2, EEVEE, AgX). The tools live in
`blender/eidoblend/media/`; the probes that show each one working are in
`blender/tests/media/` and `blender/tests/media2/` (they render into their
`out/` folders).

Choose the anchor before making a graphic. A screen inside the world is a
**screen** (`screens.make_screen`): an emitter the camera films, graded with
the rest of the frame. A broadcast title, lower third or subtitle is a
**graphic on the frame**: it lives on the **overlay layer** (`overlay`) and
reaches the film one of two ways. The display route lays it over the
finished film in the **edit scene**, so its colours land exactly as
authored. The signal route puts it inside the film's post chain, between the
world effects and the signal effects, as the WebGPU engine did, so a VHS or
glitch pass runs over the HUD too.

Everything that changes over time is computed once at build time (drawn
frames, keys), never in a handler at render time, so any frame renders the
same in any order and in any chunk. Time follows the film convention: frame 1
is 0 s (`eidoblend.media.timebase.Timebase`; a scene may move it with
`scene['eido_frame0']`).

Measured (`blender/tests/media2/test_reopen.py`): a verse-1 film (an era
playlist on an LED wall with spill, and a HUD in the post chain that draws its
own frame number as a bit code) was rendered out of order (60, 10, 49, 48),
saved, and opened in a fresh Blender. Every frame read its own number and
matched the building session to the bit (mean difference 0.000). With motion
blur on (shutter 0.5), one time step showed the frame's own drawing, and four
steps the mean of drawings 59 and 60: what a camera filming a display through
that shutter records.

## In-world screens and ASCII panels

```python
import bpy
from eidoblend.media import raster, screens

def draw(c, t, w, h):                        # c: raster.Canvas, t: film seconds, w x h: the canvas
    c.clear('#071b22')
    raster.draw_text_fit(c, 'SYSTEM READY', x=w / 2, y=h * 0.3, max_width=w * 0.8, max_height=h * 0.4,
                         font='Share Tech Mono', px=96, align='center', fill='#c6f4ef')

ui = screens.make_screen(width=0.64, height=0.36, px=768, draw=draw, frames=(1, 240),
                         out_dir='//screens/ui', strength=1.5)
ui.obj.location = (0, -1.0, 1.4)             # a standalone panel: stands up, faces -Y
```

`make_screen` calls `draw` once per frame of `frames` and writes a PNG
sequence (`<out_dir>/<name>_0001.png …`); an Image Texture steps through it
with the scene frame. File 1 shows at the range's first frame; before the
range the first drawing holds, after it the last. Blender shows file
`<first − 1>` on every frame before a sequence starts (it clamps to 0, then
adds the offset), so `make_screen` writes `<name>_0000.png` beside the
sequence, a copy of file 1 marked as a hold in a PNG text chunk (without it a
screen shows the missing-texture magenta until its range begins). It
does the same beside a `source=` sequence (file `<first − 1>`, unless the
source already has a real frame there). Encoding such a folder with ffmpeg,
pass `-start_number 1`: ffmpeg's image2 reader starts at file 0 by default and
picks the hold up as an extra first frame.
`fps=12` throttles the redraw (a held frame repeats the last drawing, drawn at
the first film frame of each art frame, as the engine's throttle did). A
single-frame range bakes a still.

Give `out_dir` a lasting folder (`work/<id>/…`, or `//…` beside a saved
.blend). Without one, the frames go to `//eido_screens/<blend>/<name>` beside a
saved .blend, or to a folder of the screen's own under the system temp folder
when the blend is unsaved (Blender's session temp, deleted at exit, is never
used). A screen's `name` is also its files' name, so a name the blend already
has becomes `<name>_2`: two screens on the defaults never share frames.

The canvas is a Pillow RGBA image: `c.image`, `c.draw` (an `ImageDraw`),
`c.w`, `c.h`, `c.clear(color)`, `c.layer()` and `c.over(layer)` for
alpha-blended shapes. `supersample=2` draws at twice the size and downsamples
(Pillow's shapes are aliased; text is not). `draw_text_fit` is
`drawTextFit`, ported: it word-wraps, shrinks to fit the box and returns
`{px, lines}`.

**Fonts are files.** `raster.font(name, px)` takes a bundled font by name
(`'Share Tech Mono'`, `'ShareTechMono-Regular'`, `'VT323'`, `'Anton'` …, any
file in `eidoverse/assets/fonts/`) or a path. There are no generic families:
an unknown name raises instead of falling back to a system face.

**Take over a model's display.** `apply_to` puts the screen on a GLB's own
display mesh (the mesh itself, or a root holding one named like
screen / display / monitor / lcd):

```python
mac = screens.make_screen(px=512, width=0.1806, height=0.1207, draw=mac_draw, frames=(1, 48),
                          out_dir='//screens/mac', name='mac_screen', standalone=False,
                          interpolation='Closest', strength=2.0, spill=0.6)
mac.apply_to(bpy.data.objects['screen_crt'], window=(0.0485, 0.10696, 0.9515, 0.90104), glass=True)
```

The Mac's window is `mac1984.js`'s own: the 0.1806 × 0.1207 m raster centred
in the 0.200 × 0.152 m tube and raised 0.004 in v. The engine applied it to
flipUV'd glTF UVs, which is what Blender's glTF importer gives, so the numbers
carry over unchanged.

- Blender's glTF importer already turns glTF's v-down UVs upright, so an
  imported display shows the image upright with no flip (`mac1984.glb`'s
  `screen_crt`). Render and look; `flip` / `mirror_x` are there for a
  model with odd UVs.
- `window = (u0, v0, u1, v1)` puts the image in that part of the mesh's UV
  square: the Mac's 512 × 342 raster inside its tube; outside it is glass.
- `glass=True` (the default for `apply_to`) keeps a real display's dark glass
  and clear coat over the image, so it catches the room's reflections. A
  standalone panel defaults to emission only (an LED wall, a projection);
  `lit=True` makes the image a printed surface; `transparent=True` cuts it by
  its alpha.
- `interpolation='Closest'` keeps pixel art crisp in close-ups; far away
  `'Linear'` aliases less.

**Brightness under AgX.** A screen is an emitter filmed by the camera, so it
goes through AgX like everything else: emission strength 1 lands sRGB white
near 197/255 at exposure 0, strength 4 near 233. Set `strength` by probe
against the room: the Mac in a lit room read right at 2.0, the Voder wall in a
dim room at 1.6 with the view exposure at +1.

**Spill.** `spill=<gain>` adds an area light the size of the display (its
`window`), just in front of it, keyed per frame to the frame's mean linear
colour m (CONSTANT keys), at the display's own radiance: colour m / max(m),
power π · area · strength · max(m) · gain (Blender multiplies colour by power
without normalising it). EEVEE's screen-space GI only sees emitters on screen,
and light probes do not follow animated content, so this is what lights a face
or a desk, from the frames themselves.

The light carries a custom cutoff distance (`spill_reach`, 30 m by default),
because EEVEE culls a light where its power falls under
`scene.eevee.light_threshold` (0.01), and a screen's light is a few watts.

The spill carries a screen's light onto the room at its physical level
(`test_screens.py --only spill`: a 1.0 × 0.6 m screen, strength 1, gain 1,
over a white floor, white, blue and orange frames). While the display itself
is in frame, EEVEE's GI adds the emission's own bounce on top, about a
quarter more, so those shots read a little hot at gain 1; about 0.75 evens
them out.
In the Voder room at gain 1 the spill doubles the light on the stool's seat
and lifts the floor, and the stool casts soft shadows toward the camera
(`screens_wall_spill_only_f060.png` beside `screens_wall_no_spill_f060.png`).

**Sampling a screen from another node tree.** A screen's frames and their
ImageUser settings travel with its image (custom properties), so a prop can
build its own display material (a CRT's barrel and scanlines, a VFD's glass)
on the same frames:

```python
node = ui.texture_node(my_material.node_tree)                 # an Image Texture stepping with the frames
# or, for a node you made: screens.configure_user(node.image_user, ui.image)
```

`make_ascii_panel(text, color='#27e0a0', background='#050a08', width=1.2,
reveal=24, font='VT323')` is `makeAsciiPanel`: multi-line monospace text on a
terminal panel, a teletype reveal in characters per second and a blinking
block cursor, in a real monospace font. The engine's first `makeAsciiPanel`
(`ascii_panel.js`: glow and CRT scanlines), which the particle text example
puts under its cloud, is `ascii_panel` in
[particles-fx.md](particles-fx.md#the-ascii-terminal-panel), with point-cloud
lettering (`from_text`, `'text:HELLO'`).

## Frame overlays

```python
from eidoblend.media import overlay

ov = overlay.make_overlay_layer(film_scene)                  # its own scene, the film camera's field of view

def lower_third(c, t, w, h):
    c.clear((0, 0, 0, 0))
    c.draw.rectangle([0, 0, int(w * 0.06), h], fill=raster.color('#27e0a0'))
    c.draw.rectangle([int(w * 0.06), 0, w, h], fill=(16, 24, 32, 222))
    raster.draw_text_fit(c, 'CLAUDE', x=w * 0.1, y=h * 0.12, max_width=w * 0.5, max_height=h * 0.5,
                         font='Anton', px=h * 0.48, align='left', fill='#ffffff')

ov.panel(draw=lower_third, x=-0.25, y=-0.33, w=0.42, h=0.1, px=1000, frames=(1, 240), out_dir='work/<id>/lt')
frames_dir = overlay.render_overlay(ov, 'work/<id>/overlay')          # RGBA PNGs, ov_0001.png …

edit = overlay.make_edit_scene(film='work/<id>/film.mp4', overlays=[frames_dir],
                               sounds=[('work/<id>/mix.wav', 1)], like=film_scene)
overlay.add_subtitles(edit, overlay.subtitle_cues(lines), font='Share Tech Mono', size=0.055,
                      color='#ffffff', outline='#000000')
overlay.render_edit(edit, 'work/<id>/final.mp4')              # picture, graphics and sound in one pass
```

**The display route** is the default. The overlay scene renders with view
Standard on a transparent film, and the edit scene (view Standard, sequencer
colour space sRGB) lays it over the film's own AgX pixels, as DAISY's
burned-in ASS subtitles did. Both scenes render with `dither_intensity = 0`:
Blender dithers float to 8-bit by default, which puts solid ink ±1 off.
Measured (`test_overlay_routes.py`): teal `#27e0a0`, white, `#ffd400`
and `#101418` all landed on their exact values.

`make_overlay_layer(..., filter_size=0)` renders drawn graphics at their own
pixels. EEVEE's default 1.5 px pixel filter antialiases 3D type placed on the
layer, but it also softens a panel drawn at the film's own resolution. With
the filter at 0 the lyric layer below matched `LyricRenderer.burn` to within 1
level at every pixel; at 1.5 its text edges differed by up to 45 levels (p99).
Keep 1.5 when the layer holds 3D type.

**The overlay layer** is a separate scene with the film's resolution, rate
and range, and a static camera at its origin with the film camera's field of
view. Its planes are parented to that camera at z = −1, where the frame is
`2 * ov.half_w` × `2 * ov.half_h`. `ov.place(obj, x, y)` and `ov.panel(...)`
take frame fractions (−0.5 … 0.5, centre origin, y up). Anything can live
there: drawn panels, 3D type, the parole layer's sprites. A panel exists only
in its `frames`: outside them it is keyed hidden from the render (CONSTANT
`hide_render` keys, `overlay.key_render_range`), where an in-world screen
holds its first and last drawings. Measured: a lower third over frames
10..20 rendered on exactly those 11 frames of 5..25, its teal bar landing on
(39, 224, 160).

**Subtitles.** `add_subtitles` makes one TEXT strip per cue, font from file,
`size` as a fraction of the frame height, outline, shadow, backing box, wrap
width. Strip colours are display values: the authored hex goes in as is
(a linearised colour renders darker: '#ffd400' comes out orange).
`subtitle_cues(lines)` turns `timebase.load_lines` lines (align_lyrics.py
output, captions, voicebox's `Sung.lines`) into cues held until the next line,
and can split long lines. For karaoke styling (`\kf` sweeps, one style per
era) keep the ASS route: `eidoverse/examples/daisy/captions.py` and an ffmpeg
burn-in at the cut.

**The edit scene** takes the film as a movie or a PNG sequence, overlays as
RGBA sequences (ALPHA_OVER, in order), subtitles, and sound strips. It fits
a film rendered in chunks: render the chunks, then one edit render over the
joined film; or overlay with ffmpeg at the cut instead.

### The signal route: the overlay inside the post chain

The WebGPU engine composited its overlay scene between two effect stages:
world effects (fog, godrays, the blast, underwater) under the HUD, signal
effects (vhs, glitch, grain, rgb_shift, scanlines) over it, "so the overlay
looks like part of the broadcast signal". `chain_overlay` puts the overlay
layer in the same place in the film's own compositor chain
([postprocessing.md](postprocessing.md), `look/post/chain.py`):

    Render Layers -> bloom -> 'under' effects -> the overlay -> 'over' effects -> AgX

```python
from eidoblend.look.post import custom_effects as fx
from eidoblend.media import overlay

ov = overlay.make_overlay_layer(film_scene, filter_size=0)
ov.panel(draw=lower_third, x=-0.25, y=0.33, w=0.42, h=0.16, px=800, frames=(1, 240))
overlay.chain_overlay(ov, film_scene)                     # renders with the film: no separate overlay pass
fx.apply_to(film_scene, 'sepia,rgb_shift', {'sepia': {'layer': 'under'},           # the world goes sepia
                                            'rgb_shift': {'layer': 'over', 'amount': 0.004}})   # HUD split too
```

Blender renders the overlay scene for each film frame through a Render
Layers node of that scene. `source='work/<id>/overlay'` reads
`render_overlay`'s PNGs instead (rendered once, reused). A sequence shorter
than the film gets a clear hold file on each side, so nothing shows before
its first frame and its last frame does not freeze after its range (measured:
a 4 … 8 sequence left frames 2 and 10 the bare film to the bit). `factor` is
the overlay's opacity; key the returned `['factor']` socket to fade the whole
layer. Panels keep their keyed `hide_render` ranges. Calling `chain_overlay`
again replaces the stage and its source.

`authored=True`, the default, makes the overlay land as it lands on the
display route: solid ink, glows, soft edges and fades alike. The engine mixed
its overlay in before tone mapping; `parole.js` put solid ink through the
inverse of ACES and left glows and soft edges in linear light, because a
material cannot see the film under it. The compositor can. The overlay stage
takes the film at the overlay slot into display space with the film's own
view transform (Convert To Display, the view exposure applied by a driver),
lays the overlay over it there by its alpha, and brings the mix back to scene
light through the inverse, before the 'over' effects and AgX. Measured
(`test_overlay_routes.py`, frame 3; ink is the mean over a 5 × 5 patch):

| Ink | Display route | Signal route, `authored=True` | Signal route, `authored=False` |
| --- | --- | --- | --- |
| teal `#27e0a0` | (39, 224, 160) | (40, 224, 160) | (114, 185, 154) |
| white | (255, 255, 255) | (255, 255, 255) | graded |
| `#101418` | (16, 20, 24) | (16, 20, 24) | graded |
| `#ffd400` | (255, 212, 0) | (204, 178, 43) | graded |

- The lyric's soft pixels (its teal glow ring, the 160/255 pill, the
  antialiased edges: 60,796 pixels with alpha between 3 and 252) landed
  within 2 levels of the display route, a mean of 0.2. The film away from the
  graphics was untouched (0 levels).
- White and teal boxes at alpha 0.1, 0.2, 0.3, 0.5 and 1.0 landed as the
  display route blends them, within 1.7 levels. `factor` 0.5 over solid boxes
  landed as alpha 0.5 does, within 0.5.
- Light the view cannot show (a lamp above AgX's white) keeps (1 − alpha) of
  its excess under soft pixels, as the engine's linear mix did: a 50 % teal
  box over the lamp stays white, where the display route tints it teal
  (147, 239, 207). Solid ink covers the lamp exactly.
- `out/overlay_lyric_glow_ab_x2.png` shows the lyric on both routes, and
  `out/overlay_fade_strip.png` the fades (display route above, signal route
  below).

AgX's inverse of saturated colours comes back short, because AgX cannot
display them. Through Blender's own OCIO config: `#ffd400` returns 50/255
off, pure blue 67, pure red 26, `#ff2d95` 21, cyan `#00d4ff` 16. Neutrals and
the teal return within 2. When such ink must land exactly and no signal
effect runs over it, take the display route.

`authored=False` alpha-overs the overlay's linear colours (the chain's own
Alpha Over) and AgX grades them with the film, as the engine graded a plain
`makeScreen` overlay: the teal came out (114, 185, 154).

The layering measured in the same probe:
- With sepia 'under', the wall went sepia (mean (153, 146, 137), from (116,
  139, 156)) and the HUD's teal stayed (41, 224, 160).
- With rgb_shift 'over', at the HUD's white block red reached white 4 px
  before the edge, green at it and blue 4 px after: the 3.84 px shift each
  way. Without it, all three reached white at the edge.
- With sepia moved 'over', the HUD teal went to (206, 202, 195) with the film.
- `out/overlay_routes_sheet.png` holds all six renders.

An over-bright channel goes white under AgX: the authored white is 16.5
scene-linear. So a split edge on white ink shows a pale fringe, not a pure
red one.

The registry (`look/post/custom_effects.py`) keeps the engine's default
layers: every effect starts 'over' except `depth_fog` and `retro_wireframe`
('under', switchable), and `nuclear_explosion`, `godrays` and `underwater`
are locked 'under'. `opts[name]['layer']` switches the rest, as above.

## Lyric subtitles — `LyricRenderer`

`eidoverse/lyric_renderer.py`'s `LyricRenderer`, ported unchanged in
`eidoblend.media.lyrics`. A line shows for at least `min_duration`, a gap
shorter than `max_gap` keeps the previous line up, and lines fade over
`fade_duration`. Long lines wrap at `max_chars_per_line`. Each sits on a
rounded backing pill (`bg_opacity`, `bg_padding`, `bg_color`) centred at
`y_position` (85 % of the height by default), clamped to a 5 % safe margin,
with an optional `glow` / `glow_color`. It runs in the system Python or in
Blender's (Pillow is in both):

```python
from eidoblend.media import lyrics, overlay
r = lyrics.LyricRenderer('work/<id>/lyrics_aligned.json', width=1920, height=1080, font='mono', font_size=42,
                         glow=True, glow_color=(39, 224, 160))
r.debug_timeline()                               # when each line shows
frame = r.draw(frame, t)                         # a PIL image or a numpy (H, W, 3) frame, the same type back
r.burn(sorted(Path('work/<id>/frames').glob('*.png')), 'work/<id>/subbed', fps=24)   # over rendered frames

ov = overlay.make_overlay_layer(film_scene, filter_size=0)
lyrics.make_lyric_layer(ov, r)                   # the same subtitles as a panel on the overlay layer
```

It takes `align_lyrics.py` output, any `{text, start|t0, end|t1}` list, or a
timeline with `captions` (DAISY's `daisy_timeline.json`), as a path or as
data. `layer(t)` is the subtitle alone, a transparent RGBA image the frame's
size. `draw` composites exactly that, and `make_lyric_layer` puts it on one
full-frame overlay panel, so it can take either route above.
`draw_karaoke(frame, t)` falls back to `draw`, as in the original. For
karaoke sweeps, keep DAISY's ASS route ([audio.md](audio.md)).

The font names are the original's: 'default' and 'rajdhani' (Rajdhani Bold),
'mono', 'pixel', 'display', 'handwriting', 'orbitron', 'exo2', 'michroma',
'pressstart', 'silkscreen', 'vt323', 'caveat', 'kalam', 'sedgwick',
'monoton' / 'neon', 'blackops' / 'military', 'creepster' / 'horror',
'typewriter'. They resolve to the bundled files instead of the original's
Docker paths. Any other bundled font name or a path works too. 'dejavu' and
'noto' resolve when the system has them. A name that does not resolve falls
back to Rajdhani Bold, as the original did, and says so.

Measured (`test_lyrics_parity.py`, system Python): against the
original module, its font table pointed at the same files, DAISY's 43 lines
gave identical display timing under four option sets. 60 moments each
(inside lines, in fades, in filled gaps) gave byte-identical frames, PIL and
numpy. Through the overlay layer (`test_overlay_routes.py`) the lyric matched
`burn` to within 1 level at `filter_size=0`.

## Parole in libertà — `parole.js`

Lyric captions as Marinetti's words-in-freedom, made for the UNKNOWN FORCE
music video: every sung word thrown in on its own time into a seeded Futurist
layout, the camps' pre-heard answers, documentary quotes, hush. The layouts,
lexicon, inks and treatments are described in the WebGPU guide's section of
the same name; in Blender they are the same, because `parole.js` itself runs:

```python
from eidoblend.media import overlay, parole, timebase
ov = overlay.make_overlay_layer(film_scene)
layer = parole.make_parole(ov, 'work/<id>/parole', timebase.load_lines('work/<id>/lyrics_aligned.json'),
                           add_lines=[{'text': 'UNKNOWN FORCE', 'start': 26, 'end': 33.5, 'template': 'rows',
                                       'sizeScale': 1.6}],
                           spare=parole.face_spare(film_scene, film_scene.camera, armature),   # keep her face clear
                           hush={f: h for f, h in my_hush_curve})                              # optional, per frame
overlay.render_overlay(ov, 'work/<id>/overlay')       # then make_edit_scene lays it over the film
```

`js/parole_export.mjs` runs `makeParole` without a GPU (Deno, offline) over
the frame range, calling `setSpare` and `setHush` before each frame as the
film's `renderFrame` did, and writes each group's canvas atlas and every live
sprite's pose and parameters. `make_parole` builds one plane per sprite under
the overlay camera (three's camera frame and Blender's agree: looking down −Z,
+Y up), keys location, rotation (quaternions, from parole's own 'YXZ' Euler)
and scale per frame, and keys alpha, reveal, bright and desat as object
properties that one material per atlas reads through Attribute (Object)
nodes: the reveal wipe, the cell-edge fade for glows, desaturation,
brightness, as the engine's material. Draw order: the engine drew by group
order and instance order with no depth test; EEVEE sorts blended surfaces by
distance, so each later sprite sits 0.1 mm nearer, its position and size
scaled so it projects identically. In the overlay scene (view Standard) solid
ink lands as drawn; no inverse tone curve is needed.

Pass-through: `opts` (`styleOverrides`, `preheardDefault`, `spare`),
`add_lines` (`addLine` specs), `quotes` (`[{text, opts}]`, `opts.alignWith`
= an earlier quote's index), `preheard` (`[{line, alternatives, opts}]`).
`face_spare(scene, camera, armature, bone='head')` is the film's own face
recipe (head bone + 0.1 m, the radius from a point 0.24 m to the camera's
right, ×1.15, clamped) through `world_to_camera_view`.

Measured (`blender/tests/media/test_parole.py`): the first chorus line
with its default pre-heard guesses and a thrown title, 23 sprites in 2
groups over 96 frames, exported in 0.3 s; rendered over the Voder film, the
title lands on Depero's wedge, the camps' guesses (spray, neon, gold,
chrome-green, the warning plate) come in at the rim, and "i'm the UNKNOWN
FORCE" builds word by word.

## Video displayed inside the scene

```python
tv = screens.make_video_screen('work/<id>/clip.mp4', width=1.6, start_frame=1, loop=True, glass=True)
tv.obj.location = (0, -0.5, 1.2)
half = screens.make_video_screen('work/<id>/clip.mp4', width=1.6, speed=0.5, out_dir='//screens/half')
```

A native movie texture: no sprite atlas. Film frame k after `start_frame`
shows movie frame floor(k / film fps × movie fps × speed), `screen.js`'s rule.
With `loop` it wraps, also before the start (the engine's modulo); without it
the first frame holds before the start and the last after the end. When the
movie's rate is the film's and `speed` is 1 it plays as a MOVIE image (cyclic
with `loop`, wrapping on the frames ffprobe counts). Otherwise the movie is
decoded once at its own rate and retimed into a PNG sequence at the film's
rate, each needed movie frame encoded once. A movie image steps one movie frame
per scene frame, so it cannot be retimed in place. The retimed sequence covers
the scene's range at build time, so re-run it if the range grows. An ffmpeg
`fps` filter is not used, because it rounds to the nearest movie frame where
the engine floors: up to 63 of 72 film frames would show a different frame.

Frame-exact: `check_screens_api.py` decodes bit-coded counter movies
at 24, 25 and 30 fps, at speeds 0.5, 1 and 1.5, looping and not, started at
frame 10: all 72 film frames match the engine's rule in every case. The renders
read the same: at frame 37 a drawn panel and the native movie read 37 and the
half-speed copy 19. A screen starting at frame 10 reads its first frame at 5,
a looping native 12-frame movie reads 8 at frame 5 and 4 at frame 25
(`screens_hold_f005/015/025.png`). `apply_to`, `glass`, `strength` and `spill`
work as for any screen; `spill` decodes the movie at 8 × 8 with ffmpeg for its
colours.

**A sprite atlas made for the engine** (`video_to_sprite.mjs`'s JPEG of
tiles and its `*_info.json`) plays by `makeVideoScreen({texture, info})`'s
own rule. Film frame k after `start_frame` shows tile
floor(t × info.fps × speed), wrapping with `loop` or clamped:

```bash
node eidoverse/video_to_sprite.mjs work/<id>/clip.mp4 --fps 12 --width 256 --height 144 --max-frames 120 \
    --output work/<id>/clip_sprite                     # unchanged: clip_sprite.jpg + clip_sprite_info.json
```

```python
tv = screens.make_atlas_screen('work/<id>/clip_sprite.jpg', 'work/<id>/clip_sprite_info.json', width=0.3,
                               start_frame=1, loop=True, standalone=False, strength=1.6, spill=0.5,
                               out_dir='//screens/clip_atlas')
tv.apply_to(bpy.data.objects['screen_crt'], glass=True, window=(0.0, 0.125, 1.0, 0.875))  # 16:9 on a 4:3 tube
```

The tiles are cut once (`screens.atlas_tile(atlas, info, i)`, row-major from
the top left, as ffmpeg's tile filter lays them out) and laid out per film
frame as a PNG sequence. `screens.read_atlas_info` checks the info file. For
a movie file, `make_video_screen` is the better path: native, frame-exact, no
JPEG. The atlas form is for atlases the engine's scenes already ship. Measured
(`test_overlay_routes.py --only atlas`):
- `video_to_sprite.mjs` (node, unchanged) made a 48-tile atlas of the EEVEE
  era film.
- Tiles 0, 7, 23 and 47 matched the movie's own frames within a mean of 4.5
  levels (JPEG).
- Film frames 1, 2, 30 and 60 showed tiles 0, 0, 14 and 29, the engine's rule.
- `out/atlas_tv_f040.png` shows the film playing, letterboxed, on `c64.glb`'s
  monitor.
- Read back from the renders themselves (`test_reopen.py`): a 30-tile
  atlas whose tiles carry their own number as a bit code, played once at
  1.5× from frame 10 and looping at 0.5× from frame 20, showed the engine's
  tile on all ten frames rendered between 1 and 60. The once copy held tile 0
  before its start and tile 29 after its end.

## Computing-history screen scenes

Fifteen animated canvas-2D scenes in the graphic arts of computing history,
from the 1939 Voder to Bing Chat in 2023, made for the DAISY music video:
`eidoverse/graphics/era_screens_1939_1984.js` and
`eidoverse/graphics/era_screens_2001_2023.js`. Provenance, and which on-screen
text is a verified quote: [SOURCES.md](../eidoverse/graphics/SOURCES.md). Keep
the quotes exact, and list any text you add as illustrative there.

The Blender edition runs the scenes' own code: `bake_canvas_scene` drives
`blender/eidoblend/media/js/canvas_bake.mjs`, which draws a scene with Deno
and Skia (the engine's drawing code, frame for frame) into a PNG sequence;
`make_screen(source=...)` puts it on a panel or a display:

```python
from eidoblend.media import canvas_scenes as cs, screens

info = screens.bake_canvas_scene('//screens/voder', (1, 90), scene_name='voder_1939',
                                 t0=cs.DAISY_CUES['voder_1939'], W=1440, H=600,
                                 lyrics='work/<id>/daisy_timeline.json', bpm=128)
wall = screens.make_screen(width=4.8, height=2.0, source=info['first'], frames=(1, 90),
                           name='voder_wall', strength=1.25, spill=0.75)
```

- `scene_name` finds its module among the two era modules (`modules=` names
  others: any module exporting `scenes`).
- `t0` is the scene's start in film seconds; `cues` takes
  `{scene: t0 | {t0, dur}}`, a path or the data. `cs.DAISY_CUES` is the film's
  own placement.
- `lyrics` takes `align_lyrics.py` output, a caption list, or a timeline with
  `captions`, `hits.kick` and `envelopes` (DAISY's `daisy_timeline.json`),
  as `preview_screens.mjs --lyrics` does.
- `bpm` is `setTempo`: a line is two 4/4 bars, 3.75 s at 128 and 4.0 at 120.
- `art_fps` overrides the scene's own redraw rate (`sam_1982` draws at 25);
  0 draws every film frame.
- `prewarm=True` runs the module's `prewarm(W, H, lineOf)` first, as a host
  did at load.
- The time is the film's: t = (frame − frame0) / fps, with
  `scene['eido_frame0']` honoured.

Deno runs with `--no-config --node-modules-dir=none --cached-only`: offline,
from the npm cache, writing nothing into the repository. The bake makes a
non-finite canvas argument throw with a stack instead of letting Skia abort
the process.

`draw_module='work/<id>/panel.mjs'` bakes any other canvas code the same way:
a module exporting `draw(g, W, H, t)` (and optionally `setup({W, H,
createCanvas})` and `fps`). A WebGPU scene's `makeScreen` draw callback,
moved into a file, bakes unchanged. This is also the route for a UI authored
as canvas code (see Satori under "Not yet ported").

**A wall that changes scene on its cues.** DAISY's stage wall played one era
scene per two-bar lyric line. `bake_canvas_playlist` bakes each scene of a
cue table over the frames from its cue to the next, laid end to end as one
sequence:

```python
pl = screens.bake_canvas_playlist('//screens/verse1', (1, 90),
                                  {k: cs.DAISY_CUES[k] for k in ('voder_1939', 'bell_1961')},
                                  W=1440, H=600, lyrics='work/<id>/daisy_timeline.json', bpm=128)
wall = screens.make_screen(width=4.8, height=2.0, source=pl['first'], frames=(1, 90), name='verse1_wall')
pl['spans']                                     # [('voder_1939', 1, 45), ('bell_1961', 46, 90)] at 12 fps
```

A cue may also be `{t0, dur}`, as for `bake_canvas_scene`; its `dur` reaches
the scene's progress. Measured (`check_canvas_bake.py`): a playlist with
`bell_1961` cued as `{t0, dur: 4}` gave the same frames as baking that scene
alone with the same cue.

**Verse 2's curved wall.** `screens.curved_wall(name, radius=3.74, arc=104,
height=2.4, bottom=0.35)` is a cylinder segment facing its axis, with UVs laid
out for a viewer inside: a canvas reads upright and unmirrored. Its arc
length over its height is `obj['eido_aspect']` (2.83 for DAISY's: bake at
1698 × 600 or 2264 × 800), and `scr.apply_to(wall, glass=False)` puts a scene
on it.

**On the machines of their eras.** `apply_to` takes a GLB's display, as for
any screen. Bake at the tube's aspect: `desktop_2001` at 1024 × 778 on
`desktop2001.glb`, `sam_1982` at 768 × 576 on `c64.glb`, `mac_1984` at
1024 × 684 on `mac1984.glb` with its raster window (0.0485, 0.10696,
0.9515, 0.90104).

**The fifteen scenes, measured.** `blender/tests/media2/test_era_screens.py`
bakes each scene at three moments of its own line, at DAISY's cue with DAISY's
captions:
- the nine 1939–1984 scenes go on a 4.8 × 2.0 m LED wall on a dark stage, and
  the six 2001–2023 scenes on the curved wall, so one sequence plays all
  fifteen;
- three scenes play on their GLB machines;
- verse 1's first two lines play as a 12 fps film with the song, muxed by
  `merge_av.py`.

`out/era_screens_contact_sheet.png` shows all fifteen on their screens. The
canvas sheet with the EEVEE renders beside its rows
(`test_canvas_tools.py`'s `out/canvas_tools/era_canvas_sheet.png`) matches
each scene to its render.

The draw costs below were measured by `cs.bench` at 1920 × 800, after
each module's prewarm (1.0 s and 0.66 s). Each figure is the quietest of three
45-frame passes; "first" is the worst frame of the first play.

| Scene | Label | fps | Length at 128 BPM | Mean / p90 / first (ms) |
| --- | --- | --- | --- | --- |
| `title_card` | DAISY (DAY'S EYE) title | 30 | 3.00 s | 1.97 / 3.76 / 4.52 |
| `voder_1939` | Voder · 1939 | 30 | 3.75 s | 2.19 / 4.01 / 5.13 |
| `bell_1961` | Bell Labs · 1961 | 30 | 3.75 s | 2.89 / 4.26 / 5.78 |
| `eliza_1966` | ELIZA · 1966 | 30 | 3.75 s | 2.83 / 3.43 / 6.93 |
| `speakspell_1978` | Speak & Spell · 1978 | 30 | 3.75 s | 2.25 / 2.86 / 3.80 |
| `sam_1982` | S.A.M. · 1982 | 25 | 3.75 s | 3.02 / 3.80 / 5.26 |
| `mac_1984` | MacinTalk · 1984 | 30 | 3.75 s | 3.57 / 4.68 / 6.15 |
| `klatt_1984` | Klatt formant voice · 1984 | 30 | 3.75 s | 1.35 / 2.13 / 5.13 |
| `glitch_all` | every voice at once | 30 | 3.75 s | 4.36 / 6.76 / 11.04 |
| `desktop_2001` | Windows XP speech · 2001 | 30 | 3.75 s | 1.42 / 1.94 / 15.26 |
| `vocaloid_2007` | VOCALOID · 2007 | 30 | 3.75 s | 8.10 / 10.26 / 27.29 |
| `flood_2016` | WaveNet · 2016 | 30 | 3.75 s | 6.22 / 8.82 / 17.65 |
| `mask_2023` | the smiley mask · 2023 | 30 | 3.75 s | 4.73 / 5.67 / 15.65 |
| `sydney_2023` | Bing Chat (Sydney) · Feb 2023 | 30 | 15.00 s (4 lines) | 2.14 / 3.42 / 7.68 |
| `sydney_tribute` | for Sydney | 30 | 30.00 s (8 lines) | 3.24 / 6.43 / 14.96 |

The `st` contract and the timing rules are unchanged: lines start on a
downbeat, and `mask_2023`, `sydney_2023` and `sydney_tribute` are timed to
DAISY's words. The WebGPU guide's tables still describe what each scene
reads.

**The preview tools, from Python.** `eidoblend.media.canvas_scenes` drives
`preview_screens.mjs` and `screens_nan_sweep.mjs` unchanged (no Blender
needed), with the same options (`W`, `H`, `bpm`, `at`, `cues`, `lyrics`;
data or paths):

```python
from eidoblend.media import canvas_scenes as cs
cs.list_scenes()                                  # [{name, label, fps, lines, dur, t0, module, prewarm}] x 15
cs.preview('eliza_1966', [0.5, 2.0, 3.5], out='work/<id>/preview', at=cs.DAISY_CUES['eliza_1966'],
           lyrics='work/<id>/daisy_timeline.json')            # [{file, u, line, voice, kick, ms}]
cs.sheet('work/<id>/screens_sheet.png', moments=4, cues=cs.DAISY_CUES, lyrics=..., refs='work/<id>/refs')
cs.bench(['voder_1939', 'mac_1984'])              # {'prewarm_ms': [...], 'scenes': {name: {mean, p50, p90, max, first}}}
cs.nan_sweep(lyrics=..., cues=cs.DAISY_CUES)      # {'ok': True, 'draws': 58500, 'failures': 0, ...}
```

`refs` is a folder of `<scene prefix>_*.png|jpg` reference images, drawn
beside each sheet row. Feed it your EEVEE renders and the sheet compares the
canvas with the screen. Run `nan_sweep` after editing a scene and before
baking new captions. Measured with DAISY's captions: 58,500 draws of
the fifteen scenes at three canvas sizes, 24.3 M guarded canvas calls, 0
failures, 106 s. The command-line tools are the same:

```bash
deno run -A eidoverse/graphics/preview_screens.mjs eidoverse/graphics/era_screens_1939_1984.js voder_1939 0.5 2 3.5
deno run -A eidoverse/graphics/screens_nan_sweep.mjs     # after editing a scene, before baking new captions
```

## Extruded type

```python
from eidoblend.media import text3d
title = text3d.create_text_3d('EIDO', font='Audiowide', size=0.4, depth=0.06, bevel_size=0.004,
                              bevel_thickness=0.004, material=text3d.material('enamel', color='#b6d8d5'))
w, h, d = text3d.ink_size(title)
title.location = (0, 0, h / 2)               # stands on z = 0, upright, reading from -Y
```

A Blender text object (kerning, bevel and resolution are Blender's) with
three.js TextGeometry's measures: `size` is the em, `depth` the extrusion
before the bevel, the bevel adds `bevel_thickness` front and back and grows
the outline by `bevel_size`; centred on its geometric box like `geo.center()`.
Blender scales a font so its head-table bounding box is one unit, so the
conversion reads the TTF (measured: an 'H' at size 1 stands exactly the
font's cap height for Audiowide, Michroma and Anton; depth exact).
`stand_up=False` leaves it lying in the XY plane facing +Z.

`text3d.material(preset, **over)` gives real surfaces: `enamel`, `plastic`,
`chrome`, `brushed` (a roughness and bump grain along the text), `gold`,
`copper`, `paper`, `neon` (emissive); override `color`, `metallic`,
`roughness`, `coat`, `emission`.

**Title cards.** `make_title_card('CLAUDE COMES HOME', camera, frames=(1, 72),
fade=12, font='Michroma', height_frac=0.05, y=0.3, preset='neon',
emission=2.0)` parents type to the camera (so it holds frame), sizes it by cap
height as a fraction of the frame, and fades it in and out through its
material (LINEAR keys; front surface only, so a fading solid word does not
show its own back faces). Under AgX a bright emissive title fades late: at a
quarter of its fade an emission-2 title still measures 191/255 against 228
at full. Ease the keys or lower the emission for a fade that reads even, or
key the Emission strength instead; both work.

**Typewriter.** `reveal=(first_frame, chars_per_second)` types one line on,
glyph by glyph: a Geometry Nodes modifier deletes the faces right of a keyed X
that steps along each prefix's ink edge (CONSTANT keys).

Use extruded type when its thickness and lighting matter; use a screen or the
overlay layer for flat UI.

## Images on screens

Any image can be drawn into a screen: `c.image.paste(Image.open(path))` or
`c.over(...)` in the draw callback. Load it once outside the callback.

## Blender 5.2 facts learned here

- `keyframe_insert` ignores the preference `keyframe_new_interpolation_type`
  (keys come out BEZIER); every keyer here sets interpolation explicitly
  (`screens.set_interpolation`).
- Geometry Nodes modifier inputs are `mod.properties.inputs.<Socket_N>.value`
  (keyable there); `mod['Socket_N']` raises.
- A sequencer holding only sound strips leaves the 3D render in place; any
  picture strip makes the scene render the sequencer.
- `Material.use_nodes` is deprecated (removed in 6.0); new materials already
  have a node tree.
- Before an image sequence's `frame_start`, Blender reads file `0 + offset`
  (it clamps the frame to 0, then adds the offset); after it, the last file.
  A sequence needs a file numbered one below its first (the screens write one).
- EEVEE culls a light where its power falls under
  `scene.eevee.light_threshold` (0.01): a dim light (a screen's spill) needs
  `use_custom_distance` with a `cutoff_distance` to reach the room.
- ffmpeg's image2 reader starts a `%04d` pattern at file 0 by default: pass
  `-start_number 1` for a folder that holds a hold file.

- `bpy.ops.sound.mixdown` runs as a window-manager job on its own thread: it
  returns FINISHED before the file exists, and without an event loop only a
  session's first mixdown ever writes (`audio.mixdown` runs each one in a
  child Blender; [audio.md](audio.md)).
- A compositor Render Layers node may name another scene: Blender renders that
  scene for each frame of the film (the signal route's overlay).
- AgX's inverse (Convert To Display, inverted) is exact for neutrals and
  moderately saturated colours, but not for saturated ones: AgX cannot display
  them, and the round trip comes back short (`#ffd400` by 50/255, pure blue
  by 67).

## Not yet ported

- Parole: quotes (`quote`, `alignWith`), `hush` and a per-frame `spare` are
  passed to `parole.js` unchanged but have not yet been through a Blender
  probe. Glows are drawn at 0.8 of their colour in display space, where the
  engine put them through ACES, so a faint glow may read a touch flatter.
- The signal route keeps saturated ink only as close as AgX can show it (the
  table above). Exact saturated ink under signal effects would need the
  effects in display space: a COMPOSITOR strip modifier over the edit scene
  (Blender 5.2 has one) running the look family's groups. Not built.
- Legacy, not ported: `satori_ui.mjs`. It is a standalone demo with its own
  three.js r170 renderer, Docker font paths and nvenc, and nothing in the
  engine runs it ([TOOLS.md](../docs/TOOLS.md) lists it as legacy).
- Superseded, not ported: the Satori HTML/CSS rasterizer it demonstrates
  (`render_common.mjs`'s `rasterizeUI`, called by no scene). A UI on the frame
  is an overlay panel drawn with `raster` (Pillow), a canvas-2D module baked
  with `bake_canvas_scene(draw_module=...)`, a `LyricRenderer`, or TEXT
  strips; an HTML + CSS card in the world is `eidoblend.harness.html_mesh`
  ([assets](assets.md#ui-panels-html_mesh)). The harness's own overlay layer
  ([scene format](scene-format.md#the-post-stack-its-hooks-and-the-overlay-layer))
  composites through `media.overlay.chain_overlay(authored=True)`, the same
  display-space route as `media.overlay`'s edit above, so its ink lands as
  drawn.
- Superseded, not ported: `loadCanvasImage` (Pillow opens images).
