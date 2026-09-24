# fx_core.py — shared Blender helpers for the DAISY funeral set's hero assets.
#
# Everything is authored in THREE.JS SPACE (x right, y UP, z toward the camera)
# and rotated into Blender space (z up) once, when a mesh is finalized, so the
# numbers here match the engine's set-local numbers one-to-one. The glTF
# exporter rotates Blender back to +Y-up on export.
#
# Law of the house (feedback_kit_craft_standards): face-modelled masses,
# bevelled edges, UVs authored in METRES (planar on the dominant axis for
# architecture, along-the-member for timber/steel), material slots named by
# ROLE so the engine binds real PBR sets (AmbientCG) + layered wear to them.
import bpy
import bmesh
import math
import os
import json
from mathutils import Vector, Matrix

def _repo_root():                 # library copy: this was a local absolute path; now the folder holding eido.py
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d) and not os.path.exists(os.path.join(d, "eido.py")):
        d = os.path.dirname(d)
    return d
ROOT = os.environ.get("EIDOVERSE_ROOT") or _repo_root()
ASSETS = ROOT + "/work/daisy/sets/assets"
T2B = Matrix.Rotation(math.radians(90.0), 4, 'X')      # three (x,y,z) -> blender (x,-z,y)

# preview colours per role (the engine replaces these with PBR NodeMaterials)
ROLE_PREVIEW = {
    'brick': (0.36, 0.16, 0.11, 0.85, 0.0), 'concrete': (0.42, 0.41, 0.39, 0.8, 0.0),
    'timber': (0.33, 0.24, 0.16, 0.8, 0.0), 'steel': (0.10, 0.10, 0.11, 0.55, 0.8),
    'glass': (0.05, 0.07, 0.09, 0.1, 0.0), 'planks': (0.30, 0.22, 0.15, 0.85, 0.0),
    'corrugated': (0.45, 0.46, 0.47, 0.5, 0.7), 'enamel': (0.12, 0.22, 0.17, 0.35, 0.0),
    'enamel_in': (0.9, 0.9, 0.86, 0.3, 0.0), 'screen': (0.8, 0.8, 0.8, 0.9, 0.0),
    'stage': (0.03, 0.03, 0.03, 0.7, 0.0), 'galv': (0.55, 0.56, 0.57, 0.45, 0.9),
    'cord': (0.02, 0.02, 0.02, 0.6, 0.0), 'orange': (0.52, 0.11, 0.06, 0.6, 0.1),
    'gold': (0.9, 0.7, 0.3, 0.3, 1.0), 'fiberglass': (0.85, 0.83, 0.8, 0.35, 0.0),
    'lace': (0.92, 0.9, 0.85, 0.7, 0.0), 'wax': (0.9, 0.86, 0.75, 0.5, 0.0),
    'black_gloss': (0.02, 0.02, 0.02, 0.25, 0.0), 'fabric': (0.1, 0.1, 0.11, 0.9, 0.0),
    'skin_dark': (0.05, 0.05, 0.06, 0.8, 0.0), 'asphalt': (0.12, 0.12, 0.12, 0.9, 0.0),
    'lamp_glass': (1.0, 0.7, 0.3, 0.2, 0.0), 'exit': (0.8, 0.1, 0.1, 0.4, 0.0),
    'porcelain': (0.95, 0.94, 0.92, 0.2, 0.0), 'feather': (0.95, 0.95, 0.95, 0.8, 0.0),
    'petal': (0.9, 0.9, 0.85, 0.7, 0.0), 'stem': (0.15, 0.3, 0.1, 0.7, 0.0),
    'net': (0.9, 0.9, 0.92, 0.6, 0.0), 'bottle': (0.8, 0.8, 0.75, 0.1, 0.0),
    'rope': (0.5, 0.12, 0.07, 0.7, 0.2), 'brass': (0.7, 0.5, 0.25, 0.35, 1.0),
    'tentacle': (0.06, 0.09, 0.07, 0.35, 0.0), 'rubber': (0.03, 0.03, 0.03, 0.85, 0.0),
}


def reset_scene():
    """clear the startup scene WITHOUT factory settings: read_factory_settings /
    --factory-startup reset the preferences, which makes Blender's extension manager
    strip the user's extension wheels (seen 2026-09-23). Just delete the data."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.images,
                 bpy.data.curves):
        for d in list(coll):
            try:
                coll.remove(d)
            except Exception:
                pass


def material(role):
    m = bpy.data.materials.get(role)
    if m:
        return m
    m = bpy.data.materials.new(role)
    r, g, b, rough, metal = ROLE_PREVIEW.get(role, (0.5, 0.5, 0.5, 0.6, 0.0))
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    return m


# ───────────────────────────── mesh building ──────────────────────────────
class Mesh:
    """Accumulates geometry in three.js space with per-face roles and
    per-loop UVs (metres). finalize() makes a Blender object."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.roles = []            # material role list, index = material_index

    def ridx(self, role):
        if role not in self.roles:
            self.roles.append(role)
        return self.roles.index(role)

    # --- primitive: a quad/poly face from points, with a uv function
    def face(self, pts, role, uvf=None):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.ridx(role)
        self._uv_face(f, uvf)
        return f

    def _uv_face(self, f, uvf=None):
        if uvf is None:
            n = f.normal if f.normal.length > 0 else Vector((0, 1, 0))
            if f.normal.length == 0:
                f.normal_update()
                n = f.normal
            uvf = planar_uv(n)
        for l in f.loops:
            l[self.uv].uv = uvf(l.vert.co)

    def box(self, c, s, role, uv='planar', bevel_tag=True):
        """axis-aligned box: centre c, size s (three space)."""
        cx, cy, cz = c
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        P = [(cx + x * hx, cy + y * hy, cz + z * hz) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        idx = lambda x, y, z: ((x > 0) * 4 + (y > 0) * 2 + (z > 0))
        quads = [
            ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)),      # +x
            ((-1, -1, 1), (-1, 1, 1), (-1, 1, -1), (-1, -1, -1)),  # -x
            ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)),      # +y
            ((-1, -1, 1), (-1, -1, -1), (1, -1, -1), (1, -1, 1)),  # -y
            ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),      # +z
            ((1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)),  # -z
        ]
        vs = [self.bm.verts.new(Vector(p)) for p in P]
        fs = []
        for q in quads:
            f = self.bm.faces.new([vs[idx(*k)] for k in q])
            f.material_index = self.ridx(role)
            f.normal_update()
            fs.append(f)
        for f in fs:
            self._uv_face(f)
        return fs

    def beam(self, p0, p1, w, h, role, up=(0, 1, 0), caps=True, twist=0.0):
        """oriented box from p0 to p1; w = width (side), h = depth (along up).
        UVs run ALONG the member (u = metres along, v = metres around), so
        wood grain / mill scale follow the member like the real thing."""
        a, b = Vector(p0), Vector(p1)
        d = b - a
        L = d.length
        if L < 1e-6:
            return []
        t = d.normalized()
        upv = Vector(up)
        if abs(t.dot(upv.normalized())) > 0.98:
            upv = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 0, 1))
        s = t.cross(upv).normalized()         # side
        n = s.cross(t).normalized()           # 'up' of the section
        if twist:
            q = Matrix.Rotation(twist, 3, t)
            s, n = q @ s, q @ n
        hw, hh = w / 2, h / 2
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        ring0 = [self.bm.verts.new(a + s * x + n * y) for x, y in corners]
        ring1 = [self.bm.verts.new(b + s * x + n * y) for x, y in corners]
        fs = []
        perim = [0.0]
        for i in range(4):
            x0, y0 = corners[i]
            x1, y1 = corners[(i + 1) % 4]
            perim.append(perim[-1] + math.hypot(x1 - x0, y1 - y0))
        for i in range(4):
            j = (i + 1) % 4
            f = self.bm.faces.new([ring0[i], ring1[i], ring1[j], ring0[j]])
            f.material_index = self.ridx(role)
            uvs = [(0.0, perim[i]), (L, perim[i]), (L, perim[i + 1]), (0.0, perim[i + 1])]
            for l, q in zip(f.loops, uvs):
                l[self.uv].uv = q
            fs.append(f)
        if caps:
            f0 = self.bm.faces.new(list(ring0))
            f1 = self.bm.faces.new(list(reversed(ring1)))
            for f in (f0, f1):
                f.material_index = self.ridx(role)
                f.normal_update()
                for l in f.loops:
                    lo = l.vert.co - (a if f is f0 else b)
                    l[self.uv].uv = (lo.dot(s) + 0.5, lo.dot(n) + 0.5)
            fs += [f0, f1]
        return fs

    def lathe(self, prof, segs, c, role, a0=0.0, a1=2 * math.pi, cap_top=False, cap_bot=False, uvscale=1.0):
        """prof: [(r, y)] bottom->top; revolves about the +y axis at c."""
        cx, cy, cz = c
        closed = abs((a1 - a0) - 2 * math.pi) < 1e-6
        n = segs if closed else segs + 1
        rings = []
        for r, y in prof:
            ring = []
            for i in range(n):
                a = a0 + (a1 - a0) * i / segs
                ring.append(self.bm.verts.new((cx + r * math.cos(a), cy + y, cz + r * math.sin(a))))
            rings.append(ring)
        # arc length along profile for v
        vacc = [0.0]
        for k in range(1, len(prof)):
            vacc.append(vacc[-1] + math.hypot(prof[k][0] - prof[k - 1][0], prof[k][1] - prof[k - 1][1]))
        rmax = max(p[0] for p in prof) or 1.0
        fs = []
        for k in range(len(prof) - 1):
            for i in range(segs):
                j = (i + 1) % n if closed else i + 1
                f = self.bm.faces.new([rings[k][i], rings[k + 1][i], rings[k + 1][j], rings[k][j]])
                f.material_index = self.ridx(role)
                uu = lambda ii: (a0 + (a1 - a0) * ii / segs) * rmax * uvscale
                uvs = [(uu(i), vacc[k] * uvscale), (uu(i), vacc[k + 1] * uvscale),
                       (uu(i + 1), vacc[k + 1] * uvscale), (uu(i + 1), vacc[k] * uvscale)]
                for l, q in zip(f.loops, uvs):
                    l[self.uv].uv = q
                fs.append(f)
        if cap_top and closed and prof[-1][0] > 1e-5:
            f = self.bm.faces.new(list(rings[-1]))
            f.material_index = self.ridx(role)
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
            self._uv_face(f)
        if cap_bot and closed and prof[0][0] > 1e-5:
            f = self.bm.faces.new(list(reversed(rings[0])))
            f.material_index = self.ridx(role)
            f.normal_update()
            if f.normal.y > 0:
                f.normal_flip()
            self._uv_face(f)
        return fs

    def tube(self, pts, radius, segs, role, caps=False, radii=None):
        """a tube along a polyline (parallel-transport frames)."""
        P = [Vector(p) for p in pts]
        if len(P) < 2:
            return []
        T = []
        for i in range(len(P)):
            if i == 0:
                t = P[1] - P[0]
            elif i == len(P) - 1:
                t = P[-1] - P[-2]
            else:
                t = (P[i + 1] - P[i - 1])
            T.append(t.normalized())
        ref = Vector((0, 1, 0)) if abs(T[0].y) < 0.9 else Vector((1, 0, 0))
        N = T[0].cross(ref).normalized()
        rings = []
        acc = 0.0
        vs_along = []
        for i in range(len(P)):
            if i > 0:
                acc += (P[i] - P[i - 1]).length
                # parallel transport
                axis = T[i - 1].cross(T[i])
                if axis.length > 1e-8:
                    ang = T[i - 1].angle(T[i])
                    N = Matrix.Rotation(ang, 3, axis.normalized()) @ N
            B = T[i].cross(N).normalized()
            r = radii[i] if radii else radius
            ring = [self.bm.verts.new(P[i] + (N * math.cos(2 * math.pi * k / segs) + B * math.sin(2 * math.pi * k / segs)) * r)
                    for k in range(segs)]
            rings.append(ring)
            vs_along.append(acc)
        fs = []
        circ = 2 * math.pi * radius
        for i in range(len(P) - 1):
            for k in range(segs):
                kk = (k + 1) % segs
                f = self.bm.faces.new([rings[i][k], rings[i][kk], rings[i + 1][kk], rings[i + 1][k]])
                f.material_index = self.ridx(role)
                uvs = [(vs_along[i], circ * k / segs), (vs_along[i], circ * (k + 1) / segs),
                       (vs_along[i + 1], circ * (k + 1) / segs), (vs_along[i + 1], circ * k / segs)]
                for l, q in zip(f.loops, uvs):
                    l[self.uv].uv = q
                fs.append(f)
        if caps:
            for ring, flip in ((rings[0], True), (rings[-1], False)):
                f = self.bm.faces.new(list(reversed(ring)) if flip else ring)
                f.material_index = self.ridx(role)
                f.normal_update()
                self._uv_face(f)
        return fs

    def extrude_profile(self, prof2d, z0, z1, role, axis='z'):
        """closed 2D profile (list of (a,b)) extruded between z0..z1 along axis.
        axis='z': profile in (x,y); 'x': profile in (z,y)."""
        def P(a, b, z):
            if axis == 'z':
                return (a, b, z)
            if axis == 'x':
                return (z, b, a)
            return (a, z, b)
        n = len(prof2d)
        r0 = [self.bm.verts.new(P(a, b, z0)) for a, b in prof2d]
        r1 = [self.bm.verts.new(P(a, b, z1)) for a, b in prof2d]
        fs = []
        for i in range(n):
            j = (i + 1) % n
            f = self.bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
            f.material_index = self.ridx(role)
            f.normal_update()
            fs.append(f)
        fa = self.bm.faces.new(list(reversed(r0)))
        fb = self.bm.faces.new(r1)
        for f in (fa, fb):
            f.material_index = self.ridx(role)
            f.normal_update()
        fs += [fa, fb]
        if axis != 'z':
            bmesh.ops.reverse_faces(self.bm, faces=fs)
        for f in fs:
            f.normal_update()
            self._uv_face(f)
        return fs

    def finalize(self, bevel=0.0, bevel_segs=2, bevel_angle=35, weighted=True, smooth_angle=40,
                 collection=None, merge_dist=1e-5):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
        bm.normal_update()
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        me.transform(T2B)
        for r in self.roles:
            me.materials.append(material(r))
        ob = bpy.data.objects.new(self.name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        for p in me.polygons:
            p.use_smooth = True
        if bevel > 0:
            m = ob.modifiers.new('bevel', 'BEVEL')
            m.width = bevel
            m.segments = bevel_segs
            m.limit_method = 'ANGLE'
            m.angle_limit = math.radians(bevel_angle)
            m.harden_normals = False
            m.miter_outer = 'MITER_ARC'
            m.use_clamp_overlap = True
        if weighted:
            m = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
            m.keep_sharp = True
            m.weight = 50
        # smooth by angle so flat faces stay flat and rounds stay round
        try:
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
                bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle), keep_sharp_edges=True)
        except Exception as e:
            print('[fx] smooth_by_angle failed', e)
        return ob


def planar_uv(n):
    """metres, on the face's dominant axis; u horizontal, v up for walls."""
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 1:          # floor / ceiling: (x, z)
        s = 1 if n[1] >= 0 else -1
        return lambda co: (co.x, -co.z * s)
    if ax == 0:          # faces +/-x: (z, y)
        s = 1 if n[0] >= 0 else -1
        return lambda co: (-co.z * s, co.y)
    s = 1 if n[2] >= 0 else -1   # faces +/-z: (x, y)
    return lambda co: (co.x * s, co.y)


def apply_modifiers(ob):
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        for m in list(ob.modifiers):
            try:
                bpy.ops.object.modifier_apply(modifier=m.name)
            except Exception as e:
                print('[fx] modifier_apply failed', m.name, e)


def boolean(ob, cutters, op='DIFFERENCE', solver='EXACT', apply=True):
    for c in cutters:
        m = ob.modifiers.new('bool', 'BOOLEAN')
        m.operation = op
        m.solver = solver
        m.object = c
        if apply:
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
                bpy.ops.object.modifier_apply(modifier=m.name)
    return ob


def reuv_planar(ob, only_role=None):
    """re-author planar metre UVs on (all | one role's) faces of an object in
    blender space (after booleans created new faces). Blender->three: (x,z,-y)."""
    me = ob.data
    uvl = me.uv_layers.active or me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        if only_role is not None and me.materials[p.material_index].name != only_role:
            continue
        nB = p.normal
        n3 = Vector((nB.x, nB.z, -nB.y))
        f = planar_uv(n3)
        for li in p.loop_indices:
            cB = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = f(Vector((cB.x, cB.z, -cB.y)))


def empty(name, pos3, collection=None, size=0.2, props=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    x, y, z = pos3
    e.location = (x, -z, y)
    if props:
        for k, v in props.items():
            e[k] = v
    (collection or bpy.context.scene.collection).objects.link(e)
    return e


def export_glb(path, objects=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if objects is not None:
        for o in bpy.data.objects:
            o.select_set(False)
        for o in objects:
            o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB', use_selection=objects is not None,
        export_apply=True, export_yup=True, export_extras=True,
        export_texcoords=True, export_normals=True, export_materials='EXPORT',
        export_image_format='AUTO', export_animations=False, export_cameras=False, export_lights=False,
    )
    print('[fx] exported', path, os.path.getsize(path) // 1024, 'KB')


def preview(path, cams, res=(960, 540), engine='workbench', world=(0.05, 0.05, 0.06), light_dir=None):
    """quick shape-check renders: cams = [(pos3, target3, fov_deg), ...] (three space)."""
    sc = bpy.context.scene
    if engine == 'workbench':
        sc.render.engine = 'BLENDER_WORKBENCH'
        sh = sc.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'MATERIAL'
        sh.show_cavity = True
        sh.cavity_type = 'BOTH'
        sh.show_shadows = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new('w')
    sc.world.color = world
    cam_data = bpy.data.cameras.new('pcam')
    cam = bpy.data.objects.new('pcam', cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    outs = []
    for i, (p, t, fov) in enumerate(cams):
        P = Vector((p[0], -p[2], p[1]))
        T = Vector((t[0], -t[2], t[1]))
        cam.location = P
        cam.rotation_euler = (T - P).to_track_quat('-Z', 'Y').to_euler()
        cam_data.sensor_fit = 'VERTICAL'
        cam_data.angle_y = math.radians(fov)
        cam_data.clip_start = 0.05
        cam_data.clip_end = 2000
        out = path.replace('.png', f'_{i}.png')
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)
        outs.append(out)
    bpy.data.objects.remove(cam)
    return outs


# ───────────────────────────── organic masses (three space) ─────────────────────────────
def link_obj(name, me, collection=None):
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def skin_chain(name, verts, edges, radii, subsurf=2, root=0):
    """a skin-modifier mass from a skeleton (three space) -> applied mesh object."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(T2B @ Vector(v)) for v in verts], edges, [])
    ob = link_obj(name, me)
    sk = ob.modifiers.new('skin', 'SKIN')
    sk.use_smooth_shade = True
    sk.branch_smoothing = 0.8
    for i, r in enumerate(radii):
        me.skin_vertices[0].data[i].radius = r
    me.skin_vertices[0].data[root].use_root = True
    if subsurf:
        ss = ob.modifiers.new('sub', 'SUBSURF')
        ss.levels = subsurf
    apply_modifiers(ob)
    return ob


def ellipsoid_obj(name, c, r, segs=24, rings=16, cut_below=None, cut_above=None, solid=0.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * r[0], v.co.z * r[1], v.co.y * r[2]))
    kill = [v for v in bm.verts if (cut_below is not None and v.co.y < cut_below) or (cut_above is not None and v.co.y > cut_above)]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(T2B)
    ob = link_obj(name, me)
    if solid:
        s = ob.modifiers.new('sol', 'SOLIDIFY')
        s.thickness = solid
        apply_modifiers(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def mesh_obj(m, **kw):
    """finalize a fx_core.Mesh without modifiers (for joins)."""
    return m.finalize(weighted=False, **kw)


def join(objs, name, role=None):
    for o in bpy.data.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    if role:
        ob.data.materials.clear()
        ob.data.materials.append(material(role))
        for p in ob.data.polygons:
            p.material_index = 0
    return ob


def set_role(ob, role):
    ob.data.materials.clear()
    ob.data.materials.append(material(role))
    for p in ob.data.polygons:
        p.material_index = 0
    return ob


def smart_uv(ob, angle=66, margin=0.02):
    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name='UVMap')
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], edit_object=ob):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')


def place(ob, pos3=(0, 0, 0), yaw=0.0, scale=1.0):
    """bake a three-space transform into the mesh (yaw about three +y)."""
    M = Matrix.Translation(T2B @ Vector(pos3)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Scale(scale, 4)
    ob.data.transform(M)
    return ob


def hard_exit():
    import sys as _s
    _s.stdout.flush()
    os._exit(0)
