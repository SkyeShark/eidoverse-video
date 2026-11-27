"""eidoblend.sets.same_seed.desk.kit: the desk room's numbers, its named clays and its build helpers, on the hard-surface
kit (eidoblend.props.hardsurface.masses). Millimetres in every table; the scene in metres.

The room is 6.0 x 5.0 x 2.8 m, a flat's room in an apartment block of the brick-and-plaster kind: the back wall the
outside wall (365 mm: brick, plaster both sides) with the window in it, the others partitions (115 brick and two coats
of plaster: 140). Its space: x across (the lenses look along +y), y to the back wall, z up from the floor. The window
is centred at x -300, so a head at (-400, 100) stands against the night outside in the room's close lens.

    ns = kit.begin(lib)       # a new file, the collection 'desk_room', the named clays; -> the groups' namespace
    shell.build(ns); desk.build(ns); ...    # each group reads its names from ns and adds what later ones use

THE NAMED CLAYS: one material per surface family ('desk.<family>'), named for what it will be, so the look gives each
its photographic set (the clay's colour is near the surface's own albedo, so a clay still already reads light against
dark). lib: the room's CC0 library (eidoblend.materials.photo.Library): the night outside and the Poly Haven pieces.
"""

import math

import bmesh
from mathutils import Matrix, Vector

from ....props.hardsurface import masses as hs

X0, X1, Y0, Y1, HT = -3000.0, 3000.0, -2000.0, 3000.0, 2800.0
TW, TWB = 140.0, 365.0
WCX = -300.0                                                    # the window's middle
MATS = {}
WALL = CEIL = FLOOR = TRIM = PVC = GLASS = SPACER = GASKET = CHROME = DARK = SWITCHES = RAD = None


def M(name, rgb=(0.5, 0.5, 0.5), rough=0.6, metal=0.0, alpha=1.0):
    """the named clay 'desk.<name>' (made once)"""
    if name not in MATS:
        MATS[name] = hs.mat('desk.' + name, rgb, rough, metal, alpha)
    return MATS[name]


def V3(x, y, z):
    return Vector((x, y, z))


# ------------------------------------------------------------------------------------------------ build helpers
# (fin, bx, rev, settle, place, trim, offset2, screw_skins, u_loop, frame_loop, torus: as the kitchen's kit has them)
def cube_uv(o, scale=1.0):
    """a UV map by box projection at real scale (1 UV unit = 1 m / scale), per face on its dominant axis: so the look
    can lay a photographic set at its true size on any built part before its own unwrap. A part that already has its
    own UV (the screen's aperture, the lyrics' sheet) keeps it first; the box projection is 'box_1m'"""
    if o.data.uv_layers:
        o.data.uv_layers.new(name='box_1m')
    bm = bmesh.new()
    bm.from_mesh(o.data)
    uv = bm.loops.layers.uv.get('box_1m') or bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            c = lp.vert.co
            if ax == 0:
                lp[uv].uv = (c.y * (1 if n.x > 0 else -1) * scale, c.z * scale)
            elif ax == 1:
                lp[uv].uv = (c.x * (-1 if n.y > 0 else 1) * scale, c.z * scale)
            else:
                lp[uv].uv = (c.x * scale, c.y * (1 if n.z > 0 else -1) * scale)
    bm.to_mesh(o.data)
    bm.free()


def fin(o, bevel=0.0, m=None, seg=3):
    """hs.finish; and a part that gets no bevel has its hard arrises marked sharp, so its flats shade flat. (A
    boolean's result carries an empty material slot first: cleared here, or its faces render in no material.)"""
    o.data.materials.clear()
    for p_ in o.data.polygons:
        p_.material_index = 0
    o = hs.finish(o, bevel, m or TRIM, segments=seg)
    if not bevel:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(32.0):
                e.smooth = False
        bm.to_mesh(o.data)
        bm.free()
    cube_uv(o)
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


def place(o, at=(0.0, 0.0, 0.0), yaw=0.0, tilt=None):
    """a piece built about its own origin (mm), turned (tilt: (angle, axis) first, then yaw about z) and stood at its
    place in the room"""
    settle(o)
    R = Matrix.Rotation(yaw, 4, 'Z')
    if tilt is not None:
        R = R @ Matrix.Rotation(tilt[0], 4, Vector(tilt[1]))
    o.data.transform(Matrix.Translation(Vector(at) * hs.MM) @ R)
    return o


def trim(o, co=(0.0, 0.0, 0.0), no=(0.0, 0.0, -1.0)):
    """a part cut off flat by a plane and closed again; what lies on the side `no` points to goes"""
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
    """an open 2D line moved sideways by d (to its left as it runs): the other face of a sheet"""
    out = []
    for i, p in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        t = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        out.append((p[0] - t.y * d, p[1] + t.x * d))
    return out


def screw_skins(at, axis, r=3.6, h=2.2):
    return [[hs.circle(at, axis, r, 0.0, 12), hs.circle(at, axis, r, h * 0.45, 12), hs.circle(at, axis, r * 0.62, h, 12)]]


def u_loop(name, a0, a1, bottom, top, prof, P):
    """a moulding up one side of an opening, across its head and down the other, MITRED at the two corners, its two
    ends cut square at `bottom`. prof [(u, v)]: u out from the opening's edge (negative: into the opening), v as P
    takes it"""
    rl = [[P(a + s * u, zt + sz * u, v) for u, v in prof] for a, s, zt, sz in ((a0, -1.0, bottom, 0.0), (a0, -1.0, top, 1.0), (a1, 1.0, top, 1.0), (a1, 1.0, bottom, 0.0))]
    return hs.rings(name, rl)


def frame_loop(name, x0, x1, z0, z1, wl, wr, wb, wt, prof, P):
    """a frame round a rectangle, one section carried round it, mitred at its four corners (a sash, a frame). prof
    [(a, v)]: a 0..1 across a member from its outer edge to its inner, v its depth; the members' widths l, r, b, t"""
    rl = [[P(cx_ + sx * a * wx, cz_ + sz * a * wz, v) for a, v in prof]
          for cx_, sx, wx, cz_, sz, wz in ((x0, 1.0, wl, z0, 1.0, wb), (x1, -1.0, wr, z0, 1.0, wb), (x1, -1.0, wr, z1, -1.0, wt), (x0, 1.0, wl, z1, -1.0, wt))]
    return hs.rings(name, rl + [rl[0]], caps=False)


def torus(name, at, axis, R, r, seg=32, n=12):
    ax = Vector(axis).normalized()
    big = hs.circle(at, ax, R, 0.0, seg)
    rl = []
    for k, p in enumerate(big):
        t = (big[(k + 1) % seg] - big[k - 1]).normalized()
        rl.append(hs.circle(p, t, r, 0.0, n, ax))
    return hs.rings(name, rl + [rl[0]], caps=False)


def mitre_sweep(name, path, section, closed=False):
    """a moulding run along the walls: path [(x, y)] in the floor's plane (mm) with the room on its LEFT; section
    [(u, z)]: u out from the wall into the room, z up. Every corner is a true MITRE (the section stretched along the
    corner's bisector by 1 / cos(half the turn)), so inside and outside corners meet as a joiner cuts them"""
    P = [Vector((p[0], p[1], 0.0)) for p in path]
    n = len(P)
    rings = []
    for i in range(n):
        if closed:
            a, b = P[i - 1], P[(i + 1) % n]
            d0, d1 = (P[i] - a).normalized(), (b - P[i]).normalized()
        else:
            d0 = (P[i] - P[i - 1]).normalized() if i > 0 else (P[1] - P[0]).normalized()
            d1 = (P[i + 1] - P[i]).normalized() if i < n - 1 else d0
        n0, n1 = Vector((-d0.y, d0.x, 0.0)), Vector((-d1.y, d1.x, 0.0))      # the room's side: left of the run
        m = (n0 + n1).normalized()
        k = 1.0 / max(m.dot(n0), 0.2)
        rings.append([P[i] + m * (u * k) + Vector((0, 0, z)) for u, z in section])
    if closed:
        rings.append(rings[0])
    return hs.rings(name, rings, caps=not closed)


def lathe_pts(profile, at, axis, seg, start=None):
    return [hs.circle(at, axis, max(r, 0.0), h, seg, start) for r, h in profile]


def begin(lib):
    """a new file with the collection 'desk_room' (and its workbench), the named clays -> the groups' namespace"""
    global WALL, CEIL, FLOOR, TRIM, PVC, GLASS, SPACER, GASKET, CHROME, DARK, SWITCHES, RAD
    import bpy
    hs.new_file()
    hs.start('desk_room', orient=False)
    MATS.clear()
    WALL = M('wall_paint', (0.62, 0.6, 0.56), 0.85)
    CEIL = M('ceiling_paint', (0.7, 0.7, 0.68), 0.9)
    FLOOR = M('floor_oak', (0.36, 0.25, 0.16), 0.5)
    TRIM = M('trim_white_paint', (0.72, 0.72, 0.7), 0.45)
    PVC = M('window_pvc_white', (0.75, 0.75, 0.73), 0.35)
    GLASS = M('glass', (0.9, 0.92, 0.92), 0.02)
    for k, v in (('Transmission Weight', 1.0), ('IOR', 1.5)):     # (real glass, so the night is seen through it)
        if k in GLASS.node_tree.nodes['Principled BSDF'].inputs:
            GLASS.node_tree.nodes['Principled BSDF'].inputs[k].default_value = v
    SPACER = M('glazing_spacer_alu', (0.45, 0.45, 0.46), 0.4, 1.0)
    GASKET = M('gasket_rubber_black', (0.03, 0.03, 0.03), 0.6)
    CHROME = M('handle_metal', (0.6, 0.6, 0.6), 0.25, 1.0)
    DARK = M('dark_plastic', (0.03, 0.03, 0.035), 0.45)
    SWITCHES = M('switch_plastic_white', (0.74, 0.74, 0.72), 0.3)
    RAD = M('radiator_enamel', (0.72, 0.72, 0.7), 0.3)
    return dict(hs=hs, bpy=bpy, math=math, bmesh=bmesh, Matrix=Matrix, Vector=Vector, LIB=lib, M=M,
                WALL=WALL, CEIL=CEIL, FLOOR=FLOOR, TRIM=TRIM, PVC=PVC, GLASS=GLASS, SPACER=SPACER, GASKET=GASKET,
                CHROME=CHROME, DARK=DARK, SWITCHES=SWITCHES, RAD=RAD,
                X0=X0, X1=X1, Y0=Y0, Y1=Y1, HT=HT, TW=TW, TWB=TWB, WCX=WCX, V3=V3, cube_uv=cube_uv, fin=fin, bx=bx,
                rev=rev, settle=settle, place=place, trim=trim, offset2=offset2, screw_skins=screw_skins,
                u_loop=u_loop, frame_loop=frame_loop, torus=torus, mitre_sweep=mitre_sweep, lathe_pts=lathe_pts)

