"""Screen-space derivatives (TSL dFdx / dFdy) over an evaluation grid.

On the GPU a derivative is a difference inside a 2x2 pixel quad. Here the grid is the array itself (rows = v, the
second texture axis; columns = u), and the compiler picks how a derivative is taken:

    'coarse'   (default) the GPU quad derivative, constant across each 2x2 quad: what Ekigar's own render takes and
               what every parity test runs, so a project evaluates to the field Ekigar draws. Row bands start on
               even rows, so the quads never straddle a band and the result does not depend on the banding.
    'central'  (a[x+1] - a[x-1]) / 2 per texel: the slope measured at each pixel instead of held constant across a
               quad. Smoother masks, but NOT Ekigar's field: slopeMask / angleMask change, and the ten wave-3
               landforms carry a different gradient, which an erosion downstream turns into different heights.
               The compiler pads every band by the graph's derivative nesting depth (measured, see
               compile.derivative_depth), so the result is exact at band and grid edges and the same whatever the
               banding.
    'fine'     per-row / per-column quad differences.
    'forbid'   raise NeedsGrid: a point evaluation (api.point_field) has no neighbouring pixels.

The sign convention is +u / +v per texel (dFdy follows v upward, Blender's +y), which is what Ekigar's operators
intend when they scale a derivative by the resolution to get a slope.
"""
from __future__ import annotations

import numpy as np

MODES = ('coarse', 'central', 'fine', 'forbid')
_MODE = ['coarse']
_SCALE = [1.0, 1.0]
_POISON = [None]


def set_mode(mode: str) -> str:
    """Set the derivative mode; returns the previous one."""
    if mode not in MODES:
        raise ValueError(f'derivative mode {mode!r}: coarse, central, fine or forbid')
    old = _MODE[0]
    _MODE[0] = mode
    return old


def get_mode() -> str:
    return _MODE[0]


def set_scale(sx: float, sy: float):
    """Grid texels per field-resolution texel on each axis. Ekigar's operators turn a screen derivative into a slope
    by multiplying it by the field resolution; when a terrain is evaluated on a finer grid than the resolution its
    texel radii are measured in (compile.evaluate_graph's field_resolution), each per-texel difference is rescaled by
    this so the product stays the true slope. 1 when the two are the same, as in Ekigar. Returns the previous pair."""
    old = tuple(_SCALE)
    _SCALE[0], _SCALE[1] = float(sx), float(sy)
    return old


def set_poison(poison):
    """For compile.derivative_depth only: every 'central' derivative overwrites its one-sided edge cells (the outer
    columns of a dFdx, the outer rows of a dFdy), so any dependence of a window's core on those cells shows. `poison`
    is a numpy Generator (huge values of random sign: they flip comparisons and branches both ways), 'nan' (NaN:
    it survives the clamps and smoothsteps that would swallow a huge value), or None (off). Returns the previous."""
    old = _POISON[0]
    _POISON[0] = poison
    return old


def _quad_index(n):
    q = np.arange(n) & ~1
    return q, np.minimum(q + 1, n - 1)


class NeedsGrid(RuntimeError):
    """A screen-space derivative was asked for where there is no grid (a point evaluation)."""


def _forbidden():
    if _MODE[0] == 'forbid':
        raise NeedsGrid('this graph takes screen-space derivatives (a slope or angle mask, or a wave-3 landform that '
                        'differentiates its relief), which need a grid: evaluate it with generate() instead')


def dfdx(a):
    _forbidden()
    d = _dfdx(a)
    return d if _SCALE[0] == 1.0 else d * _SCALE[0]


def dfdy(a):
    _forbidden()
    d = _dfdy(a)
    return d if _SCALE[1] == 1.0 else d * _SCALE[1]


def _garbage(poison, shape):
    if isinstance(poison, str):
        return np.full(shape, np.nan)
    return np.where(poison.random(shape) < 0.5, -1.0, 1.0) * 1e6 * (1.0 + poison.random(shape))


def _dfdx(a):
    a = np.asarray(a, dtype=np.float64)
    if a.ndim < 2 or a.shape[-1] < 2:
        return np.zeros_like(a) if a.ndim else 0.0
    mode = _MODE[0]
    h, w = a.shape[-2], a.shape[-1]
    if mode == 'central':
        out = np.empty_like(a)
        out[..., 1:-1] = (a[..., 2:] - a[..., :-2]) * 0.5
        out[..., 0] = a[..., 1] - a[..., 0]
        out[..., -1] = a[..., -1] - a[..., -2]
        rng = _POISON[0]
        if rng is not None:
            out[..., 0] = _garbage(rng, out[..., 0].shape)
            out[..., -1] = _garbage(rng, out[..., -1].shape)
        return out
    qx, qx1 = _quad_index(w)
    if mode == 'fine':
        return a[..., qx1] - a[..., qx]
    qy, _ = _quad_index(h)
    rows = a[..., qy, :]
    return rows[..., qx1] - rows[..., qx]


def _dfdy(a):
    a = np.asarray(a, dtype=np.float64)
    if a.ndim < 2 or a.shape[-2] < 2:
        return np.zeros_like(a) if a.ndim else 0.0
    mode = _MODE[0]
    h, w = a.shape[-2], a.shape[-1]
    if mode == 'central':
        out = np.empty_like(a)
        out[..., 1:-1, :] = (a[..., 2:, :] - a[..., :-2, :]) * 0.5
        out[..., 0, :] = a[..., 1, :] - a[..., 0, :]
        out[..., -1, :] = a[..., -1, :] - a[..., -2, :]
        rng = _POISON[0]
        if rng is not None:
            out[..., 0, :] = _garbage(rng, out[..., 0, :].shape)
            out[..., -1, :] = _garbage(rng, out[..., -1, :].shape)
        return out
    qy, qy1 = _quad_index(h)
    if mode == 'fine':
        return a[..., qy1, :] - a[..., qy, :]
    qx, _ = _quad_index(w)
    cols = a[..., :, qx]
    return cols[..., qy1, :] - cols[..., qy, :]
