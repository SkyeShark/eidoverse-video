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
                                                              one individual per seed; dials['eidoGain'] = (r, g, b)
                                                              is the eidoverse side's tone on its albedo, set
                                                              against the photographs (plant_instances: copies of
                                                              its materials; SeedThree never sees it)
                       ('flora', species, opts)               a flora-family species (create_flora) with its options;
                                                              opts['seeds'] lists the individuals (default [7]);
                                                              opts['gain'] = (r, g, b) multiplies the plant's colour
                                                              (plant_instances: a copy of its material, flora's own
                                                              untouched), its tone set against the photographs
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
        core_m       the hard-core radius at full size, metres (flora's footRadius): two plants of one priority stand
                     no closer than 0.75 x the sum of their radii. 0: no hard core (grass blades)
        crown_m      the crown's radius at full size, metres (default core_m): the ground a plant's crown covers seen
                     from above, which the cover rasters (canopy, canopy_expected, shrubs) and the shade read. Taken
                     from the grown individuals' extent (SeedThree's widthMeters over heightMeters, at size_m[1]):
                     a spruce's crown is wider than the spacing its trunks keep, so crowns interlock
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
        max_cell_m   the coarsest level cell it is placed on (None, every kind's default: any level). Densities
                     read the coarse levels whatever level holds a plant, and height_at lies on the rendered
                     triangles of every ring, so an eye view standing on a context ring (the crater's plain,
                     Schynige) gets its undergrowth too; a species may still keep to finer levels
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
    site          0..1: where plants can grow, the palettes' `plants` term on the 20 m slope and aspect: not too
                  steep, moist, open to the sky, not on talus, sand or snow, thinned above the treeline. The base
                  suitability to build a density on (the masks package's `vegetation` is not one: it multiplies by
                  `rock`, which reads nearly 1 on eroded landforms)
    slope_20m     degrees: the slope of the ground's 20 m normal (the surface bake's n20; without a bake, the slope
                  of the height blurred at 20 m), the slope a density reads on every level
    northness_20m, eastness_20m   -1..1: the 20 m normal's aspect, as masks.northness defines it (0 under 3 degrees)
    soil          loose cover the roots hold in, metres: deposit + talus + sand (scaled by `settle` when a surface
                  bake gives it)
    insolation    0..1: the cosine between the 20 m normal and the place's climatological sun
    dist_channel  metres to the nearest stream (cells whose `flow` is at least channel_flow, or, with channel_mask 1,
                  whose `channels` mask is on, on the main and context levels): pow(0.5, dist_channel / 30) halves
                  every 30 m
    dist_water    metres to the nearest standing or running water (`water` over 0.05 m, on the main and context
                  levels), at most 800
    shade         0..1: the shade of the shade-casting plants already placed
    ledge         0..1: the strata relief's ledges (0 until the material's strata_array is there to read)
One level for every density (design 4.2, change 9): every name a density, a stature or an `around.where` reads is
taken on the terrain's coarse levels (the main level inside its tile, the context levels beyond), so stems per hectare
do not step where a hero window begins, whatever the expression names: a hero level resolves steeper slopes, sharper
curvatures and its own drainage, none of which a density may follow. The finest level gives a plant its place, its
height and its normal, and decides the exclusions: every species stays off water deeper than 0.05 m, snow (snowpack
over 0.2 m; without a surface bake the snow mask over 0.5), its own cell steeper than 60 degrees, bare rock (bare over
0.5, on the coarse levels) and talus or sand thicker than roots_m, unless `on` names the substrate.

How the rules are written (in the spirit of Far Cry 5's biome recipes and EcoBrush): forest on north-facing, concave,
moist ground and grass on convex, exposed ground; riparian belts falling off with dist_channel; shrubs at talus
margins; smaller, sparser trees toward the treeline; the avalanche tracks (flow on steep slopes) kept clear. Densities
read terrain terms, with noise only as a small residual: the numpy noise here and the shader's noise in the material
are different noises, so a boundary drawn by noise would stand somewhere else in the ground's layers. Two exceptions,
where the place's own pattern has no terrain term at the scale the rule draws: a treeline's slow wander (hundreds of
metres; the forest layer reads the plant layer's own raster, canopy_expected, so the material's forest edge stands
where the trees' does) and the drifts of a sward on flat ground (the Namib's interdune grass, patchy at 5-30 m).
A stand's density varies within a band, never through a narrow window from nothing to full: a quarter-wide window
over `site` drew hard-edged blobs on the slopes it crossed (11-20, the San Gabriels and Lauterbrunnen).
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
# plants for their distance, and hands what it drops to the material's far cover (PlantSpots.cover, canopy_far).
# Since the still billboards are realised into one mesh per species (plant_instances), a tree costs little past its
# card distance: the trees' cap is 100 000, so a spruce forest stays instanced to 1.5-2 km from an eye-level camera
# (at 50 000 the stand ended 0.85-1.1 km from Schynige Platte, 11-20)
KINDS = {
    'tree': dict(priority=0, max_radius_m=2500.0, max_cell_m=None, lod_m_per_m=0.0015, roots_m=2.0, casts_shade=True,
                 shade=dict(tolerance=0.5, radius=1.0), lod=dict(hero_m=40.0, billboard_m=120.0, near_m=0.0),
                 sink=0.3, align=0.0, max_count=100000, fade=(0.8, 1.0),
                 age=dict(shape=2.2, scale=0.6, stand=0.6), cluster=dict(parents_per_ha=60.0, mu=5.0, sigma_m=7.0)),
    'shrub': dict(priority=1, max_radius_m=400.0, max_cell_m=None, lod_m_per_m=0.003, roots_m=0.8, casts_shade=False,
                  shade=dict(tolerance=0.5, radius=1.0), lod=dict(hero_m=25.0, billboard_m=250.0, near_m=30.0),
                  sink=0.05, align=0.0, max_count=40000, fade=(0.8, 1.0),
                  age=dict(shape=2.0, scale=0.65, stand=0.4), cluster=dict(parents_per_ha=150.0, mu=5.0, sigma_m=3.0)),
    # (crown_m of the undergrowth: a tuft's radius at full size, what its sward covers: flora's blade bunches are
    # 0.26-0.5 m across at their base scale, a daisy's head and leaves a quarter metre)
    # (fade: the undergrowth thins out over the far half of its radius, a sward that ends as a meadow does, not a
    # line: the material carries no grass cover beyond the tufts until the surface bake registers grass_far, and the
    # dunes' sward ended in a line at 160 m, 11-14)
    'grass': dict(priority=2, max_radius_m=100.0, max_cell_m=None, lod_m_per_m=0.006, roots_m=0.4, casts_shade=False,
                  crown_m=0.25,
                  shade=dict(tolerance=0.3, radius=1.0), lod=dict(hero_m=0.0, billboard_m=0.0, near_m=25.0),
                  sink=0.0, align=0.0, max_count=60000, fade=(0.5, 1.0),
                  age=dict(shape=2.5, scale=0.7, stand=0.3), cluster=dict(parents_per_ha=1000.0, mu=8.0, sigma_m=1.2)),
    'forb': dict(priority=2, max_radius_m=80.0, max_cell_m=None, lod_m_per_m=0.006, roots_m=0.3, casts_shade=False,
                 crown_m=0.12,
                 shade=dict(tolerance=0.3, radius=1.0), lod=dict(hero_m=0.0, billboard_m=0.0, near_m=25.0),
                 sink=0.0, align=0.0, max_count=20000, fade=(0.5, 1.0),
                 age=dict(shape=2.5, scale=0.7, stand=0.3), cluster=dict(parents_per_ha=400.0, mu=8.0, sigma_m=1.0)),
    'groundcover': dict(priority=3, max_radius_m=40.0, max_cell_m=None, lod_m_per_m=0.004, roots_m=0.2, crown_m=0.15,
                        casts_shade=False, shade=dict(tolerance=0.7, radius=1.0),
                        lod=dict(hero_m=0.0, billboard_m=0.0, near_m=15.0), sink=0.0, align=0.0, max_count=20000,
                        fade=(0.5, 1.0), age=dict(shape=2.5, scale=0.7, stand=0.3),
                        cluster=dict(parents_per_ha=2000.0, mu=10.0, sigma_m=0.6)),
}

# the plant layer's own constants (an ecotope's `constants` may set them). The sun `insolation` is measured against
# is the place's climatological one (palettes.climate_sun: its latitude_deg, or the palette's sun_azimuth_deg and
# sun_elevation_deg), the one the bake and the material read
CONSTANTS = {
    'channel_flow': 0.8,            # the `flow` a cell needs to count as a stream for dist_channel
    'channel_mask': 1.0,            # 1: the main and context levels' `channels` mask counts too (rills); 0: flow alone
}

# `site`: the palettes' `plants` term (palettes.DERIVED) on the 20 m slope and aspect, the suitability a density
# builds on. The planner reads every name of it on the coarse levels, as it reads every density term
SITE = ('(1 - smoothstep(32, 48, slope_20m)) * (0.35 + 0.65*wetness) * smoothstep(0.3, 0.7, occlusion) '
        '* (1 - snow) * (1 - smoothstep(0.3, 2.0, talus)) * (1 - smoothstep(0.1, 1.0, sand)) '
        '* (1 - 0.8*smoothstep(treeline_m - 120, treeline_m + 120, altitude + 100*northness_20m))')

# ------------------------------------------------------------------------------------------ the sources ---
# SeedThree has no spruce, hemlock, chamise or manzanita. What stands in, and how it is dialled on our side:

# Norway spruce and the subalpine firs and hemlocks: the Douglas fir with short first-level branches (a crown about
# a quarter of its height across, where the species' own is three quarters) that droop a little below the horizontal.
# Its tone: a conifer canopy reflects about half what a meadow does, and the dark spruce slopes of lauterbrunnen_01
# and _15 read far darker than their meadows; the instanced firs rendered 1.25 times as bright as the render's own
# meadow at Schynige (11-18), so their albedo is taken down to about 0.45
# (11-20, the review, design risk 7: with first-level branches of 0.14 the stand-in grew a crown a seventh of its
# height across, the same width from its foot to its top, and two individuals of it stood as a curtain of identical
# thin pencils, the litter showing between them, where lauterbrunnen_01's spruce stands are dark, dense and
# irregular. Now the spruce's own form: a cone, its foot about a third of its height across, full to the ground,
# its first-level branches longer (0.22), more of them (78 a tree) and drooping past the horizontal (106 degrees,
# curving down), denser second-level shoots and larger needle sprays; three individuals)
_NARROW_CONIFER = dict(height=30, paramOverrides=dict(length={1: 0.22, 2: 0.42}, downAngle={1: 106}, curve={1: -18},
                                                      branches={2: 24}),
                       branchDensity=78, leafSize=0.9, leavesPerBranch=16, eidoGain=(0.45, 0.48, 0.45))
_SPRUCE = ('seedthree', 'douglasFir', _NARROW_CONIFER, [11, 23, 37])
# a broadleaf of the valley floors and stream sides (sycamore maple, ash and alder at Lauterbrunnen): the red maple,
# its light crowns toned down toward the dark broadleaf line of lauterbrunnen_01 (four individuals: with two, a belt
# of them read as clones, 11-20)
_MAPLE = ('seedthree', 'redMaple', dict(eidoGain=(0.6, 0.65, 0.6)), [5, 17, 29, 41])
# a broadleaf's card level (SeedThree's LOD2) is bare branches with a few leaf cards beside its full crown, a winter
# tree in summer, and a stand of them read as an orchard on bare grey trunks; the pine's is as thin. Measured with
# match_billboards.py (11-18), the card level covers 0.62-0.63 of the full level's area for the red maple and the
# pine, 0.75-0.77 for the narrow Douglas fir (kept) and 0.97-0.99 for the shrubs: such a tree goes from its full
# level (the nearest within 40 m) straight to its billboard, which is matched to the full level
_BROADLEAF_LOD = dict(hero_m=40.0, billboard_m=40.0)
# blackbrush's stems: SeedThree's dormant slate grey (its own measurement, linear 0.40, 0.42, 0.47) from the species'
# bark texture; the species' bark tint, made for the app's light, leaves the brown texture magenta-grey (red and blue
# over green), which reads lavender under a daylit sky
_BLACKBRUSH_BARK = 0xb4c8e4
# the desert shrubs' tones against tw_04 (11-18, the canyon's approach_walk beside it, its ground half as bright as
# the photograph's, so set against the ground): blackbrush still read lavender (sRGB 92, 87, 97, where the shrub is
# a dark grey-olive in the field), and sagebrush snow-white and cool (L* 67, b* -0.4 against the photograph's silver
# grey-green, L* 68, b* +8.9, beside soil of L* 60 where the render's is 44.5)
_BLACKBRUSH_TONE = (0.85, 0.95, 0.6)
# (11-20, the review: the sage crowns still read almost white-silver and drew the eye across the field. In tw_04 the
# sage is a grey-green a shade darker than its soil, sRGB 153, 152, 139 beside soil of 203, 151, 126; at a tone of
# 0.62 the render's crowns were 1.4 times its soil's brightness, sRGB 131, 134, 123 beside 98, 86, 73, so the sage
# takes about half that, a little greener)
_SAGE = ('seedthree', 'sagebrush', dict(eidoGain=(0.31, 0.33, 0.25)), [3])
# a desert shrubland seen from the eye height closes into one grey-olive band at a few hundred metres (at grazing
# sight the shrubs hide the soil between them), so its plants reach out to where a metre-high shrub spans a pixel,
# the largest kept farthest, and thin out over the last two thirds of that, where the material's scrub takes the
# cover over by the same rule (shrubs_far): at 400 m with the smallest gone from 330 m, the shrubland ended in a
# line, the plain beyond it bare soil to the cliffs (11-20, the canyon's approach walk)
_DESERT_SHRUB_REACH = dict(max_radius_m=1100.0, lod_m_per_m=0.0009, fade=(0.35, 1.0), max_count=90000)
# flora's dry grass (galleta_dry, its straw recolour) keeps the blade atlas's luminance, about 0.2 linear, and renders
# dark olive: the Namib's sward in namib_star_dunes_02 is 2.6, 2.8 and 1.7 times as bright (linear R, G, B) as the
# grass band of the 11-14 interdune render, which mixes in some ground; the gain takes most of that
_DRY = dict(gain=(2.2, 2.1, 1.5))
# the Namib's straw, warmer and a shade paler than the plateaus' dry grass (namib_star_dunes_02's sward, sRGB 171, 142,
# 88 at its median, in the late sun)
_DUNE_STRAW = dict(gain=(2.4, 1.95, 1.25))
# chaparral: creosote bush and blackbrush, the densest evergreen shrubs SeedThree grows, tinted to chamise's dark olive
_CHAPARRAL_A = ('seedthree', 'creosote', dict(leafColorize=0x4d5a2c, leafTintAmount=0.55), [3])
_CHAPARRAL_B = ('seedthree', 'blackbrush', dict(leafColorize=0x56602f, leafTintAmount=0.45, barkTint=_BLACKBRUSH_BARK),
                [7])

# the altitude a treeline reads (11-20: a forest's upper edge drawn by altitude and the 20 m aspect alone was one
# dead-level line round Fuji's cone, a contour, where mount_fuji_04 shows tongues of forest up the slope and bare
# chutes down into it; and Lauterbrunnen's wooded sides end in ragged edges). The edge sits lower (a higher
# effective altitude) in the gullies of the steep slopes, where avalanches, slush flows and debris flows keep the
# chutes open, and on north faces; higher on the ribs and spurs between them, which the flows pass by; and it wanders
# over a few hundred metres with a slow residual (old lava, scoria, fire and clearing), tens of metres at most at the
# scale of a slope. crest (the surface bake's convexity at 8-128 m) reads 0 without a bake, where the 20 m
# curvatures carry the ribs and hollows alone
_TREELINE_ALT = ('(altitude + 100*northness_20m '
                 '+ 160*smoothstep(0.6, 0.86, flow)*smoothstep(14, 26, slope_20m) '
                 '- 120*smoothstep(0.05, 0.5, crest + 0.5*convex_20m) '
                 '+ 60*smoothstep(0.05, 0.5, 0.5*concave_20m - crest) '
                 '+ 180*(fbm(700, 61) - 0.5) + 70*(fbm(160, 62) - 0.5))')
# a volcano's cone has no avalanche regime below its treeline: the wind sets the edge. The forest reaches higher up
# the sheltered gullies and hollows and stops lower on the exposed ribs, the big debris chutes (flow on the steep
# cone) are open, and the edge wanders by hundreds of metres round the cone (eruptions bury the forest on one side and
# spare it on another: on Fuji the 1707 scoria still holds the forest lower on the east)
_TREELINE_VOLCANO = ('(altitude + 90*northness_20m '
                     '+ 200*smoothstep(0.7, 0.9, flow)*smoothstep(16, 26, slope_20m) '
                     '- 160*smoothstep(0.05, 0.5, 0.6*concave_20m - crest) '
                     '+ 140*smoothstep(0.05, 0.5, crest + 0.6*convex_20m) '
                     '+ 420*(fbm(1600, 63) - 0.5) + 120*(fbm(380, 64) - 0.5))')

ECOTOPES = {
    'alpine': dict(
        title='Alpine: spruce forest on the valley sides, maples along the streams of the floor, meadow grass and '
              'flowers near the camera',
        # the floor's broadleaves follow its river, not the rills the channels mask marks on every slope foot (at
        # Lauterbrunnen's floor camera 248 rill cells within 400 m, where the river runs 150-400 m off)
        constants=dict(channel_mask=0.0),
        species=[
            # spruce holds the 12-55 degree sides below the treeline, north faces and hollows first (the palette's
            # forest layer, on terrain terms alone); the floor is cleared pasture; the avalanche tracks down the
            # drainage lines of the steep slopes stay open; toward the treeline the stand thins out and its trees
            # stay low (krummholz, a third of their height at the line)
            # (crown_m: the narrow Douglas fir grown for it is 11.2-11.4 m across at 29-33 m, a crown radius of 5.9 m
            # at 32 m against the 2.3 m its trunks keep apart)
            # (on rock: the spruce holds the valley sides to about 60 degrees by its density's own slope terms, the
            # ledges and talus of the lower walls; the bare-rock rule, which bares slopes from 40 degrees at the main
            # level's cells, stripped the forest from Lauterbrunnen's sides, which lauterbrunnen_15 shows wooded
            # (11-18, ridge_schynige))
            # (11-20, the review: one stand on the steep sides, not blobs. The stand's own terms are the slope, the
            # altitude and the drainage; `site` (its sky view, wetness and slope factors) and a narrow smoothstep cut
            # the high ground into hard-edged dark blobs between lime pasture and grey scree, a camouflage, where
            # lauterbrunnen_15 shows continuous dark forest on the steep sides and meadow on the gentle shoulders,
            # the terraces and the floor. So: forest from 10-20 degrees up to the walls, its density varied within a
            # band by the hollows, the aspect and the drainage, never to nothing but on the avalanche tracks (the
            # flow lines of the steep slopes) and the thick active scree; and a treeline that is no contour: ribs hold
            # the forest higher and the avalanche gullies take it lower, tens to a couple of hundred metres, with a
            # slow irregular residual (TREELINE))
            dict(name='spruce', kind='tree', source=_SPRUCE, size_m=(7.0, 32.0), core_m=2.3, crown_m=5.9, on=('rock',),
                 roots_m=4.0,
                 stature='0.25 + 0.75*smoothstep(treeline_m + 80, treeline_m - 300, ' + _TREELINE_ALT + ')',
                 cluster=dict(parents_per_ha=110.0, mu=6.0, sigma_m=7.0), range_per_ha=(200.0, 660.0),
                 ground='forest', shade=dict(tolerance=0.6, radius=1.0),
                 density='0.066 * clamp(0.8 + 0.15*concave_20m + 0.1*northness_20m - 0.12*convex_20m, 0.5, 1) '
                         '* (1 - 0.85*smoothstep(0.66, 0.88, flow)*smoothstep(20, 30, slope_20m)) '
                         '* (1 - 0.8*smoothstep(1.5, 6.0, talus)*smoothstep(26, 34, slope_20m)) '
                         '* smoothstep(9, 19, slope_20m) * smoothstep(64, 54, slope_20m) '
                         '* smoothstep(treeline_m + 80, treeline_m - 150, ' + _TREELINE_ALT + ')'),
            # broadleaves along the river of the gentle floor, in irregular groups two to four crowns deep, and a
            # single tree in the pastures now and then (lauterbrunnen_01: open meadow, a dark belt of broadleaves
            # along the river and the road at 200-400 m. A belt halving every 30 m made a grove of the whole
            # 300-500 m floor, 11-14; one halving every 7 m a single file of evenly spaced trees, an orchard, 11-20).
            # crown_m: the red maples grown are 12.4-14.6 m across at 15-16 m
            dict(name='maple', kind='tree', source=_MAPLE, size_m=(5.0, 17.0), core_m=3.2, crown_m=7.3, lod=_BROADLEAF_LOD,
                 cluster=dict(parents_per_ha=24.0, mu=5.0, sigma_m=12.0), range_per_ha=(10.0, 120.0),
                 age=dict(shape=1.6, scale=0.6, stand=0.4), shade=dict(tolerance=0.5, radius=1.0),
                 density='smoothstep(0.25, 0.55, site) * smoothstep(treeline_m - 500, treeline_m - 800, altitude) '
                         '* (0.012 * pow(0.5, dist_channel / 22) * smoothstep(16, 7, slope_20m) '
                         '* smoothstep(0.3, 0.6, fbm(90, 41) + 0.25*pow(0.5, dist_channel / 12)) '
                         '+ 0.0001 * smoothstep(22, 8, slope_20m))'),
            # meadow grass: bunches of blades wherever the pasture grows, thinner under the trees
            dict(name='meadow grass', kind='grass', source=('flora', 'grass', dict(height=0.34, color='green',
                                                                                 seeds=[7, 11])),
                 size_m=(0.22, 0.42), core_m=0.0, max_radius_m=45.0, lod_m_per_m=0.0085,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(0.15, 0.45, site) * smoothstep(40, 28, slope_20m) * (1 - 0.6*shade)'),
            # white flowers in drifts through the meadow (lauterbrunnen_01's umbels)
            dict(name='meadow flowers', kind='forb', source=('flora', 'daisy', dict(color='white', height=0.4,
                                                                                    seeds=[5])),
                 size_m=(0.25, 0.45), core_m=0.0, max_radius_m=35.0, lod_m_per_m=0.012,
                 cluster=dict(parents_per_ha=600.0, mu=9.0, sigma_m=1.1), range_per_ha=(500.0, 5400.0),
                 density='0.5 * smoothstep(0.3, 0.6, site) * smoothstep(30, 16, slope_20m) * (1 - 0.8*shade)'),
        ]),
    'desert_sandstone': dict(
        title='Desert sandstone: blackbrush and sagebrush on the benches and plateaus, bunchgrass between them, a few '
              'yuccas; nothing on the cliffs and the washes',
        species=[
            # blackbrush: the plateau's shrub, a plant every few metres on the gentle ground, more in the moist
            # hollows and fewer on the convex rims, none in the washes or on thick fill
            # (crown_m: the blackbrush grown is 2.1-2.2 m across at 1.5 m, a fifth of that below its base)
            dict(name='blackbrush', kind='shrub', **_DESERT_SHRUB_REACH,
                 source=('seedthree', 'blackbrush', dict(barkTint=_BLACKBRUSH_BARK, eidoGain=_BLACKBRUSH_TONE), [7, 19]),
                 size_m=(0.35, 1.0), core_m=0.55, crown_m=0.85, range_per_ha=(250.0, 1200.0),
                 cluster=dict(parents_per_ha=200.0, mu=6.0, sigma_m=4.0),
                 density='0.12 * smoothstep(30, 16, slope_20m) * smoothstep(0.3, 0.6, site + 0.15*concave_20m '
                         '- 0.2*convex_20m + 0.2*(fbm(60, 1) - 0.5)) * smoothstep(0.93, 0.85, flow) '
                         '* (1 - 0.75*smoothstep(1.0, 6.0, deposit))'),
            # big sagebrush and snakeweed: grey shrubs where water gathers, along the wash margins and in the swales
            dict(name='sagebrush', kind='shrub', source=_SAGE, **_DESERT_SHRUB_REACH,
                 size_m=(0.4, 1.3), core_m=0.6, crown_m=0.95, range_per_ha=(40.0, 320.0),
                 cluster=dict(parents_per_ha=80.0, mu=4.0, sigma_m=5.0),
                 density='0.032 * smoothstep(24, 10, slope_20m) * smoothstep(0.45, 0.75, site + 0.35*wetness '
                         '+ 0.2*concave_20m) * smoothstep(0.95, 0.88, flow)'),
            # bunchgrass between the shrubs: tw_04's green tufts on the red soil (its grass, linear and at unit
            # luminance, is 0.83, 1.12, 0.29: flora's 'green')
            dict(name='bunchgrass', kind='grass', source=('flora', 'galleta_dry', dict(color='green', seeds=[7, 13])),
                 size_m=(0.25, 0.6), core_m=0.22, max_radius_m=110.0, lod_m_per_m=0.005,
                 cluster=dict(parents_per_ha=900.0, mu=8.0, sigma_m=1.6), range_per_ha=(1500.0, 7200.0),
                 density='0.72 * smoothstep(28, 14, slope_20m) * smoothstep(0.25, 0.55, site) '
                         '* smoothstep(0.95, 0.88, flow)'),
            dict(name='yucca', kind='shrub', source=('flora', 'yucca', dict(seeds=[7, 11])), priority=1,
                 size_m=(0.6, 1.2), core_m=0.6, max_radius_m=150.0, range_per_ha=(5.0, 60.0),
                 cluster=dict(parents_per_ha=20.0, mu=3.0, sigma_m=6.0),
                 density='0.006 * smoothstep(30, 12, slope_20m) * smoothstep(0.2, 0.5, site) '
                         '* smoothstep(0.1, 0.5, insolation + 0.3*convex_20m)'),
        ]),
    'volcanic': dict(
        title='Volcanic: a continuous conifer forest on the flanks below the treeline, pines on the dry convex ground, '
              'grass tufts on the ash flats',
        species=[
            # the fir and hemlock forest: wherever soil and moisture allow, thinner on the young lava and toward the
            # treeline; the flattest aprons (the pumice flats) stay open
            dict(name='fir', kind='tree', source=_SPRUCE, size_m=(6.0, 30.0), core_m=2.3, crown_m=5.5,
                 stature='0.25 + 0.75*smoothstep(treeline_m + 80, treeline_m - 300, ' + _TREELINE_VOLCANO + ')',
                 cluster=dict(parents_per_ha=100.0, mu=6.0, sigma_m=8.0), range_per_ha=(150.0, 600.0),
                 ground='forest', shade=dict(tolerance=0.6, radius=1.0),
                 # (not on `site`: its own treeline is a contour, altitude and aspect alone, and its wetness factor
                 # set the dry divergent flanks of a cone at the threshold; the forest's edge is the treeline below.
                 # Nor at one steepness: a cone steepens with height, so a forest that stops at one slope stops at
                 # one altitude, the dead-level line round the stratovolcano's cone of 11-20 (its edge stood on
                 # 38-48 degree ground, 1500-2400 m, under a treeline of 2400 m). The soil in the gullies holds it on
                 # steeper ground than the ribs do, and the steepness it holds wanders by some degrees round the cone)
                 density='0.06 * clamp(0.72 + 0.15*clamp(wetness, 0, 1) + 0.12*concave_20m + 0.08*northness_20m '
                         '- 0.12*convex_20m, 0.4, 1) '
                         '* smoothstep(0.5, 6.0, slope_20m) * smoothstep(50, 38, slope_20m + 14*(fbm(900, 65) - 0.5) '
                         '- 5*concave_20m + 4*convex_20m) '
                         '* (1 - 0.8*smoothstep(0.2, 0.6, lava)) * (1 - 0.85*smoothstep(0.3, 2.0, talus + sand)) '
                         '* smoothstep(0.25, 0.55, occlusion) '
                         '* smoothstep(treeline_m + 80, treeline_m - 150, ' + _TREELINE_VOLCANO + ')'),
            # (crown_m: the pine grown is 13.4 m across at 20 m)
            dict(name='pine', kind='tree', source=('seedthree', 'pine', dict(height=20), [9]), size_m=(5.0, 22.0),
                 core_m=2.8, crown_m=7.4, lod=_BROADLEAF_LOD, cluster=dict(parents_per_ha=40.0, mu=4.0, sigma_m=10.0),
                 range_per_ha=(20.0, 160.0), shade=dict(tolerance=0.2, radius=1.2),
                 density='0.016 * (1 - 0.85*smoothstep(0.3, 2.0, talus + sand)) * smoothstep(0.25, 0.55, occlusion) '
                         '* smoothstep(0.25, 0.6, insolation + 0.3*convex_20m) * smoothstep(44, 30, slope_20m) '
                         '* smoothstep(treeline_m + 150, treeline_m - 100, ' + _TREELINE_VOLCANO + ')'),
            dict(name='ash grass', kind='grass', source=('flora', 'galleta_dry', dict(_DRY, seeds=[7, 13])),
                 size_m=(0.2, 0.5), core_m=0.2, max_radius_m=90.0,
                 cluster=dict(parents_per_ha=700.0, mu=8.0, sigma_m=1.5), range_per_ha=(800.0, 5600.0),
                 density='0.5 * smoothstep(0.1, 0.4, site) * smoothstep(26, 12, slope_20m) * (1 - 0.7*shade)'),
        ]),
    'dunes': dict(
        title='Dunes: dry grass tufts on the interdune floor and the stable sand sheet, a few shrubs at the dunes\' feet',
        species=[
            # dune grass (the Namib's bushman grass, Great Sand Dunes' ricegrass): tufts on thin sand and gravel, in
            # drifts with bare ground between; none on the active dunes
            # (to 300 m, where a tuft spans a pixel or two from the eye height, the far tufts dropped first by their
            # size for their distance: the sward thins into the floor rather than ending)
            # (11-20, the review: an even, dense lawn of identical yellow-green tufts from edge to edge, at the 60,000
            # cap, where namib_star_dunes_02 shows golden straw in drifts over a bare brown gravel floor. So a third of
            # the density, the drifts a third of the floor with soft edges (the residual's window narrower than its
            # spread), four individuals, and the straw warmer: the photograph's sward is hue 39 at R/G 1.20, the
            # render's was hue 47 at R/G 1.10)
            dict(name='dune grass', kind='grass', source=('flora', 'galleta_dry', dict(_DUNE_STRAW, seeds=[7, 13, 19, 29])),
                 size_m=(0.2, 0.65), core_m=0.24, max_radius_m=300.0, lod_m_per_m=0.002, on=('sand',),
                 cluster=dict(parents_per_ha=700.0, mu=8.0, sigma_m=2.4), range_per_ha=(1200.0, 5600.0),
                 age=dict(shape=1.8, scale=0.6, stand=0.5),
                 density='0.5 * smoothstep(2.5, 0.3, sand) * smoothstep(9, 3, slope_20m) '
                         '* smoothstep(0.44, 0.64, 0.35*site + 0.65*fbm(24, 2))'),
            dict(name='dune shrub', kind='shrub', source=('seedthree', 'creosote', dict(), [3]), on=('sand',),
                 size_m=(0.5, 1.6), core_m=0.9, crown_m=1.2, cluster=dict(parents_per_ha=12.0, mu=3.0, sigma_m=8.0),
                 range_per_ha=(2.0, 36.0),
                 density='0.0036 * smoothstep(4.0, 0.5, sand) * smoothstep(10, 3, slope_20m) '
                         '* smoothstep(0.2, 0.6, concave_20m + 0.5*wetness)'),
            # camelthorn (Acacia erioloba): a few wide, flat-crowned trees on the interdune floor where the water
            # gathers, the pans and the dry channels (namib_star_dunes_02: one by the dune's foot). SeedThree grows no
            # acacia: its white oak, low, with a hemispherical crown of near-level limbs and small leaves
            dict(name='camelthorn', kind='tree', lod=_BROADLEAF_LOD, on=('sand',), roots_m=3.0,
                 source=('seedthree', 'whiteOak', dict(height=7, crownShape=2, branchAngle=82, leafSize=0.35,
                                                        eidoGain=(0.62, 0.66, 0.55)), [1737]),
                 size_m=(3.0, 8.0), core_m=4.0, crown_m=5.0, cluster=dict(parents_per_ha=1.5, mu=3.0, sigma_m=30.0),
                 range_per_ha=(0.5, 4.5), max_radius_m=1500.0,
                 density='0.0004 * smoothstep(2.5, 0.3, sand) * smoothstep(8, 3, slope_20m) '
                         '* smoothstep(0.15, 0.55, wetness + 0.4*concave_20m)'),
        ]),
    'badlands': dict(
        title='Badlands: mixed-grass prairie on the tables and the plain, sagebrush in the draws; the clay walls bare',
        species=[
            dict(name='prairie grass', kind='grass', source=('flora', 'galleta_dry', dict(_DRY, seeds=[7, 13])),
                 size_m=(0.25, 0.6), core_m=0.2, max_radius_m=110.0, lod_m_per_m=0.005,
                 cluster=dict(parents_per_ha=2500.0, mu=9.0, sigma_m=1.4), range_per_ha=(5000.0, 22500.0),
                 density='2.2 * smoothstep(0.2, 0.5, site) * smoothstep(16, 7, slope_20m) '
                         '* (1 - smoothstep(0.15, 0.45, convex_20m))'),
            dict(name='sagebrush', kind='shrub', source=_SAGE,
                 size_m=(0.4, 1.2), core_m=0.6, crown_m=0.9, cluster=dict(parents_per_ha=50.0, mu=4.0, sigma_m=5.0),
                 range_per_ha=(20.0, 200.0),
                 density='0.02 * smoothstep(0.4, 0.7, site + 0.3*wetness + 0.2*concave_20m) '
                         '* smoothstep(16, 6, slope_20m)'),
        ]),
    'karst': dict(
        title='Karst: broadleaf forest on every flank the towers let it hold, trees along the river and the field '
              'edges of the plain',
        # the river's trees follow the river, not every rill the channels mask marks across the paddies
        constants=dict(channel_mask=0.0),
        species=[
            # the towers' forest: denser where soil holds (the gentler, concave ground) on the towers' feet and lower
            # flanks; the steep flanks' clinging scrub is the material's forest (the tower_karst look draws it by
            # the slope), not instanced trees: a stand of sweetgums standing out from a 50-80 degree flank read as a
            # hard-edged block of pale cut-outs (11-20, plain_fields). Rounded crowns (SeedThree's sweetgum is a
            # cone, and its stands read as conifers, odd for Guilin's evergreen broadleaf scrub)
            # (crown_m: a sweetgum is about two thirds as wide as it is tall)
            dict(name='broadleaf', kind='tree', source=('seedthree', 'sweetgum', dict(height=14, crownShape=1), [5, 17]),
                 lod=_BROADLEAF_LOD,
                 size_m=(4.0, 15.0), core_m=2.6, crown_m=5.0, cluster=dict(parents_per_ha=110.0, mu=6.0, sigma_m=6.0),
                 range_per_ha=(150.0, 660.0), ground='forest', shade=dict(tolerance=0.6, radius=1.0),
                 density='0.066 * smoothstep(9, 17, slope_20m) * smoothstep(46, 36, slope_20m + 6*convex_20m '
                         '- 6*concave_20m + 8*(fbm(120, 44) - 0.5))'),
            # trees along the river banks in irregular groves, not in the paddies: a single row along every channel
            # of the plain stood in the flooded fields (11-20, riverbank; guilin_karst_01: the town and groves on
            # the river bank)
            dict(name='riverside trees', kind='tree', source=_MAPLE, size_m=(5.0, 16.0), core_m=3.2, crown_m=6.9,
                 lod=_BROADLEAF_LOD, age=dict(shape=1.6, scale=0.6, stand=0.4),
                 cluster=dict(parents_per_ha=30.0, mu=5.0, sigma_m=12.0), range_per_ha=(15.0, 150.0),
                 density='0.014 * pow(0.5, dist_channel / 30) * smoothstep(8, 3, slope_20m) '
                         '* smoothstep(0.35, 0.6, fbm(80, 43) + 0.2*pow(0.5, dist_channel / 15))'),
        ]),
    'chalk_coast': dict(
        title='Chalk coast: downland turf to the cliff edge, flowers in it',
        species=[
            dict(name='downland grass', kind='grass', source=('flora', 'grass', dict(height=0.22, color='green',
                                                                                   seeds=[7, 11])),
                 size_m=(0.14, 0.28), core_m=0.0, max_radius_m=40.0, lod_m_per_m=0.006,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(0.15, 0.45, site) * smoothstep(38, 26, slope_20m)'),
            dict(name='downland flowers', kind='forb', source=('flora', 'daisy', dict(color='white', height=0.25,
                                                                                      seeds=[5])),
                 size_m=(0.15, 0.3), core_m=0.0, max_radius_m=30.0, lod_m_per_m=0.008,
                 cluster=dict(parents_per_ha=600.0, mu=9.0, sigma_m=1.1), range_per_ha=(500.0, 5400.0),
                 density='0.5 * smoothstep(0.3, 0.6, site) * smoothstep(28, 14, slope_20m)'),
        ]),
    'farmland': dict(
        title='Farmland: grass on the verges and pastures near the camera (the crops are the material\'s fields)',
        species=[
            # (on the steep ground the plough leaves, not on the fields: a numpy cell noise does not lay out the
            # material's fields, whose noise is the shader's, and the sward stood on a ploughed field, 11-18)
            dict(name='field grass', kind='grass', source=('flora', 'grass', dict(height=0.3, color='green',
                                                                                seeds=[7, 11])),
                 size_m=(0.2, 0.38), core_m=0.0, max_radius_m=40.0, lod_m_per_m=0.008,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(0.15, 0.45, site) * smoothstep(18, 26, slope_20m)'),
        ]),
    'meadow': dict(
        title='Meadow: grass and flowers',
        species=[
            dict(name='meadow grass', kind='grass', source=('flora', 'grass', dict(height=0.4, color='green',
                                                                                 seeds=[7, 11])),
                 size_m=(0.25, 0.5), core_m=0.0, max_radius_m=40.0, lod_m_per_m=0.01,
                 cluster=dict(parents_per_ha=22000.0, mu=8.0, sigma_m=0.6), range_per_ha=(40000.0, 176000.0),
                 density='17 * smoothstep(30, 20, slope_20m)'),
            dict(name='meadow flowers', kind='forb', source=('flora', 'daisy', dict(seeds=[5])),
                 size_m=(0.25, 0.45), core_m=0.0, max_radius_m=30.0, lod_m_per_m=0.012,
                 cluster=dict(parents_per_ha=600.0, mu=9.0, sigma_m=1.1), range_per_ha=(500.0, 5400.0),
                 density='0.5 * smoothstep(26, 14, slope_20m)'),
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
            # chaparral covers every slope it can hold as one stand, from the canyon floors to about 50 degrees
            # (san_gabriel_mountains_02-04: continuous dark brush, denser and darker on the north faces and down the
            # draws, thinner on the ridgelines, where the pale decomposed granite shows). Its density reads the
            # slope, the aspect and the landform's convexity alone, and its variations are a band of densities, never
            # a gate to nothing: on `site` (its sky-view and wetness factors, and its fall from 32-48 degrees) and a
            # quarter-wide smoothstep the range's steep, dissected slopes broke into hard-edged dark blobs between
            # cream grass and pale granite, a camouflage (11-20: the largest region 0.53 of the frame against the
            # photograph's 0.34). It roots in the fractured granite and the colluvium of the steep slopes (on rock,
            # roots through 3 m of debris): the bare-rock rule (34-46 degrees of the cells' own slope without cover)
            # and the talus a slope carries took it off 30 % and 13 % of the range's main level in specks
            'chaparral': dict(kind='shrub', source=_CHAPARRAL_A, size_m=(0.9, 2.6), core_m=1.0, crown_m=1.9,
                              max_radius_m=450.0, on=('rock',), roots_m=3.0,
                              cluster=dict(parents_per_ha=420.0, mu=6.0, sigma_m=4.0), range_per_ha=(500.0, 2520.0),
                              density='0.25 * clamp(0.62 + 0.22*northness_20m + 0.15*concave_20m '
                                      '+ 0.15*clamp(wetness, 0, 1) - 0.45*smoothstep(0.1, 0.6, crest + 0.6*convex_20m),'
                                      ' 0.12, 1) * smoothstep(3, 8, slope_20m) * smoothstep(58, 46, slope_20m)'),
            # the low, open brush of the sunny convex ground (chamise and buckwheat), under and between the tall
            # chaparral's gaps, on the same slopes
            'low chaparral': dict(kind='shrub', source=_CHAPARRAL_B, size_m=(0.5, 1.3), core_m=0.6, crown_m=1.1,
                                  max_radius_m=350.0, on=('rock',), roots_m=3.0, cluster=dict(parents_per_ha=250.0, mu=5.0, sigma_m=3.0),
                                  range_per_ha=(200.0, 1250.0),
                                  density='0.1 * (0.3 + 0.7*smoothstep(0.15, 0.65, insolation + 0.3*convex_20m)) '
                                          '* smoothstep(3, 8, slope_20m) * smoothstep(56, 44, slope_20m)'),
            # (crown_m: the white oak grown is 12.3 m across at 10.4 m; the sycamore 29 m across at 23 m)
            'oak': dict(kind='tree', source=('seedthree', 'whiteOak', dict(height=9), [1737]), size_m=(4.0, 10.0),
                        lod=_BROADLEAF_LOD,
                        core_m=3.0, crown_m=5.9, cluster=dict(parents_per_ha=30.0, mu=4.0, sigma_m=10.0),
                        range_per_ha=(10.0, 120.0), max_radius_m=1500.0,
                        density='smoothstep(0.25, 0.5, site + 0.3*smoothstep(8, 22, slope_20m)) '
                                '* smoothstep(44, 30, slope_20m) '
                                '* (0.012 * pow(0.5, dist_channel / 45) + 0.003 * smoothstep(0.2, 0.7, northness_20m))'),
            'sycamore': dict(kind='tree', source=('seedthree', 'americanSycamore', dict(height=16), [5]),
                             lod=_BROADLEAF_LOD,
                             size_m=(7.0, 18.0), core_m=3.6, crown_m=11.7,
                             cluster=dict(parents_per_ha=20.0, mu=4.0, sigma_m=9.0),
                             range_per_ha=(8.0, 80.0), max_radius_m=1500.0,
                             density='0.008 * pow(0.5, dist_channel / 20) * smoothstep(14, 6, slope_20m)'),
            'dry grass': dict(kind='grass', source=('flora', 'galleta_dry', dict(_DRY, seeds=[7, 13])),
                              size_m=(0.25, 0.6), core_m=0.2, max_radius_m=100.0, lod_m_per_m=0.005,
                              cluster=dict(parents_per_ha=1200.0, mu=8.0, sigma_m=1.5), range_per_ha=(1500.0, 9600.0),
                              density='0.9 * smoothstep(0.15, 0.4, site) * smoothstep(30, 14, slope_20m) '
                                      '* (1 - 0.6*shade)'),
            'yucca': dict(kind='shrub', source=('flora', 'yucca', dict(seeds=[7, 11])), size_m=(0.6, 1.3),
                          core_m=0.6, max_radius_m=150.0, cluster=dict(parents_per_ha=30.0, mu=3.0, sigma_m=6.0),
                          range_per_ha=(5.0, 90.0),
                          density='0.009 * smoothstep(0.3, 0.7, insolation + 0.3*convex_20m) '
                                  '* smoothstep(42, 20, slope_20m)'),
        }),
    # the impact crater's plain is a dry grassland, not the plateau's blackbrush shrubland (meteor_crater_02: red soil
    # with straw tufts a few metres apart and a low shrub here and there; with the desert's own species, 11-18, a
    # thousand shrubs a hectare and green grass covered it): straw grass, sparse low shrubs, no sagebrush or yucca
    'impact_crater': dict(
        title='Crater plain: a dry grassland of scattered straw tufts and a few low shrubs on red soil',
        species={
            'sagebrush': None, 'yucca': None,
            'blackbrush': dict(size_m=(0.2, 0.6), cluster=dict(parents_per_ha=30.0, mu=4.0, sigma_m=6.0),
                               range_per_ha=(20.0, 120.0),
                               density='0.012 * smoothstep(30, 16, slope_20m) * smoothstep(0.3, 0.6, site '
                                       '+ 0.15*concave_20m - 0.2*convex_20m + 0.2*(fbm(60, 1) - 0.5)) '
                                       '* smoothstep(0.93, 0.85, flow) * (1 - 0.75*smoothstep(1.0, 6.0, deposit))'),
            'bunchgrass': dict(source=('flora', 'galleta_dry', dict(_DRY, seeds=[7, 13])), size_m=(0.2, 0.5),
                               cluster=dict(parents_per_ha=300.0, mu=8.0, sigma_m=1.6), range_per_ha=(600.0, 2400.0),
                               density='0.2 * smoothstep(28, 14, slope_20m) * smoothstep(0.2, 0.5, site) '
                                       '* smoothstep(0.95, 0.88, flow)'),
        }),
    # Monument Valley's floor is a sand sheet with low shrubs scattered over it (mv_04): the plateau's species keep
    # off sand thicker than their roots, which left the floor bare beyond the camera's feet (11-18). On the deep sand
    # grow sand sage (the sagebrush), narrowleaf yucca here and there, and ricegrass; blackbrush keeps to the
    # shallow soils. The yuccas at the desert's own density stood black among them, so they are a third as many
    'mesas_buttes': dict(
        title='Sand floor: sand sage and straw tufts scattered over the sand, a few yuccas',
        species={
            'blackbrush': None,
            'sagebrush': dict(size_m=(0.3, 0.9), on=('sand',), cluster=dict(parents_per_ha=40.0, mu=4.0,
                                                                            sigma_m=6.0),
                              range_per_ha=(30.0, 160.0),
                              density='0.016 * smoothstep(24, 10, slope_20m) * smoothstep(0.93, 0.85, flow) '
                                      '* (0.4 + 0.6*smoothstep(-0.3, 0.3, concave_20m - convex_20m '
                                      '+ 0.3*(fbm(80, 3) - 0.5)))'),
            'bunchgrass': dict(source=('flora', 'galleta_dry', dict(_DRY, seeds=[7, 13])), on=('sand',),
                               size_m=(0.2, 0.5), cluster=dict(parents_per_ha=200.0, mu=8.0, sigma_m=1.6),
                               range_per_ha=(400.0, 1600.0),
                               density='0.12 * smoothstep(20, 8, slope_20m) * smoothstep(0.93, 0.85, flow)'),
            'yucca': dict(on=('sand',), range_per_ha=(2.0, 20.0),
                          density='0.002 * smoothstep(30, 12, slope_20m) * smoothstep(0.2, 0.5, site)'),
        }),
    # a cinder-cone field on a dry plateau (SP Crater): juniper and pinyon scattered on the plain (the pine, grown
    # low), none on the cones' loose cinders, straw grass between them. At 40 full-size pines a hectare the plain
    # read as a pine wood from the eye (11-18), where sp_crater's plain is open grassland with a tree here and there
    # (crown_m: the pine grown is 13.4 m across at 20 m, so 3.3 m in radius at 9 m)
    'cinder_cones': dict(
        title='Cinder-cone field: scattered junipers and pinyons and straw grass on the plain, bare cinders on the '
              'cones',
        species={
            'fir': None,
            'pine': dict(size_m=(3.0, 9.0), core_m=1.6, crown_m=3.3,
                         density='0.0012 * smoothstep(0.35, 0.75, site + 0.25*wetness - 0.2*convex_20m) '
                                 '* smoothstep(14, 7, slope_20m)',
                         cluster=dict(parents_per_ha=6.0, mu=2.0, sigma_m=18.0), range_per_ha=(1.0, 12.0)),
            # (11-20, the review: the straw tufts stopped along a line about 100-150 m out and the plain beyond read
            # bare. They reach on to 260 m now, the largest kept farthest, thinning over the outer two thirds, and the
            # plain's shrubs (rabbitbrush and snakeweed, the grey-green sage grown for it) stand on to a kilometre,
            # where a shrub spans a pixel: the steppe runs on to the cones)
            'ash grass': dict(density='0.7 * smoothstep(0.1, 0.36, site) * smoothstep(22, 12, slope_20m)',
                              max_radius_m=260.0, lod_m_per_m=0.0019, fade=(0.3, 1.0)),
            'rabbitbrush': dict(kind='shrub', source=_SAGE, size_m=(0.3, 0.9), core_m=0.5, crown_m=0.7,
                                max_radius_m=1000.0, lod_m_per_m=0.0008, fade=(0.35, 1.0), max_count=60000,
                                cluster=dict(parents_per_ha=40.0, mu=4.0, sigma_m=6.0), range_per_ha=(25.0, 160.0),
                                density='0.016 * smoothstep(0.15, 0.4, site) * smoothstep(16, 8, slope_20m) '
                                        '* (0.4 + 0.6*smoothstep(0.3, 0.7, fbm(70, 47)))'),
        }),
    # Crater Lake's rim stands 100-300 m under the treeline: whitebark pine and mountain hemlock parkland, and the
    # collapse walls below it are talus and cliff with a tree here and there (crater_lake_01: two trees at the
    # overlook). With the flanks' full stand the rim camera saw 28 firs and 55 pines from 25 to 100 m in front of the
    # lake (11-18): here the stands open from 450 m under the treeline, and thin out on the walls from 24-26 degrees.
    # Inside the caldera the ground is young: Wizard Island's cinder cone and its blocky lava apron, and the rockfall
    # of the walls (crater_lake_02: the dark flows bare but for a few trees and clumps, the cone's cinders showing
    # between scattered trees). The lake marks the inside of the caldera for a rule (the outer flanks lie kilometres
    # from it): within 250-650 m of it the stands are an open woodland, a fifth of the flanks' (11-20: the island's
    # apron, wet by the wetness index on its flat ground at the shore, stood as dense conifer forest to the water)
    'caldera': dict(
        title='Caldera: conifer forest on the outer flanks, parkland toward the rim, a tree here and there on the '
              'walls, open woodland on the young island',
        species={
            'fir': dict(density='0.06 * clamp(0.72 + 0.15*clamp(wetness, 0, 1) + 0.12*concave_20m '
                                '+ 0.08*northness_20m - 0.12*convex_20m, 0.4, 1) '
                                '* smoothstep(0.5, 6.0, slope_20m) * smoothstep(38, 26, slope_20m) '
                                '* (1 - 0.8*smoothstep(0.2, 0.6, lava)) * (1 - 0.85*smoothstep(0.3, 2.0, talus + sand)) '
                                '* smoothstep(0.25, 0.55, occlusion) * (0.18 + 0.82*smoothstep(250, 650, dist_water)) '
                                '* smoothstep(treeline_m + 80, treeline_m - 450, ' + _TREELINE_VOLCANO + ')'),
            'pine': dict(density='0.016 * (1 - 0.85*smoothstep(0.3, 2.0, talus + sand)) '
                                 '* smoothstep(0.25, 0.55, occlusion) * (0.35 + 0.65*smoothstep(250, 650, dist_water)) '
                                 '* smoothstep(0.25, 0.6, insolation + 0.3*convex_20m) * smoothstep(36, 24, slope_20m) '
                                 '* smoothstep(treeline_m + 150, treeline_m - 450, ' + _TREELINE_VOLCANO + ')'),
        }),
}

# a real place's ecotope (the real_place recipe's DEM): the palette's, or a recipe's, with the same kind of merge
PLACE_ECOTOPES = {
    'san_gabriel_mountains': dict(base='fluvial_range'),
    'sp_crater': dict(base='cinder_cones'),
    'meteor_crater': dict(base='impact_crater'),
    'crater_lake': dict(base='caldera'),
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
        s.setdefault('crown_m', s['core_m'])
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
        if s['core_m'] < 0 or s['foot_m'] < 0 or s['crown_m'] < 0:
            problems.append(f'{where}: core_m, crown_m and foot_m are radii in metres, not negative')
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


__all__ = ['ECOTOPES', 'RECIPE_ECOTOPES', 'PLACE_ECOTOPES', 'KINDS', 'KIND_NAMES', 'CONSTANTS', 'SITE', 'SOURCES',
           'SUBSTRATES', 'get', 'check', 'names', 'describe', 'ecotope_hash', 'masks_used', 'resolve_name',
           'source_dict', 'expressions']
