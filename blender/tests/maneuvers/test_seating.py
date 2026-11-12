"""scene_placement.js's seating verbs on a body the character controller walks (eidoblend.characters.emotes):

    test_seating.py [--vrm aletheia] [--tag NAME]

One take on a floor with two chairs (backrests, built at angles) and the scene camera:
    1 seat_on(chair A): the walk to the spot the stand_to_sit clip's own hip travel needs, the turn out of the chair
      (its facing from its backrest), the sit-down with the clamp and the settle; seated (hold=None), wait, stand_up
      (the sit-down reversed, the example's)
    2 seat_on(chair B, a 0.56 m seat, its backrest toward the approach: the walk goes round it), then the seated loop
      'sitting_nervous_arm_rub_chair' (the root carried so the hips stay on the seat), hold, stand_up with
      'sit_to_stand' (its hips travel taken as root motion)
    3 sit_on_ground(at=...): facing the camera, 'sitting_on_ground' crossfaded in, held, back up
    4 face_camera, then emote('salute', facing='camera')

Prints PASS / FAIL: the hips on each seat's target, the seated skin on the pan (within 1.5 cm), the clamp (no skin
under the pan through the descent), the facing out of each chair, the seated boots on the floor, the hips still through
the seated loop's crossfade, no pop when the root returns after sit_to_stand, the feet still through it, the ground sit
resting on the floor, the camera facings, eido_seated keyed on the seated frames only, checks.feet on the walks, the
keyed armature against the bake; and through each WHOLE seat (_mnv_stage.whole_seat_checks / floor_checks): the seat
skin on the pan through the stand-up too, nothing of the body in a chair's back and nothing of it or its coat out
behind it, the body out of the pan and the legs, the body out of the floor through a ground sit's crossfades (near
the hips, and the whole of it: the legs and boots laid out in front). The ground sits rest the lowest of the skin near
the hips on the floor (the engine's grid of up-rays is reported beside it). Stills: strips of each sit, close-ups of the
seats, the scene camera's salute.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _mnv_stage as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.characters import emotes as E  # noqa: E402
from eidoblend.characters.emotes.verbs import skin_lowest  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'seating_{VRM}'))
R['vrm'] = VRM
CAM = ((5.5, -2.0, 1.7), (0.0, 3.0, 0.7))


def deepest_solid(fm, P):
    """which solid the deepest of these foot points is inside (FootMesh's parity test), or 'nothing'"""
    best = None
    for name, bvh, lo, hi in fm.solids:
        for p in P:
            if np.all(p >= lo - 0.01) and np.all(p <= hi + 0.01) and fm._inside(bvh, Vector(p)):
                loc, _n, _i, d = bvh.find_nearest(Vector(p), 0.3)
                if loc is not None and (best is None or d > best[1]):
                    best = (name, d)
    return 'nothing' if best is None else f'{best[0]} ({best[1] * 1000:.0f} mm)'


def main():
    sc = T.S.clean_scene(fps=30)
    T.floor()
    chair_a = T.chair('chair_a', (1.4, 1.6), math.radians(-110))
    chair_b = T.chair('chair_b', (-1.6, 4.4), math.radians(160), seat_h=0.56, back_h=1.02)
    cam = T.scene_camera(*CAM)
    me = load_vrm(VRM, name=VRM)
    # the seats are not walked on (as the course's rungs): the controller's probes would read a pan as a step
    seats = [o for ch in (chair_a, chair_b) for o in ch.children_recursive]
    loco = Locomotion(me, CollisionWorld(exclude=seats), start=(0.0, -3.0, 0.0), heading=math.pi, log=R.log)
    c = loco.ctrl
    loco.wait(0.5)
    E.seat_on(loco, chair_a)
    cmd_a = loco._queue[-1]
    loco.wait(1.5)
    E.stand_up(loco)
    E.seat_on(loco, chair_b, then='sitting_nervous_arm_rub_chair', hold=3.0, stand={'clip': 'sit_to_stand'})
    cmd_b = loco._queue[-1]
    ground_at = (1.3, 6.0)
    E.sit_on_ground(loco, at=ground_at, hold=2.5)
    cmd_g = loco._queue[-1]
    E.face_camera(loco)
    loco.wait(0.3)
    E.emote(loco, 'salute', facing='camera')
    loco.wait(0.4)
    t0 = time.time()
    rep = E.bake(loco, f0=1)
    bpy.data.actions[f'{me.name}|controller'].use_fake_user = True   # it survives the second take and the save
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    if T.arg(ARGS, '--dump'):
        T._C.dump_frames(R, rep, [tuple(int(v) for v in rg.split('-')) for rg in T.arg(ARGS, '--dump').split(',')])
        R['pelvis_lowered_mm'] = rep.get('pelvis_lowered_mm')
    R['segments'] = rep['segments']
    spans = rep['seated']['spans']
    R['seated_spans'] = spans
    R['facing_check'] = rep['seated']['facing']
    fps = 30.0
    R.check('three seats in the take (two chairs and the ground)', len(spans) == 3, f'{spans}')
    if len(spans) < 3:
        return
    fm_floor = 0.0
    arm = me.arm
    fmesh = T.FootMesh(me)

    def hips():
        return T.bone_world(me, 'hips')

    def chair_checks(tag, cmd, span, high=False):
        a, b = span
        down = int(round(cmd.span * fps))
        fm = min(b - 5, a + down + 20)
        sc.frame_set(fm)
        hp = hips()
        # a seated loop that leans into the chair's back sits forward of it by what its back needed (push_then)
        tgt = cmd.target + cmd.fwd * getattr(cmd, 'push_then', 0.0)
        d = math.hypot(hp.x - tgt.x, hp.y - tgt.y)
        R.check(f'{tag}: the hips come to rest on the seat\'s target (within 4 cm)', d < 0.04,
                f'{d * 100:.1f} cm from ({tgt.x:.3f}, {tgt.y:.3f}) at f{fm} (the back took the target '
                f'{getattr(cmd, "push", 0.0) * 100:.1f} cm forward, the seated loop '
                f'{getattr(cmd, "push_then", 0.0) * 100:.1f} cm more)')
        und = skin_lowest(me, cmd.pan, cmd.seat_here - 0.25)
        gap = (und - cmd.seat_here) if und is not None else None
        R.check(f'{tag}: the seated skin rests on the pan (its underside within 1.5 cm of it)',
                gap is not None and abs(gap) < 0.015, 'no skin over the pan' if gap is None else
                f'{gap * 100:+.2f} cm at f{fm} (pan {cmd.seat_here:.3f} m)')
        worst = None
        for f in range(a + int(0.4 * down), a + down + 1, 2):
            sc.frame_set(f)
            u = skin_lowest(me, cmd.pan, cmd.seat_here - 0.25)
            if u is not None and (worst is None or u - cmd.seat_here < worst[0]):
                worst = (u - cmd.seat_here, f)
        R.check(f'{tag}: the clamp: no seated skin more than 1 cm under the pan through the descent',
                worst is None or worst[0] > -0.01, 'never over the pan' if worst is None else
                f'lowest {worst[0] * 100:+.2f} cm at f{worst[1]}')
        sc.frame_set(fm)
        dy = T.ang_deg(T.yaw_of(me), cmd.th)
        R.check(f'{tag}: she sits facing out of the chair (within 6 deg of its facing)', dy < 6.0,
                f'{dy:.1f} deg off ({math.degrees(cmd.th):.1f} deg)')
        m = fmesh.at(fm)
        detail = '; '.join(f"{s} pen {v['pen_mm']} mm into {deepest_solid(fmesh, v['P'])}, low "
                           f"{v['zmin'] * 1000:.1f} mm" for s, v in m.items())
        if high:
            # a seat higher than the clip's: the feet rest on the floor where they reach it, else hang just over it
            ok = all(v['pen_mm'] <= 10.0 and -0.01 < v['zmin'] - fm_floor < 0.04 for v in m.values())
            R.check(f'{tag}: the seated boots reach the floor or hang just over it (the visible mesh: under 10 mm '
                    'into anything, under 4 cm up)', ok, detail)
        else:
            ok = all(v['pen_mm'] <= 10.0 and v['zmin'] - fm_floor < 0.02 for v in m.values())
            R.check(f'{tag}: the seated boots stand on the floor (the visible mesh: under 10 mm in, within 2 cm of '
                    'it)', ok, detail)
        R.check(f'{tag}: eido_seated is keyed on while she sits', bool(arm.get('eido_seated')),
                f"{arm.get('eido_seated')} at f{fm}")
        # the whole sit, not one frame of it: walking in, sitting down, the loop, standing up
        deep, over = (0.0, None, ''), []
        for f in range(a, b + 1, 2):
            for s, v in fmesh.at(f).items():
                if v['pen_mm'] > deep[0]:
                    deep = (v['pen_mm'], (f, s), deepest_solid(fmesh, v['P']))
                if v['pen_mm'] > 10.0:
                    over.append((f, s))
        R.check(f'{tag}: the boots stay out of the chair and the floor through the whole sit (the visible mesh every '
                '2 frames: under 10 mm into anything)', deep[0] <= 10.0,
                f'deepest {deep[0]} mm at {deep[1]} into {deep[2]}; {len(over)} foot-frames over: {over[:8]}')
        sc.frame_set(fm)
        return fm

    fa = chair_checks('chair A', cmd_a, spans[0])
    fb = chair_checks('chair B (0.56 m, the seated loop)', cmd_b, spans[1], high=True)
    T.whole_seat_checks(R, me, 'chair A', cmd_a, spans[0], sc)
    T.whole_seat_checks(R, me, 'chair B', cmd_b, spans[1], sc)
    T.floor_checks(R, me, 'the ground sit', spans[2], sc)
    sc.frame_set(fa)
    # the seated exemption at work in the placement audit: the sitter overlaps her chair; the keyed eido_seated leaves
    # the pair alone exactly while she sits (forced off in the same frame, the audit names it)
    from eidoblend.placement import check_clipping
    sc.frame_set(fa)

    def pairs_with_chair():
        rep_ = check_clipping(sc)
        return [p_ for p_ in rep_ if {p_['ar'], p_['br']} & {arm} and
                ({p_['a'].name, p_['b'].name} & {o.name for o in chair_a.children_recursive})]
    seated_pairs = pairs_with_chair()
    arm['eido_seated'] = 0
    unflagged_pairs = pairs_with_chair()
    sc.frame_set(fa)
    R.check('the audits leave the seated body alone while it sits (check_clipping: no sitter-chair pair; with '
            'eido_seated forced off in the same frame, it names one)', not seated_pairs and bool(unflagged_pairs),
            f'{len(seated_pairs)} pair(s) seated, {len(unflagged_pairs)} unflagged')
    R['seat_a'] = {'target': tuple(round(v, 3) for v in cmd_a.target), 'settle_cm': round(cmd_a.settle * 100, 2),
                   'recentred_cm': round(cmd_a.dxy.length * 100, 2), 'spot': cmd_a.spot}
    R['seat_b'] = {'target': tuple(round(v, 3) for v in cmd_b.target), 'settle_cm': round(cmd_b.settle * 100, 2),
                   'settle_then_cm': round(getattr(cmd_b, 'settle_then', 0.0) * 100, 2),
                   'then_shift_cm': round(cmd_b.then_shift.length * 100, 1) if hasattr(cmd_b, 'then_shift') else None}
    # the seated loop's crossfade: the hips stay on the seat
    a, b = spans[1]
    down = int(round(cmd_b.span * fps))
    t0f = a + down
    prev, mv = None, 0.0
    for f in range(t0f - 2, t0f + int(cmd_b.then_fade * fps) + 4):
        sc.frame_set(f)
        hp = hips()
        if prev is not None:
            mv = max(mv, (hp - prev).length)
        prev = hp.copy()
    R.check('chair B: the hips stay on the seat through the seated loop\'s crossfade (under 1.5 cm a frame)',
            mv < 0.015, f'{mv * 1000:.1f} mm a frame at most')
    # every seat, sitting down and standing up: no pop (a spike in the hips' acceleration) and no planted sole sliding
    for tag, (a, b) in (('chair A', spans[0]), ('chair B', spans[1]), ('the ground', spans[2])):
        P_h, pop = [], (0.0, None)
        slide = (0.0, None)
        last = {}
        for f in range(a - 6, b + 16):
            sc.frame_set(f)
            P_h.append(hips().copy())
            if len(P_h) >= 3:
                acc = (P_h[-1] - 2 * P_h[-2] + P_h[-3]).length
                if acc > pop[0]:
                    pop = (acc, f - 1)
            if tag == 'the ground':
                continue
            for s, v in fmesh.at(f).items():
                # the same boot points (FootMesh keeps its vertices in order) in contact in this frame and the last:
                # how far they moved along the floor (a heel lifting off is not a slide)
                P = v['P']
                if s in last and last[s][0] == f - 1 and last[s][1].shape == P.shape:
                    Pp = last[s][1]
                    both = (Pp[:, 2] < fm_floor + 0.004) & (P[:, 2] < fm_floor + 0.004)
                    if both.sum() >= 4:
                        mv = float(np.linalg.norm(P[both, :2] - Pp[both, :2], axis=1).max())
                        if mv > slide[0]:
                            slide = (mv, (f, s))
                last[s] = (f, P.copy())
        R.check(f'{tag}: no pop sitting down or standing up (the hips\' acceleration under 1 cm a frame squared)',
                pop[0] < 0.01, f'{pop[0] * 1000:.1f} mm at f{pop[1]}')
        if tag != 'the ground':
            R.check(f'{tag}: no planted sole slides through the sit (under 6 mm a frame where it rests on the floor)',
                    slide[0] < 0.006, f'{slide[0] * 1000:.1f} mm at {slide[1]}')
    # the ground sit
    a, b = spans[2]
    fg = a + int(cmd_g.fade * fps) + 20
    sc.frame_set(fg)
    from eidoblend.characters.emotes.verbs import _body_lowest, _lowest_near, skin_points
    hp = hips()
    pts = [(hp.x + i * 0.175, hp.y + j * 0.175) for i in range(-2, 3) for j in range(-2, 3)]
    grid = _body_lowest(me, pts, -0.6)
    low = _lowest_near(skin_points(me, loose=False), (hp.x, hp.y))
    R.check('the ground sit rests on the floor (the lowest of the skin near the hips, its coat left out, within '
            '-1 / +2 cm of it)', low is not None and -0.01 <= low - fm_floor <= 0.02,
            f'{(low or 0) * 100:+.2f} cm at f{fg} (the engine\'s grid of up-rays reads {(grid or 0) * 100:+.2f} cm)')
    R.check('the ground sit: eido_seated keyed on', bool(arm.get('eido_seated')), f"{arm.get('eido_seated')}")
    p = cam.matrix_world.translation
    want = math.atan2(p.x - hp.x, -(p.y - hp.y))
    R.check('the ground sit faces the camera (within 10 deg)', T.ang_deg(T.yaw_of(me), want) < 10.0,
            f'{T.ang_deg(T.yaw_of(me), want):.1f} deg')
    # face_camera and the salute toward it
    sal = [r['f'] for r in recs if r['weights'].get('salute', 0) > 0.9]
    if sal:
        fs = sal[len(sal) // 2]
        sc.frame_set(fs)
        hp = hips()
        want = math.atan2(p.x - hp.x, -(p.y - hp.y))
        R.check('face_camera, then the salute toward the camera (within 8 deg)', T.ang_deg(T.yaw_of(me), want) < 8.0,
                f'{T.ang_deg(T.yaw_of(me), want):.1f} deg at f{fs}')
    else:
        R.check('the salute plays', False, 'no salute frames')
    walk = next((r['f'] for r in recs if r['mode'] == 'loco' and r['speed'] > 0.5), None)
    if walk:
        sc.frame_set(walk)
        R.check('eido_seated is off while she walks', not arm.get('eido_seated'), f"{arm.get('eido_seated')} at f{walk}")
    T.gait_checks(R, rep)
    T.keyed_matches(R, me, frames)
    if T.arg(ARGS, '--trace'):
        rmode = {r['f']: (r['mode'], r['lead']) for r in recs}
        for rg in T.arg(ARGS, '--trace').split(','):
            a, b = (int(v) for v in rg.split('-'))
            for f in range(a, b + 1):
                sc.frame_set(f)
                hp = hips()
                la, ra = T.bone_world(me, 'leftFoot'), T.bone_world(me, 'rightFoot')
                lk, rk = T.bone_world(me, 'leftLowerLeg'), T.bone_world(me, 'rightLowerLeg')
                print(f'TRACE f{f} {rmode.get(f)} hips ({hp.x:.3f},{hp.y:.3f},{hp.z:.3f}) L ({la.x:.3f},{la.y:.3f},'
                      f'{la.z:.3f}) R ({ra.x:.3f},{ra.y:.3f},{ra.z:.3f}) knees {lk.z:.3f} {rk.z:.3f}', flush=True)
        R.log(f"knee floors: A {cmd_a.knee_floor}, B {cmd_b.knee_floor}")
    shots(sc, me, recs, spans, cmd_a, cmd_b, cmd_g, fa, fb, fg, sal)


def shots(sc, me, recs, spans, cmd_a, cmd_b, cmd_g, fa, fb, fg, sal):
    T.light(sc)
    S, sheets = [], {}
    fps = 30.0
    for tag, cmd, (a, b) in (('a', cmd_a, spans[0]), ('b', cmd_b, spans[1])):
        lo, hi = a - 45, b + 25
        T.strip(S, sheets, me, recs, f'seat_{tag}', [int(lo + (hi - lo) * k / 9) for k in range(10)], dist=3.6)
        # the contact: from the chair's side, low
        th = cmd.th
        side = Vector((math.cos(th), math.sin(th), 0.0))
        tgt = Vector((cmd.seat['x'], cmd.seat['y'], cmd.seat['z'] + 0.05))
        pos = tgt + side * 1.6 + Vector((0.0, 0.0, 0.1))
        S.append(T.fixed_shot(f'close_seat_{tag}', fa if tag == 'a' else fb, pos, tgt, lens=40))
        fwd = Vector((math.sin(th), -math.cos(th), 0.0))
        pos2 = tgt + fwd * 2.2 + side * 0.9 + Vector((0.0, 0.0, 0.6))
        S.append(T.fixed_shot(f'front_seat_{tag}', fa if tag == 'a' else fb, pos2, tgt + Vector((0, 0, 0.3)), lens=35))
    a, b = spans[2]
    gx, gy = cmd_g.xy
    T.strip(S, sheets, me, recs, 'ground', [int(a - 30 + (b + 40 - a + 30) * k / 7) for k in range(8)],
            at=((gx + 3.0, gy - 1.6, 1.05), (gx, gy, 0.6)), lens=30)        # standing and sitting both in frame
    S.append(T.fixed_shot('scene_cam_ground', fg, CAM[0], CAM[1], lens=40))
    if sal:
        S.append(T.fixed_shot('scene_cam_salute', sal[len(sal) // 2], CAM[0], CAM[1], lens=40))
    S.append(T.fixed_shot('wide', (spans[1][0] + spans[1][1]) // 2, (6.5, -4.5, 3.2), (0.0, 2.5, 0.5), lens=28))
    for s in S:
        s['action'] = f'{me.name}|controller'
    S2, sheets2 = options_take(sc, me)
    sheets.update(sheets2)
    T.save(R, sc, S + S2, sheets)


def options_take(sc, me):
    """the second take, on the same body (its own action): seat_on's options and the verbs' rarer paths:
    a backless stool (no facing of its own: face= given), the engine's fixed stand-off (hip_back=0.46: the arrival
    recentred), a longer settle (transition_dur), a pressed seat (sink=1 cm), no backing up, a slower walk; the seated
    loop 'sitting_normal_chair' and its pair 'sit_to_stand'; unseat while still seated; a chair sat facing its backrest
    on purpose (the engine's facing check must call it); the lying ground sit through the controller; face_camera
    toward a named camera"""
    stool = T.stool('stool', (5.6, -1.0), seat_h=0.62)
    chair_c = T.chair('chair_c', (8.6, 1.2), math.radians(90))
    cam2 = bpy.data.objects.new('cam_side', bpy.data.cameras.new('cam_side'))
    sc.collection.objects.link(cam2)
    cam2.location = (12.0, -4.0, 1.6)
    seats = [o for ch in (stool, chair_c) for o in ch.children_recursive] + \
        [o for o in sc.objects if o.name.startswith(('chair_a', 'chair_b'))]
    T.at_rest(me)                                  # the new controller measures the body at rest
    loco = Locomotion(me, CollisionWorld(exclude=seats), start=(4.0, -4.0, 0.0), heading=math.pi, log=R.log)
    from eidoblend.placement.seating import chair_facing
    face_back = chair_facing(chair_c) + math.pi                   # facing the backrest: the check must call it
    loco.wait(0.4)
    E.seat_on(loco, stool, face=math.radians(-90), hip_back=0.46, transition_dur=2.6, sink=0.01, back_up=0.0,
              speed=1.0, then='sitting_normal_chair', hold=1.5, stand={'clip': 'sit_to_stand'})
    cmd_s = loco._queue[-1]
    E.seat_on(loco, chair_c, face=face_back)
    cmd_c = loco._queue[-1]
    loco.wait(0.8)
    E.unseat(loco)
    loco.wait(0.8)
    E.stand_up(loco)
    E.sit_on_ground(loco, clip='sit_laying_on_ground', at=(10.0, 4.0), face=math.radians(180), fade=1.4, hold=1.5,
                    stand={'ground_fade': 1.6})
    E.face_camera(loco, camera=cam2)
    loco.wait(0.6)
    t0 = time.time()
    rep = E.bake(loco, f0=1, action_name=f'{me.name}|options')
    bpy.data.actions[f'{me.name}|options'].use_fake_user = True
    R['timing_s']['bake_options'] = round(time.time() - t0, 1)
    recs = rep['_records']
    spans = rep['seated']['spans']
    R['options_spans'] = spans
    R['options_facing_check'] = rep['seated']['facing']
    R.check('options: three seats (the stool, the chair, the lying ground sit)', len(spans) == 3, f'{spans}')
    if len(spans) < 3:
        return [], {}
    # the stool: face= taken (it has no facing), the engine's stand-off recentred, the hips on the target
    a, b = spans[0]
    fm = a + int(round(cmd_s.span * 30)) + 25
    sc.frame_set(fm)
    hp = T.bone_world(me, 'hips')
    R.check('options: the stool (no backrest): she sits facing face= (within 3 deg)',
            T.ang_deg(T.yaw_of(me), math.radians(-90)) < 3.0, f'{T.ang_deg(T.yaw_of(me), math.radians(-90)):.1f} deg')
    R.check('options: the stool: hip_back=0.46 stands her off the spot the clip needs and the hips are recentred '
            'onto the target (within 3 cm)', math.hypot(hp.x - cmd_s.target.x, hp.y - cmd_s.target.y) < 0.03,
            f'recentred {cmd_s.dxy.length * 100:.1f} cm; the hips {math.hypot(hp.x - cmd_s.target.x, hp.y - cmd_s.target.y) * 100:.1f} cm off')
    und = skin_lowest(me, cmd_s.pan, cmd_s.seat_here - 0.25)
    R.check('options: the stool: the skin pressed 1 cm into the pad (sink=0.01; within 1.5 cm of -1 cm)',
            und is not None and abs((und - cmd_s.seat_here) + 0.01) < 0.015,
            f'{(und - cmd_s.seat_here) * 100:+.2f} cm' if und is not None else 'none')
    R.check('options: transition_dur=2.6 sets the settle\'s span (the clip plays its own 2.21 s)',
            abs(cmd_s.span - 2.6) < 1e-6 and abs(cmd_s.clip_dur - 2.21) < 0.02, f'{cmd_s.span}, {cmd_s.clip_dur:.2f}')
    T.whole_seat_checks(R, me, 'options: the stool', cmd_s, spans[0], sc)
    T.floor_checks(R, me, "options: 'sit_laying_on_ground'", spans[2], sc)
    # the loop and its pair: no pop, no slide through the stand-up
    P_h, pop = [], (0.0, None)
    for f in range(a, b + 15):
        sc.frame_set(f)
        P_h.append(T.bone_world(me, 'hips').copy())
        if len(P_h) >= 3:
            acc = (P_h[-1] - 2 * P_h[-2] + P_h[-3]).length
            if acc > pop[0]:
                pop = (acc, f - 1)
    R.check("options: 'sitting_normal_chair' then 'sit_to_stand' (its pair): no pop (the hips' acceleration under "
            '1 cm a frame squared)', pop[0] < 0.01, f'{pop[0] * 1000:.1f} mm at f{pop[1]}')
    # the chair sat facing its backrest: the engine's deferred facing check calls it
    fc = [x for x in rep['seated']['facing'] if x['chair'] == 'chair_c']
    R.check('options: a sitter facing the backrest is called by the facing check (over 110 deg: RE-RENDER REQUIRED)',
            bool(fc) and fc[0]['deg'] > 110, f'{fc}')
    # unseat while still seated: the exemption ends there, before she stands
    a2, b2 = spans[1]
    t_un = getattr(loco, '_unseat_times', [None])[0]
    seated_after = [r['f'] for r in recs if r['mode'] in ('seated', 'seat') and t_un is not None and r['t'] > t_un + 0.1]
    if seated_after:
        sc.frame_set(seated_after[0] + 2)
        R.check('options: unseat ends the audits\' exemption while she still sits', not me.arm.get('eido_seated'),
                f"eido_seated {me.arm.get('eido_seated')} at f{seated_after[0] + 2}; the span keyed {spans[1]}")
    else:
        R.check('options: unseat ends the audits\' exemption while she still sits', False, 'no seated frame after it')
    # the lying ground sit through the controller
    a3, b3 = spans[2]
    fg = a3 + 60
    sc.frame_set(fg)
    from eidoblend.characters.emotes.verbs import _body_lowest, _lowest_near, skin_points
    hp = T.bone_world(me, 'hips')
    grid = _body_lowest(me, [(hp.x + i * 0.175, hp.y + j * 0.175) for i in range(-2, 3) for j in range(-2, 3)], -0.6)
    low = _lowest_near(skin_points(me, loose=False), (hp.x, hp.y))
    R.check("options: 'sit_laying_on_ground' through the controller rests on the floor (the lowest of the skin near "
            "the hips within -1 / +2 cm)", low is not None and -0.01 <= low <= 0.02,
            (f'{low * 100:+.2f} cm' if low is not None else 'none') +
            (f" (the engine's grid of up-rays reads {grid * 100:+.2f} cm)" if grid is not None else ''))
    # face_camera toward a named camera
    sc.frame_set(recs[-1]['f'])
    p = cam2.matrix_world.translation
    want = math.atan2(p.x - hp.x, -(p.y - hp.y))
    end_feet = Vector(recs[-1]['feet_world'])
    want = math.atan2(p.x - end_feet.x, -(p.y - end_feet.y))
    R.check('options: face_camera(camera=cam_side) turns her to that camera (within 4 deg)',
            T.ang_deg(T.yaw_of(me), want) < 4.0, f'{T.ang_deg(T.yaw_of(me), want):.1f} deg')
    T.gait_checks(R, rep)
    T.keyed_matches(R, me, rep['_frames'])
    S, sheets = [], {}
    T.strip(S, sheets, me, recs, 'opt_stool', [int(a - 30 + (b + 30 - a + 30) * k / 9) for k in range(10)], dist=3.4)
    T.strip(S, sheets, me, recs, 'opt_backwards', [int(a2 - 10 + (b2 + 20 - a2 + 10) * k / 7) for k in range(8)],
            dist=3.4)
    T.strip(S, sheets, me, recs, 'opt_lying', [int(a3 - 20 + (b3 + 30 - a3 + 20) * k / 7) for k in range(8)],
            at=((10.0 + 3.2, 4.0 - 2.0, 1.1), (10.0, 4.0, 0.5)), lens=28)
    for s in S:
        s['action'] = f'{me.name}|options'
    return S, sheets


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
