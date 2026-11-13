"""stratovolcano: an exponential cone with a summit crater, radial gullies, parasitic cones on a rift, lava flows and
a debris apron, rising from a plain among river-carved ranges (design 4.7 and section 5), judged against Mount Fuji.

    t = make_terrain('stratovolcano', seed=3)                                   # Fuji-like, 40 km
    t = make_terrain('stratovolcano', params={'age_kyr': 800, 'height_m': 2200, 'radius_m': 14000})   # an old one

Stages, in order (solvers/volcanic.py unless named):
  volcano_setting  the ground the volcano grows on: a plain at the cone's foot with the reference's regional slope
                   (3 % down toward Suruga Bay, 1 % up to the Five Lakes), ranges beyond 0.7 R in patches except in
                   the open south-west sector, and the plain pinned as the ranges' base level while they grow
  fluvial          (solvers/fluvial.py) the ranges: grown to near steady state on the coarsest level, the relief
                   controller holding the surroundings at surroundings_relief_m; refined below it on the ranges only
                   (where='volcano_far': never the cone a finer level inherited, nor the apron)
  volcano_plain    the apron of lava and debris filling the low ground the vent's flows reach (not behind a range
                   crest, fading out in deep valleys: an apron front), so valleys open onto it as flat embayments;
                   its swells fade under the cone (buried by the cone's own flows and tephra)
  stratovolcano    the cone (Fuji's measured profile: H 2983 m above its foot, lambda 4215 m, R 19.9 km), its flat-
                   topped summit with a 220 m deep crater, the Hoei flank crater, 18 rift cones along the NW-SE rift as
                   piles at repose on the flank; stamped on the coarsest level after the surroundings, sharpened below
  volcano_age      the fluvial backbone run for the volcano's age with no uplift on the main level (time-faithful:
                   a few deep ravines seeded first - the Osawa-kuzure among them - and sparse wandering furrows of
                   many depths on the upper cone and the mid flanks, the erodibility gathered into them (the planes
                   between, permeable scoria and lava, at 15 %), broad lobes running down the lower flanks onto the
                   apron; strongest on the steep upper cone, sectors of different age, sediment dropped as fans and an
                   apron; the craters kept open), then refined under the lock on the hero levels
  lava_flows       DOWNFLOW flows from flank vents along the rift, on the main level: aa flows 0.4-1.5 km wide and
                   15-30 m thick, in lobed units, with steep rubble fronts, broad levees and ridged tops, narrow down
                   the steep flank and spreading where the ground levels out, filling the gullies they cross and
                   parting round the ground that rises over their paths
  lava_rubble      the flows' clinker (blocks and pressure ridges 1-8 m) on the levels with cells of 4 m or finer
  talus, breakup, hydraulic   the hero levels: scoria at repose on the loose cones, rock breakup on the steep upper
                   cone, rain rills (the detail package's ops)
  volcano_lakes    lakes where the cone and apron dam the surroundings (Fuji's Five Lakes: at most five, within 1.3 R);
                   the craters stay dry (the recipe sets defaults lakes False: the runner's end stage would fill the
                   summit crater); every other basin fills with sediment
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage
from ..solvers import volcanic as V

_F = V.FUJI
_C0 = _F['centre']
_R0 = float(_F['radius_m'])

CONE = dict(centre=[0.0, 0.0], height_m=_F['height_m'], radius_m=_R0, upper_slope_deg=_F['upper_slope_deg'],
            crater_radius_m=_F['crater_radius_m'], crater_depth_m=_F['crater_depth_m'],
            crater_floor_frac=_F['crater_floor_frac'], summit_platform_m=_F['summit_platform_m'],
            elongation=_F['elongation'], rift_azimuth_deg=_F['rift_azimuth_deg'], radius_noise=_F['radius_noise'],
            height_noise=_F['height_noise'],
            flank_craters=[dict(fc, at=[fc['at'][0] - _C0[0], fc['at'][1] - _C0[1]]) for fc in _F['flank_craters']],
            # smaller and further out than the preset's fit: seen from Asagiri (the photo view from the west) cones
            # 650-1800 m wide high on the flank read as secondary domes on the skyline, where Fuji's are bumps
            rift=dict(_F['rift'], width_median_m=420.0, width_m=[200.0, 1100.0], distance_m=[3500.0, 12000.0]))

# The ground round the cone, measured on the reference (ring medians 12-26 km out): a plain at the cone's foot,
# 850-1000 m at the Five Lakes (north, about 1 % up from the vent's 755 m) falling 3 % toward compass 200 (Suruga
# Bay) to 125-300 m round Fujinomiya; mountains north-west to west (Misaka, Tenshi: 1500-1960 m) and north-east to
# east (Doshi, Hakone's edge), none in the south and south-west, where the apron runs out to the sea. The ranges
# grow first (volcano_setting + fluvial); then the apron of lava and debris fills the lowland between them up to
# the plain (volcano_plain), so their valleys open onto it as flat embayments.
# (the ranges begin 14-18 km out, as the Misaka and Tenshi do: at 11 km the photo views from Asagiri and Lake
# Kawaguchi stood on a range's flank with the cone hidden behind it; the apron's texture, 18 m of lobes and swells,
# keeps the wider plain from reading smoother than Fuji's: with 5 m the slope median fell to 4.6 degrees, Fuji's
# 9.2, and with 12 m the plain's slope p10 was 1.1 degrees against the reference's 2.2)
#   (the apron's round swells 10 m at 1.8 km, where its relief is mostly lobes running downslope: the aging's broad
#   radial streaks; at 18 m the swells' hollows filled flat on the plain as dozens of dead-flat patches, slope p10
#   0.7 degrees against Fuji's 2.1)
SETTING = dict(centre=[0.0, 0.0], basin_m=0.7 * _R0, ramp_m=0.2 * _R0, cover=0.75, patch_m=9000.0, texture=0.35,
               U_m_per_yr=3e-3, start_m=600.0, plain_m=float(_F['base_m']), plain_slope=0.032, plain_slope_up=0.010,
               plain_down_azimuth_deg=200.0, plain_extent_m=30000.0, open_azimuth_deg=200.0, open_half_deg=55.0,
               plain_rough_m=10.0, plain_rough_scale_m=1800.0, plain_blend_m=25.0, plain_radius_m=1.4 * _R0,
               plain_taper_m=0.3 * _R0, plain_fill_max_m=150.0,
               # under the cone the apron's swells fade to 50 % (its round lobes showed through the lower flanks as
               # blobs; the flanks' lobes run downslope: the aging's broad radial streaks)
               plain_rough_inner=dict(factor=0.5, r0_m=0.45 * _R0, r1_m=0.8 * _R0))

PLAIN_KEYS = ('centre', 'basin_m', 'plain_m', 'plain_slope', 'plain_slope_up', 'plain_down_azimuth_deg',
              'plain_extent_m', 'plain_rough_m', 'plain_rough_scale_m', 'plain_blend_m', 'plain_radius_m',
              'plain_taper_m', 'open_azimuth_deg', 'open_half_deg', 'plain_fill_max_m', 'plain_rough_inner')

SURROUNDINGS = dict(K=1.5e-5, valley_spacing_m=500.0, threshold_deg=32.0, threshold_noise=0.2, threshold_scale_m=400.0,
                    threshold_gain=0.08, roughness=0.6, roughness_scales_m=[2000.0, 300.0, 50.0], deposition=0.5,
                    age_myr=2.0, later_frac=0.5, relief_m='$surroundings_relief_m', relief_calib=1.0,
                    breakup=0.15, k_breakup=0.5, outcrops=0.5, breakup_scales_m=[60.0, 20.0, 7.0],
                    outcrop_scale_m=120.0)

# Erosion on the cone by distance from the vent (fractions of R; _apply scales them): the summit kept fresh by its
# eruptions, the steep upper cone (1.4-5 km on Fuji) cut by radial gullies, the mid and lower flanks at 0.6 (the
# reference's 12 km crop: strong radial gullies above about 2000 m, finer and shallower streaks below; its slope
# median, 9.2 degrees at 40 m, is no smooth cone's: cut at a fifth beyond 11 km the median fell to 5.9)
K_PROFILE = [[0.03, 0.5], [0.07, 1.0], [0.25, 1.0], [0.45, 0.6]]

# Gullies of many sizes, a few deep ravines among long smoother ridges, not an even comb (the judge's eye from the
# foot read the flanks as a washboard of shallow gullies all one size): the Osawa-kuzure, Fuji's great ravine on its
# west face from just under the summit down to 2200 m (up to 150 m deep and 500 m wide), a lesser one to
# the north-north-east and five more of their own, seeded before the run so the stream power gathers the drainage
# into them (seeded 110 m deep and 170 m wide it ran as a straight canal); their erodibility varying by sector over
# 30-120 degrees (sector_contrast 1.0: flanks resurfaced by young flows barely cut, older sectors deeply).
# The gullies between the ravines are seeded by sparse wandering furrows (volcanic.radial_streaks with sparse and
# wander_m): only the noise's troughs below -0.6 sigma, each as deep as it reaches, bending as they run down, in
# bands of radius so they start and end; the cone's erodibility gathered into them and the ravines (k_floor: the
# planes between, permeable scoria and lava, erode at 15 %). Two sets: the upper cone's (0.8-4.4 km out, harmonics
# 12-60: some 25 furrows round the cone, 380 m apart at 1.5 km) and the mid flanks' (3-11 km, harmonics 30-140: 500 m
# apart at 5 km, as Fuji's DEM's gullies are 440-670 m apart from 1.5 to 9 km out); then broad lobes 12 m high running
# down the lower flanks onto the apron (6-26 km, harmonics 30-120), the lava and debris lobes between which the
# streams run (round swells there held closed hollows that filled flat).
# (Seeded by straight radial streaks, harmonics 40-160 alike all round with K alike everywhere, the gullies came out
# as a sunburst of straight spokes from the summit, evenly spaced: a washboard from the foot; a round seed texture of
# 3 m at 350 m printed blobs all over the lower flanks.)
RAVINES = [dict(azimuth_deg=262.0, r_m=[0.03 * _R0, 0.27 * _R0], depth_m=60.0, width_m=100.0, wander_m=150.0),
           dict(azimuth_deg=22.0, r_m=[0.07 * _R0, 0.25 * _R0], depth_m=30.0, width_m=80.0, wander_m=120.0)]
RAVINE_FIELD = dict(count=5, r_m=[0.04 * _R0, 0.12 * _R0], length_m=[0.1 * _R0, 0.22 * _R0], depth_m=[12.0, 30.0],
                    width_m=[50.0, 110.0], wander_m=120.0)
#   (wander 40 m on the upper cone and 100 m below: at 80 and 150 m the gullies wound across the flanks like rivers,
#   where Fuji's run nearly straight down the upper cone and bend only lower down)
STREAKS = [dict(amp_m=5.0, k=[12, 60], decay=0.5, r_m=[0.04 * _R0, 0.22 * _R0], bands=3, wander_m=40.0,
                wander_scale_m=1200.0, sparse=0.6, k_floor=0.15),
           dict(amp_m=4.0, k=[30, 140], decay=0.5, r_m=[0.15 * _R0, 0.55 * _R0], bands=3, wander_m=100.0,
                wander_scale_m=2000.0, sparse=0.6, k_floor=0.15),
           dict(amp_m=12.0, k=[30, 120], decay=0.8, r_m=[0.3 * _R0, 1.3 * _R0], bands=3, wander_m=300.0,
                wander_scale_m=3000.0)]

AGE = dict(age_yr=1.0e5, K=2.0e-6, threshold_deg=38.0, threshold_noise=0.15, deposition=1.0, roughness=0.8,
           roughness_scales_m=[1500.0, 300.0, 80.0], valley_spacing_m=350.0,
           k_profile=[[f * _R0, k] for f, k in K_PROFILE], centre=[0.0, 0.0], seed_texture_m=0.0,
           seed_streaks=[dict(s) for s in STREAKS], sector_contrast=1.0, sector_harmonics=[3, 12],
           ravines=[dict(rv) for rv in RAVINES], ravine_field=dict(RAVINE_FIELD),
           keep_craters=[dict(at=[0.0, 0.0], radius_m=1.05 * _F['crater_radius_m'])]
           + [dict(at=[fc['at'][0] - _C0[0], fc['at'][1] - _C0[1]], radius_m=fc['radius_m'])
              for fc in _F['flank_craters']])

# Lakes: Fuji's summit and flank craters are dry (permeable scoria and lava); a closed hollow holds water when it is a
# real basin (0.5 km2 and the design's depth) where the cone and its apron dam the valleys against the ranges, as the
# Five Lakes are (0.5-7 km2, within 26 km of the summit): at most five, none over 8 km2, none beyond 1.3 R; every
# other basin (the ranges' intermontane hollows on the context: 83 lakes up to 230 km2) fills with sediment; on the
# hero levels the ground's own hollows stay (hero_pits 'keep': filled, the rills' puddles lay as dead-flat patches
# over a tenth of the window at the walker's feet)
LAKES = dict(dry=AGE['keep_craters'], min_area_m2=5.0e5, max_area_m2=8.0e6, max_lakes=5,
             lake_radius_m=1.3 * _R0, centre=[0.0, 0.0], hero_pits='keep')

# flank flows along the rift: DOWNFLOW's perturbation a few metres (a quarter of the thickness), their width set
# (Fuji's historic flows: 0.3-1.5 km wide, Aokigahara's far wider), as aa flows (volcanic.lava_surface with
# front_deg): rubble fronts and margins at 35 degrees, broad levees, ridged tops, four lobed units each, narrow at
# the vent; 15-30 m thick, so their fronts and levees stand out at the main level's 39 m cells (10-22 m read as flat
# grey ribbons); each filling the gullies it crosses (bury: the cone's gullies printed through the flows as stripes)
# and spreading as the ground levels out (spread_slope_deg: half its width on the steep flank, up to 1.6 x on the
# apron; at one width all the way the upper flows ran as straight-sided ribbons)
LAVA = dict(rift=dict(centre=[0.0, 0.0], azimuth_deg=_F['rift_azimuth_deg'], count=4,
                      distance_m=[0.15 * _R0, 0.45 * _R0], spread_m=1500.0, length_m=[5000.0, 10000.0],
                      thickness_m=[15.0, 30.0], age=[0.0, 0.6], width_m=[400.0, 1500.0]),
            walkers=600, dh_factor=0.25, front_deg=35.0, levee=0.35, levee_frac=0.12, rough=0.2, stop_spread=0.3,
            front_spread=1.0, vent_taper=0.2, no_climb='local', units=4, bury=True, spread_slope_deg=6.0)


def _apply(p):
    """Every knob into the stages: the cone's size (its crater, platform, flank crater and rift scaled with R), the
    rift, the age and erodibility, the flows, the basin round the vent, the centre."""
    c = [float(v) for v in p['centre']]
    R = float(p['radius_m'])
    k = R / _R0
    cone = p.stage('stratovolcano')
    cone.update(centre=c, height_m=float(p['height_m']), radius_m=R, upper_slope_deg=float(p['upper_slope_deg']),
                rift_azimuth_deg=float(p['rift_azimuth_deg']))
    for key in ('crater_radius_m', 'summit_platform_m'):
        cone[key] = float(CONE[key]) * k
    cone['crater_depth_m'] = float(CONE['crater_depth_m']) * k
    cone['flank_craters'] = [dict(fc, at=[c[0] + fc['at'][0] * k, c[1] + fc['at'][1] * k],
                                  radius_m=fc['radius_m'] * k, depth_m=fc['depth_m'] * k, rim_m=fc['rim_m'] * k)
                             for fc in CONE['flank_craters']]
    rift = dict(CONE['rift'])
    rift.update(count=int(p['rift_cones']), distance_m=[d * k for d in CONE['rift']['distance_m']],
                spread_m=CONE['rift']['spread_m'] * k)
    cone['rift'] = rift
    st = p.stage('volcano_setting')
    st.update(centre=c, basin_m=0.7 * R, ramp_m=0.2 * R, plain_m=float(p['plain_m']), plain_radius_m=1.4 * R,
              plain_taper_m=0.3 * R, plain_rough_inner=dict(SETTING['plain_rough_inner'], r0_m=0.45 * R, r1_m=0.8 * R))
    p.stage('volcano_plain').update({k: st[k] for k in PLAIN_KEYS if k in st})
    age = p.stage('volcano_age')
    craters = ([dict(at=c, radius_m=1.05 * cone['crater_radius_m'])]
               + [dict(at=fc['at'], radius_m=fc['radius_m']) for fc in cone['flank_craters']])
    age.update(age_yr=float(p['age_kyr']) * 1000.0, K=float(AGE['K']) * float(p['erodibility']), centre=c,
               k_profile=[[f * R, kk] for f, kk in K_PROFILE], keep_craters=craters,
               ravines=[dict(rv, r_m=[v * k for v in rv['r_m']], depth_m=rv['depth_m'] * k, width_m=rv['width_m'] * k,
                             wander_m=rv['wander_m'] * k) for rv in RAVINES],
               ravine_field=dict(RAVINE_FIELD, **{kk: [v * k for v in RAVINE_FIELD[kk]]
                                                  for kk in ('r_m', 'length_m', 'depth_m', 'width_m')},
                                 wander_m=RAVINE_FIELD['wander_m'] * k),
               seed_streaks=[dict(s, r_m=[v * k for v in s['r_m']], amp_m=s['amp_m'] * min(k, 1.0),
                                  wander_m=s.get('wander_m', 0.0) * k, wander_scale_m=s.get('wander_scale_m', 2000.0) * k)
                             for s in STREAKS])
    p.stage('volcano_lakes').update(dry=craters, lake_radius_m=1.3 * R, centre=c)
    lava = p.stage('lava_flows')
    lava['rift'] = dict(LAVA['rift'], centre=c, azimuth_deg=float(p['rift_azimuth_deg']), count=int(p['lava_flows']),
                        distance_m=[0.15 * R, 0.45 * R])
    for s in p.stages('breakup') + p.stages('hydraulic'):
        s['enabled'] = bool(p['detail'])


STRATOVOLCANO = Recipe(
    'stratovolcano', 'A stratovolcano: an exponential cone with a summit crater, radial gullies, rift cones, lava '
                     'flows and an apron, among river-carved ranges',
    references=['mount_fuji'],
    defaults={'size': 40000.0, 'context': 3, 'hero_cell': 0.5, 'palette': 'volcanic', 'base_elevation_m': 0.0,
              'lakes': False},
    knobs={
        'height_m': Knob(float(_F['height_m']), 'm', (300.0, 6000.0),
                         "the cone's height above its foot (Fuji: 2983 m over its 755 m median foot)"),
        'radius_m': Knob(_R0, 'm', (2000.0, 60000.0), "the foot's radius, where the cone meets the plain; the "
                                                     "crater, summit platform, flank crater and rift scale with it"),
        'upper_slope_deg': Knob(float(_F['upper_slope_deg']), 'deg', (15.0, 40.0),
                                'the exponential profile: lambda = H / tan(upper slope) (Fuji 35.3)'),
        'age_kyr': Knob(100.0, 'kyr', (1.0, 2000.0), 'erosion time on the cone: 10-100 kyr fine radial gullies, '
                                                     '0.5-2 Myr deep radial valleys with planezes between them'),
        'erodibility': Knob(1.0, '', (0.0, 20.0), 'K on the cone x 2e-6 (young permeable lava erodes slowly)'),
        'rift_cones': Knob(18, '', (0, 80), 'parasitic cones along the rift'),
        'rift_azimuth_deg': Knob(float(_F['rift_azimuth_deg']), 'deg', (0.0, 360.0),
                                 "the rift's strike (both ways), compass degrees; the cone is 12 % longer along it"),
        'lava_flows': Knob(4, '', (0, 20), 'flows from flank vents along the rift (DOWNFLOW walkers)'),
        'surroundings_relief_m': Knob(2100.0, 'm', (100.0, 4000.0),
                                      "the surroundings' relief over the main tile before the cone: the plain's fall "
                                      "plus the river-carved ranges round it (Fuji: 20 m on the coast side to "
                                      "1960 m on the Tenshi ridge)"),
        'plain_m': Knob(float(_F['base_m']), 'm', (0.0, 5000.0),
                        "the plain at the vent, metres above sea level (the cone's foot; Fuji 755 m)"),
        'centre': Knob([0.0, 0.0], 'list', None, 'the vent, world metres'),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup and rills on the hero levels",
                       apply=_apply),
    },
    stages=[
        Stage('volcano_setting', dict(SETTING), levels='all'),
        Stage('fluvial', dict(SURROUNDINGS), levels='all', where='volcano_far'),
        Stage('volcano_plain', {k: SETTING[k] for k in PLAIN_KEYS}, levels='all'),
        Stage('stratovolcano', dict(CONE), levels='all'),
        Stage('volcano_age', dict(AGE), levels=['main', 'hero']),
        Stage('lava_flows', dict(LAVA), levels='main'),
        # the flows' clinker on the levels fine enough to hold it (at 1.7 m the main level's flows were smooth)
        Stage('lava_rubble', {'scales_m': [8.0, 3.0, 1.2], 'amps_m': [1.2, 0.6, 0.3]}, levels='cell<=4'),
        Stage('talus', {'repose_deg': 33.0}, levels='hero'),
        Stage('breakup', {'rock_slope_deg': [30.0, 42.0]}, levels='hero'),
        Stage('hydraulic', {}, levels='hero'),
        Stage('volcano_lakes', dict(LAKES), levels='all'),
    ],
    doc='River-carved ranges grown round the vent -> the apron plain filling the lowland between them -> the cone '
        "stamped on it -> the fluvial backbone for the volcano's age (gullies, fans, apron) -> lava flows from the "
        'rift -> talus, rock breakup and rills on the hero levels -> lakes where the cone and apron dam valleys '
        '(the craters stay dry).')

RECIPES = [STRATOVOLCANO]
