# Setup

Everything runs in your environment: Deno renders through hardware WebGPU
when GPU access is available, or software WebGPU when it is not. ffmpeg
encodes, and the Python tools are optional extras. **The whole
render dependency list is Deno + ffmpeg.**

(A containerized edition — Docker render image + the autonomous
agent-loop runner — lives on the `auto` branch; see its docs if you want
the sandboxed/subagent setup instead.)

## 0. Prerequisites

- **WebGPU runtime/driver** — use a hardware GPU whenever GPU access is
  available; NVIDIA recommended. Windows uses D3D12; native Linux normally
  uses Vulkan; macOS uses Metal. WSL 2 needs the
  [explicit GPU setup below](#gpu-setup-for-wsl-2). Environments without
  GPU access can use [software WebGPU fallback](#software-fallback).
- **Python 3.10+** (the `eido.py` runner is stdlib-only).
- A few GB of disk for node_modules + working space.

## 1. Install Deno 2.8.1 or 2.9.5 + ffmpeg

Use **Deno 2.8.1 or 2.9.5**. A version check or a successful render does
not establish hardware acceleration: run the GPU health check in the same
shell and OS you will render from, then inspect a probe frame with effects.

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

Have `ffmpeg` on PATH. On a hardware (or unverified) adapter the renderer
encodes with `h264_nvenc` when ffmpeg lists it and a one-frame test encode
succeeds; otherwise it warns and uses `libx264` (CPU **video encoding**). A
software adapter uses `libx264` without testing. `RENDER_CODEC` overrides the
choice, for example `RENDER_CODEC=h264_videotoolbox` for Apple's encoder. The
video encoder does not select the rendering backend: hardware or software
WebGPU is reported separately by `doctor` and renderer startup.

### GPU setup for WSL 2

WSL seeing a GPU in `nvidia-smi` is not enough. CUDA, Vulkan and OpenGL use
different driver paths. A Linux Deno process can select Mesa's software
Vulkan renderer (`llvmpipe`/lavapipe) even while the NVIDIA card is visible.
`powerPreference: 'high-performance'` does not prevent that selection.

The verified WSL route is **Deno WebGPU → wgpu GL backend → Mesa D3D12 →
the Windows hardware GPU**. The scene API remains WebGPU/TSL. This route
does not need a Linux NVIDIA kernel driver or a Vulkan Dozen (`dzn`) ICD.

1. Use WSL **2**, a current Windows GPU driver supporting WSL GPU access,
   and current WSL/WSLg. Check `wsl --list --verbose` in PowerShell. If WSL
   needs updating, use `wsl --update`; restart it after saving active work.
   See [Microsoft's WSL GPU prerequisites](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps).
2. In Ubuntu, ensure Mesa's EGL/D3D12 support is available. The distro
   packages are `libgl1-mesa-dri`, `libegl-mesa0` and `libegl1`:

   ```bash
   sudo apt update
   sudo apt install libgl1-mesa-dri libegl-mesa0 libegl1
   test -e /dev/dxg && echo 'WSL GPU device present'
   ```

   `/dev/dxg` confirms access to the host GPU; the Deno probe below checks
   whether the selected rendering driver actually uses it.
3. Select the hardware backend **in the WSL shell used for both checks
   and renders**:

   ```bash
   export PATH="$HOME/.deno/bin:$HOME/.local/bin:$PATH"
   export DENO_WEBGPU_BACKEND=gl
   export GALLIUM_DRIVER=d3d12
   export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
   unset LIBGL_ALWAYS_SOFTWARE
   python3 eido.py doctor --gpu-only
   ```

   Change `NVIDIA` to a substring of your intended GPU's name for Intel/AMD.
   Mesa documents this selection in its
   [D3D12 driver instructions](https://docs.mesa3d.org/drivers/d3d12.html).
   Deno reads `DENO_WEBGPU_BACKEND` when creating its GPU instance; set it
   before launching Deno, not inside scene code.
4. On a machine with GPU access, look for a named hardware adapter,
   `"backend":"hardware"`, `"isFallbackAdapter":false`, and
   `"computeReadback":"passed"`. If `llvmpipe`, lavapipe or SwiftShader
   is selected despite an accessible GPU, correct the driver/backend
   configuration. After hardware works, keep the three backend/adapter
   exports in your WSL shell profile or render launcher. Software fallback
   remains available in environments without GPU access, as described below.
5. Bootstrap and run a scene probe from that shell. Keep a separate checkout
   and `node_modules/` for native Linux/WSL runs and Windows runs. Native
   binaries and `.bin` shims differ by OS; sharing a dependency store can
   break either installation. An agent working in WSL can instead launch
   the Windows Python/Deno runner from PowerShell against its Windows
   checkout; that uses Windows D3D12 and Windows dependencies.

The WSL route above was checked on an RTX 5090 Laptop GPU with Deno 2.9.5:
hardware selection, GPU compute/readback, and an inspected Three.js/TSL
render. This is a setup check, not a guarantee that every effect or GPU
simulation fits that backend's capabilities. Always inspect the scene probe.
An alternative hardware Vulkan driver can also work, but must pass the
same checks; installing `mesa-vulkan-drivers` alone does not establish it.

**Known limit of the WSL GL/D3D12 route** (2026-09-14, RTX 5090 Laptop,
Mesa 26.0.3, deno 2.8.1 and 2.9.5): wgpu's GLSL backend declares every
`texture_depth_2d` as `sampler2DShadow`, so a depth buffer can only be
*compared* there, never read. Any pass that reads depth fails at pipeline
creation with `GPUInternalError` (`WGSL textureLoad from depth textures is
not supported in GLSL`; a non-comparison `textureSampleLevel` fails the same
way in Mesa's compiler). Three's TSL turns nearest-filtered depth `sample()`
into `textureLoad`, so this covers N8AO, SSR, the N8AO depth copy and any
depth-fog / depth-of-field effect. Shadow maps (comparison sampling), bloom,
FXAA, fog and the overlay work. The renderer's MSAA resolve (`antialias:
true`) also blacks every frame on this route, and the kit's own
`eidoverse/examples/robotics/manufacturing.json` renders black there for the
same reason. The `auto` branch's Docker route sets `GALLIUM_DRIVER=d3d12` and
the adapter name but not `DENO_WEBGPU_BACKEND=gl`; it was not tested from
this checkout, so how it differs is unverified.

What to do: for full auto-enhance at GPU speed use the Windows Deno (native
D3D12) from Git Bash; on WSL either accept `_aoParams = {enabled:false}`,
`_ssrParams = {enabled:false}` and `antialias:false`, or force the Vulkan
software adapter (`DENO_WEBGPU_BACKEND=vulkan`) and budget CPU time. Capture
the exact failure with `GPU_DEVICE.addEventListener('uncapturederror', ...)`
in `setup()`, or compile a dumped WGSL module standalone with
`device.createRenderPipelineAsync` to read the backend's message.

### Software fallback

With no GPU access, Deno's WebGPU can still render on the CPU through a
software adapter such as Mesa's `llvmpipe`/lavapipe on Linux. Nothing needs
to be switched on in the kit; the adapter request in
`eidoverse/gpu_check.mjs` handles both cases:

- It asks for a `high-performance` adapter first and, if none is returned,
  retries with `forceFallbackAdapter: true`. Only when both fail does it stop
  with `No WebGPU adapter found`.
- It classifies the adapter as `software` when the runtime flags it as a
  fallback adapter or its name matches `llvmpipe`, `lavapipe`, `SwiftShader`,
  `softpipe`, `WARP`, "Basic Render" or "software"; as `hardware` when it is
  named and not flagged; otherwise as `unknown`.
- A software adapter prints `[gpu] WARNING: Software WebGPU fallback: …` and
  an unknown one `[gpu] WARNING: Cannot verify the WebGPU adapter type: …`.
  These are warnings, not failures. `python eido.py doctor` then runs the
  same compute dispatch/readback on it and keeps the warning in its output.
- Renderer startup logs `[render_common] WebGPU software: …` (or `hardware`).
  On a software adapter the default video encoder is `libx264`, with no NVENC
  test; `RENDER_CODEC` still overrides that choice.

Expect frames to take much longer on the CPU. Probe short and small first,
and inspect the effects you rely on, because a software driver's
capabilities are its own. If the warning appears on a machine that does have
a GPU, the hardware path is misconfigured — see
[Troubleshooting](#troubleshooting).

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

Checks: Deno version, the selected hardware/software WebGPU adapter plus
a real compute dispatch/readback, ffmpeg/nvenc, node_modules + Rapier materialized,
ComfyUI reachable (reported, not required), embeddings key set (reported,
not required). Use `python eido.py doctor --gpu-only` for the GPU check alone;
it needs no scene assets or bootstrap. Failures return a nonzero exit code.
Both the check and renderer startup report software fallback with a warning;
it is not a failure if the adapter works. Missing adapters or failed compute
checks remain errors. Direct renderer invocations report the backend too.

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
- **Native Linux**: normally Vulkan with the GPU vendor's hardware driver
  and distro ffmpeg. Run the GPU check to identify the selected adapter.
  Mesa's software Vulkan driver supports the CPU fallback. The WSL hardware
  test does not establish native Linux hardware Vulkan support.
- **WSL 2**: use the [hardware backend setup](#gpu-setup-for-wsl-2) above.
  The default adapter can be a CPU renderer even with a working host GPU.
- **macOS**: wgpu → Metal. No nvenc — the renderer falls back to `libx264`
  on its own; set `RENDER_CODEC=h264_videotoolbox` for Apple's encoder. Same caveat: unverified, judge by frames.
- **Fonts**: the 19 display fonts live at `eidoverse/assets/fonts/`. For
  `text_3d`, point `fontPath` at `eidoverse/assets/fonts/<name>.ttf`
  (relative paths work) or install them system-wide.

## Troubleshooting

- **`navigator.gpu missing`** — include `--unstable-webgpu` when invoking
  Deno directly and use Deno 2.8.1 or 2.9.5. `eido.py` adds the flag.
- **Software fallback warning when a GPU is available** — run
  `python eido.py doctor --gpu-only` in the render shell. On WSL, check the
  three backend/adapter exports above and Mesa's D3D12 driver. On native
  Linux, check the hardware Vulkan driver. A visible GPU in `nvidia-smi`
  and a passing ffmpeg/NVENC check do not verify Deno's rendering adapter.
- **`No WebGPU adapter found`** — neither a hardware nor a software adapter
  is exposed by this runtime. Check the driver setup; GPU-less environments
  need a compatible [software WebGPU driver](#software-fallback).
- **`GPU compute check failed` / timeout** — an adapter was selected but
  could not complete the compute/readback probe. Inspect the driver error
  before rendering; do not treat adapter enumeration alone as success.
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
- **Banded gradients despite a successful exit** — check the Deno version
  and a small scene probe with the same effects enabled. Stay on Deno 2.8.1
  or 2.9.5 and judge the rendered frame as well as the logs.
- **`node_modules\.bin\...: The file cannot be accessed by the system
  (os error 1920)`** on Windows — the shims were written by a Linux/WSL
  deno run on the same checkout. Delete `node_modules/.bin` and retry.
