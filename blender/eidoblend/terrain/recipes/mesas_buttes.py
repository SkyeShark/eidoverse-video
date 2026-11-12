"""mesas_buttes: flat caprock remnants standing on talus over a broad desert floor (design section 5), judged against
Monument Valley.

    t = make_terrain('mesas_buttes', params={'caprock_fraction': 0.05}, focus=(-1100, -40))

The stages (solvers/strata.py, solvers/rivers.py): Monument Valley's column (the Cedar Mesa sandstone the floor is
stripped to, the Organ Rock shale's slopes, the De Chelly sandstone's sheer walls, a thin Moenkopi slope and the
Shinarump cap); a plateau at the cap's top; a wash across the tile as the base level, cut down to the floor over
the first part of the run; then the walls retreat (weathering: the Organ Rock wears back under the De Chelly, which
fails over it at 84 degrees and leaves its debris as talus pedestals), fastest where runoff gathers, so the
escarpment frays into fingers, mesas and buttes. The run stops when the caprock left in the main tile (the ground at
or above the De Chelly's base) falls to `caprock_fraction`. Rock breakup on the hero levels.

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


# a 1-degree dip: the floor, stripped to the Cedar Mesa's top, then falls about 140 m across the tile, as Monument
# Valley's does (HI 0.26: a flat floor gave 0.08)
STRATA = {'column': COLUMN, 'zs0_m': '$floor_zs_m', 'dip_deg': 1.0, 'azimuth_deg': 160.0,
          'warp': [[3500.0, 6.0], [800.0, 2.0]]}
# two joint sets (the De Chelly's fracture pattern): weathering and incision run faster along them, so the
# escarpment frays into fingers and blocks with straight sides
JOINTS = [{'strike_deg': 20.0, 'spacing_m': 650.0, 'width_m': 35.0},
          {'strike_deg': 112.0, 'spacing_m': 900.0, 'width_m': 35.0}]
PLATEAU = {'surface_zs_m': 555.0, 'roughness': [[3000.0, 5.0], [600.0, 2.0], [120.0, 0.6]]}
RIVER = {'kind': 'walk', 'through': [0.0, 0.0], 'flow_azimuth_deg': 20.0, 'wiggle_deg': 22.0,
         'wiggle_wavelength_m': 3500.0, 'width_m': 40.0, 'bed_m': 0.0, 'gradient': 0.004,
         'schedule': [[0.0, 0.0], [0.25, 1.0], [1.0, 1.0]]}
# buttes outlive the escarpment's passage when it retreats mainly up its washes (the drainage boost, fraying) and
# a cut-off block only wears back slowly (the base weathering): with the base rate high the whole tile was stripped
# to the floor before any block stood alone
FLUVIAL = {'K': 1.5e-6, 'valley_spacing_m': 600.0, 'roughness': 0.6, 'roughness_scales_m': [3000.0, 700.0, 150.0],
           'deposition': 0.3, 'age_myr': 6.0, 'max_steps': 8000, 'repose_deg': 33.0, 'later': 'refine',
           'weather_m_per_yr': '$weathering_m_per_yr', 'weather_area': '$fraying', 'weather_loose': 0.6,
           'joints': JOINTS, 'joint_gain': 4.0,
           'caprock_target': 0.06, 'caprock_zs_m': CAP_BASE_ZS, 'check_every': 40}

MESAS_BUTTES = Recipe(
    'mesas_buttes', 'Mesas and buttes: flat caprock remnants, sheer walls over talus pedestals, a broad desert floor',
    references=['monument_valley'],
    defaults={'size': 8000.0, 'context': 2, 'hero_cell': 0.5, 'base_elevation_m': 1520.0, 'lakes': 'sediment',
              'palette': S.palette_for('desert_sandstone', COLUMN)},
    knobs={
        'caprock_fraction': Knob(0.06, '', (0.005, 0.6), 'the share of the main tile still at or above the '
                                                         "caprock's base when the run stops (Monument Valley: "
                                                         'about 0.06; a young plateau edge 0.3+)', apply=_cap),
        'relief_m': Knob(440.0, 'm', (50.0, 2000.0), 'the cap rock\'s top above the floor\'s lowest bed',
                         apply=_surface),
        'floor_zs_m': Knob(120.0, 'm', (0.0, 500.0), "where in the column the wash's bed sits (120: 30 m under "
                                                     "the Cedar Mesa's top, which the floor is stripped to)",
                           apply=_surface),
        'weathering_m_per_yr': Knob(1e-4, 'm/yr', (0.0, 3e-3), 'how fast rock of erodibility factor 1 on a '
                                                               '30-degree slope wears down (the Organ Rock shale '
                                                               'x3, the De Chelly x0.1): the walls\' retreat'),
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
        Stage('breakup', {'threshold': 'field', 'rock_slope_deg': [35.0, 50.0], 'spread_deg': 8.0}, levels='hero'),
    ],
    doc='Plateau of layered rock -> a wash cut to the floor (base-level fall) -> the walls retreat by weathering '
        'and failure until the caprock fraction is reached (talus pedestals, buttes) -> rock breakup (hero).')

RECIPES = [MESAS_BUTTES]
