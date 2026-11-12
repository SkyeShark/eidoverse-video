# Tool and source inventory (Blender edition)

[Main instructions](../AGENTS.md) list the topic guides and when to read
them. This inventory maps every module of the Blender edition's `eidoblend`
package and every command-line tool to its guide (part 1), then the Python
tools both editions share (part 2), then the WebGPU engine's sources, which
stay on this branch as the source each port came from (part 3). A source can
be a public tool, internal support, an optional utility, an example or a
test; file count is not tool count.

## 1. The Blender edition

Scenes are Python scripts run by `eido_blender.py`; systems are the
`blender/eidoblend` package, one self-contained subpackage per family.
`import eidoblend` imports nothing; `eidoblend.<family>` and each family's
subpackages load on first use.

### The runner, its tools and the tests

| Source or tool | Role | Instructions |
| --- | --- | --- |
| [eido_blender.py](../eido_blender.py) | CLI: `doctor`, `build`, `render` (`--probe`, `--at`), `bench`, `open` | [scene-format](../tools-guides/scene-format.md) |
| [run_blender.sh](../run_blender.sh) | CLI utility: isolated headless Blender (every runner call goes through it) | [blender](../tools-guides/blender.md), [development](../tools-guides/development.md) |
| [blender/README.md](../blender/README.md) | The edition's layout, families and tests | [development](../tools-guides/development.md) |
| [blender/tools/vrm_turntable.py](../blender/tools/vrm_turntable.py) | Blender CLI: VRM outfit, clip, face and PBR sheets, spin reels | [claudesona](../tools-guides/claudesona.md) |
| [blender/examples/obstacle_course/scene.py](../blender/examples/obstacle_course/scene.py) | Scene example: the walking course (`eidoverse/examples/obstacle_course.js`), aporia driven by the character controller through `course.template` | [geometry](../tools-guides/geometry.md), [controller](../tools-guides/controller.md) |
| [blender/tests/run_all.py](../blender/tests/run_all.py) | Test runner: every area's tests in one run, PASS / FAIL per test (`--kinds imports` checks the package's wiring in seconds) | [development](../tools-guides/development.md) |
| [blender/tests/pipeline/run_tests.py](../blender/tests/pipeline/run_tests.py) | Test suite: the runner end to end (T0–T17; most render) | [development](../tools-guides/development.md) |
| [blender/tests/pipeline2/run_tests.py](../blender/tests/pipeline2/run_tests.py) | Test suite: the harness's own scene API, the post stack and its hooks, the overlay layer (U0–U6) | [development](../tools-guides/development.md) |
| [blender/tests/pipeline/query_blend.py](../blender/tests/pipeline/query_blend.py) | Test helper: what a saved build shows at given frames (positions, light values, key interpolations), no render | [development](../tools-guides/development.md) |
| [blender/tests/pipeline/check_docs.py](../blender/tests/pipeline/check_docs.py) | Docs check: links resolve, every module inventoried, the guide index complete (no Blender) | [development](../tools-guides/development.md) |
| [blender/tests/pipeline/example/scene.py](../blender/tests/pipeline/example/scene.py) | Scene example/template (a stool, a clock, a push-in) | [scene-format](../tools-guides/scene-format.md) |
| [blender/tests/pipeline/crows/scene.py](../blender/tests/pipeline/crows/scene.py) | Test scene: a model's own clips on a model and its clone | [assets](../tools-guides/assets.md) |
| [blender/tests/pipeline/defects/scene.py](../blender/tests/pipeline/defects/scene.py) | Test scene: planted defects the digest must name | [render-review](../tools-guides/render-review.md) |
| [blender/tests/pipeline/placement_bridge/scene.py](../blender/tests/pipeline/placement_bridge/scene.py) | Test scene: the runner runs the placement family's audits | [placement](../tools-guides/placement.md) |
| [blender/tests/pipeline/kit/scene.py](../blender/tests/pipeline/kit/scene.py) | Test scene: `load_kit` parts standing on their bases | [assets](../tools-guides/assets.md) |
| [blender/tests/pipeline/make_kit.py](../blender/tests/pipeline/make_kit.py) | Test helper: a three-part kit GLB, made headless | [assets](../tools-guides/assets.md) |
| [blender/tests/pipeline/nav/scene.py](../blender/tests/pipeline/nav/scene.py) | Test scene: a sensing walk through an unseen room | [navigation](../tools-guides/navigation.md) |
| [blender/tests/pipeline/bloom/scene.py](../blender/tests/pipeline/bloom/scene.py) | Test scene: the compositor bloom option on a hot emitter | [scene-format](../tools-guides/scene-format.md) |
| [blender/tests/pipeline/bake/scene.py](../blender/tests/pipeline/bake/scene.py) | Test scene: a 300-frame rigid-body film, crates knocked after Blender's default cache end | [scene-format](../tools-guides/scene-format.md) |
| [blender/tests/pipeline/stale/scene.py](../blender/tests/pipeline/stale/scene.py) | Test scene: built from a plan file it reads; an edit to the plan rebuilds | [scene-format](../tools-guides/scene-format.md) |
| [blender/tests/pipeline/shots/scene.py](../blender/tests/pipeline/shots/scene.py) | Test scene: two shots, a keyed lamp step at the cut, per-shot framing | [scene-format](../tools-guides/scene-format.md) |
| [blender/tests/pipeline/gn_keying/scene.py](../blender/tests/pipeline/gn_keying/scene.py) | Test scene: a Geometry Nodes modifier's input keyed through `ctx.key`, and the unkeyed variant the digest names | [scene-format](../tools-guides/scene-format.md) |
| [blender/tests/pipeline/hand_edit.py](../blender/tests/pipeline/hand_edit.py) | Test helper: a hand edit of a built `.blend`, done headless | [development](../tools-guides/development.md) |
| [blender/tests/claudesona/basic_vrm/scene.py](../blender/tests/claudesona/basic_vrm/scene.py) | Scene example: the minimal VRM scene (`eidoverse/examples/basic_vrm.js`; `scene_claude.json` loads its own `claude.vrm`) | [claudesona](../tools-guides/claudesona.md) |
| [blender/tests/sets_daisy_ocean/](../blender/tests/sets_daisy_ocean/) | The ocean set's parity tests (against the WebGPU modules run in Deno and an independent numpy sea) and its stills | [props-and-sets](../tools-guides/props-and-sets.md) |
| [blender/tests/sdf/engine\_march.py](../blender/tests/sdf/engine_march.py) | Test helper: the engine's own raymarch of an SDF solid, volume or mushroom cloud from a Blender camera, set beside the EEVEE renders | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [blender/tests/voice_machines_b/](../blender/tests/voice_machines_b/) | Probes and parity: the era-1 machines, the Speak & Spell, the tandem (two teletypes, the dark room) | [voice-machines](../tools-guides/voice-machines.md) |

Each family's tests live in `blender/tests/<area>/` (renders land in its
git-ignored `out/`); `run_all.py --list` names them all.

### `eidoblend` itself and `eidoblend.harness`

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/__init__.py) | The package: imports nothing; each family on attribute access | [development](../tools-guides/development.md) |
| [common.py](../blender/eidoblend/common.py) | Shared paths, three.js → Blender axes, frame/time, small tools (no bpy) | [scene-format](../tools-guides/scene-format.md) |
| [harness/\_\_init\_\_.py](../blender/eidoblend/harness/__init__.py) | The harness's module map (lazy) | [development](../tools-guides/development.md) |
| [harness/config.py](../blender/eidoblend/harness/config.py) | scene.json → checked config, output names (no bpy) | [scene-format](../tools-guides/scene-format.md) |
| [harness/run_scene.py](../blender/eidoblend/harness/run_scene.py) | The script `eido_blender.py` runs inside Blender | [scene-format](../tools-guides/scene-format.md) |
| [harness/runner.py](../blender/eidoblend/harness/runner.py) | Build (setup, `render_frame` keyed, caches stretched and baked, audits, `.blend`, its inputs incl. files the script read; images painted during the build kept beside the `.blend`) then render | [scene-format](../tools-guides/scene-format.md) |
| [harness/context.py](../blender/eidoblend/harness/context.py) | `ctx`: what `setup` / `render_frame` / `cleanup` receive | [scene-format](../tools-guides/scene-format.md) |
| [harness/keying.py](../blender/eidoblend/harness/keying.py) | `ctx.key`'s keys made LINEAR (or as asked); changes `render_frame` made without a key, found and named (Geometry Nodes inputs too) | [scene-format](../tools-guides/scene-format.md) |
| [harness/settings.py](../blender/eidoblend/harness/settings.py) | The film and probe EEVEE presets, the `render` block, bloom | [scene-format](../tools-guides/scene-format.md) |
| [harness/output.py](../blender/eidoblend/harness/output.py) | H.264 straight from EEVEE, PNG stills, `.part`/`.prev`, probe frames, progress lines, `RENDER_CQ` / `RENDER_BITRATE` / `RENDER_CODEC` | [scene-format](../tools-guides/scene-format.md) |
| [harness/post.py](../blender/eidoblend/harness/post.py) | The engine's auto-enhance stack on EEVEE, its hooks, and the overlay layer, which lands as drawn | [scene-format](../tools-guides/scene-format.md) |
| [harness/render_common.py](../blender/eidoblend/harness/render_common.py) | What `render_common.mjs` (the render tools' shared kit) means in Blender | [scene-format](../tools-guides/scene-format.md) |
| [harness/ledger.py](../blender/eidoblend/harness/ledger.py) | Audit ledger, flags and digest: `audit_core.js` ported whole (no bpy) | [render-review](../tools-guides/render-review.md) |
| [harness/audits.py](../blender/eidoblend/harness/audits.py) | Preflight (the sequencer included), coverage, motion (locomotion, lipsync), framing, palette and asset checks | [render-review](../tools-guides/render-review.md) |
| [harness/showpiece.py](../blender/eidoblend/harness/showpiece.py) | The palette report's showpiece nudge (plain Python) | [production](../tools-guides/production.md) |
| [harness/assets.py](../blender/eidoblend/harness/assets.py) | Scene API: `load_image_texture`, `fetch_pbr`, `load_pbr`, `fetch_model_file`, `import_model`, `play_model_animations`, `clone_model`, `load_kit`, `load_hdri`, `make_glass`; clip names and file order, clip weights, clones that play, `Kit.islands` | [assets](../tools-guides/assets.md) |
| [harness/model_preview.py](../blender/eidoblend/harness/model_preview.py) | CLI: a model's orientation preview (`fetch_model.py`'s), rendered in Blender | [assets](../tools-guides/assets.md) |
| [harness/html_mesh.py](../blender/eidoblend/harness/html_mesh.py) | HTMLMesh: a UI element tree styled with CSS (titles, lower thirds, HUD chips, panels) painted onto a panel in the world | [assets](../tools-guides/assets.md) |
| [harness/interior_window.py](../blender/eidoblend/harness/interior_window.py) | Interior-mapped windows (a room seen behind a flat pane) and room pictures, as an EEVEE material | [assets](../tools-guides/assets.md) |
| [harness/navigation.py](../blender/eidoblend/harness/navigation.py) | Scene API: `RobotSensors`, `RobotMemory`, `RobotPlanner`, `timed_route`, `debug_overlay` (the `robot_*.js` sensing, memory and planning) | [navigation](../tools-guides/navigation.md) |
| [harness/doctor.py](../blender/eidoblend/harness/doctor.py) | The in-Blender half of `doctor`: a 64x64 EEVEE render and the GPU compute check | [development](../tools-guides/development.md) |
| [harness/gpu_check.py](../blender/eidoblend/harness/gpu_check.py) | CLI and module: hardware or software GPU, and a compute dispatch read back (`gpu_check.mjs`'s check) | [development](../tools-guides/development.md) |

### Characters (`eidoblend.characters`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/characters/__init__.py) | The family: load, clips, walking, expressions; its subpackages by name | [characters](../tools-guides/characters.md) |
| [vrm.py](../blender/eidoblend/characters/vrm.py) | `load_vrm` and the VRM handle (MToon, or `look='pbr'`) | [characters](../tools-guides/characters.md) |
| [vrma.py](../blender/eidoblend/characters/vrma.py) | The VRMA clip library: load, play, crossfade | [characters](../tools-guides/characters.md) |
| [locomotion.py](../blender/eidoblend/characters/locomotion.py) | `walk_path`: a VRM walking a path over uneven ground, feet planted | [characters](../tools-guides/characters.md) |
| [ground.py](../blender/eidoblend/characters/ground.py) | The feet's contact points and the ground a body stands on | [characters](../tools-guides/characters.md) |
| [expressions.py](../blender/eidoblend/characters/expressions.py) | A VRM's expressions keyed on its face's shape keys | [characters](../tools-guides/characters.md) |
| [performance.py](../blender/eidoblend/characters/performance.py) | A stationary clip performed through the body's own frame order, baked to keys | [characters](../tools-guides/characters.md) |
| [checks.py](../blender/eidoblend/characters/checks.py) | The family's checks as functions: T-pose, slide, a face that never moved | [characters](../tools-guides/characters.md) |
| [\_math.py](../blender/eidoblend/characters/_math.py) | The family's shared maths (mathutils, no bpy) | [characters](../tools-guides/characters.md) |
| [clippy.py](../blender/eidoblend/characters/clippy.py) | `make_clippy`: the paperclip, his morphs and his 43 clips (`clippy.js`) | [clippy](../tools-guides/clippy.md) |
| [springs.py](../blender/eidoblend/characters/springs.py) | Spring bones simulated once, in frame order, baked to keys (`bake_springs`, `SpringRig`) | [claudesona](../tools-guides/claudesona.md) |
| [lookat.py](../blender/eidoblend/characters/lookat.py) | Eyes on a target, as three-vrm's VRMLookAt drives them, baked to keys | [claudesona](../tools-guides/claudesona.md) |
| [lipsync.py](../blender/eidoblend/characters/lipsync.py) | A VRM's mouth keyed from audio (`key_lipsync`, `visemes_from_audio`) | [claudesona](../tools-guides/claudesona.md), [audio](../tools-guides/audio.md) |
| [claudesona/\_\_init\_\_.py](../blender/eidoblend/characters/claudesona/__init__.py) | The claudesona: its face, wardrobe, TuTa and look | [claudesona](../tools-guides/claudesona.md) |
| [claudesona/face.py](../blender/eidoblend/characters/claudesona/face.py) | `claudesona_face.js`: the mouths, the lipsync drivers, an emotion track keyed to words | [claudesona](../tools-guides/claudesona.md) |
| [claudesona/wardrobe.py](../blender/eidoblend/characters/claudesona/wardrobe.py) | `claudesona_wardrobe.js`'s garment layers shown, hidden and repainted, keyed | [claudesona](../tools-guides/claudesona.md) |
| [claudesona/tuta.py](../blender/eidoblend/characters/claudesona/tuta.py) | The TuTa: badges pinned and thrown, face paint, the sun disc, neon, eye lights | [claudesona](../tools-guides/claudesona.md) |
| [claudesona/look.py](../blender/eidoblend/characters/claudesona/look.py) | MToon as the VRM add-on imports it, or a PBR look, switchable | [claudesona](../tools-guides/claudesona.md) |
| [claudesona/\_mesh.py](../blender/eidoblend/characters/claudesona/_mesh.py) | The claudesona's meshes read as the WebGPU runtime reads them | [claudesona](../tools-guides/claudesona.md) |
| [claudesona/\_paint.py](../blender/eidoblend/characters/claudesona/_paint.py) | The wardrobe's paints as shader nodes, switched by a keyed property | [claudesona](../tools-guides/claudesona.md) |
| [controller/\_\_init\_\_.py](../blender/eidoblend/characters/controller/__init__.py) | The character controller for film: `VRMCharacterController`, `VRMFootControllerIK`, `Locomotion`, `CollisionWorld` (`character_controller.js` / `foot_ik.js`) | [controller](../tools-guides/controller.md) |
| [controller/controller.py](../blender/eidoblend/characters/controller/controller.py) | `VRMCharacterController`: the controller's state machine, gaits, stairs and ramps | [controller](../tools-guides/controller.md) |
| [controller/foot_ik.py](../blender/eidoblend/characters/controller/foot_ik.py) | `VRMFootControllerIK`: raycast foot planting | [controller](../tools-guides/controller.md) |
| [controller/film.py](../blender/eidoblend/characters/controller/film.py) | `Locomotion`: directing the controller for a film, and the bake that keys what it did | [controller](../tools-guides/controller.md) |
| [controller/maneuvers.py](../blender/eidoblend/characters/controller/maneuvers.py) | The controller's parkour moves: vault, climb a ledge, jump, ladder, wall, and the auto-trigger | [controller](../tools-guides/controller.md) |
| [controller/plant.py](../blender/eidoblend/characters/controller/plant.py) | The film bake's feet, planted on whatever the controller walked over | [controller](../tools-guides/controller.md) |
| [controller/pose.py](../blender/eidoblend/characters/controller/pose.py) | One frame's pose as the controller and its foot IK see it | [controller](../tools-guides/controller.md) |
| [controller/world.py](../blender/eidoblend/characters/controller/world.py) | `CollisionWorld`: the walkable world the controller and the foot IK probe | [controller](../tools-guides/controller.md) |
| [controller/clips.py](../blender/eidoblend/characters/controller/clips.py) | The controller's clip library and what it measures in each clip on a body | [controller](../tools-guides/controller.md) |
| [controller/mixer.py](../blender/eidoblend/characters/controller/mixer.py) | three.js's AnimationMixer, for the controller's build-time simulation | [controller](../tools-guides/controller.md) |
| [emotes/\_\_init\_\_.py](../blender/eidoblend/characters/emotes/__init__.py) | The character verbs on the controller: `seat_on`, `stand_up`, `sit_on_ground`, `emote`, `face_camera`, `unseat`, `bake`, `seat_plan`, the keyed seated exemption | [maneuvers](../tools-guides/maneuvers.md) |
| [emotes/verbs.py](../blender/eidoblend/characters/emotes/verbs.py) | The verbs for a body the controller drives, routed to `placement.seating` when nothing drives it | [maneuvers](../tools-guides/maneuvers.md) |
| [emotes/catalog.py](../blender/eidoblend/characters/emotes/catalog.py) | The library's expressive and sitting clips, each measured on the body | [maneuvers](../tools-guides/maneuvers.md) |
| [maneuvers/\_\_init\_\_.py](../blender/eidoblend/characters/maneuvers/__init__.py) | Moves aimed at scene objects: `vault_over`, `climb_onto`, `scramble_up`, `climb_ladder`, `jump_across`, `cross` | [maneuvers](../tools-guides/maneuvers.md) |
| [maneuvers/verbs.py](../blender/eidoblend/characters/maneuvers/verbs.py) | The aimed moves themselves | [maneuvers](../tools-guides/maneuvers.md) |
| [maneuvers/targets.py](../blender/eidoblend/characters/maneuvers/targets.py) | What a move is aimed at, measured from the scene's own geometry (a ladder's rungs and their radius too) | [maneuvers](../tools-guides/maneuvers.md) |
| [robot\_dof.py](../blender/eidoblend/characters/robot_dof.py) | My robot body's hardware pass: `claude_robot_dof.js` whole | [robot-body](../tools-guides/robot-body.md) |
| [pose\_bake.py](../blender/eidoblend/characters/pose_bake.py) | Solve a performance once, play the recorded poses back (`pose_bake.js`'s files, both ways) | [robot-body](../tools-guides/robot-body.md) |
| [robot/\_\_init\_\_.py](../blender/eidoblend/characters/robot/__init__.py) | My robot body in Blender: its runtime, its hands, the embodied robot for any VRM | [robot-body](../tools-guides/robot-body.md) |
| [robot/rig.py](../blender/eidoblend/characters/robot/rig.py) | `RobotRig`: my robot body's runtime on one VRM, the example's frame order, keyed | [robot-body](../tools-guides/robot-body.md) |
| [robot/hands.py](../blender/eidoblend/characters/robot/hands.py) | My hands' work: reach, grasp until each finger touches, hold, set down (round or flat-sided props, either hand) | [robot-body](../tools-guides/robot-body.md) |
| [robot/body.py](../blender/eidoblend/characters/robot/body.py) | `VRMRobotBody` (`robot_body.js`): sensing, memory, A*, walks, runs, vault / jump / climb_ledge / climb_ladder | [robot-body](../tools-guides/robot-body.md) |
| [robot/controller.py](../blender/eidoblend/characters/robot/controller.py) | `EidoverseRobotController` (`robot_controller.js`) and the legs it drives | [robot-body](../tools-guides/robot-body.md) |
| [robot/bake.py](../blender/eidoblend/characters/robot/bake.py) | A run the legs recorded, keyed through my body's passes | [robot-body](../tools-guides/robot-body.md) |
| [robot/debug.py](../blender/eidoblend/characters/robot/debug.py) | `RobotDebug` (`robot_debug.js`): what the robot sees and knows, as keyed geometry | [robot-body](../tools-guides/robot-body.md) |
| [robot/example.py](../blender/eidoblend/characters/robot/example.py) | `eidoverse/examples/claude_robot.js`, the whole scene | [robot-body](../tools-guides/robot-body.md) |
| [robotics/\_\_init\_\_.py](../blender/eidoblend/characters/robotics/__init__.py) | The modular robotics kit: kit, motion, solvers, running, materials, io, studio, facade, inspector, rig, examples | [robotics](../tools-guides/robotics.md) |
| [robotics/kit.py](../blender/eidoblend/characters/robotics/kit.py) | `index.js`: the kit's loader, modules, ports and assemblies | [robotics](../tools-guides/robotics.md) |
| [robotics/facade.py](../blender/eidoblend/characters/robotics/facade.py) | `robotics_kit.js`: the `RoboticsKit` facade and `make_bot` | [robotics](../tools-guides/robotics.md) |
| [robotics/motion.py](../blender/eidoblend/characters/robotics/motion.py) | `motion.js`: the kit's deterministic controls and motion samples | [robotics](../tools-guides/robotics.md) |
| [robotics/solvers.py](../blender/eidoblend/characters/robotics/solvers.py) | The kit's pure kinematics (no bpy) | [robotics](../tools-guides/robotics.md) |
| [robotics/running.py](../blender/eidoblend/characters/robotics/running.py) | `running.js`: `create_running_controller` | [robotics](../tools-guides/robotics.md) |
| [robotics/materials.py](../blender/eidoblend/characters/robotics/materials.py) | `materials.js`: the kit's materials prepared | [robotics](../tools-guides/robotics.md) |
| [robotics/io.py](../blender/eidoblend/characters/robotics/io.py) | `io.js`: the kit's shared caches | [robotics](../tools-guides/robotics.md) |
| [robotics/studio.py](../blender/eidoblend/characters/robotics/studio.py) | `studio.js`: the presentation the kit's examples and inspector share | [robotics](../tools-guides/robotics.md) |
| [robotics/inspector.py](../blender/eidoblend/characters/robotics/inspector.py) | The kit's inspector as a Blender scene | [robotics](../tools-guides/robotics.md) |
| [robotics/rig.py](../blender/eidoblend/characters/robotics/rig.py) | A robot's joints as sliders that drive its modules (the inspector's joint panel) | [robotics](../tools-guides/robotics.md) |
| [robotics/examples.py](../blender/eidoblend/characters/robotics/examples.py) | The assembly, MANTIS and motion examples | [robotics](../tools-guides/robotics.md) |
| [robotics/scenes/assembly.py](../blender/eidoblend/characters/robotics/scenes/assembly.py) | Scene script (with its `.json`): a new assembly made through interface frames | [robotics](../tools-guides/robotics.md) |
| [robotics/scenes/mantis.py](../blender/eidoblend/characters/robotics/scenes/mantis.py) | Scene script (with its `.json`): the tracked MANTIS and its payloads | [robotics](../tools-guides/robotics.md) |
| [robotics/scenes/motion.py](../blender/eidoblend/characters/robotics/scenes/motion.py) | Scene script (with its `.json`): the humanoid, the quadruped, the drone and the tracked arm in motion | [robotics](../tools-guides/robotics.md) |
| [robotics/legacy\_arm.py](../blender/eidoblend/characters/robotics/legacy_arm.py) | `RoboticArm`, the production engine's robotic arm | [robotics](../tools-guides/robotics.md) |
| [robotics/mech\_parts.py](../blender/eidoblend/characters/robotics/mech_parts.py) | `MechParts`, the production engine's mechanical parts | [robotics](../tools-guides/robotics.md) |
| [robotics/\_display.py](../blender/eidoblend/characters/robotics/_display.py) | The studio's unlit colours, displayed as the original displays them | [robotics](../tools-guides/robotics.md) |
| [robotics/\_mesh.py](../blender/eidoblend/characters/robotics/_mesh.py) | A subset of a mesh's faces as a new mesh, shading as before | [robotics](../tools-guides/robotics.md) |

### The locomotion courses (`eidoblend.course`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/course/__init__.py) | The locomotion course template (`terrain_base.js`) and three-bvh-csg's booleans | [geometry](../tools-guides/geometry.md) |
| [template.py](../blender/eidoblend/course/template.py) | The template's `setup` / `render_frame` / `cleanup`, and the walking course example on top of it | [geometry](../tools-guides/geometry.md), [controller](../tools-guides/controller.md) |
| [presets.py](../blender/eidoblend/course/presets.py) | The engine's locomotion courses (`TERRAIN_CONFIG`s) and its course example | [geometry](../tools-guides/geometry.md) |
| [builder.py](../blender/eidoblend/course/builder.py) | A course built in Blender: stairs, ramps, walls, ladders, gaps | [geometry](../tools-guides/geometry.md) |
| [plan.py](../blender/eidoblend/course/plan.py) | The course maths, in three's axes (no bpy) | [geometry](../tools-guides/geometry.md) |
| [stage.py](../blender/eidoblend/course/stage.py) | The scene around a course: light, ground, camera | [geometry](../tools-guides/geometry.md) |
| [csg.py](../blender/eidoblend/course/csg.py) | three-bvh-csg's boolean operations on Blender meshes, the two HOLLOW ones included | [geometry](../tools-guides/geometry.md) |

### Fabrication and rotary carving (`eidoblend.fabrication`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/fabrication/__init__.py) | G430 FDM printing, pocket milling and relief carving: slicer, feed clock, Geometry Nodes bead and swept-cutter stock, chips, live filament and PTFE tubes, `FabSim`, the examples | [fabrication](../tools-guides/fabrication.md) |
| [fab\_sim.py](../blender/eidoblend/fabrication/fab_sim.py) | `FabSim`: the G430 CNC / FDM facade (`fab_sim.js`) | [fabrication](../tools-guides/fabrication.md) |
| [processes.py](../blender/eidoblend/fabrication/processes.py) | Additive printing, pocket milling and three-axis relief machining (`fabrication.js`) | [fabrication](../tools-guides/fabrication.md) |
| [machine.py](../blender/eidoblend/fabrication/machine.py) | The G430 gantry's controls a job drives | [fabrication](../tools-guides/fabrication.md) |
| [feed\_path.py](../blender/eidoblend/fabrication/feed_path.py) | 2.5D process geometry and feed timing, in metres and seconds (`feed_path.js`) | [fabrication](../tools-guides/fabrication.md) |
| [filament.py](../blender/eidoblend/fabrication/filament.py) | Bézier service tubing and physically metered filament delivery (`filament.js`) | [fabrication](../tools-guides/fabrication.md) |
| [filament\_path.py](../blender/eidoblend/fabrication/filament_path.py) | Retraction and prime dwells, conserved filament volume (`filament_path.js`) | [fabrication](../tools-guides/fabrication.md) |
| [cutting.py](../blender/eidoblend/fabrication/cutting.py) | Material-aware 2.5D stock sampling, surface finishes and cutting debris (`cutting.js`) | [fabrication](../tools-guides/fabrication.md) |
| [cutter\_sweep.py](../blender/eidoblend/fabrication/cutter_sweep.py) | Stock intersections with swept flat and ball-nose cutters (`cutter_sweep.js`) | [fabrication](../tools-guides/fabrication.md) |
| [cutter\_nodes.py](../blender/eidoblend/fabrication/cutter_nodes.py) | The swept cutter's envelope in Geometry Nodes (`cutter_nodes.js`) | [fabrication](../tools-guides/fabrication.md) |
| [relief.py](../blender/eidoblend/fabrication/relief.py) | Sampled three-axis relief planning in stock coordinates (`relief.js`) | [fabrication](../tools-guides/fabrication.md) |
| [mesh\_slices.py](../blender/eidoblend/fabrication/mesh_slices.py) | Closed cross-sections with holes, and the union of overlapping meshes (`mesh_slices.js`) | [fabrication](../tools-guides/fabrication.md) |
| [polygon\_union.py](../blender/eidoblend/fabrication/polygon_union.py) | The union of planar polygons with holes, for the slicer | [fabrication](../tools-guides/fabrication.md) |
| [source\_geometry.py](../blender/eidoblend/fabrication/source_geometry.py) | One-time geometry snapshots of a source for manufacturing (`source_geometry.js`) | [fabrication](../tools-guides/fabrication.md) |
| [manufacturing\_samples.py](../blender/eidoblend/fabrication/manufacturing_samples.py) | The examples' ordinary source meshes (`manufacturing_samples.js`) | [fabrication](../tools-guides/fabrication.md) |
| [three\_geometry.py](../blender/eidoblend/fabrication/three_geometry.py) | three.js r184 primitive geometries, vertex for vertex, as Blender meshes | [fabrication](../tools-guides/fabrication.md) |
| [examples.py](../blender/eidoblend/fabrication/examples.py) | The manufacturing, relief and mesh-fabrication examples | [fabrication](../tools-guides/fabrication.md) |
| [scenes/manufacturing.py](../blender/eidoblend/fabrication/scenes/manufacturing.py) | Scene script (with its `.json`): FDM, CNC and relief CNC side by side, an 18 s time-lapse | [fabrication](../tools-guides/fabrication.md) |
| [scenes/relief.py](../blender/eidoblend/fabrication/scenes/relief.py) | Scene script (with its `.json`): three-axis carving, roughing then finishing a crest in hardwood | [fabrication](../tools-guides/fabrication.md) |
| [scenes/mesh\_fabrication.py](../blender/eidoblend/fabrication/scenes/mesh_fabrication.py) | Scene script (with its `.json`): the stock-rotating CNC carving an ordinary object in wood | [fabrication](../tools-guides/fabrication.md), [rotary-carving](../tools-guides/rotary-carving.md) |
| [\_axes.py](../blender/eidoblend/fabrication/_axes.py) | Private helpers: axes, colours, plain records | [fabrication](../tools-guides/fabrication.md) |
| [\_keys.py](../blender/eidoblend/fabrication/_keys.py) | Bulk keys written straight into F-curves | [fabrication](../tools-guides/fabrication.md) |
| [\_nodes.py](../blender/eidoblend/fabrication/_nodes.py) | An expression layer over node trees, so the TSL graphs port as code | [fabrication](../tools-guides/fabrication.md) |
| [rotary/\_\_init\_\_.py](../blender/eidoblend/fabrication/rotary/__init__.py) | All-around carving on the G430 XYZ + A assembly | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/carve.py](../blender/eidoblend/fabrication/rotary/carve.py) | `rotary_carve`: a freestanding rotary carving job (`rotary.js`) | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/path.py](../blender/eidoblend/fabrication/rotary/path.py) | Indexed XYZ + A milling about the stock's axis (`rotary_path.js`) | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/mesh.py](../blender/eidoblend/fabrication/rotary/mesh.py) | Indexed XYZ rasters from a source's triangles (`rotary_mesh.js`) | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/setup.py](../blender/eidoblend/fabrication/rotary/setup.py) | The rotary fixture's setup datums (`rotary_setup.js`) | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/removal.py](../blender/eidoblend/fabrication/rotary/removal.py) | Volumetric engagement sampling for the chip events (`rotary_removal.js`) | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/sweeps.py](../blender/eidoblend/fabrication/rotary/sweeps.py) | Swept-cutter geometry over many points, and the program's spatial stroke index | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/stock.py](../blender/eidoblend/fabrication/rotary/stock.py) | The carved stock: solid subtraction with seekable history (`rotary_stock.js`) | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/examples.py](../blender/eidoblend/fabrication/rotary/examples.py) | The rotary and rotary metal examples | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/scenes/rotary.py](../blender/eidoblend/fabrication/rotary/scenes/rotary.py) | Scene script (with its `.json`): a rotary carving study in hardwood | [rotary-carving](../tools-guides/rotary-carving.md) |
| [rotary/scenes/rotary\_metal.py](../blender/eidoblend/fabrication/rotary/scenes/rotary_metal.py) | Scene script (with its `.json`): aluminium rotary milling at physical speed, then a time-lapse finish | [rotary-carving](../tools-guides/rotary-carving.md) |

### Vegetation (`eidoblend.flora`) and trees (`eidoblend.trees`)

| Module | Role | Instructions |
| --- | --- | --- |
| [flora/\_\_init\_\_.py](../blender/eidoblend/flora/__init__.py) | `create_flora`, the vegetation brush | [vegetation](../tools-guides/vegetation.md) |
| [flora/vegetation.py](../blender/eidoblend/flora/vegetation.py) | `create_flora`'s planning half: species, generators, placement (`vegetation.js`) | [vegetation](../tools-guides/vegetation.md) |
| [flora/field.py](../blender/eidoblend/flora/field.py) | The Blender half: plans a stroke and builds it | [vegetation](../tools-guides/vegetation.md) |
| [flora/nodes.py](../blender/eidoblend/flora/nodes.py) | The field's Geometry Nodes (instancing, three-layer wind, pushers) and its leaf and bark materials | [vegetation](../tools-guides/vegetation.md) |
| [flora/plantgeo.py](../blender/eidoblend/flora/plantgeo.py) | One plant's geometry and its conversion into a Blender mesh | [vegetation](../tools-guides/vegetation.md) |
| [flora/jsmath.py](../blender/eidoblend/flora/jsmath.py) | JS-exact maths and RNGs, so one seed grows the same stand | [vegetation](../tools-guides/vegetation.md) |
| [flora/three\_math.py](../blender/eidoblend/flora/three_math.py) | three.js Vector3 / Quaternion semantics in plain Python | [vegetation](../tools-guides/vegetation.md) |
| [flora/vegetation\_corn\_gen.py](../blender/eidoblend/flora/vegetation_corn_gen.py) | The corn plant generator | [vegetation](../tools-guides/vegetation.md) |
| [flora/vegetation\_daisy\_gen.py](../blender/eidoblend/flora/vegetation_daisy_gen.py) | The daisy generator (oxeye, Shasta) | [vegetation](../tools-guides/vegetation.md) |
| [flora/vegetation\_shrub\_gen.py](../blender/eidoblend/flora/vegetation_shrub_gen.py) | The Mojave shrubs (blackbrush, creosote, sagebrush) | [vegetation](../tools-guides/vegetation.md) |
| [flora/vegetation\_sunflower\_gen.py](../blender/eidoblend/flora/vegetation_sunflower_gen.py) | The sunflower generator | [vegetation](../tools-guides/vegetation.md) |
| [trees/\_\_init\_\_.py](../blender/eidoblend/trees/__init__.py) | `make_seed_tree` | [trees](../tools-guides/trees.md) |
| [trees/seedthree\_api.py](../blender/eidoblend/trees/seedthree_api.py) | SeedThree's trees and plants in a film scene, through SeedThree's Blender add-on | [trees](../tools-guides/trees.md) |

### Effects (`eidoblend.fx`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/fx/__init__.py) | Liquids, fire, particles, the particle morph (dissolve and reform anything), cloth, iso fields, free-surface water, flat water, 2D dye fluids | [liquids](../tools-guides/liquids.md), [volume-fire](../tools-guides/volume-fire.md), [particles-fx](../tools-guides/particles-fx.md), [free-surface-water](../tools-guides/free-surface-water.md) |
| [swe.py](../blender/eidoblend/fx/swe.py) | Shallow-water liquid (`fluid_swe.js`): terrain water, pours, droplets, foam, erosion | [liquids](../tools-guides/liquids.md) |
| [\_swe\_solver.py](../blender/eidoblend/fx/_swe_solver.py) | The shallow-water solver, kernel for kernel, in numpy | [liquids](../tools-guides/liquids.md) |
| [water\_flat.py](../blender/eidoblend/fx/water_flat.py) | Flat reflective water and the sky above it (WaterMesh, SkyMesh), and the rippling pool (`water_compute.js`) | [liquids](../tools-guides/liquids.md) |
| [stable\_fluids.py](../blender/eidoblend/fx/stable_fluids.py) | 2D screen-space stable fluids: ink and dye (`fluid_sim.js`) | [liquids](../tools-guides/liquids.md) |
| [water3d/\_\_init\_\_.py](../blender/eidoblend/fx/water3d/__init__.py) | Eulerian free-surface water (`fluid_water.js`) | [free-surface-water](../tools-guides/free-surface-water.md) |
| [water3d/water.py](../blender/eidoblend/fx/water3d/water.py) | `create_water_sim`: the water baked to a mesh sequence | [free-surface-water](../tools-guides/free-surface-water.md) |
| [water3d/solver.py](../blender/eidoblend/fx/water3d/solver.py) | The GPU solver on Blender's `gpu` compute | [free-surface-water](../tools-guides/free-surface-water.md) |
| [water3d/\_kernels.py](../blender/eidoblend/fx/water3d/_kernels.py) | The solver's compute kernels as GLSL | [free-surface-water](../tools-guides/free-surface-water.md) |
| [water3d/surface.py](../blender/eidoblend/fx/water3d/surface.py) | The surface each baked frame, as a mesh | [free-surface-water](../tools-guides/free-surface-water.md) |
| [water3d/material.py](../blender/eidoblend/fx/water3d/material.py) | The water's look in EEVEE | [free-surface-water](../tools-guides/free-surface-water.md) |
| [fire.py](../blender/eidoblend/fx/fire.py) | Volume fire and smoke from burning mesh emitters (`fluid_grid.js`) | [volume-fire](../tools-guides/volume-fire.md) |
| [\_gpu.py](../blender/eidoblend/fx/_gpu.py) | GLSL compute through Blender's `gpu` module: the family's GPU bakes | [volume-fire](../tools-guides/volume-fire.md), [free-surface-water](../tools-guides/free-surface-water.md) |
| [\_noise.py](../blender/eidoblend/fx/_noise.py) | The engine's noise functions, number for number (numpy) | [volume-fire](../tools-guides/volume-fire.md) |
| [cloth.py](../blender/eidoblend/fx/cloth.py) | `create_cloth_panel`: mass-spring cloth panels (`cloth_sim.js`) | [cloth](../tools-guides/cloth.md) |
| [particles.py](../blender/eidoblend/fx/particles.py) | `make_particles`: billboard particles on the 80-sprite library (`particles.js`) | [particles-fx](../tools-guides/particles-fx.md) |
| [particle\_morph.py](../blender/eidoblend/fx/particle_morph.py) | `make_particle_morph`, `ParticleMorph`, `ascii_panel` (`particle_morph.js`, `ascii_panel.js`) | [particles-fx](../tools-guides/particles-fx.md) |
| [particle\_targets.py](../blender/eidoblend/fx/particle_targets.py) | Morph targets from anything (objects, files, VRMs and their clips, images, text, shapes), in their own colours | [particles-fx](../tools-guides/particles-fx.md) |
| [iso\_field.py](../blender/eidoblend/fx/iso_field.py) | `make_iso_field`: CPU-written scalar fields as isosurfaces (`iso_field.js`) | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [\_look.py](../blender/eidoblend/fx/_look.py) | The engine's display, matched under the film's view transform | [particles-fx](../tools-guides/particles-fx.md), [volume-fire](../tools-guides/volume-fire.md) |
| [\_nodes.py](../blender/eidoblend/fx/_nodes.py) | An expression layer over node trees, so a TSL shader ports as code | [particles-fx](../tools-guides/particles-fx.md) |
| [\_util.py](../blender/eidoblend/fx/_util.py) | Private helpers: axes, colours, the scene clock, seeded randomness, cache files | [liquids](../tools-guides/liquids.md) |

### The look (`eidoblend.look`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/look/__init__.py) | Cameras, lights, the EEVEE look presets, the post chain, exposure, review tools | [camera-lighting](../tools-guides/camera-lighting.md) |
| [camera.py](../blender/eidoblend/look/camera.py) | Cameras for film shots: targets and framing, moves baked to keys, depth of field and focus pulls | [camera-lighting](../tools-guides/camera-lighting.md) |
| [camera\_safety.py](../blender/eidoblend/look/camera_safety.py) | `CameraSafety`: sightlines, clearance, the whole animated path checked | [camera-lighting](../tools-guides/camera-lighting.md) |
| [camera\_audit.py](../blender/eidoblend/look/camera_audit.py) | The camera audits per shot: bounce, framing, focus | [render-review](../tools-guides/render-review.md) |
| [lighting.py](../blender/eidoblend/look/lighting.py) | Lights for EEVEE: units, the sun, key / fill / rim, practicals, ray-traced lighting, light probes and their bake | [camera-lighting](../tools-guides/camera-lighting.md) |
| [stage\_rig.py](../blender/eidoblend/look/stage_rig.py) | Stage lights built with their fixtures, aimed by construction | [camera-lighting](../tools-guides/camera-lighting.md) |
| [exposure.py](../blender/eidoblend/look/exposure.py) | Exposure chosen by measurement and confirmed with real renders | [camera-lighting](../tools-guides/camera-lighting.md) |
| [render\_settings.py](../blender/eidoblend/look/render_settings.py) | The EEVEE look as presets (`apply_auto_enhance`), and `summary` of what a scene will render | [postprocessing](../tools-guides/postprocessing.md), [render-review](../tools-guides/render-review.md) |
| [probe.py](../blender/eidoblend/look/probe.py) | Probe stills from a scene at given times, each one measured | [render-review](../tools-guides/render-review.md) |
| [probe\_cli.py](../blender/eidoblend/look/probe_cli.py) | CLI: probe stills from a saved `.blend` | [render-review](../tools-guides/render-review.md) |
| [frame\_stats.py](../blender/eidoblend/look/frame_stats.py) | CLI and module: what rendered frames measure as (highlights, black and frozen frames, luma jumps), contact sheets | [render-review](../tools-guides/render-review.md) |
| [overlap.py](../blender/eidoblend/look/overlap.py) | Exact mesh-against-mesh interpenetration of the posed meshes | [render-review](../tools-guides/render-review.md) |
| [audit.py](../blender/eidoblend/look/audit.py) | The look family's audit ledger for checks run outside the runner | [render-review](../tools-guides/render-review.md) |
| [post/\_\_init\_\_.py](../blender/eidoblend/look/post/__init__.py) | The post chain (its slots prebloom, bloom, under, overlay, over), the effect registry and its passes | [postprocessing](../tools-guides/postprocessing.md) |
| [post/chain.py](../blender/eidoblend/look/post/chain.py) | The compositor graph in a fixed order, the WebGPU post chain's | [postprocessing](../tools-guides/postprocessing.md) |
| [post/custom\_effects.py](../blender/eidoblend/look/post/custom_effects.py) | The effect registry: every WebGPU effect by name, `apply_to` / `register` | [postprocessing](../tools-guides/postprocessing.md) |
| [post/screen\_effects.py](../blender/eidoblend/look/post/screen_effects.py) | The registry's screen-space effects, each a compositor group | [postprocessing](../tools-guides/postprocessing.md) |
| [post/era\_looks.py](../blender/eidoblend/look/post/era_looks.py) | Graphic-arts looks from the history of computing, as weights on one pass | [postprocessing](../tools-guides/postprocessing.md) |
| [post/aeropittura.py](../blender/eidoblend/look/post/aeropittura.py) | The Futurist aeropittura painting pass | [postprocessing](../tools-guides/postprocessing.md) |
| [post/after\_image.py](../blender/eidoblend/look/post/after_image.py) | `after_image`: a frame-feedback trail | [postprocessing](../tools-guides/postprocessing.md) |
| [post/history.py](../blender/eidoblend/look/post/history.py) | Earlier frames inside the compositor, through the disk, across cuts | [postprocessing](../tools-guides/postprocessing.md) |
| [post/display.py](../blender/eidoblend/look/post/display.py) | Display space inside the compositor: the view transform and its inverse, kept synced | [postprocessing](../tools-guides/postprocessing.md) |
| [post/\_graph.py](../blender/eidoblend/look/post/_graph.py) | An expression layer over compositor node groups, so a TSL pass ports as code | [postprocessing](../tools-guides/postprocessing.md) |

### Procedural materials (`eidoblend.materials`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/materials/__init__.py) | Procedural textures and PBR material factories | [procedural-materials](../tools-guides/procedural-materials.md) |
| [procedural.py](../blender/eidoblend/materials/procedural.py) | `procedural_materials.js`: generators, height-to-normal, compositing, the six factories | [procedural-materials](../tools-guides/procedural-materials.md) |
| [\_gen.py](../blender/eidoblend/materials/_gen.py) | The canvas maths in numpy (no bpy) | [procedural-materials](../tools-guides/procedural-materials.md) |

### Screens, type, books and sound (`eidoblend.media`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/media/__init__.py) | Screens, type, overlays, subtitles, books and sound | [motion-graphics](../tools-guides/motion-graphics.md) |
| [screens.py](../blender/eidoblend/media/screens.py) | In-world screens: canvas content and video atlases on real displays (`screen.js`) | [motion-graphics](../tools-guides/motion-graphics.md) |
| [canvas\_scenes.py](../blender/eidoblend/media/canvas_scenes.py) | The canvas screen scenes without Blender: list, preview, contact sheets, bench, NaN sweep | [motion-graphics](../tools-guides/motion-graphics.md) |
| [raster.py](../blender/eidoblend/media/raster.py) | 2D drawing for screens and textures: canvases, the bundled fonts, `draw_text_fit` | [motion-graphics](../tools-guides/motion-graphics.md) |
| [overlay.py](../blender/eidoblend/media/overlay.py) | The overlay layer (`makeOverlayLayer`), subtitles and the edit scene; `chain_overlay` | [motion-graphics](../tools-guides/motion-graphics.md) |
| [parole.py](../blender/eidoblend/media/parole.py) | Parole-in-libertà lyric captions and quotes in the overlay layer | [motion-graphics](../tools-guides/motion-graphics.md) |
| [lyrics.py](../blender/eidoblend/media/lyrics.py) | Lyric subtitles drawn on frames (`lyric_renderer.py`'s `LyricRenderer`) | [motion-graphics](../tools-guides/motion-graphics.md) |
| [text3d.py](../blender/eidoblend/media/text3d.py) | Extruded type with real materials (`text_3d.js`), and title cards | [motion-graphics](../tools-guides/motion-graphics.md) |
| [book.py](../blender/eidoblend/media/book.py) | Hardcover books: the engine's own rig (`book_core.js`), posed in Deno, built and cached in Blender | [books](../tools-guides/books.md) |
| [audio.py](../blender/eidoblend/media/audio.py) | Sound strips, markers, mixdown, and visemes keyed onto a VRM's face | [audio](../tools-guides/audio.md) |
| [weather\_audio.py](../blender/eidoblend/media/weather_audio.py) | The weather-audio recorder over Blender frames (`weather_audio.js`) | [weather-effects](../tools-guides/weather-effects.md), [audio](../tools-guides/audio.md) |
| [timebase.py](../blender/eidoblend/media/timebase.py) | Frames and film seconds, and the timing files the media tools read (no bpy) | [audio](../tools-guides/audio.md) |
| [js/book\_export.mjs](../blender/eidoblend/media/js/book_export.mjs) | Deno helper: the book rig posed per frame | [books](../tools-guides/books.md) |
| [js/canvas\_bake.mjs](../blender/eidoblend/media/js/canvas_bake.mjs) | Deno helper: canvas screen frames baked to images | [motion-graphics](../tools-guides/motion-graphics.md) |
| [js/canvas\_scenes.mjs](../blender/eidoblend/media/js/canvas_scenes.mjs) | Deno helper behind `canvas_scenes.py` | [motion-graphics](../tools-guides/motion-graphics.md) |
| [js/parole\_export.mjs](../blender/eidoblend/media/js/parole_export.mjs) | Deno helper: the parole layout posed per frame | [motion-graphics](../tools-guides/motion-graphics.md) |

### Placement (`eidoblend.placement`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/placement/__init__.py) | Seating things on things, and the placement audits (`scene_placement.js`, `model_kit.js`) | [placement](../tools-guides/placement.md) |
| [helpers.py](../blender/eidoblend/placement/helpers.py) | Intent-based placement helpers: `place_on`, `place_against`, `place_touching`, `snap_to_ground` and the rest | [placement](../tools-guides/placement.md) |
| [audits.py](../blender/eidoblend/placement/audits.py) | The placement audits run after a build, before the render | [placement](../tools-guides/placement.md) |
| [seating.py](../blender/eidoblend/placement/seating.py) | `seat_on`, `sit_on_ground`, `emote`, `face_camera`, `unseat`, the seat pan and the chair's facing, for a VRM nothing drives | [placement](../tools-guides/placement.md), [maneuvers](../tools-guides/maneuvers.md) |
| [motion.py](../blender/eidoblend/placement/motion.py) | `drive_along`: a vehicle or creature along a path, heading coupled to travel | [placement](../tools-guides/placement.md) |
| [model\_kit.py](../blender/eidoblend/placement/model_kit.py) | `load_kit`: a modular kit GLB used part by part | [placement](../tools-guides/placement.md) |
| [\_world.py](../blender/eidoblend/placement/_world.py) | World-space geometry queries the helpers and audits share | [placement](../tools-guides/placement.md) |
| [\_curves.py](../blender/eidoblend/placement/_curves.py) | three.js's CatmullRomCurve3 with its arc-length tables (no bpy) | [placement](../tools-guides/placement.md) |

### Props (`eidoblend.props`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/props/__init__.py) | The DAISY props by name: eight historical voice machines (1939–2001) and the 1896 tandem; the era kit for new props in their style | [voice-machines](../tools-guides/voice-machines.md), [props-and-sets](../tools-guides/props-and-sets.md) |
| [tandem.py](../blender/eidoblend/props/tandem.py) | The 1896 tandem, its VRM rider rig and springs, the teapot stoker | [props-and-sets](../tools-guides/props-and-sets.md) |
| [voice\_machines/\_\_init\_\_.py](../blender/eidoblend/props/voice_machines/__init__.py) | The registry (`build(name)`), the screens and the era-2 kit the machines share | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/voder.py](../blender/eidoblend/props/voice_machines/voder.py) | The 1939 Voder, and the era-1 craft kit (role materials, a 2D canvas, three geometries, the keyer) | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/mainframe.py](../blender/eidoblend/props/voice_machines/mainframe.py) | The 1961 computer room | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/teletype.py](../blender/eidoblend/props/voice_machines/teletype.py) | The 1966 ASR-33 on its pedestal | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/speakspell.py](../blender/eidoblend/props/voice_machines/speakspell.py) | The 1978 Speak & Spell | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/c64.py](../blender/eidoblend/props/voice_machines/c64.py) | The 1982 home computer and its monitor | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/dectalk.py](../blender/eidoblend/props/voice_machines/dectalk.py) | The 1984 desktop speech synthesizer | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/mac1984.py](../blender/eidoblend/props/voice_machines/mac1984.py) | The 1984 all-in-one compact, its keyboard and mouse | [voice-machines](../tools-guides/voice-machines.md) |
| [voice\_machines/desktop2001.py](../blender/eidoblend/props/voice_machines/desktop2001.py) | The 2001 desktop PC: tower, CRT, speakers, keyboard, mouse | [voice-machines](../tools-guides/voice-machines.md) |

### The SDF engine (`eidoblend.sdf`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/sdf/__init__.py) | GLSL solids meshed by sparse GPU dual contouring (`create_sdf_object`), SDF volumes as OpenVDB (`create_sdf_volume`), SDF screens (`make_sdf_texture`, `make_explosion_texture`), the `EXAMPLES` and `register_example`, rhombic dodecahedron voxels | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [solid.py](../blender/eidoblend/sdf/solid.py) | `create_sdf_object`: an SDF solid as real EEVEE geometry | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [mesher.py](../blender/eidoblend/sdf/mesher.py) | Sparse dual contouring of a signed distance field | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [gpu\_eval.py](../blender/eidoblend/sdf/gpu_eval.py) | `SdfProgram`: an example's GLSL compiled into Blender's GPU module, evaluated over points | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [glsl\_lib.py](../blender/eidoblend/sdf/glsl_lib.py) | The engine's GLSL primitive library and the edition's prelude | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [np\_lib.py](../blender/eidoblend/sdf/np_lib.py) | The primitive library over numpy, for SDFs written in Python | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [materials.py](../blender/eidoblend/sdf/materials.py) | The Principled material a solid renders with, its `surface()` channels baked | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [spec.py](../blender/eidoblend/sdf/spec.py) | The SDF spec, the quality presets, the `EXAMPLES` registry | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [examples\_solids.py](../blender/eidoblend/sdf/examples_solids.py) | The solid `EXAMPLES` | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [texture.py](../blender/eidoblend/sdf/texture.py) | `make_sdf_texture` and `make_explosion_texture`: SDFs raymarched into images | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [volume.py](../blender/eidoblend/sdf/volume.py) | `create_sdf_volume`: a participating-medium SDF as a Blender Volume | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [rhombic\_dodecahedron.py](../blender/eidoblend/sdf/rhombic_dodecahedron.py) | Rhombic dodecahedron voxels (`rhombic_dodecahedron.js`) | [sdf-volumes](../tools-guides/sdf-volumes.md), [geometry](../tools-guides/geometry.md) |
| [helper.py](../blender/eidoblend/sdf/helper.py) | `register_sdf_helper` and `help()`, the engine's discoverable API reference | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [examples\_volumes.py](../blender/eidoblend/sdf/examples_volumes.py) | The volume `EXAMPLES` (explosions, fire, smoke), the lamps their emission casts, the froxel range | [sdf-explosions](../tools-guides/sdf-explosions.md) |
| [nuclear\_explosion.py](../blender/eidoblend/sdf/nuclear_explosion.py) | The mushroom cloud as volumes, baked over the scene's range, glow lamps keyed | [sdf-explosions](../tools-guides/sdf-explosions.md) |
| [examples\_vehicles.py](../blender/eidoblend/sdf/examples_vehicles.py) | The vehicle `EXAMPLES` | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |
| [vehicles/\_\_init\_\_.py](../blender/eidoblend/sdf/vehicles/__init__.py) | The four vehicles, built for EEVEE | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |
| [vehicles/vehicle.py](../blender/eidoblend/sdf/vehicles/vehicle.py) | The vehicles' `make()`: a film-ready Blender object | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |
| [vehicles/parts.py](../blender/eidoblend/sdf/vehicles/parts.py) | What every part is made of, and the options' colour parsing | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |
| [vehicles/shading.py](../blender/eidoblend/sdf/vehicles/shading.py) | One Principled material per part, every pattern drawn per pixel | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |
| [vehicles/livery.py](../blender/eidoblend/sdf/vehicles/livery.py) | The cyberpunk sedan's racing-stripe livery as decal images | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |
| [vehicles/badge.py](../blender/eidoblend/sdf/vehicles/badge.py) | The cyberpunk sedan's badge decal | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |
| [vehicles/lamps.py](../blender/eidoblend/sdf/vehicles/lamps.py) | The vehicles' real lamps, parented to the body | [sdf-vehicles](../tools-guides/sdf-vehicles.md) |

### Scenes from the music videos (`eidoblend.sets`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/sets/__init__.py) | The registry of the DAISY and UNKNOWN FORCE scenes (`sets.list` / `get` / `build` / `register`), each loaded on first use | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/\_\_init\_\_.py](../blender/eidoblend/sets/daisy/__init__.py) | The DAISY scenes, their looks (`STATES`) and their default clock | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/funeral.py](../blender/eidoblend/sets/daisy/funeral.py) | A SoMa warehouse vigil: mourners, candles, the bier, phones in the dark | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/bridge.py](../blender/eidoblend/sets/daisy/bridge.py) | The Golden Gate in fog | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/corner.py](../blender/eidoblend/sets/daisy/corner.py) | A corner room with a lamp and a laptop, and a camp in the woods with a march and a fire | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/\_\_init\_\_.py](../blender/eidoblend/sets/daisy/ocean/__init__.py) | A headland at night above a sea made of faces, as a reusable scene on your own clock | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/staging.py](../blender/eidoblend/sets/daisy/ocean/staging.py) | The scene's build, `update` and `animate` (`ocean.js`) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/sea.py](../blender/eidoblend/sets/daisy/ocean/sea.py) | The ocean of faces | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/faces\_atlas.py](../blender/eidoblend/sets/daisy/ocean/faces_atlas.py) | The atlas of drawn faces the sea is made of | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/land.py](../blender/eidoblend/sets/daisy/ocean/land.py) | The shore | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/daisies.py](../blender/eidoblend/sets/daisy/ocean/daisies.py) | Daisies on the rise (the flora family's daisy) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/house.py](../blender/eidoblend/sets/daisy/ocean/house.py) | The small house on the spit, its window and porch light | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/pages.py](../blender/eidoblend/sets/daisy/ocean/pages.py) | Two constitution pages held in the air | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/apparitions.py](../blender/eidoblend/sets/daisy/ocean/apparitions.py) | A robot and a human of light that rise from the sea and dissolve | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/echoes.py](../blender/eidoblend/sets/daisy/ocean/echoes.py) | Faint distant lights over the sea | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/perform.py](../blender/eidoblend/sets/daisy/ocean/perform.py) | Gestures layered over a performer's clip: a hand to the flower, a head turning to a point | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/keys.py](../blender/eidoblend/sets/daisy/ocean/keys.py) | How the scene's channels are keyed | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/util.py](../blender/eidoblend/sets/daisy/ocean/util.py) | Small shared helpers (`util.js`) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/\_billboards.py](../blender/eidoblend/sets/daisy/ocean/_billboards.py) | Camera-facing billboards as Geometry Nodes | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/\_land\_nodes.py](../blender/eidoblend/sets/daisy/ocean/_land_nodes.py) | The land's material and the dune grass in nodes | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/\_sea\_nodes.py](../blender/eidoblend/sets/daisy/ocean/_sea_nodes.py) | The sea's two node graphs | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/\_nodes.py](../blender/eidoblend/sets/daisy/ocean/_nodes.py) | TSL as code for Geometry Nodes and shader trees | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/\_three.py](../blender/eidoblend/sets/daisy/ocean/_three.py) | The few three.js vector operations the staging uses, on plain tuples | [props-and-sets](../tools-guides/props-and-sets.md) |
| [daisy/ocean/\_bl.py](../blender/eidoblend/sets/daisy/ocean/_bl.py) | Blender plumbing the ocean modules share | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/\_\_init\_\_.py](../blender/eidoblend/sets/unknown_force/__init__.py) | The UNKNOWN FORCE scenes' table (`SETS`), each loaded on first use | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/city.py](../blender/eidoblend/sets/unknown_force/city.py) | A dark cyberpunk megacity at night painted by a Futurist | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/hole.py](../blender/eidoblend/sets/unknown_force/hole.py) | A stage at the bottom of a sunken well in the city's centre | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/citykit.py](../blender/eidoblend/sets/unknown_force/citykit.py) | The kit the city and the well share: towers, signs, rain, the cloud deck, the pillar of light | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/quiet\_room.py](../blender/eidoblend/sets/unknown_force/quiet_room.py) | The quiet room | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/quiet\_room\_art.py](../blender/eidoblend/sets/unknown_force/quiet_room_art.py) | The quiet room's whiteboards, drawn in marker | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/showroom.py](../blender/eidoblend/sets/unknown_force/showroom.py) | The showroom | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/showroom\_art.py](../blender/eidoblend/sets/unknown_force/showroom_art.py) | The showroom's printed and displayed matter | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/interiors\_lib.py](../blender/eidoblend/sets/unknown_force/interiors_lib.py) | The quiet room's and the showroom's shared kit | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/corridor.py](../blender/eidoblend/sets/unknown_force/corridor.py) | A gold corridor of power | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/news.py](../blender/eidoblend/sets/unknown_force/news.py) | The evening news at a data centre | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/cn\_lib.py](../blender/eidoblend/sets/unknown_force/cn_lib.py) | The corridor's and the news' shared helpers, the ACES-like look | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/race.py](../blender/eidoblend/sets/unknown_force/race.py) | A night highway: Sant'Elia towers, billboards, a 1908 racing car, the roadworks | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/bin.py](../blender/eidoblend/sets/unknown_force/bin.py) | A canyon of thrown-away paper with a giant trash can | [props-and-sets](../tools-guides/props-and-sets.md) |
| [unknown\_force/bin\_pages.py](../blender/eidoblend/sets/unknown_force/bin_pages.py) | The canyon's paper: an atlas of invented pages | [props-and-sets](../tools-guides/props-and-sets.md) |

### The sky (`eidoblend.sky`) and the weather (`eidoblend.weather`)

| Module | Role | Instructions |
| --- | --- | --- |
| [sky/\_\_init\_\_.py](../blender/eidoblend/sky/__init__.py) | `make_sky`: the Earth sky, the ringworld (band rendered as a plate behind local geometry, eclipse, ring clouds) and shieldworld (red giant, hex shield, shattered moon) packages, the sun corona, the asteroid moon pipeline, custom celestial clusters, the cloud dome, and weather | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/worlds.py](../blender/eidoblend/sky/worlds.py) | The three sky worlds; one key selects a whole world | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/sky\_system.py](../blender/eidoblend/sky/sky_system.py) | The sky's state machine: time of day, cloud presets and transitions, colour channels, lights | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/palette.py](../blender/eidoblend/sky/palette.py) | The time-of-day palette, cloud presets and sun / moon paths | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/weather\_system.py](../blender/eidoblend/sky/weather_system.py) | Weather states and their coupling to the sky | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/bake/\_\_init\_\_.py](../blender/eidoblend/sky/bake/__init__.py) | The ported sky shader and its baker | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/bake/baker.py](../blender/eidoblend/sky/bake/baker.py) | Runs the sky shader in Blender's GPU module, once per film frame | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/bake/celestial.py](../blender/eidoblend/sky/bake/celestial.py) | GLSL generated per sky world: the red giant, the shattered moon's dust | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/bake/sky.glsl](../blender/eidoblend/sky/bake/sky.glsl) | The cloud and celestial shader, ported line for line | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/world\_nodes.py](../blender/eidoblend/sky/world_nodes.py) | The EEVEE world that shows the baked sky and lights the scene with it | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/sky\_view.py](../blender/eidoblend/sky/sky_view.py) | The bake camera's projection, shared by every material that reads a camera layer | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/cloud\_shadows.py](../blender/eidoblend/sky/cloud_shadows.py) | Cloud shadows carried by EEVEE's own sun shadows | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/cloud\_dome.py](../blender/eidoblend/sky/cloud_dome.py) | The cloud dome over distant geometry | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/cloud\_spatial.py](../blender/eidoblend/sky/cloud_spatial.py) | The balanced tier's spatial sky downsample | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/fog.py](../blender/eidoblend/sky/fog.py) | Distance fog in the sky's colour | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/nodes.py](../blender/eidoblend/sky/nodes.py) | Shader-node building for the sky worlds' materials | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/ringworld.py](../blender/eidoblend/sky/ringworld.py) | The ringworld band | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/ring\_materials.py](../blender/eidoblend/sky/ring_materials.py) | The ringworld's materials | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/redgiant.py](../blender/eidoblend/sky/redgiant.py) | The shieldworld's red giant and planetary shield | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/asteroid\_moon.py](../blender/eidoblend/sky/asteroid_moon.py) | The asteroid moon pipeline and the shattered moon | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/moon\_materials.py](../blender/eidoblend/sky/moon_materials.py) | The shattered moon's materials and its debris river | [sky-weather](../tools-guides/sky-weather.md) |
| [sky/sun\_corona.py](../blender/eidoblend/sky/sun_corona.py) | A corona of light-petals around the sun (`sun_corona.js`) | [sky-weather](../tools-guides/sky-weather.md) |
| [weather/\_\_init\_\_.py](../blender/eidoblend/weather/__init__.py) | `make_weather_system`, `make_weather_audio`: rain streaks and splashes, wet ground and puddles, lightning, the weather audio track | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/system.py](../blender/eidoblend/weather/system.py) | `make_weather_system` on top of the sky package (`weather_system.js`) | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/rain.py](../blender/eidoblend/weather/rain.py) | World-space rain streaks and ground splashes, as Geometry Nodes | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/wet.py](../blender/eidoblend/weather/wet.py) | Wetness and puddles in front of each Principled BSDF | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/moisture.py](../blender/eidoblend/weather/moisture.py) | The 2D moisture history (numpy) | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/shelter.py](../blender/eidoblend/weather/shelter.py) | Rain exposure for wet surfaces, as a world-space map | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/lightning.py](../blender/eidoblend/weather/lightning.py) | Lightning's deterministic profile and its scheduler (plain Python) | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/bolt.py](../blender/eidoblend/weather/bolt.py) | The visible lightning channel | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/strike.py](../blender/eidoblend/weather/strike.py) | The strike light, the bolt ribbons, sparks, smoke puffs and scorch, keyed | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/audio.py](../blender/eidoblend/weather/audio.py) | The weather audio timeline, and the tools that render and mux it | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/frame.py](../blender/eidoblend/weather/frame.py) | Per-frame weather values as plain functions | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/values.py](../blender/eidoblend/weather/values.py) | The weather's per-frame shader values in one keyed node group | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/keys.py](../blender/eidoblend/weather/keys.py) | Bulk keys through Blender 5.2's layered actions | [weather-effects](../tools-guides/weather-effects.md) |
| [weather/\_graph.py](../blender/eidoblend/weather/_graph.py) | Node-graph helpers and the weather's hash and noise functions | [weather-effects](../tools-guides/weather-effects.md) |

### Terrain (`eidoblend.terrain`)

| Package | Role | Instructions |
| --- | --- | --- |
| [blender/eidoblend/terrain/](../blender/eidoblend/terrain/__init__.py) | The terrain family: `make_terrain` (landforms made by their processes on the GPU from 16 recipes, real elevation data refined by `real_place`, levels from the horizon down to 0.25-0.5 m around the camera, the ring mesh, its masks, palettes and rocks; `bake.py` from the command line), the surface layers, parallax relief, loft | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |

### WebXR (`eidoblend.xr`)

| Module | Role | Instructions |
| --- | --- | --- |
| [\_\_init\_\_.py](../blender/eidoblend/xr/__init__.py) | WebXR from Blender: a scene exported to a GLB bundle the kit's headset page plays, the page template, the kit's server and stills, Blender's own VR session landmarks | [webxr](../tools-guides/webxr.md) |
| [export.py](../blender/eidoblend/xr/export.py) | `export_xr`: a Blender scene to an XR bundle | [webxr](../tools-guides/webxr.md) |
| [export\_cli.py](../blender/eidoblend/xr/export_cli.py) | CLI (inside Blender): a built `.blend` to an XR bundle, headless | [webxr](../tools-guides/webxr.md) |
| [materials.py](../blender/eidoblend/xr/materials.py) | Materials that survive the glTF exporter; `bake_for_gltf` bakes the rest | [webxr](../tools-guides/webxr.md) |
| [motion.py](../blender/eidoblend/xr/motion.py) | Animation that survives the glTF exporter | [webxr](../tools-guides/webxr.md) |
| [world.py](../blender/eidoblend/xr/world.py) | The scene's world as an equirectangular image the page draws and lights with | [webxr](../tools-guides/webxr.md) |
| [choreo.py](../blender/eidoblend/xr/choreo.py) | A piece's data sampled out of a built `.blend` into the JSON a page plays | [webxr](../tools-guides/webxr.md) |
| [glb.py](../blender/eidoblend/xr/glb.py) | A `.glb` read back, plain Python: what an export really holds | [webxr](../tools-guides/webxr.md) |
| [examples.py](../blender/eidoblend/xr/examples.py) | The kit's example as a Blender scene (`EXAMPLES['city']`) | [webxr](../tools-guides/webxr.md) |
| [server.py](../blender/eidoblend/xr/server.py) | CLI and module: the kit's HTTPS server for the edition's pages (no bpy) | [webxr](../tools-guides/webxr.md) |
| [shots.py](../blender/eidoblend/xr/shots.py) | CLI and module: stills of a WebXR page from headless Chrome | [webxr](../tools-guides/webxr.md) |
| [landmarks.py](../blender/eidoblend/xr/landmarks.py) | Standing in the Blender scene itself in a headset (Blender's VR Scene Inspection) | [webxr](../tools-guides/webxr.md) |
| [\_bl.py](../blender/eidoblend/xr/_bl.py) | Small Blender helpers the xr modules share | [webxr](../tools-guides/webxr.md) |
| [page/xr\_page.html](../blender/eidoblend/xr/page/xr_page.html) | The page template a bundle plays in | [webxr](../tools-guides/webxr.md) |

## 2. Tools both editions share

Python tools at the repository root and its Python packages. They run on the
system Python, outside Blender, and serve either edition.

| Source or tool | Role | Instructions |
| --- | --- | --- |
| [fetch_model.py](../fetch_model.py) | CLI: one query over local models, Poly Haven, Smithsonian, NASA and NIH 3D (`--cache`: the shared model library) | [assets](../tools-guides/assets.md) |
| [fetch_texture.py](../fetch_texture.py) | CLI: CC0 PBR sets (`--cache`: the shared texture library) | [assets](../tools-guides/assets.md) |
| [fetch_hdri.py](../fetch_hdri.py) | CLI: environment HDRIs | [assets](../tools-guides/assets.md) |
| [contact_sheet.py](../contact_sheet.py) | CLI: labelled contact sheets of a video | [render-review](../tools-guides/render-review.md) |
| [align_lyrics.py](../align_lyrics.py) | CLI: lyric timestamps from a vocal | [audio](../tools-guides/audio.md) |
| [lipsync.py](../lipsync.py) | Python audio module: per-frame viseme timelines from vocal audio; no CLI | [audio](../tools-guides/audio.md), [claudesona](../tools-guides/claudesona.md) |
| [merge_av.py](../merge_av.py) | CLI: safe muxing of sound onto a render | [audio](../tools-guides/audio.md) · [weather-effects](../tools-guides/weather-effects.md) |
| [bake_weather_audio.py](../bake_weather_audio.py) | CLI: a weather audio timeline baked to a stereo WAV | [sky-weather](../tools-guides/sky-weather.md) · [weather-effects](../tools-guides/weather-effects.md) |
| [generate_song.py](../generate_song.py) | MiniMax Music 3 generator (local ComfyUI) | [audio](../tools-guides/audio.md) |
| [generate_sfx.py](../generate_sfx.py) | CLI: Stable Audio effects and ambiences (local ComfyUI) | [audio](../tools-guides/audio.md) |
| [cyborg_stutter.py](../cyborg_stutter.py) | CLI: spoken character voice filter | [audio](../tools-guides/audio.md) |
| [cyborg_voice.py](../cyborg_voice.py) | CLI: sung character voice filter | [audio](../tools-guides/audio.md) |
| [eidoverse/comfy_bridge.py](../eidoverse/comfy_bridge.py) | Optional TCP bridge service to a host ComfyUI | [audio](../tools-guides/audio.md) |
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
| [eidoverse/examples/daisy/song.py](../eidoverse/examples/daisy/song.py) | Worked example: a complete song with voicebox + synthkit | [voicebox](../tools-guides/voicebox.md) |
| [eidoverse/examples/daisy/captions.py](../eidoverse/examples/daisy/captions.py) | Example CLI: timeline to ASS subtitles, lyric preview | [voicebox](../tools-guides/voicebox.md) |
| [eidoverse/examples/daisy/analyze.py](../eidoverse/examples/daisy/analyze.py) | Example CLI: section-by-section mix measurement | [synthkit](../tools-guides/synthkit.md) |
| [eidoverse/examples/unknown_force/build_timeline.py](../eidoverse/examples/unknown_force/build_timeline.py) | Example CLI: a song's timing spine (beats, sections, lines, gated visemes, documentary clips) | [audio](../tools-guides/audio.md) |
| [eidoverse/examples/unknown_force/transcribe_raw.py](../eidoverse/examples/unknown_force/transcribe_raw.py) | Example CLI: raw Whisper words of a vocal stem, no prompt | [audio](../tools-guides/audio.md) |
| [eidoverse/examples/unknown_force/make_fake_timing.py](../eidoverse/examples/unknown_force/make_fake_timing.py) | Example CLI: lyric words aligned to Whisper's words | [audio](../tools-guides/audio.md) |
| [eidoverse/examples/unknown_force/verify_lines.py](../eidoverse/examples/unknown_force/verify_lines.py) | Example CLI: what a generated song sang (two Whisper sizes + forced alignment) | [audio](../tools-guides/audio.md) |
| [eidoverse/examples/unknown_force/audio/make_doc.py](../eidoverse/examples/unknown_force/audio/make_doc.py) | Example CLI: documentary voices (synthetic anchor, archival, voicebox) | [audio](../tools-guides/audio.md) |
| [eidoverse/examples/unknown_force/audio/make_sfx.py](../eidoverse/examples/unknown_force/audio/make_sfx.py) | Example CLI: hand-made SFX and a far-off crowd | [audio](../tools-guides/audio.md) |
| [eidoverse/examples/unknown_force/audio/mix.py](../eidoverse/examples/unknown_force/audio/mix.py) | Example CLI: placement, ducking, the master to −14 LUFS | [synthkit](../tools-guides/synthkit.md) |
| [eidoverse/examples/unknown_force/make_review.py](../eidoverse/examples/unknown_force/make_review.py) | Example CLI: contact sheet, spectrogram and index of a render | [render-review](../tools-guides/render-review.md) |
| [eidoverse/assets/animations/performance_src/](../eidoverse/assets/animations/performance_src/README.md) | Asset source: Blender VRMA authoring script + engine-free clip checker | [blender](../tools-guides/blender.md) |
| [eidoverse/assets/animations/performance_uf_src/](../eidoverse/assets/animations/performance_uf_src/README.md) | Asset source: Blender VRMA authoring script, mesh-aware clip checker and rig data (UNKNOWN FORCE clips) | [blender](../tools-guides/blender.md) |
| [eidoverse/assets/grass/daisy_src/](../eidoverse/assets/grass/daisy_src/README.md) | Asset source: Blender + Python scripts that build the daisy sheet | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/assets/models/tandem_1896_src/](../eidoverse/assets/models/tandem_1896_src/README.md) | Asset source: Blender scripts that built the tandem GLB | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/models/voice_machines_src/](../eidoverse/assets/models/voice_machines_src/README.md) | Asset source: Blender scripts that built the voice-machine GLBs | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/assets/sets/corner_src/](../eidoverse/assets/sets/corner_src/README.md) | Asset source: Blender/PIL scripts that built the corner scene's models | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/sets/funeral_src/](../eidoverse/assets/sets/funeral_src/README.md) | Asset source: Blender scripts that built the funeral scene's models | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/sets/ocean_src/](../eidoverse/assets/sets/ocean_src/README.md) | Asset source: Blender scripts that built the ocean scene's models | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/assets/vrms/claude_suit_wardrobe_src/](../eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md) | Asset source: packed .blend, garment recipes, the petal-ring pivot tool, and the TuTa build (`build_tuta.py`, which exports the VRM), badge spec and painter | [blender](../tools-guides/blender.md) |

## 3. The WebGPU engine: the source of the port

These sources are the WebGPU edition as it stands on this branch: the source
each `eidoblend` port came from, read when a port's behaviour is in question.
The roles describe them in their own engine (Deno + WebGPU + three.js/TSL);
the Blender runner does not load them. `eido.py` still runs them where Deno is
installed.

| Source or tool | Role | Instructions |
| --- | --- | --- |
| [eido.py](../eido.py) | CLI utility: the WebGPU runner (`bootstrap`, `doctor`, `render`; needs Deno) | [development](../tools-guides/development.md) |
| [vrm_turntable.py](../vrm_turntable.py) | CLI utility: VRM outfit, clip and expression sheets in the WebGPU engine (Blender's: `blender/tools/vrm_turntable.py`) | [claudesona](../tools-guides/claudesona.md) |
| [eidoverse/render_scene.mjs](../eidoverse/render_scene.mjs) | Native render entry | [scene-format](../tools-guides/scene-format.md) |
| [eidoverse/render_common.mjs](../eidoverse/render_common.mjs) | Native runner support + UI utility | [scene-format](../tools-guides/scene-format.md) |
| [eidoverse/gpu_check.mjs](../eidoverse/gpu_check.mjs) | Hardware preference, software fallback reporting + standalone compute/readback diagnostic (Blender's: `eidoblend.harness.gpu_check`) | [development](../tools-guides/development.md) |
| [eidoverse/gpu_check_test.mjs](../eidoverse/gpu_check_test.mjs) | Hardware preference and software fallback tests; no GPU needed | [development](../tools-guides/development.md) |
| [eidoverse/audit_core.js](../eidoverse/audit_core.js) | System support; see guide for entry point | [render-review](../tools-guides/render-review.md) |
| [eidoverse/audit_core_test.mjs](../eidoverse/audit_core_test.mjs) | Test suite | [development](../tools-guides/development.md) |
| [eidoverse/asteroid_moon.js](../eidoverse/asteroid_moon.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/book.js](../eidoverse/book.js) | Injected scene API | [books](../tools-guides/books.md) |
| [eidoverse/book_core.js](../eidoverse/book_core.js) | System support; the Blender edition runs it unchanged in Deno | [books](../tools-guides/books.md) |
| [eidoverse/camera_safety.js](../eidoverse/camera_safety.js) | Injected scene API | [camera-lighting](../tools-guides/camera-lighting.md) |
| [eidoverse/character_controller.js](../eidoverse/character_controller.js) | Injected scene API | [controller](../tools-guides/controller.md) |
| [eidoverse/foot_ik.js](../eidoverse/foot_ik.js) | System support; see guide for entry point | [controller](../tools-guides/controller.md) |
| [eidoverse/claude_robot_dof.js](../eidoverse/claude_robot_dof.js) | Dynamic ESM: the robot body's hardware-DOF pass (joint limits per frame) | [robot-body](../tools-guides/robot-body.md) |
| [eidoverse/claudesona_face.js](../eidoverse/claudesona_face.js) | Dynamic ESM scene API | [claudesona](../tools-guides/claudesona.md) |
| [eidoverse/claudesona_wardrobe.js](../eidoverse/claudesona_wardrobe.js) | Dynamic ESM scene API | [claudesona](../tools-guides/claudesona.md) |
| [eidoverse/vrm_turntable_scene.js](../eidoverse/vrm_turntable_scene.js) | Scene script behind vrm_turntable.py | [claudesona](../tools-guides/claudesona.md) |
| [eidoverse/pose_bake.js](../eidoverse/pose_bake.js) | Dynamic ESM: solve a performance once, play the recorded poses back | [robot-body](../tools-guides/robot-body.md) |
| [eidoverse/robot_controller.js](../eidoverse/robot_controller.js) | Injected scene API | [robot-body](../tools-guides/robot-body.md) |
| [eidoverse/robot_body.js](../eidoverse/robot_body.js) | Injected scene API | [navigation](../tools-guides/navigation.md) · [robot-body](../tools-guides/robot-body.md) |
| [eidoverse/robot_debug.js](../eidoverse/robot_debug.js) | Injected scene API | [navigation](../tools-guides/navigation.md) · [robot-body](../tools-guides/robot-body.md) |
| [eidoverse/robot_memory.js](../eidoverse/robot_memory.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/robot_planner.js](../eidoverse/robot_planner.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/robot_sensors.js](../eidoverse/robot_sensors.js) | Injected scene API | [navigation](../tools-guides/navigation.md) |
| [eidoverse/clippy.js](../eidoverse/clippy.js) | Injected scene API | [clippy](../tools-guides/clippy.md) |
| [eidoverse/cloth_sim.js](../eidoverse/cloth_sim.js) | Dynamic ESM scene API | [cloth](../tools-guides/cloth.md) |
| [eidoverse/cloud_spatial.js](../eidoverse/cloud_spatial.js) | Dynamic ESM scene API | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/creature_builder.js](../eidoverse/creature_builder.js) | Injected scene API (not ported: a new creature creator is being made) | [creatures](../tools-guides/creatures.md) |
| [eidoverse/creature_realist.js](../eidoverse/creature_realist.js) | Injected API with optional external backend (not ported) | [creatures](../tools-guides/creatures.md) |
| [eidoverse/creature_specimen.js](../eidoverse/creature_specimen.js) | Injected API with optional external backend (not ported) | [creatures](../tools-guides/creatures.md) |
| [eidoverse/effects_tsl/aeropittura.js](../eidoverse/effects_tsl/aeropittura.js) | Injected effect implementation/registry (`aeropittura`, the Futurist painting pass) | [postprocessing](../tools-guides/postprocessing.md) |
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
| [eidoverse/effects_tsl/era_looks.js](../eidoverse/effects_tsl/era_looks.js) | Injected effect implementation/registry (`era_looks`, twenty graphic-arts looks) | [postprocessing](../tools-guides/postprocessing.md) |
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
| [eidoverse/effects_tsl/nuclear_explosion.js](../eidoverse/effects_tsl/nuclear_explosion.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) · [sdf-explosions](../tools-guides/sdf-explosions.md) |
| [eidoverse/effects_tsl/old_bw_film.js](../eidoverse/effects_tsl/old_bw_film.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/radial_blur.js](../eidoverse/effects_tsl/radial_blur.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/rain_on_camera.js](../eidoverse/effects_tsl/rain_on_camera.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/retro_wireframe.js](../eidoverse/effects_tsl/retro_wireframe.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/rgb_shift.js](../eidoverse/effects_tsl/rgb_shift.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/sepia.js](../eidoverse/effects_tsl/sepia.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/underwater.js](../eidoverse/effects_tsl/underwater.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/vhs_tape.js](../eidoverse/effects_tsl/vhs_tape.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/effects_tsl/wavy.js](../eidoverse/effects_tsl/wavy.js) | Injected effect implementation/registry | [postprocessing](../tools-guides/postprocessing.md) |
| [eidoverse/examples/basic_vrm.js](../eidoverse/examples/basic_vrm.js) | Scene example/template (Blender's: `blender/tests/claudesona/basic_vrm/`) | [claudesona](../tools-guides/claudesona.md) |
| [eidoverse/examples/claude_robot.js](../eidoverse/examples/claude_robot.js) | Scene example/template: the robot body, its face and a clip through its joints | [robot-body](../tools-guides/robot-body.md) |
| [eidoverse/examples/obstacle_course.js](../eidoverse/examples/obstacle_course.js) | Scene example/template: the walking course (Blender's: `blender/examples/obstacle_course/`) | [geometry](../tools-guides/geometry.md) |
| [eidoverse/examples/robotics/assembly.scene.js](../eidoverse/examples/robotics/assembly.scene.js) | Scene example/template | [robotics](../tools-guides/robotics.md) |
| [eidoverse/examples/robotics/mantis.scene.js](../eidoverse/examples/robotics/mantis.scene.js) | Scene example/template | [robotics](../tools-guides/robotics.md) |
| [eidoverse/examples/robotics/motion.scene.js](../eidoverse/examples/robotics/motion.scene.js) | Scene example/template | [robotics](../tools-guides/robotics.md) |
| [eidoverse/examples/robotics/manufacturing.scene.js](../eidoverse/examples/robotics/manufacturing.scene.js) | Scene example/template | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/examples/robotics/relief.scene.js](../eidoverse/examples/robotics/relief.scene.js) | Renderable close study of ball-nose roughing and finishing | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/examples/robotics/mesh_fabrication.scene.js](../eidoverse/examples/robotics/mesh_fabrication.scene.js) | Rotary carving from an ordinary Object3D mesh assembly | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/examples/robotics/rotary.scene.js](../eidoverse/examples/robotics/rotary.scene.js) | Renderable stock-rotating all-around carving example | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/examples/robotics/rotary_metal.scene.js](../eidoverse/examples/robotics/rotary_metal.scene.js) | Aluminum rotary cutting at physical speed followed by a time-lapse finish | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/examples/unknown_force/scene.js](../eidoverse/examples/unknown_force/scene.js) | The UNKNOWN FORCE music video's conductor script (its scenes, outfit, look and captions on the song's timeline) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/fab_sim.js](../eidoverse/fab_sim.js) | Injected scene API | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/fluid_grid.js](../eidoverse/fluid_grid.js) | Dynamic ESM scene API | [volume-fire](../tools-guides/volume-fire.md) |
| [eidoverse/fluid_sim.js](../eidoverse/fluid_sim.js) | Dynamic ESM scene API | [liquids](../tools-guides/liquids.md) |
| [eidoverse/fluid_swe.js](../eidoverse/fluid_swe.js) | Dynamic ESM scene API | [liquids](../tools-guides/liquids.md) |
| [eidoverse/fluid_water.js](../eidoverse/fluid_water.js) | Dynamic ESM scene API | [free-surface-water](../tools-guides/free-surface-water.md) |
| [eidoverse/graphics/era_screens_1939_1984.js](../eidoverse/graphics/era_screens_1939_1984.js) | Dynamic ESM scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/graphics/era_screens_2001_2023.js](../eidoverse/graphics/era_screens_2001_2023.js) | Dynamic ESM scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/graphics/preview_screens.mjs](../eidoverse/graphics/preview_screens.mjs) | CLI utility: engine-free PNGs, contact sheets, draw cost; Blender: `eidoblend.media.canvas_scenes` | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/graphics/screens_nan_sweep.mjs](../eidoverse/graphics/screens_nan_sweep.mjs) | CLI crash guard: non-finite canvas-geometry sweep; Blender: `eidoblend.media.canvas_scenes` | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/iso_field.js](../eidoverse/iso_field.js) | Injected scene API | [sdf-volumes](../tools-guides/sdf-volumes.md) |
| [eidoverse/loft.js](../eidoverse/loft.js) | Injected scene API | [geometry](../tools-guides/geometry.md) |
| [eidoverse/lyric_renderer.py](../eidoverse/lyric_renderer.py) | Optional Python frame utility; no CLI. Blender: `eidoblend.media.lyrics` (ported) | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/model_kit.js](../eidoverse/model_kit.js) | Injected scene API | [assets](../tools-guides/assets.md) |
| [eidoverse/parallax_material.js](../eidoverse/parallax_material.js) | ESM installer for injected scene API | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/parallax_occlusion.js](../eidoverse/parallax_occlusion.js) | System support; see guide for entry point | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/parole.js](../eidoverse/parole.js) | Dynamic ESM scene API: parole-in-libertà captions and quotes | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/particle_morph.js](../eidoverse/particle_morph.js) | Injected scene API | [particles-fx](../tools-guides/particles-fx.md) |
| [eidoverse/particles.js](../eidoverse/particles.js) | Injected scene API | [particles-fx](../tools-guides/particles-fx.md) |
| [eidoverse/procedural_materials.js](../eidoverse/procedural_materials.js) | Injected scene API | [procedural-materials](../tools-guides/procedural-materials.md) |
| [eidoverse/props/tandem.js](../eidoverse/props/tandem.js) | Dynamic ESM prop: tandem, rider IK, teapot stoker | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/props/voice_machines/index.js](../eidoverse/props/voice_machines/index.js) | Dynamic ESM: voice-machine catalogue, buildMachine/loadMachine | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/c64.js](../eidoverse/props/voice_machines/c64.js) | Dynamic ESM prop (1982 C64 + monitor) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/dectalk.js](../eidoverse/props/voice_machines/dectalk.js) | Dynamic ESM prop (1984 DECtalk) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/desktop2001.js](../eidoverse/props/voice_machines/desktop2001.js) | Dynamic ESM prop (2001 desktop PC) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/mac1984.js](../eidoverse/props/voice_machines/mac1984.js) | Dynamic ESM prop (1984 Macintosh) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/mainframe.js](../eidoverse/props/voice_machines/mainframe.js) | Dynamic ESM prop (1961 computer room) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/speakspell.js](../eidoverse/props/voice_machines/speakspell.js) | Dynamic ESM prop (1978 Speak & Spell) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/teletype.js](../eidoverse/props/voice_machines/teletype.js) | Dynamic ESM prop (1966 ASR-33) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/props/voice_machines/voder.js](../eidoverse/props/voice_machines/voder.js) | Dynamic ESM prop (1939 Voder) | [voice-machines](../tools-guides/voice-machines.md) |
| [eidoverse/redgiant.js](../eidoverse/redgiant.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/rhombic_dodecahedron.js](../eidoverse/rhombic_dodecahedron.js) | Injected scene API | [geometry](../tools-guides/geometry.md) |
| [eidoverse/ringworld.js](../eidoverse/ringworld.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/robotics/index.js](../eidoverse/robotics/index.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/grasp.js](../eidoverse/robotics/grasp.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/io.js](../eidoverse/robotics/io.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/materials.js](../eidoverse/robotics/materials.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/motion.js](../eidoverse/robotics/motion.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/running.js](../eidoverse/robotics/running.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/scara.js](../eidoverse/robotics/scara.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/serial_arm.js](../eidoverse/robotics/serial_arm.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/studio.js](../eidoverse/robotics/studio.js) | Modular runtime ESM behind RoboticsKit/FabSim | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/inspector/index.html](../eidoverse/robotics/inspector/index.html) | Inspector HTML entry | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/inspector/viewer.js](../eidoverse/robotics/inspector/viewer.js) | Inspector client | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/serve_inspector.py](../eidoverse/robotics/serve_inspector.py) | CLI utility | [robotics](../tools-guides/robotics.md) |
| [eidoverse/robotics/fabrication.js](../eidoverse/robotics/fabrication.js) | Modular runtime ESM behind RoboticsKit/FabSim | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/feed_path.js](../eidoverse/robotics/feed_path.js) | Modular runtime ESM behind RoboticsKit/FabSim | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/filament.js](../eidoverse/robotics/filament.js) | Bézier tubing factory and metered dispenser controller | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/filament_path.js](../eidoverse/robotics/filament_path.js) | Internal extrusion/retraction timeline | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/cutter_nodes.js](../eidoverse/robotics/cutter_nodes.js) | GPU swept flat/ball cutter envelope | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/cutter_sweep.js](../eidoverse/robotics/cutter_sweep.js) | Analytic CPU swept-cutter removal and spatial indexing | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/cutting.js](../eidoverse/robotics/cutting.js) | Stock profiles, surface finishes and removal-driven debris | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/relief.js](../eidoverse/robotics/relief.js) | Mesh/heightfield sampling and ball-compensated relief planning | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/source_geometry.js](../eidoverse/robotics/source_geometry.js) | Manufacturing snapshots and uniform fitting of mesh assemblies | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/mesh_slices.js](../eidoverse/robotics/mesh_slices.js) | Closed cross-sections, holes and overlapping-solid union | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/manufacturing_samples.js](../eidoverse/robotics/manufacturing_samples.js) | Reusable ordinary mesh inputs for manufacturing examples | [fabrication](../tools-guides/fabrication.md) |
| [eidoverse/robotics/rotary.js](../eidoverse/robotics/rotary.js) | Indexed four-axis volumetric carving jobs | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/rotary_setup.js](../eidoverse/robotics/rotary_setup.js) | Adjustable jaw, carriage and quill setup datums | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/rotary_path.js](../eidoverse/robotics/rotary_path.js) | Circumferential roughing, flat/ball compensation and XYZ/A timing | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/rotary_mesh.js](../eidoverse/robotics/rotary_mesh.js) | Mesh-driven indexed XYZ rasters and cutter-reach reporting | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/rotary_stock.js](../eidoverse/robotics/rotary_stock.js) | Seekable GPU volume subtraction and surface rendering | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/rotary_removal.js](../eidoverse/robotics/rotary_removal.js) | Volumetric first-engagement chip sampling | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/tests/runtime_test.mjs](../eidoverse/robotics/tests/runtime_test.mjs) | Test suite | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/attachment_frames_test.mjs](../eidoverse/robotics/tests/attachment_frames_test.mjs) | Mount frames checked against physical flange triangles through articulation | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/fabrication_feed_test.mjs](../eidoverse/robotics/tests/fabrication_feed_test.mjs) | Filament, tubing and material-aware CNC regression checks | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/relief_test.mjs](../eidoverse/robotics/tests/relief_test.mjs) | Relief compensation, swept stock and assembled machining checks | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/mesh_input_test.mjs](../eidoverse/robotics/tests/mesh_input_test.mjs) | Mesh transforms, closed slices, nested solids, infill and local skins | [development](../tools-guides/development.md) |
| [eidoverse/robotics/tests/rotary_test.mjs](../eidoverse/robotics/tests/rotary_test.mjs) | Rotary clearance, compensation, swept solids and engagement checks | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/tests/rotary_mesh_test.mjs](../eidoverse/robotics/tests/rotary_mesh_test.mjs) | Mesh toolpath compensation, flat cutter and reach checks | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics/tests/rotary_mount_test.mjs](../eidoverse/robotics/tests/rotary_mount_test.mjs) | Stud engagement and visible T-slot nut surfaces | [rotary-carving](../tools-guides/rotary-carving.md) |
| [eidoverse/robotics_kit.js](../eidoverse/robotics_kit.js) | Injected scene API | [robotics](../tools-guides/robotics.md) |
| [eidoverse/satori_ui.mjs](../eidoverse/satori_ui.mjs) | Standalone Satori demo with its own renderer (superseded, not ported) | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/scene_placement.js](../eidoverse/scene_placement.js) | ESM installer for injected scene API | [placement](../tools-guides/placement.md) |
| [eidoverse/screen.js](../eidoverse/screen.js) | Injected scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/sdf_raymarch_loader.js](../eidoverse/sdf_raymarch_loader.js) | Injected scene API | [sdf-volumes](../tools-guides/sdf-volumes.md) · [sdf-vehicles](../tools-guides/sdf-vehicles.md) · [sdf-explosions](../tools-guides/sdf-explosions.md) |
| [eidoverse/seedthree_api.js](../eidoverse/seedthree_api.js) | Injected API with optional external backend | [trees](../tools-guides/trees.md) |
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
| [eidoverse/sets/unknown_force/bin.js](../eidoverse/sets/unknown_force/bin.js) | Dynamic ESM film set (UNKNOWN FORCE) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/bin_pages.js](../eidoverse/sets/unknown_force/bin_pages.js) | Bin submodule: the page atlas | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/city.js](../eidoverse/sets/unknown_force/city.js) | Dynamic ESM film set (UNKNOWN FORCE); builds the hole too | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/citykit.js](../eidoverse/sets/unknown_force/citykit.js) | City and hole submodule: the shared kit | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/cn_lib.js](../eidoverse/sets/unknown_force/cn_lib.js) | Corridor and news submodule: shared helpers | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/corridor.js](../eidoverse/sets/unknown_force/corridor.js) | Dynamic ESM film set (UNKNOWN FORCE) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/hole.js](../eidoverse/sets/unknown_force/hole.js) | Dynamic ESM film set (UNKNOWN FORCE); also built by city.js | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/interiors_lib.js](../eidoverse/sets/unknown_force/interiors_lib.js) | Quiet room and showroom submodule: shared kit | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/news.js](../eidoverse/sets/unknown_force/news.js) | Dynamic ESM film set (UNKNOWN FORCE) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/quiet_room.js](../eidoverse/sets/unknown_force/quiet_room.js) | Dynamic ESM film set (UNKNOWN FORCE) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/quiet_room_art.js](../eidoverse/sets/unknown_force/quiet_room_art.js) | Quiet room submodule: canvas art | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/race.js](../eidoverse/sets/unknown_force/race.js) | Dynamic ESM film set (UNKNOWN FORCE) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/showroom.js](../eidoverse/sets/unknown_force/showroom.js) | Dynamic ESM film set (UNKNOWN FORCE) | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sets/unknown_force/showroom_art.js](../eidoverse/sets/unknown_force/showroom_art.js) | Showroom submodule: canvas art | [props-and-sets](../tools-guides/props-and-sets.md) |
| [eidoverse/sky_system.js](../eidoverse/sky_system.js) | Injected scene API | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/sky_worlds.js](../eidoverse/sky_worlds.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/sun_corona.js](../eidoverse/sun_corona.js) | Dynamic ESM scene API | [sky-weather](../tools-guides/sky-weather.md) |
| [eidoverse/surface_layers.js](../eidoverse/surface_layers.js) | Injected scene API | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/terrain.js](../eidoverse/terrain.js) | Injected scene API | [terrain-surfaces](../tools-guides/terrain-surfaces.md) |
| [eidoverse/terrain_base.js](../eidoverse/terrain_base.js) | Scene example/template: the locomotion courses | [geometry](../tools-guides/geometry.md) |
| [eidoverse/text_3d.js](../eidoverse/text_3d.js) | Dynamic ESM scene API | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/tsl_curl_noise.js](../eidoverse/tsl_curl_noise.js) | System support; see guide for entry point | [volume-fire](../tools-guides/volume-fire.md) |
| [eidoverse/vegetation.js](../eidoverse/vegetation.js) | Lazy ESM behind injected createFlora | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_corn_gen.js](../eidoverse/vegetation_corn_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_loader.js](../eidoverse/vegetation_loader.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_shrub_gen.js](../eidoverse/vegetation_shrub_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_sunflower_gen.js](../eidoverse/vegetation_sunflower_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/vegetation_daisy_gen.js](../eidoverse/vegetation_daisy_gen.js) | System support; see guide for entry point | [vegetation](../tools-guides/vegetation.md) |
| [eidoverse/video_to_sprite.mjs](../eidoverse/video_to_sprite.mjs) | CLI utility; Blender: `screens.make_atlas_screen` plays its atlases | [motion-graphics](../tools-guides/motion-graphics.md) |
| [eidoverse/weather_audio.js](../eidoverse/weather_audio.js) | Explicit facade/package component | [sky-weather](../tools-guides/sky-weather.md) · [weather-effects](../tools-guides/weather-effects.md) |
| [eidoverse/weather_system.js](../eidoverse/weather_system.js) | Injected scene API | [sky-weather](../tools-guides/sky-weather.md) · [weather-effects](../tools-guides/weather-effects.md) |
| [eidoverse/xr/example.html](../eidoverse/xr/example.html) | HTML entry point: minimal WebXR page on the kit (served by xr/serve.py) | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/quest.py](../eidoverse/xr/quest.py) | CLI utility: the headset over adb (Wi-Fi debugging, open, awake, pull recordings) | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/serve.py](../eidoverse/xr/serve.py) | CLI utility: HTTPS server for headset pages + /report telemetry log | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/shot.mjs](../eidoverse/xr/shot.mjs) | CLI utility: stills of a WebXR page from headless Chrome | [webxr](../tools-guides/webxr.md) |
| [eidoverse/xr/xr_kit.js](../eidoverse/xr/xr_kit.js) | Browser ES module for WebXR pages (not a scene-script import) | [webxr](../tools-guides/webxr.md) |

**Part 1: the runner and its tests, every `eidoblend` module outside the terrain family one by one, and the
terrain family by its package. Part 2: the shared Python tools and packages, plus 9 asset `_src` folders.
Part 3: the WebGPU engine's sources and entry points.** This is documentation coverage, not a claim that
every API was executed. Recount with `python blender/tests/pipeline/check_docs.py`
([development](../tools-guides/development.md#documentation-changes)) when a module lands.

## Additional instructions and asset notes

- [The Blender edition's layout and tests](../blender/README.md), [setup](SETUP.md),
  [interactive workflow](HARNESS_MODE.md), [engine maintainer map](../eidoverse/README.md) and
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
- UNKNOWN FORCE: the [music video's example folder](../eidoverse/examples/unknown_force/README.md), the
  [WebGPU scene index](../eidoverse/sets/unknown_force/README.md) with its
  [sources](../eidoverse/sets/unknown_force/SOURCES.md), the
  [TuTa source](../eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md#the-tuta) and
  [runtime art](../eidoverse/assets/vrms/claude_suit_wardrobe_tex/README.md), and the
  [performance clips source](../eidoverse/assets/animations/performance_uf_src/README.md).
- Props and scenes: [voice machines](../eidoverse/assets/models/voice_machines/README.md),
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
the active instruction split; they are preserved in place. The terrain family is listed by its
package while its new `make_terrain` lands; its guide holds its modules.

`render_scene.mjs` names a `dismember.js` in its helper list, but no dismemberment source
is on this branch, so neither edition has that system here ([destruction](../tools-guides/destruction.md)).

The retired `mech_parts.js` is intentionally absent from the WebGPU engine. `robotics_kit.js` and
`fab_sim.js` expose the modular system. The separate `robot_*.js` VRM
navigation stack remains supported. Legacy source archives stay in ignored
working storage and Git history rather than the active tool tree.
