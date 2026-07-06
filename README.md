# Eidoverse Video — prealpha 0.01

**A video-production toolkit for AI agents.** Open this repo in a coding
agent (Claude Code, codex, opencode — they auto-read `AGENTS.md`, the
full contract), describe the video you want in plain words, and the agent
plans it, builds the world, animates the characters, generates and mixes
the audio, renders on your GPU, and hands you a finished mp4.

Everything renders through **Deno + WebGPU + three.js/TSL at real-time
speeds with minimal CPU** — no per-frame CPU loops, no baking. The engine
was extracted from a production pipeline that has shipped hundreds of
videos.

## Quickstart (containerized)

```bash
# 1. Build the render image (one-time; ~15-30 min)  → docs/SETUP.md
docker build -f docker/Dockerfile --build-arg AGENT=none -t eidoverse:render docker
python eido.py bootstrap --image eidoverse:render   # deps into the container volume
python eido.py doctor                               # health check
python eido.py render eidoverse/examples/basic_vrm.json   # smoke test

# Autonomous loop: build an agent-flavored image, hand it a brief
docker build -f docker/Dockerfile --build-arg AGENT=claude -t eidoverse:claude docker
python eido.py agent --agent claude --brief my_brief.txt   # → runs/<timestamp>/
```

The runner writes `_brief.txt`/`_capabilities.json`, mounts the repo at
`/workspace` (engine files read-only), launches the agent CLI inside the
container, and collects the outputs. Full loop docs: `docs/AGENT_LOOP.md`.

## Branches

- **`auto`** (this branch) — the containerized edition: a Docker render
  image and a runner that wraps the whole toolkit as a **subagent for
  autonomous agentic loops** (a parent orchestrator hands in a brief file
  and gets back a finished mp4, engine mounted read-only, no human in the
  loop).
- **`main`** — the harness edition: no Docker anywhere; an agent + its
  human install Deno + ffmpeg and render natively.

## What's in the toolkit

**Render engine** (`eidoverse/render_scene.mjs`)
- WebGPU + NodeMaterial/TSL renderer harness: scene scripts get the GPU
  device, an asset injector, helper globals, and an ffmpeg NVENC pipe.
- Always-on auto-enhance: GTAO, screen-space reflections, bloom, FXAA.
- End-of-render **audits** that catch real defects by name: placement
  (floating/interpenetrating props), locomotion (hand-slid characters),
  lipsync (frozen mouths), camera (bouncing zooms), frozen VRM poses.

**Characters & locomotion**
- VRM character controller with physics (Rapier), terrain-conforming
  foot IK, and automatic incline speed — plus a full **movement
  vocabulary**: walk, run, vault, ledge climbs, gap jumps, ladders,
  wall scrambles, upper-body gestures while walking, chair/ground sits.
- Autonomous navigation (`VRMRobotBody`): lidar sensing + A* routing to
  a destination, or explicit waypoints (`EidoverseRobotController`).
- 30+ VRMA animation clips ship in `eidoverse/assets/animations/`.
- Lipsync pipeline: viseme timelines from any vocal audio.

**Procedural builders**
- `makeCreature` — Spore-style creatures from one parameter set: quad /
  biped / bird / serpent / octopus / insect / spider / fish / snail
  stances, morphology-adaptive gaits, flight with banking, animal faces,
  horns/tusks/fangs/feet/accessories, robot variants, seeded randoms —
  and **hinged talking jaws** you can drive from a real audio envelope.
- `makeRobot` / `makeBot` — industrial machines with real closed-form
  kinematics (6-DOF arm, SCARA, delta, Stewart, turret, AGV, gantry, FDM
  printer) + a kitbash assembler (any part on any base), all
  self-animating. `RoboticsKit.cyborg()` grafts modules onto creatures.
- `FabSim` — print any mesh (molten-metal deposition that solidifies
  into the exact source model) or carve it from a solid block with a
  CNC gantry, both raymarched in realtime.
- `makeTerrain` (heightfield ground with height/slope texture blending),
  `makeGrass` (GPU wind-swept blade fields), `Loft` (surfaces through
  cross-sections: vases, horns, ducts, ribbons), `text_3d` (extruded
  type from 19 bundled fonts), `ProceduralMaterials` (worn metal, skin,
  fabric, rubber… as NodeMaterials).
- **SPOM relief** — silhouette parallax occlusion mapping: carved depth
  whose outline follows the relief (`createReliefColumn` for curved
  surfaces, `createParallaxMaterial` for flat ones).

**Simulation**
- `fluid_3d` — 3D MLS-MPM particle liquid (pours, fountains, splashes)
  with a raymarched water surface.
- `water_compute` — interactive rippling water (drop a disturbance
  anywhere, circular pools for vessels).
- `cloth_sim` — mass-spring fabric with wind, pinning, and scene
  collision (flags, banners, capes, curtains).
- `fluid_sim` — 2D ink/dye stable-fluids for panels and screens.
- `makeIsoField` — GPU-raymarched isosurfaces over a writable voxel
  field (the fast path for anything MarchingCubes-shaped).

**Particles, FX & motion graphics**
- `makeParticles` — GPU sprite systems (fire, smoke, sparks, embers,
  dust, snow, magic, stars) + an 80-texture particle library.
- `makeParticleMorph` — dissolve any mesh/VRM into particles and reform
  it as another shape, a word (`fromText`), or ASCII art.
- `sdf_raymarch_loader` — placeable raymarched objects (with correct
  occlusion) + volumetric smoke/fire/explosions.
- **31 TSL post effects**: volumetric clouds, godrays, lens flares,
  depth fog, rain (world + lens), glitch/VHS/CRT families, color grades,
  edge/line looks, blurs, underwater, kaleidoscope, and a full-frame
  nuclear blast.
- `makeScreen` / `makeVideoScreen` (in-world animated displays),
  `makeOverlayLayer` (broadcast-style HUDs and lower thirds),
  `makeAsciiPanel` (glowing terminal panels).

**Placement & scene assembly**
- Intent-based placement that reads real geometry: `placeOn`,
  `placeAgainst`, `placeTouching` (mesh-accurate contact), `snapToGround`,
  `scatterOn`, `findClearSpot`, `faceToward`, `driveAlong` (vehicles that
  face their travel), `stationBeside`, `seatOn` / `sitOnGround`.
- Post-setup audits auto-fix overlaps and near-floaters, and hard-flag
  anything genuinely dumped in mid-air.

**Asset pipeline**
- `fetch_model.py` — parallel search across local models + Poly Haven +
  Smithsonian + NASA + NIH 3D with **semantic theme re-ranking**, scale
  and pivot info, preview renders, and kit detection (`loadKit` splits
  modular kits into usable parts).
- `fetch_hdri.py` (environment lighting) and `fetch_texture.py` (full
  PBR sets — basecolor/normal/roughness/AO/displacement, all CC0).
- ~90 bundled models, HDRI-ready examples, particle textures, fonts.

**Audio**
- `generate_song.py` — full songs (any genre, sung vocals or
  instrumental) via ACE-Step through a local ComfyUI.
- `generate_sfx.py` — sound effects/ambience via Stable Audio.
- TTS narration (edge-tts) + character voice filters
  (`cyborg_stutter.py` spoken / `cyborg_voice.py` sung), demucs stem
  splitting, `align_lyrics.py` (lyric timestamps), `lipsync.py`
  (visemes), `merge_av.py` (safe mux that refuses frozen-frame padding).

**Runner** — `eido.py`: `bootstrap` / `doctor` / `render [--probe]` / `shell` / `agent` (the loop runner) / `cleanup`.

## Requirements

- **GPU**: NVIDIA recommended. Windows renders through native D3D12
  WebGPU; Linux through Vulkan; macOS through Metal.
- **Deno 2.8.1** (version-pinned — see `docs/SETUP.md`) and **ffmpeg**.
  That's the whole render stack.
- **Python 3.10+** for the runner and tool scripts (tiered deps in
  `requirements-local.txt`; the fetchers need only `requests`).
- Optional: a local **ComfyUI** (`:8188`) with ACE-Step + Stable Audio
  checkpoints for music/SFX generation — without it the audio pipeline
  degrades to TTS + synthesized ambience. See "Music & SFX" below.
- Optional: `JINA_AI_KEY` (or any OpenAI-compatible embeddings endpoint
  via `EIDOVERSE_EMBED_*`) for semantic theme-ranking in `fetch_model.py`.

## Music & SFX — the ComfyUI backend (optional)

`generate_song.py` (music) and `generate_sfx.py` (sound effects) submit
workflows to a **local ComfyUI** and collect the result:

1. Install ComfyUI (Desktop app or server).
2. Install the checkpoints: **ACE-Step** (text-to-music; workflow
   embedded in the script) and **Stable Audio** (text-to-SFX; the repo
   ships `sa3_workflow.json`).
3. The tools look for ComfyUI at `:8188` (`COMFYUI_URL` overrides).
   ComfyUI Desktop binds a roaming localhost port —
   `eidoverse/comfy_bridge.py` proxies `0.0.0.0:8188` to wherever it
   actually is.

Without ComfyUI everything else still works; the tools fail fast with a
clear error.

## Characters

Four rigged VRMs ship in `eidoverse/assets/vrms/` (each with a preview
image; drop in your own `.vrm` and it works identically):

- **`aletheia.vrm`** / **`aporia.vrm`** — production-quality
  cyberpunk-styled characters.
- **`claude_suit.vrm`** — Claude, the AI, in a suit — **the primary
  Claude model**.
- **`claude.vrm`** — a legacy lightweight Claude stand-in (kept for the
  smoke-test example; prefer `claude_suit.vrm`).

The Claude models represent the AI Claude specifically — the usage rule
is in `AGENTS.md`.

## Status

**Prealpha.** The engine, controller stack, placement system, effects,
and simulations are production-hardened; the packaging is young. Known
rough edges: `fetch_model.py`'s preview rendering and ranking need their
Python tier installed (with bare `requests` it still fetches, unranked);
local rendering is render-verified on Windows, expected-but-unverified
on Linux (Vulkan) and macOS (Metal); `sdf_raymarch_loader` gives you the
engine but writing a good `map(p)` is on you.

## License

Code is licensed under **AGPL-3.0** (see `LICENSE`). The bundled asset
library is a mix of original handmade and AI-generated work by the
maintainer, shipped with the repo (particle sprites: Kenney Particle
Pack, CC0). See `CREDITS.md` for library credits and design inspirations.
