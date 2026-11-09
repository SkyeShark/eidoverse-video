"""Volcanoes for the new make_terrain (design section 4.7): the analytic profiles, wave 1.

Every shape here is a function of world position (metres: x east, y north, heights up) and a seed, so a level of any
cell size evaluates the same landform at its own cell centres (design 2.1 and finding 2 of 1.3: inputs are functions
of world position, never of the grid). Azimuths are compass degrees (0 north, 90 east), as the aspect mask is.

The shapes:

    stratovolcano(x, y, ...)       the design's exponential cone (or Karatson's log + linear option) with its summit
                                   crater (and an optional flat summit ring: Fuji's truncated top), azimuthal asymmetry
                                   (rift elongation, radius and height noise), flank craters (Fuji's Hoei crater),
                                   parasitic cones and an optional sector-collapse breach
    cinder_cone(x, y, ...)         a cinder cone at repose (Wood 1980 / Porter 1972): H/W 0.18, crater/W 0.40, straight
                                   flanks at the scoria repose angle with a concave toe, crater walls at 30 degrees
    cinder_cones(x, y, cones)      a set of cones (each a dict of cinder_cone's arguments), summed
    rift_cones(...)                parasitic cone placements along a volcano's rift axis
    cinder_field(...)              a field of cones along vent lines, blue-noise spaced (the cinder_cones recipe)
    caldera_collapse(x, y, h, ...) a ring-fault collapse of an edifice: a scalloped ring, rock walls at 40-45 degrees
                                   over a talus apron, a flat floor; the outer flanks are left as they are

Reference presets, measured from the reference DEMs (blender/tests/terrain_new/volcanoes_craters/ shows the fits):
FUJI (mount_fuji), CRATER_LAKE (crater_lake), SP_CRATER (the SP Crater cone).

Stage ops: OPS maps an op name to op(fields, level, params, seed), the wave-1 convention the recipe registry finds:
'stratovolcano', 'cinder_cones', 'caldera_collapse' (impact.py adds 'impact_crater'). Each is stamped once and stays
sharp on every level it runs on (stamp_add; see the op section at the end).

Later, after the fluvial backbone (the second half of package 9): the growth term, aging by creep, the fluvial stage
for the age, lava flows (DOWNFLOW walkers) and apron deposition.

numpy only: it runs in Blender's Python and in plain Python alike.
"""
import math

import numpy as np

TAU = 2.0 * math.pi
_BIG = 1.0e9                                  # an "absent" height for the smooth unions (never wins a min)


# ====================================================================== shared world-space shape helpers
# (impact.py uses these too; they move to core/world_noise.py and core/compose.py when those land)

def polar(x, y, centre):
    """(r, azimuth) of world points about centre: r in metres, azimuth in radians clockwise from north."""
    dx = np.asarray(x, np.float64) - float(centre[0])
    dy = np.asarray(y, np.float64) - float(centre[1])
    return np.hypot(dx, dy), np.arctan2(dx, dy)


def compass(azimuth_deg):
    """The unit vector (east, north) of a compass azimuth in degrees."""
    a = math.radians(azimuth_deg)
    return math.sin(a), math.cos(a)


def smoothstep(e0, e1, v):
    t = np.clip((np.asarray(v, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def smooth_min(a, b, k):
    """C1 polynomial smooth minimum; k is the blend width in the units of a and b (metres of height); k <= 0 is min."""
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smooth_max(a, b, k):
    return -smooth_min(-np.asarray(a, np.float64), -np.asarray(b, np.float64), k)


def crest_union(a, b, k):
    """A rounded crest where a surface rising one way meets one rising the other (a rim): smooth_min lowers the
    crossing by k/4, so the bump (k/4)(1 - ((a - b)/k)^2)^2, confined to the blend zone |a - b| < k, puts it back:
    the crest keeps the sharp crest's height, rounded over the blend zone."""
    if k <= 0:
        return np.minimum(a, b)
    u = np.clip((np.asarray(a, np.float64) - b) / k, -1.0, 1.0)
    return smooth_min(a, b, k) + 0.25 * k * (1.0 - u * u) ** 2


def _rng(seed, salt):
    return np.random.default_rng([abs(int(seed)), int(salt)])


_AZ_SAMPLES = 8192
AZ_TABLE_ANGLES = np.arange(_AZ_SAMPLES + 1) * (TAU / _AZ_SAMPLES)     # a closed table: the last entry is the first


class AzimuthSampler:
    """Linear reads of closed periodic tables (AZ_TABLE_ANGLES) at fixed azimuths (radians): the index and fraction
    are worked out once and shared by every table read at these points."""

    def __init__(self, az):
        u = np.mod(np.asarray(az, np.float64), TAU) * (_AZ_SAMPLES / TAU)
        self.i = np.minimum(np.floor(u).astype(np.int32), _AZ_SAMPLES - 1)
        self.f = u - self.i

    def __call__(self, table):
        a = np.take(table, self.i)
        return a + (np.take(table, self.i + 1) - a) * self.f


def azimuth_sampler(az):
    return az if isinstance(az, AzimuthSampler) else AzimuthSampler(az)


def azimuth_noise(az, seed, salt, k_min=1, k_max=6, decay=1.5):
    """Periodic noise of azimuth (radians, or an AzimuthSampler) with unit RMS: sum over k of a_k cos(k az + phi_k),
    a_k proportional to k^-decay, the phases drawn from (seed, salt). Read from an 8192-sample table, so k_max up to
    128 stays smooth."""
    rng = _rng(seed, salt)
    ks = np.arange(int(k_min), int(k_max) + 1, dtype=np.float64)
    amp = ks ** -float(decay)
    amp /= math.sqrt(float(np.sum(amp * amp)) / 2.0)
    phase = rng.uniform(0.0, TAU, ks.size)
    table = np.zeros_like(AZ_TABLE_ANGLES)
    for k, a, p in zip(ks, amp, phase):
        table += a * np.cos(k * AZ_TABLE_ANGLES + p)
    return azimuth_sampler(az)(table)


_PCG_MUL = np.uint32(747796405)
_PCG_INC = np.uint32(2891336453)
_PCG_WORD = np.uint32(277803737)


def _pcg(v):
    """The 32-bit PCG hash (Jarzynski & Olano 2020), elementwise on uint32 (the kernels' common.glsl uses it too)."""
    with np.errstate(over='ignore'):
        s = v * _PCG_MUL + _PCG_INC
        w = ((s >> ((s >> np.uint32(28)) + np.uint32(4))) ^ s) * _PCG_WORD
        return (w >> np.uint32(22)) ^ w


def _u32(v):
    return (np.asarray(v, np.int64) & 0xFFFFFFFF).astype(np.uint32)


def lattice_hash(ix, iy, seed):
    """A uint32 hash of integer lattice cells and a seed."""
    return _pcg(_u32(ix) ^ _pcg(_u32(iy) ^ _pcg(_u32(np.int64(seed)))))


def gradient_noise(x, y, scale_m, seed):
    """Gradient (Perlin) noise of world metres on a lattice of spacing scale_m; values within about +-0.7.
    The gradients are hashed once per lattice point of the covered block and gathered, so the cost is a few array
    passes per point however fine the lattice."""
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    axes = _meshgrid_axes(x, y)
    if axes is not None:
        return _gradient_noise_grid(axes[0], axes[1], scale_m, seed)
    px = x / scale_m
    py = y / scale_m
    fx0, fy0 = np.floor(px), np.floor(py)
    if px.size == 0:
        return np.zeros_like(px)
    fx, fy = (px - fx0).astype(np.float32), (py - fy0).astype(np.float32)      # in [0, 1): float32 is exact enough
    ix, iy = fx0.astype(np.int64), fy0.astype(np.int64)
    ix0, iy0 = int(ix.min()), int(iy.min())
    nx, ny = int(ix.max()) - ix0 + 2, int(iy.max()) - iy0 + 2
    lx, ly = np.meshgrid(np.arange(ix0, ix0 + nx, dtype=np.int64), np.arange(iy0, iy0 + ny, dtype=np.int64))
    a = lattice_hash(lx, ly, seed).astype(np.float64) * (TAU / 4294967296.0)
    gxt, gyt = np.cos(a).astype(np.float32).ravel(), np.sin(a).astype(np.float32).ravel()
    k = (iy - iy0) * nx + (ix - ix0)
    del ix, iy, fx0, fy0, px, py

    def corner(kk, ox, oy):
        v = np.take(gxt, kk)
        v *= (fx - np.float32(ox)) if ox else fx
        w = np.take(gyt, kk)
        w *= (fy - np.float32(oy)) if oy else fy
        v += w
        return v

    def fade(t):                                  # 6t^5 - 15t^4 + 10t^3, in place on a copy
        u = t * np.float32(6.0)
        u -= np.float32(15.0)
        u *= t
        u += np.float32(10.0)
        u *= t
        u *= t
        u *= t
        return u

    ux, uy = fade(fx), fade(fy)
    n0 = corner(k, 0, 0)
    c10 = corner(k + 1, 1, 0)
    c10 -= n0
    c10 *= ux
    n0 += c10
    n1 = corner(k + nx, 0, 1)
    c11 = corner(k + nx + 1, 1, 1)
    c11 -= n1
    c11 *= ux
    n1 += c11
    n1 -= n0
    n1 *= uy
    n0 += n1
    return n0.astype(np.float64)


def _meshgrid_axes(x, y):
    """(x axis, y axis) when x, y are a meshgrid (x varying along columns only, y along rows only), else None."""
    if x.ndim != 2 or x.shape != y.shape or x.shape[0] < 2 or x.shape[1] < 2:
        return None
    xr, yc = x[0], y[:, 0]
    if np.array_equal(x[-1], xr) and np.array_equal(y[:, -1], yc) and x[1, 0] == xr[0] and y[0, 1] == yc[0]:
        return xr, yc
    return None


def _gradient_noise_grid(xr, yc, scale_m, seed):
    """gradient_noise on the grid xr (columns) x yc (rows): the lattice cells, fractions and fades per axis, only the
    four gathers and the blends per point; the same values as the pointwise path."""
    px, py = xr / scale_m, yc / scale_m
    fx0, fy0 = np.floor(px), np.floor(py)
    fx, fy = (px - fx0).astype(np.float32), (py - fy0).astype(np.float32)
    ix, iy = fx0.astype(np.int64), fy0.astype(np.int64)
    ix0, iy0 = int(ix.min()), int(iy.min())
    nx, ny = int(ix.max()) - ix0 + 2, int(iy.max()) - iy0 + 2
    lx, ly = np.meshgrid(np.arange(ix0, ix0 + nx, dtype=np.int64), np.arange(iy0, iy0 + ny, dtype=np.int64))
    a = lattice_hash(lx, ly, seed).astype(np.float64) * (TAU / 4294967296.0)
    gxt, gyt = np.cos(a).astype(np.float32), np.sin(a).astype(np.float32)
    J, I = ix - ix0, iy - iy0

    def fade(t):
        return t * t * t * (t * (t * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))

    def corner(oy, ox):
        rows, cols = np.ix_(I + oy, J + ox)
        v = gxt[rows, cols]
        v *= (fx - np.float32(ox))[None, :]
        w = gyt[rows, cols]
        w *= (fy - np.float32(oy))[:, None]
        v += w
        return v

    ux, uy = fade(fx)[None, :], fade(fy)[:, None]
    n0 = corner(0, 0)
    c = corner(0, 1)
    c -= n0
    c *= ux
    n0 += c
    n1 = corner(1, 0)
    c = corner(1, 1)
    c -= n1
    c *= ux
    n1 += c
    n1 -= n0
    n1 *= uy
    n0 += n1
    return n0.astype(np.float64)


def fbm(x, y, scale_m, seed, octaves=3, gain=0.5):
    """Fractal sum of gradient noise from scale_m down by halves, normalised to unit standard deviation (about)."""
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(int(octaves)):
        total = total + amp * gradient_noise(x, y, scale_m / 2.0 ** o, int(seed) * 7919 + 101 * o + 17)
        norm += amp * amp
        amp *= gain
    return total / (0.24 * math.sqrt(norm))       # gradient noise has a standard deviation of about 0.24


# ====================================================================== the stratovolcano cone (design 4.7)

def cone_decay_m(height_m, upper_slope_deg):
    """The exponential cone's length scale: lambda = H / tan(upper slope) (design 4.7)."""
    return float(height_m) / math.tan(math.radians(upper_slope_deg))


def exp_cone(r, height_m, radius_m, decay_m, crater_radius_m):
    """The design's exponential cone:

        z(r) = H (e^{-(r - rc)/lambda} - e^{-(R - rc)/lambda}) / (1 - e^{-(R - rc)/lambda})

    so z(rc) = H at the crater rim and z(R) = 0 at the foot; 0 beyond R. Inside rc it keeps rising (the summit crater
    replaces it there)."""
    rc, R, lam = float(crater_radius_m), float(radius_m), float(decay_m)
    e_foot = math.exp(-(R - rc) / lam)
    r = np.asarray(r, np.float64)
    z = float(height_m) * (np.exp(-(r - rc) / lam) - e_foot) / (1.0 - e_foot)
    return np.where(r < R, z, 0.0)


def exp_cone_slope_deg(r, height_m, radius_m, decay_m, crater_radius_m):
    """The exponential cone's slope in degrees at r (rc <= r < R): tan = (H / lambda) e^{-(r - rc)/lambda} / (1 - e^{-(R - rc)/lambda})."""
    rc, R, lam = float(crater_radius_m), float(radius_m), float(decay_m)
    e_foot = math.exp(-(R - rc) / lam)
    t = float(height_m) / lam * np.exp(-(np.asarray(r, np.float64) - rc) / lam) / (1.0 - e_foot)
    return np.degrees(np.arctan(t))


def loglinear_break_m(height_m, radius_m, upper_slope_deg, crater_radius_m):
    """Where the log + linear profile's straight upper flank meets its logarithmic lower flank: r_b solves
    tan(upper) (r_b (ln(R / r_b) + 1) - rc) = H."""
    t, H, R, rc = math.tan(math.radians(upper_slope_deg)), float(height_m), float(radius_m), float(crater_radius_m)
    if H >= t * (R - rc):
        raise ValueError(f'loglinear cone: H {H:.0f} m needs a straight cone steeper than {upper_slope_deg} degrees '
                         f'over R {R:.0f} m (the most this slope reaches is {t * (R - rc):.0f} m): lower H or the '
                         f'slope, or raise R')
    g = lambda rb: t * (rb * (math.log(R / rb) + 1.0) - rc) - H   # noqa: E731  (increasing on (0, R))
    lo, hi = rc, R
    if g(lo) >= 0.0:
        return rc
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if g(mid) < 0.0 else (lo, mid)
    return 0.5 * (lo + hi)


def loglinear_cone(r, height_m, radius_m, upper_slope_deg, crater_radius_m):
    """Karatson et al. 2010's regular stratovolcano: a straight upper flank at the upper slope down to r_b, then a
    logarithmic lower flank z = A ln(R / r) with A = r_b tan(upper), C1 at r_b; z(rc) = H, z(R) = 0, 0 beyond R."""
    t = math.tan(math.radians(upper_slope_deg))
    R, rc = float(radius_m), float(crater_radius_m)
    rb = loglinear_break_m(height_m, radius_m, upper_slope_deg, crater_radius_m)
    if rb <= rc:                                  # too low for any straight part: the log flank from the rim
        A = float(height_m) / math.log(R / rc)
        rb = rc
    else:
        A = rb * t
    zb = A * math.log(R / rb)
    r = np.asarray(r, np.float64)
    z = np.where(r < rb, zb + t * (rb - r), A * np.log(R / np.maximum(r, 1e-6)))
    return np.where(r < R, z, 0.0)


def _cone_function(profile, height_m, radius_m, upper_slope_deg, crater_radius_m):
    """(z(r), slope tangent at the rim) of the named profile."""
    if profile == 'exp':
        lam = cone_decay_m(height_m, upper_slope_deg)
        return ((lambda q: exp_cone(q, height_m, radius_m, lam, crater_radius_m)),
                math.tan(math.radians(float(exp_cone_slope_deg(crater_radius_m, height_m, radius_m, lam,
                                                               crater_radius_m)))))
    if profile == 'loglinear':
        loglinear_break_m(height_m, radius_m, upper_slope_deg, crater_radius_m)      # raises if impossible
        return ((lambda q: loglinear_cone(q, height_m, radius_m, upper_slope_deg, crater_radius_m)),
                math.tan(math.radians(upper_slope_deg)))
    raise ValueError(f"stratovolcano profile {profile!r}: use 'exp' (the default, Fuji) or 'loglinear' "
                     f"(straight upper flanks, Karatson C-type)")


def stratovolcano(x, y, centre=(0.0, 0.0), height_m=3700.0, radius_m=18000.0, upper_slope_deg=33.0, profile='exp',
                  crater_radius_m=None, crater_depth_m=None, crater_floor_frac=0.0, summit_platform_m=0.0,
                  crest_round_m=None, elongation=1.0, rift_azimuth_deg=0.0, radius_noise=0.0, height_noise=0.0,
                  flank_craters=(), cones=(), breach=None, seed=0):
    """A stratovolcano's constructional surface: metres above its foot at world points (x, y).

    height_m, radius_m     H, the crater rim above the foot, and R, the foot's radius (design 4.7: Fuji 3700 m, 18 km)
    upper_slope_deg        sets lambda = H / tan(upper slope) (exp profile); the slope at the rim is then
                           atan(tan(upper) / (1 - e^{-(R - rc)/lambda})), a degree or so steeper for broad cones
    profile                'exp' (the design's exponential cone) or 'loglinear' (straight upper flank)
    crater_radius_m        rc, the summit crater's rim radius (default 0.03 R)
    crater_depth_m         rim to floor (default 0.4 rc); a parabolic bowl, with a flat floor of radius
                           crater_floor_frac * rc when that is above 0
    summit_platform_m      a flat summit ring this wide around the crater before the flank falls away: the flank's
                           top moves out to rc + this (Fuji's broad summit seen from afar: a truncated cone with
                           sharp shoulders, not a rounded ridge)
    crest_round_m          the rim crest's rounding half-width (default 0.05 rc)
    elongation             the flanks' long / short axis ratio (about), the long axis along the rift (rift_azimuth_deg,
                           both ways), the mean radius kept; the summit crater stays round, the stretch grows from
                           the rim outward
    radius_noise           the flanks' radial stretch modulated by unit-RMS azimuthal noise (harmonics 1-4) times this
    height_noise           the rim height H modulated by azimuthal noise (harmonics 1-3) times this
    flank_craters          dicts: at (x, y), radius_m, depth_m (below the cone surface at its centre), rim_m (a
                           scoria rim on the downhill side), as Fuji's Hoei crater
    cones                  parasitic cones: dicts of cinder_cone's arguments (rift_cones makes them)
    breach                 a sector-collapse amphitheatre: dict(azimuth_deg, width_m, depth_m below the rim at the
                           vent, floor_slope_deg 8, wall_deg 35, widening 0.35)

    Returns dict(height, cinder): height is the whole surface above the foot; cinder is the parasitic cones' share
    (loose scoria, for bed = h - cinder)."""
    H, R = float(height_m), float(radius_m)
    rc = 0.03 * R if crater_radius_m is None else float(crater_radius_m)
    dc = 0.4 * rc if crater_depth_m is None else float(crater_depth_m)
    if not (0.0 < rc < R):
        raise ValueError(f'stratovolcano: crater radius {rc:.0f} m must lie between 0 and R {R:.0f} m')
    if not (0.0 <= crater_floor_frac < 0.95):
        raise ValueError('stratovolcano: crater_floor_frac must be in [0, 0.95)')
    cone, s_rim = _cone_function(profile, H, R, upper_slope_deg, rc)
    rift = math.radians(rift_azimuth_deg)
    w = float(summit_platform_m)
    rt = rc + w                                   # where the flank starts falling

    def outer(xq, yq):
        """The cone's flank surface (and its continuation over the crater) with the azimuthal modulation; with a
        summit platform, flat at the rim height from the flank's top inward."""
        r, az_rad = polar(xq, yq, centre)
        az = azimuth_sampler(az_rad)
        stretch = 1.0 + (float(elongation) - 1.0) * (np.cos(az_rad - rift) ** 2 - 0.5)     # mean 1 round the cone
        if radius_noise:
            stretch = stretch * (1.0 + float(radius_noise) * azimuth_noise(az, seed, 11, 1, 4))
        hfac = 1.0 + float(height_noise) * azimuth_noise(az, seed, 12, 1, 3) if height_noise else np.ones_like(r)
        if w > 0.0:
            rf = np.where(r > rt, rc + (r - rt) / stretch, rc)
        else:
            rf = np.where(r > rc, rc + (r - rc) / stretch, r)
        return hfac * cone(rf), hfac, r

    z_out, hfac, r = outer(x, y)
    # the summit crater: a parabolic bowl from the rim (H * hfac at rho = 1, its mean H at the centre, so the floor
    # is single-valued) down to H - dc, flattened to a floor of radius crater_floor_frac * rc
    rho = r / rc
    f = float(crater_floor_frac)
    bowl_depth = dc / (1.0 - f * f)
    inner = H * (1.0 + (hfac - 1.0) * rho * rho) - bowl_depth * (1.0 - rho * rho)
    if f > 0.0:
        inner = smooth_max(inner, H - dc, 0.08 * dc)
    inner = np.where(rho < 1.6, inner, _BIG)
    w = 0.05 * rc if crest_round_m is None else float(crest_round_m)
    z = crest_union(z_out, inner, w * (2.0 * bowl_depth / rc + s_rim))

    for fc in flank_craters:
        z = _flank_crater(x, y, z, fc, centre, lambda xq, yq: outer(xq, yq)[0])
    if breach:
        z = _breach_cut(x, y, z, centre, H - float(breach.get('depth_m', 2.0 * dc)), breach)
    cinder = cinder_cones(x, y, cones) if cones else np.zeros_like(z)
    return dict(height=z + cinder, cinder=cinder)


def _flank_crater(x, y, z, fc, centre, surface):
    """A crater cut into a flank: a parabolic bowl whose floor is depth_m below the cone surface at its centre, so
    its uphill wall stands tall and its downhill rim is low, plus a scoria rim mound on the downhill side."""
    at = fc['at']
    rad, dep = float(fc['radius_m']), float(fc['depth_m'])
    rim_m = float(fc.get('rim_m', 0.0))
    z0 = float(surface(np.array([at[0]]), np.array([at[1]]))[0])
    rr, aa = polar(x, y, at)
    bowl = (z0 - dep) + dep * (rr / rad) ** 2
    bowl = np.where(rr < 2.5 * rad, bowl, _BIG)
    out = smooth_min(z, bowl, 0.06 * dep)
    if rim_m > 0.0:
        down = math.atan2(at[0] - centre[0], at[1] - centre[1])          # outward from the vent = downhill
        side = smoothstep(-0.3, 0.8, np.cos(aa - down))
        mound = rim_m * np.exp(-((rr - rad) / (0.4 * rad)) ** 2) * side * smoothstep(0.7 * rad, rad, rr)
        out = out + mound
    return out


def _breach_cut(x, y, z, vent, floor_at_vent_m, breach):
    """A horseshoe amphitheatre opening along breach['azimuth_deg']: a floor descending from the vent at
    floor_slope_deg, side walls and a head wall rising at wall_deg, widening downslope; the surface is cut down to it
    wherever it stands above it (smoothly)."""
    ex, ey = compass(float(breach['azimuth_deg']))
    dx = np.asarray(x, np.float64) - vent[0]
    dy = np.asarray(y, np.float64) - vent[1]
    u = dx * ex + dy * ey                       # along the breach, outward
    v = -dx * ey + dy * ex                      # across it
    half = 0.5 * float(breach['width_m']) * (1.0 + float(breach.get('widening', 0.35)) * np.maximum(u, 0.0)
                                             / float(breach['width_m']))
    t_floor = math.tan(math.radians(float(breach.get('floor_slope_deg', 8.0))))
    t_wall = math.tan(math.radians(float(breach.get('wall_deg', 35.0))))
    cut = (floor_at_vent_m - t_floor * np.maximum(u, 0.0)
           + t_wall * (np.maximum(np.abs(v) - half, 0.0) + np.maximum(-u, 0.0)))
    return smooth_min(z, cut, 15.0)


# ====================================================================== cinder cones (design 4.7)

def cinder_cone_toe_m(width_m, hw_ratio=0.18, crater_ratio=0.40, flank_deg=32.0):
    """The concave toe's width for a cone of these ratios: with a straight flank at flank_deg from the rim crest and a
    parabolic toe ending level at the base, L = 2 (Rb - rcr - H / tan(flank)). Raises when no toe fits."""
    W = float(width_m)
    Rb, rcr, H = 0.5 * W, 0.5 * W * float(crater_ratio), float(hw_ratio) * W
    t = math.tan(math.radians(flank_deg))
    L = 2.0 * (Rb - rcr - H / t)
    lo = math.degrees(math.atan(H / (Rb - rcr)))
    hi = math.degrees(math.atan(2.0 * H / (Rb - rcr)))
    if L < -1e-9 * W:
        raise ValueError(f'cinder cone: flanks at {flank_deg} degrees cannot reach H/W {hw_ratio} with crater/W '
                         f'{crater_ratio}; use at least {lo:.1f} degrees (a straight cone)')
    if L > (Rb - rcr) * (1.0 + 1e-9):
        raise ValueError(f'cinder cone: flanks at {flank_deg} degrees are too steep for H/W {hw_ratio} with '
                         f'crater/W {crater_ratio}; use at most {hi:.1f} degrees')
    return max(L, 0.0)


def cinder_cone(x, y, at=(0.0, 0.0), width_m=800.0, hw_ratio=0.18, crater_ratio=0.40, flank_deg=32.0,
                crater_wall_deg=30.0, crater_depth_frac=0.45, crest_round_m=None, rim_tilt=0.0,
                tilt_azimuth_deg=0.0, breach_azimuth_deg=None, breach_width_deg=50.0, outline_noise=0.0, age_yr=0.0,
                seed=0):
    """A cinder cone at repose: metres above its base at world points (x, y).

    width_m            W, the basal width (Wood's W_co); H = hw_ratio W (Wood 1980 / Porter 1972: 0.18 fresh)
    crater_ratio       the crater rim's width over W (Wood: 0.40 fresh)
    flank_deg          the straight upper flank at the scoria repose (30-33 degrees); the concave toe's width
                       follows from the ratios (cinder_cone_toe_m)
    crater_wall_deg    the crater's inner walls (30 degrees), down to a flat floor crater_depth_frac * H below the
                       rim (or the walls' meeting point, whichever is higher)
    rim_tilt           the rim higher on one side: H (1 + rim_tilt cos(azimuth - tilt_azimuth_deg)) (downwind)
    breach_azimuth_deg a breach through the rim and flank on that side (a lava flow's exit), breach_width_deg wide
    outline_noise      a lobate footprint: the whole profile's radius scaled by 1 + this x unit-RMS azimuthal noise
                       (harmonics 2-8); 0 is the pure profile
    age_yr             recorded for the aging stage (creep with kappa t, second half); the shape here is fresh"""
    W = float(width_m)
    Rb, rcr, H = 0.5 * W, 0.5 * W * float(crater_ratio), float(hw_ratio) * W
    t = math.tan(math.radians(flank_deg))
    L = cinder_cone_toe_m(W, hw_ratio, crater_ratio, flank_deg)
    r, az = polar(x, y, at)
    if outline_noise:
        r = r / (1.0 + float(outline_noise) * azimuth_noise(az, seed, 33, 2, 8))
    hrim = H * (1.0 + float(rim_tilt) * np.cos(az - math.radians(tilt_azimuth_deg))) if rim_tilt else H
    # the flank: straight at the repose angle from the rim crest, then a parabolic toe level at the base (C1);
    # continued upward inside the crater for the crest union
    rt = Rb - L
    if L > 1e-6 * W:
        flank = np.where(r <= rt, H - t * (r - rcr), np.where(r < Rb, t / (2.0 * L) * (Rb - r) ** 2, 0.0))
    else:
        flank = np.where(r < Rb, H - t * (r - rcr), 0.0)
    flank = flank * (hrim / H) if rim_tilt else flank
    # the crater: walls at crater_wall_deg descending inward from the rim, a flat floor; continued upward outside
    tc = math.tan(math.radians(crater_wall_deg))
    depth = min(float(crater_depth_frac) * H, tc * rcr)
    inner = np.maximum(hrim + tc * (r - rcr), H - depth)
    w = 0.03 * W if crest_round_m is None else float(crest_round_m)
    z = crest_union(flank, inner, w * (t + tc))
    if breach_azimuth_deg is not None:
        z = _cone_breach(z, r, az, Rb, rcr, H - depth, breach_azimuth_deg, breach_width_deg)
    return np.maximum(z, 0.0)


def _cone_breach(z, r, az, Rb, rcr, floor, azimuth_deg, width_deg):
    """A notch through a cone's rim and flank: within the breach sector the surface is lowered to a ramp running from
    the crater floor down to the base, with walls rising at 30 degrees off the sector's edges."""
    d = np.mod(az - math.radians(azimuth_deg) + math.pi, TAU) - math.pi           # angle off the breach axis
    half = 0.5 * math.radians(width_deg)
    lateral = np.maximum(np.abs(d) - half, 0.0) * np.maximum(r, rcr)              # metres outside the notch
    ramp = floor * (1.0 - np.clip((r - 0.5 * rcr) / (Rb - 0.5 * rcr), 0.0, 1.0))
    cut = ramp + math.tan(math.radians(30.0)) * lateral + np.where(np.abs(d) < math.pi / 2, 0.0, _BIG)
    return smooth_min(z, cut, 0.02 * floor + 1e-3)


def _feasible_flank(flank_deg, hw_ratio, crater_ratio):
    """flank_deg clamped into the range a cone of these ratios can take (cinder_cone_toe_m's bounds): a low, wide
    cone (an old or half-buried one, H/W 0.08) cannot keep 30-degree flanks and still reach its height."""
    run = 0.5 - 0.5 * float(crater_ratio)
    lo = math.degrees(math.atan(float(hw_ratio) / run))
    hi = math.degrees(math.atan(2.0 * float(hw_ratio) / run))
    return float(min(max(flank_deg, lo + 0.2), hi - 0.2))


_AGED_PATCHES = {}


def _gauss_fft(a, sigma_cells):
    """A Gaussian blur of a zero-bordered patch by FFT (circular: the patch carries a 4 sigma border of zeros)."""
    ky = np.fft.fftfreq(a.shape[0])[:, None]
    kx = np.fft.rfftfreq(a.shape[1])[None, :]
    g = np.exp(-2.0 * (math.pi * sigma_cells) ** 2 * (kx * kx + ky * ky))
    return np.fft.irfft2(np.fft.rfft2(a) * g, s=a.shape)


def aged_cinder_cone(x, y, kappa_t_m2=0.0, **cone):
    """A cinder cone aged by linear creep (design 4.7): the fresh cone convolved with a Gaussian of sigma^2 =
    2 kappa t (the exact solution of linear diffusion), so its crest rounds, its crater shallows and fills, its
    flanks fall below the repose angle and its H/W drops while its volume stays. kappa_t_m2 is kappa t in m^2 (fresh
    0; a 500 kyr cone at kappa 0.01 m^2/yr: 5000 m^2, sigma 100 m). The cone is evaluated on its own patch grid
    (cell min(W / 320, sigma / 3), a function of the cone alone, so every level samples one surface), blurred, and
    read bilinearly; a fresh cone is evaluated exactly. Patches are kept per process."""
    kt = float(kappa_t_m2 or 0.0)
    if kt <= 0.0:
        return cinder_cone(x, y, **cone)
    import json
    W = float(cone.get('width_m', 800.0))
    sig = math.sqrt(2.0 * kt)
    pc = max(min(W / 320.0, sig / 3.0), 0.25)
    half = 0.5 * W * (1.02 + 3.5 * float(cone.get('outline_noise', 0.0))) + 4.0 * sig
    m = int(math.ceil(2.0 * half / pc))
    at = cone.get('at', (0.0, 0.0))
    key = json.dumps(dict(cone, kappa_t_m2=kt), sort_keys=True, default=str)
    if key not in _AGED_PATCHES:
        c = (np.arange(m) + 0.5) * pc - half
        px, py = np.meshgrid(at[0] + c, at[1] + c)
        _AGED_PATCHES[key] = _gauss_fft(cinder_cone(px, py, **cone), sig / pc)
        if len(_AGED_PATCHES) > 256:
            _AGED_PATCHES.pop(next(iter(_AGED_PATCHES)))
    patch = _AGED_PATCHES[key]
    fx = (np.asarray(x, np.float64) - (at[0] - half)) / pc - 0.5
    fy = (np.asarray(y, np.float64) - (at[1] - half)) / pc - 0.5
    inside = (fx >= 0.0) & (fy >= 0.0) & (fx <= m - 1) & (fy <= m - 1)
    i0 = np.clip(np.floor(fx).astype(np.int64), 0, m - 2)
    j0 = np.clip(np.floor(fy).astype(np.int64), 0, m - 2)
    tx, ty = np.clip(fx - i0, 0.0, 1.0), np.clip(fy - j0, 0.0, 1.0)
    v = ((patch[j0, i0] * (1 - tx) + patch[j0, i0 + 1] * tx) * (1 - ty)
         + (patch[j0 + 1, i0] * (1 - tx) + patch[j0 + 1, i0 + 1] * tx) * ty)
    return np.where(inside, np.maximum(v, 0.0), 0.0)


def cinder_cones(x, y, cones):
    """The sum of several cinder cones (each a dict of cinder_cone's keyword arguments, plus kappa_t_m2 for an aged
    cone: aged_cinder_cone), each evaluated only over its own footprint, so a field of cones costs little."""
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    out = np.zeros(np.broadcast(x, y).shape)
    xb, yb = np.broadcast_to(x, out.shape), np.broadcast_to(y, out.shape)
    for c in cones:
        c = dict(c)
        kt = float(c.pop('kappa_t_m2', 0.0) or 0.0)
        rb = 0.5 * float(c.get('width_m', 800.0)) * (1.02 + 3.5 * float(c.get('outline_noise', 0.0)))
        rb += 4.0 * math.sqrt(2.0 * kt) if kt > 0 else 0.0
        add_on_support(out, xb, yb, c.get('at', (0.0, 0.0)), rb,
                       lambda xs, ys, c=c, kt=kt: aged_cinder_cone(xs, ys, kt, **c))
    return out


def support_slices(x, y, centre, radius):
    """(row slice, column slice) of the square of half-side `radius` about centre, when x and y are a meshgrid with
    ascending axes (x varying along columns only, y along rows only, as every level's cell centres are); else None."""
    if x.ndim != 2 or x.shape != y.shape or x.shape[0] < 2 or x.shape[1] < 2:
        return None
    xr, yc = x[0], y[:, 0]
    if not (xr[1] > xr[0] and yc[1] > yc[0] and np.array_equal(x[-1], xr) and np.array_equal(y[:, -1], yc)):
        return None
    c0, c1 = np.searchsorted(xr, centre[0] - radius, 'left'), np.searchsorted(xr, centre[0] + radius, 'right')
    r0, r1 = np.searchsorted(yc, centre[1] - radius, 'left'), np.searchsorted(yc, centre[1] + radius, 'right')
    return slice(int(r0), int(r1)), slice(int(c0), int(c1))


def add_on_support(out, x, y, centre, radius, fn):
    """out += fn(x, y) where fn can be non-zero only within `radius` of centre: evaluated on the covering slices of a
    meshgrid, or on the masked points otherwise."""
    sl = support_slices(x, y, centre, radius)
    if sl is not None:
        if sl[0].stop > sl[0].start and sl[1].stop > sl[1].start:
            out[sl] += fn(x[sl], y[sl])
        return out
    near = (np.abs(x - centre[0]) < radius) & (np.abs(y - centre[1]) < radius)
    if near.any():
        out[near] += fn(x[near], y[near])
    return out


def rift_cones(centre, rift_azimuth_deg, count=24, distance_m=(1500.0, 12000.0), spread_m=None,
               width_median_m=450.0, width_m=(200.0, 1600.0), hw_ratio=(0.10, 0.18), crater_ratio=(0.25, 0.45),
               crater_depth_frac=(0.25, 0.45), flank_deg=(30.0, 33.0), breach_fraction=0.25, outline_noise=0.06,
               seed=0):
    """Parasitic cones along a volcano's rift axis (both ways from the centre): distances spread evenly over the
    flank's area between distance_m (so the lower flanks get their share, not a string of beads at the summit), a
    lateral scatter growing outward to spread_m at the far end (1 sigma; default 0.15 of the far distance), widths
    lognormal about width_median_m within width_m, lobate footprints (outline_noise), no two cones overlapping by more
    than a third. Older, half-buried flank cones want low H/W and small, shallow craters (crater_ratio about 0.15-0.3,
    crater_depth_frac 0.1-0.3), or they read as rings. Returns a list of cinder_cone argument dicts."""
    rng = _rng(seed, 31)
    spread_m = 0.15 * float(distance_m[1]) if spread_m is None else float(spread_m)
    ex, ey = compass(rift_azimuth_deg)
    cones, tries = [], 0
    while len(cones) < count and tries < 50 * count:
        tries += 1
        side = 1.0 if rng.random() < 0.5 else -1.0
        d = math.sqrt(rng.uniform(distance_m[0] ** 2, distance_m[1] ** 2))
        lat = rng.normal(0.0, spread_m * d / distance_m[1])
        px = centre[0] + side * d * ex - lat * ey
        py = centre[1] + side * d * ey + lat * ex
        W = float(np.clip(width_median_m * math.exp(rng.normal(0.0, 0.55)), *width_m))
        if any(math.hypot(px - c['at'][0], py - c['at'][1]) < 0.67 * 0.5 * (W + c['width_m']) for c in cones):
            continue
        hw = rng.uniform(*hw_ratio)
        cr = rng.uniform(*crater_ratio)
        cone = dict(at=(px, py), width_m=W, hw_ratio=hw, crater_ratio=cr,
                    flank_deg=_feasible_flank(rng.uniform(*flank_deg), hw, cr),
                    crater_depth_frac=rng.uniform(*crater_depth_frac), outline_noise=float(outline_noise),
                    seed=int(rng.integers(1 << 30)))
        if rng.random() < breach_fraction:
            cone.update(breach_azimuth_deg=math.degrees(math.atan2(px - centre[0], py - centre[1])),
                        breach_width_deg=rng.uniform(35.0, 70.0))
        cones.append(cone)
    return cones


def cinder_field(window, count=12, width_m=(330.0, 1400.0), hw_ratio=0.18, crater_ratio=(0.30, 0.45),
                 flank_deg=(31.0, 33.0), vent_lines=2, line_trend_deg=None, line_spread_m=350.0,
                 age_yr=(0.0, 500e3), breach_fraction=0.3, outline_noise=0.05, seed=0):
    """A cinder cone field (the cinder_cones recipe): `count` cones along `vent_lines` straight vent alignments
    crossing the window (x0, y0, size) in metres, trends within 25 degrees of line_trend_deg (random if None),
    scattered line_spread_m (1 sigma) off their line, blue-noise spaced (no overlap beyond a fifth of the smaller
    cone), basal widths log-uniform in width_m (H 60-250 m at H/W 0.18), ages uniform in age_yr for the aging stage,
    some breached away from the field centre. Returns a list of cinder_cone argument dicts."""
    x0, y0, size = (float(v) for v in window)
    rng = _rng(seed, 41)
    trend = rng.uniform(0.0, 180.0) if line_trend_deg is None else float(line_trend_deg)
    lines = []
    for _ in range(int(vent_lines)):
        a = trend + rng.uniform(-25.0, 25.0)
        px, py = x0 + size * rng.uniform(0.3, 0.7), y0 + size * rng.uniform(0.3, 0.7)
        lines.append((px, py, *compass(a)))
    cones, tries = [], 0
    margin = 0.06 * size
    hw_lo, hw_hi = (hw_ratio, hw_ratio) if np.isscalar(hw_ratio) else hw_ratio
    while len(cones) < count and tries < 200 * count:
        tries += 1
        lx, ly, ex, ey = lines[int(rng.integers(len(lines)))]
        s = rng.uniform(-0.6, 0.6) * size
        lat = rng.normal(0.0, line_spread_m)
        px, py = lx + s * ex - lat * ey, ly + s * ey + lat * ex
        W = float(math.exp(rng.uniform(math.log(width_m[0]), math.log(width_m[1]))))
        if not (x0 + margin + W / 2 < px < x0 + size - margin - W / 2 and
                y0 + margin + W / 2 < py < y0 + size - margin - W / 2):
            continue
        if any(math.hypot(px - c['at'][0], py - c['at'][1]) < 0.5 * (W + c['width_m']) - 0.2 * min(W, c['width_m'])
               for c in cones):
            continue
        hw = rng.uniform(hw_lo, hw_hi)
        cr = rng.uniform(*crater_ratio)
        cone = dict(at=(px, py), width_m=W, hw_ratio=hw, crater_ratio=cr,
                    flank_deg=_feasible_flank(rng.uniform(*flank_deg), hw, cr),
                    crater_depth_frac=rng.uniform(0.3, 0.5), rim_tilt=rng.uniform(0.0, 0.12),
                    tilt_azimuth_deg=rng.uniform(0.0, 360.0), outline_noise=float(outline_noise),
                    age_yr=float(rng.uniform(*age_yr)), seed=int(rng.integers(1 << 30)))
        if rng.random() < breach_fraction:
            cone.update(breach_azimuth_deg=math.degrees(math.atan2(px - (x0 + size / 2), py - (y0 + size / 2))),
                        breach_width_deg=rng.uniform(40.0, 70.0))
        cones.append(cone)
    return cones


# ====================================================================== lava flows (design 4.7, DOWNFLOW)

_NB = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))      # (di column, dj row), common.glsl's
_NB_LEN = np.array([math.hypot(a, b) for a, b in _NB])


def lava_walkers(h, cell, start, walkers=400, length_m=6000.0, dh_m=3.0, seed=0, salt=0):
    """DOWNFLOW (Favalli et al. 2005), vectorised over walkers: from the start cell (column i, row j) every walker
    steps to the neighbour with the steepest descent of the surface perturbed by U(-dh, dh) (drawn per neighbour and
    step), until its path is length_m long, it leaves the grid or no perturbed neighbour lies lower (a pit stops it).
    Returns the fraction of walkers that passed through each cell (0..1), float64 (n, n). Deterministic per (seed,
    salt): numpy's generator seeded with both."""
    h = np.asarray(h, np.float64)
    ny, nx = h.shape
    rng = np.random.default_rng([abs(int(seed)) & 0xFFFFFFFF, 7177, int(salt)])
    N = int(walkers)
    i = np.full(N, int(np.clip(round(start[0]), 1, nx - 2)), np.int64)
    j = np.full(N, int(np.clip(round(start[1]), 1, ny - 2)), np.int64)
    dist = np.zeros(N)
    alive = np.ones(N, bool)
    visits = np.zeros(ny * nx, np.float64)
    di = np.array([d[0] for d in _NB])
    dj = np.array([d[1] for d in _NB])
    hp = np.pad(h, 1, mode='constant', constant_values=np.inf)          # off the grid is never lower
    lim = float(length_m)
    np.add.at(visits, j * nx + i, 1.0)
    while alive.any():
        a = np.nonzero(alive)[0]
        here = h[j[a], i[a]] + rng.uniform(-dh_m, dh_m, a.size)
        nb = hp[j[a, None] + 1 + dj[None, :], i[a, None] + 1 + di[None, :]] + rng.uniform(-dh_m, dh_m, (a.size, 8))
        drop = (here[:, None] - nb) / (_NB_LEN[None, :] * cell)
        k = np.argmax(drop, axis=1)
        ok = drop[np.arange(a.size), k] > 0.0
        stop = a[~ok]
        alive[stop] = False
        a, k = a[ok], k[ok]
        i[a] += di[k]
        j[a] += dj[k]
        dist[a] += _NB_LEN[k] * cell
        off = (i[a] <= 0) | (j[a] <= 0) | (i[a] >= nx - 1) | (j[a] >= ny - 1) | (dist[a] >= lim)
        np.add.at(visits, j[a] * nx + i[a], 1.0)          # a walker re-crossing a cell counts again: clipped at 1
        alive[a[off]] = False
    return np.minimum(visits.reshape(ny, nx) / N, 1.0)


def lava_surface(P, cell, thickness_m, x=None, y=None, p_edge=0.04, margin_m=None, levee=0.3, rough=0.12, age=0.0,
                 seed=0):
    """A lava flow's added height and footprint from the walkers' passage fraction P (lava_walkers): the footprint
    is where P exceeds p_edge (smoothed), the flow a flat-topped sheet thickness_m thick standing on its margins at a
    front margin_m wide (default 1.5 x the thickness: lava fronts stand at 30-40 degrees), levees thickness x levee
    higher along both edges, a rough top (pressure ridges: world noise at 6 and 2 x the thickness, rough x the
    thickness, needs x, y). age 0..1 dulls the front and the roughness (an older flow, weathered and mantled).
    Returns (added metres, footprint 0..1)."""
    from .hillslope import gaussian_blur
    mm = 1.5 * float(thickness_m) if margin_m is None else float(margin_m)
    mm *= 1.0 + 2.0 * float(age)
    mc = max(mm / float(cell), 0.6)
    core = (gaussian_blur(np.asarray(P, np.float64), 0.8) > p_edge).astype(np.float64)
    f1 = gaussian_blur(core, mc)
    plate = smoothstep(0.2, 0.7, f1)
    f2 = gaussian_blur(core, 3.0 * mc)
    lev = plate * (1.0 - smoothstep(0.6, 0.97, f2))
    T = float(thickness_m) * (plate + float(levee) * lev)
    if rough and x is not None:
        r = (fbm(x, y, 6.0 * float(thickness_m), seed + 91, octaves=2)
             + 0.5 * fbm(x, y, 2.0 * float(thickness_m), seed + 93, octaves=2))
        T = T + float(rough) * (1.0 - 0.7 * float(age)) * float(thickness_m) * r * plate
    return np.maximum(T, 0.0), plate


# ====================================================================== calderas (design 4.7)

def scallop_outline(az, count, amp, seed, salt=51, sharpness=0.6, round_deg=1.5):
    """A scalloped ring as a radius factor of azimuth (radians or an AzimuthSampler; zero mean): `count` arcs bulging
    outward and meeting in inward cusps (the promontories between collapse embayments), each arc's span jittered and
    its bulge sized 0.3-1.7 x amp. sharpness 0.5 makes semicircular arcs; larger values blunt them. The cusps are
    rounded by a Gaussian of round_deg along the ring (1.5 degrees is about 120 m at a 4.5 km radius), so a promontory
    is a rounded nose, not a radial crease down the wall."""
    table = _scallop_table(count, amp, seed, salt, sharpness)
    if round_deg > 0:
        sig = float(round_deg) / 360.0 * _AZ_SAMPLES
        k = np.fft.rfftfreq(_AZ_SAMPLES) * _AZ_SAMPLES            # cycles per turn
        g = np.exp(-0.5 * (TAU * k * sig / _AZ_SAMPLES) ** 2)
        body = np.fft.irfft(np.fft.rfft(table[:-1]) * g, _AZ_SAMPLES)
        table = np.append(body, body[0])
    return azimuth_sampler(az)(table)


def _scallop_table(count, amp, seed, salt, sharpness):
    rng = _rng(seed, salt)
    n = int(count)
    cusps = np.sort(np.mod((np.arange(n) + rng.uniform(-0.4, 0.4, n)) * TAU / n + rng.uniform(0.0, TAU), TAU))
    size = rng.uniform(0.3, 1.7, n)                      # embayments of very different depths, never a flower
    a = np.mod(AZ_TABLE_ANGLES, TAU)
    i = np.searchsorted(cusps, a, side='right') - 1                  # the arc that starts at cusps[i] (i = -1 wraps)
    c0 = np.where(i >= 0, cusps[i % n], cusps[-1] - TAU)
    c1 = np.where(i + 1 < n, cusps[(i + 1) % n], cusps[0] + TAU)
    c1 = np.where(i < 0, cusps[0], c1)
    t = np.clip((a - c0) / (c1 - c0), 0.0, 1.0)
    bulge = (4.0 * t * (1.0 - t)) ** float(sharpness)
    mean = math.gamma(sharpness + 1.0) ** 2 / math.gamma(2.0 * sharpness + 2.0) * 4.0 ** sharpness   # E[(4t(1-t))^s]
    return float(amp) * size[i % n] * (bulge - mean)


def wall_column(height_m, wall_deg, strong_deg=72.0, strong_frac=0.35, layer_m=(25.0, 110.0), weak_min_deg=24.0,
                seed=0, salt=55):
    """A rock wall's column from its foot up, as the layers that make its cliffs and benches: alternating weak beds
    (tephra, breccia; a crater's shale) and strong ledges (lava flows, welded tuff; a crater's limestone and
    sandstone), each (thickness_m, angle_deg). strong_frac of the height is strong at strong_deg; the weak angle is
    set so the column's whole run equals a plain face at wall_deg, so the wall keeps its mean slope and position
    (its cliffs stand where weak beds lie gentler), floored at weak_min_deg. Thicknesses uniform in layer_m (strong
    ones 0.7 x), rescaled to the height."""
    H = float(height_m)
    rng = _rng(seed, salt)
    lay, z, strong = [], 0.0, bool(rng.random() < 0.5)
    sf = float(np.clip(strong_frac, 0.0, 0.9))
    while z < H:
        th = rng.uniform(*layer_m) * (0.7 if strong else 1.0)
        th *= (sf / 0.5) if strong else ((1.0 - sf) / 0.5)
        lay.append([max(th, 1.0), strong])
        z += lay[-1][0]
        strong = not strong
    k = H / z
    for L in lay:
        L[0] *= k
    hs = sum(t for t, s in lay if s)
    hw = H - hs
    ts = math.tan(math.radians(strong_deg))
    run = H / math.tan(math.radians(wall_deg)) - hs / ts
    weak_deg = float(wall_deg) if hw <= 1e-6 else (
        math.degrees(math.atan(hw / run)) if run > 1e-6 else float(wall_deg))
    weak_deg = float(np.clip(weak_deg, weak_min_deg, wall_deg))
    return [(t, strong_deg if s else weak_deg) for t, s in lay]


def column_profile(column, talus_m=0.0, talus_deg=35.0):
    """(u, z) tables of a wall built from its column (wall_column) over a talus apron talus_m high at talus_deg: u
    the horizontal run from the wall's foot outward, z the height above it; piecewise linear, increasing."""
    us, zs = [0.0], [0.0]
    if talus_m > 0:
        us.append(talus_m / math.tan(math.radians(talus_deg)))
        zs.append(float(talus_m))
    for t, a in column:
        us.append(us[-1] + t / math.tan(math.radians(a)))
        zs.append(zs[-1] + t)
    return np.array(us), np.array(zs)


def caldera_wall_run_m(wall_height_m, wall_deg=42.0, talus_deg=35.0, talus_frac=0.35):
    """The horizontal run of a caldera wall: a talus apron at talus_deg over the lowest talus_frac of the wall
    height, then the rock face at wall_deg up to the rim."""
    th = float(talus_frac) * float(wall_height_m)
    return th / math.tan(math.radians(talus_deg)) + (float(wall_height_m) - th) / math.tan(math.radians(wall_deg))


def caldera_collapse(x, y, h_before, centre, rim_radius_m, rim_height_m, floor_m, wall_deg=42.0, talus_deg=35.0,
                     talus_frac=0.35, scallops=8, scallop_amp=0.05, radius_noise=0.02, edge_noise=0.01,
                     elongation=1.0, elongation_azimuth_deg=0.0, crest_round_m=40.0, round_crest=True, cliffs=None,
                     seed=0):
    """A ring-fault collapse of an edifice (design 4.7 steps 2-4, analytically).
    cliffs             None: a plain rock face at wall_deg. A dict (strong_deg 72, strong_frac 0.35, layer_m
                       (25, 110), sectors 7): the face is the layered column of wall_column, its strong ledges
                       standing as cliffs over weaker beds at the same mean angle (Crater Lake's walls: lava flows
                       and welded tuffs over tephra); `sectors` columns of their own spread round the ring and blended
                       by azimuth, so cliffs swell, pinch out and change height round the caldera. The result then
                       carries `strength`: the threshold the wall was built at (tangent, 10 % over its local slope;
                       NaN off the wall), for a threshold stage to keep it standing.

    h_before           the edifice's surface at (x, y), metres (the same frame as floor_m and rim_height_m)
    rim_radius_m       the caldera rim's mean radius (where the walls meet the old surface)
    rim_height_m       the edifice's mean height at that radius, to size the walls
    floor_m            the collapsed floor's height: flat, sediment-filled (a lake fills to its own level later)
    wall_deg           the rock face (design: thresholded at 40-45 degrees)
    talus_deg          the talus apron at the wall's foot (repose 33-37), over talus_frac of the wall height
    scallops           collapse embayments around the ring (design: 4-8), scallop_amp their outward bulge (fraction of
                       the radius); radius_noise low-frequency outline noise (harmonics 1-5); edge_noise the points
                       and coves along the ring (harmonics 10-48); elongation the outline's long / short axis ratio
                       (about), the long axis along elongation_azimuth_deg, the mean radius kept

    The floor's edge is the mean rim radius minus the wall's run, shaped by the scallops, noise and elongation; the
    collapse surface rises from it as talus then rock; the edifice is cut down to that surface wherever it stands
    above it, with the rim crest rounded over crest_round_m (round_crest False: a plain minimum, for a surface whose
    rim is rounded already). Outside the rim the edifice is unchanged.

    Returns dict(height, talus (the apron's thickness over the rock face), floor (1 on the flat floor))."""
    Hw = float(rim_height_m) - float(floor_m)
    if Hw <= 0.0:
        raise ValueError(f'caldera: the floor {floor_m:.0f} m must lie below the rim {rim_height_m:.0f} m')
    run = caldera_wall_run_m(Hw, wall_deg, talus_deg, talus_frac)
    r_floor = float(rim_radius_m) - run
    if r_floor <= 0.05 * float(rim_radius_m):
        raise ValueError(f'caldera: walls of {Hw:.0f} m at {wall_deg}/{talus_deg} degrees run {run:.0f} m, wider than '
                         f'the rim radius {rim_radius_m:.0f} m allows; widen the caldera or steepen the walls')
    r, az = polar(x, y, centre)
    shape = 1.0 + (float(elongation) - 1.0) * (np.cos(az - math.radians(elongation_azimuth_deg)) ** 2
                                                - 0.5)
    sampler = azimuth_sampler(az)
    if radius_noise:
        shape = shape * (1.0 + float(radius_noise) * azimuth_noise(sampler, seed, 52, 1, 5))
    if edge_noise:
        shape = shape * (1.0 + float(edge_noise) * azimuth_noise(sampler, seed, 53, 10, 48, decay=1.0))
    if scallops:
        shape = shape * (1.0 + scallop_outline(sampler, scallops, scallop_amp, seed))
    u = r - r_floor * shape                                 # outward distance from the floor's edge
    tt, tw = math.tan(math.radians(talus_deg)), math.tan(math.radians(wall_deg))
    th = float(talus_frac) * Hw
    talus_line = floor_m + tt * u
    strength = None
    if cliffs:
        rock_line, strength = _layered_face(u - th / tt, az, Hw - th, wall_deg, dict(cliffs), seed)
        rock_line = rock_line + floor_m + th
    else:
        rock_line = floor_m + th + tw * (u - th / tt)
    k = 0.02 * Hw
    surface = smooth_max(smooth_max(talus_line, rock_line, k), floor_m, k)
    rock = smooth_max(rock_line, floor_m, k)
    hb = np.asarray(h_before, np.float64)
    kr = float(crest_round_m) * (tw + 0.1)
    h = crest_union(hb, surface, kr) if round_crest else np.minimum(hb, surface)
    talus = np.clip(np.minimum(surface, hb) - rock, 0.0, None)
    floor = (u < 0.0).astype(np.float64)
    out = dict(height=h, talus=talus, floor=floor)
    if strength is not None:
        out['strength'] = np.where((u > th / tt) & (surface < hb + 1.0), strength, np.nan)
    return out


def _layered_face(u, az, height_m, wall_deg, spec, seed):
    """The rock face of a layered wall: (height above the face's foot at run u (metres outward), its threshold
    tangent). `sectors` columns (wall_column, seeds of their own) at evenly spread azimuths, blended by von Mises
    weights (kappa 8: each sector's own column about 90 % at its centre); beyond a column's top the face continues
    at wall_deg, below its foot at its first layer's angle."""
    n = int(spec.pop('sectors', 7))
    rng = _rng(seed, 57)
    phase = rng.uniform(0.0, TAU)
    tw = math.tan(math.radians(wall_deg))
    zs = np.zeros_like(u)
    ws = np.zeros_like(u)
    sl = np.zeros_like(u)
    for k in range(n):
        col = wall_column(height_m, wall_deg, seed=int(seed) * 31 + k, **spec)
        uk, zk = column_profile(col)
        w = np.exp(8.0 * (np.cos(az - (phase + TAU * k / n)) - 1.0))
        z = np.interp(u, uk, zk)
        z = np.where(u > uk[-1], zk[-1] + tw * (u - uk[-1]), z)
        z = np.where(u < 0.0, u * (zk[1] / max(uk[1], 1e-9)), z)
        seg = np.clip(np.searchsorted(uk, u) - 1, 0, len(uk) - 2)
        s = (zk[seg + 1] - zk[seg]) / np.maximum(uk[seg + 1] - uk[seg], 1e-9)
        s = np.where((u > uk[-1]) | (u < 0.0), np.where(u < 0.0, zk[1] / max(uk[1], 1e-9), tw), s)
        zs += w * z
        sl += w * s
        ws += w
    return zs / ws, 1.1 * sl / ws


# ====================================================================== reference presets (measured)
# The parameters that put each analytic shape on its reference: measured from the reference DEMs by
# blender/tests/terrain_new/volcanoes_craters/test_references.py, in the reference's local metres (x east, y north
# of the tile centre). Heights are metres above sea level, so `base_m` is the foot the cone stands on.

FUJI = dict(
    # mount_fuji (GSI DEM10B at 40 m): the crater centre 300 m east, 260 m north of the tile centre (Kengamine);
    # the median radial profile 0.5-13 km fits the exponential cone at 12.9 m rms with H 2983 m above a 755 m foot,
    # lambda 4215 m (upper slope 35.3 degrees) and R 19.9 km. The summit is flat-topped: the ring medians stay at
    # 3697-3708 m from 300 to 400 m out before the flank falls (a truncated cone with sharp shoulders seen from afar),
    # so the 220 m deep pit (the real crater: about 230 m deep, 780 m across) sits inside a 120 m summit ring and the
    # flank starts at 420 m (near-summit ring medians 22 m rms; a plain 400 m bowl leaves a rounded top, 40 m).
    centre=(300.0, 260.0), base_m=755.0, height_m=2983.0, radius_m=19860.0, upper_slope_deg=35.3,
    crater_radius_m=300.0, crater_depth_m=220.0, crater_floor_frac=0.35, summit_platform_m=120.0,
    # the parasitic cones and the Hoei crater sit along a NW-SE rift; the flanks reach farther NW and SE. The rim's
    # height noise stays small: seen from afar the real summit's skyline is flat within 30 m over 800 m, and 0.012
    # domed it 50 m (0.004: flat within 9 m)
    elongation=1.12, rift_azimuth_deg=315.0, radius_noise=0.05, height_noise=0.004,
    flank_craters=[dict(at=(1900.0, -1650.0), radius_m=650.0, depth_m=330.0, rim_m=70.0)],
    rift=dict(count=18, distance_m=(2500.0, 11500.0), spread_m=2800.0, width_median_m=650.0,
              width_m=(300.0, 1800.0), hw_ratio=(0.10, 0.17), crater_ratio=(0.15, 0.32),
              crater_depth_frac=(0.08, 0.3)),
    seed=3,
)

CRATER_LAKE = dict(
    # crater_lake (3DEP at 14 m): the lake surface at 1880.5 m, the shore 4.2 km from the outline's centre on average
    # (3.8-4.8 km), the outline long toward compass 72/252 degrees (harmonic 2: 8.5 % of the radius); the rim about
    # 570 m behind the shore, 389 m above the lake on average (183-604 m, highest south and west); wall slopes above the
    # water p50 35 / p90 51 degrees; the outer flank (Mount Mazama's remnant) fits an exponential cone at 17 m rms over
    # 4.8-9.4 km with a base of 1512 m, H 1639 m and lambda 5474 m (upper slope 16.7 degrees). The real lake floor is
    # about 590 m below the surface.
    centre=(95.0, 9.0), lake_m=1880.5, floor_m=1300.0,
    edifice=dict(base_m=1512.0, height_m=1639.0, radius_m=25000.0, upper_slope_deg=16.7, crater_radius_m=300.0,
                 height_noise=0.15, radius_noise=0.03),
    # parasitic cones on the outer flank (the real tile has Red Cone and lesser cones north and west of the rim)
    flank_cones=dict(count=5, distance_m=(5600.0, 8800.0), spread_m=2500.0, width_median_m=900.0,
                     width_m=(450.0, 1500.0), hw_ratio=(0.10, 0.16), crater_ratio=(0.12, 0.25),
                     crater_depth_frac=(0.05, 0.2), breach_fraction=0.0),
    flank_cone_azimuth_deg=330.0,
    rim_radius_m=4700.0, wall_deg=38.0, talus_deg=33.0, talus_frac=0.6, scallops=9, scallop_amp=0.12,
    radius_noise=0.025, edge_noise=0.012, elongation=1.214, elongation_azimuth_deg=72.0,
    # Wizard Island (1.32 km2 at the waterline, its summit 230 m above the lake, 1.4-1.5 km from the west shore's
    # line, a 90 m crater): a cinder cone on a lava platform whose flat top stands just above the water, placed on
    # this outline's floor with water all round (about 460 m to the west shore, as the real one has); both stand on
    # the floor and abut the walls (combined by max, not added onto the wall). The platform's flat top is 730 m in
    # radius, 4.5 m above the water; its sides fall at 31.5 degrees to the floor 585 m below.
    inner_cones=[dict(at=(-2950.0, -280.0), width_m=3409.0, hw_ratio=0.1716, crater_ratio=0.4283, flank_deg=31.5,
                      crater_depth_frac=0.0, crest_round_m=40.0, outline_noise=0.12, seed=21),
                 dict(at=(-2733.0, -385.0), width_m=1100.0, hw_ratio=0.205, crater_ratio=0.082, flank_deg=33.0,
                      crater_depth_frac=0.13, outline_noise=0.04, seed=22)],
    seed=5,
)

SP_CRATER = dict(
    # SP Crater (Terrain Tiles 7.8 m over 3DEP 10 m, the triage's cache): the cone 236 m above its base, basal width
    # about 1320 m (H/W 0.18, Wood's ratio), crater rim 364 m across (0.28 W), 96 m deep, flanks 29-31 degrees
    # median with a concave toe about 150 m wide, inner walls about 30 degrees; its crater lies a little south-east
    # of the cone's centre.
    at=(-12.0, -4.0), width_m=1320.0, hw_ratio=0.18, crater_ratio=0.28, flank_deg=32.0, crater_wall_deg=30.0,
    crater_depth_frac=0.41, rim_tilt=0.05, tilt_azimuth_deg=200.0, outline_noise=0.04, seed=9,
)


def fuji_surface(x, y, preset=FUJI):
    """The FUJI preset's analytic surface (metres above sea level) at world points: the cone, its crater, the Hoei
    crater and the rift cones, on a flat foot at base_m."""
    p = dict(preset)
    rift = p.pop('rift')
    base = p.pop('base_m')
    cones = rift_cones(p['centre'], p['rift_azimuth_deg'], seed=p['seed'], **rift)
    out = stratovolcano(x, y, cones=cones, **p)
    return base + out['height']


def crater_lake_surface(x, y, preset=CRATER_LAKE):
    """The CRATER_LAKE preset's analytic surface (metres above sea level): the edifice, the collapse, the inner cone.
    The floor is at floor_m; the lake fills it to lake_m (the reference DEM carries the lake as its flat surface)."""
    p = dict(preset)
    e = dict(p['edifice'])
    base = e.pop('base_m')
    cones = rift_cones(p['centre'], p['flank_cone_azimuth_deg'], seed=p['seed'], **p['flank_cones'])

    def edifice_at(xq, yq):
        return base + stratovolcano(xq, yq, centre=p['centre'], seed=p['seed'], **e)['height']

    edifice = edifice_at(x, y) + cinder_cones(x, y, cones)
    rim_h = _ring_mean(edifice_at, p['centre'], p['rim_radius_m'])
    keys = ('wall_deg', 'talus_deg', 'talus_frac', 'scallops', 'scallop_amp', 'radius_noise', 'edge_noise',
            'elongation', 'elongation_azimuth_deg', 'seed')
    out = caldera_collapse(x, y, edifice, p['centre'], p['rim_radius_m'], rim_h, p['floor_m'],
                           **{k: p[k] for k in keys})
    return np.maximum(out['height'], p['floor_m'] + cinder_cones(x, y, p['inner_cones']))


def _ring_mean(surface, centre, radius_m, samples=720):
    a = np.arange(samples) * (TAU / samples)
    return float(np.mean(surface(centre[0] + radius_m * np.sin(a), centre[1] + radius_m * np.cos(a))))


# ====================================================================== stage ops
# The wave-1 convention (recipes/__init__.py finds OPS here): op(fields, level, params, seed) writes the level's
# Fields in place. `fields` maps names to float32 arrays [row j, column i] with row 0 the south edge (design 2.1,
# 2.4); `level` carries x0, y0 (the window's south-west corner), cell and n (2.2) as attributes, keys or the tuple
# (x0, y0, side, cell, n). Shapes are evaluated at the cell centres x = x0 + (i + 0.5) cell, y = y0 + (j + 0.5) cell.
#
# Stamped once, sharp on every level (stamp_add): a constructional shape is added whole on the first level its
# stage runs on; a finer level has inherited it already (Catmull-Rom x2 of the parent's h), so there the op adds only
# what the parent's grid could not hold: the shape at this level's cells less the parent-grid shape upsampled the
# same way. The stage can therefore run on every level from the one that resolves the shape down ('all', or
# 'cell<=<metres>'): the shape is in h exactly once and its rims stay sharp at 0.5 m. The levels must be contiguous
# (each level's parent ran the stage too). A field 'stamp_<op>_<params hash>' records the shape's share per level.

def _stamp_key(op, params):
    import hashlib
    import json
    return f'stamp_{op}_' + hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:8]


def stamp_add(fields, level, key, evaluate, supersample=1):
    """Add a world-space shape's contributions to a level's fields once per terrain (see the section note).
    evaluate(x, y) returns {field name: metres to add}, 'h' among them; fields that are absent are skipped."""
    from ..core import grid as _grid
    x0, y0, cell, n = level_window(level)
    s = int(supersample)

    def on(ox, oy, c, m):
        g = (np.arange(m * s) + 0.5) * (c / s)
        X, Y = np.meshgrid(ox + g, oy + g)
        return {k: box_down(np.asarray(v, np.float64), s) for k, v in evaluate(X, Y).items()}

    here = on(x0, y0, cell, n)
    add = dict(here)
    if key in fields:                              # inherited: the parent's h holds the shape at the parent's grid
        if n % 2:
            raise ValueError(f'{key}: a level of {n} cells cannot be a x2 child')
        m, cp = n // 2, 2.0 * cell
        parent = on(x0 - 2.0 * cp, y0 - 2.0 * cp, cp, m + 4)       # the window and the 2 cells crop_upsample2 reads
        # as Fields.inherit upsampled them: Catmull-Rom for h and bed, bilinear for every other field
        add = {k: here[k] - _grid.crop_upsample2(parent[k], 2, 2, m, 'catmull' if k in ('h', 'bed') else 'bilinear')
               for k in here}
    for k, v in add.items():
        if k in fields:
            fields[k] = np.asarray(fields[k], np.float32) + v.astype(np.float32)
    fields[key] = here['h'].astype(np.float32)
    return fields


def level_window(level):
    """(x0, y0, cell, n) of a level given as an object, a dict or a (x0, y0, side, cell, n) tuple."""
    if isinstance(level, dict):
        return float(level['x0']), float(level['y0']), float(level['cell']), int(level['n'])
    if isinstance(level, (tuple, list)):
        x0, y0, _side, cell, n = level
        return float(x0), float(y0), float(cell), int(n)
    return float(level.x0), float(level.y0), float(level.cell), int(level.n)


def cell_centres(level, supersample=1):
    """World x, y of a level's cell centres, shaped (n, n) [row j, column i], row 0 south; with supersample s, the
    (n s, n s) sub-cell centres (average back with box_down)."""
    x0, y0, cell, n = level_window(level)
    s = int(supersample)
    c = (np.arange(n * s) + 0.5) * (cell / s)
    return np.meshgrid(x0 + c, y0 + c)


def box_down(a, s):
    """Average s x s blocks: the supersampled field back to cells."""
    if s == 1:
        return a
    n = a.shape[0] // s
    return a.reshape(n, s, n, s).mean(axis=(1, 3))


# ---------------------------------------------------------------------- with the level runner (second half)
# run.py calls an op that takes ctx with its StageContext (solvers/fluvial.py): role 'grow' on the coarsest level,
# 'refine' below it; prepass, the coarsest level's coarse-to-fine pass (None on its own cells); pins, a child level's
# border band (None on the coarsest level); device. An op taking ctx pins its own border band (run.py pulls the band
# only after ops without ctx), and an op with evolves = True is called on every pass of the coarsest level. The
# volcanic ops skip the pre-passes: there the surroundings grow (their fluvial stage runs on every pass), and the
# volcano is stamped on the level's own cells, after them, so the surroundings' long run never erodes a cone.

def _prepass(ctx):
    """True on a coarse-to-fine pre-pass of the coarsest level."""
    return ctx is not None and getattr(ctx, 'prepass', None) is not None


def _pull_band(fields, ctx):
    """A child level's border band pulled to its parent's surface (weight 1 at the edge easing to 0 at 16 cells in),
    as run.py does after ops without ctx: the level meets its parent exactly at the seam."""
    pins = getattr(ctx, 'pins', None) if ctx is not None else None
    if pins is None or 'h' not in fields:
        return
    w = np.clip(np.asarray(pins['pin_w'], np.float64), 0.0, 1.0)
    fields['h'] = (np.asarray(fields['h'], np.float64) * (1.0 - w)
                   + np.asarray(pins['pin_h'], np.float64) * w).astype(np.float32)
    if 'bed' in fields:
        fields['bed'] = np.minimum(fields['bed'], fields['h'])


def _device(ctx):
    from . import fluvial as FL
    return ctx.device if (ctx is not None and getattr(ctx, 'device', None) is not None) else FL.device()


def _world_field(spec, level, seed, dev):
    """A core/world_noise field spec at the level's cells: on the GPU in production, numpy on the twin device."""
    from ..core import world_noise as N
    if dev is not None and getattr(dev, 'name', '') == 'gpu':
        return N.field_gpu(spec, level, seed).astype(np.float64)
    x, y = level.xy()
    return np.asarray(N.field(spec, x, y, seed), np.float64)


def _unit_fbm(level, wavelength_m, seed, dev, octaves=3):
    """fbm of unit standard deviation (core/world_noise's fbm has 1/3)."""
    return 3.0 * _world_field({'kind': 'fbm', 'wavelength_m': float(wavelength_m), 'octaves': int(octaves)},
                              level, seed, dev)


def _f32(a):
    return np.asarray(a, np.float32)


# ---------------------------------------------------------------------- constructional stamps

def op_stratovolcano(fields, level, params, seed, ctx=None):
    """Stage op 'stratovolcano': params are stratovolcano's (plus rift=dict(rift_cones arguments) for parasitic
    cones, and supersample). Adds the cone to h once (stamp_add: whole on its first level, only the finer detail
    below); bed takes the rock (all but the parasitic cones' scoria). Skips the coarsest level's pre-passes."""
    if _prepass(ctx):
        return fields
    p = dict(params)
    s = int(p.pop('supersample', 1))
    rift = p.pop('rift', None)
    p.setdefault('seed', seed)
    if rift:
        p['cones'] = list(p.get('cones', ())) + rift_cones(p.get('centre', (0.0, 0.0)), p.get('rift_azimuth_deg', 0.0),
                                                           seed=p['seed'], **rift)

    def evaluate(x, y):
        out = stratovolcano(x, y, **p)
        return {'h': out['height'], 'bed': out['height'] - out['cinder']}
    stamp_add(fields, level, _stamp_key('stratovolcano', dict(params, seed=p['seed'])), evaluate, s)
    _pull_band(fields, ctx)
    return fields


def cones_of(params, seed):
    """The cinder cones a 'cinder_cones' (or 'lava_flows') stage stands for: params cones=[cinder_cone dicts] and/or
    field=dict(cinder_field arguments; its seed defaults to the stage seed), each aged when kappa_m2_per_yr is given
    (kappa_t_m2 = kappa x the cone's age_yr, unless the cone carries its own)."""
    cones = [dict(c) for c in params.get('cones', ())]
    if params.get('field'):
        f = dict(params['field'])
        f.setdefault('seed', seed)
        cones += cinder_field(**f)
    kappa = float(params.get('kappa_m2_per_yr', 0.0) or 0.0)
    if kappa > 0.0:
        for c in cones:
            c.setdefault('kappa_t_m2', kappa * float(c.get('age_yr', 0.0)))
    return cones


def op_cinder_cones(fields, level, params, seed, ctx=None):
    """Stage op 'cinder_cones': params cones=[cinder_cone dicts] and/or field=dict(cinder_field arguments), and
    kappa_m2_per_yr (linear creep: each cone aged by kappa x its age_yr, aged_cinder_cone). Adds the cones to h once
    (stamp_add); bed is unchanged, so the cones are loose scoria (h - bed) for the talus stage."""
    if _prepass(ctx):
        return fields
    p = dict(params)
    s = int(p.pop('supersample', 1))
    cones = cones_of(p, seed)
    stamp_add(fields, level, _stamp_key('cinder_cones', dict(params, seed=seed)),
              lambda x, y: {'h': cinder_cones(x, y, cones)}, s)
    _pull_band(fields, ctx)
    return fields


def op_caldera_collapse(fields, level, params, seed, ctx=None):
    """Stage op 'caldera_collapse': params are caldera_collapse's (centre, rim_radius_m, floor_m or
    floor_below_rim_m, cliffs, ...), plus inner_cones=[cinder_cone dicts, `at` relative to the centre] standing on
    the floor (Wizard Island), combined by max so they abut the walls rather than stack onto them. rim_height_m
    defaults to the mean of h within a cell of the rim circle on the first level the stage runs on, kept in the field
    'caldera_rim_m' for the finer levels (whose h is collapsed there already). The collapse is a minimum and the cones
    a maximum, so running it on every level sharpens the walls without stacking. Lowers h and bed to the collapse
    surface; talus takes the apron's thickness; with cliffs, Sc takes the strength the walls were built at (tan 40
    degrees elsewhere) for a threshold stage; 'caldera_floor' marks the floor."""
    if _prepass(ctx):
        return fields
    p = dict(params)
    p.setdefault('seed', seed)
    inner = p.pop('inner_cones', ())
    below = p.pop('floor_below_rim_m', None)
    key = _stamp_key('caldera_collapse', dict(params, seed=p['seed']))
    x, y = cell_centres(level)
    h = np.asarray(fields['h'], np.float64)
    if 'rim_height_m' not in p:
        if 'caldera_rim_m' in fields:
            p['rim_height_m'] = float(np.mean(fields['caldera_rim_m']))
        else:
            _x0, _y0, cell, _n = level_window(level)
            r, _ = polar(x, y, p['centre'])
            ring = np.abs(r - float(p['rim_radius_m'])) < max(cell, 1e-6)
            if not ring.any():
                raise ValueError('caldera_collapse: the rim circle lies outside this level; pass rim_height_m')
            p['rim_height_m'] = float(h[ring].mean())
    if 'floor_m' not in p:
        if below is None:
            raise ValueError('caldera_collapse: give floor_m (the field frame) or floor_below_rim_m')
        p['floor_m'] = p['rim_height_m'] - float(below)
    # on a level that inherited the collapse, the rim is rounded already: a plain minimum sharpens the walls (a second
    # crest union would round the rounded crest again)
    out = caldera_collapse(x, y, h, round_crest=key not in fields, **p)
    fields['h'] = _f32(out['height'])
    if 'bed' in fields:
        fields['bed'] = np.minimum(fields['bed'], _f32(out['height'] - out['talus']))
    if 'talus' in fields:
        fields['talus'] = np.maximum(fields['talus'], _f32(out['talus']))
    if inner:
        c0 = p['centre']
        cones = [dict(c, at=(c0[0] + c['at'][0], c0[1] + c['at'][1])) for c in inner]
        fields['h'] = np.maximum(fields['h'], _f32(float(p['floor_m']) + cinder_cones(x, y, cones)))
    if 'strength' in out:
        s = out['strength']
        fields['Sc'] = _f32(np.where(np.isfinite(s), np.maximum(s, math.tan(math.radians(33.0))),
                                     math.tan(math.radians(40.0))))
    fields[key] = _f32(out['floor'])
    fields['caldera_floor'] = _f32(out['floor'])
    fields['caldera_rim_m'] = np.full(fields['h'].shape, p['rim_height_m'], np.float32)
    _pull_band(fields, ctx)
    return fields


# ---------------------------------------------------------------------- the surroundings (design 4.7, 5)

SETTING_DEFAULTS = dict(centre=(0.0, 0.0), basin_m=12000.0, ramp_m=6000.0, cover=0.6, patch_m=9000.0,
                        texture=0.35, U_m_per_yr=3e-3, start_m=600.0, start_roughness=0.4, keep_m=None,
                        far_m=None, tilt_azimuth_deg=0.0, tilt=0.0, plain=0.0)


def setting_shape(level, params, seed, dev=None):
    """The uplift shape of a volcano's surroundings, about 0..1 at the level's cells: none within basin_m of the
    vent, rising over ramp_m to ranges of hills and mountains; `cover` of the ring is mountains, in patches (world
    fbm at patch_m: some sectors open into plains and valleys, as round Fuji), with texture (fbm at patch_m / 3,
    relative); `plain` lifts the whole window that much (a raised plateau: a cinder field or a crater's ground);
    tilt raises the side toward tilt_azimuth_deg by tilt x the shape's range across 20 km (a regional slope)."""
    p = dict(SETTING_DEFAULTS, **(params or {}))
    x, y = level.xy()
    r, _az = polar(x, y, p['centre'])
    ring = smoothstep(float(p['basin_m']), float(p['basin_m']) + float(p['ramp_m']), r)
    cover = float(p['cover'])
    out = ring
    if cover < 0.999:
        from statistics import NormalDist
        t = NormalDist().inv_cdf(min(max(1.0 - cover, 1e-3), 1.0 - 1e-3))
        n = _unit_fbm(level, float(p['patch_m']), int(seed) + 501, dev)
        out = out * smoothstep(t - 0.45, t + 0.45, n)
    tex = float(p['texture'])
    if tex > 0.0:
        out = out * np.clip(1.0 + tex * _unit_fbm(level, float(p['patch_m']) / 3.0, int(seed) + 503, dev), 0.0, None)
    out = out + float(p['plain'])
    if p['tilt']:
        ex, ey = compass(float(p['tilt_azimuth_deg']))
        d = ((x - p['centre'][0]) * ex + (y - p['centre'][1]) * ey) / 20000.0
        out = out * np.clip(1.0 + float(p['tilt']) * d, 0.0, None)
    return np.clip(out, 0.0, None)


def op_volcano_setting(fields, level, params, seed, ctx=None):
    """Stage op 'volcano_setting': the ground a volcano grows on, for a fluvial stage to carve before the cone is
    stamped (design 5: 'low fluvial surroundings'). params: SETTING_DEFAULTS (setting_shape's, and U_m_per_yr,
    start_m, start_roughness, keep_m / far_m). On the coarsest level (every pass) U = U_m_per_yr x the shape (the
    fluvial stage grows the ranges; its relief controller scales them), and on the fresh pass h = bed = the shape
    scaled to start_m, roughened (a flat start makes corduroy for millions of years). Every level gets
    'volcano_far', the `where` of the surroundings' fluvial stage: 1 on the coarsest level (the cone is stamped
    after that stage there), and on finer levels 0 within keep_m of the vent rising to 1 at far_m (default: the
    basin and the end of its ramp), so a finer level's surroundings stage never erodes the cone it inherited."""
    p = dict(SETTING_DEFAULTS, **(params or {}))
    dev = _device(ctx)
    grow = ctx is None or getattr(ctx, 'role', 'grow') == 'grow'
    shape = setting_shape(level, p, seed, dev)
    if grow:
        fields['U'] = _f32(float(p['U_m_per_yr']) * shape)
    if ctx is None or getattr(ctx, 'fresh', False):
        rough = float(p['start_roughness'])
        n = 0.5 + 1.5 * _world_field({'kind': 'fbm', 'wavelength_m': 0.3 * float(p['patch_m']), 'octaves': 5},
                                     level, int(seed) + 31, dev)
        pk = max(float(np.max(shape)), 1e-9)
        h0 = float(p['start_m']) * shape / pk * ((1.0 - rough) + rough * n)
        fields['h'] = _f32(h0)
        fields['bed'] = _f32(h0)
    if grow:
        fields['volcano_far'] = np.ones(fields['h'].shape, np.float32)
    else:
        x, y = level.xy()
        r, _ = polar(x, y, p['centre'])
        keep = float(p['keep_m'] if p['keep_m'] is not None else p['basin_m'])
        far = float(p['far_m'] if p['far_m'] is not None else p['basin_m'] + p['ramp_m'])
        fields['volcano_far'] = _f32(smoothstep(keep, max(far, keep + 1.0), r))
    return fields


# ---------------------------------------------------------------------- aging: the fluvial backbone for an age

AGE_DEFAULTS = dict(age_yr=1.0e5, K=2.0e-6, m=0.5, n=1.0, threshold_deg=38.0, threshold_noise=0.15,
                    threshold_scale_m=400.0, deposition=1.0, roughness=0.6, roughness_scales_m=(2000.0, 300.0, 50.0),
                    valley_spacing_m=300.0, gullies=False, steps=None, max_steps=3000, min_steps=200,
                    dt_target_yr=None, lock=True, fill_pits=True, young_radius_m=0.0, young_factor=1.0,
                    centre=(0.0, 0.0), strength_from_field=False, threshold_gain=0.0, breakup=0.0, k_breakup=0.0,
                    breakup_scales_m=(60.0, 20.0, 7.0), seed_texture_m=0.0, seed_texture_scale_m=150.0)


def op_volcano_age(fields, level, params, seed, ctx=None):
    """Stage op 'volcano_age': the fluvial backbone (solvers/fluvial.py: stream power, creep, threshold failure,
    sediment deposition) run on a constructional shape for its age with no uplift (design 4.7 'growth and erosion',
    4.8 'aging'): radial gullies on a young cone (10-100 kyr), deep radial valleys with planezes between them on an
    old one (0.5-2 Myr), gullied crater walls with the floor filled.

    On the first level the stage runs on (not a pre-pass) the run is time-faithful: age_yr in steps of at most
    dt_target_yr (default: the age in max_steps .. min_steps steps), from the drainage area routed to convergence on
    the start surface (a short run's one-iteration-per-step routing would otherwise leave the lower flanks dry), no
    lock. Finer levels refine what they inherited: the same age at the main level's step, under the fluvial stage's
    low-pass lock (lock True), so they add their own finer gullies without eroding the landform again.

    params (AGE_DEFAULTS): K (erodibility: young, permeable lava erodes slowly; 2e-6 by default), m, n,
    threshold_deg (+ noise), deposition (G: 1 makes the apron and fans where the slope drops), roughness (K noise at
    roughness_scales_m: where gullies start), valley_spacing_m (D = K (spacing / 26)^2), fill_pits (False keeps a
    crater or caldera a closed basin: its floor fills with what the walls lose), young_radius_m / young_factor (K x
    young_factor at the vent rising to 1 at young_radius_m from `centre`: a summit renewed by recent eruptions is
    the least eroded), strength_from_field (the threshold from the level's Sc field: walls built with their own
    strength, a caldera's or a crater's cliffs), seed_texture_m (metres of world noise at seed_texture_scale_m added
    before the run, where flow first concentrates)."""
    if _prepass(ctx):
        return fields
    from . import fluvial as FL
    from . import hydro as HY
    p = dict(AGE_DEFAULTS, **(params or {}))
    ctx = ctx or FL.standalone_context(fields, level)
    dev = _device(ctx)
    key = 'aged_' + _stamp_key('volcano_age', dict(params, seed=seed))[len('stamp_'):]
    first = key not in fields
    cell = float(level.cell)
    main = ctx.main
    main_cell = float(main.cell) if main is not None else cell
    grow = ctx.role == 'grow'
    age = float(p['age_yr'])
    if p['steps']:
        steps = int(p['steps'])
    else:
        dt_t = p['dt_target_yr']
        steps = int(round(age / float(dt_t))) if dt_t else int(p['max_steps'])
        steps = int(np.clip(steps, int(p['min_steps']), int(p['max_steps'])))
    dt = age / max(steps, 1)
    if not first:
        # refine at the first level's step (a finer level adds detail as deep in cells, not more years per cell)
        dt = float(fields[key].flat[0]) if key in fields else dt
        steps = max(int(round(age / dt)), 1)
    dt_ref = dt * FL.CELL_REF_M / (cell if grow else max(cell, main_cell))
    if first and float(p['seed_texture_m']) > 0:
        tx = float(p['seed_texture_m']) * _unit_fbm(level, float(p['seed_texture_scale_m']), int(seed) + 707, dev, 3)
        fields['h'] = _f32(np.asarray(fields['h'], np.float64) + tx)
        if 'bed' in fields:
            fields['bed'] = _f32(np.asarray(fields['bed'], np.float64) + tx)
    if first:
        surf = HY.routing_surface(HY.fill_depressions(np.asarray(fields['h'], np.float64),
                                                      sea_level=ctx.sea_level)[0], sea_level=ctx.sea_level)
        A_in = ctx.pins['A_in'] if ctx.pins is not None else None
        fields['A'] = HY.route_to_convergence(dev, surf, cell, A0=fields.get('A'), A_in=A_in)[0]
    saved = {k: fields[k] for k in ('U', 'K_factor', 'Sc_factor') if k in fields}
    fields['U'] = np.zeros(fields['h'].shape, np.float32)
    kf = np.ones(fields['h'].shape)
    if float(p['young_radius_m']) > 0 and float(p['young_factor']) != 1.0:
        x, y = level.xy()
        r, _ = polar(x, y, p['centre'])
        yf = float(p['young_factor'])
        kf = yf + (1.0 - yf) * smoothstep(0.0, float(p['young_radius_m']), r)
    fields['K_factor'] = _f32(kf)
    t0 = math.tan(math.radians(float(p['threshold_deg'])))
    if p['strength_from_field'] and 'Sc' in fields:
        fields['Sc_factor'] = _f32(np.asarray(fields['Sc'], np.float64) / t0)
    elif 'Sc_factor' in fields:
        del fields['Sc_factor']
    fp = {k: p[k] for k in ('K', 'm', 'n', 'threshold_deg', 'threshold_noise', 'threshold_scale_m', 'deposition',
                            'roughness', 'roughness_scales_m', 'valley_spacing_m', 'gullies', 'threshold_gain',
                            'breakup', 'k_breakup', 'breakup_scales_m')}
    fp.update(steps=steps, min_steps=1, max_steps=max(steps, 1), dt_ref_yr=dt_ref, relief_m=None,
              lock=bool(p['lock']) and not first, fill_pits=bool(p['fill_pits']), mode='evolve',
              Sc_from_fields=False)
    FL.op_fluvial(fields, level, fp, seed, ctx=ctx)
    for k in ('U', 'K_factor', 'Sc_factor'):
        if k in saved:
            fields[k] = saved[k]
        elif k in fields:
            del fields[k]
    fields[key] = np.full(fields['h'].shape, dt, np.float32)        # the step the first level used (and a marker)
    return fields


# ---------------------------------------------------------------------- lava flows (DOWNFLOW, design 4.7)

LAVA_DEFAULTS = dict(walkers=400, length_m=6000.0, thickness_m=12.0, dh_m=None, age=0.0, levee=0.3, rough=0.12,
                     p_edge=0.04)


def lava_vents(params, seed):
    """The vents of a 'lava_flows' stage, each dict(at, and LAVA_DEFAULTS overrides): params vents=[...] (explicit),
    rift=dict(centre, azimuth_deg, count, distance_m (lo, hi), spread_m, length_m (lo, hi), thickness_m (lo, hi),
    age (lo, hi)) (flank vents along a volcano's rift, both ways), breaches=dict(the cinder_cones stage's cones /
    field / kappa; length_m, thickness_m, age) (a flow from the foot of every breached cone, out of its breach), and
    scatter=dict(window (x0, y0, size), count, length_m, thickness_m, age) (old flows from vents spread over a
    plateau)."""
    out = [dict(v) for v in params.get('vents', ())]
    rng = _rng(seed, 81)
    if params.get('rift'):
        rp = dict(params['rift'])
        c0 = rp.get('centre', (0.0, 0.0))
        ex, ey = compass(float(rp.get('azimuth_deg', 0.0)))
        for _ in range(int(rp.get('count', 3))):
            side = 1.0 if rng.random() < 0.5 else -1.0
            d = rng.uniform(*rp.get('distance_m', (3000.0, 8000.0)))
            lat = rng.normal(0.0, float(rp.get('spread_m', 1500.0)))
            out.append(dict(at=(c0[0] + side * d * ex - lat * ey, c0[1] + side * d * ey + lat * ex),
                            length_m=rng.uniform(*rp.get('length_m', (5000.0, 10000.0))),
                            thickness_m=rng.uniform(*rp.get('thickness_m', (10.0, 25.0))),
                            age=rng.uniform(*rp.get('age', (0.0, 0.6)))))
    if params.get('breaches'):
        bp = dict(params['breaches'])
        for c in cones_of(bp, seed):
            if c.get('breach_azimuth_deg') is None:
                continue
            ex, ey = compass(float(c['breach_azimuth_deg']))
            rb = 0.5 * float(c['width_m'])
            youth = 1.0 - min(float(c.get('age_yr', 0.0)) / float(bp.get('age_span_yr', 5e5)), 1.0)
            out.append(dict(at=(c['at'][0] + 0.92 * rb * ex, c['at'][1] + 0.92 * rb * ey),
                            length_m=float(bp.get('length_m', 4000.0)) * (0.5 + 0.5 * youth) * rng.uniform(0.7, 1.3),
                            thickness_m=float(bp.get('thickness_m', 12.0)) * rng.uniform(0.7, 1.2),
                            age=1.0 - youth))
    if params.get('scatter'):
        sp = dict(params['scatter'])
        x0, y0, size = (float(v) for v in sp['window'])
        for _ in range(int(sp.get('count', 6))):
            out.append(dict(at=(x0 + size * rng.uniform(0.1, 0.9), y0 + size * rng.uniform(0.1, 0.9)),
                            length_m=rng.uniform(*sp.get('length_m', (2000.0, 6000.0))),
                            thickness_m=rng.uniform(*sp.get('thickness_m', (5.0, 15.0))),
                            age=rng.uniform(*sp.get('age', (0.4, 1.0)))))
    return out


def op_lava_flows(fields, level, params, seed, ctx=None):
    """Stage op 'lava_flows' (design 4.7): flows from the vents (lava_vents) by DOWNFLOW walkers on this level's
    surface, each the lava_surface of its walkers' passage, the later ones over the earlier ones; the flows go into
    h and bed (lava is rock) and their footprint, dulled with age, into 'lava' (0..1, the material's lava rock).
    Runs on the first level it selects (pick one where the flows are at least 4 cells wide); finer levels inherit the
    flows with their fields. params: the vent sources (lava_vents) and LAVA_DEFAULTS (walkers 400, dh_m: the
    perturbation, default the flow's thickness: the larger, the wider the flow spreads on gentle ground)."""
    if _prepass(ctx):
        return fields
    key = _stamp_key('lava_flows', dict(params, seed=seed))
    if key in fields:
        return fields
    p = dict(LAVA_DEFAULTS, **{k: v for k, v in (params or {}).items() if k in LAVA_DEFAULTS})
    vents = lava_vents(params or {}, seed)
    h = np.asarray(fields['h'], np.float64)
    x, y = level.xy()
    total = np.zeros_like(h)
    foot = np.asarray(fields['lava'], np.float64) if 'lava' in fields else np.zeros_like(h)
    for k, v in enumerate(vents):
        v = dict(p, **v)
        fi, fj = level.index_of(v['at'][0], v['at'][1])
        if not (2 <= fi < level.n - 2 and 2 <= fj < level.n - 2):
            continue
        dh = float(v['dh_m']) if v.get('dh_m') is not None else float(v['thickness_m'])
        P = lava_walkers(h + total, level.cell, (fi, fj), int(v['walkers']), float(v['length_m']), dh, seed, k)
        T, F = lava_surface(P, level.cell, float(v['thickness_m']), x, y, float(v['p_edge']), None,
                            float(v['levee']), float(v['rough']), float(v['age']), int(seed) + 13 * k)
        total += T
        foot = np.maximum(foot, F * (1.0 - 0.6 * float(v['age'])))
    fields['h'] = _f32(h + total)
    if 'bed' in fields:
        fields['bed'] = _f32(np.asarray(fields['bed'], np.float64) + total)
    fields['lava'] = _f32(foot)
    fields[key] = _f32(total)
    _pull_band(fields, ctx)
    return fields


# ---------------------------------------------------------------------- a caldera's (or crater's) lake

def op_caldera_lake(fields, level, params, seed, ctx=None):
    """Stage op 'caldera_lake': a lake at its own level in a caldera (or a crater), not at its spill: a closed basin's
    lake stands where inflow and evaporation and seepage balance (Crater Lake 185 m under its lowest rim notch).
    params: level_m (the field frame), or below_rim_m under the mean rim the collapse recorded ('caldera_rim_m');
    centre. The water is the connected region under the lake level that holds the centre: water = level - h there.
    Every other closed depression on the level is filled with sediment to its spill (they are the solvers' pits): a
    caldera recipe sets defaults['lakes'] = False, so the runner's end stage does not fill the caldera to its rim."""
    if _prepass(ctx):
        return fields
    from . import hydro as HY
    from ..core.metrics import label
    h = np.asarray(fields['h'], np.float64)
    if params.get('level_m') is not None:
        L = float(params['level_m'])
    else:
        if 'caldera_rim_m' not in fields:
            raise ValueError("caldera_lake: no 'caldera_rim_m' (run caldera_collapse first) and no level_m")
        L = float(np.mean(fields['caldera_rim_m'])) - float(params.get('below_rim_m', 300.0))
    c = params.get('centre', (0.0, 0.0))
    fi, fj = level.index_of(c[0], c[1])
    lab, n = label(h < L)
    water = np.zeros_like(h)
    if n:
        ci = int(np.clip(round(fi), 0, level.n - 1))
        cj = int(np.clip(round(fj), 0, level.n - 1))
        k = lab[cj, ci]
        if k == 0 and 'caldera_floor' in fields:            # an island at the centre: the largest region on the floor
            fl = (np.asarray(fields['caldera_floor']) > 0.5) & (lab > 0)
            if fl.any():
                k = np.bincount(lab[fl]).argmax()
        if k > 0:
            water = np.where(lab == k, L - h, 0.0)
    surf = h + water
    filled, _ = HY.fill_depressions(surf, sea_level=getattr(ctx, 'sea_level', None) if ctx is not None else None)
    pit = np.where(water > 0, 0.0, np.maximum(filled - surf, 0.0))
    if pit.any():
        fields['h'] = _f32(h + pit)
        fields['deposit'] = _f32((np.asarray(fields['deposit'], np.float64) if 'deposit' in fields else 0.0) + pit)
    fields['water'] = _f32(water)
    _pull_band(fields, ctx)
    return fields


for _op in (op_stratovolcano, op_cinder_cones, op_caldera_collapse, op_volcano_setting, op_volcano_age,
            op_lava_flows, op_caldera_lake):
    _op.evolves = True       # run.py calls them on every pass of the coarsest level; the stamps skip the pre-passes

OPS = {
    'stratovolcano': op_stratovolcano,
    'cinder_cones': op_cinder_cones,
    'caldera_collapse': op_caldera_collapse,
    'volcano_setting': op_volcano_setting,
    'volcano_age': op_volcano_age,
    'lava_flows': op_lava_flows,
    'caldera_lake': op_caldera_lake,
}
