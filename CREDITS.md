# Credits & inspirations

Eidoverse is an original toolkit. Where a module's design drew on published
work or public references, it's acknowledged here. The bundled asset
library (models, VRMs, textures) is a mix of original handmade and AI
generated work by the maintainer, released with the repo; the particle
sprites are the Kenney Particle Pack (kenney.nl, CC0).

## Engine & libraries (dependencies, not derivations)

- **three.js** (MIT) — rendering, TSL, WebGPU backend, addons.
- **@pixiv/three-vrm** (MIT) — VRM loading, MToon, VRM animation.
- **@dimforge/rapier3d-compat** (Apache-2.0) — physics.
- **Deno** runtime + **wgpu** WebGPU implementation.
- **Satori** (MPL-2.0) + **resvg** — HTML/CSS → texture rasterization.
- **@napi-rs/canvas** — canvas-2D in Deno.

## Design inspirations (behavior studied; implementations original)

- **Character locomotion + foot IK** (`character_controller.js`,
  `foot_ik.js`) — informed by studying the conventions of several published
  character-controller and foot-placement systems (kinematic
  character controllers, raycast foot-planting IK, rate-capped pelvis
  adjustment) across engines. The implementation here is written from
  scratch for the three.js + Rapier + VRM stack.
- **`loft.js`** — the cross-section-skinning approach follows the loft
  geometry technique discussed in the three.js community (see three.js
  PR #33776 for a related exploration); this implementation targets the
  TSL/WebGPU pipeline and adds the sweep/taper/twist authoring layer.
- **`effects_tsl/volumetric_clouds.js`** — the atmosphere model follows
  published physically-based sky/cloud rendering techniques (spherical-
  shell atmosphere, FBM-eroded weather fields, multi-scale Beer's law,
  a numerical Mie phase fit, and Sébastien Hillaire's energy-conserving
  radiance accumulation), with public sky-rendering demos — including
  clayjohn's sky demos — used as visual
  references during tuning.
- **`effects_tsl/rain_on_camera.js`** — screen-space lens-droplet rain in
  beading, drift and streaks on the lens, built in TSL.
- **`effects_tsl/*`** generally — the catalog reimplements classic
  post-processing looks (CRT, VHS, halftone, cross-hatch, kaleidoscope, …)
  as TSL node graphs.
- **`parallax_material.js`** (silhouette POM with self-shadowing + curved-
  surface clipping) — the ray-march core is the *Silhouette Parallax
  Occlusion Mapping for three.js (WebGPU/TSL)* contribution by SkyeShark
  (MIT), adapted to the eidoverse eval-injection model and three 0.184.
  Submitted upstream to three.js as a contribution candidate.

## Assets

- Fetched-at-runtime assets come from **Poly Haven** (CC0), **AmbientCG**
  (CC0), the **Smithsonian Open Access** program, **NASA**, and **NIH 3D**
  — each fetcher reports its source; check each item's license before
  redistribution.
- The bundled `eidoverse/assets/` library (characters, props, animations)
  is a mix of original handmade and AI generated work by the maintainer,
  released with the repo. Particle sprites: Kenney Particle Pack
  (kenney.nl, CC0).
