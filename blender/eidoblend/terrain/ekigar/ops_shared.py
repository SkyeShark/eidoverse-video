"""The shared maths of Ekigar's operator registry (src/core/registry.js, the helpers above OPERATORS), over numpy.

THE FIELD every operator consumes and returns is a vec4: x = height, (y, z) = the carried analytic gradient
(dh/dx, dh/dy), w = aux (ridge / a mask). Any operator that changes height also updates the gradient consistently,
for a remap h' = f(h) by the chain rule dh' = f'(h) dh; every helper here therefore returns a value AND its
derivative.

The carried gradient is for operator chaining (it steers erosion gullies); masks for material layering come from
finite differences of the final height (eidoblend.terrain.ekigar.masks).
"""
from __future__ import annotations

import math
from types import SimpleNamespace as NS

import numpy as np

from ._tsl import Vec, clamp, mix, lerp, select, step01, dot, length, fract, TAU, EPS
from .noise import noised, hash2, fractal_noise


# ----------------------------------------------------------------------------------------------- field access ---

def H(f):
    return f.x


def G(f):
    return Vec(f.y, f.z)


def AUX(f):
    return f.w


def field(h, g, aux):
    return Vec(h, g.x, g.y, aux)


def remap(f, new_h, dfdh):
    """Chain rule for a height remap: h' = f(h) with f'(h), rebuilt as a field."""
    return field(new_h, G(f) * dfdh, AUX(f))


def wrapped_delta(p, c, tile):
    """Periodic offset from point c to p, honouring per-axis tiling."""
    d = p - c
    wx = d.x - tile.x * np.floor(d.x / (tile.x or 1.0) + 0.5) if tile.x > 0 else d.x
    wy = d.y - tile.y * np.floor(d.y / (tile.y or 1.0) + 0.5) if tile.y > 0 else d.y
    return Vec(wx, wy)


def smoothstep_wgsl(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def smoothstep_soft(v, lo, hi, falloff):
    """A soft window: rises through lo, falls through hi, feathered by falloff."""
    rise = smoothstep_wgsl(lo - falloff, lo + falloff, v)
    fall = 1.0 - smoothstep_wgsl(hi - falloff, hi + falloff, v)
    return rise * fall


# ----------------------------------------------------------------------------------------------- param schema ---

class P:
    """Parameter declarations, as registry.js's P: the schema drives the inspector, the API and the defaults."""

    @staticmethod
    def float(default, lo, hi, **o):
        return {'type': 'float', 'default': default, 'min': lo, 'max': hi, 'maskable': True, **o}

    @staticmethod
    def int(default, lo, hi, **o):
        return {'type': 'int', 'default': default, 'min': lo, 'max': hi, 'structural': True, 'maskable': False, **o}

    @staticmethod
    def bool(default, **o):
        return {'type': 'bool', 'default': default, 'structural': True, 'maskable': False, **o}

    @staticmethod
    def enum(default, values, **o):
        return {'type': 'enum', 'default': default, 'values': list(values), 'structural': True, 'maskable': False, **o}

    @staticmethod
    def vec2(default, **o):
        return {'type': 'vec2', 'default': list(default), 'maskable': False, **o}


COMBINE_MODE_VALUES = [
    'add', 'subtract', 'multiply', 'max', 'min', 'blend',
    'screen', 'difference', 'divide', 'divide2', 'hypotenuse', 'overlay',
    'power', 'exclusion', 'dodge', 'burn', 'softLight', 'hardLight',
    'pinLight', 'grainMerge', 'grainExtract', 'reflect', 'glow', 'phoenix',
]


def RES(ctx):
    return ctx.resolution if ctx.resolution is not None else 1024


def texel(ctx, radius):
    """Tap distance in world units for a neighbour radius given in texels (divided by the FIELD resolution)."""
    return (float(radius) / RES(ctx)) * (ctx.tile.x if ctx.tile.x > 0 else 1.0)


def js_round(v):
    """JS Math.round (halves toward +infinity)."""
    return int(math.floor(float(v) + 0.5))


def seed_shift(seed):
    """Two decorrelated non-negative integers from a seed: a seed shifts the lattice by WHOLE cells, re-rolling the
    pattern without changing its period, so seeding cannot break tiling."""
    s = js_round(seed or 0) & 0xFFFFFFFF
    return [((s * 1103515245 + 12345) & 0xFFFFFFFF) % 4096, ((s * 22695477 + 1) & 0xFFFFFFFF) % 4096]


def seed_offset(seed, freq):
    """World-space offset that shifts a lattice of `freq` cells/tile by whole cells."""
    a, b = seed_shift(seed)
    f = max(float(freq), 1e-6)
    return [a / f, b / f]


def snap_axis(deg):
    """Snap a direction in degrees to the nearest lattice axis: an arbitrary rotation of a periodic field is not
    periodic, so snapping is a tiling constraint."""
    return [[1, 0], [0, 1], [-1, 0], [0, -1]][js_round((deg or 0) / 90.0) % 4]


def nonzero(v):
    return np.maximum(np.abs(v), EPS) * np.where(v < 0, -1.0, 1.0)


def sstep(e0, e1, x):
    """smoothstep with its first and second derivatives with respect to x: NS(v, d, dd, t, w, inside)."""
    w = np.maximum(e1 - e0, EPS)
    t = clamp((x - e0) / w, 0.0, 1.0)
    inside = step01((t > 0) & (t < 1))
    return NS(v=t * t * (3.0 - t * 2.0), d=t * (1.0 - t) * 6.0 / w,
              dd=(1.0 - t * 2.0) * 6.0 / (w * w) * inside, t=t, w=w, inside=inside)


def strata_fold(v, bands, strength, convexity=0.5):
    """THE stratification fold: monotone by construction. Each bed has equal lower and upper treads joined by a
    bounded cubic-Hermite riser; returns NS(v, d) with d = d(new)/d(old) for the chain rule."""
    b = bands
    s = v * b
    i = np.floor(s)
    fr = fract(s)
    riser = lerp(0.48, 0.18, convexity)
    start = (1.0 - riser) * 0.5
    t = clamp((fr - start) / riser, 0.0, 1.0)
    rise = t * t * (3.0 - t * 2.0)
    inside = step01((t > 0) & (t < 1))
    dtarget = t * (1.0 - t) * 6.0 / riser * inside
    target = (i + rise) / b
    k = clamp(strength, 0.0, 1.0)
    return NS(v=v + (target - v) * k, d=(1.0 - k) + k * dtarget)


def waveform(kind, u):
    """Periodic waveform on u, normalised to 0..1, with d/du."""
    if kind == 'triangle':
        t = fract(u)
        return NS(v=np.abs(t - 0.5) * 2.0, d=np.sign(t - 0.5) * 2.0)
    if kind == 'sawtooth':
        return NS(v=fract(u), d=1.0)
    return NS(v=(1.0 - np.cos(u * TAU)) * 0.5, d=np.sin(u * TAU) * (TAU * 0.5))


def median_of(xs):
    """Median of a list of arrays, by the same bubble-exchange min/max network the shader unrolls."""
    a = list(xs)
    n = len(a)
    for i in range(n - 1):
        for j in range(n - 1 - i):
            lo = np.minimum(a[j], a[j + 1])
            hi = np.maximum(a[j], a[j + 1])
            a[j], a[j + 1] = lo, hi
    return a[(n - 1) >> 1]


# ---------------------------------------------------------------------------------------------- noise fields ---

def fbm_field(ctx, frequency, octaves, lacunarity=2, gain=0.5, offset=(0, 0)):
    """fBm normalised to roughly [-1, 1], with its exact gradient."""
    n = fractal_noise(ctx.p + Vec(offset[0], offset[1]), frequency, octaves, lacunarity, gain, ctx.tile)
    norm, na = 0.0, 1.0
    for _ in range(int(octaves)):
        norm += na
        na *= gain
    return NS(v=n.x / norm, g=Vec(n.y, n.z) / norm)


def ridged_field(ctx, frequency, octaves, lacunarity=2, gain=0.5, sharpness=None, offset=(0, 0)):
    """Ridged multifractal normalised to roughly [0, 1], with its exact gradient (|n| folded, sign(n) on d)."""
    q = ctx.p + Vec(offset[0], offset[1])
    h = g = None
    nf, na, norm = float(frequency), 1.0, 0.0
    for _ in range(int(octaves)):
        nv, ndx, ndy = noised(q.x * nf, q.y * nf, ctx.tile.x * nf, ctx.tile.y * nf)
        term = (1.0 - np.abs(nv)) * na
        sg = -np.sign(nv) * (na * nf)
        d = Vec(ndx * sg, ndy * sg)
        h = term if h is None else h + term
        g = d if g is None else g + d
        norm += na
        na *= gain
        nf *= lacunarity
    v = h / norm
    vg = g / norm
    if sharpness is None:
        return NS(v=v, g=vg)
    s = sharpness
    base = np.maximum(v, EPS)
    return NS(v=np.power(base, s), g=vg * (s * np.power(base, s - 1.0)))


def swiss_field(ctx, frequency, octaves, lacunarity=2, gain=0.5, warp=0.35, offset=(0, 0)):
    """Swiss turbulence (de Carpentier): derivative feedback shears the finer octaves downhill and the amplitude is
    damped by the running sum, on the periodic lattice."""
    q0 = ctx.p + Vec(offset[0], offset[1])
    nf = float(frequency)
    amp = 1.0
    s = 0.0
    gx = gy = 0.0
    dsx = dsy = 0.0
    max_sum, amp_max = 0.0, 1.0
    w_amt = warp / max(frequency, 1)
    for _ in range(int(octaves)):
        qx = q0.x + dsx * w_amt
        qy = q0.y + dsy * w_amt
        nv, ndx, ndy = noised(qx * nf, qy * nf, ctx.tile.x * nf, ctx.tile.y * nf)
        ridge = 1.0 - np.abs(nv)
        sgn = -np.sign(nv)
        s = s + amp * ridge
        gx = gx + amp * sgn * ndx * nf
        gy = gy + amp * sgn * ndy * nf
        dsx = dsx + amp * ndx * (-nv)
        dsy = dsy + amp * ndy * (-nv)
        max_sum += amp_max
        amp_max *= gain
        amp = amp * gain * clamp(s, 0.15, 1.0)
        nf *= lacunarity
    return NS(v=s / max_sum, g=Vec(gx, gy) / max_sum)


def jordan_field(ctx, frequency, octaves, lacunarity=2, gain=0.5, warp0=0.4, warp=0.35, damp0=1.0, damp=0.8,
                 damp_scale=0.9, offset=(0, 0)):
    """Jordan turbulence (de Carpentier): billow-squared octaves with separate warp and damp derivative sums."""
    q0 = ctx.p + Vec(offset[0], offset[1])
    nf = float(frequency)
    n0, n0x, n0y = noised(q0.x * nf, q0.y * nf, ctx.tile.x * nf, ctx.tile.y * nf)
    s = n0 * n0
    gx = n0 * 2.0 * n0x * nf
    gy = n0 * 2.0 * n0y * nf
    dwx, dwy = n0x * n0 * warp0, n0y * n0 * warp0
    ddx, ddy = n0x * n0 * damp0, n0y * n0 * damp0
    amp_js, max_sum = 1.0, 1.0
    for _ in range(1, int(octaves)):
        nf *= lacunarity
        amp_js *= gain
        nv, ndx, ndy = noised(q0.x * nf + dwx, q0.y * nf + dwy, ctx.tile.x * nf, ctx.tile.y * nf)
        damped = amp_js * (1.0 - damp_scale / ((ddx * ddx + ddy * ddy) * 16.0 + 1.0))
        s = s + damped * nv * nv
        gx = gx + damped * nv * 2.0 * ndx * nf
        gy = gy + damped * nv * 2.0 * ndy * nf
        dwx = dwx + ndx * nv * warp
        dwy = dwy + ndy * nv * warp
        ddx = ddx + ndx * nv * damp
        ddy = ddy + ndy * nv * damp
        max_sum += amp_js
    return NS(v=s / max_sum * 2.3, g=Vec(gx, gy) / max_sum * 2.3)


def billowy_field(ctx, frequency, octaves, lacunarity=2, gain=0.5, offset=None):
    """Billowy noise normalised to [-1, 1], with its gradient."""
    off = offset or (0, 0)
    q = ctx.p + Vec(off[0], off[1])
    h = g = None
    nf, na, norm = float(frequency), 1.0, 0.0
    for _ in range(int(octaves)):
        nv, ndx, ndy = noised(q.x * nf, q.y * nf, ctx.tile.x * nf, ctx.tile.y * nf)
        term = (np.abs(nv) * 2.0 - 1.0) * na
        sg = np.sign(nv) * (na * nf * 2.0)
        d = Vec(ndx * sg, ndy * sg)
        h = term if h is None else h + term
        g = d if g is None else g + d
        norm += na
        na *= gain
        nf *= lacunarity
    return NS(v=h / norm, g=g / norm)


# ------------------------------------------------------------------------------------------------- cellular ---

def cell_metric(kind, d, morph):
    """Distance metric with Metric Morph blending Euclidean toward the second-named metric; NS(v, g=d(dist)/d(d))."""
    r = np.maximum(length(d), EPS)
    ge = d / r
    if kind == 'euclidianChebyshev':
        xw = np.abs(d.x) > np.abs(d.y)
        return NS(v=mix(r, np.maximum(np.abs(d.x), np.abs(d.y)), morph),
                  g=mix(ge, Vec(np.where(xw, np.sign(d.x), 0.0), np.where(xw, 0.0, np.sign(d.y))), morph))
    if kind == 'euclidianManhattan':
        return NS(v=mix(r, np.abs(d.x) + np.abs(d.y), morph), g=mix(ge, Vec(np.sign(d.x), np.sign(d.y)), morph))
    return NS(v=r, g=ge)


def euclid_metric(d):
    r = np.maximum(length(d), EPS)
    return NS(v=r, g=d / r)


def cell_search(sp, period, jitter, seed_cell, metric_fn):
    """Nearest and second-nearest jittered lattice point over the 9 surrounding cells, carrying the gradient of
    both: NS(f1, g1, f2, g2, rand=vec4 of four 0..1 randoms of the winning cell, cell, delta)."""
    cell = sp.floor()
    frc = sp.fract()
    perx, pery = (period.x, period.y) if isinstance(period, Vec) else period
    f1 = g1 = r1 = f2 = g2 = c1 = d1 = None
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            off = Vec(float(i), float(j))
            cc = cell + off + seed_cell
            hx, hy = hash2(cc.x, cc.y, perx, pery)
            h2x, h2y = hash2(cc.x + 1731.0, cc.y + 977.0, perx, pery)
            jit = Vec(hx * 0.5 + 0.5, hy * 0.5 + 0.5)
            d = off + mix(Vec(0.5, 0.5), jit, jitter) - frc
            m = metric_fn(d)
            rand = Vec(hx * 0.5 + 0.5, hy * 0.5 + 0.5, h2x * 0.5 + 0.5, h2y * 0.5 + 0.5)
            if f1 is None:
                f1, g1, r1, c1, d1 = m.v, m.g, rand, cc, d
                f2, g2 = 9.0, Vec(0.0, 0.0)
            else:
                win = m.v < f1
                runner = m.v < f2
                nf2 = np.where(win, f1, np.where(runner, m.v, f2))
                ng2 = select(win, g1, select(runner, m.g, g2))
                f1 = np.where(win, m.v, f1)
                g1 = select(win, m.g, g1)
                r1 = select(win, rand, r1)
                c1 = select(win, cc, c1)
                d1 = select(win, d, d1)
                f2, g2 = nf2, ng2
    return NS(f1=f1, g1=g1, f2=f2, g2=g2, rand=r1, cell=c1, delta=d1)


# ------------------------------------------------------------------------------------------------- profiles ---

def bowl_profile(r, floor, wall, rim, rim_height, apron, apron_height=0.15):
    """H1, the four-zone radial bowl (floor -1, plain 0): flat floor, shouldered wall, rim crest, decaying apron.
    Returns NS(v, dvdr, zFloor, zWall, zOut, dzFloor, dzWall, dzOut, zApron, dzApron, zRim, dzRim)."""
    f0 = clamp(floor, EPS, 0.9)
    span = np.maximum(1.0 - f0, EPS)
    w_band = span * clamp(wall, 0.1, 1.0)
    sh = sstep(1.0 - w_band, 1.0, r)
    v = sh.v - 1.0
    dv = sh.d
    rw = np.maximum(rim, EPS)
    off = r - 1.0
    band = sstep(0.0, rw, np.abs(off))
    v = v + (1.0 - band.v) * rim_height
    dv = dv - band.d * np.sign(off) * rim_height
    ap = np.maximum(apron, EPS)
    inner = sstep(-rw, 0.0, off)
    outer = sstep(0.0, ap, off)
    z_apron = np.where(off > 0, 1.0 - outer.v, inner.v)
    dz_apron = np.where(off > 0, -outer.d, inner.d)
    v = v + z_apron * apron_height
    dv = dv + dz_apron * apron_height
    z_wall = sh.v * (1.0 - sh.v) * 4.0
    return NS(v=v, dvdr=dv, zFloor=1.0 - sh.v, zWall=z_wall, zOut=sh.v, dzFloor=-sh.d,
              dzWall=sh.d * (1.0 - sh.v * 2.0) * 4.0, dzOut=sh.d, zApron=z_apron, dzApron=dz_apron,
              zRim=1.0 - band.v, dzRim=-(band.d * np.sign(off)))


def fan_profile(r, concavity, apex_slope, toe):
    """H6, the concave-up radial decay of a depositional apron; NS(v, dvdr)."""
    k = np.maximum(concavity, 1e-3)
    tt = np.maximum(toe, EPS)
    rn = clamp(r / tt, 0.0, 1.0)
    e = np.exp(-(k * rn))
    end = np.exp(-k)
    raw = apex_slope * tt / k * (e - end)
    draw = -apex_slope * e
    toe_ease = sstep(0.8, 1.0, rn)
    gate = 1.0 - toe_ease.v
    return NS(v=raw * gate, dvdr=draw * gate - raw * toe_ease.d / tt)


def bench_stack(s, treads, jitter=0, convexity=0.5, seed=0):
    """H5, a staircase of near-level treads keyed to an arbitrary scalar (monotone by construction).
    Returns NS(v, d, tread, riser, index, fr)."""
    n = max(0, js_round(treads or 0))
    if n <= 0:
        return NS(v=s, d=1.0, tread=1.0, riser=0.0, index=0.0, fr=0.0)
    x = s * n
    i = np.floor(x)
    fr = fract(x)
    jx, _ = hash2(i, np.full_like(np.asarray(i, dtype=np.float64), float(seed_shift(seed)[0])), 0.0, 0.0)
    j = jx * 0.5 + 0.5
    cv = clamp(convexity, 0.0, 1.0) * lerp(1.0, j, clamp(jitter, 0.0, 1.0))
    e = lerp(0.92, 0.4, cv)
    b = np.maximum(fr, EPS)
    d = e * np.power(b, e - 1.0)
    return NS(v=(i + np.power(b, e)) / n, d=d, tread=clamp(1.0 - d, 0.0, 1.0), riser=clamp(d - 1.0, 0.0, 1.0),
              index=i, fr=fr)


def breach(d, dir_deg, width):
    """H2, a differentiable angular window (1 on azimuth dir_deg, 0 beyond `width` degrees); NS(w, dwdp)."""
    a = (float(dir_deg) if dir_deg else 0.0) * math.pi / 180.0
    dirv = Vec(math.cos(a), math.sin(a))
    ln = np.maximum(length(d), 1e-6)
    n = d / ln
    c = dot(n, dirv)
    half = clamp(width, 0.0, 179.0) * (math.pi / 180.0)
    e0 = np.cos(half)
    sh = sstep(e0, 1.0, c)
    dcdp = (dirv - n * c) / ln
    return NS(w=sh.v, dwdp=dcdp * sh.d)


def angular_wave(d, harmonic, phase=0.0):
    """Integer angular harmonic with an exact Cartesian gradient; NS(v, g)."""
    r2 = np.maximum(dot(d, d), EPS)
    a = np.arctan2(d.y, d.x) * harmonic + phase
    return NS(v=np.sin(a), g=Vec(-d.y, d.x) / r2 * (np.cos(a) * harmonic))


def axis_frame(ctx, direction=0, bends=2, sinuosity=0.35, seed=0, amp=0.18, amp2=0.05):
    """H3, the along/across frame with a sinuous centreline and its exact derivative.
    Returns NS(along, across, u, q, w, dw, c, dcdu)."""
    sa, sb = seed_shift(seed)
    ax, ay = snap_axis(direction)
    along = Vec(float(ax), float(ay))
    across = Vec(float(-ay), float(ax))
    ta = max(abs(ax) * ctx.tile.x + abs(ay) * ctx.tile.y, EPS)
    tc = max(abs(ay) * ctx.tile.x + abs(ax) * ctx.tile.y, EPS)
    u = dot(ctx.p, along) / ta
    q = dot(ctx.p, across) / tc
    k1 = max(1, js_round(bends))
    k2 = k1 * 2 + 1
    ph1 = (sa % 360) * math.pi / 180.0
    ph2 = (sb % 360) * math.pi / 180.0
    a1 = sinuosity * amp
    a2 = sinuosity * amp2
    s1 = u * (TAU * k1) + ph1
    s2 = u * (TAU * k2) + ph2
    c = 0.5 + np.sin(s1) * a1 + np.sin(s2) * a2
    dcdu = np.cos(s1) * a1 * (TAU * k1) + np.cos(s2) * a2 * (TAU * k2)
    dq = q - c
    w = dq - np.floor(dq + 0.5)
    dw = across / tc - along * (dcdu / ta)
    return NS(along=along, across=across, u=u, q=q, w=w, dw=dw, c=c, dcdu=dcdu)


def axial_ridged_field(fr, du, along_frequency, across_frequency, octaves=4, gain=0.5, offset=(0, 0)):
    """Ridged noise in an axis frame, with more cells along strike than across it; NS(v, g)."""
    h = g = None
    fa = max(1, js_round(along_frequency))
    fc = max(1, js_round(across_frequency))
    na, norm = 1.0, 0.0
    for _ in range(int(octaves)):
        nv, nx, ny = noised(fr.u * fa + offset[0], fr.w * fc + offset[1], float(fa), float(fc))
        term = (1.0 - np.abs(nv)) * na
        dq = du * (nx * fa) + fr.dw * (ny * fc)
        dg = dq * (-np.sign(nv)) * na
        h = term if h is None else h + term
        g = dg if g is None else g + dg
        norm += na
        na *= gain
        fa *= 2
        fc *= 2
    return NS(v=h / norm, g=g / norm)


def warp_jac(ctx, frequency, octaves=2, strength=0.0, offset=(0, 0)):
    """A noise position warp together with its Jacobian: NS(q, pull) where pull(gq) takes a gradient measured in
    warped space back to position space."""
    q0 = ctx.p + Vec(offset[0], offset[1])
    a = fractal_noise(q0, frequency, octaves, 2, 0.5, ctx.tile)
    b = fractal_noise(q0 + Vec(31.0 / frequency, 17.0 / frequency), frequency, octaves, 2, 0.5, ctx.tile)
    s = strength

    def pull(gq):
        return Vec(gq.x * (s * a.y + 1.0) + gq.y * (s * b.y), gq.x * (s * a.z) + gq.y * (s * b.z + 1.0))

    return NS(q=q0 + Vec(a.x, b.x) * s, pull=pull)


# ---------------------------------------------------------------------------------------------- blend modes ---

def blend_pair(mode, A, B):
    """The raw result R(A, B) of a Combine blend mode plus both partials: NS(h, dA, dB)."""
    E = EPS
    if mode == 'blend':
        return NS(h=B, dA=0.0, dB=1.0)
    if mode == 'screen':
        return NS(h=1.0 - (1.0 - A) * (1.0 - B), dA=1.0 - B, dB=1.0 - A)
    if mode == 'subtract':
        return NS(h=A - B, dA=1.0, dB=-1.0)
    if mode == 'difference':
        s = np.sign(A - B)
        return NS(h=np.abs(A - B), dA=s, dB=-s)
    if mode == 'multiply':
        return NS(h=A * B, dA=B, dB=A)
    if mode == 'divide':
        d = np.maximum(B, E)
        return NS(h=A / d, dA=1.0 / d, dB=-(A / (d * d)))
    if mode == 'divide2':
        d = np.maximum(B + 1.0, E)
        return NS(h=A / d, dA=1.0 / d, dB=-(A / (d * d)))
    if mode == 'max':
        t = step01(B > A)
        return NS(h=np.maximum(A, B), dA=1.0 - t, dB=t)
    if mode == 'min':
        t = step01(B < A)
        return NS(h=np.minimum(A, B), dA=1.0 - t, dB=t)
    if mode == 'hypotenuse':
        r = np.maximum(np.sqrt(A * A + B * B), E)
        return NS(h=r, dA=A / r, dB=B / r)
    if mode in ('overlay', 'hardLight'):
        lo = (A < 0.5) if mode == 'overlay' else (B < 0.5)
        return NS(h=np.where(lo, A * B * 2.0, 1.0 - (1.0 - A) * (1.0 - B) * 2.0),
                  dA=np.where(lo, B * 2.0, (1.0 - B) * 2.0), dB=np.where(lo, A * 2.0, (1.0 - A) * 2.0))
    if mode == 'power':
        a = np.maximum(A, E)
        h = np.power(a, B)
        return NS(h=h, dA=B * np.power(a, B - 1.0), dB=h * np.log(a))
    if mode == 'exclusion':
        return NS(h=A + B - A * B * 2.0, dA=1.0 - B * 2.0, dB=1.0 - A * 2.0)
    if mode == 'dodge':
        d = np.maximum(1.0 - B, E)
        return NS(h=A / d, dA=1.0 / d, dB=A / (d * d))
    if mode == 'burn':
        d = np.maximum(B, E)
        return NS(h=1.0 - (1.0 - A) / d, dA=1.0 / d, dB=(1.0 - A) / (d * d))
    if mode == 'softLight':
        return NS(h=(1.0 - B * 2.0) * A * A + A * B * 2.0, dA=A * 2.0 * (1.0 - B * 2.0) + B * 2.0,
                  dB=A * A * -2.0 + A * 2.0)
    if mode == 'pinLight':
        lo = B < 0.5
        two_b = B * 2.0
        two_bm = B * 2.0 - 1.0
        w = np.where(lo, step01(two_b < A), step01(two_bm > A))
        return NS(h=np.where(lo, np.minimum(A, two_b), np.maximum(A, two_bm)), dA=1.0 - w, dB=w * 2.0)
    if mode == 'grainMerge':
        return NS(h=A + B - 0.5, dA=1.0, dB=1.0)
    if mode == 'grainExtract':
        return NS(h=A - B + 0.5, dA=1.0, dB=-1.0)
    if mode == 'reflect':
        d = np.maximum(1.0 - B, E)
        return NS(h=A * A / d, dA=A * 2.0 / d, dB=A * A / (d * d))
    if mode == 'glow':
        d = np.maximum(1.0 - A, E)
        return NS(h=B * B / d, dA=B * B / (d * d), dB=B * 2.0 / d)
    if mode == 'phoenix':
        t = step01(B > A)
        return NS(h=A - B + np.maximum(A, B), dA=1.0 + (1.0 - t), dB=t - 1.0)
    return NS(h=A + B, dA=1.0, dB=1.0)          # add (and the default)


def blend_field(a, b, mode, k):
    """Blend field b onto field a at ratio k: the ratio interpolates the base toward the mode's result."""
    r = blend_pair(mode, a.x, b.x)
    wa = (1.0 - k) + k * r.dA
    return field(mix(a.x, r.h, k), G(a) * wa + G(b) * (k * r.dB), AUX(b))
