"""The surface data bake (SURFACING_DESIGN.md 2.3): per level, the terrain's fields and masks in, the new maps out.

    from eidoblend.terrain.surface import bake as B
    opts = B.resolve_options(terrain, palette=None, options=None)      # every setting, the terrain's constants in
    levels, info = B.bake_levels(terrain, opts, log=print)             # [{map: array}], coarsest first
    B.bake_key(terrain, opts)                                          # the cache key of that bake

Levels run coarsest first: a level reads what its parent kept (its padded height, settled layer, snow, provenance,
wider crest and valley terms, filled surface and drainage area), so every map continues across a window edge, and
each map's outer 16 cells are then blended to the parent's map with masks.pin_band's ramp.

A level works on its window padded by MARGIN cells of its parents' terrain (the parent's padded height upsampled
with the levels' own Catmull-Rom; beyond the coarsest level a linear extrapolation), so a blur, a march or a
relaxation at the window's edge sees what the ring next to it shows. Heights go to the GPU less the level's mean
(float32 keeps 7 digits).

Per level (the design's steps, in the order they run):
   5  the blur pyramid: crest, valley, n20 (blur, crest)
  11  wind streaks, when the terrain has a wind (crest's exposure, streak)
   7  snowpack, when the terrain has a snowline (relax, twice): before the relief, which it buries
   2  field normal on the detail grid (upsample2, field_normal)
   3  relief below the cell: a spectrum of flow-steered gullies from the terrain's top octave down to 2 texels,
      varied in spacing and depth, started by the catchment, none on sand, buried by snow, stepping back where the
      height already has relief (phacelle); rock ribs (solvers/detail.py's breakup strength)
   4  cavity and crest_fine on the detail grid (cavity, blur)
  10  debris provenance: src_strata and grain (carry_src)
   6  settle (solvers/detail.py's relax)
   8  the filled surface (fill) on every level; on hero levels the drainage area routed again with the parent's
      catchment pinned in around the window (flow_weights, pin_inflow, solvers/hydro.py's route_to_convergence),
      and flow, wetness and channels from it with masks.py's formulas and the main tile's norms
   9  spi and fresh
  12  pins (masks.pin_band)
Gutters are filled when the atlases are assembled (surface/atlas.py), from the parent's pinned maps.

The device is solvers/fluvial.py's: 'gpu' (core/gpu.py, in Blender) or 'twin' (the numpy twins, for small grids in
plain Python: surface/twins.py). No bpy here.
"""
from __future__ import annotations

import copy
import glob
import hashlib
import json
import math
import os
import time
from types import SimpleNamespace

import numpy as np

from .. import masks as M
from ..core import grid as Gd
from ..core import twins as T
from ..core import world_noise as N
from . import maps as MP
from . import twins as TW

F = np.float32
MARGIN = 48                       # cells of the parents' terrain around a level's window (even: whole parent cells)
BAND = 16                         # the border band: a level's maps are blended to its parent's over it (cells)
BIG = 1.0e30
HERE = os.path.dirname(os.path.abspath(__file__))
BAKE_VERSION = 1
GULLY_LAMBDA0_M = 4096.0          # the world gully octaves: lambda_o = 4096 m x 2^-o on every level
CREST_SCALES_M = (8.0, 16.0, 32.0, 64.0, 128.0)    # crest's octaves, metres, on every level
GATE_SCALES_M = (8.0, 16.0, 32.0, 64.0)            # the geometry gates' crest scales (the gate texture's channels)
GATE_OWN_CELLS = 32.0             # a level makes a gate whose window (2 s) spans at most this many of its cells

DEFAULTS = dict(
    maps='all',                   # 'all': every map; 'masks': the field normal only (D), beside the masks the
                                  # terrain already has (no new kernels: the first SurfaceData a material reads)
    detail='auto',                # the detail grid: 'auto' (half the cell on main and hero levels of at most 1024
                                  # cells, the cell elsewhere), 1 (the cell everywhere) or 2
    detail_strength=0.5,          # the sub-cell relief's share in the height the cavity march reads (the material's
                                  # detail_strength default)
    crest_tau=0.25,               # crest: the relief ratio one octave saturates at ((h - mean) / scale)
    valley_min_m=12.0,            # valley: its finest scale
    valley_flat=(0.16, 25.0),     # valley: the flatness threshold (a tangent) at a scale in metres (MRVBF's 16 % at
                                  # 25 m), falling as scale^-0.63
    settle=dict(layer_m=0.5, repose_deg=20.0, passes=60, rate=0.12),
    snow=dict(depth_m=1.5, band_m=250.0, aspect_m=220.0, slip_deg=38.0, flow_deg=14.0, passes=100, rate=0.12,
              melt_sun_m=0.9, melt_low_m=3.0, flow=(0.5, 0.7)),
    fresh=dict(spi=(0.72, 0.95), over_deg=(1.0, 9.0), steep_deg=(25.0, 35.0)),  # steep_deg: where stream power
                                  # hands over to the threshold's exceedance (the 20 m slope)
    reroute_hero=False,           # route the hero levels' drainage again with the parent's catchment pinned in
                                  # (step 8). Off: the level runner already routes every hero level on its exact
                                  # fill with the parent's inflow pinned (solvers/hydro.py op_route, inflow), and it
                                  # keeps Lauterbrunnen's trunk (146 km2 on the main level, 131-162 km2 on the
                                  # hero levels across 10 m), where this route, on the capped fill, carried 77-113;
                                  # so the hero levels keep the masks' flow, wetness, channels
    gully=dict(),                 # the gully filter's parameters over solvers/detail.py's GULLY (and the recipe's
                                  # gully stage, where it has one): its soil mask (slope_deg), normalization, and
                                  # amp_m / wavelength_m for the spectrum's k where a stage sets them
    relief=dict(                  # the gully spectrum (step 3; kernels/phacelle.glsl says how each is used)
        top_cells=12.0,           # the top octave: the first world octave under this many main-level cells ...
        top_max_m=256.0,          # ... and at most this (coarser valleys are the geometry's)
        k=0.025,                  # every octave's mean depth over its wavelength (self-similar; 0.08 drew a washboard)
        jitter=0.3,               # a lattice point's stripe spacing: 2^(+-jitter) of its octave's
        spread=1.2,               # the gullies' depths: log-normal of this spread (most faint, a few deep)
        along=3.0,                # a gully keeps its depth this many lattice cells down the flow (1 across)
        steer=0.35,               # how much each octave turns the next into its gully walls (branching)
        initiation=1.0,           # an octave's gullies start where the specific catchment is this x its wavelength
        loose_initiation=4.0,     # ... times this on loose debris (deposit + talus), which swallows the runoff
        loose_m=(0.3, 2.0),       # loose debris that does so: a smoothstep of its thickness, metres
        sand_m=(0.1, 0.6),        # no gullies on sand: a smoothstep of its thickness, metres
        bury=(0.5, 2.0),          # a snowpack of 0.5-2 x an octave's amplitude buries its gullies
        geo=(0.12, 0.35),         # an octave the cells can hold steps back where the level's own height has relief
                                  # at its scale: the RMS of crest's term at a quarter of the wavelength, over half it
    ),
    rock_deg=(34.0, 46.0),        # bare rock for provenance and the ribs: a smoothstep of the slope (masks.py's)
    reach_m=None,                 # how far fallen rock reaches (None: the masks' rock_toe_reach_m, 300 m)
    carry_passes=512,             # provenance: the most Jacobi passes a level runs (a child starts from its parent)
    streak_cells=10.0,            # the wind tail's length, cells
    fill_slope=5.0e-4,            # the filled surface's least descent (metres per metre)
    fill_cap_m=3.0,               # the deepest pit the fill fills: deeper basins (craters, sinkholes, interdune pans)
                                  # stay sinks where their water ends
    flow_p=1.0,                   # the multiple-flow exponent (the level runner's)
    backend='auto',               # 'gpu' | 'twin' | 'auto' (the GPU in Blender, the twins in plain Python)
    # the terrain constants the bake reads (None: the terrain's, then the palette's, then palettes.CONSTANTS, then
    # the defaults in CONSTANT_DEFAULTS)
    snowline_m=None, base_elevation_m=None, sun_azimuth_deg=None, sun_elevation_deg=None, wind_azimuth_deg=None,
)
# what a constant is when neither the terrain, the palette nor palettes.CONSTANTS names it
CONSTANT_DEFAULTS = dict(base_elevation_m=0.0, snowline_m=1.0e5, sun_azimuth_deg=180.0, sun_elevation_deg=45.0,
                         wind_azimuth_deg=None)
NO_SNOW_M = 2.0e4                 # a snowline at or above this is "no snow"


# ----------------------------------------------------------------------------------------- the terrain's side ---

def recipe_defaults(terrain):
    """The recipe's defaults with its defaults_for(knobs) merged in, as api.generate reads them."""
    R = getattr(terrain, 'recipe', None)
    dfl = dict(getattr(R, 'defaults', None) or {})
    fn = getattr(R, 'defaults_for', None)
    if fn is not None:
        try:
            dfl.update(fn(getattr(terrain, 'knobs', None) or {}))
        except Exception:                                 # noqa: BLE001 - a recipe dict without its code
            pass
    return dfl


def mask_params(terrain):
    """The MaskParams the terrain's masks were made with (api.generate's: the recipe's mask_params, the sea level,
    the base elevation)."""
    info = getattr(terrain, 'info', None) or {}
    mp = dict(recipe_defaults(terrain).get('mask_params') or {})
    mp['sea_level'] = info.get('sea_level')
    mp['base_elevation_m'] = float(info.get('base_elevation_m') or 0.0)
    allowed = set(M.MaskParams.__dataclass_fields__)
    return M.MaskParams(**{k: v for k, v in mp.items() if k in allowed})


def terrain_constants(terrain):
    """The terrain's own constants (build/surfacing.py's terrain_constants, read off the Terrain instead of the
    object): its base elevation, and the snowline and treeline of its knobs, its recipe's mask parameters or its real
    place (palettes.PLACES)."""
    info = getattr(terrain, 'info', None) or {}
    out = {}
    if info.get('base_elevation_m') is not None:
        out['base_elevation_m'] = float(info['base_elevation_m'])
    knobs = getattr(terrain, 'knobs', None) or {}
    mp = dict(recipe_defaults(terrain).get('mask_params') or {})
    dem = knobs.get('dem')
    if isinstance(dem, str):
        from ..build import palettes as P
        if dem in P.PLACES:
            mp.update(P.PLACES[dem].get('mask_params') or {})
    for key in ('snowline_m', 'treeline_m'):
        if knobs.get(key) is not None:
            mp[key] = knobs[key]
        if mp.get(key) is not None:
            out[key] = float(mp[key])
    return out


def resolve_palette(terrain, palette):
    """The filled-in palette dict a bake reads: `palette` as a name, 'auto', a palette dict or one already filled in
    (palettes.get), with the terrain's place strata merged in and the terrain's constants over the palette's, the
    way make_terrain builds its material. None stays None."""
    if palette is None:
        return None
    from ..build import palettes as P
    info = getattr(terrain, 'info', None) or {}
    if isinstance(palette, dict) and 'options' in palette and 'constants' in palette:
        pal = copy.deepcopy(palette)
    else:
        pal = P.get(palette, getattr(terrain, 'recipe', None))
        place = info.get('place')
        st = (P.PLACES.get(place) or {}).get('strata') if place else None
        if st:
            pal['strata'] = dict(pal.get('strata') or {}, **copy.deepcopy(st))
            for k, v in P.STRATA_DEFAULTS.items():
                pal['strata'].setdefault(k, copy.deepcopy(v))
    for k, v in terrain_constants(terrain).items():
        pal['constants'][k] = float(v)
    return pal


def resolve_options(terrain, palette=None, options=None):
    """Every bake setting: DEFAULTS, the given options over them (a dict option merges key by key), and the terrain
    constants filled in: an option given wins, then the terrain's own, then the palette's, then palettes.CONSTANTS,
    then CONSTANT_DEFAULTS. A palette's options may carry `relief` (a dict over DEFAULTS['relief']: a look's own gully
    spectrum, a badland's dense rills or a cinder field's few gullies); an option given wins over it. Raises KeyError
    naming an unknown option or relief key."""
    import difflib
    opts = copy.deepcopy(DEFAULTS)
    pal = palette if (palette is None or isinstance(palette, dict)) else resolve_palette(terrain, palette)
    look_relief = ((pal or {}).get('options') or {}).get('relief')
    for src in ([{'relief': look_relief}] if isinstance(look_relief, dict) else []) + [options or {}]:
        for k, v in src.items():
            if k not in DEFAULTS:
                near = difflib.get_close_matches(k, list(DEFAULTS), n=3)
                raise KeyError(f'bake_surface: no option {k!r}' + (f'; nearest: {", ".join(near)}' if near else ''))
            if k == 'relief' and isinstance(v, dict):
                bad = [q for q in v if q not in DEFAULTS['relief']]
                if bad:
                    raise KeyError(f'bake_surface: no relief key {bad[0]!r}; the keys: {", ".join(DEFAULTS["relief"])}')
            if isinstance(DEFAULTS[k], dict) and isinstance(v, dict):
                opts[k].update(v)
            else:
                opts[k] = v
    pal_consts = dict((pal or {}).get('constants') or {})
    try:
        from ..build import palettes as P
        base = dict(P.CONSTANTS)
    except Exception:                                     # noqa: BLE001
        base = {}
    own = terrain_constants(terrain)
    explicit_sun = any(k in (options or {}) or k in own or k in pal_consts
                       for k in ('sun_azimuth_deg', 'sun_elevation_deg'))
    for k, dflt in CONSTANT_DEFAULTS.items():
        if opts.get(k) is None:
            v = own.get(k, pal_consts.get(k, base.get(k, dflt)))
            opts[k] = None if v is None else float(v)
    # the place's climatological sun (SURFACING_DESIGN.md 2.2: palettes.climate_sun from latitude_deg), shared with
    # the plants and the material, unless an option, the terrain or the palette sets the sun outright
    try:
        from ..build import palettes as P
        climate_sun = getattr(P, 'climate_sun', None)
    except Exception:                                     # noqa: BLE001
        climate_sun = None
    if climate_sun is not None and not explicit_sun:
        consts = dict(base)
        consts.update(pal_consts)
        consts.update(own)
        az, el = climate_sun(consts)
        opts['sun_azimuth_deg'], opts['sun_elevation_deg'] = float(az), float(el)
    if opts['reach_m'] is None:
        opts['reach_m'] = float(mask_params(terrain).rock_toe_reach_m)
    return opts


BAKE_CODE = ('bake.py', 'twins.py', 'maps.py', 'kernels/*.glsl')
PALETTE_CODE = ('palette_bake.py', 'far_colour.py', 'expr_glsl.py', 'noise.py', 'noise.glsl')
ATLAS_CODE = ('__init__.py', 'atlas.py', 'maps.py')


def code_hash(globs=BAKE_CODE):
    """SHA-1 over a part of the surface package's code (bytes and relative paths): by default the code that makes the
    maps (bake.py, twins.py, maps.py, kernels/*.glsl), so editing the palette bake (PALETTE_CODE) or the atlases
    (ATLAS_CODE) keeps the maps' cache, and those parts key their own files by their own code."""
    h = hashlib.sha1()
    files = sorted({p for g in globs for p in glob.glob(os.path.join(HERE, g))})
    for p in files:
        h.update(os.path.relpath(p, HERE).replace('\\', '/').encode('utf-8'))
        with open(p, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()


def terrain_key(terrain):
    """What names the terrain in a bake key: its cache key, or (a terrain made without one) a hash of its plan and
    its main level's height."""
    info = getattr(terrain, 'info', None) or {}
    if info.get('cache_key'):
        return str(info['cache_key'])
    h = hashlib.sha1()
    for lv in terrain.levels:
        h.update(repr((round(lv.x0, 6), round(lv.y0, 6), round(lv.cell, 9), lv.n, lv.role)).encode())
    h.update(np.ascontiguousarray(_fields(terrain, _main_index(terrain.levels))['h'], F).tobytes())
    return 'nokey_' + h.hexdigest()


def bake_key(terrain, opts):
    """The bake's cache key: SHA-1 of the terrain's key, the bake's code and its options."""
    o = {k: v for k, v in opts.items() if k != 'backend'}
    blob = json.dumps(dict(terrain=terrain_key(terrain), code=code_hash(), version=BAKE_VERSION, options=o),
                      sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()


def _fields(terrain, i):
    f = terrain.fields(i) if callable(getattr(terrain, 'fields', None)) else terrain.fields[i]
    return f


def _masks(terrain, i):
    ms = terrain.masks
    if hasattr(ms, 'level'):
        return ms.level(i)
    return ms[i]


def _main_index(levels):
    roles = [lv.role for lv in levels]
    if 'main' in roles:
        return roles.index('main')
    non_hero = [i for i, r in enumerate(roles) if r != 'hero']
    return non_hero[-1] if non_hero else len(levels) - 1


def detail_factor(level, opts):
    """Detail texels per cell on a level: 'auto' gives 2 on the main and hero levels of at most 1024 cells whose
    cell is 2 m or more, else 1 (finer levels gain under 1 degree of normal at half the cell, and their scans' own
    normals cover that band: SURFACING_DESIGN.md 2.2)."""
    d = opts.get('detail', 'auto')
    if d == 'auto':
        return 2 if (level.role in ('main', 'hero') and level.n <= 1024 and float(level.cell) >= 2.0 - 1e-6) else 1
    d = int(d)
    if d not in (1, 2):
        raise ValueError(f"bake_surface: detail {d!r} is 'auto', 1 or 2")
    return 2 if (d == 2 and level.n <= 1024) else 1


# ------------------------------------------------------------------------------------------------- the bake ---

def _K(name):
    return TW.inline(name)


def _tan(deg):
    return math.tan(math.radians(float(deg)))


def _smooth(e0, e1, x):
    return TW.smoothstep(e0, e1, x)


def _crop(a, m, n, f=1):
    return np.ascontiguousarray(a[m * f:(m + n) * f, m * f:(m + n) * f])


class _Baker:
    """One bake: the state every level shares (the terrain, the options, the device, the main tile's norms) and
    what each level keeps for its child."""

    def __init__(self, terrain, opts, log=print):
        from ..solvers import fluvial as FL
        self.t = terrain
        self.o = opts
        self.log = log or (lambda *a, **k: None)
        self.levels = list(terrain.levels)
        be = opts.get('backend', 'auto')
        if be == 'auto':
            try:
                import gpu  # noqa: F401 - Blender's GPU module
                be = 'gpu'
            except ImportError:
                be = 'twin'
        if opts.get('maps', 'all') not in ('all', 'masks'):
            raise ValueError(f"bake_surface: maps {opts.get('maps')!r} is 'all' or 'masks'")
        self.dev = FL.device('twin' if be == 'twin' else 'gpu')
        self.backend = 'numpy' if self.dev.name == 'twin' else 'gpu'
        self.P = mask_params(terrain)
        self.main = _main_index(self.levels)
        info = getattr(terrain, 'info', None) or {}
        self.seed = int(info.get('seed') or 0)
        self.base = float(opts['base_elevation_m'] or 0.0)
        self.keep = {}
        self.times = []
        self.octave_m = {}                # per level: the wavelengths of its gully octaves (info['relief_octaves'])
        self._stages = None
        fm = _fields(terrain, self.main)
        self.norms = M.norms_from(fm, self.levels[self.main].cell, self.P)
        self.spi_norm = self._spi_norms(fm, self.levels[self.main].cell)
        self.snow_on = opts['snowline_m'] is not None and float(opts['snowline_m']) < NO_SNOW_M
        self.wind = None
        if opts.get('wind_azimuth_deg') is not None:
            az = math.radians(float(opts['wind_azimuth_deg']))
            self.wind = (math.sin(az), math.cos(az))          # the unit vector the wind blows toward (a bearing)
        az, el = math.radians(float(opts['sun_azimuth_deg'])), math.radians(float(opts['sun_elevation_deg']))
        self.sun = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))

    # ---- norms and recipe stages
    def _spi_norms(self, f, cell):
        """The 5th and 95th percentiles of log10(a tan S) over the main tile's land (spi's normalisation), S the
        slope of the height blurred at 20 m, as the levels' spi reads it."""
        if 'A' not in f:
            return None
        h = np.asarray(f['h'], np.float64)
        hb = h
        s20 = 20.0 / float(cell)
        if s20 > 0.25:
            m = int(math.ceil(4.0 * s20)) + 2
            hp = M.pad_level(h - h.mean(), m, cell, wrap=self.P.wrap, fill='odd')
            hb = np.asarray(M.gaussian_blur(hp, s20), np.float64)[m:-m, m:-m]
        g = np.maximum(M._slope_tan(hb, cell, self.P.wrap), 1e-3)
        a = np.maximum(np.asarray(f['A'], np.float64), cell * cell) / cell
        v = np.log10(a * g)
        wd = M._water_depth(f, self.P, h)
        land = v if wd is None else v[wd <= 0.0]
        if land.size < 16:
            land = v
        lo, hi = (float(x) for x in np.percentile(land, [5.0, 95.0]))
        return lo, max(hi, lo + 0.5)

    def stages(self):
        """The recipe's stages with the knobs put in (their op, params and level selection), or []."""
        if self._stages is None:
            self._stages = []
            R = getattr(self.t, 'recipe', None)
            if R is not None and hasattr(R, 'resolve'):
                try:
                    _values, stages = R.resolve(getattr(self.t, 'knobs', None) or None)
                    self._stages = [(s, set(s.select(self.levels, warn=lambda m: None))) for s in stages
                                    if s.params.get('enabled', True) is not False]
                except Exception as e:                    # noqa: BLE001 - a recipe that no longer resolves
                    self.log(f'[surface] the recipe\'s stages could not be read ({e}): defaults are used')
        return self._stages

    def stage(self, op, i):
        """(params, ran): the params of the recipe's first stage of `op`, and whether one ran on level i."""
        hits = [(s, sel) for s, sel in self.stages() if s.op == op]
        if not hits:
            return {}, False
        on = [s for s, sel in hits if i in sel]
        return dict((on[0] if on else hits[0][0]).params), bool(on)

    # ---- padding
    def _pad(self, i, own, key, kind='bilinear', fill='edge', shift=0.0, scale=1.0):
        """A level's field padded by MARGIN cells: the window its own, the margin its parent's padded field
        upsampled (kind) times `scale` plus `shift`; on the coarsest level the margin is `fill` (masks.pad_level).
        float32 (N, N)."""
        lv = self.levels[i]
        m = MARGIN
        own = np.asarray(own)
        if lv.parent is None or lv.parent not in self.keep or key not in self.keep[lv.parent]:
            out = M.pad_level(np.asarray(own, np.float64), m, lv.cell, lv.x0, lv.y0, self.P.wrap, None, fill=fill)
            return np.ascontiguousarray(out, F)
        p = self.levels[lv.parent]
        i0, j0, mc = lv.in_parent(self.levels)
        par = self.keep[lv.parent][key]
        out = Gd.crop_upsample2(par, i0 - m // 2 + m, j0 - m // 2 + m, mc + m, kind)
        if scale != 1.0:
            out *= F(scale)
        if shift != 0.0:
            out += F(shift)
        out[m:m + lv.n, m:m + lv.n] = own
        return out

    def _from_parent_tex(self, i, tex, kind, channels=4):
        """A parent's padded texture upsampled onto level i's padded grid (upsample2 on the device)."""
        lv = self.levels[i]
        m = MARGIN
        i0, j0, _mc = lv.in_parent(self.levels)
        N_ = lv.n + 2 * m
        out = self.dev.empty((N_, N_), 4)
        self.dev.run(_K('upsample2'), {'src': tex}, {'outU': out},
                     {'uOrigin': (i0 - m // 2 + m, j0 - m // 2 + m), 'uSize': (N_, N_),
                      'uKind': TW.UPSAMPLE_KINDS[kind]})
        return out

    # ---- one level
    def level_normal(self, i):
        """maps='masks': the field normal on the detail grid (step 2), pinned, and nothing else."""
        dev = self.dev
        lv = self.levels[i]
        f = _fields(self.t, i)
        par = self.keep.get(lv.parent) if lv.parent is not None else None
        n, m, cell = lv.n, MARGIN, float(lv.cell)
        fD = detail_factor(lv, self.o)
        ND = (n + 2 * m) * fD
        t0 = time.perf_counter()
        h = np.asarray(f['h'], np.float64)
        href = float(h.mean())
        shift = (par['href'] - href) if par is not None else 0.0
        hp = self._pad(i, h - href, 'hp', kind='catmull', fill='odd', shift=shift)
        tH = dev.texture(hp)
        if fD == 2:
            hD = dev.empty((ND, ND), 4)
            dev.run(_K('upsample2'), {'src': tH}, {'outU': hD},
                    {'uOrigin': (0, 0), 'uSize': (ND, ND), 'uKind': TW.UPSAMPLE_KINDS['catmull']})
        else:
            hD = tH
        hg = dev.empty((ND, ND), 4)
        dev.run(_K('field_normal'), {'hT': hD}, {'outG': hg}, {'uTexel': cell / fD})
        g = dev.read(hg)
        L = np.sqrt(F(1) + g[..., 1] * g[..., 1] + g[..., 2] * g[..., 2])
        out = {'normal_x': _crop(-g[..., 1] / L, m, n, fD), 'normal_y': _crop(-g[..., 2] / L, m, n, fD)}
        if par is not None:
            self._pin(i, out, fD)
        self.keep[i] = {'href': href, 'hp': hp, 'pinned': dict(out), 'fD': fD}
        self.times.append({'total': round(time.perf_counter() - t0, 4)})
        return out

    def level(self, i):
        if self.o.get('maps', 'all') == 'masks':
            return self.level_normal(i)
        dev, o = self.dev, self.o
        lv = self.levels[i]
        f = _fields(self.t, i)
        mk = _masks(self.t, i)
        par = self.keep.get(lv.parent) if lv.parent is not None else None
        n, m, cell = lv.n, MARGIN, float(lv.cell)
        N_ = n + 2 * m
        fD = detail_factor(lv, o)
        texel = cell / fD
        ND = N_ * fD
        tm = {}
        t0 = time.perf_counter()
        keep = {}
        out = {}

        # ---- inputs: the padded height (less the level's mean), cover, water, strata, drainage area
        h = np.asarray(f['h'], np.float64)
        href = float(h.mean())
        shift = (par['href'] - href) if par is not None else 0.0
        hp = self._pad(i, h - href, 'hp', kind='catmull', fill='odd', shift=shift)
        keep['href'], keep['hp'] = href, hp
        cover = np.zeros((n, n), F)
        for nm in ('deposit', 'talus', 'sand'):
            if nm in f:
                cover += np.maximum(np.asarray(f[nm], F), F(0))
        coverp = self._pad(i, cover, 'cover')
        keep['cover'] = coverp
        water = np.maximum(np.asarray(mk['water'], F), F(0)) if 'water' in mk else np.zeros((n, n), F)
        waterp = self._pad(i, water, 'water')
        keep['water'] = waterp
        zs_own = np.asarray(mk['strata'], np.float64) - href if 'strata' in mk else h - href
        zsp = self._pad(i, zs_own, 'zs', shift=shift)
        keep['zs'] = zsp
        has_A = 'A' in f
        tH = dev.texture(hp)
        tm['inputs'] = time.perf_counter() - t0

        # ---- step 5: the blur pyramid, crest, valley, n20 (and the gully filter's steering, the wind exposure)
        t1 = time.perf_counter()
        s20 = 20.0 / cell
        n20_own = (s20 <= 16.0) or par is None
        pyrA = self._blur4(tH, (1.0, 2.0, 4.0, 8.0))
        pyrB = self._blur4(tH, (16.0, min(s20, 16.0), 0.0, 0.0))
        if par is not None:
            parT = self._from_parent_tex(i, par['tK'], 'bilinear')
        else:
            parT = self._dummy()
        outC, outK, outX = dev.empty((N_, N_), 4), dev.empty((N_, N_), 4), dev.empty((N_, N_), 4)
        wind = self.wind or (0.0, 0.0)
        inherited = (par['crest_inherited'] + 1) if par is not None else 0     # Kc's terms: one per coarser level
        keep['crest_inherited'] = inherited
        dev.run(_K('crest'), {'hT': tH, 'pyrA': pyrA, 'pyrB': pyrB, 'parT': parT},
                {'outC': outC, 'outK': outK, 'outX': outX},
                {'uCell': cell, 'uTau': float(o['crest_tau']), 'uTerms': 5.0 + inherited,
                 'uSmin': float(o['valley_min_m']),
                 'uValley': tuple(float(v) for v in o['valley_flat']), 'uHasParent': int(par is not None),
                 'uN20Own': int(n20_own), 'uWind': wind})
        # what the child reads of this level: (Kc, Kv, n20 x, n20 y) in one texture
        c_arr = dev.read(outC)
        k_arr = dev.read(outK)
        keep['tK'] = dev.texture(np.concatenate([k_arr[..., :2], c_arr[..., 2:4]], axis=2))
        out['crest'] = self._crest_metres(i, tH, hp, par, keep)
        out['valley'] = _crop(c_arr[..., 1], m, n)
        out['n20_x'] = _crop(c_arr[..., 2], m, n)
        out['n20_y'] = _crop(c_arr[..., 3], m, n)
        del pyrA, pyrB, parT
        tm['pyramid'] = time.perf_counter() - t1

        # ---- step 11: wind streaks
        if self.wind is not None:
            t1 = time.perf_counter()
            sT = dev.empty((N_, N_), 1)
            dev.run(_K('streak'), {'exT': outX}, {'outS': sT},
                    {'uWind': self.wind, 'uLength': float(o['streak_cells'])})
            out['streak'] = _crop(dev.read(sT)[..., 0], m, n)
            del sT
            tm['streak'] = time.perf_counter() - t1
        del outX

        # ---- the slope, the field normal's parts and the altitude on the padded cell grid (snow, insolation)
        gy, gx = np.gradient(hp, F(cell))
        g = np.sqrt(gx * gx + gy * gy)

        # ---- step 7: snowpack (before the relief, which it buries)
        pack = np.zeros((N_, N_), F)
        if self.snow_on:
            t1 = time.perf_counter()
            pack = self._snowpack(i, hp, href, gx, gy, g, mk, par, keep)
            out['snowpack'] = _crop(pack, m, n).astype(F)
            tm['snow'] = time.perf_counter() - t1

        # ---- steps 2-4: the detail grid
        t1 = time.perf_counter()
        steer = outK
        if 'flow_x' in f and 'flow_y' in f:               # the routed flow vector, where the level has one
            fx, fy = np.asarray(f['flow_x'], F), np.asarray(f['flow_y'], F)
            L = np.maximum(np.hypot(fx, fy), F(1e-12))
            st = np.zeros((N_, N_, 4), F)
            st[..., 2] = np.pad(fx / L, m, mode='edge')
            st[..., 3] = np.pad(fy / L, m, mode='edge')
            steer = dev.texture(st)
        sand = np.maximum(np.asarray(f['sand'], F), F(0)) if 'sand' in f else np.zeros((n, n), F)
        sandp = self._pad(i, sand, 'sand')
        keep['sand'] = sandp
        a_spec = self._catchment(i, f, keep)
        tCover = dev.texture(np.stack([coverp, sandp, pack, a_spec], axis=2))
        if fD == 2:
            hD = dev.empty((ND, ND), 4)
            dev.run(_K('upsample2'), {'src': tH}, {'outU': hD},
                    {'uOrigin': (0, 0), 'uSize': (ND, ND), 'uKind': TW.UPSAMPLE_KINDS['catmull']})
        else:
            hD = tH
        hg = dev.empty((ND, ND), 4)
        dev.run(_K('field_normal'), {'hT': hD}, {'outG': hg}, {'uTexel': texel})
        octs, gp, rp = self._gully_octaves(i, texel)
        n_oct = int((octs[0, 1::2, 2] > 0.5).sum())        # the table's octaves (a level too coarse for any: none)
        self.octave_m[i] = [round(1.0 / float(v), 6) for v in octs[0, 1:2 * n_oct:2, 0]]
        gates = self._geo_gates(i, keep, octs)
        rockT, rock_ref, rock_deg, normal_cap = self._rock_relief(i, hg, texel, ND)
        outD, outR = dev.empty((ND, ND), 4), dev.empty((ND, ND), 4)
        dev.run(_K('phacelle'),
                {'hgT': hg, 'steerT': steer, 'octT': dev.texture(octs), 'rockT': rockT or self._dummy(),
                 'coverT': tCover, 'gateT': dev.texture(gates)},
                {'outD': outD, 'outR': outR},
                {'uOct': n_oct, 'uTexel': texel, 'uF': fD, 'uSteer': float(rp['steer']),
                 'uNorm': float(gp['normalization']), 'uSlope': tuple(float(v) for v in gp['slope_deg']),
                 'uRockDeg': rock_deg, 'uCover': tuple(float(v) for v in self.P.cover_m),
                 'uNormalCap': normal_cap, 'uRockRef': rock_ref, 'uRockOn': int(rockT is not None),
                 'uStrength': float(o['detail_strength']),
                 'uSpec': (float(rp['jitter']), float(rp['spread']), float(rp['along']), 0.0),
                 'uInit': (float(rp['initiation']), float(rp['loose_initiation'])) + tuple(
                     float(v) for v in rp['sand_m']),
                 'uLoose': tuple(float(v) for v in rp['loose_m']), 'uBury': tuple(float(v) for v in rp['bury'])})
        del tCover, gates
        blurD = self._blur4(outR, (1.0,) * 4, fan=False)                 # the relief surface at 1 and 2 texels
        blurD2 = self._blur4(outR, (2.0,) * 4, fan=False)
        outE = dev.empty((ND, ND), 4)
        dev.run(_K('cavity'), {'zT': outR, 'blurT': blurD, 'blur2T': blurD2}, {'outE': outE},
                {'uTexel': texel, 'uTau': float(o['crest_tau'])})
        tm['detail'] = time.perf_counter() - t1
        t1 = time.perf_counter()
        d_arr = dev.read(outD)
        e_arr = dev.read(outE)
        for c, nm in enumerate(('normal_x', 'normal_y', 'detail_gx', 'detail_gy')):
            out[nm] = _crop(d_arr[..., c], m, n, fD)
        for c, nm in enumerate(('crease', 'cavity', 'crest_fine')):
            out[nm] = _crop(e_arr[..., c], m, n, fD)
        del d_arr, e_arr, outD, outR, outE, blurD, hg, hD, rockT, steer, outK, outC
        tm['detail_read'] = time.perf_counter() - t1

        # ---- step 10: debris provenance
        t1 = time.perf_counter()
        reach = float(o['reach_m'])
        aux = np.zeros((N_, N_, 4), F)
        aux[..., 0], aux[..., 1] = coverp, zsp
        if par is not None:
            aux[..., 2] = 1.0
            aux[m:m + n, m:m + n, 2] = 0.0
            i0, j0, mc = lv.in_parent(self.levels)
            st0 = np.stack([Gd.crop_upsample2(par['carry'][..., c], i0 - m // 2 + m, j0 - m // 2 + m, mc + m,
                                              'nearest') for c in range(3)] + [np.zeros((N_, N_), F)], axis=2)
            st0[..., 0] += F(shift)
        else:
            st0 = np.zeros((N_, N_, 4), F)
            st0[..., 0], st0[..., 1] = zsp, 1.0e9
        passes = int(min(max(math.ceil(reach / cell), 4), int(o['carry_passes'])))
        sA, sB = dev.texture(st0), dev.empty((N_, N_), 4)
        tAux = dev.texture(aux)
        ku = {'uCell': cell, 'uRockDeg': tuple(float(v) for v in o['rock_deg']),
              'uCover': tuple(float(v) for v in self.P.cover_m), 'uSalt': int(i) + 7919 * (self.seed & 0xffff)}
        for _ in range(passes):
            dev.run(_K('carry_src'), {'hT': tH, 'auxT': tAux, 'stT': sA}, {'outS': sB}, ku)
            sA, sB = sB, sA
        carry = dev.read(sA)
        keep['carry'] = np.ascontiguousarray(carry[..., :3])
        cw = _crop(carry, m, n)
        valid = cw[..., 2] > 0.5
        fade = (F(1) - _smooth(0.7 * reach, reach, cw[..., 1])) * valid
        zs_w = _crop(zsp, m, n)
        h_w = _crop(hp, m, n)
        out['strata_dz'] = (zs_w - h_w).astype(F)
        out['src_dz'] = (zs_w + (cw[..., 0] - zs_w) * fade - h_w).astype(F)
        out['grain'] = np.where(valid, np.clip(cw[..., 1] / F(reach), 0.0, 1.0), F(1)).astype(F)
        del sA, sB, tAux, carry, cw
        tm['carry'] = time.perf_counter() - t1

        # ---- step 6: settle
        t1 = time.perf_counter()
        so = o['settle']
        layer = float(so['layer_m'])
        # (every level starts from a fresh layer, so its own benches, ledges and crevices catch what its walls shed;
        # a child adds what its parent gathered beyond the layer, so the foot of a slope longer than the passes reach
        # on the finer grid stays gathered. Starting from the parent's settled layer left the walls of a hero level
        # bare of anything to settle: its benches read shed)
        d0 = np.full((N_, N_), layer, F)
        if par is not None:
            d0 += np.maximum(self._inherit(i, 'settle_d') - F(layer), F(0))
        d1 = self._relax(hp, d0, _tan(so['repose_deg']), int(so['passes']), float(so['rate']), cell)
        keep['settle_d'] = d1
        out['settle'] = (np.clip(_crop(d1, m, n) / F(layer), 0.0, 2.0) * F(0.5)).astype(F)
        tm['settle'] = time.perf_counter() - t1

        # ---- step 8: the filled surface; on hero levels the drainage area again, the parent's catchment pinned in
        t1 = time.perf_counter()
        W, fill_passes = self._fill(i, hp, waterp, par, shift)
        keep['fill'] = W
        tm['fill'] = time.perf_counter() - t1
        A_w = np.asarray(f['A'], F) if has_A else None
        if has_A:
            t1 = time.perf_counter()
            if o.get('reroute_hero') and lv.role == 'hero' and par is not None and 'A' in par:
                Ap, iters = self._route(i, W, par)
                A_w = _crop(Ap, m, n)
                keep['A'] = Ap
                out['area'] = A_w
                out.update(self._drainage_masks(A_w, f, mk, lv))
                tm['route'] = time.perf_counter() - t1
                tm['route_iterations'] = iters
            else:
                keep['A'] = self._pad(i, A_w, 'A', scale=0.5)
        tm['fill_passes'] = fill_passes

        # ---- step 9: spi and fresh
        if has_A and self.spi_norm is not None:
            t1 = time.perf_counter()
            g_w = _crop(g, m, n)
            a = np.maximum(A_w, F(cell * cell)) / F(cell)
            lo, hi = self.spi_norm
            # the slope at 20 m (n20): the same on every level, where a hero level's own slope resolves ever steeper
            # faces and lifted the stream power of whole walls
            nxy2 = np.minimum(out['n20_x'] * out['n20_x'] + out['n20_y'] * out['n20_y'], F(0.9999))
            g20 = np.sqrt(nxy2 / (F(1) - nxy2))
            spi = np.clip((np.log10(a * np.maximum(g20, F(1e-3))) - F(lo)) / F(hi - lo), 0.0, 1.0).astype(F)
            out['spi'] = spi
            fo = o['fresh']
            dry = F(1) - _smooth(0.0, 0.3, water)
            bare = (F(1) - _smooth(self.P.cover_m[0], self.P.cover_m[1], cover)) * dry
            # (SURFACING_DESIGN.md 2.3 step 9) on ground under 30 degrees, faded over 25-35, stream power on bare
            # ground: scoured channel floors; on steeper ground only the slope over the rock's own threshold: failing
            # faces (stream power peaks at the pour-overs, where the varnish curtains hang). Both on the 20 m slope,
            # which means the same on every level (a hero level's own slope resolves faces steeper than Sc almost
            # everywhere, and lit whole walls)
            sl = fo.get('steep_deg', (25.0, 35.0))
            slope20 = np.degrees(np.arctan(g20))
            steep = _smooth(sl[0], sl[1], slope20)
            fresh = _smooth(fo['spi'][0], fo['spi'][1], spi) * bare * (F(1) - steep)
            if 'Sc' in f:
                over = slope20 - np.degrees(np.arctan(np.asarray(f['Sc'], F)))
                fresh = np.maximum(fresh, _smooth(fo['over_deg'][0], fo['over_deg'][1], over) * bare * steep)
            if 'wear_recent' in f:
                fresh = np.maximum(fresh, np.clip(np.asarray(f['wear_recent'], F), 0.0, 1.0))
            out['fresh'] = fresh.astype(F)
            tm['fresh'] = time.perf_counter() - t1

        # ---- step 12: pins
        t1 = time.perf_counter()
        for k, v in out.items():
            # a 'thick' map holds at most its encoding's t_max, clipped before the pins: a child's border is then
            # what its parent's image holds there (pinned to the unclipped parent, a 30 m snow-filled gully read
            # 5 m deeper at the child's edge than the parent's clipped 16 m beside it)
            s = MP.MAPS.get(k)
            if s is not None and s.encoding == 'thick' and s.t_max:
                np.minimum(v, F(s.t_max), out=v)
        if par is not None:
            self._pin(i, out, fD)
        keep['pinned'] = {k: v for k, v in out.items()}
        keep['fD'] = fD
        tm['pins'] = time.perf_counter() - t1
        tm['total'] = time.perf_counter() - t0
        self.keep[i] = keep
        if lv.parent is not None and lv.parent in self.keep:    # the grandparent's textures are done with
            gp_ = self.levels[lv.parent].parent
            if gp_ is not None and gp_ in self.keep:
                for k_ in ('tK', 'geo_rms', 'a_spec', 'sand'):
                    self.keep[gp_].pop(k_, None)
        self.times.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in tm.items()})
        return out

    # ---- pieces
    def _snowpack(self, i, hp, href, gx, gy, g, mk, par, keep):
        """Step 7: the snowpack on the padded cell grid, metres (SURFACING_DESIGN.md 2.3): the fall from the altitude
        against the snowline and from the northness, relaxed at the slip-off, melted by the climatological sun and
        below the line, and the larger of that and a second pass that flows along the drainage. Keeps the passes for
        the child."""
        o = self.o
        sn = o['snow']
        cell = float(self.levels[i].cell)
        line, band_m = float(o['snowline_m']), float(sn['band_m'])
        alt = hp + F(href + self.base)
        slope_deg = np.degrees(np.arctan(g))
        north = -gy / np.maximum(g, F(1e-12)) * _smooth(1.0, 3.0, slope_deg)
        fall = F(sn['depth_m']) * _smooth(line - band_m, line + band_m, alt + F(sn['aspect_m']) * north)
        nl = np.sqrt(F(1) + g * g)
        insol = np.maximum((-gx * F(self.sun[0]) - gy * F(self.sun[1]) + F(self.sun[2])) / nl, F(0))
        # melt: on slopes the sun strikes harder than flat ground (melt_sun_m where it strikes square on), and below
        # the snowline (melt_low_m at band_m under it): flat ground at the line keeps half the fall, so the pack's
        # edge sits at the line, where the masks' snow is 0.5 (melting by all sunlight and on both sides of the line
        # pushed it 150 m above)
        s_el = F(self.sun[2])
        melt = (F(sn['melt_sun_m']) * np.maximum(insol - s_el, F(0)) / max(F(1) - s_el, F(1e-3))
                + F(sn['melt_low_m']) * (F(1) - _smooth(line - band_m, line, alt)))
        # (a fresh fall on every level, plus what the parent gathered beyond its fall: as settle)
        keep['snow_fall'] = fall
        rest0 = fall if par is None else fall + np.maximum(
            self._inherit(i, 'snow_rest') - self._inherit(i, 'snow_fall'), F(0))
        rest = self._relax(hp, rest0, _tan(sn['slip_deg']), int(sn['passes']), float(sn['rate']), cell)
        keep['snow_rest'] = rest
        pack = np.maximum(rest - melt, F(0))
        if 'flow' in mk:
            flowp = self._pad(i, np.asarray(mk['flow'], F), 'flow_mask')
            keep['flow_mask'] = flowp
            wf = _smooth(sn['flow'][0], sn['flow'][1], flowp)
            rep = F(_tan(sn['slip_deg'])) + (F(_tan(sn['flow_deg'])) - F(_tan(sn['slip_deg']))) * wf
            flow0 = fall if (par is None or 'snow_flow' not in par) else fall + np.maximum(
                self._inherit(i, 'snow_flow') - self._inherit(i, 'snow_fall'), F(0))
            flowed = self._relax(hp, flow0, rep, int(sn['passes']), float(sn['rate']), cell)
            keep['snow_flow'] = flowed
            pack = np.maximum(pack, np.maximum(flowed - melt, F(0)))
        return np.ascontiguousarray(pack, F)

    def _catchment(self, i, f, keep):
        """The specific catchment (metres: the drainage area over the cell's width) on the padded cell grid, the
        larger of the level's own and its parent's there, so a hero level whose own routing loses a trunk keeps the
        water its parent sends down (the gullies' initiation reads it). 1e9 where the level has no drainage area."""
        lv = self.levels[i]
        cell = float(lv.cell)
        n, m = lv.n, MARGIN
        if 'A' not in f:
            a = np.full((n + 2 * m, n + 2 * m), F(1.0e9))
        else:
            own = (np.maximum(np.asarray(f['A'], F), F(cell * cell)) / F(cell)).astype(F)
            a = self._pad(i, own, 'a_spec')
            if lv.parent is not None and 'a_spec' in self.keep.get(lv.parent, {}):
                a = np.maximum(a, self._inherit(i, 'a_spec'))
        keep['a_spec'] = np.ascontiguousarray(a, F)
        return keep['a_spec']

    def _geo_gates(self, i, keep, octs):
        """The geometry gates (SURFACING_DESIGN.md 2.3, step 3) on the padded cell grid, float32 (N, N, 4): per
        crest scale s in GATE_SCALES_M, 1 where the level's own height is smooth at that scale and 0 where it already
        holds relief of a gully octave's size there: the RMS of crest's term at s (tanh((h - G_s h) / (tau s))) over
        a Gaussian of 2 s, past relief['geo']. An octave of wavelength lam the level's cells can hold reads the
        channel of s = lam / 4 (clamped to the scales; the next coarser scale where the level has no term at s). A
        level makes the scales whose window spans at most GATE_OWN_CELLS of its cells and takes the wider ones from
        its parent, as crest does. Only the channels the octave table reads are made; the rest are 1."""
        lv = self.levels[i]
        cell, n, m = float(lv.cell), lv.n, MARGIN
        N_ = n + 2 * m
        out = np.ones((N_, N_, 4), F)
        lo, hi = (float(v) for v in self.o['relief']['geo'])
        need = sorted({int(round(float(b))) for b in octs[0, 1::2, 3] if float(b) > -0.5})
        terms = keep.get('crest_terms')
        par = self.keep.get(lv.parent) if lv.parent is not None else None
        made = {}
        own = [c for c, s in enumerate(GATE_SCALES_M)
               if 2.0 * s / cell <= GATE_OWN_CELLS and terms is not None
               and np.isfinite(terms[CREST_SCALES_M.index(s)]).all()]
        if own:                                           # the squared terms blurred on the device, one per channel
            t2 = np.zeros((N_, N_, 4), F)
            sig = [0.0] * 4
            for c in own:
                t = np.asarray(terms[CREST_SCALES_M.index(GATE_SCALES_M[c])], F)
                t2[..., c] = t * t
                sig[c] = 2.0 * GATE_SCALES_M[c] / cell
            b = self.dev.read(self._blur4(self.dev.texture(t2), tuple(sig), fan=False))
            for c in own:
                made[c] = np.sqrt(np.maximum(b[..., c], F(0)))
        for c in range(len(GATE_SCALES_M)):
            if c not in made and par is not None and c in (par.get('geo_rms') or {}):
                made[c] = Gd.crop_upsample2(par['geo_rms'][c], *self._win(i), 'bilinear')
        keep['geo_rms'] = made
        for c in need:
            src = next((made[q] for q in range(c, len(GATE_SCALES_M)) if q in made), None)
            if src is not None:
                out[..., c] = F(1) - _smooth(lo, hi, src)
        return np.ascontiguousarray(out, F)

    def _crest_metres(self, i, tH, hp, par, keep):
        """crest at fixed metre scales (SURFACING_DESIGN.md 2.3, step 5): t_s = tanh((h - G_s h) / (tau s)) for s in
        CREST_SCALES_M, the mean over the scales of at least one cell. A level blurs the scales of 1 to 16 of its
        cells itself; a wider one comes from its parent's pass (upsampled), so a threshold on crest means the same in
        a hero window and on the main level. Keeps the padded terms for the child. Returns the window's crest."""
        lv = self.levels[i]
        cell, n, m = float(lv.cell), lv.n, MARGIN
        N_ = n + 2 * m
        S = CREST_SCALES_M
        terms = np.full((len(S), N_, N_), np.nan, F)
        own = [k for k, s in enumerate(S) if s >= cell * (1 - 1e-9) and s / cell <= 16.0 + 1e-9]
        for g in range(0, len(own), 4):
            ks = own[g:g + 4]
            sig = [S[k] / cell for k in ks] + [0.0] * (4 - len(ks))
            b = self.dev.read(self._blur4(tH, tuple(sig)))
            for c, k in enumerate(ks):
                terms[k] = np.tanh((hp - b[..., c]) / F(float(self.o['crest_tau']) * S[k]))
        if par is not None and 'crest_terms' in par:
            for k, s in enumerate(S):
                if k not in own and s >= cell * (1 - 1e-9):
                    terms[k] = Gd.crop_upsample2(par['crest_terms'][k], *self._win(i), 'bilinear')
        keep['crest_terms'] = terms
        use = [k for k, s in enumerate(S) if s >= cell * (1 - 1e-9) and np.isfinite(terms[k]).all()]
        if not use:
            return np.zeros((n, n), F)
        return np.clip(np.mean([_crop(terms[k], m, n) for k in use], axis=0), -1.0, 1.0).astype(F)

    def _dummy(self):
        return self.dev.texture(np.zeros((1, 1, 4), F))

    def _blur4(self, src, sig4, fan=True):
        """Four Gaussian blurs (their sigmas in texels; 0: a copy) as one RGBA texture, two dispatches: of src.x
        (fan) or of src's four channels each."""
        dev = self.dev
        shape = (src.height, src.width)
        a, b = dev.empty(shape, 4), dev.empty(shape, 4)
        sig = tuple(float(v) for v in sig4)
        dev.run(_K('blur'), {'src': src}, {'outB': a}, {'uSigma': sig, 'uDir': (1, 0), 'uFan': 1 if fan else 0})
        dev.run(_K('blur'), {'src': a}, {'outB': b}, {'uSigma': sig, 'uDir': (0, 1), 'uFan': 0})
        return b

    def _win(self, i):
        lv = self.levels[i]
        i0, j0, mc = lv.in_parent(self.levels)
        return i0 - MARGIN // 2 + MARGIN, j0 - MARGIN // 2 + MARGIN, mc + MARGIN

    def _inherit(self, i, key, kind='bilinear'):
        """The parent's padded field `key` on level i's whole padded grid (the child starts from it)."""
        lv = self.levels[i]
        return Gd.crop_upsample2(self.keep[lv.parent][key], *self._win(i), kind)

    def _relax(self, hp, d0, repose_tan, passes, rate, cell):
        """A loose layer d0 (metres) on the ground hp relaxed at `repose_tan` (a number or a per-cell array):
        solvers/detail.py's relax with the ground cohesive (its threshold out of reach). Returns the layer, metres."""
        from ..solvers import detail as DT
        from ..solvers import hydraulic as HYD
        shape = hp.shape
        bed = (hp / F(cell)).astype(F)
        b0 = ((hp + d0) / F(cell)).astype(F)
        sc = np.full(shape, HYD.BIG_TAN, F)
        rep = np.broadcast_to(np.asarray(repose_tan, F), shape)
        dl, _bed_rel, _net = DT.relax(b0, bed, sc, rep, passes, rate, backend=self.backend)
        return np.maximum(d0 + dl.astype(F) * F(cell), F(0)).astype(F)

    def top_octave(self):
        """(lam_top, o_top): the gully spectrum's top octave, the same on every level: the first world octave
        (GULLY_LAMBDA0_M x 2^-o) under relief['top_cells'] cells of the main level and relief['top_max_m']."""
        rp = self.o['relief']
        top = min(float(rp['top_cells']) * float(self.levels[self.main].cell), float(rp['top_max_m']))
        lam, o_ = GULLY_LAMBDA0_M, 0
        while lam > top * (1.0 + 1e-9):
            lam *= 0.5
            o_ += 1
        return lam, o_

    def _gully_octaves(self, i, texel):
        """The gully spectrum's octave table for a level (two texels per octave, float32 (1, 2 n, 4)), the gully
        filter's parameters (solvers/detail.py's GULLY: its soil mask and normalisation) and the spectrum's
        (relief). The octaves are keyed by world wavelength (SURFACING_DESIGN.md 2.3, step 3): octave o has
        lambda_o = GULLY_LAMBDA0_M x 2^-o, amplitude k lambda_o (k: relief['k'], or the gully stage's amplitude
        over its wavelength where a recipe sets them: self-similar) and the lattice offset of (seed + 4242, o), so a
        wavelength has the same lattice and pattern on a parent and a child. Every level evaluates the octaves from
        the terrain's top octave (top_octave) down to 2 texels: a level's own band alone (under 3 of its cells) was
        one or two octaves, a washboard on any ground the geometry left smooth (11-20). An octave of at least 3 cells
        could be in the level's height already, so it reads a geometry gate: its row's last value is the gate
        texture's channel (GATE_SCALES_M nearest lam / 4), else -1."""
        from ..solvers import detail as DT
        lv = self.levels[i]
        cell = float(lv.cell)
        sp, _ran = self.stage('gully', i)
        given = dict(sp, **(self.o.get('gully') or {}))
        gp = DT._params(DT.GULLY, given, 'gully')
        rp = dict(self.o['relief'])
        if 'steer' in given:
            rp['steer'] = float(gp['steer'])
        k_amp = (float(gp['amp_m']) / float(gp['wavelength_m'])
                 if (gp['amp_m'] is not None and gp['wavelength_m']) else float(rp['k']))
        x0p, y0p = lv.x0 - MARGIN * cell, lv.y0 - MARGIN * cell
        rows = []
        lam, o_ = self.top_octave()
        while lam >= 2.0 * texel * (1.0 - 1e-9) and len(rows) < 12:
            ox, oy = N.lattice_offset(self.seed + 4242, o_)
            bx, by = math.floor(x0p / lam), math.floor(y0p / lam)
            if abs(bx + ox) >= 1 << 24 or abs(by + oy) >= 1 << 24:
                raise ValueError('gully lattice base beyond float32 integers: world coordinates too large')
            ch = -1.0
            if lam >= 3.0 * cell * (1.0 - 1e-9):
                s = min(max(lam / 4.0, GATE_SCALES_M[0]), GATE_SCALES_M[-1])
                ch = float(min(range(len(GATE_SCALES_M)), key=lambda q: abs(math.log(GATE_SCALES_M[q] / s))))
            rows.append([(bx + ox, by + oy, x0p / lam - bx, y0p / lam - by), (1.0 / lam, k_amp * lam, 1.0, ch)])
            lam *= 0.5
            o_ += 1
        if not rows:                                      # a placeholder row (the table is a texture): no octave
            rows.append([(0.0, 0.0, 0.0, 0.0), (1.0 / GULLY_LAMBDA0_M, 0.0, 0.0, -1.0)])
        octs = np.zeros((1, 2 * len(rows), 4), F)
        for k, (a, b) in enumerate(rows):
            octs[0, 2 * k], octs[0, 2 * k + 1] = a, b
        return octs, gp, rp

    def _rock_relief(self, i, hg, texel, ND):
        """(texture or None, amplitude, rock slope, normal cap): solvers/detail.py's breakup strength evaluated on
        the detail grid as a level of that texel, so its relief D is the band of the rock noise and joints below
        what the level's cells hold. None where the level's own breakup stage already put that band in the height
        (a detail grid at the cell on a level the stage ran on)."""
        from ..solvers import detail as DT
        from ..solvers import fluvial as FL
        lv = self.levels[i]
        cell = float(lv.cell)
        sp, ran = self.stage('breakup', i)
        p = DT._params(DT.BREAKUP, {k: v for k, v in sp.items() if k in DT.BREAKUP}, 'breakup')
        p['bedding'] = None
        rock_deg = tuple(float(v) for v in p['rock_slope_deg'])
        cap = float(p['normal_cap'])
        if ran and abs(texel - cell) < 1e-9 * cell:
            return None, 1.0, rock_deg, cap
        v = SimpleNamespace(cell=texel, x0=lv.x0 - MARGIN * cell, y0=lv.y0 - MARGIN * cell, n=ND)
        terms, nt, bu = DT.breakup_terms(p, v, self.seed)
        ref = float(np.abs(terms[0, 0::3, 3]).sum()) * N.GRADIENT_STD
        if ref <= 1e-6:
            return None, 1.0, rock_deg, cap
        u = DT.breakup_uniforms(p, v, nt, bu)
        outB = self.dev.empty((ND, ND), 4)
        self.dev.run(FL.Inline('breakup', DT.breakup_source()), {'terms': self.dev.texture(terms), 'st': hg},
                     {'outB': outB}, u)
        return outB, ref, rock_deg, cap

    def _fill(self, i, hp, waterp, par, shift):
        """The level's filled, tilted surface on its padded grid (fill.glsl to its fixed point): (W float32, passes).
        Held: the padded grid's outer ring, at the ground. On a child the margin is its parents' terrain (MARGIN
        cells of it), so water leaves the window where that terrain takes it, as the level runner's fill on its own
        window lets it leave at the edge. (Holding a child's margin at the parent's filled surface dammed rivers: the
        coarser parent's surface over a river's exit stands a metre or two over the child's channel, and the fill
        flooded the valley floor behind it into a flat the routing spread the trunk across, a wedge 100 m wide.)"""
        dev = self.dev
        lv = self.levels[i]
        n, m = lv.n, MARGIN
        N_ = n + 2 * m
        z = (hp + waterp).astype(F)
        top = float(np.max(np.abs(z))) if z.size else 1.0
        eps = max(float(self.o['fill_slope']) * float(lv.cell), 4.0 * float(np.spacing(F(max(top, 1.0)))))
        zt = np.zeros((N_, N_, 4), F)
        zt[..., 0] = z
        W0 = np.full((N_, N_), BIG, F)
        held = T.on_edge((N_, N_))
        W0[held] = z[held]
        zt[..., 1] = held
        zT = dev.texture(zt)
        a, b = dev.texture(W0), dev.empty((N_, N_), 1)
        prev = None
        done = 0
        chunk = 256
        while done < 24 * N_:
            for _ in range(chunk):
                dev.run(_K('fill'), {'wT': a, 'zT': zT}, {'outW': b}, {'uEps': eps, 'uCap': float(self.o['fill_cap_m'])})
                a, b = b, a
            done += chunk
            cur = dev.read(a)[..., 0]
            if prev is not None and np.array_equal(prev, cur):
                break
            prev = cur
        return np.ascontiguousarray(prev if prev is not None else cur, F), done

    def _route(self, i, W, par):
        """A hero level's drainage area on its padded grid, the parent's specific catchment pinned in on the margin:
        (A float32, iterations). flow_weights and route_area are the level runner's kernels, the convergence test
        solvers/hydro.py's."""
        from ..solvers import hydro as HY
        dev = self.dev
        lv = self.levels[i]
        n, m, cell = lv.n, MARGIN, float(lv.cell)
        N_ = n + 2 * m
        p = float(self.o['flow_p'])
        tgt = np.zeros((N_, N_, 4), F)
        tgt[..., 0] = Gd.crop_upsample2(par['A'], *self._win(i), 'bilinear') * F(0.5)
        tgt[..., 1] = 1.0
        tgt[m:m + n, m:m + n, 1] = 0.0
        st = dev.texture(W)
        ws = dev.empty((N_, N_), 1)
        dev.run('flow_weights', {'st': st}, {'outW': ws}, {'uDx': cell, 'uP': p, 'uBound': T.BOUND_OPEN})
        outP = dev.empty((N_, N_), 1)
        dev.run(_K('pin_inflow'), {'st': st, 'wsumT': ws, 'tgtT': dev.texture(tgt)}, {'outP': outP},
                {'uDx': cell, 'uP': p, 'uBound': T.BOUND_OPEN})
        A_in = dev.read(outP)[..., 0]
        A, iters = HY.route_to_convergence(dev, W, cell, A0=np.maximum(tgt[..., 0], F(cell * cell)), A_in=A_in,
                                           bound=T.BOUND_OPEN, p=p)
        return np.maximum(A, F(cell * cell)).astype(F), iters

    def _drainage_masks(self, A, f, mk, lv):
        """flow, channels and wetness from a drainage area, with masks.py's formulas and the main tile's norms."""
        P, nr = self.P, self.norms
        cell = float(lv.cell)
        h = np.asarray(f['h'], np.float64)
        wd = M._water_depth(f, P, h)
        wet = _smooth(0.0, 0.3, wd) if wd is not None else np.zeros(A.shape, F)
        dry = F(1) - wet
        A = np.maximum(np.asarray(A, F), F(cell * cell))
        log_a = np.log10(A) - F(math.log10(cell))
        out = {}
        out['flow'] = np.clip((log_a - F(nr.flow_lo)) * F(1.0 / max(nr.flow_hi - nr.flow_lo, 1e-6)), 0.0, 1.0).astype(F)
        thr = P.channel_area_m2 if P.channel_area_m2 is not None else M.channel_area_for_cell(cell)
        lt = math.log10(thr)
        ch = _smooth(lt - 0.7, lt + 0.3, log_a + F(math.log10(cell))) * dry
        if 'sand' in f:
            ch = ch * (F(1) - _smooth(P.sand_swallows_m[0], P.sand_swallows_m[1], np.asarray(f['sand'], F)))
        out['channels'] = ch.astype(F)
        if 'slope' in mk:
            g = np.tan(np.radians(np.asarray(mk['slope'], F)))
        else:
            g = M._slope_tan(h, cell, P.wrap).astype(F)
        twi = log_a * F(math.log(10.0)) - np.log(np.maximum(g, F(1e-3)))
        tw = np.clip((twi - F(nr.twi_lo)) * F(1.0 / max(nr.twi_hi - nr.twi_lo, 1e-6)), 0.0, 1.0)
        out['wetness'] = np.maximum(tw, wet).astype(F)
        return out

    def _pin(self, i, out, fD):
        """Blend a level's new maps to its parent's across the border band: masks.pin_band, the cell-grid maps over
        16 cells, the detail maps over the same ground on their own grid. A map the parent took from the masks (its
        flow, wetness, channels on the main level) is read from there."""
        lv = self.levels[i]
        pk = self.keep[lv.parent]
        plv = self.levels[lv.parent]
        pmk = _masks(self.t, lv.parent)
        det = [k for k, v in out.items() if MP.MAPS.get(k) is not None and MP.MAPS[k].grid == 'detail'
               and v.shape[0] == lv.n * fD and k != 'grain']
        cellmaps = [k for k in out if k not in det and k != 'area']
        child = M.Masks(lv.cell, lv.x0, lv.y0, (lv.n, lv.n))
        parent = M.Masks(plv.cell, plv.x0, plv.y0, (plv.n, plv.n))
        for k in cellmaps:
            pv = pk['pinned'].get(k)
            if pv is None and k in pmk:
                pv = np.asarray(pmk[k], F)
            if pv is not None and pv.shape == (plv.n, plv.n):
                child[k] = out[k]
                parent[k] = pv
        M.pin_band(child, parent, BAND, skip=())
        pf = pk['fD']
        childD = M.Masks(lv.cell / fD, lv.x0, lv.y0, (lv.n * fD, lv.n * fD))
        parentD = M.Masks(plv.cell / pf, plv.x0, plv.y0, (plv.n * pf, plv.n * pf))
        for k in det:
            pv = pk['pinned'].get(k)
            if pv is not None:
                childD[k] = out[k]
                parentD[k] = pv
        M.pin_band(childD, parentD, BAND * fD, skip=())


def bake_levels(terrain, opts, log=print):
    """Bake every level, coarsest first: ([{map: float32 array}], info). The maps are the new ones (and flow,
    wetness and channels on hero levels), pinned to their parents across the border band; 'strata_dz' and 'src_dz'
    are the F family's metres (zs - h); 'area' is a hero level's re-routed drainage area (m^2)."""
    B = _Baker(terrain, opts, log)
    out = []
    t0 = time.perf_counter()
    for i in range(len(B.levels)):
        out.append(B.level(i))
        tm = B.times[-1]
        if log:
            log(f"[surface] level {i} {B.levels[i].role} {B.levels[i].n} cells @ {B.levels[i].cell:.4g} m: "
                f"{tm['total']:.2f} s (" + ', '.join(f'{k} {v}' for k, v in tm.items() if k != 'total') + ')')
    info = dict(seconds=round(time.perf_counter() - t0, 3), levels=B.times, backend=B.dev.name,
                detail=[detail_factor(lv, opts) for lv in B.levels],
                norms=dict(flow_lo=B.norms.flow_lo, flow_hi=B.norms.flow_hi, twi_lo=B.norms.twi_lo,
                           twi_hi=B.norms.twi_hi, spi=B.spi_norm),
                href=[B.keep[i]['href'] for i in range(len(B.levels))],
                snow=B.snow_on, wind=B.wind is not None,
                # each level's gully octaves (metres): D's relief holds these, from the terrain's top octave down to
                # two of the level's texels, so a reader can tell the part of it finer than its scans' tile
                relief_octaves=[B.octave_m.get(i, []) for i in range(len(B.levels))])
    info['maps'] = opts.get('maps', 'all')
    fills = [B.keep[i].get('fill') for i in range(len(B.levels))]
    B.keep.clear()
    return out, info, fills


__all__ = ['DEFAULTS', 'MARGIN', 'BAND', 'resolve_options', 'resolve_palette', 'terrain_constants', 'mask_params',
           'bake_key', 'code_hash', 'bake_levels', 'detail_factor']
