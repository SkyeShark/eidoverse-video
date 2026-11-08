"""The small piece of TSL that Ekigar's operators are written in, restated over numpy arrays.

Ekigar evaluates its terrain as one TSL expression per pixel. Here every scalar is a numpy array over the whole
evaluation grid (or a plain float that broadcasts), so an operator body ports almost line for line:

    TSL                                   here
    a.add(b).mul(c)                       (a + b) * c
    vec2(x, y) / G(f) / f.x               Vec(x, y) / G(f) / f.x
    select(c, a, b)                       select(c, a, b)          (componentwise for vectors)
    mix / clamp / smoothstep / fract      the functions below, with WGSL's definitions
    dFdx / dFdy                           ctx-aware, see eidoblend.terrain.ekigar.compile (grid differences)

Numbers stay float64 (the GPU runs float32; the parity tests compare against Ekigar's own code evaluated at
float64, see blender/tests/terrain_ekigar/tsl_cpu_shim.mjs). Plain Python: no bpy.
"""
from __future__ import annotations

import math

import numpy as np

TAU = 6.283185307179586
EPS = 1e-4


class Vec:
    """A 2, 3 or 4 component vector whose components are arrays or floats (vec2/vec3/vec4 in TSL).

    Arithmetic is componentwise with another Vec of the same size, and broadcasts a scalar (float or array) over the
    components. __array_ufunc__ = None makes `ndarray * Vec` defer to Vec.__rmul__ instead of building an object array.
    """
    __slots__ = ('c',)
    __array_ufunc__ = None

    def __init__(self, *c):
        self.c = tuple(c)

    # components -------------------------------------------------------------------------------------------------
    @property
    def x(self):
        return self.c[0]

    @property
    def y(self):
        return self.c[1]

    @property
    def z(self):
        return self.c[2]

    @property
    def w(self):
        return self.c[3]

    @property
    def xy(self):
        return Vec(self.c[0], self.c[1])

    @property
    def yz(self):
        return Vec(self.c[1], self.c[2])

    @property
    def zw(self):
        return Vec(self.c[2], self.c[3])

    def __len__(self):
        return len(self.c)

    def __iter__(self):
        return iter(self.c)

    def __repr__(self):
        return f'Vec{len(self.c)}({", ".join(_short(v) for v in self.c)})'

    # arithmetic ---------------------------------------------------------------------------------------------------
    def _o(self, o):
        if isinstance(o, Vec):
            if len(o.c) != len(self.c):
                raise ValueError(f'vector size mismatch {len(self.c)} vs {len(o.c)}')
            return o.c
        return (o,) * len(self.c)

    def __add__(self, o):
        return Vec(*(a + b for a, b in zip(self.c, self._o(o))))

    __radd__ = __add__

    def __sub__(self, o):
        return Vec(*(a - b for a, b in zip(self.c, self._o(o))))

    def __rsub__(self, o):
        return Vec(*(b - a for a, b in zip(self.c, self._o(o))))

    def __mul__(self, o):
        return Vec(*(a * b for a, b in zip(self.c, self._o(o))))

    __rmul__ = __mul__

    def __truediv__(self, o):
        return Vec(*(a / b for a, b in zip(self.c, self._o(o))))

    def __rtruediv__(self, o):
        return Vec(*(b / a for a, b in zip(self.c, self._o(o))))

    def __neg__(self):
        return Vec(*(-a for a in self.c))

    # componentwise functions ---------------------------------------------------------------------------------------
    def map(self, fn):
        return Vec(*(fn(a) for a in self.c))

    def abs(self):
        return self.map(np.abs)

    def sign(self):
        return self.map(np.sign)

    def floor(self):
        return self.map(np.floor)

    def fract(self):
        return self.map(fract)


def _short(v):
    if isinstance(v, np.ndarray):
        return f'arr{v.shape}'
    return repr(v)


def vec2(x, y=None):
    if isinstance(x, Vec):
        return Vec(x.c[0], x.c[1])
    return Vec(x, x if y is None else y)


def vec3(x, y=None, z=None):
    if y is None:
        return Vec(x, x, x)
    return Vec(x, y, z)


def vec4(x, y=None, z=None, w=None):
    if y is None:
        return Vec(x, x, x, x)
    return Vec(x, y, z, w)


# ---------------------------------------------------------------------------------------------- scalar functions ---

def fract(x):
    """WGSL fract: x - floor(x)."""
    return x - np.floor(x)


def clamp(x, lo, hi):
    if isinstance(x, Vec):
        return x.map(lambda a: clamp(a, lo, hi))
    return np.minimum(np.maximum(x, lo), hi)


def sat(x):
    return clamp(x, 0.0, 1.0)


def mix(a, b, t):
    """WGSL mix: a * (1 - t) + b * t, componentwise for vectors (t may be a scalar or a vector)."""
    if isinstance(a, Vec) or isinstance(b, Vec) or isinstance(t, Vec):
        n = max(len(x.c) for x in (a, b, t) if isinstance(x, Vec))
        av = a.c if isinstance(a, Vec) else (a,) * n
        bv = b.c if isinstance(b, Vec) else (b,) * n
        tv = t.c if isinstance(t, Vec) else (t,) * n
        return Vec(*(x * (1.0 - s) + y * s for x, y, s in zip(av, bv, tv)))
    return a * (1.0 - t) + b * t


def lerp(a, b, t):
    """Ekigar's lerp(): a + (b - a) * t written as arithmetic (the same value as mix up to rounding)."""
    if isinstance(a, Vec) or isinstance(b, Vec) or isinstance(t, Vec):
        n = max(len(x.c) for x in (a, b, t) if isinstance(x, Vec))
        av = a.c if isinstance(a, Vec) else (a,) * n
        bv = b.c if isinstance(b, Vec) else (b,) * n
        tv = t.c if isinstance(t, Vec) else (t,) * n
        return Vec(*(x + (y - x) * s for x, y, s in zip(av, bv, tv)))
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    """WGSL smoothstep: t = clamp((x - e0) / (e1 - e0), 0, 1); t*t*(3 - 2t)."""
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def select(c, a, b):
    """WGSL select(false_value, true_value, cond) in TSL's order: c ? a : b, componentwise for vectors."""
    if isinstance(a, Vec) or isinstance(b, Vec):
        n = len(a.c) if isinstance(a, Vec) else len(b.c)
        av = a.c if isinstance(a, Vec) else (a,) * n
        bv = b.c if isinstance(b, Vec) else (b,) * n
        return Vec(*(np.where(c, x, y) for x, y in zip(av, bv)))
    return np.where(c, a, b)


def step01(c):
    """A boolean condition as 0.0 / 1.0 (TSL's select(c, float(1), float(0)))."""
    return np.where(c, 1.0, 0.0)


def maximum(a, b):
    if isinstance(a, Vec) or isinstance(b, Vec):
        return _vec2op(np.maximum, a, b)
    return np.maximum(a, b)


def minimum(a, b):
    if isinstance(a, Vec) or isinstance(b, Vec):
        return _vec2op(np.minimum, a, b)
    return np.minimum(a, b)


def _vec2op(fn, a, b):
    n = len(a.c) if isinstance(a, Vec) else len(b.c)
    av = a.c if isinstance(a, Vec) else (a,) * n
    bv = b.c if isinstance(b, Vec) else (b,) * n
    return Vec(*(fn(x, y) for x, y in zip(av, bv)))


def power(x, y):
    """WGSL pow (undefined below zero: NaN here, as on the GPU; callers guard with max(x, EPS))."""
    return np.power(x, y)


def dot(a, b):
    return sum(x * y for x, y in zip(a.c, b.c))


def length(v):
    if isinstance(v, Vec):
        return np.sqrt(dot(v, v))
    return np.abs(v)


def normalize(v):
    return v / length(v)


def one_minus(x):
    return 1.0 - x


def nonzero(v):
    """Keep a divisor's sign but never divide by ~0 (registry nonZero)."""
    return np.maximum(np.abs(v), EPS) * np.where(v < 0, -1.0, 1.0)


def as_float(x):
    return float(x)


class Tile:
    """ctx.tile: the period of the field on each axis, in the units of p (0 = not periodic on that axis)."""
    __slots__ = ('x', 'y')

    def __init__(self, x=1.0, y=1.0):
        self.x = float(x or 0.0)
        self.y = float(y or 0.0)

    @classmethod
    def of(cls, t):
        if isinstance(t, Tile):
            return t
        if t is None:
            return cls(1.0, 1.0)
        if isinstance(t, dict):
            return cls(t.get('x', 0) or 0, t.get('y', 0) or 0)
        if isinstance(t, (int, float)):
            return cls(t, t)
        return cls(t[0], t[1])

    def as_dict(self):
        return {'x': self.x, 'y': self.y}

    def __repr__(self):
        return f'Tile({self.x}, {self.y})'


class Params:
    """An operator's resolved parameters with JS-style access: p.frequency, and None for a missing key."""

    def __init__(self, d=None, **kw):
        self.__dict__.update(d or {})
        self.__dict__.update(kw)

    def __getattr__(self, k):              # only reached for a missing key
        if k.startswith('__'):
            raise AttributeError(k)
        return None

    def __getitem__(self, k):
        return self.__dict__.get(k)

    def __contains__(self, k):
        return k in self.__dict__

    def dict(self):
        return dict(self.__dict__)

    def with_(self, **kw):
        d = dict(self.__dict__)
        d.update(kw)
        return Params(d)

    def __repr__(self):
        return f'Params({self.__dict__})'


def or_default(v, d):
    """JS `v ?? d`."""
    return d if v is None else v


def deg2rad(d):
    return float(d) * math.pi / 180.0
