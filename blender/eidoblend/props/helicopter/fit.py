"""eidoblend.props.helicopter.fit: what stands on the skin (needs hull.py's b.surf and top.py's b.spine).

Two wire cutters (over the cockpit, under the nose), two pitot tubes on the cockpit roof, the wipers at the windshields'
feet; blade aerials on the spine, the boom and the belly; the oil cooler's outlet behind the mast; under the belly the
red beacon, the landing light and the cargo hook in its well; each side three kick steps and two handholds climbing to
the engines; on the left the auxiliary unit's exhaust port, the rail aerial on its standoffs along the boom and two
dispensers.
"""

from __future__ import annotations

import math

from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from ..hardsurface.sections import stations
from . import datum as D


def tube(pts, r, seg=10, bend=None):
    path = hs.fillet_path(pts, bend, n=5) if bend else [Vector(p) for p in pts]
    return [[p + n * (r * math.cos(2 * math.pi * i / seg)) + b * (r * math.sin(2 * math.pi * i / seg)) for i in range(seg)] for p, t, n, b in hs.frames(path)]


def build(b):
    CLAY, DARK, GLASS, STEEL = b.clay, b.dark, b.glass, b.steel
    SURF, SPINE = getattr(b, 'surf', None), getattr(b, 'spine', None)
    if SURF is None or SPINE is None:
        raise RuntimeError('helicopter fit: the hull and the top must be built first')

    def plate(name, outline, half, m=None, y=0.0, bevel=1.5):
        return hs.finish(hs.prism_side(name, outline, y - half, y + half), bevel, m or CLAY)

    def on_side(x, z, sgn):
        return SURF.hit(Vector((x, sgn * 2600.0, z)), (0.0, -float(sgn), 0.0))

    def spine_top(x):
        K = SPINE.ctrl(x)[0]
        return K[3][1]

    # the two wire cutters: a blade over the cockpit, a blade under the nose
    plate('wire_cutter_upper', [(-2500.0, 1640.0), (-2250.0, 1745.0), (-2290.0, 1785.0), (-2575.0, 1985.0), (-2612.0, 1962.0), (-2520.0, 1690.0)], 5.0)
    plate('wire_cutter_lower', [(-3890.0, -20.0), (-3640.0, -100.0), (-3655.0, -128.0), (-3985.0, -335.0), (-4015.0, -312.0), (-3930.0, -60.0)], 5.0)
    # the two pitot tubes on the cockpit roof's front; the two wipers at the side windshields' feet
    pit, wip = [], []
    for sgn in (1, -1):
        h = SURF.hit(Vector((-2940.0, sgn * 560.0, 3000.0)), (0.0, 0.0, -1.0))
        if h:
            p, n = h
            pit.append(tube([p - n * 4.0, p + n * 120.0, p + n * 150.0 + Vector((-190.0, 0.0, 6.0))], 9.0, bend=34.0))
            pit.append([hs.circle(p, n, 26.0, -2.0, 14), hs.circle(p, n, 26.0, 5.0, 14)])
        # a wiper: its pivot at the sill, its arm up the pane, its blade across the arm's end
        out = Vector((-0.55, sgn * 0.25, 0.8)).normalized()
        pts = [SURF.hit(Vector((x, sgn * y, z)) + out * 900.0, -out) for x, y, z in ((-3690.0, 560.0, 720.0), (-3520.0, 590.0, 900.0), (-3360.0, 620.0, 1070.0))]
        if all(pts):
            wip.append(tube([pts[0][0] + pts[0][1] * 16.0, pts[1][0] + pts[1][1] * 20.0, pts[2][0] + pts[2][1] * 18.0], 5.5, seg=8))
            c, n = pts[2]
            d_ = (Vector((0.35, sgn * 0.9, 0.0)) - n * n.dot(Vector((0.35, sgn * 0.9, 0.0)))).normalized()
            wip.append([[c + d_ * a + n * b_ + n.cross(d_) * e for b_, e in ((6.0, -6.0), (6.0, 6.0), (20.0, 4.0), (20.0, -4.0))] for a in (-230.0, 230.0)])
            wip.append([hs.circle(pts[0][0], pts[0][1], 15.0, -2.0, 12), hs.circle(pts[0][0], pts[0][1], 15.0, 20.0, 12)])
    if pit:
        hs.finish(hs.skins('pitot_tubes', pit), 0.0, STEEL)
    if wip:
        hs.finish(hs.skins('wipers', wip), 0.0, DARK)

    # blade aerials: on the spine, on the boom, under the belly
    def blade_aerial(name, x, z, up=1.0, h=230.0, chord=190.0):
        o = [(x - chord * 0.5, z), (x + chord * 0.5, z), (x + chord * 0.62, z + up * h), (x + chord * 0.30, z + up * h * 1.03), (x - chord * 0.2, z + up * h * 0.45)]
        plate(name, o if up > 0 else o[::-1], 6.0, bevel=2.5)
        hs.finish(hs.box(name + '_base', (x - chord * 0.62, -24.0, z - up * 2.0), (x + chord * 0.62, 24.0, z + up * 9.0)), 2.0, CLAY)
    blade_aerial('aerial_spine', 2550.0, spine_top(2550.0) + 6.0)
    blade_aerial('aerial_boom', 6000.0, D.HULL.ctrl(6000.0)[0][6][1] + 70.0, h=200.0)
    blade_aerial('aerial_belly_fwd', -1700.0, D.BELLY - 2.0, up=-1.0, h=180.0)
    blade_aerial('aerial_belly_aft', 2500.0, D.BELLY - 2.0, up=-1.0, h=180.0)
    # the drum on the spine behind the mast (the oil cooler's outlet), its mesh dark
    zt = spine_top(1650.0)
    hs.finish(hs.revolve('cooler_outlet', [(0.0, -30.0), (236.0, -30.0), (236.0, 104.0), (224.0, 116.0), (212.0, 116.0), (212.0, 96.0), (0.0, 96.0)],
                         at=(1650.0, 0.0, zt), seg=48), 0.0, CLAY)
    hs.finish(hs.revolve('cooler_outlet_mesh', [(0.0, 96.0), (212.0, 96.0), (212.0, 100.0), (0.0, 100.0)], at=(1650.0, 0.0, zt), seg=32), 0.0, DARK)
    # under the belly: the red beacon, the landing light, the cargo hook in its well
    hs.finish(hs.revolve('beacon_lower', [(0.0, 0.0), (44.0, 0.0), (44.0, 18.0), (34.0, 60.0), (16.0, 84.0), (0.0, 88.0)],
                         at=(3150.0, 0.0, D.HULL.ctrl(3150.0)[0][0][1]), axis=(0, 0, -1), seg=24), 0.0, GLASS)
    hs.finish(hs.revolve('landing_light', [(0.0, 0.0), (70.0, 0.0), (74.0, 10.0), (74.0, 26.0), (60.0, 34.0), (0.0, 36.0)],
                         at=(-3250.0, 0.0, D.HULL.ctrl(-3250.0)[0][0][1]), axis=(0, 0, -1), seg=28), 0.0, GLASS)
    hook = [tube([Vector((20.0, 0.0, D.BELLY + 6.0)), Vector((20.0, 0.0, D.BELLY - 70.0)), Vector((-30.0, 0.0, D.BELLY - 135.0)), Vector((-80.0, 0.0, D.BELLY - 110.0)),
                  Vector((-78.0, 0.0, D.BELLY - 60.0))], 16.0, seg=10, bend=36.0)]
    hook.append([[Vector((dx, dy, D.BELLY + dz)) for dx, dy in ((-90.0, -70.0), (120.0, -70.0), (120.0, 70.0), (-90.0, 70.0))] for dz in (-26.0, 4.0)])
    hs.finish(hs.skins('cargo_hook', hook), 2.0, CLAY)

    for sgn, sd in ((1, 'r'), (-1, 'l')):
        # three kick steps and two handholds, climbing from the sill's height to the engines, aft of the doorway
        holds = []
        for x, z in ((3120.0, 180.0), (3210.0, 610.0), (3300.0, 1040.0)):
            h = on_side(x, z, sgn)
            if not h:
                continue
            p, n = h
            t = Vector((1.0, 0.0, 0.0))
            s = n.cross(t).normalized()
            rim = bt.round_poly([(-66.0, -44.0), (66.0, -44.0), (66.0, 44.0), (-66.0, 44.0)], 14.0, 4)
            ring_o = [[p + t * (a * k) + s * (b_ * k) + n * c for a, b_ in rim] for k, c in ((1.0, -1.0), (1.0, 2.5), (0.86, 2.5), (0.86, -1.0))]
            bt.finish_smooth(hs.rings(f'kick_step_{sd}_{int(z)}', ring_o + [ring_o[0]], caps=False), CLAY)
            hs.finish(hs.rings(f'kick_step_door_{sd}_{int(z)}', [[p + t * (a * 0.86) + s * (b_ * 0.86) + n * c for a, b_ in rim] for c in (-3.0, 0.4)]), 0.0, DARK)
        for x, z in ((3420.0, 1330.0), (3040.0, 1420.0)):
            a_, b2 = on_side(x - 95.0, z, sgn), on_side(x + 95.0, z, sgn)
            if a_ and b2:
                holds.append(tube([a_[0] - a_[1] * 3.0, a_[0] + a_[1] * 46.0, b2[0] + b2[1] * 46.0, b2[0] - b2[1] * 3.0], 8.5, bend=22.0))
        if holds:
            hs.finish(hs.skins(f'handholds_{sd}', holds), 0.0, CLAY)
    # the left side only: the auxiliary unit's exhaust port, the rail aerial on its standoffs, the two dispensers
    h = on_side(3520.0, 1405.0, -1)
    if h:
        p, n = h
        hs.finish(hs.revolve('apu_exhaust_port', [(104.0, -40.0), (124.0, -40.0), (128.0, 8.0), (118.0, 20.0), (104.0, 20.0)], at=p, axis=n, seg=40, closed=True), 0.0, STEEL)
        hs.finish(hs.revolve('apu_exhaust_dark', [(0.0, -36.0), (104.0, -36.0), (104.0, -30.0), (0.0, -30.0)], at=p, axis=n, seg=32), 0.0, DARK)
    rail_pts, posts = [], []
    for x in stations(4750.0, 7550.0, 560.0):
        h = on_side(x, 0.62 * (D.HULL.ctrl(x)[0][0][1] + D.HULL.ctrl(x)[0][6][1]) + 60.0, -1)
        if h:
            rail_pts.append(h[0] + h[1] * 105.0)
            posts.append(tube([h[0] - h[1] * 2.0, h[0] + h[1] * 100.0], 9.0, seg=8))
            posts.append([hs.circle(h[0], h[1], 22.0, -1.0, 12), hs.circle(h[0], h[1], 22.0, 5.0, 12)])
    if len(rail_pts) > 2:
        posts.append(tube([rail_pts[0] + Vector((-120.0, 0, 0))] + rail_pts + [rail_pts[-1] + Vector((120.0, 0, 0))], 11.0, seg=10))
        hs.finish(hs.skins('rail_aerial', posts), 0.0, CLAY)
    for i, x in enumerate((4250.0, 4850.0)):
        h = on_side(x, 640.0, -1)
        if h:
            p, n = h
            t = Vector((1.0, 0.0, 0.0))
            s = n.cross(t).normalized()
            box_ = bt.round_poly([(-120.0, -95.0), (120.0, -95.0), (120.0, 95.0), (-120.0, 95.0)], 16.0, 4)
            bt.finish_smooth(hs.rings(f'dispenser_{i}', [[p + t * a + s * b_ + n * c for a, b_ in box_] for c in (-4.0, 150.0)]), CLAY, sharp_deg=35.0)
            hs.finish(hs.rings(f'dispenser_face_{i}', [[p + t * (a * 0.84) + s * (b_ * 0.84) + n * c for a, b_ in box_] for c in (150.0, 154.0)]), 0.0, DARK)
