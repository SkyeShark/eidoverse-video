"""A saved .blend plays and renders any frame on its own: baked SDF volumes, their keyed lamps and the nuclear
explosion's keyed opacity, rendered in the session that built them and again by a fresh Blender that only opens the
file.

    cd <main checkout> && bash -c \
        "bash run_blender.sh <worktree>/blender/tests/sdf_volumes/test_volume_reopen.py -- mode=build && \
         bash run_blender.sh <worktree>/blender/tests/sdf_volumes/test_volume_reopen.py -- mode=open"
    (one GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

mode=build: a bonfire (look='lit', its smoke scattering) and a small nuclear explosion baked over frames 1-4, the
    lamps keyed, the explosion's opacity keyed 0.3 -> 1; saved to out/verify/reopen/reopen.blend; frames 2 and 4
    rendered (reopen_session_f02.png, _f04.png).
mode=open: a new Blender opens the file and renders frames 2 and 4 (reopen_fresh_f0N.png); PASS when each matches
    the session's frame and frames 2 and 4 differ (the file plays).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402

A = V.args()
MODE = A.get('mode', 'build')
DIR = os.path.join(V.OUT, 'verify', 'reopen')
os.makedirs(DIR, exist_ok=True)
BLEND = os.path.join(DIR, 'reopen.blend')
W, H = 480, 270


def render_frame(f, tag):
    sc = bpy.context.scene
    sc.frame_set(f)
    p = os.path.join(DIR, f'reopen_{tag}_f{f:02d}.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    return p


if MODE == 'build':
    from eidoblend.sdf import EXAMPLES
    from eidoblend.sdf import nuclear_explosion as NX
    from eidoblend.sdf.examples_volumes import light_from_emission, fit_volume_range
    V.stage(W, H, 16, world=0.03, sun=0.4, floor=True, floor_size=400.0, sun_rot=(65.0, 0.0, -30.0))
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 4
    cam = V.camera((3.0, -14.0, 3.0), (0.0, 2.0, 2.0), lens=30)
    cam.data.clip_end = 500.0
    cache = os.path.join(DIR, 'cache')
    fire = EXAMPLES['bonfire'].make(look='lit', cells=110, cache_dir=cache, name='reopen_bonfire', build=False,
                                    location=(-2.0, 0.0, 0.0))
    fire.bake(1, 4, time_offset=1.0, time_scale=6.0, log=None)
    light_from_emission(fire, log=None)
    nuke = NX.apply_to(sc, cam, {'origin': [3, 0, -12], 'scale': 0.35, 'timeOffset': 4.0}, cache_dir=cache,
                       quality='fast', name='reopen_nuke', lights=2)
    sc.render.fps = 4                       # 1 s a frame: the cloud visibly grows over the four frames
    nuke.bake(1, 4, log=None)
    nuke.key_opacity(1, 0.3)
    nuke.key_opacity(4, 1.0)
    fit_volume_range(sc, cam, [fire] + nuke.volumes, frames=range(1, 5))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    for f in (2, 4):
        render_frame(f, 'session')
    print(f'[reopen] saved {BLEND}', flush=True)
    V.check('build: the .blend saved and the session frames rendered', os.path.exists(BLEND)
            and all(os.path.exists(os.path.join(DIR, f'reopen_session_f{f:02d}.png')) for f in (2, 4)), BLEND)
else:
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    outs = [render_frame(f, 'fresh') for f in (2, 4)]
    diffs = []
    for f, p in zip((2, 4), outs):
        a = V.read_png(p)
        b = V.read_png(os.path.join(DIR, f'reopen_session_f{f:02d}.png'))
        d = float(np.abs(a - b).mean())
        diffs.append(d)
        V.check(f'open: frame {f} from the file alone matches the session', d < 0.004, f'mean |diff| {d:.5f}')
    a2, a4 = V.read_png(outs[0]), V.read_png(outs[1])
    V.check('open: the file plays (frames 2 and 4 differ)', float(np.abs(a2 - a4).mean()) > 0.002,
            f'mean |frame 4 - frame 2| {float(np.abs(a2 - a4).mean()):.4f}')
    V.sheet([os.path.join(DIR, f'reopen_session_f{f:02d}.png') for f in (2, 4)] + outs,
            os.path.join(DIR, 'reopen_sheet.png'), cols=2)
V.summary()
