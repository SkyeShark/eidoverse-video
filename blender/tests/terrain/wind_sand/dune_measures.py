"""Measurements of a dune field (numpy only): what tells the dune families apart, read off a heightfield in metres
(row 0 south, x east, y north) and, where it helps, its sand thickness. Used by the wind-and-sand tests and sheets.

    lee_faces(h, cell, from_deg)       slip faces against one wind: the share of steep cells facing downwind
    lee_peaks(h, cell)                 the judge's count of aspect-histogram peaks of the steep (slip-face) cells
    crest_orientation(h, cell)         the structure tensor of the gradient: the dominant gradient direction
                                       (crests run across it) and its coherence (0 isotropic .. 1 one direction)
    coverage(sand, cell)               the share of the ground under sand thicker than a threshold
    bodies(sand, ...)                  separate dunes: connected sand patches, their count and mean size
    summary(...)                       all of the above in one dict
"""
from __future__ import annotations

import math

import numpy as np


def slope_aspect(h, cell):
    gy, gx = np.gradient(np.asarray(h, np.float64), float(cell))
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    aspect = np.degrees(np.arctan2(-gx, -gy)) % 360.0           # the compass direction the slope faces (downhill)
    return slope, aspect, gx, gy


def angdiff(a, b):
    """Smallest signed difference a - b of compass angles, degrees in (-180, 180]."""
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def lee_faces(h, cell, from_deg, steep_deg=24.0):
    """Slip faces against one wind blowing FROM from_deg: of the cells steeper than steep_deg, the share facing
    within 45 degrees of downwind (the lee) and the share facing within 45 degrees of upwind (the stoss); and the
    circular mean aspect of the steep cells. A dune field shaped by that wind has nearly all its steep cells in the
    lee."""
    slope, aspect, _gx, _gy = slope_aspect(h, cell)
    steep = slope > steep_deg
    downwind = (float(from_deg) + 180.0) % 360.0
    a = aspect[steep]
    if a.size == 0:
        return dict(steep_frac=0.0, lee_share=0.0, stoss_share=0.0, mean_aspect_deg=float('nan'),
                    mean_offset_deg=float('nan'))
    d = angdiff(a, downwind)
    lee = float(np.mean(np.abs(d) <= 45.0))
    stoss = float(np.mean(np.abs(d) >= 135.0))
    m = math.degrees(math.atan2(np.mean(np.sin(np.radians(a))), np.mean(np.cos(np.radians(a))))) % 360.0
    return dict(steep_frac=float(steep.mean()), lee_share=lee, stoss_share=stoss, mean_aspect_deg=m,
                mean_offset_deg=float(angdiff(m, downwind)))


def lee_peaks(h, cell, min_slope=20.0):
    """The judge's family number (judge/family.py lee_peaks): peaks of the aspect histogram of cells steeper than
    min_slope, 36 bins circularly smoothed, a peak at least 25 % of the largest and higher than its neighbours over
    +-30 degrees. Also returns the peaks' directions."""
    slope, aspect, _gx, _gy = slope_aspect(h, cell)
    asp = aspect[slope > min_slope]
    if asp.size < 50:
        return 0, []
    hist = np.bincount((asp // 10).astype(int) % 36, minlength=36).astype(np.float64)
    hist = (np.roll(hist, 1) + 2 * hist + np.roll(hist, -1)) / 4
    peaks = []
    for k in range(36):
        win = [hist[(k + d) % 36] for d in (-3, -2, -1, 1, 2, 3)]
        if hist[k] >= 0.25 * hist.max() and hist[k] > max(win):
            peaks.append(10.0 * k + 5.0)
    return len(peaks), peaks


def crest_orientation(h, cell, min_slope=2.0):
    """The gradient structure tensor over cells steeper than min_slope: (gradient direction in compass degrees
    0..180, coherence 0..1). Crests run at right angles to the gradient direction."""
    slope, _aspect, gx, gy = slope_aspect(h, cell)
    m = slope > min_slope
    if m.sum() < 50:
        return float('nan'), 0.0
    jxx, jyy, jxy = float((gx[m] ** 2).sum()), float((gy[m] ** 2).sum()), float((gx[m] * gy[m]).sum())
    theta = 0.5 * math.atan2(2.0 * jxy, jxx - jyy)               # from +x (east), counter-clockwise
    coh = math.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2) / max(jxx + jyy, 1e-30)
    compass = (90.0 - math.degrees(theta)) % 180.0
    return compass, coh


def axis_offset(a, b):
    """The angle between two undirected axes (compass degrees), 0..90."""
    d = abs((float(a) - float(b)) % 180.0)
    return min(d, 180.0 - d)


def coverage(sand, thick_m):
    return float(np.mean(np.asarray(sand) > thick_m))


def bodies(sand, cell, thick_m, min_area_m2=0.0):
    """Separate dunes: 8-connected patches of sand thicker than thick_m (core metrics.label): (count, median area
    m2)."""
    from eidoblend.terrain.core import metrics as M
    lab, n = M.label(np.asarray(sand) > thick_m)
    if n == 0:
        return 0, 0.0
    area = np.bincount(lab.ravel())[1:] * cell * cell
    area = area[area >= min_area_m2]
    return int(area.size), float(np.median(area)) if area.size else 0.0


def horns_downwind(sand, cell, from_deg, thick_m, min_cells=20):
    """Crescents with their horns downwind: per separate dune body (8-connected sand thicker than thick_m, at least
    min_cells cells), the footprint's centroid minus the sand mass's centroid, projected on the downwind direction.
    The thin horns trail ahead of the thick body, so a barchan's footprint centroid lies downwind of its mass.
    Returns (share of bodies with it downwind, number of bodies)."""
    from eidoblend.terrain.core import metrics as M
    s = np.asarray(sand, np.float64)
    lab, n = M.label(s > thick_m)
    if n == 0:
        return 0.0, 0
    jj, ii = np.nonzero(lab)
    k = lab[jj, ii]
    w = s[jj, ii]
    area = np.bincount(k, minlength=n + 1).astype(np.float64)
    mass = np.bincount(k, weights=w, minlength=n + 1)
    ax = np.bincount(k, weights=ii, minlength=n + 1) / np.maximum(area, 1)
    ay = np.bincount(k, weights=jj, minlength=n + 1) / np.maximum(area, 1)
    mx = np.bincount(k, weights=ii * w, minlength=n + 1) / np.maximum(mass, 1e-12)
    my = np.bincount(k, weights=jj * w, minlength=n + 1) / np.maximum(mass, 1e-12)
    a = math.radians(float(from_deg))
    dx, dy = -math.sin(a), -math.cos(a)                     # where the sand goes (x east, y north = rows)
    proj = ((ax - mx) * dx + (ay - my) * dy) * cell
    keep = area >= min_cells
    keep[0] = False
    if not keep.any():
        return 0.0, 0
    return float(np.mean(proj[keep] > 0.0)), int(keep.sum())


def lee_peaks_of(aspects, weights=None):
    """lee_peaks's rule on a given set of aspects (degrees): the count and the directions."""
    asp = np.asarray(aspects, np.float64)
    if asp.size < 50:
        return 0, []
    hist = np.bincount((asp // 10).astype(int) % 36, weights=weights, minlength=36).astype(np.float64)
    hist = (np.roll(hist, 1) + 2 * hist + np.roll(hist, -1)) / 4
    peaks = []
    for k in range(36):
        win = [hist[(k + d) % 36] for d in (-3, -2, -1, 1, 2, 3)]
        if hist[k] >= 0.25 * hist.max() and hist[k] > max(win):
            peaks.append(10.0 * k + 5.0)
    return len(peaks), peaks


def summary(h, cell, sand=None, winds=None, thick_m=None):
    """Every measure in one dict (winds: [(from_deg, weight)] to read the lee against the strongest)."""
    slope, _a, _gx, _gy = slope_aspect(h, cell)
    out = dict(relief_m=float(np.ptp(h)), slope_p50=float(np.percentile(slope, 50)),
               slope_p90=float(np.percentile(slope, 90)), slope_p99=float(np.percentile(slope, 99)),
               slope_max=float(slope.max()), frac_gt34=float(np.mean(slope > 34.0)))
    n, pk = lee_peaks(h, cell)
    out.update(lee_peaks=n, lee_peak_dirs=pk)
    d, c = crest_orientation(h, cell)
    out.update(gradient_dir_deg=d, coherence=c)
    if winds:
        main = max(winds, key=lambda w: w[1])[0]
        out.update({f'lee_{k}': v for k, v in lee_faces(h, cell, main).items()})
    if sand is not None:
        t = thick_m if thick_m is not None else 0.25
        out['sand_cover'] = coverage(sand, t)
        out['bodies'], out['body_median_m2'] = bodies(sand, cell, t)
    return out
