"""ocean/_three.py: the few three.js r184 Vector3 / Quaternion / Matrix4 operations ocean.js and perform.js use, on
plain tuples, in three's own arithmetic (Y up), so the staging ports line for line and is testable without Blender.

    v3 helpers: add sub scale dot cross length norm lerp; apply_q(v, q); apply_axis_angle(v, axis, a)
    quaternions (x, y, z, w): q_mul q_inv q_from_euler q_from_axis_angle q_from_matrix q_slerp
    look_q(pos, facing)          Quaternion from Matrix4.lookAt(pos + facing, pos, +Y): the object's +z along facing
    basis_q(x, y, z)             Quaternion from Matrix4.makeBasis
"""

from __future__ import annotations

import math


def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def scale(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def length(a): return math.sqrt(dot(a, a))
def lerp(a, b, k): return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k)
def adds(a, b, k): return (a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k)        # addScaledVector


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else (0.0, 0.0, 0.0)


def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (ax * bw + aw * bx + ay * bz - az * by, ay * bw + aw * by + az * bx - ax * bz,
            az * bw + aw * bz + ax * by - ay * bx, aw * bw - ax * bx - ay * by - az * bz)


def q_inv(q):
    return (-q[0], -q[1], -q[2], q[3])


def q_norm(q):
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q) if n > 0 else (0.0, 0.0, 0.0, 1.0)


def apply_q(v, q):
    x, y, z = v
    qx, qy, qz, qw = q
    tx = 2 * (qy * z - qz * y)
    ty = 2 * (qz * x - qx * z)
    tz = 2 * (qx * y - qy * x)
    return (x + qw * tx + qy * tz - qz * ty, y + qw * ty + qz * tx - qx * tz, z + qw * tz + qx * ty - qy * tx)


def q_from_axis_angle(axis, a):
    s = math.sin(a / 2)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(a / 2))


def apply_axis_angle(v, axis, a):
    return apply_q(v, q_from_axis_angle(axis, a))


def q_from_euler(x, y, z, order='XYZ'):
    c1, c2, c3 = math.cos(x / 2), math.cos(y / 2), math.cos(z / 2)
    s1, s2, s3 = math.sin(x / 2), math.sin(y / 2), math.sin(z / 2)
    if order == 'XYZ':
        return (s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 + s1 * s2 * c3, c1 * c2 * c3 - s1 * s2 * s3)
    if order == 'YXZ':
        return (s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 - s1 * s2 * c3, c1 * c2 * c3 + s1 * s2 * s3)
    raise ValueError(order)


def q_from_matrix(m):
    """Quaternion.setFromRotationMatrix; m = rows of the 3x3 rotation [[m11, m12, m13], [m21 ...], [m31 ...]]."""
    (m11, m12, m13), (m21, m22, m23), (m31, m32, m33) = m
    tr = m11 + m22 + m33
    if tr > 0:
        s = 0.5 / math.sqrt(tr + 1.0)
        return ((m32 - m23) * s, (m13 - m31) * s, (m21 - m12) * s, 0.25 / s)
    if m11 > m22 and m11 > m33:
        s = 2.0 * math.sqrt(1.0 + m11 - m22 - m33)
        return (0.25 * s, (m12 + m21) / s, (m13 + m31) / s, (m32 - m23) / s)
    if m22 > m33:
        s = 2.0 * math.sqrt(1.0 + m22 - m11 - m33)
        return ((m12 + m21) / s, 0.25 * s, (m23 + m32) / s, (m13 - m31) / s)
    s = 2.0 * math.sqrt(1.0 + m33 - m11 - m22)
    return ((m13 + m31) / s, (m23 + m32) / s, 0.25 * s, (m21 - m12) / s)


def basis_q(x, y, z):
    """Matrix4.makeBasis(x, y, z) (the columns) -> quaternion."""
    return q_from_matrix(((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2])))


def look_at_matrix(eye, target, up=(0.0, 1.0, 0.0)):
    """Matrix4.lookAt(eye, target, up): the rotation whose +z points from target to eye."""
    zz = sub(eye, target)
    if dot(zz, zz) == 0:
        zz = (zz[0], zz[1], 1.0)
    zz = norm(zz)
    xx = cross(up, zz)
    if dot(xx, xx) == 0:
        zz = (zz[0] + 0.0001, zz[1], zz[2]) if abs(up[2]) == 1 else (zz[0], zz[1], zz[2] + 0.0001)
        zz = norm(zz)
        xx = cross(up, zz)
    xx = norm(xx)
    yy = cross(zz, xx)
    return ((xx[0], yy[0], zz[0]), (xx[1], yy[1], zz[1]), (xx[2], yy[2], zz[2]))


def look_q(pos, facing):
    """ocean.js lookQ: object +z along `facing`."""
    return q_from_matrix(look_at_matrix(add(pos, facing), pos, (0.0, 1.0, 0.0)))


def q_slerp(qa, qb, t):
    """Quaternion.slerp (three r184)."""
    if t == 0:
        return qa
    if t == 1:
        return qb
    x, y, z, w = qa
    cos_half = w * qb[3] + x * qb[0] + y * qb[1] + z * qb[2]
    if cos_half < 0:
        bx, by, bz, bw = -qb[0], -qb[1], -qb[2], -qb[3]
        cos_half = -cos_half
    else:
        bx, by, bz, bw = qb
    if cos_half >= 1.0:
        return qa
    sqr_sin = 1.0 - cos_half * cos_half
    if sqr_sin <= 2.220446049250313e-16:
        s = 1 - t
        return q_norm((s * x + t * bx, s * y + t * by, s * z + t * bz, s * w + t * bw))
    sin_half = math.sqrt(sqr_sin)
    half = math.atan2(sin_half, cos_half)
    ra = math.sin((1 - t) * half) / sin_half
    rb = math.sin(t * half) / sin_half
    return (x * ra + bx * rb, y * ra + by * rb, z * ra + bz * rb, w * ra + bw * rb)
