"""eidoblend.characters.lookat: a VRM's eyes on a target, as three-vrm 3.5.2's VRMLookAt drives them, baked to keys
(claudesona.md, "Eyes on a target").

    from eidoblend.characters import load_vrm
    from eidoblend.characters.lookat import LookAt, bake_look_at
    me = load_vrm('aletheia')
    rep = bake_look_at(me, target_obj, 1, 240)            # eyes follow an object (or a point, or f(frame) -> point)
    look = LookAt(me); look.key_yaw_pitch([(1, 0, 0), (12, 20, 0), (24, 0, 0)])   # vrm.lookAt.yaw = ... by hand

What three-vrm does each vrm.update (VRMCore: humanoid, then lookAt, then expressions), ported:
    lookAt(target)     the direction from the head (offsetFromHeadBone in the raw head's frame) to the target, turned
                       by restHeadWorldQuat * currentHeadWorldQuat^-1 (so it is relative to the head as it is now),
                       as azimuth/altitude against faceFront -> yaw, pitch (degrees; yaw + = toward the model's left,
                       pitch + = down)
    bone applier       each eye: Euler(YXZ) of the mapped angles (VRMLookAtRangeMap: outputScale *
                       saturate(|angle| / inputMaxValue); inner / outer per eye, down / up), in the normalized eye
                       bone, converted to the raw bone (here: VRMHandle.write_pose)
    expression applier lookUp / lookDown / lookLeft / lookRight expression weights (three-vrm's own sign choices kept)
The range maps, type and offsetFromHeadBone come from the VRM file (VRMC_vrm.lookAt; VRM 0.x firstPerson), with
three-vrm's defaults (inputMaxValue 90, outputScale 10 for bones / 1 for expressions, offset (0, 0.06, 0)).

lag=1 (default) reproduces the engine's timing: three's lookAt reads the head's matrixWorld as the last matrix refresh
left it, before this frame's humanoid.update: this frame's root, the previous frame's head pose. lag=0 uses the head
as it is on the frame. The keys go on the NLA track '<name>|lookat' (REPLACE, above the body's clips), the eye bones
only, LINEAR; the expression type keys the four look expressions instead.
"""

import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from ._math import D2R, R2D, q_to_three, quat_from_euler, v_from_three, v_to_three
from .vrm import glb_json

_RX90 = Quaternion((1.0, 0.0, 0.0), math.pi / 2)
_RX90I = _RX90.inverted().to_matrix().to_4x4()
INPUT_MAX_VALUE_MINIMUM = 0.01


class RangeMap:
    """VRMLookAtRangeMap: map(src) = outputScale * saturate(src / inputMaxValue)"""

    def __init__(self, input_max_value=90.0, output_scale=10.0):
        self.input_max_value = max(INPUT_MAX_VALUE_MINIMUM, float(input_max_value))
        self.output_scale = float(output_scale)

    def map(self, src):
        return self.output_scale * min(1.0, max(0.0, src / self.input_max_value))


def calc_azimuth_altitude(v):
    return math.atan2(-v.z, v.x), math.atan2(v.y, math.sqrt(v.x * v.x + v.z * v.z))


def sanitize_angle(a):
    return a - 2 * math.pi * round(a / 2 / math.pi)


def _face_front_quat(face_front):
    """a quaternion turning +Z to faceFront (identity when faceFront is +Z), three's axes"""
    if (Vector(face_front) - Vector((0, 0, 1))).length_squared < 0.01:
        return Quaternion()
    az, alt = calc_azimuth_altitude(Vector(face_front))
    return quat_from_euler(0.0, 0.5 * math.pi + az, alt, 'YZX')


def _file_look_at(h):
    """(type, offset (three axes), {map name: RangeMap}, face_front) from the VRM file, three-vrm's way"""
    try:
        g = glb_json(h.path)
    except Exception:  # noqa: BLE001
        g = {}
    ext = g.get('extensions', {})
    v1 = ext.get('VRMC_vrm', {}).get('lookAt')
    if v1 is not None:
        kind = 'expression' if v1.get('type') == 'expression' else 'bone'
        dflt = 1.0 if kind == 'expression' else 10.0
        maps = {}
        for nm, key in (('horizontal_inner', 'rangeMapHorizontalInner'), ('horizontal_outer', 'rangeMapHorizontalOuter'),
                        ('vertical_down', 'rangeMapVerticalDown'), ('vertical_up', 'rangeMapVerticalUp')):
            r = v1.get(key) or {}
            maps[nm] = RangeMap(r.get('inputMaxValue', 90.0), r.get('outputScale', dflt))
        return kind, Vector(v1.get('offsetFromHeadBone', (0.0, 0.06, 0.0))), maps, (0.0, 0.0, 1.0)
    fp = ext.get('VRM', {}).get('firstPerson')
    if fp is not None:
        kind = 'expression' if fp.get('lookAtTypeName') == 'BlendShape' else 'bone'
        dflt = 1.0 if kind == 'expression' else 10.0
        maps = {}
        for nm, key in (('horizontal_inner', 'lookAtHorizontalInner'), ('horizontal_outer', 'lookAtHorizontalOuter'),
                        ('vertical_down', 'lookAtVerticalDown'), ('vertical_up', 'lookAtVerticalUp')):
            r = fp.get(key) or {}
            maps[nm] = RangeMap(r.get('xRange', 90.0), r.get('yRange', dflt))
        o = fp.get('firstPersonBoneOffset')
        off = Vector((o.get('x', 0), o.get('y', 0.06), -o.get('z', 0))) if o else Vector((0.0, 0.06, 0.0))
        return kind, off, maps, (0.0, 0.0, -1.0)
    return 'bone', Vector((0.0, 0.06, 0.0)), {k: RangeMap() for k in ('horizontal_inner', 'horizontal_outer',
                                                                      'vertical_down', 'vertical_up')}, (0.0, 0.0, 1.0)


class LookAt:
    """VRMLookAt + its applier on a VRMHandle. kind/offset/face_front override the file's."""

    def __init__(self, h, kind=None, offset=None, face_front=None):
        self.h = h
        fk, fo, maps, ff = _file_look_at(h)
        self.type = kind or fk
        self.offset_from_head_bone = Vector(offset) if offset is not None else fo      # three axes, head node frame
        self.face_front = Vector(face_front if face_front is not None else ff)
        self.range_map_horizontal_inner = maps['horizontal_inner']
        self.range_map_horizontal_outer = maps['horizontal_outer']
        self.range_map_vertical_down = maps['vertical_down']
        self.range_map_vertical_up = maps['vertical_up']
        self.head = h.humanoid.get('head')
        self.eyes = {'leftEye': h.humanoid.get('leftEye'), 'rightEye': h.humanoid.get('rightEye')}
        if self.head is None:
            raise ValueError(f'LookAt: {h.name} has no humanoid head')
        self._rest_head = h.node_frame_three(self.head)          # three's _restHeadWorldQuaternion (root at rest)
        self.yaw, self.pitch = 0.0, 0.0

    # ------------------------------------------------------------------------------------------- the head
    def head_node_world(self, head_matrix=None):
        """the raw head node's world matrix (Blender axes); head_matrix: the head bone's armature-space matrix to use"""
        pb = self.h.arm.pose.bones[self.head]
        m = pb.matrix if head_matrix is None else head_matrix
        return self.h.arm.matrix_world @ m @ _RX90I

    def look_at(self, position, head_matrix=None):
        """three's VRMLookAt.lookAt(position): yaw, pitch (degrees) toward a world point (Blender axes) from the head
        as it is now (or as head_matrix, armature space)"""
        W = self.head_node_world(head_matrix)
        cur = q_to_three(W.to_3x3().normalized().to_quaternion())
        diff_inv = self._rest_head @ cur.inverted()
        head_pos = v_to_three(W @ v_from_three(self.offset_from_head_bone))
        d = diff_inv @ (v_to_three(Vector(position)) - head_pos)
        if d.length < 1e-12:
            return self.yaw, self.pitch
        d.normalize()
        az_from, alt_from = calc_azimuth_altitude(self.face_front)
        az_to, alt_to = calc_azimuth_altitude(d)
        self.yaw = R2D * sanitize_angle(az_to - az_from)
        self.pitch = R2D * sanitize_angle(alt_from - alt_to)
        return self.yaw, self.pitch

    def look_direction(self):
        """three's getLookAtWorldDirection: the gaze in world (Blender axes) for the current yaw / pitch"""
        W = self.head_node_world()
        cur = q_to_three(W.to_3x3().normalized().to_quaternion())
        ff = self._rest_head.inverted() if (self.face_front - Vector((0, 0, 1))).length_squared < 0.01 else \
            self._rest_head.inverted() @ _face_front_quat(self.face_front)
        e = quat_from_euler(D2R * self.pitch, D2R * self.yaw, 0.0, 'YXZ')
        v = Vector((0.0, 0.0, 1.0))
        v = e @ (ff @ (cur @ v))
        return v_from_three(v)

    # ------------------------------------------------------------------------------------------- the appliers
    def eye_rotations(self, yaw, pitch):
        """the bone applier: {'leftEye': Quaternion, 'rightEye': Quaternion} normalized (three's axes)"""
        ff = _face_front_quat(self.face_front)
        out = {}
        for side in ('leftEye', 'rightEye'):
            if pitch < 0:
                x = -D2R * self.range_map_vertical_down.map(-pitch)
            else:
                x = D2R * self.range_map_vertical_up.map(pitch)
            if side == 'leftEye':
                y = -D2R * self.range_map_horizontal_inner.map(-yaw) if yaw < 0 else D2R * self.range_map_horizontal_outer.map(yaw)
            else:
                y = -D2R * self.range_map_horizontal_outer.map(-yaw) if yaw < 0 else D2R * self.range_map_horizontal_inner.map(yaw)
            q = quat_from_euler(x, y, 0.0, 'YXZ')
            out[side] = ff @ q @ ff.inverted()
        return out

    def expression_weights(self, yaw, pitch):
        """the expression applier (three-vrm's choices: lookUp from the up map for pitch < 0, both sides from the
        outer map)"""
        w = {}
        if pitch < 0:
            w['lookDown'], w['lookUp'] = 0.0, self.range_map_vertical_up.map(-pitch)
        else:
            w['lookUp'], w['lookDown'] = 0.0, self.range_map_vertical_down.map(pitch)
        if yaw < 0:
            w['lookLeft'], w['lookRight'] = 0.0, self.range_map_horizontal_outer.map(-yaw)
        else:
            w['lookRight'], w['lookLeft'] = 0.0, self.range_map_horizontal_outer.map(yaw)
        return w

    def apply_yaw_pitch(self, yaw, pitch):
        """write the gaze now (unkeyed): eye bones or look expressions"""
        self.yaw, self.pitch = yaw, pitch
        if self.type == 'bone':
            rot = {k: v for k, v in self.eye_rotations(yaw, pitch).items() if self.eyes.get(k)}
            for k in rot:
                self.h.arm.pose.bones[self.eyes[k]].rotation_mode = 'QUATERNION'
            self.h.write_pose(rot)
        else:
            from .expressions import set_expression
            for k, v in self.expression_weights(yaw, pitch).items():
                if k in self.h.expr:
                    set_expression(self.h, k, v)

    def reset(self):
        self.apply_yaw_pitch(0.0, 0.0)

    # ------------------------------------------------------------------------------------------- keyed
    def key_yaw_pitch(self, keys, track=None):
        """keys [(frame, yaw, pitch)] keyed as they are (vrm.lookAt.yaw / pitch set by hand); returns a report"""
        series = [(f, y, p) for f, y, p in keys]
        return self._key(series, track)

    def _key(self, series, track=None):
        h = self.h
        if self.type == 'bone':
            from .springs import _remove_track, key_track
            tname = track or f'{h.name}|lookat'
            _remove_track(h, tname)
            bones = {k: b for k, b in self.eyes.items() if b}
            out = {b: [] for b in bones.values()}
            for f, yaw, pitch in series:
                rot = self.eye_rotations(yaw, pitch)
                for k, b in bones.items():
                    q = h.basis_from_normalized(b, _q_from_three(rot[k]))
                    lst = out[b]
                    if lst and lst[-1][1].dot(q) < 0:
                        q.negate()
                    lst.append((f, q, 1.0))
            act, _tr, n = key_track(h, tname, out, series[0][0] if series else 1)
            for b in bones.values():
                h.arm.pose.bones[b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            return {'type': 'bone', 'track': tname, 'action': act.name, 'keys': n, 'frames': len(series)}
        from .expressions import key_expression
        ex = {k: [] for k in ('lookUp', 'lookDown', 'lookLeft', 'lookRight')}
        for f, yaw, pitch in series:
            for k, v in self.expression_weights(yaw, pitch).items():
                ex[k].append((f, v))
        n = 0
        for k, ks in ex.items():
            if k in h.expr and ks:
                n += key_expression(h, k, ks, interpolation='LINEAR')
        return {'type': 'expression', 'keys': n, 'frames': len(series)}


def _q_from_three(q):
    from ._math import q_from_three
    return q_from_three(q)


def _target_at(target, f):
    if target is None:
        return None
    if callable(target):
        return Vector(target(f))
    if hasattr(target, 'matrix_world'):
        return target.matrix_world.translation.copy()
    return Vector(target)


def bake_look_at(h, target, f0, f1, lag=1, kind=None, scene=None, look=None):
    """eyes on `target` (an object, a world point, or f(frame) -> point; Blender axes) over frames f0..f1, keyed;
    returns a report with yaw / pitch per frame"""
    scene = scene or bpy.context.scene
    look = look or LookAt(h, kind=kind)
    pb = h.arm.pose.bones[look.head]
    heads, series = {}, []
    for f in range(int(f0), int(f1) + 1):
        scene.frame_set(f)
        heads[f] = pb.matrix.copy()
        hm = heads.get(f - lag, heads[min(heads)]) if lag else heads[f]
        p = _target_at(target, f)
        yaw, pitch = look.look_at(p, head_matrix=hm)
        series.append((f, yaw, pitch))
    rep = look._key(series)
    rep['yaw_pitch'] = [(f, round(y, 4), round(p, 4)) for f, y, p in series]
    rep['lag'] = lag
    scene.frame_set(scene.frame_current)
    return rep


def remove_look_at(h):
    from .springs import _remove_track
    _remove_track(h, f'{h.name}|lookat')
