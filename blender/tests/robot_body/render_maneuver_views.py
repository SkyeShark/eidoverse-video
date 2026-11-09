"""Stills of a keyed maneuvers.blend (test_body_maneuvers.py's) from views the test's follow camera cannot take: the
ladder seen from the step's side (the tower hides the climber from the front-right), and each move's contact up close.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/render_maneuver_views.py
Stills: out/maneuvers_view_<move>_f<k>.png
"""

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.open_mainfile(filepath=os.path.join(S.OUT, 'maneuvers.blend'))
sc = bpy.context.scene
rep = json.load(open(os.path.join(S.OUT, 'maneuvers.json'), encoding='utf-8'))
arm = next(o for o in sc.objects if o.type == 'ARMATURE')
cam = S.C.camera('view', 45.0)
moves = rep['moves']


def root_at(f):
    sc.frame_set(f)
    return arm.matrix_world.translation.copy()


shots = {}
# the ladder from the step's side, level with the climber's chest; the vault and the mount from the side, low
for name, off in (('climb_ladder', Vector((-2.6, -2.2, 0.4))), ('vault', Vector((0.4, -3.4, 0.2))),
                  ('climb_ledge', Vector((-0.6, -3.2, 0.3)))):
    if name not in moves:
        continue
    fa, fb = moves[name]['film_frames']
    n = 5
    for k in range(n):
        f = fa + 8 + int(round(k * (fb - fa - 16) / (n - 1)))
        p = root_at(f) + Vector((0.0, 0.0, 0.9))
        S.C.aim(cam, p + off, p)
        path = os.path.join(S.OUT, f'maneuvers_view_{name}_f{f:03d}.png')
        shots[os.path.basename(path)] = S.C.still(sc, cam, f, path)
print('[maneuver_views]', json.dumps(shots), flush=True)
