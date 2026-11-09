"""Render a sky world from a small stage: make_sky(world=...) at the given hours, from several views.

The stage is a 1.2 km ground disc (the shared Ground037 set when the texture cache has it), white / grey / chrome
spheres and a dark monolith for light, scale and contact. Each view bakes the sky for its camera and renders an EEVEE
still into out/<world>/<world>_<hours>_<view>.png; numbers per view go to the log (PASS/FAIL lines for the checks).

    bash run_blender.sh blender/tests/sky_worlds/world_views.py --world ringworld --hours 11,23 --views horizon,up
        [--res 960x540] [--samples 16] [--quality draft|film] [--clouds cumulus] [--weather fair] [--exposure 0.6]
        [--dome 3072] [--frames 1] [--save-blend] [--out folder] [--tag _name] [--plate-scale 1]
Views: horizon (level, along +Y: up the ring), up (60 deg up the ring), side (along +X, across the band),
       giant (at the red giant), moon (at the shattered moon), sun (at the sun), down (the stage from 60 m).
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
from eidoblend.sky import palette as P  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--world', default='ringworld')
ap.add_argument('--hours', default='11,23')
ap.add_argument('--views', default='horizon,up')
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--quality', default='draft')
ap.add_argument('--clouds', default='cumulus')
ap.add_argument('--weather', default=None)
ap.add_argument('--exposure', type=float, default=0.6)
ap.add_argument('--dome', type=float, default=None)
ap.add_argument('--frames', type=int, default=1)
ap.add_argument('--fov', type=float, default=62.0)
ap.add_argument('--tag', default='')
ap.add_argument('--save-blend', action='store_true')
ap.add_argument('--ring-opts', default='', help='k=v,k=v make_ringworld options (numbers, true/false, words)')
ap.add_argument('--out', default=None, help='output folder (default out/<world>)')
ap.add_argument('--plate-scale', type=float, default=1.0, help='the ringworld band plate against the frame')
args = ap.parse_args(argv)

OUT = args.out or os.path.join(HERE, 'out', args.world)
os.makedirs(OUT, exist_ok=True)
CACHE_TEX = os.path.normpath(os.path.join(REPO, '..', 'eidoverse-video-prealpha-0.01', 'eidoverse', 'assets', 'cache',
                                          'textures'))


def check(name, ok, detail=''):
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)
    return ok


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, H = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.eevee.use_raytracing = True
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = args.exposure
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    return sc


def material(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def ground_material():
    m = bpy.data.materials.new('stage_ground')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    d = os.path.join(CACHE_TEX, 'Ground037_2k')
    if os.path.isdir(d):
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (0.25, 0.25, 0.25)
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])

        def tex(fn, nc=False):
            n = nt.nodes.new('ShaderNodeTexImage')
            n.image = bpy.data.images.load(os.path.join(d, fn), check_existing=True)
            if nc:
                n.image.colorspace_settings.name = 'Non-Color'
            nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
            return n
        nt.links.new(tex('Ground037_Color.jpg').outputs['Color'], b.inputs['Base Color'])
        nt.links.new(tex('Ground037_Roughness.jpg', True).outputs['Color'], b.inputs['Roughness'])
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(tex('Ground037_NormalGL.jpg', True).outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    else:
        b.inputs['Base Color'].default_value = (0.18, 0.15, 0.11, 1)
        b.inputs['Roughness'].default_value = 0.9
    return m


def build_stage(sc):
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=600, fill_type='NGON', location=(0, 0, 0))
    g = bpy.context.object
    g.name = 'stage_ground'
    g.data.materials.append(ground_material())
    for i, (name, col, rough, metal) in enumerate((('white', (0.8, 0.8, 0.8), 0.5, 0.0),
                                                  ('grey', (0.18, 0.18, 0.18), 0.5, 0.0),
                                                  ('chrome', (0.95, 0.95, 0.95), 0.03, 1.0))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.5, location=(-1.4 + i * 1.4, 7.0, 0.5))
        s = bpy.context.object
        s.name = 'sphere_' + name
        bpy.ops.object.shade_smooth()
        s.data.materials.append(material('ref_' + name, col, rough, metal))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(3.2, 9.0, 1.6))
    mono = bpy.context.object
    mono.name = 'monolith'
    mono.scale = (0.6, 0.3, 3.2)
    mono.data.materials.append(material('monolith', (0.05, 0.05, 0.055), 0.35))


def make_camera(sc):
    cd = bpy.data.cameras.new('cam')
    cd.lens_unit = 'FOV'
    cd.angle = math.radians(args.fov)
    cd.clip_start = 0.1
    cd.clip_end = 2000.0
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def aim(cam, yaw_deg, pitch_deg, loc=(0.0, 0.0, 1.7)):
    cam.location = loc
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (math.radians(90 + pitch_deg), 0.0, math.radians(-yaw_deg))


def dir_angles(d):
    """yaw (from +Y toward +X) and pitch of a Blender direction"""
    return math.degrees(math.atan2(d[0], d[1])), math.degrees(math.asin(max(-1, min(1, d[2]))))


def luma(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return px[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)


ok_all = True
hours_list = [float(h) for h in args.hours.split(',')]
views = args.views.split(',')
for hours in hours_list:
    sc = setup_scene()
    build_stage(sc)
    cam = make_camera(sc)
    aim(cam, 0, 5)
    t0 = time.time()
    ro = {}
    for kv in filter(None, args.ring_opts.split(',')):
        k, v = kv.split('=')
        if v.lower() in ('true', 'false'):
            ro[k] = v.lower() == 'true'
        else:
            try:
                ro[k] = float(v)
            except ValueError:
                ro[k] = v            # a string option: waves=full, debugBand=lighting
    if ro:
        print('[world_views] ring options %s' % ro, flush=True)
    extra = dict(ring=ro) if ro else {}
    sky = make_sky(sc, camera=cam, world=args.world, hours=hours, clouds=args.clouds, weather=args.weather,
                   cache_dir=os.path.join(OUT, 'cache_%s%s_%05.2f' % (args.world, args.tag, hours)),
                   quality=args.quality, cloud_dome=args.dome, **extra)
    print('[world_views] %s (%s) built in %.1fs' % (args.world, sky.label, time.time() - t0), flush=True)
    for view in views:
        sky._reset_state()
        sky.update(0.0)
        sdir, mdir = sky.sun_dir, sky.moon_dir
        if view == 'horizon':
            aim(cam, 0, 6)
        elif view == 'up':
            aim(cam, 0, 60)
        elif view == 'side':
            aim(cam, 90, 10)
        elif view == 'back':
            aim(cam, 180, 8)
        elif view == 'down':
            aim(cam, 20, -35, loc=(0.0, -60.0, 60.0))
        elif view in ('giant', 'sun'):
            y, p = dir_angles(sdir)
            aim(cam, y, max(p, 4.0))
        elif view == 'moon':
            mo = sky.moon.group.matrix_world.translation if sky.moon else None
            if mo is not None:
                sky.update(0.0)
                d = P.three_to_blender(sky.moon_vals['position3']) if sky.moon_vals else tuple(mo)
                y, p = dir_angles(P.norm3(d))
            else:
                y, p = dir_angles(mdir)
            aim(cam, y, max(p, 4.0))
        tb = time.time()
        frames = sky.bake(log=lambda *a: None, plate_scale=args.plate_scale)
        tr = time.time()
        name = '%s%s_%05.2f_%s' % (args.world, args.tag, hours, view)
        sc.render.filepath = os.path.join(OUT, name + '.png')
        bpy.ops.render.render(write_still=True)
        te = time.time()
        Y = luma(sc.render.filepath)
        L = frames[0]['lights']
        print('[world_views] %s: bake %.1fs render %.1fs  sun %s  sun lamp %.2f  luma mean %.3f p5 %.3f p95 %.3f'
              % (name, tr - tb, te - tr, tuple(round(c, 3) for c in sdir), L['sun_intensity'], Y.mean(),
                 np.percentile(Y, 5), np.percentile(Y, 95)), flush=True)
        ok_all &= check('%s rendered with finite, non-empty pixels' % name, np.isfinite(Y).all() and Y.max() > 0.01)
    if args.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, '%s%s_%05.2f.blend' % (args.world, args.tag, hours)))
print('PASS world_views all' if ok_all else 'FAIL world_views some')
