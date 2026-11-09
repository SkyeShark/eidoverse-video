"""Bulk keys: a job keys hundreds of frames on dozens of channels, so it writes F-curves directly (Blender 5.2's
layered actions), LINEAR by default, instead of one keyframe_insert per value.

    write(id_or_struct, 'location', frames, values)            # values (n, 3) for an array property, (n,) for one
    write(mod_slot, 'value', frames, values)                    # a nodes-modifier input slot (path resolved from its ID)
    quaternions_continuous(qs, before=None)                     # flip signs so neighbours stay in one hemisphere
    value_before(id, data_path, frame, size)                    # the curve's last key value before `frame`, or None
    clear(id, data_path_prefixes, frame_range=None)             # drop the job's keys again (job.stop())
    prune(id)                                                   # remove the id's '|fabrication' action once empty

write replaces the keys from the first to the last of its frames and keeps the curve's keys outside that range, and
clear with a frame_range removes only the keys inside it: two jobs keyed into separate frame ranges of one machine (a
printer printing one part, then another) keep each other's keys, and stopping one leaves the other's.
"""

from __future__ import annotations

import numpy as np

_INTERP = {'CONSTANT': 0, 'LINEAR': 1, 'BEZIER': 2}
_EPS = 1e-3                                     # frames: a key this close to a range's end belongs to the range


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


def _channelbag(idb):
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return None
    from bpy_extras import anim_utils
    try:
        return anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        return None


def _remove_range(points, lo, hi):
    """Remove the keyframe points with lo <= frame <= hi (all of them at once when nothing else is left)."""
    m = len(points)
    if not m:
        return 0
    co = np.empty(2 * m, dtype=np.float32)
    points.foreach_get('co', co)
    f = co[0::2]
    inside = np.nonzero((f >= lo) & (f <= hi))[0]
    if len(inside) == m:
        points.clear()
    else:
        for i in inside[::-1].tolist():          # from the back, so the indices still to visit stay valid
            points.remove(points[i], fast=True)
    return len(inside)


def write(target, data_path, frames, values, interpolation='LINEAR', replace=True):
    """Key values at frames on target.data_path (one F-curve per array index). replace=True first removes the curve's
    keys from the first to the last of frames (the keys outside that range stay); replace=False only adds."""
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
    if not n:
        return act
    lo, hi = float(frames.min()) - _EPS, float(frames.max()) + _EPS
    for k, idx in enumerate(indices):
        fc = act.fcurve_ensure_for_datablock(idb, path, index=idx)
        pts = fc.keyframe_points
        if replace:
            _remove_range(pts, lo, hi)
        start = len(pts)
        pts.add(n)
        co = np.empty(2 * (start + n), dtype=np.float32)
        pts.foreach_get('co', co)
        co[2 * start::2] = frames
        co[2 * start + 1::2] = vals[:, k]
        pts.foreach_set('co', co)
        interp = np.empty(start + n, dtype=np.int32)
        pts.foreach_get('interpolation', interp)
        interp[start:] = _INTERP[interpolation]
        pts.foreach_set('interpolation', interp)
        fc.update()                              # sorts the keys by frame and sets their handles
    return act


def value_before(target, data_path, frame, size):
    """The value the curves of target.data_path hold at their last key before `frame` (a tuple of `size`), or None
    when the property has no keys there: where a new range's keys should continue from."""
    idb, path = _owner_and_path(target, data_path)
    cb = _channelbag(idb)
    if cb is None:
        return None
    out = []
    for idx in range(size):
        fc = cb.fcurves.find(path, index=idx)
        if fc is None or not len(fc.keyframe_points):
            return None
        m = len(fc.keyframe_points)
        co = np.empty(2 * m, dtype=np.float32)
        fc.keyframe_points.foreach_get('co', co)
        before = np.nonzero(co[0::2] < frame - _EPS)[0]
        if not len(before):
            return None
        out.append(float(co[2 * before[-1] + 1]))
    return tuple(out)


def quaternions_continuous(qs, before=None):
    """Flip signs so each quaternion lies in the hemisphere of the one before it (and the first in that of `before`,
    the key the new range continues from), so LINEAR keys never swing the long way round."""
    qs = np.array(qs, dtype=np.float64)
    if before is not None and len(qs) and np.dot(qs[0], np.asarray(before, dtype=np.float64)) < 0:
        qs[0] = -qs[0]
    for i in range(1, len(qs)):
        if np.dot(qs[i], qs[i - 1]) < 0:
            qs[i] = -qs[i]
    return qs


def clear(idb, prefixes, frame_range=None):
    """Remove idb's F-curves whose data paths start with one of prefixes; with frame_range=(first, last), only their
    keys in that range (a curve left without keys goes). Returns the number of curves or keys removed."""
    cb = _channelbag(idb)
    if cb is None:
        return 0
    curves = [fc for fc in cb.fcurves if any(fc.data_path.startswith(p) for p in prefixes)]
    if frame_range is None:
        for fc in curves:
            cb.fcurves.remove(fc)
        return len(curves)
    lo, hi = float(frame_range[0]) - _EPS, float(frame_range[1]) + _EPS
    removed = 0
    for fc in curves:
        removed += _remove_range(fc.keyframe_points, lo, hi)
        if len(fc.keyframe_points):
            fc.update()
        else:
            cb.fcurves.remove(fc)
    return removed


def prune(idb):
    """Unassign and remove idb's own '|fabrication' action once it holds no F-curves (what stop() leaves behind).
    Actions the job did not make are never touched."""
    import bpy
    ad = getattr(idb, 'animation_data', None)
    act = ad.action if ad is not None else None
    if act is None or '|fabrication' not in act.name:
        return False
    for layer in act.layers:
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', ()):
                if len(cb.fcurves):
                    return False
    ad.action = None
    if act.users == 0:
        bpy.data.actions.remove(act)
    return True
