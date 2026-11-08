"""eidoblend.terrain: the terrain-and-surfaces family of the Blender edition.

    from eidoblend.terrain import make_terrain, layer_surface
    terrain, height_at = make_terrain(size=80, amplitude=3, seed=7, flat_radius=8, layers=[...])

Guide: tools-guides/terrain-surfaces.md. Self-contained: imports no other family's subpackage.
"""
from .heightfield import make_terrain, terrain_height_at
from .surface_layers import (normalize_texel_density, make_layered_material, layer_surface,
                             grunge_texture, add_curvature, add_geometry_normal, fetched_reason)
from ._pbr import find_set, load_set, texture_roots

__all__ = ['make_terrain', 'terrain_height_at', 'normalize_texel_density', 'make_layered_material',
           'layer_surface', 'grunge_texture', 'add_curvature', 'add_geometry_normal', 'fetched_reason',
           'find_set', 'load_set', 'texture_roots']
