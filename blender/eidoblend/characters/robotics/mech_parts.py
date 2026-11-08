"""eidoblend.characters.robotics.mech_parts: MechParts (the production engine's mech_parts.js), in Blender.

Procedural mechanical part generators: machined housings, castings, cables, treads, wheels, greebles, lights and two
procedural surface treatments. The baked modular kit supersedes the procedural ROBOTS that used to be built from these
(robotics_kit.js's retired presets); the generators themselves have no counterpart in the kit and are ported whole.

Every generator builds its geometry exactly as the original does, in three's axes (BoxGeometry, CylinderGeometry,
SphereGeometry, LatheGeometry and TubeGeometry vertex for vertex, normals included: crisp facets keep their analytic
normals as custom normals, never recomputed), then converts to Blender's (x, -z, y). Points the caller passes and
gets back (cable ends, chain paths) are Blender coordinates.

    MechParts.chamfered_box(w, h, d, chamfer, material) / chamfered_box_geometry(...)      crisp-facet box
    MechParts.motor_housing(r, len, fin_n, ...) / gearbox_bell(...) / joint_hub(...) / lathe(points, segments)
    MechParts.motor_housing_profile / gearbox_bell_profile / joint_hub_profile / tire_profile   the (x, y) profiles
    MechParts.arm_link_casting(length, box_w, box_h, cyl_r, end_w, end_h, ribs, rib_w, rib_depth)  loft shell + ribs
    MechParts.catenary_points(a, b, sag, n, lateral_jitter, seed) / make_cable(a, b, radius, sag, corrugated, seed)
    MechParts.make_e_chain(points, link_len, count) / update_e_chain(chain, points)      instanced cable carrier
    MechParts.make_tread_track(run_len, cap_r, width, plate_n, lug) / scroll_tread(tread, du) / tread_path_point
    MechParts.make_wheel(r, width, hub_r, lug_count, ...) / make_mecanum_wheel(hub_r, roller_count, ...)
    MechParts.vent_grille(w, h, fin_n, ...) / hex_bolts(r, y, n, seed, bolt_r) (geometries) / geometry_object(...)
    MechParts.piston_rod(r, clevis_w, ...) / piston_sleeve(r) / hose_coil(turns, coil_r, len, tube_r)
    MechParts.beacon(r, color, rate) / stack_light(s) -> {object, update(t)}: key_lights(light, frame_start, frame_end)
    MechParts.apply_hazard_stripes(material, freq, angle, color_a, color_b, use_world_pos) / apply_brushed_metal(...)
    MechParts.mulberry(seed), metal(color, rough, met), rubber(color)
    key_tread(tread, u_per_second, frame_start, frame_end) / key_e_chain(chain, points_at(t), ...)   the per-frame
                                    updates (scrollTread, updateEChain, light.update) keyed, so the file plays alone

Instanced parts (the e-chain links, the tread plates) are linked duplicates of one mesh under an empty: Blender's
counterpart of an InstancedMesh, with each instance's matrix a keyable object transform.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ...placement._curves import CatmullRomCurve3, frenet_frames
from .materials import to_linear

_C = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)        # three (x, y, z) -> Blender (x, -z, y)
_C4 = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def _hex(c):
    return to_linear(c if isinstance(c, (str, tuple, list)) else int(c))


# ------------------------------------------------------------------------------------------------ materials
def metal(color=0x9aa0a8, rough=0.4, met=0.8, name='mech metal'):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = tuple(_hex(color)) + (1.0,)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = met
    return m


def rubber(color=0x181818, name='mech rubber'):
    return metal(color, 0.92, 0.05, name)


def mulberry(seed):
    """the deterministic PRNG (mulberry32), bit for bit"""
    a = [(seed & 0xFFFFFFFF) or 1]

    def imul(x, y):
        return ((x & 0xFFFFFFFF) * (y & 0xFFFFFFFF)) & 0xFFFFFFFF

    def rnd():
        a[0] = (a[0] + 0x6D2B79F5) & 0xFFFFFFFF
        t = a[0]
        t = imul(t ^ (t >> 15), 1 | t)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return rnd


# ------------------------------------------------------------------------------------------------ geometry
class Geo:
    """a three BufferGeometry: positions, normals, uvs (V, ...) and triangles (T, 3), in three's axes"""

    def __init__(self, pos, nor, uv, idx):
        self.pos = np.asarray(pos, float).reshape(-1, 3)
        self.nor = np.asarray(nor, float).reshape(-1, 3)
        self.uv = np.asarray(uv, float).reshape(-1, 2)
        self.idx = np.asarray(idx, np.int64).reshape(-1, 3)

    def apply(self, m):
        m = np.asarray(m, float)
        r, t = m[:3, :3], m[:3, 3]
        self.pos = self.pos @ r.T + t
        n = self.nor @ np.linalg.inv(r)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        self.nor = np.where(ln > 0, n / np.maximum(ln, 1e-30), n)
        return self

    def translate(self, x, y, z):
        m = np.eye(4)
        m[:3, 3] = (x, y, z)
        return self.apply(m)

    def _rot(self, axis, a):
        c, s = math.cos(a), math.sin(a)
        m = np.eye(4)
        i, j = {'x': (1, 2), 'y': (2, 0), 'z': (0, 1)}[axis]
        m[i, i], m[i, j], m[j, i], m[j, j] = c, -s, s, c
        return self.apply(m)

    def rotate_x(self, a):
        return self._rot('x', a)

    def rotate_y(self, a):
        return self._rot('y', a)

    def rotate_z(self, a):
        return self._rot('z', a)

    def copy(self):
        return Geo(self.pos.copy(), self.nor.copy(), self.uv.copy(), self.idx.copy())


def merge(geos):
    pos, nor, uv, idx, off = [], [], [], [], 0
    for g in geos:
        pos.append(g.pos)
        nor.append(g.nor)
        uv.append(g.uv)
        idx.append(g.idx + off)
        off += len(g.pos)
    return Geo(np.concatenate(pos), np.concatenate(nor), np.concatenate(uv), np.concatenate(idx))


def box_geometry(w=1.0, h=1.0, d=1.0):
    """three's BoxGeometry (1 segment per side)"""
    pos, nor, uv, idx = [], [], [], []

    def plane(u, v, wax, udir, vdir, width, height, depth):
        n0 = len(pos)
        for iy in range(2):
            y = iy * height - height / 2
            for ix in range(2):
                x = ix * width - width / 2
                p = [0.0, 0.0, 0.0]
                p['xyz'.index(u)] = x * udir
                p['xyz'.index(v)] = y * vdir
                p['xyz'.index(wax)] = depth / 2
                pos.append(p)
                n = [0.0, 0.0, 0.0]
                n['xyz'.index(wax)] = 1.0 if depth > 0 else -1.0
                nor.append(n)
                uv.append((ix, 1 - iy))
        a, b, c, dd = n0, n0 + 2, n0 + 3, n0 + 1
        idx.extend([(a, b, dd), (b, c, dd)])
    plane('z', 'y', 'x', -1, -1, d, h, w)
    plane('z', 'y', 'x', 1, -1, d, h, -w)
    plane('x', 'z', 'y', 1, 1, w, d, h)
    plane('x', 'z', 'y', 1, -1, w, d, -h)
    plane('x', 'y', 'z', 1, -1, w, h, d)
    plane('x', 'y', 'z', -1, -1, w, h, -d)
    return Geo(pos, nor, uv, idx)


def cylinder_geometry(rt=1.0, rb=1.0, height=1.0, radial=32, hseg=1, open_ended=False):
    """three's CylinderGeometry"""
    pos, nor, uv, idx = [], [], [], []
    half = height / 2
    slope = (rb - rt) / height
    grid = []
    for y in range(hseg + 1):
        row = []
        v = y / hseg
        radius = v * (rb - rt) + rt
        for x in range(radial + 1):
            u = x / radial
            th = u * 2 * math.pi
            s, c = math.sin(th), math.cos(th)
            pos.append((radius * s, -v * height + half, radius * c))
            n = np.array((s, slope, c))
            nor.append(n / np.linalg.norm(n))
            uv.append((u, 1 - v))
            row.append(len(pos) - 1)
        grid.append(row)
    for x in range(radial):
        for y in range(hseg):
            a, b, c, d = grid[y][x], grid[y + 1][x], grid[y + 1][x + 1], grid[y][x + 1]
            if rt > 0 or y != 0:
                idx.append((a, b, d))
            if rb > 0 or y != hseg - 1:
                idx.append((b, c, d))
    if not open_ended:
        for top in (True, False):
            radius = rt if top else rb
            if radius <= 0:
                continue
            sign = 1 if top else -1
            c0 = len(pos)
            for x in range(1, radial + 1):
                pos.append((0, half * sign, 0))
                nor.append((0, sign, 0))
                uv.append((0.5, 0.5))
            e0 = len(pos)
            for x in range(radial + 1):
                u = x / radial
                th = u * 2 * math.pi
                c, s = math.cos(th), math.sin(th)
                pos.append((radius * s, half * sign, radius * c))
                nor.append((0, sign, 0))
                uv.append((c * 0.5 + 0.5, s * 0.5 * sign + 0.5))
            for x in range(radial):
                ci, i = c0 + x, e0 + x
                idx.append((i, i + 1, ci) if top else (i + 1, i, ci))
    return Geo(pos, nor, uv, idx)


def sphere_geometry(radius=1.0, wseg=32, hseg=16):
    """three's SphereGeometry"""
    pos, nor, uv, idx = [], [], [], []
    grid = []
    for iy in range(hseg + 1):
        v = iy / hseg
        uoff = 0.5 / wseg if iy == 0 else (-0.5 / wseg if iy == hseg else 0.0)
        row = []
        for ix in range(wseg + 1):
            u = ix / wseg
            p = (-radius * math.cos(u * 2 * math.pi) * math.sin(v * math.pi), radius * math.cos(v * math.pi),
                 radius * math.sin(u * 2 * math.pi) * math.sin(v * math.pi))
            pos.append(p)
            n = np.array(p)
            nor.append(n / (np.linalg.norm(n) or 1))
            uv.append((u + uoff, 1 - v))
            row.append(len(pos) - 1)
        grid.append(row)
    for iy in range(hseg):
        for ix in range(wseg):
            a, b, c, d = grid[iy][ix + 1], grid[iy][ix], grid[iy + 1][ix], grid[iy + 1][ix + 1]
            if iy != 0:
                idx.append((a, b, d))
            if iy != hseg - 1:
                idx.append((b, c, d))
    return Geo(pos, nor, uv, idx)


def lathe_geometry(points, segments=12):
    """three's LatheGeometry: the profile (x = radius, y = height) turned about +Y; a duplicated profile point makes a
    crisp edge (the zero-length segment between the two copies splits the normal)"""
    pts = [(float(x), float(y)) for x, y in points]
    init = []
    prev = None
    for j in range(len(pts)):
        if j == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
            n = np.array((dy, -dx, 0.0))
            prev = n.copy()
            init.append(n / (np.linalg.norm(n) or 1))
        elif j == len(pts) - 1:
            init.append(prev.copy())
        else:
            dx, dy = pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]
            cur = np.array((dy, -dx, 0.0))
            n = cur + prev
            init.append(n / (np.linalg.norm(n) or 1))
            prev = cur
    pos, nor, uv, idx = [], [], [], []
    for i in range(segments + 1):
        phi = i / segments * 2 * math.pi
        s, c = math.sin(phi), math.cos(phi)
        for j, (x, y) in enumerate(pts):
            pos.append((x * s, y, x * c))
            uv.append((i / segments, j / (len(pts) - 1)))
            nor.append((init[j][0] * s, init[j][1], init[j][0] * c))
    m = len(pts)
    for i in range(segments):
        for j in range(m - 1):
            base = j + i * m
            a, b, c, d = base, base + m, base + m + 1, base + 1
            idx.extend([(a, b, d), (c, d, b)])
    return Geo(pos, nor, uv, idx)


def tube_geometry(curve, tubular=64, radius=1.0, radial=8):
    """three's TubeGeometry along a CatmullRomCurve3 given in three's axes"""
    _t, N, B = frenet_frames(curve, tubular, False)
    pos, nor, uv, idx = [], [], [], []
    for i in range(tubular + 1):
        P = curve.get_point_at(i / tubular)
        n0, b0 = N[i], B[i]
        for j in range(radial + 1):
            v = j / radial * 2 * math.pi
            s, c = math.sin(v), -math.cos(v)
            n = np.array((c * n0[0] + s * b0[0], c * n0[1] + s * b0[1], c * n0[2] + s * b0[2]))
            n /= np.linalg.norm(n) or 1
            pos.append((P[0] + radius * n[0], P[1] + radius * n[1], P[2] + radius * n[2]))
            nor.append(n)
            uv.append((i / tubular, j / radial))
    for j in range(1, tubular + 1):
        for i in range(1, radial + 1):
            a = (radial + 1) * (j - 1) + (i - 1)
            b = (radial + 1) * j + (i - 1)
            c = (radial + 1) * j + i
            d = (radial + 1) * (j - 1) + i
            idx.extend([(a, b, d), (b, c, d)])
    return Geo(pos, nor, uv, idx)


def to_mesh(name, geo):
    """the geometry as a Blender mesh in Blender's axes, its normals as custom normals"""
    pos = geo.pos @ _C.T
    nor = geo.nor @ _C.T
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pos))
    me.vertices.foreach_set('co', pos.astype(np.float32).ravel())
    nt = len(geo.idx)
    me.loops.add(nt * 3)
    me.loops.foreach_set('vertex_index', geo.idx.astype(np.int32).ravel())
    me.polygons.add(nt)
    me.polygons.foreach_set('loop_start', (np.arange(nt) * 3).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.full(nt, 3, np.int32))
    me.update(calc_edges=True)
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', geo.uv[geo.idx.ravel()].astype(np.float32).ravel())
    me.polygons.foreach_set('use_smooth', np.ones(nt, bool))
    me.normals_split_custom_set(nor[geo.idx.ravel()].tolist())
    return me


def geometry_object(name, geo, material=None, parent=None, collection=None):
    me = to_mesh(name, geo)
    if material is not None:
        me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def _place(ob, position=(0, 0, 0), rot_three=None):
    """an Object3D placement in three's terms (position, Euler XYZ) on a Blender object"""
    m = Matrix.Translation(position)
    if rot_three is not None:                       # three's Euler XYZ: Rx * Ry * Rz
        rx, ry, rz = rot_three
        m = m @ Matrix.Rotation(rx, 4, 'X') @ Matrix.Rotation(ry, 4, 'Y') @ Matrix.Rotation(rz, 4, 'Z')
    ob.matrix_basis = _C4 @ m @ _C4.inverted()


# ------------------------------------------------------------------------------------------------ chamferedBox
def chamfered_box_geometry(w, h, d, chamfer):
    """6 inset faces + 12 edge bevels + 8 corner triangles with ANALYTIC normals; planar UVs from the dominant axis"""
    X, Y, Z = w / 2, h / 2, d / 2
    c = min(chamfer, X, Y, Z) * 0.999
    X2, Y2, Z2 = X - c, Y - c, Z - c
    pos, nor, uv, idx = [], [], [], []
    inv = 1 / max(w, h, d)

    def uv_of(p, n):
        ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
        if ax >= ay and ax >= az:
            return (p[2] * inv + 0.5, p[1] * inv + 0.5)
        if ay >= az:
            return (p[0] * inv + 0.5, p[2] * inv + 0.5)
        return (p[0] * inv + 0.5, p[1] * inv + 0.5)

    def emit(pts, n):
        e1 = np.subtract(pts[1], pts[0])
        e2 = np.subtract(pts[2], pts[1])
        if np.dot(np.cross(e1, e2), n) < 0:
            pts = pts[::-1]
        v0 = len(pos)
        for p in pts:
            pos.append(p)
            nor.append(n)
            uv.append(uv_of(p, n))
        for i in range(1, len(pts) - 1):
            idx.append((v0, v0 + i, v0 + i + 1))
    for sx in (1, -1):
        emit([(sx * X, -Y2, -Z2), (sx * X, Y2, -Z2), (sx * X, Y2, Z2), (sx * X, -Y2, Z2)], (sx, 0, 0))
    for sy in (1, -1):
        emit([(-X2, sy * Y, -Z2), (X2, sy * Y, -Z2), (X2, sy * Y, Z2), (-X2, sy * Y, Z2)], (0, sy, 0))
    for sz in (1, -1):
        emit([(-X2, -Y2, sz * Z), (X2, -Y2, sz * Z), (X2, Y2, sz * Z), (-X2, Y2, sz * Z)], (0, 0, sz))
    s2, s3 = 1 / math.sqrt(2), 1 / math.sqrt(3)
    for sx in (1, -1):
        for sy in (1, -1):
            emit([(sx * X, sy * Y2, -Z2), (sx * X2, sy * Y, -Z2), (sx * X2, sy * Y, Z2), (sx * X, sy * Y2, Z2)],
                 (sx * s2, sy * s2, 0))
    for sy in (1, -1):
        for sz in (1, -1):
            emit([(-X2, sy * Y, sz * Z2), (-X2, sy * Y2, sz * Z), (X2, sy * Y2, sz * Z), (X2, sy * Y, sz * Z2)],
                 (0, sy * s2, sz * s2))
    for sx in (1, -1):
        for sz in (1, -1):
            emit([(sx * X2, -Y2, sz * Z), (sx * X, -Y2, sz * Z2), (sx * X, Y2, sz * Z2), (sx * X2, Y2, sz * Z)],
                 (sx * s2, 0, sz * s2))
    for sx in (1, -1):
        for sy in (1, -1):
            for sz in (1, -1):
                emit([(sx * X, sy * Y2, sz * Z2), (sx * X2, sy * Y, sz * Z2), (sx * X2, sy * Y2, sz * Z)],
                     (sx * s3, sy * s3, sz * s3))
    return Geo(pos, nor, uv, idx)


def chamfered_box(w, h, d, chamfer, material=None, name='chamfered box'):
    return geometry_object(name, chamfered_box_geometry(w, h, d, chamfer), material or metal())


# ------------------------------------------------------------------------------------------------ lathe housings
def _v2(pts):
    return [(max(x, 0.0), y) for x, y in pts]


def motor_housing_profile(r=0.14, len=0.5, fin_n=10, fin_r=None, shaft_r=0.05, cap_r=0.03):  # noqa: A002
    fin_r = r * 0.14 if fin_r is None else fin_r
    L = len
    pts = [(0, L / 2 + cap_r), (cap_r * 0.8, L / 2 + cap_r * 0.3), (r * 0.9, L / 2), (r * 0.9, L / 2), (r, L / 2)]
    pitch = (L * 0.62) / fin_n
    y = L / 2 - L * 0.04
    for _ in range(fin_n):
        pts += [(r, y), (r, y), (r + fin_r, y - pitch * 0.15), (r + fin_r, y - pitch * 0.5),
                (r, y - pitch * 0.85), (r, y - pitch * 0.85)]
        y -= pitch
    pts += [(r, -L / 2), (r, -L / 2), (shaft_r * 2.2, -L / 2), (shaft_r * 2.2, -L / 2), (shaft_r, -L / 2 - 0.02),
            (0, -L / 2 - 0.02)]
    return _v2(pts)


def gearbox_bell_profile(in_r=0.05, bell_r=0.16, bell_len=0.22, flange_r=0.2, flange_t=0.02):
    bl = bell_len
    return _v2([(0, bl * 0.5 + 0.01), (in_r * 1.4, bl * 0.5), (in_r * 1.4, bl * 0.5), (in_r * 2.2, bl * 0.42),
                (bell_r * 0.55, bl * 0.15), (bell_r * 0.85, -bl * 0.1), (bell_r, -bl * 0.35), (bell_r, -bl * 0.35),
                (flange_r, -bl * 0.35), (flange_r, -bl * 0.35 - flange_t), (flange_r, -bl * 0.35 - flange_t),
                (bell_r * 0.4, -bl * 0.35 - flange_t), (0, -bl * 0.35 - flange_t - 0.01)])


def joint_hub_profile(shaft_r=0.045, hub_r=0.1, flange_r=0.14, flange_t=0.018, hub_len=0.12):
    hl = hub_len
    return _v2([(0, hl / 2), (shaft_r, hl / 2 - 0.01), (hub_r * 0.7, hl / 2 - 0.03), (hub_r, hl * 0.1),
                (hub_r, hl * 0.1), (flange_r, hl * 0.1), (flange_r, hl * 0.1 - flange_t),
                (flange_r, hl * 0.1 - flange_t), (hub_r * 0.85, hl * 0.1 - flange_t), (hub_r * 0.6, -hl / 2 + 0.02),
                (shaft_r, -hl / 2), (0, -hl / 2)])


def tire_profile(r, width, hub_r):
    hw = width / 2
    return _v2([(0, hw * 0.6), (hub_r, hw * 0.6), (hub_r, hw * 0.6), (hub_r * 1.3, hw * 0.55), (r * 0.9, hw * 0.5),
                (r, hw * 0.15), (r, -hw * 0.15), (r * 0.9, -hw * 0.5), (hub_r * 1.3, -hw * 0.55), (hub_r, -hw * 0.6),
                (hub_r, -hw * 0.6), (0, -hw * 0.6)])


def lathe(points, segments=24, material=None, name='lathe'):
    return geometry_object(name, lathe_geometry(points, segments), material or metal())


def motor_housing(segments=24, material=None, **o):
    return lathe(motor_housing_profile(**o), segments, material, 'motor housing')


def gearbox_bell(segments=24, material=None, **o):
    return lathe(gearbox_bell_profile(**o), segments, material, 'gearbox bell')


def joint_hub(segments=24, material=None, **o):
    return lathe(joint_hub_profile(**o), segments, material, 'joint hub')


# ------------------------------------------------------------------------------------------------ arm link casting
def arm_link_casting(length=0.6, box_w=0.14, box_h=0.16, cyl_r=0.075, end_w=None, end_h=None, ribs=4, rib_w=0.012,
                     rib_depth=0.012, material=None, name='arm link casting'):
    """a lofted box -> cylinder (or tapered box) shell along three's +Z with up to four longitudinal ribs near the
    box end (the terrain family's Loft.sweep makes the shell, as Loft does there)"""
    from ...terrain import loft
    material = material or metal()
    path = [tuple(_C @ np.array(p)) for p in ((0, 0, 0), (0, 0, length * 0.5), (0, 0, length))]
    end = loft.rect(end_w, end_h, 16) if (end_w and end_h) else loft.circle(cyl_r, 16)
    shell = loft.sweep(path, profile=loft.rect(box_w, box_h, 16), profile_end=end, sections=16, closed=True,
                       cap_start=True, cap_end=True, material=material, name=name)
    geos = []
    stations = [(box_w / 2, 0), (-box_w / 2, 0), (0, box_h / 2), (0, -box_h / 2)]
    for i in range(min(ribs, 4)):
        sx, sy = stations[i]
        rib = box_geometry(rib_depth * 2, rib_w, length * 0.6)
        rib.translate(math.hypot(sx, sy), 0, length * 0.34)
        rib.rotate_z(math.atan2(sy, sx))
        geos.append(rib)
    if geos:
        ribs_me = to_mesh(name + ' ribs', merge(geos))
        _append_mesh(shell.data, ribs_me)
        bpy.data.meshes.remove(ribs_me)
    return shell


def _append_mesh(dst, src):
    """dst += src (positions, polygons, UVs, normals as custom normals), keeping each part's shading"""
    nd, ns = len(dst.vertices), len(src.vertices)
    co = np.empty(nd * 3, np.float32)
    dst.vertices.foreach_get('co', co)
    cs = np.empty(ns * 3, np.float32)
    src.vertices.foreach_get('co', cs)
    loops_d = np.empty(len(dst.loops), np.int32)
    dst.loops.foreach_get('vertex_index', loops_d)
    loops_s = np.empty(len(src.loops), np.int32)
    src.loops.foreach_get('vertex_index', loops_s)
    def polys(me):
        ls = np.empty(len(me.polygons), np.int32)
        lt = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_start', ls)
        me.polygons.foreach_get('loop_total', lt)
        return ls, lt
    lsd, ltd = polys(dst)
    lss, lts = polys(src)
    cnd = np.empty(len(dst.loops) * 3, np.float32)
    dst.corner_normals.foreach_get('vector', cnd)
    cns = np.empty(len(src.loops) * 3, np.float32)
    src.corner_normals.foreach_get('vector', cns)
    uvd = np.zeros(len(dst.loops) * 2, np.float32)
    if dst.uv_layers.active:
        dst.uv_layers.active.data.foreach_get('uv', uvd)
    uvs = np.zeros(len(src.loops) * 2, np.float32)
    if src.uv_layers.active:
        src.uv_layers.active.data.foreach_get('uv', uvs)
    mats = list(dst.materials)
    dst.clear_geometry()
    dst.vertices.add(nd + ns)
    dst.vertices.foreach_set('co', np.concatenate([co, cs]))
    dst.loops.add(len(loops_d) + len(loops_s))
    dst.loops.foreach_set('vertex_index', np.concatenate([loops_d, loops_s + nd]))
    dst.polygons.add(len(lsd) + len(lss))
    dst.polygons.foreach_set('loop_start', np.concatenate([lsd, lss + len(loops_d)]))
    dst.polygons.foreach_set('loop_total', np.concatenate([ltd, lts]))
    dst.update(calc_edges=True)
    if not dst.uv_layers:
        dst.uv_layers.new(name='UVMap')
    dst.uv_layers.active.data.foreach_set('uv', np.concatenate([uvd, uvs]))
    dst.polygons.foreach_set('use_smooth', np.ones(len(dst.polygons), bool))
    dst.normals_split_custom_set(np.concatenate([cnd, cns]).reshape(-1, 3).tolist())
    if not dst.materials and mats:
        for m in mats:
            dst.materials.append(m)


# ------------------------------------------------------------------------------------------------ cables
def catenary_points(a, b, sag=0.05, n=12, lateral_jitter=0.0, seed=1):
    """the sagging polyline a -> b (Blender points; parabolic sag, close to a catenary below sag/span 0.3)"""
    rng = mulberry(seed)
    A, B = Vector(a), Vector(b)
    down = Vector((0, 0, -1))
    side = (B - A).cross(down)
    side = side.normalized() if side.length > 0 else side
    pts = []
    for i in range(n + 1):
        t = i / n
        p = A.lerp(B, t) + down * (sag * 4 * t * (1 - t))
        if lateral_jitter:
            p += side * ((rng() - 0.5) * lateral_jitter * math.sin(t * math.pi))
        pts.append(p)
    return pts


def _curve_three(points, curve_type='catmullrom', tension=0.4):
    return CatmullRomCurve3([tuple(np.linalg.inv(_C) @ np.array(p)) for p in points], False, curve_type, tension)


def make_cable(a, b, radius=0.01, sag=0.05, corrugated=False, material=None, seed=1, name='cable'):
    pts = catenary_points(a, b, sag, 12, 0.0, seed)
    curve = _curve_three(pts, 'catmullrom', 0.4)
    if corrugated:
        from ...terrain import loft
        ridges = max(3, round(curve.get_length() * 18))
        return loft.sweep(curve, profile=loft.circle(radius, 8), sections=min(ridges * 4, 240),
                          scale=lambda t: 1 + 0.22 * math.sin(t * math.pi * 2 * ridges), closed=True, cap_start=True,
                          cap_end=True, material=material or rubber(0x1a1a1a), name=name)
    return geometry_object(name, tube_geometry(curve, 32, radius, 8), material or rubber())


def _instances(name, geo, count, material):
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    me = to_mesh(name + ' instance', geo)
    me.materials.append(material)
    obs = []
    for i in range(count):
        ob = bpy.data.objects.new(f'{name} {i:03d}', me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = root
        ob.rotation_mode = 'QUATERNION'
        obs.append(ob)
    return root, obs


def make_e_chain(points, link_len=0.03, count=None, material=None, name='e-chain'):
    """a segmented cable carrier along a Catmull-Rom through `points` (Blender), each link turned from three's +Y
    (Blender +Z) onto the path's tangent"""
    curve = points if isinstance(points, CatmullRomCurve3) else _curve_three(points, 'catmullrom', 0.3)
    count = count or max(4, round(curve.get_length() / link_len))
    geo = box_geometry(link_len * 0.9, link_len * 0.62, link_len * 0.9)
    root, obs = _instances(name, geo, count, material or metal(0x30343a, 0.5, 0.6))
    chain = {'root': root, 'links': obs, 'curve': curve, 'count': count}
    update_e_chain(chain)
    return chain


def update_e_chain(chain, points=None):
    """re-place the links (call only when the path moves)"""
    if points is not None:
        chain['curve'] = points if isinstance(points, CatmullRomCurve3) else _curve_three(points, 'catmullrom', 0.3)
    curve, n = chain['curve'], chain['count']
    for i, ob in enumerate(chain['links']):
        u = i / (n - 1)
        p = np.array(curve.get_point_at(u))
        t = Vector(curve.get_tangent_at(u))
        q = Vector((0, 1, 0)).rotation_difference(t)
        m = Matrix.Translation(Vector(p)) @ q.to_matrix().to_4x4()
        ob.matrix_basis = _C4 @ m @ _C4.inverted()
    return chain


def key_e_chain(chain, points_at, frame_start, frame_end, fps=None):
    """updateEChain per frame (points_at(t) -> the path's points), keyed"""
    fps = fps or bpy.context.scene.render.fps
    for f in range(frame_start, frame_end + 1):
        update_e_chain(chain, points_at((f - frame_start) / fps))
        for ob in chain['links']:
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_quaternion', frame=f)
    _linear_all(chain['links'])


# ------------------------------------------------------------------------------------------------ treads
def tread_path_point(s, run_len, cap_r):
    """the rounded-rect loop (three's local XY: the belt along X, axles along Z): {x, y, a} at fraction s"""
    peri = 2 * run_len + 2 * math.pi * cap_r
    d = ((s % 1) + 1) % 1 * peri
    if d < run_len:
        return {'x': run_len / 2 - d, 'y': cap_r, 'a': math.pi}
    d -= run_len
    if d < math.pi * cap_r:
        t = d / cap_r
        return {'x': -run_len / 2 - math.sin(t) * cap_r, 'y': cap_r * math.cos(t), 'a': math.pi + t}
    d -= math.pi * cap_r
    if d < run_len:
        return {'x': -run_len / 2 + d, 'y': -cap_r, 'a': 0.0}
    d -= run_len
    t = d / cap_r
    return {'x': run_len / 2 + math.sin(t) * cap_r, 'y': -cap_r * math.cos(t), 'a': t}


def make_tread_track(run_len=0.9, cap_r=0.22, width=0.18, plate_n=64, lug=0.012, material=None, name='tread track'):
    peri = 2 * run_len + 2 * math.pi * cap_r
    plate_l = peri / plate_n
    geo = merge([box_geometry(plate_l * 0.92, 0.028, width), box_geometry(plate_l * 0.34, 0.028 + lug * 2, width * 0.82)])
    root, obs = _instances(name, geo, plate_n, material or rubber(0x1c1c1e))
    tread = {'root': root, 'plates': obs, 'run_len': run_len, 'cap_r': cap_r, 'plate_n': plate_n, 'u': 0.0, 'peri': peri}
    scroll_tread(tread, 0.0)
    return tread


def scroll_tread(tread, du):
    """advance the belt by du (a fraction of the loop)"""
    tread['u'] = (tread['u'] + du) % 1
    for i, ob in enumerate(tread['plates']):
        st = tread_path_point(i / tread['plate_n'] + tread['u'], tread['run_len'], tread['cap_r'])
        m = Matrix.Translation((st['x'], st['y'], 0)) @ Matrix.Rotation(st['a'], 4, 'Z')
        ob.matrix_basis = _C4 @ m @ _C4.inverted()
    return tread


def key_tread(tread, u_per_second, frame_start, frame_end, fps=None):
    """scrollTread per frame at a steady speed, keyed"""
    fps = fps or bpy.context.scene.render.fps
    u0 = tread['u']
    for f in range(frame_start, frame_end + 1):
        tread['u'] = u0
        scroll_tread(tread, u_per_second * (f - frame_start) / fps)
        for ob in tread['plates']:
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_quaternion', frame=f)
    _linear_all(tread['plates'])


# ------------------------------------------------------------------------------------------------ wheels
def make_wheel(r=0.28, width=0.16, hub_r=0.08, lug_count=22, lug_depth=0.014, bolt_count=6, material=None,
               hub_material=None, name='wheel'):
    """a lathe tyre with merged lugs, axle along local X (three's; Blender's X too); roll it about X"""
    geos = [lathe_geometry(tire_profile(r, width, hub_r), 28)]
    for i in range(lug_count):
        a = i / lug_count * 2 * math.pi
        g = box_geometry(0.03 * (r / 0.28), width * 0.85, lug_depth * 2)
        g.translate(0, 0, r)
        g.rotate_y(a)
        geos.append(g)
    tyre = merge(geos)
    tyre.rotate_z(math.pi / 2)
    wheel = geometry_object(name, tyre, material or rubber(0x151515))
    hm = hub_material or metal(0xc0c0c8, 0.3, 0.9)
    hub = geometry_object(name + ' hub', cylinder_geometry(hub_r * 0.9, hub_r * 0.9, width * 0.55, 12), hm, wheel)
    _place(hub, (0, 0, 0), (0, 0, math.pi / 2))
    for i in range(bolt_count):
        a = i / bolt_count * 2 * math.pi
        bolt = geometry_object(f'{name} bolt {i}', cylinder_geometry(hub_r * 0.13, hub_r * 0.13, width * 0.6, 6), hm,
                               wheel)
        _place(bolt, (0, math.cos(a) * hub_r * 0.55, math.sin(a) * hub_r * 0.55), (0, 0, math.pi / 2))
    return wheel


def make_mecanum_wheel(hub_r=0.09, hub_width=0.08, roller_count=9, roller_len=0.075, roller_r=0.028, material=None,
                       hub_material=None, name='mecanum wheel'):
    group = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(group)
    hub = geometry_object(name + ' hub', cylinder_geometry(hub_r, hub_r, hub_width, 16),
                          hub_material or metal(0x3a3a40, 0.4, 0.8), group)
    _place(hub, (0, 0, 0), (0, 0, math.pi / 2))
    prof = _v2([(0, -roller_len / 2), (roller_r * 0.7, -roller_len * 0.3), (roller_r, 0), (roller_r * 0.7, roller_len * 0.3),
                (0, roller_len / 2)])
    rg = lathe_geometry(prof, 10)
    rg.rotate_x(math.pi / 2)
    rm = material or rubber(0x202020)
    me = to_mesh(name + ' roller', rg)
    me.materials.append(rm)
    for i in range(roller_count):
        a = i / roller_count * 2 * math.pi
        ob = bpy.data.objects.new(f'{name} roller {i}', me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = group
        _place(ob, (0, math.cos(a) * hub_r * 1.05, math.sin(a) * hub_r * 1.05), (a, 0, math.pi / 4))
    return group


# ------------------------------------------------------------------------------------------------ greebles
def vent_grille(w=0.12, h=0.08, fin_n=7, fin_angle=0.5, fin_depth=0.012, material=None, name='vent grille'):
    geos = []
    for i in range(fin_n):
        g = box_geometry(w * 0.92, 0.005, fin_depth)
        g.rotate_x(fin_angle)
        g.translate(0, (i / (fin_n - 1) - 0.5) * h * 0.85, 0)
        geos.append(g)
    frame = box_geometry(w, h, fin_depth * 0.4)
    frame.translate(0, 0, -fin_depth * 0.35)
    geos.append(frame)
    return geometry_object(name, merge(geos), material or metal(0x1c1c20, 0.55, 0.7))


def hex_bolts(r, y, n, seed=7, bolt_r=None):
    """hex heads (facet-phase jitter) on a ring of radius r * 0.8 at height y: a list of geometries"""
    rng = mulberry(seed)
    br = r * 0.075 if bolt_r is None else bolt_r
    out = []
    for i in range(n):
        a = i / n * 2 * math.pi
        g = cylinder_geometry(br, br, br * 1.3, 6)
        g.rotate_y(rng() * 2 * math.pi)
        g.translate(math.cos(a) * r * 0.8, y, math.sin(a) * r * 0.8)
        out.append(g)
    return out


def piston_rod(r=0.02, clevis_w=0.05, clevis_t=0.009, material=None, name='piston rod'):
    rod = cylinder_geometry(r, r, 0.9, 10)
    rod.translate(0, -0.05, 0)
    ea = box_geometry(clevis_t, 0.1, clevis_w)
    ea.translate(0, 0.45, clevis_w * 0.5)
    eb = box_geometry(clevis_t, 0.1, clevis_w)
    eb.translate(0, 0.45, -clevis_w * 0.5)
    pin = cylinder_geometry(r * 0.4, r * 0.4, clevis_w * 1.5, 8)
    pin.rotate_x(math.pi / 2)
    pin.translate(0, 0.45, 0)
    return geometry_object(name, merge([rod, ea, eb, pin]), material or metal(0xd8dce2, 0.2, 0.95))


def piston_sleeve(r=0.042, wiper=True, material=None, name='piston sleeve'):
    body = cylinder_geometry(r, r, 0.9, 12)
    body.translate(0, -0.05, 0)
    collar = cylinder_geometry(r * 1.25, r * 1.25, 0.06, 12)
    collar.translate(0, 0.42, 0)
    base = cylinder_geometry(r * 1.2, r * 1.35, 0.08, 12)
    base.translate(0, -0.46, 0)
    return geometry_object(name, merge([body, collar, base]), material or metal())


def hose_coil(turns=6, coil_r=0.03, len=0.3, tube_r=0.006, material=None, name='hose coil'):  # noqa: A002
    n = turns * 12
    pts = [(math.cos(i / n * turns * 2 * math.pi) * coil_r, len * (i / n - 0.5), math.sin(i / n * turns * 2 * math.pi) * coil_r)
           for i in range(n + 1)]
    curve = CatmullRomCurve3(pts, False, 'centripetal', 0.5)
    return geometry_object(name, tube_geometry(curve, n, tube_r, 6), material or rubber(0x101014))


# ------------------------------------------------------------------------------------------------ lights
def _emissive(name, base, emissive, intensity, rough=0.5, met=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = tuple(_hex(base)) + (1.0,)
    b.inputs['Emission Color'].default_value = tuple(_hex(emissive)) + (1.0,)
    b.inputs['Emission Strength'].default_value = intensity
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = met
    return m


def beacon(r=0.05, color=0xff7a10, rate=5, name='beacon'):
    mat = _emissive(name, 0x1a0d02, color, 2.0)
    ob = geometry_object(name, sphere_geometry(r, 10, 8), mat)
    sock = mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']

    def update(t):
        sock.default_value = 1 + abs(math.sin(t * rate)) * 2.2
    return {'object': ob, 'mesh': ob, 'material': mat, 'update': update, 'sockets': [sock]}


def stack_light(s=1.0, name='stack light'):
    group = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(group)
    dark = metal(0x22262c, 0.5, 0.7, name + ' metal')
    pole = geometry_object(name + ' pole', cylinder_geometry(0.008 * s, 0.008 * s, 0.09 * s, 8), dark, group)
    _place(pole, (0, 0.045 * s, 0))
    segs, y = [], 0.09 * s
    for col_name, col in (('red', 0xd82020), ('amber', 0xe8a020), ('green', 0x28c840)):
        mat = _emissive(f'{name} {col_name}', 0x181818, col, 0.12, 0.35, 0.1)
        seg = geometry_object(f'{name} {col_name}', cylinder_geometry(0.03 * s, 0.03 * s, 0.038 * s, 12), mat, group)
        _place(seg, (0, y + 0.019 * s, 0))
        y += 0.04 * s
        segs.append((col_name, mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']))
    cap = geometry_object(name + ' cap', cylinder_geometry(0.032 * s, 0.03 * s, 0.012 * s, 12), dark, group)
    _place(cap, (0, y + 0.006 * s, 0))
    state = {'mode': 'run'}                         # 'run' | 'warn' | 'fault' | 'off'

    def update(t):
        blink1 = 1 if math.sin(t * math.pi * 2 * 1.5) > 0 else 0
        blink5 = 1 if math.sin(t * math.pi * 2 * 5) > 0 else 0
        for n, sock in segs:
            on = 0.12
            if state['mode'] == 'run' and n == 'green':
                on = 2.2
            if state['mode'] == 'warn' and n == 'amber':
                on = 0.4 + blink1 * 2.2
            if state['mode'] == 'fault' and n == 'red':
                on = 0.4 + blink5 * 2.6
            sock.default_value = on
    return {'object': group, 'group': group, 'state': state, 'update': update, 'sockets': [s for _, s in segs]}


def key_lights(light, frame_start, frame_end, fps=None, modes=None):
    """light.update(t) at every frame, keyed (CONSTANT for the stack light's blinks, LINEAR for the beacon's pulse);
    modes: optional {frame: mode} changes for a stack light"""
    from bpy_extras import anim_utils
    fps = fps or bpy.context.scene.render.fps
    for f in range(frame_start, frame_end + 1):
        if modes and f in modes and 'state' in light:
            light['state']['mode'] = modes[f]
        light['update']((f - frame_start) / fps)
        for sock in light['sockets']:
            sock.keyframe_insert('default_value', frame=f)
    interp = 'CONSTANT' if 'state' in light else 'LINEAR'
    for sock in light['sockets']:
        nt = sock.id_data
        ad = nt.animation_data
        if ad and ad.action:
            cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
            for fc in cb.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = interp


def _linear_all(objs):
    from bpy_extras import anim_utils
    for ob in objs:
        ad = ob.animation_data
        if ad and ad.action:
            cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
            for fc in cb.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'


# ------------------------------------------------------------------------------------------------ surfaces
def apply_hazard_stripes(mat, freq=24, angle=math.pi / 4, color_a=0xf5c400, color_b=0x151515, use_world_pos=False):
    """yellow / black chevrons as the base colour: stripe = |fract(d) - .5| * 2 with d along `angle` (UV, or the
    object-space x / three's z), mixed by smoothstep(.46, .54, stripe)"""
    nt = mat.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    ca, sa = math.cos(angle), math.sin(angle)
    if use_world_pos:
        src = nt.nodes.new('ShaderNodeTexCoord')
        out = src.outputs['Object']
        k = (ca, -sa, 0.0)                            # three's positionGeometry (x, z) = Blender object (x, -y)
    else:
        src = nt.nodes.new('ShaderNodeUVMap')
        out = src.outputs['UV']
        k = (ca, sa, 0.0)
    dot = nt.nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.inputs[1].default_value = k
    nt.links.new(out, dot.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = freq
    nt.links.new(dot.outputs['Value'], mul.inputs[0])
    fr = nt.nodes.new('ShaderNodeMath')
    fr.operation = 'FLOORED_MODULO'
    fr.inputs[1].default_value = 1.0
    nt.links.new(mul.outputs[0], fr.inputs[0])
    sub = nt.nodes.new('ShaderNodeMath')
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = 0.5
    nt.links.new(fr.outputs[0], sub.inputs[0])
    ab = nt.nodes.new('ShaderNodeMath')
    ab.operation = 'ABSOLUTE'
    nt.links.new(sub.outputs[0], ab.inputs[0])
    two = nt.nodes.new('ShaderNodeMath')
    two.operation = 'MULTIPLY'
    two.inputs[1].default_value = 2.0
    nt.links.new(ab.outputs[0], two.inputs[0])
    sm = nt.nodes.new('ShaderNodeMapRange')
    sm.interpolation_type = 'SMOOTHSTEP'
    sm.inputs['From Min'].default_value = 0.46
    sm.inputs['From Max'].default_value = 0.54
    nt.links.new(two.outputs[0], sm.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    sock = lambda coll, ident: next(s for s in coll if s.identifier == ident)  # noqa: E731
    sock(mix.inputs, 'A_Color').default_value = tuple(_hex(color_a)) + (1.0,)
    sock(mix.inputs, 'B_Color').default_value = tuple(_hex(color_b)) + (1.0,)
    nt.links.new(sm.outputs['Result'], sock(mix.inputs, 'Factor_Float'))
    nt.links.new(sock(mix.outputs, 'Result_Color'), b.inputs['Base Color'])
    return mat


def apply_brushed_metal(mat, base_rough=0.32, grain_freq=240, grain_amp=0.05):
    """1-D grain in the roughness: sin(u * f) * sin(u * 2.3 f + 1.7) * amp + base"""
    nt = mat.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    uv = nt.nodes.new('ShaderNodeUVMap')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uv.outputs['UV'], sep.inputs[0])

    def m(op, a, bval=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = op
        nt.links.new(a, n.inputs[0])
        if bval is not None:
            if isinstance(bval, (int, float)):
                n.inputs[1].default_value = bval
            else:
                nt.links.new(bval, n.inputs[1])
        return n.outputs[0]
    s1 = m('SINE', m('MULTIPLY', sep.outputs['X'], grain_freq))
    s2 = m('SINE', m('ADD', m('MULTIPLY', sep.outputs['X'], grain_freq * 2.3), 1.7))
    r = m('ADD', m('MULTIPLY', m('MULTIPLY', s1, s2), grain_amp), base_rough)
    nt.links.new(r, b.inputs['Roughness'])
    return mat


class _MechParts:
    """the MechParts namespace"""


MechParts = _MechParts()
for _n, _f in dict(globals()).items():
    if callable(_f) and not _n.startswith('_') and _n not in ('Geo', 'Matrix', 'Vector', 'CatmullRomCurve3',
                                                              'frenet_frames', 'to_linear', 'MechParts'):
        setattr(MechParts, _n, _f)
