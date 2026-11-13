"""The EEVEE half of the rain A/B: the blocks, camera, hour and weather moments of rain_ab_webgpu_scene.js, with
eidoblend.sky and eidoblend.weather (wet_model 'eidoverse', rain_cells 'column': eidoverse's own formulas, no
occluders, as the WebGPU scene has none), one frame per state and the same frame with the rain hidden, then the
drop-texture filtering variants.

    bash run_blender.sh blender/tests/weather/rain_ab_blender.py [--res 960x540 --samples 16] [--only cyclone,storm]
        [--variants cyclone,storm]

It reads out/verify/rain_ab/rain_ab_webgpu.json (the WebGPU run's moments and values) when it exists and renders the
same moments. Writes out/verify/rain_ab/eevee_<state>.png, eevee_<state>_norain.png, eevee_<state>_<variant>.png,
rain_ab_sheet.png (WebGPU | EEVEE per state) and rain_ab_blender.json. The rain's own contribution is the frame minus
its rain-hidden twin (display values, luma): its energy (mean |difference|), its peak (99.9th percentile) and the
number of pixels it changes by more than 2 levels, for both renderers. PASS / FAIL for the values that must agree:
rainK, denseA, rainLight, rainColor, wetness and the camera column's cell gate.
"""
import argparse
import json
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
ap.add_argument('--only', default='')
ap.add_argument('--variants', default='cyclone,storm')
ap.add_argument('--tag', default='', help='suffix for this run\'s file names (a fix under test)')
args = ap.parse_args(argv)
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'verify', 'rain_ab')
os.makedirs(OUT, exist_ok=True)
FPS = 24
TAG = ('_' + args.tag) if args.tag else ''
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


ref_path = os.path.join(OUT, 'rain_ab_webgpu.json')
ref = json.load(open(ref_path, encoding='utf-8')) if os.path.exists(ref_path) else None
if ref:
    recs = [r for r in ref['records'] if r.get('rain', True)]
    moments = [(r['name'], float(r['T'])) for r in recs]
    blocks = ref['blocks']
    hours = float(ref['hours'])
else:
    recs = []
    moments = [('cyclone', 60.0), ('storm', 60.0), ('rain', 60.0), ('darkstorm', 60.0)]
    hours = 16.0
    blocks = []
    for k in range(9):
        z0 = -6 - k * 13
        z1 = z0 - 11
        blocks.append(dict(x0=-22, x1=-8, y1=12 + (k % 3) * 4, z0=z1, z1=z0, albedo=[0.30, 0.29, 0.27]))
        blocks.append(dict(x0=8, x1=22, y1=14 + ((k + 1) % 3) * 4, z0=z1, z1=z0, albedo=[0.26, 0.27, 0.29]))
    blocks.append(dict(x0=-30, x1=30, y1=26, z0=-136, z1=-128, albedo=[0.28, 0.28, 0.28]))
if args.only:
    moments = [m for m in moments if m[0] in args.only.split(',')]
# the WebGPU frames: two per state in the JS plan's order (rain, then rain hidden), named by their film time (JS
# toFixed(2) rounding: matched by order, not by re-formatting the time)
web_png = {}
if ref:
    import re
    caps = sorted((float(m.group(1)), f) for f in os.listdir(OUT)
                  for m in [re.match(r'webgpu_at([0-9.]+)s\.png$', f)] if m)
    for r, (_t, f) in zip(sorted(ref['records'], key=lambda r: r['frame']), caps):
        web_png[(r['name'], bool(r.get('rain', True)))] = os.path.join(OUT, f)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.fps = FPS
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = 0.6                  # three's ACES at exposure 1 (sky-weather.md, Exposure)
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
from eidoblend.look.post import chain  # noqa: E402
chain.set_bloom(sc, strength=0.25, size=0.4, threshold=0.85)    # the WebGPU auto-enhance bloom, at its defaults


def material(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    p.inputs['Roughness'].default_value = rough
    return m


def box(name, x0, x1, y0, y1, z0, z1, mat):
    """An axis box from three's extents (x, y up, z), placed in Blender's (x, -z, y)."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.scale = (x1 - x0, z1 - z0, y1 - y0)
    ob.location = ((x0 + x1) / 2, -(z0 + z1) / 2, (y0 + y1) / 2)
    me.materials.append(mat)
    return ob


ground_m = material('ab_ground', (0.07, 0.07, 0.075), 0.75)
gme = bpy.data.meshes.new('ab_ground')
gme.from_pydata([(-300, -300, 0), (300, -300, 0), (300, 300, 0), (-300, 300, 0)], [], [(0, 1, 2, 3)])
gme.materials.append(ground_m)
ground = bpy.data.objects.new('ab_ground', gme)
sc.collection.objects.link(ground)
for i, b in enumerate(blocks):
    box('ab_block_%02d' % i, b['x0'], b['x1'], 0.0, b['y1'], b['z0'], b['z1'],
        material('ab_block_%02d' % i, b['albedo'], 0.85))

cam_data = bpy.data.cameras.new('ab_camera')
cam_data.sensor_fit = 'VERTICAL'
cam_data.angle_y = math.radians(50.0)
cam_data.clip_start, cam_data.clip_end = 0.1, 60000.0
cam = bpy.data.objects.new('ab_camera', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
from mathutils import Vector  # noqa: E402
cam.location = (0.0, 0.0, 1.4)
cam.rotation_euler = (Vector((0.0, 40.0, 3.2)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()

VARIANTS = {
    'closest': dict(interp='Closest', filter=None),          # the drop texture point-sampled at level 0 (no mips)
    'closest_f075': dict(interp='Closest', filter=0.75),       # and the pixel filter narrowed to 0.75 px
}


def luma(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float64)
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def _highpass(x, r=3):
    """|luma - its (2r+1) px box blur| (edges replicated): the streaks (and edges), whatever the overall level."""
    p = np.pad(x.astype(np.float64), r, mode='edge')
    c = np.cumsum(np.cumsum(p, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 2 * r + 1
    box = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
    return np.abs(x - box)


def rain_metrics(with_rain, without):
    """The rain's own contribution, in display levels (0-255 luma): |frame - its rain-hidden twin| (energy, p99.9,
    pixels changed by over 2 and 8 levels), and the streak detail it adds, robust to any overall level shift
    between the two frames (WebGPU's twins differ by a few levels overall): the high-pass energy of the frame minus
    that of its twin (hp_energy) and how many more pixels carry over 3 levels of detail (hp_px)."""
    if not (with_rain and without and os.path.exists(with_rain) and os.path.exists(without)):
        return None
    a, b = luma(with_rain), luma(without)
    d = np.abs(a - b)
    ha, hb = _highpass(a), _highpass(b)
    return dict(energy=float(d.mean()), p999=float(np.percentile(d, 99.9)), changed=int((d > 2.0).sum()),
                changed8=int((d > 8.0).sum()), hp_energy=float(ha.mean() - hb.mean()),
                hp_px=int((ha > 3.0).sum() - (hb > 3.0).sum()), base=float(b.mean()))


def render(path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


results = []
sun = None
refs = {r['name']: r for r in recs}
for name, T in moments:
    t0 = time.time()
    f = int(round(T * FPS)) + 1
    sc.frame_start, sc.frame_end = 1, f
    sky = make_sky(sc, camera=cam, hours=hours, weather=name, sun=sun, cache_dir=os.path.join(OUT, 'cache', name),
                   quality='film', weather_fx=False)
    sun = sky.sun
    wx = make_weather_system(sc, sky, wet_model='eidoverse', rain_cells='column', moisture=False,
                             log=lambda *a: None)
    wx.wrap_scene()
    rows = wx.bake(frame_start=f, frame_end=f)
    r = rows[-1]
    sc.frame_set(f)
    sc.render.filter_size = 1.5
    p_rain = render(os.path.join(OUT, 'eevee_%s%s.png' % (name, TAG)))
    gens = [m for ob in (wx.objects['eido_rain']['object'], wx.objects['eido_splashes']['object'])
            for m in ob.modifiers if m.type == 'NODES']
    for m in gens:
        m.show_render = False
    p_dry = render(os.path.join(OUT, 'eevee_%s_norain.png' % name))
    for m in gens:
        m.show_render = True
    rec = dict(name=name, T=T, frame=f, rainK=r['rain_k'], denseA=r['dense_a'], rainLight=r['rain_light'],
               rainColor=list(r['rain_color']), wetness=r['wet_target'], gate=r['cell_at_camera'],
               flash=r['l_flash'], streakLen=r['streak_len'], windVec=list(r['wind']),
               eevee=rain_metrics(p_rain, p_dry),
               webgpu=rain_metrics(web_png.get((name, True), ''), web_png.get((name, False), '')))
    w = refs.get(name)
    if w:
        for key, tol in (('rainK', 1e-4), ('denseA', 1e-4), ('rainLight', 0.02), ('wetness', 1e-3),
                         ('streakLen', 1e-4)):
            check('%s %s: EEVEE %.4f, WebGPU %.4f' % (name, key, rec[key], w[key]), abs(rec[key] - w[key]) <= tol)
        dc = max(abs(a - b) for a, b in zip(rec['rainColor'], w['rainColor']))
        check('%s rainColor within 0.02 of WebGPU' % name, dc <= 0.02, '%s vs %s' % (rec['rainColor'], w['rainColor']))
        # the Blender sky drifts its field with the wind (Eanpa's), this engine against it (sky-weather.md, Wind
        # direction): compare with the WebGPU gate under the Blender drift, and the plan rains under both
        wb = w.get('gateBlenderDrift', w['gate'])
        check('%s the camera column rains in both (gate EEVEE %.2f; WebGPU %.2f, %.2f under the Blender drift)'
              % (name, rec['gate'], w['gate'], wb), abs(rec['gate'] - wb) < 0.1 and w['gate'] > 0.9)
        check('%s no flash in either frame' % name, rec['flash'] < 0.01 and w['flash'] < 0.01,
              (rec['flash'], w['flash']))
    if name in args.variants.split(','):
        node = next(n for n in bpy.data.materials['eido_rain'].node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage')
        was = node.interpolation
        rec['variants'] = {}
        for vname, v in VARIANTS.items():
            node.interpolation = v['interp']
            sc.render.filter_size = v['filter'] if v['filter'] is not None else 1.5
            pv = render(os.path.join(OUT, 'eevee_%s_%s.png' % (name, vname)))
            if v['filter'] is not None:              # its own rain-hidden twin at that filter
                for m in gens:
                    m.show_render = False
                pd = render(os.path.join(OUT, 'eevee_%s_norain_%s.png' % (name, vname)))
                for m in gens:
                    m.show_render = True
            else:
                pd = p_dry
            rec['variants'][vname] = rain_metrics(pv, pd)
        node.interpolation = was
        sc.render.filter_size = 1.5
    results.append(rec)
    print('[rain_ab] %s' % json.dumps(rec), flush=True)
    print('[rain_ab] %s done in %.1fs' % (name, time.time() - t0), flush=True)

with open(os.path.join(OUT, 'rain_ab_blender%s.json' % TAG), 'w', encoding='utf-8') as fh:
    json.dump(dict(records=results), fh, indent=1)

# the sheet: per state, WebGPU | EEVEE
try:
    from PIL import Image, ImageDraw
    tiles = []
    for rec in results:
        row = []
        for label, p in (('WebGPU', web_png.get((rec['name'], True))),
                         ('EEVEE' + (' ' + args.tag if args.tag else ''),
                          os.path.join(OUT, 'eevee_%s%s.png' % (rec['name'], TAG)))):
            if p and os.path.exists(p):
                im = Image.open(p).convert('RGB').resize((W // 2, H // 2), Image.LANCZOS)
                ImageDraw.Draw(im).text((6, 4), '%s  %s t=%.1fs' % (label, rec['name'], rec['T']), fill=(255, 255, 0))
                row.append(im)
        if row:
            tiles.append(row)
    if tiles:
        sheet = Image.new('RGB', (W, (H // 2) * len(tiles)))
        for j, row in enumerate(tiles):
            for i, im in enumerate(row):
                sheet.paste(im, (i * (W // 2), j * (H // 2)))
        sheet.save(os.path.join(OUT, 'rain_ab_sheet%s.png' % TAG))
except Exception as e:                       # the sheet is a convenience; the numbers above are the result
    print('[rain_ab] no sheet: %s' % e, flush=True)
print('RESULT ' + ('PASS' if not fails else 'FAIL (%d)' % len(fails)), flush=True)
