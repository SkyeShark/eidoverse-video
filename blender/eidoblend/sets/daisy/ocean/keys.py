"""ocean/keys.py: how the set's channels are keyed: whole F-curves written at once (one per channel), LINEAR (or
CONSTANT where a target asks for it, and on any frame listed in `holds`); quaternions kept on one hemisphere so LINEAR
keys never pass through a flip; a 'visible' target keys hide_render and hide_viewport of its objects (CONSTANT)."""

from __future__ import annotations

from . import _bl


def _interps(frames, base, holds):
    hold = set(holds)
    return ['CONSTANT' if (base == 'CONSTANT' or f in hold) else base for f in frames]


def _continuous_quats(vals):
    out = [tuple(vals[0])]
    for q in vals[1:]:
        q = tuple(q)
        if sum(a * b for a, b in zip(out[-1], q)) < 0:
            q = tuple(-c for c in q)
        out.append(q)
    return out


def key_channels(targets, series, holds=()):
    """series {channel: [(frame, value)]} onto targets {channel: (ID, data path, n or None, interpolation)}: n = the
    vector's size, 'i2' one component of a vector property, None a scalar. holds: frames whose key is CONSTANT (the
    value holds until the next key)."""
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
        ip = _interps(frames, interp, holds)
        if isinstance(n, str):
            _bl.bulk_keys(idb, path, frames, [float(v) for _f, v in pts], index=int(n[1:]), interpolation=ip)
        elif n:
            vals = [tuple(v) for _f, v in pts]
            if path == 'rotation_quaternion':
                vals = _continuous_quats(vals)
            for i in range(n):
                _bl.bulk_keys(idb, path, frames, [v[i] for v in vals], index=i, interpolation=ip)
        else:
            _bl.bulk_keys(idb, path, frames, [float(v) for _f, v in pts], index=0, interpolation=ip)
