"""eidoblend.harness.keying: what render_frame keys, made LINEAR, and what it changed WITHOUT a key, found.

render_frame runs once per frame at build time and must key what it changes. Two things follow, both checked here:

  make_linear(log)            ctx.key logs every key it inserts; afterwards those keys are set LINEAR on their
                              F-curves. (Blender 5.2's keyframe_insert ignores the "new interpolation" preference
                              from Python and always inserts BEZIER / AUTO_CLAMPED, which eases sub-frame motion
                              blur samples at starts, stops and extremes.)
  snapshot(scene)             the values a WebGPU renderFrame typically wrote: object transforms and visibility, pose
                              bones, shape-key values, Geometry Nodes modifier inputs (node_inputs: Blender 5.2's
                              modifiers["m"].properties.inputs.<Socket_N>.value), lights, cameras, the scene camera,
                              exposure, and every unlinked node input of the world's and the materials' node trees
  diff(intended, saved)       a value render_frame set at frame f that the saved scene does not show at frame f was
                              changed without a key: the whole film shows the last value set instead

The runner snapshots right after render_frame at a handful of frames (the ends, evenly spaced frames, both sides of
every camera cut), and again after the build by jumping to those frames: what differs is reported by name.
"""

from __future__ import annotations

import math

import bpy

# ------------------------------------------------------------------------------------------------- the keys ---


INTERPOLATIONS = ('LINEAR', 'CONSTANT', 'BEZIER')


class KeyLog(dict):
    """{(id pointer, data path from the ID, array index): [ID, {frame: interpolation}]} of the keys ctx.key
    inserted."""

    def add(self, target, data_path: str, index: int, frame, interpolation: str = 'LINEAR') -> None:
        if interpolation not in INTERPOLATIONS:
            raise ValueError(f'interpolation {interpolation!r}: one of {INTERPOLATIONS}')
        idb = getattr(target, 'id_data', None) or target
        try:
            path = target.path_from_id(data_path)
        except (ValueError, TypeError, AttributeError):
            path = data_path
        k = (idb.as_pointer(), path, int(index))
        rec = self.get(k)
        if rec is None:
            rec = self[k] = [idb, {}]
        rec[1][round(float(frame), 3)] = interpolation


def _channelbag(idb):
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return None
    from bpy_extras import anim_utils
    try:
        return anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        return None


def make_linear(log: KeyLog) -> int:
    """Give every key the log holds the interpolation ctx.key asked for (LINEAR unless told otherwise); keys a
    script made by other means keep theirs. Returns how many keys changed."""
    n = 0
    for (_ptr, path, index), (idb, frames) in log.items():
        cb = _channelbag(idb)
        if cb is None:
            continue
        for fc in cb.fcurves:
            if fc.data_path != path or (index >= 0 and fc.array_index != index):
                continue
            for kp in fc.keyframe_points:
                want = frames.get(round(kp.co.x, 3))
                if want is not None and kp.interpolation != want:
                    kp.interpolation = want
                    n += 1
    return n


def interpolations(idb) -> dict:
    """{data path[index]: set of interpolation names} of an ID's F-curves (for tests and reports)."""
    out = {}
    cb = _channelbag(idb)
    if cb is not None:
        for fc in cb.fcurves:
            out.setdefault(f'{fc.data_path}[{fc.array_index}]', set()).update(k.interpolation for k in fc.keyframe_points)
    return out


# --------------------------------------------------------------------------------------- un-keyed changes ---

LIGHT_PROPS = {'POINT': ('energy', 'color', 'shadow_soft_size', 'use_shadow'),
               'SPOT': ('energy', 'color', 'shadow_soft_size', 'spot_size', 'spot_blend', 'use_shadow'),
               'AREA': ('energy', 'color', 'size', 'size_y', 'spread', 'use_shadow'),
               'SUN': ('energy', 'color', 'angle', 'use_shadow')}
CAMERA_PROPS = ('lens', 'sensor_width', 'shift_x', 'shift_y', 'clip_start', 'clip_end', 'ortho_scale')
DOF_PROPS = ('use_dof', 'focus_distance', 'aperture_fstop')


def _val(v):
    """A comparable value: floats, ints, bools, short vectors, and ID pointers by name."""
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    if isinstance(v, bpy.types.ID):
        return f'<{v.name}>'
    try:
        seq = tuple(v)
    except TypeError:
        return None
    if len(seq) > 16 or not all(isinstance(x, (bool, int, float)) for x in seq):
        return None
    return tuple(seq)


def _put(out, label, idb, path, v):
    v = _val(v)
    if v is not None:
        out[label] = (v, idb, path)


def _rotation(owner):
    mode = owner.rotation_mode
    if mode == 'QUATERNION':
        return 'rotation_quaternion'
    if mode == 'AXIS_ANGLE':
        return 'rotation_axis_angle'
    return 'rotation_euler'


def _tree(out, kind, owner_name, tree):
    if tree is None:
        return
    for node in tree.nodes:
        for i, sock in enumerate(node.inputs):
            if sock.is_linked or not hasattr(sock, 'default_value'):
                continue
            try:
                v = sock.default_value
            except (AttributeError, RuntimeError):
                continue
            _put(out, f"{kind} '{owner_name}' node '{node.name}' input '{sock.name}'", tree,
                 f'nodes["{node.name}"].inputs[{i}].default_value', v)


def node_inputs(m) -> list:
    """[(identifier, socket name, data path from the object, value)] of a Geometry Nodes modifier's inputs.

    Blender 5.2 keeps them as RNA, modifiers["m"].properties.inputs.<Socket_N>.value (a modifier holds no ID
    properties there: m.keys() and m["Socket_N"] raise TypeError), so ctx.key(ob, that path) keys one. Older builds
    kept them as ID properties, modifiers["m"]["Socket_N"]; those are read when the RNA form is absent."""
    out = []
    inputs = getattr(getattr(m, 'properties', None), 'inputs', None)
    if inputs is not None:
        names = {}                     # the group interface's socket names (the RNA items are named by identifier)
        ng = getattr(m, 'node_group', None)
        if ng is not None:
            for it in ng.interface.items_tree:
                if getattr(it, 'in_out', None) == 'INPUT':
                    names[it.identifier] = it.name
        for prop in inputs.bl_rna.properties:
            ident = prop.identifier
            if ident in ('rna_type', 'name'):
                continue
            item = getattr(inputs, ident, None)
            try:
                v = item.value
            except (AttributeError, RuntimeError, TypeError):      # a geometry input holds no value
                continue
            out.append((ident, names.get(ident, ident), f'modifiers["{m.name}"].properties.inputs.{ident}.value', v))
        return out
    try:
        ks = list(m.keys())
    except TypeError:          # Blender 5.2's NodesModifier has no IDProperties
        ks = []
    for k in ks:
        if not k.endswith(('_use_attribute', '_attribute_name')):
            out.append((k, k, f'modifiers["{m.name}"]["{k}"]', m[k]))
    return out


def snapshot(scene) -> dict:
    """{label: (value, owning ID, data path)} for everything render_frame is likely to change."""
    out = {}
    _put(out, 'scene.camera', scene, 'camera', scene.camera)
    _put(out, 'exposure', scene, 'view_settings.exposure', scene.view_settings.exposure)
    lights, cams, mats, keys = {}, {}, {}, {}
    for ob in scene.objects:
        n = ob.name
        for p in ('location', _rotation(ob), 'scale', 'hide_render'):
            _put(out, f"object '{n}'.{p}", ob, p, getattr(ob, p))
        if ob.type == 'ARMATURE' and ob.pose is not None:
            for pb in ob.pose.bones:
                for p in ('location', _rotation(pb), 'scale'):
                    _put(out, f"bone '{n}'/'{pb.name}'.{p}", ob, f'pose.bones["{pb.name}"].{p}', getattr(pb, p))
        for m in ob.modifiers:
            _put(out, f"modifier '{n}'/'{m.name}'.show_render", ob, f'modifiers["{m.name}"].show_render',
                 m.show_render)
            if m.type == 'NODES':
                for ident, sock, path, v in node_inputs(m):
                    label = ident if sock == ident else f'{sock} ({ident})'
                    _put(out, f"modifier '{n}'/'{m.name}' input '{label}'", ob, path, v)
        if ob.type == 'LIGHT' and ob.data is not None:
            lights[ob.data.name] = ob.data
        elif ob.type == 'CAMERA' and ob.data is not None:
            cams[ob.data.name] = ob.data
        sk = getattr(ob.data, 'shape_keys', None) if ob.type == 'MESH' else None
        if sk is not None:
            keys[sk.name] = sk
        for slot in ob.material_slots:
            if slot.material is not None:
                mats[slot.material.name] = slot.material
    for name, li in lights.items():
        for p in LIGHT_PROPS.get(li.type, ('energy', 'color')):
            if hasattr(li, p):
                _put(out, f"light '{name}'.{p}", li, p, getattr(li, p))
    for name, cam in cams.items():
        for p in CAMERA_PROPS:
            _put(out, f"camera '{name}'.{p}", cam, p, getattr(cam, p))
        for p in DOF_PROPS:
            _put(out, f"camera '{name}'.dof.{p}", cam, f'dof.{p}', getattr(cam.dof, p))
        _put(out, f"camera '{name}'.dof.focus_object", cam, 'dof.focus_object', cam.dof.focus_object)
    for name, sk in keys.items():
        for kb in sk.key_blocks[1:]:
            _put(out, f"shape key '{name}'/'{kb.name}'.value", sk, f'key_blocks["{kb.name}"].value', kb.value)
    if scene.world is not None and scene.world.use_nodes:
        _tree(out, 'world', scene.world.name, scene.world.node_tree)
    for name, m in mats.items():
        if m.use_nodes:
            _tree(out, 'material', name, m.node_tree)
    return out


def _same(a, b) -> bool:
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        try:
            a, b = float(a), float(b)
        except (TypeError, ValueError):
            return False
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return abs(a - b) <= 1e-4 * max(1.0, abs(a), abs(b))
    return a == b


def _short(v):
    if isinstance(v, tuple):
        return '(' + ', '.join(_short(x) for x in v) + ')'
    if isinstance(v, float):
        return f'{v:.4g}'
    return str(v)


def diff(intended: dict, saved: dict) -> list:
    """[(label, intended value, saved value, owning ID, data path)] where the saved scene differs."""
    out = []
    for label, (v, idb, path) in intended.items():
        s = saved.get(label)
        if s is None:
            continue                                       # gone (deleted or renamed by render_frame): not judged
        if not _same(v, s[0]):
            out.append((label, v, s[0], idb, path))
    return out


def sample_frames(scene, fs: int, fe: int, n: int = 8) -> list:
    """The frames the un-keyed check compares: both ends, n evenly spaced, and both sides of each camera cut."""
    picks = {fs, fe}
    if fe > fs:
        for k in range(n):
            picks.add(fs + int(round((fe - fs) * k / max(1, n - 1))))
    for m in scene.timeline_markers:
        if m.camera is not None:
            picks.update(f for f in (m.frame - 1, m.frame) if fs <= f <= fe)
    return sorted(picks)


def hint(label: str, idb, path: str) -> str:
    if label == 'scene.camera':
        return 'switch cameras with ctx.cut(t, camera) (a marker), never by setting scene.camera per frame'
    owner = {bpy.types.Object: 'bpy.data.objects', bpy.types.Light: 'bpy.data.lights',
             bpy.types.Camera: 'bpy.data.cameras', bpy.types.World: 'bpy.data.worlds'}
    for t, coll in owner.items():
        if isinstance(idb, t):
            return f"ctx.key({coll}['{idb.name}'], '{path}')"
    return f"ctx.key(<the {type(idb).__name__}>, '{path}')"


def report(diffs: list, frames_checked: list) -> str:
    """One readable line per value (at most 6), with the first frame each one goes wrong at."""
    first = {}
    for f, label, v, s, idb, path in diffs:
        if label not in first:
            first[label] = (f, v, s, idb, path)
    parts = []
    for label, (f, v, s, idb, path) in list(first.items())[:6]:
        parts.append(f'{label} (frame {f}: render_frame set {_short(v)}, the saved film shows {_short(s)}; '
                     f'{hint(label, idb, path)})')
    more = f' ... and {len(first) - 6} more' if len(first) > 6 else ''
    return (f'render_frame changed {len(first)} value(s) WITHOUT A KEY, so every frame of the film shows the last '
            f'value it set (checked at frames {frames_checked}): ' + '; '.join(parts) + more)
