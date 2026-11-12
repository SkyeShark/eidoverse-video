# Agent loop — autonomous containerized production (Blender edition)

`eido_blender.py agent` runs one full production autonomously: brief in, mp4
out, no human in the middle. Chain it from cron / a queue / your own
orchestrator for a fully autonomous pipeline. The subagent works inside the
render image, where Blender 5.2 renders EEVEE on the GPU.

## Invocation

```bash
python eido_blender.py agent --brief brief.txt \
    [--context context.txt]          # optional extra context file
    [--agent claude|codex|opencode]  # default claude; picks image + auth + CLI
    [--model MODEL]                  # pin the agent's model for this run
    [--image TAG]                    # override the image tag
    [--out runs/<utc-timestamp>]     # output collection dir (default auto)
    [--comfy auto|on|off]            # ComfyUI probe/bridge behavior (default auto)
    [--gpu-adapter NVIDIA]           # MESA_D3D12_DEFAULT_ADAPTER_NAME value
    [--timeout-min N]                # kill the run after N minutes (default 90)
    [--system-prompt FILE]           # override the built-in per-agent prompt
    [--dry-run]                      # print the docker command + mounts, run nothing
```

Build the agent's image once per flavor (docs/SETUP.md):

```bash
python eido_blender.py bootstrap --build --agent claude   # eidoverse-blender:claude
python eido_blender.py bootstrap --build                  # eidoverse-blender:render (renders only)
```

## What the runner does

1. Copies your brief/context to `_brief.txt` / `_context.txt` at the repo
   root and creates `work/`.
2. Probes ComfyUI (`--comfy auto`); if it is reachable on a roaming port,
   starts `eidoverse/comfy_bridge.py` on the host as a child process. Writes
   `_capabilities.json` — `{"comfyui": bool, "comfy_url": …, "jina_ai":
   bool, "gpu_adapter": …, "renderer": "blender-eevee"}` — the handshake
   agents read before planning audio.
3. Builds the mount list (`eido_docker.py`):
   - the repo root **read-write** at `/workspace`;
   - the toolkit **read-only** on top of it: the folders `blender/`
     (the `eidoblend` package and its tests), `eidoverse/` (the WebGPU
     engine sources the port was made from, and the shared assets),
     `tools-guides/`, `docs/`, `docker/`, `synthkit/`, `voicebox/`, plus
     every root `*.py`, `*.sh`, `AGENTS.md`, `CLAUDE.md` and `deno.*`.
     This is the **protection model**: a misbehaving agent can fill `work/`
     with anything, but the kernel rejects writes to the toolkit. (Folders,
     not per-file binds: the Blender package has hundreds of files, and a
     per-file list would overflow Windows' command line.)
   - a named volume for the container's own deno store
     (`eidoverse-blender-node-modules`);
   - per-agent auth (docs/SETUP.md §4).
4. `docker run --rm --gpus all --device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro
   -e GALLIUM_DRIVER=d3d12 -e MESA_D3D12_DEFAULT_ADAPTER_NAME=<adapter> …`
   and launches the agent CLI under `xvfb-run` (every Blender it starts gets
   the X display EEVEE opens even headless) with the read-order prompt:
   *"Read `/workspace/AGENTS.md` fully, then `/workspace/_brief.txt`
   (+`_context.txt`), then produce the video it asks for."* Inside, the agent
   renders with `python3 eido_blender.py render <scene.json> --local`.
5. On exit (or timeout): stops the comfy bridge, then collects into `--out`
   every artifact modified after launch (`*.mp4`, PNG frames, `scene.py` /
   `scene.json`, `plan.md`, the built `.blend`, the agent's stdout log) plus
   `run.json` (args, image, exit code, duration, capability flags).

## Brief conventions

`_brief.txt` is free text. Useful structure (none of it required):

```
A 60-second landscape piece: <subject / story>.
Mood: <mood>. Music: <genre direction or "instrumental">.
Character: <one of the shipped VRMs, a path to another .vrm, or "none">.
Must include: <beats you insist on>.
```

`_context.txt` is for supporting material — a script, lyrics, a persona
sheet for the character's voice, links/paths to reference imagery.

## Output contract

A successful run leaves `runs/<ts>/` with the final mp4 (the newest one is the
deliverable), the scene sources that produced it, the built `.blend` (it
replays and re-renders any frame on its own) and `run.json`. Agents are
instructed to delete test clips before finishing — if you see multiple mp4s,
trust the one the agent names in its final message (captured in the stdout
log).

## Operational notes

- **One run at a time per GPU.** Sustained renders don't share the device
  well; queue your briefs.
- **The first frame of every Blender process compiles EEVEE's shaders**
  through Mesa's D3D12 driver: 15–50 s on an RTX 5090 Laptop GPU, then
  about a second a frame for small probes. One build renders the whole film
  in one process, so a film pays it once; many single-frame probes each pay
  it. Batch probe frames into one `--at` call.
- **Check the GPU path with `python eido_blender.py doctor`.** Mesa's
  fallback to software rendering is silent (the same picture, 30–60x
  slower); the doctor prints the renderer Blender got
  (`D3D12 (NVIDIA …)` is right, `llvmpipe` is not) and times a frame.
- The container is `--rm` — all state that matters must land in the
  mounted repo (it does: `work/`, `runs/`, `techniques_archive.md`).
- `--timeout-min` is a hard stop; the collector still runs, so partial
  work is preserved for post-mortem.
- To customize the agent's standing instructions per-deployment, use
  `--system-prompt FILE` rather than editing `AGENTS.md` for one run.
