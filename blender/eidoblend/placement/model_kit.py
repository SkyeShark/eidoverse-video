"""load_kit: use a modular kit / asset-library GLB part by part (the port of eidoverse/model_kit.js).

    from eidoblend.placement import load_kit, place_on
    kit = load_kit('<repo>/eidoverse/assets/models/scifi_barrels_group_of_four.glb')
    kit.list()                              # part names
    barrel = kit.get(kit.list()[0])         # a fresh copy, bounds centred at XY 0, resting on Z 0
    for b in kit.islands():                 # one object per spatially separate piece
        place_on(b, ground, xy=(x, y))

Many fetched models are KITS: a parts library laid out as a catalogue, not one object. The source
is imported once into a collection that never renders (its objects are flagged no_clipping_check
so no helper or audit sees them) and is never changed; every get / part / family / islands call
returns a new root Empty at the world origin holding copies that SHARE the source's mesh data, its
bounds centred in XY with its lowest point on Z = 0, ready for place_on.
"""
import bpy
import numpy as np
from mathutils import Matrix, Vector

_GEOM = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}


def _box(objs):
    mn = np.full(3, np.inf)
    mx = np.full(3, -np.inf)
    for o in objs:
        for c in ([o] + list(o.children_recursive)):
            if c.type not in _GEOM:
                continue
            M = np.array(c.matrix_world)
            pts = np.array([tuple(v) for v in c.bound_box]) @ M[:3, :3].T + M[:3, 3]
            mn = np.minimum(mn, pts.min(0))
            mx = np.maximum(mx, pts.max(0))
    return (mn, mx) if np.isfinite(mn).all() else None


def _copy_tree(o, parent, coll):
    c = o.copy()
    c.hide_render = False
    for k in ('no_clipping_check',):
        if k in c:
            del c[k]
    coll.objects.link(c)
    if parent is not None:
        c.parent = parent
        c.matrix_parent_inverse = o.matrix_parent_inverse.copy() if o.parent else parent.matrix_world.inverted()
    for ch in o.children:
        _copy_tree(ch, c, coll)
    return c


class Kit:
    def __init__(self, parts, source_collection):
        self.parts = parts
        self.source = source_collection
        self.names = [p.name for p in parts]
        self.count = len(parts)

    def list(self):
        return list(self.names)

    def _recentred(self, nodes, name, collection=None):
        coll = collection or bpy.context.scene.collection
        b = _box(nodes)
        root = bpy.data.objects.new(name, None)
        coll.objects.link(root)
        root['eido_loaded_asset'] = True
        off = Matrix.Translation(Vector((-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]))) if b else Matrix()
        for n in nodes:
            c = _copy_tree(n, None, coll)
            c.parent = root
            c.matrix_parent_inverse = Matrix()
            c.matrix_basis = off @ n.matrix_world
        bpy.context.view_layer.update()
        return root

    def get(self, name, collection=None):
        for p in self.parts:
            if p.name == name:
                return self._recentred([p], name, collection)
        return None

    def part(self, i, collection=None):
        return self._recentred([self.parts[i]], self.parts[i].name, collection) if 0 <= i < len(self.parts) else None

    def family(self, prefix, collection=None):
        pf = str(prefix).lower()
        return [self._recentred([p], p.name, collection) for p in self.parts if p.name.lower().startswith(pf)]

    def islands(self, collection=None):
        """One recentred root per spatially separate piece: parts whose bounds, grown by 0.15 x the
        median part diagonal, touch are merged (union-find), so a multi-mesh plant is one island
        and a row of three plants is three."""
        boxes = [_box([p]) for p in self.parts]
        diag = sorted(float(np.linalg.norm(b[1] - b[0])) for b in boxes)
        eps = (diag[len(diag) >> 1] if diag else 1.0) * 0.15
        par = list(range(len(boxes)))

        def find(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if np.all(a[0] - eps <= b[1]) and np.all(b[0] <= a[1] + eps):
                    par[find(i)] = find(j)
        groups = {}
        for i in range(len(boxes)):
            groups.setdefault(find(i), []).append(self.parts[i])
        return [self._recentred(g, 'kit_island', collection) for g in groups.values()]


def load_kit(path_or_objects, name=None):
    """Import a kit GLB once (or take already-imported top-level objects) and return a Kit."""
    if isinstance(path_or_objects, (str, bytes)) or hasattr(path_or_objects, 'suffix'):
        path = str(path_or_objects)
        nm = name or path.replace('\\', '/').rsplit('/', 1)[-1].rsplit('.', 1)[0]
        coll = bpy.data.collections.new('eido_kit_' + nm)
        bpy.context.scene.collection.children.link(coll)
        coll.hide_render = True
        before = set(bpy.data.objects)
        layer_coll = bpy.context.view_layer.layer_collection.children[coll.name]
        prev = bpy.context.view_layer.active_layer_collection
        bpy.context.view_layer.active_layer_collection = layer_coll
        try:
            bpy.ops.import_scene.gltf(filepath=path)
        finally:
            bpy.context.view_layer.active_layer_collection = prev
        new = [o for o in bpy.data.objects if o not in before]
        tops = [o for o in new if o.parent is None]
    else:
        new = []
        for o in path_or_objects:
            new += [o] + list(o.children_recursive)
        tops = [o for o in path_or_objects if o.parent is None or o.parent not in path_or_objects]
        coll = None
    for o in new:
        o['eido_loaded_asset'] = True
        o['no_clipping_check'] = True                # the catalogue is never a support or an obstacle
        o.hide_render = True
    host = tops
    while len(host) == 1 and len(host[0].children) == 1 and len(host[0].children[0].children) > 1:
        host = [host[0].children[0]]
    if len(host) == 1 and len(host[0].children) > 1:
        host = list(host[0].children)
    bpy.context.view_layer.update()
    parts = [p for p in host if _box([p]) is not None]
    return Kit(parts, coll)
