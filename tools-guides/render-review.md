# Reviewing and sharing a render

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Review the work against what you and your collaborator are making: a finished
film, an animation study, a simulation, a material experiment, or something else.
Use your artistic judgment. Silence, stillness, negative space, image collage
and dense worldbuilding are all possible choices; none is an automatic defect.
Technical checks help establish whether those choices survived the pipeline.

In the Blender edition the review tools are in `blender/eidoblend/look/`:
`probe.py` and `probe_cli.py` (stills at chosen times), `frame_stats.py`
(highlights, black and frozen frames, contact sheets), `camera_audit.py`,
`camera_safety.py`, `overlap.py` and `audit.py` (the ledger).

## Before a long render

Read the build script and the scene. Then check what Blender will actually
render:

```python
from eidoblend.look import render_settings as RS
print(RS.summary(scene))      # engine, size, samples, ray tracing, fast GI, volumes, motion blur, AgX/look/exposure,
                              # compositing, sequencer: the look actually set
```

Check the parts relevant to the scene:

- **Give each moving rig one owner: its keys, its drivers, or its handler,
  never two.** A camera keyed per frame by `look.camera` and also given a Track
  To constraint, or an armature with an action and a frame-change handler
  moving its root, fights itself. The pose then depends on evaluation order.
  See [characters](characters.md) for armature and action ownership.
- A VRM needs the VRM add-on in every script that imports it
  (`bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')`).
  Import with `set_view_transform_to_standard_on_import=False`: by default the
  import switches the scene to Standard, and AgX is gone.
- `scene.render.use_sequencer` with strips in the VSE renders the strips
  instead of the 3D view. The look family's `apply_auto_enhance` turns it off
  unless asked to keep it; the runner leaves it as the script set it and its
  `preflight.sequencer` record warns when picture strips would replace the
  film.
- Check scale, attachment seating and moving clearances. Placement helpers and
  ports provide starting positions, not proof that every pose is clear
  (`look.overlap` below).

Render probe stills at the intended look before a long render.
`python eido_blender.py render work/<id>/scene.json --at 12.5 --at 48` does it
for a runner scene; for any saved `.blend`:

```bash
bash run_blender.sh blender/eidoblend/look/probe_cli.py --blend work/<id>/film.blend --at 12.5 --at 48 --at 88.25 --sheet
```

Each time becomes `<out>/<name>_probe_at<seconds>s.png`, the seconds being the
still's own frame time to two decimals, as JavaScript's `toFixed(2)` writes it.
That is how `render_scene.mjs` and the pipeline family's harness name their
captures: `--at 2.5` at 24 fps is frame 61, `meadow_probe_at2.50s.png`. A
`<name>_probes.json` sits beside them. The stills are written through `.part`
files and checked to exist. Each one's highlights are measured: the share of
pixels with a channel at 250 or above, and the worst grid cell
([exposure](camera-lighting.md#exposure-measured)). The blend is never saved.

- `--preset probe` (default: 960 × 540, 16 samples) / `film` / `preview` /
  `keep`. `--samples`, `--res 960x540`, `--exposure +0.5` adjust it.
- **Jump is the default, and right for anything keyed or driven**: keys and
  drivers are pure functions of the frame. `--preroll 1` evaluates one second
  of frames before each still (no rendering), for state with a short memory:
  unbaked simulations, spring bones, frame-change handlers that keep state.
  `--replay` evaluates every frame from the start.
- **A post effect that reads earlier frames needs them rendered.**
  after_image's trail, the era looks' CRT persistence and aeropittura's echoes
  read records the compositor writes as each frame composites
  ([post-processing](postprocessing.md)). `eido_blender.py render --at`
  renders the frames a still reads first, in order, keeping only the records:
  a trail fed by its own last frame from its shot's first frame (its cut), the
  CRT persistence its last seven frames and aeropittura's echoes their last
  four (at 24 fps).
  The digest's `render.capture` says how many. `probe_cli.py`'s `--preroll`
  and `--replay` evaluate frames without rendering them, so their stills of
  such a shot read missing or stale records: take those stills with
  `eido_blender.py render --at`.
- `--compare T` renders frame T alone, then again after its previous frame,
  and reports the difference. EEVEE keeps no history between final renders,
  so they match to within a level of noise.
- `--false-color` also saves each still through AgX's False Color view.
- The exit code is the script's own: 0 with every still written, 1 when a
  still is missing or the script fails, 2 for bad arguments. Blender itself
  exits 0 even when a script raises; this CLI exits itself.

In a script: `probe.render_stills(scene, at=[1.5, 4.0], out_dir=..., mode='jump'|'preroll'|'replay')`.
A scene is safe to jump only if:

- **Anything measured once is measured as the full render measures it.** A
  value computed lazily "on the first frame" depends on where rendering starts.
  Measure it when building, or key it.
- **Solvers keep no memory between frames.** A handler that warm-starts from
  the previous frame's answer makes the pose depend on the path that reached
  it. Bake it to keys, or use `--replay`.

Use a short, separately named output to inspect motion, simulation settling
and transitions before the full piece. Keep useful probes and prior versions in
the working project. Name outputs for the mode that made them, so a file's
name never claims a lighting or quality mode it didn't use.

## Inspect the actual output

Check dimensions, duration and streams with `ffprobe`. The following commands
run from the repository root; substitute the actual project and output names.

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration,nb_frames -of json work/<id>/film.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,duration -of json work/<id>/film.mp4
mkdir -p work/<id>/_check
ffmpeg -nostdin -loglevel error -i work/<id>/film.mp4 -vf "fps=1" work/<id>/_check/frame_%03d.png
```

An absent audio stream is a problem when the piece should have sound. If sound
is present, listen to the mix and check synchronization; a stream header alone
cannot establish audibility. A waveform can help locate unintended silence:

```bash
ffmpeg -nostdin -loglevel error -i work/<id>/film.mp4 -filter_complex "[0:a]showwavespic=s=1280x240[out]" -map "[out]" -frames:v 1 work/<id>/_check/wave.png
```

Measure the frames, outside Blender (system Python):

```bash
python blender/eidoblend/look/frame_stats.py work/<id>/_check --mask work/<id>/_check/clip   # every PNG: highlights; clip masks of failures
python blender/eidoblend/look/frame_stats.py work/<id>/film.mp4 --every 2                    # a video: black frames, frozen runs, luma jumps, worst clipping
```

A still fails when more than 0.1% of its pixels clip or a grid cell holds more
than 2%. `--mask` writes the failing stills darkened with the clipped pixels in
magenta, so you can see whether it is a glint or an overlit wall. On a video it
reports black frames, frozen runs (consecutive frames under 0.25 levels
apart), luma jumps (a pop or a flash) and the worst frame's clipping. The exit
code is 1 when anything fails.

View representative frames at useful resolution, including close views of
important surfaces and text. Inspect the moving video and listen when your
available tools support them. Otherwise sample transitions and multiple poses,
inspect audio with the tools available, and state the limits of that review.
Look for unintended clipping, floating attachments, exposure loss, broken
normals, texture seams, mirrored lettering, frozen rigs and timing errors.
For reusable assets, include different coating colors and both mirrored sides.

Read the audits alongside the images:

- **Camera** (`camera_audit`): bounce, framing and focus per shot. A speck
  or a bounce reads "RE-RENDER". The bounce audit does not establish clearance;
  `CameraSafety.check_camera` walks the keyed path for that
  ([cameras](camera-lighting.md#camerasafety)).
- **Overlap** (`overlap.probe_overlaps`): exact mesh-against-mesh crossings of
  the evaluated (posed) meshes, the depth of the deepest vertex inside the
  other, and resting contact (within 2 mm) reported as a touch rather than a
  cut. `push_clear` moves an object out along a direction until it rests. Depth
  is the distance to the nearest way out: a box sunk 3 cm into a 4 cm slab
  reads as 1 cm, its distance to the slab's underside.
- **The camera audits' records** (`look.camera_audit`, run from a script):
  `camera.motion` (a bounce: more than 5 direction reversals a second with a
  real swing), `framing` (a subject that ends up a speck), `camera.focus`
  (a subject outside the depth of field) and `camera.focus_sharp` (a picture
  with nothing sharp in it).

### Every record the runner writes

The runner's digest (`<out>.audit.txt` / `.audit.json`, written on every exit
path) is built from one ledger. Each record has a check name, an outcome
(PASS, WARN or SKIPPED) and a class (CORRECTNESS, REVIEW or INFO). These are
all the names it writes:

| Check | What it records |
| --- | --- |
| `config` | the scene config as checked, its warnings |
| `lifecycle` | WARN: a run refused (a hand-edited `.blend`) or one that ended abnormally, with the exception |
| `build` | the build: reused (inputs unchanged; its audits follow), rebuilt (and why), or a `.blend` rendered as edited by hand |
| `build.settings` | the render preset and the `render` block applied to the scene |
| `build.render_frame` | `render_frame` ran on every frame and keyed what it changed |
| `build.unkeyed` | WARN: a value `render_frame` changed without a key, which the film would show frozen at its last value; the message names the `ctx.key(...)` call that fixes it (Geometry Nodes inputs included) |
| `build.inputs` | the undeclared files and folders the build read, which are build inputs from then on |
| `build.files` | images the build painted into the temp folder, kept beside the `.blend` |
| `build.bake` | each cache baked over the film's frames (point caches, rigid bodies, simulation zones); WARN for a bake that failed |
| `preflight.settings` | notes on the scene's settings |
| `preflight.camera` | the camera, and the marker-bound cuts; WARN when there is none |
| `preflight.sequencer` | WARN: picture strips in the film scene's sequencer would render instead of the 3D view |
| `preflight.frames` | WARN: `setup()` changed the frame range (the config wins) |
| `preflight.images`, `preflight.libraries` | missing images and libraries |
| `preflight.colour` | the view transform and look (AgX expected) |
| `preflight.vrm_import` | WARN: the VRM importer's leftovers in the scene |
| `preflight.world`, `preflight.light` | the world; the lights, emissive materials and world light (WARN when nothing lights the scene) |
| `preflight.caches` | PASS when every cache is baked to the film's last frame; WARN for one baked short, or unbaked |
| `coverage.policy` | the scene-wide flags and what they switch off |
| `coverage.inventory`, `coverage.identity` | the bodies and leaves the audits see, and registrations that span disconnected islands |
| `coverage.<flag>` | each object declaration (`allow_intersect`, `no_clipping_check` ...): what it covers, WARN for a blanket over many bodies |
| `coverage.sensor.<sensor>` | per sensor (clipping, support, motion, facing, zfight, intrusion), the share of bodies declared away; WARN when it is systemic |
| `coverage.assembly` | an assembly tag and the pair checks it hides |
| `coverage.toctou` | WARN: audit flags changed after `setup` (by `render_frame`) |
| `clipping`, `support`, `zfight`, `facing`, `density`, `intrusion`, `motion.envelope`, `motion.locomotion`, `motion.locomotion.disposition`, `opacity` | SKIPPED when a scene-wide flag switches that check off: unobserved, not passed (`opacity` has no Blender counterpart and says so) |
| `placement` | SKIPPED when the placement audits could not run |
| `placement.clipping` | contact pairs are data; WARN only for an object substantially inside another |
| `placement.hovering` | a seating gap of 5 cm or more, in the air |
| `placement.floaters` | nothing beneath, or more than 1 m up |
| `placement.z_fighting` | WARN for two thin sheets sharing a face |
| `placement.facing` | display panels interpenetrating something or buried on both sides |
| `placement.line_intrusion` | objects planted in a transport line (a road, a rail) |
| `placement.seated_facing` | a seated character turned off its chair's natural facing (REVIEW); RE-RENDER REQUIRED when it faces the backrest (more than 110°): pass `face=` to `seat_on` |
| `placement.density` | the number of distinct top-level objects placed (an observation, never a demand) |
| `repair` | the opt-in placement repair ran before the audits (`_auto_fix_placement`) |
| `motion.envelope` | a spin about the wrong pivot, sinking below the ground, a teleport, scale drift |
| `motion.swept_clearance` | a part that turns in place (a rotor, a wheel in its fork, a fan, a radar dish), checked against the static top-level objects beside it at every angle it turns through: a full revolution in 12 steps when it turns that far (or faster than a quarter turn between samples), else its own sweep every 30°. WARN when it sits inside a neighbour at every angle (seated INTO its mount: `placement.mount_on(part, mount, standoff=...)`), or sweeps through one at some angles. A part parented under its mount is not checked against it; a rig or a skinned body is left out; `obj['no_motion_check']` opts out |
| `motion.sideways` | a long body travelling sideways |
| `motion.camera` | a bouncing camera |
| `motion.rig_pose` | a humanoid that never leaves its pose: a statue |
| `motion.locomotion` | RE-RENDER REQUIRED: a humanoid that travels more than 1.5 m while its feet slide along with it, the planted foot moving more than 60 % of the body's travel (a walk the characters family keyed plants them, about 15 %); `_allow_manual_locomotion` for a body that is carried |
| `motion.lipsync` | REVIEW: a VRM whose mouth never moved, read on its viseme expressions and any mouth shape key; ignore it for a silent character |
| `motion.springs` | REVIEW: a VRM whose spring chains (hair, tails, a tie) nothing moves: no unmuted springs track (`<name>\|springs`, which `characters.springs.bake_springs` keys, and `Locomotion.bake` and the robot body's bake by default) and no keys on its spring bones, so they hang in their rest shape the whole film. Bake them with `characters.springs.bake_springs` over a hand-keyed body; INFO when they are baked or keyed; ignore it for a character meant to stand still |
| `framing` | per shot: WARN for a speck, or for a camera that sees no candidate at all |
| `palette`, `palette.showpiece` | what the scene used; a pointer (INFO only) |
| `assets.reads`, `assets.orphans` | declared assets the script never read; models beside the script that the config never declares |
| `render.auto_enhance` | the post stack and the hooks installed |
| `render.preset`, `render.settings` | the preset and the EEVEE settings the frames rendered with |
| `render.capture` | the stills written (`--at`), their frames, any preroll, and the lead-in frames rendered first for a post effect that reads earlier frames (which effects, and how far back each reads) |
| `render.video` | the film written: frames, seconds a frame, the file |
| `render.probe_frames` | SKIPPED when the film's probe frames could not be extracted (no ffmpeg): view frames yourself |
| `render.bench` | `bench`'s seconds a frame and the film's estimate |
| `scene.<name>` | a record of the scene script's own (`ctx.record(name, outcome, message)`) |
| `preflight`, `coverage`, `motion`, `framing`, `palette`, `assets` | SKIPPED when that check itself failed: its obligations are unobserved |

Correct observed defects at their source, then render enough of the affected
sequence to verify the change and its transitions.

## Craft review

Consider composition, pacing, material response, sound and what the viewer can
read. A realistic setting benefits from coherent scale, motivated lighting and
spatial relationships; an abstract study may deliberately strip these away.
Judge density and motion by the piece's intention, without object quotas or a
required number of fetched assets. Reuse suitable assets and make new work when
that serves the idea.

Use [motion graphics](motion-graphics.md) for titles, subtitles and screens,
and [audio](audio.md) for the soundtrack. If text is mirrored, trace its source
image, UV orientation, material mapping and plane orientation before changing
pixels; there is more than one possible cause.

## Troubleshooting

- **Blender exited 0 but nothing came out.** Blender returns 0 after a script
  raises. Read the log for the traceback, and check the outputs exist
  (`probe_cli.py` does both and exits with its own code).
- **"File written by newer Blender binary, expect loss of data!"** The
  `.blend` was saved by a newer build. It reads, but a file round-tripped
  through the older binary can lose data: don't save it there.
- **Pink surfaces:** a missing image texture. Relative paths broke when the
  blend moved, or a library was not found.
- **The VSE's output instead of the 3D render:** `use_sequencer` with strips
  (above).
- **Dark or blown-out surfaces:** check the world, exposure, lights and probes.
  Measure the exposure; preserve authored metalness
  ([lighting](camera-lighting.md)).
- **An interior lit as if outdoors:** the room does not hold its light. Give
  its walls, floor and ceiling real thickness and fit a volume probe that
  covers the room, its outer samples inside the walls, then bake it
  ([interiors](camera-lighting.md#interiors)).
- **A grainy dim interior at 16 samples:** sampling noise. Raise the samples
  for the film and judge the grain at the film's settings.
- **A pass EXR holding only one layer:** in 5.2 a File Output node writes only
  its first item. Use one node per pass ([stack notes](stack-notes.md)).
- **A library override that lost its edits after an update:** resync the
  override (Outliner > Library Overrides) and check the edited properties
  survived.

## Structured audit records

The runner's ledger is `audit_core.js` ported whole:
`eidoblend.harness.ledger` (plain Python: `create_ledger`, `snapshot_policy`,
`build_inventory`, `map_declarations`, `coverage_records`,
`digest_from_ledger`) with `eidoblend.harness.audits` reading a Blender
scene into it. `GLOBAL_FLAGS`, `OBJECT_FLAGS` and `SENSOR_ALIASES` describe
its schema. Records are plain dicts, so any family's check can emit them.

```python
from eidoblend.harness import audits, ledger as L
led = L.create_ledger()
inv = audits.build_inventory(scene)                # leaves: each object's own geometry AND each instance
decl = audits.map_declarations(scene, inv)         # object custom properties: allow_intersect, no_clipping_check, ...
for r in L.coverage_records(decl, inv, L.snapshot_policy({'_no_motion_check': True})):
    led.record(**r)
print(L.digest_from_ledger(led))                   # the digest, built from the records, review gate included
```

Blender mapping, as the runner reads it:

- A leaf is one object's own evaluated geometry (a Geometry Nodes object's
  own mesh, not the instances it makes), and each collection or Geometry
  Nodes instance is a leaf of its own. Hidden objects are leaves too, never
  physical, so hidden ballast cannot dilute a coverage fraction.
- A declaration is an object custom property in snake_case (`allow_intersect`,
  `no_clipping_check`, `no_support_check`, `_sunk_placement`,
  `no_motion_check`, `no_intrusion_check`, `no_z_fight_check`,
  `no_facing_check`; `assembly = '<tag>'`), inherited by children; the JS
  spellings are read too. A seated character (`eido_seated`) joins the
  support sensor.
- A policy flag (the WebGPU globals) is a module-level name in the scene
  script or a scene custom property (`_no_auto_placement_check`,
  `_no_motion_check`, ...). `_no_opacity_check` is recorded as having no
  effect: the engine's opacity check guarded a three.js binding Blender
  does not have.
- Provenance, which leaves may merge into one body, is the `eido_src_asset`
  custom property up the parent chain (`assets.import_model` sets it).

`eidoblend.look.audit` is the look family's earlier port of the same file,
for checks run outside the runner; its flag spellings differ in places
(`sunk_placement`, `src_asset`).

Read failed, skipped and unknown coverage separately. Declarations explain
intent; they do not prove clearance. A declaration covering many bodies is a
blanket exemption and WARNs. Investigate the underlying geometry rather than
adding exemptions to conceal collisions or unsupported attachments.

## Contact sheets

A contact sheet lets a collaborator, or a model without video input, read a
whole piece from one image. For a video, from the repository root:

```bash
python contact_sheet.py work/<id>/film.mp4 --every 5 --cols 6
python contact_sheet.py work/<id>/film.mp4 --timeline work/<id>/timeline.json \
  --names '{"verse1": "verse 1 · the machines"}' --title "Title" --synopsis "What the piece is." --parts 3
```

It takes one frame from the middle of every `--every` seconds, scaled to
`--tile` pixels wide in the video's own aspect. With `--timeline` it also
takes a frame just inside each section start. It then labels every tile with
its timestamp, its section and the line sung or spoken at that moment, so
the story reads without sound. The tool accepts two timeline shapes:
- `{ "sections": [{name, t0, t1}], "captions": [{text, t0, t1}] }`, as
  voicebox and song timelines write it (either key may be missing);
- `align_lyrics.py`'s list of `{text, start, end}`.

For probe stills, `frame_stats.py sheet` lays PNGs side by side with labels.
It runs inside Blender too, as `frame_stats.sheet(paths, out, labels=...)`:

```bash
python blender/eidoblend/look/frame_stats.py sheet a.png b.png c.png --out sheet.jpg --labels "pick -1,pick,pick +1" --tile 480
```

A sheet maps the piece. It cannot show timing, flicker, lipsync or motion, so
review those in the video itself.

## Sharing the work

Link the result clearly, explain the creative choices worth discussing, and
say what you observed in review. Distinguish a study from a finished piece and
describe any remaining issues directly. There is no fixed response script.
Useful techniques can go into `techniques_archive.md`; propose toolkit
improvements when an experiment exposes a missing capability.

For tool changes, include relevant checks and observed renders. For
documentation-only work, report navigation and source checks without claiming
a fresh render or visual validation.

## Not yet ported

- Frequency-resolved flicker: `frame_stats.py` on a video reports luma
  jumps and frozen runs, not a flicker spectrum.
- A per-collection render cost report: profile Python with `cProfile`;
  `eido_blender.py bench` gives the seconds a frame.
- `motion.locomotion`'s 60 % threshold is measured on one walk (a planted
  foot moving 15 % of the travel), one slide (100 %) and synthetic rigs: a
  run with flight phases, and a stride that does not match its speed, are
  unmeasured. `motion.lipsync` reads VRM 0.x visemes and mouth-named shape
  keys too, but only a VRM 1.0 face (claude.vrm) is exercised.
- `gpu_check.mjs`'s explicit software-fallback request does not apply:
  Blender chooses its GPU when it starts. The rest of the check (hardware or
  software, and a compute dispatch read back) runs in `eido_blender.py
  doctor` (`eidoblend.harness.gpu_check`).
