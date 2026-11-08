"""Reflections see the sky; the weather and `ambient` dim only the diffuse fill.

A perfect mirror floor (metallic, white, roughness 0) and a white diffuse sphere, the horizon at the frame's
centre. The sky band above the horizon is compared with its reflection below it (the reflection of the sky at
elevation e lies at depression e): the mirror must hold the sky's brightness (ratio ~1) whatever the weather's
hemiDim and the ambient value, while the diffuse sphere must follow the fill.

    runs: cumulus 15:00 (hemiDim 1), rain 15:00 (hemiDim 0.65) at ambient 1.0 and at ambient 0.5
    bash run_blender.sh blender/tests/sky/probe_reflection.py      (renders: through the GPU slot)
Writes blender/tests/sky/out/reflection/ (float EXRs for the numbers, AgX PNGs to look at).
"""
import math
import os
import sys

import bpy
import bmesh
import numpy as np
import OpenImageIO as oiio
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky  # noqa: E402

OUT = os.path.join(HERE, 'out', 'reflection')
os.makedirs(OUT, exist_ok=True)
W, H = 480, 270
RUNS = (('cumulus_amb1', None, 1.0), ('rain_amb1', 'rain', 1.0), ('rain_amb05', 'rain', 0.5))


def material(name, color, rough, metal):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 16
    sc.eevee.use_raytracing = True
    sc.frame_start = sc.frame_end = 1
    sc.render.image_settings.media_type = 'IMAGE'
    me = bpy.data.meshes.new('mirror')
    me.from_pydata([(-3000, -3000, 0), (3000, -3000, 0), (3000, 3000, 0), (-3000, 3000, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(material('mirror', (1.0, 1.0, 1.0), 0.0, 1.0))
    sc.collection.objects.link(bpy.data.objects.new('mirror', me))
    sm = bpy.data.meshes.new('white')
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=0.6)
    bm.to_mesh(sm)
    for p in sm.polygons:
        p.use_smooth = True
    sm.materials.append(material('white', (0.8, 0.8, 0.8), 1.0, 0.0))
    sphere = bpy.data.objects.new('white', sm)
    sc.collection.objects.link(sphere)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 24.0
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam, sphere


def lum(a):
    return a[..., :3] @ np.array([0.2126, 0.7152, 0.0722])


rows = []
for tag, weather, ambient in RUNS:
    sc, cam, sphere = scene()
    sky = make_sky(sc, camera=cam, hours=15.0, clouds='cumulus', weather=weather, ambient=ambient,
                   cache_dir=os.path.join(OUT, '_cache', tag), shadows=False)
    sd = sky.sun_dir
    yaw = math.radians(math.degrees(math.atan2(-sd[0], sd[1])) - 100.0)         # sun on the left, a little behind
    cam.location = (0.0, 0.0, 1.6)
    cam.rotation_euler = (math.radians(90.0), 0.0, yaw)                          # level: horizon at mid-frame
    fwd, right = (-math.sin(yaw), math.cos(yaw)), (math.cos(yaw), math.sin(yaw))
    sphere.location = (fwd[0] * 8 - right[0] * 3.2, fwd[1] * 8 - right[1] * 3.2, 0.6)
    frames = sky.bake(log=lambda *a: None)
    # numbers: linear EXR
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    sc.render.filepath = os.path.join(OUT, tag + '.exr')
    bpy.ops.render.render(write_still=True)
    img = np.asarray(oiio.ImageBuf(sc.render.filepath).get_pixels(oiio.FLOAT))[::-1]      # row 0 = bottom
    Y = lum(img)
    c = H // 2
    cols = slice(W // 2, W)                                    # the half away from the sphere
    sky_band = np.array([Y[c + k, cols].mean() for k in range(6, 40)])
    mir_band = np.array([Y[c - 1 - k, cols].mean() for k in range(6, 40)])
    ratio = float(mir_band.mean() / sky_band.mean())
    p = world_to_camera_view(sc, cam, sphere.location)
    sx, sy = int(p.x * W), int(p.y * H)
    sph = float(Y[sy - 4:sy + 5, sx - 4:sx + 5].mean())
    rows.append((tag, frames[0]['lights']['hemi_dim'], ambient, ratio, sph, sky_band.mean()))
    print('[reflection] %-13s hemiDim %.2f ambient %.1f  mirror/sky %.3f  sky %.3f  white sphere %.4f'
          % (tag, frames[0]['lights']['hemi_dim'], ambient, ratio, sky_band.mean(), sph))
    # look: AgX PNG
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.filepath = os.path.join(OUT, tag + '.png')
    bpy.ops.render.render(write_still=True)

ok_mirror = all(0.93 < r[3] < 1.07 for r in rows)
d1 = {r[0]: r for r in rows}
fill = d1['rain_amb05'][4] / d1['rain_amb1'][4]
ok_fill = fill < 0.85
print(('PASS' if ok_mirror else 'FAIL') + ' mirrors hold the sky in every run (mirror/sky %s)'
      % ', '.join('%.3f' % r[3] for r in rows))
print(('PASS' if ok_fill else 'FAIL') + ' the diffuse sphere follows ambient (0.5 vs 1.0: %.2f of it)' % fill)
