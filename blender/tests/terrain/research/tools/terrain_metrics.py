"""Shape statistics and a hillshade for a heightfield in metres, to compare generated terrain with real terrain.

    import terrain_metrics as TM
    m = TM.metrics(h, dx)          # h: 2-D float array in metres, dx: metres per pixel
    img = TM.hillshade(h, dx)      # uint8 greyscale, sun from the north-west, 40 degrees up

metrics() returns:
    relief_m                  99.5th minus 0.5th percentile height
    hypsometric_integral      (mean - min) / (max - min)
    slope_p10/p50/p90/p99     slope percentiles in degrees (central differences)
    frac_slope_lt5 / gt30 / gt40 / gt50   area fractions
    depression_area_frac      fraction of the area inside closed depressions deeper than max(1 m, 0.2 % of relief)
                              (priority-flood fill by morphological reconstruction): fluvial terrain is ~0, noise is not
    depressions_per_100km2    count of those depressions
Needs numpy; the depression statistics also need scikit-image + scipy (system Python, not Blender's).
"""
import numpy as np


def slope_deg(h, dx):
    gy, gx = np.gradient(h, dx)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def hillshade(h, dx, azimuth=315.0, altitude=40.0, exaggeration=1.0):
    gy, gx = np.gradient(h * exaggeration, dx)
    # image rows run north to south: +row is south, so the north component of the gradient is -gy
    az, alt = np.radians(azimuth), np.radians(altitude)
    lx, ly, lz = np.sin(az) * np.cos(alt), np.cos(az) * np.cos(alt), np.sin(alt)   # x east, y north, z up
    nx, ny, nz = -gx, gy, np.ones_like(h)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    shade = (nx * lx + ny * ly + nz * lz) / n
    return (np.clip(shade, 0.0, 1.0) * 255.0).astype(np.uint8)


def depressions(h, relief):
    from skimage.morphology import reconstruction
    from scipy import ndimage
    seed = h.copy()
    seed[1:-1, 1:-1] = h.max()
    filled = reconstruction(seed, h, method='erosion')       # every cell can drain to the edge
    depth = filled - h
    thr = max(1.0, 0.002 * relief)
    lab, n = ndimage.label(depth > 1e-6, structure=np.ones((3, 3)))
    if n == 0:
        return 0.0, 0
    maxd = ndimage.maximum(depth, lab, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = maxd > thr
    mask = keep[lab]
    return float(mask.mean()), int(keep.sum())


def metrics(h, dx, with_depressions=True):
    h = np.asarray(h, dtype=np.float64)
    lo, hi = np.percentile(h, [0.5, 99.5])
    s = slope_deg(h, dx)
    out = {
        'pixel_m': float(dx),
        'extent_km': float(h.shape[1] * dx / 1000.0),
        'relief_m': float(hi - lo),
        'hypsometric_integral': float((h.mean() - h.min()) / max(h.max() - h.min(), 1e-9)),
    }
    for p in (10, 50, 90, 99):
        out[f'slope_p{p}'] = float(np.percentile(s, p))
    for t, name in ((5, 'lt5'), (30, 'gt30'), (40, 'gt40'), (50, 'gt50')):
        out[f'frac_slope_{name}'] = float((s < t).mean() if name.startswith('lt') else (s > t).mean())
    if with_depressions:
        frac, n = depressions(h, hi - lo)
        area_km2 = h.size * dx * dx / 1e6
        out['depression_area_frac'] = frac
        out['depressions_per_100km2'] = float(n / area_km2 * 100.0)
    return out
