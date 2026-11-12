"""The set parked anywhere (ctx['matrix']): built once at the world origin and once moved 120 m and turned 35 degrees,
the mark and the eye point, a figure stood on the mark, the moon (its lamp and the sea's moon uniform), the fill aimed
at a camera, the porch lamp's glint on the cove, a placed page and its keys must all move with it, and her daisies
(planted in world space through the set's matrix) must stand round the parked mark. Then the origin build is moved and
turned by the same matrix after the build: her daisies come along rigidly and sway as they did, and the porch's and the
window's glints on the cove follow the house with no update() after the move. No render.

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
PARTS = ('daisies', 'sea', 'lights', 'pages', 'house', 'world')
M = Matrix.Translation((120.0, -45.0, 3.5)) @ Matrix.Rotation(math.radians(35.0), 4, 'Z')


def build(matrix, name):
    reset_flora_occupancy()
    O = ocean.build({'scene': sc, 'parts': PARTS, 'matrix': matrix, 'name': f'set_ocean_{name}'})
    g = O.group.matrix_world
    cam = bpy.data.objects.new(f'cam_{name}', bpy.data.cameras.new(f'cam_{name}'))
    sc.collection.objects.link(cam)
    cam.location = g @ Vector(O.to_set((-1.2, O.coast.markY + 1.3, 2.3)))      # the same spot in each set's frame
    fig = bpy.data.objects.new(f'fig_{name}', None)
    sc.collection.objects.link(fig)
    O.stand(fig, facing='house')
    bpy.context.view_layer.update()
    P = g @ Vector(O.to_set((0.5, O.coast.markY + 1.4, 0.4)))
    F = g @ Vector(O.E)
    O.animate({'page_2026': lambda t: {'pos': tuple(P + g.to_3x3() @ Vector((0.0, 0.0, 0.1 * t))), 'face': tuple(F)},
               'camera': cam, 'reveal': lambda t: ocean.ease(t, 0.0, 2.0)}, frames=(1, 49), fps=24)
    return O, cam, fig


O0, cam0, fig0 = build(None, 'origin')
O1, cam1, fig1 = build(M, 'parked')
bpy.context.view_layer.update()
g0, g1 = O0.group.matrix_world, O1.group.matrix_world
ck.check('the set root takes the matrix', all(abs(a - b) < 1e-5 for ra, rb in zip(g1, M) for a, b in zip(ra, rb)))
d = max((g1 @ Vector(O1.mark) - M @ (g0 @ Vector(O0.mark))).length, (g1 @ Vector(O1.E) - M @ (g0 @ Vector(O0.E))).length)
ck.check('the mark and the eye point move with the set', d < 1e-5, f'{d * 1000:.4f} mm')
fa, fb = fig0.matrix_world, fig1.matrix_world
da = ((M @ fa).translation - fb.translation).length
aa = math.degrees((M.to_3x3() @ fa.to_3x3()).to_quaternion().rotation_difference(fb.to_3x3().to_quaternion()).angle)
ck.check('a figure stood on the mark (facing the house) moves and turns with the set', da < 1e-5 and aa < 1e-3,
         f'{da * 1000:.4f} mm, {aa:.5f} deg')
m0, m1 = Vector(O0.moon), Vector(O1.moon)
a = math.degrees((M.to_3x3() @ m0).angle(m1))
ck.check("the moon turns with the set (the set's own moon, the sea's moonW)", a < 1e-3 and (Vector(O1.sea.get('moonW')) - m1).length < 1e-6,
         f'{a:.5f} deg')
lamp0, lamp1 = O0.lights['moon'].matrix_world.to_3x3(), O1.lights['moon'].matrix_world.to_3x3()
a = math.degrees((M.to_3x3() @ (lamp0 @ Vector((0, 0, -1)))).angle(lamp1 @ Vector((0, 0, -1))))
ck.check('the moon lamp shines from the turned moon', a < 1e-3, f'{a:.5f} deg')
kd, kp, ka = 0.0, 0.0, 0.0
for f in (1, 13, 25, 49):
    sc.frame_set(f)
    a0, a1 = O0.lights['fill'].matrix_world, O1.lights['fill'].matrix_world
    kd = max(kd, ((M @ a0).translation - a1.translation).length)
    p0, p1 = O0.pages.p26.holder.matrix_world, O1.pages.p26.holder.matrix_world
    kp = max(kp, ((M @ p0).translation - p1.translation).length)
    ka = max(ka, math.degrees((M.to_3x3() @ p0.to_3x3()).to_quaternion().rotation_difference(p1.to_3x3().to_quaternion()).angle))
ck.check('the keyed fill (aimed at the camera) moves with the set', kd < 1e-4, f'{kd * 1000:.4f} mm')
ck.check('the keyed page moves and turns with the set', kp < 1e-4 and ka < 1e-3, f'{kp * 1000:.4f} mm, {ka:.5f} deg')
pw0, pw1 = Vector(O0.sea.get('porchW')), Vector(O1.sea.get('porchW'))
d = (M @ pw0 - pw1).length
ck.check("the porch lamp's glint on the cove follows the parked house", d < 1e-4 and (pw1 - O1.house.porch_world()).length < 1e-4,
         f'{d * 1000:.4f} mm')
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


# moved and turned AFTER the build: the origin set carried by the same matrix, her daisies with it (the field is in
# the set, as daisies.js's was in ocean.js's group), their sway unchanged (the field sways in its own space)
def daisy_points(O):
    """(the plants' roots in world space, the field's evaluated geometry: every vertex, the field's own space)."""
    f_ = O.land.daisies.group
    r = np.zeros(len(f_.data.vertices) * 3, np.float32)
    f_.data.vertices.foreach_get('co', r)
    Wf = np.array(f_.matrix_world)
    ev = f_.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    g_ = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', g_)
    ev.to_mesh_clear()
    return r.reshape(-1, 3) @ Wf[:3, :3].T + Wf[:3, 3], g_.reshape(-1, 3)


sc.frame_set(25)
bpy.context.view_layer.update()
root0, geo0 = daisy_points(O0)
glints0 = [Vector(O0.sea.get(k)) for k in ('porchW', 'winW')]
O0.group.matrix_world = M @ O0.group.matrix_world
bpy.context.view_layer.update()                     # no update() or animate() after the move: nothing re-synced
root1, geo1 = daisy_points(O0)
glints1 = [Vector(O0.sea.get(k)) for k in ('porchW', 'winW')]
Mn = np.array(M)
d = float(np.abs(root1 - (root0 @ Mn[:3, :3].T + Mn[:3, 3])).max())
ck.check('moved 120 m and turned 35 deg after the build, her daisies come along, rigidly', d < 1e-4, f'{d * 1000:.4f} mm')
ds = float(np.abs(geo1 - geo0).max()) if geo1.shape == geo0.shape else -1.0
ck.check('and sway as they did (the same frame: every vertex of the field in its own space unchanged)',
         geo0.shape == geo1.shape and len(geo0) > 1000 and ds < 1e-5, f'{len(geo0)} vertices, max {ds:.2e} m')
inv = np.array(O0.layout.matrix_world.inverted())
pl = root1 @ inv[:3, :3].T + inv[:3, 3]
x3, z3 = pl[:, 0], -pl[:, 1]
inside = (np.abs(x3 - 0.25) <= 2.6 + 1e-3) & (np.abs(z3 - 0.5) <= 2.3 + 1e-3)
ck.check("they stand round the moved mark (inside daisies.js's 5.2 x 4.6 m) on its ground",
         inside.all() and np.abs(pl[:, 2] - O0.coast.height_3(x3, z3)).max() < 0.01,
         f'{int((~inside).sum())} outside, max {np.abs(pl[:, 2] - O0.coast.height_3(x3, z3)).max() * 1000:.2f} mm')
# the porch lamp's and the window's glints on the cove (the sea's porchW / winW, which ocean.js copied from the house
# on every update): driven by the house's porch and window points, so they follow the move with no update() after it
dg = max((M @ a - b).length for a, b in zip(glints0, glints1))
dh = max((glints1[0] - O0.house.porch_world()).length, (glints1[1] - O0.house.window_world()).length)
ck.check("the porch's and the window's glints on the cove follow the house moved after the build", dg < 1e-4 and dh < 1e-4,
         f'{dg * 1000:.4f} mm from the moved glints, {dh * 1000:.4f} mm from the house')
ck.summary()
with open(os.path.join(C.OUT, 'test_ocean_parked.json'), 'w') as fh:
    json.dump(ck.rows, fh, indent=1)
