"""A saved .blend plays on its own: each set animated on its own clock (animate keys every moving part), saved, and the
same frames rendered twice, once in the session that keyed them and once from the saved file in a fresh Blender that
imports nothing of eidoblend. The renders must match: whatever the set left live in Python (a driver, a Geometry
Nodes input, an image variant, a camera cut by markers) would show up as a difference.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <this folder>/verify_keyed_replay.py bake corridor      (then: ... verify_keyed_replay.py replay corridor)
    the same with news

The corridor (4 s at 24 fps): a repost typed from 0.5 s, the cap carried to a stand-in head from 1 s, the door camera
cutting to corridorWide at frame 49 (a marker), the doors opening from 2.2 s, a recount at 2.5 s, the lights dimming
from 3.4 s. The news (4 s): the crowd camera, the wall from frame 41, the wide from frame 73; the tag sprayed from 1.7 s,
the signs on a kick, the floods off after 3.2 s. Writes out/verify/keyed/<set>_{live,replay}_fNNN.png and the .blend.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

A = F.args()
PHASE = A[0] if A else 'bake'
WHICH = A[1] if len(A) > 1 else 'corridor'
OUT = F.OUT / 'verify' / 'keyed'
OUT.mkdir(parents=True, exist_ok=True)
BLEND = OUT / f'{WHICH}_keyed.blend'
FRAMES = {'corridor': (20, 40, 70, 96), 'news': (12, 50, 62, 90)}[WHICH]
FPS = 24


def render_frames(tag):
    sc = bpy.context.scene
    for f in FRAMES:
        sc.frame_set(f)
        F.render_still(OUT / f'{WHICH}_{tag}_f{f:03d}.png', sc)


def bake_corridor(sc):
    from eidoblend.sets.unknown_force import corridor as COR
    C = COR.build(sc, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM'})
    C.apply_look(sc)
    C.apply_post(sc, aeropittura=False)
    head = bpy.data.objects.new('stand_in_head', None)          # a bare head bone where hers would be
    C.collection.objects.link(head)
    head.location = (0.0, 0.0, 1.45)
    cams = {n: C.camera(n, sc, set_active=False) for n in ('door', 'corridorWide')}
    for f, n in ((1, 'door'), (49, 'corridorWide')):
        sc.timeline_markers.new(f'cut_{n}', frame=f).camera = cams[n]

    def state(t):
        f = int(round(t * FPS)) + 1
        return {'postText': 'A NEW POST, IN CAPITAL LETTERS' if t >= 0.5 else 'AMERICANISM, NOT EFFECTIVE ALTRUISM',
                'post': (t - 0.5) / 0.6 if t >= 0.5 else 1.0,
                'capOn': (t - 1.0) / 0.8, 'capHead': head,
                'open': (t - 2.2) / 1.2,
                'tally': [512000, 418000, 341000] if t > 2.5 else [588214, 471902, 144215],
                'lights': 1.0 - 0.4 * min(1.0, max(0.0, t - 3.4) / 0.5),
                'camera': cams['door'] if f < 49 else cams['corridorWide']}
    C.animate(state, frames=(1, 96), scene=sc)
    return C


def bake_news(sc):
    from eidoblend.sets.unknown_force import news as NEWS
    N = NEWS.build(sc)
    N.apply_look(sc)
    N.apply_post(sc, aeropittura=False)
    cams = {n: N.camera(n, sc, set_active=False) for n in ('crowd', 'wall', 'wide')}
    for f, n in ((1, 'crowd'), (41, 'wall'), (73, 'wide')):
        sc.timeline_markers.new(f'cut_{n}', frame=f).camera = cams[n]

    def state(t):
        f = int(round(t * FPS)) + 1
        return {'spray': 0.0 if t < 1.7 else min(1.0, (t - 1.7) / 0.8), 'chant': 1.0,
                'pulse': max(0.0, 1.0 - ((t * 2.0) % 1.0) * 3.0),        # a kick on every half second
                'floods': 0.0 if t > 3.2 else 1.0,
                'camera': cams['crowd'] if f < 41 else cams['wall'] if f < 73 else cams['wide']}
    N.animate(state, frames=(1, 96), scene=sc)
    return N


if PHASE == 'bake':
    sc = F.clean_scene()
    F.render_settings(960, 540, 16, fps=FPS)
    sc.frame_start, sc.frame_end = 1, 96
    S = bake_corridor(sc) if WHICH == 'corridor' else bake_news(sc)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), copy=True)
    print(f'[keyed] saved {BLEND.name} ({BLEND.stat().st_size / 1e6:.0f} MB)', flush=True)
    render_frames('live')
else:
    mods = [m for m in sys.modules if m.startswith('eidoblend')]
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    render_frames('replay')
    from PIL import Image
    for f in FRAMES:
        a = np.asarray(Image.open(OUT / f'{WHICH}_live_f{f:03d}.png').convert('RGB')).astype(float)
        b = np.asarray(Image.open(OUT / f'{WHICH}_replay_f{f:03d}.png').convert('RGB')).astype(float)
        d = np.abs(a - b)
        F.check(f'{WHICH} frame {f}: the saved .blend renders it as the session that keyed it did',
                d.mean() < 1.0 and np.percentile(d.max(2), 99.5) < 24, f'mean |d| {d.mean():.3f}, p99.5 '
                f'{np.percentile(d.max(2), 99.5):.0f}, max {d.max():.0f}')
    F.check('replay: nothing of eidoblend was imported (the file stands alone)',
            not mods and not any(m.startswith('eidoblend') for m in sys.modules))
    F.summary()
