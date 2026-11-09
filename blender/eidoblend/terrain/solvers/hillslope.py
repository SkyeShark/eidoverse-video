"""Hillslopes on their own (design sections 4.1-4.2): creep and threshold failure, the passes the fluvial backbone
runs every step, as standalone stages.

    stage ops (OPS; op(fields, level, params, seed, ctx=None)):
      'creep'      age a surface. Linear diffusion by kappa_t_m2 (kappa t, m^2: cinder cones, craters; done
                   exactly as a Gaussian of sigma^2 = 2 kappa t), or nonlinear creep (Roering 1999) with D (m^2/yr)
                   for years, on the GPU (creep.glsl)
      'talus'      debris at repose: the threshold pass at repose_deg (default 35) on loose material only (h - bed),
                   so rock walls keep their own angle. On a level with no bed (a real DEM), the threshold is never
                   below the inherited surface's own slope, so only new detail relaxes and the landform stands
      'threshold'  slopes failing at their angle: the threshold pass at threshold_deg (or the level's Sc field, an
                   earlier stage's: karst's limestone 75 degrees), every cell

The kernels' twins are here: creep (kernels/creep.glsl) and threshold (kernels/threshold.glsl). Both exchange
material symmetrically between every neighbour pair, so the sum of h is conserved in the open and periodic modes
(test_hillslope.py checks it to 1e-5). Talus thickness accumulates in `talus` (the scree mask and the rock scatter
read it); losses take talus, then deposit, then other loose cover, then rock (`wear`).
"""
from __future__ import annotations

import math
import time

import numpy as np

from ..core import grid as Gd
from ..core import twins as T
from . import fluvial as FL

F32 = np.float32


# ================================================================================================ the twins ===

@T.twin('creep')
def creep(s, u):
    st, sc, pin = s['st'], s['par'][..., 2], s['pin']
    h = st[..., 0]
    acc = np.zeros_like(h)
    for k in range(8):
        hq, ok = T.neighbour(h, k, u['uBound'])
        sq, _ = T.neighbour(sc, k, u['uBound'], fill=1.0)
        scp = F32(0.5) * (sc + sq)
        r = ((hq - h) / (T.LEN[k] * u['uDx'])) / scp
        f = np.minimum(F32(1) / np.maximum(F32(1) - r * r, F32(1e-9)), u['uCap'])
        acc = acc + np.where(ok, T.WISO[k] * f * (hq - h), F32(0))
    hn = h + u['uDtSub'] * u['uD'] * acc / (u['uDx'] * u['uDx'])
    if u['uBound'] == T.BOUND_PINNED:
        hn = T.pin_apply(hn, pin[..., 0], pin[..., 1])
    return {'outS': T.rgba(hn, st[..., 1], st[..., 2], st[..., 3])}


# The isotropic threshold's first pass, once per iteration: every cell's excess over its threshold (threshold.glsl
# reads it for the cell and its 8 neighbours; computing it there for all nine cost 55 fetches a cell, 3 ms a step at
# 1024^2).
EXCESS = FL.Inline('threshold_excess', r'''//! sampler st     x: h (m)
//! sampler par    z: Sc, the threshold slope's tangent
//! image   outP r32f   x: phi = max(1 - Sc / G, 0), G the upwind (Rouy-Tourin) gradient magnitude
//! uniform float uDx
//! uniform int uBound
float axis_h(ivec2 p, int k, ivec2 n, float h) {
  ivec2 q;
  return neighbour(p, k, n, uBound, q) ? texelFetch(st, q, 0).x : h;
}
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(st, p, 0).x;
  float gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  float gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  float g = sqrt(gx * gx + gy * gy) / uDx;
  float sc = texelFetch(par, p, 0).z;
  imageStore(outP, p, vec4(g > sc ? 1.0 - sc / g : 0.0, 0.0, 0.0, 0.0));
}
''')


def upwind_excess(h, sc, dx, bound):
    """threshold_excess's twin: phi = max(1 - Sc / G, 0), G the upwind (Rouy-Tourin) gradient magnitude."""
    def ax(k):
        v, ok = T.neighbour(h, k, bound)
        return np.where(ok, v, h)
    gx = np.maximum(h - np.minimum(ax(3), ax(4)), F32(0))
    gy = np.maximum(h - np.minimum(ax(1), ax(6)), F32(0))
    g = np.sqrt(gx * gx + gy * gy) / dx
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(g > sc, F32(1) - sc / np.where(g > 0, g, F32(1)), F32(0)).astype(F32)


@T.twin('threshold_excess')
def threshold_excess(s, u):
    return {'outP': upwind_excess(s['st'][..., 0], s['par'][..., 2], u['uDx'], u['uBound'])[..., None]}


@T.twin('threshold')
def threshold(s, u):
    st, sc, pin, mk = s['st'], s['par'][..., 2], s['pin'], s['mk']
    h = st[..., 0]
    loose = mk[..., 3]
    dh = np.zeros_like(h)
    iso = u.get('uIso', 0) == 1
    ph = s['phiT'][..., 0] if iso else None
    for k in range(8):
        hq, ok = T.neighbour(h, k, u['uBound'])
        lq, _ = T.neighbour(loose, k, u['uBound'])
        if iso:
            pq, _ = T.neighbour(ph, k, u['uBound'])
            x = u['uRate'] * T.WISO[k] * ((h - hq) * (F32(0.5) * (ph + pq)))
        else:
            sq, _ = T.neighbour(sc, k, u['uBound'], fill=1.0)
            t = F32(0.5) * (sc + sq) * T.LEN[k] * u['uDx']
            e = u['uRate'] * np.maximum(np.abs(h - hq) - t, F32(0))
            x = np.where(h > hq, e, -e)
        if u['uLoose'] == 1:
            giver = np.where(h > hq, loose, lq)
            x = np.sign(x) * np.minimum(np.abs(x), F32(0.125) * np.maximum(giver, F32(0)))
        dh = dh - np.where(ok, x, F32(0))
    tal, dep, wear = mk[..., 2].copy(), mk[..., 1].copy(), mk[..., 0].copy()
    gain = dh >= 0
    other = np.maximum(loose - dep - tal, F32(0))
    r = np.where(gain, F32(0), -dh)
    a = np.minimum(r, tal)
    tal2 = tal - a
    r = r - a
    a = np.minimum(r, dep)
    dep2 = dep - a
    r = r - a
    r = r - np.minimum(r, other)
    tal = np.where(gain, tal + dh, tal2)
    dep = np.where(gain, dep, dep2)
    wear = np.where(gain, wear, wear + r)
    hn = h + dh
    mo = T.rgba(wear, dep, tal, np.maximum(loose + dh, F32(0)))
    if u['uBound'] == T.BOUND_PINNED:
        hp = T.pin_apply(hn, pin[..., 0], pin[..., 1])
        mo = FL.pin_layers(mo, hp - hn)                          # the pin's pull, counted in the layers
        hn = hp
    return {'outS': T.rgba(hn, st[..., 1], st[..., 2], st[..., 3]), 'outM': mo}


# ================================================================================================== helpers ===

class _Pass:
    """The state of a standalone hillslope stage on a device: h and the accumulators, the threshold field, pins."""

    def __init__(self, dev, fields, Sc, pins):
        h = np.asarray(fields['h'], F32)
        z = np.zeros_like(h)
        loose = np.maximum(h - np.asarray(fields['bed'], F32), 0) if 'bed' in fields else z
        self.dev = dev
        self.S = FL.Pair(dev, T.rgba(h, fields.get('A', z), fields.get('qs', z), z))
        self.M = FL.Pair(dev, T.rgba(fields.get('wear', z), fields.get('deposit', z), fields.get('talus', z), loose))
        self.P = dev.texture(T.rgba(None, None, np.asarray(Sc, F32), None) if Sc is not None else T.rgba(z, z, z + 1))
        self.Q = dev.texture(T.rgba(pins['pin_w'], pins['pin_h'], pins['A_in'], pins['qs_in']))

    def threshold(self, cell, rate, loose_only, bound, iso=1):
        self._phi = threshold_pass(self.dev, self.S, self.M, self.P, self.Q, cell, rate, loose_only, bound, iso,
                                   getattr(self, '_phi', None))

    def creep(self, cell, dt_sub, D, cap, bound):
        self.dev.run('creep', {'st': self.S.src, 'par': self.P, 'pin': self.Q}, {'outS': self.S.dst},
                     {'uDx': cell, 'uDtSub': dt_sub, 'uD': D, 'uCap': cap, 'uBound': bound})
        self.S.swap()

    def write(self, fields, had_bed):
        s = self.dev.read(self.S.src)
        mk = self.dev.read(self.M.src)
        fields['h'] = s[..., 0]
        fields['wear'] = mk[..., 0]
        fields['deposit'] = mk[..., 1]
        fields['talus'] = mk[..., 2]
        if had_bed:
            fields['bed'] = s[..., 0] - mk[..., 3]


def threshold_pass(dev, S, M, P, Q, cell, rate, loose_only, bound, iso=1, phi=None):
    """One threshold iteration on a device: (isotropic) the excess pass into `phi` (made when None), then the
    exchange; S and M are ping-pong pairs, swapped. Returns the phi texture for the next call."""
    if iso:
        if phi is None or (phi.height, phi.width) != (S.src.height, S.src.width):
            phi = dev.empty((S.src.height, S.src.width), 1)
        dev.run(EXCESS, {'st': S.src, 'par': P}, {'outP': phi}, {'uDx': cell, 'uBound': bound})
        phis = phi
    else:
        phis = phi if phi is not None else FL.dummy(dev)
    dev.run('threshold', {'st': S.src, 'par': P, 'pin': Q, 'mk': M.src, 'phiT': phis},
            {'outS': S.dst, 'outM': M.dst},
            {'uDx': cell, 'uRate': rate, 'uLoose': 1 if loose_only else 0, 'uIso': int(iso), 'uBound': bound})
    S.swap()
    M.swap()
    return phis


def _pins(fields, level, ctx):
    if ctx is not None and ctx.pins is not None:
        return ctx.pins
    return FL.edge_pins(level.n, np.asarray(fields['h'], F32))


def gaussian_blur(a, sigma_cells):
    """A Gaussian blur of sigma_cells (FFT, the field padded by reflection 4 sigma each side)."""
    a = np.asarray(a, np.float64)
    if sigma_cells <= 1e-6:
        return a.copy()
    pad = int(math.ceil(4.0 * sigma_cells))
    p = np.pad(a, pad, mode='reflect')
    ny, nx = p.shape
    ky = np.fft.fftfreq(ny)[:, None]
    kx = np.fft.rfftfreq(nx)[None, :]
    g = np.exp(-2.0 * (math.pi * sigma_cells) ** 2 * (kx * kx + ky * ky))
    out = np.fft.irfft2(np.fft.rfft2(p) * g, s=p.shape)
    return out[pad:pad + a.shape[0], pad:pad + a.shape[1]]


# =================================================================================================== the ops ===

def op_creep(fields, level, params, seed=0, ctx=None):
    """Stage 'creep' (module doc). params: kappa_t_m2 (linear: kappa t in m^2), or D (m^2/yr) and years (nonlinear,
    with threshold_deg 35 and cap 5). The border band stays pinned to the parent."""
    pins = _pins(fields, level, ctx)
    h = np.asarray(fields['h'], np.float64)
    if params.get('kappa_t_m2') is not None:
        kt = float(params['kappa_t_m2'])
        sig = math.sqrt(2.0 * kt) / level.cell
        hb = gaussian_blur(h, sig)
        w = np.clip(pins['pin_w'], 0, 1)
        fields['h'] = (hb * (1.0 - w) + pins['pin_h'] * w).astype(F32)
        if 'bed' in fields:
            fields['bed'] = np.minimum(fields['bed'], fields['h'])
        return fields
    dev = (ctx.device if ctx is not None and ctx.device is not None else FL.device())
    D = float(params['D'])
    years = float(params['years'])
    cap = float(params.get('cap', 5.0))
    Sc = math.tan(math.radians(float(params.get('threshold_deg', 35.0))))
    run = _Pass(dev, fields, np.full(h.shape, Sc, F32), pins)
    dt_max = 0.9 * level.cell ** 2 / (3.4 * D * cap)
    n_sub = max(1, int(math.ceil(years / dt_max)))
    for _ in range(n_sub):
        run.creep(level.cell, years / n_sub, D, cap, FL.PINNED)
    run.write(fields, 'bed' in fields)
    return fields


def _talus_sc(fields, level, repose_deg, margin=1.1):
    """The talus stage's threshold field: tan(repose), and where there is no bed, never below the inherited
    surface's own slope (times margin)."""
    t = math.tan(math.radians(repose_deg))
    if 'bed' in fields:
        return np.full((level.n, level.n), t, F32), True
    gx, gy = Gd.gradient(np.asarray(fields['h'], np.float64), level.cell)
    return np.maximum(t, margin * np.hypot(gx, gy)).astype(F32), False


def op_talus(fields, level, params, seed=0, ctx=None):
    """Stage 'talus' (module doc). params: repose_deg (35), iterations (64), rate (0.12, the isotropic threshold)."""
    t0 = time.perf_counter()
    dev = (ctx.device if ctx is not None and ctx.device is not None else FL.device())
    Sc, loose = _talus_sc(fields, level, float(params.get('repose_deg', 35.0)))
    run = _Pass(dev, fields, Sc, _pins(fields, level, ctx))
    for _ in range(int(params.get('iterations', 64))):
        run.threshold(level.cell, float(params.get('rate', 0.12)), loose, FL.PINNED)
    run.write(fields, 'bed' in fields)
    if ctx is not None:
        ctx.log(f"[terrain.hillslope] talus at {params.get('repose_deg', 35.0)} deg on {level.n}^2 @ "
                f"{level.cell:.3g} m ({'loose only' if loose else 'new detail only'}), "
                f"{time.perf_counter() - t0:.2f} s")
    return fields


def op_threshold(fields, level, params, seed=0, ctx=None):
    """Stage 'threshold' (module doc). params: threshold_deg (or the level's Sc field), iterations (64), rate."""
    dev = (ctx.device if ctx is not None and ctx.device is not None else FL.device())
    if 'Sc' in fields and params.get('threshold_deg') is None:
        Sc = np.asarray(fields['Sc'], F32)
    else:
        Sc = np.full((level.n, level.n), math.tan(math.radians(float(params.get('threshold_deg', 35.0)))), F32)
    run = _Pass(dev, fields, Sc, _pins(fields, level, ctx))
    for _ in range(int(params.get('iterations', 64))):
        run.threshold(level.cell, float(params.get('rate', 0.12)), False, FL.PINNED)
    run.write(fields, 'bed' in fields)
    return fields


for _op in (op_creep, op_talus, op_threshold):
    _op.evolves = True                # run.py: runs on every coarse-to-fine pass of the coarsest level
OPS = {'creep': op_creep, 'talus': op_talus, 'threshold': op_threshold}
