# tgeo.py - geometry toolkit for the DAISY tandem (Blender 5.2, bmesh + curves).
#
# All positions are authored in the BIKE frame used by tandem.js / three.js:
#   +X = direction of travel, +Y = up, +Z = the bike's right (drive) side.
# B() maps that into Blender's Z-up frame; the glTF exporter (+Y up) maps it straight back.
import bpy, bmesh, math
from mathutils import Vector, Matrix

TAU = math.pi * 2.0


def B(p):
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z=0.0):
    return Vector((x, y, z))


def sstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ─────────────────────────────── curve samplers ───────────────────────────────
def line_pts(a, b, n=2):
    return [a.lerp(b, i / (n - 1)) for i in range(n)]


def bezier3_pts(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n):
        t = i / (n - 1); u = 1 - t
        out.append(p0 * (u * u * u) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t * t * t))
    return out


def bezier2_pts(p0, p1, p2, n=16):
    out = []
    for i in range(n):
        t = i / (n - 1); u = 1 - t
        out.append(p0 * (u * u) + p1 * (2 * u * t) + p2 * (t * t))
    return out


def catmull_pts(ctrl, n_per=8, alpha=0.5):
    """Centripetal Catmull-Rom through ctrl (open), n_per samples per span."""
    P = [ctrl[0] + (ctrl[0] - ctrl[1])] + list(ctrl) + [ctrl[-1] + (ctrl[-1] - ctrl[-2])]
    out = []
    for k in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[k - 1], P[k], P[k + 1], P[k + 2]
        def tj(ti, pa, pb):
            return ti + max(1e-6, (pb - pa).length) ** alpha
        t0 = 0.0; t1 = tj(t0, p0, p1); t2 = tj(t1, p1, p2); t3 = tj(t2, p2, p3)
        for i in range(n_per):
            t = t1 + (t2 - t1) * i / n_per
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            out.append(b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1)))
    out.append(ctrl[-1].copy())
    return out


def helix_pts(center, radius, height, turns, axis=None, n=160, phase=0.0):
    up = (axis or V(0, 1, 0)).normalized()
    t1 = V(1, 0, 0)
    if abs(t1.dot(up)) > 0.9:
        t1 = V(0, 0, 1)
    t1 = (t1 - up * t1.dot(up)).normalized()
    t2 = up.cross(t1)
    out = []
    for i in range(n):
        t = i / (n - 1)
        a = phase + t * turns * TAU
        out.append(center + t1 * (math.cos(a) * radius) + t2 * (math.sin(a) * radius) + up * ((t - 0.5) * height))
    return out


def resample(pts, spacing):
    """Uniformly resample a polyline so long straight runs keep few rings and curves keep many."""
    L = [0.0]
    for i in range(1, len(pts)):
        L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    n = max(2, int(math.ceil(L[-1] / spacing)) + 1)
    out, k = [], 0
    for i in range(n):
        s = L[-1] * i / (n - 1)
        while k < len(L) - 2 and L[k + 1] < s:
            k += 1
        seg = max(1e-9, L[k + 1] - L[k])
        out.append(pts[k].lerp(pts[k + 1], (s - L[k]) / seg))
    return out


# ─────────────────────────────── mesh builder ─────────────────────────────────
class MB:
    """bmesh accumulator with two UV layers: UVMap (atlas, packed later) and TubeUV (metres along, 0..1 around)."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.tuv = self.bm.loops.layers.uv.new('TubeUV')
        self.trail = None

    def vert(self, p):
        return self.bm.verts.new(B(p))

    def face(self, vs, uvs=None, tuvs=None, smooth=True):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.smooth = smooth
        if uvs:
            for l, uv in zip(f.loops, uvs):
                l[self.uv].uv = uv
        if tuvs:
            for l, uv in zip(f.loops, tuvs):
                l[self.tuv].uv = uv
        return f

    def object(self, coll, sharp_angle=None):
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(self.name, me)
        coll.objects.link(ob)
        if sharp_angle is not None:
            me.set_sharp_from_angle(angle=math.radians(sharp_angle))
        return ob


def sweep(mb, pts, r, radial=16, oval=(1.0, 1.0), ref=V(0, 0, 1), cap0=False, cap1=False, twist=0.0,
          smooth=True, trail_axis=None):
    """Sweep a (possibly oval, tapered) section along pts. r: float | fn(t) | list.
    UVMap = (metres along, metres around); TubeUV = (metres along, 0..1 around; 0 at the +ref side)."""
    n = len(pts)
    T = []
    for i in range(n):
        a = pts[max(0, i - 1)]; b = pts[min(n - 1, i + 1)]
        d = b - a
        T.append(d.normalized() if d.length > 1e-12 else V(1, 0, 0))
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    total = max(L[-1], 1e-9)
    refv = Vector(ref)
    rings = []
    for i in range(n):
        t = L[i] / total
        rr = r(t) if callable(r) else (r[i] if isinstance(r, (list, tuple)) else r)
        N = refv - T[i] * refv.dot(T[i])
        if N.length < 1e-6:
            N = V(0, 1, 0) - T[i] * T[i].y
            if N.length < 1e-6:
                N = V(1, 0, 0) - T[i] * T[i].x
        N.normalize()
        Bv = N.cross(T[i]).normalized()
        ring = []
        for j in range(radial):
            a = TAU * j / radial + twist
            off = N * (math.cos(a) * oval[0] * rr) + Bv * (math.sin(a) * oval[1] * rr)
            ring.append(mb.vert(pts[i] + off))
        rings.append((ring, rr, N, Bv))
    faces = []
    for i in range(n - 1):
        ra, rb = rings[i], rings[i + 1]
        circ_a = TAU * ra[1] * (oval[0] + oval[1]) * 0.5
        circ_b = TAU * rb[1] * (oval[0] + oval[1]) * 0.5
        for j in range(radial):
            j1 = (j + 1) % radial
            v0, v1 = j / radial, (j + 1) / radial
            f = mb.face([ra[0][j], rb[0][j], rb[0][j1], ra[0][j1]],
                        uvs=[(L[i], v0 * circ_a), (L[i + 1], v0 * circ_b), (L[i + 1], v1 * circ_b), (L[i], v1 * circ_a)],
                        tuvs=[(L[i], v0), (L[i + 1], v0), (L[i + 1], v1), (L[i], v1)], smooth=smooth)
            if f:
                faces.append(f)
    def cap(idx, flip):
        ring, rr, N, Bv = rings[idx]
        c = mb.vert(pts[idx])
        for j in range(radial):
            j1 = (j + 1) % radial
            a0, a1 = TAU * j / radial, TAU * j1 / radial
            uvc = (0.0, 0.0)
            uv0 = (math.cos(a0) * rr, math.sin(a0) * rr)
            uv1 = (math.cos(a1) * rr, math.sin(a1) * rr)
            if flip:
                mb.face([c, ring[j1], ring[j]], uvs=[uvc, uv1, uv0], tuvs=[(L[idx], 0.5)] * 3, smooth=False)
            else:
                mb.face([c, ring[j], ring[j1]], uvs=[uvc, uv0, uv1], tuvs=[(L[idx], 0.5)] * 3, smooth=False)
    if cap0:
        cap(0, False)
    if cap1:
        cap(n - 1, True)
    return rings


def lathe(mb, prof, segs=48, center=V(0, 0, 0), axis='z', smooth=True, phase=0.0, closed=False):
    """Revolve prof [(r, h), ...] about an axis through center. axis: 'z' (bike lateral), 'y', or a Vector.
    For a profile running +h at its outer wall the normals face outward."""
    if isinstance(axis, str):
        ax = {'z': V(0, 0, 1), 'y': V(0, 1, 0), 'x': V(1, 0, 0)}[axis]
    else:
        ax = axis.normalized()
    e1 = V(1, 0, 0) if abs(ax.x) < 0.9 else V(0, 1, 0)
    e1 = (e1 - ax * e1.dot(ax)).normalized()
    e2 = ax.cross(e1)
    P = list(prof)
    if closed and (P[0][0] != P[-1][0] or P[0][1] != P[-1][1]):
        P.append(P[0])
    arc = [0.0]
    for i in range(1, len(P)):
        arc.append(arc[-1] + math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]))
    grid = []
    for i, (r, h) in enumerate(P):
        if r < 1e-7:
            v = mb.vert(center + ax * h)
            grid.append([v] * segs)
            continue
        row = []
        for j in range(segs):
            a = phase + TAU * j / segs
            row.append(mb.vert(center + ax * h + e1 * (math.cos(a) * r) + e2 * (math.sin(a) * r)))
        grid.append(row)
    for i in range(len(P) - 1):
        ra, rb = P[i][0], P[i + 1][0]
        for j in range(segs):
            j1 = (j + 1) % segs
            u0, u1 = j / segs, (j + 1) / segs
            ca, cb = TAU * max(ra, 1e-4), TAU * max(rb, 1e-4)
            quad = [grid[i][j], grid[i][j1], grid[i + 1][j1], grid[i + 1][j]]
            uv = [(u0 * ca, arc[i]), (u1 * ca, arc[i]), (u1 * cb, arc[i + 1]), (u0 * cb, arc[i + 1])]
            tu = [(arc[i], u0), (arc[i], u1), (arc[i + 1], u1), (arc[i + 1], u0)]
            # collapse degenerate corners (poles)
            keep = [k for k in range(4) if quad[k] not in quad[:k]]
            if len(keep) < 3:
                continue
            mb.face([quad[k] for k in keep], uvs=[uv[k] for k in keep], tuvs=[tu[k] for k in keep], smooth=smooth)
    return grid


# ─────────────────────────────── curves (2D plates) ───────────────────────────
_COLL = None


def set_coll(c):
    global _COLL
    _COLL = c


def plate(name, loops, depth, bevel=0.0006, bevel_res=2, xf=None):
    """Extrude 2D outline loops (outer + holes, lists of (x, y)) into a bevelled solid via a curve,
    then return an MB holding the mesh transformed by xf (a function mapping local Vector -> bike Vector)."""
    cu = bpy.data.curves.new(name + '_cu', 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    cu.extrude = max(0.0, depth / 2 - bevel)
    cu.bevel_depth = bevel
    cu.bevel_resolution = bevel_res
    cu.resolution_u = 1
    for lp in loops:
        sp = cu.splines.new('POLY')
        sp.points.add(len(lp) - 1)
        for k, (x, y) in enumerate(lp):
            sp.points[k].co = (x, y, 0.0, 1.0)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name + '_tmp', cu)
    _COLL.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    mb = MB(name)
    bm2 = bmesh.new()
    bm2.from_mesh(me)
    bpy.data.meshes.remove(me)
    vmap = {}
    for v in bm2.verts:
        p = Vector((v.co.x, v.co.y, v.co.z))
        q = xf(p) if xf else p
        vmap[v] = mb.vert(q)
    for f in bm2.faces:
        vs = [vmap[l.vert] for l in f.loops]
        uvs = [((l.vert.co.x), (l.vert.co.y)) for l in f.loops]
        # side faces get a better (length, depth) mapping
        n = f.normal
        if abs(n.z) < 0.5:
            uvs = [((l.vert.co.x + l.vert.co.y), l.vert.co.z) for l in f.loops]
        mb.face(vs, uvs=uvs, tuvs=[(0.0, 0.0)] * len(vs), smooth=True)
    bm2.free()
    return mb


def merge_into(dst, src):
    """Append src MB geometry into dst MB (both still open)."""
    me = bpy.data.meshes.new('_tmp_merge')
    src.bm.to_mesh(me)
    src.bm.free()
    bm2 = bmesh.new()
    bm2.from_mesh(me)
    bpy.data.meshes.remove(me)
    uvA = bm2.loops.layers.uv.get('UVMap')
    uvT = bm2.loops.layers.uv.get('TubeUV')
    vmap = {}
    for v in bm2.verts:
        vmap[v] = dst.bm.verts.new(v.co)
    for f in bm2.faces:
        try:
            nf = dst.bm.faces.new([vmap[l.vert] for l in f.loops])
        except ValueError:
            continue
        nf.smooth = f.smooth
        for l_src, l_dst in zip(f.loops, nf.loops):
            if uvA:
                l_dst[dst.uv].uv = l_src[uvA].uv
            if uvT:
                l_dst[dst.tuv].uv = l_src[uvT].uv
    bm2.free()


def mesh_object_from_mb(mb, coll, sharp=40):
    return mb.object(coll, sharp_angle=sharp)


# ─────────────────────────────── modifiers ────────────────────────────────────
def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def boolean_union(target, others, solver='EXACT'):
    for o in others:
        m = target.modifiers.new('u_' + o.name, 'BOOLEAN')
        m.operation = 'UNION'
        m.object = o
        m.solver = solver
    apply_mods(target)
    for o in others:
        me = o.data
        bpy.data.objects.remove(o)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return target


def bevel_mod(ob, width=0.0012, segments=3, angle=30.0, apply=True):
    m = ob.modifiers.new('bevel', 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.use_clamp_overlap = True
    m.harden_normals = False
    if apply:
        apply_mods(ob)
    return ob


def shade(ob, angle=40.0):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(angle))
    return ob
