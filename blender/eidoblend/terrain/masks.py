"""Terrain masks (DESIGN.md section 6): the arrays the material, the rock scatter, the flora and the scene script read
off a finished terrain, one set per level.

    from eidoblend.terrain import masks as M
    stack = M.compute_stack(level_fields, levels)    # every level: a Masks dict {name: float32 (ny, nx)}, each level
                                                     # padded from its parents, normalised by the main level, its
                                                     # border band pinned to its parent's masks
    m = M.compute(fields, cell, x0, y0)              # one level on its own (a DEM, a test)
    M.MASKS['slope']                                 # each mask's unit and meaning; M.attribute_name('slope')

Units are the design's (section 2.1): metres, degrees, m^2. Every mask is defined in them, never in cells or tile
fractions, so a mask means the same on every level and at any resolution (the tests hold each to that on fields
resampled 2 x). Two kinds are level-of-detail on purpose and say so: the signed curvatures and convex / concave
without a scale suffix are measured at 2 x the level's cell (each level's own finest bends), and `channels`' default
threshold area shrinks with the cell (rivers on the main level, rills on the hero levels). In a stack every child's
outer 16 cells are pinned to its parent's masks (pin_band, as the runner pins its heights), so even those meet the
ring next to them exactly.

Frames: arrays are [row j, column i], row 0 the south edge, cell centres at x0 + (i + 0.5) cell, y0 + (j + 0.5) cell.

Inputs: `fields` is a mapping of one level's float arrays (core's Fields, or a plain dict); only `h` is required.
    h        surface height, metres above base; altitude = h + base_elevation_m (the snowline and treeline use it)
    A        converged drainage area, m^2 (the route pass to convergence): flow, channels, wetness, vegetation
    wear, deposit, talus, sand, lava, water   the processes' accumulated outputs, passed through (metres; lava as its
             solver writes it). A mask whose input is absent is skipped and Masks.skipped says why; the material's
             Attribute node reads a missing attribute as 0, which is what an absent process means.
    zs       stratigraphic height, metres (or params.strata, from which it is computed with the design's formula)

How each mask is made, so its numbers can be trusted:
- slope and aspect: central differences of the final height (np.gradient's arithmetic). At a level's edge the padding
  supplies the outside neighbour: the parent's height in a stack; on a level alone a linear extrapolation, which
  reproduces np.gradient's one-sided edge exactly.
- curvature: the height is Gaussian-smoothed with sigma = scale (FFT on the window padded by 4 sigma of its parents'
  terrain, so no wrap-around reaches it; a wide sigma runs on the window box-averaged to sigma / 3 cells, so its cost
  does not grow with the scale), then profile = -d2h/ds2 down the slope and plan = -d2h/dn2 along the contour, in 1/m
  (positive = convex). Their sum is minus the Laplacian; on ground under flat_slope_deg both take half of it, so the
  split never flickers where the slope has no direction. convex / concave = smoothstep(bend) of
  (profile + plan) x scale: a dimensionless change of slope over the scale, the same number for a feature of the same
  shape at any size (a V-valley with 30-degree sides gives about 0.46 at its axis whatever the scale).
- peaks: Ekigar's "high AND convex" in metres. At each of peaks_scales_m (default 150 m: crests, ridgelines,
  summits) a cell must stand above the mean height within sigma = scale by enough local standard deviations (Wilson &
  Gallant's DEV) and by enough metres (5-20 % of the scale, so a 5 m knob on a bench is no peak); the strongest scale
  wins, times a band of the main tile's normalised height.
- flow and wetness use the specific catchment area a = A / cell (m^2 per metre of contour). On the main level `flow`
  is exactly log10 of the drainage area normalised over the main tile; on other levels a = A / cell keeps hillslopes
  continuous across ring borders (a hillslope cell's A is its upslope length times its own width, so A alone halves
  with every finer level). wetness is the topographic wetness index ln(a / tan(slope)) (Beven & Kirkby 1979),
  normalised by the main tile's 5th and 95th percentiles; water is wet.
- occlusion: the sky-view factor 1 - mean(sin horizon angle) over 16 azimuths within occlusion_radius_m (Zaksek et
  al. 2011; Ekigar's horizon_occlusion with its radius in metres). The march reads the padded window, so a level sees
  its parents' terrain beyond its edge; beyond the outermost level the sky is open. The first 6 cells of every
  azimuth march at full resolution (a crevice's own walls), the rest over the window box-averaged by 2 or more (the
  cost stays bounded whatever the radius); against a full-resolution march the 99th-percentile error is 0.01-0.025,
  and a plane and a V-valley floor land within 0.004 of their analytic sky views.
- rock, rock_toe, snow, vegetation: smoothstep rules on the masks above, every threshold in metres or degrees
  (MaskParams). rock_toe is the ground below exposed rock where fallen rock gathers (the dressing scatters boulders
  on it with talus): the rockfall shadow-angle test (Evans & Hungr 1993), the foot of a rock face (rock_base) within
  rock_toe_reach_m standing above the cell at 25-33 degrees or steeper, so an apron reaches farther below a taller
  talus slope; it is the geometric stand-in where no talus process ran (a real DEM). Thick sand takes the runoff in,
  so channels fade out on it. vegetation reads no level-of-detail mask, so it means the same on every level.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass

import numpy as np

ATTRIBUTE_PREFIX = 'eido_'
SCALED = ('curv_profile', 'curv_plan', 'convex', 'concave')        # the masks that take a scale suffix: convex_20m
PASS_THROUGH = ('wear', 'deposit', 'talus', 'sand', 'lava')

# name -> (unit, what it is). The material reads every one as the FLOAT point attribute eido_<name>.
MASKS = {
    'height': ('m', 'height above base (the h field); altitude = height + base_elevation_m'),
    'height_norm': ('0-1', 'height normalised over the main tile (0 its lowest cell, 1 its highest), clipped'),
    'slope': ('deg', 'slope, central differences on the final surface, never clipped'),
    'aspect': ('deg', 'compass bearing the slope faces (0 north-facing, 90 east); 0 on flats. Interpolating it across '
                      'a triangle tears at north: materials read northness / eastness'),
    'northness': ('-1..1', 'cos(aspect), faded to 0 on ground under 3 degrees: north-facing +1'),
    'eastness': ('-1..1', 'sin(aspect), faded to 0 on ground under 3 degrees: east-facing +1'),
    'curv_profile': ('1/m', 'profile curvature -d2h/ds2 down the slope at 2 x the level cell (+ convex: shoulders, cliff '
                            'tops; - concave: foot slopes, cliff feet); curv_profile_<s>m at s metres'),
    'curv_plan': ('1/m', 'plan curvature -d2h/dn2 along the contour at 2 x the level cell (+ ridges and spurs, - valleys '
                         'and hollows); curv_plan_<s>m at s metres'),
    'convex': ('0-1', 'convex ground at 2 x the level cell: smoothstep of (profile + plan) x scale; convex_<s>m at s m'),
    'concave': ('0-1', 'concave ground at 2 x the level cell; concave_<s>m at s metres'),
    'peaks': ('0-1', 'high and convex: summits and ridgelines standing above their surroundings within 150 m by '
                     'standard deviations and metres, in the upper height band of the main tile'),
    'flow': ('0-1', 'log10 of the drainage area per metre of contour (A / cell), normalised over the main tile: on '
                    'the main level, log10 drainage area normalised'),
    'channels': ('0-1', 'drainage area above the level threshold (1 km^2 at cells of 7.6 m and coarser, down to '
                        '1,000 m^2 at 0.5 m: rills), fading in from a fifth of it'),
    'wetness': ('0-1', 'topographic wetness ln(a / tan slope) normalised over the main tile; 1 on water'),
    'wear': ('m', 'eroded depth (fresh rock)'),
    'deposit': ('m', 'sediment thickness'),
    'talus': ('m', 'talus thickness'),
    'sand': ('m', 'sand thickness'),
    'lava': ('as written', 'lava-flow footprint, with age, as the volcanic solver writes it'),
    'water': ('m', 'lake or sea depth'),
    'rock': ('0-1', 'exposed rock: slope above the rock angle, or deep wear with a thin cover; not under loose cover '
                    'or water'),
    'rock_toe': ('0-1', 'the ground below exposed rock where fallen rock gathers: the foot of a rock face within '
                        '300 m stands above it at 25-33 degrees or steeper (the rockfall shadow angle); concave feet '
                        'highest'),
    'snow': ('0-1', 'altitude above the snowline (north faces and hollows hold it lower, ridges shed it), on slopes '
                    'under 45 degrees'),
    'strata': ('m', 'stratigraphic height zs: the material reads its rock column at it'),
    'occlusion': ('0-1', 'sky-view factor within occlusion_radius_m: 1 open sky, lower in valleys and gorges'),
    'vegetation': ('0-1', 'suitability for plants from moisture, slope, altitude band, aspect, light, and bare '
                          'ground (rock, snow, water, sand, scree): a density for the flora family'),
}
DEFAULT_NAMES = ('height', 'height_norm', 'slope', 'aspect', 'northness', 'eastness',
                 'curv_profile', 'curv_plan', 'convex', 'concave',
                 'curv_profile_20m', 'curv_plan_20m', 'convex_20m', 'concave_20m',
                 'peaks', 'flow', 'channels', 'wetness', 'wear', 'deposit', 'talus', 'sand', 'lava', 'water',
                 'rock', 'rock_toe', 'snow', 'strata', 'occlusion', 'vegetation')


def attribute_name(name):
    """The mesh point attribute of a mask: eido_<name>."""
    return ATTRIBUTE_PREFIX + name


@dataclass
class MaskParams:
    """Every threshold of the masks, in metres, degrees and m^2. Pairs are smoothstep edges (from, to)."""
    base_elevation_m: float = 0.0           # altitude = h + base_elevation_m
    sea_level: float | None = None          # in h's frame: cells at or below it are sea when there is no water field
    wrap: tuple = (False, False)            # periodic level along x, y (dune tiles)
    # curvature
    curvature_scales_m: tuple = (None, 20.0)     # the default curvature masks: None = 2 x the level cell
    bend: tuple = (0.03, 0.30)              # convex / concave over (profile + plan) x scale
    flat_slope_deg: float = 1.0             # under it profile and plan curvature share the Laplacian
    # peaks
    peaks_scales_m: tuple = (150.0,)        # crests, ridgelines and summits. A volcano recipe may add 600 m for a
                                            # whole summit cone; at 600 m a plateau beside a canyon stands high and
                                            # convex too (Toroweap's Esplanade lit up 1 km in from the rim)
    peaks_dev: tuple = (0.3, 1.3)           # the deviation from the local mean, in local standard deviations
    peaks_rise: tuple = (0.05, 0.2)         # and the height above that mean, as a fraction of the scale (metres:
                                            # 7.5-30 m at 150 m, 30-120 m at 600 m): a knob on a bench is no peak
    peaks_height_norm: tuple = (0.2, 0.5)   # and the main tile's normalised height
    peaks_std_floor_m: float = 2.0
    # drainage
    channel_area_m2: float | None = None    # None: channel_area_for_cell(level cell)
    # occlusion
    occlusion_radius_m: float = 500.0
    occlusion_directions: int = 16
    occlusion_step_ratio: float = 1.4       # march distances: radius, radius / 1.4, ... down to one cell
    # rock and its foot
    rock_deg: tuple = (34.0, 46.0)
    rock_wear_m: tuple = (2.0, 20.0)
    cover_m: tuple = (0.1, 1.0)             # deposit + talus + sand that hides the rock
    rock_toe_reach_m: float = 300.0         # how far from exposed rock its fall can reach
    rock_toe_shadow_deg: tuple = (25.0, 33.0)   # the rock above at this angle or steeper: inside the rockfall shadow
    rock_toe_directions: int = 12
    # snow
    snowline_m: float | None = None         # altitude; None: no snow mask
    snow_band_m: float = 150.0              # half-width of the snowline's fade
    snow_aspect_m: float = 200.0            # north faces hold snow this much lower (southern hemisphere: negative)
    snow_concave_m: float = 150.0           # hollows hold it this much lower, convex ridges this much higher
    snow_slope_deg: tuple = (40.0, 50.0)
    # vegetation
    treeline_m: float | None = None         # altitude; None: no altitude limit
    treeline_band_m: float = 120.0
    alpine_density: float = 0.3             # above the treeline: alpine grass and dwarf shrubs, not bare ground
    veg_slope_deg: tuple = (32.0, 48.0)
    sand_swallows_m: tuple = (0.5, 3.0)     # sand this thick takes the runoff in: no channels on it
    # strata: dict(dip_deg, azimuth_deg (counter-clockwise from +x, the design's x cos az + y sin az),
    # warp=callable(x, y) -> metres or None)
    strata: dict | None = None

    def to_dict(self):
        d = asdict(self)
        if d.get('strata') and callable(d['strata'].get('warp')):
            d['strata'] = dict(d['strata'], warp='<callable>')
        return d


@dataclass
class Norms:
    """The normalisations the main tile sets for every level (so a normalised mask means the same everywhere)."""
    cell_m: float                   # the main level's cell
    h_lo: float
    h_hi: float
    flow_lo: float = 0.0            # log10 metres of specific catchment area: a divide cell of the main level
    flow_hi: float = 1.0            # the largest on the main tile
    twi_lo: float = 0.0
    twi_hi: float = 1.0


class Masks(dict):
    """{name: float32 array (ny, nx)} of one level, plus where it is and what was left out."""

    def __init__(self, cell, x0, y0, shape):
        super().__init__()
        self.cell, self.x0, self.y0, self.shape = float(cell), float(x0), float(y0), tuple(shape)
        self.skipped = {}           # name -> why
        self.seconds = {}           # stage -> seconds (geometry, curvature, occlusion, drainage, ...)
        self.norms = None
        self.params = None

    def attributes(self):
        """(attribute name, array) pairs for the mesh: eido_<name>."""
        return [(attribute_name(k), v) for k, v in self.items()]


# ---------------------------------------------------------------- small helpers
F32 = np.float32


def smoothstep(e0, e1, x):
    """The GLSL smoothstep in float32 (e0 > e1 runs it downhill); two temporaries, the rest in place."""
    t = np.subtract(np.asarray(x, F32), F32(e0))
    t *= F32(1.0 / (e1 - e0))
    np.clip(t, 0.0, 1.0, out=t)
    u = t * t
    t *= F32(-2.0)
    t += F32(3.0)
    t *= u
    return t


def channel_area_for_cell(cell):
    """The default channel threshold area of a level, m^2: 1,000 m^2 at 0.5 m cells (rills), growing as cell^2.5
    to 1 km^2 at 7.6 m cells and staying there (DESIGN.md section 6: 1 km^2 on the main level, 1,000 m^2 on the hero
    levels)."""
    return float(np.clip(1000.0 * (cell / 0.5) ** 2.5, 1000.0, 1.0e6))


def scale_suffix(scale_m):
    """'20m' for 20.0, '2p5m' for 2.5: the name suffix of a curvature scale."""
    s = f'{scale_m:g}'.replace('.', 'p')
    return f'{s}m'


_SCALED_RE = re.compile(r'^(curv_profile|curv_plan|convex|concave)(?:_(\d+(?:p\d+)?)m)?$')


def parse_name(name):
    """(base, scale_m or None) of a mask name: ('convex', 20.0) for convex_20m, ('slope', None) for slope."""
    m = _SCALED_RE.match(name)
    if m:
        return m.group(1), (float(m.group(2).replace('p', '.')) if m.group(2) else None)
    if name not in MASKS:
        near = _nearest(name, list(MASKS) + [f'{b}_20m' for b in SCALED])
        raise KeyError(f'unknown mask {name!r}; nearest: {", ".join(near)}')
    return name, None


def _nearest(name, options, k=3):
    def dist(a, b):
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]
    return sorted(options, key=lambda o: dist(name, o))[:k]


def _lv(level, key, default=None):
    if level is None:
        return default
    if isinstance(level, dict):
        return level.get(key, default)
    return getattr(level, key, default)


def _good_size(n):
    """The smallest m >= n whose prime factors are 2, 3 and 5 (a fast FFT length)."""
    m = n
    while True:
        k = m
        for p in (2, 3, 5):
            while k % p == 0:
                k //= p
        if k == 1:
            return m
        m += 1


def gaussian_blur(a, sigma_cells):
    """Gaussian blur (sigma in cells) by FFT in float32, treating `a` as periodic: the caller pads it (a margin of
    4 sigma keeps the wrap-around out of the cells it keeps). Subtract a mean first: float32 keeps 7 digits."""
    a = np.asarray(a, F32)
    if sigma_cells <= 0.0:
        return a.copy()
    ny, nx = a.shape
    py, px = _good_size(ny), _good_size(nx)
    if (py, px) != (ny, nx):          # extend to a fast length by edge hold (beyond the kept cells' reach)
        a = np.pad(a, ((0, py - ny), (0, px - nx)), mode='edge')
    fy = np.fft.fftfreq(py).astype(F32)[:, None]
    fx = np.fft.rfftfreq(px).astype(F32)[None, :]
    g = np.exp(F32(-2.0 * (math.pi * sigma_cells) ** 2) * (fx * fx + fy * fy))
    out = np.fft.irfft2(np.fft.rfft2(a) * g, s=(py, px))
    return np.asarray(out[:ny, :nx], F32)


# ---------------------------------------------------------------- sampling the stack
def _bilinear(a, fx, fy):
    ny, nx = a.shape
    x0 = np.clip(np.floor(fx).astype(np.int64), 0, nx - 2)
    y0 = np.clip(np.floor(fy).astype(np.int64), 0, ny - 2)
    tx, ty = fx - x0, fy - y0
    v00, v10 = a[y0, x0], a[y0, x0 + 1]
    v01, v11 = a[y0 + 1, x0], a[y0 + 1, x0 + 1]
    return (v00 * (1 - tx) + v10 * tx) * (1 - ty) + (v01 * (1 - tx) + v11 * tx) * ty


def _catmull_rom(a, fx, fy):
    ny, nx = a.shape
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = fx - ix, fy - iy

    def w(t):
        t2, t3 = t * t, t * t * t
        return ((-t3 + 2 * t2 - t) * 0.5, (3 * t3 - 5 * t2 + 2) * 0.5, (-3 * t3 + 4 * t2 + t) * 0.5, (t3 - t2) * 0.5)
    wx, wy = w(tx), w(ty)
    cols = [np.clip(ix + di - 1, 0, nx - 1) for di in range(4)]
    out = np.zeros(fx.shape, np.float64)
    for dj in range(4):
        r = np.clip(iy + dj - 1, 0, ny - 1)
        row = wx[0] * a[r, cols[0]] + wx[1] * a[r, cols[1]] + wx[2] * a[r, cols[2]] + wx[3] * a[r, cols[3]]
        out += wy[dj] * row
    return out


class StackSampler:
    """A field at world points from the finest of several levels that holds them: what lies beyond a level's window
    (its parents' terrain). Points outside every level read NaN. layers: [(x0, y0, cell, array)], any order."""

    def __init__(self, layers):
        self.layers = sorted(((float(x0), float(y0), float(c), np.asarray(a, np.float64)) for x0, y0, c, a in layers),
                             key=lambda l: l[2])

    def __call__(self, x, y, cubic=True):
        x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
        shape = x.shape
        x, y = x.ravel(), y.ravel()
        out = np.full(x.size, np.nan)
        idx = np.arange(x.size)
        f = _catmull_rom if cubic else _bilinear
        for x0, y0, c, a in self.layers:
            if not idx.size:
                break
            ny, nx = a.shape
            fx, fy = (x[idx] - x0) / c - 0.5, (y[idx] - y0) / c - 0.5
            ins = (fx >= 0) & (fx <= nx - 1) & (fy >= 0) & (fy <= ny - 1)
            if ins.any():
                out[idx[ins]] = f(a, fx[ins], fy[ins])
                idx = idx[~ins]
        return out.reshape(shape)


def _pad_axis(a, m, axis, mode):
    n = a.shape[axis]
    widths = [(0, 0), (0, 0)]
    widths[axis] = (m, m)
    if mode == 'wrap':
        return np.pad(a, widths, mode='wrap')
    if mode == 'nan':
        return np.pad(a, widths, mode='constant', constant_values=np.nan)
    if mode == 'edge':
        return np.pad(a, widths, mode='edge')
    k = min(m, n - 1)                                     # 'odd': 2 a[edge] - a[edge + k], then hold
    widths[axis] = (k, k)
    out = np.pad(a, widths, mode='reflect', reflect_type='odd')
    if k < m:
        widths[axis] = (m - k, m - k)
        out = np.pad(out, widths, mode='edge')
    return out


def pad_level(h, m, cell, x0=0.0, y0=0.0, wrap=(False, False), outside=None, fill='odd', cubic=True):
    """h padded by m cells on every side. Along a periodic axis it wraps. Elsewhere the margin holds the parents'
    terrain from outside(x, y, cubic=...) where it has some, and beyond that: 'odd', a linear extrapolation through
    the edge (2 h[edge] - h[edge + k]: it keeps the edge slope and adds no curvature, so np.gradient's one-sided edge
    falls out of a central difference); 'nan', unknown (the occlusion march's open sky); or 'edge', the edge held."""
    h = np.asarray(h, np.float64)
    if m <= 0:
        return h.copy()
    ny, nx = h.shape
    out = _pad_axis(h, m, 1, 'wrap' if wrap[0] else fill)
    out = _pad_axis(out, m, 0, 'wrap' if wrap[1] else fill)
    if outside is not None and not (wrap[0] and wrap[1]):
        ii = np.arange(-m, nx + m)
        jj = np.arange(-m, ny + m)
        ring = np.zeros(out.shape, bool)
        if not wrap[0]:
            ring[:, :m] = ring[:, m + nx:] = True
        if not wrap[1]:
            ring[:m, :] = ring[m + ny:, :] = True
        J, I = np.nonzero(ring)
        v = outside(x0 + (ii[I] + 0.5) * cell, y0 + (jj[J] + 0.5) * cell, cubic=cubic)
        ok = np.isfinite(v)
        out[J[ok], I[ok]] = v[ok]
    return out


def _decimation(sigma_cells, n, wrap_axis=False):
    """The box factor for a blur of sigma_cells: 1 up to 6 cells, then sigma / 3 (the blurred field keeps 3 or more
    samples per sigma); on a periodic axis a divisor of n."""
    if sigma_cells <= 6.0:
        return 1
    f = max(2, int(sigma_cells // 3))
    if wrap_axis:
        while n % f:
            f -= 1
    return max(f, 1)


def window_grid(h, f, mc, cell, x0=0.0, y0=0.0, wrap=(False, False), outside=None, fill='odd', cubic=True):
    """The level window box-averaged by f (f = 1: as is) and padded by mc of those cells with the parents' terrain
    (sampled at their centres) or `fill`. Coarse cell (J, I) covers the window's cells [(J - mc) f, (J - mc + 1) f)."""
    h = np.asarray(h, np.float64)
    if f > 1:
        ny, nx = h.shape
        Ny, Nx = -(-ny // f), -(-nx // f)
        if (Ny * f, Nx * f) != (ny, nx):
            h = np.pad(h, ((0, Ny * f - ny), (0, Nx * f - nx)), mode='edge')
        h = h.reshape(Ny, f, Nx, f).mean(axis=(1, 3))
    return pad_level(h, mc, cell * f, x0, y0, wrap, outside, fill, cubic)


def to_kept(b, f, mc, ny, nx):
    """A field on a window_grid (factor f, margin mc) at the level's own cells: a crop at f = 1, else bilinear."""
    if f == 1:
        return b[mc:mc + ny, mc:mc + nx]
    fy = (np.arange(ny) + 0.5) / f - 0.5 + mc
    fx = (np.arange(nx) + 0.5) / f - 0.5 + mc
    y0 = np.floor(fy).astype(np.int64)
    x0 = np.floor(fx).astype(np.int64)
    ty = (fy - y0).astype(F32)[:, None]
    tx = (fx - x0).astype(F32)[None, :]
    r = b[y0] * (1 - ty) + b[y0 + 1] * ty
    return r[:, x0] * (1 - tx) + r[:, x0 + 1] * tx


# ---------------------------------------------------------------- the geometry
def _slices(m, ny, nx, dj, di):
    return slice(m + dj, m + dj + ny), slice(m + di, m + di + nx)


def gradient(hp, m, ny, nx, cell):
    """(dh/dx, dh/dy) at the kept cells of a padded array (central differences; x east = columns, y north = rows)."""
    p = (hp[_slices(m, ny, nx, 0, 1)] - hp[_slices(m, ny, nx, 0, -1)]) * (0.5 / cell)
    q = (hp[_slices(m, ny, nx, 1, 0)] - hp[_slices(m, ny, nx, -1, 0)]) * (0.5 / cell)
    return p, q


def curvatures(hb, cell, flat_slope_deg=1.0):
    """(profile, plan) curvature in 1/m of a (smoothed) grid, the same shape (its outer ring copies the next one):
    -d2h/ds2 down the slope and -d2h/dn2 along the contour (positive = convex); under flat_slope_deg both take half
    the Laplacian."""
    hb = np.asarray(hb, F32)
    ny, nx = hb.shape[0] - 2, hb.shape[1] - 2
    s = lambda dj, di: hb[_slices(1, ny, nx, dj, di)]   # noqa: E731
    c = s(0, 0)
    e, w, n, so = s(0, 1), s(0, -1), s(1, 0), s(-1, 0)
    k1, k2 = F32(0.5 / cell), F32(1.0 / (cell * cell))
    p = (e - w) * k1
    q = (n - so) * k1
    r = (e - c - c + w) * k2
    t = (n - c - c + so) * k2
    sxy = (s(1, 1) - s(1, -1) - s(-1, 1) + s(-1, -1)) * F32(0.25 / (cell * cell))
    pp, qq, pq2 = p * p, q * q, F32(2.0) * p * q * sxy
    g2 = pp + qq
    inv = F32(1.0) / np.maximum(g2, F32(1e-30))
    hss = (pp * r + pq2 + qq * t) * inv
    hnn = (qq * r - pq2 + pp * t) * inv
    iso = F32(0.5) * (r + t)
    wgt = g2 / (g2 + F32(math.tan(math.radians(flat_slope_deg)) ** 2))
    prof = -(iso + wgt * (hss - iso))
    plan = -(iso + wgt * (hnn - iso))
    return np.pad(prof, 1, mode='edge'), np.pad(plan, 1, mode='edge')


def _march(hp, m, ny, nx, cell, dists, directions, observer=None):
    """Per azimuth, the largest tangent of the horizon at distances `dists` (metres; each a whole-cell shift of the
    padded array hp, margin m): a list of float32 (ny, nx). NaN in hp (no terrain) never raises the horizon. The
    observer is hp's own kept cells unless given (rock_toe marches over rock heights from the ground's). A shift
    whose direction lies more than half a sector off its azimuth is skipped: near the cell the rounding snaps an odd
    azimuth onto a neighbour's line, which read another azimuth's horizon (a plane's sky view came out 0.015 low, a
    V-valley floor's 0.013; with the rule 0.004 and 0.003)."""
    z = hp[m:m + ny, m:m + nx] if observer is None else observer
    tmp = np.empty((ny, nx), F32)
    out = []
    tol = math.pi / directions + 1e-9
    for k in range(directions):
        a = 2.0 * math.pi * k / directions
        ca, sa = math.cos(a), math.sin(a)
        best = np.zeros((ny, nx), F32)
        seen = set()
        for d in dists:
            di, dj = int(round(ca * d / cell)), int(round(sa * d / cell))
            if (di, dj) in seen or (di == 0 and dj == 0) or max(abs(di), abs(dj)) > m:
                continue
            if abs((math.atan2(dj, di) - a + math.pi) % (2.0 * math.pi) - math.pi) > tol:
                continue
            seen.add((di, dj))
            np.subtract(hp[m + dj:m + dj + ny, m + di:m + di + nx], z, out=tmp)
            tmp *= F32(1.0 / (math.hypot(di, dj) * cell))
            np.fmax(best, tmp, out=best)
        out.append(best)
    return out


def _fmax_blocks(best, fb, f):
    """best = max(best, fb upsampled by f nearest-neighbour), in place: coarse cell J covers fine rows [J f, J f + f)
    (a broadcast over a block view, no upsampled copy when the width divides by f)."""
    ny, nx = best.shape
    Ny, Nx = ny // f, nx // f
    if nx % f == 0:
        core = best[:Ny * f].reshape(Ny, f, Nx, f)
        np.fmax(core, fb[:Ny, None, :Nx, None], out=core)
    else:
        up = np.repeat(np.repeat(fb[:Ny, :], f, axis=0), f, axis=1)[:, :nx]
        np.fmax(best[:Ny * f], up, out=best[:Ny * f])
    if ny > Ny * f:
        up = np.repeat(fb[Ny:Ny + 1, :], f, axis=1)[:, :nx]
        np.fmax(best[Ny * f:], up, out=best[Ny * f:])


def sky_view(h, cell, radius_m, x0=0.0, y0=0.0, wrap=(False, False), outside=None, directions=16, ratio=1.4,
             near_cells=6):
    """The sky-view factor 1 - mean(sin horizon) of a level: a march along `directions` azimuths at distances
    radius, radius / ratio, ... down to one cell, over the window padded with its parents' terrain (open sky beyond
    every level). The first near_cells cells read the level itself (a crevice's own walls); the steps beyond read the
    window box-averaged by 2 (or by radius / 256 cells when that is more), observer included, and the far horizon is
    taken per 2 x 2 block. Against a full-resolution march on Lauterbrunnen and the Badlands: mean error 0.002, 99th
    percentile 0.016, in a quarter of the time."""
    h = np.asarray(h, np.float64)
    ny, nx = h.shape
    dists = []
    d = float(radius_m)
    while d >= cell * 0.999:
        dists.append(d)
        d /= ratio
    dists = sorted(dists)
    m_all = int(math.ceil(radius_m / cell)) + 1
    m_near = min(m_all, near_cells)
    hp = np.asarray(pad_level(h, m_near, cell, x0, y0, wrap, outside, fill='nan', cubic=False), F32)
    near = [d for d in dists if d <= m_near * cell]
    best = _march(hp, m_near, ny, nx, cell, near, directions)
    far = [d for d in dists if d > m_near * cell]
    if far:
        f = max(2, int(math.ceil(radius_m / cell / 256.0)))
        if wrap[0]:
            while nx % f:
                f -= 1
        if f > 1:
            mc = int(math.ceil(radius_m / (cell * f))) + 2
            g = np.asarray(window_grid(h, f, mc, cell, x0, y0, wrap, outside, fill='nan', cubic=False), F32)
            gy, gx = g.shape[0] - 2 * mc, g.shape[1] - 2 * mc
            fb = _march(g, mc, gy, gx, cell * f, far, directions)
            for k in range(directions):
                _fmax_blocks(best[k], fb[k], f)
        else:
            hp = np.asarray(pad_level(h, m_all, cell, x0, y0, wrap, outside, fill='nan', cubic=False), F32)
            for k, b in enumerate(_march(hp, m_all, ny, nx, cell, far, directions)):
                np.fmax(best[k], b, out=best[k])
    acc = np.zeros((ny, nx), F32)
    tmp = np.empty((ny, nx), F32)
    for b in best:                                        # sin(atan(b)) = b / sqrt(1 + b^2)
        np.multiply(b, b, out=tmp)
        tmp += F32(1.0)
        np.sqrt(tmp, out=tmp)
        np.divide(b, tmp, out=tmp)
        acc += tmp
    acc *= F32(-1.0 / directions)
    acc += F32(1.0)
    return acc


def rock_base(h, rock, wrap=(False, False)):
    """Exposed rock (rock > 0.5) with a lower neighbour that is not rock: the cliff's foot, where its talus starts."""
    h = np.asarray(h, np.float64)
    r = np.asarray(rock) > 0.5
    ny, nx = h.shape
    hp = _pad_axis(_pad_axis(h, 1, 1, 'wrap' if wrap[0] else 'edge'), 1, 0, 'wrap' if wrap[1] else 'edge')
    rp = _pad_axis(_pad_axis(r.astype(np.float64), 1, 1, 'wrap' if wrap[0] else 'edge'), 1, 0,
                   'wrap' if wrap[1] else 'edge') > 0.5
    base = np.zeros((ny, nx), bool)
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            if dj or di:
                sl = _slices(1, ny, nx, dj, di)
                base |= ~rp[sl] & (hp[sl] < h)
    return base & r


def rock_shadow(h, rock, cell, reach_m, wrap=(False, False), directions=12, ratio=1.4, near_cells=8):
    """The steepest tangent from each cell up to the foot of exposed rock (rock_base) within reach_m, over
    `directions` azimuths: the rockfall shadow-angle test (Evans & Hungr 1993: fallen rock stops near a line about
    28 degrees from the talus apex, the cliff's foot). The first near_cells cells march at full resolution, the rest
    over the window box-reduced by 2 (rock feet: the highest in the box; ground: the mean), its maximum over the
    azimuths upsampled bilinearly. Rock beyond the window is not seen."""
    h = np.asarray(h, np.float64)
    ny, nx = h.shape
    zr = np.where(rock_base(h, rock, wrap), h, np.nan)
    dists = []
    d = float(reach_m)
    while d >= cell * 0.999:
        dists.append(d)
        d /= ratio
    dists = sorted(dists)
    m_all = int(math.ceil(reach_m / cell)) + 1
    m_near = min(m_all, near_cells)
    mode = ('wrap' if wrap[0] else 'nan', 'wrap' if wrap[1] else 'nan')
    zp = _pad_axis(_pad_axis(zr, m_near, 1, mode[0]), m_near, 0, mode[1]).astype(F32)
    best = _march(zp, m_near, ny, nx, cell, [d for d in dists if d <= m_near * cell], directions,
                  observer=np.asarray(h, F32))
    out = best[0]
    for b in best[1:]:
        np.fmax(out, b, out=out)
    far = [d for d in dists if d > m_near * cell]
    if far:
        f = 1 if (wrap[0] and nx % 2) or (wrap[1] and ny % 2) else 2
        Ny, Nx = -(-ny // f), -(-nx // f)
        zpad = np.pad(zr, ((0, Ny * f - ny), (0, Nx * f - nx)), mode='constant', constant_values=np.nan)
        hpad = np.pad(h, ((0, Ny * f - ny), (0, Nx * f - nx)), mode='edge')
        zc = np.fmax.reduce(np.fmax.reduce(zpad.reshape(Ny, f, Nx, f), axis=3), axis=1)
        hc = hpad.reshape(Ny, f, Nx, f).mean(axis=(1, 3))
        mc = int(math.ceil(reach_m / (cell * f))) + 2
        zcp = _pad_axis(_pad_axis(zc, mc, 1, mode[0]), mc, 0, mode[1]).astype(F32)
        fb = _march(zcp, mc, Ny, Nx, cell * f, far, directions, observer=np.asarray(hc, F32))
        fm = fb[0]
        for b in fb[1:]:
            np.fmax(fm, b, out=fm)
        np.fmax(out, to_kept(np.pad(fm, mc, mode='edge'), f, mc, ny, nx), out=out)
    return out


# ---------------------------------------------------------------- normalisations
def _slope_tan(h, cell, wrap=(False, False)):
    hp = pad_level(h, 1, cell, wrap=wrap)
    ny, nx = np.shape(h)
    p, q = gradient(hp, 1, ny, nx, cell)
    return np.hypot(p, q)


def _water_depth(fields, params, h):
    w = fields.get('water') if hasattr(fields, 'get') else None
    if w is not None:
        return np.maximum(np.asarray(w, np.float64), 0.0)
    if params.sea_level is not None:
        return np.maximum(params.sea_level - h, 0.0)
    return None


def norms_from(fields, cell=None, params=None):
    """The Norms the main level sets: its height range, the range of log10 specific catchment area from a divide
    cell (a = cell) to its largest, and its wetness index's 5th-95th percentiles over land."""
    params = params or MaskParams()
    cell = float(cell if cell is not None else _lv(getattr(fields, 'level', None), 'cell'))
    h = np.asarray(fields['h'], np.float64)
    n = Norms(cell_m=cell, h_lo=float(h.min()), h_hi=float(h.max()))
    A = fields.get('A') if hasattr(fields, 'get') else None
    if A is not None:
        a = np.maximum(np.asarray(A, np.float64), cell * cell) / cell
        n.flow_lo = math.log10(cell)
        n.flow_hi = max(float(np.log10(a.max())), n.flow_lo + 1.0)
        twi = np.log(a / np.maximum(_slope_tan(h, cell, params.wrap), 1e-3))
        wd = _water_depth(fields, params, h)
        land = twi if wd is None else twi[wd <= 0.0]
        if land.size < 16:
            land = twi
        n.twi_lo, n.twi_hi = (float(v) for v in np.percentile(land, [5.0, 95.0]))
        n.twi_hi = max(n.twi_hi, n.twi_lo + 1.0)
    return n


# ---------------------------------------------------------------- one level
_NEEDS = {          # mask -> the masks it is built from (beyond h)
    'rock_toe': ('rock', 'concave_20m'),
    'snow': ('convex_20m', 'concave_20m'),
    'vegetation': ('wetness', 'rock', 'snow', 'occlusion', 'rock_toe'),
    'peaks': ('height_norm',),
}


def _expand(names):
    """The requested names with what they are built from added (dependencies that cannot be made are skipped
    later, quietly, unless asked for by name)."""
    order = []

    def add(nm):
        if nm in order:
            return
        base, _scale = parse_name(nm)
        for dep in _NEEDS.get(base, ()):
            add(dep)
        order.append(nm)
    for nm in names:
        add(nm)
    return order


def _scales_wanted(names, cell):
    """{scale in metres: [names]} for the curvature masks among names (no suffix = 2 x cell)."""
    out = {}
    for nm in names:
        base, scale = parse_name(nm)
        if base in SCALED:
            s = 2.0 * cell if scale is None else scale
            out.setdefault(s, []).append(nm)
    return out


def _blurred(h, sigma_m, cell, x0, y0, wrap, outside, fill='odd', cubic=True, centre=0.0):
    """(b, f, mc): h - centre smoothed with sigma_m on its window grid (factor f, margin mc), float32."""
    sc = sigma_m / cell
    ny, nx = np.shape(h)
    f = min(_decimation(sc, nx, wrap[0]), _decimation(sc, ny, wrap[1])) if any(wrap) else _decimation(sc, nx)
    mc = int(math.ceil(4.0 * sc / f)) + 2
    g = window_grid(np.asarray(h, np.float64) - centre, f, mc, cell, x0, y0, wrap,
                    (None if outside is None else (lambda x, y, cubic=True: outside(x, y, cubic=cubic) - centre)),
                    fill, cubic)
    return gaussian_blur(g, sc / f), f, mc, g


def compute(fields, cell=None, x0=None, y0=None, names=None, norms=None, params=None, outside=None, strict=None):
    """The masks of one level: a Masks dict {name: float32 (ny, nx)}.

    fields    a mapping with 'h' (metres) and optionally 'A' (m^2) and the process fields (module doc); core's Fields
              carries its level, so cell, x0 and y0 may be left out
    cell      the level's cell, metres; x0, y0 the window's south-west corner in world metres (default 0)
    names     the masks to make (default DEFAULT_NAMES); a scaled curvature is asked for by suffix: 'concave_200m'
    norms     the main level's Norms (norms_from); None measures this level as if it were the main one
    params    MaskParams
    outside   a callable (x, y, cubic=bool) -> heights beyond this level's window, NaN where unknown (StackSampler
              over its parents); None: the level stands alone (linear extrapolation for the derivatives and blurs,
              open sky for the occlusion march)
    strict    a named mask whose input is absent raises KeyError when strict, else it is skipped (Masks.skipped says
              why); default: strict when names are given"""
    lvl = getattr(fields, 'level', None)
    cell = float(cell if cell is not None else _lv(lvl, 'cell'))
    x0 = float(x0 if x0 is not None else _lv(lvl, 'x0', 0.0))
    y0 = float(y0 if y0 is not None else _lv(lvl, 'y0', 0.0))
    P = params or MaskParams()
    explicit = (names is not None) if strict is None else bool(strict)
    if names is None:
        names = list(DEFAULT_NAMES)
        for s in P.curvature_scales_m:
            if s is not None and s != 20.0:
                names += [f'{b}_{scale_suffix(s)}' for b in SCALED]
    names = list(names)
    get = (lambda k: fields.get(k)) if hasattr(fields, 'get') else (lambda k: None)
    h = np.asarray(fields['h'], np.float64)
    ny, nx = h.shape
    out = Masks(cell, x0, y0, (ny, nx))
    out.params = P
    if norms is None:
        norms = norms_from(fields, cell, P)
    out.norms = norms
    want = _expand(names)
    res = {}
    t0 = time.perf_counter()

    def missing(nm, why):
        if explicit and nm in names:
            raise KeyError(f'mask {nm!r}: {why}')
        if nm in names:
            out.skipped[nm] = why

    # ---- slope, aspect, height
    hp = pad_level(h, 1, cell, x0, y0, P.wrap, outside, fill='odd')
    p, q = gradient(hp, 1, ny, nx, cell)                    # differences in float64 (h is thousands of metres)
    p, q = p.astype(F32), q.astype(F32)
    g = np.hypot(p, q)
    slope = np.arctan(g)
    slope *= F32(180.0 / math.pi)
    res['slope'] = slope
    res['height'] = h
    res['height_norm'] = np.clip((h - norms.h_lo) * (1.0 / max(norms.h_hi - norms.h_lo, 1e-6)), 0.0, 1.0)
    if {'aspect', 'northness', 'eastness', 'snow', 'vegetation'} & set(want):
        asp = np.arctan2(-p, -q)
        asp *= F32(180.0 / math.pi)
        asp %= F32(360.0)
        res['aspect'] = np.where(g > F32(1e-9), asp, F32(0.0))
        fade = smoothstep(1.0, 3.0, slope) / np.maximum(g, F32(1e-12))
        res['northness'] = -q * fade
        res['eastness'] = -p * fade
    out.seconds['geometry'] = time.perf_counter() - t0
    # ---- curvature at each scale
    t1 = time.perf_counter()
    mu = float(h.mean())
    for s, nms in sorted(_scales_wanted(want, cell).items()):
        b, f, mc, _g = _blurred(h, s, cell, x0, y0, P.wrap, outside, centre=mu)
        kp, kt = curvatures(b, cell * f, P.flat_slope_deg)
        kp, kt = to_kept(kp, f, mc, ny, nx), to_kept(kt, f, mc, ny, nx)
        bend = (kp + kt) * F32(s)
        for nm in nms:
            base, _ = parse_name(nm)
            res[nm] = {'curv_profile': lambda: kp, 'curv_plan': lambda: kt,
                       'convex': lambda: smoothstep(P.bend[0], P.bend[1], bend),
                       'concave': lambda: smoothstep(P.bend[0], P.bend[1], -bend)}[base]()
    out.seconds['curvature'] = time.perf_counter() - t1
    # ---- peaks: high and convex, at each scale: above the local mean by enough standard deviations and metres
    if 'peaks' in want:
        t1 = time.perf_counter()
        pk = np.zeros((ny, nx), F32)
        hc = np.asarray(h - mu, F32)
        for s in P.peaks_scales_m:
            b, f, mc, gr = _blurred(h, s, cell, x0, y0, P.wrap, outside, centre=mu)
            b2 = gaussian_blur(gr * gr, s / cell / f)
            b, b2 = to_kept(b, f, mc, ny, nx), to_kept(b2, f, mc, ny, nx)
            rise = hc - b
            std = np.sqrt(np.maximum(b2 - b * b, F32(P.peaks_std_floor_m ** 2)))
            np.maximum(pk, smoothstep(P.peaks_dev[0], P.peaks_dev[1], rise / std)
                       * smoothstep(P.peaks_rise[0] * s, P.peaks_rise[1] * s, rise), out=pk)
        res['peaks'] = pk * smoothstep(P.peaks_height_norm[0], P.peaks_height_norm[1], res['height_norm'])
        out.seconds['peaks'] = time.perf_counter() - t1
    # ---- water and the pass-through process fields
    wd = _water_depth(fields, P, h)
    if wd is not None:
        res['water'] = wd
        wet_cell = smoothstep(0.0, 0.3, wd)
    else:
        missing('water', "no 'water' field and no sea_level")
        wet_cell = np.zeros((ny, nx), F32)
    dry = F32(1.0) - wet_cell
    for nm in PASS_THROUGH:
        if nm not in want:
            continue
        v = get(nm)
        if v is None:
            missing(nm, f"no {nm!r} field (that process did not run)")
        else:
            res[nm] = np.maximum(np.asarray(v, np.float64), 0.0) if nm != 'lava' else np.asarray(v, np.float64)
    cover = np.zeros((ny, nx), F32)
    for nm in ('deposit', 'talus', 'sand'):
        v = get(nm)
        if v is not None:
            cover += np.maximum(np.asarray(v, F32), F32(0.0))
    cover_w = smoothstep(P.cover_m[0], P.cover_m[1], cover)
    # ---- occlusion
    if 'occlusion' in want:
        t1 = time.perf_counter()
        res['occlusion'] = sky_view(h, cell, P.occlusion_radius_m, x0, y0, P.wrap, outside,
                                    P.occlusion_directions, P.occlusion_step_ratio)
        out.seconds['occlusion'] = time.perf_counter() - t1
    # ---- drainage: flow, channels, wetness
    t1 = time.perf_counter()
    A = get('A')
    if A is None:
        for nm in ('flow', 'channels', 'wetness'):
            if nm in want:
                missing(nm, "no drainage area 'A' (run the route stage to convergence first)")
    else:
        A = np.maximum(np.asarray(A, F32), F32(cell * cell))
        log_a = np.log10(A) - F32(math.log10(cell))                        # log10 of a = A / cell
        if 'flow' in want:
            res['flow'] = np.clip((log_a - F32(norms.flow_lo)) * F32(1.0 / max(norms.flow_hi - norms.flow_lo, 1e-6)),
                                  0.0, 1.0)
        if 'channels' in want:
            thr = P.channel_area_m2 if P.channel_area_m2 is not None else channel_area_for_cell(cell)
            lt = math.log10(thr)
            ch = smoothstep(lt - 0.7, lt + 0.3, log_a + F32(math.log10(cell))) * dry
            sand = get('sand')
            if sand is not None:                          # rain soaks into dune sand: no runoff lines across it
                ch *= F32(1.0) - smoothstep(P.sand_swallows_m[0], P.sand_swallows_m[1], sand)
            res['channels'] = ch
        if 'wetness' in want:
            twi = log_a * F32(math.log(10.0)) - np.log(np.maximum(g, F32(1e-3)))
            tw = np.clip((twi - F32(norms.twi_lo)) * F32(1.0 / max(norms.twi_hi - norms.twi_lo, 1e-6)), 0.0, 1.0)
            res['wetness'] = np.maximum(tw, wet_cell)
    out.seconds['drainage'] = time.perf_counter() - t1
    # ---- rock, its foot, snow, vegetation
    t1 = time.perf_counter()
    if 'rock' in want:
        steep = smoothstep(P.rock_deg[0], P.rock_deg[1], slope)
        wear = get('wear')
        if wear is not None:
            steep = np.maximum(steep, smoothstep(P.rock_wear_m[0], P.rock_wear_m[1], np.asarray(wear, F32)))
        res['rock'] = steep * (F32(1.0) - cover_w) * dry
    if 'rock_toe' in want:
        # inside the rockfall shadow of exposed rock, on ground that is not rock itself; concave feet (talus cones,
        # aprons) score highest
        t2 = time.perf_counter()
        tan_up = rock_shadow(h, res['rock'], cell, P.rock_toe_reach_m, P.wrap, P.rock_toe_directions)
        sh = [math.tan(math.radians(a)) for a in P.rock_toe_shadow_deg]
        res['rock_toe'] = (smoothstep(sh[0], sh[1], tan_up) * (F32(1.0) - res['rock'])
                           * (F32(0.75) + F32(0.25) * res['concave_20m']) * dry)
        out.seconds['rock_toe'] = time.perf_counter() - t2
    if 'snow' in want:
        if P.snowline_m is None:
            missing('snow', 'no snowline_m')
        else:
            alt = (np.asarray(h + P.base_elevation_m, F32) + F32(P.snow_aspect_m) * res['northness']
                   + F32(P.snow_concave_m) * (res['concave_20m'] - res['convex_20m']))
            res['snow'] = (smoothstep(P.snowline_m - P.snow_band_m, P.snowline_m + P.snow_band_m, alt)
                           * (F32(1.0) - smoothstep(P.snow_slope_deg[0], P.snow_slope_deg[1], slope)) * dry)
    if 'vegetation' in want:
        v = F32(1.0) - smoothstep(P.veg_slope_deg[0], P.veg_slope_deg[1], slope)
        if P.treeline_m is not None:                      # south faces carry the treeline higher
            alt = np.asarray(h + P.base_elevation_m, F32) + F32(0.5 * P.snow_aspect_m) * res['northness']
            above_tl = smoothstep(P.treeline_m - P.treeline_band_m, P.treeline_m + P.treeline_band_m, alt)
            v *= F32(1.0) - F32(1.0 - P.alpine_density) * above_tl
        if 'wetness' in res:
            v *= F32(0.35) + F32(0.65) * res['wetness']
        if 'occlusion' in res:
            v *= smoothstep(0.35, 0.75, res['occlusion'])
        # (no channels term: channels' threshold is per level, and vegetation must mean the same on every level)
        for nm, k in (('rock', 1.0), ('snow', 1.0), ('rock_toe', 0.5)):
            if nm in res:
                v *= F32(1.0) - F32(k) * res[nm]
        for nm, (a0, a1) in (('talus', (0.2, 2.0)), ('sand', (0.1, 1.0))):
            fv = get(nm)
            if fv is not None:
                v *= F32(1.0) - smoothstep(a0, a1, fv)
        res['vegetation'] = np.clip(v * dry, 0.0, 1.0)
    out.seconds['surface'] = time.perf_counter() - t1
    # ---- strata
    if 'strata' in want:
        zs = get('zs')
        if zs is not None:
            res['strata'] = np.asarray(zs, np.float64)
        elif P.strata:
            st = P.strata
            X = x0 + (np.arange(nx) + 0.5) * cell
            Y = y0 + (np.arange(ny) + 0.5) * cell
            XX, YY = np.meshgrid(X, Y)
            az = math.radians(st.get('azimuth_deg', 0.0))
            zs = h + P.base_elevation_m - math.tan(math.radians(st.get('dip_deg', 0.0))) * (
                XX * math.cos(az) + YY * math.sin(az))
            if callable(st.get('warp')):
                zs = zs - np.asarray(st['warp'](XX, YY), np.float64)
            res['strata'] = zs
        else:
            missing('strata', "no 'zs' field and no params.strata")
    for nm in names:
        if nm in res:
            out[nm] = np.ascontiguousarray(res[nm], dtype=F32)
    out.seconds['total'] = time.perf_counter() - t0
    return out


# ---------------------------------------------------------------- the stack
def pin_band(child, parent, band=16, skip=('aspect',)):
    """A child level's masks pinned to its parent's in its outer `band` cells, as the level runner pins its heights
    (DESIGN.md 2.2): weight 1 at the edge falling smoothly to 0 at `band` cells in, the parent's masks read bilinearly
    at the child's cells. So every mask meets the ring next to it exactly at the seam, the level-of-detail ones
    (2 x cell curvature, channels) included, and fades to the child's own across the band. aspect is not blended
    (degrees tear at north; materials read northness and eastness). In place; returns child."""
    ny, nx = child.shape
    d = np.minimum(np.minimum(np.arange(ny)[:, None], np.arange(ny)[::-1][:, None]),
                   np.minimum(np.arange(nx)[None, :], np.arange(nx)[::-1][None, :]))
    w = F32(1.0) - smoothstep(0.0, float(band), d)
    sel = w > 0
    if not sel.any():
        return child
    J, I = np.nonzero(sel)
    fx = (child.x0 + (I + 0.5) * child.cell - parent.x0) / parent.cell - 0.5
    fy = (child.y0 + (J + 0.5) * child.cell - parent.y0) / parent.cell - 0.5
    py, px = parent.shape
    ok = (fx >= 0) & (fx <= px - 1) & (fy >= 0) & (fy <= py - 1)
    J, I, fx, fy, ws = J[ok], I[ok], fx[ok], fy[ok], w[sel][ok]
    x0 = np.minimum(np.floor(fx).astype(np.int64), px - 2)
    y0 = np.minimum(np.floor(fy).astype(np.int64), py - 2)
    tx, ty = (fx - x0).astype(F32), (fy - y0).astype(F32)
    for nm, v in child.items():                           # the positions once, a bilinear gather per mask
        if nm in skip or nm not in parent:
            continue
        a = parent[nm]
        pv = ((a[y0, x0] * (1 - tx) + a[y0, x0 + 1] * tx) * (1 - ty)
              + (a[y0 + 1, x0] * (1 - tx) + a[y0 + 1, x0 + 1] * tx) * ty)
        cur = v[J, I]
        v[J, I] = cur + ws * (pv - cur)
    return child


def compute_stack(level_fields, levels=None, main=None, names=None, params=None, strict=None, border_band=16):
    """Masks for every level of a stack (coarsest first): each level padded with its parents' terrain beyond its
    window (so a blur, a derivative or the occlusion march at its edge sees what the ring next to it shows),
    normalised by the main level, and pinned to its parent's masks across its outer border_band cells (pin_band; 0
    turns that off). levels: each with x0, y0, cell (and role) as objects or dicts; None takes them from each Fields'
    .level. main: the main level's index (default: the level whose role is 'main', else the finest level that is not
    'hero', else the last). Returns a list of Masks."""
    if levels is None:
        levels = [getattr(f, 'level') for f in level_fields]
    if main is None:
        roles = [_lv(l, 'role') for l in levels]
        if 'main' in roles:
            main = roles.index('main')
        else:
            non_hero = [i for i, r in enumerate(roles) if r != 'hero']
            main = non_hero[-1] if non_hero else len(levels) - 1
    P = params or MaskParams()
    norms = norms_from(level_fields[main], _lv(levels[main], 'cell'), P)
    layers = []
    result = []
    for f, lv in zip(level_fields, levels):
        cell, x0, y0 = float(_lv(lv, 'cell')), float(_lv(lv, 'x0')), float(_lv(lv, 'y0'))
        outside = StackSampler(layers) if layers else None
        m = compute(f, cell, x0, y0, names=names, norms=norms, params=P, outside=outside, strict=strict)
        if result and border_band:
            t0 = time.perf_counter()
            pin_band(m, result[-1], border_band)
            m.seconds['border_pin'] = time.perf_counter() - t0
        result.append(m)
        layers.append((x0, y0, cell, np.asarray(f['h'], np.float64)))
    return result


def describe_masks():
    """One line per mask: name, unit, meaning."""
    return '\n'.join(f'{k:14s} {u:10s} {d}' for k, (u, d) in MASKS.items())


__all__ = ['MASKS', 'DEFAULT_NAMES', 'MaskParams', 'Norms', 'Masks', 'StackSampler', 'compute', 'compute_stack',
           'norms_from', 'pin_band', 'attribute_name', 'channel_area_for_cell', 'parse_name', 'scale_suffix',
           'smoothstep', 'gaussian_blur', 'pad_level', 'window_grid', 'to_kept', 'gradient', 'curvatures', 'sky_view',
           'rock_base', 'rock_shadow', 'describe_masks']
