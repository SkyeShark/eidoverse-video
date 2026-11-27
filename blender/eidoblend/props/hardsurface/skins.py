"""eidoblend.props.hardsurface.skins: lofted skins and what an opening in a skin carries. Millimetres in, as masses.

    from eidoblend.props.hardsurface import masses as hs, skins as sk
    from eidoblend.props.hardsurface.sections import Body, stations

    hull = sk.loft_body('hull', BODY, stations(x0, x1, 60.0))        # a sections.Body skinned over its stations
    surf = sk.Surface(reference_copy)                                  # the uncut skin, to ask
    path = sk.border(surf, outline_pts, out_dir)                       # an opening's edge laid ON the skin
    sk.frame('strip', path, STRIP_SECTION, metal)                      # a retainer swept round it
    sk.screws('screws', path, metal, pitch=48.0)                       # dome heads along it
    sk.pane('pane', solid_copy, surf, cutter, glass)                   # the skin's own patch, set in, given thickness

    finish_smooth   a lofted skin kept as it was lofted (masses.finish dissolves near-flat faces into n-gons: right for
                    a machined block, wrong for a gently curved skin, whose light then breaks across each n-gon)
    round_poly      a closed 2D outline with its corners turned
    prism           a planar outline pushed along any direction (a cutter square to a leaning pane)
    Surface         the uncut skin as something to ask: where a ray meets it, its normal there, the nearest point
    border, frame   an opening's edge as a path ON the skin, and a section swept round it
    screws          dome heads along such a path
    pane            the skin's own patch inside an opening, set in and given its thickness: glass that follows the skin
    blade_data      a ring skin's own coordinates as a colour attribute (a blade's chord and span for its material)
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import masses as hs

MM = hs.MM


def finish_smooth(o, m, parent=None, sharp_deg=None):
    """A skin into the asset as it was lofted: welded, normals consistent, material m, smooth shaded (sharp by
    angle when sharp_deg is given), a weighted-normal modifier, under `parent` when given."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=2e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    open_e = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    bm.to_mesh(o.data)
    bm.free()
    for c in list(o.users_collection):
        c.objects.unlink(o)
    hs.col.objects.link(o)
    o.data.materials.clear()                                  # (a cut part can come back with an empty first slot)
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True
        p.material_index = 0
    if sharp_deg:
        o.data.set_sharp_from_angle(angle=math.radians(sharp_deg))
    w = o.modifiers.new('weighted', 'WEIGHTED_NORMAL')
    w.keep_sharp = True
    if parent is not None:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    hs.REPORT.append((o.name, open_e, round(vol * 1e3, 3), len(o.data.polygons)))
    if open_e:
        print(f'[hardsurface] part {o.name}: OPEN EDGES {open_e}')
    return o


def round_poly(pts, r, n=6):
    """A closed outline [(u, v)] with every corner turned to radius r (less where an edge is short)."""
    out, m = [], len(pts)
    for i in range(m):
        p0, p1, p2 = Vector(pts[i - 1]).to_2d(), Vector(pts[i]).to_2d(), Vector(pts[(i + 1) % m]).to_2d()
        d0, d1 = (p0 - p1), (p2 - p1)
        l0, l1 = d0.length, d1.length
        d0, d1 = d0 / l0, d1 / l1
        ang = math.acos(max(-1.0, min(1.0, d0.dot(d1))))
        if ang > math.radians(178.0) or r <= 0.0:
            out.append((p1.x, p1.y))
            continue
        t = min(r / math.tan(ang / 2.0), l0 * 0.48, l1 * 0.48)
        rr = t * math.tan(ang / 2.0)
        cen = p1 + (d0 + d1).normalized() * (rr / math.sin(ang / 2.0))
        a, b = p1 + d0 * t - cen, p1 + d1 * t - cen
        a0, a1 = math.atan2(a.y, a.x), math.atan2(b.y, b.x)
        da = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
        out += [(cen.x + rr * math.cos(a0 + da * k / n), cen.y + rr * math.sin(a0 + da * k / n)) for k in range(n + 1)]
    return out


def basis(normal, hint=(1.0, 0.0, 0.0)):
    """Two unit vectors square to `normal`: u as near `hint` as it can be, v = normal x u; and the normal."""
    n = Vector(normal).normalized()
    u = Vector(hint) - n * n.dot(Vector(hint))
    u.normalize()
    return u, n.cross(u), n


def prism(name, pts3, direction, d0, d1):
    """A planar outline (points, mm) pushed along `direction` from d0 to d1 (mm either side of its plane)."""
    dv = Vector(direction).normalized()
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((Vector(p) + dv * d0) * MM) for p in pts3])
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)], vec=dv * (d1 - d0) * MM)
    return hs.obj(name, bm)


def on_plane(at, u, v, outline):
    """A 2D outline [(a, b)] as points at + u a + v b."""
    return [Vector(at) + u * a + v * b for a, b in outline]


class Surface:
    """An uncut skin (an object, in metres) to ask, in millimetres."""

    def __init__(self, o):
        dg = bpy.context.evaluated_depsgraph_get()
        self.bvh = BVHTree.FromObject(o, dg)

    def hit(self, p, direction, reach=4000.0):
        """Where the ray from p (mm) along `direction` first meets the skin -> (point mm, normal) or None."""
        d = Vector(direction).normalized()
        loc, nrm, _i, _d = self.bvh.ray_cast(Vector(p) * MM, d, reach * MM)
        if loc is None:
            return None
        return loc / MM, nrm.normalized()

    def near(self, p):
        """The nearest point of the skin to p (mm) -> (point mm, normal, distance mm)."""
        loc, nrm, _i, dist = self.bvh.find_nearest(Vector(p) * MM)
        return loc / MM, nrm.normalized(), dist / MM


def border(surf, pts3, direction, back=1500.0, step=18.0):
    """An opening's outline (points on its cutter's plane, mm), laid ON the skin by rays along -direction from `back`
    mm outside: [(point, the skin's normal)], no two points further apart than `step`."""
    d = Vector(direction).normalized()
    dense = []
    m = len(pts3)
    for i in range(m):
        a, b = Vector(pts3[i]), Vector(pts3[(i + 1) % m])
        k = max(1, int(math.ceil((b - a).length / step)))
        dense += [a.lerp(b, q / k) for q in range(k)]
    out = []
    for p in dense:
        h = surf.hit(p + d * back, -d, back * 2.0)
        if h is not None:
            out.append(h)
    return out


def frame(name, path, section, m, inward=None):
    """A section [(s, h)] swept round a closed path of (point, normal): s runs across the skin AWAY from the opening,
    h stands off the skin. inward: a point inside the opening (default: the path's middle)."""
    P = [p for p, _n in path]
    c = Vector(inward) if inward is not None else sum(P, Vector()) / len(P)
    rings_ = []
    k = len(P)
    for i in range(k):
        t = (P[(i + 1) % k] - P[i - 1]).normalized()
        n = path[i][1]
        b = n.cross(t)
        b.normalize()
        if b.dot(P[i] - c) < 0.0:
            b = -b
        rings_.append([P[i] + b * s + n * h for s, h in section])
    return finish_smooth(hs.rings(name, rings_ + [rings_[0]], caps=False), m)


def screws(name, path, m, s=12.0, h=3.4, pitch=55.0, r=4.2, proud=1.7, inward=None):
    """Dome heads along a frame: every `pitch` mm of the path, s across from the opening's edge, standing on h."""
    P = [p for p, _n in path]
    c = Vector(inward) if inward is not None else sum(P, Vector()) / len(P)
    k = len(P)
    skins_, run, nxt = [], 0.0, pitch * 0.5
    for i in range(k):
        seg = (P[(i + 1) % k] - P[i]).length
        while run + seg >= nxt:
            f = (nxt - run) / seg
            p = P[i].lerp(P[(i + 1) % k], f)
            t = (P[(i + 1) % k] - P[i]).normalized()
            n = path[i][1]
            b = n.cross(t).normalized()
            if b.dot(p - c) < 0.0:
                b = -b
            at = p + b * s + n * (h - 0.4)
            skins_.append([hs.circle(at, n, r, 0.0, 10), hs.circle(at, n, r * 0.92, proud * 0.55, 10),
                           hs.circle(at, n, r * 0.5, proud, 10)])
            nxt += pitch
        run += seg
    return finish_smooth(hs.skins(name, skins_), m) if skins_ else None


def pane(name, solid, surf, cutter, m, set_in=5.0, thick=7.0):
    """The skin's own patch inside an opening: `solid` (a fresh copy of the uncut skin) cut down to what the cutter
    holds, only its outside faces kept (within 3 mm of the asked skin and facing as it does), moved in by set_in along
    their normals and given a thickness."""
    o = hs.boolean(solid, cutter, 'INTERSECT')
    o.name = name
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    drop = []
    for f in bm.faces:
        c = f.calc_center_median() / MM
        _loc, nrm, dist = surf.near(c)
        if dist > 3.0 or nrm.dot(f.normal) < 0.8:
            drop.append(f)
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    for v in bm.verts:
        v.co -= v.normal * set_in * MM
    bm.normal_update()
    verts, faces = list(bm.verts), list(bm.faces)
    rim = [e for e in bm.edges if len(e.link_faces) == 1]
    twin = {v: bm.verts.new(v.co - v.normal * thick * MM) for v in verts}       # its inside face, a thickness in
    for f in faces:
        bm.faces.new([twin[v] for v in reversed(f.verts)])
    for e in rim:
        a, b = e.verts
        bm.faces.new((a, b, twin[b], twin[a]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    return finish_smooth(o, m)


def blade_data(o, n_ring, chord_of, span_of, name='blade'):
    """A ring skin's own coordinates on its vertices, for its material: the colour attribute `name` with R the chord
    (0 at the leading edge .. 1 at the trailing) and G the span (0 at the root .. 1 at the tip). The rings were laid
    in order, n_ring points each; chord_of(i) and span_of(ring index) give the two numbers."""
    me = o.data
    ca = me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        ca.data[v.index].color = (chord_of(v.index % n_ring), span_of(v.index // n_ring), 0.0, 1.0)


def loft_body(name, body, xs, front=None, back=None):
    """A sections.Body as one closed skin over the stations xs; front / back: closing rings [(x, scale[, width
    scale])] before the first station and after the last."""
    def closing(x_at, e):
        x, s = e[0], e[1]
        return [(x,) + p[1:] for p in body.ring(x_at, s, scale_y=(e[2] if len(e) > 2 else None))]
    rings_ = [closing(xs[0], e) for e in (front or [])]
    rings_ += [body.ring(x) for x in xs]
    rings_ += [closing(xs[-1], e) for e in (back or [])]
    return hs.rings(name, rings_)
