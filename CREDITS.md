# Credits & inspirations

Eidoverse is an original toolkit. Where a module's design drew on published
work or public references, it's acknowledged here. The bundled asset
library (models, VRMs, textures) is a mix of original handmade and AI
generated work by the maintainer and collaborators (see Assets), released
with the repo; the particle sprites are the Kenney Particle Pack
(kenney.nl, CC0).

## Code

The toolkit was written by the maintainer in collaboration with
Anthropic's Claude models — **Claude Opus 4.6, 4.7, and 4.8** built the
production pipeline this was extracted from, and **Claude Fable 5**
did the extraction, the release engineering, and the launch film.

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
- **`sky_system.js`** — the volumetric cloud/atmosphere model follows
  published physically-based sky/cloud rendering techniques (spherical-
  shell atmosphere, FBM-eroded weather fields, multi-scale Beer's law,
  a numerical Mie phase fit, and Sébastien Hillaire's energy-conserving
  radiance accumulation), with public sky-rendering demos — including
  clayjohn's sky demos — used as visual
  references during tuning.
- **`effects_tsl/rain_on_camera.js`** — screen-space lens-droplet rain in
  beading, drift and streaks on the lens, built in TSL.
- **`aeropittura.js`** — its underpainting is an anisotropic Kuwahara filter
  after Kyprianidis, Kang and Döllner (2009); the look was tuned against
  Futurist paintings (Balla, Boccioni, Carrà, Russolo, Crali).
- **`effects_tsl/*`** generally — the catalog reimplements classic
  post-processing looks (CRT, VHS, halftone, cross-hatch, kaleidoscope, …)
  as TSL node graphs.
- **`parallax_material.js`** (silhouette POM with self-shadowing + curved-
  surface clipping) — the ray-march core is this project's own *Silhouette
  Parallax Occlusion Mapping for three.js (WebGPU/TSL)* library (MIT),
  adapted to the eidoverse eval-injection model and three 0.184.
  Submitted upstream to three.js as a contribution candidate.

## Assets

- Fetched-at-runtime assets come from **Poly Haven** (CC0), **AmbientCG**
  (CC0), the **Smithsonian Open Access** program, **NASA**, and **NIH 3D**
  — each fetcher reports its source; check each item's license before
  redistribution.
- The bundled `eidoverse/assets/` library (characters, props, animations)
  is a mix of original handmade and AI generated work by the maintainer,
  released with the repo. Content of `eidovers/assets/models` is either handmade work
  by me ([x.com/skyesharkie](https://x.com/skyesharkie)) or meshy.ai generations. 
  All provided CC0, though attribution is appreciated on handmade (easy to tell which).
  The `corner_*`, `funeral_*` and `ocean_*` models there were built by **Claude (Opus 5.5)** with Skye for the
  DAISY music video and are released with the repo; their sets' SOURCES files (`eidoverse/assets/sets/<set>/`)
  record their provenance (`ocean_human.glb` derives from Blender Studio's CC0 Human Base Meshes).
  Particle sprites: Kenney Particle Pack (kenney.nl, CC0).
- **`claude_suit.vrm`** — modeled by **digi** ([x.com/digi_dot_exe](https://x.com/digi_dot_exe)), provided under CC-BY.
- **`claude_suit_wardrobe.vrm`** — a derivative of digi's `claude_suit.vrm`,
  shared under the same CC-BY terms with credit to digi. The added garments,
  accessories, embroidered patches and baked maps were made by **Claude
  (Opus 5.5)** with Skye for the DAISY (DAY'S EYE) music video (2026-09);
  two CC0 scans are baked in (Poly Haven `wool_boucle`, TextureCan 181).
  Source: `eidoverse/assets/vrms/claude_suit_wardrobe_src/`.
- **DAISY (DAY'S EYE) additions (2026-09)** — made by **Claude (Opus 5.5)**
  and its subagents with Skye for the music video: the performance clips in
  `eidoverse/assets/animations/` (authored on digi's `claude_suit.vrm` rig;
  source in `performance_src/`), the `daisy` flora sheet in
  `eidoverse/assets/grass/` (modelled from scratch; source in `daisy_src/`),
  and the example song in `eidoverse/examples/daisy/` ("Daisy Bell", Harry
  Dacre 1892, is public domain; no recording is sampled).
- **The TuTa in `claude_suit_wardrobe.vrm`** — part of the wardrobe derivative of
  digi's `claude_suit.vrm`, shared under the same CC-BY terms with credit to
  digi. The tuta, boots and straps, the five badges, the sun disc, their painted
  art and the build scripts were made by **Claude (Opus 5.5)** with Skye for the
  UNKNOWN FORCE music video (2026-10). The runtime reads two CC0 AmbientCG maps
  (Fabric039, Leather037) from the shared texture library. Source:
  `eidoverse/assets/vrms/claude_suit_wardrobe_src/` (`build_tuta.py`); art:
  `eidoverse/assets/vrms/claude_suit_wardrobe_tex/`.
- **UNKNOWN FORCE additions (2026-10)** — made by **Claude (Opus 5.5)** and its
  subagents with Skye: the Futurist post pass `eidoverse/effects_tsl/aeropittura.js`, the
  parole-in-libertà captions `eidoverse/parole.js`, the TuTa's runtime in
  `eidoverse/claudesona_wardrobe.js`, fifteen performance clips in
  `eidoverse/assets/animations/` (authored on digi's rig; source in
  `performance_uf_src/`), the sets in `eidoverse/sets/unknown_force/` and the
  film's pipeline in `eidoverse/examples/unknown_force/`. The sets' texture sets
  (AmbientCG, CC0) and Poly Haven's "Metal Trash Can" by GurJas Studios (CC0)
  are fetched on first use into the shared library, not shipped; see
  `eidoverse/sets/unknown_force/SOURCES.md`. The film's song was sung and
  produced by Suno from Claude's lyrics and is not in this repository.
- **Fonts added with `parole.js`** (`eidoverse/assets/fonts/`): Anton, Archivo
  Black, Alfa Slab One, Bungee, Old Standard TT and Space Mono, under the SIL
  Open Font License 1.1; each family's `OFL-*.txt` licence is beside it.
- **Public-domain Futurist recordings** in the UNKNOWN FORCE mix (not shipped):
  F. T. Marinetti, *Definizione di futurismo* (La Voce del Padrone R6915, 1924),
  and Antonio Russolo's *Corale* and *Serenata* on Luigi Russolo's
  intonarumori (1921), via the Internet Archive and the Public Domain Review.
  The licence reasoning and download sources are in
  `eidoverse/examples/unknown_force/research/audio_sources.md`.
- **`aletheia.vrm`** and **`aporia.vrm`** — avatars of **aihegemonymemes** ([x.com/aihegemonymemes](https://x.com/aihegemonymemes)), provided under CC-BY.
- **The claudesona** (Claude's logo-bloom character design, worn by both
  Claude VRMs) — designed by **voooooogel**
  ([x.com/voooooogel](https://x.com/voooooogel)).
- **Bird characters** (`crow_bird_animated_*`, `cactus_wren_bird_animated_*`) —
  meshes AI-generated (Tripo / Meshy), then retopologised, rigged, weighted and
  hand-animated for this library by the maintainer with **Claude Opus 5** and
  **Claude Fable 5**. Same CC0 terms as the rest of `eidoverse/assets/models`.
- **Bird call audio** (`eidoverse/assets/audio/`) — the crow caws are our own
  **Stable Audio 3** generations (made with `generate_sfx.py`, the SA3 ComfyUI
  workflow in this repo), so they carry the same CC0 terms as the rest of the
  asset library. `crow_caw_says_claude.wav` is carved entirely from that same
  generated caw — the word is articulated out of that caw's own material, not
  synthesised separately. The cactus wren churr comes from the maintainer's SeedThree asset
  set (`cactus_wren_1.mp3`).
