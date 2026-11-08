"""The controller's course: a VRM starts from standing, walks over a step-over bump, up and down 8 deg ramps and a small
flight of stairs up and down, runs up and down a normal flight, slows to a walk and stops on its mark, turns on the spot
left and back, and walks off to the side; every frame planted by the film bake, keyed, checked per gait.

    test_controller_course.py [--vrm claude_robot | aletheia | claude] [--tag NAME]

The course is terrain_base.js's obstacle_course pieces (built by eidoblend.course), the locomotion half of the WebGPU
examples/obstacle_course.js (its vault, mount, gap jump, wall climb and ladder are the maneuvers'):

    0 flat 2.0 | 1 bump 0.10 x 0.30 | 2 flat 1.2 | 3 ramp up 8 deg 2.0 | 4 flat 1.0 | 5 ramp down 8 deg 2.0 | 6 flat 1.2
    7 stairs up 0.10 / 0.30 x 5 | 8 flat 1.0 | 9 stairs down 0.10 / 0.30 x 5 | 10 flat 2.4 (the run starts)
    11 stairs up 0.18 / 0.28 x 4 | 12 flat 1.6 | 13 stairs down 0.18 / 0.28 x 4 | 14 flat 6.0 (slow down, stop)

Prints PASS / FAIL lines: checks.feet on every gait's frames (a run's flight and its lack of double support waived:
that is what a run is), every gait the course asks for played, the stop on its mark, the walk and the run at their
measured paces, the stairs at the tread-synced speed, the turns' angles, the keyed result against Blender's evaluated
pose. Writes out/<tag>.json, out/<tag>.blend and out/<tag>_shots.json; render_shots.py renders:
    <tag>_<gait>_fNNN       a camera beside the body, the whole figure, at the middle of each gait's stretch
    <tag>_strip_<gait>_k    six frames of the gait from one fixed camera (motion read as a strip; sheet strip_<gait>)
    <tag>_feet_k            a fixed low camera on the small stairs up: a planted foot through its stance
    <tag>_wide              the whole course from above and to the side

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/test_controller_course.py --vrm aletheia
    bash C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/gpu_slot.sh \\
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/render_shots.py \\
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/out/course_aletheia_shots.json
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ctrl_stage as T  # noqa: E402

import numpy as np  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'claude_robot')
R = T.Report(T.arg(ARGS, '--tag', f'course_{VRM}'))
R['vrm'] = VRM
SEGMENTS = [
    {'kind': 'flat', 'length': 2.0},
    {'kind': 'bump', 'height': 0.10, 'depth': 0.30},
    {'kind': 'flat', 'length': 1.2},
    {'kind': 'ramp', 'angleDeg': 8, 'horizLen': 2.0, 'dir': 'up'},
    {'kind': 'flat', 'length': 1.0},
    {'kind': 'ramp', 'angleDeg': 8, 'horizLen': 2.0, 'dir': 'down'},
    {'kind': 'flat', 'length': 1.2},
    {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 5, 'dir': 'up'},
    {'kind': 'flat', 'length': 1.0},
    {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 5, 'dir': 'down'},
    {'kind': 'flat', 'length': 2.4},
    {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 4, 'dir': 'up'},
    {'kind': 'flat', 'length': 1.6},
    {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 4, 'dir': 'down'},
    {'kind': 'flat', 'length': 6.0},
]


def main():
    sc = T.S.clean_scene(fps=30)
    course = T.course({'type': 'obstacle_course', 'segments': SEGMENTS})
    seg = course.segment
    me = load_vrm(VRM, name=VRM)
    world = CollisionWorld()
    R.log(f'world: {len(world.objects)} meshes')
    loco = Locomotion(me, world, start=(0.0, -4.5, 0.0), heading=math.pi, log=R.log)
    R['native_mps'] = {k: round(v, 3) for k, v in loco.native.items()}
    run_from = seg(10)['y0'] + 0.6
    stop_at = (0.0, seg(14)['y0'] + 3.0)
    side = (-2.2, stop_at[1] + 0.4)
    loco.wait(0.8)
    loco.follow_path([(0.0, run_from)], gait='walk', stop=False)
    loco.follow_path([(0.0, seg(14)['y0'] + 0.5)], gait='run', stop=False)
    loco.move_to(stop_at, gait='run')
    loco.wait(0.4)
    loco.turn_by(90)
    loco.wait(0.4)
    loco.turn_by(-90)
    loco.wait(0.3)
    loco.move_to(side, gait='walk')
    loco.wait(0.8)
    t = time.time()
    rep = loco.bake(f0=1)
    R['timing_s']['bake'] = round(time.time() - t, 1)
    R['bake_timing_s'] = rep['timing_s']
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    R.log(f'baked frames {f0}-{f1} in {rep["timing_s"]}')
    segs = rep['segments']
    R['segments'] = segs
    T.gait_checks(R, rep)
    seen = set(r['lead'] for r in recs if r['lead'])
    want = {'idle', 'walk', 'run', 'stairsUp', 'stairsDown', 'stairsRunUp', 'stairsRunDown', 'turnLeft', 'turnRight'}
    R.check('every gait the course asks for played', want <= seen, f'played {sorted(seen)}; missing {sorted(want - seen)}')
    modes = set(r['support_mode'] or '-' for r in recs)
    R.check('the probes classified flat, ramps and stairs both ways',
            {'flat', 'rampUp', 'rampDown', 'stairUp', 'stairDown'} <= modes, f'{sorted(modes)}')
    stops = [i for i in range(1, len(recs)) if recs[i - 1]['speed'] > 0.05 and recs[i]['speed'] <= 0.05]
    end = recs[-1]['feet_world']
    d_end = math.hypot(end[0] - side[0], end[1] - side[1])
    R.check('the walk to the side stops on its mark', d_end < 0.06, f'{d_end * 100:.1f} cm from it')
    first_stop = next((recs[i]['feet_world'] for i in stops if recs[i]['f'] > 60), None)
    if first_stop is not None:
        d1 = math.hypot(first_stop[0] - stop_at[0], first_stop[1] - stop_at[1])
        R.check('the run slows to a walk and stops on its mark', d1 < 0.06, f'{d1 * 100:.1f} cm from it')
    for g in ('walk', 'run'):
        sp = [r['speed'] for r in recs if r['lead'] == g and r['support_mode'] == 'flat' and r['speed'] > 0.3]
        if sp:
            v = float(np.percentile(sp, 90))
            R.check(f'the {g} reaches its measured pace', abs(v - loco.native[g]) < 0.08 * loco.native[g],
                    f'{v:.3f} m/s against {loco.native[g]:.3f}')
    # the stairs' tread-synced speed (attachLocomotion's targetForwardSpeed): 2 x tread run x cadence / the stair clip's
    # duration (stairCadence 2.5 walking, stairCadenceRun 1.4 running), lerped at 3 / s
    c = loco.ctrl
    for g in ('stairsUp', 'stairsRunUp'):
        ii = [i for i, r in enumerate(recs) if i > 0 and r['lead'] == g and r['support_mode'] == 'stairUp']
        fr = [recs[i] for i in ii]
        if len(fr) < 4:
            R.check(f'{g}: the stair-synced speed', False, f'{len(fr)} frames on the flight')
            continue
        cad = c._stair_cadence_run if g == 'stairsRunUp' else c._stair_cadence
        dur = c._actions[g].clip.duration
        # the target reads LAST frame's probes (locomote sets the speed before update() probes): the stair formula
        # where they had a tread run and a probe spread over stair_spread_threshold, the gait's own speed elsewhere
        errs = []
        for i in ii:
            p = recs[i - 1]
            if p['tread_run'] is not None and p['spread'] > c._stair_spread_threshold:
                want_t = 2 * p['tread_run'] * cad / dur
                if p['stair_shape'] == 'large' and p['terrain'].get('highest_delta', 0) > c._stair_up_ahead_threshold:
                    want_t *= c._large_stair_ascent_speed_scale
                errs.append(abs(recs[i]['target_speed'] - want_t))
        err = max(errs) if errs else 1.0
        # the body moves at the lerped speed times the climb's speed scale (1 at 5 deg, 0.55 at 30)
        cmd = [r['smooth_speed'] * r['speed_scale'] for r in fr]
        off = max(abs(r['speed'] - v) / v for r, v in zip(fr[2:], cmd[2:]))
        R.check(f'{g}: the speed target is 2 x tread run x {cad} / the clip; the body moves at the lerped speed x the '
                f'climb\'s speed scale', err < 1e-6 and off < 0.08,
                f'target {fr[-1]["target_speed"]:.2f} m/s (tread {fr[-1]["tread_run"]:.3f} m), lerped '
                f'{fr[0]["smooth_speed"]:.2f} -> {fr[-1]["smooth_speed"]:.2f}, scale {min(r["speed_scale"] for r in fr):.2f}; '
                f'the body within {off * 100:.1f} % of it')
    hd = [r['heading'] for r in recs]
    runs, cur = [], None
    for i, r in enumerate(recs):
        if r['mode'] == 'turn':
            if cur is None:
                cur = [i, i]
                runs.append(cur)
            cur[1] = i
        else:
            cur = None
    want_turns = [90.0, -90.0]
    for k, (ia, ib) in enumerate(runs):
        ang = math.degrees(((hd[min(ib + 1, len(hd) - 1)] - hd[max(ia - 1, 0)]) + math.pi) % (2 * math.pi) - math.pi)
        if k < len(want_turns):
            want_a = want_turns[k]
        else:
            p = recs[ia]['feet_world']
            want_a = math.degrees(((math.atan2(side[0] - p[0], -(side[1] - p[1])) - hd[max(ia - 1, 0)]) + math.pi)
                                  % (2 * math.pi) - math.pi)
        R.check(f'turn on the spot {k + 1} (frames {recs[ia]["f"]}-{recs[ib]["f"]}) turns {want_a:+.1f} deg',
                abs(ang - want_a) < 1.0, f'{ang:+.1f} deg')
        moved = math.hypot(recs[ib]['feet_world'][0] - recs[ia]['feet_world'][0],
                           recs[ib]['feet_world'][1] - recs[ia]['feet_world'][1])
        R.check(f'turn on the spot {k + 1} stays on the spot', moved < 0.02, f'the root moved {moved * 100:.1f} cm')
    R['stance_ankle_err_over_2mm'] = [x for x in rep['ankle_err_mm'] if x[1] > 2.0]
    R['swing_ankle_err_mm_max'] = rep['worst'].get('swing_ankle_err_mm')
    T.keyed_matches(R, me, frames)
    R['worst'] = rep['worst']
    R['flight_frames'] = len(rep['flight'])
    R['double_support_frames'] = len(rep['double_support'])
    R['pelvis_lowered_mm'] = rep['pelvis_lowered_mm']
    R['action'] = rep['action']
    R['support_modes'] = sorted(modes)
    shots(sc, me, recs, segs)


def shots(sc, me, recs, segs):
    T.light(sc)
    S, sheets = [], {'sheet': []}
    r0 = recs[0]['f']
    for s_ in segs:
        a, b = s_['frames']
        if b - a < 3:
            continue
        f = (a + b) // 2
        sc.frame_set(f)
        name = f'{s_["gait"].replace(":", "-")}_f{f:03d}'
        S.append(T.side_shot(me, recs[f - r0], name))
        sheets['sheet'].append(name)
    # strips: six frames of a gait from one camera placed at the strip's middle frame
    for g in ('walk', 'stairsUp', 'stairsDown', 'run', 'stairsRunUp', 'stairsRunDown', 'turn:turnLeft'):
        s_ = next((x for x in segs if x['gait'] == g and x['frames'][1] - x['frames'][0] >= 10), None)
        if s_ is None:
            continue
        a, b = s_['frames']
        step = 2 if 'run' in g.lower() else 3
        fs = [min(b, a + 2 + k * step) for k in range(6)]
        mid = fs[len(fs) // 2]
        sc.frame_set(mid)
        cam = T.side_shot(me, recs[mid - r0], 'x', dist=3.6, lead=0.0)
        names = []
        for k, f in enumerate(fs):
            nm = f'strip_{g.replace(":", "-")}_{k}'
            S.append(dict(cam, name=nm, frame=f))
            names.append(nm)
        sheets[f'strip_{g.replace(":", "-")}'] = names
    st = next((s_ for s_ in segs if s_['gait'] == 'stairsUp' and s_['frames'][1] - s_['frames'][0] >= 10), None)
    if st is not None:
        a, b = st['frames']
        mid = recs[(a + b) // 2 - r0]['feet_world']
        names = []
        for k, f in enumerate(range(a, b + 1, max(1, (b - a) // 7))):
            nm = f'feet_{k}'
            S.append(T.fixed_shot(nm, f, (mid[0] + 1.7, mid[1] + 0.1, mid[2] + 0.45),
                                  (mid[0], mid[1] + 0.1, mid[2] + 0.15)))
            names.append(nm)
        sheets['feet'] = names
    S.append(T.fixed_shot('wide', recs[len(recs) // 3]['f'], (7.5, 4.0, 4.5), (0.0, 9.0, 0.3), lens=24.0))
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001 - Blender exits 0 on a raise: say FAIL so the run reads as failed
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
