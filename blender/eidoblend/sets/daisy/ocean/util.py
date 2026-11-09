"""ocean/util.py: small shared helpers for the ocean set (port of eidoverse/sets/ocean/util.js).

Everything deterministic: the seeded RNG is the WebGPU edition's stream bit for bit, so the same seed places the same
grass, lights and faces. Canvas work is Pillow (Blender 5.2's Python ships it); a drawing becomes a Blender image
through image_from_array (rows bottom-up, as Blender stores them), packed into the .blend so a saved file renders on
its own.

    clamp01 smooth lerp seg ease          the shot maths (ease = smoothstep of a segment)
    rng(seed)                             mulberry-style uint32 stream (util.js rng)
    image_from_array(name, rgba, ...)     float or uint8 (H, W, 4) array -> a packed bpy image
    font_file(names)                      the first font file that exists (system faces first, bundled fallbacks)
    OCEAN_ASSETS MODELS ENGINE_ASSETS     asset roots under eidoverse/assets
    D3 / B / B3                           three.js (x, y, z) -> Blender (x, -z, y)
"""

from __future__ import annotations

import os

import numpy as np

from eidoblend import common

ENGINE_ASSETS = common.ASSETS_DIR
OCEAN_ASSETS = os.path.join(ENGINE_ASSETS, 'sets', 'ocean')
MODELS = os.path.join(ENGINE_ASSETS, 'models')
FONTS = os.path.join(ENGINE_ASSETS, 'fonts')
M32 = 0xFFFFFFFF


def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def smooth(x):
    x = clamp01(x)
    return x * x * (3.0 - 2.0 * x)


def lerp(a, b, k):
    return a + (b - a) * k


def seg(u, a, b):
    return clamp01((u - a) / (b - a))


def ease(u, a, b):
    return smooth(seg(u, a, b))


def smoothstep(a, b, x):
    """GLSL smoothstep (also with a > b, as TSL allows)."""
    return smooth((x - a) / (b - a))


def np_smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _imul(a, b):
    return ((a & M32) * (b & M32)) & M32


def rng(seed=1):
    """util.js rng(seed): (seed * 2654435761) >>> 0, then the 0x6D2B79F5 stream. Returns a callable -> [0, 1)."""
    state = [int(seed * 2654435761) & M32]

    def nxt():
        s = (state[0] + 0x6D2B79F5) & M32
        state[0] = s
        t = s
        t = _imul(t ^ (t >> 15), t | 1)
        t = (t ^ ((t + _imul(t ^ (t >> 7), t | 61)) & M32)) & M32
        return ((t ^ (t >> 14)) & M32) / 4294967296.0
    return nxt


# ---------------------------------------------------------------------------------------------- three -> Blender
def B(x, y, z):
    """A three.js (Y-up) point or direction in Blender's Z-up axes."""
    return (x, -z, y)


def B3(v):
    return (v[0], -v[2], v[1])


def T3(v):
    """Blender -> three.js."""
    return (v[0], v[2], -v[1])


# ------------------------------------------------------------------------------------------------- mip chains
def build_mips(data, w=None, h=None):
    """util.js buildMips: RGBA8 (H, W, 4) (or flat with w, h) -> [{'data', 'width', 'height'}] down to 1 x 1, each
    level the 2x2 box filter of the one above in integers ((a + b + c + d) >> 2; odd edges clamp), as the JS."""
    a = np.asarray(data, np.uint8)
    if a.ndim == 1:
        a = a.reshape(h, w, 4)
    sh, sw = a.shape[:2]
    levels = [{'data': a, 'width': sw, 'height': sh}]
    src = a
    while sw > 1 or sh > 1:
        dw, dh = max(1, sw >> 1), max(1, sh >> 1)
        y0 = np.minimum(sh - 1, np.arange(dh) * 2)
        y1 = np.minimum(sh - 1, np.arange(dh) * 2 + 1)
        x0 = np.minimum(sw - 1, np.arange(dw) * 2)
        x1 = np.minimum(sw - 1, np.arange(dw) * 2 + 1)
        s = src.astype(np.uint16)
        acc = s[y0][:, x0] + s[y0][:, x1] + s[y1][:, x0] + s[y1][:, x1]
        src = (acc >> 2).astype(np.uint8)
        levels.append({'data': src, 'width': dw, 'height': dh})
        sw, sh = dw, dh
    return levels


# ------------------------------------------------------------------------------------------------- images
def image_from_array(name, arr, *, colorspace='Non-Color', float_buffer=None, pack=True, interpolation=None):
    """(H, W, C) array, row 0 = Blender's bottom row (v = 0) -> a Blender image (replacing one of that name).

    uint8 arrays become byte images, float arrays float images (32 bit, never halved on the GPU). The pixels are
    packed into the .blend (pack=True), so a saved file needs no side files."""
    import bpy
    a = np.asarray(arr)
    if a.ndim == 2:
        a = a[:, :, None]
    h, w, c = a.shape
    if c < 4:
        pad = np.ones((h, w, 4 - c), dtype=a.dtype) * (255 if a.dtype == np.uint8 else 1.0)
        if c == 1:
            a = np.concatenate([a, a, a, pad[:, :, :1]], axis=2)
        else:
            a = np.concatenate([a, pad], axis=2)
    fb = (a.dtype != np.uint8) if float_buffer is None else float_buffer
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, width=w, height=h, alpha=True, float_buffer=fb)
    img.colorspace_settings.name = colorspace
    px = (a.astype(np.float32) / 255.0) if a.dtype == np.uint8 else a.astype(np.float32)
    img.pixels.foreach_set(px.reshape(-1))
    if fb and hasattr(img, 'use_half_precision'):
        img.use_half_precision = False
    img.alpha_mode = 'CHANNEL_PACKED'
    if pack:
        img.pack()
    img.update()
    return img


def pil_to_array(im):
    """A Pillow image (row 0 = the canvas top) -> uint8 (H, W, C) with row 0 = the canvas top."""
    return np.asarray(im)


# ------------------------------------------------------------------------------------------------- fonts
SYSTEM_FONTS = 'C:/Windows/Fonts'


def font_file(*names):
    """The first existing font among names: absolute paths, Windows system faces ('georgia.ttf') or the bundled
    eidoverse/assets/fonts files ('SpecialElite-Regular.ttf'). util.js ensureFonts registers the same order:
    Georgia / Segoe UI when installed, Special Elite / Exo 2 bundled as the fallback."""
    for n in names:
        for p in (n, os.path.join(SYSTEM_FONTS, n), os.path.join(FONTS, n)):
            if os.path.isfile(p):
                return p
    raise FileNotFoundError(f'[ocean] none of the fonts {names} exists')
