"""Loft: skin a surface through cross sections (the port of eidoverse/loft.js).

    from eidoblend.terrain import loft
    horn = loft.sweep(path=[(0, 0, 0), (0.2, -0.1, 0.8), (0.9, 0.0, 1.4)],
                      profile=loft.circle(0.25, 32), profile_end=loft.star(0.12, 0.05, 16),
                      sections=48, scale=lambda t: 1 - 0.6 * t, twist=math.pi)

The general case of a lathe or a tube: the section can be any ring and can change shape, size and
orientation along the path. Same maths as the engine, so a sweep through the same (mapped) points
makes the same surface: three's centripetal Catmull-Rom, its 200-division arc-length table and its
Frenet frames (computed in three's axes: the first normal is picked by the tangent's smallest
component, which is axis dependent), profile x on the frame normal, y on the binormal.

What is different in Blender: a closed ring needs no duplicated seam column (UVs are per corner,
normals smooth across the seam by themselves); walls are quads (the engine's triangles split them
on the same b-d diagonal: pass triangles=True for exactly those); each cap is ONE n-gon, flat
shaded, so the wall's smooth normals stop at it like the engine's unshared cap vertices.
Rules of the craft, as the engine's: every section has the same number of points; rings wind CCW
seen from the loft's end looking back (the profiles here do); uv.x runs along the loft, uv.y around.
"""
import math

import bpy
import numpy as np

from ..placement._curves import CatmullRomCurve3, frenet_frames
from ._nodes import new_material, principled


# ── profiles: (x, y) rings, CCW ───────────────────────────────────────────────────────────────
def circle(r=1.0, n=24):
    return [(math.cos(i / n * 2 * math.pi) * r, math.sin(i / n * 2 * math.pi) * r) for i in range(n)]


def ellipse(rx=1.0, ry=0.6, n=24):
    return [(math.cos(i / n * 2 * math.pi) * rx, math.sin(i / n * 2 * math.pi) * ry) for i in range(n)]


def polygon(sides=6, r=1.0):
    return circle(r, sides)


def star(r_outer=1.0, r_inner=0.45, points=5):
    out = []
    for i in range(points * 2):
        a = i / (points * 2) * 2 * math.pi
        r = r_outer if i % 2 == 0 else r_inner
        out.append((math.cos(a) * r, math.sin(a) * r))
    return out


def _resample(loop, n):
    m = len(loop)
    seg = [math.dist(loop[i], loop[(i + 1) % m]) for i in range(m)]
    total = sum(seg)
    out, s, acc = [], 0, 0.0
    for i in range(n):
        target = i / n * total
        while acc + seg[s] < target:
            acc += seg[s]
            s = (s + 1) % m
        f = (target - acc) / seg[s] if seg[s] > 0 else 0
        a, b = loop[s], loop[(s + 1) % m]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out


def rect(w=1.0, h=1.0, n=24):
    """A rectangle outline resampled to n evenly spaced points."""
    hw, hh = w / 2, h / 2
    return _resample([(hw, -hh), (hw, hh), (-hw, hh), (-hw, -hh)], n)


def _signed_area(ring):
    return 0.5 * sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
                     for i in range(len(ring)))


def from_outline(points, n=48):
    """Any closed 2D outline (a list of (x, y), e.g. a curve's points) resampled to n points, CCW
    (the engine's fromShape takes a THREE.Shape; here the outline itself)."""
    pts = [tuple(p[:2]) for p in points]
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts.pop()
    ring = _resample(pts, n)
    if _signed_area(ring) < 0:
        ring.reverse()
    return ring


# ── the geometry ──────────────────────────────────────────────────────────────────────────────
def _newell(section):
    n = np.zeros(3)
    m = len(section)
    for i in range(m):
        p, q = section[i], section[(i + 1) % m]
        n += ((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]), (p[0] - q[0]) * (p[1] + q[1]))
    ln = np.linalg.norm(n)
    return n / ln if ln > 0 else n


def loft_mesh(sections, closed=True, cap_start=False, cap_end=False, name='loft', triangles=False):
    """A Blender mesh skinned through `sections` (rings of (x, y, z) in Blender axes, all the same
    length). UV: u along the loft (0 -> 1), v around (0 -> 1 with the seam closing on 1)."""
    rows = len(sections)
    if rows < 2:
        raise ValueError('loft_mesh: at least two sections are required')
    cols = len(sections[0])
    if any(len(s) != cols for s in sections):
        raise ValueError('loft_mesh: all sections must have the same number of points')
    co = np.asarray(sections, dtype=np.float64).reshape(-1, 3)
    span = cols if closed else cols - 1
    faces, fuv = [], []
    for i in range(rows - 1):
        for j in range(span):
            a, b = i * cols + j, i * cols + (j + 1) % cols
            c, d = (i + 1) * cols + (j + 1) % cols, (i + 1) * cols + j
            ua, ub = i / (rows - 1), (i + 1) / (rows - 1)
            va, vb = j / span, (j + 1) / span
            if triangles:
                faces += [(a, b, d), (b, c, d)]
                fuv += [((ua, va), (ua, vb), (ub, va)), ((ua, vb), (ub, vb), (ub, va))]
            else:
                faces.append((a, b, c, d))
                fuv.append(((ua, va), (ua, vb), (ub, vb), (ub, va)))
    caps = []
    for k, on in ((0, cap_start), (rows - 1, cap_end)):
        if not on or not closed:
            continue
        sec = np.asarray(sections[k], dtype=np.float64)
        cen = sec.mean(axis=0)
        nrm = _newell(sec)
        nb = np.asarray(sections[1 if k == 0 else rows - 2], dtype=np.float64).mean(axis=0) - cen
        idx = [k * cols + j for j in range(cols)]
        if np.dot(nrm, nb) > 0:                      # the ring's own winding faces into the loft
            idx.reverse()
            nrm = -nrm
        tng = np.array((1.0, 0.0, 0.0)) if abs(nrm[0]) <= 0.9 else np.array((0.0, 1.0, 0.0))
        bit = np.cross(nrm, tng)
        bit /= np.linalg.norm(bit)
        tng = np.cross(bit, nrm)
        c2 = [((co[v] - cen) @ tng, (co[v] - cen) @ bit) for v in idx]
        mn = np.min(c2, axis=0)
        sz = np.maximum(np.max(c2, axis=0) - mn, 1e-12)
        caps.append(len(faces))
        faces.append(tuple(idx))
        fuv.append(tuple(tuple((np.asarray(p) - mn) / sz) for p in c2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(co.tolist(), [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    flat = [uv for f in fuv for uv in f]
    uvl.uv.foreach_set('vector', np.asarray(flat, dtype=np.float32).ravel())
    smooth = np.ones(len(faces), dtype=bool)
    for ci in caps:
        smooth[ci] = False
    me.polygons.foreach_set('use_smooth', smooth)
    me.validate()
    return me


def sweep(path, profile=None, profile_end=None, sections=32, scale=1.0, twist=0.0, closed=True,
          cap_start=None, cap_end=None, profile_fn=None, material=None, name='loft', triangles=False,
          collection=None):
    """Profile(s) along a path -> a linked object (the engine's Loft.sweep).

    path: a list of (x, y, z) Blender points (a centripetal Catmull-Rom through them, as three's
      default) or a CatmullRomCurve3 built in THREE's axes.
    profile / profile_end: rings of (x, y) with the same count; the section morphs linearly in t.
    scale, twist: a number or fn(t) (twist as a number is the total turn, applied as twist * t).
    profile_fn(t) -> ring replaces the profile (advanced). Caps default to `closed`.
    """
    if isinstance(path, CatmullRomCurve3):
        curve = path
    else:
        pts = [tuple(p) for p in path]
        if len(pts) < 2:
            raise ValueError('loft.sweep: path needs at least two points')
        curve = CatmullRomCurve3([(p[0], p[2], -p[1]) for p in pts])      # into three's axes
    profile = profile or circle(0.5, 24)
    if profile_end is not None and len(profile_end) != len(profile):
        raise ValueError('loft.sweep: profile (%d) and profile_end (%d) must have the same point count'
                         % (len(profile), len(profile_end)))
    rows = max(2, int(sections))
    scale_at = scale if callable(scale) else (lambda t, s=scale: s)
    twist_at = twist if callable(twist) else (lambda t, w=twist: w * t)
    _, N, B = frenet_frames(curve, rows - 1, False)
    secs = []
    for i in range(rows):
        t = i / (rows - 1)
        o = curve.get_point_at(t)
        n, b = N[i], B[i]
        s = scale_at(t)
        tw = twist_at(t)
        ct, st = math.cos(tw), math.sin(tw)
        ring = profile_fn(t) if profile_fn else profile
        sec = []
        for j in range(len(profile)):
            px, py = ring[j][0], ring[j][1]
            if not profile_fn and profile_end is not None:
                px = px + (profile_end[j][0] - px) * t
                py = py + (profile_end[j][1] - py) * t
            rx = (px * ct - py * st) * s
            ry = (px * st + py * ct) * s
            x3 = (o[0] + n[0] * rx + b[0] * ry, o[1] + n[1] * rx + b[1] * ry, o[2] + n[2] * rx + b[2] * ry)
            sec.append((x3[0], -x3[2], x3[1]))                                 # back to Blender's
        secs.append(sec)
    me = loft_mesh(secs, closed=closed, cap_start=closed if cap_start is None else cap_start,
                   cap_end=closed if cap_end is None else cap_end, name=name, triangles=triangles)
    if material is None:
        material = bpy.data.materials.get('eido_loft_default')
        if material is None:
            material = new_material('eido_loft_default')
            bs = principled(material)
            c = 0xb8b8c0
            lin = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
            bs.inputs['Base Color'].default_value = (lin(((c >> 16) & 255) / 255), lin(((c >> 8) & 255) / 255),
                                                     lin((c & 255) / 255), 1.0)
            bs.inputs['Roughness'].default_value = 0.6
            bs.inputs['Metallic'].default_value = 0.1
    me.materials.append(material)
    obj = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj
