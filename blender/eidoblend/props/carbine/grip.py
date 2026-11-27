"""eidoblend.props.carbine.grip: the pistol grip, ONE moulded shell, built whole. Built by high.build after top.py.

Sections square to the grip's own axis (raked 34 degrees) are fitted to the traced front and back lines, so its side
view is the traced outline; a section is flat-sided with round straps, squarer in the top block, rounder down the
backstrap. The skin runs from the SEAT under the receiver to the BASE, each of its lines ending exactly on those two
planes; the hollow (a 3 mm wall, an open base) is the same shell's inside. Its three rims are rounded IN THE SURFACE,
each by its own radius (the base's outer rim 1.4 mm, the seat's 0.6, the base's inner rim 0.5): rows of a quadratic arc
from the plane to the wall, never a boolean cut bevelled afterwards (on a dense loft that leaves slivers the bevel
dents or tears). The finger rest stands off the front strap along the strap's own normal, the skirt flares by the
point's height over the base. Only two things are CUT: the pocket over the receiver's grip boss and the screw's hole
through its floor; the screw and its lock washer are separate parts. The chequered panels and the backstrap's ribs are
finer than this mesh carries: the bake lays them in (layers.py), from this file's frame (G_O, G_RAKE).
"""

from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from ..hardsurface import masses as hs
from ..hardsurface.masses import MM, boolean, cyl, detail, finish, obj, prism_side

G_RAKE = math.radians(34.0)
G_O = (61.9, -47.0)                                           # the top of the front face, on the receiver's underside
G_D = (-math.sin(G_RAKE), -math.cos(G_RAKE))                  # down the grip
G_N = (math.cos(G_RAKE), -math.sin(G_RAKE))                   # toward the front strap
G_B1, G_NB = (22.8, -148.5), (0.2610, 0.9654)                 # the base's plane: a point of it, its normal (up into the grip)
# the traced lines in the grip's frame (s down the axis, t toward the front strap), each run on past the seat and the
# base; the front line is the strap WITHOUT the finger rest (a section swells all round when its line steps), which is
# G_REST, laid on as a displacement
G_FRONT = [(-31.0, -20.9), (0.0, 0.0), (21.0, 14.17), (24.5, 16.2), (27.5, 17.5), (30.5, 18.0), (34.7, 17.3), (39.3, 17.4), (43.4, 18.3), (47.0, 19.6),
           (52.0, 21.3), (56.8, 22.4), (64.1, 22.3), (71.3, 21.9), (78.6, 21.8), (85.6, 21.8), (92.5, 21.9), (142.0, 21.9)]
G_BACK = [(-31.0, -61.9), (19.0, -28.2), (21.9, -26.6), (25.0, -25.7), (29.8, -23.9), (36.3, -21.6), (43.0, -21.0), (51.3, -21.2), (63.2, -21.4),
          (75.1, -21.7), (86.9, -21.9), (98.9, -22.0), (142.0, -22.0)]
G_REST = [(45.0, 0.0), (46.5, 0.0), (47.5, 0.5), (48.6, 2.2), (49.8, 4.6), (50.7, 6.1), (51.5, 6.5), (52.4, 6.0), (53.4, 4.6), (54.6, 2.8),
          (55.8, 1.2), (57.0, 0.3), (58.2, 0.0), (59.5, 0.0)]                # (s, how far it stands off the strap)
G_WALL, G_ROOF = 3.0, 28.0                                    # the shell's wall; the hollow's roof (s)


def g_line(pts, sigma=0.8):
    """a traced line resampled every 0.1 mm and eased (the trace's corners are the mould's fillets, about 1.5 mm)"""
    fine = np.arange(pts[0][0], pts[-1][0] + 0.001, 0.1)
    v = np.interp(fine, [p[0] for p in pts], [p[1] for p in pts])
    k = np.exp(-0.5 * (np.arange(-30, 31) * 0.1 / sigma) ** 2)
    pad = np.concatenate([v[0] - (v[1] - v[0]) * np.arange(30, 0, -1), v, v[-1] + (v[-1] - v[-2]) * np.arange(1, 31)])
    return fine, np.convolve(pad, k / k.sum(), mode='valid')


G_SF, G_TF = g_line(G_FRONT)
G_SB, G_TB = g_line(G_BACK)
G_SR, G_HR = g_line(G_REST, sigma=0.6)                       # (a round tip and a hollow under it, not a chisel's edge)


def g_ease(s, s0, s1, a, b):
    x = min(1.0, max(0.0, (s - s0) / (s1 - s0)))
    return a + (b - a) * x * x * (3.0 - 2.0 * x)


def g_p(s, t, y=0.0):
    """a point of the grip's frame in the carbine's space (mm)"""
    return (G_O[0] + s * G_D[0] + t * G_N[0], y, G_O[1] + s * G_D[1] + t * G_N[1])


def g_q(p):
    """a point's height over the base"""
    return (p[0] - G_B1[0]) * G_NB[0] + (p[2] - G_B1[1]) * G_NB[1]


def g_pt(s, th, inset=0.0, flare_k=1.0):
    """the shell's surface at s down the axis and th round the section (mm, the carbine's space). inset: the hollow's
    side of the wall. The skirt is laid on from the point's own height over the base; the finger rest stands off the
    front strap along the strap's own normal."""
    tf, tb = float(np.interp(s, G_SF, G_TF)), float(np.interp(s, G_SB, G_TB))
    if inset:
        tf = min(tf, 21.9)
    tc, hd = (tf + tb) / 2.0, (tf - tb) / 2.0 - inset
    hw = g_ease(s, 6.0, 38.0, 12.3, 15.0) - inset              # nearly the receiver's width at the seat, 30 mm in the hand
    nf, nb = g_ease(s, 24.0, 40.0, 6.0, 3.4), g_ease(s, 20.0, 42.0, 4.5, 2.7)
    c, sn = math.cos(th), math.sin(th)
    e = 2.0 / (nf if c >= 0 else nb)
    t = tc + hd * math.copysign(abs(c) ** e, c)
    y = hw * math.copysign(abs(sn) ** e, sn)
    if not inset and c > 0.0 and abs(y) < 11.0:
        rest = max(0.0, float(np.interp(s, G_SR, G_HR, left=0.0, right=0.0)))
        if rest > 0.0:                                         # full at the strap's middle, gone by 22 mm across
            nt_, ny_ = abs(c) ** (2.0 - e) / hd, math.copysign(abs(sn) ** (2.0 - e), sn) / hw
            nl = math.hypot(nt_, ny_)
            wy = math.cos(math.pi * abs(y) / 22.0) ** 2
            t, y = t + rest * wy * nt_ / nl, y + rest * wy * ny_ / nl
    f = min(1.0, max(0.0, (10.4 - g_q(g_p(s, t))) / 5.0))
    f = f * f * (3.0 - 2.0 * f)
    r = math.hypot(t - tc, y)
    if f > 0.0 and r > 1e-6:
        ct, sy = (t - tc) / r, y / r
        # the skirt: the toe a broad lip 6.8 mm proud right across the front strap, the sides 1.3, the heel 1.0
        dt = (5.8 * ct * ct * (3.0 - 2.0 * ct) + 1.0 * ct) if ct >= 0 else 1.0 * ct
        t, y = t + flare_k * f * dt, y + flare_k * f * 1.3 * sy
    return g_p(s, t, y)


def g_solve(fn, lo, hi):
    flo = fn(lo)
    for _ in range(44):
        mid = 0.5 * (lo + hi)
        fm = fn(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def g_round(C, sC, th, sgn, r, tp, nf, inset=0.0, flare_k=1.0):
    """the round of radius r between the wall and a cut plane at the rim point C: nf + 1 rows from the PLANE's side to
    the WALL's, and the s where the wall takes over. tp: the way into the cut face, in its plane (a unit vector)"""
    ln = r
    for _ in range(3):
        A = Vector(g_pt(sC + sgn * ln, th, inset, flare_k))
        al = (A - C).normalized().angle(tp)
        ln = min(2.5 * r, max(0.5 * r, r / math.tan(al / 2.0)))
    A = Vector(g_pt(sC + sgn * ln, th, inset, flare_k))
    B = C + tp * ln
    return [B.lerp(C, w).lerp(C.lerp(A, w), w) for w in (i / nf for i in range(nf + 1))], sC + sgn * ln


def g_shell(name, ring, rows, nf):
    bm = bmesh.new()
    TH = [2.0 * math.pi * j / ring for j in range(ring)]
    NB3 = Vector((G_NB[0], 0.0, G_NB[1]))

    def flat(v, n3):
        v = v - n3 * v.dot(n3)
        return v.normalized()
    # the rims: where each line of the skin meets the seat (z = -47) and the base; where the hollow's meets the base
    s_seat = [g_solve(lambda s, th=th: g_pt(s, th)[2] + 47.0, -31.0, 45.0) for th in TH]
    s_base = [g_solve(lambda s, th=th: g_q(g_pt(s, th)), 85.0, 141.0) for th in TH]
    s_in = [g_solve(lambda s, th=th: g_q(g_pt(s, th, G_WALL, 0.6)), 85.0, 141.0) for th in TH]
    C_seat = [Vector(g_pt(s, th)) for s, th in zip(s_seat, TH)]
    C_base = [Vector(g_pt(s, th)) for s, th in zip(s_base, TH)]
    C_in = [Vector(g_pt(s, th, G_WALL, 0.6)) for s, th in zip(s_in, TH)]
    m_seat = sum(C_seat, Vector()) / ring
    m_base = sum(C_base, Vector()) / ring
    outer, inner = [], []
    for j, th in enumerate(TH):
        top, sa = g_round(C_seat[j], s_seat[j], th, +1.0, 0.6, flat(m_seat - C_seat[j], Vector((0, 0, 1))), nf)
        bot, sb = g_round(C_base[j], s_base[j], th, -1.0, 1.4, flat(m_base - C_base[j], NB3), nf)
        wall = [Vector(g_pt(sa + (sb - sa) * k / rows, th)) for k in range(1, rows)]
        outer.append(top + wall + bot[::-1])
        rim, si = g_round(C_in[j], s_in[j], th, -1.0, 0.5, flat(C_base[j] - C_in[j], NB3), nf, G_WALL, 0.6)
        wall = [Vector(g_pt(G_ROOF + (si - G_ROOF) * k / (rows // 2), th, G_WALL, 0.6)) for k in range(0, rows // 2)]
        inner.append(wall + rim[::-1])
    vo = [[bm.verts.new(p * MM) for p in line] for line in outer]
    vi = [[bm.verts.new(p * MM) for p in line] for line in inner]

    def face(vs, tag):
        bm.faces.new(vs).material_index = tag
    for V_, tag in ((vo, 0), (vi, 4)):
        for j in range(ring):
            a, b = V_[j], V_[(j + 1) % ring]
            for k in range(len(a) - 1):
                face((a[k], b[k], b[k + 1], a[k + 1]), tag)
    face([vo[j][0] for j in range(ring)], 1)                                    # the seat
    face([vi[j][0] for j in range(ring)], 4)                                    # the hollow's roof
    for j in range(ring):                                                       # the base's flat, between the two rims
        face((vo[j][-1], vo[(j + 1) % ring][-1], vi[(j + 1) % ring][-1], vi[j][-1]), 2)
    return obj(name, bm)


def build(CLAY):
    LOW = hs.low()
    # lines round, rows down the skin, rows in a rim's round (the low: 40 lines keep its section's sagitta near 0.1 mm;
    # 44 rows follow the finger rest and the skirt)
    G_RING, G_ROWS, G_NF = (40, 44, 2) if LOW else (96, 380, 4)
    tags = [bpy.data.materials.new(f'grip_cut_{k}') for k in range(6)]     # 0 skin, 1 seat, 2 base, 3 pocket, 4 hollow, 5 hole

    def g_tag(o, k=None):
        o.data.materials.clear()
        for m_ in tags:
            o.data.materials.append(m_)
        if k is not None:
            for p in o.data.polygons:
                p.material_index = k
        return o

    grip = g_tag(g_shell('pistol_grip', G_RING, G_ROWS, G_NF))
    # the pocket over the receiver's boss: everything above the boss's angled face (square to the axis, s = 18.0), 13.2 wide
    grip = detail(grip, g_tag(prism_side('grip_pocket', [(58.3, -30.0), (58.3, -66.5), (4.2, -30.0)], -6.6, 6.6), 3), 'DIFFERENCE')
    grip = detail(grip, g_tag(cyl('grip_screw_hole', g_p(10.0, -9.0), g_p(30.0, -9.0), 6.8, seg=24), 5), 'DIFFERENCE')
    # the cut edges' group: the pocket's mouth 0.4 mm, the screw hole's two ends 0.3
    bm_ = bmesh.new()
    bm_.from_mesh(grip.data)
    bmesh.ops.remove_doubles(bm_, verts=bm_.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm_, edges=bm_.edges, dist=2e-6)
    bmesh.ops.recalc_face_normals(bm_, faces=bm_.faces)
    g_lay = bm_.edges.layers.float.get('bevel_weight_edge') or bm_.edges.layers.float.new('bevel_weight_edge')
    g_count = {}
    for e_ in bm_.edges:
        if len(e_.link_faces) != 2:
            continue
        key = tuple(sorted({e_.link_faces[0].material_index, e_.link_faces[1].material_index}))
        if (3 in key or 5 in key) and len(key) == 2 and e_.calc_face_angle_signed(0.0) > math.radians(25.0):
            e_[g_lay] = 1.0 if key == (1, 3) else 0.75
            g_count[key] = g_count.get(key, 0) + 1
    g_open = sum(1 for e_ in bm_.edges if not e_.is_manifold)
    g_vol = bm_.calc_volume()
    for f_ in bm_.faces:
        f_.material_index, f_.smooth = 0, True
    bm_.to_mesh(grip.data)
    bm_.free()
    grip.data.materials.clear()
    grip.data.materials.append(CLAY)
    for c_ in list(grip.users_collection):
        c_.objects.unlink(grip)
    hs.col.objects.link(grip)
    if not LOW:
        gb = grip.modifiers.new('cut_edges', 'BEVEL')
        gb.width, gb.segments, gb.limit_method, gb.harden_normals = 0.4 * MM, 3, 'WEIGHT', True
        gw = grip.modifiers.new('flat_faces_flat', 'WEIGHTED_NORMAL')
        gw.keep_sharp = True
    hs.REPORT.append(('pistol_grip', g_open, round(g_vol * 1e3, 3), len(grip.data.polygons)))
    # its screw (a slotted fillister head on a lock washer), up the hollow, through the pocket's floor, into the boss
    finish(cyl('grip_screw_washer', g_p(28.0, -9.0), g_p(29.3, -9.0), 12.0, seg=32), 0.2, CLAY)
    g_head = cyl('grip_screw', g_p(29.3, -9.0), g_p(34.3, -9.0), 9.6, seg=32)
    g_slot = [g_p(32.5, -9.6), g_p(36.0, -9.6), g_p(36.0, -8.4), g_p(32.5, -8.4)]
    g_head = boolean(g_head, prism_side('grip_screw_slot', [(p[0], p[2]) for p in g_slot], -8.0, 8.0), 'DIFFERENCE')
    finish(g_head, 0.4, CLAY)
    finish(cyl('grip_screw_shank', g_p(9.0, -9.0), g_p(29.3, -9.0), 6.2, seg=24), 0.0, CLAY)
