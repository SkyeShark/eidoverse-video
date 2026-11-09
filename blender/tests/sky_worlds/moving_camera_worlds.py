"""Each sky world under a MOVING camera: frame N of an animated bake against a still bake of the same pose.

A film's camera moves. The sky elements (the ringworld's band, walls and cloud sheet, the shattered moon, the cloud
dome) composite the frame's cloud and shield layers over themselves through the keyed bake camera (sky_view), and the
world reads the same keys and image sequences. The sky's state runs on the scene clock, not on the camera, so frame N
of a bake whose camera travels and turns must equal a bake of a camera parked at frame N's pose. A key or an image
sequence a frame off for a moving camera would show as clouds sliding against the band, the moon or the far ridge.

    bash run_blender.sh blender/tests/sky_worlds/moving_camera_worlds.py [--worlds earth,ringworld,shieldworld]
        [--frames 5] [--res 480x270] [--samples 8] [--quality draft]

Shots: the ringworld at 10:00 walking toward the band while tilting up its arc; the shieldworld at 01:24 sliding
under the shattered moon behind the hex shield; Earth at 17:00 with the cloud dome, panning along a ridge 9 km out.
Writes out/moving_camera/<world>_moving_####.png (every frame), <world>_still_####.png (frame N), a strip of the
moving frames, and the difference image; prints PASS/FAIL per world.
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
from eidoblend.sky import palette as P  # noqa: E402
from eidoblend.sky.world_nodes import _fcurves  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--worlds', default='ringworld,shieldworld,earth')
ap.add_argument('--frames', type=int, default=5)
ap.add_argument('--res', default='480x270')
ap.add_argument('--samples', type=int, default=8)
ap.add_argument('--quality', default='draft')
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'moving_camera')
os.makedirs(OUT, exist_ok=True)
N = args.frames
ok_all = True

# per world: hours, clouds, cloud dome, the camera at frame 1 (location, yaw from +Y toward +X, pitch) and its change
# per frame. 'aim': 'moon' starts the shot on the shattered moon.
SHOTS = {
    'ringworld': dict(hours=10.0, clouds='cumulus', dome=None, loc=(0.0, -20.0, 2.0), yaw=-4.0, pitch=12.0,
                      dloc=(8.0, 40.0, 3.0), dyaw=3.0, dpitch=2.5, ridge=False),
    'shieldworld': dict(hours=1.4, clouds='cumulus', dome=None, loc=(-60.0, 0.0, 2.0), aim='moon',
                        dloc=(30.0, 0.0, 0.0), dyaw=1.2, dpitch=-0.8, ridge=False),
    'earth': dict(hours=17.0, clouds='cumulus', dome=True, loc=(0.0, 0.0, 2.0), yaw=-12.0, pitch=7.0,
                  dloc=(0.0, 25.0, 0.0), dyaw=6.0, dpitch=0.0, ridge=True),
}


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)
    return ok


def material(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def setup_scene(shot):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, H = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, N
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=600, fill_type='NGON', location=(0, 0, 0))
    bpy.context.object.data.materials.append(material('ground', (0.16, 0.14, 0.10), 0.9))
    for i, (name, col, rough, metal) in enumerate((('white', (0.8, 0.8, 0.8), 0.5, 0.0),
                                                  ('chrome', (0.95, 0.95, 0.95), 0.03, 1.0))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.8, location=(-1.5 + 3.0 * i, 14, 0.8))
        bpy.ops.object.shade_smooth()
        bpy.context.object.data.materials.append(material('ref_' + name, col, rough, metal))
    if shot['ridge']:
        rock = material('rock', (0.16, 0.13, 0.11), 0.8)
        for i in range(9):
            x = -6000 + i * 1500
            h = 1600 + 900 * math.sin(i * 1.7) ** 2
            bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=1300, radius2=60, depth=h, location=(x, 9000, h / 2))
            bpy.context.object.data.materials.append(rock)
    cd = bpy.data.cameras.new('cam')
    cd.lens_unit = 'FOV'
    cd.angle = math.radians(62.0)
    cd.clip_start = 0.1
    cd.clip_end = 30000.0
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.rotation_mode = 'XYZ'
    return sc, cam


def pose(shot, f):
    """The camera's location and (yaw, pitch) at frame f: a straight move at constant rates (LINEAR keys)."""
    k = f - 1
    loc = tuple(shot['loc'][i] + shot['dloc'][i] * k for i in range(3))
    return loc, shot['yaw'] + shot['dyaw'] * k, shot['pitch'] + shot['dpitch'] * k


def place(cam, loc, yaw, pitch):
    cam.location = loc
    cam.rotation_euler = (math.radians(90 + pitch), 0.0, math.radians(-yaw))


def build(world, shot, tag):
    sc, cam = setup_scene(shot)
    sky = make_sky(sc, camera=cam, world=world, hours=shot['hours'], clouds=shot['clouds'],
                   cache_dir=os.path.join(OUT, 'cache_%s_%s' % (world, tag)), quality=args.quality,
                   cloud_dome=shot['dome'])
    if shot.get('aim') == 'moon':
        sky._reset_state()
        sky.update(0.0)
        d = P.norm3(P.three_to_blender(sky.moon_vals['position3']))
        shot['yaw'] = math.degrees(math.atan2(d[0], d[1])) - shot['dyaw'] * (N - 1) / 2
        shot['pitch'] = math.degrees(math.asin(d[2])) - shot['dpitch'] * (N - 1) / 2
    return sc, cam, sky


def render(sc, path, frame):
    sc.frame_set(frame)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    return px


def save_png(path, rgb):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new('png_out', w, h, alpha=False)
    img.pixels[:] = np.concatenate([rgb[::-1], np.ones((h, w, 1), np.float32)], 2).ravel()
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


for world in args.worlds.split(','):
    shot = dict(SHOTS[world])
    # ---- the moving camera: keyed at frame 1 and N, LINEAR between; one bake over the range ----
    sc, cam, sky = build(world, shot, 'moving')
    for f in (1, N):
        loc, yaw, pitch = pose(shot, f)
        place(cam, loc, yaw, pitch)
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
    for fc in _fcurves(cam.animation_data):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    sky.bake(log=lambda *a: None)
    moving = [render(sc, os.path.join(OUT, '%s_moving_%04d.png' % (world, f)), f) for f in range(1, N + 1)]
    sc.frame_set(N)
    mw_moving = [list(r) for r in cam.matrix_world]
    # ---- the still camera at frame N's pose: no animation; the bake renders frame N only (state replayed) ----
    sc, cam, sky = build(world, dict(SHOTS[world]), 'still')
    loc, yaw, pitch = pose(shot, N)
    place(cam, loc, yaw, pitch)
    sky.bake(frame_start=N, frame_end=N, log=lambda *a: None)
    still = render(sc, os.path.join(OUT, '%s_still_%04d.png' % (world, N)), N)
    mw_still = [list(r) for r in cam.matrix_world]
    pose_err = float(np.abs(np.array(mw_moving) - np.array(mw_still)).max())
    check('%s: the still camera sits at the moving camera\'s frame-%d pose' % (world, N), pose_err < 1e-4,
          'max matrix difference %.2e' % pose_err)
    a, b = moving[-1], still
    d = np.abs(a - b).mean(2)
    lum = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32))
    save_png(os.path.join(OUT, '%s_difference_x8_%04d.png' % (world, N)), np.clip(np.repeat(d[..., None] * 8, 3, 2),
                                                                                  0, 1))
    save_png(os.path.join(OUT, '%s_moving_strip.png' % world), np.concatenate(moving, 1))
    check('%s: frame %d of the moving bake equals the still bake at that pose' % (world, N),
          d.mean() < 0.6 / 255 and np.percentile(d, 99.5) < 6 / 255,
          'mean |delta| %.2f/255, p99.5 %.2f/255, max %.2f/255' % (d.mean() * 255, np.percentile(d, 99.5) * 255,
                                                                     d.max() * 255))
    # the frames really move: the first and last moving frames differ (a parked camera would pass trivially)
    dm = np.abs(moving[0] - moving[-1]).mean()
    check('%s: the camera really moves (frame 1 against frame %d)' % (world, N), dm > 4 / 255,
          'mean |delta| %.1f/255' % (dm * 255))
    check('%s: frames render with finite, non-empty pixels' % world,
          all(np.isfinite(m).all() and m.max() > 0.02 for m in moving), 'luma mean %.3f' % lum.mean())
print('PASS moving_camera_worlds all' if ok_all else 'FAIL moving_camera_worlds some')
