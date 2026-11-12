"""incised_meanders: an entrenched meandering canyon (design section 5), judged against the Goosenecks of the San
Juan River.

    t = make_terrain('incised_meanders', params={'sinuosity': 3.5, 'depth_m': 300}, focus=(-40, 250))

The canyon recipe's processes (solvers/strata.py) with a Kinoshita meander train for the river (solvers/rivers.py):
the river keeps its loops while it cuts down through flat-lying beds, so the canyon follows every bend, the spurs
inside the loops stand as stepped noses between them, and the necks between neighbouring loops thin to a few hundred
metres. The column is the Goosenecks': the Paradox formation's cliffy limestone at the river, the Honaker Trail's
ledges and slopes above it, the Halgaito's red slopes and the Cedar Mesa sandstone the plateau is stripped to.

Heights: z = 0 is the river's final bed at the tile centre; base_elevation_m (1200 m, the San Juan's) places it.
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import strata as S


def _surface(p):
    p.stage('plateau')['surface_zs_m'] = float(p['river_zs_m']) + float(p['depth_m'])


def _fall(p):
    f = min(max(float(p['fall_frac']), 0.05), 1.0)
    p.stage('river_path')['schedule'] = [[0.0, 0.0], [f, 1.0], [1.0, 1.0]]


def _detail(p):
    for s in p.stages('breakup'):
        s['enabled'] = bool(p['detail'])


STRATA = {'column': 'honaker_trail', 'zs0_m': '$river_zs_m', 'dip_deg': 0.3, 'azimuth_deg': 30.0,
          'warp': [[3000.0, 4.0], [700.0, 1.5]]}
PLATEAU = {'surface_zs_m': 400.0, 'roughness': [[2500.0, 4.0], [500.0, 1.5], [100.0, 0.5]]}
RIVER = {'kind': 'kinoshita', 'through': [0.0, 0.0], 'flow_azimuth_deg': '$flow_azimuth_deg',
         'wavelength_m': '$meander_wavelength_m', 'sinuosity': '$sinuosity', 'skew': 0.03, 'flat': 0.02,
         'vary': 0.3, 'width_m': '$river_width_m', 'bed_m': 0.0, 'gradient': 0.0004, 'growth': '$loop_growth',
         'growth_stages': 16, 'schedule': [[0.0, 0.0], [0.7, 1.0], [1.0, 1.0]]}
# K 8e-7 and a weak drainage boost: the Goosenecks' plateau is barely cut by side washes (1.5e-6 combed every rim
# with gullies); the slow weathering keeps the canyon about as narrow as its depth (faster widened it to 2x)
FLUVIAL = {'K': 8e-7, 'valley_spacing_m': 300.0, 'roughness': 0.4, 'roughness_scales_m': [2000.0, 400.0, 80.0],
           'deposition': 0.1, 'age_myr': '$age_myr', 'repose_deg': 34.0, 'later': 'refine',
           'weather_m_per_yr': '$weathering_m_per_yr', 'weather_area': 0.15}

INCISED_MEANDERS = Recipe(
    'incised_meanders', 'An entrenched meandering canyon: a river looping through flat-lying beds, stepped spurs, '
                        'thin necks',
    references=['goosenecks'],
    defaults={'size': 6000.0, 'context': 2, 'hero_cell': 0.5, 'base_elevation_m': 1200.0, 'lakes': 'sediment',
              'palette': S.palette_for('desert_sandstone', 'honaker_trail')},
    knobs={
        'depth_m': Knob(330.0, 'm', (40.0, 2000.0), "the plateau's surface above the river's final bed (the "
                                                    "Goosenecks: about 300 m to the rim)", apply=_surface),
        'river_zs_m': Knob(40.0, 'm', (0.0, 2000.0), "where in the column the river's final bed sits (metres above "
                                                     "its base: 40 is the Paradox formation's)", apply=_surface),
        'sinuosity': Knob(3.8, '', (1.0, 4.5), 'river length over down-valley length (Kinoshita): the Goosenecks '
                                               'about 3.6-4 (open bends 1.5-2.5, closing loops 4+)'),
        'meander_wavelength_m': Knob(7000.0, 'm', (300.0, 30000.0), 'the river length of one meander (two bends); '
                                                                    'down-valley it is this / sinuosity (the '
                                                                    'Goosenecks: loops about 2 km apart)'),
        'loop_growth': Knob(0.55, '', (0.1, 1.0), "the loops' amplitude when the cutting starts, as a fraction of "
                                                  'the final: they grow outward while the river cuts down, so the '
                                                  'outer walls are undercut cliffs and the spurs inside the loops '
                                                  'long slip-off slopes (1: a fixed course, symmetric walls)'),
        'flow_azimuth_deg': Knob(285.0, 'deg', (0.0, 360.0), "the river's down-valley direction, compass degrees"),
        'river_width_m': Knob(50.0, 'm', (8.0, 400.0), "the river's channel width"),
        'weathering_m_per_yr': Knob(6e-5, 'm/yr', (0.0, 3e-3), 'how fast rock of erodibility factor 1 on a '
                                                                 '30-degree slope wears down (shale x2.5, cliff '
                                                                 'rock x0.2): the walls\' retreat; 0: they stand '
                                                                 'where the river left them'),
        'age_myr': Knob(1.5, 'Myr', (0.2, 10.0), 'the time the coarsest level runs'),
        'fall_frac': Knob(0.7, '', (0.05, 1.0), 'the share of that time the river takes to cut to its bed',
                          apply=_fall),
        'detail': Knob(True, 'bool', None, 'rock breakup on the hero levels', apply=_detail),
    },
    stages=[
        Stage('strata', STRATA, levels='all'),
        Stage('plateau', PLATEAU, levels='all'),
        Stage('river_path', RIVER, levels='all'),
        Stage('strata_fluvial', FLUVIAL, levels='all'),
        Stage('breakup', {'threshold': 'field', 'rock_slope_deg': [32.0, 45.0], 'spread_deg': 10.0}, levels='hero'),
    ],
    doc='The canyon recipe with a Kinoshita meander train: strata -> plateau -> river path (loops) with a '
        'base-level fall -> fluvial with K(zs), the composite threshold and weathering -> rock breakup (hero).')

RECIPES = [INCISED_MEANDERS]
