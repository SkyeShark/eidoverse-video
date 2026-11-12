"""The karst package's numbers: how a generated tower field is held to the Guilin reference. numpy only.

The Guilin reference is Copernicus GLO-30 radar data (a 30 m surface model), bicubic-upsampled to 8 m and blurred
(Gaussian sigma 17.7 m): no wall in it is steeper than about 55 degrees, while Guilin's towers stand at 70-90
degrees (Waltham 2009: the best-known fenglin has vertical-sided towers). So the numbers come in two kinds:

  through the instrument   the generated field is degraded the way the reference was made (box-averaged to the
                           29.44 m source pixel, bicubic back to 8 m, Gaussian 17.7 m: `as_copernicus`) and then
                           measured exactly like the reference: slope percentiles, the fraction under 5 degrees,
                           the plain fraction, the summits' nearest-neighbour spacing and heights;
  at full resolution       what the radar can't see: the wall angles of the towers themselves.

Definitions (so the judge can adopt them):
  plain     a cell with slope < 5 degrees and height within 20 m of the lowest point within 500 m
  summit    a local maximum within 40 m standing 40 m above the lowest point within 250 m
  wall      the cells of a tower above 15 % and below 85 % of its height above the plain
"""
import math

import numpy as np

COPERNICUS_PIXEL_M = 29.439          # the reference's source mosaic pixel (data/guilin_karst.json)
COPERNICUS_SIGMA_M = 17.7            # its Gaussian, 0.60 source px


# ---------------------------------------------------------------- resampling
def box_resample(h, cell, target):
    """Area-weighted mean of a field of `cell`-metre pixels over `target`-metre pixels (both grids start at the
    same corner; any ratio): the integral image, read at fractional pixel edges, is exact for pixel-constant data."""
    h = np.asarray(h, np.float64)
    ny, nx = h.shape
    S = np.zeros((ny + 1, nx + 1))
    S[1:, 1:] = h.cumsum(0).cumsum(1)
    my, mx = int(ny * cell // target), int(nx * cell // target)
    ey = np.arange(my + 1) * target / cell
    ex = np.arange(mx + 1) * target / cell

    def at(e, n):
        i0 = np.clip(np.floor(e).astype(int), 0, n - 1)
        return i0, e - i0
    iy, fy = at(ey, ny)
    ix, fx = at(ex, nx)
    rows = S[iy] * (1 - fy)[:, None] + S[iy + 1] * fy[:, None]
    Se = rows[:, ix] * (1 - fx)[None, :] + rows[:, ix + 1] * fx[None, :]
    area = (target / cell) ** 2
    return (Se[1:, 1:] - Se[:-1, 1:] - Se[1:, :-1] + Se[:-1, :-1]) / area


def _keys(t):
    """Keys' cubic convolution kernel (a = -0.5), the bicubic of most resamplers."""
    t = np.abs(t)
    return np.where(t <= 1, 1.5 * t ** 3 - 2.5 * t ** 2 + 1,
                    np.where(t < 2, -0.5 * t ** 3 + 2.5 * t ** 2 - 4 * t + 2, 0.0))


def bicubic_resample(a, src, dst, n_out):
    """Bicubic from pixel-centred `src`-metre data to n_out pixel-centred `dst`-metre pixels from the same corner."""
    a = np.asarray(a, np.float64)

    def axis_weights(n_in):
        x = (np.arange(n_out) + 0.5) * dst / src - 0.5          # output centres in input pixel units
        i0 = np.floor(x).astype(int)
        W = np.zeros((n_out, n_in))
        for k in range(-1, 3):
            idx = np.clip(i0 + k, 0, n_in - 1)
            np.add.at(W, (np.arange(n_out), idx), _keys(x - (i0 + k)))
        return W
    Wy = axis_weights(a.shape[0])
    Wx = axis_weights(a.shape[1])
    return Wy @ a @ Wx.T


def gaussian_blur(a, sigma_px):
    """Separable Gaussian by FFT, edges reflected."""
    a = np.asarray(a, np.float64)
    pad = int(math.ceil(4 * sigma_px))
    p = np.pad(a, pad, mode='reflect')
    ky = np.fft.fftfreq(p.shape[0])
    kx = np.fft.rfftfreq(p.shape[1])
    G = np.exp(-2 * (math.pi * sigma_px) ** 2 * (ky[:, None] ** 2 + kx[None, :] ** 2))
    out = np.fft.irfft2(np.fft.rfft2(p) * G, s=p.shape)
    return out[pad:-pad, pad:-pad]


def as_copernicus(h, cell, out_cell=8.0, source_m=COPERNICUS_PIXEL_M, sigma_m=COPERNICUS_SIGMA_M):
    """What the Guilin reference's instrument makes of a field: box-averaged to the source pixel, bicubic to
    out_cell, Gaussian sigma_m. h: metres, `cell`-metre pixels."""
    coarse = box_resample(h, cell, source_m)
    n_out = int(round(h.shape[0] * cell / out_cell))
    up = bicubic_resample(coarse, source_m, out_cell, n_out)
    return gaussian_blur(up, sigma_m / out_cell)


# ---------------------------------------------------------------- the numbers
def slope_deg(h, pixel):
    gy, gx = np.gradient(np.asarray(h, np.float64), pixel)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def _rolling(a, r, fn):
    """Separable rolling min / max over a (2r+1)^2 window, edges clamped."""
    from numpy.lib.stride_tricks import sliding_window_view
    p = np.pad(a, r, mode='edge')
    t = fn(sliding_window_view(p, 2 * r + 1, axis=0), axis=-1)
    return fn(sliding_window_view(t, 2 * r + 1, axis=1), axis=-1)


def plain_mask(h, pixel, slope_max=5.0, above_m=20.0, radius_m=500.0):
    base = _rolling(np.asarray(h, np.float64), max(1, int(round(radius_m / pixel))), np.min)
    return (slope_deg(h, pixel) < slope_max) & (h - base < above_m)


def summits(h, pixel, peak_radius_m=40.0, relief_m=40.0, relief_radius_m=250.0):
    """(rows, cols, height above the lowest point within relief_radius_m) of the summits."""
    h = np.asarray(h, np.float64)
    mx = _rolling(h, max(1, int(round(peak_radius_m / pixel))), np.max)
    mn = _rolling(h, max(1, int(round(relief_radius_m / pixel))), np.min)
    m = (h >= mx) & (h - mn > relief_m)
    m[:2, :] = m[-2:, :] = m[:, :2] = m[:, -2:] = False
    r, c = np.nonzero(m)
    return r, c, (h - mn)[r, c]


def nn_spacing(r, c, pixel):
    """Each point's distance to its nearest neighbour, metres."""
    P = np.stack([c, r], 1).astype(np.float64) * pixel
    if len(P) < 2:
        return np.array([np.nan])
    out = np.empty(len(P))
    for s in range(0, len(P), 1024):
        d = ((P[s:s + 1024, None, :] - P[None, :, :]) ** 2).sum(-1)
        d[np.arange(d.shape[0]), np.arange(s, s + d.shape[0])] = np.inf
        out[s:s + 1024] = np.sqrt(d.min(1))
    return out


def numbers(h, pixel):
    """The shape numbers of a field (metres, `pixel`-metre cells), as the reference is measured."""
    h = np.asarray(h, np.float64)
    s = slope_deg(h, pixel)
    lo, hi = float(h.min()), float(h.max())
    r, c, rel = summits(h, pixel)
    nn = nn_spacing(r, c, pixel)
    return dict(relief_m=hi - lo, hypsometric_integral=(float(h.mean()) - lo) / max(hi - lo, 1e-6),
                slope_p10=float(np.percentile(s, 10)), slope_p50=float(np.percentile(s, 50)),
                slope_p90=float(np.percentile(s, 90)), slope_p99=float(np.percentile(s, 99)),
                frac_under_5=float((s < 5).mean()), frac_over_30=float((s > 30).mean()),
                frac_over_40=float((s > 40).mean()), frac_over_50=float((s > 50).mean()),
                plain_fraction=float(plain_mask(h, pixel).mean()),
                summits_per_km2=len(r) / (h.size * pixel * pixel / 1e6),
                summit_nn_p50_m=float(np.nanmedian(nn)), summit_nn_p25_m=float(np.nanpercentile(nn, 25)),
                summit_nn_p75_m=float(np.nanpercentile(nn, 75)),
                summit_rel_p50_m=float(np.median(rel)) if len(rel) else float('nan'),
                summit_rel_p90_m=float(np.percentile(rel, 90)) if len(rel) else float('nan'))


# the design's bands (section 10) and the karst family's own (spacing +-25 %, plain fraction +-30 %)
def bands(ref):
    """(name, low, high) the generated numbers must fall in, from the reference's numbers."""
    def pm(k, absol, rel):
        v = ref[k]
        d = max(absol, rel * abs(v))
        return (k, v - d, v + d)
    return [pm('slope_p50', 3.0, 0.25), pm('slope_p90', 4.0, 0.15), pm('slope_p99', 5.0, 0.10),
            pm('hypsometric_integral', 0.08, 0.0), pm('relief_m', 0.0, 0.20), pm('frac_under_5', 0.05, 0.40),
            pm('summit_nn_p50_m', 0.0, 0.25), pm('plain_fraction', 0.0, 0.30)]


def judge(gen, ref):
    """[(name, generated, low, high, passed)] for every band."""
    return [(k, gen[k], lo, hi, bool(lo <= gen[k] <= hi)) for k, lo, hi in bands(ref)]


def wall_angles(h, cell, plain, tower_id, lo=0.15, hi=0.85):
    """Slope (degrees) of the wall cells of every tower at full resolution: the cells whose height above the plain
    is between lo and hi of their tower's height above the plain."""
    h = np.asarray(h, np.float64)
    above = h - plain
    s = slope_deg(h, cell)
    ids = np.unique(tower_id[tower_id >= 0])
    if ids.size == 0:
        return np.array([])
    top = np.zeros(int(ids.max()) + 1)
    np.maximum.at(top, tower_id[tower_id >= 0], above[tower_id >= 0])
    t = np.where(tower_id >= 0, top[np.maximum(tower_id, 0)], 0.0)
    wall = (tower_id >= 0) & (above > lo * t) & (above < hi * t) & (t > 30.0)
    return s[wall]
