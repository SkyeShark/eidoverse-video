"""eidoblend.fabrication.polygon_union: the union of planar polygons with holes, for the slicer.

The WebGPU slicer unions each slice's solids with the vendored polygon-clipping library (MIT, a Martinez sweep). This is
the Blender edition's own exact union with the same contract, written for slices (a few polygons, hundreds of edges):

    union(*polygons) -> [[outer, hole, ...], ...]
        each polygon is a list of closed rings [(x, y), ..., first point again]: an outer boundary and its holes, in
        either orientation. The result is the region inside any polygon (inside a polygon = inside its outer ring and
        outside its holes), as closed rings with collinear points removed: outer rings counter-clockwise (positive
        area), holes clockwise, each ring starting at its lowest-x (then lowest-y) point.

Method: every edge is split where it crosses or touches an edge of another polygon (collinear overlaps included); each
piece is kept when the union's inside lies on exactly one side of it (probed a hair either side of its midpoint),
turned so the inside is on its left, and the kept pieces are linked into rings (at a vertex where two rings touch, the
walk takes the first piece clockwise from the way it came in, so each ring hugs its own inside).
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np


def _area(r):
    a = 0.0
    for i in range(len(r) - 1):
        a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
    return a / 2


def _open(r):
    r = [tuple(map(float, p)) for p in r]
    if len(r) > 1 and r[0] == r[-1]:
        r = r[:-1]
    return r


def collinear(a, b, c):
    """Exactly collinear (orient2d == 0), as polygon-clipping's robust predicate decides: the double result settles
    it outside its error bound, exact rationals inside."""
    l = (b[0] - a[0]) * (c[1] - a[1])
    r = (b[1] - a[1]) * (c[0] - a[0])
    d = l - r
    if abs(d) > 4e-16 * (abs(l) + abs(r)):
        return False
    fa = (Fraction(a[0]), Fraction(a[1]))
    return (Fraction(b[0]) - fa[0]) * (Fraction(c[1]) - fa[1]) == (Fraction(b[1]) - fa[1]) * (Fraction(c[0]) - fa[0])


def _clean(r, eps):
    """Drop repeated points, then the points exactly in line with their neighbours, walking the ring once from its
    first point as polygon-clipping's RingOut.getGeom does (the first point last)."""
    pts = []
    for p in r:
        if not pts or abs(p[0] - pts[-1][0]) > eps or abs(p[1] - pts[-1][1]) > eps:
            pts.append(p)
    while len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) <= eps and abs(pts[0][1] - pts[-1][1]) <= eps:
        pts.pop()
    if len(pts) < 3:
        return pts
    ev = pts + [pts[0]]
    prev = ev[0]
    out = [prev]
    for i in range(1, len(ev) - 1):
        pt, nxt = ev[i], ev[i + 1]
        if collinear(pt, prev, nxt):
            continue
        out.append(pt)
        prev = pt
    if len(out) < 3:
        return out
    if collinear(out[0], prev, out[1]):
        out.pop(0)
    return out


def _close(r):
    i0 = min(range(len(r)), key=lambda i: (r[i][0], r[i][1]))
    r = r[i0:] + r[:i0]
    return r + [r[0]]


def _orient(r, ccw):
    a = _area(r + [r[0]])
    if (a > 0) != ccw:
        r = r[::-1]
    return r


def _normalize(poly, eps):
    out = []
    for k, ring in enumerate(poly):
        r = _clean(_open(ring), eps)
        if len(r) < 3 or abs(_area(r + [r[0]])) <= eps * eps:
            if k == 0:
                return None
            continue
        out.append(_close(_orient(r, k == 0)))
    return out


def _inside_rings(px, py, rings):
    """Even-odd membership of points (px, py arrays) in the region bounded by rings (closed lists)."""
    inside = np.zeros(px.shape, dtype=bool)
    for r in rings:
        a = np.asarray(r[:-1], dtype=np.float64)
        b = np.asarray(r[1:], dtype=np.float64)
        ax, ay, bx, by = a[:, 0][:, None], a[:, 1][:, None], b[:, 0][:, None], b[:, 1][:, None]
        cond = (ay > py[None, :]) != (by > py[None, :])
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = (bx - ax) * (py[None, :] - ay) / (by - ay) + ax
        hit = cond & (px[None, :] < xi)
        inside ^= (hit.sum(axis=0) % 2).astype(bool)
    return inside


def _bbox(poly):
    a = np.asarray(poly[0], dtype=np.float64)
    return a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()


def union(*polygons):
    polys = [p for p in polygons if p and len(p[0]) >= 3]
    if not polys:
        return []
    allp = np.concatenate([np.asarray(r, dtype=np.float64) for p in polys for r in p])
    extent = float(np.hypot(*(allp.max(axis=0) - allp.min(axis=0)))) or 1.0
    eps = max(1e-15, extent * 1e-12)
    boxes = [_bbox(p) for p in polys]
    # clusters of polygons whose bounding boxes overlap (only these can intersect or contain one another)
    parent = list(range(len(polys)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            a, b = boxes[i], boxes[j]
            if a[0] <= b[2] + eps and b[0] <= a[2] + eps and a[1] <= b[3] + eps and b[1] <= a[3] + eps:
                parent[find(i)] = find(j)
    clusters = {}
    for i in range(len(polys)):
        clusters.setdefault(find(i), []).append(polys[i])
    out = []
    for group in clusters.values():
        if len(group) == 1:
            p = _normalize(group[0], eps)
            if p:
                out.append(p)
        else:
            out.extend(_union_cluster(group, extent, eps))
    out.sort(key=lambda p: (p[0][0][0], p[0][0][1]))
    return out


def _union_cluster(polys, extent, eps):
    # edges per polygon
    edges = []          # (ax, ay, bx, by, polygon)
    for pi, poly in enumerate(polys):
        for ring in poly:
            r = _open(ring)
            for i in range(len(r)):
                a, b = r[i], r[(i + 1) % len(r)]
                if a != b:
                    edges.append((a[0], a[1], b[0], b[1], pi))
    E = np.asarray(edges, dtype=np.float64)
    n = len(E)
    splits = [[] for _ in range(n)]           # (param, (x, y)) per edge
    tol = 1e-12
    owner = E[:, 4].astype(int)
    for pi in range(len(polys)):
        I = np.nonzero(owner == pi)[0]
        J = np.nonzero(owner > pi)[0]
        if not len(I) or not len(J):
            continue
        A, B = E[I], E[J]
        a1 = A[:, None, 0:2]
        d1 = A[:, None, 2:4] - a1
        a2 = B[None, :, 0:2]
        d2 = B[None, :, 2:4] - a2
        # bounding-box rejection
        lo1, hi1 = np.minimum(A[:, 0:2], A[:, 2:4]), np.maximum(A[:, 0:2], A[:, 2:4])
        lo2, hi2 = np.minimum(B[:, 0:2], B[:, 2:4]), np.maximum(B[:, 0:2], B[:, 2:4])
        near = ((lo1[:, None, 0] <= hi2[None, :, 0] + eps) & (lo2[None, :, 0] <= hi1[:, None, 0] + eps)
                & (lo1[:, None, 1] <= hi2[None, :, 1] + eps) & (lo2[None, :, 1] <= hi1[:, None, 1] + eps))
        ii, jj = np.nonzero(near)
        for i_, j_ in zip(ii.tolist(), jj.tolist()):
            e1, e2 = I[i_], J[j_]
            ax, ay, bx, by = E[e1, :4]
            cx, cy, dx, dy = E[e2, :4]
            ux, uy, vx, vy = bx - ax, by - ay, dx - cx, dy - cy
            den = ux * vy - uy * vx
            wx, wy = cx - ax, cy - ay
            lu2, lv2 = ux * ux + uy * uy, vx * vx + vy * vy
            if abs(den) > 1e-14 * math.sqrt(lu2 * lv2):
                t = (wx * vy - wy * vx) / den
                u = (wx * uy - wy * ux) / den
                if t < -tol or t > 1 + tol or u < -tol or u > 1 + tol:
                    continue
                if u <= tol:
                    p = (cx, cy)
                elif u >= 1 - tol:
                    p = (dx, dy)
                elif t <= tol:
                    p = (ax, ay)
                elif t >= 1 - tol:
                    p = (bx, by)
                else:
                    p = (ax + t * ux, ay + t * uy)
                if tol < t < 1 - tol:
                    splits[e1].append((t, p))
                if tol < u < 1 - tol:
                    splits[e2].append((u, p))
            else:
                # parallel: collinear overlap splits each edge at the other's endpoints inside it
                if abs(wx * uy - wy * ux) > 1e-12 * lu2 + eps * math.sqrt(lu2):
                    continue
                for (px, py) in ((cx, cy), (dx, dy)):
                    t = ((px - ax) * ux + (py - ay) * uy) / lu2
                    if tol < t < 1 - tol:
                        splits[e1].append((t, (px, py)))
                for (px, py) in ((ax, ay), (bx, by)):
                    u = ((px - cx) * vx + (py - cy) * vy) / lv2
                    if tol < u < 1 - tol:
                        splits[e2].append((u, (px, py)))

    def key(p):
        return (math.floor(p[0] / eps + .5), math.floor(p[1] / eps + .5))

    pieces = {}
    for e in range(n):
        ax, ay, bx, by = E[e, :4]
        pts = [(0.0, (ax, ay))] + sorted(splits[e]) + [(1.0, (bx, by))]
        for k in range(len(pts) - 1):
            p, q = pts[k][1], pts[k + 1][1]
            kp, kq = key(p), key(q)
            if kp == kq:
                continue
            pieces.setdefault((min(kp, kq), max(kp, kq)), (p, q))
    if not pieces:
        return []
    P = np.asarray([pq[0] for pq in pieces.values()], dtype=np.float64)
    Q = np.asarray([pq[1] for pq in pieces.values()], dtype=np.float64)
    d = Q - P
    ln = np.hypot(d[:, 0], d[:, 1])
    nrm = np.stack([-d[:, 1], d[:, 0]], axis=1) / ln[:, None]
    m = (P + Q) / 2
    delta = min(extent * 1e-9, float(ln.min()) * 1e-3)
    left, right = m + nrm * delta, m - nrm * delta
    inl = np.zeros(len(m), dtype=bool)
    inr = np.zeros(len(m), dtype=bool)
    for poly in polys:
        inl |= _inside_rings(left[:, 0], left[:, 1], poly)
        inr |= _inside_rings(right[:, 0], right[:, 1], poly)
    keep = inl != inr
    kept = []
    for i in np.nonzero(keep)[0].tolist():
        a, b = tuple(P[i]), tuple(Q[i])
        kept.append((a, b) if inl[i] else (b, a))
    # link the kept pieces into rings
    out_of = {}
    for i, (a, b) in enumerate(kept):
        out_of.setdefault(key(a), []).append(i)
    used = [False] * len(kept)
    rings = []
    for s in range(len(kept)):
        if used[s]:
            continue
        used[s] = True
        ring = [kept[s][0], kept[s][1]]
        start = key(kept[s][0])
        guard = 0
        while key(ring[-1]) != start and guard < len(kept) + 2:
            guard += 1
            cands = [j for j in out_of.get(key(ring[-1]), []) if not used[j]]
            if not cands:
                break
            if len(cands) > 1:
                prev, cur = ring[-2], ring[-1]
                back = math.atan2(prev[1] - cur[1], prev[0] - cur[0])

                def cw_from_back(j):
                    nx, ny = kept[j][1][0] - cur[0], kept[j][1][1] - cur[1]
                    ang = back - math.atan2(ny, nx)
                    ang %= 2 * math.pi
                    return ang if ang > 1e-12 else 2 * math.pi
                cands.sort(key=cw_from_back)
            j = cands[0]
            used[j] = True
            ring.append(kept[j][1])
        if key(ring[-1]) == start:
            r = _clean(ring[:-1], eps)
            if len(r) >= 3 and abs(_area(r + [r[0]])) > eps * eps:
                rings.append(r)
    outers = [r for r in rings if _area(r + [r[0]]) > 0]
    holes = [r for r in rings if _area(r + [r[0]]) < 0]
    result = [[_close(o)] for o in outers]
    areas = [abs(_area(o + [o[0]])) for o in outers]
    for h in holes:
        a, b = h[0], h[1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln_ = math.hypot(dx, dy)
        px = (a[0] + b[0]) / 2 - dy / ln_ * delta
        py = (a[1] + b[1]) / 2 + dx / ln_ * delta
        best = None
        for k, o in enumerate(outers):
            if _inside_rings(np.array([px]), np.array([py]), [o + [o[0]]])[0]:
                if best is None or areas[k] < areas[best]:
                    best = k
        if best is not None:
            result[best].append(_close(h))
    return result
