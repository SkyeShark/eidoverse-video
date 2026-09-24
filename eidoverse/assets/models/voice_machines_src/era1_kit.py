"""era1_kit.py — shared Blender (5.2, headless) toolkit for the DAISY verse-1 machines.

Hard-surface by the house laws: masses are ONE mesh cut/inset/extruded/bevelled
(bmesh face modelling), separate objects only for genuinely separate hardware
(screws, knobs, keys, reels, cables). Every hard edge gets a real chamfer
(Bevel modifier, angle-limited, harden normals + weighted normals).

Materials here are ROLE slots ('era1_<role>'); the eidoverse module rebuilds each
role as a layered NodeMaterial (tiling AmbientCG PBR set on UV0 in metres + baked
masks on UV1). So this file bakes the MASKS the layered materials need:
    R = ambient occlusion (0.35 m)   G = cavity (short-range AO, 0.03 m)
    B = convexity (Cycles pointiness → edge wear)
into <name>_mask.png on a shared UV1 atlas, and exports <name>.glb.

Blender axes: front = -Y, up = +Z (glTF export turns this into +Z toward the
camera and +Y up, the prop contract's frame).
"""
import bpy
import bmesh
import math
import os
import json
from mathutils import Vector, Matrix, Euler

def _repo_root():                 # library copy: this was a local absolute path; now the folder holding eido.py
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d) and not os.path.exists(os.path.join(d, "eido.py")):
        d = os.path.dirname(d)
    return d
ROOT = os.environ.get("EIDOVERSE_ROOT") or _repo_root()
OUT = ROOT + "/work/daisy/props/assets/era1"
os.makedirs(OUT, exist_ok=True)

# ── scene ────────────────────────────────────────────────────────────────
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    return sc


def link(ob, parent=None):
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def deselect():
    for o in bpy.context.view_layer.objects:
        o.select_set(False)


def activate(ob):
    deselect()
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


# ── materials: role slots ────────────────────────────────────────────────
PREVIEW = {}


def mat(role, rgb=(0.7, 0.7, 0.7), rough=0.5, metal=0.0):
    name = 'era1_' + role
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes.get('Principled BSDF')
        if b:
            b.inputs['Base Color'].default_value = (*rgb, 1)
            b.inputs['Roughness'].default_value = rough
            b.inputs['Metallic'].default_value = metal
    return m


def set_mats(ob, roles):
    """roles: list of role names; face material_index indexes this list.
    (Never materials.clear(): on a fresh mesh it would zero the face indices.)"""
    mats = ob.data.materials
    for i, r in enumerate(roles):
        if i < len(mats):
            mats[i] = mat(r)
        else:
            mats.append(mat(r))
    return ob


# ── bmesh helpers ────────────────────────────────────────────────────────
def bm_box(bm, w, d, h, c=(0, 0, 0)):
    """Box centred at c: x-width w, y-depth d, z-height h. Returns new faces."""
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r['verts']
    bmesh.ops.scale(bm, vec=(w, d, h), verts=vs)
    bmesh.ops.translate(bm, vec=Vector(c), verts=vs)
    return list({f for v in vs for f in v.link_faces})


def rrect_pts(x0, x1, y0, y1, radii, seg=10):
    """CCW 2D points of a rounded rectangle; radii = [r(x0,y0), r(x1,y0), r(x1,y1), r(x0,y1)]."""
    r = radii if isinstance(radii, (list, tuple)) else [radii] * 4
    corners = [(x0 + r[0], y0 + r[0], math.pi, 1.5 * math.pi, r[0]), (x1 - r[1], y0 + r[1], 1.5 * math.pi, 2 * math.pi, r[1]),
               (x1 - r[2], y1 - r[2], 0.0, 0.5 * math.pi, r[2]), (x0 + r[3], y1 - r[3], 0.5 * math.pi, math.pi, r[3])]
    pts = []
    for (cx, cy, a0, a1, rr) in corners:
        if rr < 1e-5:
            pts.append((cx, cy))
            continue
        for k in range(seg + 1):
            a = a0 + (a1 - a0) * k / seg
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    out = []
    for p in pts:
        if not out or (abs(out[-1][0] - p[0]) + abs(out[-1][1] - p[1])) > 1e-7:
            out.append(p)
    if (abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1])) < 1e-7:
        out.pop()
    return out


def bm_prism(bm, pts2d, z0, z1):
    """Vertical prism from a CCW plan polygon (x, y) between z0 and z1. Returns all faces."""
    vs = [bm.verts.new((x, y, z0)) for (x, y) in pts2d]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.z > 0:
        f.normal_flip()
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, z1 - z0), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return list(bm.faces)


def bm_profile_x(bm, pts_yz, x0, x1):
    """Side profile polygon in the YZ plane extruded along X from x0 to x1."""
    vs = [bm.verts.new((x0, y, z)) for (y, z) in pts_yz]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(x1 - x0, 0, 0), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return list(bm.faces)


def bisect_all(bm, co, no):
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=co, plane_no=no)


def groove_band(bm, axis, a, b, depth, side_only=True, thick=0.0006):
    """Cut a groove band between coordinates a..b along `axis` ('x'|'y'|'z') into every
    face ring it crosses (bisect twice, push the band inward by `depth` with walls)."""
    i = 'xyz'.index(axis)
    no = Vector((0, 0, 0)); no[i] = 1.0
    for v in (a, b):
        co = Vector((0, 0, 0)); co[i] = v
        bisect_all(bm, co, no)
    band = []
    for f in bm.faces:
        c = f.calc_center_median()
        if a < c[i] < b and (not side_only or abs(f.normal[i]) < 0.3):
            band.append(f)
    if band:
        bmesh.ops.inset_region(bm, faces=band, thickness=thick, depth=-depth, use_even_offset=True)
    return band


def seam_rect(bm, face, axis_u, axis_v, u0, u1, v0, v1, gap=0.003, depth=0.003):
    """A door/panel outline: a groove `gap` wide and `depth` deep cut around the
    rectangle into a planar face (bisect + inset ring + push). Returns the panel faces."""
    inside, _ = cut_rect(bm, face, axis_u, axis_v, u0, u1, v0, v1)
    r = bmesh.ops.inset_region(bm, faces=inside, thickness=gap, depth=0.0, use_even_offset=True)
    bmesh.ops.inset_region(bm, faces=r['faces'], thickness=0.0002, depth=-depth, use_even_offset=True)
    return inside


def uv_matid(ob, matid, name='matid'):
    """Extra UV layer whose U carries a sub-material id (for one-draw-call multi-part props)."""
    me = ob.data
    lay = me.uv_layers.get(name) or me.uv_layers.new(name=name)
    for d in lay.data:
        d.uv = (float(matid) + 0.5, 0.5)
    return ob


def face_toward(faces, direction):
    d = Vector(direction).normalized()
    return max(faces, key=lambda f: f.normal.dot(d) + 1e-3 * f.calc_area())


def faces_toward(faces, direction, tol=0.95):
    d = Vector(direction).normalized()
    return [f for f in faces if f.normal.dot(d) > tol]


def inset(bm, faces, thickness, depth=0.0, individual=False):
    """Inset (and push) a region. Returns (inner_faces, rim_faces)."""
    if individual:
        r = bmesh.ops.inset_individual(bm, faces=faces, thickness=thickness, depth=depth, use_even_offset=True)
    else:
        r = bmesh.ops.inset_region(bm, faces=faces, thickness=thickness, depth=depth, use_even_offset=True)
    return faces, r['faces']


def recess(bm, faces, border, depth):
    """Proud frame + recessed field with REAL reveal walls: inset flat by `border`,
    then push the field back by `depth` (negative = outward boss). Returns
    (field_faces, wall_faces, frame_faces)."""
    frame = []
    if border > 1e-6:
        r = bmesh.ops.inset_region(bm, faces=faces, thickness=border, depth=0.0, use_even_offset=True)
        frame = r['faces']
    n = Vector()
    for f in faces:
        n += f.normal * f.calc_area()
    n.normalize()
    ex = bmesh.ops.extrude_face_region(bm, geom=faces)
    verts = [e for e in ex['geom'] if isinstance(e, bmesh.types.BMVert)]
    newf = [e for e in ex['geom'] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, vec=-n * depth, verts=verts)
    bmesh.ops.delete(bm, geom=faces, context='FACES')
    field = [f for f in newf if f.normal.dot(n) > 0.99]
    walls = [f for f in newf if f not in field]
    return field, walls, frame


def extrude(bm, faces, dist):
    """Extrude a face region along its average normal by dist. Returns (top faces, side faces)."""
    n = Vector()
    for f in faces:
        n += f.normal * f.calc_area()
    n.normalize()
    r = bmesh.ops.extrude_face_region(bm, geom=faces)
    verts = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    new_faces = [e for e in r['geom'] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, vec=n * dist, verts=verts)
    bmesh.ops.delete(bm, geom=faces, context='FACES')
    sides = [f for f in new_faces]
    tops = [f for f in new_faces if f.normal.dot(n) > 0.99]
    sides = [f for f in new_faces if f not in tops]
    return tops, sides


def region_in_rect(faces, axis_u, axis_v, u0, u1, v0, v1):
    """Faces whose centre lies in the (u,v) rectangle (axes are 'x','y','z')."""
    iu, iv = 'xyz'.index(axis_u), 'xyz'.index(axis_v)
    out = []
    for f in faces:
        c = f.calc_center_median()
        if u0 <= c[iu] <= u1 and v0 <= c[iv] <= v1:
            out.append(f)
    return out


def cut_rect(bm, face, axis_u, axis_v, u0, u1, v0, v1):
    """Knife a rectangle into a planar face with 4 bisects restricted to that face's
    geometry; returns the faces inside the rectangle. (Local cuts only — global
    planes spiderweb the mesh.)"""
    iu, iv = 'xyz'.index(axis_u), 'xyz'.index(axis_v)
    region = [face]
    for (i, val) in ((iu, u0), (iu, u1), (iv, v0), (iv, v1)):
        no = Vector((0, 0, 0)); no[i] = 1.0
        co = Vector((0, 0, 0)); co[i] = val
        geom = list({v for f in region for v in f.verts}) + list({e for f in region for e in f.edges}) + region
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=co, plane_no=no)
        new_faces = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace)]
        region = list(set(region) | set(new_faces))
        region = [f for f in region if f.is_valid]
    return region_in_rect(region, axis_u, axis_v, u0 + 1e-5, u1 - 1e-5, v0 + 1e-5, v1 - 1e-5), region


def new_mesh_obj(name, bm, roles, parent=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob, parent)
    set_mats(ob, roles)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


# ── modifiers ────────────────────────────────────────────────────────────
def bevel(ob, width=0.003, segments=3, angle=35, profile=0.5, harden=True, clamp=True):
    m = ob.modifiers.new('chamfer', 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.use_clamp_overlap = clamp
    m.harden_normals = harden
    m.miter_outer = 'MITER_ARC'
    return m


def weighted_normals(ob):
    m = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
    m.keep_sharp = True
    m.weight = 50
    return m


def finish(ob, width=0.003, segments=3, angle=35, harden=True):
    """Chamfer every hard edge + weighted normals; shaded smooth so the bevels read."""
    for p in ob.data.polygons:
        p.use_smooth = True
    bevel(ob, width, segments, angle, harden=harden)
    weighted_normals(ob)
    return ob


def apply_mods(ob):
    activate(ob)
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            print('[kit] modifier apply failed', ob.name, m.name, e)
    return ob


def boolean(ob, cutter, op='DIFFERENCE', apply=True, keep_cutter=False):
    m = ob.modifiers.new('bool', 'BOOLEAN')
    m.object = cutter
    m.operation = op
    m.solver = 'EXACT'
    if apply:
        activate(ob)
        bpy.ops.object.modifier_apply(modifier=m.name)
        if not keep_cutter:
            bpy.data.objects.remove(cutter, do_unlink=True)
        clean_slots(ob)
    return ob


def clean_slots(ob):
    """Drop empty material slots a boolean may have added (bake + export hate them)."""
    me = ob.data
    used = {p.material_index for p in me.polygons}
    for i in range(len(me.materials) - 1, -1, -1):
        if me.materials[i] is None and i not in used:
            me.materials.pop(index=i)
    return ob


def cutter_box(w, d, h, c, rot=(0, 0, 0)):
    bm = bmesh.new()
    bm_box(bm, w, d, h)
    me = bpy.data.meshes.new('_cut')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('_cut', me)
    link(o)
    o.location = c
    o.rotation_euler = rot
    bpy.context.view_layer.update()
    return o


def cutter_cyl(r, depth, c, rot=(0, 0, 0), seg=48):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=depth)
    me = bpy.data.meshes.new('_cutc')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('_cutc', me)
    link(o)
    o.location = c
    o.rotation_euler = rot
    bpy.context.view_layer.update()
    return o


# ── primitive hardware (separate objects by nature) ──────────────────────
def lathe(name, profile, role, seg=48, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, flutes=0, flute_depth=0.0,
          flute_z=(0.0, 1.0)):
    """profile: [(r, z), ...] bottom→top, revolved about Z. r == 0 rows become proper
    triangle-fan caps (a single pole vertex). Optional flutes (knurling)."""
    bm = bmesh.new()
    rows = []
    for (r, z) in profile:
        if r < 1e-6:
            rows.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            rr = r
            if flutes and flute_z[0] <= z <= flute_z[1]:
                rr = r * (1 - flute_depth * max(0.0, math.cos(a * flutes)) ** 2)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
        rows.append(ring)
    for i in range(len(rows) - 1):
        A, Bv = rows[i], rows[i + 1]
        if len(A) == 1 and len(Bv) == 1:
            continue
        for k in range(seg):
            if len(A) == 1:
                bm.faces.new((A[0], Bv[(k + 1) % seg], Bv[k]))
            elif len(Bv) == 1:
                bm.faces.new((A[k], A[(k + 1) % seg], Bv[0]))
            else:
                bm.faces.new((A[k], A[(k + 1) % seg], Bv[(k + 1) % seg], Bv[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_mesh_obj(name, bm, [role], parent)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def screw(name, r=0.0035, h=0.0022, role='chrome', loc=(0, 0, 0), normal=(0, -1, 0), parent=None, slot=True):
    """Pan-head slotted screw sitting on a surface with the given outward normal."""
    prof = [(0, 0), (r, 0), (r, h * 0.35), (r * 0.9, h * 0.75), (r * 0.6, h), (0, h)]
    ob = lathe(name, prof, role, seg=20, parent=parent)
    if slot:
        cut = cutter_box(r * 2.6, r * 0.32, h * 1.2, (0, 0, h))
        boolean(ob, cut)
    n = Vector(normal).normalized()
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = n.to_track_quat('Z', 'Y')
    ob.location = loc
    return ob


def curve_tube(name, pts, radius, role, parent=None, res=6, bevel_res=4):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = bevel_res
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        bp = sp.bezier_points[i]
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    sp.resolution_u = res
    ob = bpy.data.objects.new(name, cu)
    link(ob, parent)
    ob.data.materials.append(mat(role))
    activate(ob)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.view_layer.objects.active
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def plane_decal(name, w, h, loc, normal, role, parent=None, up=(0, 0, 1)):
    """A label/decal quad (UV 0..1), centred, facing `normal`, 0.4 mm proud of loc."""
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0))]
    f = bm.faces.new(vs)
    uvl = bm.loops.layers.uv.new('tile')
    for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        l[uvl].uv = uv
    ob = new_mesh_obj(name, bm, [role], parent, smooth=False)
    n = Vector(normal).normalized()
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = n.to_track_quat('Z', 'Y' if abs(n.z) < 0.9 else 'Y')
    # keep text upright: quad's +Y goes to world `up` projected on the plane
    upv = Vector(up) - n * Vector(up).dot(n)
    if upv.length > 1e-6:
        cur = ob.rotation_quaternion @ Vector((0, 1, 0))
        rot = cur.rotation_difference(upv.normalized())
        ob.rotation_quaternion = rot @ ob.rotation_quaternion
    ob.location = Vector(loc) + n * 0.0004
    ob['decal'] = True
    return ob


# ── transforms / joins ───────────────────────────────────────────────────
def apply_xform(ob):
    activate(ob)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob


def join(objs, name):
    objs = [o for o in objs if o is not None]
    deselect()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def set_origin(ob, point):
    """Move the object origin to a world point without moving geometry."""
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    local = mw.inverted() @ Vector(point)
    ob.data.transform(Matrix.Translation(-local))
    ob.matrix_world = mw @ Matrix.Translation(local)
    return ob


# ── UVs ──────────────────────────────────────────────────────────────────
def uv_tile(ob, name='tile'):
    """UV0: planar projection on each face's dominant axis, in METRES (texture
    density is chosen per role in the module by repeat = tiles per metre)."""
    me = ob.data
    while len(me.uv_layers):                 # 'tile' must be layer 0 (TEXCOORD_0) and the only one so far
        me.uv_layers.remove(me.uv_layers[0])
    bm = bmesh.new()
    bm.from_mesh(me)
    lay = bm.loops.layers.uv.new(name)
    mw = ob.matrix_world
    for f in bm.faces:
        n = (mw.to_3x3() @ f.normal)
        ax = max(range(3), key=lambda i: abs(n[i]))
        pu, pv = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]
        sgn = 1 if n[ax] >= 0 else -1
        for l in f.loops:
            co = mw @ l.vert.co
            u = co[pu] * (sgn if ax != 2 else 1)
            if ax == 1:
                u = -co[pu] * sgn
            l[lay].uv = (u, co[pv])
    bm.to_mesh(me)
    bm.free()
    # make it the FIRST layer
    return ob


def uv_atlas(objs, name='mask', margin=0.004, angle=62):
    """UV1: one shared atlas over all objects (smart project, multi-object)."""
    for o in objs:
        uls = o.data.uv_layers
        if uls.get(name) is None:
            uls.new(name=name)
        uls.active = uls[name]
    deselect()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')


# ── baking ───────────────────────────────────────────────────────────────
def _gpu():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for dt in ('OPTIX', 'CUDA'):
            try:
                prefs.compute_device_type = dt
                prefs.get_devices()
                ok = False
                for d in prefs.devices:
                    d.use = d.type != 'CPU'
                    ok = ok or d.use
                if ok:
                    sc.cycles.device = 'GPU'
                    print('[kit] cycles device', dt)
                    return
            except Exception:
                continue
    except Exception as e:
        print('[kit] gpu setup failed', e)
    sc.cycles.device = 'CPU'


def bake_masks(objs, name, res=2048, samples=64, ao_far=0.30, ao_near=0.04, edge_r=0.012, edge_gain=4.0, ground=True):
    """One EMIT bake of three shader-evaluated masks into OUT/<name>_mask.png (UV1):
        R = AO over `ao_far` metres   (grime, contact darkening)
        G = edge intensity (Bevel-node normal delta, radius `edge_r`) — convex AND concave;
            the module splits them with R/B (convex edges are unoccluded)
        B = AO over `ao_near` metres  (tight crevices, seams)"""
    sc = bpy.context.scene
    _gpu()
    sc.cycles.samples = samples
    gnd = None
    if ground:                               # a temporary floor so bases get contact occlusion
        bmg = bmesh.new()
        bmesh.ops.create_grid(bmg, x_segments=1, y_segments=1, size=6.0)
        meg = bpy.data.meshes.new('_ground'); bmg.to_mesh(meg); bmg.free()
        gnd = bpy.data.objects.new('_ground', meg); link(gnd)
    sc.render.bake.margin = 8
    sc.render.bake.target = 'IMAGE_TEXTURES'
    img = bpy.data.images.new(f'{name}_mask', res, res, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers['mask']
    added, relink = {}, {}
    for o in objs:
        for m in o.data.materials:
            if m is None or m.name in added:
                continue
            nt = m.node_tree
            N = []
            def nn(t):
                x = nt.nodes.new(t); N.append(x); return x
            tex = nn('ShaderNodeTexImage'); tex.image = img
            aof = nn('ShaderNodeAmbientOcclusion'); aof.samples = 24; aof.inputs['Distance'].default_value = ao_far
            aon = nn('ShaderNodeAmbientOcclusion'); aon.samples = 16; aon.inputs['Distance'].default_value = ao_near
            bev = nn('ShaderNodeBevel'); bev.samples = 8; bev.inputs['Radius'].default_value = edge_r
            geo = nn('ShaderNodeNewGeometry')
            dot = nn('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
            inv = nn('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
            amp = nn('ShaderNodeMath'); amp.operation = 'MULTIPLY'; amp.inputs[1].default_value = edge_gain; amp.use_clamp = True
            comb = nn('ShaderNodeCombineColor')
            em = nn('ShaderNodeEmission')
            L = nt.links
            L.new(bev.outputs['Normal'], dot.inputs[0]); L.new(geo.outputs['Normal'], dot.inputs[1])
            L.new(dot.outputs['Value'], inv.inputs[1]); L.new(inv.outputs['Value'], amp.inputs[0])
            L.new(aof.outputs['AO'], comb.inputs[0]); L.new(amp.outputs['Value'], comb.inputs[1]); L.new(aon.outputs['AO'], comb.inputs[2])
            L.new(comb.outputs['Color'], em.inputs['Color'])
            out = [x for x in nt.nodes if x.type == 'OUTPUT_MATERIAL'][0]
            relink[m.name] = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
            L.new(em.outputs['Emission'], out.inputs['Surface'])
            nt.nodes.active = tex
            added[m.name] = N
    # decals / labels / glass must not cast occlusion into the masks
    hidden = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in objs and not o.hide_render
              and (o.get('decal') or o.get('no_ao'))]
    for o in hidden:
        o.hide_render = True
    deselect()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type='EMIT', use_clear=True, margin=8)
    for o in hidden:
        o.hide_render = False
    for mname, N in added.items():
        m = bpy.data.materials[mname]
        nt = m.node_tree
        for x in N:
            nt.nodes.remove(x)
        if relink.get(mname) is not None:
            out = [x for x in nt.nodes if x.type == 'OUTPUT_MATERIAL'][0]
            nt.links.new(relink[mname], out.inputs['Surface'])
    if gnd is not None:
        bpy.data.objects.remove(gnd, do_unlink=True)
    path = os.path.join(OUT, f'{name}_mask.png')
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    print('[kit] masks ->', path)
    return path


# ── export ───────────────────────────────────────────────────────────────
def export_glb(name, objs=None, extras=None):
    path = os.path.join(OUT, f'{name}.glb')
    deselect()
    objs = objs or [o for o in bpy.context.scene.objects if o.type in ('MESH', 'EMPTY')]
    for o in objs:
        o.select_set(True)
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
              export_texcoords=True, export_normals=True, export_materials='EXPORT',
              export_yup=True, export_extras=True)
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        kw.pop('export_materials')
        bpy.ops.export_scene.gltf(**kw)
    if extras:
        with open(os.path.join(OUT, f'{name}_layout.json'), 'w') as f:
            json.dump(extras, f, indent=1)
    print('[kit] glb ->', path)
    return path


def stats():
    tris = 0
    n = 0
    for o in bpy.context.scene.objects:
        if o.type == 'MESH':
            n += 1
            dg = bpy.context.evaluated_depsgraph_get()
            me = o.evaluated_get(dg).to_mesh()
            me.calc_loop_triangles()
            tris += len(me.loop_triangles)
            o.evaluated_get(dg).to_mesh_clear()
    print(f'[kit] {n} mesh objects, {tris} tris')
