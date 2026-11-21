"""mesas_buttes: flat caprock remnants standing on talus over a broad desert floor (design section 5), judged against
Monument Valley.

    t = make_terrain('mesas_buttes', params={'caprock_fraction': 0.05}, focus=(-1100, -40))

The stages (solvers/strata.py, solvers/rivers.py): Monument Valley's column (the Cedar Mesa sandstone the floor is
stripped to, the Organ Rock shale's pedestal about 150 m, the De Chelly sandstone's sheer walls about 160 m and a
thin conglomerate cap: the Mittens' proportions); a plateau at the cap's top; a winding wash across the tile as the
base level, cut down to the floor over the first part of the run; then the walls retreat (weathering: the Organ
Rock wears back under the De Chelly, which fails over it at 80 degrees and leaves its debris as talus pedestals),
fastest where runoff gathers, so the escarpment frays into fingers, and it passes the massive cores of the De Chelly
(blue noise about 1.3 km apart, the size of Monument Valley's buttes, long along the joints, rounded and each its own
outline), which it leaves standing as buttes. The first pass, on the coarsest level's 62.5 m cells, stops when the
caprock left in the main tile (the ground at or above the De Chelly's base) falls to `caprock_fraction` (or at its
age); the coarsest level's later passes (31 m, 15.6 m) go on evolving for 0.12 of its time, so the walls retreat
further and stand again at each finer cell, sheer under sharp rims. The floor follows the Cedar Mesa's top, which
undulates a metre or two over 90-260 m: low swells, ledges and swales. Rock breakup's relief on the hero levels.

Heights: z = 0 is the wash's final bed at the tile centre; base_elevation_m (1520 m) places it.
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import strata as S

COLUMN = 'monument_valley'
CAP_BASE_ZS = S.column(COLUMN).base_of('De Chelly')          # 330 m: the caprock is the De Chelly and above


def _surface(p):
    p.stage('plateau')['surface_zs_m'] = float(p['floor_zs_m']) + float(p['relief_m'])


def _cap(p):
    f = p.stage('strata_fluvial')
    f['caprock_target'] = float(p['caprock_fraction'])
    f['caprock_zs_m'] = CAP_BASE_ZS


def _detail(p):
    for s in p.stages('breakup'):
        s['enabled'] = bool(p['detail'])


# a 1.4-degree dip: the floor, stripped to the Cedar Mesa's top, rises about 195 m across the tile toward the west
# north-west, as Monument Valley's does (HI 0.26: a flat floor gave 0.08). The beds also undulate a metre or two over
# 90-260 m, and the stripped floor follows them: low swells, ledges and swales (Monument Valley's floor has slope p50
# 4-6 degrees 0.5-1 km from the buttes; with the warp at 800 m and up only, 1-2 degrees)
STRATA = {'column': COLUMN, 'zs0_m': '$floor_zs_m', 'dip_deg': 1.4, 'azimuth_deg': 160.0,
          'warp': [[3500.0, 6.0], [800.0, 2.5], [260.0, 1.4], [90.0, 0.5]]}
# two joint sets (the De Chelly's fracture pattern): weathering and incision run faster along them, so the
# escarpment frays into fingers and blocks with straight sides. 60 degrees apart, the second weaker: two equal
# perpendicular sets cut square blocks whose walls faced four ways (the 4-fold aspect harmonic 0.12 against Monument
# Valley's 0.016)
JOINTS = [{'strike_deg': 20.0, 'spacing_m': 650.0, 'width_m': 35.0},
          {'strike_deg': 80.0, 'spacing_m': 900.0, 'width_m': 35.0, 'strength': 0.7}]
# massive cores in the De Chelly (strata.rock_cores, blue noise about 1.3 km apart, 360-840 m across, long along the
# joints, rounded and each its own outline): the escarpment retreats past them and leaves them standing as buttes
# (without them it frayed into fingers that were all stripped before any stood alone: no butte in the tile). Every
# core is the rock mass at its strongest (strength 4.5 x 0.75-1.25 against n's clip at 3.5) and the rock mass weighs
# 1.0 in the erodibility and the weathering (FLUVIAL's resist): a core's walls then wear back about a thirtieth as
# fast as the escarpment's, so a block the size of Monument Valley's buttes outlives its passage (cores 1.8 km apart
# and 600-1300 m across, at strength 3 and resist 0.8, left the escarpment's plateau and four to six remnants with
# caps of 0.005-0.2 km2 in the main tile; cores of the buttes' size at that strength were worn down to spires with
# caps under 0.02 km2 once the later passes evolved; at strength 4.5, cores 300-700 m across left buttes with caps of
# 0.005-0.06 km2 and the main tile's slope p90 at 14-16 degrees against the DEM's 24.5, cores 360-840 m across caps
# up to 0.11 km2 and p90 22-24.5. The Mittens' and Merrick Butte's tops are 0.04-0.06 km2)
CORES = {'spacing_m': 1300.0, 'radius_m': [180.0, 420.0], 'elongation': [1.0, 1.8], 'angles_deg': [20.0, 80.0],
         'strength': 4.5, 'region_m': 40000.0, 'exponent': 2.5, 'wobble': 0.2}
PLATEAU = {'surface_zs_m': 480.0, 'roughness': [[3000.0, 5.0], [600.0, 2.0], [120.0, 0.6]]}
# the wash winds (32 degrees at 3.5 km): the escarpment retreating from it is embayed, not one straight front
RIVER = {'kind': 'walk', 'through': [0.0, 0.0], 'flow_azimuth_deg': 20.0, 'wiggle_deg': 32.0,
         'wiggle_wavelength_m': 3500.0, 'width_m': 40.0, 'bed_m': 0.0, 'gradient': 0.004,
         'schedule': [[0.0, 0.0], [0.25, 1.0], [1.0, 1.0]]}
# buttes outlive the escarpment's passage when it retreats mainly up its washes (the drainage boost, fraying) and
# a cut-off block only wears back slowly (the base weathering, the cores): with the base rate high the whole tile
# was stripped to the floor before any block stood alone
# (the rock mass's noise at half strength, the joints at 2.5: at full noise and 4 the caps weathered in weak patches
# and along every joint into convex humps with saw-toothed crests; the run factor at 0.3: at 0.5 the cores' walls
# stood vertical, texel-wide cliffs 3 x Monument Valley's)
# The coarsest level's later passes evolve (later 'evolve': the weathering, the failure and the incision go on at
# 31 m and 15.6 m, unlocked, for 0.12 of the first pass's time). The walls stand where the retreat runs: on the first
# pass's 62.5 m cells a 160 m De Chelly wall is one cell's step, which the upsampling to the next pass spreads over two
# of its cells, and refined from there under the low-pass lock with the rock's weathering off (later 'refine'),
# nothing steepened a wall again: on the main level the walls' upper 60 m leaned at about 50 degrees on average, a
# rim rounded over 45 m, one long soft mesa beside the Mittens' sheer walls. Evolving, the walls go on retreating and
# stand again at each pass's cells: the De Chelly now drops 115 m between 16 and 47 m from the rim (75 degrees at
# 8 m; Monument Valley's DEM at 8 m, 100 m in 32 m), over a talus pedestal at about 35 degrees.
# The debris washes off at 0.3 x the rock's rate (0.6 before; the talus mantles the pedestals longer).
FLUVIAL = {'K': 1.5e-6, 'valley_spacing_m': 600.0, 'roughness': 0.6, 'roughness_scales_m': [3000.0, 700.0, 150.0],
           'deposition': 0.6, 'age_myr': 6.0, 'max_steps': 8000, 'repose_deg': 33.0, 'later': 'evolve',
           'later_frac': 0.12,
           'weather_m_per_yr': '$weathering_m_per_yr', 'weather_area': '$fraying', 'weather_loose': 0.3,
           'joints': JOINTS, 'joint_gain': 1.8, 'resist': 1.0, 'resist_run': 0.3, 'resist_noise': 0.5,
           'resist_scales_m': [1500.0, 600.0, 240.0, 90.0, 35.0], 'resist_cores': CORES,
           'caprock_target': 0.08, 'caprock_zs_m': CAP_BASE_ZS, 'check_every': 40}
# The rock breakup on the hero levels gives the walls the strength field's relief (fluting along the joints) but no
# second failure: the composite threshold has already brought every face to its bed's angle there, and the
# breakup's own threshold at that angle failed the weaker half of every face top up to 2 m deep at once, its scar
# stopping at the rim cell by cell: a staircase of flat-topped steps along the caps' rims (incised_meanders)
BREAKUP = {'threshold': 'field', 'rock_slope_deg': [35.0, 50.0], 'spread_deg': 8.0, 'iterations': 0}

MESAS_BUTTES = Recipe(
    'mesas_buttes', 'Mesas and buttes: flat caprock remnants, sheer walls over talus pedestals, a broad desert floor',
    references=['monument_valley'],
    defaults={'size': 8000.0, 'context': 2, 'hero_cell': 0.5, 'base_elevation_m': 1520.0, 'lakes': 'sediment',
              'palette': S.palette_for('desert_sandstone', COLUMN)},
    knobs={
        'caprock_fraction': Knob(0.08, '', (0.005, 0.6), 'the share of the main tile still at or above the '
                                                         "De Chelly's base when the first pass stops (the later "
                                                         'passes then retreat the walls for 0.12 of its time; '
                                                         'Monument Valley: its butte and mesa tops and walls about '
                                                         '0.06-0.08; a young plateau edge 0.3+)', apply=_cap),
        'relief_m': Knob(340.0, 'm', (50.0, 2000.0), "the cap rock's top above the wash's final bed (the Mittens "
                                                     'stand about 300-330 m over the floor; 340 puts the start at '
                                                     "the Shinarump's top)", apply=_surface),
        'floor_zs_m': Knob(140.0, 'm', (0.0, 500.0), "where in the column the wash's bed sits (140: 10 m under "
                                                     "the Cedar Mesa's top, which the floor is stripped to)",
                           apply=_surface),
        'weathering_m_per_yr': Knob(2e-4, 'm/yr', (0.0, 3e-3), 'how fast rock of erodibility factor 1 on a '
                                                               '30-degree slope wears down (the Organ Rock shale '
                                                               'x2.5, the De Chelly x0.08): the walls\' retreat (at '
                                                               '1e-4 the escarpment had not retreated far enough '
                                                               'to free the buttes by the end of the run)'),
        'fraying': Knob(3.0, '', (0.0, 6.0), 'how much faster the walls wear back where runoff gathers (x 1 + '
                                             'this sqrt(area / 10 ha)): the escarpment frays into fingers that '
                                             'part into buttes'),
        'detail': Knob(True, 'bool', None, 'joint-guided rock breakup on the hero levels', apply=_detail),
    },
    stages=[
        Stage('strata', STRATA, levels='all'),
        Stage('plateau', PLATEAU, levels='all'),
        Stage('river_path', RIVER, levels='all'),
        Stage('strata_fluvial', FLUVIAL, levels='all'),
        Stage('breakup', BREAKUP, levels='hero'),
    ],
    doc='Plateau of layered rock -> a wash cut to the floor (base-level fall) -> the walls retreat by weathering '
        'and failure until the caprock fraction is reached, then on at finer cells (talus pedestals, buttes) -> '
        'rock breakup (hero).')

RECIPES = [MESAS_BUTTES]
