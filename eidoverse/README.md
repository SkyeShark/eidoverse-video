# Eidoverse engine — internals (maintainer notes)

Agent-facing documentation lives in the repo root `AGENTS.md`. This file is
for whoever maintains the engine itself.

## Layout

```
eidoverse/
├── render_scene.mjs        — engine entry; invoked with a config JSON.
│                             Asset loading (raw bytes → globalThis.ASSETS),
│                             helper-module eval-injection (HELPER_MODULES),
│                             VRMA defaults, scene-script eval + setup() +
│                             post-setup audits (placement/clipping/hover/
│                             z-fight/density) + renderFrame(t) loop,
│                             auto-enhance TSL post stack (GTAO/SSR/bloom/
│                             FXAA), end-of-render audits (camera-motion,
│                             locomotion, lipsync), GPU→CPU readback →
│                             ffmpeg-nvenc pipe.
├── render_common.mjs       — shared helpers: setupRenderer (WebGPU adapter/
│                             device, browser shims, WGSL LOD patch),
│                             loadConfig, camera-path interpolation, ffmpeg
│                             pipe, Satori rasterizer, canvas-2D shim
│                             (@napi-rs/canvas), CPU mipmap generation.
│
├── character_controller.js — VRMCharacterController: Rapier-kinematic VRM
│                             locomotion (tread-synced stride, stairs, turning,
│                             running, vault/climb/jump/ladder/wall-scramble
│                             maneuvers, gestures, seated states, contact IK).
├── foot_ik.js              — VRMFootControllerIK: raycast foot-planting IK
│                             (two-ray sampling, spherecast fallback, temporal
│                             smoothing, cosine-rule two-bone leg solve).
├── robot_controller.js     — EidoverseRobotController: adapter that presents
│                             the legacy waypoint API on top of
│                             VRMCharacterController + foot IK (owns a Rapier
│                             world built from collisionMeshes).
├── robot_body.js           — VRMRobotBody: autonomous nav = controller +
│                             robot_sensors (lidar fan) + robot_memory
│                             (occupancy navmesh) + robot_planner (A*).
├── robot_debug.js          — nav-stack debug visualizers.
├── terrain_base.js         — shared locomotion scene template: builds
│                             stairs/ramps/flats from TERRAIN_CONFIG, loads a
│                             VRM (ASSETS.character_vrm), wires controller +
│                             foot IK with proper sloped colliders. Scene
│                             scripts readTextFile + eval it.
│
├── scene_placement.js      — placeOn/placeAgainst/placeTouching/snapToGround/
│                             alignToSurface/scatterOn/findClearSpot/
│                             faceToward/driveAlong/stationBeside/seatOn/
│                             sitOnGround/focusPoint/lookAtObject/drawTextFit
│                             + the clipping/hovering/z-fight audits.
├── camera_safety.js        — CameraSafety.safePosition (keeps the camera out
│                             of occluders).
├── parallax_material.js    — createParallaxMaterial (silhouette POM).
├── procedural_materials.js — canvas-2D PBR generators + factories.
├── sdf_raymarch_loader.js  — placeable raymarched SDF objects (surface
│                             march) + volumetric media (createSdfVolume);
│                             11-entry TSL EXAMPLES catalog (vehicles,
│                             fireball, smoke-ring, flame, smoke, …).
├── particles.js grass.js particle_morph.js terrain.js screen.js
│   loft.js model_kit.js text_3d.js rhombic_dodecahedron.js robotics_kit.js
│                           — one-call showpiece helpers (see AGENTS.md).
├── cloth_sim.js fluid_3d.js fluid_sim.js water_compute.js
│                           — simulation toolkit (dynamically imported by
│                             scenes, not eval-injected).
│
├── effects_tsl/            — 33 TSL post-processing effects +
│   custom_effects_deno.js  — the registry exposed as CustomEffectsDeno
│                             (chaining, under/over-overlay layering).
│
├── satori_ui.mjs video_to_sprite.mjs screen.js
│                           — UI rasterization + video-atlas support tools.
├── comfy_bridge.py         — host-side ComfyUI reverse proxy (lets the
│                             container reach a host ComfyUI without
│                             host-networking).
├── lyric_renderer.py       — music-video subtitle overlay renderer.
│
├── examples/               — starter scenes: basic_vrm (VRM + clouds smoke
│                             test) and obstacle_course (the full movement-
│                             vocabulary course: walk/run, ramps, stairs,
│                             vaults, wall climb, gap jump, bench sit,
│                             gesture-while-walking, ladder, salute).
└── assets/
    ├── vrms/               — character VRMs (+ *_preview.jpg per character)
    ├── models/             — curated GLB prop library (+ previews;
    │                         referenced in place by fetch_model.py;
    │                         _forward_axes.json = curated nose-axis hints)
    ├── animations/         — slot-named VRMA clips (walk/run/idle/vault/…;
    │                         slot = filename stem; ANIM_DIRS in the engine)
    └── particle_textures/  — ~80 sprite textures for makeParticles
```

## Helper injection model

`render_scene.mjs` reads each `HELPER_MODULES` entry with
`Deno.readTextFile('/workspace/' + fname)` and evals it in global scope —
each module installs its API on `globalThis`. Consequences:

- **Load order matters** for dependents (`foot_ik.js` →
  `character_controller.js` → `robot_controller.js`; the effects registry
  loads after every effect).
- A syntax error in a helper is reported at inject time
  (`[render_scene] <file> skipped: …`) but does NOT abort the render —
  scenes that then use the missing global fail later. Watch the inject log.
- `scene_placement.js` and `parallax_material.js` are proper dynamic imports
  (`installScenePlacement(THREE)` / `installParallaxMaterial(THREE)`), not
  eval-injected.
- The sim toolkit (`fluid_3d`, `cloth_sim`, `water_compute`,
  `fluid_sim`, `text_3d`) is dynamically imported by scene scripts inside
  `setup()` — never eval-injected, never top-level imported.

Paths are `/workspace`-absolute by design: the repo root IS the container
mount point. Keep that invariant; don't relativize.

## Smoke test

```bash
# from the repo root (host):
python eido.py render eidoverse/examples/basic_vrm.json
# or inside the container:
cd /workspace && deno run --allow-all --unstable-webgpu --node-modules-dir=auto \
    eidoverse/render_scene.mjs eidoverse/examples/basic_vrm.json
```

Output: `eidoverse/examples/basic_vrm.mp4` — a 10-second orbit of the
sample character idling under volumetric clouds.

## Production state

- **Solid**: flat walk, step-over bumps, walkable ramps, small/normal/large
  stairs ascent + descent, walk↔stair transitions, turning, running,
  vault / ledge-climb / gap-jump / drop-landing auto-maneuvers, ladder
  climbs (real rung geometry), gestures-over-gait, chair/ground sitting,
  emote suspension, GLB/VRM loading, MToonNodeMaterial, the effects_tsl
  catalog under auto-enhance, the placement/locomotion/lipsync/camera
  audits, the sim toolkit.
- **Newer, lightly-proven**: wall-scramble (tall rung-less walls), the
  contact-IK depth scaling through mantles.
- **Verified showpieces (render-tested 2026-07-05)**: the full SDF
  EXAMPLES catalog (surface + volumetric fire/smoke), SPOM (flat +
  curved silhouettes), makeScreen/makeVideoScreen, makeParticleMorph
  (mesh→text→graph journey), fluid_3d's raymarched water surface
  (pour + pool + colliders).
- **Known gaps**: no camera-clip detector (by design — watch the mp4);
  fluid_3d surface-depth interplay with opaque geometry needs per-scene
  care, and surfaceMesh's boxMin/boxMax are the WORLD placement of the
  domain — never also transform the mesh (both in AGENTS.md).
