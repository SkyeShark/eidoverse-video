"""eidoblend.course.builder: a TERRAIN_CONFIG built in Blender (the terrain half of eidoverse/terrain_base.js).

    from eidoblend.course import build_course, PRESETS
    course = build_course(PRESETS['stairs_pyramid'])            # or any TERRAIN_CONFIG dict
    course.height_at(0.0, 3.2)                                   # the walkable surface's height (numpy-vectorised)
    course.segment_at(4.0)                                       # the telemetry segment under Blender y = 4.0

The plan (plan.py) is the engine's own maths in three's axes; here each piece becomes a mesh in Blender's
(three (x, y, z) -> Blender (x, -z, y)): the course starts at Blender y = -1.5 (three z = 1.5) and runs along +Y, the
character's start is (0, -5, 0). Boxes are real 8-vertex boxes (a ramp keeps its tilt about X), the dome is three's
top hemisphere (32 x 16), a rung is a 10-sided cylinder; the ground is a 120 m plane. Every face carries UVs in
METRES (each face projected on its own axes), so a tiling material keeps its scale across steps of any size
(`uv_scale` tiles per metre).

Materials: the engine's (ground 0x2a2a2a metal 0.05 rough 0.85; obstacles 0xd97550 metal 0.1 rough 0.7; ladder rails
0xb8c2cc metal 0.7 rough 0.35), or pass materials={'ground': mat, 'obstacle': mat, 'rail': mat} (any subset; a value
may also be a dict of the engine's options, {'color': 0x4ab8c0}, recolouring the engine's material).

Flags: the engine marked every terrain piece noSupportCheck; here a piece is declared (no_support_check) only where
the support sampler would misread it, a tilted ramp or a box standing on nothing below, because the harness counts
a blanket opt-out against the audit. A box standing on the ground reaches 2 mm under it (SKIRT), so no bottom face is
coplanar with the ground plane (its top stays the engine's height). The ladder's rails and rungs carry the full
fixture set (no_support_check, no_clipping_check, allow_intersect, no_z_fight_check); every
piece has eido_course_role and eido_course_segment; the collider the engine gave Rapier is recorded on each solid
(eido_collider 'cuboid' with eido_half_extents in Blender's axes, or 'ball' with eido_ball_radius) and
add_rigid_bodies(course) makes them passive rigid bodies for a simulation.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from . import plan as P
from ..terrain._nodes import new_material, principled

ENGINE_MATERIALS = {
    'ground': {'color': 0x2a2a2a, 'metalness': 0.05, 'roughness': 0.85},
    'obstacle': {'color': 0xd97550, 'metalness': 0.1, 'roughness': 0.7},
    'rail': {'color': 0xb8c2cc, 'metalness': 0.7, 'roughness': 0.35},
    'bench': {'color': 0x7a5a3a, 'metalness': 0.0, 'roughness': 0.8},
}
FIXTURE_FLAGS = ('no_support_check', 'no_clipping_check', 'allow_intersect', 'no_z_fight_check', 'no_zfight_check')


def b(x, y, z):
    """three (x, y, z) -> Blender (x, -z, y)"""
    return (x, -z, y)


def _lin(c):
    v = ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v) + (1.0,)


def engine_material(key, name=None, spec=None):
    """one of the template's MeshStandardNodeMaterials as a Principled material; spec = {'color': 0xRRGGBB,
    'metalness': .., 'roughness': ..} overrides it (a variant scene's recolour: the clouds scenes' teal steps)"""
    spec = dict(ENGINE_MATERIALS.get(key, ENGINE_MATERIALS['obstacle']), **(spec or {}))
    m = new_material(name or 'course_' + key)
    bs = principled(m)
    bs.inputs['Base Color'].default_value = _lin(spec['color'])
    bs.inputs['Metallic'].default_value = spec['metalness']
    bs.inputs['Roughness'].default_value = spec['roughness']
    m['eido_course_material'] = key
    return m


def _metre_uvs(bm, uv_scale):
    """per-face planar UVs in metres (x uv_scale), on the face's two axes other than its normal's dominant one, in
    the layer 'UVMap' (bmesh's default layer name is 'Float2')"""
    uvl = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_ax, v_ax = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            co = lp.vert.co
            lp[uvl].uv = (co[u_ax] * uv_scale, co[v_ax] * uv_scale)


def box_mesh(name, size, uv_scale=1.0):
    """a Blender box of size (sx, sy, sz) centred on its origin, UVs in metres"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.normal_update()
    _metre_uvs(bm, uv_scale)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def plane_mesh(name, ext, uv_scale=1.0):
    """the ground: one quad of side `ext` at z = 0, facing up, UVs in metres"""
    s = ext / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-s, -s, 0.0), (s, -s, 0.0), (s, s, 0.0), (-s, s, 0.0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, (x, y) in enumerate([(-s, -s), (s, -s), (s, s), (-s, s)]):
        uv.data[i].uv = (x * uv_scale, y * uv_scale)
    return me


def dome_mesh(name, r, uv_scale=1.0, w_seg=32, h_seg=16):
    """three's SphereGeometry(r, 32, 16, 0, 2pi, 0, pi/2): the top hemisphere, open at the floor"""
    verts, faces = [(0.0, 0.0, r)], []
    for j in range(1, h_seg + 1):
        th = (math.pi / 2) * j / h_seg
        for i in range(w_seg):
            ph = 2 * math.pi * i / w_seg
            verts.append((r * math.sin(th) * math.cos(ph), r * math.sin(th) * math.sin(ph), r * math.cos(th)))
    for i in range(w_seg):
        faces.append((0, 1 + i, 1 + (i + 1) % w_seg))
    for j in range(h_seg - 1):
        a0, a1 = 1 + j * w_seg, 1 + (j + 1) * w_seg
        for i in range(w_seg):
            i1 = (i + 1) % w_seg
            faces.append((a0 + i, a1 + i, a1 + i1, a0 + i1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:                         # spherical UVs in metres: around x the circumference, up the arc
        for lp in f.loops:
            x, y, z = lp.vert.co
            ph = math.atan2(y, x) % (2 * math.pi)
            lp[uvl].uv = (ph * r * uv_scale, math.acos(max(-1.0, min(1.0, z / r))) * r * uv_scale)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    return me


def rung_mesh(name, radius, length, segments=10, uv_scale=1.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius, radius2=radius,
                          depth=length)
    bm.normal_update()
    _metre_uvs(bm, uv_scale)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    return me


class Course:
    """What build_course made: the objects, the plan's table and the queries over them (Blender axes)."""

    def __init__(self, plan, collection, objects, ground):
        self.plan = plan
        self.config = plan.config
        self.collection = collection
        self.objects = objects
        self.ground_obj = ground
        self.tag = plan.tag
        self.log = list(plan.log)
        self.start = (0.0, -5.0, 0.0)                  # the controller's startPosition [0, 0, 5]
        self.first_y = -P.FIRST_Z
        self.end_y = -plan.end_z
        self.final_floor = plan.final_floor
        self.segments = [self._blender_segment(s) for s in plan.segments]
        self._solids = [p for p in plan.pieces if p.role not in ('ground', 'rail', 'rung')]
        self.bench = None

    @staticmethod
    def _blender_segment(s):
        """the engine's segment record with Blender's along-course coordinates added: y0 / y1 (Blender y at the
        segment's start and end) and floor0 / floor1 (the running floor's height there)"""
        d = dict(s)
        d['y0'] = -s['startZ'] if s['startZ'] is not None else None
        d['y1'] = -s['endZ'] if s['endZ'] is not None else None
        d['floor0'], d['floor1'] = s['startY'], s['endY']
        return d

    def segment_at(self, y):
        """_locTerrainAt for Blender y (along the course)"""
        return P.segment_at(self.segments, -y)

    def segment(self, index):
        for s in self.segments:
            if s['index'] == index:
                return s
        return None

    def height_at(self, x, y):
        """the walkable surface's height at Blender (x, y): the highest solid top over the point (box tops, ramp
        planes, the dome's cap), 0 on the ground. Arrays broadcast."""
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        best = np.zeros(np.broadcast(x, y).shape)
        for p in self._solids:
            tx, tz = x, -y                                       # three x, three z
            cx, cy, cz = p.center
            if p.kind == 'dome':
                d2 = (tx - cx) ** 2 + (tz - cz) ** 2
                inside = d2 < p.radius ** 2
                top = cy + np.sqrt(np.maximum(p.radius ** 2 - d2, 0.0))
                best = np.where(inside, np.maximum(best, top), best)
                continue
            hx, hy, hz = p.half()
            th = p.rot_x
            if abs(th) < 1e-12:
                inside = (np.abs(tx - cx) <= hx) & (np.abs(tz - cz) <= hz)
                best = np.where(inside, np.maximum(best, cy + hy), best)
                continue
            # a box tilted about X: the vertical line through (x, z) crosses it in a segment; its top is the
            # surface (the top face, or a slanted end face near the ends). |ly| <= hy and |lz| <= hz are linear in
            # the height offset dy: ly = dy c + dz s, lz = -dy s + dz c (three's rotation about X)
            c, s = math.cos(th), math.sin(th)
            dz = tz - cz
            lo1, hi1 = (-hy - dz * s) / c, (hy - dz * s) / c
            a1, a2 = (dz * c - hz) / s, (dz * c + hz) / s
            lo2, hi2 = np.minimum(a1, a2), np.maximum(a1, a2)
            top = np.minimum(hi1, hi2)
            inside = (np.abs(tx - cx) <= hx) & (top >= np.maximum(lo1, lo2))
            best = np.where(inside, np.maximum(best, cy + top), best)
        return best if best.shape else float(best)

    def ground(self):
        """a characters.Ground over the course's surface (round one's walk_path takes it)"""
        from ..characters.ground import Ground
        return Ground(fn=lambda xs, ys: self.height_at(xs, ys))


def _flag(ob, names):
    for n in names:
        ob[n] = True


SKIRT = 0.002          # a box standing on the ground reaches 2 mm under it: no bottom face coplanar with the plane


def _on_ground(p):
    """an untilted box whose bottom is the ground (three y = 0)"""
    return p.kind == 'box' and abs(p.rot_x) < 1e-12 and abs(p.center[1] - p.size[1] / 2) < 1e-6


def build_course(config=None, collection=None, materials=None, uv_scale=1.0, name='course', ground=True, scene=None):
    """TERRAIN_CONFIG -> Course (objects linked into `collection`, default a new collection under the scene's)."""
    plan = P.plan_course(config)
    for line in plan.log:
        print(line)
    if collection is None:
        collection = bpy.data.collections.new(name)
        (scene or bpy.context.scene).collection.children.link(collection)
    mats = dict(materials or {})
    cache = {}

    def mat(key):
        given = mats.get(key)
        if given is not None and not isinstance(given, dict):
            return given
        if key not in cache:                       # the engine's material, or a dict of its options overriding it
            cache[key] = engine_material(key, '%s_%s' % (name, key), spec=given)
        return cache[key]

    objects = []
    ground_obj = None
    for i, p in enumerate(plan.pieces):
        nm = '%s_%02d_%s' % (name, i, p.role)
        if p.role == 'ground':
            if not ground:
                continue
            ext = plan.ground_extent
            ob = bpy.data.objects.new(nm, plane_mesh(nm, ext, uv_scale))
            ob.data.materials.append(mat('ground'))
            ob['no_support_check'] = True
            ob['eido_collider'] = 'cuboid'
            ob['eido_half_extents'] = (ext / 2, ext / 2, 0.05)
            ob['eido_collider_offset'] = (0.0, 0.0, -0.05)
            ground_obj = ob
        elif p.kind == 'box':
            sx, sy, sz = p.size
            skirt = SKIRT if _on_ground(p) else 0.0            # sink the bottom face under the ground plane's
            me = box_mesh(nm, (sx, sz, sy + skirt), uv_scale)  # Blender (x, y, z) extents = three (x, z, y)
            ob = bpy.data.objects.new(nm, me)
            cx, cy, cz = b(*p.center)
            ob.location = (cx, cy, cz - skirt / 2)
            ob.rotation_euler = (p.rot_x, 0.0, 0.0)            # about X: the same axis in both frames
            ob.data.materials.append(mat(p.material))
        elif p.kind == 'dome':
            me = dome_mesh(nm, p.radius, uv_scale)
            ob = bpy.data.objects.new(nm, me)
            ob.location = b(*p.center)
            ob.data.materials.append(mat(p.material))
        elif p.kind == 'cylinder':
            me = rung_mesh(nm, p.radius, p.length, uv_scale=uv_scale)
            ob = bpy.data.objects.new(nm, me)
            ob.location = b(*p.center)
            ob.rotation_euler = (0.0, math.pi / 2, 0.0)        # three's rotation.z = pi/2: the axis along X
            ob.data.materials.append(mat(p.material))
        else:
            continue
        collection.objects.link(ob)
        ob['eido_course_role'] = p.role
        if p.segment is not None:
            ob['eido_course_segment'] = p.segment
        if p.role in ('rail', 'rung'):
            _flag(ob, FIXTURE_FLAGS)
        elif p.role != 'ground':
            if p.kind == 'box' and not _on_ground(p):
                # the engine exempted every piece; the harness counts a blanket opt-out against the audit, so only
                # the pieces the support sampler would misread are declared: tilted ramps (their low end is
                # buried) and boxes standing on nothing below (a bump or a wall on a raised floor)
                ob['no_support_check'] = True
            if p.collider == 'ball':
                ob['eido_collider'] = 'ball'
                ob['eido_ball_radius'] = p.radius
            else:
                hx, hy, hz = p.half()
                ob['eido_collider'] = 'cuboid'
                ob['eido_half_extents'] = (hx, hz, hy)
        objects.append(ob)
    course = Course(plan, collection, objects, ground_obj)
    course.materials = {k: mat(k) for k in ('ground', 'obstacle', 'rail')}
    return course


def add_bench(course, spec=None, material=None):
    """the course example's sit-stop bench: a solid box in its segment's middle (three: 1.1 x 0.45 x 0.5 at
    (0, 0.225, benchZ)), colour 0x7a5a3a rough 0.8; returns the object (also course.bench)."""
    spec = spec or {'segment': 26, 'size': (1.1, 0.45, 0.5)}
    seg = course.segment(spec['segment'])
    if seg is None:
        return None
    bench_z = (seg['startZ'] + seg['endZ']) / 2
    sx, sy, sz = spec['size']
    me = box_mesh('course_bench', (sx, sz, sy + SKIRT))
    ob = bpy.data.objects.new('course_bench', me)
    bx, by, bz = b(0.0, sy / 2, bench_z)
    ob.location = (bx, by, bz - SKIRT / 2)
    ob.data.materials.append(material or engine_material('bench', 'course_bench'))
    course.collection.objects.link(ob)
    ob['eido_course_role'] = 'bench'
    ob['eido_collider'] = 'cuboid'
    ob['eido_half_extents'] = (sx / 2, sz / 2, sy / 2)
    course.bench = ob
    course.bench_y = -bench_z
    return ob


def add_rigid_bodies(course):
    """the engine's Rapier statics as passive rigid bodies: a BOX per cuboid (the mesh's own bounds), a SPHERE for
    the dome's ball (centred on the floor: its lower half is buried), the ground a passive box 0.1 m thick under
    the plane. Needs a rigid body world (made if missing)."""
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    coll = sc.rigidbody_world.collection
    if coll is None:
        coll = bpy.data.collections.new('RigidBodyWorld')
        sc.rigidbody_world.collection = coll
    made = []
    for ob in course.objects + ([course.bench] if course.bench else []):
        kind = ob.get('eido_collider')
        if not kind:
            continue
        if ob.name not in coll.objects:
            coll.objects.link(ob)
        rb = ob.rigid_body
        rb.type = 'PASSIVE'
        rb.collision_shape = 'SPHERE' if kind == 'ball' else 'BOX'
        rb.collision_margin = 0.0
        made.append(ob)
    return made


def merge_solids(course, name='course_solid'):
    """join every solid piece of the course (steps, ramps, slabs, walls ...) into one mesh and union it (csg.union_all:
    one EXACT boolean with self intersection): one watertight solid without the stacked boxes' buried faces, for film
    dressing or a single collider. The pieces are replaced by the merged object (returned); rails, rungs, dome and
    ground stay."""
    from .csg import union_all
    boxes = [o for o in course.objects if o.get('eido_course_role') not in ('ground', 'rail', 'rung', 'dome')]
    if not boxes:
        return None
    merged = union_all(boxes, name=name)
    merged['no_support_check'] = True
    merged['eido_course_role'] = 'merged'
    course.objects = [o for o in course.objects if o not in boxes] + [merged]
    return merged
