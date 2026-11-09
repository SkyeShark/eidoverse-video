"""The fluvial backbone (design section 4.1): uplift, stream-power incision, creep, threshold failure and sediment
deposition, run as GLSL compute kernels on a level's fields.

    stage ops (OPS; called by run.py as op(fields, level, params, seed, ctx=...)):
      'uplift'    the uplift U (m/yr) from a core/compose shape in world space, and on a fresh level the rough start
                  surface (the shape scaled to start_m, roughened): a flat start makes corduroy for millions of years
      'fluvial'   the backbone. On the coarsest level (and its coarse-to-fine pre-passes) it GROWS the range: full
                  physics for the recipe's age, the relief controller steering U. On every finer level it REFINES:
                  the level starts as its parent upsampled, its border band is pinned to the parent and fed the
                  parent's drainage area and sediment flux, and a low-pass lock holds the mean of blocks a few of
                  the parent's valley spacings wide at their start, so the level adds valleys, ridges, gullies and
                  rock without moving the landform. Down to the main level the real uplift runs (the lock only
                  corrects drift); on hero levels the lock is the uplift: it raises exactly what the rivers cut.

Per step (dt years), as in the design probe: flow_weights -> route_incise -> creep (sub-stepped) -> threshold (4
iterations) [-> lock]. The kernels are terrain/kernels/{flow_weights,route_incise}.glsl (twins below),
creep.glsl and threshold.glsl (twins in solvers/hillslope.py); the lock's two small kernels are written inline here
(LOCK_RESTRICT, LOCK_APPLY) with their twins.

Parameters of the 'fluvial' stage (metres, years, degrees; K in the stream-power law's own units, m^(1-2m)/yr):
    K 1.5e-5, m 0.5, n 1, p 1          the law (n = 1 is solved implicitly against the receiver: stable at any dt)
    slope 'dinf'                       the incision slope: D-infinity's steepest facet ('d8': steepest neighbour)
    valley_spacing_m 400               the smallest valleys' spacing: D = K (spacing / 6.5)^2 (D overrides)
    gullies False                      below the main level D shrinks x1/4 per level (spacing halves): gullies
    threshold_deg 35, threshold_noise 0.15, threshold_scale_m 400     Sc = tan(threshold) exp(noise n): lognormal
    threshold_gain 0.0                 tan Sc x (1 + gain) per level below the main one: rock stands steeper at
                                       finer scales, so gully walls and ribs survive the threshold pass
    breakup 0.0, k_breakup 0.0, breakup_scales_m [60, 20, 7]   rock breakup at the scales a level resolves (4
                                       cells and up): ln Sc + breakup n, K (1 + k_breakup n / 3): ribs, chutes
    outcrops 0.0, outcrop_scale_m 120  strong-rock outcrops: Sc (1 + outcrops smoothstep(ridged)) - the steep tail
    roughness 0.6, roughness_scales_m [2000, 300, 50]   K (1 + roughness n / 3)
    deposition 0.5                     G (Yuan et al. 2019): 0 bedrock incision, about 1 alluvial floors
    age_myr 2.0, later_frac 0.25       the coarsest level's first pass runs age, each later pass age x later_frac
    relief_m None, relief_calib 1.0    the relief controller's target: the main tile's relief (m), measured on the
                                       coarsest level's cells inside the main window every 100 steps; U scales by
                                       (target / current)^0.7, clamped to 0.75-1.33
    dt_ref_yr 1000                     dt = dt_ref (cell / 78 m) when growing; refining levels below the main level
                                       keep the main level's dt, so each finer level adds detail as deep in cells
    refine_steps 1500                  steps on each refining level
    lock True                          the low-pass lock on refining levels (hero levels: blocks 2 parent valley
                                       spacings wide; levels down to the main one, which run their uplift: the mean)
    threshold_mode 'iso'               'iso': slopes over Sc by their upwind gradient magnitude relax along the
                                       gradient (isotropic); 'pair': the design's pair excess (octagonal, 4-fold bias)
    threshold_rate None                0.12 iso, 0.06 pair; threshold_iters 2 a step (2 x 0.12 moves what the
                                       design's 4 x 0.06 did, with 4 passes fewer: each iso iteration is 2 passes)
    fill_pits True, pit_eps_m 0.001    a pit fills to just above its lowest neighbour (a basin fills to its spill)
    creep_cap 5, max_creep_sub 32
    mode 'evolve' | 'refine'           'refine' (real_place's hero levels): no uplift, the lock, and Sc never below
                                       the inherited surface's own slope, so a real cliff stands and only new
                                       detail fails
Fields read: h, bed (else all rock), U (else 0 or the 'uplift' stage's shape), K_factor and Sc_factor (an earlier
stage's modulation, multiplied in), Sc (an earlier stage's threshold, replacing the default), A, qs.
Fields written: h, bed, A (one-step lagged; run.py routes it to convergence after the level), qs, wear, deposit,
talus, and U, K, Sc, G for the masks and later stages.

Devices. The kernels run on the GPU (core/gpu.py). For tests, the same driver runs the numpy twins instead
(device('twin'), or EIDO_TERRAIN_DEVICE=twin): plain Python, 64-128 cells, never a production path.
"""
from __future__ import annotations

import math
import os
import time

import numpy as np

from ..core import compose as C
from ..core import grid as Gd
from ..core import twins as T
from ..core import world_noise as N

F32 = np.float32
OPEN, PERIODIC, PINNED = T.BOUND_OPEN, T.BOUND_PERIODIC, T.BOUND_PINNED
CELL_REF_M = 78.0                       # dt = dt_ref (cell / 78 m): the research's 78 m cells at 1000 yr steps
SPACING_RATIO = 26.0                    # valley spacing / sqrt(D / K), calibrated here (the design asked for it): at
                                        # 62.5 m cells near steady state valleys with 5 m of prominence sit 26.0 and
                                        # 25.8 x sqrt(D / K) apart (1600 m at 61.5 m, 1238 m at 48 m). The design's
                                        # 6.5 was measured on 78 m grids, where valleys cannot sit closer than 4-6
                                        # cells: with it the first range grew valleys 2.4 x too far apart
MIN_SPACING_CELLS = 5.0                 # a level resolves valleys at least this many cells apart
LOCK_SCALE = 2.0                        # the lock's blocks: 2 of the parent's valley spacings (finer is free)
LOCK_PHASES = ((0, 0), (1, 0), (1, 1), (0, 1))   # the block grid's offsets by step, in half blocks
CONTROL_EVERY = 100                     # the relief controller: every 100 steps U x (target / relief)^0.7, clamped
CONTROL_POWER = 0.7                     # (the design's 200 steps, ^0.5 and 0.8-1.25 left the first range 30 % high:
CONTROL_CLAMP = (0.75, 1.33)            # each finer pass resolves higher peaks faster than that caught up)

DEFAULTS = dict(
    K=1.5e-5, m=0.5, n=1.0, p=1.0, slope='dinf', valley_spacing_m=400.0, D=None, gullies=False,
    threshold_deg=35.0, threshold_noise=0.15, threshold_scale_m=400.0, threshold_gain=0.0,
    breakup=0.0, k_breakup=0.0, breakup_scales_m=(60.0, 20.0, 7.0), outcrops=0.0, outcrop_scale_m=120.0,
    roughness=0.6, roughness_scales_m=(2000.0, 300.0, 50.0), deposition=0.5,
    age_myr=2.0, later_frac=0.25, relief_m=None, relief_calib=1.0, dt_ref_yr=1000.0, refine_steps=1500,
    lock=True, creep_cap=5.0, threshold_iters=2, threshold_mode='iso', threshold_rate=None, max_creep_sub=32,
    fill_pits=True, pit_eps_m=1e-3, mode='evolve', min_steps=100, max_steps=6000,
)
THRESHOLD_RATE = {'iso': 0.12, 'pair': 0.06}


def _p(params, key):
    v = params.get(key, DEFAULTS[key]) if params else DEFAULTS[key]
    return DEFAULTS[key] if v is None and DEFAULTS[key] is not None else v


# ============================================================================================== the devices ===

class _Tex:
    """A twin-device texture: a float32 (H, W, C) array with the GPU texture's size and format attributes."""

    def __init__(self, a, fmt):
        self.a = np.ascontiguousarray(a, F32)
        self.format = fmt
        self.height, self.width = self.a.shape[:2]


_FMT = {1: 'R32F', 2: 'RG32F', 4: 'RGBA32F'}


def _hwc(arr):
    a = np.asarray(arr, F32)
    if a.ndim == 2:
        a = a[:, :, None]
    if a.shape[2] == 3:
        a = np.concatenate([a, np.zeros(a.shape[:2] + (1,), F32)], 2)
    return np.ascontiguousarray(a)


class Inline:
    """A kernel written inline in a solver module: its name (the twin's) and source."""

    def __init__(self, name, source):
        self.name = name
        self.source = source


class TwinDevice:
    """The numpy twins as a device (tests only): textures are arrays, a dispatch runs the kernel's twin."""
    name = 'twin'

    def __init__(self):
        from . import hillslope, hydro  # noqa: F401 - register their twins
        self._specs = {}

    def texture(self, arr):
        a = _hwc(arr)
        return _Tex(a, _FMT[a.shape[2]])

    def empty(self, shape, channels=4):
        return _Tex(np.zeros((int(shape[0]), int(shape[1]), channels), F32), _FMT[channels])

    def read(self, tex):
        return tex.a.copy()

    def _spec(self, kernel):
        key = kernel.name if isinstance(kernel, Inline) else kernel
        if key not in self._specs:
            from ..core import gpu as G
            if isinstance(kernel, Inline):
                self._specs[key] = G.parse_spec(kernel.source, kernel.name)
            else:
                self._specs[key] = G.load_source(kernel)[2]
        return self._specs[key]

    def run(self, kernel, samplers, images, uniforms):
        spec = self._spec(kernel)
        name = kernel.name if isinstance(kernel, Inline) else kernel
        for group, declared, what in ((samplers, spec.samplers, 'sampler'), (images, spec.images, 'image'),
                                      (uniforms, spec.uniforms, 'uniform')):
            if set(group) != set(declared):
                raise KeyError(f'kernel {name!r}: {what}s given {sorted(group)}, declared {sorted(declared)}')
        u = {}
        for k, ty in spec.uniforms.items():
            v = uniforms[k]
            u[k] = int(v) if ty == 'int' else (tuple(int(x) for x in v) if ty.startswith('ivec') else
                                                (np.asarray(v, F32) if ty.startswith('vec') else F32(v)))
        out = T.get_twin(name)({k: t.a for k, t in samplers.items()}, u)
        for k, t in images.items():
            a = np.asarray(out[k], F32)
            a = a[:, :, None] if a.ndim == 2 else a
            if a.shape != t.a.shape:
                raise ValueError(f'twin of {name!r}: image {k!r} is {a.shape}, its texture {t.a.shape}')
            t.a = np.ascontiguousarray(a)

    def sync(self):
        pass


class GPUDevice:
    """The GPU through core/gpu.py."""
    name = 'gpu'

    def __init__(self):
        from ..core import gpu as G
        self.G = G
        G.init()
        self._k = {}

    def texture(self, arr):
        return self.G.texture(_hwc(arr))

    def empty(self, shape, channels=4):
        return self.G.empty(shape, channels=channels)

    def read(self, tex):
        return self.G.read(tex)

    def kernel(self, kernel):
        key = kernel.name if isinstance(kernel, Inline) else kernel
        if key not in self._k:
            self._k[key] = (self.G.kernel(source=kernel.source, name=kernel.name) if isinstance(kernel, Inline)
                            else self.G.kernel(kernel))
        return self._k[key]

    def run(self, kernel, samplers, images, uniforms):
        self.G.run(self.kernel(kernel), None, samplers=samplers, images=images, uniforms=uniforms)

    def sync(self):
        pass


_DEVICES = {}


def device(kind=None):
    """The process's device: 'gpu' (production) or 'twin' (tests). Default: EIDO_TERRAIN_DEVICE, else 'gpu'."""
    kind = kind or os.environ.get('EIDO_TERRAIN_DEVICE', 'gpu')
    if kind not in _DEVICES:
        if kind == 'gpu':
            _DEVICES[kind] = GPUDevice()
        elif kind == 'twin':
            _DEVICES[kind] = TwinDevice()
        else:
            raise ValueError(f"device {kind!r} is 'gpu' or 'twin'")
    return _DEVICES[kind]


class Pair:
    """Two textures of one size and format on a device: read .src, write .dst, swap()."""

    def __init__(self, dev, arr):
        self.dev = dev
        self.src = dev.texture(arr)
        a = _hwc(arr)
        self.dst = dev.empty(a.shape[:2], a.shape[2])

    def swap(self):
        self.src, self.dst = self.dst, self.src


def dummy(dev):
    """A 1 x 1 zero texture for a declared sampler a dispatch does not use."""
    return dev.texture(np.zeros((1, 1), F32))


# ================================================================================================ the twins ===

def wpow(s, e):
    return s if float(e) == 1.0 else np.power(s, F32(e)).astype(F32)


# D-infinity's 8 facets (side neighbour, diagonal neighbour), route_incise.glsl's FACET
FACETS = ((4, 7), (6, 7), (6, 5), (3, 5), (3, 0), (1, 0), (1, 2), (4, 2))


@T.twin('flow_weights')
def flow_weights(s, u):
    h = s['st'][..., 0]
    ws = np.zeros_like(h)
    for k in range(8):
        hq, ok = T.neighbour(h, k, u['uBound'])
        sl = (h - hq) / (T.LEN[k] * u['uDx'])
        pos = ok & (sl > 0)
        ws = ws + np.where(pos, wpow(np.where(pos, sl, F32(1)), u['uP']), F32(0))
    return {'outW': ws[..., None]}


@T.twin('route_incise')
def route_incise(s, u):
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):   # masked-out cells only
        return _route_incise(s, u)


def _route_incise(s, u):
    st, ws, par, pin, mk = s['st'], s['wsumT'][..., 0], s['par'], s['pin'], s['mk']
    h, Ac, qc = st[..., 0], st[..., 1], st[..., 2]
    dx, dt, bound = u['uDx'], u['uDt'], u['uBound']
    A = dx * dx + pin[..., 2]
    qin = pin[..., 3].copy()
    smax = np.zeros_like(h)
    dr = np.ones_like(h)
    hr = h.copy()
    hlow = h.copy()
    hnb = np.full_like(h, F32(3.0e38))
    for k in range(8):
        hq, ok = T.neighbour(h, k, bound)
        hnb = np.where(ok, np.minimum(hnb, hq), hnb)
        Aq, _ = T.neighbour(Ac, k, bound)
        qq, _ = T.neighbour(qc, k, bound)
        wq, _ = T.neighbour(ws, k, bound)
        d = T.LEN[k] * dx
        up = ok & (hq > h)
        sl_up = np.where(up, (hq - h) / d, F32(1))
        share = wpow(sl_up, u['uP']) / np.maximum(wq, F32(1e-30))
        A = np.where(up, A + Aq * share, A)
        qin = np.where(up, qin + qq * share, qin)
        down = ok & ~(hq > h)
        sl = (h - hq) / d
        better = down & (sl > smax)
        smax = np.where(better, sl, smax)
        dr = np.where(better, d, dr)
        hr = np.where(better, hq, hr)
        hlow = np.where(down, np.minimum(hlow, hq), hlow)
    if u.get('uSlope', 0) == 1:
        smax = np.zeros_like(h)
        for k1, k2 in FACETS:
            e1, ok1 = T.neighbour(h, k1, bound)
            e2, ok2 = T.neighbour(h, k2, bound)
            s1 = (h - e1) / dx
            s2 = (e1 - e2) / dx
            side = s2 < 0
            diag = ~side & (s2 > s1)
            t = np.where(s1 > 0, s2 / np.where(s1 > 0, s1, F32(1)), F32(0))
            fs = np.where(side, s1, np.where(diag, (h - e2) / (F32(1.41421356) * dx), np.sqrt(s1 * s1 + s2 * s2)))
            rh = np.where(side, e1, np.where(diag, e2, e1 - t * s2 * dx))
            rd = np.where(side, dx, np.where(diag, F32(1.41421356) * dx, dx * np.sqrt(F32(1) + t * t)))
            better = ok1 & ok2 & (fs > smax)
            smax = np.where(better, fs, smax)
            hr = np.where(better, rh, hr)
            dr = np.where(better, rd, dr)
    K = par[..., 1].copy()
    if u['uColN'] > 0:
        col = s['kcol'][0, :, 0]
        nc = u['uColN']
        t = np.clip((h - s['zoff'][..., 0] - u['uColZ0']) / u['uColDz'], F32(0), F32(nc - 1))
        i0 = np.floor(t).astype(np.int64)
        i1 = np.minimum(i0 + 1, nc - 1)
        f = (t - i0.astype(F32)).astype(F32)
        K = K * (col[i0] * (F32(1) - f) + col[i1] * f)
    Am = np.power(A, u['uM']).astype(F32)
    Dp = par[..., 3] * qin / A
    rise = dt * (par[..., 0] + Dp)
    has = smax > 0
    if float(u['uN']) == 1.0:
        Fc = dt * K * Am / dr
        hi = (h + rise + Fc * hr) / (F32(1) + Fc)
    else:
        hi = np.maximum(h - dt * K * Am * np.power(np.where(has, smax, F32(1)), u['uN']), hlow) + rise
    hn = np.where(has, hi, h + rise)
    fill = np.zeros_like(h)
    if u.get('uPitFill', 0) == 1:
        pit = (smax <= 0) & (hnb < F32(3.0e38))
        fill = np.where(pit, np.maximum(hnb + u['uPitEps'] - hn, F32(0)), F32(0))
        hn = hn + fill
    e = np.maximum(h + rise - hn, F32(0))
    qout = np.maximum(qin + (e / dt - Dp) * dx * dx, F32(0))
    dep = mk[..., 1] + dt * Dp + fill
    tal = mk[..., 2].copy()
    loose = mk[..., 3] + dt * Dp + fill
    other = np.maximum(loose - dep - tal, F32(0))
    r = e.copy()
    a = np.minimum(r, dep)
    dep = dep - a
    r = r - a
    a = np.minimum(r, tal)
    tal = tal - a
    r = r - a
    r = r - np.minimum(r, other)
    mo = T.rgba(mk[..., 0] + r, dep, tal, np.maximum(loose - e, F32(0)))
    if bound == PINNED:
        hp = T.pin_apply(hn, pin[..., 0], pin[..., 1])
        mo = pin_layers(mo, hp - hn)
        hn = hp
    return {'outS': T.rgba(hn, A, qout, st[..., 3]), 'outM': mo}


def pin_layers(m, d):
    """route_incise.glsl / threshold.glsl pin_layers: the pin's change d of the height in the layers m (wear,
    deposit, talus, loose; ... x 4): d > 0 is deposit; d < 0 takes deposit, talus, other loose cover, then rock."""
    m = np.array(m, F32)
    d = np.asarray(d, F32)
    gain = d >= 0
    q = np.where(gain, F32(0), -d)
    other = np.maximum(m[..., 3] - m[..., 1] - m[..., 2], F32(0))
    a = np.minimum(q, m[..., 1])
    dep = m[..., 1] - a
    q = q - a
    a = np.minimum(q, m[..., 2])
    tal = m[..., 2] - a
    q = q - a
    q = q - np.minimum(q, other)
    lo = np.maximum(m[..., 3] - (-d - q), F32(0))
    out = T.rgba(m[..., 0] + q, dep, tal, lo)
    up = T.rgba(m[..., 0], m[..., 1] + d, m[..., 2], m[..., 3] + d)
    return np.where(gain[..., None], up, out).astype(F32)


# ============================================================================== the low-pass lock (inline) ===
# A refining level must add detail, not move the landform. Every b x b block of its cells keeps the mean it started
# with (its parent's surface, upsampled), b about the parent's valley spacing in cells: the landform the parent
# resolved stays, and everything finer (the valleys, gullies and rock this level grows) is free. restrict: the
# blocks' drift from their targets; apply: the drift, spread by a cubic B-spline (C2: a bilinear spread leaves
# kinks along the block lines, and over a run the lock's correction is the level's whole effective uplift, hundreds
# of metres, so those kinks printed grid-aligned facets), taken off.

LOCK_RESTRICT = Inline('lock_restrict', r'''//! sampler st       x: h of the refining level (n x n)
//! sampler tgt      x: each block's target mean
//! image   outR r32f
//! uniform int uB    the block, cells
//! uniform ivec2 uOff the block grid's offset, cells: block p covers cells uB p - uOff .. + uB (clipped to the grid)
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 m = imageSize(outR);
  if (!inside(p, m)) return;
  ivec2 n = textureSize(st, 0);
  ivec2 c0 = max(uB * p - uOff, ivec2(0));
  ivec2 c1 = min(uB * p - uOff + uB, n);
  float s = 0.0;
  for (int j = c0.y; j < c1.y; j++) {
    float row = 0.0;
    for (int i = c0.x; i < c1.x; i++) row += texelFetch(st, ivec2(i, j), 0).x;
    s += row;
  }
  int cnt = max(c1.x - c0.x, 0) * max(c1.y - c0.y, 0);
  float r = cnt > 0 ? s / float(cnt) - texelFetch(tgt, p, 0).x : 0.0;
  imageStore(outR, p, vec4(r, 0.0, 0.0, 0.0));
}
''')

LOCK_APPLY = Inline('lock_apply', r'''//! sampler st       the refining level's state (x: h)
//! sampler res      x: the blocks' drift
//! sampler pin      x: pin_w, y: pin_h (the border band holds its pins through the lock too)
//! sampler mk       x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outS rgba32f
//! image   outM rgba32f  the layers with the lock's change counted (lock_layers)
//! uniform float uGain
//! uniform int uB    the block, cells
//! uniform ivec2 uOff the block grid's offset (lock_restrict's)
/* the lock's change d of the height in the layers m: d < 0 takes deposit, then talus, then other loose cover, then
   rock, as route_incise.glsl counts a pin's (a pit the lock lowered and the incision pass refilled every step
   otherwise gathered hundreds of metres of "deposit" in one cell); d > 0 restores the parent's ground: rock, the
   loose cover unchanged and the wear reduced (counted as deposit it laid sediment over every slope the lock holds) */
vec4 lock_layers(vec4 m, float d) {
  if (d >= 0.0) return vec4(max(m.x - d, 0.0), m.y, m.z, m.w);
  float q = -d;
  float other = max(m.w - m.y - m.z, 0.0);
  float a = min(q, m.y);
  m.y -= a;
  q -= a;
  a = min(q, m.z);
  m.z -= a;
  q -= a;
  q -= min(q, other);
  m.w = max(m.w - (-d - q), 0.0);
  m.x += q;
  return m;
}
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  ivec2 m = textureSize(res, 0);
  vec2 u = (vec2(p + uOff) + 0.5) / float(uB) - 0.5;
  vec2 f0 = floor(u);
  vec2 t = u - f0;
  vec2 t2 = t * t;
  vec2 t3 = t2 * t;
  vec2 w[4];
  w[0] = (1.0 - 3.0 * t + 3.0 * t2 - t3) / 6.0;
  w[1] = (4.0 - 6.0 * t2 + 3.0 * t3) / 6.0;
  w[2] = (1.0 + 3.0 * t + 3.0 * t2 - 3.0 * t3) / 6.0;
  w[3] = t3 / 6.0;
  float r = 0.0;
  for (int j = 0; j < 4; j++) {
    int jj = clamp(int(f0.y) - 1 + j, 0, m.y - 1);
    float row = 0.0;
    for (int i = 0; i < 4; i++) {
      int ii = clamp(int(f0.x) - 1 + i, 0, m.x - 1);
      row += w[i].x * texelFetch(res, ivec2(ii, jj), 0).x;
    }
    r += w[j].y * row;
  }
  vec4 c = texelFetch(st, p, 0);
  vec4 pn = texelFetch(pin, p, 0);
  float hn = pin_apply(c.x - uGain * r, pn.x, pn.y);
  imageStore(outS, p, vec4(hn, c.y, c.z, c.w));
  imageStore(outM, p, lock_layers(texelFetch(mk, p, 0), hn - c.x));
}
''')


# ===================================================================== creep's change in the layers (inline) ===
# creep.glsl moves height only (the aging and hillslope ops call it without layers). In the fluvial step its net
# change over the sub-steps is counted afterwards: h is kept before (H_KEEP, into the flow weights' texture, free by
# then) and the difference goes into the layers (CREEP_LAYERS: a gain is soil, other loose cover; a loss takes
# deposit, talus, other loose cover, then rock). Uncounted, a pit refilled every step (deposit) that creep levelled
# again gathered hundreds of metres of "deposit" in one cell.
H_KEEP = Inline('h_keep', r'''//! sampler st   x: h
//! image   outH r32f
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  imageStore(outH, p, vec4(texelFetch(st, p, 0).x, 0.0, 0.0, 0.0));
}
''')

CREEP_LAYERS = Inline('creep_layers', r'''//! sampler st   x: h after creep
//! sampler h0   x: h before creep
//! sampler mk   x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outM rgba32f
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 m = texelFetch(mk, p, 0);
  float d = texelFetch(st, p, 0).x - texelFetch(h0, p, 0).x;
  if (d >= 0.0) {
    m.w += d;
  } else {
    float q = -d;
    float other = max(m.w - m.y - m.z, 0.0);
    float a = min(q, m.y);
    m.y -= a;
    q -= a;
    a = min(q, m.z);
    m.z -= a;
    q -= a;
    q -= min(q, other);
    m.w = max(m.w - (-d - q), 0.0);
    m.x += q;
  }
  imageStore(outM, p, m);
}
''')


@T.twin('h_keep')
def h_keep(s, u):
    return {'outH': np.asarray(s['st'], F32)[..., :1].copy()}


@T.twin('creep_layers')
def creep_layers(s, u):
    mk = np.asarray(s['mk'], F32)
    d = (np.asarray(s['st'], F32)[..., 0] - np.asarray(s['h0'], F32)[..., 0]).astype(F32)
    up = T.rgba(mk[..., 0], mk[..., 1], mk[..., 2], mk[..., 3] + d)
    return {'outM': np.where((d >= 0)[..., None], up, pin_layers(mk, d)).astype(F32)}


def offset_block_means(h, b, off, shape):
    """Each block's mean over its cells inside the grid: block (J, I) covers cells b (J, I) - off .. + b, clipped;
    `shape` blocks (0 where a block holds no cell). float64."""
    h = np.asarray(h, np.float64)
    n0, n1 = h.shape
    S = np.zeros((n0 + 1, n1 + 1))
    S[1:, 1:] = h.cumsum(0).cumsum(1)
    J, I = np.mgrid[0:shape[0], 0:shape[1]]
    y0 = np.clip(b * J - off[1], 0, n0)
    y1 = np.clip(b * J - off[1] + b, 0, n0)
    x0 = np.clip(b * I - off[0], 0, n1)
    x1 = np.clip(b * I - off[0] + b, 0, n1)
    cnt = (y1 - y0) * (x1 - x0)
    tot = S[y1, x1] - S[y0, x1] - S[y1, x0] + S[y0, x0]
    return np.where(cnt > 0, tot / np.maximum(cnt, 1), 0.0), cnt


@T.twin('lock_restrict')
def lock_restrict(s, u):
    tgt = s['tgt'][..., 0]
    mean, cnt = offset_block_means(s['st'][..., 0], int(u['uB']), tuple(u['uOff']), tgt.shape)
    return {'outR': np.where(cnt > 0, mean - tgt, 0.0).astype(F32)[..., None]}


@T.twin('lock_apply')
def lock_apply(s, u):
    st, res = s['st'], s['res'][..., 0]
    n0, n1 = st.shape[:2]
    m0, m1 = res.shape
    b = F32(int(u['uB']))
    ox, oy = (int(v) for v in u['uOff'])
    uj = (np.arange(n0, dtype=F32) + F32(oy) + F32(0.5)) / b - F32(0.5)
    ui = (np.arange(n1, dtype=F32) + F32(ox) + F32(0.5)) / b - F32(0.5)
    fj0, fi0 = np.floor(uj), np.floor(ui)

    def weights(t):
        t2 = t * t
        t3 = t2 * t
        return ((F32(1) - F32(3) * t + F32(3) * t2 - t3) / F32(6), (F32(4) - F32(6) * t2 + F32(3) * t3) / F32(6),
                (F32(1) + F32(3) * t + F32(3) * t2 - F32(3) * t3) / F32(6), t3 / F32(6))
    wj = weights((uj - fj0).astype(F32))
    wi = weights((ui - fi0).astype(F32))
    r = np.zeros((n0, n1), F32)
    for j in range(4):
        jj = np.clip(fj0.astype(np.int64) - 1 + j, 0, m0 - 1)
        row = np.zeros((n0, n1), F32)
        for i in range(4):
            ii = np.clip(fi0.astype(np.int64) - 1 + i, 0, m1 - 1)
            row = row + wi[i][None, :] * res[np.ix_(jj, ii)]
        r = r + wj[j][:, None] * row
    pin = s['pin']
    hn = T.pin_apply(st[..., 0] - u['uGain'] * r, pin[..., 0], pin[..., 1])
    d = hn - st[..., 0]
    mk = np.asarray(s['mk'], F32)
    up = T.rgba(np.maximum(mk[..., 0] - d, F32(0)), mk[..., 1], mk[..., 2], mk[..., 3])
    return {'outS': T.rgba(hn, st[..., 1], st[..., 2], st[..., 3]),
            'outM': np.where((d >= 0)[..., None], up, pin_layers(mk, d)).astype(F32)}      # LOCK_APPLY lock_layers


def block_means(h, b=2):
    """The b x b block means of an (n, n) field (the lock's targets), float32."""
    h = np.asarray(h, np.float64)
    m0, m1 = h.shape[0] // b, h.shape[1] // b
    return h[:m0 * b, :m1 * b].reshape(m0, b, m1, b).mean(axis=(1, 3)).astype(F32)


def lock_block(target_m, cell, n, max_frac=8):
    """The lock's block in cells: the power of two nearest target_m / cell, at least 2, at most n / max_frac, and
    dividing n."""
    b = 2 ** int(round(math.log2(max(float(target_m) / float(cell), 2.0))))
    b = int(min(max(b, 2), max(n // max_frac, 2)))
    while n % b:
        b //= 2
    return max(b, 1)


# ========================================================================================= the stage context ===

class StageContext:
    """What run.py tells a stage about where it runs (ops called without one get standalone defaults).

    plan, index      the level stack and this level's index; level is the grid being run (a pre-pass of the
                     coarsest level is that level at fewer cells)
    prepass          the pre-pass number (0, 1, ...) or None for the level's own cells
    fresh            True when nothing was inherited: the stage makes the start (the coarsest level's first pass)
    role             'grow' on the coarsest level and its pre-passes, 'refine' below it
    pins             dict(pin_w, pin_h, A_in, qs_in) (n, n) float32 arrays: the border band and the parent's inflow
    shared           a dict carried from level to level (the uplift shape and its peak, the controller's U factor)
    """

    def __init__(self, plan=None, index=0, level=None, prepass=None, fresh=True, role='grow', pins=None,
                 shared=None, seed=0, sea_level=None, base_elevation_m=0.0, flatten=None, device=None, log=None,
                 values=None):
        self.plan = plan
        self.index = index
        self.level = level
        self.prepass = prepass
        self.fresh = fresh
        self.role = role
        self.pins = pins
        self.shared = shared if shared is not None else {}
        self.seed = seed
        self.sea_level = sea_level
        self.base_elevation_m = base_elevation_m
        self.flatten = flatten or []
        self.device = device
        self.log = log or (lambda m: print(m, flush=True))
        self.values = values or {}
        self.evolved = False                  # a stage that moves material sets it: run.py then fills lakes

    @property
    def main(self):
        if self.plan:
            for lv in self.plan:
                if lv.role == 'main':
                    return lv
        return self.level

    @property
    def depth(self):
        """Levels below the main level count negative (hero), above positive (context): Level.depth."""
        return getattr(self.plan[self.index], 'depth', 0) if self.plan else 0


def standalone_context(fields, level):
    """A context for an op called on its own (api's plain loop, a test): grow from a fresh level unless h holds
    something, the level's outer ring pinned to base level."""
    fresh = 'h' not in fields or not np.any(np.asarray(fields['h']))
    return StageContext(plan=[level], index=0, level=level, fresh=fresh, role='grow',
                        pins=edge_pins(level.n, np.asarray(fields['h'], F32) if 'h' in fields else None))


def edge_pins(n, h=None, sea_level=None):
    """The coarsest level's pins: its outer ring held at base level (the start's own edge height, normally 0 m),
    and sea cells (h <= sea_level) held at their height. A_in = qs_in = 0."""
    w = np.zeros((n, n), F32)
    w[0, :] = w[-1, :] = w[:, 0] = w[:, -1] = 1.0
    ph = np.zeros((n, n), F32) if h is None else np.asarray(h, F32).copy()
    if sea_level is not None and h is not None:
        sea = np.asarray(h) <= sea_level
        w[sea] = 1.0
        ph[sea] = np.minimum(ph[sea], sea_level)
    z = np.zeros((n, n), F32)
    return dict(pin_w=w, pin_h=ph, A_in=z, qs_in=z.copy())


# ============================================================================== world-space inputs (metres) ===

def _field(spec, level, seed, dev):
    """A core/world_noise field spec at the level's cell centres: on the GPU in production, numpy on the twins."""
    if dev is not None and dev.name == 'gpu':
        return N.field_gpu(spec, level, seed).astype(np.float64)
    x, y = level.xy()
    return np.asarray(N.field(spec, x, y, seed), np.float64)


def _scales(scales, cell, min_cells=4.0):
    return [float(s) for s in (scales or ()) if float(s) >= min_cells * cell]


def _unit_noise(scales, level, seed, dev, base_seed):
    """Unit-variance noise (about N(0, 1)): fbm fields at the given scales, summed with equal weight."""
    spec = {'kind': 'sum', 'terms': [{'kind': 'fbm', 'wavelength_m': s, 'octaves': 2, 'seed': base_seed + i,
                                      'amp': 3.0 / math.sqrt(len(scales))} for i, s in enumerate(scales)]}
    return _field(spec, level, seed, dev)


def erodibility(level, params, seed, dev):
    """K (n, n): K0 (1 + roughness n1 / 3) (1 + k_breakup n2 / 3), n1 unit noise at the roughness scales and n2 at
    the breakup scales the level resolves (so +-roughness holds nearly every value), clamped at 0.2 K0."""
    K0 = float(_p(params, 'K'))
    out = np.full((level.n, level.n), K0)
    a = float(_p(params, 'roughness'))
    sc = _scales(_p(params, 'roughness_scales_m'), level.cell, 3.0)
    if a > 0 and sc:
        out = out * np.maximum(1.0 + a / 3.0 * _unit_noise(sc, level, seed, dev, 101), 0.2)
    kb = float(_p(params, 'k_breakup'))
    sb = _scales(_p(params, 'breakup_scales_m'), level.cell)
    if kb > 0 and sb:
        out = out * np.maximum(1.0 + kb / 3.0 * _unit_noise(sb, level, seed, dev, 151), 0.2)
    return np.maximum(out, 0.2 * K0)


def threshold(level, params, seed, dev, below_main=0):
    """Sc (n, n), tangents. Lognormal: tan(threshold_deg) exp(threshold_noise n400 + breakup nb), n400 unit noise at
    threshold_scale_m and nb at the breakup scales the level resolves (rock strength varies by orders of magnitude;
    the San Gabriels' slopes at 12 m sit 0.29 (p90) and 0.69 (p99) above their median in ln tan), times
    (1 + outcrops smoothstep(0.45, 0.85, ridged at outcrop_scale_m)) for strong-rock ribs, times
    (1 + threshold_gain)^below_main: rock stands steeper at finer scales (a 0.4 m cell sees steps and ledges a 12 m
    one averages away), so a refining level's gully walls and ribs are not shaved back to the coarse level's
    angle."""
    t = math.tan(math.radians(float(_p(params, 'threshold_deg'))))
    lnS = np.full((level.n, level.n), math.log(t))
    tn = float(_p(params, 'threshold_noise'))
    s0 = float(_p(params, 'threshold_scale_m'))
    if tn > 0 and s0 >= 3.0 * level.cell:
        lnS = lnS + tn * _unit_noise([s0], level, seed, dev, 211)
    b = float(_p(params, 'breakup'))
    sc = _scales(_p(params, 'breakup_scales_m'), level.cell)
    if b > 0 and sc:
        lnS = lnS + b * _unit_noise(sc, level, seed, dev, 307)
    out = np.exp(lnS)
    o = float(_p(params, 'outcrops'))
    so = float(_p(params, 'outcrop_scale_m'))
    if o > 0 and so >= 3.0 * level.cell:
        r = _field({'kind': 'ridged', 'wavelength_m': so, 'octaves': 3, 'seed': 401}, level, seed, dev)
        tt = np.clip((r - 0.45) / 0.4, 0.0, 1.0)
        out = out * (1.0 + o * tt * tt * (3.0 - 2.0 * tt))
    g = float(_p(params, 'threshold_gain'))
    if g and below_main > 0:
        out = out * (1.0 + g) ** below_main
    return out


def uplift_field(spec, level, seed, dev, peak=None):
    """The uplift shape (core/compose.uplift, about 0..1) at the level's cells, divided by `peak` (the shape's
    maximum on the coarsest level, so every level scales alike)."""
    x, y = level.xy()
    u = C.uplift(spec, x, y, seed, level=level if (dev is not None and dev.name == 'gpu') else None)
    return u / max(float(peak if peak is not None else np.max(u)), 1e-12)


def diffusivity(params, cell, depth, main_cell):
    """The creep diffusivity of a level (m^2/yr) and the valley spacing it stands for: D = K (spacing / 6.5)^2,
    spacing at least 5 cells; with gullies, the spacing halves for every level below the main one."""
    K = float(_p(params, 'K'))
    if params.get('D') is not None:
        return float(params['D']), SPACING_RATIO * math.sqrt(float(params['D']) / K)
    sp = float(_p(params, 'valley_spacing_m'))
    if _p(params, 'gullies') and depth < 0:
        sp = sp / 2.0 ** (-depth)
    sp = max(sp, MIN_SPACING_CELLS * cell)
    return K * (sp / SPACING_RATIO) ** 2, sp


# =============================================================================================== the driver ===

class FluvialRun:
    """One level's backbone on a device: the state and accumulator textures, and step()."""

    def __init__(self, dev, cell, fields, par, pins, bound=PINNED, column=None, lock_h0=None, lock_b=2):
        self.dev = dev
        self.cell = float(cell)
        h = np.asarray(fields['h'], F32)
        n0, n1 = h.shape
        self.shape = (n0, n1)
        z = np.zeros_like(h)
        A0 = np.asarray(fields['A'], F32) if 'A' in fields else np.full_like(h, self.cell * self.cell)
        qs0 = np.asarray(fields['qs'], F32) if 'qs' in fields else z
        loose = np.maximum(h - np.asarray(fields['bed'], F32), 0) if 'bed' in fields else z
        self.S = Pair(dev, T.rgba(h, A0, qs0, z))
        self.M = Pair(dev, T.rgba(fields.get('wear', z), fields.get('deposit', z), fields.get('talus', z), loose))
        self.W = dev.empty(self.shape, 1)
        self.P = dev.texture(par)
        self.Q = dev.texture(T.rgba(pins['pin_w'], pins['pin_h'], pins['A_in'], pins['qs_in']))
        self.bound = bound
        if column is not None:
            self.kcol = dev.texture(np.asarray(column['k_factor'], F32)[None, :])
            self.zoff = dev.texture(np.asarray(column['zoff'], F32))
            self.col = (float(column['z0']), float(column['dz']), int(len(column['k_factor'])))
        else:
            self.kcol = dummy(dev)
            self.zoff = self.kcol
            self.col = (0.0, 1.0, 0)
        self.phi = None                            # the isotropic threshold's excess texture (made on first use)
        self.lock = None
        self.lock_b = int(lock_b)
        if lock_h0 is not None:
            b = self.lock_b
            half = max(b // 2, 1)
            # large blocks reduce in two stages (b1 x b1 partial means first): one work group summing 128^2 texels
            # serially cost 4 ms a step at 2048^2. b1 divides the half block, so the offsets stay whole partials
            b1 = 1
            if b >= 32 and half % 16 == 0:
                b1 = 16
                while b // b1 > 64 and half % (2 * b1) == 0:
                    b1 *= 2
            stage1 = None
            if b1 > 1:
                stage1 = (b1, dev.texture(np.zeros((n0 // b1, n1 // b1), F32)), dev.empty((n0 // b1, n1 // b1), 1))
            mb = (n0 // b + 1, n1 // b + 1)
            # the block grid cycles through four half-block offsets, one per step: a fixed square grid's box means
            # and tensor-product spread printed a 4-fold aspect bias (0.06-0.08) on the refined levels' slopes
            phases = []
            for px, py in LOCK_PHASES:
                off = (px * half, py * half)
                tgt = offset_block_means(lock_h0, b, off, mb)[0]
                phases.append((off, dev.texture(np.asarray(tgt, F32))))
            self.lock = (phases, dev.empty(mb, 1), stage1)
        self.steps = 0

    def set_par(self, par):
        self.P = self.dev.texture(par)

    def step(self, dt, D, n_sub, iters, rate, cap, m=0.5, nexp=1.0, p=1.0, lock_gain=1.0, slope=1, iso=1,
             pit_fill=1, pit_eps=1e-3):
        dev, S, M, cell, b = self.dev, self.S, self.M, self.cell, self.bound
        dev.run('flow_weights', {'st': S.src}, {'outW': self.W}, {'uDx': cell, 'uP': p, 'uBound': b})
        z0, dz, nc = self.col
        dev.run('route_incise', {'st': S.src, 'wsumT': self.W, 'par': self.P, 'pin': self.Q, 'mk': M.src,
                                 'kcol': self.kcol, 'zoff': self.zoff},
                {'outS': S.dst, 'outM': M.dst},
                {'uDx': cell, 'uDt': dt, 'uM': m, 'uN': nexp, 'uP': p, 'uColZ0': z0, 'uColDz': dz, 'uColN': nc,
                 'uSlope': int(slope), 'uPitFill': int(pit_fill), 'uPitEps': pit_eps, 'uBound': b})
        S.swap()
        M.swap()
        if D > 0 and n_sub > 0:
            dev.run(H_KEEP, {'st': S.src}, {'outH': self.W}, {})          # the flow weights are used by now
            for _ in range(n_sub):
                dev.run('creep', {'st': S.src, 'par': self.P, 'pin': self.Q}, {'outS': S.dst},
                        {'uDx': cell, 'uDtSub': dt / n_sub, 'uD': D, 'uCap': cap, 'uBound': b})
                S.swap()
            dev.run(CREEP_LAYERS, {'st': S.src, 'h0': self.W, 'mk': M.src}, {'outM': M.dst}, {})
            M.swap()
        from .hillslope import threshold_pass
        for _ in range(iters):
            self.phi = threshold_pass(dev, S, M, self.P, self.Q, cell, rate, False, b, iso, self.phi)
        if self.lock is not None:
            phases, R, stage1 = self.lock
            off, tgt = phases[self.steps % len(phases)]
            if stage1 is not None:
                b1, zero, R1 = stage1
                dev.run(LOCK_RESTRICT, {'st': S.src, 'tgt': zero}, {'outR': R1}, {'uB': b1, 'uOff': (0, 0)})
                dev.run(LOCK_RESTRICT, {'st': R1, 'tgt': tgt}, {'outR': R},
                        {'uB': self.lock_b // b1, 'uOff': (off[0] // b1, off[1] // b1)})
            else:
                dev.run(LOCK_RESTRICT, {'st': S.src, 'tgt': tgt}, {'outR': R}, {'uB': self.lock_b, 'uOff': off})
            dev.run(LOCK_APPLY, {'st': S.src, 'res': R, 'pin': self.Q, 'mk': M.src}, {'outS': S.dst, 'outM': M.dst},
                    {'uGain': lock_gain, 'uB': self.lock_b, 'uOff': off})
            S.swap()
            M.swap()
        self.steps += 1

    def height(self):
        return self.dev.read(self.S.src)[..., 0]

    def readback(self):
        s = self.dev.read(self.S.src)
        mk = self.dev.read(self.M.src)
        return dict(h=s[..., 0], A=s[..., 1], qs=s[..., 2], wear=mk[..., 0], deposit=mk[..., 1], talus=mk[..., 2],
                    loose=mk[..., 3])


def creep_substeps(dt, cell, D, cap, max_sub):
    """(sub-steps, D used): dt_sub <= 0.9 cell^2 / (3.4 D cap); past max_sub the diffusivity is lowered instead
    (a level far finer than its valley spacing is smooth either way)."""
    if D <= 0:
        return 0, 0.0
    need = int(math.ceil(dt / (0.9 * cell * cell / (3.4 * D * cap))))
    if need <= max_sub:
        return max(need, 1), D
    return int(max_sub), D * max_sub / need


def _main_window(level, main):
    """(j0, j1, i0, i1): the cells of `level` inside the main tile's window (all of it when there is none)."""
    if main is None:
        return 0, level.n, 0, level.n
    i0 = int(max(0, math.floor((main.x0 - level.x0) / level.cell)))
    j0 = int(max(0, math.floor((main.y0 - level.y0) / level.cell)))
    i1 = int(min(level.n, math.ceil((main.x0 + main.side - level.x0) / level.cell)))
    j1 = int(min(level.n, math.ceil((main.y0 + main.side - level.y0) / level.cell)))
    return j0, j1, i0, i1


def window_relief(h, level, main):
    j0, j1, i0, i1 = _main_window(level, main)
    w = np.asarray(h, np.float64)[j0:j1, i0:i1]
    return float(np.percentile(w, 99.9) - np.percentile(w, 0.1))


# =================================================================================================== the ops ===

def op_uplift(fields, level, params, seed=0, ctx=None):
    """Stage 'uplift': the uplift shape (params 'shape': a core/compose uplift spec - ridge with spurs, dome,
    plateau, massif - in world metres) times U_m_per_yr (default 3e-3 m/yr) as the field U, normalised by the
    shape's peak on the coarsest level. On a fresh level, h = the start surface: the shape scaled to start_m
    (default 600 m) with start_roughness (0.4) of multi-scale texture. Its shape is remembered for the fluvial
    stage of every level."""
    ctx = ctx or standalone_context(fields, level)
    dev = ctx.device or device()
    spec = dict(params['shape'])
    s = int(seed) + int(params.get('seed', 0))
    first = 'uplift' not in ctx.shared
    u = None
    if first or ctx.fresh:
        x, y = level.xy()
        u = C.uplift(spec, x, y, s, level=level if dev.name == 'gpu' else None)
        if first:
            ctx.shared['uplift'] = dict(spec=spec, seed=s, peak=float(np.max(u)),
                                        U=float(params.get('U_m_per_yr', 3e-3)))
    sh = ctx.shared['uplift']
    if ctx.role == 'grow':
        if u is None:
            u = uplift_field(spec, level, s, dev, peak=1.0)
        fields['U'] = (sh['U'] * u / max(sh['peak'], 1e-12)).astype(F32)
    if ctx.fresh:
        x, y = level.xy()
        h0 = C.start_surface(spec, x, y, s, height_m=float(params.get('start_m', 600.0)),
                             roughness=float(params.get('start_roughness', 0.4)),
                             level=level if dev.name == 'gpu' else None, peak=sh['peak'])
        fields['h'] = h0
        fields['bed'] = h0


def _sea_flat(fields, ctx, shape):
    """1 on sea cells and inside flatten areas (rigid: no uplift, no incision)."""
    rig = np.zeros(shape, bool)
    if ctx.sea_level is not None:
        rig |= np.asarray(fields['h']) <= ctx.sea_level
    if ctx.flatten:
        x, y = ctx.level.xy()
        rig |= C.flatten_mask([{'at': f['at'], 'radius': f.get('radius', 10.0), 'falloff': f.get('falloff', 0.0)}
                               for f in ctx.flatten if f.get('radius') is not None], x, y) > 0.5
    return rig


def op_fluvial(fields, level, params, seed=0, ctx=None):
    """Stage 'fluvial' (module doc): grow on the coarsest level, refine below it."""
    ctx = ctx or standalone_context(fields, level)
    dev = ctx.device or device()
    t0 = time.perf_counter()
    lv = level
    n = lv.n
    cell = float(lv.cell)
    mode = _p(params, 'mode')
    refine = ctx.role == 'refine' or mode == 'refine'
    main = ctx.main
    main_cell = float(main.cell) if main is not None else cell
    depth = ctx.depth
    s = int(seed) + int(params.get('seed', 0))
    if 'h' not in fields:
        raise ValueError(f"stage 'fluvial' on {lv}: no height yet (put an 'uplift' stage or a start before it)")
    h = np.asarray(fields['h'], F32)

    # the inputs, all functions of world position (finding 2 of the design)
    K = erodibility(lv, params, s, dev)
    if 'K_factor' in fields:
        K = K * np.asarray(fields['K_factor'], np.float64)
    if 'Sc' in fields and params.get('Sc_from_fields', True) and not refine:
        Sc = np.asarray(fields['Sc'], np.float64)
    else:
        Sc = threshold(lv, params, s, dev, below_main=max(0, -depth))
    if 'Sc_factor' in fields:
        Sc = Sc * np.asarray(fields['Sc_factor'], np.float64)
    if mode == 'refine':
        # a real place: its own slopes stand (a cliff in the DEM is not failed), only new detail relaxes
        gx, gy = Gd.gradient(h, cell)
        Sc = np.maximum(Sc, 1.1 * np.hypot(gx, gy))
    # uplift: the growing level runs the real uplift. Refining levels run none: the lock is their uplift, raising
    # exactly what their rivers cut. (With the coarsest level's uplift a level down eroded 343 m on average in 900
    # steps - stream power and the threshold erode more efficiently at finer cells - and a spatial lock fighting
    # that dammed valleys)
    hero_like = refine
    if hero_like:
        U = np.zeros((n, n))
    elif 'U' in fields:
        U = np.asarray(fields['U'], np.float64)
    elif 'uplift' in ctx.shared:
        sh = ctx.shared['uplift']
        U = sh['U'] * uplift_field(sh['spec'], lv, sh['seed'], dev, peak=sh['peak'])
    else:
        U = np.zeros((n, n))
    uf = float(ctx.shared.get('U_factor', 1.0))
    G = np.full((n, n), float(_p(params, 'deposition')))
    rigid = _sea_flat(fields, ctx, (n, n))
    if rigid.any():
        # the sea and flatten areas are rigid (core/compose.flatten_mask): U = K = 0. A flatten area then lags
        # its uplifted surroundings into a shallow hollow; the end stage fills that with sediment, never water
        # (run.py passes the areas to hydro.lakes as no_lake), and the API levels it exactly afterwards. (Keeping
        # U there instead raised the uncut block into a mound.)
        U = np.where(rigid, 0.0, U)
        K = np.where(rigid, 0.0, K)

    def par_of(factor):
        return T.rgba(U * factor, K, Sc, G)

    pins = ctx.pins or edge_pins(n, h, ctx.sea_level)
    D, spacing = diffusivity(params, cell, depth, main_cell)
    if refine:
        dt = float(_p(params, 'dt_ref_yr')) * max(cell, main_cell) / CELL_REF_M
        steps = int(params.get('steps', _p(params, 'refine_steps')))
    else:
        dt = float(_p(params, 'dt_ref_yr')) * cell / CELL_REF_M
        age = float(_p(params, 'age_myr')) * 1e6
        first = ctx.fresh and ctx.prepass in (None, 0)
        dur = age if first else age * float(_p(params, 'later_frac'))
        steps = int(params.get('steps', round(dur / dt)))
    steps = int(np.clip(steps, int(_p(params, 'min_steps')), int(_p(params, 'max_steps'))))
    cap = float(_p(params, 'creep_cap'))
    n_sub, D_used = creep_substeps(dt, cell, D, cap, int(_p(params, 'max_creep_sub')))
    lock, lock_b, lock_m = None, 2, None
    if refine and _p(params, 'lock'):
        # hold what the parent resolved: wavelengths from its valley spacing up (a real DEM: 8 of its cells)
        pl = ctx.plan[ctx.plan[ctx.index].parent] if (ctx.plan and ctx.plan[ctx.index].parent is not None) else None
        pcell = float(pl.cell) if pl is not None else 2.0 * cell
        if params.get('lock_m') is not None:
            lock_m = float(params['lock_m'])
        elif mode == 'refine':
            lock_m = 8.0 * pcell
        else:
            # hold what the parent's valleys made (wavelengths from 2 of its valley spacings up), free below: a lock
            # of one parent cell left bumps along channel beds (interior lakes), a mean lock let the level
            # reorganise (channels 25 m deeper, rivers aggraded, ponds at the band)
            lock_m = LOCK_SCALE * diffusivity(params, pcell, getattr(pl, 'depth', depth + 1), main_cell)[1]
        lock_b = lock_block(lock_m, cell, n)
        lock = h                                       # the start: every phase's block means are held to it
    run = FluvialRun(dev, cell, fields, par_of(uf), pins, PINNED, params.get('column'), lock, lock_b)
    target = params.get('relief_m')
    control = (not refine) and target is not None
    target = float(target) * float(_p(params, 'relief_calib')) if control else None
    iters = int(_p(params, 'threshold_iters'))
    tmode = _p(params, 'threshold_mode')
    rate = float(params.get('threshold_rate') or THRESHOLD_RATE[tmode])
    mexp, nexp, pexp = float(_p(params, 'm')), float(_p(params, 'n')), float(_p(params, 'p'))
    slope_mode = {'dinf': 1, 'd8': 0}[_p(params, 'slope')]
    pit = 1 if _p(params, 'fill_pits') else 0
    peps = float(_p(params, 'pit_eps_m'))
    history = []
    for i in range(steps):
        run.step(dt, D_used, n_sub, iters, rate, cap, mexp, nexp, pexp, slope=slope_mode,
                 iso=1 if tmode == 'iso' else 0, pit_fill=pit, pit_eps=peps)
        if control and (i + 1) % CONTROL_EVERY == 0 and i + 1 < steps:
            rel = window_relief(run.height(), lv, main)
            f = float(np.clip((target / max(rel, 1e-6)) ** CONTROL_POWER, *CONTROL_CLAMP))
            uf *= f
            run.set_par(par_of(uf))
            history.append((i + 1, round(rel, 1), round(uf, 4)))
    out = run.readback()
    if control:
        ctx.shared['U_factor'] = uf
    for k in ('h', 'A', 'qs', 'wear', 'deposit', 'talus'):
        fields[k] = out[k]
    fields['bed'] = out['h'] - out['loose']
    fields['U'] = (U * uf).astype(F32)
    fields['K'] = K.astype(F32)
    fields['Sc'] = Sc.astype(F32)
    fields['G'] = G.astype(F32)
    ctx.evolved = True
    rel = window_relief(out['h'], lv, main) if not refine else None
    info = dict(level=str(lv), prepass=ctx.prepass, role='refine' if refine else 'grow', steps=steps,
                dt_yr=round(dt, 2), years=round(steps * dt), D=D_used, spacing_m=round(spacing, 1), creep_sub=n_sub,
                U_factor=round(uf, 4), relief_main_window_m=None if rel is None else round(rel, 1),
                lock_block_cells=lock_b if lock is not None else None, lock_m=lock_m,
                seconds=round(time.perf_counter() - t0, 3), controller=history[-6:])
    ctx.shared.setdefault('fluvial_log', []).append(info)
    ctx.log(f"[terrain.fluvial] {info['role']} {lv.n}^2 @ {cell:.3g} m"
            + (f' (pre-pass {ctx.prepass})' if ctx.prepass is not None else '')
            + f": {steps} steps x {dt:.0f} yr, D {D_used:.3g} m2/yr (valleys {spacing:.0f} m), creep x{n_sub}"
            + (f", U x{uf:.3f}, relief {rel:.0f} m" if rel is not None else '')
            + (f', locked above {lock_b} cells ({lock_b * cell:.0f} m)' if lock is not None else '')
            + f", {info['seconds']} s")
    return fields


op_uplift.evolves = True              # run.py runs evolving ops on every coarse-to-fine pass, the rest once
op_fluvial.evolves = True
OPS = {'uplift': op_uplift, 'fluvial': op_fluvial}
