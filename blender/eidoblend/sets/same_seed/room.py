"""eidoblend.sets.same_seed.room: a made room appended into a scene, and where the made rooms live (Blender).

    from eidoblend.sets.same_seed import room as R
    r = R.append('sealed_room')                 # <repo>/work/sets/same_seed/sealed_room/sealed_room.blend, made by make.py
    r.group, r.parts, r.lights, r.probes        # its root Empty, meshes, lights, light probes
    r.marks['bench_top']                        # {'pos': (x, y, z) in the room's metres (relative to its root), ...}
    cam = r.make_camera('bench_right')          # one of r.cams, as a camera object under the root
    r.dispose()

A room is made once by its chain (make.py: high -> lows -> GPU bake -> prints -> look) into one .blend that holds the
room's collection (every part, its lights and its probes, the probes' bakes with them), its world and its render
settings. append() links that collection into the scene under a root Empty `<room>_root` (move or turn the root to
place the room), sets the scene's world to the room's (world=False keeps yours) and, with render=True, the room's
render settings.
"""

from __future__ import annotations

import importlib
import os

from ... import common

DEFAULT_ROOT = os.path.join(common.REPO, 'work', 'sets', 'same_seed')


def made_dir(name, out=None):
    """the folder a room is made in: `out`, else <repo>/work/sets/same_seed/<name>/"""
    return os.path.abspath(out or os.path.join(DEFAULT_ROOT, name))


def made_file(name, out=None):
    return os.path.join(made_dir(name, out), f'{name}.blend')


class Room:
    """An appended room: group (its root Empty), parts (meshes), lights, probes, collection, cams ({name: (pos, aim,
    lens)} in the room's metres), marks ({name: {...}}), render (the room's render settings for look.eevee)."""

    def __init__(self, name, group, collection, cams, marks, render, world=None):
        self.name, self.group, self.collection = name, group, collection
        objs = list(collection.all_objects)
        self.parts = [o for o in objs if o.type == 'MESH']
        self.lights = [o for o in objs if o.type == 'LIGHT']
        self.probes = [o for o in objs if o.type == 'LIGHT_PROBE']
        self.cams, self.marks, self.render, self.world = dict(cams), dict(marks), dict(render), world

    def mark(self, key):
        """a mark's point in world space (the root's transform applied)"""
        from mathutils import Vector
        return self.group.matrix_world @ Vector(self.marks[key]['pos'])

    def make_camera(self, name, coll=None):
        """one of the room's cameras (cams[name]) as an object parented to the root"""
        from . import look as L
        pos, aim, lens = self.cams[name]
        cam = L.camera(f'{self.name}.{name}', pos, aim, lens, coll or self.collection)
        cam.parent = self.group
        return cam

    def dispose(self):
        """remove what append() brought in (its objects, its collection and the ones inside it, and its world when no
        one else uses it)"""
        import bpy
        root = self.group.name
        for o in list(self.collection.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        if root in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[root], do_unlink=True)
        for c in list(self.collection.children_recursive)[::-1] + [self.collection]:
            bpy.data.collections.remove(c)
        if self.world is not None and self.world.users == 0:
            bpy.data.worlds.remove(self.world)


def append(name, ctx=None, blend=None, scene=None, world=True, render=False, location=(0.0, 0.0, 0.0), rotation_z=0.0):
    """Append the made room `name` (blend: its file, default made_file(name)) into the scene (ctx.scene, scene, or the
    context's). -> Room"""
    import bpy
    mod = importlib.import_module(f'{__package__}.{name}')
    path = os.path.abspath(blend or made_file(name))
    if not os.path.isfile(path):
        raise FileNotFoundError(f'{name}: {path} is not made yet; make it with: '
                                f'python blender/eidoblend/sets/same_seed/make.py {name}'
                                + (f' --out {os.path.dirname(path)}' if blend else ''))
    sc = scene or (ctx.scene if ctx is not None and getattr(ctx, 'scene', None) is not None else bpy.context.scene)
    wname = mod.WORLD
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [n for n in src.collections if n == mod.COLLECTION]
        dst.worlds = [n for n in src.worlds if n == wname] if world and wname else []
    if not dst.collections:
        raise ValueError(f'{name}: {path} has no collection {mod.COLLECTION!r}')
    c = dst.collections[0]
    sc.collection.children.link(c)
    root = bpy.data.objects.new(f'{name}_root', None)
    root.empty_display_size = 0.5
    c.objects.link(root)
    for o in list(c.all_objects):
        if o is not root and o.parent is None:
            o.parent = root
    root.location = location
    root.rotation_euler = (0.0, 0.0, rotation_z)
    w = dst.worlds[0] if dst.worlds else None
    if w is not None:
        sc.world = w
    if render:
        from . import look as L
        L.eevee(sc, **mod.RENDER)
    return Room(name, root, c, mod.CAMS, mod.MARKS, mod.RENDER, w)
