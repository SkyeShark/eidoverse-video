"""caldera: an eroded stratovolcano whose summit collapsed into a scalloped caldera with cliff-banded walls over talus,
a lake standing at its own level, and a cinder cone on a lava platform inside (design 4.7 and section 5), judged
against Crater Lake.

    t = make_terrain('caldera', seed=5)                                         # Crater Lake-like, 14 km
    t = make_terrain('caldera', params={'lake_below_rim_m': 700, 'island': False})    # a deep, nearly dry one

Stages, in order (solvers/volcanic.py unless named):
  stratovolcano    the edifice (Mount Mazama's remnant as measured: H 1639 m, lambda 5474 m, R 25 km) with parasitic
                   cones on its outer flanks; every level
  volcano_age      the edifice eroded for its age before the collapse (400 kyr: radial valleys on the outer flanks),
                   time-faithful on the main level, refined under the lock on the hero levels
  caldera_collapse the ring-fault collapse: a scalloped outline (9 embayments, the 8 x 10 km oval of Crater Lake),
                   walls of lava flows and welded tuff standing as cliffs over weaker beds (a 38-degree mean face over
                   a talus apron at 33 degrees), the floor 980 m under the rim, the inner cone on its lava platform
  threshold        (solvers/hillslope.py) the walls at the strength they were built with: what aging steepened fails
  talus            (solvers/hillslope.py) the debris at repose on the loose apron
  volcano_age      (named wall_age) the walls gullied since the collapse (7.7 kyr at Crater Lake): chutes, and fans at
                   their feet; the caldera is a closed basin (no pit filling)
  caldera_lake     the lake at its own level (389 m under the mean rim at Crater Lake, not at the lowest notch); every
                   other closed depression filled with sediment. The runner's end-stage lakes are off (lakes False)
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import volcanic as V

_P = V.CRATER_LAKE
_C0 = _P['centre']
_E = dict(_P['edifice'])

EDIFICE = dict(centre=[0.0, 0.0], height_m=_E['height_m'], radius_m=_E['radius_m'],
               upper_slope_deg=_E['upper_slope_deg'], crater_radius_m=_E['crater_radius_m'],
               height_noise=_E['height_noise'], radius_noise=_E['radius_noise'], rift_azimuth_deg=330.0,
               rift=dict(_P['flank_cones']))

AGE = dict(age_yr=4.0e5, K=3.0e-6, threshold_deg=36.0, threshold_noise=0.2, deposition=1.0, roughness=0.8,
           roughness_scales_m=[1500.0, 300.0, 80.0], valley_spacing_m=350.0, centre=[0.0, 0.0],
           seed_texture_m=3.0, seed_texture_scale_m=250.0)

COLLAPSE = dict(centre=[0.0, 0.0], rim_radius_m=_P['rim_radius_m'], floor_below_rim_m=980.0,
                wall_deg=_P['wall_deg'], talus_deg=_P['talus_deg'], talus_frac=_P['talus_frac'],
                scallops=_P['scallops'], scallop_amp=_P['scallop_amp'], radius_noise=_P['radius_noise'],
                edge_noise=_P['edge_noise'], elongation=_P['elongation'],
                elongation_azimuth_deg=_P['elongation_azimuth_deg'],
                cliffs=dict(strong_deg=72.0, strong_frac=0.4, layer_m=[30.0, 120.0], sectors=7),
                inner_cones=[dict(c, at=[c['at'][0] - _C0[0], c['at'][1] - _C0[1]]) for c in _P['inner_cones']])

WALL_AGE = dict(age_yr=7700.0, K=1.0e-5, threshold_deg=40.0, threshold_noise=0.1, deposition=1.0, roughness=0.8,
                roughness_scales_m=[400.0, 120.0, 40.0], valley_spacing_m=120.0, fill_pits=False,
                strength_from_field=True, steps=400, seed_texture_m=1.5, seed_texture_scale_m=60.0)


def _apply(p):
    c = [float(v) for v in p['centre']]
    e = p.stage('stratovolcano')
    e.update(centre=c, height_m=float(p['edifice_height_m']), radius_m=float(p['edifice_radius_m']))
    p.stage('volcano_age').update(age_yr=float(p['age_kyr']) * 1000.0, centre=c)
    col = p.stage('caldera_collapse')
    k = float(p['rim_radius_m']) / float(_P['rim_radius_m'])
    col.update(centre=c, rim_radius_m=float(p['rim_radius_m']), floor_below_rim_m=float(p['floor_below_rim_m']))
    col['cliffs'] = dict(COLLAPSE['cliffs'], strong_frac=float(p['cliff_fraction']))
    col['inner_cones'] = ([dict(cn, at=[cn['at'][0] * k, cn['at'][1] * k], width_m=cn['width_m'] * min(k, 1.0))
                           for cn in COLLAPSE['inner_cones']] if p['island'] else [])
    p.stage('caldera_lake').update(centre=c, below_rim_m=float(p['lake_below_rim_m']),
                                   enabled=float(p['lake_below_rim_m']) < float(p['floor_below_rim_m']))


CALDERA = Recipe(
    'caldera', 'A collapse caldera: an eroded edifice, scalloped cliff-banded walls over talus, a lake at its own '
               'level, an inner cone',
    references=['crater_lake'],
    defaults={'size': 14000.0, 'context': 2, 'hero_cell': 0.5, 'palette': 'volcanic', 'base_elevation_m': 1500.0,
              'lakes': False},
    knobs={
        'rim_radius_m': Knob(float(_P['rim_radius_m']), 'm', (500.0, 20000.0),
                             "the rim's mean radius (Crater Lake 4.7 km; the outline 8 x 10 km)"),
        'floor_below_rim_m': Knob(980.0, 'm', (50.0, 2000.0), 'the collapsed floor under the mean rim'),
        'lake_below_rim_m': Knob(389.0, 'm', (0.0, 2000.0),
                                 'the lake surface under the mean rim (Crater Lake 389 m); at or under the floor: dry'),
        'cliff_fraction': Knob(0.4, '', (0.0, 0.9), "the walls' share of strong lava and tuff standing as cliffs"),
        'edifice_height_m': Knob(float(_E['height_m']), 'm', (300.0, 5000.0), "the edifice above its foot"),
        'edifice_radius_m': Knob(float(_E['radius_m']), 'm', (3000.0, 60000.0), "the edifice's foot radius"),
        'age_kyr': Knob(400.0, 'kyr', (1.0, 3000.0), 'the edifice eroded this long before the collapse'),
        'island': Knob(True, 'bool', None, 'the inner cinder cone on its lava platform (Wizard Island)'),
        'centre': Knob([0.0, 0.0], 'list', None, "the caldera's centre, world metres", apply=_apply),
    },
    stages=[
        Stage('stratovolcano', dict(EDIFICE), levels='all'),
        Stage('volcano_age', dict(AGE), levels=['main', 'hero']),
        Stage('caldera_collapse', dict(COLLAPSE), levels=['main', 'hero']),
        Stage('threshold', {'iterations': 64}, levels=['main', 'hero']),
        Stage('talus', {'repose_deg': 33.0, 'iterations': 64}, levels=['main', 'hero']),
        Stage('volcano_age', dict(WALL_AGE), levels=['main', 'hero'], name='wall_age'),
        Stage('caldera_lake', {'centre': [0.0, 0.0], 'below_rim_m': 389.0}, levels=['main', 'hero']),
    ],
    doc='The edifice -> eroded for its age -> the ring-fault collapse with cliff-banded walls, talus and the inner '
        'cone -> the walls failing at their strength, talus at repose -> gullied since the collapse -> the lake at '
        'its own level.')

RECIPES = [CALDERA]
