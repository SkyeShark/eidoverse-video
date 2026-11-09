"""scene_placement.js's emote and faceCamera, and the stationary seatOn / sitOnGround / unseat, through
eidoblend.characters.emotes on both of its paths:

    test_emotes.py [--vrm aletheia] [--tag NAME]

    the controller path   one Locomotion take on `vrm`: every expressive clip of the library (talk, salute, cheer, fist,
                          raise, reach, crazy, dance) played from standing (playEmote: the walk suspended), facing the
                          camera (facing='camera'), its own heading kept ('keep') or a heading (degrees), a turn on the
                          spot to the camera between (face_camera), each held then stopped (stopEmote)
    the stationary path   three more VRMs nothing drives: seat_on in a chair with the fidget clip
                          ('sitting_nervous_arm_rub_chair': the instant path), sit_on_ground lying
                          ('sit_laying_on_ground'), emote('dance') turned three-quarters to the camera (face_camera
                          offset 0.4); unseat clearing the audits' exemption

Prints PASS / FAIL: each emote reaches full weight; the facing it was given (within 3 deg); no planted boot sliding
(FootMesh: the same contact points frame to frame) and no pop as it comes and goes (the hips' acceleration); the
stationary seat on its pan and facing out of its chair, the lying body on the floor, the three-quarter turn; eido_seated
set by the stationary seats and cleared by unseat; checks.feet on the take; the keyed armature against the bake. Stills:
each emote at its height from the scene camera, the stationary three.
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

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'emotes_{VRM}'))
R['vrm'] = VRM
CAM = ((0.0, -6.5, 1.5), (0.0, 0.0, 0.9))
# (slot, seconds, facing): facing 'camera', 'keep', or a heading in degrees
PLAN = [('talk', 3.0, 'camera'), ('salute', None, 'camera'), ('cheer', None, 'keep'), ('fist', None, 30.0),
        ('raise', 3.0, 'camera'), ('reach', 3.0, 'keep'), ('crazy', 3.0, 'camera'), ('dance', 4.0, 'camera')]


def heading_to(p, q):
    return math.atan2(q.x - p.x, -(q.y - p.y))


def clip_accel(me, slot, fps=30.0):
    """the clip's own hips acceleration at the scene's rate (its hips track's second difference, m a frame squared):
    what a pop is measured against (a frantic dance moves its hips that fast by itself)"""
    from eidoblend.characters.controller import clips as C
    cc = C.load_emote_clip(me, slot, loop=False)
    t = np.arange(0.0, cc.duration, 1.0 / fps)
    k = np.arange(cc.n + 1) * cc.dt
    P = np.stack([np.interp(t, k, cc.root_curve[:, j]) for j in range(3)], axis=1)
    if len(P) < 3:
        return 0.0
    return float(np.linalg.norm(P[2:] - 2 * P[1:-1] + P[:-2], axis=1).max())


def main():
    sc = T.S.clean_scene(fps=30)
    T.floor()
    chair = T.chair('chair_c', (3.2, 1.0), math.radians(-150))
    cam = T.scene_camera(*CAM)
    me = load_vrm(VRM, name=VRM)
    # ---- the controller path
    loco = Locomotion(me, CollisionWorld(exclude=list(chair.children_recursive)), start=(0.0, 0.0, 0.0),
                      heading=math.radians(40.0), log=R.log)
    loco.wait(0.5)
    spans = {}
    for slot, sec, facing in PLAN:
        if facing == 'camera':
            E.face_camera(loco)
        E.emote(loco, slot, seconds=sec, facing=facing)
        loco.wait(0.5)
    t0 = time.time()
    rep = E.bake(loco, f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs = rep['_records']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    R['segments'] = rep['segments']
    fm = T.FootMesh(me)
    camp = cam.matrix_world.translation
    for slot, sec, facing in PLAN:
        fs = [r['f'] for r in recs if r['weights'].get(slot, 0.0) > 0.05]
        if not fs:
            R.check(f"'{slot}' plays", False, 'never weighted')
            continue
        a, b = fs[0], fs[-1]
        spans[slot] = (a, b)
        top = max(r['weights'].get(slot, 0.0) for r in recs)
        R.check(f"'{slot}' plays at full weight ({b - a + 1} frames)", top > 0.95, f'max {top:.2f}')
        mid = [r for r in recs if r['f'] == (a + b) // 2][0]
        sc.frame_set(mid['f'])
        yaw = T.yaw_of(me)
        if facing == 'camera':
            want = heading_to(Vector(mid['feet_world']), camp)
        elif facing == 'keep':
            prev = [r for r in recs if r['f'] == a - 1]
            want = prev[0]['heading'] if prev else yaw
        else:
            want = math.radians(facing)
        R.check(f"'{slot}' faces {facing if isinstance(facing, str) else f'{facing:g} deg'} (within 3 deg)",
                T.ang_deg(yaw, want) < 3.0, f'{T.ang_deg(yaw, want):.1f} deg off')
        # the boots planted through it, and no pop as it comes and goes
        last, slide = {}, (0.0, None)
        P_h, pop = [], (0.0, None)
        for f in range(max(f0, a - 4), min(f1, b + 12)):
            sc.frame_set(f)
            P_h.append(T.bone_world(me, 'hips').copy())
            if len(P_h) >= 3:
                acc = (P_h[-1] - 2 * P_h[-2] + P_h[-3]).length
                if acc > pop[0]:
                    pop = (acc, f - 1)
            for s, v in fm.at(f).items():
                P = v['P']
                if s in last and last[s][0] == f - 1 and last[s][1].shape == P.shape:
                    Pp = last[s][1]
                    both = (Pp[:, 2] < 0.004) & (P[:, 2] < 0.004)
                    if both.sum() >= 4:
                        mv = float(np.linalg.norm(P[both, :2] - Pp[both, :2], axis=1).max())
                        if mv > slide[0]:
                            slide = (mv, (f, s))
                last[s] = (f, P.copy())
        R.check(f"'{slot}': no planted boot slides (under 6 mm a frame)", slide[0] < 0.006,
                f'{slide[0] * 1000:.1f} mm at {slide[1]}')
        own = clip_accel(me, slot)
        lim = max(0.015, 1.25 * own)
        R.check(f"'{slot}': no pop coming in or going out (the hips' acceleration under 1.5 cm a frame squared, or "
                "under 1.25 x the clip's own)", pop[0] < lim,
                f'{pop[0] * 1000:.1f} mm at f{pop[1]}; the clip alone {own * 1000:.1f} mm')
    T.gait_checks(R, rep)
    T.keyed_matches(R, me, rep['_frames'])
    # ---- the stationary path: nothing drives these
    seat = load_vrm(VRM, name=VRM + '_seat')
    z_seat = E.seat_on(seat, chair, clip='sitting_nervous_arm_rub_chair')
    from eidoblend.characters.emotes.verbs import pan_points, skin_lowest
    from eidoblend.placement.seating import chair_facing, find_seat_surface
    pan = find_seat_surface(chair)
    sc.frame_set(60)
    und = skin_lowest(seat, pan_points(chair, pan), pan['z'] - 0.25)
    R.check('stationary seat_on (the instant path, the fidget clip): the underside on the pan (within 2.5 cm)',
            und is not None and abs(und - pan['z']) < 0.025, f'{(und - pan["z"]) * 100:+.2f} cm' if und else 'none')
    R.check('stationary seat_on: she faces out of the chair (within 3 deg)',
            T.ang_deg(T.yaw_of(seat), chair_facing(chair, pan)) < 3.0,
            f'{T.ang_deg(T.yaw_of(seat), chair_facing(chair, pan)):.1f} deg')
    flag_on = bool(seat.arm.get('eido_seated'))
    E.unseat(seat)
    flag_off = not seat.arm.get('eido_seated')
    seat.arm['eido_seated'] = True                     # seated again for the render's audits
    R.check('stationary: seat_on sets the audits\' exemption, unseat clears it', flag_on and flag_off,
            f'set {flag_on}, cleared {flag_off}; the seat at {z_seat:.3f} m')
    ground = load_vrm('claude_robot', name='robot_ground')
    fz = E.sit_on_ground(ground, clip='sit_laying_on_ground', at=(-2.6, 1.4), face=math.radians(-20))
    sc.frame_set(60)
    from eidoblend.characters.emotes.verbs import _body_lowest
    hp = T.bone_world(ground, 'hips')
    low = _body_lowest(ground, [(hp.x + i * 0.175, hp.y + j * 0.175) for i in range(-2, 3) for j in range(-2, 3)],
                       fz - 0.6)
    R.check('stationary sit_on_ground (lying): the lowest of the body rests on the floor (within -1 / +2 cm)',
            low is not None and -0.01 <= low - fz <= 0.02, f'{(low - fz) * 100:+.2f} cm' if low else 'none')
    dancer = load_vrm('claude_robot', name='robot_dance')
    dancer.arm.location = (-1.6, -1.2, 0.0)
    E.emote(dancer, 'dance')
    th = E.face_camera(dancer, offset=0.4)
    want = heading_to(dancer.arm.matrix_world.translation, camp) + 0.4
    R.check('stationary emote(dance) and face_camera(offset=0.4): a three-quarter turn from the lens',
            T.ang_deg(T.yaw_of(dancer), want) < 1.0, f'{T.ang_deg(T.yaw_of(dancer), want):.2f} deg; {math.degrees(th):.1f}')
    shots(sc, me, recs, spans)


def shots(sc, me, recs, spans):
    T.light(sc)
    S, sheets = [], {'emotes': []}
    for slot, (a, b) in spans.items():
        f = a + int(0.55 * (b - a))
        S.append(T.fixed_shot(f'emote_{slot}', f, CAM[0], CAM[1], lens=35))
        sheets['emotes'].append(f'emote_{slot}')
    S.append(T.fixed_shot('stationary', 60, (0.5, -6.0, 2.2), (0.6, 0.6, 0.6), lens=24))
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
