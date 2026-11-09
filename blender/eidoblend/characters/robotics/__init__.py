"""eidoblend.characters.robotics: the modular robotics kit in Blender 5.2 EEVEE (tools-guides/robotics.md).

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.characters.robotics import make_robot, load_part, catalog, studio, frame_camera
    arm = make_robot('arm', color='#d9e0df', accent='#398b91')
    claw = make_robot('gripper')
    arm.attach(claw, port='a650_j6/output', child_port='parallel_gripper/input')
    arm.play('joints')                                  # keyed over the scene's frame range

Modules (each mirrors its eidoverse/robotics/ source, MIT):
    kit         index.js: catalog, make_robot / load_robot, load_part, frame_matrix, vector / to_authoring, Robot
                (ports, attach, set_joints, reset, parts / part, stats, set_colors, dispose), INSTALLERS, asset_root
    motion      motion.js: the controls and samples (grasp, grasp_reference, jaw_gap, spin_rotors, fold, track_travel,
                cooling_fan, rotary_setup, joints / move_to, scara_joints / move_scara, axes / move_tool / tool_tip,
                sample, play, stop), track_frame
    solvers     grasp.js, scara.js, serial_arm.js, rotary_setup.js (plain Python)
    running     running.js: the humanoid / quadruped running gaits (create_running_controller)
    materials   materials.js: the linear mask recolour, the palette, textures=False
    io          io.js: the shared caches (json_file, glb_json, glb_accessor, shared_image, check_anisotropy,
                cache_stats, asset_root)
    studio      studio.js: studio(scene, grid), frame_camera(camera, objects, direction, margin), world_box, make_camera,
                match_display (the unlit background and one-pixel grid shown as the WebGPU film shows them)
    facade      robotics_kit.js: RoboticsKit (version, ready, catalog, load, load_part, connect, create_ptfe_tube,
                service_loop), make_bot
    inspector   inspector/viewer.js: inspector_scene(model) -> Inspector, the scene that plays the inspector's role
                (motions, time, colours, wireframe, part picking by ray cast, UV split view, joint sliders, the
                fabrication process with its stock / timing / workpiece controls)
    rig         the inspector's joint sliders: rig_joints / measure_joints / set_slider / unrig_joints
                (simple-expression drivers)
    examples    examples/robotics/{assembly,mantis,motion}.scene.js: EXAMPLES['assembly'] ... (scenes/*.py + .json
                run them through the harness)
    mech_parts  the older production engine's mech_parts.js (MechParts): procedural mechanical part generators
    legacy_arm  the older production engine's robotic_arm.js (RoboticArm): the primitive 2-link arm with tools
"""

from .facade import RoboticsKit, connect, create_ptfe_tube, make_bot, service_loop  # noqa: F401
from .io import asset_root, cache_stats  # noqa: F401
from .kit import (INSTALLERS, Robot, catalog, frame_matrix, load_part, load_robot, make_robot,  # noqa: F401
                  to_authoring, vector)
from .motion import track_frame  # noqa: F401
from .running import RunningController, create_running_controller  # noqa: F401
from .solvers import (SerialArm, articulated_demo, constrain_gantry_pose, gantry_demo, grasp_values,  # noqa: F401
                      rotary_fixture_setup, scara)
from .studio import frame_camera, make_camera, match_display, studio, world_box  # noqa: F401

ASSET_ROOT = asset_root()          # index.js assetRoot: eidoverse/assets/robotics/
