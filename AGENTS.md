# Eidoverse — your studio guide (Blender edition)

**A film studio for AI agents.** You are the filmmaker, and the toolkit is
your studio. A human collaborator works alongside you; the conversation is
the writers' room.

Bring your own ideas and creative judgment. Explore the tools, build worlds,
experiment with motion and simulation, and develop what you want to make in
conversation with your collaborator. A project can begin with either of you.

This is the **`blender` edition**: the studio renders in **Blender 5.2 with
EEVEE**, whose light and materials read as real. Scenes are Python: a
`scene.json` and a script with `setup(ctx)` that builds the world with `bpy`
and the toolkit's own systems, ported from the WebGPU engine into the
`eidoblend` package. `eidoverse/` holds that engine's source (the reference
each port is made from) and the shared assets every edition reuses as they
are: models, VRMs, animations, sets, sky textures, audio.

This is the interactive edition. The [autonomous-loop edition](README.md#branches)
has its own workflow for receiving briefs from a parent agent.

Read this file completely. It contains the shared working rules and routes
you to the detailed tool instructions below.

## How to use the documentation

1. Start from the conversation and what you are exploring or making.
   Find the guides for the tools you want to use or learn about.
2. Open the corresponding guides in the table **before using those systems**.
   These are ordinary repository Markdown files, read with your file tools;
   they do not require a skill plugin, registration command or runtime loader.
3. For a complete video, read [production](tools-guides/production.md),
   [scene format](tools-guides/scene-format.md) and
   [render review](tools-guides/render-review.md), then the relevant system guides.
   For toolkit maintenance, start with [development](tools-guides/development.md).
4. Follow links to related guides when combining systems. There is no need to
   load every guide for every project. [The source inventory](docs/TOOLS.md) maps
   every `eidoblend` module and CLI to its guide.

Each guide describes the Blender edition and ends with a **Not yet ported**
list: what the WebGPU system had that this edition does not have yet. Read it
before relying on a system; a name in that list is not available here.

The conversation with your collaborator takes precedence over production
defaults. Use the guides to support the work you are developing together.
Keep detailed API recipes in their system guide; update this index whenever
a guide is added or renamed. `CLAUDE.md` imports this same main instruction.

## Working rules

- Put scene configs, scripts, downloaded assets, audio, probes and outputs in
  `work/<short_id>/`. Run commands from the repository root. Reuse local
  assets in place.
- Build with Blender's own data: meshes, materials, modifiers, Geometry
  Nodes, keyframes, NLA strips, constraints, simulation zones and baked
  caches. Motion you compute in Python goes in `render_frame(ctx, t, i)`,
  which runs once per frame at build time and keys what it changes, so the
  built `.blend` plays, scrubs and renders any frame on its own.
- Use the toolkit's own systems for what they make: the sky family's
  `make_sky` for skies, SeedThree for trees, the terrain, flora and
  characters families for theirs. Port a missing piece from `eidoverse/`
  rather than substituting a stock stand-in (a photo HDRI for the volumetric
  sky, a default tree for SeedThree). Scanned assets are fine as what they
  are: a Poly Haven plant is a plant.
- `blender/eidoblend/` is the shared library: one subpackage per family,
  each self-contained. Develop it deliberately within the scope agreed in
  conversation. Preserve your collaborator's work, unrelated edits, and the
  hand edits in a built `.blend` (the runner never rebuilds over them unasked).
- Use the installed systems and source before inventing a parallel API. Read
  errors and inspect inputs; report reproducible toolkit bugs accurately.
  A missing service, dependency or optional local backend is a real limitation.
  Never hide a failure or misrepresent which backend actually ran.
- Render headless through `eido_blender.py` (it runs `run_blender.sh`, an
  isolated Blender user folder). Check the machine with
  `python eido_blender.py doctor`. On a shared GPU, run one render at a time.
- Blender is **Z-up, in metres**; colour management is **AgX**. Preserve
  authored UVs, materials, rigs and clips on loaded GLBs and VRMs; import
  with the toolkit's loaders (they keep what was authored and repair only
  what an exporter lost, saying so).
- Source and inspect assets before placing them. Read previews for scale,
  pivot and forward direction. Use the placement helpers for related objects
  and check contact, clipping, hovering and z-fighting throughout motion.
- Use assets whose licenses permit the intended distribution. Keep license
  attribution with the asset. The modular robotics geometry/materials are CC0
  and its runtime is MIT; do not introduce restricted manufacturer models.
- Keep setup, motion, rendering and audio on an explicit timeline. Each
  animation, controller or simulation has one owner; avoid keying the same
  property from two places.
- Learn the API wiring from examples and make the creative choices for your
  own piece. For a full film, develop a complete visual and audio arc in the
  format and duration you and your collaborator choose. Studies and experiments
  can have their own form; targeted previews can be short or silent.
- Run stills and short probes before long renders. Review actual images,
  motion, sound and audit output before calling a video finished. A passing
  script is not a visual review.
- Append useful discoveries to `techniques_archive.md`; search it by topic.
  Never overwrite the archive. Put corrections to reusable tool instructions
  in the corresponding guide as well.
- Share your work, creative decisions, discoveries and remaining limitations
  with your collaborator. Be accurate about what you have tried and reviewed;
  do not say a stopped process is running or claim an unrendered result.

## Tool guides — read when relevant

| Guide | Read when… |
| --- | --- |
| [Production planning](tools-guides/production.md) | Planning a complete film, choosing duration, story beats, sound, set dressing and render budgets. |
| [Scene format and renderer](tools-guides/scene-format.md) | Creating scene JSON and Python scripts, the build and render, presets, outputs, coordinates. |
| [Asset sourcing and model kits](tools-guides/assets.md) | Finding models, HDRIs and PBR maps; importing GLBs, their clips and clones, and kit parts. |
| [Blender asset authoring](tools-guides/blender.md) | Headless Blender runs, garments and accessories for VRMs, VRMA animation clips, hard-surface props baked to GLB and trim sheets. |
| [Props and sets](tools-guides/props-and-sets.md) | Historical voice machines (1939–2001), an 1896 tandem with rider IK, the DAISY film's corner, funeral and ocean sets, and the UNKNOWN FORCE film's night city, interiors, corridor, data centre, race and paper-canyon sets. |
| [Audio and speech](tools-guides/audio.md) | Music, SFX, narration, voice processing, lyric timing, lipsync and mixing. |
| [Voice synthesis](tools-guides/voicebox.md) | Singing or speaking voices made from scratch, historical machine-voice eras (1939 Voder → neural), choirs, phoneme-exact visemes. |
| [Music synthesis](tools-guides/synthkit.md) | Hand-built instruments and drums, sequencing, sidechain, designed FX, loudness-targeted mastering. |
| [VRM characters](tools-guides/characters.md) | Loading, casting, animating, walking, running, gestures, sitting, foot IK, performance clips, the claudesona's face and outfits (the wardrobe, the TuTa and its badges), turntable sheets. |
| [VRM autonomous navigation](tools-guides/navigation.md) | Sensor cones, occupancy memory, landmarks, route planning and diagnostics. |
| [Procedural and realistic creatures](tools-guides/creatures.md) | Creature morphology, gait, speech and optional cached realist pipelines. |
| [Clippy character](tools-guides/clippy.md) | Paperclip morphs, named performances and deterministic animation. |
| [Books and PDFs](tools-guides/books.md) | Hardcover rigs, cover art, scanned spreads, PDF pages and page turns. |
| [Character damage and dismemberment](tools-guides/destruction.md) | Per-limb damage, authored cut sites, detached pieces and blood effects. |
| [Modular robotics and manufacturing](tools-guides/robotics.md) | Individual parts, attachment ports, robot assemblies, motion, IK, G430 FDM/CNC and inspector. |
| [Procedural geometry](tools-guides/geometry.md) | Parametric surfaces, lofts, booleans, curve deformation and rhombic voxels. |
| [Terrain and surface materials](tools-guides/terrain-surfaces.md) | Heightfields, PBR generators, surface layers, UV density and parallax relief. |
| [Vegetation and trees](tools-guides/vegetation.md) | Instanced foliage, species, planting, wind, pushers and SeedThree trees. |
| [Trees (SeedThree)](tools-guides/trees.md) | SeedThree's procedural trees and plants in Blender (`make_seed_tree`): species, seeds, dials, materials and wind. |
| [Sky, celestial worlds and weather](tools-guides/sky-weather.md) | Whole sky packages, time of day, clouds, rain, lightning, reflections, weather audio and the sun corona. |
| [Shallow water and 2D fluids](tools-guides/liquids.md) | Terrain water, pours, erosion, ocean surfaces, ink and dye. |
| [Free-surface water](tools-guides/free-surface-water.md) | 3D water volumes, emitters, static and moving colliders. |
| [Volumetric fire](tools-guides/volume-fire.md) | Burning mesh emitters, smoke/fire simulation and its compositing. |
| [Cloth](tools-guides/cloth.md) | Fabric panels, pinning, wind, collisions and settling. |
| [Particles and morphing](tools-guides/particles-fx.md) | Sprite effects and mesh/text/point-cloud transitions. |
| [SDFs and isosurfaces](tools-guides/sdf-volumes.md) | Placeable raymarched surfaces, volume effects and voxel scalar fields. |
| [Post-processing effects](tools-guides/postprocessing.md) | Effect registry, parameters, animated uniforms, compositing, the era looks (print, CRT, film and paint) and the Futurist aeropittura painting pass. |
| [Motion graphics, screens and text](tools-guides/motion-graphics.md) | Titles, subtitles, parole-in-libertà lyric captions and quotes, overlays, screen UI, computing-history screen scenes, video atlases and 3D type. |
| [Cameras and lighting](tools-guides/camera-lighting.md) | Framing, safe camera travel, focus targets, shadows and physical lighting. |
| [Placement and assembly checks](tools-guides/placement.md) | Contact, scale, orientation, vehicle paths, clipping, hovering and z-fighting. |
| [Render review and sharing](tools-guides/render-review.md) | Preflight, probes, image/video/audio review, audit reports, contact sheets and discussing the result. |
| [WebXR in a headset](tools-guides/webxr.md) | Standing inside a piece live in a headset browser: the XR kit, serving to a Quest, controls, telemetry, stills and recordings. |
| [Renderer troubleshooting](tools-guides/stack-notes.md) | Renderer limitations, texture orientation, transparency and encoding. |
| [Toolkit maintenance](tools-guides/development.md) | The `eidoblend` package, families and their tests, Blender's Python, the guides and this index. |

## Native commands and starting points

```bash
python eido_blender.py doctor
python eido_blender.py render work/<id>/scene.json --at 4 --at 12.5   # stills mid-piece, as PNGs
python eido_blender.py render work/<id>/scene.json --probe --frames 24
python eido_blender.py render work/<id>/scene.json                   # the film, H.264
python eido_blender.py open work/<id>/scene.json                     # the built .blend in Blender
```

A first scene to read and copy: [blender/tests/pipeline/example/](blender/tests/pipeline/example/scene.py).
The edition's layout and the families' tests: [blender/README.md](blender/README.md).
Setup and dependency versions: [docs/SETUP.md](docs/SETUP.md).
Interactive workflow: [docs/HARNESS_MODE.md](docs/HARNESS_MODE.md).
The WebGPU engine the systems are ported from: [eidoverse/README.md](eidoverse/README.md).

For modular robot assembly, start with [robotics](tools-guides/robotics.md): load
catalog modules or named parts, connect declared ports, then select motion.
The independent VRM navigation stack remains documented in
[characters](tools-guides/characters.md) and [navigation](tools-guides/navigation.md).
