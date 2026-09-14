# Eidoverse engine — maintainer map

Start with [the main agent instructions](../AGENTS.md). Scene-facing API
recipes are in its linked `tools-guides/*.md` guides. [The tool inventory](../docs/TOOLS.md)
maps every first-party source/tool to a guide; this file describes engine structure.

## Native entry and frame lifecycle

`python eido.py render <scene.json>` runs `render_scene.mjs` with local Deno,
FFmpeg and the GPU. `render_common.mjs` provides renderer/device setup, config
loading, image/UI utilities, frame readback and encoding support.

The renderer loads declared assets into `ASSETS` as raw bytes, evaluates the
ordered `HELPER_MODULES`, installs special imported helpers, evaluates the
scene script, calls `setup()`, and advances `renderFrame(t, frameIndex)`. It owns the
registered automatic update lists, post-setup placement checks, output encoding
and the final audit reports. See [scene format](../tools-guides/scene-format.md).

Eval helpers install globals; ESM systems are imported inside scene setup.
Injection order matters: foot IK/controller dependencies precede their adapters,
and effect implementations precede their registry. A skipped helper appears
in the log and can cause later missing-global errors. Paths resolve from the
repository root in this native edition; `/workspace` fallbacks are compatibility
paths, not a required container mount.

## System families

| Family | Guide |
| --- | --- |
| VRM controller, foot IK, movement and terrain template | [Characters](../tools-guides/characters.md) |
| VRM sensors, occupancy memory, planner and debug views | [Navigation](../tools-guides/navigation.md) |
| Creature rigs and optional realist bodies | [Creatures](../tools-guides/creatures.md) |
| Modular robot loading, ports, motion, IK and G430 fabrication | [Robotics](../tools-guides/robotics.md) |
| Books/PDFs and Clippy | [Books](../tools-guides/books.md), [Clippy](../tools-guides/clippy.md) |
| Limb damage and dismemberment | [Destruction](../tools-guides/destruction.md) |
| Terrain, procedural PBR, layer masks and parallax relief | [Terrain/surfaces](../tools-guides/terrain-surfaces.md) |
| Flora, species generators and SeedThree | [Vegetation](../tools-guides/vegetation.md) |
| Sky packages, celestial assets, weather, spatial clouds and weather audio | [Sky/weather](../tools-guides/sky-weather.md) |
| Shallow water, erosion, 2D dye, 3D water, fire and cloth | [Liquids](../tools-guides/liquids.md), [3D water](../tools-guides/free-surface-water.md), [Fire](../tools-guides/volume-fire.md), [Cloth](../tools-guides/cloth.md) |
| Geometry, lofts, voxels, particles and SDFs | [Geometry](../tools-guides/geometry.md), [Particles](../tools-guides/particles-fx.md), [SDFs](../tools-guides/sdf-volumes.md) |
| Screens, video atlases, Satori, overlays and extruded type | [Motion graphics](../tools-guides/motion-graphics.md) |
| Effect registry and 31 effect implementations | [Post-processing](../tools-guides/postprocessing.md) |
| Placement, camera safety, lighting and structured audits | [Placement](../tools-guides/placement.md), [Cameras](../tools-guides/camera-lighting.md), [Review](../tools-guides/render-review.md) |

## Modular robotics replacement

`robotics_kit.js` and `fab_sim.js` now expose the asynchronous modular runtime
under `robotics/`. They retain public entry names for loading the new system;
their old primitive constructors and mesh-reveal simulation implementations
are replaced. `mech_parts.js` is removed from the active tree and helper list.
The `robot_*.js` character navigation files are a separate system and remain.

`assets/robotics/` contains the catalog, model containers, shared textures,
triangle ownership, metadata and motion data. Preserve those paths together.
Examples in `examples/robotics/` cover assembly, motion, MANTIS and manufacturing.
`python eidoverse/robotics/serve_inspector.py` launches the local inspector.
Old implementations remain recoverable from Git history; ignored `work/`
archives are local preservation copies, not active modules or commit payloads.

## Maintenance and validation

Follow [development](../tools-guides/development.md) for changes and documentation
coverage. [Stack notes](../tools-guides/stack-notes.md) explain native renderer limits.
Use [SETUP.md](../docs/SETUP.md) for installation and the included examples for
probes. A successful render/test covers only what it actually exercised;
visual, motion and audio review are separate checks.
