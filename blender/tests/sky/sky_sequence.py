"""Update-by-frame probe: direction calls at media times, baked once, rendered as a plain animation.

    transition  cumulus 15:00, transition_to('storm', 1, 3 s, at=0.5 s): clouds thicken, sky greys, sun dims
    daycycle    day_cycle(start_hour=16.5, seconds=12): 16:30 -> 22:30 over 3 s, sunset into moonlight
    wind        fair weather for 10 s at 2 fps-equivalent steps: the clouds drift on the integrated wind

The bake writes the sky layers and keys the sun lamp, world and fog; then bpy.ops.render.render(animation=True)
renders with no Python in the loop, so every change must travel through the keyed data alone. Frames land
in blender/tests/sky/out/sequence/<name>/ and an H.264 preview beside them when ffmpeg is on PATH.

    bash run_blender.sh blender/tests/sky/sky_sequence.py [--only transition] [--res 480x270] [--frames 72]
        [--rebake]      (bake twice on the same Sky and check the second bake's layers equal the first's)
"""
import argparse
import math
import os
import shutil
import subprocess
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
ap.add_argument('--samples', type=int, default=8)
ap.add_argument('--frames', type=int, default=72)
ap.add_argument('--quality', default='draft')
ap.add_argument('--rebake', action='store_true')
args = ap.parse_args(argv)


def layer_sums(cache, frames):
    import numpy as np
    import OpenImageIO as oiio
    out = []
    for fr in frames:
        a = np.asarray(oiio.ImageBuf(os.path.join(cache, 'sky_cam_%04d.exr' % fr['frame'])).get_pixels(oiio.FLOAT))
        out.append(float(a.astype(np.float64).sum()))
    return out

FPS = 24
SEQS = {
    'transition': dict(kw=dict(hours=15.0, clouds='cumulus'), calls=lambda s: s.transition_to('storm', 1.0, 2.5, at=0.25),
                       pitch=16.0),
    'daycycle': dict(kw=dict(hours=16.5, clouds='cumulus'), calls=lambda s: s.day_cycle(start_hour=16.5, seconds=12.0),
                     pitch=12.0),
    'wind': dict(kw=dict(hours=11.0, clouds='cumulus', weather='fair'), calls=lambda s: None, pitch=30.0,
                 fps=2),
}
names = [n for n in SEQS if not args.only or n in args.only.split(',')]

for name in names:
    spec = SEQS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, H = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.eevee.use_raytracing = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.render.fps = spec.get('fps', FPS)
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    out = os.path.join(HERE, 'out', 'sequence', name)
    os.makedirs(out, exist_ok=True)
    for old in os.listdir(out):
        if old.endswith('.png'):
            os.remove(os.path.join(out, old))

    me = bpy.data.meshes.new('ground')
    me.from_pydata([(-4000, -4000, 0), (4000, -4000, 0), (4000, 4000, 0), (-4000, 4000, 0)], [], [(0, 1, 2, 3)])
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.10, 0.13, 0.06, 1)
    gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.95
    me.materials.append(gm)
    sc.collection.objects.link(bpy.data.objects.new('ground', me))
    spheres = []
    for nm, col, rough, metal in (('white', (0.8, 0.8, 0.8), 0.9, 0.0), ('chrome', (0.95, 0.95, 0.95), 0.03, 1.0)):
        sm = bpy.data.meshes.new(nm)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=0.5)
        bm.to_mesh(sm)
        for p in sm.polygons:
            p.use_smooth = True
        mat = bpy.data.materials.new(nm)
        mat.use_nodes = True
        b = mat.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*col, 1)
        b.inputs['Roughness'].default_value = rough
        b.inputs['Metallic'].default_value = metal
        sm.materials.append(mat)
        ob = bpy.data.objects.new(nm, sm)
        sc.collection.objects.link(ob)
        spheres.append(ob)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 24
    sc.collection.objects.link(cam)
    sc.camera = cam

    sky = make_sky(sc, camera=cam, cache_dir=os.path.join(out, '_cache'), quality=args.quality, **spec['kw'])
    spec['calls'](sky)
    sky.use_fog(density=0.0003)
    sd = sky.sun_dir
    yaw = math.radians(math.degrees(math.atan2(-sd[0], sd[1])) - 100.0)   # the sun on the left, a little behind
    cam.location = (0.0, 0.0, 1.6)
    cam.rotation_euler = (math.radians(90 + spec['pitch']), 0.0, yaw)
    fwd, right = (-math.sin(yaw), math.cos(yaw)), (math.cos(yaw), math.sin(yaw))
    for ob, lat in zip(spheres, (-0.9, 0.9)):
        ob.location = (fwd[0] * 6 + right[0] * lat, fwd[1] * 6 + right[1] * lat, 0.5)
    t0 = time.time()
    frames = sky.bake(log=lambda *a: None)
    t_bake = time.time() - t0
    rows = [(fr['frame'], fr['lights']['sun_intensity'], fr['U']['finalMul'], fr['U']['cloudWeatherGrey'],
             fr['lights']['key_dir'][1]) for fr in frames]
    if args.rebake:                     # a second bake on the same Sky must replay, not carry on from the end
        cache = os.path.join(out, '_cache')
        first = layer_sums(cache, frames)
        frames2 = sky.bake(log=lambda *a: None)
        rows2 = [(fr['frame'], fr['lights']['sun_intensity'], fr['U']['finalMul'], fr['U']['cloudWeatherGrey'],
                  fr['lights']['key_dir'][1]) for fr in frames2]
        same = rows2 == rows and layer_sums(cache, frames2) == first
        print('[seq] %s %s: re-bake on the same Sky gives the same state and bit-identical camera layers'
              % ('PASS' if same else 'FAIL', name))
    for r in rows[:: max(1, len(rows) // 6)]:
        print('[seq] %s f%03d sun %.2f finalMul %.3f grey %.2f key_y %.3f' % ((name,) + r))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, '_cache', name + '.blend'))
    sc.render.filepath = os.path.join(out, 'f')
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    print('[seq] %s: bake %.1fs (%.2fs/frame), render %.1fs for %d frames'
          % (name, t_bake, t_bake / len(frames), time.time() - t0, len(frames)))
    ff = shutil.which('ffmpeg')
    if ff:
        mp4 = os.path.join(os.path.dirname(out), name + '.mp4')
        subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(min(sc.render.fps, 24)),
                        '-i', os.path.join(out, 'f%04d.png'), '-c:v', 'libx264', '-profile:v', 'high',
                        '-pix_fmt', 'yuv420p', '-crf', '18', mp4], check=False)
        print('[seq] wrote', mp4)
