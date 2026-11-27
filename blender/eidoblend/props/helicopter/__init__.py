"""eidoblend.props.helicopter: a UH-60-pattern helicopter built as a measured high (290 parts), rendered as its high:
its wear and dust masks stored on its own vertices, one layer stack reading them, its rivets, seams and stencils
drawn at real size. Function markings only: no service title, no serial, no unit's mark.

    from eidoblend.props import helicopter
    heli = helicopter.build(ctx=ctx)                       # the made asset appended into the scene (make it once, below)
    heli.group.location = (0.0, 0.0, 70.0)                 # its root Empty: fly it by keying the root
    heli.spin(1, 240, fps=24)                              # the rotors keyed turning (258 and 1190 rpm), LINEAR
    heli.parts, heli.main_rotor, heli.tail_rotor; heli.dispose()

    python blender/eidoblend/props/helicopter/make.py [--out work/props/helicopter] [--stills]
        # decals -> high (~10 s) -> look (the vertex masks' rays: ~2 min) -> helicopter.blend (~66 MB)

The asset's space: metres, x AFT of the mast, y to the aircraft's RIGHT, z UP from the cabin floor (the nose at
x -4.5, the tail rotor at x +9.9; the gear built as it hangs in flight, the main wheels down to z -0.91). The cabin
doors are slid open; at the left door a troop seat faces out (seat_door_l, its pan 0.445 m up). Its modules:
    datum                       the measured numbers (plain Python)
    high, hull, top, tail, rotor, gear, cabin, doors, fit   the construction (the kit's masses, sections and skins)
    decals                      rivets, seams, fasteners and stencils at real size (plain Python: Pillow)
    look                        the vertex masks, the layer stack and every material
    cli                         the Blender steps; make: the whole chain (plain Python)
Guide: tools-guides/props-and-sets.md ("The helicopter").
"""

from __future__ import annotations

import importlib
import math
import os

from ... import common

DEFAULT_DIR = os.path.join(common.REPO, 'work', 'props', 'helicopter')
NAME = 'helicopter'
MODULES = ('datum', 'high', 'hull', 'top', 'tail', 'rotor', 'gear', 'cabin', 'doors', 'fit', 'decals', 'look', 'cli', 'make')


class Helicopter:
    """The appended asset: group (its root Empty), parts (its meshes), main_rotor / tail_rotor (the Empties that turn
    the rotors: the main about its local Z, the tail about its local Y), collection; spin(); dispose()."""

    def __init__(self, group, collection):
        self.group, self.collection = group, collection
        self.parts = [o for o in collection.objects if o.type == 'MESH']
        self.main_rotor = next((o for o in collection.objects if o.name.split('.')[0] == 'main_rotor'), None)
        self.tail_rotor = next((o for o in collection.objects if o.name.split('.')[0] == 'tail_rotor'), None)

    def spin(self, frame_start, frame_end, fps=24.0, rpm=258.0, tail_rpm=1190.0):
        """Key the rotors turning from frame_start to frame_end at rpm (the main rotor counter-clockwise seen from
        above) and tail_rpm, LINEAR, two keys each from their current angles."""
        return spin(self, frame_start, frame_end, fps, rpm, tail_rpm)

    def dispose(self):
        import bpy
        for o in list(self.collection.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(self.collection)


def spin(heli, frame_start, frame_end, fps=24.0, rpm=258.0, tail_rpm=1190.0):
    """Keyed rotation of heli.main_rotor (local Z) and heli.tail_rotor (local Y) over the frames; LINEAR keys."""
    turns = []
    for ob, ax, r in ((heli.main_rotor, 2, rpm), (heli.tail_rotor, 1, tail_rpm)):
        if ob is None:
            continue
        a0 = ob.rotation_euler[ax]
        for f, a in ((frame_start, a0), (frame_end, a0 + 2.0 * math.pi * r / 60.0 * (frame_end - frame_start) / fps)):
            ob.rotation_euler[ax] = a
            ob.keyframe_insert('rotation_euler', index=ax, frame=f)
        ob.rotation_euler[ax] = a0
        ad = ob.animation_data
        if ad and ad.action:
            from bpy_extras.anim_utils import action_get_channelbag_for_slot
            cb = action_get_channelbag_for_slot(ad.action, ad.action_slot)
            for fc in cb.fcurves:
                if fc.data_path == 'rotation_euler' and fc.array_index == ax:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
        turns.append((ob.name, round((frame_end - frame_start) / fps * r / 60.0, 3)))
    return turns


def build(ctx=None, blend=None, scene=None, name='helicopter'):
    """Append the made helicopter (blend: its file, default DEFAULT_DIR/helicopter.blend) into the scene (ctx.scene,
    scene, or the context's) under a root Empty `<name>_root`. -> Helicopter"""
    import bpy
    path = os.path.abspath(blend or os.path.join(DEFAULT_DIR, f'{NAME}.blend'))
    if not os.path.isfile(path):
        raise FileNotFoundError(f'helicopter.build: {path} is not made yet; make it with: python blender/eidoblend/props/helicopter/make.py'
                                + (f' --out {os.path.dirname(path)}' if blend else ''))
    sc = scene or (ctx.scene if ctx is not None and hasattr(ctx, 'scene') else bpy.context.scene)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [n for n in src.collections if n == NAME]
    if not dst.collections:
        raise ValueError(f'helicopter.build: {path} has no collection {NAME!r}')
    c = dst.collections[0]
    sc.collection.children.link(c)
    root = bpy.data.objects.new(f'{name}_root', None)
    c.objects.link(root)
    for o in list(c.objects):
        if o is not root and o.parent is None:
            o.parent = root
    return Helicopter(root, c)


def __getattr__(name):
    """helicopter.high, .look, .make ...: the modules, imported on first use."""
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
