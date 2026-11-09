"""eidoblend.characters.robotics._display: the studio's unlit colours displayed as the WebGPU original displays them.

studio.js's background (#c6cfd1) and GridHelper lines (#acb9bd, centre #748b91) are flat colours. The WebGPU examples and
the inspector render with three's ACESFilmicToneMapping, which the WebGPU renderer applies to the clear colour and the
lines too: the film shows ACES(#c6cfd1) = (204, 208, 209), measured (203, 207, 209). Here the film contract is AgX, and
AgX shows #c6cfd1 as (175, 179, 180). The lit robots stay AgX (the contract); these unlit presentation colours are given
the scene-linear radiance that the scene's own colour management (display device, view transform, look, exposure,
gamma, white balance) displays as three's ACES of the original colour:

    three_aces(colour)                  three r184's ACESFilmicToneMapping (the TSL edition) -> sRGB-encoded 0..1
    display_radiance(scene, targets)    the scene-linear RGB displaying as each sRGB-encoded 0..1 target: Newton steps
                                        on what Image.save_render writes (a 16-bit PNG through a scratch scene that
                                        copies the colour management), cached per colour management and target
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import tempfile
import zlib

import bpy
import numpy as np

from .materials import to_linear

# three/src/nodes/display/ToneMappingFunctions.js (r184): rows as written there (TSL's mat3 takes rows)
_ACES_IN = ((0.59719, 0.35458, 0.04823), (0.07600, 0.90834, 0.01566), (0.02840, 0.13383, 0.83777))
_ACES_OUT = ((1.60475, -0.53108, -0.07367), (-0.10208, 1.10813, -0.00605), (-0.00327, -0.07276, 1.07602))
_SOLVED = {}


def _encode(x):
    x = min(1.0, max(0.0, x))
    return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


def three_aces(colour, exposure=1.0):
    """three's ACESFilmicToneMapping of a colour ('#rrggbb', 0xrrggbb or an sRGB triple, made linear as three's Color
    does) at toneMappingExposure `exposure` -> what the canvas shows, sRGB-encoded 0..1"""
    c = [x * exposure / 0.6 for x in to_linear(colour)]
    c = [sum(_ACES_IN[i][j] * c[j] for j in range(3)) for i in range(3)]
    c = [(x * (x + 0.0245786) - 0.000090537) / (x * ((x + 0.4329510) * 0.983729) + 0.238081) for x in c]
    c = [sum(_ACES_OUT[i][j] * c[j] for j in range(3)) for i in range(3)]
    return tuple(_encode(x) for x in c)


def _read_png(path):
    """an 8- or 16-bit RGB(A) PNG -> float array (h, w, channels) in 0..1 (the encoded values, no colour transform)"""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG: ' + path)
    pos, idat = 8, b''
    w = h = depth = ctype = None
    while pos < len(data):
        n, = struct.unpack('>I', data[pos:pos + 4])
        typ, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if typ == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', body[:10])
        elif typ == b'IDAT':
            idat += body
        pos += 12 + n
    ch = {0: 1, 2: 3, 6: 4}[ctype]
    bpp = ch * depth // 8
    raw = zlib.decompress(idat)
    stride = w * bpp
    out, prev, i = bytearray(), bytearray(stride), 0
    for _y in range(h):
        kind, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        out += line
        prev = line
    arr = np.frombuffer(bytes(out), dtype='>u2' if depth == 16 else 'u1').reshape(h, w, ch).astype(np.float64)
    return arr / (65535.0 if depth == 16 else 255.0)


def _key(scene):
    vs, ds = scene.view_settings, scene.display_settings
    return (ds.display_device, vs.view_transform, vs.look, round(vs.exposure, 6), round(vs.gamma, 6),
            bool(vs.use_curve_mapping), bool(getattr(vs, 'use_white_balance', False)),
            round(getattr(vs, 'white_balance_temperature', 0.0), 3), round(getattr(vs, 'white_balance_tint', 0.0), 3))


def _probe_scene(scene):
    """a scratch scene with the scene's colour management and a 16-bit PNG output, no dither"""
    tmp = bpy.data.scenes.new('studio display probe')
    tmp.display_settings.display_device = scene.display_settings.display_device
    a, b = tmp.view_settings, scene.view_settings
    a.view_transform = b.view_transform
    a.look = b.look
    a.exposure, a.gamma = b.exposure, b.gamma
    for k in ('use_white_balance', 'white_balance_temperature', 'white_balance_tint'):
        if hasattr(b, k):
            setattr(a, k, getattr(b, k))
    a.use_curve_mapping = b.use_curve_mapping
    if b.use_curve_mapping:                  # the curve itself: copied point by point
        for ca, cb in zip(a.curve_mapping.curves, b.curve_mapping.curves):
            while len(ca.points) < len(cb.points):
                ca.points.new(0.5, 0.5)
            for pa, pb in zip(ca.points, cb.points):
                pa.location = pb.location
        a.curve_mapping.update()
    s = tmp.render.image_settings
    s.media_type = 'IMAGE'
    s.file_format = 'PNG'
    s.color_mode = 'RGB'
    s.color_depth = '16'
    tmp.render.dither_intensity = 0.0
    return tmp


def _shown(tmp, rad, folder):
    """what tmp's colour management shows for scene-linear rows rad (N, 3): sRGB-encoded 0..1 (N, 3)"""
    n = len(rad)
    im = bpy.data.images.new('studio display probe', n, 1, alpha=False, float_buffer=True)
    try:
        px = np.ones((n, 4), np.float32)
        px[:, :3] = rad
        im.pixels.foreach_set(px.ravel())
        path = os.path.join(folder, 'probe.png')
        im.save_render(path, scene=tmp)
        return _read_png(path)[0, :, :3]
    finally:
        bpy.data.images.remove(im)


def display_radiance(scene, targets, tolerance=1e-4, iterations=16):
    """the scene-linear RGB the scene's colour management displays as each target (sRGB-encoded 0..1 triples), in
    target order. A target the transform cannot show (beyond its gamut or white) ends at the nearest it reached."""
    targets = [tuple(float(v) for v in t[:3]) for t in targets]
    key = (_key(scene), tuple(tuple(round(v, 6) for v in t) for t in targets))
    if key in _SOLVED:
        return [tuple(x) for x in _SOLVED[key]]
    T = np.asarray(targets, float)
    X = np.array([to_linear(tuple(t)) for t in targets], float)          # the sRGB decoding: Standard's answer
    tmp = _probe_scene(scene)
    folder = tempfile.mkdtemp(prefix='eido_display_')
    try:
        for _ in range(iterations):
            h = np.maximum(1e-4, 0.01 * X)
            rows = []
            for j in range(len(T)):
                rows.append(X[j])
                for i in range(3):
                    e = X[j].copy()
                    e[i] += h[j, i]
                    rows.append(e)
            F = _shown(tmp, np.asarray(rows), folder).reshape(len(T), 4, 3)
            err = T - F[:, 0]
            if np.abs(err).max() < tolerance:
                break
            for j in range(len(T)):
                J = ((F[j, 1:] - F[j, 0]) / h[j][:, None]).T                   # J[:, i] = dF / dx_i
                try:
                    dx = np.linalg.solve(J, err[j])
                except np.linalg.LinAlgError:
                    dx = np.linalg.lstsq(J, err[j], rcond=None)[0]
                step = np.clip(dx, -0.5 * X[j] - 1e-3, 2.0 * X[j] + 0.05)     # damped: stays positive, no overshoot
                X[j] = np.maximum(X[j] + step, 1e-6)
    finally:
        bpy.data.scenes.remove(tmp)
        shutil.rmtree(folder, ignore_errors=True)
    if not np.all(np.isfinite(X)):
        raise RuntimeError('display_radiance diverged for ' + str(targets))
    _SOLVED[key] = X.tolist()
    return [tuple(x) for x in X.tolist()]


def shown(scene, rad):
    """what the scene's colour management shows for scene-linear triples rad: sRGB-encoded 0..1 (the check)"""
    tmp = _probe_scene(scene)
    folder = tempfile.mkdtemp(prefix='eido_display_')
    try:
        return [tuple(r) for r in _shown(tmp, np.asarray(rad, float), folder).tolist()]
    finally:
        bpy.data.scenes.remove(tmp)
        shutil.rmtree(folder, ignore_errors=True)


def to_255(t):
    return tuple(int(math.floor(v * 255 + 0.5)) for v in t)
