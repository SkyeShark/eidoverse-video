"""Motion blur and the sky layer: does every sub-frame read a layer through that layer's own camera?

A camera pans over frames 1-5 (6 deg/frame yaw, 3 deg/frame pitch, lens 30, LINEAR keys); the sky is baked
once. World-only renders to float EXRs at frame 3, at 2 + 0.75 (a motion-blur sample: the image sequence
shows layer 2 there, probe_world_api P6) and at 0 + 0.75 (a sample before the first baked frame, where the
sequence shows the file before the first). Each render is compared with the baked layers resampled at the
camera's TRUE rays at that time:
    'layer N via basis N'   a layer read through its own camera: the right sky for those rays
    'layer 2 via basis 3'   the old keying (keys held from f - 0.5): a layer read through the next camera
Then real motion-blur renders for looking (EEVEE, shutter 1.0, position steps 1 and 3) at frames 3 and 1.

    bash run_blender.sh blender/tests/sky/probe_subframe.py      (renders: through the GPU slot)
Writes blender/tests/sky/out/subframe/.
"""
import math
import os
import sys

import bpy
import numpy as np
import OpenImageIO as oiio

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky.world_nodes import _fcurves  # noqa: E402

OUT = os.path.join(HERE, 'out', 'subframe')
os.makedirs(OUT, exist_ok=True)
W, H = 480, 270


def setup(fmt):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 16
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 5
    sc.render.image_settings.media_type = 'IMAGE'
    if fmt == 'EXR':
        sc.view_settings.view_transform = 'Standard'
        sc.render.image_settings.file_format = 'OPEN_EXR'
        sc.render.image_settings.color_depth = '32'
        sc.render.filter_size = 0.5
    else:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.exposure = 0.6
        sc.render.image_settings.file_format = 'PNG'
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 30.0
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (10.0, -20.0, 1.7)
    for f, (yaw, pitch) in zip(range(1, 6), ((-40, 18), (-34, 21), (-28, 24), (-22, 27), (-16, 30))):
        cam.rotation_euler = (math.radians(90 + pitch), 0.0, math.radians(yaw))
        cam.keyframe_insert('rotation_euler', frame=f)
    for fc in _fcurves(cam.animation_data):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return sc, cam


def load_exr(path):
    return np.asarray(oiio.ImageBuf(path).get_pixels(oiio.FLOAT))[::-1, :, :3]       # row 0 = bottom


def lum(a):
    return a @ np.array([0.2126, 0.7152, 0.0722])


def bilinear(img, u, v):
    h, w = img.shape[:2]
    fx, fy = u * w - 0.5, v * h - 0.5
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    ax, ay = (fx - x0)[..., None], (fy - y0)[..., None]
    x0, y0 = np.clip(x0, 0, w - 2), np.clip(y0, 0, h - 2)
    return ((img[y0, x0] * (1 - ax) + img[y0, x0 + 1] * ax) * (1 - ay)
            + (img[y0 + 1, x0] * (1 - ax) + img[y0 + 1, x0 + 1] * ax) * ay)


def true_rays(sc, cam):
    """World directions of the frame's pixel centres for the camera as it is NOW (the evaluated sub-frame)."""
    c = cam.data.view_frame(scene=sc)
    xs, ys = [p.x / -p.z for p in c], [p.y / -p.z for p in c]
    jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
    px = min(xs) + (ii + 0.5) / W * (max(xs) - min(xs))
    py = min(ys) + (jj + 0.5) / H * (max(ys) - min(ys))
    mw = cam.matrix_world
    R, U, B = (np.array(mw.col[i][:3]) / np.linalg.norm(mw.col[i][:3]) for i in range(3))
    return px[..., None] * R + py[..., None] * U - B


def via(lay, fr, d):
    R, U, F = (np.array(v) for v in fr['basis'])
    x, y, z = d @ R, d @ U, d @ F
    u = 0.5 + 0.5 * (x / z) / fr['tan'][0]
    v = 0.5 + 0.5 * (y / z) / fr['tan'][1]
    inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    return bilinear(lay, u, v), inside


# ---------------------------------------------------------------- numeric: world-only EXRs
sc, cam = setup('EXR')
cache = os.path.join(OUT, '_cache')
sky = make_sky(sc, camera=cam, hours=16.5, clouds='cumulus', cache_dir=cache, shadows=False)
FR = {fr['frame']: fr for fr in sky.bake(log=lambda *a: None)}
lays = {f: load_exr(os.path.join(cache, 'sky_cam_%04d.exr' % f)) for f in list(FR) + [0]}
# (name, layer, basis, role): 'must' = what the world should read (under 0.5%); 'bug' = the old keying (must
# be far off, or the probe cannot see the difference); 'info' = the next frame's layer at the same rays, the
# sky one frame later (cloud drift and its own march jitter: about 1%)
cases = {3.0: [('layer 3 via basis 3', 3, 3, 'must')],
         2.75: [('layer 2 via basis 2 (what the keys now pair)', 2, 2, 'must'),
                ('layer 3 via basis 3 (one frame later)', 3, 3, 'info'),
                ('layer 2 via basis 3 (the old keying)', 2, 3, 'bug')],
         0.75: [('layer 0 (= copy of 1) via basis 1', 0, 1, 'must'), ('layer 1 via basis 1', 1, 1, 'must')]}
ok_all = True
for T, cands in cases.items():
    f, sub = int(math.floor(T)), T - math.floor(T)
    sc.frame_set(f, subframe=sub)
    path = os.path.join(OUT, 'world_t%04.2f.exr' % T)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    ren = load_exr(path)
    d = true_rays(sc, cam)
    magenta = float(((ren[..., 0] > 2 * ren[..., 1]) & (ren[..., 2] > 2 * ren[..., 1])).mean())
    line = []
    for name, li, bi, role in cands:
        ref, inside = via(lays[li], FR[bi], d)
        e = float(np.abs(lum(ren) - lum(ref))[inside].mean() / lum(ref)[inside].mean())
        line.append('%s %.2f%% (%.1f%% of rays inside)' % (name, 100 * e, 100 * inside.mean()))
        if (role == 'must' and e > 0.005) or (role == 'bug' and e < 0.05):
            ok_all = False
    print('[subframe] t=%.2f  magenta %.1f%%  |  %s' % (T, 100 * magenta, '  |  '.join(line)))
    ok_all = ok_all and magenta == 0.0
print(('PASS' if ok_all else 'FAIL') + ' every sub-frame reads a layer through its own camera (under 0.5%), '
      'no magenta before the first frame')

# ---------------------------------------------------------------- look: real motion blur
sc, cam = setup('PNG')
me = bpy.data.meshes.new('ground')
me.from_pydata([(-4000, -4000, 0), (4000, -4000, 0), (4000, 4000, 0), (-4000, 4000, 0)], [], [(0, 1, 2, 3)])
m = bpy.data.materials.new('ground')
m.use_nodes = True
m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.12, 0.15, 0.07, 1)
me.materials.append(m)
sc.collection.objects.link(bpy.data.objects.new('ground', me))
sky = make_sky(sc, camera=cam, hours=16.5, clouds='cumulus', cache_dir=os.path.join(OUT, '_cache_look'))
sky.bake(log=lambda *a: None)
sc.render.motion_blur_shutter = 1.0
for frame in (3, 1):
    for steps in (0, 1, 3):
        sc.render.use_motion_blur = steps > 0
        if steps:
            sc.eevee.motion_blur_steps = steps
        sc.frame_set(frame)
        sc.render.filepath = os.path.join(OUT, 'mblur_f%03d_%s.png' % (frame, 'steps%d' % steps if steps else 'off'))
        bpy.ops.render.render(write_still=True)
        print('[subframe] wrote', sc.render.filepath, os.path.exists(sc.render.filepath))
