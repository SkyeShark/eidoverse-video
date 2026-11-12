"""real_place: real elevation data as the main tile (design section 5), refined below its pixel by the detail stages
on the hero levels. Its test is that the hero levels add detail without moving the landform.

    t = make_terrain('real_place', params={'dem': 'lauterbrunnen'}, focus=(480, 1640))
    t = make_terrain('real_place', params={'dem': 'C:/dems/my_place.json'})   # a reference-style DEM of your own

The DEM. A name is one of the references (blender/tests/terrain/reference/data, or the folders listed in the
EIDO_TERRAIN_DEMS environment variable): a 16-bit PNG and a JSON with the grid (a north-up square, pixel_size_m,
centred on the place), the height range, the source and its licence. A path names such a JSON (or its PNG); a .npy
of metres (row 0 north) needs pixel_m. Its _context files, where they exist, are the wider surround.

Levels. By default the main tile is the DEM: its extent and pixel count are the size and resolution (Lauterbrunnen:
8000 m at 1000 cells of 8 m), so the main level holds the DEM's own pixels. Context levels (as many as the surround
covers: context 4 for Lauterbrunnen's 32 km, 2 for Fuji's 120 km around 40) come from the surround harmonised to
the main DEM: inside the DEM's extent a level is the main DEM averaged to its cell; outside, the surround plus the
main-minus-surround difference along the DEM's edge, carried outward by a push-pull fill (long wavelengths travel
far, detail fades within a few cells) and faded to nothing over blend_m. So the rings meet without a step where the
two datasets disagree (resolution, vertical datum). The bed is the surface: a DEM does not tell rock from debris, so
the inherited ground counts as rock and only what the detail stages add is loose. The hero levels start from their
parent upsampled (Catmull-Rom) and then get the detail stages: fluvial refinement (mode 'refine': the landform is
held, detail grows below the parent's pixel), talus, rock breakup and hydraulic rills (packages 3 and 12); the level
runner skips a stage whose op is not registered yet.

Drainage. The masks read the drainage area A (flow, channels, wetness, vegetation); the level runner routes it to
convergence on every level after its stages, the parent's catchment entering each child at its edge.

Heights. Blender z is metres above the main DEM's lowest point (base 'min'), or above sea level (base 'sea', the
default when the place has sea); base_elevation_m is the datum height of z = 0, so altitude = z + base_elevation_m.
Water: a DEM carries a lake as its flat surface. Under each lake the ground is lowered into a bowl (lake_depth_m at
its deepest, reached lake_depth_m / 0.15 metres from the shore), the `water` field holds the depth, and the lake
meshes sit at the lake's level. The sea's floor drops the same way below sea level.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

from ..core.recipe import Knob, Recipe, Stage

_HERE = os.path.dirname(os.path.abspath(__file__))
_BLENDER = os.path.normpath(os.path.join(_HERE, '..', '..', '..'))
DEM_DIRS = [os.path.join(_BLENDER, 'tests', 'terrain', 'reference', 'data'),
            os.path.join(_BLENDER, 'tests', 'terrain', 'reference', 'data')]
LAKE_SLOPE = 0.15                 # the lake bowl's side: depth rises 0.15 m per metre from the shore
_CACHE = {}


# ------------------------------------------------------------------------------------------------ the data ---

def dem_dirs():
    extra = [d for d in os.environ.get('EIDO_TERRAIN_DEMS', '').split(os.pathsep) if d]
    return extra + [d for d in DEM_DIRS if os.path.isdir(d)]


def dem_names():
    """The reference DEMs on this machine."""
    out = set()
    for d in dem_dirs():
        out |= {f[:-5] for f in os.listdir(d) if f.endswith('.json') and not f.endswith('_context.json')}
    return sorted(out)


def _read_json_dem(path):
    """(heights in metres with row 0 south, meta, water mask with row 0 south or None) of a reference-style DEM."""
    from ..core.io import read_png
    with open(path, encoding='utf-8') as f:
        meta = json.load(f)
    v = read_png(os.path.join(os.path.dirname(path), meta['height_png']))
    if v.dtype != np.uint16 or v.ndim != 2:
        raise ValueError(f'{path}: the height PNG must be 16-bit greyscale')
    lo, hi = float(meta['height_min_m']), float(meta['height_max_m'])
    h = lo + v.astype(np.float64) * ((hi - lo) / 65535.0)
    water = None
    if meta.get('water_mask_png'):
        w = read_png(os.path.join(os.path.dirname(path), meta['water_mask_png']))
        water = np.ascontiguousarray(np.asarray(w if w.ndim == 2 else w[..., 0])[::-1])
    return np.ascontiguousarray(h[::-1]), meta, water


def _find(dem):
    """The JSON path of a DEM name or path."""
    if os.path.isfile(str(dem)):
        p = str(dem)
        if p.lower().endswith('.png'):
            js = os.path.splitext(p)[0] + '.json'
            if os.path.isfile(js):
                return js
        return p
    for d in dem_dirs():
        p = os.path.join(d, f'{dem}.json')
        if os.path.isfile(p):
            return p
    import difflib
    near = difflib.get_close_matches(str(dem), dem_names(), n=3, cutoff=0.4)
    raise KeyError(f'no DEM {dem!r}' + (f'; nearest: {", ".join(near)}' if near else
                                        f'; the references here: {", ".join(dem_names())}'))


class Dem:
    """A DEM loaded once per process: main (rows south first, metres), its grid, the surround, water."""

    def __init__(self, dem, pixel_m=0.0):
        path = _find(dem)
        if path.lower().endswith('.npy'):
            if not pixel_m:
                raise ValueError(f'real_place: {path} is a bare array: give its pixel_m')
            h = np.load(path).astype(np.float64)[::-1].copy()
            self.meta = dict(name=os.path.splitext(os.path.basename(path))[0], pixel_size_m=float(pixel_m),
                             rows=h.shape[0], cols=h.shape[1], landform='', title=path, water=[])
            self.h, self.water_mask = h, None
        else:
            self.h, self.meta, self.water_mask = _read_json_dem(path)
        self.name = self.meta.get('name') or os.path.splitext(os.path.basename(path))[0]
        self.pixel = float(self.meta['pixel_size_m'])
        rows, cols = self.h.shape
        if rows != cols:
            raise ValueError(f'real_place: {self.name} is {cols} x {rows}; the levels are square')
        self.n = rows
        self.side = rows * self.pixel
        self.x0 = self.y0 = -self.side / 2.0          # the reference grid: centred on the place, (0, 0) its centre
        self.ctx = None
        cpath = os.path.splitext(path)[0] + '_context.json'
        if os.path.isfile(cpath):
            hc, mc, _w = _read_json_dem(cpath)
            self.ctx = (hc, float(mc['pixel_size_m']), -hc.shape[1] * float(mc['pixel_size_m']) / 2.0)
        self.water = self.meta.get('water') or []
        self.sea = [w for w in self.water if w.get('kind') == 'sea']

    def base(self, mode):
        """The datum height of z = 0: the main DEM's lowest point ('min'), sea level ('sea'), or a number."""
        if mode == 'auto':
            mode = 'sea' if self.sea else 'min'
        if mode == 'min':
            return float(self.h.min())
        if mode == 'sea':
            return 0.0
        return float(mode)


def load(dem, pixel_m=0.0):
    key = (str(dem), float(pixel_m or 0.0))
    if key not in _CACHE:
        _CACHE[key] = Dem(dem, pixel_m)
    return _CACHE[key]


# --------------------------------------------------------------------------------------------- resampling ---

def _axis_weights(out0, out_cell, n_out, src0, src_cell, n_src):
    """(n_out, n_src) weights taking a source axis (pixels from src0, src_cell wide) to an output axis: the exact
    area-weighted average where the output cell is at least the source pixel, Catmull-Rom at the output centres
    where it is finer. Edges clamp."""
    W = np.zeros((n_out, n_src))
    rows = np.arange(n_out)
    if out_cell >= src_cell * (1 - 1e-9):
        a = (out0 + rows * out_cell - src0) / src_cell            # output cell k covers source [a_k, b_k)
        b = a + out_cell / src_cell
        for k in range(n_out):
            lo, hi = a[k], b[k]
            i0, i1 = int(math.floor(lo)), int(math.ceil(hi))
            for i in range(i0, i1):
                ov = min(hi, i + 1) - max(lo, i)
                if ov > 0:
                    W[k, min(max(i, 0), n_src - 1)] += ov
        W /= W.sum(1, keepdims=True)
        return W
    t = (out0 + (rows + 0.5) * out_cell - src0) / src_cell - 0.5   # fractional source index of each centre
    i = np.floor(t).astype(np.int64)
    f = t - i
    w = np.stack([((-0.5 * f + 1.0) * f - 0.5) * f, (1.5 * f - 2.5) * f * f + 1.0,
                  ((-1.5 * f + 2.0) * f + 0.5) * f, (0.5 * f - 0.5) * f * f], 1)
    for q, o in enumerate((-1, 0, 1, 2)):
        np.add.at(W, (rows, np.clip(i + o, 0, n_src - 1)), w[:, q])
    return W


def resample(src, src0, src_cell, x0, y0, cell, n):
    """A square source grid (row 0 south, corner (src0, src0)) on a level's (n, n) cell grid: box-averaged to coarser
    cells, Catmull-Rom to finer ones."""
    Wx = _axis_weights(x0, cell, n, src0, src_cell, src.shape[1])
    Wy = _axis_weights(y0, cell, n, src0, src_cell, src.shape[0])
    return Wy @ np.asarray(src, np.float64) @ Wx.T


def push_pull(v, w):
    """Fill the cells where w == 0 from those where w == 1 smoothly: a pyramid of weighted 2 x 2 averages, then back
    down, each level filling its holes from the one above (bilinear). Long wavelengths reach far, short ones fade
    within a few cells of the data."""
    v = np.asarray(v, np.float64)
    w = np.clip(np.asarray(w, np.float64), 0.0, 1.0)
    ny, nx = v.shape
    if ny <= 2 or nx <= 2 or w.min() >= 1.0:
        tot = w.sum()
        return np.where(w > 0, v, (v * w).sum() / tot if tot > 0 else 0.0)
    py, px = ny % 2, nx % 2
    vp = np.pad(v * w, ((0, py), (0, px)))
    wp = np.pad(w, ((0, py), (0, px)))
    vs = vp.reshape(vp.shape[0] // 2, 2, vp.shape[1] // 2, 2).sum((1, 3))
    ws = wp.reshape(wp.shape[0] // 2, 2, wp.shape[1] // 2, 2).sum((1, 3))
    vc = np.where(ws > 0, vs / np.maximum(ws, 1e-300), 0.0)
    fc = push_pull(vc, np.minimum(ws, 1.0))
    p = np.pad(fc, 1, mode='edge')                              # x2 bilinear, cell-centred
    lo_r = 0.25 * p[:-2] + 0.75 * p[1:-1]
    hi_r = 0.75 * p[1:-1] + 0.25 * p[2:]
    r = np.empty((2 * fc.shape[0], fc.shape[1] + 2))
    r[0::2], r[1::2] = lo_r, hi_r
    lo_c = 0.25 * r[:, :-2] + 0.75 * r[:, 1:-1]
    hi_c = 0.75 * r[:, 1:-1] + 0.25 * r[:, 2:]
    up = np.empty((r.shape[0], 2 * fc.shape[1]))
    up[:, 0::2], up[:, 1::2] = lo_c, hi_c
    up = up[:ny, :nx]
    return v * w + up * (1.0 - w)


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _shore_distance(mask, cell, reach_m):
    """Metres from each cell inside `mask` to the nearest cell outside it, up to reach_m (an 8-neighbour chamfer
    distance, iterated)."""
    d = np.where(mask, np.inf, 0.0)
    steps = int(math.ceil(reach_m / cell)) + 1
    diag = math.sqrt(2.0) * cell
    for _ in range(steps):
        p = np.pad(d, 1, mode='edge')
        nd = np.minimum.reduce([d, p[:-2, 1:-1] + cell, p[2:, 1:-1] + cell, p[1:-1, :-2] + cell, p[1:-1, 2:] + cell,
                                p[:-2, :-2] + diag, p[:-2, 2:] + diag, p[2:, :-2] + diag, p[2:, 2:] + diag])
        if np.array_equal(nd, d):
            break
        d = nd
    return np.minimum(d, reach_m)


# ------------------------------------------------------------------------------------------------ the op ---

def ground(dem, x0, y0, cell, n, blend_m=2000.0):
    """The real ground on a level's grid (absolute metres, row 0 south): the main DEM inside its extent, the
    harmonised surround outside it (module doc). Returns (h, inside)."""
    xs = x0 + (np.arange(n) + 0.5) * cell
    inside_x = (xs >= dem.x0) & (xs <= dem.x0 + dem.side)
    ys = y0 + (np.arange(n) + 0.5) * cell
    inside_y = (ys >= dem.y0) & (ys <= dem.y0 + dem.side)
    inside = inside_y[:, None] & inside_x[None, :]
    hm = resample(dem.h, dem.x0, dem.pixel, x0, y0, cell, n)
    if inside.all() or dem.ctx is None:
        return hm, inside
    hc_src, pc, c0 = dem.ctx
    hc = resample(hc_src, c0, pc, x0, y0, cell, n)
    resid = push_pull(np.where(inside, hm - hc, 0.0), inside.astype(np.float64))
    dx = np.maximum(np.abs(xs - (dem.x0 + dem.side / 2)) - dem.side / 2, 0.0)
    dy = np.maximum(np.abs(ys - (dem.y0 + dem.side / 2)) - dem.side / 2, 0.0)
    dist = np.hypot(dy[:, None], dx[None, :])
    fade = 1.0 - _smoothstep(0.0, max(blend_m, cell), dist)
    return np.where(inside, hm, hc + resid * fade), inside


def _water(dem, h_abs, x0, y0, cell, n, lake_depth_m):
    """(ground lowered under the water, water depth) on a level's grid, from the DEM's water mask."""
    if dem.water_mask is None or not dem.water:
        return h_abs, None
    xs = x0 + (np.arange(n) + 0.5) * cell
    ys = y0 + (np.arange(n) + 0.5) * cell
    ci = np.clip(np.floor((xs - dem.x0) / dem.pixel).astype(int), 0, dem.n - 1)
    rj = np.clip(np.floor((ys - dem.y0) / dem.pixel).astype(int), 0, dem.n - 1)
    out_x = (xs < dem.x0) | (xs > dem.x0 + dem.side)
    out_y = (ys < dem.y0) | (ys > dem.y0 + dem.side)
    code = dem.water_mask[rj[:, None], ci[None, :]].astype(np.int64)
    code[out_y[:, None] | out_x[None, :]] = 0
    sea_level = dem.sea[0]['level_m'] if dem.sea else None
    if sea_level is not None and dem.ctx is not None:      # the surround: at or under sea level is sea
        code = np.where((code == 0) & (out_y[:, None] | out_x[None, :]) & (h_abs <= sea_level + 0.3), 255, code)
    h = h_abs.copy()
    depth = np.zeros_like(h)
    for wb in dem.water:
        m = code == int(wb.get('mask_value', 255))
        if not m.any():
            continue
        reach = lake_depth_m / LAKE_SLOPE
        d = _shore_distance(m, cell, reach)
        bowl = np.minimum(0.5 + LAKE_SLOPE * d, lake_depth_m)
        level = float(wb['level_m'])
        h[m] = np.minimum(h[m], level) - bowl[m]
        depth[m] = level - h[m]
    return h, depth


def op_dem(fields, level, params, seed=0):
    """Stage op 'dem': the level's h and water from the DEM, metres above the base (module doc). The bed is the
    surface (a DEM is rock or what lies on it; nothing tells them apart), so the hero levels' talus and fluvial
    refinement treat the inherited ground as rock and only what they add as loose."""
    cell = float(level.cell)
    dem = load(params['dem'], params.get('pixel_m', 0.0))
    x0, y0, n = float(level.x0), float(level.y0), int(level.n)
    h, _inside = ground(dem, x0, y0, cell, n, float(params.get('blend_m', 2000.0)))
    h, depth = _water(dem, h, x0, y0, cell, n, float(params.get('lake_depth_m', 30.0)))
    fields['h'] = h - dem.base(params.get('base', 'auto'))
    fields['bed'] = fields['h']
    if depth is not None:
        fields['water'] = depth


OPS = {'dem': op_dem}


# ----------------------------------------------------------------------------------------------- the recipe ---

def defaults_for(values):
    """The defaults that follow from the DEM: size and resolution (its extent and pixels), context (4 when it has a
    surround), the base elevation, the sea level, the palette and the mask parameters (build/palettes.PLACES, when
    the place is listed there)."""
    dem = load(values['dem'], values.get('pixel_m', 0.0))
    base = dem.base(values.get('base', 'auto'))
    context = None
    if dem.ctx is not None:                   # the largest power of two the surround covers (Fuji's 3 x: 2)
        ratio = dem.ctx[0].shape[0] * dem.ctx[1] / dem.side
        context = 2 ** int(math.floor(math.log2(ratio) + 1e-9)) if ratio >= 2 else None
    out = dict(size=dem.side, resolution=dem.n, context=context, hero_cell=0.5,
               base_elevation_m=base, centre=(0.0, 0.0), title=dem.meta.get('title', dem.name),
               landform=dem.meta.get('landform', ''), attribution=dem.meta.get('attribution', ''))
    if dem.sea:
        out['sea_level'] = float(dem.sea[0]['level_m']) - base
    try:
        from ..build import palettes as P
        if dem.name in P.PLACES:
            place = P.PLACES[dem.name]
            out['palette'] = place['palette']
            out['place'] = dem.name
            mp = dict(place.get('mask_params') or {})
            mp.pop('sea_level', None)                 # absolute there; the sea level above is in z's frame
            if place.get('strata'):                   # the strata mask as altitude: the material adds the place's
                mp['strata'] = dict(dip_deg=0.0)      # offset, faults and warp to it
            out['mask_params'] = mp
    except ImportError:
        pass
    return out


REAL_PLACE = Recipe(
    'real_place', 'Real elevation data as the main tile, refined by the detail stages below its pixel',
    references=['the DEM itself'],
    defaults={'hero_cell': 0.5},
    knobs={
        'dem': Knob('lauterbrunnen', 'name', None, 'a reference name (dem_names()) or the path of a DEM file'),
        'base': Knob('auto', 'choice', ('auto', 'min', 'sea'),
                     "z = 0 at the main DEM's lowest point ('min'), at sea level ('sea'); 'auto' is 'sea' where the "
                     "place has sea"),
        'blend_m': Knob(2000.0, 'm', (0.0, 1.0e6), 'how far outside the DEM its difference from the surround fades'),
        'lake_depth_m': Knob(30.0, 'm', (0.0, 2000.0), 'the deepest point of the bowl under each lake or the sea'),
        'pixel_m': Knob(0.0, 'm', (0.0, 1.0e4), 'the pixel of a bare .npy DEM (0 for the reference files)'),
    },
    stages=[
        Stage('dem', {'dem': '$dem', 'base': '$base', 'blend_m': '$blend_m', 'lake_depth_m': '$lake_depth_m',
                      'pixel_m': '$pixel_m'}, levels=['context', 'main']),
        Stage('fluvial', {'mode': 'refine'}, levels='hero', name='fluvial_refine'),
        Stage('talus', {'repose_deg': 35.0}, levels='hero'),
        Stage('breakup', {}, levels='hero'),
        Stage('hydraulic', {}, levels='hero'),
    ],
    doc='The main tile is the DEM; context levels are its surround harmonised to it; hero levels refine it. The '
        'hero stages (fluvial refinement, talus, rock breakup, hydraulic) belong to the fluvial and detail packages: '
        'pass their parameters through a recipe dict until their defaults are set here.')
REAL_PLACE.defaults_for = defaults_for

RECIPES = [REAL_PLACE]
