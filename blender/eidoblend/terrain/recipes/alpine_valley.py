"""alpine_valley: a glacial U-valley (design section 5), judged against Lauterbrunnen (and Yosemite Valley).

    t = make_terrain('alpine_valley', params={'ela_m': 2300, 'trough_width_m': 1400}, focus=(0, -1500))
    from eidoblend.terrain.recipes import alpine_valley as AV
    t = make_terrain('alpine_valley', **AV.preset('yosemite'))     # a granite trough in a domed upland

The defaults are Lauterbrunnen's: a 1.2 km trough with 600 m limestone walls under benches (Muerren, Wengen) in a
horseshoe of high ridges, draining north. PRESETS hold other settings as make_terrain keyword arguments (knobs,
base elevation, size): 'yosemite', a 2.2 km flat-floored trough with 900 m granite walls and no benches, cut into a
gently domed upland draining west.

The stages:
  1. valley_uplift (every level): a range around one main valley, a crest across its head and two side ridges along
     it (solvers/glacial.py 'horseshoe', Lauterbrunnen's setting: the valley drains north); the coarsest level's
     start is that shape raised to a rough 600 m;
  2. fluvial (every level, kept off the trough with where='1 - trough'): the river-carved range the ice works on,
     grown coarse-to-fine to near steady state on the coarsest level, refined below it;
  3. glacial (every level): on the coarsest level, once it is fully grown, the ice discharge, the cirques, the
     U-carve with hanging tributaries, the fresh walls' threshold and lateral moraines; on the finer levels the walls
     keep their steep threshold and fail at it at each level's own scale where the rock is weak;
  4. the end stage fills the overdeepened basins with sediment (flat floors; defaults['lakes'] = 'lake' keeps them
     as ribbon lakes and tarns);
  5. talus (levels with cells of 16 m and finer): the walls' debris at 35 degrees;
  6. rock breakup and hydraulic rills on the hero levels (knob `detail`);
  7. the snow and tree lines for the masks (knobs snowline_m, treeline_m).
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage

SHAPES = {
    # a crest across the valley's head and two side ridges along it (solvers/glacial.py HORSESHOE): Lauterbrunnen's
    # Jungfrau-Breithorn wall at the head, the Schilthorn and Maennlichen ridges either side
    # (a 26 km crest 7.5 km out with 4.5 km falloffs tilted the whole tile north and combed it into four parallel
    # troughs; side ridges near the tile's edges and a narrower crest further out give one trunk with short
    # tributaries square to it, as the real catchment has. The side ridges stand at 0.65 of the crest: the real tile's
    # relief comes from the Jungfrau spurs at its head, its sides are lower, and equal ridges all round made every
    # slope 40-45 degrees)
    'horseshoe': {'kind': 'horseshoe', 'centre': [0.0, 0.0], 'azimuth_deg': 0.0, 'crest_offset_m': 6000.0,
                  'crest_length_m': 14000.0, 'crest_width_m': 5000.0, 'side_offset_m': 3800.0,
                  'side_shift_m': 1000.0, 'side_length_m': 16000.0, 'side_width_m': 3600.0, 'side_height': 0.65,
                  'join': 0.12, 'texture': 0.3},
    # the Sierra Nevada's west slope at Yosemite: the high country up at the valley's head beyond the tile, the
    # uplands either side at half its height. Their ice stays thin (below the ELA) and one valley glacier comes down
    # from the head (side uplands as high as the crest grew glaciers radiating every way, an ice cap with no trunk)
    'upland': {'kind': 'horseshoe', 'centre': [0.0, 0.0], 'azimuth_deg': 270.0, 'crest_offset_m': 9000.0,
               'crest_length_m': 24000.0, 'crest_width_m': 7000.0, 'side_offset_m': 4500.0, 'side_shift_m': 0.0,
               'side_length_m': 26000.0, 'side_width_m': 5000.0, 'side_height': 0.5, 'join': 0.12, 'texture': 0.25},
    'ridge': {'kind': 'ridge', 'centre': [0.0, 0.0], 'azimuth_deg': 70.0, 'length_m': 24000.0, 'width_m': 12000.0,
              'spurs': 8, 'spur_length_m': 5500.0, 'texture': 0.3},
    'massif': {'kind': 'massif', 'centre': [0.0, 0.0], 'radius_m': 14000.0, 'peaks': 6, 'texture': 0.3},
}


def _shape(p):
    spec = dict(SHAPES[p['uplift']])
    if spec['kind'] == 'horseshoe':
        spec['azimuth_deg'] = float(p['drain_azimuth_deg'])
    p.stage('valley_uplift')['shape'] = spec


def _detail(p):
    for name in ('breakup', 'hydraulic'):
        for s in p.stages(name):
            s['enabled'] = bool(p['detail'])


def _defaults_for(values):
    """The snow and tree lines (altitudes) for the masks."""
    return {'mask_params': {'snowline_m': float(values['snowline_m']), 'treeline_m': float(values['treeline_m'])}}


def _tributaries(p):
    p.stage('glacial')['channel_area_m2'] = float(p['tributary_area_km2']) * 1.0e6


# (threshold_iters 4: at 2 a step the slopes ran about 10 degrees past their threshold under the uplift a 2.5 km
# range needs; breakup 0.3 and k_breakup 1: rock steps and ledges at 60-7 m, the texture the real walls carry)
FLUVIAL = dict(K=1.5e-5, valley_spacing_m='$valley_spacing_m', threshold_deg='$threshold_deg', threshold_noise=0.2,
               threshold_scale_m=400.0, threshold_gain=0.08, roughness=0.6, roughness_scales_m=[2000.0, 300.0, 50.0],
               deposition=0.5, age_myr='$age_myr', later_frac=0.5, relief_m='$relief_m', relief_calib=0.95,
               gullies=True, breakup=0.3, k_breakup=1.0, outcrops=0.5, breakup_scales_m=[60.0, 20.0, 7.0],
               outcrop_scale_m=120.0, threshold_iters=4)

# (u_exponent 3 with floor_rise 0.04: a cliff over 65 degrees from about 200 m above the floor to the lip at 79
# degrees, over a fan-and-talus toe; on the generated tiles the judge's U-fit reads 1.3 at a 0.06 rise and 2.0 at
# 0.03, the flat ground's share 0.08 and 0.10: 0.04 sits between. smooth_cells 12: a glacier cuts through its
# river's bends, so the trough runs straighter than the valley it took over)
GLACIAL = dict(ela_m='$ela_m', trough_width_m='$trough_width_m', trough_depth_m='$trough_depth_m',
               wall_deg='$wall_deg', moraine_m='$moraine_m', cirques='$cirques', u_exponent=3.0,
               floor_frac='$floor_share', floor_rise=0.04, overdeepen=0.6, shoulder_width='$shoulder_width',
               shoulder_rise=0.3, cut=0.6, cut_width=2.0, floor_grade=0.012, wall_noise=0.25,
               wall_scales_m=[400.0, 120.0, 40.0], channel_area_m2=1.5e6, smooth_cells=12.0, rock_flutes=0.6)

# other places as make_terrain keyword arguments (preset())
PRESETS = {
    # Yosemite: one wide trough in a granite upland that ice smoothed rather than cut into cirques (80 cirques at
    # every channel head made a field of flat-floored ovals), with few hanging tributaries (Yosemite and Bridalveil
    # Creeks)
    'yosemite': dict(size=12000.0, base_elevation_m=1100.0, params={
        'uplift': 'upland', 'drain_azimuth_deg': 270.0, 'relief_m': 1100.0, 'ela_m': 2100.0,
        'trough_width_m': 2200.0, 'trough_depth_m': 900.0, 'floor_share': 0.45, 'shoulder_width': 0.0,
        'wall_deg': 78.0, 'threshold_deg': 20.0, 'valley_spacing_m': 800.0, 'cirques': False,
        'tributary_area_km2': 5.0, 'snowline_m': 3300.0, 'treeline_m': 3000.0}),
}


def preset(name, **params):
    """make_terrain keyword arguments for a PRESETS entry; extra knobs override the preset's."""
    if name not in PRESETS:
        raise KeyError(f'no alpine_valley preset {name!r}; presets: {", ".join(PRESETS)}')
    p = dict(PRESETS[name])
    p['params'] = dict(p['params'], **params)
    return p

ALPINE_VALLEY = Recipe(
    'alpine_valley', 'A glacial U-valley: a flat floor between sheer walls, hanging side valleys, cirques, aretes '
                     'and horns, talus',
    references=['lauterbrunnen', 'yosemite_valley'],
    defaults={'size': 8000.0, 'context': 4, 'hero_cell': 0.5, 'palette': 'alpine', 'base_elevation_m': 800.0,
              'lakes': 'sediment'},
    knobs={
        'relief_m': Knob(2600.0, 'm', (500.0, 6000.0),
                         "the river-carved range's relief on the main tile before the ice (the controller steers the "
                         "uplift to it); the trough is cut into it"),
        'ela_m': Knob(1800.0, 'm', (0.0, 6000.0),
                      'the equilibrium-line altitude of the carving glaciation: glaciers grow above it and reach '
                      'down-valley until ablation eats them; lower it for longer, bigger troughs'),
        'trough_width_m': Knob(1200.0, 'm', (200.0, 6000.0),
                               "the trunk trough's width at its lip (tributaries are narrower by their ice "
                               "discharge, (Q / Q_trunk)^0.4)"),
        'trough_depth_m': Knob(750.0, 'm', (50.0, 2000.0), "the trunk trough's walls: from its floor to the lip"),
        'tributary_area_km2': Knob(1.5, '', (0.05, 100.0), "the smallest catchment (km2) whose glacier carves its own "
                                                          "trough; smaller ones only feed their trunk",
                                   apply=_tributaries),
        'floor_share': Knob(0.25, '', (0.0, 0.9), "the flat floor's share of the trough's half-width (the walls "
                                                  "rise from its edge; Yosemite's box trough about 0.45)"),
        'shoulder_width': Knob(1.5, '', (0.0, 5.0), "the benches above the trough's lip (Muerren, Wengen), as a "
                                                    "share of the trough's half-width; 0: none"),
        'wall_deg': Knob(76.0, 'deg', (35.0, 85.0), "the fresh trough walls' threshold angle (lognormal, with "
                                                    "fall-line couloirs and ribs on the levels that resolve them)"),
        'moraine_m': Knob(25.0, 'm', (0.0, 100.0), 'the lateral moraines along the trunk below the ELA (0: none)'),
        'cirques': Knob(True, 'bool', None, 'cirque bowls at the glacier heads near the ELA: aretes and horns '
                                            'between them'),
        'valley_spacing_m': Knob(200.0, 'm', (40.0, 5000.0), "the range's smallest valleys' spacing (200 m: the "
                                                             "couloirs and ribs of a rock range, and little creep "
                                                             "to round its crests)"),
        'threshold_deg': Knob(29.0, 'deg', (15.0, 60.0), "the range's hillslope failure angle above the trimline "
                                                         "(its median slope lands near 38: the outcrops and breakup "
                                                         "stand steeper)"),
        'age_myr': Knob(2.0, 'Myr', (0.2, 10.0), "the range's erosion time on the coarsest level"),
        'uplift': Knob('horseshoe', 'choice', tuple(SHAPES), 'the range around the valley', apply=_shape),
        'drain_azimuth_deg': Knob(0.0, 'deg', (0.0, 360.0), 'the compass direction the main valley drains toward '
                                                            '(horseshoe)'),
        'snowline_m': Knob(2750.0, 'm', (0.0, 8000.0), "today's snowline altitude, for the snow mask"),
        'treeline_m': Knob(1950.0, 'm', (0.0, 8000.0), 'the treeline altitude, for the vegetation mask'),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup and hydraulic rills on the hero levels",
                       apply=_detail),
    },
    stages=[
        Stage('valley_uplift', {'shape': dict(SHAPES['horseshoe']), 'U_m_per_yr': 3e-3, 'start_m': 600.0,
                                'start_roughness': 0.4}, levels='all'),
        Stage('fluvial', FLUVIAL, levels=['context', 'main'], where='1 - trough'),
        # on the hero levels the fluvial stage refines without moving the landform (its 'refine' mode: no slope's
        # threshold under the slope it inherits, so only new detail fails): run as on the coarser levels, its
        # threshold (about 37 degrees there) collapsed every cliff the carve left outside the trough mask - the
        # truncated spurs, the cirque headwalls - under a lock of 100-400 m blocks, raising their feet by up to 850 m
        Stage('fluvial', dict(FLUVIAL, mode='refine'), levels='hero', where='1 - trough', name='fluvial_hero'),
        Stage('glacial', GLACIAL, levels='all'),
        Stage('talus', {'repose_deg': 35.0, 'iterations': 64}, levels='cell<=16'),
        # (relief 0.6: the detail package's default 0.25 left the main level with a twentieth of the real tile's
        # power at 33 m and a sixth at 60 m: alpine rock carries more relief than its default)
        Stage('breakup', {'rock_slope_deg': [32.0, 45.0], 'relief': 0.6}, levels='cell<=16'),
        Stage('hydraulic', {}, levels='hero'),
    ],
    doc='A horseshoe range around one valley -> the fluvial backbone (kept off the trough below the coarsest level) '
        '-> the glacial carve on the grown coarsest level (ice discharge, cirques, U-troughs that deepen with '
        'discharge so tributaries hang, steep fresh walls, lateral moraines), the walls refined on every finer level '
        '-> sediment-filled flat floors -> talus -> rock breakup and rills on the hero levels.')
ALPINE_VALLEY.defaults_for = _defaults_for

RECIPES = [ALPINE_VALLEY]
