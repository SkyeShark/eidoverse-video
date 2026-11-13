"""alpine_valley: a glacial U-valley (design section 5), judged against Lauterbrunnen (and Yosemite Valley).

    t = make_terrain('alpine_valley', params={'ela_m': 2300, 'trough_width_m': 1400}, focus=(0, -1500))
    from eidoblend.terrain.recipes import alpine_valley as AV
    t = make_terrain('alpine_valley', **AV.preset('yosemite'))     # a granite trough in a domed upland

The defaults are Lauterbrunnen's: one trunk trough down the middle of the tile, draining north, its flat floor about
600 m wide between limestone walls 400-700 m high that stand at 75-80 degrees within 200 m of the floor, under
benches (Muerren, Wengen) and the hanging valleys that open onto them, in a horseshoe of high ridges whose head
stands 9.5 km up-valley. PRESETS hold other settings as make_terrain keyword arguments (knobs, base elevation,
size): 'yosemite', a 1.8 km flat-floored trough with 950 m granite walls and no benches, cut into a gently domed
upland draining west.

The stages:
  1. valley_uplift (every level): a range around one main valley, a crest across its head and two side ridges along
     it (solvers/glacial.py 'horseshoe', Lauterbrunnen's setting: the valley drains north); the coarsest level's
     start is that shape raised to a rough 600 m. Its trunk river runs down the valley's axis from the head and is
     held as base level while the range grows, its bed bench_m above where the trough's floor will lie: the range's
     drainage gathers into one main valley, and the tributaries it grades to it hang that high once the trunk
     glacier has cut the trough below them;
  2. fluvial (every level; below the coarsest kept off the troughs and their shoulders, out to twice to three times
     their half-widths): the river-carved range the ice works on, grown coarse-to-fine to near steady state on the
     coarsest level, refined below it;
  3. glacial (every level): on the coarsest level, once it is fully grown, the ice discharge, the cirques, the
     carve with hanging tributaries (box troughs: a flat floor, cliffs standing at wall_deg within about 200 m of
     it, benches above), the fresh walls' threshold (and lateral moraines, knob moraine_m); on the finer levels the
     walls are sharpened to the level's own cells from the cross-section the carve left, keep their steep
     threshold and fail at it at each level's own scale where the rock is weak;
  4. the trough's floor is levelled by its fill, graded down-valley; the end stage fills what closed basins remain
     with sediment (flat floors; defaults['lakes'] = 'lake' keeps them as ribbon lakes and tarns);
  5. talus (levels with cells of 16 m and finer): the walls' debris at 35 degrees;
  6. rock breakup and hydraulic rills on the hero levels (knob `detail`);
  7. the snow and tree lines for the masks (knobs snowline_m, treeline_m).
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage

SHAPES = {
    # a crest across the valley's head and two side ridges along it (solvers/glacial.py HORSESHOE): Lauterbrunnen's
    # Jungfrau-Breithorn wall at the head, the Schilthorn and Maennlichen ridges either side
    # (a 26 km crest 7.5 km out with 4.5 km falloffs tilted the whole tile north and combed it into four parallel
    # troughs; side ridges near the tile's edges and a narrower crest further out give one trunk with short
    # tributaries square to it, as the real catchment has. The side ridges stand at 0.65 of the crest: the real tile's
    # relief comes from the Jungfrau spurs at its head, its sides are lower, and equal ridges all round made every
    # slope 40-45 degrees)
    # (the head crest 9.5 km up-valley, as the Breithorn-Tschingelhorn wall stands about 10 km south of the tile's
    # centre: the trunk glacier enters the tile with three quarters of the size it leaves with, so the trough keeps
    # its walls through the tile; with the crest 6 km out it entered at 0.43 of it and its upper reach climbed at 14 %.
    # The trunk: solvers/glacial.py TRUNK; its bench_m and grade come from the knobs, _shape; it wanders 300 m either
    # side at 8 km, as Lauterbrunnen's floor bends once through the tile (at 200 m one seed's trough ran dead straight
    # for 8 km, a canal)
    'horseshoe': {'kind': 'horseshoe', 'centre': [0.0, 0.0], 'azimuth_deg': 0.0, 'crest_offset_m': 9500.0,
                  'crest_length_m': 14000.0, 'crest_width_m': 5000.0, 'side_offset_m': 3800.0,
                  'side_shift_m': 3000.0, 'side_length_m': 20000.0, 'side_width_m': 3600.0, 'side_height': 0.65,
                  'join': 0.12, 'texture': 0.3,
                  'trunk': {'head': 0.85, 'width_m': 60.0, 'wiggle_m': 300.0, 'wiggle_wavelength_m': 8000.0}},
    # the Sierra Nevada's west slope at Yosemite: the high country up at the valley's head beyond the tile, the
    # uplands either side at half its height. Their ice stays thin (below the ELA) and one valley glacier comes down
    # from the head (side uplands as high as the crest grew glaciers radiating every way, an ice cap with no trunk)
    'upland': {'kind': 'horseshoe', 'centre': [0.0, 0.0], 'azimuth_deg': 270.0, 'crest_offset_m': 9000.0,
               'crest_length_m': 24000.0, 'crest_width_m': 7000.0, 'side_offset_m': 4500.0, 'side_shift_m': 0.0,
               'side_length_m': 26000.0, 'side_width_m': 5000.0, 'side_height': 0.5, 'join': 0.12, 'texture': 0.25,
               'trunk': {'head': 0.85, 'width_m': 60.0, 'wiggle_m': 400.0, 'wiggle_wavelength_m': 8000.0}},
    'ridge': {'kind': 'ridge', 'centre': [0.0, 0.0], 'azimuth_deg': 70.0, 'length_m': 24000.0, 'width_m': 12000.0,
              'spurs': 8, 'spur_length_m': 5500.0, 'texture': 0.3},
    'massif': {'kind': 'massif', 'centre': [0.0, 0.0], 'radius_m': 14000.0, 'peaks': 6, 'texture': 0.3},
}


def _shape(p):
    spec = dict(SHAPES[p['uplift']])
    if spec['kind'] == 'horseshoe':
        spec['azimuth_deg'] = float(p['drain_azimuth_deg'])
        if spec.get('trunk'):
            # the trunk river's bed stands bench_m over the line the trough's fill grades along (floor_grade). It is
            # held there while the range grows, and the relief controller reads the main tile's relief from its
            # highest half-percent of cells, which the held river's line fills when the range stays lower: at
            # bench_m 970 under relief_m 1100 it cut the uplift to under 1 % and the tile came out a flat plain
            if float(p['bench_m']) > 0.75 * float(p['relief_m']):
                raise ValueError(f"alpine_valley: bench_m {float(p['bench_m']):g} m is over 0.75 of relief_m "
                                 f"{float(p['relief_m']):g} m: the trunk river held that high reads as the range's "
                                 f"relief and stops its uplift; raise relief_m or lower bench_m")
            spec['trunk'] = dict(spec['trunk'], bench_m=float(p['bench_m']),
                                 grade=float(p.stage('glacial')['floor_grade']))
    p.stage('valley_uplift')['shape'] = spec


def _detail(p):
    for name in ('breakup', 'hydraulic'):
        for s in p.stages(name):
            s['enabled'] = bool(p['detail'])


def _defaults_for(values):
    """The snow and tree lines (altitudes) for the masks."""
    return {'mask_params': {'snowline_m': float(values['snowline_m']), 'treeline_m': float(values['treeline_m'])}}


def _tributaries(p):
    p.stage('glacial')['channel_area_m2'] = float(p['tributary_area_km2']) * 1.0e6


# (threshold_iters 4: at 2 a step the slopes ran about 10 degrees past their threshold under the uplift a 2.5 km
# range needs; breakup 0.3 and k_breakup 1: rock steps and ledges at 60-7 m, the texture the real walls carry;
# deposition 0.3: at 0.5 the rivers levelled 25 gravel flats of 0.1-0.3 km2 on the benches above the walls, 3.6 times
# the flat ground Lauterbrunnen has outside its floor)
FLUVIAL = dict(K=1.5e-5, valley_spacing_m='$valley_spacing_m', threshold_deg='$threshold_deg', threshold_noise=0.2,
               threshold_scale_m=400.0, threshold_gain=0.08, roughness=0.6, roughness_scales_m=[2000.0, 300.0, 50.0],
               deposition=0.3, age_myr='$age_myr', later_frac=0.5, relief_m='$relief_m', relief_calib=0.95,
               gullies=True, breakup=0.3, k_breakup=1.0, outcrops=0.5, breakup_scales_m=[60.0, 20.0, 7.0],
               outcrop_scale_m=120.0, threshold_iters=4)

# (the walls: a cliff whose core stands at wall_deg, its toe the lower 40 % of its run (the apron, under the fill
# and talus), its lip the top 12 % (at 20 % the cliff's upper fifth rounded off into the shoulder: Lauterbrunnen's
# walls break sharply at their top); the floor is what the trough's width leaves (glacial.floor_frac: about 560 m at
# 950 m and 80 degrees, 620-670 m where the fill meets the walls). overdeepen 1: the trunk cuts its floor
# trough_depth_m below its river, plus the shoulder cut, so its lip stands shoulder_cut H (150 m) under the river's
# old bed, bench_m - 150 m over the fill's graded line, and the fill levels the floor (the power-law U it replaced
# rose its lower half at 20-50 degrees and was half buried under a fill rising to the walls: the reviewer measured
# 35-45 degree ramps).
# shoulder_cut 0.18 over shoulder_cut_width 2: beyond the lip the ice lowered the old valley floor by up to 150 m,
# the most at the lip, fading out over 1.2 km, so the shoulders rise from the lip at 10-15 degrees and their streams
# fall over the walls. The old valley floor is 1.5-2.5 km wide at the lip's height and the 1.15 km trough takes only
# its middle: the carve to a target leaves what lies under the target untouched, and the strips left along both
# lips were flat for the whole 8 km; the finer levels' rivers then ran along them behind a rim at the protected lip
# and filled them with gravel (seed 2 read as two parallel valleys, seed 3 as a channel between gutters).
# cut 0.3 over cut_width 4, fading as (1 - q)^2: beyond the lip the ice eases the slopes above the walls by at most
# 250 m, the most at the lip (a smoothstep fade held the cap whole for a trough's width and left the capped old
# floor as a shelf; a cut of 0.6 H fading over 2 W planed a bench and then rose out of it in a second 55-degree
# scarp parallel to the trough, the tooled look). shoulder_exp 1: the shoulder rises from the lip at once, about 15
# degrees as Wengen's slopes do.
# floor_rise 0.06 with rise_noise 0.6 at 900 m: the floor rises 20-80 m from the river to the walls' foot, the fans
# and aprons, differing from reach to reach (at 0.02, 14 m everywhere, the floor ran dead level to the cliffs' foot:
# the judge's U-fit read 5.1 against Lauterbrunnen's 1.8, whose floor rises over its fans and talus to the walls).
# floor_exp 1: a tributary's floor share shrinks with its size, so a hanging valley is a U, not a flat-floored slot.
# head_taper 2: a stream's trough grows in over two half-widths from its head instead of ending in a semicircular
# wall (the reviewer's side troughs with stamped, smoothly rounded outlines).
# overdeepen_exp 2: tributary glaciers cut far less deep than in proportion to their size, so they hang without
# basins of their own. smooth_cells 12: a glacier cuts through its river's bends, so the trough runs straighter than
# the valley it took over)
GLACIAL = dict(ela_m='$ela_m', trough_width_m='$trough_width_m', trough_depth_m='$trough_depth_m',
               wall_deg='$wall_deg', moraine_m='$moraine_m', cirques='$cirques', wall_toe=0.4, wall_lip=0.12,
               floor_rise=0.06, rise_noise=0.6, rise_scale_m=900.0, floor_exp=1.0, head_taper=2.0,
               overdeepen=1.0, overdeepen_exp=2.0, cirque_ela_m=2400.0,
               shoulder_width='$shoulder_width', shoulder_rise=0.3, shoulder_exp=1.0, cut=0.3, cut_width=4.0,
               shoulder_cut=0.18, shoulder_cut_width=2.0, floor_grade=0.012,
               wall_noise=0.25, wall_scales_m=[400.0, 120.0, 40.0], channel_area_m2=4.0e6, smooth_cells=12.0,
               rock_flutes=0.6, flute_weak=0.6, flute_strong=0.2)
# (the flutes: couloirs failing to about 72 degrees on 80-degree walls (flute_weak 0.6). At the defaults' 67 degrees
# (0.9) they cut the sharpened walls into deep grooves that hung like curtains)

# other places as make_terrain keyword arguments (preset())
PRESETS = {
    # Yosemite: one wide trough in a granite upland that ice smoothed rather than cut into cirques (80 cirques at
    # every channel head made a field of flat-floored ovals), with few hanging tributaries (Yosemite and Bridalveil
    # Creeks); its walls 950 m at 78 degrees leave a floor about 1 km wide in its 1.8 km (2.2 km left 1.7 km of
    # floor), the old valley floor 970 m above it (the walls 800 m under the shoulder cut's 170 m), the ELA of the
    # last glaciation's Tioga ice low enough that the trunk runs off the tile; the range's relief that of the real
    # tile (1582 m: at 1100 the trunk river held 970 m up read as the range's relief and stopped its uplift)
    'yosemite': dict(size=12000.0, base_elevation_m=1100.0, params={
        'uplift': 'upland', 'drain_azimuth_deg': 270.0, 'relief_m': 1500.0, 'ela_m': 1500.0,
        'trough_width_m': 1800.0, 'trough_depth_m': 950.0, 'bench_m': 970.0, 'shoulder_width': 0.0,
        'wall_deg': 78.0, 'threshold_deg': 20.0, 'valley_spacing_m': 800.0, 'cirques': False,
        'tributary_area_km2': 5.0, 'snowline_m': 3300.0, 'treeline_m': 3000.0}),
}


def preset(name, **params):
    """make_terrain keyword arguments for a PRESETS entry; extra knobs override the preset's."""
    if name not in PRESETS:
        raise KeyError(f'no alpine_valley preset {name!r}; presets: {", ".join(PRESETS)}')
    p = dict(PRESETS[name])
    p['params'] = dict(p['params'], **params)
    return p

ALPINE_VALLEY = Recipe(
    'alpine_valley', 'A glacial U-valley: a flat floor between sheer walls, hanging side valleys, cirques, aretes '
                     'and horns, talus',
    references=['lauterbrunnen', 'yosemite_valley'],
    defaults={'size': 8000.0, 'context': 4, 'hero_cell': 0.5, 'palette': 'alpine', 'base_elevation_m': 800.0,
              'lakes': 'sediment'},
    knobs={
        'relief_m': Knob(2600.0, 'm', (500.0, 6000.0),
                         "the river-carved range's relief on the main tile before the ice (the controller steers the "
                         "uplift to it); the trough is cut into it"),
        'ela_m': Knob(1200.0, 'm', (0.0, 6000.0),
                      'the equilibrium-line altitude of the carving glaciation (the last glacial maximum, not '
                      "today's): glaciers grow above it and reach down-valley until ablation eats them. The trunk "
                      'glacier has to run off the tile and past its context (as the Aare glacier ran out onto the '
                      'Swiss plateau) for the trough to stay deep to its mouth; raise it for shorter glaciers whose '
                      'troughs shallow out before the tile edge'),
        'trough_width_m': Knob(950.0, 'm', (200.0, 6000.0),
                               "the trunk trough's width at its lip (tributaries are narrower by their ice "
                               "discharge, (Q / Q_trunk)^0.4); the flat floor is what the walls leave of it (about "
                               "600 m here, Lauterbrunnen's 400-650; its lips 1-1.15 km apart)"),
        'trough_depth_m': Knob(830.0, 'm', (50.0, 2000.0), "the trunk trough's cut: from its rock floor to the lip, "
                                                          "the glacier's depth below its river's old bed (the fill "
                                                          "then levels the floor bench_m below the lip)"),
        'bench_m': Knob(870.0, 'm', (0.0, 2000.0), "the height of the old valley floor - the benches (Muerren, "
                                                   "Wengen) and the hanging valleys' mouths - above the trough's "
                                                   "floor; the walls stand the shoulder cut (0.18 of trough_depth_m, "
                                                   "150 m) lower, 720 m here (at 650 with no cut the cliffs stood "
                                                   "200-480 m, Lauterbrunnen's 300-950)"),
        'tributary_area_km2': Knob(4.0, '', (0.05, 100.0), "the smallest catchment (km2) whose glacier carves its own "
                                                          "trough; smaller ones only feed their trunk (at 1.5 the "
                                                          "range's every side valley became a hanging trough)",
                                   apply=_tributaries),
        'shoulder_width': Knob(1.5, '', (0.0, 5.0), "the benches above the trough's lip (Muerren, Wengen), as a "
                                                    "share of the trough's half-width; 0: none"),
        'wall_deg': Knob(80.0, 'deg', (35.0, 85.0), "the trough walls' angle: the carved cliff's core stands at it "
                                                    "and the fresh walls' threshold is it (lognormal, with fall-line "
                                                    "couloirs and ribs on the levels that resolve them; "
                                                    "Lauterbrunnen's limestone walls stand at 75-85)"),
        'moraine_m': Knob(0.0, 'm', (0.0, 100.0), 'lateral moraines along the trunk below the ELA, at the foot of the '
                                                  'walls (0: none; ridges parallel to the floor read as tooling where '
                                                  'the river and its fans have since buried them, as in Lauterbrunnen)'),
        'cirques': Knob(True, 'bool', None, 'cirque bowls at the glacier heads near the ELA: aretes and horns '
                                            'between them'),
        'valley_spacing_m': Knob(200.0, 'm', (40.0, 5000.0), "the range's smallest valleys' spacing (200 m: the "
                                                             "couloirs and ribs of a rock range, and little creep "
                                                             "to round its crests)"),
        'threshold_deg': Knob(29.0, 'deg', (15.0, 60.0), "the range's hillslope failure angle above the trimline "
                                                         "(its median slope lands near 38: the outcrops and breakup "
                                                         "stand steeper)"),
        'age_myr': Knob(2.0, 'Myr', (0.2, 10.0), "the range's erosion time on the coarsest level"),
        'uplift': Knob('horseshoe', 'choice', tuple(SHAPES), 'the range around the valley', apply=_shape),
        'drain_azimuth_deg': Knob(0.0, 'deg', (0.0, 360.0), 'the compass direction the main valley drains toward '
                                                            '(horseshoe)'),
        'snowline_m': Knob(2750.0, 'm', (0.0, 8000.0), "today's snowline altitude, for the snow mask"),
        'treeline_m': Knob(1950.0, 'm', (0.0, 8000.0), 'the treeline altitude, for the vegetation mask'),
        'detail': Knob(True, 'bool', None, "the detail package's rock breakup and hydraulic rills on the hero levels",
                       apply=_detail),
    },
    stages=[
        Stage('valley_uplift', {'shape': dict(SHAPES['horseshoe']), 'U_m_per_yr': 3e-3, 'start_m': 600.0,
                                'start_roughness': 0.4}, levels='all'),
        # (below the coarsest level the river-carved range is refined only beyond the troughs' shoulders, rho 2-3:
        # refined up to the lips (where='1 - trough', rho 1.3) it incised the shoulders behind the protected lip by
        # 30-70 m on the 16 km level, its streams ended against the lip, and the gullies they left filled with 40-80
        # m of gravel into flat strips along the trough. Run in its 'refine' mode on the main level instead, down to
        # the lips, it combed every slope of the tile into parallel gullies 100-150 m apart, no slope failing. On the
        # coarsest level trough_rho is 10 until the carve)
        Stage('fluvial', FLUVIAL, levels=['context', 'main'], where='smoothstep(2.0, 3.0, trough_rho)'),
        # on the hero levels the fluvial stage refines without moving the landform (its 'refine' mode: no slope's
        # threshold under the slope it inherits, so only new detail fails): run as on the coarser levels, its
        # threshold (about 37 degrees there) collapsed every cliff the carve left outside the trough mask - the
        # truncated spurs, the cirque headwalls - under a lock of 100-400 m blocks, raising their feet by up to 850 m
        Stage('fluvial', dict(FLUVIAL, mode='refine'), levels='hero', where='smoothstep(2.0, 3.0, trough_rho)',
              name='fluvial_hero'),
        Stage('glacial', GLACIAL, levels='all'),
        Stage('talus', {'repose_deg': 35.0, 'iterations': 64}, levels='cell<=16'),
        # (relief 0.6: the detail package's default 0.25 left the main level with a twentieth of the real tile's
        # power at 33 m and a sixth at 60 m: alpine rock carries more relief than its default)
        Stage('breakup', {'rock_slope_deg': [32.0, 45.0], 'relief': 0.6}, levels='cell<=16'),
        Stage('hydraulic', {}, levels='hero'),
    ],
    doc='A horseshoe range around one valley, its trunk river held as base level down the axis -> the fluvial '
        'backbone (kept off the troughs and their shoulders below the coarsest level) -> the glacial carve on the '
        'grown coarsest level (ice discharge, cirques, box troughs that deepen with discharge so tributaries hang, '
        'cliffs at the walls\' angle, the floor levelled by its fill), the walls sharpened and refined on every finer '
        'level -> talus -> rock breakup and rills on the hero levels.')
ALPINE_VALLEY.defaults_for = _defaults_for

RECIPES = [ALPINE_VALLEY]
