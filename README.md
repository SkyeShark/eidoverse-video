# Eidoverse Video — prealpha 0.01

A **video-production toolkit for AI agents**: a Deno + WebGPU + three.js/TSL
render engine with physics-based VRM character locomotion (Rapier), foot IK,
a movement vocabulary (run / vault / climb / jump / ladders / gestures /
sitting), 33 TSL post-processing effects, simulation showpieces (3D fluid,
cloth, interactive water, particle morphs, GPU grass, procedural terrain),
semantic asset fetchers (models / HDRIs / PBR textures), and a full audio
pipeline (music + SFX generation via ComfyUI, TTS narration, lipsync,
mixing) — all documented as a single agent-facing contract (`AGENTS.md`)
that Claude Code, codex, and opencode read natively.

Open the repo in your coding agent, describe the video you want, and the
agent plans a 4–6 phase piece, fetches and places assets, writes a scene
script against the engine's globals, generates and mixes audio, renders,
self-verifies against the engine's audits, and ships a finished mp4.

**Status: prealpha.** Extracted from a production pipeline that has shipped
hundreds of videos; the extraction is fresh, so expect rough edges in setup.

## Branches

- **`main`** (this branch) — run it straight out of your agent harness
  with your human/agent pair: install Deno + ffmpeg, no containers
  anywhere.
- **`auto`** — the containerized edition: a Docker render image and a
  runner that wraps the whole toolkit as a **subagent for autonomous
  agentic loops** (a parent orchestrator hands in a brief file and gets
  back a finished mp4, engine mounted read-only, no human in the loop).

## Requirements

- **GPU**: NVIDIA recommended. Windows renders through native D3D12
  WebGPU; Linux through Vulkan; macOS through Metal.
- **Deno 2.8.1** (pinned — see `docs/SETUP.md`) and **ffmpeg** on PATH.
  That's the whole render stack.
- **Python 3** for the `eido.py` runner and the optional tool scripts.
- Optional: a local **ComfyUI** (`:8188`) with ACE-Step + Stable Audio
  models for music/SFX generation (`generate_song.py` / `generate_sfx.py`);
  without it the audio pipeline degrades to TTS + synthesized ambience.
- Optional: `JINA_AI_KEY` (or any OpenAI-compatible embeddings endpoint via
  `EIDOVERSE_EMBED_*`) for semantic theme-ranking in `fetch_model.py`.

## Quickstart

```bash
# 1. Install Deno 2.8.1 + ffmpeg (docs/SETUP.md §1)

# 2. One-time dependency fetch (materializes node_modules from deno.lock)
python eido.py bootstrap

# 3. Health check
python eido.py doctor

# 4. Smoke test — a 10-second orbit of the sample character
python eido.py render eidoverse/examples/basic_vrm.json
```

Then open the repo in **Claude Code, codex, or opencode** — the agent
auto-reads `AGENTS.md` and knows the whole toolkit. Describe the video
you want, in plain words. The agent writes the scene into `work/<id>/`
and renders it natively on your GPU. See `docs/HARNESS_MODE.md` for the
working rhythm (probes, review, iteration).

## Repo map

```
AGENTS.md            the single agent-facing contract (API + production rules)
CLAUDE.md            one-line pointer shim (@AGENTS.md) so Claude Code auto-loads it
eido.py              runner: bootstrap / doctor / render
docs/                SETUP.md, HARNESS_MODE.md
eidoverse/           the render engine
├── render_scene.mjs      engine entry (helper injection, audits, ffmpeg pipe)
├── render_common.mjs     shared engine helpers
├── *.js                  helper modules (controller, foot IK, placement, sims, …)
├── effects_tsl/          33 TSL post-processing effects + registry
├── examples/             starter scenes (basic_vrm, obstacle_course)
└── assets/               vrms / models / animations / particle_textures / fonts
fetch_model.py fetch_hdri.py fetch_texture.py     asset fetchers
generate_song.py generate_sfx.py                  ComfyUI music/SFX (optional backend)
merge_av.py align_lyrics.py lipsync.py            audio/lipsync tools
cyborg_voice.py cyborg_stutter.py                 character voice filters
deno.lock deno.json  pinned JS deps + workspace marker (node_modules regenerates from them)
work/                agent scratch (gitignored)
```

## Music & SFX — the ComfyUI backend (optional)

`generate_song.py` (music) and `generate_sfx.py` (sound effects) don't
synthesize audio themselves — they submit workflows to a **local ComfyUI**
and collect the result. To enable them:

1. Install ComfyUI (Desktop app or server) on the host.
2. Install the model checkpoints into ComfyUI's `models/` tree:
   - **ACE-Step** (text-to-music) — used by `generate_song.py`; its
     workflow is embedded in the script (tags/lyrics/bpm/key/seed in,
     `song.mp3` out).
   - **Stable Audio 3** (text-to-SFX) — used by `generate_sfx.py`; the
     repo ships the workflow (`sa3_workflow.json`) and the script fills
     in prompt/duration/category/seed.
3. Reachability: the tools look for ComfyUI at `:8188`
   (`COMFYUI_URL` overrides). ComfyUI Desktop binds localhost on a
   roaming port — `eidoverse/comfy_bridge.py` fixes that by proxying
   `0.0.0.0:8188` to wherever ComfyUI actually is.

Without ComfyUI everything else still works: the tools fail fast with a
clear error and the audio pipeline degrades to edge-tts narration +
ffmpeg-synthesized ambience.

## Helper maturity — what's solid, what's rough

Production-hardened (hundreds of shipped renders): the render engine +
audits, the character controller stack (locomotion / maneuvers / foot IK /
seating), the effects catalog, the placement system, the simulation
showpieces (fluid_3d, cloth, water, particle morph, grass, terrain), the
fetchers. Rougher edges to expect at prealpha:

- **`sdf_raymarch_loader`** — the engine is solid; writing your own good
  `map(p)` TSL is on you (the shipped EXAMPLES are vehicles + volumetrics).
- **`robotics_kit`** — brand new (7 machine archetypes + kitbash assembly +
  creature cyborg grafts); kinematics are closed-form and solid, but it
  has far fewer shipped renders behind it than the rest.
- **`rhombic_dodecahedron`, `robot_debug`** — niche, functional, lightly
  documented.
- **`fetch_model.py` previews/ranking** — install its tier from
  `requirements-local.txt`; with bare `requests` it still fetches but
  degrades (no previews, relevance-only ranking without an embeddings key).
- **Local rendering on Linux/macOS** — expected to work (Vulkan/Metal),
  verified only on Windows so far.

## Characters

Three rigged VRM characters ship in `eidoverse/assets/vrms/`:
**Aletheia** and **Aporia** (production-quality, cyberpunk-styled) and
**Claude** (a light mannequin, also the default smoke-test character —
represents the AI Claude specifically; see the usage rule in AGENTS.md).
Drop any additional `.vrm` into the same folder and it works identically.

## License

Code is licensed under **AGPL-3.0** (see `LICENSE`). The bundled asset
library is a mix of original handmade and AI generated work by the
maintainer, shipped with the repo (particle sprites: Kenney Particle
Pack, CC0). See `CREDITS.md` for library credits and design inspirations.
