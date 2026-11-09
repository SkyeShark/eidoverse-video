"""The controller's acting vocabulary on one take, as the WebGPU course example directs it (examples/obstacle_course.js:
cheer while walking, the sit stop on a bench, the salute) plus the falls and the gaits by name:

    test_controller_acting.py [--vrm aletheia] [--tag NAME]

    1 idle, then walk with an upper-body gesture over the walk (loadGesture / playGesture 'cheer' at weight 2.75),
      the gesture stopped while walking (stopGesture), stop
    2 a full-body emote (loadEmote / playEmote 'salute', facing kept), stopEmote
    3 walk to the bench's seat spot, square up with its back to the bench, sit (beginSeated 'stand_to_sit') on a bench
      5 cm higher than the clip's own seat (seat=: seatOn's settle onto its pan), hold, stand (endSeated reversed at
      1.25x, as the example), stopEmote, walk on
    4 up eight 0.18 m stairs, across a raised slab and off its 1.44 m edge: airborne (fallIdle), the landing deeper than
      fallLandMinDrop (0.85 m) plays fallLand (its feet planted where it lands), then the walk resumes and stops
    5 a backward walk (gait 'walkBackward': the walk clip under the travel, reversed), stop
    6 a jog (gait 'slowRun') on a curve, then a sprint (gait 'fastRun'), slowing to a walk and a stop

Prints PASS / FAIL: checks.feet on every gait's frames, the gesture's weight while the legs walk, the emote's facing,
the hips over the bench at the bench's height, the seated skin resting on the pan and the seated boots on the floor
(the visible mesh), the fall and the landing clip, the backward walk's facing against its travel, the jog's and the
sprint's paces, the stops on their marks, the keyed armature against the bake.
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
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'acting_{VRM}'))
R['vrm'] = VRM
SEGMENTS = [
    {'kind': 'flat', 'length': 7.0},                                    # 0 gesture walk, salute, the bench beside
    {'kind': 'stairs', 'rise': 0.18, 'run': 0.30, 'num': 8, 'dir': 'up'},    # 1 up to 1.44 m
    {'kind': 'flat', 'length': 2.0},                                    # 2 the raised slab
    {'kind': 'stairs', 'rise': 1.44, 'run': 0.30, 'num': 1, 'dir': 'down'},  # 3 its edge: a 1.44 m drop
    {'kind': 'flat', 'length': 16.0},                                   # 4 landing, backward walk, the runs
]
BENCH_XY = (1.45, 1.4)
SEAT_RAISE = 0.05          # the bench this much higher than the seat the stand_to_sit clip was made for


def bench(top):
    """a bench seat (0.5 x 1.1 m, `top` high) beside the walking line, its long side along the course"""
    me = bpy.data.meshes.new('bench')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.5, 1.1, top), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(BENCH_XY[0], BENCH_XY[1], top / 2), verts=bm.verts)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        u, v = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[u], lp.vert.co[v])
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('bench', me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(T.course_materials()['bench'])
    return ob


def main():
    sc = T.S.clean_scene(fps=30)
    course = T.course({'type': 'obstacle_course', 'segments': SEGMENTS})
    me = load_vrm(VRM, name=VRM)
    # the seat's height from the clip: the hips at the end of stand_to_sit, less the hip joint's height over the seat
    from eidoblend.characters.controller import VRMCharacterController  # noqa: F401
    world0 = CollisionWorld()
    loco = Locomotion(me, world0, start=(0.0, -4.5, 0.0), heading=math.pi, log=R.log)
    c = loco.ctrl
    sit_clip = c._emote_clip('stand_to_sit')
    hips_end = c.body.H['hips'].z + float(sit_clip.root_curve[-1][2])
    # a bench 5 cm higher than the clip's own seat (its hips' end less 10 cm): the sit settles onto it (seat=)
    top = round(hips_end - 0.10 + SEAT_RAISE, 3)
    R['seat'] = {'hips_end_z': round(hips_end, 3), 'bench_top': top, 'clip_s': round(sit_clip.duration, 2)}
    R.log(f'stand_to_sit ends with the hips {hips_end:.3f} m up: the bench top at {top:.3f} m')
    bn = bench(top)
    world = CollisionWorld()
    loco.world = world
    c.world = world
    if c._leg_ik is not None:
        c._leg_ik.world = world
    y_slab = course.segment(2)
    y_far = course.segment(4)
    spot = loco.seat_spot(BENCH_XY, -90.0)
    R['seat']['spot'] = spot
    marks = {}
    loco.wait(0.6)
    loco.gesture('cheer', weight=2.75)
    loco.follow_path([(0.0, -1.2)], gait='walk', stop=False)
    loco.stop_gesture()
    marks['gesture_stop'] = (0.0, 0.4)
    loco.move_to(marks['gesture_stop'], gait='walk')
    loco.emote('salute')

    def auto(on):
        def f(ctl):
            ctl.auto_maneuvers = on
        return f
    # the bench is cover to the vault planner (its top over vault_min_rise 0.42): as the WebGPU example does, no
    # maneuver near it
    loco.call(auto(False))
    loco.move_to(spot, gait='walk')
    loco.turn_to(-90)
    loco.sit(hold=2.0, seat=bn)
    loco.call(auto(True))
    marks['after_fall'] = (0.0, y_far['y0'] + 3.5)
    loco.move_to((0.0, 4.6), gait='walk', stop=False)
    loco.move_to(marks['after_fall'], gait='walk')
    marks['backward'] = (0.0, marks['after_fall'][1] - 2.0)
    loco.wait(0.3)
    loco.follow_path([marks['backward']], gait='walkBackward')
    loco.wait(0.4)
    loco.follow_path([(1.0, marks['after_fall'][1] + 1.5), (0.0, marks['after_fall'][1] + 4.5)], gait='slowRun',
                     stop=False)
    marks['end'] = (0.0, y_far['y1'] - 1.5)
    loco.follow_path([marks['end']], gait='fastRun')
    loco.wait(0.8)
    t0 = time.time()
    rep = loco.bake(f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    segs = rep['segments']
    R['segments'] = segs
    T.gait_checks(R, rep)
    r0 = recs[0]['f']
    # 1 the gesture over the walk
    gw = [r['weights'].get('cheer', 0.0) for r in recs if r['lead'] == 'walk' and r['speed'] > 0.5]
    R.check('the cheer plays over the walking legs (weight over 1 while walking)', max(gw, default=0) > 1.0,
            f'gesture weight up to {max(gw, default=0):.2f} on walking frames')
    # 2 the emote and its facing
    em = [r for r in recs if r['mode'] == 'emote' and r['weights'].get('salute', 0) > 0.5]
    if em:
        dh = max(abs(math.degrees(((r['heading'] - em[0]['heading']) + math.pi) % (2 * math.pi) - math.pi)) for r in em)
        R.check('the salute plays (locomotion suspended) facing where she stood', dh < 2.0,
                f'{len(em)} frames, heading moved {dh:.2f} deg')
    else:
        R.check('the salute plays (locomotion suspended)', False, 'no emote frames')
    # 3 the sit: the hips over the bench at its height
    seated = [r for r in recs if r['mode'] == 'seated']
    R.check('the sit plays (seated frames)', len(seated) > 30, f'{len(seated)} seated frames')
    if seated:
        hb = me.humanoid['hips']
        lo, best = 9.0, None
        for r in seated[::3]:
            sc.frame_set(r['f'])
            hp = me.arm.matrix_world @ me.arm.pose.bones[hb].head
            if hp.z < lo:
                lo, best = hp.z, hp.copy()
        inside = abs(best.x - BENCH_XY[0]) < 0.25 and abs(best.y - BENCH_XY[1]) < 0.55
        R.check('the hips come to rest over the bench seat', inside,
                f'hips at ({best.x:.2f}, {best.y:.2f}), the seat at {BENCH_XY}')
        R.check('the hips rest at the seat height (their joint 5 - 15 cm over its top)', 0.05 < lo - top < 0.15,
                f'{(lo - top) * 100:.1f} cm over the top')
        R['seat']['hips_low'] = round(lo, 3)
        # seatOn's settle onto a seat higher than the clip's, the feet on the floor under it
        from eidoblend.characters.controller.film import seat_underside
        fa, fb = seated[0]['f'], seated[-1]['f']
        mid = (fa + fb) // 2
        sc.frame_set(mid)
        hp = me.arm.matrix_world @ me.arm.pose.bones[hb].head
        under = seat_underside(me, (hp.x, hp.y), top - 0.35)
        gap = (under - top) if under is not None else 9.9
        R['seat']['underside_over_pan_m'] = round(gap, 4)
        R.check('the seat settles onto a bench 5 cm higher than the clip\'s (the skin\'s underside within 1.5 cm of '
                'the pan)', abs(gap) < 0.015, f'{gap * 100:+.1f} cm')
        fm = T.FootMesh(me)
        floor = seated[0]['feet_world'][2]
        lows = [min(v['zmin'] for v in fm.at(f).values()) - floor for f in range(fa + (fb - fa) // 3,
                                                                                   fb - (fb - fa) // 3 + 1, 6)]
        R.check('the seated feet stand on the floor (the visible boots within -6 / +10 mm of it through the hold)',
                all(-0.006 <= z <= 0.010 for z in lows), f'{[round(z * 1000, 1) for z in lows]} mm')
    # 4 the fall and the landing
    air = [r for r in recs if not r['grounded']]
    fall_w = max((r['weights'].get('fallIdle', 0.0) for r in recs), default=0.0)
    land = [r for r in recs if r['mode'] == 'maneuver' and r['lead'] == 'fallLand']
    R.check('walking off the edge falls (airborne frames, fallIdle)', len(air) >= 5 and fall_w > 0.5,
            f'{len(air)} airborne frames, fallIdle weight up to {fall_w:.2f}')
    R.check('the landing plays fallLand', len(land) > 5, f'{len(land)} frames led by fallLand')
    # 5 the backward walk
    bw = [r for r in recs if r['backward'] and r['speed'] > 0.3]
    if len(bw) > 3:
        dots = []
        for a, b in zip(bw[:-1], bw[1:]):
            d = Vector(b['feet_world'][:2]) - Vector(a['feet_world'][:2])
            if d.length > 1e-4:
                f_ = Vector((math.sin(b['heading']), -math.cos(b['heading'])))
                dots.append(d.normalized().dot(f_))
        R.check('the backward walk travels against its facing', max(dots) < -0.95, f'travel . facing up to '
                f'{max(dots):.3f} over {len(dots)} frames')
    else:
        R.check('the backward walk plays', False, f'{len(bw)} frames')
    # 6 the jog and the sprint
    for g, frac in (('slowRun', 0.8), ('fastRun', 1.25)):
        sp = [r['speed'] for r in recs if r.get('gait') == g and r['lead'] == 'run' and r['speed'] > 0.5]
        if sp:
            v = float(np.percentile(sp, 90))
            want = frac * loco.native['run']
            R.check(f'the {g} reaches {frac} x the run\'s measured pace', abs(v - want) < 0.08 * want,
                    f'{v:.2f} m/s against {want:.2f}')
        else:
            R.check(f'the {g} plays', False, 'no frames')
    stops = [recs[i]['feet_world'] for i in range(1, len(recs)) if recs[i - 1]['speed'] > 0.05 and recs[i]['speed'] <= 0.05]
    for k in ('gesture_stop', 'after_fall', 'backward', 'end'):
        m = marks[k]
        d = min((math.hypot(p[0] - m[0], p[1] - m[1]) for p in stops), default=9.9)
        R.check(f'stop on its mark: {k}', d < 0.08, f'{d * 100:.1f} cm')
    R['worst'] = rep['worst']
    if T.arg(ARGS, '--dump'):
        T.dump_frames(R, rep, [tuple(int(v) for v in rg.split('-')) for rg in T.arg(ARGS, '--dump').split(',')])
    T.keyed_matches(R, me, frames)
    shots(sc, me, recs, segs, bn)


def shots(sc, me, recs, segs, bn):
    T.light(sc)
    S, sheets = [], {'sheet': []}
    r0 = recs[0]['f']
    for s_ in segs:
        a, b = s_['frames']
        if b - a < 5:
            continue
        f = (a + b) // 2
        sc.frame_set(f)
        name = f'{s_["gait"].replace(":", "-")}_f{f:03d}'
        S.append(T.side_shot(me, recs[f - r0], name))
        sheets['sheet'].append(name)
    # strips: the sit, the fall, the backward walk, from one camera each
    def strip(label, frames_):
        mid = frames_[len(frames_) // 2]
        sc.frame_set(mid)
        cam = T.side_shot(me, recs[mid - r0], 'x', dist=3.4, lead=0.0)
        names = []
        for k, f in enumerate(frames_):
            nm = f'strip_{label}_{k}'
            S.append(dict(cam, name=nm, frame=f))
            names.append(nm)
        sheets[f'strip_{label}'] = names
    seated = [r['f'] for r in recs if r['mode'] == 'seated']
    if seated:
        a = seated[0] - 10
        b = seated[-1] + 40
        strip('sit', [int(a + (b - a) * k / 7) for k in range(8)])
    air = [r['f'] for r in recs if not r['grounded']]
    if air:
        strip('fall', [air[0] - 12 + 5 * k for k in range(8)])
    bw = [r['f'] for r in recs if r['backward'] and r['speed'] > 0.3]
    if bw:
        strip('backward', [bw[0] + 4 * k for k in range(6)])
    ges = [r['f'] for r in recs if r['weights'].get('cheer', 0) > 1.0]
    if ges:
        strip('gesture', [ges[len(ges) // 2] + 3 * k for k in range(6)])
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
