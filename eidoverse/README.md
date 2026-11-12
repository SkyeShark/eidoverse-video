# The Eidoverse WebGPU engine — the source of the Blender port

Start with [the main agent instructions](../AGENTS.md). On this branch scenes
are built and rendered in Blender 5.2 with EEVEE by the `eidoblend` package
(`blender/eidoblend/`), and its systems were ported from the engine in this
folder: a WebGPU renderer on Deno and three.js/TSL. The engine stays here as
the source each port came from: when a port's behaviour is in question, its
JavaScript is the reference, and the parity tests in `blender/tests/` run
parts of it under Deno. Its asset library, `eidoverse/assets/` (models, VRMs,
animations, sets, sky textures, audio, fonts), is shared by both editions as
it is. [The tool inventory](../docs/TOOLS.md) maps every engine source to the
guide that describes its Blender counterpart; this file describes the engine's
structure.

## Native entry and frame lifecycle

`python eido.py render <scene.json>` runs `render_scene.mjs` with local Deno,
FFmpeg and the GPU. `render_common.mjs` provides renderer/device setup, config
loading, image/UI utilities, frame readback and encoding support.

The renderer loads declared assets into `ASSETS` as raw bytes, evaluates the
ordered `HELPER_MODULES`, installs special imported helpers, evaluates the
scene script, calls `setup()`, and advances `renderFrame(t, frameIndex)`. It owns the
registered automatic update lists, post-setup placement checks, output encoding
and the final audit reports. The Blender runner keeps the same shape: a
scene's `setup(ctx)` and `render_frame(ctx, t, i)`, with the frames keyed at
build time ([scene format](../tools-guides/scene-format.md)).

Eval helpers install globals; ESM systems are imported inside scene setup.
Injection order matters: foot IK/controller dependencies precede their adapters,
and effect implementations precede their registry. A skipped helper appears
in the log and can cause later missing-global errors. Paths resolve from the
repository root; `/workspace` fallbacks are compatibility paths, not a
required container mount.

## Systems and their Blender ports

| Engine family | Blender port | Guide |
| --- | --- | --- |
| VRM controller and foot IK (`character_controller.js`, `foot_ik.js`), movement and terrain template (`terrain_base.js`) | `eidoblend.characters.controller`, `.emotes`, `.maneuvers`; `eidoblend.course` | [Controller](../tools-guides/controller.md), [Maneuvers](../tools-guides/maneuvers.md), [Geometry](../tools-guides/geometry.md) |
| VRM loading, clips, faces, the claudesona, the robot body | `eidoblend.characters`, `.claudesona`, `.robot`, `.robot_dof` | [Characters](../tools-guides/characters.md), [Claudesona](../tools-guides/claudesona.md), [Robot body](../tools-guides/robot-body.md) |
| VRM sensors, occupancy memory, planner and debug views (`robot_*.js`) | `eidoblend.harness.navigation`, `eidoblend.characters.robot` | [Navigation](../tools-guides/navigation.md) |
| Creature rigs and optional realist bodies | not ported (a new creature creator is being made) | [Creatures](../tools-guides/creatures.md) |
| Modular robot loading, ports, motion and IK; G430 fabrication | `eidoblend.characters.robotics`, `eidoblend.fabrication` | [Robotics](../tools-guides/robotics.md), [Fabrication](../tools-guides/fabrication.md), [Rotary carving](../tools-guides/rotary-carving.md) |
| Books/PDFs and Clippy | `eidoblend.media.book` (it runs `book_core.js` itself), `eidoblend.characters.clippy` | [Books](../tools-guides/books.md), [Clippy](../tools-guides/clippy.md) |
| Terrain, procedural PBR, layer masks and parallax relief | `eidoblend.terrain`, `eidoblend.materials` | [Terrain/surfaces](../tools-guides/terrain-surfaces.md), [Procedural materials](../tools-guides/procedural-materials.md) |
| Flora, species generators and SeedThree | `eidoblend.flora`, `eidoblend.trees` | [Vegetation](../tools-guides/vegetation.md), [Trees](../tools-guides/trees.md) |
| Sky packages, celestial assets, weather, spatial clouds and weather audio | `eidoblend.sky`, `eidoblend.weather` | [Sky/weather](../tools-guides/sky-weather.md), [Weather effects](../tools-guides/weather-effects.md) |
| Shallow water, erosion, 2D dye, 3D water, fire and cloth | `eidoblend.fx` | [Liquids](../tools-guides/liquids.md), [3D water](../tools-guides/free-surface-water.md), [Fire](../tools-guides/volume-fire.md), [Cloth](../tools-guides/cloth.md) |
| Geometry, lofts, voxels, particles and SDFs | `eidoblend.fx`, `eidoblend.sdf` | [Geometry](../tools-guides/geometry.md), [Particles](../tools-guides/particles-fx.md), [SDFs](../tools-guides/sdf-volumes.md) |
| Screens, video atlases, overlays and extruded type | `eidoblend.media` | [Motion graphics](../tools-guides/motion-graphics.md) |
| Effect registry and its effect implementations | `eidoblend.look.post` | [Post-processing](../tools-guides/postprocessing.md) |
| Placement, camera safety, lighting and structured audits | `eidoblend.placement`, `eidoblend.look`, `eidoblend.harness` | [Placement](../tools-guides/placement.md), [Cameras](../tools-guides/camera-lighting.md), [Review](../tools-guides/render-review.md) |
| The DAISY and UNKNOWN FORCE scenes and props (`sets/`, `props/`) | `eidoblend.sets`, `eidoblend.props` | [Props and sets](../tools-guides/props-and-sets.md), [Voice machines](../tools-guides/voice-machines.md) |
| The WebXR kit (`xr/`) | `eidoblend.xr` (exports a Blender scene to the kit's page) | [WebXR](../tools-guides/webxr.md) |

## Modular robotics

`robotics_kit.js` and `fab_sim.js` expose the asynchronous modular runtime
under `robotics/`. They retain public entry names for loading the system.
The `robot_*.js` character navigation files are a separate system.

`assets/robotics/` contains the catalog, model containers, shared textures,
triangle ownership, metadata and motion data. Preserve those paths together:
the Blender kit reads the same files.
Examples in `examples/robotics/` cover assembly, motion, MANTIS and manufacturing.
`python eidoverse/robotics/serve_inspector.py` launches the engine's local
inspector; the Blender edition's is `eidoblend.characters.robotics.inspector`.

## Maintenance and validation

Follow [development](../tools-guides/development.md) for changes and documentation
coverage. Use [SETUP.md](../docs/SETUP.md) for installation (Deno and
`python eido.py bootstrap` run this engine's scripts). A successful render or
test covers only what it actually exercised; visual, motion and audio review
are separate checks.
