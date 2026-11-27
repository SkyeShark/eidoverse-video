"""eidoblend.props.carbine: an M4A1-pattern carbine built as a proper hard-surface asset: a 499 k-triangle HIGH, a
21 k-triangle LOW drawn from the same tables (64 parts), the high baked onto the low on the GPU, and one layered
material on the bakes. Function markings only (the rail's numbers, the selector's words): no maker's marks, no serial.

    from eidoblend.props import carbine
    rifle = carbine.build(ctx=ctx)            # the delivered asset appended into the scene (make it once, below)
    rifle.group.location = (0.4, 0.0, 0.9)    # its root Empty; rifle.parts: the 64 meshes; rifle.dispose()

    python blender/eidoblend/props/carbine/make.py [--out work/props/carbine] [--size 4096] [--cells 1024]
        # decals -> high -> low -> prep (the low finished, UVs packed, the bake's inputs) -> GPU bake -> look

The asset's space: metres, +X to the muzzle, +Z up, +Y the carbine's left; the origin on the bore's axis at the
receiver's rear face; every part at identity. Its modules:
    high, front, top, grip, details   the construction (the kit's masses; build(low=True) for the low)
    decals                            the drawn data at real size (plain Python: Pillow)
    layers                            the markings and the grip's relief laid into the bake (gpu_bake.py --layers)
    look                              its layered material and condition (wear, polish, dust, grime)
    cli                               the Blender steps; make: the whole chain (plain Python)
build() needs the made file: make.py writes <out>/carbine.blend (default work/props/carbine/). Guide:
tools-guides/props-and-sets.md ("The carbine").
"""

from __future__ import annotations

import importlib
import os

from ... import common

DEFAULT_DIR = os.path.join(common.REPO, 'work', 'props', 'carbine')
NAME = 'carbine'
MODULES = ('high', 'front', 'top', 'grip', 'details', 'decals', 'layers', 'look', 'cli', 'make')


class Carbine:
    """The appended asset: group (its root Empty), parts (its meshes), collection; dispose() removes them."""

    def __init__(self, group, parts, collection):
        self.group, self.parts, self.collection = group, parts, collection

    def dispose(self):
        import bpy
        for o in list(self.collection.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(self.collection)


def build(ctx=None, blend=None, scene=None, name='carbine'):
    """Append the made carbine (blend: its file, default DEFAULT_DIR/carbine.blend) into the scene (ctx.scene, scene,
    or the context's) under a root Empty `<name>_root`. -> Carbine"""
    import bpy
    path = os.path.abspath(blend or os.path.join(DEFAULT_DIR, f'{NAME}.blend'))
    if not os.path.isfile(path):
        raise FileNotFoundError(f'carbine.build: {path} is not made yet; make it with: python blender/eidoblend/props/carbine/make.py'
                                + (f' --out {os.path.dirname(path)}' if blend else ''))
    sc = scene or (ctx.scene if ctx is not None and hasattr(ctx, 'scene') else bpy.context.scene)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [n for n in src.collections if n == NAME]
    if not dst.collections:
        raise ValueError(f'carbine.build: {path} has no collection {NAME!r}')
    c = dst.collections[0]
    sc.collection.children.link(c)
    root = bpy.data.objects.new(f'{name}_root', None)
    c.objects.link(root)
    for o in list(c.objects):
        if o is not root and o.parent is None:
            o.parent = root
    return Carbine(root, [o for o in c.objects if o.type == 'MESH'], c)


def __getattr__(name):
    """carbine.high, .look, .make ...: the modules, imported on first use."""
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
