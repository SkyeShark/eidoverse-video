"""eidoblend.sets.same_seed.lab.kit: the lab's build helpers: the houseplants' kit for what grows and what is moulded
(eidoblend.props.houseplants.kit: soft, limb_rings, Skin, thicken, loops, lumps, spline, resample ...), and mouldings,
punched sheet and placing on the hard-surface kit. Millimetres in every table; the scene is in metres.

    mitred / frame_loop           a moulding run along a path or round a rectangle with TRUE mitres (a sweep's own corner
                                  is 1/cos too thin: a skirting would be notched in every corner of the room)
    boxes / box_rings / rect_ring many boxes in one object; a box's two rings; a rectangle's ring
    plate                         a punched sheet: a grid with its holes left out, then given its thickness
    turn / move                   a built part's own points turned about an axis through a pivot, or moved (mm)
"""

import math

from mathutils import Matrix, Vector

from ....props.hardsurface import masses as hs
from ....props.houseplants.kit import (MM, V3, Skin, arc_lengths, hash01, lerp, limb_rings, loops, lumps, pt_frames,  # noqa: F401
                                       resample, round_noise, round_sect, sgn01, smooth, soft, spline, table, thicken, vnoise)


def mitred(name, pts, prof, up=(0, 0, 1), closed=False):
    """a profile [(u, v) mm] run along a path with a TRUE mitre at every corner. u: to the LEFT of travel as seen with
    `up` toward the eye; v: along up. closed: the path is a loop."""
    P = [Vector(p) for p in pts]
    up = Vector(up).normalized()
    k = len(P)
    rl = []
    for i in range(k):
        d0 = (P[i] - P[i - 1]).normalized() if (i > 0 or closed) else None
        d1 = (P[(i + 1) % k] - P[i]).normalized() if (i < k - 1 or closed) else None
        d0, d1 = d0 or d1, d1 or d0
        n0, n1 = up.cross(d0).normalized(), up.cross(d1).normalized()
        m = (n0 + n1).normalized()
        m = m / max(m.dot(n0), 0.2)
        rl.append([P[i] + m * u + up * v for u, v in prof])
    if closed:
        rl.append(rl[0])
    return hs.rings(name, rl, caps=not closed)


def loop_rings(C, U, W, N, hw, hh, prof):
    """the rings of a moulding round a rectangle (centre C, half-sizes hw along U and hh along W), mitred at its four
    corners. prof: [(out from the rectangle's edge, proud along N)]"""
    C, U, W, N = Vector(C), Vector(U).normalized(), Vector(W).normalized(), Vector(N).normalized()
    return [[C + U * (su * (hw + u)) + W * (sw * (hh + u)) + N * v for u, v in prof] for su, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]


def frame_loop(name, C, U, W, N, hw, hh, prof):
    return hs.rings(name, loop_rings(C, U, W, N, hw, hh, prof), caps=False)


def box_rings(lo, hi):
    x0, y0, z0 = [min(a, b) for a, b in zip(lo, hi)]
    x1, y1, z1 = [max(a, b) for a, b in zip(lo, hi)]
    return [[V3(x0, y0, z0), V3(x1, y0, z0), V3(x1, y1, z0), V3(x0, y1, z0)], [V3(x0, y0, z1), V3(x1, y0, z1), V3(x1, y1, z1), V3(x0, y1, z1)]]


def boxes(name, pairs):
    """many boxes (lo, hi) in ONE object"""
    return hs.skins(name, [box_rings(lo, hi) for lo, hi in pairs])


def rect_ring(cx, cy, hx, hy, z):
    return [V3(cx - hx, cy - hy, z), V3(cx + hx, cy - hy, z), V3(cx + hx, cy + hy, z), V3(cx - hx, cy + hy, z)]


def turn(o, pivot, axis, deg):
    """turn a part's own points about an axis through a pivot (mm): a sash tilted on its hinge, a chair turned to the
    room. Right-handed: a positive turn about +X carries a point above the pivot toward -Y"""
    p = Vector(pivot) * MM
    o.data.transform(Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, Vector(axis).normalized()) @ Matrix.Translation(-p))
    o.data.update()
    return o


def move(o, by):
    o.data.transform(Matrix.Translation(Vector(by) * MM))
    o.data.update()
    return o


def plate(name, us, vs, keep, w0, w1, at=(0, 0, 0), U=(1, 0, 0), V=(0, 1, 0), W=(0, 0, 1)):
    """a sheet with holes punched: the cells of a grid (edges us x vs, mm) that keep(i, j) leaves, between w0 and w1
    along W; a point is at + U u + V v + W w. One closed part (the sheet has its thickness at every hole)."""
    import bmesh
    at, U, V, W = Vector(at), Vector(U), Vector(V), Vector(W)
    bm = bmesh.new()
    vv = {}

    def vert(i, j, lv):
        key = (i, j, lv)
        if key not in vv:
            p = at + U * us[i] + V * vs[j] + W * (w1 if lv else w0)
            vv[key] = bm.verts.new((p.x * MM, p.y * MM, p.z * MM))
        return vv[key]
    ni, nj = len(us) - 1, len(vs) - 1

    def kept(i, j):
        return 0 <= i < ni and 0 <= j < nj and keep(i, j)
    for i in range(ni):
        for j in range(nj):
            if not kept(i, j):
                continue
            bm.faces.new((vert(i, j, 1), vert(i + 1, j, 1), vert(i + 1, j + 1, 1), vert(i, j + 1, 1)))
            bm.faces.new((vert(i, j, 0), vert(i, j + 1, 0), vert(i + 1, j + 1, 0), vert(i + 1, j, 0)))
            for (di, dj), (a, b) in (((0, -1), ((i, j), (i + 1, j))), ((1, 0), ((i + 1, j), (i + 1, j + 1))),
                                     ((0, 1), ((i + 1, j + 1), (i, j + 1))), ((-1, 0), ((i, j + 1), (i, j)))):
                if not kept(i + di, j + dj):
                    bm.faces.new((vert(a[0], a[1], 0), vert(b[0], b[1], 0), vert(b[0], b[1], 1), vert(a[0], a[1], 1)))
    return hs.obj(name, bm)
