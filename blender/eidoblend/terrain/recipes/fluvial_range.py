"""fluvial_range: a mountain range carved by rivers (design section 5), judged against the San Gabriel Mountains.

    t = make_terrain('fluvial_range', params={'relief_m': 2000, 'valley_spacing_m': 320}, focus=(800, -1200))

The stages:
  uplift        a ridge with spurs, 60 km along its strike and 14 km across, joined to a regional background of lower massifs over
                the whole 192 km window with unuplifted lowlands between them that drain to its edge, so from a
                summit or the air ranges stand behind ranges into the haze instead of the ground falling to a
                base-level plain at 24 km; the coarsest level's start is that uplift raised to a rough 600 m
  fluvial       the backbone on every level (solvers/fluvial.py: the coarsest level grows the range coarse-to-fine
                to near steady state with the relief controller; every finer level refines it under the low-pass
                lock, the valley spacing halving per level below the main one so the hillslopes gather gullies).
                Two fault zones along the strike (crushed rock, 3.5 x the erodibility, wandering 600 m) guide a
                few deep longitudinal trunk canyons, as the San Gabriel River's forks follow the San Gabriel fault,
                and rock strength varying across kilometres (rock_contrast) grows large side basins between long
                main ridges instead of evenly spaced spurs. Rock breakup in the threshold field: ribs and chutes at 60, 20
                and 7 m and strong-rock outcrops at 120 m, the threshold 8 % steeper per hero level below the main
                one, so buttresses and couloirs stand on the hillslopes instead of planar facets
  valley_floor  alluvial floors: the trunk canyons' valleys filled flat to the width of their floor (knob
                floor_width_m where 50 km2 drains, growing with the square root of the area), tributary mouths
                backfilled to it - the flat floor route 39 runs along in the San Gabriel canyon
  breakup, hydraulic   the detail package's rock breakup (rock from 28 degrees) and hydraulic rills on the hero
                levels (knob `detail`)
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage

STRIKE_DEG = 70.0
SHAPES = {
    # longer than the 48 km context: the range runs on past the horizon along its strike
    # 14 km across its spine: at 22 km (closer to the San Gabriels with their front ranges) the interior drained
    # badly within its growth, basins between the spurs filled flat and 8 % of the main tile lay under 5 degrees
    'ridge': {'kind': 'ridge', 'centre': [0.0, 0.0], 'azimuth_deg': STRIKE_DEG, 'length_m': 60000.0,
              'width_m': 14000.0, 'spurs': 12, 'spur_length_m': 6000.0, 'texture': 0.3},
    'dome': {'kind': 'dome', 'centre': [0.0, 0.0], 'radius_m': 16000.0, 'texture': 0.3},
    'massif': {'kind': 'massif', 'centre': [0.0, 0.0], 'radius_m': 14000.0, 'peaks': 6, 'texture': 0.3},
    'plateau': {'kind': 'plateau', 'centre': [0.0, 0.0], 'radius_m': 14000.0, 'edge_m': 6000.0, 'texture': 0.3},
}
# the fault zones along the strike: offsets across it from the range's axis (metres, to the right of the strike)
FAULT_OFFSETS_M = (-2800.0, 2300.0)


def _faults(strike_deg, k_factor):
    return [{'centre': [0.0, 0.0], 'azimuth_deg': float(strike_deg), 'offset_m': off, 'width_m': 300.0,
             'k_factor': float(k_factor), 'wander_m': 600.0, 'wander_wavelength_m': 9000.0}
            for off in FAULT_OFFSETS_M] if float(k_factor) > 1.0 else None


def _shape(p):
    spec = dict(SHAPES[p['uplift']])
    if spec['kind'] == 'ridge':
        spec['azimuth_deg'] = float(p['azimuth_deg'])
    p.stage('uplift')['shape'] = spec
    p.stage('fluvial')['faults'] = _faults(p['azimuth_deg'], p['trunk_faults'])


def _rock(p):
    f = p.stage('fluvial')
    f['breakup'] = 0.3 * float(p['rock'])
    f['k_breakup'] = 0.5 * float(p['rock'])
    f['outcrops'] = 0.5 * float(p['rock'])


def _detail(p):
    for name in ('breakup', 'hydraulic'):
        for s in p.stages(name):
            s['enabled'] = bool(p['detail'])


FLUVIAL = dict(K=1.5e-5, valley_spacing_m='$valley_spacing_m', threshold_deg='$threshold_deg', threshold_noise=0.2,
               threshold_scale_m=400.0, threshold_gain=0.08, roughness='$roughness',
               roughness_scales_m=[2000.0, 600.0, 150.0, 50.0], deposition='$deposition', age_myr='$age_myr',
               later_frac=0.5, relief_m='$relief_m', relief_calib=0.85, gullies='$gullies',
               k_contrast='$rock_contrast', k_contrast_scales_m=[3000.0, 1500.0],
               breakup_scales_m=[60.0, 20.0, 7.0], outcrop_scale_m=120.0,
               faults=_faults(STRIKE_DEG, 2.5))

FLUVIAL_RANGE = Recipe(
    'fluvial_range', 'A mountain range carved by rivers: threshold hillslopes, branching valleys, alluvial floors',
    references=['san_gabriel_mountains'],
    # closed depressions fill with sediment (alluvial flats), not water: a river-carved range has none on its main
    # level, and on the hero levels the detail pass's talus dams made 4 m ponds in the valley floors.
    # context 16 (192 km): from the summit (3.3 km up) the window's edge, 96 km out, sits at the true horizon, under
    # 90 km of haze; at context 4 its 24 km edge was a ruler-straight band behind the ridges. The outer three levels
    # grow (run.py grow_levels): the 192 and 96 km levels grow the far ranges at 188 and 94 m, the 48 km level grows
    # the range itself at 47 m as before, from its parent instead of from its own pre-passes
    defaults={'size': 12000.0, 'context': 16, 'grow_levels': 3, 'hero_cell': 0.5, 'palette': 'alpine',
              'base_elevation_m': 400.0, 'lakes': 'sediment'},
    knobs={
        'relief_m': Knob(2000.0, 'm', (100.0, 6000.0),
                         "the main tile's relief: the controller steers the uplift on the coarsest level to it"),
        'valley_spacing_m': Knob(320.0, 'm', (40.0, 5000.0),
                                 "the smallest valleys' spacing on the main level (D = K (spacing / 26)^2); "
                                 "below the main level it halves per level when `gullies` is on"),
        'threshold_deg': Knob(29.0, 'deg', (15.0, 60.0), "the hillslopes' median failure angle (lognormal: sigma "
                                                         "0.2 at 400 m, 0.3 rock breakup at 60-7 m; with the "
                                                         "outcrops the slopes' median lands near 36, the San "
                                                         "Gabriels')"),
        'age_myr': Knob(2.0, 'Myr', (0.2, 10.0), 'erosion time on the coarsest level (near steady state from 2 Myr)'),
        'roughness': Knob(0.6, '', (0.0, 1.5), 'erodibility noise at 2 km, 600, 150 and 50 m: irregular valleys and '
                                               'spurs'),
        'rock_contrast': Knob(0.35, '', (0.0, 1.2), "rock strength varying across kilometres: erodibility x exp(c n) "
                                                    "at 3 and 1.5 km. Weak ground grows large side basins, strong "
                                                    "ground long main ridges between them (the San Gabriels' 1-2 km "
                                                    "valleys); 0: one rock, evenly spaced spurs along every ridge "
                                                    "(the 11-12 review's corduroy). At 0.5 the 0.1-1 km2 valleys "
                                                    "stood 266 m deep (San Gabriels 239, none 297) and the relief in "
                                                    "2 km windows varied 0.31 (0.30; none 0.22), but the weak ground "
                                                    "cut down took the hypsometric integral to its band's floor"),
        'deposition': Knob(0.5, '', (0.0, 2.0), 'G: sediment deposition in the fluvial law (0 bedrock rivers)'),
        'floor_width_m': Knob(170.0, 'm', (0.0, 600.0),
                              "the alluvial floor's width where 50 km2 drains (it grows with the square root of the "
                              "area, from 5 km2; 0: V-shaped valleys). The San Gabriel River's canyon floor, where "
                              "route 39 runs beside the river, is 150-300 m wide; at 110 m the main tile's trunk "
                              "floor was 60-80 m, a crease from the road's height"),
        'trunk_faults': Knob(3.5, '', (1.0, 6.0), "the erodibility of the two fault zones along the strike that the "
                                                  "trunk canyons follow (1: none; at 2.5 the strike valleys broke "
                                                  "into segments draining sideways, and no trunk in the main tile "
                                                  "drained over 40 km2)", apply=_shape),
        'rock': Knob(1.0, '', (0.0, 3.0), 'rock breakup: the threshold field\'s ribs and chutes (60/20/7 m) and '
                                          'strong outcrops (120 m)', apply=_rock),
        'gullies': Knob(True, 'bool', None, 'below the main level the valley spacing halves per level: gullies'),
        'uplift': Knob('ridge', 'choice', tuple(SHAPES), 'the uplift shape (core/compose)', apply=_shape),
        'azimuth_deg': Knob(STRIKE_DEG, 'deg', (0.0, 360.0), "the ridge's strike (and the fault zones'), compass "
                                                             "degrees"),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup and hydraulic rills on the hero levels",
                       apply=_detail),
    },
    stages=[
        # the regional background: lower massifs 10-20 km across (the Transverse Ranges round the San Gabriels), up
        # to half the main range's uplift, with unuplifted lowlands between them (cut: about two thirds of the
        # window) that drain to its edge. Ridged noise with no cut uplifted all 192 km at half the range's rate: a
        # 4-6 km plateau under the range, 9-11 km high after the growing levels, every basin closed and filling
        Stage('uplift', {'shape': dict(SHAPES['ridge']), 'U_m_per_yr': 3e-3, 'start_m': 600.0,
                         'start_roughness': 0.4,
                         'regional': {'kind': 'fbm', 'fraction': 0.5, 'wavelength_m': 24000.0, 'texture': 0.6,
                                      'octaves': 3, 'blend': 0.1, 'cut': 1.25}}, levels='all'),
        Stage('fluvial', FLUVIAL, levels='all'),
        # the floors on the main and hero levels only (filled on the context levels, wide shallow strike valleys
        # became kilometre-wide flat blobs that the main level inherited), and only where 5 km2 and more drains:
        # from 1 km2 every tributary got a strip of fill and 9 % of the tile was flat (the San Gabriels' 12 m DEM:
        # 0.9 % under 5 degrees)
        Stage('valley_floor', {'width_m': '$floor_width_m', 'area_ref_m2': 5.0e7, 'width_exp': 0.5,
                               'area_min_m2': 5.0e6, 'depth_max_m': 70.0}, levels=['main', 'hero']),
        # the threshold slopes stand at 30-40 degrees; the detail package's default rock mask (38-52 degrees) left
        # them smooth planes seen from a valley floor, so here rock starts at 28 degrees. It runs from the main level
        # down: the breakup adds a scale's relief only on the level that first resolves it, so on the hero levels
        # alone its 50 m buttresses never got any. The joint sets are couloirs that read from 30-300 m (8-10 m wide,
        # 3-4 m deep, 45-60 m apart), not 1 m grooves
        Stage('breakup', {'rock_slope_deg': [28.0, 40.0], 'relief': 0.3,
                          'joints': [{'strike_deg': 15.0, 'spacing_m': 45.0, 'width_m': 9.0, 'stretch': 2.5,
                                      'strength': 0.9, 'depth_m': 3.5},
                                     {'strike_deg': 105.0, 'spacing_m': 60.0, 'width_m': 7.0, 'stretch': 2.0,
                                      'strength': 0.7, 'depth_m': 2.5}]}, levels=['main', 'hero']),
        Stage('hydraulic', {}, levels='hero'),
    ],
    doc='Uplift ridge + spurs over a regional background of lower ranges -> the fluvial backbone with two fault '
        'zones guiding the trunk canyons (grown coarse-to-fine on the coarsest level, refined below it with the '
        'valley spacing halving per hero level) -> alluvial valley floors -> rock breakup and hydraulic rills on '
        'the hero levels.')

RECIPES = [FLUVIAL_RANGE]
