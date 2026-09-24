# Reviewing and sharing a render

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Review the work against what you and your collaborator are making: a finished
film, an animation study, a simulation, a material experiment, or something else.
Use your artistic judgment. Silence, stillness, negative space, image collage
and dense worldbuilding are all possible choices; none is an automatic defect.
Technical checks help establish whether those choices survived the pipeline.

## Before a long render

Read the scene's setup and frame loop. Search can locate code to inspect, but a
match count does not establish correctness. From the repository root, for example:

```bash
rg -n 'AnimationMixer|clipAction|playVRMA|Controller|enableFootIK' work/<id>/scene.js
rg -n 'position|rotation|renderFrame|renderAsync|computeAsync' work/<id>/scene.js
rg -n '^\s*import\s' work/<id>/scene.js
```

Check the parts relevant to the scene:

- Scene scripts are evaluated as scripts. Put dynamic `await import(...)`
  calls inside `setup()`; static top-level import declarations do not work.
- Give each moving rig one owner. Initial placement is valid; per-frame manual
  travel competing with a character controller causes sliding and inconsistent
  collision handling. See [characters](characters.md) for mixer, VRM and IK
  update ownership. Do not await a movement-completion promise during setup:
  it needs the frame loop to advance.
- A mixer needs an active clip to produce clip animation. Helpers may create
  and play clips internally, so counting `AnimationMixer` and `.play()` strings
  is not a useful equality check. Inspect the resulting pose and motion.
- Use the pinned WebGPU NodeMaterials and TSL for newly authored shaders.
  Preserve the loader's material conversion for imported assets. Bulk particle
  and instance simulation belongs on the GPU; a small joint or UI loop on the
  CPU is a different workload.
- Check scale, attachment seating and moving clearances. Placement helpers and
  assembly ports provide starting positions, not proof that every pose is clear.
- For a visibly speaking or singing VRM, drive that character's visemes and
  reset stale values each frame. A silent character listening to narration or
  non-diegetic music does not need lipsync.

Render a probe at the intended resolution before a long encode:

```bash
python eido.py render work/<id>/scene.json --probe
```

A probe checks one time sample. Use a short, separately named config/output to
inspect motion, simulation settling and transitions before rendering the full
piece. Keep useful probes and prior versions in the working project. The native
runner writes the configured `outputVideo`; it does not choose a deliverable by
the newest file timestamp.

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

View representative frames at useful resolution, including close views of
important surfaces and text. Inspect the moving video and listen when your
available tools support them. Otherwise sample transitions and multiple poses,
inspect audio with the tools available, and state the limits of that review.
Look for unintended clipping, floating attachments, exposure loss, broken
normals, texture seams, mirrored lettering, frozen rigs and timing errors.
For reusable assets, include different coating colors and both mirrored sides.

Read the render's logs alongside the images:

- **Placement:** the audits only warn unless the scene opted into the
  `_autoFixPlacement` repair pass ([placement](placement.md)), which can move props. Inspect the final
  arrangement and the entire moving range. An unsupported object warning can
  indicate a misplaced solid or an intentional flyer; declare intent accurately.
- **Lipsync:** a mouth-never-moved warning matters when that character has an
  audible line. It is expected for a silent character.
- **Locomotion:** a travel-without-controller warning can reveal foot sliding.
  Use the controller for grounded VRM travel. `_allowManualLocomotion` supports
  intentional carried motion or teleportation; it does not repair a bad walk.
- **Camera:** the motion audit detects some rapid position/FOV reversals. It
  does not establish geometric clearance. Review camera paths and cuts with
  [CameraSafety](camera-lighting.md), including interpolated positions.
- **Unused assets:** a nearby GLB may be a study or reusable source. Check
  whether something intended for this scene was omitted; preserve useful work
  and shared caches. A warning is not an instruction to delete those files.

Correct observed defects at their source, then render enough of the affected
sequence to verify the change and its transitions. A local fix may require a
longer render when it changes simulation history or synchronization.

## Craft review

Consider composition, pacing, material response, sound and what the viewer can
read. A realistic setting benefits from coherent scale, motivated lighting and
spatial relationships; an abstract study may deliberately strip these away.
Judge density and motion by the piece's intention, without object quotas or a
required number of fetched assets. Reuse suitable assets and make new work when
that serves the idea.

Use [motion graphics](motion-graphics.md) for titles, subtitles and screens in
the native render, and [audio](audio.md) for the soundtrack. If text is mirrored,
trace its source image, UV orientation, material mapping and plane orientation
before changing pixels; there is more than one possible cause.

## Troubleshooting

- Renderer startup: `python eido.py doctor` checks the local stack. Consult
  [setup](../docs/SETUP.md) for missing dependencies and device selection.
- Dark or blown-out surfaces: inspect environment setup, exposure, lights and
  material conversion. Preserve meaningful authored metalness values; see
  [lighting](camera-lighting.md).
- Overlays obscured by clouds or glass: use `makeOverlayLayer`, which has a
  separate overlay scene, rather than parenting HUD geometry to the world camera.
- Black VRM or T-pose: use the patched global `GLTFLoader`, then check animation
  ownership and active actions in [characters](characters.md).
- Voice drowned by music: listen to source levels and adjust gains; explicit
  `amix` weights and `normalize=0` provide control but do not guarantee balance.
- Generator connection failure: inspect the actual backend error and its
  configured endpoint. A synthesized or externally supplied replacement can be
  useful; describe how it was made accurately.
- Setup never finishes: check unresolved promises, missing assets and async
  initialization. Movement promises must be allowed to run alongside frames.

## Structured audit records

The renderer writes JSON and text audit reports alongside its outputs.
`audit_core.js` provides `createLedger`, `buildInventory`, `mapDeclarations`,
`coverageRecords`, `snapshotPolicy` and `digestFromLedger` for maintaining that
pipeline. `GLOBAL_FLAGS`, `OBJECT_FLAGS` and `SENSOR_ALIASES` describe its schema.
These are explicit ESM utilities, not additional scene globals.

Read failed, skipped and unknown coverage separately. Declarations explain
intent; they do not prove clearance. Broad assembly labels can leave gaps in
coverage. Investigate the underlying geometry rather than adding exemptions
to conceal collisions or unsupported attachments.

## Contact sheets

A contact sheet lets a collaborator, or a model without video input, read a
whole piece from one image. From the repository root:

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

`--names` gives the section keys readable labels. `--parts N` also writes the
same frames split into N sheets, for tools with per-image size limits. The
output is `<video>_contact_sheet.jpg` unless `--out` names it. A sheet maps
the piece. It cannot show timing, flicker, lipsync or motion, so review those
in the video itself.

## Sharing the work

Link the result clearly, explain the creative choices worth discussing, and
say what you observed in review. Distinguish a study from a finished piece and
describe any remaining issues directly. There is no fixed response script.
Useful techniques can go into `techniques_archive.md`; propose toolkit
improvements when an experiment exposes a missing capability.

For tool changes, include relevant checks and observed renders. For
documentation-only work, report navigation and source checks without claiming
a fresh render or visual validation.
