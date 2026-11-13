"""impact_crater: a simple bowl crater in flat-lying layered rock: a square-ish rim, cliff-banded upper walls over a
long concave debris apron strewn with fallen blocks, near-level lake beds at the centre, a hummocky ejecta blanket,
aged by chutes and creep (design 4.8 and section 5), judged against Meteor Crater.

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
  impact_crater    the crater (impact.py): Pike's bowl at depth 0.2 D, the rim 0.044 D above the plain, a 4-sided
                   rounded planform from the joint sets, rim height varying with azimuth, the ejecta blanket (r/R)^-3
                   to 2.3 R with hummocks and blocks; inside, the infill is a concave debris apron rising from the
                   floor's centre 0.143 D under the rim (talus at 35 degrees under the face, fans further out, low
                   mounds on the near-level centre) to the face of the target's beds (Kaibab and Moenkopi ledges and
                   cliffs over weaker beds) in its upper quarter; stamped on the first level, sharpened on every finer
                   one; its talus and fill recorded as talus and deposit
  volcano_age      the crater's age: stream power and creep with the walls' own strength (chutes of many sizes cut
                   into the face and the apron's top, their debris in fans, the rim crest rounded), the crater a
                   closed basin (no pit filling)
  talus            (solvers/hillslope.py) the debris at repose on the hero levels
  crater_blocks    (impact.py) blocks fallen from the face, 0.7-9 m, over the apron's upper part and at its foot
  volcano_lakes    the crater floor stays dry (lake beds over its centre); the solvers' small pits fill with sediment
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

# Meteor Crater's walls: the Moenkopi and Kaibab beds stand as ledges and cliffs in the upper wall, over a long
# concave debris apron that reaches the floor's centre (the reference: inner wall slopes p99 59 degrees at 3 m; ring
# medians from the floor's centre: 2 m up at 120 m out, 6 m at 216 m, 17 m at 310 m, 50 m at 410 m, 105-125 m at
# 500 m where the apron meets the face, the crest 165-170 m up at 550-600 m): the apron's top at 0.8 of the floor-
# to-crest height, the talus under the face at 39 degrees (fitted to those medians at 37, 2.6 m rms; steeper here so
# the aging's fans on the lower apron land it on them), the face above it at
# 50 degrees mean in beds 10-30 m thick (several ledges, pinching and swelling round the ring), the apron's top
# rising and falling 7 % round the ring (debris cones under the chutes), low mounds of 0.5 m on the floor (its
# median slope 0.5-3 degrees)
CLIFFS = dict(strong_deg=75.0, strong_frac=0.45, layer_m=[10.0, 30.0], sectors=9, talus_frac=0.8, talus_deg=39.0,
              face_deg=50.0, apron_vary=0.07, mounds_m=0.5)

# the joint sets' square planform, at 0.15 of a full polygon: Meteor Crater's outline is square to 5 % of its radius
# in the 4-fold harmonic; at 0.35, with the walls smoothly following it, the crater's slopes faced the four side
# normals strongly enough to read as a grid-direction bias to the judge (4-fold aspect 0.20, the reference's 0.12),
# at 0.27 the stamp alone read 0.17 and the aged crater 0.21, and at 0.22 the face's ring alone carried 0.29 of it
# (0.18 in all, the band ending at 0.178)
POLYGON = 0.15

CRATER = dict(centre=[0.0, 0.0], diameter_m=_D0, depth_ratio=_M['depth_ratio'], rim_ratio=_M['rim_ratio'],
              fill_ratio=_M['fill_ratio'], sides=_M['sides'], polygon=POLYGON,
              polygon_azimuth_deg=_M['polygon_azimuth_deg'], radius_noise=0.045, edge_noise=0.015,
              rim_noise=_M['rim_noise'], crest_round=0.5, ejecta_reach=_M['ejecta_reach'],
              rays=0.0, cliffs=dict(CLIFFS), supersample=2)

# the walls' chutes: Meteor Crater's upper wall is cut into radial gullies 20-40 m apart, a few of them large, their
# debris in fans on the apron below; without them the strong beds read as rings running round the wall
#   the run cuts the face and the apron's upper part (full K from 0.4 D out to the rim) and barely touches the lower
#   apron and the floor (fans and lake beds: cut at full K they were a comb of V gullies down to a sharp line at the
#   floor), the blanket or the plain beyond (the reference's plain is smooth: slope p50 1 degree outside 2.5 R); the
#   erodibility varies round the ring (sector_contrast, harmonics 4-40: some walls deeply chuted, others smooth
#   between their gullies); the gullies 32 m apart and shallow (K 1.2e-5: at 2.5e-5 and 30 m
#   they were a comb of equal V's, at 45 m a row of large rounded V chutes with sharp ridges, a dissected badland
#   wall, where Meteor Crater's walls are a cliff band over smooth debris slopes with fine gullies); in fractions of
#   D, _apply scales them. Deposition 0.4: most of the walls' debris travels on to the centre and levels the lake
#   beds (at 1.0 it built fans 3-7 m high on the lower apron, 9.5 degrees at the median 200-300 m out, the
#   reference's 4-8, and the floor's bottom tenth read as a bowl to the judge)
#   The chutes are seeded by furrows running down the wall (volcanic.radial_streaks, harmonics 50-220 falling off at
#   0.7: at 550 m out 16-70 m apart, a few broad ones that gather the most debris and many fine ones), 1.5 m deep,
#   over a weak round texture of 0.4 m at 25 m: seeded by that texture alone at 1 m, the chutes of a sector were one
#   size and evenly spaced, a comb of equal V's round the east wall. With the furrows sizing the chutes, the sectors
#   vary less (sector_contrast 0.8: at 1.1 one sector's K reached 8 x the mean, and its chute cut the south-west wall
#   in a V that dominated the view from the north rim)
#   The furrows sparse and wandering a little (radial_streaks' sparse and wander_m: only the noise's troughs below
#   -0.5 sigma, bending 5 m as they run down the steep wall, ending at the crest; at 14 m they wriggled like worms,
#   and run on to 0.58 D they streaked the rim's outer flank; harmonics 30-160: some 70 chutes round the wall, 45 m
#   apart at the face, a few broad),
#   the erodibility gathered into them (k_floor: the debris slopes between them erode at a quarter), the lower apron
#   and the floor at 3 % of K and the outer flank of the rim at 20 % falling to 5 %: seeded by straight furrows alike
#   all round, with K alike between them, the run cut a sunburst of straight spokes from the rim to within 100 m of the
#   centre and combed the rim's outer flank (the reference's floor is smooth lake beds, its outer flank hummocky)
#   Two sizes of chute: the large ones above and a fine set between them (harmonics 160-420: 8-21 m apart at the
#   face, under a metre deep at first), as the reference's walls carry fine gullies between the large ones (with the
#   large ones alone the walls between them were smooth panels following the square planform: their slopes faced
#   the four side normals, a 4-fold aspect signal of 0.21 to the judge against the reference's 0.12)
#   (the chutes from 0.36 D up, the run's full K from 0.42 D: from 0.3 D the chutes ran on down the lower apron as
#   radial ribs, a sunburst round the floor; the rim's outer flank at 0.3 of K by 0.6 D, its own small gullies seeded
#   by the round texture: at 0.2 it lay smooth and the square walls ruled the judge's aspect histogram, 4-fold 0.20)
K_PROFILE = [[0.0, 0.03], [0.33, 0.03], [0.42, 1.0], [0.5, 1.0], [0.6, 0.3], [1.0, 0.05]]
# r_m, wander_m and wander_scale_m in fractions of D (_streaks scales them)
STREAKS = [dict(amp_m=2.5, k=[30, 160], decay=0.5, r_m=[0.36, 0.5], bands=2, wander_m=0.004, wander_scale_m=0.15,
                sparse=0.5, k_floor=0.25),
           dict(amp_m=1.0, k=[160, 420], decay=0.5, r_m=[0.38, 0.5], bands=2, wander_m=0.002, wander_scale_m=0.05,
                sparse=0.0, k_floor=0.25)]


def _streaks(D):
    return [dict(s, r_m=[f * D for f in s['r_m']], wander_m=s['wander_m'] * D, wander_scale_m=s['wander_scale_m'] * D)
            for s in STREAKS]


AGE = dict(age_yr=5.0e4, K=1.2e-5, threshold_deg=38.0, threshold_noise=0.15, deposition=0.4, roughness=0.9,
           roughness_scales_m=[120.0, 40.0, 12.0], valley_spacing_m=32.0, fill_pits=False,
           strength_from_field=True, seed_texture_m=0.4, seed_texture_scale_m=25.0, centre=[0.0, 0.0],
           seed_streaks=_streaks(_D0), sector_contrast=0.8, sector_harmonics=[4, 40],
           k_profile=[[f * _D0, k] for f, k in K_PROFILE])

# the floor: the apron's lowest part, its near-level centre the lake beds (the reference: slopes 0.5-2.5 degrees
# within 150 m of the centre), not filled flat (flattened over 30 % it was a dead-flat disc meeting the walls in a
# sharp line; a playa of 4 % still flattened the centre 3.5 m deep and lifted the floor's bottom tenth onto the
# apron, past the judge's flat-floor read); the solvers' small pits on the floor fill with sediment
LAKES = dict(dry=[dict(at=[0.0, 0.0], radius_m=0.5 * _D0)], mode='sediment')

# fallen blocks on the hero levels: rockfall from the face resting over the apron's upper part and at its foot,
# fewer out onto the floor (Meteor Crater's walls shed boulder slopes; blocks of Kaibab and Coconino 1-10 m): large
# ones 2.5-9 m on a 24 m lattice, small ones 0.7-2.5 m on an 8 m lattice; rho over the crater's broad outline. And
# on the floor's lake beds, low hummocks of sediment held round its shrubs, 2.5-7 m across and 0.1-0.7 m high on a 7 m
# lattice (the review's walk on the floor saw a dead-flat featureless disc; Meteor Crater's floor is hummocky with
# brush)
BLOCKS = dict(sets=[dict(spacing_m=24.0, size_m=[2.5, 9.0], density=0.45, rho=[0.6, 0.8, 0.95, 1.02],
                         height_frac=[0.35, 0.6]),
                    dict(spacing_m=8.0, size_m=[0.7, 2.5], density=0.3, rho=[0.5, 0.72, 0.97, 1.03],
                         height_frac=[0.3, 0.55]),
                    dict(spacing_m=7.0, size_m=[2.5, 7.0], density=0.8, rho=[0.0, 0.02, 0.55, 0.7],
                         height_frac=[0.05, 0.1], profile='mound')])


def _apply(p):
    c = [float(v) for v in p['centre']]
    D = float(p['diameter_m'])
    cr = p.stage('impact_crater')
    cr.update(centre=c, diameter_m=D, rim_ratio=float(p['rim_ratio']), fill_ratio=float(p['depth_ratio']),
              sides=int(p['sides']), polygon=POLYGON if int(p['sides']) >= 3 else 0.0)
    cr['cliffs'] = dict(CLIFFS, strong_frac=float(p['cliff_fraction'])) if float(p['cliff_fraction']) > 0 else None
    p.stage('volcano_age').update(age_yr=float(p['age_kyr']) * 1000.0, centre=c,
                                  k_profile=[[f * D, k] for f, k in K_PROFILE], seed_streaks=_streaks(D))
    p.stage('volcano_lakes')['dry'] = [dict(LAKES['dry'][0], at=c, radius_m=0.5 * D)]
    p.stage('crater_blocks')['crater'] = {k: cr[k] for k in ('centre', 'diameter_m', 'sides', 'polygon',
                                                             'polygon_azimuth_deg', 'radius_noise')}
    p.stage('crater_blocks')['enabled'] = bool(cr['cliffs'])
    for st in p.stages('volcano_setting'):
        st['centre'] = c


IMPACT_CRATER = Recipe(
    'impact_crater', 'A simple impact crater: a square-ish rim, cliff-banded walls over a concave debris apron with '
                     'fallen blocks, near-level lake beds at the centre and a hummocky ejecta blanket in flat-lying '
                     'rock',
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
        Stage('crater_blocks', dict(BLOCKS, crater={k: CRATER[k] for k in ('centre', 'diameter_m', 'sides', 'polygon',
                                                                          'polygon_azimuth_deg', 'radius_noise')}),
              levels='cell<=1.5'),
        # (not on the hero levels: there it only filled the pits behind fallen blocks with sediment, a CPU fill of a
        # million cells per level; the crater holds no water, and each hero level inherits its parent's filled floor)
        Stage('volcano_lakes', dict(LAKES), levels=['context', 'main']),
    ],
    doc='The plateau with its washes -> the crater stamped (bowl, a concave debris apron from the floor to the '
        "cliff-banded face, rim, ejecta) -> the crater's age (wall chutes of many sizes, fans, a rounded rim) -> "
        'talus and fallen blocks on the hero levels; the floor stays dry.')

RECIPES = [IMPACT_CRATER]
