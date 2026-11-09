"""Heightmaps and masks in and out, for other tools (design section 3: Ekigar's export.py PNG16/R32, moved), and a
numpy-only PNG codec so previews and test sheets work in Blender's Python (which has no Pillow).

    export_heightmap(h, out_dir, cell_m, name='height', formats=('png16', 'r32'), x0=0, y0=0)
        -> the sidecar dict, also written as <name>.json: size, cell, extent, row order, height range in metres
    h, meta = read_heightmap('<dir>/height.json')         # metres, row 0 = south, from png16 or r32 + sidecar
    export_mask(m, out_dir, 'slope', lo=0, hi=90)         # an 8- or 16-bit PNG of a mask over [lo, hi]
    write_png(path, a)                                    # uint8 (H, W[, 1|3|4]) or uint16 (H, W); row 0 = top
    a = read_png(path)                                    # any non-interlaced 8/16-bit gray / GA / RGB / RGBA PNG
    encode_r32 / decode_r32 / encode_r16 / decode_r16, normalise_heights

Arrays in this package are row 0 = SOUTH; files other tools read are top-down (row 0 = north), so export flips
once (north_up=True) and the sidecar says which.

Formats: png16 is 16-bit grayscale normalised over the sidecar's [min_m, max_m] (8 bits would quantise 2000 m into
8 m steps); r32 is headerless little-endian float32 in METRES (the sidecar carries width and height); r16 is
headerless little-endian uint16 normalised like png16.
"""

from __future__ import annotations

import json
import os
import struct
import zlib

import numpy as np

_SIG = b'\x89PNG\r\n\x1a\n'
_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}
_COLOUR = {1: 0, 2: 4, 3: 2, 4: 6}
SIDECAR = 'eidoverse-terrain-heightmap/1'


# ------------------------------------------------------------------------------------------------------- PNG ---

def _chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(a, level=6):
    """PNG bytes of a uint8 (H, W[, C]) or uint16 (H, W[, C]) array, C in 1..4, row 0 = top. Rows are Up-filtered
    (vectorised), which compresses heightmaps well."""
    a = np.asarray(a)
    if a.dtype not in (np.uint8, np.uint16):
        raise ValueError(f'encode_png wants uint8 or uint16, got {a.dtype}')
    if a.ndim == 2:
        a = a[:, :, None]
    h, w, c = a.shape
    depth = 8 if a.dtype == np.uint8 else 16
    raw = np.ascontiguousarray(a.astype('>u2') if depth == 16 else a).view(np.uint8).reshape(h, w * c * depth // 8)
    filt = np.empty((h, raw.shape[1] + 1), np.uint8)
    filt[:, 0] = 2
    filt[0, 1:] = raw[0]
    filt[1:, 1:] = raw[1:] - raw[:-1]                        # uint8 arithmetic wraps mod 256, as the Up filter wants
    ihdr = struct.pack('>IIBBBBB', w, h, depth, _COLOUR[c], 0, 0, 0)
    return _SIG + _chunk(b'IHDR', ihdr) + _chunk(b'IDAT', zlib.compress(filt.tobytes(), level)) + _chunk(b'IEND', b'')


def write_png(path, a, level=6):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(encode_png(a, level))
    return path


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)


def decode_png(data):
    """(array, info): uint8 / uint16 (H, W, C), row 0 = top; info has width, height, bit_depth, channels."""
    if data[:8] != _SIG:
        raise ValueError('not a PNG')
    pos, idat, hdr = 8, [], None
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            hdr = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            break
    w, h, depth, colour, _cm, _fm, interlace = hdr
    if interlace:
        raise ValueError('interlaced PNGs are not supported')
    if depth not in (8, 16) or colour not in _CHANNELS:
        raise ValueError(f'PNG colour type {colour} at {depth} bits is not supported (8/16-bit gray, GA, RGB, RGBA)')
    c = _CHANNELS[colour]
    bpp = c * depth // 8
    stride = w * bpp
    rows = np.frombuffer(zlib.decompress(b''.join(idat)), np.uint8).reshape(h, stride + 1)
    kinds, body = rows[:, 0], rows[:, 1:]
    if np.all(kinds == 0):
        out = body.copy()
    elif np.all(kinds == 2):
        out = np.cumsum(body, axis=0, dtype=np.uint8)
    else:
        out = np.empty_like(body)
        prev = np.zeros(stride, np.uint8)
        for r in range(h):
            k, line = int(kinds[r]), body[r]
            if k == 0:
                cur = line.copy()
            elif k == 2:
                cur = line + prev
            elif k == 1:
                cur = np.empty_like(line)
                for b in range(bpp):
                    cur[b::bpp] = np.cumsum(line[b::bpp], dtype=np.uint64).astype(np.uint8)
            elif k in (3, 4):
                ln, pv, cl = line.tolist(), prev.tolist(), [0] * stride
                for i in range(stride):
                    a = cl[i - bpp] if i >= bpp else 0
                    if k == 3:
                        cl[i] = (ln[i] + ((a + pv[i]) >> 1)) & 255
                    else:
                        cl[i] = (ln[i] + _paeth(a, pv[i], pv[i - bpp] if i >= bpp else 0)) & 255
                cur = np.array(cl, np.uint8)
            else:
                raise ValueError(f'PNG filter type {k} is not valid')
            out[r] = prev = cur
    if depth == 16:
        arr = out.reshape(h, w * c, 2).astype(np.uint16)
        arr = ((arr[..., 0] << 8) | arr[..., 1]).reshape(h, w, c)
    else:
        arr = out.reshape(h, w, c)
    return arr, {'width': w, 'height': h, 'bit_depth': depth, 'channels': c}


def read_png(path):
    """A PNG as uint8 / uint16 (H, W) for gray, (H, W, C) otherwise; row 0 = top."""
    with open(path, 'rb') as f:
        arr, info = decode_png(f.read())
    return arr[..., 0] if info['channels'] == 1 else arr


# ------------------------------------------------------------------------------------------------ raw formats ---

def _round_half_up(x):
    return np.floor(np.asarray(x, dtype=np.float64) + 0.5)


def encode_r32(values):
    """Headerless little-endian float32."""
    return np.asarray(values, dtype='<f4').tobytes()


def decode_r32(data, count=None):
    a = np.frombuffer(data, dtype='<f4').astype(np.float64)
    return a if count is None else a[:count]


def encode_r16(values):
    """Headerless little-endian uint16 of [0, 1] values."""
    return np.clip(_round_half_up(np.asarray(values, dtype=np.float64) * 65535), 0, 65535).astype('<u2').tobytes()


def decode_r16(data, count=None):
    a = np.frombuffer(data, dtype='<u2').astype(np.float64) / 65535.0
    return a if count is None else a[:count]


def normalise_heights(data, range_=None):
    """[0, 1] over the data's range (or a pinned `range_` (lo, hi): export a tile SEQUENCE with one range, or the
    seams become cliffs). Returns dict(data, lo, hi, span, clipped_lo, clipped_hi)."""
    d = np.asarray(data, dtype=np.float64)
    lo, hi = (float(d.min()), float(d.max())) if range_ is None else (float(range_[0]), float(range_[1]))
    span = max(hi - lo, 1e-12)
    t = (d - lo) / span
    return {'data': np.clip(t, 0.0, 1.0), 'lo': lo, 'hi': hi, 'span': span, 'clipped_lo': int((t < 0).sum()),
            'clipped_hi': int((t > 1).sum())}


# --------------------------------------------------------------------------------------- heightmaps and masks ---

def export_heightmap(h, out_dir, cell_m, name='height', formats=('png16', 'r32'), x0=0.0, y0=0.0, north_up=True,
                     range_m=None):
    """Write a heightmap in metres (row 0 = south) in each format, and <name>.json, the sidecar carrying what the
    files cannot: size, cell, world origin, row order and the height range. Returns the sidecar dict."""
    h = np.asarray(h, dtype=np.float64)
    rows, cols = h.shape
    os.makedirs(out_dir, exist_ok=True)
    out = h[::-1] if north_up else h
    nrm = normalise_heights(out, range_m)
    files = {}
    for fmt in formats:
        if fmt == 'png16':
            fn = name + '.png'
            write_png(os.path.join(out_dir, fn), np.clip(_round_half_up(nrm['data'] * 65535), 0, 65535)
                      .astype(np.uint16))
            files['png16'] = {'file': fn, 'encoding': 'height_m = min_m + v / 65535 * (max_m - min_m)'}
        elif fmt == 'r32':
            fn = name + '.r32'
            with open(os.path.join(out_dir, fn), 'wb') as f:
                f.write(encode_r32(out))
            files['r32'] = {'file': fn, 'encoding': 'headerless little-endian float32, metres'}
        elif fmt == 'r16':
            fn = name + '.r16'
            with open(os.path.join(out_dir, fn), 'wb') as f:
                f.write(encode_r16(nrm['data']))
            files['r16'] = {'file': fn, 'encoding': 'headerless little-endian uint16: height_m = min_m + v / 65535 '
                                                    '* (max_m - min_m)'}
        else:
            raise ValueError(f"heightmap format {fmt!r} is 'png16', 'r32' or 'r16'")
    meta = {'format': SIDECAR, 'name': name, 'width': cols, 'height': rows, 'cell_m': float(cell_m),
            'extent_m': [cols * float(cell_m), rows * float(cell_m)], 'x0_m': float(x0), 'y0_m': float(y0),
            'row_order': 'row 0 is the NORTH edge' if north_up else 'row 0 is the SOUTH edge',
            'min_m': nrm['lo'], 'max_m': nrm['hi'], 'clipped_low': nrm['clipped_lo'],
            'clipped_high': nrm['clipped_hi'], 'files': files}
    with open(os.path.join(out_dir, name + '.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1)
    return meta


def read_heightmap(sidecar_path, prefer=('r32', 'png16', 'r16')):
    """(h metres float64, row 0 = SOUTH, sidecar dict) from a sidecar written by export_heightmap."""
    with open(sidecar_path, encoding='utf-8') as f:
        meta = json.load(f)
    d = os.path.dirname(os.path.abspath(sidecar_path))
    rows, cols = meta['height'], meta['width']
    for fmt in prefer:
        if fmt not in meta['files']:
            continue
        path = os.path.join(d, meta['files'][fmt]['file'])
        if fmt == 'r32':
            with open(path, 'rb') as f:
                h = decode_r32(f.read()).reshape(rows, cols)
        elif fmt == 'png16':
            v = read_png(path).astype(np.float64) / 65535.0
            h = meta['min_m'] + v * (meta['max_m'] - meta['min_m'])
        else:
            with open(path, 'rb') as f:
                h = meta['min_m'] + decode_r16(f.read()).reshape(rows, cols) * (meta['max_m'] - meta['min_m'])
        if meta['row_order'].startswith('row 0 is the NORTH'):
            h = h[::-1]
        return np.ascontiguousarray(h), meta
    raise FileNotFoundError(f'{sidecar_path}: no file in formats {prefer}')


def export_mask(m, out_dir, name, lo=None, hi=None, bits=8, north_up=True):
    """A mask as an 8- or 16-bit gray PNG over [lo, hi] (default: its own range), plus <name>.json with the range."""
    a = np.asarray(m, dtype=np.float64)
    lo = float(a.min()) if lo is None else float(lo)
    hi = float(a.max()) if hi is None else float(hi)
    t = np.clip((a - lo) / max(hi - lo, 1e-12), 0.0, 1.0)
    t = t[::-1] if north_up else t
    top = 255 if bits == 8 else 65535
    q = _round_half_up(t * top).astype(np.uint8 if bits == 8 else np.uint16)
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, name + '.png'), q)
    meta = {'name': name, 'file': name + '.png', 'bits': bits, 'lo': lo, 'hi': hi,
            'row_order': 'row 0 is the NORTH edge' if north_up else 'row 0 is the SOUTH edge',
            'encoding': f'value = lo + v / {top} * (hi - lo)'}
    with open(os.path.join(out_dir, name + '.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1)
    return meta


def hillshade(h, cell, azimuth_deg=315.0, altitude_deg=40.0, z=1.0):
    """A 0..1 hillshade of a row-0-south field (sun from the north-west, 40 degrees up, as the research's): for
    previews. Write it top-down with write_png(path, to_u8(hillshade(h, cell)[::-1]))."""
    gy, gx = np.gradient(np.asarray(h, dtype=np.float64) * z, float(cell))
    az, alt = np.radians(azimuth_deg), np.radians(altitude_deg)
    lx, ly, lz = np.sin(az) * np.cos(alt), np.cos(az) * np.cos(alt), np.sin(alt)
    return np.clip((-gx * lx - gy * ly + lz) / np.sqrt(gx * gx + gy * gy + 1.0), 0.0, 1.0)


def to_u8(t):
    return np.clip(_round_half_up(np.asarray(t, dtype=np.float64) * 255), 0, 255).astype(np.uint8)
