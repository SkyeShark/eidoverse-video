"""eidoblend.characters.emotes: scene_placement.js's character verbs (emote, faceCamera, seatOn, sitOnGround, unseat and
the seated exemption from the audits) for any VRM: through the character controller when a Locomotion drives the body
(the engine's "cohesive path": one mixer, the sit crossfaded from the walk, the root handed to the seat), else the
stationary ports in eidoblend.placement.seating. tools-guides/maneuvers.md describes this edition.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.characters import load_vrm
    from eidoblend.characters.controller import CollisionWorld, Locomotion
    from eidoblend.characters.emotes import seat_on, stand_up, sit_on_ground, face_camera, emote, bake

    me = load_vrm('aletheia')
    walk = Locomotion(me, CollisionWorld(), start=(0, -4, 0), heading=3.1416)
    seat_on(walk, chair, hold=3.0)          # walk up, turn out of the chair, sit into it, hold, stand (keyed)
    face_camera(walk)
    emote(walk, 'salute', facing='camera')
    rep = bake(walk)                        # the take keyed; arm['eido_seated'] keyed over the seated frames

Modules: verbs (seat_on, stand_up, sit_on_ground, face_camera, emote, unseat, key_seated, seated_spans, bake,
route_around, the measures seat_plan, seat_skin, skin_lowest, skin_points, pan_points, back_push, robot_body_of, and the
commands SeatOn, StandUp, SitOnGround, FaceCamera, EmoteCmd, Unseat), catalog (the expressive and sitting clips of the
library: EXPRESSIVE, CHAIR_SITS, FLOOR_SITS, TRANSITIONS, clip_info).

A VRM my robot body drives (eidoblend.characters.robot: VRMRobotBody registers itself, the engine's
globalThis._vrmControllers) sits through its own seated state: seat_on(h, chair, transition='stand_to_sit') places the
body at the measured spot, calls body.begin_seated and keeps seat_plan's measures on the body (body.seat_plan) for its
bake.
"""

from .catalog import (CHAIR_SITS, EXPRESSIVE, FLOOR_SITS, GROUND_CLIP, SEAT_CLIP, SITTING, TRANSITIONS,  # noqa: F401
                      clip_info, is_sitting)
from .verbs import (EmoteCmd, FaceCamera, SeatOn, SitOnGround, StandUp, Unseat, back_push, bake, emote,  # noqa: F401
                    face_camera, is_locomotion, key_seated, pan_points, robot_body_of, route_around, seat_on, seat_plan,
                    seat_skin, seated_spans, sit_on_ground, skin_lowest, skin_points, stand_up, unseat)
