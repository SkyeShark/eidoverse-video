"""The controller across a hillside: a 20 deg slope (a tilted slab, falling toward +X) walked along its contour, one foot
uphill of the other and the travel level; a turn on the spot on the slope; the walk back the other way (the other foot
uphill); a jog across.

    test_controller_cross_slope.py [--vrm claude_robot | aletheia] [--deg 20] [--tag NAME]

My robot body's ankle rolls at most 14.9 deg (robot_dof's cardan, less near its pitch stops), short of a 20 deg slope:
the film bake's plant gives each planted foot one roll off the ground for its whole stance, the most its solved legs
need in its flat part (plant._stance_rolls), so no sole rolls on the slope as the shin moves over it until the
heel-off. Aletheia's legs have no such stop: her feet lie flat on it.

Prints PASS / FAIL: checks.feet on every gait's frames (no planted foot turns more than 0.5 deg or slips more than
1 mm in a frame), every planted foot across the slope holding one roll off it through its flat part (the foot's own
turn about its forward axis, from its landing settled to its heel-off, plant.ROLL_FROM to ROLL_TO of the stance:
within 1 deg a frame and 1.5 deg in all, where the clip's own foot leaves Aletheia's flat on the slope 0.8 and 1.0),
the visible boots out of the slope, the stops on their marks, the keyed armature against the bake. Writes
out/<tag>.json, out/<tag>.blend and out/<tag>_shots.json;
render_shots.py renders a side camera at each gait's middle (from the downhill side) and a low camera in front of the
walk across, at the level of the feet, every four frames of a stride (sheet 'across').

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/test_controller_cross_slope.py
    bash C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/gpu_slot.sh \\
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/render_shots.py \\
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/out/cross_slope_claude_robot_shots.json
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ctrl_stage as T  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.characters.locomotion import FWD  # noqa: E402

P = sys.modules['eidoblend.characters.controller.plant']      # the module (the package re-exports its plant())

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'claude_robot')
DEG = float(T.arg(ARGS, '--deg', '20'))
R = T.Report(T.arg(ARGS, '--tag', f'cross_slope_{VRM}'))
R['vrm'] = VRM
R['slope_deg'] = DEG
TILT = math.radians(DEG)
NRM = np.array((math.sin(TILT), 0.0, math.cos(TILT)))      # the slope's normal: its top falls toward +X
MARKS = {'across': (0.0, 1.5), 'back': (0.0, -4.5), 'jog': (0.0, 1.5)}


def slope_slab(deg):
    """a 16 x 16 m slab 0.5 m thick whose top passes through z = 0 at x = 0 and falls toward +X at `deg`; metre UVs"""
    me = bpy.data.meshes.new('hillside')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 16.0
        v.co.y *= 16.0
        v.co.z = v.co.z * 0.5 - 0.25
    t = math.radians(deg)
    for v in bm.verts:                       # about Y, so +X goes down
        x, z = v.co.x, v.co.z
        v.co.x = x * math.cos(t) + z * math.sin(t)
        v.co.z = -x * math.sin(t) + z * math.cos(t)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        n = f.normal
        for lp in f.loops:
            c = lp.vert.co
            if abs(n.z) > 0.5:
                lp[uv].uv = (c.x / math.cos(t), c.y)
            elif abs(n.x) > 0.5:
                lp[uv].uv = (c.y, c.z)
            else:
                lp[uv].uv = (c.x, c.z)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('hillside', me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(T.pbr_material('ctrl_paving', 'PavingStones128_1k', tile=1.5))
    return ob


def foot_roll(body, fr, s):
    """the foot's roll off the slope about its own forward axis (deg; + turning its up toward -X, uphill), from the
    baked frame's pose through the plant's leg FK"""
    ph, Wh = body.hips(fr['M'], fr['off'], fr['N'])
    W = body.leg_fk(s, ph, Wh, fr['N'])['W_ft']
    f = W @ FWD
    f.normalize()
    u, n = W @ Vector((0.0, 0.0, 1.0)), Vector(NRM)
    u, n = u - f * u.dot(f), n - f * n.dot(f)
    return math.degrees(math.atan2(f.dot(n.cross(u)), n.dot(u)))


def main():
    sc = T.S.clean_scene(fps=30)
    slope_slab(DEG)
    me = load_vrm(VRM, name=VRM)
    world = CollisionWorld()
    loco = Locomotion(me, world, start=(0.0, -5.0, 0.0), heading=math.pi, log=R.log)
    loco.wait(0.6)
    loco.move_to(MARKS['across'], gait='walk')            # across the slope along +Y, the left foot uphill
    loco.wait(0.4)
    loco.turn_by(180)                                     # about, on the slope
    loco.wait(0.4)
    loco.move_to(MARKS['back'], gait='walk')              # back across, the right foot uphill
    loco.wait(0.4)
    loco.turn_by(180)
    loco.wait(0.3)
    loco.move_to(MARKS['jog'], gait='slowRun')            # a jog across
    loco.wait(0.6)
    t0 = time.time()
    rep = loco.bake(f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    segs = rep['segments']
    R['segments'] = [{k: v for k, v in s_.items() if k != 'checks_feet'} for s_ in segs]
    R['rolls_deg'] = rep.get('rolls_deg', {})
    R.log('stance rolls (deg):', R['rolls_deg'])
    T.gait_checks(R, rep)
    # every planted foot across the slope: one roll off it through the stance's flat part (from a quarter of it, its
    # landing settled, to 45 %, where the heel-off begins: the plant's ROLL_FROM and ROLL_TO)
    body = loco.ctrl.body
    worst = (0.0, 0.0, None)
    per = []
    for s in ('left', 'right'):
        for row in rep['stances'][s]:
            a, b = row['frames']
            if row['modes'] != ['loco'] or b - a < 6:
                continue
            k0, k1 = a + int(P.ROLL_FROM * (b - a + 1)), a + int(P.ROLL_TO * (b - a + 1))
            v = [foot_roll(body, frames[f - f0], s) for f in range(k0, max(k1, k0 + 1) + 1)]
            step = max(abs(v[k] - v[k - 1]) for k in range(1, len(v)))
            span = max(v) - min(v)
            per.append((s, [a, b], round(float(np.mean(v)), 1), round(step, 2), round(span, 2)))
            if step > worst[0] or span > worst[1]:
                worst = (max(step, worst[0]), max(span, worst[1]), (s, a, b))
    R['foot_rolls'] = per
    R.check('every planted foot across the slope holds one roll off it through its flat part (within 1 deg a frame, '
            '1.5 deg in all, from its landing settled to its heel-off: as steady as the clip leaves a human foot that '
            'lies flat on it, Aletheia\'s 0.8 and 1.0 deg)', per and worst[0] <= 1.0 and worst[1] <= 1.5,
            f'largest change {worst[0]:.2f} deg a frame, {worst[1]:.2f} deg in a stance ({worst[2]}); per stance '
            f'(side, frames, mean roll off the slope, largest a frame, in all): {per}')
    T.mesh_feet_check(R, me, f0, f1, step=2, limit_mm=10.0, label='the whole take')
    # each walk's last frame (its command's own frames, in order) against its mark
    walks, last = [], None
    for r in recs:
        if r['cmd'] == 'FollowPath' and last != 'FollowPath':
            walks.append([])
        if r['cmd'] == 'FollowPath':
            walks[-1].append(r)
        last = r['cmd']
    for key, run in zip(('across', 'back', 'jog'), walks):
        mk, end = MARKS[key], run[-1]['feet_world']
        d = math.hypot(end[0] - mk[0], end[1] - mk[1])
        R.check(f'the {key} walk stops on its mark', d < 0.08, f'{d * 100:.1f} cm')
    R['worst'] = rep['worst']
    T.keyed_matches(R, me, frames)
    shots(sc, me, recs, segs)


def shots(sc, me, recs, segs):
    T.light(sc)
    S, sheets = [], {'sheet': [], 'across': []}
    r0 = recs[0]['f']
    for s_ in segs:
        a, b = s_['frames']
        if b - a < 5:
            continue
        f = (a + b) // 2
        sc.frame_set(f)
        name = f'{s_["gait"].replace(":", "-")}_f{f:03d}'
        # from the downhill side (+X): 4.2 m uphill the hillside rises 1.5 m, over a camera level with the hips
        side = 1.0 if math.cos(recs[f - r0]['heading']) >= 0.0 else -1.0
        S.append(T.side_shot(me, recs[f - r0], name, side=side))
        sheets['sheet'].append(name)
    # the walk across seen along the travel from in front, low, at the feet: both soles against the tilted ground
    walk = next((s_ for s_ in segs if s_['gait'] == 'walk' and s_['frames'][1] - s_['frames'][0] > 30), None)
    if walk:
        a, b = walk['frames']
        for k, f in enumerate(range(a + 14, min(b, a + 14 + 8 * 4), 4)):
            p = recs[f - r0]['feet_world']
            nm = f'across_{k}'
            S.append(T.fixed_shot(nm, f, (p[0] - 0.2, p[1] + 2.4, p[2] + 0.35), (p[0], p[1], p[2] + 0.25), lens=45.0))
            sheets['across'].append(nm)
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
