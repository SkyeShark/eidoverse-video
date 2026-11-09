"""eidoblend.characters.maneuvers: the character controller's parkour moves (character_controller.js: vault, climbLedge,
jump, climbLadder, climbWall and the auto-trigger's vault / mount / scramble / gap jump, with their contact IK) aimed
at objects in a Blender scene. tools-guides/maneuvers.md describes this edition.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.characters import load_vrm
    from eidoblend.characters.controller import CollisionWorld, Locomotion
    from eidoblend.characters.maneuvers import vault_over, climb_onto, climb_ladder, cross

    me = load_vrm('aletheia')
    walk = Locomotion(me, CollisionWorld(exclude=rungs + rails), start=(0, -4, 0), heading=3.1416)
    vault_over(walk, cover)                  # walk up, square up, vault(): one hand on its top, the legs tucked over
    climb_onto(walk, block)                  # climbLedge: the hands on the lip, the feet onto the top
    climb_ladder(walk, rungs, wall)          # the rungs measured; hands and feet on them; the mantle over the top
    cross(walk, cover, gait='run')           # run at it: the auto-trigger picks the move
    rep = walk.bake()

The moves themselves (their clips, root paths, the contact IK of hands and feet, the feet kept out of solids) are the
controller's: eidoblend.characters.controller.maneuvers, ported by the controller step. This package measures what
they are aimed at and puts the body there.

Modules: targets (measure_obstacle, measure_ladder, takeoff_edge's helpers: a face, its top, depth and landing; a
ladder's rungs), verbs (vault_over, climb_onto, scramble_up, climb_ladder, jump_across, cross, takeoff_edge and the
commands Approach and Cross).
"""

from .targets import forward, heading_of, measure_ladder, measure_obstacle  # noqa: F401
from .verbs import (Approach, Cross, climb_ladder, climb_onto, cross, jump_across, scramble_up,  # noqa: F401
                    takeoff_edge, vault_over)
