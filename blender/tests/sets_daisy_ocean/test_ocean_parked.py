"""The set parked anywhere (ctx['matrix']): built once at the world origin and once moved 120 m and turned 35 degrees,
her mark, the cameras (and their keys), the moon and the sea's moon uniform must move with it, and her daisies (the
flora field lives in world space, planted through the set's matrix) must stand round the parked mark. No render.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_ocean_parked.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from eidoblend.flora import reset_flora_occupancy  # noqa: E402
from eidoblend.sets.daisy import ocean  # noqa: E402

ck = C.Checks('parked')
sc = bpy.context.scene
sc.render.fps = 24
PARTS = ('daisies', 'sea', 'lights', 'pages', 'world')
M = Matrix.Translation((120.0, -45.0, 3.5)) @ Matrix.Rotation(math.radians(35.0), 4, 'Z')


def build(matrix, name):
    reset_flora_occupancy()
    cam = bpy.data.objects.new(f'cam_{name}', bpy.data.cameras.new(f'cam_{name}'))
    sc.collection.objects.link(cam)
    O = ocean.build({'scene': sc, 'parts': PARTS, 'matrix': matrix, 'name': f'set_ocean_{name}'})
    O.key_verse(frame_start=1, fps=24, u0=0.0, u1=6.0, camera_obj=cam, log=lambda *a: None)
    return O, cam


O0, cam0 = build(None, 'origin')
O1, cam1 = build(M, 'parked')
bpy.context.view_layer.update()
g0, g1 = O0.group.matrix_world, O1.group.matrix_world
ck.check('the set root takes the matrix', (g1 - M).is_identity is False and all(abs(a - b) < 1e-5 for ra, rb in zip(g1, M) for a, b in zip(ra, rb)))
d = (g1 @ Vector(O1.mark) - M @ (g0 @ Vector(O0.mark))).length
ck.check('her mark moves with the set', d < 1e-5, f'{d * 1000:.4f} mm')
worst = 0.0
for u in (0.5, 4.2, 9.0, 12.5, 16.0, 20.0, 25.0, 29.0, 32.0):
    c0, c1 = O0.camera(u), O1.camera(u)
    worst = max(worst, (g1 @ Vector(c1['pos']) - M @ (g0 @ Vector(c0['pos']))).length,
                (g1 @ Vector(c1['target']) - M @ (g0 @ Vector(c0['target']))).length)
ck.check('camera(u) moves with the set (pos and target, every shot)', worst < 1e-4, f'{worst * 1000:.4f} mm')
kd, ka = 0.0, 0.0
for f in (1, 30, 60, 100, 140):
    sc.frame_set(f)
    a, b = cam0.matrix_world, cam1.matrix_world
    kd = max(kd, ((M @ a).translation - b.translation).length)
    ka = max(ka, math.degrees((M.to_3x3() @ a.to_3x3()).to_quaternion().rotation_difference(b.to_3x3().to_quaternion()).angle))
ck.check('the keyed camera moves and turns with the set', kd < 1e-4 and ka < 1e-3, f'{kd * 1000:.4f} mm, {ka:.5f} deg')
m0, m1 = Vector(O0.moon), Vector(O1.moon)
a = math.degrees((M.to_3x3() @ m0).angle(m1))
ck.check("the moon turns with the set (the set's own moon, the sea's moonW)", a < 1e-3 and (Vector(O1.sea.get('moonW')) - m1).length < 1e-6,
         f'{a:.5f} deg')
lamp0, lamp1 = O0.lights['moon'].matrix_world.to_3x3(), O1.lights['moon'].matrix_world.to_3x3()
a = math.degrees((M.to_3x3() @ (lamp0 @ Vector((0, 0, -1)))).angle(lamp1 @ Vector((0, 0, -1))))
ck.check('the moon lamp shines from the turned moon', a < 1e-3, f'{a:.5f} deg')
# her daisies: the field's plant roots, in the parked set's design frame
fld = O1.land.daisies.group
pts = np.zeros(len(fld.data.vertices) * 3, np.float32)
fld.data.vertices.foreach_get('co', pts)
pts = pts.reshape(-1, 3)
W = np.array(fld.matrix_world)
pw = pts @ W[:3, :3].T + W[:3, 3]
inv = np.array(O1.layout.matrix_world.inverted())
pl = pw @ inv[:3, :3].T + inv[:3, 3]                                 # the layout's frame: Blender design axes
x3, z3 = pl[:, 0], -pl[:, 1]
inside = (np.abs(x3 - 0.25) <= 2.6 + 1e-3) & (np.abs(z3 - 0.5) <= 2.3 + 1e-3)
gz = O1.coast.height_3(x3, z3)
ck.check('her daisies stand round the parked mark (inside daisies.js\'s 5.2 x 4.6 m)', len(pts) > 50 and inside.all(),
         f'{len(pts)} plants, {int((~inside).sum())} outside')
ck.check('and on the parked ground (coast height)', np.abs(pl[:, 2] - gz).max() < 0.01, f'max {np.abs(pl[:, 2] - gz).max() * 1000:.2f} mm')
ck.summary()
with open(os.path.join(C.OUT, 'test_ocean_parked.json'), 'w') as fh:
    json.dump(ck.rows, fh, indent=1)
