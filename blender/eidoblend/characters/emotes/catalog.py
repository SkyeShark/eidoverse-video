"""eidoblend.characters.emotes.catalog: the expressive and sitting clips of the shared library (render_scene.mjs's
VRMA_SLOTS: the 'Expressive' and 'Sitting' groups and the stand <-> sit transitions), and each measured on a body.

    from eidoblend.characters.emotes import EXPRESSIVE, CHAIR_SITS, FLOOR_SITS, TRANSITIONS, clip_info
    clip_info(me, 'stand_to_sit')     # {'duration': 2.21, 'hips_start': (x, y, z), 'hips_end': ..., 'seated_end': True ...}

The hips are the clip's hips track as an offset from the root in the armature's axes (Blender's: +Y is BEHIND a VRM as
loaded, -Y in front, Z up). On the library's clips:
  stand_to_sit         stands, then carries the hips 0.44 m back and 0.42 m down: it sits into a seat behind the body
  sit_to_stand         starts seated with the hips over the root, ends standing 0.45 m in front of it
  sitting_normal_chair a seated loop with the hips over the root, 0.42 m down: sit_to_stand's first pose
  sitting_nervous_arm_rub_chair   a seated fidget loop, the hips 0.29 m down (a higher seat), 4 cm back
  sitting_on_ground    a cross-legged loop, the hips 0.82 m down
  sit_laying_on_ground a loop lying on the ground
  the expressive clips stand on both feet; cheer's hips sit 0.25 m behind the root from its first frame
"""

EXPRESSIVE = ('talk', 'salute', 'cheer', 'fist', 'raise', 'reach', 'crazy', 'dance')
CHAIR_SITS = ('sitting_normal_chair', 'sitting_nervous_arm_rub_chair')
FLOOR_SITS = ('sitting_on_ground', 'sit_laying_on_ground')
TRANSITIONS = ('stand_to_sit', 'sit_to_stand')
SITTING = CHAIR_SITS + FLOOR_SITS + TRANSITIONS
SEAT_CLIP = 'sitting_normal_chair'          # seatOn's chair clip
GROUND_CLIP = 'sitting_on_ground'           # sitOnGround's clip
SEATED_DROP = 0.25                          # m: a pose whose hips sit this far under the standing hips is seated


def is_sitting(slot):
    """a sitting clip: seat_on / sit_on_ground place the body for it; emote does not"""
    return slot in SITTING or 'sit' in slot


def clip_info(h, slot, body=None):
    """a library clip measured on the VRM handle h -> {'slot', 'duration', 'hips_start', 'hips_end' (the hips' offset
    from the root at the first and last frame, armature axes), 'hips_low' (the lowest hips offset), 'seated_start',
    'seated_end' (the hips SEATED_DROP or more under the standing hips), 'travel' (the hips' horizontal travel, m)} or
    None when the library has no such clip"""
    import numpy as np
    from ..controller import clips as C
    cc = C.load_emote_clip(h, slot, loop=False, body=body)
    if cc is None:
        return None
    R = cc.root_curve
    return {'slot': slot, 'duration': cc.duration, 'hips_start': tuple(float(v) for v in R[0]),
            'hips_end': tuple(float(v) for v in R[-1]), 'hips_low': float(R[:, 2].min()),
            'seated_start': bool(R[0, 2] <= -SEATED_DROP), 'seated_end': bool(R[-1, 2] <= -SEATED_DROP),
            'travel': float(np.hypot(R[-1, 0] - R[0, 0], R[-1, 1] - R[0, 1]))}
