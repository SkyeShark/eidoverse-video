"""eidoblend.props.hardsurface: the hard-surface kit. A prop is built as a HIGH (masses booleaned and bevelled the way
it is made), a LOW is drawn from the same tables, the high is baked onto the low on the GPU, and one layered material
reads the bakes (eidoblend.materials.layered). The carbine and the helicopter are built with it.

    masses       the mass constructor: prisms of measured outlines intersected, features unioned, cutters through, one
                 bevel per edge group (edge groups by construction: tagged / finish_forged); the same tables build the
                 low (start(low=True))
    sections     a lofted body from control sections (plain Python): Body, stations
    skins        lofted skins and their openings: loft_body, Surface, border, frame, screws, pane, round_poly, prism
    lowpoly      the low finished for its bake: region-weighted normals, hard edges as seams, islands cut to disks,
                 one texel density, the pack (prepare_low)
    uv_pack      the raster UV packer
    bake_export  the GPU baker's inputs (write_high / write_low) for blender/tools/gpu_bake.py
    chain        an asset's build chain run step by step from plain Python (Blender steps, the bake)

    from eidoblend.props.hardsurface import masses as hs, lowpoly, bake_export

Nothing is imported until it is asked for (sections and chain run in plain Python). Guide: tools-guides/blender.md
("Hard-surface props and baked GLBs", "High to low, baked on the GPU").
"""

import importlib

MODULES = ('masses', 'sections', 'skins', 'lowpoly', 'uv_pack', 'bake_export', 'chain')


def __getattr__(name):
    """hardsurface.masses, .skins ...: the modules, imported on first use."""
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(MODULES))
