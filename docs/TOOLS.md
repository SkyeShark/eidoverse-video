# Tool and source inventory

[Main instructions](../AGENTS.md) list all 33 topic guides and when to read
them. This inventory maps every current first-party source file and entry point
to its guide, with loading/usage roles. A source can be a public tool, internal
support, an optional utility, an example or a test; file count is not tool count.

Coverage is checked against the source tree and the renderer's loading paths.
Guide coverage also requires usable entry-point instructions, not just a file
name in this table. Public globals and exported names were reviewed separately
to distinguish missing scene APIs from internal implementation functions.

| Source or tool | Role | Instructions |
| --- | --- | --- |
| [align_lyrics.py](../align_lyrics.py) | CLI utility | [audio](../tools-guides/audio.md) |
| [bake_weather_audio.py](../bake_weather_audio.py) | CLI utility | [sky-weather](../tools-guides/sky-weather.md) |
| [contact_sheet.py](../contact_sheet.py) | CLI utility: labelled contact sheets of a video | [render-review](../tools-guides/render-review.md) |
| [cyborg_stutter.py](../cyborg_stutter.py) | CLI utility | [audio](../tools-guides/audio.md) |
| [cyborg_voice.py](../cyborg_voice.py) | CLI utility | [audio](../tools-guides/audio.md) |
| [eido.py](../eido.py) | CLI utility | [scene-format](../tools-guides/scene-format.md) |
| [eidoverse/assets/animations/performance_src/](../eidoverse/assets/animations/performance_src/README.md) | Asset source: Blender VRMA authoring script + engine-free clip checker | [blender](../tools-guides/blender.md) |
| [eidoverse/assets/grass/daisy_src/](../eidoverse/assets/grass/daisy_src/README.md) | Asset source: Blender + Python scripts that build the daisy sheet | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/assets/models/tandem_1896_src/](../eidoverse/assets/models/tandem_1896_src/README.md) | Asset source: Blender scripts that built the tandem GLB | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/models/voice_machines_src/](../eidoverse/assets/models/voice_machines_src/README.md) | Asset source: Blender scripts that built the voice-machine GLBs | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/sets/corner_src/](../eidoverse/assets/sets/corner_src/README.md) | Asset source: Blender/PIL scripts that built the corner set | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/sets/funeral_src/](../eidoverse/assets/sets/funeral_src/README.md) | Asset source: Blender scripts that built the funeral set | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/sets/ocean_src/](../eidoverse/assets/sets/ocean_src/README.md) | Asset source: Blender scripts that built the ocean set | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/vrms/claude_suit_wardrobe_src/](../eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md) | Asset source: packed .blend, export script and garment recipes | [blender](../tools-guides/blender.md) |
| [eidoverse/asteroid_moon.js](../eidoverse/asteroid_moon.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/audit_core.js](../eidoverse/audit_core.js) | System support; see guide for entry point | [render-review](../tools-guides/render-review.md) |
| [eidoverse/audit_core_test.mjs](../eidoverse/audit_core_test.mjs) | Test suite | [development](../tools-guides/development.md) |
| [eidoverse/book.js](../eidoverse/book.js) | Injected scene API | [books](../tools-guides/books.md) |
| [eidoverse/book_core.js](../eidoverse/book_core.js) | System support; see guide for entry point | [books](../tools-guides/books.md) |
| [eidoverse/camera_safety.js](../eidoverse/camera_safety.js) | Injected scene API | [camera-lighting](../tools-guides/camera-lighting.md) |
| [eidoverse/character_controller.js](../eidoverse/character_controller.js) | Injected scene API | [characters](../tools-guides/characters.md) |
| [eidoverse/claudesona_face.js](../eidoverse/claudesona_face.js) | Dynamic ESM scene API | [characters](../tools-guides/characters.md) |
| [eidoverse/claudesona_wardrobe.js](../eidoverse/claudesona_wardrobe.js) | Dynamic ESM scene API | [characters](../tools-guides/characters.md) |
| [eidoverse/clippy.js](../eidoverse/clippy.js) | Injected scene API | [clippy](../tools-guides/clippy.md) |
| [eidoverse/cloth_sim.js](../eidoverse/cloth_sim.js) | Dynamic ESM scene API | [cloth](../tools-guides/cloth.md) |
| [eidoverse/cloud_spatial.js](../eidoverse/cloud_spatial.js) | Dynamic ESM scene API | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/comfy_bridge.py](../eidoverse/comfy_bridge.py) | Optional TCP bridge service | [audio](../tools-guides/audio.md) |
| [eidoverse/creature_builder.js](../eidoverse/creature_builder.js) | Injected scene API | [creatures](../tools-guides/creatures.md) |
| [eidoverse/creature_realist.js](../eidoverse/creature_realist.js) | Injected API with optional external backend | [creatures](../tools-guides/creatures.md) |
| [eidoverse/creature_specimen.js](../eidoverse/creature_specimen.js) | Injected API with optional external backend | [creatures](../tools-guides/creatures.md) |
| [eidoverse/dismember.js](../eidoverse/dismember.js) | Injected scene API | [destruction](../tools-guides/destruction.md) |
| [eidoverse/dismember_core.js](../eidoverse/dismember_core.js) | System support; see guide for entry point | [destruction](../tools-guides/destruction.md) |
| [eidoverse/dismember_core_test.mjs](../eidoverse/dismember_core_test.mjs) | Test suite | [development](../tools-guides/development.md) |
| [eidoverse/effects_tsl/after_image.js](../eidoverse/effects_tsl/after_image.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/anamorphic_flare.js](../eidoverse/effects_tsl/anamorphic_flare.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/bleach_bypass.js](../eidoverse/effects_tsl/bleach_bypass.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/blueprint.js](../eidoverse/effects_tsl/blueprint.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/box_blur.js](../eidoverse/effects_tsl/box_blur.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/bw_halftone.js](../eidoverse/effects_tsl/bw_halftone.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/chromatic_aberration_alpha.js](../eidoverse/effects_tsl/chromatic_aberration_alpha.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/cross_hatch.js](../eidoverse/effects_tsl/cross_hatch.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/crt.js](../eidoverse/effects_tsl/crt.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/custom_effects_deno.js](../eidoverse/effects_tsl/custom_effects_deno.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/depth_fog.js](../eidoverse/effects_tsl/depth_fog.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/dithering.js](../eidoverse/effects_tsl/dithering.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/focus_blur.js](../eidoverse/effects_tsl/focus_blur.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/full_toon.js](../eidoverse/effects_tsl/full_toon.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/glitch_bars.js](../eidoverse/effects_tsl/glitch_bars.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/godrays.js](../eidoverse/effects_tsl/godrays.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/hash_blur.js](../eidoverse/effects_tsl/hash_blur.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/jitter.js](../eidoverse/effects_tsl/jitter.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/kaleidoscope.js](../eidoverse/effects_tsl/kaleidoscope.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/lensflare.js](../eidoverse/effects_tsl/lensflare.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/melt.js](../eidoverse/effects_tsl/melt.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/neon_edges.js](../eidoverse/effects_tsl/neon_edges.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/nuclear_explosion.js](../eidoverse/effects_tsl/nuclear_explosion.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/old_bw_film.js](../eidoverse/effects_tsl/old_bw_film.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/radial_blur.js](../eidoverse/effects_tsl/radial_blur.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/rain_on_camera.js](../eidoverse/effects_tsl/rain_on_camera.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/retro_wireframe.js](../eidoverse/effects_tsl/retro_wireframe.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/rgb_shift.js](../eidoverse/effects_tsl/rgb_shift.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/sepia.js](../eidoverse/effects_tsl/sepia.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/underwater.js](../eidoverse/effects_tsl/underwater.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/vhs_tape.js](../eidoverse/effects_tsl/vhs_tape.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/wavy.js](../eidoverse/effects_tsl/wavy.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/era_looks.js](../eidoverse/era_looks.js) | Dynamic ESM; registers the `era_looks` effect | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/examples/basic_vrm.js](../eidoverse/examples/basic_vrm.js) | Scene example/template | [development](../tools-guides/development.md) |
| [eidoverse/examples/daisy/analyze.py](../eidoverse/examples/daisy/analyze.py) | Example CLI: section-by-section mix measurement | [synthkit](../tools-guides/synthkit.md) |
| [eidoverse/examples/daisy/captions.py](../eidoverse/examples/daisy/captions.py) | Example CLI: timeline to ASS subtitles, lyric preview | [voicebox](../tools-guides/voicebox.md) |
| [eidoverse/examples/daisy/song.py](../eidoverse/examples/daisy/song.py) | Worked example: a complete song with voicebox + synthkit | [voicebox](../tools-guides/voicebox.md) |
| [eidoverse/examples/obstacle_course.js](../eidoverse/examples/obstacle_course.js) | Scene example/template | [development](../tools-guides/development.md) |
| [eidoverse/examples/robotics/assembly.scene.js](../eidoverse/examples/robotics/assembly.scene.js) | Scene example/template | [development](../tools-guides/development.md) |
| [eidoverse/examples/robotics/mantis.scene.js](../eidoverse/examples/robotics/mantis.scene.js) | Scene example/template | [development](../tools-guides/development.md) |
| [eidoverse/examples/robotics/manufacturing.scene.js](../eidoverse/examples/robotics/manufacturing.scene.js) | Scene example/template | [development](../tools-guides/development.md) |
| [eidoverse/examples/robotics/motion.scene.js](../eidoverse/examples/robotics/motion.scene.js) | Scene example/template | [development](../tools-guides/development.md) |
| [eidoverse/fab_sim.js](../eidoverse/fab_sim.js) | Injected scene API | [robotics](../tools-guides/robotics.md) |
| [eidoverse/fluid_grid.js](../eidoverse/fluid_grid.js) | Dynamic ESM scene API | [volume-fire](../tools-guides/volume-fire.md) |
| [eidoverse/fluid_sim.js](../eidoverse/fluid_sim.js) | Dynamic ESM scene API | [liquids](../tools-guides/liquids.md) |
| [eidoverse/fluid_swe.js](../eidoverse/fluid_swe.js) | Dynamic ESM scene API | [liquids](../tools-guides/liquids.md) |
| [eidoverse/fluid_water.js](../eidoverse/fluid_water.js) | Dynamic ESM scene API | [free-surface-water](../tools-guides/free-surface-water.md) |
| [eidoverse/foot_ik.js](../eidoverse/foot_ik.js) | System support; see guide for entry point | [characters](../tools-guides/characters.md) |
| [eidoverse/graphics/era_screens_1939_1984.js](../eidoverse/graphics/era_screens_1939_1984.js) | Dynamic ESM scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/graphics/era_screens_2001_2023.js](../eidoverse/graphics/era_screens_2001_2023.js) | Dynamic ESM scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/graphics/preview_screens.mjs](../eidoverse/graphics/preview_screens.mjs) | CLI utility: engine-free PNGs, contact sheets, draw cost | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/graphics/screens_nan_sweep.mjs](../eidoverse/graphics/screens_nan_sweep.mjs) | CLI crash guard: non-finite canvas-geometry sweep | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/iso_field.js](../eidoverse/iso_field.js) | Injected scene API | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [eidoverse/loft.js](../eidoverse/loft.js) | Injected scene API | [geometry](../tools-guides/geometry.md) |
| [eidoverse/lyric_renderer.py](../eidoverse/lyric_renderer.py) | Optional Python frame utility; no CLI | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/model_kit.js](../eidoverse/model_kit.js) | Injected scene API | [assets](../tools-guides/assets.md) |
| [eidoverse/parallax_material.js](../eidoverse/parallax_material.js) | ESM installer for injected scene API | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/parallax_occlusion.js](../eidoverse/parallax_occlusion.js) | System support; see guide for entry point | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/particle_morph.js](../eidoverse/particle_morph.js) | Injected scene API | [particles-fx](../tools-guides/particles-fx.md) |
| [eidoverse/particles.js](../eidoverse/particles.js) | Injected scene API | [particles-fx](../tools-guides/particles-fx.md) |
| [eidoverse/procedural_materials.js](../eidoverse/procedural_materials.js) | Injected scene API | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/props/tandem.js](../eidoverse/props/tandem.js) | Dynamic ESM prop: tandem, rider IK, teapot stoker | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/index.js](../eidoverse/props/voice_machines/index.js) | Dynamic ESM: voice-machine catalogue, buildMachine/loadMachine | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/c64.js](../eidoverse/props/voice_machines/c64.js) | Dynamic ESM prop (1982 C64 + monitor) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/dectalk.js](../eidoverse/props/voice_machines/dectalk.js) | Dynamic ESM prop (1984 DECtalk) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/desktop2001.js](../eidoverse/props/voice_machines/desktop2001.js) | Dynamic ESM prop (2001 desktop PC) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/mac1984.js](../eidoverse/props/voice_machines/mac1984.js) | Dynamic ESM prop (1984 Macintosh) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/mainframe.js](../eidoverse/props/voice_machines/mainframe.js) | Dynamic ESM prop (1961 computer room) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/speakspell.js](../eidoverse/props/voice_machines/speakspell.js) | Dynamic ESM prop (1978 Speak & Spell) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/teletype.js](../eidoverse/props/voice_machines/teletype.js) | Dynamic ESM prop (1966 ASR-33) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/voder.js](../eidoverse/props/voice_machines/voder.js) | Dynamic ESM prop (1939 Voder) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/redgiant.js](../eidoverse/redgiant.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/gpu_check.mjs](../eidoverse/gpu_check.mjs) | Hardware preference, software fallback reporting + standalone compute/readback diagnostic; invoked by `doctor --gpu-only` | [stack-notes](../tools-guides/stack-notes.md), [setup](SETUP.md#gpu-setup-for-wsl-2) |
| [eidoverse/gpu_check_test.mjs](../eidoverse/gpu_check_test.mjs) | Hardware preference and software fallback tests; no GPU needed | [development](../tools-guides/development.md) |
| [eidoverse/render_common.mjs](../eidoverse/render_common.mjs) | Native runner support + UI utility | [scene-format](../tools-guides/scene-format.md) |
| [eidoverse/render_scene.mjs](../eidoverse/render_scene.mjs) | Native render entry | [scene-format](../tools-guides/scene-format.md) |
| [eidoverse/rhombic_dodecahedron.js](../eidoverse/rhombic_dodecahedron.js) | Injected scene API | [geometry](../tools-guides/geometry.md) |
| [eidoverse/ringworld.js](../eidoverse/ringworld.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/robot_body.js](../eidoverse/robot_body.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/robot_controller.js](../eidoverse/robot_controller.js) | Injected scene API | [characters](../tools-guides/characters.md) |
| [eidoverse/robot_debug.js](../eidoverse/robot_debug.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/robot_memory.js](../eidoverse/robot_memory.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/robot_planner.js](../eidoverse/robot_planner.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/robot_sensors.js](../eidoverse/robot_sensors.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/robotics/fabrication.js](../eidoverse/robotics/fabrication.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/cutter_nodes.js](../eidoverse/robotics/cutter_nodes.js) | GPU swept flat/ball cutter envelope | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/cutter_sweep.js](../eidoverse/robotics/cutter_sweep.js) | Analytic CPU swept-cutter removal and spatial indexing | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/relief.js](../eidoverse/robotics/relief.js) | Mesh/heightfield sampling and ball-compensated relief planning | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/rotary.js](../eidoverse/robotics/rotary.js) | Indexed four-axis volumetric carving jobs | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/rotary_setup.js](../eidoverse/robotics/rotary_setup.js) | Adjustable jaw, carriage and quill setup datums | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/rotary_path.js](../eidoverse/robotics/rotary_path.js) | Circumferential roughing, flat/ball compensation and XYZ/A timing | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/rotary_mesh.js](../eidoverse/robotics/rotary_mesh.js) | Mesh-driven indexed XYZ rasters and cutter-reach reporting | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/source_geometry.js](../eidoverse/robotics/source_geometry.js) | Manufacturing snapshots and uniform fitting of mesh assemblies | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/mesh_slices.js](../eidoverse/robotics/mesh_slices.js) | Closed cross-sections, holes and overlapping-solid union | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/manufacturing_samples.js](../eidoverse/robotics/manufacturing_samples.js) | Reusable ordinary mesh inputs for manufacturing examples | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/rotary_stock.js](../eidoverse/robotics/rotary_stock.js) | Seekable GPU volume subtraction and surface rendering | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/rotary_removal.js](../eidoverse/robotics/rotary_removal.js) | Volumetric first-engagement chip sampling | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/feed_path.js](../eidoverse/robotics/feed_path.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/filament.js](../eidoverse/robotics/filament.js) | Bézier tubing factory and metered dispenser controller | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/filament_path.js](../eidoverse/robotics/filament_path.js) | Internal extrusion/retraction timeline | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/cutting.js](../eidoverse/robotics/cutting.js) | Stock profiles, surface finishes and removal-driven debris | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/grasp.js](../eidoverse/robotics/grasp.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/index.js](../eidoverse/robotics/index.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/inspector/index.html](../eidoverse/robotics/inspector/index.html) | Inspector HTML entry | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/inspector/viewer.js](../eidoverse/robotics/inspector/viewer.js) | Inspector client | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/io.js](../eidoverse/robotics/io.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/materials.js](../eidoverse/robotics/materials.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/motion.js](../eidoverse/robotics/motion.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/running.js](../eidoverse/robotics/running.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/scara.js](../eidoverse/robotics/scara.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/serial_arm.js](../eidoverse/robotics/serial_arm.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/serve_inspector.py](../eidoverse/robotics/serve_inspector.py) | CLI utility | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/studio.js](../eidoverse/robotics/studio.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/tests/runtime_test.mjs](../eidoverse/robotics/tests/runtime_test.mjs) | Test suite | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/attachment_frames_test.mjs](../eidoverse/robotics/tests/attachment_frames_test.mjs) | Mount frames checked against physical flange triangles through articulation | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/fabrication_feed_test.mjs](../eidoverse/robotics/tests/fabrication_feed_test.mjs) | Filament, tubing and material-aware CNC regression checks | [development](../tools-guides/development.md) |
| [eidoverse/robotics_kit.js](../eidoverse/robotics_kit.js) | Injected scene API | [robotics](../tools-guides/robotics.md) |
| [eidoverse/satori_ui.mjs](../eidoverse/satori_ui.mjs) | Legacy standalone demo; separate renderer | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/scene_placement.js](../eidoverse/scene_placement.js) | ESM installer for injected scene API | [placement](../tools-guides/placement.md) |
| [eidoverse/screen.js](../eidoverse/screen.js) | Injected scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/sdf_raymarch_loader.js](../eidoverse/sdf_raymarch_loader.js) | Injected scene API | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [eidoverse/seedthree_api.js](../eidoverse/seedthree_api.js) | Injected API with optional external backend | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/sets/corner.js](../eidoverse/sets/corner.js) | Dynamic ESM film set | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/funeral.js](../eidoverse/sets/funeral.js) | Dynamic ESM film set | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/funeral/bridge.js](../eidoverse/sets/funeral/bridge.js) | Funeral set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean.js](../eidoverse/sets/ocean.js) | Dynamic ESM film set | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/apparitions.js](../eidoverse/sets/ocean/apparitions.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/daisies.js](../eidoverse/sets/ocean/daisies.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/echoes.js](../eidoverse/sets/ocean/echoes.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/faces_atlas.js](../eidoverse/sets/ocean/faces_atlas.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/house.js](../eidoverse/sets/ocean/house.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/land.js](../eidoverse/sets/ocean/land.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/pages.js](../eidoverse/sets/ocean/pages.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/perform.js](../eidoverse/sets/ocean/perform.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/sea.js](../eidoverse/sets/ocean/sea.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/ocean/util.js](../eidoverse/sets/ocean/util.js) | Ocean set submodule | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sky_system.js](../eidoverse/sky_system.js) | Injected scene API | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/sky_worlds.js](../eidoverse/sky_worlds.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/sun_corona.js](../eidoverse/sun_corona.js) | Dynamic ESM scene API | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/surface_layers.js](../eidoverse/surface_layers.js) | Injected scene API | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/terrain.js](../eidoverse/terrain.js) | Injected scene API | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/terrain_base.js](../eidoverse/terrain_base.js) | Scene example/template | [characters](../tools-guides/characters.md) |
| [eidoverse/text_3d.js](../eidoverse/text_3d.js) | Dynamic ESM scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/tsl_curl_noise.js](../eidoverse/tsl_curl_noise.js) | System support; see guide for entry point | [volume-fire](../tools-guides/volume-fire.md) |
| [eidoverse/vegetation.js](../eidoverse/vegetation.js) | Lazy ESM behind injected createFlora | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_corn_gen.js](../eidoverse/vegetation_corn_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_loader.js](../eidoverse/vegetation_loader.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_shrub_gen.js](../eidoverse/vegetation_shrub_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_sunflower_gen.js](../eidoverse/vegetation_sunflower_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_daisy_gen.js](../eidoverse/vegetation_daisy_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/video_to_sprite.mjs](../eidoverse/video_to_sprite.mjs) | CLI utility | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/vrm_turntable_scene.js](../eidoverse/vrm_turntable_scene.js) | Scene script behind vrm_turntable.py | [characters](../tools-guides/characters.md) |
| [eidoverse/weather_audio.js](../eidoverse/weather_audio.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/weather_system.js](../eidoverse/weather_system.js) | Injected scene API | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/xr/example.html](../eidoverse/xr/example.html) | HTML entry point: minimal WebXR page on the kit (served by xr/serve.py) | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/quest.py](../eidoverse/xr/quest.py) | CLI utility: the headset over adb (Wi-Fi debugging, open, awake, pull recordings) | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/serve.py](../eidoverse/xr/serve.py) | CLI utility: HTTPS server for headset pages + /report telemetry log | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/shot.mjs](../eidoverse/xr/shot.mjs) | CLI utility: stills of a WebXR page from headless Chrome | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/xr_kit.js](../eidoverse/xr/xr_kit.js) | Browser ES module for WebXR pages (not a scene-script import) | [webxr](../tools-guides/webxr.md) |
| [fetch_hdri.py](../fetch_hdri.py) | CLI utility | [assets](../tools-guides/assets.md) |
| [fetch_model.py](../fetch_model.py) | CLI utility | [assets](../tools-guides/assets.md) |
| [fetch_texture.py](../fetch_texture.py) | CLI utility | [assets](../tools-guides/assets.md) |
| [generate_sfx.py](../generate_sfx.py) | CLI utility | [audio](../tools-guides/audio.md) |
| [generate_song.py](../generate_song.py) | MiniMax Music 3 generator | [audio](../tools-guides/audio.md) |
| [lipsync.py](../lipsync.py) | Python audio module; no CLI | [audio](../tools-guides/audio.md) |
| [merge_av.py](../merge_av.py) | CLI utility | [audio](../tools-guides/audio.md) |
| [run_blender.sh](../run_blender.sh) | CLI utility: isolated headless Blender runner | [blender](../tools-guides/blender.md) |
| [synthkit/__init__.py](../synthkit/__init__.py) | Python package API (import from repo root) | [synthkit](../tools-guides/synthkit.md) |
| [synthkit/dsp.py](../synthkit/dsp.py) | Oscillators, filters, envelopes (numba) | [synthkit](../tools-guides/synthkit.md) |
| [synthkit/fx.py](../synthkit/fx.py) | Designed effects (tape stop, stutter, modem, power-down) | [synthkit](../tools-guides/synthkit.md) |
| [synthkit/instruments.py](../synthkit/instruments.py) | Instruments and drums | [synthkit](../tools-guides/synthkit.md) |
| [synthkit/seq.py](../synthkit/seq.py) | Sequencer, mixer, true-peak master bus | [synthkit](../tools-guides/synthkit.md) |
| [voicebox/__init__.py](../voicebox/__init__.py) | Python package API (import from repo root) | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/articulate.py](../voicebox/articulate.py) | Voice, phoneme planning, control tracks, sung F0 | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/choir.py](../voicebox/choir.py) | Choir and humming (many singers per chord tone) | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/engine.py](../voicebox/engine.py) | System support: numba formant synthesis core | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/eras.py](../voicebox/eras.py) | Historical machine-voice renderers | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/g2p.py](../voicebox/g2p.py) | Lyrics to syllables (CMUdict + custom lexicon) | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/phonemes.py](../voicebox/phonemes.py) | System support: vowel and consonant tables | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/resing.py](../voicebox/resing.py) | Optional backend (network/Windows): TTS re-sung via PSOLA | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/score.py](../voicebox/score.py) | Sung score API, speech timing, visemes | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/tube.py](../voicebox/tube.py) | Kelly–Lochbaum vocal-tract model (the 1961 voice) | [voicebox](../tools-guides/voicebox.md) |
| [voicebox/util.py](../voicebox/util.py) | WAV I/O, spectrograms, Whisper checks | [voicebox](../tools-guides/voicebox.md) |
| [vrm_turntable.py](../vrm_turntable.py) | CLI utility: VRM outfit, clip and expression sheets | [characters](../tools-guides/characters.md) |
| [eidoverse/robotics/tests/relief_test.mjs](../eidoverse/robotics/tests/relief_test.mjs) | Relief compensation, swept stock and assembled machining checks | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/rotary_test.mjs](../eidoverse/robotics/tests/rotary_test.mjs) | Rotary clearance, compensation, swept solids and engagement checks | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/mesh_input_test.mjs](../eidoverse/robotics/tests/mesh_input_test.mjs) | Mesh transforms, closed slices, nested solids, infill and local skins | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/rotary_mesh_test.mjs](../eidoverse/robotics/tests/rotary_mesh_test.mjs) | Mesh toolpath compensation, flat cutter and reach checks | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/rotary_mount_test.mjs](../eidoverse/robotics/tests/rotary_mount_test.mjs) | Stud engagement and visible T-slot nut surfaces | [development](../tools-guides/development.md) |
| [eidoverse/examples/robotics/mesh_fabrication.scene.js](../eidoverse/examples/robotics/mesh_fabrication.scene.js) | Rotary carving from an ordinary Object3D mesh assembly | [robotics](../tools-guides/robotics.md) |
| [eidoverse/examples/robotics/rotary.scene.js](../eidoverse/examples/robotics/rotary.scene.js) | Renderable stock-rotating all-around carving example | [robotics](../tools-guides/robotics.md) |
| [eidoverse/examples/robotics/rotary_metal.scene.js](../eidoverse/examples/robotics/rotary_metal.scene.js) | Aluminum rotary cutting at physical speed followed by a time-lapse finish | [robotics](../tools-guides/robotics.md) |
| [eidoverse/examples/robotics/relief.scene.js](../eidoverse/examples/robotics/relief.scene.js) | Renderable close study of ball-nose roughing and finishing | [robotics](../tools-guides/robotics.md) |

**215 first-party source/entry-point files, plus 8 asset `_src` folders; 33 guides; 31 post effects.**
This is documentation coverage, not a claim that every API was executed in
this audit or a count of robot parts. The inspector HTML entry point is included.

## Additional instructions and asset notes

- [Setup](SETUP.md), [interactive workflow](HARNESS_MODE.md),
  [engine maintainer map](../eidoverse/README.md) and
  [documentation maintenance](../tools-guides/development.md).
- [Robotics assets](../eidoverse/assets/robotics/README.md) and
  [asset provenance](../eidoverse/assets/robotics/THIRD_PARTY.md).
- [Book template](../eidoverse/assets/book_template/README.md) and
  [book sound sources](../eidoverse/assets/book_sfx/SOURCES.md).
- [Claudesona wardrobe source](../eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md),
  [performance clips source](../eidoverse/assets/animations/performance_src/README.md) and
  [daisy sheet source](../eidoverse/assets/grass/daisy_src/README.md).
- [DAISY song example](../eidoverse/examples/daisy/README.md) and
  [era screen sources](../eidoverse/graphics/SOURCES.md).
- Props and sets: [voice machines](../eidoverse/assets/models/voice_machines/README.md),
  [tandem](../eidoverse/assets/models/tandem_1896/README.md),
  [corner](../eidoverse/assets/sets/corner/README.md), [funeral](../eidoverse/assets/sets/funeral/README.md) and
  [ocean](../eidoverse/assets/sets/ocean/README.md), each with a SOURCES file beside it.

## Scope and exclusions

The scan includes first-party JS/MJS, Python and HTML entry points, and checks
for other script/shader extensions. Vendored Three.js, N8AO, PDF.js and polygon-clipping are
dependencies, not separately authored tools. `book_core.pre_astra.js` is a
source snapshot. An asset's `<name>_src/` folder holds the scripts that authored that asset
(mostly Blender, run through `run_blender.sh`); each folder is listed once, by its
README, rather than script by script. Ignored working projects, `ASTRA_NOTES*.md` session notes,
credits/license notices and the historical techniques archive are outside
the active instruction split; they are preserved in place.

The retired `mech_parts.js` is intentionally absent. `robotics_kit.js` and
`fab_sim.js` expose the new modular system. The separate `robot_*.js` VRM
navigation stack remains supported. Legacy source archives stay in ignored
working storage and Git history rather than the active tool tree.
