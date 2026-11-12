"""The strike light's range window in EEVEE, measured against three.js's.

three.js fades a PointLight of range D over distance r as (1 - (r / D)^4)^2 on top of the inverse square law (the
Frostbite window of getDistanceAttenuation). The strike light (eidoblend.weather.strike.strike_light) is EEVEE's point
light with use_custom_distance and cutoff_distance = LIGHTNING_LIGHT_RANGE (900 m). This renders that light, at the
strike's peak (12000 cd: 4 pi x 12000 W), over a white diffuse plane seen straight down through an orthographic camera,
10 m over the ground (a local strike) and 120 m up (a distant one). Along the line out from the light's foot it reads
the irradiance (pi x the plane's radiance), divides by the inverse square law I cos(theta) / r^2 (I measured from the
10 m light over r = 15-60 m, where both windows are 1), and compares the window it finds with three's at the same r.
A third render leaves the custom distance off: the range EEVEE then derives from the scene's light_threshold.

    bash run_blender.sh blender/tests/weather/probe_strike_light_falloff.py        (GPU: three 1200 x 24 renders)

Writes out/strike_falloff/: the renders (EXR), falloff.png (the windows found, against three's: white three's, orange
the 10 m light, cyan the 120 m light, grey the light without its custom distance) and falloff.json.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.weather import lightning as L  # noqa: E402
from eidoblend.weather.strike import strike_light  # noqa: E402

OUT = os.path.join(HERE, 'out', 'strike_falloff')
os.makedirs(OUT, exist_ok=True)
fails = []
D = L.LIGHTNING_LIGHT_RANGE
W, H = 1200, 24                      # one metre per pixel along the line, from 100 m behind the foot to 1100 m out


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


def three_window(r):
    return np.clip(1.0 - (r / D) ** 4, 0.0, 1.0) ** 2


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.eevee.taa_render_samples = 16
sc.eevee.use_raytracing = True
sc.eevee.use_fast_gi = True
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0.0
sc.render.image_settings.file_format = 'OPEN_EXR'
sc.render.image_settings.color_depth = '32'
world = bpy.data.worlds.new('black')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
sc.world = world

# the ground: a white diffuse plane, no specular
m = bpy.data.materials.new('white_diffuse')
m.use_nodes = True
bs = m.node_tree.nodes['Principled BSDF']
bs.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
bs.inputs['Roughness'].default_value = 1.0
bs.inputs['Specular IOR Level'].default_value = 0.0
me = bpy.data.meshes.new('ground')
s = 3000.0
me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
me.materials.append(m)
ground = bpy.data.objects.new('ground', me)
sc.collection.objects.link(ground)

# the camera: straight down over the line y = 0, x from -100 to 1100 m (pixel centres at -99.5 ... 1099.5)
cd = bpy.data.cameras.new('cam')
cd.type = 'ORTHO'
cd.ortho_scale = float(W)
cd.clip_start, cd.clip_end = 1.0, 2000.0
cam = bpy.data.objects.new('cam', cd)
cam.location = (500.0, 0.0, 600.0)
sc.collection.objects.link(cam)
sc.camera = cam

light = strike_light(sc.collection)                  # the toolkit's own strike light: point, no shadow, 900 m cutoff
light.data.energy = L.LIGHTNING_LIGHT_PEAK * 4 * math.pi
light.data.color = (1.0, 1.0, 1.0)
print('[falloff] strike light: custom distance %s, cutoff %.0f m, energy %.0f W, light_threshold %.3f'
      % (light.data.use_custom_distance, light.data.cutoff_distance, light.data.energy, sc.eevee.light_threshold),
      flush=True)


def render_line(tag, height, custom):
    light.location = (0.0, 0.0, height)
    light.data.use_custom_distance = custom
    p = os.path.join(OUT, '%s.exr' % tag)
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p, check_existing=False)
    px = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    rad = px.reshape(H, W, 4)[H // 2 - 2:H // 2 + 2, :, :3].mean(axis=(0, 2))     # the rows through y = 0
    x = -100.0 + (np.arange(W) + 0.5)
    r = np.sqrt(x * x + height * height)
    e = math.pi * rad                                  # irradiance on a white Lambert plane
    isq = height / r ** 3                              # I cos(theta) / r^2 per unit intensity
    return dict(tag=tag, height=height, custom=custom, x=x, r=r, e=e, isq=isq)


runs = [render_line('local_10m', 10.0, True), render_line('distant_120m', 120.0, True),
        render_line('no_custom_distance_120m', 120.0, False)]
light.data.use_custom_distance = True
# the intensity EEVEE gives the light, from the 10 m light where both windows are 1 (r = 15-60 m: three's is 0.99998)
near = (runs[0]['r'] >= 15.0) & (runs[0]['r'] <= 60.0) & (runs[0]['x'] > 0)
K = float(np.median(runs[0]['e'][near] / runs[0]['isq'][near]))
for run in runs:
    run['intensity'] = K
    run['window'] = run['e'] / (K * run['isq'])
summary = {}
for run in runs:
    r, win, x = run['r'], run['window'], run['x']
    out = x > 0
    inside = out & (r >= 60.0) & (r <= D - 10.0)
    beyond = out & (r >= D + 5.0)
    w3 = three_window(r)
    dev = float(np.max(np.abs(win[inside] - w3[inside])))
    tail = float(np.max(np.abs(win[beyond]))) if beyond.any() else 0.0
    # where the light found ends: the first r past which the window stays under 1e-4
    lit = np.where(out & (win > 1e-4))[0]
    reach = float(r[lit[-1]]) if len(lit) else 0.0
    samples = {('%d m' % d): round(float(np.interp(d, r[out], win[out])), 4) for d in (100, 300, 450, 600, 700, 800, 880)}
    summary[run['tag']] = dict(height=run['height'], custom_distance=run['custom'],
                               intensity_cd=round(run['intensity'], 1), reach_m=round(reach, 1),
                               max_deviation_from_three=round(dev, 4), max_beyond_900=round(tail, 6),
                               window=samples, three=dict((k, round(float(three_window(float(k.split()[0]))), 4))
                                                          for k in samples))
    print('[falloff] %s: I %.0f cd, reach %.0f m, window %s (three %s)'
          % (run['tag'], run['intensity'], reach, samples, summary[run['tag']]['three']), flush=True)
    if run['custom']:
        check('%s: EEVEE fades the strike light over its 900 m range by three\'s window (max deviation %.3f)'
              % (run['tag'], dev), dev < 0.03)
        check('%s: nothing past 900 m' % run['tag'], tail < 1e-4, '%.2e' % tail)
        check('%s: the light is the 12000 cd strike (within 3 %%)' % run['tag'],
              abs(run['intensity'] / L.LIGHTNING_LIGHT_PEAK - 1.0) < 0.03, '%.0f cd' % run['intensity'])
nc = summary['no_custom_distance_120m']
check('without its custom distance the light ends far short of 900 m (EEVEE\'s light_threshold range)',
      nc['reach_m'] < 0.8 * D, '%.0f m' % nc['reach_m'])
with open(os.path.join(OUT, 'falloff.json'), 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=1)

# the chart: window against r, 0-1000 m across, 0-1.05 up
CW, CH, PAD = 900, 420, 30
chart = np.zeros((CH, CW, 4), np.float32)
chart[..., 3] = 1.0
chart[..., :3] = 0.08


def plot(rr, ww, col, thick=1):
    ok = np.isfinite(ww)
    rr, ww = rr[ok], ww[ok]
    px_ = PAD + rr / 1000.0 * (CW - 2 * PAD)
    py_ = PAD + np.clip(ww, 0.0, 1.05) / 1.05 * (CH - 2 * PAD)
    for xa, ya in zip(px_, py_):
        xi, yi = int(round(xa)), int(round(ya))
        chart[max(0, yi - thick):yi + thick + 1, max(0, xi - thick):xi + thick + 1, :3] = col


for d in range(0, 1001, 100):                         # grid every 100 m, the range at 900 m brighter
    xi = int(round(PAD + d / 1000.0 * (CW - 2 * PAD)))
    chart[PAD:CH - PAD, xi, :3] = 0.35 if d == 900 else 0.18
chart[PAD, PAD:CW - PAD, :3] = 0.35
rr = np.linspace(0.0, 1000.0, 2000)
plot(rr, three_window(rr), (1.0, 1.0, 1.0), 2)
colours = dict(local_10m=(1.0, 0.55, 0.1), distant_120m=(0.2, 0.85, 1.0), no_custom_distance_120m=(0.55, 0.55, 0.55))
for run in runs:
    sel = (run['x'] > 0) & (run['r'] >= 15.0) & (run['r'] <= 1000.0)
    plot(run['r'][sel][::3], run['window'][sel][::3], colours[run['tag']], 1)
img = bpy.data.images.new('falloff_chart', CW, CH, alpha=False)
img.pixels.foreach_set(chart.ravel())
img.filepath_raw = os.path.join(OUT, 'falloff.png')
img.file_format = 'PNG'
img.save()
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
