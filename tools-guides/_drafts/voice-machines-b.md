# The Voder, the 1961 computer room, the ASR-33, the Speak & Spell and the tandem

[Main instructions](../../AGENTS.md) · [Tool inventory](../../docs/TOOLS.md)

This is the Blender edition (Blender 5.2, EEVEE, AgX) of five free, reusable
props: four historical voice machines and an 1896 bicycle built for two, with
a rider rig and a teapot stoker. They were first made for the DAISY music
video; here each is an asset for any new piece, with its own moving parts,
screens and time controls (nothing in them is tied to that song's clock).
The modules live in `blender/eidoblend/props/voice_machines/`
(`voder.py`, `mainframe.py`, `teletype.py`, `speakspell.py`) and
`blender/eidoblend/props/tandem.py`; the probes that show each one working are
in `blender/tests/voice_machines_b/` (they render into its `out/` folder). The
WebGPU modules they port (`eidoverse/props/voice_machines/*.js`,
`eidoverse/props/tandem.js`) and the pack's GLBs, masks, layouts and AmbientCG
sets (`eidoverse/assets/models/voice_machines/`, `models/tandem_1896/`) are
reused as they are.

Every prop is built by one call and animated by `update(t, state)`, as in the
engine. What is new in Blender: `update` **keys** what it sets at the frame of
`t` (LINEAR), so the saved `.blend` plays and renders any frame on its own, in
any order. Build a prop with a scene's `ctx` and every update keys through
`ctx.key` without being told (the runner then sets the keys' interpolation);
`ctx=` on a single `update` does the same, `frame=` places a key by hand, and
`key=False` only poses (a still). The engine's uniforms are float custom
properties on the prop's root Empty that the materials read through
one-variable drivers. Drawings that change over time (the teletype's character
buffer, the Speak & Spell's VFD) are PNG sequences that get a new file only on
the frames whose drawing changes. Call `update` in time order, as the engine
did: the mainframe integrates its tape speed frame to frame.

All five: metres, Blender axes (Z up, front toward −Y, three's +Z), resting on
z = 0 of their root, deterministic in t. They also build by name through the
registry: `from eidoblend import props; props.build('teletype', ctx=ctx)`.
`dispose()` removes everything a prop's `build` made (objects, meshes,
materials, maps, node groups, keys and its collection) and nothing else.

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
  (`albedo × mix(1, 0.65 + 0.35 cav, ao)`). The engine's `curvature()`
  (screen derivatives of the normal) is a per-triangle attribute
  `eido_curv` (1/m), the trace of the shape operator from the corner normals,
  written once at build. `mx_fractal_noise` is Blender's Noise Texture with
  Normalize off (the same hash and gradients as MaterialX, `fx/_noise.py`).
  Every role material draws both faces: the pack's closed shells look the
  same as with three's `FrontSide`, and a single-sided panel seen from behind
  never vanishes.
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
Catmull-Rom (equal to `CatmullRomCurve3.getSpacedPoints` to 0.0000 mm). A fractional count moves the type box to the next column, and on
`"\n"` the paper feeds one line (platen and roll turn, the type box returns).
The struck character's key goes down; with `voice` the call-control lamps
flare and the home row flutters; `power` lights the lamps. The text is drawn
in the paper's shader from the glyph atlas and the engine's 128 × 64
character buffer (glyph, jitter, weight, ink per texel), byte for byte equal
to teletype.js's `writeBuffer`. The buffer is a PNG sequence (through the
voice-machine kit's `EraScreen`): 48 small files for 96 frames of typing,
holds hard-linked; with a scene's `ctx` it goes to
`<ctx.out_dir>/screens/<root name>`. The frames are named after the
machine's root, which Blender keeps unique (`teletype`, `teletype.001`), so
two teletypes in one film each print their own text, even when they are
given the same `buffer_dir`; `dispose(files=True)` takes a machine's own
frames, and the folder once nothing else is in it. A Blender-relative
`buffer_dir` (`'//screens/tty'`) lands beside the saved blend; in a blend not
saved yet it falls back to a folder of its own under the system temp folder.
The engine sampled the glyph atlas with
explicit gradients to avoid mip seams between cells; EEVEE has no gradient
sampling, so the atlas is read with four nearest taps blended by hand
(bilinear without mips), smooth when magnified, with no seams. Each of the 53
keys is its own object (the engine moved them in one mesh's vertex stage).
Parts: `paper` {mesh, set_text, lines(), uniforms, texture, glyphs},
`printhead`, `platen`, `roll`, `keyboard`, `keys`, `lamps`, `body`,
`uniforms` {power, voice, line, keys}.

## The Speak & Spell (1978)

The era-2 machine builds on the registry module's era-2 kit
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

## The 1896 tandem

```python
from eidoblend.props import tandem as TD
from eidoblend.characters import load_vrm

bike = TD.build()                                     # spoke_smear=None: on unless the scene has motion blur
pot = TD.build_teapot_rider().mount(bike)             # the Utah teapot stoker, 0.35 m, on the rear saddle
me = load_vrm('claude_suit')
speed = lambda t: 2.2 * min(1.0, t / 3)               # m/s, or a number, or state['distance']
for f in range(1, 241):
    t = (f - 1) / 24
    st = bike.update(t, {'speed': speed, 'steer': 0.03 * math.sin(t)}, frame=f)
    bike.group.location.x = st['distance']            # the film owns the root
    bike.group.keyframe_insert('location', frame=f)
    TD.pose_rider(me, st['crank_angle'], bike=bike, t=t, frame=f)
    pot.update(t, st['crank_angle'], frame=f)
TD.bake_rider_springs(me, 1, 240)                     # the mane and the tie, as the engine ran them under a rider
```

`update` integrates a speed function with the engine's Simpson rule (equal to
tandem.js), turns the wheels, the geared cranks (9/24) and the level pedals,
steers about the head-tube axis, walks both chains and sets the spoke sweep
(`shutter`, default half a frame); `crank_angle` and `crank_phase` override
the geared crank. The chains are Geometry Nodes: the GLB's one-pitch link
instanced round each belt (two tangent runs, two arcs) from the keyed,
unwrapped phase; the instances land on the CPU walk to 0.000 mm
(`bike.chains['drive'].set_phase(crank)` walks one by hand). The spoke smear
(the engine's stand-in for motion blur: trailing wire vertices swing back
over the shutter and fade to wire width / swept arc) is a Geometry Nodes
rotation plus the spoke material, switched by the root property
`spoke_smear`; `build` turns it off when the scene renders EEVEE motion blur
(the harness default), which blurs the keyed wheels for real.
`bike.set_spoke_smear(on, frame=f, key=True)` switches it later (a shot with
motion blur after one without); it shows at once, where a bare write of the
property waits for the next frame change. `glb=` takes
another GLB as a path or as its bytes (the engine's `ASSETS.tandem`).
`dispose()` leaves a seated rider or a mounted teapot in the scene where it
is.

`pose_rider` seats a VRM (a `characters` handle) on the front saddle at 0.87,
leans and sways the torso with the crank, solves both legs onto the pedals
(two-bone IK, ankling from `ankle_pitch`), the arms onto the grips (the wrist
twist shared with the forearm), closes the fingers and curls the tail up
behind; it writes the normalized humanoid rotations (`VRMHandle.write_pose`)
and keys them. Every engine option ports by its snake_case name (`lean`,
`sway`, `head_pitch`, `head_yaw`, `hip_above_seat`, `hip_forward`, `sole`,
`ankling`, `toe_out`, `foot_forward`, `grip_along`, `grip_palm`,
`wrist_drop`, `finger_curl`, `tail_lift`; and, read on the first call as the
engine's rig read them, `scale`, `tail` ('curl' | 'spring') and `settle`).

`bake_rider_springs(vrm, f0, f1)` is the rest of the engine's rider rig, run
once every frame is posed: the springs swing in the rider's own frame (every
joint's center is the VRM's root, so a bike at speed does not drag the mane
back: the probe measures 0.0000° between a moving and a standing bake, where
the file's own centers would differ by 59°), the curled tail stays out of the
solver, and with `settle` the springs are pre-rolled 120 steps of 1/60 s on
the first pose, so nothing swings in from the T-pose on camera. The keys go
on the `<name>|springs` NLA track as `characters.springs.bake_springs` keys
them (`remove_springs(vrm)` takes them off).

The teapot is three's `TeapotGeometry` ported (Newell's 32 patches, Blinn's
squash undone; its vertices, normals, UVs and triangles equal three r184's),
glazed with a two-scale Worley crazing that fades as the
camera's pixel grows past the line width (the engine measured the pixel with
screen derivatives; here it is the view depth times the camera's angle per
pixel, measured in the shader by the voice-machine kit's `pixel_angle`, so it
holds for a teapot built before the scene has a camera, and across camera
cuts and lens changes); `build_teapot_rider` takes the
engine's `height`, `segments`, `color`, `pitch`, `roll`, `contact` and
`seat_offset`.

## Verify

```
cd <main checkout>
bash run_blender.sh <worktree>/blender/tests/voice_machines_b/run_all.py                    # 154 checks, ~5 min
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/voice_machines_b/run_all.py --render                           # + 34 stills, 158 checks
deno run --no-config --no-lock -A blender/tests/voice_machines_b/parity_dump.mjs \
    blender/tests/voice_machines_b/out/parity_js.json                                       # the engine's numbers
deno run --no-config --no-lock -A blender/tests/voice_machines_b/geometry_parity_dump.mjs \
    <main checkout>/node_modules/three/build blender/tests/voice_machines_b/out/geometry_js.json   # three's geometries
```

`test_museum_reload.py` builds all five through the registry with a scene's
`ctx` (the harness's own `Ctx`), animates them through `ctx.key`, saves the
`.blend`, reopens it and checks that frame 30 shows the same nine values
(keys, properties, the buffer sequence on disk), then renders the reopened
file. `test_two_teletypes.py` builds two ASR-33s with one `ctx` and the
default name (and two more into one shared `buffer_dir`) and checks that each
paper prints its own text and that `dispose(files=True)` takes only its own
frames; it also runs the Blender-relative `buffer_dir` of the example above in
an unsaved and a saved blend. `test_dark_room_and_back_views.py` lights the
Voder, the Speak & Spell and the 7090 console only by their own glow, voice on
and then power off, and counts the glowing pixels in each pair of stills; it
also renders the Voder from behind and the tandem from its left (non-drive)
side at speed, where the smeared spokes must shade without sparkle.

## Not yet ported

- `build(opts.gltf)`: a glTF already parsed by three's loader has no
  Blender counterpart; pass the GLB's path or its bytes (`glb=`).
- The engine's global flags `_seatedVRMs` and `_allowManualLocomotion`: they
  told the WebGPU character controller a vehicle carries the VRM; Blender has
  no controller running at render time, so there is nothing to tell.
- The engine's CPU mip chains for canvas textures: Blender builds its own
  mips (and the paper's glyph lookup needs none).
