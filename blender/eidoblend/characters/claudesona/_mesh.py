"""eidoblend.characters.claudesona._mesh: the claudesona's meshes read as the WebGPU runtime reads them.

The runtime works in each mesh's glTF geometry space (three's axes) and finds meshes by their glTF material names.
The VRM add-on imports a glTF mesh with several primitives as ONE Blender mesh with one material slot per primitive,
converts coordinates to Blender's axes, and renames a material whose name is taken ('Material' -> 'Material.001').
These helpers undo all three: slots carry their glTF material names again, vertex sets are per slot (= per three
primitive), and coordinates go to three's axes (x, y, z) = Blender (x, z, -y) and back.
"""

import re

import bpy
import numpy as np
from mathutils import Matrix

from ..vrm import glb_json

B2T = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])     # Blender -> three
T2B = B2T.T
_SUFFIX = re.compile(r'^(.*)\.(\d{3})$')


def _m4(m):
    return np.array([list(r) for r in m], dtype=np.float64)


def b2t4():
    M = np.eye(4)
    M[:3, :3] = B2T
    return M


def gltf_slots(h):
    """{object name: [glTF material name per material slot]} (the add-on's renames undone)"""
    try:
        g = glb_json(h.path)
    except Exception:  # noqa: BLE001 (no file: fall back to the Blender names)
        g = {}
    mats = [m.get('name', '') for m in g.get('materials', [])]
    by_node = {}
    for n in g.get('nodes', []):
        if 'mesh' in n:
            prims = g['meshes'][n['mesh']]['primitives']
            by_node[n.get('name', '')] = [mats[p['material']] if 'material' in p else '' for p in prims]
    out = {}
    for o in h.meshes:
        name = o.name if o.name in by_node else (_SUFFIX.match(o.name).group(1) if _SUFFIX.match(o.name) else o.name)
        pn = by_node.get(name)
        if pn is not None and len(pn) == len(o.material_slots):
            out[o.name] = pn
        else:
            out[o.name] = [_SUFFIX.sub(r'\1', s.material.name) if s.material else '' for s in o.material_slots]
    return out


def materials_by_name(h):
    """{glTF material name: [bpy materials]} over the character's meshes"""
    out = {}
    slots = gltf_slots(h)
    for o in h.meshes:
        for s, gname in zip(o.material_slots, slots[o.name]):
            if s.material is None:
                continue
            lst = out.setdefault(gname, [])
            if s.material not in lst:
                lst.append(s.material)
    return out


def find(h, material, need_keys=False):
    """(object, slot index) of the first mesh with a slot whose glTF material is `material`"""
    slots = gltf_slots(h)
    for o in h.meshes:
        if need_keys and not (o.data.shape_keys and len(o.data.shape_keys.key_blocks) > 1):
            continue
        names = slots.get(o.name, [])
        if material in names:
            return o, names.index(material)
    return None, None


def coords(o):
    me = o.data
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def key_coords(kb):
    a = np.empty(len(kb.data) * 3)
    kb.data.foreach_get('co', a)
    return a.reshape(-1, 3)


def set_key_coords(kb, arr):
    kb.data.foreach_set('co', np.ascontiguousarray(arr, dtype=np.float64).ravel())


def slot_vertices(o, k):
    """indices of the vertices used by faces of material slot k (one three primitive)"""
    me = o.data
    n = len(me.polygons)
    mi = np.empty(n, np.int32)
    me.polygons.foreach_get('material_index', mi)
    lt = np.empty(n, np.int32)
    me.polygons.foreach_get('loop_total', lt)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    per_loop = np.repeat(mi, lt)
    return np.unique(lv[per_loop == k])


def slot_triangles(o, k):
    """(n, 3) vertex indices of the triangles of material slot k"""
    me = o.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    v = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', v)
    mi = np.empty(n, np.int32)
    me.loop_triangles.foreach_get('material_index', mi)
    return v.reshape(-1, 3)[mi == k]


def to_space(o, ref):
    """4x4 (numpy): o's mesh coordinates -> ref's geometry space in three's axes (three: ref.matrixWorld^-1 *
    o.matrixWorld). Both on the same rigid bone, it does not change with the pose."""
    rel = _m4(ref.matrix_world.inverted_safe() @ o.matrix_world)
    return b2t4() @ rel


def apply(M, P):
    return P @ M[:3, :3].T + M[:3, 3]


def bl_to_three(P):
    return P @ B2T.T


def three_to_bl(P):
    return P @ T2B.T


def ensure_basis(o):
    if o.data.shape_keys is None:
        o.shape_key_add(name='Basis', from_mix=False)
    return o.data.shape_keys.key_blocks[0]


def rest_matrix(o, arm):
    """o's object -> armature rest space, with the armature at rest (for a bone-parented mesh: parent bone rest @
    parent inverse @ local; for an object-parented one: its local matrix)"""
    if o.parent is arm and o.parent_type == 'BONE' and o.parent_bone:
        b = arm.data.bones[o.parent_bone]
        return b.matrix_local @ Matrix.Translation((0.0, b.length, 0.0)) @ o.matrix_parent_inverse @ o.matrix_basis
    if o.parent is arm:
        return o.matrix_parent_inverse @ o.matrix_basis
    return arm.matrix_world.inverted_safe() @ o.matrix_world


def key_series(id_data, series, action_name, interpolation='LINEAR'):
    """write {data_path: [(frame, value)]} as one action on id_data (shape keys, a material's node tree, an
    object), replacing earlier keys on those paths; returns the action"""
    from bpy_extras import anim_utils
    ad = id_data.animation_data or id_data.animation_data_create()
    act = ad.action
    if act is None:
        act = bpy.data.actions.new(action_name)
        ad.action = act
    slot = ad.action_slot
    if slot is None:
        slot = act.slots.new(id_type=id_data.id_type, name=id_data.name)
        ad.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    for path, keys in series.items():
        idx = 0
        m = re.match(r'^(.*)\[(\d+)\]$', path)
        if m and not path.endswith('"]'):
            path, idx = m.group(1), int(m.group(2))
        fc = cb.fcurves.find(path, index=idx)
        if fc is not None:
            cb.fcurves.remove(fc)
        fc = cb.fcurves.new(path, index=idx)
        keys = sorted(keys)
        fc.keyframe_points.add(len(keys))
        fc.keyframe_points.foreach_set('co', [c for f, v in keys for c in (float(f), float(v))])
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
        fc.update()
    return act
