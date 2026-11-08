"""eidoblend.fabrication.feed_path: 2.5D process geometry and feed timing, metres and seconds (feed_path.js, MIT).

    from eidoblend.fabrication import FeedPath
    path = FeedPath([{'position': (0, 0, 0.03), 'type': 'rapid'},
                     {'position': (0.01, 0, 0.018), 'type': 'cut', 'feed': 0.001},
                     {'position': (0.03, 0, 0.018), 'type': 'cut'}], feed=0.012, rapid=0.10, acceleration=0.3)
    s = path.sample(1.5)          # time, position, tangent, velocity, acceleration, speed, type, index,
                                  # segment_distance, distance, volume, done (a dict that also reads as attributes)

Points are Blender coordinates, Z up: (x, y, height). Each move has a type, 'rapid', 'cut' or 'extrude', and an
optional feed (m/s) that wins over the path's. Corners between moves of one type are blended into arcs within
blend_tolerance (none when it is 0, and never between a plunge and horizontal cutting); the speed along the path is a
trapezoid per segment, limited by 0.6 * acceleration and continuous where the direction is. extrude moves meter
bead_area * length of material into volume.
"""

from __future__ import annotations

import math

from ._axes import Rec

UP = 2          # the vertical axis in Blender's coordinates (three's was 1)


def _clamp(v, a, b):
    return max(a, min(b, v))


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    return _mul(a, 1.0 / _length(a))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _rotate(p, n, a):
    """Rodrigues: p turned by angle a about the unit axis n."""
    return _add(_add(_mul(p, math.cos(a)), _mul(_cross(n, p), math.sin(a))), _mul(n, _dot(n, p) * (1 - math.cos(a))))


def _ok(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


class FeedPath:
    def __init__(self, points, feed=0.012, rapid=0.10, acceleration=0.3, blend_tolerance=0.000025, bead_area=0.0):
        points = list(points)
        if len(points) < 2:
            raise ValueError('A process path needs at least two points')
        if (not all(_ok(v) and v > 0 for v in (feed, rapid, acceleration)) or not (_ok(blend_tolerance) and blend_tolerance >= 0)
                or not (_ok(bead_area) and bead_area >= 0)):
            raise ValueError('Invalid feed settings')
        nodes = []
        for p in points:
            pos = p['position']
            if len(pos) != 3 or not all(_ok(float(v)) for v in pos):
                raise ValueError('Invalid tool coordinate')
            nodes.append(dict(p, position=(float(pos[0]), float(pos[1]), float(pos[2]))))
        self.acceleration = acceleration
        self.bead_area = bead_area
        self.blend_tolerance = blend_tolerance
        raw = []
        for i in range(1, len(nodes)):
            d = _sub(nodes[i]['position'], nodes[i - 1]['position'])
            l = _length(d)
            if l < 1e-10:
                continue
            typ = nodes[i].get('type') or 'cut'
            if typ not in ('cut', 'rapid', 'extrude'):
                raise ValueError('Unsupported process mode')
            rate = nodes[i].get('feed')
            if rate is None:
                rate = rapid if typ == 'rapid' else feed
            if not (_ok(rate) and rate > 0):
                raise ValueError('Invalid segment feed')
            raw.append(Rec(a=nodes[i - 1]['position'], b=nodes[i]['position'], length=l, d=_mul(d, 1 / l), type=typ, feed=rate))
        if not raw:
            raise ValueError('Path has zero length')
        joins = [None] * (len(raw) - 1)
        for i in range(len(joins)):
            a, b = raw[i], raw[i + 1]
            c = _clamp(_dot(a.d, b.d), -1, 1)
            angle = math.acos(c)
            if a.type != b.type or angle < 1e-5 or angle > math.pi - .001 or blend_tolerance == 0:
                continue
            if a.type == 'cut' and abs(a.d[UP]) + abs(b.d[UP]) > 1e-8:
                continue                                     # a plunge ends before horizontal cutting
            radius = blend_tolerance / (1 / math.cos(angle / 2) - 1)
            trim = min(radius * math.tan(angle / 2), a.length * .35, b.length * .35)
            r = trim / math.tan(angle / 2)
            n = _unit(_cross(a.d, b.d))
            start = _sub(a.b, _mul(a.d, trim))
            end = _add(a.b, _mul(b.d, trim))
            center = _add(start, _mul(_cross(n, a.d), r))
            joins[i] = Rec(kind='arc', a=start, b=end, center=center, normal=n, angle=angle, radius=r, length=r * angle,
                           type=a.type, feed=min(a.feed, b.feed, math.sqrt(acceleration * .8 * r)),
                           entry_direction=a.d, exit_direction=b.d)
        self.segments = []
        for i, r in enumerate(raw):
            a = joins[i - 1].b if i > 0 and joins[i - 1] is not None else r.a
            b = joins[i].a if i < len(joins) and joins[i] is not None else r.b
            l = _length(_sub(b, a))
            if l > 1e-10:
                self.segments.append(Rec(r, kind='line', a=a, b=b, length=l, entry_direction=r.d, exit_direction=r.d))
            if i < len(joins) and joins[i] is not None:
                self.segments.append(joins[i])
        s = self.segments
        n = len(s)
        velocity = [0.0] * (n + 1)
        tangent_a = acceleration * .6
        for i in range(1, n):
            if s[i - 1].type == s[i].type and _dot(s[i - 1].exit_direction, s[i].entry_direction) > 1 - 1e-6:
                velocity[i] = min(s[i - 1].feed, s[i].feed)
        for i in range(1, n + 1):
            velocity[i] = min(velocity[i], math.sqrt(velocity[i - 1] ** 2 + 2 * tangent_a * s[i - 1].length))
        for i in range(n - 1, -1, -1):
            velocity[i] = min(velocity[i], math.sqrt(velocity[i + 1] ** 2 + 2 * tangent_a * s[i].length))
        time = distance = volume = 0.0
        for i in range(n):
            g = s[i]
            v0, v1 = velocity[i], velocity[i + 1]
            peak = min(g.feed, math.sqrt(tangent_a * g.length + (v0 * v0 + v1 * v1) / 2))
            ta = (peak - v0) / tangent_a
            td = (peak - v1) / tangent_a
            da = (v0 + peak) * ta / 2
            dd = (v1 + peak) * td / 2
            tc = max(0.0, (g.length - da - dd) / peak)
            g.update(t0=time, t1=time + ta + tc + td, v0=v0, v1=v1, peak=peak, ta=ta, td=td, tc=tc, da=da,
                     acceleration=tangent_a, distance0=distance, volume0=volume)
            time = g.t1
            distance += g.length
            if g.type == 'extrude':
                volume += g.length * bead_area
        self.duration = time
        self.length = distance
        self.volume = volume
        self._t1 = [g.t1 for g in s]

    def segment_at(self, t):
        lo, hi = 0, len(self.segments) - 1
        t1 = self._t1
        while lo < hi:
            m = (lo + hi) >> 1
            if t1[m] < t:
                lo = m + 1
            else:
                hi = m
        return lo

    def sample(self, seconds):
        t = _clamp(seconds, 0, self.duration)
        index = self.segment_at(t)
        g = self.segments[index]
        dt = t - g.t0
        if dt < g.ta:
            v = g.v0 + g.acceleration * dt
            s = g.v0 * dt + g.acceleration * dt * dt / 2
            at = g.acceleration
        elif dt < g.ta + g.tc:
            v = g.peak
            s = g.da + g.peak * (dt - g.ta)
            at = 0.0
        else:
            u = dt - g.ta - g.tc
            v = g.peak - g.acceleration * u
            s = g.da + g.peak * g.tc + g.peak * u - g.acceleration * u * u / 2
            at = -g.acceleration
        s = _clamp(s, 0, g.length)
        v = max(0.0, v)
        normal_acceleration = (0.0, 0.0, 0.0)
        if g.kind == 'line':
            position = _add(g.a, _mul(g.d, s))
            tangent = g.d
        else:
            a = g.angle * s / g.length
            radial = _rotate(_sub(g.a, g.center), g.normal, a)
            position = _add(g.center, radial)
            tangent = _rotate(g.entry_direction, g.normal, a)
            normal_acceleration = _mul(_unit(radial), -v * v / g.radius)
        if seconds < 0 or seconds >= self.duration:
            v = 0.0
            at = 0.0
            normal_acceleration = (0.0, 0.0, 0.0)
        return Rec(time=t, position=position, tangent=tangent, velocity=_mul(tangent, v),
                   acceleration=_add(_mul(tangent, at), normal_acceleration), speed=v, type=g.type, index=index,
                   segment_distance=s, distance=g.distance0 + s,
                   volume=g.volume0 + (s * self.bead_area if g.type == 'extrude' else 0.0), done=seconds >= self.duration)

    def walk(self, start_time, end_time, step, visit):
        """Visit (previous, next, type) sample pairs at most `step` metres apart from start_time to end_time."""
        if end_time < start_time:
            raise ValueError('Reset the process before rewinding')
        start = _clamp(start_time, 0, self.duration)
        end = _clamp(end_time, 0, self.duration)
        for i in range(self.segment_at(start), self.segment_at(end) + 1):
            g = self.segments[i]
            a = max(start, g.t0)
            b = min(end, g.t1)
            if b < a:
                continue
            first = self.sample(a)
            last = self.sample(b)
            count = max(1, math.ceil(max(0.0, last.segment_distance - first.segment_distance) / step),
                        math.ceil((b - a) * g.peak / step))
            previous = first
            for k in range(1, count + 1):
                nxt = self.sample(a + (b - a) * k / count)
                visit(previous, nxt, g.type)
                previous = nxt
