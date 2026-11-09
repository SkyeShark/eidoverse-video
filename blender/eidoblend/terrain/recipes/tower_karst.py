"""tower_karst: Guilin's karst. Fenglin (sheer towers on a flat river plain, with peak clusters between the plains)
or fengcong (cones packed on a raised common base, closed star-shaped dolines between them). Design 4.10 and row
`tower_karst` of section 5; the solver is solvers/karst.py.

    make_terrain('tower_karst', seed=7)                                   # Yangshuo-like fenglin, 8 km
    make_terrain('tower_karst', params={'kind': 'fengcong'})              # cone karst: no plain, no river
    make_terrain('tower_karst', params={'spacing_m': 260, 'median_height_m': 160, 'cluster_cover': 0.5})

Stages, in order:
  karst      every level: the alluvial plain and its river, the towers and cluster peaks (blue-noise centres, each
             tower's profile, footprint, spurs, lobes and summit from world-space numbers), the cockpits; vertical
             fluting on levels with cells of 2 m or less. Rebuilt per level from world functions, so the walls are
             sharp at every scale (`levels='all'`, not the design's 'resolves:200': a wall upsampled from a coarser
             level would be soft at 0.5 m).
  threshold  limestone at Sc 75 degrees (the karst op writes Sc with +-8 % noise at 50 m; the stage reads it when
             it has no threshold_deg); package 3's solvers/hillslope.py.
  creep      light linear creep, kappa_t_m2 20 m^2: takes the edge off rims and toes; package 3's.
  talus      the trimmed rock settles at 35 degrees on the loose material (cells <= 4 m); package 3's.

The cockpits between the cluster peaks are closed depressions by design (karst drains underground): the level
runner's end stage must neither flood nor fill them, so the recipe sets defaults['lakes'] = False (run.py: "False
skips them"); the karst op already gives each cockpit its flat soil floor.
"""
from ..core.recipe import Knob, Recipe, Stage
from ..solvers.karst import DEFAULTS, KIND_PRESETS

# the knobs that are also karst parameters; their defaults are fenglin's, and kind='fengcong' takes its own preset
# for every one of them left at that default
_KIND_DEPENDENT = ('spacing_m', 'median_height_m', 'cluster_cover', 'plinth_m', 'river')


def _apply_knobs(p):
    """Write the knob values into the karst stage's parameters. With kind other than 'fenglin', a knob left at its
    (fenglin) default is not written, so the kind's preset in solvers/karst.py decides it."""
    st = p.stage('karst')
    st['kind'] = p['kind']
    knobs = p.recipe.knobs if p.recipe is not None else {}
    for k in ('spacing_m', 'median_height_m', 'wall_deg', 'cluster_cover', 'plinth_m', 'river', 'river_width_m'):
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
                     'fenglin: peak clusters and sheer isolated towers on a flat alluvial plain with a river '
                     '(Yangshuo); fengcong: cones packed on a raised common base with closed dolines between '
                     '(the Li River gorge, Guizhou)', apply=_apply_knobs),
        'spacing_m': Knob(DEFAULTS['spacing_m'], 'm', (60.0, 1000.0),
                          'Poisson-disc spacing of the peaks inside the clusters (fengcong: 250)'),
        'median_height_m': Knob(DEFAULTS['median_height_m'], 'm', (15.0, 600.0),
                                'median summit height above the plain (fengcong: 200, above the plain under its base)'),
        'wall_deg': Knob(DEFAULTS['wall_deg'], 'deg', (55.0, 88.0),
                         "an isolated tower's wall: the chord angle between 15 % and 85 % of its height"),
        'cluster_cover': Knob(DEFAULTS['cluster_cover'], '', (0.0, 1.0),
                              'the share of the ground inside peak clusters; the rest is plain (fengcong: 0.97)'),
        'plinth_m': Knob(DEFAULTS['plinth_m'], 'm', (0.0, 300.0),
                         "the clusters' common base: the cockpit floors' height above the plain (fengcong: 80)"),
        'river': Knob(DEFAULTS['river'], 'bool', None, 'a river meandering across the plain (fengcong: none)'),
        'river_width_m': Knob(DEFAULTS['river_width_m'], 'm', (5.0, 600.0), "the river's channel width"),
    },
    stages=[
        Stage('karst', {}, levels='all'),
        Stage('threshold', {'iterations': 160}, levels='all'),
        Stage('creep', {'kappa_t_m2': 20.0}, levels='all'),
        Stage('talus', {'repose_deg': 35.0}, levels='cell<=4'),
    ],
    doc='Peaks from blue-noise centres in clusters (each fills its share of the massif) and isolated towers with '
        '70-85 degree walls on the plain; judged against guilin_karst (Copernicus 30 m: read its spacing, heights and '
        'plain, not its walls) and photographs.')

RECIPES = [TOWER_KARST]
