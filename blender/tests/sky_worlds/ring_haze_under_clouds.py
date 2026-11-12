"""The ringworld's haze walls under the clouds, as WebGPU draws them (its cloud dome, -98, over the walls, -99).

A storm at 10:30 over the ringworld stage (a 600 m ground disc), the camera at eye height looking up the ring along +Y
at the horizon and across it along +X, with make_sky(cloud_dome=True):
  under_dome   the bake's own order: the walls drawn before the dome (Ringworld.order_walls_under_dome)
  over_dome    the walls drawn after the dome (the walls themselves, without their copies): the clouds veiled
  no_walls     the walls out of the render
Read through the frame's own cloud layer (sky_cloud_0001.exr, mapped onto the render's pixels): where the clouds are
opaque (alpha > 0.9) under_dome must equal no_walls (the walls do not show through the clouds) while over_dome shows
their veil; where the cloud layer is clear (alpha < 0.05) the walls must show the same both ways. Without the dome
(the default sky) the clouds are in the world and the walls veil them: that difference is printed for the guide.

    bash run_blender.sh blender/tests/sky_worlds/ring_haze_under_clouds.py [--res 960x540] [--samples 16]
Writes out/haze_under_clouds/ (renders and sheet.png) and prints PASS/FAIL per numeric check.
"""
import argparse
import math
import os
import sys
import time

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
ap.add_argument('--weather', default='storm')
ap.add_argument('--exposure', type=float, default=0.6)
args = ap.parse_args(argv)
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'haze_under_clouds')
os.makedirs(OUT, exist_ok=True)
OVERSCAN = 0.08
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  (' + str(detail) + ')') if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.eevee.use_fast_gi = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = args.exposure
sc.render.fps = 24
sc.frame_start = sc.frame_end = 1
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'OPEN_EXR'
sc.render.image_settings.color_depth = '32'
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=600, fill_type='NGON')
ground = bpy.context.object
m = bpy.data.materials.new('ground')
m.use_nodes = True
m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.18, 0.15, 0.11, 1)
m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
ground.data.materials.append(m)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
cam.data.lens = 24.0
sc.collection.objects.link(cam)
sc.camera = cam
sky = make_sky(sc, camera=cam, world='ringworld', hours=args.hours, weather=args.weather, cloud_dome=True,
               cache_dir=os.path.join(OUT, 'cache'), weather_fx=False)
ring = sky.ring


def read_exr(path):
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        return px.reshape(h, w, 4)[::-1]                    # top row first, as the frame reads
    finally:
        bpy.data.images.remove(img)


def cloud_alpha():
    """The frame's cloud layer alpha on the render's pixels (the layer spans the frame plus OVERSCAN each side)."""
    lay = read_exr(os.path.join(sky.cache_dir, 'sky_cloud_0001.exr'))[..., 3]
    lh, lw = lay.shape
    nx = ((np.arange(W) + 0.5) / W * 2 - 1) / (1 + 2 * OVERSCAN)
    ny = (1 - (np.arange(H) + 0.5) / H * 2) / (1 + 2 * OVERSCAN)
    cols = np.clip(np.round((nx + 1) / 2 * lw - 0.5).astype(int), 0, lw - 1)
    rows = np.clip(np.round((1 - (ny + 1) / 2) * lh - 0.5).astype(int), 0, lh - 1)
    return lay[rows][:, cols]


views = (('up_the_ring', (0.0, 1.0, math.tan(math.radians(4.0)))), ('across_the_ring', (1.0, 0.0, math.tan(math.radians(4.0)))))
items = []
for vname, d in views:
    from mathutils import Vector
    cam.location = (0.0, 0.0, 1.7)
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = Vector(d).normalized().to_track_quat('-Z', 'Y')
    t0 = time.time()
    sky.bake(log=lambda *a: None)                              # the dome on: the walls' copies draw before it
    copies = [o for o in sc.objects if o.name.endswith('_under_dome')]
    walls = [w for w in (ring.fog_wall, ring.rain_wall) if w is not None]
    alpha = cloud_alpha()
    renders = {}

    def render(tag):
        """The linear EXR for the numbers, and the frame through its own view (AgX) as a PNG to look at."""
        p = os.path.join(OUT, '%s_%s.exr' % (vname, tag))
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        renders[tag] = read_exr(p)[..., :3]
        ims = sc.render.image_settings
        ims.file_format, ims.color_depth = 'PNG', '8'
        bpy.data.images['Render Result'].save_render(p[:-4] + '.png', scene=sc)
        ims.file_format, ims.color_depth = 'OPEN_EXR', '32'
        return p

    sc.view_layers[0].update()
    check('%s: with the dome the bake draws the walls by their copies (riding farther than the dome)' % vname,
          len(copies) == len(walls) and all(w.hide_render for w in walls)
          and all((c.matrix_world.translation - cam.matrix_world.translation).length > 1.5e6 for c in copies))
    render('under_dome')
    for c in copies:                                           # the walls themselves: drawn after the dome
        c.hide_render = True
    for w in walls:
        w.hide_render = False
    render('over_dome')
    for w in walls:
        w.hide_render = True
    render('no_walls')
    for w in walls:
        w.hide_render = False
    ring.order_walls_under_dome(cam, on=False)
    sky.use_cloud_dome(None)
    sky.bake(log=lambda *a: None)
    render('default_no_dome')
    for w in walls:
        w.hide_render = True
    render('default_no_dome_no_walls')
    for w in walls:
        w.hide_render = False
    sky.use_cloud_dome(3072.0)
    sky_px = np.ones((H, W), bool)
    sky_px[int(H * 0.62):] = False                              # above the stage's ground and the walls' foot
    opaque = (alpha > 0.9) & sky_px
    clear = (alpha < 0.05) & sky_px
    u, o, n = renders['under_dome'], renders['over_dome'], renders['no_walls']
    wall_px = sky_px & (np.abs(o - n).max(axis=2) > 0.002)      # where the walls change the sky at all
    oq, cl = opaque & wall_px, clear & wall_px
    du_o = float(np.abs(u - n)[oq].mean()) if oq.any() else 0.0
    do_o = float(np.abs(o - n)[oq].mean()) if oq.any() else 0.0
    d_cl = float(np.abs(u - o)[cl].mean()) if cl.any() else 0.0
    w_cl = float(np.abs(o - n)[cl].mean()) if cl.any() else 0.0
    print('[haze] %s: %d px of opaque cloud over the walls, %d px of clear sky over them; bake %.1fs'
          % (vname, int(oq.sum()), int(cl.sum()), time.time() - t0), flush=True)
    check('%s: under opaque cloud the walls no longer show through (under the dome %.4f, over it %.4f, linear)'
          % (vname, du_o, do_o), oq.sum() > 200 and du_o < 0.25 * do_o, '%d px' % int(oq.sum()))
    check('%s: in clear sky the walls show alike both ways (%.4f apart, their veil %.4f)' % (vname, d_cl, w_cl),
          cl.sum() < 50 or d_cl < 0.25 * max(w_cl, 1e-4), '%d px' % int(cl.sum()))
    dn = np.abs(renders['default_no_dome'] - renders['default_no_dome_no_walls'])
    print('[haze] %s: without the dome the walls veil the sky (and its clouds) by a mean of %.4f linear over the frame,'
          ' %.4f at most' % (vname, float(dn.mean()), float(dn.max())), flush=True)
    for tag in ('under_dome', 'over_dome', 'no_walls', 'default_no_dome'):
        items.append((os.path.join(OUT, '%s_%s.png' % (vname, tag)), '%s: %s' % (vname, tag)))
from PIL import Image, ImageDraw  # noqa: E402
sheet = Image.new('RGB', (W * 4, H * len(views)))
for i, (p, label) in enumerate(items):
    im = Image.open(p).convert('RGB')
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, 8 + 7 * len(label), 20), fill=(0, 0, 0))
    dr.text((6, 4), label, fill=(255, 255, 255))
    sheet.paste(im, ((i % 4) * W, (i // 4) * H))
sheet.save(os.path.join(OUT, 'sheet.png'))
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
