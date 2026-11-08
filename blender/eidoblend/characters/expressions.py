"""eidoblend.characters.expressions: a VRM's expressions keyed on its face's shape keys (characters.md, "Expressions").

    from eidoblend.characters import key_expression
    key_expression(me, 'happy', [(1, 0.0), (12, 1.0)])      # (frame, weight) pairs
    key_expression(me, 'blink', [(40, 0), (42, 1), (45, 0)], interpolation='LINEAR')

Every morph bind of the expression (h.expr[name]: mesh, shape key, bind weight) is keyed with weight * value: the shape keys
are the source of truth, as in episode 3's build. The add-on's own preview property is keyed beside them, so its
frame_change_post handler, which writes previews into shape keys, writes the same values and never fights the keys. A
rendered frame needs no handler: the keys alone carry the face.

scale_visemes(face) keeps the five vowel visemes summing to at most one shape (each frame of their key union divided by the
sum where it is over 1; keyed LINEAR so it holds between keys too): the robot's mouth chart is a set of whole shapes.
"""

import bpy

VISEMES = ('aa', 'ee', 'ih', 'oh', 'ou')


def _shape_action(o):
    sk = o.data.shape_keys
    if sk.animation_data is None:
        sk.animation_data_create()
    if sk.animation_data.action is None:
        sk.animation_data.action = bpy.data.actions.new('face|' + o.name)
    return sk.animation_data.action


def set_expression(h, name, value):
    """set (not key) an expression's shape keys and preview now"""
    binds = h.expr.get(name)
    if binds is None:
        raise KeyError(f'{h.name} has no expression {name!r} ({sorted(h.expr)})')
    for o, key, w in binds:
        o.data.shape_keys.key_blocks[key].value = value * w
    pv = h.preview(name)
    if pv is not None and hasattr(pv, 'preview'):
        pv.preview = value


def key_expression(h, name, keys, interpolation='BEZIER'):
    """key an expression: keys = [(frame, value)]; returns the number of keys written"""
    binds = h.expr.get(name)
    if binds is None:
        raise KeyError(f'{h.name} has no expression {name!r} ({sorted(h.expr)})')
    n = 0
    for o, key, w in binds:
        _shape_action(o)
        kb = o.data.shape_keys.key_blocks[key]
        for f, v in keys:
            kb.value = v * w
            kb.keyframe_insert('value', frame=f)
            n += 1
    pv = h.preview(name)
    if pv is not None and hasattr(pv, 'preview'):
        for f, v in keys:
            pv.preview = v
            pv.id_data.keyframe_insert(pv.path_from_id('preview'), frame=f)
    if interpolation != 'BEZIER':
        _set_interp(h, name, interpolation)
    return n


def _set_interp(h, name, interpolation):
    from bpy_extras import anim_utils
    for o, key, _w in h.expr.get(name, []):
        act = o.data.shape_keys.animation_data.action
        for slot in act.slots:
            cb = anim_utils.action_get_channelbag_for_slot(act, slot)
            for fc in (cb.fcurves if cb else []):
                if fc.data_path == f'key_blocks["{key}"].value':
                    for kp in fc.keyframe_points:
                        kp.interpolation = interpolation


def scale_visemes(face):
    """face: {expression: [(frame, value)]}; the visemes divided by their sum where it passes 1 (in place) -> a report"""
    vs = [e for e in VISEMES if e in face]
    if not vs:
        return {'frames_scaled': 0}
    frames = sorted({f for e in vs for f, _v in face[e]})

    def at(ks, f):
        ks = sorted(ks)
        if f <= ks[0][0]:
            return ks[0][1]
        if f >= ks[-1][0]:
            return ks[-1][1]
        for (f0, v0), (f1, v1) in zip(ks, ks[1:]):
            if f0 <= f <= f1:
                return v1 if f1 == f0 else v0 + (v1 - v0) * (f - f0) / (f1 - f0)
        return ks[-1][1]
    vals = {e: [at(face[e], f) for f in frames] for e in vs}
    changed, worst = 0, 0.0
    for i in range(len(frames)):
        s = sum(vals[e][i] for e in vs)
        worst = max(worst, s)
        if s > 1.0:
            changed += 1
            for e in vs:
                vals[e][i] /= s
    for e in vs:
        face[e] = list(zip(frames, vals[e]))
    return {'frames_scaled': changed, 'key_frames': len(frames), 'worst_sum': round(worst, 3)}
