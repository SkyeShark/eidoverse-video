"""fluvial_range: a mountain range carved by rivers (design section 5), judged against the San Gabriel Mountains.

    t = make_terrain('fluvial_range', params={'relief_m': 2000, 'valley_spacing_m': 400}, focus=(800, -1200))

The stages: an uplift ridge with spurs (every level; the coarsest level's start is the ridge raised to a rough
600 m), then the fluvial backbone on every level (solvers/fluvial.py: the coarsest level grows the range
coarse-to-fine to near steady state with the relief controller; every finer level refines it under the low-pass
lock, the valley spacing halving per level below the main one so the hillslopes gather gullies), with rock breakup
in the threshold field (ribs and chutes at 60, 20 and 7 m, strong-rock outcrops at 120 m; the threshold 8 % steeper
per hero level below the main one, so gully walls and ribs survive), then the detail package's rock breakup (rock
from 28 degrees) and hydraulic rills on the hero levels (knob `detail`).
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage

SHAPES = {
    'ridge': {'kind': 'ridge', 'centre': [0.0, 0.0], 'azimuth_deg': 70.0, 'length_m': 24000.0, 'width_m': 12000.0,
              'spurs': 8, 'spur_length_m': 5500.0, 'texture': 0.3},
    'dome': {'kind': 'dome', 'centre': [0.0, 0.0], 'radius_m': 16000.0, 'texture': 0.3},
    'massif': {'kind': 'massif', 'centre': [0.0, 0.0], 'radius_m': 14000.0, 'peaks': 6, 'texture': 0.3},
    'plateau': {'kind': 'plateau', 'centre': [0.0, 0.0], 'radius_m': 14000.0, 'edge_m': 6000.0, 'texture': 0.3},
}


def _shape(p):
    spec = dict(SHAPES[p['uplift']])
    if spec['kind'] == 'ridge':
        spec['azimuth_deg'] = float(p['azimuth_deg'])
    p.stage('uplift')['shape'] = spec


def _rock(p):
    f = p.stage('fluvial')
    f['breakup'] = 0.15 * float(p['rock'])
    f['k_breakup'] = 0.5 * float(p['rock'])
    f['outcrops'] = 0.5 * float(p['rock'])


def _detail(p):
    for name in ('breakup', 'hydraulic'):
        for s in p.stages(name):
            s['enabled'] = bool(p['detail'])


FLUVIAL = dict(K=1.5e-5, valley_spacing_m='$valley_spacing_m', threshold_deg='$threshold_deg', threshold_noise=0.2,
               threshold_scale_m=400.0, threshold_gain=0.08, roughness='$roughness',
               roughness_scales_m=[2000.0, 300.0, 50.0], deposition='$deposition', age_myr='$age_myr',
               later_frac=0.5, relief_m='$relief_m', relief_calib=0.95, gullies='$gullies',
               breakup_scales_m=[60.0, 20.0, 7.0], outcrop_scale_m=120.0)

FLUVIAL_RANGE = Recipe(
    'fluvial_range', 'A mountain range carved by rivers: threshold hillslopes, branching valleys, alluvial floors',
    references=['san_gabriel_mountains'],
    # closed depressions fill with sediment (alluvial flats), not water: a river-carved range has none on its main
    # level, and on the hero levels the detail pass's talus dams made 4 m ponds in the valley floors
    defaults={'size': 12000.0, 'context': 4, 'hero_cell': 0.5, 'palette': 'alpine', 'base_elevation_m': 400.0,
              'lakes': 'sediment'},
    knobs={
        'relief_m': Knob(2000.0, 'm', (100.0, 6000.0),
                         "the main tile's relief: the controller steers the uplift on the coarsest level to it"),
        'valley_spacing_m': Knob(400.0, 'm', (40.0, 5000.0),
                                 "the smallest valleys' spacing on the main level (the San Gabriels: 444 m between "
                                 "valleys 5 m deep; D = K (spacing / 26)^2)"),
        'threshold_deg': Knob(32.0, 'deg', (15.0, 60.0), "the hillslopes' median failure angle (lognormal: sigma "
                                                         "0.2 at 400 m, 0.15 rock breakup at 60-7 m; with the "
                                                         "outcrops the slopes' median lands near 36, the San "
                                                         "Gabriels')"),
        'age_myr': Knob(2.0, 'Myr', (0.2, 10.0), 'erosion time on the coarsest level (near steady state from 2 Myr)'),
        'roughness': Knob(0.6, '', (0.0, 1.5), 'erodibility noise at 2 km, 300 m and 50 m: irregular valleys'),
        'deposition': Knob(0.5, '', (0.0, 2.0), 'G: sediment deposition (0 bedrock rivers, about 1 alluvial floors)'),
        'rock': Knob(1.0, '', (0.0, 3.0), 'rock breakup: the threshold field\'s ribs and chutes (60/20/7 m) and '
                                          'strong outcrops (120 m)', apply=_rock),
        'gullies': Knob(True, 'bool', None, 'below the main level the valley spacing halves per level: gullies'),
        'uplift': Knob('ridge', 'choice', tuple(SHAPES), 'the uplift shape (core/compose)', apply=_shape),
        'azimuth_deg': Knob(70.0, 'deg', (0.0, 360.0), "the ridge's strike, compass degrees"),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup and hydraulic rills on the hero levels",
                       apply=_detail),
    },
    stages=[
        Stage('uplift', {'shape': dict(SHAPES['ridge']), 'U_m_per_yr': 3e-3, 'start_m': 600.0,
                         'start_roughness': 0.4}, levels='all'),
        Stage('fluvial', FLUVIAL, levels='all'),
        # the threshold slopes stand at 30-40 degrees; the detail package's default rock mask (38-52 degrees) left
        # them smooth planes seen from a valley floor, so here rock starts at 28 degrees
        Stage('breakup', {'rock_slope_deg': [28.0, 40.0]}, levels='hero'),
        Stage('hydraulic', {}, levels='hero'),
    ],
    doc='Uplift ridge + spurs -> the fluvial backbone (grown coarse-to-fine on the coarsest level, refined below '
        'it with the valley spacing halving per hero level) -> rock breakup and hydraulic rills on the hero levels.')

RECIPES = [FLUVIAL_RANGE]
