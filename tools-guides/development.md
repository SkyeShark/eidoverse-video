# Maintaining the toolkit and its documentation

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Start with [AGENTS.md](../AGENTS.md) and the guide for the system being changed.
The [tool inventory](../docs/TOOLS.md) maps the `eidoblend` modules, the CLIs and
the WebGPU sources to those guides. Source determines the actual API; comments
and old scenes can be stale.

## Preserve the workspace

Inspect `git status` and the relevant diffs before editing. Keep unrelated
collaborators' changes intact. Put experiments and archives in ignored
`work/<id>/`; apply shared-library changes within the agreed scope. Replacing a
tool means updating its callers, examples and docs together. Preserve the old
implementation in Git history and a local archive when requested; do not
rewrite history to remove it. A built `.blend` your collaborator edited by hand
is their work too: the runner refuses to rebuild over it without `--force`.

## How tools become available

- `eido_blender.py` (stdlib only) checks `scene.json`, writes the run's job
  file beside the output, and runs `bash run_blender.sh
  blender/eidoblend/harness/run_scene.py <job.json>`. `run_scene.py` puts
  `<repo>/blender` on `sys.path` and hands the job to `harness/runner.py`,
  which builds the scene (or reuses its build) and renders it. The
  [scene format](scene-format.md) describes what a run does.
- **There is no helper injection.** The WebGPU runner evaluated an ordered
  `HELPER_MODULES` list into globals; here a scene script imports what it
  uses (`from eidoblend.sky import make_sky`), at the top of the file. The
  runner also adds the script's own folder to `sys.path`.
- **One subpackage per family, self-contained:** `eidoblend.harness`,
  `characters`, `flora`, `fx`, `look`, `media`, `placement`, `sky`, `terrain`,
  `trees`. A family imports only itself, `eidoblend.common` and Blender's
  modules. `blender/eidoblend/__init__.py` imports nothing, so importing one
  family never loads another. Families meet in scene scripts.
- **Plain-Python halves stay plain.** Modules that plan rather than build
  (`harness/config.py`, `harness/ledger.py`, `common.py`, several families'
  planners) import no `bpy`, so the system Python can run them and test them.
- **Names mirror the WebGPU API in snake_case** (`makeSky` → `make_sky`,
  `loadPBR` → `load_pbr`), and a guide's Python examples are real calls.
- Coordinates are Blender's: Z-up, metres; `common.from_three` and friends
  convert positions, quaternions, ground points and matrices from three.js.

### `run_blender.sh` and Blender's own Python

`run_blender.sh <script.py> [args]` runs Blender 5.2 headless
(`--background --factory-startup`) with `BLENDER_USER_RESOURCES` pointing at an
isolated folder (default `$TMP/blender_user_isolated`, `BLENDER_SANDBOX` to
move it): run against your real user folder, `--factory-startup` would sync
your extension wheels to the empty set and delete the Python packages your
add-ons depend on. The extensions a script needs (`BLENDER_EXTS`, default
`vrm`) are copied into the sandbox from your installed Blender; a script
enables one with `bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')`.
Arguments after the script reach it after Blender's `--`
(`eidoblend.common.script_args()`). Two jobs running at once should use two
sandboxes (`BLENDER_SANDBOX`).

Blender 5.2's Python is 3.13 with **numpy**, **OpenImageIO** and
**requests**; there is no scipy and no cv2. This machine's Blender also
imports **Pillow 12.3.0** from its own `5.2/python/Lib/site-packages`, but its
`pillow-12.3.0.dist-info` is half an hour newer than numpy's, so it may have
been installed after Blender rather than shipped with it: shared code should
not rely on it. Read and write images with `bpy.data.images` or OpenImageIO;
dilate, filter and solve with numpy. Outside Blender, the system Python has
numpy, Pillow and cv2.

**Exit codes.** Blender exits 0 even when a `--python` script raises, unless
the script itself calls `sys.exit(code)` (a `sys.exit(3)` exits 3). The runner
does: 0 rendered, 1 failed, 3 refused, 2 bad arguments. A standalone test
script should catch its own failure and `sys.exit(1)`, and its caller should
still check that the files it expected exist. `run_scene.py` turns bytecode off
(`sys.dont_write_bytecode`), and `eido_blender.py` sets
`PYTHONDONTWRITEBYTECODE`, so no `__pycache__` lands in the package.

### Blender 5.2 facts the pipeline relies on

- `bpy.ops.wm.read_homefile(use_empty=True)` gives one empty scene: no
  objects, **no world**, EEVEE, AgX.
- Output: `image_settings.media_type` (`IMAGE`, `MULTI_LAYER_IMAGE`, `VIDEO`)
  is set before `file_format`. Video is `FFMPEG` with `ffmpeg.format`/`codec`.
  With `use_file_extension` off, Blender writes exactly `render.filepath`.
- A render's own multilayer EXR holds Combined only: extra passes leave
  through a compositor File Output node (`file_output_items.new(...)`). The
  compositor is a node group, `scene.compositing_node_group`; a Glare node's
  type and settings are input sockets (`'Type'`, `'Threshold'`, ...).
- Actions are layered, with slots: the glTF importer makes one action per clip
  with one slot per animated object, assigns the first clip and stashes every
  clip as a muted NLA track. An NLA strip needs its `action_slot`.
- The glTF importer also makes an `Icosphere` bone-display shape in a
  `glTF_not_exported` collection hidden for render; move only the objects it
  selects (`assets.import_model` does).
- EEVEE gives alpha-blended materials an **opaque shadow** unless
  `use_transparent_shadow`; screen-space refraction loses objects a few
  millimetres behind a pane (a clock dial). `assets.import_model` repairs both
  and logs it.
- Python-expression drivers do not evaluate when Blender opens a file with
  auto-run off, the factory setting `run_blender.sh` starts with, and the
  runner reopens a reused build that way (Blender's documented behaviour; not
  tested here). Key, or use simple expressions.
- `keyframe_insert` from Python ignores
  `preferences.edit.keyframe_new_interpolation_type`: every key is BEZIER with
  AUTO_CLAMPED handles. Set `keyframe_points[*].interpolation` afterwards; the
  runner does it for every key `ctx.key` made (`harness/keying.py`). An F-curve
  is found through `bpy_extras.anim_utils.action_get_channelbag_for_slot(
  action, slot)`; a key on a nested struct (a node socket, a pose bone) lives
  on its owner ID under `target.path_from_id(prop)`.
- Point caches (rigid body world, cloth, soft body) default to frames 1-250,
  whatever the scene's range; a particle system's cache range follows its
  emission and lifetime and is read-only. The build stretches the editable
  ones before baking.
- Python's audit hooks (`sys.addaudithook`) see every file the build's Python
  opens, including the glTF and VRM importers' reads; reads made in C (image
  loads, the OBJ / PLY / STL importers) are invisible to them.
- The `gpu` module is not initialised in background mode until `gpu.init()`
  is called; after it, `gpu.platform` names the device (OpenGL 4.6 on the
  studio's RTX 5090 Laptop) and **compute shaders run from Python**: a
  `GPUShaderCreateInfo` with `compute_source` and an `image(...,
  qualifiers={'WRITE'})`, `gpu.compute.dispatch`, the texture read back.
  The doctor's GPU check (`harness/gpu_check.py`) is gpu_check.mjs's own
  test, 64 invocations writing `id * 3 + 7`, beside a 64x64 EEVEE render.
- Blender makes action names unique across the file: a second glTF with
  the same clip names gets `Walk.001` (`assets.import_model` stamps each
  action's own clip name). `strips.new` picks an action's slot by the owner's
  name, so on a copy (`.001`) it finds none and sizes the strip to one frame:
  set the strip's `action_slot`, then its `action_frame_end` and start.
- A VRM's armature (the add-on's import) rotates by quaternion:
  `rotation_euler` does nothing on it; turn it through `rotation_mode`.
- `mathutils.bvhtree` is float32: a ray cast from 10 km above a floor lands
  a millimetre off; cast from just above what you measure.
- An object in a scene other than the context's (an overlay card) is not
  evaluated by `view_layer.update()`: its `dimensions` and `matrix_world` stay
  stale until that scene is evaluated. Size it from its mesh's `bound_box`.
- Blender 5's compositor has no MixRGB: mix with `ShaderNodeMix`
  (`data_type = 'RGBA'`, inputs 6 and 7 are A and B, output 2 the result).

## Documentation changes

`AGENTS.md` is the shared main instruction and the complete guide index.
`tools-guides/*.md` are ordinary tool and craft guides; there is no custom skill dispatcher.
Keep `CLAUDE.md` importing `AGENTS.md` so both entry paths reach the same rules.

When adding or porting a system:

1. Explain when to use it, how it loads (which `eidoblend` subpackage), and any
   dependencies it actually needs.
2. Include a source-checked Python example, its return values, controls,
   coordinate conventions (Z-up), what it keys or bakes at build time, and
   material limitations that affect use.
3. Rewrite its `tools-guides/<system>.md` for this edition in the same voice and
   structure, and end it with a **Not yet ported** list: what the WebGPU
   system had that is not here yet, so nothing is silently dropped. Update the
   index in `AGENTS.md` and the inventory in `docs/TOOLS.md`.
4. Remove obsolete active API instructions. Keep optional or historical
   utilities clearly identified; do not advertise absent files as supported
   imports.
5. Run the docs check, which needs no Blender:

   ```bash
   python blender/tests/pipeline/check_docs.py
   ```

   It fails on a broken relative link in AGENTS.md, `docs/`, `blender/README.md`
   or any guide; on an `eidoblend` module the inventory does not cover (by the
   file or by its family package); and on a guide missing from the AGENTS.md
   table. A file name in a table still does not replace usable API
   instructions.
6. Preserve the branch's relationship between collaborators. On this edition,
   as on `main`, the agent is a filmmaker working with a human collaborator;
   ideas may come from either. The auto editions' parent-agent workflow belongs
   on their branches ([blender/README.md](../blender/README.md) lists what a
   `blender-auto` branch must add). Technical requirements explain actual
   behavior; artistic recipes leave room for judgment and experimentation.

## Validation

For a docs-only change, run the docs check; no render is needed. For behavior
changes, run the affected family's tests in `blender/tests/<family>/` and
inspect their probe stills. The runner's own suite:

```bash
python blender/tests/pipeline/run_tests.py          # T0-T16 (most render)
python blender/tests/pipeline/run_tests.py T3       # one test
```

| Test | Checks |
| --- | --- |
| T0 | the config without Blender: `composedOutput` / `outputDir` fallbacks, `ceil(duration x fps)` frames |
| T7 | `doctor`: Blender 5.2, bash, ffmpeg, a 64x64 EEVEE render |
| T1 | the example's `--at` stills, the digest's status, no warnings, nothing unobserved (the placement family's audits ran) |
| T6 | the film: H.264 High, yuv420p, size and frame count by ffprobe; probe frames; `.mp4.prev` kept |
| T2 | `--at` stills against the film's own frames (PSNR above 35 dB) |
| T3 | planted defects, each named in the digest (an un-keyed light change among them) |
| T4 | build reuse; a hand-edited `.blend` rendered as edited, its placement audits re-run (the clock left in the air is named); rebuild refused, then forced |
| T5 | a model's clips on the model and its clone; the framed subject is the model |
| T8 | the placement family's audits run when a scene uses that family; a floating box is named |
| T9 | `bench`: seconds a frame and the film's estimate |
| T10 | `load_kit`: parts out of their catalogue row, standing on z = 0 |
| T11 | navigation: positive pitch looks down; a sensing walk through an unseen room arrives, its whole radius clear of the true obstacles |
| T12 | the `bloom` option: a halo round a hot emitter with it, none without |
| T13 | the config's `"preset": "probe"` applies the probe caps |
| T14 | a 300-frame rigid-body film: the cache stretched past Blender's default 250, baked 1-300, the crates knocked after frame 250 (read back from the saved `.blend`) |
| T15 | a plan file the script reads, undeclared: unchanged, the build is reused; edited, it rebuilds from the new plan |
| T16 | two shots: LINEAR and CONSTANT keys in the saved `.blend`, the lamp's keyed step at the cut, nothing changed without a key, shot B's framing measures what its camera sees |

`blender/tests/pipeline/query_blend.py` reads a saved build without rendering
(positions and light values at given frames, key interpolations): T14 and T16
use it to check what the film will show, not what the script meant.

The second suite covers the rest of the harness and the placement family,
measured against the engine's own JavaScript where there is any:

```bash
python blender/tests/pipeline2/run_tests.py          # U0-U5
python blender/tests/pipeline2/test_plain.py         # U0 alone: no Blender (Deno for the parity parts)
```

| Test | Checks |
| --- | --- |
| U0 | `audit_core_test.mjs` and `gpu_check_test.mjs` run under Deno, and their cases on the Python ports (`harness.ledger`, `harness.gpu_check`); `[KIT_INFO]` against `fetch_model.py`'s own preview script; `getCameraAtTime` and `alphaComposite` against `render_common.mjs`'s source; the `html_mesh` painter; the showpiece nudge |
| U1 | (Blender, no render) `audit_core`'s 14 cases as Blender scenes; the hovering fix (a clock left over a moved stool is named, a book on a wire rack the rays slip through is seated); kit islands and instances seated through their geometry; `play_model_animations` against three's `AnimationMixer` on the same GLB; clones with their own actions; the post hooks' order; `render_common` in Blender |
| U2 | the hovering before and after, a supplies kit stacked with a mounted `html_mesh` sign, interior windows on a brick facade from two angles (LOOK at `out/renders/`) |
| U3 | `model_preview.py` on five models and the lines it prints (LOOK at `out/previews/`) |
| U4 | the runner: the overlay layer between the colour hook and the screen hook, measured on a still |
| U5 | the runner: a build that never imports the placement family is audited by it, gets the showpiece nudge and records its post stack |

Tests render: keep them small (960x540 or less, 16 samples or fewer, a few
seconds of film) and run one render at a time on a shared GPU. A test's
`out/` folder is git-ignored. Library textures and models come from the
shared cache: `EIDO_ASSET_CACHE` points it at another checkout's
`eidoverse/assets/cache`, and `EIDO_NO_FETCH=1` makes a missing ID an error
instead of a download.

Report what was actually checked. A passing test is not a visual review (the
T5 crows once passed every check while a 2 m icosphere hid them); a catalog
or motion test does not establish visual quality or physical contact; an
asset inventory is not a license review.

## Internal support code

`harness/runner.py`, `context.py`, `keying.py`, `settings.py`, `post.py`,
`output.py`, `audits.py`, `ledger.py` and `showpiece.py` are the runner;
scene authors use `setup(ctx)`, `render_frame(ctx, t, i)`, `ctx`'s methods,
the post hooks and the families' APIs rather than starting a second render
loop. `harness/assets.py`, `render_common.py`, `html_mesh.py` and
`interior_window.py` are scene APIs ([assets](assets.md),
[scene format](scene-format.md)); `model_preview.py`, `gpu_check.py` and
`doctor.py` are scripts for `run_blender.sh`. The WebGPU engine's
`render_scene.mjs`, `render_common.mjs`, `audit_core.js` and `gpu_check.mjs`
are the reference the harness was ported from; `eido.py` still runs them
where Deno is installed, and its `bootstrap` materializes `node_modules` for
the [WebXR](webxr.md) pages.

## Not yet ported

- `bootstrap` has no Blender counterpart (nothing to materialize); the WebXR
  pages still use it.
- `comfy_bridge.py` is not ported because it needs nothing: it is a plain
  Python TCP proxy for the music and sound tools' ComfyUI and never touches a
  renderer, so every edition runs it as it is ([audio](audio.md)).
- The production engine's `shape_report.js` / `shape_verify.js` (a mesh
  "touch sensor": radial profiles, connectors and `snapConnectors`, pipe
  ports, symmetry, `verify.loadPath`) are a research thread on structured
  spatial sensing for robots, not film tools, and are deliberately left out
  of the toolkit. The film-side needs they touched are the placement family's: support and
  floaters (`check_hovering`), clipping, `mount_on` / `place_touching` for
  flush joints. `render_scene_deno.mjs` / `render_common_deno.mjs` there are
  older copies of the public runner, superseded by it (their only extra
  globals are other families' systems and `createInteriorWindowMaterial`,
  ported in `harness/interior_window.py`).
