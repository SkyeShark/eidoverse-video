"""ocean/perform.py: the claudesona's verse-3 gestures, layered over whatever clip plays (port of
eidoverse/sets/ocean/perform.js).

Works on VRM 1.0 NORMALIZED rotations (rest = identity, model axes three's: +y up, +z the way she faces, +x her left),
read from and written to the armature through the characters family's VRMHandle (read_pose / write_pose), so the
WebGPU maths runs unchanged in three's frame.

    P = make_performer()
    P.hand_to_flower(h, w, side='right', tilt=0.1)    # two-bone IK: the hand rises to the petals by her cheek
    P.look_at(h, world_point, w)                      # neck + head toward a world point (Blender), clamped
    P.commit(h, frame=f, key=True)                    # normalized -> the armature's bones (and keys them)

    key_performance(O, h, frames, camera)   the whole verse: each frame's clip pose + the set's gestures, keyed on an
                                            NLA track 'ocean|perform' over exactly the verse's frames (REPLACE)
    bake_springs_with_plan(h, frames, plan) the characters family's spring bake with the set's resets on cuts and the
                                            flower's springs stiffened for the turn to the lens
"""

from __future__ import annotations

import math

from . import _three as T

TRACK = 'ocean|perform'
FINGERS = ('Index', 'Middle', 'Ring', 'Little')
JOINTS = ('Proximal', 'Intermediate', 'Distal')


def _q3(q):
    """mathutils Quaternion (w, x, y, z), three axes -> _three tuple (x, y, z, w)."""
    return (q.x, q.y, q.z, q.w)


def _qm(q):
    from mathutils import Quaternion
    return Quaternion((q[3], q[0], q[1], q[2]))


class _Frame:
    """One frame's working pose: normalized locals (three), the model-space rest offsets and the clip's positions."""

    def __init__(self, h):
        self.h = h
        self.N = {n: _q3(q) for n, q in h.read_pose().items()}
        self.changed = set()
        arm = h.arm
        self.pos = {}
        for n, b in h.humanoid.items():
            pb = arm.pose.bones.get(b)
            if pb is not None:
                v = pb.head
                self.pos[n] = (v.x, v.z, -v.y)                     # armature space -> three model space
        self.parent = _humanoid_parents(h)

    def model_q(self, name):
        """the normalized bone's model-space rotation (rest identity): its chain's locals composed from the hips."""
        q = (0.0, 0.0, 0.0, 1.0)
        chain = []
        n = name
        while n is not None:
            chain.append(n)
            n = self.parent.get(n)
        for n in reversed(chain):
            q = T.q_mul(q, self.N.get(n, (0.0, 0.0, 0.0, 1.0)))
        return q

    def slerp(self, name, target, w):
        if name not in self.N:
            return
        self.N[name] = T.q_slerp(self.N[name], target, w)
        self.changed.add(name)


def _humanoid_parents(h):
    cache = getattr(h, '_ocean_parents', None)
    if cache is not None:
        return cache
    inv = {b: n for n, b in h.humanoid.items()}
    out = {}
    for n, b in h.humanoid.items():
        bone = h.arm.data.bones.get(b)
        p = bone.parent if bone is not None else None
        while p is not None and p.name not in inv:
            p = p.parent
        out[n] = inv[p.name] if p is not None else None
    h._ocean_parents = out
    return out


def _rest_len(h, a, b):
    ra, rb = h.rest_head.get(h.humanoid.get(a)), h.rest_head.get(h.humanoid.get(b))
    return (rb - ra).length if ra is not None and rb is not None else 0.0


class Performer:
    def __init__(self):
        self.fr = None

    def _frame(self, h):
        if self.fr is None or self.fr.h is not h:
            self.fr = _Frame(h)
        return self.fr

    def hand_to_flower(self, h, w, side='right', reach=(0.0, 0.0, 0.0), tilt=0.0, curl=0.45):
        """the hand rises to the flower: the wrist beside the face disc, elbow down and a little out."""
        if h is None or w <= 0.0001:
            return
        fr = self._frame(h)
        s = -1.0 if side == 'right' else 1.0                   # model x of her right side is -x
        P = 'right' if side == 'right' else 'left'
        up, lo, hand = P + 'UpperArm', P + 'LowerArm', P + 'Hand'
        if any(n not in fr.N for n in (up, lo, hand, 'head')):
            return
        S, H = fr.pos[up], fr.pos['head']
        a, b = _rest_len(h, up, lo), _rest_len(h, lo, hand)
        # the face disc is centred ~(0, head + 0.03, 0.12), radius ~0.16 (claude_suit rig units): the wrist goes just
        # outside its edge at cheek height, so the fingers rise into the petals
        Tg = T.add(H, (s * (0.245 + reach[0]), -0.17 + reach[1], 0.10 + reach[2]))
        dST = T.sub(Tg, S)
        d = min(max(T.length(dST), 0.05), (a + b) * 0.995)
        dST = T.norm(dST)
        cosA = (a * a + d * d - b * b) / (2 * a * d)
        alpha = math.acos(max(-1.0, min(1.0, cosA)))
        pole = T.norm((s * 0.35, -1.0, -0.25))                 # elbow down, out, a little back
        perp = T.norm(T.sub(pole, T.scale(dST, T.dot(pole, dST))))
        E = T.add(T.add(S, T.scale(dST, math.cos(alpha) * a)), T.scale(perp, math.sin(alpha) * a))
        Tt = T.add(S, T.scale(dST, d))
        u_ = T.norm(T.sub(E, S))
        f_ = T.norm(T.sub(Tt, E))
        d0, f0 = (s, 0.0, 0.0), (0.0, 0.0, 1.0)                 # rest: the arm along s*x, the elbow flexes toward +z
        hinge0 = T.norm(T.cross(d0, f0))
        hinge = T.cross(u_, f_)
        hinge = hinge0 if T.dot(hinge, hinge) < 1e-8 else T.norm(hinge)

        def basis(dr, hg):
            x = T.norm(dr)
            y = T.norm(T.sub(hg, T.scale(x, T.dot(hg, x))))
            return T.basis_q(x, y, T.cross(x, y))
        B0i = T.q_inv(basis(d0, hinge0))
        qUp = T.q_mul(basis(u_, hinge), B0i)                  # model-space rotations
        qLo = T.q_mul(basis(f_, hinge), B0i)
        qParent = fr.model_q(fr.parent[up]) if fr.parent.get(up) else (0.0, 0.0, 0.0, 1.0)
        fr.slerp(up, T.q_mul(T.q_inv(qParent), qUp), w)
        fr.slerp(lo, T.q_mul(T.q_inv(qUp), qLo), w)
        fr.slerp(hand, T.q_from_euler(0.0, 0.15 * s, 0.22 * s), w)   # palm toward the cheek, fingers up into the petals
        for fi, F in enumerate(FINGERS):                          # a soft curl (axis +z for the right hand, -z left)
            for ji, J in enumerate(JOINTS):
                k = curl * (0.55 + ji * 0.25) * (0.8 + fi * 0.12)
                fr.slerp(P + F + J, T.q_from_axis_angle((0.0, 0.0, -s), k), w)
        fr.slerp(P + 'ThumbProximal', T.q_from_axis_angle((0.0, 1.0, 0.0), 0.35 * s), w)
        if tilt:                                                  # lean the flower into the hand
            fr.slerp('head', T.q_mul(fr.N['head'], T.q_from_axis_angle((0.0, 0.0, 1.0), tilt * -s)), w)

    def look_at(self, h, world_point, w, max_yaw=1.1, max_pitch=0.45, neck_share=0.4):
        """neck + head toward a world point (Blender world), clamped; w blends from the clip."""
        from mathutils import Vector
        if h is None or world_point is None or w <= 0.0001:
            return
        fr = self._frame(h)
        if 'head' not in fr.N:
            return
        Hm = fr.pos['head']
        pl = h.arm.matrix_world.inverted() @ Vector(world_point)
        Pm = (pl.x, pl.z, -pl.y)
        dr = T.norm(T.sub(Pm, Hm))
        yaw = max(-max_yaw, min(max_yaw, math.atan2(dr[0], dr[2])))
        pitch = max(-max_pitch, min(max_pitch, math.asin(max(-1.0, min(1.0, dr[1])))))
        want = T.q_from_euler(-pitch, yaw, 0.0, 'YXZ')            # model-space head rotation
        if 'neck' in fr.N:
            pn = fr.model_q(fr.parent['neck']) if fr.parent.get('neck') else (0.0, 0.0, 0.0, 1.0)
            nq = T.q_from_euler(-pitch * neck_share, yaw * neck_share, 0.0, 'YXZ')
            fr.slerp('neck', T.q_mul(T.q_inv(pn), nq), w)
        ph = fr.model_q(fr.parent['head']) if fr.parent.get('head') else (0.0, 0.0, 0.0, 1.0)
        fr.slerp('head', T.q_mul(T.q_inv(ph), want), w)

    def commit(self, h, frame=None, key=None):
        """normalized -> the armature (vrm.humanoid.update()); returns {bone: basis Quaternion} of what changed."""
        if h is None or self.fr is None:
            return {}
        fr, self.fr = self.fr, None
        if not fr.changed:
            return {}
        pose = {n: _qm(fr.N[n]) for n in fr.changed}
        h.write_pose(pose)
        out = {}
        for n in fr.changed:
            b = h.humanoid[n]
            pb = h.arm.pose.bones[b]
            out[b] = pb.rotation_quaternion.copy()
            if key:
                if callable(key):
                    key(pb, 'rotation_quaternion', frame=frame)
                else:
                    pb.keyframe_insert('rotation_quaternion', frame=frame)
        return out


def make_performer():
    """makePerformer(THREE) -> Performer (hand_to_flower, look_at, commit)."""
    return Performer()


# ------------------------------------------------------------------------------------------------- the verse
GESTURE_BONES = ('neck', 'head', 'rightUpperArm', 'rightLowerArm', 'rightHand', 'rightThumbProximal') + tuple(
    'right' + F + J for F in FINGERS for J in JOINTS)


def key_performance(O, h, frames, camera=None):
    """Every frame of the verse: the clip's pose (as the scene plays it), the set's gestures on top, keyed on the NLA
    track 'ocean|perform' (REPLACE, nothing outside the verse) for the bones the gestures move."""
    import bpy
    from bpy_extras import anim_utils
    scene = bpy.context.scene
    ad = h.arm.animation_data or h.arm.animation_data_create()
    for tr in list(ad.nla_tracks):
        if tr.name == TRACK:
            for st in list(tr.strips):
                if st.action is not None:
                    bpy.data.actions.remove(st.action)
            ad.nla_tracks.remove(tr)
    bones = [h.humanoid[n] for n in GESTURE_BONES if n in h.humanoid]
    series = {b: [] for b in bones}
    moved = 0
    for f, u in frames:
        scene.frame_set(f)
        base = {b: h.arm.pose.bones[b].rotation_quaternion.copy() for b in bones}
        cam_w = tuple(camera.matrix_world.translation) if camera is not None else None
        O['perform'](u, h, cam_w)
        for b in bones:
            q = h.arm.pose.bones[b].rotation_quaternion.copy()
            lst = series[b]
            if lst and lst[-1][1].dot(q) < 0:
                q.negate()
            if base[b].rotation_difference(q).angle > 1e-4:
                moved += 1
            lst.append((f, q))
    act = bpy.data.actions.new(TRACK)
    slot = act.slots.new(id_type='OBJECT', name=h.arm.name)
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    for b, lst in series.items():
        for i in range(4):
            fc = cb.fcurves.new(f'pose.bones["{b}"].rotation_quaternion', index=i, group_name=b)
            fc.keyframe_points.add(len(lst))
            fc.keyframe_points.foreach_set('co', [c for f, q in lst for c in (f, q[i])])
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.update()
    act.use_fake_user = True
    track = ad.nla_tracks.new()
    track.name = TRACK
    strip = track.strips.new(TRACK, int(frames[0][0]), act)
    if hasattr(strip, 'action_slot'):
        strip.action_slot = slot
    strip.blend_type = 'REPLACE'
    strip.extrapolation = 'NOTHING'
    strip.use_auto_blend = False
    scene.frame_set(frames[0][0])
    return {'track': TRACK, 'bones': len(bones), 'frames': len(frames), 'gesture_samples': moved}


def bake_springs_with_plan(h, frames, plan, log=None):
    """characters.springs.bake_springs over the verse with the set's resets (the entry, the cuts) and, for the turn to
    the lens, every joint's stiffness x (1 + 3.5 bump) and drag toward 0.95 by 0.6 bump (perform.js, originals restored
    outside the window). The stiffening goes in through bake_springs(step_hook=...) when the characters family has
    it, else it rides SpringRig.update for the length of this bake only."""
    import inspect
    import bpy
    from eidoblend.characters import springs as SP
    bump = plan['bump']

    def stiffen(rig, frame):
        k = bump.get(frame, 0.0)
        if not hasattr(rig, '_ocean_sd'):
            rig._ocean_sd = {id(j): (j.stiffness, j.drag) for j in rig.joints}
        for j in rig.joints:
            s0, d0 = rig._ocean_sd[id(j)]
            j.stiffness = s0 * (1 + 3.5 * k)
            j.drag = min(0.95, d0 + (0.95 - d0) * 0.6 * k)

    args = dict(solver='three', resets=plan['resets'], log=log)
    if 'step_hook' in inspect.signature(SP.bake_springs).parameters:
        rep = SP.bake_springs(h, frames[0][0], frames[-1][0], step_hook=stiffen, **args)
    else:
        orig = SP.SpringRig.update

        def update(rig, dt):
            stiffen(rig, bpy.context.scene.frame_current)
            return orig(rig, dt)
        SP.SpringRig.update = update
        try:
            rep = SP.bake_springs(h, frames[0][0], frames[-1][0], **args)
        finally:
            SP.SpringRig.update = orig
    rep['stiffened_frames'] = sum(1 for v in bump.values() if v > 0)
    return rep
