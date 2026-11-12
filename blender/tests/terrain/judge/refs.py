"""The real landform references as the judge reads them: in the terrain package's frame (row 0 = SOUTH, metres;
core/grid.py), with each one's landform family, its open water, the resolution its source really carries, and the
kind of eye-level view its renders take (so a generated terrain is framed alike).

    from judge import refs
    ref = refs.load('mount_fuji')        # .h (rows, cols) float64 metres, row 0 south; .pixel; .family; .meta ...
    refs.names()                         # every reference in reference/data/

Numpy only (the PNG codec is reference/landform_refs.py's), so it runs in Blender's Python too.
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN_NEW = os.path.normpath(os.path.join(HERE, '..'))
REFERENCE_DIR = os.path.join(TERRAIN_NEW, 'reference')
BLENDER_DIR = os.path.normpath(os.path.join(TERRAIN_NEW, '..', '..'))
for _p in (REFERENCE_DIR, BLENDER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import landform_refs as R  # noqa: E402
from sites import SITES  # noqa: E402
from eidoblend.terrain.core import grid  # noqa: E402

# The landform family each reference stands for (DESIGN.md section 5's "judged against" column): it picks the
# family numbers (section 10 item 4) and whether closed basins are allowed (BASIN_FAMILIES).
FAMILY = {
    'mount_fuji': 'volcano',
    'crater_lake': 'caldera',
    'meteor_crater': 'crater',
    'sp_crater': 'cinder_cones',
    'grand_canyon_toroweap': 'canyon',
    'goosenecks': 'canyon',
    'monument_valley': 'mesas',
    'badlands_sd': 'badlands',
    'badlands_sd_detail': 'badlands',
    'namib_star_dunes': 'dunes',
    'great_sand_dunes': 'dunes',
    'white_sands': 'dunes',
    'namib_linear_dunes': 'dunes',
    'lauterbrunnen': 'alpine_valley',
    'yosemite_valley': 'alpine_valley',
    'guilin_karst': 'karst',
    'cliffs_of_moher': 'coast',
    'seven_sisters': 'coast',
    'palouse_hills': 'rolling_hills',
    'san_gabriel_mountains': 'fluvial_range',
}

# Families whose closed depressions are real (craters, calderas, karst dolines, interdune hollows, glacial lakes):
# for them the depression band is replaced by "every basin has a flat floor or water" (section 10 item 3).
BASIN_FAMILIES = {'crater', 'caldera', 'karst', 'dunes', 'alpine_valley'}

# The recipes of section 5 and the references each is judged against (the first is the default).
RECIPE_REFERENCES = {
    'fluvial_range': ['san_gabriel_mountains'],
    'alpine_valley': ['lauterbrunnen', 'yosemite_valley'],
    'stratovolcano': ['mount_fuji'],
    'caldera': ['crater_lake'],
    'cinder_cones': ['sp_crater'],
    'impact_crater': ['meteor_crater'],
    'canyon': ['grand_canyon_toroweap'],
    'incised_meanders': ['goosenecks'],
    'mesas_buttes': ['monument_valley'],
    'badlands': ['badlands_sd', 'badlands_sd_detail'],
    'dunes': ['namib_star_dunes', 'great_sand_dunes', 'white_sands', 'namib_linear_dunes'],
    'tower_karst': ['guilin_karst'],
    'sea_cliffs': ['seven_sisters', 'cliffs_of_moher'],
    'rolling_hills': ['palouse_hills'],
}

# Where the source carries less detail than the stored pixel (radar DSMs, 1/3 arc-second 3DEP), in metres, and the
# Gaussian (in native pixels) the fetch applied after upsampling: the judge passes a generated field through the
# same chain before measuring it (match.py), so a sharp generated crest is not failed against a soft radar one.
NATIVE = {
    'namib_star_dunes': (30.0, 0.6),
    'namib_linear_dunes': (30.0, 0.6),
    'guilin_karst': (30.0, 0.6),
    'cliffs_of_moher': (30.0, 0.6),
    'monument_valley': (10.0, 0.0),
}

# The kind of eye-level view each reference's renders take (sites.py's hand-picked spot), so the judge frames a
# generated terrain the same way (views.py): plain = on the surrounding plain looking at the landform; rim = on the
# edge of a drop looking down into it; floor = on a valley floor looking along it; ridge = on high ground looking
# across valleys; interdune = in a flat between dunes looking at a slip face or along a corridor; inside = on a
# crater or caldera floor or rim looking across it; shore = on the cliff top or beach looking along the coast.
EYE_KIND = {
    'mount_fuji': 'plain', 'crater_lake': 'rim', 'meteor_crater': 'rim', 'sp_crater': 'plain',
    'grand_canyon_toroweap': 'rim', 'goosenecks': 'rim', 'monument_valley': 'plain', 'badlands_sd': 'floor',
    'badlands_sd_detail': 'floor', 'namib_star_dunes': 'interdune', 'great_sand_dunes': 'interdune',
    'white_sands': 'ridge', 'namib_linear_dunes': 'interdune', 'lauterbrunnen': 'floor',
    'yosemite_valley': 'floor', 'guilin_karst': 'plain', 'cliffs_of_moher': 'shore', 'seven_sisters': 'shore',
    'palouse_hills': 'ridge', 'san_gabriel_mountains': 'ridge',
}


class Reference:
    """One reference in the terrain frame. h: float64 metres, row 0 = south; pixel: metres; extent: metres;
    water: uint8 mask in the same frame (0 land, 255 sea, 128 + i lake i) or None; lakes: [{'name', 'level_m',
    'mask_value'}]; sea_level: metres or None; native_m / native_blur_px: see NATIVE; family; eye_kind; meta: the
    JSON; site: sites.py's entry (views)."""

    def __init__(self, name, h, meta, water=None, bodies=None):
        self.name = name
        self.meta = meta
        self.h = np.asarray(h, dtype=np.float64)
        self.pixel = float(meta['pixel_size_m'])
        self.extent = float(meta['cols'] * self.pixel)
        self.water = water
        bodies = bodies or []
        self.lakes = [b for b in bodies if b.get('kind') == 'lake']
        sea = [b for b in bodies if b.get('kind') == 'sea']
        self.sea_level = float(sea[0]['level_m']) if sea else None
        self.family = FAMILY.get(name, meta.get('landform', 'unknown'))
        self.basins_allowed = self.family in BASIN_FAMILIES
        self.native_m, self.native_blur_px = NATIVE.get(name, (None, 0.0))
        self.eye_kind = EYE_KIND.get(name, 'plain')
        self.site = SITES.get(name, {})
        self.title = meta.get('title', name)

    @property
    def soft(self):
        """True when the source is coarser than the stored pixel (the fields carry no detail below native_m)."""
        return self.native_m is not None and self.native_m > 1.2 * self.pixel

    def lake_mask(self):
        """Lakes (not the sea) as a boolean array in the terrain frame, or None."""
        if self.water is None:
            return None
        return (self.water >= 128) & (self.water < 255)

    def eye(self):
        """The site's eye-level view in this tile's local metres (x east, y north from the centre)."""
        ev = self.site.get('views', {}).get('eye')
        if not ev:
            return None
        ex, ey = R.latlon_to_xy(self.meta, *ev['at'])
        lx, ly = R.latlon_to_xy(self.meta, *ev['look'])
        return dict(x=float(ex), y=float(ey), look_x=float(lx), look_y=float(ly), look_dz=ev.get('look_dz', 0.0),
                    lens_mm=ev.get('lens_mm', 35.0))

    def aerial_azimuth(self):
        return float(self.site.get('views', {}).get('aerial', {}).get('azimuth_deg', 200.0))

    def __repr__(self):
        return (f'Reference({self.name!r}, {self.h.shape[1]}x{self.h.shape[0]} @ {self.pixel:g} m, family '
                f'{self.family}{", soft " + format(self.native_m, "g") + " m" if self.soft else ""})')


def names():
    """Every reference in reference/data/ (the context files are not separate references)."""
    return R.names()


_CACHE = {}


def load(name):
    """The named reference (cached per process)."""
    if name in _CACHE:
        return _CACHE[name]
    if name not in names():
        near = sorted(names(), key=lambda n: _distance(n, name))[:3]
        raise KeyError(f'no reference {name!r}; nearest: {", ".join(near)}')
    h, meta = R.load(name)
    water = bodies = None
    w = R.load_water(name)
    if w is not None:
        water = grid.from_north_up(w[0])
        bodies = w[1]
    ref = Reference(name, grid.from_north_up(h), meta, water, bodies)
    _CACHE[name] = ref
    return ref


def load_context(name):
    """(h float64 row 0 south, pixel m, meta) of a reference's wider, coarser surround, or None."""
    try:
        hc, mc = R.load(name, context=True)
    except FileNotFoundError:
        return None
    return np.asarray(grid.from_north_up(hc), dtype=np.float64), float(mc['pixel_size_m']), mc


def _distance(a, b):
    """Edit distance, for 'did you mean' messages."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
