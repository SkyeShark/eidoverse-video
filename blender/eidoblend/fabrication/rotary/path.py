"""Indexed XYZ + A milling about the stock's X axis: the port of eidoverse/robotics/rotary_path.js. numpy alone, no scene
needed (rotary_surface makes a Blender mesh).

    from eidoblend.fabrication.rotary.path import (CENTRE_SEAT, RotaryPath, rotary_blank_distance, rotary_program,
                                                   rotary_surface_arrays, sample_rotary, sweep_distance)
    p = rotary_program(sample_rotary, material='wood', tool='flat', angles=96, sample_step=0.001)
    p.moves      # [{'position': (x, y, z), 'angle': a, 'type': 'rapid'|'index'|'cut', 'stage': 'rough 1', 'feed': ...}]
    p.path       # a RotaryPath: timed segments; p.path.sample(seconds) -> the cutter and A axis at that time
    p.stages     # [{'name': 'rough 1', 'first_move': 1}, ..., {'name': 'finish', ...}]
    p.settings   # stock, cutter, rates, axis datums (snake_case of the WebGPU names)

STOCK COORDINATES (Blender axes, metres): X along the rotary axis, Z the radial direction toward the cutter at A = 0
(the stock's height), Y its width (three's stock z, negated). A move's position is the cutter tip in this frame; its
angle is the A axis (the chuck). A stock point p sits at R_x(angle) p in the cutter's frame, so a station that cuts
the stock's direction theta (radius(x, theta) measured at the point (x, -r sin theta, r cos theta)) indexes to
angle = -theta. The change from three's stock frame is the same +90 degree turn about X as everywhere else in
eidoblend, so angles, the A axis and every distance are unchanged.

Option names are the WebGPU ones in snake_case: stockLength -> stock_length, sampleStep -> sample_step,
roughAllowance -> rough_allowance, rotationSpeed -> rotation_speed, fluteLength -> flute_length, axisX -> axis_x ...
"""

from __future__ import annotations

import bisect
import math
from types import MappingProxyType

import numpy as np

from .._axes import Rec
from ..cutting import stock_profile

TAU = 2 * math.pi

# The mounted blank is prepared with a 60-degree centre-drilled seat and a narrower pilot for tip relief. This is
# workholding preparation, not a cut performed by the program. Dimensions match the supplied live centre.
CENTRE_SEAT = MappingProxyType({'depth': .003, 'half_angle': math.pi / 6, 'pilot_radius': .0008, 'pilot_depth': .006})


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _finite(*values):
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def _is_integer(v):
    """Number.isInteger: an int, or a float with no fraction."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and float(v).is_integer()


def _option(options, key, default):
    """options.key ?? default: a missing key or None takes the default."""
    v = options.get(key)
    return default if v is None else v


# ------------------------------------------------------------------------------------------- the prepared blank ---

def rotary_blank_distance(p, settings) -> float:
    """Signed distance to the mounted blank: the stock box less the tailstock end's centre seat and pilot relief.
    p in stock coordinates; settings needs stock_length, stock_width, stock_height."""
    L, W, H = settings['stock_length'], settings['stock_width'], settings['stock_height']
    q = (abs(p[0]) - L / 2, abs(p[1]) - W / 2, abs(p[2]) - H / 2)
    box = math.hypot(*(max(v, 0.0) for v in q)) + min(max(q), 0.0)
    rho, h = math.hypot(p[1], p[2]), p[0] - (L / 2 - CENTRE_SEAT['depth'])
    cone = max(rho * math.cos(CENTRE_SEAT['half_angle']) - h * math.sin(CENTRE_SEAT['half_angle']), -h)
    pilot = max(rho - CENTRE_SEAT['pilot_radius'], L / 2 - CENTRE_SEAT['pilot_depth'] - p[0])
    return max(box, -min(cone, pilot))


# ------------------------------------------------------------------------------------------ the sample sculpture ---

def sample_rotary(x, theta, stock=None):
    """The original asymmetric, twisted three-lobed sculpture: its radius at axial x and stock angle theta. End stock is
    retained for chuck / tailstock workholding (parting off is a separate operation). stock: optional dict with
    start, end, stock_width, stock_height (the blank it is sized for). x, theta may be numpy arrays."""
    stock = stock or {}
    start, end = stock.get('start', -.041), stock.get('end', .052)
    sw, sh = stock.get('stock_width', .036), stock.get('stock_height', .036)
    u = np.clip((np.asarray(x, dtype=float) - start) / (end - start), 0.0, 1.0)
    swell = np.sin(math.pi * u) ** 1.25
    half = min(sw, sh) / 2
    corner = math.hypot(sw / 2, sh / 2)
    base = max(.0095 * half / .018, corner - .016)
    scale = min(half / .018, (half - .0005 - base) / .0077)
    if not scale > 0:
        raise ValueError("This blank's aspect exceeds the ball tool's reach for an all-around sample")
    r = base + scale * (.0048 * swell + .0022 * swell * np.cos(3 * np.asarray(theta, dtype=float) - u * TAU * .85)
                        + .0007 * swell * np.sin(np.asarray(theta, dtype=float) + u * 4))
    return float(r) if np.ndim(r) == 0 else r


def _call_radius(radius, x, theta):
    """radius(x, theta) over numpy arrays: vectorised when the function takes arrays, element by element otherwise."""
    x, theta = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(theta, dtype=float))
    try:
        with np.errstate(all='ignore'):
            r = np.asarray(radius(x, theta), dtype=float)
        if r.shape == x.shape:
            return r
        if r.ndim == 0:
            return np.full(x.shape, float(r))
    except (TypeError, ValueError) as e:                 # a scalar-only function (math.sin on an array ...)
        if 'aspect' in str(e):
            raise
    out = np.empty(x.shape)
    for k in np.ndindex(x.shape):
        out[k] = float(radius(float(x[k]), float(theta[k])))
    return out


def rotary_surface_arrays(radius=sample_rotary, start=-.041, end=.052, nx=100, na=192):
    """The target surface of revolution as (vertices (N, 3) float64, triangles (M, 3) int) in stock coordinates:
    rings of na + 1 points (the seam repeated, as the WebGPU geometry) for nx + 1 axial stations, and end caps."""
    xs = start + (end - start) * np.arange(nx + 1) / nx
    ts = TAU * np.arange(na + 1) / na
    X, Tt = np.meshgrid(xs, ts, indexing='ij')
    r = _call_radius(radius, X, Tt)
    if not np.all(np.isfinite(r) & (r > 0)):
        raise ValueError('Invalid rotary surface radius')
    verts = np.stack([X, -r * np.sin(Tt), r * np.cos(Tt)], axis=-1).reshape(-1, 3)
    i, j = np.meshgrid(np.arange(nx), np.arange(na), indexing='ij')
    a = (i * (na + 1) + j).ravel()
    b = a + na + 1
    tris = [np.stack([a, a + 1, b], 1), np.stack([a + 1, b + 1, b], 1)]
    side = np.empty((2 * a.size, 3), dtype=np.int64)
    side[0::2], side[1::2] = tris
    caps, extra = [], []
    for k, i_ring in enumerate((0, nx)):
        c = verts.shape[0] + k
        extra.append((start + (end - start) * i_ring / nx, 0.0, 0.0))
        aa = i_ring * (na + 1) + np.arange(na)
        caps.append(np.stack([np.full(na, c), aa + 1, aa], 1) if i_ring == 0 else np.stack([np.full(na, c), aa, aa + 1], 1))
    return np.vstack([verts, np.asarray(extra)]), np.vstack([side] + caps)


def rotary_surface(radius=sample_rotary, start=-.041, end=.052, nx=100, na=192, name='rotary_surface'):
    """The WebGPU rotarySurface as a Blender mesh datablock (not linked to an object): the target shape, smooth
    shaded, its seam welded so the shading is continuous all the way round. Needs bpy."""
    import bpy
    verts, tris = rotary_surface_arrays(radius, start, end, nx, na)
    na1 = na + 1
    seam = np.arange(nx + 1) * na1
    keep = np.ones(verts.shape[0], dtype=bool)
    keep[seam + na] = False                               # the repeated seam column ...
    remap = np.full(verts.shape[0], -1, dtype=np.int64)
    remap[keep] = np.arange(int(keep.sum()))
    remap[seam + na] = remap[seam]                        # ... welded onto column 0
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts[keep].tolist(), [], remap[tris].tolist())
    me.validate(clean_customdata=False)
    me.update()
    me.shade_smooth()
    return me


# ------------------------------------------------------------------------------------------- the cutter offset ---

def _radial_offsets(radius, x, theta, R, step=.0005, tool='ball'):
    """radialOffset over arrays: the conservative sampled tool offset at each (x, theta). The maximum over the complete
    cutter footprint keeps axial and azimuthal slopes from gouging the target."""
    x, theta = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(theta, dtype=float))
    with np.errstate(all='ignore'):
        centre = _call_radius(radius, x, theta)
        angle = np.arcsin(np.minimum(1.0, R / centre)) * 1.25
        n = math.ceil(R / step)
        nt = np.ceil(centre * angle / step)
        finite_nt = nt[np.isfinite(nt)]
        ntmax = int(finite_nt.max()) if finite_nt.size else 0
        top = np.full(x.shape, -np.inf)
        bad = ~np.isfinite(nt)
        for i in range(-n, n + 1):
            dx = R * i / n
            for j in range(-ntmax, ntmax + 1):
                valid = np.abs(j) <= nt
                if not valid.any():
                    continue
                t = angle * j / nt
                r = _call_radius(radius, x + dx, theta + t)
                z = r * np.sin(t)
                d = R * R - dx * dx - z * z
                val = r * np.cos(t) + (0.0 if tool == 'flat' else np.sqrt(d) - R)
                use = valid & ~(d < 0)
                top = np.where(use, np.maximum(top, val), top)
        top = np.where(bad, np.nan, top)
    return top + .00004


# ----------------------------------------------------------------------------------------------- the program ---

def rotary_program(source=sample_rotary, **options):
    """rotaryProgram: an indexed roughing + finishing program for a radius function radius(x, theta), or for a mesh
    (any other source goes to rotary_mesh_program). Every roughing level visits the whole circumference before going
    deeper; roughing uses alternate stations, the finish all of them."""
    if not callable(source):
        from .mesh import rotary_mesh_program
        return rotary_mesh_program(source, **options)
    tool = _option(options, 'tool', 'ball')
    flute_length = _option(options, 'flute_length', .018 if tool == 'flat' else .017)
    if tool not in ('flat', 'ball') or not (_finite(flute_length) and flute_length > 0):
        raise ValueError('Invalid rotary cutter')
    profile = stock_profile(_option(options, 'material', 'wood'))
    L = _option(options, 'stock_length', .140)
    W = _option(options, 'stock_width', .036)
    H = _option(options, 'stock_height', .036)
    start = _option(options, 'start', -L / 2 + .029)
    end = _option(options, 'end', L / 2 - .018)
    radius = _option(options, 'radius', .003)
    angles = _option(options, 'angles', 96)
    sample_step = _option(options, 'sample_step', .001)
    rough_allowance = _option(options, 'rough_allowance', .0007)
    stepdown = _option(options, 'stepdown', profile['stepdown'])
    material = _option(options, 'material', 'wood')
    rotation_speed = _option(options, 'rotation_speed', .8)
    axis_height = _option(options, 'axis_height', .097)
    axis_x = _option(options, 'axis_x', -.055 + L / 2)
    if not _is_integer(angles) or angles < 16 or angles > 512 or not (sample_step >= .0001 and stepdown >= .0001):
        raise ValueError('Invalid rotary sampling')
    angles = int(angles)
    if not _finite(L, W, H, start, end, radius, sample_step, rough_allowance, stepdown, rotation_speed,
                   axis_height, axis_x):
        raise ValueError('Rotary dimensions and rates must be finite')
    if not (L > 0 and W > 0 and H > 0 and start < end and start > -L / 2 and end < L / 2):
        raise ValueError('Invalid stock or cutting interval')
    if not (rotation_speed > 0 and radius > 0 and rough_allowance >= 0):
        raise ValueError('Invalid rotary tool settings')
    feed = _option(options, 'feed', profile['feed'])
    plunge = _option(options, 'plunge', profile['plunge'])
    rpm = _option(options, 'rpm', profile['rpm'])
    if not all(_finite(v) and v > 0 for v in (feed, plunge, rpm)):
        raise ValueError('Invalid rotary feed or spindle speed')
    stock_radius = math.hypot(W / 2, H / 2)
    safe = stock_radius + .0022
    if source is sample_rotary:
        bounds = {'start': start, 'end': end, 'stock_width': W, 'stock_height': H}

        def target(x, a):
            return sample_rotary(x, a, bounds)
    else:
        target = source
    count = math.ceil((end - start) / sample_step)
    xs = start + (end - start) * np.arange(count + 1) / count
    thetas = TAU * np.arange(angles) / angles
    X, TH = np.meshgrid(xs, thetas)                       # [station j][sample i]
    R = _radial_offsets(target, X, TH, radius, .0005, tool)
    if not np.all((R > 0) & (R < min(W, H) / 2)):
        raise ValueError('Target must fit inside the rotary stock')
    minimum = float(R.min())
    profiles = [[(float(xs[i]), 0.0, float(R[j, i])) for i in range(count + 1)] for j in range(angles)]
    if stock_radius - minimum > flute_length - .0005:
        raise ValueError('Target exceeds the installed cutting length')

    stages, moves = [], []
    cur = {'p': (start, 0.0, safe), 'a': 0.0}

    def push(position, angle, kind, stage, rate=None):
        moves.append(Rec(position=position, angle=angle, type=kind, stage=stage, feed=rate))
        cur['p'], cur['a'] = position, angle

    push(cur['p'], 0.0, 'rapid', 'setup')
    floors = []
    r = stock_radius - stepdown
    while r > minimum + rough_allowance:
        floors.append(r)
        r -= stepdown
    floors.append(minimum + rough_allowance)
    for pass_, floor in [*enumerate(floors), (len(floors), 0)]:
        finish = floor == 0
        stage = 'finish' if finish else 'rough %d' % (pass_ + 1)
        stages.append(Rec(name=stage, first_move=len(moves)))
        stride = 1 if finish else 2
        for j in range(0, angles, stride):
            angle = -TAU * (pass_ + j / angles)
            row = [(x, y, rr if finish else max(floor, rr + rough_allowance)) for x, y, rr in profiles[j]]
            if (j // stride) % 2:
                row.reverse()
            push((cur['p'][0], 0.0, safe), cur['a'], 'rapid', stage)
            push((cur['p'][0], 0.0, safe), angle, 'index', stage)
            push((row[0][0], 0.0, safe), angle, 'rapid', stage)
            push(row[0], angle, 'cut', stage, plunge)
            for p in row[1:]:
                push(p, angle, 'cut', stage, feed)
    push((cur['p'][0], 0.0, safe), cur['a'], 'rapid', 'retract')
    path = RotaryPath(moves, feed=feed, rapid=_option(options, 'rapid', .08),
                      acceleration=_option(options, 'acceleration', .3), rotation_speed=rotation_speed)
    settings = Rec(stock_length=L, stock_width=W, stock_height=H, start=start, end=end, radius=radius,
                      angles=angles, sample_step=sample_step, axis_height=axis_height, axis_x=axis_x, safe=safe,
                      flute_length=flute_length, tool=tool, material=material, feed=feed, plunge=plunge, rpm=rpm,
                      stepdown=stepdown, centre_seat=dict(CENTRE_SEAT))
    return Rec(moves=moves, path=path, stages=stages, settings=settings, target=source)


# -------------------------------------------------------------------------------------------- the timed path ---

class RotaryPath:
    """Timed indexed strokes. A change of A must be an explicit 'index' move with XYZ stationary; cut and rapid strokes
    keep A fixed and run a trapezoidal feed with look-ahead along finely sampled rows (complete stops at plunges,
    retracts and indexing, none at each 1 mm sample).

    segments: dicts with a, b (positions), a0, a1, type, stage, t0, t1, index; strokes also length, d (unit
    direction), feed, v0, v1, peak, ta, tc, td, da, acceleration. duration: seconds."""

    def __init__(self, moves, feed=.035, rapid=.08, acceleration=.3, rotation_speed=.8, **_options):
        if not all(_finite(v) and v > 0 for v in (feed, rapid, acceleration, rotation_speed)):
            raise ValueError('Invalid rotary motion rates')
        self.segments = []
        self._time = 0.0
        block = []

        def flush():
            if not block:
                return
            n = len(block)
            speed = [0.0] * (n + 1)
            acc = acceleration * .6
            for i in range(1, n):
                a, b = block[i - 1], block[i]
                dot = a['d'][0] * b['d'][0] + a['d'][1] * b['d'][1] + a['d'][2] * b['d'][2]
                ang = math.acos(_clamp(dot, -1.0, 1.0))
                if a['type'] != b['type'] or ang > .15:
                    continue
                rad = min(a['length'], b['length']) / (2 * max(1e-8, math.sin(ang / 2)))
                speed[i] = min(a['feed'], b['feed'], math.sqrt(acceleration * .8 * rad))
            for i in range(1, n + 1):
                speed[i] = min(speed[i], math.sqrt(speed[i - 1] ** 2 + 2 * acc * block[i - 1]['length']))
            for i in range(n - 1, -1, -1):
                speed[i] = min(speed[i], math.sqrt(speed[i + 1] ** 2 + 2 * acc * block[i]['length']))
            for i in range(n):
                s = block[i]
                v0, v1 = speed[i], speed[i + 1]
                peak = min(s['feed'], math.sqrt(acc * s['length'] + (v0 * v0 + v1 * v1) / 2))
                ta, td = (peak - v0) / acc, (peak - v1) / acc
                da, dd = (v0 + peak) * ta / 2, (v1 + peak) * td / 2
                tc = max(0.0, (s['length'] - da - dd) / peak)
                s.update(t0=self._time, t1=self._time + ta + tc + td, v0=v0, v1=v1, peak=peak, ta=ta, td=td, da=da,
                         tc=tc, acceleration=acc, index=len(self.segments))
                self.segments.append(s)
                self._time = s['t1']
            block.clear()

        for i in range(1, len(moves)):
            a, b = moves[i - 1], moves[i]
            if not _finite(*a['position'], *b['position'], a['angle'], b['angle']):
                raise ValueError('Invalid rotary move')
            delta = b['angle'] - a['angle']
            pa, pb = a['position'], b['position']
            dist = math.sqrt((pb[0] - pa[0]) ** 2 + (pb[1] - pa[1]) ** 2 + (pb[2] - pa[2]) ** 2)
            if abs(delta) > 1e-9 and dist > 1e-9:
                raise ValueError('Indexed program rotates only with stationary XYZ')
            if abs(delta) > 1e-9:
                flush()
                if b['type'] != 'index':
                    raise ValueError('A-axis changes require an explicit index move')
                duration = max(.02, abs(delta) * 1.5 / rotation_speed)
                self.segments.append(Rec(a=pa, b=pb, a0=a['angle'], a1=b['angle'], type='index', stage=b.get('stage'),
                                         t0=self._time, t1=self._time + duration, index=len(self.segments)))
                self._time += duration
            elif dist > 1e-10:
                rate = b.get('feed')
                if rate is None:
                    rate = rapid if b['type'] == 'rapid' else feed
                if not (_finite(rate) and rate > 0) or b['type'] not in ('cut', 'rapid'):
                    raise ValueError('Invalid indexed stroke')
                if b['type'] == 'cut' and abs(pa[1] - pb[1]) > 1e-10:
                    raise ValueError('Indexed strokes must remain in one axial/radial plane')
                block.append(Rec(a=pa, b=pb, a0=a['angle'], a1=b['angle'], type=b['type'], stage=b.get('stage'),
                                 length=dist, d=tuple((pb[k] - pa[k]) / dist for k in range(3)), feed=rate))
        flush()
        if not self.segments:
            raise ValueError('Empty rotary program')
        self.duration = self._time
        self._t1 = [s['t1'] for s in self.segments]

    def sample(self, seconds):
        """The cutter tip (stock coordinates), the A angle, the stroke and its speed at `seconds` (clamped to the
        program); 'done' once seconds reaches the duration."""
        if not _finite(seconds):
            raise ValueError('Rotary time must be finite')
        t = _clamp(float(seconds), 0.0, self.duration)
        lo = bisect.bisect_left(self._t1, t, 0, len(self._t1) - 1)
        s = self.segments[lo]
        u = (t - s['t0']) / (s['t1'] - s['t0'])
        ease = u * u * (3 - 2 * u)
        distance = speed = 0.0
        if s['type'] != 'index':
            dt = t - s['t0']
            acc = s['acceleration']
            if dt < s['ta']:
                speed = s['v0'] + acc * dt
                distance = s['v0'] * dt + acc * dt * dt / 2
            elif dt < s['ta'] + s['tc']:
                speed = s['peak']
                distance = s['da'] + s['peak'] * (dt - s['ta'])
            else:
                v = dt - s['ta'] - s['tc']
                speed = max(0.0, s['peak'] - acc * v)
                distance = s['da'] + s['peak'] * s['tc'] + s['peak'] * v - acc * v * v / 2
        f = ease if s['type'] == 'index' else _clamp(distance / s['length'], 0.0, 1.0)
        return Rec(time=t, index=lo, fraction=f,
                   position=tuple(s['a'][k] + (s['b'][k] - s['a'][k]) * f for k in range(3)),
                   angle=s['a0'] + (s['a1'] - s['a0']) * ease, type=s['type'], stage=s['stage'], speed=speed,
                   done=seconds >= self.duration)


# ------------------------------------------------------------------------------------------- the swept cutter ---

def sweep_distance(point, s, radius, flute_length=.017, fraction=1.0, tool='ball') -> float:
    """Independent numeric swept-tool distance (negative inside), for planning and review queries: a stroke s (a
    segment or any dict with a, b, a0) sweeps a ball nose (or a flat end) and its cylindrical cutting length up to
    `fraction` of its length. point in stock coordinates."""
    c, sn = math.cos(s['a0']), math.sin(s['a0'])
    a, b = s['a'], s['b']
    p0 = point[0]
    p1 = point[2] * c + point[1] * sn                   # height in the cutter's frame
    p2 = point[2] * sn - point[1] * c + a[1]            # lateral offset from the stroke's plane (sign as the JS)
    if tool == 'flat':
        dx = (b[0] - a[0]) * fraction
        dy = (b[2] - a[2]) * fraction
        x, y = p0 - a[0], p1 - a[2]
        w = math.sqrt(max(0.0, radius * radius - p2 * p2))
        tx = _clamp(x, min(0.0, dx), max(0.0, dx))
        radial = math.hypot(x - tx, p2) - radius
        lo, hi = 0.0, 1.0
        if abs(dx) > 1e-12:
            lo = _clamp(min((x - w) / dx, (x + w) / dx), 0.0, 1.0)
            hi = _clamp(max((x - w) / dx, (x + w) / dx), 0.0, 1.0)
        low = min(lo * dy, hi * dy)
        high = max(lo * dy, hi * dy) + flute_length
        normalizer = math.sqrt(1 + (dy / dx) ** 2 * (1 + (p2 / max(w, 1e-7)) ** 2)) if abs(dx) > 1e-12 else 1.0
        return max(radial, (low - y) / normalizer, (y - high) / normalizer)
    pa = (a[0], a[2] + radius)
    pb = (a[0] + (b[0] - a[0]) * fraction, a[2] + (b[2] - a[2]) * fraction + radius)
    h = flute_length - radius
    poly = (pa, pb, (pb[0], pb[1] + h), (pa[0], pa[1] + h))
    d, inside = math.inf, False
    j = 3
    for i in range(4):
        v, w2 = poly[i], poly[j]
        ddx, ddy = w2[0] - v[0], w2[1] - v[1]
        ll = ddx * ddx + ddy * ddy
        u = _clamp(((p0 - v[0]) * ddx + (p1 - v[1]) * ddy) / ll, 0.0, 1.0) if ll else 0.0
        d = min(d, (p0 - v[0] - u * ddx) ** 2 + (p1 - v[1] - u * ddy) ** 2)
        if (v[1] > p1) != (w2[1] > p1) and p0 < (w2[0] - v[0]) * (p1 - v[1]) / (w2[1] - v[1]) + v[0]:
            inside = not inside
        j = i
    return math.sqrt((0.0 if inside else d) + p2 * p2) - radius
