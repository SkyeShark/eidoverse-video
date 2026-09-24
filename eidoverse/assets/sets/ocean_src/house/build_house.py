# build_house.py — the verse-3 beach cottage (DAISY), built headless in Blender 5.2.
#
#   blender --background --python build_house.py -- [--render neutral|night|lamp|all] [--quick]
#
# Design coordinates: x right, u up, f front (+f = toward the porch / the camera).
# Blender coordinates: X = x, Y = -f, Z = u  (the glTF exporter maps Blender -Y -> glTF +Z,
# so the porch faces +Z in the GLB, as the set expects). Metres throughout.
#
# Topology tells the fabrication story: one siding shell with its door/window pockets cut
# as reveals; one continuous broken-pitch roof mass (main 38 deg + porch 12 deg); trim boards,
# posts, rails, balusters, lamp parts are separate (assembled) pieces with buried end caps
# deleted where they meet what they sit on. Layered materials (library PBR base + AO grime +
# streaks + ground splash + edge wear) live in the source node trees; bake_export.py bakes
# them down per object and writes the GLB.

import bpy, bmesh, math, os, sys, json, random
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(ROOT, 'tex')
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

def arg(name, default=None):
    if name in ARGV:
        i = ARGV.index(name)
        return ARGV[i + 1] if i + 1 < len(ARGV) and not ARGV[i + 1].startswith('--') else True
    return default

# ----------------------------------------------------------------------------- dimensions
W2 = 2.40            # half width of the body (x)
D2 = 2.00            # half depth (f)
U_BASE = 0.40        # siding bottom (laps 2 cm over the foundation top)
U_FLOOR = 0.45       # finished floor / porch deck top
U_TOP = 3.15         # wall top plate = roof underside at the wall line
PITCH = math.radians(38.0)
ROOF_T = 0.15        # roof thickness (vertical)
OVH_EAVE = 0.30      # rear eave overhang (horizontal)
OVH_RAKE = 0.30      # gable rake overhang (x)
PORCH_F = 3.60       # porch deck front edge
PORCH_ROOF_F = 3.85  # porch roof front edge (0.25 overhang past the beam line)
PORCH_PITCH = math.radians(12.0)
POST_F = 3.50        # porch post centre line
U_RIDGE_TOP = U_TOP + ROOF_T + D2 * math.tan(PITCH)       # roof top at the ridge

DOOR = dict(x0=-1.33, x1=-0.47, u0=U_FLOOR, u1=2.48, depth=0.14)
WIN = dict(x0=0.60, x1=1.60, u0=1.18, u1=2.48, depth=0.45)
LAMP_X = 0.065
LAMP_BULB_U = 2.315
WALL_F = D2          # front wall plane

def roof_top_u(f):
    """Top surface height of the roof mass at design f (valid for |x| inside the rakes)."""
    if f <= 0.0:
        return U_RIDGE_TOP + f * math.tan(PITCH)          # rear slope (f negative)
    if f <= D2:
        return U_RIDGE_TOP - f * math.tan(PITCH)          # front main slope
    return U_TOP + ROOF_T - (f - D2) * math.tan(PORCH_PITCH)

def roof_bot_u(f):
    return roof_top_u(f) - ROOF_T

def B(x, u, f):
    """design -> Blender"""
    return Vector((x, -f, u))

# ----------------------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    return sc

# ----------------------------------------------------------------------------- mesh builder
class Part:
    """A bmesh under construction: vertex welding by coordinate, per-face material slots,
    per-face tile-UV projection, and a list of materials for the final object."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('tile')
        self.vcache = {}
        self.mats = []

    def mat(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def v(self, p, weld=True):
        p = Vector(p)
        if not weld:
            return self.bm.verts.new(p)
        k = (round(p.x, 5), round(p.y, 5), round(p.z, 5))
        vv = self.vcache.get(k)
        if vv is None or not vv.is_valid:
            vv = self.bm.verts.new(p)
            self.vcache[k] = vv
        return vv

    def face(self, pts, mat, normal=None, uvp=None, weld=True):
        vs = [self.v(p, weld) for p in pts]
        # drop consecutive duplicates (degenerate corners)
        clean = []
        for vv in vs:
            if not clean or clean[-1] is not vv:
                clean.append(vv)
        if len(clean) > 2 and clean[0] is clean[-1]:
            clean.pop()
        if len(clean) < 3:
            return None
        try:
            f = self.bm.faces.new(clean)
        except ValueError:
            f = self.bm.faces.get(clean)
            if f is None:
                return None
        f.normal_update()
        if normal is not None and f.normal.dot(Vector(normal)) < 0:
            f.normal_flip()
        f.material_index = self.mat(mat)
        if uvp:
            self.project(f, *uvp)
        return f

    def project(self, f, U, V, tile=1.0, off=(0.0, 0.0)):
        U = Vector(U); V = Vector(V)
        for lp in f.loops:
            co = lp.vert.co
            lp[self.uv].uv = (co.dot(U) / tile + off[0], co.dot(V) / tile + off[1])

    def finish(self, collection=None, smooth_angle=None, parent=None):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        for p in me.polygons:
            p.use_smooth = smooth_angle is not None
        if smooth_angle is not None:
            ob.data.set_sharp_from_angle(angle=math.radians(smooth_angle))
        return ob

# axis helpers in Blender space
X = Vector((1, 0, 0)); Yb = Vector((0, 1, 0)); Z = Vector((0, 0, 1))
F = Vector((0, -1, 0))        # design +f in Blender

def box(part, mat, x0, x1, u0, u1, f0, f1, skip=(), grain='x', tile=1.0, uoff=(0, 0)):
    """Axis-aligned board in design coords. skip: faces to omit ('-x','+x','-u','+u','-f','+f').
    grain: which design axis the texture's u runs along ('x', 'u' or 'f')."""
    P = lambda x, u, f: B(x, u, f)
    gdir = {'x': X, 'u': Z, 'f': F}[grain]
    faces = {
        '-x': ([P(x0, u0, f0), P(x0, u1, f0), P(x0, u1, f1), P(x0, u0, f1)], -X),
        '+x': ([P(x1, u0, f0), P(x1, u0, f1), P(x1, u1, f1), P(x1, u1, f0)], X),
        '-u': ([P(x0, u0, f0), P(x0, u0, f1), P(x1, u0, f1), P(x1, u0, f0)], -Z),
        '+u': ([P(x0, u1, f0), P(x1, u1, f0), P(x1, u1, f1), P(x0, u1, f1)], Z),
        '-f': ([P(x0, u0, f0), P(x1, u0, f0), P(x1, u1, f0), P(x0, u1, f0)], -F),
        '+f': ([P(x0, u0, f1), P(x0, u1, f1), P(x1, u1, f1), P(x1, u0, f1)], F),
    }
    out = []
    for k, (pts, n) in faces.items():
        if k in skip:
            continue
        # texture u along the grain; v along the other in-plane axis
        if abs(gdir.dot(n)) > 0.5:          # grain is the face normal (end grain): any in-plane pair
            U = X if abs(n.dot(X)) < 0.5 else F
        else:
            U = gdir
        Vv = n.cross(U).normalized()
        out.append(part.face(pts, mat, n, (U, Vv, tile, uoff)))
    return out

def prism(part, mat, poly_uf, x0, x1, tile=1.0, caps=True, uvU=None, side_normal_out=True):
    """Extrude a closed (f,u) polygon (CCW seen from +x) along x. Side faces get u along x."""
    n = len(poly_uf)
    out = []
    for i in range(n):
        (fa, ua), (fb, ub) = poly_uf[i], poly_uf[(i + 1) % n]
        pts = [B(x0, ua, fa), B(x1, ua, fa), B(x1, ub, fb), B(x0, ub, fb)]
        # outward normal of this edge in the (f,u) plane
        ef, eu = fb - fa, ub - ua
        nf, nu = eu, -ef               # rotate edge by -90 deg (CCW polygon -> outward)
        nrm = (F * nf + Z * nu).normalized()
        if not side_normal_out:
            nrm = -nrm
        Vv = nrm.cross(X).normalized()
        out.append(part.face(pts, mat, nrm, (X, -Vv if Vv.dot(Z) < 0 else Vv, tile)))
    if caps:
        for xx, nx in ((x0, -X), (x1, X)):
            pts = [B(xx, u, f) for (f, u) in poly_uf]
            out.append(part.face(pts, mat, nx, (F, Z, tile)))
    return out

def lathe(part, mat, prof_ru, center, segs=24, axis='u', cap_top=False, cap_bot=False, tile=0.2,
          radial_fn=None, u_scale=1.0):
    """Revolve a (r, h) profile around a vertical (u) axis at design centre (x, u, f)."""
    cx, cu, cf = center
    rings = []
    for (r, h) in prof_ru:
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            rr = r * (radial_fn(a, h) if radial_fn else 1.0)
            ring.append(B(cx + rr * math.cos(a), cu + h, cf + rr * math.sin(a)))
        rings.append(ring)
    out = []
    for i in range(len(rings) - 1):
        for j in range(segs):
            a0, a1 = rings[i][j], rings[i][(j + 1) % segs]
            b0, b1 = rings[i + 1][j], rings[i + 1][(j + 1) % segs]
            mid = (a0 + a1 + b0 + b1) / 4
            axisp = B(cx, mid.z, cf)
            nrm = (mid - Vector((axisp.x, axisp.y, mid.z)))
            if nrm.length < 1e-6:
                nrm = Z
            f = part.face([a0, a1, b1, b0], mat, None, None, weld=True)
            if f is None:
                continue
            # orient outward from the axis (or up/down for flat rings)
            fc = f.calc_center_median()
            radial = Vector((fc.x - cx, fc.y + cf, 0))
            if radial.length > 1e-4 and abs(f.normal.z) < 0.9:
                if f.normal.dot(radial) < 0:
                    f.normal_flip()
            # cylindrical uv: angle x circumference, height
            for lp in f.loops:
                co = lp.vert.co
                ang = math.atan2(co.y + cf, co.x - cx)
                lp[part.uv].uv = ((ang / (2 * math.pi)) * 0.3 / tile, co.z / tile * u_scale)
            out.append(f)
    if cap_top:
        out.append(part.face(rings[-1], mat, Z, (X, F, tile)))
    if cap_bot:
        out.append(part.face(rings[0], mat, -Z, (X, F, tile)))
    return out

def tube(part, mat, pts, radius, segs=8, tile=0.2, cap=False):
    """Sweep a circle along a polyline of design points (x,u,f)."""
    P = [B(*p) for p in pts]
    rings = []
    prev_n = None
    for i, p in enumerate(P):
        if i == 0:
            t = (P[1] - P[0]).normalized()
        elif i == len(P) - 1:
            t = (P[-1] - P[-2]).normalized()
        else:
            t = ((P[i] - P[i - 1]).normalized() + (P[i + 1] - P[i]).normalized()).normalized()
        if prev_n is None:
            ref = Z if abs(t.dot(Z)) < 0.9 else X
            n = t.cross(ref).normalized()
        else:
            n = (prev_n - t * prev_n.dot(t)).normalized()
        prev_n = n
        b = t.cross(n).normalized()
        rings.append([p + (n * math.cos(2 * math.pi * j / segs) + b * math.sin(2 * math.pi * j / segs)) * radius
                      for j in range(segs)])
    dist = 0.0
    out = []
    for i in range(len(rings) - 1):
        d0 = dist
        dist += (P[i + 1] - P[i]).length
        for j in range(segs):
            a0, a1 = rings[i][j], rings[i][(j + 1) % segs]
            b0, b1 = rings[i + 1][j], rings[i + 1][(j + 1) % segs]
            f = part.face([a0, a1, b1, b0], mat, None, None, weld=False)
            if f is None:
                continue
            c = f.calc_center_median()
            axisp = (P[i] + P[i + 1]) / 2
            if f.normal.dot(c - axisp) < 0:
                f.normal_flip()
            for k, lp in enumerate(f.loops):
                jj = j + (1 if k in (1, 2) else 0)
                along = d0 if k in (0, 1) else dist
                lp[part.uv].uv = (along / tile, jj / segs * 2 * math.pi * radius / tile)
            out.append(f)
    if cap:
        for ring, tdir in ((rings[0], -(P[1] - P[0])), (rings[-1], P[-1] - P[-2])):
            out.append(part.face(ring, mat, tdir.normalized(), (X, Z, tile), weld=False))
    return out


def reproject(part, faces, tile=1.0, grain=None):
    """Planar tile-UVs per face: u along `grain` (Blender vector) projected into the face plane,
    or along the face's longer in-plane extent when grain is None."""
    for f in faces:
        if f is None or not f.is_valid:
            continue
        n = f.normal
        if grain is not None:
            g = Vector(grain)
            U = g - n * g.dot(n)
            if U.length < 1e-4:
                U = X - n * X.dot(n) if abs(n.dot(X)) < 0.9 else Yb - n * Yb.dot(n)
        else:
            cs = [lp.vert.co for lp in f.loops]
            best = None
            for ax in (X, Yb, Z):
                a = ax - n * ax.dot(n)
                if a.length < 0.3:
                    continue
                a.normalize()
                ext = max(c.dot(a) for c in cs) - min(c.dot(a) for c in cs)
                if best is None or ext > best[0]:
                    best = (ext, a)
            U = best[1] if best else X
        U = U.normalized()
        V = n.cross(U).normalized()
        part.project(f, U, V, tile)

# ============================================================================ geometry
def grid_wall(part, mat, plane, a_breaks, u_breaks, holes, normal, U, tile=1.0):
    faces = []
    for i in range(len(a_breaks) - 1):
        for j in range(len(u_breaks) - 1):
            a0, a1 = a_breaks[i], a_breaks[i + 1]
            u0, u1 = u_breaks[j], u_breaks[j + 1]
            ac, uc = (a0 + a1) / 2, (u0 + u1) / 2
            if any(h[0] <= ac <= h[1] and h[2] <= uc <= h[3] for h in holes):
                continue
            faces.append(part.face([plane(a0, u0), plane(a1, u0), plane(a1, u1), plane(a0, u1)], mat, normal,
                                   (U, Z, tile)))
    return faces

def hole_sides(part, hole, a_breaks, u_breaks, plane_at, depths, mats, inward_normals=True, tile=1.0):
    """Walls of a rectangular hole between successive depth planes. plane_at(a, u, depth) -> Vector.
    Normals point into the hole's interior (toward its axis)."""
    x0, x1, u0, u1 = hole
    xs = [b for b in a_breaks if x0 - 1e-6 <= b <= x1 + 1e-6]
    us = [b for b in u_breaks if u0 - 1e-6 <= b <= u1 + 1e-6]
    out = []
    ax, au = (x0 + x1) / 2, (u0 + u1) / 2
    for k in range(len(depths) - 1):
        da, db = depths[k], depths[k + 1]
        m = mats[k]
        for j in range(len(us) - 1):
            for xx in (x0, x1):
                pts = [plane_at(xx, us[j], da), plane_at(xx, us[j + 1], da), plane_at(xx, us[j + 1], db), plane_at(xx, us[j], db)]
                c = sum(pts, Vector()) / 4
                tgt = plane_at(ax, (us[j] + us[j + 1]) / 2, (da + db) / 2)
                nrm = (tgt - c).normalized() if inward_normals else (c - tgt).normalized()
                out.append(part.face(pts, m, nrm, (Z, F, tile)))
        for i in range(len(xs) - 1):
            for uu in (u0, u1):
                pts = [plane_at(xs[i], uu, da), plane_at(xs[i + 1], uu, da), plane_at(xs[i + 1], uu, db), plane_at(xs[i], uu, db)]
                c = sum(pts, Vector()) / 4
                tgt = plane_at((xs[i] + xs[i + 1]) / 2, au, (da + db) / 2)
                nrm = (tgt - c).normalized() if inward_normals else (c - tgt).normalized()
                out.append(part.face(pts, m, nrm, (X, F, tile)))
    return out

def slab_with_holes(part, mat, x0, x1, u0, u1, f_front, f_back, holes, tile=1.0, outer=True, skip_outer=()):
    """A board with rectangular through-holes as ONE mass (frame + rails + muntins, the way a
    CNC'd sash or screen-door frame reads): front/back grids, hole walls, outer edges."""
    ab = sorted({round(v, 6) for v in [x0, x1] + [h[0] for h in holes] + [h[1] for h in holes]})
    ub = sorted({round(v, 6) for v in [u0, u1] + [h[2] for h in holes] + [h[3] for h in holes]})
    faces = []
    for fz, nrm in ((f_front, F), (f_back, -F)):
        for i in range(len(ab) - 1):
            for j in range(len(ub) - 1):
                a0, a1, b0, b1 = ab[i], ab[i + 1], ub[j], ub[j + 1]
                ac, bc = (a0 + a1) / 2, (b0 + b1) / 2
                if any(h[0] <= ac <= h[1] and h[2] <= bc <= h[3] for h in holes):
                    continue
                grain = Z if (b1 - b0) > (a1 - a0) else X          # stiles vertical, rails horizontal
                faces.append(part.face([B(a0, b0, fz), B(a1, b0, fz), B(a1, b1, fz), B(a0, b1, fz)], mat, nrm,
                                       (grain, nrm.cross(grain).normalized(), tile)))
    pa = lambda a, u, d: B(a, u, d)
    for h in holes:
        faces += hole_sides(part, h, ab, ub, pa, [f_front, f_back], [mat], True, tile)
    if outer:
        # outer perimeter faces, split at the grid breaks so the mass stays welded
        for j in range(len(ub) - 1):
            for xx, nx in ((x0, -X), (x1, X)):
                if ('-x' if nx.x < 0 else '+x') in skip_outer:
                    continue
                faces.append(part.face([B(xx, ub[j], f_front), B(xx, ub[j + 1], f_front), B(xx, ub[j + 1], f_back),
                                        B(xx, ub[j], f_back)], mat, nx, (Z, F, tile)))
        for i in range(len(ab) - 1):
            for uu, nz in ((u0, -Z), (u1, Z)):
                if ('-u' if nz.z < 0 else '+u') in skip_outer:
                    continue
                faces.append(part.face([B(ab[i], uu, f_front), B(ab[i + 1], uu, f_front), B(ab[i + 1], uu, f_back),
                                        B(ab[i], uu, f_back)], mat, nz, (X, F, tile)))
    return faces

def square_stack(part, mat, cx, cf, prof, tile=1.0, cap_top=False, cap_bot=False):
    """Square-section turned post: prof = [(half_width, u), ...] bottom->top. One mass."""
    rings = []
    for (hw, u) in prof:
        rings.append([B(cx - hw, u, cf - hw), B(cx + hw, u, cf - hw), B(cx + hw, u, cf + hw), B(cx - hw, u, cf + hw)])
    out = []
    for i in range(len(rings) - 1):
        for j in range(4):
            a0, a1 = rings[i][j], rings[i][(j + 1) % 4]
            b0, b1 = rings[i + 1][j], rings[i + 1][(j + 1) % 4]
            c = (a0 + a1 + b0 + b1) / 4
            nrm = Vector((c.x - cx, c.y + cf, 0.0))
            if abs(prof[i][0] - prof[i + 1][0]) > 1e-6:          # sloped transition: tilt the hint
                nrm.z = (prof[i][0] - prof[i + 1][0]) / max(1e-6, abs(prof[i + 1][1] - prof[i][1])) * 0.5
            out.append(part.face([a0, a1, b1, b0], mat, nrm, (Z, nrm.cross(Z).normalized() if nrm.cross(Z).length > 1e-6 else X, tile)))
    if cap_top:
        out.append(part.face(rings[-1], mat, Z, (X, F, tile)))
    if cap_bot:
        out.append(part.face(rings[0], mat, -Z, (X, F, tile)))
    return out

def prism_x(part, mat, poly, xs, tile=1.0, mats_by_edge=None, caps=True, uv_along_slope=True):
    """Extrude a closed (f,u) polygon along x through the breaks xs. Each edge i can carry its own
    material (mats_by_edge[i]); faces get u along x and v along the edge (slope-aligned)."""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) / 2
    out = []
    for i in range(n):
        (fa, ua), (fb, ub) = poly[i], poly[(i + 1) % n]
        m = mats_by_edge[i] if mats_by_edge else mat
        if m is None:
            continue
        ef, eu = fb - fa, ub - ua
        # outward normal from the winding (works for concave outlines like the roof chevron)
        nf, nu = (eu, -ef) if area > 0 else (-eu, ef)
        nrm = (F * nf + Z * nu).normalized()
        edge_dir = (F * ef + Z * eu).normalized()
        for k in range(len(xs) - 1):
            x0, x1 = xs[k], xs[k + 1]
            pts = [B(x0, ua, fa), B(x1, ua, fa), B(x1, ub, fb), B(x0, ub, fb)]
            out.append(part.face(pts, m, nrm, (X, edge_dir, tile)))
    if caps:
        for xx, nx in ((xs[0], -X), (xs[-1], X)):
            out.append(part.face([B(xx, u, f) for (f, u) in poly], mat, nx, (F, Z, tile)))
    return out

# ---------------------------------------------------------------------------- the parts
def build_body(M, col, root):
    p = Part('house_body')
    # --- foundation: concrete block wall, 2 cm inside the siding plane, top buried under the siding
    box(p, M['found'], -W2 + 0.02, W2 - 0.02, -0.15, U_BASE + 0.02, -D2 + 0.02, D2 - 0.02, skip=('-u', '+u'), grain='x')
    # --- siding shell: front wall with door + window pockets, rear wall, two gable ends
    ab = sorted({-W2, W2, DOOR['x0'], DOOR['x1'], WIN['x0'], WIN['x1']})
    ub = sorted({U_BASE, U_TOP, DOOR['u0'], DOOR['u1'], WIN['u0'], WIN['u1']})
    holes = [(DOOR['x0'], DOOR['x1'], DOOR['u0'], DOOR['u1']), (WIN['x0'], WIN['x1'], WIN['u0'], WIN['u1'])]
    grid_wall(p, M['siding'], lambda a, u: B(a, u, WALL_F), ab, ub, holes, F, X)
    pa = lambda a, u, d: B(a, u, d)
    # door pocket: jamb (trim) all the way to the door's back stop
    hole_sides(p, holes[0], ab, ub, pa, [WALL_F, WALL_F - DOOR['depth']], [M['trim']])
    p.face([B(DOOR['x0'], DOOR['u0'], WALL_F - DOOR['depth']), B(DOOR['x1'], DOOR['u0'], WALL_F - DOOR['depth']),
            B(DOOR['x1'], DOOR['u1'], WALL_F - DOOR['depth']), B(DOOR['x0'], DOOR['u1'], WALL_F - DOOR['depth'])],
           M['trim'], F, (X, Z, 1.0))
    # window pocket: jamb (trim) through the wall thickness, then the room beyond (interior)
    hole_sides(p, holes[1], ab, ub, pa, [WALL_F, WALL_F - 0.15, WALL_F - WIN['depth']], [M['trim'], M['interior']])
    p.face([B(WIN['x0'], WIN['u0'], WALL_F - WIN['depth']), B(WIN['x1'], WIN['u0'], WALL_F - WIN['depth']),
            B(WIN['x1'], WIN['u1'], WALL_F - WIN['depth']), B(WIN['x0'], WIN['u1'], WALL_F - WIN['depth'])],
           M['interior'], F, (X, Z, 1.0))
    # rear wall
    p.face([B(-W2, U_BASE, -D2), B(W2, U_BASE, -D2), B(W2, U_TOP, -D2), B(-W2, U_TOP, -D2)], M['siding'], -F, (X, Z, 1.0))
    # gable ends (pentagon n-gons carrying the front-wall breaks so the corner edges weld)
    for sx in (-1, 1):
        pts = [(-D2, U_BASE), (D2, U_BASE)] + [(D2, u) for u in ub if U_BASE < u < U_TOP] + [(D2, U_TOP), (0.0, U_TOP + D2 * math.tan(PITCH)), (-D2, U_TOP)]
        p.face([B(sx * W2, u, f) for (f, u) in pts], M['siding'], X * sx, (F * (-sx), Z, 1.0))
    # --- trim: water table (rear + sides; the porch deck takes the front)
    T = M['trim']
    box(p, T, -W2 - 0.025, W2 + 0.025, U_BASE, 0.58, -D2 - 0.025, -D2, skip=('+f',), grain='x')
    for sx in (-1, 1):
        xa, xb = sorted((sx * W2, sx * (W2 + 0.025)))
        box(p, T, xa, xb, U_BASE, 0.58, -D2, D2, skip=('-x' if sx > 0 else '+x', '-f'), grain='f')
    # corner boards (L: the face board laps the side board's edge)
    for sx in (-1, 1):
        for sf in (-1, 1):
            u0 = U_FLOOR if sf > 0 else 0.58
            u0s = 0.58
            # board on the front/rear face
            xa, xb = sorted((sx * (W2 - 0.11), sx * (W2 + 0.025)))
            fa, fb = sorted((sf * D2, sf * (D2 + 0.025)))
            box(p, T, xa, xb, u0, U_TOP, fa, fb, skip=('-f' if sf > 0 else '+f', '+u'), grain='u')
            # board on the gable face (under the face board's lap)
            xa, xb = sorted((sx * W2, sx * (W2 + 0.025)))
            fa, fb = sorted((sf * (D2 - 0.11), sf * D2))
            box(p, T, xa, xb, u0s, U_TOP, fa, fb, skip=('-x' if sx > 0 else '+x', '+f' if sf > 0 else '-f', '+u'), grain='u')
    # frieze boards: rear under the soffit, front under the porch ceiling
    box(p, T, -W2 + 0.11, W2 - 0.11, U_TOP - 0.18, U_TOP, -D2 - 0.02, -D2, skip=('+f', '+u', '-x', '+x'), grain='x')
    box(p, T, -W2 + 0.11, W2 - 0.11, U_TOP - 0.12, U_TOP, D2, D2 + 0.02, skip=('-f', '+u', '-x', '+x'), grain='x')
    # base board along the front wall where it meets the porch deck
    box(p, T, -W2 + 0.11, W2 - 0.11, U_FLOOR, U_FLOOR + 0.10, D2, D2 + 0.018,
        skip=('-f', '-u', '-x', '+x'), grain='x')
    # rake friezes: chevron boards along both gable heads, tight under the rake soffit
    for sx in (-1, 1):
        top = [(-D2 - 0.0, U_TOP), (0.0, U_TOP + D2 * math.tan(PITCH)), (D2, U_TOP)]
        poly = top + [(D2 - 0.001, U_TOP - 0.16), (0.0, U_TOP + D2 * math.tan(PITCH) - 0.20), (-D2 + 0.001, U_TOP - 0.16)]
        xs = sorted((sx * W2, sx * (W2 + 0.02)))
        prism_x(p, T, poly, xs, mats_by_edge=[None, None, T, T, T, T], caps=True)
    # door casing: sides, head, drip cap (casing backs are buried against the siding)
    dx0, dx1 = DOOR['x0'], DOOR['x1']
    box(p, T, dx0 - 0.10, dx0, U_FLOOR, DOOR['u1'], D2, D2 + 0.025, skip=('-f', '+u', '-u'), grain='u')
    box(p, T, dx1, dx1 + 0.10, U_FLOOR, DOOR['u1'], D2, D2 + 0.025, skip=('-f', '+u', '-u'), grain='u')
    box(p, T, dx0 - 0.12, dx1 + 0.12, DOOR['u1'], DOOR['u1'] + 0.14, D2, D2 + 0.03, skip=('-f',), grain='x')
    prism_x(p, T, [(D2, DOOR['u1'] + 0.14), (D2 + 0.055, DOOR['u1'] + 0.14), (D2 + 0.055, DOOR['u1'] + 0.155),
                   (D2, DOOR['u1'] + 0.175)], [dx0 - 0.14, dx1 + 0.14], mats_by_edge=[T, T, T, None])
    # threshold (worn, porch-floor paint)
    box(p, M['porchfloor'], dx0, dx1, U_FLOOR, U_FLOOR + 0.018, D2 - DOOR['depth'], D2 + 0.045, skip=('-u',), grain='x')
    # --- gable vents: surface-mounted louvered frames, diagonal fins as geometry
    for sx in (-1, 1):
        cu = 3.95
        hw, hh = 0.24, 0.17
        x_out = sx * (W2 + 0.045)
        xa, xb = sorted((sx * W2, x_out))
        # frame: slab with one hole, depth along x -> build in a local way with boxes on the wall
        for (fa, fb, ua, ub) in ((-hw, hw, cu + hh - 0.05, cu + hh), (-hw, hw, cu - hh, cu - hh + 0.06),
                                 (-hw, -hw + 0.05, cu - hh + 0.06, cu + hh - 0.05), (hw - 0.05, hw, cu - hh + 0.06, cu + hh - 0.05)):
            box(p, T, xa, xb, ua, ub, fa, fb, skip=('-x' if sx > 0 else '+x',), grain='f' if (fb - fa) > (ub - ua) else 'u')
        # dark back
        xback = sx * (W2 + 0.003)
        p.face([B(xback, cu - hh + 0.06, -hw + 0.05), B(xback, cu - hh + 0.06, hw - 0.05),
                B(xback, cu + hh - 0.05, hw - 0.05), B(xback, cu + hh - 0.05, -hw + 0.05)], M['vent'], X * sx, (F, Z, 1.0))
        # fins: 5 slats tilted 45 deg, shedding water outward-down
        n_f = 5
        for k in range(n_f):
            uc = cu - hh + 0.06 + (k + 0.5) * ((2 * hh - 0.11) / n_f)
            d = 0.028
            a_in, a_out = sx * (W2 + 0.006), sx * (W2 + 0.040)
            poly_fu = None
            pts = [B(a_in, uc + d, -hw + 0.05), B(a_out, uc - d, -hw + 0.05), B(a_out, uc - d, hw - 0.05), B(a_in, uc + d, hw - 0.05)]
            p.face(pts, T, Vector((sx, 0, 1)).normalized(), (F, Z, 1.0))
            pts2 = [B(a_in, uc + d - 0.012, -hw + 0.05), B(a_out, uc - d - 0.012, -hw + 0.05), B(a_out, uc - d - 0.012, hw - 0.05), B(a_in, uc + d - 0.012, hw - 0.05)]
            p.face(pts2, T, Vector((-sx, 0, -1)).normalized(), (F, Z, 1.0))
            p.face([pts[1], pts[2], pts2[2], pts2[1]], T, X * sx, (F, Z, 1.0))
    return p.finish(col, smooth_angle=None, parent=root)


def build_window(M, col, root):
    T = M['trim']
    fr = Part('window_frame')
    x0, x1, u0, u1 = WIN['x0'], WIN['x1'], WIN['u0'], WIN['u1']
    # casing: sides, head, drip cap, sill with horns, apron
    box(fr, T, x0 - 0.10, x0, u0, u1, D2, D2 + 0.025, skip=('-f', '+u', '-u'), grain='u')
    box(fr, T, x1, x1 + 0.10, u0, u1, D2, D2 + 0.025, skip=('-f', '+u', '-u'), grain='u')
    box(fr, T, x0 - 0.12, x1 + 0.12, u1, u1 + 0.14, D2, D2 + 0.03, skip=('-f',), grain='x')
    prism_x(fr, T, [(D2, u1 + 0.14), (D2 + 0.055, u1 + 0.14), (D2 + 0.055, u1 + 0.155), (D2, u1 + 0.175)],
            [x0 - 0.14, x1 + 0.14], mats_by_edge=[T, T, T, None])
    prism_x(fr, T, [(D2 - 0.12, u0 + 0.020), (D2 + 0.07, u0 - 0.005), (D2 + 0.07, u0 - 0.05), (D2 - 0.12, u0 - 0.05)],
            [x0 - 0.13, x1 + 0.13])
    box(fr, T, x0 - 0.07, x1 + 0.07, u0 - 0.14, u0 - 0.05, D2, D2 + 0.02, skip=('-f', '+u'), grain='x')
    # double-hung sashes, 6-over-6, each ONE mass (stiles, rails, muntins cut as through-holes)
    glass = Part('window_glass')
    def sash(ua, ub, fa, fb, top_rail, bot_rail):
        st = 0.055
        mw = 0.019
        cols, rows = 3, 2
        ix0, ix1 = x0 + st, x1 - st
        iu0, iu1 = ua + bot_rail, ub - top_rail
        pw = (ix1 - ix0 - (cols - 1) * mw) / cols
        ph = (iu1 - iu0 - (rows - 1) * mw) / rows
        holes = []
        for r in range(rows):
            for c in range(cols):
                hx0 = ix0 + c * (pw + mw)
                hu0 = iu0 + r * (ph + mw)
                holes.append((hx0, hx0 + pw, hu0, hu0 + ph))
        slab_with_holes(fr, T, x0 + 0.004, x1 - 0.004, ua, ub, fb, fa, holes, tile=1.0)
        fm = (fa + fb) / 2
        for (hx0, hx1, hu0, hu1) in holes:
            glass.face([B(hx0, hu0, fm), B(hx1, hu0, fm), B(hx1, hu1, fm), B(hx0, hu1, fm)], M['glass'], F, (X, Z, 1.0),
                       weld=False)
    meet = (u0 + u1) / 2 + 0.02
    sash(meet - 0.018, u1 - 0.004, D2 - 0.075, D2 - 0.040, 0.055, 0.036)        # upper sash, outer track
    sash(u0 + 0.004, meet + 0.018, D2 - 0.118, D2 - 0.083, 0.036, 0.075)        # lower sash, inner track
    # parting bead / stops between the tracks
    for xx in ((x0, x0 + 0.012), (x1 - 0.012, x1)):
        box(fr, T, xx[0], xx[1], u0, u1, D2 - 0.083, D2 - 0.075, grain='u')
    ob_fr = fr.finish(col, None, root)
    ob_gl = glass.finish(col, None, root)
    # curtain: two linen panels gathered on a rod just inside the room, parted a hand's width
    cur = Part('window_curtain')
    fc = D2 - 0.19
    rng = random.Random(7)
    for (px0, px1, gap_side) in ((x0 + 0.01, (x0 + x1) / 2 - 0.02, 1), ((x0 + x1) / 2 + 0.02, x1 - 0.01, -1)):
        nx, nu = 36, 18
        verts = []
        for j in range(nu + 1):
            t = j / nu
            uu = u1 + 0.02 - t * (u1 - u0 + 0.01)
            row = []
            for i in range(nx + 1):
                s = i / nx
                xx = px0 + s * (px1 - px0)
                # the inner edge swings open toward the bottom (drawn back)
                inner = s if gap_side > 0 else 1 - s
                xx -= gap_side * 0.035 * (t ** 1.6) * inner
                pleat = 0.018 * math.sin(2 * math.pi * s * 7.5 + 0.6 * gap_side) * (1.0 - 0.25 * t)
                pleat += 0.004 * math.sin(2 * math.pi * s * 19 + t * 3)
                ff = fc + pleat + 0.01 * t
                row.append(B(xx, uu, ff))
            verts.append(row)
        for j in range(nu):
            for i in range(nx):
                cur.face([verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]], M['curtain'], F,
                         None)
        # uv by true arc length along the pleats
    reproject(cur, list(cur.bm.faces), 1.0, grain=X)
    tube(cur, M['metal'], [(x0 + 0.005, u1 + 0.035, fc - 0.005), (x1 - 0.005, u1 + 0.035, fc - 0.005)], 0.007, 10)
    ob_cu = cur.finish(col, smooth_angle=60, parent=root)
    return ob_fr, ob_gl, ob_cu


def build_door(M, col, root):
    p = Part('door')
    x0, x1 = DOOR['x0'] + 0.005, DOOR['x1'] - 0.005
    u0, u1 = DOOR['u0'] + 0.008, DOOR['u1'] - 0.005
    fb, ff = D2 - DOOR['depth'] + 0.004, D2 - DOOR['depth'] + 0.049
    # four panels: face cells, then inset (recessed field) + inset (raised field): face modelling
    st, tr, mr, br = 0.12, 0.12, 0.16, 0.20
    mu = u0 + 1.05
    px = [x0 + st, (x0 + x1) / 2 - 0.05, (x0 + x1) / 2 + 0.05, x1 - st]
    pu = [u0 + br, mu - mr / 2, mu + mr / 2, u1 - tr]
    holes = [(px[0], px[1], pu[0], pu[1]), (px[2], px[3], pu[0], pu[1]),
             (px[0], px[1], pu[2], pu[3]), (px[2], px[3], pu[2], pu[3])]
    D = M['door']
    ab = sorted({x0, x1, *px})
    ub = sorted({u0, u1, *pu})
    panel_faces = []
    for i in range(len(ab) - 1):
        for j in range(len(ub) - 1):
            a0, a1, b0, b1 = ab[i], ab[i + 1], ub[j], ub[j + 1]
            ac, bc = (a0 + a1) / 2, (b0 + b1) / 2
            f = p.face([B(a0, b0, ff), B(a1, b0, ff), B(a1, b1, ff), B(a0, b1, ff)], D, F,
                       (Z if (b1 - b0) > (a1 - a0) else X, None, 1.0) if False else None)
            if any(h[0] <= ac <= h[1] and h[2] <= bc <= h[3] for h in holes):
                panel_faces.append(f)
    p.face([B(x0, u0, fb), B(x1, u0, fb), B(x1, u1, fb), B(x0, u1, fb)], D, -F)
    for (xx, nx) in ((x0, -X), (x1, X)):
        pts = [B(xx, u, ff) for u in ub] + [B(xx, u1, fb), B(xx, u0, fb)]
        p.face(pts, D, nx)
    for (uu, nz) in ((u0, -Z), (u1, Z)):
        pts = [B(a, uu, ff) for a in ab] + [B(x1, uu, fb), B(x0, uu, fb)]
        p.face(pts, D, nz)
    bm = p.bm
    r1 = bmesh.ops.inset_individual(bm, faces=panel_faces, thickness=0.018, depth=-0.012, use_even_offset=True)
    r2 = bmesh.ops.inset_individual(bm, faces=panel_faces, thickness=0.035, depth=0.009, use_even_offset=True)
    reproject(p, list(bm.faces), 1.0, grain=Z)
    # knob + rose, hinge knuckles
    M_ = M['metal']
    kx, ku = x1 - 0.065, U_FLOOR + 0.93
    lathe(p, M_, [(0.0, 0.0), (0.028, 0.0), (0.030, 0.006), (0.012, 0.012), (0.011, 0.035), (0.026, 0.045),
                  (0.030, 0.062), (0.022, 0.075), (0.0, 0.078)], (kx, ku, ff), segs=20, cap_top=False)
    # the lathe revolves around u; a knob points along f -> rotate those verts afterwards
    for (hu) in (u0 + 0.22, u1 - 0.22):
        lathe(p, M_, [(0.009, -0.05), (0.009, 0.05)], (x0 - 0.002, hu, ff - 0.004), segs=10, cap_top=True, cap_bot=True)
    ob = p.finish(col, smooth_angle=40, parent=root)
    # rotate the knob geometry: verts near (kx, ff) with |z-ku| small were built vertical; turn them to +f
    me = ob.data
    pivot = B(kx, ku, ff)
    R = Matrix.Rotation(math.radians(90), 4, 'X')
    for v in me.vertices:
        if (v.co - pivot).length < 0.09 and abs(v.co.x - kx) < 0.04 and v.co.z >= ku - 0.001:
            v.co = pivot + (R @ (v.co - pivot))
    return ob


def build_screen_door(M, col, root):
    T = M['trim']
    fr = Part('screen_door')
    x0, x1 = DOOR['x0'] + 0.004, DOOR['x1'] - 0.004
    u0, u1 = DOOR['u0'] + 0.02, DOOR['u1'] - 0.004
    fb, ff = D2 - 0.006, D2 + 0.024
    st, tr, br = 0.085, 0.085, 0.20
    pr0, pr1 = U_FLOOR + 0.85, U_FLOOR + 0.97
    holes = [(x0 + st, x1 - st, u0 + br, pr0), (x0 + st, x1 - st, pr1, u1 - tr)]
    slab_with_holes(fr, T, x0, x1, u0, u1, ff, fb, holes)
    # corner brackets in the upper opening (spandrel gussets with a scooped edge)
    hx0, hx1, hu0, hu1 = holes[1]
    fm0, fm1 = fb + 0.006, ff - 0.006
    for (cx, cu, sx, su) in ((hx0, hu1, 1, -1), (hx1, hu1, -1, -1)):
        pts2d = [(0, 0), (0.13, 0)]
        for k in range(1, 8):
            a = k / 8 * (math.pi / 2)
            pts2d.append((0.13 - 0.13 * math.sin(a) * 0.93, 0.13 - 0.13 * math.cos(a) * 0.93 * 1.0 - 0.009 * 0))
        pts2d.append((0, 0.13))
        for fz, nrm in ((fm1, F), (fm0, -F)):
            fr.face([B(cx + sx * a, cu + su * b, fz) for (a, b) in pts2d], T, nrm, (X, Z, 1.0))
        for k in range(len(pts2d)):
            a0, b0 = pts2d[k]; a1, b1 = pts2d[(k + 1) % len(pts2d)]
            q = [B(cx + sx * a0, cu + su * b0, fm1), B(cx + sx * a1, cu + su * b1, fm1),
                 B(cx + sx * a1, cu + su * b1, fm0), B(cx + sx * a0, cu + su * b0, fm0)]
            mid = sum(q, Vector()) / 4
            ctr = B(cx + sx * 0.05, cu + su * 0.05, (fm0 + fm1) / 2)
            fr.face(q, T, (mid - ctr), (Z, F, 1.0))
    # hardware: D pull, a door spring on the inside, two hinges on the hinge stile
    Mt = M['metal']
    hx = x1 - 0.045
    pull = [(hx, pr0 - 0.02, ff), (hx, pr0 - 0.01, ff + 0.03), (hx, pr0 + 0.03, ff + 0.042), (hx, pr1 - 0.03, ff + 0.042),
            (hx, pr1 + 0.01, ff + 0.03), (hx, pr1 + 0.02, ff)]
    tube(fr, Mt, pull, 0.0065, 10)
    for uu in (pr0 - 0.02, pr1 + 0.02):
        lathe(fr, Mt, [(0.013, 0.0), (0.013, 0.004)], (hx, uu, ff), segs=12, cap_top=True)
    # spring: from the push rail (inside face) to a screw eye on the hinge jamb
    A = Vector((x0 + 0.20, pr0 + 0.06, fb - 0.004))
    Bp = Vector((DOOR['x0'] + 0.004, U_FLOOR + 1.62, D2 - 0.045))
    ax = (Bp - A)
    L = ax.length
    axn = ax.normalized()
    ref = Vector((0, 0, 1)) if abs(axn.z) < 0.9 else Vector((1, 0, 0))
    nn = axn.cross(ref).normalized()
    bb = axn.cross(nn).normalized()
    coil0, coil1 = 0.10 * L, 0.88 * L
    pts = [tuple(A)]
    turns = int((coil1 - coil0) / 0.0055)
    steps = turns * 8
    for k in range(steps + 1):
        s = coil0 + (coil1 - coil0) * k / steps
        a = 2 * math.pi * k / 8
        c = A + axn * s + (nn * math.cos(a) + bb * math.sin(a)) * 0.011
        pts.append(tuple(c))
    pts.append(tuple(Bp))
    # pts are design coords (x,u,f) -> tube() expects design; convert
    tube(fr, Mt, pts, 0.0019, 6)
    lathe(fr, Mt, [(0.0, -0.004), (0.006, -0.004), (0.006, 0.004), (0.0, 0.004)], (Bp[0] - 0.003, Bp[1], Bp[2]), segs=8)
    for hu in (u0 + 0.28, u1 - 0.28):
        box(fr, Mt, x0 - 0.035, x0 + 0.055, hu - 0.035, hu + 0.035, ff, ff + 0.003, skip=('-f',), grain='x')
        lathe(fr, Mt, [(0.0065, -0.035), (0.0065, 0.035)], (x0 - 0.004, hu, ff + 0.004), segs=10, cap_top=True, cap_bot=True)
    ob = fr.finish(col, smooth_angle=40, parent=root)
    # screen panels in the frame's groove (mid-depth)
    sc = Part('screen_mesh')
    fm = (ff + fb) / 2
    for (hx0, hx1, hu0, hu1) in holes:
        e = 0.006
        sc.face([B(hx0 - e, hu0 - e, fm), B(hx1 + e, hu0 - e, fm), B(hx1 + e, hu1 + e, fm), B(hx0 - e, hu1 + e, fm)],
                M['screen'], F, (X, Z, 1.0), weld=False)
    ob_sc = sc.finish(col, None, root)
    return ob, ob_sc


def roof_poly():
    ft = [-D2 - OVH_EAVE, 0.0, D2, PORCH_ROOF_F]
    top = [(f, roof_top_u(f)) for f in ft]
    bot = [(PORCH_ROOF_F, roof_bot_u(PORCH_ROOF_F)), (D2, U_TOP), (0.0, roof_bot_u(0.0)), (-D2, U_TOP),
           (-D2 - OVH_EAVE, roof_bot_u(-D2 - OVH_EAVE))]
    return top + bot


def build_roof(M, col, root):
    p = Part('roof')
    poly = roof_poly()
    # edges: 0 rear slope top, 1 front slope top, 2 porch top, 3 porch eave end, 4 porch ceiling,
    #        5 inside (hidden, front), 6 inside (hidden, rear), 7 rear soffit, 8 rear eave end
    R, T, C = M['roof'], M['trim'], M['ceiling']
    inner = [R, R, R, T, C, None, None, T, T]          # underside inside the house: never seen
    outer = [R, R, R, T, C, T, T, T, T]                # rake overhangs keep their soffits
    prism_x(p, R, poly, [-W2 - OVH_RAKE, -W2], mats_by_edge=outer, caps=False)
    prism_x(p, R, poly, [-W2, W2], mats_by_edge=inner, caps=False)
    prism_x(p, R, poly, [W2, W2 + OVH_RAKE], mats_by_edge=outer, caps=False)
    # ridge cap
    rc = [(-0.14, roof_top_u(-0.14) - 0.002), (0.0, U_RIDGE_TOP + 0.035), (0.14, roof_top_u(0.14) - 0.002),
          (0.0, U_RIDGE_TOP - 0.004)]
    prism_x(p, R, rc, [-W2 - OVH_RAKE - 0.015, W2 + OVH_RAKE + 0.015], mats_by_edge=[R, R, None, None])
    # fascia: porch eave and rear eave
    fe = PORCH_ROOF_F
    box(p, T, -W2 - OVH_RAKE - 0.025, W2 + OVH_RAKE + 0.025, roof_bot_u(fe) - 0.07, roof_top_u(fe) + 0.006, fe, fe + 0.025,
        grain='x')
    re = -D2 - OVH_EAVE
    box(p, T, -W2 - OVH_RAKE - 0.025, W2 + OVH_RAKE + 0.025, roof_bot_u(re) - 0.07, roof_top_u(re) + 0.006, re - 0.025, re,
        grain='x')
    # rake boards: chevron along each gable end, covering the roof mass end
    for sx in (-1, 1):
        top = [(re - 0.025, roof_top_u(re) + 0.006), (0.0, U_RIDGE_TOP + 0.012), (D2, U_TOP + ROOF_T + 0.012),
               (fe + 0.025, roof_top_u(fe) + 0.006)]
        bot = [(fe + 0.025, roof_bot_u(fe) - 0.07), (D2, U_TOP - 0.06), (0.0, roof_bot_u(0.0) - 0.065),
               (re - 0.025, roof_bot_u(re) - 0.07)]
        x_in = sx * (W2 + OVH_RAKE)
        xs2 = sorted((x_in, sx * (W2 + OVH_RAKE + 0.025)))
        prism_x(p, T, top + bot, xs2, caps=True)
    ob = p.finish(col, None, root)
    return ob


def build_porch(M, col, root):
    p = Part('porch')
    T, PF = M['trim'], M['porchfloor']
    # deck boards (run along f, away from the house), nosing overhangs the rim 25 mm
    box(p, PF, -W2 - 0.03, W2 + 0.03, U_FLOOR - 0.04, U_FLOOR, D2, PORCH_F + 0.05, skip=('-f',), grain='f')
    # rim boards
    box(p, T, -W2, W2, 0.20, U_FLOOR - 0.04, PORCH_F, PORCH_F + 0.025, skip=('+u',), grain='x')
    for sx in (-1, 1):
        xa, xb = sorted((sx * (W2 - 0.025), sx * W2))
        box(p, T, xa, xb, 0.20, U_FLOOR - 0.04, D2 + 0.02, PORCH_F, skip=('+u', '-f', '+f'), grain='f')
    # piers under the posts, on concrete footings (piers socket into the footing and the rim)
    posts_x = [-2.30, -1.60, -0.20, 2.30]
    for px in posts_x:
        box(p, M['pier'], px - 0.05, px + 0.05, 0.05, U_FLOOR - 0.04, POST_F - 0.05, POST_F + 0.05, skip=('+u', '-u'), grain='u')
        box(p, M['found'], px - 0.13, px + 0.13, -0.10, 0.07, POST_F - 0.13, POST_F + 0.13, skip=('-u',), grain='x')
    # posts: square turned profile, socketed 10 mm into the deck and into the beam
    beam_u0 = 2.61
    prof = [(0.07, U_FLOOR - 0.01), (0.07, U_FLOOR + 0.13), (0.0525, U_FLOOR + 0.155), (0.0525, beam_u0 - 0.10),
            (0.07, beam_u0 - 0.075), (0.07, beam_u0 + 0.01)]
    for px in posts_x:
        square_stack(p, T, px, POST_F, prof)
    # beam with its top cut to the porch roof slope
    f0, f1 = POST_F - 0.06, POST_F + 0.06
    poly = [(f0, beam_u0), (f1, beam_u0), (f1, roof_bot_u(f1) + 0.004), (f0, roof_bot_u(f0) + 0.004)]
    prism_x(p, T, poly, [-W2, W2], caps=True)
    # railings: top rail + bottom rail + square balusters. Rails end inside the posts; balusters
    # socket into both rails (no buried caps).
    hw = 0.0525
    spans = [('x', -2.30, -1.60), ('x', -0.20, 2.30), ('f', -2.30, None), ('f', 2.30, None)]
    for kind, a, b in spans:
        if kind == 'x':
            ra, rb = a + hw - 0.01, b - hw + 0.01
            box(p, T, ra, rb, U_FLOOR + 0.855, U_FLOOR + 0.90, POST_F - 0.035, POST_F + 0.035, skip=('-x', '+x'), grain='x')
            box(p, T, ra, rb, U_FLOOR + 0.08, U_FLOOR + 0.125, POST_F - 0.0225, POST_F + 0.0225, skip=('-x', '+x'), grain='x')
            n = max(1, int((rb - ra) / 0.105))
            for k in range(n):
                cx = ra + (rb - ra) * (k + 0.5) / n
                box(p, T, cx - 0.0175, cx + 0.0175, U_FLOOR + 0.115, U_FLOOR + 0.865, POST_F - 0.0175, POST_F + 0.0175,
                    skip=('-u', '+u'), grain='u')
        else:
            xx = a
            ra, rb = D2 + 0.015, POST_F - hw + 0.01
            box(p, T, xx - 0.035, xx + 0.035, U_FLOOR + 0.855, U_FLOOR + 0.90, ra, rb, skip=('-f', '+f'), grain='f')
            box(p, T, xx - 0.0225, xx + 0.0225, U_FLOOR + 0.08, U_FLOOR + 0.125, ra, rb, skip=('-f', '+f'), grain='f')
            n = max(1, int((rb - ra) / 0.105))
            for k in range(n):
                cf = ra + (rb - ra) * (k + 0.5) / n
                box(p, T, xx - 0.0175, xx + 0.0175, U_FLOOR + 0.115, U_FLOOR + 0.865, cf - 0.0175, cf + 0.0175,
                    skip=('-u', '+u'), grain='u')
    return p.finish(col, None, root)


def build_steps(M, col, root):
    p = Part('steps')
    T, PF = M['trim'], M['porchfloor']
    x0, x1 = -1.50, -0.30
    # open (cut) stringers: the sawtooth follows the underside of each tread and riser
    st = [(PORCH_F, 0.265), (3.905, 0.265), (3.905, 0.115), (4.185, 0.115), (4.185, -0.03), (3.93, -0.03),
          (PORCH_F, 0.10)]
    for xc in (x0 + 0.065, (x0 + x1) / 2, x1 - 0.065):
        prism_x(p, T, st, [xc - 0.024, xc + 0.024], caps=True)
    # treads with 25 mm nosings, ends proud of the stringers; closed risers set under the nosings
    box(p, PF, x0, x1, 0.265, 0.30, PORCH_F + 0.005, 3.930, grain='x')
    box(p, PF, x0, x1, 0.115, 0.15, 3.880, 4.210, grain='x')
    box(p, T, x0 + 0.015, x1 - 0.015, 0.15, 0.265, 3.885, 3.905, skip=('-u', '+u', '-f'), grain='x')
    box(p, T, x0 + 0.015, x1 - 0.015, -0.03, 0.115, 4.165, 4.185, skip=('-u', '+u', '-f'), grain='x')
    return p.finish(col, None, root)


def build_chimney(M, col, root):
    p = Part('chimney')
    Mt = M['metal']
    cx, cf = 1.55, -0.35
    ur = roof_top_u(cf)
    top = ur + 0.92
    # pipe with two crimped joints
    prof = [(0.075, ur - 0.06 - ur), (0.075, 0.30), (0.079, 0.31), (0.079, 0.33), (0.075, 0.34), (0.075, 0.62),
            (0.079, 0.63), (0.079, 0.65), (0.075, 0.66), (0.075, top - ur)]
    lathe(p, Mt, [(r, h) for (r, h) in prof], (cx, ur, cf), segs=24, cap_top=True)
    # storm collar
    lathe(p, Mt, [(0.078, 0.14), (0.098, 0.10), (0.118, 0.035), (0.118, 0.025), (0.0785, 0.025)], (cx, ur, cf), segs=24)
    # flashing plate on the slope (4 mm proud of the shingles)
    s = 0.26
    corners = [(cx - s, cf - s), (cx + s, cf - s), (cx + s, cf + s), (cx - s, cf + s)]
    topv = [B(x, roof_top_u(f) + 0.004, f) for (x, f) in corners]
    botv = [B(x, roof_top_u(f) - 0.001, f) for (x, f) in corners]
    nrm = (B(0, roof_top_u(cf + 0.1), cf + 0.1) - B(0, roof_top_u(cf), cf)).cross(X).normalized()
    if nrm.z < 0:
        nrm = -nrm
    p.face(topv, Mt, nrm, (X, F, 0.35))
    for k in range(4):
        a, b = k, (k + 1) % 4
        q = [topv[a], topv[b], botv[b], botv[a]]
        mid = sum(q, Vector()) / 4
        p.face(q, Mt, mid - B(cx, ur, cf), (X, Z, 0.35))
    # rain cap on three straps
    cap_u = top + 0.07
    lathe(p, Mt, [(0.0, 0.13), (0.03, 0.12), (0.145, 0.035), (0.150, 0.025), (0.140, 0.022), (0.03, 0.105), (0.0, 0.112)],
          (cx, cap_u, cf), segs=24)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3
        ox, of = math.cos(a) * 0.08, math.sin(a) * 0.08
        box(p, Mt, cx + ox - 0.008, cx + ox + 0.008, top - 0.03, cap_u + 0.06, cf + of - 0.003, cf + of + 0.003, grain='u')
    return p.finish(col, smooth_angle=35, parent=root)


def build_lamp(M, col, root):
    """Wall jelly-jar lantern (refs/ref_03): wall block, plate, gooseneck arm, canopy, collar,
    ribbed jar hanging down inside a 4-wire guard, A15 bulb with a filament."""
    Mt = M['metal']
    fx = Part('lamp_fixture')
    lx = LAMP_X
    fj = D2 + 0.155                    # jar axis
    # mounting block (painted wood) on the shingles, plate on the block
    box(fx, M['trim'], lx - 0.085, lx + 0.085, 2.30, 2.62, D2, D2 + 0.028, skip=('-f',), grain='u')
    plate = [(0.045, -0.07), (0.05, -0.065), (0.05, 0.065), (0.045, 0.07), (-0.045, 0.07), (-0.05, 0.065), (-0.05, -0.065),
             (-0.045, -0.07)]
    pu = 2.47
    f0, f1 = D2 + 0.028, D2 + 0.040
    fx.face([B(lx + a, pu + b, f1) for (a, b) in plate], Mt, F, (X, Z, 0.35))
    for k in range(len(plate)):
        (a0, b0), (a1, b1) = plate[k], plate[(k + 1) % len(plate)]
        q = [B(lx + a0, pu + b0, f0), B(lx + a1, pu + b1, f0), B(lx + a1, pu + b1, f1), B(lx + a0, pu + b0, f1)]
        mid = sum(q, Vector()) / 4
        fx.face(q, Mt, mid - B(lx, pu, (f0 + f1) / 2), (Z, F, 0.35))
    # bracket arm: straight out of the plate, resting on the canopy crown (2 mm into it), a
    # collar where it leaves the plate and a finial nut through the crown
    arm_u = 2.4105 + 0.098 + 0.007
    tube(fx, Mt, [(lx, arm_u, f1 - 0.004), (lx, arm_u, fj + 0.012)], 0.0085, 12, cap=True)
    tube(fx, Mt, [(lx, arm_u, f1 - 0.002), (lx, arm_u, f1 + 0.014)], 0.0135, 12, cap=True)
    lathe(fx, Mt, [(0.0100, -0.012), (0.0100, 0.012), (0.0065, 0.020), (0.0, 0.024)], (lx, arm_u + 0.004, fj), segs=12)
    # canopy (dome) + socket collar with thread rings
    cu = 2.4105
    lathe(fx, Mt, [(0.0, 0.098), (0.018, 0.096), (0.044, 0.078), (0.056, 0.052), (0.060, 0.040), (0.060, 0.034),
                   (0.036, 0.034)], (lx, cu, fj), segs=32, cap_bot=True)
    lathe(fx, Mt, [(0.036, 0.034), (0.036, 0.006), (0.038, 0.004), (0.038, -0.002), (0.034, -0.004), (0.034, -0.012)],
          (lx, cu, fj), segs=32)
    # guard: 4 wires from the collar ring down around the jar to a bottom boss, two hoops
    ring_r = 0.056
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        pts = []
        for s in range(9):
            h = -0.004 - s * 0.018
            r = ring_r if h > -0.13 else ring_r - (h + 0.13) * -1.6
            r = min(ring_r, max(0.012, r))
            pts.append((lx + math.cos(a) * r, cu + h, fj + math.sin(a) * r))
        pts.append((lx + math.cos(a) * 0.012, cu - 0.163, fj + math.sin(a) * 0.012))
        tube(fx, Mt, pts, 0.0026, 6)
    for hh in (-0.045, -0.105):
        ring = [(lx + math.cos(2 * math.pi * j / 32) * (ring_r + 0.001), cu + hh, fj + math.sin(2 * math.pi * j / 32) * (ring_r + 0.001))
                for j in range(33)]
        tube(fx, Mt, ring, 0.0028, 6)
    lathe(fx, Mt, [(0.0, -0.172), (0.016, -0.168), (0.018, -0.158), (0.010, -0.154), (0.0, -0.153)], (lx, cu, fj), segs=16)
    ob_fx = fx.finish(col, smooth_angle=45, parent=root)
    # ribbed glass jar
    jar = Part('lamp_glass')
    rib = lambda a, h: 1.0 + (0.045 * max(0.0, math.cos(16 * a)) ** 3 if -0.132 < h < -0.02 else 0.0)
    lathe(jar, M['jar'], [(0.034, -0.010), (0.044, -0.020), (0.047, -0.034), (0.047, -0.118), (0.043, -0.134),
                          (0.030, -0.146), (0.012, -0.151), (0.0, -0.152)], (lx, cu, fj), segs=64, radial_fn=rib)
    ob_jar = jar.finish(col, smooth_angle=80, parent=root)
    # bulb (A15) + filament
    bl = Part('lamp_bulb')
    lathe(bl, M['bulb'], [(0.012, -0.012), (0.013, -0.030), (0.020, -0.050), (0.0235, -0.068), (0.023, -0.083),
                          (0.019, -0.096), (0.010, -0.105), (0.0, -0.107)], (lx, cu, fj), segs=24)
    fil = []
    for k in range(25):
        a = k / 24 * 2 * math.pi * 2.0
        fil.append((lx + math.cos(a) * 0.006, cu - 0.058 - 0.012 * math.sin(k / 24 * math.pi), fj + math.sin(a) * 0.006))
    tube(bl, M['filament'], fil, 0.0012, 5)
    tube(bl, M['wire'], [(lx - 0.003, cu - 0.020, fj), (lx - 0.006, cu - 0.058, fj)], 0.0006, 4)
    tube(bl, M['wire'], [(lx + 0.003, cu - 0.020, fj), (lx + 0.006, cu - 0.058, fj)], 0.0006, 4)
    ob_bulb = bl.finish(col, smooth_angle=80, parent=root)
    return ob_fx, ob_jar, ob_bulb, B(lx, cu - 0.064, fj)


def empty(name, loc, root, col):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'SPHERE'
    e.empty_display_size = 0.05
    e.location = loc
    col.objects.link(e)
    e.parent = root
    return e


def build_all():
    sys.path.insert(0, ROOT)
    import importlib, house_mats
    importlib.reload(house_mats)
    geo_info = dict(u_top=U_TOP, win=(WIN['x0'], WIN['x1'], WIN['u0']))
    M = house_mats.make_materials(TEX, ROOT, geo_info)
    col = bpy.data.collections.new('house')
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new('house', None)
    col.objects.link(root)
    obs = {}
    obs['house_body'] = build_body(M, col, root)
    obs['window_frame'], obs['window_glass'], obs['window_curtain'] = build_window(M, col, root)
    obs['door'] = build_door(M, col, root)
    obs['screen_door'], obs['screen_mesh'] = build_screen_door(M, col, root)
    obs['roof'] = build_roof(M, col, root)
    obs['porch'] = build_porch(M, col, root)
    obs['steps'] = build_steps(M, col, root)
    obs['chimney'] = build_chimney(M, col, root)
    obs['lamp_fixture'], obs['lamp_glass'], obs['lamp_bulb'], bulb_c = build_lamp(M, col, root)
    empty('lamp_light_point', bulb_c, root, col)
    empty('window_light_point', B((WIN['x0'] + WIN['x1']) / 2, (WIN['u0'] + WIN['u1']) / 2, D2 - 0.5), root, col)
    return M, obs

# ============================================================================ look-dev lighting + renders
def world(color, strength):
    w = bpy.data.worlds.new('world')
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*color, 1.0)
    bg.inputs['Strength'].default_value = strength
    return w

def light(kind, name, loc, rot=None, energy=1.0, color=(1, 1, 1), size=0.1, spot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = size
    if kind == 'AREA':
        ld.size = size
    if kind == 'SUN':
        ld.angle = math.radians(size)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    return ob

def cam(name, loc, target, lens=35):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.02
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

def ground(M):
    me = bpy.data.meshes.new('ground')
    bm = bmesh.new()
    s = 30
    vs = [bm.verts.new(v) for v in ((-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0))]
    bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('ground', me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new('sand_lookdev')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.42, 0.38, 0.31, 1)
    b.inputs['Roughness'].default_value = 0.95
    me.materials.append(m)
    return ob

def render_setup(res=(1280, 720), samples=48):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    try:
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_raytracing = True
        sc.eevee.use_shadows = True
    except Exception as e:
        print('eevee settings:', e)
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.render.image_settings.file_format = 'PNG'

def do_render(camobj, path):
    sc = bpy.context.scene
    sc.camera = camobj
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[render]', path)

def lookdev(mode, outdir, obs, M):
    os.makedirs(outdir, exist_ok=True)
    sc = bpy.context.scene
    for o in list(sc.collection.objects):
        if o.type in ('LIGHT', 'CAMERA'):
            bpy.data.objects.remove(o)
    render_setup()
    bulb = M['filament']
    bsdf = bulb.node_tree.nodes['Principled BSDF']
    if mode == 'neutral':
        world((0.55, 0.6, 0.68), 0.9)
        bsdf.inputs['Emission Strength'].default_value = 0.0
        light('SUN', 'sun', (0, 0, 10), (math.radians(50), 0, math.radians(35)), 3.2, (1.0, 0.96, 0.9), 2.0)
        shots = {
            'front': ((1.2, -13.5, 2.4), (0.0, 0.0, 2.1), 40),
            'front34': ((9.0, -10.5, 3.2), (0.0, 0.0, 2.0), 38),
            'left34': ((-10.0, -8.0, 3.8), (0.0, 0.0, 2.2), 38),
            'rear34': ((-9.0, 10.5, 4.2), (0.0, 0.0, 2.4), 38),
        }
    elif mode == 'night':
        world((0.010, 0.014, 0.028), 1.0)
        bsdf.inputs['Emission Strength'].default_value = 60.0
        light('SUN', 'moon', (0, 0, 10), (math.radians(40), 0, math.radians(-150)), 0.35, (0.62, 0.72, 1.0), 1.0)
        lp = obs['_lamp']
        light('POINT', 'porch_bulb', lp, None, 25.0, (1.0, 0.72, 0.42), 0.02)
        light('AREA', 'window_glow', B(1.1, 1.83, D2 - 0.30), (math.radians(90), 0, 0), 30.0, (1.0, 0.68, 0.36), 0.8)
        shots = {
            'night_front': ((2.0, -14.0, 1.9), (0.0, 0.0, 1.9), 38),
            'night_34': ((8.5, -11.0, 2.6), (0.0, 0.0, 1.8), 36),
        }
    else:   # lamp / screen close-ups in neutral light + lamp on
        world((0.35, 0.38, 0.44), 0.6)
        bsdf.inputs['Emission Strength'].default_value = 30.0
        light('SUN', 'sun', (0, 0, 10), (math.radians(55), 0, math.radians(25)), 2.0, (1.0, 0.96, 0.9), 2.0)
        light('POINT', 'porch_bulb', obs['_lamp'], None, 6.0, (1.0, 0.72, 0.42), 0.02)
        lb = obs['_lamp']
        shots = {
            'lamp_close': ((lb.x + 0.55, lb.y - 0.75, lb.z + 0.05), (lb.x, lb.y, lb.z + 0.02), 50),
            'door_close': ((-0.2, -5.2, 1.5), (-0.75, -2.0, 1.45), 40),
            'window_close': ((1.6, -4.8, 1.9), (1.1, -2.0, 1.8), 45),
        }
    for k, (loc, tgt, lens) in shots.items():
        c = cam('cam_' + k, loc, tgt, lens)
        do_render(c, os.path.join(outdir, f'{k}.png'))


if __name__ == '__main__':
    reset()
    M, obs = build_all()
    obs['_lamp'] = bpy.data.objects['lamp_light_point'].location.copy()
    ground(M)
    stats = {}
    for n, o in obs.items():
        if n.startswith('_') or o.type != 'MESH':
            continue
        o.data.calc_loop_triangles()
        stats[n] = len(o.data.loop_triangles)
    print('[tris]', json.dumps(stats), 'total', sum(stats.values()))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'house_src.blend'))
    mode = arg('--render')
    if mode:
        modes = ['neutral', 'night', 'lamp'] if mode == 'all' else [mode]
        for md in modes:
            lookdev(md, os.path.join(ROOT, 'renders', 'src'), obs, M)
