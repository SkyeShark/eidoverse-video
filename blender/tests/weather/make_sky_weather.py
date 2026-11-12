"""The weather on screen two ways: built by make_sky in one call, and over a scene with no procedural sky.

    bash run_blender.sh blender/tests/weather/make_sky_weather.py [--res 960x540] [--samples 16] [--at 30]

A small street of blocks on wet-able asphalt, the camera at eye height looking down it; every shot is the frame
`--at` seconds in (the weather before it is a pre-roll that wets the street).
  one_call   make_sky(weather='storm', weather_fx={occluders, strike_targets}) and sky.bake(): the sky with its storm,
             the rain and splashes, the street wet. Against dry: the same make_sky with weather_fx=False.
  no_sky     the scene's own world (a plain overcast grey) and its own sun lamp, make_weather_system(scene, None) in
             rain turning to storm: the rain falls in the base colour and the street wets, the world and the sun are
             the scene's. Against dry: the same scene without the weather.
Writes out/make_sky_weather/ with sheet.png (dry left, weather right), and prints PASS/FAIL per numeric check.
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

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--at', type=float, default=30.0)
ap.add_argument('--exposure', type=float, default=0.6)
args = ap.parse_args(argv)
W, H = (int(v) for v in args.res.split('x'))
FPS = 24
F = int(round(args.at * FPS)) + 1
OUT = os.path.join(HERE, 'out', 'make_sky_weather')
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  (' + str(detail) + ')') if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


def material(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    return m


def street():
    """A fresh scene: asphalt, two rows of blocks, a camera down the street."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.eevee.taa_render_samples = args.samples
    sc.eevee.use_raytracing = True
    sc.eevee.use_fast_gi = True
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = args.exposure
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, F
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    coll = bpy.data.collections.new('street')
    sc.collection.children.link(coll)
    me = bpy.data.meshes.new('road')
    me.from_pydata([(-100, -100, 0), (100, -100, 0), (100, 100, 0), (-100, 100, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(material('asphalt', (0.11, 0.11, 0.115), 0.62))
    coll.objects.link(bpy.data.objects.new('road', me))
    walls = [material('brick', (0.42, 0.20, 0.13), 0.8), material('render', (0.55, 0.53, 0.48), 0.7)]
    for i in range(6):
        for side in (-1, 1):
            h = 8.0 + 5.0 * ((i * 7 + (side + 1) * 3) % 4)
            bm = bpy.data.meshes.new('block')
            x0, x1 = (6.0, 14.0) if side > 0 else (-14.0, -6.0)
            y0, y1 = 4.0 + i * 13.0, 15.0 + i * 13.0
            v = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h)]
            bm.from_pydata(v, [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
            bm.materials.append(walls[(i + side) % 2])
            ob = bpy.data.objects.new('building_%d_%d' % (i, side), bm)
            ob['eido_noLightningStrike'] = 1
            coll.objects.link(ob)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 28.0
    cam.data.clip_end = 20000.0
    cam.location = (1.2, -10.0, 1.6)
    cam.rotation_euler = (math.radians(86.0), 0.0, math.radians(-4.0))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam, coll


def render(sc, name):
    sc.frame_set(F)
    p = os.path.join(OUT, name + '.png')
    sc.render.filepath = p
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('[make_sky_weather] %s rendered in %.1fs' % (name, time.time() - t0), flush=True)
    return p


def img(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGB')).astype(np.float64) / 255.0


def lum(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def streaks(dry, wet):
    """The share of the frame's upper part (the facades and the sky over the street's far end) the rain makes
    brighter by 0.02 or more: its streaks (wet walls only darken)."""
    top = slice(0, int(H * 0.40))
    return float(((lum(wet) - lum(dry))[top] > 0.02).mean())


ROAD = (slice(int(H * 0.80), H), slice(int(W * 0.30), int(W * 0.70)))      # the road just ahead of the camera
shots = {}

# ---- one call: make_sky builds and bakes the weather ----
for tag, fx in (('one_call_dry', False), ('one_call_storm', None)):
    sc, cam, coll = street()
    t0 = time.time()
    kw = dict(weather_fx=False) if fx is False else dict(weather_fx={'occluders': coll, 'strike_targets': [coll]})
    sky = make_sky(sc, camera=cam, hours=16.5, weather='storm', cache_dir=os.path.join(OUT, 'cache_' + tag), **kw)
    sky.use_fog(density=0.0012)
    sky.bake(F, F, log=lambda *a: None)
    print('[make_sky_weather] %s: built and baked in %.1fs' % (tag, time.time() - t0), flush=True)
    if fx is None:
        wx = sky.weather_fx
        r = wx.rows[-1]
        check('one call: make_sky built the weather and its bake keyed it (rain falling, the street wet at %.0f s)'
              % args.at, wx is not None and wx.owned_by_sky and r['rain_k'] > 0.9 and r['wetness'] > 0.6
              and not bpy.data.objects['eido_rain'].hide_render, 'rainK %.2f wetness %.2f water %.2f'
              % (r['rain_k'], r['wetness'], r['surface_water']))
        check("one call: the sky was baked by the weather's bake, flashes and all",
              wx.sky_frames is not None and len(wx.sky_frames) == 1 and wx._active)
    shots[tag] = render(sc, tag)

# ---- no sky: the scene's own world and sun ----
for tag, rain in (('no_sky_dry', False), ('no_sky_rain', True)):
    sc, cam, coll = street()
    world = bpy.data.worlds.new('overcast_grey')
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.30, 0.32, 0.35, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    sc.world = world
    sun = bpy.data.objects.new('key_sun', bpy.data.lights.new('key_sun', 'SUN'))
    sun.data.energy = 1.2
    sun.rotation_euler = (math.radians(55.0), 0.0, math.radians(35.0))
    sc.collection.objects.link(sun)
    if rain:
        wx = make_weather_system(sc, None, cache_dir=os.path.join(OUT, 'cache_' + tag), occluders=coll)
        wx.wrap_scene()
        wx.set_weather('rain')
        wx.transition_to('storm', 1.0, 10.0, at=8.0)
        rows = wx.bake(F, F)
        r = rows[-1]
        check('no sky: the scene keeps its world and its one sun lamp, nothing baked a sky',
              sc.world == world and [o.name for o in sc.objects if o.type == 'LIGHT' and o.name != 'eido_lightning_light']
              == ['key_sun'] and wx.sky_frames is None)
        check('no sky: storm rain on every column, base colour, street wet, no lightning',
              r['rain_k'] > 0.9 and r['cell_at_camera'] == 1.0 and r['wetness'] > 0.6 and not wx.sched.events,
              'rainK %.2f wetness %.2f events %d' % (r['rain_k'], r['wetness'], len(wx.sched.events)))
    shots[tag] = render(sc, tag)

a = {k: img(p) for k, p in shots.items()}
for pre in ('one_call', 'no_sky'):
    dry, wet = a[pre + '_dry'], a[pre + ('_storm' if pre == 'one_call' else '_rain')]
    road = float(np.abs(lum(wet) - lum(dry))[ROAD].mean())
    st = streaks(dry, wet)
    check('%s: the road reads wet (reflections, puddles) and the rain draws its streaks over the street' % pre,
          road > 0.015 and st > 0.002, 'road |wet - dry| %.3f; %.2f %% of the upper frame brighter by the streaks'
          % (road, st * 100))
from PIL import Image, ImageDraw  # noqa: E402
order = [('one_call_dry', 'make_sky storm, weather_fx=False'), ('one_call_storm', 'make_sky storm: its own weather'),
         ('no_sky_dry', 'own world and sun, no weather'), ('no_sky_rain', 'own world and sun: weather without a sky')]
sheet = Image.new('RGB', (W * 2, H * 2))
for i, (k, label) in enumerate(order):
    im = Image.open(shots[k]).convert('RGB')
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 8 + 7 * len(label), 20), fill=(0, 0, 0))
    d.text((6, 4), label, fill=(255, 255, 255))
    sheet.paste(im, ((i % 2) * W, (i // 2) * H))
sheet.save(os.path.join(OUT, 'sheet.png'))
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
