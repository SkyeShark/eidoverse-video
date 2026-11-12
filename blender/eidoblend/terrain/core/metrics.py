"""The judge's generic numbers for a heightfield in metres (design section 10, item 2). Numpy only (no scipy or
scikit-image), so it runs in Blender's Python as well as system Python.

    from eidoblend.terrain.core import metrics as M
    h8 = M.to_pixel(h, cell, 8.0)            # box-average to the reference's pixel first: slope depends on pixel size
    m = M.metrics(h8, 8.0)                   # the dict below
    M.slope_stats(h, cell)                   # the reference JSONs' shape_stats keys (slope_deg_p10 ...), to check
                                             # a field against <reference>.json's numbers

metrics() keys (degrees, metres, fractions of the area):
    pixel_m, extent_m
    relief_m                max - min (the reference JSONs' relief); relief_robust_m: p99.5 - p0.5
    mean_m, hypsometric_integral (mean - min) / (max - min)
    slope_p10, slope_p50, slope_p90, slope_p99, slope_mean     central differences (np.gradient), never clipped
    frac_slope_lt5, frac_slope_gt30, frac_slope_gt40, frac_slope_gt50
    depression_area_frac, depression_count, depressions_per_100km2, depression_threshold_m
                            closed depressions deeper than max(1 m, 0.2 % of relief), the edge draining
                            (fill by hydro.fill_depressions; 8-connected regions of filled - h > 0 whose deepest
                            point passes the threshold)
    spectrum_slope          log-log slope of the radially averaged power spectrum over wavelengths from 4 pixels
                            to a quarter of the extent
    spectrum_knee_m         the wavelength where a two-segment (broken power law) fit breaks: the characteristic
                            valley scale; spectrum_slope_long / _short, the two segments' slopes
    spectrum_peak_m         the wavelength of the largest bump above the power-law fit (dune spacing, say)
    anisotropy_4, anisotropy_8, anisotropy
                            the 4-fold and 8-fold Fourier amplitude of the aspect histogram, weighted by the
                            gradient (tan slope) of the cells steeper than 10 degrees: grid-direction bias;
                            anisotropy is the larger. anisotropy_2 is the 2-fold term: a landform aligned along one
                            direction (linear dunes 0.49 A4, a straight coast) scores high A4 with a high A2, grid
                            combing scores A4 / A8 without it
    cliff_pair_frac         the fraction of 8-neighbour pairs steeper than 80 degrees (texel-wide cliffs)
"""

from __future__ import annotations

import math

import numpy as np

from . import grid


# -------------------------------------------------------------------------------------------- pixel matching ---

def to_pixel(h, cell, pixel_m, n_out=None):
    """h box-averaged to `pixel_m` pixels (exact area weights; core/grid.resample_box)."""
    return grid.resample_box(h, cell, pixel_m, n_out)


# ----------------------------------------------------------------------------------------------- slopes ---

def slope_stats(h, cell):
    """The reference JSONs' shape_stats over a field, same definitions and rounding-free:
    relief_m, mean_m, hypsometric_integral, slope_deg_p10/p50/p90/p99, slope_deg_mean."""
    h = np.asarray(h, dtype=np.float64)
    s = grid.slope_deg(h, cell)
    lo, hi, mean = float(h.min()), float(h.max()), float(h.mean())
    p = np.percentile(s, [10, 50, 90, 99])
    return {'relief_m': hi - lo, 'mean_m': mean, 'hypsometric_integral': (mean - lo) / max(hi - lo, 1e-6),
            'slope_deg_p10': float(p[0]), 'slope_deg_p50': float(p[1]), 'slope_deg_p90': float(p[2]),
            'slope_deg_p99': float(p[3]), 'slope_deg_mean': float(s.mean())}


# ------------------------------------------------------------------------------------ closed depressions ---

def _fill_function():
    """hydro.fill_depressions (solvers/hydro.py: exact, on the graph of D8 basins; numpy only)."""
    from ..solvers import hydro                                      # noqa: WPS433 - owned elsewhere
    return hydro.fill_depressions


_FILL = []


def fill_depressions(h, wrap=(False, False), sea_level=None):
    """(filled, info): every cell's spill level (priority-flood result) with the open edge as the outlet."""
    if not _FILL:
        _FILL.append(_fill_function())
    return _FILL[0](np.asarray(h, dtype=np.float64), wrap, sea_level)


PAIR_DIRS = ((0, 1), (1, 0), (1, 1), (1, -1))           # (row step, column step): every 8-neighbour pair once


def pair_slices(dj, di, shape):
    """(slice of a, slice of b) so that a[sa] and b[sb] are the cells [j, i] and [j + dj, i + di] of every pair."""
    h, w = shape
    sa = (slice(max(0, -dj), h - max(0, dj)), slice(max(0, -di), w - max(0, di)))
    sb = (slice(max(0, dj), h - max(0, -dj)), slice(max(0, di), w - max(0, -di)))
    return sa, sb


def label(mask):
    """8-connected components of a boolean mask: (labels int64 (0 = background, 1..n), n). Vectorised union-find
    (hook to the smaller root, then pointer jumping) over the mask's neighbour pairs."""
    mask = np.asarray(mask, dtype=bool)
    idx = np.arange(mask.size).reshape(mask.shape)
    pairs = []
    for dj, di in PAIR_DIRS:
        sa, sb = pair_slices(dj, di, mask.shape)
        ok = mask[sa] & mask[sb]
        pairs.append((idx[sa][ok], idx[sb][ok]))
    ea = np.concatenate([p[0] for p in pairs]) if pairs else np.zeros(0, np.int64)
    eb = np.concatenate([p[1] for p in pairs]) if pairs else np.zeros(0, np.int64)
    parent = np.arange(mask.size)
    while ea.size:
        ra, rb = parent[ea], parent[eb]
        diff = ra != rb
        if not diff.any():
            break
        lo, hi = np.minimum(ra[diff], rb[diff]), np.maximum(ra[diff], rb[diff])
        np.minimum.at(parent, hi, lo)
        while True:
            pp = parent[parent]
            if np.array_equal(pp, parent):
                break
            parent = pp
        keep = parent[ea] != parent[eb]
        ea, eb = ea[keep], eb[keep]
    roots = parent.reshape(mask.shape)
    lab = np.zeros(mask.shape, np.int64)
    if mask.any():
        u, inv = np.unique(roots[mask], return_inverse=True)
        lab[mask] = inv + 1
        return lab, int(u.size)
    return lab, 0


def depressions(h, cell, relief=None, wrap=(False, False)):
    """Closed depressions deeper than max(1 m, 0.2 % of relief): (area fraction, count, threshold m, depth
    array (filled - h))."""
    h = np.asarray(h, dtype=np.float64)
    relief = float(h.max() - h.min()) if relief is None else float(relief)
    thr = max(1.0, 0.002 * relief)
    filled, _info = fill_depressions(h, wrap)
    depth = filled - h
    lab, n = label(depth > 1e-6)
    if n == 0:
        return 0.0, 0, thr, depth
    maxd = np.zeros(n + 1)
    np.maximum.at(maxd, lab.ravel(), depth.ravel())
    keep = maxd > thr
    keep[0] = False
    return float(keep[lab].mean()), int(keep.sum()), thr, depth


# -------------------------------------------------------------------------------------------- the spectrum ---

def radial_spectrum(h, cell, nbins=48):
    """The radially averaged power spectrum: (wavelength_m, power) per log-spaced band of wavenumber, from the
    extent down to two pixels. The field is detrended (least-squares plane) and Hann-windowed first."""
    z = np.asarray(h, dtype=np.float64)
    ny, nx = z.shape
    jj, ii = np.mgrid[0:ny, 0:nx]
    A = np.stack([ii.ravel(), jj.ravel(), np.ones(z.size)], axis=1)
    coef, *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)
    z = z - (A @ coef).reshape(z.shape)
    w = np.outer(np.hanning(ny), np.hanning(nx))
    F = np.fft.rfft2(z * w)
    P = (np.abs(F) ** 2) * (cell * cell) / max((w * w).sum(), 1e-12)
    ky = np.fft.fftfreq(ny, d=cell)
    kx = np.fft.rfftfreq(nx, d=cell)
    k = np.hypot(ky[:, None], kx[None, :])
    kmin, kmax = 1.0 / (max(nx, ny) * cell), 0.5 / cell
    edges = np.logspace(math.log10(kmin), math.log10(kmax), nbins + 1)
    b = np.digitize(k.ravel(), edges) - 1
    ok = (b >= 0) & (b < nbins)
    cnt = np.bincount(b[ok], minlength=nbins)
    tot = np.bincount(b[ok], weights=P.ravel()[ok], minlength=nbins)
    kc = np.sqrt(edges[1:] * edges[:-1])
    have = cnt > 0
    return 1.0 / kc[have], tot[have] / cnt[have]


def spectrum_summary(wl, P, cell, extent):
    """(slope, knee_m, slope_long, slope_short, peak_m) of a radial spectrum over wavelengths from 4 pixels to a
    quarter of the extent."""
    band = (wl >= 4.0 * cell) & (wl <= extent / 4.0) & (P > 0)
    if band.sum() < 6:
        return float('nan'), float('nan'), float('nan'), float('nan'), float('nan')
    x, y = np.log10(1.0 / wl[band]), np.log10(P[band])
    slope, icept = np.polyfit(x, y, 1)
    best = (np.inf, None)
    for i in range(3, x.size - 3):                                 # a broken power law, continuous at the knee
        xk = x[i]
        X = np.stack([np.ones_like(x), np.minimum(x - xk, 0.0), np.maximum(x - xk, 0.0)], axis=1)
        c, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = float(((X @ c - y) ** 2).sum())
        if r < best[0]:
            best = (r, (xk, c[1], c[2]))
    xk, s_long, s_short = best[1]
    resid = y - (slope * x + icept)
    inner = slice(1, resid.size - 1)
    peak = float(1.0 / 10 ** x[inner][int(np.argmax(resid[inner]))])
    return float(slope), float(1.0 / 10 ** xk), float(s_long), float(s_short), peak


# --------------------------------------------------------------------------------------------- anisotropy ---

def aspect_harmonics(h, cell, min_slope_deg=10.0, orders=(2, 4, 8)):
    """{m: |sum w e^(i m theta)| / sum w}: the m-fold Fourier amplitudes of the aspect histogram, theta the gradient
    direction and w its magnitude (tan slope), over the cells steeper than min_slope_deg."""
    gx, gy = grid.gradient(h, cell)
    g = np.hypot(gx, gy)
    sel = g > math.tan(math.radians(min_slope_deg))
    if not sel.any():
        return {m: 0.0 for m in orders}
    th = np.arctan2(gy[sel], gx[sel])
    w = g[sel]
    tot = w.sum()
    return {m: float(abs(np.sum(w * np.exp(1j * m * th))) / tot) for m in orders}


def aspect_anisotropy(h, cell, min_slope_deg=10.0):
    """(A4, A8): the grid-direction anisotropy of the design (4-fold and 8-fold aspect harmonics). A landform
    aligned along one direction (linear dunes, a straight coast) has them too, with a strong 2-fold term (A2,
    aspect_harmonics): grid combing is 4- or 8-fold without the 2-fold."""
    a = aspect_harmonics(h, cell, min_slope_deg, (4, 8))
    return a[4], a[8]


def cliff_pairs(h, cell, deg=80.0):
    """The fraction of 8-neighbour pairs steeper than `deg` degrees."""
    h = np.asarray(h, dtype=np.float64)
    t = math.tan(math.radians(deg))
    n_steep, n_all = 0, 0
    for dj, di in PAIR_DIRS:
        sa, sb = pair_slices(dj, di, h.shape)
        s = np.abs(h[sa] - h[sb]) / (math.hypot(dj, di) * cell)
        n_steep += int((s > t).sum())
        n_all += s.size
    return n_steep / max(n_all, 1)


# --------------------------------------------------------------------------------------------- everything ---

def metrics(h, cell, with_depressions=True, with_spectrum=True):
    """The generic numbers of a heightfield in metres at `cell` metres per pixel (see the module doc)."""
    h = np.asarray(h, dtype=np.float64)
    ny, nx = h.shape
    s = grid.slope_deg(h, cell)
    lo, hi, mean = float(h.min()), float(h.max()), float(h.mean())
    p05, p995 = np.percentile(h, [0.5, 99.5])
    p = np.percentile(s, [10, 50, 90, 99])
    out = {'pixel_m': float(cell), 'extent_m': [float(nx * cell), float(ny * cell)],
           'relief_m': hi - lo, 'relief_robust_m': float(p995 - p05), 'mean_m': mean,
           'hypsometric_integral': (mean - lo) / max(hi - lo, 1e-9),
           'slope_p10': float(p[0]), 'slope_p50': float(p[1]), 'slope_p90': float(p[2]), 'slope_p99': float(p[3]),
           'slope_mean': float(s.mean()),
           'frac_slope_lt5': float((s < 5).mean()), 'frac_slope_gt30': float((s > 30).mean()),
           'frac_slope_gt40': float((s > 40).mean()), 'frac_slope_gt50': float((s > 50).mean())}
    if with_depressions:
        frac, count, thr, _d = depressions(h, cell, hi - lo)
        area_km2 = h.size * cell * cell / 1e6
        out.update(depression_area_frac=frac, depression_count=count,
                   depressions_per_100km2=count / max(area_km2, 1e-12) * 100.0, depression_threshold_m=thr)
    if with_spectrum:
        wl, P = radial_spectrum(h, cell)
        sl, knee, s_long, s_short, peak = spectrum_summary(wl, P, cell, min(nx, ny) * cell)
        out.update(spectrum_slope=sl, spectrum_knee_m=knee, spectrum_slope_long=s_long, spectrum_slope_short=s_short,
                   spectrum_peak_m=peak)
    a = aspect_harmonics(h, cell)
    out.update(anisotropy_2=a[2], anisotropy_4=a[4], anisotropy_8=a[8], anisotropy=max(a[4], a[8]),
               cliff_pair_frac=cliff_pairs(h, cell))
    return out
