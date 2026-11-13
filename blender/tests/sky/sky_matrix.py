"""Coverage probe: every cloud preset at four times of day, every weather state, on one small stage.

Each cell is its own make_sky + bake + EEVEE render (white / grey / chrome spheres on a ground plane, the
camera side-on to the key light, which is the sun by day and the moon at night). Cells land in
blender/tests/sky/out/matrix/<name>.png; a labelled contact sheet is assembled afterwards with
contact_sheet_matrix.py (system Python, Pillow).

    bash run_blender.sh blender/tests/sky/sky_matrix.py [--only cumulus_1630,storm_1500] [--res 480x270]
"""
import argparse
import math
import os
import sys
import time

import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--only', default='')
ap.add_argument('--res', default='480x270')
ap.add_argument('--samples', type=int, default=12)
ap.add_argument('--quality', default='film')
ap.add_argument('--exposure', type=float, default=0.6)
ap.add_argument('--pitch', type=float, default=14.0)
ap.add_argument('--cirrus-atlas', default=None, help='an ice-trail atlas to read (e.g. Eanpa\'s, read only)')
ap.add_argument('--suffix', default='')
args = ap.parse_args(argv)

CELLS = []
for clouds in ('cumulus', 'stratus', 'cirrus', 'clear'):
    for hours, tag in ((12.0, '1200'), (16.5, '1630'), (18.15, '1809'), (22.0, '2200')):
        CELLS.append(('%s_%s' % (clouds, tag), dict(clouds=clouds, hours=hours)))
for weather in ('fair', 'sunshower', 'overcast', 'rain', 'storm', 'cyclone', 'darkstorm'):
    CELLS.append(('%s_1500' % weather, dict(clouds='cumulus', weather=weather, hours=15.0)))
if args.only:
    keep = set(args.only.split(','))
    CELLS = [c for c in CELLS if c[0] in keep]

OUT = os.path.join(HERE, 'out', 'matrix')
CACHE_TEX = os.path.normpath(os.path.join(REPO, '..', 'eidoverse-video-prealpha-0.01', 'eidoverse', 'assets',
                                          'cache', 'textures', 'Ground037_2k'))
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W, H = (int(v) for v in args.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = args.exposure
sc.frame_start = sc.frame_end = 1
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'


def material(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def ground_material():
    m = material('ground', (0.12, 0.14, 0.07), 0.9)
    if os.path.isdir(CACHE_TEX):
        nt = m.node_tree
        b = nt.nodes['Principled BSDF']
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (0.25, 0.25, 0.25)
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        col = nt.nodes.new('ShaderNodeTexImage')
        col.image = bpy.data.images.load(os.path.join(CACHE_TEX, 'Ground037_Color.jpg'))
        nt.links.new(mp.outputs['Vector'], col.inputs['Vector'])
        nt.links.new(col.outputs['Color'], b.inputs['Base Color'])
    return m


me = bpy.data.meshes.new('ground')
me.from_pydata([(-4000, -4000, 0), (4000, -4000, 0), (4000, 4000, 0), (-4000, 4000, 0)], [], [(0, 1, 2, 3)])
me.materials.append(ground_material())
sc.collection.objects.link(bpy.data.objects.new('ground', me))
spheres = []
for name, col, rough, metal in (('white', (0.8, 0.8, 0.8), 0.9, 0.0), ('grey', (0.18, 0.18, 0.18), 0.7, 0.0),
                                ('chrome', (0.95, 0.95, 0.95), 0.03, 1.0)):
    sm = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=0.5)
    bm.to_mesh(sm)
    for p in sm.polygons:
        p.use_smooth = True
    sm.materials.append(material(name, col, rough, metal))
    ob = bpy.data.objects.new(name, sm)
    sc.collection.objects.link(ob)
    spheres.append(ob)

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
cam.data.lens = 24
sc.collection.objects.link(cam)
sc.camera = cam
sun = None
t_all = time.time()
for name, kw in CELLS:
    t0 = time.time()
    probe = make_sky(sc, camera=cam, cache_dir=os.path.join(OUT, '_cache', name), sun=sun, shadows=False,
                     weather_fx=False, **kw)
    sun = probe.sun
    probe.update(0.0)
    key = probe.lights['key_dir']                       # three.js: sun by day, moon at night
    kb = (key[0], -key[2])                              # its Blender heading
    key_yaw = math.degrees(math.atan2(-kb[0], kb[1]))
    yaw = math.radians(key_yaw - 100.0)                 # key light on the left, a little behind
    cam.location = (0.0, 0.0, 1.6)
    cam.rotation_euler = (math.radians(90 + args.pitch), 0.0, yaw)
    fwd, right = (-math.sin(yaw), math.cos(yaw)), (math.cos(yaw), math.sin(yaw))
    for ob, lat in zip(spheres, (-1.5, 0.0, 1.5)):
        ob.location = (fwd[0] * 7 + right[0] * lat, fwd[1] * 7 + right[1] * lat, 0.5)
    if args.cirrus_atlas:
        kw = dict(kw, cirrus_atlas=args.cirrus_atlas)
    sky = make_sky(sc, camera=cam, cache_dir=os.path.join(OUT, '_cache', name), sun=sun, quality=args.quality,
                   weather_fx=False, **kw)
    sky.use_fog(density=0.0003)
    sky.bake(log=lambda *a: None)
    sc.render.filepath = os.path.join(OUT, name + args.suffix + '.png')
    bpy.ops.render.render(write_still=True)
    L = sky.lights
    print('[matrix] %-16s sun %.2f %s key el %.1f  hemi_dim %.2f  %.1fs' % (
        name, L['sun_intensity'], tuple(round(c, 2) for c in L['sun_color']),
        math.degrees(math.asin(max(-1, min(1, L['key_dir'][1])))), L['hemi_dim'], time.time() - t0))
print('[matrix] %d cells in %.1fs' % (len(CELLS), time.time() - t_all))
