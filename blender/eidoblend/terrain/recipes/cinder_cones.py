"""cinder_cones: a field of cinder cones on a lava plateau: one young cone at repose with its summit crater and the
thick basalt flow that left its foot, among older cones of mixed ages, lowered and rounded by creep, some breached
with flows of their own (design 4.7 and section 5), judged against SP Crater in the San Francisco volcanic field.

    t = make_terrain('cinder_cones', seed=9)                                    # SP Crater-like, 10 km
    t = make_terrain('cinder_cones', params={'count': 30, 'age_kyr_max': 2000})  # a bigger, older field

Stages, in order (solvers/volcanic.py unless named):
  volcano_setting  the lava plateau: a plain falling 3.2 % toward compass 18 (the slope round SP Crater), with low
                   swells (plain_texture_m). No fluvial stage: a young basalt plateau is permeable and barely drained
                   (with half a million years of stream power on its slope the 40 km context cut a corduroy of
                   valleys 100 m deep, and the finer levels eroded the cones)
  lava_flows       (named old_flows) the plateau's older flows from vents scattered over the field, on the main level
                   (made on the 39 m context level their margins upsampled into stair-steps along the grid): lobes and
                   fronts a few metres to 15 m high
  cinder_cones     the hero cone (fitted to SP Crater as the judge reads it: W 1420 m, H/W 0.188, crater 0.26 W,
                   flanks at 28 degrees) and the field round it: cones along three vent alignments, blue-noise spaced,
                   some coalescing, fissure-fed ones drawn out along their line, basal widths 330-1400 m, ages up to
                   age_kyr_max, each aged by linear creep kappa x its age (the exact Gaussian solution: older cones
                   lower, rounder, their craters shallower), some breached; every cone a pile at repose on the
                   plateau (volcanic.piles_on: on sloping ground its downhill flank is longer, never steeper)
  lava_flows       (named flows) DOWNFLOW flows: the hero cone's thick flow from its north foot (SP Crater's runs 7 km
                   north) and one from each breached cone, out of its breach, shorter and duller with age
  talus            (solvers/hillslope.py) scoria at repose on the hero levels
  volcano_lakes    every cone's crater stays dry (permeable scoria); the plateau's small pits fill with sediment
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import volcanic as V

_S = V.SP_CRATER

# (measured on the reference's ground, the 20th percentile by sector and distance from SP: the plateau falls 2.5 %
# toward compass 25 and rises 1.2 % the other way, and SP stands on a low shield of older flows: about 2010 m at its
# foot, 1920 m 1.5 km out, 1870 m by 3.5 km)
SETTING = dict(centre=[0.0, 0.0], basin_m=1.0e9, ramp_m=1.0, cover=1.0, texture=0.0, plain=1.0, U_m_per_yr=0.0,
               start_m='$plain_texture_m', start_roughness=0.8, patch_m=4000.0, plain_m=1865.0, plain_slope=0.025,
               plain_slope_up=0.012, plain_down_azimuth_deg=25.0, plain_extent_m=40000.0, shield_m=150.0,
               shield_radius_m=1500.0)

# DOWNFLOW's perturbation is a few metres (dh_factor 0.25 of the thickness): at 3 x the thickness every walker
# random-walked, and each flow came out a round pancake about its vent
OLD_FLOWS = dict(scatter=dict(window=[-6500.0, -6500.0, 13000.0], count=22, length_m=[2500.0, 9000.0],
                              thickness_m=[5.0, 15.0], age=[0.5, 1.0], width_m=[200.0, 900.0]),
                 dh_factor=0.25, walkers=200)

# SP Crater as measured (volcanic.SP_CRATER), its flanks a little under the 32-degree preset: the reference's flank
# p90 at 10 m is 27.5 degrees (median 29-31 on the cone itself, the crest and toe rounded)
#   fitted with the judge's own cone reader on a 10 m grid (the reference reads SP at H 246 m, W 1420 m, H/W 0.173,
#   flank p90 27.5): W 1420, H/W 0.188, crater 0.26 W, flanks 28 degrees, a 20 m crest, a level rim (a 5 % rim tilt
#   smears the radial mean's peak and reads 25 m lower) read 0.18 and 29.7; young, so only kappa t = 40 m2
HERO = dict(at=[0.0, 0.0], width_m=1420.0, hw_ratio=0.188, crater_ratio=0.26, flank_deg=28.0,
            crater_wall_deg=_S['crater_wall_deg'], crater_depth_frac=_S['crater_depth_frac'], crest_round_m=20.0,
            rim_tilt=0.02, tilt_azimuth_deg=_S['tilt_azimuth_deg'], outline_noise=0.02, seed=_S['seed'],
            age_yr=71000.0, kappa_t_m2=40.0)

# the field's cones are not gumdrops: fissure-fed ones elongated along their vent line, coalescing pairs, breached
# horseshoes with their flows (the reference's older cones round SP Crater)
FIELD = dict(window=[-5000.0, -5000.0, 10000.0], count=17, width_m=[330.0, 1400.0], hw_ratio=0.18,
             crater_ratio=[0.25, 0.42], flank_deg=[26.5, 29.5], vent_lines=3, line_spread_m=1400.0,
             age_yr=[150000.0, 900000.0], breach_fraction=0.4, outline_noise=0.05, elongation=[1.0, 1.35],
             overlap=0.35)

KAPPA = 0.002            # m2/yr, scoria creep: a 500 kyr cone smoothed by kappa t = 1000 m2 (sigma 45 m)

CONES = dict(cones=[dict(HERO)], field=dict(FIELD), kappa_m2_per_yr=KAPPA, supersample=1)

# SP Crater's flow: from its north foot 7 km down the plateau, 20-30 m thick, up to 1-2 km wide
LAVA = dict(vents=[dict(at=[0.0, 0.75 * HERO['width_m']], length_m=7000.0, thickness_m=22.0, age=0.05, dh_m=2.5,
                        width_m=900.0, walkers=800)],
            breaches=dict(cones=[dict(HERO)], field=dict(FIELD), kappa_m2_per_yr=KAPPA, length_m=3000.0,
                          thickness_m=10.0, age_span_yr=900000.0, width_m=400.0),
            dh_factor=0.25, walkers=500)

LAKES = dict(mode='sediment', dry_cones=dict(cones=[dict(HERO)], field=dict(FIELD), kappa_m2_per_yr=KAPPA))


def _apply(p):
    size = float(p['field_size_m'])
    c = [float(v) for v in p['centre']]
    field = dict(FIELD, window=[c[0] - size / 2, c[1] - size / 2, size], count=int(p['count']),
                 age_yr=[150000.0, max(float(p['age_kyr_max']) * 1000.0, 151000.0)])
    hero = dict(HERO, at=c)
    kappa = float(p['kappa_m2_per_yr'])
    cones = [hero] if p['hero_cone'] else []
    p.stage('cinder_cones').update(cones=cones, field=field, kappa_m2_per_yr=kappa)
    lava = p.stage('flows')
    lava['vents'] = ([dict(LAVA['vents'][0], at=[c[0], c[1] + 0.75 * float(HERO['width_m'])])]
                     if p['hero_cone'] and p['hero_flow'] else [])
    lava['breaches'] = dict(LAVA['breaches'], cones=cones, field=field, kappa_m2_per_yr=kappa)
    p.stage('volcano_lakes')['dry_cones'] = dict(cones=cones, field=field, kappa_m2_per_yr=kappa)
    for st in p.stages('volcano_setting'):
        st['centre'] = c


CINDER_CONES = Recipe(
    'cinder_cones', 'A cinder cone field: a young cone at repose with its flow among older, rounder, breached cones '
                    'on a lava plateau',
    references=['sp_crater'],
    defaults={'size': 8000.0, 'context': 4, 'hero_cell': 0.25, 'palette': 'volcanic', 'base_elevation_m': 0.0,
              'lakes': False},
    knobs={
        'count': Knob(17, '', (0, 80), 'cones in the field besides the hero cone (SP Crater: about 17 in 10 km)'),
        'age_kyr_max': Knob(900.0, 'kyr', (150.0, 5000.0), "the oldest cone's age; older cones are lower and "
                                                          'rounder (creep) with shallow craters'),
        'kappa_m2_per_yr': Knob(KAPPA, 'm2/yr', (0.0, 0.05), 'creep on the scoria (kappa x age smooths each cone)'),
        'field_size_m': Knob(10000.0, 'm', (1000.0, 40000.0), 'the square the field is scattered over'),
        'plain_texture_m': Knob(16.0, 'm', (0.0, 100.0), "the plateau's own swells at about 1.2 km down to 75 m "
                                                        '(round SP Crater its slopes have a median of 3.7 degrees)'),
        'hero_cone': Knob(True, 'bool', None, 'the young SP Crater-like cone at the centre'),
        'hero_flow': Knob(True, 'bool', None, "the hero cone's thick flow from its north foot"),
        'centre': Knob([0.0, 0.0], 'list', None, 'the hero cone, world metres', apply=_apply),
    },
    stages=[
        Stage('volcano_setting', dict(SETTING), levels='all'),
        Stage('lava_flows', dict(OLD_FLOWS), levels='main', name='old_flows'),
        Stage('cinder_cones', dict(CONES), levels='all'),
        Stage('lava_flows', dict(LAVA), levels='main', name='flows'),
        Stage('talus', {'repose_deg': 33.0, 'iterations': 48}, levels='hero'),
        Stage('volcano_lakes', dict(LAKES), levels='all'),
    ],
    doc='The lava plateau with its older flows -> the hero cone and the field, each aged by creep for its age -> the '
        "hero cone's flow and the breached cones' flows -> talus on the hero levels; the craters stay dry.")

RECIPES = [CINDER_CONES]
