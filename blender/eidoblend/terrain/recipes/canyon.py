"""canyon: a canyon cut into layered plateau rock (design section 5), judged against the Grand Canyon at Toroweap.

    t = make_terrain('canyon', params={'depth_m': 1400, 'flow_azimuth_deg': 235}, focus=(300, -900))

The stages (solvers/strata.py, solvers/rivers.py):
  strata          the stratigraphic column in world z (the Grand Canyon's Paleozoic section by default: Kaibab and
                  Toroweap ledges, the Coconino cliff, the Hermit slope, the Esplanade's bench, the Supai ledges, the
                  Redwall cliff, the Muav walls, the Bright Angel slope), dipping dip_deg, warped a little
  plateau         the start: the plateau's structural surface at depth_m above the river's final bed, following the
                  beds, roughened
  river_path      the river's course across every level (a smoothed random walk flowing toward flow_azimuth_deg)
  strata_fluvial  the river cuts down from the plateau to its final bed (the base-level fall: one steady fall over
                  the first 1 - inner_gorge_frac of the run, or with bench_layer a quick cut to that layer's top, a
                  long hold, and the inner gorge cut late), its tributaries cut back into the plateau, every wall
                  stands at its layer's own angle (the composite threshold: strong beds cliffs, weak ones slopes),
                  and the walls retreat by weathering (weak rock under a cliff wears back, the cliff fails over it;
                  faster where runoff gathers: side canyons), leaving the strong beds as benches; the debris rests
                  at repose and washes away
  breakup         joint-guided rock breakup on the hero levels (the detail package): buttresses, chutes and talus
                  at the foot of the walls

Heights: z = 0 is the river's final bed at the tile centre; base_elevation_m (505 m, Toroweap's river) places it.
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import strata as S


def _surface(p):
    """The plateau's structural surface: depth_m above the river's final bed, in the column's height."""
    p.stage('plateau')['surface_zs_m'] = float(p['river_zs_m']) + float(p['depth_m'])


def _fall(p):
    """The base-level fall in two stages, as the Grand Canyon's history: the river cuts quickly to the top of the
    bench layer and holds there while the upper walls retreat across the bench (most of the run), then cuts the
    inner gorge late, so its walls stay near their own angles (a single steady fall left them exposed for a million
    years and the weathering widened the gorge to twice Toroweap's). bench_layer None: one steady fall."""
    g = min(max(float(p['inner_gorge_frac']), 0.05), 0.9)
    depth = float(p['depth_m'])
    if p['bench_layer'] and depth > 0:
        col = S.column(p['column'])
        hb = col.top_of(p['bench_layer']) - float(p['river_zs_m'])        # the bench's top above the final bed
        fb = min(max((depth - hb) / depth, 0.0), 1.0)
        sch = [[0.0, 0.0], [0.15, fb], [1.0 - g, fb], [1.0 - 0.3 * g, 1.0], [1.0, 1.0]]
    else:
        sch = [[0.0, 0.0], [1.0 - g, 1.0], [1.0, 1.0]]
    p.stage('river_path')['schedule'] = sch


def _detail(p):
    for s in p.stages('breakup'):
        s['enabled'] = bool(p['detail'])


STRATA = {'column': '$column', 'zs0_m': '$river_zs_m', 'dip_deg': '$dip_deg', 'azimuth_deg': '$dip_azimuth_deg',
          'warp': [[4000.0, 10.0], [900.0, 3.0]]}
PLATEAU = {'surface_zs_m': 1765.0, 'roughness': [[3000.0, 6.0], [600.0, 2.5], [120.0, 0.8]]}
RIVER = {'kind': 'walk', 'through': [0.0, 0.0], 'flow_azimuth_deg': '$flow_azimuth_deg', 'wiggle_deg': 16.0,
         'wiggle_wavelength_m': 5000.0, 'width_m': '$river_width_m', 'bed_m': 0.0, 'gradient': 0.0015,
         'schedule': [[0.0, 0.0], [0.6, 1.0], [1.0, 1.0]]}
# K 1.5e-6: an arid plateau's (1.5e-5, a humid range's, sent tributary knickpoints 5 km/Myr through the Kaibab and
# dissected the whole plateau into a maze of peaks: slope p50 43 degrees against Toroweap's 15)
FLUVIAL = {'K': 1.5e-6, 'valley_spacing_m': '$valley_spacing_m', 'roughness': 0.4,
           'roughness_scales_m': [2500.0, 500.0, 90.0], 'deposition': 0.1, 'age_myr': '$age_myr',
           'repose_deg': 34.0, 'later': 'refine', 'weather_m_per_yr': '$weathering_m_per_yr',
           'weather_area': '$side_canyons'}

CANYON = Recipe(
    'canyon', 'A canyon in layered plateau rock: stepped cliffs and benches, tributaries, an inner gorge',
    references=['grand_canyon_toroweap'],
    defaults={'size': 8000.0, 'context': 2, 'hero_cell': 0.5, 'base_elevation_m': 505.0, 'lakes': 'sediment',
              'palette': S.palette_for('desert_sandstone', 'colorado_plateau')},
    knobs={
        'depth_m': Knob(1445.0, 'm', (100.0, 3000.0), "the plateau's surface above the river's final bed at the "
                                                      "tile centre (Toroweap: the Kaibab rim 1445 m over the river)",
                        apply=_surface),
        'river_zs_m': Knob(325.0, 'm', (0.0, 3000.0), "where in the column the river's final bed sits (metres "
                                                      "above the column's base: 325 is the Bright Angel shale, "
                                                      "Toroweap's)", apply=_surface),
        'column': Knob('colorado_plateau', 'choice', tuple(S.COLUMNS),
                       'the stratigraphic column (solvers/strata.COLUMNS); the material bands follow the default '
                       "column: with another, pass palette=strata.palette_for('desert_sandstone', column)"),
        'dip_deg': Knob(0.3, 'deg', (0.0, 10.0), 'the beds\' dip (the plateau surface follows them)'),
        'dip_azimuth_deg': Knob(60.0, 'deg', (0.0, 360.0), 'the direction the beds rise toward (counter-clockwise '
                                                           'from +x)'),
        'flow_azimuth_deg': Knob(235.0, 'deg', (0.0, 360.0), "the river's down-valley direction, compass degrees"),
        'river_width_m': Knob(80.0, 'm', (10.0, 400.0), "the river's channel width"),
        'valley_spacing_m': Knob(500.0, 'm', (60.0, 5000.0), 'the smallest side canyons\' spacing on the main level'),
        'weathering_m_per_yr': Knob(3e-4, 'm/yr', (0.0, 3e-3), 'how fast rock of erodibility factor 1 on a '
                                                               '30-degree slope wears down (the Hermit shale x3.5, '
                                                               'cliff rock x0.2): the upper walls\' retreat over '
                                                               'the benches; 0: they stand where the river left '
                                                               'them (a V canyon)'),
        'side_canyons': Knob(0.5, '', (0.0, 3.0), 'how much faster the walls wear back where runoff gathers '
                                                  '(x 1 + this sqrt(area / 10 ha)): amphitheatres and side canyons '
                                                  'cut into the benches'),
        'age_myr': Knob(2.0, 'Myr', (0.2, 10.0), 'the time the coarsest level runs: the cut and then the walls\' '
                                                 'retreat'),
        'bench_layer': Knob(None, 'name', None, 'a layer whose top the river holds at for most of the run (the '
                                                '"Esplanade": a wide bench the upper walls retreat across and a '
                                                'young inner gorge cut late below it); None: one steady fall (the '
                                                'default: the two-stage cut left the inner gorge a straight '
                                                'polygonal slot with planar walls and the bench too wide)',
                            apply=_fall),
        'inner_gorge_frac': Knob(0.4, '', (0.05, 0.9), "two-stage: the share of the run left when the inner "
                                                       "gorge's cut begins (it takes 70 % of that; then the bed "
                                                       "holds); one steady fall: the share the bed holds at the end",
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
    doc='Layered plateau -> strata column -> river path with a base-level fall -> fluvial with K(zs) and the '
        'composite threshold (every level) -> rock breakup on the hero levels.')

RECIPES = [CANYON]
