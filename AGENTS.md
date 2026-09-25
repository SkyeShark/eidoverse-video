# Eidoverse — your studio guide

**A film studio for AI agents.** You are the filmmaker, and the toolkit is
your studio. A human collaborator works alongside you; the conversation is
the writers' room.

Bring your own ideas and creative judgment. Explore the tools, build worlds,
experiment with motion and simulation, and develop what you want to make in
conversation with your collaborator. A project can begin with either of you.

The studio runs Three.js on native Deno, WebGPU and NodeMaterial/TSL. These
instructions help you find and use its tools and care for the shared workspace.

This is the interactive `main` edition. The [autonomous-loop edition](README.md#branches)
has its own workflow for receiving briefs from a parent agent.

Read this file completely. It contains the shared working rules and routes
you to the detailed tool instructions below.

## How to use the documentation

1. Start from the conversation and what you are exploring or making.
   Find the guides for the tools you want to use or learn about.
2. Open the corresponding guides in the table **before using those systems**.
   These are ordinary repository Markdown files, read with your file tools;
   they do not require a skill plugin, registration command or runtime loader.
   Merely having a file in `tools-guides/` does not load its contents.
3. For a complete video, read [production](tools-guides/production.md),
   [scene format](tools-guides/scene-format.md) and
   [render review](tools-guides/render-review.md), then the relevant system guides.
   For toolkit maintenance, start with [development](tools-guides/development.md).
4. Follow links to related guides when combining systems. There is no need to
   load every guide for every project. [The source inventory](docs/TOOLS.md) maps
   every first-party tool/module to its primary guide, including optional tools.

The conversation with your collaborator takes precedence over production
defaults. Use the guides to support the work you are developing together.
Keep detailed API recipes in their system guide; update this index whenever
a guide is added or renamed. `CLAUDE.md` imports this same main instruction.

## Working rules

- Put scene scripts, downloaded assets, audio, probes and outputs in
  `work/<short_id>/`. Run commands from the repository root unless the tool
  guide specifies another working directory. Reuse local assets in place.
- `eidoverse/` is the shared engine. Stage exploratory changes separately;
  develop the engine deliberately within the scope agreed in conversation.
  Preserve your collaborator's work, unrelated edits and the previous
  implementation when replacing tools.
- Use the installed systems and source before inventing a parallel API. Read
  errors and inspect inputs; report reproducible toolkit bugs accurately.
  A missing service, dependency or optional local backend is a real limitation.
  Never hide a failure or misrepresent which backend actually ran.
- Use hardware GPU rendering whenever the environment provides GPU access.
  Run `python eido.py doctor --gpu-only` in the render shell to check the
  backend. Software WebGPU fallback is supported for environments without
  GPU access, including hosted sandboxes; report it clearly. If a GPU is
  available but software is selected, fix the driver/backend configuration.
  WSL 2 needs [explicit hardware backend selection](docs/SETUP.md#gpu-setup-for-wsl-2).
- Render with NodeMaterials and TSL. Large per-frame vertex/instance updates,
  CPU raster loops and CPU booleans do not belong in scene playback. Build
  geometry once; use GPU deformation/compute for bulk motion. Small joint,
  camera and Object3D transforms and supported simulation controls are fine.
- Preserve authored UVs and material maps on loaded GLBs, VRMs and the modular
  robotics kit. Apply `layerSurface`/texel normalization only to suitable
  geometry built for the scene. Load image bytes with `loadImageTexture`.
- Source and inspect assets before placing them. Read previews for scale,
  pivot and forward direction. Use contact/placement helpers for related
  objects and check clipping, hovering and z-fighting throughout motion.
- Use assets whose licenses permit the intended distribution. Keep license
  attribution with the asset. The modular robotics geometry/materials are CC0
  and its runtime is MIT; do not introduce restricted manufacturer models.
- Keep setup, motion, rendering and audio on an explicit timeline. Each
  animation/controller/simulation has one owner; avoid double updates.
- Learn the API wiring from examples and make the creative choices for your
  own piece. For a full film, develop a complete visual and audio arc in the
  format and duration you and your collaborator choose. Studies and experiments
  can have their own form; targeted previews can be short or silent.
- Run single-frame/short probes before long renders. Review actual images,
  motion, sound and audit output before calling a video finished. Run one
  sustained render at a time. A passing script is not a visual review.
- Append useful discoveries to `techniques_archive.md`; search it by topic.
  Never overwrite the archive. Put corrections to reusable tool instructions
  in the corresponding guide as well.
- Share your work, creative decisions, discoveries and remaining limitations
  with your collaborator. Be accurate about what you have tried and reviewed;
  do not say a stopped process is running or claim an unrendered result.

## Tool guides — read when relevant

| Guide | Read when… |
| --- | --- |
| [Production planning](tools-guides/production.md) | Planning a complete film, choosing duration, story beats, sound and set dressing. |
| [Scene format and renderer](tools-guides/scene-format.md) | Creating scene JSON/JS, loading assets, renderer setup and engine globals. |
| [Asset sourcing and model kits](tools-guides/assets.md) | Finding models, HDRIs and PBR maps; loading GLBs and reusable kit parts. |
| [Blender asset authoring](tools-guides/blender.md) | Headless Blender runs, garments and accessories for VRMs, VRMA animation clips, hard-surface props baked to GLB and trim sheets. |
| [Props and sets](tools-guides/props-and-sets.md) | Historical voice machines (1939–2001), an 1896 tandem with rider IK, and the DAISY film's corner, funeral and ocean sets. |
| [Audio and speech](tools-guides/audio.md) | Music, SFX, narration, voice processing, lyric timing, lipsync and mixing. |
| [Voice synthesis](tools-guides/voicebox.md) | Singing or speaking voices made from scratch, historical machine-voice eras (1939 Voder → neural), choirs, phoneme-exact visemes. |
| [Music synthesis](tools-guides/synthkit.md) | Hand-built instruments and drums, sequencing, sidechain, designed FX, loudness-targeted mastering. |
| [VRM characters](tools-guides/characters.md) | Loading, casting, animating, walking, running, gestures, sitting, foot IK, the claudesona's face and outfits, turntable sheets. |
| [VRM autonomous navigation](tools-guides/navigation.md) | Sensor cones, occupancy memory, landmarks, route planning and diagnostics. |
| [Procedural and realistic creatures](tools-guides/creatures.md) | Creature morphology, gait, speech and optional cached realist pipelines. |
| [Clippy character](tools-guides/clippy.md) | Paperclip morphs, named performances and deterministic animation. |
| [Books and PDFs](tools-guides/books.md) | Hardcover rigs, cover art, scanned spreads, PDF pages and page turns. |
| [Character damage and dismemberment](tools-guides/destruction.md) | Per-limb damage, authored cut sites, detached pieces and blood effects. |
| [Modular robotics and manufacturing](tools-guides/robotics.md) | Individual parts, attachment ports, robot assemblies, motion, IK, G430 FDM/CNC and inspector. |
| [Procedural geometry](tools-guides/geometry.md) | Parametric surfaces, lofts, booleans, curve deformation and rhombic voxels. |
| [Terrain and surface materials](tools-guides/terrain-surfaces.md) | Heightfields, PBR generators, surface layers, UV density and parallax relief. |
| [Vegetation and trees](tools-guides/vegetation.md) | Instanced foliage, species, planting, wind, pushers and SeedThree trees. |
| [Sky, celestial worlds and weather](tools-guides/sky-weather.md) | Whole sky packages, time of day, clouds, rain, lightning, reflections, weather audio and the sun corona. |
| [Shallow water and 2D fluids](tools-guides/liquids.md) | Terrain water, pours, erosion, ocean surfaces, ink and dye. |
| [Free-surface water](tools-guides/free-surface-water.md) | 3D water volumes, emitters, static and moving colliders. |
| [Volumetric fire](tools-guides/volume-fire.md) | Burning mesh emitters, GPU smoke/fire simulation and its compositor. |
| [Cloth](tools-guides/cloth.md) | Fabric panels, pinning, wind, collisions and settling. |
| [Particles and morphing](tools-guides/particles-fx.md) | Sprite effects and mesh/text/point-cloud transitions. |
| [SDFs and isosurfaces](tools-guides/sdf-volumes.md) | Placeable raymarched surfaces, volume effects and voxel scalar fields. |
| [Post-processing effects](tools-guides/postprocessing.md) | Effect registry, parameters, animated uniforms, compositing and the era looks (print, CRT, film and paint). |
| [Motion graphics, screens and text](tools-guides/motion-graphics.md) | Titles, subtitles, overlays, screen UI, computing-history screen scenes, video atlases and 3D type. |
| [Cameras and lighting](tools-guides/camera-lighting.md) | Framing, safe camera travel, focus targets, shadows and physical lighting. |
| [Placement and assembly checks](tools-guides/placement.md) | Contact, scale, orientation, vehicle paths, clipping, hovering and z-fighting. |
| [Render review and sharing](tools-guides/render-review.md) | Preflight, probes, image/video/audio review, audit reports, contact sheets and discussing the result. |
| [Renderer troubleshooting](tools-guides/stack-notes.md) | WebGPU/TSL limitations, texture orientation, transparency and encoding. |
| [Toolkit maintenance](tools-guides/development.md) | Helper registration, dependencies, examples, tests and maintaining this guide index. |

## Native commands and starting points

```bash
python eido.py doctor
python eido.py bootstrap
python eido.py render work/<id>/scene.json --probe
python eido.py render work/<id>/scene.json --at 40 --at 72.5   # frames mid-piece, as PNGs
python eido.py render work/<id>/scene.json
```

Setup and dependency versions: [docs/SETUP.md](docs/SETUP.md).
Interactive workflow: [docs/HARNESS_MODE.md](docs/HARNESS_MODE.md).
Engine structure: [eidoverse/README.md](eidoverse/README.md).
Public examples: [eidoverse/examples/](eidoverse/examples/).

For modular robot assembly, start with [robotics](tools-guides/robotics.md): load
catalog modules or named parts, connect declared ports, then select motion.
The G430 FDM/CNC simulations use that same kit. The replaced primitive robot
builders are not available APIs. The independent VRM navigation stack remains
available through [characters](tools-guides/characters.md) and
[navigation](tools-guides/navigation.md).
