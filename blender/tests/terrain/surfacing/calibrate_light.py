"""What an albedo renders as under the review rig's light (system Python cannot answer this: AgX's curve, make_sky's
sun and sky): a chart of grey and coloured patches on flat ground, on a wall facing the camera and on a wall facing
the sun, lit exactly as review_views.py lights a view (make_sky 'earth' at RR.SUN_ELEV_HOURS, the sun 70 degrees left
of the view, AgX Medium High Contrast, exposure -0.5, EEVEE, 16 samples), and the displayed sRGB of each patch
measured from the render. The palettes' colours are set from the photographs through this table: a photographed
colour on a sunlit slope is matched by the albedo that renders to it here, not by the photograph's own pixel values.

    bash run_blender.sh blender/tests/terrain/surfacing/calibrate_light.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Writes out/surfacing/calibration/chart.png and chart.json ({orientation: [[albedo or colour, displayed sRGB], ...]}).
"""
import json
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'surfacing', 'calibration')
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402

W, H = 960, 540
GREYS = [0.02, 0.04, 0.06, 0.09, 0.12, 0.16, 0.2, 0.26, 0.33, 0.42, 0.55, 0.7, 0.85]
# linear colours: meadow greens, forest, limestone greys, red sandstone, tan, snow
COLOURS = {'meadow_a': (0.10, 0.20, 0.03), 'meadow_b': (0.07, 0.15, 0.025), 'meadow_c': (0.14, 0.24, 0.05),
           'forest_a': (0.025, 0.05, 0.018), 'forest_b': (0.04, 0.075, 0.025), 'lime_a': (0.12, 0.115, 0.10),
           'lime_b': (0.18, 0.17, 0.15), 'red_a': (0.20, 0.08, 0.045), 'red_b': (0.30, 0.13, 0.07),
           'tan_a': (0.32, 0.22, 0.13), 'snow': (0.75, 0.78, 0.82)}


def patch(name, loc, rot, size, rgb):
    me = bpy.data.meshes.new(name)
    s = size / 2.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = 0.9
    b.inputs['Specular IOR Level'].default_value = 0.3
    me.materials.append(m)
    return ob


def main():
    os.makedirs(OUT, exist_ok=True)
    sc = RR.new_scene((W, H), 16, -0.5)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 35.0
    cam.data.sensor_width = 36.0
    # the camera looks north (+y) from 30 m south, 14 m up; the sun is then 70 degrees left of the view (west-north-west)
    RR.place_camera(cam, (0.0, -30.0, 14.0), (0.0, 4.0, 1.5))
    # a big grey ground (the bounce light a landscape gives), the patches on and above it
    patch('ground', (0, 0, -0.02), (0, 0, 0), 4000.0, (0.12, 0.12, 0.11))
    # the sun's heading from the view, as review_views.render computes it
    bpy.context.view_layer.update()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    sun_xy = (math.cos(hd), math.sin(hd))
    rows = {'flat': [], 'wall_to_camera': [], 'wall_to_sun': []}
    items = [(f'{g:.2f}', (g, g, g)) for g in GREYS] + list(COLOURS.items())
    n = len(items)
    step = 1.25
    x0 = -0.5 * (n - 1) * step
    for k, (label, rgb) in enumerate(items):
        x = x0 + k * step
        rows['flat'].append((label, rgb, patch(f'f_{label}', (x, -6.0, 0.0), (0, 0, 0), 1.1, rgb)))
        # a wall whose normal points back at the camera (-y), standing on the ground
        rows['wall_to_camera'].append((label, rgb, patch(f'c_{label}', (x, 2.0, 1.0), (math.radians(90), 0, 0),
                                                         1.1, rgb)))
        # a wall turned to face the sun's azimuth
        az = math.atan2(sun_xy[1], sun_xy[0])
        rows['wall_to_sun'].append((label, rgb, patch(f's_{label}', (x, 8.0, 2.4),
                                                      (math.radians(90), 0, az - math.radians(90) + math.pi), 1.1,
                                                      rgb)))
    cache = os.path.join(OUT, '_sky')
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    path = os.path.join(OUT, 'chart.png')
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)
    img = bpy.data.images.load(path)
    px = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(H, W, 4)
    out = {}
    for row, lst in rows.items():
        res = []
        for label, rgb, ob in lst:
            # the patch's centre in the image (the normal's side: the patch's local centre), a 5 x 5 pixel mean
            co = world_to_camera_view(sc, cam, ob.matrix_world.translation)
            i, j = int(co.x * W), int(co.y * H)
            if not (2 <= i < W - 2 and 2 <= j < H - 2):
                res.append([label, list(rgb), None])
                continue
            v = px[j - 2:j + 3, i - 2:i + 3, :3].reshape(-1, 3).mean(0)
            res.append([label, [round(c, 4) for c in rgb], [int(round(255 * c)) for c in v]])
        out[row] = res
    with open(os.path.join(OUT, 'chart.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(sun_left_deg=RR.SUN_LEFT_DEG, sun_hours=RR.SUN_ELEV_HOURS, exposure=-0.5,
                       look=sc.view_settings.look, rows=out), f, indent=1)
    for row, res in out.items():
        print(f'[calibrate] {row}:', '; '.join(f'{lb} -> {v}' for lb, _c, v in res), flush=True)
    os._exit(0)


main()
