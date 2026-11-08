"""eidoblend.characters.robotics.solvers: the kit's pure kinematics, line for line (plain Python, no bpy).

From eidoverse/robotics/ (MIT): grasp.js, scara.js, serial_arm.js and rotary_setup.js. All of them already work in the
kit's native authoring axes (Blender's +Z up, metres, radians): the WebGPU edition converts their results to three's
+Y up, this edition uses them as they are.

    grasp_values(g, t)              grasp.js graspValues: interaction.json mobile.hand.grasp at phase t (0..1)
    scara                           scara.js: L1, L2, Z, GRIP_TCP (gripTCP), LIMITS (limits), forward(q, tcp),
                                    inverse(x, y, z, yaw, tcp, seed, min_z), demo(t)
    SerialArm(report, tip)          serial_arm.js: the A650's chain from metadata/articulated.json; forward(q,
                                    with_jacobian) -> 4x4 rows (or {'transform', 'jacobian'}), inverse(target, seed):
                                    bounded damped least squares, None when unreachable
    articulated_demo(t)             articulatedDemo: the A650's six joints of the 'joints' sample at phase t
    gantry_demo(t, tool, tip_rest_z)    gantryDemo: the G430's XYZ of the 'joints' sample
    constrain_gantry_pose(report, assembly, xyz)    constrainGantryPose: XYZ clamped to the axis limits
    rotary_fixture_setup(...)       rotary_setup.js rotaryFixtureSetup: the captured-jaw, sliding-tailstock datums
"""

from __future__ import annotations

import math


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (10 + t * (-15 + 6 * t))


# --------------------------------------------------------------------------------------------- grasp.js ---

def grasp_values(g: dict, t: float) -> dict:
    """the hand's joint values at grasp phase t: joints_rad eased in, and the reviewed approach keyframes (the curved,
    opposed thumb) interpolated between the two that bracket t"""
    q = {n: a * _smooth(t) for n, a in g['joints_rad'].items()}
    frames = g.get('approach_keyframes') or []
    if len(frames) > 1:
        pairs = list(zip(frames[:-1], frames[1:]))
        a, b = next(((a, b) for a, b in pairs if a['phase'] <= t <= b['phase']), (frames[-2], frames[-1]))
        f = _smooth((t - a['phase']) / (b['phase'] - a['phase']))
        for n, v in a['joints_rad'].items():
            q[n] = v * (1 - f) + b['joints_rad'][n] * f
    return q


# --------------------------------------------------------------------------------------------- scara.js ---

class _Scara:
    """Original S-500 analytic kinematics. Metres and radians; Blender Z up. The finished shared TC70 receiver moved the
    tool-root datum by 9 mm, calibrated against the delivered s500_tool transform at zero travel."""

    L1, L2, Z = 0.245, 0.255, 0.341
    GRIP_TCP = (0.0, 0.0, -0.1641)
    LIMITS = ((-125 * math.pi / 180, 125 * math.pi / 180), (-145 * math.pi / 180, 145 * math.pi / 180),
              (0.0, 0.14), (-math.pi, math.pi))

    @staticmethod
    def wrap(a):
        pi = math.pi
        return math.fmod(math.fmod(a + pi, 2 * pi) + 2 * pi, 2 * pi) - pi

    def forward(self, q, tcp=(0.0, 0.0, 0.0)):
        """[x, y, z, yaw] of the tool (plus a tool-frame tcp offset) for q = [shoulder, elbow, quill, tool]"""
        a, b, z, r = q
        yaw = self.wrap(a + b + r)
        tx, ty, tz = tcp
        return [self.L1 * math.cos(a) + self.L2 * math.cos(a + b) + math.cos(yaw) * tx - math.sin(yaw) * ty,
                self.L1 * math.sin(a) + self.L2 * math.sin(a + b) + math.sin(yaw) * tx + math.cos(yaw) * ty,
                self.Z - z + tz,
                yaw]

    def inverse(self, x, y, z, yaw=0.0, tcp=(0.0, 0.0, 0.0), seed=None, min_z=None):
        """every joint solution within limits (elbow up / down), sorted nearest the seed when given; [] if none"""
        if not all(math.isfinite(v) for v in (x, y, z, yaw, *tcp)) or (min_z is not None and z < min_z):
            return []
        tx, ty, tz = tcp
        x -= math.cos(yaw) * tx - math.sin(yaw) * ty
        y -= math.sin(yaw) * tx + math.cos(yaw) * ty
        L1, L2 = self.L1, self.L2
        d = (x * x + y * y - L1 * L1 - L2 * L2) / (2 * L1 * L2)
        if abs(d) > 1 + 1e-10:
            return []
        angle = math.acos(max(-1.0, min(1.0, d)))
        result = []
        for b in ((angle, -angle) if angle > 1e-9 else (0.0,)):
            a = self.wrap(math.atan2(y, x) - math.atan2(L2 * math.sin(b), L1 + L2 * math.cos(b)))
            q = [a, b, self.Z + tz - z, self.wrap(yaw - a - b)]
            if all(self.LIMITS[i][0] - 1e-9 <= v <= self.LIMITS[i][1] + 1e-9 for i, v in enumerate(q)):
                result.append(q)
        if seed:
            def distance(q):
                return sum(((v - seed[i]) * 8 if i == 2 else self.wrap(v - seed[i])) ** 2 for i, v in enumerate(q))
            result.sort(key=distance)
        return result

    def demo(self, t):
        """the 'joints' sample's SCARA path at phase t (an ellipse with a bobbing quill, elbow on the positive side)"""
        a = t * 2 * math.pi
        sols = self.inverse(0.32 + 0.08 * math.cos(a), 0.12 * math.sin(a), 0.102 + 0.025 * math.cos(a * 2), 0.0,
                            self.GRIP_TCP, None, 0.055)
        q = next((q for q in sols if q[1] >= 0), None)
        if q is None:
            raise RuntimeError('SCARA path is unreachable')
        return q


scara = _Scara()


# ---------------------------------------------------------------------------------------- serial_arm.js ---

def _identity():
    return [[float(i == j) for j in range(4)] for i in range(4)]


def _mul(a, b):
    return [[sum(row[k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for row in a]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _length(a):
    return math.sqrt(sum(v * v for v in a))


def _rotation(axis, angle):
    n = _length(axis)
    x, y, z = (v / n for v in axis)
    c, s = math.cos(angle), math.sin(angle)
    v = 1 - c
    r = _identity()
    r[0][0:3] = [c + x * x * v, x * y * v - z * s, x * z * v + y * s]
    r[1][0:3] = [y * x * v + z * s, c + y * y * v, y * z * v - x * s]
    r[2][0:3] = [z * x * v - y * s, z * y * v + x * s, c + z * z * v]
    return r


def _rotation_error(target, actual):
    r = [[sum(target[i][k] * actual[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
    trace = r[0][0] + r[1][1] + r[2][2]
    if trace > 0:
        s = math.sqrt(trace + 1) * 2
        q = [(r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s, s / 4]
    else:
        q = [0.0, 0.0, 0.0, 0.0]
        i = 0
        for k in (1, 2):
            if r[k][k] > r[i][i]:
                i = k
        j, k = (i + 1) % 3, (i + 2) % 3
        s = 2 * math.sqrt(max(0.0, 1 + r[i][i] - r[j][j] - r[k][k]))
        q[i] = s / 4
        q[j] = (r[j][i] + r[i][j]) / s
        q[k] = (r[k][i] + r[i][k]) / s
        q[3] = (r[k][j] - r[j][k]) / s
    if q[3] < 0:
        q = [-v for v in q]
    n = _length(q[:3])
    if n < 1e-10:
        return [v * 2 for v in q[:3]]
    return [v * 2 * math.atan2(n, q[3]) / n for v in q[:3]]


def _solve(a, b):
    n = len(b)
    m = [list(r) + [b[i]] for i, r in enumerate(a)]
    for k in range(n):
        p = k
        for i in range(k + 1, n):
            if abs(m[i][k]) > abs(m[p][k]):
                p = i
        m[k], m[p] = m[p], m[k]
        if abs(m[k][k]) < 1e-16:
            return None
        d = m[k][k]
        for j in range(k, n + 1):
            m[k][j] /= d
        for i in range(n):
            if i != k:
                d = m[i][k]
                for j in range(k, n + 1):
                    m[i][j] -= d * m[k][j]
    return [r[n] for r in m]


class SerialArm:
    """the A650's kinematic chain from its metadata (report.roots: location, rotation_euler XYZ, parent, properties
    axis / limits), in native Blender coordinates relative to the GLB's root; tip = the TCP offset in a650_j6's frame"""

    def __init__(self, report: dict, tip=(0.018, 0.0, 0.0)):
        self.tip = list(tip)
        self.joints = []
        previous = None
        for i in range(1, 7):
            name = f'a650_j{i}'
            chain = []
            node = name
            while node != previous:
                r = report['roots'][node]
                chain.append(r)
                node = r.get('parent')
                if node is None:
                    break
            rest = _identity()
            for r in reversed(chain):
                x, y, z = r['rotation_euler']
                t = _mul(_mul(_rotation([0, 0, 1], z), _rotation([0, 1, 0], y)), _rotation([1, 0, 0], x))
                for k in range(3):
                    t[k][3] = r['location'][k]
                rest = _mul(rest, t)
            self.joints.append(dict(report['roots'][name]['properties'], rest=rest))
            previous = name

    def forward(self, q, with_jacobian=False):
        t = _identity()
        origins, axes = [], []
        for i in range(6):
            j = self.joints[i]
            t = _mul(t, j['rest'])
            origins.append([r[3] for r in t[:3]])
            axes.append([sum(r[k] * v for k, v in enumerate(j['axis'])) for r in t[:3]])
            t = _mul(t, _rotation(j['axis'], q[i]))
        for i in range(3):
            t[i][3] += sum(t[i][k] * v for k, v in enumerate(self.tip))
        if not with_jacobian:
            return t
        p = [t[k][3] for k in range(3)]
        columns = [_cross(a, [p[k] - origins[i][k] for k in range(3)]) + list(a) for i, a in enumerate(axes)]
        return {'transform': t, 'jacobian': [[c[i] for c in columns] for i in range(6)]}

    def inverse(self, target, seed=None):
        """joint angles that put the TCP at `target` (4x4 rows, the GLB root's frame), or None"""
        if len(target) != 4 or any(len(r) != 4 or any(not math.isfinite(v) for v in r) for r in target):
            raise ValueError('A finite 4x4 target transform is required')
        lim = [j['limits'] for j in self.joints]
        start = seed if seed is not None else [(a + b) / 2 for a, b in lim]
        q = [max(lim[i][0], min(lim[i][1], v)) for i, v in enumerate(start)]
        weights = [1, 1, 1, 0.18, 0.18, 0.18]
        for _step in range(100):
            f = self.forward(q, True)
            t, raw = f['transform'], f['jacobian']
            p = [target[i][3] - t[i][3] for i in range(3)]
            o = _rotation_error(target, t)
            if _length(p) < 2e-5 and _length(o) < 2e-4:
                return q
            e = [v * weights[i] for i, v in enumerate(p + o)]
            j = [[v * weights[i] for v in r] for i, r in enumerate(raw)]
            a = [[sum(n * s[l] for l, n in enumerate(r)) + (1e-6 if i == k else 0.0) for k, s in enumerate(j)]
                 for i, r in enumerate(j)]
            sol = _solve(a, e)
            if sol is None:
                return None
            dq = [sum(r[k] * sol[i] for i, r in enumerate(j)) for k in range(len(q))]
            scale = min(1.0, 0.2 / max(abs(v) for v in dq)) if any(dq) else 1.0
            q = [max(lim[i][0], min(lim[i][1], v + dq[i] * scale)) for i, v in enumerate(q)]
        return None


def articulated_demo(t):
    a = t * math.pi * 2
    return [0.35 * math.sin(a), 0.20 + 0.23 * math.sin(a + 0.4), -0.45 + 0.27 * math.cos(a), 0.30 * math.sin(a + 0.8),
            0.65 + 0.24 * math.sin(a + 0.5), 0.4 * math.cos(a)]


def gantry_demo(t, tool='bare', tip_rest_z=None):
    a = t * math.pi * 2
    tip = 0.066 + 0.035 * (1 - math.cos(a))
    if tip_rest_z is not None and math.isfinite(tip_rest_z):
        z = tip - tip_rest_z
    elif tool == 'extruder':
        z = tip - (0.275 - 0.077)
    elif tool == 'spindle':
        z = tip - (0.275 - 0.132)
    else:
        z = -0.07 + 0.06 * math.sin(a + 0.9)
    return [0.145 * math.sin(a), 0.110 * math.sin(2 * a + 0.3), z]


def constrain_gantry_pose(report, assembly, xyz):
    if len(xyz) != 3 or any(not math.isfinite(v) for v in xyz):
        raise ValueError('A finite XYZ pose is required')
    out = []
    for i, v in enumerate(xyz):
        if i == 2 and assembly and assembly.get('z_limits_m'):
            lim = assembly['z_limits_m']
        else:
            lim = report['roots'][('gantry_x', 'gantry_y', 'gantry_z')[i]]['properties']['limits']
        out.append(max(lim[0], min(lim[1], v)))
    return out


# -------------------------------------------------------------------------------------- rotary_setup.js ---

def rotary_fixture_setup(stock_length=0.140, stock_width=0.036, stock_height=0.036, quill=0.0):
    """the rotary fixture's joints for a rectangular blank: tailstock carriage, quill and handwheel, the four jaws
    (rotaryFixtureSetup({stockLength, stockWidth, stockHeight, quill}); the record's keys in snake_case)"""
    if not all(math.isfinite(v) for v in (stock_length, stock_width, stock_height, quill)):
        raise ValueError('Rotary stock dimensions and quill travel must be finite')
    if (stock_length < 0.080 - 1e-9 or stock_length > 0.180 + 1e-9 or min(stock_width, stock_height) < 0.018 - 1e-9
            or max(stock_width, stock_height) > 0.050 + 1e-9):
        raise ValueError('Fixture accepts 80-180 mm long stock, 18-50 mm wide and high')
    tailstock = stock_length - 0.140 - quill
    if abs(quill) > 0.006 + 1e-9 or tailstock < -0.060 - 1e-9 or tailstock > 0.040 + 1e-9:
        raise ValueError('Tailstock carriage or quill exceeds its captured travel')
    return {'stock_length': stock_length, 'stock_width': stock_width, 'stock_height': stock_height, 'quill': quill,
            'axis_x': -0.055 + stock_length / 2, 'axis_height': 0.097,
            'start': -stock_length / 2 + 0.029, 'end': stock_length / 2 - 0.018,
            'joints': {'rotary_tailstock': tailstock, 'rotary_quill': quill,
                       'rotary_handwheel': -quill / 0.001 * 2 * math.pi,
                       'rotary_jaw_0': stock_height / 2 - 0.018, 'rotary_jaw_2': stock_height / 2 - 0.018,
                       'rotary_jaw_1': stock_width / 2 - 0.018, 'rotary_jaw_3': stock_width / 2 - 0.018}}
