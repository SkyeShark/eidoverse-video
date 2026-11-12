"""eidoblend.characters: VRM characters in Blender 5.2 EEVEE (tools-guides/characters.md describes this edition).

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.characters import load_vrm, load_clip, play_vrma_default, walk_path, key_expression, Ground

    me = load_vrm('claude_robot')                                  # vrm.py: the add-on import, a handle
    play_vrma_default(me, 'still_breathe')                         # vrma.py: a stationary clip as an NLA strip
    rep = walk_path(me, load_clip(me, 'walk'), [(0, 0), (10, 0)],  # locomotion.py: planted feet over uneven ground
                    Ground(obj=terrain), face={'happy': 1.0})
    key_expression(me, 'happy', [(1, 1.0)])                        # expressions.py: shape keys + the add-on's previews

    from eidoblend.characters import controller, emotes            # the subpackages, each loaded on first use
    walk = controller.Locomotion(me, controller.CollisionWorld(), start=(0, -4, 0), heading=3.1416)
    emotes.seat_on(walk, chair, hold=3.0)

Modules: vrm (load_vrm, VRMHandle; look='asis' | 'mtoon' | 'pbr'), vrma (load_clip, play_vrma, play_vrma_default),
expressions (key_expression, set_expression, scale_visemes), robot_dof (my robot body's hardware pass:
claude_robot_dof.js whole), ground (foot_points, Ground, ground_vrm), locomotion (walk_path, analyze_clip, Body),
performance (perform, key_face_track: a stationary clip through a body's frame order, baked), checks (the audits),
clippy (make_clippy: tools-guides/clippy.md), springs (bake_springs, SpringRig: spring bones baked to keys), lookat
(bake_look_at, LookAt: eyes on a target), lipsync (key_lipsync, visemes_from_audio), pose_bake (pose_bake.js's files,
both ways).

Subpackages (each imported on first use, as characters.<name> or `from eidoblend.characters import <name>`):
    controller  the character controller for film: VRMCharacterController, VRMFootControllerIK, Locomotion,
                CollisionWorld (character_controller.js, foot_ik.js; tools-guides/controller.md)
    emotes      the character verbs for a walking body: seat_on, stand_up, sit_on_ground, emote, face_camera, unseat,
                bake, seat_plan (tools-guides/maneuvers.md)
    maneuvers   moves aimed at scene objects: vault_over, climb_onto, scramble_up, climb_ladder, jump_across, cross
                (tools-guides/maneuvers.md)
    robot       my robot body's runtime, hands and the embodied body (VRMRobotBody), which drives any VRM
                (tools-guides/robot-body.md)
    claudesona  the claudesona's face, mouths and lipsync, its wardrobe and the TuTa, the MToon / PBR look
                (tools-guides/claudesona.md)
    robotics    the modular robotics kit: make_robot, load_part, catalog, studio (tools-guides/robotics.md)

The family stands on the others only where it must: robot drives eidoblend.harness.navigation (the sensors, the
memory, the planner) and plays its runs and moves through characters.controller; controller's sit, emotes and
maneuvers read eidoblend.placement (the seat pan, the world's rays); claudesona builds on fx's node layer, media's
timebase and harness.assets' PBR fetch; lipsync reads media's visemes; robotics loads eidoblend.fabrication for a
dispenser's filament. Names follow the WebGPU API in snake_case (playVRMADefault -> play_vrma_default, groundVRM ->
ground_vrm).
"""

import importlib

from .expressions import key_expression, scale_visemes, set_expression  # noqa: F401
from .ground import Ground, foot_points, ground_vrm  # noqa: F401
from .lipsync import key_lipsync, visemes_from_audio  # noqa: F401
from .locomotion import Body, analyze_clip, walk_path  # noqa: F401
from .lookat import LookAt, bake_look_at  # noqa: F401
from .performance import key_face_track, perform  # noqa: F401
from .springs import SpringRig, bake_springs  # noqa: F401
from .vrm import VRMHandle, load_vrm  # noqa: F401
from .vrma import load_clip, play_vrma, play_vrma_default  # noqa: F401

SUBPACKAGES = ('controller', 'emotes', 'maneuvers', 'robot', 'claudesona', 'robotics')


def __getattr__(name):
    """characters.controller, characters.robot ...: the subpackages, imported on first use (each is heavy, and robot
    pulls in harness.navigation)."""
    if name in SUBPACKAGES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(SUBPACKAGES))
