"""Is the world's camera-layer lookup pixel-aligned? World-only EEVEE render vs the baked layer itself.

A camera with roll, pitch and lens shift renders an empty scene (world only) to a float EXR; the baked
camera layer is resampled at the same rays in numpy; the script prints the error and the best integer
shift between the two (0, 0 = aligned). EEVEE's pixel filter blurs slightly, so the error is not zero.
The frame's rays come from Blender's own frame corners (any sensor fit, shift, aspect). It also counts the
frame's pixels whose ray falls OUTSIDE the layer window (they would show the softer environment): 0 expected.

    bash run_blender.sh blender/tests/sky/probe_projection.py [--shift 0.08,-0.05] [--roll 9]
        [--res 480x270] [--fit AUTO|HORIZONTAL|VERTICAL] [--tag name]     (portrait: --res 270x480)
"""
import math
import os
import sys

import bpy
import numpy as np
import OpenImageIO as oiio

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
TAG = opt('--tag', '')
OUT = os.path.join(HERE, 'out', 'projection' + (('_' + TAG) if TAG else ''))
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W, H = (int(v) for v in opt('--res', '480x270').split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'OPEN_EXR'
sc.render.image_settings.color_depth = '32'
sc.render.filter_size = 0.5                     # narrow pixel filter: the comparison is about alignment
sc.frame_start = sc.frame_end = 1               # one frame: the layer compared is the layer rendered
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
sc.camera = cam
shift = [float(v) for v in opt('--shift', '0.08,-0.05').split(',')]
roll = float(opt('--roll', '9.0'))
cam.data.lens = 30
cam.data.sensor_fit = opt('--fit', 'AUTO')
cam.data.shift_x, cam.data.shift_y = shift
cam.location = (10.0, -20.0, 1.7)
cam.rotation_euler = (math.radians(90 + 28), math.radians(roll), math.radians(-35))   # pitch, roll, yaw
print('[proj] %dx%d fit %s shift %s roll %.1f' % (W, H, cam.data.sensor_fit, shift, roll))
overscan = 0.08
sky = make_sky(sc, camera=cam, cache_dir=os.path.join(OUT, '_cache'), hours=16.5, clouds='cumulus',
               shadows=False)
frames = sky.bake(overscan=overscan)
sc.render.filepath = os.path.join(OUT, 'world_only.exr')
bpy.ops.render.render(write_still=True)

ren = np.asarray(oiio.ImageBuf(sc.render.filepath).get_pixels(oiio.FLOAT))[::-1, :, :3]   # row 0 = bottom
lay = np.asarray(oiio.ImageBuf(os.path.join(OUT, '_cache', 'sky_cam_0001.exr')).get_pixels(oiio.FLOAT))[::-1, :, :3]
LH, LW = lay.shape[:2]
# the frame's rays from Blender's own frame corners (camera space, one depth), then into the layer window
corners = cam.data.view_frame(scene=sc)
xs = [c.x / -c.z for c in corners]
ys = [c.y / -c.z for c in corners]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
wx, wy = frames[0]['tan']                       # the window the bake used (overscan included)
jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
px = x0 + (ii + 0.5) / W * (x1 - x0)
py = y0 + (jj + 0.5) / H * (y1 - y0)
u = 0.5 + 0.5 * px / wx
v = 0.5 + 0.5 * py / wy
outside = int(((u < 0) | (u > 1) | (v < 0) | (v > 1)).sum())
print('[proj] frame half-tangents x %.4f..%.4f y %.4f..%.4f, layer window (%.4f, %.4f): %d of %d pixels outside'
      % (x0, x1, y0, y1, wx, wy, outside, W * H))
fx, fy = u * LW - 0.5, v * LH - 0.5
x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
ax, ay = (fx - x0)[..., None], (fy - y0)[..., None]
x0, y0 = np.clip(x0, 0, LW - 2), np.clip(y0, 0, LH - 2)
ref = ((lay[y0, x0] * (1 - ax) + lay[y0, x0 + 1] * ax) * (1 - ay)
       + (lay[y0 + 1, x0] * (1 - ax) + lay[y0 + 1, x0 + 1] * ax) * ay)
lum = lambda a: a @ np.array([0.2126, 0.7152, 0.0722])
a, b = lum(ren), lum(ref)
err = np.abs(a - b)
print('[proj] render mean %.4f  layer-at-rays mean %.4f  mean |diff| %.4f (%.2f%%)  p99 %.4f'
      % (a.mean(), b.mean(), err.mean(), 100 * err.mean() / b.mean(), np.percentile(err, 99)))
best = None
for dy in range(-3, 4):
    for dx in range(-3, 4):
        e = np.abs(a[4:-4, 4:-4] - np.roll(np.roll(b, dy, 0), dx, 1)[4:-4, 4:-4]).mean()
        if best is None or e < best[0]:
            best = (e, dx, dy)
print('[proj] best integer shift dx=%d dy=%d (error %.4f)  -> %s'
      % (best[1], best[2], best[0], 'ALIGNED' if best[1] == 0 and best[2] == 0 else 'MISALIGNED'))
# side by side (render | layer at the same rays | |difference| x4), display-mapped, for looking
tm = lambda x: (np.clip(x / (1 + x), 0, 1) ** (1 / 2.2)).astype(np.float32)
diff = np.repeat(np.clip(np.abs(a - b) * 4, 0, 1)[..., None], 3, axis=2).astype(np.float32)
sheet = np.concatenate([tm(ren), tm(ref), diff], axis=1)[::-1]
o = oiio.ImageBuf(oiio.ImageSpec(sheet.shape[1], sheet.shape[0], 3, 'uint8'))
o.set_pixels(oiio.ROI(), np.ascontiguousarray(sheet))
o.write(os.path.join(OUT, 'side_by_side.png'))
