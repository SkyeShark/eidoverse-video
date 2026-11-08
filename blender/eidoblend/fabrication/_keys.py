"""Bulk keys: a job keys hundreds of frames on dozens of channels, so it writes F-curves directly (Blender 5.2's
layered actions), LINEAR by default, instead of one keyframe_insert per value.

    write(id_or_struct, 'location', frames, values)            # values (n, 3) for an array property, (n,) for one
    write(mod_slot, 'value', frames, values)                    # a nodes-modifier input slot (path resolved from its ID)
    quaternions_continuous(qs)                                  # flip signs so neighbours stay in one hemisphere
    clear(id, data_path_prefix)                                 # drop the job's F-curves again (job.stop())
"""

from __future__ import annotations

import numpy as np

_INTERP = {'CONSTANT': 0, 'LINEAR': 1, 'BEZIER': 2}


def _owner_and_path(target, data_path):
    idb = getattr(target, 'id_data', None) or target
    if idb is target:
        return idb, data_path
    return idb, target.path_from_id(data_path)


def _action(idb):
    import bpy
    ad = idb.animation_data or idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f'{idb.name}|fabrication')
    return ad.action


def write(target, data_path, frames, values, interpolation='LINEAR', replace=True):
    idb, path = _owner_and_path(target, data_path)
    act = _action(idb)
    frames = np.asarray(frames, dtype=np.float64)
    vals = np.asarray(values, dtype=np.float64)
    if vals.ndim == 1:
        vals = vals[:, None]
        indices = [0]
    else:
        indices = list(range(vals.shape[1]))
    n = len(frames)
    for k, idx in enumerate(indices):
        fc = act.fcurve_ensure_for_datablock(idb, path, index=idx)
        if replace:
            fc.keyframe_points.clear()
        start = len(fc.keyframe_points)
        fc.keyframe_points.add(n)
        co = np.empty(2 * (start + n), dtype=np.float32)
        fc.keyframe_points.foreach_get('co', co)
        co[2 * start::2] = frames
        co[2 * start + 1::2] = vals[:, k]
        fc.keyframe_points.foreach_set('co', co)
        interp = np.empty(start + n, dtype=np.int32)
        fc.keyframe_points.foreach_get('interpolation', interp)
        interp[start:] = _INTERP[interpolation]
        fc.keyframe_points.foreach_set('interpolation', interp)
        fc.update()
    return act


def quaternions_continuous(qs):
    qs = np.array(qs, dtype=np.float64)
    for i in range(1, len(qs)):
        if np.dot(qs[i], qs[i - 1]) < 0:
            qs[i] = -qs[i]
    return qs


def clear(idb, prefixes):
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return 0
    from bpy_extras import anim_utils
    try:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        return 0
    if cb is None:
        return 0
    gone = [fc for fc in cb.fcurves if any(fc.data_path.startswith(p) for p in prefixes)]
    for fc in gone:
        cb.fcurves.remove(fc)
    return len(gone)
