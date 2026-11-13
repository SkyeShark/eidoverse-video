"""tower_karst: Guilin's karst. Fenglin (steep towers and peak clusters on a flat river plain, Yangshuo) or fengcong
(peaks packed on a raised common base, closed star-shaped dolines between them). Design 4.10 and row `tower_karst` of
section 5; the solver is solvers/karst.py.

    make_terrain('tower_karst', seed=7)                                   # Yangshuo-like fenglin, 8 km
    make_terrain('tower_karst', params={'kind': 'fengcong'})              # cone karst: no plain, no river
    make_terrain('tower_karst', params={'spacing_m': 260, 'median_height_m': 180, 'cluster_cover': 0.6})

Stages, in order:
  karst      every level: the alluvial plain and its river (a flat water surface with cut banks and point bars,
             written to `water` so the lake builder draws it), the towers (each a ledged wall from its footprint's
             edge meeting its summit: a spire's needle, a peak's knobbed cone, a block's cliffed cap with knobs; deep
             inside a cluster the broad concave fengcong cone, its flanks meeting its neighbours' at cols), inside the
             clusters each tower's massif body (a walled skirt reaching toward its neighbours, so a cluster stands as
             one massif with its peaks on it, cols between them and cockpits in the gaps), the
             raised ground between a cluster's inner towers, the talus cones at their feet, the cockpits filled flat
             with soil (and slots under 30 m to their outlet); vertical fluting on levels with cells of 2 m or less.
             Rebuilt per level from world functions, so the walls are sharp at every scale (`levels='all'`, not the
             design's 'resolves:200': a wall upsampled from a coarser level would be soft at 0.5 m).
  threshold  at the op's Sc (87.5 degrees), a few iterations: trims texel spikes only (package 3's hillslope.py).

Why no 'creep' and no 75-degree threshold any more (the design's "threshold pass at limestone Sc 75 degrees and light
creep"): the review measured the towers' walls at a median of 55 degrees, 8 % over 70, beside photographs with 70-90
degree walls. The creep stage is a Gaussian of sigma sqrt(2 kappa t) = 6.3 m at every level (13 cells on a 0.49 m hero
level): it rounded every summit into a dome and flared every foot; the threshold at 75 degrees shaved the walls back.
The walls' angles, their ledges and their brows are now the op's own (the wall table, the brow's smooth minimum).

The palette (defaults['palette'], karst_palette()): the surfacing package's karst palette with its bare limestone on
the walls' sheerest bands only (79-87 degrees), so the steep towers wear its forest as Guilin's do.

The cockpits and poljes between the towers are closed depressions by design (karst drains underground): the level
runner's end stage must neither flood nor fill them, so the recipe sets defaults['lakes'] = False (run.py: "False
skips them"); the karst op already gives each its flat soil floor, and writes the river's water itself.
"""
from ..core.recipe import Knob, Recipe, Stage
from ..solvers.karst import DEFAULTS, KIND_PRESETS

# the knobs that are also karst parameters; their defaults are fenglin's, and kind='fengcong' takes its own preset
# for every one of them left at that default
_KIND_DEPENDENT = ('spacing_m', 'median_height_m', 'cluster_cover', 'plinth_m', 'base_m', 'river')


def _apply_knobs(p):
    """Write the knob values into the karst stage's parameters. With kind other than 'fenglin', a knob left at its
    (fenglin) default is not written, so the kind's preset in solvers/karst.py decides it."""
    st = p.stage('karst')
    st['kind'] = p['kind']
    knobs = p.recipe.knobs if p.recipe is not None else {}
    for k in ('spacing_m', 'median_height_m', 'wall_deg', 'cluster_cover', 'plinth_m', 'base_m', 'river',
              'river_width_m'):
        if k not in p:
            continue
        v = p[k]
        if (p['kind'] != 'fenglin' and k in _KIND_DEPENDENT and k in KIND_PRESETS[p['kind']]
                and k in knobs and v == knobs[k].default):
            continue
        st[k] = bool(v) if k == 'river' else float(v)


TOWER_KARST = Recipe(
    'tower_karst', 'Tower karst: fenglin towers on a river plain (Guilin), or fengcong cones over dolines',
    references=['guilin_karst'],
    defaults={'size': 8000.0, 'resolution': 1024, 'context': 4, 'hero_cell': 0.5, 'palette': 'karst',
              'base_elevation_m': 110.0, 'lakes': False},
    knobs={
        'kind': Knob('fenglin', 'choice', ('fenglin', 'fengcong'),
                     'fenglin: peak clusters and steep isolated towers on a flat alluvial plain with a river '
                     '(Yangshuo); fengcong: peaks packed on a raised common base with closed dolines between '
                     '(the Li River gorge, Guizhou)', apply=_apply_knobs),
        'spacing_m': Knob(DEFAULTS['spacing_m'], 'm', (60.0, 1000.0),
                          'Poisson-disc spacing of the towers inside the clusters (fengcong: 210)'),
        'median_height_m': Knob(DEFAULTS['median_height_m'], 'm', (15.0, 600.0),
                                'median summit height above the plain (fengcong: 190, above the plain under its base)'),
        'wall_deg': Knob(DEFAULTS['wall_deg'], 'deg', (70.0, 89.0),
                         "the towers' cliffed walls: their median angle (each tower +-4 degrees, ledges between)"),
        'cluster_cover': Knob(DEFAULTS['cluster_cover'], '', (0.0, 1.0),
                              'the share of the ground inside peak clusters; the rest is plain (fengcong: 0.97)'),
        'plinth_m': Knob(DEFAULTS['plinth_m'], 'm', (0.0, 300.0),
                         "fengcong's common base under the clusters: the cockpit floors' height above the plain "
                         "(fengcong: 60)"),
        'base_m': Knob(DEFAULTS['base_m'], 'm', (0.0, 200.0),
                       "fenglin: the raised ground between a cluster's inner towers (none at its edge)"),
        'river': Knob(DEFAULTS['river'], 'bool', None, 'a river meandering across the plain (fengcong: none)'),
        'river_width_m': Knob(DEFAULTS['river_width_m'], 'm', (5.0, 600.0), "the river's mean width"),
    },
    stages=[
        Stage('karst', {}, levels='all'),
        Stage('threshold', {'iterations': 24}, levels='all'),
    ],
    doc='Towers from blue-noise centres in clusters along the joint strike and scattered on the plain: spires, peaks '
        'and cliffed blocks, each a ledged wall of 76-88 degrees from its foot meeting a pointed or knobby summit; '
        'a river at plain level with cut banks and point bars; judged against guilin_karst (Copernicus 30 m, through '
        'the radar chain: its spacing, heights and plain, not its walls) and the Li River photographs.')

def karst_palette():
    """The towers' material: the surfacing package's karst palette (its scans, colours, forest canopy and fields),
    with two layers placed from this terrain's own fields:
      - bare limestone on the towers' sheer walls and on the benches' risers, from 76 to 86 degrees, the threshold
        broken by noise at 40 m and 12 m, bared a little lower on convex ribs and held under forest in gullies,
        without the convex bonus that bared the pointed summits (Guilin's towers are forest on every flank and ledge
        the rock lets it hold, the grey showing on the vertical faces; at the palette's 68-80 degrees these towers'
        58-70 degree cones went bare grey);
      - river gravel and sand on the Li's banks and point bars: the ground under the plain's level by 0.7 m and more
        (the karst op cuts the channel 2.2 m under the plain, the bars standing 0.8 m over the water) and the bed
        under shallow water, broken at 25 m; the palette's red soil fields had reached the water's edge;
    and the plain's fields: the paddies a patchwork of whole fields (young and ripening rice), and one field in
    eleven ploughed brown laterite, never on the damp ground by the river (the palette's one in five, raw red, read
    as hard-edged red blotches on a lawn)."""
    from ..build import palettes as P
    pal = P.get('karst')
    cliff = getattr(P, '_cliff', None)
    rock_w = (cliff(76, 86, extra=' - 6*convex_20m', ribs=' * 0') if cliff is not None else
              'smoothstep(76, 86, slope + 6*(fbm(40, 2) - 0.5) + 2.5*(fbm(12, 0) - 0.5))')
    gravel = dict(name='river gravel', set='Gravel041', tile_m=2.0, colour='#8b8170', roughness=1.1,
                  patches=[dict(scale_m=14.0, colour='#a39a86', amount=0.45)],
                  weight='max(smoothstep(0.05, 0.3, water), smoothstep(-0.6, -1.3, height + 0.5*(fbm(25, 2) - 0.5)) '
                         '* smoothstep(18, 9, slope))')
    # the plain's paddies as a patchwork of whole fields (70 m Voronoi cells with straight boundaries): a third young
    # rice, a fifth ripening, over the palette's noise patches (one green with blotches read as a lawn from the air)
    fields_ = [dict(scale_m=None, colour='#6d8f3a', amount=0.55, where='smoothstep(0.66, 0.665, cells(70, 5))'),
               dict(scale_m=None, colour='#8c8f48', amount=0.5, where='smoothstep(0.2, 0.195, cells(70, 5))')]
    # ploughed fields as one field in eleven (90 m cells), brown laterite under the crop stubble rather than raw red
    # earth, never on damp ground by the river or in a cockpit's wettest hollow (one field in five, saturated red, read
    # from the plain as hard-edged red blotches on a lawn)
    soil_w = 'smoothstep(0.91, 0.915, cells(90, 3)) * smoothstep(5, 2, slope) * smoothstep(0.75, 0.55, wetness)'
    layers = []
    for L in pal['layers']:
        if L['name'] == 'limestone':
            # the fresh faces of the collapse scarps (concave) a warm orange-grey, the weathered walls grey
            L = dict(L, weight=rock_w,
                     patches=[dict(scale_m=None, colour='#9d8370', amount=0.6,
                                   where='smoothstep(0.3, 0.75, concave_20m + 0.25*(fbm(25, 7) - 0.5))')]
                     + list(L.get('patches') or []))
        if L['name'] == 'paddies':
            L = dict(L, patches=fields_ + list(L.get('patches') or []))
        if L['name'] == 'red soil':
            L = dict(L, colour='#7b5c46', weight=soil_w)
        if L['name'] == 'forest':
            layers.append(gravel)
            # the north-facing flanks' forest darker and denser, the sunny south faces a lighter, yellower green; the
            # crowns from afar softer and broader (6 m crowns, light against near-black gaps, read as polka dots on
            # the towers from the plain 500-900 m off)
            if isinstance(L.get('canopy'), dict):
                L = dict(L, canopy=dict(L['canopy'], crown_m=8.0, light='#577b40', gap='#27361f'))
            L = dict(L, patches=list(L.get('patches') or [])
                     + [dict(scale_m=None, tint=(0.8, 0.86, 0.8), amount=0.5,
                             where='smoothstep(0.1, 0.8, northness) * smoothstep(12, 25, slope)'),
                        dict(scale_m=None, tint=(1.12, 1.1, 0.92), amount=0.45,
                             where='smoothstep(-0.1, -0.8, northness) * smoothstep(12, 25, slope)')])
        layers.append(L)
    if not any(L['name'] == 'river gravel' for L in layers):
        layers.insert(min(2, len(layers)), gravel)
    out = dict(pal, layers=layers[:P.MAX_LAYERS],
               title=pal['title'] + " (tower_karst: rock on the sheer walls, gravel on the river's banks and bars)")
    out.pop('name', None)
    return out


TOWER_KARST.defaults['palette'] = karst_palette()
RECIPES = [TOWER_KARST]
