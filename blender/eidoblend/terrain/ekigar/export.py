"""Heightmap and map-set export (Ekigar's src/export/heightmap.js, bake.js, png.js and png_read.js), writing files
to a folder instead of browser downloads.

    export_heightmap(height, out_dir, formats=('png16', 'r32'), world_size=400, vertical_scale=0.3)
        -> the 'ekigar-heightmap/1' sidecar (written beside the files as <name>.json)
    export_maps(height, aux, out_dir, world_size=400, vertical_scale=0.3, tile=(1, 1), stack=None, layers=None)
        -> the 'ekigar-bake/1' terrain.json: 16-bit height, normal, slope and ridge PNGs
    encode_png8 / encode_png16_gray / decode_png / decode_png16_gray, encode_r32 / encode_r16 / decode_r32 / decode_r16

Height ships as 16-bit (8 bits quantise a 2000 m range into ~8 m steps). Headerless formats carry neither dimensions,
row order nor elevation scale, so the sidecar does. Arrays here are [row = v, column = u], row 0 the SOUTH (v = 0)
edge, as the field is evaluated; export_maps writes top-down PNGs (row 0 = north) like Ekigar's bake.
"""
from __future__ import annotations

import json
import os
import struct
import zlib

import numpy as np

from ._tsl import Tile

HEIGHTMAP_FORMATS = {
    'png16': {'ext': 'png', 'bits': 16, 'endian': 'big (PNG spec)', 'sampleType': 'uint16 grayscale',
              'container': 'PNG', 'dimensions': 'embedded'},
    'r32': {'ext': 'r32', 'bits': 32, 'endian': 'little', 'sampleType': 'IEEE-754 float32',
            'container': 'headerless', 'dimensions': 'sidecar'},
    'r16': {'ext': 'r16', 'bits': 16, 'endian': 'little', 'sampleType': 'uint16', 'container': 'headerless',
            'dimensions': 'sidecar'},
    'raw': {'ext': 'raw', 'bits': 16, 'endian': 'little', 'sampleType': 'uint16', 'container': 'headerless',
            'dimensions': 'sidecar'},
}


def _round_half_up(x):
    return np.floor(np.asarray(x, dtype=np.float64) + 0.5)


# ------------------------------------------------------------------------------------------------------- PNG ---

def _chunk(kind, data):
    body = kind.encode('ascii') + data
    return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)


def _build_png(width, height, bit_depth, colour_type, rows):
    raw = b''.join(b'\x00' + r for r in rows)
    ihdr = struct.pack('>IIBBBBB', width, height, bit_depth, colour_type, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + _chunk('IHDR', ihdr) + _chunk('IDAT', zlib.compress(raw, 6)) + _chunk('IEND', b''))


def encode_png8(width, height, data, channels=3):
    """8-bit image from a (height, width[, channels]) uint8 array, rows in the order given (row 0 = top)."""
    a = np.asarray(data, dtype=np.uint8).reshape(height, width * channels)
    colour = {1: 0, 3: 2, 4: 6}[channels]
    return _build_png(width, height, 8, colour, [a[y].tobytes() for y in range(height)])


def encode_png16_gray(width, height, values):
    """16-bit grayscale from floats in [0, 1], written big-endian per the PNG spec (row 0 = top)."""
    q = np.clip(_round_half_up(np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0) * 65535), 0, 65535)
    a = q.astype('>u2').reshape(height, width)
    return _build_png(width, height, 16, 0, [a[y].tobytes() for y in range(height)])


_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def _unfilter(raw, width, height, bpp, stride):
    out = np.zeros((height, stride), dtype=np.uint8)
    prior = np.zeros(stride, dtype=np.int64)
    pos = 0
    for y in range(height):
        ft = raw[pos]
        line = np.frombuffer(raw, dtype=np.uint8, count=stride, offset=pos + 1).astype(np.int64)
        pos += stride + 1
        if ft == 0:
            rec = line
        elif ft == 2:
            rec = (line + prior) & 255
        elif ft == 1:
            rec = line.copy()
            for i in range(bpp, stride):
                rec[i] = (rec[i] + rec[i - bpp]) & 255
        elif ft == 3:
            rec = line.copy()
            for i in range(stride):
                left = rec[i - bpp] if i >= bpp else 0
                rec[i] = (rec[i] + ((left + prior[i]) >> 1)) & 255
        elif ft == 4:
            rec = line.copy()
            for i in range(stride):
                a = rec[i - bpp] if i >= bpp else 0
                b = prior[i]
                c = prior[i - bpp] if i >= bpp else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                rec[i] = (rec[i] + pred) & 255
        else:
            raise ValueError(f'png_read: filter type {ft} not supported')
        out[y] = rec
        prior = rec
    return out


def decode_png(data: bytes):
    """Decode a non-interlaced 8- or 16-bit gray / gray-alpha / RGB / RGBA PNG. Returns dict(width, height, bitDepth,
    channels, data) with data a (height, width, channels) uint8 or uint16 array, row 0 = top."""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('png_read: bad signature')
    o = 8
    idat = []
    width = height = bit_depth = colour = interlace = 0
    while o < len(data):
        ln, kind = struct.unpack('>I4s', data[o:o + 8])
        body = data[o + 8:o + 8 + ln]
        if kind == b'IHDR':
            width, height, bit_depth, colour, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            break
        o += 12 + ln
    if interlace:
        raise ValueError('png_read: interlaced PNG not supported')
    ch = _CHANNELS.get(colour)
    if not ch:
        raise ValueError(f'png_read: colour type {colour} not supported')
    if bit_depth not in (8, 16):
        raise ValueError(f'png_read: bit depth {bit_depth} not supported')
    raw = zlib.decompress(b''.join(idat))
    bps = bit_depth // 8
    stride = width * ch * bps
    flat = _unfilter(raw, width, height, max(1, ch * bps), stride)
    if bit_depth == 8:
        return {'width': width, 'height': height, 'bitDepth': 8, 'channels': ch,
                'data': flat.reshape(height, width, ch)}
    px = flat.reshape(height, width * ch, 2).astype(np.uint16)
    return {'width': width, 'height': height, 'bitDepth': 16, 'channels': ch,
            'data': ((px[..., 0] << 8) | px[..., 1]).reshape(height, width, ch)}


def decode_png16_gray(data: bytes):
    """A 16-bit gray PNG back to the [0, 1] floats encode_png16_gray was given: dict(width, height, data (h, w))."""
    img = decode_png(data)
    if img['bitDepth'] != 16 or img['channels'] != 1:
        raise ValueError(f"decode_png16_gray: got {img['bitDepth']}-bit x{img['channels']}")
    return {'width': img['width'], 'height': img['height'], 'data': img['data'][..., 0] / 65535.0}


# ------------------------------------------------------------------------------------------------ raw formats ---

def encode_r32(values):
    """Headerless little-endian float32."""
    return np.asarray(values, dtype='<f4').tobytes()


def encode_r16(values):
    """Headerless little-endian uint16 of [0, 1] values."""
    return np.clip(_round_half_up(np.asarray(values, dtype=np.float64) * 65535), 0, 65535).astype('<u2').tobytes()


def decode_r32(data: bytes, count=None):
    a = np.frombuffer(data, dtype='<f4').astype(np.float64)
    return a if count is None else a[:count]


def decode_r16(data: bytes, count=None):
    a = np.frombuffer(data, dtype='<u2').astype(np.float64) / 65535.0
    return a if count is None else a[:count]


def normalise_heights(data, range_=None):
    """Normalise to [0, 1] and report the mapping; `range_` pins it (export a tile SEQUENCE with one range, or the
    seams become cliffs). Returns dict(data, lo, hi, span, dataLo, dataHi, clippedLo, clippedHi)."""
    d = np.asarray(data, dtype=np.float64)
    lo, hi = float(d.min()), float(d.max())
    use_lo = range_[0] if range_ else lo
    use_hi = range_[1] if range_ else hi
    span = max(use_hi - use_lo, 1e-12)
    t = (d - use_lo) / span
    return {'data': np.clip(t, 0.0, 1.0), 'lo': use_lo, 'hi': use_hi, 'span': span, 'dataLo': lo, 'dataHi': hi,
            'clippedLo': int((t < 0).sum()), 'clippedHi': int((t > 1).sum())}


def export_heightmap(height, out_dir, formats=('png16', 'r32'), world_size=400.0, vertical_scale=0.3,
                     height_range_metres=None, range_=None, flip_y=False, name='ekigar_height'):
    """Write a plain heightmap in each format plus the sidecar carrying what the files cannot. `height` is
    [row = v, column = u] with row 0 the south edge; flip_y writes north first. Returns the sidecar dict."""
    h = np.asarray(height, dtype=np.float64)
    H, W = h.shape
    os.makedirs(out_dir, exist_ok=True)
    n = normalise_heights(h, range_)
    rows = n['data'][::-1] if flip_y else n['data']
    warnings = []
    if W != H:
        warnings.append(f'field is {W}x{H}, not square: headerless .r32/.r16/.raw files do not carry dimensions and '
                        f'may be inferred as square. Use png16, or export square.')
    files = []
    for fmt in formats:
        spec = HEIGHTMAP_FORMATS.get(fmt)
        if not spec:
            raise ValueError(f"export_heightmap: unknown format '{fmt}'")
        fn = f"{name}.{spec['ext']}"
        if fmt == 'png16':
            blob = encode_png16_gray(W, H, rows)
        elif fmt == 'r32':
            blob = encode_r32(rows)
        else:
            blob = encode_r16(rows)
        with open(os.path.join(out_dir, fn), 'wb') as f:
            f.write(blob)
        files.append(dict({'file': fn, 'format': fmt}, **spec))
    height_m = height_range_metres if height_range_metres is not None else n['span'] * world_size * vertical_scale
    sidecar = {
        'format': 'ekigar-heightmap/1', 'generator': 'Ekigar (Blender edition)',
        'width': W, 'height': H, 'square': W == H,
        'rowOrder': 'row 0 is the NORTH (v = 1) edge' if flip_y else 'row 0 is the SOUTH (v = 0) edge',
        'rowOrderNote': 'Row order is not encoded by these formats. If the destination appears vertically flipped, '
                        'toggle flip_y and keep that setting for the pipeline.',
        'worldSizeMetres': world_size, 'metresPerTexel': world_size / W,
        'elevation': {
            'encodedRange': [0, 1], 'heightRangeMetres': height_m, 'fieldMin': n['lo'], 'fieldMax': n['hi'],
            'observedFieldMin': n['dataLo'], 'observedFieldMax': n['dataHi'],
            'clippedLowTexels': n['clippedLo'], 'clippedHighTexels': n['clippedHi'], 'metresPerUnit': height_m,
            'formula': 'elevation_metres = encoded * heightRangeMetres, with encoded in [0,1]',
            'note': 'No format written here carries a physical elevation scale. Transport this block with the file.',
        },
        'files': files, 'warnings': warnings,
        'formatContract': {
            'png16': '16-bit grayscale PNG with embedded dimensions',
            'r32': 'headerless little-endian IEEE-754 float32 samples normalised to [0,1]',
            'r16': 'headerless little-endian uint16 samples normalised to [0,65535]',
            'externalMetadata': 'raw dimensions, row order, and elevation scale are carried by this sidecar',
        },
    }
    with open(os.path.join(out_dir, f'{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(sidecar, f, indent=2)
    return sidecar


def export_maps(height, aux, out_dir, world_size=400.0, vertical_scale=0.3, tile=(1.0, 1.0), stack=None,
                layers=None, green='ekigar'):
    """Ekigar's bake: 16-bit height, tangent normal, slope and ridge PNGs (top-down, row 0 = north) plus a
    terrain.json sidecar with the texel density, height range, tiling and the graph that made them.

    green  'ekigar' (default) writes the normal map byte for byte as bake.js does. Its sidecar calls it OpenGL (+Y up),
           but bake.js differentiates down the top-down rows, so a slope rising to the north writes green ABOVE 0.5:
           the green channel is DirectX order. 'opengl' flips green so the map is what the label says (and what
           Blender's Normal Map node and glTF expect)."""
    if green not in ('ekigar', 'opengl'):
        raise ValueError("export_maps: green is 'ekigar' or 'opengl'")
    h = np.asarray(height, dtype=np.float64)[::-1]          # top-down, as bake.js flips the readback
    N = h.shape[1]
    os.makedirs(out_dir, exist_ok=True)
    lo, hi = float(h.min()), float(h.max())
    span = max(hi - lo, 1e-6)
    t = Tile.of(tile)
    wrap_x, wrap_y = t.x > 0, t.y > 0

    def at(di, dj):
        a = h
        a = np.roll(a, -di, axis=1) if wrap_x else a[:, np.clip(np.arange(N) + di, 0, N - 1)]
        # rows are top-down here, so +y (north) is row - 1, exactly as bake.js indexes its flipped array
        a = np.roll(a, -dj, axis=0) if wrap_y else a[np.clip(np.arange(a.shape[0]) + dj, 0, a.shape[0] - 1), :]
        return a

    norm = (h - lo) / span
    with open(os.path.join(out_dir, 'ekigar_height16.png'), 'wb') as f:
        f.write(encode_png16_gray(N, h.shape[0], norm))
    m_per_texel = world_size / N
    height_m = span * world_size * vertical_scale
    dx = (at(1, 0) - at(-1, 0)) / span * height_m / (2 * m_per_texel)
    dy = (at(0, 1) - at(0, -1)) / span * height_m / (2 * m_per_texel)
    ln = np.sqrt(dx * dx + dy * dy + 1.0)
    gy = -dy if green == 'ekigar' else dy                   # rows run south: +dy here is -dh/dv
    nrm = np.stack([-dx / ln * 0.5 + 0.5, gy / ln * 0.5 + 0.5, 1.0 / ln * 0.5 + 0.5], axis=-1)
    with open(os.path.join(out_dir, 'ekigar_normal.png'), 'wb') as f:
        f.write(encode_png8(N, h.shape[0], _round_half_up(nrm * 255).astype(np.uint8), 3))
    slope = _round_half_up(np.minimum(1.0, np.hypot(dx, dy)) * 255).astype(np.uint8)
    with open(os.path.join(out_dir, 'ekigar_slope.png'), 'wb') as f:
        f.write(encode_png8(N, h.shape[0], slope, 1))
    ridge_src = np.zeros_like(h) if aux is None else np.asarray(aux, dtype=np.float64)[::-1]
    ridge = _round_half_up(np.clip(ridge_src * 0.5 + 0.5, 0.0, 1.0) * 255).astype(np.uint8)
    with open(os.path.join(out_dir, 'ekigar_ridge.png'), 'wb') as f:
        f.write(encode_png8(N, h.shape[0], ridge, 1))
    sidecar = {
        'format': 'ekigar-bake/1', 'resolution': N, 'worldSizeMetres': world_size, 'metresPerTexel': m_per_texel,
        'heightRangeMetres': height_m, 'tiling': {'x': bool(wrap_x), 'y': bool(wrap_y)},
        'rowOrder': 'top-down (row 0 = +v edge, PNG convention)', 'stack': stack, 'materialLayers': layers,
        'maps': {
            'height': {'file': 'ekigar_height16.png', 'bits': 16, 'encoding': 'linear 0..1 over heightRangeMetres'},
            'normal': {'file': 'ekigar_normal.png', 'space': 'tangent, OpenGL (+Y up)'} if green == 'ekigar' else
                      {'file': 'ekigar_normal.png', 'space': 'tangent, OpenGL (+Y up), green checked: a slope rising '
                                                             'north has green below 0.5'},
            'slope': {'file': 'ekigar_slope.png', 'encoding': '0..1 = |grad|, clamped'},
            'ridge': {'file': 'ekigar_ridge.png', 'encoding': '0.5 = neutral, >0.5 ridge, <0.5 crease'},
        },
    }
    with open(os.path.join(out_dir, 'terrain.json'), 'w', encoding='utf-8') as f:
        json.dump(sidecar, f, indent=2, default=str)
    return sidecar


def linear_to_srgb(v):
    """export/ops.js linearToSRGB: the sRGB transfer of a linear value (clamped to 0..1), arrays elementwise."""
    c = np.clip(np.asarray(v, dtype=np.float64), 0.0, 1.0)
    out = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return float(out) if np.ndim(out) == 0 else out


def _srgb_to_linear_table():
    c = np.arange(256, dtype=np.float64) / 255.0
    t = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    t.setflags(write=False)
    return t


# export/ops.js SRGB_TO_LINEAR: the real sRGB EOTF (not pow 2.2) for every 8-bit code, float64; index it with uint8
# samples (SRGB_TO_LINEAR[png]) to decode an sRGB texture to linear
SRGB_TO_LINEAR = _srgb_to_linear_table()


def srgb_to_linear(v):
    """The sRGB EOTF of values in 0..1 (arrays elementwise): what SRGB_TO_LINEAR tabulates at i / 255."""
    c = np.clip(np.asarray(v, dtype=np.float64), 0.0, 1.0)
    out = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(out) if np.ndim(out) == 0 else out
