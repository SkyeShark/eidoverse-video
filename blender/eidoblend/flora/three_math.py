"""three.js r184 Vector3 / Quaternion semantics in plain Python (doubles, in-place mutation, chainable), so the
vendored SeedThree generators port line for line and grow the same plants as the WebGPU edition. Only what the
generators use is here; each method mirrors three.core.js's arithmetic order.
"""
import math


class Vec3:
    __slots__ = ('x', 'y', 'z')

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def set(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        return self

    def clone(self):
        return Vec3(self.x, self.y, self.z)

    def copy(self, v):
        self.x, self.y, self.z = v.x, v.y, v.z
        return self

    def add(self, v):
        self.x += v.x; self.y += v.y; self.z += v.z
        return self

    def sub(self, v):
        self.x -= v.x; self.y -= v.y; self.z -= v.z
        return self

    def subVectors(self, a, b):
        self.x, self.y, self.z = a.x - b.x, a.y - b.y, a.z - b.z
        return self

    def addScaledVector(self, v, s):
        self.x += v.x * s; self.y += v.y * s; self.z += v.z * s
        return self

    def multiplyScalar(self, s):
        self.x *= s; self.y *= s; self.z *= s
        return self

    def divideScalar(self, s):
        return self.multiplyScalar(1 / s)

    def dot(self, v):
        return self.x * v.x + self.y * v.y + self.z * v.z

    def lengthSq(self):
        return self.x * self.x + self.y * self.y + self.z * self.z

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalize(self):
        return self.divideScalar(self.length() or 1)

    def crossVectors(self, a, b):
        ax, ay, az, bx, by, bz = a.x, a.y, a.z, b.x, b.y, b.z
        self.x, self.y, self.z = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
        return self

    def distanceToSquared(self, v):
        dx, dy, dz = self.x - v.x, self.y - v.y, self.z - v.z
        return dx * dx + dy * dy + dz * dz

    def distanceTo(self, v):
        return math.sqrt(self.distanceToSquared(v))

    def lerp(self, v, a):
        self.x += (v.x - self.x) * a; self.y += (v.y - self.y) * a; self.z += (v.z - self.z) * a
        return self

    def applyQuaternion(self, q):
        vx, vy, vz = self.x, self.y, self.z
        qx, qy, qz, qw = q.x, q.y, q.z, q.w
        tx = 2 * (qy * vz - qz * vy)
        ty = 2 * (qz * vx - qx * vz)
        tz = 2 * (qx * vy - qy * vx)
        self.x = vx + qw * tx + qy * tz - qz * ty
        self.y = vy + qw * ty + qz * tx - qx * tz
        self.z = vz + qw * tz + qx * ty - qy * tx
        return self

    def applyAxisAngle(self, axis, angle):
        return self.applyQuaternion(Quat().setFromAxisAngle(axis, angle))

    def tup(self):
        return (self.x, self.y, self.z)


class Quat:
    __slots__ = ('x', 'y', 'z', 'w')

    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self.x, self.y, self.z, self.w = x, y, z, w

    def clone(self):
        return Quat(self.x, self.y, self.z, self.w)

    def copy(self, q):
        self.x, self.y, self.z, self.w = q.x, q.y, q.z, q.w
        return self

    def setFromAxisAngle(self, axis, angle):
        half = angle / 2
        s = math.sin(half)
        self.x, self.y, self.z, self.w = axis.x * s, axis.y * s, axis.z * s, math.cos(half)
        return self

    def setFromUnitVectors(self, vf, vt):
        r = vf.dot(vt) + 1
        if r < 1e-8:
            r = 0
            if abs(vf.x) > abs(vf.z):
                self.x, self.y, self.z, self.w = -vf.y, vf.x, 0.0, r
            else:
                self.x, self.y, self.z, self.w = 0.0, -vf.z, vf.y, r
        else:
            self.x = vf.y * vt.z - vf.z * vt.y
            self.y = vf.z * vt.x - vf.x * vt.z
            self.z = vf.x * vt.y - vf.y * vt.x
            self.w = r
        return self.normalize()

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z + self.w * self.w)

    def normalize(self):
        ln = self.length()
        if ln == 0:
            self.x, self.y, self.z, self.w = 0.0, 0.0, 0.0, 1.0
        else:
            ln = 1 / ln
            self.x, self.y, self.z, self.w = self.x * ln, self.y * ln, self.z * ln, self.w * ln
        return self

    def dot(self, q):
        return self.x * q.x + self.y * q.y + self.z * q.z + self.w * q.w

    @staticmethod
    def _mul(a, b):
        qax, qay, qaz, qaw = a.x, a.y, a.z, a.w
        qbx, qby, qbz, qbw = b.x, b.y, b.z, b.w
        return (qax * qbw + qaw * qbx + qay * qbz - qaz * qby,
                qay * qbw + qaw * qby + qaz * qbx - qax * qbz,
                qaz * qbw + qaw * qbz + qax * qby - qay * qbx,
                qaw * qbw - qax * qbx - qay * qby - qaz * qbz)

    def multiply(self, q):
        self.x, self.y, self.z, self.w = Quat._mul(self, q)
        return self

    def premultiply(self, q):
        self.x, self.y, self.z, self.w = Quat._mul(q, self)
        return self

    def slerp(self, qb, t):
        x, y, z, w = qb.x, qb.y, qb.z, qb.w
        d = self.dot(qb)
        if d < 0:
            x, y, z, w = -x, -y, -z, -w
            d = -d
        s = 1 - t
        if d < 0.9995:
            theta = math.acos(d)
            sn = math.sin(theta)
            s = math.sin(s * theta) / sn
            t = math.sin(t * theta) / sn
            self.x, self.y, self.z, self.w = self.x * s + x * t, self.y * s + y * t, self.z * s + z * t, self.w * s + w * t
        else:
            self.x, self.y, self.z, self.w = self.x * s + x * t, self.y * s + y * t, self.z * s + z * t, self.w * s + w * t
            self.normalize()
        return self
