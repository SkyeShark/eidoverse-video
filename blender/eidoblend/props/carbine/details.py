"""eidoblend.props.carbine.details: the high raised where a camera sees it close (built last by high.build).

Forms down to about half a millimetre are mesh; what is finer is left to the bake.
    the trigger      a swept, curved blade: its front face concave, the tip curled forward, rounded across
    the magazine     ONE pressed shell of fitted sections, its pressed ribs a profile IN the section (a plateau 0.9 mm
                     proud with cosine shoulders, each fading out at its ends as a pressing does); its floor plate
    the stock        its latch (rounded across, finger grooves, a roll pin), the butt's ribs, the sling loop (a bent wire
                     D-ring: one closed superellipse path, so no bend is tighter than the wire)
    small parts      the optic's turret caps, battery cap and brightness knob knurled, its objective's ribbed rubber
                     sleeve; the rear sight's knurled windage knob, its two-hole aperture and the cross-bolt's nut
The low (high.build(low=True)) keeps every form but turns the knurls, the ribs and the grooves plain: the bake's.
"""

from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..hardsurface import masses as hs
from ..hardsurface.masses import MM, boolean, box, clean, cyl, detail, finish, lathe, nseg, obj, prism_section, prism_side, rrect


def d_path(pts, n):
    """a smooth path through traced points (mm): Catmull-Rom through them, resampled to n points by arc length"""
    P = [np.array(p, float) for p in pts]
    P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(32):
            t = k / 32
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    dense.append(P[-2])
    dense = np.array(dense)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
    u = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(u, s, dense[:, k]) for k in range(dense.shape[1])], 1), float(s[-1])


def d_skin(name, ring_list, cap0=True, cap1=True):
    """a skin over rings of points (mm), each ring the same count and winding; the end rings filled"""
    bm = bmesh.new()
    V = [[bm.verts.new(Vector(tuple(p)) * MM) for p in r] for r in ring_list]
    n = len(V[0])
    for a_, b_ in zip(V, V[1:]):
        for k in range(n):
            bm.faces.new((a_[k], a_[(k + 1) % n], b_[(k + 1) % n], b_[k]))
    if cap0:
        bm.faces.new(V[0][::-1])
    if cap1:
        bm.faces.new(V[-1])
    return obj(name, bm)


def d_se(th, ef, eb):
    """a superellipse's point for the angle th: (along, across); the front half (cos >= 0) squareness ef, the back eb"""
    c_, s_ = math.cos(th), math.sin(th)
    e = 2.0 / (ef if c_ >= 0 else eb)
    return math.copysign(abs(c_) ** e, c_), math.copysign(abs(s_) ** e, s_)


def fluted(name, stations, band, flutes, depth, seg=None, z=0.0, y=0.0, pitch=0.0):
    """a turned part on a line parallel to X with a FLUTED (knurled) band: stations [(x, diameter)]; inside band (x0, x1)
    each ring's radius dips by depth in `flutes` narrow grooves (pitch: degrees the flutes turn per mm, a straight knurl
    when 0). The low turns it plain."""
    if hs.low():
        return lathe(name, stations, seg=nseg(max(d for _, d in stations), seg or 48), z=z)
    seg = seg or flutes * 8
    # the profile in its own order (a flat end is two stations at one x), each run along x cut every 0.25 mm, so a
    # groove's two ends are rounded off by the band's own ease
    pts_ = []
    for (xa, da), (xb, db) in zip(stations, stations[1:]):
        pts_.append((xa, da))
        if xb - xa > 0.3:
            m_ = int((xb - xa) / 0.25)
            pts_ += [(xa + (xb - xa) * k / m_, da + (db - da) * k / m_) for k in range(1, m_)]
    pts_.append(stations[-1])
    bm = bmesh.new()
    rings_ = []
    for x, d_ in pts_:
        ease = min(1.0, max(0.0, (x - band[0]) / 0.6)) * min(1.0, max(0.0, (band[1] - x) / 0.6))
        ring = []
        for k in range(seg):
            a_ = 2 * math.pi * k / seg
            ph = (a_ + math.radians(pitch * (x - band[0]))) * flutes
            g = max(0.0, math.cos(ph)) ** 6                     # a narrow groove, its bottom round, lands broad
            r_ = d_ / 2 - depth * g * ease
            ring.append(bm.verts.new((x * MM, (y + r_ * math.cos(a_)) * MM, (z + r_ * math.sin(a_)) * MM)))
        rings_.append(ring)
    for a_, b_ in zip(rings_, rings_[1:]):
        for k in range(seg):
            bm.faces.new((a_[k], a_[(k + 1) % seg], b_[(k + 1) % seg], b_[k]))
    bm.faces.new(rings_[0][::-1])
    bm.faces.new(rings_[-1])
    return obj(name, bm)


def turned_on(o, p0, p1):
    """a part made along +X from x = 0, carried onto the axis p0 -> p1 (mm)"""
    a, b = Vector(p0) * MM, Vector(p1) * MM
    o.location = a
    o.rotation_euler = (b - a).to_track_quat('X', 'Z').to_euler()
    bpy.context.view_layer.update()
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    return o


# the trigger's blade: 6.2 mm wide, its front face concave, the tip curled forward; depths fore and aft by the path's
# fraction
TR_C = [(92.0, -43.0), (91.2, -50.5), (89.6, -55.5), (88.4, -60.0), (88.0, -63.8), (88.6, -66.8), (89.8, -68.6)]
TR_D = [(0.0, 6.2), (0.3, 5.0), (0.55, 4.2), (0.8, 3.8), (1.0, 3.5)]
TR_W = 6.2
# the magazine: stations square to its curve between the traced front and back lines, each a rounded rectangle 22.2 mm
# across with the sheet's 2 mm bends; the ribs (centre as a share of the depth back -> front, plateau half-width, top
# and bottom z)
MG_F = [(186.0, -20.0), (188.0, -66.0), (190.0, -80.0), (198.0, -120.0), (207.0, -166.0), (207.5, -168.0)]
MG_B = [(124.0, -20.0), (125.0, -75.0), (126.0, -100.0), (133.0, -140.0), (148.0, -185.0)]
MG_HW, MG_RC, MG_H = 11.1, 2.0, 0.9
MG_RIBS = [(0.095, 1.1, -76.0, -183.0), (0.30, 2.1, -78.0, -180.0), (0.58, 2.1, -74.0, -172.0)]


def build(CLAY):
    LOW = hs.low()
    # ======================================================================================== THE TRIGGER
    n_p, n_r = (12, 16) if LOW else (110, 72)
    path, L_ = d_path(TR_C, n_p)
    rings_ = []
    for i, p in enumerate(path):
        f = i / (n_p - 1)
        t = path[min(i + 1, n_p - 1)] - path[max(i - 1, 0)]
        t /= np.linalg.norm(t)
        nf = np.array((-t[1], t[0]))                                 # forward, square to the blade's line
        d_ = float(np.interp(f, [q[0] for q in TR_D], [q[1] for q in TR_D]))
        tip = 1.8 / L_                                                # the last 1.8 mm round the tip off
        k_ = 1.0 if f < 1.0 - tip else max(0.18, math.sqrt(max(0.0, 1.0 - ((f - (1.0 - tip)) / tip) ** 2)))
        ring = []
        for j in range(n_r):
            a_, b_ = d_se(2 * math.pi * j / n_r, 2.3, 4.5)
            ring.append((p[0] + nf[0] * a_ * d_ / 2 * k_, b_ * TR_W / 2 * k_, p[1] + nf[1] * a_ * d_ / 2 * k_))
        rings_.append(ring)
    finish(d_skin('trigger', rings_), 0.0, CLAY, dissolve=False)

    # ======================================================================================== THE MAGAZINE
    n_st = 22 if LOW else 170
    FB, _ = d_path(MG_F, n_st)
    BB, _ = d_path(MG_B, n_st)
    n_side, n_cor, n_end = (6, 3, 3) if LOW else (84, 8, 14)

    def mg_bump(t_mm, D, zt):
        """how far the side stands out at t_mm from the back (the ribs; 0 in the low: the bake's)"""
        if LOW:
            return 0.0
        h = 0.0
        for c_, pw, z0, z1 in MG_RIBS:
            x = abs(t_mm - c_ * D)
            prof = 1.0 if x <= pw else (0.5 * (1.0 + math.cos(math.pi * (x - pw) / 1.6)) if x <= pw + 1.6 else 0.0)
            fade = min(1.0, max(0.0, (z0 - zt) / 6.0)) * min(1.0, max(0.0, (zt - z1) / 6.0))
            fade = fade * fade * (3.0 - 2.0 * fade)
            h = max(h, MG_H * prof * fade)
        return h

    rings_ = []
    for i in range(n_st):
        B_, F_ = BB[i], FB[i]
        a_ = F_ - B_
        D = float(np.linalg.norm(a_))
        a_ /= D

        def P(t_mm, y_, B_=B_, a_=a_):
            return (B_[0] + a_[0] * t_mm, y_, B_[1] + a_[1] * t_mm)
        ring = []
        r_ = MG_RC
        # around the section: the right side (y < 0) back -> front, the front bends, the left side front -> back, the back
        for k in range(n_side):
            t_ = r_ + (D - 2 * r_) * k / n_side
            zt = B_[1] + a_[1] * t_
            ring.append(P(t_, -(MG_HW + mg_bump(t_, D, zt))))
        for k in range(n_cor):                                       # front-right bend
            th = -math.pi / 2 + (math.pi / 2) * k / n_cor
            ring.append(P(D - r_ + r_ * math.cos(th), -(MG_HW - r_) + r_ * math.sin(th)))
        for k in range(n_end):
            ring.append(P(D, -(MG_HW - r_) + 2 * (MG_HW - r_) * k / n_end))
        for k in range(n_cor):                                       # front-left bend
            th = (math.pi / 2) * k / n_cor
            ring.append(P(D - r_ + r_ * math.cos(th), (MG_HW - r_) + r_ * math.sin(th)))
        for k in range(n_side):
            t_ = D - r_ - (D - 2 * r_) * k / n_side
            zt = B_[1] + a_[1] * t_
            ring.append(P(t_, MG_HW + mg_bump(t_, D, zt)))
        for k in range(n_cor):                                       # back-left bend
            th = math.pi / 2 + (math.pi / 2) * k / n_cor
            ring.append(P(r_ + r_ * math.cos(th), (MG_HW - r_) + r_ * math.sin(th)))
        for k in range(n_end):
            ring.append(P(0.0, (MG_HW - r_) - 2 * (MG_HW - r_) * k / n_end))
        for k in range(n_cor):                                       # back-right bend
            th = math.pi + (math.pi / 2) * k / n_cor
            ring.append(P(r_ + r_ * math.cos(th), -(MG_HW - r_) + r_ * math.sin(th)))
        rings_.append(ring)
    finish(d_skin('magazine', rings_), 0.0, CLAY, dissolve=False)
    # its floor plate (sheet steel slid into the body's turned-in flange)
    finish(prism_side('magazine_floor_plate', [(146.5, -186.5), (208.5, -166.8), (209.5, -169.6), (147.5, -189.6)], -12.6, 12.6), 0.9, CLAY)

    # ======================================================================================== THE STOCK'S HARDWARE
    # the latch: the moulded lever under the stock's front, rounded across (2.5 mm) by its section, three finger grooves
    # across its rear pull, its pivot's roll pin through the front
    lat = boolean(prism_side('stock_latch', [(-95, -49.5), (-48, -49.5), (-46, -47), (-46, -52), (-62, -55), (-90, -55)], -8.0, 8.0),
                  prism_section('latch_sec', rrect(-8.0, -56.0, 8.0, -46.0, 2.5, n=6), -100, -40), 'INTERSECT')
    for k in range(3):
        xg = -91.0 + k * 3.2
        lat = detail(lat, box(f'latch_groove{k}', (xg - 0.6, -10, -56.5), (xg + 0.6, 10, -54.2)), 'DIFFERENCE')
    finish(lat, 0.8, CLAY)
    finish(cyl('stock_latch_roll_pin', (-52.0, -8.4, -51.0), (-52.0, 8.4, -51.0), 2.6, seg=24), 0.15, CLAY)
    # the butt's ribs: grooves across its rear face (2.6 mm apart, 0.6 mm deep, round-bottomed by the part's own edge
    # group), along the face's slope (-178.5, 0) -> (-171, -104), and over its top (-178, 14) -> (-178.5, 0)
    if not LOW:
        butt_face = [((-178.0, 12.5), (-178.5, 0.0)), ((-178.5, 0.0), (-171.2, -101.0))]
        cut = None
        for (p0, p1) in butt_face:
            p0, p1 = np.array(p0), np.array(p1)
            L = float(np.linalg.norm(p1 - p0))
            t = (p1 - p0) / L
            nrm = np.array((t[1], -t[0]))                            # into the stock (forward)
            if nrm[0] < 0:
                nrm = -nrm
            s = 1.8
            while s < L - 1.0:
                c_ = p0 + t * s
                q = [c_ - t * 0.55 - nrm * 2.0, c_ + t * 0.55 - nrm * 2.0, c_ + t * 0.55 + nrm * 0.6, c_ - t * 0.55 + nrm * 0.6]
                g = prism_side(f'butt_rib_{len(butt_face)}_{s:.1f}', [tuple(v) for v in q], -19.5, 19.5)
                cut = g if cut is None else boolean(cut, g, 'UNION')
                s += 2.6
        stock_o = hs.col.objects.get('stock')
        if stock_o is None:
            raise RuntimeError('details: the stock is not in this build (build the carbine into an empty file)')
        for mdf in list(stock_o.modifiers):                        # (the stock left the workbench with its edge group:
            stock_o.modifiers.remove(mdf)                          #  cut first, then give it back)
        stock_o = boolean(stock_o, cut, 'DIFFERENCE')
        clean(stock_o)
        b_ = stock_o.modifiers.new('edge_group', 'BEVEL')
        b_.width, b_.segments, b_.limit_method, b_.angle_limit = 1.6 * MM, 3, 'ANGLE', math.radians(30)
        b_.harden_normals = True
        w_ = stock_o.modifiers.new('flat_faces_flat', 'WEIGHTED_NORMAL')
        w_.keep_sharp = True
    # the sling loop at the toe: the straight bar through the slot's foot, the round of the D hanging down and back at
    # 40 degrees; wire 3.4 mm
    lp_n = 24 if LOW else 72
    dn3 = np.array((-math.sin(math.radians(40.0)), 0.0, -math.cos(math.radians(40.0))))      # down and back
    o3 = np.array((-167.0, 0.0, -97.0))
    lp_path = []
    for k in range(lp_n):
        ph = 2 * math.pi * k / lp_n
        c_, s_ = math.cos(ph), math.sin(ph)
        e = 2.0 / (4.0 if s_ < 0 else 2.2)
        lp_path.append(o3 + np.array((0.0, 10.5 * math.copysign(abs(c_) ** e, c_), 0.0)) + dn3 * (6.2 + 6.2 * math.copysign(abs(s_) ** e, s_)))
    m3 = np.cross((0.0, 1.0, 0.0), dn3)
    m3 /= np.linalg.norm(m3)                                          # the D's plane's normal: one frame all round
    n_w = 10 if LOW else 20
    wr = []
    for i, p in enumerate(lp_path):
        t = lp_path[(i + 1) % lp_n] - lp_path[i - 1]
        t /= np.linalg.norm(t)
        v = np.cross(t, m3)
        wr.append([tuple(p + (m3 * math.cos(2 * math.pi * j / n_w) + v * math.sin(2 * math.pi * j / n_w)) * 1.7) for j in range(n_w)])
    bm_ = bmesh.new()
    V_ = [[bm_.verts.new(Vector(q) * MM) for q in r] for r in wr]
    for a_, b_ in zip(V_, V_[1:] + V_[:1]):                          # a closed ring of wire: the last section joins the first
        for k in range(n_w):
            bm_.faces.new((a_[k], a_[(k + 1) % n_w], b_[(k + 1) % n_w], b_[k]))
    finish(obj('sling_loop', bm_), 0.0, CLAY, dissolve=False)

    # ======================================================================================== THE OPTIC'S SMALL PARTS
    # knurled turret caps and battery cap, a fluted brightness knob, the objective's ribbed rubber sleeve: they replace
    # top.py's plain cylinders (same names, same places)
    for nm in ('turret_top_cap', 'turret_side_cap', 'battery_cap', 'brightness_knob'):
        if nm in hs.col.objects:
            bpy.data.objects.remove(hs.col.objects[nm], do_unlink=True)
    cap_prof = [(0.0, 8.0), (0.0, 15.2), (0.6, 16.0), (8.6, 16.0), (9.4, 15.2), (10.0, 13.6), (10.0, 8.0)]
    finish(turned_on(fluted('turret_top_cap', cap_prof, (1.2, 8.8), 28, 0.45), (112, 0, 82), (112, 0, 92)), 0.0, CLAY, dissolve=False)
    finish(turned_on(fluted('turret_side_cap', [(x * 0.9, d) for x, d in cap_prof], (1.1, 7.9), 28, 0.45), (112, -21, 61), (112, -30, 61)), 0.0, CLAY, dissolve=False)
    finish(turned_on(fluted('battery_cap', [(0.0, 6.0), (0.0, 14.2), (0.5, 15.0), (5.4, 15.0), (6.4, 13.4), (6.4, 6.0)], (0.9, 5.2), 24, 0.4),
                     (150, -22, 46), (150, -28.4, 43.4)), 0.0, CLAY, dissolve=False)
    finish(turned_on(fluted('brightness_knob', [(0.0, 6.0), (0.0, 16.0), (0.6, 17.0), (12.4, 17.0), (13.0, 16.0), (13.0, 6.0)], (1.4, 11.6), 20, 0.8),
                     (79, 0, 84), (92, 0, 84)), 0.0, CLAY, dissolve=False)
    finish(fluted('optic_front_sleeve', [(168.0, 31.0), (168.0, 33.8), (168.8, 34.6), (195.2, 34.6), (196.0, 33.8), (196.0, 31.0)],
                  (169.2, 194.8), 40, 0.35, z=61.0), 0.0, CLAY, dissolve=False)

    # ======================================================================================== THE REAR SIGHT'S PARTS
    for nm in ('rs_windage_knob', 'rs_aperture'):
        if nm in hs.col.objects:
            bpy.data.objects.remove(hs.col.objects[nm], do_unlink=True)
    finish(turned_on(fluted('rs_windage_knob', [(0.0, 4.0), (0.0, 13.2), (0.5, 14.0), (5.5, 14.0), (6.0, 13.2), (6.0, 4.0)], (0.9, 5.1), 24, 0.45),
                     (38, -15, 40.5), (38, -21, 40.5)), 0.0, CLAY, dissolve=False)
    ap = prism_side('rs_aperture', [(36.2, 40.5), (39.8, 40.5), (39.8, 53.5), (39.0, 55.2), (37.0, 55.2), (36.2, 53.5)], -3.4, 3.4)
    ap = detail(ap, cyl('ap_small', (30, 0, 51.6), (46, 0, 51.6), 1.8, seg=24), 'DIFFERENCE')
    ap = detail(ap, cyl('ap_large', (30, 0, 45.4), (46, 0, 45.4), 4.6, seg=32), 'DIFFERENCE')
    finish(ap, 0.3, CLAY)
    hexn = [(68.0 + 5.2 * math.cos(math.radians(30 + 60 * k)), 37.0 + 5.2 * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    finish(prism_side('rs_cross_bolt_nut', hexn, 13.0, 16.8), 0.35, CLAY)
