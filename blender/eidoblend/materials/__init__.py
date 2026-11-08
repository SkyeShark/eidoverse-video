"""eidoblend.materials: procedural textures and PBR material factories (eidoverse/procedural_materials.js).

    from eidoblend.materials import procedural as PM            # the engine's window.ProceduralMaterials
    mat = PM.create_worn_metal(paint_color=0x3a5a3a, wear_amount=0.5, repeat=(2, 2))
    tex = PM.noise(512, 512, scale=12, octaves=5, contrast=0.7)  # a packed bpy Image

Guide: tools-guides/_drafts/procedural-materials.md. The numpy core (materials/_gen.py) imports no bpy and matches
the engine's canvas byte for byte on its per-pixel generators (blender/tests/terrain_extras/test_pm_parity.py).
"""
from . import procedural  # noqa: F401
from .procedural import (FACTORIES, composite, computer_plastic_90s, create_fabric, create_painted_metal,  # noqa: F401
                         create_rubber, create_scaly, create_skin, create_worn_metal, grain, height_to_normal, help,
                         mesh_material, noise, patches, pores, scratches, smudges, voronoi, weave)

__all__ = ['procedural', 'scratches', 'smudges', 'noise', 'voronoi', 'patches', 'pores', 'weave', 'grain',
           'height_to_normal', 'composite', 'create_painted_metal', 'create_rubber', 'create_skin', 'create_scaly',
           'create_fabric', 'create_worn_metal', 'computer_plastic_90s', 'mesh_material', 'FACTORIES', 'help']
