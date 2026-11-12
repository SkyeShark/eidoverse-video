"""Real landform references: real elevation data of named landforms, the ground truth the new make_terrain is
judged against.

Each reference is a north-up square of real elevation data, resampled onto a local metric grid, in data/:

    <name>.png           16-bit greyscale PNG: height_m = height_min_m + v / 65535 * (height_max_m - height_min_m)
    <name>.json          what it is (landform, place, centre in WGS84), the grid (pixel_size_m, extent_m), the height
                         range, the source (dataset, native resolution, how it was resampled), its licence and
                         attribution, and a few shape statistics (relief, slope percentiles, hypsometric integral)
    <name>_context.*     the same place, wider and coarser: the surround the eye-level renders stand in, so their
                         horizon is real terrain, not the edge of the tile
    <name>_water.png     where the landform has open water: 8-bit mask, 0 land, 255 sea, 128 + i the i-th lake of
                         the JSON's `water` list (each with its surface level_m: DEMs carry a lake as its flat surface)

The grid is a local azimuthal equidistant projection (sphere, R = 6371008.8 m) centred on centre_lat / centre_lon,
so pixels are square metres and north is up. Pixel (row r, column c) has its centre at
x = (c + 0.5 - cols / 2) * p metres east and y = (rows / 2 - r - 0.5) * p metres north of the centre: row 0 is the
north edge, column 0 the west edge. Heights are metres above the source's vertical datum (named in the JSON).

    import sys; sys.path.insert(0, '<worktree>/blender/tests/terrain/reference')
    import landform_refs as R
    R.names()                                  # every reference in data/
    h, meta = R.load('mount_fuji')             # float32 metres, shape (rows, cols)
    hc, mc = R.load('mount_fuji', context=True)
    x, y = R.grid_xy(meta)                     # pixel-centre metres east / north of the centre
    z = R.sample(h, meta, x_m, y_m)            # bilinear height at local metres
    x_m, y_m = R.latlon_to_xy(meta, lat, lon)  # a real place (a viewpoint, a summit) in the grid

Needs numpy only (the PNG codec here is numpy + zlib), so it runs in Blender's Python too. fetch_references.py
builds data/ from the public sources; render_references.py renders each reference in Blender (grey clay, make_sky).
"""
import json
import math
import os
import struct
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
EARTH_R = 6371008.8                    # mean Earth radius, metres (the projection's sphere)
_SIG = b'\x89PNG\r\n\x1a\n'


# ---------------------------------------------------------------- 16-bit PNG, numpy + zlib
def write_png(path, v, depth=16):
    """Write a 2-D uint16 (depth 16) or uint8 (depth 8) array as a greyscale PNG (rows Up-filtered, zlib 9)."""
    if depth == 16:
        a = np.ascontiguousarray(np.asarray(v, dtype=np.uint16).astype('>u2'))
    else:
        a = np.ascontiguousarray(np.asarray(v, dtype=np.uint8))
    h, w = a.shape
    raw = a.view(np.uint8).reshape(h, w * depth // 8)
    filt = np.empty((h, raw.shape[1] + 1), np.uint8)
    filt[:, 0] = 2
    filt[0, 1:] = raw[0]
    filt[1:, 1:] = raw[1:] - raw[:-1]                     # uint8 arithmetic wraps mod 256, as the Up filter wants

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(_SIG + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, 0, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(filt.tobytes(), 9)) + chunk(b'IEND', b''))


def write_png16(path, v):
    write_png(path, v, 16)


def _unfilter_row(kind, line, prev, bpp):
    if kind == 0:
        return line.copy()
    if kind == 2:
        return line + prev
    if kind == 1:
        out = np.empty_like(line)
        for k in range(bpp):
            out[k::bpp] = (np.cumsum(line[k::bpp], dtype=np.uint64) & 255).astype(np.uint8)
        return out
    out = [0] * len(line)                                 # Average and Paeth run byte by byte (other writers' files)
    ln, pv = line.tolist(), prev.tolist()
    for i in range(len(ln)):
        a = out[i - bpp] if i >= bpp else 0
        b = pv[i]
        if kind == 3:
            out[i] = (ln[i] + ((a + b) >> 1)) & 255
        else:
            c = pv[i - bpp] if i >= bpp else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            out[i] = (ln[i] + pr) & 255
    return np.array(out, np.uint8)


def read_png(path):
    """A greyscale PNG (8 or 16 bit, not interlaced) as a uint8 / uint16 array; any writer's filters."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != _SIG:
        raise ValueError(f'{path}: not a PNG')
    pos, idat, hdr = 8, [], None
    while pos < len(data):
        n, kind = struct.unpack('>I', data[pos:pos + 4])[0], data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            hdr = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            break
    w, h, depth, ctype, _cm, _fm, interlace = hdr
    if ctype != 0 or interlace != 0 or depth not in (8, 16):
        raise ValueError(f'{path}: greyscale 8/16-bit non-interlaced PNG expected (got type {ctype}, depth {depth})')
    bpp = depth // 8
    rows = np.frombuffer(zlib.decompress(b''.join(idat)), np.uint8).reshape(h, w * bpp + 1)
    kinds, body = rows[:, 0], rows[:, 1:]
    if np.all(kinds == 2) or np.all(kinds == 0):          # this module's own files: one vectorised pass
        out = body.copy() if kinds[0] == 0 else np.cumsum(body, axis=0, dtype=np.uint8)
    else:
        out = np.empty_like(body)
        prev = np.zeros(w * bpp, np.uint8)
        for r in range(h):
            prev = out[r] = _unfilter_row(int(kinds[r]), body[r], prev, bpp)
    if depth == 16:
        return out.reshape(h, w * 2).view('>u2').astype(np.uint16)
    return out


# ---------------------------------------------------------------- the local grid
def grid_xy(meta):
    """(x, y): pixel-centre coordinates in metres east / north of the centre, each shaped (rows, cols)."""
    rows, cols, p = meta['rows'], meta['cols'], meta['pixel_size_m']
    x = (np.arange(cols) + 0.5 - cols / 2.0) * p
    y = (rows / 2.0 - np.arange(rows) - 0.5) * p
    return np.meshgrid(x, y)


def xy_to_latlon(lat0, lon0, x, y):
    """Inverse spherical azimuthal equidistant projection: local metres -> WGS84 degrees."""
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    p0, l0 = math.radians(lat0), math.radians(lon0)
    rho = np.hypot(x, y)
    c = rho / EARTH_R
    with np.errstate(invalid='ignore', divide='ignore'):
        lat = np.arcsin(np.cos(c) * math.sin(p0) + np.where(rho > 0, y * np.sin(c) * math.cos(p0) / rho, 0.0))
        lon = l0 + np.arctan2(x * np.sin(c), rho * math.cos(p0) * np.cos(c) - y * math.sin(p0) * np.sin(c))
    return np.degrees(lat), np.degrees(lon)


def latlon_to_xy_raw(lat0, lon0, lat, lon):
    """Forward spherical azimuthal equidistant projection: WGS84 degrees -> local metres (x east, y north)."""
    p0, l0 = math.radians(lat0), math.radians(lon0)
    p, dl = np.radians(np.asarray(lat, np.float64)), np.radians(np.asarray(lon, np.float64)) - l0
    cosc = math.sin(p0) * np.sin(p) + math.cos(p0) * np.cos(p) * np.cos(dl)
    c = np.arccos(np.clip(cosc, -1.0, 1.0))
    k = np.where(c > 1e-12, c / np.maximum(np.sin(c), 1e-300), 1.0)
    x = EARTH_R * k * np.cos(p) * np.sin(dl)
    y = EARTH_R * k * (math.cos(p0) * np.sin(p) - math.sin(p0) * np.cos(p) * np.cos(dl))
    return x, y


def latlon_to_xy(meta, lat, lon):
    """A WGS84 position in a reference's grid: metres east / north of its centre."""
    return latlon_to_xy_raw(meta['centre_lat'], meta['centre_lon'], lat, lon)


def sample(h, meta, x, y):
    """Bilinear height (metres) at local metres x east, y north (clamped to the grid)."""
    rows, cols, p = meta['rows'], meta['cols'], meta['pixel_size_m']
    c = np.clip(np.asarray(x, np.float64) / p + cols / 2.0 - 0.5, 0, cols - 1)
    r = np.clip(rows / 2.0 - 0.5 - np.asarray(y, np.float64) / p, 0, rows - 1)
    c0 = np.minimum(np.floor(c).astype(int), cols - 2)
    r0 = np.minimum(np.floor(r).astype(int), rows - 2)
    fc, fr = c - c0, r - r0
    a, b = h[r0, c0], h[r0, c0 + 1]
    d, e = h[r0 + 1, c0], h[r0 + 1, c0 + 1]
    return (a * (1 - fc) + b * fc) * (1 - fr) + (d * (1 - fc) + e * fc) * fr


# ---------------------------------------------------------------- the files
def names(root=DATA):
    """Every reference in data/ (the context files are reached through load(name, context=True))."""
    if not os.path.isdir(root):
        return []
    return sorted(f[:-5] for f in os.listdir(root) if f.endswith('.json') and not f.endswith('_context.json'))


def load(name, context=False, root=DATA):
    """(height float32 metres (rows, cols), meta dict) of a reference, or of its context surround."""
    stem = name + ('_context' if context else '')
    with open(os.path.join(root, stem + '.json'), encoding='utf-8') as f:
        meta = json.load(f)
    v = read_png(os.path.join(root, meta['height_png']))
    lo, hi = meta['height_min_m'], meta['height_max_m']
    h = (lo + v.astype(np.float64) * ((hi - lo) / 65535.0)).astype(np.float32)
    return h, meta


def load_water(name, root=DATA):
    """(mask uint8, water bodies) of a reference, or None when it has no open water."""
    with open(os.path.join(root, name + '.json'), encoding='utf-8') as f:
        meta = json.load(f)
    if not meta.get('water_mask_png'):
        return None
    return read_png(os.path.join(root, meta['water_mask_png'])), meta['water']


def save(stem, h, meta, root=DATA):
    """Write <stem>.png (16-bit, the height range stretched over 0..65535) and <stem>.json; returns the JSON dict."""
    os.makedirs(root, exist_ok=True)
    h = np.asarray(h, np.float64)
    lo, hi = float(np.floor(h.min() * 100) / 100), float(np.ceil(h.max() * 100) / 100)
    hi = max(hi, lo + 0.01)
    v = np.round((h - lo) / (hi - lo) * 65535.0).astype(np.uint16)
    write_png16(os.path.join(root, stem + '.png'), v)
    meta = dict(meta)
    meta.update(height_png=stem + '.png', rows=int(h.shape[0]), cols=int(h.shape[1]), height_min_m=lo,
                height_max_m=hi, height_step_m=(hi - lo) / 65535.0,
                encoding='16-bit greyscale PNG: height_m = height_min_m + v / 65535 * (height_max_m - height_min_m)')
    with open(os.path.join(root, stem + '.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    return meta


# ---------------------------------------------------------------- reading the shape
def slope_deg(h, pixel_m):
    gy, gx = np.gradient(np.asarray(h, np.float64), pixel_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def hillshade(h, pixel_m, azimuth_deg=315.0, altitude_deg=45.0, z_factor=1.0):
    """Classic cartographic hillshade, 0..1 (light from azimuth, compass degrees, north = row 0)."""
    gy, gx = np.gradient(np.asarray(h, np.float64) * z_factor, pixel_m)
    gy = -gy                                              # rows run south: d/dy north = -d/drow
    az, alt = math.radians(azimuth_deg), math.radians(altitude_deg)
    lx, ly, lz = math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)
    n = np.sqrt(gx * gx + gy * gy + 1.0)
    return np.clip((-gx * lx - gy * ly + lz) / n, 0.0, 1.0)


def shape_stats(h, pixel_m):
    """Relief, slope percentiles and the hypsometric integral: numbers a generated landform can be held to."""
    s = slope_deg(h, pixel_m)
    lo, hi, mean = float(h.min()), float(h.max()), float(h.mean())
    return dict(relief_m=round(hi - lo, 2), mean_m=round(mean, 2),
                hypsometric_integral=round((mean - lo) / max(hi - lo, 1e-6), 4),
                slope_deg_p10=round(float(np.percentile(s, 10)), 2), slope_deg_p50=round(float(np.percentile(s, 50)), 2),
                slope_deg_p90=round(float(np.percentile(s, 90)), 2), slope_deg_p99=round(float(np.percentile(s, 99)), 2),
                slope_deg_mean=round(float(s.mean()), 2))
