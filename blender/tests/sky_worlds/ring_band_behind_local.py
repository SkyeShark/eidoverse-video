"""The ringworld's band behind every LOCAL object, as WebGPU draws it: a large terrain with mesas 1.5-4 km out.

WebGPU draws the band without depth before every local opaque (sky_worlds.js: "foreground opaques draw later,
painting over the depthless band"; Eanpa composites the band's private depth layer behind local geometry). At its
authored placement the band meets an eye-level view about 875 m out along the ring, so in one depth buffer a terrain
reaching past that, inside a 60 degree wedge each way along the ring, would lie behind the band. Sky.bake renders the
band as a plate into the sky's camera layer (Ringworld.make_plate), so the terrain and the mesas draw in front of it.

    bash run_blender.sh blender/tests/sky_worlds/ring_band_behind_local.py [--res 960x540] [--samples 16] [--hours 10.5]

Renders the horizon with the band and with the ring's plate emptied (the same sky without the band); at each mesa
the two must agree (the mesa is in front), and over the open band above the mesas they must differ (the band is
there). Also checks that a plate re-render (bake_plates) reproduces the bake's frame and that use_fog leaves the band
unfogged, as WebGPU's ring materials take no scene fog. Writes out/band_behind_local/*.png.
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--hours', type=float, default=10.5)
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'band_behind_local')
os.makedirs(OUT, exist_ok=True)
W, H = (int(v) for v in args.res.split('x'))
ok_all = True
# (x, y, half width, height): three inside the band's strip (|x| < 483 m) along +Y, two outside it
MESAS = ((0, 2000, 260, 260), (-280, 3000, 300, 420), (330, 1500, 150, 140), (-1500, 2500, 400, 380),
         (1300, 3800, 450, 520))


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)
    return ok


def material(name, color, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    return m


def render(sc, name):
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    return px


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = args.samples
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = 0.6
sc.frame_start = sc.frame_end = 1
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
bpy.ops.mesh.primitive_plane_add(size=12000, location=(0, 0, 0))
bpy.context.object.data.materials.append(material('desert', (0.42, 0.30, 0.19), 0.9))
rock = material('mesa', (0.36, 0.22, 0.13), 0.85)
for i, (x, y, hw, h) in enumerate(MESAS):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, h / 2))
    ob = bpy.context.object
    ob.name = 'mesa_%d' % i
    ob.scale = (hw * 2, hw * 1.4, h)
    ob.data.materials.append(rock)
cd = bpy.data.cameras.new('cam')
cd.lens_unit = 'FOV'
cd.angle = math.radians(70)
cd.clip_start, cd.clip_end = 0.1, 20000.0
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (0, 0, 2.0)
cam.rotation_euler = (math.radians(95), 0, 0)
sky = make_sky(sc, camera=cam, world='ringworld', hours=args.hours, clouds='cumulus', cache_dir=os.path.join(OUT, 'cache'),
               quality='film')
ring = sky.ring
check('the band, its walls, its cloud sheet and its lamps render in the plate scene, not the main scene',
      all(o.name not in sc.objects and o.name in ring.plate_scene.objects
          for o in (ring.band, ring.walls, ring.clouds, ring.band_sun, ring.band_shine)),
      'plate scene %s' % ring.plate_scene.name)
check('the eclipse proxy shadows both scenes, the haze walls stay local',
      ring.eclipse_proxy.name in sc.objects and ring.eclipse_proxy.name in ring.plate_scene.objects
      and ring.fog_wall.name in sc.objects and ring.fog_wall.name not in ring.plate_scene.objects)
sky.bake(log=lambda *a: None)
with_band = render(sc, 'band')
# the same sky without the band: empty the plate (hide its elements) and composite again
for ob in (ring.band, ring.walls, ring.clouds):
    ob.hide_render = True
sky.bake_plates(log=lambda *a: None)
no_band = render(sc, 'band_hidden')
for ob in (ring.band, ring.walls, ring.clouds):
    ob.hide_render = False
sky.bake_plates(log=lambda *a: None)
again = render(sc, 'band_replated')
dr = np.abs(again - with_band).mean() * 255
check('bake_plates reproduces the bake\'s frame', dr < 0.5, 'mean |delta| %.3f/255' % dr)

from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402
lum = lambda a: a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
la, lb = lum(with_band), lum(no_band)
for i, (x, y, hw, h) in enumerate(MESAS):
    p = world_to_camera_view(sc, cam, Vector((x, y, h * 0.6)))
    px, py = int(p.x * W), int((1 - p.y) * H)
    if not (2 <= px < W - 2 and 2 <= py < H - 2):
        continue
    d = abs(float(la[py - 2:py + 3, px - 2:px + 3].mean() - lb[py - 2:py + 3, px - 2:px + 3].mean()))
    inside = abs(x) < 483
    check('mesa %d (%d, %d) m, %d m tall%s draws in front of the band' % (i, x, y, h, ', inside the strip,' if inside
                                                                        else ''), d < 0.02,
          'luma with band %.3f, without %.3f' % (la[py - 2:py + 3, px - 2:px + 3].mean(),
                                                 lb[py - 2:py + 3, px - 2:px + 3].mean()))
# the band itself is there: above the mesas, along the ring, the frame changes with it
p = world_to_camera_view(sc, cam, Vector((0, 4000, 1300)))
px, py = int(p.x * W), int((1 - p.y) * H)
d = abs(float(la[py - 3:py + 4, px - 3:px + 4].mean() - lb[py - 3:py + 4, px - 3:px + 4].mean()))
check('the band shows above the mesas', d > 0.03, 'luma with band %.3f, without %.3f'
      % (la[py - 3:py + 4, px - 3:px + 4].mean(), lb[py - 3:py + 4, px - 3:px + 4].mean()))
# fog: three's FogExp2 on local geometry only; the band, like WebGPU's ring materials (fog: false), stays clear
sky.use_fog(density=0.0004)
sky.bake(log=lambda *a: None)
fogged = render(sc, 'band_fog')
lf = lum(fogged)
d_band = abs(float(lf[py - 3:py + 4, px - 3:px + 4].mean() - la[py - 3:py + 4, px - 3:px + 4].mean()))
m0 = world_to_camera_view(sc, cam, Vector((-1500, 2500, 380 * 0.6)))
mx, my = int(m0.x * W), int((1 - m0.y) * H)
d_mesa = abs(float(lf[my - 2:my + 3, mx - 2:mx + 3].mean() - la[my - 2:my + 3, mx - 2:mx + 3].mean()))
check('use_fog fogs a mesa 2.9 km out and leaves the band clear', d_mesa > 0.02 and d_band < 0.01,
      'mesa luma change %.3f, band %.3f' % (d_mesa, d_band))
sheet = np.concatenate([with_band, no_band, fogged], 1)
img = bpy.data.images.new('sheet', sheet.shape[1], sheet.shape[0], alpha=False)
img.pixels[:] = np.concatenate([sheet[::-1], np.ones(sheet.shape[:2] + (1,), np.float32)], 2).ravel()
img.filepath_raw = os.path.join(OUT, 'sheet_band_hidden_fog.png')
img.file_format = 'PNG'
img.save()
print('PASS ring_band_behind_local all' if ok_all else 'FAIL ring_band_behind_local some')
