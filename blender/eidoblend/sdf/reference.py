"""The engine's raymarch, run in Blender: an SDF's original look from a Blender camera.

createSdfObject drew each SDF by sphere tracing inside its bounds box, per pixel, with the quality preset's
maxSteps / surfEps / stepScale / maxDist, then coloured the hit with the example's own shade() (its hand lights,
soft shadow, fresnel). raymarch_image() is that fragment shader (glsl_lib.KERNEL_RAYMARCH) driven by a Blender
camera moved into the SDF's local three.js frame. It is how the EEVEE port is judged: the reference beside the
render, same camera, same time.
"""

from __future__ import annotations

import numpy as np

from .solid import T2B


def _local_frame(obj):
    """4x4: Blender world -> the SDF's local three frame."""
    mw = np.array(obj.matrix_world, dtype=np.float64)
    t2b = np.eye(4)
    t2b[:3, :3] = T2B
    return np.linalg.inv(mw @ t2b)


def camera_rays(scene, camera, obj):
    """(position, forward, right, up, (tan_x, tan_y)) of a Blender camera in obj's local three frame."""
    inv = _local_frame(obj)
    cw = np.array(camera.matrix_world, dtype=np.float64)
    pos = (inv @ cw[:, 3])[:3]
    rot = inv[:3, :3] @ cw[:3, :3]
    right, up, back = rot[:, 0], rot[:, 1], rot[:, 2]
    frame = camera.data.view_frame(scene=scene)
    xs = [abs(v.x) for v in frame]
    ys = [abs(v.y) for v in frame]
    z = abs(frame[0].z)
    tx, ty = max(xs) / z, max(ys) / z
    # unit-length axes, so tan scales the ray exactly (non-uniform object scale stays in the lengths below)
    return pos, -back, right, up, (tx, ty)


def model_matrix_three(obj):
    """The object's world matrix in three's axes (local three frame -> three world), as uModelMatrix: what
    sdfReflectWorld and the originals' mat3(uModelMatrix) * n read."""
    mw = np.array(obj.matrix_world, dtype=np.float64)
    t2b = np.eye(4)
    t2b[:3, :3] = T2B
    return np.linalg.inv(t2b) @ mw @ t2b


def _camera_values(scene, camera, obj, width, height):
    import bpy
    bpy.context.view_layer.update()          # a camera or object moved since the last update has a stale matrix_world
    pos, fwd, right, up, tan = camera_rays(scene, camera, obj)
    m3 = model_matrix_three(obj)
    cw = np.array(camera.matrix_world, dtype=np.float64)[:3, 3]
    cam_three_world = (cw[0], cw[2], -cw[1])
    return {
        'sdfCameraUniform': tuple(float(x) for x in pos),
        'cameraPositionWorld': tuple(float(x) for x in cam_three_world),
        'uModelMatrix': tuple(float(x) for x in m3.T.ravel()),
        'sdfCamFwd': tuple(float(x) for x in fwd), 'sdfCamRight': tuple(float(x) for x in right),
        'sdfCamUp': tuple(float(x) for x in up), 'sdfCamTan': (float(tan[0]), float(tan[1])),
        'sdfImageSize': (float(width), float(height)),
    }


def _accumulate(prog, kind, width, height, samples):
    acc = np.zeros((height * width, 4), np.float64)
    rng = np.random.default_rng(7)
    dummy = np.zeros((width * height, 3), np.float32)
    for s in range(max(1, int(samples))):
        j = (0.0, 0.0) if s == 0 else tuple(rng.uniform(-1.0, 1.0, 2))
        prog.values['sdfJitter'] = (float(j[0]), float(j[1]))
        acc += prog.eval(kind, dummy, width=width)[0]
    return (acc / max(1, int(samples))).reshape(height, width, 4).astype(np.float32)


def raymarch_image(sdf, camera, width=480, height=270, samples=4, scene=None):
    """Linear (H, W, 4) image of sdf (an SdfObject) through the engine's raymarch + shade(); alpha = coverage."""
    import bpy
    scene = scene or bpy.context.scene
    prog = sdf.program
    if prog.shade is None:
        raise ValueError(f'{sdf.name}: no shade() to raymarch')
    sp = sdf.spec
    keep = dict(prog.values)
    prog.values.update(_camera_values(scene, camera, sdf.object, width, height))
    prog.values.update({
        'uMaxSteps': float(sp.max_steps), 'uSurfEps': float(sp.surf_eps), 'uStepScale': float(sp.step_scale),
        'uMaxDist': float(sp.max_dist), 'sdfNormalH': 0.0004,
        'sdfClipMin': tuple(float(x) for x in sp.bounds_min), 'sdfClipMax': tuple(float(x) for x in sp.bounds_max),
        # the engine marched the bare map; an example cut_by_bounds is the field cut by its box, as its mesh is
        'sdfUseClip': 1.0 if getattr(sp, 'cut_by_bounds', False) else 0.0,
    })
    try:
        return _accumulate(prog, 'raymarch', width, height, samples)
    finally:
        prog.values.clear()
        prog.values.update(keep)


def volume_raymarch_image(vol, camera, width=480, height=270, samples=4, scene=None, medium_step=None,
                          ambient=(0.0, 0.0, 0.0)):
    """Linear premultiplied (H, W, 4) image of vol (an SdfVolume) through createSdfVolume's own march: its sample()
    (alpha, step) or, for a medium() volume, an emission-absorption march at medium_step with its scattering colour
    under a flat `ambient` light; then post(sum)."""
    import bpy
    scene = scene or bpy.context.scene
    prog = vol.program
    keep = dict(prog.values)
    prog.values.update(_camera_values(scene, camera, vol.object, width, height))
    prog.values.update({
        'sdfVolSteps': float(vol.spec.steps),
        'sdfMediumStep': float(medium_step or vol.voxel),
        'sdfMediumAmbient': tuple(float(x) for x in ambient),
        'sdfClipMin': tuple(float(x) for x in vol.spec.bounds_min),
        'sdfClipMax': tuple(float(x) for x in vol.spec.bounds_max),
    })
    try:
        return _accumulate(prog, 'volume_raymarch', width, height, samples)
    finally:
        prog.values.clear()
        prog.values.update(keep)


def save_png(path, img, exposure=0.0):
    """A linear (H, W, 4) image (row 0 at the bottom) to an 8-bit sRGB PNG (the engine's display encoding),
    composited over black."""
    import os
    import OpenImageIO as oiio
    a = np.asarray(img, np.float64)[::-1]
    rgb = np.clip(a[..., :3] * (2.0 ** exposure), 0.0, 1.0)
    srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.ascontiguousarray((srgb * 255 + 0.5).astype(np.uint8))
    h, w = data.shape[:2]
    out = oiio.ImageOutput.create(path)
    out.open(path, oiio.ImageSpec(w, h, 3, 'uint8'))
    out.write_image(data)
    out.close()
