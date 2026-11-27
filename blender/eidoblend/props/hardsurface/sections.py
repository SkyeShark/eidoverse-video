"""eidoblend.props.hardsurface.sections: a lofted body from control sections (plain Python, no bpy).

An airframe, a cowling or a fairing changes the KIND of its section along its length (a blunt nose, a faceted canopy of
flat panes between posts, a slab-sided cabin, an egg-shaped boom), and its creases run along it. So:

    a HALF-SECTION at station x is a control polygon K0 .. Kn in the (y, z) plane, from the keel (y = 0) up the right
    side to the crown (y = 0); each inner corner has a REACH (mm along its two edges) over which it is rounded by a
    conic (a circular arc when the two reaches are equal): reach 10 is a crease, reach 300 a soft shoulder; every edge
    and every corner carries a FIXED number of points, so a corner is the same loop of edges from end to end.
    A BODY is a list of such keys along x; every number is carried between keys by a monotone cubic (no overshoot,
    straight where three keys are in line), restarted at a key named in `breaks` (a crease ACROSS the body there).

    from eidoblend.props.hardsurface.sections import Body, stations
    hull = Body([(x, [(y, z), ...], [reach, ...]), ...], n_edge=[8, 5, ...], n_corner=[14, 8, ...],
                breaks={'K4': [x_windshield_foot]})
    hull.ring(x)       # [(x, y, z)] round the whole section: up the right side (+y), down the left
    hull.half(x)       # the right half's points [(y, z)]
    hull.ctrl(x)       # the control polygon and the reaches at x
    stations(x0, x1, step, must=(...))   # stations no further apart than step, through every x in must

skins.loft_body(name, body, xs) skins a Body over the stations xs (hardsurface.skins).
"""

from __future__ import annotations

import math


def pchip(xs, ys):
    """A monotone cubic through (xs, ys) (Fritsch-Carlson) -> f(x); flat beyond its ends."""
    n = len(xs)
    if n == 1:
        return lambda x: ys[0]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    if n == 2:
        m[0] = m[1] = d[0]
    else:
        for i in range(1, n - 1):
            if d[i - 1] * d[i] <= 0.0:
                m[i] = 0.0
            else:
                w1, w2 = 2.0 * h[i] + h[i - 1], h[i] + 2.0 * h[i - 1]
                m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

        def end(h0, h1, d0, d1):
            v = ((2.0 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
            if v * d0 <= 0.0:
                return 0.0
            if d0 * d1 <= 0.0 and abs(v) > 3.0 * abs(d0):
                return 3.0 * d0
            return v
        m[0] = end(h[0], h[1], d[0], d[1])
        m[-1] = end(h[-1], h[-2], d[-1], d[-2])

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        t = (x - xs[lo]) / h[lo]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[lo] + (t3 - 2 * t2 + t) * h[lo] * m[lo] + (-2 * t3 + 3 * t2) * ys[lo + 1]
                + (t3 - t2) * h[lo] * m[lo + 1])
    return f


def curve(xs, ys, breaks=()):
    """pchip, restarted at each x in `breaks` (a corner there)."""
    cuts = [i for i, x in enumerate(xs) if x in breaks and 0 < i < len(xs) - 1]
    if not cuts:
        return pchip(xs, ys)
    spans, a = [], 0
    for c in cuts + [len(xs) - 1]:
        spans.append((xs[a], xs[c], pchip(xs[a:c + 1], ys[a:c + 1])))
        a = c

    def f(x):
        for x0, x1, g in spans:
            if x <= x1:
                return g(x)
        return spans[-1][2](x)
    return f


def conic(a, k, b, n):
    """n points from a (included) toward b (not included) along the conic that leaves a toward k and arrives at b from
    k: a circular arc when |a - k| = |b - k|."""
    ax, ay = a[0] - k[0], a[1] - k[1]
    bx, by = b[0] - k[0], b[1] - k[1]
    la, lb = math.hypot(ax, ay), math.hypot(bx, by)
    if la < 1e-9 or lb < 1e-9:
        return [a] * n
    c = max(-1.0, min(1.0, (ax * bx + ay * by) / (la * lb)))
    w = math.sin(math.acos(c) / 2.0)                          # the weight of a circular arc for this corner
    out = []
    for i in range(n):
        t = i / n
        u0, u1, u2 = (1 - t) * (1 - t), 2 * w * t * (1 - t), t * t
        s = u0 + u1 + u2
        out.append(((u0 * a[0] + u1 * k[0] + u2 * b[0]) / s, (u0 * a[1] + u1 * k[1] + u2 * b[1]) / s))
    return out


def half_ring(K, R, n_edge, n_corner):
    """The half-section's points from K[0] to K[-1] (both included): K control points (y, z); R reaches for
    K[1] .. K[-2]."""
    n = len(K)
    L = [math.hypot(K[i + 1][0] - K[i][0], K[i + 1][1] - K[i][1]) for i in range(n - 1)]
    r = [0.0] + [max(0.0, v) for v in R] + [0.0]
    ra, rb = [0.0] * n, [0.0] * n                             # each corner's reach back along its edge, and on along the next
    for i in range(1, n - 1):
        ra[i], rb[i] = r[i], r[i]
    for e in range(n - 1):                                    # two corners share an edge: neither takes more than its share
        want = rb[e] + ra[e + 1]
        if want > L[e] and want > 0.0:
            s = L[e] / want
            rb[e] *= s
            ra[e + 1] *= s

    def along(i, j, dist):
        if L[min(i, j)] < 1e-9:
            return K[i]
        t = dist / L[min(i, j)]
        return (K[i][0] + (K[j][0] - K[i][0]) * t, K[i][1] + (K[j][1] - K[i][1]) * t)
    out = []
    start = K[0]
    for i in range(1, n):
        a = along(i, i - 1, ra[i]) if i < n - 1 else K[i]
        m = n_edge[i - 1]
        out += [(start[0] + (a[0] - start[0]) * q / m, start[1] + (a[1] - start[1]) * q / m) for q in range(m)]
        if i < n - 1:
            b = along(i, i + 1, rb[i])
            out += conic(a, K[i], b, n_corner[i - 1])
            start = b
    out.append(K[-1])
    return out


class Body:
    def __init__(self, keys, n_edge, n_corner, breaks=None):
        """keys: [(x, [(y, z), ...], [reach, ...])] in any order; breaks: {name: [x, ...]} with names 'K3' (both of
        that point's numbers), 'K3y', 'K3z', 'R3', or 'all'."""
        keys = sorted(keys, key=lambda k: k[0])
        self.xs = [k[0] for k in keys]
        self.n = len(keys[0][1])
        self.n_edge, self.n_corner = n_edge, n_corner
        br = breaks or {}

        def cuts(*names):
            s = set(br.get('all', ()))
            for nm in names:
                s |= set(br.get(nm, ()))
            return s
        self.fy = [curve(self.xs, [k[1][i][0] for k in keys], cuts(f'K{i}', f'K{i}y')) for i in range(self.n)]
        self.fz = [curve(self.xs, [k[1][i][1] for k in keys], cuts(f'K{i}', f'K{i}z')) for i in range(self.n)]
        self.fr = [curve(self.xs, [k[2][i] for k in keys], cuts(f'R{i + 1}')) for i in range(self.n - 2)]

    def ctrl(self, x):
        return [(f(x), g(x)) for f, g in zip(self.fy, self.fz)], [f(x) for f in self.fr]

    def half(self, x):
        K, R = self.ctrl(x)
        K[0], K[-1] = (0.0, K[0][1]), (0.0, K[-1][1])
        return half_ring(K, R, self.n_edge, self.n_corner)

    def ring(self, x, scale=1.0, about=None, scale_y=None):
        """The whole section at x: up the right side (+y), down the left. scale < 1 draws it in toward `about` (a
        blunt end's closing rings); scale_y: its width's own scale (a lip that closes in height but stays broad)."""
        h = self.half(x)
        if scale != 1.0 or scale_y is not None:
            cz = about if about is not None else (h[0][1] + h[-1][1]) / 2.0
            sy = scale if scale_y is None else scale_y
            h = [(y * sy, cz + (z - cz) * scale) for y, z in h]
        return [(x, y, z) for y, z in h] + [(x, -y, z) for y, z in h[-2:0:-1]]

    def side_at(self, x, z):
        """The half-width of the section at height z (the outermost crossing), or None."""
        h = self.half(x)
        best = None
        for (y0, z0), (y1, z1) in zip(h, h[1:]):
            if (z0 - z) * (z1 - z) <= 0.0 and abs(z1 - z0) > 1e-9:
                y = y0 + (y1 - y0) * (z - z0) / (z1 - z0)
                best = y if best is None else max(best, y)
        return best


def stations(x0, x1, step, must=()):
    """x0 .. x1 in steps no longer than `step`, through every x in `must`."""
    pts = sorted({x0, x1} | {m for m in must if x0 < m < x1})
    out = []
    for a, b in zip(pts, pts[1:]):
        k = max(1, int(math.ceil((b - a) / step)))
        out += [a + (b - a) * i / k for i in range(k)]
    out.append(x1)
    return out
