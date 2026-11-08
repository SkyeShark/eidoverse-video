"""The controller on every TERRAIN_CONFIG the WebGPU locomotion bench ran (eidoblend.course.PRESETS: terrain_base.js's
variant scenes), one preset a run:

    test_controller_presets.py --preset stairs_small [--vrm aletheia] [--tag NAME]

    stairs / stairs_small / stairs_steep     walk up 10 treads, stop on the flight, turn about (two turns on the spot on
                                             the tread), walk back down to the floor and stop
    ramp15 / ramp33 / ramp45                 walk 5 m up the slope, stop on it, turn about, walk down and stop on the flat
    ramp_pyramid / stairs_pyramid            walk over (up, the plateau, down) and stop beyond
    large_stairs_only                        the six large steps up and down, end to end
    obstacle_course_expanded                 the engine's stress course end to end: bumps of 6 / 10 / 15 cm, a dome, 8 deg
                                             ramps, small / normal / large stairs both ways, 22 deg up and 25 deg down

Prints PASS / FAIL: checks.feet on every gait's frames, the stop(s) on the mark, what the probes classified, which clips
led on the slopes and steps, the speed scale the climb angle set (attachLocomotion: 1 at 5 deg falling to 0.55 at 30),
the keyed armature against the bake. Writes out/presets_<preset>.json / .blend / _shots.json (render_shots.py).
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
from eidoblend.course import PRESETS  # noqa: E402

ARGS = T.argv()
PRESET = T.arg(ARGS, '--preset', 'stairs_small')
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'presets_{PRESET}'))
R['vrm'], R['preset'] = VRM, PRESET


def plan(loco, course, cfg):
    """the walk for a preset -> the marks it should stop on"""
    t = cfg['type']
    y_first = course.first_y
    marks = []
    loco.wait(0.6)
    if t == 'stairs':
        run = cfg['run']
        top = (0.0, y_first + 9.0 * run)                 # the middle of the tenth tread (the first is centred on y_first)
        loco.move_to(top, gait='walk')
        marks.append(top)
        loco.wait(0.4).turn_by(180).wait(0.3)
        back = (0.0, y_first - 1.6)
        loco.move_to(back, gait='walk')
        marks.append(back)
    elif t == 'ramp':
        ang = cfg['angleDeg'] * math.pi / 180
        up = (0.0, y_first + 5.0 * math.cos(ang))
        loco.move_to(up, gait='walk')
        marks.append(up)
        loco.wait(0.4).turn_by(180).wait(0.3)
        back = (0.0, y_first - 1.6)
        loco.move_to(back, gait='walk')
        marks.append(back)
    else:
        end = (0.0, course.end_y + (2.0 if t != 'obstacle_course' else -1.2))
        loco.move_to(end, gait='walk')
        marks.append(end)
    loco.wait(0.6)
    return marks


def main():
    sc = T.S.clean_scene(fps=30)
    cfg = PRESETS[PRESET]
    course = T.course(cfg)
    me = load_vrm(VRM, name=VRM)
    world = CollisionWorld()
    loco = Locomotion(me, world, start=(0.0, -5.0, 0.0), heading=math.pi, log=R.log)
    marks = plan(loco, course, cfg)
    t0 = time.time()
    rep = loco.bake(f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    segs = rep['segments']
    R['segments'] = segs
    T.gait_checks(R, rep)
    stops = [i for i in range(1, len(recs)) if recs[i - 1]['speed'] > 0.05 and recs[i]['speed'] <= 0.05]
    stop_pts = [recs[i]['feet_world'] for i in stops]
    for k, m in enumerate(marks):
        d = min((math.hypot(p[0] - m[0], p[1] - m[1]) for p in stop_pts), default=9.9)
        R.check(f'stop {k + 1} on its mark ({m[0]:.2f}, {m[1]:.2f})', d < 0.08, f'{d * 100:.1f} cm from it')
    modes = sorted(set(r['support_mode'] or '-' for r in recs))
    leads = {}
    for r in recs:
        leads.setdefault(r['support_mode'] or '-', set()).add(r['lead'])
    R['support_modes'] = modes
    R['leads_by_support'] = {k: sorted(x for x in v if x) for k, v in leads.items()}
    R.log(f'support modes {modes}; leads {R["leads_by_support"]}')
    t = cfg['type']
    if t in ('stairs', 'stairs_pyramid'):
        R.check('the flight reads as stairs both ways', {'stairUp', 'stairDown'} <= set(modes), f'{modes}')
        R.check('the stair clips lead on the flight', 'stairsUp' in leads.get('stairUp', ()) and
                'stairsDown' in leads.get('stairDown', ()), f'{R["leads_by_support"]}')
    if t in ('ramp', 'ramp_pyramid'):
        sc_ = [r['speed_scale'] for r in recs if r['support_mode'] == 'rampUp' or (r['climb_deg'] or 0) > 5]
        ang = cfg['angleDeg']
        if sc_:
            lo = float(min(sc_))
            R.check(f'the climb slows the body ({ang} deg: speed scale under 1)', lo < 0.97, f'least {lo:.2f}')
        R['speed_scale_min'] = float(min(sc_)) if sc_ else None
        R['climb_deg_max'] = float(max(abs(r['climb_deg'] or 0) for r in recs))
    if PRESET == 'obstacle_course_expanded':
        R.check('every terrain kind classified', {'flat', 'rampUp', 'rampDown', 'stairUp', 'stairDown'} <= set(modes),
                f'{modes}')
        bump_leads = set()
        for s in course.segments:
            if s['kind'] in ('bump', 'dome'):
                y0, y1 = s['y0'] - 0.3, s['y1'] + 0.3
                bump_leads |= set(r['lead'] for r in recs if y0 <= r['feet_world'][1] <= y1)
        R['bump_leads'] = sorted(x for x in bump_leads if x)
        R.check('the bumps and the dome are walked (isolated obstacles keep the walk)', 'walk' in bump_leads,
                f'{R["bump_leads"]}')
    R['worst'] = rep['worst']
    R['pelvis_lowered_mm'] = rep['pelvis_lowered_mm']
    R['released'] = rep.get('released')
    if T.arg(ARGS, '--dump'):
        T.dump_frames(R, rep, [tuple(int(v) for v in rg.split('-')) for rg in T.arg(ARGS, '--dump').split(',')])
    T.keyed_matches(R, me, frames)
    shots(sc, me, recs, segs)


def shots(sc, me, recs, segs):
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
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
