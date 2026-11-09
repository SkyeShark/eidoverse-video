# The claudesona and the VRM extras (Blender edition)

[Main instructions](../AGENTS.md) · [Characters](characters.md) · [Audio](audio.md) · [Blender](blender.md)

This is the Blender 5.2 EEVEE edition of the claudesona (digi's `claude_suit.vrm`, and
`claude_suit_wardrobe.vrm` with every outfit in it) and of the VRM extras every
character shares: spring bones, eyes on a target, lipsync from audio, the
MToon or PBR look, and the turntable sheets. The packages are
`blender/eidoblend/characters/claudesona/` (the face, the wardrobe, the TuTa,
the look) and, beside it, `characters/springs.py`, `characters/lookat.py` and
`characters/lipsync.py`; the turntable is `blender/tools/vrm_turntable.py`.
Names follow the WebGPU API in snake_case (`installSuitMouth` →
`install_suit_mouth`, `makeFaceTrack` → `make_face_track`, `facePaint` →
`face_paint`). Three's `(x, y, z)` is Blender's `(x, −z, y)`.

**What changes from the WebGPU edition.** The engine writes morph weights,
spring tails, eye bones and badge poses before every render. Here each of them
is worked out once, in frame order, and **keyed**: shape keys, NLA tracks of
bone keys, custom properties on the armature read by drivers, object
visibility. A saved `.blend` plays and renders any frame on its own, and a
frame jumped to cold is the frame you get by playing up to it (the tests check
that).

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.characters import load_vrm, play_vrma_default
from eidoblend.characters.claudesona import face as F, make_wardrobe
from eidoblend.characters.springs import bake_springs
from eidoblend.characters.lipsync import key_lipsync

bpy.context.scene.render.fps = 30
me = load_vrm('claude_suit_wardrobe'); me.arm.scale = (0.87,) * 3     # the 2.00 m rig at a human 1.74 m
play_vrma_default(me, 'idle', loop=True, until=12.0)
wd = make_wardrobe(me, wear='lab_coat_1961')                          # outfits, keyed with wear(key, frame=...)
key_lipsync(me, 'work/song/vocals.wav', start_t=1.0, windows=[(1.0, 4.2)])   # its own mouth, keyed
bake_springs(me, 1, 360)                                              # petals, tie, tail: keyed, after the body moves
```

Order matters in one way: **bake the springs last**. They follow whatever
moves the body (clips, walks, turns) and the wardrobe's petal folds, so
everything that poses the character goes in first.

## The face — `claudesona/face.py`

The visible cat smile, the eyes and the lines are **painted** plates on a white
face dome. The rig's own mouth (`show MMD mouth`) slides a flat black plate
straight toward the camera: on the face at about 1.1, floating in front of it
past that, and its vowel shapes are authored flat while the face is a dome. So
the claudesona never uses its rig mouth. `install_suit_mouth` re-seats every
painted feature (at rest and at the end of every expression target) onto the
dome along its depth axis, 1.8 mm proud (the blush 1.0 mm, as a switch at
exactly 1), leaves the rig's mouth shapes at 0 and gives the hidden mouth
plate shape keys of its own, each vertex raycast onto the face 1.5 mm proud:
`claudesona.mouth.seat` (a sliver under the smile), `claudesona.mouth.wide` and
`claudesona.mouth.round`, the two openings relative to the seat.

```python
from eidoblend.characters.claudesona import face as F
face = F.install_suit_mouth(me)                         # once per character; returns the same face on a second call
mouth = F.make_suit_mouth(input_max=0.35)               # 0.35 for lipsync.py timelines, 1 for voicebox visemes
feel = F.make_face_track(TL, section_base={'chorus': {'smile': 0.5}},
                         line_cues=[(r'goodbye', {'soft': 0.8, 'blush': 1})])
face.bake(lambda t: F.merge_max(mouth.update(t, vis_at(t)), feel.at(t)), 1, 360)   # every face key, every frame
```

`face.set(weights)` writes the face now (every other face shape key to 0, as
three's `set` zeroes the influences); `face.record(frame, weights)` +
`face.flush()` or `face.bake(fn, f0, f1)` key it, LINEAR, one action on each
face mesh's shape keys. Weights are `MOUTH_OPEN` / `MOUTH_ROUND` (0..1) for the
mouth and any face shape key by name (`Blink`, `EyeClosedLeft`, `Smile`,
`MouthSmileLeft`, `MouthFrown`, `Blush` …). Zeroing removes auto-blink:
`make_suit_mouth` blinks every `blink_every` seconds between phrases.

`make_suit_mouth(input_max, floor, attack, release, open_at, close_at,
switch_dip, switch_lead, blink_every)` is the WebGPU driver line for line: one
openness signal (fast attack, slow release), opening and closing with
hysteresis so the mouth stays open through a phrase, changing vowel only at a
syllable dip or when the new vowel clearly leads. `SUIT_VISEMES` maps each
vowel to its openness and roundness.

**The viseme mouth** (instead of the suit mouth: one or the other per
character) gives the plate one shape key per mouth shape (`VISEME_SHAPES`: a
superellipse outline hung from the painted line, raycast onto the dome) and
warps the painted line itself for the rounded sounds (`LINE_WARP`: the "3"
squeezed in from the sides). Any two shapes blend into a sensible third.

```python
face = F.install_viseme_mouth(me)
track = F.make_viseme_track(F.events_from_phones(segs))      # voicebox's timed phones -> [{t0, t1, v}]
face.bake(track.at, 1, 360)                                  # at(t) -> {'viseme': {AA: .7, O: .3}, 'mouth': 0..1}
```

`PHONE_VISEME` maps ARPAbet phones to the ten visemes (M, B, P press the lips:
the line moves, no opening). `make_viseme_track(events, lead, fade, close_gap,
breath, scale)`: each event fades in `lead` before its sound, the next crosses
over it, gaps longer than `close_gap` close the mouth, long held notes breathe.

**Emotion and gaze keyed to words.** `make_face_track(TL, section_base,
line_cues, close_after_last)` reads `{sections, captions}` (voicebox and song
timelines) and returns `at(t)` → face weights: a section's resting feeling, a
line's cue eased in and out, the eyes closing slowly after the last caption.
Channels: `smile` (Smile + the smile corners), `frown`, `wide`, `soft` (0.75–0.85
reads as content, sleepy slits), `down` / `up` (the eye looks), `blush` (a
switch at 0.3) and `jaw` (a silent open mouth from 0.15). `merge_max` merges
weight dicts by the per-key maximum.

Measured (`tests/claudesona/test_face.py`): every mouth key 1.5 mm proud on
all 849 plate vertices, the painted features 1.79–1.80 mm, every expression
target's end on the dome within 0.02 mm; the drivers equal the JS module's
outputs on the same input (deno), to 1e-16. And against the JS's own geometry
(`test_face_geometry.py`: `installSuitMouth` / `installVisemeMouth` run in deno
on the same VRM): every plate, blush and mouth vertex, at rest and at the end
of every shape key (the expressions, the rig's mouth shapes, the seat, the
openings and the ten visemes with the line's warp), within 0.0002 mm.
`face.idx` names each viseme's shape key, as the JS's `idx` its morph target.

## Lipsync from audio — `characters/lipsync.py`

```python
from eidoblend.characters import lipsync as L
vis = L.visemes_from_audio('work/song/vocals.wav')            # the repo's lipsync.py, run in Blender's Python
vis = L.gate_visemes(vis, [(1.0, 4.2), (5.0, 8.8)])           # shut outside the sung lines (+- 0.12 s)
rep = L.key_lipsync(me, vis, start_t=1.0)                     # mode 'auto'
```

`key_lipsync` picks the mouth by the character: any VRM gets `aa ih ou ee oh`
keyed on its expressions with the raw values, as the engine writes them
(`media.audio.key_expressions`, every frame exact); the claudesona gets its
own mouth (`install_suit_mouth` + `make_suit_mouth(input_max=0.35)`), or with
`mode='viseme'` and `events` the viseme mouth. `emotions=feel.at` merges a face
track in by maximum. `get_mouth_openness(v)` is lipsync.py's helper. A JSON
timeline loads with `L.load(path)` and saves with `L.save(vis, path)`; a WAV
path passed straight to `key_lipsync` is analysed for you (ffmpeg on PATH).

## Outfits — `claudesona/wardrobe.py`

`claude_suit_wardrobe.vrm` holds every garment as a hidden layer. A preset
shows layers, repaints materials, hides materials, folds petals and seats a
hat; `WARDROBE` has the eighteen of the DAISY video's history of machine
voices plus the TuTa.

```python
from eidoblend.characters.claudesona import make_wardrobe, WARDROBE, preset
wd = make_wardrobe(me)                            # wears 'suit' now (or wear=...)
wd.wear('lab_coat_1961')                          # now: a still, a single-outfit film
wd.wear('cyclist_1892', frame=240)                # KEYED from frame 240: layers, paints, folds, the hat
wd.petals('mac_launch_1984', frame=300)           # another era's petals only; petals(None, frame=...) gives them back
preset('cyclist_tall', base='cyclist_1892', hat={'seat': 'auto', 'sink': 0.004, 'tilt': -9, 'scale': 1.25})
```

What each part of a preset becomes:

- `show` — each optional layer's `hide_render` / `hide_viewport`, keyed.
- `paint: {material: spec}` — every paint a material is ever given becomes a
  slot of that material, picked by the armature's float property
  `cs_paint.<material>` (keyed CONSTANT) through a driver; slot 0 is the
  material as imported. A hex colours an untextured garment and replaces a
  textured one's print (its normal map keeps the weave); the shade follows at
  0.55, the outline at 0.22. Patterns are procedural in the model's rest
  space (the `rest_position` attribute in three's axes, so a print rides the
  cloth): `stripes` (`axis` 'y' or 'x', `scale`, `width`), `blocks`,
  `herringbone` (tweed with flecks), `gradient`, `canvas`; for the petals
  `rainbow` (`top`, `bottom`), `perPetal` (a per-vertex colour per petal, the
  centre its own) and `sweep`.
- `hide: [material]` — a Geometry Nodes switch deletes that material's faces
  (`cs_hide.<material>`, keyed): the hoodie drops the jersey's roll neck.
- `fold: {'12_L': deg | [deg, scale]}` — the petal chain's root turned toward
  the back of the head from its REST direction and scaled; the spring bake
  takes it as the chain's initial state, colliders off, so the folded petal
  still springs about its fold ("hat hair").
- `hat: {seat: 'auto', sink, tilt, cant, fwd, scale, fold, foldKeys}` — the
  boater measured onto the head (its brim plane, the face disc's top edge, the
  flower's depth centre); with `seat: 'auto'` every petal the hat would cut is
  folded back (searched per petal, 150–178° × 0.30–0.65 length, on the skinned
  petal mesh) and the brim lifted clear of the petal bases. `{offset, scale}`
  places it by hand.

`wd.petal_dir(key)` gives a petal's direction in the head frame; `wd.folds`
and `wd.lift` what the last wear decided; `wd.head_frame()` the face disc's
frame; `wd.worn_at(frame)` the outfit keyed at a frame (the last keyed wear at
or before it). `wardrobe.DEBUG = True` logs paints and folds (the JS's
`WARDROBE_DEBUG`). Measured against claudesona_wardrobe.js run in deno on the
same VRM: the cyclist's automatic folds identical (`12_L` 178°/0.65, `11_R`
170°/0.65, `1_L` 150°/0.65, `10_R` 170°/0.65, `2_L` 150°/0.65), the brim lift
27.54 mm in both, the boater's centroid within 0.01 mm, and a hand-placed hat
(`{offset, scale}`) within 0.001 mm.

## The TuTa — `claudesona/tuta.py`

The UNKNOWN FORCE outfit: Thayaht's 1920 TuTa as black techwear with neon
piping (cyan on her left, magenta on her right), Balla's colour blocks, a
sodium lightning inlay, a diagonal zip, pockets, knee panels, boots, straps,
five snap-on badges (the modificanti), face paint and a sun disc. On the
wardrobe VRM `make_wardrobe` returns the TuTa wardrobe (the garment wardrobe
with these on top). Its surfaces are the WebGPU TSL rebuilt in shader nodes in
the model's rest space (the Fabric039 weave and Leather037 grain from the
shared texture library, triplanar); the uniforms are armature properties
(`cs_tuta.neon`, `.paint`, `.eyes`, `.eye_neon`, `.grime`, `.ghost.<badge>`,
`.glow.<badge>`) read by drivers.

```python
from eidoblend.characters.claudesona import make_wardrobe, FINAL_CHORUS
wd = make_wardrobe(me, wear='tuta')
wd.face_paint(True); wd.sun_disc(True); wd.neon(0.8)
for k in ('mod_red', 'mod_gold', 'mod_chrome', 'mod_warning', 'mod_spray'):
    wd.pin(k)                                              # now
wd.schedule([{'at': 131.4, 'pin': 'mod_gold'},             # a snap at film time 131.4 s
             {'at': 273.0, 'unpin': 'mod_gold', 'eject': True},          # it pops off and tumbles; its ghost stays
             {'at': 280.0, 'unpin': 'mod_spray', 'eject': True, 'linger': True}])
wd.bake(1, 9000)                                           # the JS's update(t), every frame, keyed
p = wd.badge_world('mod_gold', frame=8200)                 # {position, quaternion, flying, visible}: aim a camera
```

Bake after the wears and the `neon(level, frame=...)` keys, as the springs
are baked last: the WebGPU `update(t)` sees the outfit worn and the neon level
at `t`, and `bake` reads the same per frame (`wd.worn_at(frame)`, from the
keyed `wear(key, frame=...)` calls, and the keyed `cs_tuta.neon`), so a
scheduled badge is keyed hidden on every frame of a film where the claudesona
is not in the TuTa, and glows at that frame's neon.

`pin(key, at=None)`, `unpin(key, ghost=True, at=None, eject=False,
linger=False)`, `schedule(events)` (replaces the schedule), `clear_ghost(key)`,
`face_paint(0..1 | bool)`, `sun_disc(bool)`, `neon(level)`, `eye_lights(amount,
neon)`, `update(t, frame)`, `bake(f0, f1)`, `pinned`, `ghosts`, `uniforms`,
`badges`, `all_layers`, `base`; every setter also takes `frame=` to key it. An
ejection flies a keyed copy of the badge (the original hides at the pop),
integrated with the WebGPU edition's fixed 1/240 s step from its launch pose
(out along its normal, a lift, floaty gravity, drag, a spin, a bounce and a
slide on the floor), its glow flickering out; the pop's flare and eight embers
are camera-facing cards (a Geometry Nodes billboard toward the active camera,
as three's sprites face whatever renders) that add light as three's additive
sprites do: colour × opacity, both the sprite's shape × its fade.
`make_wardrobe(..., neon, grime, plain, eject_speed, eject_up, eject_gravity,
eject_drag, floor_z)` are the JS options. `FINAL_CHORUS` pairs each line of the last chorus with the badge
that comes off on it; `MODIFICANTI` gives each badge's camp, glow and bone.

Measured against the JS module run in deno, frame by frame through a snap, an
unsnap, an ejection and a lingering landing: every badge within 0.002 mm of
the JS's, visible on exactly the same frames, glow and ghost equal; the sparks
within 0.001 mm.

## Spring bones — `characters/springs.py`

```python
from eidoblend.characters.springs import bake_springs
rep = bake_springs(me, 1, 360)                    # every chain keyed on the NLA track '<name>|springs'
rep = bake_springs(me, 1, 360, resets=[121])      # springBoneManager.reset() where the body is teleported (seatOn)
```

The engine steps three-vrm's spring bones inside `vrm.update(dt)`, once per
rendered frame, after the body takes its pose. `bake_springs` does that once at
build time: a `preroll` (seconds on frame f0's pose, so the chains start
settled; 0 is the engine's cold start), then each frame: the body's pose, any
`resets`, the wardrobe's folds (`overrides`, from `me.spring_overrides`), one
step of 1/fps, keyed LINEAR (`rate=60` steps the add-on's own schedule
instead). Two solvers on the VRM's own `VRMC_springBone` data: `solver='three'`
(default), a port of three-vrm 3.5.2's joints and manager, matching the engine
within 0.001 mm on aletheia's 40 springs and the claudesona's 14 through a turn
and a nod (aletheia's four cat tails, whose nodes carry a 0.5 % non-uniform
scale a Blender rest pose cannot hold, within 10 mm); `solver='addon'`, the VRM
add-on's own step. `length='engine'` keeps three-vrm's one quirk (a joint's
length measured to its child's previous-frame pose); `'true'` is the bone's
real length. `tie_limit_deg` is the engine's tie limiter as it was meant to
work (render_scene.mjs's wrapper is inert in three-vrm 3.5.2, so the films show
the free tie, and the default matches them). Lower level: `SpringRig(me)` with
`read_pose`, `set_init_state` / `reset`, `update(dt)`, `override(bone, basis,
scale, colliders)`, `basis()`, `tails()`; `spring_bones`, `reset_springs`,
`spring_track`, `remove_springs`.

## Eyes on a target — `characters/lookat.py`

```python
from eidoblend.characters.lookat import LookAt, bake_look_at
rep = bake_look_at(me, target_obj, 1, 240)                   # an object, a world point, or f(frame) -> point
LookAt(me).key_yaw_pitch([(1, 0, 0), (12, 20, 0), (24, 0, 0)])   # vrm.lookAt.yaw / pitch by hand
```

three-vrm 3.5.2's `VRMLookAt` and its appliers: the direction from the head
(`offsetFromHeadBone`) relative to the head as it is now, as yaw / pitch
against the face's front, then the bone applier (each eye turned through the
VRM's range maps, inner and outer per eye) or the expression applier
(`lookUp` / `lookDown` / `lookLeft` / `lookRight`). The range maps, type and
offset come from the file (VRM 1.0 `lookAt`, VRM 0.x `firstPerson`). `lag=1`
(default) keeps the engine's timing (the head as the last matrix refresh left
it). Keys go on the NLA track `<name>|lookat`. Measured: yaw / pitch within
0.0001° of three-vrm's, the eye bones' world rotations within 0.0001°, on
both VRMs. **The claudesona's eye bones move nothing**: its eyes are painted on
the face plate, so its gaze is the face track's `down` / `up` channels.

## MToon or PBR — `claudesona/look.py`

```python
from eidoblend.characters.claudesona.look import set_look
set_look(me, 'pbr')       # every MToon material also renders through a Principled BSDF (EEVEE's output)
set_look(me, 'mtoon')     # back to the add-on's MToon, outlines on
```

The add-on's MToon import stays the default. The PBR look adds an EEVEE
output fed by a Principled BSDF (base colour = MToon's lit colour × its
texture, the wardrobe's paints included; metallic, roughness and IOR from the
VRM's glTF material; its normal map, or the TuTa's bump where the TuTa puts
one; MToon's emission at MToon's strength, with the driver on it, so the
badges' snaps, flicker and neon animate; alpha where MToon blends) and
switches the outline modifiers off. It can be set before or after
`make_wardrobe`: every paint, the TuTa's surfaces, face paint, catchlights,
sun disc and badge glow re-feed the PBR path when they are built
(`tests/claudesona/test_pbr_tuta.py` checks both orders). Which one a film
uses is an artistic call; both are kept.

## Turntable sheets — `blender/tools/vrm_turntable.py`

```bash
cd <main checkout> && bash run_blender.sh <worktree>/blender/tools/vrm_turntable.py -- \
    --outfits lab_coat_1961,mourning,cyclist_1892:nofold --frames head,body --views 0,35,90,150,180 \
    --out work/turntable/sheet.png
bash run_blender.sh <worktree>/blender/tools/vrm_turntable.py -- --vrm eidoverse/assets/vrms/aletheia.vrm \
    --outfits - --anim idle,cheer --frames chest --look pbr --out work/turntable/aletheia.png
bash run_blender.sh <worktree>/blender/tools/vrm_turntable.py -- --outfits tuta --frames body --views 0 \
    --hold 48 --spin --video work/turntable/tuta_spin.mp4
```

The repo-root tool and its scene, one keyed scene: a block of `--hold` frames
per (outfit, clip, framing, yaw), each with its outfit worn, its clip, its yaw
and camera keyed and the springs reset at its first frame, then the springs
baked over the run. A sheet tiles each block's last frame (the springs settle
over the block): one row per (outfit, clip, framing), one column per yaw, or
`--tile CxR`. `--spin` renders a reel instead (one eased turn per block).
Options as the original: `--vrm --scale --outfits ('-' for any VRM) --views
--frames (face, head, chest, body: authored on a 1.305 m head, scaled to the
character's) --hold --size --anim --light --presets --faces --tile --out
--video`; and `--samples`, `--look mtoon|pbr`, `--save scene.blend`. The
studio is the engine's: key, cool fill, rim, a sky/ground hemisphere (three's
irradiance I is a Blender world of radiance I / π), the grey floor disc.

## The minimal VRM scene — `blender/tests/claudesona/basic_vrm/`

`eidoverse/examples/basic_vrm.js`, the starting template for a scene without
the terrain harness, as a runner scene: a VRM plays its idle clip on a dark
reflective floor under a hemisphere and a sun, in a thin depth fog, while the
camera orbits it (keyed in `render_frame`); its springs are baked in `setup`.
`scene_claude.json` loads the example's own character (`claude.vrm`, as
`basic_vrm.json` does); the others load aletheia and the claudesona.

```bash
python eido_blender.py render blender/tests/claudesona/basic_vrm/scene_claude.json --at 0 --at 3 --at 6
python eido_blender.py render blender/tests/claudesona/basic_vrm/scene.json --at 0 --at 3 --at 6
python eido_blender.py render blender/tests/claudesona/basic_vrm/scene_claudesona.json --at 2
```

The runner currently stops this scene (and any scene with an MToon VRM) at its keying
snapshot: `harness/keying.py` reads Geometry Nodes modifier inputs with `keys()`,
which Blender 5.2's modifiers no longer have, and the VRM add-on's outlines are
Geometry Nodes modifiers. Until that is fixed, `tests/claudesona/test_basic_vrm.py`
runs the same `setup` and `render_frame` with a ctx that keys as the runner's
does, and renders the stills.

## Blender facts these modules depend on (measured)

- **A custom property added from Python is not copied to the evaluated
  object until something tags it.** Keying it on an action the object already
  has does not: its keys then never apply on `frame_set`, and every driver
  reading it fails and is flagged invalid. `_paint.new_prop` tags the
  armature (`update_tag()`) when it makes a switch property.
- **A driver flagged invalid is never evaluated again.** Every driver here
  goes through `_paint.drive`, which removes a stale driver on the path and
  marks the new one valid; a test checks each switch driver's output, which
  is what the render reads, not only the property.
- **An interpolated constant is not that constant.** A per-vertex id of 3
  arrives in the shader as 2.9999998 on part of a triangle; a palette looked up
  with floor() speckles. perPetal writes the colours per vertex instead, as
  the WebGPU edition does.
- **A material's outline is `mtoon1.outline_material`.** Looking it up by the
  name `MToon Outline (<name>)` finds another character's in a file with two.
- **An action that `keyframe_insert` creates on an object which already has
  animation data is not evaluated by the session's depsgraph until the object
  is tagged.** The armature carries its clips as NLA strips, so the first
  keyed switch after `play_vrma_default` (a TuTa bake, a paint, a turn) made
  an action that `frame_set` never played: Python read the last value it had
  set on every frame. Renders build their own depsgraph and were right; any
  bake that reads the evaluated scene (the springs, the gaze, the TuTa's neon)
  was not. Every keyed setter and bake here tags the armature
  (`_paint.tag_keyed`); `tests/claudesona/test_pbr_tuta.py` plays the clip
  first on purpose.

## Tests — `blender/tests/claudesona/`

Each writes its PASS / FAIL lines, a JSON beside its probes in `out/`, and
renders through the GPU slot:

```bash
cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/claudesona/test_face.py
#   test_lipsync.py   (python blender/tests/claudesona/sung_line_host.py first: the sung line, system Python)
#   test_springs.py   test_lookat.py   test_wardrobe.py   test_tuta.py   [--no-render]
#   test_turntable.py   test_basic_vrm.py
#   test_pbr_tuta.py  (the PBR look on the TuTa: glow drivers, bump, face paint, both orders)   [--no-render]
#   test_keyed_film.py  (three outfits, the TuTa's badges and an ejection, springs: saved, reopened, re-rendered)
bash run_blender.sh <worktree>/blender/tests/claudesona/test_face_geometry.py     # no render: the face vs the JS's
```

The references are the WebGPU modules themselves, run in deno on the CPU with
the engine's three-vrm (`three_vrm_parity.mjs`, `face_parity.mjs`,
`face_geometry_parity.mjs`, `tuta_parity.mjs`).

## Not yet ported

- **The TuTa's screen-space anti-aliasing.** The TSL widens a band thinner
  than a pixel and dims it (fwidth); shader nodes have no screen derivatives,
  so edges are drawn at a fixed 0.2 mm and EEVEE's samples average them, and
  the TSL bump from screen derivatives is Blender's Bump node on the same
  height. Thin stitches shimmer more in motion at low sample counts.
- **The TuTa's random draws.** Its fleck, slub, grime and fuzz noise uses
  Blender's White Noise of the same integer cells: the same statistics, not the
  same fleck positions.
- **`boater_band`**, listed in the JS's optional layers, has no object in
  `claude_suit_wardrobe.vrm` (in either edition).
- **Aletheia's four cat-tail chains** follow three-vrm within about 10 mm at
  their tips, not 0.001 mm as every other chain: their nodes carry a 0.5 %
  non-uniform scale that a Blender rest pose cannot hold.
