"""Every stock preset carved: the sample sculpture finished by each material's own rotary program (wood, plywood,
aluminum, brass, steel: their own feeds and depth steps) and laid side by side under the robotics studio, each in the
stock's finish exactly as the rotary stock wears it (the WebGPU (z, y, x) grain swizzle). Saves
out/rotary_materials_lineup.blend for render_rotary_probes.py.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_materials_lineup.py

Checks each finished part against the target (inside it within a cell, cut to it on average) and that the presets'
programs differ as the presets do (metal: more passes, longer physical cutting). Prints PASS / FAIL.
"""

import math
import os
import sys
import time

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
from eidoblend.fabrication.rotary import StockField, rotary_program, sample_rotary                    # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
FAILS = []
MATERIALS = ('wood', 'plywood', 'aluminum', 'brass', 'steel')


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def trilinear(fs, p):
    g = (p - np.asarray(fs.bounds['min'])) / np.asarray(fs.cell)
    i0 = np.clip(np.floor(g).astype(int), 0, np.asarray(fs.resolution) - 2)
    f = g - i0
    val = np.zeros(len(p))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                val += w * fs.field[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz]
    return val


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
studio(sc, grid=False)
programs = {}
for k, name in enumerate(MATERIALS):
    t0 = time.time()
    p = rotary_program(sample_rotary, material=name, tool='flat', flute_length=.018)
    s = p.settings
    field = StockField(p.path, s, (256, 96, 96))
    field.update(p.path.sample(p.path.duration))
    dt = time.time() - t0
    programs[name] = p
    bounds = {'start': s['start'], 'end': s['end'], 'stock_width': s['stock_width'], 'stock_height': s['stock_height']}
    xs = np.linspace(s['start'] + .001, s['end'] - .001, 60)
    th = np.linspace(0, 2 * math.pi, 90, endpoint=False)
    X, TH = np.meshgrid(xs, th)
    R = sample_rotary(X, TH, bounds)
    val = trilinear(field, np.stack([X, -R * np.sin(TH), R * np.cos(TH)], -1).reshape(-1, 3))
    check(f'{name}: {len(p.stages)} stages, {sum(1 for g in p.path.segments if g["type"] == "cut")} cutting strokes, '
          f'{p.path.duration / 3600:.2f} h physical; the finished part holds the target and is cut to it',
          val.max() < max(field.cell) and -val.mean() < .00025,
          f'max {val.max() * 1000:.3f} mm, mean depth {-val.mean() * 1000:.3f} mm (carved in {dt:.1f} s)')
    pts, faces = field.polygons()
    me = bpy.data.meshes.new(f'{name} part')
    me.from_pydata(pts.tolist(), [], faces)
    me.update()
    me.shade_smooth()
    mat, _finish = stock_material(f'{name} stock finish', stock_profile(name), axes='rotary')
    me.materials.append(mat)
    ob = bpy.data.objects.new(f'carved {name}', me)
    sc.collection.objects.link(ob)
    # side by side across Y, the rotary axis along X; each sits on the floor (its lowest corner at z = 0), turned a
    # little about its axis so the lobes catch the light differently
    ob.matrix_basis = Matrix.Translation((0.0, (k - 2) * .052, s['stock_height'] / 2)) @ Matrix.Rotation(.35 * k, 4, 'X')
wood, steel = programs['wood'], programs['steel']
check('the presets differ as cutting rates do: steel takes more stages and far longer than wood',
      len(steel.stages) > len(wood.stages) and steel.path.duration > 5 * wood.path.duration,
      f'{len(wood.stages)} vs {len(steel.stages)} stages, {wood.path.duration / 60:.0f} min vs '
      f'{steel.path.duration / 3600:.1f} h')
cam = make_camera(30, 'materials lineup camera', sc)
cam.data.clip_start = .01
sc.camera = cam
cam.location = Vector((-.20, -.20, .20))
cam.rotation_quaternion = (Vector((.004, -.004, .012)) - cam.location).to_track_quat('-Z', 'Y')
sc.render.engine = 'BLENDER_EEVEE'
blend = os.path.join(OUT, 'rotary_materials_lineup.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
print('saved', blend)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
