"""Rhombic dodecahedron voxels: the Blender edition of eidoverse/rhombic_dodecahedron.js.

Rhombic dodecahedra are the 12-faced cells of the face-centred cubic (FCC) lattice: they tile space like cubes but
read crystalline. The engine built one cell geometry and an InstancedMesh over FCC lattice points; here the cells are
Geometry Nodes instances of one cell mesh on a point cloud, so a fill of 100k cells stays one light object, and the
engine's documented animation (cells appearing inside a growing sphere) is a node setup driven by the scene time:
a saved .blend plays it with no script.

    from eidoblend.sdf import rhombic_dodecahedron as RD
    crystal = RD.fill_volume_rd(bounds={'x': [-3, 3], 'y': [-3, 3], 'z': [0, 4]}, cell_size=0.5, material=mat)
    orb = RD.fill_sphere_rd(center=(0, 0, 2), radius=3, cell_size=0.4, material=mat)
    vox = RD.voxelize_mesh_rd(mesh=some_object, cell_size=0.3, material=mat)
    crystal.reveal(center=(0, 0, 0), speed=3.0)     # the engine's "expanding sphere reveal" recipe

Coordinates are Blender's (z up). The FCC lattice and the cell are symmetric under the change of axes, so a fill of
the same box gives the engine's lattice point for point. Two of the engine's numbers are kept as they were, though
they disagree with its comments: createRhombicDodecahedron(radius) puts the face centres at radius / sqrt(2), not at
radius, and the fills pass radius = cellSize / 2, so each cell is half the size of the lattice's tiling cell and
stands apart from its neighbours (gaps half a cell wide). That spaced look is what the engine rendered; fill=2.0
closes the gaps into the true space-filling tiling.
"""

from __future__ import annotations

import math

import numpy as np

# 8 "cube" vertices at (+-1, +-1, +-1), 6 "octahedron" vertices at (+-2, 0, 0), (0, +-2, 0), (0, 0, +-2)
CUBE_VERTS = [(1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]
OCT_VERTS = [(2, 0, 0), (-2, 0, 0), (0, 2, 0), (0, -2, 0), (0, 0, 2), (0, 0, -2)]
ALL_VERTS = CUBE_VERTS + OCT_VERTS

# the engine's 12 rhombic faces (oct, cube, oct, cube), cube verts 0-7, oct verts 8-13
FACES = [
    (8, 0, 10, 1), (8, 2, 12, 0), (8, 3, 11, 2), (8, 1, 13, 3),
    (9, 4, 10, 5), (9, 6, 12, 4), (9, 7, 11, 6), (9, 5, 13, 7),
    (10, 0, 12, 4), (10, 5, 13, 1), (11, 2, 12, 6), (11, 7, 13, 3),
]


def rd_geometry(radius=1.0):
    """(verts (14, 3), faces (12, 4) wound outward): the engine's cell at scale radius / 2."""
    s = (radius or 1.0) / 2.0
    v = np.asarray(ALL_VERTS, np.float64) * s
    faces = []
    for a, b, c, d in FACES:
        centre = (v[a] + v[b] + v[c] + v[d]) / 4.0
        # the engine flipped its normal attribute outward and kept the triangle winding; Blender's normal IS the
        # winding's, so each face is wound so that a -> b -> c turns counter-clockwise seen from outside
        wn = np.cross(v[b] - v[a], v[c] - v[a])
        faces.append((a, b, c, d) if np.dot(wn, centre) > 0 else (a, d, c, b))
    return v, np.asarray(faces, np.int32)


def create_rhombic_dodecahedron(radius=1.0, name='rhombic_dodecahedron'):
    """The engine's createRhombicDodecahedron(radius): a 12-quad flat-shaded cell mesh (a bpy Mesh)."""
    import bpy
    v, f = rd_geometry(radius)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v.tolist(), [], f.tolist())
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    return me


def fcc_lattice(bounds, cell_size):
    """The engine's _fccLattice: walk x, y, z from each min to max in cell_size strides (accumulating as the
    engine's floats did), round each to the cubic grid, keep the points whose index sum is even."""
    c = float(cell_size)
    (x0, x1), (y0, y1), (z0, z1) = bounds['x'], bounds['y'], bounds['z']
    pts = []

    def stride(a, b):
        out = []
        v = float(a)
        while v <= b:
            out.append(v)
            v += c
        return out
    xs, ys, zs = stride(x0, x1), stride(y0, y1), stride(z0, z1)
    for x in xs:
        i = _js_round(x / c)
        for y in ys:
            j = _js_round(y / c)
            for z in zs:
                k = _js_round(z / c)
                if (i + j + k) % 2 == 0:
                    pts.append((i * c, j * c, k * c))
    return np.asarray(pts, np.float64).reshape(-1, 3)


def _js_round(v):
    """Math.round: halves go up (toward +inf), unlike Python's banker's rounding."""
    return int(math.floor(v + 0.5))


def fcc_lattice_blender(bounds, cell_size):
    """fcc_lattice for a box given in Blender axes, walked in the engine's axes (x, y = Blender z, z = -Blender y)
    and converted back: the walk's float rounding depends on where each axis starts, so this gives exactly the
    engine's points for the same physical box."""
    bx, by, bz = bounds['x'], bounds['y'], bounds['z']
    three = fcc_lattice({'x': [bx[0], bx[1]], 'y': [bz[0], bz[1]], 'z': [-by[1], -by[0]]}, cell_size)
    return np.stack([three[:, 0], -three[:, 2], three[:, 1]], -1) + 0.0


class RdVoxels:
    """What the fills return (the engine's InstancedMesh): .object (a point cloud mesh whose Geometry Nodes instance
    the cell on every point), .points (N, 3) (the engine's _rdPoints), .cell_size (_rdCellSize), .cell (the cell
    mesh), .material, reveal()."""

    def __init__(self, points, cell_size, material=None, name='rd_voxels', scene=None, fill=1.0):
        import bpy
        pts = np.asarray(points, np.float64).reshape(-1, 3)
        # the engine's float walk can round two strides to one lattice point: two identical cells in one place
        _u, first = np.unique(np.round(pts / max(float(cell_size), 1e-12)).astype(np.int64), axis=0, return_index=True)
        self.points = pts[np.sort(first)]
        self.duplicates_dropped = int(len(pts) - len(self.points))
        self.cell_size = float(cell_size)
        self.scene = scene or bpy.context.scene
        self.cell = create_rhombic_dodecahedron(self.cell_size * 0.5 * float(fill), name=name + '_cell')
        if material is None:
            material = bpy.data.materials.new(name + '_material')
            material.use_nodes = True
        self.material = material
        self.cell.materials.append(material)
        src = bpy.data.objects.new(name + '_cell', self.cell)
        src.hide_render = True
        src.hide_viewport = True
        self.source = src
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(self.points))
        me.vertices.foreach_set('co', self.points.astype(np.float32).ravel())
        me.update()
        at = me.attributes.new('rd_index', 'INT', 'POINT')
        at.data.foreach_set('value', np.arange(len(self.points), dtype=np.int32))
        self.object = bpy.data.objects.new(name, me)
        self.scene.collection.objects.link(self.object)
        self.scene.collection.objects.link(src)
        self._tree = self._instancer(bpy)

    def _instancer(self, bpy):
        tree = bpy.data.node_groups.new(self.object.name + '.rd', 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        N, L = tree.nodes, tree.links
        gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
        oi = N.new('GeometryNodeObjectInfo')
        oi.inputs['Object'].default_value = self.source
        inst = N.new('GeometryNodeInstanceOnPoints')
        L.new(gi.outputs[0], inst.inputs['Points'])
        L.new(oi.outputs['Geometry'], inst.inputs['Instance'])
        self._inst = inst
        self._scale_link = inst.inputs['Scale']
        L.new(inst.outputs[0], go.inputs[0])
        mod = self.object.modifiers.new('rd_cells', 'NODES')
        mod.node_group = tree
        return tree

    def reveal(self, center=(0.0, 0.0, 0.0), speed=3.0, start=0.0, hidden_scale=0.001):
        """The engine's header recipe: a cell shows (scale 1) once its distance from center is under
        (t - start) * speed, t the scene time in seconds; before that it is scaled to hidden_scale. Built in the
        node tree from Scene Time, so the saved file plays it."""
        tree = self._tree
        N, L = tree.nodes, tree.links
        pos = N.new('GeometryNodeInputPosition')
        cen = N.new('FunctionNodeInputVector')
        cen.vector = tuple(float(x) for x in center)
        dist = N.new('ShaderNodeVectorMath')
        dist.operation = 'DISTANCE'
        L.new(pos.outputs[0], dist.inputs[0])
        L.new(cen.outputs[0], dist.inputs[1])
        tm = N.new('GeometryNodeInputSceneTime')
        sub = N.new('ShaderNodeMath')
        sub.operation = 'SUBTRACT'
        L.new(tm.outputs['Seconds'], sub.inputs[0])
        sub.inputs[1].default_value = float(start)
        rad = N.new('ShaderNodeMath')
        rad.operation = 'MULTIPLY'
        L.new(sub.outputs[0], rad.inputs[0])
        rad.inputs[1].default_value = float(speed)
        lt = N.new('ShaderNodeMath')
        lt.operation = 'LESS_THAN'
        L.new(dist.outputs['Value'], lt.inputs[0])
        L.new(rad.outputs[0], lt.inputs[1])
        mix = N.new('ShaderNodeMapRange')
        mix.inputs['From Min'].default_value = 0.0
        mix.inputs['From Max'].default_value = 1.0
        mix.inputs['To Min'].default_value = float(hidden_scale)
        mix.inputs['To Max'].default_value = 1.0
        L.new(lt.outputs[0], mix.inputs['Value'])
        L.new(mix.outputs['Result'], self._scale_link)
        return self


def _make(points, opts, name):
    return RdVoxels(points, opts.get('cell_size', opts.get('cellSize', 0.5)), material=opts.get('material'),
                    name=opts.get('name', name), scene=opts.get('scene'), fill=opts.get('fill', 1.0))


def fill_volume_rd(opts=None, **kw):
    """The engine's fillVolumeRD({bounds: {x, y, z}, cellSize, material}): cells on every FCC point of the box."""
    o = dict(opts or {}, **kw)
    cs = o.get('cell_size', o.get('cellSize', 0.5)) or 0.5
    o['cell_size'] = cs
    return _make(fcc_lattice_blender(o['bounds'], cs), o, 'rd_volume')


def fill_sphere_rd(opts=None, **kw):
    """The engine's fillSphereRD({center, radius, cellSize, material}): the FCC points of the sphere's box that lie
    within radius of center."""
    o = dict(opts or {}, **kw)
    cs = o.get('cell_size', o.get('cellSize', 0.5)) or 0.5
    o['cell_size'] = cs
    c = o.get('center') or (0.0, 0.0, 0.0)
    cx, cy, cz = (float(c[0] or 0), float(c[1] or 0), float(c[2] or 0))
    r = float(o.get('radius') or 3.0)
    pts = fcc_lattice_blender({'x': [cx - r, cx + r], 'y': [cy - r, cy + r], 'z': [cz - r, cz + r]}, cs)
    d2 = ((pts - np.array([cx, cy, cz])) ** 2).sum(axis=1)
    return _make(pts[d2 <= r * r], o, 'rd_sphere')


def voxelize_mesh_rd(opts=None, **kw):
    """The engine's voxelizeMeshRD({mesh, cellSize, material, padding}): the FCC points of the object's world
    bounding box (plus padding) inside the mesh, by ray parity along +z (the engine cast along +y, its up); when
    nothing tests inside (an open mesh), the engine's fallback keeps the points of the box's inscribed ellipsoid
    (squared normalised radius <= 1.1).

    front_faces_only=True counts hits as three's Raycaster did for a single-sided (FrontSide) material: a face hit
    from behind is skipped. Then a ray leaving a closed mesh never counts its exit, no point tests inside, and the
    engine always fell back to the ellipsoid; the default counts every crossing, which is what its documentation
    promised (cells whose centre is inside the mesh)."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    o = dict(opts or {}, **kw)
    cs = o.get('cell_size', o.get('cellSize', 0.3)) or 0.3
    o['cell_size'] = cs
    pad = float(o.get('padding') or 0.0)
    src = o['mesh']
    dg = bpy.context.evaluated_depsgraph_get()
    objs = [src] + [c for c in src.children_recursive if c.type == 'MESH'] if hasattr(src, 'children_recursive') else [src]
    vs, tris = [], []
    base = 0
    for ob in objs:
        if ob.type != 'MESH':
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        me.calc_loop_triangles()
        co = [mw @ v.co for v in me.vertices]
        vs.extend(co)
        tris.extend([tuple(base + i for i in lt.vertices) for lt in me.loop_triangles])
        base += len(co)
        ev.to_mesh_clear()
    if not vs:
        raise ValueError('voxelize_mesh_rd: the object has no mesh')
    arr = np.array([tuple(v) for v in vs])
    box_lo, box_hi = arr.min(axis=0), arr.max(axis=0)
    lo, hi = box_lo - pad, box_hi + pad
    bvh = BVHTree.FromPolygons(vs, tris)
    pts = fcc_lattice_blender({'x': [lo[0], hi[0]], 'y': [lo[1], hi[1]], 'z': [lo[2], hi[2]]}, cs)
    up = Vector((0.0, 0.0, 1.0))
    front_only = bool(o.get('front_faces_only', False))
    keep = []
    for p in pts:
        origin = Vector(p)
        hits = 0
        guard = 0
        while guard < 256:
            loc, nrm, _i, _d = bvh.ray_cast(origin, up)
            if loc is None:
                break
            if not front_only or nrm.dot(up) < 0.0:
                hits += 1
            origin = loc + up * 1e-5
            guard += 1
        if hits % 2 == 1:
            keep.append(p)
    inside = np.asarray(keep, np.float64).reshape(-1, 3)
    if len(inside) == 0:
        centre = (box_lo + box_hi) * 0.5
        half = (box_hi - box_lo) * 0.5
        half[half == 0] = 1.0
        q = (pts - centre) / half
        inside = pts[(q ** 2).sum(axis=1) <= 1.1]
    return _make(inside, o, 'rd_voxelized')
