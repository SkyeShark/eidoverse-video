"""Steering the controller frame by frame from scene logic (Locomotion.steer) and following a keyed object
(Locomotion.follow), planted and keyed like any command:

    test_controller_follow.py [--vrm aletheia] [--tag NAME] [--no-render]

A cart (a box, keyed every frame) stands, rolls off at 1.5 m/s, curves left and stops; after 2 s it races off at
2.8 m/s and stops again. The body follows it 1.8 m from its middle (walking, then running while the cart races), then
steers itself for 5 s along a heading a function of time gives (a slow S), and stops.

Prints PASS / FAIL: she sets off after the cart and keeps within reach of it while it rolls; she never comes nearer
than her distance less 0.3 m; she stops at her distance where it stops, and again at its last stop; she runs while it
races; the steered walk follows the function's heading; checks.feet on every gait's frames (planted feet, no slip, one
foot down in a walk); the keyed armature matches the bake. Stills (render_shots.py): low side strips of the set-off,
the run after the racing cart and the stop behind it, and the steered S.
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
from eidoblend.course.builder import box_mesh, plane_mesh  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'follow_{VRM}'))
R['vrm'] = VRM
FPS = 30
DIST = 1.8
PATH = [(0.0, 2.0), (0.0, 8.0), (-1.5, 10.5), (-4.0, 11.0), (-11.0, 11.0)]


def polyline(pts):
    seg = [(Vector(a), Vector(b)) for a, b in zip(pts, pts[1:])]
    lens = [(b - a).length for a, b in seg]

    def at(s):
        for (a, b), ln in zip(seg, lens):
            if s <= ln:
                return a + (b - a) * (s / ln), (b - a).normalized()
            s -= ln
        a, b = seg[-1]
        return b.copy(), (b - a).normalized()
    return at, sum(lens), lens


def cart_schedule():
    """the cart's travel along PATH, frame by frame from frame 1: it stands 1 s, rolls to the third corner at 1.5 m/s
    (3 m/s^2 either way), stands 2 s, races to the end at 2.8 m/s, stands 2 s -> ([s per frame], {'go0': the frame
    its first move shows, 'stop0': the frame it stands again, 'go1', 'stop1'})"""
    _at, total, lens = polyline(PATH)
    dt = 1.0 / FPS
    S, marks, s = [0.0] * FPS, {}, 0.0
    for k, (goal, vmax) in enumerate(((sum(lens[:3]), 1.5), (total, 2.8))):
        marks[f'go{k}'] = len(S) + 1
        v = 0.0
        while goal - s > 1e-4:
            v = min(vmax, v + 3.0 * dt, math.sqrt(2.0 * 3.0 * (goal - s)))
            s = min(goal, s + max(v, 1e-3) * dt)
            S.append(s)
        marks[f'stop{k}'] = len(S)
        S += [s] * (2 * FPS)
    return S, marks


def make_cart(sched):
    """a box keyed at every frame of the schedule, turned to its travel"""
    from bpy_extras import anim_utils
    me = box_mesh('cart', (0.9, 1.6, 0.7))
    me.materials.append(T.course_materials()['obstacle'])
    cart = bpy.data.objects.new('cart', me)
    bpy.context.scene.collection.objects.link(cart)
    at, _total, _l = polyline(PATH)
    cart.rotation_mode = 'XYZ'
    for i, s in enumerate(sched):
        p, d = at(s)
        cart.location = (p.x, p.y, 0.35)
        cart.rotation_euler = (0.0, 0.0, math.atan2(d.x, -d.y))
        cart.keyframe_insert('location', frame=i + 1)
        cart.keyframe_insert('rotation_euler', frame=i + 1)
    ad = cart.animation_data
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    for fc in cb.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return cart


def main():
    sc = T.S.clean_scene(fps=FPS)
    pm = plane_mesh('floor', 60.0)
    pm.materials.append(T.course_materials()['ground'])
    floor = bpy.data.objects.new('floor', pm)
    sc.collection.objects.link(floor)
    sched, marks = cart_schedule()
    R['cart_marks'] = marks
    cart = make_cart(sched)
    me = load_vrm(VRM, name=VRM)
    loco = Locomotion(me, CollisionWorld(exclude=[cart]), start=(0.0, 0.2, 0.0), heading=math.pi, log=R.log)
    stamps = {}

    def mark(name):
        def f(c):
            stamps[name] = c.time
        return f
    loco.wait(0.3)
    loco.call(mark('follow'))
    loco.follow(cart, distance=DIST)
    loco.call(mark('steer'))
    base = math.radians(30.0)

    def s_curve(t, ctrl):
        a = base + 0.9 * math.sin(2.0 * math.pi * t / 5.0)
        return (math.sin(a), -math.cos(a)) if t < 5.0 else None
    loco.steer(s_curve)
    loco.call(mark('end'))
    loco.wait(0.8)
    t0 = time.time()
    rep = loco.bake(f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    fr = {k: f0 + int(round(t * FPS)) for k, t in stamps.items()}
    R['marks'] = fr
    R['segments'] = [(s['gait'], s['frames']) for s in rep['segments']]
    byf = {r['f']: r for r in recs}
    at, _tot, _l = polyline(PATH)

    def cart_xy(f):
        return at(sched[min(len(sched) - 1, f - 1)])[0]

    def gap(f):
        r = byf[f]
        p = Vector(r['feet_world'][:2])
        return (p - cart_xy(f)).length

    follow_frames = range(fr['follow'], fr['steer'])
    gaps = [(f, gap(f)) for f in follow_frames]
    R['gap_every_15'] = [(f, round(g, 3)) for f, g in gaps[::15]]
    near = min(gaps, key=lambda x: x[1])
    R.check(f'she never comes nearer than {DIST - 0.3:.1f} m to the cart', near[1] > DIST - 0.3,
            f'nearest {near[1]:.2f} m at f{near[0]}')
    go0, stop0, go1, stop1 = marks['go0'], marks['stop0'], marks['go1'], marks['stop1']
    first_move = next((f for f in follow_frames if byf[f]['speed'] > 0.1), None)
    R.check('she sets off after the cart sets off', first_move is not None and go0 <= first_move <= go0 + 20,
            f'the cart at f{go0}, she at f{first_move}')
    roll = [g for f, g in gaps if go0 + 60 <= f <= stop0 - 15]
    R.check('she keeps within reach while it rolls at 1.5 m/s', bool(roll) and max(roll) < DIST + 1.0,
            f'the gap {min(roll):.2f}-{max(roll):.2f} m (her distance {DIST} m)' if roll else 'no frames')
    for label, f_stop, f_next in (('its first stop', stop0, go1), ('its last stop', stop1, fr['steer'])):
        f_chk = min(f_next - 2, f_stop + 50)
        g = gap(f_chk)
        sp = byf[f_chk]['speed']
        R.check(f'she stands at her distance behind {label}', abs(g - DIST) < 0.25 and sp < 0.05,
                f'{g:.2f} m at f{f_chk} (wanted {DIST}), speed {sp:.3f} m/s')
    ran = [s for s in rep['segments'] if s['gait'] == 'run' and s['frames'][1] >= go1 and s['frames'][0] <= stop1]
    R.check('she runs while the cart races at 2.8 m/s', bool(ran), f"{[s['frames'] for s in ran]}")
    # the steered S: her travel against the function's heading (the controller turns at most 3.5 rad/s)
    errs = []
    for f in range(fr['steer'] + 24, fr['end'] - 6):
        r0, r1 = byf.get(f - 1), byf.get(f)
        if r0 is None or r1 is None or r1['speed'] < 0.3:
            continue
        d = Vector(r1['feet_world'][:2]) - Vector(r0['feet_world'][:2])
        t = (f - fr['steer']) / FPS
        a = base + 0.9 * math.sin(2.0 * math.pi * t / 5.0)
        want = Vector((math.sin(a), -math.cos(a)))
        if d.length > 1e-4:
            errs.append(math.degrees(d.angle(want)))
    R.check('the steered walk follows the heading its function gives', errs and np.percentile(errs, 90) < 20.0,
            f'90th percentile {np.percentile(errs, 90):.1f} deg over {len(errs)} frames' if errs else 'no frames')
    T.gait_checks(R, rep)
    T.keyed_matches(R, me, frames)
    # stills: low side strips
    T.light(sc)
    shots, sheets = [], {}

    def strip(label, a, b, step, side=1.0, dist=4.6, height=0.15):
        names = []
        a, b = max(a, f0), min(b, f1)
        mid = (a + b) // 2
        sc.frame_set(mid)
        cam = T.side_shot(me, byf[mid], 'x', dist=dist, side=side, height=height, lead=0.8)
        for k, f in enumerate(range(a, b + 1, step)):
            nm = f'strip_{label}_{k}'
            shots.append(dict(cam, name=nm, frame=f))
            names.append(nm)
        sheets[f'strip_{label}'] = names
    strip('set_off', go0 - 3, go0 + 42, 5)
    strip('run', go1 + 10, go1 + 60, 5, dist=6.0)
    strip('stop', stop1 - 30, stop1 + 30, 6, dist=5.2)
    strip('steer', fr['steer'], fr['end'], 12, dist=6.5, height=1.2)
    T.save(R, sc, shots, sheets)


try:
    main()
except Exception as e:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, f'{type(e).__name__}: {e}')
R.finish()
