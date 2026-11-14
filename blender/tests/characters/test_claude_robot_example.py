"""eidoverse/examples/claude_robot.js in Blender: my body playing the stock idle through its hardware limits, the OLED face
running through a few expressions and a spoken "hello", the head and the crown's petals following the face, the eyes
looking left then right, set down onto the floor each frame. Same studio (the example's own light, background, floor),
same 8 s at 30 fps, the same camera move (the whole body easing in to the head and shoulders). Performed and keyed by
performance.perform (no handler at render time), checked, saved as out/claude_robot_example.blend. Not the example's
whole frame: it also runs applyLegClearance and initHandDOF / applyHandDOF each frame, which robot_dof does not port yet
(characters.md, "Not yet ported"). Stills at the moments the example's face track names:

    out/claude_robot_example_t<S.SS>.png      t = 0.5 (rest), 2.1 (happy), 3.85 ("hello": oh), 5.25 (surprised),
                                              6.8 (relaxed, looking left), 7.6 (looking right)
    out/claude_robot_example.json             the report and the checks

    bash run_blender.sh blender/tests/characters/test_claude_robot_example.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters import Ground, load_clip, load_vrm, perform  # noqa: E402
from eidoblend.characters import checks  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS, DUR = 30, 8.0
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def smooth(a, b, x):
    return ease((x - a) / (b - a))


def bump(t, t0, t1):
    return 0.0 if (t <= t0 or t >= t1) else math.sin(math.pi * ease((t - t0) / (t1 - t0)))


LINE = [(3.3, 3.55, 'ee'), (3.55, 3.75, 'ih'), (3.75, 4.2, 'oh')]
ROUND = {'oh', 'ou'}


def face(t):
    """the example's face(vrm, t), line for line"""
    s = {'happy': bump(t, 1.2, 3.1), 'surprised': bump(t, 4.5, 6.0), 'relaxed': smooth(6.0, 6.6, t),
         'blink': bump(t, 0.7, 0.95) + bump(t, 6.1, 6.35)}
    mouth = {}
    for t0, t1, v in LINE:
        w = min(1.0, max(0.0, (t - t0 + 0.03) / 0.06)) * min(1.0, max(0.0, (t1 + 0.03 - t) / 0.06))
        mouth[v] = mouth.get(v, 0.0) + (smooth(0.15, 0.6, w) if v in ROUND else w)
    sm = sum(mouth.values())
    for v in ('aa', 'ih', 'ou', 'ee', 'oh'):
        s[v] = mouth.get(v, 0.0) / max(1.0, sm)
    return {k: min(1.0, v) for k, v in s.items()}


def look(t):
    return 20.0 * (bump(t, 6.4, 7.2) - bump(t, 7.2, 8.0))


def log(*a):
    print('[robot_example]', *a, flush=True)


try:
    sc = S.clean_scene(FPS)
    S.probe_render(sc)
    S.studio_world(sc, 0.8, background=0x121214)
    S.sun('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.2, angle_deg=3.0)
    S.sun('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.0, angle_deg=3.0)
    S.floor_disc()
    me = load_vrm('claude_robot', name='claude')
    idle = load_clip(me, 'idle')
    nfr = int(DUR * FPS)
    sc.frame_start, sc.frame_end = 1, nfr
    t = time.time()
    rep = perform(me, idle, 1, nfr, ground=Ground(fn=lambda x, y: 0.0 * x), face=face, look=look)
    R['perform_s'] = round(time.time() - t, 1)
    R['perform'] = {k: v for k, v in rep.items() if not k.startswith('_')}
    fr = {x['f']: x for x in rep['_frames']}
    R['petals_at'] = {f'{tt:.2f}': [round(p, 1) for p in fr[1 + round(tt * FPS)]['petals']] for tt in (0.5, 2.1, 5.25, 6.8, 7.6)}
    R['checks'] = {'posed_vs_rest_deg': checks.posed_vs_rest(me, [1, nfr // 2]),
                   'happy': checks.expression_moved(me, 'happy', [1, 64, 100]),
                   'mouth_oh': checks.expression_moved(me, 'oh', [1, 117, 120, 124]),
                   'blink': checks.expression_moved(me, 'blink', [1, 25]),
                   'look_left': checks.expression_moved(me, 'lookLeft', [1, 205])}
    log('perform', R['perform_s'], 's', R['perform']['set_down_mm'], R['checks'])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'claude_robot_example.blend'), compress=True)
    if RENDER:
        cam = S.camera('cam', 50.0)
        cam.data.sensor_fit = 'VERTICAL'
        cam.data.angle_y = math.radians(30.0)
        rs = {}
        for tt in (0.5, 2.1, 3.85, 5.25, 6.8, 7.6):
            f = 1 + round(tt * FPS)
            k = ease((tt - 1.2) / 4.3)
            dist, a = 3.9 + (1.6 - 3.9) * k, 0.35 - 0.2 * k
            S.aim(cam, (math.sin(a) * dist, -math.cos(a) * dist, 1.0 + 0.55 * k), (0.0, 0.0, 0.88 + 0.57 * k))
            p = os.path.join(S.OUT, f'claude_robot_example_t{tt:.2f}.png')
            rs[os.path.basename(p)] = S.still(sc, cam, f, p)
        R['renders'] = rs
    R['ok'] = True
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
with open(os.path.join(S.OUT, 'claude_robot_example.json'), 'w', encoding='utf-8') as f:
    json.dump(R, f, indent=1, default=str)
log('done', R['ok'], R['seconds'], 's')
