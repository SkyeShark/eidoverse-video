"""Cloud shadows on high ground: a plateau at 300 m, seen from 380 m up with the sun behind the camera.

The caster now sits just under the lowest cloud base (630 m under cumulus), so a receiver at 300 m is under
it and gets its cloud shadow; with the old fixed 150 m caster (shadow_height=150) the plateau is above the
plane and receives none. Prints the spread of the plateau's brightness (cloud-shadow patches = a wide spread)
and renders both for looking.

    bash run_blender.sh blender/tests/sky/probe_caster_height.py      (renders: through the GPU slot)
Writes blender/tests/sky/out/caster_height/.
"""
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky  # noqa: E402

OUT = os.path.join(HERE, 'out', 'caster_height')
os.makedirs(OUT, exist_ok=True)
PLATEAU_Z = 300.0
spreads = {}
for tag, height in (('auto', None), ('fixed150', 150.0)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 480, 270, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 16
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.frame_start = sc.frame_end = 1
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    me = bpy.data.meshes.new('plateau')
    me.from_pydata([(-5000, -5000, PLATEAU_Z), (5000, -5000, PLATEAU_Z), (5000, 5000, PLATEAU_Z),
                    (-5000, 5000, PLATEAU_Z)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new('ground')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.16, 0.20, 0.10, 1)
    b.inputs['Roughness'].default_value = 0.9
    me.materials.append(m)
    sc.collection.objects.link(bpy.data.objects.new('plateau', me))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 24.0
    cam.data.clip_end = 20000.0
    sc.collection.objects.link(cam)
    sc.camera = cam
    sky = make_sky(sc, camera=cam, hours=16.5, clouds='cumulus', shadow_height=height,
                   cache_dir=os.path.join(OUT, '_cache_' + tag))
    sd = sky.sun_dir
    yaw = math.degrees(math.atan2(-sd[0], sd[1])) + 180.0 - 25.0          # sun behind, a little to the right
    cam.location = (0.0, 0.0, PLATEAU_Z + 80.0)
    cam.rotation_euler = (math.radians(90 - 16.0), 0.0, math.radians(yaw))
    sky.bake(log=print)
    caster = bpy.data.objects['eido_sky_cloud_shadow_caster']
    sc.render.filepath = os.path.join(OUT, 'plateau300_%s.png' % tag)
    bpy.ops.render.render(write_still=True)
    import OpenImageIO as oiio
    rgb = np.asarray(oiio.ImageBuf(sc.render.filepath).get_pixels(oiio.FLOAT))[..., :3]     # row 0 = top
    land = (rgb @ np.array([0.2126, 0.7152, 0.0722]))[120:265, 20:460] * 255.0      # the plateau, below the horizon
    spreads[tag] = (float(np.percentile(land, 95) - np.percentile(land, 5)), caster.location.z)
    print('[caster] %-8s caster z %.0f m  plateau brightness p5..p95 spread %.1f levels'
          % (tag, caster.location.z, spreads[tag][0]))
if len(spreads) == 2:
    ok = spreads['auto'][0] > 2.0 * spreads['fixed150'][0]
    print(('PASS' if ok else 'FAIL') + ' the plateau at 300 m gets cloud shadows with the caster under the cloud base '
          '(spread %.1f vs %.1f with the old 150 m plane)' % (spreads['auto'][0], spreads['fixed150'][0]))
