"""Swept-cutter geometry over many points at once, and the spatial index of a program's cutting strokes: the numpy side
of eidoverse/robotics/rotary_stock.js (indexRotarySweeps, the stock pass's cutDistance) and rotary_path.js
(sweepDistance). numpy alone, no scene needed.

    from eidoblend.fabrication.rotary.sweeps import index_rotary_sweeps, sweep_distance_np, stroke_bounds
    index = index_rotary_sweeps(path, settings, {'min': lo, 'max': hi}, dims=(40, 16, 16), band=0.002)
    index.bins[ix + nx * (iy + ny * iz)]     # the cutting strokes (segment indices, ascending) that can reach the cell
    d = sweep_distance_np(points, segment, radius, flute_length, fraction, tool)   # signed distance per point

Stock coordinates as in path.py: X along the rotary axis, Y the stock's width, Z its height. The WebGPU stock pass's
cutDistance (TSL, float32) and the planner's sweepDistance (float64) are the same solid: the ball nose and its flute
cylinder (or the flat end and its flute) swept along a stroke up to `fraction` of its length, in the plane of the
stroke. Both are this one function here, in float64.
"""

from __future__ import annotations

import math

import numpy as np

from .._axes import Rec


def stroke_corners(s, settings):
    """The four tool-frame corners of a cutting stroke's swept flute (tip or ball centre, and the flute top, at both
    ends), turned back into stock coordinates: (4, 3). indexRotarySweeps' points, in the same float order."""
    radius, flute = settings['radius'], settings['flute_length']
    c, sn = math.cos(s['a0']), math.sin(s['a0'])
    out = []
    for v in (s['a'], s['b']):
        for h in (0.0 if settings.get('tool') == 'flat' else radius, flute):
            out.append((v[0], (v[2] + h) * sn + v[1] * c, (v[2] + h) * c - v[1] * sn))
    return out


def stroke_bounds(s, settings, band=0.0):
    """(low, high): the axis-aligned box in stock coordinates that holds everything the stroke's sweep removes."""
    p = stroke_corners(s, settings)
    r = settings['radius']
    low = tuple(min(q[k] for q in p) - r - band for k in range(3))
    high = tuple(max(q[k] for q in p) + r + band for k in range(3))
    return low, high


def index_rotary_sweeps(path, settings, bounds, dims=(40, 16, 16), band=.002):
    """indexRotarySweeps: bin every cutting stroke of a RotaryPath into the cells of `bounds` ({'min', 'max'} in stock
    coordinates, dims cells along X, Y, Z) that its swept box (+ band) touches.

    Returns a Rec: bins (list of ascending segment-index lists, x fastest), headers (offset, count, 0, 0 per bin,
    float32), links (the bins' segment indices end to end, float32, padded to 4), records (8 float32 per segment:
    a, a0, b, cut?1:0, the WebGPU stock pass's texture rows), dims, cell, max_bin, bounds."""
    lo, hi = bounds['min'], bounds['max']
    dims = tuple(int(d) for d in dims)
    nb = dims[0] * dims[1] * dims[2]
    bins = [[] for _ in range(nb)]
    records = []
    cell = tuple((hi[k] - lo[k]) / dims[k] for k in range(3))
    for s in path.segments:
        records.extend((*s['a'], s['a0'], *s['b'], 1.0 if s['type'] == 'cut' else 0.0))
        if s['type'] != 'cut':
            continue
        low, high = stroke_bounds(s, settings, band)
        a = [max(0, math.floor((low[k] - lo[k]) / cell[k])) for k in range(3)]
        b = [min(dims[k] - 1, math.floor((high[k] - lo[k]) / cell[k])) for k in range(3)]
        for z in range(a[2], b[2] + 1):
            for y in range(a[1], b[1] + 1):
                base = dims[0] * (y + dims[1] * z)
                for x in range(a[0], b[0] + 1):
                    bins[x + base].append(s['index'])
    headers = np.zeros((nb, 4), dtype=np.float32)
    links = []
    for i, b in enumerate(bins):
        headers[i, 0], headers[i, 1] = len(links), len(b)
        links.extend(b)
    packed = np.zeros(math.ceil(len(links) / 4) * 4, dtype=np.float32)
    packed[:len(links)] = links
    return Rec(bins=bins, headers=headers.ravel(), records=np.asarray(records, dtype=np.float32), links=packed,
                  dims=dims, cell=cell, max_bin=max((len(b) for b in bins), default=0), bounds=bounds)


def cutter_frame(points, a0):
    """(height, lateral) of stock points with the stock turned to A = a0, before the stroke's lateral offset is added:
    height = z cos a0 + y sin a0; lateral = z sin a0 - y cos a0 (three's z, the JS sign)."""
    P = np.asarray(points, dtype=float)
    c, sn = math.cos(a0), math.sin(a0)
    return P[..., 2] * c + P[..., 1] * sn, P[..., 2] * sn - P[..., 1] * c


def sweep_distance_np(points, s, radius, flute_length=.017, fraction=1.0, tool='ball'):
    """sweep_distance for an (N, 3) array of stock points (fraction a scalar or an (N,) array): the same operations
    as path.sweep_distance, element by element."""
    P = np.asarray(points, dtype=float)
    p1, p2 = cutter_frame(P, s['a0'])
    return sweep_core(P[..., 0], p1, p2 + s['a'][1], s, radius, flute_length, fraction, tool)


def sweep_core(p0, p1, p2, s, radius, flute_length=.017, fraction=1.0, tool='ball'):
    """The swept-cutter distance from points already in the stroke's frame: p0 along X, p1 the height, p2 the lateral
    offset from the stroke's plane."""
    f = np.asarray(fraction, dtype=float)
    a, b = s['a'], s['b']
    with np.errstate(all='ignore'):
        if tool == 'flat':
            dx = (b[0] - a[0]) * f
            dy = (b[2] - a[2]) * f
            x, y = p0 - a[0], p1 - a[2]
            w = np.sqrt(np.maximum(0.0, radius * radius - p2 * p2))
            tx = np.clip(x, np.minimum(0.0, dx), np.maximum(0.0, dx))
            radial = np.hypot(x - tx, p2) - radius
            moving = np.abs(dx) > 1e-12
            l1, l2 = (x - w) / dx, (x + w) / dx
            lo = np.where(moving, np.clip(np.minimum(l1, l2), 0.0, 1.0), 0.0)
            hi = np.where(moving, np.clip(np.maximum(l1, l2), 0.0, 1.0), 1.0)
            low = np.minimum(lo * dy, hi * dy)
            high = np.maximum(lo * dy, hi * dy) + flute_length
            norm = np.where(moving, np.sqrt(1 + (dy / dx) ** 2 * (1 + (p2 / np.maximum(w, 1e-7)) ** 2)), 1.0)
            return np.maximum(radial, np.maximum((low - y) / norm, (y - high) / norm))
        ax, ay = a[0], a[2] + radius
        bx = a[0] + (b[0] - a[0]) * f
        by = a[2] + (b[2] - a[2]) * f + radius
        h = flute_length - radius
        bx, by = np.broadcast_to(bx, p0.shape), np.broadcast_to(by, p0.shape)
        axa, aya = np.full(p0.shape, ax), np.full(p0.shape, ay)
        poly = ((axa, aya), (bx, by), (bx, by + h), (axa, aya + h))
        d = np.full(p0.shape, np.inf)
        inside = np.zeros(p0.shape, dtype=bool)
        j = 3
        for i in range(4):
            vx, vy = poly[i]
            wx, wy = poly[j]
            ddx, ddy = wx - vx, wy - vy
            ll = ddx * ddx + ddy * ddy
            u = np.where(ll != 0, np.clip(((p0 - vx) * ddx + (p1 - vy) * ddy) / ll, 0.0, 1.0), 0.0)
            d = np.minimum(d, (p0 - vx - u * ddx) ** 2 + (p1 - vy - u * ddy) ** 2)
            crosses = (vy > p1) != (wy > p1)
            inside ^= crosses & (p0 < (wx - vx) * (p1 - vy) / (wy - vy) + vx)
            j = i
        return np.sqrt(np.where(inside, 0.0, d) + p2 * p2) - radius
