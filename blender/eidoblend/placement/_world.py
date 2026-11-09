"""World-space geometry queries the placement helpers and audits share (private).

Every query reads EVALUATED geometry (modifiers, Geometry Nodes, shape keys at the current frame) in
WORLD space, so a Displace or Subdivision modifier is seen exactly as it renders. The engine's caveat
about TSL `positionNode` deformation has no twin here; only shader displacement stays invisible.

Ray casts go through one BVH per object built in the object's own space (BVHTree.FromObject: fast,
in C) and cached; rays are carried into that space and hits back out, so moving an object never
rebuilds its tree. BVHTree.ray_cast does not cull back faces: a ray hits both sides (the engine had
to force DoubleSide for its enclosure test; nothing to do here).

Conventions (eidoblend): Blender Z up, metres. Custom properties stand in for the engine's
userData flags, snake_cased: no_support_check, allow_intersect, no_clipping_check, no_z_fight_check,
no_facing_check, no_intrusion_check, assembly, _sunk_placement, _support_target(s).
"""
import re

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

GEOM_TYPES = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}
_SKIP_NAME = re.compile(r'^(secondary|hair|Hair)$')
_BVH_CACHE = {}


def update():
    bpy.context.view_layer.update()


def depsgraph():
    return bpy.context.evaluated_depsgraph_get()


def clear_cache():
    """Forget cached BVH trees (call after editing a mesh's geometry in place)."""
    _BVH_CACHE.clear()


def flag(o, name):
    try:
        return bool(o.get(name))
    except Exception:
        return False


def visible(o):
    return not o.hide_render and (o.visible_get() if bpy.context.view_layer.objects.get(o.name) else True)


def is_ancestor(a, b):
    """True when a is b or one of b's parents."""
    p = b
    while p is not None:
        if p == a:
            return True
        p = p.parent
    return False


def as_objects(t):
    """An object, a collection, or a list of either -> a flat list of objects."""
    if t is None:
        return []
    if isinstance(t, bpy.types.Collection):
        return [o for o in t.all_objects if o.parent is None or o.parent.name not in t.all_objects]
    if isinstance(t, bpy.types.Scene):
        return [o for o in t.objects if o.parent is None]
    if isinstance(t, (list, tuple, set)):
        out = []
        for x in t:
            out += as_objects(x)
        return out
    return [t]


class _EvalInstance:
    """An instance's evaluated stand-in: the source's evaluated object with the instance's world matrix."""

    def __init__(self, ev, matrix):
        self._ev = ev
        self.matrix_world = matrix

    def __getattr__(self, name):
        return getattr(self._ev, name)


class InstanceProxy:
    """One object of a collection instance, standing in for a real object wherever the helpers and audits read
    geometry (bounds, rays, triangles): the source object's geometry at the instance's world matrix. Its parent is
    the instancing Empty, so root_of / is_ancestor / placed roots treat the instance as part of that Empty (a kit
    part from harness.assets.load_kit, a collection instanced by hand)."""

    def __init__(self, src, instancer, matrix, index):
        self.src = src
        self.parent = instancer
        self.matrix_world = matrix
        self.name = f'{instancer.name}/{src.name}'
        self.children = []
        self._key = (instancer.as_pointer(), src.as_pointer(), index)

    def __eq__(self, other):
        return isinstance(other, InstanceProxy) and other._key == self._key

    def __hash__(self):
        return hash(self._key)

    @property
    def hide_render(self):
        return self.parent.hide_render

    def evaluated_get(self, dg):
        return _EvalInstance(self.src.evaluated_get(dg), self.matrix_world)

    def get(self, key, default=None):
        return self.src.get(key, default)

    def __getattr__(self, name):
        return getattr(self.src, name)


def _instances_of(o, depth=0):
    """The geometry objects a collection-instancing Empty shows, as InstanceProxy objects (nested instancing
    followed four levels deep)."""
    coll = getattr(o, 'instance_collection', None) if getattr(o, 'instance_type', '') == 'COLLECTION' else None
    if coll is None or depth > 4:
        return []
    out = []
    base = o.matrix_world @ Matrix.Translation(-Vector(coll.instance_offset))
    for i, s in enumerate(coll.all_objects):
        if s.hide_render or flag(s, 'no_clipping_check') or s.type in ('LIGHT', 'CAMERA'):
            continue
        m = base @ s.matrix_world
        if s.type in GEOM_TYPES:
            out.append(InstanceProxy(s, o, m, i))
        if getattr(s, 'instance_type', '') == 'COLLECTION' and s.instance_collection is not None:
            for p in _instances_of(s, depth + 1):           # p sits in s's source space: carry it to this instance
                out.append(InstanceProxy(p.src, o, base @ p.matrix_world, (i, p._key)))
    return out


def collect(root, exclude=()):
    """Visible geometry objects in root's subtree (root included), as the engine's collectMeshes, with the objects
    of collection instances (an Empty instancing a collection: a kit part, a hand-made instance) as InstanceProxy
    stand-ins at the instance's place.

    Prunes a whole subtree under an object flagged no_clipping_check, hidden objects, lights and
    cameras, and VRM secondary chains (named secondary / hair).
    """
    excl = set(exclude)
    out = []

    def walk(o):
        if o in excl or not visible(o) or flag(o, 'no_clipping_check') or _SKIP_NAME.match(o.name):
            return
        if o.type in ('LIGHT', 'CAMERA'):
            return
        if o.type in GEOM_TYPES:
            out.append(o)
        out.extend(_instances_of(o))
        for c in o.children:
            walk(c)
    for r in as_objects(root):
        walk(r)
    return out


def box_of_object(o, dg=None):
    """World AABB (min Vector, max Vector) of one object's evaluated bounds (its 8 corners
    transformed: the same loose box three's Box3.setFromObject gives for a rotated mesh)."""
    dg = dg or depsgraph()
    ev = o.evaluated_get(dg)
    M = ev.matrix_world
    pts = [M @ Vector(c) for c in ev.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def tight_box(obj, exclude=(), dg=None):
    """World AABB of obj's visible geometry descendants (the engine's tightBox). Falls back to the
    object's own location when it holds no geometry. Returns (min, max) Vectors."""
    dg = dg or depsgraph()
    ms = collect(obj, exclude)
    if not ms:
        p = obj.matrix_world.translation.copy()
        return p.copy(), p.copy()
    mn = Vector((1e30, 1e30, 1e30))
    mx = Vector((-1e30, -1e30, -1e30))
    for m in ms:
        a, b = box_of_object(m, dg)
        mn = Vector((min(mn.x, a.x), min(mn.y, a.y), min(mn.z, a.z)))
        mx = Vector((max(mx.x, b.x), max(mx.y, b.y), max(mx.z, b.z)))
    return mn, mx


def box_center(b):
    return (b[0] + b[1]) * 0.5


def box_size(b):
    return b[1] - b[0]


def boxes_intersect(a, b):
    return (a[0].x <= b[1].x and a[1].x >= b[0].x and a[0].y <= b[1].y and a[1].y >= b[0].y
            and a[0].z <= b[1].z and a[1].z >= b[0].z)


def box_overlap(a, b):
    """Per-axis overlap lengths (can be negative)."""
    return Vector((min(a[1].x, b[1].x) - max(a[0].x, b[0].x),
                   min(a[1].y, b[1].y) - max(a[0].y, b[0].y),
                   min(a[1].z, b[1].z) - max(a[0].z, b[0].z)))


def box_volume(b):
    s = box_size(b)
    return max(1e-9, s.x * s.y * s.z)


def _geom_key(o):
    d = o.data
    mods = tuple((m.type, m.show_render) for m in getattr(o, 'modifiers', []))
    n = len(d.vertices) if hasattr(d, 'vertices') else 0
    return (o.as_pointer(), d.as_pointer() if d else 0, n, mods)


def local_bvh(o, dg=None):
    """A cached BVHTree of o's evaluated geometry in o's own space."""
    o = o.src if isinstance(o, InstanceProxy) else o          # an instance shares its source's tree (own space)
    key = _geom_key(o)
    t = _BVH_CACHE.get(key)
    if t is None:
        dg = dg or depsgraph()
        ev = o.evaluated_get(dg)
        try:
            t = BVHTree.FromObject(ev, dg)
        except Exception:
            me = ev.to_mesh()
            t = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
            ev.to_mesh_clear()
        _BVH_CACHE[key] = t
    return t


def world_tris(o, dg=None):
    """(verts Nx3 world float64, tris Mx3) of o's evaluated, triangulated geometry."""
    dg = dg or depsgraph()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get('co', co)
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get('vertices', tri)
    finally:
        ev.to_mesh_clear()
    M = np.array(ev.matrix_world, dtype=np.float64)
    co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return co, tri.reshape(-1, 3)


def world_bvh(objs, dg=None):
    """One world-space BVHTree over several objects (for BVHTree.overlap between objects)."""
    vs, ps, off = [], [], 0
    for o in objs:
        co, tri = world_tris(o, dg)
        vs.append(co)
        ps.append(tri + off)
        off += len(co)
    if not vs:
        return None
    co = np.concatenate(vs)
    tri = np.concatenate(ps)
    return BVHTree.FromPolygons(co.tolist(), tri.tolist(), all_triangles=True)


def world_verts(o, dg=None, cap=None):
    co, _ = world_tris(o, dg)
    if cap and len(co) > cap:
        co = co[::max(1, len(co) // cap)]
    return co


def _clip_poly(poly, axis, value, keep_ge):
    """Sutherland-Hodgman: the part of a 3D polygon on one side of the vertical plane coord[axis] = value."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ina = (a[axis] >= value) if keep_ge else (a[axis] <= value)
        inb = (b[axis] >= value) if keep_ge else (b[axis] <= value)
        if ina:
            out.append(a)
        if ina != inb:
            d = b[axis] - a[axis]
            t = (value - a[axis]) / d if d else 0.0
            out.append(a + (b - a) * t)
    return out


LOAD_BEARING_NZ = 0.5       # |normal.z| of a face that can carry what rests on it (a slope under 60 degrees)


def surface_top_in_footprint(objs, box, top_z, dg=None, min_nz=LOAD_BEARING_NZ):
    """The highest point of objs' REAL load-bearing surfaces inside box's xy footprint, at or below top_z, or None.

    Every triangle of the evaluated geometry that faces up or down (|normal.z| >= min_nz: a top, a board, a wire's
    crown, a slope under 60 degrees; either winding, as imported models come) is clipped to the footprint (the
    four vertical planes of the box's xy rectangle); a clipped piece reaching up past top_z counts as top_z (the
    object's base is in contact with it). Unlike a ray grid, nothing thin slips between samples (a wire rack, a
    slatted bench); unlike the support's bounding box, nothing off to the side counts (a stool's splayed legs reach
    under a clock its seat no longer holds). Steep and vertical faces never count: a rack's post or a chair's
    backrest standing inside a lifted book's or cushion's footprint rises past its base but holds nothing up."""
    dg = dg or depsgraph()
    x0, y0, x1, y1 = box[0].x, box[0].y, box[1].x, box[1].y
    best = None
    for o in objs:
        co, tri = world_tris(o, dg)
        if not len(tri):
            continue
        P = co[tri]                                          # (M, 3, 3)
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        ln = np.linalg.norm(n, axis=1)
        flat = np.abs(n[:, 2]) >= min_nz * np.maximum(ln, 1e-30)
        sel = (flat & (ln > 0) & (P[:, :, 0].max(1) >= x0) & (P[:, :, 0].min(1) <= x1) & (P[:, :, 1].max(1) >= y0)
               & (P[:, :, 1].min(1) <= y1) & (P[:, :, 2].min(1) <= top_z))
        if best is not None:
            sel &= P[:, :, 2].max(1) > best                   # cannot beat what was found
        for t in P[sel]:
            poly = [t[0], t[1], t[2]]
            for axis, value, ge in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
                poly = _clip_poly(poly, axis, value, ge)
                if not poly:
                    break
            if not poly:
                continue
            zs = [float(p[2]) for p in poly]
            if min(zs) > top_z:
                continue
            z = min(max(zs), top_z)
            if best is None or z > best:
                best = z
    return best


class Rays:
    """Ray casting in world space against a fixed list of objects (nearest hit wins)."""

    def __init__(self, objs, dg=None):
        dg = dg or depsgraph()
        self.items = []
        for o in objs:
            ev = o.evaluated_get(dg)
            M = ev.matrix_world.copy()
            try:
                Mi = M.inverted()
            except ValueError:
                continue
            self.items.append((o, local_bvh(o, dg), M, Mi, Mi.to_3x3(), M.to_3x3().inverted_safe().transposed()))

    def cast(self, origin, direction, max_dist=1e9):
        """Nearest hit: (location Vector, normal Vector, object, distance) or None."""
        origin = Vector(origin)
        d = Vector(direction).normalized()
        best = None
        for o, t, M, Mi, Mi3, N3 in self.items:
            lo = Mi @ origin
            ld = Mi3 @ d
            ll = ld.length
            if ll == 0:
                continue
            hit = t.ray_cast(lo, ld / ll, max_dist * ll if max_dist < 1e8 else 1e9)
            if hit[0] is None:
                continue
            p = M @ hit[0]
            dist = (p - origin).length
            if dist > max_dist:
                continue
            if best is None or dist < best[3]:
                n = (N3 @ hit[1]).normalized()
                best = (p, n, o, dist)
        return best

    def count_hits(self, origin, direction, max_dist):
        return 1 if self.cast(origin, direction, max_dist) else 0


def placed_roots(scene=None, exclude=()):
    """The scene's placed objects: parentless, visible, not cameras or lights; descends through a
    lone wrapper (a scene built under one root) as the engine's audits do."""
    scene = scene or bpy.context.scene
    excl = set(exclude)
    roots = [o for o in scene.objects if o.parent is None and o.type not in ('CAMERA', 'LIGHT')
             and o not in excl and visible(o)]
    g = 0
    while (len(roots) == 1 and roots[0].type not in GEOM_TYPES
           and len([c for c in roots[0].children if c.type not in ('LIGHT', 'CAMERA')]) > 1 and g < 4):
        roots = [c for c in roots[0].children if c.type not in ('LIGHT', 'CAMERA') and c not in excl]
        g += 1
    return roots


def root_of(o, root_set):
    p = o
    while p is not None and p not in root_set:
        p = p.parent
    return p if p is not None else o


def move_world(obj, delta):
    """Translate obj by a world-space delta whatever its parenting."""
    mw = obj.matrix_world.copy()
    mw.translation = mw.translation + Vector(delta)
    obj.matrix_world = mw
    update()


def name_of(o, box=None):
    if o is None:
        return '(none)'
    if o.name:
        return o.name
    b = box or tight_box(o)
    s, c = box_size(b), box_center(b)
    return '(%.1fx%.1fx%.1fm @ %.0f,%.0f,%.0f)' % (s.x, s.y, s.z, c.x, c.y, c.z)


def record_support(obj, targets):
    """The engine's userData._supportTarget: what obj was seated on (names, and the object when one)."""
    objs = as_objects(targets)
    obj['_support_targets'] = [o.name for o in objs]
    if len(objs) == 1:
        obj['_support_target'] = objs[0]
    elif '_support_target' in obj:
        del obj['_support_target']


def support_targets(obj):
    names = obj.get('_support_targets')
    if not names:
        t = obj.get('_support_target')
        return [t] if isinstance(t, bpy.types.Object) else []
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]
