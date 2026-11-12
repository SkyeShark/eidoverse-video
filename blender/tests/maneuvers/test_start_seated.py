"""seatOn's instant path for a walking body (emotes.seat_on(walk, chair, instant=True)): a take that opens seated, and
a cut into a second chair later in it, each in a seated loop at once, then a stand-up and a walk:

    test_start_seated.py [--vrm aletheia] [--tag NAME] [--no-render]

One take on a floor with two chairs (as test_seating.py builds them): the take opens seated on chair A in the default
seated loop (sitting_normal_chair), holds, stands up (sit_to_stand) and walks off; later the body is put on chair B
(0.56 m) at once in 'sitting_nervous_arm_rub_chair', holds 1.5 s, stands up and walks.

Prints PASS / FAIL for each seat: its first frame is seated (keyed eido_seated, the take's frames kept by the seat),
no descent (the hips hold their height over its first second), the hips on the seat's target, the seated skin on the
pan, facing out of the chair, the boots on (chair A) or over (chair B) the floor, the whole seat checks (the stage's:
the skin on the pan, nothing in the chair's back or out behind it, the body out of the pan and the legs); the springs
start over where the take jumps into chair B; checks.feet on every walk after them; the keyed armature matches the
bake. Stills (render_shots.py): the opening frame and the stand-up of chair A from a low side camera, the cut into
chair B.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _mnv_stage as T  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.characters import emotes as E  # noqa: E402
from eidoblend.characters.emotes.verbs import skin_lowest  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'start_seated_{VRM}'))
R['vrm'] = VRM
FPS = 30


def main():
    sc = T.S.clean_scene(fps=FPS)
    T.floor()
    chair_a = T.chair('chair_a', (1.4, 1.6), math.radians(-110))
    chair_b = T.chair('chair_b', (-1.6, 4.4), math.radians(160), seat_h=0.56, back_h=1.02)
    T.scene_camera((5.5, -2.0, 1.7), (0.0, 3.0, 0.7))
    me = load_vrm(VRM, name=VRM)
    seats = [o for ch in (chair_a, chair_b) for o in ch.children_recursive]
    loco = Locomotion(me, CollisionWorld(exclude=seats), start=(0.0, -3.0, 0.0), heading=math.pi, log=R.log)
    E.seat_on(loco, chair_a, instant=True)
    cmd_a = loco._queue[-1]
    loco.wait(1.5)
    E.stand_up(loco)
    loco.move_to((0.5, -1.0))
    loco.wait(0.5)
    E.seat_on(loco, chair_b, instant=True, then='sitting_nervous_arm_rub_chair', hold=1.5)
    cmd_b = loco._queue[-1]
    loco.move_to((0.0, 2.0))
    loco.wait(0.5)
    t0 = time.time()
    rep = E.bake(loco, f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    spans = rep['seated']['spans']
    R['seated_spans'] = spans
    R['segments'] = [(s['gait'], s['frames']) for s in rep['segments']]
    R.check('two seats in the take', len(spans) == 2, f'{spans}')
    if len(spans) < 2:
        return
    R.check('the take opens seated on chair A (its first frame keyed seated)', spans[0][0] == f0,
            f'the seat from f{spans[0][0]}, the take from f{f0}')
    arm = me.arm
    fmesh = T.FootMesh(me)

    def seat_checks(tag, cmd, span, high=False):
        a, b = span
        sc.frame_set(a)
        R.check(f'{tag}: eido_seated is keyed on from its first frame', bool(arm.get('eido_seated')),
                f"{arm.get('eido_seated')} at f{a}")
        zs = []
        for f in range(a, min(b, a + FPS) + 1):
            sc.frame_set(f)
            zs.append(T.bone_world(me, 'hips').z)
        R.check(f'{tag}: no descent: the hips hold their height over the first second', max(zs) - min(zs) < 0.01,
                f'{(max(zs) - min(zs)) * 100:.2f} cm')
        sc.frame_set(a)
        hp = T.bone_world(me, 'hips')
        tgt = cmd.target + cmd.fwd * getattr(cmd, 'push_then', 0.0)
        d = math.hypot(hp.x - tgt.x, hp.y - tgt.y)
        R.check(f"{tag}: the hips rest on the seat's target (within 4 cm)", d < 0.04, f'{d * 100:.1f} cm at f{a}')
        und = skin_lowest(me, cmd.pan, cmd.seat_here - 0.25)
        gap = (und - cmd.seat_here) if und is not None else None
        R.check(f'{tag}: the seated skin rests on the pan (its underside within 1.5 cm of it)',
                gap is not None and abs(gap) < 0.015, 'no skin over the pan' if gap is None else
                f'{gap * 100:+.2f} cm at f{a}')
        dy = T.ang_deg(T.yaw_of(me), cmd.th)
        R.check(f'{tag}: she sits facing out of the chair (within 6 deg)', dy < 6.0, f'{dy:.1f} deg off')
        m = fmesh.at(a)
        lows = '; '.join(f"{s} low {v['zmin'] * 1000:.1f} mm, {v['pen_mm']} mm in" for s, v in m.items())
        if high:
            ok = all(v['pen_mm'] <= 10.0 and -0.01 < v['zmin'] < 0.04 for v in m.values())
            R.check(f'{tag}: the seated boots reach the floor or hang just over it', ok, lows)
        else:
            ok = all(v['pen_mm'] <= 10.0 and v['zmin'] < 0.02 for v in m.values())
            R.check(f'{tag}: the seated boots stand on the floor', ok, lows)
        T.whole_seat_checks(R, me, tag, cmd, span, sc)

    seat_checks('chair A (the take opens seated)', cmd_a, spans[0])
    seat_checks('chair B (a cut into it, 0.56 m)', cmd_b, spans[1], high=True)
    sp = rep.get('springs')
    if sp is not None:
        R.check('the springs start over where the take cuts into chair B', spans[1][0] in sp['resets'],
                f"resets {sp['resets']}, chair B from f{spans[1][0]}")
    walks = [s for s in rep['segments'] if s['gait'] == 'walk' and s['frames'][0] > spans[0][1]]
    R.check('she walks off after each stand-up', len(walks) >= 2, f"{[s['frames'] for s in walks]}")
    T.gait_checks(R, rep)
    T.keyed_matches(R, me, frames)
    # stills
    T.light(sc)
    shots, sheets = [], {}
    T.strip(shots, sheets, me, recs, 'chair_a_open', [f0, f0 + 20, f0 + 44], dist=3.0, height=0.0)
    a_up = spans[0][1]
    T.strip(shots, sheets, me, recs, 'chair_a_up', list(range(a_up - 50, a_up + 25, 6)), dist=3.4, height=0.05)
    b0 = spans[1][0]
    T.strip(shots, sheets, me, recs, 'chair_b_cut', [b0 - 2, b0 - 1, b0, b0 + 12, b0 + 30], dist=3.6, height=0.1)
    T.save(R, sc, shots, sheets)


try:
    main()
except Exception as e:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, f'{type(e).__name__}: {e}')
R.finish()
