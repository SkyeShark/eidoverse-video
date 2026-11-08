"""look/overlap.py: EXACT mesh-against-mesh interpenetration in a Blender scene: which meshes cut into an object, where,
and how deep. overlap_probe.js ported, with Blender's own BVH trees (mathutils.bvhtree) of the EVALUATED meshes, so a
posed character, modifiers and shape keys are measured as they render. Read-only: nothing in the scene is changed
(push_clear moves the target only when called).

    from eidoblend.look import overlap
    hits = overlap.probe_overlaps(scene, box_obj, ignore=lambda o: o.name == 'floor')
    print(overlap.format_overlaps(hits))
    overlap.push_clear(scene, box_obj, direction=(0, 0, 1))          # lift it until nothing cuts into it

Each hit: {object, crossings (intersecting triangle pairs), where (world (min, max) of the intersecting triangles),
depth (m: the deepest vertex of either mesh INSIDE the other; 0 for a surface graze), inside ('a in b' / 'b in a'),
touch (True when depth <= tolerance: resting contact, a cup on a table, not clipping)}. Sorted deepest first.
"""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

GEOM = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}


def _world_mesh(obj, dg):
    """World-space vertices and polygons of an object's evaluated mesh (and its children's)."""
    verts, polys = [], []
    stack = [obj]
    while stack:
        o = stack.pop()
        stack.extend(o.children)
        if o.type not in GEOM or o.hide_render:
            continue
        ev = o.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        mw = ev.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in me.vertices)
        polys.extend([base + i for i in p.vertices] for p in me.polygons)
        ev.to_mesh_clear()
    return verts, polys


def _box(verts, pad=0.0):
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts))) - Vector((pad,) * 3)
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts))) + Vector((pad,) * 3)
    return lo, hi


def _boxes_meet(a, b):
    return all(a[0][i] <= b[1][i] and b[0][i] <= a[1][i] for i in range(3))


def _inside(tree, p, box):
    """Is p inside the closed-ish surface? Parity of hits along +X and +Y; both must agree (the WebGPU rule)."""
    if not all(box[0][i] <= p[i] <= box[1][i] for i in range(3)):
        return False
    votes = 0
    for d in (Vector((1, 0, 0)), Vector((0, 1, 1e-4)).normalized()):
        n, o = 0, Vector(p)
        for _ in range(256):
            loc, _nor, _i, dist = tree.ray_cast(o, d)
            if loc is None:
                break
            n += 1
            o = loc + d * 1e-5
        votes += n % 2
    return votes == 2


def _deepest(verts, tree, box, max_verts):
    step = max(1, len(verts) // max_verts)
    depth = 0.0
    for v in verts[::step]:
        if _inside(tree, v, box):
            loc, _n, _i, d = tree.find_nearest(v)
            if loc is not None and d > depth:
                depth = d
    return depth


def probe_overlaps(scene, target, ignore=None, margin=0.02, tolerance=0.002, max_verts=20000, depsgraph=None):
    """probeOverlaps: every visible mesh object near `target` (an object with its children) tested triangle against
    triangle. ignore(obj) -> True skips an object (the floor it stands on, by design)."""
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    own = {o.name for o in [target] + list(target.children_recursive)}
    tv, tp = _world_mesh(target, dg)
    if not tv:
        return []
    tbox = _box(tv, margin)
    ttree = BVHTree.FromPolygons(tv, tp, epsilon=0.0)
    hits = []
    for o in scene.objects:
        if o.name in own or o.type not in GEOM or o.hide_render or (ignore and ignore(o)):
            continue
        if any(p.name in own for p in _parents(o)):
            continue
        ev = o.evaluated_get(dg)
        cs = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        if not _boxes_meet(_box(cs), tbox):
            continue
        v, p = _world_mesh_only(o, dg)          # its children are tested as objects of their own
        if not v:
            continue
        obox = _box(v)
        if not _boxes_meet(obox, tbox):
            continue
        otree = BVHTree.FromPolygons(v, p, epsilon=0.0)
        pairs = ttree.overlap(otree)
        lo, hi = Vector((math.inf,) * 3), Vector((-math.inf,) * 3)
        for a, b in pairs:                      # 'where': the box of the crossing triangles (no segments in 5.2's BVH)
            for q in [tv[i] for i in tp[a]] + [v[i] for i in p[b]]:
                lo = Vector(map(min, lo, q))
                hi = Vector(map(max, hi, q))
        depth_b, depth_a = 0.0, 0.0
        contained = all(tbox[0][i] <= obox[0][i] and obox[1][i] <= tbox[1][i] for i in range(3))
        if pairs or contained:
            depth_b = _deepest(v, ttree, _box(tv), max_verts)       # the other's vertices inside the target
            depth_a = _deepest(tv, otree, obox, max_verts)          # the target's vertices inside the other
        depth = max(depth_a, depth_b)
        if not pairs and depth == 0:
            continue
        hits.append({'object': o.name, 'crossings': len(pairs), 'where': (lo, hi) if pairs else None,
                     'depth': depth, 'inside': ('a in b' if depth_a >= depth_b else 'b in a') if depth else '',
                     'touch': depth <= tolerance})
    hits.sort(key=lambda h: -h['depth'])
    return hits


def _parents(o):
    p = o.parent
    while p is not None:
        yield p
        p = p.parent


def _world_mesh_only(o, dg):
    """An object's own evaluated mesh (its children are tested as objects of their own)."""
    if o.type not in GEOM:
        return [], []
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    v = [mw @ x.co for x in me.vertices]
    p = [list(x.vertices) for x in me.polygons]
    ev.to_mesh_clear()
    return v, p


def format_overlaps(hits, name=''):
    """One line per hit (the log line the WebGPU probe printed)."""
    if not hits:
        return f'[overlap] {name}: nothing cuts into it'
    out = []
    for h in hits:
        kind = 'touches (resting contact)' if h['touch'] else f"CUTS {h['depth'] * 1000:.1f} mm deep ({h['inside']})"
        where = ''
        if h['where']:
            lo, hi = h['where']
            where = f" in [{lo.x:.2f}, {lo.y:.2f}, {lo.z:.2f}] .. [{hi.x:.2f}, {hi.y:.2f}, {hi.z:.2f}]"
        out.append(f"[overlap] {name} x {h['object']}: {kind}, {h['crossings']} crossing triangle pairs{where}")
    return '\n'.join(out)


def push_clear(scene, target, direction=(0.0, 0.0, 1.0), step=0.002, max_dist=1.0, tolerance=0.002, ignore=None):
    """Move `target` along `direction` in `step`s until no hit is deeper than `tolerance` (a box sunk into a table comes
    up to rest on it). Returns the distance moved, or None if it never cleared within max_dist (then it is put back)."""
    d = Vector(direction).normalized()
    start = target.location.copy()
    moved = 0.0
    while moved <= max_dist:
        bpy.context.view_layer.update()
        hits = [h for h in probe_overlaps(scene, target, ignore=ignore, tolerance=tolerance) if not h['touch']]
        if not hits:
            return moved
        # jump by most of the reported depth first, then creep
        jump = max(step, hits[0]['depth'] * 0.9) if moved == 0 else step
        target.location += d * jump
        moved += jump
    target.location = start
    return None
