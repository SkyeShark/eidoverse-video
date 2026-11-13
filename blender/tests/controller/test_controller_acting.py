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
    7 a plain seat where she stopped (no seat object), stood up from with the stand-up clip played forward
      (reverse=False: its hips' travel taken as root motion)

Prints PASS / FAIL: checks.feet on every gait's frames, the gesture's weight while the legs walk, the emote's facing,
the hips over the bench at the bench's height, the seated skin resting on the pan and never more than 1 cm into the
bench sitting down, held or standing up (the clamp), the seated boots on the floor (the visible mesh), the stand-up
keeping the seat's heading (not the salute's facing), the plain seat's hips held through the stand-up clip's crossfade,
carried forward by it and never back, ending over the spot she sat down from, its boots on the floor through the hold
and one on it at every frame from the hips leaving the seat, the fall and the landing clip, the backward walk's facing against its
travel, the jog's and the sprint's paces, the stops on their marks, the keyed armature against the bake.
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
    # last, a plain seat where she stopped (beginSeated where she stands, no seat object), stood up from with the
    # stand-up clip played forward
    loco.sit(hold=1.0, reverse=False)
    loco.wait(0.5)
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
    # 3 the sit: the hips over the bench at its height (the take's first seat; the plain seat after it is 3b)
    sits = []
    for i, r in enumerate(recs):
        if r['cmd'] == 'Sit':
            if sits and sits[-1][-1] == i - 1:
                sits[-1].append(i)
            else:
                sits.append([i])
    R.check('both sits play (the bench, then the plain seat)', len(sits) == 2, f'{len(sits)} sit commands')
    seated = [recs[i] for i in (sits[0] if sits else []) if recs[i]['mode'] == 'seated']
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
        # the clamp: sitting down, held and standing up, no seated skin goes into the bench (up-rays over its top only)
        from eidoblend.characters.emotes.verbs import skin_lowest
        bb = [bn.matrix_world @ Vector(cn) for cn in bn.bound_box]
        x0, x1 = min(v.x for v in bb) + 0.02, max(v.x for v in bb) - 0.02
        y0, y1 = min(v.y for v in bb) + 0.02, max(v.y for v in bb) - 0.02
        pts = [(x0 + (x1 - x0) * i / 8.0, y0 + (y1 - y0) * j / 16.0) for i in range(9) for j in range(17)]
        worst = (0.0, None)
        for f in range(fa, fb + 1, 2):
            sc.frame_set(f)
            u = skin_lowest(me, pts, top - 0.25)
            if u is not None and u - top < worst[0]:
                worst = (u - top, f)
        R['seat']['deepest_in_bench_m'] = [round(worst[0], 4), worst[1]]
        R.check('the clamp: no seated skin more than 1 cm into the bench sitting down, held or standing up (up-rays '
                'over its top, every 2nd frame)', worst[0] > -0.01,
                f'deepest {worst[0] * 100:+.2f} cm at f{worst[1]}')
        fm = T.FootMesh(me)
        floor = seated[0]['feet_world'][2]
        lows = [min(v['zmin'] for v in fm.at(f).values()) - floor for f in range(fa + (fb - fa) // 3,
                                                                                   fb - (fb - fa) // 3 + 1, 6)]
        R.check('the seated feet stand on the floor (the visible boots within -6 / +10 mm of it through the hold)',
                all(-0.006 <= z <= 0.010 for z in lows), f'{[round(z * 1000, 1) for z in lows]} mm')
        # the salute before the sit set the controller's emote facing: once the root is handed back the body keeps
        # the seat's heading, not that one
        dh = max(abs(math.degrees(math.remainder(recs[i]['heading'] - seated[0]['heading'], 2 * math.pi)))
                 for i in sits[0])
        R.check("the bench stand-up keeps the seat's heading to the walk on (not the earlier salute's facing)",
                dh < 1.0, f"the heading at most {dh:.2f} deg off the seat's over the sit's {len(sits[0])} frames")
    # 3b the plain seat with the stand-up clip forward: its hips' travel taken as root motion (stand_shift)
    if len(sits) > 1:
        hb = me.humanoid['hips']
        pl = sits[1]
        fa, fb = recs[pl[0]]['f'], recs[pl[-1]]['f'] + 1           # to the first frame after it: standing, walking on
        hips, hips_z = {}, {}
        for f in range(fa, fb + 1):
            sc.frame_set(f)
            hp = me.arm.matrix_world @ me.arm.pose.bones[hb].head
            hips[f], hips_z[f] = hp.xy.copy(), hp.z
        up0 = next((recs[i]['f'] for i in pl if recs[i]['weights'].get('sit_to_stand', 0.0) > 0.01), None)
        if up0 is None:
            R.check('the plain seat stands up with the stand-up clip', False, 'no sit_to_stand weight')
        else:
            h = recs[pl[0]]['heading']
            fwd = Vector((math.sin(h), -math.cos(h)))
            fade = int(round(0.25 * 30))
            held = max((hips[f] - hips[up0 - 1]).length for f in range(up0, up0 + fade + 1))
            steps = [(hips[f] - hips[f - 1]) for f in range(up0, fb + 1)]
            big = max(d.length for d in steps)
            back = max(-d.dot(fwd) for d in steps)
            end = (hips[fb] - hips[fa]).length
            R['plain_seat'] = {'frames': [fa, fb], 'stand_clip_from': up0, 'crossfade_hips_cm': round(held * 100, 2),
                               'step_max_cm': round(big * 100, 2), 'back_max_cm': round(back * 100, 2),
                               'seated_hips_back_cm': round((hips[fa] - hips[up0 - 1]).dot(fwd) * 100, 1),
                               'end_from_start_cm': round(end * 100, 2)}
            R.check("the plain seat: through the stand-up clip's crossfade the hips stay on the seat (within 1 cm)",
                    held < 0.01, f"{held * 100:.2f} cm over the {fade} frames from f{up0}")
            R.check('the plain seat: the stand-up clip carries the hips forward, never back (at most 2.5 cm a frame, '
                    'none over 0.5 cm back)', big < 0.025 and back < 0.005,
                    f'largest step {big * 100:.2f} cm, largest back {back * 100:.2f} cm, f{up0}-f{fb}')
            R.check('the plain seat: she stands up over the spot she sat down from (the hips within 3 cm)', end < 0.03,
                    f"{end * 100:.2f} cm, the seated hips {R['plain_seat']['seated_hips_back_cm']:.1f} cm behind it")
            # the seat's feet (the plant keeps a seat's stance: no early toe-off at its end): both boots on the floor
            # through the hold, and one on it at every frame from the hips leaving the seat (2 cm over their seated
            # height as the stand-up starts) to standing
            fm = T.FootMesh(me)
            floor = recs[pl[0]]['feet_world'][2]
            hold = range(fa + int(0.6 * (up0 - fa)), up0, 2)
            low = {f: {s: v['zmin'] - floor for s, v in fm.at(f).items()} for f in list(hold) + list(range(up0, fb + 1))}
            worst = max((abs(z) for f in hold for z in low[f].values()), default=9.9)
            off = next((f for f in range(up0, fb + 1) if hips_z[f] > hips_z[up0 - 1] + 0.02), fb)
            up = [f for f in range(off, fb + 1) if min(low[f].values()) > 0.010]
            R['plain_seat'].update(feet_hold_mm=round(1000 * worst, 1), hips_leave_seat=off, rise_frames_no_foot_down=up[:8])
            R.check('the plain seat: both boots on the floor through the hold (within 10 mm)', worst < 0.010,
                    f'{worst * 1000:.1f} mm at most over f{hold[0]}-f{hold[-1]}')
            R.check('the plain seat: a boot on the floor at every frame from the hips leaving the seat to standing '
                    '(within 10 mm)', not up, f'{len(up)} frames of f{off}-f{fb} with neither boot down: {up[:8]}')
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
    runs = []
    for r in recs:
        if r['mode'] == 'seated':
            if runs and runs[-1][1] == r['f'] - 1:
                runs[-1][1] = r['f']
            else:
                runs.append([r['f'], r['f']])
    if runs:
        a = runs[0][0] - 10
        b = runs[0][1] + 40
        strip('sit', [int(a + (b - a) * k / 7) for k in range(8)])
    up = [r['f'] for r in recs if r['weights'].get('sit_to_stand', 0.0) > 0.01]
    if len(runs) > 1 and up:
        # the plain seat's stand-up clip: from the end of the hold to standing, every 6 frames
        a = up[0] - 6
        strip('plain_stand', [a + 6 * k for k in range(min(14, (up[-1] + 12 - a) // 6 + 1))])
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
