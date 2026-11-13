"""incised_meanders: an entrenched meandering canyon (design section 5), judged against the Goosenecks of the San
Juan River.

    t = make_terrain('incised_meanders', params={'sinuosity': 3.5, 'depth_m': 300}, focus=(-40, 250))

The canyon recipe's processes (solvers/strata.py) with a Kinoshita meander train for the river (solvers/rivers.py):
the river keeps its loops while it cuts down through flat-lying beds, so the canyon follows every bend, the spurs
inside the loops stand as stepped noses between them, and the necks between neighbouring loops thin to a few hundred
metres (each loop its own size; none closes). The column is the Goosenecks': the Paradox formation's cliffs at the
river, the Honaker Trail's cliffs, ledges and slopes above it up to the rim's ledge, the Halgaito's red slope set
back from the rim, and the thin Cedar Mesa bed; the plateau is an older erosion surface truncating the gently warped
beds, so it weathers into low cuestas and benches where the Cedar Mesa bed crops out over the Halgaito.

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


# the beds are gently warped (8 m at 2 km, 4 m at 600 m, 1.5 m at 200 m) and the plateau is an older erosion surface
# that truncates them (follow_warp False): the thin Cedar Mesa bed crops out in patches over the Halgaito, so the
# plateau weathers into low cuestas, benches and washes, as the Goosenecks' does (slope p50 15 degrees; a surface on
# the bed itself stayed a smooth flat, p50 2)
STRATA = {'column': 'honaker_trail', 'zs0_m': '$river_zs_m', 'dip_deg': 0.3, 'azimuth_deg': 30.0,
          'warp': [[2000.0, 8.0], [600.0, 4.0], [200.0, 2.0], [70.0, 0.8]]}
# the old surface is rough at 25-600 m (the Goosenecks' plateau has slope p50 15 degrees at 6 m: ledges, low
# cuestas and washes; at 4 / 1.5 / 0.5 m it stayed a smooth flat round the belt, p50 7.5)
PLATEAU = {'surface_zs_m': 410.0, 'follow_warp': False,
           'roughness': [[2500.0, 6.0], [600.0, 5.0], [200.0, 3.0], [60.0, 1.6], [25.0, 0.6]]}
# the loops vary one by one (vary over 1.3 meander wavelengths, the skew too: some lean downstream, some up), and a
# loop whose limbs would pass closer than min_neck_m is shrunk until they do not: thin necks, never a crossing; the
# belt is centred on the tile (centre 'axis': anchored at a loop's apex it lay a loop's amplitude off, a flat
# plateau filling half the tile); the San Juan runs pool and drop (pools 350 m apart, scoured 4 m, each holding
# flat water: defaults['lakes'] 'lake')
RIVER = {'kind': 'kinoshita', 'through': [0.0, 0.0], 'centre': 'axis', 'flow_azimuth_deg': '$flow_azimuth_deg',
         'wavelength_m': '$meander_wavelength_m', 'sinuosity': '$sinuosity', 'skew': 0.03, 'flat': 0.02,
         'vary': 0.35, 'vary_scale': 1.3, 'vary_skew': 0.05, 'min_neck_m': 250.0, 'width_m': '$river_width_m',
         'bed_m': 0.0, 'gradient': 0.0004, 'growth': '$loop_growth', 'growth_stages': 16,
         'schedule': [[0.0, 0.0], [0.7, 1.0], [1.0, 1.0]], 'pool_spacing_m': 350.0, 'pool_depth_m': 4.0,
         'pool_riffle': 0.07}
# K 6e-7, valleys 900 m apart and a weak drainage boost: the Goosenecks' plateau is barely cut by side washes (at
# 1.5e-6 and 300 m every rim was combed by an even sunburst of gullies; at 8e-7 with 600 m the tributaries ate a 4 km
# belt of ridges round the river); the slow weathering keeps the canyon about as narrow as its depth. The rock mass
# varies (strata.rock_mass, 18 m to 700 m): sheer buttresses and chutes on the walls, mostly in their angle.
# (dry_basins: the plateau's closed basins fill with sand, so only the river's pools hold water)
# The beds' facies change along the walls (strata.facies: 250 m along, 25 m up): a ledge is a cliff in one bend and
# a slope in the next, so the walls' bands vary in width round every loop instead of running as even concentric
# contours; and cliff rock wears by failing, not by surface wear (weather_k_exp 2), so the Paradox cliffs stand
# near-vertical over the river as at the Goosenecks (at the K factor itself they wore back into stepped ramps)
FLUVIAL = {'K': 6e-7, 'valley_spacing_m': 900.0, 'roughness': 0.4, 'roughness_scales_m': [2000.0, 400.0, 80.0],
           'deposition': 0.1, 'age_myr': '$age_myr', 'repose_deg': 34.0, 'later': 'refine',
           'weather_m_per_yr': '$weathering_m_per_yr', 'weather_area': 0.15, 'weather_loose': 0.5,
           'resist_scales_m': [700.0, 260.0, 100.0, 40.0, 18.0], 'dry_basins': True,
           'facies': {'strength': 0.45, 'scale_m': 250.0, 'scale_z_m': 25.0, 'weather': 0.5}, 'weather_k_exp': 2.0}


def _rock(p):
    f = p.stage('strata_fluvial')
    f['resist_run'] = float(p['rock_variety'])
    f['resist'] = 0.3 * float(p['rock_variety'])

INCISED_MEANDERS = Recipe(
    'incised_meanders', 'An entrenched meandering canyon: a river looping through flat-lying beds, stepped spurs, '
                        'thin necks',
    references=['goosenecks'],
    defaults={'size': 6000.0, 'context': 2, 'hero_cell': 0.5, 'base_elevation_m': 1200.0, 'lakes': 'lake',
              'palette': S.palette_for('desert_sandstone', 'honaker_trail')},
    knobs={
        'depth_m': Knob(350.0, 'm', (40.0, 2000.0), "the plateau's surface above the river's final bed: the Cedar "
                                                    "Mesa sandstone's, standing kilometres back from the rim (the "
                                                    "Goosenecks: the bench round the canyon 210-250 m over the river, "
                                                    "its highest ground 400 m)", apply=_surface),
        'river_zs_m': Knob(80.0, 'm', (0.0, 2000.0), "where in the column the river's final bed sits (metres above "
                                                     "its base: 80 is in the Paradox formation's upper cliff, so the "
                                                     "rim ledge's top stands 240 m over the river)", apply=_surface),
        'sinuosity': Knob(4.3, '', (1.0, 4.5), 'river length over down-valley length (Kinoshita) before the necks '
                                               'are kept open: the Goosenecks about 3.6-4 (open bends 1.5-2.5, '
                                               'closing loops 4+)'),
        'meander_wavelength_m': Knob(6000.0, 'm', (300.0, 30000.0), 'the river length of one meander (two bends); '
                                                                    'down-valley it is this / sinuosity (the '
                                                                    'Goosenecks: loops about 1.5-2 km apart)'),
        'loop_growth': Knob(1.0, '', (0.1, 1.0), "the loops' amplitude when the cutting starts, as a fraction of "
                                                 'the final: below 1 they grow outward while the river cuts down, '
                                                 'undercutting the outer walls and leaving slip-off slopes inside '
                                                 'the loops (1, the default: a fixed course; the Goosenecks\' spurs '
                                                 'are steep on both sides, and 0.55 left long slip-off slopes in '
                                                 'concentric terraces dotted with the abandoned channel\'s pits)'),
        'rock_variety': Knob(0.5, '', (0.0, 1.5), "how much the rock mass's strength varies (18 m to 700 m): "
                                                  'sheer buttresses where it is strong, chutes over talus where it '
                                                  'is weak; 0: every layer one angle along the whole wall',
                             apply=_rock),
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
