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
  lava_flows       (named old_flows) the plateau's older flows, each from the foot of one of the field's cones, on the
                   main level (made on the 39 m context level their margins upsampled into stair-steps along the
                   grid): aa lobes with fronts 6-14 m high, dulled with age
  cinder_cones     the hero cone (fitted to SP Crater as the judge reads it: W 1420 m, H/W 0.188, crater 0.26 W,
                   flanks at 28 degrees, fresh: a sharp rim) and the field round it: cones along three vent alignments,
                   blue-noise spaced, some coalescing, fissure-fed ones drawn out along their line, basal widths
                   330-1400 m, ages up to age_kyr_max, each aged by linear creep kappa x its age (the exact Gaussian
                   solution: older cones lower, rounder, their craters shallower), some breached; every cone a pile at
                   repose on the plateau (volcanic.piles_on: on sloping ground its downhill flank is longer, never
                   steeper), its toe a distinct break
  lava_flows       (named flows) DOWNFLOW flows: the hero cone's thick compound aa flow leaving its north foot at full
                   thickness in a channel a third of its width and opening into lobes (SP Crater's runs 7 km north:
                   rubble fronts and margins at 35 degrees, broad levees, a ridged top), parting round the cones in its
                   way, and one from each breached cone, out of its breach, shorter and duller with age
  lava_rubble      the flows' clinker (blocks and pressure ridges 1-8 m) on the levels with cells of 4 m or finer
  cone_rills       the cones' rills, up to 1.5 m deep and about 30 m apart, from just under the rim to the toe,
                   fainter on the older cones, on the levels finer than the main one
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

# the flows' shape (volcanic.lava_surface with front_deg): an aa flow's rubble margins and front standing at 35
# degrees, broad levees, a ridged rubbly top, compound lobes (units: later units breaking out of the first one's
# sides and front, turned aside by it), each walker stopping at its own length and spreading as it slows; DOWNFLOW's
# perturbation a few metres (dh_factor 0.25 of the thickness: at 3 x the thickness every walker random-walked, and
# each flow came out a round pancake about its vent). The footprint follows the walkers' corridor where 2 % of them
# passed (at 6 % the corridor broke where the walkers fanned out on the 10 m cells: SP's flow ended 1 km out and its
# far half lay detached, a lobe connected to no vent; at 1 % with a band of one width, the outline was the walkers'
# spread, a fan with straight sides), each flow leaving its vent in a channel (channel: 35 % of its width, opening
# over the first 40 % of its length) and parting round the ground that rises over its paths' level (no_climb
# 'local': the cone it left, and the cones in its way stand as islands, not buried). The top's ridges and clinker at
# the main level 0.17 of the thickness (0.22 crumpled the 10 m hillshade like foil; at 0.12 the field's slope p90 fell
# to 14.2 degrees, under the judge's band from SP's 18.3); the clinker the eye sees is added on the finer levels
# (lava_rubble)
FLOW_SHAPE = dict(front_deg=35.0, levee=0.3, levee_frac=0.1, rough=0.17, stop_spread=0.3, front_spread=1.0,
                  vent_taper=0.0, no_climb='local', units=3, p_edge=0.02, channel=dict(frac=0.35, until=0.4))

# the plateau's older flows, each from the foot of one of the field's cones (60 % of them), down the plateau's slope
# +- 70 degrees (scattered from points with no vent, they were lobes connected to nothing): mantled, so no levees
# (with them, a 6-14 m flow dulled by age read in the hillshade as a flat plate traced by a thin raised line), their
# fronts 8-18 m high at 30 degrees, widened with age, their tops still hummocky (rough 0.25 of the thickness, dulled
# by at most a half)
OLD_FLOWS = dict(FLOW_SHAPE, feet=dict(cones=[], field=None, kappa_m2_per_yr=None, fraction=0.6,
                                       downhill_azimuth_deg=25.0, spread_deg=70.0, length_m=[2500.0, 7000.0],
                                       thickness_m=[8.0, 18.0], age=[0.3, 0.7], width_m=[250.0, 700.0]),
                 dh_factor=0.25, walkers=200, rough=0.25, levee=0.0, front_deg=30.0)

# SP Crater as measured (volcanic.SP_CRATER), its flanks a little under the 32-degree preset: the reference's flank
# p90 at 10 m is 27.5 degrees (median 29-31 on the cone itself, the crest and toe rounded)
#   fitted with the judge's own cone reader on a 10 m grid (the reference reads SP at H 246 m, W 1420 m, H/W 0.173,
#   flank p90 27.5): W 1420, H/W 0.188, crater 0.26 W, flanks 28 degrees, a level rim (a 5 % rim tilt smears the
#   radial mean's peak and reads 25 m lower) read 0.18 and 29.7. Its crest rounded over 6 m and no creep: SP Crater
#   is young (71 kyr) and from the plateau its rim is a sharp shoulder over straight flanks; with a 20 m crest and
#   kappa t 40 m2 (evaluated on a 3.8 m patch) the cone read as a soft rounded hill at 1.7 m
HERO = dict(at=[0.0, 0.0], width_m=1420.0, hw_ratio=0.188, crater_ratio=0.26, flank_deg=28.0,
            crater_wall_deg=_S['crater_wall_deg'], crater_depth_frac=_S['crater_depth_frac'], crest_round_m=6.0,
            rim_tilt=0.02, tilt_azimuth_deg=_S['tilt_azimuth_deg'], outline_noise=0.02, seed=_S['seed'],
            age_yr=71000.0, kappa_t_m2=0.0)

# the field's cones are not gumdrops: fissure-fed ones elongated along their vent line, coalescing pairs, breached
# horseshoes with their flows (the reference's older cones round SP Crater)
# (breached toward the plateau's downhill side, compass 25 +- 50 degrees)
FIELD = dict(window=[-5000.0, -5000.0, 10000.0], count=17, width_m=[330.0, 1400.0], hw_ratio=0.18,
             crater_ratio=[0.25, 0.42], flank_deg=[26.5, 29.5], vent_lines=3, line_spread_m=1400.0,
             age_yr=[150000.0, 900000.0], breach_fraction=0.4, outline_noise=0.05, elongation=[1.0, 1.35],
             overlap=0.35, breach_toward_deg=25.0, breach_spread_deg=50.0)

KAPPA = 0.002            # m2/yr, scoria creep: a 500 kyr cone smoothed by kappa t = 1000 m2 (sigma 45 m)

# (the toe: each pile joined to the plateau over 8 % of its height, a distinct break at the foot; at 20 % the
# fillet spread over 100 m and the cones read as rounded hills from the plateau)
CONES = dict(cones=[dict(HERO)], field=dict(FIELD), kappa_m2_per_yr=KAPPA, supersample=1, toe_frac=0.08)

OLD_FLOWS['feet'].update(field=dict(FIELD), kappa_m2_per_yr=KAPPA)

# SP Crater's flow: a thick, dark, rough tongue leaving its north foot (at the cone's base, full thickness) and
# running 7 km down the plateau, 20-30 m thick, 1-2 km wide in lobes (five units); leaving the cone in a channel
# 300-400 m wide and opening out over its first 3 km (FLOW_SHAPE's channel; vent_taper, a thinning at the vent, left
# it a skirt along the cone's toe); its walkers' perturbation 1 m, so they keep one corridor down the plateau; the
# breached cones' flows from their breaches, three units each, shorter and duller with age
LAVA = dict(FLOW_SHAPE, vents=[dict(at=[0.0, 0.5 * HERO['width_m'] + 20.0], length_m=8500.0, thickness_m=22.0,
                                    age=0.05, dh_m=1.0, width_m=900.0, walkers=800, units=5, vent_taper=0.0)],
            breaches=dict(cones=[dict(HERO)], field=dict(FIELD), kappa_m2_per_yr=KAPPA, length_m=3000.0,
                          thickness_m=10.0, age_span_yr=900000.0, width_m=400.0),
            dh_factor=0.25, walkers=500, vent_taper=0.35)

LAKES = dict(mode='sediment', dry_cones=dict(cones=[dict(HERO)], field=dict(FIELD), kappa_m2_per_yr=KAPPA))

# the cones' rills: up to 1.5 m deep, about 30 m apart at mid-flank, each about half that wide, fainter on the older
# cones (volcanic.cone_rills; 25 m apart and narrow, the talus pass at repose relaxed them away on the hero levels)
RILLS = dict(cones=[dict(HERO)], field=dict(FIELD), kappa_m2_per_yr=KAPPA, depth_m=1.5, spacing_m=30.0)


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
    v0 = LAVA['vents'][0]
    lava['vents'] = ([dict(v0, at=[c[0] + v0['at'][0], c[1] + v0['at'][1]])]
                     if p['hero_cone'] and p['hero_flow'] else [])
    lava['breaches'] = dict(LAVA['breaches'], cones=cones, field=field, kappa_m2_per_yr=kappa)
    p.stage('old_flows')['feet'] = dict(OLD_FLOWS['feet'], field=field, kappa_m2_per_yr=kappa)
    p.stage('volcano_lakes')['dry_cones'] = dict(cones=cones, field=field, kappa_m2_per_yr=kappa)
    p.stage('cone_rills').update(cones=cones, field=field, kappa_m2_per_yr=kappa)
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
        # the flows' clinker on the levels fine enough to hold it (blocks and pressure ridges 1-8 m: at 1.7 m the
        # main level's flow was a smooth tongue)
        Stage('lava_rubble', {'scales_m': [8.0, 3.0, 1.2], 'amps_m': [1.2, 0.6, 0.3]}, levels='cell<=4'),
        # the cones' rills, from just under the rim to the toe, on the levels finer than the main one (SP Crater's
        # flanks are rilled from rim to toe; at 1.7 m smooth flanks read as clay)
        Stage('cone_rills', dict(RILLS), levels='cell<=5'),
        Stage('talus', {'repose_deg': 33.0, 'iterations': 48}, levels='hero'),
        # (not on the hero levels: there it only filled small pits with sediment, a CPU fill of a million cells per
        # level; the field holds no water, and each hero level inherits its parent's filled ground)
        Stage('volcano_lakes', dict(LAKES), levels=['context', 'main']),
    ],
    doc='The lava plateau with its older flows -> the hero cone and the field, each aged by creep for its age -> the '
        "hero cone's flow and the breached cones' flows -> talus on the hero levels; the craters stay dry.")

RECIPES = [CINDER_CONES]
