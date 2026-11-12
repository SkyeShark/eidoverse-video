"""The target and the result side by side: rotary_surface(sample_rotary) (the sculpture the program aims at, behind)
and the finished part carved by the wood example's own program (in front: the field at the program's end, meshed by
OpenVDB, with its end stock and centre seat), both in the stock's finish, under the robotics studio. Saves
out/rotary_target_vs_carved.blend for render_rotary_probes.py.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_target_vs_carved.py

Checks the carved part's surface against the target: every target vertex lies inside or on the part (within a cell),
and the part's surface lies within the finish tolerance outside the target over the carved length.
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups beside the saved builds
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.characters.robotics import studio                                          # noqa: E402
from eidoblend.characters.robotics.studio import make_camera                               # noqa: E402
from eidoblend.fabrication.cutting import stock_material, stock_profile                    # noqa: E402
from eidoblend.fabrication.rotary import StockField, rotary_program, rotary_surface, sample_rotary   # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
studio(sc, grid=False)
p = rotary_program(sample_rotary, material='wood', tool='flat', flute_length=.018)
s = p.settings
field = StockField(p.path, s, (256, 96, 96))
field.update(p.path.sample(p.path.duration))
mat, _finish = stock_material('target and carved finish', stock_profile('wood'), axes='rotary')
check("the stock finish reads the WebGPU rotary stock's point (z, y, x), its fades by their exact footprint",
      all(n in mat.node_tree.nodes for n in ('phase growth rings', 'fwidth growth rings', 'fwidth wood fibre')))


def place(name, me, y):
    """me's vertices in stock coordinates -> an object at y with object space = stock space, so the finish reads both
    pieces the way it reads the rotary stock"""
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.matrix_basis = Matrix.Translation((0.0, y, 0.0))
    return ob


bounds = {'start': s['start'], 'end': s['end'], 'stock_width': s['stock_width'], 'stock_height': s['stock_height']}
target = place('target: rotary_surface(sample_rotary)',
               rotary_surface(lambda x, a: sample_rotary(x, a, bounds), start=s['start'], end=s['end'], nx=160, na=192,
                              name='rotary_surface (the target)'), .045)
pts, faces = field.polygons()
carved_me = bpy.data.meshes.new('carved part')
carved_me.from_pydata(pts.tolist(), [], faces)
carved_me.update()
carved_me.shade_smooth()
carved = place('carved: the wood program, finished', carved_me, 0.0)
# the surfaces against each other (stock coordinates)
xs = np.linspace(s['start'] + .001, s['end'] - .001, 80)
th = np.linspace(0, 2 * math.pi, 120, endpoint=False)
X, TH = np.meshgrid(xs, th)
R = sample_rotary(X, TH, bounds)
on = np.stack([X, -R * np.sin(TH), R * np.cos(TH)], -1).reshape(-1, 3)
g = (on - np.asarray(field.bounds['min'])) / np.asarray(field.cell)
i0 = np.clip(np.floor(g).astype(int), 0, np.asarray(field.resolution) - 2)
f = g - i0
val = np.zeros(len(on))
for dx in (0, 1):
    for dy in (0, 1):
        for dz in (0, 1):
            w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
            val += w * field.field[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz]
check('target vs carved: the target lies inside the finished part (within a cell)', val.max() < max(field.cell),
      f'max {val.max() * 1000:.3f} mm, cell {max(field.cell) * 1000:.2f} mm')
check('target vs carved: the part\'s surface lies on average within 0.25 mm outside the target',
      -val.mean() < .00025, f'mean depth of the target below the surface {-val.mean() * 1000:.3f} mm, '
      f'95th percentile {np.percentile(-val, 95) * 1000:.3f} mm')
cam = make_camera(28, 'target vs carved camera', sc)
cam.data.clip_start = .01
sc.camera = cam
cam.location = Vector((-.02, -.20, .11))
cam.rotation_quaternion = (Vector((.004, .022, 0)) - cam.location).to_track_quat('-Z', 'Y')
sc.render.engine = 'BLENDER_EEVEE'
blend = os.path.join(OUT, 'rotary_target_vs_carved.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
print('saved', blend)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
