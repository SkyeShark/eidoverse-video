# The Blender edition

The `blender` branch renders the Eidoverse in **Blender 5.2 with EEVEE**. A
scene is a `scene.json` and a Python script with `setup(ctx)`; the runner,
`eido_blender.py` at the repository root, builds it into a `.blend` (keyed,
baked, audited) and renders that with EEVEE straight to H.264, or to PNG stills.
Start with [AGENTS.md](../AGENTS.md) and the
[scene format](../tools-guides/scene-format.md); copy
[tests/pipeline/example/](tests/pipeline/example/scene.py) for a first scene.

```bash
python eido_blender.py doctor
python eido_blender.py render blender/tests/pipeline/example/scene.json --at 0 --at 1.5 --at 3
python eido_blender.py render blender/tests/pipeline/example/scene.json
```

## Layout

```
eido_blender.py                 the runner (stdlib only): doctor, build, render, bench, open
run_blender.sh                  headless Blender in an isolated user folder (every run goes through it)
blender/
  eidoblend/                    the package; <repo>/blender goes on sys.path
    __init__.py                 imports nothing
    common.py                   paths, three.js Y-up -> Blender Z-up, frame/time, small tools (no bpy)
    harness/                    the runner, the audits, the asset loaders (the pipeline family)
    characters/ flora/ fx/ look/ media/ placement/ sky/ terrain/ trees/    one subpackage per family
  tests/<family>/               each family's headless tests; renders land in out/ (git-ignored)
eidoverse/                      the WebGPU engine (the port's reference) and the shared assets
tools-guides/                   one guide per system, describing this edition, each with a Not yet ported list
```

The rules every family keeps:

- **Self-contained subpackages.** A family imports only its own subpackage,
  `eidoblend.common` and Blender's modules, never another family's. A scene
  script imports whichever families it uses; that is where they meet.
- **Names mirror the WebGPU API in snake_case** (`makeSky` → `make_sky`,
  `createFlora` → `create_flora`), so a guide translates one to one.
- **Z-up, metres, AgX.** three.js `(x, y, z)` is Blender `(x, -z, y)`
  (`common.from_three`); APIs that took a ground point `(x, z)` take `(x, y)`.
- **Motion is keyed or baked at build time.** Nothing runs per frame at render
  time, so a frame renders the same whether the render jumps to it or plays up
  to it, and the built `.blend` opens and scrubs in Blender's window.
- **Port, don't substitute.** A system that is not ported yet is listed in its
  guide's *Not yet ported* section; a stock stand-in is not a port.

## Tests

Each family's tests are headless Blender scripts in `tests/<family>/` that
build a small scene with the family's system and render probe stills into
`tests/<family>/out/`. The pipeline family's suite runs the runner end to end:

```bash
python blender/tests/pipeline/run_tests.py           # T0-T16: the config, stills, the H.264 film, --at against
                                                     # the film, planted defects, build reuse and hand edits, a
                                                     # model's clips, the placement bridge, bench, kits, navigation,
                                                     # bloom, presets, a 300-frame simulation, a plan file as an
                                                     # input, two shots with LINEAR / CONSTANT keys
python blender/tests/pipeline/check_docs.py          # links, the inventory, the guide index (no Blender)
```

Tests render: keep them small (960x540 or less, 16 samples or fewer, a few
seconds of film), run one at a time on a shared GPU, and LOOK at what they
write. A passing test is not a visual review.

Blender's own Python runs the package: 3.13 with numpy, OpenImageIO and
requests; no scipy, no cv2 (Pillow is present on this machine's Blender but
may have been installed after it: don't rely on it). Outside Blender use the
system Python (`eido_blender.py`, `config.py`, `ledger.py` and `common.py`
import no bpy).

## For the `blender-auto` edition (agents + Docker)

The `auto` branch runs the WebGPU edition in a container for a parent agent
(`eido.py agent`: brief and context in, `_capabilities.json`, the repo
mounted read-write with per-file read-only binds over the engine, Docker with
`--gpus all`, plus `/dev/dxg` on WSL 2, a timeout, artifacts collected into
`runs/<ts>/run.json`). A `blender-auto` branch built on this edition needs, in
its AGENTS.md and its tooling (not written here; that branch is not edited
from this one):

1. **The image.** Blender 5.2 LTS for Linux, pinned (the official tarball and
   its checksum), on PATH as `blender`; the VRM add-on installed into the
   image's Blender user folder (`~/.config/blender/5.2/extensions/blender_org/vrm/`),
   where `run_blender.sh` finds it and copies it into its sandbox; ffmpeg and
   ffprobe. Deno, Mesa and Node stay only if the WebXR pages are served.
2. **EEVEE needs a graphics context on the GPU,** not just compute: the NVIDIA
   container runtime with `NVIDIA_DRIVER_CAPABILITIES=all` (graphics, not only
   `compute,utility`) so Blender's headless EGL path finds the GPU. On WSL 2
   (`/dev/dxg`, Mesa's d3d12 driver) EEVEE is **unverified**: run
   `python eido_blender.py doctor` inside the container first; it renders a
   64x64 EEVEE frame and fails loudly if it cannot.
3. **The brief's working loop** in its AGENTS.md: the agent writes
   `work/<id>/scene.json` and `scene.py` (Python with `setup(ctx)`, not a
   `.js` scene), checks stills with `render --at`, renders the film with
   `render`, reads `<out>.audit.txt`, and looks at the probe PNGs before it
   reports. The exit code is honest (0 done, 1 failed, 3 refused) and
   `<out>.audit.json` carries `status: normal completion` only for a run that
   finished.
4. **Read-only binds** over this edition's engine: `eido_blender.py`,
   `run_blender.sh`, `blender/eidoblend/**`, `AGENTS.md`, `tools-guides/**`,
   plus the existing `eidoverse/**` sources and `eidoverse/assets` (one
   directory mount). `work/` stays writable; the texture/model library
   (`eidoverse/assets/cache/`) must be writable or pre-fetched, since
   `fetch_pbr` / `fetch_model_file` fetch on first use (`EIDO_NO_FETCH=1`
   makes a missing ID an error instead).
5. **`_capabilities.json`** gains `blender` (the version `doctor` found),
   `eevee_gpu` (the doctor render passed) and `vrm_extension`.
6. **Collection** adds `work/**/scene.py`, `*.audit.txt`, `*.audit.json`,
   `*.build.json` and the built `*.blend` (the parent can open the very scene
   that rendered), alongside the `.mp4` and `.png` files.
7. **Budgets:** the probe preset (960x540, 16 samples) for checks; the film
   preset's 32 samples for the film. `eido_blender.py bench` estimates a
   film's render time before the agent commits to it.
8. **Not ported from the WebGPU auto edition:** the palette report's showpiece
   nudge (it read `_brief.txt`).
