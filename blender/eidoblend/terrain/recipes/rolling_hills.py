"""rolling_hills: soil-mantled rolling hills with convex tops and dense dendritic drainage (design section 5), judged
against the Palouse hills.

    t = make_terrain('rolling_hills', params={'relief_m': 120, 'valley_spacing_m': 250})

A plateau uplifted slowly (low U/K) and carved by the fluvial backbone with creep strong against incision, so the
hillslopes never reach their threshold: convex hilltops (creep's parabolic profile), narrow valleys, one drainage
network at the valley spacing. Below the main level the hills stay smooth (no gully schedule): their eye-level detail
is the soil's and the vegetation's.
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage


def _start(p):
    p.stage('uplift')['start_m'] = 1.2 * float(p['relief_m'])


FLUVIAL = dict(K=2e-5, valley_spacing_m='$valley_spacing_m', threshold_deg=35.0, threshold_noise=0.1,
               threshold_scale_m=400.0, roughness='$roughness', roughness_scales_m=[1500.0, 300.0, 60.0],
               deposition='$deposition', age_myr='$age_myr', relief_m='$relief_m', relief_calib=0.75, gullies=False,
               breakup=0.0, outcrops=0.0)

ROLLING_HILLS = Recipe(
    'rolling_hills', 'Soil-mantled rolling hills: convex tops, dense dendritic drainage',
    references=['palouse_hills'],
    defaults={'size': 4000.0, 'context': 4, 'hero_cell': 0.5, 'palette': 'farmland', 'base_elevation_m': 650.0},
    knobs={
        'relief_m': Knob(120.0, 'm', (5.0, 800.0), "the main tile's relief (the controller steers the uplift to it)",
                         apply=_start),
        'valley_spacing_m': Knob(300.0, 'm', (30.0, 3000.0),
                                 "the smallest valleys' spacing (the Palouse: 333 m between valleys 1 m deep)"),
        'age_myr': Knob(1.0, 'Myr', (0.1, 10.0), 'erosion time on the coarsest level'),
        'roughness': Knob(0.4, '', (0.0, 1.5), 'erodibility noise at 1.5 km, 300 m and 60 m'),
        'deposition': Knob(0.3, '', (0.0, 2.0), 'G: sediment deposition on the valley floors'),
    },
    stages=[
        Stage('uplift', {'shape': {'kind': 'plateau', 'centre': [0.0, 0.0], 'radius_m': 7000.0, 'edge_m': 3000.0,
                                   'texture': 0.25},
                         'U_m_per_yr': 2e-4, 'start_m': 150.0, 'start_roughness': 0.4}, levels='all'),
        Stage('fluvial', FLUVIAL, levels='all'),
    ],
    doc='A slowly uplifted plateau carved by the fluvial backbone with creep strong against incision: hillslopes '
        'stay under their threshold, so hilltops are convex and the valleys narrow.')

RECIPES = [ROLLING_HILLS]
