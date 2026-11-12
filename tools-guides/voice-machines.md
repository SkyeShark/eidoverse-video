# Historical voice machines, 1939–2001

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Props and sets](props-and-sets.md) · [Motion graphics](motion-graphics.md)

This is the Blender edition (Blender 5.2, EEVEE, AgX). Eight machines that
spoke or sang, first made for the DAISY music video's museum of voices, are
free props for any new piece, built by name from `blender/eidoblend/props/`;
nothing in them runs on that song's clock. Each one is the pack's model
(`eidoverse/assets/models/voice_machines/`, the GLBs the Blender scripts in
`models/voice_machines_src/` built and the WebGPU modules load) with its
runtime parts made in Blender: the screens and their drawings,
the CRT switch-on, the LEDs, the surfaces the voice lights from inside, the
runtime metal. `update(t, state)` keys everything it changes, so a saved
.blend plays and renders any frame on its own. The probes that show each
machine working are in `blender/tests/voice_machines_a/` (C64, Macintosh,
DECtalk, the 2001 desktop) and `blender/tests/voice_machines_b/` (the Voder,
the mainframe room, the Teletype, the Speak & Spell).

Everything is in metres, Blender axes: +Z up, every machine resting on z = 0
of its root, its front toward −Y.

Every machine is built by one call and animated by `update(t, state)`, as in
the engine. What is new in Blender: `update` **keys** what it sets at the
frame of `t`, so the saved `.blend` plays and renders any frame on its own, in
any order. Build a machine with a scene's `ctx` and every update keys through
`ctx.key` without being told (the runner then sets the keys' interpolation);
`ctx=` on a single `update` does the same, `frame=` places a key by hand, and
`key=False` only poses (a still). The era-1 machines (the Voder, the
mainframe, the teletype) key LINEAR; the era-2 machines, the Speak & Spell
among them, key CONSTANT channels (below). Drawings that change over time (a
screen, the teletype's character buffer, the Speak & Spell's display) are PNG
sequences that get a new file only on the frames whose drawing changes. Call
`update` in time order, as the engine did: the mainframe integrates its tape
speed frame to frame. `dispose()` removes everything a machine's `build` made
(objects, meshes, materials, maps, node groups, keys and its collection) and
nothing else. The 1896 tandem, built through the same registry, is in
[props and sets](props-and-sets.md#the-1896-tandem).

## Build one by name

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend import props
from eidoblend.props import voice_machines as VM

props.NAMES          # ['voder', 'mainframe', 'teletype', 'speakspell', 'c64', 'mac1984', 'dectalk', 'desktop2001', 'tandem']
c64 = props.build('c64', screen_dir='//screens/c64')       # or VM.build_machine('c64', {...}), or c64.build()
c64.group.location = (0.0, 0.0, 0.74)                      # the root Empty: on a desk top
c64.parts['screen'].set_text(['READY.', 'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.'], True)

for f in range(1, 241):                                    # in time order, t in film seconds
    t = (f - 1) / 24
    c64.update(t, {'power': min(1.0, t / 0.6), 'voice': loudness(t)})
```

`props.build(name, opts, **kw)` builds a machine through
`voice_machines.build_machine` (it stamps the root with the machine's record,
`group['voice_machine']`) or the tandem through `props/tandem.py`; options come
as a dict, as keywords, or both. Nothing is imported until a name asks for
it: `props.REGISTRY` maps names to modules, `props.load(name)` /
`VM.load_machine(name)` import one (the Voder's module also carries its
`pattern(t)`), and a registered module that is not on disk yet raises
`ModuleNotFoundError` naming the file.

`VM.MACHINES[name]` is index.js's record in Blender axes: `year`, `title`,
`era` (1: layered at runtime from AmbientCG sets, masks and decals; 2: baked
maps), `text` (the screen or paper API), `drive` (the state keys),
`footprint` (the measured bounding box, width x × depth y × height z) and
`center` (its XY centre offset from the root). To centre a machine on a
pedestal, add the negation:

```python
cx, cy = VM.MACHINES['mac1984']['center']
mac = props.build('mac1984', text='hello')
mac.group.location = (x - cx, y - cy, 0.74 - 0.0025)        # 2.5 mm into a desk top 0.74 m up
```

Seat a machine a couple of millimetres into the surface it stands on. The
keyboards' bottoms are flat, so on the surface they share its plane (EEVEE
z-fights coplanar faces, and the placement audit flags any pair within 2 mm),
and proud of it they would hover.

| Machine | Year | Footprint W × D × H (m) | Screen / text | update state |
| --- | --- | --- | --- | --- |
| `voder` | 1939 | 1.28 × 1.32 × 1.70 | none | `voice, power` or `keys[10], wrist, stops[3], quiet, pedal, level, power` |
| `mainframe` | 1961 | 4.58 × 2.81 × 1.87 | none | `tape_speed` / `tape_stop` / `tape_pos`, `voice, power` (in time order) |
| `teletype` | 1966 | 0.60 × 0.76 × 1.07 | the paper: `text, n_chars` | `text, n_chars, voice, power` |
| `speakspell` | 1978 | 0.18 × 0.10 × 0.26 | `parts['display'].set_text('LOVE')` | `power, voice` |
| `c64` | 1982 | 0.41 × 0.69 × 0.34 | `parts['screen'].set_text(lines, cursor_on)` | `power, voice, lines?, cursor_on?` |
| `mac1984` | 1984 | 0.45 × 0.50 × 0.34 | `parts['screen'].set_text('hello')` | `power, voice, text?` |
| `dectalk` | 1984 | 0.46 × 0.31 × 0.10 | none | `power, voice` or `leds: [power, speech, back]` |
| `desktop2001` | 2001 | 1.15 × 0.91 × 0.45 | `parts['screen'].set_text('reading screens')` | `power, voice, text?` |

A state written the JS way (`cursorOn`, `nChars`, `tapeSpeed`) works too:
`update` snake-cases its keys.

## How a machine becomes Blender data

- **The model.** The first machine of a kind imports its GLB once per blend
  into a collection that is in no scene (`vm_source_<name>`, kept by a fake
  user). Each build copies those objects under its own root Empty and its own
  collection. The baked parts (cases, keys, monitors) share the source's
  meshes, imported materials and packed maps, so a second C64 costs no second
  set of textures. Glass, LEDs, glow surfaces and metal get their own mesh
  copy and this machine's materials.
- **The surfaces.** The era-2 GLBs carry colour at 2048², normal and packed
  AO/roughness at 1024² (512² on small parts). Blender's glTF importer builds
  the same Principled graph the WebGPU `bakedMaterial` did (colour, the packed
  map's G as roughness, the normal map at its scale). The baked AO map stays
  in the file unwired, the edition's rule for every baked AO map (as
  `harness.assets.load_pbr` does): three's `aoMap` darkens indirect light only,
  Blender's Principled has no indirect-only input, and EEVEE's horizon scan
  and ray-traced GI occlude the indirect light themselves (multiplying the map
  into the albedo would darken the key light's direct light too).
- **The uniforms.** Every WebGPU uniform of a machine (a screen's power and
  gain, each LED's level, the voice glow) is a float custom property on its
  root (`c64.group['led_monitor']`), and the materials read it through a
  one-variable driver (no Python expression, so it evaluates in a blend opened
  with auto-run off). `update` computes the values as the engine did and keys
  them at the frame of t, CONSTANT (a uniform holds what the last update set);
  a value that repeats the last key is skipped. The first key of a property
  after the scene's first frame also keys the value before it on the frame
  before. Build with `interpolation='LINEAR'` to blend between frames instead.
- **The screens.** A machine's drawing is a PNG sequence through
  `eidoblend.media.screens` (`<screen_dir>/screen/<name>_0001.png` = the
  scene's first frame). `update` draws a new file only when the drawing
  changes (new text, a cursor blink); the frames between are hard links to the
  last drawing, so a long hold costs no disk, and after the last file Blender
  holds it. Give `screen_dir` a lasting folder (`work/<id>/…` or `//…` beside a
  saved blend); without one the frames go beside the saved blend
  (`//eido_screens/<blend>/…`) or to a folder of their own under the system
  temp folder.
- **In a harness scene,** pass `ctx=ctx` to the build (or to `update`): keys
  go through `ctx.key` with their interpolation (the runner applies it after
  `render_frame`), frames come from `ctx.frame_at(t)`, and screens default to
  `<out_dir>/screens/<machine>`.

```python
from eidoblend import props
PC = None

def setup(ctx):
    global PC
    PC = props.build('desktop2001', ctx=ctx, text='reading screens')
    PC.group.location = (0.0, 0.2, 0.74)

def render_frame(ctx, t, i):
    PC.update(t, {'power': 1.0, 'voice': voice_env(t)})      # keys through ctx.key, CONSTANT
```

`dispose()` removes what the machine made (its objects, own meshes,
materials, screen images; `files=True` also its PNG folders) and the imported
source once no machine of that kind is left.

## The era-1 machines: one craft kit

The Voder, the mainframe and the teletype share the engine's era-1 craft kit,
which lives once at the top of `voder.py` (`mainframe.py` and `teletype.py`
import it). Each machine imports its GLB, swaps every `era1_<role>` slot for a
layered role material, and draws its labels and logos as canvas decals:

* **Role materials** (`role_mat`): an AmbientCG set on UV0 at its real repeat,
  recoloured by luminance (`lum`, `lum_contrast`, `tint`), the pack's baked
  masks on UV1 (R = AO over 30 cm, G = edges, B = AO over 4 cm), and on top:
  grime in cavities, chipped convex edges, dust on up-facing surfaces, mottle,
  and fingerprint / smear maps breaking the roughness. Every engine option
  ports by its snake_case name (`rough_mul`, `edge_color`, `imperf_repeat`…).
* **EEVEE translations**, measured on the probes: the engine applied AO to
  indirect light only. EEVEE's horizon scan already occludes indirect light at
  the 30 cm scale, so mask R is not applied again; the 4 cm cavity term (B),
  which screen space cannot resolve at a distance, darkens the base colour
  (`albedo × mix(1, 0.65 + 0.35 cav, ao)`). A scene rendered with ray tracing
  and the horizon scan off loses the 30 cm term, which the engine applied to
  indirect light. The engine's `curvature()` (screen derivatives of the
  normal) is a per-triangle attribute `eido_curv` (1/m), the trace of the
  shape operator from the corner normals, written once at build.
  `mx_fractal_noise` is Blender's Noise Texture with Normalize off (the same
  hash and gradients as MaterialX, `fx/_noise.py`). Every role material draws
  both faces: the pack's closed shells look the same as with three's
  `FrontSide`, and a single-sided panel seen from behind never vanishes.
* **Canvas decals**: the engine drew its plates with canvas-2D; `Ctx2D` is
  that canvas on numpy + Pillow (paths, arcs, Béziers, gradients, text with
  align and baseline, shadow blur, global alpha, strokes with miter joins),
  supersampled 3×. Fonts resolve as Skia's lookup did: Bahnschrift, Segoe UI,
  Lucida Console from Windows, the repo's bundled faces elsewhere. Images are
  packed into the `.blend`. `canvas_tex(name, w, h, draw)` keeps the canvas:
  `.redraw(fn)` draws more on it and repacks the image (`.tex`).
* **Decals on their panels**: the engine drew decals with a polygon offset;
  EEVEE has no depth bias, so `seat_decals` measures each decal quad against
  the panel behind it (rays along its normal) at build: a corner grazing the
  panel (the Voder's labels touch it at 0.01 mm) moves out to 0.2 mm, and a
  quad floating off it is laid onto the surface. The teletype's TT monogram
  stands vertical 9 to 16 mm in front of the cover's 12.7° face in the pack's
  GLB (and so in the engine); here it lies on the cover, 0.6 mm off. The
  probes check every decal of the three machines at 0.15 to 1 mm.
* **Runtime parts**: `mesh(geo, mat, seed, name)` is the kit's `K.mesh`, the
  part's seed written on every vertex (`aSeed`); `rbox`, `sphere_geo`,
  `cylinder_geo`, `box_geo`, `torus_geo` and `lathe_geo` are three's
  geometries in three's axes, turned into Blender's when the object is made.
  They equal three r184's own (positions, normals, UVs and triangles, to
  float32) on the parts the machines build, RoundedBoxGeometry's atlas-cell
  UVs and LatheGeometry's uneven normals included (`test_kit_geometry.py`).

### The Voder (1939)

```python
import math, sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.props.voice_machines import voder

vo = voder.build()                       # 1.28 x 1.32 x 1.70 m, the console plays itself
vo.group.location = (0, 2, 0)
vo.animate(lambda t: {'voice': 0.5 + 0.5 * math.sin(t * 3), 'power': 1}, frames=(1, 96))
# or full control, per frame:
vo.update(t, {'keys': [0.8] + [0] * 9, 'wrist': 1, 'stops': [0, 0, 0], 'quiet': 0, 'pedal': 0.5}, ctx=ctx)
voder.pattern(t)                         # the demo fingering: keys[10], stops[3], quiet, wrist, pedal, level
```

`voice` (0..1) plays the demo fingering gated by the voice, swings the level
needle (with its flutter) and lights the grille cloth from behind; `power`
lights the pilot jewel, the dial card and the grille. Given `keys`, the
machine plays them instead: `level` is then derived from the keys (and the
quiet key's 20 dB) unless it is given too. `pattern(t)` equals voder.js to
2e-16 on 401 samples. `animate` keys a range and drops the keys that change
nothing (a held value costs two keys). Parts: `keys` (each with `['band']` in
Hz), `stop_keys`, `quiet_key`, `wrist_bar`, `pedal`, `dial` {needle, face,
texture}, `lamp`, `grille`, `console`, `speaker`, `uniforms` {power, level}.
The pack's GLB has no separate `voder_grille_cloth` node (the engine found
null there); `grille` is the speaker tower, which carries the cloth slot.

### The computer room (1961)

```python
from eidoblend.props.voice_machines import mainframe

room = mainframe.build()                 # 4.58 x 2.81 x 1.87 m: four 729 drives, cabinets, the console
def run_down(t):                         # nominal, then (1 - x)^1.6 to a stop
    x = max(0.0, (t - 2.0) / 2.0)
    return {'tapeSpeed': 1.0 if t < 2 else max(0.0, 1 - x) ** 1.6, 'voice': 0.6 if 1 < t < 3.5 else 0.0}
room.animate(run_down, frames=(1, 120))
room.update(t, {'tape_stop': {'at': 2.0, 'duration': 1.5, 'curve': 2}})      # or analytic
room.update(t, {'tape_pos': 3.2})                                              # or metres of tape
room.update(t, {'power': 0.12})                                                # the lights dying
```

The reels follow the integrated tape speed exactly (trapezoid, equal to
mainframe.js on 120 frames); the clock that drives the register lamps is the
tape, so it freezes when the tape stops. The lamp logic (register bits, a
binary counter, steady and blinking indicators, the voice's sparkle) runs in
the shader as it ran on the GPU, from a per-vertex `aLamp` attribute and the
keyed root properties `clock`, `t`, `power`, `voice`; `mainframe.lamp_on_cpu`
is the same logic in Python for checks. The vacuum-column loops were one mesh
deformed from a uniform array; the deformation is affine per part, so each
loop is two objects (the runs stretched from the column mouth, the U-bend
slid) with keyed scale and location. `draw_ibm(ctx, x, y, h, ink, bg,
stripes)` is the striped wordmark homage, drawn from rectangles and arcs.
Parts: `reels` [{pivot, drive, side, pack_radius}], `lamps` {bulbs, lenses,
status, cabinets, count, uniforms}, `console`, `row`, `loops`, `uniforms`.

### The ASR-33 (1966)

```python
from eidoblend.props.voice_machines import teletype

tty = teletype.build(buffer_dir='//screens/tty')        # paper_color= as opts.paperColor
eliza = 'MEN ARE ALL ALIKE.\nIN WHAT WAY?\n'             # printed in capitals, every "?" dropped
for f in range(1, 241):
    t = (f - 1) / 24
    tty.update(t, {'text': eliza, 'nChars': t * 10, 'voice': loud(t)}, frame=f)
tty.parts['paper'].set_text(eliza, 12.4, frame=300)      # or directly
```

`set_text(full_text, n_chars)` prints 72 columns at 10 characters and 6 lines
to the inch; the newest line sits at the platen and older lines ride up the
paper, which curls back over the machine on three's own centripetal
Catmull-Rom (equal to `CatmullRomCurve3.getSpacedPoints` to 0.0000 mm). A
fractional count moves the type box to the next column, and on `"\n"` the
paper feeds one line (platen and roll turn, the type box returns). The struck
character's key goes down; with `voice` the call-control lamps flare and the
home row flutters; `power` lights the lamps. The text is drawn in the paper's
shader from the glyph atlas and the engine's 128 × 64 character buffer
(glyph, jitter, weight, ink per texel), byte for byte equal to teletype.js's
`writeBuffer`. The buffer is a PNG sequence (through the voice-machine kit's
`EraScreen`): 48 small files for 96 frames of typing, holds hard-linked; with
a scene's `ctx` it goes to `<ctx.out_dir>/screens/<root name>`. The frames
are named after the machine's root, which Blender keeps unique (`teletype`,
`teletype.001`), so two teletypes in one film each print their own text, even
when they are given the same `buffer_dir`; `dispose(files=True)` takes a
machine's own frames, and the folder once nothing else is in it. A
Blender-relative `buffer_dir` (`'//screens/tty'`) lands beside the saved
blend; in a blend not saved yet it falls back to a folder of its own under
the system temp folder. The engine sampled the glyph atlas with explicit
gradients to avoid mip seams between cells; EEVEE has no gradient sampling,
so the atlas is read with four nearest taps blended by hand (bilinear without
mips), smooth when magnified, with no seams. Each of the 53 keys is its own
object (the engine moved them in one mesh's vertex stage). Parts: `paper`
{mesh, set_text, lines(), uniforms, texture, glyphs}, `printhead`, `platen`,
`roll`, `keyboard`, `keys`, `lamps`, `body`, `uniforms` {power, voice, line,
keys}.

## The era-2 machines

### Speak & Spell (1978)

The Speak & Spell builds on the registry module's era-2 kit
(`props/voice_machines/__init__.py`: the GLB imported once per blend, baked,
metal and glow materials, `screen_material`, `EraScreen`, keyed channels).

```python
from eidoblend.props.voice_machines import speakspell

ss = speakspell.build(text='LOVE')                    # stand=False: upright on its edge, no stand
ss.parts['display'].set_text('DAISY')                 # 8 characters at most, 14 segments, unlit ghosted ~8 %
ss.parts['display'].set_text('HI', align='right')     # 'left' | 'center' | 'right'
ss.update(t, {'power': 1.0, 'voice': v}, ctx=ctx)     # the VFD flares (gain 1 + 0.55 v), the grille glows
```

The VFD is drawn as the engine drew it (black glass, ghost segments, three
glowing passes, the control grid and filaments) and shown behind its glass
with the 3.2 mm parallax recess. It leans back 0.12 rad on its wire stand
exactly as the pack's build placed it (bounds 0.178 × 0.101 × 0.260 m).
`parts['speaker'].set(v)` keys the grille glow by hand.

### Commodore 64 (1982)

The brown/beige breadbin wedge with its 13" colour monitor behind it. The
screen is the C64's own raster at double pixels (a 768 × 594 canvas): 40 × 25
characters in an 8 × 8 font drawn for this prop (2-px verticals, 1-px
horizontals; not a ROM dump), light-blue text on a blue field inside a
lighter border, a block cursor. `set_text(lines, cursor_on=True)` takes a
list of lines or one string with newlines; it upper-cases them, wraps at 40
columns (an empty line stays a line) and keeps the last 24, the screen
scrolling. `cursor_on`: `True` blinks with t (on for ⅓ s, off for ⅓ s),
`'solid'` stays on, `False` hides it. As in the engine, the drawing changes at
the next `update(t)`; `update(t, {'lines': [...], 'cursor_on': ...})` sets
the text in the same call. `build(lines=..., cursor_on=...)` sets the first
drawing (default: the SPEECH BASIC V2 boot screen).

- `power`: the raster, with the CRT switch-on (below) and the monitor's LED.
- `voice`: the raster flares with each syllable (gain 1 + 0.4 voice), the
  monitor LED pulses (0.75 + 0.6 voice), the side vents glow lavender from
  inside (0.8 voice). The computer's LED is on the whole scene.
- parts: `computer`, `keys`, `monitor` (objects), `screen` (`mesh`,
  `set_text`, `lines`, `power`, `screen`: the image sequence), `leds`
  (`computer`, `monitor`: `mesh`, `level`, `set(v)`), `speaker` (the vents).

### Macintosh 128K (1984)

The beige all-in-one, its small keyboard and one-button mouse. The screen is
a 512 × 342 1-bit canvas at native resolution (72 dpi: 180.6 × 120.7 mm) in
the middle of the black glass: the 50 % desktop, the menu bar with a 1-bit
apple, the System Disk and Trash icons, and a window with the text. The text
is drawn small with the bold UI face (Tahoma), thresholded to 1 bit, and blown
up by the largest integer factor that fits (up to 3 lines).
`build(title='Note', text='hello')`; `parts['screen'].set_text(s)`.

The 1-bit raster magnifies crisp and minifies to grey, as the engine's
nearest-magnify / mipmapped-minify texture did: EEVEE's Closest sampling has
no mips, so the material blends a Closest and a (mipmapped) Linear sample by
how many texels one pixel covers (the footprint below), and the scanlines
fade out where they get finer than a pixel. Up close every texel is a hard
square; from across the room the dithered desktop reads as an even grey
instead of a moiré.

- `power`: the raster (switch-on); `voice`: gain 1 + 0.3 voice, the rear side
  vents glow warm from inside (0.8 voice, off below power 0.01).
- parts: `computer`, `keyboard`, `mouse`, `screen` (`mesh`, `set_text`,
  `text`, `power`, `screen`), `speaker`.

### DECtalk DTC01 (1984)

The flat putty-beige synthesizer: the slanted top edge, grooves across the
front, the grey stripe, the rocker. The real DTC01 front carries only the
rocker; the two front LEDs and the speaker grille are the brief's additions in
the same groove language.

- `power` lights POWER and the READY LED on the back; `voice` pulses SPEECH
  (0.4 voice when quiet, 0.55 + 0.9 voice above 0.3) and lights the speaker
  cavity behind the grille (0.9 voice).
- `update(t, {'leds': [power, speech, back]})` drives the three directly
  (the speaker keeps its last value), and `dt.parts['leds'][1].set(0.8, t)`
  keys one LED at the frame of t.
- parts: `box`, `leds` (a list: `name`, `mesh`, `level`, `set`), `speaker`.

### The 2001 desktop

A beige mid-tower, a 17" CRT, powered speakers, a 104-key keyboard and a
wheel mouse. The CRT shows a 1024 × 768 desktop in a 1024 × 778 canvas: a
generic green hill under a blue sky with soft clouds (drawn here, not the real
wallpaper), a Luna-blue taskbar whose Start button carries our homage of the
four-tile flag, and a Narrator dialog the film fills with text (large bold
Tahoma, wrapped to the panel, 3 lines at most). `build(title='Narrator',
clock='10:23 PM', text='reading screens')`; `parts['screen'].set_text(s)`.

- `power`: the raster (switch-on); off, the monitor LED dims to 0.15 and the
  tower stays on.
- `voice`: gain 1 + 0.25 voice; the speaker cloth glows warm from within,
  brightest over each driver and through the open threads of its weave (0.8
  voice); the drive light flickers with the speech while the voice is above
  0.15 (deterministic in t: `Desktop2001.drive_flicker(t)`).
- parts: `monitor`, `tower`, `keyboard`, `speakers`, `screen`, `leds` (`mon`,
  `tw_power`, `tw_hdd`, `tw_cd`, `spk`, `kb0`–`kb2`), `speaker` (the cloth).

A redraw of this desktop takes about 1.4 s (it is drawn at 3× and averaged
down, as canvas-2D antialiases; `draw_desktop(..., ss=2)` halves it); it
happens only when the text changes.

## The CRT glass

Every era-2 screen is the GLB's own display glass (`screen_crt`) with a
screen material: the drawing as emission under a clear coat, so it reads as a
lit tube and still catches reflections. The JS options carry over by name
(`voice_machines.screen_material`): `window` (where the raster sits in the
glass's UV), `barrel` (pincushion), `scan` (scanline count) and `scan_amt`,
`corner` (the tube mask's rounded corners), `vignette`, `tint`, `bleed` (a
3-tap horizontal phosphor smear), `glow`, `parallax`, and `crt_on`: as
`power` rises from 0 the raster opens from a bright horizontal line (squeezed
by smoothstep(0.05, 0.7, power)), the collapsed line burning up to 3× brighter.
The engine faded its scanlines where they got finer than a pixel with
`fwidth`; Blender's shader nodes have no screen-space derivatives, so the fade
reads a pixel's footprint on the glass, over the tilt. `pixel_footprint(nb,
scene)` measures it in the shader itself: each point's camera-space position
against its Window position gives the metres one pixel spans there, through a
perspective camera (the depth times the pixel angle) or an orthographic one
(the ortho scale over the width), with the render size from three
one-variable drivers on the scene's resolution (no Python).
`pixel_angle(nb, scene)` is the perspective angle per pixel on its own, from
the View Vector. Neither needs a driver on the camera, so they follow cuts
and animated lenses, and a saved blend reopened with scripts off renders the
same. Do not drive a material from `scene.camera`: a driver first evaluated
while the scene has no camera (a machine is usually built before its shot's
camera) is switched off by Blender for good. The measure assumes a camera
without lens shift.

```python
c = props.build('c64')
for f, p in enumerate((0.02, 0.12, 0.3, 0.6, 1.0), start=1):
    c.update((f - 1) / 24, {'power': p})           # five frames of the switch-on
```

The glass is a clear coat over a gloss base, so it mirrors the lights:
broad, soft area lights read as a soft sheen across the tube, while a small,
hot light leaves a sharp dot on it.

## Era canvas scenes on a machine's tube

The fifteen computing-history screen scenes (`eidoverse/graphics/era_screens_*.js`,
see [motion graphics](motion-graphics.md#computing-history-screen-scenes)) can
play on a machine's own tube: `sam_1982` on the C64, `mac_1984` on the
Macintosh, `klatt_1984` or `desktop_2001` on the desktop. `show_scene` bakes
the scene with the engine's own drawing code (Deno + Skia, through
`media.screens.bake_canvas_scene`) at the tube's aspect, and mixes it over the
machine's drawing for the frame range through the same glass, raster,
scanlines, switch-on, power and gain. Before and after the range the
machine's own drawing shows (a CONSTANT-keyed root property `scene_<k>`).
The scene plays from its own beginning on the range's first frame; `t0`
(film seconds) starts its clock elsewhere, so `t0 = <that frame's time> - 2`
joins it two seconds in.

```python
c64 = props.build('c64', screen_dir='//screens/c64')
c64.show_scene('sam_1982', (49, 138))                    # frames 49-138: the scene from its start
mac = props.build('mac1984')
mac.show_scene(source='work/mac/hello_reel_0001.png', frames=(120, 200))   # any frames: a sequence, a still, a movie
```

`lyrics`, `cues` and `bpm` pass through to `bake_canvas_scene` for the
scenes that draw captions or pulse with a beat.

The default canvas is the machine's own scaled to about 1024 px wide
(768 × 594 on the C64, 1024 × 684 on the Macintosh, 1024 × 778 on the
desktop); `W` / `H` override it.

## The era-2 kit

`eidoblend.props.voice_machines` also carries the helpers the five era-2
modules share (the JS kept an identical copy in each): `rng(seed)` (bit-exact
with the JS, including its float64 seed product), `lin(hex)`, the tiling
noise (`noise_data()` / `noise_image()`, also `noise_texture()`: four
periodic fBm channels, bit-exact with the JS), `triplanar` (object space,
three's planes mapped to Blender's), `metal_material`, `glow_material`, `led_material`,
`screen_material`, `load_glb`, `EraScreen` (a drawing as a keyed PNG
sequence), `SceneLayer`, `Channel` / `Lamp` and the `Machine` base class.
`font(families, px, bold, italic)` finds a CSS-like family list in the
system's fonts as the canvas did (Tahoma, Verdana, Arial, Franklin Gothic
Medium, Trebuchet MS; DejaVu Sans elsewhere).

`plastic_material` is the kit's moulded plastic for new props in the same
style (no machine calls it: their plastics are baked): a base colour with
large-scale ageing toward `aged` (stronger on up-facing surfaces), mottling,
grime in concave fillets, polished convex edges, a little dust on top,
roughness speckle, a fine orange-peel bump in metres, and an optional printed
decal. Its edges and fillets read the mesh's curvature, which EEVEE's
shader nodes cannot derive (no screen-space derivatives of the normal, no
Pointiness): run `write_curvature(obj)` on each mesh that
wears it (a face-corner attribute, 1/m).

```python
case = bpy.data.objects['my_case']                  # a bevelled mesh, smooth shaded
VM.write_curvature(case)
case.data.materials.append(VM.plastic_material('beige', color='#d6ccb0', aged='#c9b27a', age_amt=0.6,
                                               decal=label_image, decal_rough=0.35))
```

`curvature(nb)` and `bump_normal(nb, height)` are the two pieces of it on
their own: the attribute as a socket, and a Bump node that takes a height in
metres.

### Building a new prop in the same style

The kit's geometry builders from the procedural edition are here on BMesh, so
a new prop in the machines' style needs no GLB. No machine calls them (the
machines are the pack's GLBs, built by `models/voice_machines_src/`); they are
the toolkit for what comes next. Everything is in Blender axes: the JS's
front plane `'xy'` is `'xz'` here, and things face −Y.

| Builder | What it makes |
| --- | --- |
| `rbox(w, h, d, r, seg=3)` | a rounded box: w along X, h up Z, d along Y, every edge and corner rounded at r in seg segments, with box UVs |
| `keycap(w_b, d_b, w_t, d_t, h, r)` | a rounded box whose top narrows (the sculpted-key taper) |
| `rr_points(w, h, r, n, cx, cy)` | a rounded rectangle's outline (circular corners), for rings |
| `loft_rings(rings, flip=False)` | a smooth skin through closed rings of equal count; a ring collapsed to a point closes that end |
| `rounded_rect_shape(w, h, r, cx, cy)` | an outline with quadratic corners; `shape_geometry(outline, holes, depth)` makes it a sheet (depth 0) or a closed extrusion toward −Y |
| `bake(geo, pos, rot, scl)`, `merge(geos)`, `smooth(geo)` | a transformed copy, many geometries as one, coincident vertices welded and faces smoothed |
| `planar_uv(geo, x0, y0, x1, y1, axes)`, `planar_uv_facing(...)` | UVs from a rectangle on two axes; the facing variant prints only the faces turned toward a direction and sends the rest to (−0.25, −0.25), outside any decal |
| `rounded_polyline(pts, radius)`, `wire(path, radius)` | a polyline with filleted corners (`points()`, `length`); a round tube along it, as a curve object |
| `mesh(geo, mat, name, collection)` | the object, with three's area-weighted normals, so a rounded box's flat faces stay flat |

Printed labels come from the canvas core the drawings use: `make_canvas(w, h)`
(a `Canvas2D`: rects, polygons, ellipses, strokes, arcs, text, gradients,
blur and drop shadows, composited as canvas does), `rr(x, y, w, h, r)` (the
rounded-rectangle path), `speckle(g, w, h, n, seed, colors)` (seeded wear
dots), and `canvas_texture(canvas, srgb, mips, repeat, nearest,
alpha_weighted)`, which makes it a packed image with the canvas top at
v = 1. With `alpha_weighted`, the decal's colour is bled into its transparent
texels from the alpha-weighted mip chain (`build_mips`, bit-exact with the
JS, and `bleed_alpha`), so EEVEE's own mips never pull a dark fringe into its
edge. `refresh()` re-reads the canvas. `flip_uv(mesh)` turns v-down UVs
v-up; the glTF importer already does it for the machines.

```python
import math
from eidoblend.props import voice_machines as VM

label = VM.make_canvas(512, 160)
label.fill_poly(VM.rr(8, 8, 496, 144, 18), '#2b2622')
label.text('EIDO VOICE BOX', 256, 82, 'Franklin Gothic Medium, Arial', 50, '#e3d6b0', 'center')
VM.speckle(label, 512, 160, 900, 82, ['#5a5045', '#efe6cc'], 1.2, 0.25)
tex = VM.canvas_texture(label, name='voice_box_label')

case = VM.rbox(0.26, 0.06, 0.17, 0.012)                        # 26 x 17 x 6 cm, 12 mm fillets
VM.planar_uv_facing(case, -0.118, -0.016, -0.0156, 0.016, 'xz') # the label on the front's flat band
case = VM.mesh(VM.bake(case, pos=(0.0, 0.0, 0.774)), None, 'voice_box_case')
VM.write_curvature(case)
case.data.materials.append(VM.plastic_material('case', color='#d8cdb2', aged='#cdb98a', age_amt=0.45,
                                               decal=tex.image, decal_rough=0.3))

keys = VM.merge([VM.bake(VM.keycap(0.016, 0.016, 0.0115, 0.0118, 0.0085), pos=(-0.085 + i * 0.0195, -0.035, 0.838),
                         rot=(math.radians(4), 0, 0)) for i in range(8)])          # tops toward the user
cord = VM.wire(VM.rounded_polyline([(0.06, 0.08, 0.79), (0.06, 0.14, 0.79), (0.06, 0.18, 0.743),
                                    (0.30, 0.21, 0.743)], 0.03), 0.003, 'cord')
```

`test_machines.py --only kit` builds this voice box whole (with a lofted
knob, an extruded grille with ten rounded slots, and feet), checks each
builder against the JS kit's own numbers, and renders it beside a C64
(`out/kit_voice_box.png`, `out/kit_voice_box_close.png`).

## Costs

Measured on the probes (Blender 5.2, EEVEE, 960 × 540, 16 samples):

- building a machine, the GLB import included: the DECtalk 0.1 s, the
  Macintosh 0.3 s, the C64 0.3 to 0.8 s, the desktop 1.6 to 3.2 s (most of it
  its first drawing); a second machine of a kind copies objects and shares
  the maps;
- a screen redraw: the C64 and the Macintosh 5 to 9 ms of drawing, the
  desktop 1.4 to 2.5 s (a busy machine is the slower figure), plus one PNG
  write; the held frames are hard links;
- a 960 × 540 still: 2 to 3 s.

## Verify

From the repository root (the renders one at a time on a shared GPU):

```bash
# the drawings and the kit's pure helpers against the WebGPU originals (no Blender; Deno runs the JS's own code)
python -B blender/tests/voice_machines_a/test_screens_parity.py
# the era-2 machines: API checks, then renders
bash run_blender.sh blender/tests/voice_machines_a/test_machines.py [--only api,desk,close,crt,voice,mac,scene,lineup,plastic,kit,saved]
# the machines as a new film uses them: two of a kind, one turned, a 30 fps clock from frame 1001, ortho cameras
bash run_blender.sh blender/tests/voice_machines_a/test_instances_clock_ortho.py [--only two,turned,clock,ortho,footprint]
# a whole scene through the harness: four machines powering on and speaking in turn on one desk, keyed by ctx
python eido_blender.py build blender/tests/voice_machines_a/museum/scene.json
python eido_blender.py render blender/tests/voice_machines_a/museum/scene.json --at 0.4 --at 1.3 --at 2.4 --at 3.6
# the era-1 machines, the Speak & Spell and the tandem: 154 checks (about 5 min); --render adds 34 stills (158 checks)
bash run_blender.sh blender/tests/voice_machines_b/run_all.py [--render]
# the engine's own numbers for those checks (Deno runs the WebGPU modules and three's geometries)
deno run --no-config --no-lock -A blender/tests/voice_machines_b/parity_dump.mjs \
    blender/tests/voice_machines_b/out/parity_js.json
deno run --no-config --no-lock -A blender/tests/voice_machines_b/geometry_parity_dump.mjs \
    node_modules/three/build blender/tests/voice_machines_b/out/geometry_js.json
```

`blender/tests/run_all.py --areas voice_machines_a,voice_machines_b` runs both
areas' tests in their no-render modes.

The parity test runs `drawC64`, `drawMac` and `drawDesktop` cut out of the JS
modules on @napi-rs/canvas and compares thirteen cases (scrolling, the
Macintosh's scale choice, a word too long for the dialog, empty text,
characters the C64 font lacks): the C64 raster is identical, the Macintosh
within 0.5 to 3.7 grey levels on average (FreeType and Skia hint the 12 px UI
face differently), the desktop within 0.75 to 1.15 levels, every layout the
same. It also runs the kit's own `rng`, noise, `buildMips`, `rrPoints`,
`roundedRectShape`, `roundedPolyline` and `speckle` from the JS: the first
six match bit for bit (or to 1e-12 m), the speckle has the same dots with
the same ink (within 0.3 %), differing only along their antialiased rims.
`test_instances_clock_ortho.py` builds two C64s without names into one
screen folder (each keeps its own root, channels and frames), turns the
desktop on the desk (the cloth still glows over its drivers), runs a 30 fps
film clock that starts at frame 1001 (the new text lands on its frame; the
blend reopened with scripts off renders the same), and measures
`pixel_footprint` against the camera's own metres per pixel through
landscape, portrait and orthographic cameras (within 0.1 %); its stills land
in `out/verify/`.
`test_machines.py` checks the registry, each machine's keyed update, the
cursor's blink, the footprints, `dispose`, that every driver a machine makes
is a one-variable AVERAGE with no path through `scene.camera`, the kit's
geometry builders against the JS kit's numbers, and a film saved and
reopened; its renders land in `out/` (`desk_<name>.png`, `close_<name>.png`,
`crt_switch_on.png`, `voice_<name>_<view>.png`, `mac_near_far.png`,
`scene_<name>.png`, `lineup_true_scale.png`, `plastic_runtime_vs_baked.png`,
`kit_voice_box.png`, `kit_voice_box_close.png`, `saved_reopen.png`). The
museum scene's build reports `build.unkeyed PASS` (every value `update`
changed is keyed). Look at the frames.

`test_museum_reload.py` builds the Voder, the mainframe, the teletype, the
Speak & Spell and the tandem through the registry with a scene's `ctx` (the
harness's own `Ctx`), animates them through `ctx.key`, saves the `.blend`,
reopens it and checks that frame 30 shows the same nine values (keys,
properties, the buffer sequence on disk), then renders the reopened file.
`test_two_teletypes.py` builds two ASR-33s with one `ctx` and the default
name (and two more into one shared `buffer_dir`) and checks that each paper
prints its own text and that `dispose(files=True)` takes only its own
frames; it also runs the Blender-relative `buffer_dir` of the example above
in an unsaved and a saved blend. `test_dark_room_and_back_views.py` lights
the Voder, the Speak & Spell and the 7090 console only by their own glow,
voice on and then power off, and counts the glowing pixels in each pair of
stills; it also renders the Voder from behind and the tandem from its left
(non-drive) side at speed, where the smeared spokes must shade without
sparkle.

## Not yet ported

- The baked AO maps (see above): unwired, on purpose; EEVEE's own occlusion
  replaces them.
- Text drawn by FreeType instead of Skia: the same faces, hinted a little
  differently (the parity test's numbers); Skia's synthetic bold is imitated
  with a stroke where a family has no bold face.
- `pixel_footprint` (the screens' footprint) assumes a camera without lens
  shift: with a shift its measure drifts across the frame, so the scanline
  fade and the Macintosh's nearest-to-smooth blend set in a little early or
  late.
- The desktop's speakers sit 1.3 mm into the desk: the pack's GLB places
  their bottoms there (the WebGPU edition does the same).
- The engine's CPU mip chains for canvas textures: Blender builds its own
  mips (`build_mips` stays for the decals' alpha bleed and the parity
  checks; the teletype's glyph lookup needs none).
- No side-by-side WebGPU render of these props exists to compare with: their
  parity rests on the shared GLBs, the drawings compared pixel by pixel with
  Skia, and the material code read line by line against the JS.
