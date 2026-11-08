"""t_close.py: the daisy dusk close, keyframed (set_close(v, frame)), and frame purity of the saved .blend.
Builds a daisy patch with close keyed 0 at frame 1 -> 1 at frame 49, renders frames 1, 25, 49 (open, half, shut),
saves out/close.blend, then reopens it and renders frame 25 again after jumping straight to it and after stepping
1 -> 25 -> 49 -> 25, and compares the pixels with the first frame-25 render (frame-pure: the same frame renders the
same whatever happened before; nothing depends on a handler or on evaluation history).
    bash run_blender.sh blender/tests/flora/t_close.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402


def build():
    S.new_scene(samples=16)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 49
    S.lights(sun_elev_deg=14, sun_az_deg=-20, strength=3.0, sky_strength=0.6, gradient=True)
    S.ground()
    reset_flora_occupancy()
    create_flora('grass', size=8, seed=3, height=0.3, blades='fine', normals='true', density=0.6)
    fields = [create_flora('daisy', size=4, seed=5, center=(0.0, 0.6), density=0.8, color={'white': 2, 'orange': 1}),
              create_flora('daisy', placements=[(0.05, -0.15, 1.2)], seed=4, head_scale=1.3, heading=-1.9, color='white')]
    for f in fields:
        f.set_close(0.0, frame=1)
        f.set_close(1.0, frame=49)
    S.camera((0.55, -0.95, 0.42), (0.0, 0.1, 0.33), 45)


def load(path):
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], np.float32)
    bpy.data.images.remove(img)
    return px


build()
for f in (1, 25, 49):
    S.render(os.path.join(S.OUT, f'close_f{f}.png'), f)
blend = os.path.join(S.OUT, 'close.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend)
if '--no-render' not in S.args():
    ref = load(os.path.join(S.OUT, 'close_f25.png'))
    bpy.ops.wm.open_mainfile(filepath=blend)
    S.render(os.path.join(S.OUT, 'close_pure_jump_f25.png'), 25)
    for f in (1, 25, 49):
        bpy.context.scene.frame_set(f)
    S.render(os.path.join(S.OUT, 'close_pure_steps_f25.png'), 25)
    for tag in ('jump', 'steps'):
        a = load(os.path.join(S.OUT, f'close_pure_{tag}_f25.png'))
        d = np.abs(a - ref)
        print(f'[close] frame 25 reopened ({tag}) vs first render: max |diff| {d.max() * 255:.2f} / 255, mean {d.mean() * 255:.4f}')
print('[close] done')
