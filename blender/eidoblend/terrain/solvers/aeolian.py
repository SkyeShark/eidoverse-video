"""Wind and sand: dunes from Werner's slab model on the GPU (design section 4.6).

The model (Werner 1995, with the numbers of Paris et al. 2019's Desertscapes code), on two layers: `bed` (rock, which
the wind does not touch here) and `sand` (thickness, metres); the surface is h = bed + sand. One iteration:

  1. shadow     every cell's wind shadow: the steepest angle up to the ground upwind of it within `shadow_reach`
                cells, ramped from 0 at shadow_lo_deg to 1 at shadow_deg (Werner's 15-degree line); and its `rise`
                for the speed-up (the sand's thickness)                             kernels/dune_shadow.glsl
  2. activate   a random share of the cells with sand (a PCG hash of cell, iteration and seed) lift one slab, none in
                a shadow: p_lift x (1 + lift_boost x f), f growing with the sand's thickness from speed_from_m to
                speed_ref_m (the wind speeds up over a dune toward its crest, Momiji et al. 2000; without it Werner's
                dunes stand steep on both sides); each picks an integer hop vector by stochastic rounding of the
                real one (any wind direction on average, no grid-locked crests) and follows it for up to `max_hops`
                hops, depositing with probability shadow + (1 - shadow) x (p_sand on sand, p_rock on bare rock),
                always at the last                                                  kernels/dune_activate.glsl
  3. transport  the same move as a GATHER: a cell adds every slab whose recorded path ends on it (no atomics, so
                deterministic and exactly mass-conserving)                          kernels/dune_transport.glsl
  4. avalanche  sand steeper than the angle of repose (tan 0.60, 31 degrees, the Desertscapes value) slides to the
                lower neighbour, a symmetric pair exchange over 16 neighbours (the 8 and the knight's moves, so slip
                faces stand at one angle whichever way they face) limited by the upper cell's own sand, so bare rock
                never moves and mass is conserved; `aval_passes` per iteration      AVALANCHE_SRC (this module)
The slab noise (single slabs arriving and leaving: a cell-scale speckle the shadow rule bounds at about 0.15 cells; a
creep strong enough to clear it during the run flattens the dunes too) is cleared at the end of a run by reading the
sand time-averaged over the run's last `average_iters` iterations (SandSim.run_averaged: the speckle decorrelates in
tens of iterations while a dune moves a fraction of a cell in hundreds, so crests and brinks stay as sharp as the
cells draw them), then a Gaussian of `smooth_cells` (alone, without the average, it rounds a crest by a cell).

The avalanche is a fourth kernel kept as source text here (core/world_noise.py keeps its field kernel the same way):
the design names "the threshold kernel" (package 3's threshold.glsl), but that limit is the pair's mean Sc, which
would hold sand against bare rock at the mean of 31 and 68 degrees; on the sand layer the limit is the upper cell's
material and only its sand can move. Rock never moves in this solver (no abrasion), so the design's rock limit (tan
2.5) has nothing to act on.

Frames and units (design 2.1): arrays [row j, column i], row 0 the south edge, x east and y north; metres, degrees;
winds are compass degrees the wind blows FROM (meteorological: 225 is a south-westerly, the sand moves north-east).
Numerical lengths of the slab model are in cells (the hop, the shadow reach) or fractions of a cell (the slab), so
every level runs the same model at its own scale: a coarse level grows the big dunes, a fine level sharpens their
crests and grows the small dunes on their flanks.

The wind regime is a list of (from_deg, weight), cycled in blocks of `block` iterations per wind (a wind's block is
weighted by its share, its direction jittered by up to `jitter_deg`), each run ending on a whole cycle. With `gust`
and `spread_deg` a block blows as gusts of `gust` iterations, each from its wind's direction plus a normal scatter of
spread_deg: a season's wind wanders, and one direction held for a whole block builds planar slip faces meeting in
straight arms at the regime's fixed angles, where a wandering one curves the faces and the crests. Which dunes
form is the regime and the sand supply, not a shape parameter (Rubin & Hunter 1987, Courrech du Pont et al. 2014,
Zhang et al. 2012): one wind and thin sand make barchans; one wind and a sand sheet transverse ridges; two winds more
than 90 degrees apart linear dunes; three or more of similar weight star dunes. KINDS holds each with its sand,
spacing, bed and its calibration of the model (barchans and linear dunes run Werner's original rule without the
speed-up, which would spread their thin sheets; star dunes blow each wind 1000 iterations at a time and grow 90 cells
across, calibrated on the Namib).

A dune field over a level stack (op 'dune_field', design 4.6 "Scale"): Werner dunes need dozens of cells across a
dune, and the time to grow them goes as 1 / cell^2, so the field is grown ONCE, periodic, on the coarsest level that
resolves the target spacing with `cells_per_spacing` cells (the growth level; the recipe's prepare hook records the
level stack so every level's op finds it). Its start is world-space noise: a gently rolling bed, the sand supply
(thinner and thicker sheets, `supply_var`; drawn out along `supply_axis_deg` by `supply_stretch_m` so the bare floor
where it runs out is a long pan, and capped at `supply_cap` x the mean), and a seed at `seed_scale` x the target
spacing (`seed_frac` of the target height), all periodic over the growth window. It runs `grow_iters` iterations (the model is scale-free in
cells, so one count is one maturity; `grow_phases` can run model changes in turn). Coarser levels average the
periodic field over their cells (a context window larger than the growth window repeats it); finer levels start
from their parent (the level runner's inherit) and run `refine_iters` more iterations at their own cell with their
border band pinned to the parent, which sharpens the crests and slip faces and grows small dunes on the big ones:
under the whole regime (`refine_winds` 'cycle') or its last season only ('last': the big dunes keep the forms the
whole regime built, and the finer cells show the latest season's fresh slip faces and brinks on them).

    from eidoblend.terrain.solvers import aeolian as A
    sim = A.SandSim(bed, sand, cell=5.0, bound=A.T.BOUND_PERIODIC, params={'hop_cells': 3}, seed=1)   # GPU
    sim.run(A.KINDS['transverse']['winds'], iterations=4000)
    bed, sand = sim.read()
    tw = A.TwinSim(bed, sand, cell=5.0, ...)              # the same model on the numpy twins (tests, 64-128 cells)

Twins: dune_shadow, dune_activate, dune_transport, dune_avalanche (registered with core/twins.py on import);
scatter_step is the scatter the transport gather replaces, for the gather test.
"""
from __future__ import annotations

import hashlib
import json
import math
import time

import numpy as np

from ..core import grid as _grid
from ..core import twins as T

# ------------------------------------------------------------------------------------------------ parameters ---

DEFAULTS = dict(
    slab_cells=0.1,          # slab thickness as a fraction of the cell: one slab step is a 5.7-degree slope
    hop_cells=3.0,           # saltation hop, cells (the smallest dunes are some ten hops long)
    lift_boost=15.0,         # the wind's speed-up over a dune: lifting grows to p_lift x (1 + lift_boost) between
                             # speed_from_m and speed_ref_m of sand, so the flux grows all the way up the stoss and
                             # the stoss stays gentle (Momiji et al. 2000); 0: Werner's original, steep both sides
    rise='sand',             # what the speed-up grows with: 'sand' (the sand's thickness, Momiji's height) or
                             # 'upwind' (height above the lowest ground within the shadow's reach; saturates there)
    speed_from_m=5.0,        # 'sand': the speed-up starts at this thickness (a thinner sheet is not a dune) ...
    speed_ref_m=40.0,        # ... and is full at this one (a dune field derives both from its target height)
    speed_ref_deg=10.0,      # 'upwind': the full rise is a stoss of this angle over the shadow's reach
    speed_pow=1,             # the speed-up grows as f^speed_pow (an integer): 2 or 3 make it grow faster toward the
                             # crest, so a dune's top outruns its base and its flanks stretch into broad aprons
    long_factor=1.0,         # the speed-up as a longer hop as well: the long hop, a multiple of the short (1: off;
                             # long hops overshoot a small dune's shadow, so barchans and linear ridges dissolve)
    speedup=0.0,             # the long hop's chance at full speed-up
    max_hops=3,              # hops before a slab must deposit (design 4.6)
    p_lift=0.02,             # chance a sand cell lifts a slab per iteration where the wind has no speed-up (on a
                             # dune's upper stoss it rises to p_lift x (1 + lift_boost): the design's 5-10 % and more)
    p_sand=0.6,              # deposition chance on sand (Desertscapes)
    p_rock=0.4,              # deposition chance on bare rock (Desertscapes)
    min_sand_slabs=0.25,     # sand thinner than this many slabs is bare rock
    shadow_deg=15.0,         # Werner's shadow line
    shadow_lo_deg=10.0,      # where the shadow ramp starts (equal to shadow_deg: Werner's step)
    shadow_reach=20,         # cells upwind the shadow looks (design: 20)
    repose_deg=31.0,         # sand's angle of repose: tan 0.60 (Desertscapes)
    aval_rate=0.06,          # pair exchange per avalanche pass: a share of the excess height over the pair's length
                             # in cells (16 neighbours: their rates sum to about 0.6, below the overshoot of a spike)
    creep=0.0,               # linear creep per avalanche pass, a share of each height difference (isotropic
                             # weights). Off: any rate that clears the slab noise also flattens the dunes
    aval_passes=4,           # avalanche passes per iteration
    smooth_cells=1.0,        # after a run, the slab noise (a cell-scale speckle the shadow rule bounds at ~0.15
                             # cells) is cleared by a Gaussian of this many cells on the sand (0: none)
    block=200,               # iterations per wind block (design 4.6)
    jitter_deg=8.0,          # each block's direction varies by up to this much (real winds wander; it also keeps
                             # crests from locking to a lattice direction)
    gust=0,                  # > 0: a block blows as gusts of this many iterations ...
    spread_deg=0.0,          # ... each from the block's direction plus a normal scatter of this many degrees
    steer_deg=0.0,           # the regional relief steers each wind (Steering): the local turn's standard deviation,
                             # degrees, a different pattern per wind direction (a wind and its reverse alike) ...
    steer_turn_deg=0.0,      # ... plus one turn every wind shares (the whole regime turns across the field), degrees
)

# The dune kinds (design 4.6's table): the wind regime as (from_deg, weight), and the sand and spacing they want.
# The regimes are absolute compass directions; a recipe rotates them with wind_rotate_deg.
KINDS = {
    'star': dict(winds=[(28.0, 1.0), (148.0, 0.75), (268.0, 0.55)], sand_m=45.0, spacing_m=1400.0, bed_m=20.0,
                 model=dict(cells_per_spacing=60.0, lift_boost=25.0, p_lift=0.02, speed_from_frac=0.06,
                            speed_ref_frac=1.0, speed_pow=2, aval_passes=14, grow_iters=24000, grow_min_iters=24000,
                            grow_check=6000, block=1000, seed_scale=1.5, gust=100, spread_deg=30.0,
                            steer_deg=35.0, steer_wavelength_m=2000.0, supply_var=0.6, supply_wavelength_m=4000.0,
                            supply_stretch_m=1500.0, supply_axis_deg=90.0, supply_cap=1.3, average_iters=400,
                            smooth_cells=0.5, sheet_smooth_cells=2.0, refine_winds='last', refine_iters=400,
                            refine_block=400, refine_average_iters=200, hero_winds='last2', hero_iters=1200,
                            hero_block=150, hero_average_iters=100),
                 doc='three winds 120 degrees apart of unequal weight: star dunes with curving arms in masses of '
                     'sand, long bare pans between the masses (calibrated on the Namib at Sossusvlei: spacing 1.4 km, '
                     '45 m of sand on a gently rolling plain; the winds off the grid axes, as real winds are). The '
                     'arms: each wind is a season of 1000 iterations blowing as gusts of 100 that wander 30 degrees '
                     'about its direction, and the regional relief steers every wind by a smooth turn (35 degrees '
                     'standard deviation over 2 km) that differs from wind to wind (Steering), so each dune sees its '
                     'own regime and its arms curve and meet at varying angles (one direction held for a season '
                     'everywhere built planar faces meeting in three straight arms at a fixed 120 degrees: the 11-12 '
                     'review; the slopes\' 3-fold aspect harmonic falls from 0.3-0.6 to the Namib\'s 0.06-0.08). The '
                     'flanks: the speed-up grows as the square of its ramp (speed_pow 2) between 21 m of sand and the '
                     'target height, at 0.02 x (1 + 25 f^2) a slab an iteration, so a dune\'s top outruns its base and '
                     'its flanks stretch into broad aprons under a sharp crest zone, the Namib\'s 5-20 degree ground '
                     '(a linear speed-up only carries each face along at its angle: pyramids at repose, every dune '
                     '400 m tall). The pans: the supply varies 60 % over 4 km, drawn out east-west by 1.5 km '
                     '(stretch_periodic) and capped at 1.3 x the mean, so where the sand runs out the floor is a long '
                     'smooth pan, as Sossusvlei\'s are, and no mass grows a dune above the Namib\'s; the thin sand is '
                     'smoothed and its margins thin out onto the floor (smooth_sheet: kept as it stood, it was a '
                     'speckled table with a step at its edge, the review\'s straight-edged plates and pitted sand). '
                     '14 avalanche passes an iteration hold the slip faces at 31-33 degrees (8 left them at 34-37). '
                     'The sand is read time-averaged over each run\'s last iterations (the slab speckle goes, crests '
                     'stay sharp). The main level blows the last season only, 400 iterations: every crest a sharp brink '
                     'above a fresh slip face (longer, every face turns to that one wind). The hero levels around a '
                     'camera blow the last two seasons in turns of 150 iterations (refine_winds \'last2\'), which '
                     'reverses the crest zone: arms steep on both sides, knife-edges above the broad flanks, ribs and '
                     'small dunes on the flanks (one season left a brink over a gentle stoss, a rounded shoulder at '
                     '1.7 m; a whole cycle re-planes each big dune into a pyramid of straight-edged facets). The dunes '
                     'grow 90 cells across'),
    'barchan': dict(winds=[(225.0, 1.0)], sand_m=2.5, spacing_m=250.0, bed_m=1.5,
                    model=dict(lift_boost=0.0, p_lift=0.075),
                    doc='one wind, thin sand on a bare plain: crescents with horns downwind. The thin sheet must '
                        'gather into dunes before any speed-up, so barchans run Werner\'s original rule'),
    'transverse': dict(winds=[(225.0, 1.0)], sand_m=5.0, spacing_m=120.0, bed_m=1.5,
                       model=dict(speed_from_frac=0.0, speed_ref_frac=4.0),
                       doc='one wind, a continuous sand sheet: ridges across the wind, slip faces downwind (White '
                           'Sands: 5 m of sand on a flat plain)'),
    'linear': dict(winds=[(120.0, 1.0), (240.0, 1.0)], sand_m=45.0, spacing_m=2000.0,
                   model=dict(lift_boost=0.0, p_lift=0.075),
                   doc='two winds 120 degrees apart: long ridges along their resultant, slip faces flipping side '
                       'to side (the Namib south of Gobabeb); symmetric in section, so Werner\'s original rule'),
}
# Each kind's `model` is its calibration of the slab model (DEFAULTS and FIELD_DEFAULTS keys), applied unless the
# caller gives the key. The speed-up's proxy (sand thickness) cannot tell a sheet that is gathering into dunes from a
# dune: under it a thin sheet spreads instead of heaping into barchans, and two crossing winds leave a sheet with a
# few dunes on it instead of ridges, so barchans and linear dunes run Werner's original rule (linear dunes are
# symmetric in section anyway: their slip faces flip side to side); transverse ridges start the speed-up at the toe.

LOG_PREFIX = '[terrain.aeolian]'


def params_for(params=None):
    """DEFAULTS with `params` over them (unknown keys are kept for the dune field's own use)."""
    p = dict(DEFAULTS)
    p.update(params or {})
    return p


# ---------------------------------------------------------------------------------------------- the wind ---

def transport_dir(from_deg):
    """The unit (x east, y north) direction sand moves in a wind blowing FROM compass `from_deg`."""
    a = math.radians(float(from_deg))
    return np.array([-math.sin(a), -math.cos(a)], np.float64)


def normalise_winds(winds):
    """[(from_deg, weight), ...] with positive weights, from pairs, dicts {'from_deg', 'weight'} or bare angles."""
    out = []
    for w in winds:
        if isinstance(w, dict):
            d, wt = float(w['from_deg']), float(w.get('weight', 1.0))
        elif isinstance(w, (int, float)):
            d, wt = float(w), 1.0
        else:
            d, wt = float(w[0]), float(w[1]) if len(w) > 1 else 1.0
        if wt < 0:
            raise ValueError(f'wind weight {wt} is negative')
        if wt > 0:
            out.append((d % 360.0, wt))
    if not out:
        raise ValueError('a wind regime needs at least one wind with a positive weight')
    return out


def cycle_blocks(winds, block):
    """One cycle of the regime: [(from_deg, iterations), ...], each wind's block its weighted share of
    block x (number of winds) iterations, at least 1."""
    winds = normalise_winds(winds)
    tot = sum(w for _, w in winds)
    n = len(winds)
    return [(d, max(1, int(round(block * n * w / tot)))) for d, w in winds]


def schedule(winds, iterations, block, jitter_deg=0.0, seed=0, gust=0, spread_deg=0.0, with_wind=False):
    """[(from_deg, iterations), ...] covering at least `iterations`, in whole cycles of the regime. Each block's
    direction varies by up to jitter_deg (deterministic per seed). With gust > 0 and spread_deg > 0 a block blows as
    gusts of `gust` iterations, each from the block's direction plus a normal scatter of spread_deg (a real wind
    wanders continuously around its season's direction: one direction held for a whole block builds planar slip
    faces meeting in straight arms; a wandering one curves the faces and the crests). with_wind: triples
    (from_deg, iterations, the regime's own direction for that wind), the direction the steering is keyed on."""
    blocks = cycle_blocks(winds, block)
    per = sum(b for _, b in blocks)
    cycles = max(1, int(math.ceil(int(iterations) / per)))
    rng = np.random.default_rng((int(seed) * 7919 + 17) & 0xFFFFFFFF)
    out = []
    for _c in range(cycles):
        for d, b in blocks:
            j = float(rng.uniform(-1.0, 1.0)) * float(jitter_deg) if jitter_deg else 0.0
            if gust and spread_deg and int(gust) < b:
                left = b
                while left > 0:
                    g = min(int(gust), left)
                    out.append(((d + j + float(rng.normal(0.0, float(spread_deg)))) % 360.0, g, d))
                    left -= g
            else:
                out.append(((d + j) % 360.0, b, d))
    return out if with_wind else [(d, b) for d, b, _w in out]


def schedule_length(sched):
    return sum(s[1] for s in sched)


def hop_box(hop, long_f=1.0, turn=(0.0, 0.0)):
    """The integer hop vectors any source can pick (dune_activate's stochastic rounding of its hop, turned by its
    cell's local angle): ((vx_min, vy_min), (vx_max, vy_max)), the box dune_transport gathers over. hop: the short hop
    (cells, float32 as the kernels see it); long_f: the long hop's multiple (> 1: long hops too); turn: the least and
    the most the steering turns this wind anywhere on the grid, radians."""
    hx, hy = float(np.float32(hop[0])), float(np.float32(hop[1]))
    r0, phi = math.hypot(hx, hy), math.atan2(hy, hx)
    lo, hi = float(turn[0]), float(turn[1])
    ang = np.array([0.0]) if hi <= lo else np.concatenate([np.linspace(lo, hi, 129), [lo, hi]])
    for ax in (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi, 2.0 * math.pi, -0.5 * math.pi, -math.pi):
        a = ax - phi                                   # an axis crossing inside the range sets that component's extreme
        if lo < a < hi:
            ang = np.append(ang, a)
    lens = [1.0] + ([float(long_f)] if float(long_f) > 1.0 else [])
    xs = np.concatenate([r0 * m * np.cos(phi + ang) for m in lens])
    ys = np.concatenate([r0 * m * np.sin(phi + ang) for m in lens])
    if hi <= lo:                                       # no steering: exactly the kernels' own float32 hops
        xs = np.array([hx] + ([float(np.float32(np.float32(hx) * np.float32(long_f)))] if long_f > 1.0 else []))
        ys = np.array([hy] + ([float(np.float32(np.float32(hy) * np.float32(long_f)))] if long_f > 1.0 else []))
    eps = 1.0e-3                                       # float32 rounding of the turned hop in the kernel
    vmin = (int(math.floor(float(xs.min()) - eps)), int(math.floor(float(ys.min()) - eps)))
    vmax = (int(math.floor(float(xs.max()) + eps)) + 1, int(math.floor(float(ys.max()) + eps)) + 1)
    return vmin, vmax


class Steering:
    """The regional relief's steering of the wind: the turn of its direction at every cell of a grid. A wind the
    regime gives from compass theta is turned by

        delta(x, y, theta) = steer x (n1 cos 2 theta + n2 sin 2 theta) + turn x n3        (radians)

    with n1, n2, n3 smooth world-space fields of unit variance clipped at +-2 (steering_for). The 2 theta turns a wind
    and its reverse alike, as flow steered round relief is; winds from other directions are turned in other
    patterns, so the regime's shape (the angles between its winds) varies across the field as well as its
    orientation: each dune sees its own regime, and a long arm curves as the regime turns along it. turn x n3 turns
    every wind together (the whole regime rotates across the field). for_wind(theta) gives the kernels' `wind` input,
    (cos, sin) of delta as float32 (H, W, 2), and the least and the most turn on the grid (for hop_box)."""

    def __init__(self, n, steer_deg, turn_deg=0.0):
        self.n = np.asarray(n, np.float64)
        if self.n.ndim != 3 or self.n.shape[0] != 3:
            raise ValueError(f'steering fields must be (3, H, W), got {self.n.shape}')
        self.shape = self.n.shape[1:]
        self.steer = math.radians(float(steer_deg))
        self.turn = math.radians(float(turn_deg))
        self._cache = {}

    def angle(self, theta_deg):
        """delta at every cell for a wind from compass theta_deg, radians (float64)."""
        a = math.radians(2.0 * float(theta_deg))
        return self.steer * (self.n[0] * math.cos(a) + self.n[1] * math.sin(a)) + self.turn * self.n[2]

    def for_wind(self, theta_deg):
        """((cos, sin) of delta as float32 (H, W, 2), (least, most) delta in radians), cached per direction."""
        key = round(float(theta_deg) % 360.0, 6)
        if key not in self._cache:
            d = self.angle(key)
            cs = np.ascontiguousarray(np.stack([np.cos(d), np.sin(d)], -1).astype(np.float32))
            if len(self._cache) >= 8:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (cs, (float(d.min()), float(d.max())))
        return self._cache[key]


def uniforms_for(params, cell, from_deg, it, seed, bound, turn=(0.0, 0.0)):
    """The uniforms of the four kernels for one iteration: {kernel: {uniform: value}}. turn: the least and the most
    the steering turns this wind on the grid, radians (Steering.for_wind), for the transport's box of hops."""
    p = params
    d = transport_dir(from_deg)
    hop = d * float(p['hop_cells'])
    slab = float(p['slab_cells']) * float(cell)
    tan_hi = math.tan(math.radians(float(p['shadow_deg'])))
    tan_lo = math.tan(math.radians(min(float(p['shadow_lo_deg']), float(p['shadow_deg']))))
    long_f = max(1.0, float(p['long_factor']))
    rise_mode = 1 if p.get('rise') == 'sand' else 0
    if rise_mode == 1:
        speed_from = float(p['speed_from_m'])
        speed_ref = max(speed_from + 1e-6, float(p['speed_ref_m']))
    else:
        speed_from = 0.0
        speed_ref = max(1e-6, int(p['shadow_reach']) * float(cell) * math.tan(math.radians(float(p['speed_ref_deg']))))
    return {
        'dune_shadow': {'uDir': (float(d[0]), float(d[1])), 'uTanLo': tan_lo, 'uTanHi': tan_hi,
                        'uReach': int(p['shadow_reach']), 'uCell': float(cell), 'uRiseMode': rise_mode,
                        'uBound': int(bound)},
        'dune_activate': {'uHop': (float(hop[0]), float(hop[1])), 'uLong': long_f,
                          'uSpeedup': float(p['speedup']) if long_f > 1.0 else 0.0,
                          'uLiftBoost': float(p['lift_boost']), 'uSpeedFrom': speed_from, 'uSpeedRef': speed_ref,
                          'uSpeedPow': max(1, int(p.get('speed_pow') or 1)),
                          'uSlab': slab, 'uMinSand': float(p['min_sand_slabs']) * slab, 'uPLift': float(p['p_lift']),
                          'uPSand': float(p['p_sand']), 'uPRock': float(p['p_rock']),
                          'uMaxHops': int(p['max_hops']), 'uIter': int(it), 'uSeed': int(seed),
                          'uBound': int(bound)},
        'dune_transport': dict(zip(('uVMin', 'uVMax'), hop_box(hop, long_f, turn)), uMaxHops=int(p['max_hops']),
                               uBound=int(bound)),
        'dune_avalanche': {'uTanRepose': math.tan(math.radians(float(p['repose_deg']))),
                           'uRate': float(p['aval_rate']), 'uCreep': float(p['creep']), 'uCell': float(cell),
                           'uBound': int(bound)},
    }


def check_grid(shape, params, bound):
    """The slab model's limits on a grid: a hop path and the shadow ray must stay within one period."""
    h, w = shape[:2]
    p = params
    reach = (abs(float(p['hop_cells'])) * max(1.0, float(p['long_factor'])) + 1.0) * int(p['max_hops'])
    if bound == T.BOUND_PERIODIC and reach >= min(h, w):
        raise ValueError(f'a periodic grid of {w} x {h} cells is too small for {p["max_hops"]} hops of '
                         f'{p["hop_cells"]} cells')
    if bound == T.BOUND_PERIODIC and int(p['shadow_reach']) + 2 >= min(h, w):
        raise ValueError(f'a periodic grid of {w} x {h} cells is too small for a shadow reach of '
                         f'{p["shadow_reach"]} cells')


# ----------------------------------------------------------------------------------------- the avalanche ---

AVALANCHE_SRC = r'''/* dune_avalanche: sand slides where it is steeper than its angle of repose (design 4.6, step 4), and
   can creep a little everywhere (reptation: grains the saltating ones kick down the slope).
   For each neighbour pair, the higher cell's surface stands above the lower's by more than tan(repose) x the
   distance: a share uRate of that excess moves down; and a share uCreep x WISO[k] of the whole difference creeps down
   (the isotropic 9-point weights, so the creep is a diffusion with no grid direction). The neighbours are the 8 of
   common.glsl and the 8 knight's moves (distance sqrt 5): with 8 directions alone a plane facing 22.5 degrees off
   them stands 8 % steeper than one facing along them, and slip faces lock to the grid's eight directions; with 16
   the most is 2.7 %. Each pair's flow never takes more than a sixteenth of the upper cell's sand (so a cell can never
   give more than it has, and bare rock never moves). Both cells of a pair compute the same flow from the same texels,
   so the exchange is symmetric and sand is conserved exactly. Pins (pin_w, pin_sand) then hold the border band of a
   child level to its parent's sand. Twin: solvers/aeolian.py, twin 'dune_avalanche'. */
//! sampler st                bed (r) and sand thickness (g), metres
//! sampler pins              pin weight (r) 0..1 and pinned sand thickness (g), metres
//! image   outSt rg32f       bed and sand after one pass
//! uniform float uTanRepose  tan of the angle of repose
//! uniform float uRate       share of the excess moved per pass
//! uniform float uCreep      the creep's share of the height difference per pass (0: none)
//! uniform float uCell       metres
//! uniform int uBound        BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED

/* the 8 knight's moves, opposite = 7 - k as in common.glsl's OFF */
const ivec2 KOFF[8] = ivec2[8](ivec2(-2, -1), ivec2(-1, -2), ivec2(1, -2), ivec2(2, -1), ivec2(-2, 1),
                               ivec2(-1, 2), ivec2(1, 2), ivec2(2, 1));
const float KLEN = 2.23606798;

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 s = texelFetch(st, p, 0);
  float hc = s.r + s.g;
  float net = 0.0;
  for (int k = 0; k < 16; k++) {
    ivec2 q = p + (k < 8 ? OFF[k] : KOFF[k - 8]);
    if (uBound == BOUND_PERIODIC) {
      q = wrap(q, n);
    } else if (!inside(q, n)) {
      continue;
    }
    vec4 sq = texelFetch(st, q, 0);
    float hq = sq.r + sq.g;
    float len = k < 8 ? LEN[k] : KLEN;
    float lim = uTanRepose * len * uCell;
    float rate = uRate / len;                    /* the flow follows the pair's SLOPE excess, so a face drains at
                                                    the same rate whichever stencil direction it faces */
    float cw = k < 8 ? uCreep * WISO[k] : 0.0;
    float down = rate * max(hc - hq - lim, 0.0) + cw * max(hc - hq, 0.0);
    float up = rate * max(hq - hc - lim, 0.0) + cw * max(hq - hc, 0.0);
    net += min(up, sq.g * 0.0625) - min(down, s.g * 0.0625);
  }
  vec4 pn = texelFetch(pins, p, 0);
  float sand = pin_apply(s.g + net, pn.r, pn.g);
  imageStore(outSt, p, vec4(s.r, max(sand, 0.0), 0.0, 0.0));
}
'''


# ------------------------------------------------------------------------------------------------- twins ---
# Each twin does its kernel's arithmetic in float32 with whole-array reads, in the kernel's order (core/twins.py).

F32 = np.float32
KOFF = ((-2, -1), (-1, -2), (1, -2), (2, -1), (-2, 1), (-1, 2), (1, 2), (2, 1))   # the avalanche's knight's moves
KLEN = F32(2.23606798)


def _surface(st):
    return (st[..., 0] + st[..., 1]).astype(F32)


def _grid_ij(shape):
    jj, ii = np.mgrid[0:shape[0], 0:shape[1]]
    return ii, jj


def _turn_of(s, shape):
    """The local turn of the wind, (cos, sin) float32 arrays, from the 'wind' input ((1, 0) when there is none)."""
    w = s.get('wind')
    if w is None:
        return np.ones(shape, F32), np.zeros(shape, F32)
    w = np.asarray(w, F32)
    return w[..., 0], w[..., 1]


def _turned(c, sn, x, y):
    """(x, y) turned by the angle whose cosine and sine are c and sn, in float32 as the kernels compute it."""
    return (c * x - sn * y).astype(F32), (sn * x + c * y).astype(F32)


@T.twin('dune_shadow')
def twin_shadow(s, u):
    st = s['st']
    h = _surface(st)
    H, W = h.shape
    ii, jj = _grid_ij(h.shape)
    px, py = ii.astype(F32), jj.astype(F32)
    c, sn = _turn_of(s, h.shape)
    dx, dy = _turned(c, sn, F32(u['uDir'][0]), F32(u['uDir'][1]))
    cell = F32(u['uCell'])
    periodic = int(u['uBound']) == T.BOUND_PERIODIC
    best = np.full(h.shape, F32(-1.0e30), F32)
    lowest = h.copy()
    alive = np.ones(h.shape, bool)
    for d in range(1, int(u['uReach']) + 1):
        fd = F32(d)
        qx = (px - fd * dx).astype(F32)
        qy = (py - fd * dy).astype(F32)
        fx, fy = np.floor(qx), np.floor(qy)
        tx, ty = (qx - fx).astype(F32), (qy - fy).astype(F32)
        ax, ay = fx.astype(np.int64), fy.astype(np.int64)
        bx, by = ax + 1, ay + 1
        if periodic:
            ax, ay, bx, by = ax % W, ay % H, bx % W, by % H
        else:
            alive &= (ax >= 0) & (ay >= 0) & (bx < W) & (by < H)
            ax, bx = np.clip(ax, 0, W - 1), np.clip(bx, 0, W - 1)
            ay, by = np.clip(ay, 0, H - 1), np.clip(by, 0, H - 1)
        h00, h10, h01, h11 = h[ay, ax], h[ay, bx], h[by, ax], h[by, bx]
        one = F32(1.0)
        lo = (h00 * (one - tx) + h10 * tx).astype(F32)               # GLSL mix(a, b, t) = a (1 - t) + b t
        hi = (h01 * (one - tx) + h11 * tx).astype(F32)
        hq = (lo * (one - ty) + hi * ty).astype(F32)
        r = ((hq - h) / (fd * cell)).astype(F32)
        best = np.where(alive, np.maximum(best, r), best)
        lowest = np.where(alive, np.minimum(lowest, hq), lowest)
    lo_t, hi_t = F32(u['uTanLo']), F32(u['uTanHi'])
    sh = np.clip((best - lo_t) / max(hi_t - lo_t, F32(1.0e-6)), 0.0, 1.0).astype(F32)
    out = np.zeros(h.shape + (2,), F32)
    out[..., 0] = sh
    out[..., 1] = st[..., 1] if int(u['uRiseMode']) == 1 else (h - lowest).astype(F32)
    return {'outShadow': out}


def _hop_choice(h, hx, hy):
    """The integer hop vector each source picks by stochastic rounding of its real hop (hx, hy) cells (scalars or
    per-cell float32 arrays): (vx, vy) int64 arrays."""
    hx, hy = np.asarray(hx, F32), np.asarray(hy, F32)
    flx, fly = np.floor(hx), np.floor(hy)
    frx, fry = (hx - flx).astype(F32), (hy - fly).astype(F32)
    vx = flx.astype(np.int64) + (T.u01(T.pcg2(h, 2)) < frx).astype(np.int64)
    vy = fly.astype(np.int64) + (T.u01(T.pcg2(h, 3)) < fry).astype(np.int64)
    return vx, vy


def _hop_vectors(u):
    """The integer hop vectors the transport gather looks at, in its order: the box uVMin..uVMax, x fastest."""
    (x0, y0), (x1, y1) = u['uVMin'], u['uVMax']
    return [(vx, vy) for vy in range(int(y0), int(y1) + 1) for vx in range(int(x0), int(x1) + 1)]


@T.twin('dune_activate')
def twin_activate(s, u):
    st, sh, rise = s['st'], s['shadow'][..., 0], s['shadow'][..., 1]
    sand = st[..., 1]
    H, W = sand.shape
    ii, jj = _grid_ij(sand.shape)
    h = T.cell_hash(sand.shape, int(u['uIter']), int(u['uSeed']))
    span = max(F32(F32(u['uSpeedRef']) - F32(u['uSpeedFrom'])), F32(1.0e-6))
    f1 = np.clip((rise - F32(u['uSpeedFrom'])) / span, F32(0.0), F32(1.0)).astype(F32)
    f = f1
    for _ in range(1, int(u.get('uSpeedPow', 1))):
        f = (f * f1).astype(F32)
    plift = (F32(u['uPLift']) * (F32(1.0) + F32(u['uLiftBoost']) * f)).astype(F32)
    lift = (sand > F32(u['uMinSand'])) & (T.u01(h) < plift) & (T.u01(T.pcg2(h, 1)) >= sh)
    plong = (F32(u['uSpeedup']) * f).astype(F32)
    long_ = T.u01(T.pcg2(h, 64)) < plong
    hx, hy, lg = F32(u['uHop'][0]), F32(u['uHop'][1]), F32(u['uLong'])
    c, sn = _turn_of(s, sand.shape)
    tx, ty = _turned(c, sn, np.where(long_, F32(hx * lg), hx).astype(F32), np.where(long_, F32(hy * lg), hy).astype(F32))
    vx, vy = _hop_choice(h, tx, ty)
    periodic = int(u['uBound']) == T.BOUND_PERIODIC
    kmax = int(u['uMaxHops'])
    k = np.full(sand.shape, -1, np.int64)
    done = np.zeros(sand.shape, bool)
    psand, prock, minsand = F32(u['uPSand']), F32(u['uPRock']), F32(u['uMinSand'])
    for j in range(1, kmax + 1):
        qx, qy = ii + j * vx, jj + j * vy
        if periodic:
            qx, qy = qx % W, qy % H
            ok = np.ones(sand.shape, bool)
        else:
            ok = (qx >= 0) & (qy >= 0) & (qx < W) & (qy < H)
            done |= ~ok                                              # left the grid: k stays -1
            qx, qy = np.clip(qx, 0, W - 1), np.clip(qy, 0, H - 1)
        sq, shq = sand[qy, qx], sh[qy, qx]
        pdep = (shq + (F32(1.0) - shq) * np.where(sq > minsand, psand, prock)).astype(F32)
        dep = np.full(sand.shape, j == kmax) | (T.u01(T.pcg2(h, 3 + j)) < pdep)
        land = ~done & ok & dep
        k[land] = j
        done |= land
    amount = np.minimum(sand, F32(u['uSlab'])).astype(F32)
    rec = np.zeros(sand.shape + (4,), F32)
    rec[..., 0] = np.where(lift, amount, F32(0.0))
    rec[..., 1] = np.where(lift, vx, 0)
    rec[..., 2] = np.where(lift, vy, 0)
    rec[..., 3] = np.where(lift, k, 0)
    return {'outPlan': rec}


@T.twin('dune_transport')
def twin_transport(s, u):
    st, plan = s['st'], s['plan']
    H, W = st.shape[:2]
    ii, jj = _grid_ij((H, W))
    sand = (st[..., 1] - plan[..., 0]).astype(F32)
    periodic = int(u['uBound']) == T.BOUND_PERIODIC
    for vx, vy in _hop_vectors(u):
        for k in range(1, int(u['uMaxHops']) + 1):
            qx, qy = ii - k * vx, jj - k * vy
            if periodic:
                ok = np.ones((H, W), bool)
                qx, qy = qx % W, qy % H
            else:
                ok = (qx >= 0) & (qy >= 0) & (qx < W) & (qy < H)
                qx, qy = np.clip(qx, 0, W - 1), np.clip(qy, 0, H - 1)
            r = plan[qy, qx]
            hit = ok & (r[..., 0] > 0) & (r[..., 1].astype(np.int64) == vx) & \
                (r[..., 2].astype(np.int64) == vy) & (r[..., 3].astype(np.int64) == k)
            sand = (sand + np.where(hit, r[..., 0], F32(0.0))).astype(F32)
    out = np.zeros((H, W, 2), F32)
    out[..., 0] = st[..., 0]
    out[..., 1] = sand
    return {'outSt': out}


@T.twin('dune_avalanche')
def twin_avalanche(s, u):
    st, pins = s['st'], s['pins']
    bed, sand = st[..., 0], st[..., 1]
    h = _surface(st)
    mode = int(u['uBound'])
    tanr, rate, cell = F32(u['uTanRepose']), F32(u['uRate']), F32(u['uCell'])
    creep = F32(u['uCreep'])
    eighth, zero = F32(0.0625), F32(0.0)                         # a sixteenth: 16 neighbours
    net = np.zeros(h.shape, F32)
    for k in range(16):
        dx, dy = T.OFF[k] if k < 8 else KOFF[k - 8]
        hq, ok = T.shift(h, dx, dy, mode)
        sq, _ = T.shift(sand, dx, dy, mode)
        ln = T.LEN[k] if k < 8 else KLEN
        lim = F32(F32(tanr * ln) * cell)
        rk = F32(rate / ln)
        cw = F32(creep * T.WISO[k]) if k < 8 else zero
        dh = (h - hq).astype(F32)
        hd = (hq - h).astype(F32)
        down = (rk * np.maximum(dh - lim, zero) + cw * np.maximum(dh, zero)).astype(F32)
        up = (rk * np.maximum(hd - lim, zero) + cw * np.maximum(hd, zero)).astype(F32)
        flow = (np.minimum(up, sq * eighth) - np.minimum(down, sand * eighth)).astype(F32)
        net = (net + np.where(ok, flow, F32(0.0))).astype(F32)
    new = T.pin_apply((sand + net).astype(F32), pins[..., 0], pins[..., 1])
    out = np.zeros(st.shape[:2] + (2,), F32)
    out[..., 0] = bed
    out[..., 1] = np.maximum(new, F32(0.0))
    return {'outSt': out}


def scatter_step(st, plan, hop, max_hops, bound):
    """The transport as the scatter it stands for (each lifted slab added at its landing cell), float64: the
    reference the gather (dune_transport and its twin) must equal."""
    st = np.asarray(st, np.float64)
    plan = np.asarray(plan, np.float64)
    H, W = st.shape[:2]
    sand = st[..., 1] - plan[..., 0]
    jj, ii = np.nonzero((plan[..., 0] > 0) & (plan[..., 3] >= 1))
    vx = plan[jj, ii, 1].astype(np.int64)
    vy = plan[jj, ii, 2].astype(np.int64)
    k = plan[jj, ii, 3].astype(np.int64)
    tx, ty = ii + k * vx, jj + k * vy
    if bound == T.BOUND_PERIODIC:
        tx, ty = tx % W, ty % H
    keep = (tx >= 0) & (ty >= 0) & (tx < W) & (ty < H)
    np.add.at(sand, (ty[keep], tx[keep]), plan[jj[keep], ii[keep], 0])
    return sand


# -------------------------------------------------------------------------------------------- simulation ---

class _SimBase:
    """The iteration loop shared by the GPU sim and its numpy twin."""

    def _setup(self, bed, sand, cell, bound, params, seed, pin_w, pin_sand, steer=None):
        self.P = params_for(params)
        bed = np.ascontiguousarray(bed, np.float32)
        sand = np.ascontiguousarray(np.maximum(sand, 0.0), np.float32)
        if bed.shape != sand.shape or bed.ndim != 2:
            raise ValueError(f'bed {bed.shape} and sand {sand.shape} must be one 2D shape')
        check_grid(bed.shape, self.P, bound)
        if steer is not None and tuple(steer.shape) != tuple(bed.shape):
            raise ValueError(f'the steering {steer.shape} is not on the grid {bed.shape}')
        self.steer = steer
        self.shape = bed.shape
        self.cell = float(cell)
        self.bound = int(bound)
        self.seed = int(seed)
        self.it = 0
        pins = np.zeros(bed.shape + (2,), np.float32)
        if pin_w is not None:
            pins[..., 0] = np.asarray(pin_w, np.float32)
            pins[..., 1] = np.asarray(pin_sand if pin_sand is not None else sand, np.float32)
        return np.stack([bed, sand], -1), pins

    def set_params(self, **overrides):
        """Change model parameters between runs (a growth phase): the next step builds its uniforms afresh."""
        self.P.update(overrides)
        check_grid(self.shape, self.P, self.bound)
        self._u = None

    def run_averaged(self, winds, iterations, average_iters, every=10, callback=None, check_every=0):
        """run() for at least `iterations` (whole cycles), and the sand time-averaged over the run's last
        `average_iters` iterations (read every `every`): (iterations run, bed, mean sand). The slab model's speckle
        (single slabs arriving and leaving, about 0.15 cells) decorrelates within tens of iterations while a dune
        moves a fraction of a cell in hundreds, so the average clears the speckle and keeps the crests and brinks
        as sharp as the cells draw them; a Gaussian of a cell rounds them by as much. Each sample holds the same
        total, so the mean does too."""
        block = int(self.P['block'])
        per = schedule_length(schedule(winds, 1, block, 0.0))
        total = per * max(1, int(math.ceil(int(iterations) / per)))
        start = max(0, total - int(average_iters))
        acc, k = None, 0
        every = max(1, int(every))

        def cb(sim, done):
            nonlocal acc, k
            if average_iters and done > start and (done - start) % every == 0:
                s = sim.read()[1].astype(np.float64)
                acc = s if acc is None else acc + s
                k += 1
            if callback is not None and check_every and done % int(check_every) == 0:
                return callback(sim, done)
            return False
        done = self.run(winds, iterations, callback=cb, every=1)
        bed, sand = self.read()
        if acc is not None and k > 1 and done == total:
            sand = (acc / k).astype(np.float32)
        return done, bed, sand

    def run(self, winds, iterations, block=None, jitter_deg=None, callback=None, every=0):
        """Run the regime for at least `iterations`, in whole cycles. callback(sim, done) every `every` iterations
        (a True return stops the run at the end of the current cycle). Returns the iterations run."""
        block = int(block or self.P['block'])
        jit = float(self.P['jitter_deg'] if jitter_deg is None else jitter_deg)
        sched = schedule(winds, iterations, block, jit, self.seed + self.it, int(self.P.get('gust') or 0),
                         float(self.P.get('spread_deg') or 0.0), with_wind=True)
        per = schedule_length(schedule(winds, 1, block, 0.0))
        done = 0
        stop = False
        for d, b, w in sched:
            for _ in range(b):
                self.step(d, w)
                done += 1
                if callback is not None and every and done % every == 0 and callback(self, done):
                    stop = True
            if stop and done % per == 0:
                break
        return done


def unturned(shape):
    """The `wind` input of a grid where the wind is not turned: (cos, sin) = (1, 0) everywhere, float32 (H, W, 2)."""
    w = np.zeros(tuple(shape[:2]) + (2,), np.float32)
    w[..., 0] = 1.0
    return w


class SandSim(_SimBase):
    """The slab model on the GPU (core/gpu.py): bed and sand (metres, row 0 south) on a grid of `cell` metres.
    bound: T.BOUND_PERIODIC, T.BOUND_OPEN or T.BOUND_PINNED (with pin_w 0..1 and pin_sand, the sand held there).
    steer: a Steering on the same grid (the wind turned cell by cell), or None. step(from_deg, wind_deg) runs one
    iteration (wind_deg: the regime's own direction for this wind, which the steering is keyed on; default
    from_deg); run(winds, iterations) a regime; read() -> (bed, sand) float32."""

    def __init__(self, bed, sand, cell, bound=T.BOUND_PERIODIC, params=None, seed=0, pin_w=None, pin_sand=None,
                 steer=None):
        from ..core import gpu as G
        self.G = G
        G.init()
        st, pins = self._setup(bed, sand, cell, bound, params, seed, pin_w, pin_sand, steer)
        self.k = {n: G.kernel(n) for n in ('dune_shadow', 'dune_activate', 'dune_transport')}
        self.k['dune_avalanche'] = G.kernel(source=AVALANCHE_SRC, name='dune_avalanche')
        self.st = G.PingPong(st)
        self.shadow = G.empty(self.shape, channels=2)
        self.plan = G.empty(self.shape, channels=4)
        self.pins = G.texture(pins)
        self._wind_tex = {}
        self._u = None
        self._u_dir = None

    def _wind(self, wind_deg):
        """The `wind` texture for a wind (the steering's turn, or none) and its range of turns, cached."""
        key = None if self.steer is None else round(float(wind_deg) % 360.0, 6)
        if key not in self._wind_tex:
            if key is None:
                self._wind_tex[key] = (self.G.texture(unturned(self.shape)), (0.0, 0.0))
            else:
                cs, rng = self.steer.for_wind(key)
                self._wind_tex[key] = (self.G.texture(cs), rng)
        return self._wind_tex[key]

    def step(self, from_deg, wind_deg=None):
        G = self.G
        wind_deg = from_deg if wind_deg is None else wind_deg
        tex, turn = self._wind(wind_deg)
        if self._u_dir != (from_deg, wind_deg) or self._u is None:
            self._u = uniforms_for(self.P, self.cell, from_deg, self.it, self.seed, self.bound, turn)
            self._u_dir = (from_deg, wind_deg)
        u = self._u
        u['dune_activate']['uIter'] = self.it
        G.run(self.k['dune_shadow'], None, samplers={'st': self.st.src, 'wind': tex},
              images={'outShadow': self.shadow}, uniforms=u['dune_shadow'])
        G.run(self.k['dune_activate'], None, samplers={'st': self.st.src, 'shadow': self.shadow, 'wind': tex},
              images={'outPlan': self.plan}, uniforms=u['dune_activate'])
        G.run(self.k['dune_transport'], None, samplers={'st': self.st.src, 'plan': self.plan},
              images={'outSt': self.st.dst}, uniforms=u['dune_transport'])
        self.st.swap()
        for _ in range(int(self.P['aval_passes'])):
            G.run(self.k['dune_avalanche'], None, samplers={'st': self.st.src, 'pins': self.pins},
                  images={'outSt': self.st.dst}, uniforms=u['dune_avalanche'])
            self.st.swap()
        self.it += 1

    def read(self):
        a = self.G.read(self.st.src)
        return np.array(a[..., 0]), np.array(a[..., 1])

    def read_shadow(self):
        return np.array(self.G.read(self.shadow)[..., 0])


class TwinSim(_SimBase):
    """The same model on the numpy twins (test oracle at 64-128 cells; not a production path)."""

    def __init__(self, bed, sand, cell, bound=T.BOUND_PERIODIC, params=None, seed=0, pin_w=None, pin_sand=None,
                 steer=None):
        st, pins = self._setup(bed, sand, cell, bound, params, seed, pin_w, pin_sand, steer)
        self.st = st
        self.pins = pins
        self.last_plan = None
        self.last_shadow = None
        self._u = None

    def step(self, from_deg, wind_deg=None):
        wind_deg = from_deg if wind_deg is None else wind_deg
        cs, turn = (unturned(self.shape), (0.0, 0.0)) if self.steer is None else self.steer.for_wind(wind_deg)
        u = uniforms_for(self.P, self.cell, from_deg, self.it, self.seed, self.bound, turn)
        sh = twin_shadow({'st': self.st, 'wind': cs}, u['dune_shadow'])['outShadow']
        plan = twin_activate({'st': self.st, 'shadow': sh, 'wind': cs}, u['dune_activate'])['outPlan']
        st = twin_transport({'st': self.st, 'plan': plan}, u['dune_transport'])['outSt']
        for _ in range(int(self.P['aval_passes'])):
            st = twin_avalanche({'st': st, 'pins': self.pins}, u['dune_avalanche'])['outSt']
        self.st = st
        self.last_plan, self.last_shadow = plan, sh
        self.it += 1

    def read(self):
        return np.array(self.st[..., 0]), np.array(self.st[..., 1])


def denoise(sand, sigma_cells, periodic=False, pin_w=None, pin_sand=None):
    """The slab noise cleared: a separable Gaussian of sigma_cells cells over the sand thickness (wrapped on a
    periodic grid, mirrored at an open edge, so the total sand is kept), then the pins re-applied. float32."""
    s = np.asarray(sand, np.float64)
    if sigma_cells and sigma_cells > 0:
        r = max(1, int(math.ceil(3.0 * float(sigma_cells))))
        k = np.exp(-0.5 * (np.arange(-r, r + 1) / float(sigma_cells)) ** 2)
        k /= k.sum()
        for axis in (0, 1):
            if periodic:
                s = sum(w * np.roll(s, r - i, axis=axis) for i, w in enumerate(k))
            else:
                pad = [(0, 0), (0, 0)]
                pad[axis] = (r, r)
                p = np.pad(s, pad, mode='symmetric')
                n = s.shape[axis]
                s = sum(w * np.take(p, np.arange(i, i + n), axis=axis) for i, w in enumerate(k))
    if pin_w is not None:
        w = np.clip(np.asarray(pin_w, np.float64), 0.0, 1.0)
        s = s * (1.0 - w) + np.asarray(pin_sand, np.float64) * w
    return np.maximum(s, 0.0).astype(np.float32)


def smooth_sheet(sand, p, periodic=False, pin_w=None, pin_sand=None):
    """The low-mobility sand sheet smoothed: where the sand is thinner than 1.5 x the speed-up's start (speed_from_m:
    sand the wind barely lifts, the plinth under the dunes and the interdune sheets) and on the bare floor, a Gaussian
    of sheet_smooth_cells replaces it, easing to none at 3 x that thickness (the dunes' aprons). Slabs the dunes shed
    land on such a sheet and stay, a speckle the time-averaged read-out cannot clear because the sheet hardly moves;
    on real sheets reptation and migrating ripples keep the surface flat. The bare floor takes the Gaussian too, so a
    sheet's margin thins out onto the floor over a few sigma as a real sand sheet's does (kept bare, the floor left
    every sheet standing as a table with a step at its edge: the review's straight-edged plates), and single slabs
    resting on the floor spread into a faint veneer. The dunes are untouched. A read-out blend, not a transport: the
    total can rise by about a percent where the blur reaches up a dune's toe. float32 (sand unchanged when the
    parameter is 0 or there is no threshold)."""
    sig = float(p.get('sheet_smooth_cells') or 0.0)
    top = float(p.get('sheet_top_m') or p.get('speed_from_m') or 0.0)
    if sig <= 0 or top <= 0 or p.get('rise', 'sand') != 'sand':
        return np.asarray(sand, np.float32)
    s = np.asarray(sand, np.float64)
    blur = np.asarray(denoise(s, sig, periodic=periodic, pin_w=pin_w, pin_sand=pin_sand), np.float64)
    t = np.clip((s - 1.5 * top) / (1.5 * top), 0.0, 1.0)
    w = 1.0 - t * t * (3.0 - 2.0 * t)                          # 1 on the sheet and the floor, 0 from 3 x the threshold
    return np.maximum(s * (1.0 - w) + blur * w, 0.0).astype(np.float32)


# ------------------------------------------------------------------------------------------ measurements ---

def spacing_peak(h, cell, lo_cells=4.0):
    """The dune spacing as the judge reads it: the wavelength carrying the most slope (the peak of k^2 P(k)),
    between lo_cells pixels and a quarter of the extent, metres."""
    from ..core import metrics as M
    wl, P = M.radial_spectrum(np.asarray(h, np.float64), cell, nbins=64)
    k = 1.0 / wl
    band = (wl >= lo_cells * cell) & (wl <= 0.25 * min(np.shape(h)) * cell)
    if not band.any():
        return float('nan')
    sp = np.convolve((k * k * P)[band], np.ones(3) / 3, mode='same')
    return float(wl[band][int(np.argmax(sp))])


def dune_height(sand):
    """How tall the dunes stand: p99.5 - p0.5 of the sand thickness, metres (the bed's own relief left out)."""
    s = np.asarray(sand, np.float64)
    return float(np.percentile(s, 99.5) - np.percentile(s, 0.5))


def slip_fraction(h, cell, repose_deg=31.0, below=4.0):
    """The share of cells within `below` degrees of the angle of repose or steeper: standing slip faces."""
    s = _grid.slope_deg(h, cell)
    return float(np.mean(s >= repose_deg - below))


# ------------------------------------------------------------------------------------- the start surface ---

def _periodic_wavelength(w, period):
    from ..core import world_noise as N
    return N.snap_wavelength(w, period) if period else float(w)


def _fbm(level, wavelength_m, octaves, seed, period_m=None):
    """World-space fbm at a level's cells (periodic over period_m when given, its wavelength snapped to it), float64:
    the GPU evaluation in Blender, numpy outside it."""
    from ..core import world_noise as N
    wl = _periodic_wavelength(wavelength_m, period_m)
    spec = {'kind': 'fbm', 'wavelength_m': wl, 'octaves': int(octaves), 'period_m': period_m}
    try:
        from ..core import gpu as G                                  # noqa: F401 - Blender: the GPU path
        return N.field_gpu(spec, level, seed=seed).astype(np.float64)
    except (RuntimeError, ImportError):
        x, y = level.xy()
        return N.field(spec, x, y, seed=seed)


def steering_for(level, p, seed, period_m=None):
    """The Steering at a level's cells (world-space, periodic over period_m when given), or None when p asks for
    none (steer_deg and steer_turn_deg 0). n1, n2, n3: 3 x fbm at steer_wavelength_m (2 octaves: unit variance),
    clipped at +-2, so no cell turns more than twice the standard deviation. Every level evaluates the same
    functions of world position, so a finer level's wind turns as its parent's did."""
    steer, turn = float(p.get('steer_deg') or 0.0), float(p.get('steer_turn_deg') or 0.0)
    if steer <= 0.0 and turn <= 0.0:
        return None
    wl = float(p.get('steer_wavelength_m') or 2.5 * float(p.get('spacing_m') or 1200.0))
    n = np.stack([np.clip(3.0 * _fbm(level, wl, 2, int(seed) * 7 + 11 + k, period_m), -2.0, 2.0) for k in range(3)])
    return Steering(n, steer, turn)


def stretch_periodic(a, cell, sigma_m, axis_deg):
    """A periodic field's features drawn out along one compass direction: a Gaussian of sigma_m metres along
    axis_deg only (in Fourier space, so it wraps over the period exactly), then rescaled to the field's own mean and
    standard deviation. float64 (the field unchanged when sigma_m is 0)."""
    a = np.asarray(a, np.float64)
    if not sigma_m or sigma_m <= 0:
        return a
    ny, nx = a.shape
    t = math.radians(float(axis_deg))
    kx = np.fft.rfftfreq(nx, d=float(cell))[None, :]                 # cycles per metre along x (east)
    ky = np.fft.fftfreq(ny, d=float(cell))[:, None]                  # ... along y (north: row 0 is south)
    k_along = kx * math.sin(t) + ky * math.cos(t)
    m = float(a.mean())
    out = np.fft.irfft2(np.fft.rfft2(a - m) * np.exp(-2.0 * (math.pi * float(sigma_m) * k_along) ** 2), s=a.shape)
    sd0, sd1 = float(a.std()), float(out.std())
    return m + out * (sd0 / sd1 if sd1 > 0 else 0.0)


def start_fields(level, p, seed, period_m=None):
    """The growth start at a level's cells (world-space, periodic over period_m when given): bed and sand, float32.
    bed: bed_m x fbm at bed_wavelength_m (3 octaves). sand: sand_m x max(0, 1 + supply_var x 3 fbm) at
    supply_wavelength_m, plus the seed: seed_m x 3 fbm at the target spacing (2 octaves). With supply_stretch_m (a
    periodic start only) the supply's highs and lows are drawn out along supply_axis_deg (stretch_periodic), so
    where the sand runs out the floor is a long corridor between dune chains, as the Namib's interdune pans are,
    not a round hole; supply_cap limits the supply's highs (a multiple of sand_m)."""
    per = period_m

    def fbm(w, octaves, s):
        return _fbm(level, w, octaves, s, per)
    bed = float(p['bed_m']) * 3.0 * fbm(float(p['bed_wavelength_m']), 3, seed * 7 + 1)
    sn = fbm(float(p['supply_wavelength_m']), 2, seed * 7 + 2)
    if float(p.get('supply_stretch_m') or 0.0) > 0.0 and per:
        sn = stretch_periodic(sn, level.cell, float(p['supply_stretch_m']), float(p.get('supply_axis_deg') or 0.0))
    supply = np.maximum(0.0, 1.0 + float(p['supply_var']) * 3.0 * sn)
    if p.get('supply_cap'):
        supply = np.minimum(supply, float(p['supply_cap']))
    sand = float(p['sand_m']) * supply
    if float(p['seed_m']) > 0:
        sand = sand + float(p['seed_m']) * 3.0 * fbm(float(p['spacing_m']) * float(p['seed_scale']), 2, seed * 7 + 3)
    return bed.astype(np.float32), np.maximum(sand, 0.0).astype(np.float32)


# ------------------------------------------------------------------------------------- the level stack ---

FIELD_DEFAULTS = dict(
    kind='star',
    winds=None,                 # None: the kind's regime
    wind_rotate_deg=0.0,        # turn the whole regime clockwise
    sand_m=None,                # mean sand thickness, metres (None: the kind's)
    spacing_m=None,             # target dune spacing, metres (None: the kind's)
    seed_frac=0.15,             # seed amplitude, a share of the target height (design: 10-20 %)
    height_ratio=None,          # target height / spacing for the seed (None: from the kind)
    seed_scale=1.0,             # the seed's lattice wavelength, a multiple of the spacing
    speed_from_frac=0.25,       # the speed-up starts at this share of the target height of sand ...
    speed_ref_frac=2.0,         # ... and is full at this multiple of it
    supply_var=0.35,            # the sand supply's variation: 1 + supply_var x (unit-variance noise)
    patchiness=None,            # > 0: the recipe's sand_patchiness knob, which sets supply_var over the kind's own
    supply_wavelength_m=None,   # the supply's wavelength (None: 6 x the spacing)
    supply_stretch_m=0.0,       # > 0: the supply's highs and lows drawn out along supply_axis_deg by a Gaussian of
    supply_axis_deg=90.0,       # this many metres (stretch_periodic: long interdune corridors); the axis is a compass
                                # trend, turned with the winds by wind_rotate_deg
    supply_cap=None,            # the most the sand piles anywhere at the start, a multiple of sand_m (None: no cap): a
                                # strong supply_var opens bare corridors, and uncapped its highs grow dunes far taller
                                # than the place's
    bed_m=None,                 # the bed's undulation, metres (standard deviation; None: the kind's, else 6)
    bed_wavelength_m=None,      # its wavelength (None: 5 x the spacing)
    cells_per_spacing=24.0,     # the growth level resolves the spacing with at least this many cells
    grow_iters=12000,           # the growth run: the slab model is scale-free in cells, and the growth level always
                                # holds cells_per_spacing or more cells per dune, so one count gives one maturity
    grow_min_iters=12000,       # an early stop may come after this many (equal to grow_iters: no early stop) ...
    grow_check=3000,            # (iterations between the growth checks, which log the dunes' height and spacing)
    height_reached=1.0,         # ... once the dunes (p99.5 - p0.5 of the sand) stand this share of the target height
    slip_reached=0.002,         # ... and this share of the cells stand at the slip-face angle
    refine_iters=1200,          # iterations on each level finer than the growth level (whole cycles of its winds)
    refine_winds='cycle',       # the winds those levels blow: 'cycle' the whole regime, 'last' its last wind (refine)
    refine_hop_cells=None,      # the hop on refinement levels (None: hop_cells)
    refine_block=None,          # iterations per wind block on those levels (None: block)
    refine_average_iters=None,  # their time-averaged read-out (None: average_iters; 0: the last state, denoised)
    refine_smooth_cells=None,   # their read-out Gaussian, cells (None: smooth_cells)
    hero_winds=None,            # the hero levels' own winds, iterations, block, read-out and Gaussian (None: the
    hero_iters=None,            # refine_* values). The hero levels hold the last few hundred metres around a
    hero_block=None,            # camera: at their cells a season moves a big dune's body by metres, so the whole
    hero_average_iters=None,    # regime there re-cuts the crests (each arm's brink and slip face from the last
    hero_smooth_cells=None,     # wind that crossed it) and grows the small dunes on the flanks (refine)
    pin_band=16,                # the border band pinned to the parent, cells
    steer_wavelength_m=None,    # the steering's wavelength (None: 2.5 x the spacing; steer_deg turns it on)
    sheet_smooth_cells=0.0,     # > 0: sand thinner than the speed-up's start smoothed by this many cells (smooth_sheet)
    sheet_top_m=None,           # the thickness smooth_sheet calls a sheet (None: the speed-up's start, speed_from_m)
    average_iters=0,            # > 0: each run's sand is its mean over its last this many iterations ...
    average_every=10,           # ... read every this many (SandSim.run_averaged): the speckle goes, the crests stay
)
HEIGHT_RATIO = {'star': 0.25, 'linear': 0.06, 'transverse': 0.06, 'barchan': 0.08}

_CURRENT = {'plan': None}
_TILES = {}


def prepare(values, plan):
    """The dunes recipe's prepare hook: remember the level stack, so each level's op finds the growth level."""
    _CURRENT['plan'] = list(plan)


def resolve_params(params):
    """The dune field's parameters: FIELD_DEFAULTS and the slab model's DEFAULTS, the kind's winds, sand and
    spacing filled in where None, the derived seed amplitude and noise wavelengths. Raises on an unknown kind."""
    p = dict(DEFAULTS)
    p.update(FIELD_DEFAULTS)
    for k, v in (params or {}).items():
        if v is not None or k not in p:
            p[k] = v
    kind = p.get('kind') or 'star'
    if kind not in KINDS:
        import difflib
        near = difflib.get_close_matches(str(kind), list(KINDS), n=2)
        raise KeyError(f'dune kind {kind!r}' + (f'; did you mean {near}?' if near else f'; one of {list(KINDS)}'))
    K = KINDS[kind]
    given = {k for k, v in (params or {}).items() if v is not None}
    for k, v in (K.get('model') or {}).items():
        if k not in given:
            p[k] = v
    if p.get('patchiness'):
        p['supply_var'] = float(p['patchiness'])
    winds = p['winds'] if p.get('winds') else K['winds']
    rot = float(p.get('wind_rotate_deg') or 0.0)
    p['winds'] = [((d + rot) % 360.0, w) for d, w in normalise_winds(winds)]
    p['supply_axis_deg'] = (float(p.get('supply_axis_deg') or 0.0) + rot) % 180.0
    p['sand_m'] = float(p['sand_m'] if p.get('sand_m') else K['sand_m'])
    p['spacing_m'] = float(p['spacing_m'] if p.get('spacing_m') else K['spacing_m'])
    p['bed_m'] = float(p['bed_m'] if p.get('bed_m') else K.get('bed_m', 6.0))
    ratio = float(p['height_ratio'] if p.get('height_ratio') else HEIGHT_RATIO[kind])
    target_h = ratio * p['spacing_m']
    p['target_height_m'] = target_h
    # the seed: a share of the target height, but no more than the sand there is can heap
    p['seed_m'] = float(p.get('seed_m') or p['seed_frac'] * min(target_h, 3.0 * p['sand_m']))
    # the speed-up grows over the dune's height: by default from a quarter of the target height to twice it
    if not (params or {}).get('speed_from_m'):
        p['speed_from_m'] = float(p['speed_from_frac']) * target_h
    if not (params or {}).get('speed_ref_m'):
        p['speed_ref_m'] = max(float(p['speed_ref_frac']) * target_h, p['speed_from_m'] + 1e-3)
    if not p.get('supply_wavelength_m'):
        p['supply_wavelength_m'] = 6.0 * p['spacing_m']
    if not p.get('bed_wavelength_m'):
        p['bed_wavelength_m'] = 5.0 * p['spacing_m']
    return p


def _plan_holding(level):
    """(plan, index): the stack prepare() recorded when it holds this level's window at the level's index, else
    the level alone (a standalone run: it is its own growth level)."""
    plan = _CURRENT['plan']
    if plan:
        i = int(getattr(level, 'index', -1))
        if 0 <= i < len(plan):
            q = plan[i]
            if all(abs(float(getattr(q, a)) - float(getattr(level, a))) <= 1e-6 * max(1.0, abs(float(getattr(q, a))))
                   for a in ('x0', 'y0', 'cell')) and int(q.n) == int(level.n):
                return plan, i
    return [level], 0


def growth_index(plan, spacing_m, cells_per_spacing, warn=None):
    """The growth level: the coarsest context or main level whose cell resolves the spacing with cells_per_spacing
    cells (the main level, with a warning, when none does)."""
    for i, lv in enumerate(plan):
        if lv.role in ('context', 'main') and spacing_m / lv.cell >= cells_per_spacing * (1 - 1e-9):
            return i
    main = [i for i, lv in enumerate(plan) if lv.role == 'main']
    i = main[0] if main else len(plan) - 1
    if warn:
        warn(f'no level resolves a {spacing_m:g} m dune spacing with {cells_per_spacing:g} cells; growing on '
             f'{plan[i]} ({spacing_m / plan[i].cell:.1f} cells per spacing)')
    return i


def _tile_key(lv, p, seed):
    keep = {k: v for k, v in p.items() if not k.startswith(('refine_', 'hero_')) and k != 'pin_band'}
    blob = json.dumps(dict(w=[lv.x0, lv.y0, lv.cell, lv.n], p=keep, seed=int(seed)), sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def grow_tile(lv, p, seed, log=None):
    """The dune field grown on level lv's window, periodic over it (cached per process): dict(bed, sand, iters,
    spacing_m, slip_frac, seconds, history). The last growth phase reads its sand time-averaged when
    p['average_iters'] is set (SandSim.run_averaged), then the light Gaussian of smooth_cells."""
    key = _tile_key(lv, p, seed)
    if key in _TILES:
        return _TILES[key]
    t0 = time.perf_counter()
    target = float(p['spacing_m'])
    bed, sand = start_fields(lv, p, seed, period_m=lv.side)
    sim = SandSim(bed, sand, lv.cell, T.BOUND_PERIODIC, p, seed=int(seed) * 131 + 7,
                  steer=steering_for(lv, p, seed, period_m=lv.side))
    hist = []

    def check(s, done):
        b, sd = s.read()
        hh = b + sd
        sp, sf = spacing_peak(hh, lv.cell), slip_fraction(hh, lv.cell, float(p['repose_deg']))
        tall = dune_height(sd)
        hist.append(dict(iters=done, spacing_m=round(sp, 1), slip_frac=round(sf, 5), dune_height_m=round(tall, 2),
                         relief_m=round(float(hh.max() - hh.min()), 2)))
        if log:
            log(f'{LOG_PREFIX}   growth {done} it: dunes {tall:.0f} m (target {p["target_height_m"]:.0f}), spacing '
                f'{sp:.0f} m (target {target:g}), slip faces {100 * sf:.2f} %')
        return done >= int(p['grow_min_iters']) and tall >= float(p['height_reached']) * p['target_height_m'] \
            and sf >= float(p['slip_reached'])
    phases = p.get('grow_phases') or [[int(p['grow_iters']), {}]]      # [[iterations, {model overrides}], ...]
    avg = int(p.get('average_iters') or 0)
    iters = 0
    bed = sand = None
    for k, (n_it, over) in enumerate(phases):
        sim.set_params(**(over or {}))
        if avg and k == len(phases) - 1:
            d, bed, sand = sim.run_averaged(p['winds'], int(n_it), avg, int(p.get('average_every') or 10),
                                            callback=check, check_every=int(p['grow_check']))
            iters += d
        else:
            iters += sim.run(p['winds'], int(n_it), callback=check, every=int(p['grow_check']))
    if sand is None:
        bed, sand = sim.read()
    sand = smooth_sheet(denoise(sand, float(p['smooth_cells']), periodic=True), p, periodic=True)
    h = bed + sand
    out = dict(bed=bed, sand=sand, iters=iters, spacing_m=spacing_peak(h, lv.cell),
               slip_frac=slip_fraction(h, lv.cell, float(p['repose_deg'])),
               seconds=round(time.perf_counter() - t0, 2), history=hist)
    if len(_TILES) >= 4:
        _TILES.clear()
    _TILES[key] = out
    if log:
        log(f'{LOG_PREFIX} grew the dune field on {lv}: {iters} iterations, spacing {out["spacing_m"]:.0f} m '
            f'(target {target:g}), slip faces {100 * out["slip_frac"]:.2f} % of cells, {out["seconds"]} s')
    return out


def sample_periodic(a, src, lv):
    """A periodic field on level `src`'s window, averaged over the (coarser, nested) cells of level lv: lv's cell
    must be a power-of-two multiple of src's and its window on src's grid lines (plan_levels makes them so)."""
    r = lv.cell / src.cell
    m = int(round(r))
    if abs(r - m) > 1e-6 or m < 1 or (m & (m - 1)):
        raise ValueError(f'{lv} is not a power-of-two coarsening of {src}')
    i0 = (lv.x0 - src.x0) / src.cell
    j0 = (lv.y0 - src.y0) / src.cell
    if abs(i0 - round(i0)) > 1e-6 or abs(j0 - round(j0)) > 1e-6:
        raise ValueError(f'{lv} is not on the grid lines of {src}')
    n = src.n
    cols = (int(round(i0)) + np.arange(lv.n * m)) % n
    rows = (int(round(j0)) + np.arange(lv.n * m)) % n
    a = np.asarray(a, np.float64)
    a = a[rows, :].reshape(lv.n, m, n).mean(axis=1)
    a = a[:, cols].reshape(lv.n, lv.n, m).mean(axis=2)
    return a.astype(np.float32)


def refine_winds(p, mode=None):
    """The winds a level finer than the growth level blows: the whole regime ('cycle'), its last wind alone ('last',
    the season the growth run ended on), or its last two in turn ('last2'); mode None: p['refine_winds']. The big
    dunes are the whole regime's work, grown on the growth level; a finer level adds what its cells can draw. On the
    main level a whole cycle re-planes every big dune into the faces of its winds (a star dune into a pyramid of
    straight-edged facets), so there the latest season alone shows (fresh slip faces and brinks on the dunes the
    regime built). On the hero levels two seasons in short turns reverse the crest zone: each builds its slip face on
    its own lee and cuts back the other's, so a crest stands steep on both sides above the broad flanks, the knife-edge
    arm of a star dune, where one season leaves a sharp brink over a gentle stoss."""
    mode = mode or p.get('refine_winds') or 'cycle'
    if mode == 'last':
        return [normalise_winds(p['winds'])[-1]]
    if mode == 'last2':
        return normalise_winds(p['winds'])[-2:]
    return p['winds']


def refine_settings(p, lv):
    """A refinement level's run: dict(winds, iters, block, average_iters, smooth_cells). Hero levels take the hero_*
    values where given; every level falls back on the refine_* values, then on the growth run's own (block,
    average_iters, smooth_cells)."""
    hero = getattr(lv, 'role', '') == 'hero'

    def pick(name, fallback):
        v = p.get('hero_' + name) if hero else None
        if v is None:
            v = p.get('refine_' + name)
        return fallback if v is None else v
    return dict(winds=refine_winds(p, pick('winds', p.get('refine_winds'))), iters=int(pick('iters', 1200)),
                block=int(pick('block', p['block'])), average_iters=int(pick('average_iters', p.get('average_iters')
                                                                                    or 0)),
                smooth_cells=float(pick('smooth_cells', p['smooth_cells'])))


def refine(fields, lv, p, seed, log=None):
    """Run the slab model on one level from its current fields (h and bed; sand = h - bed), its border band pinned
    to that start (a child level is pinned to its parent), as refine_settings(p, lv) says. Writes bed, sand and h."""
    t0 = time.perf_counter()
    h = np.asarray(fields['h'], np.float32)
    bed = np.asarray(fields['bed'], np.float32) if 'bed' in fields else \
        (h - np.asarray(fields.get('sand', 0.0), np.float32))
    bed = np.minimum(bed, h)
    sand = np.maximum(h - bed, 0.0).astype(np.float32)
    rs = refine_settings(p, lv)
    q = dict(p, block=rs['block'])
    if p.get('refine_hop_cells'):
        q['hop_cells'] = float(p['refine_hop_cells'])
    w = _grid.border_ramp(lv.n, int(p['pin_band']), 'smooth')
    sim = SandSim(bed, sand, lv.cell, T.BOUND_PINNED, q, seed=int(seed) * 131 + 11 + 977 * int(lv.index),
                  pin_w=w, pin_sand=sand, steer=steering_for(lv, q, seed, period_m=p.get('growth_period_m')))
    if rs['average_iters']:
        iters, bed2, sand2 = sim.run_averaged(rs['winds'], rs['iters'], rs['average_iters'],
                                              int(q.get('average_every') or 10))
    else:
        iters = sim.run(rs['winds'], rs['iters'])
        bed2, sand2 = sim.read()
    sand2 = smooth_sheet(denoise(sand2, rs['smooth_cells'], periodic=False, pin_w=w, pin_sand=sand), q,
                         periodic=False, pin_w=w, pin_sand=sand)
    fields['bed'] = bed2
    fields['sand'] = sand2
    fields['h'] = bed2 + sand2
    if log:
        log(f'{LOG_PREFIX} refined {lv}: {iters} iterations ({len(rs["winds"])} winds, blocks of {rs["block"]}), '
            f'{time.perf_counter() - t0:.2f} s')
    return iters


def op_dune_field(fields, level, params, seed=0, log=print):
    """Stage op 'dune_field': the dune field on one level of the stack (module doc). Levels coarser than the
    growth level average the grown field, the growth level is the grown field, finer levels refine their inherited
    surface. Writes h, bed and sand."""
    p = resolve_params(params)
    plan, i = _plan_holding(level)
    g = growth_index(plan, p['spacing_m'], float(p['cells_per_spacing']), warn=lambda m: log(f'{LOG_PREFIX} {m}'))
    p['growth_period_m'] = float(plan[g].side)          # the steering is periodic over the growth window everywhere
    if i <= g:
        src = plan[g]
        tile = grow_tile(src, p, seed, log=log)
        if i == g:
            bed, sand = tile['bed'], tile['sand']
        else:
            bed, sand = sample_periodic(tile['bed'], src, level), sample_periodic(tile['sand'], src, level)
        fields['bed'] = bed
        fields['sand'] = sand
        fields['h'] = bed + sand
        return fields
    if 'h' not in fields:
        raise ValueError(f'dune_field on {level}: a level finer than the growth level starts from its parent '
                         f'(the level runner inherits h and bed); this one has no h')
    refine(fields, level, p, seed, log=log)
    return fields


def op_aeolian(fields, level, params, seed=0, log=print):
    """Stage op 'aeolian': the slab model on one level's own surface (h and bed, or h and sand), for recipes that
    blow sand over ground another stage made. params: the slab model's (DEFAULTS), winds or kind, iterations,
    periodic (False: the border band pinned to the start)."""
    p = resolve_params(params)
    t0 = time.perf_counter()
    h = np.asarray(fields['h'], np.float32)
    bed = np.asarray(fields['bed'], np.float32) if 'bed' in fields else \
        (h - np.asarray(fields.get('sand', 0.0), np.float32))
    bed = np.minimum(bed, h)
    sand = np.maximum(h - bed, 0.0).astype(np.float32)
    periodic = bool(p.get('periodic', False))
    w = None if periodic else _grid.border_ramp(level.n, int(p['pin_band']), 'smooth')
    sim = SandSim(bed, sand, level.cell, T.BOUND_PERIODIC if periodic else T.BOUND_PINNED, p,
                  seed=int(seed) * 131 + 5 + 977 * int(getattr(level, 'index', 0)), pin_w=w, pin_sand=sand,
                  steer=steering_for(level, p, seed, period_m=level.side if periodic else None))
    iters = sim.run(p['winds'], int(p.get('iterations', p['refine_iters'])))
    b, s = sim.read()
    s = denoise(s, float(p['smooth_cells']), periodic=periodic, pin_w=w, pin_sand=sand)
    fields['bed'], fields['sand'], fields['h'] = b, s, b + s
    log(f'{LOG_PREFIX} aeolian on {level}: {iters} iterations, {time.perf_counter() - t0:.2f} s')
    return fields


OPS = {'dune_field': op_dune_field, 'aeolian': op_aeolian}
