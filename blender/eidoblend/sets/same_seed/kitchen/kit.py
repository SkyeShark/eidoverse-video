"""eidoblend.sets.same_seed.kitchen.kit: the kitchen's numbers and build helpers, on the hard-surface kit
(eidoblend.props.hardsurface.masses). Millimetres in every table; the scene in metres.

The room is 6.0 x 5.0 m with a 9 ft (2743 mm) ceiling: the back wall an outside wall (2 x 6 studs, sheathing, boards: 190
with its plaster), the others partitions (2 x 4 and two plasterboards: 115). Its space: x across (the lenses look along
+y), y to the back wall, z up from the floor.

    ns = kit.begin()          # a new file, the collection 'kitchen_room', the clay materials; -> the groups' namespace
    shell.build(ns); cabinets.build(ns); ...    # each group reads its names from ns and adds what later ones use
"""

import math

import bmesh
from mathutils import Matrix, Vector

from ....props.hardsurface import masses as hs

X0, X1, Y0, Y1, HT = -3000.0, 3000.0, -2000.0, 3000.0, 2743.0
TW, TWB = 115.0, 190.0
CLAY = DARK = GLASS = None


def V3(x, y, z):
    return Vector((x, y, z))


def fin(o, bevel=0.0, m=None, seg=3):
    """hs.finish; and a part that gets no bevel has its hard arrises marked sharp, so its flats shade flat"""
    o = hs.finish(o, bevel, m or CLAY, segments=seg)
    if not bevel:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(32.0):
                e.smooth = False
        bm.to_mesh(o.data)
        bm.free()
    return o


def bx(lo, hi):
    """a box as a skin (for hs.skins: many closed pieces in one object)"""
    x0, y0, z0 = [min(a, b) for a, b in zip(lo, hi)]
    x1, y1, z1 = [max(a, b) for a, b in zip(lo, hi)]
    return [[V3(x0, y0, z0), V3(x1, y0, z0), V3(x1, y1, z0), V3(x0, y1, z0)], [V3(x0, y0, z1), V3(x1, y0, z1), V3(x1, y1, z1), V3(x0, y1, z1)]]


def rev(profile, at, axis=(0, 0, 1), seg=24, start=None):
    """a turned piece as a skin (for hs.skins): profile [(radius, height)] about `axis` through `at`"""
    return [hs.circle(at, axis, max(r, 0.0), h, seg, start) for r, h in profile]


def settle(o):
    """an object's own turn and place put into its points"""
    o.data.transform(o.matrix_basis)
    o.matrix_basis = Matrix.Identity(4)
    return o


def place(o, at=(0.0, 0.0, 0.0), yaw=0.0):
    """a piece built about its own origin (mm), turned about z and stood at its place in the room"""
    settle(o)
    o.data.transform(Matrix.Translation(Vector(at) * hs.MM) @ Matrix.Rotation(yaw, 4, 'Z'))
    return o


def trim(o, co=(0.0, 0.0, 0.0), no=(0.0, 0.0, -1.0)):
    """a part cut off flat by a plane and closed again (a splayed leg's foot on the floor); what lies on the side `no`
    points to goes"""
    settle(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7, plane_co=Vector(co) * hs.MM, plane_no=Vector(no), clear_outer=True)
    bmesh.ops.edgeloop_fill(bm, edges=[e for e in r['geom_cut'] if isinstance(e, bmesh.types.BMEdge)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    return o


def offset2(pts, d):
    """an open 2D line moved sideways by d (to its left as it runs): the other face of a sheet or a wall"""
    out = []
    for i, p in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        t = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        out.append((p[0] - t.y * d, p[1] + t.x * d))
    return out


def screw_skins(at, axis, r=3.6, h=2.2):
    return [[hs.circle(at, axis, r, 0.0, 12), hs.circle(at, axis, r, h * 0.45, 12), hs.circle(at, axis, r * 0.62, h, 12)]]


def begin():
    """a new file with the collection 'kitchen_room' (and its workbench), the clay materials -> the groups' namespace"""
    global CLAY, DARK, GLASS
    hs.new_file()
    hs.start('kitchen_room', orient=False)
    CLAY = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    DARK = hs.mat('clay_dark', (0.03, 0.03, 0.03), 0.4, 0.0)
    GLASS = hs.mat('clay_glass', (0.16, 0.19, 0.22), 0.06, 0.0)    # panes and tumblers: a clay still reads them as glass
    return dict(hs=hs, math=math, Vector=Vector, Matrix=Matrix, bmesh=bmesh, CLAY=CLAY, DARK=DARK, GLASS=GLASS,
                X0=X0, X1=X1, Y0=Y0, Y1=Y1, HT=HT, TW=TW, TWB=TWB, V3=V3, fin=fin, bx=bx, rev=rev, settle=settle,
                place=place, trim=trim, offset2=offset2, screw_skins=screw_skins)
