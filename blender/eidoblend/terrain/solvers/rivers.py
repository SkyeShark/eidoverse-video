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
    centre 'course'              'kinoshita': 'course' puts the course itself through `through`; 'axis' puts the
                                 meander belt's centre line there (the train shifted across the valley, so the belt
                                 sits on the point whatever the bends' phase: through a loop's apex the whole belt
                                 lay one loop amplitude off it)
    flow_azimuth_deg 90          the down-valley direction, compass degrees (clockwise from north: 90 flows east)
    length_m None                the course's length (default: three times the coarsest level's side)
    wiggle_deg 12, wiggle_wavelength_m 3000     'walk': the direction's spread and the scale of its bends
    wavelength_m 1200            'kinoshita': the arc length of one meander (two bends)
    sinuosity 2.5 (or theta0_deg)  'kinoshita': arc length / down-valley length (theta0 is solved for it)
    skew 0.03, flat 0.0          'kinoshita': Js (bends lean downstream) and Jf (flattened, boxy bends)
    vary 0.15                    'kinoshita': the variation of the amplitude and wavelength along the course
    vary_scale 3.0, vary_skew 0  'kinoshita': the variation's scale in meander wavelengths (3: slow, neighbouring
                                 loops alike; about 1: every loop its own size), and the skew's variation (+-)
    min_neck_m 0                 'kinoshita': a loop whose limbs would pass closer than this (or cross) is shrunk
                                 until they do not: thin necks, never a closed or crossing loop (0: no check)
    growth 1.0, growth_stages 6  'kinoshita': the bends' amplitude when the base-level fall starts, as a fraction
                                 of the final; it grows to 1 over the fall, every bend keeping its down-valley place,
                                 so the channel sweeps outward while it cuts down (undercut outer walls, long slip-off
                                 slopes inside the loops: incised meanders' asymmetry); 1: a fixed course
    width_m 60                   the channel's width (at least 1.5 cells, so it is connected on every level)
    bed_m 0                      the final bed's height (relative h) at `through`
    gradient 0.0015              the bed's fall per metre downstream
    schedule [[0, 0], [1, 1]]    the base-level fall over the run (strata_fluvial): time fraction -> fraction of the
                                 way from the starting surface down to the final bed (piecewise linear)
    pool_spacing_m 0, pool_depth_m 0, pool_riffle 0.12, pool_jitter 0.35    pool and riffle (0: a smooth bed): the
                                 final bed steps down the valley as pools pool_spacing_m apart (each its own length,
                                 x exp(jitter N(0, 1))), each scoured pool_depth_m below the bed line and ending at
                                 its downstream lip, where a dry riffle (pool_riffle of the reach) runs down at the
                                 gradient to the next pool. Every pool is a closed basin spilling at its lip, so a
                                 recipe with defaults['lakes'] = 'lake' holds flat water in each, at its own level:
                                 the river reads as water, pool and drop, as a canyon river does (one connected strip
                                 of water would be one lake at one level)

The Kinoshita curve (Kinoshita 1961; Parker et al. 1983): the channel direction along arc length s is
    theta(s) = theta0 sin(k s) + theta0^3 (Js cos(3 k s) - Jf sin(3 k s)),   k = 2 pi / wavelength
whose sinuosity is 1 / mean(cos theta) (Langbein & Leopold's sine-generated curve when Js = Jf = 0). Numpy only.
"""
from __future__ import annotations

import math

import numpy as np

F32 = np.float32
DEFAULTS = dict(kind='walk', points=None, through=(0.0, 0.0), centre='course', flow_azimuth_deg=90.0, length_m=None,
                wiggle_deg=12.0, wiggle_wavelength_m=3000.0, wavelength_m=1200.0, sinuosity=2.5, theta0_deg=None,
                skew=0.03, flat=0.0, vary=0.15, vary_scale=3.0, vary_skew=0.0, min_neck_m=0.0, width_m=60.0,
                bed_m=0.0, gradient=0.0015, schedule=((0.0, 0.0), (1.0, 1.0)), step_m=None, seed=0, growth=1.0,
                growth_stages=6, pool_spacing_m=0.0, pool_depth_m=0.0, pool_riffle=0.12, pool_jitter=0.35)
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


def _place(local, through, flow_azimuth_deg, s, s0=0.0, anchor=None):
    """Rotate a course built along +x (down-valley) to the compass azimuth and move its arc-length origin s0 (or
    the local point `anchor`) onto `through`."""
    az = math.radians(float(flow_azimuth_deg))
    ux, uy = math.sin(az), math.cos(az)                  # compass: clockwise from north
    vx, vy = -uy, ux                                     # left of the flow
    k = int(np.argmin(np.abs(s - s0)))
    p = local - (local[k] if anchor is None else np.asarray(anchor, np.float64))
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


def _close_pairs(local, s, min_d, min_sep):
    """Index pairs (a, b), a < b, of course points closer than min_d whose arc lengths differ by more than min_sep
    (the two limbs of a loop or two loops), one pair (the closest) per 0.5 min_sep stretch of the arc. Points are
    binned on a min_d grid, so only neighbouring bins are compared."""
    stride = max(1, int(min_d / max(float(s[1] - s[0]), 1e-9) / 3.0))
    idx = np.arange(0, len(local), stride)
    p = local[idx]
    key = np.floor(p / min_d).astype(np.int64)
    bins = {}
    for k, (kx, ky) in enumerate(key):
        bins.setdefault((int(kx), int(ky)), []).append(k)
    best = {}
    for (kx, ky), members in bins.items():
        near = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near += bins.get((kx + dx, ky + dy), [])
        near = np.array(near)
        for k in members:
            other = near[near > k]
            if not len(other):
                continue
            ia, ib = idx[k], idx[other]
            far = (s[ib] - s[ia]) > min_sep
            if not far.any():
                continue
            d = np.hypot(*(local[ib[far]] - local[ia]).T)
            m = int(np.argmin(d))
            if d[m] < min_d:
                slot = int(s[ia] // (0.5 * min_sep))
                if slot not in best or d[m] < best[slot][0]:
                    best[slot] = (float(d[m]), int(ia), int(ib[far][m]))
    return [(a, b) for _d, a, b in best.values()]


def kinoshita(through, flow_azimuth_deg, length_m, wavelength_m=1200.0, sinuosity=2.5, theta0_deg=None, skew=0.03,
              flat=0.0, vary=0.15, seed=0, step_m=None, vary_scale=3.0, vary_skew=0.0, min_neck_m=0.0,
              centre='course'):
    """A meander train: the Kinoshita direction along the arc, its amplitude theta0 (from the sinuosity unless
    given) and its wavelength varying along the course by `vary` (relative) over vary_scale meander wavelengths
    (3: slowly, neighbouring loops alike; about 1: loop by loop, every loop its own size and shape), and its skew
    by +-vary_skew (some loops lean downstream, some up), so no two bends are alike. min_neck_m > 0: a loop whose
    limbs would come closer than that (or cross) has its amplitude shrunk until they do not, so the necks are thin
    but never closed. The course's down-valley length is about length_m. centre 'course': the course passes
    through `through`; 'axis': the belt's centre line does (the middle of the course's lateral spread within two
    down-valley wavelengths of the arc origin). (N, 2) world metres, upstream first."""
    th0 = math.radians(float(theta0_deg)) if theta0_deg is not None else theta0_for(sinuosity, skew, flat)
    sig = kinoshita_sinuosity(th0, skew, flat)
    arc = float(length_m) * sig
    step = float(step_m) if step_m else max(1.0, float(wavelength_m) / 160.0)
    n = max(int(math.ceil(arc / step)) + 1, 3)
    s = np.linspace(-0.5 * arc, 0.5 * arc, n)
    v = float(vary)
    sc = float(vary_scale)
    nl = _smooth_noise_1d(s, 1.1 * sc * float(wavelength_m), int(seed) + 17, octaves=2)
    na = _smooth_noise_1d(s, 0.9 * sc * float(wavelength_m), int(seed) + 29, octaves=2)
    lam = float(wavelength_m) * np.clip(1.0 + v * nl, 0.5, 1.6)
    phase = np.concatenate([[0.0], np.cumsum(2.0 * math.pi / (0.5 * (lam[1:] + lam[:-1])) * np.diff(s))])
    phase += np.random.default_rng(int(seed) * 31 + 7).uniform(0.0, 2.0 * math.pi)
    # amplitude variation, kept under the closing angle: past about 125 degrees the bends touch
    amp = np.clip(th0 * (1.0 + 0.6 * v * na), 0.0, math.radians(125.0))
    if float(vary_skew):
        skew = skew + float(vary_skew) * _smooth_noise_1d(s, 1.3 * sc * float(wavelength_m), int(seed) + 41,
                                                          octaves=1)
    ds = s[1] - s[0]
    mult = np.ones_like(s)
    neck = float(min_neck_m or 0.0)
    for _ in range(60):
        theta = kinoshita_theta(phase, amp * mult, skew, flat)
        local = _integrate(theta, ds)
        if neck <= 0.0:
            break
        pairs = _close_pairs(local, s, neck, 3.0 * neck)
        if not pairs:
            break
        # a loop whose limbs come closer than the neck: its amplitude shrinks a little (a smooth dip over the arc
        # between the two points), until every neck is at least min_neck_m wide
        for a, b in pairs:
            lo, hi = s[a], s[b]
            pad = 0.25 * (hi - lo) + 2.0 * ds
            t = np.clip(np.minimum(s - (lo - pad), (hi + pad) - s) / max(pad, 1e-9), 0.0, 1.0)
            mult = mult * (1.0 - 0.05 * t * t * (3.0 - 2.0 * t))
    # the mean direction of a varying train drifts a little: turn it back onto +x
    d = local[-1] - local[0]
    a = -math.atan2(d[1], d[0])
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    local = local @ R.T
    anchor = None
    if centre == 'axis':
        k0 = int(np.argmin(np.abs(s)))
        near = np.abs(local[:, 0] - local[k0, 0]) <= 2.0 * float(wavelength_m) / sig
        lat = local[near, 1]
        anchor = (float(local[k0, 0]), 0.5 * float(np.percentile(lat, 5) + np.percentile(lat, 95)))
    elif centre != 'course':
        raise ValueError(f"river_path centre {centre!r} is 'course' or 'axis'")
    return _place(local, through, flow_azimuth_deg, s, 0.0, anchor)


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
        bed(s, f) = top(s) - f (top(s) - final(s)),   final(s) = bed_m - gradient (s - s_through) - pool(s)
    top(s) is the starting surface along the course (sampled once, on the level where the run starts). pool(s) is
    the pool-and-riffle scour (pool_spacing_m, pool_depth_m; 0 without pools): on the hero levels it is the full
    pool depth everywhere (a smooth trench under the pools' water, never a closed basin: a pool crossing a hero
    window's border band would be filled with sediment there, so the hero levels take each pool's water from their
    parent instead, cell by cell; the parent's dry riffles part the pools).
    stages: [(f, points, s_through), ...] a growing course (growth < 1): the course used at a fall fraction f is the
    last stage whose f is at most it; the final course is `points`."""

    def __init__(self, points, width_m, bed_m, gradient, schedule, s_through, top=None, spec=None, stages=None,
                 seed=0):
        self.width_m = float(width_m)
        self.bed_m = float(bed_m)
        self.gradient = float(gradient)
        self.schedule = [list(map(float, r)) for r in schedule]
        self.spec = dict(spec or {})
        self.pool = (float(_p(self.spec, 'pool_spacing_m') or 0.0), float(_p(self.spec, 'pool_depth_m') or 0.0),
                     float(_p(self.spec, 'pool_riffle')), float(_p(self.spec, 'pool_jitter')))
        self.pool_seed = int(seed)
        self._crest_cache = None
        self.final_course = (np.asarray(points, np.float64), float(s_through))
        self.stages = [(float(f), np.asarray(p, np.float64), float(s0)) for f, p, s0 in (stages or [])]
        self.top_field = None
        self._use(self.final_course[0], self.final_course[1])
        self.top = None if top is None else np.asarray(top, np.float64)

    def crests(self):
        """The riffles' crests (the pools' downstream lips), arc lengths along the final course, ascending: one every
        pool_spacing_m x exp(pool_jitter N(0, 1)) (clipped to 0.5-2 spacings), from the course's start to its end,
        the same on every level (world arc length, a seeded draw)."""
        sp = self.pool[0]
        if sp <= 0.0:
            return None
        if self._crest_cache is None:
            s_end = float(arc_length(self.final_course[0])[-1])
            rng = np.random.default_rng(self.pool_seed * 4421 + 613)
            n = int(s_end / (0.5 * sp)) + 4
            steps = sp * np.clip(np.exp(self.pool[3] * rng.standard_normal(n)), 0.5, 2.0)
            c = -sp * rng.uniform(0.0, 1.0) + np.concatenate([[0.0], np.cumsum(steps)])
            self._crest_cache = c[c <= s_end + 2.0 * sp]
        return self._crest_cache

    def pool_scour(self, s):
        """0..1 along the final course: 0 on the riffles and at every pool's lip, rising quickly below a riffle to the
        pool's deepest point (a third of the way down it) and back to 0 at its lip."""
        c = self.crests()
        s = np.asarray(s, np.float64)
        if c is None or len(c) < 2:
            return np.zeros_like(s)
        k = np.clip(np.searchsorted(c, s, side='right') - 1, 0, len(c) - 2)
        u = np.clip((s - c[k]) / (c[k + 1] - c[k]), 0.0, 1.0)
        r = min(max(self.pool[2], 0.0), 0.9)
        v = np.clip((u - r) / (1.0 - r), 0.0, 1.0)
        return np.where(u > r, np.sin(math.pi * v ** 0.75) ** 0.6, 0.0)

    def final(self, s, smooth=False):
        """The final bed at arc length s: the bed line minus the pool scour (smooth: minus the full pool depth, the
        hero levels' trench)."""
        line = self.bed_m - self.gradient * (np.asarray(s, np.float64) - self.s_through)
        depth = self.pool[1] if self.pool[0] > 0.0 else 0.0
        if depth <= 0.0:
            return line
        return line - depth * (1.0 if smooth else self.pool_scour(s))

    def _use(self, points, s_through):
        self.points = points
        self.s = arc_length(points)
        self.s_through = s_through
        self.top = None
        if self.top_field is not None:
            self._sample()

    def course_at(self, f):
        """Switch to the course of fall fraction f (a growing river); True when it changed."""
        if not self.stages:
            return False
        pick = self.final_course
        if f < 1.0 - 1e-9:
            for fk, p, s0 in self.stages:
                if fk <= f + 1e-9:
                    pick = (p, s0)
        if pick[0] is self.points:
            return False
        self._use(*pick)
        return True

    def _sample(self):
        from ..core import grid as Gd
        h, x0, y0, cell = self.top_field
        self.top = Gd.sample_bilinear(h, x0, y0, cell, self.points[:, 0], self.points[:, 1])

    def sample_top(self, level, h):
        """top(s): the surface h of `level` along the course (bilinear, clamped to the window); kept, so a growing
        course's later stages sample the same starting surface."""
        self.top_field = (np.asarray(h, np.float64), level.x0, level.y0, level.cell)
        self._sample()
        return self.top

    def bed(self, s, f, smooth=False):
        fin = self.final(s, smooth)
        if self.top is None or f >= 1.0:
            return fin
        top = np.interp(np.asarray(s, np.float64), self.s, self.top)
        top = np.maximum(top, fin)
        return top - float(f) * (top - fin)

    def pins(self, level, base_pins, f, cache=None, hold=None):
        """base_pins (pin_w, pin_h, A_in, qs_in dict) with the channel pinned at bed(s, f). `cache` (a dict) keeps
        the level's channel cells between calls. hold: a child level's border-band weights (1 at its edge, 0 from
        16 cells in): there the channel's pin eases from the parent's surface (the base pin) to the bed, so the
        channel meets its parent's coarser channel at the seam exactly (the bed alone left steps of up to 18 m
        where the two channels' margins fall on different cells)."""
        self.course_at(f)
        key = (level.x0, level.y0, level.cell, level.n, id(self.points))
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
            bed = self.bed(s[m], f, smooth=getattr(level, 'role', None) == 'hero')
            if hold is not None:
                wb = np.clip(np.asarray(hold, np.float64)[m], 0.0, 1.0)
                bed = wb * np.asarray(base_pins['pin_h'], np.float64)[m] + (1.0 - wb) * bed
            w[m] = 1.0
            ph[m] = bed.astype(F32)
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
                        float(_p(params, 'vary')), s_seed, _p(params, 'step_m'), float(_p(params, 'vary_scale')),
                        float(_p(params, 'vary_skew')), float(_p(params, 'min_neck_m') or 0.0),
                        str(_p(params, 'centre')))
    else:
        raise ValueError(f"river_path kind {kind!r} is 'walk', 'kinoshita' or 'polyline'")
    s = arc_length(pts)
    d = np.hypot(pts[:, 0] - through[0], pts[:, 1] - through[1])
    return pts, float(s[int(np.argmin(d))])


def growth_courses(params, seed=0, extent_m=10000.0):
    """A growing Kinoshita course's stages [(f, points, s_through)]: the bend amplitude theta0 from growth x its
    final value to the final, the arc wavelength scaled with the sinuosity so every bend keeps its down-valley place
    (the train's noise is a function of arc length over wavelength, so it is the same bend by bend)."""
    g0 = float(_p(params, 'growth'))
    k = max(int(_p(params, 'growth_stages')), 2)
    if _p(params, 'kind') != 'kinoshita' or g0 >= 1.0:
        return []
    skew, flat = float(_p(params, 'skew')), float(_p(params, 'flat'))
    th_f = (math.radians(float(_p(params, 'theta0_deg'))) if _p(params, 'theta0_deg') is not None else
            theta0_for(float(_p(params, 'sinuosity')), skew, flat))
    sig_f = kinoshita_sinuosity(th_f, skew, flat)
    wl_dv = float(_p(params, 'wavelength_m')) / sig_f
    out = []
    for i in range(k - 1):                                   # the last stage is the final course itself
        f = i / (k - 1)
        th = th_f * (g0 + (1.0 - g0) * f)
        sig = kinoshita_sinuosity(th, skew, flat)
        p = dict(params or {}, theta0_deg=math.degrees(th), wavelength_m=wl_dv * sig, growth=1.0)
        pts, s0 = course(p, seed, extent_m)
        out.append((f, pts, s0))
    return out


def make_river(params, seed=0, extent_m=10000.0):
    pts, s0 = course(params, seed, extent_m)
    sch = _p(params, 'schedule')
    return River(pts, float(_p(params, 'width_m')), float(_p(params, 'bed_m')), float(_p(params, 'gradient')),
                 sch, s0, spec=dict(params or {}), stages=growth_courses(params, seed, extent_m),
                 seed=int(seed) + int(_p(params, 'seed')))


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
    # a child level (its pins are its parent's border band): the channel eases into the parent's at the seam
    ctx.pins, m = rv.pins(level, base, 1.0, hold=base['pin_w'] if ctx.role == 'refine' else None)
    fields['river'] = m.astype(F32)
    ctx.log(f"[terrain.rivers] {params.get('kind', DEFAULTS['kind'])} course, {rv.s[-1] / 1000:.1f} km, "
            f"channel {rv.width_m:g} m: {int(m.sum())} cells on {level.n}^2 @ {level.cell:.3g} m")
    return fields


op_river_path.evolves = True             # run.py: on every coarse-to-fine pass, so each pass gets its pins
OPS = {'river_path': op_river_path}
