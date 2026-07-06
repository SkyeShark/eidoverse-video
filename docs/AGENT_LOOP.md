# Agent loop — autonomous containerized production

`eido.py agent` runs one full production autonomously: brief in, mp4 out,
no human in the middle. Chain it from cron / a queue / your own
orchestrator for a fully autonomous pipeline.

## Invocation

```bash
python eido.py agent --brief brief.txt \
    [--context context.txt]        # optional extra context file
    [--agent claude|codex|opencode]  # default claude; picks image + auth + CLI
    [--image TAG]                  # override the image tag
    [--out runs/<utc-timestamp>]   # output collection dir (default auto)
    [--comfy auto|on|off]          # ComfyUI probe/bridge behavior (default auto)
    [--gpu-adapter NVIDIA]         # MESA_D3D12_DEFAULT_ADAPTER_NAME value
    [--timeout-min N]              # kill the run after N minutes (default 90)
    [--system-prompt FILE]         # override the built-in per-agent prompt
    [--dry-run]                    # print the docker command + mounts, run nothing
```

## What the runner does

1. Copies your brief/context to `_brief.txt` / `_context.txt` at the repo
   root and recreates `work/`.
2. Probes ComfyUI (`--comfy auto`); if reachable, starts
   `eidoverse/comfy_bridge.py` on the host as a child process. Writes
   `_capabilities.json` — `{"comfyui": bool, "comfy_url": …, "jina_ai":
   bool, "gpu_adapter": …}` — the handshake agents read before planning
   audio.
3. Builds the mount list:
   - the repo root **read-write** at `/workspace`;
   - `eidoverse/assets` re-mounted **read-only** on top;
   - a per-file **read-only** bind for every tracked engine/tool file
     (derived from `git ls-files` over `eidoverse/*.mjs`, `eidoverse/*.js`,
     `eidoverse/effects_tsl/*`, `eidoverse/examples/*`, root `*.py`,
     `AGENTS.md`, `deno.lock`; glob fallback when not a git checkout).
     This is the **protection model**: a misbehaving agent can fill
     `work/` with anything, but the kernel rejects writes to the toolkit.
   - per-agent auth (see `docs/SETUP.md` §4).
4. `docker run --rm --gpus all --device /dev/dxg -e GALLIUM_DRIVER=d3d12
   -e MESA_D3D12_DEFAULT_ADAPTER_NAME=<adapter> [-e JINA_AI_KEY] …` and
   launches the agent CLI with the read-order prompt:
   *"Read `/workspace/AGENTS.md` fully, then `/workspace/_brief.txt`
   (+`_context.txt`), then produce the video it asks for."*
5. On exit (or timeout): stops the comfy bridge, then collects into
   `--out`: every artifact modified after launch (`*.mp4`, final frames,
   `work/<id>/` deliverables, the agent's stdout log) plus `run.json`
   (args, image, exit code, duration, capability flags).

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

A successful run leaves `runs/<ts>/` with the final mp4 (the newest one
is the deliverable), the scene sources that produced it, and `run.json`.
Agents are instructed to delete test clips before finishing — if you see
multiple mp4s, trust the one the agent names in its final message
(captured in the stdout log).

## Operational notes

- **One run at a time per GPU.** Sustained renders don't share the device
  well; queue your briefs.
- The container is `--rm` — all state that matters must land in the
  mounted repo (it does: `work/`, `runs/`, `techniques_archive.md`).
- `--timeout-min` is a hard stop; the collector still runs, so partial
  work is preserved for post-mortem.
- To customize the agent's standing instructions per-deployment, use
  `--system-prompt FILE` rather than editing `AGENTS.md` for one run.
