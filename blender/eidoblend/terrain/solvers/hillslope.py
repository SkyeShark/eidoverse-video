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
      'soil_hills' soil-mantled hillslopes at steady state between the channels the level's erosion cut: linear
                   creep with uplift, div(D grad h) = -U, so every hill is a smooth convex dome (Culling's parabola),
                   with lee slopes steeper than stoss slopes when asked (aspect-dependent creep), and rill lines
                   cut along the channels on fine levels (op_soil_hills)

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


# ================================================================ soil hillslopes at steady state (inline) ===
# Linear creep with uplift at steady state, with the channels held: div(D grad h) = -U on the hillslopes. With D
# uniform the Laplacian is -U / D everywhere off the channels: parabolic, convex hills whose relief is
# (U / D) L^2 / 2 for channels 2 L apart (Culling 1960; the Palouse's and Gabilan Mesa's hills). The diffusivity can
# depend on which way a slope faces the wind: D (1 - a cos theta), theta between the pair's downslope direction and
# the wind's, so a lee slope (facing downwind) carries the same soil flux at a steeper gradient: the crest moves
# toward the lee channel and the lee face stands steeper and shorter. One damped Jacobi step of the 9-point
# isotropic stencil per dispatch; each pair's weight is computed alike from both cells (it depends only on which of
# the two is higher), so the operator is the divergence of a flux.

SOIL = FL.Inline('soil_jacobi', r'''//! sampler st     x: h (m)
//! sampler con    x: hold (1 on channels), y: the held height (m), z: pin_w, w: pin_h (the border band)
//! image   outS r32f
//! uniform float uDx      the cell, metres
//! uniform float uC       U / D (1/m): the steady Laplacian of h is -uC
//! uniform float uAsym    a: the pair's diffusivity is 1 - a cos(downslope direction, wind)
//! uniform vec2 uWind     the unit vector the wind blows toward (x east, y north)
//! uniform float uOmega   the Jacobi damping, 0..1
//! uniform int uBound
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(st, p, 0).x;
  float num = 0.0;
  float den = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float hq = texelFetch(st, q, 0).x;
    float dw = dot(vec2(OFF[k]), uWind) / LEN[k];          // c -> q along the wind
    float w = WISO[k] * (1.0 - uAsym * (h >= hq ? dw : -dw));
    num += w * hq;
    den += w;
  }
  float hj = den > 0.0 ? (num + uC * uDx * uDx) / den : h;
  vec4 c = texelFetch(con, p, 0);
  float hn = mix(h, hj, uOmega);
  hn = mix(hn, c.y, clamp(c.x, 0.0, 1.0));
  hn = pin_apply(hn, c.z, c.w);
  imageStore(outS, p, vec4(hn, 0.0, 0.0, 0.0));
}
''')


@T.twin('soil_jacobi')
def soil_jacobi(s, u):
    h = s['st'][..., 0]
    con = s['con']
    wind = np.asarray(u['uWind'], F32)
    num = np.zeros_like(h)
    den = np.zeros_like(h)
    for k in range(8):
        hq, ok = T.neighbour(h, k, u['uBound'])
        ox, oy = T.OFF[k]
        dw = F32((F32(ox) * wind[0] + F32(oy) * wind[1]) / T.LEN[k])
        w = T.WISO[k] * (F32(1) - F32(u['uAsym']) * np.where(h >= hq, dw, -dw))
        num = num + np.where(ok, w * hq, F32(0))
        den = den + np.where(ok, w, F32(0))
    with np.errstate(divide='ignore', invalid='ignore'):
        hj = np.where(den > 0, (num + F32(u['uC']) * F32(u['uDx']) * F32(u['uDx'])) / np.where(den > 0, den, F32(1)),
                      h)
    om = F32(u['uOmega'])
    hn = h * (F32(1) - om) + hj * om
    a = np.clip(con[..., 0], F32(0), F32(1))
    hn = hn * (F32(1) - a) + con[..., 1] * a
    hn = T.pin_apply(hn, con[..., 2], con[..., 3])
    return {'outS': hn.astype(F32)[..., None]}


SOIL_DEFAULTS = dict(relief_m=20.0, valley_spacing_m=300.0, context_spacing_factor=1.0, relief_scaling=1.0,
                     channel_frac=0.25, asymmetry=0.0, wind_from_deg=225.0, rill_depth_m=0.0, rill_max_cell_m=1.0,
                     rill_width_cells=1.2, rill_width_m=None, rill_growth_max=2.5, rise_cap=0.5, flow_exponent=4.0,
                     omega=0.9, coarse_levels=3, iter_scale=1.0, blend=1.0, seed_m=0.0, seed_max_cell_m=1.0,
                     head_soft=1.0, hold_deposit_m=None)


def smooth_min(a, b, k):
    """C1 smooth minimum, blend width k (metres)."""
    if k <= 0:
        return np.minimum(a, b)
    hh = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - hh * hh * k * 0.25


def _downstream(mask, rec, max_iter=4096):
    """mask grown down the receiver paths `rec` (hydro.flow_receivers: every path ends at an outlet) until every
    cell downstream of a masked cell is masked. Each pass extends every path by one cell; it stops when nothing
    changes (the gaps between channel segments are short)."""
    flat = np.asarray(mask, bool).ravel().copy()
    has = rec >= 0
    for _ in range(int(max_iter)):
        src = flat & has
        tgt = rec[src]
        new = ~flat[tgt]
        if not new.any():
            break
        flat[tgt[new]] = True
    return flat.reshape(np.shape(mask))


def soft_cap(r, cap):
    """r unchanged up to cap / 2, then easing (tanh, C1) to at most cap: monotone in r, so capping a rise never
    makes a hollow (a smooth minimum dips up to an eighth of the cap below both inputs where they cross: grooves
    along that contour, closed depressions a few centimetres deep on a meadow)."""
    r = np.asarray(r, np.float64)
    half = 0.5 * float(cap)
    return np.where(r <= half, r, half + half * np.tanh((r - half) / max(half, 1e-12)))


def soil_convexity(relief_m, spacing_m):
    """U / D (1/m) of parabolic hills relief_m high between channels spacing_m apart: relief = C (spacing / 2)^2 / 2."""
    return 8.0 * float(relief_m) / float(spacing_m) ** 2


def _block2(a, how):
    m0, m1 = a.shape[0] // 2, a.shape[1] // 2
    b = np.asarray(a, np.float64)[:2 * m0, :2 * m1].reshape(m0, 2, m1, 2)
    return b.max(axis=(1, 3)) if how == 'max' else b.mean(axis=(1, 3))


def soil_solve(dev, h0, hold_w, hold_h, pin_w, pin_h, cell, C, asym=0.0, wind=(1.0, 0.0), half_cells=20.0,
               omega=0.9, coarse_levels=3, iter_scale=1.0, bound=FL.PINNED):
    """The steady soil hillslope on a device: damped Jacobi (SOIL) coarse to fine. The held cells (hold_w 1) and the
    pins stay; every other cell relaxes toward div(D grad h) = -C. Coarser grids (2 x 2 block means; a coarse cell
    is held when any of its cells is, at their mean height) solve first, each upsampled into the next as its start:
    Jacobi needs about (distance to a held cell)^2 iterations, which the coarse grids cut by 4 per level.
    half_cells: the largest distance to a channel expected, in cells of the finest grid. Returns (h float64, the
    last iteration's largest change in metres, iterations)."""
    pyr = [(np.asarray(h0, np.float64), np.asarray(hold_w, np.float64), np.asarray(hold_h, np.float64),
            np.asarray(pin_w, np.float64), np.asarray(pin_h, np.float64), float(cell))]
    while len(pyr) <= coarse_levels and min(pyr[-1][0].shape) >= 128 and min(pyr[-1][0].shape) % 2 == 0:
        h, hw, hh, pw, ph, c = pyr[-1]
        hw2 = _block2(hw, 'max')
        num = _block2(hw * hh, 'mean')
        den = _block2(hw, 'mean')
        hh2 = np.where(den > 1e-9, num / np.maximum(den, 1e-12), _block2(h, 'mean'))
        pyr.append((_block2(h, 'mean'), hw2, hh2, _block2(pw, 'mean'), _block2(ph, 'mean'), 2.0 * c))
    total = 0
    cur = None
    change = 0.0
    for li in range(len(pyr) - 1, -1, -1):
        h, hw, hh, pw, ph, c = pyr[li]
        if cur is not None:
            up = np.repeat(np.repeat(cur, 2, 0), 2, 1)
            start = h.copy()
            start[:up.shape[0], :up.shape[1]] = up
            h = start
        L = max(half_cells * float(cell) / c, 1.0)
        its = int(np.clip((2.0 if li == len(pyr) - 1 else 0.6) * L * L * float(iter_scale), 40, 4000))
        S = FL.Pair(dev, h.astype(F32))
        con = dev.texture(T.rgba(hw, hh, pw, ph))
        u = {'uDx': c, 'uC': float(C), 'uAsym': float(asym), 'uWind': (float(wind[0]), float(wind[1])),
             'uOmega': float(omega), 'uBound': int(bound)}
        for _ in range(its - 1):
            dev.run(SOIL, {'st': S.src, 'con': con}, {'outS': S.dst}, u)
            S.swap()
        prev = dev.read(S.src)[..., 0].astype(np.float64)
        dev.run(SOIL, {'st': S.src, 'con': con}, {'outS': S.dst}, u)
        S.swap()
        cur = dev.read(S.src)[..., 0].astype(np.float64)
        change = float(np.max(np.abs(cur - prev)))
        total += its
    return cur, change, total


def op_soil_hills(fields, level, params, seed=0, ctx=None):
    """Stage 'soil_hills' (module doc): the level's hillslopes replaced by their steady soil-mantled form between the
    channels its erosion cut.

    params (metres, degrees):
      valley_spacing_m 300, context_spacing_factor 1   the channels' spacing on the main level, and its growth per
                                         context level (the fluvial stage's, so both see the same network)
      relief_m 20                        a hill's height over its channels at that spacing: the convexity
                                         U / D = 8 relief / spacing^2; on a level of another spacing, relief x
                                         (spacing ratio)^relief_scaling (1: self-similar, slopes alike at every scale)
      channel_frac 0.25                  channels: drainage area >= channel_frac spacing^2 (a first-order valley's
                                         head); they keep their height, everything between is solved
      flow_exponent 4                    the area for that test is routed with the slope weights to this power
                                         (concentrated flow), on the heights scaled so the steeper slopes are about
                                         1 (the weights are ratios, so the area is the same; unscaled, a gentle
                                         slope's power underflows float32 and the water is lost): the fluvial
                                         stage's dispersive area (power 1) spreads a swale's water over gentle smooth
                                         ground, and on the meadow's finest levels no cell gathered a swale's
                                         catchment
      asymmetry 0, wind_from_deg 225     lee slopes steeper: D (1 - a cos) by the angle between a slope's downslope
                                         direction and the wind's (blowing from wind_from_deg, compass)
      rill_depth_m 0, rill_max_cell_m 1  on levels with cells up to rill_max_cell_m, the channels cut as rills
                                         this deep (x (A / channel area)^0.25, at most x rill_growth_max 2.5),
                                         rounded over rill_width_cells (a Gaussian's sigma) or rill_width_m (the
                                         sigma in metres, the same rill on every level: at 1.5 cells of 0.16 m the
                                         meadow's rills were grooves with 40-degree walls, its slope p99 26)
      head_soft 1                        > 1: a channel's hold eases in along its head, from A = channel area /
                                         head_soft to channel area x head_soft (smoothstep in log A), instead of
                                         starting at full strength on one cell: a held cell alone in the solved
                                         slope is a point sink, and the steady solution drew a cone-shaped funnel
                                         round every channel head
      hold_deposit_m None                cells with at least this much deposit (the alluvial floors an earlier
                                         level's valley_floor laid) are held too: the solve domed a flat floor
      rise_cap 0.5                       the steady form rises at most rise_cap x the level's hill relief above the
                                         eroded surface (soft_cap: monotone, so it makes no hollows): where the
                                         rivers have not dissected the
                                         ground yet, the steady solution's height grows with the square of the
                                         distance to a channel, and an undissected upland would become one tall dome
      blend 1                            1: the steady form; less keeps some of the eroded form
      seed_m 0, seed_max_cell_m 1        on levels with cells up to seed_max_cell_m: an undulation seed_m high
                                         (world-space fbm at the level's spacing, 3 octaves; never in the pinned
                                         band) added before the channels are found, its hollows filled to their
                                         spills so every swale drains - the microrelief a near-level surface starts
                                         from (till hummocks, old dune swells), so a meadow the countryside left
                                         level still gathers its water into swales at the spacing
    The border band stays pinned to the parent; sea cells are held."""
    ctx = ctx or FL.standalone_context(fields, level)
    t0 = time.perf_counter()
    if params.get('enabled', True) is False:
        return fields
    p = dict(SOIL_DEFAULTS)
    p.update({k: v for k, v in (params or {}).items() if k in SOIL_DEFAULTS and v is not None})
    dev = ctx.device or FL.device()
    cell = float(level.cell)
    depth = ctx.depth
    sp0 = float(p['valley_spacing_m'])
    sp = FL.level_spacing({'valley_spacing_m': sp0, 'context_spacing_factor': p['context_spacing_factor']}, depth)
    sp = max(sp, FL.MIN_SPACING_CELLS * cell)
    relief = float(p['relief_m']) * (sp / sp0) ** float(p['relief_scaling'])
    C = soil_convexity(relief, sp)
    h = np.asarray(fields['h'], np.float64)
    pins = ctx.pins if ctx.pins is not None else FL.edge_pins(level.n, np.asarray(h, F32), ctx.sea_level)
    rill = float(p['rill_depth_m'])
    cuts = rill > 0 and cell <= float(p['rill_max_cell_m'])
    if cuts and 'rill_cut' in fields:
        # the parent's rills come out before this level cuts its own (rill_cut, inherited): held channel cells kept
        # the parent's rill depth and the new rill went in on top, three levels deep, as steps along the swales
        h = h + np.asarray(fields['rill_cut'], np.float64) * (1.0 - np.clip(pins['pin_w'], 0.0, 1.0))
    from . import hydro as HY
    seed_m = float(p['seed_m'])
    seeded = seed_m > 0 and cell <= float(p['seed_max_cell_m'])
    h_route = h
    hollow = None
    if seeded:
        nz = FL._field({'kind': 'fbm', 'wavelength_m': sp, 'octaves': 3, 'amp': 3.0}, level, int(seed) + 907, dev)
        free = 1.0 - np.clip(np.asarray(pins['pin_w'], np.float64), 0.0, 1.0)
        h_seed = h + seed_m * nz * free
        h = np.asarray(HY.fill_depressions(h_seed, sea_level=ctx.sea_level)[0], np.float64)
        hollow = (h - h_seed) > 1e-4
        h_route = np.asarray(HY.routing_surface(h, sea_level=ctx.sea_level), np.float64)
    pe = float(p['flow_exponent'])
    if pe > 1.0 or 'A' not in fields or seeded:
        gy, gx = np.gradient(h_route, cell)
        lam = 1.0 / max(float(np.percentile(np.hypot(gx, gy), 90)), 1e-4)
        A, _ = HY.route_to_convergence(dev, ((h_route - float(h_route.min())) * lam).astype(F32), cell,
                                       A_in=pins['A_in'], p=max(pe, 1.0))
        A = np.asarray(A, np.float64)
    else:
        A = np.asarray(fields['A'], np.float64)
    a_ch = float(p['channel_frac']) * sp * sp
    chan = A >= a_ch
    if ctx.sea_level is not None:
        chan |= h <= ctx.sea_level
    # every cell downstream of a channel cell is channel too (D8 on the filled surface, down to an outlet), held at
    # the filled height: the multiple-flow area thins along a swale and broke it into segments, and the solve raised
    # the gaps into dams (closed depressions as deep as the rise cap)
    filled = np.asarray(HY.fill_depressions(h, sea_level=ctx.sea_level)[0], np.float64)
    # a filled hollow is no channel by its area: the routing spreads its water over the whole flat, every flat cell
    # passed the channel area and was held, and the flat survived the solve (the meadow's swales came out as flats
    # a few metres wide with 10-25 cm steps at their edges). Its water crosses it along one path (the downstream
    # extension below); the rest of it is hillslope
    lake = (filled - h) > 1e-4
    if hollow is not None:
        lake |= hollow
    chan &= ~lake
    core = chan
    chan = _downstream(chan, HY.flow_receivers(filled, sea_level=ctx.sea_level))
    h = np.where(chan, filled, h)
    hold = chan.astype(np.float64)
    soft = float(p['head_soft'])
    if soft > 1.0:
        # the channel heads' hold eases in over log A (module doc: no point sinks); the cells the downstream
        # extension added, and the sea, stay fully held
        t = np.clip((np.log(np.maximum(A, 1e-12)) - math.log(a_ch / soft)) / (2.0 * math.log(soft)), 0.0, 1.0)
        wsoft = np.where(lake, 0.0, t * t * (3.0 - 2.0 * t))      # a filled hollow's spread water holds nothing
        hold = np.where(chan & ~core, 1.0, wsoft)
        if ctx.sea_level is not None:
            hold = np.where(h <= ctx.sea_level, 1.0, hold)
    if p['hold_deposit_m'] is not None and 'deposit' in fields:
        floor = np.asarray(fields['deposit'], np.float64) >= float(p['hold_deposit_m'])
        hold = np.where(floor, 1.0, hold)
    for k in ('incised', 'river'):
        # a river course (op_incise's, river_path's) is a base level: the solve never raises it. Its cells whose
        # routed area fell under the channel area were solved as hillslope and raised up to the rise cap, 10 m
        # dams across a freshly cut creek that the finer levels filled into flat ribbons
        if k in fields:
            hold = np.where(np.asarray(fields[k], np.float64) > 0.5, 1.0, hold)
    az = math.radians(float(p['wind_from_deg']) + 180.0)
    wind = (math.sin(az), math.cos(az))
    hs, change, its = soil_solve(dev, h, hold, h, pins['pin_w'], pins['pin_h'], cell, C,
                                 float(p['asymmetry']), wind, half_cells=0.5 * sp / cell, omega=float(p['omega']),
                                 coarse_levels=int(p['coarse_levels']), iter_scale=float(p['iter_scale']))
    cap = float(p['rise_cap']) * relief
    if cap > 0:
        hs = h + soft_cap(hs - h, cap)
    b = float(p['blend'])
    hn = h + b * (hs - h)
    if cuts:
        gmax = max(float(p['rill_growth_max']), 1.0)
        d = np.where(chan, rill * np.clip((A / a_ch) ** 0.25, 1.0, gmax), 0.0)
        sig = float(p['rill_width_cells']) if p['rill_width_m'] is None else float(p['rill_width_m']) / cell
        peak = 1.0 / (math.sqrt(2.0 * math.pi) * sig) if sig > 0.4 else 1.0     # a line's blurred peak
        cut = gaussian_blur(d, sig) / peak if sig > 0.4 else d
        # the blurred line, not the line itself: max(cut, d) put the full depth back on the centre cells, a
        # one-cell slot down the middle of every rill
        cut = np.minimum(cut, gmax * rill) * (1.0 - np.clip(pins['pin_w'], 0.0, 1.0))
        hn = hn - cut
        fields['rill_cut'] = cut.astype(F32)
    fields['h'] = hn.astype(F32)
    if 'bed' in fields:
        bed = np.minimum(np.asarray(fields['bed'], np.float64), hn)
        fields['bed'] = bed.astype(F32)
        for k in ('deposit', 'talus'):
            if k in fields:
                fields[k] = np.minimum(np.asarray(fields[k], np.float64), hn - bed).astype(F32)
    ctx.evolved = True
    secs = round(time.perf_counter() - t0, 3)
    ctx.shared.setdefault('soil_log', []).append(dict(level=str(level), spacing_m=round(sp, 1),
                                                      relief_m=round(relief, 2), convexity=C,
                                                      channel_cells=int(chan.sum()), iterations=its,
                                                      last_change_m=change, seconds=secs))
    ctx.log(f"[terrain.hillslope] soil hills {level.n}^2 @ {cell:.3g} m: channels {100.0 * chan.mean():.1f} % "
            f"(A >= {a_ch:.0f} m2), spacing {sp:.0f} m, relief {relief:.2f} m (U/D {C:.3g} /m), asymmetry "
            f"{float(p['asymmetry']):g}, {its} iterations (last change {change:.2g} m), {secs} s")
    return fields



for _op in (op_creep, op_talus, op_threshold):
    _op.evolves = True                # run.py: runs on every coarse-to-fine pass of the coarsest level
op_soil_hills.post = True             # run.py: once per level, after its last coarse-to-fine pass
OPS = {'creep': op_creep, 'talus': op_talus, 'threshold': op_threshold, 'soil_hills': op_soil_hills}
