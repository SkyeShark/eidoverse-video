"""eidoblend.props.hardsurface.masses: hard-surface parts built the way they are made, each ONE mass.

    from eidoblend.props.hardsurface import masses as hs

    hs.start('my_prop')                                   # collections 'my_prop' (the parts) and 'my_prop_tmp' (the bench)
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    body = hs.boolean(hs.prism_side('body', SIDE_XZ, -11.0, 11.0),          # the side outline's prism ...
                      hs.prism_section('body_sec', SECTION_YZ, 0.0, 200.0), 'INTERSECT')   # ... x the section's
    body = hs.boolean(body, hs.cyl('boss', (40, -10, 0), (40, -15, 0), 9.0), 'UNION')    # a feature, overlapping
    body = hs.boolean(body, hs.box('slot', (60, -20, -5), (80, 20, 5)), 'DIFFERENCE')    # a cut that goes through
    hs.finish(body, 0.8, clay)                            # cleaned, ONE bevel for its edges, flats shading flat
    hs.sweep_tmp()                                        # the bench emptied

Every table is in MILLIMETRES; the scene is in metres (MM = 1e-3). A part is the intersection of its measured
outlines' prisms (side x section x plan), its features unioned in with a clear overlap, its recesses and openings cut by
cutters that go fully through; then finish() welds it, dissolves degenerate and coplanar leftovers, reports open edges
and gives its edges one bevel modifier (an angle-limited bevel with hardened normals, and a weighted-normal modifier
that keeps flats flat). Hardware that is separate stays a separate part.

Edge groups by construction (a forging's soft radii, the fillet where a forged-in feature meets the body, crisp
machining): tag each boolean operand's faces with its group (tagged(o, EG_FEATURE)); finish_forged(o, width, m) reads
each edge's group from the pair of tags it parts and whether it is convex, and bevels it by width(tag_a, tag_b,
convex) millimetres as a round (a radius R across a dihedral of angle a is set back R tan(a / 2)), never wider than
0.45 of the narrower face beside it.

THE LOW from the same tables: start(name, low=True) builds the same construction at the resolution a low needs.
Round parts take the radial count their chord sagitta allows (nseg: s = r (1 - cos(pi / n)) under sag_mm), detail()
booleans are left to the bake, finish() and finish_forged() only clean (no bevel, no normals: lowpoly.prepare_low
finishes a low), and a low a boolean left open is closed where it is open.

Lofts, sweeps and turned parts: rings() / skins() (a skin over rings of points, the general loft), sweep() (a section
along a path with rotation-minimising frames), revolve() (a profile about any axis), lathe() (about a line parallel to
X), loft() (superellipse sections), fillet_path() (a polyline's corners turned to arcs).
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

MM = 1e-3
EG_BODY, EG_FEATURE, EG_MACHINED, EG_CUT = 0, 1, 2, 3      # edge groups by construction (tagged / finish_forged)

col = tmp = None             # the build's collections: the asset's parts, the workbench
LOW = False                  # building the low (start(low=True))
SAG_MM = 0.12                # the low's chord sagitta (mm)
ORIENT = True                # turn a closed part right side out by its signed volume
REPORT = []                  # (name, open edges, volume litres, faces) per finished part
_EG = []                     # the edge-group tag materials of this build


def start(name: str, low: bool = False, sag_mm: float = 0.12, orient: bool = True, scene=None):
    """Begin a build in the scene (the context's by default): the parts' collection `name` and a workbench
    `name + '_tmp'`, both linked to the scene. low: build the low (see the module doc); sag_mm: the low's chord
    sagitta; orient: a closed part whose signed volume is negative is turned right side out. Returns the scene."""
    global col, tmp, LOW, SAG_MM, ORIENT
    sc = scene or bpy.context.scene
    col = bpy.data.collections.new(name)
    sc.collection.children.link(col)
    tmp = bpy.data.collections.new(name + '_tmp')
    sc.collection.children.link(tmp)
    LOW, SAG_MM, ORIENT = bool(low), float(sag_mm), bool(orient)
    REPORT.clear()
    _EG.clear()
    return sc


def new_file():
    """An empty file (factory settings, no objects): the asset scripts call it before a build of their own."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def low() -> bool:
    """True while the low is being built."""
    return LOW


def nseg(dia: float, seg: int) -> int:
    """The radial count of a round part: `seg` for the high; for the low, the count the sagitta budget allows at
    diameter `dia` (mm), a multiple of 4, at least 8, never more than the high's."""
    if not LOW:
        return seg
    r_ = max(dia / 2.0, 1e-3)
    n_ = math.pi / math.acos(max(-1.0, 1.0 - SAG_MM / r_)) if SAG_MM < r_ else 8
    return int(max(8, min(seg, math.ceil(n_ / 4.0) * 4)))


# ------------------------------------------------------------------------------------------------ objects ---

def obj(name: str, bm, where=None):
    """A mesh object from a bmesh (freed), its normals made consistent, on the workbench (or in `where`)."""
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    (where or tmp).objects.link(o)
    return o


def _prism(name, pts3, vec):
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(p) for p in pts3])
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)], vec=vec)
    return obj(name, bm)


def prism_side(name: str, outline, y0: float, y1: float):
    """A side outline [(x, z)] extruded across from y0 to y1 (mm)."""
    return _prism(name, [(x * MM, y0 * MM, z * MM) for x, z in outline], (0, (y1 - y0) * MM, 0))


def prism_section(name: str, section, x0: float, x1: float):
    """A cross-section [(y, z)] extruded along from x0 to x1 (mm)."""
    return _prism(name, [(x0 * MM, y * MM, z * MM) for y, z in section], ((x1 - x0) * MM, 0, 0))


def prism_plan(name: str, plan, z0: float, z1: float):
    """A plan outline [(x, y)] extruded up from z0 to z1 (mm)."""
    return _prism(name, [(x * MM, y * MM, z0 * MM) for x, y in plan], (0, 0, (z1 - z0) * MM))


def box(name: str, lo, hi):
    """A box between two corners (mm), as real vertices on an untransformed object (so a bevel on it is even)."""
    bm = bmesh.new()
    x0, y0, z0 = [min(a, b) * MM for a, b in zip(lo, hi)]
    x1, y1, z1 = [max(a, b) * MM for a, b in zip(lo, hi)]
    v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1),
                                   (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([v[i] for i in f])
    return obj(name, bm)


def cyl(name: str, p0, p1, dia: float, seg: int = 48, dia1: float = None, keep: bool = False, where=None):
    """A cylinder (or a cone: dia at p0, dia1 at p1) from p0 to p1 (mm). keep: the low keeps the high's count (a tube
    whose cutters must meet it exactly)."""
    if not keep:
        seg = nseg(max(dia, dia1 if dia1 is not None else dia), seg)
    a, b = Vector(p0) * MM, Vector(p1) * MM
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=dia / 2 * MM,
                          radius2=(dia1 if dia1 is not None else dia) / 2 * MM, depth=(b - a).length)
    o = obj(name, bm, where)
    o.location = (a + b) / 2
    o.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
    return o


def lathe(name: str, stations, seg: int = 48, y: float = 0.0, z: float = 0.0):
    """A turned part on a line parallel to X: stations [(x, diameter)] (mm); the low's count from its largest
    diameter's sagitta."""
    seg = nseg(max(d for _, d in stations), seg)
    bm = bmesh.new()
    rings_ = [[bm.verts.new((x * MM, (y + d / 2 * math.cos(2 * math.pi * k / seg)) * MM,
                             (z + d / 2 * math.sin(2 * math.pi * k / seg)) * MM)) for k in range(seg)]
              for x, d in stations]
    for a_, b_ in zip(rings_, rings_[1:]):
        for k in range(seg):
            bm.faces.new((a_[k], a_[(k + 1) % seg], b_[(k + 1) % seg], b_[k]))
    bm.faces.new(rings_[0][::-1])
    bm.faces.new(rings_[-1])
    return obj(name, bm)


def loft(name: str, sections, n: int = 40):
    """Rings of a superellipse section along a line in the side plane: sections [(x, z centre, half-width across,
    half-height, squareness 2 = ellipse .. 8 = nearly a box, y centre (optional))] (mm); the rings stand in Y-Z."""
    bm = bmesh.new()
    rings_ = []
    for s in sections:
        x, zc, hw, hh, sq = s[:5]
        yc = s[5] if len(s) > 5 else 0.0
        e = 2.0 / sq
        ring = []
        for k in range(n):
            a_ = 2 * math.pi * k / n
            c_, s_ = math.cos(a_), math.sin(a_)
            ring.append(bm.verts.new((x * MM, (yc + hw * math.copysign(abs(c_) ** e, c_)) * MM,
                                      (zc + hh * math.copysign(abs(s_) ** e, s_)) * MM)))
        rings_.append(ring)
    for a_, b_ in zip(rings_, rings_[1:]):
        for k in range(n):
            bm.faces.new((a_[k], a_[(k + 1) % n], b_[(k + 1) % n], b_[k]))
    bm.faces.new(rings_[0][::-1])
    bm.faces.new(rings_[-1])
    return obj(name, bm)


def _skin(bm, ring_list, close_u=True, caps=True):
    V = [[bm.verts.new((p[0] * MM, p[1] * MM, p[2] * MM)) for p in r] for r in ring_list]
    n = len(V[0])
    for a_, b_ in zip(V, V[1:]):
        for k in range(n if close_u else n - 1):
            bm.faces.new((a_[k], a_[(k + 1) % n], b_[(k + 1) % n], b_[k]))
    if caps and close_u:
        bm.faces.new(V[0][::-1])
        bm.faces.new(V[-1])


def rings(name: str, ring_list, close_u: bool = True, caps: bool = True):
    """A skin over rings of points (mm), each ring the same count and winding: the general loft. close_u: each ring
    is a closed loop; caps: the first and last rings are filled."""
    bm = bmesh.new()
    _skin(bm, ring_list, close_u, caps)
    return obj(name, bm)


def skins(name: str, skin_list):
    """Many closed, capped skins in ONE object (small hardware that repeats: a plate's bolts, a run's straps)."""
    bm = bmesh.new()
    for ring_list in skin_list:
        _skin(bm, ring_list)
    return obj(name, bm)


def circle(at, axis, r: float, h: float = 0.0, seg: int = 16, start=None):
    """A ring of points: a circle of radius r about `axis`, h along it from `at` (mm)."""
    ax = Vector(axis).normalized()
    n0 = Vector(start).normalized() if start is not None else ax.orthogonal().normalized()
    n0 = (n0 - ax * n0.dot(ax)).normalized()
    b0 = ax.cross(n0)
    o_ = Vector(at) + ax * h
    return [o_ + (n0 * math.cos(2 * math.pi * k / seg) + b0 * math.sin(2 * math.pi * k / seg)) * r for k in range(seg)]


def frames(path):
    """Rotation-minimising frames along a polyline of points (mm): [(point, tangent, normal, binormal)], so a sweep's
    section does not spin as the path turns."""
    P = [Vector(p) for p in path]
    T = []
    for i in range(len(P)):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)])
        T.append(t.normalized())
    n = T[0].orthogonal().normalized()
    out = []
    for i, t in enumerate(T):
        if i:
            ax = T[i - 1].cross(t)
            if ax.length > 1e-9:
                n = Quaternion(ax.normalized(), T[i - 1].angle(t)) @ n
        n = (n - t * n.dot(t)).normalized()
        out.append((P[i], t, n, t.cross(n)))
    return out


def sweep(name: str, path, section, up=None, caps: bool = True):
    """A closed section [(u, v)] (mm) carried along a path of points (mm). up: a vector the section's v axis leans
    to (given: the frame is fixed to it at every point; not given: rotation-minimising frames)."""
    out = []
    for p, t, n, b in frames(path):
        if up is not None:
            u_ = Vector(up)
            b = (u_ - t * u_.dot(t)).normalized()
            n = b.cross(t)
        out.append([p + n * s[0] + b * s[1] for s in section])
    return rings(name, out, caps=caps)


def fillet_path(points, radius: float, n: int = 6):
    """A polyline (mm) with each corner replaced by an arc of the given radius (the bends of a tube or a bar)."""
    P = [Vector(p) for p in points]
    out = [P[0]]
    for a_, b_, c_ in zip(P, P[1:], P[2:]):
        d0, d1 = (a_ - b_).normalized(), (c_ - b_).normalized()
        ang = d0.angle(d1)
        if ang > math.radians(179.0):
            out.append(b_)
            continue
        t = min(radius / math.tan(ang / 2.0), (a_ - b_).length * 0.49, (c_ - b_).length * 0.49)
        r = t * math.tan(ang / 2.0)
        cen = b_ + (d0 + d1).normalized() * (r / math.sin(ang / 2.0))
        s0, s1 = b_ + d0 * t, b_ + d1 * t
        for k in range(n + 1):
            v = (s0 - cen).slerp(s1 - cen, k / n)               # (slerp gives the direction: scale it back to r)
            out.append(cen + v.normalized() * r)
    out.append(P[-1])
    return out


def revolve(name: str, profile, at=(0, 0, 0), axis=(0, 0, 1), seg: int = 48, start=None, closed: bool = False):
    """A profile [(radius, height)] (mm) turned about an axis through `at`, in any direction. closed: the profile is a
    closed loop (a sheet with its thickness: the last point joins the first); otherwise its two ends are filled."""
    ax = Vector(axis).normalized()
    n0 = Vector(start).normalized() if start is not None else ax.orthogonal().normalized()
    n0 = (n0 - ax * n0.dot(ax)).normalized()
    b0 = ax.cross(n0)
    o_ = Vector(at)
    rr = [[o_ + ax * h + (n0 * math.cos(2 * math.pi * k / seg) + b0 * math.sin(2 * math.pi * k / seg)) * r
           for k in range(seg)] for r, h in profile]
    if closed:
        rr.append(rr[0])
    return rings(name, rr, caps=not closed)


# ------------------------------------------------------------------------------------------------ booleans ---

def boolean(target, other, op: str):
    """target op other ('UNION' | 'DIFFERENCE' | 'INTERSECT'), Blender's EXACT solver, applied; `other` is removed."""
    bpy.context.view_layer.update()
    m = target.modifiers.new(op, 'BOOLEAN')
    m.operation, m.object, m.solver = op, other, 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.remove(m)
    old = target.data
    target.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(other, do_unlink=True)
    return target


def detail(target, other, op: str):
    """A boolean the low leaves to the bake (a pin hole, a bore inside the asset, a knurl): the high makes it, the
    low drops `other`."""
    if LOW:
        bpy.data.objects.remove(other, do_unlink=True)
        return target
    return boolean(target, other, op)


def clean(o, dissolve: bool = True):
    """Weld, dissolve degenerate faces and (dissolve=True) coplanar leftovers; make the normals consistent; the low
    is closed where a boolean left it open; a closed part with a negative signed volume is turned right side out
    (start(orient=True)). A skin of fitted sections keeps its quads with dissolve=False. -> (open edges, volume m3)"""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=2e-6)
    if dissolve:
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    if LOW:
        open_ = [e for e in bm.edges if not e.is_manifold]
        if open_:
            bmesh.ops.holes_fill(bm, edges=open_, sides=0)
            print(f'[hardsurface] low {o.name}: {len(open_)} open edges closed by filling')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    open_e = sum(1 for e in bm.edges if not e.is_manifold)
    if ORIENT and not open_e and bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        print(f'[hardsurface] part {o.name}: turned right side out (its signed volume was negative)')
    vol = bm.calc_volume()
    bm.to_mesh(o.data)
    bm.free()
    return open_e, vol


def _into_asset(o, m):
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)
    o.data.materials.clear()
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True


def finish(o, bevel_mm: float, m, segments: int = 3, parent=None, dissolve: bool = True):
    """The part leaves the workbench: cleaned, its edges given ONE bevel of bevel_mm (angle-limited at 30 degrees,
    hardened normals), flats shading flat (a weighted-normal modifier), material m, into the asset's collection,
    under `parent` when given. The low is cleaned only."""
    open_e, vol = clean(o, dissolve)
    if open_e:
        bm_ = bmesh.new()
        bm_.from_mesh(o.data)
        where = [tuple(round(c / MM, 1) for c in (e.verts[0].co + e.verts[1].co) / 2) for e in bm_.edges
                 if not e.is_manifold][:6]
        bm_.free()
        print(f'[hardsurface] part {o.name}: OPEN EDGES {open_e} at (mm) {where}')
    _into_asset(o, m)
    if not LOW:
        if bevel_mm:
            b = o.modifiers.new('edge_group', 'BEVEL')
            b.width, b.segments, b.limit_method, b.angle_limit = bevel_mm * MM, segments, 'ANGLE', math.radians(30)
            b.harden_normals = True
        w = o.modifiers.new('flat_faces_flat', 'WEIGHTED_NORMAL')
        w.keep_sharp = True
    if parent is not None:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    REPORT.append((o.name, open_e, round(vol * 1e3, 3), len(o.data.polygons)))
    return o


def tagged(o, k: int):
    """Every face of `o` tagged with edge group k (EG_BODY, EG_FEATURE, EG_MACHINED, EG_CUT): a boolean carries the
    tags into its result, and finish_forged reads them."""
    if not _EG:
        _EG.extend(bpy.data.materials.new(f'edge_group_{i}') for i in range(4))
    o.data.materials.clear()
    for m_ in _EG:
        o.data.materials.append(m_)
    for p in o.data.polygons:
        p.material_index = k
    return o


def finish_forged(o, width, m, segments: int = 4):
    """A forged and machined part leaves the workbench: each edge bevelled by its group. width(tag_a, tag_b, convex)
    -> the round's radius in mm (0: no bevel). Where two groups meet the junction is rounded all along its loop,
    however shallow; inside one group only edges sharper than 30 degrees count. A round of radius R across a dihedral
    a is set back R tan(a / 2), so a fillet that runs tangent into a tube thins away, and no bevel is wider than 0.45
    of the narrower face beside it (neighbouring rounds never run through each other). The low is cleaned only."""
    if LOW:
        return finish(o, 0.0, m)
    open_e, vol = clean(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    lay = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
    want = []
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        a_ = e.calc_face_angle_signed(0.0)
        ka, kb = sorted(f.material_index for f in e.link_faces)
        if abs(a_) < math.radians(3.0 if ka != kb else 30.0):
            continue
        r_ = width(ka, kb, a_ > 0)
        if not r_:
            continue
        w_ = r_ * math.tan(min(abs(a_), math.radians(150.0)) / 2.0)
        p0, p1 = e.verts[0].co, e.verts[1].co
        L_ = (p1 - p0).length
        d_ = (p1 - p0) / max(L_, 1e-9)
        room = 1e9
        for f in e.link_faces:
            for v in f.verts:
                if v in e.verts:
                    continue
                q = v.co - p0
                along = q.dot(d_)
                perp = (q - d_ * along).length
                # (a vertex in line with the edge, a boolean's T-junction, is not across from it; one far along the
                #  edge does not crowd it)
                if perp < 0.02 * MM or along < -3.0 * MM or along > L_ + 3.0 * MM:
                    continue
                room = min(room, perp / MM)
        want.append((e, min(w_, 0.45 * room)))
    top = max([w_ for _, w_ in want] + [0.1])
    for e, w_ in want:
        e[lay] = w_ / top
    for f in bm.faces:
        f.material_index = 0
    bm.to_mesh(o.data)
    bm.free()
    _into_asset(o, m)
    b = o.modifiers.new('edge_groups', 'BEVEL')
    b.width, b.segments, b.limit_method, b.use_clamp_overlap, b.harden_normals = top * MM, segments, 'WEIGHT', False, True
    w = o.modifiers.new('flat_faces_flat', 'WEIGHTED_NORMAL')
    w.keep_sharp = True
    REPORT.append((o.name, open_e, round(vol * 1e3, 3), len(o.data.polygons)))
    return o


# ----------------------------------------------------------------------------------------------- the rest ---

def arc(cy: float, cz: float, r: float, a0: float, a1: float, n: int):
    """n + 1 points of a circular arc about (cy, cz), from a0 to a1 degrees."""
    return [(cy + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cz + r * math.sin(math.radians(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


def rrect(x0: float, z0: float, x1: float, z1: float, r: float, n: int = 6):
    """A rounded rectangle's outline (corner radius r, n segments a corner)."""
    out = []
    for cx, cz, a0 in ((x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180), (x1 - r, z0 + r, 270)):
        out += [(cx + r * math.cos(math.radians(a0 + 90 * k / n)), cz + r * math.sin(math.radians(a0 + 90 * k / n)))
                for k in range(n + 1)]
    return out


def mat(name: str, rgb, rough: float, metal: float, alpha: float = 1.0):
    """A plain Principled material (a build's clay, or a part's role before its look)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value, b.inputs['Metallic'].default_value = rough, metal
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        m.surface_render_method = 'BLENDED'
    return m


def empty(name: str, at):
    """An Empty in the asset at `at` (mm): a pivot that turns its children (a rotor's hub)."""
    e = bpy.data.objects.new(name, None)
    col.objects.link(e)
    e.location = Vector(at) * MM
    bpy.context.view_layer.update()
    return e


def sweep_tmp():
    """Remove what is left on the workbench (cutters and references)."""
    for o in list(tmp.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def apply_transforms(objs=None):
    """Every mesh part's own mesh in the asset's space, its object at identity (the low's UVs, tangents and bake rays
    read object space as the asset's own): the asset's collection by default."""
    bpy.context.view_layer.update()                           # (a transform set since the last update is not in matrix_world yet)
    for o in (objs if objs is not None else col.objects):
        if o.type == 'MESH' and o.matrix_world != Matrix.Identity(4):
            o.data.transform(o.matrix_world)
            o.matrix_world = Matrix.Identity(4)
