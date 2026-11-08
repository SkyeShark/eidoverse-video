"""Periodic gradient noise: Ekigar's src/nodes/noise.js (and its CPU twin in field_cpu.js), over numpy arrays.

Every function takes an explicit period in LATTICE CELLS; period <= 0 on an axis means "not periodic on that axis".
The lattice coordinate is wrapped with a floor-based modulo before hashing (never `%`, whose sign follows the
dividend), so a negative cell hashes to the right place.

hash2 is Ekigar's integer lattice hash, bit for bit: the multiplies wrap like u32 and every shift is logical, so it is
exact at any width (the reference demo's fract-product hash loses all precision at large lattice coordinates).
"""
from __future__ import annotations

import numpy as np

from ._tsl import Vec

HASH_BIAS = 8388608.0          # 2^23: keeps the input non-negative so the shifts are logical
K0 = 0.3183099
K1 = 0.3678794

_M1 = np.uint32(0x27d4eb2d)
_M2 = np.uint32(0x85ebca6b)
_M3 = np.uint32(0x2c1b3c6d)
_M4 = np.uint32(0x297a2d39)


def wrap_cell(v, period):
    """Floor-based lattice wrap; period <= 0 leaves v unchanged (noise.js wrapCell)."""
    period = np.asarray(period, dtype=np.float64)
    p = np.maximum(period, 1e-9)
    wrapped = v - p * np.floor(v / p)
    return np.where(period > 0, wrapped, v)


def _to_u32(x):
    """WGSL u32(f32) for the biased, non-negative lattice coordinate: truncation toward zero."""
    return (np.asarray(np.trunc(x), dtype=np.float64).astype(np.int64) & 0xFFFFFFFF).astype(np.uint32)


def hash2(cx, cy, px=0.0, py=0.0):
    """Integer lattice hash of cell (cx, cy) wrapped to periods (px, py). Returns (gx, gy) in [-1, 1)."""
    wx = _to_u32(wrap_cell(np.asarray(cx, dtype=np.float64), px) + HASH_BIAS)
    wy = _to_u32(wrap_cell(np.asarray(cy, dtype=np.float64), py) + HASH_BIAS)
    with np.errstate(over='ignore'):
        h = (wx * _M1) ^ (wy * _M2)
        h = h ^ (h >> np.uint32(15))
        h = h * _M3
        h = h ^ (h >> np.uint32(13))
        h = h * _M4
        h = h ^ (h >> np.uint32(16))
    lo = (h & np.uint32(0xFFFF)).astype(np.float64)
    hi = ((h >> np.uint32(16)) & np.uint32(0xFFFF)).astype(np.float64)
    return lo / 32767.5 - 1.0, hi / 32767.5 - 1.0


def hash2v(cell: Vec, period: Vec | tuple = (0.0, 0.0)) -> Vec:
    """hash2 on vectors, as the TSL Fn is called: hash2(cell, period) -> vec2."""
    px, py = (period.x, period.y) if isinstance(period, Vec) else period
    return Vec(*hash2(cell.x, cell.y, px, py))


def noised(px, py, perx=0.0, pery=0.0):
    """Gradient noise with exact analytic derivatives: (value, d/dx, d/dy) (noise.js noised)."""
    ix = np.floor(px)
    iy = np.floor(py)
    fx = px - ix
    fy = py - iy
    ux = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0)
    uy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0)
    dux = fx * fx * 30.0 * (fx * (fx - 2.0) + 1.0)
    duy = fy * fy * 30.0 * (fy * (fy - 2.0) + 1.0)

    gax, gay = hash2(ix, iy, perx, pery)
    gbx, gby = hash2(ix + 1.0, iy, perx, pery)
    gcx, gcy = hash2(ix, iy + 1.0, perx, pery)
    gdx, gdy = hash2(ix + 1.0, iy + 1.0, perx, pery)

    va = gax * fx + gay * fy
    vb = gbx * (fx - 1.0) + gby * fy
    vc = gcx * fx + gcy * (fy - 1.0)
    vd = gdx * (fx - 1.0) + gdy * (fy - 1.0)
    q = va - vb - vc + vd

    value = va + ux * (vb - va) + uy * (vc - va) + ux * uy * q
    dx = (gax + ux * (gbx - gax) + uy * (gcx - gax) + ux * uy * (gax - gbx - gcx + gdx)
          + dux * (uy * q + vb - va))
    dy = (gay + ux * (gby - gay) + uy * (gcy - gay) + ux * uy * (gay - gby - gcy + gdy)
          + duy * (ux * q + vc - va))
    return value, dx, dy


def noisedv(p: Vec, period=(0.0, 0.0)) -> Vec:
    """noised on a vec2 position, as the TSL Fn is called: returns vec3(value, d/dx, d/dy)."""
    px, py = (period.x, period.y) if isinstance(period, Vec) else period
    return Vec(*noised(p.x, p.y, px, py))


def fractal_noise(p: Vec, frequency, octaves, lacunarity, gain, tile) -> Vec:
    """fBm over noised (noise.js fractalNoise). `tile` is (tx, ty) in the units of p; each octave's lattice period
    is tile * its frequency, which is why tile * frequency must be whole and lacunarity integral to tile.

    Returns vec3(value, d/dx, d/dy) with the derivatives in the units of p."""
    tx, ty = _tile(tile)
    acc = None
    nf = float(frequency)
    na = 1.0
    for _ in range(int(octaves)):
        v, dx, dy = noised(p.x * nf, p.y * nf, tx * nf, ty * nf)
        term = (v * na, dx * (na * nf), dy * (na * nf))
        acc = term if acc is None else (acc[0] + term[0], acc[1] + term[1], acc[2] + term[2])
        na *= gain
        nf *= lacunarity
    if acc is None:
        return Vec(0.0, 0.0, 0.0)
    return Vec(*acc)


def _tile(tile):
    if isinstance(tile, dict):
        return float(tile.get('x', 0) or 0), float(tile.get('y', 0) or 0)
    if hasattr(tile, 'x'):
        return tile.x, tile.y
    return float(tile[0]), float(tile[1])
