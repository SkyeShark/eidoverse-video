"""River courses (design section 4.13, `river_path`): a river given as a polyline, or generated (a Kinoshita meander
train for incised meanders, or a smoothed random walk), carved as a base-level line: its channel is pinned low with
a slope along it, so the erosion stages build the valley around it.

    stage op (OPS; run.py calls op(fields, level, params, seed, ctx=...)):
      'river_path'   the course (world metres, deterministic per seed) into ctx.shared['river'], and the level's pins
                     (ctx.pins) with the channel held at its final bed: the stock 'fluvial' stage then cuts its valley
                     around it. The layered-rock stage (solvers/strata.py 'strata_fluvial') reads the same course and
                     lowers the channel over time instead (the base-level fall), following `schedule`.

    from eidoblend.terrain.solvers import rivers as RV
    pts = RV.kinoshita((0, 0), 270.0, 20000.0, wavelength_m=1100.0, sinuosity=3.0, seed=4)   # (N, 2) metres
    RV.metrics(pts)                 # arc length, chord, sinuosity, bend wavelengths, the closest approach of two parts
    mask, s, d = RV.channel(level, pts, width_m=60.0)       # the channel's cells, the arc length and distance there

Parameters of 'river_path' (metres, degrees, m/m):
    kind 'walk'                  'walk' (a smoothed random walk), 'kinoshita' (meanders), 'polyline' (points)
    points None                  [[x, y], ...] for 'polyline' (extended straight past its ends to cross every level)
    through [0, 0]               a point on the course (its arc-length origin)
    flow_azimuth_deg 90          the down-valley direction, compass degrees (clockwise from north: 90 flows east)
    length_m None                the course's length (default: three times the coarsest level's side)
    wiggle_deg 12, wiggle_wavelength_m 3000     'walk': the direction's spread and the scale of its bends
    wavelength_m 1200            'kinoshita': the arc length of one meander (two bends)
    sinuosity 2.5 (or theta0_deg)  'kinoshita': arc length / down-valley length (theta0 is solved for it)
    skew 0.03, flat 0.0          'kinoshita': Js (bends lean downstream) and Jf (flattened, boxy bends)
    vary 0.15                    'kinoshita': the slow variation of the amplitude and wavelength along the course
    width_m 60                   the channel's width (at least 1.5 cells, so it is connected on every level)
    bed_m 0                      the final bed's height (relative h) at `through`
    gradient 0.0015              the bed's fall per metre downstream
    schedule [[0, 0], [1, 1]]    the base-level fall over the run (strata_fluvial): time fraction -> fraction of the
                                 way from the starting surface down to the final bed (piecewise linear)

The Kinoshita curve (Kinoshita 1961; Parker et al. 1983): the channel direction along arc length s is
    theta(s) = theta0 sin(k s) + theta0^3 (Js cos(3 k s) - Jf sin(3 k s)),   k = 2 pi / wavelength
whose sinuosity is 1 / mean(cos theta) (Langbein & Leopold's sine-generated curve when Js = Jf = 0). Numpy only.
"""
from __future__ import annotations

import math

import numpy as np

F32 = np.float32
DEFAULTS = dict(kind='walk', points=None, through=(0.0, 0.0), flow_azimuth_deg=90.0, length_m=None, wiggle_deg=12.0,
                wiggle_wavelength_m=3000.0, wavelength_m=1200.0, sinuosity=2.5, theta0_deg=None, skew=0.03, flat=0.0,
                vary=0.15, width_m=60.0, bed_m=0.0, gradient=0.0015, schedule=((0.0, 0.0), (1.0, 1.0)),
                step_m=None, seed=0)
MIN_CELLS = 1.5                         # the channel is at least this many cells wide (8-connected on every level)


def _p(params, key):
    v = (params or {}).get(key, DEFAULTS[key])
    return DEFAULTS[key] if v is None and DEFAULTS[key] is not None else v


# ------------------------------------------------------------------------------------------- the courses ---

def _smooth_noise_1d(s, wavelength, seed, octaves=3):
    """A smooth 1D noise of unit standard deviation along s: sines at random phases, wavelengths halving."""
    rng = np.random.default_rng(int(seed) * 7919 + 101)
    out = np.zeros_like(s, dtype=np.float64)
    norm = 0.0
    for o in range(octaves):
        a = 0.5 ** o
        for _ in range(2):
            lam = wavelength / (2.0 ** o) * rng.uniform(0.7, 1.4)
            out += a * np.sin(2.0 * math.pi * s / lam + rng.uniform(0.0, 2.0 * math.pi))
            norm += a * a * 0.5
    return out / math.sqrt(norm)


def _integrate(theta, ds):
    """Points of a curve from its direction angle theta (radians, from +x) at arc steps ds."""
    dx = np.cos(theta) * ds
    dy = np.sin(theta) * ds
    x = np.concatenate([[0.0], np.cumsum(0.5 * (dx[1:] + dx[:-1]))])
    y = np.concatenate([[0.0], np.cumsum(0.5 * (dy[1:] + dy[:-1]))])
    return np.stack([x, y], 1)


def _place(local, through, flow_azimuth_deg, s, s0=0.0):
    """Rotate a course built along +x (down-valley) to the compass azimuth and move its arc-length origin s0 onto
    `through`."""
    az = math.radians(float(flow_azimuth_deg))
    ux, uy = math.sin(az), math.cos(az)                  # compass: clockwise from north
    vx, vy = -uy, ux                                     # left of the flow
    k = int(np.argmin(np.abs(s - s0)))
    p = local - local[k]
    xy = np.stack([p[:, 0] * ux + p[:, 1] * vx, p[:, 0] * uy + p[:, 1] * vy], 1)
    return xy + np.asarray(through, np.float64)[None, :]


def walk(through, flow_azimuth_deg, length_m, wiggle_deg=12.0, wiggle_wavelength_m=3000.0, seed=0, step_m=10.0):
    """A smoothed random walk: the direction wanders around the flow azimuth by a smooth noise of `wiggle_deg`
    standard deviation at `wiggle_wavelength_m`. (N, 2) world metres, upstream first."""
    n = max(int(math.ceil(length_m / step_m)) + 1, 3)
    s = np.linspace(-0.5 * length_m, 0.5 * length_m, n)
    theta = math.radians(float(wiggle_deg)) * _smooth_noise_1d(s, float(wiggle_wavelength_m), seed)
    local = _integrate(theta, s[1] - s[0])
    return _place(local, through, flow_azimuth_deg, s, 0.0)


def kinoshita_theta(phase, theta0, skew=0.0, flat=0.0):
    """The Kinoshita direction angle (radians) at a phase k s."""
    return theta0 * np.sin(phase) + theta0 ** 3 * (skew * np.cos(3.0 * phase) - flat * np.sin(3.0 * phase))


def kinoshita_sinuosity(theta0, skew=0.0, flat=0.0, samples=4096):
    """Arc length over down-valley length of the Kinoshita curve (one wavelength, exact up to sampling)."""
    ph = np.linspace(0.0, 2.0 * math.pi, samples, endpoint=False)
    c = float(np.mean(np.cos(kinoshita_theta(ph, theta0, skew, flat))))
    return float('inf') if c <= 1e-9 else 1.0 / c


def theta0_for(sinuosity, skew=0.0, flat=0.0):
    """theta0 (radians) giving a Kinoshita curve of the given sinuosity (bisection; sinuosity rises with theta0)."""
    target = float(sinuosity)
    if target <= 1.0:
        return 0.0
    lo, hi = 0.0, 2.6
    if kinoshita_sinuosity(hi, skew, flat) < target:
        raise ValueError(f'sinuosity {target:g} is beyond what the Kinoshita curve reaches before its bends close '
                         f'({kinoshita_sinuosity(hi, skew, flat):.2f} at theta0 {math.degrees(hi):.0f} degrees)')
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if kinoshita_sinuosity(mid, skew, flat) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def kinoshita(through, flow_azimuth_deg, length_m, wavelength_m=1200.0, sinuosity=2.5, theta0_deg=None, skew=0.03,
              flat=0.0, vary=0.15, seed=0, step_m=None):
    """A meander train: the Kinoshita direction along the arc, its amplitude theta0 (from the sinuosity unless
    given) and its wavelength varying slowly along the course by `vary` (relative), so no two bends are alike. The
    course's down-valley length is about length_m. (N, 2) world metres, upstream first."""
    th0 = math.radians(float(theta0_deg)) if theta0_deg is not None else theta0_for(sinuosity, skew, flat)
    sig = kinoshita_sinuosity(th0, skew, flat)
    arc = float(length_m) * sig
    step = float(step_m) if step_m else max(1.0, float(wavelength_m) / 160.0)
    n = max(int(math.ceil(arc / step)) + 1, 3)
    s = np.linspace(-0.5 * arc, 0.5 * arc, n)
    v = float(vary)
    nl = _smooth_noise_1d(s, 3.3 * float(wavelength_m), int(seed) + 17, octaves=2)
    na = _smooth_noise_1d(s, 2.7 * float(wavelength_m), int(seed) + 29, octaves=2)
    lam = float(wavelength_m) * np.clip(1.0 + v * nl, 0.5, 1.6)
    phase = np.concatenate([[0.0], np.cumsum(2.0 * math.pi / (0.5 * (lam[1:] + lam[:-1])) * np.diff(s))])
    phase += np.random.default_rng(int(seed) * 31 + 7).uniform(0.0, 2.0 * math.pi)
    # amplitude variation, kept under the closing angle: past about 125 degrees the bends touch
    amp = np.clip(th0 * (1.0 + 0.6 * v * na), 0.0, math.radians(125.0))
    theta = kinoshita_theta(phase, amp, skew, flat)
    local = _integrate(theta, s[1] - s[0])
    # the mean direction of a varying train drifts a little: turn it back onto +x
    d = local[-1] - local[0]
    a = -math.atan2(d[1], d[0])
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    local = local @ R.T
    return _place(local, through, flow_azimuth_deg, s, 0.0)


def extend(points, length_m):
    """A polyline extended straight past both ends (along its end segments) by length_m."""
    p = np.asarray(points, np.float64)
    if len(p) < 2:
        raise ValueError('a river polyline needs at least two points')
    a = p[0] - p[1]
    b = p[-1] - p[-2]
    a /= max(np.hypot(*a), 1e-9)
    b /= max(np.hypot(*b), 1e-9)
    return np.vstack([p[0] + a * length_m, p, p[-1] + b * length_m])


def resample(points, step_m):
    """The polyline at (about) equal arc steps."""
    p = np.asarray(points, np.float64)
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(math.ceil(s[-1] / step_m)) + 1, 2)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1)


def arc_length(points):
    p = np.asarray(points, np.float64)
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])


def metrics(points, wavelength_hint=None):
    """The course's geometry: arc length, chord, sinuosity (arc / chord), the bends (apexes where the direction
    turns back, i.e. local extremes of the lateral offset from the chord), the down-valley spacing of every second
    apex (the meander wavelength), and the closest approach of two parts of the course more than 1.5 local
    wavelengths of arc apart (a loop's neck)."""
    p = np.asarray(points, np.float64)
    s = arc_length(p)
    chord_v = p[-1] - p[0]
    chord = float(np.hypot(*chord_v))
    u = chord_v / max(chord, 1e-9)
    v = np.array([-u[1], u[0]])
    lat = (p - p[0]) @ v
    along = (p - p[0]) @ u
    sm = np.convolve(lat, np.ones(9) / 9.0, mode='same')
    d = np.diff(sm)
    ext = np.nonzero((d[:-1] > 0) & (d[1:] <= 0) | (d[:-1] < 0) & (d[1:] >= 0))[0] + 1
    ext = ext[(ext > 5) & (ext < len(p) - 6)]
    wl = np.diff(along[ext[::2]]) if len(ext) > 3 else np.array([])
    # the closest approach of parts far apart along the arc
    q = resample(p, max(s[-1] / 4000.0, 1.0))
    sq = arc_length(q)
    gap = 1.5 * (wavelength_hint if wavelength_hint else (float(np.median(np.abs(wl))) * max(s[-1] / max(chord, 1e-9), 1.0)
                                                          if len(wl) else s[-1] / 4.0))
    neck = float('inf')
    step = max(1, len(q) // 1500)
    qq, ss = q[::step], sq[::step]
    for i in range(len(qq)):
        far = np.abs(ss - ss[i]) > gap
        if far.any():
            neck = min(neck, float(np.min(np.hypot(*(qq[far] - qq[i]).T))))
    return dict(arc_m=float(s[-1]), chord_m=chord, sinuosity=float(s[-1] / max(chord, 1e-9)),
                bends=int(len(ext)), wavelength_m=float(np.median(np.abs(wl))) if len(wl) else float('nan'),
                amplitude_m=float(0.5 * (np.percentile(lat, 95) - np.percentile(lat, 5))), neck_m=neck)


# ------------------------------------------------------------------------------------------- on a level ---

def channel(level, points, width_m, min_cells=MIN_CELLS):
    """The channel on a level: (mask (n, n) bool, s (n, n) float64 arc length of the nearest course point (nan off
    the channel), d (n, n) distance to the course (inf off the channel's neighbourhood)). The channel is the cells
    within max(width_m, min_cells * cell) / 2 of the course. Only the course's segments near the window are
    visited, each over its own bounding box."""
    p = np.asarray(points, np.float64)
    n = level.n
    cell = float(level.cell)
    half = 0.5 * max(float(width_m), min_cells * cell)
    reach = half + cell
    s_all = arc_length(p)
    a, b = p[:-1], p[1:]
    lo = np.minimum(a, b) - reach
    hi = np.maximum(a, b) + reach
    keep = ((hi[:, 0] >= level.x0) & (lo[:, 0] <= level.x0 + level.side) & (hi[:, 1] >= level.y0)
            & (lo[:, 1] <= level.y0 + level.side))
    d = np.full((n, n), np.inf)
    s = np.full((n, n), np.nan)
    for k in np.nonzero(keep)[0]:
        i0 = max(int(math.floor((lo[k, 0] - level.x0) / cell - 0.5)), 0)
        i1 = min(int(math.ceil((hi[k, 0] - level.x0) / cell - 0.5)) + 1, n)
        j0 = max(int(math.floor((lo[k, 1] - level.y0) / cell - 0.5)), 0)
        j1 = min(int(math.ceil((hi[k, 1] - level.y0) / cell - 0.5)) + 1, n)
        if i1 <= i0 or j1 <= j0:
            continue
        xs = level.x0 + (np.arange(i0, i1) + 0.5) * cell
        ys = level.y0 + (np.arange(j0, j1) + 0.5) * cell
        X, Y = np.meshgrid(xs, ys)
        v = b[k] - a[k]
        L2 = max(float(v @ v), 1e-12)
        t = np.clip(((X - a[k, 0]) * v[0] + (Y - a[k, 1]) * v[1]) / L2, 0.0, 1.0)
        dd = np.hypot(X - (a[k, 0] + t * v[0]), Y - (a[k, 1] + t * v[1]))
        sub = d[j0:j1, i0:i1]
        better = dd < sub
        sub[better] = dd[better]
        ss = s[j0:j1, i0:i1]
        ss[better] = (s_all[k] + t * math.sqrt(L2))[better]
    return d <= half, s, d


def schedule_at(schedule, t):
    """The schedule's value (fraction of the fall done) at time fraction t (piecewise linear, clamped)."""
    sch = np.asarray(schedule, np.float64)
    return float(np.interp(float(t), sch[:, 0], sch[:, 1]))


class River:
    """A course with its channel width, final bed profile and schedule (what 'river_path' keeps in ctx.shared).
    The bed at arc length s, at the fraction f of the fall done:
        bed(s, f) = top(s) - f (top(s) - final(s)),   final(s) = bed_m - gradient (s - s_through)
    top(s) is the starting surface along the course (sampled once, on the level where the run starts)."""

    def __init__(self, points, width_m, bed_m, gradient, schedule, s_through, top=None, spec=None):
        self.points = np.asarray(points, np.float64)
        self.s = arc_length(self.points)
        self.width_m = float(width_m)
        self.bed_m = float(bed_m)
        self.gradient = float(gradient)
        self.schedule = [list(map(float, r)) for r in schedule]
        self.s_through = float(s_through)
        self.top = None if top is None else np.asarray(top, np.float64)
        self.spec = dict(spec or {})

    def final(self, s):
        return self.bed_m - self.gradient * (np.asarray(s, np.float64) - self.s_through)

    def sample_top(self, level, h):
        """top(s): the surface h of `level` along the course (bilinear, clamped to the window)."""
        from ..core import grid as Gd
        self.top = Gd.sample_bilinear(np.asarray(h, np.float64), level.x0, level.y0, level.cell, self.points[:, 0],
                                      self.points[:, 1])
        return self.top

    def bed(self, s, f):
        fin = self.final(s)
        if self.top is None or f >= 1.0:
            return fin
        top = np.interp(np.asarray(s, np.float64), self.s, self.top)
        top = np.maximum(top, fin)
        return top - float(f) * (top - fin)

    def pins(self, level, base_pins, f, cache=None):
        """base_pins (pin_w, pin_h, A_in, qs_in dict) with the channel pinned at bed(s, f). `cache` (a dict) keeps
        the level's channel cells between calls."""
        key = (level.x0, level.y0, level.cell, level.n)
        if cache is not None and cache.get('key') == key:
            m, s = cache['mask'], cache['s']
        else:
            m, s, _ = channel(level, self.points, self.width_m)
            if cache is not None:
                cache.update(key=key, mask=m, s=s)
        out = dict(base_pins)
        w = np.array(base_pins['pin_w'], F32, copy=True)
        ph = np.array(base_pins['pin_h'], F32, copy=True)
        if m.any():
            w[m] = 1.0
            ph[m] = self.bed(s[m], f).astype(F32)
        out['pin_w'] = w
        out['pin_h'] = ph
        return out, m

    def to_dict(self):
        return dict(points=self.points.tolist(), width_m=self.width_m, bed_m=self.bed_m, gradient=self.gradient,
                    schedule=self.schedule, s_through=self.s_through,
                    top=None if self.top is None else self.top.tolist(), spec=self.spec)


def course(params, seed=0, extent_m=10000.0):
    """The course of a 'river_path' stage's parameters: (points (N, 2), s_through). extent_m is the coarsest
    level's side: a generated course runs three times that, a polyline is extended that far past its ends."""
    kind = _p(params, 'kind')
    s_seed = int(seed) + int(_p(params, 'seed'))
    through = tuple(float(v) for v in _p(params, 'through'))
    az = float(_p(params, 'flow_azimuth_deg'))
    length = float(_p(params, 'length_m') or 3.0 * float(extent_m))
    if kind == 'polyline':
        pts = np.asarray(_p(params, 'points'), np.float64)
        pts = extend(pts, float(extent_m) * 1.5)
        step = float(_p(params, 'step_m') or 5.0)
        pts = resample(pts, step)
    elif kind == 'walk':
        pts = walk(through, az, length, float(_p(params, 'wiggle_deg')), float(_p(params, 'wiggle_wavelength_m')),
                   s_seed, float(_p(params, 'step_m') or 10.0))
    elif kind == 'kinoshita':
        pts = kinoshita(through, az, length, float(_p(params, 'wavelength_m')), float(_p(params, 'sinuosity')),
                        _p(params, 'theta0_deg'), float(_p(params, 'skew')), float(_p(params, 'flat')),
                        float(_p(params, 'vary')), s_seed, _p(params, 'step_m'))
    else:
        raise ValueError(f"river_path kind {kind!r} is 'walk', 'kinoshita' or 'polyline'")
    s = arc_length(pts)
    d = np.hypot(pts[:, 0] - through[0], pts[:, 1] - through[1])
    return pts, float(s[int(np.argmin(d))])


def make_river(params, seed=0, extent_m=10000.0):
    pts, s0 = course(params, seed, extent_m)
    sch = _p(params, 'schedule')
    return River(pts, float(_p(params, 'width_m')), float(_p(params, 'bed_m')), float(_p(params, 'gradient')),
                 sch, s0, spec=dict(params or {}))


# ------------------------------------------------------------------------------------------------- the op ---

def op_river_path(fields, level, params, seed=0, ctx=None):
    """Stage 'river_path' (module doc): the course into ctx.shared['river'] (a River) and the level's pins with the
    channel at its final bed. On the fresh start of a run (the coarsest level's first pass) it also samples the
    starting surface along the course (the top the layered-rock stage lowers the bed from)."""
    from . import fluvial as FL
    ctx = ctx or FL.standalone_context(fields, level)
    extent = float(ctx.plan[0].side) if ctx.plan else float(level.side)
    rv = ctx.shared.get('river')
    if not isinstance(rv, River) or rv.spec != dict(params or {}) or getattr(rv, 'seed', None) != int(seed):
        rv = make_river(dict(params or {}), seed, extent)
        rv.seed = int(seed)
        ctx.shared['river'] = rv
    if ctx.fresh and 'h' in fields:
        rv.sample_top(level, fields['h'])
    base = ctx.pins if ctx.pins is not None else FL.edge_pins(level.n, np.asarray(fields['h'], F32)
                                                              if 'h' in fields else None, ctx.sea_level)
    ctx.pins, m = rv.pins(level, base, 1.0)
    fields['river'] = m.astype(F32)
    ctx.log(f"[terrain.rivers] {params.get('kind', DEFAULTS['kind'])} course, {rv.s[-1] / 1000:.1f} km, "
            f"channel {rv.width_m:g} m: {int(m.sum())} cells on {level.n}^2 @ {level.cell:.3g} m")
    return fields


op_river_path.evolves = True             # run.py: on every coarse-to-fine pass, so each pass gets its pins
OPS = {'river_path': op_river_path}
