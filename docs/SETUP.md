# Setup

Everything runs directly on your machine: Deno renders through your GPU,
ffmpeg encodes, and the Python tools are optional extras. **The whole
render dependency list is Deno + ffmpeg.**

(A containerized edition — Docker render image + the autonomous
agent-loop runner — lives on the `auto` branch; see its docs if you want
the sandboxed/subagent setup instead.)

## 0. Prerequisites

- **GPU** — NVIDIA recommended. Windows renders through native D3D12
  WebGPU; Linux through Vulkan; macOS through Metal.
- **Python 3.10+** (the `eido.py` runner is stdlib-only).
- A few GB of disk for node_modules + working space.

## 1. Install Deno 2.8.1 or 2.9.5 + ffmpeg

Verified versions are **2.8.1** (Windows, native D3D12) and **2.9.5**
(Linux/WSL, Vulkan). An earlier note pinned 2.8.1 because a 2.9.x build had
shown banded gradients in the TSL effects path; a side-by-side test on
2026-09-12 (`work/nightshift/fxtest/`, full auto-enhance chain plus a TSL
effect on a gradient-heavy scene) rendered identically clean on 2.8.1 and
2.9.5, so 2.9.5 is accepted. Judge any other version by a rendered frame
with effects on, never by a clean exit:

```powershell
# Windows
irm https://deno.land/install.ps1 | iex
deno upgrade 2.9.5
deno --version
```
```bash
# Linux/mac/WSL
curl -fsSL https://deno.land/install.sh | sh -s v2.9.5   # needs unzip or 7z
```

**One OS per `node_modules/`.** Deno writes platform-native shims into
`node_modules/.bin`; a WSL run leaves Linux symlinks that Windows cannot
open (`os error 1920`) and vice versa. When switching OS on the same
checkout, delete `node_modules/.bin` (or run `python eido.py bootstrap`)
before rendering.

Have `ffmpeg` on PATH. If it lacks `h264_nvenc`, set
`RENDER_CODEC=libx264` (or `h264_videotoolbox` on macOS).

## 2. Bootstrap JS dependencies

`node_modules/` is not committed; it regenerates from `deno.lock`:

```bash
python eido.py bootstrap          # add --fresh to rebuild from scratch
```

This runs `deno cache --node-modules-dir=auto` against the engine entry
points and pre-caches `@dimforge/rapier3d-compat` (the physics engine the
character controller imports). Re-run after any `deno.lock` change.

## 3. Health check

```bash
python eido.py doctor
```

Checks: deno version, ffmpeg/nvenc, node_modules + rapier materialized,
ComfyUI reachable (reported, not required), embeddings key set (reported,
not required).

## 4. Smoke test

```bash
python eido.py render eidoverse/examples/basic_vrm.json
```

A 10-second, 1280×720 orbit of the sample character with volumetric
clouds should land at `eidoverse/examples/basic_vrm.mp4`. Runtime varies
with hardware, shader compilation, effects and encoding. Inspect frame
progress and logs before deciding that a slow first render is stuck.

## 5. Optional backends

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
  It is a separate service, not a native rendering prerequisite.

- **Semantic theme ranking** — set `JINA_AI_KEY` (free tier) or point
  `EIDOVERSE_EMBED_URL` / `EIDOVERSE_EMBED_MODEL` / `EIDOVERSE_EMBED_KEY`
  at any OpenAI-compatible `/v1/embeddings` endpoint. Without a key,
  `fetch_model.py` ranks by relevance only (still works).
- **Python tool tiers** — see `requirements-local.txt`: the fetchers need
  only `requests`; the TTS/lipsync chain is a few audio libs; demucs
  pulls PyTorch. Install what you use.

## Platform notes

- **Windows**: native D3D12 WebGPU — the path this release was verified
  on.
- **Linux**: wgpu goes through Vulkan — you need working Vulkan drivers
  (`mesa-vulkan-drivers` / NVIDIA proprietary) + distro ffmpeg. Expected
  to work; not yet render-verified — check your first frame, not just the
  exit code, and report findings.
- **macOS**: wgpu → Metal. No nvenc — set `RENDER_CODEC=libx264` (or
  `h264_videotoolbox`). Same caveat: unverified, judge by frames.
- **Fonts**: the 19 display fonts live at `eidoverse/assets/fonts/`. For
  `text_3d`, point `fontPath` at `eidoverse/assets/fonts/<name>.ttf`
  (relative paths work) or install them system-wide.

## Troubleshooting

- **`navigator.gpu missing`** — deno can't see a WebGPU adapter: check
  GPU drivers (Vulkan on Linux) and that you're on a verified deno
  (2.8.1 or 2.9.5).
- **Rapier import error at controller creation** — bootstrap didn't
  materialize node_modules; re-run step 2 (add `--fresh` if node_modules
  came from another OS).
- **Black frames** — check device/adapter selection, the pinned versions,
  asset loading, lights, exposure and material conversion. Construct the
  renderer with `adapter: GPU_ADAPTER, device: GPU_DEVICE`; then consult
  [stack notes](../tools-guides/stack-notes.md) for the affected render path.
- **`generate_song.py --probe` fails** — inspect the reported
  connection error or missing node/model names. Check ComfyUI's address,
  version and model folders against the audio guide. A passing dependency
  probe still needs a real generation to check weight loading and GPU memory.
- **Renders come out as banded color gradients (but "DONE" and all audits
  pass)** — version drift caused this in earlier tests. Check the installed
  versions and a minimal probe before assuming the cause (the effects-path
  test scene in `work/nightshift/fxtest/fx.js` is a ready probe). Stay on a
  verified Deno (2.8.1 or 2.9.5) and always judge a new stack by a rendered
  FRAME, never by a clean exit.
- **`node_modules\.bin\...: The file cannot be accessed by the system
  (os error 1920)`** on Windows — the shims were written by a Linux/WSL
  deno run on the same checkout. Delete `node_modules/.bin` and retry.
