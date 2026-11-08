"""The terrain's noise, ported bit for bit from eidoverse/terrain.js.

Pure numpy, no bpy: the parity test imports it outside Blender too.

The WebGPU engine works in three.js axes (Y up). Everything in this module stays in those
axes, so the maths reads line for line against the JS: `height_three(x, z)` is the engine's
`heightAt(x, z)`. The Blender-facing wrappers in heightfield.py convert, three (x, y, z) ->
Blender (x, -z, y).

What "exact" means here:
  - mulberry32 is uint32 arithmetic, the same stream for the same seed, including the
    `(seed | 0) || 1` quirk (seed 0 and seed 1 give the same terrain);
  - the 64x64 lattice is a Float32Array in the JS, so its values are float32-rounded here too;
  - every other operation is IEEE double in both languages, in the same order, so heights agree
    to the last bit except where Math.hypot and C hypot differ by an ulp (a 1e-16 relative
    difference in the clearing's blend distance).
"""
import math

import numpy as np

GS = 64  # lattice size, periodic


def _to_uint32_seed(seed):
    """JS `(seed | 0) || 1` as a uint32 bit pattern."""
    try:
        s = float(seed)
    except (TypeError, ValueError):
        s = 0.0
    if not math.isfinite(s):
        s = 0.0
    a = int(s) & 0xFFFFFFFF          # ToInt32: truncate toward zero, wrap mod 2^32
    return a or 1


def mulberry32(seed):
    """Exact port of the engine's mulberry32: returns rand() -> float in [0, 1)."""
    a = _to_uint32_seed(seed)

    def rand():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((a ^ (a >> 15)) * (1 | a)) & 0xFFFFFFFF                       # Math.imul
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
    return rand


def lattice(seed):
    """The 64x64 Float32Array the JS fills from mulberry32(seed), as float64 values."""
    r = mulberry32(seed)
    vals = [r() for _ in range(GS * GS)]
    return np.asarray(vals, dtype=np.float32).astype(np.float64)


def smooth(t):
    """JS `sm`: t <= 0 ? 0 : t >= 1 ? 1 : t*t*(3-2*t)."""
    t = np.asarray(t, dtype=np.float64)
    return np.where(t <= 0, 0.0, np.where(t >= 1, 1.0, t * t * (3 - 2 * t)))


def _lerp(a, b, t):
    return a + (b - a) * t


def vnoise(grid, x, y):
    """Value noise on the periodic lattice (JS `vnoise`)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xi = np.floor(x)
    yi = np.floor(y)
    xf = x - xi
    yf = y - yi
    X = xi.astype(np.int64)
    Y = yi.astype(np.int64)
    X0 = np.mod(X, GS)
    X1 = np.mod(X + 1, GS)
    Y0 = np.mod(Y, GS) * GS
    Y1 = np.mod(Y + 1, GS) * GS
    sx = smooth(xf)
    sy = smooth(yf)
    return _lerp(_lerp(grid[Y0 + X0], grid[Y0 + X1], sx),
                 _lerp(grid[Y1 + X0], grid[Y1 + X1], sx), sy)


def fbm(grid, x, y, octaves=4):
    """JS `fbm`: octaves of vnoise, normalised by 1 - 0.5^octaves."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    v = np.zeros(np.broadcast(x, y).shape, dtype=np.float64)
    a = 0.5
    f = 1.0
    for _ in range(int(octaves)):
        v = v + a * vnoise(grid, x * f, y * f)
        a *= 0.5
        f *= 2
    return v / (1 - math.pow(0.5, int(octaves)))


class Heightfield:
    """The engine's heightAt and blend-weight maths for one set of makeTerrain options."""

    def __init__(self, size=80, amplitude=3, seed=1, flat_radius=0, flat_height=0,
                 octaves=4, frequency=2.5, slope_steep=(0.25, 0.55), high_start=None):
        self.size = float(size)
        self.amplitude = float(amplitude)
        self.seed = seed
        self.flat_radius = float(flat_radius)
        self.flat_height = float(flat_height)
        self.octaves = int(octaves)
        self.frequency = float(frequency)
        self.slope_steep = (float(slope_steep[0]), float(slope_steep[1]))
        self.high_start = None if high_start is None else float(high_start)
        self.grid = lattice(seed)

    def fbm(self, x, y):
        return fbm(self.grid, x, y, self.octaves)

    def height_three(self, x, z):
        """heightAt(x, z) in three.js axes (z = Blender -y). Scalars or arrays."""
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        u = (x / self.size + 0.5) * self.frequency
        v = (z / self.size + 0.5) * self.frequency
        h = (self.fbm(u, v) - 0.5) * 2 * self.amplitude
        if self.flat_radius > 0:
            d = np.hypot(x, z)
            k = smooth((d - self.flat_radius) / max(0.001, self.flat_radius * 0.6))
            h = _lerp(self.flat_height, h, k)
        return h

    def plane_grid(self, segments):
        """three's PlaneGeometry(size, size, n, n).rotateX(-PI/2) vertex x and z, as float32.

        Row iy runs along three +z (Blender -y), column ix along x; vertex index = iy*(n+1)+ix.
        """
        n = int(segments)
        seg = self.size / n
        half = self.size / 2
        ix = np.arange(n + 1, dtype=np.float64)
        xs = (ix * seg - half).astype(np.float32)        # Float32BufferAttribute
        zs = (ix * seg - half).astype(np.float32)        # (-y) stored, then negated by rotateX: exact
        X, Z = np.meshgrid(xs, zs)                        # Z varies by row (iy), X by column (ix)
        return X, Z

    def triangles(self, segments):
        """PlaneGeometry's index buffer: (a, b, d) and (b, c, d) per quad, split on b-d."""
        n = int(segments)
        g1 = n + 1
        iy, ix = np.meshgrid(np.arange(n), np.arange(n), indexing='ij')
        a = ix + g1 * iy
        b = ix + g1 * (iy + 1)
        c = (ix + 1) + g1 * (iy + 1)
        d = (ix + 1) + g1 * iy
        t1 = np.stack([a, b, d], axis=-1).reshape(-1, 3)
        t2 = np.stack([b, c, d], axis=-1).reshape(-1, 3)
        tris = np.empty((t1.shape[0] * 2, 3), dtype=np.int64)
        tris[0::2] = t1                                    # same order as the JS index buffer
        tris[1::2] = t2
        return tris

    def build(self, segments, n_layers=3):
        """The displaced plane and its blend weights, exactly as makeTerrain bakes them.

        Returns dict(X, Z, H: float32 (n+1, n+1) three-axes vertex coords; tris (2n^2, 3);
        normals: (N, 3) three-axes area-weighted vertex normals; weights: (N, 3) R base,
        G mid, B steep; uv: (N, 2)).
        """
        n = int(segments)
        X, Z = self.plane_grid(n)
        H = self.height_three(X.astype(np.float64), Z.astype(np.float64)).astype(np.float32)
        P = np.stack([X.ravel(), H.ravel(), Z.ravel()], axis=-1).astype(np.float64)
        tris = self.triangles(n)
        # three's computeVertexNormals: per face (C - B) x (A - B), summed unnormalised (area
        # weighted) into each corner, then normalised
        pa, pb, pc = P[tris[:, 0]], P[tris[:, 1]], P[tris[:, 2]]
        fn = np.cross(pc - pb, pa - pb)
        nrm = np.zeros_like(P)
        for k in range(3):
            np.add.at(nrm, tris[:, k], fn)
        ln = np.linalg.norm(nrm, axis=1)
        ln[ln == 0] = 1.0
        nrm = (nrm / ln[:, None]).astype(np.float32).astype(np.float64)

        hi = self.amplitude * 0.45 if self.high_start is None else self.high_start
        nl = min(3, int(n_layers))
        slope = 1 - nrm[:, 1]
        s0, s1 = self.slope_steep
        w_steep = smooth((slope - s0) / (s1 - s0)) if nl >= 3 else np.zeros(len(P))
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        breakup = self.fbm(x * 0.15 + 31.7, z * 0.15 + 7.3) - 0.5
        if nl >= 2:
            w_mid = smooth((y - hi + breakup * self.amplitude) / max(0.001, self.amplitude * 0.5)) * (1 - w_steep)
        else:
            w_mid = np.zeros(len(P))
        w_base = np.maximum(0, 1 - w_mid - w_steep)
        weights = np.stack([w_base, w_mid, w_steep], axis=-1).astype(np.float32)

        g = np.arange(n + 1, dtype=np.float64)
        U, V = np.meshgrid(g / n, 1 - g / n)
        uv = np.stack([U.ravel(), V.ravel()], axis=-1).astype(np.float32)
        return dict(X=X, Z=Z, H=H, tris=tris, normals=nrm, weights=weights, uv=uv)
