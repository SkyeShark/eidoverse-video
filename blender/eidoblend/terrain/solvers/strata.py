"""Layered rock (design section 4.9): a stratigraphic column in world z that the erosion reads at every cell's current
height, so canyons step in cliffs and benches, mesas and buttes stand on talus over a flat floor, and badlands cut
banded mudstone into knife ridges.

    stage ops (OPS; run.py calls op(fields, level, params, seed, ctx=...)):
      'strata'          the column and where it sits (dip, warp, faults, its height at h = 0), kept for the level's
                        later stages (ctx.shared['strata']), and the field zs (stratigraphic height, metres: the
                        masks' `strata`, which the material reads its colour bands at)
      'plateau'         the start (on a fresh level only): a structural surface at one stratigraphic height (so it
                        follows the dip and warp of the beds), roughened, optionally with an escarpment
      'strata_fluvial'  the fluvial backbone (solvers/fluvial.py's passes) in layered rock: the erodibility K x
                        K(zs) in the stream-power incision, the composite threshold (each layer at its own angle,
                        talus at repose) in place of a single Sc, creep only on soft rock and debris, and the
                        base-level fall: a 'river_path' channel lowered from the starting surface to its final bed
                        over the run (solvers/rivers.py); optionally stopped at a target caprock fraction (mesas)

    from eidoblend.terrain.solvers import strata as S
    col = S.column('colorado_plateau')            # bottom to top, zs = 0 at its base
    col.tan_at(800.0), col.k_at(800.0), col.run_at(800.0), col.layer_at(800.0)
    col.formations()                              # [(thickness_m, K_factor, Sc_deg, colour_id, name), ...] for the
                                                  # material (build/palettes.column_layers reads this form)
    S.palette_for('desert_sandstone', 'colorado_plateau')   # a palette dict whose strata layers read this column
                                                  # (its own thicknesses, colours from MATERIAL): a recipe's
                                                  # defaults['palette'], which palettes.resolve_name honours

The column. Layers bottom to top, each (thickness_m, K_factor, Sc_deg, colour_id, name) or a dict with those keys
plus `creep` (0..1, how much the layer creeps: soft rock 1, cliff rock about 0; default from Sc) and `beds` (ledges
inside the formation: {'period_m', 'ledge_frac', 'ledge_K_factor', 'ledge_Sc_deg', 'jitter'}: the Supai's ledges and
slopes, the Brule's thin sandstones; resolved on the fine levels, averaged by the run integral on the coarse ones).
Tabulated every dz (0.5 m) from 60 m below its base to 60 m above its top: K factor, tan(theta), creep factor, and
the horizontal run R(zs) = integral dz / tan(theta(z)); beyond, the end layers continue.

Stratigraphic height. zs = h + zs0_m - tan(dip) (x cos az + y sin az) - warp(x, y) - throws - fold: zs0_m is the
column height at h = 0 at the origin, the beds rise toward azimuth_deg (counter-clockwise from +x: the design's
formula, the same as masks.py and build/surfacing.py), warp is world noise ([[wavelength_m, amp_m], ...], amp the
standard deviation), each fault drops the beds on one side of its line by throw_m, and fold {'axis_deg' (compass),
'through', 'rise_m', 'half_width_m'} raises them rise_m (d / half_width)^2 at a distance d from the axis (a
syncline; rise < 0 an anticline). The kernels read zoff = h - zs. (The material's strata bands read the zs field
the masks write, so they follow dip, warp, faults and fold alike.)

The composite threshold (kernels/strata_threshold.glsl, the design's rule). Between a cell and its downhill
neighbour the column needs the run R(zs) - R(zs - G dx); the cell is over its threshold when that exceeds dx, and
the excess phi = 1 - dx / run feeds the isotropic exchange of kernels/threshold.glsl (package 3's: mass-conserving,
the moved rock lands as talus). For one uniform layer it is the stock rule (slope <= tan theta); in a column a weak
layer cut back under a cliff makes the cliff fail and retreat. The cell's loose cover (h - bed) rests at repose.

Parameters of 'strata_fluvial' (metres, years, degrees; K in the stream-power law's units). As 'fluvial'
(solvers/fluvial.py): K 1.5e-5, m 0.5, n 1, p 1, slope 'dinf', valley_spacing_m 400 (or D), gullies, roughness 0.3
with roughness_scales_m, k_breakup and breakup_scales_m, deposition 0.5, age_myr 2, dt_ref_yr 1000, refine_steps
1500, lock True, lock_m, min_steps, max_steps, creep_cap 5, max_creep_sub 32, fill_pits, pit_eps_m. Its own:
    U_m_per_yr 0               uplift (layered-rock landforms are driven by base-level fall: 0)
    threshold_iters 3, threshold_rate 0.12     the composite threshold's iterations per step
    repose_deg 34              loose cover (talus, deposits) at its repose angle
    later 'refine'             the coarsest level's later coarse-to-fine passes: 'refine' holds what the first pass
                               made under the low-pass lock and sharpens it (cliffs, benches, gullies), 'evolve' runs
                               on (age x later_frac) like the stock stage
    later_frac 0.25
    pin_every 8                steps between moves of the falling channel
    caprock_zs_m None, caprock_target None, check_every 40    stop the first pass when the share of the main
                               window still at or above the caprock's base height (stratigraphic) falls to the target
    weather_m_per_yr 0         weathering (STRATA_WEATHER, the scarp-retreat process): rock of K factor 1 on a
                               slope of weather_slope_deg (30) or steeper lowers this fast, any layer by its K factor
                               (loose cover x weather_loose, 2), whatever drains across it: weak rock under a cliff
                               wears back, the cliff fails over it and retreats, the strong bed below stays a bench
    weather_area 0             x (1 + weather_area sqrt(A / 10 ha)): faster where runoff gathers (amphitheatres,
                               side canyons, the escarpment fraying into fingers and buttes)
    weather_refine 0           the weathering's factor on the passes under the low-pass lock (it grows the landform;
                               there it only fought the lock, which raised the plateau beside a retreating wall)
    joints (), joint_gain 0    joint sets (joint_field): K x (1 + joint_gain x the joints' weakness): incision and
                               weathering follow the fractures (straight-sided blocks, mesas and buttes)
    resist 0, resist_scales_m [1400, 600]   resistant patches: K x exp(-resist n), n unit noise at those scales: a
                               retreating escarpment leaves the strong patches standing (outliers: mesas, buttes)
Fields read: h, bed (else all rock), K_factor, A, qs. Written: h, bed, A, qs, wear, deposit, talus, zs, and U, K, Sc
(the layer's own tan theta at each cell), G.

Twins (tests only, the 'twin' device): strata_threshold, strata_cell, strata_creep, strata_weather below.
"""
from __future__ import annotations

import math
import time

import numpy as np

from ..core import twins as T
from . import fluvial as FL
from . import rivers as RV

F32 = np.float32
DZ = 0.5
PAD_M = 60.0


# =============================================================================================== the columns ===
# Bottom to top. Thicknesses are the section's own; K_factor multiplies the stage's K; Sc_deg is the angle the rock
# stands at (cliffs 70-84, ledgy slopes 40-50, shale 28-34). Colour ids match build/palettes.LAYER_COLOURS.

def _L(name, thickness_m, K_factor, Sc_deg, colour=None, creep=None, beds=None):
    d = dict(name=name, thickness_m=float(thickness_m), K_factor=float(K_factor), Sc_deg=float(Sc_deg),
             colour=colour or name.split()[0].lower())
    if creep is not None:
        d['creep'] = float(creep)
    if beds is not None:
        d['beds'] = dict(beds)
    return d


COLUMNS = {
    # The Grand Canyon's Paleozoic section as it stands at Toroweap (east of the Toroweap fault): an inner gorge of
    # Muav, Temple Butte and Redwall walls under the lower Supai's ledges, the Esplanade sandstone's wide bench, the
    # Hermit shale slope, and the Coconino, Toroweap and Kaibab rim; Bright Angel shale, Tapeats and Vishnu below
    # for deeper canyons. Contacts checked against the Toroweap DEM's gentle-ground heights (the Esplanade bench at
    # 1300-1450 m holds 45 % of the tile, the river at 505 m, the rim at 1950 m); the angles against its walls by
    # altitude at 8 m (the Muav and lower Supai ledgy slopes with p50 32-40 degrees and cliff bands at p90 65-75, the
    # Redwall p90 72-78, the Hermit slope 21-30, the Coconino p90 62-68, the Kaibab p50 41-46).
    'colorado_plateau': [
        _L('Vishnu schist', 200, 0.35, 62, 'vishnu'),
        _L('Tapeats sandstone', 60, 0.3, 72, 'tapeats'),
        _L('Bright Angel shale', 80, 2.5, 32, 'bright angel'),
        _L('Muav limestone', 350, 0.45, 40, 'muav',
           beds=dict(period_m=28.0, ledge_frac=0.35, ledge_K_factor=0.3, ledge_Sc_deg=72.0, jitter=0.35)),
        _L('Temple Butte limestone', 60, 0.3, 72, 'muav'),
        _L('Redwall limestone', 170, 0.2, 76, 'redwall'),
        # (K 0.55: at 0.9 the Supai wore back under the weathering and the inner gorge came out twice Toroweap's
        # width: its overlook stands 626 m from the river, 869 m above it, a 54-degree wall, the column's own)
        _L('lower Supai group', 200, 0.55, 34, 'supai',
           beds=dict(period_m=22.0, ledge_frac=0.4, ledge_K_factor=0.3, ledge_Sc_deg=68.0, jitter=0.45)),
        _L('Esplanade sandstone', 85, 0.18, 74, 'esplanade'),
        _L('Hermit shale', 265, 3.5, 28, 'hermit'),
        _L('Coconino sandstone', 50, 0.25, 78, 'coconino'),
        _L('Toroweap formation', 100, 0.9, 36, 'toroweap',
           beds=dict(period_m=14.0, ledge_frac=0.35, ledge_K_factor=0.4, ledge_Sc_deg=66.0, jitter=0.4)),
        _L('Kaibab limestone', 180, 0.35, 48, 'kaibab',
           beds=dict(period_m=22.0, ledge_frac=0.4, ledge_K_factor=0.3, ledge_Sc_deg=70.0, jitter=0.35)),
    ],
    # The Goosenecks of the San Juan: the Paradox and Honaker Trail formations, limestone ledges and shaly slopes in
    # thin alternation (the walls "stepped in ledges and slopes"), the lower walls the cliffiest, under the
    # Halgaito's red slopes and a resistant bed the plateau is stripped to. Angles against the Goosenecks DEM at 6 m
    # by height above the river: 0-120 m p50 31-43, p90 55-70 degrees; 120-240 m p50 30-35, p90 43-63; above that
    # benches and the plateau with 25-30 degree slopes.
    # The Paradox's cliff beds are thick (15 m and more) so they stand as cliffs in a 6 m cell: with 5 m beds the
    # composite averaged them away and the walls' steepest 1 % came out at 48 degrees against the DEM's 69.
    'honaker_trail': [
        _L('Paradox formation', 120, 0.3, 42, 'limestone',
           beds=dict(period_m=30.0, ledge_frac=0.5, ledge_K_factor=0.22, ledge_Sc_deg=78.0, jitter=0.35)),
        _L('lower Honaker Trail formation', 100, 0.45, 36, 'limestone',
           beds=dict(period_m=18.0, ledge_frac=0.45, ledge_K_factor=0.3, ledge_Sc_deg=72.0, jitter=0.4)),
        _L('upper Honaker Trail formation', 90, 0.9, 32, 'limestone',
           beds=dict(period_m=9.0, ledge_frac=0.3, ledge_K_factor=0.4, ledge_Sc_deg=60.0, jitter=0.45)),
        _L('Halgaito formation', 70, 2.5, 28, 'shale'),
        _L('Cedar Mesa sandstone (basal bed)', 20, 0.2, 62, 'cedar mesa'),
        _L('Cedar Mesa sandstone', 80, 0.5, 45, 'cedar mesa'),
    ],
    # Monument Valley: the Cedar Mesa sandstone the floor is stripped to, the Organ Rock shale's talus slopes, the
    # De Chelly sandstone's sheer walls, a thin Moenkopi slope and the Shinarump cap the buttes' tops are.
    'monument_valley': [
        _L('Cedar Mesa sandstone', 150, 0.35, 62, 'cedar mesa'),
        _L('Organ Rock shale', 180, 3.0, 33, 'organ rock'),
        _L('De Chelly sandstone', 170, 0.1, 84, 'de chelly'),
        _L('Moenkopi formation', 40, 1.5, 42, 'moenkopi'),
        _L('Shinarump conglomerate', 20, 0.12, 78, 'shinarump'),
    ],
    # The Badlands Wall near Cedar Pass: Chadron clay mounds at the foot, the Brule's banded mudstone with thin
    # sandstone and ash ledges (the Scenic member, then a resistant sandstone the middle surface is stripped to, the
    # Poleslide member), the Rockyford ash and the Sharps formation at the top.
    'badlands': [
        _L('Chadron formation', 30, 2.0, 30, 'chadron', creep=1.0),
        _L('Brule formation, Scenic member', 46, 1.2, 46, 'brule',
           beds=dict(period_m=3.5, ledge_frac=0.25, ledge_K_factor=0.4, ledge_Sc_deg=64.0, jitter=0.5)),
        _L('Brule formation, channel sandstone', 4, 0.15, 68, 'sandstone'),
        _L('Brule formation, Poleslide member', 48, 1.0, 48, 'brule',
           beds=dict(period_m=4.0, ledge_frac=0.25, ledge_K_factor=0.4, ledge_Sc_deg=64.0, jitter=0.5)),
        _L('Rockyford ash', 6, 0.5, 60, 'ash'),
        _L('Sharps formation', 40, 1.0, 46, 'sharps',
           beds=dict(period_m=5.0, ledge_frac=0.2, ledge_K_factor=0.45, ledge_Sc_deg=60.0, jitter=0.5)),
    ],
    'chalk': [_L('chalk with flint bands', 400, 0.8, 80, 'chalk')],
    'limestone': [_L('limestone', 600, 0.4, 75, 'limestone')],
    'granite': [_L('granite', 3000, 0.25, 65, 'granite')],
}


# The colour of each colour id in daylight photographs (desert varnish and staining included), with the material's
# roughness multiplier, mean bed thickness (m) and bed colour jitter: build/palettes' strata-column form. A colour is
# a hex or [(hex, weight), ...] (each bed draws one: the Brule's buff beds with red and maroon palaeosols). The
# Grand Canyon and Badlands colours are the surfacing package's, calibrated on those places (palettes.STRATA_COLUMNS
# 'toroweap' and 'badlands_cedar_pass').
MATERIAL = {
    'vishnu': ('#4f4844', 1.0, 6.0, 0.05), 'tapeats': ('#7d5b45', 1.0, 2.0, 0.07),
    'bright angel': ('#7a6f5e', 1.0, 2.0, 0.06), 'muav': ('#8c6553', 1.0, 3.0, 0.06),
    'redwall': ('#a15b43', 0.95, 6.0, 0.05), 'supai': ('#8f4a33', 1.0, 2.5, 0.09),
    'esplanade': ('#a8653f', 0.95, 4.0, 0.06), 'hermit': ('#9a4f37', 1.0, 2.0, 0.07),
    'coconino': ('#cdb48c', 0.9, 6.0, 0.04), 'toroweap': ('#b19a7c', 1.0, 2.5, 0.06),
    'kaibab': ('#c4b294', 0.95, 3.5, 0.05),
    'limestone': ('#9e958a', 0.95, 2.5, 0.06), 'sandstone': ('#b0875f', 1.0, 2.5, 0.07),
    'shale': ('#94634c', 1.0, 1.5, 0.07),
    'cedar mesa': ('#c7a17b', 1.0, 3.0, 0.06), 'organ rock': ('#9c4f37', 1.0, 2.0, 0.07),
    'de chelly': ('#b8663f', 0.95, 8.0, 0.04), 'moenkopi': ('#9a5940', 1.0, 1.5, 0.08),
    'shinarump': ('#a7896c', 1.0, 2.0, 0.06),
    'chadron': ('#a29e8b', 1.0, 3.0, 0.05),
    'brule': ([('#cdae92', 0.55), ('#b47a62', 0.22), ('#9a6150', 0.12), ('#d9d1c2', 0.11)], 1.0, 0.9, 0.07),
    'ash': ('#ddd6c8', 0.95, 1.5, 0.04), 'sharps': ([('#cdbfa8', 0.8), ('#b9a58c', 0.2)], 1.0, 1.6, 0.06),
    'chalk': ('#e2ded3', 0.9, 1.2, 0.03), 'granite': ('#9d9890', 1.0, 40.0, 0.03),
}


def material_column(spec, dz=None, seed=0):
    """The column as build/palettes' strata-column dict ({'base_m': 0, 'formations': [(name, thickness_m, colour,
    roughness, bed_m, jitter), ...]}): the solver's own thicknesses, so the material's colour bands sit on the
    benches the solver made (the mask `strata` is zs, from the column's base)."""
    col = column(spec, DZ if dz is None else dz, seed)
    rows = []
    for d in col.layers:
        c = MATERIAL.get(str(d['colour']).lower(), ('#a39a8e', 1.0, 2.5, 0.06))
        rows.append((d['name'], d['thickness_m']) + tuple(c))
    return {'base_m': 0.0, 'formations': rows}


def palette_for(base, spec):
    """A palette dict for a recipe's defaults['palette'] (build/palettes resolves 'auto' to it): the named palette
    with its strata layers reading this column (material_column), from the attribute the masks write (zs)."""
    import copy
    from ..build import palettes as P
    pal = copy.deepcopy(P.PALETTES[base])
    pal['name'] = f'{base}+{spec if isinstance(spec, str) else "column"}'
    pal['strata'] = {'column': material_column(spec), 'source': 'attribute'}
    return pal


def default_creep(sc_deg):
    """How much a rock creeps from the angle it stands at: shale and mudstone (<= 35 degrees) 1, ledgy rock less,
    cliff rock (>= 62 degrees) 0.02: bare walls do not creep."""
    t = math.tan(math.radians(sc_deg))
    lo, hi = math.tan(math.radians(35.0)), math.tan(math.radians(62.0))
    return float(min(1.0, max(0.02, (hi - t) / (hi - lo))))


def _layer_dict(row):
    if isinstance(row, dict):
        d = dict(row)
    else:
        row = list(row)
        d = dict(thickness_m=row[0], K_factor=row[1], Sc_deg=row[2], colour=row[3] if len(row) > 3 else None,
                 name=row[4] if len(row) > 4 else f'layer {row[3] if len(row) > 3 else ""}')
    for k in ('thickness_m', 'K_factor', 'Sc_deg'):
        if k not in d:
            raise ValueError(f'a column layer needs {k}: {row}')
    d['thickness_m'] = float(d['thickness_m'])
    d['K_factor'] = float(d['K_factor'])
    d['Sc_deg'] = float(d['Sc_deg'])
    if d['thickness_m'] <= 0 or d['K_factor'] <= 0 or not (5.0 <= d['Sc_deg'] <= 89.0):
        raise ValueError(f'column layer {d.get("name")!r}: thickness and K factor must be positive, Sc 5-89 degrees')
    d.setdefault('name', 'layer')
    d['colour'] = d.get('colour') or str(d['name']).split()[0].lower()
    d.setdefault('creep', default_creep(d['Sc_deg']))
    return d


class Column:
    """A stratigraphic column (the module doc): .layers (formations, bottom to top, with base_m and top_m), .fine
    (the beds every table reads), .top_m, and the tables .z0, .dz, .K, .tan, .creep, .R (n,) float64."""

    def __init__(self, layers, name='custom', dz=DZ, seed=0):
        self.name = name
        self.dz = float(dz)
        self.layers = []
        z = 0.0
        for row in layers:
            d = _layer_dict(row)
            d['base_m'], d['top_m'] = z, z + d['thickness_m']
            z = d['top_m']
            self.layers.append(d)
        if not self.layers:
            raise ValueError('a column needs at least one layer')
        self.top_m = z
        rng = np.random.default_rng(int(seed) * 977 + sum(ord(c) for c in str(name)) % 7919)
        fine = []                                     # (bottom, top, K, tan, creep, formation index)
        for i, d in enumerate(self.layers):
            b, t = d['base_m'], d['top_m']
            beds = d.get('beds')
            base = (d['K_factor'], math.tan(math.radians(d['Sc_deg'])), d['creep'])
            if not beds:
                fine.append((b, t) + base + (i,))
                continue
            per = float(beds.get('period_m', 10.0))
            frac = float(beds.get('ledge_frac', 0.4))
            jit = float(beds.get('jitter', 0.3))
            led = (float(beds.get('ledge_K_factor', 0.3)), math.tan(math.radians(float(beds.get('ledge_Sc_deg', 70.0)))),
                   default_creep(float(beds.get('ledge_Sc_deg', 70.0))))
            zz = b
            while zz < t - 1e-9:
                p = per * float(np.exp(jit * rng.standard_normal()))
                lf = float(np.clip(frac * (1.0 + 0.5 * jit * rng.standard_normal()), 0.08, 0.9))
                z1 = min(zz + p * (1.0 - lf), t)
                if z1 > zz:
                    fine.append((zz, z1) + base + (i,))
                z2 = min(z1 + p * lf, t)
                if z2 > z1:
                    fine.append((z1, z2) + led + (i,))
                zz = z2
        self.fine = fine
        self.z0 = -PAD_M
        n = int(math.ceil((self.top_m + 2.0 * PAD_M) / self.dz)) + 1
        z = self.z0 + np.arange(n) * self.dz
        self.zs = z
        bot = np.array([f[0] for f in fine])
        idx = np.clip(np.searchsorted(bot, np.clip(z, 0.0, self.top_m - 1e-9), side='right') - 1, 0, len(fine) - 1)
        self.K = np.array([fine[i][2] for i in idx])
        self.tan = np.array([fine[i][3] for i in idx])
        self.creep = np.array([fine[i][4] for i in idx])
        self.formation = idx
        # R exactly at the samples: the run through every fine layer below, the end layers continuing past the ends
        edges = np.array([f[0] for f in fine] + [fine[-1][1]])
        inv = np.array([1.0 / f[3] for f in fine])
        cum = np.concatenate([[0.0], np.cumsum(np.diff(edges) * inv)])
        zc = np.clip(z, 0.0, self.top_m)
        k = np.clip(np.searchsorted(edges, zc, side='right') - 1, 0, len(fine) - 1)
        R = cum[k] + (zc - edges[k]) * inv[k]
        R = R + np.where(z < 0.0, z * inv[0], 0.0) + np.where(z > self.top_m, (z - self.top_m) * inv[-1], 0.0)
        self.R = R

    # -------------------------------------------------------------------------------------- lookups (twins) ---
    def _t(self, zs):
        return np.clip((np.asarray(zs, np.float64) - self.z0) / self.dz, 0.0, len(self.zs) - 1.0)

    def _lerp(self, table, zs):
        t = self._t(zs)
        i0 = np.floor(t).astype(np.int64)
        i1 = np.minimum(i0 + 1, len(table) - 1)
        f = t - i0
        return table[i0] * (1.0 - f) + table[i1] * f

    def k_at(self, zs):
        return self._lerp(self.K, zs)

    def tan_at(self, zs):
        return self._lerp(self.tan, zs)

    def creep_at(self, zs):
        return self._lerp(self.creep, zs)

    def run_at(self, zs):
        """R(zs), linearly continued past the table (as the kernel)."""
        zs = np.asarray(zs, np.float64)
        t = (zs - self.z0) / self.dz
        n = len(self.R)
        lo = self.R[0] + t * (self.R[1] - self.R[0])
        hi = self.R[-1] + (t - (n - 1)) * (self.R[-1] - self.R[-2])
        return np.where(t <= 0, lo, np.where(t >= n - 1, hi, self._lerp(self.R, zs)))

    def layer_at(self, zs):
        """The formation's name at a stratigraphic height."""
        z = float(np.clip(zs, 0.0, self.top_m - 1e-9))
        for d in self.layers:
            if d['base_m'] <= z < d['top_m']:
                return d['name']
        return self.layers[-1]['name']

    def base_of(self, name):
        for d in self.layers:
            if d['name'] == name or str(d['name']).lower().startswith(str(name).lower()):
                return d['base_m']
        raise KeyError(f'column {self.name!r} has no layer {name!r}; layers: {[d["name"] for d in self.layers]}')

    def top_of(self, name):
        for d in self.layers:
            if d['name'] == name or str(d['name']).lower().startswith(str(name).lower()):
                return d['top_m']
        raise KeyError(f'column {self.name!r} has no layer {name!r}; layers: {[d["name"] for d in self.layers]}')

    def formations(self):
        """The design's form, bottom to top from zs = 0: [(thickness_m, K_factor, Sc_deg, colour_id, name), ...]."""
        return [(d['thickness_m'], d['K_factor'], d['Sc_deg'], d['colour'], d['name']) for d in self.layers]

    def table_texture(self):
        """(1, n, 4) float32: tan, creep factor, R, K factor (strata_cell, strata_threshold)."""
        return np.stack([self.tan, self.creep, self.R, self.K], 1).astype(F32)[None, :, :]

    def describe(self):
        lines = [f'column {self.name}: {self.top_m:g} m, {len(self.layers)} formations, {len(self.fine)} beds']
        for d in reversed(self.layers):
            lines.append(f"  {d['top_m']:7.1f} m  {d['name']:<36} {d['thickness_m']:6.1f} m  K x{d['K_factor']:<5g} "
                         f"{d['Sc_deg']:4.0f} deg  creep {d['creep']:.2f}" + ('  (ledges)' if d.get('beds') else ''))
        return '\n'.join(lines)

    def __repr__(self):
        return f'Column({self.name!r}, {self.top_m:g} m, {len(self.layers)} formations)'


_COLUMN_CACHE = {}


def column(spec, dz=DZ, seed=0):
    """A Column from a COLUMNS name, a list of layers (bottom to top), or a Column (cached per spec)."""
    if isinstance(spec, Column):
        return spec
    if isinstance(spec, dict) and 'layers' in spec:
        name, layers = spec.get('name', 'custom'), spec['layers']
    elif isinstance(spec, str):
        if spec not in COLUMNS:
            import difflib
            near = difflib.get_close_matches(spec, list(COLUMNS), n=3, cutoff=0.4)
            raise KeyError(f'no column {spec!r}' + (f'; nearest: {", ".join(near)}' if near else
                                                    f'; columns: {", ".join(sorted(COLUMNS))}'))
        name, layers = spec, COLUMNS[spec]
    else:
        name, layers = 'custom', spec
    key = (repr(layers), float(dz), int(seed), name)
    if key not in _COLUMN_CACHE:
        _COLUMN_CACHE[key] = Column(layers, name, dz, seed)
    return _COLUMN_CACHE[key]


# ======================================================================================= where the beds sit ===

STRATA_DEFAULTS = dict(column='colorado_plateau', zs0_m=0.0, dip_deg=0.0, azimuth_deg=0.0, warp=(), faults=(),
                       fold=None, dz_m=DZ, seed=0)


def strata_spec(params):
    d = dict(STRATA_DEFAULTS)
    d.update({k: v for k, v in (params or {}).items() if k in STRATA_DEFAULTS})
    return d


def _fault_drop(f, x, y):
    """0..1 on the downthrown side of a fault line (C1 across width_m)."""
    ax, ay = (float(v) for v in f.get('at', (0.0, 0.0)))
    s = math.radians(float(f.get('strike_deg', 0.0)))            # compass strike
    ux, uy = math.sin(s), math.cos(s)
    side = (x - ax) * (-uy) + (y - ay) * ux                      # > 0 left of the strike direction
    if f.get('down', 'left') == 'right':
        side = -side
    w = max(float(f.get('width_m', 20.0)), 1e-6)
    t = np.clip(side / w + 0.5, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def offset(spec, level, seed=0, dev=None):
    """zoff = h - zs on a level's cells (float64): -zs0 + tan(dip) (x cos az + y sin az) + warp - throws."""
    sp = strata_spec(spec)
    x, y = level.xy()
    az = math.radians(float(sp['azimuth_deg']))
    out = -float(sp['zs0_m']) + math.tan(math.radians(float(sp['dip_deg']))) * (x * math.cos(az) + y * math.sin(az))
    s = int(seed) + int(sp.get('seed', 0))
    for k, (wl, amp) in enumerate(sp.get('warp') or ()):
        if float(amp) == 0.0:
            continue
        f = FL._field({'kind': 'fbm', 'wavelength_m': float(wl), 'octaves': 3, 'seed': 501 + k}, level, s, dev)
        out = out + 3.0 * float(amp) * f                       # fbm's standard deviation is 1/3
    for f in sp.get('faults') or ():
        out = out - float(f.get('throw_m', 0.0)) * _fault_drop(f, x, y)
    fd = sp.get('fold')
    if fd:
        # a fold along an axis: the beds rise rise_m at half_width_m from it (a syncline; negative: an anticline),
        # so a plateau following them drains toward the axis, over the escarpments that face it
        ax, ay = (float(v) for v in fd.get('through', (0.0, 0.0)))
        a = math.radians(float(fd.get('axis_deg', 0.0)))                    # compass
        d = (x - ax) * math.cos(a) - (y - ay) * math.sin(a)                  # across the axis (along sin a, cos a)
        out = out + float(fd.get('rise_m', 0.0)) * (d / max(float(fd.get('half_width_m', 4000.0)), 1.0)) ** 2
    return out


def zs_field(h, spec, level, seed=0, dev=None):
    return (np.asarray(h, np.float64) - offset(spec, level, seed, dev)).astype(F32)


# ================================================================================================ the twins ===

def _run_lookup(rtab_z, z, z0, dz):
    """strata_threshold.glsl run_at: R linearly interpolated, continued linearly past the ends (float32)."""
    n = rtab_z.shape[0]
    t = ((z - F32(z0)) / F32(dz)).astype(F32)
    tn = F32(n - 1)
    lo = rtab_z[0] + t * (rtab_z[1] - rtab_z[0])
    hi = rtab_z[n - 1] + (t - tn) * (rtab_z[n - 1] - rtab_z[n - 2])
    tc = np.clip(t, F32(0), tn)
    i0 = np.minimum(np.floor(tc).astype(np.int64), n - 2)
    f = (tc - i0.astype(F32)).astype(F32)
    mid = rtab_z[i0] * (F32(1) - f) + rtab_z[i0 + 1] * f
    return np.where(t <= 0, lo, np.where(t >= tn, hi, mid)).astype(F32)


@T.twin('strata_threshold')
def strata_threshold(s, u):
    h = s['st'][..., 0]
    bound = u['uBound']

    def ax(k):
        v, ok = T.neighbour(h, k, bound)
        return np.where(ok, v, h)
    gx = np.maximum(h - np.minimum(ax(3), ax(4)), F32(0))
    gy = np.maximum(h - np.minimum(ax(1), ax(6)), F32(0))
    span = np.sqrt(gx * gx + gy * gy).astype(F32)
    zs = (h - s['zoff'][..., 0]).astype(F32)
    L = np.maximum(s['mk'][..., 3], F32(0))
    rt = s['rtab'][0, :, 2]
    z0, dz = u['uRZ0'], u['uRDz']
    dR = (np.minimum(span, L) / u['uRepose']).astype(F32)
    rock = (_run_lookup(rt, (zs - L).astype(F32), z0, dz) - _run_lookup(rt, (zs - span).astype(F32), z0, dz))
    dR = np.where(span > L, dR + rock, dR).astype(F32)
    with np.errstate(divide='ignore', invalid='ignore'):
        phi = np.where((span > 0) & (dR > u['uDx']), F32(1) - u['uDx'] / np.where(dR > 0, dR, F32(1)), F32(0))
    return {'outP': phi.astype(F32)[..., None]}


# Per cell, once a step: the layer's own threshold and creep factor at the cell's current height (strata_creep reads
# them for the cell and its 8 neighbours; looking them up there cost 9 table reads a neighbour pair).
STRATA_CELL = FL.Inline('strata_cell', r'''//! sampler st     x: h (m)
//! sampler zoff   x: z - zs (m)
//! sampler ctab   x: tan(theta), y: creep factor (1 row of uTN texels from uTZ0 every uTDz metres)
//! image   outC rg32f   x: tan(theta) of the layer at the cell's zs, y: its creep factor
//! uniform float uTZ0
//! uniform float uTDz
//! uniform int uTN
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float zs = texelFetch(st, p, 0).x - texelFetch(zoff, p, 0).x;
  float t = clamp((zs - uTZ0) / uTDz, 0.0, float(uTN - 1));
  int i0 = min(int(floor(t)), uTN - 2);
  float f = t - float(i0);
  vec2 a = texelFetch(ctab, ivec2(i0, 0), 0).xy;
  vec2 b = texelFetch(ctab, ivec2(i0 + 1, 0), 0).xy;
  imageStore(outC, p, vec4(mix(a, b, f), 0.0, 0.0));
}
''')

# creep.glsl on soft rock only: the pair's threshold is the mean of its cells' layer tangents, its diffusivity the
# smaller of their creep factors (a cliff's rock does not creep; a shale slope and its talus do).
STRATA_CREEP = FL.Inline('strata_creep', r'''//! sampler st     x: h (m); y, z, w carried
//! sampler cell   x: tan(theta), y: creep factor (strata_cell)
//! sampler pin    x: pin_w, y: pin_h
//! image   outS rgba32f
//! uniform float uDx
//! uniform float uDtSub
//! uniform float uD
//! uniform float uCap
//! uniform int uBound
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float h = c.x;
  vec2 cc = texelFetch(cell, p, 0).xy;
  float acc = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float hq = texelFetch(st, q, 0).x;
    vec2 cq = texelFetch(cell, q, 0).xy;
    float scp = 0.5 * (cc.x + cq.x);
    float r = ((hq - h) / (LEN[k] * uDx)) / scp;
    float f = min(1.0 / max(1.0 - r * r, 1e-9), uCap);
    acc += WISO[k] * f * min(cc.y, cq.y) * (hq - h);
  }
  float hn = h + uDtSub * uD * acc / (uDx * uDx);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    hn = pin_apply(hn, pn.x, pn.y);
  }
  imageStore(outS, p, vec4(hn, c.y, c.z, c.w));
}
''')


# Weathering (the scarp-retreat process): exposed rock wears back at a rate set by its layer and the slope, whatever
# drains across it. The stream-power term needs drainage area, so on hillslopes it is weak: a weak layer once at its
# threshold angle never retreated, the cliffs above it never failed, and no bench widened (the Esplanade platform is
# 45 % of Toroweap's tile). Here a cell lowers by
#     E = uW f (K / uK0) min(G / uS0, 1),   f = the column's K factor at its zs (loose cover: uLoose)
# G the upwind gradient magnitude (strata_threshold's), never below its lowest neighbour (no pits). Shale under a
# cliff wears back fast, the cliff above fails over it (the composite threshold), the strong bed below stays a bench;
# gentle ground barely wears (the plateau and the benches stay flat). The fine debris leaves (suspended load).
STRATA_WEATHER = FL.Inline('strata_weather', r'''//! sampler st     x: h (m); y, z, w carried
//! sampler zoff   x: z - zs (m)
//! sampler ctab   w: the column's K factor (1 row of uTN texels from uTZ0 every uTDz metres)
//! sampler par    y: K, the erodibility field (its noise varies the weathering alike)
//! sampler pin    x: pin_w, y: pin_h
//! sampler mk     x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outS rgba32f
//! image   outM rgba32f
//! uniform float uDx
//! uniform float uDt
//! uniform float uW      lowering rate (m/yr) of K-factor-1 rock on a slope of uS0 or steeper
//! uniform float uS0     tan of the slope from which the full rate applies
//! uniform float uK0     the stage's K: the field's noise is K / uK0
//! uniform float uWl     lowering rate (m/yr) of loose cover: debris washes away
// (on the refining passes the rock rate is off and only uWl runs, so failed debris does not drape the cliffs below)
//! uniform float uAc     the drainage-area boost: x (1 + uAc min(sqrt(A / 1e5 m^2), 30)), A = st.y
//! uniform float uTZ0
//! uniform float uTDz
//! uniform int uTN
//! uniform int uBound
float axis_h(ivec2 p, int k, ivec2 n, float h) {
  ivec2 q;
  return neighbour(p, k, n, uBound, q) ? texelFetch(st, q, 0).x : h;
}
/* q >= 0 metres taken off the top of the layers m: deposit, then talus, then other loose cover, then rock (wear) */
vec4 take(vec4 m, float q) {
  float other = max(m.w - m.y - m.z, 0.0);
  float r = q;
  float a = min(r, m.y);
  m.y -= a;
  r -= a;
  a = min(r, m.z);
  m.z -= a;
  r -= a;
  r -= min(r, other);
  m.w = max(m.w - (q - r), 0.0);
  m.x += r;
  return m;
}
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float h = c.x;
  float gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  float gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  float G = sqrt(gx * gx + gy * gy) / uDx;
  float hlow = h;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (neighbour(p, k, n, uBound, q)) hlow = min(hlow, texelFetch(st, q, 0).x);
  }
  float zs = h - texelFetch(zoff, p, 0).x;
  float t = clamp((zs - uTZ0) / uTDz, 0.0, float(uTN - 1));
  int i0 = min(int(floor(t)), uTN - 2);
  float kf = mix(texelFetch(ctab, ivec2(i0, 0), 0).w, texelFetch(ctab, ivec2(i0 + 1, 0), 0).w, t - float(i0));
  vec4 m = texelFetch(mk, p, 0);
  float w = clamp(max(m.w, 0.0), 0.0, 1.0);
  float rate = mix(uW * kf, uWl, w);
  float boost = 1.0 + uAc * min(sqrt(max(c.y, 0.0) / 1e5), 30.0);
  float E = rate * (texelFetch(par, p, 0).y / uK0) * min(G / uS0, 1.0) * boost;
  float hn = max(h - uDt * E, min(h, hlow));
  m = take(m, h - hn);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    float hp = pin_apply(hn, pn.x, pn.y);
    float d = hp - hn;
    if (d >= 0.0) {
      m.y += d;
      m.w += d;
    } else {
      m = take(m, -d);
    }
    hn = hp;
  }
  imageStore(outS, p, vec4(hn, c.y, c.z, c.w));
  imageStore(outM, p, m);
}
''')


def _take(wear, dep, tal, loose, q):
    """STRATA_WEATHER's take(): q >= 0 metres off the top of the layers (deposit, talus, other loose cover, rock)."""
    other = np.maximum(loose - dep - tal, F32(0))
    r = q
    a = np.minimum(r, dep)
    dep = dep - a
    r = r - a
    a = np.minimum(r, tal)
    tal = tal - a
    r = r - a
    r = r - np.minimum(r, other)
    loose = np.maximum(loose - (q - r), F32(0))
    return wear + r, dep, tal, loose


@T.twin('strata_weather')
def strata_weather(s, u):
    st, mk = s['st'], s['mk']
    h = st[..., 0]
    bound = u['uBound']

    def ax(k):
        v, ok = T.neighbour(h, k, bound)
        return np.where(ok, v, h)
    gx = np.maximum(h - np.minimum(ax(3), ax(4)), F32(0))
    gy = np.maximum(h - np.minimum(ax(1), ax(6)), F32(0))
    G = (np.sqrt(gx * gx + gy * gy) / u['uDx']).astype(F32)
    hlow = h.copy()
    for k in range(8):
        v, ok = T.neighbour(h, k, bound)
        hlow = np.where(ok, np.minimum(hlow, v), hlow)
    zs = (h - s['zoff'][..., 0]).astype(F32)
    tab = s['ctab'][0, :, 3]
    nt = int(u['uTN'])
    t = np.clip((zs - u['uTZ0']) / u['uTDz'], F32(0), F32(nt - 1)).astype(F32)
    i0 = np.minimum(np.floor(t).astype(np.int64), nt - 2)
    fr = (t - i0.astype(F32)).astype(F32)
    kf = tab[i0] * (F32(1) - fr) + tab[i0 + 1] * fr
    w = np.clip(np.maximum(mk[..., 3], F32(0)), F32(0), F32(1))
    rate = (u['uW'] * kf) * (F32(1) - w) + u['uWl'] * w
    boost = F32(1) + u['uAc'] * np.minimum(np.sqrt(np.maximum(st[..., 1], F32(0)) / F32(1e5)), F32(30))
    E = rate * (s['par'][..., 1] / u['uK0']) * np.minimum(G / u['uS0'], F32(1)) * boost
    hn = np.maximum(h - u['uDt'] * E, np.minimum(h, hlow)).astype(F32)
    wear, dep, tal, loose = _take(mk[..., 0], mk[..., 1], mk[..., 2], mk[..., 3], (h - hn).astype(F32))
    if bound == T.BOUND_PINNED:
        pin = s['pin']
        hp = T.pin_apply(hn, pin[..., 0], pin[..., 1])
        d = (hp - hn).astype(F32)
        g = d >= 0
        w2, d2, t2, l2 = _take(wear, dep, tal, loose, np.maximum(-d, F32(0)))
        wear = np.where(g, wear, w2)
        dep = np.where(g, dep + d, d2)
        tal = np.where(g, tal, t2)
        loose = np.where(g, loose + d, l2)
        hn = hp
    return {'outS': T.rgba(hn, st[..., 1], st[..., 2], st[..., 3]), 'outM': T.rgba(wear, dep, tal, loose)}


@T.twin('strata_cell')
def strata_cell(s, u):
    zs = (s['st'][..., 0] - s['zoff'][..., 0]).astype(F32)
    tab = s['ctab'][0]
    n = int(u['uTN'])
    t = np.clip((zs - u['uTZ0']) / u['uTDz'], F32(0), F32(n - 1)).astype(F32)
    i0 = np.minimum(np.floor(t).astype(np.int64), n - 2)
    f = (t - i0.astype(F32)).astype(F32)[..., None]
    v = tab[i0, :2] * (F32(1) - f) + tab[i0 + 1, :2] * f
    return {'outC': v.astype(F32)}


@T.twin('strata_creep')
def strata_creep(s, u):
    st, cell, pin = s['st'], s['cell'], s['pin']
    h = st[..., 0]
    sc, cf = cell[..., 0], cell[..., 1]
    acc = np.zeros_like(h)
    for k in range(8):
        hq, ok = T.neighbour(h, k, u['uBound'])
        sq, _ = T.neighbour(sc, k, u['uBound'], fill=1.0)
        cq, _ = T.neighbour(cf, k, u['uBound'])
        scp = F32(0.5) * (sc + sq)
        r = ((hq - h) / (T.LEN[k] * u['uDx'])) / scp
        f = np.minimum(F32(1) / np.maximum(F32(1) - r * r, F32(1e-9)), u['uCap'])
        acc = acc + np.where(ok, T.WISO[k] * f * np.minimum(cf, cq) * (hq - h), F32(0))
    hn = h + u['uDtSub'] * u['uD'] * acc / (u['uDx'] * u['uDx'])
    if u['uBound'] == T.BOUND_PINNED:
        hn = T.pin_apply(hn, pin[..., 0], pin[..., 1])
    return {'outS': T.rgba(hn, st[..., 1], st[..., 2], st[..., 3])}


# =============================================================================================== the driver ===

class StrataRun(FL.FluvialRun):
    """FluvialRun (solvers/fluvial.py) in layered rock: route_incise with the column's K(zs); creep through
    strata_cell + strata_creep; the threshold as strata_threshold's composite excess, then threshold.glsl's
    isotropic exchange; the lock as the stock driver's."""

    def __init__(self, dev, cell, fields, par, pins, col, zoff, lock_h0=None, lock_b=2, repose_tan=0.67,
                 weather=None):
        column = dict(k_factor=np.asarray(col.K, F32), zoff=np.asarray(zoff, F32), z0=col.z0, dz=col.dz)
        super().__init__(dev, cell, fields, par, pins, FL.PINNED, column, lock_h0, lock_b)
        self.column = col                              # (FluvialRun keeps the K table's (z0, dz, n) in self.col)
        self.ctab = dev.texture(col.table_texture())
        self.tcol = (float(col.z0), float(col.dz), int(len(col.R)))
        self.C = dev.empty(self.shape, 2)
        self.phiS = dev.empty(self.shape, 1)
        self.repose = float(repose_tan)
        # weathering: (rock rate W m/yr, tan of the full-rate slope, the stage's K0, the loose cover's rate m/yr, the
        # drainage-area boost) or None
        self.weather = weather if weather and (float(weather[0]) > 0 or float(weather[3]) > 0) else None

    def weather_pass(self, dt):
        if self.weather is None:
            return
        W, s0, k0, wl, ac = self.weather
        z0, dz, nt = self.tcol
        self.dev.run(STRATA_WEATHER, {'st': self.S.src, 'zoff': self.zoff, 'ctab': self.ctab, 'par': self.P,
                                      'pin': self.Q, 'mk': self.M.src},
                     {'outS': self.S.dst, 'outM': self.M.dst},
                     {'uDx': self.cell, 'uDt': dt, 'uW': W, 'uS0': s0, 'uK0': k0, 'uWl': wl, 'uAc': ac,
                      'uTZ0': z0, 'uTDz': dz, 'uTN': nt, 'uBound': self.bound})
        self.S.swap()
        self.M.swap()

    def set_pins(self, pins):
        self.Q = self.dev.texture(T.rgba(pins['pin_w'], pins['pin_h'], pins['A_in'], pins['qs_in']))

    def threshold(self, iters, rate):
        dev, S, M, b = self.dev, self.S, self.M, self.bound
        z0, dz, nt = self.tcol
        for _ in range(iters):
            dev.run('strata_threshold', {'st': S.src, 'zoff': self.zoff, 'mk': M.src, 'rtab': self.ctab},
                    {'outP': self.phiS}, {'uDx': self.cell, 'uRZ0': z0, 'uRDz': dz, 'uRN': nt,
                                          'uRepose': self.repose, 'uBound': b})
            dev.run('threshold', {'st': S.src, 'par': self.P, 'pin': self.Q, 'mk': M.src, 'phiT': self.phiS},
                    {'outS': S.dst, 'outM': M.dst},
                    {'uDx': self.cell, 'uRate': rate, 'uLoose': 0, 'uIso': 1, 'uBound': b})
            S.swap()
            M.swap()

    def creep(self, dt, D, n_sub, cap):
        dev, S, M, b = self.dev, self.S, self.M, self.bound
        z0, dz, nt = self.tcol
        dev.run(STRATA_CELL, {'st': S.src, 'zoff': self.zoff, 'ctab': self.ctab}, {'outC': self.C},
                {'uTZ0': z0, 'uTDz': dz, 'uTN': nt})
        dev.run(FL.H_KEEP, {'st': S.src}, {'outH': self.W}, {})
        for _ in range(n_sub):
            dev.run(STRATA_CREEP, {'st': S.src, 'cell': self.C, 'pin': self.Q}, {'outS': S.dst},
                    {'uDx': self.cell, 'uDtSub': dt / n_sub, 'uD': D, 'uCap': cap, 'uBound': b})
            S.swap()
        dev.run(FL.CREEP_LAYERS, {'st': S.src, 'h0': self.W, 'mk': M.src}, {'outM': M.dst}, {})
        M.swap()

    def lock_pass(self, lock_gain=1.0):
        if self.lock is None:
            return
        dev, S, M = self.dev, self.S, self.M
        phases, R, stage1 = self.lock
        off, tgt = phases[self.steps % len(phases)]
        if stage1 is not None:
            b1, zero, R1 = stage1
            dev.run(FL.LOCK_RESTRICT, {'st': S.src, 'tgt': zero}, {'outR': R1}, {'uB': b1, 'uOff': (0, 0)})
            dev.run(FL.LOCK_RESTRICT, {'st': R1, 'tgt': tgt}, {'outR': R},
                    {'uB': self.lock_b // b1, 'uOff': (off[0] // b1, off[1] // b1)})
        else:
            dev.run(FL.LOCK_RESTRICT, {'st': S.src, 'tgt': tgt}, {'outR': R}, {'uB': self.lock_b, 'uOff': off})
        dev.run(FL.LOCK_APPLY, {'st': S.src, 'res': R, 'pin': self.Q, 'mk': M.src}, {'outS': S.dst, 'outM': M.dst},
                {'uGain': lock_gain, 'uB': self.lock_b, 'uOff': off})
        S.swap()
        M.swap()

    def step(self, dt, D, n_sub, iters, rate, cap, m=0.5, nexp=1.0, p=1.0, lock_gain=1.0, slope=1, iso=1,
             pit_fill=1, pit_eps=1e-3):
        dev, S, M, cell, b = self.dev, self.S, self.M, self.cell, self.bound
        dev.run('flow_weights', {'st': S.src}, {'outW': self.W}, {'uDx': cell, 'uP': p, 'uBound': b})
        z0, dz, nc = self.col
        dev.run('route_incise', {'st': S.src, 'wsumT': self.W, 'par': self.P, 'pin': self.Q, 'mk': M.src,
                                 'kcol': self.kcol, 'zoff': self.zoff},
                {'outS': S.dst, 'outM': M.dst},
                {'uDx': cell, 'uDt': dt, 'uM': m, 'uN': nexp, 'uP': p, 'uColZ0': z0, 'uColDz': dz, 'uColN': nc,
                 'uSlope': int(slope), 'uPitFill': int(pit_fill), 'uPitEps': pit_eps, 'uBound': b})
        S.swap()
        M.swap()
        self.weather_pass(dt)
        if D > 0 and n_sub > 0:
            self.creep(dt, D, n_sub, cap)
        self.threshold(iters, rate)
        self.lock_pass(lock_gain)
        self.steps += 1


# ================================================================================================== helpers ===

def caprock_fraction(h, zoff, level, main, cap_zs):
    """The share of the main window's cells (on `level`) whose stratigraphic height is at or above cap_zs."""
    j0, j1, i0, i1 = FL._main_window(level, main)
    zs = np.asarray(h, np.float64)[j0:j1, i0:i1] - np.asarray(zoff, np.float64)[j0:j1, i0:i1]
    return float(np.mean(zs >= float(cap_zs)))


def _ring_inner(h):
    """(n, n): on the outer ring, the height of each ring cell's inward neighbour (the diagonal one at the corners);
    elsewhere h itself."""
    h = np.asarray(h, F32)
    out = h.copy()
    out[0, 1:-1], out[-1, 1:-1] = h[1, 1:-1], h[-2, 1:-1]
    out[1:-1, 0], out[1:-1, -1] = h[1:-1, 1], h[1:-1, -2]
    out[0, 0], out[0, -1], out[-1, 0], out[-1, -1] = h[1, 1], h[1, -2], h[-2, 1], h[-2, -2]
    return out


def _strata_of(params, ctx):
    spec = (params or {}).get('strata') or (ctx.shared.get('strata') if ctx is not None else None)
    if spec is None:
        raise ValueError("no strata column: put a 'strata' stage before this one (or give params['strata'])")
    return strata_spec(spec)


def joint_field(level, sets, seed=0, dev=None):
    """Joint-guided weakness, 0..1 on a level's cells (float64): for each set {'strike_deg' (compass: the lines'
    direction), 'spacing_m', 'width_m' (the weathered zone; at least 1.5 cells, so coarse levels see a fuzzy band),
    'wiggle_m' (the lines' waver, default 0.15 spacing), 'segment_m' (the length over which a line fades in and
    out, default 3 spacings), 'strength' (1)} a Gaussian ridge along every line, broken into segments; the sets
    combine by max. The layered-rock stage multiplies K by (1 + joint_gain x this): incision and weathering run
    faster along the joints, so escarpments fray into fingers and blocks with straight sides, and promontories part
    into mesas and buttes along them."""
    x, y = level.xy()
    out = np.zeros((level.n, level.n))
    for k, js in enumerate(sets or ()):
        spacing = max(float(js.get('spacing_m', 500.0)), 4.0 * level.cell)
        a = math.radians(float(js.get('strike_deg', 0.0)))
        u = (x * math.cos(a) - y * math.sin(a)) / spacing           # across the lines (they run along sin a, cos a)
        wig = float(js.get('wiggle_m', 0.15 * spacing))
        if wig:
            u = u + 3.0 * wig / spacing * FL._field({'kind': 'fbm', 'wavelength_m': 2.0 * spacing, 'octaves': 3,
                                                     'seed': 701 + 13 * k}, level, seed, dev)
        d = np.abs(u - np.round(u)) * spacing
        w = max(float(js.get('width_m', 20.0)), 1.5 * level.cell)
        line = np.exp(-(d / w) ** 2)
        seg = FL._field({'kind': 'fbm', 'wavelength_m': float(js.get('segment_m', 3.0 * spacing)), 'octaves': 2,
                         'seed': 733 + 13 * k}, level, seed, dev)
        seg = np.clip((seg + 0.15) / 0.3, 0.0, 1.0)
        out = np.maximum(out, float(js.get('strength', 1.0)) * line * seg)
    return out


def _noise_m(scales, level, seed, dev, base):
    """Roughness in metres: [[wavelength_m, amp_m], ...] as fbm (amp the standard deviation), scales the level
    resolves only."""
    out = np.zeros((level.n, level.n))
    for k, (wl, amp) in enumerate(scales or ()):
        if float(amp) == 0.0 or float(wl) < 3.0 * level.cell:
            continue
        f = FL._field({'kind': 'fbm', 'wavelength_m': float(wl), 'octaves': 4, 'seed': base + k}, level, seed, dev)
        out = out + 3.0 * float(amp) * f
    return out


# =================================================================================================== the ops ===

def op_strata(fields, level, params, seed=0, ctx=None):
    """Stage 'strata' (module doc): the column spec into ctx.shared['strata'] for the level's later stages, and zs.
    params: column (a COLUMNS name or a list of layers), zs0_m, dip_deg, azimuth_deg, warp, faults, dz_m, seed."""
    ctx = ctx or FL.standalone_context(fields, level)
    sp = strata_spec(params)
    col = column(sp['column'], float(sp['dz_m']), int(sp.get('seed', 0)))
    ctx.shared['strata'] = sp
    if 'h' in fields:
        fields['zs'] = zs_field(fields['h'], sp, level, seed, ctx.device)
    ctx.log(f"[terrain.strata] column {col.name} ({col.top_m:g} m, {len(col.layers)} formations, "
            f"{len(col.fine)} beds), dip {sp['dip_deg']} deg toward {sp['azimuth_deg']} deg")
    return fields


PLATEAU_DEFAULTS = dict(surface_zs_m=None, height_m=0.0, follow_strata=True, tilt_deg=0.0, tilt_azimuth_deg=0.0,
                        roughness=((3000.0, 6.0), (600.0, 2.5), (120.0, 0.8)), edge=None, edges=())


def plateau_surface(level, params, seed=0, dev=None, strata=None):
    """The start of 'plateau' on a level's cells (float64): a structural surface at surface_zs_m (following the
    beds' dip and warp) or a plane at height_m tilted tilt_deg (rising toward tilt_azimuth_deg, counter-clockwise from
    +x), plus roughness ([[wavelength_m, amp_m], ...]) and optional escarpments, `edge` (one) or `edges` (a list):
    {'through': [x, y], 'strike_deg' (compass), 'drop_m', 'width_m', 'wiggle_m', 'wiggle_wavelength_m'}: the
    ground to the right of the strike direction lies drop_m lower, the fall spread over width_m. Each edge's wiggle
    has its own noise (a badlands wall standing between an upper and a lower prairie is two edges)."""
    p = dict(PLATEAU_DEFAULTS)
    p.update(params or {})
    x, y = level.xy()
    s = int(seed) + int(p.get('seed', 0))
    if p.get('surface_zs_m') is not None and p.get('follow_strata', True):
        if strata is None:
            raise ValueError("stage 'plateau' with surface_zs_m needs the 'strata' stage before it")
        h = float(p['surface_zs_m']) + offset(strata, level, seed, dev)
    else:
        az = math.radians(float(p.get('tilt_azimuth_deg', 0.0)))
        h = float(p.get('height_m', 0.0)) + math.tan(math.radians(float(p.get('tilt_deg', 0.0)))) * (
            x * math.cos(az) + y * math.sin(az))
    h = h + _noise_m(p.get('roughness'), level, s, dev, 601)
    edges = ([p['edge']] if p.get('edge') else []) + list(p.get('edges') or [])
    for k, e in enumerate(edges):
        ax, ay = (float(v) for v in e.get('through', (0.0, 0.0)))
        st = math.radians(float(e.get('strike_deg', 90.0)))
        ux, uy = math.sin(st), math.cos(st)
        side = (x - ax) * uy - (y - ay) * ux                    # > 0 right of the strike direction
        wig = float(e.get('wiggle_m', 0.0))
        if wig:
            side = side + 3.0 * wig * FL._field({'kind': 'fbm', 'wavelength_m': float(e.get('wiggle_wavelength_m',
                                                                                          2000.0)),
                                                 'octaves': 4, 'seed': 641 + 7 * k}, level, s, dev)
        w = max(float(e.get('width_m', 200.0)), 1e-6)
        t = np.clip(side / w + 0.5, 0.0, 1.0)
        h = h - float(e.get('drop_m', 100.0)) * t * t * (3.0 - 2.0 * t)
    return h


def op_plateau(fields, level, params, seed=0, ctx=None):
    """Stage 'plateau' (plateau_surface): the start surface, on a fresh level only (a level that inherited one keeps
    it). Writes h and bed (all rock)."""
    ctx = ctx or FL.standalone_context(fields, level)
    if not ctx.fresh and 'h' in fields and np.any(np.asarray(fields['h'])):
        return fields
    sp = ctx.shared.get('strata')
    h = plateau_surface(level, params, seed, ctx.device, sp)
    fields['h'] = h.astype(F32)
    fields['bed'] = h.astype(F32)
    if sp is not None:
        fields['zs'] = zs_field(h, sp, level, seed, ctx.device)
    ctx.log(f"[terrain.strata] plateau start on {level.n}^2 @ {level.cell:.3g} m: {float(h.min()):.0f}.."
            f"{float(h.max()):.0f} m")
    return fields


FLUVIAL_DEFAULTS = dict(U_m_per_yr=0.0, threshold_iters=3, threshold_rate=0.12, repose_deg=34.0, later='refine',
                        later_frac=0.25, pin_every=8, caprock_zs_m=None, caprock_target=None, check_every=40,
                        roughness=0.3, deposition=0.5, weather_m_per_yr=0.0, weather_slope_deg=30.0,
                        weather_loose=2.0, weather_area=0.0, weather_refine=0.0, weather_loose_refine=0.5,
                        joints=(), joint_gain=0.0, resist=0.0, resist_scales_m=(1400.0, 600.0), edge_follow=True)


def _q(params, key):
    if key in (params or {}) and params[key] is not None:
        return params[key]
    if key in FLUVIAL_DEFAULTS:
        return FLUVIAL_DEFAULTS[key]
    return FL._p(params, key)


def op_strata_fluvial(fields, level, params, seed=0, ctx=None):
    """Stage 'strata_fluvial' (module doc): the coarsest level's first pass grows the landform under the base-level
    fall; its later passes, and every finer level, refine it under the low-pass lock with the channel at its final
    bed."""
    ctx = ctx or FL.standalone_context(fields, level)
    dev = ctx.device or FL.device()
    t0 = time.perf_counter()
    lv = level
    n = lv.n
    cell = float(lv.cell)
    p = dict(params or {})
    for k in ('roughness', 'deposition'):
        p.setdefault(k, FLUVIAL_DEFAULTS[k])
    sp = _strata_of(p, ctx)
    col = column(sp['column'], float(sp['dz_m']), int(sp.get('seed', 0)))
    s = int(seed) + int(p.get('seed', 0))
    if 'h' not in fields:
        raise ValueError(f"stage 'strata_fluvial' on {lv}: no height yet (put a 'plateau' stage before it)")
    zoff = offset(sp, lv, seed, dev)
    h = np.asarray(fields['h'], F32)
    main = ctx.main
    main_cell = float(main.cell) if main is not None else cell
    depth = ctx.depth
    first = ctx.role == 'grow' and ctx.fresh and ctx.prepass in (None, 0)
    later = ctx.role == 'grow' and not first
    refine = ctx.role == 'refine' or (later and _q(p, 'later') == 'refine')

    # the inputs (world functions; the column's K(zs) and threshold come from the tables in the kernels)
    K = FL.erodibility(lv, p, s, dev)
    if 'K_factor' in fields:
        K = K * np.asarray(fields['K_factor'], np.float64)
    if p.get('joints') and float(_q(p, 'joint_gain')) > 0:
        K = K * (1.0 + float(_q(p, 'joint_gain')) * joint_field(lv, p['joints'], s, dev))
    if float(_q(p, 'resist')) > 0:
        # resistant patches: K x exp(-resist n), n unit noise at resist_scales_m (clipped at 2.5 sigma); a retreating
        # escarpment leaves the strong patches behind as outliers (mesas, buttes)
        sc = FL._scales(_q(p, 'resist_scales_m'), lv.cell, 3.0)
        if sc:
            nz = np.clip(FL._unit_noise(sc, lv, s, dev, 811), -2.5, 2.5)
            K = K * np.exp(-float(_q(p, 'resist')) * nz)
    U = np.full((n, n), float(_q(p, 'U_m_per_yr')))
    G = np.full((n, n), float(_q(p, 'deposition')))
    rigid = FL._sea_flat(fields, ctx, (n, n))
    if rigid.any():
        U = np.where(rigid, 0.0, U)
        K = np.where(rigid, 0.0, K)
    Sc_now = col.tan_at(h - zoff)
    par = T.rgba(U, K, Sc_now, G)

    # pins: the level's (edge or border band), and the river's channel
    base = ctx.pins if ctx.pins is not None else FL.edge_pins(n, h, ctx.sea_level)
    rv = ctx.shared.get('river')
    chan_cache = {}
    if isinstance(rv, RV.River):
        # (on a child level the river_path stage already eased the channel into the parent's at the border band:
        # hold keeps that, since its weight is 1 on the channel there)
        pins, chan = rv.pins(lv, base, 0.0 if first else 1.0, chan_cache,
                             hold=base['pin_w'] if ctx.role == 'refine' else None)
    else:
        pins, chan = base, None

    D, spacing = FL.diffusivity(p, cell, depth, main_cell)
    if ctx.role == 'refine':
        dt = float(FL._p(p, 'dt_ref_yr')) * max(cell, main_cell) / FL.CELL_REF_M
        steps = int(p.get('steps', FL._p(p, 'refine_steps')))
    else:
        dt = float(FL._p(p, 'dt_ref_yr')) * cell / FL.CELL_REF_M
        if first:
            dur = float(FL._p(p, 'age_myr')) * 1e6
        else:
            dur = float(ctx.shared.get('strata_years', float(FL._p(p, 'age_myr')) * 1e6)) * float(_q(p, 'later_frac'))
        steps = int(p.get('steps', round(dur / dt)))
    steps = int(np.clip(steps, int(FL._p(p, 'min_steps')), int(FL._p(p, 'max_steps'))))
    cap = float(FL._p(p, 'creep_cap'))
    n_sub, D_used = FL.creep_substeps(dt, cell, D, cap, int(FL._p(p, 'max_creep_sub')))
    lock, lock_b, lock_m = None, 2, None
    if refine and FL._p(p, 'lock'):
        if ctx.role == 'refine':
            pl = ctx.plan[ctx.plan[ctx.index].parent] if (ctx.plan and ctx.plan[ctx.index].parent is not None) else None
            pcell = float(pl.cell) if pl is not None else 2.0 * cell
            pdepth = getattr(pl, 'depth', depth + 1)
        else:
            pcell, pdepth = 2.0 * cell, depth                  # the previous coarse-to-fine pass
        lock_m = float(p['lock_m']) if p.get('lock_m') is not None else \
            FL.LOCK_SCALE * FL.diffusivity(p, pcell, pdepth, main_cell)[1]
        lock_b = FL.lock_block(lock_m, cell, n)
        lock = h
    # weathering grows the landform (the walls' retreat); on the passes under the low-pass lock the rock's only
    # fought the lock (which raised the plateau beside a retreating wall into bumps), so there it is scaled by
    # weather_refine; the loose cover's goes on (x weather_loose_refine), or the debris of every failing bed draped
    # the cliffs below it at 34 degrees and the walls rendered as smooth banded slabs
    W0 = float(_q(p, 'weather_m_per_yr'))
    wf = float(_q(p, 'weather_refine')) if refine else 1.0
    wl = W0 * float(_q(p, 'weather_loose')) * (float(_q(p, 'weather_loose_refine')) if refine else 1.0)
    weather = (wf * W0, math.tan(math.radians(float(_q(p, 'weather_slope_deg')))), float(FL._p(p, 'K')), wl,
               float(_q(p, 'weather_area')))
    run = StrataRun(dev, cell, fields, par, pins, col, zoff, lock, lock_b,
                    math.tan(math.radians(float(_q(p, 'repose_deg')))), weather)
    iters = int(_q(p, 'threshold_iters'))
    rate = float(_q(p, 'threshold_rate'))
    mexp, nexp, pexp = float(FL._p(p, 'm')), float(FL._p(p, 'n')), float(FL._p(p, 'p'))
    slope_mode = {'dinf': 1, 'd8': 0}[FL._p(p, 'slope')]
    pit = 1 if FL._p(p, 'fill_pits') else 0
    peps = float(FL._p(p, 'pit_eps_m'))
    pin_every = max(int(_q(p, 'pin_every')), 1)
    target = _q(p, 'caprock_target')
    cap_zs = _q(p, 'caprock_zs_m')
    check = max(int(_q(p, 'check_every')), 1)
    falling = first and isinstance(rv, RV.River)
    # the coarsest level's outer ring follows the ground inside it down (never up) while the landform grows: held at
    # the starting plateau it stood as a one-cell wall up to 1 km tall where the canyon reached the tile's edge (a
    # white sliver on the horizon); badlands keep their prairies' edges as fixed base levels (edge_follow False)
    # (the coarsest level: no parent; ctx.pins is set by then, by the river_path stage)
    coarsest = not ctx.plan or ctx.plan[ctx.index].parent is None
    follow = first and coarsest and bool(_q(p, 'edge_follow'))
    ring = None
    if follow:
        ring = np.zeros((n, n), bool)
        ring[0, :] = ring[-1, :] = ring[:, 0] = ring[:, -1] = True
        base = dict(base, pin_h=np.array(base['pin_h'], F32, copy=True))
    history = []
    done = steps
    f_now = 0.0 if falling else 1.0
    for i in range(steps):
        if (falling or follow) and i % pin_every == 0:
            moved = False
            if follow and i > 0:
                inner = _ring_inner(run.height())
                lower = ring & (inner < base['pin_h'])
                if lower.any():
                    base['pin_h'][lower] = inner[lower]
                    moved = True
            f = RV.schedule_at(rv.schedule, i / max(steps - 1, 1)) if falling else 1.0
            if f != f_now or i == 0 or moved:
                f_now = f
                pins = rv.pins(lv, base, f, chan_cache)[0] if isinstance(rv, RV.River) else base
                run.set_pins(pins)
        run.step(dt, D_used, n_sub, iters, rate, cap, mexp, nexp, pexp, slope=slope_mode, pit_fill=pit,
                 pit_eps=peps)
        if first and target is not None and cap_zs is not None and (i + 1) % check == 0 and f_now >= 0.999:
            frac = caprock_fraction(run.height(), zoff, lv, main, cap_zs)
            history.append((i + 1, round(frac, 4)))
            if frac <= float(target):
                done = i + 1
                break
    out = run.readback()
    if first:
        ctx.shared['strata_years'] = done * dt
    for k in ('h', 'A', 'qs', 'wear', 'deposit', 'talus'):
        fields[k] = out[k]
    fields['bed'] = out['h'] - out['loose']
    zs = np.asarray(out['h'], np.float64) - zoff
    fields['zs'] = zs.astype(F32)
    fields['U'] = U.astype(F32)
    fields['K'] = (K * col.k_at(zs)).astype(F32)
    fields['Sc'] = col.tan_at(zs).astype(F32)
    fields['G'] = G.astype(F32)
    if chan is not None:
        fields['river'] = chan.astype(F32)
    ctx.evolved = True
    rec = dict(level=str(lv), prepass=ctx.prepass, role='first' if first else ('refine' if refine else 'evolve'),
               steps=done, dt_yr=round(dt, 2), years=round(done * dt), D=D_used, spacing_m=round(spacing, 1),
               creep_sub=n_sub, lock_block_cells=lock_b if lock is not None else None, lock_m=lock_m,
               caprock=history[-4:], seconds=round(time.perf_counter() - t0, 3))
    if cap_zs is not None:
        rec['caprock_frac'] = round(caprock_fraction(out['h'], zoff, lv, main, cap_zs), 4)
    ctx.shared.setdefault('fluvial_log', []).append(rec)
    ctx.log(f"[terrain.strata] {rec['role']} {n}^2 @ {cell:.3g} m" + (f' (pre-pass {ctx.prepass})'
                                                                    if ctx.prepass is not None else '')
            + f": {done} steps x {dt:.0f} yr, D {D_used:.3g} (valleys {spacing:.0f} m), creep x{n_sub}"
            + (', base level falling' if falling else '')
            + (f", caprock {rec['caprock_frac']:.3f}" if 'caprock_frac' in rec else '')
            + (f', locked above {lock_b} cells ({lock_b * cell:.0f} m)' if lock is not None else '')
            + f", {rec['seconds']} s")
    return fields


op_strata_fluvial.evolves = True
op_strata.evolves = True              # every coarse-to-fine pass: zs on each
OPS = {'strata': op_strata, 'plateau': op_plateau, 'strata_fluvial': op_strata_fluvial}
