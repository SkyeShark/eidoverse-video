"""eidoblend.fabrication.cutter_sweep: vertical stock intersections with swept flat and ball-nose cutters
(cutter_sweep.js, MIT).

    swept_cutter_height(x, y, a, b, radius, kind='flat')   the lowest the cutter's lower envelope reaches above the
                         stock point (x, y) while its tip travels the straight move a -> b (Blender (x, y, height)
                         points); inf where the footprint never covers (x, y). A ball nose is minimised along the full
                         3D centre trajectory, so sloping passes are exact, not nearest-XY projections.
    swept_cutter_height_np(x, y, a, b, radius, kind)       the same over numpy arrays of stock points
    index_cutter_sweeps(cuts, width, depth, radius, tiles=24)   spatial bins over the stock (x across width, y across
                         depth): headers[(by * tiles + bx) * 4 + 0 / 1] = start / count into indices, so a stock point
                         visits only the sweeps whose padded bounds cover its bin
"""

from __future__ import annotations

import math

import numpy as np


def swept_cutter_height(x, y, a, b, radius, kind='flat'):
    vx, vy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    qx, qy = x - a[0], y - a[1]
    h2 = vx * vx + vy * vy
    if h2 < 1e-18:
        d2 = qx * qx + qy * qy
        if d2 > radius * radius:
            return math.inf
        return min(a[2], b[2]) + (radius - math.sqrt(max(0.0, radius * radius - d2)) if kind == 'ball' else 0.0)
    h = math.sqrt(h2)
    projected = (qx * vx + qy * vy) / h
    cross = qx * vy - qy * vx               # the 2D cross product keeps the tiny radial distance near a tangent
    perpendicular2 = cross * cross / h2
    if perpendicular2 > radius * radius:
        return math.inf
    section = math.sqrt(max(0.0, radius * radius - perpendicular2))
    lo = max(0.0, (projected - section) / h)
    hi = min(1.0, (projected + section) / h)
    if lo > hi:
        return math.inf
    # minimise the lower sphere envelope along the full 3D centre trajectory (nearest-XY projection is wrong on a slope)
    if kind == 'ball':
        candidate = (projected - dz * section / math.sqrt(h2 + dz * dz)) / h
    else:
        candidate = lo if dz >= 0 else hi
    t = max(lo, min(hi, candidate))
    dx, dy = qx - vx * t, qy - vy * t
    return a[2] + dz * t + (radius - math.sqrt(max(0.0, radius * radius - dx * dx - dy * dy)) if kind == 'ball' else 0.0)


def swept_cutter_height_np(x, y, a, b, radius, kind='flat'):
    """swept_cutter_height over arrays x, y (any matching shapes) for one move a -> b."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    vx, vy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    qx, qy = x - a[0], y - a[1]
    h2 = vx * vx + vy * vy
    r2 = radius * radius
    ball = kind == 'ball'
    if h2 < 1e-18:
        d2 = qx * qx + qy * qy
        out = np.full(np.broadcast(x, y).shape, min(a[2], b[2]))
        if ball:
            out = out + (radius - np.sqrt(np.maximum(0.0, r2 - d2)))
        return np.where(d2 > r2, np.inf, out)
    h = math.sqrt(h2)
    projected = (qx * vx + qy * vy) / h
    cross = qx * vy - qy * vx
    perpendicular2 = cross * cross / h2
    section = np.sqrt(np.maximum(0.0, r2 - perpendicular2))
    lo = np.maximum(0.0, (projected - section) / h)
    hi = np.minimum(1.0, (projected + section) / h)
    if ball:
        candidate = (projected - dz * section / math.sqrt(h2 + dz * dz)) / h
    else:
        candidate = lo if dz >= 0 else hi
    t = np.maximum(lo, np.minimum(hi, candidate))
    dx, dy = qx - vx * t, qy - vy * t
    out = a[2] + dz * t
    if ball:
        out = out + (radius - np.sqrt(np.maximum(0.0, r2 - dx * dx - dy * dy)))
    return np.where((perpendicular2 > r2) | (lo > hi), np.inf, out)


def swept_cutter_height_steps(x, y, pts, radius, kind='flat'):
    """The envelope of each consecutive move pts[k-1] -> pts[k] (k = 1 .. n-1) at the stock points x, y (1D arrays of
    m cells): an (n-1, m) array. One vectorised pass for a run of sub-steps along one segment."""
    pts = np.asarray(pts, dtype=np.float64)
    return swept_cutter_height_moves(x, y, pts[:-1], pts[1:], radius, kind)


def swept_cutter_height_moves(x, y, starts, ends, radius, kind='flat'):
    """The envelope of each move starts[k] -> ends[k] at the stock points x, y (1D arrays of m cells): (n, m)."""
    a = np.asarray(starts, dtype=np.float64)[:, None, :]
    b = np.asarray(ends, dtype=np.float64)[:, None, :]
    x = np.asarray(x, dtype=np.float64)[None, :]
    y = np.asarray(y, dtype=np.float64)[None, :]
    vx, vy, dz = b[..., 0] - a[..., 0], b[..., 1] - a[..., 1], b[..., 2] - a[..., 2]
    qx, qy = x - a[..., 0], y - a[..., 1]
    h2 = vx * vx + vy * vy
    r2 = radius * radius
    ball = kind == 'ball'
    point = h2 < 1e-18
    hs = np.sqrt(np.where(point, 1.0, h2))
    h2s = np.where(point, 1.0, h2)
    projected = (qx * vx + qy * vy) / hs
    cross = qx * vy - qy * vx
    perpendicular2 = np.where(point, qx * qx + qy * qy, cross * cross / h2s)
    section = np.sqrt(np.maximum(0.0, r2 - perpendicular2))
    lo = np.maximum(0.0, (projected - section) / hs)
    hi = np.minimum(1.0, (projected + section) / hs)
    if ball:
        candidate = (projected - dz * section / np.sqrt(h2s + dz * dz)) / hs
    else:
        candidate = np.where(dz >= 0, lo, hi)
    t = np.maximum(lo, np.minimum(hi, candidate))
    dx, dy = qx - vx * t, qy - vy * t
    out = a[..., 2] + dz * t
    if ball:
        out = out + (radius - np.sqrt(np.maximum(0.0, r2 - dx * dx - dy * dy)))
    # a vertical move (no XY travel): the footprint disc at the lower end
    d2 = qx * qx + qy * qy
    vertical = np.minimum(a[..., 2], b[..., 2]) + ((radius - np.sqrt(np.maximum(0.0, r2 - d2))) if ball else 0.0)
    out = np.where(point, vertical, out)
    miss = np.where(point, d2 > r2, (perpendicular2 > r2) | (lo > hi))
    return np.where(miss, np.inf, out)


def index_cutter_sweeps(cuts, width, depth, radius, tiles=24):
    """cuts: records with .a / .b (or ['a'] / ['b']) in Blender (x, y, height). Returns {tiles, headers (float32,
    tiles*tiles*4), indices (list of cut indices), maximum_bin}."""
    bins = [[] for _ in range(tiles * tiles)]

    def cell(v, extent):
        return math.floor((v / extent + .5) * tiles)

    for i, c in enumerate(cuts):
        a, b = (c['a'], c['b']) if isinstance(c, dict) else (c.a, c.b)
        x0 = max(0, cell(min(a[0], b[0]) - radius, width))
        x1 = min(tiles - 1, cell(max(a[0], b[0]) + radius, width))
        y0 = max(0, cell(min(a[1], b[1]) - radius, depth))
        y1 = min(tiles - 1, cell(max(a[1], b[1]) + radius, depth))
        for y in range(y0, y1 + 1):
            row = y * tiles
            for x in range(x0, x1 + 1):
                bins[row + x].append(i)
    headers = np.zeros(tiles * tiles * 4, dtype=np.float32)
    indices = []
    for i, b in enumerate(bins):
        headers[i * 4] = len(indices)
        headers[i * 4 + 1] = len(b)
        indices.extend(b)
    return {'tiles': tiles, 'headers': headers, 'indices': indices, 'maximum_bin': max(len(b) for b in bins)}
