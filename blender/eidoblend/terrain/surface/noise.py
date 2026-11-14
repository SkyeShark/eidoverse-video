"""The numpy twin of surface/noise.glsl: Blender's shader noise (the Noise Texture's normalised fBM, 3D and 4D, and
the Voronoi texture's F1 cell colour, 2D and 3D), with Blender's own hashes (Jenkins' lookup3) and Perlin noise
(Cycles' svm/noise.h, Apache-2.0). Float32 arithmetic, uint32 hashes bit for bit with the GLSL.

    from eidoblend.terrain.surface import noise as BN
    BN.noise_node3(co, scale, detail, roughness)           # the Noise Texture node's Fac, 3D (co (..., 3))
    BN.noise_node4(co, w, scale, detail, roughness)        # 4D
    BN.voronoi_f1_colour2(co_xy, scale, randomness)        # the Voronoi node's F1 Color, 2D ((..., 3))
    BN.voronoi_f1_colour3(co, scale, randomness)
    BN.source()                                            # the GLSL text
"""
from __future__ import annotations

import os

import numpy as np

F = np.float32
U = np.uint32
HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = {}


def source():
    """noise.glsl's text."""
    if 'src' not in _SRC:
        with open(os.path.join(HERE, 'noise.glsl'), encoding='utf-8') as f:
            _SRC['src'] = f.read()
    return _SRC['src']


def _u(v):
    a = np.asarray(v)
    if a.dtype == np.uint32:
        return a
    return (a.astype(np.int64) & 0xFFFFFFFF).astype(U)


def _rot(x, k):
    k = U(k)
    return (x << k) | (x >> (U(32) - k))


def _mix(a, b, c):
    a = a - c; a = a ^ _rot(c, 4); c = c + b      # noqa: E702
    b = b - a; b = b ^ _rot(a, 6); a = a + c      # noqa: E702
    c = c - b; c = c ^ _rot(b, 8); b = b + a      # noqa: E702
    a = a - c; a = a ^ _rot(c, 16); c = c + b     # noqa: E702
    b = b - a; b = b ^ _rot(a, 19); a = a + c     # noqa: E702
    c = c - b; c = c ^ _rot(b, 4); b = b + a      # noqa: E702
    return a, b, c


def _final(a, b, c):
    c = c ^ b; c = c - _rot(b, 14)                # noqa: E702
    a = a ^ c; a = a - _rot(c, 11)                # noqa: E702
    b = b ^ a; b = b - _rot(a, 25)                # noqa: E702
    c = c ^ b; c = c - _rot(b, 16)                # noqa: E702
    a = a ^ c; a = a - _rot(c, 4)                 # noqa: E702
    b = b ^ a; b = b - _rot(a, 14)                # noqa: E702
    c = c ^ b; c = c - _rot(b, 24)                # noqa: E702
    return a, b, c


def hash2(kx, ky):
    with np.errstate(over='ignore'):
        kx, ky = np.broadcast_arrays(_u(kx), _u(ky))
        a = np.full(kx.shape, U(0xdeadbeef + (2 << 2) + 13), U)
        b, c = a.copy(), a.copy()
        b = b + ky
        a = a + kx
        a, b, c = _final(a, b, c)
        return c


def hash3(kx, ky, kz):
    with np.errstate(over='ignore'):
        kx, ky, kz = np.broadcast_arrays(_u(kx), _u(ky), _u(kz))
        a = np.full(kx.shape, U(0xdeadbeef + (3 << 2) + 13), U)
        b, c = a.copy(), a.copy()
        c = c + kz
        b = b + ky
        a = a + kx
        a, b, c = _final(a, b, c)
        return c


def hash4(kx, ky, kz, kw):
    with np.errstate(over='ignore'):
        kx, ky, kz, kw = np.broadcast_arrays(_u(kx), _u(ky), _u(kz), _u(kw))
        a = np.full(kx.shape, U(0xdeadbeef + (4 << 2) + 13), U)
        b, c = a.copy(), a.copy()
        a = a + kx
        b = b + ky
        c = c + kz
        a, b, c = _mix(a, b, c)
        a = a + kw
        a, b, c = _final(a, b, c)
        return c


def _u2f(h):
    return (np.asarray(h, U).astype(F) / F(4294967295.0)).astype(F)


def _bits(x):
    return np.ascontiguousarray(np.asarray(x, F)).view(U)


def hash_f2(kx, ky):
    return _u2f(hash2(_bits(kx), _bits(ky)))


def hash_f3(kx, ky, kz):
    return _u2f(hash3(_bits(kx), _bits(ky), _bits(kz)))


def hash_f4(kx, ky, kz, kw):
    return _u2f(hash4(_bits(kx), _bits(ky), _bits(kz), _bits(kw)))


def _fade(t):
    return (t * t * t * (t * (t * F(6) - F(15)) + F(10))).astype(F)


def _neg(v, c):
    return np.where(c != 0, -v, v)


def _grad3(h, x, y, z):
    h = h & U(15)
    u = np.where(h < 8, x, y)
    vt = np.where((h == 12) | (h == 14), x, z)
    v = np.where(h < 4, y, vt)
    return (_neg(u, h & U(1)) + _neg(v, h & U(2))).astype(F)


def _grad4(h, x, y, z, w):
    h = h & U(31)
    u = np.where(h < 24, x, y)
    v = np.where(h < 16, y, z)
    s = np.where(h < 8, z, w)
    return (_neg(u, h & U(1)) + _neg(v, h & U(2)) + _neg(s, h & U(4))).astype(F)


def _tri_mix(v, x, y, z):
    x1, y1, z1 = F(1) - x, F(1) - y, F(1) - z
    return (z1 * (y1 * (v[0] * x1 + v[1] * x) + y * (v[2] * x1 + v[3] * x))
            + z * (y1 * (v[4] * x1 + v[5] * x) + y * (v[6] * x1 + v[7] * x))).astype(F)


def perlin3(x, y, z):
    x, y, z = (np.asarray(a, F) for a in (x, y, z))
    fx0, fy0, fz0 = np.floor(x), np.floor(y), np.floor(z)
    X, Y, Z = (_u(np.asarray(a, np.float64).astype(np.int64)) for a in (fx0, fy0, fz0))
    fx, fy, fz = (x - fx0).astype(F), (y - fy0).astype(F), (z - fz0).astype(F)
    u, v, w = _fade(fx), _fade(fy), _fade(fz)
    with np.errstate(over='ignore'):
        one = U(1)
        g = [_grad3(hash3(X + dx, Y + dy, Z + dz), fx - F(dx), fy - F(dy), fz - F(dz))
             for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
    _ = one
    return _tri_mix(g, u, v, w)


def perlin4(x, y, z, w):
    x, y, z, w = (np.asarray(a, F) for a in (x, y, z, w))
    fl = [np.floor(a) for a in (x, y, z, w)]
    X, Y, Z, W = (_u(np.asarray(a, np.float64).astype(np.int64)) for a in fl)
    fx, fy, fz, fw = ((a - f).astype(F) for a, f in zip((x, y, z, w), fl))
    u, v, t, s = _fade(fx), _fade(fy), _fade(fz), _fade(fw)
    with np.errstate(over='ignore'):
        ga = [_grad4(hash4(X + dx, Y + dy, Z + dz, W), fx - F(dx), fy - F(dy), fz - F(dz), fw)
              for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
        gb = [_grad4(hash4(X + dx, Y + dy, Z + dz, W + U(1)), fx - F(dx), fy - F(dy), fz - F(dz), fw - F(1))
              for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
    a = _tri_mix(ga, u, v, t)
    b = _tri_mix(gb, u, v, t)
    return (a + (b - a) * s).astype(F)


def _fmod(a, b):
    return (a - F(b) * np.trunc(a / F(b))).astype(F)


def snoise3(x, y, z):
    pc = [F(0.5) * (np.abs(np.asarray(a, F)) >= F(1000000.0)).astype(F) for a in (x, y, z)]
    q = [_fmod(np.asarray(a, F), 100000.0) + c for a, c in zip((x, y, z), pc)]
    return (F(0.9820) * perlin3(*q)).astype(F)


def snoise4(x, y, z, w):
    pc = [F(0.5) * (np.abs(np.asarray(a, F)) >= F(1000000.0)).astype(F) for a in (x, y, z, w)]
    q = [_fmod(np.asarray(a, F), 100000.0) + c for a, c in zip((x, y, z, w), pc)]
    return (F(0.8344) * perlin4(*q)).astype(F)


def _fbm(sn, p, detail, roughness):
    detail = float(min(max(detail, 0.0), 15.0))
    rough = F(max(roughness, 0.0))
    fscale, amp, maxamp = F(1), F(1), F(0)
    total = np.zeros(np.shape(p[0]), F)
    for _i in range(int(detail) + 1):
        t = sn(*[fscale * a for a in p])
        total = (total + t * amp).astype(F)
        maxamp = F(maxamp + amp)
        amp = F(amp * rough)
        fscale = F(fscale * F(2))
    rmd = F(detail - np.floor(detail))
    if rmd != 0:
        t = sn(*[fscale * a for a in p])
        sum2 = (total + t * amp).astype(F)
        a = F(0.5) * total / maxamp + F(0.5)
        b = F(0.5) * sum2 / (maxamp + amp) + F(0.5)
        return (a + (b - a) * rmd).astype(F)
    return (F(0.5) * total / maxamp + F(0.5)).astype(F)


def noise_node3(co, scale, detail=2.0, roughness=0.5):
    """The Noise Texture node's Fac (3D, fBM, normalised, lacunarity 2, no distortion) at co (..., 3)."""
    co = np.asarray(co, F)
    s = F(scale)
    p = [co[..., 0] * s, co[..., 1] * s, co[..., 2] * s]
    return _fbm(snoise3, p, detail, roughness)


def noise_node4(co, w, scale, detail=2.0, roughness=0.5):
    """The Noise Texture node's Fac, 4D: (co, w) x scale."""
    co = np.asarray(co, F)
    s = F(scale)
    p = [co[..., 0] * s, co[..., 1] * s, co[..., 2] * s, np.broadcast_to(F(w) * s, co.shape[:-1]).astype(F)]
    return _fbm(snoise4, p, detail, roughness)


def _i(a):
    """Integer cell indices as the GLSL's ivec, as uint32 bits (the low 32 bits)."""
    return _u(np.asarray(a, np.float64).astype(np.int64))


def _sra16(v):
    """v >> 16 on int32 bits (sign-extending, as GLSL's on an int), as uint32 bits."""
    return (np.ascontiguousarray(v, U).view(np.int32) >> 16).view(U)


def pcg2d_i(x, y):
    """Blender's hash_pcg2d_i (the paper's pcg2d without its last xor-shift, in signed integers) on int32 bits held
    as uint32 arrays: two hashes in 0..2^31-1, as uint32 (checked against Blender's Voronoi render)."""
    x, y = (np.array(np.broadcast_to(_u(v), np.broadcast(x, y).shape), U) for v in (x, y))
    with np.errstate(over='ignore'):
        x = x * U(1664525) + U(1013904223)
        y = y * U(1664525) + U(1013904223)
        x = x + y * U(1664525)
        y = y + x * U(1664525)
        x, y = x ^ _sra16(x), y ^ _sra16(y)
        x = x + y * U(1664525)
        y = y + x * U(1664525)
    m = U(0x7FFFFFFF)
    return x & m, y & m


def pcg3d_i(x, y, z):
    """Blender's hash_pcg3d_i (the PCG hash of "Hash Functions for GPU Rendering", JCGT 2020, in signed integers)
    on int32 bits held as uint32 arrays: three hashes in 0..2^31-1, as uint32."""
    x, y, z = (np.array(np.broadcast_to(_u(v), np.broadcast(x, y, z).shape), U) for v in (x, y, z))
    with np.errstate(over='ignore'):
        x = x * U(1664525) + U(1013904223)
        y = y * U(1664525) + U(1013904223)
        z = z * U(1664525) + U(1013904223)
        x = x + y * z
        y = y + z * x
        z = z + x * y
        x, y, z = x ^ _sra16(x), y ^ _sra16(y), z ^ _sra16(z)
        x = x + y * z
        y = y + z * x
        z = z + x * y
    m = U(0x7FFFFFFF)
    return x & m, y & m, z & m


def _pcg_f(h):
    """float(h) * (1 / float(0x7FFFFFFF)) in float32, as the shaders do."""
    return np.asarray(h).astype(np.int64).astype(F) * F(1.0 / 2147483648.0)


def voronoi_f1_colour2(co, scale, randomness=1.0):
    """The Voronoi node's F1 Color (2D, Euclidean, detail 0) at co (..., 2): (..., 3). Blender 4.1+ hashes the
    integer cell index k with PCG: the point hash_int2_to_float2(k) = pcg2d_i(k) / (2^31 - 1), the colour
    hash_int2_to_float3(k) = pcg3d_i(k, 0) / (2^31 - 1)."""
    co = np.asarray(co, F) * F(scale)
    cx, cy = np.floor(co[..., 0]), np.floor(co[..., 1])
    lx, ly = (co[..., 0] - cx).astype(F), (co[..., 1] - cy).astype(F)
    ix, iy = _i(cx), _i(cy)
    r = F(min(max(randomness, 0.0), 1.0))
    best = np.full(cx.shape, np.inf, F)
    tx, ty = np.zeros(cx.shape, np.int64), np.zeros(cx.shape, np.int64)
    with np.errstate(over='ignore'):
        for j in (-1, 0, 1):
            for i in (-1, 0, 1):
                kx, ky = ix + U(i & 0xFFFFFFFF), iy + U(j & 0xFFFFFFFF)
                hx, hy = pcg2d_i(kx, ky)
                px = F(i) + _pcg_f(hx) * r
                py = F(j) + _pcg_f(hy) * r
                d = np.sqrt((px - lx) ** 2 + (py - ly) ** 2).astype(F)
                take = d < best
                best = np.where(take, d, best)
                tx, ty = np.where(take, i, tx), np.where(take, j, ty)
        kx, ky = ix + _u(tx), iy + _u(ty)
    return np.stack([_pcg_f(h) for h in pcg3d_i(kx, ky, U(0))], -1)


def voronoi_f1_colour3(co, scale, randomness=1.0):
    """The Voronoi node's F1 Color (3D, Euclidean, detail 0) at co (..., 3): (..., 3), from the integer cell index
    (hash_int3_to_float3(k) = pcg3d_i(k) / (2^31 - 1), for the points and the colour)."""
    co = np.asarray(co, F) * F(scale)
    c = [np.floor(co[..., k]) for k in range(3)]
    loc = [(co[..., k] - c[k]).astype(F) for k in range(3)]
    ic = [_i(a) for a in c]
    r = F(min(max(randomness, 0.0), 1.0))
    best = np.full(c[0].shape, np.inf, F)
    t = [np.zeros(c[0].shape, np.int64) for _ in range(3)]
    with np.errstate(over='ignore'):
        for k in (-1, 0, 1):
            for j in (-1, 0, 1):
                for i in (-1, 0, 1):
                    off = (i, j, k)
                    kk = [ic[q] + U(off[q] & 0xFFFFFFFF) for q in range(3)]
                    h = [_pcg_f(v) for v in pcg3d_i(*kk)]
                    pt = [F(off[q]) + h[q] * r for q in range(3)]
                    d = np.sqrt(sum((pt[q] - loc[q]) ** 2 for q in range(3))).astype(F)
                    take = d < best
                    best = np.where(take, d, best)
                    t = [np.where(take, off[q], t[q]) for q in range(3)]
        kk = [ic[q] + _u(t[q]) for q in range(3)]
    return np.stack([_pcg_f(v) for v in pcg3d_i(*kk)], -1)


__all__ = ['noise_node3', 'noise_node4', 'voronoi_f1_colour2', 'voronoi_f1_colour3', 'snoise3', 'snoise4',
           'perlin3', 'perlin4', 'hash2', 'hash3', 'hash4', 'source']
