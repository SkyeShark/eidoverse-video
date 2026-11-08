"""eidoblend.characters.clippy: the Office Assistant, ported from eidoverse/clippy.js (tools-guides/clippy.md).

    from eidoblend.characters.clippy import make_clippy
    clippy = make_clippy(height=1.2, location=(2, 1, 0))
    clippy.play('IdleAtom', 2.0)            # any of the 43 original Microsoft Agent clip names, at scene second 2
    clippy.bake(1, 240)                     # key every frame: the shape keys and the inner transform

The same character, made the same way: every transformation is the WHOLE character re-evaluated (the wire's centreline
re-routed into atom orbits, a rope pile, a floppy, an envelope, a printer, a wizard hat ..., the eyes re-homed, the brows
and his legal-pad page riding along), so one shape key IS one transformation. The geometry is clippy.js's, line for line
(the gem clip's segments, the shapes, the pose field, the parallel-transport tube, the ghost pinches, the face anchors,
the page): built in three's frame and turned into Blender's (x, -z, y), so he faces -Y. Topology differs from the WebGPU
mesh in one way only: the spheres and the tube have no duplicated seam vertices (three's SphereGeometry splits its seam),
so EEVEE shades them without a crease; base and every key share the one topology.

    morphs (shape keys)  pose: lean tilt squash curl wave tap scratch point; face: blink browUp browDown lookAside lookUp
                         peer bulge phones droopEyes pencil; shape: shapeAtom shapePile shapeFloppy shapeEnvelope
                         shapePrinter shapeWizard shapeCheck shapeVortex shapeBike shapeMobile; paper: paperUp paperFeed
                         paperCrumple (each slider -1 .. 1.25, as three's influences are clamped)
    the inner object     '@scale', '@hopY', '@spinY', '@slideX' and the idle bob, sway and fidgets (clippy.js update(t))
    materials            chrome (metal 1, roughness 0.17), white, black, the lined legal-pad page (its 64 x 88 texture made
                         the same way), the pencil's yellow

bake() is the WebGPU update(t) run once per frame in order and keyed (LINEAR): no handler at render time.
"""

import math

import bpy
import numpy as np
from mathutils import Euler, Vector

TAU = math.pi * 2.0
MORPHS = ['lean', 'tilt', 'squash', 'curl', 'wave', 'tap', 'scratch', 'point',
          'blink', 'browUp', 'browDown', 'lookAside', 'lookUp', 'peer',
          'bulge', 'phones', 'droopEyes', 'pencil',
          'shapeAtom', 'shapePile', 'shapeFloppy', 'shapeEnvelope', 'shapePrinter', 'shapeWizard',
          'shapeCheck', 'shapeVortex', 'shapeBike', 'shapeMobile',
          'paperUp', 'paperFeed', 'paperCrumple']


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------------------------------- the 3D path machinery
def L(p0, p1):
    return {'kind': 'l', 'p0': p0, 'p1': p1}


def GL(p0, p1):
    return {'kind': 'l', 'p0': p0, 'p1': p1, 'ghost': True}


def E(C, U, V, r1, r2, a0, a1):
    return {'kind': 'e', 'C': C, 'U': U, 'V': V, 'r1': r1, 'r2': r2, 'a0': a0, 'a1': a1}


UX, UY = [1, 0, 0], [0, 1, 0]


def _ell(g, a):
    c, sn = math.cos(a) * g['r1'], math.sin(a) * g['r2']
    return [g['C'][k] + g['U'][k] * c + g['V'][k] * sn for k in range(3)]


def segs_sample(segs, N):
    for g in segs:
        if g['kind'] == 'l':
            g['len'] = math.dist(g['p0'], g['p1'])
        else:
            g['len'] = abs(g['a1'] - g['a0']) * (g['r1'] + g['r2']) * 0.5
    total = sum(g['len'] for g in segs)
    pts = np.zeros((N, 3))
    ghost = np.zeros(N)
    for i in range(N):
        s = (i / (N - 1)) * total
        p = None
        for g in segs:
            if s > g['len']:
                s -= g['len']
                continue
            if g.get('ghost'):
                ghost[i] = 1
            f = s / g['len'] if g['len'] > 1e-9 else 0.0
            if g['kind'] == 'l':
                p = [g['p0'][k] + (g['p1'][k] - g['p0'][k]) * f for k in range(3)]
            else:
                p = _ell(g, g['a0'] + (g['a1'] - g['a0']) * f)
            break
        if p is None:
            g = segs[-1]
            p = list(g['p1']) if g['kind'] == 'l' else _ell(g, g['a1'])
        pts[i] = p
    return pts, ghost


def gem_segs(hat):
    W, d = 0.34, 0.075
    xL, xR = -W / 2, W / 2
    xl, xr = -(W / 2 - d), W / 2 - d
    rBi, rBo = 0.095, 0.17
    yBi, yBo = 0.235, 0.215
    rA = (xR - xl) / 2
    cA = (xR + xl) / 2
    yA = 1.00 - rA
    s = [E([xr + 0.045, 0.66, 0], UX, UY, 0.045, 0.045, math.pi * 0.55, math.pi * 1.5),
         L([xr, 0.64, 0], [xr, yBi, 0]),
         E([0, yBi, 0], UX, UY, rBi, rBi, 0, -math.pi),
         L([xl, yBi, 0], [xl, yA, 0])]
    if hat:
        s += [L([xl, yA, 0], [-0.02, 1.12, 0]),
              L([-0.02, 1.12, 0], [0.055, 1.33, 0]),
              E([0.085, 1.335, 0], UX, UY, 0.032, 0.032, math.pi, -math.pi * 0.5),
              L([0.115, 1.30, 0], [0.17, 1.02, 0]),
              L([0.17, 1.02, 0], [xR, yA, 0])]
    else:
        s.append(E([cA, yA, 0], UX, UY, rA, rA, math.pi, 0))
    s += [L([xR, yA, 0], [xR, yBo, 0]),
          E([0, yBo, 0], UX, UY, rBo, rBo, 0, -math.pi),
          L([xL, yBo, 0], [xL, 0.62, 0]),
          E([xL - 0.045, 0.62, 0], UX, UY, 0.045, 0.045, 0, math.pi * 0.95)]
    return s


def _poly(points):
    return [L(a, b) for a, b in zip(points, points[1:])]


def shape_segs(name):
    s = []
    if name == 'atom':
        C = [0, 0.56, 0]
        s.append(E([C[0], C[1], 0.035], UX, UY, 0.05, 0.05, 0, TAU * 1.75))
        prev = [C[0] + 0.05 * math.cos(TAU * 1.75), C[1] + 0.05 * math.sin(TAU * 1.75), 0.035]
        for k in range(3):
            ph = (k / 3) * math.pi
            U = [math.cos(ph) * 0.375, math.sin(ph) * 0.375, 0]
            Vv = [-math.sin(ph) * 0.135, math.cos(ph) * 0.135, 0]
            Cz = [C[0], C[1], (k - 1) * 0.028]
            a0 = math.pi * 0.25
            st = [Cz[j] + U[j] * math.cos(a0) + Vv[j] * math.sin(a0) for j in range(3)]
            s.append(GL(prev, st))
            s.append(E(Cz, U, Vv, 1, 1, a0, a0 + TAU))
            prev = st
        return s
    if name == 'pile':
        turns, NN, prev = 5.5, 44, None
        for i in range(NN + 1):
            f = i / NN
            a = f * TAU * turns
            wob = math.sin(a * 0.37 + 1.7) * 0.06
            r = 0.30 - 0.13 * f + wob
            p = [math.cos(a) * r + wob * 0.8, 0.05 + 0.11 * f, math.sin(a) * r * 0.8 - wob]
            if prev:
                s.append(L(prev, p))
            prev = p
        s.append(L(prev, [prev[0] - 0.03, prev[1] + 0.10, prev[2]]))
        return s
    if name == 'floppy':
        w, y0, r = 0.36, 0.50, 0.05
        s += [L([-w + r, y0 - w, 0], [w - r, y0 - w, 0]),
              E([w - r, y0 - w + r, 0], UX, UY, r, r, -math.pi / 2, 0),
              L([w, y0 - w + r, 0], [w, y0 + w - r, 0]),
              E([w - r, y0 + w - r, 0], UX, UY, r, r, 0, math.pi / 2),
              L([w - r, y0 + w, 0], [-w + r, y0 + w, 0]),
              E([-w + r, y0 + w - r, 0], UX, UY, r, r, math.pi / 2, math.pi),
              L([-w, y0 + w - r, 0], [-w, y0 - w + r, 0]),
              E([-w + r, y0 - w + r, 0], UX, UY, r, r, math.pi, math.pi * 1.5),
              GL([-w + r, y0 - w, -0.05], [-w + 0.04, y0 + w - 0.06, -0.05]),
              GL([-w + 0.04, y0 + w - 0.06, -0.05], [0.04, y0 + w - 0.05, -0.05]),
              L([0.04, y0 + w - 0.03, 0.02], [0.04, y0 + 0.20, 0.02]),
              L([0.04, y0 + 0.20, 0.02], [0.26, y0 + 0.20, 0.02]),
              L([0.26, y0 + 0.20, 0.02], [0.26, y0 + w - 0.03, 0.02]),
              GL([0.26, y0 + w - 0.03, -0.05], [0.28, y0 - 0.14, -0.02]),
              L([0.26, y0 - 0.17, 0.03], [-0.26, y0 - 0.17, 0.03])]
        return s
    if name == 'envelope':
        w, h, y0 = 0.42, 0.26, 0.46
        s += [L([-w, y0 - h, 0], [w, y0 - h, 0]), L([w, y0 - h, 0], [w, y0 + h, 0]),
              L([w, y0 + h, 0], [-w, y0 + h, 0]), L([-w, y0 + h, 0], [-w, y0 - h, 0]),
              GL([-w, y0 - h, 0.015], [-w, y0 + h, 0.015]),
              L([-w, y0 + h, 0.02], [0, y0 - 0.02, 0.03]), L([0, y0 - 0.02, 0.03], [w, y0 + h, 0.02])]
        return s
    if name == 'printer':
        y0 = 0.16
        s += _poly([[-0.34, y0, 0], [0.34, y0, 0], [0.34, y0 + 0.22, 0], [0.24, y0 + 0.22, 0], [0.24, y0 + 0.36, 0],
                    [0.10, y0 + 0.36, 0], [0.10, y0 + 0.30, 0], [-0.10, y0 + 0.30, 0], [-0.10, y0 + 0.36, 0],
                    [-0.24, y0 + 0.36, 0], [-0.24, y0 + 0.22, 0], [-0.34, y0 + 0.22, 0], [-0.34, y0, 0]])
        s += [L([-0.34, y0, 0.03], [-0.26, y0 + 0.10, 0.05]), L([-0.26, y0 + 0.10, 0.05], [-0.18, y0 + 0.10, 0.05])]
        return s
    if name == 'check':
        s += [L([-0.26, 0.52, 0], [-0.02, 0.16, 0]), L([-0.02, 0.16, 0], [0.34, 0.88, 0]),
              L([0.34, 0.88, 0], [0.30, 0.90, 0.03]), L([0.30, 0.90, 0.03], [0.0, 0.20, 0.03]),
              L([0.0, 0.20, 0.03], [-0.23, 0.55, 0.03])]
        return s
    if name == 'vortex':
        turns, NN, prev = 6.0, 44, None
        for i in range(NN + 1):
            f = i / NN
            a = f * TAU * turns
            r = 0.34 - 0.28 * f
            p = [math.cos(a) * r, 0.62 - 0.54 * f, math.sin(a) * r]
            if prev:
                s.append(L(prev, p))
            prev = p
        return s
    if name == 'bike':
        hubY, rW = 0.20, 0.165
        s += [L([0.34, 0.66, 0.05], [0.25, 0.62, 0.02]), L([0.25, 0.62, 0.02], [0.21, 0.50, 0.02]),
              L([0.21, 0.50, 0.02], [0.19, hubY + 0.02, 0.02]),
              E([0.19, hubY, 0], UX, UY, rW, rW, math.pi / 2, math.pi / 2 + TAU),
              L([0.19, hubY, 0.02], [-0.19, hubY, 0.02]),
              E([-0.19, hubY, 0], UX, UY, rW, rW, math.pi / 2, math.pi / 2 + TAU),
              L([-0.19, hubY, 0.02], [-0.06, 0.52, 0.02]), L([-0.06, 0.52, 0.02], [0.21, 0.50, 0.03]),
              L([0.21, 0.50, 0.03], [-0.06, 0.52, 0.04]), L([-0.06, 0.52, 0.04], [-0.16, 0.58, 0.04])]
        return s
    if name == 'mobile':
        s += [E([0, 1.06, 0], UX, UY, 0.045, 0.045, 0, TAU * 0.75),
              L([0, 1.02, 0], [0, 0.94, 0]), L([0, 0.94, 0], [-0.30, 0.86, 0.10]),
              L([-0.30, 0.86, 0.10], [-0.30, 0.68, 0.10]),
              E([-0.30, 0.57, 0.10], UX, UY, 0.11, 0.11, math.pi / 2, math.pi * 2.5),
              L([-0.30, 0.86, 0.10], [0.20, 0.98, -0.09]), L([0.20, 0.98, -0.09], [0.20, 0.84, -0.09]),
              L([0.20, 0.84, -0.09], [0.36, 0.80, -0.02]), L([0.36, 0.80, -0.02], [0.36, 0.70, -0.02]),
              E([0.36, 0.645, -0.02], UX, UY, 0.055, 0.055, math.pi / 2, math.pi * 2.5)]
        return s
    return gem_segs(False)


FACE = {
    'gem': {'eL': [-0.098, 0.815, 0.05], 'eR': [0.062, 0.755, 0.055], 'eS': 1,
            'bL': [-0.118, 0.955, 0.05], 'bR': [0.085, 0.905, 0.05], 'bY': 0.99, 'bX': 0.105, 'bZ': 0.052, 'bS': 1},
    'wizard': {'eL': [-0.098, 0.815, 0.05], 'eR': [0.062, 0.755, 0.055], 'eS': 1,
               'bL': [-0.118, 0.945, 0.05], 'bR': [0.085, 0.90, 0.05], 'bY': 0.97, 'bX': 0.105, 'bZ': 0.052, 'bS': 1},
    'atom': {'eL': [-0.21, 0.42, -0.07], 'eR': [0.16, 0.75, 0.13], 'eS': 0.9,
             'pL': [0.265, 0.825, 0.0], 'pR': [-0.30, 0.375, 0.028], 'bY': 0.98, 'bX': 0.30, 'bZ': -0.02, 'bS': 0.04},
    'pile': {'eL': [-0.05, 0.27, 0.19], 'eR': [0.10, 0.26, 0.17], 'eS': 0.85, 'bY': 0.385, 'bX': 0.055, 'bZ': 0.17, 'bS': 0.8},
    'floppy': {'eL': [-0.11, 0.60, 0.055], 'eR': [0.09, 0.60, 0.055], 'eS': 0.82, 'bY': 0.735, 'bX': 0.11, 'bZ': 0.05, 'bS': 0.9},
    'envelope': {'eL': [-0.10, 0.735, 0.05], 'eR': [0.10, 0.735, 0.05], 'eS': 0.78, 'bY': 0.845, 'bX': 0.105, 'bZ': 0.05, 'bS': 0.85},
    'printer': {'eL': [-0.09, 0.44, 0.10], 'eR': [0.09, 0.44, 0.10], 'eS': 0.72, 'bY': 0.545, 'bX': 0.10, 'bZ': 0.09, 'bS': 0.8},
    'check': {'eL': [-0.27, 0.60, 0.05], 'eR': [-0.16, 0.66, 0.05], 'eS': 0.75, 'bY': 0.76, 'bX': -0.21, 'bZ': 0.05, 'bS': 0.8,
              'bDX': True},
    'vortex': {'eL': [-0.07, 0.70, 0.24], 'eR': [0.09, 0.70, 0.23], 'eS': 0.8, 'bY': 0.84, 'bX': 0.08, 'bZ': 0.22, 'bS': 0.7},
    'bike': {'eL': [-0.19, 0.20, 0.06], 'eR': [0.19, 0.20, 0.06], 'eS': 1.25, 'bY': 0.70, 'bX': 0.28, 'bZ': 0.04, 'bS': 0.05},
    'mobile': {'eL': [-0.30, 0.57, 0.135], 'eR': [0.36, 0.645, 0.015], 'eS': 1.0, 'sL': 1.0, 'sR': 0.5,
               'bY': 1.0, 'bX': 0.3, 'bZ': 0, 'bS': 0.04},
}
_SHAPES = [('shapeAtom', 'atom'), ('shapePile', 'pile'), ('shapeFloppy', 'floppy'), ('shapeEnvelope', 'envelope'),
           ('shapePrinter', 'printer'), ('shapeWizard', 'wizard'), ('shapeCheck', 'check'), ('shapeVortex', 'vortex'),
           ('shapeBike', 'bike'), ('shapeMobile', 'mobile')]


def active_shape(pose):
    for k, n in _SHAPES:
        if pose.get(k):
            return n
    return 'gem'


# ------------------------------------------------------------------------------------------- the pose field
def _rot_yz(v, pivot_y, a):
    y, z = v[1] - pivot_y, v[2]
    v[1] = pivot_y + y * math.cos(a) - z * math.sin(a)
    v[2] = z * math.cos(a) + y * math.sin(a)


def _rot_xy(v, pivot_y, a):
    y, x = v[1] - pivot_y, v[0]
    v[0] = x * math.cos(a) - y * math.sin(a)
    v[1] = pivot_y + y * math.cos(a) + x * math.sin(a)


def apply_pose(v, pose):
    if pose.get('curl'):
        f = ease((0.34 - v[1]) / 0.34)
        if f > 0:
            _rot_yz(v, 0.34, -1.05 * pose['curl'] * f)
    if pose.get('squash'):
        k = pose['squash']
        v[1] = 0.03 + (v[1] - 0.03) * (1 - 0.24 * k)
        v[0] *= 1 + 0.16 * k
        v[2] *= 1 + 0.16 * k
    if pose.get('tilt'):
        f = ease((v[1] - 0.52) / 0.40)
        if f > 0:
            _rot_xy(v, 0.52, 0.38 * pose['tilt'] * f)
    if pose.get('lean'):
        f = ease((v[1] - 0.16) / 0.72)
        if f > 0:
            _rot_yz(v, 0.16, -0.52 * pose['lean'] * f)


def _rotate_about(p, h, a, dz):
    dx, dy = p[0] - h[0], p[1] - h[1]
    p[0] = h[0] + dx * math.cos(a) - dy * math.sin(a)
    p[1] = h[1] + dy * math.cos(a) + dx * math.sin(a)
    p[2] += dz


# ------------------------------------------------------------------------------------------- the wire sweep
def sweep_wire(pose, N, RADIAL, wire_r):
    shape = active_shape(pose)
    pts, ghost = segs_sample(gem_segs(shape == 'wizard') if shape in ('gem', 'wizard') else shape_segs(shape), N)
    P = [list(p) for p in pts]

    def end_hinge(t0, fn):
        i0 = int(math.floor(t0 * (N - 1)))
        h = list(P[i0])
        for i in range(i0, N):
            fn(P[i], h, ease((i / (N - 1) - t0) / (1 - t0)))

    def start_hinge(t0, fn):
        i0 = int(math.ceil(t0 * (N - 1)))
        h = list(P[i0])
        for i in range(i0, -1, -1):
            fn(P[i], h, ease((t0 - i / (N - 1)) / t0))
    if shape in ('gem', 'wizard'):
        if pose.get('wave'):
            w = pose['wave']
            end_hinge(0.84, lambda p, h, f: _rotate_about(p, h, -1.8 * f * w, 0.10 * f * w))
        if pose.get('tap'):
            k = pose['tap']

            def tap(p, h, f):
                p[1] -= 0.10 * f * k
                p[2] += 0.05 * f * k
            start_hinge(0.06, tap)
        if pose.get('scratch'):
            w = pose['scratch']
            end_hinge(0.78, lambda p, h, f: _rotate_about(p, h, -2.05 * f * w, 0.09 * f * w))
        if pose.get('point'):
            w = pose['point']
            start_hinge(0.075, lambda p, h, f: _rotate_about(p, h, 1.25 * f * w, 0.12 * f * w))
        for p in P:
            apply_pose(p, pose)
    pts = np.array(P)
    # the parallel-transport tube (fixed seed normal, NaN-guarded)
    tans = []
    for i in range(N):
        d = pts[min(i + 1, N - 1)] - pts[max(i - 1, 0)]
        n = np.linalg.norm(d)
        tans.append(d / n if n > 0 else np.array([0.0, 1.0, 0.0]))
    n0 = np.array([0.0, 0.0, 1.0])
    n0 = n0 - tans[0] * n0.dot(tans[0])
    nn = np.linalg.norm(n0)
    n0 = n0 / nn if nn > 0.7 else np.array([0.0, 1.0, 0.0])
    nors, bins = [], []
    for i in range(N):
        if i > 0:
            axis = np.cross(tans[i - 1], tans[i])
            s2 = np.linalg.norm(axis)
            if s2 > 1e-8:
                axis = axis / s2
                ang = math.asin(min(s2, 1.0))
                c, sn = math.cos(ang), math.sin(ang)
                n0 = n0 * c + np.cross(axis, n0) * sn + axis * axis.dot(n0) * (1 - c)
            n0 = n0 - tans[i] * n0.dot(tans[i])
            nn = np.linalg.norm(n0)
            n0 = n0 / nn if (nn > 0.7 and np.all(np.isfinite(n0))) else np.array([0.0, 1.0, 0.0])
        nors.append(n0.copy())
        b = np.cross(tans[i], n0)
        bins.append(b / max(np.linalg.norm(b), 1e-12))
    r_mul = np.ones(N)
    for i in range(N):
        if not ghost[i]:
            continue
        for k in range(-3, 4):
            ii = min(max(i + k, 0), N - 1)
            r_mul[ii] = min(r_mul[ii], 0.03 + 0.97 * abs(k) / 4)
    th = np.arange(RADIAL) / RADIAL * TAU
    nors, bins = np.array(nors), np.array(bins)
    ring = (nors[:, None, :] * np.cos(th)[None, :, None] + bins[:, None, :] * np.sin(th)[None, :, None])
    pos = pts[:, None, :] + ring * (wire_r * r_mul)[:, None, None]
    faces = []
    for i in range(N - 1):
        for j in range(RADIAL):
            a, b = i * RADIAL + j, i * RADIAL + (j + 1) % RADIAL
            faces.append((a, a + RADIAL, b + RADIAL, b))        # clippy.js's winding: (a, a+R, b), (b, a+R, b+R)
    return pos.reshape(-1, 3), faces, (pts[0], pts[-1])


# ------------------------------------------------------------------------------------------- spheres (no seam split)
def _unit_sphere(seg):
    """a UV sphere of `seg` rings and segments, shared seam and poles: (verts (n, 3), quads/tris)"""
    vs = [(0.0, 1.0, 0.0)]
    for iy in range(1, seg):
        v = iy / seg
        for ix in range(seg):
            u = ix / seg
            vs.append((-math.cos(u * TAU) * math.sin(v * math.pi), math.cos(v * math.pi), math.sin(u * TAU) * math.sin(v * math.pi)))
    vs.append((0.0, -1.0, 0.0))
    faces = []                                              # three's SphereGeometry winding, its seam and poles shared
    ring = lambda iy, ix: 1 + (iy - 1) * seg + (ix % seg)  # noqa: E731
    for ix in range(seg):
        faces.append((0, ring(1, ix), ring(1, ix + 1)))
    for iy in range(1, seg - 1):
        for ix in range(seg):
            faces.append((ring(iy, ix + 1), ring(iy, ix), ring(iy + 1, ix), ring(iy + 1, ix + 1)))
    last = len(vs) - 1
    for ix in range(seg):
        faces.append((ring(seg - 1, ix + 1), ring(seg - 1, ix), last))
    return np.array(vs), faces


_SPH = {}


def sphere(pose, center, r, o=None):
    o = o or {}
    seg = o.get('seg', 14)
    if seg not in _SPH:
        _SPH[seg] = _unit_sphere(seg)
    U, faces = _SPH[seg]
    out = []
    for x0, y0, z0 in U:
        v = [x0 * r[0], y0 * r[1], z0 * r[2]]
        if o.get('roll'):
            a = o['roll']
            x, y = v[0], v[1]
            v[0], v[1] = x * math.cos(a) - y * math.sin(a), y * math.cos(a) + x * math.sin(a)
        if o.get('yaw'):
            a = o['yaw']
            x, z = v[0], v[2]
            v[0], v[2] = x * math.cos(a) + z * math.sin(a), z * math.cos(a) - x * math.sin(a)
        if o.get('scale') is not None:
            v = [c * o['scale'] for c in v]
        if o.get('blinkK'):
            v[1] *= 1 - 0.80 * o['blinkK']
        v[0] += center[0] + o.get('dx', 0.0)
        v[1] += center[1] + o.get('dy', 0.0)
        v[2] += center[2] + o.get('dz', 0.0)
        if o.get('posed', True):
            apply_pose(v, pose)
        out.append(v)
    return np.array(out), faces


# ------------------------------------------------------------------------------------------- the legal-pad page
GX, GY = 16, 20


def paper_part(pose):
    W2, H2 = 0.36, 0.50
    fUp, fFeed, fCr = pose.get('paperUp', 0), pose.get('paperFeed', 0), pose.get('paperCrumple', 0)
    pos, uv = [], []
    for j in range(GY + 1):
        for i in range(GX + 1):
            u, w = i / GX, j / GY
            gx, gy = (u - 0.5) * W2 * 2, w * H2 * 2
            curl = 0.22 * (max(u + w - 1.35, 0) / 0.65) ** 2 + 0.10 * (max((1 - u) - w - 0.45, 0) / 0.55) ** 2
            px = 0.07 + gx * 0.965 + gy * 0.115 - curl * gx * 0.3
            py = 0.012 + gy * 0.845 + curl * 0.55
            pz = -0.115 - gy * 0.50 + gx * 0.155 + curl * 0.6
            if fCr:
                h1 = math.sin(i * 12.9898 + j * 78.233) * 43758.5453
                h2 = math.sin(i * 39.425 + j * 11.135) * 24634.6345
                tx = gx * 0.42 + (h1 - math.floor(h1) - 0.5) * 0.15
                ty = 0.38 + (gy - 0.5) * 0.35 + (h2 - math.floor(h2) - 0.5) * 0.15
                tz = math.sin(h1) * 0.07
                px += (tx - px) * fCr
                py += (ty - py) * fCr
                pz += (tz - pz) * fCr
            if fUp:
                tx, ty, tz = -0.02 + gx, 0.30 + gy * 0.9, 0.30 - 0.05 * gy
                px += (tx - px) * fUp
                py += (ty - py) * fUp
                pz += (tz - pz) * fUp
            if fFeed:
                tx, ty, tz = gx * 0.7, 0.56 + gy * 0.75, 0.02 * math.sin(w * 9)
                px += (tx - px) * fFeed
                py += (ty - py) * fFeed
                pz += (tz - pz) * fFeed
            pos.append((px, py, pz))
            uv.append((u, w))
    faces = []
    for j in range(GY):
        for i in range(GX):
            a = j * (GX + 1) + i
            faces.append((a, a + 1, a + GX + 2, a + GX + 1))
    return np.array(pos), faces, uv


# ------------------------------------------------------------------------------------------- the whole character
def build_all(pose, N=700, RADIAL=20, wire_r=0.031):
    """-> (verts (n, 3) three's frame, faces, material index per face, uv per face corner or None)"""
    parts = []
    wpos, wfaces, ends = sweep_wire(pose, N, RADIAL, wire_r)
    parts.append((wpos, wfaces, 0, None))
    for e in ends:
        v, f = sphere({}, e, [wire_r] * 3, {'seg': 10, 'posed': False})
        parts.append((v, f, 0, None))
    F = FACE[active_shape(pose)]
    browUp, browDn, blink = pose.get('browUp', 0), pose.get('browDown', 0), pose.get('blink', 0)
    lookX, lookY = pose.get('lookAside', 0) * 0.030, pose.get('lookUp', 0) * 0.028
    peer, bulge, droop = pose.get('peer', 0), pose.get('bulge', 0), pose.get('droopEyes', 0)
    phones = pose.get('phones', 0)
    for s in (-1, 1):
        ec = Vector(F['eL'] if s < 0 else F['eR'])
        if droop:
            ec = ec.lerp(Vector((s * 0.015, 0.40 if s < 0 else 0.24, 0.09)), droop)
        per = F.get('sL', 1) if s < 0 else F.get('sR', 1)
        eye_s = F['eS'] * per * (1 + (0.55 if s < 0 else -0.42) * peer) * (1 + 0.45 * bulge)
        v, f = sphere(pose, ec, [0.095, 0.130, 0.055], {'blinkK': blink, 'scale': eye_s})
        parts.append((v, f, 1, None))
        p_over = F.get('pL') if s < 0 else F.get('pR')
        pc = Vector(p_over) if p_over else Vector((ec.x - s * 0.012 * eye_s, ec.y - 0.024 * eye_s, ec.z + 0.052 * eye_s))
        v, f = sphere(pose, pc, [0.042, 0.052, 0.017], {'blinkK': 0 if p_over else blink, 'dx': lookX, 'dy': lookY,
                                                        'scale': 1 if p_over else eye_s, 'seg': 10})
        parts.append((v, f, 2, None))
        b_over = F.get('bL') if s < 0 else F.get('bR')
        if b_over:
            bc = Vector(b_over)
        elif F.get('bDX'):
            bc = Vector((F['bX'] + (0.11 if s > 0 else 0), F['bY'], F['bZ']))
        else:
            bc = Vector((s * F['bX'], F['bY'], F['bZ']))
        if phones:
            bc = bc.lerp(Vector((s * 0.165, 0.775, 0.03)), phones)
        roll = (1 - phones) * s * (-0.18 - 0.42 * browDn + 0.38 * browUp)
        v, f = sphere(pose, bc, [0.066, 0.019, 0.024], {'roll': roll, 'yaw': phones * s * 1.45,
                                                        'dy': (0.038 * browUp - 0.032 * browDn) * (1 - phones),
                                                        'scale': F['bS'] * (1 + 2.0 * phones), 'seg': 10})
        parts.append((v, f, 2, None))
    v, f = sphere(pose, Vector((0.03, 0.88 + 0.10 * phones, 0.0)), [0.175, 0.075, 0.03],
                  {'scale': 0.012 + 0.988 * phones, 'seg': 10})
    parts.append((v, f, 2, None))
    pk = pose.get('pencil', 0)
    pcen = Vector((0.0, 0.55, -0.01)).lerp(Vector((0.24, 0.34, 0.15)), pk)
    proll, psc = -0.9 * pk, 0.012 + 0.988 * pk
    v, f = sphere(pose, pcen, [0.016, 0.15, 0.016], {'roll': proll, 'scale': psc, 'seg': 8})
    parts.append((v, f, 4, None))
    tip = Vector((math.sin(proll) * 0.15, -math.cos(proll) * 0.15, 0)) * psc
    v, f = sphere(pose, pcen + tip, [0.017, 0.035, 0.017], {'roll': proll, 'scale': psc, 'seg': 8})
    parts.append((v, f, 2, None))
    v, f, uv = paper_part(pose)
    parts.append((v, f, 3, uv))
    verts, faces, mats, uvs = [], [], [], []
    base = 0
    for v, f, m, uv in parts:
        verts.append(np.asarray(v, dtype=np.float64))
        for face in f:
            faces.append(tuple(i + base for i in face))
            mats.append(m)
            uvs.append([uv[i] for i in face] if uv is not None else [(0.0, 0.0)] * len(face))
        base += len(v)
    return np.concatenate(verts, axis=0), faces, mats, uvs


def _to_bl(P):
    return np.stack([P[:, 0], -P[:, 2], P[:, 1]], axis=1)


def paper_image(name='clippy_paper'):
    W, H = 64, 88
    px = np.zeros((H, W, 4), dtype=np.float32)
    col = np.array([244, 232, 168], dtype=np.float32)
    px[...] = np.append(col, 255) / 255.0
    for j in range(H):
        if j % 8 == 2 and j > 8:
            px[j, :, :3] = np.array([150, 175, 215]) / 255.0
    px[:, 9, :3] = np.array([225, 130, 130]) / 255.0
    lin = np.where(px[..., :3] <= 0.04045, px[..., :3] / 12.92, ((px[..., :3] + 0.055) / 1.055) ** 2.4)
    img = bpy.data.images.new(name, W, H, float_buffer=True)
    out = px.copy()
    out[..., :3] = lin
    img.pixels.foreach_set(out.ravel())
    img.pack()
    return img


def _srgb(hexcol):
    c = ((hexcol >> 16) & 255, (hexcol >> 8) & 255, hexcol & 255)
    return tuple(((x / 255) / 12.92) if x / 255 <= 0.04045 else (((x / 255) + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def _materials(name):
    def pbr(n, colour, metal, rough):
        m = bpy.data.materials.new(f'{name}_{n}')
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = _srgb(colour)
        b.inputs['Metallic'].default_value = metal
        b.inputs['Roughness'].default_value = rough
        return m
    chrome = pbr('chrome', 0xcdd3dc, 1.0, 0.17)
    white = pbr('white', 0xffffff, 0.0, 0.32)
    black = pbr('black', 0x14161a, 0.1, 0.42)
    paper = pbr('paper', 0xffffff, 0.0, 0.92)
    nt = paper.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = paper_image(f'{name}_paper')
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    paper.use_backface_culling = False
    pencil = pbr('pencil', 0xe8b93c, 0.0, 0.6)
    return [chrome, white, black, paper, pencil]


def _ease_track(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, wa), (tb, wb) in zip(keys, keys[1:]):
        if ta <= t <= tb:
            return wa + (wb - wa) * ease((t - ta) / max(tb - ta, 1e-6))
    return keys[-1][1]


def _hash1(k):
    s = math.sin(k * 12.9898) * 43758.5453
    return s - math.floor(s)


def _T(dur, tracks):
    return {'dur': dur, 'tracks': tracks}


def _hold(a, b, w, dur):
    return [[a, 0], [a + 0.45, w], [b, w], [min(b + 0.5, dur), 0]]


CLIPS = {
    'RestPose': _T(1.6, {}),
    'Idle1_1': _T(4.2, {'droopEyes': [[0.4, 0], [1.2, 1], [3.2, 1], [4.0, 0]],
                        'lookAside': [[1.4, 0], [1.9, 0.6], [2.5, -0.6], [3.0, 0]]}),
    'IdleEyeBrowRaise': _T(2.2, {'browUp': [[0.3, 0], [0.6, 0.9], [0.9, 0.1], [1.2, 0.9], [1.8, 0]]}),
    'IdleSideToSide': _T(3.6, {'tilt': [[0.2, 0], [0.9, 0.6], [1.8, -0.6], [2.7, 0.5], [3.5, 0]],
                               'lookAside': [[0.2, 0], [0.9, 0.8], [1.8, -0.8], [2.7, 0.7], [3.5, 0]]}),
    'IdleFingerTap': _T(3.2, {'tap': [[0.2, 0], [0.5, 0.9], [0.7, 0.35], [0.9, 0.9], [1.1, 0.35], [1.3, 0.9],
                                      [1.5, 0.35], [1.7, 0.9], [2.1, 0.9], [2.8, 0]],
                              'lookAside': _hold(0.3, 2.4, -0.6, 3.2)}),
    'IdleHeadScratch': _T(3.6, {'scratch': [[0.3, 0], [1.0, 1], [1.25, 0.84], [1.5, 1], [1.75, 0.84], [2.0, 1], [2.9, 0]],
                                'tilt': _hold(0.3, 2.6, 0.4, 3.6), 'browDown': _hold(0.4, 2.6, 0.5, 3.6)}),
    'IdleSnooze': _T(5.6, {'shapePile': [[0.5, 0], [1.7, 0.85], [4.6, 0.85], [5.5, 0]],
                           'blink': [[1.2, 0], [1.9, 0.95], [4.4, 0.95], [5.2, 0]],
                           'browDown': [[1.0, 0], [1.8, 0.3], [4.4, 0.3], [5.2, 0]]}),
    'IdleRopePile': _T(6.4, {'droopEyes': [[0.3, 0], [1.0, 1], [1.6, 1], [2.2, 0]],
                             'shapePile': [[1.6, 0], [2.6, 1], [5.2, 1], [6.2, 0]],
                             'blink': [[3.4, 0], [3.55, 1], [3.7, 0]]}),
    'IdleAtom': _T(5.8, {'shapeAtom': [[0.4, 0], [1.6, 1], [4.6, 1], [5.6, 0]],
                         'lookAside': [[1.8, 0], [2.5, 0.9], [3.2, -0.9], [3.9, 0.9], [4.5, 0]],
                         'lookUp': [[1.8, 0], [2.2, 0.7], [2.9, -0.7], [3.6, 0.7], [4.3, -0.5], [4.8, 0]]}),
    'Alert': _T(2.4, {'lean': [[0.1, 0], [0.4, 0.9], [1.9, 0.9], [2.4, 0]],
                      'browUp': [[0.1, 0], [0.35, 0.85], [2.0, 0.85], [2.4, 0]],
                      'bulge': [[0.1, 0], [0.35, 1.2], [1.9, 1.2], [2.4, 0]],
                      'squash': [[0.4, 0], [0.5, 0.4], [0.62, 0], [0.74, 0.4], [0.86, 0]]}),
    'GetAttention': _T(3.0, {'browUp': _hold(0.2, 2.4, 0.85, 3.0), 'bulge': _hold(0.2, 2.3, 1.2, 3.0),
                             'tap': [[0.4, 0], [0.7, 0.8], [1.9, 0.8], [2.4, 0]],
                             'squash': [[0.3, 0], [0.5, -0.22], [1.9, -0.22], [2.4, 0]],
                             '@hopY': [[0.3, 0], [0.6, 1], [1.6, 1], [2.2, 0]]}),
    'Greeting': _T(3.2, {'wave': [[0.2, 0], [0.7, 1], [1.0, 0.55], [1.3, 1], [1.6, 0.55], [1.9, 1], [2.6, 0]],
                         'browUp': _hold(0.1, 2.4, 0.75, 3.2), 'lean': _hold(0.2, 2.4, 0.45, 3.2),
                         'tilt': _hold(0.3, 2.3, 0.4, 3.2)}),
    'Wave': _T(2.8, {'wave': [[0.15, 0], [0.55, 1], [0.85, 0.5], [1.15, 1], [1.45, 0.5], [1.75, 1], [2.4, 0]],
                     'browUp': _hold(0.1, 2.1, 0.7, 2.8)}),
    'Explain': _T(3.0, {'point': _hold(0.25, 2.3, 0.9, 3.0), 'browUp': _hold(0.3, 2.2, 0.45, 3.0),
                        'lookAside': _hold(0.3, 2.2, -0.5, 3.0)}),
    'GestureRight': _T(2.4, {'wave': _hold(0.2, 1.8, 0.85, 2.4), 'lookAside': _hold(0.2, 1.8, 0.7, 2.4)}),
    'GestureLeft': _T(2.4, {'point': _hold(0.2, 1.8, 0.9, 2.4), 'lookAside': _hold(0.2, 1.8, -0.7, 2.4),
                            'tilt': _hold(0.2, 1.8, -0.3, 2.4)}),
    'GestureUp': _T(2.4, {'wave': _hold(0.2, 1.8, 0.7, 2.4), 'lookUp': _hold(0.2, 1.8, 0.85, 2.4),
                          'browUp': _hold(0.2, 1.8, 0.6, 2.4), 'lean': _hold(0.2, 1.8, -0.2, 2.4)}),
    'GestureDown': _T(2.4, {'tap': _hold(0.2, 1.8, 0.85, 2.4), 'lean': _hold(0.2, 1.8, 0.5, 2.4),
                            'lookUp': _hold(0.2, 1.8, -0.85, 2.4)}),
    'LookRight': _T(2.0, {'lookAside': _hold(0.2, 1.5, 0.95, 2.0), 'tilt': _hold(0.2, 1.5, 0.15, 2.0)}),
    'LookLeft': _T(2.0, {'lookAside': _hold(0.2, 1.5, -0.95, 2.0), 'tilt': _hold(0.2, 1.5, -0.15, 2.0)}),
    'LookUp': _T(2.0, {'lookUp': _hold(0.2, 1.5, 0.95, 2.0), 'browUp': _hold(0.2, 1.5, 0.3, 2.0)}),
    'LookDown': _T(2.0, {'lookUp': _hold(0.2, 1.5, -0.95, 2.0)}),
    'LookUpRight': _T(2.0, {'lookUp': _hold(0.2, 1.5, 0.8, 2.0), 'lookAside': _hold(0.2, 1.5, 0.8, 2.0)}),
    'LookUpLeft': _T(2.0, {'lookUp': _hold(0.2, 1.5, 0.8, 2.0), 'lookAside': _hold(0.2, 1.5, -0.8, 2.0)}),
    'LookDownRight': _T(2.0, {'lookUp': _hold(0.2, 1.5, -0.8, 2.0), 'lookAside': _hold(0.2, 1.5, 0.8, 2.0)}),
    'LookDownLeft': _T(2.0, {'lookUp': _hold(0.2, 1.5, -0.8, 2.0), 'lookAside': _hold(0.2, 1.5, -0.8, 2.0)}),
    'CheckingSomething': _T(4.2, {'paperUp': [[0.3, 0], [1.0, 1], [3.4, 1], [4.1, 0]],
                                  'lookUp': _hold(0.5, 3.2, -0.6, 4.2), 'browDown': _hold(0.5, 3.2, 0.3, 4.2),
                                  'lookAside': [[1.2, 0], [1.9, 0.5], [2.6, -0.5], [3.2, 0]]}),
    'Writing': _T(4.6, {'pencil': [[0.3, 0], [0.9, 1], [3.8, 1], [4.5, 0]],
                        'lean': [[0.5, 0], [1.1, 1.05], [1.5, 0.9], [1.9, 1.1], [2.3, 0.9], [2.7, 1.1], [3.1, 0.95],
                                 [3.8, 1.0], [4.4, 0]],
                        'lookUp': _hold(0.5, 3.6, -0.9, 4.6)}),
    'Processing': _T(3.6, {'browDown': _hold(0.3, 2.8, 0.55, 3.6),
                           'tilt': [[0.3, 0], [0.8, 0.3], [1.3, -0.3], [1.8, 0.3], [2.3, -0.3], [2.9, 0]],
                           'lookAside': [[0.3, 0], [0.7, 0.7], [1.1, -0.7], [1.5, 0.7], [1.9, -0.7], [2.5, 0]],
                           'squash': [[0.5, 0], [0.7, 0.12], [0.9, 0], [1.1, 0.12], [1.3, 0], [1.5, 0.12], [1.7, 0]]}),
    'Thinking': _T(3.4, {'tilt': [[0.2, 0], [0.8, -0.8], [2.8, -0.8], [3.4, 0]],
                         'browDown': _hold(0.2, 2.7, 0.9, 3.4), 'lookUp': _hold(0.3, 2.6, 1, 3.4),
                         'lookAside': [[0.3, 0], [0.9, 0.7], [1.9, 0.7], [2.2, -0.5], [2.6, -0.5], [3.2, 0]]}),
    'Searching': _T(3.8, {'peer': [[0.3, 0], [0.9, 1], [3.0, 1], [3.7, 0]],
                          'lean': _hold(0.3, 3.0, 0.5, 3.8), 'browDown': _hold(0.3, 3.0, 0.25, 3.8),
                          'lookAside': [[0.5, 0], [1.2, 0.8], [2.0, -0.8], [2.8, 0.6], [3.4, 0]]}),
    'Hearing_1': _T(3.6, {'phones': [[0.2, 0], [0.7, 1], [2.9, 1], [3.5, 0]],
                          'tilt': [[0.8, 0], [1.1, 0.35], [1.4, -0.35], [1.7, 0.35], [2.0, -0.35], [2.3, 0.35], [2.7, 0]],
                          'squash': [[0.9, 0], [1.1, 0.08], [1.3, 0], [1.5, 0.08], [1.7, 0], [1.9, 0.08], [2.1, 0]]}),
    'Congratulate': _T(4.6, {'shapeCheck': [[0.3, 0], [1.2, 1], [3.6, 1], [4.5, 0]],
                             'browUp': [[1.2, 0], [1.6, 0.8], [3.4, 0.8], [4.0, 0]],
                             '@hopY': [[1.4, 0], [1.7, 0.7], [2.6, 0.7], [3.1, 0]]}),
    'GetArtsy': _T(5.0, {'shapeMobile': [[0.3, 0], [1.3, 1], [4.0, 1], [4.9, 0]],
                         'tilt': [[1.6, 0], [2.4, 0.25], [3.2, -0.25], [4.0, 0.2], [4.6, 0]]}),
    'GetTechy': _T(4.0, {'browDown': _hold(0.3, 3.2, 0.45, 4.0), 'lean': _hold(0.3, 3.2, 0.45, 4.0),
                         'tap': [[0.5, 0], [0.65, 0.6], [0.8, 0.2], [0.95, 0.6], [1.1, 0.2], [1.25, 0.6],
                                 [1.4, 0.2], [1.55, 0.6], [1.7, 0.2], [1.85, 0.6], [2.4, 0.6], [3.2, 0]],
                         'lookAside': [[0.4, 0], [0.7, 0.5], [1.0, -0.5], [1.3, 0.5], [1.6, -0.5], [2.2, 0]]}),
    'GetWizardy': _T(4.8, {'shapeWizard': [[0.3, 0], [1.2, 1], [3.8, 1], [4.7, 0]],
                           'wave': [[1.4, 0], [1.9, 0.8], [2.3, 0.45], [2.7, 0.8], [3.1, 0.45], [3.6, 0]],
                           'browUp': [[1.2, 0], [1.7, 0.6], [3.4, 0.6], [4.0, 0]]}),
    'Save': _T(4.6, {'shapeFloppy': [[0.4, 0], [1.4, 1], [3.5, 1], [4.5, 0]], 'blink': [[2.2, 0], [2.35, 1], [2.5, 0]]}),
    'Print': _T(5.2, {'shapePrinter': [[0.4, 0], [1.4, 1], [4.2, 1], [5.1, 0]],
                      'paperFeed': [[1.6, 0], [2.4, 0.55], [3.6, 1], [4.1, 1], [4.7, 0]]}),
    'EmptyTrash': _T(5.0, {'shapeVortex': [[0.3, 0], [1.2, 1], [4.0, 1], [4.9, 0]],
                           'paperCrumple': [[0.9, 0], [1.8, 1], [3.8, 1], [4.5, 0]],
                           '@spinY': [[1.9, 0], [2.3, 2.2], [3.7, 2.2], [4.1, 0]]}),
    'SendMail': _T(4.6, {'shapeEnvelope': [[0.4, 0], [1.4, 1], [3.5, 1], [4.4, 0]], '@hopY': [[3.4, 0], [3.7, 1], [4.1, 0]]}),
    'Show': _T(2.6, {'@scale': [[0, 0.01], [0.55, 1.14], [0.85, 0.95], [1.15, 1]],
                     'browUp': [[0.6, 0], [1.0, 0.8], [2.1, 0.8], [2.6, 0]], 'wave': [[0.9, 0], [1.4, 0.8], [2.2, 0]]}),
    'Hide': _T(2.2, {'@scale': [[0.2, 1], [0.8, 1.09], [1.7, 0.01], [2.2, 0.01]],
                     'squash': [[0.3, 0], [0.9, 0.5], [1.6, 0]], 'browUp': [[0.2, 0], [0.5, 0.7], [1.2, 0]]}),
    'GoodBye': _T(12.0, {'wave': [[0.3, 0], [0.8, 1], [1.15, 0.5], [1.5, 1], [2.1, 0]],
                         'shapeBike': [[2.0, 0], [3.0, 1], [5.6, 1]], '@slideX': [[3.4, 0], [5.4, 1]],
                         '@scale': [[4.6, 1], [5.5, 0.01]]}),
}


class Clippy:
    def __init__(self, root, inner, obj, height):
        self.root, self.inner, self.obj, self.H = root, inner, obj, height
        self.active = []
        self.clips = list(CLIPS)
        self.morphs = list(MORPHS)

    def play(self, name, t0=0.0):
        """schedule a clip at scene second t0 (frame = frame_start + t0 * fps); an unknown name raises"""
        if name not in CLIPS:
            raise KeyError(f'clippy has no clip {name!r} ({", ".join(CLIPS)})')
        self.active.append({'clip': CLIPS[name], 't0': t0, 'name': name})

    def play_all(self, t0=0.8, gap=0.5):
        t, order = t0, []
        for name, c in CLIPS.items():
            self.play(name, t)
            order.append((name, t, c['dur']))
            t += c['dur'] + gap
        return order

    def current_clip(self, t):
        for a in self.active:
            if a['t0'] <= t <= a['t0'] + a['clip']['dur']:
                return a['name']
        return ''

    def state(self, t):
        """clippy.js update(t): the morph weights and the inner transform (three's terms) at second t"""
        W = {n: 0.0 for n in MORPHS}
        scale, hop, spin, slide, any_clip = 1.0, 0.0, 0.0, 0.0, False
        for a in self.active:
            ct = t - a['t0']
            if ct < 0 or ct > a['clip']['dur'] + 0.1:
                continue
            any_clip = True
            for n, keys in a['clip']['tracks'].items():
                w = _ease_track(keys, ct)
                if n == '@scale':
                    scale = w
                elif n == '@hopY':
                    hop = w
                elif n == '@spinY':
                    spin += w * ct
                elif n == '@slideX':
                    slide = w
                else:
                    W[n] += w
        if not any_clip:
            bi = math.floor(t / 2.8)
            bt = t - (bi * 2.8 + 2.0 * _hash1(bi + 3))
            if 0 < bt < 0.22:
                W['blink'] += math.sin((bt / 0.22) * math.pi)
            wi = math.floor(t / 4.3)
            wt = t - (wi * 4.3 + 2.6 * _hash1(wi + 11))
            if 0 < wt < 0.5 and _hash1(wi) > 0.45:
                W['browUp'] += 0.5 * math.sin((wt / 0.5) * math.pi)
        H = self.H
        tr = {'scale': max(scale, 0.01), 'x': slide * -2.6,
              'y': 0.012 * H * math.sin(t * 1.7) + hop * abs(math.sin(t * math.pi * 3.2)) * 0.13 * H,
              'rz': 0.022 * math.sin(t * 0.9 + 1.3), 'ry': 0.05 * math.sin(t * 0.53) + spin * 1.9}
        return {n: min(max(w, -1.0), 1.25) for n, w in W.items()}, tr

    def bake(self, f0, f1, scene=None):
        """key every frame f0..f1 (LINEAR): the shape keys and the inner object's transform"""
        from bpy_extras import anim_utils
        scene = scene or bpy.context.scene
        fps = scene.render.fps / scene.render.fps_base
        start = scene.frame_start
        sk = self.obj.data.shape_keys
        ad = sk.animation_data or sk.animation_data_create()
        ad.action = bpy.data.actions.new(f'{self.obj.name}|morphs')
        ad.action_slot = ad.action.slots.new(id_type='KEY', name=sk.name)
        cb = anim_utils.action_ensure_channelbag_for_slot(ad.action, ad.action_slot)
        ia = self.inner.animation_data or self.inner.animation_data_create()
        ia.action = bpy.data.actions.new(f'{self.inner.name}|move')
        ia.action_slot = ia.action.slots.new(id_type='OBJECT', name=self.inner.name)
        cbi = anim_utils.action_ensure_channelbag_for_slot(ia.action, ia.action_slot)
        self.inner.rotation_mode = 'XYZ'
        series = {}
        for f in range(f0, f1 + 1):
            t = (f - start) / fps
            W, tr = self.state(t)
            for n, w in W.items():
                series.setdefault((cb, f'key_blocks["{n}"].value', 0), []).append((f, w))
            loc = (tr['x'], 0.0, tr['y'])                    # three (x, y, z) -> Blender (x, -z, y)
            rot = (0.0, -tr['rz'], tr['ry'])                 # three Euler XYZ (0, ry, rz) -> Blender XYZ (0, -rz, ry)
            for i in range(3):
                series.setdefault((cbi, 'location', i), []).append((f, loc[i]))
                series.setdefault((cbi, 'rotation_euler', i), []).append((f, rot[i]))
                series.setdefault((cbi, 'scale', i), []).append((f, tr['scale']))
        for (bag, path, idx), kv in series.items():
            fc = bag.fcurves.new(path, index=idx)
            fc.keyframe_points.add(len(kv))
            fc.keyframe_points.foreach_set('co', [c for f, v in kv for c in (f, v)])
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.update()
        return {'frames': [f0, f1], 'fcurves': len(series)}


def make_clippy(height=1.2, wire_radius=0.031, name='clippy', location=(0.0, 0.0, 0.0), rotation=0.0, collection=None,
                N=700, RADIAL=20):
    """build Clippy: an outer root (placement: location, heading deg about +Z), the inner object the clips move, and the
    mesh (scale = height) with 31 shape keys -> Clippy"""
    scene = bpy.context.scene
    col = collection or bpy.data.collections.new(name)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    base_v, faces, mats, uvs = build_all({}, N, RADIAL, wire_radius)
    me = bpy.data.meshes.new(name)
    me.from_pydata(_to_bl(base_v).tolist(), [], faces)
    me.validate()
    uv = me.uv_layers.new(name='UVMap')
    flat_uv = [c for face_uv in uvs for c in face_uv]
    uv.data.foreach_set('uv', np.array(flat_uv, dtype=np.float32).ravel())
    me.polygons.foreach_set('material_index', np.array(mats, dtype=np.int32))
    me.polygons.foreach_set('use_smooth', np.ones(len(faces), dtype=bool))
    for m in _materials(name):
        me.materials.append(m)
    obj = bpy.data.objects.new(name, me)
    obj.scale = (height, height, height)
    root = bpy.data.objects.new(name + '_root', None)
    inner = bpy.data.objects.new(name + '_inner', None)
    for o in (root, inner, obj):
        col.objects.link(o)
    inner.parent = root
    obj.parent = inner
    root.location = Vector(location)
    root.rotation_euler = Euler((0.0, 0.0, math.radians(rotation)))
    obj.shape_key_add(name='Basis', from_mix=False)
    for n in MORPHS:
        v, _f, _m, _u = build_all({n: 1}, N, RADIAL, wire_radius)
        if len(v) != len(base_v):
            raise RuntimeError(f'clippy morph {n}: {len(v)} vertices against the base {len(base_v)}')
        kb = obj.shape_key_add(name=n, from_mix=False)
        kb.data.foreach_set('co', _to_bl(v).astype(np.float32).ravel())
        kb.slider_min, kb.slider_max = -1.0, 1.25
        kb.value = 0.0
    return Clippy(root, inner, obj, height)
