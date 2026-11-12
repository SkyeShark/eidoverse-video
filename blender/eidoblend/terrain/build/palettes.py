"""The terrain's palettes (design section 7): which CC0 scans cover which ground, as data, plus the small mask
expression language their layer weights and rock densities are written in. No bpy: build/surfacing.py turns a
palette into the eido_terrain_surface node group, build/dressing.py scatters its rocks.

    from eidoblend.terrain.build import palettes as P
    P.names()                          # ['alpine', 'badlands', 'chalk_coast', 'desert_sandstone', 'dunes', ...]
    pal = P.get('alpine')              # a validated deep copy, every default filled in
    pal = P.get('auto', recipe='canyon')       # the recipe's palette (RECIPE_PALETTES)
    pal, place = P.for_place('grand_canyon_toroweap')   # a real DEM's palette, its strata and its mask parameters
    P.masks_used(pal)                  # {'slope', 'rock', 'talus', ...}: the eido_<mask> attributes it reads
    P.describe('alpine')               # one page: layers, scans, weights, rocks

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
                     with the layer's own (talus: mostly the colour of the beds above it)
        edge_noise   ragged-edge noise amplitude for this layer (default the palette's)
        specular     this layer's Principled specular (default the palette's): grass is not glossy, wet rock is
        contrast     1 keeps the scan's detail as it is around the new mean; under 1 flattens it
        streaks      (width_m, amount): vertical streaks darkening walls (water stains, desert varnish)
        patches      dict(scale_m, colour, amount): a second tone in world-noise patches (drier grass): what breaks a
                     lawn-like scan up at the few-metre scale it mipmaps away at, seen from eye height
        far_contrast the far read's contrast around the scan's mean (default the palette's 0.65)
        ripples      dict(wavelength_m, height_m, azimuth_deg (the bearing the wind blows toward), fade_m): wind
                     ripples as bump, faded out with distance before they alias
    options      material options (DEFAULT_OPTIONS; the old film material's, plus landscape macro octaves and the far
                 scale)
    strata       None, or the column spec the strata layers read (see STRATA_COLUMNS and surfacing.strata_image)
    dressing     the rock scatter (build/dressing.py): models (ids, or (id, min_size_m, max_size_m) so heavy boulder
                 scans stand only for big rocks), colour, density expression, sizes, burial

The mask expression language (layer weights, rock densities; the same grammar as a stage's `where`):
    numbers, mask names (masks.MASKS: slope, rock, talus, snow, vegetation, convex_20m, ...), + - * /, unary -,
    smoothstep(e0, e1, x)  (e0 > e1 allowed: a falling edge), min(a, b, ...), max(a, b, ...), clamp(x, lo, hi),
    abs(x), pow(x, e), mix(a, b, t), noise(scale_m[, seed]): a world-space noise of about 0..1 (mean 0.5) with
    features `scale_m` metres across, and cells(scale_m[, seed]): a random value 0..1 per cell of a world-space
    Voronoi partition with cells about scale_m across (fields, patches with straight boundaries). Every mask is in its own unit (slope in degrees, talus in metres, ...), so a
    weight means the same at every level. The material and the scatter evaluate noise() with different noises (the
    shader's and a numpy value noise), so use it for breakup, not for anything the two must agree on. DERIVED names
    expand to expressions: `plants` is vegetation with the masks package's stream-bed factor undone (see DERIVED).
"""
from __future__ import annotations

import ast
import copy
import math
import re

import numpy as np

# ------------------------------------------------------------------------------------------- the options ---

DEFAULT_OPTIONS = dict(
    # the film material's settings, measured with the shimmer probe (tests/terrain/surfacing/test_shimmer.py)
    anti_tile=True,                 # a second sample per map at an unrelated scale and offset, switched by noise
    detile_patch=1.2,               # the switch's patches, in tiles
    height_blend=0.5,               # a_i = w_i + height_i * height_blend
    blend_depth=0.2,                # keep what is within this of the tallest a_i
    edge_noise=0.3,                 # ragged ~1 m noise on the upper layers' edges
    ao=0.5,                         # how much of each scan's AO darkens its albedo (EEVEE adds the scene's on top)
    damp=0.5,                       # damp patches: wet soil darkens and loses some roughness
    damp_scale_m=6.25,              # the old patches' size (noise scale 0.16)
    damp_where=None,                # an expression that adds damp ground (e.g. 'wetness'), on top of the patches
    specular=0.5,                   # Principled 'Specular IOR Level'
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
    debug=None,                     # 'weights' (the top three layers' weights as RGB) or 'albedo', unlit
    # world-scale variation: brightness, hue and saturation drift. The old material's two octaves (value over ~14 m,
    # hue and saturation over ~22 m) plus, for landscapes, octaves at hundreds and thousands of metres
    macro=[dict(scale_m=14.3, value=0.14, detail=4.0, roughness=0.5),
           dict(scale_m=22.2, hue=0.012, saturation=(0.88, 1.08), detail=2.0, roughness=0.55, w=7.7)],
)

# macro octaves for landscapes: the old two plus field-scale and valley-scale drift
LANDSCAPE_MACRO = [dict(scale_m=14.3, value=0.10, detail=4.0, roughness=0.5),
                   dict(scale_m=22.2, hue=0.010, saturation=(0.9, 1.06), detail=2.0, roughness=0.55, w=7.7),
                   dict(scale_m=180.0, value=0.12, hue=0.008, saturation=(0.88, 1.1), detail=3.0, roughness=0.55,
                        w=3.3),
                   dict(scale_m=1500.0, value=0.08, saturation=(0.92, 1.06), detail=2.0, roughness=0.5, w=5.1)]

# the options every landscape palette shares: the landscape macro octaves and the far scale
LANDSCAPE = dict(macro=LANDSCAPE_MACRO, far_scale=8.0)

MAX_LAYERS = 6
PROJECTIONS = ('planar', 'box')

# ------------------------------------------------------------------------------------- the strata columns ---
# A column is bottom to top: base_m (the stratigraphic height of its bottom, metres) and formations
# (name, thickness_m, colour sRGB, roughness multiplier, mean bed thickness m, bed colour jitter). Inside a formation
# the beds take random thicknesses around the mean and a little colour jitter, so a cliff shows bedding, not one flat
# band. Colours are what the rock looks like in daylight photographs (desert varnish and staining included).

STRATA_COLUMNS = {
    # Grand Canyon at Toroweap, east of the Toroweap fault (the overlook's side): the Esplanade bench stands at about
    # 1370 m, the Kaibab rim at 1950 m, the river at 505 m. Contacts placed on the benches the DEM shows (gentle ground
    # piles up at 1090-1110 m, 1310-1460 m, 1760-1780 m and 1910-1945 m).
    'toroweap': dict(base_m=480.0, formations=[
        ('Muav limestone and Bright Angel shale', 220.0, '#7a5c50', 1.0, 4.0, 0.06),
        ('Temple Butte and upper Muav', 230.0, '#8c6553', 1.0, 3.0, 0.06),
        ('Redwall limestone (stained)', 170.0, '#a15b43', 0.95, 6.0, 0.05),
        ('lower Supai group', 200.0, '#8f4a33', 1.0, 2.5, 0.09),
        ('Esplanade sandstone', 85.0, '#a8653f', 0.95, 4.0, 0.06),
        ('Hermit shale', 265.0, '#9a4f37', 1.0, 2.0, 0.07),
        ('Coconino sandstone', 50.0, '#cdb48c', 0.9, 6.0, 0.04),
        ('Toroweap formation', 100.0, '#b19a7c', 1.0, 2.5, 0.06),
        ('Kaibab limestone', 180.0, '#c4b294', 0.95, 3.5, 0.05),
    ]),
    # Badlands Wall near Cedar Pass: Chadron mounds at the foot, the Brule's pink-buff mudstone with red and maroon
    # palaeosols, the Poleslide's buff siltstone, pale ash beds near the top.
    'badlands_cedar_pass': dict(base_m=720.0, formations=[
        ('Chadron formation', 32.0, '#a29e8b', 1.0, 3.0, 0.05),
        # the Scenic member: buff mudstone beds with red and maroon palaeosols and a few pale ash beds, each bed
        # drawing its colour (the bands are many and thin, not two thick stripes)
        ('Brule, Scenic member', 48.0, [('#cdae92', 0.55), ('#b47a62', 0.22), ('#9a6150', 0.12), ('#d9d1c2', 0.11)],
         1.0, 0.9, 0.07),
        ('Brule, Poleslide member', 50.0, [('#c8ae8e', 0.7), ('#b58b6c', 0.2), ('#a8907a', 0.1)], 1.0, 1.3, 0.07),
        ('Rockyford ash', 6.0, '#ddd6c8', 0.95, 1.5, 0.04),
        ('Sharps formation', 40.0, [('#cdbfa8', 0.8), ('#b9a58c', 0.2)], 1.0, 1.6, 0.06),
    ]),
    # the solver's columns (package 10, design 4.9), coloured by layer; their thicknesses there are the solver's own
    # (the material takes the solver's column when the recipe passes it, and colours it with LAYER_COLOURS)
    'colorado_plateau': dict(base_m=0.0, formations=[
        ('Vishnu schist', 300.0, '#4f4844', 1.0, 6.0, 0.05),
        ('Tapeats sandstone', 70.0, '#7d5b45', 1.0, 2.0, 0.07),
        ('Muav and Bright Angel', 200.0, '#7d7568', 1.0, 3.0, 0.06),
        ('Redwall limestone (stained)', 170.0, '#9b5f49', 0.95, 6.0, 0.05),
        ('Supai group', 300.0, '#934f39', 1.0, 2.5, 0.09),
        ('Hermit shale', 250.0, '#9a4f37', 1.0, 2.0, 0.07),
        ('Coconino sandstone', 100.0, '#d0bd9a', 0.9, 6.0, 0.04),
        ('Toroweap formation', 80.0, '#b3a48c', 1.0, 2.5, 0.06),
        ('Kaibab limestone', 100.0, '#c2b8a3', 0.95, 3.5, 0.05),
    ]),
    'monument_valley': dict(base_m=0.0, formations=[
        ('Cedar Mesa sandstone', 120.0, '#c7a17b', 1.0, 3.0, 0.06),
        ('Organ Rock shale', 200.0, '#9c4f37', 1.0, 2.0, 0.07),
        ('De Chelly sandstone', 250.0, '#b8663f', 0.95, 8.0, 0.04),
        ('Moenkopi formation', 40.0, '#9a5940', 1.0, 1.5, 0.08),
        ('Shinarump conglomerate', 20.0, '#a7896c', 1.0, 2.0, 0.06),
    ]),
    'badlands': dict(base_m=0.0, formations=[
        ('Chadron formation', 30.0, '#a29e8b', 1.0, 3.0, 0.05),
        ('Brule formation', 90.0, [('#cdae92', 0.55), ('#b47a62', 0.22), ('#9a6150', 0.12), ('#d9d1c2', 0.11)],
         1.0, 1.0, 0.07),
        ('Rockyford ash', 6.0, '#ddd6c8', 0.95, 1.5, 0.04),
        ('Sharps formation', 40.0, '#cdbfa8', 1.0, 2.0, 0.06),
    ]),
    'chalk': dict(base_m=0.0, formations=[('chalk with flint bands', 400.0, '#e2ded3', 0.9, 1.2, 0.03)]),
    'limestone': dict(base_m=0.0, formations=[('limestone', 600.0, '#a6a39b', 0.95, 4.0, 0.05)]),
    'granite': dict(base_m=0.0, formations=[('granite', 3000.0, '#9d9890', 1.0, 40.0, 0.03)]),
}

# colours by layer name, for a column the solver passes (name, thickness_m, ...): matched by case-insensitive
# substring, first hit wins
LAYER_COLOURS = [
    ('kaibab', '#c2b8a3'), ('toroweap', '#b3a48c'), ('coconino', '#d0bd9a'), ('hermit', '#9a4f37'),
    ('esplanade', '#b9795a'), ('supai', '#934f39'), ('redwall', '#9b5f49'), ('muav', '#857a6c'),
    ('bright angel', '#7d7568'), ('tapeats', '#7d5b45'), ('vishnu', '#4f4844'), ('shinarump', '#a7896c'),
    ('moenkopi', '#9a5940'), ('de chelly', '#b8663f'), ('organ rock', '#9c4f37'), ('cedar mesa', '#c7a17b'),
    ('brule', '#c9a88d'), ('chadron', '#a29e8b'), ('ash', '#ddd6c8'), ('sharps', '#cdbfa8'), ('chalk', '#e2ded3'),
    ('flint', '#5e5a55'), ('limestone', '#a6a39b'), ('granite', '#9d9890'), ('basalt', '#3a3634'),
    ('sandstone', '#c09a76'), ('shale', '#8e7c6c'), ('clay', '#b9a58c'),
]

# ------------------------------------------------------------------------------------------- the palettes ---

PALETTES = {
    'alpine': dict(
        title='Alpine: grey limestone walls, scree, pasture and spruce forest, river gravel, snow',
        layers=[
            # pasture with drier yellow-green patches a few metres across (what a meadow shows from eye height)
            dict(name='pasture', set='Grass004', tile_m=2.5, colour='#647b34', roughness=1.4, specular=0.25, weight='1',
                 patches=dict(scale_m=7.0, colour='#8f8a45', amount=0.7)),
            # forest on the lower flanks and talus cones, not on walls or ledges: the brown needle litter under the
            # trees (the trees family plants them; a painted canopy colour read as holes in the walls)
            dict(name='forest floor', set='forrest_ground_03', tile_m=2.5, colour='#3d3a2a', normal=0.8, specular=0.25,
                 weight='smoothstep(0.22, 0.45, plants + 0.3*(noise(220) - 0.5)) * smoothstep(13, 22, slope) '
                        '* smoothstep(33, 26, slope)'),
            # river gravel on the trunk streams only: flow is continuous across levels, where channels marks rills
            # on the fine levels
            dict(name='gravel', set='rock_ground_02', tile_m=3.0, colour='#8a8679',
                 weight='max(smoothstep(0.86, 0.96, flow) * smoothstep(8, 2, slope), smoothstep(0.3, 1.5, deposit))'),
            dict(name='scree', set='rocks_ground_06', tile_m=3.0, colour='#a39f96', projection='box',
                 weight='max(smoothstep(0.2, 1.5, talus), smoothstep(0.25, 0.6, rock_toe) * smoothstep(0.5, 0.15, plants), '
                        'smoothstep(29, 36, slope) * smoothstep(0.35, 0.1, plants))'),
            # limestone walls with the dark water stains that streak them
            dict(name='rock', set='Rock051', tile_m=9.0, colour='#8b867d', projection='box', bump_m=0.45,
                 streaks=(5.0, 0.45), weight='smoothstep(0.35, 0.75, rock + 0.3*(noise(60) - 0.5))'),
            dict(name='snow', set='Snow010A', tile_m=3.0, colour='#eceff3', roughness=0.85, normal=0.6,
                 weight='smoothstep(0.2, 0.65, snow + 0.35*(noise(120) - 0.5) + 0.15*(noise(25) - 0.5))'),
        ],
        options=dict(LANDSCAPE, damp_where='0.5*smoothstep(0.6, 0.9, wetness)'),
        dressing=dict(models=[('rock_09', 0.0, 0.35), ('rock_07', 0.2, 0.9), ('boulder_01', 0.6, 4.0)],
                      colour='#8d8981',
                      density='2.2*smoothstep(0.2, 1.5, talus) + 1.4*rock_toe + 0.5*smoothstep(28, 36, slope)*(1 - plants)'
                              ' + 0.25*smoothstep(0.86, 0.96, flow)*smoothstep(10, 3, slope) + 0.01'),
    ),
    'desert_sandstone': dict(
        title='Desert sandstone: banded red sandstone and limestone walls, red talus, desert pavement and scrub, sand',
        layers=[
            dict(name='pavement', set='sandy_gravel_02', tile_m=2.5, colour='#93664a', weight='1'),
            # blackbrush and sage on the benches and plateau soil: grey-olive patches (the flora family adds the
            # shrubs themselves; this is the ground they make look grey-green from the air)
            dict(name='scrub', set='grass_ground', tile_m=2.5, colour='#6b674c', roughness=1.3, specular=0.3,
                 weight='smoothstep(0.2, 0.45, plants) * smoothstep(0.42, 0.62, noise(11) + 0.2*(noise(140) - 0.5))'),
            dict(name='sand', set='red_sand', tile_m=3.0, colour='#a46a4a',
                 weight='max(smoothstep(0.6, 0.85, wetness) * smoothstep(8, 2, slope), smoothstep(0.3, 1.5, deposit), '
                        'smoothstep(0.2, 1.0, sand))'),
            # talus is the debris of the beds above it: mostly their colour (strata 0.7), on the slopes between cliffs
            dict(name='talus', set='rocks_ground_02', tile_m=2.5, colour='#8a5a42', projection='box', strata=0.7,
                 weight='max(smoothstep(0.2, 1.5, talus), smoothstep(0.2, 0.55, rock_toe), smoothstep(24, 31, slope))'),
            # banded rock with desert varnish streaking the walls
            dict(name='rock', set='rock_face_03', tile_m=6.0, projection='box', strata=True, bump_m=0.3,
                 streaks=(3.0, 0.4),
                 weight='max(smoothstep(0.35, 0.6, rock + 0.15*(noise(15) - 0.5)), '
                        '0.9*smoothstep(0.1, 0.35, convex_20m + 0.25*(noise(25) - 0.5)) * smoothstep(0.62, 0.45, wetness))'),
        ],
        options=dict(LANDSCAPE, damp=0.0),
        strata=dict(column='colorado_plateau', source='attribute'),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 0.8), ('namaqualand_boulder_04', 0.6, 5.0),
                              ('namaqualand_boulder_02', 0.6, 5.0), ('namaqualand_boulder_06', 0.6, 5.0)],
                      colour='#8c5a40', size_m=(0.15, 3.0), alpha=2.1,
                      density='2.6*smoothstep(0.2, 1.5, talus) + 1.6*rock_toe + 0.7*smoothstep(24, 32, slope)*(1 - rock)'
                              ' + 0.3*smoothstep(0.1, 0.4, convex_20m) + 0.02'),
    ),
    'volcanic': dict(
        title='Volcanic: dark lava rock, red-black scoria, ash soil, sparse grass and forest on the lower flanks, snow',
        layers=[
            dict(name='ash soil', set='Ground051', tile_m=2.5, colour='#5a4d43', weight='1'),
            dict(name='grass', set='grass_ground', tile_m=2.5, colour='#565a3a', roughness=1.3, specular=0.25,
                 weight='smoothstep(0.08, 0.45, plants + 0.25*(noise(150) - 0.5))'),
            # the forest reads the vegetation with the masks' stream-bed thinning (1 - 0.8 channels) undone, so the
            # canopy is not veined by every gully
            # forest on the flanks; the flat apron plains stay grass (pasture and fields on an inhabited volcano)
            dict(name='forest floor', set='forrest_ground_03', tile_m=2.5, colour='#2c3524', normal=0.8, specular=0.25,
                 weight='smoothstep(0.2, 0.55, plants + 0.3*(noise(400) - 0.5)) * smoothstep(2.5, 6, slope)'),
            dict(name='scoria', set='Gravel024', tile_m=2.0, colour='#4f4039',
                 weight='smoothstep(0.1, 0.02, plants) * smoothstep(5, 12, slope)'),
            dict(name='lava rock', set='Rock031', tile_m=6.0, colour='#3a3532', projection='box', bump_m=0.3,
                 weight='max(smoothstep(0.3, 0.75, rock + 0.3*(noise(50) - 0.5)), smoothstep(0.2, 0.6, lava))'),
            dict(name='snow', set='Snow010A', tile_m=3.0, colour='#eceff3', roughness=0.85, normal=0.6,
                 weight='smoothstep(0.2, 0.65, snow + 0.45*(noise(140) - 0.5) + 0.2*(noise(30) - 0.5))'),
        ],
        options=dict(LANDSCAPE, damp=0.3),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 1.0), ('boulder_01', 0.6, 4.0)], colour='#3d3633',
                      density='1.4*smoothstep(0.2, 1.5, talus) + 1.0*rock_toe + 0.3*smoothstep(0.1, 0.02, plants)'
                              ' + 0.6*smoothstep(0.2, 0.6, lava) + 0.02'),
    ),
    'dunes': dict(
        title='Dunes: wind-rippled sand, damp interdune flats, crusted pans, grass on the stable sand sheet',
        layers=[
            # plain sand with wind ripples in the material (design 4.6: ripples belong in the material): 12 cm crests
            # across the wind, a steep lee side, faded out before they alias
            dict(name='sand', set='sand_03', tile_m=2.0, colour='#ad9677', weight='1', contrast=0.5,
                 ripples=dict(wavelength_m=0.14, height_m=0.015, azimuth_deg=45.0, fade_m=(12.0, 35.0))),
            # damp sand along the creek and in interdune hollows (the wetness index is high on every flat, so it is
            # not the cue): flow for the creek, concavity for the hollows
            dict(name='damp sand', set='gravelly_sand', tile_m=2.5, colour='#8b7b67',
                 weight='max(smoothstep(0.88, 0.97, flow), 0.6*smoothstep(0.5, 0.9, concave_20m)) * smoothstep(5, 1.5, slope)'),
            dict(name='crust', set='dry_ground_01', tile_m=4.0, colour='#aa9c88',
                 weight='smoothstep(0.35, 0.75, concave_20m) * smoothstep(6, 2, slope) * smoothstep(0.35, 0.6, noise(60))'),
            dict(name='grass', set='grass_ground', tile_m=2.5, colour='#88825f', roughness=1.3, specular=0.25,
                 weight='smoothstep(0.25, 0.55, plants + 0.4*(noise(30) - 0.5))'),
        ],
        options=dict(LANDSCAPE, damp=0.0, specular=0.35),
        dressing=dict(models=[('rock_09', 0.0, 2.0)], colour='#7c7062',
                      density='0.004*smoothstep(0.35, 0.75, concave_20m)*smoothstep(6, 2, slope)'),
    ),
    'badlands': dict(
        title='Badlands: banded mudstone (grey, buff, red), crusted popcorn clay, gravel washes, prairie',
        layers=[
            dict(name='prairie', set='grass_ground', tile_m=2.5, colour='#8d8657', roughness=1.3, specular=0.25,
                 weight='1'),
            # the popcorn crust of swelling clay: the crack scan at a small tile reads as crumbs, not mud polygons; bare
            # wherever the slope is past what grass holds and on the mound crests
            dict(name='clay', set='mud_cracked_dry_03', tile_m=0.8, colour='#bba68b', normal=0.7,
                 weight='max(smoothstep(8, 15, slope + 8*(noise(12) - 0.5)), smoothstep(0.15, 0.45, convex_20m), '
                        'smoothstep(0.3, 1.0, deposit))'),
            dict(name='wash gravel', set='rocks_ground_02', tile_m=2.0, colour='#a28d74',
                 weight='smoothstep(0.75, 0.92, flow) * smoothstep(12, 4, slope)'),
            dict(name='mudstone', set='excavated_soil_wall', tile_m=4.0, projection='box', strata=True, bump_m=0.15,
                 weight='smoothstep(20, 30, slope + 6*(noise(20) - 0.5))'),
        ],
        options=dict(LANDSCAPE, damp=0.0),
        strata=dict(column='badlands', source='attribute'),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 2.0)], colour='#a68e72',
                      density='0.25*smoothstep(0.75, 0.92, flow)*smoothstep(12, 4, slope) + 0.06*rock_toe'),
    ),
    'karst': dict(
        title='Karst: grey limestone towers streaked dark, dense scrub on their flanks, paddies and red soil on the plain',
        layers=[
            # the plain is paddies and fields, field-sized patches of young and ripe green
            dict(name='paddies', set='Grass004', tile_m=2.5, colour='#5b7834', roughness=1.3, specular=0.3, weight='1',
                 patches=dict(scale_m=60.0, colour='#7d8a3e', amount=0.6)),
            dict(name='red soil', set='red_laterite_soil_stones', tile_m=2.0, colour='#8a5a41',
                 weight='smoothstep(0.58, 0.66, noise(140, 3)) * smoothstep(8, 3, slope)'),
            dict(name='scrub', set='Ground037', tile_m=2.0, colour='#3c4d2c', roughness=1.3, specular=0.25,
                 weight='smoothstep(10, 18, slope)'),
            # limestone walls with the dark vertical streaks karst towers carry (the radar DEM rounds the towers'
            # walls to 40-55 degrees, so the rock shows on their steepest faces)
            dict(name='limestone', set='Rock051', tile_m=8.0, colour='#7d7a73', projection='box', bump_m=0.4,
                 streaks=(4.0, 0.5), weight='smoothstep(38, 52, slope + 8*(noise(30) - 0.5))'),
        ],
        options=dict(LANDSCAPE),
        dressing=dict(models=[('rock_07', 0.0, 0.9), ('boulder_01', 0.6, 4.0)], colour='#8a8781',
                      density='1.0*rock_toe + 0.3*smoothstep(0.2, 1.5, talus)'),
    ),
    'chalk_coast': dict(
        title='Chalk coast: white chalk cliffs, flint shingle, a green wave-cut platform, downland turf',
        layers=[
            # downland turf with field-sized patches of arable and pasture
            dict(name='downland', set='Grass004', tile_m=2.5, colour='#6a7c44', roughness=1.3, specular=0.25,
                 weight='1', patches=dict(scale_m=150.0, colour='#8b8a4f', amount=0.5)),
            # flint shingle on the beach (height is metres above sea level on a coast)
            dict(name='shingle', set='Gravel041', tile_m=2.0, colour='#968e80',
                 weight='max(smoothstep(0.1, 0.4, water), smoothstep(4.0, 1.5, height) * smoothstep(10, 4, slope))'),
            # the wave-cut chalk platform, green with weed, only at the cliff foot near sea level
            dict(name='platform', set='Rock019', tile_m=6.0, colour='#8f9682',
                 weight='smoothstep(0.8, 0.1, height) * smoothstep(0.1, 0.4, rock_toe)'),
            dict(name='chalk', set='Rock019', tile_m=8.0, colour='#e3dfd5', projection='box', bump_m=0.3,
                 weight='smoothstep(40, 55, slope)'),
        ],
        options=dict(LANDSCAPE),
        dressing=dict(models=[('rock_09', 0.0, 0.4), ('rock_07', 0.2, 2.0)], colour='#d8d3c8',
                      density='1.5*rock_toe*smoothstep(4, 0.5, height) + 0.02'),
    ),
    'farmland': dict(
        title='Farmland: fields of grass, ploughed soil and ripe crop with straight boundaries',
        # each field (a Voronoi cell ~280 m across) takes one crop: about a quarter soil, a third ripe crop, the rest
        # grass; a field's boundary is a straight line, not a noise blob
        layers=[
            dict(name='grass', set='Grass004', tile_m=2.5, colour='#6b7d3c', roughness=1.3, specular=0.25, weight='1',
                 patches=dict(scale_m=40.0, colour='#7f8a45', amount=0.4)),
            dict(name='soil', set='Ground048', tile_m=2.5, colour='#7a6248',
                 weight='smoothstep(0.255, 0.245, cells(280, 1))'),
            dict(name='crop', set='grass_ground', tile_m=2.5, colour='#b39a5c', roughness=1.3, specular=0.25,
                 weight='smoothstep(0.645, 0.655, cells(280, 1))'),
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

# a real DEM's palette (the real_place recipe), its strata (absolute metres: the reference DEMs carry their own
# heights) and the mask parameters that make its snow and tree line (masks.MaskParams fields, altitude in metres)
PLACES = {
    'lauterbrunnen': dict(palette='alpine', mask_params=dict(snowline_m=2750.0, treeline_m=1950.0)),
    'grand_canyon_toroweap': dict(
        palette='desert_sandstone', mask_params=dict(treeline_m=2200.0),
        # the Toroweap fault: the west side is down about 170 m (the Esplanade bench at 1200 m there, 1370 m east)
        strata=dict(column='toroweap', source='attribute',
                    faults=[dict(x=-1450.0, y=0.0, strike_deg=8.0, throw_m=170.0, down='west', width_m=60.0)],
                    warp=[(300.0, 4.0), (6.0, 0.6)])),
    'mount_fuji': dict(palette='volcanic', mask_params=dict(snowline_m=3150.0, treeline_m=2450.0)),
    'crater_lake': dict(palette='volcanic', mask_params=dict(treeline_m=2400.0)),
    'great_sand_dunes': dict(palette='dunes', mask_params=dict()),
    'namib_star_dunes': dict(palette='dunes', mask_params=dict()),
    'badlands_sd': dict(palette='badlands', mask_params=dict(),
                        strata=dict(column='badlands_cedar_pass', source='attribute', warp=[(250.0, 1.5), (4.0, 0.25)])),
    'badlands_sd_detail': dict(palette='badlands', mask_params=dict(),
                               strata=dict(column='badlands_cedar_pass', source='attribute',
                                           warp=[(250.0, 1.5), (4.0, 0.25)])),
    'guilin_karst': dict(palette='karst', mask_params=dict()),
    'seven_sisters': dict(palette='chalk_coast', mask_params=dict(sea_level=0.0)),
    'palouse_hills': dict(palette='farmland', mask_params=dict()),
    'monument_valley': dict(palette='desert_sandstone', mask_params=dict(),
                            strata=dict(column='monument_valley', source='attribute', z_offset_m=1500.0)),
    'meteor_crater': dict(palette='desert_sandstone', mask_params=dict(),
                          strata=dict(column='colorado_plateau', source='attribute', z_offset_m=-500.0)),
}

# ------------------------------------------------------------------------------ the expression language ---

_FUNCS = {'smoothstep': (3, 3), 'min': (2, 99), 'max': (2, 99), 'clamp': (3, 3), 'abs': (1, 1), 'pow': (2, 2),
          'mix': (3, 3), 'noise': (1, 2), 'cells': (1, 2)}

# names that stand for an expression over the masks (expanded when parsed)
DERIVED = {
    # vegetation with the masks package's stream-bed factor (1 - 0.8 channels) undone: on the fine (hero) levels
    # channels marks rills, which on level ground is nearly everywhere, so vegetation itself drops to a fifth across
    # every flat near the camera (and on the main level it veins forests along each gully). Package 4 owns the
    # factor; when its vegetation stops using the level-dependent channels, this becomes plain vegetation.
    'plants': 'min(vegetation / (1 - 0.75*channels), 1)',
}
_OPS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/'}


class ExprError(ValueError):
    pass


def parse(src):
    """A mask expression -> a tuple tree: ('num', v) | ('mask', name) | ('op', '+-*/', a, b) | ('neg', a) |
    ('call', fname, [args]). Raises ExprError naming what it can't read."""
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
            if f in ('noise', 'cells') and any(a[0] != 'num' for a in args):
                raise ExprError(f'mask expression {src!r}: {f}(scale_m[, seed]) takes numbers')
            return ('call', f, args)
        raise ExprError(f'mask expression {src!r}: {ast.dump(n)[:60]} is not part of the language '
                        f'(numbers, mask names, + - * /, and {", ".join(sorted(_FUNCS))})')
    return conv(tree)


def names_in(expr):
    """The mask names an expression (string or tree) reads."""
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


def value_noise(x, y, scale_m, seed=0, octaves=2, gain=0.5):
    """A world-space value noise of about 0..1 (mean 0.5), features `scale_m` metres across: the numpy side of the
    language's noise() (the scatter's; the material uses the shader's noise)."""
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
    return np.clip(0.5 + (v - 0.5) * 1.6, 0.0, 1.0)      # stretch the octaves' narrowed spread back toward 0..1


def voronoi_cells(x, y, scale_m, seed=0):
    """A random value 0..1 per cell of a world-space Voronoi partition, cells about scale_m across (the nearest of
    jittered lattice points): the numpy side of the language's cells(), for fields and patches with straight
    boundaries. The material uses Blender's Voronoi, so the two partitions differ."""
    gx = np.asarray(x, np.float64) / max(scale_m, 1e-9)
    gy = np.asarray(y, np.float64) / max(scale_m, 1e-9)
    ix, iy = np.floor(gx), np.floor(gy)
    best = np.full(gx.shape, np.inf)
    val = np.zeros(gx.shape)
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            cx, cy = ix + di, iy + dj
            px = cx + _hash2(cx, cy, seed * 13 + 1)
            py = cy + _hash2(cx, cy, seed * 13 + 2)
            d = (gx - px) ** 2 + (gy - py) ** 2
            closer = d < best
            best = np.where(closer, d, best)
            val = np.where(closer, _hash2(cx, cy, seed * 13 + 3), val)
    return val


def evaluate(expr, masks, x=None, y=None):
    """Evaluate an expression with numpy. masks: {name: array} or a callable name -> array (all the same shape);
    x, y: world metres of the points (needed only by noise()). A mask the dict lacks reads 0 (an absent process),
    as the material's Attribute node does."""
    t = parse(expr) if not isinstance(expr, tuple) else expr
    get = masks if callable(masks) else (lambda n: masks.get(n))
    shape = None if x is None else np.shape(x)

    def ev(n):
        k = n[0]
        if k == 'num':
            return n[1]
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
        if f in ('noise', 'cells'):
            if x is None:
                raise ExprError(f'{f}() needs the points (x, y) to evaluate with numpy')
            fn = value_noise if f == 'noise' else voronoi_cells
            return fn(x, y, args[0][1], int(args[1][1]) if len(args) > 1 else 0)
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


def resolve_name(palette, recipe=None):
    """The palette name 'auto' and recipe names resolve to (RECIPE_PALETTES), or the name itself."""
    if palette == 'auto':
        rname = recipe if isinstance(recipe, str) else getattr(recipe, 'name', None) or (
            recipe.get('name') if isinstance(recipe, dict) else None)
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
    recipe's), or a palette dict (validated as given). None is not a palette: the caller builds grey clay for it."""
    if palette is None:
        raise ValueError("palette None is grey clay: call surfacing.clay_material() instead")
    palette = resolve_name(palette, recipe)
    if isinstance(palette, str):
        if palette not in PALETTES:
            raise KeyError(f'unknown palette {palette!r}; nearest: {", ".join(_nearest(palette, PALETTES))}')
        pal = copy.deepcopy(PALETTES[palette])
        pal['name'] = palette
    elif isinstance(palette, dict):
        pal = copy.deepcopy(palette)
        pal.setdefault('name', 'custom')
    else:
        raise TypeError('palette: a name, "auto", a dict or None')
    opts = copy.deepcopy(DEFAULT_OPTIONS)
    opts.update(pal.get('options') or {})
    pal['options'] = opts
    for L in pal['layers']:
        L.setdefault('projection', 'planar')
        L.setdefault('colour', None)
        L.setdefault('tint', None)
        L.setdefault('roughness', 1.0)
        L.setdefault('normal', 1.0)
        L.setdefault('bump_m', 0.04 * float(L['tile_m']) if L['projection'] == 'box' else 0.0)
        L.setdefault('strata', False)
        L.setdefault('edge_noise', None)
        L.setdefault('weight', '1')
    pal.setdefault('strata', None)
    pal.setdefault('dressing', None)
    if validate:
        problems = check(pal)
        if problems:
            raise ValueError(f'palette {pal["name"]!r}: ' + '; '.join(problems))
    return pal


def check(pal):
    """Problems with a filled-in palette (empty list when it is fine)."""
    out = []
    layers = pal.get('layers') or []
    if not 1 <= len(layers) <= MAX_LAYERS:
        out.append(f'{len(layers)} layers: a palette has 1 to {MAX_LAYERS}')
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
        if L.get('strata') and not pal.get('strata'):
            out.append(f'{tag}: strata=True but the palette has no strata column')
        try:
            for nm in names_in(L.get('weight', '1')):
                msg = known_mask(nm)
                if msg:
                    out.append(f'{tag} weight: {msg}')
        except ExprError as e:
            out.append(f'{tag}: {e}')
    o = pal.get('options') or {}
    if o.get('interpolation') not in ('Auto', 'Cubic', 'Linear', 'Closest'):
        out.append("options.interpolation must be 'Auto', 'Cubic', 'Linear' or 'Closest'")
    if o.get('damp_where'):
        try:
            for nm in names_in(o['damp_where']):
                msg = known_mask(nm)
                if msg:
                    out.append(f'damp_where: {msg}')
        except ExprError as e:
            out.append(f'damp_where: {e}')
    st = pal.get('strata')
    if st:
        col = st.get('column')
        if isinstance(col, str) and col not in STRATA_COLUMNS:
            out.append(f'strata column {col!r}; nearest: {", ".join(_nearest(col, STRATA_COLUMNS))}')
        if st.get('source', 'attribute') not in ('attribute', 'position'):
            out.append("strata source must be 'attribute' (eido_strata) or 'position' (Position.z)")
    d = pal.get('dressing')
    if d and d.get('density') is not None:
        try:
            for nm in names_in(d['density']):
                msg = known_mask(nm)
                if msg:
                    out.append(f'dressing density: {msg}')
        except ExprError as e:
            out.append(f'dressing density: {e}')
    return out


def masks_used(pal):
    """Every mask a palette's material and rocks read (so the mesh carries them as eido_<name>)."""
    pal = get(pal) if not isinstance(pal, dict) or 'options' not in pal else pal
    out = set()
    for L in pal['layers']:
        out |= names_in(L['weight'])
    if pal['options'].get('damp_where'):
        out |= names_in(pal['options']['damp_where'])
    if pal.get('strata') and pal['strata'].get('source', 'attribute') == 'attribute':
        out.add('strata')
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
    return get(pal), place


def column_layers(column):
    """A strata column as [(name, bottom_m, top_m, colour_linear (3,), roughness, bed_m, jitter)], from a
    STRATA_COLUMNS key, a column dict, or a solver column [(thickness_m, K_factor, Sc_deg, colour_id, name), ...]
    or [(name, thickness_m), ...] (coloured by LAYER_COLOURS)."""
    if isinstance(column, str):
        column = STRATA_COLUMNS[column]
    if isinstance(column, dict):
        z = float(column.get('base_m', 0.0))
        out = []
        for name, thick, col, rough, bed, jit in column['formations']:
            if isinstance(col, (list, tuple)):          # bed colours drawn by weight: [(colour, weight), ...]
                cv = [(np.array(hex_linear(c)), float(w)) for c, w in col]
            else:
                cv = np.array(hex_linear(col))
            out.append((name, z, z + float(thick), cv, float(rough), float(bed), float(jit)))
            z += float(thick)
        return out
    out = []
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
        col = next((c for key, c in LAYER_COLOURS if key in name.lower()), '#a39a8e')
        out.append((name, z, z + thick, np.array(hex_linear(col)), 1.0, 2.5, 0.06))
        z += thick
    return out


def describe(palette):
    """One page on a palette: its layers (scan, tile, colour, projection, weight) and its rocks."""
    pal = get(palette)
    lines = [f"{pal['name']}: {pal.get('title', '')}"]
    for i, L in enumerate(pal['layers']):
        lines.append(f"  {i} {L['name']:<14} {L['set']:<26} tile {L['tile_m']:>5.1f} m  {L['projection']:<6} "
                     f"colour {L['colour'] or 'scan'}{'  strata' if L['strata'] else ''}")
        lines.append(f"      weight: {L['weight']}")
    if pal.get('strata'):
        lines.append(f"  strata: {pal['strata']}")
    d = pal.get('dressing')
    if d:
        lines.append(f"  rocks: {', '.join(d.get('models', []))}  colour {d.get('colour')}")
        lines.append(f"      density (per m^2): {d.get('density')}")
    lines.append(f"  masks read: {', '.join(sorted(masks_used(pal)))}")
    return '\n'.join(lines)


__all__ = ['PALETTES', 'STRATA_COLUMNS', 'LAYER_COLOURS', 'RECIPE_PALETTES', 'PLACES', 'DEFAULT_OPTIONS',
           'LANDSCAPE_MACRO', 'MAX_LAYERS', 'ExprError', 'parse', 'names_in', 'evaluate', 'value_noise', 'names',
           'get', 'check', 'masks_used', 'for_place', 'column_layers', 'describe', 'hex_linear', 'srgb_to_linear',
           'linear_to_srgb', 'resolve_name']
