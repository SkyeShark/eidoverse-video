"""eidoblend.props.helicopter.top: what stands on the roof.

    the spine      one long fairing on the centre line: it rises out of the cockpit's roof behind the overhead panes
                   (the cover over the flight controls: broad, flat-topped, soft-shouldered), swells into the gearbox
                   fairing round the mast (top at 2250), and falls away aft between the exhausts to the drive shaft's
                   cover on the boom; the mast's boot on it
    the engines    two cowlings beside the gearbox, their centres 845 from the centre line: round at the intake, a
                   rounded box behind it; each intake a thick rolled lip, a dark throat, the bullet and its struts
    the exhausts   behind each cowling the duct turns up and out, open at its end, under a shield: a shallow tray turned
                   over the duct, its edges turned down all round, running aft to a point
    the shaft's cover  a half-round cover along the boom's top in four lengths, a raised band at each joint
Leaves b.spine: the spine's Body (fit.py stands its aerial on it).
"""

from __future__ import annotations

import math

from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from ..hardsurface.sections import Body, stations
from . import datum as D


def _spine_key(x, wb, wt, zt, r, zb=1460.0, crown=14.0):
    # K0 buried in the roof, K1 its foot (buried), K2 its shoulder, K3 its crown      (x, [(y, z) x 4], [R1, R2])
    return (x, [(0, zb), (wb, zb), (wt, zt), (0, zt + crown)], [0.0, r])


SPINE = Body([
    _spine_key(-2650, 240, 110, 1492, 30, crown=4.0),
    _spine_key(-2560, 430, 250, 1590, 80),
    _spine_key(-2400, 530, 340, 1688, 130),
    _spine_key(-2000, 600, 400, 1800, 170),
    _spine_key(-1500, 640, 420, 1900, 190),
    _spine_key(-1000, 650, 430, 1990, 200),
    _spine_key(-650, 650, 440, 2052, 200),
    _spine_key(-300, 620, 440, 2175, 180),
    _spine_key(0, 600, 440, 2240, 180),
    _spine_key(600, 600, 440, 2245, 180),
    _spine_key(1300, 590, 420, 2230, 180),
    _spine_key(1700, 560, 380, 2190, 170),
    _spine_key(2300, 520, 330, 2075, 160),
    _spine_key(3000, 430, 250, 1885, 150),
    _spine_key(3650, 330, 170, 1675, 120, zb=1400.0),
    _spine_key(4230, 200, 100, 1462, 80, zb=1280.0, crown=8.0),
    _spine_key(4420, 150, 92, 1372, 70, zb=1240.0, crown=6.0),
], [4, 10, 8], [2, 14])
EY, EZ = 845.0, 1865.0                                        # an engine's centre line


def _nac_key(x, w, zb, zt, rb, rt):
    return (x, [(0, zb), (w, zb), (w, zt), (0, zt)], [rb, rt])


NACELLE = Body([
    _nac_key(-575, 268, 1597, 2133, 262, 262),              # round behind the intake's lip
    _nac_key(-430, 282, 1572, 2158, 250, 260),
    _nac_key(-150, 292, 1550, 2180, 190, 250),
    _nac_key(300, 295, 1545, 2186, 150, 240),
    _nac_key(1300, 295, 1545, 2186, 150, 240),
    _nac_key(1650, 288, 1558, 2172, 160, 240),
], [6, 8, 6], [12, 12])
EXHAUST = Body([
    _nac_key(1650, 288, 1558, 2172, 160, 240),
    _nac_key(1950, 280, 1575, 2150, 160, 230),
    _nac_key(2300, 262, 1612, 2105, 150, 200),
    _nac_key(2620, 240, 1660, 2060, 140, 170),
], [6, 8, 6], [12, 12])


def offset(o, dy):
    for v in o.data.vertices:
        v.co.y += dy * hs.MM
    return o


def build(b):
    CLAY, DARK = b.clay, b.dark
    b.spine = SPINE
    bt.finish_smooth(bt.loft_body('spine_fairing', SPINE, stations(-2650.0, 4420.0, 70.0, [-650.0, 0.0, 1300.0])), CLAY)
    # the mast's boot on the gearbox fairing: a low ring the mast comes up through
    hs.finish(hs.revolve('mast_boot', [(0.0, 2225.0), (255.0, 2225.0), (255.0, 2262.0), (238.0, 2284.0), (150.0, 2296.0), (0.0, 2296.0)],
                         at=(0.0, 0.0, 0.0), seg=64), 0.0, CLAY)
    for sgn, sd in ((1, 'r'), (-1, 'l')):
        yc = sgn * EY
        nac = offset(bt.loft_body(f'nacelle_{sd}', NACELLE, stations(-575.0, 1650.0, 60.0, [-150.0, 300.0, 1300.0])), yc)
        bt.finish_smooth(nac, CLAY)
        # the intake: a rolled lip (a closed profile turned about the engine's line), the dark throat, the bullet, three struts
        at = Vector((-575.0, yc, EZ))
        fwd = (-1.0, 0.0, 0.0)
        lip = [(268.0, -30.0), (272.0, 10.0), (262.0, 42.0), (240.0, 58.0), (214.0, 52.0), (200.0, 30.0), (196.0, -10.0), (196.0, -260.0),
               (206.0, -260.0), (210.0, -40.0)]
        hs.finish(hs.revolve(f'intake_lip_{sd}', lip, at=at, axis=fwd, seg=56, closed=True), 0.0, CLAY)
        hs.finish(hs.revolve(f'intake_throat_{sd}', [(0.0, -250.0), (200.0, -250.0), (200.0, -262.0), (0.0, -262.0)], at=at, axis=fwd, seg=40), 0.0, DARK)
        hs.finish(hs.revolve(f'intake_bullet_{sd}', [(0.0, -40.0), (24.0, -52.0), (52.0, -90.0), (70.0, -150.0), (76.0, -252.0), (0.0, -252.0)],
                             at=at, axis=fwd, seg=32), 0.0, CLAY)
        sk = []
        for k in range(3):
            a = math.radians(90.0 + 120.0 * k)
            rad = Vector((0.0, math.cos(a), math.sin(a)))
            sk.append([[at + Vector((1.0, 0.0, 0.0)) * (160.0 + dx) + rad * r_ + rad.cross(Vector((1.0, 0.0, 0.0))) * dt
                        for dx, dt in ((0, -9), (50, -11), (95, 0), (50, 11), (0, 9), (-14, 0))] for r_ in (60.0, 204.0)])
        hs.finish(hs.skins(f'intake_struts_{sd}', sk), 0.0, CLAY)
        # the exhaust: its duct narrowing aft and turned out a little, open at its end; the shield over it
        ex = bt.loft_body(f'exhaust_duct_{sd}', EXHAUST, stations(1650.0, 2620.0, 60.0))
        core = bt.loft_body(f'exhaust_core_{sd}', Body([_nac_key(x, w - 14, zb + 14, zt - 14, rb, rt) for x, w, zb, zt, rb, rt in
                                                        ((2100, 268, 1590, 2130, 150, 215), (2300, 262, 1612, 2105, 150, 200),
                                                         (2700, 236, 1668, 2052, 140, 170))], [6, 8, 6], [12, 12]),
                            stations(2100.0, 2700.0, 60.0))
        ex = hs.boolean(ex, core, 'DIFFERENCE')
        offset(ex, yc)
        for v in ex.data.vertices:                            # turned outboard 7 degrees about its front end
            dx = v.co.x - 1.650
            v.co.y += sgn * dx * math.tan(math.radians(7.0))
        bt.finish_smooth(ex, CLAY)
        plate = [(1840, -305), (2500, -335), (3460, -150), (3470, -40), (3060, 292), (1840, 322)]
        cx_, cy_ = sum(p[0] for p in plate) / 6.0, sum(p[1] for p in plate) / 6.0
        inner = [(x - 9.0 * (1 if x > cx_ else -1), y - 9.0 * (1 if y > cy_ else -1)) for x, y in plate]
        pl = hs.prism_plan(f'exhaust_shield_{sd}', [(x, yc + sgn * y) for x, y in plate], 2118.0, 2182.0)
        pl = hs.boolean(pl, hs.prism_plan(f'exhaust_shield_in_{sd}', [(x, yc + sgn * y) for x, y in inner], 2100.0, 2175.0), 'DIFFERENCE')
        hs.finish(pl, 3.0, CLAY)
    # the drive shaft's cover along the boom
    half_round = [(95.0 * math.cos(math.radians(a)), 95.0 * math.sin(math.radians(a))) for a in range(-25, 206, 11)]
    joints = [4440.0, 5400.0, 6360.0, 7320.0, 8230.0]
    for i, (x0, x1) in enumerate(zip(joints, joints[1:])):
        path = [Vector((x, 0.0, D.HULL.ctrl(x)[0][6][1] - 22.0)) for x in stations(x0 + 6.0, x1 - 6.0, 120.0)]
        bt.finish_smooth(hs.sweep(f'shaft_cover_{i}', path, [(-u, v) for u, v in half_round], up=(0.0, 0.0, 1.0)), CLAY)
    bands = []
    band = [(101.0 * math.cos(math.radians(a)), 101.0 * math.sin(math.radians(a))) for a in range(-25, 206, 11)]
    for x in joints:
        z = D.HULL.ctrl(x)[0][6][1] - 22.0
        bands.append([[Vector((x + dx, -u, z + v)) for u, v in band] for dx in (-16.0, 16.0)])
    hs.finish(hs.skins('shaft_cover_bands', bands), 0.0, CLAY)
