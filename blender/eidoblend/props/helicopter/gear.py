"""eidoblend.props.helicopter.gear: the landing gear, as it hangs in flight (the oleos run out 230 mm).

    main gear, each side   a ribbed 26 x 10 tyre on a two-piece wheel, its brake inboard; the axle's knuckle; a DRAG
                           BEAM from a pivot low on the hull's side under the cockpit door's rear, trailing down to the
                           knuckle, its front under a smooth fairing that carries a step and a position light; a near-
                           upright OLEO from the knuckle up the hull's side to a fitting under the gunner's window (a
                           painted cylinder, a bright piston), its torque links and brake hose
    tail wheel             a 15 x 6 tyre in a fork that castors on a trailing oleo under the boom, a brace behind it
"""

from __future__ import annotations

import math

from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from . import datum as D

EXT = 230.0                                                   # how far the oleos have run out, off the ground


def tyre(name, at, axis, r_out, half_w, r_bead, m):
    kw = half_w / 127.0
    base = [(150, -92), (168, -112), (215, -126), (262, -126), (300, -112), (322, -88), (330, -60), (330, -38), (323, -36), (323, -28), (330, -26), (330, 26),
            (323, 28), (323, 36), (330, 38), (330, 60), (322, 88), (300, 112), (262, 126), (215, 126), (168, 112), (150, 92)]
    prof = [(r_bead + (r - 150.0) * (r_out - r_bead) / 180.0, h * kw) for r, h in base]
    return bt.finish_smooth(hs.revolve(name, prof, at=at, axis=axis, seg=64, closed=True), m)


def wheel(name, at, axis, r_rim, half_w, m):
    k = r_rim / 150.0
    prof = [(0, 52), (34, 52), (40, 44), (62, 40), (72, 24), (120, 16), (134, 38), (150, 92), (158, 92), (158, -92), (150, -92), (134, -40), (120, -22), (118, -30),
            (118, -72), (60, -76), (0, -76)]
    return hs.finish(hs.revolve(name, [(r * k, h * half_w / 127.0) for r, h in prof], at=at, axis=axis, seg=48), 1.2, m)


def build(b):
    CLAY, GLASS, RUBBER, STEEL = b.clay, b.glass, b.rubber, b.steel
    bolts, rods = [], []
    for sgn, sd in ((1, 'r'), (-1, 'l')):
        out = Vector((0.0, float(sgn), 0.0))
        A = Vector((D.MAIN_WHEEL[0] + 35.0, sgn * D.MAIN_WHEEL[1], D.MAIN_WHEEL[2] - EXT))      # the wheel's centre, hanging
        J = A - out * 172.0                                        # the knuckle: where beam, oleo and axle meet
        U = Vector((-1092.0, sgn * 1216.0, 440.0))                 # the oleo's fitting on the hull
        P = Vector((-2180.0, sgn * 1160.0, -92.0))                 # the drag beam's pivot
        tyre(f'main_tyre_{sd}', A, out, 330.0, 127.0, 150.0, RUBBER)
        wheel(f'main_wheel_{sd}', A, out, 150.0, 127.0, CLAY)
        for q in range(8):
            a = 2 * math.pi * q / 8
            p = A + out * 20.0 + Vector((math.cos(a), 0.0, math.sin(a))) * 96.0
            bolts.append([hs.circle(p, out, 8.0, 0.0, 6), hs.circle(p, out, 8.0, 7.0, 6)])
        hs.finish(hs.revolve(f'main_axle_{sd}', [(0.0, -4.0), (40.0, -4.0), (40.0, 150.0), (56.0, 156.0), (56.0, 190.0), (0.0, 190.0)], at=J, axis=out, seg=24), 1.5, STEEL)
        # the knuckle: a forged block the three meet in
        kn = bt.round_poly([(-78.0, -70.0), (78.0, -70.0), (86.0, 60.0), (40.0, 108.0), (-40.0, 108.0), (-86.0, 60.0)], 26.0, 4)
        hs.finish(hs.rings(f'main_knuckle_{sd}', [[J + out * (dy) + Vector((x, 0.0, z)) for x, z in kn] for dy in (-58.0, 58.0)]), 5.0, CLAY)
        # the oleo: the painted cylinder from the hull's fitting, the bright piston out of it down to the knuckle
        ax = (J + Vector((0, 0, 60.0)) - U)
        L = ax.length
        ax.normalize()
        cyl_len = 560.0
        prof_c = [(0.0, -30.0), (40.0, -30.0), (46.0, 0.0), (66.0, 6.0), (66.0, 60.0), (60.0, 70.0), (60.0, cyl_len - 50.0), (68.0, cyl_len - 40.0),
                  (68.0, cyl_len - 6.0), (58.0, cyl_len), (0.0, cyl_len)]
        hs.finish(hs.revolve(f'main_oleo_{sd}', prof_c, at=U, axis=ax, seg=32), 0.0, CLAY)
        hs.finish(hs.revolve(f'main_oleo_piston_{sd}', [(0.0, cyl_len - 10.0), (43.0, cyl_len - 10.0), (43.0, L - 40.0), (52.0, L - 30.0), (52.0, L + 10.0),
                                                        (0.0, L + 10.0)], at=U, axis=ax, seg=32), 0.0, STEEL)
        # its fitting on the hull: a bracket
        hs.finish(hs.box(f'main_oleo_fitting_{sd}', (U.x - 70.0, min(sgn * 1172.0, sgn * 1252.0), U.z - 55.0),
                         (U.x + 70.0, max(sgn * 1172.0, sgn * 1252.0), U.z + 60.0)), 8.0, CLAY)
        # the torque links between cylinder and knuckle (they keep the wheel pointing ahead)
        t0, t1, t2 = U + ax * (cyl_len - 60.0) + Vector((-64.0, 0, 0)), U + ax * (cyl_len + (L - cyl_len) * 0.5) + Vector((-150.0, 0, 0)), J + Vector((-70.0, 0, 40.0))
        hs.finish(hs.skins(f'main_torque_links_{sd}', [rb for a_, b_ in ((t0, t1), (t1, t2)) for rb in ([[p + out * (w * i) + Vector((0, 0, 9.0 * j))
                                                                                                        for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                                                                                                       for p, w in ((a_, 34.0), (b_, 26.0))],)]), 2.0, CLAY)
        # the drag beam: a tapered box from its pivot to the knuckle
        beam_sec = bt.round_poly([(-52.0, -72.0), (52.0, -72.0), (52.0, 72.0), (-52.0, 72.0)], 22.0, 4)
        d = (J - P).normalized()
        side_ = d.cross(Vector((0, 0, 1.0))).normalized()
        up_ = side_.cross(d)
        rl = [[P.lerp(J, f) + side_ * (u * (1.0 - 0.22 * f)) + up_ * (v * (1.0 - 0.3 * f)) for u, v in beam_sec] for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
        bt.finish_smooth(hs.rings(f'main_drag_beam_{sd}', rl), CLAY, sharp_deg=35.0)
        # its fairing on the hull's side: a smooth teardrop over the pivot, a step let into its top, a light at its nose
        fc = Vector((-2060.0, sgn * 1218.0, -90.0))
        rl = []
        for q in range(1, 20):
            u = -1.0 + 2.0 * q / 20.0
            x = fc.x + 470.0 * u
            rr = math.sqrt(max(0.0, 1.0 - abs(u) ** 2.4))
            rl.append([(x, fc.y + sgn * 96.0 * rr * math.cos(2 * math.pi * i / 20), fc.z + 150.0 * rr * math.sin(2 * math.pi * i / 20) * (0.86 if math.sin(2 * math.pi * i / 20) > 0 else 1.0))
                       for i in range(20)])
        bt.finish_smooth(hs.rings(f'drag_beam_fairing_{sd}', rl), CLAY)
        hs.finish(hs.box(f'gear_step_{sd}', (fc.x - 150.0, min(fc.y - sgn * 40.0, fc.y + sgn * 150.0), fc.z + 118.0),
                         (fc.x + 170.0, max(fc.y - sgn * 40.0, fc.y + sgn * 150.0), fc.z + 134.0)), 3.0, CLAY)
        hs.finish(hs.revolve(f'position_light_{sd}', [(0.0, 0.0), (26.0, 0.0), (26.0, 16.0), (20.0, 40.0), (9.0, 52.0), (0.0, 54.0)], at=(fc.x - 455.0, fc.y, fc.z),
                             axis=(-1, 0, 0), seg=20), 0.0, GLASS)
        # the brake's hose down the oleo
        h0 = U + Vector((40.0, sgn * 62.0, -40.0))
        rods.append([hs.circle(h0, (J + out * 40.0 + Vector((60.0, 0, 30.0))) - h0, 6.5, 0.0, 8),
                     hs.circle(h0, (J + out * 40.0 + Vector((60.0, 0, 30.0))) - h0, 6.5, (J - U).length, 8)])
    hs.finish(hs.skins('main_wheel_bolts', bolts), 0.0, STEEL)
    hs.finish(hs.skins('brake_hoses', rods), 0.0, RUBBER)
    # ---------------------------------------------------------------- the tail wheel
    T = Vector((D.TAIL_WHEEL[0], 0.0, D.TAIL_WHEEL[2] - 110.0))
    ay = Vector((0.0, 1.0, 0.0))
    tyre('tail_tyre', T, ay, 190.0, 75.0, 82.0, RUBBER)
    wheel('tail_wheel', T, ay, 82.0, 75.0, CLAY)
    crown = Vector((7648.0, 0.0, T.z + 232.0))
    fork = []
    for s in (-1, 1):
        side_pts = [T + ay * (s * 92.0), T + ay * (s * 92.0) + Vector((-28.0, 0, 120.0)), crown + ay * (s * 70.0)]
        fork.append([[p + Vector((dx, 0, 0)) + ay * (s * dy) for dx, dy in ((-24.0, -8.0), (24.0, -8.0), (24.0, 8.0), (-24.0, 8.0))] for p in side_pts])
    fork.append([[crown + Vector((dx, dy, dz)) for dx, dy in ((-40.0, -82.0), (40.0, -82.0), (40.0, 82.0), (-40.0, 82.0))] for dz in (-22.0, 26.0)])
    hs.finish(hs.skins('tail_fork', fork), 4.0, CLAY)
    hs.finish(hs.revolve('tail_axle', [(0.0, -104.0), (17.0, -104.0), (17.0, 104.0), (0.0, 104.0)], at=T, axis=ay, seg=16), 1.0, STEEL)
    top = Vector((7070.0, 0.0, 150.0))
    ax = (crown - top)
    L = ax.length
    ax.normalize()
    hs.finish(hs.revolve('tail_oleo', [(0.0, -40.0), (50.0, -40.0), (50.0, L * 0.55), (44.0, L * 0.55 + 10.0), (0.0, L * 0.55 + 10.0)], at=top, axis=ax, seg=28), 0.0, CLAY)
    hs.finish(hs.revolve('tail_oleo_piston', [(0.0, L * 0.5), (33.0, L * 0.5), (33.0, L - 10.0), (44.0, L - 4.0), (44.0, L + 24.0), (0.0, L + 24.0)], at=top, axis=ax, seg=28),
              0.0, STEEL)
    b0, b1 = top + ax * (L * 0.5), Vector((7560.0, 0.0, 196.0))
    hs.finish(hs.skins('tail_brace', [[hs.circle(b0, b1 - b0, 21.0, 0.0, 12), hs.circle(b0, b1 - b0, 21.0, (b1 - b0).length, 12)]]), 0.0, CLAY)
