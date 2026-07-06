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

## 1. Install Deno 2.8.1 (pinned) + ffmpeg

Deno is version-pinned: **2.9.x corrupts the TSL effects path** (renders
come out as banded gradients while every audit passes). Use 2.8.1:

```powershell
# Windows
$v = "2.8.1"; irm https://deno.land/install.ps1 | iex
```
```bash
# Linux/mac
curl -fsSL https://deno.land/install.sh | sh -s v2.8.1
```

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
clouds should land at `eidoverse/examples/basic_vrm.mp4`. Expect roughly
~0.5–1 second of wall time per second of 720p footage on a modern NVIDIA
GPU — if a 10-second clip takes many minutes, something is stuck; read
the log.

## 5. Optional backends

- **ComfyUI (music + SFX)** — run ComfyUI on the host at `:8188` with the
  ACE-Step (music) and Stable Audio (SFX) models installed
  (`COMFYUI_URL` overrides the address). ComfyUI Desktop binds localhost
  on a roaming port — `eidoverse/comfy_bridge.py` fixes that by proxying
  `0.0.0.0:8188` to wherever ComfyUI actually is; run it alongside your
  session when you want `generate_song.py` / `generate_sfx.py`.
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
  GPU drivers (Vulkan on Linux) and that you're on deno 2.8.1.
- **Rapier import error at controller creation** — bootstrap didn't
  materialize node_modules; re-run step 2 (add `--fresh` if node_modules
  came from another OS).
- **Black frames** — almost always a scene bug (see AGENTS.md "Known
  stack quirks"), not the stack: the renderer must be constructed with
  `adapter: GPU_ADAPTER, device: GPU_DEVICE`.
- **`generate_song.py` connection error** — ComfyUI isn't
  running/reachable (this is graceful: degrade to TTS + ambience).
- **Renders come out as banded color gradients (but "DONE" and all audits
  pass)** — wgpu version drift corrupting the TSL effects path. Pin Deno
  2.8.1 and always judge a new stack by a rendered FRAME, never by a
  clean exit.
