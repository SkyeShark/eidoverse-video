"""eidoblend.fabrication.three_geometry: three.js r184 primitive geometries, vertex for vertex, as Blender meshes.

A WebGPU scene hands the fabrication planners ordinary three geometries (a LatheGeometry sleeve, a TorusKnot ring, an
extruded bracket). The planners slice and sample real triangles, so a port that wants the same toolpath needs the same
tessellation: these builders reproduce three's vertex order, index order and float32 positions, in three's axes, and
convert to Blender's (x, -z, y) when they become a mesh.

    g = box(1, 1, 1); cylinder(.012, .010, .080, 40, 6); capsule(.005, .030, 6, 20); lathe(points, 48)
    torus_knot(.018, .0045, 128, 16, 2, 3); plane(.02, .02)
    extrude(shape(outline, holes=[circle_hole(cx, cy, r, clockwise=True)]), depth=.012, curve_segments=24)
    g.rotate_x(-pi / 2)                       # BufferGeometry.rotateX, in three's axes
    me = g.to_mesh('name')                    # a bpy Mesh in Blender's axes
    ob = make_object('name', g, position=(x, y, z), rotation=(rx, ry, rz), scale=(sx, sy, sz), parent=None)
                                              # an Object3D placement given in three's terms (Euler XYZ, radians)

ExtrudeGeometry's lids are filled with Blender's polygon tessellator instead of earcut: the lids lie in the extrusion's
end planes, so every slice and every ray from above meets the same side walls and the same lid planes.
"""

from __future__ import annotations

import math

import numpy as np

from ._axes import C3, t2b_np


class Geom:
    """positions (V, 3) float32 in three's axes and triangle indices (T, 3); `name` like BufferGeometry.name."""

    def __init__(self, positions, indices=None, name=''):
        self.positions = np.asarray(positions, dtype=np.float32).reshape(-1, 3)
        if indices is None:
            indices = np.arange(len(self.positions)).reshape(-1, 3)
        self.indices = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
        self.name = name

    def copy(self):
        return Geom(self.positions.copy(), self.indices.copy(), self.name)

    def apply_matrix3(self, m):
        p = self.positions.astype(np.float64) @ np.asarray(m, dtype=np.float64).T
        self.positions = p.astype(np.float32)
        return self

    def rotate_x(self, a):
        c, s = math.cos(a), math.sin(a)
        return self.apply_matrix3([[1, 0, 0], [0, c, -s], [0, s, c]])

    def rotate_y(self, a):
        c, s = math.cos(a), math.sin(a)
        return self.apply_matrix3([[c, 0, s], [0, 1, 0], [-s, 0, c]])

    def rotate_z(self, a):
        c, s = math.cos(a), math.sin(a)
        return self.apply_matrix3([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    def translate(self, x, y, z):
        self.positions = (self.positions.astype(np.float64) + (x, y, z)).astype(np.float32)
        return self

    def blender_positions(self):
        return t2b_np(self.positions.astype(np.float64)).astype(np.float32)

    def triangles_blender(self):
        """(T, 3, 3) float64 triangles in Blender's axes."""
        return self.blender_positions().astype(np.float64)[self.indices]

    def to_mesh(self, name=None):
        import bpy
        me = bpy.data.meshes.new(name or self.name or 'geometry')
        v = self.blender_positions()
        me.vertices.add(len(v))
        me.vertices.foreach_set('co', v.ravel())
        n = len(self.indices)
        me.loops.add(n * 3)
        me.loops.foreach_set('vertex_index', self.indices.astype(np.int32).ravel())
        me.polygons.add(n)
        me.polygons.foreach_set('loop_start', np.arange(0, n * 3, 3, dtype=np.int32))
        me.update(calc_edges=True)
        return me


def euler_xyz_matrix(rx, ry, rz):
    """three's Euler 'XYZ' as a 3x3 (three's axes): R = Rx * Ry * Rz applied to column vectors."""
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    rx_ = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry_ = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz_ = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rx_ @ ry_ @ rz_


def three_trs(position=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    """An Object3D's local matrix (position, Euler XYZ rotation, scale; three's axes) as the same placement in
    Blender's axes: a 4x4 numpy matrix C (T R S) C^-1."""
    m = np.eye(4)
    m[:3, :3] = euler_xyz_matrix(*rotation) @ np.diag(scale)
    m[:3, 3] = position
    c = np.eye(4)
    c[:3, :3] = C3
    return c @ m @ c.T


def three_compose(position=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    """Object3D.matrix in three's axes with three's own arithmetic: Euler XYZ -> quaternion -> Matrix4.compose
    (rows of a 4x4 numpy array)."""
    x, y, z = rotation
    c1, c2, c3 = math.cos(x / 2), math.cos(y / 2), math.cos(z / 2)
    s1, s2, s3 = math.sin(x / 2), math.sin(y / 2), math.sin(z / 2)
    qx = s1 * c2 * c3 + c1 * s2 * s3
    qy = c1 * s2 * c3 - s1 * c2 * s3
    qz = c1 * c2 * s3 + s1 * s2 * c3
    qw = c1 * c2 * c3 - s1 * s2 * s3
    x2, y2, z2 = qx + qx, qy + qy, qz + qz
    xx, xy, xz = qx * x2, qx * y2, qx * z2
    yy, yz, zz = qy * y2, qy * z2, qz * z2
    wx, wy, wz = qw * x2, qw * y2, qw * z2
    sx, sy, sz = scale
    return np.array([[(1 - (yy + zz)) * sx, (xy - wz) * sy, (xz + wy) * sz, position[0]],
                     [(xy + wz) * sx, (1 - (xx + zz)) * sy, (yz - wx) * sz, position[1]],
                     [(xz - wy) * sx, (yz + wx) * sy, (1 - (xx + yy)) * sz, position[2]],
                     [0.0, 0.0, 0.0, 1.0]])


def three_multiply(a, b):
    """Matrix4.multiplyMatrices(a, b), each entry summed in three's order."""
    out = np.zeros((4, 4))
    for r in range(4):
        for c in range(4):
            out[r, c] = a[r, 0] * b[0, c] + a[r, 1] * b[1, c] + a[r, 2] * b[2, c] + a[r, 3] * b[3, c]
    return out


def three_apply(m, p):
    """Vector3.applyMatrix4 over an (n, 3) array in three's axes, in three's order of operations."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    w = 1 / (m[3, 0] * x + m[3, 1] * y + m[3, 2] * z + m[3, 3])
    return np.stack([(m[0, 0] * x + m[0, 1] * y + m[0, 2] * z + m[0, 3]) * w,
                     (m[1, 0] * x + m[1, 1] * y + m[1, 2] * z + m[1, 3]) * w,
                     (m[2, 0] * x + m[2, 1] * y + m[2, 2] * z + m[2, 3]) * w], axis=1)


class Parts:
    """An Object3D hierarchy for the planners without Blender objects: (geometry, world matrix in three's axes,
    name, instance) parts, composed and applied with three's own double-precision arithmetic (Blender objects keep
    their placement in single precision). node() builds a group:

        root = Parts()
        root.add(cylinder(.012, .010, .080, 40, 6), name='shaft', rotation=(0, 0, pi / 2))
        group = root.node(position=(5, .2, -2)); root.add(g, parent=group, position=...)
    """

    def __init__(self, position=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
        self.root_matrix = three_compose(position, rotation, scale)
        self.parts = []

    def node(self, position=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), parent=None):
        """A group node's world matrix (three's axes) under parent (another node's matrix, or the root)."""
        base = self.root_matrix if parent is None else parent
        return three_multiply(base, three_compose(position, rotation, scale))

    def add(self, geom, name='mesh', position=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), parent=None,
            instances=None):
        m = self.node(position, rotation, scale, parent)
        if instances is None:
            self.parts.append((geom, m, name, None))
        else:
            for k, im in enumerate(instances):
                self.parts.append((geom, three_multiply(m, three_compose(*im) if isinstance(im, tuple) else im), name, k))
        return m


def make_object(name, geom=None, position=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), parent=None,
                collection=None):
    """A Blender object placed as three would place it (an empty when geom is None)."""
    import bpy
    from mathutils import Matrix
    data = geom.to_mesh(name) if isinstance(geom, Geom) else geom
    ob = bpy.data.objects.new(name, data)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix(three_trs(position, rotation, scale).tolist())
    return ob


# ------------------------------------------------------------------------------------------------- primitives ---

def box(width=1.0, height=1.0, depth=1.0, ws=1, hs=1, ds=1):
    verts, idx = [], []
    count = [0]

    def plane(u, v, w, udir, vdir, pw, ph, pd, gx, gy):
        seg_w, seg_h = pw / gx, ph / gy
        wh, hh, dh = pw / 2, ph / 2, pd / 2
        gx1, gy1 = gx + 1, gy + 1
        n0 = count[0]
        for iy in range(gy1):
            y = iy * seg_h - hh
            for ix in range(gx1):
                x = ix * seg_w - wh
                vec = [0.0, 0.0, 0.0]
                vec['xyz'.index(u)] = x * udir
                vec['xyz'.index(v)] = y * vdir
                vec['xyz'.index(w)] = dh
                verts.append(vec)
        for iy in range(gy):
            for ix in range(gx):
                a = n0 + ix + gx1 * iy
                b = n0 + ix + gx1 * (iy + 1)
                c = n0 + (ix + 1) + gx1 * (iy + 1)
                d = n0 + (ix + 1) + gx1 * iy
                idx.extend([(a, b, d), (b, c, d)])
        count[0] += gx1 * gy1

    plane('z', 'y', 'x', -1, -1, depth, height, width, ds, hs)
    plane('z', 'y', 'x', 1, -1, depth, height, -width, ds, hs)
    plane('x', 'z', 'y', 1, 1, width, depth, height, ws, ds)
    plane('x', 'z', 'y', 1, -1, width, depth, -height, ws, ds)
    plane('x', 'y', 'z', 1, -1, width, height, depth, ws, hs)
    plane('x', 'y', 'z', -1, -1, width, height, -depth, ws, hs)
    return Geom(verts, idx, 'BoxGeometry')


def plane(width=1.0, height=1.0, ws=1, hs=1):
    gx, gy = int(ws), int(hs)
    verts, idx = [], []
    for iy in range(gy + 1):
        y = iy * (height / gy) - height / 2
        for ix in range(gx + 1):
            verts.append((ix * (width / gx) - width / 2, -y, 0.0))
    for iy in range(gy):
        for ix in range(gx):
            a = ix + (gx + 1) * iy
            b = ix + (gx + 1) * (iy + 1)
            c = ix + 1 + (gx + 1) * (iy + 1)
            d = ix + 1 + (gx + 1) * iy
            idx.extend([(a, b, d), (b, c, d)])
    return Geom(verts, idx, 'PlaneGeometry')


def cylinder(radius_top=1.0, radius_bottom=1.0, height=1.0, radial=32, height_segments=1, open_ended=False,
             theta_start=0.0, theta_length=2 * math.pi):
    verts, idx, rows = [], [], []
    hh = height / 2
    index = 0
    for y in range(height_segments + 1):
        row = []
        v = y / height_segments
        r = v * (radius_bottom - radius_top) + radius_top
        for x in range(radial + 1):
            th = (x / radial) * theta_length + theta_start
            verts.append((r * math.sin(th), -v * height + hh, r * math.cos(th)))
            row.append(index)
            index += 1
        rows.append(row)
    for x in range(radial):
        for y in range(height_segments):
            a, b, c, d = rows[y][x], rows[y + 1][x], rows[y + 1][x + 1], rows[y][x + 1]
            if radius_top > 0 or y != 0:
                idx.append((a, b, d))
            if radius_bottom > 0 or y != height_segments - 1:
                idx.append((b, c, d))

    def cap(top):
        nonlocal index
        start = index
        r = radius_top if top else radius_bottom
        sign = 1 if top else -1
        for _ in range(radial):
            verts.append((0.0, hh * sign, 0.0))
            index += 1
        end = index
        for x in range(radial + 1):
            th = (x / radial) * theta_length + theta_start
            verts.append((r * math.sin(th), hh * sign, r * math.cos(th)))
            index += 1
        for x in range(radial):
            c, i = start + x, end + x
            idx.append((i, i + 1, c) if top else (i + 1, i, c))

    if not open_ended:
        if radius_top > 0:
            cap(True)
        if radius_bottom > 0:
            cap(False)
    return Geom(verts, idx, 'CylinderGeometry')


def capsule(radius=1.0, height=1.0, cap_segments=4, radial=8, height_segments=1):
    height = max(0.0, height)
    cap_segments = max(1, int(cap_segments))
    radial = max(3, int(radial))
    height_segments = max(1, int(height_segments))
    hh = height / 2
    nv = cap_segments * 2 + height_segments
    per = radial + 1
    verts, idx = [], []
    for iy in range(nv + 1):
        if iy <= cap_segments:
            ang = (iy / cap_segments) * math.pi / 2
            py, pr = -hh - radius * math.cos(ang), radius * math.sin(ang)
        elif iy <= cap_segments + height_segments:
            py, pr = -hh + ((iy - cap_segments) / height_segments) * height, radius
        else:
            ang = ((iy - cap_segments - height_segments) / cap_segments) * math.pi / 2
            py, pr = hh + radius * math.sin(ang), radius * math.cos(ang)
        for ix in range(radial + 1):
            th = ix / radial * math.pi * 2
            verts.append((-pr * math.cos(th), py, pr * math.sin(th)))
        if iy > 0:
            prev = (iy - 1) * per
            for ix in range(radial):
                i1, i2, i3, i4 = prev + ix, prev + ix + 1, iy * per + ix, iy * per + ix + 1
                idx.extend([(i1, i2, i3), (i2, i4, i3)])
    return Geom(verts, idx, 'CapsuleGeometry')


def lathe(points, segments=12, phi_start=0.0, phi_length=2 * math.pi):
    segments = int(segments)
    phi_length = max(0.0, min(2 * math.pi, phi_length))
    inv = 1.0 / segments
    verts, idx = [], []
    n = len(points)
    for i in range(segments + 1):
        phi = phi_start + i * inv * phi_length
        s, c = math.sin(phi), math.cos(phi)
        for p in points:
            verts.append((p[0] * s, p[1], p[0] * c))
    for i in range(segments):
        for j in range(n - 1):
            base = j + i * n
            a, b, c, d = base, base + n, base + n + 1, base + 1
            idx.extend([(a, b, d), (c, d, b)])
    return Geom(verts, idx, 'LatheGeometry')


def torus_knot(radius=1.0, tube=0.4, tubular=64, radial=8, p=2, q=3):
    tubular, radial = int(tubular), int(radial)

    def on_curve(u):
        cu, su = math.cos(u), math.sin(u)
        qu = q / p * u
        cs = math.cos(qu)
        return np.array([radius * (2 + cs) * .5 * cu, radius * (2 + cs) * su * .5, radius * math.sin(qu) * .5])

    verts, idx = [], []
    for i in range(tubular + 1):
        u = i / tubular * p * math.pi * 2
        p1, p2 = on_curve(u), on_curve(u + .01)
        t = p2 - p1
        n = p2 + p1
        b = np.cross(t, n)
        n = np.cross(b, t)
        b = b / np.linalg.norm(b)
        n = n / np.linalg.norm(n)
        for j in range(radial + 1):
            v = j / radial * math.pi * 2
            cx, cy = -tube * math.cos(v), tube * math.sin(v)
            verts.append(tuple(p1 + cx * n + cy * b))
    for j in range(1, tubular + 1):
        for i in range(1, radial + 1):
            a = (radial + 1) * (j - 1) + (i - 1)
            b = (radial + 1) * j + (i - 1)
            c = (radial + 1) * j + i
            d = (radial + 1) * (j - 1) + i
            idx.extend([(a, b, d), (b, c, d)])
    return Geom(verts, idx, 'TorusKnotGeometry')


# ----------------------------------------------------------------------------------------------- extrusions ---

class Shape:
    """A three Shape outline: points from moveTo/lineTo (+ closePath) and hole point lists (already sampled)."""

    def __init__(self, outline, holes=()):
        self.outline = [tuple(map(float, p)) for p in outline]
        self.holes = [list(h) for h in holes]


def shape(outline, holes=()):
    """moveTo(outline[0]); lineTo(each next); closePath(): three's getPoints keeps the closing point (dropped later
    by ExtrudeGeometry's merge of overlapping points, as in three)."""
    pts = [tuple(map(float, p)) for p in outline]
    if pts[-1] != pts[0]:
        pts = pts + [pts[0]]
    return Shape(pts, holes)


def circle_hole(cx, cy, r, start=0.0, end=2 * math.pi, clockwise=False, curve_segments=12):
    """Path.absarc(cx, cy, r, start, end, clockwise).getPoints(curve_segments): an EllipseCurve sampled at
    divisions * 2 = 2 * curve_segments steps, with three's angle wrap and clockwise rule."""
    two_pi = math.pi * 2
    delta = end - start
    same = abs(delta) < 2.220446049250313e-16
    while delta < 0:
        delta += two_pi
    while delta > two_pi:
        delta -= two_pi
    if delta < 2.220446049250313e-16:
        delta = 0.0 if same else two_pi
    if clockwise and not same:
        delta = -two_pi if delta == two_pi else delta - two_pi
    n = curve_segments * 2
    out, last = [], None
    for d in range(n + 1):
        a = start + (d / n) * delta
        p = (cx + r * math.cos(a), cy + r * math.sin(a))
        if last is not None and p == last:
            continue
        out.append(p)
        last = p
    return out


def _area2(pts):
    n = len(pts)
    a = 0.0
    p = n - 1
    for q in range(n):
        a += pts[p][0] * pts[q][1] - pts[q][0] * pts[p][1]
        p = q
    return a * .5


def _merge_overlapping(points):
    th2 = 1e-10 * 1e-10
    i = 1
    prev = points[0]
    while i <= len(points):
        cur_i = i % len(points)
        cur = points[cur_i]
        dx, dy = cur[0] - prev[0], cur[1] - prev[1]
        sc = max(abs(cur[0]), abs(cur[1]), abs(prev[0]), abs(prev[1]))
        if dx * dx + dy * dy <= th2 * sc * sc:
            points.pop(cur_i)
            continue
        prev = cur
        i += 1
    return points


def extrude(shp, depth=1.0, curve_segments=12):
    """ExtrudeGeometry(shape, {depth, bevelEnabled: false, curveSegments}): non-indexed, lids then side walls."""
    from mathutils.geometry import tessellate_polygon
    vertices = list(shp.outline)
    holes = [list(h) for h in shp.holes]
    if not (_area2(vertices) < 0):                      # three makes the outline clockwise, the holes counter-clockwise
        vertices = vertices[::-1]
        holes = [h[::-1] if _area2(h) < 0 else h for h in holes]
    _merge_overlapping(vertices)
    for h in holes:
        _merge_overlapping(h)
    contour = vertices
    allv = contour + [p for h in holes for p in h]
    vlen = len(allv)
    placeholder = [(x, y, 0.0) for x, y in allv] + [(x, y, depth) for x, y in allv]
    loops = [[(x, y, 0.0) for x, y in contour]] + [[(x, y, 0.0) for x, y in h] for h in holes]
    tris = tessellate_polygon(loops)
    out = []
    for a, b, c in tris:                                 # orient the lid triangles: bottom faces -z, top faces +z
        pa, pb, pc = allv[a], allv[b], allv[c]
        z = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        if z > 0:
            a, b, c = a, c, b
        out.extend([placeholder[a], placeholder[b], placeholder[c]])
    for a, b, c in tris:
        pa, pb, pc = allv[a], allv[b], allv[c]
        z = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        if z < 0:
            a, b, c = a, c, b
        out.extend([placeholder[a + vlen], placeholder[b + vlen], placeholder[c + vlen]])

    def sidewalls(cont, off):
        i = len(cont)
        while True:
            i -= 1
            if i < 0:
                break
            j, k = i, (i - 1 if i - 1 >= 0 else len(cont) - 1)
            a, b, c, d = off + j, off + k, off + k + vlen, off + j + vlen
            out.extend([placeholder[a], placeholder[b], placeholder[d], placeholder[b], placeholder[c], placeholder[d]])

    sidewalls(contour, 0)
    off = len(contour)
    for h in holes:
        sidewalls(h, off)
        off += len(h)
    return Geom(out, None, 'ExtrudeGeometry')
