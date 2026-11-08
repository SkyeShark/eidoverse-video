"""Every weather state on the street (the WEATHER presets: clear, fair, sunshower, overcast, rain, storm, cyclone,
darkstorm), each after at least 30 s in that state, so the ground carries the wetness and pooled water it builds.

    bash run_blender.sh blender/tests/weather/weather_states.py [--res 960x540 --samples 12] [--only rain,storm]

Rain falls where the state's cells are (the cell gate of the sky's weather field, upwind of the drops), and the
street's moisture history fills only under them. So each raining state is planned for 300 s and shown at the moment
its rain has wet the street most (after 30 s). A state whose cells never pass over the street in that time must
have left it dry; then the whole street is carried under the nearest of its raining cells (at 60 s) and shown
there, so its rain is seen. The plan runs at 10 fps (dt 0.1 s, the JS motion clamp; the moisture history is
analytic between its 4 Hz refreshes, so the frame rate does not change it). Also checks the legacy names (drizzle,
hurricane, noreaster) and an unknown name. Writes out/states/<state>.png and states_sheet.png (labelled).
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
from eidoblend.sky import make_sky, WEATHER  # noqa: E402
from eidoblend.weather import make_weather_system  # noqa: E402
from street_set import build_street  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=12)
ap.add_argument('--only', default='')
ap.add_argument('--hours', type=float, default=16.0)
ap.add_argument('--seconds', type=float, default=300.0)
ap.add_argument('--dry', action='store_true', help='plan, key and check only: no sky bake, no render (no GPU)')
args = ap.parse_args(argv)
DRY = args.dry
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'states')
os.makedirs(OUT, exist_ok=True)
FPS = 10
F_END = int(args.seconds * FPS) + 1
F30 = 30 * FPS + 1
F60 = 60 * FPS + 1
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
sc.frame_start, sc.frame_end = 1, F_END
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = 0.6
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
S = build_street(sc, rooms=not DRY)
for ob in S['collection'].objects:
    if ob.name.startswith('building_'):
        ob['eido_noLightningStrike'] = 1
cam = S['camera']


def move_street(dx, dy):
    """Carry the whole street (its objects, lamps and camera) dx, dy metres across the world."""
    for ob in list(S['collection'].objects) + list(S['lamps']) + [cam]:
        ob.location.x += dx
        ob.location.y += dy


# ---- the legacy names and an unknown one (the sky owns the table; the weather follows its state) ----
probe = make_sky(sc, camera=cam, hours=args.hours, weather='clear', cache_dir=os.path.join(OUT, 'cache', 'names'),
                 shadows=False)
for name, want in (('drizzle', 'rain'), ('hurricane', 'cyclone'), ('noreaster', 'cyclone'), ('no_such', 'clear')):
    probe.wx.set_weather(name, 1.0)
    check("set_weather('%s') -> %s" % (name, want), probe.wx.state['name'] == want, probe.wx.state['name'])
bpy.data.objects.remove(probe.sun, do_unlink=True)
states = [s for s in ('clear', 'fair', 'sunshower', 'overcast', 'rain', 'storm', 'cyclone', 'darkstorm')
          if not args.only or s in args.only.split(',')]
sun = None
paths = []
for name in states:
    t0 = time.time()
    sky = make_sky(sc, camera=cam, hours=args.hours, weather=name, sun=sun,
                   cache_dir=os.path.join(OUT, 'cache', name), quality='film')
    sun = sky.sun
    wx = make_weather_system(sc, sky, strike_targets=[S['collection']], occluders=S['collection'],
                             storm_center=(0.0, 380.0), storm_range=420.0, log=lambda *a: None)
    wx.wrap_scene()
    w = WEATHER[name]
    f = F30
    moved = None
    if w['rain'] > 0:
        rows = wx.plan(F_END, write_from=F_END + 1)
        cells = max(r['cell_at_camera'] for r in rows)
        if cells < 0.3:
            check("%s: no cell passes over the street in %d s, and it stays dry under the state's rainy target"
                  % (name, int(args.seconds)), max(r['moisture_at_camera'][0] for r in rows) < 0.05)
            # to show the state's rain, move the street under one of its raining cells (the nearest at 60 s)
            import numpy as np
            wx.plan(F60, write_from=F60 + 1)
            g = np.arange(-2500.0, 2501.0, 25.0)
            X, Y = np.meshgrid(g, g)
            gate = wx._cell_at(X + cam.location.x, Y + cam.location.y)
            d = np.where(gate > 0.95, np.hypot(X, Y), np.inf)
            if np.isfinite(d).any():
                i = np.unravel_index(np.argmin(d), d.shape)
                moved = (float(X[i]), float(Y[i]))
                move_street(*moved)
                print('[states] %-9s the street moved %.0f m to a raining cell %s' % (name, d[i], moved), flush=True)
                rows = wx.plan(F_END, write_from=F_END + 1)
                cells = max(r['cell_at_camera'] for r in rows)
        cand = [r for r in rows if r['frame'] >= F30]
        best = max(cand, key=lambda r: (round(r['moisture_at_camera'][0], 3), -r['frame']))
        if best['moisture_at_camera'][0] > 0.05:
            f = best['frame']
        print('[states] %-9s its cells over the street: gate up to %.2f in %ds; shown at t=%.1fs' % (
            name, cells, int(args.seconds), (f - 1) / FPS), flush=True)
    rows = wx.bake(frame_start=f, frame_end=f, bake_sky=not DRY)
    r = rows[-1]
    sc.frame_set(f)
    p = os.path.join(OUT, '%s.png' % name)
    sc.render.filepath = p
    if not DRY:
        bpy.ops.render.render(write_still=True)
        paths.append((name, p, (f - 1) / FPS))
    wet, water = r['moisture_at_camera']
    print('[states] %-9s t=%.1fs rainK %.2f, the street under the camera: cell gate %.2f, wet %.2f, water %.2f; '
          '%d lightning events (%.1fs)' % (name, (f - 1) / FPS, r['rain_k'], r['cell_at_camera'], wet, water,
                                           len(wx.sched.events), time.time() - t0), flush=True)
    if w['wet'] == 0:
        check('%s: the street stays dry' % name, wet < 1e-3 and water < 1e-3)
    elif w['rain'] == 0:
        check('%s: humidity damps the street without pooling (target %.2f)' % (name, w['wet']),
              abs(wet - w['wet']) < 0.05 and water < 0.02, 'wet %.3f water %.3f' % (wet, water))
    elif f != F30:
        check('%s: the street wets under its rain (target %.2f)%s' % (name, w['wet'], ' (moved under a cell)'
                                                                      if moved else ''), wet > 0.5 * w['wet'],
              '%.3f' % wet)
    else:
        check("%s: no cell passed over the street, and it stayed dry under the state's rainy target" % name,
              wet < 0.05, '%.3f' % wet)
    if moved:
        move_street(-moved[0], -moved[1])
if paths:
    from PIL import Image, ImageDraw  # noqa: E402
    hw, hh = W // 2, H // 2
    sheet = Image.new('RGB', (hw * 2, hh * ((len(paths) + 1) // 2)), (0, 0, 0))
    for i, (name, p, t) in enumerate(paths):
        im = Image.open(p).convert('RGB').resize((hw, hh), Image.LANCZOS)
        ImageDraw.Draw(im).text((8, 6), '%s  t=%.0fs' % (name, t), fill=(255, 255, 255))
        sheet.paste(im, ((i % 2) * hw, (i // 2) * hh))
    sheet.save(os.path.join(OUT, 'states_sheet.png' if not args.only
                            else 'states_sheet_%s.png' % args.only.replace(',', '_')))
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
