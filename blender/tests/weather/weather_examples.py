"""The weather system's options and the source's own examples, rendered on the street.

    bash run_blender.sh blender/tests/weather/weather_examples.py [--res 960x540 --samples 16] [--only a,b]

  rain_drop_texture      storm rain down the street from 1.4 m, the repo's rain_streak.png
  rain_procedural        the same frame with drop_texture=None: the JS fallback shape (bright core, end fades)
  ember_rain             weather.setColors({ rain: [1.0, 0.55, 0.30] }) (the JS example) with an alien wet_tint
  wet_moisture_model     'rain' after 30 s, eido_wet over the moisture history (the default)
  wet_eidoverse_model    the same frame, wet_model='eidoverse' (eidoverse's one global wetness)
  ground_y_splashes      no occluders: the splash rings on the flat ground_y plane (the JS default), close
  procedural_bolt        bolt_texture=None at a forced close strike (debug_force_local_strike)
  rain_without_splashes  splash_count=0 (the JS terrain-scene switch): no rings, the rain still falls

Writes out/examples/<name>.png and examples_sheet.png. Prints PASS/FAIL for what it can measure: the procedural and
textured streaks differ, ember rain is warmer than plain rain, the two wet models both wet the road, the rings sit on
ground_y, the procedural bolt is drawn, splash_count=0 leaves the splashes hidden.
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
sys.path.insert(0, HERE)
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.weather import make_weather_system  # noqa: E402
from street_set import build_street  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--only', default='')
ap.add_argument('--dry', action='store_true', help='plan, key and check only: no sky bake, no render (no GPU)')
args = ap.parse_args(argv)
DRY = args.dry
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'examples')
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
S = build_street(sc, rooms=not DRY)
from eidoblend.look.post import chain  # noqa: E402
chain.set_bloom(sc, strength=0.25, size=0.4, threshold=0.85)    # the WebGPU auto-enhance bloom, at its defaults
for ob in S['collection'].objects:
    if ob.name.startswith('building_'):
        ob['eido_noLightningStrike'] = 1
cam = S['camera']
STREET_CAM = (tuple(cam.location), tuple(cam.rotation_euler), cam.data.lens)


def set_cam(loc, rot, lens):
    cam.location, cam.rotation_euler, cam.data.lens = loc, rot, lens


def look(loc, target, lens=35.0):
    from mathutils import Vector
    d = Vector(target) - Vector(loc)
    set_cam(loc, d.to_track_quat('-Z', 'Y').to_euler(), lens)


def shot(name, weather, t, cam_fn, hours=16.0, sky_calls=(), **wopts):
    """Build the sky and the weather with these options, bake to media time t, render one frame."""
    t0 = time.time()
    f = int(round(t * FPS)) + 1
    sc.frame_start, sc.frame_end = 1, f
    cam_fn()
    sky = make_sky(sc, camera=cam, hours=hours, weather=weather, sun=shot.sun,
                   cache_dir=os.path.join(OUT, 'cache', name), quality='film')
    shot.sun = sky.sun
    for fn in sky_calls:
        fn(sky)
    wx = make_weather_system(sc, sky, strike_targets=[S['collection']], log=lambda *a: None, **wopts)
    wx.wrap_scene()
    if name == 'procedural_bolt':
        wx.debug_force_local_strike(at=t - 1.2)
    rows = wx.bake(frame_start=f, frame_end=f, bake_sky=not DRY)
    if name == 'procedural_bolt' and wx.sched.events:
        f = int(round(wx.sched.events[-1]['time'] * FPS)) + 1 + 1          # the frame after the strike begins
        rows = wx.bake(frame_start=f, frame_end=f, bake_sky=not DRY)
    sc.frame_set(f)
    p = os.path.join(OUT, name + '.png')
    sc.render.filepath = p
    if not DRY:
        bpy.ops.render.render(write_still=True)
    print('[examples] %s: %s t=%.2fs frame %d (%.1fs)' % (name, weather, (f - 1) / FPS, f, time.time() - t0),
          flush=True)
    return p, wx, rows[-1], f


shot.sun = None


# the rain shots look down the street from 1.4 m: depth for the drops to layer in, dark facades behind them (rain is
# a population of faint streaks, about 0.08 per cubic metre at 16000: a short view holds a handful)
RAIN_VIEW = ((1.5, -4.0, 1.4), (1.0, 40.0, 3.2))
names = ['rain_drop_texture', 'rain_procedural', 'ember_rain', 'wet_moisture_model', 'wet_eidoverse_model',
         'ground_y_splashes', 'procedural_bolt', 'rain_without_splashes']
if args.only:
    names = [n for n in names if n in args.only.split(',')]
paths = {}
stats = {}


def img(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGB')).astype(np.float64) / 255.0


for name in names:
    if name in ('rain_drop_texture', 'rain_procedural', 'ember_rain', 'rain_without_splashes'):
        kw = dict(occluders=S['collection'])
        if name == 'rain_procedural':
            kw['drop_texture'] = None
        if name == 'ember_rain':
            kw.update(rain_color=(1.0, 0.55, 0.30), wet_tint=(1.0, 0.72, 0.5))
        if name == 'rain_without_splashes':
            kw['splash_count'] = 0
        p, wx, r, f = shot(name, 'storm', 8.0, lambda: look(*RAIN_VIEW), **kw)
        if name == 'ember_rain':
            check('ember rain: the rain colour record is the override', wx.get_colors()['rain'] == (1.0, 0.55, 0.30),
                  wx.get_colors())
            rc = r['rain_color']
            check('ember rain: the keyed rain colour is the lit rain x (1, 0.55, 0.30)',
                  abs(rc[1] / rc[0] - r['lit_rain'][1] / r['lit_rain'][0] * 0.55) < 1e-6, rc)
        if name == 'rain_without_splashes':
            sp = bpy.data.objects['eido_splashes']
            check('splash_count=0: the splashes stay hidden while the rain falls',
                  sp.hide_render and not bpy.data.objects['eido_rain'].hide_render)
    elif name in ('wet_moisture_model', 'wet_eidoverse_model'):
        model = 'moisture' if name == 'wet_moisture_model' else 'eidoverse'
        p, wx, r, f = shot(name, 'rain', 30.0, lambda: set_cam(*STREET_CAM), occluders=S['collection'],
                           wet_model=model)
        m = bpy.data.materials['street_asphalt']
        g = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup' and n.node_tree.name.startswith('eido_wet'))
        check('%s: the asphalt is wrapped by %s' % (name, g.node_tree.name),
              g.node_tree.name == ('eido_wet' if model == 'moisture' else 'eido_wet_eidoverse'))
    elif name == 'ground_y_splashes':
        p, wx, r, f = shot(name, 'storm', 8.0, lambda: look((1.0, 0.0, 0.55), (1.0, 4.0, 0.0), 35.0),
                           occluders=None, ground_y=0.0)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.objects['eido_splashes'].evaluated_get(dg).data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        z = co.reshape(-1, 3)[:, 2]
        check('ground_y: every ring lies 1.5 cm over ground_y (no occluders: the flat plane)',
              len(z) > 0 and np.allclose(z, 0.015, atol=1e-4), '%d vertices, z %.4f..%.4f' % (len(z), z.min(), z.max()))
    elif name == 'procedural_bolt':
        p, wx, r, f = shot(name, 'storm', 9.0, lambda: set_cam(*STREET_CAM), occluders=S['collection'],
                           bolt_texture=None)
        bolts = [o for o in bpy.data.objects if o.name.startswith('eido_bolt_') and not o.hide_render]
        check('procedural bolt: the forced strike draws its ribbon with no trace texture',
              bool(bolts) and not any(n.bl_idname == 'ShaderNodeTexImage'
                                      for n in bpy.data.materials['eido_bolt'].node_tree.nodes), [o.name for o in bolts])
    if not DRY:
        paths[name] = p
from eidoblend.weather.keys import key_series  # noqa: E402


def render_to(name):
    p = os.path.join(OUT, name + '.png')
    sc.render.filepath = p
    if not DRY:
        bpy.ops.render.render(write_still=True)
        paths[name] = p
    return p


def impact_closeups():
    """A forced close strike planned from the street camera. From the frame after it the camera stands 7 m from the
    impact, so the sparks, the burn puffs (they face the camera of every frame) and the scorch are seen close. The
    strike lands where it did in the first pass, because the camera at the event's own frame is unchanged."""
    t0 = time.time()
    f_end = int(round(32.0 * FPS)) + 1
    sc.frame_start, sc.frame_end = 1, f_end
    set_cam(*STREET_CAM)
    sky = make_sky(sc, camera=cam, hours=16.0, weather='storm', sun=shot.sun,
                   cache_dir=os.path.join(OUT, 'cache', 'impact'), quality='film')
    shot.sun = sky.sun
    wx = make_weather_system(sc, sky, strike_targets=[S['collection']], occluders=S['collection'], log=lambda *a: None)
    wx.wrap_scene()
    wx.debug_force_local_strike(at=6.0)
    wx.plan(f_end, write_from=f_end + 1)
    imp = wx.sched.impacts[-1]
    p3 = imp['point']
    P = (p3[0], -p3[2], p3[1])
    fs = int(round(imp['birth'] * FPS)) + 1
    from mathutils import Vector
    eye = Vector((P[0] - 4.5, P[1] - 5.5, P[2] + 1.6))
    rot = (Vector((P[0], P[1], P[2] + 1.0)) - eye).to_track_quat('-Z', 'Y').to_euler()
    key_series(cam, 'location', [1, fs + 1], [STREET_CAM[0], tuple(eye)], 'CONSTANT')
    key_series(cam, 'rotation_euler', [1, fs + 1], [STREET_CAM[1], tuple(rot)], 'CONSTANT')
    cam.data.lens = 30.0
    out = []
    for name, df in (('impact_sparks_close', 2), ('impact_puff_close', int(round(1.2 * FPS))),
                     ('impact_smoke_close', int(round(3.0 * FPS))), ('scorch_close', int(round(20.0 * FPS)))):
        f = fs + df
        wx.bake(frame_start=f, frame_end=f, bake_sky=not DRY)
        imp2 = wx.sched.impacts[-1]
        check('%s: the strike lands where the first pass put it' % name,
              max(abs(a - b) for a, b in zip(imp2['point'], p3)) < 1e-9)
        sc.frame_set(f)
        out.append(render_to(name))
        print('[examples] %s: %.2f s after the strike, frame %d' % (name, df / FPS, f), flush=True)
    cam.animation_data_clear()
    set_cam(*STREET_CAM)
    print('[examples] impact close-ups (%.1fs)' % (time.time() - t0), flush=True)
    return out


def bolt_styles():
    """The five lightning styles (white, blue, purple, red, green: the darkstorm palette) as bolt ribbons side by
    side, 260 m out under the darkstorm canopy, each at channel glow 0.55."""
    from eidoblend.weather.bolt import bolt_ribbon
    from eidoblend.weather import lightning as LG
    t0 = time.time()
    sc.frame_start, sc.frame_end = 1, 2
    look((0.0, -8.0, 1.6), (0.0, 100.0, 42.0), 24.0)
    sky = make_sky(sc, camera=cam, hours=17.0, weather='darkstorm', sun=shot.sun,
                   cache_dir=os.path.join(OUT, 'cache', 'bolt_styles'), quality='film')
    shot.sun = sky.sun
    wx = make_weather_system(sc, sky, log=lambda *a: None)
    wx.bake(frame_start=2, frame_end=2, bake_sky=not DRY)
    cs = float(sky.sky.U['cloudStart'])
    coll = bpy.data.collections['eido_weather']
    for i, key in enumerate(('white', 'blue', 'purple', 'red', 'green')):
        pos, uvs, tris = bolt_ribbon(40 + i * 7, (0.0, 1.6, 8.0), -100.0 + 50.0 * i, -260.0, 2.0, cs)
        me = bpy.data.meshes.new('bolt_style_' + key)
        me.from_pydata([(p[0], -p[2], p[1]) for p in pos], [], tris)
        uvl = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li in poly.loop_indices:
                uvl.data[li].uv = uvs[me.loops[li].vertex_index]
        ca = me.color_attributes.new('eido_color', 'FLOAT_COLOR', 'POINT')
        c = LG.style_color(key) + (1.0,)
        for d in ca.data:
            d.color = c
        me.materials.append(wx.bolt_material)
        ob = bpy.data.objects.new('bolt_style_' + key, me)
        ob['eido_channel'] = 0.55
        coll.objects.link(ob)
    sc.frame_set(2)
    p = render_to('bolt_styles')
    for key in ('white', 'blue', 'purple', 'red', 'green'):
        bpy.data.objects.remove(bpy.data.objects['bolt_style_' + key], do_unlink=True)
    if DRY:
        return p
    import colorsys
    from PIL import Image
    hsv = np.asarray(Image.open(p).convert('HSV')).astype(np.float64)[:int(H * 0.6)]     # the sky, above the shops
    hue, sat, val = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    near = {}
    for key in ('blue', 'purple', 'red', 'green'):
        hx = LG.LIGHTNING_STYLES[key]['hex']
        want = colorsys.rgb_to_hsv(((hx >> 16) & 255) / 255, ((hx >> 8) & 255) / 255, (hx & 255) / 255)[0] * 360
        d = np.abs((hue - want + 180) % 360 - 180)
        near[key] = int(((d < 25) & (sat > 0.25) & (val > 0.3)).sum())
    check('bolt styles: each coloured style shows its own hue in its glow (display hue within 25 degrees; the cores '
          'run white, as the JS tints them)', all(n >= 20 for n in near.values()), near)
    print('[examples] bolt styles (%.1fs)' % (time.time() - t0), flush=True)
    return p


if not args.only or 'impact' in args.only:
    impact_closeups()
if not args.only or 'bolt_styles' in args.only:
    bolt_styles()
if 'rain_drop_texture' in paths and 'rain_procedural' in paths:
    a, b = img(paths['rain_drop_texture']), img(paths['rain_procedural'])
    check('the procedural streak shape differs from the drop texture (same frame)', np.abs(a - b).mean() > 1e-4,
          '%.5f' % np.abs(a - b).mean())
if 'rain_drop_texture' in paths and 'ember_rain' in paths:
    a, b = img(paths['rain_drop_texture']), img(paths['ember_rain'])
    da, db = a[..., 0] - a[..., 2], b[..., 0] - b[..., 2]
    check('ember rain reads warmer than plain rain (mean red minus blue)', db.mean() > da.mean(),
          '%.4f vs %.4f' % (db.mean(), da.mean()))
if paths:
    from PIL import Image, ImageDraw  # noqa: E402
    hw, hh = W // 2, H // 2
    sheet = Image.new('RGB', (hw * 3, hh * ((len(paths) + 2) // 3)))
    for i, name in enumerate(paths):
        im = Image.open(paths[name]).convert('RGB').resize((hw, hh), Image.LANCZOS)
        ImageDraw.Draw(im).text((6, 4), name, fill=(255, 255, 255))
        sheet.paste(im, ((i % 3) * hw, (i // 3) * hh))
    sheet.save(os.path.join(OUT, 'examples_sheet.png'))
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
