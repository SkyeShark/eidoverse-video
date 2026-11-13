"""The terrain's palettes (design section 7): which CC0 scans cover which ground, as data, plus the small mask
expression language their layer weights and rock densities are written in. No bpy: build/surfacing.py turns a
palette into the eido_terrain_surface node group, build/dressing.py scatters its rocks.

    from eidoblend.terrain.build import palettes as P
    P.names()                          # ['alpine', 'badlands', 'chalk_coast', 'desert_sandstone', 'dunes', ...]
    pal = P.get('alpine')              # a validated deep copy, every default filled in
    pal = P.get('auto', recipe='canyon')       # the recipe's palette (RECIPE_PALETTES, RECIPE_LOOKS)
    pal, place = P.for_place('grand_canyon_toroweap')   # a real DEM's palette, its strata and its mask parameters
    P.masks_used(pal)                  # {'slope', 'talus', 'convex_20m', ...}: the eido_<mask> attributes it reads
    P.describe('alpine')               # one page: layers, scans, weights, rocks

How the layers are placed (the way a terrain artist places them, from the terrain's own data):
  - cliffs against flats by slope, the threshold broken by world noise at several scales (fbm) and moved by curvature:
    convex ground (ridges, rims, spurs) bares its rock at a lower slope, hollows hold their cover to a steeper one;
  - talus and scree on the slopes under cliffs (the talus field, rock_toe, and the repose band of slopes, more in
    the concave feet), coloured by the beds above them (strata_offset_m);
  - sediment, sand and gravel in the channels (flow) and on deposits; damp ground by wetness;
  - plants by the derived `plants` (slope, wetness, sky view, talus, sand, snow and the treeline), never by the
    masks package's `vegetation`, which multiplies by its `rock`: that mask counts any ground eroded more than 20 m
    as rock, and on an eroded landform that is nearly all of it (rock reads 0.8-0.95 on ground under 25 degrees in
    the canyon, mesas and meanders recipes, so vegetation and rock_toe read 0 there);
  - snow on the flatter, shaded faces and in the gullies, lower on north faces and in hollows, off ridges and
    walls (altitude against the snowline, both constants of the terrain);
  - rock layers coloured by the strata column at the stratigraphic height (its dip, warp and faults), with
    bed-scale bedding, lateral facies changes and runnels dragging the bands down the walls (surfacing.strata_image);
  - every transition height-blended by the scans' own heights, with ragged edges, and macro colour variation over
    the whole place (options macro, patches, tone).

A palette is a dict:
    title        what it is
    layers       up to six, bottom first; each a dict:
        name         a label
        set          a texture set as _pbr.find_set names it (fetch_texture.py "<ID>" 2k --cache puts it in the cache)
        tile_m       metres one tile of the scan spans
        colour       the albedo the layer averages, sRGB '#rrggbb': the scan is rescaled channel by channel from its
                     own mean (measured when it is packed) to this, so its detail stays and its cast goes; None keeps
                     the scan's own colour
        tint         (r, g, b) linear multiplier applied after colour (the old film material's tint), default none
        value        brightness multiplier after the colour (default 1): slickrock a little paler than its bed
        roughness    multiplier on the roughness map (default 1)
        projection   'planar' (world XY; the scan's normal map in the XY tangent frame) or 'box' (the Image Texture
                     node's Box projection with blend, a cheap triplanar for walls; its normal comes from the bump of
                     its own height map, which is right in any projection)
        normal       normal-map strength (planar layers, default 1)
        bump_m       relief of the height map in metres for the bump (default 0 on planar layers, 0.04 x tile_m on
                     box layers)
        weight       the layer's coverage, 0..1, as a mask expression (below). Coverage composites in order: a layer
                     covers what lies below it, so the base layer is '1' and snow sits on top
        strata       True: the albedo is recoloured by the palette's strata column at each point's stratigraphic
                     height (the bands sit on the benches the solver made); a float 0..1 mixes the column's colour
                     with the layer's own (talus: mostly the colour of the beds above it). A palette without a column
                     keeps the layer's own colour
        strata_offset_m   read the column this many metres above the point (talus and slope wash: the debris of the
                     beds above, default 0)
        edge_noise   ragged-edge noise amplitude for this layer (default the palette's)
        specular     this layer's Principled specular (default the palette's): grass is not glossy, wet rock is
        contrast     1 keeps the scan's detail as it is around the new mean; under 1 flattens it
        streaks      (width_m, amount[, lo, hi]): vertical streaks darkening the steep faces (water stains, desert
                     varnish); lo, hi (default 0.45, 0.68) the noise's edges: higher is sparser
        streaks_where  a mask expression the streaks' darkening is multiplied by (where the water runs: flow)
        ledges       dict(tint, amount, scale_m, lo, hi, where): on a strata layer whose palette's strata has relief_m,
                     plants and debris lodged on the ledges (the tops of the beds that stand out): the layer's own scan
                     tinted by tint (r, g, b), in tufts broken at scale_m metres, limited by where
        relief       False: no bed relief on this strata layer (default True when the strata spec has relief_m)
        patches      a dict or a list of dicts: a second tone in world-noise patches, what breaks a lawn-like scan up
                     at the scales it mipmaps away at. Each: scale_m (None: everywhere `where` says), colour (sRGB,
                     relative to the layer's colour) or tint ((r, g, b) multiplier), amount, detail (noise octaves,
                     default 3), lo/hi (the noise's smoothstep edges, default 0.42/0.62), where (a mask expression
                     that limits it)
        far_contrast the far read's contrast around the scan's mean (default the palette's 0.65)
        macro_mod    how much the far read's brightness modulates the near read (default the palette's)
        far_height   False: the height blend keeps the near read's height at a distance too (speckle layers: shrubs,
                     tufts), where the default takes the far read's, magnified with its pattern
        ripples      dict(wavelength_m, height_m, azimuth_deg (the bearing the wind blows toward), fade_m): wind
                     ripples as bump, faded out with distance before they alias
        canopy       dict(crown_m, colour, light, gap, height_m, near_m, edge, clump_m, clump_height_m, clump_gap): a
                     forest seen from afar: tree crowns crown_m across (a world-space Voronoi, one random tone per
                     tree) with gaps of shadow between, shaded by a bump height_m tall, faded in beyond near_m (from
                     the layer's own scan near the camera, where the flora family's trees stand), and each tree in or
                     out as a whole at the forest's edge (edge True: a ragged edge of single trees, not a noise blob);
                     with clump_m the crowns cluster in clumps that many metres across, clump_gap of the ground in the
                     shadowed gaps between them, each clump its own tone and a relief clump_height_m tall (the grain
                     a canopy keeps from the air), whole clumps in or out at the edge
    options      material options (DEFAULT_OPTIONS; the old film material's, plus landscape macro octaves, the far
                 scale and the de-tiling)
    strata       None, or the column spec the strata layers read (see STRATA_COLUMNS and surfacing.strata_image):
                 column, source ('attribute': the eido_strata mask; 'position': object z with a dip), z_offset_m,
                 dip_deg, dip_azimuth_deg, faults, warp [(scale_m, amp_m), ...], facies_m (the lateral scale over
                 which beds thin, thicken and change colour), smear (width_m, metres: runnels drag the bands down the
                 walls), parting (how dark the bedding planes are), looks (True: colour the formations by
                 FORMATION_LOOKS by name, over the column's own colours), rows (facies realisations), pad_m,
                 relief_m (the beds in relief on the strata layers: hard beds stand this many metres out of a wall
                 as ledges over soft recesses, by bump; 0 = off) and relief_shade (how much darker the recessed
                 beds are, so the banding holds where the bump is finer than a pixel)
    constants    defaults for the terrain constants the weights may read (CONSTANTS): the terrain's own values
                 (surfacing.terrain_constants) replace them
    dressing     the rock scatter (build/dressing.py): models (ids, or (id, min_size_m, max_size_m) so heavy boulder
                 scans stand only for big rocks), colour, density expression, sizes, burial

The mask expression language (layer weights, rock densities; the same grammar as a stage's `where`):
    numbers, mask names (masks.MASKS: slope, talus, snow, northness, convex_20m, ...), the terrain constants
    (CONSTANTS: base_elevation_m, snowline_m, treeline_m), + - * /, unary -,
    smoothstep(e0, e1, x)  (e0 > e1 allowed: a falling edge), min(a, b, ...), max(a, b, ...), clamp(x, lo, hi),
    abs(x), pow(x, e), mix(a, b, t), noise(scale_m[, seed]): a world-space noise of about 0..1 (mean 0.5) with
    features `scale_m` metres across, fbm(scale_m[, seed]): the same with five octaves (features from scale_m down to
    a thirtieth of it: breakup at several scales in one term), and cells(scale_m[, seed[, z_stretch]]): a random
    value 0..1 per cell of a world-space Voronoi partition with cells about scale_m across (fields, patches with
    straight boundaries; with z_stretch k the partition is of (x, y, k z) in 3D, so on a hillside a cell spans only
    scale_m / k of height and runs along the contours: fields ploughed around the hills). Every mask is in its own unit (slope in degrees, talus in metres, ...), so a weight means the same at
    every level. The material and the scatter evaluate noise() and fbm() with different noises (the shader's and a
    numpy value noise), so use them for breakup, not for anything the two must agree on. DERIVED names expand to
    expressions (altitude, cover, bare, plants).
"""
from __future__ import annotations

import ast
import copy
import re

import numpy as np

# ------------------------------------------------------------------------------------------- the options ---

DEFAULT_OPTIONS = dict(
    # the film material's settings, measured with the shimmer probe (tests/terrain/surfacing/test_shimmer.py)
    anti_tile=True,                 # a second sample per map at an unrelated scale and offset, switched by noise
    detile='offset',                # 'offset': that second sample at 0.7071 x the scale and an offset (the old
                                    # material's); 'rotate': turned as well (planar layers; box layers keep
                                    # 'offset'), with the switch following the scans' heights (no soft seam)
    detile_patch=1.2,               # the switch's patches, in tiles
    height_blend=0.5,               # a_i = w_i + height_i * height_blend
    blend_depth=0.2,                # keep what is within this of the tallest a_i
    edge_noise=0.3,                 # ragged ~1 m noise on the upper layers' edges
    ao=0.5,                         # how much of each scan's AO darkens its albedo (EEVEE adds the scene's on top)
    damp=0.5,                       # damp patches: wet soil darkens and loses some roughness
    damp_scale_m=6.25,              # the old patches' size (noise scale 0.16)
    damp_where=None,                # an expression that adds damp ground (e.g. 'wetness'), on top of the patches
    tone=None,                      # an expression added to the albedo's brightness (x (1 + tone)): hollows and
                                    # gorges darker, convex edges paler
    specular=0.5,                   # Principled 'Specular IOR Level'. Plant layers (grass, forest, crops) take 0.08:
                                    # at 0.25 a meadow seen at eye level mirrored the blue sky at the grazing angle
                                    # and rendered (87, 109, 90), blue-grey, where lauterbrunnen_01's grass is
                                    # yellow-green with almost no blue (11-13); blades scatter, they do not mirror
    bump=0.0,                       # the old global bump from the blended height (metres; 0 = off)
    interpolation='Auto',           # 'Auto': Cubic within detail_distance of the camera, mipmapped Linear beyond
    detail_distance=(4.0, 9.0),
    # the far scale (new for landscapes; 1 = off, as the old material): past far_distance metres the albedo and
    # height are read again at far_scale x the tile, so slopes hundreds of metres off show the scan's pattern at a
    # larger size instead of a fine regular knit of repeats; far_bump scales the bump of that larger relief
    far_scale=1.0,
    far_distance=(40.0, 200.0),
    far_bump=0.5,
    far_contrast=0.65,              # the far read's contrast around the scan's mean (its pattern, not polka dots)
    far_detile=False,               # the far read de-tiled too (two lattices switched by noise)
    macro_mod=0.0,                  # near the camera, the scan's brightness modulated by its own far read's (a
                                    # macro variation map from the scan itself: no two repeats alike)
    debug=None,                     # 'weights' (the top three layers' weights as RGB), 'layers' (one flat colour per
                                    # layer, blended by weight) or 'albedo', unlit
    # world-scale variation: brightness, hue and saturation drift. The old material's two octaves (value over ~14 m,
    # hue and saturation over ~22 m) plus, for landscapes, octaves at tens to thousands of metres
    macro=[dict(scale_m=14.3, value=0.14, detail=4.0, roughness=0.5),
           dict(scale_m=22.2, hue=0.012, saturation=(0.88, 1.08), detail=2.0, roughness=0.55, w=7.7)],
)

# macro octaves for landscapes: the old two plus slope-scale, field-scale and valley-scale drift
LANDSCAPE_MACRO = [dict(scale_m=14.3, value=0.10, detail=4.0, roughness=0.5),
                   dict(scale_m=22.2, hue=0.010, saturation=(0.9, 1.06), detail=2.0, roughness=0.55, w=7.7),
                   dict(scale_m=75.0, value=0.10, hue=0.008, detail=3.0, roughness=0.6, w=2.1),
                   dict(scale_m=320.0, value=0.12, saturation=(0.86, 1.1), detail=3.0, roughness=0.55, w=3.3),
                   dict(scale_m=1600.0, value=0.10, hue=0.008, saturation=(0.92, 1.06), detail=2.0, roughness=0.5,
                        w=5.1)]

# the options every landscape palette shares: the landscape macro octaves, the far scale, and the de-tiling that
# breaks large single-material areas up (a turned second lattice near, two lattices far, the scan's own macro map)
LANDSCAPE = dict(macro=LANDSCAPE_MACRO, far_scale=8.0, detile='rotate', far_detile=True, macro_mod=0.35)

MAX_LAYERS = 6
PROJECTIONS = ('planar', 'box')

# what a strata spec takes when it does not say (a recipe's palette from strata.palette_for carries only its column
# and source): the beds undulate by +-4 m over 500 m and +-1.2 m over 90 m, thin, thicken and change colour over
# 700 m (8 realisations of the column's beds), runnels 2.5 m wide drag the bands 1.5 m down the walls, the bedding
# planes are 15 % darker, the formations take their FORMATION_LOOKS, and the column runs on 300 m past either end
STRATA_DEFAULTS = dict(warp=[(500.0, 4.0), (90.0, 1.2)], facies_m=700.0, rows=8, smear=(2.5, 1.5), parting=0.15,
                       looks=True, pad_m=300.0)

# the terrain constants the expressions may read; the material and the scatter fold them in as numbers. The
# defaults mean "none": no snow, no treeline. surfacing.terrain_constants reads a terrain's own (its base elevation,
# its recipe knobs or its place's mask parameters); a palette's `constants` sets defaults for its kind of place.
CONSTANTS = {
    'base_elevation_m': 0.0,        # altitude = height + base_elevation_m
    'snowline_m': 1.0e5,            # altitude of today's snowline
    'treeline_m': 1.0e5,            # altitude of the treeline
}

# ------------------------------------------------------------------------------------- the strata columns ---
# A column is bottom to top: base_m (the stratigraphic height of its bottom, metres) and formations
# (name, thickness_m, colour sRGB, roughness multiplier, mean bed thickness m, bed colour jitter). Inside a formation
# the beds take random thicknesses around the mean and a little colour jitter, so a cliff shows bedding, not one flat
# band. Colours are what the rock looks like in daylight photographs (desert varnish and staining included).
# repeat=True: the column repeats (a generic limestone pile for walls at any height).

STRATA_COLUMNS = {
    # Grand Canyon at Toroweap, east of the Toroweap fault (the overlook's side): the Esplanade bench stands at about
    # 1370 m, the Kaibab rim at 1950 m, the river at 505 m. Contacts placed on the benches the DEM shows (gentle ground
    # piles up at 1090-1110 m, 1310-1460 m, 1760-1780 m and 1910-1945 m). Colours as in the photographs from the
    # overlook (tw_03, tw_07): the inner gorge grey-brown, the Supai red with grey ledges, the Esplanade salmon.
    'toroweap': dict(base_m=480.0, formations=[
        ('Muav limestone and Bright Angel shale', 220.0, '#7b7067', 1.0, 1.6, 0.11),
        ('Temple Butte and upper Muav', 230.0, '#83756a', 1.0, 1.8, 0.1),
        ('Redwall limestone (stained)', 170.0, '#8d6455', 0.95, 4.0, 0.09),
        ('lower Supai group', 200.0, [('#7f4f3f', 0.55), ('#97796a', 0.3), ('#6c4a3e', 0.15)], 1.0, 1.4, 0.12),
        ('Esplanade sandstone', 85.0, '#ad826a', 0.95, 3.0, 0.09),
        ('Hermit shale', 265.0, '#8b5a48', 1.0, 1.2, 0.11),
        ('Coconino sandstone', 50.0, '#c8bca3', 0.9, 5.0, 0.06),
        ('Toroweap formation', 100.0, '#a8987f', 1.0, 1.5, 0.11),
        ('Kaibab limestone', 180.0, '#b5aa98', 0.95, 2.5, 0.1),
    ]),
    # Badlands Wall near Cedar Pass: Chadron mounds at the foot, the Brule's pale buff mudstone with pink and rusty
    # palaeosols (muted: the photographs bl_01-bl_07 show soft pastel bands, not candy stripes), the Poleslide's buff
    # siltstone, pale ash beds near the top.
    'badlands_cedar_pass': dict(base_m=720.0, formations=[
        ('Chadron formation', 32.0, '#a9a593', 1.0, 3.0, 0.05),
        ('Brule, Scenic member', 48.0, [('#cdb9a0', 0.6), ('#c19c86', 0.2), ('#ae8a77', 0.1), ('#dcd4c4', 0.1)],
         1.0, 0.9, 0.06),
        ('Brule, Poleslide member', 50.0, [('#c8b398', 0.7), ('#b99a80', 0.2), ('#ab9580', 0.1)], 1.0, 1.3, 0.06),
        ('Rockyford ash', 6.0, '#dcd6ca', 0.95, 1.5, 0.04),
        ('Sharps formation', 40.0, [('#cfc2ab', 0.8), ('#bba98f', 0.2)], 1.0, 1.6, 0.05),
    ]),
    # Meteor Crater's target rock (the walls, rim to floor): the Moenkopi's red-brown siltstone at the rim, the Kaibab's
    # buff dolomite and limestone ledges in the upper wall, the thin Toroweap, the Coconino's pale cream sandstone in
    # the lower wall (behind its talus), the Supai's red under the floor. zs 352 is the plain's level.
    'meteor_crater': dict(base_m=0.0, formations=[
        ('Supai formation', 50.0, '#8c5a45', 1.0, 2.0, 0.07),
        ('Coconino sandstone', 210.0, '#cbb898', 0.9, 4.0, 0.08),
        ('Toroweap formation', 8.0, '#b9a98c', 1.0, 1.5, 0.08),
        ('Kaibab formation', 84.0, [('#b19b79', 0.65), ('#9a8670', 0.35)], 0.95, 2.0, 0.1),
        ('Moenkopi formation', 12.0, '#8f6450', 1.0, 1.0, 0.1),
    ]),
    # a generic alpine limestone pile, repeated (the walls of Lauterbrunnen: the Quinten limestone's massive grey
    # cliffs with ochre stains, the thin-bedded darker beds and marly bands between them): horizontal bedding on any
    # wall at any height. Mid greys, as the sunlit Staubbach wall photographs (lauterbrunnen_01): the paler pile of
    # 11-12 (#b3aea4) rendered the walls near white, chalk rather than limestone
    # (11-13: a shade darker again and with more contrast between the formations, thicker beds in the massive units:
    # at #928e86 the sunlit wall still rendered pale and even, a fine plywood of thin beds, where the photograph's wall
    # is mid grey, its bedding broad zones of paler massive and darker thin-bedded limestone)
    'alpine_limestone': dict(base_m=0.0, repeat=True, formations=[
        ('massive limestone', 210.0, '#837f78', 0.95, 9.0, 0.09),
        ('thin-bedded limestone', 55.0, '#6d6a64', 1.0, 2.6, 0.1),
        ('marly band', 22.0, '#7a7266', 1.0, 2.0, 0.09),
        ('massive limestone', 170.0, '#7f7b73', 0.95, 8.0, 0.09),
        ('dark shaly limestone', 45.0, '#5e5b57', 1.0, 2.2, 0.1),
        ('ochre limestone', 60.0, '#8a7c64', 0.95, 4.0, 0.09),
    ]),
    # Guilin's grey karst limestone, repeated: massive grey beds with thin darker partings
    'karst_limestone': dict(base_m=0.0, repeat=True, formations=[
        ('massive limestone', 120.0, '#89857c', 0.95, 6.0, 0.08),
        ('thin-bedded limestone', 30.0, '#76726a', 1.0, 1.2, 0.09),
        ('massive limestone', 90.0, '#908b81', 0.95, 5.0, 0.08),
    ]),
    # the solver's columns (package 10, design 4.9), coloured by layer; their thicknesses there are the solver's own
    # (the material takes the solver's column when the recipe passes it, and colours it with FORMATION_LOOKS)
    'colorado_plateau': dict(base_m=0.0, formations=[
        ('Vishnu schist', 300.0, '#4f4844', 1.0, 6.0, 0.05),
        ('Tapeats sandstone', 70.0, '#6f5848', 1.0, 1.0, 0.07),
        ('Muav and Bright Angel', 200.0, '#7b7067', 1.0, 1.6, 0.07),
        ('Redwall limestone (stained)', 170.0, '#8d6455', 0.95, 4.0, 0.06),
        ('Supai group', 300.0, [('#7f4f3f', 0.55), ('#97796a', 0.3), ('#6c4a3e', 0.15)], 1.0, 1.4, 0.08),
        ('Hermit shale', 250.0, '#8b5a48', 1.0, 1.2, 0.08),
        ('Coconino sandstone', 100.0, '#c8bca3', 0.9, 5.0, 0.04),
        ('Toroweap formation', 80.0, '#a8987f', 1.0, 1.5, 0.07),
        ('Kaibab limestone', 100.0, '#b5aa98', 0.95, 2.5, 0.06),
    ]),
    'monument_valley': dict(base_m=0.0, formations=[
        ('Cedar Mesa sandstone', 120.0, '#c4a07c', 1.0, 3.0, 0.06),
        ('Organ Rock shale', 200.0, '#94503a', 1.0, 1.0, 0.07),
        ('De Chelly sandstone', 250.0, '#b0603c', 0.95, 6.0, 0.04),
        ('Moenkopi formation', 40.0, '#8f5640', 1.0, 1.0, 0.08),
        ('Shinarump conglomerate', 20.0, '#8a5039', 1.0, 2.0, 0.06),
    ]),
    'badlands': dict(base_m=0.0, formations=[
        ('Chadron formation', 30.0, '#a9a593', 1.0, 3.0, 0.05),
        ('Brule formation', 90.0, [('#cdb9a0', 0.6), ('#c19c86', 0.2), ('#ae8a77', 0.1), ('#dcd4c4', 0.1)],
         1.0, 1.0, 0.06),
        ('Rockyford ash', 6.0, '#dcd6ca', 0.95, 1.5, 0.04),
        ('Sharps formation', 40.0, '#cfc2ab', 1.0, 2.0, 0.05),
    ]),
    'chalk': dict(base_m=0.0, formations=[('chalk with flint bands', 400.0, '#e2ded3', 0.9, 1.2, 0.03)]),
    'limestone': dict(base_m=0.0, formations=[('limestone', 600.0, '#a6a39b', 0.95, 4.0, 0.05)]),
    'granite': dict(base_m=0.0, formations=[('granite', 3000.0, '#9d9890', 1.0, 40.0, 0.03)]),
}

# How each formation looks, by name (case-insensitive substring, first hit wins): (colour, roughness, mean bed m,
# bed colour jitter). A strata spec with looks=True colours a column's formations from this table over the colours it
# came with (the solver's columns, strata.material_column); a formation it does not name keeps its own. Calibrated on
# the photographs of each place under make_sky daylight at the textured views' exposure: the Grand Canyon's walls are
# muted grey-browns and reds with dense thin ledges (Toroweap, tw_03 and tw_07), Monument Valley's walls orange-red
# over red talus (mv_02, mv_04), the Goosenecks grey-green limestone ledges under red Halgaito slopes (gn_01, gn_06),
# the Badlands pale buff with pastel bands (bl_01-bl_07).
FORMATION_LOOKS = [
    # (bed jitter 0.09-0.13 on the layered walls: the photographs' walls are zebra-striped by ledge and recess at the
    # metre scale; at 0.06 the formations read as smooth painted bands)
    ('channel sandstone', ('#bfae94', 0.95, 1.5, 0.05)),
    # (the rim formations a shade warmer than the 11-12 values: under the sky's blue fill and the haze they rendered
    # cool blue-grey from the air, where tw_07's rim cliffs are buff and cream)
    ('kaibab', ('#baa78c', 0.95, 2.5, 0.1)), ('toroweap', ('#ad977b', 1.0, 1.5, 0.11)),
    ('coconino', ('#cdbb9c', 0.9, 5.0, 0.06)), ('hermit', ('#8b5a48', 1.0, 1.2, 0.11)),
    ('esplanade', ('#ad826a', 0.95, 3.0, 0.09)),
    ('supai', ([('#7f4f3f', 0.55), ('#97796a', 0.3), ('#6c4a3e', 0.15)], 1.0, 1.4, 0.12)),
    ('redwall', ('#8d6455', 0.95, 4.0, 0.09)), ('temple butte', ('#83756a', 1.0, 1.8, 0.1)),
    ('muav', ('#7b7067', 1.0, 1.6, 0.11)), ('bright angel', ('#76705f', 1.0, 1.2, 0.1)),
    ('tapeats', ('#6f5848', 1.0, 1.0, 0.1)), ('vishnu', ('#4f4844', 1.0, 6.0, 0.06)),
    ('shinarump', ('#8a5039', 1.0, 2.0, 0.09)), ('moenkopi', ('#8f5640', 1.0, 1.0, 0.11)),
    ('de chelly', ('#b0603c', 0.95, 6.0, 0.07)), ('organ rock', ('#94503a', 1.0, 1.0, 0.1)),
    ('cedar mesa', ('#c4a07c', 1.0, 3.0, 0.08)),
    ('paradox', ([('#8b877c', 0.7), ('#7d7468', 0.3)], 0.95, 1.6, 0.1)),
    ('honaker', ([('#8e897e', 0.6), ('#80614f', 0.25), ('#9c968a', 0.15)], 1.0, 1.1, 0.1)),
    ('halgaito', ('#8c5444', 1.0, 1.0, 0.1)),
    # (the Chadron's grey-green mounds read cold blue-grey under the sky at #a9a593: warmer, as in bl_01 and bl_07)
    ('chadron', ('#b1a990', 1.0, 3.0, 0.05)),
    # (a shade warmer, 11-13: under the sky's blue fill the walls rendered cool grey-pink beside bl_01's buff)
    ('brule', ([('#d3bc9c', 0.62), ('#c9a68b', 0.2), ('#b8957f', 0.1), ('#ddd3bf', 0.08)], 1.0, 0.9, 0.06)),
    ('ash', ('#dcd6ca', 0.95, 1.5, 0.04)), ('sharps', ([('#cfc2ab', 0.8), ('#bba98f', 0.2)], 1.0, 1.6, 0.05)),
]

# colours by layer name, for a column the solver passes as bare rows (name, thickness_m, ...): matched by
# case-insensitive substring, first hit wins
LAYER_COLOURS = [
    ('kaibab', '#b5aa98'), ('toroweap', '#a8987f'), ('coconino', '#c8bca3'), ('hermit', '#8b5a48'),
    ('esplanade', '#ad826a'), ('supai', '#7f4f3f'), ('redwall', '#8d6455'), ('muav', '#7b7067'),
    ('bright angel', '#76705f'), ('tapeats', '#6f5848'), ('vishnu', '#4f4844'), ('shinarump', '#8a5039'),
    ('moenkopi', '#8f5640'), ('de chelly', '#b0603c'), ('organ rock', '#94503a'), ('cedar mesa', '#c4a07c'),
    ('brule', '#c9b49b'), ('chadron', '#a9a593'), ('ash', '#dcd6ca'), ('sharps', '#cfc2ab'), ('chalk', '#e2ded3'),
    ('flint', '#5e5a55'), ('limestone', '#a6a39b'), ('granite', '#9d9890'), ('basalt', '#3a3634'),
    ('sandstone', '#c09a76'), ('shale', '#8e7c6c'), ('clay', '#b9a58c'),
]

# ------------------------------------------------------------------------------- shared weight vocabulary ---
# The breakup that moves every threshold: fbm (five octaves) at a few scales, shared between the layers (each
# (scale, seed // 3) is one noise node in the material, its three channels three decorrelated noises).

# cliffs: steep ground, bared lower on convex rims and spurs, held under cover in hollows; the threshold wanders by
# +-6 degrees over 80 m and +-2.5 over 12 m (a wall's edge is never a contour); and the convex ribs between a wall's
# gullies bare at a gentler slope than the chutes between them, which hold the debris (a crater's or a canyon's
# gullied wall: rock ribs and talus chutes, not one material)
_CLIFF = ('max(smoothstep({lo}, {hi}, slope + 12*(fbm(80, 5) - 0.5) + 5*(fbm(12, 0) - 0.5) + 10*convex_20m '
          '- 8*concave_20m{extra}), 0.9*smoothstep(0.2, 0.5, convex_20m + 0.3*(fbm(22, 4) - 0.5)) '
          '* smoothstep({rlo}, {rhi}, slope){ribs}) * (1 - smoothstep(0.4, 2.0, deposit + talus))')


def _cliff(lo, hi, extra='', ribs=''):
    """A cliff weight bared from `lo` to `hi` degrees; ribs: a factor on the convex-rib term (a vegetated alpine spur
    is not a bare rib: the alpine palette keeps its ribs above the treeline)."""
    return _CLIFF.format(lo=lo, hi=hi, extra=extra, rlo=lo - 13, rhi=lo - 4, ribs=ribs)


# talus and scree: the repose band of slopes under the cliffs (more in the concave feet, less on spurs), the talus
# the solvers left, and rock_toe where the masks' rock is the geometry's (real DEMs). rock_toe enters weakly and
# broken by noise: its rockfall march runs along 12 azimuths from every edge of the masks' rock, and where that rock
# is speckled (an eroded recipe's wear) it draws polygons with straight edges (the alpine valley's scree, 11-12)
_TALUS = ('max(smoothstep(0.2, 1.5, talus), 0.8*smoothstep(0.4, 0.85, rock_toe + 0.45*(fbm(30, 3) - 0.5)){toe}, '
          'smoothstep({lo}, {hi}, slope + 9*(fbm(45, 3) - 0.5) + 10*concave_20m - 8*convex_20m){band})')


def _talus(lo, hi, toe='', band=''):
    return _TALUS.format(lo=lo, hi=hi, toe=toe, band=band)


# rubble, scree and gravel scans seen from afar: the far read (far_scale x the tile, past far_distance) magnifies
# their stones eight times, a knit of pale "boulders" on every talus apron (Meteor Crater's walls' feet, 11-13), so on
# these layers it is only a faint variation (far_contrast) and a weak macro map
_RUBBLE_FAR = dict(far_contrast=0.22, macro_mod=0.12)


# snow: altitude against the snowline, decided over a broad band by the ground's shape, never by a height line: held
# up to 550 m lower in gullies and hollows and shed up to 450 m higher off ridges and ribs (the signed plan and profile
# curvature at 20 m, in metres of snowline per 1/m and clamped: a young cone's shallow gullies, plan curvature -3e-3/m,
# move it about 150-250 m, a rugged range's couloirs the whole 550; the concave_20m mask's 0.03-0.3 bend threshold
# reads 0.02 on Fuji's flanks), 250 m lower along the drainage lines a couloir follows (flow), 220 m lower on north
# faces; caught on the flatter benches only above the line; off walls steeper than about 45 degrees; broken by noise
# at 500, 60 and 14 m (and the wall edge at 6 m). Near the line it lies as streaks in the gullies with bare ribs
# between them (Fuji's flanks from the air, the couloirs above Lauterbrunnen), not as a cap with a contour for an
# edge (the review of 11-12: "the alpine snow stops at a height line"), and its edge is ragged down to metres, not
# a smooth blob (the 11-12 aerial's "hard-edged white patches")
_SNOW = ('smoothstep(0.33, 0.63, smoothstep(snowline_m - 250, snowline_m + 250, altitude + 220*northness '
         '+ clamp(-50000*curv_plan_20m - 20000*curv_profile_20m, -450, 550) + 250*smoothstep(0.5, 0.8, flow) '
         '+ 200*(fbm(500, 6) - 0.5) + 110*(fbm(60, 7) - 0.5) + 80*(fbm(14, 9) - 0.5)) '
         '+ 0.2*smoothstep(30, 12, slope)*smoothstep(snowline_m - 100, snowline_m + 300, altitude) - 0.06) '
         '* smoothstep(52, 40, slope + 10*(fbm(30, 8) - 0.5) + 6*(fbm(6, 10) - 0.5))')

# ------------------------------------------------------------------------------------------- the palettes ---

PALETTES = {
    'alpine': dict(
        title='Alpine: bedded limestone walls, scree, pasture and spruce forest, river gravel, snow in the gullies',
        layers=[
            # pasture, with drier tufts a few metres across, lusher swales at field scale, and tawny alpine grass above
            # the treeline (what a meadow shows from eye height, a valley side from the air)
            dict(name='pasture', set='Grass004', tile_m=2.5, colour='#5f7a33', roughness=1.4, specular=0.08,
                 weight='1',
                 # drier tufts a few metres across, lusher swales at field scale, the lush green of wet ground along
                 # the drainage and in hollows (wetness), drier yellow-green on the convex knolls, and tawny alpine
                 # grass above the treeline (south faces carry the green higher)
                 patches=[dict(scale_m=7.0, colour='#8a8a45', amount=0.6),
                          dict(scale_m=90.0, colour='#4c6a2b', amount=0.5, detail=4.0),
                          dict(scale_m=None, colour='#4f7a2c', amount=0.6,
                               where='smoothstep(0.55, 0.9, wetness + 0.2*(fbm(40, 10) - 0.5))'),
                          dict(scale_m=None, colour='#7d8445', amount=0.5,
                               where='smoothstep(0.15, 0.6, convex_20m + 0.3*(fbm(25, 11) - 0.5))'),
                          dict(scale_m=None, colour='#86804f', amount=0.85,
                               where='smoothstep(treeline_m - 120, treeline_m + 320, altitude + 120*northness '
                                     '+ 120*(fbm(150, 9) - 0.5))')]),
            # scree: the debris at repose under the walls, the talus cones and the rockfall shadow's toe. Below the
            # forest in the order: Lauterbrunnen's talus cones are forested below the treeline (lauterbrunnen_01: the
            # slope at the foot of the Staubbach wall is spruce), so the grey shows where the forest thins out, above
            # the treeline and on the youngest cones, never as grey blots in a wooded slope (the leopard spots of the
            # 11-12 renders: scree laid over forest on every dry 30-40 degree slope)
            # (the repose band of slopes only well above the treeline: the alpine pastures over the forest are grass on
            # slopes to 40 degrees, Schynige Platte and Maennlichen in lauterbrunnen_15; on every slope over 31 degrees
            # the band laid grey spots all over them, 11-13. Talus and rock_toe make scree at any altitude)
            dict(name='scree', set='rocks_ground_06', tile_m=3.0, colour='#8f8b82', projection='box',
                 weight=_talus(29, 38, band=' * smoothstep(treeline_m + 250, treeline_m + 700, altitude '
                                            '+ 150*(fbm(300, 14) - 0.5))'), **_RUBBLE_FAR),
            # river gravel on the trunk streams and the bars beside them: flow is continuous across levels, where
            # channels marks rills on the fine levels. A valley's sediment fill away from the river is meadow (the
            # floor at Lauterbrunnen), so deposits take gravel only near flowing water
            dict(name='gravel', set='rock_ground_02', tile_m=3.0, colour='#8a8679', **_RUBBLE_FAR,
                 weight='max(smoothstep(0.86, 0.95, flow + 0.05*(fbm(40, 2) - 0.5)) * smoothstep(9, 3, slope), '
                        'smoothstep(0.4, 1.5, deposit) * smoothstep(12, 4, slope) '
                        '* smoothstep(0.66, 0.84, flow + 0.12*(fbm(40, 2) - 0.5)))'),
            # spruce forest on the lower walls, their ledges and the talus cones (not on the floor, cleared for
            # pasture, nor on walls): from afar a canopy of crowns with shadow between them and single trees at its
            # ragged edge, near the camera the needle litter under the trees the flora family plants
            # (spruce holds the talus and ledges of the lower walls, steeper than `plants` lets grass: the forest
            # gives back its slope term between 28 and 44 degrees and holds under the rock until 60-70, so the bare
            # walls take over by covering it (the rock fades in from 50-62): when the forest stopped at 48-56, the
            # scree beneath both showed through between them as pale spots all over the forested slopes, 11-13)
            # (the canopy fades in from 120 m to 400 m: nearer, the flora family's trees stand on the litter, and the
            # stand-in crowns read as scales at 30-100 m)
            # (the canopy's crowns cluster in clumps about 14 m across with shadowed gaps, each clump its own tone and
            # relief: what a forest seen from the air keeps when a crown is finer than a pixel; one flat crown tone
            # read as black-green blotches with hard edges in the 11-12 aerial)
            # (the litter near the camera an olive-brown forest floor: at #3a3626 the trees' ground read as black
            # holes in the meadow of a terrain-only eye view, 11-13 judge)
            dict(name='forest', set='forrest_ground_03', tile_m=2.5, colour='#4a4532', normal=0.8, specular=0.08,
                 canopy=dict(crown_m=4.2, colour='#38552e', light='#5f7a44', gap='#1b2415', height_m=1.6,
                             near_m=(120.0, 400.0), edge=True, clump_m=14.0, clump_height_m=5.0, clump_gap=0.22),
                 # stands of lighter larch and beech, and denser, darker spruce: the canopy's tone at 25-70 m (more
                 # of them than 11-12's: the clumped canopy still read as one dark sheet from Schynige Platte)
                 patches=[dict(scale_m=70.0, tint=(1.32, 1.3, 1.02), amount=0.65, detail=4.0, lo=0.45, hi=0.66),
                          dict(scale_m=25.0, tint=(0.78, 0.84, 0.8), amount=0.4)],
                 # (meadows on the gentler slopes, the alps around Wengen and Mürren, with stands of forest in them;
                 # forest on the 20-50 degree slopes; avalanche tracks down the drainage lines of the steep slopes,
                 # strips of meadow through the forest; the treeline ragged by aspect and noise)
                 weight='smoothstep(0.46, 0.64, 0.8*plants + 0.45*smoothstep(20, 34, slope) '
                        '+ 0.35*(fbm(260, 3) - 0.5) + 0.12*(fbm(30, 4) - 0.5) + 0.08*(fbm(12, 13) - 0.5) '
                        '+ 0.1*concave_20m '
                        '- 0.4*smoothstep(0.62, 0.86, flow)*smoothstep(18, 28, slope)) * smoothstep(6, 12, slope) '
                        '* smoothstep(70, 60, slope + 4*(fbm(30, 5) - 0.5)) '
                        '* smoothstep(treeline_m + 80, treeline_m - 150, altitude + 100*northness '
                        '+ 120*(fbm(300, 12) - 0.5))'),
            # the limestone walls: the bedded pile (horizontal bedding, the Staubbach wall's signature), ochre stains
            # and the dark water streaks that run down them. Below the treeline only the walls are bare (50-62
            # degrees: the forest clothes every ledge it can hold); above it, where no soil holds, the rock bares from
            # 38-50 degrees and on the convex ribs and arêtes
            # (the bedding shows as ledges in relief, the strata's relief_m, with grass and shrubs lodged on them below
            # the treeline: the green lines along the Staubbach wall's beds; the dark water streaks gather where the
            # water runs down the wall (flow), a few, not a vertical grain over every wall)
            dict(name='rock', set='Rock019', tile_m=14.0, colour='#8a867e', projection='box', bump_m=0.5,
                 strata=True, streaks=(3.5, 0.32, 0.6, 0.78), contrast=1.4,
                 streaks_where='0.25 + 0.75*smoothstep(0.22, 0.42, flow + 0.15*(fbm(40, 21) - 0.5))',
                 ledges=dict(tint=(0.52, 0.8, 0.42), amount=0.8, scale_m=5.0,
                             where='smoothstep(treeline_m + 150, treeline_m - 150, altitude + 120*(fbm(200, 22) - 0.5))'),
                 # ochre and orange iron staining in broad zones (the Staubbach wall's tan and orange: about a third of
                 # the wall), darker wet and lichen-grown zones, grey lichen, and moss and dark lichen held on the
                 # shaded north faces
                 patches=[dict(scale_m=130.0, tint=(1.3, 1.02, 0.7), amount=0.85, detail=4.0, lo=0.42, hi=0.62),
                          dict(scale_m=25.0, tint=(1.12, 0.97, 0.8), amount=0.4, lo=0.55, hi=0.7),
                          dict(scale_m=45.0, tint=(0.72, 0.73, 0.74), amount=0.5, detail=4.0, lo=0.52, hi=0.7),
                          dict(scale_m=11.0, tint=(0.78, 0.78, 0.76), amount=0.35),
                          dict(scale_m=8.0, tint=(0.74, 0.84, 0.7), amount=0.6, lo=0.35, hi=0.6,
                               where='smoothstep(0.15, 0.8, northness) * smoothstep(0.45, 0.8, occlusion)')],
                 # (bared lower only well above the treeline, from 2050 m to 2650 m: the first 500 m over the forest
                 # are alpine pasture, rock only where the walls stand)
                 weight=_cliff(50, 62, extra=' + 10*smoothstep(treeline_m + 100, treeline_m + 700, altitude '
                                             '+ 150*(fbm(400, 2) - 0.5))',
                               ribs=' * smoothstep(treeline_m + 300, treeline_m + 800, altitude)')),
            dict(name='snow', set='Snow010A', tile_m=3.0, colour='#eceff3', roughness=0.85, normal=0.6,
                 weight=_SNOW),
        ],
        options=dict(LANDSCAPE, damp_where='0.5*smoothstep(0.6, 0.9, wetness)',
                     tone='0.1*convex_20m - 0.22*smoothstep(0.8, 0.45, occlusion) - 0.08*concave_20m'),
        strata=dict(column='alpine_limestone', source='position', dip_deg=2.0, dip_azimuth_deg=200.0,
                    warp=[(400.0, 6.0), (60.0, 1.2)], facies_m=600.0, smear=(1.5, 0.6), parting=0.14,
                    relief_m=0.3, relief_shade=0.2),
        constants=dict(snowline_m=2800.0, treeline_m=1950.0),
        dressing=dict(models=[('rock_09', 0.0, 0.35), ('rock_07', 0.2, 0.9), ('boulder_01', 0.6, 4.0)],
                      colour='#8d8981',
                      density='2.2*smoothstep(0.2, 1.5, talus) + 1.4*rock_toe + 0.5*smoothstep(28, 36, slope)*(1 - plants)'
                              ' + 0.25*smoothstep(0.86, 0.96, flow)*smoothstep(10, 3, slope) + 0.01'),
    ),
    'desert_sandstone': dict(
        title='Desert sandstone: banded cliffs over talus slopes coloured by the beds above, slickrock rims, red soil '
              'and blackbrush on the benches, sand and gravel in the washes',
        layers=[
            # the desert soil weathered from the bed it lies on (a third the bed's colour), with darker and caliche-pale
            # patches at 5 m and 70 m, as tints (ratios), so a recipe's own soil colour keeps its hue: written as
            # absolute colours they were ratios to this palette's soil, and a redder soil (Monument Valley's sand,
            # Meteor Crater's Moenkopi) took a x(1.4, 1.9, 2.2) bleach over half its floor (the v4 pinkish-grey floor)
            dict(name='soil', set='sandy_gravel_02', tile_m=2.5, colour='#9c6e52', strata=0.35, weight='1',
                 patches=[dict(scale_m=5.0, tint=(0.72, 0.75, 0.81), amount=0.5),
                          dict(scale_m=70.0, tint=(1.22, 1.4, 1.55), amount=0.4, detail=4.0)]),
            # sand and gravel in the washes, and in ragged sheets on the sediment the rivers left (not a pasted blob:
            # the sheets are broken at 150 m too, so a filled basin does not print its own round outline, the pale
            # disc on Monument Valley's floor in the 11-12 aerial)
            # (silty darker patches, paler crusted flats and the fans' coarser lobes, so a filled floor hundreds of
            # metres across is not one sheet: Meteor Crater's floor rendered as a flat beige disc in the 11-13 view)
            dict(name='wash', set='gravelly_sand', tile_m=2.5, colour='#a88466', strata=0.2,
                 patches=[dict(scale_m=60.0, tint=(1.12, 1.13, 1.14), amount=0.5, detail=4.0),
                          dict(scale_m=14.0, tint=(0.84, 0.82, 0.8), amount=0.4, lo=0.48, hi=0.66),
                          dict(scale_m=4.0, tint=(0.88, 0.88, 0.86), amount=0.3)],
                 weight='max(smoothstep(0.80, 0.92, flow + 0.06*(fbm(30, 2) - 0.5)) * smoothstep(14, 4, slope), '
                        '0.85*smoothstep(0.4, 1.6, deposit + sand + 1.2*(fbm(30, 2) - 0.5) + 1.6*(fbm(150, 9) - 0.5)) '
                        '* smoothstep(20, 8, slope))'),
            # blackbrush and sage: grey-olive clumps a few metres across on the gentle ground (the sediment flats
            # too), more in moist hollows and fewer on bare rims, none in the channels (the flora family adds the
            # shrubs; this is the ground they make look grey-green from the air)
            # (sparse, as desert shrubs are: about a sixth of the gentle ground, fewer on a playa's thick fill, and a
            # grey-olive close to the soil's value so it reads as shrubs, not as camouflage dots; a scan of dry twigs
            # and grass under them, which near the camera reads as the litter under a bush, where a grass scan read as
            # lawn patches on the desert soil)
            # (shrub-sized: 1-2 m clumps from a 1.6 m noise, and at a distance neither the far read's magnified height
            # nor its magnified twig pattern: those drew 5-20 m flat, hard-edged blobs, moss or camouflage from eye
            # level on the plateau, 11-13 approach_walk)
            dict(name='scrub', set='burned_ground_01', tile_m=2.0, colour='#726e58', roughness=1.2, specular=0.12,
                 far_height=False, **_RUBBLE_FAR,
                 weight='smoothstep(25, 14, slope) * smoothstep(0.62, 0.78, fbm(1.6, 0) + 0.18*wetness + 0.08*northness '
                        '+ 0.2*concave_20m '
                        '- 0.25*convex_20m + 0.25*(fbm(180, 1) - 0.5) - 0.06) * smoothstep(0.93, 0.85, flow) '
                        '* (1 - 0.75*smoothstep(1.0, 6.0, deposit))'),
            # talus: the debris of the beds above (their colour, read 25 m up the column), on the repose slopes under
            # the cliffs and in their concave feet
            # (with blackbrush and grass speckling the gentler talus: the grey-green cast of the slopes between the
            # cliff bands in tw_03 and tw_07)
            dict(name='talus', set='rocks_ground_02', tile_m=3.0, colour='#8a5e48', projection='box', strata=0.75,
                 strata_offset_m=25.0, weight=_talus(21, 29), **_RUBBLE_FAR,
                 patches=[dict(scale_m=3.0, tint=(0.8, 0.88, 0.72), amount=0.45, lo=0.5, hi=0.64,
                               where='smoothstep(40, 30, slope + 6*(fbm(30, 23) - 0.5))')]),
            # slickrock: the bare, pale sandstone of the convex rims and bench edges (the overlook's rounded blocks),
            # and the bedrock pavement breaking through the thin soil of the benches and plateaus in patches tens to
            # hundreds of metres across, on the dry and convex ground, never on sediment (tw_07: pale rock between the
            # scrub of the rim country; a plateau of one soil read as one tiled material from the overlook)
            dict(name='slickrock', set='worn_rock_natural_01', tile_m=4.0, projection='box', strata=0.65, value=1.04,
                 bump_m=0.12,
                 weight='max(smoothstep(0.14, 0.4, convex_20m + 0.45*(fbm(22, 4) - 0.5)) * smoothstep(5, 14, slope) '
                        '* smoothstep(0.62, 0.35, wetness), 0.75*smoothstep(0.6, 0.76, fbm(120, 16) + 0.25*convex_20m '
                        '- 0.3*wetness + 0.12*(fbm(15, 17) - 0.5)) * smoothstep(0.5, 0.1, deposit + sand) '
                        '* smoothstep(22, 12, slope))'),
            # the banded cliffs: the column's colour at the stratigraphic height, the beds in relief (hard ledges
            # over soft recesses: the walls' ledge-and-recess striping, tw_03 and tw_07, where painted bands of
            # uniform colour read as stripes), debris and blackbrush lodged on the ledges, and desert varnish
            # streaking down from the pour-overs (flow) more than elsewhere
            dict(name='cliff', set='marble_cliff_02', tile_m=12.0, projection='box', strata=True, bump_m=0.5,
                 streaks=(2.5, 0.35), streaks_where='0.4 + 0.6*smoothstep(0.2, 0.4, flow + 0.15*(fbm(50, 21) - 0.5))',
                 ledges=dict(tint=(0.78, 0.8, 0.66), amount=0.55, scale_m=4.0, lo=0.42, hi=0.62),
                 weight=_cliff(37, 47)),
        ],
        options=dict(LANDSCAPE, damp=0.0, damp_where='0.7*smoothstep(0.9, 0.97, flow) * smoothstep(6, 2, slope)',
                     tone='0.08*convex_20m - 0.2*smoothstep(0.8, 0.45, occlusion) - 0.06*concave_20m'),
        strata=dict(column='colorado_plateau', source='attribute', warp=[(500.0, 4.0), (90.0, 1.2)],
                    facies_m=700.0, smear=(2.5, 2.0), parting=0.25, relief_m=0.8, relief_shade=0.16),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 0.8), ('namaqualand_boulder_04', 0.6, 5.0),
                              ('namaqualand_boulder_02', 0.6, 5.0), ('namaqualand_boulder_06', 0.6, 5.0)],
                      # pale pink-grey blocks of the rim and bench beds (the overlook's rubble, tw_04 and tw_07):
                      # the old dark red-brown read black on the red soil under make_sky
                      colour='#a3826c', size_m=(0.15, 3.0), alpha=2.1,
                      density='2.6*smoothstep(0.2, 1.5, talus) + 1.4*rock_toe + 0.8*smoothstep(22, 30, slope + '
                              '8*concave_20m) * smoothstep(46, 38, slope) + 0.3*smoothstep(0.1, 0.4, convex_20m) '
                              '* smoothstep(4, 12, slope) + 0.02'),
    ),
    'volcanic': dict(
        title='Volcanic: dark lava walls, red-black scoria, ash soil, grass and forest on the lower flanks, snow in the '
              'gullies',
        layers=[
            dict(name='ash soil', set='Ground051', tile_m=2.5, colour='#5a4d43', weight='1',
                 patches=[dict(scale_m=6.0, colour='#4c4038', amount=0.45),
                          dict(scale_m=120.0, colour='#6a5a4c', amount=0.4, detail=4.0)]),
            dict(name='grass', set='grass_ground', tile_m=2.5, colour='#5a5e39', roughness=1.3, specular=0.08,
                 weight='smoothstep(0.1, 0.42, plants + 0.25*(fbm(150, 0) - 0.5) + 0.08*(fbm(15, 1) - 0.5))',
                 patches=dict(scale_m=60.0, colour='#77754a', amount=0.5)),
            # forest on the lower flanks; the flat apron plains stay grass (pasture and fields on an inhabited volcano)
            # (the forest's edge on gentle ground broken by noise over a broad band of slope, the flattest aprons open:
            # a sharp 2.5-6 degree gate laid the forest-grass boundary along every few degrees of micro-relief, hard
            # dark blotches all round Crater Lake from the air, 11-13; clumped crowns for the canopy's grain)
            dict(name='forest', set='forrest_ground_03', tile_m=2.5, colour='#2c3524', normal=0.8, specular=0.08,
                 canopy=dict(crown_m=5.0, colour='#2c4426', light='#486238', gap='#141b10', height_m=1.8,
                             near_m=(120.0, 400.0), edge=True, clump_m=16.0, clump_height_m=5.0, clump_gap=0.25),
                 patches=[dict(scale_m=90.0, tint=(1.25, 1.25, 1.0), amount=0.5, detail=4.0, lo=0.5, hi=0.68),
                          dict(scale_m=30.0, tint=(0.75, 0.8, 0.76), amount=0.45)],
                 weight='smoothstep(0.35, 0.58, plants + 0.3*(fbm(400, 2) - 0.5) + 0.1*(fbm(40, 3) - 0.5) '
                        '+ 0.06*(fbm(12, 17) - 0.5)) * smoothstep(0.5, 7.0, slope + 5*(fbm(300, 18) - 0.5))'),
            # bare scoria and ash where nothing grows (above the treeline, on the young cones)
            dict(name='scoria', set='Gravel024', tile_m=2.0, colour='#4f4039', **_RUBBLE_FAR,
                 weight='smoothstep(0.12, 0.03, plants + 0.06*(fbm(80, 4) - 0.5)) * smoothstep(5, 12, slope)'),
            # (the flows' edges broken at 40 m and 8 m, as a lobate front is, and the older flows' surface taken back
            # in patches by the cover around them: Aokigahara's forest stands on Fuji's 864 flow; a flow drawn as
            # one hard-edged grey plate read as a parking lot from the air)
            dict(name='lava rock', set='Rock031', tile_m=6.0, colour='#3a3532', projection='box', bump_m=0.3,
                 weight='max(' + _cliff(36, 46) + ', smoothstep(0.2, 0.6, lava + 0.35*(fbm(40, 13) - 0.5) '
                        '+ 0.15*(fbm(8, 14) - 0.5)) * (1 - 0.7*smoothstep(0.55, 0.8, fbm(150, 15) + 0.2*wetness)))'),
            dict(name='snow', set='Snow010A', tile_m=3.0, colour='#eceff3', roughness=0.85, normal=0.6, weight=_SNOW),
        ],
        options=dict(LANDSCAPE, damp=0.3,
                     tone='0.06*convex_20m - 0.18*smoothstep(0.8, 0.45, occlusion) - 0.06*concave_20m'),
        # (Fuji's snowline from autumn to spring, the season of the photographs: its upper cone white, the snow
        # running down the gullies to about 2000 m; at 3300 m the cone wore a small white cap)
        constants=dict(snowline_m=2700.0, treeline_m=2400.0),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 1.0), ('boulder_01', 0.6, 4.0)], colour='#3d3633',
                      density='1.4*smoothstep(0.2, 1.5, talus) + 1.0*rock_toe + 0.3*smoothstep(0.1, 0.02, plants)'
                              ' + 0.6*smoothstep(0.2, 0.6, lava) + 0.02'),
    ),
    'dunes': dict(
        title='Dunes: wind-rippled sand, damp interdune flats, crusted pans, grass on the stable sand sheet',
        layers=[
            # plain sand with wind ripples in the material (design 4.6: ripples belong in the material): 12 cm crests
            # across the wind, a steep lee side, faded out before they alias; paler crests and darker, coarser
            # troughs at the dune scale
            # (golden tan, Great Sand Dunes' sand: at #ad9677 it read grey-green under the blue sky)
            dict(name='sand', set='sand_03', tile_m=2.0, colour='#c2a37a', weight='1', contrast=0.5,
                 # (8 mm high, faded out over 8-25 m: at 15 mm their crests read as painted parallel lines on the crest
                 # view of 11-12)
                 ripples=dict(wavelength_m=0.14, height_m=0.008, azimuth_deg=45.0, fade_m=(8.0, 25.0)),
                 # paler wind-scoured crests, darker coarser sand in the troughs at the dune scale (tints, so a
                 # recipe's own sand colour keeps its hue)
                 patches=[dict(scale_m=None, tint=(1.1, 1.08, 1.06), amount=0.6, where='convex_20m'),
                          dict(scale_m=40.0, tint=(0.88, 0.86, 0.84), amount=0.35, detail=4.0)]),
            # damp sand along the creek and in interdune hollows (the wetness index is high on every flat, so it is
            # not the cue): flow for the creek, concavity for the hollows
            dict(name='damp sand', set='gravelly_sand', tile_m=2.5, colour='#8b7b67',
                 weight='max(smoothstep(0.88, 0.97, flow), 0.6*smoothstep(0.5, 0.9, concave_20m + 0.2*(fbm(60, 0) - 0.5))) '
                        '* smoothstep(5, 1.5, slope)'),
            # the interdune floor: pale gravel and clay pans where the sand runs out between the dunes (the Namib's
            # interdunes), crusted in the hollows
            # (the sand thins out onto the floor over metres of thickness, not at one: a dune's toe is a ragged
            # sand sheet over the gravel, so the edge spreads over 0.2-2.5 m of sand broken at 40 m and 8 m)
            dict(name='crust', set='dry_ground_01', tile_m=4.0, colour='#aa9c88',
                 patches=dict(scale_m=30.0, colour='#9c8a72', amount=0.5),
                 weight='max(smoothstep(0.35, 0.75, concave_20m) * smoothstep(6, 2, slope) * smoothstep(0.35, 0.6, '
                        'fbm(60, 1)), smoothstep(2.5, 0.2, sand + 1.2*(fbm(40, 0) - 0.5) + 0.5*(fbm(8, 5) - 0.5)) '
                        '* smoothstep(10, 3, slope))'),
            # sparse dry grass in clumps on the stable sand sheet and the interdune floor (not a lawn: straw-coloured
            # tufts with the ground between them)
            # (tufts from a 1.8 m noise, sparser: from a 4 m one they lay as flat olive patches 5-15 m across on the
            # interdune floor, camouflage from the crest view, 11-13)
            dict(name='grass', set='withered_grass', tile_m=2.0, colour='#9c9468', roughness=1.3, specular=0.08,
                 far_height=False, **_RUBBLE_FAR,
                 weight='smoothstep(0.3, 0.6, plants + 0.4*(fbm(30, 2) - 0.5)) * smoothstep(0.6, 0.78, fbm(1.8, 3))'),
        ],
        options=dict(LANDSCAPE, damp=0.0, specular=0.35, tone='0.06*convex_20m - 0.05*concave_20m'),
        dressing=dict(models=[('rock_09', 0.0, 2.0)], colour='#7c7062',
                      density='0.004*smoothstep(0.35, 0.75, concave_20m)*smoothstep(6, 2, slope)'),
    ),
    'badlands': dict(
        title='Badlands: pale banded mudstone with runnels, crusted popcorn clay, gravel washes, prairie',
        layers=[
            # mixed-grass prairie: golden grass with greener swales, paler dry flats and darker tufts (bl_01, bl_04,
            # bl_07), so the plain in front of the Wall is not one tiled lawn
            dict(name='prairie', set='grass_ground', tile_m=2.5, colour='#9a8f5e', roughness=1.3, specular=0.08,
                 weight='1', patches=[dict(scale_m=6.0, colour='#78783f', amount=0.55),
                                      dict(scale_m=25.0, colour='#b6a776', amount=0.5),
                                      dict(scale_m=80.0, colour='#6b723e', amount=0.45, detail=4.0)]),
            # the popcorn crust of swelling clay: the crack scan at a small tile reads as crumbs, not mud polygons; bare
            # wherever the slope is past what grass holds and on the mound crests; the colour of the beds it weathers
            # from. Bare on the sediment only where it is young: the aprons at the walls' feet and along the washes; the
            # old filled flats of the tables are sod (a filled basin read as a pale pasted blob with a hard edge)
            dict(name='clay', set='mud_cracked_dry_03', tile_m=0.8, colour='#bfae95', strata=0.5, normal=0.7,
                 weight='max(smoothstep(8, 15, slope + 8*(fbm(12, 0) - 0.5)), smoothstep(0.15, 0.45, convex_20m), '
                        'smoothstep(0.3, 1.0, deposit) * smoothstep(14, 5, slope) * 0.8 '
                        '* smoothstep(0.3, 0.7, rock_toe + 0.5*smoothstep(0.6, 0.85, flow) + 0.4*(fbm(60, 6) - 0.5)))'),
            dict(name='wash gravel', set='rocks_ground_02', tile_m=2.0, colour='#a8957c', **_RUBBLE_FAR,
                 weight='smoothstep(0.75, 0.9, flow + 0.06*(fbm(25, 2) - 0.5)) * smoothstep(12, 4, slope)'),
            # the banded walls: pastel beds dragged down the runnels (strata smear), thin dark partings
            dict(name='mudstone', set='excavated_soil_wall', tile_m=4.0, projection='box', strata=True, bump_m=0.15,
                 streaks=(0.8, 0.22),
                 weight='smoothstep(21, 31, slope + 8*(fbm(20, 3) - 0.5) + 6*convex_20m - 4*concave_20m)'),
        ],
        options=dict(LANDSCAPE, damp=0.0, tone='0.06*convex_20m - 0.14*smoothstep(0.8, 0.45, occlusion)'),
        strata=dict(column='badlands', source='attribute', warp=[(250.0, 1.5), (40.0, 0.4)], facies_m=300.0,
                    smear=(0.8, 1.6), parting=0.12, relief_m=0.2, relief_shade=0.08),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 2.0)], colour='#a68e72',
                      density='0.25*smoothstep(0.75, 0.92, flow)*smoothstep(12, 4, slope) + 0.06*rock_toe'),
    ),
    'karst': dict(
        title='Karst: grey limestone walls streaked dark, dense forest on the towers, paddies and red soil fields on '
              'the plain',
        layers=[
            # the plain is paddies and fields, field-sized patches of young and ripe green
            dict(name='paddies', set='Grass004', tile_m=2.5, colour='#5b7834', roughness=1.3, specular=0.3, weight='1',
                 patches=[dict(scale_m=60.0, colour='#7d8a3e', amount=0.6),
                          dict(scale_m=8.0, colour='#4d6a2e', amount=0.4)]),
            # ploughed red soil fields: whole fields (cells), straight boundaries
            dict(name='red soil', set='red_laterite_soil_stones', tile_m=2.0, colour='#8a5a41',
                 weight='smoothstep(0.8, 0.81, cells(110, 3)) * smoothstep(7, 3, slope)'),
            # the towers' forest: broadleaf crowns on every flank the rock lets them hold
            dict(name='forest', set='Ground037', tile_m=2.0, colour='#3c4d2c', roughness=1.3, specular=0.08,
                 # (subtropical broadleaf: a lusher, lighter green than the alpine spruce, as the Li River photographs;
                 # the scrub forest clinging to the towers is fine-grained, small crowns in clumps, where 6 m crowns
                 # read as big round blobs on the v3 towers)
                 canopy=dict(crown_m=3.5, colour='#456b37', light='#6b8f4c', gap='#22301a', height_m=1.5,
                             near_m=(120.0, 400.0), edge=True, clump_m=11.0, clump_height_m=3.0, clump_gap=0.18),
                 patches=[dict(scale_m=60.0, tint=(1.2, 1.22, 1.0), amount=0.5, detail=4.0, lo=0.5, hi=0.68),
                          dict(scale_m=20.0, tint=(0.8, 0.84, 0.8), amount=0.4)],
                 weight='smoothstep(9, 17, slope + 4*(fbm(40, 4) - 0.5))'),
            # limestone walls with the dark vertical streaks karst towers carry, bedded grey: only the sheerest faces
            # (Guilin's towers are clothed in forest that clings to every ledge; the grey shows where they are
            # vertical, overhanging or freshly fallen: the photographs' towers are mostly green, a fifth or so bare.
            # From 68 degrees the v3 towers, whose walls the solver stands at 70-85, were nearly all bare grey)
            dict(name='limestone', set='Rock019', tile_m=10.0, colour='#8f8c85', projection='box', bump_m=0.4,
                 strata=True, streaks=(3.5, 0.5, 0.52, 0.72),
                 weight=_cliff(77, 86, ribs=' * 0')),
        ],
        options=dict(LANDSCAPE, tone='0.06*convex_20m - 0.18*smoothstep(0.8, 0.45, occlusion)'),
        strata=dict(column='karst_limestone', source='position', warp=[(300.0, 4.0), (40.0, 0.8)], facies_m=400.0,
                    smear=(1.5, 1.5), parting=0.2, relief_m=0.4, relief_shade=0.1),
        dressing=dict(models=[('rock_07', 0.0, 0.9), ('boulder_01', 0.6, 4.0)], colour='#8a8781',
                      density='1.0*rock_toe + 0.3*smoothstep(0.2, 1.5, talus)'),
    ),
    'chalk_coast': dict(
        title='Chalk coast: white chalk cliffs, flint shingle, a green wave-cut platform, downland turf',
        layers=[
            # downland turf with field-sized patches of arable and pasture
            dict(name='downland', set='Grass004', tile_m=2.5, colour='#6a7c44', roughness=1.3, specular=0.08,
                 weight='1', patches=[dict(scale_m=150.0, colour='#8b8a4f', amount=0.5),
                                      dict(scale_m=9.0, colour='#5c7038', amount=0.4)]),
            # flint shingle on the beach (height is metres above sea level on a coast)
            dict(name='shingle', set='Gravel041', tile_m=2.0, colour='#968e80', **_RUBBLE_FAR,
                 weight='max(smoothstep(0.1, 0.4, water), smoothstep(4.0, 1.5, height + 0.8*(fbm(30, 0) - 0.5)) '
                        '* smoothstep(10, 4, slope))'),
            # the wave-cut chalk platform, green with weed, only at the cliff foot near sea level
            dict(name='platform', set='Rock019', tile_m=6.0, colour='#8f9682',
                 weight='smoothstep(0.8, 0.1, height) * smoothstep(0.1, 0.4, rock_toe)'),
            dict(name='chalk', set='Rock019', tile_m=8.0, colour='#e3dfd5', projection='box', bump_m=0.3,
                 weight='smoothstep(40, 55, slope + 6*(fbm(40, 1) - 0.5))'),
        ],
        options=dict(LANDSCAPE),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 2.0)], colour='#d8d3c8',
                      density='1.5*rock_toe*smoothstep(4, 0.5, height) + 0.02'),
    ),
    'farmland': dict(
        title='Farmland: fields of grass, ploughed soil and ripe crop with straight boundaries',
        # each field takes one crop: about a quarter soil, a third ripe crop, the rest grass. The fields are cells of
        # a partition of (x, y, 14 z): about 500 m along the contours and 36 m of height across them, so on the hills
        # they run around the slopes as the Palouse's are ploughed (palouse_hills_01, 04), where a flat (x, y)
        # partition laid straight-edged polygons over the hills like camouflage; each boundary stays a clean line
        layers=[
            dict(name='grass', set='Grass004', tile_m=2.5, colour='#6b7d3c', roughness=1.3, specular=0.08, weight='1',
                 patches=[dict(scale_m=40.0, colour='#7f8a45', amount=0.4),
                          dict(scale_m=7.0, colour='#5e7236', amount=0.35)]),
            dict(name='soil', set='Ground048', tile_m=2.5, colour='#7a6248',
                 weight='smoothstep(0.255, 0.245, cells(500, 1, 14))'),
            dict(name='crop', set='grass_ground', tile_m=2.5, colour='#b39a5c', roughness=1.3, specular=0.08,
                 weight='smoothstep(0.645, 0.655, cells(500, 1, 14))',
                 patches=dict(scale_m=None, colour='#c9b27a', amount=0.6,
                              where='smoothstep(0.82, 0.83, cells(500, 1, 14))')),
        ],
        options=dict(LANDSCAPE),
        dressing=dict(models=[('rock_09', 0.0, 1.0)], colour='#7a6a5a', density='0.0'),
    ),
    'meadow': dict(
        title="Meadow: the old meadow film's soil, withered thatch on the high ground, sand on the banks",
        # the meadow film's soil, its layer weights written as masks:
        # mid = smooth((h - high_start + breakup * amplitude) / (0.5 amplitude)), steep over 18-26 degrees
        layers=[
            dict(name='soil', set='Ground106', tile_m=2.3, roughness=1.35, weight='1'),
            dict(name='thatch', set='withered_grass', tile_m=2.0, tint=(0.6, 0.58, 0.52),
                 weight='smoothstep(-0.2, 1.05, height + 2.5*(noise(6.7) - 0.5))'),
            dict(name='bank', set='coast_sand_01', tile_m=2.6, weight='smoothstep(18.2, 25.8, slope)'),
        ],
        options=dict(),
        dressing=dict(models=[('rock_09', 0.0, 1.0)], colour=None, density='0.002'),
    ),
}

# the palette a recipe takes with palette='auto'
RECIPE_PALETTES = {
    'fluvial_range': 'alpine', 'alpine_valley': 'alpine', 'stratovolcano': 'volcanic', 'caldera': 'volcanic',
    'cinder_cones': 'volcanic', 'impact_crater': 'desert_sandstone', 'canyon': 'desert_sandstone',
    'incised_meanders': 'desert_sandstone', 'mesas_buttes': 'desert_sandstone', 'badlands': 'badlands',
    'dunes': 'dunes', 'tower_karst': 'karst', 'sea_cliffs': 'chalk_coast', 'rolling_hills': 'farmland',
    'meadow': 'meadow',
}

# the slickrock of a plain whose floor is soil or sand over the bedrock (Meteor Crater's Moenkopi plain, Monument
# Valley's sand floor): the convex rims as in the palette, the bedrock pavement fewer and weaker than on Toroweap's
# rim country (the canyon's term painted these floors with pale splats, 11-13)
_SLICKROCK_SPARSE = ('max(smoothstep(0.14, 0.4, convex_20m + 0.45*(fbm(22, 4) - 0.5)) * smoothstep(5, 14, slope) '
                     '* smoothstep(0.62, 0.35, wetness), 0.5*smoothstep(0.68, 0.82, fbm(120, 16) + 0.25*convex_20m '
                     '- 0.3*wetness + 0.12*(fbm(15, 17) - 0.5)) * smoothstep(0.5, 0.1, deposit + sand) '
                     '* smoothstep(22, 12, slope))')

# what a recipe's 'auto' palette takes on top of its palette (merged into it): the impact crater's walls are Meteor
# Crater's target rock read at object z (the recipe writes no zs). The impact turned the beds up at the rim, so the
# Moenkopi's top (zs 362) sits at the rim crest, about 50 m over the plain at 1683 m: the Kaibab's buff ledges make the
# upper wall, the Coconino the lower wall under its talus, as in the photographs from the rim
RECIPE_LOOKS = {
    'impact_crater': dict(strata=dict(column='meteor_crater', source='position', z_offset_m=362.0 - 1741.0,
                                      warp=[(400.0, 3.0), (60.0, 0.8)], facies_m=500.0, smear=(2.0, 1.5),
                                      parting=0.15, looks=False, relief_m=0.5, relief_shade=0.1),
                          # the plain's red Moenkopi soil and its dry grass and shrubs (meteor_crater_02_plain_north)
                          layers={'soil': dict(colour='#9a6248', strata=0.15,
                                               patches=[dict(scale_m=5.0, tint=(0.8, 0.8, 0.84), amount=0.45),
                                                        dict(scale_m=70.0, tint=(1.14, 1.2, 1.26), amount=0.4,
                                                             detail=4.0)]),
                                  # the plain's bedrock showing through: weathered red-brown Moenkopi ledges, a few
                                  # (plain_north's foreground ledge), where the canyon's pale pavement term painted
                                  # the whole plain with white splats in the 11-13 aerial (the Kaibab's buff at the
                                  # plain's level, twice the red soil's brightness)
                                  'slickrock': dict(colour='#9c7d66', strata=0.3, weight=_SLICKROCK_SPARSE),
                                  'scrub': dict(colour='#8a7c58')}),
    # Monument Valley's floor is orange-red sand blown off the De Chelly (mv_02, mv_04, mv_05), not the pale Cedar Mesa
    # the floor is stripped to
    # (its shrubs are dark dots on the orange sand, a tenth of the floor at most: the palette's grey-olive scrub, a
    # sixth of the ground in 3.5 m speckle, averaged to a grey haze over the whole floor from the air)
    # (the floor's tones: paler wind-sorted sand in sheets and darker gravelly lag, not caliche: mv_04, mv_05)
    'mesas_buttes': dict(layers={'slickrock': dict(colour='#b0704c', strata=0.3, weight=_SLICKROCK_SPARSE),
                                 'soil': dict(colour='#a6623f', strata=0.2,
                                              patches=[dict(scale_m=6.0, tint=(0.84, 0.82, 0.82), amount=0.45),
                                                       dict(scale_m=90.0, tint=(1.12, 1.14, 1.16), amount=0.5,
                                                            detail=4.0),
                                                       dict(scale_m=25.0, tint=(0.9, 0.86, 0.84), amount=0.35)]),
                                 'wash': dict(colour='#b07a52', strata=0.1),
                                 'scrub': dict(colour='#5c5741',
                                               weight='smoothstep(25, 14, slope) * smoothstep(0.74, 0.88, fbm(1.6, 0) '
                                                      '+ 0.08*wetness + 0.2*concave_20m - 0.25*convex_20m '
                                                      '+ 0.25*(fbm(180, 1) - 0.5) - 0.06) '
                                                      '* smoothstep(0.93, 0.85, flow) '
                                                      '* (1 - 0.75*smoothstep(1.0, 6.0, deposit))')}),
    # the star dunes recipe is judged against the Namib: its iron-red sand over the interdune's gravel and dry grass
    # (the review's Dune 45 and crest photographs: namib_star_dunes_02, a brown gravel floor under straw grass where
    # the red sand runs out; the pale grey-beige crust of 11-12 drew every dune's toe as a hard orange-on-grey line)
    'dunes': dict(layers={'sand': dict(colour='#c47c4f'), 'damp sand': dict(colour='#9a6447'),
                          'crust': dict(colour='#a07a5e', patches=dict(scale_m=30.0, colour='#8e6e58', amount=0.5)),
                          'grass': dict(colour='#b0a070')}),
    # the river-carved range is judged against the San Gabriel Mountains: chaparral, a dense dark olive brush on every
    # slope it can hold, grey-brown decomposed granite and pale outcrops on the ridges and the steepest faces, golden
    # dry grass on the gentle ground, pale washes; no snow (san_gabriel_mountains_01-03). The alpine palette's bedded
    # limestone and snow painted the whole range white (the 11-12 aerial). palette='alpine' keeps the alpine look
    'fluvial_range': dict(constants=dict(snowline_m=4500.0, treeline_m=2900.0), layers={
        'pasture': dict(colour='#a08d62', patches=[dict(scale_m=7.0, colour='#8f7f58', amount=0.5),
                                                   dict(scale_m=90.0, colour='#b09c70', amount=0.45, detail=4.0)]),
        'scree': dict(colour='#958a7a'),
        'gravel': dict(colour='#a8a090'),
        # chaparral: small crowns packed close, the soil between them showing grey-brown; on slopes it can hold,
        # thinned on the convex ridges and broken where the decomposed granite is bare
        'forest': dict(colour='#6a6250', canopy=dict(crown_m=2.6, colour='#3e4430', light='#5c5f40', gap='#6a604e',
                                                     height_m=0.8, near_m=(80.0, 300.0), edge=True),
                       weight='smoothstep(0.3, 0.55, plants + 0.35*smoothstep(10, 26, slope) + 0.3*(fbm(220, 3) - 0.5) '
                              '+ 0.12*(fbm(30, 4) - 0.5) - 0.3*convex_20m) * smoothstep(5, 10, slope) '
                              '* smoothstep(52, 44, slope + 4*(fbm(30, 5) - 0.5))',
                       patches=[dict(scale_m=60.0, tint=(1.15, 1.08, 0.95), amount=0.5, detail=4.0, lo=0.5, hi=0.68),
                                dict(scale_m=25.0, tint=(0.82, 0.84, 0.82), amount=0.4)]),
        # granite and gneiss: grey-brown, no bedding
        'rock': dict(colour='#8f877b', strata=False, streaks=(3.0, 0.25, 0.6, 0.78),
                     patches=[dict(scale_m=60.0, tint=(1.1, 1.0, 0.86), amount=0.5, detail=4.0, lo=0.5, hi=0.7),
                              dict(scale_m=11.0, tint=(0.8, 0.8, 0.78), amount=0.35)])}),
    # a cinder-cone field on a dry plateau (SP Crater, northern Arizona, 2000 m): black and red-black cinders on the
    # cones, black basalt flows, a pale grey-brown cinder plain under straw grass with juniper and pinyon scattered on
    # it (sp_crater_01 from the air: a black cone and its flow on a pale plain). The volcanic palette's wet look
    # (green grass, closed forest) dressed the whole field in forest
    'cinder_cones': dict(layers={
        'ash soil': dict(colour='#8a8070', patches=[dict(scale_m=6.0, colour='#7a7062', amount=0.45),
                                                    dict(scale_m=120.0, colour='#9a8f7a', amount=0.4, detail=4.0)]),
        'grass': dict(colour='#a49a76', weight='smoothstep(0.1, 0.36, plants + 0.25*(fbm(150, 0) - 0.5) '
                                               '+ 0.08*(fbm(15, 1) - 0.5)) * smoothstep(24, 13, slope)',
                      patches=dict(scale_m=60.0, colour='#b4a985', amount=0.5)),
        # juniper and pinyon: single dark crowns scattered over the plain (the canopy's trees in or out one by one
        # at a coverage of a third or less), none on the cones' loose cinder flanks
        'forest': dict(colour='#5a5444', canopy=dict(crown_m=5.0, colour='#323b29', light='#465036', gap='#5e574a',
                                                     height_m=1.2, near_m=(80.0, 300.0), edge=True),
                       weight='0.38*smoothstep(0.35, 0.75, fbm(160, 2) + 0.25*wetness - 0.2*convex_20m) '
                              '* smoothstep(16, 8, slope)'),
        # the cones' cinders: every flank at repose and the crater rims, red-black, oxidised redder on the youngest
        'scoria': dict(colour='#3a302c', weight='max(smoothstep(13, 21, slope + 6*(fbm(40, 4) - 0.5)), '
                                                'smoothstep(0.3, 0.7, peaks))',
                       patches=dict(scale_m=90.0, colour='#5a3a30', amount=0.5, lo=0.55, hi=0.72)),
        'lava rock': dict(colour='#2b2725')}),
}

# a real DEM's palette (the real_place recipe), its strata (absolute metres: the reference DEMs carry their own
# heights) and the mask parameters that make its snow and tree line (masks.MaskParams fields, altitude in metres)
PLACES = {
    'lauterbrunnen': dict(palette='alpine', mask_params=dict(snowline_m=2750.0, treeline_m=1950.0)),
    'grand_canyon_toroweap': dict(
        palette='desert_sandstone', mask_params=dict(treeline_m=2200.0),
        # the Toroweap fault: the west side is down about 170 m (the Esplanade bench at 1200 m there, 1370 m east)
        strata=dict(column='toroweap', source='attribute', looks=False,
                    faults=[dict(x=-1450.0, y=0.0, strike_deg=8.0, throw_m=170.0, down='west', width_m=60.0)],
                    warp=[(300.0, 4.0), (6.0, 0.6)])),
    'mount_fuji': dict(palette='volcanic', mask_params=dict(snowline_m=2700.0, treeline_m=2450.0)),
    'crater_lake': dict(palette='volcanic', mask_params=dict(treeline_m=2400.0)),
    'great_sand_dunes': dict(palette='dunes', mask_params=dict()),
    'namib_star_dunes': dict(palette='dunes', mask_params=dict()),
    'badlands_sd': dict(palette='badlands', mask_params=dict(),
                        strata=dict(column='badlands_cedar_pass', source='attribute', looks=False,
                                    warp=[(250.0, 1.5), (4.0, 0.25)])),
    'badlands_sd_detail': dict(palette='badlands', mask_params=dict(),
                               strata=dict(column='badlands_cedar_pass', source='attribute', looks=False,
                                           warp=[(250.0, 1.5), (4.0, 0.25)])),
    'guilin_karst': dict(palette='karst', mask_params=dict()),
    'seven_sisters': dict(palette='chalk_coast', mask_params=dict(sea_level=0.0)),
    'palouse_hills': dict(palette='farmland', mask_params=dict()),
    'monument_valley': dict(palette='desert_sandstone', mask_params=dict(),
                            strata=dict(column='monument_valley', source='attribute', z_offset_m=1500.0)),
    'meteor_crater': dict(palette='desert_sandstone', mask_params=dict(),
                          strata=dict(column='meteor_crater', source='attribute', z_offset_m=352.0 - 1700.0,
                                      looks=False)),
}

# ------------------------------------------------------------------------------ the expression language ---

_FUNCS = {'smoothstep': (3, 3), 'min': (2, 99), 'max': (2, 99), 'clamp': (3, 3), 'abs': (1, 1), 'pow': (2, 2),
          'mix': (3, 3), 'noise': (1, 2), 'fbm': (1, 2), 'cells': (1, 3)}

# names that stand for an expression over the masks (expanded when parsed)
DERIVED = {
    # altitude above the sea (the snowline and treeline are altitudes): the terrain's height plus its base elevation
    'altitude': 'height + base_elevation_m',
    # loose cover that hides the bedrock: sediment, talus and sand thicker than 0.1-1 m
    'cover': 'smoothstep(0.1, 1.0, deposit + talus + sand)',
    # bare bedrock from the geometry alone: slope over the rock angle (lower on convex ground, higher in hollows),
    # under no loose cover. (The masks package's `rock` also counts ground eroded more than 20 m as rock, which on an
    # eroded landform is nearly all of it.)
    'bare': 'smoothstep(34, 46, slope + 10*convex_20m - 8*concave_20m) * (1 - cover)',
    # where plants can grow, from masks every landform carries right: not too steep, moist, open to the sky (not in
    # a slot), not on talus, sand or snow, thinned above the treeline (south faces carry it higher). The masks
    # package's `vegetation` multiplies by its `rock`, which reads nearly 1 over a whole eroded canyon.
    'plants': '(1 - smoothstep(32, 48, slope)) * (0.35 + 0.65*wetness) * smoothstep(0.3, 0.7, occlusion) '
              '* (1 - snow) * (1 - smoothstep(0.3, 2.0, talus)) * (1 - smoothstep(0.1, 1.0, sand)) '
              '* (1 - 0.8*smoothstep(treeline_m - 120, treeline_m + 120, altitude + 100*northness))',
}
_OPS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/'}


class ExprError(ValueError):
    pass


def parse(src):
    """A mask expression -> a tuple tree: ('num', v) | ('mask', name) | ('const', name) | ('op', '+-*/', a, b) |
    ('neg', a) | ('call', fname, [args]). Raises ExprError naming what it can't read."""
    if isinstance(src, (int, float)):
        return ('num', float(src))
    try:
        tree = ast.parse(str(src).strip(), mode='eval')
    except SyntaxError as e:
        raise ExprError(f'mask expression {src!r}: {e.msg}') from None

    def conv(n):
        if isinstance(n, ast.Expression):
            return conv(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return ('num', float(n.value))
        if isinstance(n, ast.Name):
            if n.id in DERIVED:
                return parse(DERIVED[n.id])
            if n.id in CONSTANTS:
                return ('const', n.id)
            return ('mask', n.id)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            a = conv(n.operand)
            return a if isinstance(n.op, ast.UAdd) else (('num', -a[1]) if a[0] == 'num' else ('neg', a))
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return ('op', _OPS[type(n.op)], conv(n.left), conv(n.right))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
            f = n.func.id
            if f not in _FUNCS:
                raise ExprError(f'mask expression {src!r}: unknown function {f!r}; the functions are '
                                f'{", ".join(sorted(_FUNCS))}')
            lo, hi = _FUNCS[f]
            if not lo <= len(n.args) <= hi:
                raise ExprError(f'mask expression {src!r}: {f}() takes {lo}' + (f'-{hi}' if hi != lo else '')
                                + f' arguments, got {len(n.args)}')
            args = [conv(a) for a in n.args]
            if f in ('noise', 'fbm', 'cells') and any(a[0] != 'num' for a in args):
                raise ExprError(f'mask expression {src!r}: {f}(scale_m[, seed]) takes numbers')
            return ('call', f, args)
        raise ExprError(f'mask expression {src!r}: {ast.dump(n)[:60]} is not part of the language '
                        f'(numbers, mask names, + - * /, and {", ".join(sorted(_FUNCS))})')
    return conv(tree)


def tree_key(t):
    """A hashable key of an expression tree (its call arguments as tuples): the material shares the nodes of equal
    sub-expressions (a derived name every layer reads is built once)."""
    if t[0] == 'call':
        return ('call', t[1], tuple(tree_key(a) for a in t[2]))
    if t[0] == 'op':
        return ('op', t[1], tree_key(t[2]), tree_key(t[3]))
    if t[0] == 'neg':
        return ('neg', tree_key(t[1]))
    return t


def names_in(expr):
    """The mask names an expression (string or tree) reads (constants are not masks)."""
    t = parse(expr) if not isinstance(expr, tuple) else expr
    out = set()

    def walk(n):
        if n[0] == 'mask':
            out.add(n[1])
        elif n[0] == 'op':
            walk(n[2])
            walk(n[3])
        elif n[0] == 'neg':
            walk(n[1])
        elif n[0] == 'call':
            for a in n[2]:
                walk(a)
    walk(t)
    return out


def known_mask(name):
    """None if `name` is a mask the masks package makes (masks.parse_name), else an error message naming the
    nearest valid ones."""
    try:
        from .. import masks as _M
    except Exception:                                    # pragma: no cover - the masks package is part of the family
        return None
    try:
        _M.parse_name(name)
        return None
    except KeyError as e:
        return str(e).strip('"\'')


def _smooth(e0, e1, x):
    if e1 == e0:
        return (np.asarray(x) >= e0).astype(np.float64)
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hash2(ix, iy, seed):
    """A 32-bit integer hash of lattice points -> float 0..1 (numpy, vectorised)."""
    h = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + int(seed) * 2147483647) & 0xffffffff
    h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
    h = h ^ (h >> 16)
    return (h & 0xffffff).astype(np.float64) / float(0xffffff)


def value_noise(x, y, scale_m, seed=0, octaves=2, gain=0.5, stretch=1.6):
    """A world-space value noise of about 0..1 (mean 0.5), features `scale_m` metres across: the numpy side of the
    language's noise() (octaves 2) and fbm() (octaves 5) (the scatter's; the material uses the shader's noise)."""
    x = np.asarray(x, np.float64) / max(scale_m, 1e-9)
    y = np.asarray(y, np.float64) / max(scale_m, 1e-9)
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        ix, iy = np.floor(x), np.floor(y)
        fx, fy = x - ix, y - iy
        ux, uy = fx * fx * fx * (fx * (fx * 6 - 15) + 10), fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        s = seed * 31 + o * 17
        v00, v10 = _hash2(ix, iy, s), _hash2(ix + 1, iy, s)
        v01, v11 = _hash2(ix, iy + 1, s), _hash2(ix + 1, iy + 1, s)
        v = (v00 * (1 - ux) + v10 * ux) * (1 - uy) + (v01 * (1 - ux) + v11 * ux) * uy
        tot = tot + amp * v
        norm += amp
        amp *= gain
        x, y = x * 2.0 + 17.3, y * 2.0 - 9.1
    v = tot / norm
    return np.clip(0.5 + (v - 0.5) * stretch, 0.0, 1.0)  # stretch the octaves' narrowed spread back toward 0..1


def voronoi_cells(x, y, scale_m, seed=0, z=None, z_stretch=0.0):
    """A random value 0..1 per cell of a world-space Voronoi partition, cells about scale_m across (the nearest of
    jittered lattice points): the numpy side of the language's cells(), for fields and patches with straight
    boundaries. With z (the ground's height, metres) and z_stretch k > 0 the partition is of (x, y, k z) in 3D: a cell
    spans scale_m along a contour but only scale_m / k of height across it, so on a hillside the cells run along the
    contours (fields ploughed around a hill, the Palouse). The material uses Blender's Voronoi, so the two partitions
    differ."""
    gx = np.asarray(x, np.float64) / max(scale_m, 1e-9)
    gy = np.asarray(y, np.float64) / max(scale_m, 1e-9)
    three = z is not None and z_stretch > 0.0
    gz = np.asarray(z, np.float64) * float(z_stretch) / max(scale_m, 1e-9) if three else None
    ix, iy = np.floor(gx), np.floor(gy)
    iz = np.floor(gz) if three else None
    best = np.full(gx.shape, np.inf)
    val = np.zeros(gx.shape)
    for dk in ((-1, 0, 1) if three else (0,)):
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                cx, cy = ix + di, iy + dj
                if three:
                    cz = iz + dk
                    salt = (cz.astype(np.int64) * 7919) % 104729
                    px = cx + _hash2(cx, cy + salt, seed * 13 + 1)
                    py = cy + _hash2(cx, cy + salt, seed * 13 + 2)
                    pz = cz + _hash2(cx, cy + salt, seed * 13 + 4)
                    d = (gx - px) ** 2 + (gy - py) ** 2 + (gz - pz) ** 2
                    v = _hash2(cx, cy + salt, seed * 13 + 3)
                else:
                    px = cx + _hash2(cx, cy, seed * 13 + 1)
                    py = cy + _hash2(cx, cy, seed * 13 + 2)
                    d = (gx - px) ** 2 + (gy - py) ** 2
                    v = _hash2(cx, cy, seed * 13 + 3)
                closer = d < best
                best = np.where(closer, d, best)
                val = np.where(closer, v, val)
    return val


def evaluate(expr, masks, x=None, y=None, constants=None):
    """Evaluate an expression with numpy. masks: {name: array} or a callable name -> array (all the same shape);
    x, y: world metres of the points (needed only by noise(), fbm() and cells()); constants: the terrain constants
    (CONSTANTS defaults). A mask the dict lacks reads 0 (an absent process), as the material's Attribute node does."""
    t = parse(expr) if not isinstance(expr, tuple) else expr
    get = masks if callable(masks) else (lambda n: masks.get(n))
    consts = dict(CONSTANTS)
    consts.update(constants or {})
    shape = None if x is None else np.shape(x)

    def ev(n):
        k = n[0]
        if k == 'num':
            return n[1]
        if k == 'const':
            return float(consts[n[1]])
        if k == 'mask':
            v = get(n[1])
            return 0.0 if v is None else np.asarray(v, np.float64)
        if k == 'neg':
            return -ev(n[1])
        if k == 'op':
            a, b = ev(n[2]), ev(n[3])
            o = n[1]
            if o == '+':
                return a + b
            if o == '-':
                return a - b
            if o == '*':
                return a * b
            return a / np.where(np.abs(b) < 1e-12, 1e-12, b) if isinstance(b, np.ndarray) else a / (b if abs(b) > 1e-12 else 1e-12)
        f, args = n[1], n[2]
        if f in ('noise', 'fbm', 'cells'):
            if x is None:
                raise ExprError(f'{f}() needs the points (x, y) to evaluate with numpy')
            seed = int(args[1][1]) if len(args) > 1 else 0
            if f == 'cells':
                k = float(args[2][1]) if len(args) > 2 else 0.0
                zh = get('height') if k > 0.0 else None          # the material reads the object z: the same height
                if k > 0.0 and zh is None:
                    raise ExprError('cells(scale_m, seed, z_stretch) needs the height mask to evaluate with numpy')
                return voronoi_cells(x, y, args[0][1], seed, z=zh, z_stretch=k)
            if f == 'fbm':
                return value_noise(x, y, args[0][1], seed + 101, octaves=5, gain=0.6, stretch=2.2)
            return value_noise(x, y, args[0][1], seed)
        v = [ev(a) for a in args]
        if f == 'smoothstep':
            if not all(isinstance(e, float) for e in v[:2]):
                raise ExprError('smoothstep(e0, e1, x): the edges must be numbers')
            return _smooth(v[0], v[1], v[2])
        if f == 'min':
            out = v[0]
            for e in v[1:]:
                out = np.minimum(out, e)
            return out
        if f == 'max':
            out = v[0]
            for e in v[1:]:
                out = np.maximum(out, e)
            return out
        if f == 'clamp':
            return np.clip(v[0], v[1], v[2])
        if f == 'abs':
            return np.abs(v[0])
        if f == 'pow':
            return np.power(np.maximum(v[0], 0.0), v[1])
        if f == 'mix':
            return v[0] + (v[1] - v[0]) * v[2]
        raise ExprError(f)
    out = ev(t)
    if shape is not None and np.ndim(out) == 0:
        out = np.full(shape, float(out))
    return out


# ------------------------------------------------------------------------------------------ colour helpers ---

def srgb_to_linear(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


_HEX = re.compile(r'^#?([0-9a-fA-F]{6})$')


def hex_linear(h):
    """'#rrggbb' (sRGB) -> linear (r, g, b) floats."""
    m = _HEX.match(str(h).strip())
    if not m:
        raise ValueError(f'colour {h!r}: write it as sRGB "#rrggbb"')
    v = int(m.group(1), 16)
    return tuple(float(x) for x in srgb_to_linear(np.array([(v >> 16) & 255, (v >> 8) & 255, v & 255]) / 255.0))


# ----------------------------------------------------------------------------------------- resolution, checks ---

def names():
    return sorted(PALETTES)


def _nearest(name, options, k=3):
    def dist(a, b):
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]
    return sorted(options, key=lambda o: dist(str(name), o))[:k]


def _recipe_name(recipe):
    return recipe if isinstance(recipe, str) else getattr(recipe, 'name', None) or (
        recipe.get('name') if isinstance(recipe, dict) else None)


def resolve_name(palette, recipe=None):
    """The palette name 'auto' and recipe names resolve to (RECIPE_PALETTES), or the name itself."""
    if palette == 'auto':
        rname = _recipe_name(recipe)
        defaults = getattr(recipe, 'defaults', None) or (recipe.get('defaults') if isinstance(recipe, dict) else None)
        if isinstance(defaults, dict) and defaults.get('palette') not in (None, 'auto'):
            return defaults['palette']
        if rname in RECIPE_PALETTES:
            return RECIPE_PALETTES[rname]
        if rname in PLACES:
            return PLACES[rname]['palette']
        return 'meadow' if rname is None else RECIPE_PALETTES.get(rname, 'alpine')
    return palette


def get(palette, recipe=None, validate=True):
    """A palette as a validated deep copy with every default filled in. palette: a name from names(), 'auto' (the
    recipe's, with its RECIPE_LOOKS), or a palette dict (validated as given). None is not a palette: the caller builds
    grey clay for it."""
    if palette is None:
        raise ValueError("palette None is grey clay: call surfacing.clay_material() instead")
    auto = palette == 'auto'
    palette = resolve_name(palette, recipe)
    if isinstance(palette, str):
        if palette not in PALETTES:
            raise KeyError(f'unknown palette {palette!r}; nearest: {", ".join(_nearest(palette, PALETTES))}')
        pal = copy.deepcopy(PALETTES[palette])
        pal['name'] = palette
    elif isinstance(palette, dict):
        pal = copy.deepcopy(palette)
        pal.setdefault('name', 'custom')
        # a recipe's palette from strata.palette_for ('<base>+<column>') carries only its column and source: the base
        # palette's other strata settings (warp, facies, runnels, partings) fill in what it does not say
        base = PALETTES.get(str(pal['name']).split('+')[0])
        if pal.get('strata') and base and base.get('strata'):
            for k, v in base['strata'].items():
                if k not in ('column', 'source'):
                    pal['strata'].setdefault(k, copy.deepcopy(v))
    else:
        raise TypeError('palette: a name, "auto", a dict or None')
    look = RECIPE_LOOKS.get(_recipe_name(recipe)) if auto else None
    if look:                                             # the recipe's own look over its palette ('auto' only)
        for k, v in copy.deepcopy(look).items():
            if k == 'layers':                            # {layer name: {key: value}} over the palette's layers
                for L in pal['layers']:
                    L.update(v.get(L['name'], {}))
            else:
                pal[k] = dict(pal.get(k) or {}, **v) if isinstance(v, dict) and k != 'strata' else v
    opts = copy.deepcopy(DEFAULT_OPTIONS)
    opts.update(pal.get('options') or {})
    pal['options'] = opts
    for L in pal['layers']:
        L.setdefault('projection', 'planar')
        L.setdefault('colour', None)
        L.setdefault('tint', None)
        L.setdefault('value', 1.0)
        L.setdefault('roughness', 1.0)
        L.setdefault('normal', 1.0)
        L.setdefault('bump_m', 0.04 * float(L['tile_m']) if L['projection'] == 'box' else 0.0)
        L.setdefault('strata', False)
        L.setdefault('strata_offset_m', 0.0)
        L.setdefault('edge_noise', None)
        L.setdefault('weight', '1')
    pal.setdefault('strata', None)
    if pal['strata']:
        for k, v in STRATA_DEFAULTS.items():
            pal['strata'].setdefault(k, copy.deepcopy(v))
    pal.setdefault('dressing', None)
    consts = dict(CONSTANTS)
    consts.update(pal.get('constants') or {})
    pal['constants'] = consts
    if validate:
        problems = check(pal)
        if problems:
            raise ValueError(f'palette {pal["name"]!r}: ' + '; '.join(problems))
    return pal


def _patches(L):
    p = L.get('patches')
    if not p:
        return []
    return [p] if isinstance(p, dict) else list(p)


def _layer_exprs(L):
    """A layer's other mask expressions: its streaks_where and its ledges' where."""
    out = []
    if L.get('streaks_where'):
        out.append(L['streaks_where'])
    if isinstance(L.get('ledges'), dict) and L['ledges'].get('where'):
        out.append(L['ledges']['where'])
    return out


def check(pal):
    """Problems with a filled-in palette (empty list when it is fine)."""
    out = []
    layers = pal.get('layers') or []
    if not 1 <= len(layers) <= MAX_LAYERS:
        out.append(f'{len(layers)} layers: a palette has 1 to {MAX_LAYERS}')

    def expr_ok(tag, e):
        try:
            for nm in names_in(e):
                msg = known_mask(nm)
                if msg:
                    out.append(f'{tag}: {msg}')
        except ExprError as err:
            out.append(f'{tag}: {err}')
    for i, L in enumerate(layers):
        tag = f'layer {i} ({L.get("name", "?")})'
        if not L.get('set'):
            out.append(f'{tag}: no texture set')
        if not float(L.get('tile_m', 0)) > 0:
            out.append(f'{tag}: tile_m must be metres > 0')
        if L.get('projection') not in PROJECTIONS:
            out.append(f'{tag}: projection {L.get("projection")!r} (planar or box)')
        if L.get('colour') is not None:
            try:
                hex_linear(L['colour'])
            except ValueError as e:
                out.append(f'{tag}: {e}')
        if L.get('strata') and not pal.get('strata') and L.get('colour') is None:
            out.append(f'{tag}: strata=True, but the palette has no strata column and the layer no colour')
        expr_ok(f'{tag} weight', L.get('weight', '1'))
        for k, pt in enumerate(_patches(L)):
            if not (pt.get('colour') or pt.get('tint')):
                out.append(f'{tag} patch {k}: needs a colour or a tint')
            if pt.get('colour'):
                try:
                    hex_linear(pt['colour'])
                except ValueError as e:
                    out.append(f'{tag} patch {k}: {e}')
            if pt.get('where'):
                expr_ok(f'{tag} patch {k} where', pt['where'])
        for e in _layer_exprs(L):
            expr_ok(f'{tag} streaks_where/ledges where', e)
        ld = L.get('ledges')
        if ld is not None and not (isinstance(ld, dict) and len(ld.get('tint') or ()) >= 3):
            out.append(f'{tag} ledges: a dict with a tint (r, g, b)')
        cn = L.get('canopy')
        if cn:
            for key in ('colour', 'light', 'gap'):
                try:
                    hex_linear(cn.get(key, '#000000'))
                except ValueError as e:
                    out.append(f'{tag} canopy {key}: {e}')
    o = pal.get('options') or {}
    if o.get('interpolation') not in ('Auto', 'Cubic', 'Linear', 'Closest'):
        out.append("options.interpolation must be 'Auto', 'Cubic', 'Linear' or 'Closest'")
    if o.get('detile') not in ('offset', 'rotate'):
        out.append("options.detile must be 'offset' or 'rotate'")
    for key in ('damp_where', 'tone'):
        if o.get(key):
            expr_ok(key, o[key])
    st = pal.get('strata')
    if st:
        col = st.get('column')
        if isinstance(col, str) and col not in STRATA_COLUMNS:
            out.append(f'strata column {col!r}; nearest: {", ".join(_nearest(col, STRATA_COLUMNS))}')
        if st.get('source', 'attribute') not in ('attribute', 'position'):
            out.append("strata source must be 'attribute' (eido_strata) or 'position' (Position.z)")
    d = pal.get('dressing')
    if d and d.get('density') is not None:
        expr_ok('dressing density', d['density'])
    return out


def material_masks(pal):
    """The masks a palette's material reads (its layer weights, patches, streaks, ledges, damp, tone and strata):
    the mesh attributes its shader compiles with."""
    pal = get(pal) if not isinstance(pal, dict) or 'options' not in pal else pal
    out = set()
    for L in pal['layers']:
        out |= names_in(L['weight'])
        for pt in _patches(L):
            if pt.get('where'):
                out |= names_in(pt['where'])
        for e in _layer_exprs(L):
            out |= names_in(e)
    for key in ('damp_where', 'tone'):
        if pal['options'].get(key):
            out |= names_in(pal['options'][key])
    if pal.get('strata') and pal['strata'].get('source', 'attribute') == 'attribute' and \
            any(L.get('strata') for L in pal['layers']):
        out.add('strata')
    return out


def masks_used(pal):
    """Every mask a palette's material and rocks read (so the mesh carries them as eido_<name>)."""
    pal = get(pal) if not isinstance(pal, dict) or 'options' not in pal else pal
    out = material_masks(pal)
    d = pal.get('dressing')
    if d and d.get('density') is not None:
        out |= names_in(d['density'])
    return out


def for_place(dem):
    """(palette, place) for a real DEM (a reference name): the palette dict with the place's strata merged in, and
    the place record (its mask_params for masks.MaskParams: snowline_m, treeline_m, sea_level)."""
    if dem not in PLACES:
        raise KeyError(f'no palette for the place {dem!r}; nearest: {", ".join(_nearest(dem, PLACES))}')
    place = copy.deepcopy(PLACES[dem])
    pal = copy.deepcopy(PALETTES[place['palette']])
    pal['name'] = place['palette']
    if place.get('strata'):
        pal['strata'] = dict(pal.get('strata') or {}, **place['strata'])
    mp = place.get('mask_params') or {}
    pal['constants'] = dict(pal.get('constants') or {},
                            **{k: float(v) for k, v in mp.items() if k in ('snowline_m', 'treeline_m')})
    return get(pal), place


def _look(name):
    low = str(name).lower()
    return next((lk for key, lk in FORMATION_LOOKS if key in low), None)


def column_layers(column, looks=False):
    """A strata column as [(name, bottom_m, top_m, colour_linear (3,) or [(colour (3,), weight)], roughness, bed_m,
    jitter)], from a STRATA_COLUMNS key, a column dict, or a solver column [(thickness_m, K_factor, Sc_deg,
    colour_id, name), ...] or [(name, thickness_m), ...] (coloured by LAYER_COLOURS). looks=True colours the
    formations FORMATION_LOOKS names by their look (colour, roughness, bed thickness, jitter)."""
    if isinstance(column, str):
        column = STRATA_COLUMNS[column]

    def colour(col):
        if isinstance(col, (list, tuple)) and col and isinstance(col[0], (list, tuple)):
            return [(np.array(hex_linear(c)), float(w)) for c, w in col]
        return np.array(hex_linear(col))
    out = []
    if isinstance(column, dict):
        z = float(column.get('base_m', 0.0))
        for name, thick, col, rough, bed, jit in column['formations']:
            lk = _look(name) if looks else None
            if lk:
                col, rough, bed, jit = lk
            out.append((name, z, z + float(thick), colour(col), float(rough), float(bed), float(jit)))
            z += float(thick)
        return out
    z = 0.0
    for row in column:
        if isinstance(row, dict):
            name, thick = row.get('name', 'layer'), float(row['thickness_m'])
            base = row.get('base_m')
        elif isinstance(row[0], str):
            name, thick, base = row[0], float(row[1]), None
        else:
            thick, name, base = float(row[0]), str(row[4] if len(row) > 4 else row[-1]), None
        if base is not None:
            z = float(base)
        lk = _look(name) if looks else None
        if lk:
            col, rough, bed, jit = lk
            out.append((name, z, z + thick, colour(col), float(rough), float(bed), float(jit)))
        else:
            col = next((c for key, c in LAYER_COLOURS if key in name.lower()), '#a39a8e')
            out.append((name, z, z + thick, np.array(hex_linear(col)), 1.0, 2.5, 0.06))
        z += thick
    return out


def column_repeats(column):
    """True when a column (a STRATA_COLUMNS key or dict) repeats (a generic pile for walls at any height)."""
    if isinstance(column, str):
        column = STRATA_COLUMNS.get(column, {})
    return bool(isinstance(column, dict) and column.get('repeat'))


def describe(palette):
    """One page on a palette: its layers (scan, tile, colour, projection, weight) and its rocks."""
    pal = get(palette)
    lines = [f"{pal['name']}: {pal.get('title', '')}"]
    for i, L in enumerate(pal['layers']):
        lines.append(f"  {i} {L['name']:<14} {L['set']:<26} tile {L['tile_m']:>5.1f} m  {L['projection']:<6} "
                     f"colour {L['colour'] or 'scan'}{'  strata' if L['strata'] else ''}"
                     f"{'  canopy' if L.get('canopy') else ''}")
        lines.append(f"      weight: {L['weight']}")
    if pal.get('strata'):
        lines.append(f"  strata: {pal['strata']}")
    lines.append(f"  constants: {pal['constants']}")
    d = pal.get('dressing')
    if d:
        lines.append(f"  rocks: {', '.join(m if isinstance(m, str) else m[0] for m in d.get('models', []))}  "
                     f"colour {d.get('colour')}")
        lines.append(f"      density (per m^2): {d.get('density')}")
    lines.append(f"  masks read: {', '.join(sorted(masks_used(pal)))}")
    return '\n'.join(lines)


__all__ = ['PALETTES', 'STRATA_COLUMNS', 'STRATA_DEFAULTS', 'FORMATION_LOOKS', 'LAYER_COLOURS', 'RECIPE_PALETTES', 'RECIPE_LOOKS',
           'PLACES', 'DEFAULT_OPTIONS', 'LANDSCAPE', 'LANDSCAPE_MACRO', 'CONSTANTS', 'DERIVED', 'MAX_LAYERS',
           'ExprError', 'parse', 'tree_key', 'names_in', 'evaluate', 'value_noise', 'voronoi_cells', 'names', 'get',
           'check', 'masks_used', 'material_masks', 'for_place', 'column_layers', 'column_repeats', 'describe',
           'hex_linear',
           'srgb_to_linear', 'linear_to_srgb', 'resolve_name']
