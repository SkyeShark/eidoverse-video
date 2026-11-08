"""eidoblend.characters.robotics.kit: index.js, the modular kit's loader, in Blender (tools-guides/robotics.md).

    from eidoblend.characters.robotics import make_robot, load_part, catalog
    arm = make_robot('arm', position=(0, 0, 0), color='#d9e0df', accent='#398b91')
    claw = make_robot('gripper')
    arm.attach(claw, port='a650_j6/output', child_port='parallel_gripper/input')
    arm.joints([0, 0.5, 0.4, 0, -0.9, 0]); claw.jaw_gap(0.03)
    arm.play('joints')                                   # the sample keyed over the scene's frames (motion.py)

The kit (eidoverse/assets/robotics/: catalog.json, 85 GLBs, shared textures, metadata/ and provenance/) was authored in
Blender, +Z up, and exported to glTF. Blender's glTF importer brings every node back in its authoring frame, so every
number the catalog and the metadata give in "source +Z-up coordinates" (joint axes, port frames, nominal matrices, gait
rest matrices, track paths) is used AS IT IS: the WebGPU edition converts each to three's +Y up (vector(), the C
matrices); this edition must not convert them again. Metres and radians, as there.

    catalog()                       catalog.json (models, aliases, textures, port_frames)
    make_robot(id | alias, **opts) / load_robot     -> Robot (index.js loadRobot / makeRobot). Options, as there:
        position (Blender axes; location is the same), rotation (Euler XYZ radians, Blender axes), scale (uniform,
        positive), color / primary, accent, filament, textures (False: geometry-only), subassembly ({'root',
        'keepModule'}), model (makeBot's), scene (the bpy scene the robot's collection joins; default the context's).
        Blender's own: collection, name. Any other option raises, as the WebGPU loader does.
    load_part(model_id, part, **opts)   one part's own triangles (provenance/ ownership) on the donor's hierarchy and
                                    origin, every other donor mesh hidden; an unknown part raises and leaves nothing behind
    frame_matrix(point, normal, tangent)   index.js frameMatrix in authoring (= Blender) terms
    vector(p) / to_authoring(p)     index.js's axis conversions: identities here (Blender's frame IS the authoring frame)
    INSTALLERS                      functions(robot, register_part) run at the end of every load, as index.js runs
                                    installFilament: the fabrication port (filament.js) registers its own there

    Robot   group / root / model (the 'robot|<id>' empty: place the robot there), collection, id, entry, report, gltf,
            roots / specs (module objects and their joint specs: the node's extras over the family metadata's root
            properties), ports / port(name) (mounts: X the tangent, Z the outward mating normal, local to the owner),
            attach(child, port, child_port, twist), connections / connection, set_joints(values, clamp), state, rest,
            reset(), parts() / part(name), stats(), set_colors(primary, accent), materials (RobotMaterials), dispose(),
            key_joints(frame) / key_pose(frame), part_faces(obj) (the part name of each face); the motion API is
            motion.py's (MotionMixin)
"""

from __future__ import annotations

import json
import math
import os
import re

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from . import io as kio
from . import materials as kmat
from ._mesh import submesh
from .motion import MotionMixin

ROOT = kio.ROOT
LOADER_OPTIONS = ('model', 'scene', 'position', 'rotation', 'scale', 'color', 'primary', 'accent', 'filament',
                  'textures', 'subassembly')
BLENDER_OPTIONS = ('location', 'collection', 'name')
INSTALLERS = []
_OWN_KEYS = {'gltf_node', 'part_faces', 'robot_id', 'eidoverseRobotics', '_loadedAsset'}


def catalog() -> dict:
    """catalog.json: {'models', 'aliases', 'textures', 'port_frames', ...} (await RoboticsKit.catalog())"""
    return kio.json_file('catalog.json')


def vector(p):
    """index.js vector(): source +Z-up -> the public frame. In Blender the public frame IS the source frame."""
    return Vector((float(p[0]), float(p[1]), float(p[2])))


def to_authoring(p):
    """index.js toAuthoring(): the public frame -> source +Z-up; an identity here"""
    return (float(p[0]), float(p[1]), float(p[2]))


def _finite3(v):
    try:
        return len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v)
    except TypeError:
        return False


def frame_matrix(point, normal, tangent=None):
    """a mount frame: Z the outward normal, X the tangent (or a reference axis made orthogonal), at point"""
    if not _finite3(point) or not _finite3(normal) or math.hypot(*normal) < 1e-10:
        raise ValueError('Mount frame needs an explicit finite position and nonzero outward normal; check the catalog '
                         'port metadata.')
    if tangent is not None and not _finite3(tangent):
        raise ValueError('Mount tangent must be three finite numbers')
    z = Vector(normal).normalized()
    x = Vector(tangent) if tangent is not None else (Vector((1, 0, 0)) if abs(z.x) < 0.9 else Vector((0, 1, 0)))
    x = x - z * x.dot(z)
    if x.length_squared < 1e-20:
        raise ValueError('Mount tangent must not be parallel to its normal')
    x.normalize()
    y = z.cross(x)
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2] = x[i], y[i], z[i]
    m.translation = Vector(point)
    return m


def _plain(v):
    if hasattr(v, 'to_dict'):
        return v.to_dict()
    if hasattr(v, 'to_list'):
        return v.to_list()
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    try:
        return [_plain(x) for x in v]
    except TypeError:
        return v


def _nz(*vals):
    """JavaScript's a ?? b ?? c"""
    for v in vals:
        if v is not None:
            return v
    return None


def decompose_three(m):
    """three's Matrix4.decompose: a negative determinant flips the X scale only (Blender's flips all three); joint
    turns compose as T * (R * turn) * S on THIS split, so mirrored modules turn exactly as in the WebGPU edition"""
    loc = m.to_translation()
    cols = [Vector((m[0][i], m[1][i], m[2][i])) for i in range(3)]
    s = [c.length for c in cols]
    if m.to_3x3().determinant() < 0:
        s[0] = -s[0]
    r = Matrix([[m[i][j] / s[j] for j in range(3)] for i in range(3)])
    return loc, r.to_quaternion(), Vector(s)


def gltf_local(node):
    """a glTF node's local transform as the Blender importer builds it: (x, y, z) -> (x, -z, y)"""
    if 'matrix' in node:
        e = node['matrix']
        M = Matrix([[e[0], e[4], e[8], e[12]], [e[1], e[5], e[9], e[13]], [e[2], e[6], e[10], e[14]], [0, 0, 0, 1]])
        C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
        return C @ M @ C.inverted()
    t = node.get('translation', (0, 0, 0))
    r = node.get('rotation', (0, 0, 0, 1))
    s = node.get('scale', (1, 1, 1))
    return Matrix.LocRotScale(Vector((t[0], -t[2], t[1])), Quaternion((r[3], r[0], -r[2], r[1])),
                              Vector((s[0], s[2], s[1])))


def _dfs(gltf):
    nodes = gltf['nodes']
    sc = gltf['scenes'][gltf.get('scene', 0)]
    order, parent = [], {}
    stack = [(i, None) for i in reversed(sc['nodes'])]
    while stack:
        i, p = stack.pop()
        order.append(i)
        parent[i] = p
        for c in reversed(nodes[i].get('children', [])):
            stack.append((c, i))
    return order, parent


def _map_nodes(gltf, new):
    """{glTF node index: the object the importer made of it}: by name (a '.001' suffix allowed), under the mapped
    parent, and by the node's own transform when two siblings share a name"""
    order, parent = _dfs(gltf)
    by_name = {}
    for o in new:
        by_name.setdefault(o.name, []).append(o)
        m = re.match(r'^(.*)\.\d{3,}$', o.name)
        if m:
            by_name.setdefault(m.group(1), []).append(o)
    out, taken = {}, set()
    for i in order:
        n = gltf['nodes'][i]
        name = n.get('name', '')
        want = out.get(parent[i])
        cands = [o for o in by_name.get(name, []) if o.name not in taken and o.parent == want]
        if not cands:
            raise RuntimeError(f'glTF node {i} {name!r}: the importer made no object for it')
        if len(cands) > 1:
            ref = gltf_local(n)
            cands.sort(key=lambda o: (sum(abs(a - b) for ra, rb in zip(o.matrix_basis, ref) for a, b in zip(ra, rb)),
                                      o.name != name))
        out[i] = cands[0]
        taken.add(cands[0].name)
    return out, order


def _subtree(o):
    out = [o]
    for c in o.children:
        out.extend(_subtree(c))
    return out


class Robot(MotionMixin):
    """a loaded catalog model: index.js's robot record, its objects in Blender"""

    def __init__(self):
        self.disposed = False
        self.connections, self.connection = [], None
        self.state, self.pose_callbacks = {}, []
        self.default_joints = None
        self.filament = None
        self.grasp_references = []
        self.extra_objects = []                  # made after loading: track shoes, grasp references, filament parts

    # ------------------------------------------------------------------------------------------------ ports
    def _install_ports(self):
        ports = {}

        def add(name, owner, s):
            if owner is None or not s.get('interface'):
                return
            p = _nz(s.get('position_m'), s.get('position'))
            try:
                ports[name] = dict(s, name=name, owner=owner, matrix=frame_matrix(p, s.get('normal'), s.get('tangent')))
            except ValueError as e:
                raise ValueError(f'Invalid mount {name}: {e}') from None
        for n, o in self.roots.items():
            s = self.specs[n]
            mid = s.get('module_id')
            shared = self.port_frames.get(mid) or (self.port_frames.get(mid.split(' / ')[-1]) if mid else None) or {}
            if s.get('ports_json'):
                for p, d in json.loads(s['ports_json']).items():
                    add(n + '/' + p, o, d)
            if s.get('interface') and (s.get('output_frame') or shared.get('output')):
                out = shared.get('output') or {}
                add(n + '/output', o, {'interface': s['interface'],
                                       'position_m': _nz(s.get('output_frame'), out.get('position_m')),
                                       'normal': _nz(s.get('output_normal'), out.get('normal')),
                                       'tangent': _nz(s.get('output_tangent'), out.get('tangent'))})
            if s.get('interface') and (s.get('attachment_position') or s.get('input_frame') or s.get('mount_pattern_m')
                                       or shared.get('input')):
                inp = shared.get('input') or {}
                add(n + '/input', o, {'interface': s['interface'],
                                      'position_m': _nz(s.get('attachment_position'), s.get('input_frame'),
                                                        inp.get('position_m')),
                                      'normal': _nz(s.get('attachment_normal'), inp.get('normal')),
                                      'tangent': _nz(s.get('attachment_tangent'), inp.get('tangent'))})
        top = [n for n, o in self.roots.items() if not (o.parent is not None and o.parent.get('module_id'))]
        for n, s in ((self.report.get('mobile') or {}).get('ports') or {}).items():
            add(n, self.roots.get(s.get('owner')) or (self.roots[top[0]] if top else None), s)
        owners = set(o.name for o in self.roots.values())
        for p in self.derived_ports:
            if p['owner'].name in owners:
                ports[p['name']] = p
        self.ports = ports

    def port(self, name):
        if name not in self.ports:
            raise KeyError(f'Unknown port {name}; available: {", ".join(self.ports)}')
        return self.ports[name]

    def _ancestors(self):
        out, o = set(), self.group
        while o is not None:
            out.add(o.name)
            o = o.parent
        return out

    def attach(self, child, port, child_port, twist=0.0):
        """parent the child robot to this robot's port owner so the two mating frames meet with opposed normals:
        port * Rz(twist) * Rx(pi) * child_frame^-1 (index.js attach; RoboticsKit.connect)"""
        if not isinstance(twist, (int, float)) or not math.isfinite(twist):
            raise ValueError('Attachment twist must be finite radians')
        if child is self or child.group.name in self._ancestors():
            raise ValueError('Attachment would create a scene-graph cycle')
        a, b = self.port(port), child.port(child_port)
        for p in (a, b):
            m = p.get('matrix')
            if (not isinstance(m, Matrix) or not all(math.isfinite(v) for r in m for v in r)
                    or abs(m.determinant()) < 1e-10):
                raise ValueError(f"Invalid mount matrix {p['name']}")
        if a['interface'] != b['interface']:
            raise ValueError(f"Mount mismatch: {a['interface']} / {b['interface']}. Use the matching adapter.")
        bpy.context.view_layer.update()
        child_frame = child.group.matrix_world.inverted() @ b['owner'].matrix_world @ b['matrix']
        mate = a['matrix'] @ Matrix.Rotation(twist, 4, 'Z') @ Matrix.Rotation(math.pi, 4, 'X') @ child_frame.inverted()
        child.group.parent = a['owner']
        child.group.matrix_parent_inverse = Matrix.Identity(4)
        child.group.matrix_basis = mate
        if child.connection:
            old = child.connection['parent']
            old.connections = [c for c in old.connections if c is not child]
        self.connections.append(child)
        child.connection = {'parent': self, 'port': port, 'child_port': child_port, 'twist': twist}
        bpy.context.view_layer.update()
        return child

    # ------------------------------------------------------------------------------------------------ joints
    def set_joints(self, values, clamp=False):
        """revolute / continuous: a turn about the joint's axis from its rest (radians); prismatic: travel along it
        (metres). The whole transaction is validated before any joint moves."""
        rf = self.report.get('rotary_fixture')
        if rf and 'rotary_output' in self.roots and 'rotary_chuck' in self.roots:
            angle = _nz(values.get('rotary_output'), values.get('rotary_chuck'))
            if angle is not None:
                if ('rotary_output' in values and 'rotary_chuck' in values
                        and abs(values['rotary_output'] - values['rotary_chuck']) > 1e-9):
                    raise ValueError('Rotary output and chuck share the same A-axis angle')
                values = dict(values, rotary_output=angle, rotary_chuck=angle)
        pending = []
        for n, v in values.items():
            o, s = self.roots.get(n), self.specs.get(n)
            if o is None or s is None:
                raise KeyError('Unknown joint ' + n)
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError('Non-finite joint ' + n)
            if s.get('joint_type') not in ('revolute', 'prismatic', 'continuous'):
                raise ValueError('Joint is fixed: ' + n)
            lim = s.get('limits') or (-math.inf, math.inf)
            if not clamp and (v < lim[0] - 1e-7 or v > lim[1] + 1e-7):
                raise ValueError(f'Joint {n} outside [{lim[0]},{lim[1]}]')
            pending.append((n, o, s, max(lim[0], min(lim[1], v))))
        for n, o, s, v in pending:
            loc, rot, sc = decompose_three(self.rest[o.name])
            axis = Vector(s.get('axis') or (0, 0, 1)).normalized()
            if s['joint_type'] == 'prismatic':
                loc = loc + (rot @ axis) * v
            else:
                rot = rot @ Quaternion(axis, v)
            o.matrix_basis = Matrix.LocRotScale(loc, rot, sc)
            self.state[n] = v
        for cb in list(self.pose_callbacks):
            cb()
        return self

    def reset(self):
        """every node back to its rest, state cleared, the default joints (MANTIS's nominal pose) applied"""
        for name, m in self.rest.items():
            o = bpy.data.objects.get(name)
            if o is not None:
                o.matrix_basis = m
        self.state = {}
        if self.default_joints:
            self.set_joints(self.default_joints)
        if self.filament is not None and hasattr(self.filament, 'seek'):
            self.filament.seek(0)
        for cb in list(self.pose_callbacks):
            cb()
        return self

    # ------------------------------------------------------------------------------------------------ parts
    def part_faces(self, o):
        """the part name of each face of mesh object o (provenance/ ownership), or None"""
        return self.part_for_face.get(o.name)

    def _part_ids(self, o):
        ids = self.part_ids.get(o.name)
        if ids is None:
            v = _plain(o.get('part_ids')) if o.get('part_ids') is not None else None
            ids = list(v) if isinstance(v, list) else [o.get('part_id')]
        return [p for p in ids if p]

    def parts(self):
        return list(self.actual_parts)

    def part(self, name):
        """the mesh objects holding part `name` (a batched mesh can hold others too: load_part isolates one)"""
        found = [o for o in self.meshes() if name in self._part_ids(o)]
        if not found:
            raise KeyError('Unknown part ' + name)
        return found

    def meshes(self):
        return [o for o in self.objects + self.extra_objects if o.type == 'MESH' and o.name in bpy.data.objects
                and o.get('eidoverseRobotics')]

    def stats(self):
        """triangles, meshes, uniqueGeometry, materials, textures, parts of the visible kit meshes; primitives counts
        the glTF primitives behind them (three makes one Mesh per primitive, Blender one object per node)"""
        import numpy as np
        tris = meshes = prims = 0
        geo, mats, texs = set(), set(), set()
        for o in self.meshes():
            if o.hide_render:
                continue
            lt = np.empty(len(o.data.polygons), np.int32)
            o.data.polygons.foreach_get('loop_total', lt)
            tris += int((lt - 2).sum())
            meshes += 1
            node = o.get('gltf_node')
            if node is not None and 'mesh' in self.gltf['nodes'][node] and not o.get('track_shoe'):
                prims += len(self.gltf['meshes'][self.gltf['nodes'][node]['mesh']]['primitives'])
            else:
                prims += 1
            geo.add(o.data.name)
            for s in o.material_slots:
                m = s.material
                if m is None:
                    continue
                mats.add(m.name)
                if m.use_nodes:
                    for n in m.node_tree.nodes:
                        if n.type == 'TEX_IMAGE' and n.image is not None:
                            texs.add(n.image.name)
        return {'triangles': tris, 'meshes': meshes, 'primitives': prims, 'uniqueGeometry': len(geo),
                'materials': len(mats), 'textures': len(texs), 'parts': len(self.parts())}

    # ------------------------------------------------------------------------------------------------ the look
    def set_colors(self, primary=None, accent=None, filament=None):
        self.materials.set_color(primary, accent)
        if filament is not None:
            self.materials.set_filament(filament)
        return self

    @property
    def palette(self):
        return self.materials.palette

    @property
    def recoloured(self):
        return self.materials.recoloured

    # ------------------------------------------------------------------------------------------------ keys
    def key_joints(self, frame):
        """key the joints set_joints moved, at `frame` (LINEAR)"""
        return self.key_pose(frame, [self.roots[n] for n in self.state])

    def key_pose(self, frame, objects=None):
        """key location / rotation / scale of these objects (default: every object of this robot that is away from
        its rest) at `frame`, LINEAR"""
        if objects is None:
            objects = [o for o in self.objects if o.name in self.rest and not _same(o.matrix_basis, self.rest[o.name])]
            objects += [o for o in self.extra_objects if o.name in bpy.data.objects and o.get('track_shoe')]
        n = 0
        for o in objects:
            for path in ('location', 'rotation_quaternion' if o.rotation_mode == 'QUATERNION' else 'rotation_euler',
                         'scale'):
                o.keyframe_insert(path, frame=frame)
            n += 1
        _linear_keys(objects, frame)
        return n

    # ------------------------------------------------------------------------------------------------ cleanup
    def dispose(self):
        """remove this robot (and every robot attached to it) from the file"""
        if self.disposed:
            return
        self.disposed = True
        for c in list(self.connections):
            c.dispose()
        self.stop()
        if self.filament is not None and hasattr(self.filament, 'dispose'):
            self.filament.dispose()
        self.pose_callbacks.clear()
        if self.connection:
            p = self.connection['parent']
            p.connections = [c for c in p.connections if c is not self]
        objs = [o for o in self.objects + self.extra_objects + [self.group] if o.name in bpy.data.objects]
        meshes = {o.data for o in objs if o.type == 'MESH'}
        for o in objs:
            ad = o.animation_data
            if ad is not None and ad.action is not None and ad.action.users <= 1:
                bpy.data.actions.remove(ad.action)
            bpy.data.objects.remove(o, do_unlink=True)
        for me in meshes:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        for m in self.materials.materials:
            if m.name in bpy.data.materials and m.users == 0:
                bpy.data.materials.remove(m)
        if self.materials.palette.users == 0:
            bpy.data.node_groups.remove(self.materials.palette)
        for a in self.gltf_actions:
            if a.name in bpy.data.actions and a.users == 0:
                bpy.data.actions.remove(a)
        if self.collection.name in bpy.data.collections and not self.collection.objects:
            bpy.data.collections.remove(self.collection)


def _same(a, b, eps=1e-9):
    return all(abs(x - y) <= eps for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def _linear_keys(objects, frame):
    from bpy_extras import anim_utils
    for o in objects:
        ad = o.animation_data
        if ad is None or ad.action is None:
            continue
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        if cb is None:
            continue
        for fc in cb.fcurves:
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 1e-6:
                    kp.interpolation = 'LINEAR'


# ---------------------------------------------------------------------------------------------- loading ---

def load_robot(rid, **opts) -> Robot:
    for k in opts:
        if k not in LOADER_OPTIONS and k not in BLENDER_OPTIONS:
            raise ValueError(f"Unknown modular loader option '{k}'. Geometry/slot presets were retired; load and attach "
                             'the required catalog modules.')
    pos = _nz(opts.get('position'), opts.get('location'))
    for key, v in (('position', pos), ('rotation', opts.get('rotation'))):
        if v is not None and not _finite3(v):
            raise ValueError(key + ' must be three finite numbers')
    sc = opts.get('scale')
    if sc is not None and (not isinstance(sc, (int, float)) or not math.isfinite(sc) or not sc > 0):
        raise ValueError('Use a positive uniform display scale')
    cat = catalog()
    rid = cat['aliases'].get(rid, rid)
    entry = cat['models'].get(rid)
    if entry is None:
        raise KeyError(f"Unknown modular robot '{rid}'. See catalog(); delta, Stewart and Kossel primitive presets were "
                       'retired.')
    textures = opts.get('textures', True) is not False
    path = os.path.normpath(os.path.join(ROOT, entry['path']))
    report = kio.json_file(entry['metadata']) if entry.get('metadata') else {}
    provenance = kio.json_file(entry['provenance'])
    gltf = kio.glb_json(path)
    kio.check_anisotropy(gltf)
    scene = opts.get('scene') or bpy.context.scene
    name = opts.get('name') or ('robot|' + rid)

    before = _ids()
    res = bpy.ops.import_scene.gltf(filepath=path)
    if 'FINISHED' not in res:
        raise RuntimeError(f'make_robot: the glTF importer refused {path}')
    new = [o for o in bpy.data.objects if o not in before['objects']]
    new_actions = [a for a in bpy.data.actions if a not in before['actions']]
    try:
        return _assemble(rid, entry, report, provenance, gltf, path, opts, scene, name, new, new_actions, cat,
                         textures, pos, sc)
    except Exception:
        _rollback(before)               # a refused load leaves nothing behind (index.js: never added to the scene)
        raise


_BLOCKS = ('objects', 'collections', 'materials', 'meshes', 'node_groups', 'actions', 'images')


def _ids():
    return {k: set(getattr(bpy.data, k)) for k in _BLOCKS}


def _rollback(before):
    for k in _BLOCKS:
        coll = getattr(bpy.data, k)
        for b in [b for b in coll if b not in before[k]]:
            try:
                coll.remove(b)
            except (ReferenceError, RuntimeError):
                pass


def _assemble(rid, entry, report, provenance, gltf, path, opts, scene, name, new, new_actions, cat, textures, pos, sc):
    node_obj, order = _map_nodes(gltf, new)
    gltf_actions = []                    # the GLB's own animations: kept, muted, as the source clips
    for i, o in node_obj.items():
        o['gltf_node'] = i
        # the importer evaluates a GLB's animations at the current frame while it builds (a propeller turned 15 deg,
        # the humanoid's legs moved): the rest is the node's own transform from the file
        ad = o.animation_data
        if ad is not None:
            for t in ad.nla_tracks:
                t.mute = True
                for st in t.strips:
                    if st.action is not None and st.action not in gltf_actions:
                        gltf_actions.append(st.action)
            if ad.action is not None and ad.action not in gltf_actions:
                gltf_actions.append(ad.action)
            ad.action = None
        o.rotation_mode = 'QUATERNION'
        o.matrix_basis = gltf_local(gltf['nodes'][i])
    node_name = {o.name: gltf['nodes'][i].get('name', '') for i, o in node_obj.items()}

    # provenance/: the part that owns each triangle (a node's primitives concatenate in Blender's one mesh)
    rows = {(r['node'], r['primitive']): r for r in provenance.get('meshes', [])}
    part_for_face, part_ids = {}, {}
    for i, o in node_obj.items():
        if o.type != 'MESH' or 'mesh' not in gltf['nodes'][i]:
            continue
        nprim = len(gltf['meshes'][gltf['nodes'][i]['mesh']]['primitives'])
        runs = []
        for p in range(nprim):
            r = rows.get((i, p))
            if r is None:
                runs = None
                break
            runs.extend(r['faces'])
        if not runs:
            continue
        faces = [n for n, c in runs for _ in range(c)]
        part_for_face[o.name] = faces
        ids = list(dict.fromkeys(n for n, _ in runs))
        part_ids[o.name] = ids
        o['part_faces'] = json.dumps(runs)
        o['part_id'] = ids[0]

    # derived ports: mating frames measured from the approved complete assembly (before any subassembly cut)
    bpy.context.view_layer.update()
    derived = []
    for i in order:
        o = node_obj[i]
        s = o
        par = o.parent
        km = s.get('kit_module')
        if not km or par is None or not par.get('module_id'):
            continue
        inp = ({'interface': s.get('interface'), 'position': _plain(s['attachment_position']),
                'normal': _plain(s.get('attachment_normal'))} if s.get('attachment_position') else None)
        if km == 'torso' and s.get('ports_json'):
            b = json.loads(s['ports_json']).get('belly')
            if b:
                inp = {'interface': b['interface'], 'position': b['position_m'], 'normal': b['normal']}
        if not inp or not inp.get('interface') or km == par.get('kit_module'):
            continue
        m = (par.matrix_world.inverted() @ o.matrix_world @ frame_matrix(inp['position'], inp['normal'])
             @ Matrix.Rotation(math.pi, 4, 'X'))
        derived.append({'name': par['module_id'] + '/' + km, 'owner': par, 'interface': inp['interface'], 'matrix': m,
                        'provenance': 'Mating frame measured from the approved complete assembly'})

    keep = [node_obj[i] for i in order]
    sub = opts.get('subassembly') or entry.get('subassembly')
    if sub:
        cands = [node_obj[i] for i in order if gltf['nodes'][i].get('name') == sub['root']]
        if len(cands) != 1:
            _purge(new, new_actions)
            raise ValueError('Subassembly root is missing or ambiguous: ' + sub['root'])
        root = cands[0]
        M = root.matrix_world.copy()
        drop = set()
        if sub.get('keepModule'):
            for o in _subtree(root):
                if o is not root and o.get('kit_module') and o['kit_module'] != sub['keepModule']:
                    drop.update(x.name for x in _subtree(o))
        kept = set(x.name for x in _subtree(root)) - drop
        doomed = [o for o in new if o.name not in kept]
        keep = [o for o in keep if o.name in kept]
        new = [o for o in new if o.name in kept]
        node_obj = {i: o for i, o in node_obj.items() if o.name in kept}
        order = [i for i in order if i in node_obj]
        node_name = {k: v for k, v in node_name.items() if k in kept}
        derived = [p for p in derived if p['owner'].name in kept]
        root.parent = None
        loc, rot, scl = M.decompose()
        root.matrix_basis = Matrix.LocRotScale(Vector(), rot, scl)
        for o in new:                                    # gltf.animations = []: a subassembly plays none
            if o.animation_data is not None:
                o.animation_data_clear()
        _purge(doomed, gltf_actions)
        gltf_actions = []

    col = opts.get('collection') or bpy.data.collections.new(name)
    if col.name not in scene.collection.children and col != scene.collection:
        scene.collection.children.link(col)
    group = bpy.data.objects.new(name, None)
    group.empty_display_size = 0.1
    col.objects.link(group)
    group['eidoverseRobotics'] = True
    group['_loadedAsset'] = True
    group['robot_id'] = rid
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        if o.parent is None:
            o.parent = group
            o.matrix_parent_inverse = Matrix.Identity(4)
        if o.type == 'MESH':
            o['eidoverseRobotics'] = True
            o['_loadedAsset'] = True
        if o.get('assembly') is not None:                # one mechanical instance: qualify the label per robot
            o['eidoverseAssembly'] = o['assembly']
            o['assembly'] = group.name + '/' + str(o['assembly'])

    r = Robot()
    r.id, r.entry, r.report, r.gltf, r.gltf_path = rid, dict(entry), report, gltf, path
    r.group = r.root = r.model = group
    r.collection, r.scene = col, scene
    r.objects = keep
    r.node_obj = {i: o for i, o in node_obj.items() if o.name in set(x.name for x in keep)}
    r.node_name = {k: v for k, v in node_name.items() if k in set(x.name for x in keep)}
    r.part_for_face = {k: v for k, v in part_for_face.items() if k in r.node_name}
    r.part_ids = {k: v for k, v in part_ids.items() if k in r.node_name}
    r.port_frames = cat.get('port_frames') or {}
    r.derived_ports = derived
    r.gltf_actions = gltf_actions
    r.textures = textures
    actual = []
    for o in keep:
        if o.type == 'MESH':
            for p in r._part_ids(o):
                if p not in actual:
                    actual.append(p)
    r.actual_parts = actual
    r.entry['parts'] = list(actual)

    # jointSpecs: module roots, qualified by node name when a module_id repeats
    counts = {}
    for o in keep:
        mid = o.get('module_id')
        if mid:
            counts[mid] = counts.get(mid, 0) + 1
    r.roots, r.specs = {}, {}
    for o in keep:
        mid = o.get('module_id')
        if not mid:
            continue
        n = mid if counts[mid] == 1 else r.node_name[o.name]
        if n in r.roots:
            raise RuntimeError('Ambiguous joint identity ' + n)
        r.roots[n] = o
        spec = dict(((report.get('roots') or {}).get(n) or {}).get('properties') or {})
        spec.update({k: _plain(o[k]) for k in o.keys() if k not in _OWN_KEYS and not k.startswith('_')})
        spec['name'] = r.node_name[o.name]
        r.specs[n] = spec
    r.rest = {o.name: o.matrix_basis.copy() for o in keep}
    r.materials = kmat.prepare_materials(keep, os.path.dirname(path), textures=textures, color=opts.get('color'),
                                         primary=opts.get('primary'), accent=opts.get('accent'),
                                         filament=opts.get('filament'), name=group.name)
    r._install_ports()
    r.install_motion()

    def register_part(mesh, part, parent):
        """index.js's installFilament callback: a part made at load joins the robot's parts and materials"""
        mesh.parent = parent
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        for c in list(mesh.users_collection):
            c.objects.unlink(mesh)
        col.objects.link(mesh)
        mesh['part_id'] = part
        mesh['eidoverseRobotics'] = True
        mesh['_loadedAsset'] = True
        r.part_ids[mesh.name] = [part]
        r.part_for_face[mesh.name] = [part] * len(mesh.data.polygons)
        r.extra_objects.append(mesh)
        if part not in r.actual_parts:
            r.actual_parts.append(part)
            r.entry['parts'].append(part)
        for s in mesh.material_slots:
            if s.material is not None and s.material not in r.materials.materials:
                r.materials.materials.append(s.material)
    for fn in INSTALLERS:
        fn(r, register_part)

    if pos is not None:
        group.location = Vector(pos)
    if opts.get('rotation') is not None:
        group.rotation_euler = Euler(opts['rotation'], 'XYZ')
    if sc is not None:
        group.scale = (sc, sc, sc)
    bpy.context.view_layer.update()
    return r


make_robot = load_robot


def _purge(objs, actions=()):
    meshes = {o.data for o in objs if o.type == 'MESH'}
    mats = {s.material for o in objs if o.type == 'MESH' for s in o.material_slots if s.material}
    for o in objs:
        if o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    for m in mats:
        if m.users == 0:
            bpy.data.materials.remove(m)
    for a in actions:
        if a.name in bpy.data.actions and a.users == 0:
            bpy.data.actions.remove(a)


def load_part(model_id, name, **opts) -> Robot:
    """one part's own triangles from its donor model: the donor's hierarchy and origin kept (not recentred), every
    other donor mesh hidden; incomplete ownership or an unknown part raises and removes the donor"""
    robot = load_robot(model_id, **opts)
    try:
        selected = set(o.name for o in robot.part(name))
        for o in robot.meshes():
            if o.name not in selected:
                o.hide_render = o.hide_viewport = True
                o['_hidden_by_load_part'] = True
                continue
            faces = robot.part_for_face.get(o.name)
            if not faces or len(faces) != len(o.data.polygons):
                raise RuntimeError('Exact triangle ownership unavailable for ' + name)
            keep = [i for i, p in enumerate(faces) if p == name]
            if not keep:
                raise RuntimeError('No mapped triangles for part ' + name + ' in ' + o.name)
            old = o.data
            o.data = submesh(old, keep, f'{old.name}|{name}')
            if old.users == 0:
                bpy.data.meshes.remove(old)
            robot.part_for_face[o.name] = [name] * len(keep)
            robot.part_ids[o.name] = [name]
            o['part_faces'] = json.dumps([[name, len(keep)]])
        robot.actual_parts = [name]
        robot.entry['parts'] = [name]
        return robot
    except Exception:
        robot.dispose()
        raise
