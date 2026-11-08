"""Ekigar's display-grid policy (src/nodes/terrain_mesh.js) over numpy: how many vertices a side a terrain mesh gets
for a field resolution, what that costs, the grid itself, and the bilinear field read its vertices take.

    side = terrain_vertex_side(4096)                 # 2048: Ekigar's cap; 1:1 with the field from 256 to 2048
    terrain_geometry_cost(side)                      # verts, triangles, index width, bytes
    g = build_terrain_geometry(4096)                 # positions (xy in [-0.5, 0.5], z = 0), uv on texel centres, index
    z = field_height_bilinear(hf.height, u, v)       # the field at any uv, bilinear, wrapping like the field target

The two rules terrain_mesh.js measured, both kept: vertices sit on the DISPLAY grid's texel centres (uv = (i + 0.5)/N,
never i/(N-1)), so at 1:1 every vertex reads its own texel exactly; and when the grid is coarser than the field the
height is a bilinear read, which at a whole ratio is an exact two-tap box average (attenuating what the grid cannot
show) where a nearest read would alias it. build_mesh(hf, side=...) in mesh.py builds this grid in Blender.
"""
from __future__ import annotations

import numpy as np

VERT_CAP = 2048        # vertices a side beyond which a uniform grid stops paying for itself (Ekigar's policy)
VERT_FLOOR = 256       # below this the grid is coarse enough to see, whatever the field resolution


def terrain_vertex_side(field_res, cap=VERT_CAP):
    """Vertices per side for a field resolution: 1:1 between VERT_FLOOR and `cap`."""
    try:
        res = max(1, int(np.floor(float(field_res or 1))))
    except (TypeError, ValueError):
        res = 1
    return max(VERT_FLOOR, min(cap, res))


def terrain_geometry_cost(n):
    """Byte cost of build_terrain_geometry(side=n) without building it: verts, triangles, indices, index bytes, and
    the position / uv / index / total bytes (three.js float32 attributes; u16 indices while they fit)."""
    verts = n * n
    quads = (n - 1) * (n - 1)
    indices = quads * 6
    index_bytes = 4 if verts > 65536 else 2
    position = verts * 3 * 4
    uv = verts * 2 * 4
    index = indices * index_bytes
    return {'verts': verts, 'triangles': quads * 2, 'indices': indices, 'indexBytes': index_bytes,
            'position': position, 'uv': uv, 'index': index, 'bytes': position + uv + index}


def build_terrain_geometry(field_res, cap=VERT_CAP, side=None, with_normal=False):
    """The display grid as arrays: {'position' (N*N, 3) float32 with xy = uv - 0.5 and z = 0, 'uv' (N*N, 2),
    'index' (6 per quad, wound to face +z: (a, b, c), (b, d, c)), 'normal' (when asked), 'terrain': {side, fieldRes,
    and the terrain_geometry_cost fields} (what three's geometry carries as userData.terrain)}."""
    n = max(2, int(np.floor(side if side is not None else terrain_vertex_side(field_res, cap))))
    t = (np.arange(n, dtype=np.float64) + 0.5) / n
    U, V = np.meshgrid(t, t)
    uv = np.stack([U.ravel(), V.ravel()], axis=1).astype(np.float32)
    pos = np.zeros((n * n, 3), dtype=np.float32)
    pos[:, 0] = (U.ravel() - 0.5).astype(np.float32)
    pos[:, 1] = (V.ravel() - 0.5).astype(np.float32)
    j, i = np.mgrid[0:n - 1, 0:n - 1]
    a = (j * n + i).ravel()
    b, c = a + 1, a + n
    d = c + 1
    index = np.stack([a, b, c, b, d, c], axis=1).ravel().astype(np.uint32 if n * n > 65536 else np.uint16)
    out = {'position': pos, 'uv': uv, 'index': index,
           'terrain': dict({'side': n, 'fieldRes': field_res}, **terrain_geometry_cost(n))}   # three's userData.terrain
    if with_normal:
        nrm = np.zeros_like(pos)
        nrm[:, 2] = 1.0
        out['normal'] = nrm
    return out


def field_height_bilinear(height, u, v):
    """A field grid (ny, nx) read at uv (arrays), bilinear on texel centres, out-of-range texels WRAPPING (the field
    target's RepeatWrapping), as terrain_mesh.js fieldHeightBilinear reads it in the vertex shader."""
    h = np.asarray(height, dtype=np.float64)
    ny, nx = h.shape
    cx = np.asarray(u, dtype=np.float64) * nx - 0.5
    cy = np.asarray(v, dtype=np.float64) * ny - 0.5
    i0 = np.floor(cx)
    j0 = np.floor(cy)
    fx, fy = cx - i0, cy - j0
    i0 = i0.astype(np.int64)
    j0 = j0.astype(np.int64)

    def at(i, j):
        return h[np.mod(j, ny), np.mod(i, nx)]
    return ((at(i0, j0) * (1 - fx) + at(i0 + 1, j0) * fx) * (1 - fy)
            + (at(i0, j0 + 1) * (1 - fx) + at(i0 + 1, j0 + 1) * fx) * fy)


def display_heights(height, side):
    """The heights a side x side display grid's vertices take from a field grid (bilinear, wrapping)."""
    t = (np.arange(side, dtype=np.float64) + 0.5) / side
    U, V = np.meshgrid(t, t)
    return field_height_bilinear(height, U, V)


__all__ = ['VERT_CAP', 'VERT_FLOOR', 'terrain_vertex_side', 'terrain_geometry_cost', 'build_terrain_geometry',
           'field_height_bilinear', 'display_heights']
