"""Recipe variants for the coast package's experiments (gen.py, render_photo_views.py): the sea_cliffs recipe with a
variant's changes, so settings can be tried before they go into recipes/sea_cliffs.py.

    from variants import recipe_for
    R = recipe_for({'rocks': {'chalk': {'fluvial': {'age_myr': 2}}}, 'patch': {'coast': {'crenel_m': 2}},
                    'stages': [{'op': 'creep', 'params': {...}, 'levels': 'first', 'before': 'coast'}],
                    'defaults': {'lakes': 'sediment'}})

A variant may carry
    rocks     merged into recipes/sea_cliffs.ROCKS[rock] in this process (the rock presets the 'rock' knob applies)
    patch     {op: {param: value}} merged into that stage's params after the recipe resolves
    stages    extra stages [{"op":, "params":, "levels":, "before": op}] inserted before the named stage
    defaults  merged into the recipe's defaults
An empty variant returns the recipe as it is. ROCKS overrides change the resolved stages but not the recipe dict that
api.generate's cache is keyed on: generate such a variant with cache=False.
"""
import copy

from eidoblend.terrain.core.recipe import Recipe, Stage
from eidoblend.terrain.recipes import sea_cliffs as SC

ROCKS0 = copy.deepcopy(SC.ROCKS)


def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], v)
        else:
            dst[k] = v


def recipe_for(var=None):
    var = var or {}
    SC.ROCKS.clear()
    SC.ROCKS.update(copy.deepcopy(ROCKS0))
    for rock, upd in (var.get('rocks') or {}).items():
        merge(SC.ROCKS[rock], upd)
    if not var.get('patch') and not var.get('stages') and not var.get('defaults'):
        return SC.SEA_CLIFFS
    R = SC.SEA_CLIFFS
    stages = list(R.stages)
    for extra in var.get('stages') or []:
        st = Stage(extra['op'], dict(extra.get('params') or {}), levels=extra.get('levels', 'all'))
        k = next((i for i, s in enumerate(stages) if s.op == extra.get('before')), len(stages))
        stages.insert(k, st)
    patch = var.get('patch') or {}
    base_apply = R.knobs['rock'].apply

    def apply(p):
        base_apply(p)
        for op, upd in patch.items():
            for s in p.stages(op):
                s.update(upd)
    knobs = dict(R.knobs)
    kn = copy.copy(knobs['rock'])
    kn.apply = apply
    knobs['rock'] = kn
    return Recipe(R.name, R.title, references=R.references,
                  defaults=dict(R.defaults, **(var.get('defaults') or {})), knobs=knobs, stages=stages,
                  doc=getattr(R, 'doc', ''))
