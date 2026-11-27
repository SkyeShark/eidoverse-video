"""eidoblend.props.houseplants.kit: build helpers for what grows and what is moulded, on the hard-surface kit
(eidoblend.props.hardsurface.masses). Millimetres in every table; the scene is in metres.

The hard-surface kit builds machined and welded things: one mass, one bevel per edge group. A plant also needs:
    soft(o, m)                    finish a grown or moulded part: welded, smooth, sharp only where its surface turns
    pt_frames(path, up0)          rotation-minimising frames that START from a chosen normal (a leaf has an upper side)
    limb_rings                    a stem, a petiole, a spout: sections carried along a path, its ends closed round
    Skin + thicken()              a leaf blade: ONE skin with its own top and bottom distances at every point, made a
                                  closed thin solid (the midrib sunk above, proud beneath)
    loops                         many closed loops (ring lists) in one object: wire ties, beads
    lumps                         the top of what fills a pot: soil in clods, crowned, heaped round each stem
    table / spline / resample     profile tables read smoothly, curves through points, even arc length
    hash01 / sgn01 / vnoise       one stream per thing, from its own integers (no shared random stream)
"""

import math

import bmesh
from mathutils import Quaternion, Vector

from ..hardsurface import masses as hs

MM = hs.MM


def V3(x, y, z):
    return Vector((x, y, z))


# ---------------------------------------------------------------------------- numbers that are the same every run
def hash01(*k):
    h = 2166136261
    for v in k:
        h = ((h ^ (int(v) & 0xffffffff)) * 16777619) & 0xffffffff
        h ^= h >> 15
        h = (h * 2246822519) & 0xffffffff
        h ^= h >> 13
    return h / 4294967296.0


def sgn01(*k):
    """-1 .. 1"""
    return hash01(*k) * 2.0 - 1.0


def vnoise(x, y, seed=0):
    """smooth value noise, 0 .. 1, one cell a unit"""
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = x - xi, y - yi
    fx, fy = fx * fx * (3.0 - 2.0 * fx), fy * fy * (3.0 - 2.0 * fy)
    a, b = hash01(xi, yi, seed), hash01(xi + 1, yi, seed)
    c, d = hash01(xi, yi + 1, seed), hash01(xi + 1, yi + 1, seed)
    return (a + (b - a) * fx) * (1.0 - fy) + (c + (d - c) * fx) * fy


def smooth(x, lo=0.0, hi=1.0):
    t = min(1.0, max(0.0, (x - lo) / (hi - lo))) if hi != lo else float(x >= hi)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def table(pts, x):
    """a profile table [(x, y)] read at x by a monotone cubic: smooth through its rows, no overshoot between them (a
    leaf's outline has no bulge its table does not have)"""
    n = len(pts)
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    i = 0
    while pts[i + 1][0] < x:
        i += 1

    def slope(k):
        if k == 0 or k == n - 1:
            j = 0 if k == 0 else n - 2
            return (pts[j + 1][1] - pts[j][1]) / (pts[j + 1][0] - pts[j][0])
        h0, h1 = pts[k][0] - pts[k - 1][0], pts[k + 1][0] - pts[k][0]
        d0, d1 = (pts[k][1] - pts[k - 1][1]) / h0, (pts[k + 1][1] - pts[k][1]) / h1
        if d0 * d1 <= 0.0:
            return 0.0
        w1, w2 = 2.0 * h1 + h0, h1 + 2.0 * h0
        return (w1 + w2) / (w1 / d0 + w2 / d1)
    (x0, y0), (x1, y1) = pts[i], pts[i + 1]
    h = x1 - x0
    t = (x - x0) / h
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * y0 + (t3 - 2 * t2 + t) * h * slope(i) + (-2 * t3 + 3 * t2) * y1 + (t3 - t2) * h * slope(i + 1)


def round_noise(k, n, z, seed=0, reach=2.3):
    """smooth noise round a turned form, 0 .. 1: the k-th of n points of a ring at height z (in cells). Read on the
    ring's DIRECTION, not on its angle, so it has no seam where the ring closes"""
    a = 2.0 * math.pi * k / n
    return vnoise(math.cos(a) * reach + z + 40.0, math.sin(a) * reach - 0.45 * z + 40.0, seed)


def spline(pts, n):
    """a centripetal Catmull-Rom curve through points (any dimension as Vectors), n pieces a span"""
    P = [Vector(p) for p in pts]
    if len(P) < 3:
        return [P[0].lerp(P[-1], i / n) for i in range(n + 1)]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0.0
        t1 = t0 + max((p1 - p0).length, 1e-9) ** 0.5
        t2 = t1 + max((p2 - p1).length, 1e-9) ** 0.5
        t3 = t2 + max((p3 - p2).length, 1e-9) ** 0.5
        for k in range(n):
            t = t1 + (t2 - t1) * k / n
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            out.append(b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1)))
    out.append(P[-2].copy())
    return out


def arc_lengths(path):
    L = [0.0]
    for a, b in zip(path, path[1:]):
        L.append(L[-1] + (Vector(b) - Vector(a)).length)
    return L


def resample(path, step):
    """a polyline at even arc length, no piece longer than step"""
    P = [Vector(p) for p in path]
    L = arc_lengths(P)
    n = max(1, int(math.ceil(L[-1] / step)))
    out, j = [], 0
    for i in range(n + 1):
        d = L[-1] * i / n
        while j < len(P) - 2 and L[j + 1] < d:
            j += 1
        seg = L[j + 1] - L[j]
        out.append(P[j].lerp(P[j + 1], (d - L[j]) / seg if seg > 1e-12 else 0.0))
    return out


# ---------------------------------------------------------------------------------------------- frames, limbs
def pt_frames(path, up0=(0, 0, 1)):
    """rotation-minimising frames along a polyline, the first normal leaning to up0:
    [(point, tangent, normal, binormal = tangent x normal)]"""
    P = [Vector(p) for p in path]
    k = len(P)
    T = [(P[min(i + 1, k - 1)] - P[max(i - 1, 0)]).normalized() for i in range(k)]
    u = Vector(up0)
    n = u - T[0] * u.dot(T[0])
    if n.length < 1e-6:
        n = T[0].orthogonal()
    n.normalize()
    out = []
    for i, t in enumerate(T):
        if i:
            ax = T[i - 1].cross(t)
            if ax.length > 1e-9:
                n = Quaternion(ax.normalized(), T[i - 1].angle(t)) @ n
        n = (n - t * n.dot(t)).normalized()
        out.append((P[i], t, n, t.cross(n)))
    return out


def round_sect(r, seg=12, squash=1.0, flat=0.0):
    """a round section [(along the normal, along the binormal)]; squash: the normal's radius over the binormal's;
    flat: how far its upper side (the normal's) is pressed in, 0 .. 1 (a petiole's channel)"""
    out = []
    for k in range(seg):
        a = 2.0 * math.pi * k / seg
        u, v = math.cos(a) * r * squash, math.sin(a) * r
        if flat and u > 0.0:
            u *= 1.0 - flat * (math.cos(a) ** 2)
        out.append((u, v))
    return out


def limb_rings(path, radius, seg=12, up0=(0, 0, 1), squash=1.0, flat=0.0, caps=(0.0, 0.0)):
    """rings of a round section carried along a path. radius, squash, flat: a number, or a function of the arc
    fraction 0 .. 1 (a taper, a node's swelling, a petiole's channel that fades out); caps: how round each end is
    closed, as a share of its radius (0: a flat cut)"""
    P = [Vector(p) for p in path]
    L = arc_lengths(P)
    tot = L[-1] or 1.0
    fr = pt_frames(P, up0)

    def val(x, s):
        return x(s) if callable(x) else x

    def ring(p, n, b, r, s):
        return [p + n * u + b * v for u, v in round_sect(r, seg, val(squash, s), val(flat, s))]
    out = []
    for i, (p, t, n, b) in enumerate(fr):
        out.append(ring(p, n, b, val(radius, L[i] / tot), L[i] / tot))
    for end, share in ((0, caps[0]), (-1, caps[1])):
        if share <= 0.0:
            continue
        p, t, n, b = fr[end]
        s = 0.0 if end == 0 else 1.0
        r = val(radius, s)
        sg = -1.0 if end == 0 else 1.0
        dome = [ring(p + t * (sg * r * share * math.sin(a)), n, b, r * math.cos(a), s) for a in (math.radians(35), math.radians(62), math.radians(80))]
        out = (dome[::-1] + out) if end == 0 else (out + dome)
    return out


# --------------------------------------------------------------------------- finishing what is grown or moulded
def soft(o, m, sharp=40.0, weld=1e-6):
    """finish a grown or moulded part: welded, smooth-shaded, an edge sharp only where the surface really turns there
    (a rim, a cut end). No bevel and nothing dissolved: its curvature IS its form. Into the build's collection."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=weld)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    open_e = sum(1 for e in bm.edges if not e.is_manifold)
    if open_e:
        for e in [e for e in bm.edges if not e.is_manifold][:6]:
            m_ = (e.verts[0].co + e.verts[1].co) * 500.0
            print(f'    {o.name}: an edge with {len(e.link_faces)} faces at ({m_.x:.1f}, {m_.y:.1f}, {m_.z:.1f}) mm, {e.calc_length() * 1e3:.3f} mm long')
    vol = bm.calc_volume()
    lim = math.radians(sharp)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(o.data)
    bm.free()
    for c in list(o.users_collection):
        c.objects.unlink(o)
    hs.col.objects.link(o)
    o.data.materials.append(m)
    hs.REPORT.append((o.name, open_e, round(vol * 1e3, 3), len(o.data.polygons)))
    if open_e:
        print(f'PART {o.name}: OPEN EDGES {open_e}')
    return o


# ------------------------------------------------------------------------------------ thin curved solids: leaves
class Skin:
    """ONE skin of a thin thing (a leaf blade), points in mm. Each point carries how far the finished surface stands
    above it and below it (mm: the blade's thickness, the midrib's groove above and its ridge beneath) and four numbers
    a material reads (along the blade 0 .. 1, across it 0 .. 1 with 0.5 the midrib, which leaf, how old).
    Points at the same place are one point (a slit's two edges are one edge until the slit opens)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.top = self.bm.verts.layers.float.new('top')
        self.bot = self.bm.verts.layers.float.new('bot')
        self.dat = self.bm.verts.layers.float_color.new('leafdata')
        self.up = self.bm.verts.layers.float_vector.new('up')
        self.q = self.bm.verts.layers.float.new('q')
        self.seen = {}

    def point(self, p, top, bot, data=(0.0, 0.5, 0.0, 0.0), up=(0.0, 0.0, 1.0), q=0.0):
        """up: which way the blade's UPPER side looks there (the builder's own frame), so the solid's top is its top.
        q: where the point lies across its vein's field, -1 .. 1, 0 ON the vein (a Monstera's primary veins run down
        the middle of each field, its slits and holes between fields): data for the material, no form."""
        key = (round(p[0] * 2e3), round(p[1] * 2e3), round(p[2] * 2e3))        # a two-thousandth of a millimetre
        v = self.seen.get(key)
        if v is None:
            v = self.bm.verts.new((p[0] * MM, p[1] * MM, p[2] * MM))
            v[self.top], v[self.bot], v[self.dat], v[self.up], v[self.q] = top * MM, bot * MM, data, up, q
            self.seen[key] = v
        return v

    def proxy(self, keep=None):
        """the skin as points (m) and faces, for asking whether it would pass through a neighbour; keep(vertex's
        leafdata) picks the part that is asked about"""
        self.bm.verts.index_update()
        fs = [tuple(v.index for v in f.verts) for f in self.bm.faces if keep is None or all(keep(v[self.dat]) for v in f.verts)]
        return [v.co.copy() for v in self.bm.verts], fs

    def face(self, vs):
        """the points in order, counter-clockwise seen from ABOVE the blade"""
        u = []
        for v in vs:
            if v not in u:
                u.append(v)
        if len(u) < 3:
            return
        try:
            self.bm.faces.new(u)
        except ValueError:
            pass                                                # (the same face twice: two rays that are one ray)

    def grid(self, rows):
        """quads over rows of points (each row the same count); rows run ALONG the blade, a row's points go ACROSS it
        toward the binormal's side: wound so the normal is the frame's"""
        for a_, b_ in zip(rows, rows[1:]):
            for k in range(len(a_) - 1):
                self.face((a_[k], a_[k + 1], b_[k + 1], b_[k]))


def thicken(skin, into, flip=False):
    """the skin made a closed thin solid inside the bmesh `into` (many leaves, one object): every point moved along its
    normal by its own top and bottom distances, the rim walled. The leaves' data travels as the point attributes
    'leafdata' (along, across, which leaf, age; the underside's age below zero) and 'leafq' (the vein's field).
    -> the open edges it found in the skin's own inside (0 when the skin is a clean sheet)"""
    bm = skin.bm
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)          # one way round over the whole sheet ...
    bm.normal_update()
    vote = sum((1.0 if f.normal.dot(sum((v[skin.up] for v in f.verts), Vector())) > 0.0 else -1.0) * f.calc_area() for f in bm.faces)
    if vote < 0.0:                                             # ... and that way the builder's UP
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.normal_update()
    bm.verts.index_update()
    dat = into.verts.layers.float_color.get('leafdata') or into.verts.layers.float_color.new('leafdata')
    lq = into.verts.layers.float.get('leafq') or into.verts.layers.float.new('leafq')
    sg = -1.0 if flip else 1.0
    vt, vb = {}, {}
    for v in bm.verts:
        a = into.verts.new(v.co + v.normal * (sg * v[skin.top]))
        b = into.verts.new(v.co - v.normal * (sg * v[skin.bot]))
        a[dat] = v[skin.dat]
        a[lq] = b[lq] = v[skin.q]
        d = list(v[skin.dat])
        b[dat] = (d[0], d[1], d[2], -1.0 - d[3])                # (the underside: its age below zero, so a material can tell)
        vt[v.index], vb[v.index] = a, b
    bad = 0
    for f in bm.faces:
        into.faces.new([vt[v.index] for v in f.verts])
        into.faces.new([vb[v.index] for v in reversed(f.verts)])
    for e in bm.edges:
        k = len(e.link_faces)
        if k == 1:
            vs = list(e.link_faces[0].verts)
            i = vs.index(e.verts[0])
            a, b = (e.verts[0], e.verts[1]) if vs[(i + 1) % len(vs)] == e.verts[1] else (e.verts[1], e.verts[0])
            into.faces.new((vt[b.index], vt[a.index], vb[a.index], vb[b.index]))
        elif k != 2:
            bad += 1
    bm.free()
    return bad


def loops(name, ring_lists):
    """many closed loops (each a ring list whose last ring is its first) in ONE object: wire ties, beads"""
    bm = bmesh.new()
    for rl in ring_lists:
        V = [[bm.verts.new((p[0] * MM, p[1] * MM, p[2] * MM)) for p in r] for r in rl[:-1]]
        n = len(V[0])
        for i in range(len(V)):
            a_, b_ = V[i], V[(i + 1) % len(V)]
            for k in range(n):
                bm.faces.new((a_[k], a_[(k + 1) % n], b_[(k + 1) % n], b_[k]))
    return hs.obj(name, bm)


def lumps(name, at, r, z_top, z_bot, amp, cell, seed, rings=10, seg=40, crown=0.0, hole=None):
    """the top of what fills a pot: a disc of radius r whose surface rises and falls by amp (clods a `cell` across),
    crowned by `crown` at its middle, its side going down inside the pot to z_bot: one closed plug.
    hole: (x, y, radius) places where it is heaped a little round a stem."""
    C = Vector(at)
    rl = [[C + V3(r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z_bot) for k in range(seg)]]
    for i in range(rings, 0, -1):
        rr = r * i / rings
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            x, y = rr * math.cos(a), rr * math.sin(a)
            h = (vnoise(x / cell + 31.0, y / cell + 17.0, seed) - 0.5) * 2.0 * amp
            h += (vnoise(x / (cell * 0.37) + 5.0, y / (cell * 0.37) + 9.0, seed + 1) - 0.5) * amp * 0.7
            h *= smooth(r - rr, 0.0, r * 0.12) * 0.75 + 0.25                       # (it settles against the pot's wall)
            h += crown * (1.0 - (rr / r) ** 2)
            for hx, hy, hr in (hole or ()):
                d = math.hypot(x - hx, y - hy)
                h += amp * 0.9 * (1.0 - smooth(d, hr, hr * 2.6))                    # (heaped a little round each stem)
            ring.append(C + V3(x, y, z_top + h))
        rl.append(ring)
    return hs.rings(name, rl)
