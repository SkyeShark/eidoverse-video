"""eidoblend.characters.checks: the family's audits as functions a test (or a scene's build) calls.

The WebGPU edition audits at render time ([vrm-pose], [lipsync], the foot-slide detector). Here a scene is built once and
keyed, so the checks read the keyed result:

    posed_vs_rest(h, frames)        the largest turn off the rest pose per frame ([vrm-pose]: a body left in its T-pose
                                    is a body nobody animated) -> {frame: deg}
    expression_moved(h, name, frames)  the expression's shape keys' range over the frames ([lipsync]: a mouth that never
                                    moves is a lipsync that never ran)
    feet(rep, slip_mm, drift_mm, gap_mm, yaw_deg, clearance_mm, ankle_mm, rock_mm)  walk_path's report (measured on the
                                    result) against limits: every planted foot's slip along the ground a frame (the
                                    least-moving of its points in contact in that frame and the last) and over its
                                    stance, its turn on the ground a frame, its lowest point's gap over the ground (float
                                    > 0, sink < 0), no rock (its contact jumping end to end, the old one lifting more
                                    than rock_mm); every swing never touching the ground while it moves and clearing it
                                    by clearance_mm mid-swing; the IK reaching its targets; the weight crossing in double
                                    support, no flight
    fk_matches_blender(h, body, rep, frames)  the walk's own FK (the measures above) against Blender's evaluated pose: the
                                    soles' points from pose_bone.matrix, mm; the measures mean nothing if this is not ~0
"""

import math

import bpy
import numpy as np

from ._math import R2D


def posed_vs_rest(h, frames):
    out = {}
    sc = bpy.context.scene
    for f in frames:
        sc.frame_set(f)
        worst = 0.0
        for n, b in h.humanoid.items():
            q = h.arm.pose.bones[b].rotation_quaternion
            worst = max(worst, 2.0 * math.acos(min(1.0, abs(q.w))) * R2D)
        out[f] = round(worst, 2)
    return out


def expression_moved(h, name, frames):
    sc = bpy.context.scene
    vals = []
    for f in frames:
        sc.frame_set(f)
        vals.append(max((o.data.shape_keys.key_blocks[k].value for o, k, _w in h.expr.get(name, [])), default=0.0))
    return {'min': round(min(vals), 4), 'max': round(max(vals), 4)}


def feet(rep, slip_mm=1.0, drift_mm=3.0, gap_mm=(-1.5, 2.0), yaw_deg=0.5, clearance_mm=10.0, ankle_mm=2.0, rock_mm=2.5):
    """-> (ok, [failures]). ankle_mm: the IK's miss of the lock's own ankle target; a straight push-off leg can end a mm
    or so short of it while its toe holds the ground (the slip limit judges the foot), so its limit is the slip's x2"""
    bad = []
    for s, rows in rep['stances'].items():
        for r in rows:
            if r['slip_mm_per_frame_max'] > slip_mm:
                bad.append(f'{s} stance {r["frames"]}: slips {r["slip_mm_per_frame_max"]} mm in a frame (limit {slip_mm})')
            if r['drift_mm'] > drift_mm:
                bad.append(f'{s} stance {r["frames"]}: slides {r["drift_mm"]} mm in all (limit {drift_mm})')
            if r['yaw_deg_per_frame_max'] > yaw_deg:
                bad.append(f'{s} stance {r["frames"]}: turns {r["yaw_deg_per_frame_max"]} deg on the ground in a frame '
                           f'(limit {yaw_deg})')
            if r['gap_mm'][0] < gap_mm[0] or r['gap_mm'][1] > gap_mm[1]:
                bad.append(f'{s} stance {r["frames"]}: the sole {r["gap_mm"]} mm over the ground (limits {gap_mm})')
            for f, lift in r['rocks']:
                if lift > rock_mm:
                    bad.append(f'{s} stance {r["frames"]}: rocks at frame {f}, its last contact {lift} mm off the ground '
                               f'(limit {rock_mm})')
    for s, rows in rep['swings'].items():
        for r in rows:
            for f, v in r['touch_frames']:
                bad.append(f'{s} swing {r["frames"]}: touches the ground at frame {f}, moving {v} m/s')
            if r['clearance_mm'] < gap_mm[0]:
                bad.append(f'{s} swing {r["frames"]}: goes {r["clearance_mm"]} mm into the ground')
            if r['mid_clearance_mm'] is not None and r['mid_clearance_mm'] < clearance_mm:
                bad.append(f'{s} swing {r["frames"]}: clears the ground by {r["mid_clearance_mm"]} mm mid-swing '
                           f'(limit {clearance_mm})')
    if rep['worst']['ankle_err_mm'] > ankle_mm:
        bad.append(f'the IK misses an ankle target by {rep["worst"]["ankle_err_mm"]} mm (limit {ankle_mm})')
    if sum(len(rows) for rows in rep['stances'].values()) >= 3 and not rep['double_support']:
        bad.append('no frame has both feet on the ground: the weight never crosses in double support')
    if rep['airborne']:
        bad.append(f'frames {rep["airborne"][:8]} have neither foot on the ground: a walk has no flight')
    return (not bad), bad


def fk_matches_blender(h, body, rep, frames):
    from .ground import posed_foot_world
    sc = bpy.context.scene
    byf = {fr['f']: fr for fr in rep['_frames']}
    worst = 0.0
    for f in frames:
        sc.frame_set(f)
        for s in ('left', 'right'):
            P = posed_foot_world(h, body.feet, s)
            Q = byf[f]['meas'][s]['P']
            worst = max(worst, float(np.max(np.linalg.norm(P - Q, axis=1))))
    return round(worst * 1000, 3)
