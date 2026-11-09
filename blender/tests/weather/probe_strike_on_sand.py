"""A local strike on pale open ground (a desert flat under storm), close up: the impact's sparks, burn puffs, smoke and
scorch where they read against the ground (the test street's dark asphalt hides the scorch).

    bash run_blender.sh blender/tests/weather/probe_strike_on_sand.py [--res 960x540 --samples 16]

A forced strike (debug_force_local_strike) lands 34-58 m ahead of the camera; the camera then stands 9 m from it.
Renders out/verify/strike_on_sand/<moment>.png and strike_on_sand_sheet.png: the strike frame, sparks (0.1 s),
the white-hot burn puffs (0.8 s), grey smoke (3 s) and the scorch alone (20 s, and from above). PASS / FAIL: the
strike is local and lands on the sand; the scorch darkens the sand under it at 20 s; the strike light lights the
sand at the strike and at 0.1 s (over twice its light at 5 s); the puffs are drawn at 0.8 s and gone after their
4.5 s.
"""
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.weather import make_weather_system  # noqa: E402
from eidoblend.weather.keys import key_series  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
args = ap.parse_args(argv)
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'verify', 'strike_on_sand')
os.makedirs(OUT, exist_ok=True)
FPS = 24
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
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = 0.6
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
from eidoblend.look.post import chain  # noqa: E402
chain.set_bloom(sc, strength=0.25, size=0.4, threshold=0.85)

flat = bpy.data.collections.new('desert_flat')
sc.collection.children.link(flat)
sand = bpy.data.materials.new('sand')
sand.use_nodes = True
nt = sand.node_tree
p = nt.nodes['Principled BSDF']
p.inputs['Roughness'].default_value = 0.92
noise = nt.nodes.new('ShaderNodeTexNoise')               # a little grain, so the scorch edge reads against texture
noise.inputs['Scale'].default_value = 3.0
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.40, 0.33, 0.24, 1.0)
ramp.color_ramp.elements[1].color = (0.52, 0.44, 0.33, 1.0)
nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
me = bpy.data.meshes.new('sand')
me.from_pydata([(-400, -400, 0), (400, -400, 0), (400, 400, 0), (-400, 400, 0)], [], [(0, 1, 2, 3)])
me.materials.append(sand)
ground = bpy.data.objects.new('sand', me)
flat.objects.link(ground)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 30.0
cam.location = (0.0, 0.0, 1.7)
cam.rotation_euler = (math.radians(88), 0.0, 0.0)          # looking along +Y

T_END = 40.0
sc.frame_start, sc.frame_end = 1, int(T_END * FPS) + 1
sky = make_sky(sc, camera=cam, hours=15.0, weather='storm', cache_dir=os.path.join(OUT, 'cache'), quality='film')
wx = make_weather_system(sc, sky, strike_targets=[flat], moisture=False, log=lambda *a: None)
wx.wrap_scene()
wx.debug_force_local_strike(at=2.0)
wx.plan(sc.frame_end)
imp = wx.sched.impacts[0] if wx.sched.impacts else None
check('the forced strike is local and lands on the sand', imp is not None and wx.sched.events[0]['strike']['kind'] == 'sand',
      imp and (imp['birth'], imp['point']))
if imp is None:
    print('RESULT FAIL', flush=True)
    sys.exit(0)
p3 = imp['point']
P = (p3[0], -p3[2], p3[1])
fs = int(math.floor(imp['birth'] * FPS)) + 1           # the frame the strike begins on
print('[sand] strike at t=%.3f s (frame %d), %s' % (imp['birth'], fs, P), flush=True)
from mathutils import Vector  # noqa: E402
eye = Vector((P[0] - 6.0, P[1] - 6.5, 1.8))
rot = (Vector((P[0], P[1], 1.2)) - eye).to_track_quat('-Z', 'Y').to_euler()
top = Vector((P[0] + 0.01, P[1] - 2.5, 6.0))
rot_top = (Vector(P) - top).to_track_quat('-Z', 'Y').to_euler()
shots = [('strike', 0.0, eye, rot), ('sparks_0.1s', 0.1, eye, rot), ('burn_puffs_0.8s', 0.8, eye, rot),
         ('sparks_gone_1s', 1.0, eye, rot), ('smoke_3s', 3.0, eye, rot), ('smoke_gone_5s', 5.0, eye, rot),
         ('scorch_20s', 20.0, eye, rot), ('scorch_from_above_20s', 20.0, top, rot_top)]
paths = {}
for name, dt, loc, r in shots:
    t0 = time.time()
    f = fs + int(round(dt * FPS)) + (1 if dt == 0.0 else 0)       # the strike frame: the one after it begins
    key_series(cam, 'location', [1, f], [tuple(cam.location), tuple(loc)], 'CONSTANT')
    key_series(cam, 'rotation_euler', [1, f], [tuple(cam.rotation_euler), tuple(r)], 'CONSTANT')
    wx.bake(frame_start=f, frame_end=f)
    sc.frame_set(f)
    pth = os.path.join(OUT, name + '.png')
    sc.render.filepath = pth
    bpy.ops.render.render(write_still=True)
    paths[name] = pth
    cam.animation_data_clear()
    cam.location, cam.rotation_euler = (0.0, 0.0, 1.7), (math.radians(88), 0.0, 0.0)
    print('[sand] %s: frame %d (%.1fs)' % (name, f, time.time() - t0), flush=True)

from PIL import Image, ImageDraw  # noqa: E402


def lum(name):
    a = np.asarray(Image.open(paths[name]).convert('RGB')).astype(np.float64)
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


# the scorch from above: the impact point sits at the image centre; compare the centre with the top corners (sand 3-5 m
# from the impact, beyond the largest scorch). The char is near black at 62 % opacity, but storm-wet sand is dark
# already (wet darkening under a dimmed sky), so the contrast is modest: the centre under 0.9 of the sand beyond it
L20 = lum('scorch_from_above_20s')
yy, xx = np.mgrid[0:H, 0:W]
rr = np.hypot(yy - H * 0.5, xx - W * 0.5)
core = L20[rr < H * 0.05].mean()
far = np.concatenate([L20[:H // 6, :W // 6].ravel(), L20[:H // 6, -W // 6:].ravel()]).mean()
check('the scorch darkens the sand under it (from above, 20 s: the centre under 0.9 of the sand beyond it)',
      core < 0.9 * far, '%.1f vs %.1f' % (core, far))
# the strike light: the ground in the strike frame and at 0.1 s against the ground at 5 s (the lower third: the sand)
g0, g01, g5 = (lum(n)[2 * H // 3:].mean() for n in ('strike', 'sparks_0.1s', 'smoke_gone_5s'))
check('the strike lights the sand: the ground at the strike and at 0.1 s over twice its light at 5 s',
      g0 > 2 * g5 and g01 > 2 * g5, '%.1f, %.1f vs %.1f' % (g0, g01, g5))
pf, p5 = lum('burn_puffs_0.8s'), lum('smoke_gone_5s')
check('the burn puffs are drawn at 0.8 s and gone at 5 s (bright pixels near the impact)',
      (pf > 200).sum() > 500 and (p5 > 200).sum() < (pf > 200).sum() * 0.05, ((pf > 200).sum(), (p5 > 200).sum()))
hw, hh = W // 2, H // 2
sheet = Image.new('RGB', (hw * 2, hh * ((len(paths) + 1) // 2)))
for i, n in enumerate(paths):
    im = Image.open(paths[n]).convert('RGB').resize((hw, hh), Image.LANCZOS)
    ImageDraw.Draw(im).text((6, 4), n, fill=(255, 255, 0))
    sheet.paste(im, ((i % 2) * hw, (i // 2) * hh))
sheet.save(os.path.join(OUT, 'strike_on_sand_sheet.png'))
print('RESULT ' + ('PASS' if not fails else 'FAIL (%d)' % len(fails)), flush=True)
