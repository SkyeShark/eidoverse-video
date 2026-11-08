"""JS-exact maths for the flora port: the generators and the placement draw from these exactly as the WebGPU
originals do, so one seed grows the same stand in both editions.

- Rng: SeedThree's src/core/rng.js (xmur3 + splitmix32), the stream vegetation_shrub_gen.js vendors and the corn,
  sunflower and daisy generators import. All 32-bit integer maths is kept as uint32 bit patterns.
- lehmer: vegetation.js's Park-Miller stream (doubles, JS `%` = math.fmod).
- value_noise_2d: vegetation.js's sin-hash value noise (doubles).
- js_round: Math.round (floor(x + 0.5)); Python's round() rounds halves to even.
"""
import math

M32 = 0xFFFFFFFF


def imul(a, b):
    """Math.imul as a uint32 bit pattern."""
    return ((a & M32) * (b & M32)) & M32


def xmur3(s):
    h = (1779033703 ^ len(s)) & M32
    for ch in s:
        h = imul(h ^ ord(ch), 3432918353)
        h = ((h << 13) | (h >> 19)) & M32

    def nxt():
        nonlocal h
        h = imul(h ^ (h >> 16), 2246822507)
        h = imul(h ^ (h >> 13), 3266489909)
        h ^= h >> 16
        return h & M32
    return nxt


def js_num(v):
    """A number the way a JS template literal prints it (7.0 -> '7')."""
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e21:
        return str(int(v))
    return str(v)


class Rng:
    def __init__(self, seed):
        s = f'n:{js_num(seed)}' if isinstance(seed, (int, float)) else str(seed)
        self._state = xmur3(s)() & M32

    def next(self):
        self._state = (self._state + 0x9E3779B9) & M32
        z = self._state
        z ^= z >> 16
        z = imul(z, 0x21F0AAAD)
        z ^= z >> 15
        z = imul(z, 0x735A2D97)
        z ^= z >> 15
        return (z & M32) / 4294967296.0

    def range(self, lo, hi):
        return lo + (hi - lo) * self.next()

    def vary(self, base, spread):
        return base + (self.next() * 2 - 1) * spread


def lehmer(seed, mult):
    """vegetation.js lehmer(): the seed folded into [1, M-1], then s = s * mult % M (doubles)."""
    M = 2147483647.0
    s = math.fmod(float(seed), M) if math.isfinite(seed) else 0.0
    if s < 0:
        s += M
    if s == 0:
        s = math.fmod(2654435761.0, M)
    state = [s]

    def nxt():
        state[0] = math.fmod(state[0] * mult, M)
        return state[0] / M
    return nxt


def _fract(v):
    return v - math.floor(v)


def value_noise_2d(seed):
    def h(x, y):
        return _fract(math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453)

    def n(x, y):
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        ux, uy = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
        return ((h(xi, yi) * (1 - ux) + h(xi + 1, yi) * ux) * (1 - uy)
                + (h(xi, yi + 1) * (1 - ux) + h(xi + 1, yi + 1) * ux) * uy)
    return n


def value_noise_2d_np(seed, x, y):
    """value_noise_2d over numpy arrays (the gust texture's 65k samples)."""
    import numpy as np
    xi, yi = np.floor(x), np.floor(y)
    xf, yf = x - xi, y - yi
    ux, uy = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)

    def h(a, b):
        s = np.sin(a * 12.9898 + b * 78.233 + seed * 37.719) * 43758.5453
        return s - np.floor(s)
    return ((h(xi, yi) * (1 - ux) + h(xi + 1, yi) * ux) * (1 - uy)
            + (h(xi, yi + 1) * (1 - ux) + h(xi + 1, yi + 1) * ux) * uy)


def js_round(x):
    return math.floor(x + 0.5)


def smoothstep(a, b, v):
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return t * t * (3 - 2 * t)
