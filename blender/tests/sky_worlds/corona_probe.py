"""The sun corona: a camera-facing card of light-petals parked along the TRUE sun, keyed over a short day.

Bakes an Earth morning (the sun ~10 degrees up), adds make_sun_corona and keys it with corona.bake(sky), then
renders the sun with the petals open and with them folded (open = 0.15), and a frame where a ridge stands in front
of the sun (the depth test lets nearer geometry occlude the card). Checks the card sits `distance` along the sun from
the camera, faces it, and that the petals add light around the sun only when open.

    bash run_blender.sh blender/tests/sky_worlds/corona_probe.py [--res 960x540]
Writes out/corona/*.png.
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky.sun_corona import make_sun_corona  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'corona')
os.makedirs(OUT, exist_ok=True)
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W, H = (int(v) for v in args.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = 0.6
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 3
sc.render.image_settings.file_format = 'PNG'
g = bpy.data.materials.new('ground')
g.use_nodes = True
g.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.1, 0.12, 0.07, 1)
bpy.ops.mesh.primitive_plane_add(size=6000)
bpy.context.object.data.materials.append(g)
cd = bpy.data.cameras.new('cam')
cd.lens_unit = 'FOV'
cd.angle = math.radians(50)
cd.clip_end = 5000.0                 # the ground runs 3 km out; the corona raises it for its own card as needed
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (0, 0, 2)
sky = make_sky(sc, camera=cam, world='earth', hours=7.2, clouds='clear', cache_dir=os.path.join(OUT, 'cache'),
               quality='draft', shadows=False)
sky.update(0.0)
sd = Vector(sky.sun_dir)
yaw = math.atan2(sd.x, sd.y)
pitch = math.asin(sd.z)
cam.rotation_euler = (math.pi / 2 + pitch, 0.0, -yaw)
# a ridge 900 m out, square to the view, whose crest sits on the sun's centre line: on frame 3 it hides the lower
# half of the card (it rises from under the ground between frames 2 and 3)
bpy.ops.mesh.primitive_cube_add(size=1)
ridge = bpy.context.object
ridge.data.materials.append(g)
far = Vector((0, 0, 2)) + sd * 900
height = far.z + 60.0
ridge.scale = (900, 60, height)
ridge.rotation_euler = (0.0, 0.0, -yaw)
ridge.location = (far.x, far.y, far.z - height / 2 - 3000)
ridge.keyframe_insert('location', frame=2)
ridge.location = (far.x, far.y, far.z - height / 2)
ridge.keyframe_insert('location', frame=3)
sky.bake(log=lambda *a: None)
corona = make_sun_corona(sc, petals=12, size=400)
opens = {1: 1.0, 2: 0.15, 3: 1.0}
corona.bake(sky, open_fn=lambda t, s: opens[int(round(t * 24)) + 1])
sc.frame_set(1)
d = (corona.mesh.matrix_world.translation - cam.matrix_world.translation)
check('corona sits `distance` along the true sun', abs(d.length - 1500) < 1.0 and d.normalized().dot(sd) > 0.9999,
      'distance %.2f, cos %.6f' % (d.length, d.normalized().dot(sd)))
fz = corona.mesh.matrix_world.to_3x3() @ Vector((0, 0, 1))
check('corona card faces the camera', fz.dot(cam.matrix_world.to_3x3() @ Vector((0, 0, 1))) > 0.9999)


def render(frame, name):
    sc.frame_set(frame)
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    bpy.data.images.remove(img)
    return px


open_ = render(1, 'corona_open')
shut = render(2, 'corona_folded')
behind = render(3, 'corona_behind_ridge')
cy, cx = H // 2, W // 2
ring = np.zeros_like(open_, bool)
yy, xx = np.mgrid[0:H, 0:W]
rr = np.hypot(yy - cy, xx - cx)
# the card is 400 m at 1500 m: ~15 degrees across; the petals live between ~0.2 and ~0.9 of its half width
half_px = (200.0 / 1500.0) / math.tan(math.radians(25)) * (W / 2)
petal_zone = (rr > half_px * 0.3) & (rr < half_px * 0.85)
gain = open_[petal_zone].mean() - shut[petal_zone].mean()
check('open petals add light around the sun', gain > 0.01, 'petal-zone luma open %.3f folded %.3f'
      % (open_[petal_zone].mean(), shut[petal_zone].mean()))
lower = petal_zone & (yy < cy)       # image rows run bottom-up in Blender pixels: lower half of the frame
check('the ridge in front occludes the card (depth test)', behind[lower].mean() < open_[lower].mean() - 0.01,
      'lower-half luma %.3f behind the ridge vs %.3f open' % (behind[lower].mean(), open_[lower].mean()))


# ---- the options: distance, size, petals, color (a second corona; the first is hidden) ----
def petal_count(lum, zone):
    """The dominant angular frequency of the luma in the petal zone: the number of petals."""
    ang = np.arctan2(yy - cy, xx - cx)[zone]
    bins = np.clip(((ang + math.pi) / (2 * math.pi) * 96).astype(int), 0, 95)
    prof = np.bincount(bins, lum[zone], 96) / np.maximum(np.bincount(bins, None, 96), 1)
    spec = np.abs(np.fft.rfft(prof - prof.mean()))
    return int(np.argmax(spec[1:]) + 1)


def render_rgb(frame, name):
    sc.frame_set(frame)
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return px


corona.mesh.hide_render = True
c2 = make_sun_corona(sc, distance=900.0, size=250.0, petals=6, color=(0.40, 0.70, 1.0))
c2.bake(sky, open_fn=lambda t, s: 1.0)
sc.frame_set(1)
d2 = c2.mesh.matrix_world.translation - cam.matrix_world.translation
check('distance= and size= place and size the card', abs(d2.length - 900.0) < 1.0
      and abs(max(c2.mesh.dimensions) - 250.0) < 0.5, 'distance %.2f, card %.1f m' % (d2.length, max(c2.mesh.dimensions)))
rgb2 = render_rgb(1, 'corona_options_6_petals_blue')
half2 = (125.0 / 900.0) / math.tan(math.radians(25)) * (W / 2)
zone2 = (rr > half2 * 0.35) & (rr < half2 * 0.8)
n12 = petal_count(open_, petal_zone)
n6 = petal_count(rgb2 @ np.array([0.2126, 0.7152, 0.0722]), zone2)
check('petals= sets the petal count (12 by default, 6 asked)', n12 == 12 and n6 == 6, 'counted %d and %d' % (n12, n6))
c2.mesh.hide_render = True
sky_only = render_rgb(1, 'corona_options_hidden')                 # the same frame without the card: the sky alone
petal_rgb = (rgb2 - sky_only)[zone2].mean(0)
check('color= tints the petals (a blue corona over the morning sky)', petal_rgb[2] > petal_rgb[0],
      'petal light over the sky: rgb (%.4f, %.4f, %.4f)' % tuple(float(c) for c in petal_rgb))
print('PASS corona all' if ok_all else 'FAIL corona some')
