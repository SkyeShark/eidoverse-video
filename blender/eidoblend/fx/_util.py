"""Small helpers private to the fx family: axes, colours, the scene clock, seeded randomness, cache files.

Axes. The WebGPU engine is three.js, Y-up; Blender is Z-up. Both in metres.
    three (x, y, z) -> Blender (x, -z, y)       from_three(v)
    Blender (x, y, z) -> three (x, z, -y)       to_three(v)
The solvers run in three's frame (so every kernel reads like its source); the API takes and returns Blender
coordinates only.

Time. A scene's clock is frame / fps: frame `frame_start` is t = 0. Nothing in the family reads a wall clock.
"""

from __future__ import annotations

import os

import numpy as np


def from_three(v):
    """three.js (x, y, z) -> Blender (x, -z, y). Works on (..., 3) arrays and plain triples."""
    a = np.asarray(v, dtype=np.float64)
    return np.stack([a[..., 0], -a[..., 2], a[..., 1]], axis=-1)


def to_three(v):
    """Blender (x, y, z) -> three.js (x, z, -y)."""
    a = np.asarray(v, dtype=np.float64)
    return np.stack([a[..., 0], a[..., 2], -a[..., 1]], axis=-1)


# the 4x4 that maps Blender coordinates to three's (rows): (x, y, z) -> (x, z, -y)
B2T = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=np.float64)
T2B = B2T.T.copy()


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def color(c):
    """An engine colour ('#rrggbb', 0xrrggbb or an sRGB triple) as LINEAR sRGB, the way three's
    ColorManagement turns `new THREE.Color('#ff7305')` into its working colour. A 3-tuple of floats is taken
    as already linear."""
    if isinstance(c, str):
        h = c.lstrip('#')
        rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
        return tuple(float(x) for x in srgb_to_linear(rgb))
    if isinstance(c, int):
        rgb = [((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0]
        return tuple(float(x) for x in srgb_to_linear(rgb))
    return tuple(float(x) for x in c)


def smoothstep(e0, e1, x):
    """GLSL/WGSL smoothstep, including reversed edges (e0 > e1) as the shaders use them."""
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return a + (b - a) * t


def luminance(rgb):
    """three's luminance() in its linear-sRGB working space (Rec. 709 weights)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def saturation(rgb, amount):
    """three TSL saturation(color, amount) = mix(luminance, color, amount)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    lum = luminance(rgb)[..., None]
    return lum + (rgb - lum) * amount


def hue(rgb, angle):
    """three TSL hue(color, radians): rotation about the grey axis."""
    rgb = np.asarray(rgb, dtype=np.float64)
    k = np.array([0.57735, 0.57735, 0.57735])
    c, s = np.cos(angle), np.sin(angle)
    return rgb * c + np.cross(k, rgb) * s + k * (rgb @ k)[..., None] * (1.0 - c)


class LCG:
    """fluid_grid.js's seeded generator: sd = sd*1664525 + 1013904223 (u32); returns (sd >>> 8) / 2^24."""

    def __init__(self, seed=1):
        self.s = int(seed) & 0xffffffff

    def __call__(self):
        self.s = (self.s * 1664525 + 1013904223) & 0xffffffff
        return (self.s >> 8) / 16777216.0


def scene_fps(scene):
    return scene.render.fps / scene.render.fps_base


def abspath(path):
    """bpy-style '//relative' paths resolve against the open .blend; plain paths are made absolute."""
    if path.startswith('//'):
        import bpy
        return os.path.normpath(bpy.path.abspath(path))
    return os.path.abspath(path)


def frame_file(directory, stem, frame, ext):
    return os.path.join(directory, f'{stem}_{int(frame):04d}.{ext}')


def write_exr(path, rgba, half=False):
    """Write an (H, W, C) float array as an OpenEXR image, row 0 = the image's BOTTOM row as Blender reads it
    (the file's scanlines run top-down, so the array is flipped on the way out)."""
    import OpenImageIO as oiio
    a = np.ascontiguousarray(np.asarray(rgba, dtype=np.float32)[::-1])
    h, w = a.shape[:2]
    ch = 1 if a.ndim == 2 else a.shape[2]
    spec = oiio.ImageSpec(w, h, ch, 'half' if half else 'float')
    spec.attribute('compression', 'zip')
    tmp = path + '.tmp.exr'
    out = oiio.ImageOutput.create(tmp)
    if out is None:
        raise RuntimeError('[fx] cannot write ' + path + ': ' + oiio.geterror())
    out.open(tmp, spec)
    out.write_image(a)
    out.close()
    os.replace(tmp, path)


def read_exr(path):
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(path)
    if inp is None:
        raise RuntimeError('[fx] cannot read ' + path + ': ' + oiio.geterror())
    a = inp.read_image('float')
    inp.close()
    return np.asarray(a)[::-1]
