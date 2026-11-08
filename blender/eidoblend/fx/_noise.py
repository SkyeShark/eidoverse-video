"""The fx family's noise functions, ported from the WebGPU engine number for number (numpy, no bpy).

Each function names its source. They run on arrays, so a whole grid or particle pool is one call.

    snoise(v)              three.js TSL curlNoise.js `snoise` (Ashima simplex, returns 0.5 + 12*dot(...))
    snoise_vec3(v)         TSL `snoiseVec3`, including its upstream quirk: components 1 and 3 apply the
                           `*2-1` to the INPUT, component 2 to the output. Ported as it is: it shapes the fire.
    curl_noise(p)          TSL `curlNoise` (e = 0.1 central differences of snoise_vec3)
    ImprovedNoise          three/addons/math/ImprovedNoise.js (Ken Perlin 2002), the fire light's CPU flicker
    mx_noise_float(p)      three's MaterialX `mx_noise_float` (= mx_perlin_noise_float * amplitude + pivot).
                           Blender's own Noise Texture (detail 0, distortion 0, normalized) computes exactly
                           0.5 * mx_noise_float(p) + 0.5: same Jenkins lookup3 hash, gradients, quintic fade and
                           0.982 scale. Shader graphs use that node; this port is for bakes and the tests.
    tsl_hash(seed)         three's TSL `hash` (PCG, Jarzynski & Olano), float seeds truncated to u32 the way WGSL
                           converts them (toward zero, clamped at 0): negative float seeds all hash like 0.
    swe_vnoise(q), swe_fbm2(q)   fluid_swe.js's value noise (quintic, tsl_hash corners) and its 2-octave sum.

float32 is used where the GPU's single precision decides a result (the hashes' float products); everything
else is float64, which only differs from the GPU in the last bits.
"""

from __future__ import annotations

import math

import numpy as np

__all__ = [
    'snoise', 'snoise_vec3', 'curl_noise', 'ImprovedNoise', 'mx_perlin_noise_float', 'mx_noise_float',
    'tsl_hash', 'tsl_hash_int', 'swe_vnoise', 'swe_fbm2', 'swe_ripple_field',
]


# --------------------------------------------------------------------------------------------------
# TSL simplex noise (three.js examples/jsm/tsl/math/curlNoise.js, vendored as eidoverse/tsl_curl_noise.js)
# --------------------------------------------------------------------------------------------------

_F = np.float32


def _mod289(x):
    return x - _F(289.0) * np.floor(x / _F(289.0))   # TSL mod = GLSL mod (floored), also on WGSL


def _permute(x):
    return _mod289(x * x * _F(34.0) + x)


def snoise(v):
    """TSL `snoise(v: vec3) -> float`. v has shape (..., 3); returns shape (...).

    Computed in float32 like the GPU: the TSL's ns constant 0.142857142857 is not exactly 1/7, and in single
    precision `floor(j * ns.z)` rounds UP to k at every j = 7k (and `floor(p*ns.z*ns.z)` at p = 49k) where
    double precision rounds down. That picks different gradients for about half of all samples, so float64
    would be a different noise, not a more accurate one."""
    v = np.asarray(v, dtype=_F)
    C0, C1 = _F(1.0 / 6.0), _F(1.0 / 3.0)
    i = np.floor(v + (v[..., 0] + v[..., 1] + v[..., 2])[..., None] * C1)
    x0 = v - i + (i[..., 0] + i[..., 1] + i[..., 2])[..., None] * C0
    # g = step(x0.yzx, x0.xyz) = x0.xyz >= x0.yzx
    g = (x0 >= x0[..., [1, 2, 0]]).astype(_F)
    l = _F(1.0) - g
    lzxy = l[..., [2, 0, 1]]
    i1 = np.minimum(g, lzxy)
    i2 = np.maximum(g, lzxy)
    x1 = x0 - i1 + C0
    x2 = x0 - i2 + C1
    x3 = x0 - _F(0.5)                                # x0 - D.yyy
    i = _mod289(i)

    def v4(a, b, c, d):
        return np.stack([a, b, c, d], axis=-1)

    zero = np.zeros(v.shape[:-1], dtype=_F)
    one = np.ones(v.shape[:-1], dtype=_F)
    p = _permute(i[..., 2][..., None] + v4(zero, i1[..., 2], i2[..., 2], one))
    p = _permute(p + i[..., 1][..., None] + v4(zero, i1[..., 1], i2[..., 1], one))
    p = _permute(p + i[..., 0][..., None] + v4(zero, i1[..., 0], i2[..., 0], one))
    # ns = 0.142857142857 * D.wyz - D.xzx, D = (0, .5, 1, 2), in float32
    k7 = _F(0.142857142857)
    nsx = k7 * _F(2.0)
    nsy = k7 * _F(0.5) - _F(1.0)
    nsz = k7
    j = p - _F(49.0) * np.floor(p * nsz * nsz)
    x_ = np.floor(j * nsz)
    x = x_ * nsx + nsy
    y = np.floor(j - _F(7.0) * x_) * nsx + nsy
    h = _F(1.0) - np.abs(x) - np.abs(y)
    b0 = np.stack([x[..., 0], x[..., 1], y[..., 0], y[..., 1]], axis=-1)
    b1 = np.stack([x[..., 2], x[..., 3], y[..., 2], y[..., 3]], axis=-1)
    sh = -(_F(0.0) >= h).astype(_F)                  # -step(h, 0)
    f0 = np.floor(b0) * _F(2.0) + _F(1.0)
    f1 = np.floor(b1) * _F(2.0) + _F(1.0)
    xzyw = [0, 2, 1, 3]
    a0 = b0[..., xzyw] + f0[..., xzyw] * sh[..., [0, 0, 1, 1]]
    a1 = b1[..., xzyw] + f1[..., xzyw] * sh[..., [2, 2, 3, 3]]
    p0 = np.stack([a0[..., 0], a0[..., 1], h[..., 0]], axis=-1)
    p1 = np.stack([a0[..., 2], a0[..., 3], h[..., 1]], axis=-1)
    p2 = np.stack([a1[..., 0], a1[..., 1], h[..., 2]], axis=-1)
    p3 = np.stack([a1[..., 2], a1[..., 3], h[..., 3]], axis=-1)

    def dot(a, b):
        return (a * b).sum(axis=-1)

    p0 = p0 / np.sqrt(dot(p0, p0))[..., None]
    p1 = p1 / np.sqrt(dot(p1, p1))[..., None]
    p2 = p2 / np.sqrt(dot(p2, p2))[..., None]
    p3 = p3 / np.sqrt(dot(p3, p3))[..., None]
    m = np.maximum(0.6 - v4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0)
    m3 = m * m * m
    return 0.5 + 12.0 * dot(m3, v4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)))


def snoise_vec3(x):
    """TSL `snoiseVec3(x: vec3) -> vec3`, quirk included (see the module docstring)."""
    x = np.asarray(x, dtype=_F)
    X, Y, Z = x[..., 0], x[..., 1], x[..., 2]
    a = snoise(x * _F(2.0) - _F(1.0))
    b = snoise(np.stack([Y - _F(19.1), Z + _F(33.4), X + _F(47.2)], axis=-1)) * _F(2.0) - _F(1.0)
    c = snoise(np.stack([Z + _F(74.2), X - _F(124.5), Y + _F(99.4)], axis=-1) * _F(2.0) - _F(1.0))
    return np.stack([a, b, c], axis=-1)


def curl_noise(p, e=0.1):
    """TSL `curlNoise(p)`: the curl of snoise_vec3 by central differences of step e (divergence free)."""
    p = np.asarray(p, dtype=np.float64)
    dx = np.array([e, 0.0, 0.0])
    dy = np.array([0.0, e, 0.0])
    dz = np.array([0.0, 0.0, e])
    p_x0, p_x1 = snoise_vec3(p - dx), snoise_vec3(p + dx)
    p_y0, p_y1 = snoise_vec3(p - dy), snoise_vec3(p + dy)
    p_z0, p_z1 = snoise_vec3(p - dz), snoise_vec3(p + dz)
    cx = p_y1[..., 2] - p_y0[..., 2] - p_z1[..., 1] + p_z0[..., 1]
    cy = p_z1[..., 0] - p_z0[..., 0] - p_x1[..., 2] + p_x0[..., 2]
    cz = p_x1[..., 1] - p_x0[..., 1] - p_y1[..., 0] + p_y0[..., 0]
    return np.stack([cx, cy, cz], axis=-1) * (1.0 / (2.0 * e))


# --------------------------------------------------------------------------------------------------
# ImprovedNoise (three/addons/math/ImprovedNoise.js) — scalar, CPU, used per frame for the fire light
# --------------------------------------------------------------------------------------------------

_P = [151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225, 140, 36, 103, 30, 69, 142, 8, 99,
      37, 240, 21, 10, 23, 190, 6, 148, 247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
      57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175, 74, 165, 71, 134, 139, 48, 27,
      166, 77, 146, 158, 231, 83, 111, 229, 122, 60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102,
      143, 54, 65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169, 200, 196, 135, 130, 116,
      188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64, 52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126,
      255, 82, 85, 212, 207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213, 119, 248, 152,
      2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9, 129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224,
      232, 178, 185, 112, 104, 218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241, 81,
      51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157, 184, 84, 204, 176, 115, 121, 50, 45,
      127, 4, 150, 254, 138, 236, 205, 93, 222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180]
_P = _P + _P


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(t, a, b):
    return a + t * (b - a)


def _grad(h, x, y, z):
    h &= 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h in (12, 14) else z)
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


class ImprovedNoise:
    """three's ImprovedNoise: `ImprovedNoise().noise(x, y, z)` in about [-1, 1]."""

    def noise(self, x, y, z):
        fx, fy, fz = math.floor(x), math.floor(y), math.floor(z)
        X, Y, Z = int(fx) & 255, int(fy) & 255, int(fz) & 255
        x -= fx
        y -= fy
        z -= fz
        xm, ym, zm = x - 1, y - 1, z - 1
        u, v, w = _fade(x), _fade(y), _fade(z)
        p = _P
        A = p[X] + Y
        AA = p[A] + Z
        AB = p[A + 1] + Z
        B = p[X + 1] + Y
        BA = p[B] + Z
        BB = p[B + 1] + Z
        return _lerp(w,
                     _lerp(v, _lerp(u, _grad(p[AA], x, y, z), _grad(p[BA], xm, y, z)),
                           _lerp(u, _grad(p[AB], x, ym, z), _grad(p[BB], xm, ym, z))),
                     _lerp(v, _lerp(u, _grad(p[AA + 1], x, y, zm), _grad(p[BA + 1], xm, y, zm)),
                           _lerp(u, _grad(p[AB + 1], x, ym, zm), _grad(p[BB + 1], xm, ym, zm))))


# --------------------------------------------------------------------------------------------------
# MaterialX Perlin noise (three/src/nodes/materialx/lib/mx_noise.js) — uint32 arithmetic wraps like WGSL
# --------------------------------------------------------------------------------------------------

def _rotl32(x, k):
    return (x << np.uint32(k)) | (x >> np.uint32(32 - k))


def _bjfinal(a, b, c):
    c = c ^ b; c = c - _rotl32(b, 14)
    a = a ^ c; a = a - _rotl32(c, 11)
    b = b ^ a; b = b - _rotl32(a, 25)
    c = c ^ b; c = c - _rotl32(b, 16)
    a = a ^ c; a = a - _rotl32(c, 4)
    b = b ^ a; b = b - _rotl32(a, 14)
    c = c ^ b; c = c - _rotl32(b, 24)
    return c


def _mx_hash_int3(x, y, z):
    seed = np.uint32((0xdeadbeef + (3 << 2) + 13) & 0xffffffff)
    a = seed + x.astype(np.int64).astype(np.uint32)
    b = seed + y.astype(np.int64).astype(np.uint32)
    c = seed + z.astype(np.int64).astype(np.uint32)
    return _bjfinal(a, b, c)


def _mx_gradient3(h, x, y, z):
    h = h & np.uint32(15)
    u = np.where(h < 8, x, y)
    v = np.where(h < 4, y, np.where((h == 12) | (h == 14), x, z))
    u = np.where((h & np.uint32(1)) != 0, -u, u)
    v = np.where((h & np.uint32(2)) != 0, -v, v)
    return u + v


def mx_perlin_noise_float(p):
    """MaterialX `mx_perlin_noise_float(vec3)`: gradient noise in about [-1, 1]. p shape (..., 3)."""
    p = np.asarray(p, dtype=np.float64)
    with np.errstate(over='ignore'):
        fl = np.floor(p)
        X, Y, Z = fl[..., 0], fl[..., 1], fl[..., 2]
        fx, fy, fz = p[..., 0] - X, p[..., 1] - Y, p[..., 2] - Z
        u, v, w = _fade(fx), _fade(fy), _fade(fz)

        def g(dx, dy, dz):
            return _mx_gradient3(_mx_hash_int3(X + dx, Y + dy, Z + dz), fx - dx, fy - dy, fz - dz)

        v0, v1, v2, v3 = g(0, 0, 0), g(1, 0, 0), g(0, 1, 0), g(1, 1, 0)
        v4, v5, v6, v7 = g(0, 0, 1), g(1, 0, 1), g(0, 1, 1), g(1, 1, 1)
    s1, t1, r1 = 1.0 - u, 1.0 - v, 1.0 - w
    res = (r1 * (t1 * (v0 * s1 + v1 * u) + v * (v2 * s1 + v3 * u))
           + w * (t1 * (v4 * s1 + v5 * u) + v * (v6 * s1 + v7 * u)))
    return 0.9820 * res


def mx_noise_float(p, amplitude=1.0, pivot=0.0):
    """three's `mx_noise_float(texcoord, amplitude, pivot)` for vec3 texcoords."""
    return mx_perlin_noise_float(p) * amplitude + pivot


# --------------------------------------------------------------------------------------------------
# TSL hash (three/src/nodes/math/Hash.js) and fluid_swe.js's value noise
# --------------------------------------------------------------------------------------------------

def _pcg(state):
    state = state * np.uint32(747796405) + np.uint32(2891336453)
    word = ((state >> ((state >> np.uint32(28)) + np.uint32(4))) ^ state) * np.uint32(277803737)
    res = (word >> np.uint32(22)) ^ word
    return res.astype(np.float64) * (1.0 / 4294967296.0)


def tsl_hash(seed):
    """TSL `hash(seed)` for FLOAT seeds: u32(seed) truncates toward zero and clamps to [0, 2^32-1] (WGSL)."""
    s = np.asarray(seed, dtype=np.float32)
    s = np.clip(np.trunc(s.astype(np.float64)), 0.0, 4294967295.0).astype(np.uint32)
    with np.errstate(over='ignore'):
        return _pcg(s)


def tsl_hash_int(seed):
    """TSL `hash(seed)` for INTEGER seeds (instance ids and the like): the bits as u32."""
    s = np.asarray(seed, dtype=np.int64).astype(np.uint32)
    with np.errstate(over='ignore'):
        return _pcg(s)


def swe_vnoise(qx, qz):
    """fluid_swe.js `vnoise(q)` (2D value noise, quintic). Corner seeds are float32 products, as on the GPU."""
    qx = np.asarray(qx, dtype=np.float32)
    qz = np.asarray(qz, dtype=np.float32)
    ix, iz = np.floor(qx), np.floor(qz)
    fx, fz = qx - ix, qz - iz
    ux = fx * fx * fx * (fx * (fx * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))
    uz = fz * fz * fz * (fz * (fz * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))

    def hc(ox, oz):
        return tsl_hash((ix + np.float32(ox)) * np.float32(157.31) + (iz + np.float32(oz)) * np.float32(113.97))

    ux = ux.astype(np.float64)
    uz = uz.astype(np.float64)
    a = hc(0, 0) + (hc(1, 0) - hc(0, 0)) * ux
    b = hc(0, 1) + (hc(1, 1) - hc(0, 1)) * ux
    return a + (b - a) * uz


def swe_fbm2(qx, qz):
    """fluid_swe.js `fbm2(q) = vnoise(q) + 0.5 * vnoise(q * 2.13 + 7.7)`."""
    qx = np.asarray(qx, dtype=np.float32)
    qz = np.asarray(qz, dtype=np.float32)
    return swe_vnoise(qx, qz) + 0.5 * swe_vnoise(qx * np.float32(2.13) + np.float32(7.7),
                                                 qz * np.float32(2.13) + np.float32(7.7))


def swe_ripple_field(wx, wz, t, ripple_scale):
    """fluid_swe.js `rippleField(wx, wz, t)`: two counter-scrolled fbm2 layers centred on 0 (~[-1.5, 1.5])."""
    rs = np.float32(ripple_scale)
    wx = np.asarray(wx, dtype=np.float32)
    wz = np.asarray(wz, dtype=np.float32)
    t = np.float32(t) if np.ndim(t) == 0 else np.asarray(t, dtype=np.float32)
    q1x = wx * rs + t * np.float32(2.3)
    q1z = wz * rs + t * np.float32(1.4)
    q2x = wx * rs * np.float32(1.41) - t * np.float32(1.7)
    q2z = wz * rs * np.float32(1.41) - t * np.float32(2.6)
    return swe_fbm2(q1x, q1z) + swe_fbm2(q2x, q2z) - 1.5
