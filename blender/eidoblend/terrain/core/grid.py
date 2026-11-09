"""Frames, units and grid operations of the terrain core (design section 2.1). Numpy only.

Frames
    Blender axes: Z up, metres, XY the ground plane.
    Arrays are [row j, column i] with row 0 the SOUTH edge. A cell centre is at
        x = x0 + (i + 0.5) * cell,   y = y0 + (j + 0.5) * cell.
    A window is square: (x0, y0, side, cell, n) with side = n * cell (core/levels.py).
    The reference loader (tests/terrain_new/reference/landform_refs.py) returns row 0 = NORTH: flip it once on load
    (from_north_up), and back for PNGs other tools read top-down (to_north_up).

Units, in every public parameter: metres (heights, sizes, spacings), years (durations), degrees (angles; their
tangent inside kernels: tan_deg / deg_of_tan), m/yr (uplift, deposition), m^2/yr (creep diffusivity). Erodibility K
is in the stream-power law's own units (m^(1-2m)/yr) and appears only inside recipes. Nothing is a fraction of the
tile.

Operations
    cell_centres(x0, y0, cell, n_or_shape)       world (x, y) of every cell centre, float64 meshgrids
    index_of(x, y, x0, y0, cell)                  fractional (i, j): cell centres are whole numbers
    upsample2(a, 'catmull' | 'bilinear')          x2, cell-centred: child centres at parent i -/+ 0.25 (edge clamp)
    crop_upsample2(a, i0, j0, m, kind)            a child window (m parent cells from parent cell (i0, j0)), x2
    box_down(a, f)                                integer box average
    resample_box(a, src_cell, dst_cell)           exact area-weighted average to any coarser pixel (the judge's)
    sample_bilinear(a, x0, y0, cell, x, y)        world-space lookup, clamped at the edges
    border_ramp(n, band, kind)                    pin weight: 1 at the edge -> 0 at `band` cells in (C1 by default)
    gradient(h, cell) / slope_deg / aspect_deg    central differences (np.gradient), the reference JSONs' slope
"""

from __future__ import annotations

import numpy as np

DEG = np.pi / 180.0
# Catmull-Rom weights at t = 0.25 and t = 0.75 (p0, p1, p2, p3): the cell-centred x2 child sits at parent i + 0.25
# (between p_i and p_i+1, t = 0.25) and at i - 0.25 (between p_i-1 and p_i, t = 0.75)
_CR25 = np.array([-0.0703125, 0.8671875, 0.2265625, -0.0234375])
_CR75 = _CR25[::-1].copy()


# --------------------------------------------------------------------------------------------- frames, units ---

def tan_deg(deg):
    """An angle in degrees as the tangent kernels use."""
    return np.tan(np.asarray(deg, dtype=np.float64) * DEG)


def deg_of_tan(t):
    return np.degrees(np.arctan(np.asarray(t, dtype=np.float64)))


def cell_centres(x0, y0, cell, n):
    """World (x, y) of every cell centre of a window: float64 (H, W) meshgrids. `n` is the cell count of a square
    window or an (H, W) shape."""
    h, w = (int(n), int(n)) if np.ndim(n) == 0 else (int(n[0]), int(n[1]))
    xs = x0 + (np.arange(w, dtype=np.float64) + 0.5) * cell
    ys = y0 + (np.arange(h, dtype=np.float64) + 0.5) * cell
    return np.meshgrid(xs, ys)


def index_of(x, y, x0, y0, cell):
    """Fractional array indices (i, j) of world points: cell centres are whole numbers."""
    return (np.asarray(x, np.float64) - x0) / cell - 0.5, (np.asarray(y, np.float64) - y0) / cell - 0.5


def from_north_up(a):
    """A top-down array (row 0 = north, the reference loader's and PNGs') in this package's frame (row 0 = south)."""
    return np.ascontiguousarray(np.asarray(a)[::-1])


to_north_up = from_north_up


# ------------------------------------------------------------------------------------------------ resampling ---

def _up1(a, axis, kind):
    """x2 along one axis, cell-centred, edges clamped."""
    a = np.moveaxis(np.asarray(a, dtype=np.float64), axis, 0)
    n = a.shape[0]
    if kind == 'catmull':
        p = np.concatenate([a[:1], a[:1], a, a[-1:], a[-1:]], 0)              # p[k + 2] = a[k], clamped
        lo = (_CR75[0] * p[0:n] + _CR75[1] * p[1:n + 1] + _CR75[2] * p[2:n + 2] + _CR75[3] * p[3:n + 3])
        hi = (_CR25[0] * p[1:n + 1] + _CR25[1] * p[2:n + 2] + _CR25[2] * p[3:n + 3] + _CR25[3] * p[4:n + 4])
    elif kind == 'bilinear':
        p = np.concatenate([a[:1], a, a[-1:]], 0)                              # p[k + 1] = a[k]
        lo = 0.25 * p[0:n] + 0.75 * p[1:n + 1]
        hi = 0.75 * p[1:n + 1] + 0.25 * p[2:n + 2]
    elif kind == 'nearest':
        lo = hi = a
    else:
        raise ValueError(f"upsample kind {kind!r} is 'catmull', 'bilinear' or 'nearest'")
    out = np.empty((2 * n,) + a.shape[1:], np.float64)
    out[0::2] = lo
    out[1::2] = hi
    return np.moveaxis(out, 0, axis)


def upsample2(a, kind='catmull'):
    """x2 cell-centred upsampling of a 2D array (child cells nest 2 x 2 in each parent cell): 'catmull' (Catmull-Rom,
    for h and bed), 'bilinear' (masks, A, qs) or 'nearest'. Returns float32."""
    return _up1(_up1(a, 0, kind), 1, kind).astype(np.float32)


def crop_upsample2(a, i0, j0, m, kind='catmull', mj=None):
    """The x2 child of a window m parent cells wide (mj tall, default m) starting at parent cell (i0, j0): (2 mj, 2 m)
    float32. Reads 2 parent cells around the window (clamped at the parent's edge), so the result equals
    upsample2(a) cropped there."""
    mj = m if mj is None else mj
    a = np.asarray(a)
    rows = np.clip(np.arange(j0 - 2, j0 + mj + 2), 0, a.shape[0] - 1)
    cols = np.clip(np.arange(i0 - 2, i0 + m + 2), 0, a.shape[1] - 1)
    up = upsample2(a[np.ix_(rows, cols)], kind)
    return np.ascontiguousarray(up[4:4 + 2 * mj, 4:4 + 2 * m])


def box_down(a, f):
    """Integer box average by f on both axes (the shape must divide)."""
    a = np.asarray(a, dtype=np.float64)
    h, w = a.shape
    if h % f or w % f:
        raise ValueError(f'box_down: shape {a.shape} does not divide by {f}')
    return a.reshape(h // f, f, w // f, f).mean(axis=(1, 3))


def _box_axis(a, r, n_out, axis):
    """Area-weighted average along one axis: output pixel k covers source cells [k r, (k + 1) r)."""
    a = np.moveaxis(np.asarray(a, dtype=np.float64), axis, 0)
    n = a.shape[0]
    cum = np.concatenate([np.zeros((1,) + a.shape[1:]), np.cumsum(a, axis=0)], 0)   # F at whole cells
    edges = np.minimum(np.arange(n_out + 1) * r, n)
    k = np.minimum(np.floor(edges).astype(np.int64), n - 1)
    frac = (edges - k)[(slice(None),) + (None,) * (a.ndim - 1)]
    F = cum[k] + frac * a[k]                                       # exact for piecewise-constant cells
    out = (F[1:] - F[:-1]) / r
    return np.moveaxis(out, 0, axis)


def resample_box(a, src_cell, dst_cell, n_out=None):
    """The exact area-weighted (box) average of a grid of `src_cell` pixels onto `dst_cell` pixels over the same
    extent from the same origin (the judge's "box-average to the reference's pixel"). n_out defaults to the whole
    pixels that fit: floor(n * src_cell / dst_cell) per axis. dst_cell must be at least src_cell."""
    a = np.asarray(a, dtype=np.float64)
    r = float(dst_cell) / float(src_cell)
    if r < 1.0 - 1e-9:
        raise ValueError(f'resample_box averages down; dst_cell {dst_cell} m is finer than src_cell {src_cell} m')
    h, w = a.shape
    if n_out is None:
        n_out = (int(np.floor(h / r + 1e-6)), int(np.floor(w / r + 1e-6)))
    elif np.ndim(n_out) == 0:
        n_out = (int(n_out), int(n_out))
    if abs(r - round(r)) < 1e-9 and h % int(round(r)) == 0 and w % int(round(r)) == 0 \
            and n_out == (h // int(round(r)), w // int(round(r))):
        return box_down(a, int(round(r)))
    return _box_axis(_box_axis(a, r, n_out[0], 0), r, n_out[1], 1)


def sample_bilinear(a, x0, y0, cell, x, y):
    """Bilinear value of a cell-centred grid at world (x, y), clamped to the outermost cell centres."""
    a = np.asarray(a)
    h, w = a.shape[:2]
    fi, fj = index_of(x, y, x0, y0, cell)
    fi = np.clip(fi, 0.0, w - 1.0)
    fj = np.clip(fj, 0.0, h - 1.0)
    i0 = np.minimum(np.floor(fi).astype(np.int64), max(w - 2, 0))
    j0 = np.minimum(np.floor(fj).astype(np.int64), max(h - 2, 0))
    ti, tj = fi - i0, fj - j0
    i1, j1 = np.minimum(i0 + 1, w - 1), np.minimum(j0 + 1, h - 1)
    return ((a[j0, i0] * (1 - ti) + a[j0, i1] * ti) * (1 - tj) + (a[j1, i0] * (1 - ti) + a[j1, i1] * ti) * tj)


def edge_distance(n):
    """Chebyshev distance of every cell of an (n, n) window (or an (H, W) shape) from its nearest edge, in cells
    (0 on the edge row)."""
    h, w = (int(n), int(n)) if np.ndim(n) == 0 else (int(n[0]), int(n[1]))
    jj, ii = np.mgrid[0:h, 0:w]
    return np.minimum(np.minimum(ii, w - 1 - ii), np.minimum(jj, h - 1 - jj))


def border_ramp(n, band=16, kind='smooth'):
    """The border band's pin weight (design section 2.2): 1 on the edge, falling to 0 at `band` cells in. 'smooth'
    is 1 - smoothstep(0, band, d), C1 so the blend leaves no crease line; 'linear' is 1 - d / band. float32."""
    d = edge_distance(n).astype(np.float64)
    t = np.clip(d / float(band), 0.0, 1.0)
    w = 1.0 - (t * t * (3.0 - 2.0 * t) if kind == 'smooth' else t)
    return w.astype(np.float32)


# --------------------------------------------------------------------------------------------- derivatives ---

def gradient(h, cell):
    """(dh/dx east, dh/dy north) by central differences (one-sided on the edges), as np.gradient: rows run north."""
    gy, gx = np.gradient(np.asarray(h, dtype=np.float64), float(cell))
    return gx, gy


def slope_deg(h, cell):
    """Slope in degrees by central differences, never clipped: the reference JSONs' definition (shape_stats)."""
    gx, gy = gradient(h, cell)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def aspect_deg(h, cell):
    """The compass direction the slope faces (downhill), degrees clockwise from north, 0..360."""
    gx, gy = gradient(h, cell)
    return np.degrees(np.arctan2(-gx, -gy)) % 360.0
