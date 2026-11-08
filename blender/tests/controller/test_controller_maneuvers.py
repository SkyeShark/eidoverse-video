"""examples/obstacle_course.js, the controller's full vocabulary on one course, directed as the WebGPU example directs it:

    test_controller_maneuvers.py [--vrm aletheia] [--tag NAME]

The course is the example's TERRAIN_CONFIG (eidoblend.course.EXAMPLES['obstacle_course']), the controller
terrain_base's (CONTROLLER_PRESETS['terrain_base']), and the example's renderFrame script becomes film commands:
    walk: the bump, 8 deg ramps, small stairs up and down, the low cover VAULT (auto), the 1.15 m wall MOUNT (auto),
          across its top and off its far edge (a fall, fallLand)
    run (segments 15 to 23): stairs up, the 1.1 m GAP JUMP (auto), stairs down, the chest-high cover VAULT (auto)
    walk: the 2.2 m wall CLIMB (auto: climbWallUp), its top and the drop (fallLand)
    the sit stop: auto maneuvers off near the bench, routed around it (the example's three waypoints), squared up to
          the course heading, seated (stand_to_sit), held, stood (the clip reversed at 1.25x), stopEmote
    a cheer gesture while walking (segment 27), stopped before the ladder
    the LADDER (explicit climbLadder, 2.5 m: the rung loop chained into the mantle over the top)
    the finale: walk to the platform's middle, salute facing the camera's side

Prints PASS / FAIL: every maneuver the example has played (vault x2, mount x2, the gap jump, the ladder and its mantle,
fallLand), the contact IK touching what it grabs (the vault's prop hand on the cover top, the hands on the lip
during the mounts, the hands on the rungs), checks.feet on the walking and running stretches, the sit, the gesture,
the salute, the finale on the top platform, the keyed armature against the bake.
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

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.course import EXAMPLES, add_bench  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'maneuvers_{VRM}'))
R['vrm'] = VRM
EX = EXAMPLES['obstacle_course']


def main():
    sc = T.S.clean_scene(fps=30)
    course = T.course(EX['config'], name='example')
    bench = add_bench(course, EX['bench'], material=T.course_materials()['bench'])
    seg = course.segment
    me = load_vrm(VRM, name=VRM)
    # terrain_base: "Rungs are visual; the flat face is the collider": the ladder's rails and rungs are not walked on
    fixtures = [o for o in course.objects if o.get('eido_course_role') in ('rail', 'rung')]
    world = CollisionWorld(exclude=fixtures)
    R['fixtures_excluded'] = len(fixtures)
    loco = Locomotion(me, world, start=course.start, heading=math.pi, preset='terrain_base', log=R.log)
    c = loco.ctrl
    z = EX['zones']
    run0, run1 = seg(z['run'][0])['y0'], seg(z['run'][1])['y1']
    by = (bench.location.y if bench is not None else (seg(z['sit'])['y0'] + seg(z['sit'])['y1']) / 2)
    sit_seg = seg(z['sit'])
    ges, lad, top = seg(z['gesture']), seg(z['ladder']), seg(z['finale'])
    R['zones'] = {'run': (run0, run1), 'bench_y': by, 'ladder_y0': lad['y0'], 'top': (top['y0'], top['y1'])}

    def auto(on):
        def f(ctl):
            ctl.auto_maneuvers = on
        return f
    loco.wait(0.6)
    loco.follow_path([(0.0, run0)], gait='walk', stop=False)
    loco.follow_path([(0.0, run1)], gait='run', stop=False)
    loco.follow_path([(0.0, sit_seg['y0'] - 1.2)], gait='walk', stop=False)
    loco.call(auto(False))                                       # the example: no maneuver near the bench
    route = [(x, by - z_) for x, z_ in EX['sit_route']]          # three (x, bz + dz) -> Blender (x, by - dz)
    loco.follow_path(route, gait='walk')
    loco.turn_to(180.0)                                          # square up to the course heading (three's pi)
    st = EX['sit_timing']
    loco.sit(hold=st['hold'], down=st['sit_down'], up=st['stand_up'], reverse=True, reverse_speed=st['reverse_speed'])
    loco.call(auto(True))
    loco.follow_path([(0.0, ges['y0'])], gait='walk', stop=False)
    loco.gesture(EX['gesture']['name'], weight=EX['gesture']['weight'])
    loco.follow_path([(0.0, ges['y1'] - EX['gesture']['stop_before_end'])], gait='walk', stop=False)
    loco.stop_gesture()
    # the example calls climbLadder 0.55 m from the face, but its auto-trigger (0.35 + 0.3 x speed ahead) reads the
    # 2.5 m ladder block as a wall to scramble before that: the trigger is off for the approach so the ladder plays
    loco.call(auto(False))
    loco.move_to((0.0, lad['y0'] - EX['ladder']['trigger']), gait='walk')
    loco.climb_ladder(height=EX['ladder']['height'])
    loco.call(auto(True))
    loco.move_to((0.0, (top['y0'] + top['y1']) / 2), gait='walk')
    loco.wait(EX['finale']['delay'])
    loco.emote(EX['finale']['emote'], fade_in=EX['finale']['fade_in'], facing=90.0)   # toward the side camera (+X)
    loco.wait(0.5)
    t0 = time.time()
    rep = loco.bake(f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    segs = rep['segments']
    R['segments'] = segs
    man = {}
    for r in recs:
        if r['mode'] == 'maneuver' and r['maneuver']:
            man.setdefault(r['maneuver'], []).append(r['f'])
    runs = {}
    for k, fs in man.items():
        runs[k] = [[fs[0], fs[0]]]
        for f in fs[1:]:
            if f == runs[k][-1][1] + 1:
                runs[k][-1][1] = f
            else:
                runs[k].append([f, f])
    R['maneuvers'] = runs
    R.log(f'maneuvers: {runs}')
    want = {'vault': 2, 'mount': 2, 'jump': 1, 'ladder': 1, 'land': 1}
    for k, n in want.items():
        got = len(runs.get(k, []))
        R.check(f'the example\'s {k} maneuver plays ({n} or more)', got >= n, f'{got}: {runs.get(k)}')
    R.check('the ladder chains into the mantle (a mount right after the ladder)', bool(runs.get('ladder')) and any(
        a == runs['ladder'][-1][1] + 1 for a, _b in runs.get('mount', [])), f'ladder {runs.get("ladder")}, mount '
        f'{runs.get("mount")}')
    # the contact IK: the hands where the grab puts them
    hand = {s: me.humanoid[s + 'Hand'] for s in ('left', 'right')}

    def hand_z(f):
        sc.frame_set(f)
        return {s: (me.arm.matrix_world @ me.arm.pose.bones[b].head) for s, b in hand.items()}
    for k, label, height_of in (('vault', 'the vault\'s prop hand on the cover top', 'cover'),
                                ('mount', 'a hand on the lip / the top during the mount', 'top')):
        best = []
        for a, b in runs.get(k, []):
            d_min = 9.9
            for f in range(a, b + 1, 2):
                rr = recs[f - f0]
                hz = hand_z(f)
                y = rr['feet_world'][1]
                tops = [o for o in course.objects if o.type == 'MESH' and 'wall' in o.name.lower()]
                for o in tops:
                    lo, hi = [o.matrix_world @ v.co for v in o.data.vertices], None
                    zmax = max(v.z for v in lo)
                    ymin, ymax = min(v.y for v in lo), max(v.y for v in lo)
                    for s in hz:
                        p = hz[s]
                        if ymin - 0.1 <= p.y <= ymax + 0.1:
                            d_min = min(d_min, abs(p.z - zmax))
            best.append(round(d_min, 3))
        R.check(f'{label} (the nearest hand within 6 cm of the surface)', bool(best) and min(best) < 0.06,
                f'closest per {k}: {best} m')
    # the hands on the rungs through the ladder's loop (a rung is a bar along X: the distance to its line)
    rungs = [o.matrix_world.translation.copy() for o in course.objects if o.get('eido_course_role') == 'rung']
    near = []
    for a, b in runs.get('ladder', []):
        for f in range(a, b + 1, 3):
            hz = hand_z(f)
            d = min((math.hypot(p.y - q.y, p.z - q.z) for p in hz.values() for q in rungs if abs(p.x - q.x) < 0.3),
                    default=9.9)
            near.append(d)
    R['ladder_hand_to_rung_m'] = [round(d, 3) for d in near]
    R.check('the hands latch the rungs through the ladder (a hand within 6 cm of a rung in most sampled frames)',
            bool(near) and float(np.mean(np.array(near) < 0.06)) > 0.5,
            f'{sum(1 for d in near if d < 0.06)} of {len(near)} sampled frames; median {np.median(near) if near else 9.9:.3f} m')
    # the walking and running stretches
    T.gait_checks(R, rep)
    seated = [r for r in recs if r['mode'] == 'seated']
    R.check('the sit stop: seated on the bench', len(seated) > 30, f'{len(seated)} seated frames')
    gw = max((r['weights'].get('cheer', 0.0) for r in recs), default=0.0)
    R.check('the cheer gesture over the walk', gw > 1.0, f'weight up to {gw:.2f}')
    em = [r for r in recs if r['mode'] == 'emote' and r['weights'].get('salute', 0) > 0.5]
    R.check('the finale salute', len(em) > 10, f'{len(em)} frames')
    end = recs[-1]['feet_world']
    R.check('the finale stands on the ladder\'s top platform', top['y0'] < end[1] < top['y1'] and
            abs(end[2] - top['floor0']) < 0.08, f'feet at {tuple(round(v, 2) for v in end)}, the platform at '
            f'{top["floor0"]:.2f} m from y {top["y0"]:.2f} to {top["y1"]:.2f}')
    R['worst'] = rep['worst']
    T.keyed_matches(R, me, frames)
    shots(sc, me, recs, segs, runs)


def shots(sc, me, recs, segs, runs):
    T.light(sc)
    S, sheets = [], {'sheet': []}
    r0 = recs[0]['f']
    for s_ in segs:
        a, b = s_['frames']
        if b - a < 8:
            continue
        f = (a + b) // 2
        sc.frame_set(f)
        name = f'{s_["gait"].replace(":", "-")}_f{f:03d}'
        S.append(T.side_shot(me, recs[f - r0], name, dist=5.2, lens=35.0, height=0.45))
        sheets['sheet'].append(name)
    for k, rs in runs.items():
        for j, (a, b) in enumerate(rs[:2]):
            a2, b2 = max(r0, a - 6), b + 10
            fs = [int(a2 + (b2 - a2) * i / 7) for i in range(8)]
            mid = fs[4]
            sc.frame_set(mid)
            cam = T.side_shot(me, recs[mid - r0], 'x', dist=4.0, lead=0.0, height=0.5)
            names = []
            for i, f in enumerate(fs):
                nm = f'strip_{k}{j}_{i}'
                S.append(dict(cam, name=nm, frame=f))
                names.append(nm)
            sheets[f'strip_{k}{j}'] = names
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
