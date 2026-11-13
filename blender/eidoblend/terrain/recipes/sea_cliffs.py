"""sea_cliffs: sea cliffs cut back into the land, a wave-cut platform at their foot, beaches in sheltered bays,
stacks off strong headlands (design section 4.11 and row `sea_cliffs` of section 5). Judged against the Seven
Sisters (chalk, 2 m lidar) and the Cliffs of Moher (layered shale and sandstone, 30 m radar).

    make_terrain('sea_cliffs', seed=3)                                    # chalk: the Seven Sisters
    make_terrain('sea_cliffs', params={'rock': 'layered'})                # shale and sandstone: Moher
    make_terrain('sea_cliffs', params={'retreat_m': 500, 'azimuth_deg': 180}, sea_level=0.0)

Stages, in order:
  coast_land  the land the sea cuts into (coarsest level, every coarse-to-fine pass): an old surface sloping from
              the uplands down past the original coastline (offset_m + retreat_m seaward of the tile centre, facing
              azimuth_deg, bent into headlands and bays by headlands_m) to a base level kilometres out: the plain of
              the low sea levels the land was carved under, drowned and planed since
  fluvial     package 3's backbone on the coarsest level, no uplift: the rivers cut into that surface from the
              distant base level for age_myr, so the valleys run down its slope (chalk: the dry valleys between the
              'sisters'; Moher: shallow streams on a plateau dipping inland) and the surface between them survives
              as broad interfluves. The finer levels inherit the land (Catmull-Rom)
  creep       hillslope.py's linear creep (kappa t) on the coarsest level: the valley sides and crests rounded
              (coast_land runs on every level: on the finer ones down to the main level it refines the land with
              the same backbone before the sea cuts it, REFINE, then rounds it by creep, refine_creep_m2; before,
              every finer level's downland was the 23 m coarsest level's upsampled, blurred and printed with its
              grid)
  coast       every level: exposure (16-direction fetch) and retreat from the original shore, the cliff at the
              retreat line as high as the land there, the platform, talus apron, collapse scars with their debris,
              the shingle beach, Dean beaches in bays, stacks (solvers/coast.py)
  breakup     the detail package's rock breakup on the hero levels' cliff faces: buttresses, joints, scars (knob
              `detail`)

rock='chalk' (the default) is the Seven Sisters: downland on a dip slope toward the sea, consequent dry valleys
about 450 m apart cut 20-60 m into it, a near-straight cliff line at about 79 degrees whose top rises and falls
across the valleys, its face stepped by the chalk's beds and flint bands and recessed by fresh collapse scars with
their fallen blocks at the foot, a flint shingle beach (a 3.6 m crest, 25-60 m wide) and beyond it a 300 m platform
just under the mid-tide sea, a few ledges awash. rock='layered' is Moher: a flat plateau highest at the cliffs and
dipping inland, an
indented coast of coves and headlands with stacks, the face stepped by its beds (sandstone 82-85 degrees, siltstone
and shale 55-60). A knob left at its default takes the rock's own value.

Why no uplift (the steady-state regime of rolling_hills was tried first): with uplift balancing erosion the backbone
dissects the whole surface into a uniform network of planar facets ("folded paper"), and at film quality the relief
controller cut U to 0.2x and left the coastal land 20 m low. The real downs are an old tilted surface whose valleys
were cut into it, with broad smooth interfluves left between them; the reference's steepest 1 % of ground is the
narrow steep sides of those valleys. Start noise is kept below the regional slope (gradients of 1 % against 1.5-2 %),
or undrained hollows survive the short run (6 % of the tile; filled with sediment they became large flat basins).

The sea is make_terrain's sea_level (default 0 m here); the end stage's lake filling is off (defaults['lakes']
False), so the masks' `water` is the sea's depth.
"""
from __future__ import annotations

import numpy as np

from ..core.recipe import Knob, Recipe, Stage

# what each rock sets: the land stage, the fluvial stage, the creep and the coast stage (a knob the caller sets away
# from its default overrides its rock's value)
ROCKS = {
    'chalk': dict(
        # (relief 140 m: with the downs refined, no longer blurred, 160 m stood their uplands at 213 m against the
        # reference's 167 and the cliff tops at 72 m against its 63)
        knobs=dict(relief_m=140.0, valley_spacing_m=450.0, azimuth_deg=200.0, offset_m=390.0, headlands_m=120.0,
                   irregularity=0.06, stacks=0.0, face_deg=78.0),
        # (the refined downland rounded by creep, 120 m^2: the refine alone left knife-edged crests and V notches; at
        # 300 m^2, a 24 m Gaussian on 5.9 m cells, it blurred the downs into a smooth upsampled field)
        land=dict(wiggle_scale_m=2500.0, coast_frac=0.65, rise_m=3000.0, inland_gain=0.25, tilt_m=5000.0,
                  texture=0.08, refine_creep_m2=120.0),
        # the downs refined 3000 steps (225 kyr on the 5.9 m main level): the combes branching off the dry valleys,
        # crisp valley sides under rounded interfluves (at 600 steps, 45 kyr, the land stayed the 23 m level's
        # upsampled, its straight coarse drainage lines printed in it: the review's "blurred, upsampled coarse field")
        refine=dict(refine_steps=3000),
        fluvial=dict(K=8e-6, age_myr=0.4, threshold_deg=32.0, roughness=0.3),
        creep=dict(kappa_t_m2=200.0),
        # chalk is uniform: weak zones only at kilometre scales (at 100-300 m they cut little bays the real cliff
        # line does not have). The face: the chalk's beds and flint bands (column 'chalk': horizontal lines, the
        # material's flint bands read at the same zs), dipping 1 degree east; its crenellation at 60 m and 25 m only
        # (at 15 m every wiggle of the foot line ran straight up the face: the review's 'fine vertical drape
        # flutes'); collapse scars, recesses of 3-12 m with their fallen blocks heaped at the foot. At the foot a
        # flint shingle beach (Birling Gap: a 3-4 m crest, 25-60 m wide; at 32 m x exp(0.45 n) a third of the shore
        # kept under 18 m, the talus apron covered it and a beach camera stood on the rubble), and beyond it the chalk
        # platform just under mid-tide water, a few ledges awash (at +0.1 m +- 0.3 it broke the sea for 150 m out as
        # white islands)
        coast=dict(column='chalk', column_dip_deg=1.0, column_dip_azimuth_deg=90.0,
                   weakness_scales_m=[1500.0, 600.0], crenel_m=1.0, crenel_scales_m=[60.0, 25.0],
                   talus_frac=0.07, talus_max_m=14.0, face_spread_deg=4.0, shingle_m=3.6, shingle_w_m=45.0,
                   shingle_berm=0.35, shingle_var=0.3, platform_top_m=-0.4, platform_rough_m=0.2,
                   platform_slope_deg=0.4, scars=0.45, beach_exposure=[0.25, 0.33]),
    ),
    'layered': dict(
        knobs=dict(relief_m=165.0, valley_spacing_m=600.0, azimuth_deg=300.0, offset_m=180.0, headlands_m=350.0,
                   irregularity=0.45, stacks=0.35, face_deg=74.0),
        # the cliff tops rise and fall along the coast (Moher's from about 30 m to 200 m at O'Brien's Tower): a
        # broad swell of the plateau, its gradients under the inland dip's (2 % here: steeper swells left 11 % of
        # the tile in hollows the short run could not drain). Erosion takes 40-50 m off the start near the coast
        land=dict(wiggle_scale_m=1800.0, coast_frac=0.95, rise_m=300.0, inland_gain=-0.35, tilt_m=3000.0,
                  texture=0.2, texture_scales_m=[8000.0, 5000.0]),
        # a flat moorland plateau (the reference: 84 % of the tile under 5 degrees): fewer, shallower valleys
        fluvial=dict(K=5e-6, age_myr=0.4, threshold_deg=30.0, roughness=0.3),
        creep=dict(kappa_t_m2=150.0),
        # a few stacks off strong headlands, not a speckle of knobs along the whole coast
        # coves and headlands at 300-900 m (a 100 m weakness term carved headlands narrower than two face runs,
        # which the faces closing from both sides sharpened into fangs)
        coast=dict(column='moher', column_dip_deg=1.5, column_dip_azimuth_deg=160.0,
                   weakness_scales_m=[900.0, 300.0], crenel_m=5.0, crenel_scales_m=[60.0, 20.0],
                   stack_scale_m=250.0, talus_frac=0.05, talus_max_m=10.0, face_spread_deg=3.0, shingle_m=1.6,
                   platform_top_m=-0.5, beach_exposure=[0.25, 0.33]),
    ),
}

# start noise below the regional slope (module doc): one kilometre-scale term
LAND = dict(azimuth_deg='$azimuth_deg', offset_m='$offset_m', retreat_m='$retreat_m', wiggle_m='$headlands_m',
            U_m_per_yr=0.0, start_m=150.0, start_roughness=0.04, start_scales_m=[3000.0],
            texture_scales_m=[6000.0, 3000.0])

# the rivers cutting into the old surface (no uplift, so no relief controller: the start sets the heights)
FLUVIAL = dict(K=8e-6, valley_spacing_m='$valley_spacing_m', threshold_deg=32.0, threshold_noise=0.1,
               threshold_scale_m=400.0, roughness=0.3, roughness_scales_m=[1500.0, 400.0], deposition=0.3,
               age_myr=0.4, relief_m=None, gullies=False, breakup=0.0, outcrops=0.0)

COAST = dict(retreat_m='$retreat_m', weakness='$irregularity', stacks='$stacks', face_deg='$face_deg')

# the land's refinement on the finer levels, down to the main level (coast.refine_land): the backbone in refine mode
# (no uplift; the lock holds what the coarser level made), 600 steps (a rock's `refine` takes its own): the dry
# valleys, their sides and the interfluves sharpened at each level's own cells, not a coarse field upsampled
REFINE = dict(refine_steps=600, gullies=False)


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
    land['start_m'] = float(val('relief_m'))
    fl = p.stage('fluvial')
    fl.update(rock['fluvial'])
    fl['valley_spacing_m'] = float(val('valley_spacing_m'))
    # the finer levels refine the land with the same backbone before the sea cuts it (coast.refine_land)
    land['refine'] = dict(fl, **dict(REFINE, **rock.get('refine', {})))
    p.stage('creep').update(rock['creep'])
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
        'relief_m': Knob(140.0, 'm', (10.0, 1500.0),
                         "the height of the old land surface the valleys cut into, its uplands above sea level "
                         "(layered: 165)"),
        'retreat_m': Knob(300.0, 'm', (0.0, 5000.0),
                          'how far an open straight coast has been cut back: the wave-cut platform\'s width'),
        'valley_spacing_m': Knob(450.0, 'm', (60.0, 5000.0),
                                 "the land's valleys (chalk: the dry valleys the cliff cuts across; layered: 600)"),
        'azimuth_deg': Knob(200.0, 'deg', (0.0, 360.0), 'the compass direction the coast faces, toward the sea '
                                                        '(layered: 300)'),
        'offset_m': Knob(390.0, 'm', (-20000.0, 20000.0),
                         "the cliff line's distance from the tile centre toward the sea (layered: 180)"),
        'headlands_m': Knob(120.0, 'm', (0.0, 5000.0),
                            "the original coastline's headlands and bays, metres (std; layered: 350)"),
        'irregularity': Knob(0.06, '', (0.0, 1.5), 'rock weakness spread (ln std): coves where weak, headlands '
                                                   'where strong (layered: 0.45)'),
        'stacks': Knob(0.0, '', (0.0, 1.0), 'strong knobs that stand as stacks when the retreat passes both sides '
                                            '(layered: 0.35)'),
        'face_deg': Knob(78.0, 'deg', (40.0, 89.0), "the cliff face's angle (chalk; the layered face follows its "
                                                    "beds)"),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup on the hero levels' faces"),
    },
    stages=[
        Stage('coast_land', LAND, levels='all'),
        Stage('fluvial', FLUVIAL, levels='first'),
        Stage('creep', {'kappa_t_m2': 200.0}, levels='first'),
        Stage('coast', COAST, levels='all'),
        Stage('breakup', {'rock_slope_deg': [50.0, 62.0], 'threshold': 'field', 'max_fail_m': 1.5},
              levels='hero'),
    ],
    doc='An old land surface (sloping to a base level kilometres out) cut by rivers without uplift, rounded by creep, '
        'then cut back by the sea: exposure x weakness sets the retreat; the cliff stands at the retreat line as '
        'high as the land, over a wave-cut platform, a talus apron and shingle; beaches in sheltered bays; stacks.')

def _flint_column():
    """The chalk face's bands for the material, by stratigraphic height (the coast stage's zs, the beds of its
    'chalk' column): white chalk beds 1.1-2.9 m thick, each topped by a grey band of flint nodules (0.5 m: one pixel
    of the material's strata image, the nodules' grey and the chalk between them averaged), from 40 m below sea
    level to 260 m above it. Deterministic."""
    rng = np.random.default_rng(1907)
    rows, z = [], -40.0
    while z < 260.0:
        t = float(rng.uniform(1.1, 2.9))
        rows.append(('chalk', t, '#e4e0d6', 0.9, t, 0.02))
        rows.append(('flint band', 0.5, '#a19d94', 0.75, 0.5, 0.04))
        z += t + 0.5
    return dict(base_m=-40.0, formations=rows)


def chalk_palette():
    """The chalk coast's material: the surfacing package's chalk_coast scans and colours, each layer placed from the
    coast stage's own fields (height is metres above the sea here):
      - downland turf, broken into fields (600 m patches) over its own 150 m and 9 m patches, drier and yellower on
        the dry valleys' south-facing sides (northness), lusher along their floors (flow), paler on the convex crests
        and darker in the valleys (the options' tone);
      - the wave-cut platform: rock at and under sea level that is neither shingle nor rubble, dark with weed, the
        chalk's ridges pale through it (patches at 10 m), its edge broken at 18 m (the palette's platform needed
        rock_toe, which reaches 60 m from a face: the platform runs 300 m out);
      - the shingle beach: the coast stage's beach deposit up to 6 m over the sea, flint grey, darker where the swash
        wets it (the palette's height and slope bands also painted the platform's shallows and the beach face's
        10-20 degrees turf);
      - chalk rubble on the talus apron and the scars' debris lobes (talus thicker than 0.3-1.2 m under 38-48
        degrees: it fell to the downland grass layer and read as green slopes at the cliff foot), white;
      - the chalk face by slope (40-52 degrees, its edge broken at 40 m and 10 m and held a little lower in the scars'
        hollows; every face steeper than 58-66 degrees whatever talus the detail package's breakup left on it), with
        its flint bands from the coast stage's stratigraphic height (the review: 'the real face shows horizontal flint
        bands'), faint runnels down it, and a tight edge against the turf (its ragged edge noise read as a comb of
        white teeth along the cliff top from Seaford Head; at 42-56 degrees, with the talus taking the face on any
        slope, green teeth ran down from the top and up from the foot);
    and the fallen blocks scattered on the talus, the lobes and the foot."""
    from ..build import palettes as P
    pal = P.get('chalk_coast')
    keep = {L['name']: L for L in pal['layers']}
    down = dict(keep['downland'])
    # the turf by the ground's own shape: grazed fields (600 m), the south-facing slopes of the dry valleys drier
    # and yellower than the north-facing (aspect), the valley floors lusher (flow), over the palette's 150 m and 9 m
    # patches
    down['patches'] = [dict(scale_m=600.0, colour='#7f8a4c', amount=0.45, detail=2.0, lo=0.45, hi=0.62),
                       dict(scale_m=None, colour='#8e8c55', amount=0.4,
                            where='smoothstep(0.1, -0.7, northness) * smoothstep(3, 12, slope)'),
                       dict(scale_m=None, colour='#5d7536', amount=0.35,
                            where='smoothstep(0.55, 0.8, flow + 0.1*(fbm(40, 5) - 0.5))')] + \
        list(down.get('patches') or [])
    platform = dict(keep['platform'], colour='#666b52', projection='planar', normal=0.8,
                    patches=[dict(scale_m=10.0, colour='#c6c1b1', amount=0.55, lo=0.52, hi=0.7)],
                    weight='smoothstep(1.4, 0.5, height + 0.4*(fbm(18, 3) - 0.5)) '
                           '* (1 - smoothstep(0.15, 0.5, deposit + talus))')
    # (flint shingle is dark grey-brown under the white cliffs, Birling Gap's photograph; #8e877b read as pale gravel)
    shingle = dict(keep['shingle'], colour='#736d65',
                   patches=[dict(scale_m=None, tint=(0.72, 0.72, 0.74), amount=1.0,
                                 where='smoothstep(0.9, 0.2, height + 0.3*(fbm(6, 1) - 0.5))')],
                   weight='smoothstep(0.12, 0.5, deposit) * smoothstep(6.5, 4.5, height) '
                          '* (1 - smoothstep(0.6, 1.5, talus))')
    rubble = dict(name='chalk rubble', set='Gravel041', tile_m=3.0, colour='#d3cec1', roughness=1.1,
                  patches=[dict(scale_m=8.0, colour='#bdb8ab', amount=0.4)],
                  weight='smoothstep(0.3, 1.2, talus + 0.4*(fbm(15, 2) - 0.5)) * smoothstep(52, 40, slope)')
    chalk = dict(keep['chalk'], edge_noise=0.1, strata=0.75, streaks=(2.5, 0.22, 0.5, 0.72),
                 # fresh white in the scars' recesses (concave), the weathered face a little greyer, and the splash
                 # zone's grey-green stain on the lowest metres
                 patches=[dict(scale_m=None, colour='#f1eee6', amount=0.7,
                               where='smoothstep(0.25, 0.7, concave_20m + 0.3*(fbm(14, 2) - 0.5))'),
                          dict(scale_m=None, tint=(0.82, 0.88, 0.78), amount=0.5,
                               where='smoothstep(4.0, 1.5, height + 1.5*(fbm(9, 3) - 0.5))')],
                 # the face by slope, its threshold low (40-52 degrees: the brow's band of the slope mask spans a
                 # whole triangle where the mesh is coarse, and at 42-56 it drew a comb of green teeth down the
                 # face's top), the talus taking it only where the debris lies at its repose (the detail package's
                 # breakup leaves talus in the face's chutes; that cut green teeth up from the foot), and every face
                 # over 58-66 degrees chalk whatever lies on it
                 weight='max(smoothstep(40, 52, slope + 6*(fbm(40, 1) - 0.5) + 3*(fbm(10, 0) - 0.5) + 4*concave_20m) '
                        '* (1 - smoothstep(0.8, 2.0, talus) * smoothstep(50, 40, slope)), smoothstep(58, 66, slope))')
    out = dict(pal, layers=[down, platform, shingle, rubble, chalk],
               title=pal['title'] + ' (sea_cliffs: layers from the coast fields, flint bands, chalk rubble)')
    out['options'] = dict(pal['options'], tone='0.05*convex_20m - 0.07*concave_20m')
    out['strata'] = dict(column=_flint_column(), source='attribute')
    if isinstance(out.get('dressing'), dict):
        out['dressing'] = dict(out['dressing'], density='1.2*smoothstep(0.3, 2.5, talus) + '
                                                       '1.0*rock_toe*smoothstep(6, 1, height) + 0.02')
    out.pop('name', None)
    return out


def layered_palette():
    """Moher's material: the surfacing package's alpine layers without forest and snow, the walls darkened to the
    grey-brown of the Clare shales and sandstones with their water streaks, a boulder beach under them, and the
    plateau's pasture (chalk_coast's white chalk would paint Moher's dark faces white)."""
    from ..build import palettes as P
    pal = P.get('alpine')
    keep = {L['name']: L for L in pal['layers']}
    layers = [keep['pasture'], keep['scree'], keep['rock']]
    layers[0] = dict(layers[0], colour='#5c7834')
    layers[1] = dict(layers[1], colour='#6c6961',
                     weight='max(smoothstep(0.2, 1.5, talus), smoothstep(0.25, 0.6, rock_toe), '
                            'smoothstep(3.0, 1.0, height) * smoothstep(14, 6, slope))')
    layers[2] = dict(layers[2], colour='#57534b', streaks=(4.0, 0.5),
                     weight='smoothstep(38, 52, slope + 6*(noise(40) - 0.5))')
    out = dict(title="Moher's coast: dark grey-brown shale and sandstone walls with water streaks, boulders at the "
                     'foot, pasture on the plateau', layers=layers, options=pal['options'],
               dressing=dict(pal['dressing'], colour='#5d5a54'))
    out.pop('name', None)
    return out


def defaults_for(values):
    """The palette by rock: the chalk palette for chalk (also the recipe's static default), Moher's for the layered
    rock. (make_terrain's palette='auto' reads the recipe's static default, so until api.py takes this hook's palette
    for recipes as it does for real places, pass palette=sea_cliffs.layered_palette() for Moher.)"""
    return {'palette': layered_palette()} if values.get('rock') == 'layered' else {}


SEA_CLIFFS.defaults['palette'] = chalk_palette()
SEA_CLIFFS.defaults_for = defaults_for
RECIPES = [SEA_CLIFFS]
