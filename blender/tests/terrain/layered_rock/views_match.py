"""Photo-matched cameras (numpy only): each reference photograph's camera described by its relation to the landform,
and the camera with the same relation found on a generated terrain, so the render beside the photo shows the same
kind of view (the same height above the river, the same distance to the butte, the same angle along the canyon).

Frames: the terrain frame (x east, y north, metres; arrays row 0 = south) for both the reference DEM (centred on
(0, 0), refs.Reference.h) and a generated main level (x0, y0, cell). Azimuths are compass degrees (0 north, 90 east).

    cam = photo_camera(ref, view)            # the photo's camera on the DEM: x, y, z, az, pitch, lens
    rel = relation(ref.h, ref.pixel, (0, 0) frame, cam, view)      # its relation to the river / the target
    gen = match(h, cell, x0, y0, rel, view)  # a camera on the generated level with that relation

View kinds (view['kind']):
  river    the canyon views: relation = distance to the trunk river, height above it, the view's angle to the
           river's local downstream direction (mirrored when the camera stands on the other bank)
  target   the butte and wall views: relation = the distance and bearing to a target (view['target']: lat, lon, or
           found as the highest ground near the view axis), the camera's height above the floor, the view's offset
           from the bearing; on the generated terrain the target is a butte (a caprock remnant of about the same
           relief) or a wall point, and the camera stands at that distance on floor-level ground with a clear sight
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
if TN not in sys.path:
    sys.path.insert(0, TN)

from judge import family as F  # noqa: E402

EYE = 1.7


def sample(h, cell, x0, y0, x, y):
    """Bilinear height at world (x, y) on a level (row 0 south)."""
    return F.sample(h, (np.asarray(x, np.float64) - x0) / cell - 0.5, (np.asarray(y, np.float64) - y0) / cell - 0.5)


def slope_deg(h, cell):
    gy, gx = np.gradient(np.asarray(h, np.float64), cell)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def ray_clear(h, cell, x0, y0, cam, az, pitch, dist=400.0, clearance=0.5):
    """True when the view ray (from cam (x, y, z), compass az, pitch degrees) stays clearance metres above the
    ground for its first `dist` metres (the camera does not face a wall)."""
    t = np.linspace(4.0, dist, 120)
    a = math.radians(az)
    x = cam[0] + t * math.sin(a)
    y = cam[1] + t * math.cos(a)
    z = cam[2] + t * math.tan(math.radians(pitch))
    g = sample(h, cell, x0, y0, x, y)
    return bool(np.all(z - g >= clearance))


# ----------------------------------------------------------------------------------------------- the river ---

def trunk_xy(h, cell, x0, y0):
    """The trunk river (the judge's trunk) as world points, upstream first; [] when none."""
    path = F.trunk(h, cell)
    if not path:
        return np.zeros((0, 2))
    return np.array([(x0 + (i + 0.5) * cell, y0 + (j + 0.5) * cell) for i, j in path])


def river_at(P, x, y, half=8):
    """(distance, index, downstream azimuth, side): the trunk point nearest (x, y), the flow direction there and
    the side the point lies on (+1 right of the flow, -1 left)."""
    d = np.hypot(P[:, 0] - x, P[:, 1] - y)
    i = int(np.argmin(d))
    j0, j1 = max(i - half, 0), min(i + half, len(P) - 1)
    v = P[j1] - P[j0]
    flow = math.degrees(math.atan2(v[0], v[1])) % 360.0
    w = np.array([x, y]) - P[i]
    side = 1 if (v[0] * w[1] - v[1] * w[0]) < 0 else -1          # cross < 0: the point is right of the flow
    return float(d[i]), i, flow, side


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def slide_to_edge(h, cell, x0, y0, x, y, az, max_m=300.0, drop=20.0):
    """From (x, y) forward along az in 3 m steps until the ground 10-40 m ahead lies more than `drop` below: the
    brink (photographers stand at it; a GPS fix or a matched spot is often tens of metres back)."""
    a = math.radians(az)
    ux, uy = math.sin(a), math.cos(a)
    ahead = np.array([10.0, 20.0, 30.0, 40.0])
    for s in np.arange(0.0, max_m, 3.0):
        px, py = x + s * ux, y + s * uy
        z = float(sample(h, cell, x0, y0, px, py))
        za = float(np.min(sample(h, cell, x0, y0, px + ahead * ux, py + ahead * uy)))
        if za < z - drop:
            return float(px), float(py)
    return float(x), float(y)


def river_heading(P, x, y, look, toward_deg):
    """The heading of a view along the river from (x, y): the local downstream direction ('downstream') or its
    reverse ('upstream'), turned toward_deg toward the river's side of the camera."""
    d, i, flow, side = river_at(P, x, y)
    b = math.degrees(math.atan2(P[i, 0] - x, P[i, 1] - y)) % 360.0
    if look == 'across':                      # facing the river (a loop below a rim), turned toward_deg clockwise
        return (b + float(toward_deg)) % 360.0
    base = flow if look == 'downstream' else (flow + 180.0) % 360.0
    return (base + math.copysign(float(toward_deg), wrap(b - base))) % 360.0


def to_brink(h, cell, x0, y0, P, x, y, max_descent=25.0):
    """Toward the nearest river point to the brink of the gorge: the first point where the ground 12 m further
    drops at 45 degrees or more (a DEM rounds a rim into a shoulder that a gentler test stops on, and from a
    shoulder a view along the gorge meets the ground a few metres ahead), not walking more than max_descent down
    from the start (then the last point above that)."""
    d = np.hypot(P[:, 0] - x, P[:, 1] - y)
    i = int(np.argmin(d))
    a = math.atan2(P[i, 0] - x, P[i, 1] - y)
    ux, uy = math.sin(a), math.cos(a)
    z0 = float(sample(h, cell, x0, y0, x, y))
    last = (float(x), float(y))
    for s in np.arange(0.0, min(500.0, float(d[i])), 2.0):
        px, py = x + s * ux, y + s * uy
        z = float(sample(h, cell, x0, y0, px, py))
        if z < z0 - max_descent:
            return last
        if float(sample(h, cell, x0, y0, px + 12.0 * ux, py + 12.0 * uy)) < z - 12.0:
            return float(px), float(py)
        last = (float(px), float(py))
    return last


def ray_hit(h, cell, x0, y0, cam, az, pitch, reach=20000.0):
    """Where the view axis from cam (x, y, z) at compass az and pitch first meets the ground: (x, y, distance) or
    None when it leaves the level or never comes down."""
    a = math.radians(az)
    n = h.shape[0]
    t = np.concatenate([np.linspace(2.0, 400.0, 200), np.linspace(400.0, reach, 400)[1:]])
    x = cam[0] + t * math.sin(a)
    y = cam[1] + t * math.cos(a)
    z = cam[2] + t * math.tan(math.radians(pitch))
    inside = (x > x0) & (y > y0) & (x < x0 + n * cell) & (y < y0 + n * cell)
    g = sample(h, cell, x0, y0, x, y)
    below = inside & (z <= g)
    if not below.any():
        return None
    k = int(np.argmax(below))
    return float(x[k]), float(y[k]), float(t[k])


# ------------------------------------------------------------------------------------------- the relations ---

def relation(h, cell, x0, y0, cam, view):
    """The photo camera's relation to its landform (see the module doc)."""
    kind = view['kind']
    if kind == 'river':
        cam = dict(cam)
        P0 = trunk_xy(h, cell, x0, y0)
        if view.get('edge'):
            cam['x'], cam['y'] = to_brink(h, cell, x0, y0, P0, cam['x'], cam['y'])
        if view.get('look'):
            cam['az'] = river_heading(P0, cam['x'], cam['y'], view['look'], view.get('toward_deg', 0.0))
    z_ground = float(sample(h, cell, x0, y0, cam['x'], cam['y']))
    rel = dict(kind=kind, pitch=cam['pitch'], lens=cam['lens'], eye=cam.get('eye', EYE), edge=bool(view.get('edge')),
               x=float(cam['x']), y=float(cam['y']), az=float(cam['az']))
    for k in ('look', 'toward_deg', 'hit_river_m'):
        if k in view:
            rel[k] = view[k]
    if kind == 'river':
        P = trunk_xy(h, cell, x0, y0)
        d, i, flow, side = river_at(P, cam['x'], cam['y'])
        zr = float(sample(h, cell, x0, y0, P[i, 0], P[i, 1]))
        rel.update(dist=d, above=z_ground - zr, rel_az=wrap(cam['az'] - flow), side=side)
        hit = ray_hit(h, cell, x0, y0, (cam['x'], cam['y'], z_ground + rel['eye']), cam['az'], cam['pitch'])
        if hit is not None:
            # how close to the river the view axis comes down (the photo looks into the gorge)
            rel.update(hit_dist=hit[2], hit_river=float(np.min(np.hypot(P[:, 0] - hit[0], P[:, 1] - hit[1]))))
    else:
        tx, ty = view['target_xy']
        d = math.hypot(tx - cam['x'], ty - cam['y'])
        bearing = math.degrees(math.atan2(tx - cam['x'], ty - cam['y'])) % 360.0
        fl = floor_level(h, cell, x0, y0, cam['x'], cam['y'])
        gx, gy = np.meshgrid(np.linspace(-60.0, 60.0, 9), np.linspace(-60.0, 60.0, 9))
        tz = float(np.max(sample(h, cell, x0, y0, tx + gx, ty + gy)))
        rel.update(dist=d, offset=wrap(cam['az'] - bearing), above_floor=z_ground - fl, target_top=tz - fl)
    return rel


def floor_level(h, cell, x0, y0, x, y, radius=1500.0):
    """The local floor: the 10th percentile of the ground within radius of (x, y)."""
    n = h.shape[0]
    i = int((x - x0) / cell)
    j = int((y - y0) / cell)
    r = int(radius / cell)
    w = h[max(j - r, 0):min(j + r, n), max(i - r, 0):min(i + r, n)]
    return float(np.percentile(w, 10))


# ----------------------------------------------------------------------------------- the generated terrain ---

def match_river(h, cell, x0, y0, rel, prefer=0.5, tol=0.25):
    """A camera on the generated level standing in the photo's relation to the river (module doc)."""
    P = trunk_xy(h, cell, x0, y0)
    if len(P) < 10:
        raise ValueError('no trunk river on the generated level')
    n = h.shape[0]
    s = slope_deg(h, cell)
    X = x0 + (np.arange(n) + 0.5) * cell
    Y = y0 + (np.arange(n) + 0.5) * cell
    step = max(1, n // 256)
    best = None
    for tol_k in (tol, 1.6 * tol, 2.5 * tol):
        cand = []
        for j in range(0, n, step):
            for i in range(0, n, step):
                if s[j, i] > 22.0:
                    continue
                x, y = X[i], Y[j]
                if min(x - x0, y - y0, x0 + n * cell - x, y0 + n * cell - y) < 0.12 * n * cell:
                    continue
                cand.append((x, y, h[j, i]))
        cand = np.array(cand)
        d = np.hypot(cand[:, None, 0] - P[None, ::4, 0], cand[:, None, 1] - P[None, ::4, 1])
        k = np.argmin(d, axis=1)
        dmin = d[np.arange(len(cand)), k]
        zr = np.array([sample(h, cell, x0, y0, P[4 * kk, 0], P[4 * kk, 1]) for kk in k])
        above = cand[:, 2] - zr
        ok = (np.abs(dmin / rel['dist'] - 1) < tol_k) & (np.abs(above / rel['above'] - 1) < tol_k)
        frac = (4 * k) / max(len(P) - 1, 1)
        order = np.argsort(np.abs(frac - prefer) + 0.3 * np.abs(dmin / rel['dist'] - 1)
                           + 0.3 * np.abs(above / rel['above'] - 1))
        for o in order:
            if not ok[o]:
                continue
            x, y, z = cand[o]
            dd, ii, flow, side = river_at(P, x, y)
            if rel.get('look'):
                az0 = None
            else:
                az0 = (flow + (rel['rel_az'] if side == rel['side'] else -rel['rel_az'])) % 360.0
            # the heading the photo's relation gives, or within 35 degrees of it, whose view axis comes down as
            # near the river as the photo's does (else a bend put a wall in front of the camera); standing at the
            # brink in that direction when the photo did
            if rel.get('edge'):
                x, y = to_brink(h, cell, x0, y0, P, x, y)
                z = float(sample(h, cell, x0, y0, x, y))
            if az0 is None:
                az0 = river_heading(P, x, y, rel['look'], rel.get('toward_deg', 0.0))
            cam = (x, y, z + rel['eye'])
            for daz in (0.0, -10.0, 10.0, -20.0, 20.0, -35.0, 35.0):
                az = (az0 + daz) % 360.0
                if not ray_clear(h, cell, x0, y0, cam, az, rel['pitch'], 120.0, -50.0 if rel['pitch'] < -5
                                 else 0.5):
                    continue
                if 'hit_river_m' in rel:
                    hit = ray_hit(h, cell, x0, y0, cam, az, rel['pitch'])
                    if hit is None:
                        continue
                    hr = float(np.min(np.hypot(P[:, 0] - hit[0], P[:, 1] - hit[1])))
                    if hr > float(rel['hit_river_m']):
                        continue
                best = dict(x=float(x), y=float(y), z=float(z + rel['eye']), az=float(az), pitch=rel['pitch'],
                            lens=rel['lens'], dist=float(dd), above=float(z - sample(h, cell, x0, y0, P[ii, 0],
                                                                                        P[ii, 1])),
                            tol=tol_k, turn=daz)
                return best
    raise ValueError('no spot on the generated level stands in the photo\'s relation to the river')


def buttes(h, cell, x0, y0, min_rel=60.0, min_area_m2=4000.0):
    """Caprock remnants: connected cells more than min_rel above the local floor. [(area m^2, cx, cy, top, floor)]"""
    from collections import deque
    fl = F._floor_surface(h, cell)
    m = (h - fl) > min_rel
    n = h.shape[0]
    lab = np.zeros(h.shape, np.int32)
    out = []
    k = 0
    for j0, i0 in zip(*np.nonzero(m)):
        if lab[j0, i0]:
            continue
        k += 1
        q = deque([(j0, i0)])
        lab[j0, i0] = k
        cells = []
        while q:
            j, i = q.popleft()
            cells.append((j, i))
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jj, ii = j + dj, i + di
                if 0 <= jj < n and 0 <= ii < n and m[jj, ii] and not lab[jj, ii]:
                    lab[jj, ii] = k
                    q.append((jj, ii))
        c = np.array(cells)
        area = len(c) * cell * cell
        if area < min_area_m2:
            continue
        out.append((area, float(x0 + (c[:, 1].mean() + 0.5) * cell), float(y0 + (c[:, 0].mean() + 0.5) * cell),
                    float(h[c[:, 0], c[:, 1]].max()), float(fl[c[:, 0], c[:, 1]].mean())))
    return sorted(out, key=lambda t: -t[0])


def match_target(h, cell, x0, y0, rel, targets, tol=0.3):
    """A camera at the photo's distance from a target (a butte or wall point (x, y, relief)), on ground as high
    above the floor as the photo's, with a clear sight of it; the view offset from the bearing as in the photo."""
    n = h.shape[0]
    side = n * cell
    s = slope_deg(h, cell)
    for tol_k in (tol, 2 * tol, 3.5 * tol):
        for tx, ty, trel in targets:
            for d_f in (1.0, 0.85, 1.15, 0.7, 1.3):
                D = rel['dist'] * d_f
                for a in np.arange(0.0, 360.0, 7.5):
                    x = tx - D * math.sin(math.radians(a))
                    y = ty - D * math.cos(math.radians(a))
                    if min(x - x0, y - y0, x0 + side - x, y0 + side - y) < 0.06 * side:
                        continue
                    i = int((x - x0) / cell)
                    j = int((y - y0) / cell)
                    if s[min(max(j, 0), n - 1), min(max(i, 0), n - 1)] > 20.0:
                        continue
                    z = float(sample(h, cell, x0, y0, x, y))
                    fl = floor_level(h, cell, x0, y0, x, y)
                    if abs((z - fl) - rel['above_floor']) > max(25.0, tol_k * abs(rel['above_floor'])):
                        continue
                    cam = (x, y, z + rel['eye'])
                    # the sight line to the target's upper half clears the ground
                    tz = float(sample(h, cell, x0, y0, tx, ty))
                    t = np.linspace(0.05, 0.9, 80)
                    lx, ly = x + (tx - x) * t, y + (ty - y) * t
                    lz = cam[2] + (tz - 0.3 * trel - cam[2]) * t
                    if np.any(sample(h, cell, x0, y0, lx, ly) > lz):
                        continue
                    az = (a + rel['offset']) % 360.0
                    return dict(x=x, y=y, z=cam[2], az=float(az), pitch=rel['pitch'], lens=rel['lens'],
                                dist=float(D), target=(float(tx), float(ty)), above_floor=float(z - fl), tol=tol_k)
    raise ValueError('no spot on the generated level stands in the photo\'s relation to a target')
