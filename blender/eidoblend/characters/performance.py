"""eidoblend.characters.performance: a stationary clip performed through the body's own frame order, baked to keys.

    from eidoblend.characters import load_vrm, load_clip, perform, Ground
    me = load_vrm('claude_robot')
    rep = perform(me, load_clip(me, 'idle'), 1, 240, ground=Ground(fn=lambda x, y: 0 * x),
                  face=lambda t: {'happy': bump(t, 1.2, 3.1)}, look=lambda t: 0.0)

The WebGPU example eidoverse/examples/claude_robot.js plays a clip through my body's hardware limits each frame in a fixed
order: the clip -> the DOF pass (rehome, the leg clamps, the arms) -> the face's expressions -> the head and the crown,
which follow the expressions at their actuators' rates -> vrm.update -> the body set down onto the floor (the lowest
vertex of either foot on y = 0) -> render. perform() runs the same order ONCE over the frames, in order, and keys it all
into one action (the armature object's place, every humanoid bone, the hip stages, the shoulder pitch helpers, the 12
petals) plus the face's shape keys and the add-on's previews (LINEAR, every frame): any frame then renders alone.

    face(t) -> {expression: weight}    every frame (aa / ih / ou / ee / oh kept summing to at most 1)
    look(t) -> yaw deg (+ the robot's left); for an expression-type lookAt (my body) it keys lookLeft / lookRight at
               |yaw| / 28 (the face's horizontal range), and the crown leans into it
    ground  a Ground; the body is set down vertically every frame so its lowest foot point touches the ground under it
            (groundVRM); None leaves the clip's height
For a body without the robot's DOF (any other VRM) the clip plays as it is; the face and the ground still apply.
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import robot_dof as dof
from ._math import D2R, q_from_three, q_to_three
from .ground import SIDES
from .locomotion import Body, key_frames

LOOK_RANGE = {'horizontal': 28.0, 'up': 20.0, 'down': 25.0}     # my face's look range (rigmath.py), deg
VISEMES = ('aa', 'ih', 'ou', 'ee', 'oh')


def perform(h, clip, f0, f1, ground=None, at=(0.0, 0.0), heading=0.0, face=None, look=None, phase=0.0, time_scale=1.0,
            crown_state=None, head_state=None, body=None, loop=True, action_name=None, preroll=1.0):
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    dt = 1.0 / fps
    body = body or Body(h)
    Qr = Quaternion((0.0, 0.0, 1.0), heading * D2R)
    head, crown = dof.HeadState(), dof.Crown()
    frames, track = [], {}
    if body.robot and preroll > 0:
        w0 = dict(face(0.0)) if face else {}
        N0, _o = body.clip_pose(clip, phase, dt=dt)
        p3 = {n: q_to_three(q) for n, q in N0.items()}
        for _k in range(int(preroll * fps)):
            q3 = dict(p3)
            head.apply(q3, w0, dt, state=head_state)
            crown.apply(w0, dof.head_roll_deg(q3), dt, state=crown_state)
    for f in range(f0, f1 + 1):
        t = (f - f0) * dt
        N, off = body.clip_pose(clip, phase + t * time_scale, dt=dt * time_scale)
        helpers = dict(body.arms.helper_phi) if body.arms else {}
        stages = body.project_legs(N, stages=True)
        w = dict(face(t)) if face else {}
        vs = [w.get(v, 0.0) for v in VISEMES]
        if sum(vs) > 1:
            for v in VISEMES:
                if v in w:
                    w[v] /= sum(vs)
        if look is not None:
            yaw = look(t)
            w['lookLeft'] = min(1.0, max(0.0, yaw) / LOOK_RANGE['horizontal'])
            w['lookRight'] = min(1.0, max(0.0, -yaw) / LOOK_RANGE['horizontal'])
        petals = None
        if body.robot:
            p3 = {n: q_to_three(q) for n, q in N.items()}
            head.apply(p3, w, dt, state=head_state)
            petals = crown.apply(w, dof.head_roll_deg(p3), dt, look=w.get('lookLeft', 0.0) - w.get('lookRight', 0.0),
                                 state=crown_state)
            N = {n: q_from_three(q) for n, q in p3.items()}
        M = Matrix.Translation(Vector((at[0], at[1], 0.0))) @ Qr.to_matrix().to_4x4()
        gap = None
        if ground is not None:
            ph, Wh = body.hips(M, off, N)
            low = math.inf
            for s in SIDES:
                fk = body.leg_fk(s, ph, Wh, N)
                P = body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
                low = min(low, float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1]))))
            M = Matrix.Translation(Vector((0.0, 0.0, -low))) @ M
            gap = low
        frames.append({'f': f, 'M': M, 'N': N, 'off': off, 'stages': stages, 'helpers': helpers, 'petals': petals,
                       'set_down_m': gap})
        for k, v in w.items():
            if k not in track and f > f0:
                track[k] = [(f0, 0.0)]              # (an expression named late starts from 0, not from its first value)
            track.setdefault(k, []).append((f, v))
    rep = {'frames': [f0, f1], 'action': key_frames(h, body, frames, action_name or f'{h.name}|perform|{clip.slot}')}
    rep['face'] = key_face_track(h, track)
    rep['set_down_mm'] = [round(-1000 * max(fr['set_down_m'] for fr in frames), 1), round(-1000 * min(fr['set_down_m'] for fr in frames), 1)] \
        if ground is not None else None
    rep['_frames'] = frames
    return rep


def key_face_track(h, track):
    """{expression: [(frame, weight)]} keyed on the expressions' shape keys (weight * bind weight) and previews, LINEAR"""
    from bpy_extras import anim_utils
    out = {}
    per_key = {}
    for name, ks in track.items():
        binds = h.expr.get(name)
        if not binds:
            continue
        out[name] = len(ks)
        for o, key, wb in binds:
            d = per_key.setdefault((o, key), {})
            for f, v in ks:
                d[f] = d.get(f, 0.0) + v * wb
        pv = h.preview(name)
        if pv is not None and hasattr(pv, 'preview'):
            idb, path = pv.id_data, pv.path_from_id('preview')
            for f, v in ks:
                pv.preview = v
                idb.keyframe_insert(path, frame=f)
    for (o, key), d in per_key.items():
        sk = o.data.shape_keys
        ad = sk.animation_data or sk.animation_data_create()
        if ad.action is None:
            ad.action = bpy.data.actions.new('face|' + o.name)
        if ad.action_slot is None:
            ad.action_slot = ad.action.slots[0] if len(ad.action.slots) else ad.action.slots.new(id_type='KEY', name=sk.name)
        cb = anim_utils.action_ensure_channelbag_for_slot(ad.action, ad.action_slot)
        dp = f'key_blocks["{key}"].value'
        fc = cb.fcurves.find(dp) or cb.fcurves.new(dp)
        fs = sorted(d)
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(fs))
        fc.keyframe_points.foreach_set('co', [c for f in fs for c in (f, min(1.0, d[f]))])
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        fc.update()
    return out
