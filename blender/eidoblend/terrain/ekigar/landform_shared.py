"""Shared, tile-safe geometry for Ekigar's first-class landform library (src/core/landform_shared.js), over numpy.

Landform profiles are scalar functions of position. sampled_add() takes a central derivative of a profile while it
is built, so every profile carries a consistent gradient downstream without derivative algebra written 39 times.

Note the two smoothsteps, kept apart as in the source: sstep() here is the typed polynomial with an EPS-guarded span
(the wave files import it AS `smoothstep`), and smoothstep_wgsl() is the WGSL builtin ring() and breach() use.
"""
from __future__ import annotations

import math
from types import SimpleNamespace as NS

import numpy as np

from ._tsl import Vec, clamp, mix, select, step01, dot, length, normalize, fract, sat
from .noise import noised, hash2

TAU = 6.283185307179586
EPS = 1e-4


class P:
    @staticmethod
    def float(default, lo, hi, **extra):
        return {'type': 'float', 'default': default, 'min': lo, 'max': hi, 'maskable': True, **extra}

    @staticmethod
    def int(default, lo, hi, **extra):
        return {'type': 'int', 'default': default, 'min': lo, 'max': hi, 'structural': True, 'maskable': False,
                **extra}

    @staticmethod
    def bool(default, **extra):
        return {'type': 'bool', 'default': default, 'structural': True, 'maskable': False, **extra}

    @staticmethod
    def enum(default, values, **extra):
        return {'type': 'enum', 'default': default, 'values': list(values), 'structural': True, 'maskable': False,
                **extra}

    @staticmethod
    def vec2(default, **extra):
        return {'type': 'vec2', 'default': list(default), 'maskable': False, **extra}


def H(f):
    return f.x


def G(f):
    return Vec(f.y, f.z)


def AUX(f):
    return f.w


def field(h, g, aux=0.0):
    return Vec(h, g.x, g.y, aux)


def sstep(edge0, edge1, x):
    """Typed smoothstep polynomial: t = sat((x - a) / max(b - a, EPS)); t*t*(3 - 2t)."""
    t = sat((x - edge0) / np.maximum(edge1 - edge0, EPS))
    return t * t * (3.0 - t * 2.0)


def smoothstep_wgsl(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def js_round(v):
    return int(math.floor(float(v) + 0.5))


def js_mod(a, b):
    """JS `%` on numbers: the remainder takes the sign of the dividend."""
    return math.fmod(a, b)


def wrapped_delta(p, centre, tile):
    d = p - centre
    tx = tile.x if tile.x > 0 else 1.0
    ty = tile.y if tile.y > 0 else 1.0
    x = d.x - tile.x * np.floor(d.x / tx + 0.5) if tile.x > 0 else d.x
    y = d.y - tile.y * np.floor(d.y / ty + 0.5) if tile.y > 0 else d.y
    return Vec(x, y)


def sampled_add(f, ctx, shape, aux=None):
    """Add a periodic scalar profile and its central derivative to an input field."""
    e = 1.0 / max(512, ctx.resolution if ctx.resolution is not None else 512)
    q = ctx.p
    h = shape(q)
    gx = (shape(q + Vec(e, 0.0)) - shape(q - Vec(e, 0.0))) / (2 * e)
    gy = (shape(q + Vec(0.0, e)) - shape(q - Vec(0.0, e))) / (2 * e)
    a = aux(q, h) if aux else sat(np.abs(h) * 4.0)
    return field(H(f) + h, G(f) + Vec(gx, gy), a)


def seed_shift(seed=0):
    s = js_round(seed) & 0xFFFFFFFF
    return [((s * 1103515245 + 12345) & 0xFFFFFFFF) % 4096, ((s * 22695477 + 1) & 0xFFFFFFFF) % 4096]


def noise(q, frequency, ctx, seed=0):
    """Periodic coherent noise in roughly [-1, 1]; frequency is structural (rounded to whole cells)."""
    f = max(1, js_round(frequency))
    sx, sy = seed_shift(seed)
    return noised(q.x * f + sx, q.y * f + sy, ctx.tile.x * f, ctx.tile.y * f)[0]


def fbm(q, frequency, octaves, ctx, seed=0, gain=0.5):
    s, norm, amp = 0.0, 0.0, 1.0
    f = max(1, js_round(frequency))
    for i in range(int(octaves)):
        s = s + noise(q, f, ctx, seed + i * 137) * amp
        norm += amp
        amp *= gain
        f *= 2
    return s / (norm or 1.0)


def ridged(q, frequency, octaves, ctx, seed=0):
    return (1.0 - np.abs(fbm(q, frequency, octaves, ctx, seed))) * 2.0 - 1.0


def scatter_cell(q, cells, ctx, seed=0, jitter=0.82):
    """Nearest jittered periodic lattice point plus four stable instance randoms: NS(d, delta, random, cells)."""
    n = max(1, js_round(cells))
    sx, sy = seed_shift(seed)
    sp = q * n
    base = sp.floor()
    fr = sp.fract()
    perx, pery = ctx.tile.x * n, ctx.tile.y * n
    best = 1e4
    delta = Vec(0.0, 0.0)
    random = Vec(0.0, 0.0, 0.0, 0.0)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx = base.x + ox
            cy = base.y + oy
            ax_, ay_ = hash2(cx + sx, cy + sy, perx, pery)
            bx_, by_ = hash2(cx + (sx + 733), cy + (sy + 197), perx, pery)
            d = Vec(ox + 0.5 + ax_ * jitter * 0.48 - fr.x, oy + 0.5 + ay_ * jitter * 0.48 - fr.y)
            dist = length(d)
            win = dist < best
            best = np.minimum(best, dist)
            delta = select(win, d, delta)
            random = select(win, Vec(ax_ * 0.5 + 0.5, ay_ * 0.5 + 0.5, bx_ * 0.5 + 0.5, by_ * 0.5 + 0.5), random)
    return NS(d=best, delta=delta, random=random, cells=n)


def radial(q, ctx, x=0.5, y=0.5, scale=0.3):
    d = wrapped_delta(q, Vec(x, y), ctx.tile)
    return NS(d=d, r=length(d) / np.maximum(scale, EPS))


def ring(r, centre=1.0, width=0.08):
    return 1.0 - smoothstep_wgsl(0.0, np.maximum(width, EPS), np.abs(r - centre))


def bowl_profile(r, floor=0.3, wall=0.55, rimWidth=0.08, rimHeight=0.2, apron=0.12):
    """Four-zone depression: floor, wall, raised rim and decaying apron (the landform library's version)."""
    wall_start = np.maximum(floor, 0.02)
    wall_end = np.maximum(wall_start + 0.02, 1.0 - np.maximum(wall, 0.02) * 0.08)
    basin = mix(-1.0, 0.0, smoothstep_wgsl(wall_start, wall_end, r))
    crest = ring(r, 1.0, rimWidth) * rimHeight
    outside = np.maximum(r - 1.0, 0.0)
    apron_shape = np.exp(-(outside / np.maximum(apron, EPS))) * apron * step01(r > 1)
    return basin + crest + apron_shape


_BREACH_DIRS = {'east': (1, 0), 'west': (-1, 0), 'north': (0, 1), 'south': (0, -1),
                'northeast': (0.7071068, 0.7071068), 'northwest': (-0.7071068, 0.7071068)}


def breach(d, direction='east', width=0.3, softness=0.08):
    """Dot-product angular gate without an azimuth branch cut."""
    v = _BREACH_DIRS.get(direction, _BREACH_DIRS['east'])
    c = dot(normalize(d + Vec(EPS, 0.0)), Vec(float(v[0]), float(v[1])))
    return smoothstep_wgsl(1.0 - width - softness, 1.0 - width, c)


def fan_profile(r, concavity=2.5, toe=1.0):
    t = sat(1.0 - r / np.maximum(toe, EPS))
    return (1.0 - np.exp(-(t * concavity))) / np.maximum(1.0 - np.exp(-concavity), EPS)


def snapped_axis(direction='x'):
    if isinstance(direction, (int, float)) and not isinstance(direction, bool):
        i = js_round(direction / 45.0) % 8
        return [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]][i]
    return {'y': [0, 1], 'diag': [1, 1], 'anti': [1, -1], 'west': [-1, 0], 'south': [0, -1]}.get(direction, [1, 0])


def axis_vectors(direction='x'):
    a = snapped_axis(direction)
    return a, [-a[1], a[0]]


def axis_frame(q, direction='x', bends=2, sinuosity=0.08, seed=0):
    """Period-closing directed frame with an integral-wave sinuous centreline: NS(along, across, w, axis, side)."""
    a, c = axis_vectors(direction)
    along = dot(q, Vec(float(a[0]), float(a[1])))
    across = dot(q, Vec(float(c[0]), float(c[1])))
    phase = js_mod(seed * 0.754877666, 1) * TAU
    centre = 0.5 + np.sin(along * (TAU * max(1, bends)) + phase) * sinuosity
    w = across - centre
    w = w - np.floor(w + 0.5)
    return NS(along=along, across=across, w=w, axis=Vec(float(a[0]), float(a[1])), side=Vec(float(c[0]), float(c[1])))


def asym_ridge(w, steepWidth=0.08, gentleWidth=0.24, steepPower=1.5, gentlePower=2.0):
    left = np.power(sat(1.0 - np.abs(w) / np.maximum(steepWidth, EPS)), steepPower)
    right = np.power(sat(1.0 - np.abs(w) / np.maximum(gentleWidth, EPS)), gentlePower)
    return np.where(w < 0, left, right)


def bench_stack(s, treads=6, convexity=0.55, jitter=0.0):
    """Monotone tread/riser transfer keyed to an arbitrary scalar: NS(value, tread, riser, index)."""
    n = max(2, js_round(treads))
    x = s * n + jitter
    i = np.floor(x)
    fr = fract(x)
    riser_start = 0.45 + convexity * 0.38
    shaped = sstep(riser_start, 0.98, fr)
    return NS(value=(i + shaped) / n,
              tread=1.0 - sstep(riser_start - 0.08, riser_start + 0.02, fr),
              riser=sstep(riser_start - 0.04, riser_start + 0.05, fr) * (1.0 - sstep(0.94, 1.0, fr)),
              index=i / max(1, n - 1))


def streamline(delta, direction='x', elongation=3.0, bluntness=0.5):
    a, c = axis_vectors(direction)
    s = dot(delta, Vec(float(a[0]), float(a[1]))) * 2.0 / np.maximum(elongation, EPS)
    t = dot(delta, Vec(float(c[0]), float(c[1]))) * 2.0
    lee = np.maximum(s, 0.0)
    taper = np.maximum(0.25, 1.0 - lee * bluntness)
    rho = s * s + (t / taper) * (t / taper)
    return np.power(sat(1.0 - rho), 1.6)


def piedmont_break(h, level=0.0, apron=0.08):
    e = h - level
    above = np.maximum(e, 0.0)
    shoulder = 1.0 + (1.0 - smoothstep_wgsl(0.0, np.maximum(apron, EPS), above)) * 0.3
    return NS(value=level + above * shoulder, floor=1.0 - step01(e > 0))


def surface_detail(q, ctx, seed=0, frequency=7, octaves=3):
    """Zone-aware, nonzero microrelief that keeps analytic silhouettes geologically alive."""
    broad = fbm(q, frequency, octaves, ctx, seed)
    fine = ridged(q, frequency * 2, max(2, octaves - 1), ctx, seed + 911)
    return broad * 0.62 + fine * 0.38
