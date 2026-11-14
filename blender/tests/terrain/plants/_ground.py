"""A small stand-in for a Terrain, for the plant tests that run in plain Python (numpy; no Blender, no GPU): an
analytic valley (a flat floor with a stream, sides rising to 40 degrees, side gullies) on a main level with hero
levels around a focus, with the family's own masks (masks.compute_stack over a drainage area routed by
solvers/hydro.py). plan_plants reads of a terrain only what this carries: levels, masks, height_at, normal_at, info,
recipe, knobs, flats; the surface bake (surface.bake_surface, through its numpy twins) reads its fields too.

    import _ground as G
    t = G.valley()                       # 2 km at 8 m cells, hero levels down to 0.5 m around (60, -120)
    t.levels, t.masks.level(0), t.fields(0)['h'], t.height_at(x, y), t.info['focus']
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(HERE, '..', 'out', 'plants')
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

from eidoblend.terrain import masks as M  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.core import grid as GR  # noqa: E402
from eidoblend.terrain.core import levels as LV  # noqa: E402


def valley_height(x, y):
    """Metres above the floor: a valley along y (its axis winding a little), sides to 40 degrees, gullies down them."""
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    u = x - 90.0 * np.sin(y / 420.0)
    side = 650.0 * np.tanh(u / 620.0) ** 2
    gullies = 26.0 * np.tanh(np.abs(u) / 220.0) ** 2 * np.sin(y / 61.0 + 2.0 * np.sin(u / 170.0))
    rise = 0.012 * (y + 1024.0)
    lumps = 5.0 * (P.value_noise(x, y, 46.0, seed=5, octaves=3) - 0.5)
    return side + gullies + rise + lumps


class _MaskSet:
    def __init__(self, stack):
        self._stack = stack

    def level(self, i):
        return self._stack[i]

    def __contains__(self, name):
        return any(name in m for m in self._stack)


class Ground:
    """What plan_plants (and the surface bake) read of a terrain."""

    def __init__(self, levels, stack, height, info, recipe='alpine_valley', fields=None):
        self.levels = levels
        self.masks = _MaskSet(stack)
        self._height = height
        self._fields = fields or []
        self.info = info
        self.recipe = recipe
        self.knobs = {}
        self.flats = []

    def fields(self, i):
        """A level's fields ({'h', 'A'}), as Terrain.fields gives them."""
        return self._fields[i]

    def height_at(self, x, y):
        return self._height(x, y)

    def normal_at(self, x, y, smooth=False):
        e = 0.25
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        gx = (self._height(x + e, y) - self._height(x - e, y)) / (2 * e)
        gy = (self._height(x, y + e) - self._height(x, y - e)) / (2 * e)
        n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)


def _area(h, cell):
    from eidoblend.terrain.solvers import hydro as H
    filled, _ = H.fill_depressions(np.asarray(h, np.float64), wrap=(False, False))
    recv, wgt, term = H.route(filled, wrap=(False, False), method='mfd')
    return (H.accumulate(recv, wgt, term) * cell * cell).reshape(h.shape)


def valley(size=2048.0, n=256, focus=(60.0, -120.0), hero_cell=0.5, palette='alpine', base_elevation_m=800.0,
           treeline_m=1950.0, recipe='alpine_valley', seed=3, height=valley_height):
    """The synthetic valley as a Ground: the main level `size` metres at n cells, hero levels around the focus down
    to hero_cell, masks with the alpine place's kind of parameters."""
    plan = LV.plan_levels(size, n, centre=(0.0, 0.0), context=None, focus=focus, hero=hero_cell,
                          warn=lambda m: None)
    fields = []
    A_prev = None
    for lv in plan:
        X, Y = lv.xy()
        h = height(X, Y)
        if lv.role != 'hero':
            A = _area(h, lv.cell)
        else:                                            # the parent's drainage area carried in (as the levels do)
            i0, j0, m = lv.in_parent(plan)
            A = GR.crop_upsample2(A_prev, i0, j0, m, 'bilinear').astype(np.float64) / 2.0
        A_prev = A
        fields.append({'h': h, 'A': A})
    params = M.MaskParams(base_elevation_m=base_elevation_m, treeline_m=treeline_m, snowline_m=3200.0)
    stack = M.compute_stack(fields, plan, params=params)
    info = dict(seed=seed, focus=[list(focus)] if focus is not None else None, palette=palette, place=None,
                base_elevation_m=base_elevation_m, cache_key=None, recipe_name=recipe)
    return Ground(plan, stack, height, info, recipe=recipe,
                  fields=[{k: np.asarray(v, np.float32) for k, v in f.items()} for f in fields])


_CACHE = {}


def cached(name='valley', **kw):
    """One synthetic ground per process and argument set (its masks take a few seconds)."""
    key = (name, tuple(sorted(kw.items())))
    if key not in _CACHE:
        _CACHE[key] = valley(**kw)
    return _CACHE[key]
