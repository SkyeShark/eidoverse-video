"""ocean/_bl.py: Blender plumbing shared by the ocean modules: meshes from arrays, attributes, keys (one at a time
or a whole F-curve at once), drivers that read a custom property, GLB import under one root."""

from __future__ import annotations

import os

import bpy
import numpy as np

INTERP = {'CONSTANT': 0, 'LINEAR': 1, 'BEZIER': 2}


# ------------------------------------------------------------------------------------------------- meshes
def mesh_from_arrays(name, verts, tris, smooth=True):
    """A mesh from (N, 3) vertices and (M, 3) triangles (or (M, 4) quads), smooth shaded."""
    verts = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
    tris = np.asarray(tris, dtype=np.int32)
    k = tris.shape[1]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.reshape(-1))
    me.loops.add(tris.size)
    me.loops.foreach_set('vertex_index', tris.reshape(-1))
    me.polygons.add(len(tris))
    me.polygons.foreach_set('loop_start', np.arange(0, tris.size, k, dtype=np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(tris), k, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    if smooth:
        me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), dtype=bool))
    return me


def add_point_attr(me, name, values, kind='FLOAT'):
    a = me.attributes.get(name) or me.attributes.new(name, kind, 'POINT')
    vals = np.asarray(values, dtype=np.float32)
    key = 'vector' if kind == 'FLOAT_VECTOR' else ('color' if kind == 'FLOAT_COLOR' else 'value')
    a.data.foreach_set(key, vals.reshape(-1))
    return a


def add_uv_from_points(me, name, uv_points):
    """A UV map from a per-vertex (N, 2) array (each loop takes its vertex's uv)."""
    uvl = me.uv_layers.get(name) or me.uv_layers.new(name=name)
    vi = np.zeros(len(me.loops), dtype=np.int32)
    me.loops.foreach_get('vertex_index', vi)
    uv = np.asarray(uv_points, dtype=np.float32)[vi]
    uvl.data.foreach_set('uv', uv.reshape(-1))
    return uvl


def link(ob, collection=None):
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def empty(name, parent=None, collection=None, display='PLAIN_AXES', size=1.0):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = display
    e.empty_display_size = size
    link(e, collection)
    if parent is not None:
        e.parent = parent
    return e


# ------------------------------------------------------------------------------------------------- keys
class Keyer:
    """Keys custom properties and transforms. key=None: set values only. key=True: insert keys and remember them
    (finish() makes them LINEAR, or CONSTANT where asked). key=<callable>: the harness's ctx.key (it does the
    interpolation pass itself)."""

    def __init__(self, key=None):
        self.key = key
        self.log = None
        if key is True:
            from eidoblend.harness.keying import KeyLog
            self.log = KeyLog()

    def __bool__(self):
        return bool(self.key)

    def __call__(self, target, data_path, index=-1, frame=None, interpolation='LINEAR'):
        if not self.key:
            return False
        if callable(self.key):
            return self.key(target, data_path, index=index, frame=frame, interpolation=interpolation)
        f = bpy.context.scene.frame_current if frame is None else frame
        ok = target.keyframe_insert(data_path, index=index, frame=f)
        if ok:
            self.log.add(target, data_path, index, f, interpolation)
        return ok

    def finish(self):
        if self.log is not None:
            from eidoblend.harness.keying import make_linear
            make_linear(self.log)


def as_keyer(key):
    return key if isinstance(key, Keyer) else Keyer(key)


def set_prop(ob, name, value, key=None, frame=None, interpolation='LINEAR'):
    """ob[name] = value (keyed when asked). A custom property set from Python sends no update of its own: the ID is
    tagged, so the drivers that read it (modifier inputs, material values) follow at the next evaluation."""
    ob[name] = value
    if hasattr(ob, 'update_tag'):
        ob.update_tag()
    k = as_keyer(key)
    if k:
        k(ob, f'["{name}"]', frame=frame, interpolation=interpolation)


def fcurve(idb, data_path, index=0, group=None):
    """The F-curve for (data_path, index) on idb's action (made when missing; Blender 5.2 slotted actions)."""
    ad = idb.animation_data or idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f'{idb.name}_action')
    act = ad.action
    if hasattr(act, 'fcurve_ensure_for_datablock'):
        return act.fcurve_ensure_for_datablock(idb, data_path, index=index, group_name=group or '')
    fc = act.fcurves.find(data_path, index=index)
    return fc or act.fcurves.new(data_path, index=index, action_group=group or '')


def bulk_keys(idb, data_path, frames, values, index=0, interpolation='LINEAR', group=None, replace=True):
    """Write a whole F-curve at once: keys at frames with values (one channel), all with one interpolation (or a
    per-key list of 'LINEAR' / 'CONSTANT'). Much faster than keyframe_insert per frame."""
    fc = fcurve(idb, data_path, index, group)
    kp = fc.keyframe_points
    if replace and len(kp):
        kp.clear()
    n = len(frames)
    if n == 0:
        return fc
    kp.add(n)
    co = np.empty(2 * n, dtype=np.float32)
    co[0::2] = np.asarray(frames, dtype=np.float32)
    co[1::2] = np.asarray(values, dtype=np.float32)
    kp.foreach_set('co', co)
    if isinstance(interpolation, str):
        ip = np.full(n, INTERP[interpolation], dtype=np.int32)
    else:
        ip = np.array([INTERP[i] for i in interpolation], dtype=np.int32)
    kp.foreach_set('interpolation', ip)
    fc.update()
    return fc


def bulk_keys_vec(idb, data_path, frames, values, interpolation='LINEAR', group=None):
    vals = np.asarray(values, dtype=np.float64)
    for i in range(vals.shape[1]):
        bulk_keys(idb, data_path, frames, vals[:, i], index=i, interpolation=interpolation, group=group)


def linear_extrapolation(idb, data_path, index=0):
    fc = fcurve(idb, data_path, index)
    fc.extrapolation = 'LINEAR'
    return fc


# ------------------------------------------------------------------------------------------------- drivers
def drive(target, data_path, source, prop, expr='x', index=-1):
    """A driver on target.data_path reading source["prop"] (a simple expression: evaluated without Python)."""
    if index >= 0:
        fc = target.driver_add(data_path, index)
    else:
        fc = target.driver_add(data_path)
    fcs = fc if isinstance(fc, list) else [fc]
    for i, f in enumerate(fcs):
        d = f.driver
        d.type = 'SCRIPTED'
        for v in list(d.variables):
            d.variables.remove(v)
        v = d.variables.new()
        v.name = 'x'
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'OBJECT'
        v.targets[0].id = source
        idx = f'[{i}]' if len(fcs) > 1 else ''
        v.targets[0].data_path = f'["{prop}"]{idx}'
        d.expression = expr
    return fcs


def modifier_input_path(mod, name):
    """The data path (from the object) of a nodes modifier's input socket `name` (Blender 5.2 keeps inputs at
    mod.properties.inputs.<identifier>.value)."""
    for item in mod.node_group.interface.items_tree:
        if getattr(item, 'in_out', None) == 'INPUT' and item.name == name:
            slot = getattr(mod.properties.inputs, item.identifier)
            return slot, slot.path_from_id('value')
    raise KeyError(name)


def set_modifier_input(mod, name, value):
    slot, _ = modifier_input_path(mod, name)
    slot.value = value


def drive_modifier_input(ob, mod, name, source, prop, expr='x'):
    slot, path = modifier_input_path(mod, name)
    return drive(ob, path, source, prop, expr)


# ------------------------------------------------------------------------------------------------- import
def import_glb(path, name, collection=None, parent=None):
    """Import a GLB under one Empty root named `name` (the guide's pattern): returns (root, new objects). The
    objects are stamped as loaded assets (the texel tools never rewrite their UVs)."""
    if not os.path.isfile(path):
        return None, []
    col = collection or bpy.context.scene.collection
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    root = empty(name, parent=parent, collection=col)
    for o in new:
        o['eido_loaded_asset'] = True
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        if o.parent is None:
            o.parent = root
    root['eido_loaded_asset'] = True
    return root, new
