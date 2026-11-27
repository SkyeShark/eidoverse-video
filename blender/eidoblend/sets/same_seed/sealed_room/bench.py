"""eidoblend.sets.same_seed.sealed_room.bench: the welded steel bench of the sealed room, a HIGH and a LOW drawn on one
construction (Blender). Millimetres in the tables; the room's own space (x across, y to the back wall, z up); the scene
in metres.

    from eidoblend.sets.same_seed.sealed_room import bench
    claims = bench.build(high_collection, low_collection)    # {low name: [the high parts it bakes from]}
    for o in high_collection.objects: bench.finish_high(o, clay)
    for o in lows: bench.finish_low(o, clay)

Every part a lens resolves at 0.6-1.0 m is built:
  THE TOP: one 2.5 mm sheet FORMED, not a slab: the face, a 4 mm outside bend, a 40 mm skirt down all four sides, and a
    7 mm return turned in under the skirt's foot (its cut edge broken); the plan's corners welded and ground to an 8 mm
    radius. The face stands at z 880 over (0, -750), 1400 x 600 (TOP, L, D, CX, CY: the mark a prop is set down on).
  THE FRAME: 40 x 40 x 2 square tube (outside corner radius 4 mm), legs inside the skirt's corners up to the sheet's
    underside; top rails inside the skirt (they carry the sheet; no lens sees them: high and AO only); four stretchers
    at 180 mm, butted to the legs and WELDED round (fillet beads with their ripples).
  THE SHELF: a 1.5 mm sheet on the stretchers, its long edges turned down over them.
  THE FEET: each leg closed by a 4 mm plate welded round; under it a welded M12 nut, a jam nut, the threaded stem, a
    pressed steel pad on a rubber disc (a levelling foot as sold).
  THE LOW, drawn on the same construction (never decimated, never remeshed): the same profiles and outlines with fewer
    segments on each radius (the high's bends 6, the low's 2), no welds, threads or edge breaks (they are baked), no
    hidden rails; every low face smooth with face-area weighted normals applied into the mesh (flat faces keep their
    plane normal, the chamfers carry the bend), the bake synced to those normals. UVs are written as the low is built:
    every swept part unrolled by arc length (u round its section, v along its path), every cap and flat by its own
    plane, all in metres (true size; the room's lows step weights and packs them).
"""
import math
import zlib

import bmesh
import bpy
from mathutils import Vector

MM = 1e-3
TOP, L, D, CX, CY = 880.0, 1400.0, 600.0, 0.0, -750.0
T_SHEET, SKIRT, RET, RC = 2.5, 40.0, 7.0, 8.0                 # the top's sheet, skirt, return, plan corner radius
TUBE, TR, TW = 40.0, 4.0, 2.0                                   # square tube, its outside radius, its wall
INSET = RET + 0.5                                               # a leg's outer face just inside the return's edge
LX = L / 2 - INSET - TUBE / 2                                  # leg centres: +-677
LY = D / 2 - INSET - TUBE / 2                                   # +-277 about CY
Z_PLATE0, Z_PLATE1 = 40.0, 44.0                                 # the foot plate
Z_TOPU = TOP - T_SHEET                                          # the sheet's underside: the legs' tops
Z_STR = 180.0                                                   # the stretchers' centre line
T_SHELF = 1.5


def V(x, y, z):
    return Vector((x, y, z))


# ============================================================================================ GENERAL BUILDERS
def arc_pts(cu, cv, r, a0, a1, n):
    """(u, v) points along an arc, degrees, n segments"""
    return [(cu + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cv + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def dedup(pts, eps=1e-6):
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    return out


def support(pts, closed=False, eps=0.05, turn_deg=35.0, with_normals=False):
    """SUPPORT ROWS for a high's section: smooth normals interpolate across a flat face whose edge vertex is shared with
    a bend, so a flat strip beside a bend would shade as if it were curved. Where a straight run longer than 4 eps meets
    a smooth vertex (a vertex of an arc: it turns less than turn_deg), a vertex is put eps (mm) along the run from it:
    the run then shades flat to within eps of the bend, the way a sub-d support loop holds an edge. pts: [(u, v)], or
    with_normals [((u, v), n)] (the new vertex takes its neighbour's normal: an arc's end shares its tangent run's)."""
    P = [p[0] if with_normals else p for p in pts]
    n = len(P)

    def turn(i):
        if not closed and (i == 0 or i == n - 1):
            return 180.0
        a, b, c = Vector(P[(i - 1) % n]), Vector(P[i]), Vector(P[(i + 1) % n])
        d0, d1 = (b - a), (c - b)
        if d0.length < 1e-9 or d1.length < 1e-9:
            return 180.0
        return math.degrees(d0.angle(d1))
    out = []
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        out.append(pts[i])
        a, b = Vector(P[i]), Vector(P[j])
        seg = (b - a).length
        if seg > 4.0 * eps:
            d = (b - a) / seg
            for at, src in (((a + d * eps), i), ((b - d * eps), j)):
                if turn(src) < turn_deg:
                    q = (at.x, at.y)
                    out.append((q, pts[src][1]) if with_normals else q)
    if not closed:
        out.append(pts[-1])
    return out


def rrect_loop(cx, cy, hw, hh, r, n):
    """a rounded rectangle's outline (counter-clockwise from the right side's bottom), with each vertex's outward normal:
    [((x, y), (nx, ny))]; n segments a corner"""
    out = []
    for (ccx, ccy), a0 in (((cx + hw - r, cy - hh + r), -90.0), ((cx + hw - r, cy + hh - r), 0.0), ((cx - hw + r, cy + hh - r), 90.0),
                           ((cx - hw + r, cy - hh + r), 180.0)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            out.append(((ccx + r * math.cos(a), ccy + r * math.sin(a)), (math.cos(a), math.sin(a))))
    return out


def polyline_len(P):
    s = [0.0]
    for a, b in zip(P, P[1:]):
        s.append(s[-1] + (Vector(b) - Vector(a)).length)
    return s


class MeshB:
    """a bmesh that collects skins and caps, with an optional UV layer 'atlas' written in metres as faces are made"""

    def __init__(self, uv=False):
        self.bm = bmesh.new()
        self.uvl = self.bm.loops.layers.uv.new('atlas') if uv else None

    def verts(self, pts):
        return [self.bm.verts.new(Vector(p) * MM) for p in pts]

    def face(self, vs, uvs=None):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        if self.uvl is not None and uvs is not None:
            for lp, uv in zip(f.loops, uvs):
                lp[self.uvl].uv = uv
        return f

    def grid(self, G, close_sec, close_path, us=None, vs=None, seams=()):
        """G[i][j]: points along the path (i) and round the section (j). Faces between neighbours; close_sec: the
        section is a closed loop; close_path: the path is. UV: u = us[j] (mm along the section), v = vs[i] (mm along
        the path), both in metres; a closed loop's last column carries u = its whole length (the seam). seams: path
        indices where v starts again from 0 (a new UV island: the bench top's 4 m loop as four sides, so the packer
        is not held to the scale of one strip 4 m long)"""
        ni, nj = len(G), len(G[0])
        Vt = [self.verts(row) for row in G]
        if us is None:
            us = polyline_len(list(G[0]) + ([G[0][0]] if close_sec else []))
        if vs is None:
            cen = [Vector(map(lambda *c: sum(c) / nj, *row)) for row in G]
            vs = polyline_len(cen + ([cen[0]] if close_path else []))
        starts = sorted(seams)
        for i in range(ni if close_path else ni - 1):
            i2 = (i + 1) % ni
            base = vs[max([s for s in starts if s <= i], default=0)] if starts else 0.0
            for j in range(nj if close_sec else nj - 1):
                j2 = (j + 1) % nj
                ua, ub = us[j] * MM, us[j + 1] * MM
                va, vb = (vs[i] - base) * MM, (vs[i + 1] - base) * MM
                self.face([Vt[i][j], Vt[i2][j], Vt[i2][j2], Vt[i][j2]], [(ua, va), (ua, vb), (ub, vb), (ub, va)])
        return Vt

    def cap(self, vs, axes, flip=False):
        """an n-gon over existing vertices, its UV the plane's own coordinates (axes: two of 0, 1, 2), in metres"""
        vv = vs[::-1] if flip else vs
        uvs = [(v.co[axes[0]], v.co[axes[1]]) for v in vv]
        return self.face(vv, uvs)

    def obj(self, name, coll):
        me = bpy.data.meshes.new(name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        o = bpy.data.objects.new(name, me)
        coll.objects.link(o)
        return o


def section_ring(C, n_out, axis, sec):
    """a section [(a, b)] placed at C: a along n_out, b along axis"""
    return [C + n_out * a + axis * b for a, b in sec]


# ============================================================================================ THE TOP
def top_profile(high):
    """the formed sheet's section (u out from the plan's outline, v up from the face at z TOP), inner top -> inner bottom"""
    nb, nr, ni = (6, 4, 3) if high else (2, 1, 1)
    p = [(-RC + 0.5, 0.0), (-4.0, 0.0)]
    p += arc_pts(-4.0, -4.0, 4.0, 90.0, 0.0, nb)[1:]                   # the outside bend
    p += [(0.0, -SKIRT + 2.5)]
    p += arc_pts(-2.5, -SKIRT + 2.5, 2.5, 0.0, -90.0, nr)[1:]           # the return's bend
    if high:
        p += [(-RET + 0.2, -SKIRT), (-RET, -SKIRT + 0.2), (-RET, -SKIRT + T_SHEET - 0.2), (-RET + 0.2, -SKIRT + T_SHEET)]   # the cut edge, broken
    else:
        p += [(-RET, -SKIRT), (-RET, -SKIRT + T_SHEET)]
    p += [(-T_SHEET, -SKIRT + T_SHEET), (-T_SHEET, -4.0)]
    p += arc_pts(-4.0, -4.0, 1.5, 0.0, 90.0, ni)[1:]                    # the inside of the bend
    p += [(-RC + 0.5, -T_SHEET)]
    return support(dedup(p)) if high else dedup(p)


def build_top(name, coll, high):
    mb = MeshB(uv=not high)
    nc = 8 if high else 2
    loop = rrect_loop(CX, CY, L / 2, D / 2, RC, nc)
    prof = top_profile(high)
    G = [[V(x + nx * u, y + ny * u, TOP + v) for u, v in prof] for (x, y), (nx, ny) in loop]
    Vt = mb.grid(G, close_sec=False, close_path=True, seams=[c * (nc + 1) + nc // 2 for c in range(4)])   # (at each corner's middle)
    mb.cap([row[0] for row in Vt], (0, 1))                             # the face (z up)
    mb.cap([row[-1] for row in Vt], (0, 1), flip=True)                # the sheet's underside
    return mb.obj(name, coll)


# ============================================================================================ TUBES
def tube_section(n, w=TUBE, h=TUBE):
    s = [(x, y) for x, y in rrect_pts(w / 2, h / 2, TR, n)]
    return support(s, closed=True) if n > 2 else s


def rrect_pts(hw, hh, r, n):
    return [p for p, _ in rrect_loop(0.0, 0.0, hw, hh, r, n)]


def build_tube(name, coll, a, b, up, high, caps=True, size=(TUBE, TUBE)):
    """a square (or rectangular: size = across, toward up) tube from a to b (its centre line), its section's second
    axis toward `up`"""
    a, b = Vector(a), Vector(b)
    t = (b - a).normalized()
    u_ = Vector(up)
    w = (u_ - t * u_.dot(t)).normalized()
    s = w.cross(t)
    sec = tube_section(6 if high else 2, *size)
    mb = MeshB(uv=not high)
    G = [[P + s * x + w * y for x, y in sec] for P in (a, b)]
    Vt = mb.grid(G, close_sec=True, close_path=False)
    if caps:
        ax = max(range(3), key=lambda i: abs(t[i]))
        pl = tuple(i for i in range(3) if i != ax)
        mb.cap(Vt[0], pl, flip=True)
        mb.cap(Vt[-1], pl)
    return mb.obj(name, coll)


# ============================================================================================ WELDS
def weld_loop(name, coll, centre, n1, n2, outline, r=2.6, pitch=1.8, step=0.45, seed=0):
    """a fillet weld bead round a closed outline [(p, q)] in the plane (n1, n2) through `centre` where a part butts
    into a face whose normal is axis = n1 x n2 (the bead lies on the face, round the part). Its section a circle of
    radius r centred 0.5 r out from the part and 0.5 r off the face; its radius rippling every `pitch` mm (the puddle's
    freezing fronts) and wandering a little (a hand weld is not machine-even)."""
    ax = n1.cross(n2).normalized()
    pts = [(Vector(p), Vector(nrm)) for p, nrm in outline]
    # resample the outline to `step`
    res = []
    for k in range(len(pts)):
        (p0, m0), (p1, m1) = pts[k], pts[(k + 1) % len(pts)]
        seg = (p1 - p0).length
        n = max(1, int(math.ceil(seg / step)))
        for i in range(n):
            f = i / n
            mm = (m0.lerp(m1, f)).normalized()
            res.append((p0.lerp(p1, f), mm))
    s = 0.0
    ring_list = []
    rnd = (seed * 7919) % 97 / 97.0
    for i, (p, m) in enumerate(res):
        if i:
            s += (p - res[i - 1][0]).length
        rip = 1.0 + 0.07 * math.sin(math.pi * s / pitch) ** 2 + 0.05 * math.sin(s / 23.0 + rnd * 6.28)
        rr = r * rip
        nm = n1 * m.x + n2 * m.y
        C = centre + n1 * p.x + n2 * p.y + nm * (0.5 * r) + ax * (0.5 * r)
        ring = []
        for k in range(12):
            th = 2.0 * math.pi * k / 12
            ring.append(C + (nm * math.cos(th) + ax * math.sin(th)) * rr)
        ring_list.append(ring)
    mb = MeshB()
    mb.grid(ring_list, close_sec=True, close_path=True)
    return mb.obj(name, coll)


# ============================================================================================ THE FEET
def revolve_mb(mb, prof, at, seg, close_top=True):
    """a profile [(r, z)] turned about the vertical through `at`; the profile starts and ends on the axis (r = 0)
    or is closed by caps"""
    at = Vector(at)
    G = []
    for k in range(seg):
        a = 2.0 * math.pi * k / seg
        c, s_ = math.cos(a), math.sin(a)
        G.append([at + Vector((r * c, r * s_, z)) for r, z in prof])
    Vt = mb.grid(G, close_sec=False, close_path=True, us=polyline_len(prof),
                 vs=[2.0 * math.pi * max(r for r, _ in prof) * k / seg for k in range(seg + 1)])
    if prof[0][0] > 1e-6:                                              # (a profile that starts or ends ON the axis needs no
        mb.cap([row[0] for row in Vt], (0, 1), flip=True)              #  cap: its ring is one point, welded by the finish)
    if prof[-1][0] > 1e-6:
        mb.cap([row[-1] for row in Vt], (0, 1))
    return Vt


def hex_pts(af, n_round=0, r_round=0.0, turn=0.0):
    """a hexagon across flats af (mm), its corners rounded by r_round in n_round segments: [((x, y), (nx, ny))]"""
    R = af / math.sqrt(3.0)
    out = []
    for k in range(6):
        a = math.radians(60.0 * k + turn)
        cx, cy = (R - r_round / math.cos(math.radians(30.0))) * math.cos(a), (R - r_round / math.cos(math.radians(30.0))) * math.sin(a)
        if n_round:
            for i in range(n_round + 1):
                b = a + math.radians(-30.0 + 60.0 * i / n_round)
                out.append(((cx + r_round * math.cos(b), cy + r_round * math.sin(b)), (math.cos(b), math.sin(b))))
        else:
            out.append(((R * math.cos(a), R * math.sin(a)), (math.cos(a), math.sin(a))))
    return out


def build_prism(name, coll, outline, z0, z1, high, chamfer=0.0):
    """a vertical prism over an outline [((x, y), n)], its top and bottom arrises chamfered by `chamfer` (high only)"""
    mb = MeshB(uv=not high)
    if high and chamfer > 0.0:
        rows = [(0.0 - chamfer, z0), (0.0, z0 + chamfer), (0.0, z1 - chamfer), (-chamfer, z1)]
    else:
        rows = [(0.0, z0), (0.0, z1)]
    G = [[V(x + nx * du, y + ny * du, z) for du, z in rows] for (x, y), (nx, ny) in outline]
    Gt = [list(c) for c in zip(*G)]                                    # rows along z, each a ring round the outline
    Vt = mb.grid(Gt, close_sec=True, close_path=False)
    mb.cap(Vt[0], (0, 1), flip=True)
    mb.cap(Vt[-1], (0, 1))
    return mb.obj(name, coll)


def thread_profile(z0, z1, r_crest=6.0, r_root=5.1, pitch=1.75):
    """an M12 thread's section as rings (a helix's look at this size), from z0 to z1, on the axis at both ends"""
    p = [(0.0, z0), (r_crest - 0.6, z0), (r_crest, z0 + 0.6)]
    z = z0 + 0.6
    while z + pitch < z1 - 0.6:
        p += [(r_root, z + pitch * 0.5), (r_crest, z + pitch)]
        z += pitch
    p += [(r_crest, z1 - 0.6), (r_crest - 0.6, z1), (0.0, z1)]
    return p


def build_feet(coll_h, coll_l, legs):
    """each leg's foot: plate, welded nut, jam nut, stem, pad, rubber; HIGH and LOW; returns {low name: [high names]}"""
    claims = {}
    for k, (x, y) in enumerate(legs):
        for high, coll in ((True, coll_h), (False, coll_l)):
            sfx = 'high' if high else 'low'
            n_r = 6 if high else 2
            sup = (lambda o_: support(o_, closed=True, with_normals=True)) if high else (lambda o_: o_)
            plate = build_prism(f'bench_foot_plate_{k}_{sfx}', coll, [((x + px, y + py), nn) for (px, py), nn in sup(rrect_loop(0, 0, 25.0, 25.0, 4.0, n_r))],
                                Z_PLATE0, Z_PLATE1, high, chamfer=0.6)
            nut = build_prism(f'bench_foot_nut_{k}_{sfx}', coll, [((x + px, y + py), nn) for (px, py), nn in sup(hex_pts(19.0, 2 if high else 0, 0.8, 15.0 + k * 11))],
                              Z_PLATE0 - 10.0, Z_PLATE0, high, chamfer=1.0)
            jam = build_prism(f'bench_foot_jam_{k}_{sfx}', coll, [((x + px, y + py), nn) for (px, py), nn in sup(hex_pts(19.0, 2 if high else 0, 0.8, 40.0 + k * 17))],
                              21.0, 28.0, high, chamfer=0.9)
            mb = MeshB(uv=not high)
            if high:
                revolve_mb(mb, thread_profile(12.0, Z_PLATE0 - 0.5), (x, y, 0.0), 32)
            else:
                revolve_mb(mb, [(0.0, 12.0), (6.0, 12.0), (6.0, Z_PLATE0 - 0.5), (0.0, Z_PLATE0 - 0.5)], (x, y, 0.0), 12)
            stem = mb.obj(f'bench_foot_stem_{k}_{sfx}', coll)
            mb = MeshB(uv=not high)
            if high:
                pad = [(0.0, 3.0), (23.6, 3.0), (24.6, 3.6), (25.0, 4.8), (25.0, 6.6), (24.2, 8.0), (21.0, 9.2), (12.0, 10.6), (9.2, 12.0), (8.0, 13.6), (0.0, 13.6)]
            else:
                pad = [(0.0, 3.0), (24.6, 3.0), (25.0, 4.8), (25.0, 6.6), (21.0, 9.2), (9.2, 12.0), (8.0, 13.6), (0.0, 13.6)]
            revolve_mb(mb, support(pad) if high else pad, (x, y, 0.0), 48 if high else 16)
            padobj = mb.obj(f'bench_foot_pad_{k}_{sfx}', coll)
            mb = MeshB(uv=not high)
            rub = [(0.0, 0.0), (23.4, 0.0), (24.2, 0.4), (24.6, 1.2), (24.6, 3.0), (0.0, 3.0)] if high else [(0.0, 0.0), (24.2, 0.0), (24.6, 1.2), (24.6, 3.0), (0.0, 3.0)]
            revolve_mb(mb, support(rub) if high else rub, (x, y, 0.0), 48 if high else 16)
            rubber = mb.obj(f'bench_foot_rubber_{k}_{sfx}', coll)
            if high:
                # the plate welded round the leg's foot, and the nut welded to the plate's underside
                weld_loop(f'bench_weld_foot_{k}_high', coll, V(x, y, Z_PLATE1), Vector((1, 0, 0)), Vector((0, 1, 0)),
                          rrect_loop(0, 0, TUBE / 2, TUBE / 2, TR, 6), r=2.2, seed=k)
                # (its plane's axes are x and -y, so the bead stands down off the plate: the nut's hexagon mirrored about x)
                weld_loop(f'bench_weld_nut_{k}_high', coll, V(x, y, Z_PLATE0), Vector((1, 0, 0)), Vector((0, -1, 0)),
                          hex_pts(19.0, 2, 0.8, -(15.0 + k * 11)), r=1.4, seed=k + 10)
        claims[f'bench_foot_plate_{k}_low'] = [f'bench_foot_plate_{k}_high', f'bench_weld_foot_{k}_high', f'bench_weld_nut_{k}_high']
        claims[f'bench_foot_nut_{k}_low'] = [f'bench_foot_nut_{k}_high', f'bench_weld_nut_{k}_high']
        claims[f'bench_foot_jam_{k}_low'] = [f'bench_foot_jam_{k}_high']
        claims[f'bench_foot_stem_{k}_low'] = [f'bench_foot_stem_{k}_high']
        claims[f'bench_foot_pad_{k}_low'] = [f'bench_foot_pad_{k}_high']
        claims[f'bench_foot_rubber_{k}_low'] = [f'bench_foot_rubber_{k}_high']
    return claims


# ============================================================================================ THE SHELF
def shelf_section(high):
    """the shelf's section (y about CY, z): its long edges turned down 20 mm over the stretchers"""
    yo = TUBE / 2 + LY + 0.8                                            # the flange's inside face, 0.8 off the stretcher
    z1 = Z_STR + TUBE / 2 + T_SHELF                                    # its face
    nb = 4 if high else 1
    outer = [(-(yo + T_SHELF), z1 - 22.0)]
    outer += arc_pts(-(yo + T_SHELF) + 2.5, z1 - 2.5, 2.5, 180.0, 90.0, nb)
    outer += arc_pts((yo + T_SHELF) - 2.5, z1 - 2.5, 2.5, 90.0, 0.0, nb)
    outer += [((yo + T_SHELF), z1 - 22.0)]
    inner = [(yo, z1 - 22.0)]
    inner += arc_pts(yo - 1.0, z1 - T_SHELF - 1.0, 1.0, 0.0, 90.0, nb)
    inner += arc_pts(-yo + 1.0, z1 - T_SHELF - 1.0, 1.0, 90.0, 180.0, nb)
    inner += [(-yo, z1 - 22.0)]
    return support(dedup(outer + inner), closed=True) if high else dedup(outer + inner)


def build_shelf(name, coll, high):
    sec = shelf_section(high)
    x0, x1 = -(LX - TUBE / 2 - 1.0), (LX - TUBE / 2 - 1.0)
    mb = MeshB(uv=not high)
    G = [[V(x, CY + y, z) for y, z in sec] for x in (x0, x1)]
    Vt = mb.grid(G, close_sec=True, close_path=False)
    mb.cap(Vt[0], (1, 2), flip=True)
    mb.cap(Vt[-1], (1, 2))
    return mb.obj(name, coll)


# ============================================================================================ THE WHOLE BENCH
def build(coll_h, coll_l):
    """the bench's HIGH parts into coll_h and its LOW parts into coll_l; returns {low name: [the high names it claims]}"""
    claims = {}
    build_top('bench_top_high', coll_h, True)
    build_top('bench_top_low', coll_l, False)
    claims['bench_top_low'] = ['bench_top_high']
    legs = [(CX + sx * LX, CY + sy * LY) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for k, (x, y) in enumerate(legs):
        build_tube(f'bench_leg_{k}_high', coll_h, (x, y, Z_PLATE1), (x, y, Z_TOPU), (0, 1, 0), True)
        build_tube(f'bench_leg_{k}_low', coll_l, (x, y, Z_PLATE1), (x, y, Z_TOPU), (0, 1, 0), False)
        claims[f'bench_leg_{k}_low'] = [f'bench_leg_{k}_high', f'bench_weld_foot_{k}_high']
    # the top rails inside the skirt (HIGH and AO only: the skirt hides them from every lens)
    zr = Z_TOPU - 15.0
    for nm, a, b in (('front', (CX - LX + 20, CY - LY, zr), (CX + LX - 20, CY - LY, zr)), ('back', (CX - LX + 20, CY + LY, zr), (CX + LX - 20, CY + LY, zr)),
                     ('left', (CX - LX, CY - LY + 20, zr), (CX - LX, CY + LY - 20, zr)), ('right', (CX + LX, CY - LY + 20, zr), (CX + LX, CY + LY - 20, zr))):
        build_tube(f'bench_rail_{nm}_high', coll_h, a, b, (0, 0, 1), True, size=(TUBE, 30.0))     # 40 x 30, 847.5-877.5
    # the stretchers, butted to the legs' faces and welded round at both ends
    strs = {'front': ((CX - LX + 20, CY - LY, Z_STR), (CX + LX - 20, CY - LY, Z_STR)), 'back': ((CX - LX + 20, CY + LY, Z_STR), (CX + LX - 20, CY + LY, Z_STR)),
            'left': ((CX - LX, CY - LY + 20, Z_STR), (CX - LX, CY + LY - 20, Z_STR)), 'right': ((CX + LX, CY - LY + 20, Z_STR), (CX + LX, CY + LY - 20, Z_STR))}
    for nm, (a, b) in strs.items():
        build_tube(f'bench_stretcher_{nm}_high', coll_h, a, b, (0, 0, 1), True, caps=False)
        build_tube(f'bench_stretcher_{nm}_low', coll_l, a, b, (0, 0, 1), False, caps=False)
        a, b = Vector(a), Vector(b)
        t = (b - a).normalized()
        welds = []
        for end, P, sgn in (('a', a, 1.0), ('b', b, -1.0)):
            # the bead lies on the leg's face (its normal: the stretcher's axis, pointing away from the leg), round the tube
            ax = t * sgn
            n1 = Vector((0, 0, 1)).cross(ax).normalized() if abs(ax.z) < 0.9 else Vector((1, 0, 0))
            n2 = ax.cross(n1).normalized()
            wn = f'bench_weld_{nm}_{end}_high'
            weld_loop(wn, coll_h, P, n1, n2, rrect_loop(0, 0, TUBE / 2, TUBE / 2, TR, 6), r=2.6, seed=zlib.crc32(wn.encode()) % 1000)
            welds.append(wn)
        claims[f'bench_stretcher_{nm}_low'] = [f'bench_stretcher_{nm}_high'] + welds
        # each weld also lies on its leg
        legs_of = {'front': (0, 1), 'back': (3, 2), 'left': (0, 3), 'right': (1, 2)}[nm]
        for wn, kleg in zip(welds, legs_of):
            claims[f'bench_leg_{kleg}_low'].append(wn)
    build_shelf('bench_shelf_high', coll_h, True)
    build_shelf('bench_shelf_low', coll_l, False)
    claims['bench_shelf_low'] = ['bench_shelf_high']
    claims.update(build_feet(coll_h, coll_l, legs))
    return claims


def finish_high(o, mat=None):
    """a high part: smooth, sharp only past 31 degrees (every radius here turns 15-22.5 degrees a segment)"""
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)           # (a revolve's axis points, a closed sweep's seam)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(31.0))
    except Exception:  # noqa: BLE001
        pass
    if mat is not None:
        me.materials.append(mat)


def finish_low(o, mat=None):
    """a low part: every face smooth, face-area weighted normals written into the mesh, triangulated once"""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    for e in bm.edges:                                                 # (hard where a face turns past 50 degrees: a hex's
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(50.0))   # 60, a cap's 90;
    for f in bm.faces:                                                 #  smooth over a bend's 45-degree segments)
        f.smooth = True
    bm.to_mesh(o.data)
    bm.free()
    if mat is not None:
        o.data.materials.append(mat)
    m = o.modifiers.new('weighted', 'WEIGHTED_NORMAL')
    m.mode, m.weight, m.keep_sharp = 'FACE_AREA', 100, True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    o.modifiers.clear()
    old = o.data
    o.data = me2
    me2.name = old.name
    bpy.data.meshes.remove(old)
