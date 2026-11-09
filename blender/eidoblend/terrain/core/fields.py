"""Fields: a level's named float32 arrays (design section 2.4).

    f = Fields(level)                       # a dict of (n, n) float32 arrays, row 0 south, with .level attached
    f['h'] = start_surface                  # cast to float32, shape checked against the level
    f.new('qs')                             # a zero field;  f.ensure('wear') keeps an existing one
    child = f.inherit(child_level)          # the child's start: h and bed Catmull-Rom x2, other fields bilinear x2,
                                            # U, K, Sc and the pins left out (re-evaluated from world space per level)
    f.thickness()                           # h - bed (sediment, sand, talus)

Ops read and write fields by name; FIELD_DOCS is the table of the design.
"""

from __future__ import annotations

import numpy as np

from . import grid

FIELD_DOCS = {
    'h': 'surface height, m',
    'bed': 'top of rock, m; sediment, sand and talus thickness is h - bed',
    'A': 'drainage area, m^2',
    'qs': 'sediment flux, m^3/yr',
    'U': 'uplift, m/yr',
    'K': 'erodibility, m^(1-2m)/yr',
    'Sc': 'threshold slope (tangent)',
    'G': 'deposition coefficient (dimensionless: 0 bedrock incision, about 1 alluvial floors)',
    'pin_w': 'Dirichlet pin weight 0..1 (borders, sea, flatten areas)',
    'pin_h': 'Dirichlet pin value, m',
    'wear': 'eroded depth, m',
    'deposit': 'deposited sediment, m',
    'talus': 'talus gained by threshold failure, m',
    'sand': 'sand thickness, m',
    'ice': 'ice (glacier) thickness or discharge, per the glacial solver',
    'lava': 'lava-flow footprint / thickness',
    'water': 'lake or sea depth, m',
}
CATMULL = ('h', 'bed')                                  # surfaces: Catmull-Rom x2
NOT_INHERITED = ('U', 'K', 'Sc', 'pin_w', 'pin_h')      # re-evaluated from world space / set per level by the runner


class Fields(dict):
    """A level's named float32 arrays; .level is the Level (core/levels.py) they belong to."""

    def __init__(self, level, arrays=None, **kw):
        super().__init__()
        self.level = level
        for k, v in dict(arrays or {}, **kw).items():
            self[k] = v

    @property
    def shape(self):
        return (self.level.n, self.level.n)

    def __setitem__(self, name, value):
        a = np.asarray(value, dtype=np.float32)
        if a.ndim == 0:
            a = np.full(self.shape, a, np.float32)
        if a.shape != self.shape:
            raise ValueError(f'field {name!r}: shape {a.shape}, the level is {self.shape} ({self.level})')
        super().__setitem__(name, np.ascontiguousarray(a))

    def update(self, other=(), **kw):
        for k, v in dict(other, **kw).items():
            self[k] = v

    def new(self, name, fill=0.0):
        """A new field of `fill` (replacing any old one)."""
        self[name] = np.full(self.shape, fill, np.float32)
        return dict.__getitem__(self, name)

    def ensure(self, name, fill=0.0):
        """The existing field, or a new one of `fill`."""
        if name not in self:
            self.new(name, fill)
        return dict.__getitem__(self, name)

    def thickness(self):
        """h - bed (0 where there is no bed field)."""
        if 'bed' not in self:
            return np.zeros(self.shape, np.float32)
        return (self['h'] - self['bed']).astype(np.float32)

    def xy(self):
        return self.level.xy()

    def copy(self):
        return Fields(self.level, {k: v.copy() for k, v in self.items()})

    def inherit(self, child, rules=None, names=None):
        """The child level's start, from these (parent) fields. `child` is a Level whose cell is half of this level's
        and whose window lies on this level's grid lines (plan_levels makes them so), or the same window at twice
        the cells (a coarse-to-fine pre-pass). Per field: 'catmull' for h and bed, 'skip' for U, K, Sc and the pins,
        'bilinear' for the rest; `rules` ({name: 'catmull' | 'bilinear' | 'nearest' | 'skip'}) overrides, and
        `names` limits which fields are carried."""
        p = self.level
        if abs(child.cell * 2.0 - p.cell) > 1e-9 * p.cell:
            raise ValueError(f'inherit: the child cell {child.cell} m is not half of {p.cell} m')
        fi, fj = (child.x0 - p.x0) / p.cell, (child.y0 - p.y0) / p.cell
        i0, j0, m = int(round(fi)), int(round(fj)), int(round(child.side / p.cell))
        if abs(fi - i0) > 1e-6 or abs(fj - j0) > 1e-6:
            raise ValueError(f'inherit: the child window {child} is not on the grid lines of {p}')
        out = Fields(child)
        for name, a in self.items():
            if names is not None and name not in names:
                continue
            kind = (rules or {}).get(name)
            if kind is None:
                kind = 'skip' if name in NOT_INHERITED else ('catmull' if name in CATMULL else 'bilinear')
            if kind == 'skip':
                continue
            out[name] = grid.crop_upsample2(a, i0, j0, m, kind)
        return out

    def summary(self):
        """{name: (min, max, mean)} for a log line."""
        return {k: (float(v.min()), float(v.max()), float(v.mean())) for k, v in self.items()}

    def __repr__(self):
        return f'Fields({self.level!r}, {sorted(self)})'
