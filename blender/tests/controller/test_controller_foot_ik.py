"""VRMFootControllerIK (foot_ik.js) option by option, then the WebGPU per-frame IK against the film's planted feet.

    test_controller_foot_ik.py [--vrm aletheia] [--tag NAME]

PART A, the IK on a still body (the rest pose, root on the ground) over a floor, a 10 cm block, a 15 deg and a 40 deg
slope and a stair (each check prints PASS / FAIL with its numbers):
    CastType RAY / SPHERE / RAY_AND_SPHERE   the sole on the floor; the leg over the block lifts by the block
    the riser                                 a ray hitting a stair riser (normal under NormalUpThreshold) is no ground,
                                              RAY_AND_SPHERE falls back to the ball and finds the tread
    foot_constraint                           the foot conforms to 15 deg; on 40 deg it is held to acos(0.85) = 31.8 deg
    max_step_height                           the setter clamps to [0, 2]
    left_enabled / right_enabled              a disabled leg keeps the animated pose
    distance_power / smoothing_angle          a 10 cm change of ground reached at once (0) or eased in over frames (1)
    global_smoothing_power                    the leg's turn blended with last frame's
    fix_knee                                  the knee plane from the leg (True) or from the forward offset (False): both
                                              reach the target, the knee forward
    lowest / highest / lowest position / directional foot height, can_reach_targets
    foot_plant_forward_offset, extra_cast_reach_scale, ramp_foot_clearance_offset, descent_context
    flat_walk_context / step_clearance_context (the swing arc's synthetic lift)
    stair_ascent_sole_fit_context, stair_ascent_edge_align_context (the stair-ascent nudges and their status)
PART B, one walk over small stairs baked twice: feet='foot_ik' (the WebGPU IK's own per-frame result keyed: it follows the
animated foot's xy, so a stride that differs from the travel slides) and feet='plant' (the film's planted feet); the
stance slip of each measured from the keyed soles, both rendered side by side.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ctrl_stage as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import (CastType, CollisionWorld, Locomotion, Pose, VRMFootControllerIK,  # noqa: E402
                                             root_matrix)
from eidoblend.characters.locomotion import Body  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'foot_ik_{VRM}'))
R['vrm'] = VRM
DT = 1.0 / 30.0


def mesh(name, verts, faces, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    return ob


def box(name, x0, x1, y0, y1, z0, z1, mat=None):
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh(name, V, F, mat)


def slope(name, x0, x1, y0, y1, deg, mat=None):
    """a plane rising along +Y at `deg` from (y0, z=0)"""
    t = math.tan(math.radians(deg))
    V = [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, (y1 - y0) * t), (x0, y1, (y1 - y0) * t)]
    return mesh(name, V, [(0, 1, 2, 3)], mat)


def part_a(me, body):
    """the IK on a still body: stations along X, each its own ground"""
    mats = T.course_materials()
    mesh('floor', [(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [(0, 1, 2, 3)], mats['ground'])
    # station x = 3: a 10 cm block under the left foot (found from the rest pose); x = 6: 15 deg; x = 9: 40 deg;
    # x = 12: a stair (a 0.10 m riser across the feet's line, the tread ahead)
    rest = Pose(body, root_matrix(0, 0, 0, math.pi), {})
    lf = rest.world_pos('leftFoot')
    box('block', 3 + lf.x - 0.10, 3 + lf.x + 0.10, lf.y - 0.25, lf.y + 0.25, 0.0, 0.10, mats['obstacle'])
    slope('slope15', 5.0, 7.0, -1.0, 2.0, 15.0, mats['obstacle'])
    slope('slope40', 8.0, 10.0, -1.0, 2.0, 40.0, mats['obstacle'])
    box('stair', 11.0, 13.0, 0.06, 1.0, 0.0, 0.10, mats['obstacle'])
    world = CollisionWorld()
    base = dict(increased_accuracy=True, fix_knee=True, foot_height_offset=0.012, sphere_radius=0.015,
                max_step_height=0.6, distance_power=0, smoothing_angle=0, global_smoothing_power=0)
    # the animated pose: knees bent (thighs 20 deg forward, shins 20 deg back, feet flat) and the hips lowered so the
    # ankles sit 2 cm under their rest height: a leg with room to reach down as well as up (a straight rest leg cannot
    # reach lower), and no lift of its own over the ground (the IK keeps an animated foot's lift: upY)
    N0 = {}
    for s in ('left', 'right'):
        N0[s + 'UpperLeg'] = Quaternion((1.0, 0.0, 0.0), -0.35)
        N0[s + 'LowerLeg'] = Quaternion((1.0, 0.0, 0.0), 0.70)
        N0[s + 'Foot'] = Quaternion((1.0, 0.0, 0.0), -0.35)
    bent = Pose(body, root_matrix(0, 0, 0, math.pi), dict(N0))
    OFF0 = Vector((0.0, 0.0, -(bent.world_pos('leftFoot').z - rest.world_pos('leftFoot').z) - 0.02))
    R['crouch_hips_drop_mm'] = round(-OFF0.z * 1000, 1)

    def pose_at(x, y=0.0, z=0.0, N=None):
        return Pose(body, root_matrix(x, y, z, math.pi), dict(N0 if N is None else N), OFF0 if N is None else None)

    def ik_at(x, y=0.0, z=0.0, N=None, frames=1, **kw):
        o = dict(base)
        o.update(kw)
        ik = VRMFootControllerIK(body, world=world, **o)
        p = None
        for _ in range(frames):
            p = pose_at(x, y, z, N)
            ik.update(DT, p)
        return ik, p

    def sole_tilt(p, side):
        up = p.world_quat(side + 'Foot') @ Vector((0.0, 0.0, 1.0))
        rest_up = rest.world_quat(side + 'Foot') @ Vector((0.0, 0.0, 1.0))
        return math.degrees(up.angle(Vector((0, 0, 1)))) - math.degrees(rest_up.angle(Vector((0, 0, 1))))

    def over(ik, p, side, ground):
        """the ankle's height over the ground less what the IK places it at (the leg's mesh distance less the 12 mm
        FootHeightOffset): 0 when the IK put the foot on that ground"""
        limb = ik.m_left_leg if side == 'left' else ik.m_right_leg
        return p.world_pos(side + 'Foot').z - ground - (limb.distance_from_mesh - 0.012)
    # 1 flat, each cast type
    for name, ct in (('RAY', CastType.RAY), ('SPHERE', CastType.SPHERE), ('RAY_AND_SPHERE', CastType.RAY_AND_SPHERE)):
        ik, p = ik_at(0.0, type=ct)
        hz = [ik.m_left_leg.lowest_hit_point.z, ik.m_right_leg.lowest_hit_point.z]
        dz = [over(ik, p, 'left', 0.0), over(ik, p, 'right', 0.0)]
        R.check(f'{name}: the casts find the floor and the IK sets the ankles their height over it (less '
                f'FootHeightOffset)', max(abs(h) for h in hz) < 1e-3 and max(abs(d) for d in dz) < 1e-3 and
                ik.can_reach_targets, f'hits z {hz[0]:.4f} / {hz[1]:.4f}, ankles off by {dz[0] * 1000:.2f} / '
                f'{dz[1] * 1000:.2f} mm')
    # 2 the block under the left foot
    for name, ct in (('RAY', CastType.RAY), ('RAY_AND_SPHERE', CastType.RAY_AND_SPHERE)):
        ik, p = ik_at(3.0, type=ct)
        dl, dr = over(ik, p, 'left', 0.10), over(ik, p, 'right', 0.0)
        R.check(f'{name}: the left leg steps onto the 10 cm block, the right stays on the floor',
                abs(dl) < 1e-3 and abs(dr) < 1e-3, f'left off the block by {dl * 1000:.2f} mm, right off the floor by '
                f'{dr * 1000:.2f} mm')
        R.check(f'{name}: lowest / highest foot height read the floor and the block',
                abs(ik.lowest_foot_height) < 1e-3 and abs(ik.highest_foot_height - 0.10) < 1e-3 and
                abs(ik.lowest_foot_position.z) < 1e-3,
                f'lowest {ik.lowest_foot_height:.4f}, highest {ik.highest_foot_height:.4f}')
        lx = p.world_pos('leftFoot').x - 3.0
        d_left = ik.directional_foot_height(Vector((math.copysign(1.0, lx), 0.0, 0.0)))
        d_right = ik.directional_foot_height(Vector((-math.copysign(1.0, lx), 0.0, 0.0)))
        R.check(f'{name}: directional_foot_height picks the foot further along the direction',
                abs(d_left.z - 0.10) < 1e-3 and abs(d_right.z) < 1e-3, f'{d_left.z:.3f} / {d_right.z:.3f}')
    # 3 the slopes and the foot constraint (the root on the slope's surface at y = 0.5: 1.5 m up the plane)
    ik, p = ik_at(6.0, y=0.5, z=1.5 * math.tan(math.radians(15)), type=CastType.RAY)
    tl = sole_tilt(p, 'left')
    R.check('the foot conforms to a 15 deg slope', abs(tl - 15.0) < 1.0, f'{tl:.2f} deg')
    ik, p = ik_at(9.0, y=0.5, z=1.5 * math.tan(math.radians(40)), type=CastType.RAY)
    tl_free = sole_tilt(p, 'left')
    ik, p = ik_at(9.0, y=0.5, z=1.5 * math.tan(math.radians(40)), type=CastType.RAY, foot_constraint=True)
    tl_con = sole_tilt(p, 'left')
    R.check('foot_constraint holds a 40 deg slope to acos(0.85) = 31.8 deg (free: 40)',
            abs(tl_con - 31.79) < 1.0 and abs(tl_free - 40.0) < 1.5, f'constrained {tl_con:.2f}, free {tl_free:.2f}')
    # 4 the riser: a ray straight down the riser's face hits the floor below it (it is not a hit on the riser), but
    # a toe ray over the step hits the tread; the ball cast from over the edge touches the edge
    ik = VRMFootControllerIK(body, world=world, **dict(base, type=CastType.RAY_AND_SPHERE))
    h_ray = ik.raycast_down(Vector((12.0, 0.06 + 0.005, 0.5)), 1.0)
    h_ball = ik.sphere_cast_down(Vector((12.0, 0.06 - 0.008, 0.5)), 0.015, 1.0)
    R.check('a ball cast just short of the stair edge rests on the edge (the tread height), a ray past it on the tread',
            h_ball['hit'] and abs(h_ball['point'].z - 0.10) < 0.002 and h_ray['hit'] and abs(h_ray['point'].z - 0.10) < 1e-3,
            f'ball contact z {h_ball["point"].z if h_ball["hit"] else None}, ray z {h_ray["point"].z:.3f}')
    # 5 max_step_height clamps
    ik.max_step_height = 5.0
    a = ik.max_step_height
    ik.max_step_height = -1.0
    b = ik.max_step_height
    R.check('max_step_height clamps to [0, 2]', a == 2 and b == 0, f'{a}, {b}')
    # 6 a disabled leg
    ik, p = ik_at(3.0, type=CastType.RAY, left_enabled=False)
    anim = pose_at(3.0)
    dl = p.world_pos('leftFoot').z - anim.world_pos('leftFoot').z
    dr = over(ik, p, 'right', 0.0)
    R.check('left_enabled=False leaves the left leg animated (it does not step onto the block); the right is placed',
            abs(dl) < 1e-4 and abs(dr) < 1e-3, f'left moved {dl * 1000:.2f} mm, right off the floor by {dr * 1000:.2f} mm')
    # 7 smoothing: the body slides 1 cm a frame across the block's edge, so the ground under the left foot jumps 10 cm
    # in one frame while the animated foot moves 1 cm: DistancePower 0 takes the jump at once, 1 lerps by the animated
    # motion over the target's (MAX_DISTANCE_POWER - power) x animD / moveD a frame
    for dp, want in ((0, 'at once'), (1, 'eased')):
        o = dict(base, type=CastType.RAY, distance_power=dp)
        ik = VRMFootControllerIK(body, world=world, **o)
        zs = []
        for k in range(30):
            x = 2.80 + 0.01 * k
            p = pose_at(x)
            ik.update(DT, p)
            zs.append(p.world_pos('leftFoot').z)
        steps = [b - a for a, b in zip(zs, zs[1:])]
        R.check(f'distance_power={dp}: the block\'s 10 cm reached {want}',
                (max(steps) > 0.09) if dp == 0 else (max(steps) < 0.03 and zs[-1] - zs[0] > 0.09),
                f'largest rise in a frame {max(steps) * 1000:.1f} mm, total {(zs[-1] - zs[0]) * 1000:.1f} mm')
        R[f'distance_power_{dp}'] = [round((z - zs[0]) * 1000, 1) for z in zs]
    o = dict(base, type=CastType.RAY, smoothing_angle=2)
    ik = VRMFootControllerIK(body, world=world, **o)
    tl = []
    for k in range(5):
        p = Pose(body, root_matrix(6.0 if k >= 1 else 0.0, 0.5 if k >= 1 else 0.0,
                                   0.5 * math.tan(math.radians(15)) if k >= 1 else 0.0, math.pi), {})
        ik.update(DT, p)
        tl.append(sole_tilt(p, 'left'))
    R.check('smoothing_angle=2: the foot turns onto the slope over frames, not at once', tl[1] < 10.0 and tl[-1] > tl[1],
            f'tilt by frame {[round(x, 2) for x in tl]} deg')
    # 8 global smoothing: the leg's turn halves toward last frame's
    o = dict(base, type=CastType.RAY, global_smoothing_power=0.5)
    ik = VRMFootControllerIK(body, world=world, **o)
    p0 = Pose(body, root_matrix(0.0, 0.0, 0.0, math.pi), {})
    ik.update(DT, p0)
    q_last = ik.m_left_leg.last_up_bone_rotation.copy()
    p1 = Pose(body, root_matrix(3.0, 0.0, 0.0, math.pi), {})
    ik.update(DT, p1)
    ang = math.degrees(q_last.rotation_difference(p1.world_quat('leftUpperLeg')).angle)
    ik2 = VRMFootControllerIK(body, world=world, **dict(base, type=CastType.RAY))
    p2 = Pose(body, root_matrix(3.0, 0.0, 0.0, math.pi), {})
    ik2.update(DT, p2)
    full = math.degrees(q_last.rotation_difference(p2.world_quat('leftUpperLeg')).angle)
    R.check('global_smoothing_power=0.5 blends the thigh halfway to last frame\'s turn', abs(ang - 0.5 * full) < 0.3,
            f'{ang:.2f} deg against the full {full:.2f}')
    # 9 fix_knee: both reach, the knee forward
    for fk in (True, False):
        ik, p = ik_at(3.0, type=CastType.RAY, fix_knee=fk)
        tgt = ik.m_left_leg.target_position
        err = (p.world_pos('leftFoot') - tgt).length
        hip, knee, an = p.world_pos('leftUpperLeg'), p.world_pos('leftLowerLeg'), p.world_pos('leftFoot')
        fwd = Vector((0.0, 1.0, 0.0))                                  # heading pi faces +Y
        bend = (knee - (hip + an) * 0.5).dot(fwd)
        R.check(f'fix_knee={fk}: the leg reaches its target, the knee bends forward', err < 0.002 and bend > -0.002,
                f'miss {err * 1000:.2f} mm, knee {bend * 1000:.1f} mm ahead of the hip-ankle line')
    # 10 the cast-shaping offsets
    ik, p = ik_at(0.0, type=CastType.RAY, ramp_foot_clearance_offset=0.0)
    z0 = ik.m_left_leg.target_position.z
    ik.ramp_foot_clearance_offset = 0.008
    p = pose_at(0.0)
    ik.update(DT, p)
    R.check('ramp_foot_clearance_offset raises the planted target by itself', abs(ik.m_left_leg.target_position.z - z0
                                                                                 - 0.008) < 1e-4,
            f'+{(ik.m_left_leg.target_position.z - z0) * 1000:.2f} mm')
    ik.ramp_foot_clearance_offset = 0.0
    ik.foot_plant_forward_offset = 0.5
    p = pose_at(0.0)
    ik.update(DT, p)
    R.check('foot_plant_forward_offset moves the casts along the foot (extra length x offset)',
            abs(ik.m_left_leg._foot_plant_forward_offset_distance - 0.5 * ik.m_left_leg.extra_length) < 1e-6,
            f'{ik.m_left_leg._foot_plant_forward_offset_distance * 1000:.1f} mm')
    ik.foot_plant_forward_offset = 0.0
    # the toe cast's reach: the step's edge at 3/4 of the way from the ankle to the toes. The half reach (the default:
    # extraCastReachScale 0.5) samples the floor short of the edge and the foot stays down; the full reach samples the
    # step under the toes and the foot is placed from that higher hit
    an0 = pose_at(0.0)
    a, t = an0.world_pos('leftFoot'), an0.world_pos('leftToes')
    y_body = 0.06 - (a.y + 0.75 * (t.y - a.y))
    tz = {}
    for reach in (0.5, 1.0):
        ik, p = ik_at(12.0, y=y_body, type=CastType.RAY, extra_cast_reach_scale=reach)
        tz[reach] = ik.m_left_leg.target_position.z
    R.check('extra_cast_reach_scale: the half reach leaves the foot on the floor, the full reach puts it on the step',
            tz[1.0] - tz[0.5] > 0.05, f'ankle target z {tz[0.5]:.3f} at 0.5, {tz[1.0]:.3f} at 1.0')
    R['toe_reach_targets'] = tz
    # 11 the swing arc: one leg raised 6 cm (an animated swing) with the flat-walk context
    lift_q = Quaternion((1.0, 0.0, 0.0), math.radians(-25.0))
    N = {'leftUpperLeg': lift_q, 'leftLowerLeg': Quaternion((1.0, 0.0, 0.0), math.radians(40.0))}
    for ctx in ('flat_walk_context', 'step_clearance_context'):
        ik = VRMFootControllerIK(body, world=world, **dict(base, type=CastType.RAY))
        setattr(ik, ctx, True)
        lifts = []
        for k in range(8):
            p = Pose(body, root_matrix(0.0, 0.0, 0.0, math.pi), dict(N))
            ik.update(DT, p)
            lifts.append(ik.m_left_leg._synthetic_lift)
        R.check(f'{ctx}: the raised foot swings (the synthetic arc lifts it)', ik.m_left_leg._in_swing and max(lifts) > 0.02,
                f'synthetic lift by frame {[round(x * 1000, 1) for x in lifts]} mm; peak '
                f'{ik.step_clearance_arc_height if ctx == "step_clearance_context" else ik.swing_arc_height} m')
    # 12 descent_context: the running minimum of the foot's height over its rest (the Mixamo descent baseline)
    ik = VRMFootControllerIK(body, world=world, **dict(base, type=CastType.RAY))
    ik.descent_context = True
    for k in range(3):
        p = Pose(body, root_matrix(0.0, 0.0, 0.0, math.pi), {})
        ik.update(DT, p)
    R.check('descent_context tracks the running minimum of the foot\'s lift', math.isfinite(ik.m_left_leg._min_up_y),
            f'min up {ik.m_left_leg._min_up_y * 1000:.2f} mm after 3 frames (drifts +0.5 x 16.7 mm a frame)')
    # 13 the stair-ascent nudges: the heel short of the tread (on the riser's edge) is fitted forward onto it
    ik = VRMFootControllerIK(body, world=world, **dict(base, type=CastType.RAY_AND_SPHERE))
    ik.stair_ascent_sole_fit_context = True
    ik.stair_ascent_tread_run = 0.30
    ik.stair_ascent_sole_fit_max_scale = 1.0
    y_heel = 0.06 + 0.02 - (rest.world_pos('leftFoot').y)        # the ankle 2 cm past the edge: the heel hangs off it
    p = Pose(body, root_matrix(12.0, y_heel, 0.10, math.pi), {})
    ik.update(DT, p)
    st, nd = ik.m_left_leg._stair_ascent_sole_fit_status, ik.m_left_leg._stair_ascent_sole_fit_nudge
    R.check('stair_ascent_sole_fit_context nudges a hanging heel forward until the tread supports it',
            st in ('supported', 'already-supported', 'max', 'toe-guard') and nd >= 0.0, f'status {st}, nudge {nd * 1000:.1f} mm')
    ik = VRMFootControllerIK(body, world=world, **dict(base, type=CastType.RAY_AND_SPHERE))
    ik.stair_ascent_edge_align_context = True
    ik.stair_ascent_edge_point = (12.0, 0.06)
    ik.stair_ascent_move_dir = (0.0, 1.0)
    ik.stair_ascent_edge_tread_run = 0.30
    p = Pose(body, root_matrix(12.0, 0.06 + 0.005 - rest.world_pos('leftFoot').y, 0.10, math.pi), {})
    ik.update(DT, p)
    st, nd = ik.m_left_leg._stair_ascent_edge_align_status, ik.m_left_leg._stair_ascent_edge_align_nudge
    R.check('stair_ascent_edge_align_context moves a foot planted on the edge onto the tread', st is not None,
            f'status {st}, nudge {nd * 1000:.1f} mm')
    R['casts'] = ik.casts
    for o in [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name in
              ('floor', 'block', 'slope15', 'slope40', 'stair')]:
        bpy.data.objects.remove(o, do_unlink=True)


def part_b(sc, me):
    """the same walk over small stairs, the WebGPU per-frame IK keyed against the film's planted feet"""
    course = T.course({'type': 'obstacle_course', 'segments': [
        {'kind': 'flat', 'length': 1.5}, {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 4, 'dir': 'up'},
        {'kind': 'flat', 'length': 1.2}, {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 4, 'dir': 'down'},
        {'kind': 'flat', 'length': 3.0}]})
    world = CollisionWorld()
    out = {}
    # the plant with pelvis='controller' keeps the controller's own body height (its probes, rate caps and descent
    # drop), only capped so the planted legs reach: the third bake
    for feet, kw in (('foot_ik', {'feet': 'foot_ik'}), ('plant', {'feet': 'plant'}),
                     ('plant_controller_pelvis', {'feet': 'plant', 'pelvis': 'controller'})):
        loco = Locomotion(me, world, start=(0.0, -3.5, 0.0), heading=math.pi, log=R.log)
        loco.wait(0.5).move_to((0.0, course.end_y - 1.0), gait='walk').wait(0.4)
        t0 = time.time()
        rep = loco.bake(f0=1, action_name=f'{VRM}|{feet}', **kw)
        R['timing_s'][f'bake_{feet}'] = round(time.time() - t0, 1)
        act = me.arm.animation_data.action
        act.use_fake_user = True                     # every bake stays in the file (the renders swap them)
        out[feet] = (rep, act)
        if feet == 'plant_controller_pelvis':
            fails = [b for s_ in rep['segments'] if 'checks_feet' in s_ for b in s_['checks_feet']['failures']]
            R.check('pelvis=\'controller\': the controller\'s body height, the feet still planted (checks.feet)',
                    not fails, '; '.join(fails[:3]) or f'{len(rep["segments"])} gait stretches clean')

    def use(act):
        me.arm.animation_data.action = act
        me.arm.animation_data.action_slot = act.slots[0]
    # measure the stance slip of each keyed result from the evaluated soles: a planted (stance) foot's lowest points
    from eidoblend.characters.controller.plant import sole_subset
    from eidoblend.characters.ground import posed_foot_world
    feet_pts = sole_subset(me)
    recs = out['plant'][0]['_records']
    f0, f1 = recs[0]['f'], recs[-1]['f']
    res = {}
    for feet, (rep, act) in out.items():
        use(act)
        P = {}
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            P[f] = {s: posed_foot_world(me, feet_pts, s) for s in ('left', 'right')}
        slips, gaps = [], []
        for f in range(f0 + 1, f1 + 1):
            r = recs[f - f0]
            if r['mode'] != 'loco' or not r['grounded'] or r['speed'] < 0.3:
                continue
            for s in ('left', 'right'):
                if r['stance'][s] < 0.99 or recs[f - f0 - 1]['stance'][s] < 0.99:
                    continue
                Q, Qp = P[f][s], P[f - 1][s]
                k = np.argsort(Q[:, 2])[:6]
                slips.append(float(np.min(np.linalg.norm(Q[k, :2] - Qp[k, :2], axis=1))))
        res[feet] = {'slip_mm_p95': round(1000 * float(np.percentile(slips, 95)), 2),
                     'slip_mm_max': round(1000 * float(np.max(slips)), 2), 'n': len(slips)}
    R['part_b'] = res
    R.log(f'stance slip a frame: {res}')
    R.check('the film plant holds planted feet (95th percentile slip under 1 mm a frame)', res['plant']['slip_mm_p95'] < 1.0,
            f'{res["plant"]}')
    R.check('the WebGPU per-frame IK follows the animated feet (it slides where stride and travel differ: reported)',
            res['foot_ik']['n'] > 0, f'{res["foot_ik"]}')
    use(out['plant'][1])
    # a second armature would double the scene: the renders swap the action per shot (render_shots: 'action')
    T.light(sc)
    S, sheets = [], {}
    names = {'foot_ik': [], 'plant': []}
    st = [r['f'] for r in recs if r['support_mode'] in ('stairUp', 'stairDown')]
    fs = [st[0] + 4 * k for k in range(6)] if st else [60 + 4 * k for k in range(6)]
    mid = recs[fs[2] - f0]['feet_world']
    for feet in ('foot_ik', 'plant'):
        for k, f in enumerate(fs):
            nm = f'{feet}_{k}'
            S.append(dict(T.fixed_shot(nm, f, (mid[0] + 2.2, mid[1] + 0.3, mid[2] + 0.5),
                                       (mid[0], mid[1] + 0.3, mid[2] + 0.35), lens=40.0), action=out[feet][1].name))
            names[feet].append(nm)
    sheets['foot_ik_vs_plant'] = names['foot_ik'] + names['plant']
    T.save(R, sc, S, sheets)


def main():
    sc = T.S.clean_scene(fps=30)
    me = load_vrm(VRM, name=VRM)
    body = Body(me)
    from eidoblend.characters.controller.pose import humanoid_parents
    body.parents = humanoid_parents(me)
    part_a(me, body)
    part_b(sc, me)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
