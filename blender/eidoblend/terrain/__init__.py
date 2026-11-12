"""eidoblend.terrain: the terrain-and-surfaces family of the Blender edition.

    from eidoblend.terrain import make_terrain, recipes, describe
    t = make_terrain(recipe='real_place', params={'dem': 'lauterbrunnen'}, focus=(480, 1640), seed=1)
    obj, height_at, masks = t                  # or t.obj, t.height_at(x, y), t.masks['slope'].at(x, y)
    recipes()                                  # every recipe's name and title
    describe('real_place')                     # its stages, knobs (units, defaults, ranges) and references

    from eidoblend.terrain import layer_surface   # the surface tools for built geometry, unchanged

Guide: tools-guides/terrain-surfaces.md; design: blender/tests/terrain/DESIGN.md. Self-contained: imports no
other family's subpackage.

Names are resolved on first use, so importing a numeric module of the family (core, masks, the solvers, the recipes)
needs no bpy and runs in plain Python. `recipes` is the recipe registry (the recipes/ subpackage), and calling it
lists the recipes.
"""
import importlib

_EXPORTS = {
    'make_terrain': '.api', 'Terrain': '.api', 'MaskSet': '.api', 'describe': '.api', 'terrain_height_at': '.api',
    'normalize_texel_density': '.surface_layers', 'make_layered_material': '.surface_layers',
    'layer_surface': '.surface_layers', 'grunge_texture': '.surface_layers', 'add_curvature': '.surface_layers',
    'add_geometry_normal': '.surface_layers', 'fetched_reason': '.surface_layers',
    'find_set': '._pbr', 'load_set': '._pbr', 'texture_roots': '._pbr',
}

__all__ = ['make_terrain', 'Terrain', 'MaskSet', 'recipes', 'describe', 'terrain_height_at',
           'normalize_texel_density', 'make_layered_material', 'layer_surface', 'grunge_texture', 'add_curvature',
           'add_geometry_normal', 'fetched_reason', 'find_set', 'load_set', 'texture_roots']


def __getattr__(name):
    if name == 'recipes':
        return importlib.import_module('.recipes', __name__)
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value = getattr(importlib.import_module(mod, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
