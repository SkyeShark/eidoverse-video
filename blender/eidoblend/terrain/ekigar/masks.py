"""Terrain masks from a baked height grid (Ekigar's src/nodes/masks.js and its backend-generic twin
src/export/terrain_masks.js), over numpy.

Everything comes from FINITE DIFFERENCES of the height, never from the field's carried gradient (which is ~29 degrees
out and 0.42x in magnitude under erosion). Curvature is real: profile curvature runs along the slope (negative =
concave = deposition), plan curvature across it (negative = convergent = drainage lines).

    m = build_masks(height, aux=ridge, texel=1/N, world_size=400, vertical_scale=0.3, wrap=(True, True))
    m['slope'], m['curvProfile'], m['concave'], m['geoNormal'] (3, N, N) ...

Every constant is Ekigar's, including the ones that look arbitrary (the 1e-6 flat guard, the 1e-5 aspect guard, the
curvature display gain K = 6, and (g2 + 1)^1.5 in profile curvature but bare denomFlat^1.5 in plan curvature), so a
band keyed to a mask lands where it lands in Ekigar.

The arrays are [row = v, column = u]; `wrap` says whether each axis is periodic (the field target samples with
repeat wrapping on a tiled axis) or clamps at the edge.
"""
from __future__ import annotations

import numpy as np

MASK_NAMES = ['height', 'slope', 'aspect', 'aspectEast', 'curvProfile', 'curvPlan', 'curvMean', 'ridge']
ALL_MASKS = MASK_NAMES + ['concave', 'convex', 'converge', 'constant']


def _shift(a, di, dj, wrap):
    """a sampled at (row + dj, col + di), wrapping or clamping per axis (wrap = (u, v))."""
    out = a
    if di:
        if wrap[0]:
            out = np.roll(out, -di, axis=1)
        else:
            idx = np.clip(np.arange(a.shape[1]) + di, 0, a.shape[1] - 1)
            out = out[:, idx]
    if dj:
        if wrap[1]:
            out = np.roll(out, -dj, axis=0)
        else:
            idx = np.clip(np.arange(a.shape[0]) + dj, 0, a.shape[0] - 1)
            out = out[idx, :]
    return out


def build_masks(height, aux=None, texel=None, world_size=400.0, vertical_scale=0.3, wrap=(True, True)):
    """The mask set of masks.js over a height grid. `texel` is the stencil step in uv units (1/N, one texel);
    `aux` is the field's ridge channel (the 'ridge' mask is 0.5 where it is absent)."""
    h = np.asarray(height, dtype=np.float64)
    e = (1.0 / h.shape[1]) if texel is None else float(texel)
    k = max(1, int(round(e * h.shape[1])))           # the stencil in whole texels
    hL, hR = _shift(h, -k, 0, wrap), _shift(h, k, 0, wrap)
    hD, hU = _shift(h, 0, -k, wrap), _shift(h, 0, k, wrap)
    hLD, hRD = _shift(h, -k, -k, wrap), _shift(h, k, -k, wrap)
    hLU, hRU = _shift(h, -k, k, wrap), _shift(h, k, k, wrap)
    return masks_from_stencil(h, hL, hR, hD, hU, hLD, hRD, hLU, hRU, e, world_size, vertical_scale, aux)


def masks_from_stencil(h, hL, hR, hD, hU, hLD, hRD, hLU, hRU, e, world_size=400.0, vertical_scale=0.3, aux=None):
    """terrain_masks.js buildMasks over the nine reads of its 3x3 stencil (centre, left/right, down/up and the four
    diagonals, `e` uv units apart), whatever sampled them: build_masks shifts a grid, local_area reads a crop."""
    dw = e * 2.0 * world_size
    vs = vertical_scale * world_size
    p = (hR - hL) / dw * vs
    q = (hU - hD) / dw * vs
    step = e * world_size
    r = (hR + hL - h * 2.0) / (step * step) * vs
    t = (hU + hD - h * 2.0) / (step * step) * vs
    s = (hRU - hLU - hRD + hLD) / (step * step * 4.0) * vs
    p2, q2 = p * p, q * q
    g2 = p2 + q2
    g = np.sqrt(g2)
    denom_flat = np.maximum(g2, 1e-6)
    profile = -((p2 * r + p * q * s * 2.0 + q2 * t) / (denom_flat * np.power(g2 + 1.0, 1.5)))
    plan = -((q2 * r - p * q * s * 2.0 + p2 * t) / np.power(denom_flat, 1.5))
    mean = -((r + t) * 0.5)
    K = 6.0

    def norm(c):
        return np.clip(c * K * 0.5 + 0.5, 0.0, 1.0)

    g_guard = np.maximum(g, 1e-5)
    flatish = g > 1e-5
    nlen = np.sqrt(p * p + q * q + 1.0)
    return {
        'raw': {'h': h, 'p': p, 'q': q, 'r': r, 's': s, 't': t},
        'geoNormal': np.stack([-p / nlen, -q / nlen, 1.0 / nlen]),
        'height': np.clip(h, 0.0, 1.0),
        'slope': np.clip(g, 0.0, 1.0),
        'aspect': np.where(flatish, np.clip(q / g_guard * 0.5 + 0.5, 0.0, 1.0), 0.5),
        'aspectEast': np.where(flatish, np.clip(p / g_guard * 0.5 + 0.5, 0.0, 1.0), 0.5),
        'curvProfile': norm(profile),
        'curvPlan': norm(plan),
        'curvMean': norm(mean),
        'concave': np.clip(-(profile * K), 0.0, 1.0),
        'convex': np.clip(profile * K, 0.0, 1.0),
        'converge': np.clip(-(plan * K), 0.0, 1.0),
        'ridge': (np.full_like(h, 0.5) if aux is None else np.clip(np.asarray(aux) * 0.5 + 0.5, 0.0, 1.0)),
        'constant': np.ones_like(h),
    }


def world_position(u, v, height, world_x, world_y=None, world_size=None, vertical_scale=0.3):
    """Ekigar's shading frame in three.js axes: X = (u - 0.5) * worldX, Y = h * verticalScale * worldSize (up),
    Z = -(v - 0.5) * worldY. (In Blender the same point is (x, y, z) = ((u - 0.5) W, (v - 0.5) W, h * vs * W).)"""
    world_y = world_x if world_y is None else world_y
    ws = world_x if world_size is None else world_size
    return np.stack([(np.asarray(u) - 0.5) * world_x, np.asarray(height) * vertical_scale * ws,
                     -(np.asarray(v) - 0.5) * world_y])


def world_normal(p, q):
    """The surface normal in that three.js frame from the heightfield derivatives: normalize(-p, 1, +q)."""
    n = np.stack([-np.asarray(p), np.ones_like(np.asarray(p, dtype=np.float64)), np.asarray(q)])
    return n / np.linalg.norm(n, axis=0, keepdims=True)


def blender_normal(p, q):
    """The same normal in Blender's Z-up axes: normalize(-p, -q, 1)."""
    n = np.stack([-np.asarray(p), -np.asarray(q), np.ones_like(np.asarray(p, dtype=np.float64))])
    return n / np.linalg.norm(n, axis=0, keepdims=True)
