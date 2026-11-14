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
    characters/ course/ fabrication/ flora/ fx/ look/ materials/ media/ placement/
    props/ sdf/ sets/ sky/ terrain/ trees/ weather/ xr/     one subpackage per family (18 with harness/)
  tests/<family>/               each family's headless tests; renders land in out/ (git-ignored)
  tests/run_all.py              every family's tests in one run, PASS / FAIL per test
eidoverse/                      the WebGPU engine (the port's reference) and the shared assets
tools-guides/                   one guide per system, describing this edition, each with a Not yet ported list
docs/TOOLS.md                   every eidoblend module and CLI, mapped to its guide
```

The rules every family keeps:

- **Families build on each other.** Sets use characters, flora, terrain and
  media; weather uses fx, media and sky; course uses characters and terrain.
  The node-graph and curve helpers are shared too: `terrain._nodes`,
  `terrain._pbr`, `fx._nodes` and `placement._curves` are imported by other
  families, so a change there is checked with
  `python blender/tests/run_all.py --kinds imports`. A scene script imports
  whichever families it uses.
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
python blender/tests/run_all.py                      # every family's tests, each in its no-render mode where it
                                                     # has one (--list, --areas, --kinds, --only, --failed)
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

Tests find everything relative to the checkout (`tests/_where.py`), so they run
from a fresh clone. A few environment variables adapt them to a machine:

| variable | what it does |
|---|---|
| `EIDO_GPU_WRAP` | a command prefix for every headless Blender job (a GPU queue on a shared machine, `nice`, a job runner); unset, Blender runs directly |
| `EIDO_MEMCAP` | a RAM-cap launcher `run_all.py` runs its no-render jobs through (`python -I $EIDO_MEMCAP <GB> -- <command>`) |
| `EIDO_MAIN_CHECKOUT` | the checkout holding the untracked `node_modules/` and `eidoverse/assets/cache/` (default: the main worktree when this checkout is a git worktree, else this checkout) |
| `EIDO_ASSET_CACHE` | another folder's fetched texture and model library, read before fetching again |
| `EIDOBLEND_PH_ASSETS` | the folder of the scanned Poly Haven plant sets (default: `scanned_plants/` in the asset cache) |
| `TRIAGE_CACHE` | the terrain triage cache of real DEMs and Ekigar fields (default: under `tests/terrain/out/`) |

Inputs that live outside this repo (another engine's reference renders, another
project's assets) have their own variables, named where each test reads them;
without one, the checks that need it are skipped, saying which variable to set.

Blender's own Python runs the package: 3.13 with numpy, OpenImageIO and
requests; no scipy, no cv2 (Pillow is present on this machine's Blender but
may have been installed after it: don't rely on it). Outside Blender use the
system Python (`eido_blender.py`, `config.py`, `ledger.py` and `common.py`
import no bpy).

## The `auto-blender` edition (agents + Docker)

The `auto-blender` branch is this edition plus a container for a parent agent.
Its `eido_docker.py` and `docker/` run `doctor`, `build`, `render` and `bench`
inside the render image unless `--local` is given, and add `bootstrap`,
`shell`, `agent` and `cleanup`. Its `docs/AGENT_LOOP.md` is the agent loop:
brief and context in, `_capabilities.json` (with `renderer: blender-eevee`),
the engine bound read-only, artifacts (`.mp4`, stills, the audit, `scene.py`
and the built `.blend`) collected into `runs/<ts>/`.

The image is Ubuntu 26.04 with Blender 5.2.0 from Blender's mirrors
(checksummed), the VRM extension, ffmpeg, Deno and Node, and Mesa for the GPU.
On WSL 2 (Docker Desktop with `--gpus all`, `/dev/dxg` and `/usr/lib/wsl`
mounted, `GALLIUM_DRIVER=d3d12`) EEVEE renders on the NVIDIA GPU through Mesa's
d3d12 driver; `docker/blender_gpu_check.py` (run by `doctor`) prints the
renderer and fails if Blender fell back to a software renderer.
