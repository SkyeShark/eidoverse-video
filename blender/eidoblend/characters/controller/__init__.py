"""eidoblend.characters.controller: the character controller (locomotion) for film, ported from the WebGPU edition's
character_controller.js (VRMCharacterController) and foot_ik.js (VRMFootControllerIK). tools-guides/controller.md
describes this edition.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.characters import load_vrm
    from eidoblend.course import build_course, PRESETS              # terrain_base.js's courses (the course package)
    from eidoblend.characters.controller import CollisionWorld, Locomotion

    build_course(PRESETS['stairs_pyramid'])
    me = load_vrm('claude_robot')
    walk = Locomotion(me, CollisionWorld(), start=(0, -5, 0), heading=3.1416)
    walk.wait(0.5).move_to((0, 4)).turn_by(90).follow_path([(-3, 4)], gait='run')
    rep = walk.bake(f0=1)                 # keyed: any frame renders on its own

Modules: world (CollisionWorld: the walkable world's casts, the Rapier stand-in), mixer (AnimationMixer: three.js's),
clips (the clip library stripped as the controller strips it, each clip measured on the body: stance, stride, phase),
pose (Pose: the frame's scene graph), foot_ik (VRMFootControllerIK, CastType, RotationType), controller
(VRMCharacterController: probes, stairs and ramps, the gait tree, emotes, gestures, seating, the maneuver engine, turns on
the spot, the backward walk), plant (the film bake's planted feet), film (Locomotion: move_to / follow_path / turn_to /
wait / emote / gesture / sit and bake; GAITS).
"""

from .clips import ControllerClip, GaitAnalysis, analyze, load_standard_animations  # noqa: F401
from .controller import PRESETS as CONTROLLER_PRESETS, VRMCharacterController  # noqa: F401
from .film import GAITS, Locomotion, check_segment, segments  # noqa: F401
from .foot_ik import CastType, Limb, RotationType, VRMFootControllerIK  # noqa: F401
from .mixer import AnimationAction, AnimationMixer, LOOP_ONCE, LOOP_PINGPONG, LOOP_REPEAT, damp  # noqa: F401
from .plant import plant, report, sub_report  # noqa: F401
from .pose import Pose, humanoid_parents, root_matrix  # noqa: F401
from .world import CollisionWorld, Hit  # noqa: F401
