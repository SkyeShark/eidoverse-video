# Setup

## 0. Prerequisites

- **Docker** — Docker Desktop (Windows: WSL2 backend) or docker-ce (Linux).
- **NVIDIA GPU + driver** — on Windows the container reaches the GPU through
  WSL2's `/dev/dxg` + Mesa D3D12; on Linux through `--gpus all`.
- **Python 3.10+** on the host (the `eido.py` runner is stdlib-only).
- ~20 GB disk for the image + node_modules + working space.

## 1. Build the render image

One Dockerfile serves every flavor via `--build-arg AGENT=`:

```bash
# render-only (no agent CLI) — for harness mode + CI:
docker build -f docker/Dockerfile --build-arg AGENT=none -t eidoverse:render docker

# agent-loop flavors (each adds one agent CLI):
docker build -f docker/Dockerfile --build-arg AGENT=claude   -t eidoverse:claude docker
docker build -f docker/Dockerfile --build-arg AGENT=codex    -t eidoverse:codex docker
docker build -f docker/Dockerfile --build-arg AGENT=opencode -t eidoverse:opencode docker
```

The image contains: Deno + Mesa (recent enough for the WebGPU TSL passes) +
ffmpeg(+nvenc) + the Python/audio toolchain (edge-tts, demucs, librosa, …)
+ fonts. The repo itself is NOT baked in — it's mounted at `/workspace`
at runtime, so engine changes never require a rebuild.

## 2. Bootstrap JS dependencies

`node_modules/` is not committed; it regenerates from `deno.lock`:

```bash
python eido.py bootstrap --image eidoverse:render
```

This runs `deno cache --node-modules-dir=auto` against the engine entry
points inside the container (cwd `/workspace`), pre-caches
`@dimforge/rapier3d-compat` (the physics engine the controller imports),
and asserts `RAPIER_OK`. Re-run after any `deno.lock` change.

## 3. Health check

```bash
python eido.py doctor
```

Checks: docker reachable, image present, GPU device visible, node_modules +
rapier materialized, ComfyUI reachable (reported, not required), embed/API
keys set (reported, not required).

## 4. Agent CLI auth (agent-loop mode only)

The runner bind-mounts **your own host credentials and config** read-only
into the container at launch — nothing is baked into the image or the
repo, and no model/provider is hardcoded:

| agent    | host auth/config (mounted ro)                                  | mounted at                                              |
|----------|----------------------------------------------------------------|---------------------------------------------------------|
| claude   | `~/.claude/`                                                   | `/home/node/.claude/`                                    |
| codex    | `~/.codex/` (auth.json + config.toml)                          | `/home/node/.codex/`                                     |
| opencode | `~/.config/opencode/` + `~/.local/share/opencode/`             | same paths under `/home/node/` (+ `OPENCODE_API_KEY` env)|

Log in / configure on the host first (`claude login`, `codex login`,
`opencode auth login` or set `OPENCODE_API_KEY`); `eido.py agent` picks
the mounts from its per-agent table. **opencode runs with whatever
default provider/model you configured on your host** — the runner never
selects a model for it (set the `OPENCODE_MODEL` env var for an explicit
per-run pin, e.g. `OPENCODE_MODEL=opencode-go/some-model`). Missing paths
are skipped with a note.

## 5. Optional backends

- **ComfyUI (music + SFX)** — run ComfyUI on the host at `:8188` with the
  ACE-Step (music) and Stable Audio (SFX) models installed. `eido.py agent
  --comfy auto` probes it, starts `eidoverse/comfy_bridge.py` when up, and
  records the result in `_capabilities.json` so agents plan audio
  accordingly. Override the URL with `COMFYUI_URL`.
- **Semantic theme ranking** — set `JINA_AI_KEY` (free tier) or point
  `EIDOVERSE_EMBED_URL` / `EIDOVERSE_EMBED_MODEL` / `EIDOVERSE_EMBED_KEY`
  at any OpenAI-compatible `/v1/embeddings` endpoint. Without a key,
  `fetch_model.py` ranks by relevance only (still works).

## 6. Local rendering (no Docker) — optional, FAST

The engine also runs directly on the host — on Windows, native Deno
WebGPU talks D3D12 straight to your GPU (no Mesa translation), which
renders **4-10× faster** than the container path. Verified output-
identical to the container.

1. Install Deno **2.8.1** (version-pinned for the same wgpu reason as
   the image — 2.9.x corrupts the effects path):
   ```powershell
   # Windows
   $v = "2.8.1"; irm https://deno.land/install.ps1 | iex
   ```
   ```bash
   # Linux/mac
   curl -fsSL https://deno.land/install.sh | sh -s v2.8.1
   ```
2. Have `ffmpeg` on PATH. If it lacks `h264_nvenc`, set
   `RENDER_CODEC=libx264` for local renders.
3. Bootstrap the JS deps with HOST deno. (Deno's node_modules store is
   platform-specific; container runs keep their own copy in a Docker
   named volume, so the two modes never conflict — bootstrap each mode
   you use once.):
   ```bash
   python eido.py bootstrap --local          # add --fresh to rebuild
   ```
4. Render:
   ```bash
   python eido.py render eidoverse/examples/basic_vrm.json --local
   ```

`python eido.py doctor` reports host deno/ffmpeg/nvenc status.

**Platform notes for the raw path:**
- **Windows**: native D3D12 WebGPU — the path this release was verified on
  (pixel-identical to the container, 4-10× faster).
- **Linux**: wgpu goes through Vulkan — you need working Vulkan drivers
  (`mesa-vulkan-drivers` / NVIDIA proprietary) + distro ffmpeg. Expected to
  work; not yet render-verified — check your first frame, not just the exit
  code, and report findings.
- **macOS**: wgpu → Metal. No nvenc — set `RENDER_CODEC=libx264` (or
  `h264_videotoolbox`). Same caveat: unverified, judge by frames.
- **Fonts**: the 19 display fonts live at `docker/fonts/` in the repo; the
  container installs them at `/usr/share/fonts/truetype/custom/`. For local
  `text_3d` use, point `fontPath` at `docker/fonts/<name>.ttf` (relative
  paths work) or install them system-wide.

**That's the whole render dependency list: Deno + ffmpeg.** The Python
tools are tiered and optional — see `requirements-local.txt` (fetchers
need only `requests`; the TTS/lipsync chain is a few audio libs; demucs
pulls PyTorch). The recommended HYBRID workflow skips most of it: render
locally for speed, and run the audio/fetch tools inside the container
(`python eido.py shell`) where everything is preinstalled.

## 7. Smoke test (container)

```bash
python eido.py render eidoverse/examples/basic_vrm.json
```

A 10-second, 1280×720 orbit of the sample character with volumetric clouds
should land at `eidoverse/examples/basic_vrm.mp4`. Expect roughly ~0.5–1
second of wall time per second of 720p footage on a modern NVIDIA GPU —
if a 10-second clip takes many minutes, something is stuck; read the log.

## Disk hygiene (read once — it will save your drive)

Docker Desktop's VM disk **grows on demand and never shrinks by itself**:
image builds and build cache expand it, and deleting images afterwards
only frees space *inside* the VM — the host-side file keeps its high-water
mark. Left unattended this can fill the entire host drive (builds start
failing with "read-only file system" and the engine crashes).

Defenses, in order of value:
1. **Set a hard cap**: Docker Desktop → Settings → Resources → Advanced →
   "Disk usage limit". With a cap, a runaway build fails cleanly inside
   Docker instead of eating your drive.
2. **Prune after building**: `python eido.py cleanup` (drops build cache +
   dangling images; `--all-cache` for everything). `eido.py doctor` shows
   what's reclaimable, and `eido.py bootstrap --build` refuses to start
   below ~60 GB free.
3. **Build flavors one at a time** — each is ~14 GB and they share layers,
   but pin/Dockerfile changes rebuild the big layers per flavor.
4. **Compact when the host drive runs low** (Windows): fully quit Docker
   Desktop → `wsl --shutdown` → in an *elevated* terminal:
   ```
   diskpart
   select vdisk file="%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx"
   attach vdisk readonly
   compact vdisk
   detach vdisk
   ```
   (Run `docker run --rm --privileged --pid=host alpine nsenter -t 1 -m -u -n -i fstrim -a -v`
   once beforehand, while Docker is still up, so the compact has trimmed
   pages to drop. diskpart fails instantly and silently if the engine is
   still running.)

## Troubleshooting

- **`navigator.gpu missing`** — the container didn't get the GPU: on
  Windows check Docker Desktop is on the WSL2 backend and `/dev/dxg`
  exists in WSL; on Linux check `--gpus all` works (`nvidia-container-toolkit`).
- **Rapier import error at controller creation** — bootstrap didn't
  materialize node_modules; re-run step 2.
- **Black frames** — almost always a scene bug (see AGENTS.md "Known stack
  quirks"), not the stack: renderer must be constructed with
  `adapter: GPU_ADAPTER, device: GPU_DEVICE`.
- **`generate_song.py` connection error** — ComfyUI isn't running/reachable
  (this is graceful: agents degrade to TTS + ambience).
- **Renders come out as banded color gradients (but "DONE" and all audits
  pass)** — wgpu/Mesa version drift corrupting the TSL effects path. Use the
  pinned versions (Deno 2.8.1; the image's pinned Mesa) and always judge a
  new stack by a rendered FRAME, never by a clean exit.
