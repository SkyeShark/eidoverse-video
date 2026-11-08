"""Shared scaffolding of the SDF tests: argument parsing, PASS/FAIL lines, a lit probe stage, renders, sheets.

Every test script puts <repo>/blender on sys.path through this module and prints `PASS name: detail` or
`FAIL name: detail` for each numeric check; `summary()` prints the counts and exits 1 when anything failed.
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..'))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

_RESULTS = {'pass': 0, 'fail': 0}


def args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return dict(a.split('=', 1) for a in argv if '=' in a)


def check(name, ok, detail=''):
    _RESULTS['pass' if ok else 'fail'] += 1
    print(f'{"PASS" if ok else "FAIL"} {name}: {detail}', flush=True)
    return ok


def summary(exit_on_fail=True):
    print(f'[sdf.tests] {_RESULTS["pass"]} passed, {_RESULTS["fail"]} failed', flush=True)
    if exit_on_fail and _RESULTS['fail']:
        import bpy  # noqa: F401  (Blender exits 0 on a script error: make a failure visible to the shell)
        os._exit(1)


def clear_scene():
    import bpy
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


def stage(width=960, height=540, samples=16, world_color=(0.42, 0.47, 0.55), world_strength=0.6, floor=True,
          floor_color=(0.32, 0.31, 0.29), floor_size=12.0, sun=True, sun_energy=3.0, sun_angle=2.0,
          sun_rot=(52.0, 0.0, 35.0), raytracing=True, film_transparent=False):
    """A probe stage: EEVEE, AgX, a sky-tinted world, a sun with soft shadows, an optional grey floor at z = 0."""
    import bpy
    clear_scene()
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = int(width), int(height)
    sc.render.resolution_percentage = 100
    sc.render.fps = 24
    sc.eevee.taa_render_samples = int(samples)
    sc.eevee.use_raytracing = bool(raytracing)
    sc.eevee.use_shadows = True
    sc.render.film_transparent = film_transparent
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.render.image_settings.file_format = 'PNG'
    world = bpy.data.worlds.new('probe_world')
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*world_color, 1.0)
    bg.inputs['Strength'].default_value = world_strength
    sc.world = world
    if floor:
        me = bpy.data.meshes.new('floor')
        h = floor_size * 0.5
        me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
        fl = bpy.data.objects.new('floor', me)
        sc.collection.objects.link(fl)
        fm = bpy.data.materials.new('floor_mat')
        fm.use_nodes = True
        b = fm.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*floor_color, 1.0)
        b.inputs['Roughness'].default_value = 0.8
        me.materials.append(fm)
    if sun:
        ld = bpy.data.lights.new('sun', 'SUN')
        ld.energy = sun_energy
        ld.angle = math.radians(sun_angle)
        so = bpy.data.objects.new('sun', ld)
        sc.collection.objects.link(so)
        so.rotation_euler = tuple(math.radians(a) for a in sun_rot)
    return sc


def camera(location, target, lens=50.0, name='cam'):
    import bpy
    from mathutils import Vector
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    d = Vector(target) - Vector(location)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam


def render(path):
    import bpy
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    ok = os.path.exists(path)
    if not ok:
        print(f'[sdf.tests] render did not write {path}', flush=True)
    return ok


def sheet(paths, out_path, cols=2, labels=None, scale=1.0):
    """Paste PNGs into one contact sheet (Pillow is not in Blender's Python: OpenImageIO is)."""
    import numpy as np
    import OpenImageIO as oiio
    imgs = []
    for p in paths:
        buf = oiio.ImageBuf(p)
        a = buf.get_pixels(oiio.UINT8)
        if a is None or a.size == 0:
            continue
        a = np.asarray(a)
        if a.shape[2] == 4:
            a = a[..., :3]
        imgs.append(a)
    if not imgs:
        return None
    h = max(i.shape[0] for i in imgs)
    w = max(i.shape[1] for i in imgs)
    rows = int(math.ceil(len(imgs) / cols))
    canvas = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, im in enumerate(imgs):
        r, c = divmod(k, cols)
        canvas[r * h:r * h + im.shape[0], c * w:c * w + im.shape[1]] = im
    out = oiio.ImageOutput.create(out_path)
    out.open(out_path, oiio.ImageSpec(canvas.shape[1], canvas.shape[0], 3, 'uint8'))
    out.write_image(canvas)
    out.close()
    return out_path


def save_linear_png(path, img, exposure=0.0, agx=True):
    """A linear (H, W, 3|4) float image (row 0 at the bottom, GL order) as an 8-bit PNG through the scene's AgX view
    (so a raymarch reference reads like the EEVEE render beside it), or plain sRGB when agx=False."""
    import numpy as np
    import OpenImageIO as oiio
    a = np.asarray(img, np.float32)[::-1, :, :3] * (2.0 ** exposure)
    if agx:
        import PyOpenColorIO as ocio
        cfg = ocio.GetCurrentConfig()
        try:
            proc = cfg.getProcessor(ocio.ROLE_SCENE_LINEAR, 'sRGB', 'AgX', ocio.TRANSFORM_DIR_FORWARD)
        except Exception:
            dvt = ocio.DisplayViewTransform()
            dvt.setSrc(ocio.ROLE_SCENE_LINEAR)
            dvt.setDisplay('sRGB')
            dvt.setView('AgX')
            proc = cfg.getProcessor(dvt)
        cpu = proc.getDefaultCPUProcessor()
        b = np.ascontiguousarray(a.reshape(-1, 3).astype(np.float32))
        cpu.applyRGB(b)
        srgb = np.clip(b.reshape(a.shape), 0.0, 1.0)
    else:
        rgb = np.clip(a, 0.0, 1.0)
        srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
    data = np.ascontiguousarray((srgb * 255 + 0.5).astype(np.uint8))
    out = oiio.ImageOutput.create(path)
    out.open(path, oiio.ImageSpec(data.shape[1], data.shape[0], 3, 'uint8'))
    out.write_image(data)
    out.close()
    return path
