"""eidoblend.flora: the vegetation brush (createFlora) for the Blender 5.2 EEVEE edition.

    from eidoblend.flora import create_flora, FLORA_SPECIES, GRASS_COLORS, DAISY_COLORS, reset_flora_occupancy

The planning half (species, generators, placement) imports without bpy; create_flora needs Blender.
Guide: tools-guides/vegetation.md.
"""
from .vegetation import FLORA_SPECIES, GRASS_COLORS, reset_flora_occupancy, plan_flora, create_flora
from .vegetation_daisy_gen import DAISY_COLORS

__all__ = ['create_flora', 'FLORA_SPECIES', 'GRASS_COLORS', 'DAISY_COLORS', 'reset_flora_occupancy', 'plan_flora']
