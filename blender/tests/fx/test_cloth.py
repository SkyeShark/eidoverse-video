"""The cloth port's probe: the guide's two recipes, a hanging banner (pin 'top', gentle wind, settle 60) and a
streaming flag on a pole (pin 'left', wind 0.0008, windBias 0.9, windDir away from the pole), over a floor,
with a sphere collider the banner drapes over.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 \
        bash run_blender.sh <worktree>/blender/tests/fx/test_cloth.py [-- end=90 frames=1,45,90]

The bake is CPU (numpy, 1120 vertices); writes out/cloth_cache/*.pc2 and out/cloth_f####.png.
"""

import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx import cloth as fxcloth          # noqa: E402
from eidoblend.fx._util import color               # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
END = int(args.get('end', 90))
FRAMES = [int(x) for x in args.get('frames', '1,45,90').split(',')]
OUT = os.path.join(HERE, 'out')

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 960, 540
sc.render.fps = 30
sc.frame_start, sc.frame_end = 1, END
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'AgX'
world = bpy.data.worlds.new('sky')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (*color('#8fa6c0'), 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
sc.world = world
sd = bpy.data.lights.new('sun', 'SUN')
sd.energy = 3.5
sd.angle = math.radians(2)
sun = bpy.data.objects.new('sun', sd)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), 0, math.radians(35))

bpy.ops.mesh.primitive_plane_add(size=20)
fl = bpy.context.active_object
fm = bpy.data.materials.new('floor')
fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*color('#6d6a63'), 1)
fl.data.materials.append(fm)


def fabric(name, hexc):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color(hexc), 1)
    b.inputs['Roughness'].default_value = 0.65
    b.inputs['Sheen Weight'].default_value = 0.5
    m.use_backface_culling = False
    return m


# a hanging banner, 3 x 2 m, top edge at 3.2 m, a ball 0.45 m in front of it at mid height
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(0.4, -0.35, 1.9))
ball = bpy.context.active_object
for p in ball.data.polygons:
    p.use_smooth = True
banner = fxcloth.create_cloth_panel(name='banner', material=fabric('banner_fabric', '#b8323a'),
                                    cache_dir=os.path.join(OUT, 'cloth_cache'), location=(0.0, 0.0, 2.2),
                                    width=3, height=2, cols=40, rows=28, wind=0.0004, wind_bias=0.1, pin='top',
                                    floor=0.0)
banner.collide_with([ball], as_sphere=True)
banner.settle(60)

# a flag on a pole: pinned left edge, streaming along +X
bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=4.0, location=(3.2, 2.5, 2.0))
flag = fxcloth.create_cloth_panel(name='flag', material=fabric('flag_fabric', '#2a5db0'),
                                  cache_dir=os.path.join(OUT, 'cloth_cache'), location=(4.0, 2.5, 3.3),
                                  width=1.6, height=1.0, cols=32, rows=20, wind=0.0008, wind_bias=0.9,
                                  # wind along the flag's own plane alone gives no out-of-plane force and the
                                  # deterministic solver never breaks the symmetry: blow across it a little
                                  wind_dir=(1.0, -0.4, 0.0), pin='left', settle_steps=60)
t0 = time.time()
banner.bake(1, END)
flag.bake(1, END)
print(f'[test_cloth] bake {time.time() - t0:.1f} s')

cd = bpy.data.cameras.new('cam')
cd.lens = 32
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
cam.location = (2.2, -8.5, 2.6)
cam.rotation_euler = (math.radians(86), 0, math.radians(8))
sc.camera = cam
for f in FRAMES:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f'cloth_f{f:04d}.png')
    bpy.ops.render.render(write_still=True)
    print('[test_cloth] wrote', sc.render.filepath)
print('[test_cloth] DONE')
