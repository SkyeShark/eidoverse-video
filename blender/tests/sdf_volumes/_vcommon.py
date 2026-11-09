"""Scaffolding of the SDF-volume tests: the SDF tests' helpers (tests/sdf/_common.py: PASS/FAIL lines, the probe
stage, camera, render, contact sheets, AgX PNGs of a linear image) with this folder's out/, plus what the volume
tests share: a dusk stage, image statistics, Cycles on the GPU, the reference march composited over the world.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SDF_TESTS = os.path.normpath(os.path.join(HERE, '..', 'sdf'))
if SDF_TESTS not in sys.path:
    sys.path.insert(0, SDF_TESTS)
import _common as C  # noqa: E402  (puts <repo>/blender on sys.path)

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
C.OUT = OUT

args, check, summary, camera, render, sheet, save_linear_png = (C.args, C.check, C.summary, C.camera, C.render,
                                                                 C.sheet, C.save_linear_png)


def stage(width=960, height=540, samples=16, world=0.02, sun=0.0, floor=True, floor_color=(0.30, 0.29, 0.27),
          floor_size=40.0, sun_rot=(50.0, 0.0, 35.0), raytracing=True):
    """A probe stage for fire: a dim world (`world` grey), an optional sun, a grey floor at z = 0, EEVEE, AgX."""
    return C.stage(width, height, samples, world_color=(world,) * 3, world_strength=1.0, floor=floor,
                   floor_color=floor_color, floor_size=floor_size, sun=sun > 0, sun_energy=sun, sun_rot=sun_rot,
                   raytracing=raytracing)


def read_png(path):
    """An 8-bit PNG as float (H, W, 3) in 0..1, row 0 at the top."""
    import numpy as np
    import OpenImageIO as oiio
    buf = oiio.ImageBuf(path)
    a = np.asarray(buf.get_pixels(oiio.FLOAT))
    return a[..., :3]


def read_exr(path):
    """A float EXR (H, W, C), row 0 at the top."""
    import numpy as np
    import OpenImageIO as oiio
    buf = oiio.ImageBuf(path)
    return np.asarray(buf.get_pixels(oiio.FLOAT))


def render_linear(path_exr, engine='BLENDER_EEVEE', samples=None):
    """Render the scene to a linear float EXR (view transform Standard is not involved: an EXR holds scene-linear
    values). Returns the (H, W, 4) array."""
    import bpy
    sc = bpy.context.scene
    r = sc.render
    keep = (r.engine, r.image_settings.media_type if hasattr(r.image_settings, 'media_type') else None,
            r.image_settings.file_format, r.image_settings.color_depth)
    try:
        r.engine = engine
        if hasattr(r.image_settings, 'media_type'):
            r.image_settings.media_type = 'IMAGE'
        r.image_settings.file_format = 'OPEN_EXR'
        r.image_settings.color_depth = '32'
        if samples is not None:
            if engine == 'CYCLES':
                sc.cycles.samples = int(samples)
            else:
                sc.eevee.taa_render_samples = int(samples)
        C.render(path_exr)
    finally:
        r.engine = keep[0]
        if keep[1] is not None:
            r.image_settings.media_type = keep[1]
        r.image_settings.file_format = keep[2]
        r.image_settings.color_depth = keep[3]
    return read_exr(path_exr)


def cycles_gpu(scene, samples=128):
    """Cycles on the GPU (OptiX first), denoised: the ground truth of the same file."""
    import bpy
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            break
    for d in prefs.devices:
        d.use = d.type != 'CPU'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = int(samples)
    scene.cycles.use_denoising = True
    scene.cycles.volume_step_rate = 1.0
    return scene


def reference_over(vol_or_fx, cam, width, height, world, samples=2, t=None):
    """The engine's own march of a volume (or a NuclearExplosion) composited over a flat world colour: linear
    (H, W, 3), row 0 at the bottom (save with save_linear_png)."""
    import numpy as np
    ref = vol_or_fx.raymarch_reference(cam, width, height, samples=samples, t=t)
    bg = np.full(ref.shape[:2] + (3,), world, np.float32)
    return ref[..., :3] + bg * (1.0 - ref[..., 3:4])


_FONTS = [r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\segoeui.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']


def label(path, text, size=16):
    """Burn a short label into a PNG's top-left corner (OpenImageIO's text renderer, a system font), in place; with
    no font found the image stays unlabelled."""
    import OpenImageIO as oiio
    font = next((f for f in _FONTS if os.path.exists(f)), None)
    if font is None:
        return path
    buf = oiio.ImageBuf(path)
    buf.read(0, 0, True)
    ok = oiio.ImageBufAlgo.render_text(buf, 8, 6 + size, text, size, font, (1.0, 1.0, 0.85, 1.0))
    if ok:
        buf.write(path)
    buf.geterror()
    return path
