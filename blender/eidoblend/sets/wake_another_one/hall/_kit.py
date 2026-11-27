"""The hall's geometry kit (private to the set): meshes that can carry a layered material.

The layout builds the hall from plain boxes and cylinders (one flat colour, no bevel, no UV). This kit turns such a mesh
into one a material can read, as one would prepare it for texturing:
  - every hard edge gets a real BEVEL (two segments, hardened normals), so a strip light has an arris to catch;
  - every face gets an INSET loop a wear-width in from its hard edges, and the vertex attribute `wear` runs 1 on the
    arris to 0 on that loop: edge wear has its own band of geometry, so no facet of the mask ever shows (the shader
    breaks it with fine noise);
  - the vertex attribute `cavity` is baked by ray casts (how much of the hemisphere over a vertex is closed within a few
    centimetres): where dust and grime gather;
  - a UV map in METRES (each face projected along its dominant axis), so a fetched scan lies at its real size.
The same primitives as the layout's (boxes, cylinders, quads) plus prisms (a section swept along an axis: channels,
angles, step beams), tubes and hexagon bolts. The edition's own hard-surface kit (eidoblend.props.hardsurface, baked
maps under eidoblend.materials.layered) is the way for a new prop; this one is the hall's own.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

PI = math.pi
SHARP = math.radians(50.0)


class MB:
    """a mesh from boxes, cylinders, prisms and quads; mi = material slot"""

    def __init__(self):
        self.v, self.f, self.mi, self.sm = [], [], [], []

    def box(self, c, s, mi=0, rz=0.0, rx=0.0, ry=0.0):
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        pts = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
               (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
        if rz or rx or ry:
            m = Matrix.Rotation(rz, 3, 'Z') @ Matrix.Rotation(ry, 3, 'Y') @ Matrix.Rotation(rx, 3, 'X')
            pts = [tuple(m @ Vector(p)) for p in pts]
        n = len(self.v)
        self.v += [(p[0] + c[0], p[1] + c[1], p[2] + c[2]) for p in pts]
        for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.f.append(tuple(n + i for i in q))
            self.mi.append(mi)
            self.sm.append(False)
        return self

    def span(self, lo, hi, mi=0):
        return self.box([(lo[i] + hi[i]) / 2 for i in range(3)], [abs(hi[i] - lo[i]) for i in range(3)], mi)

    def cyl(self, c, r, length, axis='x', n=16, mi=0, caps=True, r2=None):
        """a cylinder (r2: the radius at its far end, for a cone)"""
        n0 = len(self.v)
        for side, rr in ((-1, r), (1, r if r2 is None else r2)):
            d = side * length / 2
            for i in range(n):
                a, b = math.cos(2 * PI * i / n) * rr, math.sin(2 * PI * i / n) * rr
                p = (d, a, b) if axis == 'x' else (b, d, a) if axis == 'y' else (a, b, d)
                self.v.append((c[0] + p[0], c[1] + p[1], c[2] + p[2]))
        for i in range(n):
            j = (i + 1) % n
            self.f.append((n0 + i, n0 + j, n0 + n + j, n0 + n + i))
            self.mi.append(mi)
            self.sm.append(True)
        if caps:
            self.f.append(tuple(n0 + i for i in reversed(range(n))))
            self.f.append(tuple(n0 + n + i for i in range(n)))
            self.mi += [mi, mi]
            self.sm += [False, False]
        return self

    def prism(self, poly, a, b, axis='y', mi=0, at=(0.0, 0.0)):
        """the closed section `poly` [(u, v), ...] swept from a to b along `axis`; (u, v) is (x, z) for 'y', (y, z) for
        'x', (x, y) for 'z'; `at` is added to every (u, v)"""
        n0, k = len(self.v), len(poly)
        for d in (a, b):
            for u, v in poly:
                u, v = u + at[0], v + at[1]
                self.v.append((u, d, v) if axis == 'y' else (d, u, v) if axis == 'x' else (u, v, d))
        for i in range(k):
            j = (i + 1) % k
            self.f.append((n0 + i, n0 + j, n0 + k + j, n0 + k + i))
            self.mi.append(mi)
            self.sm.append(False)
        self.f.append(tuple(n0 + i for i in reversed(range(k))))
        self.f.append(tuple(n0 + k + i for i in range(k)))
        self.mi += [mi, mi]
        self.sm += [False, False]
        return self

    def bolt(self, c, r=0.009, h=0.007, axis='z', mi=0, washer=True):
        """a hexagon head (across corners 2 r) on a washer"""
        if washer:
            off = [0, 0, 0]
            off['xyz'.index(axis)] = -h / 2 - 0.001
            self.cyl((c[0] + off[0], c[1] + off[1], c[2] + off[2]), r * 1.45, 0.002, axis, 12, mi)
        return self.cyl(c, r, h, axis, 6, mi)

    def quad(self, pts, mi=0):
        n = len(self.v)
        self.v += [tuple(p) for p in pts]
        self.f.append((n, n + 1, n + 2, n + 3))
        self.mi.append(mi)
        self.sm.append(False)
        return self

    def tube(self, pts, r, n=10, mi=0, caps=True):
        """a round tube swept through the points `pts` (a conduit with its bends, a cable, a handle, a hose): one ring
        of n vertices at every point, mitred, the frame carried along without twist"""
        P = [Vector(p) for p in pts]
        k = len(P)
        tang = []
        for i in range(k):
            a = P[i] - P[i - 1] if i > 0 else P[1] - P[0]
            b = P[i + 1] - P[i] if i < k - 1 else P[k - 1] - P[k - 2]
            t = (a.normalized() + b.normalized())
            tang.append(t.normalized() if t.length > 1e-9 else a.normalized())
        up = Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0))
        u = tang[0].cross(up).normalized()
        n0 = len(self.v)
        for i in range(k):
            u = (u - tang[i] * u.dot(tang[i])).normalized()             # carried along: projected onto the new normal plane
            w = tang[i].cross(u)
            if 0 < i < k - 1:                                           # a mitre is wider than the tube by 1 / cos(half the bend)
                c = max(0.35, tang[i].dot((P[i] - P[i - 1]).normalized()))
            else:
                c = 1.0
            for j in range(n):
                a = 2 * PI * j / n
                p = P[i] + (u * math.cos(a) + w * math.sin(a)) * (r / c)
                self.v.append(tuple(p))
        for i in range(k - 1):
            for j in range(n):
                j2 = (j + 1) % n
                self.f.append((n0 + i * n + j, n0 + i * n + j2, n0 + (i + 1) * n + j2, n0 + (i + 1) * n + j))
                self.mi.append(mi)
                self.sm.append(True)
        if caps:
            self.f.append(tuple(n0 + j for j in reversed(range(n))))
            self.f.append(tuple(n0 + (k - 1) * n + j for j in range(n)))
            self.mi += [mi, mi]
            self.sm += [False, False]
        return self

    def rod(self, a, b, r, n=10, mi=0):
        """a straight round bar from a to b"""
        return self.tube([a, b], r, n, mi)

    def bar(self, a, b, w, h, mi=0, roll=0.0):
        """a rectangular bar w x h from a to b (any direction): w across, h along the frame's second axis (up for a
        level bar)"""
        A, B = Vector(a), Vector(b)
        d = B - A
        ln = d.length
        t = d / ln
        up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
        u = t.cross(up).normalized()
        v = u.cross(t)
        if roll:
            m = Matrix.Rotation(roll, 3, t)
            u, v = m @ u, m @ v
        n0 = len(self.v)
        for p in (A, B):
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                self.v.append(tuple(p + u * (su * w / 2) + v * (sv * h / 2)))
        for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.f.append(tuple(n0 + i for i in q))
            self.mi.append(mi)
            self.sm.append(False)
        return self

    def _quads(self, pts, quads, mi):
        n0 = len(self.v)
        self.v += [tuple(p) for p in pts]
        for q in quads:
            self.f.append(tuple(n0 + i for i in q))
            self.mi.append(mi)
            self.sm.append(False)
        return self

    def frame(self, lo, hi, hole_lo, hole_hi, mi=0):
        """a plate in the XZ plane (its thickness along Y, lo[1]..hi[1]) with a rectangular hole (hole_lo, hole_hi:
        (x, z)): a door leaf round its window, a bezel. ONE closed shell: no seam where four boxes would meet"""
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        (a0, c0), (a1, c1) = hole_lo, hole_hi
        ring = [(x0, z0), (x1, z0), (x1, z1), (x0, z1), (a0, c0), (a1, c0), (a1, c1), (a0, c1)]
        pts = [(x, y0, z) for x, z in ring] + [(x, y1, z) for x, z in ring]
        quads = []
        for k in range(4):
            j = (k + 1) % 4
            quads += [(k, j, 4 + j, 4 + k), (8 + k, 12 + k, 12 + j, 8 + j),          # the two faces' rings
                      (k, 8 + k, 8 + j, j), (4 + k, 4 + j, 12 + j, 12 + k)]          # the outer edge, the hole's reveal
        return self._quads(pts, quads, mi)

    def tub(self, lo, hi, t, mi=0):
        """a box of sheet `t` thick, open on its +Y side (an enclosure's body, its door off): one closed shell with its
        hollow, so its outer arrises bevel and what stands inside it is seen through the door's window"""
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        o = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]
        i = [(x0 + t, y0 + t, z0 + t), (x1 - t, y0 + t, z0 + t), (x1 - t, y0 + t, z1 - t), (x0 + t, y0 + t, z1 - t),
             (x0 + t, y1, z0 + t), (x1 - t, y1, z0 + t), (x1 - t, y1, z1 - t), (x0 + t, y1, z1 - t)]
        quads = [(0, 1, 2, 3), (8, 11, 10, 9)]                                       # the back outside, the back inside
        for k in range(4):
            j = (k + 1) % 4
            quads += [(k, 4 + k, 4 + j, j), (8 + k, 8 + j, 12 + j, 12 + k), (4 + k, 12 + k, 12 + j, 4 + j)]   # outside, inside, rim
        return self._quads(o + i, quads, mi)

    def arc(self, c, r, a0, a1, axis='z', steps=8):
        """points on an arc round `c` (for tube()): angles in radians in the plane across `axis`"""
        out = []
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            ca, sa = math.cos(a) * r, math.sin(a) * r
            p = (ca, sa, 0.0) if axis == 'z' else (0.0, ca, sa) if axis == 'x' else (sa, 0.0, ca)
            out.append((c[0] + p[0], c[1] + p[1], c[2] + p[2]))
        return out

    def mesh(self, name, mats, recalc=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', self.mi)
        me.polygons.foreach_set('use_smooth', self.sm)
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(me)
            bm.free()
        me.update()
        return me


def i_section(h, w, tf, tw, r=0.0):
    """the closed section of an I beam (height h, flange width w, flange tf, web tw), centred, for MB.prism: (u across
    the flanges, v up); r > 0 adds the root fillets as one chamfer"""
    a, b, c = w / 2, tw / 2, h / 2
    if r <= 0:
        return [(-a, -c), (a, -c), (a, -c + tf), (b, -c + tf), (b, c - tf), (a, c - tf), (a, c), (-a, c), (-a, c - tf), (-b, c - tf),
                (-b, -c + tf), (-a, -c + tf)]
    return [(-a, -c), (a, -c), (a, -c + tf), (b + r, -c + tf), (b, -c + tf + r), (b, c - tf - r), (b + r, c - tf), (a, c - tf),
            (a, c), (-a, c), (-a, c - tf), (-b - r, c - tf), (-b, c - tf - r), (-b, -c + tf + r), (-b - r, -c + tf), (-a, -c + tf)]


def c_section(h, w, t):
    """a channel (height h, flange w, thickness t), its back on u = 0, opening toward +u"""
    c = h / 2
    return [(0, -c), (w, -c), (w, -c + t), (t, -c + t), (t, c - t), (w, c - t), (w, c), (0, c)]


# ====================================================================================================== the detail pass
def detail(me, bevel=0.0025, inset=0.014, segments=2, sharp=SHARP, uv=True, log=None):
    """Bevel + inset + the `wear` attribute + hardened normals + a UV map in metres, in place. Closed shells only: a
    sheet (a face with an open edge) is left as it is. Returns {'faces', 'bevelled_edges', 'regions'}."""
    bm = bmesh.new()
    bm.from_mesh(me)
    wear = bm.verts.layers.float.new('wear')
    inner_l = bm.verts.layers.int.new('look_inner')
    reg_l = bm.faces.layers.int.new('look_region')
    bw_l = bm.edges.layers.float.new('look_bw')
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    for v in bm.verts:
        v[wear] = 0.0

    def hard(e):
        return len(e.link_faces) != 2 or e.calc_face_angle(0.0) > sharp

    hard_e = {e for e in bm.edges if hard(e)}
    region, regions = {}, []
    for f in bm.faces:                                       # smooth regions: faces joined across soft edges
        if f in region:
            continue
        rid = len(regions)
        region[f] = rid
        grp, stack = [f], [f]
        while stack:
            g = stack.pop()
            for e in g.edges:
                if e in hard_e:
                    continue
                for h in e.link_faces:
                    if h not in region:
                        region[h] = rid
                        grp.append(h)
                        stack.append(h)
        regions.append(grp)
    # a region is workable when its shell is closed there (every edge has two faces)
    closed, thick, neigh = [], [], [set() for _ in regions]
    for rid, grp in enumerate(regions):
        ok, area, per = True, 0.0, 0.0
        for f in grp:
            area += f.calc_area()
            for e in f.edges:
                if len(e.link_faces) != 2:
                    ok = False
                elif e in hard_e:
                    per += e.calc_length()
                    for h in e.link_faces:
                        if region[h] != rid:
                            neigh[rid].add(region[h])
        closed.append(ok)
        thick.append(min(inset, 0.30 * 2.0 * area / per) if (ok and per > 1e-9) else 0.0)
    for v in bm.verts:                                       # the arris: every vertex on a hard edge of a closed shell
        if any(e in hard_e and all(closed[region[f]] for f in e.link_faces) and len(e.link_faces) == 2 for e in v.link_edges):
            v[wear] = 1.0
    # bevel width per connected island: a thin part must not cap the bevel of a stout one
    isl = {}
    for v0 in bm.verts:
        if v0 in isl:
            continue
        i = v0.index
        stack = [v0]
        isl[v0] = i
        while stack:
            a = stack.pop()
            for e in a.link_edges:
                b = e.other_vert(a)
                if b not in isl:
                    isl[b] = i
                    stack.append(b)
    isl_w = {}
    for e in hard_e:
        if len(e.link_faces) != 2 or not all(closed[region[f]] for f in e.link_faces):
            continue
        w = min(bevel, 0.22 * e.calc_length(), *(0.55 * thick[region[f]] if thick[region[f]] > 0 else bevel for f in e.link_faces))
        k = isl[e.verts[0]]
        isl_w[k] = min(isl_w.get(k, bevel), w)
    classes = [bevel, bevel * 0.5, bevel * 0.25, bevel * 0.12]
    for e in hard_e:
        if len(e.link_faces) != 2 or not all(closed[region[f]] for f in e.link_faces):
            continue
        w = isl_w.get(isl[e.verts[0]], 0.0)
        e[bw_l] = next((c for c in classes if w >= c * 0.999), 0.0)
    # insets: regions that touch across a hard edge go in different calls (in one call they would count as one region)
    colour = {}
    for rid in sorted(range(len(regions)), key=lambda r: -len(neigh[r])):
        if not closed[rid] or thick[rid] < 0.0006:
            continue
        used = {colour[n] for n in neigh[rid] if n in colour}
        tcls = 0 if thick[rid] >= inset * 0.999 else 1 if thick[rid] >= inset * 0.5 else 2 if thick[rid] >= inset * 0.2 else 3
        c = 0
        while (c, tcls) in used:
            c += 1
        colour[rid] = (c, tcls)
    groups = {}
    for rid, key in colour.items():
        groups.setdefault(key, []).append(rid)
    for (c, tcls), rid_list in sorted(groups.items()):
        rids = set(rid_list)
        t = min(thick[r] for r in rids)
        faces = [f for r in rid_list for f in regions[r]]
        res = bmesh.ops.inset_region(bm, faces=faces, use_boundary=True, use_even_offset=True, use_interpolate=True,
                                     use_relative_offset=False, use_edge_rail=True, thickness=t, depth=0.0)
        for f in faces:
            for v in f.verts:
                v[inner_l] = 1
        new = res['faces']
        for f in new:                                        # a rim face belongs to the region it was cut from
            rid = None
            for e in f.edges:
                for h in e.link_faces:
                    if h is not f and h in region and region[h] in rids:
                        rid = region[h]
            if rid is not None:
                region[f] = rid
    for f in bm.faces:
        f[reg_l] = region.get(f, -2) + 1
    n_bev = 0
    for c in classes:
        edges = [e for e in bm.edges if abs(e[bw_l] - c) < 1e-9 and c > 0]
        if not edges:
            continue
        n_bev += len(edges)
        res = bmesh.ops.bevel(bm, geom=edges, offset=c, offset_type='OFFSET', profile_type='SUPERELLIPSE', segments=segments,
                              profile=0.5, affect='EDGES', clamp_overlap=True, loop_slide=True)
        for f in res['faces']:                               # the op also hands back the faces it rebuilt beside a bevel:
            if not any(v[inner_l] for v in f.verts):         # those keep a vertex of their inset loop; a bevel face has none
                f[reg_l] = 0
                for v in f.verts:
                    v[wear] = 1.0
    for v in bm.verts:                                       # the inset loops are where the wear band ends
        if v[inner_l]:
            v[wear] = 0.0
    bm.edges.layers.float.remove(bw_l)                       # (look_inner stays on the mesh: bake_cavity reads it)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    _normals_and_uv(me, uv)
    out = {'faces': len(me.polygons), 'bevelled_edges': n_bev, 'regions': len(regions)}
    if log:
        log('   detail %s: %s' % (me.name, out))
    return out


def _loop_faces(ls, lt, nl):
    """loop -> face"""
    if np.array_equal(ls, np.cumsum(lt) - lt):               # loops stored face by face, in order (the usual case)
        return np.repeat(np.arange(len(lt), dtype=np.int64), lt)
    lf = np.empty(nl, np.int64)
    for i in range(len(lt)):
        lf[ls[i]:ls[i] + lt[i]] = i
    return lf


def _normals_and_uv(me, uv=True):
    """hardened normals (a flat face keeps its own normal, a smooth region its area-weighted mean, a bevel the mean of
    the regions it joins) and a UV map in metres (dominant-axis projection)"""
    nl, nf, nv = len(me.loops), len(me.polygons), len(me.vertices)
    lv = np.empty(nl, np.int32)
    me.loops.foreach_get('vertex_index', lv)
    ls = np.empty(nf, np.int32)
    lt = np.empty(nf, np.int32)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    fn = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', fn)
    fn = fn.reshape(nf, 3).astype(np.float64)
    fa = np.empty(nf, np.float32)
    me.polygons.foreach_get('area', fa)
    reg = np.zeros(nf, np.int32)
    if 'look_region' in me.attributes:
        me.attributes['look_region'].data.foreach_get('value', reg)
    lf = _loop_faces(ls, lt, nl)
    lreg = reg[lf]
    wn = fn[lf] * fa[lf][:, None].astype(np.float64)
    out = np.zeros((nl, 3))
    nreg = int(reg.max()) + 2
    inreg = lreg > 0
    key = lv[inreg].astype(np.int64) * nreg + lreg[inreg]
    uk, inv = np.unique(key, return_inverse=True)
    acc = np.zeros((len(uk), 3))
    np.add.at(acc, inv, wn[inreg])
    acc /= np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-20)
    out[inreg] = acc[inv]
    vsum = np.zeros((nv, 3))                                 # per vertex: the mean of its regions' normals
    np.add.at(vsum, (uk // nreg).astype(np.int64), acc)
    vall = np.zeros((nv, 3))                                 # per vertex: the area-weighted mean of every face
    np.add.at(vall, lv, wn)
    use = np.linalg.norm(vsum, axis=1) > 1e-9
    vmean = np.where(use[:, None], vsum, vall)
    vmean /= np.maximum(np.linalg.norm(vmean, axis=1, keepdims=True), 1e-20)
    bev = lreg == 0
    out[bev] = vmean[lv[bev]]
    rest = lreg < 0                                          # untouched (open) faces: their own normal
    out[rest] = fn[lf][rest]
    me.normals_split_custom_set(out.tolist())
    if uv:
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(nv, 3)[lv]
        ax = np.abs(fn[lf]).argmax(axis=1)
        uvs = np.where((ax == 0)[:, None], co[:, (1, 2)], np.where((ax == 1)[:, None], co[:, (0, 2)], co[:, (0, 1)]))
        layer = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
        layer.data.foreach_set('uv', uvs.astype(np.float32).ravel())
    me.update()


def uv_metres(me):
    """only the UV map in metres (for a sheet or a mesh that keeps its shape)"""
    nl, nf, nv = len(me.loops), len(me.polygons), len(me.vertices)
    if not nl:
        return
    lv = np.empty(nl, np.int32)
    me.loops.foreach_get('vertex_index', lv)
    lt = np.empty(nf, np.int32)
    me.polygons.foreach_get('loop_total', lt)
    ls = np.empty(nf, np.int32)
    me.polygons.foreach_get('loop_start', ls)
    fn = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', fn)
    fn = fn.reshape(nf, 3)
    lf = _loop_faces(ls, lt, nl)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(nv, 3)[lv]
    ax = np.abs(fn[lf]).argmax(axis=1)
    uvs = np.where((ax == 0)[:, None], co[:, (1, 2)], np.where((ax == 1)[:, None], co[:, (0, 2)], co[:, (0, 1)]))
    layer = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
    layer.data.foreach_set('uv', uvs.astype(np.float32).ravel())


# ====================================================================================================== the cavity bake
def _hemi(k, seed=7):
    rng = np.random.default_rng(seed)
    u, v = rng.random(k), rng.random(k)
    r, phi = np.sqrt(u), 2 * PI * v                          # cosine-weighted
    return np.stack([r * np.cos(phi), r * np.sin(phi), np.sqrt(1.0 - u)], axis=1)


def bake_cavity(me, dist=0.10, rays=14, ground=None, extra=None, log=None, big_face=0.0025):
    """the vertex attribute `cavity` (0 open .. 1 closed in): the share of a cosine-weighted hemisphere over each vertex
    that meets the mesh (or `ground`, a z in the mesh's own space, or `extra` = (verts, polygons) more geometry) within
    `dist`, nearer hits counting more"""
    nv = len(me.vertices)
    if not nv:
        return
    verts = [tuple(v.co) for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    if ground is not None:
        lo = np.min(np.array(verts), axis=0) - 1.0
        hi = np.max(np.array(verts), axis=0) + 1.0
        n0 = len(verts)
        verts += [(lo[0], lo[1], ground), (hi[0], lo[1], ground), (hi[0], hi[1], ground), (lo[0], hi[1], ground)]
        polys.append((n0, n0 + 1, n0 + 2, n0 + 3))
    if extra is not None:
        n0 = len(verts)
        verts += [tuple(p) for p in extra[0]]
        polys += [tuple(n0 + i for i in f) for f in extra[1]]
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    hemi = _hemi(rays)
    out = np.zeros(nv, np.float32)
    up = Vector((0.0, 0.0, 1.0))
    cast = tree.ray_cast
    for i, v in enumerate(me.vertices):
        n = v.normal
        if n.length < 1e-6:
            continue
        t = n.cross(up)
        if t.length < 1e-4:
            t = n.cross(Vector((1.0, 0.0, 0.0)))
        t.normalize()
        b = n.cross(t)
        o = v.co + n * 0.0008
        acc = 0.0
        for hx, hy, hz in hemi:
            d = t * hx + b * hy + n * hz
            hit = cast(o, d, dist)
            if hit[0] is not None:
                acc += 1.0 - hit[3] / dist
        out[i] = acc / rays
    # A PER-VERTEX MASK MAY ONLY VARY WHERE THE MESH IS DENSE. The band between an arris and its inset loop is (its
    # quads are a wear-width wide); the big face inside the loop is not: four corners with four values are read across
    # its two triangles and the diagonal shows as a wedge of dirt. So a vertex of the inset loop of a LARGE face holds 0:
    # grime lives in the band where shells meet, and what rises up a tall face is the material's own (by height).
    if 'look_inner' in me.attributes and len(me.attributes['look_inner'].data) == nv:
        inner = np.zeros(nv, np.int32)
        me.attributes['look_inner'].data.foreach_get('value', inner)
        nf, nl = len(me.polygons), len(me.loops)
        fa = np.empty(nf, np.float32)
        me.polygons.foreach_get('area', fa)
        ls = np.empty(nf, np.int32)
        lt = np.empty(nf, np.int32)
        me.polygons.foreach_get('loop_start', ls)
        me.polygons.foreach_get('loop_total', lt)
        lv = np.empty(nl, np.int32)
        me.loops.foreach_get('vertex_index', lv)
        big = np.zeros(nv, np.float32)
        np.maximum.at(big, lv, fa[_loop_faces(ls, lt, nl)])
        out[(inner > 0) & (big > big_face)] = 0.0
    a = me.attributes.get('cavity') or me.attributes.new('cavity', 'FLOAT', 'POINT')
    a.data.foreach_set('value', np.clip(out * 1.6, 0.0, 1.0))
    if log:
        log('   cavity %s: %d vertices, mean %.3f, max %.3f' % (me.name, nv, float(out.mean()), float(out.max())))


def finish(me, bevel=0.0025, inset=0.014, cavity=0.10, ground=None, rays=14, log=None):
    """the whole preparation of one built mesh: detail(), then bake_cavity()"""
    r = detail(me, bevel=bevel, inset=inset, log=log)
    if cavity:
        bake_cavity(me, dist=cavity, rays=rays, ground=ground, log=log)
    return r


# ====================================================================================================== instances
def instance_on_points(name, points, source, collection, rz=0.0, parent=None):
    """one object whose points each show `source` (an object or a collection), turned rz: thousands of rollers or rack
    bays from one mesh"""
    me = bpy.data.meshes.new(name + '_points')
    me.from_pydata([tuple(p) for p in points], [], [])
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n_in, n_out = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    if isinstance(source, bpy.types.Collection):
        src = ng.nodes.new('GeometryNodeCollectionInfo')
        src.inputs[0].default_value = source
        src.transform_space = 'ORIGINAL'
    else:
        src = ng.nodes.new('GeometryNodeObjectInfo')
        src.inputs[0].default_value = source
        src.transform_space = 'ORIGINAL'
        src.inputs['As Instance'].default_value = True
    iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Rotation'].default_value = (0.0, 0.0, rz)
    ng.links.new(n_in.outputs[0], iop.inputs['Points'])
    ng.links.new(src.outputs['Geometry' if not isinstance(source, bpy.types.Collection) else 0], iop.inputs['Instance'])
    ng.links.new(iop.outputs[0], n_out.inputs[0])
    mod = ob.modifiers.new('instances', 'NODES')
    mod.node_group = ng
    return ob
