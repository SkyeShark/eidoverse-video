"""Clippy (eidoblend.characters.clippy, the port of eidoverse/clippy.js) on the studio floor: eight of his original clips
scheduled one after another, baked, and a still at each clip's peak:

    out/clippy_<Clip>.png    RestPose, Greeting (the wave), IdleAtom (three rings, the electrons), Writing (the pencil),
                             CheckingSomething (the page held up), GetWizardy (the hat), Print (the page feeding),
                             Congratulate (the checkmark)
    out/clippy.json          the build (vertices, shape keys, timings) and the checks: every shape key moves some vertex,
                             the topology is one for all keys

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/characters/test_clippy.py [--no-render]
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
import numpy as np  # noqa: E402

from eidoblend.characters.clippy import MORPHS, make_clippy  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()
SHOW = [('RestPose', 0.8), ('Greeting', 0.7), ('IdleAtom', 3.0), ('Writing', 2.0), ('CheckingSomething', 2.0),
        ('GetWizardy', 2.3), ('Print', 3.8), ('Congratulate', 2.4)]


def log(*a):
    print('[clippy]', *a, flush=True)


try:
    sc = S.clean_scene(FPS)
    S.probe_render(sc)
    S.studio_world(sc, 0.8, background=0x121214)
    S.sun('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.2, angle_deg=3.0)
    S.sun('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.0, angle_deg=3.0)
    S.floor_disc()
    t = time.time()
    clippy = make_clippy(height=1.2)
    R['build_s'] = round(time.time() - t, 1)
    me = clippy.obj.data
    kbs = me.shape_keys.key_blocks
    base = np.zeros(len(me.vertices) * 3)
    kbs['Basis'].data.foreach_get('co', base)
    moved = {}
    for n in MORPHS:
        co = np.zeros_like(base)
        kbs[n].data.foreach_get('co', co)
        moved[n] = round(float(np.abs(co - base).max()), 4)
    R['mesh'] = {'vertices': len(me.vertices), 'faces': len(me.polygons), 'shape_keys': len(kbs) - 1,
                 'materials': [m.name for m in me.materials]}
    R['morph_max_offset_m'] = moved
    R['morphs_that_never_move'] = [n for n, v in moved.items() if v < 1e-4]
    t0, sched = 0.5, {}
    for name, peak in SHOW:
        clippy.play(name, t0)
        sched[name] = (t0, t0 + peak)
        t0 += __import__('eidoblend.characters.clippy', fromlist=['CLIPS']).CLIPS[name]['dur'] + 0.6
    f1 = int(math.ceil(t0 * FPS)) + 1
    sc.frame_start, sc.frame_end = 1, f1
    R['bake'] = clippy.bake(1, f1)
    R['schedule'] = sched
    log(R['mesh'], 'never move:', R['morphs_that_never_move'], R['bake'])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'clippy.blend'), compress=True)
    if RENDER:
        cam = S.camera('cam', 50.0)
        S.aim(cam, (1.35, -4.3, 1.15), (0.0, 0.0, 0.78))
        rs = {}
        for name, (a, peak) in sched.items():
            f = 1 + round(peak * FPS)
            p = os.path.join(S.OUT, f'clippy_{name}.png')
            rs[os.path.basename(p)] = (S.still(sc, cam, f, p), clippy.current_clip((f - 1) / FPS))
        R['renders'] = rs
    R['ok'] = True
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
with open(os.path.join(S.OUT, 'clippy.json'), 'w', encoding='utf-8') as f:
    json.dump(R, f, indent=1, default=str)
log('done', R['ok'], R['seconds'], 's')
