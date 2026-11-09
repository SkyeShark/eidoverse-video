"""Karst towers: fenglin (towers and peak clusters on a river plain, Guilin) and fengcong (cones packed over closed,
flat-floored cockpits). Design section 4.10.

Every input is a function of world position in metres. One global plan, built once on the CPU over the outermost
level's window, holds the tower centres, each tower's shape numbers and the river course. Every level evaluates that
plan at its own cells, so:
  - the walls stay sharp on a 0.5 m hero level (they are never upsampled from a coarser level);
  - a 31 m horizon level shows the same massifs, anti-aliased by 2 x 2 supersampling;
  - a child level matches its parent where they overlap, up to the octaves only the child resolves.

Frames and units (design 2.1): metres and degrees; arrays [row j, column i] with row 0 the south edge; a cell centre
is at x = x0 + (i + 0.5) cell, y = y0 + (j + 0.5) cell.

    plan = plan_karst(seed=7, domain=(-16000.0, -16000.0, 32000.0), params={'kind': 'fenglin'}, via=(0.0, 0.0),
                      main=(-4000.0, -4000.0, 8000.0))
    out = evaluate(plan, x0=-4000.0, y0=-4000.0, cell=7.8125, n=1024)
    out['h'], out['bed'], out['deposit'], out['river'], out['Sc']      # float32 (n, n)

The plan:
  - a cluster field (broad noise mixed with ridged noise, stretched along the joint strike): the peak clusters as
    elongated massifs, the rest plain; its threshold makes cluster_cover the main tile's share in clusters;
  - centres by variable-radius Poisson-disc (poisson_disc): spacing_m apart inside the clusters, 2.5 times that on
    the plain, the plain's then thinned to plain_density (isolated towers);
  - heights lognormal around median_height_m, times a world-space trend so neighbours are alike.
Two kinds of tower, blended by cluster membership:
  - an isolated (fenglin) tower: profile z = T (1 - (r/R)^p)^(1/q) with p 2-4.5 (Guilin's domed sugarloaf) and q
    1.7-2.4 (the steepened, near-vertical foot that stands in for the undercut notch: a heightfield can't overhang);
    R solved so the wall's chord angle between 15 % and 85 % of T is 70-85 degrees (radius_for_wall), held to the
    design's 0.3-0.6 H; a short concave talus apron;
  - a cluster (fengcong) peak: a steep cone, its wall chord 55-70 degrees (photographs; the radar reference can't
    hold walls, see the report), with a long footslope toe that fills its share of the massif out to fill x the
    median distance to its three nearest neighbours, so neighbours meet at cols whatever their heights;
  - every footprint elongated along the strike, leaning, given radial spurs (harmonics 2-5) and lobed by world
    noise; summits roughened by world noise; on levels with cells of 2 m or less, vertical fluting: a radial offset
    that depends only on the direction from the tower's axis, so the grooves run straight down the wall.
Composition: every tower by max over the plain; the plain is flat alluvium tilted along a river that winds through
it (a least-cost course around the clusters, with meanders), cut 3.5 m into it; where peaks ring a gap, the gap is a
closed depression (a cockpit, star-shaped), and soil fills its bottom flat (cockpit_fill of its depth): the one
family where closed depressions are correct. fengcong raises the clusters on a common base (plinth_m).

The stage op `karst` (op_karst) writes h, bed (the rock: towers, and the buried rock under the alluvium and the
cockpit soil), deposit (h - bed) and Sc (limestone at 75 degrees +- 8 %) on a level. The river's channel is carved
into h; its water is not written: the `water` field is lake and sea depth (design 2.4, 6), which the lake builder
draws as flat sheets, and a river slopes (its ribbon is the water family's, later); evaluate() returns its depth as
`river`. The recipe tower_karst then runs the threshold pass and light creep (package 3's). Needs numpy only, so it
runs in Blender's Python and in plain Python tests.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import numpy as np

__all__ = ['DEFAULTS', 'KIND_PRESETS', 'KarstPlan', 'params_for', 'tower_profile', 'wall_chord_deg',
           'radius_for_wall', 'poisson_disc', 'plan_karst', 'cached_plan', 'evaluate', 'op_karst', 'noise2',
           'fbm2', 'supersampling_for', 'OPS']

# ---------------------------------------------------------------- parameters (metres, degrees)
DEFAULTS = dict(
    kind='fenglin',              # 'fenglin' (towers on a river plain) | 'fengcong' (cones over dolines)
    spacing_m=180.0,             # Poisson-disc spacing of the peaks inside the clusters (about their neighbour gap)
    satellites=0.0,              # satellite peaks between the peaks: their height share (0: none)
    satellite_spacing=0.55,      # their Poisson-disc spacing, a multiple of spacing_m
    median_height_m=125.0,       # median summit height above the plain
    height_sigma=0.30,           # lognormal spread of the heights (natural log)
    height_trend=0.30,           # world-space height trend (2 km scale, natural-log amplitude): neighbours alike
    wall_deg=78.0,               # isolated towers on the plain: wall chord angle, 15 % -> 85 % of the height
    cone_wall_deg=(55.0, 70.0),  # a cluster peak's wall chord angle range (drawn per peak; photographs, not radar)
    fill=0.9,                    # a cluster peak's whole footprint (cone and toe): x the median gap to 3 neighbours
    wall_spread_deg=4.0,         # per-tower spread of the wall angle (normal)
    profile_p=(2.0, 4.5),        # towers' shoulder exponent (low: domed sugarloaf; high: flat-topped column)
    profile_q=(1.7, 2.4),        # towers' foot exponent (2: vertical foot)
    cone_p=(1.1, 1.8),           # cluster peaks' shoulder exponent (1: a pointed cone; higher: rounder summits)
    cone_q=(1.2, 1.6),           # cluster peaks' foot exponent (above 1: the lower wall steepens)
    spurs=0.08,                  # radial spurs: the largest amplitude of azimuthal harmonics 2-5 of the footprint
    plinth_m=0.0,                # the clusters' common base (fengcong 50-150): the cockpit floors between the peaks
    apron=0.08,                  # an isolated tower's talus apron: share of its height, reaching 0.35 R
    toe=0.28,                    # a cluster peak's toe (footslope): share of its height; it reaches out to fill
    toe_shape=1.3,               # the toe's profile exponent: 2 concave (talus), toward 1 straight (higher cols)
    cluster_cover=0.80,          # fraction of the main tile inside peak clusters (the rest is plain)
    cluster_scale_m=2600.0,      # wavelength of the cluster / plain pattern
    cluster_ridges=0.65,         # share of ridged noise in it: massifs as elongated ridges with peaks along them
    ridge_scale_m=1500.0,        # the ridges' wavelength (about twice their spacing)
    cluster_stretch=2.2,         # the pattern's elongation along the joint strike
    strike_deg=115.0,            # joint strike, compass degrees: clusters, towers and plains elongate along it
    plain_density=0.06,          # share of the plain's blue-noise points kept as isolated towers
    plain_spacing=2.5,           # their Poisson radius, a multiple of the clusters' radius
    elongation=0.30,             # max footprint elongation along the strike
    lean=0.22,                   # max footprint offset (one wall steeper than the other)
    lobes_m=9.0,                 # footprint lobing: radial displacement by world noise (130 m and 60 m), std metres
    summit_noise=0.08,           # summit irregularity, std as a fraction of the tower's height
    cockpit_fill=0.7,            # soil filling each cockpit (closed depression between peaks) flat: share of its depth
    river=True,                  # a river winding through the plain
    river_width_m=90.0,
    river_depth_m=4.0,
    river_bank_m=3.5,            # bank height above the water
    river_meander=2.4,           # meander amplitude, a multiple of the width
    river_azimuth_deg=None,      # flow direction, compass degrees (None: from the seed)
    plain_tilt_m_per_km=0.25,    # the plain falls along the river
    plain_rise_m=4.0,            # and rises this much away from it, over 1.5 km
    plain_micro_m=0.35,          # alluvial micro-relief (std)
    alluvium_m=12.0,             # alluvium over the buried rock of the plain
    fluting_m=0.9,               # vertical fluting depth on the walls (levels with cells <= 2 m)
    sc_deg=75.0,                 # limestone threshold angle written to Sc (the threshold pass reads it)
    sc_noise=0.08,               # its relative noise (50 m scale)
)

KIND_PRESETS = {
    'fenglin': dict(),
    'fengcong': dict(spacing_m=230.0, median_height_m=200.0, height_sigma=0.22, height_trend=0.2,
                     cone_wall_deg=(50.0, 66.0), plinth_m=20.0, toe=0.3, fill=1.0, cluster_cover=0.97,
                     cluster_ridges=0.3, plain_density=0.0, elongation=0.22, lean=0.18, river=False),
}


def params_for(params=None):
    """The full parameter dict: DEFAULTS, then the kind's preset, then the caller's values."""
    params = dict(params or {})
    kind = params.get('kind', DEFAULTS['kind'])
    if kind not in KIND_PRESETS:
        raise ValueError(f"karst kind {kind!r}: use one of {sorted(KIND_PRESETS)}")
    unknown = sorted(set(params) - set(DEFAULTS))
    if unknown:
        raise ValueError(f'unknown karst parameter(s) {unknown}; known: {sorted(DEFAULTS)}')
    out = dict(DEFAULTS)
    out.update(KIND_PRESETS[kind])
    out.update(params)
    return out


# ---------------------------------------------------------------- world-space gradient noise
_GX16 = np.cos(np.arange(16) * (2 * math.pi / 16))
_GY16 = np.sin(np.arange(16) * (2 * math.pi / 16))


def _pcg(v):
    """32-bit PCG hash (Jarzynski & Olano 2020) on uint32 arrays (the multiplies wrap mod 2^32)."""
    s = v * np.uint32(747796405) + np.uint32(2891336453)
    w = ((s >> ((s >> np.uint32(28)) + np.uint32(4))) ^ s) * np.uint32(277803737)
    return (w >> np.uint32(22)) ^ w


def _hash2(ix, iy, salt):
    """uint32 hash of integer lattice coordinates (any sign) and a salt."""
    a = (np.asarray(ix, np.int64) & 0xFFFFFFFF).astype(np.uint32)
    b = (np.asarray(iy, np.int64) & 0xFFFFFFFF).astype(np.uint32)
    return _pcg(a + _pcg(b + np.uint32(salt & 0xFFFFFFFF)))


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def noise2(x, y, wavelength, salt):
    """2-D gradient noise of world metres x, y at a wavelength in metres: about -1..1, std about 0.3. The corner
    gradients are hashed once per lattice point of the block the samples cover, then gathered."""
    gx = np.asarray(x, np.float64) / wavelength
    gy = np.asarray(y, np.float64) / wavelength
    if gx.ndim == 2 and gy.ndim == 2 and gx.shape[0] == 1 and gy.shape[1] == 1:
        return _noise2_separable(gx[0], gy[:, 0], salt)
    gx, gy = np.broadcast_arrays(gx, gy)
    fx0, fy0 = np.floor(gx), np.floor(gy)
    fx, fy = gx - fx0, gy - fy0
    ix, iy = fx0.astype(np.int64), fy0.astype(np.int64)
    if ix.size == 0:
        return np.zeros(ix.shape)
    ix0, iy0 = int(ix.min()), int(iy.min())
    bw, bh = int(ix.max()) - ix0 + 2, int(iy.max()) - iy0 + 2
    if bw * bh <= max(4 * ix.size, 4096):
        lat = _hash2(np.arange(ix0, ix0 + bw)[None, :], np.arange(iy0, iy0 + bh)[:, None], salt) & np.uint32(15)
        gxl, gyl = _GX16[lat], _GY16[lat]
        li, lj = ix - ix0, iy - iy0

        def corner(di, dj):
            return gxl[lj + dj, li + di] * (fx - di) + gyl[lj + dj, li + di] * (fy - dj)
    else:
        def corner(di, dj):
            k = _hash2(ix + di, iy + dj, salt) & np.uint32(15)
            return _GX16[k] * (fx - di) + _GY16[k] * (fy - dj)
    ux, uy = _fade(fx), _fade(fy)
    n00, n10, n01, n11 = corner(0, 0), corner(1, 0), corner(0, 1), corner(1, 1)
    a = n00 + (n10 - n00) * ux
    b = n01 + (n11 - n01) * ux
    return (a + (b - a) * uy) * 1.41


def _noise2_separable(gx, gy, salt):
    """noise2 on the grid of lattice coordinates gx (columns) x gy (rows): row and column gathers only."""
    fx0, fy0 = np.floor(gx), np.floor(gy)
    fx, fy = gx - fx0, gy - fy0
    ix, iy = fx0.astype(np.int64), fy0.astype(np.int64)
    ix0, iy0 = int(ix.min()), int(iy.min())
    bw, bh = int(ix.max()) - ix0 + 2, int(iy.max()) - iy0 + 2
    lat = _hash2(np.arange(ix0, ix0 + bw)[None, :], np.arange(iy0, iy0 + bh)[:, None], salt) & np.uint32(15)
    gxl, gyl = _GX16[lat], _GY16[lat]
    li, lj = ix - ix0, iy - iy0

    def corner(di, dj):
        a = np.take(np.take(gxl, lj + dj, axis=0), li + di, axis=1)
        b = np.take(np.take(gyl, lj + dj, axis=0), li + di, axis=1)
        return a * (fx - di)[None, :] + b * (fy - dj)[:, None]
    ux, uy = _fade(fx)[None, :], _fade(fy)[:, None]
    n00, n10, n01, n11 = corner(0, 0), corner(1, 0), corner(0, 1), corner(1, 1)
    a = n00 + (n10 - n00) * ux
    b = n01 + (n11 - n01) * ux
    return (a + (b - a) * uy) * 1.41


def _noise1_periodic(s, period, salt):
    """1-D gradient noise of lattice coordinate s, periodic with `period` lattice cells (an integer): about -1..1."""
    i = np.floor(s)
    f = s - i
    i = i.astype(np.int64)
    P = max(int(period), 1)
    g = _hash2(np.arange(P), np.zeros(P, np.int64), salt).astype(np.float64) / 2147483648.0 - 1.0
    d0 = g[np.mod(i, P)] * f
    d1 = g[np.mod(i + 1, P)] * (f - 1.0)
    return 2.0 * (d0 + (d1 - d0) * _fade(f))


def fbm2(x, y, wavelength, octaves, salt, gain=0.5, min_wavelength=0.0):
    """Octaves of noise2, halving the wavelength each time; octaves shorter than min_wavelength (the level's
    resolution limit) are left out, so a coarse level gets the band-limited version of the same field."""
    out = np.zeros(np.broadcast(np.asarray(x), np.asarray(y)).shape, np.float64)
    a, lam = 1.0, float(wavelength)
    for k in range(octaves):
        if lam >= min_wavelength:
            out += a * noise2(x, y, lam, salt + 7919 * k)
        a *= gain
        lam *= 0.5
    return out


def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the tower profile
def tower_profile(u, p, q):
    """z / H at normalised radius u = r / R: (1 - u^p)^(1/q) inside the foot, 0 beyond it (design 4.10)."""
    u = np.clip(np.asarray(u, np.float64), 0.0, 1.0)
    return np.maximum(1.0 - u ** p, 0.0) ** (1.0 / q)


def _u_at(f, p, q):
    """The normalised radius where the profile stands at f (0..1) of the height."""
    return (1.0 - np.asarray(f, np.float64) ** q) ** (1.0 / p)


def wall_chord_deg(p, q, r_over_h, lo=0.15, hi=0.85):
    """The wall's chord angle in degrees between lo and hi of the height, for a footprint R = r_over_h H."""
    du = _u_at(lo, p, q) - _u_at(hi, p, q)
    return np.degrees(np.arctan((hi - lo) / (du * np.asarray(r_over_h, np.float64))))


def radius_for_wall(p, q, wall_deg, lo=0.15, hi=0.85):
    """R / H that gives the wall chord angle wall_deg (degrees) between lo and hi of the height."""
    du = _u_at(lo, p, q) - _u_at(hi, p, q)
    return (hi - lo) / (du * np.tan(np.radians(np.asarray(wall_deg, np.float64))))


# ---------------------------------------------------------------- blue noise
def poisson_disc(seed, x0, y0, width, height, radius_fn, r_min, r_max, tries=8, throw=0.3):
    """Variable-radius Poisson-disc points in [x0, x0 + width) x [y0, y0 + height) metres, by phase-group parallel
    dart throwing on a background grid of cell r_min / sqrt(2) (one point per cell at most). Cells of one phase are
    more than r_max apart, so their darts never conflict and each phase is one vectorised step. In each phase a live
    cell throws only with probability `throw`: were every cell of the first phase to throw, its points would be a
    jittered lattice that the later phases fill around, and the set would keep the grid's axes (a 4-fold bias in the
    directions between neighbours). Two points conflict when closer than the larger of their radii; a cell retires
    after `tries` rejected darts (Bridson's k), so the set is near-maximal. radius_fn(x, y) -> metres, between r_min
    and r_max. Returns (x, y, r) float64 arrays; deterministic for a seed and window."""
    rng = np.random.default_rng(seed)
    g = r_min / math.sqrt(2.0)
    nx, ny = int(math.ceil(width / g)), int(math.ceil(height / g))
    k = int(math.ceil(r_max / g))
    P = k + 1
    pad = k
    GX = np.full((ny + 2 * pad, nx + 2 * pad), np.nan)
    GY = np.full_like(GX, np.nan)
    GR = np.full_like(GX, np.nan)
    fails = np.zeros((ny, nx), np.int32)
    off = np.arange(-k, k + 1)
    oj, oi = np.meshgrid(off, off, indexing='ij')
    near = (np.maximum(np.abs(oj), np.abs(oi)) - 1) * g < r_max        # neighbour cells that can hold a conflict
    oj, oi = oj[near], oi[near]
    jj, ii = np.meshgrid(np.arange(ny), np.arange(nx), indexing='ij')
    phases = [(jj[a::P, b::P].ravel(), ii[a::P, b::P].ravel()) for a in range(P) for b in range(P)]
    for _ in range(int(math.ceil((tries + 2) / throw)) + 4):
        added = 0
        for n_, (pj, pi) in enumerate(phases):
            live = np.isnan(GX[pj + pad, pi + pad]) & (fails[pj, pi] < tries)
            pj, pi = pj[live], pi[live]
            phases[n_] = (pj, pi)
            pick = rng.random(pj.size) < throw
            cj, ci = pj[pick], pi[pick]
            added += int(pj.size)
            if cj.size == 0:
                continue
            dx = x0 + (ci + rng.random(ci.size)) * g
            dy = y0 + (cj + rng.random(cj.size)) * g
            inside = (dx < x0 + width) & (dy < y0 + height)
            rd = np.asarray(radius_fn(dx, dy), np.float64)
            nj = cj[:, None] + pad + oj[None, :]
            ni = ci[:, None] + pad + oi[None, :]
            qx, qy, qr = GX[nj, ni], GY[nj, ni], GR[nj, ni]
            d2 = (qx - dx[:, None]) ** 2 + (qy - dy[:, None]) ** 2
            lim = np.maximum(qr, rd[:, None])
            clash = np.any(d2 < lim * lim, axis=1)                      # NaN (an empty cell) compares False
            ok = inside & ~clash
            GX[cj[ok] + pad, ci[ok] + pad] = dx[ok]
            GY[cj[ok] + pad, ci[ok] + pad] = dy[ok]
            GR[cj[ok] + pad, ci[ok] + pad] = rd[ok]
            fails[cj[~ok], ci[~ok]] += 1
        if added == 0:                                                   # no live cell left
            break
    m = ~np.isnan(GX)
    return GX[m], GY[m], GR[m]


# ---------------------------------------------------------------- the plan
@dataclass
class KarstPlan:
    """Everything global about one karst terrain: the parameters, the cluster field, the towers and the river.
    Tower arrays are float64, one entry per tower; angles in radians from +x, counter-clockwise."""
    seed: int
    domain: tuple
    params: dict
    salt: int
    strike: float
    cluster_threshold: float
    cluster_band: float
    cluster_std: float = 1.0
    x: np.ndarray = None
    y: np.ndarray = None
    H: np.ndarray = None              # summit height above the plain, metres
    F: np.ndarray = None              # the common base's height under the tower's foot, metres (cluster peaks)
    B: np.ndarray = None              # the talus apron's height at the tower's foot, metres (isolated towers)
    T: np.ndarray = None              # the tower's own height above its foot and apron (H - F - B), metres
    R: np.ndarray = None              # the tower's footprint radius, metres
    reach: np.ndarray = None          # the apron's reach past the foot, metres
    p: np.ndarray = None
    q: np.ndarray = None
    wall: np.ndarray = None           # wall chord angle, degrees
    elong: np.ndarray = None
    axis: np.ndarray = None
    lean: np.ndarray = None
    lean_dir: np.ndarray = None
    cluster: np.ndarray = None        # cluster membership at the centre, 0..1
    interior: np.ndarray = None       # how deep inside its cluster, 0..1
    spur: np.ndarray = None           # (N, 4) complex: amplitude and phase of footprint harmonics 2, 3, 4, 5
    major: np.ndarray = None          # True for the major peaks and isolated towers, False for satellites
    river: np.ndarray = None          # (N, 2) polyline in metres, upstream first; None without a river
    river_coarse: np.ndarray = None   # the same, resampled at 40 m (the plain's far field, tower clearance)
    river_mid: np.ndarray = None      # the same, resampled at 30 m (the channel; chord error < 0.6 m on its bends)
    river_dir: tuple = (1.0, 0.0)
    stats: dict = field(default_factory=dict)

    @property
    def count(self):
        return 0 if self.x is None else int(self.x.size)


def _cluster_raw(salt, pr, strike, x, y):
    """The un-thresholded cluster field, stretched along the strike: broad noise (where the massifs and the plains
    are) mixed with ridged noise (the massifs as elongated ridges, peaks strung along their crests)."""
    c, s = math.cos(strike), math.sin(strike)
    u = (x * c + y * s) / pr['cluster_stretch']
    v = -x * s + y * c
    broad = fbm2(u, v, pr['cluster_scale_m'], 3, salt + 11, gain=0.5) / 0.3
    a = pr['cluster_ridges']
    if a <= 0:
        return broad
    n = noise2(u, v, pr['ridge_scale_m'], salt + 13) + 0.35 * noise2(u, v, 0.5 * pr['ridge_scale_m'], salt + 17)
    ridged = (1.0 - np.abs(n) / 0.45) * 1.6               # about unit std, high along the zero lines of n
    return (1.0 - a) * broad + a * ridged


def _cluster(plan, x, y):
    """(membership 0..1, raw field) at world points: 1 inside the clusters, 0 on the plain."""
    raw = _cluster_raw(plan.salt, plan.params, plan.strike, x, y)
    return _smoothstep(plan.cluster_threshold - plan.cluster_band, plan.cluster_threshold + plan.cluster_band, raw), raw


def _plinth_of(plan, x, y):
    """The clusters' common base at full height (metres above the plain): plinth_m, varying +-25 % at 1.5 km."""
    return plan.params['plinth_m'] * np.maximum(1.0 + 0.25 * fbm2(x, y, 1500.0, 2, plan.salt + 31) / 0.3, 0.3)


def _interior_of(plan, raw):
    """How deep inside its cluster a point is (0 at the edge, 1 well inside), from the raw cluster field."""
    t0 = plan.cluster_threshold + plan.cluster_band
    return _smoothstep(t0, t0 + 0.9 * plan.cluster_std, raw)


def _compass_to_rad(deg):
    """Compass degrees (0 north, clockwise) to radians from +x, counter-clockwise."""
    return math.radians(90.0 - deg)


def plan_karst(seed, domain, params=None, via=None, main=None):
    """The global plan over domain = (x0, y0, side) metres (the outermost level's window): the cluster field's
    threshold, the river course (passing near `via`, default the domain's centre), the blue-noise tower centres and
    every tower's shape numbers. main = (x0, y0, side), the main tile: cluster_cover is then the share of the main
    tile in clusters (else of the domain; a 2.6 km pattern puts few clusters in one tile, so a tile's own share
    would wander by seed). Deterministic for (seed, domain, params, via, main)."""
    pr = params_for(params)
    x0, y0, side = (float(v) for v in domain)
    salt = (int(seed) * 2654435761 + 97) & 0xFFFFFFF
    rng = np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x4B41525354])     # 'KARST'
    strike = _compass_to_rad(pr['strike_deg'])
    plan = KarstPlan(seed=int(seed), domain=(x0, y0, side), params=pr, salt=salt, strike=strike,
                     cluster_threshold=0.0, cluster_band=1.0)

    # the cluster field's threshold: the (1 - cover) quantile over the main tile (or the domain)
    n = 192
    mx0, my0, mside = (float(v) for v in (main if main is not None else domain))
    g = mx0 + (np.arange(n) + 0.5) * mside / n
    GX, GY = np.meshgrid(g, my0 + (np.arange(n) + 0.5) * mside / n)
    raw = _cluster_raw(salt, pr, strike, GX, GY)
    cover = float(np.clip(pr['cluster_cover'], 0.0, 1.0))
    if cover >= 1.0:
        plan.cluster_threshold = float(raw.min()) - 1.0
    elif cover <= 0.0:
        plan.cluster_threshold = float(raw.max()) + 1.0
    else:
        plan.cluster_threshold = float(np.quantile(raw, 1.0 - cover))
    plan.cluster_std = float(raw.std())
    plan.cluster_band = 0.12 * plan.cluster_std

    # the river: a least-cost course through the plain, then meanders
    if pr['river']:
        plan.river, plan.river_dir = _river_course(plan, rng, via)
        plan.river_coarse, _ = _resample(plan.river, 40.0)
        plan.river_mid, _ = _resample(plan.river, 30.0)

    # tower centres, two classes. Major peaks: Poisson-disc at spacing_m in the clusters and plain_spacing times
    # that on the plain, the plain's then thinned to plain_density. Satellites: a second Poisson-disc set at
    # satellite_spacing times spacing_m, inside the clusters only, kept clear of the major peaks: the lower peaks
    # on a massif's flanks and cols, so a cluster reads as bold peaks with their satellites, not uniform gravel.
    r_cl = pr['spacing_m'] / 1.12                 # a maximal Poisson-disc set's nearest-neighbour median ~ 1.12 r
    r_pl = r_cl * max(pr['plain_spacing'], 1.0)

    def radius(x, y):
        m, _ = _cluster(plan, x, y)
        return r_pl + (r_cl - r_pl) * m

    margin = 0.5 * r_pl
    tx, ty, _tr = poisson_disc(int(rng.integers(1 << 31)), x0 - margin, y0 - margin, side + 2 * margin,
                               side + 2 * margin, radius, r_cl, r_pl)
    m, raw_t = _cluster(plan, tx, ty)
    keep = rng.random(tx.size) < (m + (1.0 - m) * pr['plain_density'])
    tx, ty, m, raw_t = tx[keep], ty[keep], m[keep], raw_t[keep]
    major = np.ones(tx.size, bool)
    if pr['satellites'] > 0 and tx.size:
        r_s = r_cl * pr['satellite_spacing']
        sx, sy, _sr = poisson_disc(int(rng.integers(1 << 31)), x0 - margin, y0 - margin, side + 2 * margin,
                                   side + 2 * margin, lambda x, y: np.full(np.shape(x), r_s), r_s, r_s)
        ms, raw_s = _cluster(plan, sx, sy)
        inside = rng.random(sx.size) < ms
        sx, sy, ms, raw_s = sx[inside], sy[inside], ms[inside], raw_s[inside]
        clear = _nearest_distance(tx, ty, sx, sy, 0.62 * r_cl) >= 0.62 * r_cl
        tx = np.concatenate([tx, sx[clear]])
        ty = np.concatenate([ty, sy[clear]])
        m = np.concatenate([m, ms[clear]])
        raw_t = np.concatenate([raw_t, raw_s[clear]])
        major = np.concatenate([major, np.zeros(int(clear.sum()), bool)])
    N = tx.size

    # shape numbers. w: how much a tower belongs to a cluster (0 an isolated tower on the plain, 1 a peak inside a
    # massif); it blends the sheer fenglin tower (with a short talus apron) into the broader fengcong cone
    interior = _interior_of(plan, raw_t)
    w = np.clip(0.5 * m + 0.5 * np.sqrt(interior), 0.0, 1.0)
    trend = np.exp(pr['height_trend'] * fbm2(tx, ty, 2000.0, 2, salt + 23) / 0.3)
    H = np.exp(pr['height_sigma'] * rng.standard_normal(N)) * trend * (0.85 + 0.3 * w)
    if N and major.any():
        H *= pr['median_height_m'] / max(float(np.median(H[major])), 1e-6)
    H = np.where(major, H, H * pr['satellites'])
    H = np.clip(H, 0.2 * pr['median_height_m'], 2.6 * pr['median_height_m'])    # Guilin's towers: 100-300 m
    F = np.minimum(_plinth_of(plan, tx, ty) * m, 0.6 * H)     # the common base under the foot (cluster peaks)
    wf = _smoothstep(0.3, 0.7, m)                       # inside a cluster: fill; outside: a tower's own footprint
    # every foot ends in a concave toe of talus and colluvium (an isolated tower's apron, a cluster peak's toe
    # flaring into the cockpits and the plain), so no peak stands on the ground like a stamp with a crisp outline
    B = (pr['apron'] * (1.0 - wf) + pr['toe'] * wf) * H
    T = H - F - B
    p = rng.uniform(*pr['profile_p'], N) * (1 - w) + rng.uniform(*pr['cone_p'], N) * w
    q = rng.uniform(*pr['profile_q'], N) * (1 - w) + rng.uniform(*pr['cone_q'], N) * w
    wall = np.clip(pr['wall_deg'] + rng.normal(0.0, pr['wall_spread_deg'], N), 62.0, 87.0)
    # an isolated tower: its footprint from its wall angle, held to the design's 0.3-0.6 of its height (a slim
    # sugarloaf with a near-vertical wall would otherwise come out a needle; its wall then follows)
    R_tower = np.clip(T * radius_for_wall(p, q, wall), 0.3 * H, 0.6 * H)
    # a cluster peak fills its share of the massif: its whole footprint (steep cone and concave toe) reaches fill x
    # the median distance to its three nearest neighbours, so neighbours meet at cols whatever their heights. The
    # cone keeps a steep wall (its chord angle drawn in cone_wall_deg's range, as photographs show) and the toe, a
    # long concave footslope of colluvium, takes the rest of the space: steep peaks over gentle ground, as Guilin's
    # massifs are (and as the radar reference's gentle median slope says)
    lo_w, hi_w = pr['cone_wall_deg']
    cone_wall = rng.uniform(lo_w, hi_w, N)
    R_cone = T * radius_for_wall(p, q, cone_wall)
    R_total = np.maximum(pr['fill'] * _knn_median(tx, ty, 3, 3.0 * pr['spacing_m']), 1.3 * R_cone)
    R = R_tower * (1 - wf) + R_cone * wf
    wall = wall_chord_deg(p, q, R / np.maximum(T, 1e-6))
    reach = 0.35 * R_tower * (1 - wf) + (R_total - R_cone) * wf
    elong = rng.uniform(0.0, pr['elongation'], N)
    axis = strike + np.radians(rng.normal(0.0, 22.0, N))
    lean = rng.uniform(0.0, pr['lean'], N)
    lean_dir = rng.uniform(0.0, 2 * math.pi, N)
    # radial spurs: harmonics 2-5 of the footprint radius, weaker with order (ridges running down from the summit,
    # gullies between; low orders keep them broad, not the sharp facets of a cut gem)
    spur = (rng.uniform(0.0, 1.0, (N, 4)) * pr['spurs'] * np.array([1.0, 0.75, 0.55, 0.4])[None, :]
            * (0.5 + 0.5 * w)[:, None]) * np.exp(1j * rng.uniform(0.0, 2 * math.pi, (N, 4)))

    # no tower in the river's corridor: its foot, its pedestal and the river's banks stay clear
    if plan.river is not None and N:
        foot = (R + reach) * (1.0 + elong) * (1.0 + lean + np.abs(spur).sum(1)) + 2.5 * pr['lobes_m']
        clear = foot + 0.5 * pr['river_width_m'] + 2.5 * pr['river_bank_m'] + 40.0
        d = _river_distance(plan.river_coarse, tx, ty, float(clear.max()) + 50.0)
        ok = d > clear
        arrays = [tx, ty, H, F, B, T, R, reach, p, q, wall, elong, axis, lean, lean_dir, m, interior, spur, major]
        tx, ty, H, F, B, T, R, reach, p, q, wall, elong, axis, lean, lean_dir, m, interior, spur, major = (
            a[ok] for a in arrays)
    plan.major = major
    plan.x, plan.y, plan.H, plan.F, plan.B, plan.T, plan.R, plan.reach = tx, ty, H, F, B, T, R, reach
    plan.p, plan.q, plan.wall, plan.spur = p, q, wall, spur
    plan.elong, plan.axis, plan.lean, plan.lean_dir = elong, axis, lean, lean_dir
    plan.cluster, plan.interior = m, interior
    if tx.size:
        plan.stats = dict(towers=int(tx.size), density_per_km2=float(tx.size / (side / 1000.0) ** 2),
                          H_p10_p50_p90=[round(float(v), 1) for v in np.percentile(H, [10, 50, 90])],
                          R_over_T_p10_p50_p90=[round(float(v), 3) for v in np.percentile(R / T, [10, 50, 90])],
                          wall_p10_p50_p90=[round(float(v), 1) for v in np.percentile(wall, [10, 50, 90])])
    return plan


def _knn_median(x, y, k, max_d):
    """For every point, the median of its distances to its k nearest other points (metres; at most max_d)."""
    out = np.full(x.shape, float(max_d))
    if x.size < 2:
        return out
    bx = np.floor(x / max_d).astype(np.int64)
    by = np.floor(y / max_d).astype(np.int64)
    bins = {}
    for i, key in enumerate(zip(bx.tolist(), by.tolist())):
        bins.setdefault(key, []).append(i)
    for (cx, cy), idx in bins.items():
        cand = np.asarray([j for ddx in (-1, 0, 1) for ddy in (-1, 0, 1) for j in bins.get((cx + ddx, cy + ddy), ())])
        q = np.asarray(idx)
        d = np.sqrt((x[q, None] - x[cand][None, :]) ** 2 + (y[q, None] - y[cand][None, :]) ** 2)
        d[q[:, None] == cand[None, :]] = np.inf
        kk = min(k, d.shape[1] - 1)
        if kk < 1:
            continue
        part = np.sort(d, axis=1)[:, :kk]
        out[q] = np.minimum(np.median(part, axis=1), max_d)
    return out


def _nearest_distance(px, py, qx, qy, max_d):
    """For every point q, the distance (metres) to the nearest point p, capped at max_d (points binned on max_d)."""
    out = np.full(qx.shape, float(max_d))
    if px.size == 0 or qx.size == 0:
        return out
    bins = {}
    for k, key in enumerate(zip(np.floor(px / max_d).astype(np.int64).tolist(),
                                np.floor(py / max_d).astype(np.int64).tolist())):
        bins.setdefault(key, []).append(k)
    qb = np.stack([np.floor(qx / max_d), np.floor(qy / max_d)], 1).astype(np.int64)
    # group the queries by bin, test each group against the points of the 3 x 3 bins around it
    order = np.lexsort((qb[:, 1], qb[:, 0]))
    keys = qb[order]
    starts = np.flatnonzero(np.r_[True, np.any(keys[1:] != keys[:-1], axis=1)])
    ends = np.r_[starts[1:], len(order)]
    for s, e in zip(starts, ends):
        bx, by = int(keys[s, 0]), int(keys[s, 1])
        cand = [i for ddx in (-1, 0, 1) for ddy in (-1, 0, 1) for i in bins.get((bx + ddx, by + ddy), ())]
        if not cand:
            continue
        qi = order[s:e]
        c = np.asarray(cand)
        d = np.sqrt((qx[qi, None] - px[c][None, :]) ** 2 + (qy[qi, None] - py[c][None, :]) ** 2).min(1)
        out[qi] = np.minimum(out[qi], d)
    return out


# ---------------------------------------------------------------- the river course
def _dijkstra(cost, start, goal):
    """Least-cost 8-connected path on a grid of cell costs; [(j, i), ...] from start to goal."""
    ny, nx = cost.shape
    dist = np.full(cost.shape, np.inf)
    prev = -np.ones(cost.shape, np.int64)
    dist[start] = 0.0
    heap = [(0.0, start[0], start[1])]
    steps = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while heap:
        d, j, i = heapq.heappop(heap)
        if d > dist[j, i]:
            continue
        if (j, i) == goal:
            break
        for dj, di in steps:
            jj, ii = j + dj, i + di
            if 0 <= jj < ny and 0 <= ii < nx:
                nd = d + 0.5 * (cost[j, i] + cost[jj, ii]) * (1.4142135 if dj and di else 1.0)
                if nd < dist[jj, ii]:
                    dist[jj, ii] = nd
                    prev[jj, ii] = j * nx + i
                    heapq.heappush(heap, (nd, jj, ii))
    path = [goal]
    while path[-1] != start:
        k = prev[path[-1]]
        if k < 0:
            break
        path.append((int(k // nx), int(k % nx)))
    return path[::-1]


def _chaikin(pts, times):
    for _ in range(times):
        q = 0.75 * pts[:-1] + 0.25 * pts[1:]
        r = 0.25 * pts[:-1] + 0.75 * pts[1:]
        mid = np.empty((2 * len(q), 2))
        mid[0::2], mid[1::2] = q, r
        pts = np.vstack([pts[:1], mid, pts[-1:]])
    return pts


def _resample(pts, step):
    seg = np.hypot(*(pts[1:] - pts[:-1]).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.append(np.arange(0.0, s[-1], step), s[-1])
    return np.stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])], 1), t


def _river_course(plan, rng, via):
    """A river across the domain: a least-cost course through the plain (low cluster membership) from the upstream
    edge, near `via`, to the downstream edge; smoothed, then given meanders by a lateral offset of smooth 1-D noise
    along its length. Returns (polyline (N, 2) metres upstream first at 10 m steps, flow direction (dx, dy))."""
    pr = plan.params
    x0, y0, side = plan.domain
    n = 160
    cs = side / n
    g = x0 + (np.arange(n) + 0.5) * cs
    GX, GY = np.meshgrid(g, y0 + (np.arange(n) + 0.5) * cs)
    m, _ = _cluster(plan, GX, GY)
    az = pr['river_azimuth_deg']
    if az is None:
        az = float(rng.uniform(0.0, 360.0))
    a = _compass_to_rad(az)
    d = np.array([math.cos(a), math.sin(a)])
    vx, vy = (x0 + side / 2, y0 + side / 2) if via is None else (float(via[0]), float(via[1]))
    # the cost: clusters are expensive (the river finds the plain), and a soft pull toward the line through `via`
    # along the flow direction keeps the course passing the main tile without a forced waypoint (no doubling back)
    off_line = np.abs(-(GX - vx) * d[1] + (GY - vy) * d[0])
    cost = 1.0 + 60.0 * m ** 2 + 0.6 * (fbm2(GX, GY, 1200.0, 2, plan.salt + 41) + 1.0) + \
        3.0 * (off_line / max(0.12 * side, 1.0)) ** 2

    def edge_cell(sign):
        p = np.array([vx, vy]) + sign * d * side * 1.5
        p = np.clip(p, [x0 + 0.5 * cs, y0 + 0.5 * cs], [x0 + side - 0.5 * cs, y0 + side - 0.5 * cs])
        return int((p[1] - y0) // cs), int((p[0] - x0) // cs)

    up, down = edge_cell(-1.0), edge_cell(+1.0)
    cells = _dijkstra(cost, up, down)
    pts = np.array([[x0 + (i + 0.5) * cs, y0 + (j + 0.5) * cs] for j, i in cells], np.float64)
    pts = _chaikin(pts, 4)
    pts, s = _resample(pts, 20.0)
    w = pr['river_width_m']
    t = np.gradient(pts, axis=0)
    t /= np.maximum(np.hypot(t[:, 0], t[:, 1])[:, None], 1e-9)
    nrm = np.stack([-t[:, 1], t[:, 0]], 1)
    lam = 13.0 * w                                       # meander wavelength ~ 13 channel widths
    off = pr['river_meander'] * w * (1.6 * noise2(s, np.full_like(s, 0.5), lam, plan.salt + 53)
                                     + 0.55 * noise2(s, np.full_like(s, 0.5), 0.45 * lam, plan.salt + 59))
    pts = _chaikin(pts + nrm * off[:, None], 2)
    pts, _ = _resample(pts, 10.0)
    flow = pts[-1] - pts[0]
    flow = flow / max(float(np.hypot(*flow)), 1e-9)
    return pts, (float(flow[0]), float(flow[1]))


def _river_distance(poly, X, Y, max_d):
    """Distance (metres) from points X, Y to a polyline, capped at max_d: segments and points are binned on a grid
    of max_d + 20 m, and each bin of segments is measured only against the points in the 3 x 3 bins around it."""
    X = np.asarray(X, np.float64).ravel()
    Y = np.asarray(Y, np.float64).ravel()
    out = np.full(X.shape, float(max_d))
    if poly is None or X.size == 0:
        return out
    B = float(max_d) + 20.0
    a = poly[:-1]
    ab = poly[1:] - a
    mid = a + 0.5 * ab
    reach = B + float(np.hypot(*ab.T).max())                 # only the segments that can be within max_d
    keep = ((mid[:, 0] > X.min() - reach) & (mid[:, 0] < X.max() + reach) &
            (mid[:, 1] > Y.min() - reach) & (mid[:, 1] < Y.max() + reach))
    if not keep.any():
        return out
    a, ab, mid = a[keep], ab[keep], mid[keep]
    L2 = np.maximum((ab ** 2).sum(1), 1e-12)
    sbx = np.floor(mid[:, 0] / B).astype(np.int64)
    sby = np.floor(mid[:, 1] / B).astype(np.int64)
    pbx = np.floor(X / B).astype(np.int64)
    pby = np.floor(Y / B).astype(np.int64)
    ox, oy = int(pbx.min()), int(pby.min())
    W = int(pbx.max()) - ox + 1
    Hh = int(pby.max()) - oy + 1
    key = (pby - oy) * W + (pbx - ox)
    order = np.argsort(key, kind='stable')
    sk = key[order]
    uk, st = np.unique(sk, return_index=True)
    en = np.append(st[1:], sk.size)
    span = {int(k): (int(s), int(e)) for k, s, e in zip(uk, st, en)}
    segs = {}
    for s, k in enumerate(zip(sbx.tolist(), sby.tolist())):
        segs.setdefault(k, []).append(s)
    for (bx, by), sl in segs.items():
        parts = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                cx, cy = bx + dx - ox, by + dy - oy
                if 0 <= cx < W and 0 <= cy < Hh:
                    se = span.get(cy * W + cx)
                    if se is not None:
                        parts.append(order[se[0]:se[1]])
        if not parts:
            continue
        idx = np.concatenate(parts)
        sg = np.asarray(sl)
        px, py = X[idx], Y[idx]
        best = out[idx]
        for c0 in range(0, idx.size, 32768):
            xx = px[c0:c0 + 32768, None]
            yy = py[c0:c0 + 32768, None]
            t = np.clip(((xx - a[sg, 0]) * ab[sg, 0] + (yy - a[sg, 1]) * ab[sg, 1]) / L2[sg], 0, 1)
            ddx = a[sg, 0] + t * ab[sg, 0] - xx
            ddy = a[sg, 1] + t * ab[sg, 1] - yy
            best[c0:c0 + 32768] = np.minimum(best[c0:c0 + 32768], np.sqrt((ddx * ddx + ddy * ddy).min(1)))
        out[idx] = best
    return np.minimum(out, max_d)


# ---------------------------------------------------------------- evaluation on a level
def supersampling_for(cell):
    """Subsamples per cell axis: a wall spans a few metres, so levels coarser than 2.5 m average 2 x 2 subsamples
    per cell (the horizon levels are drawn at a 2-cell vertex stride: more would buy nothing visible)."""
    return 1 if cell <= 2.5 else 2


class _Grid:
    """A level's subsample grid and a way to put smooth world fields on it: a field is evaluated on a lattice of
    `stride` cells (aligned with the level's cell centres, one sample of rim) and bilinearly interpolated."""

    def __init__(self, x0, y0, cell, n, ss):
        self.x0, self.y0, self.cell, self.n, self.ss = x0, y0, cell, n, ss
        self.sub = cell / ss
        self.N = n * ss
        self.xs = x0 + (np.arange(self.N) + 0.5) * self.sub
        self.ys = y0 + (np.arange(self.N) + 0.5) * self.sub

    def smooth(self, fn, shortest_m):
        """fn(X, Y) of world metres, on the subsample grid; sampled every max(1, shortest_m / 8 / cell) cells."""
        k = max(1, int(shortest_m / (8.0 * self.cell)))
        step = k * self.cell
        m = int(math.ceil(self.n / k)) + 3
        lx = self.x0 + 0.5 * self.cell + (np.arange(m) - 1) * step
        ly = self.y0 + 0.5 * self.cell + (np.arange(m) - 1) * step
        v = np.broadcast_to(np.asarray(fn(lx[None, :], ly[:, None]), np.float64), (m, m))   # separable lattice
        if k == 1 and self.ss == 1:
            return v[1:self.n + 1, 1:self.n + 1]
        tx = (self.xs - lx[0]) / step
        ty = (self.ys - ly[0]) / step
        i0 = np.clip(np.floor(tx).astype(np.intp), 0, m - 2)
        j0 = np.clip(np.floor(ty).astype(np.intp), 0, m - 2)
        fx = tx - i0
        fy = ty - j0
        rows = v[j0] * (1 - fy)[:, None] + v[j0 + 1] * fy[:, None]
        return rows[:, i0] * (1 - fx)[None, :] + rows[:, i0 + 1] * fx[None, :]

    def down(self, a):
        """Subsamples to cells: the mean of each cell's ss x ss subsamples."""
        if self.ss == 1:
            return a
        return a.reshape(self.n, self.ss, self.n, self.ss).mean(axis=(1, 3))


def _bilinear_sep(v, lx, ly, qx, qy):
    """Values v on a separable lattice (rows ly, columns lx, evenly spaced), bilinear at query columns qx, rows qy."""
    tx = (qx - lx[0]) / (lx[1] - lx[0])
    ty = (qy - ly[0]) / (ly[1] - ly[0])
    i0 = np.clip(np.floor(tx).astype(np.intp), 0, len(lx) - 2)
    j0 = np.clip(np.floor(ty).astype(np.intp), 0, len(ly) - 2)
    fx = np.clip(tx - i0, 0.0, 1.0)
    fy = np.clip(ty - j0, 0.0, 1.0)
    rows = v[j0] * (1 - fy)[:, None] + v[j0 + 1] * fy[:, None]
    return rows[:, i0] * (1 - fx)[None, :] + rows[:, i0 + 1] * fx[None, :]


def _river_distance_level(plan, G, band):
    """Distance to the river on a level's subsample grid, as (near, far). far: a lattice of 20-80 m, bilinear, smooth
    everywhere (the plain's gentle rise reads it, so it has no seam). near: exact at the cell centres within `band`
    metres of the channel (a bilinear distance is at most half a lattice diagonal too large, hence the margin), far
    elsewhere, then bilinear to the subsamples (the channel and its banks read it, inside the band)."""
    side = G.n * G.cell
    stepf = float(np.clip(side / 100.0, max(G.cell, 20.0), max(80.0, G.cell)))
    kf = max(1, int(round(stepf / G.cell)))
    stepf = kf * G.cell
    mf = int(math.ceil(G.n / kf)) + 3
    lxf = G.x0 + 0.5 * G.cell + (np.arange(mf) - 1) * stepf
    lyf = G.y0 + 0.5 * G.cell + (np.arange(mf) - 1) * stepf
    XF, YF = np.meshgrid(lxf, lyf)
    df = _river_distance(plan.river_coarse, XF, YF, 1500.0).reshape(XF.shape)
    lxc = G.x0 + (np.arange(-1, G.n + 1) + 0.5) * G.cell
    lyc = G.y0 + (np.arange(-1, G.n + 1) + 0.5) * G.cell
    dc = _bilinear_sep(df, lxf, lyf, lxc, lyc)
    far = dc.copy()
    margin = 0.75 * stepf + 2.0 * G.cell
    near = dc < band + margin
    if near.any():
        jj, ii = np.nonzero(near)
        dc[near] = _river_distance(plan.river_mid, lxc[ii], lyc[jj], band + margin + 10.0)
    if G.ss == 1:
        return dc[1:-1, 1:-1], far[1:-1, 1:-1]
    return _bilinear_sep(dc, lxc, lyc, G.xs, G.ys), _bilinear_sep(far, lxc, lyc, G.xs, G.ys)


def evaluate(plan, x0, y0, cell, n, ss=None):
    """The karst surface on one level: an (n, n) window of `cell`-metre cells whose south-west corner is (x0, y0).
    Each cell is the mean of ss x ss subsamples (default supersampling_for(cell)). Returns float32 arrays:
      h        the surface;
      bed      the top of rock: towers, pedestals, and the buried rock under the alluvium and the cockpit soil;
      deposit  soil and alluvium thickness, h - bed;
      river    the river's water depth in its channel (not the `water` field: that is lakes and sea);
      Sc       the threshold slope (tangent) of the limestone, for the threshold pass;
      plain    the plain's level (no towers, no channel);
    and tower_id (int32: the tower whose steep part is the surface at the cell's centre subsample, -1 elsewhere)."""
    pr = plan.params
    G = _Grid(float(x0), float(y0), float(cell), int(n), int(ss or supersampling_for(cell)))
    N, sub = G.N, G.sub
    lim = 2.5 * cell
    # lobes: a radial displacement in metres (spurs and re-entrants of every footprint); each octave's amplitude
    # stays near a tenth of its wavelength, so the displaced contours never fold (folding reads as crumpled foil)
    LOB = G.smooth(lambda X, Y: pr['lobes_m'] * (noise2(X, Y, 130.0, plan.salt + 101)
                                                 + 0.45 * noise2(X, Y, 60.0, plan.salt + 102)) / 0.33,
                   max(60.0, lim))
    # summit irregularity: knolls and saddles at the peaks' own scale, a fraction of the tower's height
    SUM = G.smooth(lambda X, Y: pr['summit_noise'] * fbm2(X, Y, 110.0, 2, plan.salt + 103, 0.45, lim) / 0.3,
                   max(55.0, lim))

    # ---- the plain and the river
    plain = _plain(plan, G)

    # ---- towers and cones on the common base (rock heights relative to the plain's level)
    NEG = -1.0e9
    rock = np.full((N, N), NEG, np.float32)    # rock, each tower's flank continuing steeply below its foot
    owner = np.full((N, N), -1, np.int32)
    flute_on = cell <= 2.0 and pr['fluting_m'] > 0
    tan_foot = math.tan(math.radians(85.0))    # an isolated tower's rock under the alluvium
    tan_flank = math.tan(math.radians(62.0))   # a cluster peak's flank, continued below its foot
    if plan.count:
        # each tower's box holds everything it shapes: its footprint, spurs, lobes and apron (a box too small
        # would cut a tower's flank off along a straight line)
        ext = (plan.R + plan.reach) * (1.0 + plan.elong) * (1.0 + plan.lean + np.abs(plan.spur).sum(1)) + \
            4.0 * pr['lobes_m'] + pr['fluting_m'] + 2.0 * cell
        xe, ye = G.x0 + N * sub, G.y0 + N * sub
        hit = (plan.x + ext > G.x0) & (plan.x - ext < xe) & (plan.y + ext > G.y0) & (plan.y - ext < ye)
        f32 = np.float32
        xs_l = (G.xs - G.x0).astype(f32)                # window-local metres: float32 keeps millimetres here
        ys_l = (G.ys - G.y0).astype(f32)
        LOB = LOB.astype(f32)
        SUM = SUM.astype(f32)
        for t in np.nonzero(hit)[0]:
            cx, cy, e_ = plan.x[t], plan.y[t], ext[t]
            i0 = max(int((cx - e_ - G.x0) / sub), 0)
            i1 = min(int(math.ceil((cx + e_ - G.x0) / sub)) + 1, N)
            j0 = max(int((cy - e_ - G.y0) / sub), 0)
            j1 = min(int(math.ceil((cy + e_ - G.y0) / sub)) + 1, N)
            if i1 <= i0 or j1 <= j0:
                continue
            dx = xs_l[i0:i1][None, :] - f32(cx - G.x0)
            dy = ys_l[j0:j1][:, None] - f32(cy - G.y0)
            r = np.sqrt(dx * dx + dy * dy)
            ca, sa = f32(math.cos(plan.axis[t])), f32(math.sin(plan.axis[t]))
            el = f32(1.0 + plan.elong[t])
            re = np.sqrt(((dx * ca + dy * sa) / el) ** 2 + ((dy * ca - dx * sa) * el) ** 2)
            rinv = f32(1.0) / np.maximum(r, f32(1e-3))
            c1, s1 = dx * rinv, dy * rinv                    # cos and sin of the direction from the axis
            stretch = f32(1.0) + f32(plan.lean[t]) * (c1 * f32(math.cos(plan.lean_dir[t]))
                                                      + s1 * f32(math.sin(plan.lean_dir[t])))
            if pr['spurs'] > 0:
                # harmonics 2-5 by the angle-addition recurrences (no trigonometry per sample)
                c2, s2 = c1 * c1 - s1 * s1, f32(2.0) * c1 * s1
                c3, s3 = c2 * c1 - s2 * s1, s2 * c1 + c2 * s1
                c4, s4 = c2 * c2 - s2 * s2, f32(2.0) * c2 * s2
                c5, s5 = c4 * c1 - s4 * s1, s4 * c1 + c4 * s1
                sp = plan.spur[t]
                for ck, sk, a in ((c2, s2, sp[0]), (c3, s3, sp[1]), (c4, s4, sp[2]), (c5, s5, sp[3])):
                    stretch = stretch + f32(a.real) * ck - f32(a.imag) * sk
            re = re / stretch
            R = float(plan.R[t])
            u = (re - LOB[j0:j1, i0:i1]) / f32(R)
            if flute_on:
                # vertical flutes: a periodic noise of the direction from the axis only, so every groove runs
                # straight down the wall (the same offset at every height)
                theta = np.arctan2(dy, dx).astype(np.float64)
                per1 = max(int(round(2 * math.pi * R / 7.0)), 3)
                per2 = max(int(round(2 * math.pi * R / 2.9)), 3)
                g1 = (theta + math.pi) / (2 * math.pi) * per1
                g2 = (theta + math.pi) / (2 * math.pi) * per2
                fl = 0.7 * (1.0 - np.abs(_noise1_periodic(g1, per1, plan.salt + 211 + t))) + \
                    0.3 * (1.0 - np.abs(_noise1_periodic(g2, per2, plan.salt + 223 + t)))
                u = u + (pr['fluting_m'] * (fl - 0.55) / R).astype(f32)
            F, B, reach = f32(plan.F[t]), f32(plan.B[t]), f32(plan.reach[t])
            T = f32(plan.T[t]) * (f32(1.0) + SUM[j0:j1, i0:i1])
            # the tower above its foot, on the common base (F, cluster peaks) and on its toe (B, falling to the base
            # or the plain `reach` metres out); past the toe, a cluster peak's flank carries on down (hidden under the
            # base inside a cluster, reaching the plain at its edge) and an isolated tower's rock dips steeply under
            # the alluvium
            out_m = (u - f32(1.0)) * f32(R)
            toe = F + B * (f32(1.0) - np.clip(out_m / reach, f32(0.0), f32(1.0))) ** f32(pr['toe_shape'])
            beyond = F - (out_m - reach) * f32(tan_flank if F > 0.5 else tan_foot)
            prof = np.maximum(f32(1.0) - np.clip(u, f32(0.0), f32(1.0)) ** f32(plan.p[t]), f32(0.0)) ** \
                f32(1.0 / plan.q[t])
            z = np.where(u < f32(1.0), F + B + T * prof, np.where(out_m < reach, toe, beyond))
            blk = rock[j0:j1, i0:i1]
            win = z > blk
            rock[j0:j1, i0:i1] = np.where(win, z, blk)
            owner[j0:j1, i0:i1] = np.where(win & (u < 1.0), t, owner[j0:j1, i0:i1])

    # the clusters' common base (fengcong): flat at plinth_m inside a cluster, under the peaks; it shows only between
    # them, as the cockpits' floors
    if pr['plinth_m'] > 0 and plan.count:
        # the base's edge is a step of plinth_m over the cluster band (~70 m): sampled at cell resolution, or it
        # aliases into a dashed line along every cluster edge
        PM = G.smooth(lambda X, Y: _plinth_of(plan, X, Y) * _cluster(plan, X, Y)[0], 8.0 * cell)
        rock = np.maximum(rock, np.where(PM > 0.5, PM, NEG))

    level = plain['level']
    rock_h = level + rock
    h_ss = np.maximum(plain['surface'], rock_h)
    bed_ss = np.minimum(h_ss, np.maximum(rock_h, level - pr['alluvium_m']))
    water_ss = np.where(h_ss < plain['water_level'], plain['water_level'] - h_ss, 0.0) * plain['in_channel']

    h = G.down(h_ss).astype(np.float64)
    bed = G.down(bed_ss).astype(np.float32)
    # the cockpits: where peaks meet around a gap, the gap is a closed depression (star-shaped, its arms the gullies
    # up to the cols). Soil fills its bottom flat, cockpit_fill of its depth (bottom to spill): the farmed floors of
    # Guilin's cockpits. Inside the clusters only, never in the river; the bed stays the rock (the soil is deposit).
    if pr['cockpit_fill'] > 0 and plan.count:
        w = G.down(G.smooth(lambda X, Y: _cluster(plan, X, Y)[0], 200.0))
        dry = G.down((plain['surface'] >= level - 0.25).astype(np.float64)) > 0.999
        floor = _cockpit_floors(h, cell, pr['cockpit_fill'], (w > 0.5) & dry)
        h = np.maximum(h, floor)
    h = h.astype(np.float32)
    out = dict(h=h, bed=bed, deposit=np.maximum(h - bed, 0.0).astype(np.float32),
               river=G.down(water_ss).astype(np.float32), plain=G.down(level).astype(np.float32))
    xc = G.x0 + (np.arange(G.n) + 0.5) * cell
    yc = G.y0 + (np.arange(G.n) + 0.5) * cell
    sc = pr['sc_deg'] * (1.0 + pr['sc_noise'] * fbm2(xc[None, :], yc[:, None], 50.0, 2, plan.salt + 307, 0.5, lim)
                         / 0.3)
    out['Sc'] = np.tan(np.radians(np.clip(sc, 30.0, 88.0))).astype(np.float32)
    mid = G.ss // 2
    out['tower_id'] = owner[mid::G.ss, mid::G.ss].copy()
    return out


def _cockpit_floors(h, cell, share, allowed, max_cells=320):
    """The soil floor of every closed depression deeper than 1 m whose bottom lies where `allowed`: a flat level at
    its bottom + share x (spill - bottom), -inf elsewhere (apply as max(h, floor)). The depressions are found on h
    box-averaged to at most max_cells (core.metrics' fill: the moved Ekigar priority-flood), and each one's floor
    level is spread over its footprint, one coarse cell wider; the fine surface's own contours then outline the
    floor, so the coarse grid never shows, and a floor never reaches a col (it stays below its spill)."""
    from ..core import metrics as M
    n = h.shape[0]
    f = max(1, int(math.ceil(n / max_cells)))
    m = n // f
    if m < 8:
        return np.full_like(h, -np.inf)
    hc = h[:m * f, :m * f].reshape(m, f, m, f).mean(axis=(1, 3))
    filled, _ = M.fill_depressions(hc)
    depth = filled - hc
    lab, k = M.label(depth > 1e-6)
    if k == 0:
        return np.full_like(h, -np.inf)
    flat = lab.ravel()
    bottom = np.full(k + 1, np.inf)
    np.minimum.at(bottom, flat, hc.ravel())
    spill = np.full(k + 1, -np.inf)
    np.maximum.at(spill, flat, filled.ravel())
    al = allowed[:m * f, :m * f].reshape(m, f, m, f).all(axis=(1, 3))
    at_bottom = np.zeros(k + 1, bool)
    is_bottom = (hc <= bottom[lab]) & (lab > 0)
    at_bottom[np.unique(lab[is_bottom & al])] = True
    keep = (spill - bottom > 1.0) & at_bottom
    keep[0] = False
    level = np.where(keep, bottom + share * (spill - bottom), -np.inf)
    fl = level[lab]
    fl = np.maximum(fl, _rolling_max_1(fl))                          # one coarse cell wider
    out = np.repeat(np.repeat(fl, f, 0), f, 1)
    if out.shape[0] < n:
        out = np.pad(out, ((0, n - out.shape[0]), (0, n - out.shape[1])), mode='edge')
    return out


def _rolling_max_1(a):
    """The maximum over each cell's 3 x 3 neighbourhood (edges clamped)."""
    p = np.pad(a, 1, mode='edge')
    out = a.copy()
    for dj in (0, 1, 2):
        for di in (0, 1, 2):
            np.maximum(out, p[dj:dj + a.shape[0], di:di + a.shape[1]], out=out)
    return out


def _rolling_min(a, r, axis):
    """The minimum over a window of 2r + 1 cells along one axis, edges clamped, in O(1) per cell whatever r is
    (van Herk / Gil-Werman: running minima forward and backward within blocks of the window's length)."""
    a = np.moveaxis(np.asarray(a, np.float64), axis, -1)
    n = a.shape[-1]
    w = 2 * r + 1
    p = np.concatenate([np.repeat(a[..., :1], r, -1), a, np.repeat(a[..., -1:], r, -1)], -1)
    m = p.shape[-1]
    nb = -(-m // w)
    p = np.concatenate([p, np.repeat(p[..., -1:], nb * w - m, -1)], -1)
    blk = p.reshape(p.shape[:-1] + (nb, w))
    fwd = np.minimum.accumulate(blk, -1).reshape(p.shape)
    bwd = np.minimum.accumulate(blk[..., ::-1], -1)[..., ::-1].reshape(p.shape)
    out = np.minimum(bwd[..., :n], fwd[..., w - 1:w - 1 + n])
    return np.moveaxis(out, -1, axis)


def _plain(plan, G):
    """The alluvial plain and its river on a level's subsample grid: level (the plain without the channel), surface
    (with the channel cut in), water_level (the river's surface) and in_channel (1 inside the wetted channel)."""
    pr = plan.params
    fx, fy = plan.river_dir
    x0, y0, side = plan.domain
    cx, cy = x0 + side / 2, y0 + side / 2
    lim = 2.5 * G.cell
    xs, ys = G.xs, G.ys
    along = ((xs[None, :] - cx) * fx + (ys[:, None] - cy) * fy)          # metres along the river's direction
    tilt = -pr['plain_tilt_m_per_km'] * along / 1000.0
    micro = G.smooth(lambda X, Y: pr['plain_micro_m'] * fbm2(X, Y, 160.0, 3, plan.salt + 401, 0.45, lim) / 0.3,
                     max(40.0, lim))
    level = tilt + micro
    if plan.river is None:
        return dict(level=level, surface=level, water_level=np.full_like(level, -1e9), in_channel=np.zeros_like(level))
    W = pr['river_width_m']
    hw = 0.5 * W
    bank_w = max(2.5 * pr['river_bank_m'], 2.0 * G.cell)
    d, d_far = _river_distance_level(plan, G, hw + bank_w + 30.0)
    level = level + pr['plain_rise_m'] * _smoothstep(hw + bank_w, 1500.0, d_far)
    ws = tilt - pr['river_bank_m']
    bed = ws - pr['river_depth_m'] * (1.0 - np.clip(d / hw, 0.0, 1.0) ** 2)
    bank = ws + (level - ws) * _smoothstep(hw, hw + bank_w, d)
    surface = np.where(d < hw, bed, np.minimum(level, bank))
    return dict(level=level, surface=surface, water_level=ws, in_channel=(d < hw).astype(np.float64))


# ---------------------------------------------------------------- the stage op
_PLANS = {}


def _plan_key(seed, domain, params, via, main=None):
    def freeze(v):
        return tuple(freeze(x) for x in v) if isinstance(v, (list, tuple)) else v

    def window(w):
        return None if w is None else tuple(round(float(v), 3) for v in w)
    full = params_for(params)
    return (int(seed), tuple(round(float(v), 6) for v in domain), tuple(sorted((k, freeze(v)) for k, v in full.items())),
            window(via), window(main))


def cached_plan(seed, domain, params=None, via=None, main=None):
    """plan_karst, cached per process: every level of one terrain shares one plan."""
    key = _plan_key(seed, domain, params, via, main)
    if key not in _PLANS:
        if len(_PLANS) >= 8:
            _PLANS.clear()
        _PLANS[key] = plan_karst(seed, domain, params, via, main)
    return _PLANS[key]


_DOMAINS = {}


def op_karst(fields, level, params, seed=0):
    """Stage op 'karst' (the wave-1 convention op(fields, level, params, seed)): writes h, bed, deposit and Sc of one
    level from the world-space plan, in place (the river's channel is in h; its water is not a lake, so `water` is
    left alone).

    level: a core.levels.Level (or anything with x0, y0, cell, n, parent (None on the coarsest level) and depth (the
    context levels' count of doublings above the main tile)). params: the karst parameters (DEFAULTS; an unknown one
    raises naming the known ones), plus optionally domain=(x0, y0, side), the plan's extent, via=(x, y), a point the
    river passes near, and main=(x0, y0, side), the main tile (the window cluster_cover is the share of).

    The plan covers the outermost window, so every level sees the same towers: by default the domain is the window
    of the coarsest level the op runs on (parent None: levels run coarsest first), via its centre and main its
    central window of side / 2^depth: the main tile (the context levels are centred on it). So run it on 'all'
    levels: the fields are rebuilt from world functions at each level's cells (the walls are never upsampled), the
    stages after it (threshold, creep) refine each level, and the runner's border band pins a child to its parent."""
    def get(k, default=None):
        if isinstance(level, dict):
            return level.get(k, default)
        return getattr(level, k, default)
    x0, y0, cell, n = float(get('x0')), float(get('y0')), float(get('cell')), int(get('n'))
    p = dict(params)
    domain, via, main = p.pop('domain', None), p.pop('via', None), p.pop('main', None)
    key = (int(seed), _plan_key(seed, (0.0, 0.0, 1.0), p, None)[2])
    if domain is None:
        if get('parent') is None or key not in _DOMAINS:
            side = n * cell
            ms = side / 2.0 ** max(int(get('depth', 0) or 0), 0)
            cx, cy = x0 + 0.5 * side, y0 + 0.5 * side
            _DOMAINS[key] = ((x0, y0, side), (cx, cy), (cx - 0.5 * ms, cy - 0.5 * ms, ms))
        domain, via0, main0 = _DOMAINS[key]
        via = via0 if via is None else via
        main = main0 if main is None else main
    plan = cached_plan(seed, domain, p, via, main)
    out = evaluate(plan, x0, y0, cell, n)
    # the level is rebuilt, so its own alluvium and cockpit soil replace what it inherited (a parent's coarse
    # alluvium would otherwise bleed onto rock this level resolves)
    for k in ('h', 'bed', 'deposit', 'Sc'):
        fields[k] = out[k]
    return fields


OPS = {'karst': op_karst}
