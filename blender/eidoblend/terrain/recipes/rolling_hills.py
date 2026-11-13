"""rolling_hills: soil-mantled rolling hills with convex tops and dense dendritic drainage (design section 5), judged
against the Palouse hills.

    t = make_terrain('rolling_hills', params={'relief_m': 140, 'valley_spacing_m': 300, 'asymmetry': 0.35})

The Palouse is a high loess upland cut by valleys: 90 % of the Steptoe Butte tile lies within 64 m of its top,
its hill summits are level within about 35 m over a kilometre, the hills stand 30-45 m over their hollows, and
one creek valley is cut some 70 m deeper (hypsometric integral 0.66). A landscape at steady state with its rivers
is low instead (its channels' concave profiles put most of the ground near their mouths: the first version of this
recipe measured 0.24), so the recipe runs the history: a hill landscape grown on a high base level, then the base
level falls along the creek and the creek's valley is cut into it.

The stages:
  uplift       a broad upland over the whole 32 km context (the Palouse runs on to the horizon), grown from low
               ground (a rough start a few metres high: the drainage organises everywhere at once, so every
               square kilometre is dissected; a start at full height was dissected only from its edges, and its
               middle stayed a flat table), with slow uplift varying +-25 % at 3 km
  fluvial      the backbone grows the drainage network at the valley spacing (creep strong against incision; the
               threshold is never reached), its relief steered to the upland's (relief_m - incision_m)
  incise       the base-level fall (solvers/fluvial.py): a creek rising in the upland 12 km above the tile and
               flowing south-west across it drops incision_m below the upland's grade over incise_kyr (the fall
               easing in over its first 5 km), and its valley and the lower reaches of its tributaries are cut while
               the knickpoints climb; above them the upland keeps its hills. The finer levels hold its channel
               where it arrives (the incised field), so it stays their base level
  soil_hills   the hillslopes between the channels at their steady soil-mantled form (solvers/hillslope.py): linear
               creep with uplift, so every hill is a smooth convex dome hill_relief_m over hollows hill_spacing_m
               apart, with the lee slopes steeper (asymmetry: the wind from the south-west, as on the Palouse, whose
               north-east faces are the steep ones); the channel heads ease in (no funnels) and the creek's floor
               stays flat
  valley_floor the creek's flat floor (about 100 m wide where 10 km2 drains), on the main and hero levels
Below the main level the hills stay smooth (no gully schedule): their eye-level detail is the soil's and the
vegetation's.
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage


def _relief(p):
    # the growth's target is the upland's relief: the creek's fall adds the rest
    p.stage('fluvial')['relief_m'] = max(float(p['relief_m']) - float(p['incision_m']), 5.0)


def _incise(p):
    p.stage('incise')['years'] = 1000.0 * float(p['incise_kyr'])


FLUVIAL = dict(K=4e-5, valley_spacing_m='$valley_spacing_m', threshold_deg=35.0, threshold_noise=0.1,
               threshold_scale_m=400.0, roughness='$roughness', roughness_scales_m=[1500.0, 300.0, 60.0],
               deposition='$deposition', age_myr='$age_myr', relief_m=70.0, relief_calib=0.9, gullies=False,
               breakup=0.0, outcrops=0.0)

# the creek (a tributary of the Palouse River, flowing south-west across the tile). 235 degrees, not 225: a valley
# exactly along a grid diagonal faces its long walls at 135 and 315 degrees, multiples of 45, and the 8-fold aspect
# bias rose to 0.039. It rises in the upland 12 km above the tile's middle and its fall eases in over 5 km: run from
# the window's edge (base level), its bed could never rise above that edge's height and it ran 130 m under the
# upland, a 200 m gorge 300 m wide; rising 7 km up it drained under 3 km2 across the tile, too little for a floor.
# Its bends: 30 degrees at 1.8 km (at 15 degrees and 2.5 km it crossed the tile as a ruler-straight ribbon)
CREEK = {'kind': 'walk', 'flow_azimuth_deg': 235.0, 'through': [500.0, -400.0], 'wiggle_deg': 30.0,
         'wiggle_wavelength_m': 1800.0, 'width_m': 40.0, 'head_m': 12000.0, 'taper_m': 5000.0}

ROLLING_HILLS = Recipe(
    'rolling_hills', 'Soil-mantled rolling hills: convex tops, dense dendritic drainage',
    references=['palouse_hills'],
    defaults={'size': 4000.0, 'context': 8, 'hero_cell': 0.5, 'palette': 'farmland', 'base_elevation_m': 650.0,
              'lakes': 'sediment'},
    knobs={
        'relief_m': Knob(125.0, 'm', (5.0, 800.0), "the upland's relief (the growth's controller steers to relief_m - "
                                                   "incision_m) plus the creek's fall; the soil hills stand on top, so "
                                                   "the tile's relief comes out some 30 m more (the Palouse: 140 m, "
                                                   "its upland 48 m from its top to its mean)",
                         apply=_relief),
        'incision_m': Knob(80.0, 'm', (0.0, 600.0), "how far the creek's base level falls below the upland's grade "
                                                    "(0: no creek, a landscape at steady state). With 70 m the upland "
                                                    "took 70 of the 140 m and spread its ground too low: "
                                                    "hypsometric integral 0.53 against the Palouse's 0.66",
                           apply=_relief),
        'incise_kyr': Knob(25.0, 'kyr', (1.0, 2000.0), "the fall's time: how far its knickpoints climb the "
                                                       "tributaries (longer: more of the upland cut down, a lower "
                                                       "hypsometry)", apply=_incise),
        'valley_spacing_m': Knob(300.0, 'm', (30.0, 3000.0),
                                 "the smallest valleys' spacing (the Palouse: 333 m between valleys 1 m deep)"),
        'hill_relief_m': Knob(35.0, 'm', (0.5, 300.0), "a hill's height over the hollows either side of it, "
                                                       "hill_spacing_m apart (the soil hills' convexity; the "
                                                       "Palouse: 30-45 m of local relief)"),
        'hill_spacing_m': Knob(560.0, 'm', (30.0, 3000.0),
                               "the hollows' spacing the hill relief stands over (their channels drain at least a "
                               "quarter of its square). Parabolic hills' mean slope is 2 relief / spacing: the "
                               "Palouse's slope p50 7 and p90 13 degrees (p90 / p50 1.9, a parabola's 1.8) are 35 m "
                               "hills 580 m apart; at the valley spacing (300 m) they stood at 13 and 26"),
        'asymmetry': Knob(0.35, '', (0.0, 0.8), 'lee slopes steeper than stoss slopes: their soil diffusivity '
                                                'x (1 - asymmetry), the stoss x (1 + asymmetry); 0: symmetric'),
        'wind_from_deg': Knob(225.0, 'deg', (0.0, 360.0), 'the prevailing wind, compass degrees it comes from (the '
                                                          'lee faces the other way)'),
        'age_myr': Knob(2.0, 'Myr', (0.1, 10.0), 'the growth on the coarsest level (long enough to reach steady '
                                                 'state with the uplift)'),
        'roughness': Knob(0.4, '', (0.0, 1.5), 'erodibility noise at 1.5 km, 300 m and 60 m'),
        'deposition': Knob(0.3, '', (0.0, 2.0), 'G: sediment deposition in the fluvial law'),
        'floor_width_m': Knob(100.0, 'm', (0.0, 400.0), "the creek's flat floor where 10 km2 drains (it grows with "
                                                        "the area to the power 0.4, from 1 km2; 0: none). The "
                                                        "Palouse's upland valleys are rounded swales with no floor"),
    },
    stages=[
        Stage('uplift', {'shape': None,
                         'regional': {'fraction': 1.0, 'wavelength_m': 3000.0, 'texture': 0.25, 'octaves': 3},
                         'U_m_per_yr': 1e-4, 'start_m': 12.0, 'start_roughness': 0.6}, levels='all'),
        Stage('fluvial', FLUVIAL, levels='all'),
        Stage('incise', dict(CREEK, drop_m='$incision_m', years=25000.0, stages=6), levels='all'),
        # the alluvial floor an earlier level laid stays flat (held); the channel heads' hold eases in (no funnels)
        Stage('soil_hills', {'valley_spacing_m': '$hill_spacing_m', 'relief_m': '$hill_relief_m',
                             'channel_frac': 0.25, 'asymmetry': '$asymmetry', 'wind_from_deg': '$wind_from_deg',
                             'head_soft': 2.0, 'hold_deposit_m': 0.3},
              levels='all'),
        # the creek's floor (from 1 km2, a flat floor is under 2 cells wide on the main level below about 3 km2: the
        # upland's swales keep their round bottoms), on the main and hero levels only: from 0.5 km2 on every level,
        # each upland valley got a flat strip along its D8 path (straight ribbons at 45 degrees, the 8-fold aspect
        # bias 0.061) and the context levels flat blobs a kilometre across
        Stage('valley_floor', {'width_m': '$floor_width_m', 'area_ref_m2': 1.0e7, 'width_exp': 0.4,
                               'area_min_m2': 1.0e6, 'width_max_m': 160.0, 'depth_max_m': 20.0},
              levels=['main', 'hero']),
    ],
    doc='A hill landscape grown from low ground over a broad upland (every square kilometre dissected), then a '
        'base-level fall along a creek cutting its valley into it (a youthful, high hypsometry); the hillslopes '
        'between the channels at their steady soil-mantled form (convex domes, lee faces steeper); flat floors in '
        'the larger valleys.')

RECIPES = [ROLLING_HILLS]
