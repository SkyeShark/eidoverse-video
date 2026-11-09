"""examples/obstacle_course.js's sit stop through eidoblend.characters.emotes, on the example's own character:

    test_example_bench.py [--vrm aporia] [--tag NAME]

The example puts a bench on the course line (a plain 1.1 x 0.5 m box, 0.45 m high: no backrest), routes the walk
round it, squares up to the course heading, calls seatOn(vrm, bench, {transition: 'stand_to_sit', faceY: Math.PI})
through the controller (globalThis._vrmControllers: the cohesive path), holds 2.2 s, stands up with
endSeated(null, {reverse: true, reverseSpeed: 1.25}), stopEmote, walks on, and cheers over the walk (playGesture('cheer',
{weight: 2.75})). Here: seat_on(walk, bench, face=pi) (three's rotation.y = pi faces +Y in Blender), the course along +Y.

Prints PASS / FAIL: one seat; she faces the course (face=); the hips on the seat's target; the seat skin on the bench
through the whole seat (the descent, the hold, the reversed stand-up); nothing of the body in the bench; the boots out of
it; no pop; eido_seated keyed over the seat; the cheer over the walk after it; checks.feet; the keyed armature against
the bake. Stills: a strip of the sit from the side, a three-quarter view seated, the cheer.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _mnv_stage as T  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.characters import emotes as E  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aporia')
R = T.Report(T.arg(ARGS, '--tag', f'example_bench_{VRM}'))
R['vrm'] = VRM
BENCH_Y = 4.0


def main():
    sc = T.S.clean_scene(fps=30)
    T.floor()
    # the example's bench: BoxGeometry(1.1, 0.45, 0.5) at (0, 0.225, benchZ), three -> Blender (x, -z, y)
    bench = T.box('bench', (0.0, BENCH_Y, 0.225), (1.1, 0.5, 0.45), 'chair', role='bench')
    cam = T.scene_camera((3.2, BENCH_Y + 2.6, 1.5), (0.0, BENCH_Y, 0.6))
    me = load_vrm(VRM, name=VRM)
    loco = Locomotion(me, CollisionWorld(exclude=[bench]), start=(0.0, 0.0, 0.0), heading=math.pi, log=R.log)
    loco.wait(0.4)
    E.seat_on(loco, bench, face=math.pi, hold=2.2, stand={'reverse': True, 'reverse_speed': 1.25})
    cmd = loco._queue[-1]
    loco.gesture('cheer', weight=2.75)
    loco.follow_path([(0.0, BENCH_Y + 4.5)], gait='walk')
    loco.stop_gesture()
    loco.wait(0.4)
    t0 = time.time()
    rep = E.bake(loco, f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs = rep['_records']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    spans = rep['seated']['spans']
    R['seated_spans'] = spans
    R['segments'] = rep['segments']
    R.check('one seat in the take (the bench)', len(spans) == 1, f'{spans}')
    if not spans:
        return
    a, b = spans[0]
    fm = a + int(round(cmd.span * 30)) + 20
    sc.frame_set(fm)
    R.check('she sits facing the course (face=pi, the example\'s faceY: within 3 deg)',
            T.ang_deg(T.yaw_of(me), math.pi) < 3.0, f'{T.ang_deg(T.yaw_of(me), math.pi):.1f} deg')
    hp = T.bone_world(me, 'hips')
    d = math.hypot(hp.x - cmd.target.x, hp.y - cmd.target.y)
    R.check('the hips come to rest on the seat\'s target (within 4 cm)', d < 0.04,
            f'{d * 100:.1f} cm from ({cmd.target.x:.3f}, {cmd.target.y:.3f}) at f{fm}')
    from eidoblend.characters.emotes.verbs import skin_lowest
    und = skin_lowest(me, cmd.pan, cmd.seat_here - 0.25)
    R.check('the seated skin rests on the bench (within 1.5 cm of its top)', und is not None and
            abs(und - cmd.seat_here) < 0.015, f'{(und - cmd.seat_here) * 100:+.2f} cm' if und is not None else 'none')
    R.check('eido_seated is keyed on while she sits', bool(me.arm.get('eido_seated')), f"{me.arm.get('eido_seated')}")
    T.whole_seat_checks(R, me, 'the bench', cmd, spans[0], sc)
    fmesh = T.FootMesh(me)
    deep = (0.0, None)
    for f in range(a, b + 1, 2):
        for s, v in fmesh.at(f).items():
            if v['pen_mm'] > deep[0]:
                deep = (v['pen_mm'], (f, s))
    R.check('the boots stay out of the bench and the floor through the whole sit (under 10 mm)', deep[0] <= 10.0,
            f'deepest {deep[0]} mm at {deep[1]}')
    P_h, pop = [], (0.0, None)
    for f in range(a - 6, b + 16):
        sc.frame_set(f)
        P_h.append(T.bone_world(me, 'hips').copy())
        if len(P_h) >= 3:
            acc = (P_h[-1] - 2 * P_h[-2] + P_h[-3]).length
            if acc > pop[0]:
                pop = (acc, f - 1)
    R.check('no pop sitting down or standing up (the hips\' acceleration under 1 cm a frame squared)', pop[0] < 0.01,
            f'{pop[0] * 1000:.1f} mm at f{pop[1]}')
    ws = [r['weights'].get('cheer', 0.0) for r in recs if r['mode'] == 'loco' and r['lead'] == 'walk']
    R.check("the example's cheer rides over the walk after the seat (its weight reaches 2.5)",
            bool(ws) and max(ws) >= 2.5, f'max {max(ws) if ws else 0:.2f}')
    T.gait_checks(R, rep)
    T.keyed_matches(R, me, rep['_frames'])
    # stills
    T.light(sc)
    S, sheets = [], {}
    T.strip(S, sheets, me, recs, 'bench', [int(a - 50 + (b + 30 - a + 50) * k / 9) for k in range(10)], dist=3.6,
            at=((3.6, BENCH_Y + 0.4, 0.95), (0.0, BENCH_Y + 0.4, 0.75)), lens=30)
    S.append(T.fixed_shot('bench_seated', fm, (1.6, BENCH_Y + 1.7, 1.0), (0.0, BENCH_Y + 0.15, 0.55), lens=35))
    S.append(T.fixed_shot('bench_low', fm, (1.3, BENCH_Y - 0.2, 0.35), (0.0, BENCH_Y + 0.1, 0.4), lens=30))
    cheer = [r['f'] for r in recs if r['weights'].get('cheer', 0.0) > 2.0]
    if cheer:
        S.append(T.fixed_shot('cheer', cheer[len(cheer) // 2], tuple(cam.location), (0.0, BENCH_Y + 2.0, 0.9), lens=30))
    for s in S:
        s['action'] = f'{me.name}|controller'
    sheets['sheet'] = [s['name'] for s in S if not s['name'].startswith('strip_')]
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
