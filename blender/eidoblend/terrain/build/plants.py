"""Plant placement on the terrain (surfacing design section 4): an ecotope's rules (build/ecotopes.py) turned into
spots, the places where single plants stand: position, yaw, scale, age, species, individual and tint. Numpy only, no
bpy: build/plant_instances.py instances the spots in Blender, and the saved spots are a file a three.js placer reads.

    from eidoblend.terrain.build import plants as PL
    spots = PL.plan_plants(t, ecotope='auto', focus=(x, y), seed=0)      # t: a Terrain (make_terrain's)
    spots.names()                         # ['spruce', 'maple', 'meadow grass', ...]
    spots.array('spruce')                 # (n, 12) float32: x, y, z, yaw, scale, age, tint, nx, ny, nz, variant, level
    spots.field('spruce', 'scale')        # one column
    spots.stats['spruce']                 # candidates, kept, stems per hectare where the species is at home, ...
    spots.save('<dir>/valley')            # <dir>/valley.plants.json and valley.plants.<species>.f32
    spots = PL.PlantSpots.load('<dir>/valley', terrain=t)
    spots.cover('main')                   # {'canopy', 'canopy_expected', 'canopy_far', 'shrubs', 'shrubs_far'}
    sd.add_maps(spots.cover_extra())      # every level's rasters into the terrain's surface bake (sd: SurfaceData)
    PL.expected_cover(t)                  # with no plan: {'canopy_expected': [per level], 'canopy_far', 'shrubs', ...}

How a spot is placed, so the result can be trusted:
- candidates. The world is cut into square cells per species (4 x the species' mean spacing, at least 8 m), anchored
  at the world origin. A cell's cluster centres are a Poisson draw (cluster.parents_per_ha), each with a Poisson
  (cluster.mu) number of plants scattered sigma_m around it (a Thomas cluster process). Every draw is a hash of the
  cell, the species' name, the terrain's seed and the plan's: no generator state, so a cell gives the same candidates
  whatever is planned around it.
- density. A candidate is kept with probability density / (parents_per_ha x mu), the species' density expression
  (the rejection the rock scatter uses), times 1 - shade x (1 - tolerance) under the trees already placed. Every
  name a density reads is taken on the terrain's coarse levels (the main level in its tile, the context levels
  beyond it), so stems per hectare never step where a hero window begins (design 4.2): a hero level's steeper
  slopes, sharper curvatures and own drainage shape no density. It is dropped, on the finest level that holds the
  point, on water, settled snow, its own cell steeper than STEEP_DEG and deep talus or sand, and on the coarse levels'
  bare rock (ecotopes.py); and on a level coarser than the species' max_cell_m, inside a flatten area, or off the
  terrain.
- hard core. Species are placed in the order of their priority. A candidate is dropped within 0.75 x (its radius +
  the other's foot) of a plant placed earlier, and among the candidates of one priority the one with the smaller mark
  (a hash) wins wherever two stand closer than 0.75 x the sum of their radii: sequential inhibition in the order of
  the marks. That order does not depend on what is planned around a plant, and the planner checks it: every decision
  inside the planned radius is traced back to candidates it has generated (a decision that could change with
  candidates beyond the generated margin widens the margin and plans again). So the same inputs give the same bytes,
  and a larger radius or another focus keeps every plant already placed.
- size. An age from the species' Weibull, part of it shared by the cluster (a stand has an age); the height grows
  from size_m[0] to size_m[1] as 1 - exp(-3 age), times the species' stature where the site stunts it (krummholz
  toward the treeline); scale = height / size_m[1].
- the view. Of the spots so made, a plan returns those within the species' max_radius_m of the focus (a point or a
  path), at least lod_m_per_m x their distance tall, thinned out over the species' fade band at the radius' end.
  These three never move a plant: they only choose which ones a plan returns.
- on the ground. z is the terrain's height_at at the spot, and the normal its triangle's.

The saved format (the three.js contract, design 4.5): <base>.plants.json describes the frame, the terrain, the focus
and every species (its source, size range and count); <base>.plants.<species>.f32 holds its records, headerless
little-endian float32, FIELDS per spot. A plant's height is scale x size_m[1] metres; an instancer scales the
individual it grew (source seeds[variant]) to that height.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time

import numpy as np

from . import ecotopes as E
from . import palettes as P

FORMAT = 'eidoverse-terrain-plants/1'
FIELDS = ('x', 'y', 'z', 'yaw', 'scale', 'age', 'tint', 'nx', 'ny', 'nz', 'variant', 'level')
# names the density expressions may read beyond the masks and the surface bake's maps (ecotopes.py describes them)
DERIVED_NAMES = ('site', 'slope_20m', 'northness_20m', 'eastness_20m', 'soil', 'insolation', 'dist_channel',
                 'dist_water', 'fall_streak', 'shade', 'ledge')
STEEP_DEG = 60.0                    # no plant stands on its own cell steeper than this (unless it grows on rock)
# the cover rasters a plan gives the surface bake (PlantSpots.cover), of which cover_extra hands over those its map
# registry knows; and the kind of plant each cover kind counts
COVER_MAPS = ('canopy', 'canopy_expected', 'canopy_far', 'shrubs', 'shrubs_far', 'grass', 'grass_far')
COVER_KIND = {'tree': 'tree', 'shrub': 'shrub', 'grass': 'grass', 'forb': 'grass', 'groundcover': 'grass'}
CORE_FACTOR = 0.75                 # two plants stand no closer than this x the sum of their radii (flora's rule)
PAD_CORES = 12.0                    # the margin generated around a planned radius, in hard-core distances: a
                                    # decision inside the radius hangs on the margin's edge only through a chain of
                                    # that many neighbours of falling mark, which a plan practically never holds
DIST_CHANNEL_CAP_M = 400.0          # dist_channel reads at most this
DIST_WATER_CAP_M = 800.0            # dist_water reads at most this
SHADE_CHUNK = 1_000_000             # candidates per pass of the shade from the trees placed before (_shade_at)
STREAK_NOISE_M = 120.0              # fall_streak: the noise's feature size across the fall line, metres
STREAK_HALF_M = 240.0               # and how far it is smeared down and up the fall line from each point, metres
_FRAME = {
    'axes': 'x east, y north, z up, metres (Blender)',
    'three': 'position (x, z, -y)',
    'yaw': 'radians about +z, counter-clockwise from +x; three rotation.y = yaw',
    'size': 'a plant stands scale * size_m[1] metres tall: scale the grown individual (source seeds[variant]) to it',
    'normal': '(nx, ny, nz) the ground normal at the spot, unit, Blender axes; three (nx, nz, -ny)',
    'level': 'the index in terrain.levels of the finest level holding the spot',
}


# ----------------------------------------------------------------------------------------------- hashing ---
# Every random draw is a hash (splitmix64's finaliser over a chain of keys), turned into a uniform number: a world
# cell, a cluster or a plant draws the same numbers whatever else is planned.

_GOLD = np.uint64(0x9E3779B97F4A7C15)
_M1 = np.uint64(0xBF58476D1CE4E5B9)
_M2 = np.uint64(0x94D049BB133111EB)
_S30, _S27, _S31, _S11 = np.uint64(30), np.uint64(27), np.uint64(31), np.uint64(11)


def _mix(z):
    z = (z ^ (z >> _S30)) * _M1
    z = (z ^ (z >> _S27)) * _M2
    return z ^ (z >> _S31)


def _h(*keys):
    """A uint64 hash of a chain of integer keys (scalars or arrays, broadcast together)."""
    with np.errstate(over='ignore'):
        h = np.array([0x243F6A8885A308D3], np.uint64)
        for k in keys:
            k = np.asarray(k)
            if k.dtype != np.uint64:
                k = k.astype(np.int64).astype(np.uint64)
            h = _mix((h ^ np.atleast_1d(k)) + _GOLD)
        return h


def _u(h, stream):
    """Uniform numbers in [0, 1) from hashes, one independent set per stream number."""
    with np.errstate(over='ignore'):
        z = _mix(np.atleast_1d(h) + np.uint64(stream) * _GOLD + _M2)
    return (z >> _S11).astype(np.float64) * (1.0 / 9007199254740992.0)


def _name_key(name):
    return np.uint64(int.from_bytes(hashlib.sha1(str(name).encode('utf-8')).digest()[:8], 'little'))


def _poisson(mean, u):
    """Poisson(mean) numbers from uniforms, by inverting the distribution."""
    mean = float(mean)
    if mean <= 0.0:
        return np.zeros(np.shape(u), np.int64)
    kmax = int(mean + 12.0 * math.sqrt(mean) + 24.0)
    k = np.arange(kmax + 1, dtype=np.float64)
    logp = -mean + k * math.log(mean) - np.concatenate([[0.0], np.cumsum(np.log(np.arange(1, kmax + 1)))])
    return np.searchsorted(np.cumsum(np.exp(logp)), u, side='right').astype(np.int64)


def _ragged(counts):
    """(owner index, ordinal within the owner) of counts[i] items per owner i."""
    counts = np.asarray(counts, np.int64)
    owner = np.repeat(np.arange(len(counts)), counts)
    first = np.repeat(np.cumsum(counts) - counts, counts)
    return owner, np.arange(len(owner), dtype=np.int64) - first


def _smooth(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------------------------------- the ground ---

class _Level:
    __slots__ = ('index', 'role', 'x0', 'y0', 'side', 'cell', 'n')

    def __init__(self, index, lv):
        self.index = index
        if isinstance(lv, (list, tuple)):
            self.x0, self.y0, self.side, self.cell, self.n = (float(lv[0]), float(lv[1]), float(lv[2]), float(lv[3]),
                                                             int(lv[4]))
            self.role = str(lv[5]) if len(lv) > 5 else 'main'
        else:
            self.x0, self.y0, self.side, self.cell, self.n = (float(lv.x0), float(lv.y0), float(lv.side),
                                                             float(lv.cell), int(lv.n))
            self.role = str(getattr(lv, 'role', 'main'))

    def contains(self, x, y):
        return (x >= self.x0) & (x <= self.x0 + self.side) & (y >= self.y0) & (y <= self.y0 + self.side)

    def taps(self, x, y, n=None):
        """Bilinear taps of points on the texel centres of an n x n raster over this level's window (default its
        cells; a surface bake's detail maps are at half the cell), clamped to the outermost centres (the arithmetic
        of core.grid.sample_bilinear): four flat indices and the two weights."""
        n = self.n if n is None else int(n)
        texel = self.side / n
        fi = np.clip((x - self.x0) / texel - 0.5, 0.0, n - 1.0)
        fj = np.clip((y - self.y0) / texel - 0.5, 0.0, n - 1.0)
        i0 = np.minimum(np.floor(fi).astype(np.int64), max(n - 2, 0))
        j0 = np.minimum(np.floor(fj).astype(np.int64), max(n - 2, 0))
        i1, j1 = np.minimum(i0 + 1, n - 1), np.minimum(j0 + 1, n - 1)
        return j0 * n + i0, j0 * n + i1, j1 * n + i0, j1 * n + i1, fi - i0, fj - j0

    def as_list(self):
        return [self.x0, self.y0, self.side, self.cell, self.n]


class _Points:
    """World points located on the level stack: each on the finest level that holds it (the outermost level takes
    the rest, clamped), with its bilinear taps there."""

    def __init__(self, levels, x, y, only=None):
        self.x = np.asarray(x, np.float64)
        self.y = np.asarray(y, np.float64)
        n = len(self.x)
        self.n = n
        self.level = np.zeros(n, np.int16)
        self.parts = []
        todo = np.ones(n, bool)
        order = [i for i in range(len(levels) - 1, -1, -1) if only is None or i in only]
        for k, i in enumerate(order):
            lv = levels[i]
            inside = todo if k == len(order) - 1 else (todo & lv.contains(self.x, self.y))
            idx = np.nonzero(inside)[0]
            if len(idx):
                self.parts.append((i, idx) + lv.taps(self.x[idx], self.y[idx]))
                self.level[idx] = i
                todo[idx] = False

    def sample(self, levels, arrays):
        """Bilinear values of one map (arrays: per level a square array over the level's window, or None) at the
        points. A level without the map hands its points to the next coarser one that has it; None when no level has
        it."""
        if all(a is None for a in arrays):
            return None
        out = np.zeros(self.n, np.float64)
        for i, idx, k00, k10, k01, k11, ti, tj in self.parts:
            a = arrays[i]
            j = i
            if a is None:
                j = next((j for j in range(i - 1, -1, -1) if arrays[j] is not None), None)
                if j is None:
                    j = next(j for j in range(i + 1, len(arrays)) if arrays[j] is not None)
                a = arrays[j]
            a = np.asarray(a)
            if j != i or a.shape[0] != levels[j].n:
                k00, k10, k01, k11, ti, tj = levels[j].taps(self.x[idx], self.y[idx], a.shape[0])
            f = a.reshape(-1)
            out[idx] = ((f[k00] * (1.0 - ti) + f[k10] * ti) * (1.0 - tj)
                        + (f[k01] * (1.0 - ti) + f[k11] * ti) * tj)
        return out


class _GridPoints:
    """The texel centres of an m x m raster over level i's window, as located points (_Points' interface). A map of
    that level is read straight from its array: a texel centre of the raster is where the bilinear sample of a finer
    array lands on its block's middle (one texel, or the mean of the middle four), so this equals _Points' bilinear
    read, without its taps; anything else falls back to them."""

    def __init__(self, levels, i, m):
        lv = levels[i]
        c = (np.arange(m) + 0.5) * (lv.side / m)
        X, Y = np.meshgrid(lv.x0 + c, lv.y0 + c)
        self.x, self.y = X.ravel(), Y.ravel()
        self.n = len(self.x)
        self.level = np.full(self.n, i, np.int16)
        self._i, self._m = i, int(m)
        self._pts = None

    def sample(self, levels, arrays):
        a = arrays[self._i]
        if a is not None:
            a = np.asarray(a)
            r = a.shape[0] / self._m
            if r >= 1 and r == int(r) and a.shape[0] == a.shape[1]:
                r, m = int(r), self._m
                if r == 1:
                    return a.reshape(-1).astype(np.float64)
                b = a.reshape(m, r, m, r)
                if r % 2:
                    return b[:, r // 2, :, r // 2].reshape(-1).astype(np.float64)
                h = r // 2
                return b[:, h - 1:h + 1, :, h - 1:h + 1].astype(np.float64).mean((1, 3)).reshape(-1)
        if self._pts is None:
            self._pts = _Points(levels, self.x, self.y, only={self._i})
        return self._pts.sample(levels, arrays)


def _upsample(a, m):
    """A k x k raster (texel centres over a window) bilinearly resampled to m x m over the same window."""
    k = a.shape[0]
    if k == m:
        return a
    if k == 1:
        return np.full((m, m), float(a[0, 0]))
    t = np.clip((np.arange(m) + 0.5) * (k / m) - 0.5, 0.0, k - 1.0)
    i0 = np.minimum(np.floor(t).astype(np.int64), k - 2)
    w = (t - i0)[None, :]
    rows = a[:, i0] * (1.0 - w) + a[:, i0 + 1] * w                  # along x
    w = (t - i0)[:, None]
    return rows[i0, :] * (1.0 - w) + rows[i0 + 1, :] * w           # along y


def _normal_20m(h, cell):
    """(nx, ny) of the normal of a level's height raster blurred at 20 m, as the surface bake makes n20: the
    masks' Gaussian (a periodic FFT) over the raster padded by reflection out to 4 sigma, then central differences."""
    from .. import masks as _masks
    h = np.asarray(h, np.float64)
    s = 20.0 / float(cell)
    hb = h
    if s > 0.25:
        m = min(int(math.ceil(4.0 * s)) + 2, h.shape[0] - 1, h.shape[1] - 1)
        mu = float(h.mean())
        hb = np.asarray(_masks.gaussian_blur(np.pad(h - mu, m, mode='reflect'), s), np.float64)[m:-m, m:-m] + mu
    gy, gx = np.gradient(hb, float(cell))
    L = np.sqrt(1.0 + gx * gx + gy * gy)
    return -gx / L, -gy / L


def terrain_constants(terrain):
    """The terrain constants (palettes.CONSTANTS) of a Terrain: its base elevation, its snowline and treeline from
    its recipe's mask parameters, its real place's (palettes.PLACES) or its knobs, and a real place's latitude: what
    surfacing.terrain_constants reads off the object, read off the Terrain."""
    info = getattr(terrain, 'info', None) or {}
    knobs = getattr(terrain, 'knobs', None) or {}
    out = {}
    if info.get('base_elevation_m') is not None:
        out['base_elevation_m'] = float(info['base_elevation_m'])
    mp = {}
    R = getattr(terrain, 'recipe', None)
    dfl = dict(getattr(R, 'defaults', None) or {})
    if getattr(R, 'defaults_for', None) is not None:
        try:
            dfl.update(R.defaults_for(knobs))
        except Exception:                                # a recipe whose defaults need what the Terrain no longer has
            pass
    mp.update(dfl.get('mask_params') or {})
    place = info.get('place') or knobs.get('dem')
    if isinstance(place, str) and place in P.PLACES:
        mp.update(P.PLACES[place].get('mask_params') or {})
        if P.PLACES[place].get('latitude_deg') is not None:          # the place's climatological sun
            out['latitude_deg'] = float(P.PLACES[place]['latitude_deg'])
    for key in ('snowline_m', 'treeline_m'):
        if knobs.get(key) is not None:
            mp[key] = knobs[key]
        if mp.get(key) is not None:
            out[key] = float(mp[key])
    return out


class _Ground:
    """What the planner reads of a terrain: its levels, each level's maps (its masks; with a surface bake, everything
    SurfaceData.maps gives a level: the masks, the bake's maps with its own drainage on hero levels, the plant
    rasters and the derived insolation), the planner's derived names, heights and normals, and the constants.
    Two reads: site() takes a name on the coarse levels, the one level every density reads (the module doc), and
    at() on the finest level holding each point, for the exclusions."""

    def __init__(self, terrain, data=None, constants=None):
        self.levels = [_Level(i, lv) for i, lv in enumerate(terrain.levels)]
        self.data = data
        self._terrain = terrain
        if data is not None:
            self.stack = [data.maps(i) for i in range(len(self.levels))]
        else:
            masks = terrain.masks
            if hasattr(masks, 'level'):
                self.stack = [masks.level(i) for i in range(len(self.levels))]
            else:
                self.stack = list(masks)
        self.height_at = terrain.height_at
        self._normal_at = getattr(terrain, 'normal_at', None)
        self.constants = dict(E.CONSTANTS)
        self.constants.update(constants or {})
        self._coarse = [lv.index for lv in self.levels if lv.role != 'hero'] or [0]
        self._dist = None
        self._distw = None
        self._streak = None
        self._n20 = None
        self._site = P.parse(E.SITE)
        self.notes = []
        lv0 = self.levels[0]
        self.bounds = (lv0.x0, lv0.y0, lv0.x0 + lv0.side, lv0.y0 + lv0.side)

    # points ------------------------------------------------------------------------------------------------
    def locate(self, x, y):
        return _Points(self.levels, x, y)

    def coarse(self, pts):
        """The points located on the coarse levels (kept on the points: one location per set of points)."""
        cp = getattr(pts, '_coarse', None)
        if cp is None:
            cp = _Points(self.levels, pts.x, pts.y, only=set(self._coarse))
            pts._coarse = cp
        return cp

    def site(self, pts, name, shade=None, memo=None):
        """A name as every density reads it: on the coarse levels (the main level in its tile, the context levels
        beyond), whatever level holds the point, so a density never steps at a hero window's edge; the 20 m slope
        and aspect, `site`, `soil` and `insolation` are made from such reads too. memo: a dict that keeps what was
        read (the expressions of one set of points share it). None when the terrain has none (it reads 0)."""
        memo = {} if memo is None else memo
        if name in memo:
            return memo[name]

        def get(n):
            return self.site(pts, n, shade, memo)
        if name == 'shade':
            v = shade if shade is not None else np.zeros(pts.n)
        elif name == 'site':
            v = np.asarray(P.evaluate(self._site, get, pts.x, pts.y, self.constants), np.float64) * np.ones(pts.n)
        elif name in ('slope_20m', 'northness_20m', 'eastness_20m'):
            cp = self.coarse(pts)
            n20 = self.n20()
            nx = cp.sample(self.levels, [None if a is None else a[0] for a in n20])
            ny = cp.sample(self.levels, [None if a is None else a[1] for a in n20])
            g2 = np.minimum(nx * nx + ny * ny, 0.9999)
            slope = np.degrees(np.arctan(np.sqrt(g2 / (1.0 - g2))))
            fade = _smooth(1.0, 3.0, slope) / np.maximum(np.sqrt(g2), 1e-12)
            memo['slope_20m'], memo['northness_20m'], memo['eastness_20m'] = slope, ny * fade, nx * fade
            v = memo[name]
        elif name == 'insolation':                       # the place's climatological sun on the 20 m normal
            v = self._insolation(get('slope_20m'), get('northness_20m'), get('eastness_20m'), pts.n)
        elif name == 'soil':
            v = self._soil(get, pts.n, get('slope_20m'))
        elif name == 'dist_channel':
            v = self.coarse(pts).sample(self.levels, self.dist_channel())
        elif name == 'dist_water':
            v = self.coarse(pts).sample(self.levels, self.dist_water())
        elif name == 'fall_streak':
            v = self.coarse(pts).sample(self.levels, self.fall_streak())
        elif name == 'ledge':
            v = None
        else:
            v = self.coarse(pts).sample(self.levels, [m.get(name) for m in self.stack])
        memo[name] = v
        return v

    def n20(self):
        """Per level the 20 m normal's x and y (None on hero levels, which a density never reads): the surface
        bake's n20 where the data holds it, else the normal of the level's height blurred at 20 m (the bake's own
        rule), else the masks' slope and aspect of the level's cells."""
        if self._n20 is None:
            out = [None] * len(self.levels)
            for i in self._coarse:
                m, lv = self.stack[i], self.levels[i]
                if m.get('n20_x') is not None and m.get('n20_y') is not None:
                    out[i] = (np.asarray(m['n20_x'], np.float64), np.asarray(m['n20_y'], np.float64))
                    continue
                h = None
                fields = getattr(self._terrain, 'fields', None)
                if fields is not None:
                    try:
                        h = np.asarray(fields(i)['h'], np.float64)
                    except (KeyError, IndexError, TypeError, AttributeError):
                        h = None
                if h is not None and h.shape == (lv.n, lv.n):
                    out[i] = _normal_20m(h, lv.cell)
                elif m.get('slope') is not None and m.get('aspect') is not None:
                    t = np.tan(np.radians(np.asarray(m['slope'], np.float64)))
                    a = np.radians(np.asarray(m['aspect'], np.float64))
                    L = np.sqrt(1.0 + t * t)
                    out[i] = (t * np.sin(a) / L, t * np.cos(a) / L)
            if all(a is None for a in out):
                lv = self.levels[self._coarse[-1]]
                out[self._coarse[-1]] = (np.zeros((lv.n, lv.n)), np.zeros((lv.n, lv.n)))
                self.notes.append('no height, n20 or slope on the coarse levels: densities read flat ground')
            self._n20 = out
        return self._n20

    def _soil(self, get, n, slope):
        """Loose cover the roots hold in: deposit + talus + sand, more in hollows (-crest) and, on slopes, where the
        bake's settle gathered it (settle reads 0.5, unmoved, on gentle ground)."""
        parts = [get(k) for k in ('deposit', 'talus', 'sand')]
        v = sum((p for p in parts if p is not None), np.zeros(n))
        crest, settle = get('crest'), get('settle')
        if crest is not None:
            v = v * (1.0 + np.clip(-crest, 0.0, 1.0))
        if settle is not None:
            k = _smooth(10.0, 20.0, slope) if slope is not None else np.ones(n)
            v = v * (1.0 + k * (2.0 * settle - 1.0))
        return v

    def normal_at(self, x, y):
        if self._normal_at is not None:
            try:
                n = np.asarray(self._normal_at(x, y, smooth=False), np.float64)
            except TypeError:
                n = np.asarray(self._normal_at(x, y), np.float64)
            return n.reshape(-1, 3)
        e = 0.5
        dzx = (np.asarray(self.height_at(x + e, y)) - np.asarray(self.height_at(x - e, y))) / (2 * e)
        dzy = (np.asarray(self.height_at(x, y + e)) - np.asarray(self.height_at(x, y - e))) / (2 * e)
        n = np.stack([-dzx, -dzy, np.ones(len(x))], 1)
        return n / np.linalg.norm(n, axis=1, keepdims=True)

    def at(self, pts, name, shade=None):
        """One map or derived name at located points, on the finest level holding each (the exclusions' read): an
        array, or None when the terrain has none (it then reads 0, as the material's reader does). The 20 m terms,
        `site` and `dist_channel` are the coarse levels' (site())."""
        if name == 'shade':
            return shade if shade is not None else np.zeros(pts.n)
        if name in ('site', 'slope_20m', 'northness_20m', 'eastness_20m', 'dist_channel', 'dist_water',
                    'fall_streak'):
            return self.site(pts, name, shade)
        if name == 'soil':                               # loose cover, more in hollows and, on slopes, where the
            return self._soil(lambda n: self.at(pts, n), pts.n,          # bake's settle gathered it
                              self.at(pts, 'slope'))
        if name == 'ledge':
            return None
        v = pts.sample(self.levels, [m.get(name) for m in self.stack])
        if v is None and name == 'insolation':          # no bake: the same cosine, from the masks' slope and aspect
            v = self._insolation(self.at(pts, 'slope'), self.at(pts, 'northness'), self.at(pts, 'eastness'), pts.n)
        return v

    def _insolation(self, slope, north, east, n):
        """The cosine of the ground's normal with the place's climatological sun (palettes.climate_sun: its
        latitude's, unless the palette sets the sun), as the bake and the material read it; never a shot's sun."""
        az_deg, el_deg = P.climate_sun(self.constants)
        if slope is None:
            return np.full(n, max(math.sin(math.radians(el_deg)), 0.0))
        az = math.radians(az_deg)
        el = math.radians(el_deg)
        s = np.sin(np.radians(slope))
        north = 0.0 if north is None else north
        east = 0.0 if east is None else east
        dot = (s * east * math.cos(el) * math.sin(az) + s * north * math.cos(el) * math.cos(az)
               + np.cos(np.radians(slope)) * math.sin(el))
        return np.maximum(dot, 0.0)

    # level rasters -----------------------------------------------------------------------------------------
    def dist_channel(self):
        """Per level, metres to the nearest stream cell (None on hero levels, which read the main level's): the
        cells whose `flow` is at least channel_flow, or, with the constant channel_mask 1, whose `channels` mask is
        on where the level's cell is 7.6 m or more (finer levels' `channels` mark rills). A level takes its parent's
        distance where that is nearer, so a stream outside a window still counts."""
        if self._dist is None:
            out = [None] * len(self.levels)
            prev = None
            for i in self._coarse:
                lv, m = self.levels[i], self.stack[i]
                seed = np.zeros((lv.n, lv.n), bool)
                if m.get('flow') is not None:
                    seed |= np.asarray(m['flow']) >= self.constants['channel_flow']
                if m.get('channels') is not None and lv.cell >= 7.6 and self.constants.get('channel_mask', 1.0):
                    seed |= np.asarray(m['channels']) > 0.5
                d = _distance_to(seed, lv.cell, DIST_CHANNEL_CAP_M)
                if prev is not None:
                    X, Y = self._xy(lv)
                    pp = _Points(self.levels, X.ravel(), Y.ravel(), only={prev})
                    d = np.minimum(d, pp.sample(self.levels, out).reshape(lv.n, lv.n))
                out[i] = d.astype(np.float32)
                prev = i
            self._dist = out
        return self._dist

    def dist_water(self):
        """Per level, metres to the nearest standing or running water (`water` over 0.05 m), at most
        DIST_WATER_CAP_M, on the coarse levels as dist_channel is (a level takes its parent's distance where that is
        nearer)."""
        if self._distw is None:
            out = [None] * len(self.levels)
            prev = None
            for i in self._coarse:
                lv, m = self.levels[i], self.stack[i]
                w = m.get('water')
                seed = (np.asarray(w) > 0.05) if w is not None else np.zeros((lv.n, lv.n), bool)
                d = _distance_to(seed, lv.cell, DIST_WATER_CAP_M)
                if prev is not None:
                    X, Y = self._xy(lv)
                    pp = _Points(self.levels, X.ravel(), Y.ravel(), only={prev})
                    d = np.minimum(d, pp.sample(self.levels, out).reshape(lv.n, lv.n))
                out[i] = d.astype(np.float32)
                prev = i
            self._distw = out
        return self._distw

    def fall_streak(self):
        """Per level (the coarse levels; None on hero levels, which read the main level's) a 0..1 noise smeared along
        the fall line: a world-space value noise of STREAK_NOISE_M features averaged along each cell's streamline down
        and up the 20 m normal's slope for STREAK_HALF_M either way (a line integral convolution), so its values run
        in streaks down every slope, radial on a cone, and stay the noise itself on ground under 3 degrees. What the
        disturbances that shape a forest's upper edge follow (avalanche tracks, debris flows, lava tongues, fire
        runs): a treeline that reads it ends in tongues up and down the slope, not lobes (11-20: an isotropic wander
        left the stratovolcano's forest edge a level line over each face). The levels share one stretch (the main
        level's 5-95 % spread to 0.1-0.9), so a value means the same on each."""
        if self._streak is None:
            out = [None] * len(self.levels)
            n20 = self.n20()
            raw = {}
            for i in self._coarse:
                if n20[i] is None:
                    continue
                lv = self.levels[i]
                nx, ny = (np.asarray(a, np.float64) for a in n20[i])
                g = np.hypot(nx, ny)
                flat = g < math.sin(math.radians(3.0))
                ux = np.where(flat, 0.0, nx / np.maximum(g, 1e-12))
                uy = np.where(flat, 0.0, ny / np.maximum(g, 1e-12))
                n = nx.shape[0]                          # the normal's own grid over the level's window
                cell = lv.side / n
                c = (np.arange(n) + 0.5) * cell
                X, Y = np.meshgrid(lv.x0 + c, lv.y0 + c)
                noise = P.value_noise(X, Y, STREAK_NOISE_M, seed=71, octaves=3)
                step = max(cell, 12.0)
                k = max(int(round(STREAK_HALF_M / step)), 1)
                acc, cnt = noise.copy(), 1
                flat_n = noise.ravel()
                for sign in (1.0, -1.0):
                    px, py = X.copy(), Y.copy()
                    for _ in range(k):
                        # the fall line's direction at the nearest cell, one step along it
                        ii = np.clip(np.floor((px - lv.x0) / cell).astype(np.int64), 0, n - 1)
                        jj = np.clip(np.floor((py - lv.y0) / cell).astype(np.int64), 0, n - 1)
                        px = px + sign * step * ux[jj, ii]
                        py = py + sign * step * uy[jj, ii]
                        # the noise there, bilinear on the grid
                        fi = np.clip((px - lv.x0) / cell - 0.5, 0.0, n - 1.001)
                        fj = np.clip((py - lv.y0) / cell - 0.5, 0.0, n - 1.001)
                        i0, j0 = fi.astype(np.int64), fj.astype(np.int64)
                        ti, tj = fi - i0, fj - j0
                        k00 = j0 * n + i0
                        acc += ((flat_n[k00] * (1.0 - ti) + flat_n[k00 + 1] * ti) * (1.0 - tj)
                                + (flat_n[k00 + n] * (1.0 - ti) + flat_n[k00 + n + 1] * ti) * tj)
                        cnt += 1
                raw[i] = np.where(flat, noise, acc / cnt)
            if raw:
                main = next((i for i in self._coarse[::-1] if i in raw), None)
                lo, hi = np.percentile(raw[main], [5.0, 95.0])
                for i, a in raw.items():
                    out[i] = np.clip(0.1 + 0.8 * (a - lo) / max(hi - lo, 1e-6), 0.0, 1.0).astype(np.float32)
            else:
                self.notes.append('no 20 m normal on the coarse levels: fall_streak reads 0.5')
                lv = self.levels[self._coarse[-1]]
                out[self._coarse[-1]] = np.full((lv.n, lv.n), 0.5, np.float32)
            self._streak = out
        return self._streak

    @staticmethod
    def _xy(lv, step=1):
        """World (x, y) of a level's cell centres (of every step x step block of cells), as meshgrids."""
        c = (np.arange(0, lv.n, step) + 0.5 * step) * lv.cell
        return np.meshgrid(lv.x0 + c, lv.y0 + c)


def _distance_to(seed, cell, cap_m):
    """Metres from every cell to the nearest True cell of `seed`, at most cap_m, exactly: the squared distance to
    the nearest seed is the least over rows j' of (the distance along row j' to its nearest seed)^2 + (j - j')^2,
    and within the cap only the rows |j - j'| <= cap / cell count. A pass along the rows, then one shifted minimum
    per row offset."""
    ny, nx = seed.shape
    if not seed.any():
        return np.full(seed.shape, float(cap_m))
    R = int(math.ceil(cap_m / cell))
    idx = np.arange(nx)
    far = np.int64(nx + R + 2)
    left = np.maximum.accumulate(np.where(seed, idx, -far), axis=1)
    right = np.minimum.accumulate(np.where(seed, idx, 2 * far)[:, ::-1], axis=1)[:, ::-1]
    dx = np.minimum(np.minimum(idx - left, right - idx), R + 1).astype(np.float32)
    g = dx * dx
    best = g.copy()
    for dj in range(1, min(R, ny - 1) + 1):
        d2 = np.float32(dj * dj)
        np.minimum(best[dj:], g[:-dj] + d2, out=best[dj:])
        np.minimum(best[:-dj], g[dj:] + d2, out=best[:-dj])
    return np.minimum(np.sqrt(best.astype(np.float64)) * cell, float(cap_m))


# --------------------------------------------------------------------------------------- neighbour search ---

def _pairs(xa, ya, xb, yb, reach, chunk=2_000_000):
    """(i, j, distance) of every pair of a point of a and a point of b at most `reach` apart (a grid of reach-sized
    cells; no scipy in Blender's Python)."""
    na, nb = len(xa), len(xb)
    e = np.zeros(0, np.int64)
    if na == 0 or nb == 0 or reach <= 0.0:
        return e, e, np.zeros(0)
    x0 = min(float(xa.min()), float(xb.min()))
    y0 = min(float(ya.min()), float(yb.min()))
    g = float(reach)
    cax, cay = np.floor((xa - x0) / g).astype(np.int64), np.floor((ya - y0) / g).astype(np.int64)
    cbx, cby = np.floor((xb - x0) / g).astype(np.int64), np.floor((yb - y0) / g).astype(np.int64)
    W = int(max(cax.max(), cbx.max())) + 3
    kb = (cby + 1) * W + (cbx + 1)
    order = np.argsort(kb, kind='stable')
    uniq, start, count = np.unique(kb[order], return_index=True, return_counts=True)
    oi, oj, od = [], [], []
    r2 = g * g
    for s0 in range(0, na, chunk):
        sl = slice(s0, min(na, s0 + chunk))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                k = (cay[sl] + dy + 1) * W + (cax[sl] + dx + 1)
                pos = np.minimum(np.searchsorted(uniq, k), len(uniq) - 1)
                hit = uniq[pos] == k
                if not hit.any():
                    continue
                ia = np.nonzero(hit)[0]
                c = count[pos[hit]]
                rep, ordn = _ragged(c)
                jb = order[start[pos[hit]][rep] + ordn]
                ia = ia[rep] + s0
                d2 = (xa[ia] - xb[jb]) ** 2 + (ya[ia] - yb[jb]) ** 2
                m = d2 <= r2
                oi.append(ia[m])
                oj.append(jb[m])
                od.append(np.sqrt(d2[m]))
    if not oi:
        return e, e, np.zeros(0)
    return np.concatenate(oi), np.concatenate(oj), np.concatenate(od)


def _hard_core(x, y, r, rank, tainted):
    """Sequential inhibition in the order of `rank` (distinct integers): a candidate is accepted unless an accepted
    one of lower rank stands within CORE_FACTOR x the sum of the two radii. Returns (accepted, certain): certain says
    the decision follows from candidates that are all here. A tainted candidate may have neighbours that were not
    generated, so its acceptance, and whatever hangs on it, is not certain."""
    n = len(x)
    acc = np.zeros(n, bool)
    certain = np.zeros(n, bool)
    if n == 0:
        return acc, certain
    hard = r > 0.0
    acc[~hard] = True
    certain[~hard] = True
    hi = np.nonzero(hard)[0]
    if len(hi) == 0:
        return acc, certain
    i, j, d = _pairs(x[hi], y[hi], x[hi], y[hi], 2.0 * CORE_FACTOR * float(r[hi].max()))
    keep = (i < j) & (d < CORE_FACTOR * (r[hi][i] + r[hi][j]))
    i, j = hi[i[keep]], hi[j[keep]]
    src = np.concatenate([i, j])
    dst = np.concatenate([j, i])
    o = np.argsort(src, kind='stable')
    fsrc, fdst = src[o], dst[o]                          # the whole conflict graph, grouped by source
    und = hard.copy()
    src, dst = fsrc, fdst
    while und.any():
        has = np.zeros(n, bool)
        has[src] = True
        new = und & ~has                                 # no undecided neighbour left: accepted
        if len(src):
            nodes, first = np.unique(src, return_index=True)
            lowest = np.minimum.reduceat(rank[dst], first)
            new[nodes[rank[nodes] < lowest]] = True      # the lowest rank among its undecided neighbours
        acc |= new
        und &= ~new
        # certain: not tainted, and every lower-ranked neighbour (all rejected by now) certainly rejected
        ok = ~tainted & new
        e = new[fsrc]
        if e.any():
            es, ed = fsrc[e], fdst[e]
            fine = certain[ed] | (rank[ed] > rank[es])
            nodes2, first2 = np.unique(es, return_index=True)
            ok[nodes2] &= np.minimum.reduceat(fine.astype(np.uint8), first2).astype(bool)
        certain |= ok
        # their undecided neighbours are rejected: certainly so when a certain plant rejects them
        e = new[src]
        rej = np.zeros(n, bool)
        rej[dst[e]] = True
        sure = np.zeros(n, bool)
        sure[dst[e & certain[src]]] = True
        certain |= rej & sure
        und &= ~rej
        keep = und[src] & und[dst]
        src, dst = src[keep], dst[keep]
    return acc, certain


# ------------------------------------------------------------------------------------------- the planner ---

def _focus_points(focus):
    if focus is None:
        return None
    if hasattr(focus, 'location'):
        return np.array([[float(focus.location[0]), float(focus.location[1])]])
    if isinstance(focus, (list, tuple)) and focus and hasattr(focus[0], 'location'):
        return np.array([[float(f.location[0]), float(f.location[1])] for f in focus])
    a = np.asarray(focus, np.float64)
    if a.ndim == 1:
        a = a[None, :]
    if a.ndim != 2 or a.shape[1] < 2:
        raise ValueError(f'focus must be (x, y), a list of (x, y[, z]) or a camera; got shape {a.shape}')
    return a[:, :2].copy()


PATH_GAP_M = 600.0                  # a focus's consecutive points farther apart than this are separate views, not a path


def path_distance(focus, x, y):
    """Metres from points to the focus: a point, or the path through its points in order. Two consecutive points
    farther apart than PATH_GAP_M are not joined (no camera path jumps so far: such a list is a set of views, each
    planned around its own point; joined, two views 9 km apart planted a 9 km corridor of grass between them, 17
    million candidates, 11-20)."""
    f = np.asarray(focus, np.float64).reshape(-1, 2)
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    d = np.hypot(x - f[0, 0], y - f[0, 1])
    for a, b in zip(f[:-1], f[1:]):
        ab = b - a
        L2 = float(ab @ ab)
        if L2 > PATH_GAP_M * PATH_GAP_M:
            d = np.minimum(d, np.hypot(x - b[0], y - b[1]))
            continue
        if L2 <= 0.0:
            continue
        t = np.clip(((x - a[0]) * ab[0] + (y - a[1]) * ab[1]) / L2, 0.0, 1.0)
        d = np.minimum(d, np.hypot(x - (a[0] + t * ab[0]), y - (a[1] + t * ab[1])))
    return d


def _age_size(s, u_stand, u_own):
    """(age 0..1, height metres) of plants from their cluster's and their own uniform draws."""
    a = s['age']
    w = lambda u: float(a['scale']) * (-np.log1p(-np.minimum(u, 1.0 - 1e-12))) ** (1.0 / float(a['shape']))
    k = float(a.get('stand', 0.5))
    age = np.clip(k * w(u_stand) + (1.0 - k) * w(u_own), 0.02, 1.0)
    lo, hi = s['size_m']
    grow = (1.0 - np.exp(-3.0 * age)) / (1.0 - math.exp(-3.0))
    return age, lo + (hi - lo) * grow


def _cell_m(s):
    c = s['cluster']
    spacing = 1.0 / math.sqrt(max(c['parents_per_ha'] * c['mu'] / 1.0e4, 1e-12))
    return max(8.0, 4.0 * spacing)


def _candidates(s, keys, focus, reach, bounds):
    """Every candidate of species s whose cluster centre lies in a world cell within `reach` of the focus, as a dict
    of arrays (x, y, id, age, size, and the uniform draws the later steps use)."""
    c = _cell_m(s)
    cl = s['cluster']
    f = np.asarray(focus, np.float64).reshape(-1, 2)
    x0, y0 = max(f[:, 0].min() - reach, bounds[0] - c), max(f[:, 1].min() - reach, bounds[1] - c)
    x1, y1 = min(f[:, 0].max() + reach, bounds[2] + c), min(f[:, 1].max() + reach, bounds[3] + c)
    if x1 < x0 or y1 < y0:
        return None
    ix, iy = np.meshgrid(np.arange(math.floor(x0 / c), math.floor(x1 / c) + 1, dtype=np.int64),
                         np.arange(math.floor(y0 / c), math.floor(y1 / c) + 1, dtype=np.int64))
    ix, iy = ix.ravel(), iy.ravel()
    near = path_distance(f, (ix + 0.5) * c, (iy + 0.5) * c) <= reach + 0.7072 * c
    ix, iy = ix[near], iy[near]
    hc = _h(*keys, ix, iy)
    npar = _poisson(cl['parents_per_ha'] * 1.0e-4 * c * c, _u(hc, 1))
    ci, pj = _ragged(npar)
    hp = _h(hc[ci], pj)
    px = (ix[ci] + _u(hp, 2)) * c
    py = (iy[ci] + _u(hp, 3)) * c
    pi, ok = _ragged(_poisson(cl['mu'], _u(hp, 5)))
    ho = _h(hp[pi], ok)
    sig = float(cl['sigma_m'])
    rr = np.minimum(sig * np.sqrt(-2.0 * np.log1p(-_u(ho, 6))), 3.0 * sig)
    th = 2.0 * math.pi * _u(ho, 7)
    x = px[pi] + rr * np.cos(th)
    y = py[pi] + rr * np.sin(th)
    age, size = _age_size(s, _u(hp, 4)[pi], _u(ho, 8))
    return dict(x=x, y=y, id=ho, age=age, size=size, tone=0.6 * _u(hp, 9)[pi] + 0.4 * _u(ho, 10))


def _around(s, keys, parents, pcore):
    """Candidates of an `around` species: per plant of the species it grows around, a Poisson(per) number within
    radius x that plant's crown radius."""
    a = s['around']
    px, py, pscale = parents['x'], parents['y'], parents['scale']
    hp = _h(*keys, np.round(px * 100.0).astype(np.int64), np.round(py * 100.0).astype(np.int64))
    pi, ok = _ragged(_poisson(float(a.get('per', 2.0)), _u(hp, 1)))
    ho = _h(hp[pi], ok)
    rr = float(a.get('radius', 1.5)) * pcore * pscale[pi] * np.sqrt(_u(ho, 6))
    th = 2.0 * math.pi * _u(ho, 7)
    age, size = _age_size(s, _u(hp, 4)[pi], _u(ho, 8))
    return dict(x=px[pi] + rr * np.cos(th), y=py[pi] + rr * np.sin(th), id=ho, age=age, size=size,
                tone=0.6 * _u(hp, 9)[pi] + 0.4 * _u(ho, 10))


class _NeedMargin(Exception):
    pass


def _exclusions(s, ground, pts, site, fine, steep=True):
    """True where the species may stand: off water, settled snow, a cell steeper than STEEP_DEG (with steep) and
    talus or sand deeper than its roots, read on the finest level holding the point (fine), and off bare rock and
    the snow mask, read where its density is (site: the coarse levels)."""
    ok = np.ones(pts.n, bool)
    on = set(s['on'])
    if 'water' not in on:
        w = fine('water')
        if w is not None:
            ok &= w <= 0.05
    if 'snow' not in on:
        sp = fine('snowpack')                            # a surface bake's settled snow, metres
        if sp is not None:
            ok &= sp <= 0.2
        else:
            sn = site('snow')
            if sn is not None:
                ok &= sn <= 0.5
    if 'rock' not in on:
        ok &= np.asarray(P.evaluate(_BARE, site, pts.x, pts.y, ground.constants)) * np.ones(pts.n) <= 0.5
        if steep:
            sl = fine('slope')
            if sl is not None:
                ok &= sl <= STEEP_DEG
    for sub in ('talus', 'sand'):
        if sub not in on:
            v = fine(sub)
            if v is not None:
                ok &= v <= float(s['roots_m'])
    return ok


_BARE = P.parse('bare')


def _shade_at(x, y, casters, radius):
    """0..1 shade at points from the shade-casting plants placed so far: full within half of radius x a crown's
    radius of its trunk, none beyond radius x it; crowns add up as 1 - product(1 - s)."""
    if casters is None or len(casters['x']) == 0 or len(x) == 0:
        return np.zeros(len(x))
    reach = radius * casters['r']
    logs = np.zeros(len(x))
    for s0 in range(0, len(x), SHADE_CHUNK):          # in chunks: a dense undergrowth under a dense forest is tens
        s1 = min(len(x), s0 + SHADE_CHUNK)            # of millions of pairs, gigabytes at once (11-20)
        i, j, d = _pairs(x[s0:s1], y[s0:s1], casters['x'], casters['y'], float(reach.max()))
        s = 1.0 - _smooth(0.5 * reach[j], reach[j], d)
        keep = s > 0.0
        logs[s0:s1] = np.bincount(i[keep], weights=np.log1p(-np.minimum(s[keep], 1.0 - 1e-9)), minlength=s1 - s0)
    return 1.0 - np.exp(logs)


def plan_plants(terrain, ecotope='auto', focus=None, radius_m=None, seed=0, data=None, exclude=None, log=print):
    """The spots of an ecotope on a terrain (the module doc says how each is placed).

    terrain    a Terrain (make_terrain's): its levels, masks, height_at and normal_at are read
    ecotope    'auto' (the terrain's place's, recipe's or palette's: ecotopes.get), an ecotope name or dict
    focus      (x, y), [(x, y), ...] (a path) or a camera: where the plants are wanted; default the terrain's own
               focus, else the main level's centre. Each species is placed within its max_radius_m of it
    radius_m   a cap on every species' max_radius_m (None: each species' own)
    seed       the plan's seed (the terrain's own seed is hashed in too)
    data       the terrain's SurfaceData (terrain.surface.bake_surface), when there is one: every level's maps are
               read from it (SurfaceData.maps: the masks, the bake's maps with its own drainage on hero levels, the
               plant rasters), so the expressions read the material's data; without one, the masks alone (a bake
               map an expression names then reads 0)
    exclude    [(x, y, r), ...] discs kept clear; default the terrain's flatten areas. A disc given as
               (x, y, r, 'crown') keeps every plant's crown off it too (a plant's foot at least r plus its crown
               radius from the centre): a spot a person stands on, a camera at eye height
    Returns a PlantSpots."""
    t0 = time.perf_counter()
    info = getattr(terrain, 'info', None) or {}
    recipe = getattr(terrain, 'recipe', None)
    eco = _resolve(terrain, ecotope)
    consts = _constants(terrain, eco)
    ground = _Ground(terrain, data, consts)
    f = _focus_points(focus)
    if f is None:
        f = _focus_points(info.get('focus'))
    if f is None:
        main = next((lv for lv in ground.levels if lv.role == 'main'), ground.levels[-1])
        f = np.array([[main.x0 + 0.5 * main.side, main.y0 + 0.5 * main.side]])
    if exclude is None:
        exclude = [(fl['at'][0], fl['at'][1], float(fl.get('radius', 0.0)))
                   for fl in (getattr(terrain, 'flats', None) or []) if fl.get('radius')]
    tseed = int(info.get('seed') or 0)
    order = sorted(range(len(eco['species'])), key=lambda i: (eco['species'][i]['priority'], i))
    species = [dict(eco['species'][i]) for i in order]   # the planner's own copies: the ecotope stays as it is
    for s in species:
        s['_radius'] = min(float(s['max_radius_m']), float(radius_m)) if radius_m is not None \
            else float(s['max_radius_m'])
        s['_density'] = P.parse(s['density'])
        s['_stature'] = P.parse(s['stature']) if s.get('stature') is not None else None
    scale = 1.0
    for attempt in range(5):
        try:
            placed, stats = _plan(species, ground, f, tseed, int(seed), exclude, scale)
            break
        except _NeedMargin:
            scale *= 2.0
    else:
        raise RuntimeError('plan_plants: the hard-core margin did not settle after five widenings')
    out_species, arrays = [], {}
    for s in species:
        st = stats[s['name']]
        rec = _view(s, placed[s['name']], ground, f, st)
        arrays[s['name']] = rec
        st['count'] = int(len(rec))
        out_species.append(_species_record(s, len(rec), st))
    meta = dict(format=FORMAT, frame=dict(_FRAME),
                terrain=dict(cache_key=info.get('cache_key'), recipe=P._recipe_name(recipe) or info.get('recipe_name'),
                             seed=tseed, levels=[lv.as_list() for lv in ground.levels],
                             roles=[lv.role for lv in ground.levels]),
                focus=[[float(a), float(b)] for a, b in f], seed=int(seed),
                radius_m=None if radius_m is None else float(radius_m),
                ecotope=f"{eco['name']}#{E.ecotope_hash(eco)}", fields=list(FIELDS),
                constants={k: v for k, v in consts.items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
    spots = PlantSpots(meta, out_species, arrays, ground=ground, ecotope=eco)
    spots.seconds = round(time.perf_counter() - t0, 2)
    spots.notes = list(ground.notes)
    if log:
        parts = ', '.join(f"{s['name']} {s['count']:,}" for s in out_species) or 'no species'
        log(f"[plants] {eco['name']}: {parts} around ({f[0, 0]:.0f}, {f[0, 1]:.0f})"
            + (f' .. ({f[-1, 0]:.0f}, {f[-1, 1]:.0f})' if len(f) > 1 else '') + f' in {spots.seconds} s')
        for s in species:
            st = stats[s['name']]
            if st.get('clipped', 0.0) > 0.02:
                c = s['cluster']
                log(f"[plants] {s['name']}: its density asks for more than parents_per_ha x mu = "
                    f"{c['parents_per_ha'] * c['mu']:g} per ha at {100 * st['clipped']:.0f} % of its candidates "
                    f"(up to {st['density_max'] * 1e4:.0f} per ha): raise parents_per_ha or mu")
        for n in ground.notes:
            log('[plants] ' + n)
    return spots


def _resolved(ecotope):
    return isinstance(ecotope, dict) and bool(ecotope.get('species')) and 'priority' in ecotope['species'][0] \
        and 'cluster' in ecotope['species'][0] and isinstance(ecotope['species'][0].get('source'), tuple) \
        and len(ecotope['species'][0]['source']) == 4


def _plan(species, ground, f, tseed, seed, exclude, scale):
    """Every species' accepted plants within its exact radius of the focus: {name: dict of arrays}, and the stats."""
    groups = []
    for s in species:
        if not groups or groups[-1][0]['priority'] != s['priority']:
            groups.append([])
        groups[-1].append(s)
    # how far each group must be exact, and the margin it generates beyond that: later groups read the earlier
    # ones' plants (their feet, their shade, the plants they seed around) out to their own margins
    info = []
    for g in groups:
        core = max(float(s['core_m']) for s in g)
        spill = max(3.0 * float(s['cluster']['sigma_m']) for s in g)
        pad = scale * (PAD_CORES * 2.0 * CORE_FACTOR * core + 4.0) + spill
        info.append(dict(core=core, spill=spill, pad=pad, R=max(s['_radius'] for s in g), exact=0.0))
    for k in range(len(groups) - 1, -1, -1):
        need = info[k]['R']
        for j in range(k + 1, len(groups)):
            feet = max(float(s['foot_m']) for s in groups[k])
            crown = max(float(s['crown_m']) for s in groups[k])      # the shade and `around` reach crowns
            reach = CORE_FACTOR * (feet + info[j]['core'])
            reach = max(reach, max(float(s['shade']['radius']) for s in groups[j]) * crown)
            reach = max(reach, max((float(s['around'].get('radius', 1.5)) * crown for s in groups[j]
                                    if s.get('around')), default=0.0))
            need = max(need, info[j]['exact'] + info[j]['pad'] + reach + 1.0)
        info[k]['exact'] = need
    placed, stats = {}, {}
    feet = dict(x=np.zeros(0), y=np.zeros(0), r=np.zeros(0))       # the plants placed so far, with their foot radii
    casters = dict(x=np.zeros(0), y=np.zeros(0), r=np.zeros(0))    # and the shade-casting ones, with their crowns
    for g, gi in zip(groups, info):
        cands = []
        for s in g:
            keys = (np.int64(tseed), np.int64(seed), _name_key(s['name']))
            c = _candidates(s, keys, f, gi['exact'] + gi['pad'], ground.bounds)
            if s.get('around'):
                par = placed[s['around']['species']]
                pcore = float(next(x for x in species if x['name'] == s['around']['species'])['crown_m'])
                extra = _around(s, keys + (np.int64(77),), par, pcore)
                n_own = 0 if c is None else len(c['x'])
                c = extra if c is None else {k: np.concatenate([c[k], extra[k]]) for k in c}
                c['seeded'] = np.concatenate([np.zeros(n_own, bool), np.ones(len(extra['x']), bool)])
            st = stats[s['name']] = dict(candidates=0, after_density=0, kept=0, clipped=0.0, density_max=0.0,
                                         home_m2=0.0, home_count=0, per_ha_home=None)
            st['yield'] = 1.0
            placed[s['name']] = _empty()
            if c is None or len(c['x']) == 0:
                continue
            cands.append((s, _thin(s, c, ground, f, gi, exclude, feet, casters, st)))
        if not cands:
            continue
        x = np.concatenate([c['x'] for _s, c in cands])
        y = np.concatenate([c['y'] for _s, c in cands])
        r = np.concatenate([float(s['core_m']) * c['size'] / s['size_m'][1] for s, c in cands])
        ids = np.concatenate([c['id'] for _s, c in cands])
        mark = np.concatenate([c['mark'] for _s, c in cands])
        dist = np.concatenate([c['dist'] for _s, c in cands])
        rank = np.empty(len(x), np.int64)
        rank[np.lexsort((y, x, ids, mark))] = np.arange(len(x))
        tainted = dist > gi['exact'] + gi['pad'] - gi['spill'] - 2.0 * CORE_FACTOR * gi['core']
        acc, certain = _hard_core(x, y, r, rank, tainted)
        inside = dist <= gi['exact']
        if not certain[inside].all():
            raise _NeedMargin()
        keep = acc & inside
        o = 0
        for s, c in cands:
            n = len(c['x'])
            k = keep[o:o + n]
            o += n
            p = {key: v[k] for key, v in c.items()}
            p['scale'] = p['size'] / s['size_m'][1]
            placed[s['name']] = p
            st = stats[s['name']]
            own = p['dist'] <= s['_radius']
            st['kept'] = int(own.sum())
            st['home_count'] = int((p['home'] & own).sum())
            if st['home_m2'] > 0.0:
                st['per_ha_home'] = round(1.0e4 * st['home_count'] / st['home_m2'], 2)
            st['yield'] = round(float(own.sum()) / max(st['after_density'], 1), 4)
        for s in g:
            p = placed[s['name']]
            feet = dict(x=np.concatenate([feet['x'], p['x']]), y=np.concatenate([feet['y'], p['y']]),
                        r=np.concatenate([feet['r'], float(s['foot_m']) * p['scale']]))
            if s['casts_shade']:                         # a crown shades the ground under it: its crown radius
                casters = dict(x=np.concatenate([casters['x'], p['x']]), y=np.concatenate([casters['y'], p['y']]),
                               r=np.concatenate([casters['r'], float(s['crown_m']) * p['scale']]))
    return placed, stats


def _empty():
    z = np.zeros(0)
    return dict(x=z, y=z, id=np.zeros(0, np.uint64), age=z, size=z, tone=z, scale=z, dist=z, mark=z,
                home=np.zeros(0, bool), level=np.zeros(0, np.int16))


def _thin(s, c, ground, f, gi, exclude, feet, casters, st):
    """The candidates of a species that survive everything short of the hard core among their own priority: on the
    terrain, on a fine enough level, off the excluded ground, kept by the density and the shade, clear of the feet
    of the plants placed before."""
    x, y = c['x'], c['y']
    b = ground.bounds
    dist = path_distance(f, x, y)
    ok = (x >= b[0]) & (x <= b[2]) & (y >= b[1]) & (y <= b[3]) & (dist <= gi['exact'] + gi['pad'])
    for disc in exclude:
        ex, ey, er = (float(v) for v in disc[:3])
        reach = er
        if len(disc) > 3 and disc[3] == 'crown':        # a spot a person stands on: no crown over the disc either
            reach = er + float(s.get('crown_m', s['core_m'])) * c['size'] / float(s['size_m'][1])
        ok &= (x - ex) ** 2 + (y - ey) ** 2 > reach * reach
    c = {k: v[ok] for k, v in c.items()}
    dist = dist[ok]
    x, y = c['x'], c['y']
    pts = ground.locate(x, y)
    if s['max_cell_m'] is not None:
        cells = np.array([lv.cell for lv in ground.levels])[pts.level]
        fine = cells <= float(s['max_cell_m']) * (1.0 + 1e-9)
        c = {k: v[fine] for k, v in c.items()}
        dist = dist[fine]
        x, y = c['x'], c['y']
        pts = ground.locate(x, y)
    shade = _shade_at(x, y, casters, float(s['shade']['radius']))
    memo, fine_memo = {}, {}

    def getter(name):                                    # what a density, stature or `where` reads: the coarse levels
        return ground.site(pts, name, shade, memo)

    def fine(name):                                      # what an exclusion reads: the finest level holding the point
        if name not in fine_memo:
            fine_memo[name] = ground.at(pts, name, shade=shade)
        return fine_memo[name]
    if s['_stature'] is not None:                        # the height the site lets a plant reach (krummholz): before
        k = np.asarray(P.evaluate(s['_stature'], getter, x, y, ground.constants), np.float64) * np.ones(len(x))
        c['size'] = c['size'] * np.clip(k, 0.05, 1.0)    # the hard core, so stunted plants stand closer
    dmax = s['cluster']['parents_per_ha'] * s['cluster']['mu'] * 1.0e-4
    seeded = c.get('seeded')
    dens = np.maximum(np.asarray(P.evaluate(s['_density'], getter, x, y, ground.constants), np.float64), 0.0)
    if dens.ndim == 0:
        dens = np.full(len(x), float(dens))
    allowed = _exclusions(s, ground, pts, getter, fine)
    own = dist <= s['_radius']
    drawn = own if seeded is None else own & ~seeded     # the cluster process's own candidates, uniform over the ground
    st['candidates'] = int(own.sum())
    if drawn.any():
        st['density_max'] = float(dens[drawn].max())
        st['clipped'] = float((dens[drawn] > dmax * 1.0001).mean())
    prob = np.minimum(dens / dmax, 1.0)
    if seeded is not None and seeded.any():              # plants seeded around others: kept where `where` allows
        w = s['around'].get('where')
        pw = np.ones(len(x)) if w is None else np.clip(
            np.asarray(P.evaluate(P.parse(w), getter, x, y, ground.constants), np.float64) * np.ones(len(x)), 0, 1)
        prob = np.where(seeded, pw, prob)
    # the ground where the species is at home (its density at half its ceiling or more), measured by its own
    # candidates: their process is uniform at the ceiling, so their count over it is an area
    home = (dens >= 0.5 * dmax) & allowed
    st['home_m2'] = float((home & drawn).sum() / dmax)
    keep = allowed & (_u(c['id'], 11) < prob)
    st['after_density'] = int((keep & own).sum())
    keep &= _u(c['id'], 12) < 1.0 - shade * (1.0 - float(s['shade']['tolerance']))
    if len(feet['x']) and keep.any():
        ki = np.nonzero(keep)[0]
        rc = float(s['core_m']) * c['size'][ki] / s['size_m'][1]
        i, j, d = _pairs(x[ki], y[ki], feet['x'], feet['y'],
                         CORE_FACTOR * (float(feet['r'].max()) + float(rc.max())) + 1e-9)
        hit = d < CORE_FACTOR * (feet['r'][j] + rc[i])
        blocked = np.zeros(len(ki), bool)
        blocked[i[hit]] = True
        keep[ki[blocked]] = False
    out = {k: v[keep] for k, v in c.items() if k != 'seeded'}
    out['dist'] = dist[keep]
    out['mark'] = _u(out['id'], 13)
    out['home'] = home[keep]
    out['level'] = pts.level[keep]
    return out


KEPT_BINS = 48                      # distance bands of the kept-cover profile (_view), across a species' radius


def _kept_profile(d, w, idx, R):
    """The share of the placed plants' crown area (weights w) a view keeps (indices idx), per distance band of
    R / KEPT_BINS from the focus: what the instances carry of a species' cover, and so what the material's far
    cover must carry (1 - share). Bands holding no plant take their neighbours' share."""
    b = np.minimum((d / R * KEPT_BINS).astype(np.int64), KEPT_BINS)
    tot = np.bincount(b, weights=w, minlength=KEPT_BINS + 1)[:KEPT_BINS]
    got = np.bincount(b[idx], weights=w[idx], minlength=KEPT_BINS + 1)[:KEPT_BINS]
    ok = tot > 0.0
    if not ok.any():
        return [1.0] * KEPT_BINS
    c = np.arange(KEPT_BINS)
    share = np.interp(c, c[ok], got[ok] / tot[ok])
    return [round(float(v), 4) for v in share]


def _view(s, p, ground, f, st=None):
    """A species' records for the plan's focus: the placed plants within its radius, tall enough for their
    distance, thinned out over the fade band, capped at max_count; then heights and normals from the terrain. With
    st (its stats), records there the kept share of its crown area by distance (_kept_profile)."""
    n = len(p['x'])
    if n == 0:
        return np.zeros((0, len(FIELDS)), np.float32)
    R = s['_radius']
    d = p['dist']
    keep = (d <= R) & (p['size'] >= float(s['lod_m_per_m']) * d)
    f0, f1 = s['fade']
    if f1 > f0:
        keep &= _u(p['id'], 14) < 1.0 - _smooth(f0 * R, f1 * R, d)
    idx = np.nonzero(keep)[0]
    cap = s.get('max_count')
    if cap is not None and len(idx) > int(cap):
        # the smallest for their distance go first
        order = np.argsort(-(p['size'][idx] / np.maximum(d[idx], 1.0)), kind='stable')
        idx = np.sort(idx[order[:int(cap)]])
        ground.notes.append(f"{s['name']}: capped at max_count {int(cap):,} (the smallest and farthest dropped); a "
                            f"capped plan does not keep its spots when the radius grows")
    if st is not None:
        st['kept_area'] = _kept_profile(d, p['size'] ** 2, idx, R)
        st['kept_band_m'] = round(R / KEPT_BINS, 4)
    x, y = p['x'][idx], p['y'][idx]
    z = np.asarray(ground.height_at(x, y), np.float64).reshape(-1)
    nrm = ground.normal_at(x, y)
    nvar = max(len(s['source'][3]), 1)
    rec = np.empty((len(idx), len(FIELDS)), np.float32)
    rec[:, 0], rec[:, 1], rec[:, 2] = x, y, z
    rec[:, 3] = 2.0 * math.pi * _u(p['id'][idx], 15)
    rec[:, 4] = p['scale'][idx]
    rec[:, 5] = p['age'][idx]
    rec[:, 6] = p['tone'][idx]
    rec[:, 7:10] = nrm
    rec[:, 10] = np.minimum((_u(p['id'][idx], 16) * nvar).astype(np.int64), nvar - 1)
    rec[:, 11] = p['level'][idx]
    return rec


# the spot fields each Blender instancer turns into what it draws (design 4.6): flora's strokes take each spot's
# place and height, flora draws yaw and tint itself; SeedThree's still groves take yaw, the individual and the tint
# (each plant's own tone) too (its swaying grove, plant_instances with wind, all but the tint)
HONOURED = {'flora': ['x', 'y', 'z', 'scale'], 'ph': ['x', 'y', 'z', 'scale'],
            'seedthree': ['x', 'y', 'z', 'yaw', 'scale', 'variant', 'tint']}


def _species_record(s, count, st):
    rule = {k: v for k, v in s.items() if not k.startswith('_') and k != 'source'}
    return dict(name=s['name'], kind=s['kind'], source=E.source_dict(s['source']), honoured=HONOURED[s['source'][0]],
                size_m=[float(s['size_m'][0]), float(s['size_m'][1])], core_m=float(s['core_m']),
                crown_m=float(s['crown_m']), foot_m=float(s['foot_m']), cluster=E._jsonable(s['cluster']),
                sink=float(s['sink']),
                align=float(s['align']), lod=dict(s['lod']),
                ground=s['ground'], count=int(count), fields=list(FIELDS), rule=E._jsonable(rule), stats=dict(st))


def _file_part(name):
    return re.sub(r'[^A-Za-z0-9_-]+', '_', str(name)).strip('_') or 'species'


# ---------------------------------------------------------------------------------------------- the spots ---

class PlantSpots:
    """The spots of a plan: per species an (n, 12) float32 array of FIELDS, with what an instancer needs to know of
    each species (.species: name, kind, source, size_m, core_m, lod, count ...) and the plan's description (.meta).
    save / load round-trip the saved format; cover(level) gives the cover rasters the material reads."""

    def __init__(self, meta, species, arrays, ground=None, ecotope=None):
        self.meta = meta
        self.species = species
        self._arrays = arrays
        self._ground = ground
        self._ecotope = ecotope
        self.stats = {s['name']: s.get('stats', {}) for s in species}
        self.notes = []
        self.seconds = None

    def names(self):
        return [s['name'] for s in self.species]

    def __contains__(self, name):
        return name in self._arrays

    def __len__(self):
        return int(sum(len(a) for a in self._arrays.values()))

    def __repr__(self):
        return f"PlantSpots({self.meta.get('ecotope')}: " + ', '.join(
            f"{s['name']} {len(self._arrays[s['name']]):,}" for s in self.species) + ')'

    def entry(self, name):
        for s in self.species:
            if s['name'] == name:
                return s
        raise KeyError(f'no species {name!r}; the plan has {", ".join(self.names())}')

    def array(self, name):
        """The (n, 12) float32 records of a species: FIELDS per spot."""
        self.entry(name)
        return self._arrays[name]

    def field(self, name, field):
        return self.array(name)[:, FIELDS.index(field)]

    def count(self, name):
        return int(len(self.array(name)))

    # files -------------------------------------------------------------------------------------------------
    def save(self, base):
        """Write <base>.plants.json and one <base>.plants.<species>.f32 per species (headerless little-endian
        float32, FIELDS per spot). Returns the paths written, the JSON first."""
        base = _strip_ext(base)
        os.makedirs(os.path.dirname(os.path.abspath(base)) or '.', exist_ok=True)
        stem = os.path.basename(base)
        meta = dict(self.meta)
        out, used = [], set()
        entries = []
        for s in self.species:
            part = _file_part(s['name'])
            while part in used:
                part += '_'
            used.add(part)
            fn = f'{stem}.plants.{part}.f32'
            a = np.ascontiguousarray(self._arrays[s['name']], dtype='<f4')
            path = os.path.join(os.path.dirname(os.path.abspath(base)), fn)
            with open(path + '.tmp', 'wb') as fh:
                fh.write(a.tobytes())
            os.replace(path + '.tmp', path)
            out.append(path)
            entries.append(dict(s, count=int(len(a)), file=fn))
        meta['species'] = entries
        jpath = base + '.plants.json'
        with open(jpath + '.tmp', 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=1)
        os.replace(jpath + '.tmp', jpath)
        return [jpath] + out

    @classmethod
    def load(cls, base, terrain=None, data=None):
        """The spots save() wrote. With the terrain they were planned on, cover() works too."""
        base = _strip_ext(base)
        with open(base + '.plants.json', encoding='utf-8') as fh:
            meta = json.load(fh)
        if meta.get('format') != FORMAT:
            raise ValueError(f"{base}.plants.json: format {meta.get('format')!r}, this reads {FORMAT!r}")
        species = meta.pop('species')
        arrays = {}
        folder = os.path.dirname(os.path.abspath(base))
        for s in species:
            stride = len(s['fields'])
            a = np.fromfile(os.path.join(folder, s['file']), dtype='<f4')
            if len(a) != s['count'] * stride:
                raise ValueError(f"{s['file']}: {len(a)} numbers, the description says {s['count']} x {stride}")
            arrays[s['name']] = a.reshape(-1, stride).astype(np.float32)
        spots = cls(meta, species, arrays)
        if terrain is not None:
            spots.attach(terrain, data)
        return spots

    def attach(self, terrain, data=None):
        """Give loaded spots the terrain they were planned on, for cover(): read with the constants the plan read
        (saved in its description), else the terrain's."""
        consts = _constants(terrain)
        consts.update(self.meta.get('constants') or {})
        self._ground = _Ground(terrain, data, consts)
        return self

    # cover ---------------------------------------------------------------------------------------------------
    def _level_index(self, level):
        roles = self.meta['terrain'].get('roles') or ['main'] * len(self.meta['terrain']['levels'])
        n = len(roles)
        if isinstance(level, (int, np.integer)):
            return int(level) % n
        if level == 'first':
            return 0
        if level == 'last':
            return n - 1
        hit = [i for i, r in enumerate(roles) if r == level]
        if not hit:
            raise KeyError(f"level {level!r}: an index, 'main', 'context', 'hero', 'first' or 'last' ({roles})")
        return hit[0] if level == 'context' else hit[-1]

    def cover(self, level='main', max_n=1024, density_n=512):
        """The cover rasters of one level (an index or role, as Terrain.fields takes), row 0 south, at the level's
        cell (at most max_n across: a finer level is read every other cell). The expected covers are areal
        densities: they are evaluated on at most density_n x density_n points of the level and interpolated up (the
        palettes' noise on a million points per species is most of a level's cost); the placed crowns are drawn
        at full size:
          canopy            the placed tree crowns as discs, the fraction of each texel they cover
          canopy_expected   the cover the trees' densities imply, everywhere: 1 - exp(-sum density x the share a hard
                            core keeps x the mean crown area), from the rules alone (expected_cover gives the same
                            with no plan: one forest rule for the instances and the material)
          canopy_far        the part of it the plan did not instance: each tree species' cover times the share of
                            its crown area the plan left out at that distance from the focus or path (the fade band,
                            the smallest dropped by distance, a max_count cap: the plan's own kept_area profile); the
                            crowns the material draws beyond the instanced forest, so that canopy and canopy_far make
                            one forest (design 4.7)
          shrubs            the same as canopy_expected for the shrubs: the undergrowth's cover
          shrubs_far        and as canopy_far: the shrub cover the instanced shrubs leave to the material
          grass             the same for the grasses, forbs and ground cover (their tufts' crown_m): the sward
          grass_far         and the sward the instanced tufts leave to the material, past their radius
        Needs the terrain (a plan has it; loaded spots take it through load(base, terrain=) or attach)."""
        if self._ground is None:
            raise RuntimeError('cover() reads the terrain: PlantSpots.load(base, terrain=t), or spots.attach(t)')
        g = self._ground
        i = self._level_index(level)
        lv = g.levels[i]
        entries = {s['name']: s for s in self.species}
        rules = [dict(s['rule'], name=s['name'], kind=s['kind']) for s in self.species]
        m, step, k, expected, far = _level_cover(
            g, rules, i, max_n, density_n, kept=lambda name, d: self._kept_at(entries[name], d),
            focus=np.asarray(self.meta['focus'], np.float64).reshape(-1, 2))
        cell = lv.cell * step
        canopy = np.zeros((m, m))
        for s in self.species:
            if s['kind'] != 'tree' or not len(self._arrays[s['name']]):
                continue
            a = self._arrays[s['name']]
            _discs(canopy, (a[:, 0].astype(np.float64) - lv.x0) / cell, (a[:, 1].astype(np.float64) - lv.y0) / cell,
                   s.get('crown_m', s['core_m']) * a[:, 4].astype(np.float64) / cell)
        return dict(canopy=np.clip(canopy, 0.0, 1.0).astype(np.float32),
                    canopy_expected=_cover_raster(expected['tree'], k, m), canopy_far=_cover_raster(far['tree'], k, m),
                    shrubs=_cover_raster(expected['shrub'], k, m), shrubs_far=_cover_raster(far['shrub'], k, m),
                    grass=_cover_raster(expected['grass'], k, m), grass_far=_cover_raster(far['grass'], k, m))

    def _kept_at(self, entry, d):
        """The share of a species' crown area its instances carry at distances d from the focus: the plan's own
        profile (kept_area, per band of kept_band_m), 0 beyond its radius; none for a species the plan placed
        nowhere; for spots saved without a profile, its fade band."""
        st = entry.get('stats') or {}
        prof = st.get('kept_area')
        if prof:
            step = float(st['kept_band_m'])
            xp = np.append((np.arange(len(prof)) + 0.5) * step, step * len(prof))
            return np.interp(d, xp, np.append(np.asarray(prof, np.float64), 0.0), right=0.0)
        if not entry.get('count'):
            return np.zeros(len(d))
        rule = entry['rule']
        cap = self.meta.get('radius_m')
        R = float(rule['max_radius_m']) if cap is None else min(float(rule['max_radius_m']), float(cap))
        f0, f1 = (float(v) for v in rule['fade'])
        return 1.0 - (_smooth(f0 * R, f1 * R, d) if f1 > f0 else (d > R).astype(np.float64))

    def cover_extra(self, max_n=1024, density_n=512):
        """The cover rasters of every level in the form the surface bake takes as extra= (bake_surface, or
        SurfaceData.add_maps): {'canopy': [array per level], 'canopy_expected': [...], ...}, the rasters its map
        registry (surface.maps.MAPS) knows (grass and grass_far once it registers them)."""
        from ..surface.maps import MAPS as known
        names = [k for k in COVER_MAPS if k in known]
        out = {k: [] for k in names}
        for i in range(len(self.meta['terrain']['levels'])):
            c = self.cover(i, max_n, density_n)
            for k in out:
                out[k].append(c[k])
        return out


def _crown_and_scale(rule):
    """(mean crown area in m^2, mean scale) of a species' plants over its age distribution (24 x 24 quantiles of the
    stand's draw and the plant's own): what a density of stems covers, with no plan (the crown radius crown_m)."""
    u = (np.arange(24) + 0.5) / 24.0
    us, uo = np.meshgrid(u, u)
    _age, size = _age_size(rule, us.ravel(), uo.ravel())
    sc = size / float(rule['size_m'][1])
    crown = float(rule.get('crown_m', rule['core_m']))
    return float(np.mean(math.pi * (crown * sc) ** 2)), float(sc.mean())


def _kept_by_core(rule, dens, mean_scale):
    """The share of a density's candidates a hard core keeps, with no plan: Matern's second process (a plant stays
    when no plant within the inhibition distance came first), at the density a plant meets inside its cluster,
    dens x g(0) with the Thomas process's g(0) = 1 + 1 / (4 pi sigma^2 kappa)."""
    core = float(rule['core_m'])
    if core <= 0.0:
        return np.ones(np.shape(dens))
    cl = rule['cluster']
    kappa = max(float(cl['parents_per_ha']) * 1.0e-4, 1e-12)
    sig = max(float(cl['sigma_m']), 0.1)
    g0 = 1.0 + 1.0 / (4.0 * math.pi * sig * sig * kappa)
    d = 2.0 * CORE_FACTOR * core * mean_scale
    a = np.asarray(dens, np.float64) * g0 * math.pi * d * d
    return np.where(a > 1e-9, -np.expm1(-a) / np.maximum(a, 1e-9), 1.0)


def _level_cover(ground, rules, i, max_n=1024, density_n=512, kept=None, focus=None):
    """The expected cover of trees, of shrubs and of grasses (forbs and ground cover with them: COVER_KIND) on level
    i, from the rules' densities alone (the one rule the plan and the material share, design 4.7): per kind the sum
    over its species of density x the share the hard core keeps x the mean crown area, the density clipped to the
    cluster process's ceiling, kept off excluded ground, the undergrowth thinned under the expected tree cover. With
    kept (species name, distances -> the share its instances carry) and the plan's focus, also what the instances
    leave to the material. The densities are evaluated on a k x k grid of the level (at most density_n across, a
    whole fraction of the raster's m x m). Returns (m, step, k, {kind: exponent}, {kind: far exponent})."""
    lv = ground.levels[i]
    step = 1
    while lv.n // step > max_n:
        step *= 2
    m = lv.n // step
    k = m // math.ceil(m / max(int(density_n), 1))
    pts = _GridPoints(ground.levels, i, k)
    memo, fine_memo = {}, {}

    def getter(name):                                    # the densities' read: the coarse levels, on every level
        return ground.site(pts, name, memo.get('shade'), memo)

    def fine(name):
        if name not in fine_memo:
            fine_memo[name] = ground.at(pts, name)
        return fine_memo[name]
    expected = {k_: np.zeros(pts.n) for k_ in ('tree', 'shrub', 'grass')}
    far = {k_: np.zeros(pts.n) for k_ in ('tree', 'shrub', 'grass')}
    dfocus = None if kept is None else path_distance(focus, pts.x, pts.y)
    for kind in ('tree', 'shrub', 'grass'):
        if kind == 'shrub':
            memo['shade'] = 1.0 - np.exp(-expected['tree'])
        for rule in rules:
            if COVER_KIND.get(rule['kind']) != kind:
                continue
            dmax = rule['cluster']['parents_per_ha'] * rule['cluster']['mu'] * 1.0e-4
            dens = np.asarray(P.evaluate(P.parse(rule['density']), getter, pts.x, pts.y, ground.constants),
                              np.float64) * np.ones(pts.n)
            # the physical exclusions on this level's own cells, as the plan places; not its cells' steepness,
            # which a hero level resolves and its parent does not (the raster must not step at a window edge)
            dens = np.clip(dens, 0.0, dmax) * _exclusions(rule, ground, pts, getter, fine, steep=False)
            if kind != 'tree':
                dens = dens * (1.0 - memo['shade'] * (1.0 - float(rule['shade']['tolerance'])))
            crown, mean_scale = _crown_and_scale(rule)
            e = dens * _kept_by_core(rule, dens, mean_scale) * crown
            expected[kind] += e
            far[kind] += e if kept is None else e * (1.0 - kept(rule['name'], dfocus))
    return m, step, k, expected, far


def _cover_raster(v, k, m):
    return _upsample((1.0 - np.exp(-v)).reshape(k, k), m).astype(np.float32)


def _constants(terrain, eco=None):
    """The terrain constants a plan reads: the palette's (palettes.CONSTANTS filled in), the terrain's own
    (terrain_constants) and the ecotope's."""
    info = getattr(terrain, 'info', None) or {}
    try:
        pal = info.get('palette')
        consts = dict(P.get(pal if pal is not None else 'auto', getattr(terrain, 'recipe', None),
                            validate=False)['constants'])
    except (KeyError, ValueError, TypeError):
        consts = dict(P.CONSTANTS)
    consts.update(terrain_constants(terrain))
    consts.update((eco or {}).get('constants') or {})
    return consts


def _resolve(terrain, ecotope):
    info = getattr(terrain, 'info', None) or {}
    if _resolved(ecotope):
        return ecotope
    return E.get(ecotope, recipe=getattr(terrain, 'recipe', None), place=info.get('place'),
                 palette=info.get('palette'))


def expected_cover(terrain, ecotope='auto', data=None, max_n=1024, density_n=512):
    """The ecotope's cover rasters with no plan (design 4.7): per level, from its tree, shrub and grass densities
    alone, in the form bake_surface(extra=) takes: {'canopy_expected': [array per level], 'canopy_far': [...],
    'shrubs': [...], 'shrubs_far': [...], 'grass': [...], 'grass_far': [...]} (the names the surface bake's map
    registry knows), the far ones equal to the expected ones (nothing is instanced). A plan's cover() gives the same
    canopy_expected, shrubs and grass. terrain, ecotope and data as plan_plants takes them."""
    from ..surface.maps import MAPS as known
    eco = _resolve(terrain, ecotope)
    ground = _Ground(terrain, data, _constants(terrain, eco))
    out = {k: [] for k in ('canopy_expected', 'canopy_far', 'shrubs', 'shrubs_far', 'grass', 'grass_far')}
    for i in range(len(ground.levels)):
        m, _step, k, exp_, _far = _level_cover(ground, eco['species'], i, max_n, density_n)
        for kind, name in (('tree', 'canopy_expected'), ('shrub', 'shrubs'), ('grass', 'grass')):
            r = _cover_raster(exp_[kind], k, m)
            out[name].append(r)
            out['canopy_far' if kind == 'tree' else name + '_far'].append(r.copy())
    return {k: v for k, v in out.items() if k in known}


def _discs(img, cx, cy, r):
    """Add discs (centres and radii in texels, texel k spanning [k, k + 1)) to a cover image: each texel gains the
    fraction of it a disc covers. Crowns smaller than a texel add their area; larger ones are stamped with a one-texel
    soft edge. Overlaps saturate at 1 (the caller clips)."""
    ny, nx = img.shape
    ok = (cx > -r) & (cx < nx + r) & (cy > -r) & (cy < ny + r)
    cx, cy, r = cx[ok], cy[ok], r[ok]
    small = r < 0.75
    if small.any():
        i = np.clip(np.floor(cx[small]).astype(np.int64), 0, nx - 1)
        j = np.clip(np.floor(cy[small]).astype(np.int64), 0, ny - 1)
        inside = (cx[small] >= 0) & (cx[small] < nx) & (cy[small] >= 0) & (cy[small] < ny)
        area = np.bincount((j * nx + i)[inside], weights=(math.pi * r[small] ** 2)[inside], minlength=ny * nx)
        img += 1.0 - np.exp(-area.reshape(ny, nx))       # sub-texel crowns overlap at random inside the texel
    for x, y, rad in zip(cx[~small], cy[~small], r[~small]):
        i0, i1 = max(int(math.floor(x - rad - 1)), 0), min(int(math.ceil(x + rad + 1)), nx)
        j0, j1 = max(int(math.floor(y - rad - 1)), 0), min(int(math.ceil(y + rad + 1)), ny)
        if i1 <= i0 or j1 <= j0:
            continue
        dx = np.arange(i0, i1) + 0.5 - x
        dy = np.arange(j0, j1) + 0.5 - y
        d = np.sqrt(dy[:, None] ** 2 + dx[None, :] ** 2)
        img[j0:j1, i0:i1] = np.maximum(img[j0:j1, i0:i1], np.clip(rad - d + 0.5, 0.0, 1.0))
    return img


def _strip_ext(base):
    base = str(base)
    for ext in ('.plants.json', '.json', '.npz'):
        if base.endswith(ext):
            return base[:-len(ext)]
    return base


def cache_base(terrain, ecotope='auto', focus=None, radius_m=None, seed=0, data=None, exclude=None):
    """Where a plan of this terrain is kept in the terrain cache (design 4.5): <terrain cache entry>/plants_<key>,
    the key a hash of the ecotope, the seed, the focus, the radius, the surface bake it read (data, its key), the
    discs it keeps clear when given (exclude, as plan_plants takes it) and the plant code (plants.py, ecotopes.py,
    and palettes.py, whose expressions decide every density). None for a terrain without a cache entry."""
    info = getattr(terrain, 'info', None) or {}
    if not info.get('cache_key'):
        return None
    from ..core import cache as _cache
    eco = ecotope if _resolved(ecotope) else E.get(ecotope, recipe=getattr(terrain, 'recipe', None),
                                                  place=info.get('place'), palette=info.get('palette'))
    f = _focus_points(focus)
    if f is None:
        f = _focus_points(info.get('focus'))
    h = hashlib.sha1()
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in ('plants.py', 'ecotopes.py', 'palettes.py'):
        with open(os.path.join(here, fn), 'rb') as fh:
            h.update(fh.read())
    key = [E.ecotope_hash(eco), int(seed), None if f is None else np.round(f, 3).tolist(),
           None if radius_m is None else float(radius_m), None if data is None else str(getattr(data, 'key', ''))]
    if exclude is not None:
        key.append([[v if isinstance(v, str) else round(float(v), 3) for v in disc] for disc in exclude])
    h.update(json.dumps(key).encode('utf-8'))
    return os.path.join(_cache.Cache(info['cache_key']).path, 'plants_' + h.hexdigest()[:16])


__all__ = ['plan_plants', 'expected_cover', 'PlantSpots', 'FORMAT', 'FIELDS', 'DERIVED_NAMES', 'COVER_MAPS',
           'STEEP_DEG', 'path_distance', 'terrain_constants', 'cache_base']
