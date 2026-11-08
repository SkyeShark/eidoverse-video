"""The cloud dome and the spatial (downsampled) camera layer, on Earth with a mountain range 9 km away.

  dome:    the same overcast-ish cumulus shot with and without make_sky(cloud_dome=3072). Without it the far ridge
           draws over every cloud (the EEVEE world is behind everything); with it the clouds draw over the ridge where
           they cover it, as WebGPU's 3 km cloud dome does. Checks: inside the ridge, the dome render's pixels where
           the cloud layer is dense differ from the no-dome render; sky pixels match it (the dome adds nothing twice).
  spatial: make_spatial_cloud_pass(sky, div=2) halves the camera layer; the render matches the full-resolution one.

    bash run_blender.sh blender/tests/sky_worlds/dome_and_spatial.py [--res 960x540] [--samples 16]
Writes out/dome/*.png (the two shots side by side in dome_sheet.png).
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky.cloud_spatial import make_spatial_cloud_pass  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'dome')
os.makedirs(OUT, exist_ok=True)
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, H = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.frame_start = sc.frame_end = 1
    sc.render.image_settings.file_format = 'PNG'
    m = bpy.data.materials.new('rock')
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.13, 0.11, 1)
    g = bpy.data.materials.new('ground')
    g.use_nodes = True
    g.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.12, 0.14, 0.07, 1)
    bpy.ops.mesh.primitive_plane_add(size=40000)
    bpy.context.object.data.materials.append(g)
    # a ridge of tall peaks 9 km out, reaching 2.5 km: well past the dome's 3 km and up into the cloud layer's view
    for i in range(9):
        x = -6000 + i * 1500
        h = 1600 + 900 * math.sin(i * 1.7) ** 2
        bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=1300, radius2=60, depth=h, location=(x, 9000, h / 2))
        bpy.context.object.data.materials.append(m)
    cd = bpy.data.cameras.new('cam')
    cd.lens_unit = 'FOV'
    cd.angle = math.radians(70)
    cd.clip_end = 30000.0                # the ridge stands 9 km out (Blender's default clip end is 100 m)
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0, 0, 2)
    cam.rotation_euler = (math.radians(98), 0, 0)
    return sc, cam


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return px


def read_exr(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return px


shots = {}
geometry = None
for tag, dome in (('nodome', None), ('dome', 3072.0)):
    sc, cam = scene()
    sky = make_sky(sc, camera=cam, world='earth', hours=15.0, clouds='cumulus', cache_dir=os.path.join(OUT, 'cache_' + tag),
                   quality='draft', cloud_dome=dome, shadows=False)
    sky.set_clouds('cumulus', {'largeT': 0.25})      # a fuller deck (a preset override), so clouds cross the ridge
    sky.bake(log=lambda *a: None)
    shots[tag] = render(sc, os.path.join(OUT, 'dome_%s.png' % tag))
    if geometry is None:
        # where the scene's geometry is: the alpha of a transparent-film render (the world drops out)
        sc.render.film_transparent = True
        sc.render.image_settings.color_mode = 'RGBA'
        mpath = os.path.join(OUT, 'dome_geometry_mask.png')
        sc.render.filepath = mpath
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(mpath)
        w, h = img.size
        geometry = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., 3] > 0.5
        bpy.data.images.remove(img)
        sc.render.film_transparent = False
a, b = shots['nodome'], shots['dome']
lum = lambda x: x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
H, W = a.shape[:2]
la, lb = lum(a), lum(b)
# the ridge: geometry above the horizon (the ground plane's far edge sits a few rows below the cones' feet)
rows = np.arange(H)[:, None] * np.ones((1, W))
ground_top = max(r for r in range(H) if geometry[r].all()) if geometry.any() else 0   # last full row (bottom-up)
ridge = geometry & (rows > ground_top + 2)
sky_px = ~geometry
diff_ridge = np.abs(lb - la)[ridge].mean() if ridge.any() else float('nan')
diff_sky = np.abs(lb - la)[sky_px].mean()
check('dome: clouds now draw over the far ridge', diff_ridge > 0.02, 'mean |delta luma| over the ridge %.4f' % diff_ridge)
check('dome: the open sky is unchanged (clouds composited once)', diff_sky < 0.01, 'mean |delta luma| over sky %.4f' % diff_sky)
sheet = np.concatenate([a, b], axis=1)
im = bpy.data.images.new('dome_sheet', sheet.shape[1], sheet.shape[0])
px = np.ones((sheet.shape[0], sheet.shape[1], 4), np.float32)
px[..., :3] = sheet
im.pixels.foreach_set(px.ravel())
im.filepath_raw = os.path.join(OUT, 'dome_sheet.png')
im.file_format = 'PNG'
im.save()

# ---- spatial pass ----
sc, cam = scene()
sky = make_sky(sc, camera=cam, world='earth', hours=15.0, clouds='cumulus', cache_dir=os.path.join(OUT, 'cache_spatial'),
               quality='draft', shadows=False)
sky.set_clouds('cumulus', {'largeT': 0.25})
sp = make_spatial_cloud_pass(sky, div=2)
res = sp.get_resolution()
sky.bake(log=lambda *a: None)
layer = read_exr(os.path.join(OUT, 'cache_spatial', 'sky_cam_0001.exr'))
full_w = math.ceil(sc.render.resolution_x * 1.16)
check('spatial pass: the camera layer is baked at 1/2', abs(layer.shape[1] - math.ceil(full_w / 2)) <= 1,
      'layer %dx%d, full %d, get_resolution %s' % (layer.shape[1], layer.shape[0], full_w, res))
half = render(sc, os.path.join(OUT, 'spatial_div2.png'))
d = np.abs(lum(half) - la).mean()
check('spatial pass: the 1/2 layer renders the same sky as the full one', d < 0.02, 'mean |delta luma| %.4f' % d)
sp.dispose()
check('spatial pass: dispose restores full resolution', sky.layer_scale == 1.0)
print('PASS dome_and_spatial all' if ok_all else 'FAIL dome_and_spatial some')
