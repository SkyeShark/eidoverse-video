"""eidoblend.sets.town.mb: the town's mesh builder. Blender (mathutils; bpy only in mesh()).

Every mesh of the town is written face by face from its construction's own numbers (a wall from its bays and the
openings reserved in it first, a tank turned from its profile), not modelled and then cut. Metres throughout.

    from eidoblend.sets.town.mb import MB, place, catenary, arc
    b = MB();  b.box(...), b.prism(...), b.lathe(...), b.run(...) ...;  me = b.mesh('name', material_of_name)

A face carries its material's NAME (eidoblend.sets.town.materials makes the material) and whether it shades smooth.
Flat things get their own vertices, so a flat face stays flat; turned and lofted things share theirs, so a tank is
round. place(at, rz, rx, ry, s) is a placing matrix; catenary(a, b, sag) a slack line's points; arc(c, r, a0, a1, n)
points on an arc in plan.
"""
import math

import bpy
from mathutils import Matrix, Vector

FACES = (('z-', (0, 3, 2, 1)), ('z+', (4, 5, 6, 7)), ('y-', (0, 1, 5, 4)), ('x+', (1, 2, 6, 5)), ('y+', (2, 3, 7, 6)), ('x-', (3, 0, 4, 7)))


def rot_z(a):
    return Matrix.Rotation(a, 4, 'Z')


def place(at, rz=0.0, rx=0.0, ry=0.0, s=1.0):
    """a placing: turned about x, then y, then z, scaled, then moved to `at`"""
    M = Matrix.Translation(Vector(at)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Rotation(ry, 4, 'Y') @ Matrix.Rotation(rx, 4, 'X')
    if s != 1.0:
        M = M @ Matrix.Scale(s, 4)
    return M


class MB:
    """a mesh being built"""

    def __init__(self):
        self.v, self.f, self.m, self.s, self.uv = [], [], [], [], {}

    # ------------------------------------------------------------------ raw
    def verts(self, pts):
        i = len(self.v)
        self.v.extend((p[0], p[1], p[2]) for p in pts)
        return i

    def face(self, idx, m, smooth=False):
        self.f.append(tuple(idx))
        self.m.append(m)
        self.s.append(smooth)

    def poly(self, pts, m, smooth=False, uv=None):
        pts = list(pts)
        if len(pts) < 3:
            return
        i = self.verts(pts)
        self.face(range(i, i + len(pts)), m, smooth)
        if uv:
            self.uv[len(self.f) - 1] = uv

    def quad(self, a, b, c, d, m, uv=None):
        self.poly((a, b, c, d), m, False, uv)

    def stamp(self, other, M=None):
        """another builder's faces, placed by M"""
        i = len(self.v)
        if M is None:
            self.v.extend(other.v)
        else:
            self.v.extend(tuple(M @ Vector(p)) for p in other.v)
        n = len(self.f)
        self.f.extend(tuple(k + i for k in f) for f in other.f)
        self.m.extend(other.m)
        self.s.extend(other.s)
        for k, uv in other.uv.items():
            self.uv[n + k] = uv

    # ------------------------------------------------------------------ flat-faced solids
    def hexa(self, p, m, skip='', top=None, mats=None):
        """a six-faced solid on eight corners in a box's order: the bottom four round, then the top four above them"""
        for k, idx in FACES:
            if k in skip:
                continue
            self.poly([p[i] for i in idx], (mats or {}).get(k) or (top if (k == 'z+' and top) else m))

    def box(self, lo, hi, m, skip='', top=None, mats=None, M=None):
        """a box between two corners. skip: the faces nobody can see ('z-', 'y+x-' ...); M: a placing"""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        if M is not None:
            p = [M @ Vector(q) for q in p]
        self.hexa(p, m, skip, top, mats)

    def beam(self, a, b, w, h, m, up=(0.0, 0.0, 1.0), caps=True):
        """a bar of section w x h from a to b (an angle-iron leg, a rail, a brace): h stands along `up`"""
        a, b = Vector(a), Vector(b)
        t = b - a
        if t.length < 1e-6:
            return
        t.normalize()
        u = Vector(up)
        s = t.cross(u)
        if s.length < 1e-4:
            s = t.cross(Vector((1.0, 0.0, 0.0)))
        s.normalize()
        u = s.cross(t)
        s, u = s * (w / 2.0), u * (h / 2.0)
        p = [a - s - u, a + s - u, b + s - u, b - s - u, a - s + u, a + s + u, b + s + u, b - s + u]
        # (box order with the bar's length as y: its ends are the 'y-' and 'y+' faces)
        self.hexa(p, m, '' if caps else 'y-y+')

    def prism(self, outline, z0, z1, m, top=None, bottom=None, cap_top=True, cap_bot=True, sides=None, side_m=None):
        """an outline [(x, y)], counter-clockwise from above, from z0 up to z1. sides: which of its edges get a wall"""
        n = len(outline)
        if cap_top:
            self.poly([(x, y, z1) for x, y in outline], top or m)
        if cap_bot:
            self.poly([(x, y, z0) for x, y in reversed(outline)], bottom or m)
        for k in range(n):
            if sides is not None and not sides[k]:
                continue
            (xa, ya), (xb, yb) = outline[k], outline[(k + 1) % n]
            if abs(xa - xb) + abs(ya - yb) < 1e-6:
                continue
            self.quad((xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1), side_m or m)

    def plate(self, outline, M, thick, top, side, bottom=None):
        """a broken piece of slab or wall: an outline [(x, y)] in its own plane (counter-clockwise), `thick` below it,
        placed by M (hanging by its steel, lying on a heap)"""
        up = [M @ Vector((x, y, 0.0)) for x, y in outline]
        dn = [M @ Vector((x, y, -thick)) for x, y in outline]
        n = len(outline)
        self.poly(up, top)
        self.poly(reversed(dn), bottom or side)
        for k in range(n):
            j = (k + 1) % n
            self.quad(dn[k], dn[j], up[j], up[k], side)

    # ------------------------------------------------------------------ smooth surfaces (shared vertices)
    def grid(self, P, m, smooth=True, wrap_u=False, wrap_v=False, flip=False):
        """a skin over rows of points P[row][column]; wrap_u: each row is a closed ring"""
        nv, nu = len(P), len(P[0])
        base = self.verts([p for row in P for p in row])
        for j in range(nv - (0 if wrap_v else 1)):
            for i in range(nu - (0 if wrap_u else 1)):
                a, b = base + j * nu + i, base + j * nu + (i + 1) % nu
                c, d = base + ((j + 1) % nv) * nu + (i + 1) % nu, base + ((j + 1) % nv) * nu + i
                self.face((a, d, c, b) if flip else (a, b, c, d), m, smooth)
        return base

    def lathe(self, prof, c, m, n=12, smooth=True, cap0=None, cap1=None, phase=0.0, M=None):
        """a profile [(radius, height)], bottom to top, turned about the vertical through c. cap0, cap1:
        materials for its bottom and top discs. M: a placing (a tank lying down, a dome's finial leaning)"""
        P = []
        for r, z in prof:
            r = max(r, 0.002)
            ring = [(c[0] + r * math.cos(phase + 2 * math.pi * k / n), c[1] + r * math.sin(phase + 2 * math.pi * k / n), c[2] + z) for k in range(n)]
            P.append([M @ Vector(q) for q in ring] if M is not None else ring)
        self.grid(P, m, smooth, wrap_u=True)
        if cap0:
            self.poly(reversed(P[0]), cap0)
        if cap1:
            self.poly(P[-1], cap1)

    def tube(self, a, b, r, m, n=8, r1=None, caps=True, smooth=True):
        """a round bar from a to b (a pole, a pipe, a leg); r1: its radius at b"""
        self.path([a, b], r, m, n, r1=r1, caps=caps, smooth=smooth)

    def path(self, pts, r, m, n=6, r1=None, caps=False, smooth=True):
        """a round section carried along a line of points (a wire, a bent bar, a trunk): the frame is carried from
        point to point without spinning"""
        P = [Vector(p) for p in pts]
        if len(P) < 2:
            return
        T = [(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]) for i in range(len(P))]
        T = [t.normalized() if t.length > 1e-9 else Vector((0.0, 0.0, 1.0)) for t in T]
        u = T[0].orthogonal().normalized()
        rings = []
        for i, t in enumerate(T):
            u = (u - t * u.dot(t))
            u = u.normalized() if u.length > 1e-6 else t.orthogonal().normalized()
            w = t.cross(u)
            rr = r if r1 is None else r + (r1 - r) * i / (len(P) - 1)
            if callable(r):
                rr = r(i / (len(P) - 1))
            rings.append([P[i] + (u * math.cos(2 * math.pi * k / n) + w * math.sin(2 * math.pi * k / n)) * rr for k in range(n)])
        self.grid(rings, m, smooth and n > 4, wrap_u=True)
        if caps:
            self.poly(reversed(rings[0]), m)
            self.poly(rings[-1], m)

    # ------------------------------------------------------------------ a wall run in plan (parapets, kerbs, yard walls)
    def run(self, pts, t, z0, z1, m, closed=False, top=None, inner=None, ends=(True, True), skip_outer=False):
        """a wall of thickness t standing on a line of points [(x, y)] from z0 to z1, built to the LEFT of the line as
        it is walked (walk a roof's edge counter-clockwise and the parapet stands inside it), mitred at every corner
        so nothing overlaps (no pushed-together boxes). inner: the material of its inner face; ends: whether an
        open run's two ends are closed"""
        P = [Vector((p[0], p[1])) for p in pts]
        if closed and (P[0] - P[-1]).length < 1e-6:
            P.pop()
        n = len(P)
        if n < 2:
            return
        seg = n if closed else n - 1
        D = [(P[(k + 1) % n] - P[k]) for k in range(seg)]
        D = [d.normalized() if d.length > 1e-9 else Vector((1.0, 0.0)) for d in D]
        N = [Vector((-d.y, d.x)) for d in D]                        # left of the walk
        I = []
        for k in range(n):
            if closed:
                n0, n1 = N[(k - 1) % seg], N[k % seg]
            else:
                n0, n1 = N[max(k - 1, 0)], N[min(k, seg - 1)]
            den = 1.0 + n0.dot(n1)
            I.append(P[k] + (n0 + n1) * (t / den) if den > 0.05 else P[k] + n1 * t)
        top = top or m
        inner = inner or m
        for k in range(seg):
            j = (k + 1) % n
            a, b_, ia, ib = P[k], P[j], I[k], I[j]
            if not skip_outer:
                self.quad((a.x, a.y, z0), (b_.x, b_.y, z0), (b_.x, b_.y, z1), (a.x, a.y, z1), m)
            self.quad((ib.x, ib.y, z0), (ia.x, ia.y, z0), (ia.x, ia.y, z1), (ib.x, ib.y, z1), inner)
            self.quad((a.x, a.y, z1), (b_.x, b_.y, z1), (ib.x, ib.y, z1), (ia.x, ia.y, z1), top)
        if not closed:
            if ends[0]:
                a, ia = P[0], I[0]
                self.quad((ia.x, ia.y, z0), (a.x, a.y, z0), (a.x, a.y, z1), (ia.x, ia.y, z1), m)
            if ends[1]:
                a, ia = P[-1], I[-1]
                self.quad((a.x, a.y, z0), (ia.x, ia.y, z0), (ia.x, ia.y, z1), (a.x, a.y, z1), m)

    # ------------------------------------------------------------------ out
    def count(self):
        return len(self.f)

    def mesh(self, name, material):
        """-> a bpy mesh; material(name) gives each face's material"""
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        slot = {}
        for m in self.m:
            if m not in slot:
                slot[m] = len(slot)
                me.materials.append(material(m))
        me.polygons.foreach_set('material_index', [slot[m] for m in self.m])
        me.polygons.foreach_set('use_smooth', self.s)
        if self.uv:
            uvl = me.uv_layers.new(name='UVMap')
            for fi, uv in self.uv.items():
                for k, li in enumerate(me.polygons[fi].loop_indices):
                    uvl.data[li].uv = uv[k % len(uv)]
        me.update()
        return me


def arc(c, r, a0, a1, n):
    """points on an arc in plan, degrees"""
    return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def catenary(a, b, sag, n=8):
    """a slack line's points between two points, hanging `sag` at its middle"""
    a, b = Vector(a), Vector(b)
    return [a.lerp(b, k / n) - Vector((0.0, 0.0, sag * (1.0 - (2.0 * k / n - 1.0) ** 2))) for k in range(n + 1)]
