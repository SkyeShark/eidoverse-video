"""caldera: an eroded stratovolcano whose summit collapsed into a caldera with cliff-banded walls over talus, a lake
standing at its own level, and a cinder cone on a lava platform inside (design 4.7 and section 5), judged against
Crater Lake.

    t = make_terrain('caldera', seed=5)                                         # Crater Lake-like, 14 km
    t = make_terrain('caldera', params={'lake_below_rim_m': 700, 'island': False})    # a deep, nearly dry one

Stages, in order (solvers/volcanic.py unless named):
  stratovolcano    the edifice (Mount Mazama's remnant as measured: H 1639 m, lambda 5474 m, R 25 km) with parasitic
                   cones on its outer flanks and a cluster of overlapping cones round its summit, which the collapse
                   cuts into the rim's peaks; every level
  volcano_setting  (named ground) the regional slope the edifice stands on, falling north-east, with low swells
  volcano_age      the edifice eroded for its age before the collapse (400 kyr: a few deep valleys radiating from the
                   summit region between broad smooth pumice ridges, fading out on the lower flanks), time-faithful on
                   the 56 km context level, refined under the lock on the finer ones, so the valleys run on across the
                   main tile's edge (the summit, which the collapse takes, barely cut, so no canyon breaches the rim)
  lava_flows       (named flank_flows) thick old flows on the edifice's flanks (Llao Rock, Cleetwood): lobes with
                   steep fronts and blocky tops, cut in section by the walls
  caldera_collapse the ring-fault collapse: the outline a rounded pentagon with three embayments on the 8 x 10 km
                   oval of Crater Lake (straight stretches between broad corners and a few bights, not a ring of
                   scallops), walls of lava flows and welded tuff standing as cliffs over weaker beds (a
                   50-degree mean face down to a talus apron at 33 degrees over the lowest third of the wall, its top
                   rising and falling round the ring), the floor 980 m under the rim, the inner cone on its lava
                   platform
  threshold        (solvers/hillslope.py) the walls at the strength they were built with: what aging steepened fails
  talus            (solvers/hillslope.py) the debris at repose on the loose apron
  volcano_age      (named wall_age) the walls gullied since the collapse (7.7 kyr at Crater Lake): chutes, and fans at
                   their feet; the caldera is a closed basin (no pit filling)
  talus            (named ravel) the chutes cut into the loose apron refilled to repose: debris cones at their mouths
  caldera_lake     the lake at its own level (389 m under the mean rim at Crater Lake, not at the lowest notch); every
                   other closed depression filled with sediment. The runner's end-stage lakes are off (lakes False)
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import volcanic as V

_P = V.CRATER_LAKE
_C0 = _P['centre']
_E = dict(_P['edifice'])

# Mount Scott: an older composite cone on Mazama's east flank, its summit (2721 m) 7.5 km east and 1.5 km south of
# the caldera's centre, just outside the 14 km tile, whose west flank (to 2575 m) is the reference's highest ground;
# old, so rounded by creep (kappa t 2e4 m2: sigma 200 m)
SCOTT = dict(at=[7500.0 - _C0[0], -1500.0 - _C0[1]], width_m=4200.0, hw_ratio=0.17, crater_ratio=0.05, flank_deg=30.0,
             crater_depth_frac=0.02, outline_noise=0.08, seed=17, kappa_t_m2=5.0e3)

# Mazama was a cluster of overlapping composite cones and domes (Hillman, Garfield, Applegate, Dutton, Cloudcap,
# Llao's flow): the collapse cut them in section, and they stand as the rim's peaks between notches. The rim crest
# round the real caldera: p10..p90 -149..+186 m about its median, its harmonics 5-15 (peaks 2-6 km apart) 25-48 m;
# without them the generated crest was a tilted ring (harmonics 5-15 at 8-31 m) and the far walls in the photo
# views a flat band
# (two crossing alignments, so the cones stand all round the summit, not in two opposite sectors; 4-5.8 km out, so
# most straddle the rim at 4.7 km and the wall cuts them)
CLUSTER = dict(azimuth_deg=60.0, count=5, distance_m=[4000.0, 5800.0], spread_m=3500.0, width_median_m=1900.0,
               width_m=[1200.0, 2800.0], hw_ratio=[0.09, 0.14], crater_ratio=[0.03, 0.08],
               crater_depth_frac=[0.0, 0.03], flank_deg=[20.0, 26.0], breach_fraction=0.0, outline_noise=0.12)
CLUSTER_CROSS = dict(CLUSTER, azimuth_deg=150.0)

EDIFICE = dict(centre=[0.0, 0.0], height_m=_E['height_m'], radius_m=_E['radius_m'],
               upper_slope_deg=_E['upper_slope_deg'], crater_radius_m=_E['crater_radius_m'],
               height_noise=_E['height_noise'], radius_noise=_E['radius_noise'], rift_azimuth_deg=330.0,
               rift=[dict(_P['flank_cones']), dict(CLUSTER), dict(CLUSTER_CROSS)], cones=[dict(SCOTT)])

# Mazama's flanks before the collapse: a few deep radial valleys (Annie Creek and Sun Notch cut 150-250 m: the
# reference's 914 m of relief is rim to canyon floor) between broad smooth pumice-mantled ridges, not a skin of
# gullies (gullied everywhere, the radial valleys of a cone in a square tile all face the diagonals in its corners:
# a 4- and 8-fold aspect bias of 0.2 / 0.08): the erodibility gathered into sectors (sector_contrast), the valleys
# 1.1 km apart from a seed texture at 500 m (700 m and 150 m combed the flanks into dense parallel streaks), cut
# from the rim's foot out to 11 km and fading into the smooth ignimbrite and pumice apron beyond (k_profile, metres
# from the centre: the summit and the ring the collapse takes barely cut, the valleys at full strength from 7 km;
# full from 5.5 km, one cut back through the rim below the lake's level and the lake ran out over the flank). Run
# from the 56 km context level down (the valleys then run on across the main tile's edge and the edifice continues
# to the horizon; aged on the main tile alone it stood as a square plate of valleys on a smooth cone). K 2.2e-6 and
# 0.75 of it 7-11 km out: there the valleys gather whole flanks, and at the main tile's 1e-5 they cut 1175 m of
# relief and an 11-degree slope median into Crater Lake's gentle pumice slopes (the reference: 914 m, 5.5 degrees;
# at 3.5e-6, 1065 m and 8.9). Beyond the main tile the valleys run on down the outer edifice at half strength and
# more (0.55 at 16 km, 0.35 at 25 km: at 0.3 and 0.1 the context ring 7-28 km out lay at a slope median of 1.8
# degrees, the reference's surroundings 4.5, a flat plain from the airliner)
AGE = dict(age_yr=4.0e5, K=2.2e-6, threshold_deg=36.0, threshold_noise=0.2, deposition=1.0, roughness=0.6,
           roughness_scales_m=[3000.0, 900.0, 300.0], valley_spacing_m=1100.0, centre=[0.0, 0.0],
           seed_texture_m=4.0, seed_texture_scale_m=500.0, sector_contrast=0.8, sector_harmonics=[4, 16],
           k_profile=[[0.0, 0.05], [4000.0, 0.08], [5500.0, 0.35], [7000.0, 0.75], [11000.0, 0.75],
                      [16000.0, 0.55], [25000.0, 0.35], [40000.0, 0.25]])

# the ground the edifice stands on: the Cascades' slope falls toward the Klamath basin, north-east (the reference's
# north-east corner is 220 m under the lake, its south-west corner 50 m above it), with swells of 70 m at 9 km beyond
# 14 km out, 40 m under the main tile (from an airliner the land beyond the edifice runs to the horizon; a plane
# there ended in a straight edge, and at 40 m all round the far ground read as a flat plain)
GROUND = dict(centre=[0.0, 0.0], basin_m=1.0e9, ramp_m=1.0, cover=1.0, texture=0.0, plain=0.0, U_m_per_yr=0.0,
              start_m=0.0, plain_m=1.0, plain_slope=0.02, plain_slope_up=0.008, plain_down_azimuth_deg=45.0,
              plain_extent_m=30000.0, plain_rough_m=70.0, plain_rough_scale_m=9000.0,
              plain_rough_inner=dict(factor=0.57, r0_m=8000.0, r1_m=14000.0))

# Mazama's flank flows (Llao Rock, Cleetwood, Grouse Hill: dacite and andesite 30-300 m thick): lobes with steep
# fronts in every orientation on the outer flanks, made before the collapse so its walls cut them in section; 20 of
# them with blocky tops (rough 0.28 of the thickness: ridges 7-17 m high at 75-180 m) - the flanks' relief at 30-800 m
# is lava lobes and their rubble, where the aged edifice alone is smooth pumice slopes (its spectrum fell off at
# -4.67 against Crater Lake's -4.17, the judge's band edge, with 14 flows dulled to 0.06). Their outline the walkers'
# corridor where 3 % of them passed (at the default 1 % a flow's outline was the walkers' whole spread: a fan with
# straight sides, a flat plate jutting from the rim in the airliner's view), each parting round the ground that rises
# over its paths' level (no_climb 'local'); their blocky tops 0.28 of the thickness (at 0.15, with the tighter
# outlines, the spectrum fell to -4.671, past the band's edge). Stubby, as thick dacite flows are (Cleetwood, Llao
# Rock: 1-3 km long, about as wide), in three lobed units: 1.5-4.5 km long and 0.5-1.3 km wide in two units, those
# whose vents the collapse took survived as straight-sided strips running out from the rim
FLANK_FLOWS = dict(scatter=dict(window=[-6000.0, -6000.0, 12000.0], count=20, length_m=[1000.0, 3000.0],
                                thickness_m=[25.0, 60.0], age=[0.3, 0.8], width_m=[700.0, 1600.0]),
                   dh_factor=0.25, walkers=200, rough=0.28, front_deg=35.0, levee=0.2, levee_frac=0.12,
                   stop_spread=0.3, front_spread=1.0, no_climb='local', units=3, p_edge=0.03)

# the walls: lava flows and welded tuff as cliff bands over tephra (the reference's walls above the water: p50 35,
# p90 51, p99 59 degrees at 14 m; ledges at 72 read as 79-degree texel steps)
COLLAPSE = dict(centre=[0.0, 0.0], rim_radius_m=_P['rim_radius_m'], floor_below_rim_m=980.0,
                # the walls run steeply into the lake: the rock face down to a talus apron over the lowest 32 % of
                # the wall (under the water), its top rising and falling 40 % round the ring (at 55 % of the wall at
                # one height, the dry walls stepped down to a continuous bench ring: a donut)
                wall_deg=50.0, talus_deg=_P['talus_deg'], talus_frac=0.32, talus_vary=0.4,
                # the outline: Crater Lake's rim is a rounded polygon (straight stretches between broad corners) with
                # a few bights, so a rounded pentagon blended in at a half (its straight walls face five ways: no
                # 4-fold grid signal to the judge), three smooth embayments 4-9 % deep and 18-38 degrees across,
                # broad outline noise at 5 %, and the points and coves along the rim (edge_noise, harmonics 10-48
                # falling off at 1.6: broad points, not a gear of sharp spurs) at 2 %. (Nine scallops of one size
                # read as a pie-crust edge; six of very different sizes still met in an inward cusp at every
                # junction, and from the air the rim read as a lobed cloud.)
                scallops=0, polygon=dict(sides=5, strength=0.5, azimuth_deg=15.0, roundness=0.1),
                embayments=dict(count=3, amp=[0.04, 0.09], width_deg=[18.0, 38.0]), radius_noise=0.05,
                edge_noise=0.02, edge_decay=1.6, elongation=_P['elongation'],
                elongation_azimuth_deg=_P['elongation_azimuth_deg'],
                cliffs=dict(strong_deg=70.0, strong_frac=0.4, layer_m=[30.0, 120.0], sectors=7),
                # Wizard Island 13 % nearer the centre than measured: these walls run wider under the water than
                # the real ones, and at the measured place its platform touched the west wall at the waterline
                # (the real one has 460 m of water between)
                inner_cones=[dict(c, at=[0.87 * (c['at'][0] - _C0[0]), 0.87 * (c['at'][1] - _C0[1])])
                             for c in _P['inner_cones']])

# the walls gullied since the collapse: chutes and fans on the walls only (k_profile; _apply scales it with the rim
# radius) - over the whole tile its seed texture and stream power crinkled the outer flanks into grid-biased rills
WALL_K = [[0.0, 1.0], [1.04, 1.0], [1.15, 0.0]]
# (K 3e-5: the walls' fractured lava and tuff; at 1e-5 the chutes were 20 m deep and the walls read as smooth
# panels from across the lake, where the real ones are spurs and gullies)
WALL_AGE = dict(age_yr=7700.0, K=3.0e-5, threshold_deg=40.0, threshold_noise=0.1, deposition=1.0, roughness=0.8,
                roughness_scales_m=[400.0, 120.0, 40.0], valley_spacing_m=120.0, fill_pits=False,
                strength_from_field=True, steps=400, seed_texture_m=1.5, seed_texture_scale_m=60.0,
                centre=[0.0, 0.0], k_profile=[[f * _P['rim_radius_m'], k] for f, k in WALL_K])


def _apply(p):
    c = [float(v) for v in p['centre']]
    e = p.stage('stratovolcano')
    e.update(centre=c, height_m=float(p['edifice_height_m']), radius_m=float(p['edifice_radius_m']),
             cones=[dict(SCOTT, at=[c[0] + SCOTT['at'][0], c[1] + SCOTT['at'][1]])] if p['flank_volcano'] else [])
    col = p.stage('caldera_collapse')
    k = float(p['rim_radius_m']) / float(_P['rim_radius_m'])
    p.stage('volcano_age').update(age_yr=float(p['age_kyr']) * 1000.0, centre=c,
                                  k_profile=[[r * k, f] for r, f in AGE['k_profile']])
    p.stage('ground').update(centre=c, plain_rough_inner=dict(GROUND['plain_rough_inner'],
                                                              r0_m=GROUND['plain_rough_inner']['r0_m'] * k,
                                                              r1_m=GROUND['plain_rough_inner']['r1_m'] * k))
    col.update(centre=c, rim_radius_m=float(p['rim_radius_m']), floor_below_rim_m=float(p['floor_below_rim_m']))
    col['cliffs'] = dict(COLLAPSE['cliffs'], strong_frac=float(p['cliff_fraction']))
    col['inner_cones'] = ([dict(cn, at=[cn['at'][0] * k, cn['at'][1] * k], width_m=cn['width_m'] * min(k, 1.0))
                           for cn in COLLAPSE['inner_cones']] if p['island'] else [])
    if col['inner_cones'] and float(p['lake_below_rim_m']) < float(p['floor_below_rim_m']):
        # the lava platform's flat top 4.5 m above the water, as Wizard Island's (at the preset's height ratio it
        # stood 6 m under the lake: a pale submerged shelf round the cone)
        plat = col['inner_cones'][0]
        top = float(p['floor_below_rim_m']) - float(p['lake_below_rim_m']) + 4.5
        plat['hw_ratio'] = top / float(plat['width_m'])
    p.stage('wall_age').update(centre=c, k_profile=[[f * float(p['rim_radius_m']), kk] for f, kk in WALL_K])
    p.stage('caldera_lake').update(centre=c, below_rim_m=float(p['lake_below_rim_m']),
                                   enabled=float(p['lake_below_rim_m']) < float(p['floor_below_rim_m']))


CALDERA = Recipe(
    'caldera', 'A collapse caldera: an eroded edifice, embayed cliff-banded walls over talus, a lake at its own '
               'level, an inner cone',
    references=['crater_lake'],
    # context 16: four context levels to 224 km, so from an airliner 28 km out and 10 km up the land runs on past
    # the frame's top (at 2 the 28 km context's square edge was the horizon)
    defaults={'size': 14000.0, 'context': 16, 'hero_cell': 0.5, 'palette': 'volcanic', 'base_elevation_m': 1500.0,
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
        'flank_volcano': Knob(True, 'bool', None, 'an older composite cone on the east flank (Mount Scott)'),
        'centre': Knob([0.0, 0.0], 'list', None, "the caldera's centre, world metres", apply=_apply),
    },
    stages=[
        Stage('volcano_setting', dict(GROUND), levels='all', name='ground'),
        Stage('stratovolcano', dict(EDIFICE), levels='all'),
        Stage('volcano_age', dict(AGE), levels='cell<=60'),
        Stage('lava_flows', dict(FLANK_FLOWS), levels='main', name='flank_flows'),
        Stage('caldera_collapse', dict(COLLAPSE), levels=['main', 'hero']),
        Stage('threshold', {'iterations': 64}, levels=['main', 'hero']),
        Stage('talus', {'repose_deg': 33.0, 'iterations': 64}, levels=['main', 'hero']),
        Stage('volcano_age', dict(WALL_AGE), levels=['main', 'hero'], name='wall_age'),
        # dry ravel: the chutes cut into the loose apron refill to repose, debris cones at their mouths (without it
        # the two largest chutes stood as dark notches 200 m tall at the waterline in the views across the lake)
        Stage('talus', {'repose_deg': 33.0, 'iterations': 64}, levels=['main', 'hero'], name='ravel'),
        Stage('caldera_lake', {'centre': [0.0, 0.0], 'below_rim_m': 389.0}, levels=['main', 'hero']),
    ],
    doc='The edifice -> eroded for its age -> the ring-fault collapse with cliff-banded walls, talus and the inner '
        'cone -> the walls failing at their strength, talus at repose -> gullied since the collapse -> the lake at '
        'its own level.')

RECIPES = [CALDERA]
