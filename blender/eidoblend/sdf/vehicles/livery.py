"""The cyberpunk sedan's racing-stripe livery as decal images, and GLSL expressions evaluated at points.

stripeMaskFn(p, n) painted the stripes per pixel: every one of its thirteen strokes is gated by one normal test
(n.y > 0.6 for the hood, trunk and roof strokes, n.x > 0.6 for the right flank's, n.x < -0.6 for the left flank's)
and then depends only on the position in that view's plane (plus the side of the car and the wheel-arch cut-out,
which the material tests per pixel). So the mask is three images, each the engine's own GLSL evaluated on the GPU
over a millimetre grid with the matching normal:

    side image   z -2.4..2.4, y 0..1.55   R = the right flank (n = +x), G = the left flank (n = -x)
    top image    x -1.05..1.05, z -2.4..2.4   R = the top strokes (n = +y)

and the stripe material looks them up per pixel by object position, which keeps 2 mm ramps sharp in a close-up.
The images are written once into <cache_dir>/vehicles/ (named by a hash of the GLSL) and reused.

eval_glsl(extra, expr, points) is the small tool under both: an expression of p (and n) in an example's GLSL dialect,
evaluated at (N, 3) points of the SDF's local frame, returned as (N,) floats. The jet's camo field uses it too.
"""

from __future__ import annotations

import hashlib
import os

import numpy as np

SIDE_DOMAIN = {'z': (-2.4, 2.4), 'y': (0.0, 1.55)}
TOP_DOMAIN = {'x': (-1.05, 1.05), 'z': (-2.4, 2.4)}


def eval_glsl(extra, expr, points, normal=None, label='glsl', uniforms=None, textures=None):
    """Evaluate the GLSL float expression `expr` (of p, and of n when `normal` is given: the unit normal every
    point sees) after `extra`, at points (N, 3) in the SDF's local three frame. Returns (N,) float32."""
    from ..gpu_eval import SdfProgram
    if normal is None:
        mp = 'vec2 map(vec3 p) { return vec2(1.0, 0.0); }'
    else:
        nx, ny, nz = (float(c) for c in normal)
        mp = 'vec2 map(vec3 p) { return vec2(dot(p, vec3(%r, %r, %r)), 0.0); }' % (nx, ny, nz)
    surf = ('SdfSurface surface(vec3 p, vec3 n, float mat) { return sdfSurface(vec3(%s, 0.0, 0.0), 0.5); }'
            % expr)
    prog = SdfProgram(map=mp, surface=surf, extra=extra, uniforms=uniforms, textures=textures, label=label)
    try:
        out = prog.surface_eval(np.asarray(points, np.float32), project=0, grad_h=0.001, normal_h=0.001)
        return np.asarray(out['albedo'][:, 0], np.float32).copy()
    finally:
        prog.free()


def _grid(a_range, b_range, mm):
    """Pixel-centre coordinates of an image over a_range (columns) x b_range (rows), row 0 at b's low end."""
    step = mm / 1000.0
    na = int(round((a_range[1] - a_range[0]) / step))
    nb = int(round((b_range[1] - b_range[0]) / step))
    a = a_range[0] + (np.arange(na) + 0.5) * (a_range[1] - a_range[0]) / na
    b = b_range[0] + (np.arange(nb) + 0.5) * (b_range[1] - b_range[0]) / nb
    A, B = np.meshgrid(a, b, indexing='xy')                    # (nb, na)
    return A, B


def _write_png(path, rgba):
    """(H, W, 4) floats 0..1, row 0 at the bottom (Blender order), to an 8-bit PNG (top row first, as files are)."""
    import OpenImageIO as oiio
    data = np.ascontiguousarray((np.clip(rgba[::-1], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))
    tmp = path + '.tmp.png'
    out = oiio.ImageOutput.create(tmp)
    out.open(tmp, oiio.ImageSpec(data.shape[1], data.shape[0], data.shape[2], 'uint8'))
    out.write_image(data)
    out.close()
    os.replace(tmp, path)


def stripe_masks(extra, mm=1.0):
    """The three stripe masks as float arrays: (side (H, W, 2) [right, left], top (H, W)), row 0 at the low end
    of y (side) or z (top)."""
    Z, Y = _grid(SIDE_DOMAIN['z'], SIDE_DOMAIN['y'], mm)
    side = np.zeros(Z.shape + (2,), np.float32)
    for k, x in enumerate((0.9, -0.9)):
        pts = np.stack([np.full(Z.size, x, np.float32), Y.ravel(), Z.ravel()], -1).astype(np.float32)
        side[..., k] = eval_glsl(extra, 'stripeMaskFn(p, n)', pts, normal=(1.0 if x > 0 else -1.0, 0.0, 0.0),
                                 label='livery_side').reshape(Z.shape)
    X, Z2 = _grid(TOP_DOMAIN['x'], TOP_DOMAIN['z'], mm)
    pts = np.stack([X.ravel(), np.full(X.size, 1.5, np.float32), Z2.ravel()], -1).astype(np.float32)
    top = eval_glsl(extra, 'stripeMaskFn(p, n)', pts, normal=(0.0, 1.0, 0.0), label='livery_top').reshape(X.shape)
    return side, top


def stripe_livery_images(extra, cache_dir, mm=1.0):
    """The livery decal images (side, top) as Non-Color Blender images, made once per GLSL and resolution."""
    import bpy
    tag = hashlib.sha1((extra + '|%g' % mm).encode('utf-8')).hexdigest()[:10]
    folder = os.path.join(cache_dir, 'vehicles')
    os.makedirs(folder, exist_ok=True)
    paths = {k: os.path.join(folder, f'cyberpunk_stripes_{k}_{tag}.png') for k in ('side', 'top')}
    if not all(os.path.exists(p) for p in paths.values()):
        side, top = stripe_masks(extra, mm)
        rgba = np.zeros(side.shape[:2] + (4,), np.float32)
        rgba[..., 0] = side[..., 0]
        rgba[..., 1] = side[..., 1]
        rgba[..., 3] = 1.0
        _write_png(paths['side'], rgba)
        rgba = np.zeros(top.shape + (4,), np.float32)
        rgba[..., 0] = top
        rgba[..., 3] = 1.0
        _write_png(paths['top'], rgba)
    out = {}
    for k, p in paths.items():
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = 'Non-Color'
        out[k] = img
    return out['side'], out['top']
