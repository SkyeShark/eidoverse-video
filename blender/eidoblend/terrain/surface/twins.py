"""The surface bake's kernels and their numpy twins (SURFACING_DESIGN.md 2.3): each kernel in surface/kernels/ has a
twin here that does its arithmetic in float32 numpy. The twins are the test oracle (parity on a 96 x 80 field within
1e-4 of each output's range, blender/tests/terrain/surface_data/test_kernels.py) and the bake's `backend='numpy'`
path for small grids in plain Python; production runs the kernels on the GPU.

    from eidoblend.terrain.surface import twins as TW
    k = TW.inline('blur')                    # the kernel as solvers.fluvial.Inline: a device runs it, on the GPU
                                             # (FL.device('gpu')) or through its twin (FL.device('twin'))
    TW.source('phacelle')                    # its GLSL text, core/world_noise.GLSL_NOISE put in its place
    TW.KERNELS                               # every kernel name

The kernels load through core/gpu.kernel with common.glsl prefixed, as every terrain kernel does; their twins
register with core/twins by the name 'surface_<kernel>'. The gully filter's twin calls solvers/detail.py's
phacelle_noise itself, the settle's and the snowpack's twin is detail.relax(backend='numpy'), upsample2's is
core/grid.py's crop_upsample2. No bpy.
"""
from __future__ import annotations

import math
import os

import numpy as np

from ..core import grid as Gd
from ..core import twins as T
from ..core import world_noise as N

F = np.float32
TAU = 6.28318530717959
HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_DIR = os.path.join(HERE, 'kernels')
PREFIX = 'surface_'
KERNELS = ('blur', 'upsample2', 'field_normal', 'crest', 'phacelle', 'cavity', 'carry_src', 'streak', 'fill',
           'pin_inflow', 'route_colour')
UPSAMPLE_KINDS = {'catmull': 0, 'bilinear': 1, 'nearest': 2}
_SRC = {}
_INLINE = {}


def source(name):
    """A kernel's GLSL text (surface/kernels/<name>.glsl), with core/world_noise.GLSL_NOISE where it is marked."""
    if name not in _SRC:
        with open(os.path.join(KERNEL_DIR, name + '.glsl'), encoding='utf-8') as f:
            _SRC[name] = f.read().replace('/*__WORLD_NOISE__*/', N.GLSL_NOISE)
    return _SRC[name]


def inline(name):
    """The kernel as a solvers.fluvial.Inline (name 'surface_<name>', its source): what a device's run() takes."""
    if name not in _INLINE:
        from ..solvers import fluvial as FL
        _INLINE[name] = FL.Inline(PREFIX + name, source(name))
    return _INLINE[name]


# ------------------------------------------------------------------------------------------------ helpers ---

def smoothstep(e0, e1, x):
    """GLSL smoothstep in float32."""
    t = np.clip((np.asarray(x, F) - F(e0)) / F(e1 - e0), F(0), F(1))
    return (t * t * (F(3) - F(2) * t)).astype(F)


def cdiff(a, k):
    """(d/dx, d/dy) of a 2D array by central differences times k, indices clamped at the edges (the kernels' grad)."""
    h, w = a.shape
    ie, iw = np.minimum(np.arange(w) + 1, w - 1), np.maximum(np.arange(w) - 1, 0)
    jn, js = np.minimum(np.arange(h) + 1, h - 1), np.maximum(np.arange(h) - 1, 0)
    return ((a[:, ie] - a[:, iw]) * F(k)).astype(F), ((a[jn, :] - a[js, :]) * F(k)).astype(F)


def cell_at(a, shape_d, f):
    """A cell-grid array (H, W[, C]) at the texels of a detail grid of f texels per cell: itself at f = 1, bilinear
    (indices clamped) at f = 2: phacelle.glsl's cell_at."""
    a = np.asarray(a, F)
    if int(f) == 1:
        return a
    h, w = a.shape[:2]

    def taps(nd, n):
        c = (np.arange(nd, dtype=F) + F(0.5)) / F(f) - F(0.5)
        fl = np.floor(c)
        i = fl.astype(np.int64)
        return np.clip(i, 0, n - 1), np.clip(i + 1, 0, n - 1), (c - fl).astype(F)
    j0, j1, ty = taps(shape_d[0], h)
    i0, i1, tx = taps(shape_d[1], w)
    if a.ndim == 3:
        tx, ty = tx[None, :, None], ty[:, None, None]
    else:
        tx, ty = tx[None, :], ty[:, None]
    top = a[j0][:, i0] * (F(1) - tx) + a[j0][:, i1] * tx
    bot = a[j1][:, i0] * (F(1) - tx) + a[j1][:, i1] * tx
    return (top * (F(1) - ty) + bot * ty).astype(F)


def bilinear_at(a, px, py):
    """A 2D array at fractional texel positions (px, py), indices clamped: streak.glsl's exposure()."""
    h, w = a.shape
    fx, fy = np.floor(px), np.floor(py)
    tx, ty = (px - fx).astype(F), (py - fy).astype(F)
    i0, i1 = np.clip(fx.astype(np.int64), 0, w - 1), np.clip(fx.astype(np.int64) + 1, 0, w - 1)
    j0, j1 = np.clip(fy.astype(np.int64), 0, h - 1), np.clip(fy.astype(np.int64) + 1, 0, h - 1)
    top = a[j0, i0] * (F(1) - tx) + a[j0, i1] * tx
    bot = a[j1, i0] * (F(1) - tx) + a[j1, i1] * tx
    return (top * (F(1) - ty) + bot * ty).astype(F)


# -------------------------------------------------------------------------------------------------- twins ---

@T.twin(PREFIX + 'blur')
def blur(s, u):
    src = s['src']
    h, w = src.shape[:2]
    sig = np.asarray(u['uSigma'], F)
    dx, dy = (int(v) for v in u['uDir'])
    R = min(int(math.ceil(3.0 * float(sig.max()))), 96)
    with np.errstate(divide='ignore'):
        inv = np.where(sig > 0, F(0.5) / (sig * sig), F(1.0e30)).astype(F)
    acc = np.zeros((h, w, 4), F)
    ws = np.zeros(4, F)
    for i in range(-R, R + 1):
        jj = np.clip(np.arange(h) + i * dy, 0, h - 1)
        ii = np.clip(np.arange(w) + i * dx, 0, w - 1)
        v = src[jj][:, ii]
        if int(u['uFan']) == 1:
            v = np.repeat(v[..., :1], 4, axis=2)
        with np.errstate(over='ignore'):
            wt = np.exp(-F(i * i) * inv).astype(F)
        acc += wt * v
        ws += wt
    return {'outB': (acc / ws).astype(F)}


@T.twin(PREFIX + 'upsample2')
def upsample2(s, u):
    src = s['src']
    i0, j0 = (int(v) for v in u['uOrigin'])
    cols, rows = (int(v) for v in u['uSize'])
    kind = {v: k for k, v in UPSAMPLE_KINDS.items()}[int(u['uKind'])]
    m, mj = (cols + 1) // 2, (rows + 1) // 2
    out = np.zeros((rows, cols, 4), F)
    for c in range(src.shape[2]):
        out[..., c] = Gd.crop_upsample2(src[..., c], i0, j0, m, kind, mj)[:rows, :cols]
    return {'outU': out}


@T.twin(PREFIX + 'field_normal')
def field_normal(s, u):
    h = s['hT'][..., 0]
    hx, hy = cdiff(h, 0.5 / float(u['uTexel']))
    return {'outG': T.rgba(h, hx, hy, np.sqrt(hx * hx + hy * hy))}


@T.twin(PREFIX + 'crest')
def crest(s, u):
    h = s['hT'][..., 0]
    a, b = s['pyrA'], s['pyrB']
    shape = h.shape
    has_parent = int(u['uHasParent']) == 1
    par = s['parT'] if has_parent else np.zeros(shape + (4,), F)
    cell = F(u['uCell'])
    k = 0.5 / float(cell)
    inv = F(1) / (F(u['uTau']) * cell)
    t16 = np.tanh((h - b[..., 0]) * inv * F(0.0625))
    S = (np.tanh((h - a[..., 0]) * inv) + np.tanh((h - a[..., 1]) * inv * F(0.5))
         + np.tanh((h - a[..., 2]) * inv * F(0.25)) + np.tanh((h - a[..., 3]) * inv * F(0.125)) + t16 + par[..., 0])
    cr = np.clip(S / F(u['uTerms']), F(-1), F(1)).astype(F)
    V = np.zeros(shape, F)
    V8 = np.zeros(shape, F)
    t_ref, s_ref = (F(v) for v in u['uValley'])
    for j in range(4):
        sig = F(1 << j) * cell
        if sig < F(u['uSmin']):
            continue
        gx, gy = cdiff(a[..., j], k)
        t = t_ref * np.power(s_ref / sig, F(0.63)).astype(F)
        r = np.sqrt(gx * gx + gy * gy) / t
        flat = F(1) / (F(1) + r * r * r * r)
        nxt = a[..., j + 1] if j < 3 else b[..., 0]
        v = (flat * smoothstep(-1.0, 1.0, (nxt - a[..., j]) / (t * sig))).astype(F)
        V = np.maximum(V, v)
        if j == 3:
            V8 = v
    valley = np.maximum(V, par[..., 1])
    n20x, n20y = par[..., 2], par[..., 3]
    if int(u['uN20Own']) == 1:
        gx, gy = cdiff(b[..., 1], k)
        L = np.sqrt(F(1) + gx * gx + gy * gy)
        n20x, n20y = -gx / L, -gy / L
    g2x, g2y = cdiff(a[..., 1], k)
    L = np.sqrt(g2x * g2x + g2y * g2y)
    ok = L > F(1.0e-12)
    Ls = np.where(ok, L, F(1))
    sx, sy = np.where(ok, -g2x / Ls, F(0)), np.where(ok, -g2y / Ls, F(0))
    ghx, ghy = cdiff(h, k)
    tan_s = np.sqrt(ghx * ghx + ghy * ghy)
    nl = np.sqrt(F(1) + tan_s * tan_s)
    wx, wy = (F(v) for v in u['uWind'])
    ex = np.maximum(F(0), -((-ghx / nl) * wx + (-ghy / nl) * wy)) * smoothstep(0.0, 0.4, cr)
    return {'outC': T.rgba(cr, valley, n20x, n20y),
            'outK': T.rgba(t16 + par[..., 0], np.maximum(par[..., 1], V8), sx, sy),
            'outX': T.rgba(ex, tan_s)}


@T.twin(PREFIX + 'phacelle')
def phacelle(s, u):
    from ..solvers import detail as DT
    hg = s['hgT']
    hd, wd = hg.shape[:2]
    f = int(u['uF'])
    texel = F(u['uTexel'])
    d = cell_at(s['steerT'], (hd, wd), f)[..., 2:4].astype(np.float64)
    L = np.hypot(d[..., 0], d[..., 1])
    ok = L > 1e-12
    Ls = np.where(ok, L, 1.0)
    dx, dy = np.where(ok, d[..., 0] / Ls, 0.0), np.where(ok, d[..., 1] / Ls, 0.0)
    jj, ii = np.mgrid[0:hd, 0:wd]
    lx = ((ii.astype(F) + F(0.5)) * texel).astype(F)
    ly = ((jj.astype(F) + F(0.5)) * texel).astype(F)
    octs = s['octT']
    relief = np.zeros((hd, wd))
    gx = np.zeros((hd, wd))
    gy = np.zeros((hd, wd))
    cn = np.zeros((hd, wd))
    cd = 0.0
    for o in range(int(u['uOct'])):
        A, B = octs[0, 2 * o], octs[0, 2 * o + 1]
        px = (A[2] + lx * B[0]).astype(F).astype(np.float64)        # the lattice coordinate as the kernel holds it
        py = (A[3] + ly * B[0]).astype(F).astype(np.float64)
        c, sn, sdx, sdy = DT.phacelle_noise(px, py, dx, dy, 1.0, 0.25, float(u['uNorm']), (int(A[0]), int(A[1])))
        ogx, ogy = -sn * sdx * float(B[0]), -sn * sdy * float(B[0])
        if B[2] > 0.5:
            relief += float(B[1]) * c
            gx += float(B[1]) * ogx
            gy += float(B[1]) * ogy
            k2 = float(B[1]) * float(B[0]) * float(B[0])
            cn += k2 * c
            cd += k2
        dx = dx + float(u['uSteer']) * ogx / (float(B[0]) * TAU)
        dy = dy + float(u['uSteer']) * ogy / (float(B[0]) * TAU)
        L = np.maximum(np.hypot(dx, dy), 1e-12)
        dx, dy = dx / L, dy / L
    slope = np.degrees(np.arctan(hg[..., 3].astype(np.float64)))
    cover = cell_at(s['coverT'], (hd, wd), f)[..., 0]
    cover_w = smoothstep(u['uCover'][0], u['uCover'][1], cover).astype(np.float64)
    rock = smoothstep(u['uRockDeg'][0], u['uRockDeg'][1], slope).astype(np.float64) * (1.0 - cover_w)
    sl = [float(v) for v in u['uSlope']]
    soil = (smoothstep(sl[0], sl[1], slope).astype(np.float64) * (1.0 - smoothstep(sl[2], sl[3], slope))
            * (1.0 - rock))
    rel = soil * relief
    grx, gry = soil * gx, soil * gy
    cr = soil * (cn / cd if cd > 0.0 else 0.0)
    if int(u['uRockOn']) == 1:
        D = s['rockT'][..., 3].astype(np.float64)
        ddx, ddy = cdiff(s['rockT'][..., 3], 0.5 / float(texel))
        ie, iw = np.minimum(np.arange(wd) + 1, wd - 1), np.maximum(np.arange(wd) - 1, 0)
        jn, js = np.minimum(np.arange(hd) + 1, hd - 1), np.maximum(np.arange(hd) - 1, 0)
        lap = D[:, ie] + D[:, iw] + D[jn, :] + D[js, :] - 4.0 * D
        nf = np.minimum(np.sqrt(1.0 + hg[..., 3].astype(np.float64) ** 2), float(u['uNormalCap']))
        rel = rel + rock * nf * D
        grx = grx + rock * nf * ddx
        gry = gry + rock * nf * ddy
        cr = cr + rock * np.clip(-lap / (4.0 * float(u['uRockRef'])), -1.0, 1.0)
    L2 = np.sqrt(1.0 + hg[..., 1].astype(np.float64) ** 2 + hg[..., 2].astype(np.float64) ** 2)
    return {'outD': T.rgba(-hg[..., 1] / L2, -hg[..., 2] / L2, grx, gry),
            'outR': T.rgba(rel, np.clip(cr, -1.0, 1.0), hg[..., 0] + float(u['uStrength']) * rel, soil - rock)}


@T.twin(PREFIX + 'cavity')
def cavity(s, u):
    z = s['zT'][..., 2]
    hd, wd = z.shape
    texel = F(u['uTexel'])
    acc = np.zeros((hd, wd), F)
    jj, ii = np.arange(hd), np.arange(wd)
    for k in range(16):
        a = F(TAU) * F(k) / F(16.0)
        ca, sa = np.cos(a, dtype=F), np.sin(a, dtype=F)
        best = np.zeros((hd, wd), F)
        r = 2
        while r <= 32:
            ox = int(math.floor(float(ca * F(r)) + 0.5))
            oy = int(math.floor(float(sa * F(r)) + 0.5))
            zq = z[np.clip(jj + oy, 0, hd - 1)][:, np.clip(ii + ox, 0, wd - 1)]
            best = np.maximum(best, (zq - z) / (F(math.hypot(ox, oy)) * texel))
            r *= 2
        acc += best / np.sqrt(F(1) + best * best)
    fine = F(0.5) * (np.tanh((z - s['blurT'][..., 2]) / (F(u['uTau']) * texel))
                     + np.tanh((z - s['blur2T'][..., 2]) / (F(u['uTau']) * F(2.0) * texel)))
    return {'outE': T.rgba(s['zT'][..., 1], F(1) - acc / F(16.0), fine)}


@T.twin(PREFIX + 'carry_src')
def carry_src(s, u):
    h = s['hT'][..., 0]
    aux, st = s['auxT'], s['stT']
    cell = F(u['uCell'])
    gx, gy = cdiff(h, 1.0)
    tan_s = np.sqrt(gx * gx + gy * gy) * (F(0.5) / cell)
    bare = (smoothstep(u['uRockDeg'][0], u['uRockDeg'][1], np.degrees(np.arctan(tan_s)).astype(F))
            * (F(1) - smoothstep(u['uCover'][0], u['uCover'][1], aux[..., 0])))
    S = np.zeros((8,) + h.shape, F)
    nbr = []
    for k in range(8):
        hq, ok = T.neighbour(h, k, T.BOUND_OPEN)
        sq, _ = T.neighbour(st, k, T.BOUND_OPEN)
        nbr.append(sq)
        S[k] = np.where(ok & (sq[..., 2] >= F(0.5)), np.maximum((hq - h) / T.LEN[k], F(0)), F(0))
    smax = S.max(axis=0)
    has = smax > F(0)
    r = S / np.where(has, smax, F(1))[None]
    W = (((r * r) * r) * r).astype(F)
    wsum = np.zeros(h.shape, F)
    for k in range(8):
        wsum = (wsum + W[k]).astype(F)
    jj, ii = np.mgrid[0:h.shape[0], 0:h.shape[1]]
    uu = (T.u01(T.pcg3(ii, jj, np.full_like(ii, int(u['uSalt'])))) * wsum).astype(F)
    acc = np.zeros(h.shape, F)
    kp = np.full(h.shape, -1, np.int64)
    done = np.zeros(h.shape, bool)
    for k in range(8):
        pos = W[k] > F(0)
        acc = np.where(pos, (acc + W[k]).astype(F), acc)
        kp = np.where(pos & ~done, k, kp)
        done |= pos & (uu < acc)
    src = aux[..., 1].copy()
    dist = np.full(h.shape, F(1.0e9))
    valid = np.zeros(h.shape, F)
    for k in range(8):
        take = has & (kp == k)
        src = np.where(take, nbr[k][..., 0], src)
        dist = np.where(take, nbr[k][..., 1] + T.LEN[k] * cell, dist)
        valid = np.where(take, F(1), valid)
    is_src = bare > F(0.5)
    src = np.where(is_src, aux[..., 1], src)
    dist = np.where(is_src, F(0), dist)
    valid = np.where(is_src, F(1), valid)
    out = T.rgba(src, dist, valid)
    pinned = aux[..., 2] > F(0.5)
    out[pinned] = st[pinned]
    return {'outS': out}


@T.twin(PREFIX + 'streak')
def streak(s, u):
    ex = s['exT'][..., 0]
    h, w = ex.shape
    wx, wy = (F(v) for v in u['uWind'])
    length = F(u['uLength'])
    R = min(int(math.ceil(3.0 * float(length))), 96)
    jj, ii = np.mgrid[0:h, 0:w].astype(F)
    acc = np.zeros((h, w), F)
    ws = F(0)
    for t in range(R + 1):
        wt = np.exp(-F(t) / length).astype(F)
        acc += wt * bilinear_at(ex, ii - F(t) * wx, jj - F(t) * wy)
        ws += wt
    return {'outS': (acc / ws)[..., None]}


@T.twin(PREFIX + 'fill')
def fill(s, u):
    W = s['wT'][..., 0]
    z, held = s['zT'][..., 0], s['zT'][..., 1] > F(0.5)
    eps = F(u['uEps'])
    lo = W.copy()
    for k in range(8):
        wq, ok = T.neighbour(W, k, T.BOUND_OPEN)
        with np.errstate(over='ignore'):
            lo = np.where(ok, np.minimum(lo, wq + eps * T.LEN[k]), lo)
    out = np.where(held, W, np.maximum(z, np.minimum(lo, z + F(u['uCap'])))).astype(F)
    return {'outW': out[..., None]}


def _shares(h, ws, u, k):
    """(up, share): where neighbour k is higher than the cell, and the share of its flow the cell receives:
    route_area's arithmetic."""
    from ..solvers.fluvial import wpow
    hq, ok = T.neighbour(h, k, u['uBound'])
    wq, _ = T.neighbour(ws, k, u['uBound'])
    up = ok & (hq > h)
    sl = np.where(up, (hq - h) / (T.LEN[k] * F(u['uDx'])), F(1))
    with np.errstate(over='ignore', invalid='ignore'):
        return up, (wpow(sl, u['uP']) / np.maximum(wq, F(1e-30))).astype(F)


@T.twin(PREFIX + 'pin_inflow')
def pin_inflow(s, u):
    h, ws = s['st'][..., 0], s['wsumT'][..., 0]
    tgt, pinned = s['tgtT'][..., 0], s['tgtT'][..., 1] > F(0.5)
    dx = F(u['uDx'])
    A = np.full(h.shape, dx * dx, F)
    for k in range(8):
        up, share = _shares(h, ws, u, k)
        tq, _ = T.neighbour(s['tgtT'], k, u['uBound'])
        take = up & (tq[..., 1] > F(0.5))
        with np.errstate(over='ignore', invalid='ignore'):
            A = np.where(take, A + tq[..., 0] * share, A)
    return {'outP': np.where(pinned, tgt - A, F(0)).astype(F)[..., None]}


@T.twin(PREFIX + 'route_colour')
def route_colour(s, u):
    h, ws = s['st'][..., 0], s['wsumT'][..., 0]
    q0 = s['qT']
    Q = s['srcT'].copy()
    for k in range(8):
        up, share = _shares(h, ws, u, k)
        qq, _ = T.neighbour(q0, k, u['uBound'])
        with np.errstate(over='ignore', invalid='ignore'):
            Q = np.where(up[..., None], Q + qq * share[..., None], Q)
    held = s['pinT'][..., 1] > F(0.5)
    Q[held] = q0[held]
    return {'outQ': Q.astype(F)}


__all__ = ['KERNELS', 'PREFIX', 'UPSAMPLE_KINDS', 'source', 'inline', 'smoothstep', 'cdiff', 'cell_at', 'bilinear_at']
