"""One-time volumetric engagement sampling for deterministic chip events: the port of
eidoverse/robotics/rotary_removal.js (rotaryRemoval). numpy alone, no scene needed.

    from eidoblend.fabrication.rotary.removal import rotary_removal
    r = rotary_removal(program.path, program.settings, resolution=(96, 28, 28))
    r.events          # [{'position': (x, y, z), 'time': s, 'volume': m3, 'floor': 0, 'total_volume': m3}] by time
    r.removed_volume  # m3 of blank the program removes (sampled at the voxel centres)

Every voxel centre inside the prepared blank is charged to the FIRST cutting stroke whose full sweep reaches it, at
the fraction of that stroke where the cutter first touches it (14 bisections); voxels are bucketed per stroke into
eighths, and each bucket becomes one event at its mean position and time. Air travel and repeated cuts add nothing.
Event positions are machine coordinates relative to the bed top, the stock turned to the stroke's A angle:
(x + axis_x, y, z + axis_height), as cutting_debris expects them.

resolution counts voxels along the stock's X (length), Y (width) and Z (height): the WebGPU [nx, ny, nz] counted
three's y (height) second; for a square blank the numbers are the same.
"""

from __future__ import annotations

import math

import numpy as np

from .._axes import Rec
from .path import CENTRE_SEAT
from .sweeps import index_rotary_sweeps, stroke_bounds, sweep_distance_np


def blank_distance_np(P, settings):
    """rotary_blank_distance over an (..., 3) array."""
    L, W, H = settings['stock_length'], settings['stock_width'], settings['stock_height']
    P = np.asarray(P, dtype=float)
    q = np.stack([np.abs(P[..., 0]) - L / 2, np.abs(P[..., 1]) - W / 2, np.abs(P[..., 2]) - H / 2], -1)
    box = np.sqrt((np.maximum(q, 0.0) ** 2).sum(-1)) + np.minimum(q.max(-1), 0.0)
    rho = np.hypot(P[..., 1], P[..., 2])
    h = P[..., 0] - (L / 2 - CENTRE_SEAT['depth'])
    cone = np.maximum(rho * math.cos(CENTRE_SEAT['half_angle']) - h * math.sin(CENTRE_SEAT['half_angle']), -h)
    pilot = np.maximum(rho - CENTRE_SEAT['pilot_radius'], L / 2 - CENTRE_SEAT['pilot_depth'] - P[..., 0])
    return np.maximum(box, -np.minimum(cone, pilot))


def _distance_time_np(s, distance):
    """eidoblend.fabrication.cutting.distance_time over an array of distances along one stroke."""
    d = np.clip(np.asarray(distance, dtype=float), 0.0, s['length'])
    a = s['acceleration']
    cruise = s['da'] + s['peak'] * s['tc']
    with np.errstate(all='ignore'):
        t_acc = s['t0'] + (np.sqrt(s['v0'] ** 2 + 2 * a * d) - s['v0']) / a
        t_cru = s['t0'] + s['ta'] + (d - s['da']) / s['peak']
        t_dec = s['t1'] - (np.sqrt(s['v1'] ** 2 + 2 * a * (s['length'] - d)) - s['v1']) / a
    return np.where(d <= s['da'], t_acc, np.where(d < cruise, t_cru, t_dec))


def rotary_removal(path, settings, resolution=(96, 28, 28)):
    """rotaryRemoval: the program's chip events (see the module docstring). settings needs stock_length,
    stock_width, stock_height, radius, flute_length, axis_x, axis_height (and tool, 'ball' when absent)."""
    if len(resolution) != 3 or any(not isinstance(v, int) or isinstance(v, bool) or v < 12 or v > 256
                                   for v in resolution):
        raise ValueError('Invalid removal sampling resolution')
    L, W, H = settings['stock_length'], settings['stock_width'], settings['stock_height']
    radius, flute = settings['radius'], settings['flute_length']
    tool = settings.get('tool') or 'ball'
    axis_x, axis_h = settings['axis_x'], settings['axis_height']
    lo = np.array([-L / 2, -W / 2, -H / 2])
    hi = np.array([L / 2, W / 2, H / 2])
    res = np.array(resolution)
    cell = (hi - lo) / res
    volume = float(cell[0] * cell[1] * cell[2])
    cs = dict(settings, tool=tool)
    # the WebGPU bins exist to find candidate strokes per voxel; the first stroke reaching a voxel is the same found
    # stroke by stroke, so the bins only count the queries the JS loop made (a diagnostic)
    indexed = index_rotary_sweeps(path, cs, {'min': tuple(lo), 'max': tuple(hi)}, (32, 12, 12), 0)
    nx, ny, nz = resolution
    ii, jj, kk = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing='ij')
    P = np.stack([lo[0] + (ii + .5) * cell[0], lo[1] + (jj + .5) * cell[1], lo[2] + (kk + .5) * cell[2]], -1)
    inside = blank_distance_np(P, settings) < 0
    owner = np.full((nx, ny, nz), -1, dtype=np.int64)
    high = np.zeros((nx, ny, nz))
    open_ = inside.copy()
    for s in path.segments:
        if s['type'] != 'cut':
            continue
        low_b, high_b = stroke_bounds(s, cs, 0.0)
        a = [max(0, math.ceil((low_b[k] - lo[k]) / cell[k] - .5)) for k in range(3)]
        b = [min(resolution[k] - 1, math.floor((high_b[k] - lo[k]) / cell[k] - .5)) for k in range(3)]
        if any(a[k] > b[k] for k in range(3)):
            continue
        sl = (slice(a[0], b[0] + 1), slice(a[1], b[1] + 1), slice(a[2], b[2] + 1))
        cand = open_[sl]
        if not cand.any():
            continue
        idx = np.nonzero(cand)
        pts = P[sl][idx]
        hit = sweep_distance_np(pts, s, radius, flute, 1.0, tool) <= 0
        if not hit.any():
            continue
        pts = pts[hit]
        lo_f, hi_f = np.zeros(len(pts)), np.ones(len(pts))
        for _ in range(14):
            f = (lo_f + hi_f) / 2
            inn = sweep_distance_np(pts, s, radius, flute, f, tool) <= 0
            hi_f = np.where(inn, f, hi_f)
            lo_f = np.where(inn, lo_f, f)
        gi = tuple(idx[k][hit] + a[k] for k in range(3))
        owner[gi] = s['index']
        high[gi] = hi_f
        open_[gi] = False
    sel = np.nonzero(owner >= 0)
    ids, fr = owner[sel], high[sel]
    pts = P[sel]
    # the JS walks voxels with three's z (the stock's width, -Y here) outermost, then height, then x: the first-seen
    # order of buckets settles ties in time, as Map insertion order did
    order = np.lexsort((sel[0], sel[2], -sel[1]))
    ids, fr, pts = ids[order], fr[order], pts[order]
    keys = ids * 8 + np.minimum(7, np.floor(fr * 8)).astype(np.int64)
    times = np.empty(len(ids))
    positions = np.empty((len(ids), 3))
    for sid in np.unique(ids):
        m = ids == sid
        s = path.segments[int(sid)]
        times[m] = _distance_time_np(s, s['length'] * fr[m])
        c, sn = math.cos(s['a0']), math.sin(s['a0'])
        q = pts[m]
        positions[m] = np.stack([q[:, 0] + axis_x, q[:, 1] * c - q[:, 2] * sn, q[:, 1] * sn + q[:, 2] * c + axis_h], 1)
    uk, first, inv, counts = np.unique(keys, return_index=True, return_inverse=True, return_counts=True)
    psum = np.zeros((len(uk), 3))
    np.add.at(psum, inv, positions)
    tsum = np.bincount(inv, weights=times, minlength=len(uk))
    events = []
    for k in np.argsort(first, kind='stable'):
        events.append(Rec(position=tuple(float(v) for v in psum[k] / counts[k]), time=float(tsum[k] / counts[k]),
                          volume=volume * int(counts[k]), floor=0.0))
    events.sort(key=lambda e: e['time'])
    total = 0.0
    for e in events:
        total += e['volume']
        e['total_volume'] = total
    queries = _queries(indexed, P, inside, owner, lo)
    return Rec(events=events, removed_volume=volume * int(len(ids)), resolution=tuple(resolution),
                  cell_size=tuple(float(v) for v in cell), queries=queries)


def _queries(indexed, P, inside, owner, lo):
    """The sweep tests the WebGPU loop made: per voxel inside the blank, its bin's strokes up to and including the
    first that reaches it (all of them when none does)."""
    dims, cell = indexed.dims, indexed.cell
    pts = P[inside]
    own = owner[inside]
    b = [np.minimum(dims[k] - 1, np.floor((pts[:, k] - lo[k]) / cell[k]).astype(np.int64)) for k in range(3)]
    flat = b[0] + dims[0] * (b[1] + dims[1] * b[2])
    total = 0
    for bi in np.unique(flat):
        ids = np.asarray(indexed.bins[int(bi)], dtype=np.int64)
        o = own[flat == bi]
        n_before = np.searchsorted(ids, np.where(o >= 0, o, np.iinfo(np.int64).max))
        total += int(np.where(o >= 0, n_before + 1, len(ids)).sum())
    return total
