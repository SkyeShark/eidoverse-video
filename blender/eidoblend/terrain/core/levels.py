"""Nested levels around the shot (design section 2.2): plan_levels and the stage `levels` selector.

A terrain is a stack of square windows, coarsest first: context levels for the horizon, the main tile, and hero
levels around the camera. Each child has half its parent's cell; its window edges lie on its parent's EVEN grid
lines (so the child's cells nest 2 x 2 inside the parent's, and the hole in the parent's stride-2 mesh lines up with
the child's edge) and it stays at least `band` parent cells inside its parent.

    plan = plan_levels(8000, 1024, centre=(0, 0), context=4, focus=(1200, -300), hero=0.5)
    for lv in plan: print(lv)     # Level(0 context 32000 m @ 31.25 m x1024 ...), ..., Level(6 hero 500 m @ 0.4883 m
                                  # x1024): the design's "512 m at 0.5 m" is that level, rounded
    lv.window                     # (x0, y0, side, cell, n)
    lv.xy()                       # world cell centres
    lv.in_parent(plan)            # (i0, j0, m): the window in its parent's cells
    select_levels('cell<=40', plan) -> [indices];  'all' 'first' 'context' 'main' 'hero' 'cell>=30'
                                    'resolves:2000' (the first level whose cell is at most 2000 / 8 m)
    QUALITY['film']               # {'resolution': 1024, 'hero_cell': 0.5, 'steps_scale': 1.0}

Rules (each one the design's):
- context levels: ceil(log2(context)) of them, each twice the next's side, centred on the tile centre, all with the
  main tile's cell count;
- the coarsest level carries `prepass`: the cell counts it is solved at before its own (n / 2^k while >= 192:
  256 and 512 for 1024), each upsampled into the next;
- the main tile: `size` metres at `resolution` cells (a multiple of 8, so the nesting is exact);
- hero levels, only with a focus and a hero cell: each half its parent's side but never smaller than the focus's
  bounding box plus a margin (the border band plus 16 free cells, each side), centred on the focus, snapped and kept
  inside its parent; they continue until the cell is at most `hero` metres. A large focus grows the cell count, up
  to max_cells (2048); past that, or when the focus no longer fits inside the parent, the cell stops shrinking and
  a warning says so;
- the border band is 16 cells: there the child is pinned to its parent (core/grid.border_ramp).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, asdict

import numpy as np

BAND = 16                                       # the border band, cells
FREE = 16                                       # cells between the band and the focus, each side
MAX_CELLS = 2048
PREPASS_MIN = 192
QUALITY = {
    'draft': {'resolution': 512, 'hero_cell': None, 'steps_scale': 0.5},
    'film': {'resolution': 1024, 'hero_cell': 0.5, 'steps_scale': 1.0},
    'hero': {'resolution': 2048, 'hero_cell': 0.25, 'steps_scale': 1.0},
}
ROLES = ('context', 'main', 'hero')


@dataclass
class Level:
    """One square window: (x0, y0, side, cell, n) plus its place in the stack."""
    index: int
    role: str                                   # 'context' | 'main' | 'hero'
    x0: float
    y0: float
    side: float
    cell: float
    n: int
    parent: int | None = None                   # the index of the next coarser level
    stride: int = 2                             # the ring mesh's vertex stride (1 on hero levels, 2 elsewhere)
    prepass: tuple = ()                         # coarse-to-fine cell counts before this level's own (coarsest only)
    band: int = BAND
    depth: int = 0                              # main = 0; context levels > 0 (2^depth x the main's cell); hero < 0
    notes: list = field(default_factory=list)

    @property
    def window(self):
        return (self.x0, self.y0, self.side, self.cell, self.n)

    @property
    def x1(self):
        return self.x0 + self.side

    @property
    def y1(self):
        return self.y0 + self.side

    @property
    def centre(self):
        return (self.x0 + 0.5 * self.side, self.y0 + 0.5 * self.side)

    @property
    def lv(self):
        """(x0, y0, cell): what a kernel's world_xy takes."""
        return (self.x0, self.y0, self.cell)

    def xy(self):
        """World (x, y) of every cell centre: float64 (n, n) meshgrids, row 0 south."""
        xs = self.x0 + (np.arange(self.n) + 0.5) * self.cell
        ys = self.y0 + (np.arange(self.n) + 0.5) * self.cell
        return np.meshgrid(xs, ys)

    def contains(self, x, y, margin=0.0):
        x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
        return ((x >= self.x0 + margin) & (x <= self.x1 - margin) & (y >= self.y0 + margin)
                & (y <= self.y1 - margin))

    def index_of(self, x, y):
        """Fractional (i, j) of world points; cell centres are whole numbers."""
        return ((np.asarray(x, np.float64) - self.x0) / self.cell - 0.5,
                (np.asarray(y, np.float64) - self.y0) / self.cell - 0.5)

    def in_parent(self, levels):
        """(i0, j0, m): this window in its parent's cells (whole numbers by construction), or None for level 0."""
        if self.parent is None:
            return None
        p = levels[self.parent]
        return (int(round((self.x0 - p.x0) / p.cell)), int(round((self.y0 - p.y0) / p.cell)),
                int(round(self.side / p.cell)))

    def with_cells(self, m):
        """The same window at m cells (a coarse-to-fine pre-pass of the coarsest level)."""
        return Level(self.index, self.role, self.x0, self.y0, self.side, self.side / m, int(m), self.parent,
                     self.stride, (), self.band, self.depth, ['prepass of level %d' % self.index])

    def to_dict(self):
        d = asdict(self)
        d['prepass'] = list(self.prepass)
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d['prepass'] = tuple(d.get('prepass', ()))
        return cls(**d)

    def __repr__(self):
        return (f'Level({self.index} {self.role} {self.side:g} m @ {self.cell:.4g} m x{self.n}, '
                f'x0 {self.x0:g} y0 {self.y0:g}' + (f', prepass {list(self.prepass)}' if self.prepass else '') + ')')


# -------------------------------------------------------------------------------------------------- the focus ---

def focus_points(focus):
    """A focus as an (N, 2) float array of world (x, y): a point, a list of points, a camera (anything with
    .location), or a list of camera positions (x, y[, z])."""
    if focus is None:
        return None
    if hasattr(focus, 'location'):
        return np.array([[float(focus.location[0]), float(focus.location[1])]])
    if isinstance(focus, (list, tuple)) and focus and hasattr(focus[0], 'location'):
        return np.array([[float(f.location[0]), float(f.location[1])] for f in focus])
    a = np.asarray(focus, dtype=np.float64)
    if a.ndim == 1:
        a = a[None, :]
    if a.ndim != 2 or a.shape[1] < 2:
        raise ValueError(f'focus must be (x, y), a list of (x, y[, z]) or a camera; got shape {a.shape}')
    return a[:, :2].copy()


def _snap(v, origin, step, how=round):
    return origin + step * how((v - origin) / step)


# --------------------------------------------------------------------------------------------- plan_levels ---

def plan_levels(size, resolution, centre=(0.0, 0.0), context=None, focus=None, hero=None, band=BAND,
                max_cells=MAX_CELLS, warn=None):
    """The level stack, coarsest first (see the module doc for the rules). size: the main tile's side in metres;
    resolution: its cell count (a multiple of 8); context: the horizon's extent multiplier (None or <= 1: none);
    focus: a point, points or camera(s) inside the main tile; hero: the finest cell in metres around the focus
    (None: no hero levels). Raises ValueError for a focus outside the main tile or a bad resolution."""
    warn = warn or (lambda m: print('[terrain.levels] ' + m, flush=True))
    size, n = float(size), int(resolution)
    if size <= 0:
        raise ValueError(f'size must be positive metres, got {size}')
    if n < 64 or n % 8:
        lo, hi = max(64, n - n % 8), max(64, n - n % 8 + 8)
        raise ValueError(f'resolution {n} must be a multiple of 8 (at least 64) so the levels nest exactly; '
                         f'nearest: {lo} or {hi}')
    cx, cy = float(centre[0]), float(centre[1])
    main_cell = size / n
    nctx = int(math.ceil(math.log2(context) - 1e-9)) if context and context > 1 else 0

    # context levels, outermost first, each on its child's even grid lines
    main = Level(0, 'main', cx - size / 2, cy - size / 2, size, main_cell, n, None, 2, (), band, 0)
    chain = [main]
    for d in range(1, nctx + 1):
        child = chain[0]
        cell = main_cell * 2 ** d
        off = 2 * int(round(n / 8.0))                    # n / 4 parent cells: the child centred (n % 8 == 0: exact)
        lv = Level(0, 'context', child.x0 - off * cell, child.y0 - off * cell, n * cell, cell, n, None, 2, (),
                   band, d)
        chain.insert(0, lv)
    levels = chain

    # hero levels
    pts = focus_points(focus)
    if pts is not None:
        if not bool(np.all(main.contains(pts[:, 0], pts[:, 1]))):
            bad = pts[~main.contains(pts[:, 0], pts[:, 1])][0]
            raise ValueError(f'focus ({bad[0]:g}, {bad[1]:g}) is outside the main tile '
                             f'[{main.x0:g}, {main.x1:g}] x [{main.y0:g}, {main.y1:g}] m')
    if pts is not None and hero:
        bx0, by0 = pts.min(axis=0)
        bx1, by1 = pts.max(axis=0)
        fcx, fcy = 0.5 * (bx0 + bx1), 0.5 * (by0 + by1)
        extent = max(bx1 - bx0, by1 - by0)
        parent = levels[-1]
        while parent.cell > hero * (1.0 + 1e-9):
            cell = parent.cell / 2.0
            step = 2.0 * parent.cell                     # the parent's even grid lines
            margin = (band + FREE) * cell
            side = max(parent.side / 2.0, extent + 2.0 * margin)
            side = step * math.ceil(side / step - 1e-9)
            m = int(round(side / cell))
            limit = parent.side - 2.0 * band * parent.cell
            if side > limit + 1e-6:
                warn(f'the focus ({extent:.0f} m across) does not fit a hero window inside the {parent.side:g} m '
                     f'level: the hero cell stops at {parent.cell:.3g} m instead of {hero:g} m')
                break
            if m > max_cells:
                warn(f'a hero window around the focus ({extent:.0f} m across) at {cell:.3g} m cells would need '
                     f'{m} cells (> {max_cells}): the hero cell stops at {parent.cell:.3g} m instead of {hero:g} m')
                break
            lo_x, hi_x = parent.x0 + band * parent.cell, parent.x1 - band * parent.cell - side
            lo_y, hi_y = parent.y0 + band * parent.cell, parent.y1 - band * parent.cell - side
            # centred on the focus, on an even grid line, clamped inside the parent (both bounds are even lines:
            # band is even and the parent's cell count a multiple of 4), then rounded back onto the line exactly
            x0 = _snap(min(max(_snap(fcx - side / 2.0, parent.x0, step), lo_x), hi_x), parent.x0, step)
            y0 = _snap(min(max(_snap(fcy - side / 2.0, parent.y0, step), lo_y), hi_y), parent.y0, step)
            lv = Level(0, 'hero', x0, y0, side, cell, m, None, 1, (), band, parent.depth - 1)
            if not (bool(np.all(lv.contains(pts[:, 0], pts[:, 1], margin=band * cell)))):
                warn(f'the focus is too close to the edge of the {parent.side:g} m level for a hero window at '
                     f'{cell:.3g} m: the hero cell stops at {parent.cell:.3g} m')
                break
            levels.append(lv)
            parent = lv

    for i, lv in enumerate(levels):
        lv.index = i
        lv.parent = i - 1 if i > 0 else None
    # the coarsest level grows coarse-to-fine on its own window first
    first = levels[0]
    pre, m = [], first.n
    while m % 2 == 0 and m // 2 >= PREPASS_MIN:
        m //= 2
        pre.insert(0, m)
    first.prepass = tuple(pre)
    check_plan(levels)
    return levels


def check_plan(levels):
    """Assert the nesting rules: each child has half its parent's cell, sits on the parent's even grid lines, and
    stays `band` parent cells inside. Raises AssertionError naming the level."""
    for lv in levels[1:]:
        p = levels[lv.parent]
        assert abs(lv.cell * 2.0 - p.cell) <= 1e-9 * p.cell, f'{lv}: cell is not half of {p}'
        for a, b in ((lv.x0, p.x0), (lv.y0, p.y0), (lv.x1, p.x0), (lv.y1, p.y0)):
            k = (a - b) / (2.0 * p.cell)
            assert abs(k - round(k)) < 1e-6, f'{lv}: an edge is not on an even grid line of {p}'
        m = lv.band * p.cell - 1e-6 * p.cell
        assert lv.x0 - p.x0 >= m and lv.y0 - p.y0 >= m and p.x1 - lv.x1 >= m and p.y1 - lv.y1 >= m, \
            f'{lv}: closer than {lv.band} cells to the edge of {p}'
        assert abs(lv.n * lv.cell - lv.side) < 1e-6 * lv.side, f'{lv}: n x cell != side'


def plan_dict(levels):
    return [lv.to_dict() for lv in levels]


# ------------------------------------------------------------------------------------------- level selection ---

_SPEC = re.compile(r'^\s*(?:(all|first|last|context|main|hero)|cell\s*(<=|>=|<|>)\s*([0-9.eE+-]+)|'
                   r'resolves\s*:\s*([0-9.eE+-]+))\s*$')
SPEC_FORMS = ("'all'", "'first'", "'last'", "'context'", "'main'", "'hero'", "'cell>=30'", "'cell<=2'",
              "'resolves:<metres>'", 'a level index, or a list of these')


def parse_levels_spec(spec):
    """Check a stage's `levels` value; returns it normalised (a list of strings / ints). Raises ValueError naming
    the forms allowed."""
    items = spec if isinstance(spec, (list, tuple)) else [spec]
    out = []
    for s in items:
        if isinstance(s, (int, np.integer)) and not isinstance(s, bool):
            out.append(int(s))
            continue
        if not isinstance(s, str) or not _SPEC.match(s):
            raise ValueError(f'levels {s!r} is not one of {", ".join(SPEC_FORMS)}')
        out.append(s.strip())
    return out


def select_levels(spec, levels, warn=None):
    """The indices of the levels a stage runs on, sorted. A 'resolves:<m>' that no level resolves picks the finest
    level, with a warning."""
    warn = warn or (lambda m: print('[terrain.levels] ' + m, flush=True))
    picked = set()
    for s in parse_levels_spec(spec):
        if isinstance(s, int):
            if not -len(levels) <= s < len(levels):
                raise IndexError(f'level index {s} out of range for {len(levels)} levels')
            picked.add(s % len(levels))
            continue
        m = _SPEC.match(s)
        word, op, val, res = m.groups()
        if word == 'all':
            picked.update(range(len(levels)))
        elif word == 'first':
            picked.add(0)
        elif word == 'last':
            picked.add(len(levels) - 1)
        elif word:
            picked.update(lv.index for lv in levels if lv.role == word)
        elif op:
            v = float(val)
            f = {'<=': lambda c: c <= v * (1 + 1e-9), '>=': lambda c: c >= v * (1 - 1e-9),
                 '<': lambda c: c < v, '>': lambda c: c > v}[op]
            picked.update(lv.index for lv in levels if f(lv.cell))
        else:
            need = float(res) / 8.0
            hit = [lv.index for lv in levels if lv.cell <= need * (1 + 1e-9)]
            if hit:
                picked.add(hit[0])
            else:
                warn(f"no level resolves {float(res):g} m (cell <= {need:g} m; the finest is "
                     f"{levels[-1].cell:.3g} m): using the finest")
                picked.add(len(levels) - 1)
    return sorted(picked)
