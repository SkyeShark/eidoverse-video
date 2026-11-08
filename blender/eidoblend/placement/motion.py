"""drive_along: move a vehicle / creature along a smooth path with its heading coupled to travel,
so it can never slide sideways (ported from eidoverse/scene_placement.js driveAlong).

    drive = drive_along(car, [(-8, 0), (0, -1.5), (6, 0)], duration=30, forward='+x')
    # keys every frame of the drive (LINEAR), and drive(t) poses it at t seconds for a probe

Blender takes the engine's per-frame update(t) as keys: location and Z rotation keyed on every frame
from frame_start through the drive's end, LINEAR, the house pattern of the films' build scripts.
Waypoints: (x, y) keeps the object's current height, (x, y, z), or objects. `forward` has no
default: it is the model's nose axis ('-y', '+y', '+x', '-x'), read off its preview.
"""
import math

import bpy
from mathutils import Vector

from . import _world as W
from ._curves import CatmullRomCurve3
from .helpers import _YAW


def _point(p, z0):
    if isinstance(p, bpy.types.Object):
        return tuple(p.matrix_world.translation)
    p = list(p)
    return (p[0], p[1], p[2] if len(p) > 2 else z0)


def _linear_keys(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    curves = []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        curves = list(cb.fcurves) if cb else []
    except Exception:
        curves = list(getattr(ad.action, 'fcurves', []))
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def drive_along(obj, waypoints, duration=10.0, forward=None, start_time=0.0, loop=False,
                fps=None, frame_start=None, frame_end=None, key=True):
    """Key obj along a centripetal Catmull-Rom path through `waypoints`, yawed to face travel.

    duration: seconds from start to the last waypoint. start_time: seconds before the drive begins
    (parked at the first waypoint, facing the path). loop: wrap instead of stopping.
    fps / frame_start / frame_end default to the scene's. Returns drive(t) -> u (also poses obj).
    """
    if forward not in _YAW:
        raise ValueError("drive_along: forward is REQUIRED ('-y'|'+y'|'+x'|'-x'): the LOCAL axis the "
                         "model's NOSE points along. There is no safe default: it varies per model. For "
                         "fetched models read the *_preview.jpg axis guides; for vehicles you build, the "
                         "house convention is nose along -Y, so forward='-y'.")
    sc = bpy.context.scene
    W.update()
    try:
        b = W.tight_box(obj)
        c = W.box_center(b)
        lp = obj.matrix_world.translation
        off = math.hypot(c.x - lp.x, c.y - lp.y)
        s = W.box_size(b)
        dim = max(s.x, s.y)
        if off > max(0.5, dim * 0.6):
            print("[drive_along] ⚠ '%s''s mesh is %.1fm from its origin: driving the origin swings the BODY "
                  "wide of the path. Recenter first: parent it under an Empty at its centre and drive the Empty."
                  % (obj.name, off))
        long_ax = 'x' if s.x >= s.y else 'y'
        fwd_ax = forward[1]
        if max(s.x, s.y) / max(0.001, min(s.x, s.y)) >= 1.3 and long_ax != fwd_ax:
            print("[drive_along] ⚠ forward='%s' is PERPENDICULAR to '%s''s long axis (%s): an elongated "
                  "vehicle's nose is almost always along its long axis. Re-check the preview; this is "
                  "probably forward='+%s' or '-%s'." % (forward, obj.name, long_ax, long_ax, long_ax))
    except Exception:
        pass
    z0 = obj.location.z
    pts = [_point(p, z0) for p in waypoints]
    if len(pts) < 2:
        raise ValueError('drive_along: need at least 2 waypoints')
    curve = CatmullRomCurve3(pts, False, 'centripetal')
    yaw_of = _YAW[forward]
    state = {'yaw': None}

    def drive(t):
        u = (t - start_time) / duration
        u = (u % 1.0) if loop else min(1.0, max(0.0, u))
        p = curve.get_point_at(u)
        tan = curve.get_tangent_at(min(0.999, max(0.001, u)))
        obj.location = p
        if tan[0] * tan[0] + tan[1] * tan[1] > 1e-10:
            y = yaw_of(tan[0], tan[1])
            if state['yaw'] is not None:                 # keep the keyed yaw continuous
                y += round((state['yaw'] - y) / (2 * math.pi)) * 2 * math.pi
            obj.rotation_euler.z = y
            state['yaw'] = y
        return u

    if key:
        fps = fps or sc.render.fps / sc.render.fps_base
        f0 = sc.frame_start if frame_start is None else frame_start
        f1 = frame_end if frame_end is not None else (sc.frame_end if loop else
                                                      int(math.ceil(f0 + (start_time + duration) * fps)))
        for f in range(int(f0), int(f1) + 1):
            drive((f - f0) / fps)
            obj.keyframe_insert('location', frame=f)
            obj.keyframe_insert('rotation_euler', index=2, frame=f)
        _linear_keys(obj)
        state['yaw'] = None
    return drive
