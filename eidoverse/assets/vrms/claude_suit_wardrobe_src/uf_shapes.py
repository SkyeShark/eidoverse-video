"""Badge outlines shared by build_tuta.py (Blender: geometry) and paint_badges.py (PIL: face textures + ghost SDFs).
Pure Python, no Blender or PIL imports. Units: badge millimetres, +x right, +y up, seen from outside the suit."""
import math


def star(cx, cy, R, r, n=5, rot=90.0):
    """an n-point star, first point up"""
    pts = []
    for k in range(2 * n):
        a = math.radians(rot) + math.pi * k / n
        rr = R if k % 2 == 0 else r
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def signed_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def ccw(pts):
    return pts if signed_area(pts) > 0 else pts[::-1]


def round_corners(pts, r, seg=5):
    """replace each corner by an arc of radius r (clamped to a third of the shorter neighbouring edge)"""
    if r <= 0:
        return list(pts)
    pts = ccw(pts)
    n = len(pts)
    out = []
    for i in range(n):
        ax, ay = pts[i - 1]
        px, py = pts[i]
        bx, by = pts[(i + 1) % n]
        e1 = (ax - px, ay - py)
        e2 = (bx - px, by - py)
        l1, l2 = math.hypot(*e1), math.hypot(*e2)
        e1 = (e1[0] / l1, e1[1] / l1)
        e2 = (e2[0] / l2, e2[1] / l2)
        cosang = max(-0.9999, min(0.9999, e1[0] * e2[0] + e1[1] * e2[1]))
        half = math.acos(cosang) / 2                         # half the corner's angle
        if half < 1e-3:
            out.append((px, py))
            continue
        t = min(r / math.tan(half), l1 / 3, l2 / 3)          # tangent distance from the corner
        rr = t * math.tan(half)
        p1 = (px + e1[0] * t, py + e1[1] * t)
        p2 = (px + e2[0] * t, py + e2[1] * t)
        bis = (e1[0] + e2[0], e1[1] + e2[1])
        bl = math.hypot(*bis)
        if bl < 1e-9:
            out.append((px, py))
            continue
        d = rr / math.sin(half)
        c = (px + bis[0] / bl * d, py + bis[1] / bl * d)
        a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
        a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi   # the short arc faces the corner
        for s_ in range(seg + 1):
            a = a1 + da * s_ / seg
            out.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)))
    return out


def pieces_of(badge):
    """the badge's outline polygons (CCW, corners rounded)"""
    out = []
    for p in badge['pieces']:
        if isinstance(p, str) and p.startswith('star:'):
            cx, cy, R, r = (float(x) for x in p[5:].split(','))
            poly = star(cx, cy, R, r)
            out.append(round_corners(poly, min(badge.get('round', 0), 1.0), 3))
        else:
            out.append(round_corners([tuple(q) for q in p], badge.get('round', 0)))
    return out


def point_in_poly(x, y, pts):
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside
