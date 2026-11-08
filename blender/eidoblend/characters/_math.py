"""eidoblend.characters._math: the family's shared maths (plain mathutils, no bpy).

three.js is Y-up, the VRM's normalized frame +X its left, +Y up, +Z forward. Blender is Z-up and a VRM faces -Y after import.
    three (x, y, z)            -> Blender (x, -z, y)             v_from_three / v_to_three
    three quaternion (w, x, y, z) -> Blender (w, x, -z, y)        q_from_three / q_to_three
The change of axes is a proper rotation (+90 deg about X): angles about mapped axes keep their sign, so the WebGPU
edition's joint tables, axes and Euler orders port literally when the maths runs in three's frame (robot_dof does).

three's Euler orders name the matrix product left to right (order 'XZY' is Rx Rz Ry); euler_from_quat / quat_from_euler
reproduce three's Euler.setFromQuaternion and Quaternion.setFromEuler exactly, including the gimbal branches.
"""

import math

from mathutils import Quaternion, Vector

D2R = math.pi / 180.0
R2D = 180.0 / math.pi


def v_from_three(v):
    return Vector((v[0], -v[2], v[1]))


def v_to_three(v):
    return Vector((v[0], v[2], -v[1]))


def q_from_three(q):
    return Quaternion((q[0], q[1], -q[3], q[2]))


def q_to_three(q):
    return Quaternion((q[0], q[1], q[3], -q[2]))


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def smooth(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0) if e1 != e0 else (1.0 if x >= e1 else 0.0)
    return t * t * (3.0 - 2.0 * t)


def ease(u):
    u = clamp(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def wrap_pi(a):
    return a - 2.0 * math.pi * math.floor((a + math.pi) / (2.0 * math.pi))


def lerp(a, b, u):
    return a + (b - a) * u


def lerp_table(xs, ys, x):
    """piecewise linear in x, held at its ends (robot_dof's lerpTable)"""
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1])
    return ys[-1]


def axis_angle(axis, ang):
    return Quaternion(Vector(axis).normalized(), ang)


def quat_from_euler(x, y, z, order):
    """three's Quaternion.setFromEuler(new Euler(x, y, z, order)): the product of the axis turns in the order's letters"""
    turns = {'X': Quaternion((1.0, 0.0, 0.0), x), 'Y': Quaternion((0.0, 1.0, 0.0), y), 'Z': Quaternion((0.0, 0.0, 1.0), z)}
    q = Quaternion()
    for c in order:
        q = q @ turns[c]
    return q


def euler_from_quat(q, order):
    """three's Euler.setFromQuaternion(q, order) -> (x, y, z) radians"""
    m = q.normalized().to_matrix()
    m11, m12, m13 = m[0]
    m21, m22, m23 = m[1]
    m31, m32, m33 = m[2]
    if order == 'XZY':
        z = math.asin(-clamp(m12, -1.0, 1.0))
        if abs(m12) < 0.9999999:
            return math.atan2(m32, m22), math.atan2(m13, m11), z
        return math.atan2(-m23, m33), 0.0, z
    if order == 'YXZ':
        x = math.asin(-clamp(m23, -1.0, 1.0))
        if abs(m23) < 0.9999999:
            return x, math.atan2(m13, m33), math.atan2(m21, m22)
        return x, math.atan2(-m31, m11), 0.0
    if order == 'XYZ':
        y = math.asin(clamp(m13, -1.0, 1.0))
        if abs(m13) < 0.9999999:
            return math.atan2(-m23, m33), y, math.atan2(-m12, m11)
        return math.atan2(m32, m22), y, 0.0
    raise ValueError(order)


def twist_about(q, a):
    """the twist of q about the unit axis a (swing-twist: q = swing * twist); identity when q is a pure swing"""
    p = q.x * a[0] + q.y * a[1] + q.z * a[2]
    t = Quaternion((q.w, a[0] * p, a[1] * p, a[2] * p))
    n = math.sqrt(t.w * t.w + t.x * t.x + t.y * t.y + t.z * t.z)
    if n < 1e-9:
        return Quaternion()
    return Quaternion((t.w / n, t.x / n, t.y / n, t.z / n))


def angle_about(q, a):
    """the signed angle of q's twist about the unit axis a, in (-pi, pi]"""
    tw = twist_about(q, a)
    ang = 2.0 * math.atan2(tw.x * a[0] + tw.y * a[1] + tw.z * a[2], tw.w)
    return wrap_pi(ang)


def qangle(a, b):
    """the angle between two orientations (rad)"""
    d = abs(a.normalized().dot(b.normalized()))
    return 2.0 * math.acos(min(1.0, d))


def rot_between(u, v):
    """the least rotation taking direction u onto direction v"""
    return Vector(u).normalized().rotation_difference(Vector(v).normalized())


def hann_smooth(vals, r):
    """a Hann-window moving average of a list (ends held), radius r samples"""
    if r <= 0:
        return list(vals)
    w = [0.5 - 0.5 * math.cos(2.0 * math.pi * (k + r + 1) / (2 * r + 2)) for k in range(-r, r + 1)]
    sw = sum(w)
    n = len(vals)
    out = []
    for i in range(n):
        s = 0.0
        for wk, k in zip(w, range(-r, r + 1)):
            s += wk * vals[min(n - 1, max(0, i + k))]
        out.append(s / sw)
    return out
