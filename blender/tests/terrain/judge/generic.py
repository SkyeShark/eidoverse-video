"""The generic numbers the judge compares (DESIGN.md section 10 item 2), on a matched surface (match.py): Core's
metrics (eidoblend/terrain/core/metrics.py: relief, hypsometry, slope percentiles and fractions, closed
depressions, the spectrum, grid-direction anisotropy, texel-wide cliffs) plus the judge's basin read: for every
closed depression deeper than the threshold, whether its floor is flat or holds water (section 10 item 3: the
basin families pass on that instead of on the depression area).

    nums = numbers(h, pixel, lake_mask=None)       # dict; keys below + Core's

Basin keys (fractions of the tile's area):
    bowl_area_frac, bowl_count     depressions with neither a flat floor nor water: pits, honeycomb cells
    flat_basin_area_frac           depressions with a flat floor or water: lakes, playas, infilled crater floors
A depression (deeper than Core's threshold) has a flat floor when either
    (a) the lower half of its depth (filled - h >= D / 2) is mostly gentle: >= 50 % of those cells under 8 degrees
        (interdune flats, pans, playas, a lake surface: a DEM carries a lake as its flat surface), or
    (b) the bottom tenth of its depth (>= 0.9 D) is flat (>= 75 % under 8 degrees) and covers >= 15 % of the basin
        (an infilled crater floor below steep walls: Meteor Crater's bottom tenth is 4.4 degrees at its median and
        28 % of the crater, while its lower half takes in the walls).
A paraboloid bowl of depth D and radius R fails both once D / R is about 0.25 or more (a crater-like bowl, a honeycomb
cell): its lower half is 6 % under 8 degrees at D / R = 0.4 and its bottom tenth 31 %. A depression holding water
(a lake mask cell) counts as flat. Numpy only.
"""
from __future__ import annotations

import numpy as np

from .refs import grid
from eidoblend.terrain.core import metrics as M

FLAT_FLOOR_DEG = 8.0
HALF_FLAT_SHARE = 0.5          # (a)
TENTH_FLAT_SHARE = 0.75        # (b)
TENTH_AREA_SHARE = 0.15


def basins(h, cell, lake_mask=None, relief=None, depressions=None):
    """The basin read of a surface: dict of the keys in the module doc. `depressions` is Core's
    metrics.depressions() result when the caller has it already (the fill runs once)."""
    h = np.asarray(h, dtype=np.float64)
    frac, count, thr, depth = depressions if depressions is not None else M.depressions(h, cell, relief)
    out = dict(bowl_area_frac=0.0, bowl_count=0, flat_basin_area_frac=0.0, flat_basin_count=0)
    if count == 0:
        return out
    lab, n = M.label(depth > 1e-6)
    flat = lab.ravel()
    d = depth.ravel()
    maxd = np.zeros(n + 1)
    np.maximum.at(maxd, flat, d)
    keep = maxd > thr
    keep[0] = False
    area = np.bincount(flat, minlength=n + 1)
    s = grid.slope_deg(h, cell).ravel()
    gentle = s < FLAT_FLOOR_DEG
    half = d >= 0.5 * maxd[flat]
    tenth = d >= 0.9 * maxd[flat]
    n_half = np.bincount(flat[half], minlength=n + 1)
    n_half_flat = np.bincount(flat[half & gentle], minlength=n + 1)
    n_tenth = np.bincount(flat[tenth], minlength=n + 1)
    n_tenth_flat = np.bincount(flat[tenth & gentle], minlength=n + 1)
    wet = np.zeros(n + 1, bool)
    if lake_mask is not None:
        lm = np.asarray(lake_mask, bool).ravel()
        wet = np.bincount(flat[lm], minlength=n + 1) > 0
    ok_a = n_half_flat >= HALF_FLAT_SHARE * np.maximum(n_half, 1)
    ok_b = (n_tenth_flat >= TENTH_FLAT_SHARE * np.maximum(n_tenth, 1)) & (n_tenth >= TENTH_AREA_SHARE * area)
    ok = ok_a | ok_b | wet
    bowl = keep & ~ok
    good = keep & ok
    tot = float(h.size)
    out.update(bowl_area_frac=float(area[bowl].sum() / tot), bowl_count=int(bowl.sum()),
               flat_basin_area_frac=float(area[good].sum() / tot), flat_basin_count=int(good.sum()))
    return out


def numbers(h, cell, lake_mask=None):
    """Core's metrics of a surface plus the basin read (Core's depression keys come from the same single fill, set
    as core/metrics.metrics() sets them)."""
    h = np.asarray(h, dtype=np.float64)
    nums = M.metrics(h, cell, with_depressions=False)
    dep = M.depressions(h, cell, nums['relief_m'])
    frac, count, thr, _depth = dep
    area_km2 = h.size * cell * cell / 1e6
    nums.update(depression_area_frac=frac, depression_count=count,
                depressions_per_100km2=count / max(area_km2, 1e-12) * 100.0, depression_threshold_m=thr)
    nums.update(basins(h, cell, lake_mask, depressions=dep))
    return nums
