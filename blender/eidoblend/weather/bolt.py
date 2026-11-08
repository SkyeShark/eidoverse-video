"""The visible lightning channel: rebuildBolt from eidoverse/weather_system.js, as plain Python (three.js space).

One jagged camera-facing ribbon per event, from its seed: a 12-anchor trunk that leaves the cloud deck slightly inside
it (cloudStart x 1.04) and lands exactly on the strike point, refined by three midpoint-displacement passes (89
points: organic kinks from ~60 m wander down to ~3 m jitter), plus 2-4 forks with recursive sub-forks. Return strokes
reuse the same channel. Each ribbon vertex pair faces the camera position the event began with; u runs across the
ribbon (0..1), v along it from the cloud (0) to the end (1).
"""
import math

from .lightning import js_hash


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm3(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0     # three's normalize: divide by length || 1
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def bolt_points(interval, gx, gz, bottom_y=2.0, cloud_start=500.0):
    """The trunk (89 points) and the fork polylines with their start widths, three space.

    Returns [(points, w0, w1), ...]: the trunk first (3.6 m to 1.3 m), then each fork (w0 to w0 x 0.2)."""
    def rng(i):
        return js_hash(interval * 131.7 + i * 17.3)

    top_y = cloud_start * 1.04
    trunk = []
    n0 = 12
    x = gx + (rng(2) - 0.5) * 70
    z = gz + (rng(4) - 0.5) * 70
    for i in range(n0):
        t = i / (n0 - 1)
        y = top_y * (1 - t) + bottom_y * t
        if i > 0:
            amp = 34 * (1 - t * 0.35)
            x += (rng(10 + i) - 0.5) * amp + (gx - x) * 0.22
            z += (rng(30 + i) - 0.5) * amp + (gz - z) * 0.22
        if i == n0 - 1:
            x, z = gx, gz
        trunk.append((x, y, z))
    seed = 500
    for _level in range(3):
        refined = [trunk[0]]
        for i in range(1, len(trunk)):
            a, b = trunk[i - 1], trunk[i]
            span = math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)
            kink = span * 0.16
            refined.append(((a[0] + b[0]) / 2 + (rng(seed + i * 3) - 0.5) * 2 * kink,
                            (a[1] + b[1]) / 2 + (rng(seed + i * 3 + 1) - 0.5) * 0.6 * kink,
                            (a[2] + b[2]) / 2 + (rng(seed + i * 3 + 2) - 0.5) * 2 * kink))
            refined.append(b)
        trunk = refined
        seed += 137
    ribbons = [(trunk, 3.6, 1.3)]

    def branch_from(parent, s, w0, depth):
        k = 3 + int(math.floor(rng(s) * (len(parent) - 6)))
        bp = []
        bx, bz = parent[k][0], parent[k][2]
        n = 7 - depth * 2
        for i in range(n):
            t = i / (n - 1)
            bp.append((bx, parent[k][1] * (1 - t * (0.45 + rng(s + 1) * 0.25)), bz))
            bx += (rng(s + 10 + i) - 0.25) * 30
            bz += (rng(s + 40 + i) - 0.5) * 30
        ribbons.append((bp, w0, w0 * 0.2))
        if depth < 2 and rng(s + 5) > 0.4:
            branch_from(bp, s * 3 + 7, w0 * 0.5, depth + 1)

    n_branch = 2 + int(math.floor(rng(50) * 3))
    for b in range(n_branch):
        branch_from(trunk, 60 + b * 23, 1.5, 1)
    return ribbons


def bolt_ribbon(interval, cam_pos, gx, gz, bottom_y=2.0, cloud_start=500.0):
    """rebuildBolt's ribbon mesh: (positions, uvs, triangles), three space; each vertex pair faces cam_pos (seen
    horizontally, as the JS does: toCam has no height)."""
    pos, uvs, tris = [], [], []
    to_cam = _norm3((cam_pos[0] - gx, 0.0, cam_pos[2] - gz))
    for pts, w0, w1 in bolt_points(interval, gx, gz, bottom_y, cloud_start):
        b0 = len(pos)                       # the vertex count before this ribbon (the JS pos.length / 3)
        n = len(pts)
        for i in range(n):
            t = i / (n - 1)
            seg = _norm3(_sub(pts[i + 1], pts[i]) if i < n - 1 else _sub(pts[i], pts[i - 1]))
            right = _norm3(_cross(seg, to_cam))
            w = (w0 + (w1 - w0) * t) / 2
            p = pts[i]
            pos.append((p[0] - right[0] * w, p[1] - right[1] * w, p[2] - right[2] * w))
            pos.append((p[0] + right[0] * w, p[1] + right[1] * w, p[2] + right[2] * w))
            uvs.append((0.0, t))
            uvs.append((1.0, t))
            if i > 0:
                a = b0 + (i - 1) * 2
                tris.append((a, a + 1, a + 2))
                tris.append((a + 1, a + 3, a + 2))
    return pos, uvs, tris
