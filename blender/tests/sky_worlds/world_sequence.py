"""A sky world's day as KEYED data: day_cycle over a short shot, baked once, rendered as plain frames, then the saved
.blend reopened in the same Blender and one frame rendered again from the file alone.

Checks (PASS/FAIL lines): every frame renders; the keyed sun lamp, band lamps / moon fade follow the cycle (the
lamp's strength changes across the day); the reopened file's frame matches the in-session frame (keys, image
sequences and Geometry Nodes are all the .blend needs). Writes out/sequence/<world>_<tag>_####.png, a strip of the
frames, and the .blend.

    bash run_blender.sh blender/tests/sky_worlds/world_sequence.py --world ringworld [--frames 12] [--start 5]
        [--seconds 0.5] [--res 384x216] [--view horizon|up] [--weather rain] [--transition storm@0.1]
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
ap.add_argument('--world', default='ringworld')
ap.add_argument('--frames', type=int, default=12)
ap.add_argument('--start', type=float, default=5.0, help='start hour of the cycle')
ap.add_argument('--seconds', type=float, default=0.5, help='seconds of media time for a full 24 h')
ap.add_argument('--res', default='384x216')
ap.add_argument('--view', default='horizon')
ap.add_argument('--samples', type=int, default=8)
ap.add_argument('--weather', default=None)
ap.add_argument('--transition', default='', help='state@seconds: transition_to(state, 1, 0.2, at=seconds)')
ap.add_argument('--tag', default='day')
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'sequence')
os.makedirs(OUT, exist_ok=True)
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)


def read(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return px


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W, H = (int(v) for v in args.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = 0.6
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, args.frames
sc.render.image_settings.file_format = 'PNG'
g = bpy.data.materials.new('ground')
g.use_nodes = True
g.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.15, 0.12, 1)
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=600, fill_type='NGON')
bpy.context.object.data.materials.append(g)
m = bpy.data.materials.new('white')
m.use_nodes = True
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0.0, 6.0, 0.5))
bpy.ops.object.shade_smooth()
bpy.context.object.data.materials.append(m)
cd = bpy.data.cameras.new('cam')
cd.lens_unit = 'FOV'
cd.angle = math.radians(62)
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (0, 0, 1.7)
pitch = 50.0 if args.view == 'up' else 8.0
cam.rotation_euler = (math.radians(90 + pitch), 0, 0)
blend = os.path.join(OUT, '%s_%s.blend' % (args.world, args.tag))
cache = os.path.join(OUT, 'cache_%s_%s' % (args.world, args.tag))
sky = make_sky(sc, camera=cam, world=args.world, hours=args.start, clouds='cumulus', weather=args.weather,
               cache_dir=cache, quality='draft')
sky.day_cycle(start_hour=args.start, seconds=args.seconds)
if args.transition:
    st, at = args.transition.split('@')
    sky.transition_to(st, 1.0, 0.2, at=float(at))
t0 = time.time()
frames = sky.bake(log=lambda *a: None)
print('[world_sequence] %s: %d frames baked in %.1fs' % (args.world, len(frames), time.time() - t0), flush=True)
lamp = [fr['lights']['sun_intensity'] for fr in frames]
print('[world_sequence] sun lamp per frame %s' % [round(v, 2) for v in lamp], flush=True)
check('the keyed sun lamp follows the cycle', max(lamp) - min(lamp) > 0.5, 'min %.2f max %.2f' % (min(lamp), max(lamp)))
if sky.ring is not None:
    bs = sky.ring.band_sun
    fc_ok = bs.animation_data is not None and bs.animation_data.action is not None
    check('the band sun is keyed (rotation, colour)', fc_ok and bs.data.animation_data is not None)
    tw = bpy.data.objects.get('eido_sky_cloud_shadow_caster_band')
    blk = bs.light_linking.blocker_collection
    ons = []
    if tw is not None and tw.animation_data and tw.animation_data.action:
        # the twin lives in the band's plate scene, which is not the active one, so its keyed property is read from
        # its F-curve rather than from the object after a frame change
        from eidoblend.sky.world_nodes import _fcurves
        fc = next((c for c in _fcurves(tw.animation_data) if c.data_path == '["eido_band_caster_on"]'), None)
        ons = [float(fc.evaluate(fr['frame'])) for fr in frames] if fc is not None else []
    check('the near band takes the local deck\'s cloud shadow by day only (the band-sun caster twin)',
          tw is not None and tw.name in blk.objects and 1.0 in ons and 0.0 in ons,
          'on per frame %s' % ons)
if sky.moon is not None:
    fades = [fr['moon']['visibility'] for fr in frames]
    print('[world_sequence] moon fade per frame %s' % [round(v, 2) for v in fades], flush=True)
bpy.ops.wm.save_as_mainfile(filepath=blend)
shots = []
t0 = time.time()
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, '%s_%s_%04d.png' % (args.world, args.tag, f))
    bpy.ops.render.render(write_still=True)
    shots.append(read(sc.render.filepath))
print('[world_sequence] rendered %d frames in %.1fs' % (len(shots), time.time() - t0), flush=True)
check('every frame rendered with finite pixels', all(np.isfinite(s).all() and s.max() > 0.01 for s in shots))
# the strip
strip = np.concatenate([np.concatenate(shots[i:i + 6], axis=1) for i in range(0, len(shots) - len(shots) % 6, 6)
                        ][::-1], axis=0) if len(shots) >= 6 else np.concatenate(shots, axis=1)
im = bpy.data.images.new('strip', strip.shape[1], strip.shape[0])
px = np.ones((strip.shape[0], strip.shape[1], 4), np.float32)
px[..., :3] = strip
im.pixels.foreach_set(px.ravel())
im.filepath_raw = os.path.join(OUT, '%s_%s_strip.png' % (args.world, args.tag))
im.file_format = 'PNG'
im.save()
# the saved file alone: reopen, render a middle frame, compare
mid = (sc.frame_start + sc.frame_end) // 2
ref = shots[mid - sc.frame_start]
bpy.ops.wm.open_mainfile(filepath=blend)
sc2 = bpy.context.scene
sc2.frame_set(mid)
sc2.render.filepath = os.path.join(OUT, '%s_%s_reopened_%04d.png' % (args.world, args.tag, mid))
bpy.ops.render.render(write_still=True)
again = read(sc2.render.filepath)
d = np.abs(again - ref).mean()
check('the saved .blend renders frame %d on its own like the session did' % mid, d < 0.01, 'mean |delta| %.4f' % d)
print('PASS world_sequence all' if ok_all else 'FAIL world_sequence some')
