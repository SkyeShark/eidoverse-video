"""mesas_buttes: flat caprock remnants standing on talus over a broad desert floor (design section 5), judged against
Monument Valley.

    t = make_terrain('mesas_buttes', params={'caprock_fraction': 0.05}, focus=(-1100, -40))

The stages (solvers/strata.py, solvers/rivers.py): Monument Valley's column (the Cedar Mesa sandstone the floor is
stripped to, the Organ Rock shale's pedestal about 125 m, the De Chelly sandstone's sheer walls about 165 m and a
thin conglomerate cap: the free buttes' proportions on the DEM, the cliff the taller); a plateau at the cap's top; a
winding wash across the tile as the base level, cut down to the floor over the first part of the run; then the walls
retreat (weathering: the Organ Rock wears back under the De Chelly, which fails over it at 80 degrees and leaves its
debris as talus pedestals), fastest where runoff gathers, so the escarpment frays into fingers, and it passes the
massive cores of the De Chelly, which it leaves standing: cores of many sizes (many small, few large) in groups with
open ground between, long along the joints, each its own outline, so the remnants run from mesas through buttes and
slender buttes to spires on their pedestals and low capless cones. The massive rock stands sheer; the shale under it
stands at its own angle (resist_run_beds 'strong'), so every pedestal is as broad as Monument Valley's, and a core
narrower than its pedestal's run leaves a spire or a cone, not a steep plinth. The first pass, on the coarsest level's
62.5 m cells, stops when the caprock left in the main tile (the ground at or above the De Chelly's base) falls to
`caprock_fraction` (or at its age); the coarsest level's later passes (31 m, 15.6 m) go on evolving for 0.12 of its
time, so the walls retreat further and stand again at each finer cell, sheer under sharp rims. The floor follows the
Cedar Mesa's top, which undulates a metre or two over 90-260 m: low swells, ledges and swales. Rock breakup's relief
on the hero levels.

Heights: z = 0 is the wash's final bed at the tile centre; base_elevation_m (1520 m) places it.
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import strata as S

COLUMN = 'monument_valley'
CAP_BASE_ZS = S.column(COLUMN).base_of('De Chelly')          # 275 m: the caprock is the De Chelly and above


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
# massive cores in the De Chelly (strata.rock_cores): the escarpment retreats past them and leaves them standing
# (without them it frayed into fingers that were all stripped before any stood alone: no butte in the tile). Every
# core is the rock mass at its strongest (strength 4.5 x 0.75-1.25 against n's clip at 3.5) and the rock mass weighs
# 1.0 in the erodibility and the weathering (FLUVIAL's resist): a core's walls then wear back about a thirtieth as
# fast as the escarpment's, so a block outlives its passage.
# What a core leaves is its size less its pedestal: the shale stands at its own angle, so the pedestal's foot sits
# about 250-300 m out from the cliff's top (Monument Valley's 80 % of the pedestal's height is lost 220 m from the
# cliff's foot). A core narrower than that leaves a spire on its pedestal or a capless cone, one of 300-450 m radius
# a butte, a larger one a mesa. The sizes follow a power law (p(r) ~ r^-2.2 over 280-900 m: many small, few large) and the
# cores stand in groups with open ground between (a world noise 6 km across keeps about two thirds of the plane;
# a pair stands at least 1.4 km x (r1 + r2) / 1180 m apart: big blocks keep their distance, small ones may stand
# close, as the Mittens and Merrick Butte; four darts per spacing squared, so the distances are irregular). Rounded
# (elliptic, up to 1.6 long, along the joints +-35 degrees, the outline wobbling 0.3): long straight walls along one
# joint set added up in the 4-fold aspect harmonic.
# (The cores before, 1.3 km apart in blue noise and 360-840 m across, stood as about twenty buttes of one size at
# near-even spacing from the air; with the shale at its own angle they left one capped butte and six cones.)
CORES = {'spacing_m': 1400.0, 'radius_m': [280.0, 900.0], 'size_power': 2.2, 'elongation': [1.0, 1.6],
         'angles_deg': [20.0, 80.0], 'angle_jitter_deg': 35.0, 'strength': 4.5, 'region_m': 40000.0,
         'exponent': 2.0, 'wobble': 0.3, 'darts': 4.0, 'spacing_by_size': True,
         'cluster': {'wavelength_m': 6000.0, 'cover': 0.65, 'soft': 0.35}}
PLATEAU = {'surface_zs_m': 460.0, 'roughness': [[3000.0, 5.0], [600.0, 2.0], [120.0, 0.6]]}
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
# The rock mass's run factor steepens the massive formations only (resist_run_beds 'strong'): with it on every bed the
# Organ Rock under the cores stood at 45-60 degrees (its own angle is 34, the DEM's pedestals' upper halves 30-35), so
# every butte stood on a steep banded plinth that read as part of its wall, the cliff about as tall as its pedestal,
# and a worn core ended as a pointed banded cone. With it on the De Chelly alone the cliff stands sheer and the
# pedestal at the shale's angle: on the main level the cliff drops about 170 m at 64 degrees over 60 m (the DEM's free
# buttes 150 m at 63 over 46) onto a pedestal of about 125 m that loses 80 % of its height 225 m out (the DEM's
# 90-120 m and 220 m).
FLUVIAL = {'K': 1.5e-6, 'valley_spacing_m': 600.0, 'roughness': 0.6, 'roughness_scales_m': [3000.0, 700.0, 150.0],
           'deposition': 0.6, 'age_myr': 6.0, 'max_steps': 8000, 'repose_deg': 33.0, 'later': 'evolve',
           'later_frac': 0.12,
           'weather_m_per_yr': '$weathering_m_per_yr', 'weather_area': '$fraying', 'weather_loose': 0.3,
           'joints': JOINTS, 'joint_gain': 1.8, 'resist': 1.0, 'resist_run': 0.3, 'resist_run_beds': 'strong',
           'resist_noise': 0.5, 'resist_scales_m': [1500.0, 600.0, 240.0, 90.0, 35.0], 'resist_cores': CORES,
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
        'relief_m': Knob(320.0, 'm', (50.0, 2000.0), "the cap rock's top above the wash's final bed (the Mittens "
                                                     'stand about 300-330 m over the floor; 320 puts the start at '
                                                     "the Shinarump's top)", apply=_surface),
        'floor_zs_m': Knob(140.0, 'm', (0.0, 500.0), "where in the column the wash's bed sits (140: 10 m under "
                                                     "the Cedar Mesa's top, which the floor is stripped to)",
                           apply=_surface),
        'weathering_m_per_yr': Knob(2.2e-4, 'm/yr', (0.0, 3e-3), 'how fast rock of erodibility factor 1 on a '
                                                                 '30-degree slope wears down (the Organ Rock shale '
                                                                 'x2.5, the De Chelly x0.08): the walls\' retreat '
                                                                 '(at 1e-4 the escarpment had not retreated far '
                                                                 'enough to free the buttes by the end of the run; '
                                                                 'at 2e-4, with cores large enough for their '
                                                                 'pedestals, the plateau kept a sixth of the main '
                                                                 'tile and its rim zone 5 % against Monument '
                                                                 "Valley's 2.5)"),
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
