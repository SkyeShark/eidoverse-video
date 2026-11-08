"""three.js CatmullRomCurve3 with its arc-length tables, ported exactly (pure Python, no bpy).

The curve is axis agnostic (it only interpolates the points), so a path given in Blender axes is the
engine's path through the mapped points. getPointAt / getTangentAt reparameterise by arc length
through the same 200-division table three uses, so a drive at u = 0.5 is at the same place.
"""
import math


class _Cubic:
    __slots__ = ('c0', 'c1', 'c2', 'c3')

    def init(self, x0, x1, t0, t1):
        self.c0 = x0
        self.c1 = t0
        self.c2 = -3 * x0 + 3 * x1 - 2 * t0 - t1
        self.c3 = 2 * x0 - 2 * x1 + t0 + t1

    def catmull_rom(self, x0, x1, x2, x3, tension):
        self.init(x1, x2, tension * (x2 - x0), tension * (x3 - x1))

    def nonuniform(self, x0, x1, x2, x3, dt0, dt1, dt2):
        t1 = (x1 - x0) / dt0 - (x2 - x0) / (dt0 + dt1) + (x2 - x1) / dt1
        t2 = (x2 - x1) / dt1 - (x3 - x1) / (dt1 + dt2) + (x3 - x2) / dt2
        t1 *= dt1
        t2 *= dt1
        self.init(x1, x2, t1, t2)

    def calc(self, t):
        t2 = t * t
        t3 = t2 * t
        return self.c0 + self.c1 * t + self.c2 * t2 + self.c3 * t3


def _d2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


class CatmullRomCurve3:
    """points: sequence of (x, y, z). curve_type: 'centripetal' (three's default for driveAlong),
    'chordal' or 'catmullrom' (with tension)."""

    arc_length_divisions = 200

    def __init__(self, points, closed=False, curve_type='centripetal', tension=0.5):
        self.points = [tuple(float(v) for v in p) for p in points]
        self.closed = closed
        self.curve_type = curve_type
        self.tension = tension
        self._lengths = None
        self._px, self._py, self._pz = _Cubic(), _Cubic(), _Cubic()

    def get_point(self, t):
        pts = self.points
        n = len(pts)
        p = (n - (0 if self.closed else 1)) * t
        ip = math.floor(p)
        w = p - ip
        if self.closed:
            ip += 0 if ip > 0 else (math.floor(abs(ip) / n) + 1) * n
        elif w == 0 and ip == n - 1:
            ip = n - 2
            w = 1
        if self.closed or ip > 0:
            p0 = pts[(ip - 1) % n]
        else:
            p0 = tuple(2 * pts[0][k] - pts[1][k] for k in range(3))
        p1 = pts[ip % n]
        p2 = pts[(ip + 1) % n]
        if self.closed or ip + 2 < n:
            p3 = pts[(ip + 2) % n]
        else:
            p3 = tuple(2 * pts[n - 1][k] - pts[n - 2][k] for k in range(3))
        cs = (self._px, self._py, self._pz)
        if self.curve_type in ('centripetal', 'chordal'):
            pw = 0.5 if self.curve_type == 'chordal' else 0.25
            dt0 = math.pow(_d2(p0, p1), pw)
            dt1 = math.pow(_d2(p1, p2), pw)
            dt2 = math.pow(_d2(p2, p3), pw)
            if dt1 < 1e-4:
                dt1 = 1.0
            if dt0 < 1e-4:
                dt0 = dt1
            if dt2 < 1e-4:
                dt2 = dt1
            for k in range(3):
                cs[k].nonuniform(p0[k], p1[k], p2[k], p3[k], dt0, dt1, dt2)
        else:
            for k in range(3):
                cs[k].catmull_rom(p0[k], p1[k], p2[k], p3[k], self.tension)
        return (cs[0].calc(w), cs[1].calc(w), cs[2].calc(w))

    def get_lengths(self, divisions=None):
        divisions = divisions or self.arc_length_divisions
        if self._lengths is not None and len(self._lengths) == divisions + 1:
            return self._lengths
        cache = [0.0]
        last = self.get_point(0)
        s = 0.0
        for p in range(1, divisions + 1):
            cur = self.get_point(p / divisions)
            s += math.sqrt(_d2(cur, last))
            cache.append(s)
            last = cur
        self._lengths = cache
        return cache

    def get_length(self):
        return self.get_lengths()[-1]

    def get_u_to_t_mapping(self, u, distance=None):
        L = self.get_lengths()
        il = len(L)
        target = distance if distance else u * L[il - 1]
        low, high = 0, il - 1
        while low <= high:
            i = math.floor(low + (high - low) / 2)
            c = L[i] - target
            if c < 0:
                low = i + 1
            elif c > 0:
                high = i - 1
            else:
                high = i
                break
        i = high
        if L[i] == target:
            return i / (il - 1)
        before = L[i]
        seg = L[i + 1] - before
        return (i + (target - before) / seg) / (il - 1)

    def get_point_at(self, u):
        return self.get_point(self.get_u_to_t_mapping(u))

    def get_tangent(self, t):
        d = 0.0001
        t1 = max(0.0, t - d)
        t2 = min(1.0, t + d)
        a, b = self.get_point(t1), self.get_point(t2)
        v = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
        return (v[0] / n, v[1] / n, v[2] / n)

    def get_tangent_at(self, u):
        return self.get_tangent(self.get_u_to_t_mapping(u))

    def compute_frenet_frames(self, segments, closed=False):
        return frenet_frames(self, segments, closed)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else a


def _rot(v, axis, theta):
    """v rotated about the unit axis by theta (three's makeRotationAxis applied to v)."""
    c, s = math.cos(theta), math.sin(theta)
    t = 1 - c
    x, y, z = axis
    m = ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
         (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
         (t * x * z - s * y, t * y * z + s * x, t * z * z + c))
    return tuple(m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2] for r in range(3))


def frenet_frames(curve, segments, closed=False):
    """three's Curve.computeFrenetFrames: (tangents, normals, binormals), segments + 1 of each.

    NOT axis agnostic: the first normal is picked from the smallest tangent component, so call it
    in three's axes when the result must match the engine's (eidoblend.terrain.loft does)."""
    tangents = [curve.get_tangent_at(i / segments) for i in range(segments + 1)]
    t0 = tangents[0]
    mn = float('inf')
    normal = (0.0, 0.0, 0.0)
    tx, ty, tz = abs(t0[0]), abs(t0[1]), abs(t0[2])
    if tx <= mn:
        mn = tx
        normal = (1.0, 0.0, 0.0)
    if ty <= mn:
        mn = ty
        normal = (0.0, 1.0, 0.0)
    if tz <= mn:
        normal = (0.0, 0.0, 1.0)
    vec = _norm(_cross(t0, normal))
    normals = [_cross(t0, vec)]
    binormals = [_cross(t0, normals[0])]
    for i in range(1, segments + 1):
        n = normals[i - 1]
        vec = _cross(tangents[i - 1], tangents[i])
        if math.sqrt(_dot(vec, vec)) > 2.220446049250313e-16:
            vec = _norm(vec)
            theta = math.acos(max(-1.0, min(1.0, _dot(tangents[i - 1], tangents[i]))))
            n = _rot(n, vec, theta)
        normals.append(n)
        binormals.append(_cross(tangents[i], n))
    if closed:
        theta = math.acos(max(-1.0, min(1.0, _dot(normals[0], normals[segments])))) / segments
        if _dot(tangents[0], _cross(normals[0], normals[segments])) > 0:
            theta = -theta
        for i in range(1, segments + 1):
            normals[i] = _rot(normals[i], tangents[i], theta * i)
            binormals[i] = _cross(tangents[i], normals[i])
    return tangents, normals, binormals
