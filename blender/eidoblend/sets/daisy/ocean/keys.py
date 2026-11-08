"""ocean/keys.py: how the verse is keyed: whole F-curves written at once (one per channel), LINEAR, CONSTANT on the
last key before a cut so nothing interpolates across it; quaternions kept on one hemisphere so LINEAR keys never pass
through a flip; the camera aimed as three's camera.lookAt (its -Z at the target, +Y toward world up) with its
vertical FOV as the lens; her mark as the armature's place, heading and scale."""

from __future__ import annotations

import math

from . import _bl


def _interps(frames, base, cuts):
    cut = set(cuts)
    return ['CONSTANT' if (base == 'CONSTANT' or f in cut) else base for f in frames]


def _continuous_quats(vals):
    out = [tuple(vals[0])]
    for q in vals[1:]:
        q = tuple(q)
        if sum(a * b for a, b in zip(out[-1], q)) < 0:
            q = tuple(-c for c in q)
        out.append(q)
    return out


def key_channels(targets, series, cuts=()):
    """series {channel: [(frame, value)]} onto targets {channel: (ID, data path, n or None, interpolation)}; a
    'visible' target keys hide_render / hide_viewport of its objects (CONSTANT)."""
    for name, pts in series.items():
        idb, path, n, interp = targets[name]
        frames = [f for f, _v in pts]
        if idb == 'visible':
            hide = [0.0 if v else 1.0 for _f, v in pts]
            for o in path:
                for dp in ('hide_render', 'hide_viewport'):
                    _bl.bulk_keys(o, dp, frames, hide, interpolation='CONSTANT')
                o.hide_render = o.hide_viewport = bool(hide[-1])
            continue
        ip = _interps(frames, interp, cuts)
        if isinstance(n, str):                                  # 'i2': one component of a vector property
            _bl.bulk_keys(idb, path, frames, [float(v) for _f, v in pts], index=int(n[1:]), interpolation=ip)
        elif n:
            vals = [tuple(v) for _f, v in pts]
            if path == 'rotation_quaternion':
                vals = _continuous_quats(vals)
            for i in range(n):
                _bl.bulk_keys(idb, path, frames, [v[i] for v in vals], index=i, interpolation=ip)
        else:
            _bl.bulk_keys(idb, path, frames, [float(v) for _f, v in pts], index=0, interpolation=ip)


def look_quat(pos, target):
    """three's camera.lookAt in Blender: -Z toward the target, the camera's +Y toward world +Z."""
    from mathutils import Vector
    return (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y')


def key_camera(cam, shots, set_matrix, cuts=()):
    """shots [(frame, {'pos', 'target', 'fov'})] (set-local) -> the camera keyed in world space: location, rotation
    (quaternion), lens for the vertical FOV (sensor fit VERTICAL)."""
    from mathutils import Vector
    cam.rotation_mode = 'QUATERNION'
    cd = cam.data
    cd.sensor_fit = 'VERTICAL'
    cd.clip_start = min(cd.clip_start, 0.05)                    # the page inserts sit 0.24 m from the lens
    cd.clip_end = max(cd.clip_end, 3200.0)                      # the sea reaches 1500 m (and the haze is the horizon)
    frames, locs, quats, lens = [], [], [], []
    for f, c in shots:
        p = set_matrix @ Vector(c['pos'])
        tg = set_matrix @ Vector(c['target'])
        frames.append(f)
        locs.append(tuple(p))
        quats.append(tuple(look_quat(p, tg)))
        lens.append(cd.sensor_height / (2.0 * math.tan(math.radians(c['fov']) / 2.0)))
    ip = _interps(frames, 'LINEAR', cuts)
    quats = _continuous_quats(quats)
    for i in range(3):
        _bl.bulk_keys(cam, 'location', frames, [v[i] for v in locs], index=i, interpolation=ip)
    for i in range(4):
        _bl.bulk_keys(cam, 'rotation_quaternion', frames, [v[i] for v in quats], index=i, interpolation=ip)
    _bl.bulk_keys(cd, 'lens', frames, lens, index=0, interpolation=ip)
    return {'frames': len(frames)}


def key_mark(vrm, marks, set_matrix, scale=0.87, step=0.35):
    """marks [(frame, {'pos', 'yaw'})] (set-local, yaw about +Z with 0 facing -Y) -> the armature's world place keyed:
    location, heading, scale; CONSTANT on the last key before a yaw step (her yaw steps only on cuts)."""
    from mathutils import Matrix, Vector
    arm = vrm.arm if hasattr(vrm, 'arm') else vrm
    arm.rotation_mode = 'XYZ'
    frames, locs, eul = [], [], []
    prev = None
    for f, m in marks:
        M = set_matrix @ Matrix.Translation(Vector(m['pos'])) @ Matrix.Rotation(m['yaw'], 4, 'Z')
        loc, rot, _s = M.decompose()
        e = rot.to_euler('XYZ', prev) if prev is not None else rot.to_euler('XYZ')
        prev = e
        frames.append(f)
        locs.append(tuple(loc))
        eul.append(tuple(e))
    cuts = [frames[i] for i in range(len(frames) - 1) if abs(eul[i + 1][2] - eul[i][2]) > step]
    ip = _interps(frames, 'LINEAR', cuts)
    for i in range(3):
        _bl.bulk_keys(arm, 'location', frames, [v[i] for v in locs], index=i, interpolation=ip)
        _bl.bulk_keys(arm, 'rotation_euler', frames, [v[i] for v in eul], index=i, interpolation=ip)
    arm.scale = (scale, scale, scale)
    return {'yaw_steps': cuts}
