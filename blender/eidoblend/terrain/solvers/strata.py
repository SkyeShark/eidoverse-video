"""Layered rock (design section 4.9): a stratigraphic column in world z that the erosion reads at every cell's current
height, so canyons step in cliffs and benches, mesas and buttes stand on talus over a flat floor, and badlands cut
banded mudstone into knife ridges.

    stage ops (OPS; run.py calls op(fields, level, params, seed, ctx=...)):
      'strata'          the column and where it sits (dip, warp, faults, its height at h = 0), kept for the level's
                        later stages (ctx.shared['strata']), and the field zs (stratigraphic height, metres: the
                        masks' `strata`, which the material reads its colour bands at)
      'plateau'         the start (on a fresh level only): a structural surface at one stratigraphic height (so it
                        follows the dip and warp of the beds), roughened, optionally with an escarpment
      'strata_fluvial'  the fluvial backbone (solvers/fluvial.py's passes) in layered rock: the erodibility K x
                        K(zs) in the stream-power incision, the composite threshold (each layer at its own angle,
                        talus at repose) in place of a single Sc, creep only on soft rock and debris, and the
                        base-level fall: a 'river_path' channel lowered from the starting surface to its final bed
                        over the run (solvers/rivers.py); optionally stopped at a target caprock fraction (mesas)

    from eidoblend.terrain.solvers import strata as S
    col = S.column('colorado_plateau')            # bottom to top, zs = 0 at its base
    col.tan_at(800.0), col.k_at(800.0), col.run_at(800.0), col.layer_at(800.0)
    col.formations()                              # [(thickness_m, K_factor, Sc_deg, colour_id, name), ...] for the
                                                  # material (build/palettes.column_layers reads this form)
    S.palette_for('desert_sandstone', 'colorado_plateau')   # a palette dict whose strata layers read this column
                                                  # (its own thicknesses, colours from MATERIAL): a recipe's
                                                  # defaults['palette'], which palettes.resolve_name honours

The column. Layers bottom to top, each (thickness_m, K_factor, Sc_deg, colour_id, name) or a dict with those keys
plus `creep` (0..1, how much the layer creeps: soft rock 1, cliff rock about 0; default from Sc) and `beds` (ledges
inside the formation: {'period_m', 'ledge_frac', 'ledge_K_factor', 'ledge_Sc_deg', 'jitter'}: the Supai's ledges and
slopes, the Brule's thin sandstones; resolved on the fine levels, averaged by the run integral on the coarse ones).
Tabulated every dz (0.5 m) from 60 m below its base to 60 m above its top: K factor, tan(theta), creep factor, and
the horizontal run R(zs) = integral dz / tan(theta(z)); beyond, the end layers continue.

Stratigraphic height. zs = h + zs0_m - tan(dip) (x cos az + y sin az) - warp(x, y) - throws - fold: zs0_m is the
column height at h = 0 at the origin, the beds rise toward azimuth_deg (counter-clockwise from +x: the design's
formula, the same as masks.py and build/surfacing.py), warp is world noise ([[wavelength_m, amp_m], ...], amp the
standard deviation), each fault drops the beds on one side of its line by throw_m, and fold {'axis_deg' (compass),
'through', 'rise_m', 'half_width_m'} raises them rise_m (d / half_width)^2 at a distance d from the axis (a
syncline; rise < 0 an anticline). The kernels read zoff = h - zs. (The material's strata bands read the zs field
the masks write, so they follow dip, warp, faults and fold alike.)

The composite threshold (kernels/strata_threshold.glsl, the design's rule). Between a cell and its downhill
neighbour the column needs the run R(zs) - R(zs - G dx); the cell is over its threshold when that exceeds dx, and
the excess phi = 1 - dx / run feeds the isotropic exchange of kernels/threshold.glsl (package 3's: mass-conserving,
the moved rock lands as talus). For one uniform layer it is the stock rule (slope <= tan theta); in a column a weak
layer cut back under a cliff makes the cliff fail and retreat. The cell's loose cover (h - bed) rests at repose.

Parameters of 'strata_fluvial' (metres, years, degrees; K in the stream-power law's units). As 'fluvial'
(solvers/fluvial.py): K 1.5e-5, m 0.5, n 1, p 1, slope 'dinf', valley_spacing_m 400 (or D), gullies, roughness 0.3
with roughness_scales_m, k_breakup and breakup_scales_m, deposition 0.5, age_myr 2, dt_ref_yr 1000, refine_steps
1500, lock True, lock_m, min_steps, max_steps, creep_cap 5, max_creep_sub 32, fill_pits, pit_eps_m. Its own:
    U_m_per_yr 0               uplift (layered-rock landforms are driven by base-level fall: 0)
    threshold_iters 3, threshold_rate 0.12     the composite threshold's iterations per step
    repose_deg 34              loose cover (talus, deposits) at its repose angle
    later 'refine'             the coarsest level's later coarse-to-fine passes: 'refine' holds what the first pass
                               made under the low-pass lock and sharpens it (cliffs, benches, gullies), 'evolve' runs
                               on (age x later_frac) like the stock stage
    later_frac 0.25
    pin_every 8                steps between moves of the falling channel
    caprock_zs_m None, caprock_target None, check_every 40    stop the first pass when the share of the main
                               window still at or above the caprock's base height (stratigraphic) falls to the target
    weather_m_per_yr 0         weathering (STRATA_WEATHER, the scarp-retreat process): rock of K factor 1 on a
                               slope of weather_slope_deg (30) lowers this fast, in proportion to the slope (so every
                               contour retreats weather_m_per_yr / tan(30 degrees) metres a year horizontally, in
                               any direction; weather_sat caps the slope term, 1 the old saturated law), any layer by
                               its K factor (loose cover x weather_loose, 2), whatever drains across it: weak rock
                               under a cliff wears back, the cliff fails over it and retreats, the strong bed below
                               stays a bench
    weather_area 0             x (1 + weather_area sqrt(A / 10 ha)): faster where runoff gathers (amphitheatres,
                               side canyons, the escarpment fraying into fingers and buttes)
    weather_area_slope_deg [20, 35]   the boost ramps in over these slopes: it acts on scarps; on gentle ground
                               the gathered runoff is the stream-power term's (boosted there, every wash sank a valley
                               into a floor or bench that should stay a stripped structural surface)
    weather_refine 0           the weathering's factor on the passes under the low-pass lock (it grows the landform;
                               there it only fought the lock, which raised the plateau beside a retreating wall)
    weather_k_exp 1            the weathering reads K factor^weather_k_exp where the K factor is under 1 (weather_table):
                               massive cliff rock retreats by failing over its undercut base, not by surface wear, so
                               2 slows the cliffs' own wear (the Muav x0.16, the Redwall x0.04) and keeps soft rock's
    joints (), joint_gain 0    joint sets (joint_field): K x (1 + joint_gain x the joints' weakness): incision and
                               weathering follow the fractures (straight-sided blocks, mesas and buttes)
    resist 0, resist_run 0, resist_scales_m [1400, 600]   the rock mass (rock_mass: n, unit noise at those scales,
                               world space): K x exp(-resist n) and the composite threshold's run of rock
                               x exp(-resist_run n): a retreating escarpment leaves the strong patches standing
                               (outliers: mesas, buttes), and a wall is sheer buttresses where the rock is strong,
                               chutes and talus where it is weak
    resist_noise 1             the noise part of n is scaled by this (the cores are not): a weakly varying caprock
                               with a few massive cores (mesas and buttes with flat tops)
    resist_cores None          strong cores added to n (rock_cores: {'spacing_m', 'radius_m' [lo, hi],
                               'elongation' [lo, hi], 'angles_deg' (joint directions, compass) or None, 'strength',
                               'region_m', 'seed', 'exponent' (the outline's superellipse power, 4), 'wobble' (its
                               radius noise, 0)}): blue-noise blocks of massive rock the escarpment leaves standing
                               (buttes)
    dry_basins False           after each pass, fill every closed depression that does not touch the river's channel
                               with sediment (fill_dry_basins): a desert plateau's basins are dry sinks; the river's
                               pools stay basins, which the end stage holds as water (recipes with lakes 'lake')
    sod None                   a grass cover on the hero levels ({'below_deg' 10, 'above_deg' 22, 'k' 0.1, 'hero_only'
                               True}): K x k where the inherited surface is gentler than below_deg, ramping to x1 at
                               above_deg (prairies stay smooth sod; the bare walls rill)
    facies None                the beds' lateral facies change ({'strength' 0.5, 'scale_m' 300, 'scale_z_m' 40,
                               'weather' 0.5, 'seed'}; facies_spec): a 3D noise f of world position and stratigraphic
                               height scales the rock's run in the composite threshold by exp(-strength f) and its
                               weathering rate by exp(-weather f), so each bed is a cliff in one place and a ledgy
                               slope in another, wears back into alcoves here and stands as a buttress there,
                               independently of the beds above and below (rock_mass's n is one value through every
                               bed at a place)
Fields read: h, bed (else all rock), K_factor, A, qs. Written: h, bed, A, qs, wear, deposit, talus, zs, and U, K, Sc
(the layer's own tan theta at each cell), G.

Twins (tests only, the 'twin' device): strata_threshold, strata_cell, strata_creep, strata_weather below.
"""
from __future__ import annotations

import math
import time

import numpy as np

from ..core import twins as T
from . import fluvial as FL
from . import rivers as RV

F32 = np.float32
DZ = 0.5
PAD_M = 60.0


# =============================================================================================== the columns ===
# Bottom to top. Thicknesses are the section's own; K_factor multiplies the stage's K; Sc_deg is the angle the rock
# stands at (cliffs 70-84, ledgy slopes 40-50, shale 28-34). Colour ids match build/palettes.LAYER_COLOURS.

def _L(name, thickness_m, K_factor, Sc_deg, colour=None, creep=None, beds=None):
    d = dict(name=name, thickness_m=float(thickness_m), K_factor=float(K_factor), Sc_deg=float(Sc_deg),
             colour=colour or name.split()[0].lower())
    if creep is not None:
        d['creep'] = float(creep)
    if beds is not None:
        d['beds'] = dict(beds)
    return d


COLUMNS = {
    # The Grand Canyon's Paleozoic section as it stands at Toroweap (east of the Toroweap fault): an inner gorge of
    # Muav, Temple Butte and Redwall walls under the lower Supai's ledges, the Esplanade sandstone's wide bench, the
    # Hermit shale slope, and the Coconino, Toroweap and Kaibab rim; Bright Angel shale, Tapeats and Vishnu below
    # for deeper canyons. Contacts checked against the Toroweap DEM's gentle-ground heights (the Esplanade bench at
    # 1300-1450 m holds 45 % of the tile, the river at 505 m, the rim at 1950 m); the angles against its walls by
    # altitude at 8 m (the Muav and lower Supai ledgy slopes with p50 32-40 degrees and cliff bands at p90 65-75, the
    # Redwall p90 72-78, the Hermit slope 21-30, the Coconino p90 62-68, the Kaibab p50 41-46).
    # The units are the members as they crop out, thick cliffs and the slopes between them, not a repeating ledge
    # pattern: with 14-28 m ledge periods (2-3 cells at 8 m) every wall came out as dozens of thin parallel terraces,
    # the same thickness all along the canyon (the review: Toroweap's benches are few, wide and irregular, between
    # cliff bands 50-150 m tall). Thicknesses for the western canyon (Muav and Temple Butte thick and cliffy, the
    # Coconino thin); the Supai as its four members (Watahomigi slope, Manakacha cliff, Wescogame ledges, Esplanade
    # cliff whose top is the Esplanade bench).
    # The cliff angles are the rock mass's mean (strata.rock_mass steepens the strong spots to 78-82 degrees): at
    # 76-82 everywhere the walls were bare and uniform, slope p90 63 degrees against Toroweap's 51 at 8 m. The Muav
    # is cliffs and ledges of uneven thickness (as one 180 m cliff 93 % of its outcrop was over 51 degrees, where
    # Toroweap's walls at that height have a median of 43-50); the Redwall stays the one great cliff. The Muav's
    # ledgy members are thin-bedded dolomitic limestone, not shale (K x0.5): at x0.8-0.9 they wore back beside the
    # river into bedrock benches 0.6-1 km wide, 15-150 m over it, and every section came out a flat-floored
    # trapezoid where Toroweap's inner gorge rises straight from the water (half its height within 400 m).
    # Few, bold members (the review: Toroweap's cliff bands are 50-150 m tall with few, wide, irregular benches): the
    # Muav as two cliffs 100-110 m tall with ledgy slopes between, the Manakacha one cliff-and-ledge member, the
    # Toroweap one ledgy member (with eight Muav members and the Toroweap's three, the amphitheatres showed six to
    # eight thin, evenly spaced bands). The lower Supai members are ledges (48-50 degrees, K x0.5-0.55), not slopes:
    # Toroweap's Esplanade rim stands at the inner gorge's top, 900 m of near-sheer wall; as slopes (K x0.8-1) they
    # wore back 450 m under the Esplanade and the gorge was 2 km wide at the bench against Toroweap's 1.2-1.4. The
    # ledgy members stand at 38-44 degrees, under the talus that covers them (the talus peak at 25-40 degrees).
    'colorado_plateau': [
        _L('Vishnu schist', 200, 0.35, 65, 'vishnu'),
        _L('Tapeats sandstone', 60, 0.3, 70, 'tapeats'),
        _L('Bright Angel shale', 80, 2.5, 32, 'bright angel'),
        _L('Muav limestone, lower cliffs', 110, 0.4, 70, 'muav'),
        _L('Muav limestone, ledgy middle', 60, 0.55, 38, 'muav'),
        _L('Muav limestone, upper cliffs', 100, 0.4, 68, 'muav'),
        _L('Muav limestone, top ledges', 80, 0.5, 40, 'muav'),
        _L('Temple Butte formation', 60, 0.35, 64, 'muav'),
        _L('Redwall limestone', 170, 0.2, 74, 'redwall'),
        _L('Watahomigi formation (lower Supai ledges)', 70, 0.55, 48, 'supai'),
        _L('Manakacha formation (Supai cliffs and ledges)', 70, 0.4, 62, 'supai'),
        _L('Wescogame formation (Supai ledges)', 60, 0.5, 50, 'supai'),
        _L('Esplanade sandstone', 85, 0.18, 72, 'esplanade'),
        _L('Hermit shale', 265, 3.5, 25, 'hermit'),
        _L('Coconino sandstone', 50, 0.25, 74, 'coconino'),
        _L('Toroweap formation', 100, 0.9, 46, 'toroweap'),
        _L('Kaibab limestone, Fossil Mountain cliff', 90, 0.3, 70, 'kaibab'),
        _L('Kaibab limestone, Harrisburg ledges', 90, 0.8, 42, 'kaibab'),
    ],
    # The Goosenecks of the San Juan: the Paradox and Honaker Trail formations, limestone ledges and shaly slopes in
    # thin alternation (the walls "stepped in ledges and slopes"), the lower walls the cliffiest, under the
    # Halgaito's red slopes and a resistant bed the plateau is stripped to. Angles against the Goosenecks DEM at 6 m
    # by height above the river: 0-120 m p50 31-43, p90 55-70 degrees; 120-240 m p50 30-35, p90 43-63; above that
    # benches and the plateau with 25-30 degree slopes.
    # The units are cliffs and slopes 20-70 m thick (3-12 cells at 6 m): with 9-30 m ledge periods every slip-off
    # slope came out as concentric contour terraces, and the 0-150 m above the river had no cliff (p90 44 degrees
    # against the DEM's 65). The river runs in the Paradox's lower cliff; the rim is the upper Honaker Trail's top
    # ledge, 280 m over the river (the overlook's bench); the Halgaito's red slope stands back from it under a thin
    # resistant Cedar Mesa bed the plateau is stripped to (a weak plateau surface was combed by radial gullies).
    # The Halgaito is soft red siltstone (K x5): at x2.5 its scarp stood 200 m behind the rim, and the whole tile
    # beyond the canyon was a flat plateau 90 m above the rim, where the ground round the Goosenecks is a broad rough
    # bench at the rim's level (median 210-250 m over the river from 0.4 to 2.5 km out) with the Halgaito's slopes
    # and the Cedar Mesa's ledges standing kilometres back. (K x9: at x5 the flat top 300-400 m over the river still
    # held 41 % of the tile against the Goosenecks' 26 %; with ledges in the Halgaito it never retreated at all and
    # the tile was one high flat to the rim.) The Cedar Mesa's basal bed is 30 m at 64 degrees, a 15 m run (2.5 cells
    # at the 6 m main level): at 20 m and 70 degrees it cropped out as a dotted one-cell line round the scarp.
    # (Tried: the Paradox as one massive cliff with the river 40 m in it and the lower Honaker Trail as ledgy cliffs,
    # for a sheerer lower wall: the tile became a high flat plateau, HI 0.77 against 0.59, with walls too steep, slope
    # p90 49 against 42, and from the overlook the river stayed hidden behind the upper slopes.)
    'honaker_trail': [
        _L('Paradox formation, lower cliff', 50, 0.25, 76, 'limestone'),
        _L('Paradox formation, shaly ledge', 20, 0.9, 40, 'shale'),
        _L('Paradox formation, upper cliff', 70, 0.25, 74, 'limestone'),
        _L('lower Honaker Trail formation, slope', 25, 1.0, 36, 'shale'),
        _L('lower Honaker Trail formation, cliff', 35, 0.3, 70, 'limestone'),
        _L('lower Honaker Trail formation, ledges', 30, 0.9, 42, 'limestone'),
        _L('upper Honaker Trail formation, cliff', 25, 0.35, 66, 'limestone'),
        _L('upper Honaker Trail formation, slope', 35, 1.2, 34, 'shale'),
        _L('upper Honaker Trail formation, rim ledge', 30, 0.3, 66, 'limestone'),
        _L('Halgaito formation', 80, 9.0, 30, 'shale'),
        _L('Cedar Mesa sandstone (basal bed)', 30, 0.18, 64, 'cedar mesa'),
        _L('Cedar Mesa sandstone', 70, 0.5, 45, 'cedar mesa'),
    ],
    # Monument Valley: the Cedar Mesa sandstone the floor is stripped to (resistant: the floor stays a broad flat,
    # not a valley network cut into weak shale), the Organ Rock shale's talus pedestals (about 120 m under the
    # Mittens), the De Chelly sandstone's sheer walls (about 210 m) and the thin conglomerate cap the buttes' flat tops
    # are (a weak Moenkopi slope on top wore into convex humps with saw-toothed crests).
    # (the Cedar Mesa at K x0.3 was planed to the wash's level over the run, so the floor lost the dip that lifts
    # Monument Valley's 150-200 m toward the west: K x0.08 keeps it a stripped structural surface)
    # The proportions are the Mittens': a De Chelly cliff about 160 m tall on an Organ Rock pedestal about 150 m tall
    # (on the DEM the caps' edges stand 275-300 m over the floor and the cliffs' feet 100-150 m over it, 100-150 m
    # out; the pedestal reaches 400 m out). With a 210 m De Chelly over 120 m of Organ Rock the cliff came down to
    # 70 m over the floor and the talus cone was half Monument Valley's (the review: one wall straight to the floor,
    # no pedestal).
    # The Organ Rock has thin sandstone ledges (every 18 m, a fifth of it, 55 degrees): the pedestals' bands under the
    # Mittens; without them the generated tile had a third less of its caprock and its walls faced four ways (A4 0.10)
    'monument_valley': [
        _L('Cedar Mesa sandstone', 150, 0.08, 62, 'cedar mesa'),
        _L('Organ Rock shale', 150, 2.5, 31, 'organ rock',
           beds=dict(period_m=18.0, ledge_frac=0.2, ledge_K_factor=0.5, ledge_Sc_deg=55.0, jitter=0.5)),
        _L('De Chelly sandstone', 160, 0.08, 80, 'de chelly'),
        _L('Shinarump conglomerate', 20, 0.1, 78, 'shinarump'),
    ],
    # The Badlands Wall near Cedar Pass: Chadron clay mounds at the foot, the Brule's banded mudstone with thin
    # sandstone and ash ledges (the Scenic member, then a resistant sandstone the middle surface is stripped to, the
    # Poleslide member), the Rockyford ash and the Sharps formation at the top.
    # The mudstone stands steep and bare (knife-edge ridges at about 50 degrees with steeper ledges, the Wall's p99
    # at 3 m about 58, at 1.2 m 69) and hardly creeps: at 46 degrees with creep 0.4 every ridge was rounded into a
    # pillow; at 51 with 68-degree ledges the 3 m tile's p99 came out 64.
    'badlands': [
        _L('Chadron formation', 30, 2.0, 34, 'chadron', creep=1.0),
        _L('Brule formation, Scenic member', 46, 1.2, 49, 'brule', creep=0.1,
           beds=dict(period_m=3.5, ledge_frac=0.25, ledge_K_factor=0.4, ledge_Sc_deg=65.0, jitter=0.5)),
        _L('Brule formation, channel sandstone', 4, 0.15, 70, 'sandstone'),
        _L('Brule formation, Poleslide member', 48, 1.0, 49, 'brule', creep=0.1,
           beds=dict(period_m=4.0, ledge_frac=0.25, ledge_K_factor=0.4, ledge_Sc_deg=65.0, jitter=0.5)),
        _L('Rockyford ash', 6, 0.5, 62, 'ash'),
        _L('Sharps formation', 40, 1.0, 48, 'sharps', creep=0.15,
           beds=dict(period_m=5.0, ledge_frac=0.2, ledge_K_factor=0.45, ledge_Sc_deg=62.0, jitter=0.5)),
    ],
    'chalk': [_L('chalk with flint bands', 400, 0.8, 80, 'chalk')],
    'limestone': [_L('limestone', 600, 0.4, 75, 'limestone')],
    'granite': [_L('granite', 3000, 0.25, 65, 'granite')],
}


# The colour of each colour id in daylight photographs (desert varnish and staining included), with the material's
# roughness multiplier, mean bed thickness (m) and bed colour jitter: build/palettes' strata-column form. A colour is
# a hex or [(hex, weight), ...] (each bed draws one: the Brule's buff beds with red and maroon palaeosols). The
# Grand Canyon and Badlands colours are the surfacing package's, calibrated on those places (palettes.STRATA_COLUMNS
# 'toroweap' and 'badlands_cedar_pass').
MATERIAL = {
    'vishnu': ('#4f4844', 1.0, 6.0, 0.05), 'tapeats': ('#7d5b45', 1.0, 2.0, 0.07),
    'bright angel': ('#7a6f5e', 1.0, 2.0, 0.06), 'muav': ('#8c6553', 1.0, 3.0, 0.06),
    'redwall': ('#a15b43', 0.95, 6.0, 0.05), 'supai': ('#8f4a33', 1.0, 2.5, 0.09),
    'esplanade': ('#a8653f', 0.95, 4.0, 0.06), 'hermit': ('#9a4f37', 1.0, 2.0, 0.07),
    'coconino': ('#cdb48c', 0.9, 6.0, 0.04), 'toroweap': ('#b19a7c', 1.0, 2.5, 0.06),
    'kaibab': ('#c4b294', 0.95, 3.5, 0.05),
    'limestone': ('#9e958a', 0.95, 2.5, 0.06), 'sandstone': ('#b0875f', 1.0, 2.5, 0.07),
    'shale': ('#94634c', 1.0, 1.5, 0.07),
    'cedar mesa': ('#c7a17b', 1.0, 3.0, 0.06), 'organ rock': ('#9c4f37', 1.0, 2.0, 0.07),
    'de chelly': ('#b8663f', 0.95, 8.0, 0.04), 'moenkopi': ('#9a5940', 1.0, 1.5, 0.08),
    'shinarump': ('#a7896c', 1.0, 2.0, 0.06),
    'chadron': ('#a29e8b', 1.0, 3.0, 0.05),
    'brule': ([('#cdae92', 0.55), ('#b47a62', 0.22), ('#9a6150', 0.12), ('#d9d1c2', 0.11)], 1.0, 0.9, 0.07),
    'ash': ('#ddd6c8', 0.95, 1.5, 0.04), 'sharps': ([('#cdbfa8', 0.8), ('#b9a58c', 0.2)], 1.0, 1.6, 0.06),
    'chalk': ('#e2ded3', 0.9, 1.2, 0.03), 'granite': ('#9d9890', 1.0, 40.0, 0.03),
}


def material_column(spec, dz=None, seed=0):
    """The column as build/palettes' strata-column dict ({'base_m': 0, 'formations': [(name, thickness_m, colour,
    roughness, bed_m, jitter), ...]}): the solver's own thicknesses, so the material's colour bands sit on the
    benches the solver made (the mask `strata` is zs, from the column's base)."""
    col = column(spec, DZ if dz is None else dz, seed)
    rows = []
    for d in col.layers:
        c = MATERIAL.get(str(d['colour']).lower(), ('#a39a8e', 1.0, 2.5, 0.06))
        rows.append((d['name'], d['thickness_m']) + tuple(c))
    return {'base_m': 0.0, 'formations': rows}


def palette_for(base, spec):
    """A palette dict for a recipe's defaults['palette'] (build/palettes resolves 'auto' to it): the named palette
    with its strata layers reading this column (material_column), from the attribute the masks write (zs)."""
    import copy
    from ..build import palettes as P
    pal = copy.deepcopy(P.PALETTES[base])
    pal['name'] = f'{base}+{spec if isinstance(spec, str) else "column"}'
    pal['strata'] = {'column': material_column(spec), 'source': 'attribute'}
    return pal


def default_creep(sc_deg):
    """How much a rock creeps from the angle it stands at: shale and mudstone (<= 35 degrees) 1, ledgy rock less,
    cliff rock (>= 62 degrees) 0.02: bare walls do not creep."""
    t = math.tan(math.radians(sc_deg))
    lo, hi = math.tan(math.radians(35.0)), math.tan(math.radians(62.0))
    return float(min(1.0, max(0.02, (hi - t) / (hi - lo))))


def _layer_dict(row):
    if isinstance(row, dict):
        d = dict(row)
    else:
        row = list(row)
        d = dict(thickness_m=row[0], K_factor=row[1], Sc_deg=row[2], colour=row[3] if len(row) > 3 else None,
                 name=row[4] if len(row) > 4 else f'layer {row[3] if len(row) > 3 else ""}')
    for k in ('thickness_m', 'K_factor', 'Sc_deg'):
        if k not in d:
            raise ValueError(f'a column layer needs {k}: {row}')
    d['thickness_m'] = float(d['thickness_m'])
    d['K_factor'] = float(d['K_factor'])
    d['Sc_deg'] = float(d['Sc_deg'])
    if d['thickness_m'] <= 0 or d['K_factor'] <= 0 or not (5.0 <= d['Sc_deg'] <= 89.0):
        raise ValueError(f'column layer {d.get("name")!r}: thickness and K factor must be positive, Sc 5-89 degrees')
    d.setdefault('name', 'layer')
    d['colour'] = d.get('colour') or str(d['name']).split()[0].lower()
    d.setdefault('creep', default_creep(d['Sc_deg']))
    return d


class Column:
    """A stratigraphic column (the module doc): .layers (formations, bottom to top, with base_m and top_m), .fine
    (the beds every table reads), .top_m, and the tables .z0, .dz, .K, .tan, .creep, .R (n,) float64."""

    def __init__(self, layers, name='custom', dz=DZ, seed=0):
        self.name = name
        self.dz = float(dz)
        self.layers = []
        z = 0.0
        for row in layers:
            d = _layer_dict(row)
            d['base_m'], d['top_m'] = z, z + d['thickness_m']
            z = d['top_m']
            self.layers.append(d)
        if not self.layers:
            raise ValueError('a column needs at least one layer')
        self.top_m = z
        rng = np.random.default_rng(int(seed) * 977 + sum(ord(c) for c in str(name)) % 7919)
        fine = []                                     # (bottom, top, K, tan, creep, formation index)
        for i, d in enumerate(self.layers):
            b, t = d['base_m'], d['top_m']
            beds = d.get('beds')
            base = (d['K_factor'], math.tan(math.radians(d['Sc_deg'])), d['creep'])
            if not beds:
                fine.append((b, t) + base + (i,))
                continue
            per = float(beds.get('period_m', 10.0))
            frac = float(beds.get('ledge_frac', 0.4))
            jit = float(beds.get('jitter', 0.3))
            led = (float(beds.get('ledge_K_factor', 0.3)), math.tan(math.radians(float(beds.get('ledge_Sc_deg', 70.0)))),
                   default_creep(float(beds.get('ledge_Sc_deg', 70.0))))
            zz = b
            while zz < t - 1e-9:
                p = per * float(np.exp(jit * rng.standard_normal()))
                lf = float(np.clip(frac * (1.0 + 0.5 * jit * rng.standard_normal()), 0.08, 0.9))
                z1 = min(zz + p * (1.0 - lf), t)
                if z1 > zz:
                    fine.append((zz, z1) + base + (i,))
                z2 = min(z1 + p * lf, t)
                if z2 > z1:
                    fine.append((z1, z2) + led + (i,))
                zz = z2
        self.fine = fine
        self.z0 = -PAD_M
        n = int(math.ceil((self.top_m + 2.0 * PAD_M) / self.dz)) + 1
        z = self.z0 + np.arange(n) * self.dz
        self.zs = z
        bot = np.array([f[0] for f in fine])
        idx = np.clip(np.searchsorted(bot, np.clip(z, 0.0, self.top_m - 1e-9), side='right') - 1, 0, len(fine) - 1)
        self.K = np.array([fine[i][2] for i in idx])
        self.tan = np.array([fine[i][3] for i in idx])
        self.creep = np.array([fine[i][4] for i in idx])
        self.formation = idx
        # R exactly at the samples: the run through every fine layer below, the end layers continuing past the ends
        edges = np.array([f[0] for f in fine] + [fine[-1][1]])
        inv = np.array([1.0 / f[3] for f in fine])
        cum = np.concatenate([[0.0], np.cumsum(np.diff(edges) * inv)])
        zc = np.clip(z, 0.0, self.top_m)
        k = np.clip(np.searchsorted(edges, zc, side='right') - 1, 0, len(fine) - 1)
        R = cum[k] + (zc - edges[k]) * inv[k]
        R = R + np.where(z < 0.0, z * inv[0], 0.0) + np.where(z > self.top_m, (z - self.top_m) * inv[-1], 0.0)
        self.R = R

    # -------------------------------------------------------------------------------------- lookups (twins) ---
    def _t(self, zs):
        return np.clip((np.asarray(zs, np.float64) - self.z0) / self.dz, 0.0, len(self.zs) - 1.0)

    def _lerp(self, table, zs):
        t = self._t(zs)
        i0 = np.floor(t).astype(np.int64)
        i1 = np.minimum(i0 + 1, len(table) - 1)
        f = t - i0
        return table[i0] * (1.0 - f) + table[i1] * f

    def k_at(self, zs):
        return self._lerp(self.K, zs)

    def tan_at(self, zs):
        return self._lerp(self.tan, zs)

    def creep_at(self, zs):
        return self._lerp(self.creep, zs)

    def run_at(self, zs):
        """R(zs), linearly continued past the table (as the kernel)."""
        zs = np.asarray(zs, np.float64)
        t = (zs - self.z0) / self.dz
        n = len(self.R)
        lo = self.R[0] + t * (self.R[1] - self.R[0])
        hi = self.R[-1] + (t - (n - 1)) * (self.R[-1] - self.R[-2])
        return np.where(t <= 0, lo, np.where(t >= n - 1, hi, self._lerp(self.R, zs)))

    def layer_at(self, zs):
        """The formation's name at a stratigraphic height."""
        z = float(np.clip(zs, 0.0, self.top_m - 1e-9))
        for d in self.layers:
            if d['base_m'] <= z < d['top_m']:
                return d['name']
        return self.layers[-1]['name']

    def base_of(self, name):
        for d in self.layers:
            if d['name'] == name or str(d['name']).lower().startswith(str(name).lower()):
                return d['base_m']
        raise KeyError(f'column {self.name!r} has no layer {name!r}; layers: {[d["name"] for d in self.layers]}')

    def top_of(self, name):
        for d in self.layers:
            if d['name'] == name or str(d['name']).lower().startswith(str(name).lower()):
                return d['top_m']
        raise KeyError(f'column {self.name!r} has no layer {name!r}; layers: {[d["name"] for d in self.layers]}')

    def formations(self):
        """The design's form, bottom to top from zs = 0: [(thickness_m, K_factor, Sc_deg, colour_id, name), ...]."""
        return [(d['thickness_m'], d['K_factor'], d['Sc_deg'], d['colour'], d['name']) for d in self.layers]

    def table_texture(self):
        """(1, n, 4) float32: tan, creep factor, R, K factor (strata_cell, strata_threshold)."""
        return np.stack([self.tan, self.creep, self.R, self.K], 1).astype(F32)[None, :, :]

    def describe(self):
        lines = [f'column {self.name}: {self.top_m:g} m, {len(self.layers)} formations, {len(self.fine)} beds']
        for d in reversed(self.layers):
            lines.append(f"  {d['top_m']:7.1f} m  {d['name']:<36} {d['thickness_m']:6.1f} m  K x{d['K_factor']:<5g} "
                         f"{d['Sc_deg']:4.0f} deg  creep {d['creep']:.2f}" + ('  (ledges)' if d.get('beds') else ''))
        return '\n'.join(lines)

    def __repr__(self):
        return f'Column({self.name!r}, {self.top_m:g} m, {len(self.layers)} formations)'


_COLUMN_CACHE = {}


def column(spec, dz=DZ, seed=0):
    """A Column from a COLUMNS name, a list of layers (bottom to top), or a Column (cached per spec)."""
    if isinstance(spec, Column):
        return spec
    if isinstance(spec, dict) and 'layers' in spec:
        name, layers = spec.get('name', 'custom'), spec['layers']
    elif isinstance(spec, str):
        if spec not in COLUMNS:
            import difflib
            near = difflib.get_close_matches(spec, list(COLUMNS), n=3, cutoff=0.4)
            raise KeyError(f'no column {spec!r}' + (f'; nearest: {", ".join(near)}' if near else
                                                    f'; columns: {", ".join(sorted(COLUMNS))}'))
        name, layers = spec, COLUMNS[spec]
    else:
        name, layers = 'custom', spec
    key = (repr(layers), float(dz), int(seed), name)
    if key not in _COLUMN_CACHE:
        _COLUMN_CACHE[key] = Column(layers, name, dz, seed)
    return _COLUMN_CACHE[key]


# ======================================================================================= where the beds sit ===

STRATA_DEFAULTS = dict(column='colorado_plateau', zs0_m=0.0, dip_deg=0.0, azimuth_deg=0.0, warp=(), faults=(),
                       fold=None, dz_m=DZ, seed=0)


def strata_spec(params):
    d = dict(STRATA_DEFAULTS)
    d.update({k: v for k, v in (params or {}).items() if k in STRATA_DEFAULTS})
    return d


def _fault_drop(f, x, y):
    """0..1 on the downthrown side of a fault line (C1 across width_m)."""
    ax, ay = (float(v) for v in f.get('at', (0.0, 0.0)))
    s = math.radians(float(f.get('strike_deg', 0.0)))            # compass strike
    ux, uy = math.sin(s), math.cos(s)
    side = (x - ax) * (-uy) + (y - ay) * ux                      # > 0 left of the strike direction
    if f.get('down', 'left') == 'right':
        side = -side
    w = max(float(f.get('width_m', 20.0)), 1e-6)
    t = np.clip(side / w + 0.5, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def offset(spec, level, seed=0, dev=None):
    """zoff = h - zs on a level's cells (float64): -zs0 + tan(dip) (x cos az + y sin az) + warp - throws."""
    sp = strata_spec(spec)
    x, y = level.xy()
    az = math.radians(float(sp['azimuth_deg']))
    out = -float(sp['zs0_m']) + math.tan(math.radians(float(sp['dip_deg']))) * (x * math.cos(az) + y * math.sin(az))
    s = int(seed) + int(sp.get('seed', 0))
    for k, (wl, amp) in enumerate(sp.get('warp') or ()):
        if float(amp) == 0.0:
            continue
        f = FL._field({'kind': 'fbm', 'wavelength_m': float(wl), 'octaves': 3, 'seed': 501 + k}, level, s, dev)
        out = out + 3.0 * float(amp) * f                       # fbm's standard deviation is 1/3
    for f in sp.get('faults') or ():
        out = out - float(f.get('throw_m', 0.0)) * _fault_drop(f, x, y)
    fd = sp.get('fold')
    if fd:
        # a fold along an axis: the beds rise rise_m at half_width_m from it (a syncline; negative: an anticline),
        # so a plateau following them drains toward the axis, over the escarpments that face it
        ax, ay = (float(v) for v in fd.get('through', (0.0, 0.0)))
        a = math.radians(float(fd.get('axis_deg', 0.0)))                    # compass
        d = (x - ax) * math.cos(a) - (y - ay) * math.sin(a)                  # across the axis (along sin a, cos a)
        out = out + float(fd.get('rise_m', 0.0)) * (d / max(float(fd.get('half_width_m', 4000.0)), 1.0)) ** 2
    return out


def zs_field(h, spec, level, seed=0, dev=None):
    return (np.asarray(h, np.float64) - offset(spec, level, seed, dev)).astype(F32)


# ================================================================================================ the twins ===

def _run_lookup(rtab_z, z, z0, dz):
    """strata_threshold.glsl run_at: R linearly interpolated, continued linearly past the ends (float32)."""
    n = rtab_z.shape[0]
    t = ((z - F32(z0)) / F32(dz)).astype(F32)
    tn = F32(n - 1)
    lo = rtab_z[0] + t * (rtab_z[1] - rtab_z[0])
    hi = rtab_z[n - 1] + (t - tn) * (rtab_z[n - 1] - rtab_z[n - 2])
    tc = np.clip(t, F32(0), tn)
    i0 = np.minimum(np.floor(tc).astype(np.int64), n - 2)
    f = (tc - i0.astype(F32)).astype(F32)
    mid = rtab_z[i0] * (F32(1) - f) + rtab_z[i0 + 1] * f
    return np.where(t <= 0, lo, np.where(t >= tn, hi, mid)).astype(F32)


# The facies noise (strata_threshold.glsl and STRATA_WEATHER's facies_noise): two octaves of trilinear value noise on
# the PCG lattice at (x / L, y / L, zs / Lz), about unit standard deviation; fac = (strength, L, Lz, seed). Each bed's
# strength varies along the wall and from bed to bed (rock_mass's n is one value through every bed at a place).
FACIES_GLSL = r'''
float lattice(ivec3 c, uint s) { return 2.0 * u01(pcg4(uint(c.x), uint(c.y), uint(c.z), s)) - 1.0; }
float vnoise3(vec3 q, uint s) {
  vec3 i = floor(q);
  vec3 f = q - i;
  vec3 u = f * f * (3.0 - 2.0 * f);
  ivec3 c = ivec3(i);
  float a = mix(lattice(c, s), lattice(c + ivec3(1, 0, 0), s), u.x);
  float b = mix(lattice(c + ivec3(0, 1, 0), s), lattice(c + ivec3(1, 1, 0), s), u.x);
  float d = mix(lattice(c + ivec3(0, 0, 1), s), lattice(c + ivec3(1, 0, 1), s), u.x);
  float e = mix(lattice(c + ivec3(0, 1, 1), s), lattice(c + ivec3(1, 1, 1), s), u.x);
  return mix(mix(a, b, u.y), mix(d, e, u.y), u.z);
}
float facies_noise(vec2 xy, float zs, vec4 fac) {
  vec3 q = vec3(xy / fac.y, zs / fac.z);
  uint s = uint(fac.w);
  return (vnoise3(q, s) + 0.5 * vnoise3(2.0 * q + vec3(17.3), s + 1u)) * 2.2;
}
'''
FACIES_OFF = (0.0, 1.0, 1.0, 0.0)


def _vnoise3(qx, qy, qz, s):
    ix, iy, iz = np.floor(qx), np.floor(qy), np.floor(qz)
    fx, fy, fz = (qx - ix).astype(F32), (qy - iy).astype(F32), (qz - iz).astype(F32)
    ux, uy, uz = (f * f * (F32(3) - F32(2) * f) for f in (fx, fy, fz))
    cx, cy, cz = ix.astype(np.int64), iy.astype(np.int64), iz.astype(np.int64)

    def lat(dx, dy, dz):
        return (F32(2) * T.u01(T.pcg4(cx + dx, cy + dy, cz + dz, s)) - F32(1)).astype(F32)

    def mix(a, b, t):
        return (a * (F32(1) - t) + b * t).astype(F32)
    a = mix(lat(0, 0, 0), lat(1, 0, 0), ux)
    b = mix(lat(0, 1, 0), lat(1, 1, 0), ux)
    d = mix(lat(0, 0, 1), lat(1, 0, 1), ux)
    e = mix(lat(0, 1, 1), lat(1, 1, 1), ux)
    return mix(mix(a, b, uy), mix(d, e, uy), uz)


def facies_noise(x, y, zs, fac):
    """The facies noise at world (x, y) and stratigraphic height zs (float32 arrays), fac = (strength, L, Lz, seed):
    the kernels' facies_noise."""
    fac = np.asarray(fac, F32)
    qx, qy = (np.asarray(x, F32) / fac[1]).astype(F32), (np.asarray(y, F32) / fac[1]).astype(F32)
    qz = (np.asarray(zs, F32) / fac[2]).astype(F32)
    s = int(fac[3])
    o = F32(17.3)
    n1 = _vnoise3(qx, qy, qz, s)
    n2 = _vnoise3((F32(2) * qx + o).astype(F32), (F32(2) * qy + o).astype(F32), (F32(2) * qz + o).astype(F32),
                  s + 1)
    return ((n1 + F32(0.5) * n2) * F32(2.2)).astype(F32)


FACIES_DEFAULTS = dict(strength=0.5, scale_m=300.0, scale_z_m=40.0, weather=0.5, seed=0)


def facies_spec(spec, seed=0):
    """(the threshold's facies, the weathering's facies) as the kernels' uniforms (strength, L, Lz, seed) from a
    'strata_fluvial' stage's `facies` dict ({'strength', 'scale_m', 'scale_z_m', 'weather', 'seed'}; None: both
    FACIES_OFF). The same noise drives both, so a weak facies both lies back and wears back."""
    if not spec:
        return FACIES_OFF, FACIES_OFF
    p = dict(FACIES_DEFAULTS)
    p.update(spec)
    sd = float((int(seed) * 7 + int(p['seed']) + 9001) % 65536)
    L, Lz = float(p['scale_m']), float(p['scale_z_m'])
    return (float(p['strength']), L, Lz, sd), (float(p['weather']), L, Lz, sd)


def facies_factor(level, zs, fac):
    """exp(-strength x facies_noise) on a level's cells at stratigraphic heights zs (float64; 1 with no facies)."""
    if not fac or float(fac[0]) <= 0.0:
        return np.ones(np.shape(zs))
    x, y = T.world_xy(np.shape(zs), (level.x0, level.y0, level.cell))
    return np.exp(-float(fac[0]) * facies_noise(x, y, np.asarray(zs, F32), fac).astype(np.float64))


@T.twin('strata_threshold')
def strata_threshold(s, u):
    h = s['st'][..., 0]
    bound = u['uBound']

    def ax(k):
        v, ok = T.neighbour(h, k, bound)
        return np.where(ok, v, h)
    gx = np.maximum(h - np.minimum(ax(3), ax(4)), F32(0))
    gy = np.maximum(h - np.minimum(ax(1), ax(6)), F32(0))
    span = np.sqrt(gx * gx + gy * gy).astype(F32)
    zs = (h - s['zoff'][..., 0]).astype(F32)
    L = np.maximum(s['mk'][..., 3], F32(0))
    rt = s['rtab'][0, :, 2]
    z0, dz = u['uRZ0'], u['uRDz']
    dR = (np.minimum(span, L) / u['uRepose']).astype(F32)
    rock = (_run_lookup(rt, (zs - L).astype(F32), z0, dz) - _run_lookup(rt, (zs - span).astype(F32), z0, dz))
    q = s['par'][..., 2]                                         # the rock mass's run factor
    fac = np.asarray(u['uFac'], F32)
    if fac[0] > 0:                                              # the facies
        x, y = T.world_xy(h.shape, u['uLv'])
        q = (q * np.exp(-fac[0] * facies_noise(x, y, zs, fac))).astype(F32)
    rock = (q * rock).astype(F32)
    dR = np.where(span > L, dR + rock, dR).astype(F32)
    with np.errstate(divide='ignore', invalid='ignore'):
        phi = np.where((span > 0) & (dR > u['uDx']), F32(1) - u['uDx'] / np.where(dR > 0, dR, F32(1)), F32(0))
    return {'outP': phi.astype(F32)[..., None]}


# Per cell, once a step: the layer's own threshold and creep factor at the cell's current height (strata_creep reads
# them for the cell and its 8 neighbours; looking them up there cost 9 table reads a neighbour pair).
STRATA_CELL = FL.Inline('strata_cell', r'''//! sampler st     x: h (m)
//! sampler zoff   x: z - zs (m)
//! sampler ctab   x: tan(theta), y: creep factor (1 row of uTN texels from uTZ0 every uTDz metres)
//! image   outC rg32f   x: tan(theta) of the layer at the cell's zs, y: its creep factor
//! uniform float uTZ0
//! uniform float uTDz
//! uniform int uTN
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float zs = texelFetch(st, p, 0).x - texelFetch(zoff, p, 0).x;
  float t = clamp((zs - uTZ0) / uTDz, 0.0, float(uTN - 1));
  int i0 = min(int(floor(t)), uTN - 2);
  float f = t - float(i0);
  vec2 a = texelFetch(ctab, ivec2(i0, 0), 0).xy;
  vec2 b = texelFetch(ctab, ivec2(i0 + 1, 0), 0).xy;
  imageStore(outC, p, vec4(mix(a, b, f), 0.0, 0.0));
}
''')

# creep.glsl on soft rock only: the pair's threshold is the mean of its cells' layer tangents, its diffusivity the
# smaller of their creep factors (a cliff's rock does not creep; a shale slope and its talus do).
STRATA_CREEP = FL.Inline('strata_creep', r'''//! sampler st     x: h (m); y, z, w carried
//! sampler cell   x: tan(theta), y: creep factor (strata_cell)
//! sampler pin    x: pin_w, y: pin_h
//! image   outS rgba32f
//! uniform float uDx
//! uniform float uDtSub
//! uniform float uD
//! uniform float uCap
//! uniform int uBound
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float h = c.x;
  vec2 cc = texelFetch(cell, p, 0).xy;
  float acc = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float hq = texelFetch(st, q, 0).x;
    vec2 cq = texelFetch(cell, q, 0).xy;
    float scp = 0.5 * (cc.x + cq.x);
    float r = ((hq - h) / (LEN[k] * uDx)) / scp;
    float f = min(1.0 / max(1.0 - r * r, 1e-9), uCap);
    acc += WISO[k] * f * min(cc.y, cq.y) * (hq - h);
  }
  float hn = h + uDtSub * uD * acc / (uDx * uDx);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    hn = pin_apply(hn, pn.x, pn.y);
  }
  imageStore(outS, p, vec4(hn, c.y, c.z, c.w));
}
''')


# Weathering (the scarp-retreat process): exposed rock wears back at a rate set by its layer and the slope, whatever
# drains across it. The stream-power term needs drainage area, so on hillslopes it is weak: a weak layer once at its
# threshold angle never retreated, the cliffs above it never failed, and no bench widened (the Esplanade platform is
# 45 % of Toroweap's tile). Here a cell lowers by
#     E = uW f (K / uK0) min(G / uS0, uSat),   f = the column's K factor at its zs (loose cover: uLoose)
# G the upwind gradient magnitude (strata_threshold's), never below its lowest neighbour (no pits). Linear in G (uSat
# large, the default) it is a level-set motion: every contour retreats uW f / uS0 metres a year horizontally, at any
# slope, in every direction and at every cell size. (Saturated at G = uS0, uSat 1, a cliff cell lowered at a fixed
# rate whatever its height, so a cliff retreated a cell per (height / rate): faster on coarse levels, and faster
# where the grid made its step one cell (axis-aligned) than two (diagonal): the walls ran in straight 0- and
# 45-degree segments.) Shale under a cliff wears back fast, the cliff above fails over it (the composite threshold),
# the strong bed below stays a bench; gentle ground barely wears (the plateau and the benches stay flat). The fine
# debris leaves (suspended load).
STRATA_WEATHER = FL.Inline('strata_weather', r'''//! sampler st     x: h (m); y, z, w carried
//! sampler zoff   x: z - zs (m)
//! sampler ctab   w: the column's K factor (1 row of uTN texels from uTZ0 every uTDz metres)
//! sampler par    y: K, the erodibility field (its noise varies the weathering alike)
//! sampler pin    x: pin_w, y: pin_h
//! sampler mk     x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outS rgba32f
//! image   outM rgba32f
//! uniform float uDx
//! uniform float uDt
//! uniform float uW      lowering rate (m/yr) of K-factor-1 rock on a slope of uS0 or steeper
//! uniform float uS0     tan of the slope at which the rate is uW
//! uniform float uSat    the slope term's cap, G / uS0 <= uSat (large: linear; 1: the old saturated law)
//! uniform float uK0     the stage's K: the field's noise is K / uK0
//! uniform float uWl     lowering rate (m/yr) of loose cover: debris washes away
// (on the refining passes the rock rate is off and only uWl runs, so failed debris does not drape the cliffs below)
//! uniform float uAc     the drainage-area boost: x (1 + uAc min(sqrt(A / 1e5 m^2), 30) r), A = st.y
//! uniform float uAs0    r: 0 at this gradient (tan) and below ...
//! uniform float uAs1    ... 1 at this one and above: runoff gathering at a scarp (amphitheatres, a fraying
// escarpment) speeds its retreat; on gentle ground (benches, a desert floor) the gathered runoff is the stream-power
// incision's, not the scarp's (boosted there, every wash lowered its floor into a valley: Monument Valley's floor
// sank 60 m into the Cedar Mesa sandstone it is stripped to, and lost its westward rise)
//! uniform float uTZ0
//! uniform float uTDz
//! uniform int uTN
//! uniform vec3 uLv      the level: x0, y0, cell (m), for the cell's world position
//! uniform vec4 uFacW    the facies (strength, horizontal and vertical wavelength m, seed; strength 0: off): the
// rock's rate x exp(-strength facies_noise), so weak facies wear back into alcoves and strong ones stand as buttresses
//! uniform int uBound
''' + FACIES_GLSL + r'''
float axis_h(ivec2 p, int k, ivec2 n, float h) {
  ivec2 q;
  return neighbour(p, k, n, uBound, q) ? texelFetch(st, q, 0).x : h;
}
/* q >= 0 metres taken off the top of the layers m: deposit, then talus, then other loose cover, then rock (wear) */
vec4 take(vec4 m, float q) {
  float other = max(m.w - m.y - m.z, 0.0);
  float r = q;
  float a = min(r, m.y);
  m.y -= a;
  r -= a;
  a = min(r, m.z);
  m.z -= a;
  r -= a;
  r -= min(r, other);
  m.w = max(m.w - (q - r), 0.0);
  m.x += r;
  return m;
}
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float h = c.x;
  float gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  float gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  float G = sqrt(gx * gx + gy * gy) / uDx;
  float hlow = h;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (neighbour(p, k, n, uBound, q)) hlow = min(hlow, texelFetch(st, q, 0).x);
  }
  float zs = h - texelFetch(zoff, p, 0).x;
  float t = clamp((zs - uTZ0) / uTDz, 0.0, float(uTN - 1));
  int i0 = min(int(floor(t)), uTN - 2);
  float kf = mix(texelFetch(ctab, ivec2(i0, 0), 0).w, texelFetch(ctab, ivec2(i0 + 1, 0), 0).w, t - float(i0));
  vec4 m = texelFetch(mk, p, 0);
  float w = clamp(max(m.w, 0.0), 0.0, 1.0);
  if (uFacW.x > 0.0) kf *= exp(-uFacW.x * facies_noise(world_xy(p, uLv), zs, uFacW));
  float rate = mix(uW * kf, uWl, w);
  float ramp = clamp((G - uAs0) / max(uAs1 - uAs0, 1e-6), 0.0, 1.0);
  float boost = 1.0 + uAc * min(sqrt(max(c.y, 0.0) / 1e5), 30.0) * ramp;
  float E = rate * (texelFetch(par, p, 0).y / uK0) * min(G / uS0, uSat) * boost;
  float hn = max(h - uDt * E, min(h, hlow));
  m = take(m, h - hn);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    float hp = pin_apply(hn, pn.x, pn.y);
    float d = hp - hn;
    if (d >= 0.0) {
      m.y += d;
      m.w += d;
    } else {
      m = take(m, -d);
    }
    hn = hp;
  }
  imageStore(outS, p, vec4(hn, c.y, c.z, c.w));
  imageStore(outM, p, m);
}
''')


def _take(wear, dep, tal, loose, q):
    """STRATA_WEATHER's take(): q >= 0 metres off the top of the layers (deposit, talus, other loose cover, rock)."""
    other = np.maximum(loose - dep - tal, F32(0))
    r = q
    a = np.minimum(r, dep)
    dep = dep - a
    r = r - a
    a = np.minimum(r, tal)
    tal = tal - a
    r = r - a
    r = r - np.minimum(r, other)
    loose = np.maximum(loose - (q - r), F32(0))
    return wear + r, dep, tal, loose


@T.twin('strata_weather')
def strata_weather(s, u):
    st, mk = s['st'], s['mk']
    h = st[..., 0]
    bound = u['uBound']

    def ax(k):
        v, ok = T.neighbour(h, k, bound)
        return np.where(ok, v, h)
    gx = np.maximum(h - np.minimum(ax(3), ax(4)), F32(0))
    gy = np.maximum(h - np.minimum(ax(1), ax(6)), F32(0))
    G = (np.sqrt(gx * gx + gy * gy) / u['uDx']).astype(F32)
    hlow = h.copy()
    for k in range(8):
        v, ok = T.neighbour(h, k, bound)
        hlow = np.where(ok, np.minimum(hlow, v), hlow)
    zs = (h - s['zoff'][..., 0]).astype(F32)
    tab = s['ctab'][0, :, 3]
    nt = int(u['uTN'])
    t = np.clip((zs - u['uTZ0']) / u['uTDz'], F32(0), F32(nt - 1)).astype(F32)
    i0 = np.minimum(np.floor(t).astype(np.int64), nt - 2)
    fr = (t - i0.astype(F32)).astype(F32)
    kf = tab[i0] * (F32(1) - fr) + tab[i0 + 1] * fr
    w = np.clip(np.maximum(mk[..., 3], F32(0)), F32(0), F32(1))
    fac = np.asarray(u['uFacW'], F32)
    if fac[0] > 0:                                              # the facies
        x, y = T.world_xy(h.shape, u['uLv'])
        kf = (kf * np.exp(-fac[0] * facies_noise(x, y, zs, fac))).astype(F32)
    rate = (u['uW'] * kf) * (F32(1) - w) + u['uWl'] * w
    ramp = np.clip((G - F32(u['uAs0'])) / F32(max(u['uAs1'] - u['uAs0'], 1e-6)), F32(0), F32(1))
    boost = F32(1) + u['uAc'] * np.minimum(np.sqrt(np.maximum(st[..., 1], F32(0)) / F32(1e5)), F32(30)) * ramp
    E = rate * (s['par'][..., 1] / u['uK0']) * np.minimum(G / u['uS0'], F32(u['uSat'])) * boost
    hn = np.maximum(h - u['uDt'] * E, np.minimum(h, hlow)).astype(F32)
    wear, dep, tal, loose = _take(mk[..., 0], mk[..., 1], mk[..., 2], mk[..., 3], (h - hn).astype(F32))
    if bound == T.BOUND_PINNED:
        pin = s['pin']
        hp = T.pin_apply(hn, pin[..., 0], pin[..., 1])
        d = (hp - hn).astype(F32)
        g = d >= 0
        w2, d2, t2, l2 = _take(wear, dep, tal, loose, np.maximum(-d, F32(0)))
        wear = np.where(g, wear, w2)
        dep = np.where(g, dep + d, d2)
        tal = np.where(g, tal, t2)
        loose = np.where(g, loose + d, l2)
        hn = hp
    return {'outS': T.rgba(hn, st[..., 1], st[..., 2], st[..., 3]), 'outM': T.rgba(wear, dep, tal, loose)}


@T.twin('strata_cell')
def strata_cell(s, u):
    zs = (s['st'][..., 0] - s['zoff'][..., 0]).astype(F32)
    tab = s['ctab'][0]
    n = int(u['uTN'])
    t = np.clip((zs - u['uTZ0']) / u['uTDz'], F32(0), F32(n - 1)).astype(F32)
    i0 = np.minimum(np.floor(t).astype(np.int64), n - 2)
    f = (t - i0.astype(F32)).astype(F32)[..., None]
    v = tab[i0, :2] * (F32(1) - f) + tab[i0 + 1, :2] * f
    return {'outC': v.astype(F32)}


@T.twin('strata_creep')
def strata_creep(s, u):
    st, cell, pin = s['st'], s['cell'], s['pin']
    h = st[..., 0]
    sc, cf = cell[..., 0], cell[..., 1]
    acc = np.zeros_like(h)
    for k in range(8):
        hq, ok = T.neighbour(h, k, u['uBound'])
        sq, _ = T.neighbour(sc, k, u['uBound'], fill=1.0)
        cq, _ = T.neighbour(cf, k, u['uBound'])
        scp = F32(0.5) * (sc + sq)
        r = ((hq - h) / (T.LEN[k] * u['uDx'])) / scp
        f = np.minimum(F32(1) / np.maximum(F32(1) - r * r, F32(1e-9)), u['uCap'])
        acc = acc + np.where(ok, T.WISO[k] * f * np.minimum(cf, cq) * (hq - h), F32(0))
    hn = h + u['uDtSub'] * u['uD'] * acc / (u['uDx'] * u['uDx'])
    if u['uBound'] == T.BOUND_PINNED:
        hn = T.pin_apply(hn, pin[..., 0], pin[..., 1])
    return {'outS': T.rgba(hn, st[..., 1], st[..., 2], st[..., 3])}


# =============================================================================================== the driver ===

def weather_table(col, k_exp=1.0):
    """The column's table texture (tan, creep, R, K factor) with the weathering's factor in its fourth channel (what
    STRATA_WEATHER reads; route_incise reads the K table on its own): the K factor, or K^k_exp where it is under 1.
    Massive cliff rock retreats by failing when the weak rock under it is cut back, not by its surface wearing down:
    with the K factor itself (k_exp 1) the Muav's cliffs (0.4) wore back 300 m over the canyon's run and the inner
    gorge became a 2 km trapezoid with a broad floor, where Toroweap's walls run steep to the river; k_exp 2 keeps soft
    rock's rate and slows the cliffs' (the Muav x0.16, the Redwall x0.04)."""
    t = col.table_texture()
    if float(k_exp) != 1.0:
        k = t[..., 3].astype(np.float64)
        t[..., 3] = np.where(k < 1.0, np.power(np.maximum(k, 0.0), float(k_exp)), k).astype(F32)
    return t


class StrataRun(FL.FluvialRun):
    """FluvialRun (solvers/fluvial.py) in layered rock: route_incise with the column's K(zs); creep through
    strata_cell + strata_creep; the threshold as strata_threshold's composite excess, then threshold.glsl's
    isotropic exchange; the lock as the stock driver's."""

    def __init__(self, dev, cell, fields, par, pins, col, zoff, lock_h0=None, lock_b=2, repose_tan=0.67,
                 weather=None, lv=(0.0, 0.0, 1.0), facies=FACIES_OFF, facies_w=FACIES_OFF, weather_k_exp=1.0):
        column = dict(k_factor=np.asarray(col.K, F32), zoff=np.asarray(zoff, F32), z0=col.z0, dz=col.dz)
        super().__init__(dev, cell, fields, par, pins, FL.PINNED, column, lock_h0, lock_b)
        self.column = col                              # (FluvialRun keeps the K table's (z0, dz, n) in self.col)
        self.ctab = dev.texture(weather_table(col, weather_k_exp))
        self.tcol = (float(col.z0), float(col.dz), int(len(col.R)))
        self.C = dev.empty(self.shape, 2)
        self.phiS = dev.empty(self.shape, 1)
        self.repose = float(repose_tan)
        # weathering: (rock rate W m/yr, tan of the slope it applies at, the stage's K0, the loose cover's rate m/yr,
        # the drainage-area boost, the slope term's cap, the boost's slope ramp (tan lo, tan hi)) or None
        self.weather = weather if weather and (float(weather[0]) > 0 or float(weather[3]) > 0) else None
        # the level's frame (x0, y0, cell) and the facies of the threshold and of the weathering (strength, L, Lz,
        # seed; FACIES_OFF: none)
        self.lv = tuple(float(v) for v in lv)
        self.facies = tuple(float(v) for v in facies)
        self.facies_w = tuple(float(v) for v in facies_w)

    def weather_pass(self, dt):
        if self.weather is None:
            return
        W, s0, k0, wl, ac, sat, (as0, as1) = self.weather
        z0, dz, nt = self.tcol
        self.dev.run(STRATA_WEATHER, {'st': self.S.src, 'zoff': self.zoff, 'ctab': self.ctab, 'par': self.P,
                                      'pin': self.Q, 'mk': self.M.src},
                     {'outS': self.S.dst, 'outM': self.M.dst},
                     {'uDx': self.cell, 'uDt': dt, 'uW': W, 'uS0': s0, 'uSat': sat, 'uK0': k0, 'uWl': wl,
                      'uAc': ac, 'uAs0': as0, 'uAs1': as1, 'uTZ0': z0, 'uTDz': dz, 'uTN': nt,
                      'uLv': self.lv, 'uFacW': self.facies_w, 'uBound': self.bound})
        self.S.swap()
        self.M.swap()

    def set_pins(self, pins):
        self.Q = self.dev.texture(T.rgba(pins['pin_w'], pins['pin_h'], pins['A_in'], pins['qs_in']))

    def threshold(self, iters, rate):
        dev, S, M, b = self.dev, self.S, self.M, self.bound
        z0, dz, nt = self.tcol
        for _ in range(iters):
            dev.run('strata_threshold', {'st': S.src, 'zoff': self.zoff, 'mk': M.src, 'rtab': self.ctab,
                                         'par': self.P},
                    {'outP': self.phiS}, {'uDx': self.cell, 'uRZ0': z0, 'uRDz': dz, 'uRN': nt,
                                          'uRepose': self.repose, 'uLv': self.lv, 'uFac': self.facies,
                                          'uBound': b})
            dev.run('threshold', {'st': S.src, 'par': self.P, 'pin': self.Q, 'mk': M.src, 'phiT': self.phiS},
                    {'outS': S.dst, 'outM': M.dst},
                    {'uDx': self.cell, 'uRate': rate, 'uLoose': 0, 'uIso': 1, 'uBound': b})
            S.swap()
            M.swap()

    def creep(self, dt, D, n_sub, cap):
        dev, S, M, b = self.dev, self.S, self.M, self.bound
        z0, dz, nt = self.tcol
        dev.run(STRATA_CELL, {'st': S.src, 'zoff': self.zoff, 'ctab': self.ctab}, {'outC': self.C},
                {'uTZ0': z0, 'uTDz': dz, 'uTN': nt})
        dev.run(FL.H_KEEP, {'st': S.src}, {'outH': self.W}, {})
        for _ in range(n_sub):
            dev.run(STRATA_CREEP, {'st': S.src, 'cell': self.C, 'pin': self.Q}, {'outS': S.dst},
                    {'uDx': self.cell, 'uDtSub': dt / n_sub, 'uD': D, 'uCap': cap, 'uBound': b})
            S.swap()
        dev.run(FL.CREEP_LAYERS, {'st': S.src, 'h0': self.W, 'mk': M.src}, {'outM': M.dst}, {})
        M.swap()

    def lock_pass(self, lock_gain=1.0):
        if self.lock is None:
            return
        dev, S, M = self.dev, self.S, self.M
        phases, R, stage1 = self.lock
        off, tgt = phases[self.steps % len(phases)]
        if stage1 is not None:
            b1, zero, R1 = stage1
            dev.run(FL.LOCK_RESTRICT, {'st': S.src, 'tgt': zero}, {'outR': R1}, {'uB': b1, 'uOff': (0, 0)})
            dev.run(FL.LOCK_RESTRICT, {'st': R1, 'tgt': tgt}, {'outR': R},
                    {'uB': self.lock_b // b1, 'uOff': (off[0] // b1, off[1] // b1)})
        else:
            dev.run(FL.LOCK_RESTRICT, {'st': S.src, 'tgt': tgt}, {'outR': R}, {'uB': self.lock_b, 'uOff': off})
        dev.run(FL.LOCK_APPLY, {'st': S.src, 'res': R, 'pin': self.Q, 'mk': M.src}, {'outS': S.dst, 'outM': M.dst},
                {'uGain': lock_gain, 'uB': self.lock_b, 'uOff': off})
        S.swap()
        M.swap()

    def step(self, dt, D, n_sub, iters, rate, cap, m=0.5, nexp=1.0, p=1.0, lock_gain=1.0, slope=1, iso=1,
             pit_fill=1, pit_eps=1e-3):
        dev, S, M, cell, b = self.dev, self.S, self.M, self.cell, self.bound
        dev.run('flow_weights', {'st': S.src}, {'outW': self.W}, {'uDx': cell, 'uP': p, 'uBound': b})
        z0, dz, nc = self.col
        dev.run('route_incise', {'st': S.src, 'wsumT': self.W, 'par': self.P, 'pin': self.Q, 'mk': M.src,
                                 'kcol': self.kcol, 'zoff': self.zoff},
                {'outS': S.dst, 'outM': M.dst},
                {'uDx': cell, 'uDt': dt, 'uM': m, 'uN': nexp, 'uP': p, 'uColZ0': z0, 'uColDz': dz, 'uColN': nc,
                 'uSlope': int(slope), 'uPitFill': int(pit_fill), 'uPitEps': pit_eps, 'uBound': b})
        S.swap()
        M.swap()
        self.weather_pass(dt)
        if D > 0 and n_sub > 0:
            self.creep(dt, D, n_sub, cap)
        self.threshold(iters, rate)
        self.lock_pass(lock_gain)
        self.steps += 1


# ================================================================================================== helpers ===

def caprock_fraction(h, zoff, level, main, cap_zs):
    """The share of the main window's cells (on `level`) whose stratigraphic height is at or above cap_zs."""
    j0, j1, i0, i1 = FL._main_window(level, main)
    zs = np.asarray(h, np.float64)[j0:j1, i0:i1] - np.asarray(zoff, np.float64)[j0:j1, i0:i1]
    return float(np.mean(zs >= float(cap_zs)))


def fill_dry_basins(fields, keep=None, hold=0):
    """Fill every closed depression of a level's surface that does not touch `keep` (a bool mask: the river's
    channel) with sediment, in place (h and deposit; the bed stays), never within `hold` cells of the edge (a child
    level's seam stays its parent's). A desert plateau's and bench's closed basins are dry sinks that sand and
    alluvium fill; the run's end stage holds every depression deeper than its threshold as a lake (with the recipe's
    lakes 'lake', kept for the river's pools), and without this Toroweap's Esplanade and plateau carried dozens of
    lakes. The river's pools touch its channel and stay basins (they hold its water). Returns the cells filled."""
    from ..core import grid as Gd
    from ..core import metrics as Mx
    from . import hydro as HY
    h = np.asarray(fields['h'], np.float64)
    filled, _info = HY.fill_depressions(h)
    depth = filled - h
    lab, n = Mx.label(depth > 1e-4)
    if not n:
        return 0
    kept = np.zeros(n + 1, bool)
    if keep is not None:
        k = np.asarray(keep, bool) & (lab > 0)
        if k.any():
            kept[np.unique(lab[k])] = True
    fill = (lab > 0) & ~kept[lab]
    if hold > 0:
        fill &= Gd.edge_distance(h.shape) >= hold
    if not fill.any():
        return 0
    add = np.where(fill, depth, 0.0)
    fields['h'] = (h + add).astype(F32)
    fields['deposit'] = (np.asarray(fields.get('deposit', np.zeros_like(h)), np.float64) + add).astype(F32)
    return int(fill.sum())


def _ring_inner(h):
    """(n, n): on the outer ring, the height of each ring cell's inward neighbour (the diagonal one at the corners);
    elsewhere h itself."""
    h = np.asarray(h, F32)
    out = h.copy()
    out[0, 1:-1], out[-1, 1:-1] = h[1, 1:-1], h[-2, 1:-1]
    out[1:-1, 0], out[1:-1, -1] = h[1:-1, 1], h[1:-1, -2]
    out[0, 0], out[0, -1], out[-1, 0], out[-1, -1] = h[1, 1], h[1, -2], h[-2, 1], h[-2, -2]
    return out


def _strata_of(params, ctx):
    spec = (params or {}).get('strata') or (ctx.shared.get('strata') if ctx is not None else None)
    if spec is None:
        raise ValueError("no strata column: put a 'strata' stage before this one (or give params['strata'])")
    return strata_spec(spec)


def joint_field(level, sets, seed=0, dev=None):
    """Joint-guided weakness, 0..1 on a level's cells (float64): for each set {'strike_deg' (compass: the lines'
    direction), 'spacing_m', 'width_m' (the weathered zone; at least 1.5 cells, so coarse levels see a fuzzy band),
    'wiggle_m' (the lines' waver, default 0.15 spacing), 'segment_m' (the length over which a line fades in and
    out, default 3 spacings), 'strength' (1)} a Gaussian ridge along every line, broken into segments; the sets
    combine by max. The layered-rock stage multiplies K by (1 + joint_gain x this): incision and weathering run
    faster along the joints, so escarpments fray into fingers and blocks with straight sides, and promontories part
    into mesas and buttes along them."""
    x, y = level.xy()
    out = np.zeros((level.n, level.n))
    for k, js in enumerate(sets or ()):
        spacing = max(float(js.get('spacing_m', 500.0)), 4.0 * level.cell)
        a = math.radians(float(js.get('strike_deg', 0.0)))
        u = (x * math.cos(a) - y * math.sin(a)) / spacing           # across the lines (they run along sin a, cos a)
        wig = float(js.get('wiggle_m', 0.15 * spacing))
        if wig:
            u = u + 3.0 * wig / spacing * FL._field({'kind': 'fbm', 'wavelength_m': 2.0 * spacing, 'octaves': 3,
                                                     'seed': 701 + 13 * k}, level, seed, dev)
        d = np.abs(u - np.round(u)) * spacing
        w = max(float(js.get('width_m', 20.0)), 1.5 * level.cell)
        line = np.exp(-(d / w) ** 2)
        seg = FL._field({'kind': 'fbm', 'wavelength_m': float(js.get('segment_m', 3.0 * spacing)), 'octaves': 2,
                         'seed': 733 + 13 * k}, level, seed, dev)
        seg = np.clip((seg + 0.15) / 0.3, 0.0, 1.0)
        out = np.maximum(out, float(js.get('strength', 1.0)) * line * seg)
    return out


def rock_mass(level, scales, seed=0, dev=None):
    """The rock mass's strength as a function of world position, n about N(0, 1) (float64, clipped at +-2.5): fbm
    at each of `scales` (metres) the level resolves (3 cells and up), every scale with the same weight on every level
    (a coarse level lacks the fine scales, it does not reweight the coarse ones). Positive is strong rock: fewer
    joints, thicker beds, no alteration. 'strata_fluvial' multiplies the erodibility (incision and weathering) by
    exp(-resist n) and the composite threshold's run of rock by exp(-resist_run n): strong spots stand as sheer
    buttresses and promontories, weak ones wear back into chutes and embayments, so a wall is a mosaic of cliffs,
    ledges and talus at every height instead of one ramp at the column's angle."""
    sc = [float(s) for s in (scales or ())]
    if not sc:
        return None
    amp = 3.0 / math.sqrt(len(sc))                      # fbm's standard deviation is 1/3: unit variance in all
    out = np.zeros((level.n, level.n))
    used = 0
    for k, wl in enumerate(sc):
        if wl < 3.0 * level.cell:
            continue
        out = out + amp * FL._field({'kind': 'fbm', 'wavelength_m': wl, 'octaves': 2, 'seed': 811 + 7 * k},
                                    level, seed, dev)
        used += 1
    if not used:
        return None
    return np.clip(out, -2.5, 2.5)


CORES_DEFAULTS = dict(spacing_m=1800.0, radius_m=(200.0, 420.0), elongation=(1.0, 2.2), angles_deg=None,
                      strength=2.5, region_m=40000.0, seed=0, exponent=4.0, wobble=0.0)


def core_centres(spec, seed=0):
    """The strong cores' centres and shapes, world metres: [(x, y, a, b, angle_rad, strength)], blue noise (dart
    throwing at spacing_m over a square region_m wide around the origin), the same on every level of a terrain."""
    p = dict(CORES_DEFAULTS)
    p.update(spec or {})
    sp = float(p['spacing_m'])
    half = 0.5 * float(p['region_m'])
    rng = np.random.default_rng((int(seed) + int(p['seed'])) * 7919 + 4243)
    cand = rng.uniform(-half, half, (int(25 * (2 * half / sp) ** 2), 2))
    gcell = sp / math.sqrt(2.0)
    grid = {}
    out = []
    r0, r1 = (float(v) for v in p['radius_m'])
    e0, e1 = (float(v) for v in p['elongation'])
    angles = p.get('angles_deg')
    for x, y in cand:
        gi, gj = int(math.floor(x / gcell)), int(math.floor(y / gcell))
        ok = True
        for di in (-2, -1, 0, 1, 2):
            for dj in (-2, -1, 0, 1, 2):
                q = grid.get((gi + di, gj + dj))
                if q is not None and (q[0] - x) ** 2 + (q[1] - y) ** 2 < sp * sp:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        grid[(gi, gj)] = (x, y)
        r = rng.uniform(r0, r1)
        e = rng.uniform(e0, e1)
        if angles:
            ang = math.radians(float(angles[int(rng.integers(len(angles)))]) + rng.uniform(-12.0, 12.0))
        else:
            ang = rng.uniform(0.0, math.pi)
        out.append((float(x), float(y), r * math.sqrt(e), r / math.sqrt(e), ang,
                    float(p['strength']) * rng.uniform(0.75, 1.25)))
    return out


def rock_cores(level, spec, seed=0):
    """Strong cores of the rock mass (n units, float64, or None): each a rounded block (a superellipse of power
    `exponent`, semi-axes a and b along its compass angle) of strength n, flat inside, falling off over about a
    tenth of its size, its outline wobbling by +-`wobble` of its radius (a world-space noise at about 0.7 of its
    width, so no two cores share a shape). Where the caprock is less jointed (Monument Valley's buttes stand where the
    De Chelly is massive), the retreating escarpment leaves the cores standing as buttes and mesas. (Power 4 with no
    wobble made square blocks whose walls faced four ways only: the field's 4-fold aspect harmonic was 8 x Monument
    Valley's.)"""
    if not spec:
        return None
    p = dict(CORES_DEFAULTS)
    p.update(spec)
    pw = max(float(p['exponent']), 1.0)
    wob = float(p['wobble'])
    x, y = level.xy()
    out = np.zeros((level.n, level.n))
    for k, (cx, cy, a, b, ang, s) in enumerate(core_centres(spec, seed)):
        reach = 1.6 * (1.0 + wob) * max(a, b)
        if (cx + reach < level.x0 or cx - reach > level.x0 + level.side or cy + reach < level.y0
                or cy - reach > level.y0 + level.side):
            continue
        i0 = max(int((cx - reach - level.x0) / level.cell), 0)
        i1 = min(int((cx + reach - level.x0) / level.cell) + 1, level.n)
        j0 = max(int((cy - reach - level.y0) / level.cell), 0)
        j1 = min(int((cy + reach - level.y0) / level.cell) + 1, level.n)
        if i1 <= i0 or j1 <= j0:
            continue
        dx = x[j0:j1, i0:i1] - cx
        dy = y[j0:j1, i0:i1] - cy
        u = dx * math.sin(ang) + dy * math.cos(ang)              # along the compass angle
        v = dx * math.cos(ang) - dy * math.sin(ang)
        d = (np.abs(u / a) ** pw + np.abs(v / b) ** pw) ** (1.0 / pw)
        if wob > 0.0:
            # the outline's wobble: a smooth world-space noise sampled on this core's box (seeded per core)
            d = d / np.maximum(1.0 + wob * _box_noise(x[j0:j1, i0:i1], y[j0:j1, i0:i1], 0.7 * (a + b),
                                                      int(seed) * 131 + 977 * k + 5), 0.3)
        out[j0:j1, i0:i1] = np.maximum(out[j0:j1, i0:i1], s * np.exp(-d ** 8))
    return out


def _box_noise(x, y, wavelength, seed):
    """A smooth noise of about unit amplitude on world points (x, y arrays): a few random plane waves at about
    `wavelength` metres (numpy only; for small boxes, where a level-wide fbm would be wasted)."""
    rng = np.random.default_rng(seed)
    out = np.zeros_like(x, dtype=np.float64)
    for _ in range(4):
        th = rng.uniform(0.0, math.pi)
        lam = wavelength * rng.uniform(0.7, 1.4)
        out += np.sin(2.0 * math.pi * (x * math.cos(th) + y * math.sin(th)) / lam + rng.uniform(0.0, 2.0 * math.pi))
    return out / 2.0


def _noise_m(scales, level, seed, dev, base):
    """Roughness in metres: [[wavelength_m, amp_m], ...] as fbm (amp the standard deviation), scales the level
    resolves only."""
    out = np.zeros((level.n, level.n))
    for k, (wl, amp) in enumerate(scales or ()):
        if float(amp) == 0.0 or float(wl) < 3.0 * level.cell:
            continue
        f = FL._field({'kind': 'fbm', 'wavelength_m': float(wl), 'octaves': 4, 'seed': base + k}, level, seed, dev)
        out = out + 3.0 * float(amp) * f
    return out


# =================================================================================================== the ops ===

def op_strata(fields, level, params, seed=0, ctx=None):
    """Stage 'strata' (module doc): the column spec into ctx.shared['strata'] for the level's later stages, and zs.
    params: column (a COLUMNS name or a list of layers), zs0_m, dip_deg, azimuth_deg, warp, faults, dz_m, seed."""
    ctx = ctx or FL.standalone_context(fields, level)
    sp = strata_spec(params)
    col = column(sp['column'], float(sp['dz_m']), int(sp.get('seed', 0)))
    ctx.shared['strata'] = sp
    if 'h' in fields:
        fields['zs'] = zs_field(fields['h'], sp, level, seed, ctx.device)
    ctx.log(f"[terrain.strata] column {col.name} ({col.top_m:g} m, {len(col.layers)} formations, "
            f"{len(col.fine)} beds), dip {sp['dip_deg']} deg toward {sp['azimuth_deg']} deg")
    return fields


PLATEAU_DEFAULTS = dict(surface_zs_m=None, height_m=0.0, follow_strata=True, follow_warp=True, tilt_deg=0.0,
                        tilt_azimuth_deg=0.0, roughness=((3000.0, 6.0), (600.0, 2.5), (120.0, 0.8)), edge=None,
                        edges=(), roughness_low=1.0, roughness_fade=0.25)


def plateau_surface(level, params, seed=0, dev=None, strata=None):
    """The start of 'plateau' on a level's cells (float64): a structural surface at surface_zs_m (following the
    beds' dip, fold, faults and, with follow_warp, their warp; without it the surface is an older erosion surface
    that truncates the warped beds, so a thin cap bed crops out in patches over the weaker bed below) or a plane at
    height_m tilted tilt_deg (rising toward tilt_azimuth_deg, counter-clockwise from +x), plus roughness
    ([[wavelength_m, amp_m], ...]) and optional escarpments, `edge` (one) or `edges` (a list): {'through': [x, y],
    'strike_deg' (compass), 'drop_m', 'width_m', 'wiggle_m', 'wiggle_wavelength_m'}: the ground to the right of the
    strike direction lies drop_m lower, the fall spread over width_m. Each edge's wiggle has its own noise (a
    badlands wall standing between an upper and a lower prairie is two edges). roughness_low: the roughness's factor
    on the low ground beyond an edge's foot, reached roughness_fade x its width past the foot (1: the same roughness
    everywhere): the high ground and the flanks keep the roughness that seeds their drainage, while a sod-covered
    prairie below stays smooth (rough, its pinned edges became low base levels the prairie was cut down to, and the
    fine levels dimpled it into a field of hummocks)."""
    p = dict(PLATEAU_DEFAULTS)
    p.update(params or {})
    x, y = level.xy()
    s = int(seed) + int(p.get('seed', 0))
    if p.get('surface_zs_m') is not None and p.get('follow_strata', True):
        if strata is None:
            raise ValueError("stage 'plateau' with surface_zs_m needs the 'strata' stage before it")
        sp = strata if p.get('follow_warp', True) else dict(strata, warp=())
        h = float(p['surface_zs_m']) + offset(sp, level, seed, dev)
    else:
        az = math.radians(float(p.get('tilt_azimuth_deg', 0.0)))
        h = float(p.get('height_m', 0.0)) + math.tan(math.radians(float(p.get('tilt_deg', 0.0)))) * (
            x * math.cos(az) + y * math.sin(az))
    rough = _noise_m(p.get('roughness'), level, s, dev, 601)
    edges = ([p['edge']] if p.get('edge') else []) + list(p.get('edges') or [])
    low = float(p.get('roughness_low', 1.0))
    keep = np.ones_like(h)                         # 1 on the high ground and the flanks, 0 on the low ground
    drops = []
    for k, e in enumerate(edges):
        ax, ay = (float(v) for v in e.get('through', (0.0, 0.0)))
        st = math.radians(float(e.get('strike_deg', 90.0)))
        ux, uy = math.sin(st), math.cos(st)
        side = (x - ax) * uy - (y - ay) * ux                    # > 0 right of the strike direction
        wig = float(e.get('wiggle_m', 0.0))
        if wig:
            side = side + 3.0 * wig * FL._field({'kind': 'fbm', 'wavelength_m': float(e.get('wiggle_wavelength_m',
                                                                                          2000.0)),
                                                 'octaves': 4, 'seed': 641 + 7 * k}, level, s, dev)
        w = max(float(e.get('width_m', 200.0)), 1e-6)
        t = np.clip(side / w + 0.5, 0.0, 1.0)
        drops.append(float(e.get('drop_m', 100.0)) * t * t * (3.0 - 2.0 * t))
        if low != 1.0:
            beyond = np.clip((side - 0.5 * w) / max(float(p.get('roughness_fade', 0.25)) * w, 1e-6), 0.0, 1.0)
            keep = keep * (1.0 - beyond * beyond * (3.0 - 2.0 * beyond))
    if low != 1.0:
        rough = rough * (low + (1.0 - low) * keep)
    h = h + rough
    for d in drops:
        h = h - d
    return h


def op_plateau(fields, level, params, seed=0, ctx=None):
    """Stage 'plateau' (plateau_surface): the start surface, on a fresh level only (a level that inherited one keeps
    it). Writes h and bed (all rock)."""
    ctx = ctx or FL.standalone_context(fields, level)
    if not ctx.fresh and 'h' in fields and np.any(np.asarray(fields['h'])):
        return fields
    sp = ctx.shared.get('strata')
    h = plateau_surface(level, params, seed, ctx.device, sp)
    fields['h'] = h.astype(F32)
    fields['bed'] = h.astype(F32)
    if sp is not None:
        fields['zs'] = zs_field(h, sp, level, seed, ctx.device)
    ctx.log(f"[terrain.strata] plateau start on {level.n}^2 @ {level.cell:.3g} m: {float(h.min()):.0f}.."
            f"{float(h.max()):.0f} m")
    return fields


FLUVIAL_DEFAULTS = dict(U_m_per_yr=0.0, threshold_iters=3, threshold_rate=0.12, repose_deg=34.0, later='refine',
                        later_frac=0.25, pin_every=8, caprock_zs_m=None, caprock_target=None, check_every=40,
                        roughness=0.3, deposition=0.5, weather_m_per_yr=0.0, weather_slope_deg=30.0,
                        weather_sat=1000.0, weather_loose=2.0, weather_area=0.0, weather_area_slope_deg=(20.0, 35.0),
                        weather_refine=0.0, weather_loose_refine=0.5, weather_k_exp=1.0, joints=(), joint_gain=0.0,
                        resist=0.0,
                        resist_run=0.0,
                        resist_noise=1.0, resist_scales_m=(1400.0, 600.0), edge_follow=True)


def _q(params, key):
    if key in (params or {}) and params[key] is not None:
        return params[key]
    if key in FLUVIAL_DEFAULTS:
        return FLUVIAL_DEFAULTS[key]
    return FL._p(params, key)


def op_strata_fluvial(fields, level, params, seed=0, ctx=None):
    """Stage 'strata_fluvial' (module doc): the coarsest level's first pass grows the landform under the base-level
    fall; its later passes, and every finer level, refine it under the low-pass lock with the channel at its final
    bed."""
    ctx = ctx or FL.standalone_context(fields, level)
    dev = ctx.device or FL.device()
    t0 = time.perf_counter()
    lv = level
    n = lv.n
    cell = float(lv.cell)
    p = dict(params or {})
    for k in ('roughness', 'deposition'):
        p.setdefault(k, FLUVIAL_DEFAULTS[k])
    sp = _strata_of(p, ctx)
    col = column(sp['column'], float(sp['dz_m']), int(sp.get('seed', 0)))
    s = int(seed) + int(p.get('seed', 0))
    if 'h' not in fields:
        raise ValueError(f"stage 'strata_fluvial' on {lv}: no height yet (put a 'plateau' stage before it)")
    zoff = offset(sp, lv, seed, dev)
    h = np.asarray(fields['h'], F32)
    main = ctx.main
    main_cell = float(main.cell) if main is not None else cell
    depth = ctx.depth
    first = ctx.role == 'grow' and ctx.fresh and ctx.prepass in (None, 0)
    later = ctx.role == 'grow' and not first
    refine = ctx.role == 'refine' or (later and _q(p, 'later') == 'refine')

    # the inputs (world functions; the column's K(zs) and threshold come from the tables in the kernels)
    K = FL.erodibility(lv, p, s, dev)
    if 'K_factor' in fields:
        K = K * np.asarray(fields['K_factor'], np.float64)
    if p.get('joints') and float(_q(p, 'joint_gain')) > 0:
        K = K * (1.0 + float(_q(p, 'joint_gain')) * joint_field(lv, p['joints'], s, dev))
    # the rock mass (rock_mass): strong patches erode and weather slower (K x exp(-resist n)) and stand steeper (the
    # composite threshold's run of rock x exp(-resist_run n), carried in par.z, which route_incise does not read)
    Q = np.ones((n, n))
    if float(_q(p, 'resist')) > 0 or float(_q(p, 'resist_run')) > 0:
        nz = rock_mass(lv, _q(p, 'resist_scales_m'), s, dev)
        if nz is not None:
            nz = nz * float(_q(p, 'resist_noise'))
        cores = rock_cores(lv, p.get('resist_cores'), s)
        if cores is not None:
            nz = cores if nz is None else np.clip(nz + cores, -2.5, 3.5)
        if nz is not None:
            K = K * np.exp(-float(_q(p, 'resist')) * nz)
            Q = np.exp(-float(_q(p, 'resist_run')) * nz)
    sod = p.get('sod')
    if sod and refine and (lv.role == 'hero' or not sod.get('hero_only', True)):
        # the sod cover (the hero levels): grass holds gentle ground, so the inherited surface's gentle slopes keep
        # only a fraction of their erodibility (the rills stay on the bare walls; on the prairies at the wall's foot
        # the hero levels' halved valley spacing cut every bump into a crumple of micro-rills). On the coarser
        # passes too it froze the band's flanks, gentle at coarse cells, and the dissected band shrank to half
        gy, gx = np.gradient(np.asarray(h, np.float64), cell)
        sl = np.degrees(np.arctan(np.hypot(gx, gy)))
        lo, hi = float(sod.get('below_deg', 10.0)), float(sod.get('above_deg', 22.0))
        t = np.clip((sl - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
        kmin = float(sod.get('k', 0.1))
        K = K * (kmin + (1.0 - kmin) * t * t * (3.0 - 2.0 * t))
    U = np.full((n, n), float(_q(p, 'U_m_per_yr')))
    G = np.full((n, n), float(_q(p, 'deposition')))
    rigid = FL._sea_flat(fields, ctx, (n, n))
    if rigid.any():
        U = np.where(rigid, 0.0, U)
        K = np.where(rigid, 0.0, K)
    par = T.rgba(U, K, Q, G)

    # pins: the level's (edge or border band), and the river's channel
    base = ctx.pins if ctx.pins is not None else FL.edge_pins(n, h, ctx.sea_level)
    rv = ctx.shared.get('river')
    chan_cache = {}
    if isinstance(rv, RV.River):
        # (on a child level the river_path stage already eased the channel into the parent's at the border band:
        # hold keeps that, since its weight is 1 on the channel there)
        pins, chan = rv.pins(lv, base, 0.0 if first else 1.0, chan_cache,
                             hold=base['pin_w'] if ctx.role == 'refine' else None)
    else:
        pins, chan = base, None

    D, spacing = FL.diffusivity(p, cell, depth, main_cell)
    if ctx.role == 'refine':
        dt = float(FL._p(p, 'dt_ref_yr')) * max(cell, main_cell) / FL.CELL_REF_M
        steps = int(p.get('steps', FL._p(p, 'refine_steps')))
    else:
        dt = float(FL._p(p, 'dt_ref_yr')) * cell / FL.CELL_REF_M
        if first:
            dur = float(FL._p(p, 'age_myr')) * 1e6
        else:
            dur = float(ctx.shared.get('strata_years', float(FL._p(p, 'age_myr')) * 1e6)) * float(_q(p, 'later_frac'))
        steps = int(p.get('steps', round(dur / dt)))
    steps = int(np.clip(steps, int(FL._p(p, 'min_steps')), int(FL._p(p, 'max_steps'))))
    cap = float(FL._p(p, 'creep_cap'))
    n_sub, D_used = FL.creep_substeps(dt, cell, D, cap, int(FL._p(p, 'max_creep_sub')))
    lock, lock_b, lock_m = None, 2, None
    if refine and FL._p(p, 'lock'):
        if ctx.role == 'refine':
            pl = ctx.plan[ctx.plan[ctx.index].parent] if (ctx.plan and ctx.plan[ctx.index].parent is not None) else None
            pcell = float(pl.cell) if pl is not None else 2.0 * cell
            pdepth = getattr(pl, 'depth', depth + 1)
        else:
            pcell, pdepth = 2.0 * cell, depth                  # the previous coarse-to-fine pass
        lock_m = float(p['lock_m']) if p.get('lock_m') is not None else \
            FL.LOCK_SCALE * FL.diffusivity(p, pcell, pdepth, main_cell)[1]
        lock_b = FL.lock_block(lock_m, cell, n)
        lock = h
    # weathering grows the landform (the walls' retreat); on the passes under the low-pass lock the rock's only
    # fought the lock (which raised the plateau beside a retreating wall into bumps), so there it is scaled by
    # weather_refine; the loose cover's goes on (x weather_loose_refine), or the debris of every failing bed draped
    # the cliffs below it at 34 degrees and the walls rendered as smooth banded slabs
    W0 = float(_q(p, 'weather_m_per_yr'))
    wf = float(_q(p, 'weather_refine')) if refine else 1.0
    wl = W0 * float(_q(p, 'weather_loose')) * (float(_q(p, 'weather_loose_refine')) if refine else 1.0)
    a_lo, a_hi = (math.tan(math.radians(float(v))) for v in _q(p, 'weather_area_slope_deg'))
    weather = (wf * W0, math.tan(math.radians(float(_q(p, 'weather_slope_deg')))), float(FL._p(p, 'K')), wl,
               float(_q(p, 'weather_area')), float(_q(p, 'weather_sat')), (a_lo, a_hi))
    fac, fac_w = facies_spec(p.get('facies'), s)
    run = StrataRun(dev, cell, fields, par, pins, col, zoff, lock, lock_b,
                    math.tan(math.radians(float(_q(p, 'repose_deg')))), weather,
                    lv=(lv.x0, lv.y0, lv.cell), facies=fac, facies_w=fac_w,
                    weather_k_exp=float(_q(p, 'weather_k_exp')))
    iters = int(_q(p, 'threshold_iters'))
    rate = float(_q(p, 'threshold_rate'))
    mexp, nexp, pexp = float(FL._p(p, 'm')), float(FL._p(p, 'n')), float(FL._p(p, 'p'))
    slope_mode = {'dinf': 1, 'd8': 0}[FL._p(p, 'slope')]
    pit = 1 if FL._p(p, 'fill_pits') else 0
    peps = float(FL._p(p, 'pit_eps_m'))
    pin_every = max(int(_q(p, 'pin_every')), 1)
    target = _q(p, 'caprock_target')
    cap_zs = _q(p, 'caprock_zs_m')
    check = max(int(_q(p, 'check_every')), 1)
    falling = first and isinstance(rv, RV.River)
    # the coarsest level's outer ring follows the ground inside it down (never up) while the landform grows: held at
    # the starting plateau it stood as a one-cell wall up to 1 km tall where the canyon reached the tile's edge (a
    # white sliver on the horizon); badlands keep their prairies' edges as fixed base levels (edge_follow False)
    # (the coarsest level: no parent; ctx.pins is set by then, by the river_path stage)
    coarsest = not ctx.plan or ctx.plan[ctx.index].parent is None
    follow = first and coarsest and bool(_q(p, 'edge_follow'))
    ring = None
    if follow:
        ring = np.zeros((n, n), bool)
        ring[0, :] = ring[-1, :] = ring[:, 0] = ring[:, -1] = True
        base = dict(base, pin_h=np.array(base['pin_h'], F32, copy=True))
    history = []
    done = steps
    f_now = 0.0 if falling else 1.0
    for i in range(steps):
        if (falling or follow) and i % pin_every == 0:
            moved = False
            if follow and i > 0:
                inner = _ring_inner(run.height())
                lower = ring & (inner < base['pin_h'])
                if lower.any():
                    base['pin_h'][lower] = inner[lower]
                    moved = True
            f = RV.schedule_at(rv.schedule, i / max(steps - 1, 1)) if falling else 1.0
            if f != f_now or i == 0 or moved:
                f_now = f
                pins = rv.pins(lv, base, f, chan_cache)[0] if isinstance(rv, RV.River) else base
                run.set_pins(pins)
        run.step(dt, D_used, n_sub, iters, rate, cap, mexp, nexp, pexp, slope=slope_mode, pit_fill=pit,
                 pit_eps=peps)
        if first and target is not None and cap_zs is not None and (i + 1) % check == 0 and f_now >= 0.999:
            frac = caprock_fraction(run.height(), zoff, lv, main, cap_zs)
            history.append((i + 1, round(frac, 4)))
            if frac <= float(target):
                done = i + 1
                break
    out = run.readback()
    if first:
        ctx.shared['strata_years'] = done * dt
    for k in ('h', 'A', 'qs', 'wear', 'deposit', 'talus'):
        fields[k] = out[k]
    fields['bed'] = out['h'] - out['loose']
    dry = 0
    if p.get('dry_basins'):
        # the basins off the river fill with sand and alluvium (fill_dry_basins); the river's pools stay
        keep = None
        if chan is not None:
            keep = np.asarray(chan, bool)
            for ax_ in (0, 1):
                keep = keep | np.roll(keep, 1, ax_) | np.roll(keep, -1, ax_)
        dry = fill_dry_basins(fields, keep, hold=2 if (ctx.plan and ctx.plan[ctx.index].parent is not None) else 0)
    zs = np.asarray(fields['h'], np.float64) - zoff
    fields['zs'] = zs.astype(F32)
    fields['U'] = U.astype(F32)
    fields['K'] = (K * col.k_at(zs)).astype(F32)
    # the layer's angle where the rock is strong or weak (the rock mass and the facies)
    fields['Sc'] = (col.tan_at(zs) / (Q * facies_factor(lv, zs, fac))).astype(F32)
    fields['G'] = G.astype(F32)
    if chan is not None:
        fields['river'] = chan.astype(F32)
    ctx.evolved = True
    rec = dict(level=str(lv), prepass=ctx.prepass, role='first' if first else ('refine' if refine else 'evolve'),
               steps=done, dt_yr=round(dt, 2), years=round(done * dt), D=D_used, spacing_m=round(spacing, 1),
               creep_sub=n_sub, lock_block_cells=lock_b if lock is not None else None, lock_m=lock_m,
               caprock=history[-4:], dry_basin_cells=dry, seconds=round(time.perf_counter() - t0, 3))
    if cap_zs is not None:
        rec['caprock_frac'] = round(caprock_fraction(out['h'], zoff, lv, main, cap_zs), 4)
    ctx.shared.setdefault('fluvial_log', []).append(rec)
    ctx.log(f"[terrain.strata] {rec['role']} {n}^2 @ {cell:.3g} m" + (f' (pre-pass {ctx.prepass})'
                                                                    if ctx.prepass is not None else '')
            + f": {done} steps x {dt:.0f} yr, D {D_used:.3g} (valleys {spacing:.0f} m), creep x{n_sub}"
            + (', base level falling' if falling else '')
            + (f", caprock {rec['caprock_frac']:.3f}" if 'caprock_frac' in rec else '')
            + (f', locked above {lock_b} cells ({lock_b * cell:.0f} m)' if lock is not None else '')
            + f", {rec['seconds']} s")
    return fields


op_strata_fluvial.evolves = True
op_strata.evolves = True              # every coarse-to-fine pass: zs on each
OPS = {'strata': op_strata, 'plateau': op_plateau, 'strata_fluvial': op_strata_fluvial}
