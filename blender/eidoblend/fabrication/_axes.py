"""Small helpers private to the fabrication family: axes, colours, plain records.

Axes. The WebGPU engine is three.js, Y-up; Blender is Z-up; both in metres.
    three (x, y, z) -> Blender (x, -z, y)       t2b(v)
    Blender (x, y, z) -> three (x, z, -y)       b2t(v)
The change is a proper rotation (+90 degrees about X): lengths, volumes, cross products and turning senses survive it.
Every public input and output of the family is in Blender's axes. A few planners (the slicer's hatch rows, the
filament payout, the feed routing) run in three's axes inside, so they read like their sources, and convert at their
edges.
"""

from __future__ import annotations

import math

import numpy as np


def t2b(v):
    """three.js (x, y, z) -> Blender (x, -z, y), for one point / direction (a tuple back)."""
    return (float(v[0]), -float(v[2]), float(v[1]))


def b2t(v):
    """Blender (x, y, z) -> three.js (x, z, -y)."""
    return (float(v[0]), float(v[2]), -float(v[1]))


def t2b_np(a):
    a = np.asarray(a, dtype=np.float64)
    return np.stack([a[..., 0], -a[..., 2], a[..., 1]], axis=-1)


def b2t_np(a):
    a = np.asarray(a, dtype=np.float64)
    return np.stack([a[..., 0], a[..., 2], -a[..., 1]], axis=-1)


# C maps three coordinates to Blender's (v_b = C v_t); a Blender matrix M_b acts in three's axes as C^-1 M_b C
C3 = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
C4 = np.eye(4)
C4[:3, :3] = C3


def matrix_b2t(m) -> np.ndarray:
    """A Blender 4x4 (mathutils.Matrix or rows) as the same transform in three's axes (numpy 4x4)."""
    m = np.array([list(r) for r in m], dtype=np.float64)
    return C4.T @ m @ C4


def matrix_t2b(m) -> np.ndarray:
    m = np.asarray(m, dtype=np.float64)
    return C4 @ m @ C4.T


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def color_linear(c):
    """An engine colour ('#rrggbb', 0xrrggbb or an (r, g, b) sRGB triple in 0..1) as linear RGB, the way three's
    ColorManagement turns new THREE.Color('#bec7cd') into its working colour."""
    if isinstance(c, str):
        h = c.lstrip('#')
        if len(h) == 3:
            h = ''.join(ch * 2 for ch in h)
        rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    elif isinstance(c, (int, np.integer)):
        rgb = [((int(c) >> 16) & 255) / 255.0, ((int(c) >> 8) & 255) / 255.0, (int(c) & 255) / 255.0]
    else:
        rgb = [float(x) for x in list(c)[:3]]
    return tuple(float(x) for x in srgb_to_linear(rgb))


def finite(*vals) -> bool:
    return all(isinstance(v, (int, float, np.floating, np.integer)) and math.isfinite(v) for v in vals)


def positive(v, name):
    if not (isinstance(v, (int, float, np.floating, np.integer)) and math.isfinite(v) and v > 0):
        raise ValueError(name + ' must be positive')
    return v


class Rec(dict):
    """A dict that also reads as attributes (state.time, segment.t0), like the JS objects it replaces."""

    __slots__ = ()

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None

    def __setattr__(self, k, v):
        self[k] = v
