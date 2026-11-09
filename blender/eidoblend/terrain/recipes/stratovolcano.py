"""stratovolcano: an exponential cone with a summit crater, radial gullies, parasitic cones on a rift, lava flows and
a debris apron, rising from a plain among river-carved ranges (design 4.7 and section 5), judged against Mount Fuji.

    t = make_terrain('stratovolcano', seed=3)                                   # Fuji-like, 40 km
    t = make_terrain('stratovolcano', params={'age_kyr': 800, 'height_m': 2200, 'radius_m': 14000})   # an old one

Stages, in order (solvers/volcanic.py unless named):
  volcano_setting  the ground the volcano grows on: no uplift within 0.65 R of the vent, ranges beyond it in patches
                   (some sectors open into plains, as round Fuji), and the fresh start surface on the coarsest level
  fluvial          (solvers/fluvial.py) the surroundings: grown to near steady state on the coarsest level, the
                   relief controller holding them at surroundings_relief_m; refined below it, where='volcano_far' so a
                   finer level never erodes the cone it inherited
  stratovolcano    the cone (Fuji's measured profile: H 2983 m above its foot, lambda 4215 m, R 19.9 km), its flat-
                   topped summit with a 220 m deep crater, the Hoei flank crater, 18 rift cones along the NW-SE rift;
                   stamped on the coarsest level's own cells after the surroundings, sharpened on every finer level
  volcano_age      the fluvial backbone run for the volcano's age with no uplift on the main level (time-faithful:
                   radial gullies, the eroded sediment dropped as fans and an apron where the slope eases; the summit
                   renewed by recent eruptions erodes least), then refined under the lock on the hero levels
  lava_flows       DOWNFLOW flows from flank vents along the rift, on the main level
  talus, breakup, hydraulic   the hero levels: scoria at repose on the loose cones, rock breakup on the steep upper
                   cone, rain rills (the detail package's ops)
The end stages (run.py): lakes where the cone dams the surroundings' valleys (Fuji's Five Lakes), drainage.
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
            rift=dict(_F['rift']))

SETTING = dict(centre=[0.0, 0.0], basin_m=0.65 * _R0, ramp_m=0.25 * _R0, cover=0.6, patch_m=9000.0, texture=0.35,
               U_m_per_yr=3e-3, start_m=600.0)

SURROUNDINGS = dict(K=1.5e-5, valley_spacing_m=500.0, threshold_deg=32.0, threshold_noise=0.2, threshold_scale_m=400.0,
                    threshold_gain=0.08, roughness=0.6, roughness_scales_m=[2000.0, 300.0, 50.0], deposition=0.5,
                    age_myr=2.0, later_frac=0.5, relief_m='$surroundings_relief_m', relief_calib=1.0,
                    breakup=0.15, k_breakup=0.5, outcrops=0.5, breakup_scales_m=[60.0, 20.0, 7.0],
                    outcrop_scale_m=120.0)

AGE = dict(age_yr=1.0e5, K=2.0e-6, threshold_deg=38.0, threshold_noise=0.15, deposition=1.0, roughness=0.8,
           roughness_scales_m=[1500.0, 300.0, 80.0], valley_spacing_m=250.0, young_radius_m=4000.0,
           young_factor=0.3, centre=[0.0, 0.0], seed_texture_m=4.0, seed_texture_scale_m=200.0)

LAVA = dict(rift=dict(centre=[0.0, 0.0], azimuth_deg=_F['rift_azimuth_deg'], count=4,
                      distance_m=[0.15 * _R0, 0.45 * _R0], spread_m=1500.0, length_m=[5000.0, 10000.0],
                      thickness_m=[10.0, 22.0], age=[0.0, 0.6]),
            walkers=500)


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
    st.update(centre=c, basin_m=0.65 * R, ramp_m=0.25 * R)
    age = p.stage('volcano_age')
    age.update(age_yr=float(p['age_kyr']) * 1000.0, K=float(AGE['K']) * float(p['erodibility']), centre=c,
               young_radius_m=0.2 * R)
    lava = p.stage('lava_flows')
    lava['rift'] = dict(LAVA['rift'], centre=c, azimuth_deg=float(p['rift_azimuth_deg']), count=int(p['lava_flows']),
                        distance_m=[0.15 * R, 0.45 * R])
    for s in p.stages('breakup') + p.stages('hydraulic'):
        s['enabled'] = bool(p['detail'])


STRATOVOLCANO = Recipe(
    'stratovolcano', 'A stratovolcano: an exponential cone with a summit crater, radial gullies, rift cones, lava '
                     'flows and an apron, among river-carved ranges',
    references=['mount_fuji'],
    defaults={'size': 40000.0, 'context': 3, 'hero_cell': 0.5, 'palette': 'volcanic', 'base_elevation_m': 300.0,
              'lakes': 'lake'},
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
        'surroundings_relief_m': Knob(1500.0, 'm', (100.0, 4000.0),
                                      "the river-carved ranges round the basin: their relief over the main tile"),
        'centre': Knob([0.0, 0.0], 'list', None, 'the vent, world metres'),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup and rills on the hero levels",
                       apply=_apply),
    },
    stages=[
        Stage('volcano_setting', dict(SETTING), levels='all'),
        Stage('fluvial', dict(SURROUNDINGS), levels='all', where='volcano_far'),
        Stage('stratovolcano', dict(CONE), levels='all'),
        Stage('volcano_age', dict(AGE), levels=['main', 'hero']),
        Stage('lava_flows', dict(LAVA), levels='main'),
        Stage('talus', {'repose_deg': 33.0}, levels='hero'),
        Stage('breakup', {'rock_slope_deg': [30.0, 42.0]}, levels='hero'),
        Stage('hydraulic', {}, levels='hero'),
    ],
    doc='River-carved ranges grown round a basin -> the cone stamped over them -> the fluvial backbone for the '
        "volcano's age (gullies, fans, apron) -> lava flows from the rift -> talus, rock breakup and rills on the "
        'hero levels; lakes where the cone dams valleys.')

RECIPES = [STRATOVOLCANO]
