"""Bulk keys on any ID through Blender 5.2's layered actions: one F-curve per channel, points set in one call.

    key_series(obj, 'location', frames, xyz_rows, interp='CONSTANT')       # a vector: one F-curve per component
    key_series(tree, 'nodes["rain_light"].outputs[0].default_value', frames, values)

keyframe_insert one frame at a time is slow over a film and ignores the interpolation preference from Python; these
write each F-curve's points at once and set their interpolation explicitly (LINEAR unless told otherwise). Calling
again for the same channel replaces its keys, so a re-bake never interleaves old keys with new ones.
"""
import bpy


def _channelbag(idb):
    from bpy_extras import anim_utils
    ad = idb.animation_data or idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new('eido_wx|' + idb.name)
    if ad.action_slot is None:
        slots = [s for s in ad.action.slots if s.target_id_type == idb.id_type]
        ad.action_slot = slots[0] if slots else ad.action.slots.new(id_type=idb.id_type, name=idb.name)
    return anim_utils.action_ensure_channelbag_for_slot(ad.action, ad.action_slot)


def key_series(idb, data_path, frames, values, interp='LINEAR'):
    """Key `data_path` of ID `idb` at `frames` with `values` (scalars, or equal-length sequences for an array
    property: one F-curve per component). Replaces the channel's existing keys."""
    frames = [float(f) for f in frames]
    if not frames:
        return
    vals = list(values)
    width = len(vals[0]) if isinstance(vals[0], (tuple, list)) else 0
    cb = _channelbag(idb)
    for comp in range(max(1, width)):
        fc = cb.fcurves.find(data_path, index=comp)
        if fc is None:
            fc = cb.fcurves.new(data_path, index=comp)
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(frames))
        flat = []
        for f, v in zip(frames, vals):
            flat.extend((f, float(v[comp]) if width else float(v)))
        fc.keyframe_points.foreach_set('co', flat)
        try:
            fc.keyframe_points.foreach_set('interpolation', [_INTERP[interp]] * len(frames))
        except (TypeError, AttributeError, RuntimeError):
            for kp in fc.keyframe_points:
                kp.interpolation = interp
        fc.update()


_INTERP = {'CONSTANT': 0, 'LINEAR': 1, 'BEZIER': 2}


def clear_keys(idb, prefix=''):
    """Remove idb's F-curves whose data path starts with prefix (all of them by default)."""
    ad = idb.animation_data
    if not ad or not ad.action or ad.action_slot is None:
        return
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    if cb is None:
        return
    for fc in [fc for fc in cb.fcurves if fc.data_path.startswith(prefix)]:
        cb.fcurves.remove(fc)


def changes_only(frames, values, tol=1e-9):
    """The frames where a value changes (plus the first and last): enough keys for CONSTANT interpolation."""
    out_f, out_v = [], []
    prev = None
    for i, (f, v) in enumerate(zip(frames, values)):
        if prev is None or _differs(v, prev, tol) or i == len(frames) - 1:
            out_f.append(f)
            out_v.append(v)
            prev = v
    return out_f, out_v


def _differs(a, b, tol):
    if isinstance(a, (tuple, list)):
        return any(abs(float(x) - float(y)) > tol for x, y in zip(a, b))
    return abs(float(a) - float(b)) > tol
