"""Close on the road under a street lamp as rain wets it: dry, wet sheen, puddles filling, rings and splashes.

    bash run_blender.sh blender/tests/weather/probe_puddles.py [--res 960x540 --samples 16]

The camera stands 1.1 m over the right lane looking down the street at about 18 degrees, a lamp ahead. 'rain' from
t = 0 at 18:30 (dusk, lamps on). Frames at 1 s (barely damp), 8 s (thin wetness, no pools), 40 s and 90 s
(puddles filled, rain rippling them), then 'clear' from 90 s and a frame at 180 s (rain stopped: the sheen dries
first, the puddles outlast it). Writes out/puddles/*.png and a sheet; checks the moisture history's order (wetness
before water, water outlasting the rain) at the camera.
"""
import argparse
import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.weather import make_weather_system  # noqa: E402
from street_set import build_street  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--exposure', type=float, default=0.6)
ap.add_argument('--dry', action='store_true', help='plan, key and check only: no sky bake, no render (no GPU)')
args = ap.parse_args(argv)
DRY = args.dry
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'puddles')
os.makedirs(OUT, exist_ok=True)
FPS = 10                      # dt 0.1 s, the JS motion clamp; the moisture history is analytic between refreshes
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.fps = FPS
shots = dict(damp_1s=1.0, wet_8s=8.0, pooling_40s=40.0, pooled_90s=90.0, after_rain_180s=180.0)
F_END = int(max(shots.values()) * FPS) + 1
sc.frame_start, sc.frame_end = 1, F_END
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = args.exposure
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
S = build_street(sc, rooms=not DRY)
cam = S['camera']
cam.location = (1.6, 22.0, 1.1)
cam.rotation_euler = (math.radians(72.0), 0, math.radians(-6.0))
cam.data.lens = 35
sky = make_sky(sc, camera=cam, hours=18.5, weather='rain', cache_dir=os.path.join(OUT, 'cache'), quality='film',
               weather_fx=False)
sky.use_fog(density=0.0012)
sky.set_weather('clear', 1.0, at=90.0)
wx = make_weather_system(sc, sky, occluders=S['collection'], strike_targets=None)
wx.wrap_scene()
wx.plan(F_END, write_from=F_END + 1)            # state only first: where the history stands at each shot
mm = {}
for name, t in shots.items():
    f = int(round(t * FPS)) + 1
    mm[name] = tuple(wx._rows[f]['moisture_at_camera'])
print('[puddles] moisture under the camera (wet, water) at the shots:',
      {k: tuple(round(x, 3) for x in v) for k, v in mm.items()}, flush=True)
check('thin wetness arrives before pooled water (8 s)', mm['wet_8s'][0] > 3 * mm['wet_8s'][1])
check('water keeps rising while it rains (40 s -> 90 s)', mm['pooled_90s'][1] > mm['pooling_40s'][1])
check('after the rain the sheen dries faster than the puddles (180 s)',
      mm['after_rain_180s'][0] / mm['pooled_90s'][0] < mm['after_rain_180s'][1] / mm['pooled_90s'][1])
paths = []
for name, t in shots.items():
    f = int(round(t * FPS)) + 1
    t0 = time.time()
    wx.bake(frame_start=f, frame_end=f, bake_sky=not DRY)
    sc.frame_set(f)
    p = os.path.join(OUT, '%s_f%04d.png' % (name, f))
    sc.render.filepath = p
    if DRY:
        continue
    bpy.ops.render.render(write_still=True)
    paths.append((name, p))
    print('[puddles] %s rendered (%.1fs)' % (name, time.time() - t0), flush=True)
if paths:
    from PIL import Image, ImageDraw  # noqa: E402
    hw, hh = W // 2, H // 2
    sheet = Image.new('RGB', (hw * 2, hh * ((len(paths) + 1) // 2)))
    for i, (name, p) in enumerate(paths):
        im = Image.open(p).convert('RGB').resize((hw, hh), Image.LANCZOS)
        ImageDraw.Draw(im).text((8, 6), name, fill=(255, 255, 255))
        sheet.paste(im, ((i % 2) * hw, (i // 2) * hh))
    sheet.save(os.path.join(OUT, 'puddles_sheet.png'))
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
