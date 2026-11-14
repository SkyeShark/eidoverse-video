"""The terrain's ecotopes (surfacing design section 4.2): which plants a kind of place grows and where, as data. An
ecotope is a list of species, each with a density written in the palettes' mask expression language, so a plant rule
reads the same terrain data a material layer does. No bpy: build/plants.py turns an ecotope into spots, and
build/plant_instances.py instances the spots in Blender.

    from eidoblend.terrain.build import ecotopes as E
    E.names()                                  # ['alpine', 'badlands', 'chalk_coast', 'desert_sandstone', ...]
    eco = E.get('alpine')                      # a validated deep copy, every default filled in
    eco = E.get('auto', recipe='fluvial_range')        # the recipe's palette's ecotope with its RECIPE_ECOTOPES
    eco = E.get('auto', recipe='real_place', place='lauterbrunnen')   # a real place's (PLACE_ECOTOPES)
    E.describe('alpine')                       # one page: species, sources, densities, sizes
    E.ecotope_hash(eco)                        # what the spots' file names the ecotope by

An ecotope is a dict:
    title        what it is
    constants    terrain constants its expressions may read over the palette's (palettes.CONSTANTS: latitude_deg
                 sets the climatological sun the derived `insolation` is measured against, palettes.climate_sun),
                 and the plant layer's own: channel_flow (the `flow` a cell needs to count as a stream for
                 `dist_channel`, default 0.8)
    species      the plants, each a dict:
        name         a label, unique in the ecotope; it names the spots' file
        kind         'tree', 'shrub', 'grass', 'forb' or 'groundcover': it sets the defaults below (KINDS)
        source       what an instancer grows for it:
                       ('seedthree', species, dials, seeds)   a SeedThree species (make_seed_tree) with its dials,
                                                              one individual per seed
                       ('flora', species, opts)               a flora-family species (create_flora) with its options;
                                                              opts['seeds'] lists the individuals (default [7])
                       ('ph', asset, opts)                    a scanned Poly Haven plant set (create_flora 'ph:<asset>')
        density      plants per m^2 at full size, a mask expression (below)
        size_m       (min, max) height in metres: a plant's size grows with its age from min toward max
        stature      None, or a mask expression 0..1: the share of that height the site lets a plant reach (the
                     krummholz toward the treeline, stunted shrubs on bare ground); stunted plants keep their
                     smaller hard core, so they stand closer
        age          dict(shape, scale, stand): ages are Weibull(shape, scale) clipped to 0..1; `stand` of a plant's
                     age is its cluster's (a stand shares its age), the rest its own
        cluster      dict(parents_per_ha, mu, sigma_m): the Thomas cluster process the candidates are drawn from:
                     parents_per_ha cluster centres per hectare, each with a Poisson(mu) number of plants scattered
                     sigma_m metres around it. parents_per_ha x mu is the most plants per hectare the species can
                     reach: where `density` asks for more, it is clipped (plan_plants reports how often)
        core_m       the hard-core radius at full size, metres (a crown's half-width; flora's footRadius): two plants
                     of one priority stand no closer than 0.75 x the sum of their radii. 0: no hard core (grass blades)
        foot_m       the radius plants of a LOWER priority keep clear of (a trunk and its root flare; default core_m,
                     0.15 x core_m for trees, so shrubs and grass grow under a crown)
        priority     the placing order: lower numbers first, and they win the ground. Species of one priority are
                     placed together
        shade        dict(tolerance, radius): how it takes the shade of the trees already placed: within `radius`
                     crown radii of a tree its density is multiplied by 1 - shade x (1 - tolerance)
        casts_shade  True: the species shades the ones placed after it (default: trees)
        around       None, or dict(species, per, radius, where): understory seeded around another species' plants
                     (per plant of `species`, a Poisson(per) number of candidates within `radius` crown radii, kept
                     where the expression `where` allows): what a forest floor grows at the feet of its trees
        ground       the material layer the species implies under it (litter under conifers), a layer name of the
                     palette, or None
        max_radius_m how far from the focus it is placed
        max_cell_m   the coarsest level cell it is placed on (None: any level): shrubs want 4 m cells or finer,
                     grass the finest levels, so a plant is never placed on ground that does not resolve its site
        lod_m_per_m  the smallest size kept grows by this much per metre from the focus (as the rocks' does)
        fade         (from, to) fractions of max_radius_m over which the species thins out to nothing (the band the
                     material's far canopy takes over in)
        max_count    a cap on the species' spots (the smallest and farthest go first)
        lod          dict(hero_m, billboard_m, near_m): SeedThree species show their full level within hero_m of the
                     focus, their card level within billboard_m of the camera and their billboard beyond; flora
                     species sway and part within near_m of the focus and stand still beyond
        align        0..1: how far its up axis leans from world up toward the ground's normal (recorded with the
                     spots; Blender's instancers stand plants upright)
        sink         metres at full size the plant's base sits under the ground
        on           substrates the species grows on that plants otherwise keep off: any of 'water', 'snow', 'rock',
                     'talus', 'sand'
        roots_m      the talus or sand thickness (metres) its roots still reach through
        range_per_ha (min, max) stems per hectare where it is at home (where `density` is at least half of
                     parents_per_ha x mu): what the checks hold the plan to

The density language is palettes.py's (numbers, mask names, the terrain constants, + - * /, smoothstep, min, max,
clamp, abs, pow, mix, noise, fbm, cells, and its derived names altitude, cover, bare and plants). A plan given the
terrain's surface bake (plan_plants(data=)) reads its maps too (surface.maps.MAPS: settle, valley, snowpack, crest,
cavity, fresh ...), as the material does; without one such a name reads 0, so a rule stays usable on a terrain
without a bake. Plus the plant layer's derived names (plants.DERIVED_NAMES):
    soil          loose cover the roots hold in, metres: deposit + talus + sand (scaled by `settle` when a surface
                  bake gives it)
    insolation    0..1: the cosine between the ground's normal and the ecotope's sun
    dist_channel  metres to the nearest stream (cells whose `channels` mask is on, or whose `flow` is at least
                  channel_flow, on the main and context levels): pow(0.5, dist_channel / 30) halves every 30 m
    shade         0..1: the shade of the shade-casting plants already placed
    ledge         0..1: the strata relief's ledges (0 until the material's strata_array is there to read)
Every species stays off water deeper than 0.05 m, snow (snowpack over 0.2 m; without a surface bake the snow mask
over 0.5), bare rock (bare over 0.5) and talus or sand thicker than roots_m, unless `on` names the substrate. The
palettes' `plants` term is the base suitability to build a density on; the masks package's `vegetation` is not (it
multiplies by `rock`, which reads nearly 1 on eroded landforms).

How the rules are written (in the spirit of Far Cry 5's biome recipes and EcoBrush): forest on north-facing, concave,
moist ground and grass on convex, exposed ground; riparian belts falling off with dist_channel; shrubs at talus
margins; smaller, sparser trees toward the treeline; the avalanche tracks (flow on steep slopes) kept clear. Densities
read terrain terms, with noise only as a small residual: the numpy noise here and the shader's noise in the material
are different noises, so a boundary drawn by noise would stand somewhere else in the ground's layers.
"""
from __future__ import annotations

import copy
import hashlib
import json

from . import palettes as P

KIND_NAMES = ('tree', 'shrub', 'grass', 'forb', 'groundcover')
SOURCES = ('seedthree', 'flora', 'ph')
SUBSTRATES = ('water', 'snow', 'rock', 'talus', 'sand')

# what a species takes from its kind when it does not say. max_count holds a scene to what EEVEE renders within a
# render job's memory and an eye-level frame's time: a SeedThree billboard instance (two crossed cards) cost about
# 40 microseconds of frame and several KB of memory at render (290 000 spruce: 25.6 s a frame, +3.2 GB at the peak,
# against 0.5 s without them), on top of a terrain that renders at 7.3-8.3 GB. A capped plan keeps the largest
# plants for their distance, and hands what it drops to the material's far cover (PlantSpots.cover, canopy_far)
KINDS = {
    'tree': dict(priority=0, max_radius_m=2500.0, max_cell_m=None, lod_m_per_m=0.0015, roots_m=2.0, casts_shade=True,
                 shade=dict(tolerance=0.5, radius=1.0), lod=dict(hero_m=40.0, billboard_m=120.0, near_m=0.0),
                 sink=0.3, align=0.0, max_count=50000, fade=(0.8, 1.0),
                 age=dict(shape=2.2, scale=0.6, stand=0.6), cluster=dict(parents_per_ha=60.0, mu=5.0, sigma_m=7.0)),
    'shrub': dict(priority=1, max_radius_m=400.0, max_cell_m=4.0, lod_m_per_m=0.003, roots_m=0.8, casts_shade=False,
                  shade=dict(tolerance=0.5, radius=1.0), lod=dict(hero_m=25.0, billboard_m=60.0, near_m=30.0),
                  sink=0.05, align=0.0, max_count=40000, fade=(0.8, 1.0),
                  age=dict(shape=2.0, scale=0.65, stand=0.4), cluster=dict(parents_per_ha=150.0, mu=5.0, sigma_m=3.0)),
    'grass': dict(priority=2, max_radius_m=100.0, max_cell_m=1.0, lod_m_per_m=0.006, roots_m=0.4, casts_shade=False,
                  shade=dict(tolerance=0.3, radius=1.0), lod=dict(hero_m=0.0, billboard_m=0.0, near_m=25.0),
                  sink=0.0, align=0.0, max_count=60000, fade=(0.75, 1.0),
                  age=dict(shape=2.5, scale=0.7, stand=0.3), cluster=dict(parents_per_ha=1000.0, mu=8.0, sigma_m=1.2)),
    'forb': dict(priority=2, max_radius_m=80.0, max_cell_m=1.0, lod_m_per_m=0.006, roots_m=0.3, casts_shade=False,
                 shade=dict(tolerance=0.3, radius=1.0), lod=dict(hero_m=0.0, billboard_m=0.0, near_m=25.0),
                 sink=0.0, align=0.0, max_count=20000, fade=(0.75, 1.0),
                 age=dict(shape=2.5, scale=0.7, stand=0.3), cluster=dict(parents_per_ha=400.0, mu=8.0, sigma_m=1.0)),
    'groundcover': dict(priority=3, max_radius_m=40.0, max_cell_m=0.6, lod_m_per_m=0.004, roots_m=0.2,
                        casts_shade=False, shade=dict(tolerance=0.7, radius=1.0),
                        lod=dict(hero_m=0.0, billboard_m=0.0, near_m=15.0), sink=0.0, align=0.0, max_count=20000,
                        fade=(0.75, 1.0), age=dict(shape=2.5, scale=0.7, stand=0.3),
                        cluster=dict(parents_per_ha=2000.0, mu=10.0, sigma_m=0.6)),
}

# the plant layer's own constants (an ecotope's `constants` may set them). The sun `insolation` is measured against
# is the place's climatological one (palettes.climate_sun: its latitude_deg, or the palette's sun_azimuth_deg and
# sun_elevation_deg), the one the bake and the material read
CONSTANTS = {
    'channel_flow': 0.8,            # the `flow` a cell needs to count as a stream for dist_channel
}

# ------------------------------------------------------------------------------------------ the sources ---
# SeedThree has no spruce, hemlock, chamise or manzanita. What stands in, and how it is dialled on our side:

# Norway spruce and the subalpine firs and hemlocks: the Douglas fir with short first-level branches (a crown about
# a quarter of its height across, where the species' own is three quarters) that droop a little below the horizontal
_NARROW_CONIFER = dict(height=30, paramOverrides=dict(length={1: 0.14}, downAngle={1: 98}))
_SPRUCE = ('seedthree', 'douglasFir', _NARROW_CONIFER, [11, 23])
# a broadleaf of the valley floors and stream sides (sycamore maple, ash and alder at Lauterbrunnen): the red maple
_MAPLE = ('seedthree', 'redMaple', dict(), [5, 17])
# blackbrush's stems: SeedThree's dormant slate grey (its own measurement, linear 0.40, 0.42, 0.47) from the species'
# bark texture; the species' bark tint, made for the app's light, leaves the brown texture magenta-grey (red and blue
# over green), which reads lavender under a daylit sky
_BLACKBRUSH_BARK = 0xb4c8e4
# chaparral: creosote bush and blackbrush, the densest evergreen shrubs SeedThree grows, tinted to chamise's dark olive
_CHAPARRAL_A = ('seedthree', 'creosote', dict(leafColorize=0x4d5a2c, leafTintAmount=0.55), [3])
_CHAPARRAL_B = ('seedthree', 'blackbrush', dict(leafColorize=0x56602f, leafTintAmount=0.45, barkTint=_BLACKBRUSH_BARK),
                [7])

ECOTOPES = {
    'alpine': dict(
        title='Alpine: spruce forest on the valley sides, maples along the streams of the floor, meadow grass and '
              'flowers near the camera',
        species=[
            # spruce holds the 12-55 degree sides below the treeline, north faces and hollows first (the palette's
            # forest layer, on terrain terms alone); the floor is cleared pasture; the avalanche tracks down the
            # drainage lines of the steep slopes stay open; toward the treeline the stand thins out and its trees
            # stay low (krummholz, a third of their height at the line)
            dict(name='spruce', kind='tree', source=_SPRUCE, size_m=(7.0, 32.0), core_m=2.3,
                 stature='0.25 + 0.75*smoothstep(treeline_m + 80, treeline_m - 300, altitude + 100*northness)',
                 cluster=dict(parents_per_ha=110.0, mu=6.0, sigma_m=7.0), range_per_ha=(200.0, 660.0),
                 ground='forest', shade=dict(tolerance=0.6, radius=1.0),
                 density='0.066 * smoothstep(0.42, 0.62, 0.8*plants + 0.45*smoothstep(20, 34, slope) + 0.1*concave_20m '
                         '+ 0.08*northness - 0.4*smoothstep(0.62, 0.86, flow)*smoothstep(18, 28, slope)) '
                         '* smoothstep(6, 12, slope) * smoothstep(66, 56, slope) '
                         '* smoothstep(treeline_m + 80, treeline_m - 150, altitude + 100*northness)'),
            # maples in a line along the streams of the gentle floor, and a single tree in the pastures now and then
            # (lauterbrunnen_01: open meadow, one belt of broadleaves along the river; a belt halving every 30 m made
            # a grove of the whole 300-500 m floor)
            dict(name='maple', kind='tree', source=_MAPLE, size_m=(6.0, 17.0), core_m=3.2,
                 cluster=dict(parents_per_ha=30.0, mu=5.0, sigma_m=9.0), range_per_ha=(20.0, 150.0),
                 shade=dict(tolerance=0.5, radius=1.0),
                 density='smoothstep(0.25, 0.55, plants) * smoothstep(treeline_m - 500, treeline_m - 800, altitude) '
                         '* (0.014 * pow(0.5, dist_channel / 12) * smoothstep(16, 7, slope) '
                         '+ 0.00015 * smoothstep(22, 8, slope))'),
            # meadow grass: bunches of blades wherever the pasture grows, thinner under the trees
            dict(name='meadow grass', kind='grass', source=('flora', 'grass', dict(height=0.34, color='green',
                                                                                 seeds=[7, 11])),
                 size_m=(0.22, 0.42), core_m=0.0, max_radius_m=45.0, lod_m_per_m=0.0085,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(0.15, 0.45, plants) * smoothstep(40, 28, slope) * (1 - 0.6*shade)'),
            # white flowers in drifts through the meadow (lauterbrunnen_01's umbels)
            dict(name='meadow flowers', kind='forb', source=('flora', 'daisy', dict(color='white', height=0.4,
                                                                                    seeds=[5])),
                 size_m=(0.25, 0.45), core_m=0.0, max_radius_m=35.0, lod_m_per_m=0.012,
                 cluster=dict(parents_per_ha=600.0, mu=9.0, sigma_m=1.1), range_per_ha=(500.0, 5400.0),
                 density='0.5 * smoothstep(0.3, 0.6, plants) * smoothstep(30, 16, slope) * (1 - 0.8*shade)'),
        ]),
    'desert_sandstone': dict(
        title='Desert sandstone: blackbrush and sagebrush on the benches and plateaus, bunchgrass between them, a few '
              'yuccas; nothing on the cliffs and the washes',
        species=[
            # blackbrush: the plateau's shrub, a plant every few metres on the gentle ground, more in the moist
            # hollows and fewer on the convex rims, none in the washes or on thick fill
            dict(name='blackbrush', kind='shrub',
                 source=('seedthree', 'blackbrush', dict(barkTint=_BLACKBRUSH_BARK), [7, 19]),
                 size_m=(0.35, 1.0), core_m=0.55, range_per_ha=(250.0, 1200.0),
                 cluster=dict(parents_per_ha=200.0, mu=6.0, sigma_m=4.0),
                 density='0.12 * smoothstep(30, 16, slope) * smoothstep(0.3, 0.6, plants + 0.15*concave_20m '
                         '- 0.2*convex_20m + 0.2*(fbm(60, 1) - 0.5)) * smoothstep(0.93, 0.85, flow) '
                         '* (1 - 0.75*smoothstep(1.0, 6.0, deposit))'),
            # big sagebrush and snakeweed: grey shrubs where water gathers, along the wash margins and in the swales
            dict(name='sagebrush', kind='shrub', source=('seedthree', 'sagebrush', dict(), [3]),
                 size_m=(0.4, 1.3), core_m=0.6, range_per_ha=(40.0, 320.0),
                 cluster=dict(parents_per_ha=80.0, mu=4.0, sigma_m=5.0),
                 density='0.032 * smoothstep(24, 10, slope) * smoothstep(0.45, 0.75, plants + 0.35*wetness '
                         '+ 0.2*concave_20m) * smoothstep(0.95, 0.88, flow)'),
            # bunchgrass between the shrubs: tw_04's green tufts on the red soil (its grass, linear and at unit
            # luminance, is 0.83, 1.12, 0.29: flora's 'green')
            dict(name='bunchgrass', kind='grass', source=('flora', 'galleta_dry', dict(color='green', seeds=[7, 13])),
                 size_m=(0.25, 0.6), core_m=0.22, max_radius_m=110.0, lod_m_per_m=0.005,
                 cluster=dict(parents_per_ha=900.0, mu=8.0, sigma_m=1.6), range_per_ha=(1500.0, 7200.0),
                 density='0.72 * smoothstep(28, 14, slope) * smoothstep(0.25, 0.55, plants) '
                         '* smoothstep(0.95, 0.88, flow)'),
            dict(name='yucca', kind='shrub', source=('flora', 'yucca', dict(seeds=[7, 11])), priority=1,
                 size_m=(0.6, 1.2), core_m=0.6, max_radius_m=150.0, range_per_ha=(5.0, 60.0),
                 cluster=dict(parents_per_ha=20.0, mu=3.0, sigma_m=6.0),
                 density='0.006 * smoothstep(30, 12, slope) * smoothstep(0.2, 0.5, plants) '
                         '* smoothstep(0.1, 0.5, insolation + 0.3*convex_20m)'),
        ]),
    'volcanic': dict(
        title='Volcanic: a continuous conifer forest on the flanks below the treeline, pines on the dry convex ground, '
              'grass tufts on the ash flats',
        species=[
            # the fir and hemlock forest: wherever soil and moisture allow, thinner on the young lava and toward the
            # treeline; the flattest aprons (the pumice flats) stay open
            dict(name='fir', kind='tree', source=_SPRUCE, size_m=(6.0, 30.0), core_m=2.3,
                 stature='0.25 + 0.75*smoothstep(treeline_m + 80, treeline_m - 300, altitude + 100*northness)',
                 cluster=dict(parents_per_ha=100.0, mu=6.0, sigma_m=8.0), range_per_ha=(150.0, 600.0),
                 ground='forest', shade=dict(tolerance=0.6, radius=1.0),
                 density='0.06 * smoothstep(0.3, 0.52, plants + 0.1*concave_20m + 0.08*northness) '
                         '* smoothstep(0.5, 6.0, slope) * smoothstep(48, 38, slope) '
                         '* (1 - 0.8*smoothstep(0.2, 0.6, lava)) '
                         '* smoothstep(treeline_m + 80, treeline_m - 150, altitude + 100*northness)'),
            dict(name='pine', kind='tree', source=('seedthree', 'pine', dict(height=20), [9]), size_m=(5.0, 22.0),
                 core_m=2.8, cluster=dict(parents_per_ha=40.0, mu=4.0, sigma_m=10.0), range_per_ha=(20.0, 160.0),
                 shade=dict(tolerance=0.2, radius=1.2),
                 density='0.016 * smoothstep(0.2, 0.45, plants) * smoothstep(0.25, 0.6, insolation + 0.3*convex_20m) '
                         '* smoothstep(44, 30, slope) '
                         '* smoothstep(treeline_m + 150, treeline_m - 100, altitude + 100*northness)'),
            dict(name='ash grass', kind='grass', source=('flora', 'galleta_dry', dict(seeds=[7, 13])),
                 size_m=(0.2, 0.5), core_m=0.2, max_radius_m=90.0,
                 cluster=dict(parents_per_ha=700.0, mu=8.0, sigma_m=1.5), range_per_ha=(800.0, 5600.0),
                 density='0.5 * smoothstep(0.1, 0.4, plants) * smoothstep(26, 12, slope) * (1 - 0.7*shade)'),
        ]),
    'dunes': dict(
        title='Dunes: dry grass tufts on the interdune floor and the stable sand sheet, a few shrubs at the dunes\' feet',
        species=[
            # dune grass (the Namib's bushman grass, Great Sand Dunes' ricegrass): tufts on thin sand and gravel, in
            # drifts with bare ground between; none on the active dunes
            dict(name='dune grass', kind='grass', source=('flora', 'galleta_dry', dict(seeds=[7, 13])),
                 size_m=(0.25, 0.65), core_m=0.24, max_radius_m=160.0, lod_m_per_m=0.004, on=('sand',),
                 cluster=dict(parents_per_ha=1500.0, mu=9.0, sigma_m=1.8), range_per_ha=(2500.0, 13500.0),
                 density='1.3 * smoothstep(3.0, 0.4, sand) * smoothstep(9, 3, slope) '
                         '* smoothstep(0.3, 0.55, 0.5*plants + 0.5*fbm(30, 2))'),
            dict(name='dune shrub', kind='shrub', source=('seedthree', 'creosote', dict(), [3]), on=('sand',),
                 size_m=(0.5, 1.6), core_m=0.9, cluster=dict(parents_per_ha=12.0, mu=3.0, sigma_m=8.0),
                 range_per_ha=(2.0, 36.0),
                 density='0.0036 * smoothstep(4.0, 0.5, sand) * smoothstep(10, 3, slope) '
                         '* smoothstep(0.2, 0.6, concave_20m + 0.5*wetness)'),
        ]),
    'badlands': dict(
        title='Badlands: mixed-grass prairie on the tables and the plain, sagebrush in the draws; the clay walls bare',
        species=[
            dict(name='prairie grass', kind='grass', source=('flora', 'galleta_dry', dict(seeds=[7, 13])),
                 size_m=(0.25, 0.6), core_m=0.2, max_radius_m=110.0, lod_m_per_m=0.005,
                 cluster=dict(parents_per_ha=2500.0, mu=9.0, sigma_m=1.4), range_per_ha=(5000.0, 22500.0),
                 density='2.2 * smoothstep(0.2, 0.5, plants) * smoothstep(16, 7, slope) '
                         '* (1 - smoothstep(0.15, 0.45, convex_20m))'),
            dict(name='sagebrush', kind='shrub', source=('seedthree', 'sagebrush', dict(), [3]),
                 size_m=(0.4, 1.2), core_m=0.6, cluster=dict(parents_per_ha=50.0, mu=4.0, sigma_m=5.0),
                 range_per_ha=(20.0, 200.0),
                 density='0.02 * smoothstep(0.4, 0.7, plants + 0.3*wetness + 0.2*concave_20m) '
                         '* smoothstep(16, 6, slope)'),
        ]),
    'karst': dict(
        title='Karst: broadleaf forest on every flank the towers let it hold, trees along the river and the field '
              'edges of the plain',
        species=[
            # the towers' forest: denser where soil holds (the gentler, concave ground), thin scrub on the steep
            # flanks, none on the sheer walls
            dict(name='broadleaf', kind='tree', source=('seedthree', 'sweetgum', dict(height=14), [5, 17]),
                 size_m=(4.0, 15.0), core_m=2.6, cluster=dict(parents_per_ha=110.0, mu=6.0, sigma_m=6.0),
                 range_per_ha=(150.0, 660.0), ground='forest', shade=dict(tolerance=0.6, radius=1.0),
                 density='0.066 * smoothstep(9, 17, slope) * smoothstep(80, 62, slope) '
                         '* (0.45 + 0.55*smoothstep(60, 35, slope + 10*convex_20m - 10*concave_20m))'),
            dict(name='riverside trees', kind='tree', source=_MAPLE, size_m=(6.0, 16.0), core_m=3.2,
                 cluster=dict(parents_per_ha=30.0, mu=5.0, sigma_m=9.0), range_per_ha=(15.0, 150.0),
                 density='0.014 * pow(0.5, dist_channel / 25) * smoothstep(8, 3, slope)'),
        ]),
    'chalk_coast': dict(
        title='Chalk coast: downland turf to the cliff edge, flowers in it',
        species=[
            dict(name='downland grass', kind='grass', source=('flora', 'grass', dict(height=0.22, color='green',
                                                                                   seeds=[7, 11])),
                 size_m=(0.14, 0.28), core_m=0.0, max_radius_m=40.0, lod_m_per_m=0.006,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(0.15, 0.45, plants) * smoothstep(38, 26, slope)'),
            dict(name='downland flowers', kind='forb', source=('flora', 'daisy', dict(color='white', height=0.25,
                                                                                      seeds=[5])),
                 size_m=(0.15, 0.3), core_m=0.0, max_radius_m=30.0, lod_m_per_m=0.008,
                 cluster=dict(parents_per_ha=600.0, mu=9.0, sigma_m=1.1), range_per_ha=(500.0, 5400.0),
                 density='0.5 * smoothstep(0.3, 0.6, plants) * smoothstep(28, 14, slope)'),
        ]),
    'farmland': dict(
        title='Farmland: grass on the verges and pastures near the camera (the crops are the material\'s fields)',
        species=[
            dict(name='field grass', kind='grass', source=('flora', 'grass', dict(height=0.3, color='green',
                                                                                seeds=[7, 11])),
                 size_m=(0.2, 0.38), core_m=0.0, max_radius_m=40.0, lod_m_per_m=0.008,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(0.15, 0.45, plants) * smoothstep(0.26, 0.3, cells(500, 1, 14)) '
                         '* smoothstep(0.645, 0.6, cells(500, 1, 14))'),
        ]),
    'meadow': dict(
        title='Meadow: grass and flowers',
        species=[
            dict(name='meadow grass', kind='grass', source=('flora', 'grass', dict(height=0.4, color='green',
                                                                                 seeds=[7, 11])),
                 size_m=(0.25, 0.5), core_m=0.0, max_radius_m=40.0, lod_m_per_m=0.01,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(30, 20, slope)'),
            dict(name='meadow flowers', kind='forb', source=('flora', 'daisy', dict(seeds=[5])),
                 size_m=(0.25, 0.45), core_m=0.0, max_radius_m=30.0, lod_m_per_m=0.012,
                 cluster=dict(parents_per_ha=600.0, mu=9.0, sigma_m=1.1), range_per_ha=(500.0, 5400.0),
                 density='0.5 * smoothstep(26, 14, slope)'),
        ]),
}

# what a recipe's 'auto' ecotope takes on top of its palette's (as palettes.RECIPE_LOOKS does for the material):
# `species` entries by name are merged over the palette's (None removes one), new names are added, `constants` merge
RECIPE_ECOTOPES = {
    # the river-carved range is judged against the San Gabriel Mountains: chaparral on every slope it can hold, denser
    # on north faces and in the draws, oaks and sycamores along the canyon floors, dry grass and yuccas on the sunny
    # gentle ground; no spruce, no meadow
    'fluvial_range': dict(
        title='Chaparral range: dense evergreen brush on the slopes, oaks and sycamores in the canyons, dry grass',
        species={
            'spruce': None, 'maple': None, 'meadow grass': None, 'meadow flowers': None,
            'chaparral': dict(kind='shrub', source=_CHAPARRAL_A, size_m=(0.9, 2.6), core_m=1.0, max_radius_m=450.0,
                              cluster=dict(parents_per_ha=420.0, mu=6.0, sigma_m=4.0), range_per_ha=(500.0, 2520.0),
                              density='0.25 * smoothstep(0.25, 0.5, plants + 0.35*smoothstep(10, 26, slope) '
                                      '+ 0.12*northness + 0.1*concave_20m - 0.3*convex_20m) * smoothstep(4, 9, slope) '
                                      '* smoothstep(52, 44, slope)'),
            'low chaparral': dict(kind='shrub', source=_CHAPARRAL_B, size_m=(0.5, 1.3), core_m=0.6,
                                  max_radius_m=350.0, cluster=dict(parents_per_ha=250.0, mu=5.0, sigma_m=3.0),
                                  range_per_ha=(200.0, 1250.0),
                                  density='0.12 * smoothstep(0.2, 0.45, plants + 0.3*smoothstep(8, 22, slope)) '
                                          '* smoothstep(0.1, 0.5, insolation + 0.3*convex_20m) '
                                          '* smoothstep(50, 40, slope)'),
            'oak': dict(kind='tree', source=('seedthree', 'whiteOak', dict(height=9), [1737]), size_m=(4.0, 10.0),
                        core_m=3.0, cluster=dict(parents_per_ha=30.0, mu=4.0, sigma_m=10.0),
                        range_per_ha=(10.0, 120.0), max_radius_m=1500.0,
                        density='smoothstep(0.25, 0.5, plants + 0.3*smoothstep(8, 22, slope)) * smoothstep(44, 30, slope) '
                                '* (0.012 * pow(0.5, dist_channel / 45) + 0.003 * smoothstep(0.2, 0.7, northness))'),
            'sycamore': dict(kind='tree', source=('seedthree', 'americanSycamore', dict(height=16), [5]),
                             size_m=(7.0, 18.0), core_m=3.6, cluster=dict(parents_per_ha=20.0, mu=4.0, sigma_m=9.0),
                             range_per_ha=(8.0, 80.0), max_radius_m=1500.0,
                             density='0.008 * pow(0.5, dist_channel / 20) * smoothstep(14, 6, slope)'),
            'dry grass': dict(kind='grass', source=('flora', 'galleta_dry', dict(seeds=[7, 13])),
                              size_m=(0.25, 0.6), core_m=0.2, max_radius_m=100.0, lod_m_per_m=0.005,
                              cluster=dict(parents_per_ha=1200.0, mu=8.0, sigma_m=1.5), range_per_ha=(1500.0, 9600.0),
                              density='0.9 * smoothstep(0.15, 0.4, plants) * smoothstep(30, 14, slope) '
                                      '* (1 - 0.6*shade)'),
            'yucca': dict(kind='shrub', source=('flora', 'yucca', dict(seeds=[7, 11])), size_m=(0.6, 1.3),
                          core_m=0.6, max_radius_m=150.0, cluster=dict(parents_per_ha=30.0, mu=3.0, sigma_m=6.0),
                          range_per_ha=(5.0, 90.0),
                          density='0.009 * smoothstep(0.3, 0.7, insolation + 0.3*convex_20m) * smoothstep(42, 20, slope)'),
        }),
    # a cinder-cone field on a dry plateau (SP Crater): pines scattered on the plain, none on the cones' loose
    # cinders, straw grass between them
    'cinder_cones': dict(
        title='Cinder-cone field: scattered pines and straw grass on the plain, bare cinders on the cones',
        species={
            'fir': None,
            'pine': dict(density='0.004 * smoothstep(0.35, 0.75, plants + 0.25*wetness - 0.2*convex_20m) '
                                 '* smoothstep(14, 7, slope)',
                         cluster=dict(parents_per_ha=14.0, mu=3.0, sigma_m=14.0), range_per_ha=(2.0, 42.0)),
            'ash grass': dict(density='0.7 * smoothstep(0.1, 0.36, plants) * smoothstep(22, 12, slope)'),
        }),
}

# a real place's ecotope (the real_place recipe's DEM): the palette's, or a recipe's, with the same kind of merge
PLACE_ECOTOPES = {
    'san_gabriel_mountains': dict(base='fluvial_range'),
    'sp_crater': dict(base='cinder_cones'),
}


# ----------------------------------------------------------------------------------------- resolution, checks ---

def names():
    return sorted(ECOTOPES)


def _merge(eco, over):
    """An override (RECIPE_ECOTOPES' form) merged into an ecotope dict, in place."""
    for k, v in copy.deepcopy(over).items():
        if k == 'species':
            by = {s['name']: s for s in eco['species']}
            for name, entry in v.items():
                if entry is None:
                    by.pop(name, None)
                elif name in by:
                    by[name].update(entry)
                else:
                    by[name] = dict(entry, name=name)
            eco['species'] = list(by.values())
        elif k == 'constants':
            eco['constants'] = dict(eco.get('constants') or {}, **v)
        elif k != 'base':
            eco[k] = v
    return eco


def _palette_base(palette):
    """The palette name an ecotope is looked up by: a palette's name without a strata column ('<base>+<column>'),
    or None for 'auto', None or a nameless dict."""
    if isinstance(palette, dict):
        palette = palette.get('name')
    if isinstance(palette, str) and palette != 'auto':
        return palette.split('+')[0]
    return None


def resolve_name(ecotope='auto', recipe=None, place=None, palette=None):
    """(base ecotope name, [overrides]) for 'auto'. The base is the palette's ecotope: the terrain's palette (a
    name, or a dict's name), else the place's (palettes.PLACES), else the recipe's own. On top of it come the
    recipe's RECIPE_ECOTOPES, when the palette is the recipe's own (as RECIPE_LOOKS: another palette keeps its own
    plants), and the place's PLACE_ECOTOPES (whose `base` names a recipe to start from)."""
    if ecotope != 'auto':
        return ecotope, []
    rname = P._recipe_name(recipe)
    defaults = getattr(recipe, 'defaults', None) or (recipe.get('defaults') if isinstance(recipe, dict) else None)
    own = _palette_base((defaults or {}).get('palette'))
    pe = PLACE_ECOTOPES.get(place) if isinstance(place, str) else None
    if pe is not None and pe.get('base'):
        rname, own, palette = pe['base'], None, None
    if own not in ECOTOPES:
        own = P.RECIPE_PALETTES.get(rname, own)
    base = _palette_base(palette)
    if base is None and isinstance(place, str) and place in P.PLACES:
        base = P.PLACES[place]['palette']
    if base not in ECOTOPES:
        base = own or base or 'meadow'
    over = []
    if rname in RECIPE_ECOTOPES and base == own:
        over.append(RECIPE_ECOTOPES[rname])
    if pe is not None:
        over.append(pe)
    return base, over


def get(ecotope='auto', recipe=None, place=None, palette=None, validate=True):
    """An ecotope as a validated deep copy with every default filled in. ecotope: a name from names(), 'auto' (the
    place's, the recipe's or the palette's: a real place's palette and RECIPE_ECOTOPES / PLACE_ECOTOPES on top), or an
    ecotope dict (validated as given). A palette without an ecotope gives one with no species."""
    if isinstance(ecotope, dict):
        eco = copy.deepcopy(ecotope)
        eco.setdefault('name', 'custom')
    elif isinstance(ecotope, str):
        base, over = resolve_name(ecotope, recipe, place, palette)
        if base not in ECOTOPES:
            if ecotope != 'auto':
                raise KeyError(f'unknown ecotope {ecotope!r}; nearest: {", ".join(P._nearest(ecotope, ECOTOPES))}')
            eco = dict(title=f'{base}: no ecotope', species=[])
        else:
            eco = copy.deepcopy(ECOTOPES[base])
        eco['name'] = base
        for o in over:
            _merge(eco, o)
        if over:
            eco['name'] = base + '+' + str((place if place in PLACE_ECOTOPES else None) or P._recipe_name(recipe)
                                           or 'look')
    else:
        raise TypeError('ecotope: a name, "auto" or a dict')
    eco.setdefault('title', eco['name'])
    eco['constants'] = dict(eco.get('constants') or {})
    out = []
    for s in eco.get('species') or []:
        s = dict(s)
        kind = s.get('kind')
        if kind not in KINDS:
            raise ValueError(f"ecotope {eco['name']!r}: species {s.get('name')!r} has kind {kind!r}; the kinds are "
                             f"{', '.join(KIND_NAMES)}")
        for k, v in KINDS[kind].items():
            if isinstance(v, dict):
                s[k] = dict(v, **(s.get(k) or {}))
            else:
                s.setdefault(k, copy.deepcopy(v))
        s.setdefault('core_m', 0.0)
        s.setdefault('foot_m', (0.15 if kind == 'tree' else 1.0) * float(s['core_m']))
        s.setdefault('around', None)
        s.setdefault('stature', None)
        s.setdefault('ground', None)
        s.setdefault('on', ())
        s.setdefault('range_per_ha', None)
        s['source'] = _source(s.get('source'))
        s['size_m'] = tuple(float(v) for v in s.get('size_m', (1.0, 1.0)))
        s['fade'] = tuple(float(v) for v in s['fade'])
        s['on'] = tuple(s['on'])
        out.append(s)
    eco['species'] = out
    if validate:
        problems = check(eco)
        if problems:
            raise ValueError(f"ecotope {eco['name']!r}: " + '; '.join(problems))
    return eco


def _source(src):
    """A source as (kind, id, options dict, seeds list)."""
    if not isinstance(src, (list, tuple)) or len(src) < 2 or src[0] not in SOURCES:
        raise ValueError(f"source {src!r}: ('seedthree', species, dials, seeds), ('flora', species, opts) or "
                         f"('ph', asset, opts)")
    kind, ident = src[0], str(src[1])
    opts = dict(src[2]) if len(src) > 2 and src[2] else {}
    if kind == 'seedthree':
        seeds = list(src[3]) if len(src) > 3 and src[3] else [1]
    else:
        seeds = list(opts.pop('seeds', [7]))
    return (kind, ident, opts, [int(v) for v in seeds])


def source_dict(src):
    """A source as the spots' file writes it: {'seedthree': species, 'dials': {...}, 'seeds': [...]} or
    {'flora': species, 'options': {...}, 'seeds': [...]} or {'ph': asset, 'options': {...}, 'seeds': [...]}."""
    kind, ident, opts, seeds = src
    return {kind: ident, ('dials' if kind == 'seedthree' else 'options'): _jsonable(opts), 'seeds': list(seeds)}


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def expressions(s):
    """{what: expression} of every mask expression a species carries."""
    out = {'density': s['density']}
    if s.get('stature') is not None:
        out['stature'] = s['stature']
    if s.get('around') and s['around'].get('where') is not None:
        out['around.where'] = s['around']['where']
    return out


def check(eco):
    """Problems of a filled-in ecotope (an empty list: none): unreadable expressions, unknown names, bad numbers."""
    from . import plants as _plants               # the derived names and the constants the planner knows
    problems = []
    seen = set()
    consts = set(P.CONSTANTS) | set(CONSTANTS)
    for k in eco.get('constants') or {}:
        if k not in consts:
            problems.append(f'constant {k!r} is not one of {", ".join(sorted(consts))}')
    names_ = [s.get('name') for s in eco['species']]
    for s in eco['species']:
        nm = s.get('name')
        where = f'species {nm!r}'
        if not nm or nm in seen:
            problems.append(f'{where}: names must be unique and not empty')
        seen.add(nm)
        if 'density' not in s:
            problems.append(f'{where}: no density')
            continue
        for what, src in expressions(s).items():
            try:
                tree = P.parse(src)
            except P.ExprError as e:
                problems.append(f'{where} {what}: {e}')
                continue
            for n in sorted(P.names_in(tree)):
                if n in _plants.DERIVED_NAMES or n in CONSTANTS:
                    continue
                err = P.known_mask(n)
                if err:
                    problems.append(f'{where} {what}: {err}')
        lo, hi = s['size_m']
        if not 0 < lo <= hi:
            problems.append(f'{where}: size_m {s["size_m"]} must be 0 < min <= max')
        c = s['cluster']
        if c['parents_per_ha'] <= 0 or c['mu'] <= 0 or c['sigma_m'] < 0:
            problems.append(f'{where}: cluster {c} needs parents_per_ha > 0, mu > 0, sigma_m >= 0')
        if s['core_m'] < 0 or s['foot_m'] < 0:
            problems.append(f'{where}: core_m and foot_m are radii in metres, not negative')
        for sub in s['on']:
            if sub not in SUBSTRATES:
                problems.append(f'{where}: on {sub!r} is not one of {", ".join(SUBSTRATES)}')
        if not 0 <= s['fade'][0] <= s['fade'][1] <= 1:
            problems.append(f'{where}: fade {s["fade"]} must be 0 <= from <= to <= 1')
        a = s.get('around')
        if a:
            if a.get('species') not in names_:
                problems.append(f'{where}: around.species {a.get("species")!r} is not a species of this ecotope')
            elif next(x for x in eco['species'] if x['name'] == a['species'])['priority'] >= s['priority']:
                problems.append(f'{where}: around.species {a["species"]!r} must be placed before it (a lower '
                                f'priority number)')
        if s['range_per_ha'] is not None and not 0 <= s['range_per_ha'][0] <= s['range_per_ha'][1]:
            problems.append(f'{where}: range_per_ha {s["range_per_ha"]} must be (min, max)')
    return problems


def ecotope_hash(eco):
    """A short hash of everything in an ecotope that decides its spots."""
    blob = json.dumps(_jsonable({k: v for k, v in eco.items() if k not in ('title',)}), sort_keys=True, default=str)
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]


def masks_used(eco):
    """Every mask and derived name the ecotope's expressions read."""
    out = set()
    for s in eco['species']:
        for src in expressions(s).values():
            out |= P.names_in(src)
    return out


def describe(ecotope, recipe=None, place=None):
    """One page on an ecotope: its species, what grows them, where and how big."""
    eco = get(ecotope, recipe, place) if not (isinstance(ecotope, dict) and 'species' in ecotope
                                              and ecotope['species'] and 'priority' in ecotope['species'][0]) else ecotope
    lines = [f"{eco['name']}: {eco['title']}"]
    for s in sorted(eco['species'], key=lambda s: s['priority']):
        kind, ident, opts, seeds = s['source']
        c = s['cluster']
        lines.append(f"  {s['name']} ({s['kind']}, priority {s['priority']}): {kind} {ident} x{len(seeds)}, "
                     f"{s['size_m'][0]:g}-{s['size_m'][1]:g} m, core {s['core_m']:g} m, up to "
                     f"{c['parents_per_ha'] * c['mu']:g} per ha in clusters of {c['mu']:g} over {c['sigma_m']:g} m, "
                     f"within {s['max_radius_m']:g} m"
                     + (f", on cells of {s['max_cell_m']:g} m or finer" if s['max_cell_m'] else ''))
        lines.append(f"      density: {s['density']}")
    return '\n'.join(lines)


__all__ = ['ECOTOPES', 'RECIPE_ECOTOPES', 'PLACE_ECOTOPES', 'KINDS', 'KIND_NAMES', 'CONSTANTS', 'SOURCES',
           'SUBSTRATES', 'get', 'check', 'names', 'describe', 'ecotope_hash', 'masks_used', 'resolve_name',
           'source_dict', 'expressions']
