"""eidoblend.fabrication.source_geometry: one-time geometry snapshots for manufacturing (source_geometry.js, MIT).
No source mesh is edited.

    g = source_geometry(source, matrix=None, space='world', visible_only=True, max_triangles=2_000_000)
    g = fit_source_geometry(source, size=0.04, base=0.00065, center=(0, 0))      # or bounds=(min_xyz, max_xyz)

source is any of
    a bpy Object             the object and its children, as evaluated now: modifiers, the armature's current pose
                             and shape keys (the skinned / morph pose), Geometry Nodes and collection instances. Each
                             part is placed by its world matrix (space='world') or relative to the given root
                             (space='local'); hidden objects (viewport or render) and their subtrees are left out unless
                             visible_only=False
    a bpy Collection         its objects (and nested collections), as above
    a bpy Mesh               the datablock's own coordinates (a BufferGeometry: no placement)
    a three_geometry.Geom    (three's axes, converted), or a (vertices, triangles) pair in Blender's axes
    a SourceGeometry         copied
matrix (a 4x4, Blender's axes) is applied after the placement. A reflected placement flips the triangle winding so
the snapshot's surface still faces out. Degenerate triangles are skipped and counted.

The snapshot is planning data in double precision (Blender's axes, metres): g.triangles (N, 3, 3), g.bounding_box
(min, max), and g.manufacturing_source = {triangles, ranges [{name, instance, first_triangle, triangles}],
skipped_degenerate, space, fit}. ranges keep each mesh's triangles apart so the slicer can union overlapping solids.
fit_source_geometry scales uniformly so the largest extent is `size`, centres X/Y on `center` and puts the lowest
point at height `base` (or fits inside `bounds`, centred), and records the fit {scale, offset, bounds}.
"""

from __future__ import annotations

import math

import numpy as np


class SourceGeometry:
    def __init__(self, triangles, ranges, skipped_degenerate=0, space='world'):
        self.triangles = np.ascontiguousarray(triangles, dtype=np.float64).reshape(-1, 3, 3)
        self.manufacturing_source = {'triangles': len(self.triangles), 'ranges': ranges,
                                     'skipped_degenerate': skipped_degenerate, 'space': space}
        self.compute_bounding_box()

    def compute_bounding_box(self):
        p = self.triangles.reshape(-1, 3)
        self.bounding_box = (p.min(axis=0), p.max(axis=0))
        return self.bounding_box

    def apply_matrix(self, m):
        m = np.asarray(m, dtype=np.float64)
        q = self.triangles.reshape(-1, 3)
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        p = np.stack([m[0, 0] * x + m[0, 1] * y + m[0, 2] * z + m[0, 3], m[1, 0] * x + m[1, 1] * y + m[1, 2] * z + m[1, 3],
                      m[2, 0] * x + m[2, 1] * y + m[2, 2] * z + m[2, 3]], axis=1)
        self.triangles = p.reshape(-1, 3, 3)
        if np.linalg.det(m[:3, :3]) < 0:
            self.triangles = self.triangles[:, [0, 2, 1]]
        self.compute_bounding_box()
        return self

    def copy(self):
        g = SourceGeometry(self.triangles.copy(), [dict(r) for r in self.manufacturing_source['ranges']],
                           self.manufacturing_source['skipped_degenerate'], self.manufacturing_source['space'])
        if 'fit' in self.manufacturing_source:
            g.manufacturing_source['fit'] = dict(self.manufacturing_source['fit'])
        return g

    def size(self):
        lo, hi = self.bounding_box
        return hi - lo

    def dispose(self):
        self.triangles = np.zeros((0, 3, 3))


def _mesh_arrays(me):
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('co', v)
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get('vertices', t)
    return v.reshape(-1, 3).astype(np.float64), t.reshape(-1, 3)


def _hidden(ob):
    try:
        hidden_view = ob.hide_get()
    except RuntimeError:                       # not in the view layer
        hidden_view = ob.hide_viewport
    return ob.hide_render or ob.hide_viewport or hidden_view


class _Collector:
    def __init__(self, after, max_triangles):
        self.after = after
        self.max = max_triangles
        self.chunks = []
        self.count = 0
        self.ranges = []
        self.skipped = 0

    def append(self, verts, tris, transform, name, instance=None, flip=None):
        if verts.ndim != 2 or verts.shape[1] != 3:
            raise ValueError('Source mesh has no three-dimensional position attribute')
        if len(tris) == 0:
            return
        if tris.min() < 0 or tris.max() >= len(verts):
            raise ValueError('Source has an invalid triangle index')
        m = np.asarray(transform, dtype=np.float64)
        p = verts if np.array_equal(m, np.eye(4)) else verts @ m[:3, :3].T + m[:3, 3]
        if not np.isfinite(p).all():
            raise ValueError('Source contains a non-finite vertex')
        t = p[tris]
        area = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        keep = (area * area).sum(axis=1) != 0
        self.skipped += int((~keep).sum())
        t = t[keep]
        if not len(t):
            return
        if self.count + len(t) > self.max:
            raise ValueError('Source exceeds the configured manufacturing triangle budget')
        if (np.linalg.det(m[:3, :3]) < 0) if flip is None else flip:
            t = t[:, [0, 2, 1]]
        self.ranges.append({'name': name, 'instance': instance, 'first_triangle': self.count, 'triangles': len(t)})
        self.chunks.append(t)
        self.count += len(t)


def source_geometry(source, matrix=None, space='world', visible_only=True, max_triangles=2000000):
    if not (isinstance(max_triangles, int) and max_triangles >= 1):
        raise ValueError('Manufacturing triangle budget must be a positive integer')
    if space not in ('world', 'local'):
        raise ValueError('Geometry space must be world or local')
    after = np.eye(4) if matrix is None else np.array([list(r) for r in matrix], dtype=np.float64)
    if after.shape != (4, 4):
        raise ValueError('Source matrix must be a 4x4 matrix')
    if isinstance(source, SourceGeometry):
        g = source.copy()
        return g.apply_matrix(after) if matrix is not None else g
    col = _Collector(after, max_triangles)
    from .three_geometry import Geom, Parts
    if isinstance(source, Geom):
        col.append(source.blender_positions().astype(np.float64), source.indices, after, source.name or 'geometry')
    elif isinstance(source, Parts):
        # an Object3D hierarchy as (geometry, world matrix) parts in three's axes and three's own double-precision
        # arithmetic, so a snapshot matches the WebGPU one bit for bit (Blender objects store placements in floats)
        from ._axes import t2b_np
        from .three_geometry import three_apply, three_multiply
        inv = np.linalg.inv(source.root_matrix) if space == 'local' else None
        for geom, mw, name, instance in source.parts:
            m = three_multiply(inv, mw) if inv is not None else mw
            p = t2b_np(three_apply(m, geom.positions.astype(np.float64)))
            if matrix is not None:
                p = p @ after[:3, :3].T + after[:3, 3]
            col.append(p, geom.indices, np.eye(4), name, instance,
                       flip=(np.linalg.det(m[:3, :3]) < 0) != (np.linalg.det(after[:3, :3]) < 0))
    elif isinstance(source, (tuple, list)) and len(source) == 2 and not hasattr(source[0], 'type'):
        col.append(np.asarray(source[0], dtype=np.float64).reshape(-1, 3), np.asarray(source[1]).reshape(-1, 3), after,
                   'geometry')
    else:
        import bpy
        if isinstance(source, bpy.types.Mesh):
            v, t = _mesh_arrays(source)
            col.append(v, t, after, source.name)
        elif isinstance(source, (bpy.types.Object, bpy.types.Collection)):
            _collect_objects(source, col, after, space, visible_only)
        else:
            raise TypeError('Supply a Mesh, an Object (with its children), a Collection or a Geom')
    if not col.count:
        raise ValueError('Source contains no visible non-degenerate triangles')
    return SourceGeometry(np.concatenate(col.chunks), col.ranges, col.skipped, space)


def _collect_objects(source, col, after, space, visible_only):
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    if isinstance(source, bpy.types.Collection):
        roots = [o for o in source.all_objects if o.parent is None or o.parent.name not in source.all_objects]
        root_inv = np.eye(4)
    else:
        roots = [source]
        root_inv = np.eye(4)
        if space == 'local':
            root_inv = np.linalg.inv(np.array([list(r) for r in source.evaluated_get(dg).matrix_world], dtype=np.float64))
    pre = after @ root_inv
    # instances (Geometry Nodes, particles, collection instances) by their instancer
    instances = {}
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        ob = inst.object
        if ob.type not in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
            continue
        try:
            me = ob.to_mesh()
        except RuntimeError:
            continue
        if me is None:
            continue
        v, t = _mesh_arrays(me)
        ob.to_mesh_clear()
        key = inst.parent.original.name
        instances.setdefault(key, []).append((v, t, np.array([list(r) for r in inst.matrix_world], dtype=np.float64),
                                              ob.original.name, len(instances.get(key, []))))

    def visit(o):
        if visible_only and _hidden(o):
            return
        if o.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            if me is not None:
                v, t = _mesh_arrays(me)
                oe.to_mesh_clear()
                mw = np.array([list(r) for r in oe.matrix_world], dtype=np.float64)
                col.append(v, t, pre @ mw, o.name)
        for v, t, mw, name, k in instances.get(o.name, []):
            col.append(v, t, pre @ mw, o.name, k)
        for child in sorted(o.children, key=lambda c: c.name):
            visit(child)

    for r in roots:
        visit(r)


def fit_source_geometry(source, bounds=None, size=None, base=0.0, center=(0.0, 0.0), **snapshot):
    g = source_geometry(source, **snapshot)
    lo, hi = g.bounding_box
    extent = hi - lo
    if bounds is not None:
        bmin, bmax = np.asarray(bounds[0], dtype=np.float64), np.asarray(bounds[1], dtype=np.float64)
        if not (bmax >= bmin).all() or (bmax == bmin).all():
            raise ValueError('Fit bounds must be a nonempty box (min, max)')
        span = bmax - bmin
        factor = min(span[k] / extent[k] if extent[k] > 0 else math.inf for k in range(3))
        offset = (bmin + bmax) / 2 - (lo + hi) / 2 * factor
    else:
        if not (isinstance(size, (int, float)) and math.isfinite(size) and size > 0):
            raise ValueError('Fit size must be positive')
        factor = size / max(extent)
        offset = np.array([center[0], center[1], base]) - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]) * factor
    if not (factor > 0 and math.isfinite(factor)) or not np.isfinite(offset).all():
        raise ValueError('Invalid source fit')
    m = np.diag([factor, factor, factor, 1.0])
    m[:3, 3] = offset
    g.apply_matrix(m)
    g.manufacturing_source['fit'] = {'scale': factor, 'offset': offset.tolist(),
                                     'bounds': [g.bounding_box[0].tolist(), g.bounding_box[1].tolist()]}
    return g
