"""The iso field port's probe: three metaballs written into the engine's field layout each frame, meshed by
OpenVDB, played back as a PLY sequence by Geometry Nodes, lit by a key light that they shadow onto the floor
(the engine's raymarched surface could not cast shadows).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 \
        bash run_blender.sh <worktree>/blender/tests/fx/test_iso_field.py [-- frames=1,24]
"""

import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx import iso_field as fxiso       # noqa: E402
from eidoblend.fx._util import color               # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
FRAMES = [int(x) for x in args.get('frames', '1,24').split(',')]
OUT = os.path.join(HERE, 'out')

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 960, 540
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 24
sc.eevee.taa_render_samples = 16
sc.eevee.use_raytracing = True
sc.view_settings.view_transform = 'AgX'
world = bpy.data.worlds.new('w')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (*color('#9fb2c8'), 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
sc.world = world
bpy.ops.mesh.primitive_plane_add(size=6)
fm = bpy.data.materials.new('floor')
fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*color('#5c5a55'), 1)
bpy.context.active_object.data.materials.append(fm)
ld = bpy.data.lights.new('key', 'AREA')
ld.energy = 400
ld.size = 0.8
key = bpy.data.objects.new('key', ld)
sc.collection.objects.link(key)
key.location = (-1.6, -1.2, 2.6)
key.rotation_euler = (math.radians(40), math.radians(-30), math.radians(-35))

iso = fxiso.make_iso_field(resolution=64, half=0.5, iso=50, cache_dir=os.path.join(OUT, 'iso_cache'), name='blobs')
r = iso.res
g = np.linspace(0, 1, r)
X, Y, Z = np.meshgrid(g * 2 * iso.half - iso.half, g * 2 * iso.half, g * 2 * iso.half - iso.half, indexing='ij')


def update(frame, t, it):
    f = np.zeros_like(X)
    for k in range(3):
        a = t * 2.0 + k * 2.1
        c = (0.22 * math.cos(a), 0.45 + 0.18 * math.sin(a * 1.3), 0.22 * math.sin(a))   # engine axes, y up
        f += 100.0 * np.exp(-((X - c[0]) ** 2 + (Y - c[1]) ** 2 + (Z - c[2]) ** 2) / (2 * 0.11 ** 2))
    # the engine's layout: idx = x + y*res + z*res^2  ->  [z][y][x]
    it.field[:] = f.transpose(2, 1, 0).ravel().astype(np.float32)


iso.bake(1, 24, update=update)
cd = bpy.data.cameras.new('cam')
cd.lens = 45
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
cam.location = (2.3, -2.6, 1.4)
tgt = bpy.data.objects.new('tgt', None)
sc.collection.objects.link(tgt)
tgt.location = (0, 0, 0.45)
c = cam.constraints.new('TRACK_TO')
c.target = tgt
c.track_axis = 'TRACK_NEGATIVE_Z'
c.up_axis = 'UP_Y'
sc.camera = cam
for f in FRAMES:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f'iso_field_f{f:04d}.png')
    bpy.ops.render.render(write_still=True)
    print('[test_iso] wrote', sc.render.filepath)
print('[test_iso] DONE')
