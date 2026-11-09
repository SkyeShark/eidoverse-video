"""A terrain's water surfaces (design section 7): flat lake meshes at their levels, a sea grid at sea level, and a
simple water material, dark and glossy, tinted by depth.

    objs = lake_objects(t)                 # one object per level that holds lake water (its ring of the terrain)
    sea = sea_object(t, sea_level)         # None when sea_level is None
    mat = water_material()

Lakes come from each level's `water` field (lake depth in metres; the runner's hydrology fills depressions into it,
real_place carves it under a DEM's lakes). On every level, the wet cells are split into lakes (8-connected); a lake
shallower than min_depth_m everywhere is dropped; each lake is flat at its level (the median of h + water over it,
the spill level) and grown one cell under its shore, so the plane runs into the bank and the waterline is where the
ground rises through it (Ekigar's build_lake_mesh rule, moved). A level draws only the cells of its own ring (outside
its child's window, which lies on its cell grid), so the pieces of one lake on two levels meet edge to edge, at the
same level, without overlapping. Cells at the sea's level are left to the sea grid. Each vertex carries eido_water,
the depth to the rendered ground under it (the material's tint).
"""
from __future__ import annotations

import numpy as np

SEA_TOL_M = 0.05
SEA_GRID = 160              # vertices per side of the sea grid


def _label(mask):
    from ..core.metrics import label
    return label(mask)


def _lake_cells(lv, f, child, min_depth_m, sea_level):
    """[(level_m, cells bool (n, n))] of one level's lakes, each grown one cell, limited to the level's ring."""
    if 'water' not in f:
        return []
    w = np.asarray(f['water'], np.float64)
    h = np.asarray(f['h'], np.float64)
    wet = w > 1e-6
    if not wet.any():
        return []
    labels, n = _label(wet)
    ring = np.ones(wet.shape, bool)
    if child is not None:
        i0 = int(round((child.x0 - lv.x0) / lv.cell))
        j0 = int(round((child.y0 - lv.y0) / lv.cell))
        m = int(round(child.side / lv.cell))
        ring[j0:j0 + m, i0:i0 + m] = False
    out = []
    for k in range(1, n + 1):
        cells = labels == k
        if w[cells].max() < min_depth_m:
            continue
        level = float(np.median(h[cells] + w[cells]))
        if sea_level is not None and abs(level - sea_level) <= SEA_TOL_M:
            continue
        p = np.pad(cells, 1)
        grown = cells.copy()
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                grown |= p[1 + dj:1 + dj + cells.shape[0], 1 + di:1 + di + cells.shape[1]]
        grown &= ring
        if grown.any():
            out.append((level, grown))
    return out


def lake_geometry(lv, lakes):
    """(vertices (V, 3), quads (Q, 4)) of a level's lakes: one quad per cell, CCW from above, corners shared within
    a lake."""
    verts, quads, base = [], [], 0
    n = lv.n
    for level, cells in lakes:
        j, i = np.nonzero(cells)
        corners = np.stack([j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i], 1)
        uniq, inv = np.unique(corners.ravel(), return_inverse=True)
        cj, ci = uniq // (n + 1), uniq % (n + 1)
        v = np.stack([lv.x0 + ci * lv.cell, lv.y0 + cj * lv.cell, np.full(len(uniq), level)], 1)
        verts.append(v)
        quads.append(inv.reshape(-1, 4) + base)
        base += len(uniq)
    if not verts:
        return None, None
    return np.concatenate(verts), np.concatenate(quads)


def _mesh_object(name, verts, quads, depth, collection, mat):
    import bpy
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', np.asarray(verts, np.float32).ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set('vertex_index', np.asarray(quads, np.int32).ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4, dtype=np.int32))
    me.update(calc_edges=True)
    att = me.attributes.new('eido_water', 'FLOAT', 'POINT')
    att.data.foreach_set('value', np.asarray(depth, np.float32))
    me.materials.append(mat)
    obj = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def lake_objects(t, name='terrain_lake', collection=None, min_depth_m=0.5, material=None):
    """The lake objects of a Terrain (module doc): one per level that holds lake water, named <name>_L<level>."""
    plan = t.levels
    sea = t.info.get('sea_level')
    mat = None
    out = []
    for k, (lv, f) in enumerate(zip(plan, [t.fields(i) for i in range(len(plan))])):
        child = plan[k + 1] if k + 1 < len(plan) else None
        lakes = _lake_cells(lv, f, child, min_depth_m, sea)
        if not lakes:
            continue
        verts, quads = lake_geometry(lv, lakes)
        depth = np.maximum(verts[:, 2] - t.height_at(verts[:, 0], verts[:, 1]), 0.0)
        mat = mat or material or water_material(name + '_water')
        out.append(_mesh_object(f'{name}_L{k}', verts, quads, depth, collection, mat))
    return out


def sea_object(t, sea_level, name='terrain_sea', collection=None, material=None, n=SEA_GRID):
    """A sea grid at sea_level over the outermost level (n x n vertices, the depth to the ground as eido_water), or
    None when sea_level is None."""
    if sea_level is None:
        return None
    xmin, ymin, xmax, ymax = t.ring.bounds()
    xs = np.linspace(xmin, xmax, n)
    ys = np.linspace(ymin, ymax, n)
    X, Y = np.meshgrid(xs, ys)
    verts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, float(sea_level))], 1)
    idx = np.arange(n * n).reshape(n, n)
    quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    depth = np.maximum(float(sea_level) - t.height_at(verts[:, 0], verts[:, 1]), 0.0)
    return _mesh_object(name, verts, quads, depth, collection, material or water_material(name + '_water'))


def water_material(name='terrain_water'):
    """Dark glossy water whose colour runs from a green shallow tint to a deep blue-black over 0-12 m of depth
    (eido_water)."""
    import bpy
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.06
    b.inputs['IOR'].default_value = 1.333
    att = nt.nodes.new('ShaderNodeAttribute')
    att.attribute_type = 'GEOMETRY'
    att.attribute_name = 'eido_water'
    att.location = (-700, 200)
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = 12.0
    mr.location = (-450, 200)
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs[6].default_value = (0.055, 0.12, 0.10, 1.0)
    mix.inputs[7].default_value = (0.006, 0.018, 0.028, 1.0)
    mix.location = (-200, 200)
    nt.links.new(att.outputs['Fac'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], mix.inputs[0])
    nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    return mat


__all__ = ['lake_objects', 'sea_object', 'water_material', 'lake_geometry']
