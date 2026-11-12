# Setup (Blender edition)

Everything runs on your machine: Blender 5.2 builds every scene and renders
it with EEVEE on your GPU, ffmpeg checks and muxes, and Python runs the runner
and the tool scripts. **The render stack is Blender 5.2, bash and ffmpeg.**
The rest below is for the systems that need it.

(The containerized edition, a Docker render image plus an autonomous
agent-loop runner, lives on the `auto-blender` branch; see its docs for the
sandboxed or subagent setup instead.)

## 0. Prerequisites

- **A GPU EEVEE runs on.** NVIDIA recommended. Blender chooses the GPU when
  it starts; use the vendor's current driver.
- **Python 3.10+** (`eido_blender.py` is stdlib only).
- A few GB of disk for Blender, the shared texture and model caches, and
  working space.

## 1. Blender 5.2

Install Blender 5.2 from [blender.org](https://www.blender.org/download/)
(the installer or the portable archive). The runner and `run_blender.sh` find
it the same way:

1. `BLENDER`, the path to the executable, when set;
2. `blender` on `PATH`;
3. the usual install folders, newest version first:
   `~/Blender/<version>/blender.exe` and
   `C:\Program Files\Blender Foundation\<version>\blender.exe` on Windows,
   `/Applications/Blender.app` on macOS, `/usr/bin/blender` or the snap on
   Linux.

`python eido_blender.py doctor` reports the version it found. The edition is
built and checked on 5.2, and the doctor fails on another version.

## 2. bash

Every Blender run goes through `run_blender.sh`, which starts Blender
headless (`--background --factory-startup`) in an isolated user folder, so a
run never touches your installed add-ons. On Windows install
[Git for Windows](https://git-scm.com/download/win); the runner finds its Git
Bash (or the bash named by `EIDO_BASH`) and never uses WSL's bash, which sees
Windows paths differently. Linux and macOS use their own bash.

## 3. ffmpeg and ffprobe

Both on `PATH`. Blender writes the film's H.264 itself; ffmpeg and ffprobe
make the probe frames, the checks and the delivery copies, and mux sound.

## 4. The VRM Add-on for Blender

For scenes with VRM characters. Install it once in normal Blender:
Edit > Preferences > Get Extensions, search for **VRM format** (extension id
`vrm`), Install. `run_blender.sh` copies your installed copy into its sandbox,
again whenever yours changes; `BLENDER_EXTS="vrm other"` copies more
extensions. Scripts enable it with
`bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')`.

## 5. SeedThree, for trees

`make_seed_tree` runs SeedThree's own Blender add-on. Check out SeedThree's
`blender` branch beside this repository:

```bash
git clone -b blender https://github.com/SkyeShark/SeedThree ../SeedThree-blender
```

The trees family looks in `SEEDTHREE_DIR`, then `../SeedThree-blender`,
`../SeedThree` and `./SeedThree` (the first that holds `blender/seedthree/`).

## 6. Deno and its npm cache

A few systems run the WebGPU engine's own JavaScript while a scene builds:
the canvas screens and the computing-history screen scenes, the books' rig
and the parole captions. The WebXR pages import three.js from
`node_modules`. Both need **Deno 2.8.1 or 2.9.5** and the npm cache that
bootstrap fills:

```powershell
# Windows
irm https://deno.land/install.ps1 | iex
deno upgrade 2.9.5
```
```bash
# Linux / macOS
curl -fsSL https://deno.land/install.sh | sh -s v2.9.5   # needs unzip or 7z
```

```bash
python eido.py bootstrap          # fills the npm cache and node_modules; add --fresh to rebuild from scratch
```

The build-time scripts run offline from that cache
(`--cached-only --node-modules-dir=none`) and write nothing into the
repository. Re-run bootstrap after any `deno.lock` change. Keep a separate
checkout and `node_modules/` for native Linux or WSL runs and Windows runs:
native binaries differ by OS.

## 7. Health check

```bash
python eido_blender.py doctor
```

Checks: Blender's version, bash, the VRM extension (optional), ffmpeg and
ffprobe, then one 64 × 64 EEVEE render of a lit cube at 1 sample and the GPU
check: the renderer Blender chose, classified hardware or software, and a
compute dispatch whose readback must be exact. Then the Deno of step 6, as
the canvas screens, the books' rig and parole run it: the binary on `PATH`,
its version (2.8.1 or 2.9.5), and one offline import (`--cached-only`, no
config, no `node_modules`) of the npm packages their scripts import, three
and `@napi-rs/canvas`; a miss says to run `python eido.py bootstrap`. Deno,
ComfyUI and an embeddings key are reported, not required. `--no-render`
skips the render. Failures return a nonzero exit code.

A **software renderer** (Mesa llvmpipe or lavapipe, Microsoft WARP) runs
everything on the CPU, many times slower, and the doctor warns. On a machine
that has a GPU, fix the driver setup before rendering.

## 8. Smoke test

```bash
python eido_blender.py render blender/tests/pipeline/example/scene.json --at 0 --at 1.5 --at 3
python eido_blender.py render blender/tests/pipeline/example/scene.json
```

The first builds the example (a stool, a clock, a push-in) into its `.blend`
and writes three PNG stills; the second renders the 3-second film to
`blender/tests/pipeline/out/example.mp4`. A Blender process's first frame
takes longer while EEVEE compiles its shaders. Look at the stills before you
judge the run. `python blender/tests/run_all.py --kinds imports` checks that
every module of the package imports and wires, in seconds.

## 9. Optional backends

- **ComfyUI (music + SFX)** — **MiniMax Music 3 is the recommended music
  model**; use Stable Audio for sound effects. Install the corresponding
  checkpoints and workflow dependencies listed in
  [audio](../tools-guides/audio.md). Set `COMFYUI_URL` to the actual backend
  address (default `http://127.0.0.1:8188`); native clients connect directly.
  `python generate_song.py --probe` checks the required MiniMax node
  classes and configured model names without generating audio. Follow it
  with a short generation to verify inference.
- **Optional TCP bridge** — `python eidoverse/comfy_bridge.py` can expose a
  host ComfyUI to a container client. It listens on `0.0.0.0:8188` by default
  and discovers the upstream in `SCAN_PORTS` (default `8000-8020`).
  `BRIDGE_PORT` and `COMFY_HOST` configure the exposed port and upstream host.
  It is a separate service, not a rendering prerequisite.
- **Semantic theme ranking** — set `JINA_AI_KEY` (free tier) or point
  `EIDOVERSE_EMBED_URL` / `EIDOVERSE_EMBED_MODEL` / `EIDOVERSE_EMBED_KEY`
  at any OpenAI-compatible `/v1/embeddings` endpoint. Without a key,
  `fetch_model.py` ranks by relevance only (still works).
- **Python tool tiers** — see `requirements-local.txt`: the fetchers need
  only `requests`; the TTS/lipsync chain is a few audio libs; voicebox and
  synthkit need numpy, scipy and numba; demucs pulls PyTorch. Install what
  you use, into the system Python (Blender's own Python runs the package and
  needs nothing installed).

## Platform notes

- **Windows**: the platform this edition is built and render-checked on
  (Blender 5.2, NVIDIA RTX, Git Bash).
- **Linux**: Blender's Linux build with the GPU vendor's driver. The
  `auto-blender` branch's container (Ubuntu) renders EEVEE this way.
- **WSL 2**: running the Windows Blender from the Windows side is the
  simplest route. A Linux Blender inside WSL reaches the host GPU through
  Mesa's d3d12 driver (`GALLIUM_DRIVER=d3d12`, with `/dev/dxg` present);
  the `auto-blender` container renders that way under `xvfb-run`. Run the
  doctor in the same shell you will render from.
- **macOS**: Blender on Metal. Same caveat: unverified here, judge by frames.
- **Fonts**: the 19 display fonts live at `eidoverse/assets/fonts/`; the
  media family reaches them by name.

## Troubleshooting

- **`run_blender.sh: Blender not found`** — set `BLENDER=/path/to/blender`,
  or put `blender` on `PATH`.
- **`no bash found`** — install Git for Windows, or set `EIDO_BASH` to its
  `bash.exe`.
- **`extension 'vrm' is not installed in your Blender`** — install the VRM
  add-on once (step 4); VRM scenes need it.
- **Blender exited 0 but nothing came out** — Blender returns 0 after a script
  raises. The runner checks every output and the digest's status, and says
  what is missing: read the log above it for the traceback.
- **`[trees] no SeedThree checkout with blender/seedthree found`** — step 5.
- **`deno not found on PATH`**, or a canvas screen, book or parole build that
  fails on a missing npm package — install Deno and run
  `python eido.py bootstrap` (step 6).
- **`fetch_pbr <id> (1k) is not in the library`** — fetch the set into the
  shared library: `python fetch_texture.py <id> 1k --cache`.
  `EIDO_NO_FETCH=1` makes every missing asset an error instead of a fetch.
- **The doctor warns of a software renderer on a machine with a GPU** — the
  driver or backend setup is wrong; on WSL, see the platform notes.
- **Black or pink frames** — check the world, the lights, the exposure and
  missing images ([render review](../tools-guides/render-review.md)); the
  audit digest's `preflight.*` records name missing images and libraries.
