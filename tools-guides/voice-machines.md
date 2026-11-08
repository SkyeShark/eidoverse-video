# Historical voice machines, 1939–2001

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Props and sets](props-and-sets.md) · [Motion graphics](motion-graphics.md)

This is the Blender edition (Blender 5.2, EEVEE, AgX). Eight machines that
spoke or sang, built for the DAISY music video's museum of voices, are built
by name from `blender/eidoblend/props/`. Each one is the pack's model
(`eidoverse/assets/models/voice_machines/`, the same GLBs the WebGPU modules
load) with its runtime parts made in Blender: the screens and their drawings,
the CRT switch-on, the LEDs, the surfaces the voice lights from inside, the
runtime metal. `update(t, state)` keys everything it changes, so a saved
.blend plays and renders any frame on its own. The probes that show each
machine working are in `blender/tests/voice_machines_a/` (C64, Macintosh,
DECtalk, the 2001 desktop) and `blender/tests/voice_machines_b/` (the Voder,
the mainframe room, the Teletype, the Speak & Spell).

Everything is in metres, Blender axes: +Z up, every machine resting on z = 0
of its root, its front toward −Y.

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

## The era-2 machines

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
reads a pixel's footprint on the glass: the view depth times the pixel angle,
over the tilt. `pixel_angle(nb, scene)` measures that angle in the shader
itself, from each point's View Vector against its Window position (which
gives the camera's field of view) and the render size (three one-variable
drivers on the scene's resolution, no Python). It needs no driver on the
camera, so it follows cuts and animated lenses, and a saved blend reopened
with scripts off renders the same. Do not drive a material from
`scene.camera`: a driver first evaluated while the scene has no camera (a
machine is usually built before its shot's camera) is switched off by Blender
for good. The measure assumes a perspective camera without lens shift.

```python
c = props.build('c64')
for f, p in enumerate((0.02, 0.12, 0.3, 0.6, 1.0), start=1):
    c.update((f - 1) / 24, {'power': p})           # five frames of the switch-on
```

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

```python
from eidoblend.media import canvas_scenes as cs

scene = bpy.context.scene
scene['eido_frame0'] = 1 - round(cs.DAISY_CUES['sam_1982'] * 24)  # frame 1 = the scene's cue in the song
c64 = props.build('c64', screen_dir='//screens/c64')
c64.show_scene('sam_1982', (1, 90), t0=cs.DAISY_CUES['sam_1982'],
               lyrics='work/daisy/daisy_timeline.json')          # captions, kicks, envelopes, as bake_canvas_scene
mac = props.build('mac1984')
mac.show_scene(source='work/mac/hello_reel_0001.png', frames=(120, 200))   # any frames: a sequence, a still, a movie
```

The default canvas is the machine's own scaled to about 1024 px wide
(768 × 594 on the C64, 1024 × 684 on the Macintosh, 1024 × 778 on the
desktop); `W` / `H` override it.

## The era-2 kit

`eidoblend.props.voice_machines` also carries the helpers the five era-2
modules share (the JS kept an identical copy in each): `rng(seed)` (bit-exact
with the JS, including its float64 seed product), `lin(hex)`, the tiling
noise (`noise_data()` / `noise_image()`: four periodic fBm channels, every
texel within one step of the JS), `triplanar` (object space, three's planes
mapped to Blender's), `metal_material`, `glow_material`, `led_material`,
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
decal. Its edges and fillets read the mesh's curvature, which Blender's
shader nodes cannot derive (no screen-space derivatives of the normal;
Pointiness is Cycles only): run `write_curvature(obj)` on each mesh that
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
- a 960 × 540 still: 2 to 3 s through the GPU slot.

## Verify

```bash
# the drawings and the kit's pure helpers against the WebGPU originals (no Blender; Deno runs the JS's own code)
python -B blender/tests/voice_machines_a/test_screens_parity.py
# from the main checkout, through the GPU slot: API checks, then renders
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/voice_machines_a/test_machines.py [-- --only api,desk,close,crt,voice,mac,scene,lineup,plastic,kit,saved]
# a whole scene through the harness: four machines powering on and speaking in turn on one desk, keyed by ctx
python eido_blender.py build blender/tests/voice_machines_a/museum/scene.json
python eido_blender.py render blender/tests/voice_machines_a/museum/scene.json --at 0.4 --at 1.3 --at 2.4 --at 3.6
```

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

## Not yet ported

- The baked AO maps (see above): unwired, on purpose; EEVEE's own occlusion
  replaces them.
- Text drawn by FreeType instead of Skia: the same faces, hinted a little
  differently (the parity test's numbers); Skia's synthetic bold is imitated
  with a stroke where a family has no bold face.
- `pixel_angle` (the screens' footprint) assumes a perspective camera with no
  lens shift: under an orthographic camera the scanlines would not fade and
  the Macintosh's raster would stay nearest-filtered.
- The desktop's speakers sit 1.3 mm into the desk: the pack's GLB places
  their bottoms there (the WebGPU edition does the same).
