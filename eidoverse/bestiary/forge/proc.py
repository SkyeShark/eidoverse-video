"""The TEXTURE TIER's vocabulary (research/SD_SKIN_BRIEF.md): procedural point functions as Warp @wp.func, evaluated
per texel at the texel's ANATOMICAL coordinate (mm) during the material pass, and the same functions place the sculpt
tier's instances (a papilla sits on the skin patch whose site it is), so the two tiers agree by construction.

SOLID (3D) functions rather than SD's 2D canvases: a texel's coordinate is its point on the high (the head set) or its
straightened, radius-normalised arm coordinate (the arms set), so there are no canvas seams or poles; SD's
neighbourhood filters on procedural inputs become point functions with more evaluations (warps, slope blur), and the
generators EMIT INSTANCE DATA (cell id, site, local offset), so no flood fill is needed (brief §0.3).

One integer hash everywhere (lowbias32, brief §1.4): the bake, the sculpt and a later TSL port agree to the bit.
"""
import warp as wp


@wp.func
def lowbias32(x: wp.uint32):
    x = x ^ (x >> wp.uint32(16))
    x = x * wp.uint32(0x7FEB352D)
    x = x ^ (x >> wp.uint32(15))
    x = x * wp.uint32(0x846CA68B)
    x = x ^ (x >> wp.uint32(16))
    return x


@wp.func
def hash3i(i: int, j: int, k: int, seed: int):
    h = lowbias32(wp.uint32(seed) ^ wp.uint32(0x9E3779B9))
    h = lowbias32(h ^ wp.uint32(i))
    h = lowbias32(h ^ wp.uint32(j))
    return lowbias32(h ^ wp.uint32(k))


@wp.func
def u01(h: wp.uint32):
    """[0, 1) from the top 24 bits"""
    return float(h >> wp.uint32(8)) * (1.0 / 16777216.0)


@wp.func
def rnd3(h: wp.uint32):
    a = lowbias32(h ^ wp.uint32(0x68E31DA4))
    b = lowbias32(a ^ wp.uint32(0xB5297A4D))
    c = lowbias32(b ^ wp.uint32(0x1B56C4E9))
    return wp.vec3(u01(a), u01(b), u01(c))


@wp.func
def fade(t: float):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


@wp.func
def grad_dot(h: wp.uint32, d: wp.vec3):
    # one of 12 cube-edge gradients (Perlin's improved set)
    g = int(h % wp.uint32(12))
    gx = float(0.0)
    gy = float(0.0)
    gz = float(0.0)
    if g < 4:
        gx = float(1 - 2 * (g & 1))
        gy = float(1 - (g & 2))
    elif g < 8:
        gx = float(1 - 2 * (g & 1))
        gz = float(1 - (g & 2))
    else:
        gy = float(1 - 2 * (g & 1))
        gz = float(1 - (g & 2))
    return gx * d[0] + gy * d[1] + gz * d[2]


@wp.func
def noise3(p: wp.vec3, seed: int):
    """gradient noise, about [-1, 1], unit lattice"""
    i = int(wp.floor(p[0]))
    j = int(wp.floor(p[1]))
    k = int(wp.floor(p[2]))
    f = wp.vec3(p[0] - float(i), p[1] - float(j), p[2] - float(k))
    u = fade(f[0])
    v = fade(f[1])
    w = fade(f[2])
    n000 = grad_dot(hash3i(i, j, k, seed), f)
    n100 = grad_dot(hash3i(i + 1, j, k, seed), f - wp.vec3(1.0, 0.0, 0.0))
    n010 = grad_dot(hash3i(i, j + 1, k, seed), f - wp.vec3(0.0, 1.0, 0.0))
    n110 = grad_dot(hash3i(i + 1, j + 1, k, seed), f - wp.vec3(1.0, 1.0, 0.0))
    n001 = grad_dot(hash3i(i, j, k + 1, seed), f - wp.vec3(0.0, 0.0, 1.0))
    n101 = grad_dot(hash3i(i + 1, j, k + 1, seed), f - wp.vec3(1.0, 0.0, 1.0))
    n011 = grad_dot(hash3i(i, j + 1, k + 1, seed), f - wp.vec3(0.0, 1.0, 1.0))
    n111 = grad_dot(hash3i(i + 1, j + 1, k + 1, seed), f - wp.vec3(1.0, 1.0, 1.0))
    x00 = n000 + u * (n100 - n000)
    x10 = n010 + u * (n110 - n010)
    x01 = n001 + u * (n101 - n001)
    x11 = n011 + u * (n111 - n011)
    y0 = x00 + v * (x10 - x00)
    y1 = x01 + v * (x11 - x01)
    return y0 + w * (y1 - y0)


@wp.func
def fbm3(p: wp.vec3, octaves: int, lacunarity: float, gain: float, seed: int):
    """sum of octaves, normalised to about [-1, 1]"""
    a = float(1.0)
    s = float(0.0)
    norm = float(0.0)
    q = p
    for o in range(octaves):
        s = s + a * noise3(q, seed + o * 131)
        norm = norm + a
        a = a * gain
        q = q * lacunarity
    return s / norm


@wp.func
def warp3(p: wp.vec3, scale: float, amp: float, seed: int):
    """domain warp: p displaced by a 3-channel fBm (scale = the warp's feature size, amp = its displacement)"""
    q = p / scale
    return p + wp.vec3(fbm3(q, 3, 2.0, 0.5, seed), fbm3(q + wp.vec3(17.3, 5.1, 9.7), 3, 2.0, 0.5, seed + 7),
                       fbm3(q + wp.vec3(3.9, 21.7, 13.1), 3, 2.0, 0.5, seed + 13)) * amp


@wp.struct
class Cell:
    f1: float            # distance to the nearest site (lattice units)
    f2: float            # to the second nearest
    edge: float          # the exact distance to the nearest site's cell boundary (Quilez): the groove driver
    site: wp.vec3        # the nearest site (lattice units)
    cell: wp.vec3i       # its lattice cell: the instance key
    rand: float          # its random in [0, 1)


@wp.func
def site_of(c: wp.vec3i, disorder: float, seed: int):
    h = hash3i(c[0], c[1], c[2], seed)
    r = rnd3(h)
    return wp.vec3(float(c[0]), float(c[1]), float(c[2])) + wp.vec3(0.5, 0.5, 0.5) + (r - wp.vec3(0.5, 0.5, 0.5)) * disorder


@wp.func
def cellular3(p: wp.vec3, disorder: float, seed: int):
    """jittered-grid Worley in 3D, unit lattice: F1, F2, the exact border distance and the nearest site's instance
    data. Disorder <= 1 keeps the 3^3 search exact for F1; the border pass searches 5^3 around the nearest cell"""
    ci = int(wp.floor(p[0]))
    cj = int(wp.floor(p[1]))
    ck = int(wp.floor(p[2]))
    f1 = float(1.0e9)
    f2 = float(1.0e9)
    best = wp.vec3i(0, 0, 0)
    bsite = wp.vec3(0.0)
    for a in range(-1, 2):
        for b in range(-1, 2):
            for c in range(-1, 2):
                cc = wp.vec3i(ci + a, cj + b, ck + c)
                s = site_of(cc, disorder, seed)
                d = wp.length(p - s)
                if d < f1:
                    f2 = f1
                    f1 = d
                    best = cc
                    bsite = s
                elif d < f2:
                    f2 = d
    edge = float(1.0e9)
    for a in range(-2, 3):
        for b in range(-2, 3):
            for c in range(-2, 3):
                cc = wp.vec3i(best[0] + a, best[1] + b, best[2] + c)
                if cc[0] == best[0] and cc[1] == best[1] and cc[2] == best[2]:
                    continue
                s = site_of(cc, disorder, seed)
                dv = s - bsite
                l = wp.length(dv)
                if l > 1.0e-6:
                    e = wp.dot(0.5 * (bsite + s) - p, dv / l)
                    edge = wp.min(edge, e)
    out = Cell()
    out.f1 = f1
    out.f2 = f2
    out.edge = edge
    out.site = bsite
    out.cell = best
    out.rand = u01(hash3i(best[0], best[1], best[2], seed + 977))
    return out


@wp.kernel
def k_cells(pts: wp.array(dtype=wp.vec3), inv_s: float, disorder: float, seed: int, cell: wp.array(dtype=wp.vec3i),
            site: wp.array(dtype=wp.vec3), edge: wp.array(dtype=wp.float32)):
    t = wp.tid()
    c = cellular3(pts[t] * inv_s, disorder, seed)
    cell[t] = c.cell
    site[t] = c.site / inv_s
    edge[t] = c.edge / inv_s


def cells(points, spacing, disorder, seed):
    """the patch network at points (the coordinate's units): each point's nearest site's lattice cell (the instance
    key), the site (same units) and the distance to its cell's border"""
    import numpy as np
    P = np.asarray(points, np.float32).reshape(-1, 3)
    n = len(P)
    cell = wp.zeros(n, dtype=wp.vec3i)
    site = wp.zeros(n, dtype=wp.vec3)
    edge = wp.zeros(n, dtype=wp.float32)
    wp.launch(k_cells, dim=n, inputs=[wp.array(P, dtype=wp.vec3), float(1.0 / spacing), float(disorder), int(seed),
                                      cell, site, edge])
    return cell.numpy(), site.numpy().astype(np.float64), edge.numpy()


@wp.func
def smoothstep(a: float, b: float, x: float):
    t = wp.clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@wp.func
def histogram_scan(x: float, position: float, contrast: float):
    """SD's Histogram Scan [recon, brief §3.3]: a levels window of width (1 - contrast) sliding with position"""
    w = wp.max(1.0 - contrast, 1.0e-4)
    lo = (1.0 - position) * (1.0 + w) - w
    return wp.clamp((x - lo) / w, 0.0, 1.0)
