"""A water_compute pool baked and saved, for test_reopen_saved_blend.py (the EXR heights played by Geometry Nodes).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/water3d/probe_water_compute_saved.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
    ... then test_reopen_saved_blend.py -- blend=<worktree>/blender/tests/water3d/out/verify/wc_saved.blend
        frames=12,20 tag=wc "ref=<worktree>/blender/tests/water3d/out/verify/wc_saved_f{f}.png"

A 1 m round pool (width 64, circular), a drop at frame 4 and another at frame 10, baked over 24 frames into
out/verify/wc_cache; frames 12 and 20 rendered to out/verify/wc_saved_f####.png; the file saved as wc_saved.blend.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _scene as S  # noqa: E402
from eidoblend.fx.water_flat import create_water_compute  # noqa: E402

OUT = os.path.join(S.OUT, 'verify')
os.makedirs(OUT, exist_ok=True)
sc = S.fresh_scene(res=(640, 360), fps=24, end=24, samples=16)
S.world_panorama(sc, os.path.join(S.HERE, '..', '..', '..', 'eidoverse', 'assets', 'sky',
                                  'kloppenheim_puresky_ldr.png'), strength=1.0)
S.sun(sc, 'sun', azimuth_deg=-40, elevation_deg=40, strength=3.0)
S.box(sc, 'floor', (3, 3, 0.1), (0, 0, -0.05), S.principled('floor', 0x6a6f74, rough=0.6))
pool = create_water_compute(width=64, bounds=1.0, circular=True, location=(0, 0, 0.05), color=0x2266aa,
                            max_height=0.05)


def controls(frame, t, w):
    if frame in (4, 10):
        w.disturb(0.12 if frame == 4 else -0.15, 0.05, 0.06, 0.01)


pool.bake(1, 24, controls=controls, cache_dir=os.path.join(OUT, 'wc_cache'))
S.camera_look(sc, (0.9, -1.1, 0.9), (0, 0, 0.05), lens=35)
for f in (12, 20):
    S.render(sc, f, os.path.join(OUT, f'wc_saved_f{f:04d}.png'))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'wc_saved.blend'))
