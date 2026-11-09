"""sea_cliffs: sea cliffs cut back into the land, a wave-cut platform at their foot, beaches in sheltered bays,
stacks off strong headlands (design section 4.11 and row `sea_cliffs` of section 5). Judged against the Seven
Sisters (chalk, 2 m lidar) and the Cliffs of Moher (layered shale and sandstone, 30 m radar).

    make_terrain('sea_cliffs', seed=3)                                    # chalk: the Seven Sisters
    make_terrain('sea_cliffs', params={'rock': 'layered'})                # shale and sandstone: Moher
    make_terrain('sea_cliffs', params={'retreat_m': 500, 'azimuth_deg': 180}, sea_level=0.0)

Stages, in order:
  coast_land  the land the sea cuts into (coarsest level, every coarse-to-fine pass): an uplift rising inland from
              the original coastline (offset_m + retreat_m seaward of the tile centre, facing azimuth_deg, bent into
              headlands and bays by headlands_m), and the rough start; the sea beyond it a shallow shelf
  fluvial     package 3's backbone on the coarsest level, the sea as base level: chalk downland with dry valleys
              running down to the sea (the 'sisters' between them), or Moher's plateau with its shallow streams;
              the relief controller holds the land's relief. The finer levels inherit the land (Catmull-Rom)
  coast       every level: exposure (16-direction fetch) and retreat from the original shore, the cliff at the
              retreat line as high as the land there, the platform, talus apron, shingle, Dean beaches in bays,
              stacks (solvers/coast.py)
  breakup     the detail package's rock breakup on the hero levels' cliff faces: buttresses, joints, scars (knob
              `detail`)

rock='chalk' (the default) is the Seven Sisters: rolling downland with dry valleys 600 m apart, a near-straight
cliff line at 74-82 degrees whose top rises and falls across the valleys, a 300 m platform. rock='layered' is Moher:
a plateau dipping gently inland, an indented coast of coves and headlands with stacks, the face stepped by its beds
(sandstone 82-85 degrees, siltstone and shale 55-60). A knob left at its default takes the rock's own value.

The sea is make_terrain's sea_level (default 0 m here): sea cells are the fluvial stage's base level; the end
stage's lake filling is off (defaults['lakes'] False), so the masks' `water` is the sea's depth.
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage

# what each rock sets: the land stage, the fluvial stage and the coast stage (the knobs' own values override)
ROCKS = {
    'chalk': dict(
        knobs=dict(relief_m=165.0, valley_spacing_m=600.0, azimuth_deg=200.0, offset_m=390.0, headlands_m=120.0,
                   irregularity=0.15, stacks=0.0, face_deg=78.0),
        land=dict(wiggle_scale_m=2500.0, rise_m=250.0, inland_gain=0.35, tilt_m=5000.0, texture=0.3),
        fluvial=dict(age_myr=1.5, threshold_deg=32.0, roughness=0.5),
        coast=dict(column=None, crenel_m=3.0, crenel_scales_m=[45.0, 15.0], talus_frac=0.07, talus_max_m=14.0,
                   face_spread_deg=4.0, shingle_m=1.3, platform_top_m=0.2),
    ),
    'layered': dict(
        knobs=dict(relief_m=185.0, valley_spacing_m=900.0, azimuth_deg=300.0, offset_m=180.0, headlands_m=350.0,
                   irregularity=0.45, stacks=0.6, face_deg=74.0),
        land=dict(wiggle_scale_m=1800.0, rise_m=150.0, inland_gain=-0.55, tilt_m=4000.0, texture=0.25),
        fluvial=dict(age_myr=0.8, threshold_deg=30.0, roughness=0.4),
        coast=dict(column='moher', column_dip_deg=1.5, column_dip_azimuth_deg=160.0, crenel_m=5.0,
                   crenel_scales_m=[60.0, 20.0], talus_frac=0.05, talus_max_m=10.0, face_spread_deg=3.0,
                   shingle_m=1.6, platform_top_m=0.3),
    ),
}

LAND = dict(azimuth_deg='$azimuth_deg', offset_m='$offset_m', retreat_m='$retreat_m', wiggle_m='$headlands_m',
            U_m_per_yr=2e-4, start_m=150.0, start_roughness=0.3, shelf_m=12.0, shelf_w_m=1500.0)

# chalk downland: creep strong against incision, so the hillslopes stay under their threshold and the interfluves
# are rounded (rolling_hills' regime), valleys at the knob's spacing, the sea as base level
FLUVIAL = dict(K=2e-5, valley_spacing_m='$valley_spacing_m', threshold_deg=32.0, threshold_noise=0.1,
               threshold_scale_m=400.0, roughness=0.5, roughness_scales_m=[1500.0, 300.0, 60.0], deposition=0.3,
               age_myr=1.5, relief_m=165.0, relief_calib=1.0, gullies=False, breakup=0.0, outcrops=0.0)

COAST = dict(retreat_m='$retreat_m', weakness='$irregularity', stacks='$stacks', face_deg='$face_deg')


def _apply(p):
    """The rock's preset, then every knob the caller set away from its (chalk) default."""
    rock = ROCKS[p['rock']]
    knobs = p.recipe.knobs if p.recipe is not None else {}

    def val(k):
        v = p[k]
        if k in rock['knobs'] and k in knobs and v == knobs[k].default:
            return rock['knobs'][k]
        return v
    land = p.stage('coast_land')
    land.update(rock['land'])
    for k, dst in (('azimuth_deg', 'azimuth_deg'), ('offset_m', 'offset_m'), ('headlands_m', 'wiggle_m')):
        land[dst] = float(val(k))
    land['retreat_m'] = float(p['retreat_m'])
    shelf = float(land.get('shelf_m', 12.0))
    relief = float(val('relief_m'))
    land['start_m'] = relief
    fl = p.stage('fluvial')
    fl.update(rock['fluvial'])
    fl['valley_spacing_m'] = float(val('valley_spacing_m'))
    # the controller measures the main window, sea floor included (about the shelf's depth below sea level)
    fl['relief_m'] = relief + 0.8 * shelf
    co = p.stage('coast')
    co.update(rock['coast'])
    co['retreat_m'] = float(p['retreat_m'])
    co['weakness'] = float(val('irregularity'))
    co['stacks'] = float(val('stacks'))
    co['face_deg'] = float(val('face_deg'))
    for s in p.stages('breakup'):
        s['enabled'] = bool(p['detail'])


SEA_CLIFFS = Recipe(
    'sea_cliffs', 'Sea cliffs: a cliffed coast with a wave-cut platform, beaches in bays and stacks (chalk or layered)',
    references=['seven_sisters', 'cliffs_of_moher'],
    defaults={'size': 6000.0, 'resolution': 1024, 'context': 4, 'hero_cell': 0.5, 'palette': 'chalk_coast',
              'base_elevation_m': 0.0, 'sea_level': 0.0, 'lakes': False},
    knobs={
        'rock': Knob('chalk', 'choice', tuple(ROCKS),
                     "chalk: the Seven Sisters (downland with dry valleys, a straight white face); layered: Moher (a "
                     "plateau, an indented coast with stacks, a face stepped by its beds)", apply=_apply),
        'relief_m': Knob(165.0, 'm', (10.0, 1500.0), "the land's relief above sea level (layered: 185)"),
        'retreat_m': Knob(300.0, 'm', (0.0, 5000.0),
                          'how far an open straight coast has been cut back: the wave-cut platform\'s width'),
        'valley_spacing_m': Knob(600.0, 'm', (60.0, 5000.0),
                                 "the land's valleys (chalk: the dry valleys the cliff cuts across; layered: 900)"),
        'azimuth_deg': Knob(200.0, 'deg', (0.0, 360.0), 'the compass direction the coast faces, toward the sea '
                                                        '(layered: 300)'),
        'offset_m': Knob(390.0, 'm', (-20000.0, 20000.0),
                         "the cliff line's distance from the tile centre toward the sea (layered: 180)"),
        'headlands_m': Knob(120.0, 'm', (0.0, 5000.0),
                            "the original coastline's headlands and bays, metres (std; layered: 350)"),
        'irregularity': Knob(0.15, '', (0.0, 1.5), 'rock weakness spread (ln std): coves where weak, headlands '
                                                   'where strong (layered: 0.45)'),
        'stacks': Knob(0.0, '', (0.0, 1.0), 'strong knobs that stand as stacks when the retreat passes both sides '
                                            '(layered: 0.6)'),
        'face_deg': Knob(78.0, 'deg', (40.0, 89.0), "the cliff face's angle (chalk; the layered face follows its "
                                                    "beds)"),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup on the hero levels' faces"),
    },
    stages=[
        Stage('coast_land', LAND, levels='first'),
        Stage('fluvial', FLUVIAL, levels='first'),
        Stage('coast', COAST, levels='all'),
        Stage('breakup', {'rock_slope_deg': [50.0, 62.0], 'threshold': 'field', 'max_fail_m': 1.5},
              levels='hero'),
    ],
    doc='The land (an uplift rising inland, carved by the fluvial backbone to the sea) cut back by the sea: '
        'exposure x weakness sets the retreat; the cliff stands at the retreat line as high as the land, over a '
        'wave-cut platform, a talus apron and shingle; beaches in sheltered bays; stacks.')

RECIPES = [SEA_CLIFFS]
