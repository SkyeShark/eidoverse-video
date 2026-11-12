"""eidoblend.sets.unknown_force.race: THE RACE, a reusable night-highway set, the Blender 5.2 EEVEE edition of
eidoverse/sets/unknown_force/race.js (made for the UNKNOWN FORCE music video; free to use in any piece).

An elevated wet highway at night between dark Sant'Elia towers. Two giant billboards face each other across the road,
$100,000,000 in gold (worship) and $20,000,000 in red (fear), both showing the same machine-god face. Marinetti's
1908-pattern racing car tears past with two goggled cosplayers, smashes through the roadworks that close the right
carriageway and flies off the broken end of the deck into the factory drain below, wheels in the air. A roadworks
floodlight throws the shadows of a marching column across a blank tower wall, and a boot comes down on the 1909
manifesto lying in a puddle. No files are loaded: every mesh, material and drawing is built here.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.sets.unknown_force import race as R
    race = R.build(scene)                                    # opts as race.js: reflect, sky, towers, rain, rain_count, lamp_i
    for f in range(f0, f1 + 1):                              # your clock -> frames; each call KEYS the frame
        t = (f - f0) / fps
        st = R.sequence(t, car_edge=6.0, march_on=(7.0, 7.6), heel_strike=9.0)   # the moving parts, on your times
        race.update(t, st, frame=f)
        race.key_camera(cam_obj, 'carTrack' if t < 5 else 'crashLow', t, st, frame=f)
    race.finish()                                            # the keys made LINEAR (CONSTANT for switches)
    race.apply_render_settings(scene)                        # AgX, ray tracing, the set's fog and bloom

What the JS module exports, and where it is here:
  LAYOUT           the set's dimensions, in race.js's own numbers (three's axes: +Y up, the road runs along +Z).
                   Everything this module returns is in Blender's axes: three (x, y, z) -> Blender (x, -z, y).
  build            -> Race: group (the set's root Empty), parts, update(t, state, frame), cams, cam_at, focal,
                   set_active, uniforms, key_camera, animate, make_cameras, finish, dispose.
  CUES, suggest    the music video's sung word times and its cut on the song clock: left out (this edition is the
                   set, not the video). Their moving parts keep their own time controls instead: ease_in (a screen
                   powering on, the march coming up), glance (the irises), car_drive (the run and the crash),
                   heel_stamp (the boot), and sequence(t, ...) that combines them into update()'s state.
The pure half (no Blender): race_state, crash_pose, car_path, debris_specs, heel_pose, cam_at_three, lamp_heads,
noise_atlas, night_env, and the canvases (march_canvas, radiator_number_canvas, Race.billboard_canvas,
Race.manifesto_canvas).

Lighting. race.js lit its set ANALYTICALLY inside its materials (two rows of sodium lamps, the bridge works' floods,
glints), because a three.js light costs every material in the film. EEVEE lights hundreds of real lights at once, so
here the street lamps, the works' floods and the heel's close key are real spot lights at the same heads, with the
same colours, intensities (three's candela I -> 4 pi I W), cones and cut-off distances; the deck's occlusion of the
lamps for anything below it, which race.js computed, is now a real shadow. Three things stay analytic, as in race.js,
because they are effects of one material: the march's floodlight and its projected column of shadows (towers only),
the ground's sparse sodium pools, and the glints in the rain and the splash (Geometry Nodes evaluate the lamp field
at each drop). The set's procedural night-city environment and race.js's hemisphere light become the world seen by
reflection and ambient rays; camera rays see the set's own night sky (the 2400 m dome's shader).

Animation. update(t, state, frame) sets everything for t and KEYS it at `frame`: transforms (the car on its path or
in its crash, the wheels, the debris, the boot), light energies, and the shader uniforms (one node group of keyed
values every material reads: race.js's U). The rain, the splash, the drain's waves and the scarf tails are Geometry
Nodes whose inputs are keyed the same way, so a saved .blend plays and renders any frame on its own.
"""
from __future__ import annotations

import math
import os

import numpy as np

try:                                                    # the cue sheet, the layout and the pure state math work in
    import bpy                                          # plain Python (the parity tests run them outside Blender)
    from mathutils import Matrix, Quaternion, Vector
except ImportError:                                     # pragma: no cover
    bpy = None

from ... import common

PI = math.pi
TAU = 2.0 * math.pi

# ============================================================================================ the set's numbers ===
D = {
    'ground': -6.0, 'deck_t': 1.4,
    'x_r': -2.2, 'x_l': 20.2, 'x_med': 9.6,                 # deck outer edges and median centre
    'z_far': -470, 'z_near': 270,
    'gap0': 92, 'gap1': 140,                                # the right half of the deck is missing between these
    'lanes': [3.6, 7.2, 11.85, 15.45],                      # lane centres (1, 2 = +Z carriageway; 3, 4 = -Z)
    'lamp_r': {'x': -1.9, 'head': [1.4, 10.15], 'dz': 34, 'z0': 0},
    'lamp_l': {'x': 19.9, 'head': [16.6, 10.15], 'dz': 34, 'z0': 17},
    'ch': {'z0': 108, 'z1': 130, 'b0': 113, 'b1': 125, 'bottom': -9.6, 'water': -9.05},     # the drain (along X)
    'bill_a': {'x': 33.5, 'z': -64, 'yaw': -0.96, 'w': 24, 'h': 16, 'y': 16},               # $100,000,000 gold
    'bill_b': {'x': -14.5, 'z': -64, 'yaw': 0.96, 'w': 24, 'h': 16, 'y': 16},               # $20,000,000 red
    'wall': {'x': -22, 'z0': -6, 'z1': 76, 'top': 66},                                      # the shadow wall (+X face)
    'flood': [18.6, 0.12, 40.0],                            # the roadworks floodlight that casts the march
    'march_x': 13.4,                                        # the (absent) column walks lane 3
    'heel': [-0.55, 0, 9.6],                                # the puddle where the boot comes down
    'works': {'taper0': [-1.3, 28], 'taper1': [8.7, 58], 'board': [0.2, 63.5], 'barrier': 67},
}
LAYOUT = D
"""race.js's LAYOUT in its own numbers: three's set-local metres, +Y up, the deck surface at y = 0, the performer's
mark (the 'singer' camera's subject, lit by the key, the back rim and the barrier's neon) at the origin facing +Z,
down the road. In Blender (x, y, z)_three sits at (x, -z, y): the mark faces -Y."""
CAR_LEN = 390.45                     # the car path's length (checked against the path in build)


def _ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _lin(t, a, b):
    return min(1.0, max(0.0, (t - a) / (b - a)))


# ================================================================================ the moving parts' own clocks ===
# update(t, state) drives every moving part from its state keys. race.js's suggest(t) set those keys from the music
# video's sung word times; here each moving part has its own time control instead, on any clock (seconds): give the
# times things happen and these return update()'s keys. sequence() combines them. Their formulas are suggest's,
# number for number (race_parity.py checks them against race.js run at the video's times).

def ease_in(t, t0, t1):
    """0 before t0, 1 after t1, a smoothstep between (race.js's ease(lin(t, t0, t1))): a screen powering on
    (bill_a, bill_b), the floodlight and the column coming up (march)."""
    if t1 <= t0:
        return 1.0 if t >= t0 else 0.0
    return _ease(_lin(t, t0, t1))


def glance(t, t0):
    """gaze for the screens' irises: from t0 they swing over to the other screen within a second and keep swinging
    (sin 1.3 (t - t0)), -1..1."""
    return math.sin(max(0.0, t - t0) * 1.3) * ease_in(t, t0, t0 + 1.0)


def car_drive(t, t_edge, speed=22.0):
    """The car on its own clock: it runs its path at `speed` (m/s; 22, the speed its crash is modelled at) so that its
    front wheels reach the broken edge at t_edge, waiting at the start of the path until it is due, then goes over the
    edge (crash 0..1 over 3 s: nose in at 0.437, on its back by 0.65, settled by 0.9). Returns update()'s car_t and
    crash (car_t rather than car_s, so a later car_t of yours still wins), and car_v when `speed` is not 22."""
    s = CAR_LEN - speed * (t_edge - t)
    st = {'car_t': min(1.0, max(0.0, s / CAR_LEN)), 'crash': 0.0}
    if t >= t_edge:
        st['crash'] = min(1.0, (t - t_edge) / CR['t_end'])
    elif speed != CR['v'] and 0.0 < s < CAR_LEN:
        st['car_v'] = float(speed)
    return st


def heel_stamp(t, t_strike):
    """The boot on its own clock (heel 0..1 over 2.2 s): it comes down from knee height, hovers, strikes the page at
    t_strike (heel 0.68), the toe slaps down, and it stays planted. 0 (no boot) until it starts, 1.5 s before."""
    return min(1.0, max(0.0, (t - t_strike) / HEEL['dur'] + HEEL['strike']))


def sequence(t, bill_a_on=None, bill_b_on=None, glance_from=None, car_edge=None, car_speed=22.0, march_on=None,
             heel_strike=None, **keys):
    """update()'s state at time t from the times things happen on your clock; every part is optional and keeps
    update()'s default when not given (the screens on, the car parked at the start of its path, no march, no boot):
      bill_a_on, bill_b_on  (t0, t1): that screen powers on (ease_in)
      glance_from           the irises start glancing across (glance)
      car_edge, car_speed   the car reaches the broken edge at car_edge and goes over (car_drive)
      march_on              (t0, t1): the floodlight and the marching shadows come up (ease_in)
      heel_strike           the boot's strike lands (heel_stamp)
    Any other update() key passes through as given (rain, wet, lamps, march_t, headlamps, back_rim, car ...)."""
    st = {}
    if bill_a_on is not None:
        st['bill_a'] = ease_in(t, *bill_a_on)
    if bill_b_on is not None:
        st['bill_b'] = ease_in(t, *bill_b_on)
    if glance_from is not None:
        st['gaze'] = glance(t, glance_from)
    if car_edge is not None:
        st.update(car_drive(t, car_edge, car_speed))
    if march_on is not None:
        st['march'] = ease_in(t, *march_on)
    if heel_strike is not None:
        st['heel'] = heel_stamp(t, heel_strike)
    st.update(keys)
    return st


# ======================================================================================== the set kit (pure) ===
# race.js's tiny helpers, three r184's geometry generators, its CatmullRomCurve3 and its Euler / quaternion maths,
# all in THREE's axes so the set ports number for number; meshes are converted to Blender's axes when they are made.
# bin.py builds with the same kit.

def lcg(seed):
    """race.js's rng: s = imul(s, 1664525) + 1013904223 (>>> 0), bit for bit; returns floats in [0, 1)."""
    s = [(int(seed) & 0xFFFFFFFF) or 1]

    def r():
        s[0] = (s[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        return s[0] / 4294967296.0
    return r


def srgb_to_linear(c):
    return c * 0.0773993808 if c < 0.04045 else (c * 0.9478672986 + 0.0521327014) ** 2.4


def lin_hex(h):
    """three's Color(hex) with colour management: an sRGB hex as linear (r, g, b)."""
    if isinstance(h, str):
        h = int(h.lstrip('#'), 16)
    return tuple(srgb_to_linear(((h >> s) & 255) / 255.0) for s in (16, 8, 0))


def to_blender(p):
    """A three (x, y, z) as Blender (x, -z, y)."""
    return (float(p[0]), -float(p[2]), float(p[1]))


def from_blender(p):
    return (float(p[0]), float(p[2]), -float(p[1]))


# ---------------------------------------------------------------------------------------------- quaternions --
def quat_euler(x, y, z, order='XYZ'):
    """three's Quaternion.setFromEuler -> (x, y, z, w)."""
    c1, c2, c3 = math.cos(x / 2), math.cos(y / 2), math.cos(z / 2)
    s1, s2, s3 = math.sin(x / 2), math.sin(y / 2), math.sin(z / 2)
    if order == 'XYZ':
        return (s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 + s1 * s2 * c3,
                c1 * c2 * c3 - s1 * s2 * s3)
    if order == 'YXZ':
        return (s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 - s1 * s2 * c3,
                c1 * c2 * c3 + s1 * s2 * s3)
    if order == 'ZXY':
        return (s1 * c2 * c3 - c1 * s2 * s3, c1 * s2 * c3 + s1 * c2 * s3, c1 * c2 * s3 + s1 * s2 * c3,
                c1 * c2 * c3 - s1 * s2 * s3)
    raise ValueError(order)


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (ax * bw + aw * bx + ay * bz - az * by, ay * bw + aw * by + az * bx - ax * bz,
            az * bw + aw * bz + ax * by - ay * bx, aw * bw - ax * bx - ay * by - az * bz)


def quat_axis_angle(axis, ang):
    s = math.sin(ang / 2)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(ang / 2))


def quat_unit_vectors(a, b):
    """three's Quaternion.setFromUnitVectors(a, b)."""
    r = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + 1
    if r < 1e-8:
        r = 0
        if abs(a[0]) > abs(a[2]):
            q = (-a[1], a[0], 0.0, r)
        else:
            q = (0.0, -a[2], a[1], r)
    else:
        q = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0], r)
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def qrot(q, v):
    """three's Vector3.applyQuaternion."""
    vx, vy, vz = v
    qx, qy, qz, qw = q
    tx, ty, tz = 2 * (qy * vz - qz * vy), 2 * (qz * vx - qx * vz), 2 * (qx * vy - qy * vx)
    return (vx + qw * tx + qy * tz - qz * ty, vy + qw * ty + qz * tx - qx * tz, vz + qw * tz + qx * ty - qy * tx)


def quat_to_blender(q):
    """A three quaternion (x, y, z, w) as a Blender (w, x, y, z) rotation."""
    return (q[3], q[0], -q[2], q[1])


def mat_quat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def compose(pos=(0, 0, 0), q=(0, 0, 0, 1), s=(1, 1, 1)):
    """three's Matrix4.compose as a row-major 4x4."""
    m = np.eye(4)
    m[:3, :3] = mat_quat(q) * np.asarray(s, float)[None, :]
    m[:3, 3] = pos
    return m


def M4(x=0, y=0, z=0, rx=0, ry=0, rz=0, sx=1, sy=1, sz=1):
    """race.js's M4: compose(position, Euler(rx, ry, rz) 'XYZ', scale)."""
    return compose((x, y, z), quat_euler(rx, ry, rz), (sx, sy, sz))


def m_basis(xa, ya, za, pos=(0, 0, 0), s=1.0):
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2] = np.asarray(xa) * s, np.asarray(ya) * s, np.asarray(za) * s
    m[:3, 3] = pos
    return m


def _norm(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ------------------------------------------------------------------------------------- CatmullRomCurve3 ------
class CatmullRom:
    """three's CatmullRomCurve3 (centripetal by default), with its arc-length table of 200 divisions."""

    def __init__(self, pts, closed=False, curve_type='centripetal', tension=0.5, divisions=200):
        self.pts = [np.asarray(p, float) for p in pts]
        self.closed, self.type, self.tension, self.div = closed, curve_type, tension, divisions
        self._lengths = None

    def point(self, t):
        P, l = self.pts, len(self.pts)
        p = (l - (0 if self.closed else 1)) * t
        ip = math.floor(p)
        w = p - ip
        if self.closed:
            ip += 0 if ip > 0 else (math.floor(abs(ip) / l) + 1) * l
        elif w == 0 and ip == l - 1:
            ip, w = l - 2, 1.0
        p0 = P[(ip - 1) % l] if (self.closed or ip > 0) else (P[0] - P[1]) + P[0]
        p1, p2 = P[ip % l], P[(ip + 1) % l]
        p3 = P[(ip + 2) % l] if (self.closed or ip + 2 < l) else (P[l - 1] - P[l - 2]) + P[l - 1]
        out = np.zeros(3)
        if self.type in ('centripetal', 'chordal'):
            pw = 0.5 if self.type == 'chordal' else 0.25
            dt0 = float(np.sum((p0 - p1) ** 2)) ** pw
            dt1 = float(np.sum((p1 - p2) ** 2)) ** pw
            dt2 = float(np.sum((p2 - p3) ** 2)) ** pw
            if dt1 < 1e-4:
                dt1 = 1.0
            if dt0 < 1e-4:
                dt0 = dt1
            if dt2 < 1e-4:
                dt2 = dt1
            for k in range(3):
                x0, x1, x2, x3 = p0[k], p1[k], p2[k], p3[k]
                t1 = (x1 - x0) / dt0 - (x2 - x0) / (dt0 + dt1) + (x2 - x1) / dt1
                t2 = (x2 - x1) / dt1 - (x3 - x1) / (dt1 + dt2) + (x3 - x2) / dt2
                out[k] = _cubic(x1, x2, t1 * dt1, t2 * dt1, w)
        else:
            for k in range(3):
                x0, x1, x2, x3 = p0[k], p1[k], p2[k], p3[k]
                out[k] = _cubic(x1, x2, self.tension * (x2 - x0), self.tension * (x3 - x1), w)
        return out

    def lengths(self):
        if self._lengths is None:
            c, last, s = [0.0], self.point(0), 0.0
            for i in range(1, self.div + 1):
                cur = self.point(i / self.div)
                s += float(np.linalg.norm(cur - last))
                c.append(s)
                last = cur
            self._lengths = c
        return self._lengths

    def length(self):
        return self.lengths()[-1]

    def u_to_t(self, u):
        al = self.lengths()
        il = len(al)
        target = u * al[-1]
        lo, hi = 0, il - 1
        while lo <= hi:
            i = int(math.floor(lo + (hi - lo) / 2))
            c = al[i] - target
            if c < 0:
                lo = i + 1
            elif c > 0:
                hi = i - 1
            else:
                hi = i
                break
        i = hi
        if al[i] == target:
            return i / (il - 1)
        return (i + (target - al[i]) / (al[i + 1] - al[i])) / (il - 1)

    def point_at(self, u):
        return self.point(self.u_to_t(u))

    def tangent(self, t):
        t1, t2 = max(0.0, t - 0.0001), min(1.0, t + 0.0001)
        return _norm(self.point(t2) - self.point(t1))

    def tangent_at(self, u):
        return self.tangent(self.u_to_t(u))

    def frenet(self, segs, closed):
        """three's Curve.computeFrenetFrames -> (tangents, normals, binormals)."""
        T = [self.tangent_at(i / segs) for i in range(segs + 1)]
        t0 = np.abs(T[0])
        mn, nrm = 1e300, None
        if t0[0] <= mn:
            mn, nrm = t0[0], np.array([1.0, 0, 0])
        if t0[1] <= mn:
            mn, nrm = t0[1], np.array([0, 1.0, 0])
        if t0[2] <= mn:
            nrm = np.array([0, 0, 1.0])
        v = _norm(np.cross(T[0], nrm))
        N = [np.cross(T[0], v)]
        B = [np.cross(T[0], N[0])]
        for i in range(1, segs + 1):
            n = N[i - 1].copy()
            v = np.cross(T[i - 1], T[i])
            if np.linalg.norm(v) > 2.220446049250313e-16:
                v = _norm(v)
                th = math.acos(min(1.0, max(-1.0, float(np.dot(T[i - 1], T[i])))))
                n = _rot_axis(n, v, th)
            N.append(n)
            B.append(np.cross(T[i], n))
        if closed:
            th = math.acos(min(1.0, max(-1.0, float(np.dot(N[0], N[segs]))))) / segs
            if np.dot(T[0], np.cross(N[0], N[segs])) > 0:
                th = -th
            for i in range(1, segs + 1):
                N[i] = _rot_axis(N[i], T[i], th * i)
                B[i] = np.cross(T[i], N[i])
        return T, N, B


def _cubic(x0, x1, t0, t1, w):
    c2 = -3 * x0 + 3 * x1 - 2 * t0 - t1
    c3 = 2 * x0 - 2 * x1 + t0 + t1
    return x0 + t0 * w + c2 * w * w + c3 * w * w * w


def _rot_axis(v, axis, ang):
    """three's Matrix4.makeRotationAxis applied to v."""
    c, s = math.cos(ang), math.sin(ang)
    t = 1 - c
    x, y, z = axis
    tx, ty = t * x, t * y
    m = np.array([[tx * x + c, tx * y - s * z, tx * z + s * y],
                  [tx * y + s * z, ty * y + c, ty * z - s * x],
                  [tx * z - s * y, ty * z + s * x, t * z * z + c]])
    return m @ v


# ------------------------------------------------------------------------------------------- geometries ------
class Geo:
    """A three BufferGeometry: P (n,3), N (n,3), UV (n,2), I (m,3) triangle indices; three's axes."""

    def __init__(self, P, N, UV, I):
        self.P = np.asarray(P, float).reshape(-1, 3)
        self.N = np.asarray(N, float).reshape(-1, 3)
        self.UV = np.asarray(UV, float).reshape(-1, 2)
        self.I = np.asarray(I, np.int64).reshape(-1, 3)

    def transformed(self, m):
        if m is None:
            return self
        m = np.asarray(m, float)
        P = self.P @ m[:3, :3].T + m[:3, 3]
        nm = np.linalg.inv(m[:3, :3]).T
        N = self.N @ nm.T
        ln = np.linalg.norm(N, axis=1, keepdims=True)
        N = np.where(ln > 0, N / np.maximum(ln, 1e-30), N)
        return Geo(P, N, self.UV, self.I)

    def compute_normals(self):
        """three's computeVertexNormals: area-weighted, per vertex (a non-indexed geometry comes out flat)."""
        N = np.zeros_like(self.P)
        a, b, c = self.P[self.I[:, 0]], self.P[self.I[:, 1]], self.P[self.I[:, 2]]
        fn = np.cross(c - b, a - b)
        for k in range(3):
            np.add.at(N, self.I[:, k], fn)
        ln = np.linalg.norm(N, axis=1, keepdims=True)
        self.N = np.where(ln > 0, N / np.maximum(ln, 1e-30), N)
        return self

    def non_indexed(self):
        idx = self.I.reshape(-1)
        return Geo(self.P[idx], self.N[idx], self.UV[idx], np.arange(len(idx)).reshape(-1, 3))


def plane_geo(w=1, h=1, ws=1, hs=1):
    gx, gy = int(ws), int(hs)
    xs = np.arange(gx + 1) * (w / gx) - w / 2
    ys = np.arange(gy + 1) * (h / gy) - h / 2
    X, Y = np.meshgrid(xs, ys)
    P = np.stack([X.ravel(), -Y.ravel(), np.zeros(X.size)], 1)
    iy, ix = np.meshgrid(np.arange(gy + 1), np.arange(gx + 1), indexing='ij')
    UV = np.stack([(ix / gx).ravel(), (1 - iy / gy).ravel()], 1)
    I = []
    g1 = gx + 1
    for y in range(gy):
        for x in range(gx):
            a, b, c, d = x + g1 * y, x + g1 * (y + 1), x + 1 + g1 * (y + 1), x + 1 + g1 * y
            I += [(a, b, d), (b, c, d)]
    return Geo(P, np.tile([0, 0, 1.0], (len(P), 1)), UV, I)


def box_geo(w=1, h=1, d=1, ws=1, hs=1, ds=1):
    Ps, Ns, UVs, Is = [], [], [], []
    nv = [0]

    def plane(u, v, wax, udir, vdir, width, height, depth, gx, gy):
        sw, sh = width / gx, height / gy
        g1 = gx + 1
        for iy in range(gy + 1):
            y = iy * sh - height / 2
            for ix in range(gx + 1):
                x = ix * sw - width / 2
                vec = [0.0, 0.0, 0.0]
                vec[u], vec[v], vec[wax] = x * udir, y * vdir, depth / 2
                Ps.append(vec)
                n = [0.0, 0.0, 0.0]
                n[wax] = 1.0 if depth > 0 else -1.0
                Ns.append(n)
                UVs.append((ix / gx, 1 - iy / gy))
        for iy in range(gy):
            for ix in range(gx):
                a = nv[0] + ix + g1 * iy
                b = nv[0] + ix + g1 * (iy + 1)
                c = nv[0] + ix + 1 + g1 * (iy + 1)
                dd = nv[0] + ix + 1 + g1 * iy
                Is.extend([(a, b, dd), (b, c, dd)])
        nv[0] += (gx + 1) * (gy + 1)

    X, Y, Z = 0, 1, 2
    plane(Z, Y, X, -1, -1, d, h, w, ds, hs)
    plane(Z, Y, X, 1, -1, d, h, -w, ds, hs)
    plane(X, Z, Y, 1, 1, w, d, h, ws, ds)
    plane(X, Z, Y, 1, -1, w, d, -h, ws, ds)
    plane(X, Y, Z, 1, -1, w, h, d, ws, hs)
    plane(X, Y, Z, -1, -1, w, h, -d, ws, hs)
    return Geo(Ps, Ns, UVs, Is)


def cylinder_geo(rt=1, rb=1, h=1, rs=32, hs=1, open_ended=False, th0=0.0, thl=TAU):
    Ps, Ns, UVs, Is = [], [], [], []
    hh = h / 2
    slope = (rb - rt) / h
    rows = []
    idx = 0
    for y in range(hs + 1):
        v = y / hs
        r = v * (rb - rt) + rt
        row = []
        for x in range(rs + 1):
            u = x / rs
            th = u * thl + th0
            st, ct = math.sin(th), math.cos(th)
            Ps.append((r * st, -v * h + hh, r * ct))
            n = np.array([st, slope, ct])
            Ns.append(n / np.linalg.norm(n))
            UVs.append((u, 1 - v))
            row.append(idx)
            idx += 1
        rows.append(row)
    for x in range(rs):
        for y in range(hs):
            a, b, c, d = rows[y][x], rows[y + 1][x], rows[y + 1][x + 1], rows[y][x + 1]
            if rt > 0 or y != 0:
                Is.append((a, b, d))
            if rb > 0 or y != hs - 1:
                Is.append((b, c, d))

    def cap(top):
        nonlocal idx
        r = rt if top else rb
        sign = 1 if top else -1
        c0 = idx
        for _ in range(rs):
            Ps.append((0, hh * sign, 0))
            Ns.append((0, sign, 0))
            UVs.append((0.5, 0.5))
            idx += 1
        c1 = idx
        for x in range(rs + 1):
            th = x / rs * thl + th0
            st, ct = math.sin(th), math.cos(th)
            Ps.append((r * st, hh * sign, r * ct))
            Ns.append((0, sign, 0))
            UVs.append((ct * 0.5 + 0.5, st * 0.5 * sign + 0.5))
            idx += 1
        for x in range(rs):
            c, i = c0 + x, c1 + x
            Is.append((i, i + 1, c) if top else (i + 1, i, c))

    if not open_ended:
        if rt > 0:
            cap(True)
        if rb > 0:
            cap(False)
    return Geo(Ps, Ns, UVs, Is)


def cone_geo(r=1, h=1, rs=32, hs=1, open_ended=False, th0=0.0, thl=TAU):
    return cylinder_geo(0, r, h, rs, hs, open_ended, th0, thl)


def sphere_geo(r=1, ws=32, hs=16, phi0=0.0, phil=TAU, th0=0.0, thl=PI):
    ws, hs = max(3, int(ws)), max(2, int(hs))
    th_end = min(th0 + thl, PI)
    Ps, Ns, UVs, Is, grid = [], [], [], [], []
    idx = 0
    for iy in range(hs + 1):
        row = []
        v = iy / hs
        uo = 0.5 / ws if (iy == 0 and th0 == 0) else (-0.5 / ws if (iy == hs and th_end == PI) else 0)
        for ix in range(ws + 1):
            u = ix / ws
            x = -r * math.cos(phi0 + u * phil) * math.sin(th0 + v * thl)
            y = r * math.cos(th0 + v * thl)
            z = r * math.sin(phi0 + u * phil) * math.sin(th0 + v * thl)
            Ps.append((x, y, z))
            n = np.array([x, y, z])
            ln = np.linalg.norm(n)
            Ns.append(n / ln if ln > 0 else n)
            UVs.append((u + uo, 1 - v))
            row.append(idx)
            idx += 1
        grid.append(row)
    for iy in range(hs):
        for ix in range(ws):
            a, b, c, d = grid[iy][ix + 1], grid[iy][ix], grid[iy + 1][ix], grid[iy + 1][ix + 1]
            if iy != 0 or th0 > 0:
                Is.append((a, b, d))
            if iy != hs - 1 or th_end < PI:
                Is.append((b, c, d))
    return Geo(Ps, Ns, UVs, Is)


def torus_geo(r=1, tube=0.4, rs=12, ts=48, arc=TAU):
    Ps, Ns, UVs, Is = [], [], [], []
    for j in range(rs + 1):
        for i in range(ts + 1):
            u = i / ts * arc
            v = j / rs * TAU
            x = (r + tube * math.cos(v)) * math.cos(u)
            y = (r + tube * math.cos(v)) * math.sin(u)
            z = tube * math.sin(v)
            Ps.append((x, y, z))
            n = np.array([x - r * math.cos(u), y - r * math.sin(u), z])
            Ns.append(n / np.linalg.norm(n))
            UVs.append((i / ts, j / rs))
    for j in range(1, rs + 1):
        for i in range(1, ts + 1):
            a = (ts + 1) * j + i - 1
            b = (ts + 1) * (j - 1) + i - 1
            c = (ts + 1) * (j - 1) + i
            d = (ts + 1) * j + i
            Is += [(a, b, d), (b, c, d)]
    return Geo(Ps, Ns, UVs, Is)


def circle_geo(r=1, segs=32, th0=0.0, thl=TAU):
    segs = max(3, segs)
    Ps, UVs = [(0, 0, 0)], [(0.5, 0.5)]
    for s in range(segs + 1):
        a = th0 + s / segs * thl
        x, y = r * math.cos(a), r * math.sin(a)
        Ps.append((x, y, 0))
        UVs.append(((x / r + 1) / 2, (y / r + 1) / 2))
    Is = [(i, i + 1, 0) for i in range(1, segs + 1)]
    return Geo(Ps, np.tile([0, 0, 1.0], (len(Ps), 1)), UVs, Is)


def tube_geo(curve, ts=64, radius=1, rad=8, closed=False):
    T, N, B = curve.frenet(ts, closed)
    Ps, Ns, UVs, Is = [], [], [], []

    def seg(i):
        P = curve.point_at(i / ts)
        for j in range(rad + 1):
            v = j / rad * TAU
            s, c = math.sin(v), -math.cos(v)
            n = _norm(c * N[i] + s * B[i])
            Ns.append(n)
            Ps.append(P + radius * n)

    for i in range(ts):
        seg(i)
    seg(ts if not closed else 0)
    for i in range(ts + 1):
        for j in range(rad + 1):
            UVs.append((i / ts, j / rad))
    for j in range(1, ts + 1):
        for i in range(1, rad + 1):
            a = (rad + 1) * (j - 1) + (i - 1)
            b = (rad + 1) * j + (i - 1)
            c = (rad + 1) * j + i
            d = (rad + 1) * (j - 1) + i
            Is += [(a, b, d), (b, c, d)]
    return Geo(Ps, Ns, UVs, Is)


def lathe_geo(points, segs=12, phi0=0.0, phil=TAU):
    pts = [np.asarray(p, float) for p in points]
    init = []
    prev = None
    for j in range(len(pts)):
        if j == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
            n = np.array([dy, -dx, 0.0])
            prev = n.copy()
            init.append(_norm(n))
        elif j == len(pts) - 1:
            init.append(prev.copy())
        else:
            dx, dy = pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]
            n = np.array([dy, -dx, 0.0])
            cur = n.copy()
            init.append(_norm(n + prev))
            prev = cur
    Ps, Ns, UVs, Is = [], [], [], []
    for i in range(segs + 1):
        phi = phi0 + i / segs * phil
        s, c = math.sin(phi), math.cos(phi)
        for j, p in enumerate(pts):
            Ps.append((p[0] * s, p[1], p[0] * c))
            UVs.append((i / segs, j / (len(pts) - 1)))
            Ns.append((init[j][0] * s, init[j][1], init[j][0] * c))
    for i in range(segs):
        for j in range(len(pts) - 1):
            base = j + i * len(pts)
            a, b, c, d = base, base + len(pts), base + len(pts) + 1, base + 1
            Is += [(a, b, d), (c, d, b)]
    return Geo(Ps, Ns, UVs, Is)


def icosahedron_geo(r=1, detail=0):
    """three's IcosahedronGeometry (PolyhedronGeometry): non-indexed, subdivided, on the sphere, its uvs."""
    t = (1 + math.sqrt(5)) / 2
    V = np.array([-1, t, 0, 1, t, 0, -1, -t, 0, 1, -t, 0, 0, -1, t, 0, 1, t, 0, -1, -t, 0, 1, -t, t, 0, -1, t, 0, 1,
                  -t, 0, -1, -t, 0, 1], float).reshape(-1, 3)
    F = [0, 11, 5, 0, 5, 1, 0, 1, 7, 0, 7, 10, 0, 10, 11, 1, 5, 9, 5, 11, 4, 11, 10, 2, 10, 7, 6, 7, 1, 8, 3, 9, 4, 3,
         4, 2, 3, 2, 6, 3, 6, 8, 3, 8, 9, 4, 9, 5, 2, 4, 11, 6, 2, 10, 8, 6, 7, 9, 8, 1]
    out = []
    cols = detail + 1
    for k in range(0, len(F), 3):
        a, b, c = V[F[k]], V[F[k + 1]], V[F[k + 2]]
        v = []
        for i in range(cols + 1):
            aj = a + (c - a) * (i / cols)
            bj = b + (c - b) * (i / cols)
            rows = cols - i
            v.append([aj if (j == 0 and i == cols) else aj + (bj - aj) * (j / rows) for j in range(rows + 1)])
        for i in range(cols):
            for j in range(2 * (cols - i) - 1):
                kk = j // 2
                if j % 2 == 0:
                    out += [v[i][kk + 1], v[i + 1][kk], v[i][kk]]
                else:
                    out += [v[i][kk + 1], v[i + 1][kk + 1], v[i + 1][kk]]
    P = np.array(out)
    P = P / np.linalg.norm(P, axis=1, keepdims=True) * r
    n = len(P)
    return Geo(P, P / r, np.zeros((n, 2)), np.arange(n).reshape(-1, 3))


# ------------------------------------------------------------------------------------ shapes and extrusion --
class Shape:
    """A THREE.Shape / Path: moveTo, lineTo, quadraticCurveTo, closePath; holes."""

    def __init__(self, pts=None):
        self.segs, self.holes, self._cur = [], [], None
        if pts:
            self.move_to(*pts[0])
            for p in pts[1:]:
                self.line_to(*p)

    def move_to(self, x, y):
        self._cur = (float(x), float(y))
        self._start = self._cur
        return self

    def line_to(self, x, y):
        self.segs.append(('L', self._cur, (float(x), float(y))))
        self._cur = (float(x), float(y))
        return self

    def quadratic_curve_to(self, cx, cy, x, y):
        self.segs.append(('Q', self._cur, (float(cx), float(cy)), (float(x), float(y))))
        self._cur = (float(x), float(y))
        return self

    def close_path(self):
        if self._cur != self._start:
            self.line_to(*self._start)
        return self

    def points(self, divisions=12):
        """three's Path.getPoints: line curves give their end points, curves `divisions` steps; no consecutive
        duplicates."""
        out = []
        for s in self.segs:
            if s[0] == 'L':
                pts = [s[1], s[2]]
            else:
                p0, c, p1 = s[1], s[2], s[3]
                pts = []
                for i in range(divisions + 1):
                    t = i / divisions
                    u = 1 - t
                    pts.append((u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0],
                                u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]))
            for p in pts:
                if out and abs(out[-1][0] - p[0]) < 1e-12 and abs(out[-1][1] - p[1]) < 1e-12:
                    continue
                out.append(p)
        return out


def _area2(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        p, q = pts[i - 1], pts[i]
        a += p[0] * q[1] - q[0] * p[1]
    return a * 0.5


def _merge_overlapping(pts):
    out = list(pts)
    i = 1
    prev = out[0]
    while i <= len(out):
        ci = i % len(out)
        cur = out[ci]
        dx, dy = cur[0] - prev[0], cur[1] - prev[1]
        sc = max(abs(cur[0]), abs(cur[1]), abs(prev[0]), abs(prev[1]))
        if dx * dx + dy * dy <= 1e-20 * sc * sc:
            out.pop(ci)
            continue
        prev = cur
        i += 1
    return out


def _bevel_vec(p, prv, nxt):
    vpx, vpy = p[0] - prv[0], p[1] - prv[1]
    vnx, vny = nxt[0] - p[0], nxt[1] - p[1]
    vpl2 = vpx * vpx + vpy * vpy
    col = vpx * vny - vpy * vnx
    if abs(col) > 2.220446049250313e-16:
        vpl, vnl = math.sqrt(vpl2), math.sqrt(vnx * vnx + vny * vny)
        psx, psy = prv[0] - vpy / vpl, prv[1] + vpx / vpl
        nsx, nsy = nxt[0] - vny / vnl, nxt[1] + vnx / vnl
        sf = ((nsx - psx) * vny - (nsy - psy) * vnx) / (vpx * vny - vpy * vnx)
        tx, ty = psx + vpx * sf - p[0], psy + vpy * sf - p[1]
        tl2 = tx * tx + ty * ty
        if tl2 <= 2:
            return (tx, ty)
        shrink = math.sqrt(tl2 / 2)
    else:
        same = False
        if vpx > 2.220446049250313e-16:
            same = vnx > 2.220446049250313e-16
        elif vpx < -2.220446049250313e-16:
            same = vnx < -2.220446049250313e-16
        else:
            same = math.copysign(1, vpy) == math.copysign(1, vny)
        if same:
            tx, ty, shrink = -vpy, vpx, math.sqrt(vpl2)
        else:
            tx, ty, shrink = vpx, vpy, math.sqrt(vpl2 / 2)
    return (tx / shrink, ty / shrink)


def extrude_geo(shape, depth=1.0, steps=1, bevel=False, bevel_thickness=0.2, bevel_size=None, bevel_offset=0.0,
                bevel_segments=3, curve_segments=12):
    """three's ExtrudeGeometry (straight extrusion along +Z, optional bevel); non-indexed, flat normals."""
    if bevel_size is None:
        bevel_size = bevel_thickness - 0.1
    if not bevel:
        bevel_segments, bevel_thickness, bevel_size, bevel_offset = 0, 0.0, 0.0, 0.0
    verts = shape.points(curve_segments)
    holes = [h.points(curve_segments) for h in shape.holes]
    if _area2(verts) >= 0:                      # three: reverse a counter-clockwise outline, then clockwise holes
        verts = verts[::-1]
        holes = [h[::-1] if _area2(h) < 0 else h for h in holes]
    verts = _merge_overlapping(verts)
    holes = [_merge_overlapping(h) for h in holes]
    from mathutils.geometry import tessellate_polygon
    tris = tessellate_polygon([[(p[0], p[1], 0.0) for p in verts]] + [[(p[0], p[1], 0.0) for p in h] for h in holes])
    allv = list(verts) + [p for h in holes for p in h]
    faces = []
    for t in tris:
        a, b, c = (allv[k] for k in t)
        ar = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        faces.append(tuple(t) if ar > 0 else (t[0], t[2], t[1]))      # counter-clockwise, as earcut returns them
    contour = verts
    cmov = [_bevel_vec(contour[i], contour[i - 1], contour[(i + 1) % len(contour)]) for i in range(len(contour))]
    hmov = [[_bevel_vec(h[i], h[i - 1], h[(i + 1) % len(h)]) for i in range(len(h))] for h in holes]
    vmov = cmov + [m for hm in hmov for m in hm]
    vlen = len(allv)
    pos = []

    def ring(bs, z):
        for i, p in enumerate(contour):
            pos.append((p[0] + cmov[i][0] * bs, p[1] + cmov[i][1] * bs, z))
        for h, hm in zip(holes, hmov):
            for i, p in enumerate(h):
                pos.append((p[0] + hm[i][0] * bs, p[1] + hm[i][1] * bs, z))

    for b in range(bevel_segments):
        t = b / bevel_segments
        ring(bevel_size * math.sin(t * PI / 2) + bevel_offset, -bevel_thickness * math.cos(t * PI / 2))
    bs = bevel_size + bevel_offset
    for s in range(0, steps + 1):
        for i in range(vlen):
            p = allv[i]
            pos.append((p[0] + vmov[i][0] * bs, p[1] + vmov[i][1] * bs, depth / steps * s))
    for b in range(bevel_segments - 1, -1, -1):
        t = b / bevel_segments
        ring(bevel_size * math.sin(t * PI / 2) + bevel_offset, depth + bevel_thickness * math.cos(t * PI / 2))
    out = []
    top = vlen * (steps + bevel_segments * 2)
    for f in faces:
        out += [pos[f[2]], pos[f[1]], pos[f[0]]]
    for f in faces:
        out += [pos[f[0] + top], pos[f[1] + top], pos[f[2] + top]]
    layers = steps + bevel_segments * 2

    def walls(cont, off):
        nonlocal out
        for i in range(len(cont) - 1, -1, -1):
            j, k = i, (i - 1 if i - 1 >= 0 else len(cont) - 1)
            for s in range(layers):
                a, b = off + j + vlen * s, off + k + vlen * s
                c, d = off + k + vlen * (s + 1), off + j + vlen * (s + 1)
                out += [pos[a], pos[b], pos[d], pos[b], pos[c], pos[d]]

    walls(contour, 0)
    off = len(contour)
    for h in holes:
        walls(h, off)
        off += len(h)
    P = np.array(out, float)
    n = len(P)
    g = Geo(P, np.zeros((n, 3)), np.zeros((n, 2)), np.arange(n).reshape(-1, 3))
    return g.compute_normals()


# ------------------------------------------------------------------------------------------ GB accumulator --
class GB:
    """race.js's GB: merge many pieces into one geometry with position / normal / uv and a vec4 'aux' per piece."""

    def __init__(self):
        self.parts = []
        self.v = 0

    def add(self, geo, m=None, aux=(0, 0, 0, 0), uv_fn=None):
        g = geo.transformed(m)
        UV = g.UV
        if uv_fn is not None:
            UV = np.array([uv_fn(p, n, k) for k, (p, n) in enumerate(zip(g.P, g.N))], float).reshape(-1, 2)
        A = np.tile(np.asarray(aux, float), (len(g.P), 1))
        self.parts.append((g.P, g.N, UV, A, g.I + self.v))
        self.v += len(g.P)
        return self

    def quad(self, p0, p1, p2, p3, aux=(0, 0, 0, 0), uv0=(0, 0), uv_scale=1.0):
        p = [np.asarray(q, float) for q in (p0, p1, p2, p3)]
        e1, e2 = p[1] - p[0], p[3] - p[0]
        n = _norm(np.cross(e1, e2))
        L1, L2 = np.linalg.norm(e1) * uv_scale, np.linalg.norm(e2) * uv_scale
        UV = [(uv0[0], uv0[1]), (uv0[0] + L1, uv0[1]), (uv0[0] + L1, uv0[1] + L2), (uv0[0], uv0[1] + L2)]
        I = np.array([(0, 1, 2), (0, 2, 3)]) + self.v
        self.parts.append((np.array(p), np.tile(n, (4, 1)), np.array(UV, float), np.tile(np.asarray(aux, float), (4, 1)), I))
        self.v += 4
        return self

    def merge(self, other, offset=(0, 0, 0)):
        """Append another GB's pieces, translated (race.js copies a drum's or a barricade's arrays into wG)."""
        base = 0
        for P, N, UV, A, I in other.parts:
            self.parts.append((P + np.asarray(offset, float), N, UV, A, I - base + self.v))
            base += len(P)
            self.v += len(P)
        return self

    def build(self):
        if not self.parts:
            return None
        P = np.concatenate([p[0] for p in self.parts])
        N = np.concatenate([p[1] for p in self.parts])
        UV = np.concatenate([p[2] for p in self.parts])
        A = np.concatenate([p[3] for p in self.parts])
        I = np.concatenate([p[4] for p in self.parts])
        g = Geo(P, N, UV, I)
        g.A = A
        return g


def box_quads(gb, x0, y0, z0, x1, y1, z1, aux, top=True, bottom=False, sides=(1, 1, 1, 1)):
    """race.js's boxQuads: a box from min/max corners, uv in metres per face."""
    p = lambda x, y, z: (x, y, z)
    if sides[0]:
        gb.quad(p(x1, y0, z1), p(x1, y0, z0), p(x1, y1, z0), p(x1, y1, z1), aux, (-z1, y0))
    if sides[1]:
        gb.quad(p(x0, y0, z0), p(x0, y0, z1), p(x0, y1, z1), p(x0, y1, z0), aux, (z0, y0))
    if sides[2]:
        gb.quad(p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1), aux, (x0, y0))
    if sides[3]:
        gb.quad(p(x1, y0, z0), p(x0, y0, z0), p(x0, y1, z0), p(x1, y1, z0), aux, (-x1, y0))
    if top:
        gb.quad(p(x0, y1, z1), p(x1, y1, z1), p(x1, y1, z0), p(x0, y1, z0), aux, (x0, -z1))
    if bottom:
        gb.quad(p(x0, y0, z0), p(x1, y0, z0), p(x1, y0, z1), p(x0, y0, z1), aux, (x0, z0))


# ======================================================================================= the set kit (Blender) ===

def make_collection(name, parent=None):
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col


def mesh_object(name, g, mat=None, parent=None, collection=None, aux=True, flat=False, uv_name='UVMap', attrs=None):
    """One Blender mesh object from a three-axes Geo (or a GB's build()): positions and normals converted to
    Blender's axes, per-vertex custom normals, the uv layer and the GB's 'aux' (FLOAT_COLOR, point domain)."""
    if g is None:
        return None
    P = g.P[:, [0, 2, 1]] * np.array([1.0, -1.0, 1.0])
    N = g.N[:, [0, 2, 1]] * np.array([1.0, -1.0, 1.0])
    I = g.I
    keep = (I[:, 0] != I[:, 1]) & (I[:, 1] != I[:, 2]) & (I[:, 0] != I[:, 2])
    I = I[keep]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(P))
    me.vertices.foreach_set('co', P.astype(np.float32).ravel())
    me.loops.add(I.size)
    me.loops.foreach_set('vertex_index', I.astype(np.int32).ravel())
    me.polygons.add(len(I))
    me.polygons.foreach_set('loop_start', (np.arange(len(I)) * 3).astype(np.int32))
    me.update(calc_edges=True)
    uv = me.uv_layers.new(name=uv_name)
    uv.data.foreach_set('uv', g.UV[I.ravel()].astype(np.float32).ravel())
    if aux and getattr(g, 'A', None) is not None:
        a = me.attributes.new('aux', 'FLOAT_COLOR', 'POINT')
        a.data.foreach_set('color', g.A.astype(np.float32).ravel())
    for nm, (kind, dom, arr) in (attrs or {}).items():
        a = me.attributes.new(nm, kind, dom)
        a.data.foreach_set('vector' if kind == 'FLOAT_VECTOR' else 'color' if kind == 'FLOAT_COLOR' else 'value',
                           np.asarray(arr, np.float32).ravel())
    if flat:
        me.shade_flat()
    else:
        me.shade_smooth()
        ln = np.linalg.norm(N, axis=1, keepdims=True)
        Nn = np.where(ln > 0, N / np.maximum(ln, 1e-30), np.array([0, 0, 1.0]))
        me.normals_split_custom_set_from_vertices(Nn.astype(np.float32).tolist())
    if mat is not None:
        for m in (mat if isinstance(mat, (list, tuple)) else [mat]):
            me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, parent=None, collection=None, pos=(0, 0, 0), q=None):
    """An Empty at a three-axes position (and three quaternion), parented."""
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.3
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.parent = parent
    ob.rotation_mode = 'QUATERNION'
    ob.location = to_blender(pos)
    if q is not None:
        ob.rotation_quaternion = quat_to_blender(q)
    return ob


def image_from_array(name, arr, colorspace='sRGB', top_first=True, pack=True, alpha_mode=None, float_buffer=False):
    """A packed bpy Image from (h, w, 3|4) floats in 0..1 (or uint8). top_first: row 0 is the image's top (a canvas);
    else row 0 is the bottom (three's DataTexture). alpha_mode: STRAIGHT for colour with coverage alpha; a Non-Color
    image is data (independent channels, as three's DataTexture held them) and defaults to CHANNEL_PACKED.
    float_buffer: give it to an image that Geometry Nodes sample. Sampling a byte image, Geometry Nodes make a float
    copy that is premultiplied (RGB x A) in the session that built the set and straight once the .blend is reopened,
    so the drain's waves came out different in the two; a float image is read as stored in both."""
    if alpha_mode is None:
        alpha_mode = 'CHANNEL_PACKED' if colorspace == 'Non-Color' else 'STRAIGHT'
    a = np.asarray(arr)
    if a.dtype == np.uint8:
        a = a.astype(np.float32) / 255.0
    h, w = a.shape[:2]
    if a.shape[2] == 3:
        a = np.concatenate([a, np.ones((h, w, 1), np.float32)], 2)
    if top_first:
        a = a[::-1]
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=float_buffer)
    img.colorspace_settings.name = colorspace
    img.alpha_mode = alpha_mode
    img.pixels.foreach_set(np.ascontiguousarray(a, np.float32).ravel())
    if pack:
        img.pack()
    return img


# ------------------------------------------------------------------------------------------- node builder --
class V:
    """A value in a node graph: a socket that writes nodes when combined (+ - * /, .x .y .z)."""
    __slots__ = ('nb', 'out', 'vec')

    def __init__(self, nb, out, vec):
        self.nb, self.out, self.vec = nb, out, vec

    def __add__(self, o):
        return self.nb.op('ADD', self, o)

    def __radd__(self, o):
        return self.nb.op('ADD', o, self)

    def __sub__(self, o):
        return self.nb.op('SUBTRACT', self, o)

    def __rsub__(self, o):
        return self.nb.op('SUBTRACT', o, self)

    def __mul__(self, o):
        return self.nb.op('MULTIPLY', self, o)

    def __rmul__(self, o):
        return self.nb.op('MULTIPLY', o, self)

    def __truediv__(self, o):
        return self.nb.op('DIVIDE', self, o)

    def __rtruediv__(self, o):
        return self.nb.op('DIVIDE', o, self)

    def __neg__(self):
        return self.nb.op('MULTIPLY', self, -1.0)

    @property
    def x(self):
        return self.nb.sep(self)[0]

    @property
    def y(self):
        return self.nb.sep(self)[1]

    @property
    def z(self):
        return self.nb.sep(self)[2]


def _isnum(a):
    return isinstance(a, (int, float))


class NB:
    """Writes TSL-style math as nodes in a shader or Geometry Nodes tree (both share the Math, Vector Math, Map
    Range, Mix, Combine / Separate XYZ, White Noise nodes). Python numbers fold; tuples are constant vectors."""

    def __init__(self, tree):
        self.tree, self.nodes, self.links = tree, tree.nodes, tree.links
        self.gn = tree.bl_idname == 'GeometryNodeTree'
        self._sep, self._cache = {}, {}

    def node(self, idname, **kw):
        n = self.nodes.new(idname)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def put(self, a, sock):
        if isinstance(a, V):
            self.links.new(a.out, sock)
        elif _isnum(a):
            dv = sock.default_value
            try:
                n = len(dv)
            except TypeError:
                n = 0
            sock.default_value = (float(a),) * n if n else float(a)
        else:
            dv = sock.default_value
            a = tuple(float(c) for c in a)
            if len(dv) == 4 and len(a) == 3:
                a = a + (1.0,)
            sock.default_value = a

    def v(self, a):
        """A constant (number or 3-tuple) as a value node."""
        if isinstance(a, V):
            return a
        if _isnum(a):
            n = self.node('ShaderNodeValue')
            n.outputs[0].default_value = float(a)
            return V(self, n.outputs[0], False)
        return self.vec3(*a)

    def vec3(self, x, y, z):
        if _isnum(x) and _isnum(y) and _isnum(z):
            n = self.node('ShaderNodeCombineXYZ')
            for i, c in enumerate((x, y, z)):
                n.inputs[i].default_value = float(c)
            return V(self, n.outputs[0], True)
        n = self.node('ShaderNodeCombineXYZ')
        for i, c in enumerate((x, y, z)):
            self.put(c, n.inputs[i])
        return V(self, n.outputs[0], True)

    def vec2(self, x, y):
        return self.vec3(x, y, 0.0)

    def sep(self, a):
        k = a.out.as_pointer()
        if k not in self._sep:
            n = self.node('ShaderNodeSeparateXYZ')
            self.links.new(a.out, n.inputs[0])
            self._sep[k] = (V(self, n.outputs[0], False), V(self, n.outputs[1], False), V(self, n.outputs[2], False))
        return self._sep[k]

    def _isvec(self, a):
        return (isinstance(a, V) and a.vec) or (isinstance(a, (tuple, list)))

    def op(self, opn, a, b):
        if _isnum(a) and _isnum(b):
            return {'ADD': a + b, 'SUBTRACT': a - b, 'MULTIPLY': a * b, 'DIVIDE': a / b}[opn]
        if self._isvec(a) or self._isvec(b):
            n = self.node('ShaderNodeVectorMath', operation=opn)
            self.put(a, n.inputs[0])
            self.put(b, n.inputs[1])
            return V(self, n.outputs[0], True)
        n = self.node('ShaderNodeMath', operation=opn)
        self.put(a, n.inputs[0])
        self.put(b, n.inputs[1])
        return V(self, n.outputs[0], False)

    def math(self, opn, a, b=None, c=None):
        n = self.node('ShaderNodeMath', operation=opn)
        for i, x in enumerate((a, b, c)):
            if x is not None:
                self.put(x, n.inputs[i])
        return V(self, n.outputs[0], False)

    def vmath(self, opn, a, b=None, scalar=False):
        n = self.node('ShaderNodeVectorMath', operation=opn)
        self.put(a, n.inputs[0])
        if b is not None:
            self.put(b, n.inputs[1] if opn != 'SCALE' else n.inputs['Scale'])
        return V(self, n.outputs['Value'] if scalar else n.outputs['Vector'], not scalar)

    # unary / binary functions (vector-aware where Vector Math has them)
    def _u(self, fop, vop, a):
        if _isnum(a):
            return None
        return self.vmath(vop, a) if a.vec else self.math(fop, a)

    def sin(self, a):
        return math.sin(a) if _isnum(a) else self._u('SINE', 'SINE', a)

    def cos(self, a):
        return math.cos(a) if _isnum(a) else self._u('COSINE', 'COSINE', a)

    def abs(self, a):
        return abs(a) if _isnum(a) else self._u('ABSOLUTE', 'ABSOLUTE', a)

    def floor(self, a):
        return math.floor(a) if _isnum(a) else self._u('FLOOR', 'FLOOR', a)

    def fract(self, a):
        return a - math.floor(a) if _isnum(a) else self._u('FRACT', 'FRACTION', a)

    def sign(self, a):
        return self._u('SIGN', 'SIGN', a)

    def sqrt(self, a):
        return self.math('SQRT', a)

    def exp(self, a):
        return math.exp(a) if _isnum(a) else self.math('EXPONENT', a)

    def log2(self, a):
        return self.math('LOGARITHM', a, 2.0)

    def pow(self, a, b):
        if isinstance(a, V) and a.vec:
            return self.vmath('POWER', a, b if not _isnum(b) else (b, b, b))
        return self.math('POWER', a, b)

    def min(self, a, b):
        return self.vmath('MINIMUM', a, b) if (self._isvec(a) or self._isvec(b)) else self.math('MINIMUM', a, b)

    def max(self, a, b):
        return self.vmath('MAXIMUM', a, b) if (self._isvec(a) or self._isvec(b)) else self.math('MAXIMUM', a, b)

    def clamp(self, a, lo=0.0, hi=1.0):
        if isinstance(a, V) and a.vec:
            return self.min(self.max(a, (lo,) * 3), (hi,) * 3)
        n = self.node('ShaderNodeClamp')
        self.put(a, n.inputs[0])
        self.put(lo, n.inputs[1])
        self.put(hi, n.inputs[2])
        return V(self, n.outputs[0], False)

    def mod(self, a, b):
        """GLSL / TSL mod (floored)."""
        return self.math('FLOORED_MODULO', a, b)

    def atan2(self, y, x):
        return self.math('ARCTAN2', y, x)

    def smoothstep(self, e0, e1, x):
        """TSL smoothstep, either edge order (Map Range's smoothstep handles e0 > e1 as GLSL computes it)."""
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
        self.put(x, n.inputs[0])
        self.put(e0, n.inputs[1])
        self.put(e1, n.inputs[2])
        return V(self, n.outputs[0], False)

    def step(self, e, x):
        """TSL step(edge, x) = x >= edge."""
        return 1.0 - self.math('LESS_THAN', x, e)

    def mix(self, a, b, t):
        vec = self._isvec(a) or self._isvec(b)
        n = self.node('ShaderNodeMix', data_type='VECTOR' if vec else 'FLOAT')
        if vec:
            n.factor_mode = 'UNIFORM'
            self.put(t, n.inputs[0])
            self.put(a if not _isnum(a) else (a, a, a), n.inputs[4])
            self.put(b if not _isnum(b) else (b, b, b), n.inputs[5])
            return V(self, n.outputs[1], True)
        self.put(t, n.inputs[0])
        self.put(a, n.inputs[2])
        self.put(b, n.inputs[3])
        return V(self, n.outputs[0], False)

    def select(self, cond, a, b):
        """cond ? a : b, with cond a 0/1 value."""
        return self.mix(b, a, cond)

    def dot(self, a, b):
        return self.vmath('DOT_PRODUCT', a, b, scalar=True)

    def length(self, a):
        return self.vmath('LENGTH', a, scalar=True)

    def normalize(self, a):
        return self.vmath('NORMALIZE', a)

    def cross(self, a, b):
        return self.vmath('CROSS_PRODUCT', a, b)

    def hash(self, a):
        """A uniform [0, 1) value per integer seed (TSL's hash(); a White Noise of the seed: same role, other bits).
        TSL reads its seed as an integer (toUint) and every seed the sets hash is an integer by construction (a
        per-window or per-cell number), so the seed is rounded first: a per-face attribute interpolates to
        1000.0000001 here and 999.9999999 there, and White Noise of the raw float would speckle each window and
        shimmer whenever the camera or the set moves."""
        n = self.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
        self.put(math.floor(a + 0.5) if _isnum(a) else self.floor(a + 0.5), n.inputs['W'])
        return V(self, n.outputs['Value'], False)

    def tex(self, image, uv, interp='Linear', ext='REPEAT'):
        """(rgb, alpha) of an image at uv (a vector; z ignored)."""
        if self.gn:
            n = self.node('GeometryNodeImageTexture', interpolation=interp, extension=ext)
            n.inputs['Image'].default_value = image
            self.put(uv, n.inputs['Vector'])
        else:
            n = self.node('ShaderNodeTexImage', interpolation=interp, extension=ext)
            n.image = image
            self.put(uv, n.inputs['Vector'])
        return V(self, n.outputs['Color'], True), V(self, n.outputs['Alpha'], False)

    # inputs (shader trees)
    def texco(self, obj=None):
        k = ('texco', obj.name if obj is not None else None)
        if k not in self._cache:
            n = self.node('ShaderNodeTexCoord')
            if obj is not None:
                n.object = obj
            self._cache[k] = n
        return self._cache[k]

    def three(self, v):
        """A Blender-axes vector as three's axes: (x, y, z) -> (x, z, -y)."""
        return self.vec3(v.x, v.z, -v.y)

    def local3(self):
        """positionLocal: the object's own coordinates, in three's axes."""
        return self.three(V(self, self.texco().outputs['Object'], True))

    def set3(self, root):
        """race.js's PL: the position in the set root's space, three's axes."""
        return self.three(V(self, self.texco(root).outputs['Object'], True))

    def geom(self, name):
        k = ('geom',)
        if k not in self._cache:
            self._cache[k] = self.node('ShaderNodeNewGeometry')
        s = self._cache[k].outputs[name]
        return V(self, s, s.type == 'VECTOR')

    def normal3(self):
        return self.three(self.geom('Normal'))

    def uv(self, name=None):
        k = ('uv', name)
        if k not in self._cache:
            n = self.node('ShaderNodeUVMap')
            if name:
                n.uv_map = name
            self._cache[k] = V(self, n.outputs['UV'], True)
        return self._cache[k]

    def attr(self, name, kind='GEOMETRY', out='Fac'):
        k = ('attr', name, kind)
        if k not in self._cache:
            self._cache[k] = self.node('ShaderNodeAttribute', attribute_name=name, attribute_type=kind)
        s = self._cache[k].outputs[out]
        return V(self, s, out in ('Color', 'Vector'))

    def group(self, tree, key=None):
        k = ('group', tree.name)
        if k not in self._cache:
            n = self.node('ShaderNodeGroup')
            n.node_tree = tree
            self._cache[k] = n
        return self._cache[k]

    def bump(self, height, strength=1.0, distance=1.0, normal=None):
        """bumpN(h): a physically scaled bump of a height in metres (Blender's Bump: the height's screen
        derivatives, as race.js's surface-gradient method), a world-space normal for the BSDF."""
        n = self.node('ShaderNodeBump')
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = distance
        self.put(height, n.inputs['Height'])
        if normal is not None:
            self.put(normal, n.inputs['Normal'])
        return V(self, n.outputs['Normal'], True)


# ---------------------------------------------------------------------------------------- keyed uniforms --
class Uniforms:
    """race.js's U: one shader node group of keyed values that every material of the set reads. Scalars are Value
    nodes; vectors are three Values combined. set(name, value) writes, key(frame) keys what changed."""

    def __init__(self, name, spec):
        self.tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        t = self.tree
        out = t.nodes.new('NodeGroupOutput')
        self.spec, self.nodes, self.vals = dict(spec), {}, {}
        for k, v in spec.items():
            if isinstance(v, (tuple, list)):
                t.interface.new_socket(k, in_out='OUTPUT', socket_type='NodeSocketVector')
                c = t.nodes.new('ShaderNodeCombineXYZ')
                vs = []
                for i in range(3):
                    n = t.nodes.new('ShaderNodeValue')
                    n.name = n.label = f'{k}.{"xyz"[i]}'
                    n.outputs[0].default_value = float(v[i])
                    t.links.new(n.outputs[0], c.inputs[i])
                    vs.append(n)
                t.links.new(c.outputs[0], out.inputs[k])
                self.nodes[k] = vs
            else:
                t.interface.new_socket(k, in_out='OUTPUT', socket_type='NodeSocketFloat')
                n = t.nodes.new('ShaderNodeValue')
                n.name = n.label = k
                n.outputs[0].default_value = float(v)
                t.links.new(n.outputs[0], out.inputs[k])
                self.nodes[k] = [n]
            self.vals[k] = v

    def get(self, nb, k):
        """The uniform as a value in a material being built with nb."""
        g = nb.group(self.tree)
        s = g.outputs[k]
        return V(nb, s, isinstance(self.spec[k], (tuple, list)))

    def set(self, k, v):
        vs = v if isinstance(v, (tuple, list, np.ndarray)) else [v]
        for n, x in zip(self.nodes[k], vs):
            n.outputs[0].default_value = float(x)
        self.vals[k] = v

    def key(self, keyer, frame):
        for k, ns in self.nodes.items():
            for n in ns:
                keyer(n.outputs[0], 'default_value', frame)


class Keyer:
    """Keys a property at a frame; remembers each key's interpolation so finish() can give it (LINEAR by default,
    CONSTANT for switches; a property may mix both, as a light's level does where the set is parked). Pass the
    harness's ctx.key instead (it does the same at the end of the build)."""

    def __init__(self, fn=None):
        self.fn = fn
        self.ids = {}

    def __call__(self, target, path, frame, index=-1, interp='LINEAR'):
        if self.fn is not None:
            return self.fn(target, path, index=index, frame=frame, interpolation=interp)
        ok = target.keyframe_insert(path, index=index, frame=frame)
        idb = target.id_data
        try:
            full = target.path_from_id(path)
        except (ValueError, TypeError, AttributeError):
            full = path
        self.ids.setdefault(idb.as_pointer(), [idb, {}])[1].setdefault(full, {})[round(float(frame), 3)] = interp
        return ok

    def finish(self):
        """Every key this keyer made gets its interpolation (Blender 5.2's keyframe_insert makes BEZIER keys); a key on
        the same property that this keyer did not make takes the property's last one."""
        from bpy_extras import anim_utils
        n = 0
        for idb, paths in self.ids.values():
            ad = getattr(idb, 'animation_data', None)
            if ad is None or ad.action is None:
                continue
            try:
                cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
            except (AttributeError, TypeError, RuntimeError):
                cb = None
            if cb is None:
                continue
            for fc in cb.fcurves:
                per = paths.get(fc.data_path)
                if per is None:
                    continue
                last = next(reversed(per.values()))
                for kp in fc.keyframe_points:
                    kp.interpolation = per.get(round(kp.co.x, 3), last)
                    n += 1
        return n

    @staticmethod
    def keyed_before(target, path, frame):
        """True when target's `path` already has a key before `frame` (any index)."""
        from bpy_extras import anim_utils
        ad = getattr(target.id_data, 'animation_data', None)
        if ad is None or ad.action is None:
            return False
        try:
            cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
            full = target.path_from_id(path)
        except (AttributeError, TypeError, RuntimeError, ValueError):
            return False
        if cb is None:
            return False
        return any(fc.data_path == full and any(kp.co.x < frame - 1e-6 for kp in fc.keyframe_points) for fc in cb.fcurves)

    def step(self, target, path, value, frame):
        """A switch keyed as a step at `frame`: the property's value before the call is held up to it (keyed at
        frame - 1 when nothing earlier is keyed, else a lone key would hold the new value backwards too), and `value`
        holds from it on (CONSTANT) until the next key."""
        if not self.keyed_before(target, path, frame):
            self(target, path, frame - 1, interp='CONSTANT')
        setattr(target, path, value)
        self(target, path, frame, interp='CONSTANT')


# ------------------------------------------------------------------------------------------- materials --
def new_material(name, method='DITHERED'):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    m.surface_render_method = method
    return m


def principled(nb, color=None, rough=None, metal=None, normal=None, alpha=None, coat=None, coat_rough=None,
               sheen=None, sheen_tint=None, sheen_rough=None, ior=None, emission=None, spec=None):
    """A Principled BSDF fed by values (numbers, tuples or node values) -> its BSDF value."""
    b = nb.node('ShaderNodeBsdfPrincipled')
    for sock, v in (('Base Color', color), ('Roughness', rough), ('Metallic', metal), ('Normal', normal),
                    ('Alpha', alpha), ('Coat Weight', coat), ('Coat Roughness', coat_rough), ('Sheen Weight', sheen),
                    ('Sheen Tint', sheen_tint), ('Sheen Roughness', sheen_rough), ('IOR', ior),
                    ('Specular IOR Level', spec)):
        if v is not None:
            nb.put(v, b.inputs[sock])
    if emission is not None:
        nb.put(emission, b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = 1.0
    if normal is not None and coat is not None:
        nb.put(normal, b.inputs['Coat Normal'])
    return V(nb, b.outputs[0], False)


def output(nb, shader, volume=None, displacement=None):
    o = nb.node('ShaderNodeOutputMaterial')
    nb.links.new(shader.out, o.inputs['Surface'])
    if displacement is not None:
        nb.links.new(displacement.out, o.inputs['Displacement'])
    return o


def emission(nb, color, strength=1.0):
    e = nb.node('ShaderNodeEmission')
    nb.put(color, e.inputs['Color'])
    nb.put(strength, e.inputs['Strength'])
    return V(nb, e.outputs[0], False)


def add_shader(nb, a, b):
    n = nb.node('ShaderNodeAddShader')
    nb.links.new(a.out, n.inputs[0])
    nb.links.new(b.out, n.inputs[1])
    return V(nb, n.outputs[0], False)


def mix_shader(nb, fac, a, b):
    n = nb.node('ShaderNodeMixShader')
    nb.put(fac, n.inputs[0])
    nb.links.new(a.out, n.inputs[1])
    nb.links.new(b.out, n.inputs[2])
    return V(nb, n.outputs[0], False)


def transparent(nb, color=(1, 1, 1)):
    n = nb.node('ShaderNodeBsdfTransparent')
    nb.put(color, n.inputs['Color'])
    return V(nb, n.outputs[0], False)


def unlit(name, build, additive=False, alpha=None, method=None):
    """MeshBasicNodeMaterial: build(nb) -> colour (or (colour, opacity)); the colour is the radiance. additive:
    added over what is behind (AdditiveBlending); an opacity makes it alpha-blended."""
    m = new_material(name, method or ('BLENDED' if (additive or alpha) else 'DITHERED'))
    nb = NB(m.node_tree)
    res = build(nb)
    col, op = (res if isinstance(res, tuple) else (res, None))
    em = emission(nb, col)
    if additive:
        sh = add_shader(nb, em, transparent(nb))
    elif op is not None:
        sh = mix_shader(nb, op, transparent(nb), em)
    else:
        sh = em
    output(nb, sh)
    if additive or op is not None:
        m.use_transparent_shadow = True
    return m


def light(name, kind, color_lin, watts, pos=None, target=None, parent=None, collection=None, spot_half=None,
          blend=0.15, cutoff=None, radius=0.1, shadow=True):
    """A Blender light from a three light: kind 'POINT' / 'SPOT' / 'SUN'; watts = 4 pi I (cd) for point and spot
    (three's candela; Blender spots are specified as if they were points), the irradiance for a sun."""
    ld = bpy.data.lights.new(name, kind)
    ld.color = color_lin
    ld.energy = float(watts)
    ld.use_shadow = shadow
    if kind != 'SUN':
        ld.shadow_soft_size = radius
        if cutoff:
            ld.use_custom_distance = True
            ld.cutoff_distance = float(cutoff)
    else:
        ld.angle = 0.02
    if kind == 'SPOT' and spot_half is not None:
        ld.spot_size = min(PI, 2 * spot_half)
        ld.spot_blend = max(0.0, min(1.0, blend))
    ob = bpy.data.objects.new(name, ld)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.parent = parent
    if pos is not None:
        aim_light(ob, pos, target)
    return ob


def aim_light(ob, pos, target=None):
    """Place a light at a three position, its -Z axis toward a three target (spots and suns)."""
    p = Vector(to_blender(pos))
    ob.location = p
    ob.rotation_mode = 'QUATERNION'
    if target is not None:
        d = Vector(to_blender(target)) - p
        if d.length > 1e-9:
            ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')


def cd(i):
    """three candela -> Blender watts for a point or spot light."""
    return 4.0 * PI * float(i)


# ===================================================================================== the race's motion (pure) ===
# Everything update() moves, as closed-form functions of (t, state), in three's axes: the car on its path or in its
# crash, its body's bounce, the wheels, the debris it throws, the boot, the uniforms and the light levels.

CAR = {'wb': 2.76, 'track': 1.40, 'R': 0.45, 'com': (0, 0.62, 0.1), 'nose': (0, 0.55, 2.05), 'top': 1.32}
CR = {'v': 22, 't_imp': 1.31, 't_flip': 1.95, 't_end': 3.0, 'rest_y': D['ch']['bottom'] + (CAR['top'] - CAR['com'][1])}
HEEL = {'dur': 2.2, 'strike': 0.68}
WORK = [   # the bridge works' LED floods and the heel's close key: [position, aim, cos(inner), cos(outer), intensity]
    [(-0.8, 7.5, 86.0), (0.12, -0.62, 0.78), 0.80, 0.45, 1500.0, None],
    [(7.6, 7.5, 86.5), (-0.25, -0.66, 0.70), 0.80, 0.45, 1200.0, None],
    [(-6.0, -1.5, 133.5), (0.35, -0.42, -0.84), 0.82, 0.50, 900.0, None],
    [(D['heel'][0] - 1.9, 1.15, D['heel'][2] - 1.7), (0.69, -0.42, 0.59), 0.93, 0.78, 15.0, 'heel_key'],
]
LIGHT_BASE = {'key': 190.0, 'glow': 1300.0, 'rim': 0.8, 'hemi': 0.35, 'back_rim': 110.0, 'neon_fill': 7.0}


def car_path():
    """The car's path (lane 1 from z -300, drifting right through the works to the broken edge), three's axes."""
    return CatmullRom([(3.6, 0, -300), (3.6, 0, -120), (3.6, 0, 20), (3.1, 0, 50), (2.2, 0, 72),
                       (1.8, 0, D['gap0'] - CAR['wb'] / 2 - 0.2)], False, 'centripetal')


def crash_pose(tc, start, yaw0):
    """race.js crashPose: off the broken edge at 22 m/s; the nose drops, digs into the drain and the car goes over
    onto its back. -> {'com', 'pitch', 'roll', 'yaw', 'spin'} (Euler 'YXZ': pitch about x, yaw about y)."""
    com_l, nose_l = np.array(CAR['com'], float), np.array(CAR['nose'], float)
    x0, z0 = start[0], start[2] + com_l[2]

    def flight(t):
        return {'com': np.array([x0 - 0.25 * t, CAR['com'][1] - 4.905 * t * t, z0 + CR['v'] * t - 0.9 * t * t]),
                'pitch': 0.2 * min(1, t / 0.15) + 0.3 * max(0, t - 0.15), 'roll': 0.1 * t, 'yaw': yaw0 - 0.04 * t}

    out = {'spin': CR['v'] / CAR['R']}
    if tc <= CR['t_imp']:
        out.update(flight(max(0.0, tc)))
        return out
    f = flight(CR['t_imp'])
    q = quat_euler(f['pitch'], f['yaw'], f['roll'], 'YXZ')
    nose_rel = nose_l - com_l
    pivot0 = f['com'] + np.array(qrot(q, nose_rel))
    s = min(1.0, (tc - CR['t_imp']) / (CR['t_flip'] - CR['t_imp']))
    fs = 2 * s * s if s < 0.5 else 1 - (-2 * s + 2) ** 2 / 2
    pitch = f['pitch'] + (PI - f['pitch']) * fs
    roll = f['roll'] * (1 - fs) + 0.05 * fs
    yaw = f['yaw'] - 0.12 * fs
    q = quat_euler(pitch, yaw, roll, 'YXZ')
    pivot = pivot0 + np.array([0, 0, 0.7 * fs])
    com = pivot - np.array(qrot(q, nose_rel))
    settle = _ease((tc - CR['t_flip'] + 0.25) / 0.5)
    com[1] = com[1] * (1 - settle) + CR['rest_y'] * settle
    out.update({'com': com, 'pitch': pitch, 'roll': roll, 'yaw': yaw})
    if tc > CR['t_flip']:
        u = tc - CR['t_flip']
        out['pitch'] += 0.05 * math.exp(-3.5 * u) * math.sin(10 * u)
        out['roll'] += 0.035 * math.exp(-3.0 * u) * math.sin(8 * u + 1)
        out['com'][1] += 0.06 * math.exp(-4 * u) * math.sin(12 * u)
    out['spin'] = (CR['v'] / CAR['R']) * math.exp(-max(0.0, tc - CR['t_imp']) / 1.4)
    return out


def _path_at_z(path, z):
    lo, hi = 0.0, 1.0
    for _ in range(30):
        m = (lo + hi) / 2
        if path.point_at(m)[2] < z:
            lo = m
        else:
            hi = m
    return lo * path.length()


def drum_taper():
    """The works' drum taper: [(x, z, u, hit)] for its 12 drums (the car hits the ones within 0.95 m of x 3.5)."""
    t0, t1 = D['works']['taper0'], D['works']['taper1']
    out = []
    for k in range(12):
        u = k / 11
        x, z = t0[0] + (t1[0] - t0[0]) * u, t0[1] + (t1[1] - t0[1]) * u
        out.append((x, z, u, abs(x - 3.5) < 0.95))
    return out


def debris_specs(path):
    """What the car throws: the hit drums, then the hit barricade's legs and boards, each {'name', 's0', 'home', 'v',
    'w', 'r'} (s0: the car's path distance at the hit)."""
    out = []
    for k, (x, z, u, hit) in enumerate(drum_taper()):
        if hit:
            out.append({'name': f'drum{k}', 's0': _path_at_z(path, z), 'home': (x, 0, z), 'v': (1.8, 4.2, 13.0),
                        'w': (7.0, 2.0, 4.0), 'r': 0.35})
    bz = D['works']['barrier']
    for nm, v, w in (('barricade_legs', (-2.2, 3.0, 9.0), (3.0, 6.0, 1.0)), ('barricade_boards', (1.4, 5.5, 15.0), (9.0, 3.0, 6.0))):
        out.append({'name': nm, 's0': _path_at_z(path, bz), 'home': (2.3, 0, bz), 'v': v, 'w': w, 'r': 0.3})
    return out


def debris_pose(d, s_car, visible=True):
    """A debris piece's (position, Euler XYZ) at the car's path distance s_car (ballistic, a skid, off the edge)."""
    age = (s_car + 2.0 - d['s0']) / CR['v'] if visible else -1
    home = np.array(d['home'], float)
    if age <= 0:
        return home, (0.0, 0.0, 0.0)
    v, w = d['v'], d['w']
    t_land = (2 * v[1]) / 9.81
    ta = min(age, t_land)
    slide = (1 - math.exp(-(age - t_land) * 2.2)) / 2.2 if age > t_land else 0
    pos = home + np.array([v[0] * (ta + slide), v[1] * ta - 4.905 * ta * ta, v[2] * (ta + slide)])
    if pos[0] < D['x_r']:
        pos[1] = max(D['ground'], v[1] * age - 4.905 * age * age)
    st = ta + slide * 0.3
    rot = [w[0] * st, w[1] * st, w[2] * st]
    if age > t_land and pos[0] >= D['x_r']:
        k = min(1.0, (age - t_land) / 0.15)
        rot[0] = rot[0] * (1 - k) + (PI / 2) * k
        rot[2] *= 1 - k
        pos[1] = d['r'] * k
    return pos, tuple(rot)


def heel_pose(hv, t):
    """The stamp: (root y, pivot pitch) for heel 0..1 (descend, hover, slam at 0.68, the toe slaps down, planted)."""
    y, pitch = 0.0, 0.0
    if hv <= 0:
        return y, pitch
    eo = lambda x: 1 - (1 - x) * (1 - x)
    if hv < 0.45:
        k = eo(hv / 0.45)
        y, pitch = 0.95 + (0.22 - 0.95) * k, -0.35 + 0.1 * k
    elif hv < 0.62:
        k = (hv - 0.45) / 0.17
        y, pitch = 0.22 - 0.04 * k + 0.003 * math.sin(t * 38), -0.25 - 0.07 * k
    elif hv < HEEL['strike']:
        k = (hv - 0.62) / (HEEL['strike'] - 0.62)
        y, pitch = 0.18 * (1 - k * k), -0.32
    elif hv < 0.74:
        k = (hv - HEEL['strike']) / (0.74 - HEEL['strike'])
        y, pitch = 0.005 * math.sin(k * PI), -0.32 * (1 - k) * (1 - k)
    return y, pitch


def _mat_from(pos, q):
    return compose(pos, q, (1, 1, 1))


def race_state(t, state=None, path=None, debris=None, active=True):
    """Everything update(t, state) sets, as plain numbers in three's set-local axes:
    car {visible, pos, q, euler_yxz (pitch, yaw, roll), body_pos, body_rot (x, z)}, wheel_ang, debris [(pos, rot)],
    heel {visible, y, pitch}, beam {pos, target, w}, shadow {pos, yaw}, the uniforms U (race.js's names in snake_case)
    and the light levels (three intensities)."""
    state = state or {}
    path = path or car_path()
    debris = debris if debris is not None else debris_specs(path)
    L = path.length()
    out = {'U': {}}
    U = out['U']
    U['time'] = t
    U['rain'] = state.get('rain', 1)
    U['wet'] = state.get('wet', 1)
    U['lamps'] = state.get('lamps', 1)
    bb = state.get('billboards', 1)
    U['bill_a'] = state.get('bill_a', 1) * bb
    U['bill_b'] = state.get('bill_b', 1) * bb
    U['gaze'] = state.get('gaze', 0)
    U['march'] = state.get('march', 0)
    U['march_t'] = state.get('march_t', t)
    crash = min(1.0, max(0.0, state.get('crash', 0)))
    vis = state.get('car', True) is not False
    s_dist = state['car_s'] if state.get('car_s') is not None else state.get('car_t', 0) * L
    s_dist = min(L, max(0.0, s_dist))
    v = state['car_v'] if state.get('car_v') is not None else (CR['v'] if 0 < s_dist < L else 0)
    shutter = 1 / 120
    car = {'visible': vis}
    if crash <= 0:
        u = s_dist / L
        p, tg = path.point_at(u), path.tangent_at(u)
        yaw = math.atan2(tg[0], tg[2])
        car['pos'] = p
        car['euler_yxz'] = (0.0, yaw, 0.0)
        car['q'] = quat_euler(0, yaw, 0, 'YXZ')
        jm = ((s_dist % 36) + 36) % 36 - 3
        joint = math.exp(-jm * jm * 1.5)
        car['body_pos'] = (0.0, 0.004 * math.sin(t * 61) * (1 if v > 0 else 0.3) + 0.012 * joint, 0.0)
        car['body_rot'] = (-0.006 * min(1, v / 20) + 0.004 * joint, 0.003 * math.sin(t * 23))
        wheel_ang = s_dist / CAR['R']
        spin = v / CAR['R']
        out['shadow'] = {'pos': (p[0], 0.012, p[2]), 'yaw': yaw, 'visible': True}
        U['car_shadow'] = 1 if vis else 0
        U['crash_age'], U['flip_age'], U['steam'] = -10, -10, 0
        U['crash_p'] = (1.6, D['ch']['water'], 121)
        U['flip_p'] = (1.6, D['ch']['water'], 124)
        U['steam_p'] = (1.6, D['ch']['water'], 120)
    else:
        start, tg = path.point_at(1), path.tangent_at(1)
        tc = crash * CR['t_end']
        yaw1 = math.atan2(tg[0], tg[2])
        pose = crash_pose(tc, start, yaw1)
        q = quat_euler(pose['pitch'], pose['yaw'], pose['roll'], 'YXZ')
        car['q'] = q
        car['euler_yxz'] = (pose['pitch'], pose['yaw'], pose['roll'])
        car['pos'] = np.array(pose['com']) - np.array(qrot(q, CAR['com']))
        car['body_pos'] = (0.0, 0.0, 0.0)
        car['body_rot'] = (0.0, 0.0)
        w0, tau = CR['v'] / CAR['R'], 1.4
        wheel_ang = (L / CAR['R'] + w0 * min(tc, CR['t_imp'])
                     + (w0 * tau * (1 - math.exp(-(tc - CR['t_imp']) / tau)) if tc > CR['t_imp'] else 0))
        spin = pose['spin']
        U['car_shadow'] = max(0.0, 1 - tc * 6)
        out['shadow'] = {'pos': (start[0], 0.012, start[2] + CR['v'] * tc), 'yaw': yaw1, 'visible': True}
        f = crash_pose(CR['t_imp'], start, 0)
        U['crash_age'] = tc - CR['t_imp']
        U['crash_p'] = (f['com'][0], D['ch']['water'], f['com'][2] + 1.7)
        U['flip_age'] = tc - CR['t_flip']
        fp = crash_pose(CR['t_flip'], start, 0)['com']
        U['flip_p'] = (fp[0], D['ch']['water'], fp[2])
        U['steam'] = _ease((tc - CR['t_imp']) / 0.6)
        # race.js rotates the bonnet's middle by the quaternion crashPose(tFlip) leaves in its shared temporary: the
        # settled, upside-down pose (yaw0 = 0), so the steam rises where the bonnet comes to rest
        f_imp = crash_pose(CR['t_imp'], start, 0)
        q_flip = quat_euler(PI, f_imp['yaw'] - 0.12, 0.05, 'YXZ')
        sp = np.array(qrot(q_flip, (0, 0.9, 1.1))) + car['pos']
        U['steam_p'] = (sp[0], D['ch']['water'] + 0.1, sp[2])
    out['car'] = car
    out['wheel_ang'] = wheel_ang
    s_car = L + CR['v'] * crash * CR['t_end'] if crash > 0 else s_dist
    out['debris'] = [debris_pose(d, s_car, vis) for d in debris]
    U['headlamps'] = (state.get('headlamps', 1) * ((max(0.0, 1 - max(0.0, crash * CR['t_end'] - CR['t_imp']) / 0.35)
                                                    * (0.8 + 0.2 * math.sin(t * 90))) if crash > 0 else 1)
                      * (1 if vis else 0))
    # the beam: the body's (0, 0.97, 2.15) toward (0, 0.1, 14) in the set
    gm = _mat_from(car['pos'], car['q'])
    br = car['body_rot']
    bm = compose(car['body_pos'], quat_euler(br[0], 0, br[1]), (1, 1, 1))
    wm = gm @ bm
    out['beam'] = {'pos': (wm @ [0, 0.97, 2.15, 1])[:3], 'target': (wm @ [0, 0.1, 14.0, 1])[:3],
                   'i': 300 * U['headlamps'] * (1 if active else 0)}
    out['car_matrix'] = gm
    U['smear'] = min(2.5, spin * shutter)
    U['chain_run'] = (wheel_ang * 0.24) / 0.0254
    U['scarf_speed'] = max(0.15, 1 - crash * 1.4) if crash > 0 else min(1.0, v / 20)
    hv = min(1.0, max(0.0, state.get('heel', 0)))
    hy, hp = heel_pose(hv, t)
    out['heel'] = {'visible': hv > 0, 'y': hy, 'pitch': hp}
    U['heel_age'] = (hv - HEEL['strike']) * HEEL['dur'] if hv > 0 else -10
    U['heel_key'] = 1 if hv > 0 else 0
    U['works'] = 1
    on = 1 if active else 0
    lv = {'key': LIGHT_BASE['key'] * U['lamps'] * on, 'glow_a': LIGHT_BASE['glow'] * U['bill_a'] * on,
          'glow_b': LIGHT_BASE['glow'] * U['bill_b'] * on, 'neon_fill': LIGHT_BASE['neon_fill'] * on,
          'back_rim': LIGHT_BASE['back_rim'] * on * state.get('back_rim', 1) * (0.35 + 0.65 * max(U['bill_a'], U['bill_b'])),
          'rim': LIGHT_BASE['rim'] * on, 'hemi': LIGHT_BASE['hemi'] * on, 'beam': out['beam']['i']}
    out['lights'] = lv
    return out


# ------------------------------------------------------------------------------------------------ cameras --
CAMS = {
    'singer': {'pos': [1.35, 1.5, 5.4], 'target': [0.15, 1.38, 0.0], 'fov': 36},
    'billboards': {'pos': [8.2, 1.3, -20.0], 'target': [8.6, 13.5, -64.0], 'fov': 52},
    'billA': {'pos': [12.0, 7.2, -41.5], 'target': [33.5, 15.2, -64.0], 'fov': 34, 'roll': 0.05},
    'billB': {'pos': [7.0, 7.2, -41.5], 'target': [-14.5, 15.2, -64.0], 'fov': 34, 'roll': -0.05},
    'carPass': {'pos': [-0.9, 0.55, 12.0], 'target': [3.8, 1.0, -40.0], 'fov': 48},
    'carChase': {'pos': [6.4, 1.6, 30.0], 'target': [2.4, 0.4, 92.0], 'fov': 46},
    'crash': {'pos': [-17.0, -4.4, 104.5], 'target': [1.5, -4.6, 107.5], 'fov': 60, 'roll': 0.05},
    'crashLow': {'pos': [-7.5, -7.1, 112.6], 'target': [1.6, -6.4, 114.0], 'fov': 54, 'roll': -0.08},
    'carTrack': {'pos': [-1.4, 1.25, 1.0], 'target': [3.6, 0.85, 0.5], 'fov': 44, 'roll': 0.07},
    'shadows': {'pos': [12.0, 1.7, 6.0], 'target': [-22.0, 11.0, 40.0], 'fov': 52},
    'shadowsWide': {'pos': [3.4, 0.95, 9.0], 'target': [-22.0, 3.2, 39.0], 'fov': 56, 'roll': -0.03},
    'heel': {'pos': [-0.36, 0.13, 10.42], 'target': [-0.5, 0.2, 9.6], 'fov': 44, 'roll': 0.06},
    'heelTop': {'pos': [-0.18, 0.78, 10.12], 'target': [-0.6, 0.03, 9.62], 'fov': 42, 'roll': -0.12},
}
"""race.js's cams in its own numbers (three's set-local axes); Race.cams has them in Blender's."""
FOCAL = {
    'singer': [0.0, 1.45, 0.0], 'billboards': [9.6, 16.0, -64.0], 'billA': [D['bill_a']['x'], D['bill_a']['y'] + 2, D['bill_a']['z']],
    'billB': [D['bill_b']['x'], D['bill_b']['y'] + 2, D['bill_b']['z']], 'carPass': [3.6, 1.0, -30.0], 'carTrack': [3.6, 1.0, 40.0],
    'carChase': [2.0, 0.0, D['gap0']], 'crash': [1.6, -8.5, 121.0], 'crashLow': [1.6, -6.0, 112.0],
    'shadowsWide': [D['flood'][0], 0.6, D['flood'][2]], 'heelTop': [D['heel'][0], 0.0, D['heel'][2]],
    'shadows': [D['flood'][0], 0.6, D['flood'][2]], 'heel': [D['heel'][0] + 0.05, 0.75, D['heel'][2] - 0.2],
}


def cam_at_three(name, t, state, rs, path=None):
    """race.js camAt in three's axes: the moving cameras that follow the car (None when it has nothing)."""
    state = state or {}
    path = path or car_path()
    car = rs['car']
    if name == 'crashLow':
        if car['visible'] and state.get('crash', 0) > 0:
            tgt = (rs['car_matrix'] @ [0, 0.7, 0.3, 1])[:3]
        else:
            tgt = (1.6, -7.5, 116)
        return {'pos': [-7.5, -7.1, 112.6], 'target': [float(c) for c in tgt], 'fov': 54, 'roll': -0.08}
    if name not in ('carChase', 'carTrack', 'carSide', 'carFront', 'carRear') or not car['visible']:
        return None
    L = path.length()
    p = np.array(car['pos'], float)
    s = state['car_s'] if state.get('car_s') is not None else state.get('car_t', 0) * L
    tg = path.tangent_at(min(1.0, max(0.0, s / L)))
    yaw = math.atan2(tg[0], tg[2])
    q = quat_axis_angle((0, 1, 0), yaw)
    rot = lambda x, y, z: [float(c) for c in (np.array(qrot(q, (x, y, z))) + p)]
    if state.get('crash', 0) > 0:
        return None
    shake = lambda k: (math.sin(t * 31) * k, math.sin(t * 27 + 1) * k)
    if name == 'carChase':
        a, b = shake(0.015)
        return {'pos': rot(2.1 + a, 1.15 + b, -6.2), 'target': rot(-0.4, 0.75, 9.0), 'fov': 52, 'roll': -0.06}
    if name == 'carTrack':
        a, b = shake(0.01)
        return {'pos': rot(-5.0 + a, 1.25 + b, 0.7), 'target': rot(0, 0.85, 0.25), 'fov': 44, 'roll': 0.07}
    if name == 'carSide':
        return {'pos': rot(4.6, 1.05, 2.2), 'target': rot(0, 0.75, 0.2), 'fov': 34}
    if name == 'carFront':
        return {'pos': rot(1.6, 0.9, 5.5), 'target': rot(0, 0.85, 0.8), 'fov': 36}
    return {'pos': rot(-2.2, 1.6, -4.6), 'target': rot(0, 1.0, 0.0), 'fov': 38}


def lamp_heads():
    """The street lamps' heads (three's axes): [(x, y, z, row)], row 'R' (the +Z carriageway's side) or 'L'."""
    out = []
    dz = D['lamp_r']['dz']
    z = D['z_far'] + 10
    while z <= D['gap0']:
        zz = math.floor(z / dz + 0.5) * dz
        if D['z_far'] + 10 <= zz <= D['gap0']:
            out.append((D['lamp_r']['x'] + 3.3, 10.15, zz, 'R'))
        z += dz
    k = math.ceil((D['z_far'] + 10 - D['lamp_l']['z0']) / D['lamp_l']['dz'])
    while True:
        z = D['lamp_l']['z0'] + k * D['lamp_l']['dz']
        if z > D['z_near'] - 5:
            break
        out.append((D['lamp_l']['x'] - 3.3, 10.15, z, 'L'))
        k += 1
    return out


def noise_atlas():
    """race.js's 256^2 tiling value-noise atlas, bit for bit: R fbm (breakup), G ridged (cracks, streaks), B fine
    grain, A blotches. -> (256, 256, 4) uint8, rows bottom-up (three's DataTexture)."""
    N = 256
    cache = {}

    def lat(seed, P):
        k = (seed, P)
        if k not in cache:
            r = lcg(seed * 7919 + P)
            cache[k] = np.array([r() for _ in range(P * P)], np.float32).astype(np.float64)
        return cache[k]

    ys, xs = np.mgrid[0:N, 0:N].astype(np.float64)

    def vn(a, P, x, y):
        xi, yi = np.floor(x), np.floor(y)
        fx, fy = x - xi, y - yi
        sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        xi, yi = xi.astype(np.int64), yi.astype(np.int64)
        g = lambda i, j: a[((j % P) + P) % P * P + ((i % P) + P) % P]
        return (g(xi, yi) * (1 - sx) + g(xi + 1, yi) * sx) * (1 - sy) + (g(xi, yi + 1) * (1 - sx) + g(xi + 1, yi + 1) * sx) * sy

    def fbm(seed, base, octs):
        s, w, tot = 0.0, 0.5, 0.0
        for o in range(octs):
            P = base << o
            s = s + w * vn(lat(seed + o, P), P, (xs * P) / N, (ys * P) / N)
            tot += w
            w *= 0.5
        return s / tot

    c = lambda v: np.clip(np.floor(((v - 0.5) * 1.6 + 0.5) * 255 + 0.5), 0, 255).astype(np.uint8)
    out = np.zeros((N, N, 4), np.uint8)
    out[..., 0] = c(fbm(11, 4, 5))
    out[..., 1] = c(1 - np.abs(2 * fbm(23, 8, 4) - 1))
    out[..., 2] = c(fbm(37, 64, 2))
    out[..., 3] = c(fbm(51, 2, 4))
    return out


def night_env():
    """race.js's procedural night-city equirect (Uint8 sRGB, 512 x 256, rows bottom-up = nadir first): navy zenith,
    sodium haze at the horizon, a skyline of dark towers with lit windows and neon blooms, a dark wet ground."""
    W, H = 512, 256
    r = lcg(4242)
    sky = []
    h = 0.05
    for x in range(W):
        if r() < 0.12:
            h = 0.02 + r() ** 1.6 * 0.22
        sky.append(h)
    neon = []
    for _ in range(22):
        nx, ny, ns = r() * W, 0.02 + r() * 0.14, 2 + r() * 5
        neon.append((nx, ny, ns, (1.0, 0.25, 0.75) if r() < 0.5 else (0.15, 0.85, 1.0)))
    sky = np.array(sky)
    el = ((np.arange(H) + 0.5) / H - 0.5) * PI
    S = np.sin(el)[:, None] * np.ones((1, W))
    X = np.ones((H, 1)) * np.arange(W)[None, :]
    col = np.zeros((H, W, 3))
    up = S > 0
    k = np.where(up, np.abs(S) ** 0.45, 0)
    cl = np.maximum(0, np.sin(X * 0.05 + np.sin(X * 0.013) * 3) * 0.5 + 0.5) * np.exp(-S * 6) * 0.05
    for i, (a, b, cc) in enumerate(((0.075, 0.004, 0.9), (0.040, 0.006, 0.45), (0.045, 0.014, 0.35))):
        col[..., i] = np.where(up, a * (1 - k) + b * k + cl * cc, 0)
    kd = np.where(~up, np.abs(S) ** 0.6, 0)
    for i, (a, b) in enumerate(((0.035, 0.006), (0.020, 0.006), (0.018, 0.008))):
        col[..., i] = np.where(up, col[..., i], a * (1 - kd) + b * kd)
    # the random draws, in raster order: two per skyline pixel, one per pixel just below the horizon
    for y in range(H):
        s = math.sin(el[y])
        for x in range(W):
            if s > 0:
                if s < sky[x]:
                    lit = 1 if r() < 0.18 else 0
                    warm = r() < 0.6
                    col[y, x] = (0.008 + lit * (0.55 if warm else 0.25), 0.009 + lit * (0.32 if warm else 0.40),
                                 0.012 + lit * (0.16 if warm else 0.55))
            elif -s < 0.12 and r() < 0.02:
                col[y, x] = (0.5, 0.26, 0.09)
    for nx, ny, ns, nc in neon:
        dx = np.minimum(np.abs(X - nx), W - np.abs(X - nx))
        dy = (S - ny) * H / PI
        g = np.exp(-(dx * dx + dy * dy) / (ns * ns))
        for i in range(3):
            col[..., i] += nc[i] * g * 0.9
    v = np.clip(col, 0, 1)
    enc = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = np.floor(255 * np.clip(enc, 0, 1) + 0.5).astype(np.uint8)
    out[..., 3] = 255
    return out


def march_canvas():
    """race.js's march atlas, unblurred: the walk cycle of the absent column, 8 frames x 2 rows (rifles on the
    shoulder, then blank banners), white on black, 1024 x 512 -> float RGBA, row 0 at the top. Lockstep: frame f of
    either row is the same step."""
    from .bin_pages import Canvas2D
    FW, FH, NF = 128, 256, 8
    g = Canvas2D(FW * NF, FH * 2, ss=2)
    g.fillStyle = '#000'
    g.fillRect(0, 0, FW * NF, FH * 2)
    g.fillStyle = '#fff'
    g.strokeStyle = '#fff'
    g.lineCap = 'round'
    g.lineJoin = 'round'

    def seg(ax, ay, bx, by, w):
        g.lineWidth = w
        g.beginPath()
        g.moveTo(ax, ay)
        g.lineTo(bx, by)
        g.stroke()

    def fig(ox, oy, f, kind):
        ph = (f / NF) * TAU
        bob = -3 * abs(math.sin(ph))
        hip_x, hip_y = ox + 64, oy + 128 + bob
        lean = 0.08
        sh_x, sh_y = hip_x - math.sin(lean) * 62, hip_y - 62
        for s, far in ((0, 1), (PI, 0)):
            a = math.sin(ph + s) * 0.48
            k = max(0.0, math.sin(ph + s + 0.9)) * 0.75
            kx, ky = hip_x - math.sin(a) * 54, hip_y + math.cos(a) * 54
            fx, fy = kx - math.sin(a - k) * 56, ky + math.cos(a - k) * 56
            g.globalAlpha = 0.92 if far else 1
            seg(hip_x, hip_y, kx, ky, 24)
            seg(hip_x - 4, hip_y + 18, (hip_x + kx) / 2 + 6, (hip_y + ky) / 2, 30)
            seg(kx, ky, fx, fy, 17)
            seg(fx + 6, fy + 2, fx - 18, fy + 4, 9)
            g.globalAlpha = 1
        g.beginPath()
        g.moveTo(hip_x - 16, hip_y + 6)
        g.lineTo(hip_x + 14, hip_y + 4)
        g.lineTo(sh_x + 15, sh_y - 2)
        g.lineTo(sh_x - 17, sh_y + 2)
        g.closePath()
        g.fill()
        hx, hy = sh_x - 4, sh_y - 24
        g.beginPath()
        g.arc(hx, hy, 13, 0, TAU)
        g.fill()
        seg(hx - 2, sh_y - 2, hx, hy + 8, 12)
        if kind == 0:
            g.fillRect(hx - 14, hy - 17, 26, 9)
            seg(hx - 13, hy - 8, hx - 25, hy - 6, 4)
        else:
            g.fillRect(hx - 11, hy - 21, 21, 12)
            seg(hx + 9, hy - 19, hx + 15, hy - 6, 3)
        aa = -math.sin(ph) * 0.5
        ex, ey = sh_x - math.sin(aa) * 34, sh_y + 6 + math.cos(aa) * 34
        seg(sh_x, sh_y + 6, ex, ey, 11)
        seg(ex, ey, ex - math.sin(aa - 0.25) * 30, ey + math.cos(aa - 0.25) * 30, 9)
        if kind == 0:
            seg(sh_x + 6, sh_y + 2, sh_x + 34, sh_y + 52, 7)
            seg(sh_x + 8, sh_y + 4, sh_x - 40, sh_y - 70, 5)
        else:
            seg(sh_x + 2, sh_y + 30, sh_x - 6, sh_y - 105, 5)
            g.beginPath()
            g.moveTo(sh_x - 6, sh_y - 104)
            g.lineTo(sh_x + 46, sh_y - 92)
            g.lineTo(sh_x + 40, sh_y - 64)
            g.lineTo(sh_x - 4, sh_y - 70)
            g.closePath()
            g.fill()

    for row in range(2):
        for f in range(NF):
            fig(f * FW, row * FH, f, row)
    return g.to_float()


def radiator_number_canvas():
    """race.js's numTex: the white racing 7 painted on the honeycomb core, 256 x 256 -> float RGBA, row 0 at the top
    (Georgia where Windows has it, the bundled serif elsewhere)."""
    from .bin_pages import Canvas2D
    g = Canvas2D(256, 256, ss=2)
    g.fillStyle = '#000'
    g.fillRect(0, 0, 256, 256)
    g.fillStyle = '#fff'
    g.font = 'bold 210px Georgia, "Times New Roman", serif'
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.fillText('7', 128, 140)
    return g.to_float()


def cam_to_blender(c):
    """A three cam {pos, target, fov, roll, up} as Blender's axes (fov stays three's vertical degrees)."""
    if c is None:
        return None
    out = {'pos': to_blender(c['pos']), 'target': to_blender(c['target']), 'fov': c.get('fov', 40),
           'roll': c.get('roll', 0.0)}
    if c.get('up'):
        out['up'] = to_blender(c['up'])
    return out


# =============================================================================================== the build ===

U_SPEC = {   # race.js's uniforms (snake_case) and their starting values; px: the camera's pixel angle (LED cells)
    'time': 0.0, 'rain': 1.0, 'wet': 1.0, 'lamps': 1.0, 'bill_a': 1.0, 'bill_b': 1.0, 'gaze': 0.0, 'march': 0.0,
    'march_t': 0.0, 'crash_age': -10.0, 'crash_p': (1.6, D['ch']['water'], 121.0), 'flip_age': -10.0,
    'flip_p': (1.6, D['ch']['water'], 124.0), 'heel_age': -10.0, 'works': 1.0, 'smear': 0.0, 'chain_run': 0.0,
    'scarf_speed': 0.0, 'car_shadow': 0.0, 'steam': 0.0, 'steam_p': (1.6, D['ch']['water'], 120.0),
    'headlamps': 1.0, 'heel_key': 0.0, 'px': 0.0012,
}
SODIUM = lin_hex('#ffab5c')
WORK_COL = lin_hex('#dfe9ff')


class _NZ:
    """race.js's nz(p2, scale): the noise atlas at a 2D coordinate (tiles) -> .r .g .b .a."""

    def __init__(self, nb, img, uv):
        col, a = nb.tex(img, uv)
        self.rgb = col
        self.r, self.g, self.b = nb.sep(col)
        self.a = a


class Race:
    """The built set (what race.js's build returns): group (the root Empty), parts, cams, update, cam_at, focal,
    set_active, key_camera, finish, dispose. Build it with build()."""

    def __init__(self, scene=None, reflect=True, reflect_scale=0.5, sky=True, towers=True, rain=True, rain_count=5200,
                 lamp_i=140.0, amounts=('$100,000,000', '$20,000,000'), name='race', keyer=None, collection=None):
        self.scene = scene or bpy.context.scene
        self.opts = dict(reflect=reflect, reflect_scale=reflect_scale, sky=sky, towers=towers, rain=rain,
                         rain_count=rain_count, lamp_i=lamp_i, amounts=tuple(amounts))
        self.key = keyer if isinstance(keyer, Keyer) else Keyer(keyer)
        self.col = collection or make_collection(f'set:{name}', self.scene.collection)
        self.group = empty(f'set:{name}', collection=self.col)
        self.group.empty_display_size = 2.0
        self.parts = {}
        self.objects = []
        self.mats = {}
        self.path = car_path()
        if abs(self.path.length() - CAR_LEN) > 0.5:
            print(f'[race] car path is {self.path.length():.2f} m; update CAR_LEN')
        self.debris = debris_specs(self.path)
        self.gn_inputs = []          # (modifier, socket identifier, uniform name) keyed from the uniforms
        self.U = Uniforms(f'{name}:U', U_SPEC)
        self._active = True
        self._textures()
        self._materials()
        if sky:
            self._world()
        self._deck()
        self._ground_drain()
        self._street_lamps()
        if towers:
            self._towers()
        self._billboards()
        self._car()
        self._riders()
        self._contact_shadow()
        self._works()
        self._heel()
        if rain:
            self._rain(rain_count)
        self._water()
        self._splash()
        self._lights()
        if reflect:
            self._planar()
        self.car['mats'] = self.car_mats
        self.cams = {k: cam_to_blender(v) for k, v in CAMS.items()}
        self.update(0.0, {}, frame=None)

    # ------------------------------------------------------------------------------------------- helpers
    def obj(self, name, g, mat, parent=None, **kw):
        ob = mesh_object(name, g, mat, parent=parent or self.group, collection=self.col, **kw)
        if ob is not None:
            self.objects.append(ob)
        return ob

    def nz(self, nb, uv, scale=1.0):
        return _NZ(nb, self.noise_img, uv * scale if scale != 1.0 else uv)

    def u(self, nb, k):
        return self.U.get(nb, k)

    def PL(self, nb):
        return nb.set3(self.group)

    def tri(self, nb, P, N, s):
        """race.js tri(): triplanar noise from set-local position and normal -> .r .g .b."""
        w = nb.pow(nb.abs(N), 4.0)
        ws = w / (w.x + w.y + w.z)
        c1 = self.nz(nb, nb.vec2(P.z, P.y), s).rgb
        c2 = self.nz(nb, nb.vec2(P.x, P.z), s).rgb
        c3 = self.nz(nb, nb.vec2(P.x, P.y), s).rgb
        rgb = c1 * ws.x + c2 * ws.y + c3 * ws.z
        o = _NZ.__new__(_NZ)
        o.rgb = rgb
        o.r, o.g, o.b = nb.sep(rgb)
        return o

    # ------------------------------------------------------------------------------------------- textures
    def _textures(self):
        # float: the drain's waves sample it in Geometry Nodes (see image_from_array)
        self.noise_img = image_from_array('race:noise', noise_atlas(), 'Non-Color', top_first=False, float_buffer=True)
        self.env_img = image_from_array('race:night_env', night_env(), 'sRGB', top_first=False)

    # ------------------------------------------------------------------------------------------- materials
    def concrete_mat(self, name, tint='#7d7f80', dark=0.75, streak=1.0, drain=False):
        m = new_material(name)
        nb = NB(m.node_tree)
        P, N = self.PL(nb), nb.normal3()
        n1, n2 = self.tri(nb, P, N, 0.11), self.tri(nb, P, N, 0.9)
        vert = nb.smoothstep(0.75, 0.95, 1.0 - nb.abs(N.y))
        st = self.nz(nb, nb.vec2((P.x + P.z) * 0.22, P.y * 0.03)).r
        streaks = nb.smoothstep(0.55, 0.95, st) * vert * streak
        base = nb.v(lin_hex(tint)) * dark * (n1.r * 0.45 + 0.75) * (n2.b * 0.25 + 0.85)
        wetness = self.u(nb, 'wet') * 0.6 + streaks * 0.4
        if drain:
            above = P.y - D['ch']['water']
            algae = nb.smoothstep(0.9, 0.1, above) * (n1.g * 0.5 + 0.6)
            silt = nb.smoothstep(2.6, 0.6, above) * (n2.r * 0.6 + 0.4)
            base = nb.mix(nb.mix(base, nb.v(lin_hex('#4a4230')) * 0.5, silt * 0.6), nb.v(lin_hex('#1d2416')) * 0.6,
                          nb.clamp(algae))
            wetness = wetness + nb.smoothstep(3.0, 0.0, above) * 0.6
        wet = nb.clamp(wetness)
        albedo = base * (1.0 - wet * 0.45) * (1.0 - streaks * 0.35)
        rough = nb.mix(0.86, 0.36, wet) + (n2.b - 0.5) * 0.15
        nrm = nb.bump(n2.b * 0.004 + n1.g * 0.006)
        output(nb, principled(nb, albedo, rough, 0.0, nrm))
        self.mats[name] = m
        return m

    def steel_mat(self, name, tint='#2a2d31', rough=0.5, metal=0.75, rust=0.25):
        m = new_material(name)
        nb = NB(m.node_tree)
        n = self.tri(nb, self.PL(nb), nb.normal3(), 0.6)
        r = nb.smoothstep(0.62, 0.9, n.r) * rust
        albedo = nb.mix(lin_hex(tint), lin_hex('#4a2a16'), r) * (n.b * 0.3 + 0.85)
        mt = nb.mix(metal, 0.1, r)
        # race.js lit its steel with 0.6 of the lamp field whatever the metalness; the real lights give a metal no
        # diffuse, so the rest of that dose comes back here
        output(nb, principled(nb, albedo, nb.mix(rough, 0.85, r) - self.u(nb, 'wet') * 0.12, mt,
                              emission=self._dose(nb, albedo, nb.max(mt - 0.4, 0.0))))
        self.mats[name] = m
        return m

    def _materials(self):
        self.mats['concrete'] = self.concrete_mat('race:concrete')
        self.mats['concrete_dark'] = self.concrete_mat('race:concrete_dark', tint='#5d6062', dark=0.7)
        self.mats['steel'] = self.steel_mat('race:steel')
        self.mats['steel_light'] = self.steel_mat('race:steel_light', tint='#6b6f73', rough=0.42, metal=0.85, rust=0.15)

    # ------------------------------------------------------------------------------------------- world
    def _world(self):
        """The night sky (race.js's 2400 m dome, no fog) for camera rays; the set's night-city environment plus its
        hemisphere light (race.js's lit() envNode and HemisphereLight) for every other ray."""
        w = bpy.data.worlds.new('race:world')
        w.use_nodes = True
        nt = w.node_tree
        nt.nodes.clear()
        nb = NB(nt)
        tc = nb.node('ShaderNodeTexCoord')
        dB = nb.normalize(V(nb, tc.outputs['Generated'], True))
        d = nb.three(dB)
        h = d.y
        k = nb.pow(nb.clamp(h, 0.0, 1.0), 0.45)
        base = nb.mix(nb.v(lin_hex('#2a1d1c')) * 0.5, lin_hex('#05070d'), k)
        cp = nb.vec2(d.x, d.z) / (nb.max(h, 0.04) + 0.15) * 0.22 + nb.vec2(self.u(nb, 'time') * 0.004, 0.0)
        c = self.nz(nb, cp)
        cloud = nb.smoothstep(0.35, 0.8, c.r * 0.7 + c.a * 0.5) * nb.smoothstep(0.0, 0.12, h) * (1.0 - k * 0.7)
        glow_h = nb.exp(nb.abs(h) * -9.0) * 0.6
        sky = (base + nb.v(lin_hex('#ff7a3c')) * cloud * 0.06 + nb.v(lin_hex('#8e3b46')) * glow_h * 0.045
               + nb.v(lin_hex('#ff8a3d')) * nb.exp(nb.abs(h) * -30.0) * 0.10)
        env = nb.node('ShaderNodeTexEnvironment', interpolation='Linear')
        env.image = self.env_img
        nb.links.new(dB.out, env.inputs['Vector'])
        up = nb.step(0.0, dB.z)
        hv = nb.node('ShaderNodeValue')
        hv.name = hv.label = 'hemi'
        hv.outputs[0].default_value = LIGHT_BASE['hemi'] / PI
        self._hemi_value = hv
        hemi = nb.mix(nb.v(lin_hex('#120c0a')), lin_hex('#1a2438'), up) * V(nb, hv.outputs[0], False)
        amb = V(nb, env.outputs['Color'], True) + hemi
        lp = nb.node('ShaderNodeLightPath')
        col = nb.mix(amb, sky, V(nb, lp.outputs['Is Camera Ray'], False))
        bg = nb.node('ShaderNodeBackground')
        nb.links.new(col.out, bg.inputs['Color'])
        o = nb.node('ShaderNodeOutputWorld')
        nb.links.new(bg.outputs[0], o.inputs['Surface'])
        self.world = w
        self.parts['sky'] = w

    # ------------------------------------------------------------------------------------------- the deck
    def _ripples(self, nb, p, cell, rate, salt):
        """race.js ripples(): one rain ring per cell, random phase."""
        c = nb.floor(p / cell)
        hs = nb.abs(c.x * 73.0 + c.y * 9157.0 + salt)
        h1, h2, h3 = nb.hash(hs), nb.hash(hs + 17.0), nb.hash(hs + 41.0)
        ctr = (c + nb.vec2(h1 * 0.6 + 0.2, h2 * 0.6 + 0.2)) * cell
        age = nb.fract(self.u(nb, 'time') * rate + h3)
        r = nb.length(p - ctr)
        R = age * cell * 0.48
        return nb.sin((r - R) * 42.0) * nb.exp(nb.abs(r - R) * -28.0) * (1.0 - age) * nb.step(r, cell * 0.5)

    def road_mat(self):
        """Wet asphalt with lane paint and wear, ruts and gutters that hold water, the heel's puddle, rain rings and
        the heel's impact rings. race.js mirrored the set in it with a planar reflector, jittered down the screen
        into streaks; here the reflection is the BSDF's own (EEVEE's ray tracing and the deck's planar probe), its
        normal tilted toward the viewer by the same streak noise so lights smear into vertical streaks."""
        m = new_material('race:road')
        nb = NB(m.node_tree)
        P = self.PL(nb)
        x, z = P.x, P.z
        xz = nb.vec2(x, z)
        n1, n2, n3 = self.nz(nb, xz, 0.031), self.nz(nb, xz, 0.45), self.nz(nb, xz, 2.2)
        band = lambda c, w: nb.smoothstep(w, w - 0.012, nb.abs(x - c))
        dash = lambda ph: nb.step(nb.fract((z + ph) / 12.0), 0.25)
        paint = (band(1.8, 0.075) + band(D['x_med'] - 0.75, 0.075) + band(D['x_med'] + 0.75, 0.075)
                 + band(17.45, 0.075) + band(5.4, 0.07) * dash(0.0) + band(13.65, 0.07) * dash(5.0))
        wear = nb.smoothstep(0.25, 0.65, n3.b + n2.r * 0.5)
        paint_m = nb.clamp(paint) * (wear * 0.7 + 0.3)
        gutter = (nb.smoothstep(1.4, 0.2, x - (D['x_r'] + 0.6)) + nb.smoothstep(1.4, 0.2, (D['x_l'] - 0.6) - x)
                  + nb.smoothstep(1.0, 0.1, nb.abs(x - D['x_med']) - 0.6))
        rut = lambda c: nb.exp(nb.abs(x - (c - 0.85)) * -5.0) + nb.exp(nb.abs(x - (c + 0.85)) * -5.0)
        ruts = rut(D['lanes'][0]) + rut(D['lanes'][1]) + rut(D['lanes'][2]) + rut(D['lanes'][3])
        wet = self.u(nb, 'wet')
        puddle = nb.smoothstep(0.58, 0.66, n1.a * 0.7 + n1.r * 0.3 + ruts * 0.16 + gutter * 0.28) * wet
        hp = nb.vec2(x - D['heel'][0], z - D['heel'][2])
        heel_pud = nb.smoothstep(0.95, 0.55, nb.length(hp * (1.0, 0.75, 1.0)) + (n3.r - 0.5) * 0.25)
        puddle = nb.max(puddle, heel_pud)
        mark = nb.smoothstep(2.2, 1.0, nb.length(xz))
        puddle = puddle * (1.0 - mark * 0.9)
        asphalt = nb.v(lin_hex('#24262a')) * (n2.r * 0.5 + 0.62) * (n3.b * 0.35 + 0.8)
        wet_a = asphalt * nb.mix(1.0, 0.5, wet)
        albedo = nb.mix(wet_a, nb.v(lin_hex('#c9c7bd')) * 0.62, paint_m) * (1.0 - puddle * 0.65)
        rings = (self._ripples(nb, xz, 0.55, 1.3, 0.0) + self._ripples(nb, xz + (0.27, 0.27, 0.0), 0.37, 1.7, 31.0)) * self.u(nb, 'rain')
        h_agg = n3.b * 0.0035 + n2.g * 0.002
        hr = nb.length(hp)
        h_age = self.u(nb, 'heel_age')
        heel_ring = (nb.sin((hr - h_age * 0.55) * 55.0) * nb.exp(nb.abs(hr - h_age * 0.55) * -18.0)
                     * nb.exp(h_age * -1.6) * nb.step(0.0, h_age) * heel_pud)
        height = nb.mix(h_agg, rings * 0.0011 + heel_ring * 0.002, puddle)
        nrm = nb.bump(height)
        # the wet streak: a tilt toward the viewer along the ground, fast across the road, slow along it
        streak_n = (self.nz(nb, nb.vec2(x * 9.0, z * 0.12)).r - 0.5) + (self.nz(nb, nb.vec2(x * 31.0, z * 0.4)).b - 0.5) * 0.6
        spread = nb.mix(0.16, 0.004, puddle)
        inc = nb.geom('Incoming')
        vh = nb.normalize(nb.vec3(inc.x, inc.y, 0.0))
        nrm = nb.normalize(nrm + vh * (streak_n * spread * 0.45))
        wet_k = nb.mix(wet * 0.38, 0.95, puddle) * (1.0 - paint_m * 0.6)
        rough = nb.mix(nb.mix(0.92, 0.3, wet_k), 0.03, puddle) + paint_m * 0.25
        bsdf = principled(nb, albedo, rough, 0.0, nrm, ior=1.33, spec=nb.mix(0.15, 0.5, nb.clamp(wet_k * 1.6)))
        output(nb, bsdf)
        self.mats['road'] = m
        return m

    def _deck(self):
        jag = lambda x, s: math.sin(x * 2.3 + s) * 0.35 + math.sin(x * 5.7 + s * 2) * 0.22 + math.sin(x * 11.1 + s) * 0.1
        road = GB()

        def road_piece(x0, x1, z0, z1, jag_end=False, jag_start=False):
            nx = 28
            P, I = [], []
            for i in range(nx + 1):
                x = x0 + (x1 - x0) * i / nx
                za = z0 - (jag(x, 4.1) - 0.6) if jag_start else z0
                zb = z1 + (jag(x, 1.3) - 0.6) if jag_end else z1
                P += [(x, 0, za), (x, 0, zb)]
            for i in range(nx):
                a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
                I += [(a, b, c), (b, d, c)]
            g = Geo(P, np.tile([0, 1.0, 0], (len(P), 1)), np.zeros((len(P), 2)), I)
            road.add(g, None, (0, 0, 0, 0), lambda v, n, k: (v[0], v[2]))

        road_piece(D['x_r'], D['x_med'] - 0.6, D['z_far'], D['gap0'], jag_end=True)
        road_piece(D['x_r'], D['x_med'] - 0.6, D['gap1'], D['z_near'], jag_start=True)
        road_piece(D['x_med'] - 0.6, D['x_l'], D['z_far'], D['z_near'])
        self.parts['road'] = self.obj('race:road', road.build(), self.road_mat())
        # slab body: fascia, soffits, the broken ends
        dt = D['deck_t']
        sl = GB()

        def fascia(x, z0, z1, side):
            p = lambda zz, y: (x, y, zz)
            if side > 0:
                sl.quad(p(z1, -dt), p(z0, -dt), p(z0, 0.0), p(z1, 0.0), (1, 0, 0, 0), (-z1, -dt))
            else:
                sl.quad(p(z0, -dt), p(z1, -dt), p(z1, 0.0), p(z0, 0.0), (1, 0, 0, 0), (z0, -dt))

        fascia(D['x_r'], D['z_far'], D['gap0'] - 0.6, -1)
        fascia(D['x_r'], D['gap1'] + 0.6, D['z_near'], -1)
        fascia(D['x_l'], D['z_far'], D['z_near'], 1)
        fascia(D['x_med'] - 0.6, D['gap0'], D['gap1'], -1)
        soffit = lambda x0, x1, z0, z1: sl.quad((x0, -dt, z1), (x0, -dt, z0), (x1, -dt, z0), (x1, -dt, z1), (2, 0, 0, 0), (x0, z0))
        soffit(D['x_r'], D['x_med'] - 0.6, D['z_far'], D['gap0'])
        soffit(D['x_r'], D['x_med'] - 0.6, D['gap1'], D['z_near'])
        soffit(D['x_med'] - 0.6, D['x_l'], D['z_far'], D['z_near'])
        nx = 28
        for z_edge, s, dr in ((D['gap0'], 1.3, 1), (D['gap1'], 4.1, -1)):
            for i in range(nx):
                xa = D['x_r'] + (D['x_med'] - 0.6 - D['x_r']) * (i / nx)
                xb = D['x_r'] + (D['x_med'] - 0.6 - D['x_r']) * ((i + 1) / nx)
                za, zb = z_edge + dr * (jag(xa, s) - 0.6), z_edge + dr * (jag(xb, s) - 0.6)
                zab = za - dr * (0.3 + 0.25 * math.sin(xa * 3.1))
                zbb = zb - dr * (0.3 + 0.25 * math.sin(xb * 3.1))
                if dr > 0:
                    sl.quad((xa, -dt, zab), (xb, -dt, zbb), (xb, 0, zb), (xa, 0, za), (3, 0, 0, 0), (xa, -dt))
                else:
                    sl.quad((xb, -dt, zbb), (xa, -dt, zab), (xa, 0, za), (xb, 0, zb), (3, 0, 0, 0), (xb, -dt))
        self.parts['slab'] = self.obj('race:slab', sl.build(), self.mats['concrete_dark'], flat=True)
        # Jersey barriers with a neon strip in long dashes along the top
        jersey = [(-0.30, 0), (-0.27, 0.075), (-0.14, 0.33), (-0.09, 0.84), (0.09, 0.84), (0.14, 0.33), (0.27, 0.075), (0.30, 0)]
        bar, neon = GB(), GB()

        def barrier(x, z0, z1, neon_c=None, side=0):
            g = extrude_geo(Shape(jersey), depth=z1 - z0, steps=1)
            bar.add(g, M4(x, 0, z0), (0, 0, 0, 0), lambda v, n, k: (v[2], v[1]))
            if neon_c:
                z = z0
                while z < z1:
                    ln = min(6.5, z1 - z)
                    neon.add(box_geo(0.05, 0.05, ln), M4(x + side * 0.06, 0.875, z + ln / 2), neon_c)
                    z += 9

        barrier(D['x_r'] + 0.3, D['z_far'], D['gap0'] - 0.9, (0.16, 0.9, 1.0, 1), -1)
        barrier(D['x_r'] + 0.3, D['gap1'] + 0.9, D['z_near'], (0.16, 0.9, 1.0, 1), -1)
        barrier(D['x_l'] - 0.3, D['z_far'], D['z_near'], (1.0, 0.25, 0.8, 1), 1)
        barrier(D['x_med'], D['z_far'], D['z_near'])
        self.parts['barriers'] = self.obj('race:barriers', bar.build(), self.mats['concrete'], flat=True)

        def neon_build(nb):
            a = nb.attr('aux', out='Color')
            aw = nb.attr('aux', out='Alpha')
            fl = nb.sin(self.PL(nb).z * 0.21 + self.u(nb, 'time') * 1.7) * 0.08 + 0.92
            return a * aw * fl * 5.5
        self.mats['neon'] = unlit('race:neon', neon_build)
        self.parts['neon'] = self.obj('race:neon', neon.build(), self.mats['neon'])
        # piers: hammerhead caps on paired columns every 36 m (none in the gap on the right, none in the drain)
        pier = GB()
        z = D['z_far'] + 18
        while z < D['z_near']:
            in_gap = D['gap0'] - 4 < z < D['gap1'] + 4
            in_drain = D['ch']['z0'] - 2 < z < D['ch']['z1'] + 2
            if not in_drain:
                for x in ([15.0] if in_gap else [2.6, 15.0]):
                    pier.add(cylinder_geo(0.85, 0.95, -dt - D['ground'], 18), M4(x, (D['ground'] - dt) / 2, z))
                x0 = D['x_med'] - 0.6 if in_gap else D['x_r'] + 0.4
                box_quads(pier, x0, -dt - 1.3, z - 1.1, D['x_l'] - 0.4, -dt, z + 1.1, (0, 0, 0, 0), bottom=True)
            z += 36
        for z in (D['ch']['z0'] - 2.5, D['ch']['z1'] + 2.5):
            for x in (11.5, 18.0):
                pier.add(cylinder_geo(0.85, 1.0, -dt - D['ground'], 18), M4(x, (D['ground'] - dt) / 2, z))
            box_quads(pier, D['x_med'] - 0.4, -dt - 1.3, z - 1.1, D['x_l'] - 0.4, -dt, z + 1.1, (0, 0, 0, 0), bottom=True)
        self.parts['piers'] = self.obj('race:piers', pier.build(), self.mats['concrete_dark'])

    # ------------------------------------------------------------------------------------------- ground + drain
    def _ground_drain(self):
        m = new_material('race:ground')
        nb = NB(m.node_tree)
        P = self.PL(nb)
        pxz = nb.vec2(P.x, P.z)
        n1, n2 = self.nz(nb, pxz, 0.02), self.nz(nb, pxz, 0.3)
        albedo = nb.v(lin_hex('#1d1f22')) * (n1.r * 0.6 + 0.6) * (n2.b * 0.3 + 0.8)
        pud = nb.smoothstep(0.55, 0.7, n1.a + n2.r * 0.2)
        col = albedo * (1.0 - pud * 0.6)
        # street lamps down here: a sparse grid of sodium pools (race.js paints them into the ground's own light)
        cell = nb.floor(pxz / 38.0)
        hs = nb.abs(cell.x * 31.0 + cell.y * 977.0) + 5.0
        on = nb.step(nb.hash(hs), 0.55)
        lp = (cell + (0.5, 0.5, 0.0)) * 38.0
        dv = nb.vec3(lp.x, D['ground'] + 5.5, lp.y) - P
        pool = on * nb.max(nb.dot(nb.normalize(dv), (0, 1, 0)), 0.0) / nb.max(nb.dot(dv, dv), 1.0) * 140.0
        em = col * nb.v(SODIUM) * pool * (1.0 / PI)
        output(nb, principled(nb, col, nb.mix(0.7, 0.06, pud), 0.0, emission=em))
        self.mats['ground'] = m
        S = 1400
        gg = GB()
        g0 = D['ground']
        gg.quad((-S, g0, D['ch']['z0']), (S, g0, D['ch']['z0']), (S, g0, -S), (-S, g0, -S))
        gg.quad((-S, g0, S), (S, g0, S), (S, g0, D['ch']['z1']), (-S, g0, D['ch']['z1']))
        self.parts['ground'] = self.obj('race:ground', gg.build(), m)
        C, L = D['ch'], 1400
        cg = GB()
        cg.quad((L, g0, C['z0']), (-L, g0, C['z0']), (-L, C['bottom'], C['b0']), (L, C['bottom'], C['b0']))
        cg.quad((-L, g0, C['z1']), (L, g0, C['z1']), (L, C['bottom'], C['b1']), (-L, C['bottom'], C['b1']))
        cg.quad((-L, C['bottom'], C['b1']), (L, C['bottom'], C['b1']), (L, C['bottom'], C['b0']), (-L, C['bottom'], C['b0']))
        self.parts['drain'] = self.obj('race:drain', cg.build(),
                                       self.concrete_mat('race:drain_concrete', tint='#6e706a', dark=0.7, drain=True))

    # ------------------------------------------------------------------------------------------- street lamps
    def _street_lamps(self):
        poles, lens, cones = GB(), GB(), GB()
        heads = lamp_heads()
        arm = CatmullRom([(0, 9.6, 0), (0.35, 10.15, 0), (1.6, 10.42, 0), (3.15, 10.32, 0)])
        arm_g = tube_geo(arm, 12, 0.07, 8, False)
        for hx, hy, hz, row in heads:
            flip = row == 'L'
            bx = D['lamp_l']['x'] if flip else D['lamp_r']['x']
            m = M4(bx, 0.84, hz, 0, PI if flip else 0, 0)
            poles.add(cylinder_geo(0.11, 0.16, 10.0, 10), m @ M4(0, 5.0, 0))
            poles.add(arm_g, m)
            poles.add(box_geo(1.05, 0.2, 0.46), m @ M4(3.3, 10.3, 0, 0, 0, -0.06))
            lens.add(plane_geo(0.82, 0.32), m @ M4(3.32, 10.19, 0, PI / 2, 0, -0.06))
            cones.add(cone_geo(5.2, 10.0, 28, 1, True), M4(hx, hy - 5.0, hz))
        self.parts['lamp_poles'] = self.obj('race:lampPoles', poles.build(), self.mats['steel'])
        self.mats['lamp_lens'] = unlit('race:lamp_lens', lambda nb: nb.v(SODIUM) * (self.u(nb, 'lamps') * 14.0))
        lenses = self.obj('race:lampLenses', lens.build(), self.mats['lamp_lens'])

        def cone_build(nb):
            P, N = self.PL(nb), nb.normal3()
            facing = nb.abs(nb.dot(N, nb.three(nb.geom('Incoming'))))
            yN = nb.clamp(P.y / 10.0)
            fall = nb.pow(yN, 1.6) * 0.85 + 0.15
            spark = self.nz(nb, nb.vec2((P.x + P.z) * 0.6, P.y * 0.08 + self.u(nb, 'time') * 1.4)).g
            return (nb.v(SODIUM) * nb.pow(facing, 1.8) * fall * (spark * 0.6 + 0.55) * self.u(nb, 'lamps') * 0.055
                    * (self.u(nb, 'rain') * 0.5 + 0.5))
        cm = unlit('race:lamp_cones', cone_build, additive=True)
        cm.use_backface_culling = True
        self.mats['lamp_cones'] = cm
        cone_ob = self.obj('race:lampCones', cones.build(), cm)
        _no_shadow(cone_ob)
        _no_reflection(cone_ob)
        self.parts['lamps'] = {'poles': self.parts['lamp_poles'], 'lenses': lenses, 'cones': cone_ob,
                               'heads': [to_blender(h[:3]) for h in heads]}

    # ------------------------------------------------------------------------------------------- the march
    def _march_texture(self):
        """The walk-cycle atlas of the absent column (march_canvas()), blurred by the penumbra race.js read from its
        mips (log2(0.06 m on the marchers' plane x 128 px) ~ level 2.7 at the wall)."""
        a = march_canvas()
        self.march_canvas = a
        from PIL import Image, ImageFilter
        im = Image.fromarray((a[..., 0] * 255 + 0.5).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(2.0))
        b = np.asarray(im, np.float32) / 255.0
        rgba = np.stack([b, b, b, np.ones_like(b)], -1)
        return image_from_array('race:march_atlas', rgba, 'Non-Color', top_first=False)

    def _march_at(self, nb, P, xm, z_off):
        """race.js marchAt: looks up the column's plane along the floodlight's ray (a true projection)."""
        fx0 = D['flood'][0]
        L = nb.v(tuple(D['flood']))
        denom = P.x - fx0
        tP = (xm - fx0) / (denom + (1.0 - nb.step(1e-4, nb.abs(denom))) * 1e-4)
        valid = nb.step(0.02, tP) * nb.step(tP, 0.985)
        Q = L + (P - L) * tP
        cz = (Q.z + self.u(nb, 'march_t') * 1.5 + z_off) / 1.05
        idx, fx = nb.floor(cz), nb.fract(cz)
        frame = nb.floor(nb.fract(self.u(nb, 'march_t')) * 8.0)
        row = nb.step(0.72, nb.hash(nb.abs(idx) + 11.0))
        sv = Q.y / 2.0
        ins = nb.step(0.0, sv) * nb.step(sv, 0.999)
        su = (frame + nb.clamp(fx, 0.02, 0.98)) / 8.0
        cvv = (1.0 - sv + row) * 0.5
        col, _a = nb.tex(self.march_img, nb.vec2(su, cvv), ext='CLIP')
        return col.x * valid * ins

    # ------------------------------------------------------------------------------------------- towers
    def tower_mat(self):
        m = new_material('race:towers')
        nb = NB(m.node_tree)
        seed = nb.attr('aux', out='Color').x
        style = nb.attr('aux', out='Color').y
        blank = nb.attr('aux', out='Color').z
        lit_f = nb.attr('aux', out='Alpha')
        uvv = nb.uv()
        fu, fv = uvv.x, uvv.y
        P, N = self.PL(nb), nb.normal3()
        vert = 1.0 - nb.abs(N.y)
        lt = lambda a, b: nb.math('LESS_THAN', a, b)
        mod_w = nb.select(lt(style, 0.5), 1.55, nb.select(lt(style, 1.5), 2.2, 1.8))
        floor_h = nb.select(lt(style, 1.5), 3.6, 3.3)
        cu, cvv = nb.fract(fu / mod_w), nb.fract(fv / floor_h)
        colc, row = nb.floor(fu / mod_w), nb.floor(fv / floor_h)
        st = nb.step
        punched = st(0.14, cu) * st(cu, 0.86) * st(0.22, cvv) * st(cvv, 0.84)
        curtain = st(0.035, cu) * st(cu, 0.965) * st(0.12, cvv) * st(cvv, 0.93)
        is_glass = (nb.select(nb.math('GREATER_THAN', style, 1.5), curtain, punched) * vert * (1.0 - blank)
                    * st(style, 2.5) * st(D['ground'] + 4.0, P.y))
        hs = nb.abs(seed * 131.0 + row * 17.0 + colc * 3.0)
        cluster = self.nz(nb, nb.vec2(seed * 0.37 + colc * 0.031, row * 0.045)).r
        on = st(nb.hash(hs), lit_f * (cluster * 1.4 + 0.2))
        warm = nb.hash(hs + 7.0)
        wcol = nb.mix(lin_hex('#9cc8ff'), nb.mix(lin_hex('#ffb26b'), lin_hex('#ffd9a0'), nb.hash(hs + 13.0)), st(0.35, warm))
        w_i = nb.hash(hs + 3.0) * 0.9 + 0.35
        n1, n2 = self.tri(nb, P, N, 0.07), self.tri(nb, P, N, 0.6)
        stn = self.nz(nb, nb.vec2((P.x + P.z) * 0.07, P.y * 0.012)).r
        streak = nb.smoothstep(0.5, 0.85, stn) * vert * 0.7
        pu, pv = nb.fract(fu / 2.4), nb.fract(fv / 1.2)
        joint = nb.max(nb.smoothstep(0.012, 0.0, nb.min(pu, 1.0 - pu)), nb.smoothstep(0.02, 0.0, nb.min(pv, 1.0 - pv)))
        tie = nb.smoothstep(0.035, 0.02, nb.length(nb.vec2((nb.fract(fu / 0.6) - 0.5) * 0.6, (nb.fract(fv / 0.6) - 0.5) * 0.6)))
        board = self.nz(nb, nb.vec2(fu * 0.05, fv * 4.0)).b
        conc = nb.v(lin_hex('#3e4246')) * (n1.r * 0.5 + 0.6) * (n2.b * 0.3 + 0.8) * (1.0 - streak * 0.35)
        blank_c = (nb.v(lin_hex('#8a8c8a')) * (n1.r * 0.4 + 0.72) * (board * 0.18 + 0.9) * (1.0 - streak * 0.4)
                   * (1.0 - (joint * 0.45 + tie * 0.6) * blank))
        albedo = nb.mix(nb.mix(conc, blank_c, blank), lin_hex('#06080b'), is_glass)
        rough = nb.mix(nb.mix(0.82, 0.6, blank), 0.08, is_glass) - self.u(nb, 'wet') * 0.15 * (1.0 - is_glass)
        # the march: the floodlight's beam and the shadows of an absent column, on every wall the beam reaches
        Fv = nb.v(tuple(D['flood']))
        dv = Fv - P
        d2 = nb.max(nb.dot(dv, dv), 1.0)
        l = dv / nb.sqrt(d2)
        ndl = nb.max(nb.dot(N, l), 0.0)
        axis = _norm((D['wall']['x'] - D['flood'][0], 10.0 - D['flood'][1], 38.0 - D['flood'][2]))
        cos_a = nb.dot(-l, tuple(axis))
        flood = ndl * nb.smoothstep(0.66, 0.93, cos_a) / d2 * 7600.0 * (self.u(nb, 'march') * 0.92 + 0.08)
        sh = nb.max(self._march_at(nb, P, D['march_x'], 0.0), self._march_at(nb, P, D['march_x'] - 1.3, 0.52)) * self.u(nb, 'march')
        E = nb.v(lin_hex('#ffe2b8')) * flood * (1.0 - sh * 0.93)
        em = albedo * E * (1.0 / PI) + wcol * on * is_glass * w_i * 1.6
        nrm = nb.bump(n2.b * 0.01 * (1.0 - is_glass) - (joint + tie) * blank * 0.008)
        output(nb, principled(nb, albedo, rough, is_glass * 0.6, nrm, emission=em))
        self.mats['towers'] = m
        return m

    def _towers(self):
        tg, ng = GB(), GB()
        R = lcg(9091)
        W = D['wall']

        def blocked(x0, x1, z0, z1):
            no = [(D['x_r'] - 6, D['x_l'] + 6, -2000, 2000), (-30, -4, -84, -44), (22, 48, -84, -44),
                  (-2000, 2000, D['ch']['z0'] - 6, D['ch']['z1'] + 6), (W['x'] - 26, W['x'] + 1, W['z0'] - 4, W['z1'] + 4)]
            return any(x1 > a and x0 < b and z1 > c and z0 < d for a, b, c, d in no)

        def tower(cx, cz, w, d, h, style, seed, tiers=None, blank_face=False):
            lit = 0.06 + R() * 0.22
            if tiers is None:
                tiers = 1 + math.floor(R() * 3) if h > 70 else 1
            y0, ww, dd = D['ground'], w, d
            for k in range(tiers):
                top = D['ground'] + h if k == tiers - 1 else y0 + h * (0.45 + R() * 0.25) / (k + 1)
                sx0, sx1, sz0, sz1 = cx - ww / 2, cx + ww / 2, cz - dd / 2, cz + dd / 2
                box_quads(tg, sx0, y0, sz0, sx1, top, sz1, (seed, style, 0, lit), top=True,
                          sides=(0 if (blank_face and k == 0) else 1, 1, 1, 1))
                if blank_face and k == 0:
                    tg.quad((sx1, y0, sz1), (sx1, y0, sz0), (sx1, top, sz0), (sx1, top, sz1), (seed, style, 1, 0), (-sz1, y0))
                if k == 0 and R() < 0.35:
                    sw = 3 + R() * 3
                    side = -1 if R() < 0.5 else 1
                    sx = sx0 - sw * 0.6 if side < 0 else sx1 - sw * 0.4
                    box_quads(tg, sx, y0, cz - sw / 2, sx + sw, top + 6 + R() * 10, cz + sw / 2, (seed + 1, 3, 0, 0.0))
                if R() < 0.28:
                    c = (0.16, 0.9, 1.0, 1) if R() < 0.5 else ((1.0, 0.25, 0.8, 1) if R() < 0.6 else (1.0, 0.48, 0.2, 1))
                    corners = [(sx0, sz0), (sx1, sz1), (sx0, sz1), (sx1, sz0)][:2 + math.floor(R() * 3)]
                    for ex, ez in corners:
                        ng.add(box_geo(0.22, top - y0, 0.22), M4(ex, (top + y0) / 2, ez), c)
                for ex, ez in ((sx0, sz0), (sx1, sz1)):
                    ng.add(box_geo(0.5, 0.5, 0.5), M4(ex, top + 0.3, ez), (1.0, 0.06, 0.03, 2))
                y0 = top
                ww *= 0.62 + R() * 0.2
                dd *= 0.62 + R() * 0.2
            if R() < 0.4:
                ht = 16 + R() * 20
                tg.add(cylinder_geo(0.25, 0.4, ht, 6), M4(cx, D['ground'] + h + 9, cz), (seed, 4, 0, 0))

        tower(W['x'] - 11, (W['z0'] + W['z1']) / 2, 22, W['z1'] - W['z0'], W['top'] - D['ground'], 1, 777, tiers=1,
              blank_face=True)
        placed = 0
        i = 0
        while i < 520 and placed < 150:
            side = -1 if R() < 0.5 else 1
            dist = 14 + R() ** 1.5 * 230
            cx = D['x_r'] - dist if side < 0 else D['x_l'] + dist
            cz = -520 + R() * 860
            w = 12 + R() * 22
            d = 12 + R() * 26
            h = 26 + R() ** 1.3 * (150 if dist < 60 else 230)
            if blocked(cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2):
                i += 1
                continue
            style = 2 if R() < 0.45 else (0 if R() < 0.6 else 1)
            tower(cx, cz, w, d, h, style, 1000 + i)
            placed += 1
            i += 1
        for k in range(6):
            x0 = -110 + k * 22
            box_quads(tg, x0, D['ground'], D['ch']['z1'] + 8, x0 + 20, D['ground'] + 9, D['ch']['z1'] + 40, (3000 + k, 0, 0, 0.35))
        tg.add(cylinder_geo(2.2, 3.0, 42, 14, 1, True), M4(-40, D['ground'] + 21, D['ch']['z1'] + 30), (3100, 3, 0, 0))
        tg.add(cylinder_geo(1.8, 2.6, 36, 14, 1, True), M4(-78, D['ground'] + 18, D['ch']['z1'] + 24), (3101, 3, 0, 0))
        self.tower_geo = tg.build()
        self.march_img = self._march_texture()
        towers = self.obj('race:towers', self.tower_geo, self.tower_mat(), flat=True)

        def tneon_build(nb):
            a = nb.attr('aux', out='Color')
            aw = nb.attr('aux', out='Alpha')
            is_av = nb.step(1.5, aw)
            blink = nb.step(0.55, nb.fract(self.u(nb, 'time') * 0.75 + self.PL(nb).x * 0.013))
            return a * nb.mix(2.2, blink * 9.0, is_av)
        self.mats['tower_neon'] = unlit('race:tower_neon', tneon_build)
        tneon = self.obj('race:towerNeon', ng.build(), self.mats['tower_neon'])
        self.parts['towers'] = {'towers': towers, 'neon': tneon}
        self.parts['march'] = {'texture': self.march_img, 'plane': D['march_x'], 'flood': to_blender(D['flood'])}

    # ------------------------------------------------------------------------------------------- billboards
    FACE = {'W': 1024, 'H': 683, 'cx': 512, 'cy': 238, 's': 0.6}
    BAND_V = 0.66

    def draw_face(self, g):
        """race.js drawFace: the machine-god face both screens show. Channels: R traces, G phase, B fills."""
        F = self.FACE
        S, ox, oy = F['s'], F['cx'], F['cy']
        X = lambda x: ox + (x - 512) * S
        Y = lambda y: oy + (y - 540) * S
        ph = lambda x, y: min(1.0, math.hypot(x - 512, y - 470) / 560)
        col = lambda r, gp, b: f'rgb({_jr(r * 255)},{_jr(gp * 255)},{_jr(b * 255)})'

        def line(pts, w, r=1, glow=6):
            mx = sum(p[0] for p in pts) / len(pts)
            my = sum(p[1] for p in pts) / len(pts)
            g.strokeStyle = col(r, ph(mx, my), 0)
            g.lineWidth = w * S
            g.lineCap = 'round'
            g.lineJoin = 'round'
            g.shadowColor = col(r * 0.8, ph(mx, my), 0)
            g.shadowBlur = glow * S
            g.beginPath()
            g.moveTo(X(pts[0][0]), Y(pts[0][1]))
            for p in pts[1:]:
                g.lineTo(X(p[0]), Y(p[1]))
            g.stroke()
            g.shadowBlur = 0

        def pad(x, y, r):
            g.fillStyle = col(1, ph(x, y), 0)
            g.beginPath()
            g.arc(X(x), Y(y), r * S, 0, TAU)
            g.fill()

        mir = lambda pts: [(1024 - x, y) for x, y in pts]
        g.globalCompositeOperation = 'lighter'
        for k in range(64):
            a = (k / 64) * TAU
            long_ = k % 2 == 0
            r0, r1 = 430, (560 if long_ else 500)
            line([(512 + math.cos(a) * r0, 470 + math.sin(a) * r0), (512 + math.cos(a) * r1, 470 + math.sin(a) * r1)],
                 5 if long_ else 3, 0.45, 4)
        for r, a0, a1 in ((455, 0.2, 2.9), (455, 3.4, 6.0), (485, -0.5, 1.4), (485, 1.9, 4.4), (515, 0.9, 5.2)):
            g.strokeStyle = col(0.5, ph(512 + r, 470), 0)
            g.lineWidth = 3 * S
            g.beginPath()
            g.arc(X(512), Y(470), r * S, a0, a1)
            g.stroke()
        planes = [
            ([(512, 205), (600, 215), (690, 260), (512, 395)], 0.20),
            ([(690, 260), (745, 340), (760, 440), (700, 420), (512, 395)], 0.13),
            ([(512, 395), (724, 420), (760, 440), (765, 520), (609, 520), (529, 430)], 0.10),
            ([(529, 430), (539, 650), (554, 655), (694, 720), (745, 610), (765, 520), (609, 520)], 0.16),
            ([(554, 655), (694, 720), (630, 810), (560, 870), (512, 880), (512, 760)], 0.12),
            ([(700, 720), (745, 610), (694, 720)], 0.08),
        ]
        for poly, v in planes:
            for pp, vv in ((poly, v), (mir(poly), v * 1.6)):
                g.fillStyle = col(0, 0, vv)
                g.beginPath()
                g.moveTo(X(pp[0][0]), Y(pp[0][1]))
                for p in pp[1:]:
                    g.lineTo(X(p[0]), Y(p[1]))
                g.closePath()
                g.fill()
        outline = [(512, 205), (600, 215), (690, 260), (745, 340), (760, 440), (765, 520), (745, 610), (700, 720),
                   (630, 810), (560, 870), (512, 880)]
        line(outline, 9, 1, 10)
        line(mir(outline), 9, 1, 10)
        line([(600, 845), (612, 1100)], 7, 0.9)
        line([(424, 845), (412, 1100)], 7, 0.9)
        line([(330, 1010), (512, 960), (694, 1010)], 5, 0.7)
        line([(300, 425), (360, 405), (440, 396), (512, 394), (584, 396), (664, 405), (724, 425)], 10, 1, 12)
        for ex in (415, 609):
            lid = [(ex - 72 * math.cos(PI * k / 16), 470 - 30 * math.sin(PI * k / 16)) for k in range(17)]
            low = [(ex - 72 * math.cos(PI * k / 16), 470 + 24 * math.sin(PI * k / 16)) for k in range(17)]
            line(lid, 6, 1, 8)
            line(low, 4, 0.8, 6)
        line([(497, 420), (488, 640)], 5)
        line([(527, 420), (536, 640)], 5)
        line([(468, 655), (556, 655)], 5)
        line([(432, 735), (480, 728), (512, 733), (544, 728), (592, 735)], 7, 1, 8)
        line([(456, 764), (512, 770), (568, 764)], 4, 0.7)
        line([(468, 660), (330, 720)], 4, 0.8)
        line(mir([(468, 660), (330, 720)]), 4, 0.8)
        line([(345, 485), (300, 600), (330, 720), (392, 812)], 4, 0.75)
        line(mir([(345, 485), (300, 600), (330, 720), (392, 812)]), 4, 0.75)
        traces = [
            [(512, 394), (512, 330), (470, 288), (470, 230)], [(480, 394), (480, 350), (430, 300), (430, 250)],
            [(450, 397), (450, 365), (390, 305), (360, 305)], [(420, 400), (380, 360), (330, 360), (300, 330)],
            [(350, 520), (320, 550), (320, 640)], [(380, 560), (360, 580), (360, 680), (400, 720)],
            [(440, 600), (420, 620), (420, 700)], [(470, 790), (470, 830), (500, 860)], [(400, 760), (430, 790), (430, 840)],
            [(300, 470), (260, 470), (240, 450), (210, 450)], [(300, 560), (250, 560), (220, 590), (190, 590)],
            [(330, 680), (290, 720), (250, 720)],
        ]
        for tr in traces:
            for t2 in (tr, mir(tr)):
                line(t2, 3.2, 0.85, 5)
                pad(t2[-1][0], t2[-1][1], 6)
        pad(512, 300, 9)
        g.strokeStyle = col(1, ph(512, 300), 0)
        g.lineWidth = 3 * S
        g.beginPath()
        g.arc(X(512), Y(300), 20 * S, 0, TAU)
        g.stroke()
        g.globalCompositeOperation = 'source-over'

    def billboard_canvas(self, amount):
        """race.js billboardCanvas: the face above the band, the amount in the band (blue channel), the rules (red)."""
        from .bin_pages import Canvas2D
        F = self.FACE
        g = Canvas2D(F['W'], F['H'], ss=2)
        g.fillStyle = 'rgb(0,0,0)'
        g.fillRect(0, 0, F['W'], F['H'])
        g.save()
        g.beginPath()
        g.rect(0, 0, F['W'], F['H'] * self.BAND_V)
        g.clip()
        self.draw_face(g)
        g.restore()
        band_y = F['H'] * self.BAND_V
        g.fillStyle = 'rgb(0,0,0)'
        g.fillRect(0, band_y, F['W'], F['H'] - band_y)
        band_h = F['H'] - band_y
        fam = lambda n: f'{n}px Impact, "Arial Black", Rajdhani, sans-serif'
        px = _jr(band_h * 1.0)
        g.font = fam(px)
        w = g.measureText(amount).width
        if w > F['W'] * 0.96:
            px = math.floor(px * (F['W'] * 0.96) / w)
            g.font = fam(px)
        g.textAlign = 'center'
        g.textBaseline = 'middle'
        g.fillStyle = 'rgb(0,0,255)'
        g.fillText(amount, F['W'] / 2, band_y + band_h * 0.54)
        g.fillStyle = 'rgb(150,0,0)'
        g.fillRect(16, band_y + 3, F['W'] - 32, 4)
        g.fillRect(16, F['H'] - 7, F['W'] - 32, 4)
        return g.to_float()

    def screen_mat(self, name, img, tint_hex, mode, power_key):
        """race.js screenMat: the face's traces with data flowing outward, live irises glancing at the other screen,
        the amount in the screen's own hue; fear tears in bands and pulses, worship breathes; LED cells, a scan."""
        F = self.FACE

        def build(nb):
            q = nb.uv()
            t = self.u(nb, 'time')
            fear = mode == 'fear'
            if fear:
                band = nb.floor(q.y * 46.0)
                tear = (nb.step(0.9, nb.hash(nb.abs(band + nb.floor(t * 11.0) * 57.0))) * (nb.hash(band + 3.0) - 0.5) * 0.035)
                qx = q.x + tear
            else:
                qx = q.x
            cuv = nb.vec2(qx, 1.0 - q.y)
            s, _a = nb.tex(img, cuv, ext='CLIP')
            lines, phase, fill_b = s.x, s.y, s.z
            in_band = nb.step(q.y, 1.0 - self.BAND_V + 0.004)
            flow = nb.smoothstep(0.75, 1.0, nb.sin(phase * 26.0 - t * 3.2)) * 0.8 + 0.55
            face_i = lines * flow + fill_b * (1.0 - in_band) * 0.55
            eye_i = 0.0
            for ex, ey in self.EYE:
                c = (ex / F['W'], ey / F['H'], 0.0)
                gz = nb.vec2(self.u(nb, 'gaze') * (0.010 if fear else -0.010), 0.0)
                dd = (cuv - (gz + c)) * (F['W'] / F['H'], 1.0, 0.0)
                r = nb.length(dd)
                a = nb.atan2(dd.y, dd.x)
                blades = nb.sin(a * 9.0 + t * (2.6 if fear else 0.8)) * 0.5 + 0.5
                ring = nb.smoothstep(0.034, 0.030, r) * nb.smoothstep(0.020, 0.024, r) * (blades * 0.6 + 0.4)
                pupil = nb.smoothstep(0.012, 0.004, r) * 2.2
                lid = nb.smoothstep(0.042, 0.03, nb.abs(dd.y * 1.6)) * nb.smoothstep(0.075, 0.05, r)
                eye_i = eye_i + (ring + pupil) * lid
            text = fill_b * in_band
            tint = lin_hex(tint_hex)
            text_k = 2.1 if fear else 1.15
            mixc = tuple(a * 0.92 + b * 0.08 for a, b in zip(tint, (1.0, 0.95, 0.85)))
            col = nb.v(tint) * (face_i * (2.0 if fear else 1.5) + eye_i * 4.2) + nb.v(mixc) * text * text_k
            pulse = (nb.smoothstep(0.6, 1.0, nb.sin(t * 5.2)) * 0.35 + 0.85) if fear else (nb.sin(t * 1.1) * 0.12 + 1.0)
            col = col * pulse
            cells = q * (320.0, 213.0, 0.0)
            # fwidth(cells.x): the LED cells per pixel, from the distance and the camera's pixel angle (keyed)
            vd = V(nb, nb.node('ShaderNodeCameraData').outputs['View Distance'], False)
            fw = vd * self.u(nb, 'px') * (320.0 / D['bill_a']['w'])
            fr = nb.fract(cells) - (0.5, 0.5, 0.0)
            led = nb.smoothstep(0.5, 0.25, nb.length(nb.vec2(fr.x, fr.y))) * 0.6 + 0.4
            led_k = nb.mix(led, 0.75, nb.smoothstep(0.25, 0.6, fw))
            scan = nb.sin(q.y * 9.0 - t * 1.7) * 0.06 + 0.94
            base = nb.v(tint) * 0.035
            return (base + col * led_k * scan) * self.u(nb, power_key)
        return unlit(name, build)

    def _billboards(self):
        F = self.FACE
        self.EYE = [(F['cx'] + (x - 512) * F['s'], F['cy'] + (y - 540) * F['s']) for x, y in ((415, 470), (609, 470))]
        out = {}
        am_a, am_b = self.opts['amounts']
        for key, B, amount, tint_hex, mode, pk in (('a', D['bill_a'], am_a, '#ffb43c', 'worship', 'bill_a'),
                                                  ('b', D['bill_b'], am_b, '#ff2a1a', 'fear', 'bill_b')):
            arr = self.billboard_canvas(amount)
            img = image_from_array(f'race:billboard_{key}', arr, 'Non-Color', top_first=False)
            grp = empty(f'race:billboard_{key}', parent=self.group, collection=self.col, pos=(B['x'], 0, B['z']),
                        q=quat_axis_angle((0, 1, 0), B['yaw']))
            sm = self.screen_mat(f'race:screen_{key}', img, tint_hex, mode, pk)
            scr = self.obj(f'race:screen_{key}', plane_geo(B['w'], B['h']).transformed(M4(0, B['y'], 0.35)), sm, parent=grp)
            _no_shadow(scr)
            fg = GB()
            hw, hh = B['w'] / 2, B['h'] / 2
            box_quads(fg, -hw - 0.4, B['y'] - hh - 0.4, -0.6, hw + 0.4, B['y'] + hh + 0.4, 0.3, (0, 0, 0, 0), bottom=True)
            for k in range(7):
                fg.add(box_geo(0.35, B['h'] + 0.8, 0.35), M4(-hw + B['w'] * k / 6, B['y'], -1.1))
            for k in range(6):
                xa = -hw + B['w'] * k / 6
                xb = xa + B['w'] / 6
                for y0, y1 in ((B['y'] - hh, B['y'] + hh), (B['y'] + hh, B['y'] - hh)):
                    L = math.hypot(xb - xa, y1 - y0)
                    fg.add(box_geo(0.18, L, 0.18), M4((xa + xb) / 2, (y0 + y1) / 2, -1.1, 0, 0, math.atan2(-(xb - xa), y1 - y0)))
            for x in (-hw * 0.55, hw * 0.55):
                fg.add(cylinder_geo(0.75, 0.9, B['y'] - hh - D['ground'], 16), M4(x, (B['y'] - hh + D['ground']) / 2, -1.0))
            fg.add(box_geo(B['w'] + 1.0, 0.12, 1.4), M4(0, B['y'] - hh - 0.6, 0.5))
            for k in range(6):
                fg.add(box_geo(0.5, 0.35, 0.4), M4(-hw + 2 + k * (B['w'] - 4) / 5, B['y'] - hh - 0.35, 1.0, -0.5, 0, 0))
            frame = self.obj(f'race:billboardFrame_{key}', fg.build(), self.mats['steel'], parent=grp)
            out[key] = {'group': grp, 'screen': scr, 'material': sm, 'texture': img, 'amount': amount, 'mode': mode,
                        'tint': tint_hex, 'frame': frame}
        self.parts['billboards'] = out

    # ------------------------------------------------------------------------------------------- the car
    def _car_materials(self):
        """The 1908 racer's materials, from race.js (positionLocal = car space for the body, wheel space for the
        wheels). Their lamp-field emission and lamp glints are the real lamps' light and highlights here."""
        M = {}
        u = self.u

        def P0(nb):
            return nb.local3()

        m = new_material('race:car_paint')
        nb = NB(m.node_tree)
        p = P0(nb)
        n = self.nz(nb, nb.vec2(p.x + p.z, p.y + p.z * 0.3), 1.7)
        n2 = self.nz(nb, nb.vec2(p.x * 1.3 + p.z, p.y), 9.0)
        low = nb.smoothstep(0.95, 0.5, p.y)
        filth = nb.smoothstep(0.45, 0.8, n.r + low * 0.45) * low
        st = nb.step
        louv = st(0.3, nb.abs(p.x)) * st(1.0, p.z) * st(p.z, 1.72) * st(0.76, p.y) * st(p.y, 1.04) * st(p.y, 1.1)
        slot = nb.smoothstep(0.30, 0.22, nb.fract(p.z / 0.07)) * louv
        red = nb.v(lin_hex('#bd1b12')) * (n2.b * 0.12 + 0.94)
        albedo = nb.mix(nb.mix(red, lin_hex('#2b1a12'), filth * 0.85), lin_hex('#090303'), slot)
        nloc = nb.three(V(nb, _vt(nb, nb.geom('Normal'), 'WORLD', 'OBJECT'), True))
        up = nb.smoothstep(0.4, 0.9, nb.normalize(nloc).y)
        bead = nb.smoothstep(0.72, 0.9, self.nz(nb, nb.vec2(p.x, p.z), 14.0).b) * up * u(nb, 'wet')
        nrm = nb.bump(bead * 0.0012 + n.b * 0.0004 - slot * 0.004)
        output(nb, principled(nb, albedo, nb.mix(0.32, 0.75, filth) + (n2.b - 0.5) * 0.06, 0.0, nrm,
                              coat=1.0 - filth * 0.8, coat_rough=n2.g * 0.06 + 0.07, emission=self._dose(nb, albedo, 0.7)))
        M['paint'] = m

        m = new_material('race:car_brass')
        nb = NB(m.node_tree)
        p = P0(nb)
        n = self.nz(nb, nb.vec2(p.x + p.y, p.z + p.y), 6.0)
        tarn = nb.smoothstep(0.55, 0.85, n.r)
        alb = nb.mix(lin_hex('#e0b158'), lin_hex('#6b5a2c'), tarn * 0.75)
        output(nb, principled(nb, alb, nb.mix(0.22, 0.55, tarn), 1.0, emission=self._dose(nb, alb, 0.425)))
        M['brass'] = m
        M['steel'] = self.steel_mat('race:car_steel', tint='#1c1d1f', rough=0.45, metal=0.8, rust=0.35)

        m = new_material('race:car_exhaust')
        nb = NB(m.node_tree)
        p = P0(nb)
        heat = nb.smoothstep(0.6, 1.5, p.z)
        n = self.nz(nb, nb.vec2(p.z, p.y + p.x), 5.0)
        albedo = nb.mix(nb.mix(lin_hex('#4a2a17'), lin_hex('#2d2f3a'), heat), lin_hex('#3d2a4a'), heat * n.r)
        output(nb, principled(nb, albedo * (n.b * 0.4 + 0.75), nb.mix(0.7, 0.4, heat), 0.85,
                              emission=self._dose(nb, albedo, 0.7)))
        M['exh'] = m

        m = new_material('race:car_leather_black')
        nb = NB(m.node_tree)
        a = nb.attr('aux', out='Color')
        q = nb.uv() * (7.0, 4.0, 0.0)
        dia = nb.vec2(q.x + q.y, q.x - q.y)
        cell = nb.abs(nb.fract(dia) - (0.5, 0.5, 0.0))
        tuft = a.x * nb.smoothstep(0.08, 0.0, nb.min(cell.x, cell.y))
        n = self.nz(nb, nb.uv(), 3.0)
        alb = nb.v(lin_hex('#14090a')) * (n.r * 0.4 + 0.8)
        output(nb, principled(nb, alb, n.b * 0.2 + 0.42 + tuft * 0.2, 0.0, nb.bump(tuft * -0.006 + n.b * 0.0006),
                              emission=self._dose(nb, alb, 0.7)))
        M['leatherK'] = m

        m = new_material('race:car_leather_brown')
        nb = NB(m.node_tree)
        p = P0(nb)
        n = self.nz(nb, nb.vec2(p.x + p.z, p.y), 4.0)
        alb = nb.v(lin_hex('#4a2814')) * (n.r * 0.5 + 0.7)
        output(nb, principled(nb, alb, n.g * 0.25 + 0.5, 0.0, nb.bump(n.g * 0.0015), emission=self._dose(nb, alb, 0.7)))
        M['leatherB'] = m

        def wood(name, smear):
            m = new_material(name)
            nb = NB(m.node_tree)
            p = P0(nb)
            r = nb.length(nb.vec2(p.y, p.z))
            a = nb.atan2(p.z, p.y)
            gc = nb.vec2(r * 40.0, a * 3.0) if smear else nb.vec2((p.x + p.z) * 30.0, p.y * 3.0)
            grain = self.nz(nb, gc, 0.05).g
            albedo = nb.mix(lin_hex('#7a4a20'), lin_hex('#b37a3c'), grain)
            h = grain * 0.0005
            alpha = None
            if smear:
                # artillery spokes under the camera's shutter: each spoke box-blurred by the wheel's turn during the
                # exposure (smear radians): slow wheels show spokes, fast ones a translucent blur, never strobing
                NS = 12
                SP = TAU / NS
                half_w = nb.mix(0.030, 0.021, nb.clamp((r - 0.09) / 0.21)) / nb.max(r, 0.05)
                w = half_w * 2.0
                sm = u(nb, 'smear')
                dl = nb.max(sm, 1e-4)
                ac = a + sm * 0.5
                d = nb.abs(nb.fract(ac / SP + 0.5) - 0.5) * SP
                ov = nb.max(nb.min(half_w, d + dl * 0.5) - nb.max(-half_w, d - dl * 0.5), 0.0)
                cov = nb.clamp(ov / dl) * nb.step(0.075, r) * nb.step(r, 0.315)
                hub = nb.step(r, 0.105)
                alpha = nb.max(cov, hub)
                uu = nb.clamp(d / half_w)
                h = h + nb.sqrt(nb.max(1.0 - uu * uu, 0.0)) * 0.01 * (1.0 - nb.clamp(dl / w))
            output(nb, principled(nb, albedo, grain * 0.15 + 0.32, 0.0, nb.bump(h), alpha=alpha,
                                  emission=self._dose(nb, albedo, 0.53)))
            if smear:
                m.use_transparent_shadow = True
            return m
        M['wood'] = wood('race:car_wood', False)
        M['spokes'] = wood('race:car_spokes', True)

        m = new_material('race:car_rubber')
        nb = NB(m.node_tree)
        p = P0(nb)
        r = nb.length(nb.vec2(p.y, p.z))
        tread = nb.smoothstep(0.43, 0.445, r)
        rib = (nb.sin(p.x * 160.0) * 0.5 + 0.5) * tread
        n = self.nz(nb, nb.vec2(nb.atan2(p.z, p.y) * 3.0, p.x * 8.0))
        grime = nb.smoothstep(0.35, 0.75, n.r + tread * 0.35)
        alb = nb.mix(lin_hex('#b8b09c'), lin_hex('#3a3128'), grime * 0.75)
        output(nb, principled(nb, alb, nb.mix(0.75, 0.45, u(nb, 'wet') * tread), 0.0, nb.bump(rib * 0.0015),
                              emission=self._dose(nb, alb, 0.53)))
        M['rubber'] = m

        self.num_img = image_from_array('race:radiator_number', radiator_number_canvas(), 'Non-Color', top_first=False)
        m = new_material('race:car_core')
        nb = NB(m.node_tree)
        p = P0(nb)
        qx, qy = p.x * 115.0, p.y * 100.0
        hx = nb.abs(nb.fract(qx + nb.step(0.5, nb.fract(qy * 0.5)) * 0.5) - 0.5)
        hy = nb.abs(nb.fract(qy) - 0.5)
        cellv = nb.max(hx, hy)
        num_c, _ = nb.tex(self.num_img, nb.vec2(p.x / 0.6 + 0.5, 1.0 - (p.y - 0.56) / 0.62), ext='CLIP')
        num = num_c.x * nb.step(1.95, p.z)
        alb = nb.mix(lin_hex('#0a0a0a'), lin_hex('#d8d4c8'), num)
        output(nb, principled(nb, alb, 0.55, 0.5, nb.bump(nb.smoothstep(0.38, 0.5, cellv) * -0.004),
                              emission=self._dose(nb, alb, 0.86)))
        M['core'] = m

        m = new_material('race:car_glass')
        nb = NB(m.node_tree)
        output(nb, principled(nb, lin_hex('#050608'), 0.05, 0.2))
        M['glass'] = m

        m = new_material('race:car_chain')
        nb = NB(m.node_tree)
        link_u = nb.uv().x * 114.0 + u(nb, 'chain_run')
        link = nb.smoothstep(0.2, 0.5, nb.abs(nb.fract(link_u) - 0.5) * 2.0)
        alb = nb.mix(lin_hex('#141414'), lin_hex('#4a4642'), link)
        output(nb, principled(nb, alb, link * 0.2 + 0.4, 0.9, nb.bump(link * 0.003), emission=self._dose(nb, alb, 0.75)))
        M['chain'] = m

        def lens_build(nb):
            r = nb.length(nb.uv() - (0.5, 0.5, 0.0)) * 2.0
            return nb.mix(lin_hex('#fff0c8'), lin_hex('#ffad55'), nb.smoothstep(0.15, 0.95, r)) * (u(nb, 'headlamps') * 3.2)
        M['lens'] = unlit('race:car_lamps', lens_build)
        self.car_mats = M
        for k, v in M.items():
            self.mats['car_' + k] = v
        return M

    def _car(self):
        M = self._car_materials()
        car = {'group': empty('race:car', parent=self.group, collection=self.col), 'wheels': []}
        car['group'].rotation_mode = 'YXZ'
        body = empty('race:carBody', parent=car['group'], collection=self.col)
        body.rotation_mode = 'YXZ'
        car['body'] = body
        B = {k: GB() for k in ('paint', 'brass', 'steel', 'exh', 'leatherK', 'leatherB', 'wood', 'core', 'glass')}
        V3 = lambda x, y, z: np.array([x, y, z], float)

        def bar(gb, pts, w, h, aux=(0, 0, 0, 0)):
            pos, idx = [], []
            side = V3(1, 0, 0)
            for i in range(len(pts)):
                p = np.asarray(pts[i], float)
                qn, o = np.asarray(pts[min(len(pts) - 1, i + 1)], float), np.asarray(pts[max(0, i - 1)], float)
                tng = _norm(qn - o)
                up = _norm(-np.cross(tng, side))
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    pos.append(p + side * (sx * w / 2) + up * (sy * h / 2))
            for i in range(len(pts) - 1):
                for k in range(4):
                    a, b = i * 4 + k, i * 4 + (k + 1) % 4
                    c, d = a + 4, b + 4
                    idx += [(a, c, b), (b, c, d)]
            g = Geo(pos, np.zeros((len(pos), 3)), np.zeros((len(pos), 2)), idx).compute_normals()
            gb.add(g, None, aux)

        def tube(gb, pts, r, seg=24, rad=8, closed=False, aux=(0, 0, 0, 0)):
            gb.add(tube_geo(CatmullRom(pts, closed), seg, r, rad, closed), None, aux)

        def loft(gb, rings, aux=(0, 0, 0, 0), cap=True):
            n = len(rings[0])
            pos, uvs, idx = [], [], []
            for i, ring in enumerate(rings):
                for j, p in enumerate(ring):
                    pos.append(p)
                    uvs.append((i / (len(rings) - 1), j / n))
            for i in range(len(rings) - 1):
                for j in range(n):
                    a, b = i * n + j, i * n + (j + 1) % n
                    c, d = a + n, b + n
                    idx += [(a, b, c), (b, d, c)]
            if cap:
                for ri, flip in ((0, True), (len(rings) - 1, False)):
                    ctr = np.mean(np.array(rings[ri], float), axis=0)
                    ci = len(pos)
                    pos.append(ctr)
                    uvs.append((0, 0))
                    for j in range(n):
                        a, b = ri * n + j, ri * n + (j + 1) % n
                        idx.append((ci, b, a) if flip else (ci, a, b))
            g = Geo(pos, np.zeros((len(pos), 3)), uvs, idx).compute_normals()
            gb.add(g, None, aux)

        def bonnet_ring(z, hw, top, bot, rr):
            pts = [V3(hw, bot, z)]
            for cx, cy, a0, a1 in ((hw - rr, top - rr, 0, PI / 2), (-hw + rr, top - rr, PI / 2, PI)):
                for i in range(6):
                    a = a0 + (a1 - a0) * i / 5
                    pts.append(V3(cx + math.cos(a) * rr, cy + math.sin(a) * rr, z))
            pts.append(V3(-hw, bot, z))
            return pts

        wb = CAR['wb']
        # chassis: pressed-steel rails with dumb irons, cross members, leaf springs, axles
        for s in (-1, 1):
            bar(B['paint'], [V3(s * 0.40, 0.42, 2.12), V3(s * 0.40, 0.56, 1.95), V3(s * 0.40, 0.59, 1.2),
                             V3(s * 0.40, 0.59, -1.0), V3(s * 0.40, 0.58, -2.05)], 0.07, 0.17)
            for zc, yc in ((wb / 2, 0.5), (-wb / 2, 0.49)):
                for k in range(5):
                    L, y = 0.5 - k * 0.075, yc + 0.012 * k
                    pts = []
                    for i in range(11):
                        uu = -1 + 2 * i / 10
                        pts.append(V3(s * 0.40, y + 0.055 * uu * uu, zc + uu * L))
                    bar(B['steel'], pts, 0.055, 0.011)
        for z in (1.92, 0.55, -0.55, -1.95):
            box_quads(B['paint'], -0.40, 0.55, z - 0.04, 0.40, 0.62, z + 0.04, (0, 0, 0, 0), bottom=True)
        box_quads(B['paint'], -0.66, 0.41, wb / 2 - 0.035, 0.66, 0.48, wb / 2 + 0.035, (0, 0, 0, 0), bottom=True)
        tube(B['steel'], [V3(-0.62, 0.44, wb / 2 - 0.16), V3(0, 0.43, wb / 2 - 0.17), V3(0.62, 0.44, wb / 2 - 0.16)], 0.014, 12, 6)
        box_quads(B['steel'], -0.66, 0.41, -wb / 2 - 0.04, 0.66, 0.49, -wb / 2 + 0.04, (0, 0, 0, 0), bottom=True)
        B['steel'].add(cylinder_geo(0.07, 0.07, 1.12, 14), M4(0, 0.5, -0.45, 0, 0, PI / 2))
        B['steel'].add(sphere_geo(0.16, 16, 12), M4(0, 0.5, -0.45, 0, 0, 0, 1, 0.9, 0.9))
        for s in (-1, 1):
            B['steel'].add(cylinder_geo(0.09, 0.09, 0.03, 18), M4(s * 0.58, 0.5, -0.45, 0, 0, PI / 2))
        chain = GB()
        for s in (-1, 1):
            c1y, c1z, r1, c2y, c2z, r2 = 0.5, -0.45, 0.09, 0.45, -wb / 2, 0.24
            pts = [V3(s * 0.58, c1y + r1 * math.sin(-PI / 2 + PI * i / 10), c1z + r1 * math.cos(-PI / 2 + PI * i / 10)) for i in range(11)]
            pts += [V3(s * 0.58, c2y + r2 * math.sin(PI / 2 + PI * i / 16), c2z + r2 * math.cos(PI / 2 + PI * i / 16)) for i in range(17)]
            chain.add(tube_geo(CatmullRom(pts, True), 90, 0.013, 6, True), None, (0, 0, 0, 0))
        # exhaust: four headers out of the left bonnet side into a fat pipe along the side
        for k in range(4):
            z = 1.62 - k * 0.2
            tube(B['exh'], [V3(-0.33, 0.95, z), V3(-0.43, 0.94, z - 0.02), V3(-0.51, 0.82, z - 0.08),
                            V3(-0.53, 0.66, z - 0.16 - k * 0.02)], 0.032, 10, 8)
        tube(B['exh'], [V3(-0.53, 0.66, 1.5), V3(-0.53, 0.63, 1.0), V3(-0.52, 0.6, 0.0), V3(-0.52, 0.58, -1.2),
                        V3(-0.5, 0.6, -2.05), V3(-0.48, 0.66, -2.3)], 0.056, 40, 10)
        # radiator: a brass shell round a honeycomb core, filler cap; the number on the core
        box_quads(B['core'], -0.30, 0.56, 1.93, 0.30, 1.18, 2.02, (0, 0, 0, 0))
        ow, ot, ob, rr = 0.35, 1.235, 0.52, 0.07
        sh = Shape()
        sh.move_to(-ow, ob).line_to(ow, ob).line_to(ow, ot - rr).quadratic_curve_to(ow, ot, ow - rr, ot)
        sh.line_to(-ow + rr, ot).quadratic_curve_to(-ow, ot, -ow, ot - rr).close_path()
        hole = Shape()
        hole.move_to(-0.30, 0.56).line_to(-0.30, 1.18).line_to(0.30, 1.18).line_to(0.30, 0.56).close_path()
        sh.holes.append(hole)
        B['brass'].add(extrude_geo(sh, depth=0.14, bevel=True, bevel_thickness=0.012, bevel_size=0.01, bevel_segments=2,
                                   curve_segments=6), M4(0, 0, 1.9))
        B['brass'].add(cylinder_geo(0.042, 0.048, 0.08, 16), M4(0, 1.28, 1.97))
        B['brass'].add(cylinder_geo(0.055, 0.055, 0.025, 16), M4(0, 1.33, 1.97))
        # bonnet, straps, scuttle
        rings = [bonnet_ring(1.9 - (i / 10) * 1.6, 0.33 + (i / 10) * 0.03, 1.18 + (i / 10) * 0.02, 0.6, 0.075) for i in range(11)]
        loft(B['paint'], rings[::-1])
        for zc in (1.48, 0.82):
            uu = (1.9 - zc) / 1.6
            base = bonnet_ring(zc, 0.33 + uu * 0.03, 1.18 + uu * 0.02, 0.6, 0.075)
            sc = lambda rg, z: [V3(p[0] * 1.03, 0.6 + (p[1] - 0.6) * 1.02 + 0.004, z) for p in rg]
            loft(B['leatherB'], [sc(base, zc - 0.025), sc(base, zc + 0.025)], cap=False)
        srings = [bonnet_ring(0.3 - (i / 6) * 0.3, 0.36 + (i / 6) * 0.09, 1.2 + math.sin((i / 6) * PI * 0.5) * 0.12, 0.6,
                              0.075 + (i / 6) * 0.08) for i in range(7)]
        loft(B['paint'], srings[::-1])
        # cockpit: sides, rear bulkhead, a leather roll round the rim, wooden floor and dash
        for s in (-1, 1):
            box_quads(B['paint'], 0.43 if s > 0 else -0.46, 0.6, -1.18, 0.46 if s > 0 else -0.43, 0.97, 0.0, (0, 0, 0, 0))
        box_quads(B['paint'], -0.46, 0.6, -1.22, 0.46, 1.02, -1.16, (0, 0, 0, 0))
        tube(B['leatherK'], [V3(0.45, 0.99, 0.0), V3(0.45, 0.99, -1.18), V3(0.0, 1.03, -1.2), V3(-0.45, 0.99, -1.18),
                             V3(-0.45, 0.99, 0.0)], 0.032, 40, 8)
        box_quads(B['wood'], -0.43, 0.6, -1.16, 0.43, 0.63, 0.0, (0, 0, 0, 0))
        box_quads(B['wood'], -0.44, 0.97, -0.01, 0.44, 1.26, 0.03, (0, 0, 0, 0))
        for x, r in ((-0.25, 0.045), (-0.08, 0.035), (0.08, 0.035)):
            B['brass'].add(cylinder_geo(r, r, 0.03, 18), M4(x, 1.14, -0.02, PI / 2, 0, 0))
            B['glass'].add(circle_geo(r * 0.8, 18), M4(x, 1.14, -0.04, 0, PI, 0))
        B['brass'].add(cylinder_geo(0.03, 0.03, 0.22, 12), M4(-0.3, 1.12, -0.08))
        tube(B['brass'], [V3(-0.43, 1.05, -0.05), V3(-0.43, 1.16, -0.1), V3(-0.43, 1.16, -0.32), V3(-0.43, 1.03, -0.36)], 0.012, 12, 6)
        # seats: buttoned leather buckets
        for sx in (-0.24, 0.24):
            B['leatherK'].add(box_geo(0.42, 0.13, 0.46, 2, 1, 2), M4(sx, 0.7, -0.72), (1, 0, 0, 0))
            th0 = PI - 1.75
            B['leatherK'].add(cylinder_geo(0.235, 0.22, 0.52, 22, 1, True, th0, 3.5), M4(sx, 0.98, -0.78), (1, 0, 0, 0))
            B['leatherK'].add(cylinder_geo(0.258, 0.243, 0.52, 22, 1, True, th0, 3.5), M4(sx, 0.98, -0.78), (0, 0, 0, 0))
            rim = [V3(sx + math.sin(th0 + 3.5 * i / 14) * 0.247, 1.24, -0.78 + math.cos(th0 + 3.5 * i / 14) * 0.247) for i in range(15)]
            tube(B['leatherK'], rim, 0.022, 20, 6)
        # steering: a raked column, a wooden rim on brass spokes (right-hand drive)
        whl_c, whl_n, whl_r = V3(0.24, 1.3, -0.3), _norm((0, 0.62, -0.78)), 0.22
        col_base = V3(0.24, 0.66, 0.36)
        tube(B['steel'], [col_base, col_base + (whl_c - col_base) * 0.5, whl_c + whl_n * -0.02], 0.022, 6, 8)
        mw = compose(whl_c, quat_unit_vectors((0, 0, 1), whl_n), (1, 1, 1))
        B['wood'].add(torus_geo(whl_r, 0.018, 8, 40), mw)
        for k in range(4):
            B['brass'].add(box_geo(0.012, whl_r * 2, 0.008), mw @ M4(0, 0, 0, 0, 0, k * PI / 4 + PI / 8))
        B['brass'].add(cylinder_geo(0.035, 0.035, 0.04, 14), mw @ M4(0, 0, 0, PI / 2, 0, 0))
        # outside levers with the quadrant, and the bulb horn
        for z, h in ((-0.36, 0.62), (-0.56, 0.66)):
            tube(B['steel'], [V3(0.53, 0.6, z - 0.06), V3(0.535, 0.6 + h * 0.5, z - 0.02), V3(0.53, 0.6 + h, z + 0.04)], 0.012, 8, 6)
            B['brass'].add(sphere_geo(0.028, 12, 10), M4(0.53, 0.6 + h + 0.02, z + 0.04))
        bar(B['steel'], [V3(0.51, 0.62 + math.cos(-0.5 + i * 0.125) * 0.3, -0.42 + math.sin(-0.5 + i * 0.125) * 0.3) for i in range(9)], 0.01, 0.025)
        tube(B['brass'], [V3(0.42, 1.16, -0.05), V3(0.46, 1.1, 0.25), V3(0.43, 1.08, 0.55), V3(0.4, 1.09, 0.72)], 0.014, 16, 6)
        B['brass'].add(lathe_geo([(0.014, 0), (0.03, 0.08), (0.075, 0.14)], 16), M4(0.4, 1.09, 0.72, PI / 2, 0, 0))
        B['leatherK'].add(sphere_geo(0.048, 12, 10), M4(0.42, 1.17, -0.1, 0, 0, 0, 1, 1.15, 1))
        # tail: the bolster tank (red, brass bands, cap) and a spare strapped behind it
        B['paint'].add(cylinder_geo(0.23, 0.23, 0.96, 26), M4(0, 0.93, -1.46, 0, 0, PI / 2))
        for s in (-1, 1):
            B['paint'].add(sphere_geo(0.23, 20, 12, 0, TAU, 0, PI / 2), M4(s * 0.48, 0.93, -1.46, 0, 0, -s * PI / 2, 1, 0.35, 1))
        for x in (-0.3, 0.3):
            B['brass'].add(torus_geo(0.236, 0.011, 8, 32), M4(x, 0.93, -1.46, 0, PI / 2, 0))
        B['brass'].add(cylinder_geo(0.05, 0.05, 0.07, 16), M4(0.22, 1.18, -1.46))
        spare_m = M4(0, 0.74, -1.83)
        for x in (-0.18, 0.18):
            bar(B['leatherB'], [V3(x, 0.74 + math.sin(PI * 0.15 + (i / 11) * PI * 0.7) * 0.45,
                                   -1.83 + math.cos(PI * 0.15 + (i / 11) * PI * 0.7) * 0.02) for i in range(12)], 0.04, 0.006)
        for x in (-0.25, 0.25):
            bar(B['leatherB'], [V3(x, 0.93 + math.sin((i / 9) * PI) * 0.245, -1.46 + math.cos((i / 9) * PI) * 0.245) for i in range(10)], 0.035, 0.006)
        # two brass acetylene headlamps on forks either side of the radiator
        lens = GB()
        for s in (-1, 1):
            lx, ly, lz = s * 0.47, 0.97, 2.0
            B['brass'].add(cylinder_geo(0.105, 0.11, 0.2, 22, 1, False), M4(lx, ly, lz - 0.02, PI / 2, 0, 0))
            B['brass'].add(torus_geo(0.106, 0.014, 8, 26), M4(lx, ly, lz + 0.085))
            B['brass'].add(cylinder_geo(0.025, 0.03, 0.09, 10), M4(lx, ly + 0.14, lz - 0.05))
            B['brass'].add(cone_geo(0.045, 0.04, 10), M4(lx, ly + 0.2, lz - 0.05))
            bar(B['steel'], [V3(lx - s * 0.02, 0.6, 1.97), V3(lx, 0.75, 1.98), V3(lx, 0.86, 1.98)], 0.03, 0.03)
            lens.add(circle_geo(0.094, 24), M4(lx, ly, lz + 0.082))
        mats = {'paint': M['paint'], 'brass': M['brass'], 'steel': M['steel'], 'exh': M['exh'], 'leatherK': M['leatherK'],
                'leatherB': M['leatherB'], 'wood': M['wood'], 'core': M['core'], 'glass': M['glass']}
        car['meshes'] = {}
        for k, gb in B.items():
            if gb.v:
                car['meshes'][k] = self.obj('race:car_' + k, gb.build(), mats[k], parent=body)
        car['meshes']['chains'] = self.obj('race:car_chains', chain.build(), M['chain'], parent=body)
        car['meshes']['lamps'] = self.obj('race:car_lamps', lens.build(), M['lens'], parent=body)
        sp = GB()
        sp.add(torus_geo(0.39, 0.058, 12, 40), spare_m)
        car['meshes']['spare'] = self.obj('race:car_spare', sp.build(), M['rubber'], parent=body)
        # wheels: pale tyre, wooden felloe on a steel band, the smeared spokes, brass hub; the rear wheels carry
        # the chain sprocket ring. Wheel space: the axle along X.
        for x, z, rear in ((CAR['track'] / 2, wb / 2, False), (-CAR['track'] / 2, wb / 2, False),
                           (CAR['track'] / 2, -wb / 2, True), (-CAR['track'] / 2, -wb / 2, True)):
            pivot = empty('race:wheelPivot', parent=car['group'], collection=self.col, pos=(x, CAR['R'], z))
            spin = empty('race:wheelSpin', parent=pivot, collection=self.col)
            spin.rotation_mode = 'XYZ'
            s = math.copysign(1, x)
            tG, wG, sG, bG, stG = GB(), GB(), GB(), GB(), GB()
            tG.add(torus_geo(0.39, 0.06, 12, 44), M4(0, 0, 0, 0, PI / 2, 0))
            wG.add(torus_geo(0.318, 0.026, 8, 40), M4(0, 0, 0, 0, PI / 2, 0))
            stG.add(torus_geo(0.337, 0.013, 6, 40), M4(0, 0, 0, 0, PI / 2, 0))
            sG.add(circle_geo(0.33, 48), M4(s * 0.005, 0, 0, 0, PI / 2, 0))
            bG.add(cylinder_geo(0.075, 0.095, 0.2, 18), M4(0, 0, 0, 0, 0, PI / 2))
            bG.add(cylinder_geo(0.06, 0.07, 0.06, 18), M4(s * 0.12, 0, 0, 0, 0, PI / 2))
            if rear:
                stG.add(torus_geo(0.24, 0.018, 6, 40), M4(-s * 0.12, 0, 0, 0, PI / 2, 0))
            for gb, mat, nm in ((tG, M['rubber'], 'tyre'), (wG, M['wood'], 'felloe'), (sG, M['spokes'], 'spokes'),
                                (bG, M['brass'], 'hub'), (stG, M['steel'], 'band')):
                self.obj('race:wheel_' + nm, gb.build(), mat, parent=spin)
            car['wheels'].append({'pivot': pivot, 'spin': spin, 'front': not rear})
        self.car = car
        self.parts['car'] = car['group']
        self.parts['car_rig'] = car
        car['path'], car['length'], car['CR'] = self.path, self.path.length(), CR
        car['crash_pose'] = crash_pose

    # ------------------------------------------------------------------------------------------- the riders
    def _riders(self):
        """The driver (right) and the riding mechanic (left): dusters, leather helmets, brass goggles and white silk
        scarves over their faces, the scarf tails streaming (a Geometry Nodes flutter on keyed time and speed)."""
        u = self.u
        m = new_material('race:rider_coat')
        nb = NB(m.node_tree)
        a = nb.attr('aux', out='Color')
        p = nb.local3()
        n = self.nz(nb, nb.vec2((p.x + p.z) * 3.0, p.y * 3.0))
        folds = self.nz(nb, nb.vec2(p.x * 2.0 + p.z, p.y * 9.0)).g
        albedo = nb.mix(lin_hex('#8b7451'), lin_hex('#4c4e44'), a.x) * (n.r * 0.35 + 0.75)
        output(nb, principled(nb, albedo, 0.78, 0.0, nb.bump(folds * 0.006)))
        coat = m
        # white silk catches every lamp it streams through (race.js: the scarves take the field twice, the streaming
        # tails 2.4 times on their face and 1.2 through the silk): the riders' signature at speed
        m = new_material('race:rider_silk')
        nb = NB(m.node_tree)
        output(nb, principled(nb, lin_hex('#ece6d8'), 0.38, 0.0, emission=self._dose(nb, nb.v(lin_hex('#ece6d8')), 1.0)))
        silk = m
        m = new_material('race:rider_silk_tail')
        nb = NB(m.node_tree)
        output(nb, principled(nb, lin_hex('#ece6d8'), 0.38, 0.0,
                              emission=self._dose(nb, nb.v(lin_hex('#ece6d8')), 1.4, k_back=1.2)))
        silk_tail = m
        RB = {k: GB() for k in ('coat', 'helmet', 'silk', 'tail', 'brass', 'glass')}
        V3 = lambda x, y, z: np.array([x, y, z], float)
        ell = lambda cx, cy, cz, w, d, n=18: [V3(cx + math.cos(i / n * TAU) * w / 2, cy, cz + math.sin(i / n * TAU) * d / 2) for i in range(n)]
        tails = []

        def rider(sx, role, tint):
            zc, lean = -0.74, 0.30
            z_at = lambda y: zc + (y - 0.74) * lean
            rings = [ell(sx, y, z_at(y), w, d) for y, w, d in ((0.74, 0.36, 0.25), (0.9, 0.33, 0.23), (1.06, 0.37, 0.25),
                                                               (1.2, 0.43, 0.25), (1.3, 0.40, 0.21), (1.355, 0.15, 0.14))]
            n = len(rings[0])
            pos = [p for r in rings for p in r]
            idx = []
            for i in range(len(rings) - 1):
                for j in range(n):
                    a_, b_ = i * n + j, i * n + (j + 1) % n
                    idx += [(a_, a_ + n, b_), (b_, a_ + n, b_ + n)]
            RB['coat'].add(Geo(pos, np.zeros((len(pos), 3)), np.zeros((len(pos), 2)), idx).compute_normals(), None, (tint, 0, 0, 0))
            RB['coat'].add(torus_geo(0.085, 0.032, 8, 18), M4(sx, 1.35, z_at(1.35), PI / 2, 0, 0), (tint, 0, 0, 0))
            hz = z_at(1.49) + 0.02
            RB['helmet'].add(sphere_geo(0.108, 20, 14), M4(sx, 1.495, hz, 0, 0, 0, 0.92, 1.06, 1.1))
            for s in (-1, 1):
                RB['helmet'].add(box_geo(0.02, 0.07, 0.06), M4(sx + s * 0.098, 1.45, hz - 0.005))
            RB['silk'].add(cylinder_geo(0.098, 0.104, 0.12, 18), M4(sx, 1.415, hz + 0.008))
            gq = M4(sx, 1.515, hz + 0.105)
            for s in (-1, 1):
                RB['brass'].add(torus_geo(0.031, 0.008, 8, 18), gq @ M4(s * 0.04, 0, 0, 0, s * 0.22, 0))
                RB['brass'].add(cylinder_geo(0.03, 0.033, 0.03, 18, 1, True), gq @ M4(s * 0.04, 0, -0.012, PI / 2, 0, 0))
                RB['glass'].add(circle_geo(0.029, 18), gq @ M4(s * 0.04, 0, 0.004, 0, s * 0.22, 0))
            RB['helmet'].add(torus_geo(0.104, 0.008, 6, 26), M4(sx, 1.515, hz, PI / 2, 0, 0, 0.94, 1.12, 1))
            sh_y, sh_z = 1.26, z_at(1.26)
            if role == 'driver':
                c, nW, right = V3(0.24, 1.3, -0.3), _norm((0, 0.62, -0.78)), V3(1, 0, 0)
                up_w = _norm(-np.cross(nW, right))
                hands = [c + right * -0.19 + up_w * 0.1, c + right * 0.19 + up_w * 0.1]
            else:
                hands = [V3(-0.43, 1.16, -0.2), V3(-0.3, 1.18, -0.08)]
            for i, s in enumerate((-1, 1)):
                shp = V3(sx + s * 0.2, sh_y, sh_z)
                hd = hands[i]
                el = shp + (hd - shp) * 0.5 + V3(s * 0.08, -0.12, -0.04)
                RB['coat'].add(tube_geo(CatmullRom([shp, el, hd + V3(0, 0, -0.06)]), 16, 0.05, 8, False), None, (tint, 0, 0, 0))
                dr = _norm(hd - el)
                gm = compose(hd + dr * -0.07, quat_unit_vectors((0, 1, 0), dr), (1, 1, 1))
                RB['helmet'].add(cylinder_geo(0.045, 0.062, 0.11, 12), gm)
                RB['helmet'].add(sphere_geo(0.045, 10, 8), M4(hd[0], hd[1], hd[2], 0, 0, 0, 1, 0.8, 1.3))
            tg = plane_geo(0.15, 1.25, 1, 18)
            dd = (0.625 - tg.P[:, 1]) / 1.25
            P = np.stack([sx + tg.P[:, 0] * (1 - 0.5 * dd) + (0.04 if role == 'driver' else -0.04) * dd,
                          1.42 + 0.08 * dd, hz - 0.09 - dd * 1.25], 1)
            g = Geo(P, tg.N, tg.UV, tg.I).compute_normals()
            start = RB['tail'].v
            RB['tail'].add(g, None, (0, 0.0 if role == 'driver' else 2.1, 0, 0))
            tails.append((start, dd))

        rider(0.24, 'driver', 0)
        rider(-0.24, 'mechanic', 1)
        tail_g = RB['tail'].build()
        for start, dd in tails:
            tail_g.A[start:start + len(dd), 0] = dd
        rg = empty('race:riders', parent=self.car['body'], collection=self.col)
        out = {}
        for k, mat, nm in (('coat', coat, 'coats'), ('helmet', self.car_mats['leatherB'], 'helmets'), ('silk', silk, 'scarves'),
                           ('brass', self.car_mats['brass'], 'goggles'), ('glass', self.car_mats['glass'], 'lenses')):
            out[nm] = self.obj('race:rider_' + nm, RB[k].build(), mat, parent=rg)
        tail = self.obj('race:rider_scarfTails', tail_g, silk_tail, parent=rg)
        self._scarf_flutter(tail)
        out['scarfTails'] = tail
        self.car['riders'] = rg
        self.parts['riders'] = rg
        self.parts['rider_meshes'] = out

    def _gn(self, ob, name, inputs):
        """A Geometry Nodes modifier on ob with float / vector inputs [(name, default)] -> (tree, nb, gin, gout)."""
        tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        for nm, dv in inputs:
            s = tree.interface.new_socket(nm, in_out='INPUT',
                                          socket_type='NodeSocketVector' if isinstance(dv, tuple) else 'NodeSocketFloat')
            s.default_value = dv
        nb = NB(tree)
        gin = nb.node('NodeGroupInput')
        gout = nb.node('NodeGroupOutput')
        mod = ob.modifiers.new(name, 'NODES')
        mod.node_group = tree
        for item in tree.interface.items_tree:
            if item.in_out == 'INPUT' and item.socket_type != 'NodeSocketGeometry':
                # Blender 5.2 keeps a nodes modifier's inputs at mod.properties.inputs.<identifier>.value; the slots
                # are rebuilt when the tree changes, so they are looked up when used, never kept
                self.gn_inputs.append((ob, mod.name, item.identifier, _GN_U.get(item.name, item.name)))
        return tree, nb, gin, gout, mod

    def _scarf_flutter(self, ob):
        tree, nb, gin, gout, mod = self._gn(ob, 'race:scarf_flutter', [('time', 0.0), ('scarf_speed', 0.0)])
        aux = nb.node('GeometryNodeInputNamedAttribute', data_type='FLOAT_COLOR')
        aux.inputs['Name'].default_value = 'aux'
        a = nb.sep(V(nb, aux.outputs['Attribute'], True))
        d, ph = a[0], a[1]
        t = V(nb, gin.outputs['time'], False)
        sp = V(nb, gin.outputs['scarf_speed'], False)
        f1 = nb.sin(d * 9.0 - t * 17.0 + ph) * 0.07
        f2 = nb.sin(d * 5.0 - t * 11.0 + ph * 2.0) * 0.05
        droop = (1.0 - sp) * d * d * 0.55
        # three's (f2 d, f1 d (0.8 speed + 0.2) - droop, 0) in Blender's axes
        off = nb.vec3(f2 * d, 0.0, f1 * d * (sp * 0.8 + 0.2) - droop)
        setp = nb.node('GeometryNodeSetPosition')
        nb.links.new(gin.outputs['Geometry'], setp.inputs['Geometry'])
        nb.links.new(off.out, setp.inputs['Offset'])
        nb.links.new(setp.outputs['Geometry'], gout.inputs['Geometry'])

    # ------------------------------------------------------------------------------------------- contact shadow
    def _contact_shadow(self):
        def build(nb):
            q = (nb.uv() - (0.5, 0.5, 0.0)) * 2.0
            op = nb.smoothstep(1.0, 0.25, nb.length(q)) * 0.8 * self.u(nb, 'car_shadow')
            return (nb.v((0.0, 0.0, 0.0)), op)
        m = unlit('race:car_shadow', build)
        pad = self.obj('race:carShadow', plane_geo(1.9, 4.6).transformed(M4(0, 0, 0, -PI / 2, 0, 0)), m)
        pad.rotation_mode = 'XYZ'
        _no_shadow(pad)
        _no_reflection(pad)
        self.car['shadow'] = pad

    # ------------------------------------------------------------------------------------------- the roadworks
    def _works(self):
        u = self.u
        m = new_material('race:works_paint')
        nb = NB(m.node_tree)
        a = nb.attr('aux', out='Color')
        p = nb.local3()
        bands_d = nb.step(0.5, nb.fract(p.y * 3.4))
        bands_b = nb.step(0.5, nb.fract((p.x + p.y) * 2.6))
        is_d = nb.step(a.x, 0.5)
        is_b = nb.step(0.5, a.x) * nb.step(a.x, 1.5)
        is_body = nb.step(1.5, a.x)
        band = bands_d * is_d + bands_b * is_b
        n = self.nz(nb, nb.vec2(p.x + p.z, p.y), 3.0)
        col = nb.mix(nb.mix(lin_hex('#e8501c'), lin_hex('#e9e6dc'), band), lin_hex('#2b2d30'), is_body) * (n.r * 0.3 + 0.8)
        grime = nb.smoothstep(0.35, 0.0, p.y) * 0.5 + nb.smoothstep(0.6, 0.9, n.g) * 0.3
        albedo = col * (1.0 - grime)
        retro = band * (1.0 - is_body)
        output(nb, principled(nb, albedo, grime * 0.3 + 0.5, 0.0, emission=albedo * retro * u(nb, 'headlamps') * 0.25))
        paint_w = m
        self.mats['works_paint'] = m
        wG, wSteel, wGlow = GB(), GB(), GB()
        debris_obs = []
        hit_i = 0
        for k, (x, z, uu, hit) in enumerate(drum_taper()):
            drum = GB()
            drum.add(cylinder_geo(0.28, 0.3, 0.9, 16), M4(0, 0.45, 0), (0, 0, 0, 0))
            drum.add(cylinder_geo(0.42, 0.42, 0.08, 16), M4(0, 0.04, 0), (2, 0, 0, 0))
            if hit:
                d = self.debris[hit_i]
                hit_i += 1
                g = empty('race:drum_hit', parent=self.group, collection=self.col, pos=(x, 0, z))
                g.rotation_mode = 'YZX'
                self.obj('race:drum_hit_mesh', drum.build(), paint_w, parent=g)
                debris_obs.append((g, d))
            else:
                wG.merge(drum, offset=(x, 0, z))
                wGlow.add(sphere_geo(0.075, 10, 8), M4(x, 1.0, z), (1.0, 0.62, 0.12, uu))
                wSteel.add(cylinder_geo(0.02, 0.02, 0.12, 6), M4(x, 0.94, z))
        bz = D['works']['barrier']

        def barricade(cx, hit):
            nonlocal hit_i
            legs, boards = GB(), GB()
            for sx in (-1.05, 1.05):
                for sz in (-1, 1):
                    legs.add(box_geo(0.06, 1.15, 0.06), M4(sx, 0.55, sz * 0.22, sz * 0.2, 0, 0), (2, 0, 0, 0))
            for y, h in ((1.0, 0.24), (0.6, 0.2)):
                boards.add(box_geo(2.4, h, 0.035), M4(0, y, 0), (1, 0, 0, 0))
            if hit:
                for gbx, nm in ((legs, 'race:barricade_legs'), (boards, 'race:barricade_boards')):
                    d = self.debris[hit_i]
                    hit_i += 1
                    g = empty(nm, parent=self.group, collection=self.col, pos=(cx, 0, bz))
                    g.rotation_mode = 'YZX'
                    self.obj(nm + '_mesh', gbx.build(), paint_w, parent=g)
                    debris_obs.append((g, d))
            else:
                wG.merge(legs, offset=(cx, 0, bz))
                wG.merge(boards, offset=(cx, 0, bz))

        barricade(-0.2, False)
        barricade(2.3, True)
        barricade(4.8, False)
        barricade(7.3, False)
        abx, abz = D['works']['board']
        box_quads(wG, abx - 0.8, 0.35, abz - 1.2, abx + 0.8, 0.85, abz + 1.2, (2, 0, 0, 0), bottom=True)
        wSteel.add(box_geo(0.12, 2.4, 0.12), M4(abx, 1.6, abz))
        box_quads(wG, abx - 1.25, 2.1, abz - 0.12, abx + 1.25, 3.5, abz - 0.02, (2, 0, 0, 0), bottom=True)
        for s in (-1, 1):
            wSteel.add(cylinder_geo(0.3, 0.3, 0.2, 14), M4(abx + s * 0.85, 0.3, abz, 0, 0, PI / 2))
        for lp in (WORK[0][0], WORK[1][0]):
            lx, ly, lz = lp
            box_quads(wG, lx - 0.7, 0.3, lz - 1.6, lx + 0.7, 1.4, lz + 1.6, (2, 0, 0, 0), bottom=True)
            wSteel.add(box_geo(0.16, ly - 1.4, 0.16), M4(lx, (ly + 1.4) / 2, lz))
            wSteel.add(box_geo(1.6, 0.1, 0.1), M4(lx, ly + 0.35, lz))
            for s in (-0.55, -0.18, 0.18, 0.55):
                wSteel.add(box_geo(0.34, 0.26, 0.1), M4(lx + s, ly, lz + 0.06, -0.85, 0, 0))
                wGlow.add(plane_geo(0.28, 0.2), M4(lx + s, ly - 0.05, lz + 0.12, PI / 2 + 0.72, 0, 0), (0.88, 0.92, 1.0, 3))
        fx, fy, fz = D['flood']
        yaw = math.atan2(D['wall']['x'] - fx, 38.0 - fz)
        mf = M4(fx, fy + 0.25, fz, -0.25, yaw, 0)
        for s in (-1, 1):
            wSteel.add(box_geo(0.04, 0.5, 0.04), M4(fx + s * 0.25, 0.25, fz, 0, 0, s * 0.3))
        wSteel.add(box_geo(0.7, 0.45, 0.16), mf)
        wGlow.add(plane_geo(0.62, 0.38), mf @ M4(0, 0, 0.085), (1.0, 0.93, 0.82, 4))
        cx, cz, top, w = -11.5, 101.0, 48.0, 1.8

        def lattice(p0, p1, wid):
            p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
            L = float(np.linalg.norm(p1 - p0))
            q = quat_unit_vectors((0, 1, 0), _norm(p1 - p0))
            base = compose(p0, q, (1, 1, 1))
            nseg = max(1, math.floor(L / wid + 0.5))
            for ox, oz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                wSteel.add(box_geo(0.14, L, 0.14), base @ M4(ox * wid / 2, L / 2, oz * wid / 2))
            for i in range(nseg):
                y0, y1 = i * L / nseg, (i + 1) * L / nseg
                dl, ang = math.hypot(wid, y1 - y0), math.atan2(wid, y1 - y0)
                for face, rx in ((0, 1), (1, -1)):
                    sgn = (i % 2) * 2 - 1
                    off = (M4(0, (y0 + y1) / 2, wid / 2, 0, 0, sgn * ang) if face else
                           M4(wid / 2, (y0 + y1) / 2, 0, sgn * ang * rx, 0, 0))
                    wSteel.add(box_geo(0.07, dl, 0.07), base @ off)

        lattice((cx, D['ground'], cz), (cx, top, cz), w)
        lattice((cx - 12, top + 1.0, cz), (cx + 34, top + 1.0, cz), 1.2)
        wSteel.add(box_geo(5, 3, 3), M4(cx - 8, top + 0.2, cz))
        wSteel.add(cylinder_geo(0.03, 0.03, 18, 6), M4(cx + 22, top - 8.0, cz))
        wSteel.add(box_geo(0.5, 0.7, 0.3), M4(cx + 22, top - 17.2, cz))
        wGlow.add(sphere_geo(0.25, 10, 8), M4(cx + 34, top + 1.6, cz), (1.0, 0.05, 0.03, 2))
        wGlow.add(sphere_geo(0.25, 10, 8), M4(cx, top + 4.5, cz), (1.0, 0.05, 0.03, 2))
        wm = self.obj('race:works', wG.build(), paint_w)
        ws = self.obj('race:worksSteel', wSteel.build(), self.mats['steel'])

        def glow_build(nb):
            a = nb.attr('aux', out='Color')
            k = nb.attr('aux', out='Alpha')
            t = u(nb, 'time')
            st = nb.step
            seq = st(0.82, nb.fract(t * 1.6 - k * 0.9)) * st(k, 1.0)
            crane = st(1.5, k) * st(k, 2.5) * st(0.5, nb.fract(t * 0.8))
            led = st(2.5, k) * st(k, 3.5) * u(nb, 'works')
            flood = st(3.5, k) * (u(nb, 'march') * 0.92 + 0.08)
            return a * (seq * 9.0 + st(k, 1.0) * 0.35 + crane * 10.0 + led * 14.0 + flood * 22.0)
        gm = unlit('race:works_lamps', glow_build)
        glow = self.obj('race:worksLamps', wGlow.build(), gm)
        _no_shadow(glow)

        def arrow_build(nb):
            q = nb.uv()
            x, y = (1.0 - q.x) * 3.0, q.y - 0.5
            cell, f = nb.floor(x), nb.fract(x)
            chev = nb.smoothstep(0.1, 0.04, nb.abs(f - 0.65 + nb.abs(y) * 0.9)) * nb.step(nb.abs(y), 0.36)
            on = nb.step(cell, nb.floor(nb.fract(u(nb, 'time') * 1.25) * 4.0) - 0.5)
            fr = nb.fract(q * (48.0, 22.0, 0.0)) - (0.5, 0.5, 0.0)
            dots = nb.smoothstep(0.42, 0.2, nb.length(nb.vec2(fr.x, fr.y)))
            return nb.v(lin_hex('#ffa31a')) * (chev * on * dots * 11.0 + 0.02)
        am = unlit('race:arrow_board', arrow_build)
        arrow = self.obj('race:arrowBoard', plane_geo(2.4, 1.3).transformed(M4(abx, 2.8, abz - 0.13, 0, PI, 0)), am)
        _no_shadow(arrow)
        self.debris_obs = debris_obs
        self.parts['works'] = {'drums': wm, 'steel': ws, 'lamps': glow, 'arrow': arrow,
                               'debris': [{'obj': g, **d} for g, d in debris_obs], 'mat': paint_w}

    # ------------------------------------------------------------------------------------------- the heel
    def manifesto_canvas(self):
        """race.js's page: Marinetti's 1909 manifesto (the 1914 Italian text, public domain), 768 x 1086."""
        from .bin_pages import Canvas2D
        PW, PH = 768, 1086
        g = Canvas2D(PW, PH, ss=2)
        g.fillStyle = '#e6dfcc'
        g.fillRect(0, 0, PW, PH)
        R3 = lcg(1909)
        for _ in range(1400):
            g.fillStyle = f'rgba(120,96,60,{0.02 + R3() * 0.05})'
            x, y = R3() * PW, R3() * PH
            g.fillRect(x, y, 1 + R3() * 3, 1 + R3() * 3)
        g.fillStyle = '#1b1712'
        g.textBaseline = 'alphabetic'
        g.font = 'bold 26px Georgia, "Times New Roman", serif'
        g.textAlign = 'center'
        g.fillText('FONDAZIONE E', PW / 2, 70)
        g.font = 'bold 66px Georgia, "Times New Roman", serif'
        g.fillText('MANIFESTO DEL', PW / 2, 140)
        g.fillText('FUTURISMO', PW / 2, 208)
        g.fillRect(40, 228, PW - 80, 4)
        g.fillRect(40, 236, PW - 80, 1.5)
        g.font = 'italic 20px Georgia, "Times New Roman", serif'
        g.fillText('F. T. Marinetti — 1909', PW / 2, 262)
        pts = [
            '1. Noi vogliamo cantare l’amor del pericolo, l’abitudine all’energia e alla temerità.',
            '2. Il coraggio, l’audacia, la ribellione, saranno elementi essenziali della nostra poesia.',
            '4. Noi affermiamo che la magnificenza del mondo si è arricchita di una bellezza nuova: la bellezza della '
            'velocità. Un automobile da corsa col suo cofano adorno di grossi tubi simili a serpenti dall’alito '
            'esplosivo.... un automobile ruggente, che sembra correre sulla mitraglia, è più bello della Vittoria di '
            'Samotracia.',
            '9. Noi vogliamo glorificare la guerra — sola igiene del mondo — il militarismo, il patriottismo, il gesto '
            'distruttore dei libertarî, le belle idee per cui si muore e il disprezzo della donna.',
        ]
        g.textAlign = 'left'
        g.font = '21px Georgia, "Times New Roman", serif'
        col_w, lead = (PW - 120) / 2, 27
        st = {'col': 0, 'y': 310}
        xs = [44, 44 + col_w + 32]
        for para in pts:
            line = ''

            def flush(line):
                g.fillText(line, xs[st['col']], st['y'])
                st['y'] += lead
                if st['y'] > PH - 50:
                    st['col'] += 1
                    st['y'] = 310
            for w in para.split(' '):
                test = line + ' ' + w if line else w
                if g.measureText(test).width > col_w and line:
                    flush(line)
                    line = ''
                line = line + ' ' + w if line else w
            if line:
                flush(line)
            st['y'] += lead * 0.6
        g.fillRect(PW / 2 + 6, 300, 1.2, PH - 340)
        return g.to_float()

    def _heel(self):
        u = self.u
        V3 = lambda x, y, z: np.array([x, y, z], float)

        def loft_r(rings, caps=True, open_=False):
            n = len(rings[0])
            pos, uvs, idx = [], [], []
            for i, ring in enumerate(rings):
                for j, p in enumerate(ring):
                    pos.append(p)
                    uvs.append((j / n, i / (len(rings) - 1)))
            for i in range(len(rings) - 1):
                for j in range(n):
                    a, b = i * n + j, i * n + (j + 1) % n
                    c, d = a + n, b + n
                    idx += [(a, b, c), (b, d, c)]
            if caps:
                for ri, flip in ((0, True), (len(rings) - 1, False)):
                    if open_ and ri == len(rings) - 1:
                        continue
                    ctr = np.mean(np.array(rings[ri], float), axis=0)
                    ci = len(pos)
                    pos.append(ctr)
                    uvs.append((0.5, 1 if ri else 0))
                    for j in range(n):
                        a, b = ri * n + j, ri * n + (j + 1) % n
                        idx.append((ci, b, a) if flip else (ci, a, b))
            return Geo(pos, np.zeros((len(pos), 3)), uvs, idx).compute_normals()

        def lerp_t(tab, z):
            if z <= tab[0][0]:
                return tab[0][1]
            for i in range(1, len(tab)):
                if z <= tab[i][0]:
                    (a, va), (b, vb) = tab[i - 1], tab[i]
                    return va + (vb - va) * (z - a) / (b - a)
            return tab[-1][1]

        W = [(-0.046, 0.026), (-0.036, 0.035), (0.0, 0.038), (0.04, 0.036), (0.1, 0.033), (0.17, 0.047), (0.22, 0.046),
             (0.255, 0.034), (0.278, 0.01)]
        TOP = [(-0.046, 0.09), (-0.035, 0.125), (-0.02, 0.142), (0.0, 0.152), (0.03, 0.166), (0.07, 0.158), (0.11, 0.128),
               (0.15, 0.1), (0.19, 0.078), (0.225, 0.064), (0.25, 0.05), (0.272, 0.03)]
        sole_bot = lambda z: 0.038 if z < 0.04 else (0.038 * (1 - _ease((z - 0.04) / 0.12)) if z < 0.16 else 0.012 * _ease((z - 0.2) / 0.075))
        ZS = [-0.046, -0.04, -0.03, -0.015, 0.0, 0.03, 0.06, 0.09, 0.12, 0.15, 0.18, 0.21, 0.235, 0.255, 0.268, 0.278]
        up_rings = []
        for z in ZS:
            w, b = lerp_t(W, z) - 0.0015, sole_bot(z) + 0.012
            t = max(b + 0.008, lerp_t(TOP, z))
            yc, h = (b + t) / 2, (t - b) / 2
            ring = []
            for k in range(28):
                a = k / 28 * TAU
                c, s = math.cos(a), math.sin(a)
                x = w * math.copysign(1, c) * abs(c) ** 0.7 if c != 0 else 0.0
                y = max(b + 0.003, yc + h * (math.copysign(1, s) if s != 0 else 0.0) * abs(s) ** 0.8)
                ring.append(V3(-x, y, z))
            up_rings.append(ring)
        upper = loft_r(up_rings)
        SY = [0.11, 0.15, 0.2, 0.26, 0.32, 0.38, 0.43, 0.47]
        HW = [0.04, 0.041, 0.045, 0.051, 0.055, 0.054, 0.055, 0.058]
        HD = [0.05, 0.052, 0.055, 0.06, 0.064, 0.062, 0.063, 0.066]
        shaft = loft_r([[V3(math.cos(k / 28 * TAU) * HW[i], y, 0.004 + (y - 0.11) * 0.05 + math.sin(k / 28 * TAU) * HD[i])
                         for k in range(28)] for i, y in enumerate(SY)], caps=False)
        sole_r = []
        for z in ZS:
            w, b = lerp_t(W, z) + 0.002, sole_bot(z)
            t = b + 0.013
            sole_r.append([V3(-w, b, z), V3(w, b, z), V3(w, t, z), V3(-w, t, z)])
        sole = loft_r(sole_r)

        def heel_ring(y):
            pts = [V3(-0.034 * math.cos(PI * k / 16), y, -0.004 - 0.042 * math.sin(PI * k / 16)) for k in range(17)]
            return pts + [V3(0.034, y, 0.042), V3(-0.034, y, 0.042)]
        heel_block = loft_r([heel_ring(0.0), heel_ring(0.039)])
        BY = [0.42, 0.5, 0.62, 0.78, 0.95, 1.1]
        RR = [0.05, 0.056, 0.066, 0.078, 0.082, 0.08]
        breech = loft_r([[V3(math.cos(k / 24 * TAU) * RR[i], y, 0.016 + (y - 0.42) * 0.04 + math.sin(k / 24 * TAU) * RR[i] * 1.1)
                          for k in range(24)] for i, y in enumerate(BY)], caps=False)
        # materials: polished wet black leather (clearcoat), stacked leather, black wool (sheen)
        m = new_material('race:boot_leather')
        nb = NB(m.node_tree)
        p = nb.local3()
        n = self.nz(nb, nb.vec2((p.x + p.z) * 9.0, p.y * 9.0))
        ankle = nb.smoothstep(0.08, 0.12, p.y) * nb.smoothstep(0.24, 0.15, p.y)
        crease = (nb.sin(p.y * 260.0 + n.r * 9.0) * 0.5 + 0.5) * ankle
        scuff = nb.smoothstep(0.6, 0.85, n.g) * nb.smoothstep(0.17, 0.25, p.z) * nb.step(p.y, 0.09)
        seam = nb.smoothstep(0.004, 0.0, nb.abs(p.x)) * nb.step(p.z, 0.0) * nb.step(0.16, p.y)
        albedo = nb.mix(lin_hex('#0b0807'), lin_hex('#3a332c'), scuff * 0.6) * (1.0 - seam * 0.5)
        bead = nb.smoothstep(0.78, 0.92, self.nz(nb, nb.vec2(p.x + p.z, p.y), 60.0).b) * u(nb, 'wet')
        nrm = nb.bump(crease * 0.0009 + bead * 0.0004 + n.b * 0.0002)
        # the fear screen behind it outlines the silhouette in red (race.js's backlit edge, an emission term)
        vv = nb.geom('Incoming')
        fres = nb.pow(1.0 - nb.max(nb.dot(nb.geom('Normal'), vv), 0.0), 3.0) * u(nb, 'heel_key') * u(nb, 'bill_b')
        em = nb.v(lin_hex('#ff3a24')) * fres * 0.55
        output(nb, principled(nb, albedo, crease * 0.25 + scuff * 0.4 + 0.2, 0.0, nrm, coat=0.85 - scuff * 0.6,
                              coat_rough=crease * 0.1 + 0.1, emission=em))
        leather = m
        m = new_material('race:boot_stack')
        nb = NB(m.node_tree)
        p = nb.local3()
        layers = nb.sin(p.y * (TAU / 0.0065)) * 0.5 + 0.5
        albedo = nb.mix(lin_hex('#2a1a10'), lin_hex('#4d3220'), layers) * (self.nz(nb, nb.vec2(p.x, p.z), 30.0).r * 0.4 + 0.75)
        output(nb, principled(nb, albedo, 0.7, 0.0))
        stack = m
        m = new_material('race:boot_wool')
        nb = NB(m.node_tree)
        p = nb.local3()
        n = self.nz(nb, nb.vec2((p.x + p.z) * 40.0, p.y * 40.0))
        output(nb, principled(nb, nb.v(lin_hex('#121212')) * (n.b * 0.4 + 0.8), 0.92, 0.0, sheen=0.6,
                              sheen_tint=lin_hex('#3a3a3a'), sheen_rough=0.5))
        wool = m
        HG = {k: GB() for k in ('leather', 'stack', 'wool', 'steel')}
        HG['leather'].add(upper)
        HG['leather'].add(shaft)
        HG['leather'].add(torus_geo(1, 0.06, 6, 28), M4(0, 0.47, 0.004 + 0.36 * 0.05, PI / 2, 0, 0, 0.058, 0.066, 0.06))
        HG['stack'].add(sole)
        HG['stack'].add(heel_block)
        HG['wool'].add(breech)
        HG['steel'].add(torus_geo(0.03, 0.003, 4, 20, PI), M4(0, 0.0015, -0.004, PI / 2, 0, PI))
        R2 = lcg(77)
        for _ in range(14):
            z = 0.13 + R2() * 0.13
            x = (R2() - 0.5) * 2 * (lerp_t(W, z) - 0.008)
            HG['steel'].add(sphere_geo(0.0035, 6, 4), M4(x, sole_bot(z) - 0.0005, z))
        root = empty('race:heel', parent=self.group, collection=self.col, pos=(D['heel'][0], 0, D['heel'][2]))
        root.rotation_mode = 'XYZ'
        root.rotation_euler = (0.0, 0.0, PI / 2 - 0.3)
        pivot = empty('race:heelPivot', parent=root, collection=self.col)
        pivot.rotation_mode = 'XYZ'
        meshes = {}
        for k, mat in (('leather', leather), ('stack', stack), ('wool', wool), ('steel', self.mats['steel_light'])):
            meshes[k] = self.obj('race:boot_' + k, HG[k].build(), mat, parent=pivot)
        # the page, soaking in the puddle; the heel's print appears when it lands
        page_img = image_from_array('race:manifesto_page', self.manifesto_canvas(), 'sRGB', top_first=False)
        pg = plane_geo(0.297, 0.42, 24, 34).transformed(M4(0, 0, 0, -PI / 2, 0, 0))
        x, z = pg.P[:, 0], pg.P[:, 2]
        pg.P[:, 1] = 0.0035 + np.sin(x * 61 + z * 17) * 0.0016 + np.sin(x * 23 - z * 41) * 0.0012 + np.maximum(0, x + z - 0.25) * 0.05
        pg.compute_normals()
        page_at = {'x': D['heel'][0] - 0.05, 'z': D['heel'][2] + 0.06, 'yaw': 0.42}
        v = qrot(quat_axis_angle((0, 1, 0), -page_at['yaw']), (D['heel'][0] - page_at['x'], 0, D['heel'][2] - page_at['z']))
        pr = (v[0], v[2])
        m = new_material('race:manifesto')
        nb = NB(m.node_tree)
        p = nb.local3()
        q = nb.uv()
        ink, _ = nb.tex(page_img, nb.vec2(q.x, 1.0 - q.y), ext='CLIP')
        soak = (nb.smoothstep(0.3, 0.55, self.nz(nb, nb.vec2(p.x, p.z), 14.0).r + 0.25) * 0.6 + 0.4) * u(nb, 'wet')
        hp = nb.vec2(p.x - pr[0], p.z - pr[1])
        ring = nb.smoothstep(0.012, 0.004, nb.abs(nb.length(hp * (1.0, 0.85, 1.0)) - 0.03))
        plate = nb.smoothstep(0.036, 0.026, nb.length(hp))
        h_age = u(nb, 'heel_age')
        print_k = nb.clamp(ring * 0.8 + plate * 0.35) * nb.step(0.0, h_age) * nb.smoothstep(0.0, 0.08, h_age)
        paper = nb.mix(0.62, 0.3, soak)
        albedo = nb.mix(ink * paper + nb.v(lin_hex('#2a2418')) * soak * 0.08, lin_hex('#1e170f'), print_k)
        output(nb, principled(nb, albedo, nb.mix(0.7, 0.25, nb.clamp(soak + print_k)), 0.0))
        page = self.obj('race:manifesto', pg, m)
        page.location = to_blender((page_at['x'], 0, page_at['z']))
        page.rotation_mode = 'XYZ'
        page.rotation_euler = (0.0, 0.0, page_at['yaw'])
        self.heel = {'root': root, 'pivot': pivot, 'page': page, 'meshes': meshes}
        self.parts['heel'] = {'root': root, 'pivot': pivot, 'page': page, 'dur': HEEL['dur'], 'strike': HEEL['strike'],
                              'page_image': page_img}

    def _dose(self, nb, albedo, k_front, k_back=0.0):
        """race.js dosed its lamp field per material: the hero car's paint and leather took it 1.7 times ("the hero
        catches more of the row"), its wood and tyres 1.53, the radiator core 1.36, the white silk twice and the
        streaming tails 2.4 on the face and 1.2 through it. The real lights give every material the light once; this
        is the rest of the dose, race.js's own field (unshadowed, the deck's occlusion included) as emission:
        albedo x field x k / pi, k = dose - 1 (k_back: the light through a thin sheet, from its far side)."""
        g = nb.group(self._field_group(bool(k_back)))
        nb.put(self.PL(nb), g.inputs['P'])
        nb.put(nb.normal3(), g.inputs['N'])
        E = V(nb, g.outputs['front'], True) * k_front
        if k_back:
            E = E + V(nb, g.outputs['back'], True) * k_back
        return E * albedo * (1.0 / PI)

    def _field_group(self, back=False):
        """race.js's fieldLight (the sodium rows and the works' floods, coloured) as one shader node group, built
        once: P and N in three's set-local axes -> front (the light on N) [and back (on -N)]."""
        trees = self.__dict__.setdefault('_field_trees', {})
        if back in trees:
            return trees[back]
        tree = bpy.data.node_groups.new(f'race:field_light{"_2" if back else ""}', 'ShaderNodeTree')
        for nm in ('P', 'N'):
            tree.interface.new_socket(nm, in_out='INPUT', socket_type='NodeSocketVector')
        for nm in (('front', 'back') if back else ('front',)):
            tree.interface.new_socket(nm, in_out='OUTPUT', socket_type='NodeSocketVector')
        nb = NB(tree)
        gi, go = nb.node('NodeGroupInput'), nb.node('NodeGroupOutput')
        P, N = V(nb, gi.outputs['P'], True), V(nb, gi.outputs['N'], True)
        lamps, works = self._fields(nb, P, [N, -N] if back else [N], lambda k: self.u(nb, k))
        for i, nm in enumerate(('front', 'back') if back else ('front',)):
            nb.put(nb.v(SODIUM) * lamps[i] + nb.v(WORK_COL) * works[i], go.inputs[nm])
        trees[back] = tree
        return tree

    # ------------------------------------------------------------------------------------- the lamp field (GN)
    def _fields(self, nb, P, normals, get):
        """race.js lampField(P, N) for several normals at once, and workField(P, N): the sodium rows (occluded by the
        deck below it) and the works' floods, as values in a node tree (three's axes). -> ([lamp per N], [work per N])"""
        lamp_acc = [0.0 for _ in normals]
        st = nb.step

        def lamp_one(Lx, Ly, Lz, on):
            Lv = nb.vec3(Lx, Ly, Lz) if not all(_isnum(c) for c in (Lx, Ly, Lz)) else (Lx, Ly, Lz)
            d = (nb.v(Lv) if isinstance(Lv, tuple) else Lv) - P
            d2 = nb.max(nb.dot(d, d), 0.25)
            l = d / nb.sqrt(d2)
            cone = nb.smoothstep(0.18, 0.72, l.y)
            ty = nb.clamp((-0.7 - P.y) / nb.max(Ly - P.y, 1e-3))
            xc = P.x + (Lx - P.x) * ty
            zc = P.z + (Lz - P.z) * ty
            under = (st(P.y, -0.8) * st(D['x_r'], xc) * st(xc, D['x_l']) * st(D['z_far'], zc)
                     * (1.0 - st(D['gap0'], zc) * st(zc, D['gap1']) * st(xc, D['x_med'] - 0.6)))
            k = cone * (1.0 - under) / d2 * on
            return [(nb.max(nb.dot(N, l), 0.0) * 0.85 + 0.15) * k for N in normals]

        kR = nb.floor(P.z / D['lamp_r']['dz'] + 0.5)
        for o in (-1, 0, 1):
            z = (kR + o) * D['lamp_r']['dz']
            on = st(z, D['gap0'] + 0.5) * st(D['z_far'] + 10, z)
            for i, v in enumerate(lamp_one(D['lamp_r']['head'][0], D['lamp_r']['head'][1], z, on)):
                lamp_acc[i] = lamp_acc[i] + v
        kL = nb.floor((P.z - D['lamp_l']['z0']) / D['lamp_l']['dz'] + 0.5)
        for o in (-1, 0, 1):
            z = (kL + o) * D['lamp_l']['dz'] + D['lamp_l']['z0']
            on = st(D['z_far'] + 10, z)
            for i, v in enumerate(lamp_one(D['lamp_l']['head'][0], D['lamp_l']['head'][1], z, on)):
                lamp_acc[i] = lamp_acc[i] + v
        lamps = [a * get('lamps') * self.opts['lamp_i'] for a in lamp_acc]
        work_acc = [0.0 for _ in normals]
        for p, a, ci, co, I, key in WORK:
            d = nb.v(tuple(p)) - P
            d2 = nb.max(nb.dot(d, d), 1.0)
            l = d / nb.sqrt(d2)
            cone = nb.smoothstep(co, ci, nb.dot(-l, tuple(_norm(a))))
            k = cone * I / d2 * get(key or 'works')
            for i, N in enumerate(normals):
                work_acc[i] = work_acc[i] + (nb.max(nb.dot(N, l), 0.0) * 0.8 + 0.2) * k
        return lamps, work_acc

    def _cam_gn(self, nb):
        """The active camera in the modified object's space (Blender axes): (location, right, up)."""
        ac = nb.node('GeometryNodeInputActiveCamera')
        oi = nb.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
        nb.links.new(ac.outputs[0], oi.inputs['Object'])
        loc = V(nb, oi.outputs['Location'], True)
        axes = []
        for v in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
            rv = nb.node('FunctionNodeRotateVector')
            rv.inputs['Vector'].default_value = v
            nb.links.new(oi.outputs['Rotation'], rv.inputs['Rotation'])
            axes.append(V(nb, rv.outputs[0], True))
        return loc, axes[0], axes[1]

    @staticmethod
    def _blender(nb, v):
        return nb.vec3(v.x, -v.z, v.y)

    def _named(self, nb, name, kind='FLOAT_VECTOR'):
        n = nb.node('GeometryNodeInputNamedAttribute', data_type=kind)
        n.inputs['Name'].default_value = name
        return V(nb, n.outputs['Attribute'], kind != 'FLOAT')

    def _store(self, nb, geo_sock, name, value, kind='FLOAT_VECTOR'):
        s = nb.node('GeometryNodeStoreNamedAttribute', data_type=kind, domain='POINT')
        s.inputs['Name'].default_value = name
        nb.links.new(geo_sock, s.inputs['Geometry'])
        nb.links.new(value.out, s.inputs['Value'])
        return s.outputs['Geometry']

    def _sprite_mesh(self, name, seeds, extra=None):
        """n quads (4 corners each) carrying 'corner' and 'seed' (and any extra per-quad float attributes)."""
        n = len(seeds)
        corners = np.array([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], float)
        P = np.zeros((4 * n, 3))
        I = np.concatenate([np.array([(0, 1, 2), (0, 2, 3)]) + 4 * q for q in range(n)])
        g = Geo(P, np.tile([0, 1.0, 0], (4 * n, 1)), np.tile([(0, 0), (1, 0), (1, 1), (0, 1)], (n, 1)), I)
        attrs = {'corner': ('FLOAT_VECTOR', 'POINT', np.tile(corners, (n, 1))),
                 'seed': ('FLOAT_VECTOR', 'POINT', np.repeat(np.asarray(seeds, float)[:, :3], 4, axis=0))}
        for k, v in (extra or {}).items():
            attrs[k] = ('FLOAT', 'POINT', np.repeat(np.asarray(v, float), 4))
        return g, attrs

    # ------------------------------------------------------------------------------------------- rain
    def _rain(self, count):
        """Slanted streaks in a box that travels with the camera (wrapped, so it never runs out), each lit by the
        lamp field at its own position: they glint inside the light cones and vanish in the dark between them."""
        R = lcg(4711)
        seeds = [(R(), R(), R(), R()) for _ in range(count)]
        g, attrs = self._sprite_mesh('race:rain', [s[:3] for s in seeds], {'seed_w': [s[3] for s in seeds]})

        def build(nb):
            c = nb.attr('corner', out='Vector')
            vl = nb.attr('rain_light', out='Vector')
            return vl * ((1.0 - nb.abs(c.y)) * (1.0 - nb.abs(c.x)) * 1.35) * self.u(nb, 'rain')
        m = unlit('race:rain', build, additive=True)
        ob = self.obj('race:rain', g, m, attrs=attrs, flat=True)
        _no_shadow(ob)
        _no_reflection(ob)
        tree, nb, gin, gout, mod = self._gn(ob, 'race:rain_gn', [('time', 0.0), ('lamps', 1.0), ('works', 1.0), ('heel_key', 0.0)])
        get = lambda k: V(nb, gin.outputs[k], False)
        seed, sw, c = self._named(nb, 'seed'), self._named(nb, 'seed_w', 'FLOAT'), self._named(nb, 'corner')
        loc, _right, _up = self._cam_gn(nb)
        CL = nb.three(loc)
        speed = nb.mix(8.0, 11.0, sw)
        fall = tuple(_norm((-0.26, -1.0, 0.1)))
        box = (34.0, 22.0, 34.0)
        raw = seed * box + nb.v(fall) * (get('time') * speed)
        rel = (raw - CL) / box + (0.5, 0.5, 0.5)
        ctr = (nb.fract(rel) - (0.5, 0.5, 0.5)) * box + CL
        to_cam = nb.normalize(CL - ctr)
        side = nb.normalize(nb.cross(fall, to_cam))
        pos = ctr + nb.v(fall) * (c.y * 0.3) + side * (c.x * 0.009)
        dist = nb.length(CL - ctr)
        fade = nb.smoothstep(0.8, 2.0, dist) * nb.smoothstep(19.0, 9.0, dist)
        (l1, l2), (w1, _w2) = self._fields(nb, ctr, [to_cam, nb.v((0.0, 1.0, 0.0))], get)
        vl = (nb.v(SODIUM) * (l1 * 0.6 + l2 * 0.5) + nb.v(WORK_COL) * (w1 * 0.12) + (0.02, 0.03, 0.045)) * fade
        geo = self._store(nb, gin.outputs['Geometry'], 'rain_light', vl)
        sp = nb.node('GeometryNodeSetPosition')
        nb.links.new(geo, sp.inputs['Geometry'])
        nb.links.new(self._blender(nb, pos).out, sp.inputs['Position'])
        nb.links.new(sp.outputs['Geometry'], gout.inputs['Geometry'])
        self.parts['rain'] = ob

    # ------------------------------------------------------------------------------------------- the drain's water
    def _wave_h(self, nb, P2, get):
        """race.js waveH: slow muddy flow to -X plus the ring waves of the two impacts (P2 = three's (x, z))."""
        t = get('time')
        n1, _ = nb.tex(self.noise_img, (P2 + nb.vec2(t * 0.35, 0.0)) * 0.18)
        n2, _ = nb.tex(self.noise_img, (P2 + nb.vec2(t * 0.5, t * 0.1)) * 0.9)
        flow = (n1.x - 0.5) * 0.03 + (n2.z - 0.5) * 0.012

        def ring(age, cp, amp):
            r = nb.length(P2 - nb.vec2(cp.x, cp.z))
            front = age * 4.2
            return (nb.sin((r - front) * 5.0) * nb.exp(nb.abs(r - front) * -1.6) * nb.exp(age * -0.9) * nb.step(0.0, age)
                    * amp * nb.smoothstep(0.0, 0.6, r))
        return flow + ring(get('crash_age'), get('crash_p'), 0.22) + ring(get('flip_age'), get('flip_p'), 0.16)

    def _water(self):
        u = self.u
        m = new_material('race:water')
        nb = NB(m.node_tree)
        P = self.PL(nb)
        P2 = nb.vec2(P.x, P.z)
        h = self._wave_h(nb, P2, lambda k: u(nb, k))
        t = u(nb, 'time')
        fq = nb.vec2((P.x + t * 0.35) * 0.06, P.z * 0.55)
        sp = u(nb, 'steam_p')
        foam = (nb.smoothstep(0.66, 0.8, self.nz(nb, fq).r) * 0.45
                + nb.smoothstep(0.6, 0.85, self.nz(nb, P2 * 0.8 + nb.vec2(t * 0.25, 0.0)).r)
                * nb.smoothstep(4.0, 0.6, nb.length(P2 - nb.vec2(sp.x, sp.z))) * u(nb, 'steam') * 0.8)
        fc = nb.clamp(foam)
        output(nb, principled(nb, nb.mix(lin_hex('#1b1810'), lin_hex('#6f6a5e'), fc), nb.mix(0.07, 0.6, fc), 0.0,
                              nb.bump(h), ior=1.33))
        C = D['ch']
        wg = GB()
        x0, x1, nxs, nzs = -14, 18, 64, 28
        zA, zB = C['b0'] - 1.0, C['b1'] + 1.0
        wg.add(plane_geo(x1 - x0, zB - zA, nxs, nzs).transformed(M4(0, 0, 0, -PI / 2, 0, 0)), M4((x0 + x1) / 2, C['water'], (zA + zB) / 2))
        wg.quad((-260, C['water'], zB), (x0, C['water'], zB), (x0, C['water'], zA), (-260, C['water'], zA))
        wg.quad((x1, C['water'], zB), (260, C['water'], zB), (260, C['water'], zA), (x1, C['water'], zA))
        ob = self.obj('race:water', wg.build(), m)
        tree, gnb, gin, gout, mod = self._gn(ob, 'race:water_waves', [('time', 0.0), ('crash_age', -10.0), ('crash_p', U_SPEC['crash_p']),
                                                                       ('flip_age', -10.0), ('flip_p', U_SPEC['flip_p'])])
        pos = V(gnb, gnb.node('GeometryNodeInputPosition').outputs[0], True)
        hgn = self._wave_h(gnb, gnb.vec2(pos.x, -pos.y), lambda k: V(gnb, gin.outputs[k], k.endswith('_p')))
        setp = gnb.node('GeometryNodeSetPosition')
        gnb.links.new(gin.outputs['Geometry'], setp.inputs['Geometry'])
        gnb.links.new(gnb.vec3(0.0, 0.0, hgn).out, setp.inputs['Offset'])
        gnb.links.new(setp.outputs['Geometry'], gout.inputs['Geometry'])
        self.mats['water'] = m
        self.parts['water'] = ob

    # ------------------------------------------------------------------------------------------- splash, steam
    def _splash(self):
        """One sprite mesh; every particle is a closed-form function of its seed and the impact clocks: the crown of
        mud thrown up by the nose, a mist sheet, the slam when the car lands on its back, steam off the drowned
        engine, and the droplets from the boot heel."""
        kinds = [(0, 520), (1, 60), (2, 360), (3, 90), (4, 90)]
        R = lcg(31337)
        seeds, kind_of = [], []
        for kind, cnt in kinds:
            for _ in range(cnt):
                seeds.append((R(), R(), R()))
                kind_of.append(kind)
        g, attrs = self._sprite_mesh('race:splash', seeds, {'kind': kind_of})
        u = self.u

        def build(nb):
            c = nb.attr('corner', out='Vector')
            kind = nb.attr('kind')
            is3 = nb.step(2.5, kind) * nb.step(kind, 3.5)
            is4 = nb.step(3.5, kind) * nb.step(kind, 4.5)
            soft_k = nb.attr('splash_soft')
            light = nb.attr('splash_light', out='Vector')
            alive = nb.attr('splash_alpha')
            d = nb.length(nb.vec2(c.x, c.y))
            drop = nb.smoothstep(1.0, 0.55, d)
            soft = nb.pow(nb.smoothstep(1.0, 0.0, d), 1.6)
            shape = nb.mix(drop, soft, soft_k)
            tint = nb.mix(lin_hex('#4f4230'), nb.mix(lin_hex('#7a6e5c'), lin_hex('#b9b2a6'), is3), soft_k)
            col = tint * light * 0.45 + tint * 0.025 + nb.v((1.6, 1.5, 1.35)) * (is4 * u(nb, 'heel_key'))
            op = shape * alive * nb.mix(0.95, nb.mix(0.22, 0.32, is3), soft_k)
            return col, op
        m = unlit('race:splash', build)
        ob = self.obj('race:splash', g, m, attrs=attrs, flat=True)
        _no_shadow(ob)
        _no_reflection(ob)
        ins = [('time', 0.0), ('crash_age', -10.0), ('crash_p', U_SPEC['crash_p']), ('flip_age', -10.0),
               ('flip_p', U_SPEC['flip_p']), ('steam', 0.0), ('steam_p', U_SPEC['steam_p']), ('heel_age', -10.0),
               ('heel_key', 0.0), ('lamps', 1.0), ('works', 1.0)]
        tree, nb, gin, gout, mod = self._gn(ob, 'race:splash_gn', ins)
        get = lambda k: V(nb, gin.outputs[k], k.endswith('_p'))
        sd = self._named(nb, 'seed')
        r1, r2, r3 = sd.x, sd.y, sd.z
        kind = self._named(nb, 'kind', 'FLOAT')
        c = self._named(nb, 'corner')
        st = nb.step
        is_ = lambda k: st(k - 0.5, kind) * st(kind, k + 0.5)
        W = D['ch']['water']

        def ballistic(age, o, out, up, a):
            return nb.vec3(nb.cos(a) * out * age, up * age - age * age * 4.905, nb.sin(a) * out * age) + o
        a0 = get('crash_age')
        p0 = ballistic(a0, get('crash_p'), nb.mix(1.0, 6.0, r2), nb.mix(3.5, 10.0, r3), r1 * TAU)
        al0 = st(0.0, a0) * st(a0, 2.6) * st(W - 0.02, p0.y)
        a1 = a0
        rr1 = nb.mix(0.6, 3.8, r2) * (1.0 - nb.exp(a1 * -3.0))
        p1 = nb.vec3(nb.cos(r1 * TAU) * rr1, nb.mix(0.3, 2.6, r3) * (1.0 - nb.exp(a1 * -2.2)), nb.sin(r1 * TAU) * rr1) + get('crash_p')
        al1 = st(0.0, a1) * nb.exp(a1 * -1.3)
        a2 = get('flip_age')
        p2 = ballistic(a2, get('flip_p'), nb.mix(2.5, 7.0, r2), nb.mix(1.0, 4.2, r3), r1 * TAU)
        al2 = st(0.0, a2) * st(a2, 2.0) * st(W - 0.02, p2.y)
        cyc = nb.fract(get('time') * 0.34 + r1)
        a3 = cyc * 2.9
        p3 = get('steam_p') + nb.vec3((r2 - 0.5) * 0.9 + nb.sin(a3 * 1.5 + r1 * 6.0) * 0.35 * a3,
                                      a3 * nb.mix(0.7, 1.5, r3) + 0.1,
                                      (r3 - 0.5) * 1.2 + nb.cos(a3 * 1.3 + r2 * 6.0) * 0.3 * a3)
        al3 = get('steam') * nb.smoothstep(0.0, 0.35, a3) * (1.0 - cyc) * 0.55
        a4 = get('heel_age')
        p4 = ballistic(a4, (D['heel'][0], 0.0, D['heel'][2]), nb.mix(0.25, 1.4, r2), nb.mix(0.5, 2.3, r3), r1 * TAU)
        al4 = st(0.0, a4) * st(a4, 1.0) * st(-0.005, p4.y)
        i0, i1, i2, i3, i4 = (is_(k) for k in range(5))
        P = p0 * i0 + p1 * i1 + p2 * i2 + p3 * i3 + p4 * i4
        alive = al0 * i0 + al1 * i1 + al2 * i2 + al3 * i3 + al4 * i4
        size = (nb.mix(0.035, 0.11, r2) * (i0 + i2) + nb.mix(0.4, 1.0, r2) * (a1 + 0.5) * i1
                + (nb.mix(0.3, 0.6, r2) + a3 * 0.9) * i3 + nb.mix(0.0018, 0.005, r1) * i4)
        vy = ((nb.mix(3.5, 10.0, r3) - a0 * 9.81) * i0 + (nb.mix(1.0, 4.2, r3) - a2 * 9.81) * i2
              + (nb.mix(0.5, 2.3, r3) - a4 * 9.81) * i4)
        stretch = nb.abs(vy) * 0.11 + 1.0
        (lf,), (wf,) = self._fields(nb, P, [nb.v((0.0, 1.0, 0.0))], get)
        light = nb.v(SODIUM) * lf + nb.v(WORK_COL) * wf + (0.02, 0.02, 0.02)
        loc, right, up = self._cam_gn(nb)
        sz = size * st(0.001, alive)
        pos = self._blender(nb, P) + right * (c.x * sz) + up * (c.y * sz * stretch)
        geo = self._store(nb, gin.outputs['Geometry'], 'splash_light', light)
        geo = self._store(nb, geo, 'splash_alpha', alive, 'FLOAT')
        geo = self._store(nb, geo, 'splash_soft', i1 + i3, 'FLOAT')
        sp = nb.node('GeometryNodeSetPosition')
        nb.links.new(geo, sp.inputs['Geometry'])
        nb.links.new(pos.out, sp.inputs['Position'])
        nb.links.new(sp.outputs['Geometry'], gout.inputs['Geometry'])
        self.parts['splash'] = ob

    # ------------------------------------------------------------------------------------------- the lights
    def _lights(self):
        """race.js's real lights (key, the screens' glows, rim, back rim, neon fill, the headlamp beam; its hemisphere
        light is in the world) and, real here, the lights it computed in its materials: the two rows of sodium
        lamps (one shared light datablock, so one key drives them all), the works' floods and the heel's close key."""
        lg = empty('race:lights', parent=self.group, collection=self.col)
        L = {}
        mk = lambda nm, kind, hexc, w, **kw: light(nm, kind, lin_hex(hexc), w, parent=lg, collection=self.col, **kw)
        L['key'] = mk('race:key', 'SPOT', 0xffa04e, cd(LIGHT_BASE['key']), pos=(D['lamp_r']['head'][0], D['lamp_r']['head'][1] - 0.15, 0.0),
                      target=(0.3, 0, 0.6), spot_half=0.62, blend=0.65, cutoff=34, radius=0.15)
        for k, hexc, B in (('glow_a', 0xffb040, D['bill_a']), ('glow_b', 0xff2418, D['bill_b'])):
            L[k] = mk(f'race:{k}', 'POINT', hexc, 0.0, pos=(B['x'] + math.sin(B['yaw']) * 6, B['y'] - 2, B['z'] + math.cos(B['yaw']) * 6),
                      cutoff=140, radius=3.0)
            # the screens' light on the set, diffuse only: their reflections are the screens themselves (the wet road's
            # mirror), as in race.js, where the road kept its PBR roughness at 1 for real lights so a screen's point
            # light never printed a blown disc into every puddle
            L[k].data.specular_factor = 0.0
        L['rim'] = mk('race:rim', 'SUN', 0x5fd2ff, LIGHT_BASE['rim'], pos=(-3, 8, -30), target=(0, 0.8, 0))
        L['back_rim'] = mk('race:backRim', 'SPOT', 0xff6a38, cd(LIGHT_BASE['back_rim']), pos=(0.9, 2.6, -4.6), target=(0.0, 1.0, 0.2),
                           spot_half=0.5, blend=0.7, cutoff=14, radius=0.3)
        L['neon_fill'] = mk('race:neonFill', 'POINT', 0x2fe0ff, cd(LIGHT_BASE['neon_fill']), pos=(-1.5, 0.95, -0.5), cutoff=4.5, radius=0.05)
        L['beam'] = mk('race:beam', 'SPOT', 0xffdca8, 0.0, pos=(0, 1, 2), target=(0, 0.1, 14), spot_half=0.42, blend=0.55, cutoff=70, radius=0.1)
        # the street lamps: spots straight down; full light within 44 deg of the axis, none past 79.6 deg (race.js's
        # cone = smoothstep(0.18, 0.72, l.y)), cut off where race.js stopped summing lamps
        sod = bpy.data.lights.new('race:sodium', 'SPOT')
        sod.color = SODIUM
        sod.energy = cd(self.opts['lamp_i'])
        sod.spot_size = 2 * math.acos(0.18)
        sod.spot_blend = (0.72 - 0.18) / (1 - 0.18)
        sod.shadow_soft_size = 0.2
        sod.use_custom_distance = True
        sod.cutoff_distance = 55.0
        # shadow-map texels: 38 heads (and the screens' far glows) at EEVEE's default 1 mm would overflow the shadow
        # pool; the lamps' shadows (the deck's occlusion, the car, the works) read at 2 cm, the glows' at 5 cm
        sod.shadow_maximum_resolution = 0.02
        for k in ('glow_a', 'glow_b'):
            L[k].data.shadow_maximum_resolution = 0.05
        heads = []
        for i, (hx, hy, hz, row) in enumerate(lamp_heads()):
            ob = bpy.data.objects.new(f'race:sodium_{row}{i:02d}', sod)
            self.col.objects.link(ob)
            ob.parent = lg
            ob.location = to_blender((hx, hy - 0.12, hz))
            heads.append(ob)
        L['sodium'] = sod
        works = []
        for i, (p, a, ci, co, I, key) in enumerate(WORK):
            tgt = tuple(np.asarray(p) + _norm(a))
            ob = mk(f'race:work_{i}' if not key else 'race:heelKey', 'SPOT', 0xdfe9ff, cd(I), pos=p, target=tgt,
                    spot_half=math.acos(co), blend=(ci - co) / (1 - co), cutoff=60 if not key else 6, radius=0.25 if not key else 0.05)
            if not key:
                ob.data.shadow_maximum_resolution = 0.01
            works.append(ob)
        L['works'] = works[:3]
        L['heel_key'] = works[3]
        self.lights = L
        self.parts['lights'] = {'key': L['key'], 'glow_a': L['glow_a'], 'glow_b': L['glow_b'], 'rim': L['rim'],
                                'back_rim': L['back_rim'], 'neon_fill': L['neon_fill'], 'hemi': self.world if self.opts['sky'] else None,
                                'sodium': heads, 'works': works[:3], 'heel_key': works[3], 'group': lg}
        self.car['beam'] = L['beam']
        self.parts['car_rig']['beam'] = L['beam']

    # ------------------------------------------------------------------------------------------- update
    def _vis(self, obs, visible, f):
        for ob in obs:
            ob.hide_render = not visible
            ob.hide_viewport = not visible
            self.key(ob, 'hide_render', f, interp='CONSTANT')
            self.key(ob, 'hide_viewport', f, interp='CONSTANT')

    def _descendants(self, ob):
        out = [ob]
        for ch in ob.children:
            out += self._descendants(ch)
        return out

    def update(self, t, state=None, frame=None):
        """Set the set for time t (seconds on your clock: the rain, the screens, the engine's shake, the march's
        lockstep) and state (race.js's keys in snake_case: car_t, car_s, car_v, crash, car, headlamps, bill_a, bill_b,
        billboards, gaze, march, march_t, heel, rain, wet, lamps, back_rim; sequence() makes them from event times)
        and KEY it at `frame`; frame=None sets without keying (a still)."""
        state = dict(state or {})
        rs = race_state(t, state, self.path, self.debris, self._active)
        f = frame
        k = self.key
        for name, v in rs['U'].items():
            self.U.set(name, v)
        if f is not None:
            self.U.key(k, f)
        for ob, mname, ident, uname in self.gn_inputs:
            slot = getattr(ob.modifiers[mname].properties.inputs, ident)
            v = rs['U'].get(uname, self.U.vals.get(uname))
            slot.value = tuple(float(c) for c in v) if isinstance(v, (tuple, list, np.ndarray)) else float(v)
            if f is not None:
                k(slot, 'value', f)
        car = rs['car']
        g = self.car['group']
        g.location = to_blender(car['pos'])
        pitch, yaw, roll = car['euler_yxz']
        g.rotation_euler = (pitch, -roll, yaw)
        b = self.car['body']
        b.location = to_blender(car['body_pos'])
        b.rotation_euler = (car['body_rot'][0], -car['body_rot'][1], 0.0)
        for w in self.car['wheels']:
            w['spin'].rotation_euler = (rs['wheel_ang'], 0.0, 0.0)
        for (ob, _d), (pos, rot) in zip(self.debris_obs, rs['debris']):
            ob.location = to_blender(pos)
            ob.rotation_euler = (rot[0], -rot[2], rot[1])
        pad = self.car['shadow']
        pad.location = to_blender(rs['shadow']['pos'])
        pad.rotation_euler = (0.0, 0.0, rs['shadow']['yaw'])
        hr = self.heel['root']
        hr.location = to_blender((D['heel'][0], rs['heel']['y'], D['heel'][2]))
        self.heel['pivot'].rotation_euler = (rs['heel']['pitch'], 0.0, 0.0)
        beam = self.lights['beam']
        aim_light(beam, rs['beam']['pos'], rs['beam']['target'])
        L, lv = self.lights, rs['lights']
        L['beam'].data.energy = cd(lv['beam'])
        L['key'].data.energy = cd(lv['key'])
        L['glow_a'].data.energy = cd(lv['glow_a'])
        L['glow_b'].data.energy = cd(lv['glow_b'])
        L['back_rim'].data.energy = cd(lv['back_rim'])
        L['neon_fill'].data.energy = cd(lv['neon_fill'])
        L['rim'].data.energy = lv['rim']
        L['sodium'].energy = cd(self.opts['lamp_i']) * rs['U']['lamps'] * (1 if self._active else 0)
        L['heel_key'].data.energy = cd(15.0) * rs['U']['heel_key'] * (1 if self._active else 0)
        for i, w in enumerate(L['works']):
            w.data.energy = cd(WORK[i][4]) * rs['U']['works'] * (1 if self._active else 0)
        if self.opts['sky']:
            self._hemi_value.outputs[0].default_value = lv['hemi'] / PI
        if f is None:
            return rs
        for ob in (g, b, pad, hr, beam):
            k(ob, 'location', f)
        for ob in (g, b, pad):
            k(ob, 'rotation_euler', f)
        k(self.heel['pivot'], 'rotation_euler', f)
        k(beam, 'rotation_quaternion', f)
        for w in self.car['wheels']:
            k(w['spin'], 'rotation_euler', f)
        for ob, _d in self.debris_obs:
            k(ob, 'location', f)
            k(ob, 'rotation_euler', f)
        for nm in ('beam', 'key', 'glow_a', 'glow_b', 'back_rim', 'neon_fill', 'rim', 'heel_key'):
            k(L[nm].data, 'energy', f)
        for w in L['works']:
            k(w.data, 'energy', f)
        k(L['sodium'], 'energy', f)
        if self.opts['sky']:
            k(self._hemi_value.outputs[0], 'default_value', f)
        car_obs = self._descendants(g)
        self._vis([o for o in car_obs if o.type == 'MESH'], car['visible'] and self._active, f)
        self._vis([pad], car['visible'] and self._active, f)
        self._vis([o for o in self._descendants(hr) if o.type == 'MESH'], rs['heel']['visible'] and self._active, f)
        return rs

    def set_active(self, on, frame=None):
        """race.js setActive: park the set outside its section. Every mesh is hidden and every light kept, at 0; with
        on, the set shows again and the next update() brings its lights back. With a frame, each switch is keyed as a
        step there (Keyer.step): the set stays as it was up to the frame and parked from it until the next key, so a
        set parked at frame 200 still shows on frames 1 to 199, and its lights stay off while it is parked."""
        self._active = bool(on)
        f = frame
        always = [o for o in self.objects if o not in self._descendants(self.car['group'])
                  and o not in self._descendants(self.heel['root']) and o is not self.car['shadow']]
        for ob in always:
            for p in ('hide_render', 'hide_viewport'):
                if f is not None:
                    self.key.step(ob, p, not self._active, f)
                else:
                    setattr(ob, p, not self._active)
        if not self._active:
            L = self.lights
            datas = [L[k].data for k in ('key', 'glow_a', 'glow_b', 'rim', 'back_rim', 'neon_fill', 'beam', 'heel_key')]
            datas += [w.data for w in L['works']] + [L['sodium']]
            for d in datas:
                if f is not None:
                    self.key.step(d, 'energy', 0.0, f)
                else:
                    d.energy = 0.0
            if self.opts['sky']:
                hv = self._hemi_value.outputs[0]
                if f is not None:
                    self.key.step(hv, 'default_value', 0.0, f)
                else:
                    hv.default_value = 0.0

    # ------------------------------------------------------------------------------------------- cameras
    def cam_at(self, name, t, state=None):
        """race.js camAt in Blender's axes (set-local): the moving cameras that follow the car, or None."""
        state = dict(state or {})
        rs = race_state(t, state, self.path, self.debris, self._active)
        return cam_to_blender(cam_at_three(name, t, state, rs, self.path))

    def focal(self, name):
        """The shot's idol for the painting's sun cones (set-local, Blender's axes)."""
        return Vector(to_blender(FOCAL.get(name, FOCAL['singer'])))

    def focal_world(self, name):
        return self.group.matrix_world @ self.focal(name)

    def camera_matrix(self, c):
        """A cam {pos, target, fov, roll, up} (set-local, Blender's axes) -> the camera's world matrix (three's
        applyCam: look at the target with +Z up, then roll about the view axis)."""
        from ...look.camera import look_matrix
        up = Vector(c.get('up') or (0.0, 0.0, 1.0))
        f = (Vector(c['target']) - Vector(c['pos'])).normalized()
        if abs(f.dot(up.normalized())) > 0.995:
            up = Vector(to_blender((0, 0, -1)))
        m = look_matrix(c['pos'], c['target'], up)
        if c.get('roll'):
            m = m @ Matrix.Rotation(c['roll'], 4, 'Z')
        return self.group.matrix_world @ m

    def key_camera(self, cam, name, t, state=None, frame=None, scene=None):
        """Put a Blender camera on the shot `name` at time t (cam_at for the moving cameras, else cams) and key it at
        frame: location, rotation, the vertical fov (three's), and the LED-cell pixel angle."""
        scene = scene or self.scene
        c = self.cam_at(name, t, state) or self.cams.get(name)
        if c is None:
            raise ValueError(f'race.key_camera: {name!r} follows the car, which is hidden or in its crash at this state '
                             f'(cam_at gives None); static cameras: {", ".join(self.cams)}')
        cam.rotation_mode = 'QUATERNION'
        cam.matrix_world = self.camera_matrix(c)
        cam.data.sensor_fit = 'VERTICAL'
        cam.data.sensor_height = 24.0
        cam.data.lens = 12.0 / math.tan(math.radians(c['fov']) / 2)
        cam.data.clip_start = 0.05
        cam.data.clip_end = 4000.0
        px = 2 * math.tan(math.radians(c['fov']) / 2) / max(1, scene.render.resolution_y * scene.render.resolution_percentage / 100)
        self.U.set('px', px)
        if frame is not None:
            self.key(cam, 'location', frame)
            self.key(cam, 'rotation_quaternion', frame)
            self.key(cam.data, 'lens', frame)
            for n in self.U.nodes['px']:
                self.key(n.outputs[0], 'default_value', frame)
        return c

    # ------------------------------------------------------------------------------------------- whole sections
    def animate(self, frames=None, t0=0.0, fps=None, state_fn=None):
        """Key update() over frames (t = t0 at frames[0], your clock): state_fn(t) gives the state (sequence() makes one
        from event times); without it the set idles on its own clock (rain, screens, lamps; the car parked). The
        section then plays from the .blend alone. Returns the keys made LINEAR / CONSTANT."""
        sc = self.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        for f in range(f0, f1 + 1):
            t = t0 + (f - f0) / fps
            self.update(t, state_fn(t) if state_fn else {}, frame=f)
        return self.finish()

    def make_cameras(self, cut, frames=None, t0=0.0, fps=None, scene=None, state_fn=None):
        """Your cut as cameras: `cut` is cut(t) -> camera name, or [(t_start, name), ...] on the same clock as t0.
        One camera per shot (a run of frames on the same name), keyed every frame of its shot (cam_at follows the car
        for the moving ones, with state_fn(t)'s state), bound to timeline markers at the cuts.
        Returns {(first frame, name): camera}."""
        from ...look.camera import add_shot
        sc = scene or self.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        if not callable(cut):
            plan = sorted(cut)
            cut = lambda t: next((n for s, n in reversed(plan) if t >= s - 1e-9), plan[0][1])
        runs = []
        for f in range(f0, f1 + 1):
            t = t0 + (f - f0) / fps
            name = cut(t)
            if not runs or runs[-1][0] != name:
                runs.append((name, []))
            runs[-1][1].append((f, t))
        cams = {}
        col = bpy.data.collections.get('race:cameras') or make_collection('race:cameras', self.col)
        for name, lst in runs:
            cam = bpy.data.objects.new(f'race:cam_{name}_{lst[0][0]}', bpy.data.cameras.new(f'race:cam_{name}_{lst[0][0]}'))
            col.objects.link(cam)
            for f, t in lst:
                st = state_fn(t) if state_fn else {}
                self.key_camera(cam, name, t, st, frame=f, scene=sc)
            add_shot(sc, f'race_{name}_{lst[0][0]}', lst[0][0], cam)
            cams[(lst[0][0], name)] = cam
        self.finish()
        self.cameras = cams
        return cams

    # dict-style access, the sets' contract (eidoblend.sets.unknown_force): s['group'], s['update'] ...
    def __getitem__(self, k):
        return getattr(self, k)

    def get(self, k, default=None):
        return getattr(self, k, default)

    def keys(self):
        return ['group', 'parts', 'update', 'dispose', 'cams', 'cam_at', 'focal', 'set_active', 'LAYOUT', 'uniforms']

    LAYOUT = LAYOUT

    @property
    def uniforms(self):
        """race.js's uniforms: one node group of keyed values every material reads (.vals, .set(name, v))."""
        return self.U

    # ------------------------------------------------------------------------------------------- the rest
    def finish(self):
        """Give every key update() made its interpolation (LINEAR; CONSTANT for the visibility switches)."""
        return self.key.finish()

    def apply_render_settings(self, scene=None, fog=True, bloom=True, world=True):
        """The set's renderer settings (RACE.md): AgX, EEVEE ray tracing (the wet road's reflections, with the deck's
        planar probe; race.js carried its own mirror and kept SSR off) and global illumination (fast GI), bloom
        {strength 0.55, threshold 0.7}, the set's fog FogExp2(0x0c0f16, 0.0062), and the set's world."""
        scene = scene or self.scene
        scene.render.engine = 'BLENDER_EEVEE'
        scene.view_settings.view_transform = 'AgX'
        ee = scene.eevee
        ee.use_raytracing = True
        ee.ray_tracing_method = 'SCREEN'
        ee.use_fast_gi = True
        ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
        ee.clamp_surface_indirect = 10.0
        ee.shadow_pool_size = '1536'
        if world and self.opts['sky']:
            scene.world = self.world
        done = ['AgX', 'ray tracing', 'fast GI']
        if bloom:                                   # first: the fog splices in after Render Layers, before the bloom
            from ...harness.settings import add_bloom
            done.append(add_bloom(scene, {'threshold': 0.7, 'size': 0.5, 'strength': 0.55}))
        if fog:
            from ...sky.fog import setup_fog
            colnode = setup_fog(scene, density=0.0062, kind='exp2')
            colnode.outputs[0].default_value = lin_hex(0x0c0f16) + (1.0,)
            done.append('fog')
        return done

    def _planar(self):
        """race.js's ReflectorNode over the deck: an EEVEE planar light probe covering the road (y = 0)."""
        pd = bpy.data.lightprobes.new('race:deck_mirror', 'PLANE')
        ob = bpy.data.objects.new('race:deck_mirror', pd)
        self.col.objects.link(ob)
        ob.parent = self.group
        ob.location = to_blender(((D['x_l'] + D['x_r']) / 2, 0.0, (D['z_far'] + D['z_near']) / 2))
        ob.scale = ((D['x_l'] - D['x_r']) / 2 + 0.5, (D['z_near'] - D['z_far']) / 2, 1.0)
        # the road lies on the mirror's own plane: left in the probe's capture, its underside covers the whole
        # mirrored set and every puddle reflects black (race.js's reflector clipped at its plane)
        self.parts['road'].hide_probe_plane = True
        self.parts['reflector'] = ob

    def dispose(self):
        """race.js dispose: remove everything the set made (its objects and their meshes, lights, probe and cameras,
        its materials and the images they read, its node groups, its uniforms, its world and its collections)."""
        _dispose_set(self.col, set(self.mats.values()), 'race:', self.world if self.opts['sky'] else None)


def build(ctx=None, **opts):
    """race.js build(THREE, opts) -> Race. ctx: the harness ctx (its scene and ctx.key keyer), a scene, or None (the
    current scene). opts (race.js's, snake_case): reflect (True: the deck's planar probe), reflect_scale (kept for the
    API; EEVEE sizes its own probe), sky (True: the set's night world), towers, rain, rain_count (5200), lamp_i (140: a
    250 W sodium head in three's candela), keyer (a keyer instead of ctx.key); and, for a new piece, amounts (the text
    in the two screens' bands, gold then red: ('$100,000,000', '$20,000,000'), race.js's own)."""
    scene, keyer = _ctx_scene_keyer(ctx, opts)
    return Race(scene, keyer=keyer, **opts)


def _ctx_scene_keyer(ctx, opts):
    keyer = opts.pop('keyer', None)
    if ctx is None or (bpy is not None and isinstance(ctx, bpy.types.Scene)):
        return ctx, keyer
    return getattr(ctx, 'scene', None), keyer or getattr(ctx, 'key', None)


# ------------------------------------------------------------------------------------------- small helpers ---
_GN_U = {}


def _jr(x):
    """JavaScript Math.round."""
    return int(math.floor(x + 0.5))


def _no_shadow(ob):
    if ob is not None:
        ob.visible_shadow = False


def _dispose_set(col, mats, prefix, world=None):
    """Remove a built set: every object in its collection (child collections included) with its mesh, light, probe or
    camera data, the materials those objects and `mats` use and the images they read (once nothing else uses them),
    the node groups named with the set's prefix, its world, its collections, and the actions its keys made."""
    obs = list(col.all_objects)
    mats = set(mats)
    for ob in obs:
        for s in getattr(ob, 'material_slots', []):
            if s.material is not None:
                mats.add(s.material)

    def images_of(tree):
        return {n.image for n in tree.nodes if n.bl_idname in ('ShaderNodeTexImage', 'ShaderNodeTexEnvironment')
                and n.image is not None} if tree is not None else set()
    imgs = set().union(*(images_of(m.node_tree) for m in mats)) if mats else set()
    groups = [g for g in bpy.data.node_groups if g.name.startswith(prefix)]
    for g in groups:
        imgs |= images_of(g)
    if world is not None:
        imgs |= images_of(world.node_tree)
    imgs |= {i for i in bpy.data.images if i.name.startswith(prefix)}
    datas = [ob.data for ob in obs if ob.data is not None]
    keyed = obs + datas + list(mats) + [m.node_tree for m in mats if m.node_tree is not None] + groups
    if world is not None:
        keyed += [world, world.node_tree]
    acts = set()
    for idb in keyed:
        ad = getattr(idb, 'animation_data', None)
        if ad is not None and ad.action is not None:
            acts.add(ad.action)
    for ob in obs:
        bpy.data.objects.remove(ob, do_unlink=True)
    kinds = ((bpy.types.Mesh, bpy.data.meshes), (bpy.types.Light, bpy.data.lights),
             (bpy.types.LightProbe, bpy.data.lightprobes), (bpy.types.Camera, bpy.data.cameras))
    for d in datas:
        try:
            if d.users:
                continue
        except ReferenceError:                           # shared by two objects: already removed
            continue
        for typ, coll in kinds:
            if isinstance(d, typ):
                coll.remove(d)
                break
    if world is not None and world.name in bpy.data.worlds:
        bpy.data.worlds.remove(world)
    for g in groups:
        bpy.data.node_groups.remove(g)
    for m in mats:
        try:
            if m.users == 0:
                bpy.data.materials.remove(m)
        except ReferenceError:
            pass
    for i in imgs:
        try:
            if i.users == 0:
                bpy.data.images.remove(i)
        except ReferenceError:
            pass

    def colls(c):
        out = []
        for ch in c.children:
            out += colls(ch)
        return out + [c]
    for c in colls(col):
        bpy.data.collections.remove(c)
    for a in acts:
        try:
            if a.users == 0:
                bpy.data.actions.remove(a)
        except ReferenceError:
            pass


def _no_reflection(ob):
    """race.js's noRefl: the transparent effects (the lamps' light cones, the car's contact pad, the rain, the splash)
    stay out of the road's mirror. Here: hidden from the deck's planar probe (EEVEE's screen-space tracing never sees
    blended surfaces)."""
    if ob is not None and hasattr(ob, 'hide_probe_plane'):
        ob.hide_probe_plane = True


def _vt(nb, v, frm, to, kind='NORMAL'):
    n = nb.node('ShaderNodeVectorTransform', vector_type=kind, convert_from=frm, convert_to=to)
    nb.put(v, n.inputs[0])
    return n.outputs[0]
