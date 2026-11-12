"""impact_crater: a simple bowl crater in flat-lying layered rock: a square-ish rim, cliff-banded upper walls over
talus, an infilled flat floor, a hummocky ejecta blanket, aged by gullies and creep (design 4.8 and section 5),
judged against Meteor Crater.

    t = make_terrain('impact_crater', seed=11)                                  # Meteor Crater-like, 3 km
    t = make_terrain('impact_crater', params={'diameter_m': 600, 'sides': 0, 'age_kyr': 500})   # a rounder, older one

Stages, in order (solvers/volcanic.py and impact.py unless named):
  volcano_setting  the plateau the crater is punched into: a plain falling 0.66 % toward compass 52 (the Colorado
                   Plateau round Meteor Crater, measured on the reference: 2.5 m of texture about that plane),
                   roughened by plain_texture_m
  fluvial          (solvers/fluvial.py) the washes: the plain eroded for half a million years with no uplift, its
                   rivers graded to the tile's low side, cutting shallow dendritic washes (a plateau is not uplifted
                   against its own edges: with uplift the relief controller domed the window 570 m high); on the
                   coarsest level only, before the impact (on the finer levels it would erode the crater itself)
  impact_crater    the crater (impact.py): Pike's bowl at depth 0.2 D, the rim 0.044 D above the plain, infilled to a
                   flat floor 0.143 D under the rim, a 4-sided rounded planform from the joint sets, rim height varying
                   with azimuth, the ejecta blanket (r/R)^-3 to 2.3 R with hummocks and blocks; the upper walls are
                   the target's beds (Kaibab and Coconino cliffs over weaker beds) over a talus apron; stamped on the
                   first level, sharpened on every finer one
  volcano_age      the crater's age: stream power and creep with the walls' own strength (gullies cut into the walls,
                   their debris on the floor, the rim crest rounded), the crater a closed basin (no pit filling)
  talus            (solvers/hillslope.py) the debris at repose on the hero levels
  volcano_lakes    the crater floor stays dry (a playa); the solvers' small pits on the plain fill with sediment
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import impact as I

_M = I.METEOR_CRATER
_D0 = float(_M['diameter_m'])

SETTING = dict(centre=[0.0, 0.0], basin_m=1.0e9, ramp_m=1.0, cover=1.0, texture=0.0, plain=1.0, U_m_per_yr=0.0,
               start_m='$plain_texture_m', start_roughness=0.8, patch_m=1500.0, plain_m=1683.0, plain_slope=0.0066,
               plain_down_azimuth_deg=52.0, plain_extent_m=20000.0)

WASHES = dict(K=2.0e-6, valley_spacing_m=150.0, threshold_deg=30.0, threshold_noise=0.2, threshold_scale_m=150.0,
              roughness=0.6, roughness_scales_m=[800.0, 200.0, 50.0], deposition=0.6, age_myr=0.5, later_frac=0.4,
              relief_m=None)

# Meteor Crater's walls: the Kaibab limestone and the Coconino sandstone stand as cliffs in the upper wall, over
# weaker beds and a talus apron (the reference: inner wall slopes p99 59 degrees at 3 m)
# (measured ring by ring against the reference: its lower wall is fans and talus at a median 23 degrees, its upper
# wall cliffs to a p90 of 47 degrees at 3 m, its rim's outer flank a median 11 degrees)
CLIFFS = dict(strong_deg=75.0, strong_frac=0.45, layer_m=[25.0, 60.0], sectors=9, talus_frac=0.4, talus_deg=26.0)

POLYGON = 0.35

CRATER = dict(centre=[0.0, 0.0], diameter_m=_D0, depth_ratio=_M['depth_ratio'], rim_ratio=_M['rim_ratio'],
              fill_ratio=_M['fill_ratio'], sides=_M['sides'], polygon=POLYGON,
              polygon_azimuth_deg=_M['polygon_azimuth_deg'], radius_noise=0.045, edge_noise=0.015,
              rim_noise=_M['rim_noise'], crest_round=0.5, ejecta_reach=_M['ejecta_reach'],
              rays=0.0, cliffs=dict(CLIFFS), supersample=2)

# the walls' chutes: Meteor Crater's upper wall is cut into radial gullies 20-40 m apart, their debris in fans on
# the lower wall and the floor; without them the strong beds read as rings running round the wall
#   the run cuts the crater (full K out to the rim) and barely touches the blanket and the plain beyond (the
#   reference's plain is smooth: slope p50 1 degree outside 2.5 R); in fractions of D, _apply scales them
K_PROFILE = [[0.0, 1.0], [0.5, 1.0], [0.6, 0.3], [1.0, 0.05]]

AGE = dict(age_yr=5.0e4, K=2.5e-5, threshold_deg=38.0, threshold_noise=0.15, deposition=1.0, roughness=0.9,
           roughness_scales_m=[120.0, 40.0, 12.0], valley_spacing_m=30.0, fill_pits=False,
           strength_from_field=True, seed_texture_m=1.0, seed_texture_scale_m=25.0, centre=[0.0, 0.0],
           k_profile=[[f * _D0, k] for f, k in K_PROFILE])

# the floor: lake beds, flat over about 30 % of the crater (Meteor Crater's bottom tenth: 28 % of it, 4.4 degrees)
LAKES = dict(dry=[dict(at=[0.0, 0.0], radius_m=0.5 * _D0, playa_frac=0.3)], mode='sediment')


def _apply(p):
    c = [float(v) for v in p['centre']]
    D = float(p['diameter_m'])
    cr = p.stage('impact_crater')
    cr.update(centre=c, diameter_m=D, rim_ratio=float(p['rim_ratio']), fill_ratio=float(p['depth_ratio']),
              sides=int(p['sides']), polygon=POLYGON if int(p['sides']) >= 3 else 0.0)
    cr['cliffs'] = dict(CLIFFS, strong_frac=float(p['cliff_fraction'])) if float(p['cliff_fraction']) > 0 else None
    p.stage('volcano_age').update(age_yr=float(p['age_kyr']) * 1000.0, centre=c,
                                  k_profile=[[f * D, k] for f, k in K_PROFILE])
    p.stage('volcano_lakes')['dry'] = [dict(at=c, radius_m=0.5 * D, playa_frac=0.3)]
    for st in p.stages('volcano_setting'):
        st['centre'] = c


IMPACT_CRATER = Recipe(
    'impact_crater', 'A simple impact crater: a square-ish rim, cliff-banded walls over talus, a flat infilled floor '
                     'and a hummocky ejecta blanket in flat-lying rock',
    references=['meteor_crater'],
    defaults={'size': 3000.0, 'context': 4, 'hero_cell': 0.25, 'palette': 'desert_sandstone',
              'base_elevation_m': 0.0, 'lakes': False},
    knobs={
        'diameter_m': Knob(_D0, 'm', (100.0, 1700.0),
                           'rim crest to rim crest (Meteor Crater 1194 m); simple craters only on Earth (under '
                           'about 1.75 km); the ejecta reaches 2.3 D / 2'),
        'depth_ratio': Knob(float(_M['fill_ratio']), '', (0.05, 0.2),
                            'rim crest to the infilled floor over D (Meteor Crater 0.143; Pike\'s fresh bowl 0.2)'),
        'rim_ratio': Knob(float(_M['rim_ratio']), '', (0.0, 0.06),
                          'the rim crest above the plain over D (Meteor Crater 0.044; Pike 0.036 fresh)'),
        'sides': Knob(int(_M['sides']), '', (0, 8), 'the planform\'s sides from the joint sets (Meteor Crater 4); '
                                                     '0 a round crater'),
        'cliff_fraction': Knob(CLIFFS['strong_frac'], '', (0.0, 0.9),
                               "the walls' share of strong beds standing as cliffs (0: a plain parabolic wall)"),
        'age_kyr': Knob(50.0, 'kyr', (0.0, 5000.0), 'time since the impact: gullies on the walls, debris on the '
                                                   'floor, the rim rounding (Meteor Crater about 50 kyr)'),
        'plain_texture_m': Knob(3.0, 'm', (0.0, 100.0), "the plain's own texture before the washes: low swells at "
                                                       'about 450 m (Meteor Crater 2.5 m rms about its plane)'),
        'centre': Knob([0.0, 0.0], 'list', None, "the crater's centre, world metres", apply=_apply),
    },
    stages=[
        Stage('volcano_setting', dict(SETTING), levels='all'),
        Stage('fluvial', dict(WASHES), levels='first'),
        Stage('impact_crater', dict(CRATER), levels='all'),
        Stage('volcano_age', dict(AGE), levels=['main', 'hero']),
        Stage('talus', {'repose_deg': 33.0, 'iterations': 48}, levels='hero'),
        Stage('volcano_lakes', dict(LAKES), levels='all'),
    ],
    doc='The plateau with its washes -> the crater stamped (bowl, infilled floor, cliff-banded walls, rim, ejecta) '
        "-> the crater's age (wall gullies, floor debris, a rounded rim) -> talus on the hero levels; the floor "
        'stays dry.')

RECIPES = [IMPACT_CRATER]
