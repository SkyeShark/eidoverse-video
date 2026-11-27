"""eidoblend.props.helicopter.rotor: the main rotor.

    standing still   the bright steel guide the swashplate slides on, the stationary swashplate, three servo rods up to it
                     from the gearbox, the stationary scissors
    turning          (under the Empty 'main_rotor', which turns about its local Z: the mast, leaning 3 degrees forward
                     under 'mast_tilt') the rotating swashplate and its scissors; four pitch links up to four pitch horns;
                     the hub (a barrel and four arms, each housing an elastomeric bearing); out of each arm a spindle, its
                     horn, the blade's cuff (two plates, two pins); a damper beside each spindle; the bifilar absorber on
                     top (a cross of four arms, a pair of weights on each); the cap over the slip ring
    the blades       four, 8.18 m to the tip, 0.53 m chord, a thin cambered section, twisted 18 degrees, the last 0.5 m swept
                     back 20 degrees, tapered and turned down; coned up 3.5 degrees as they fly; each carries the colour
                     attribute 'blade' (chord, span) for its material
Its own frame: the hub's centre (0, 0, 2800), z along the mast.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from . import datum as D

TILT = math.radians(D.MAST_TILT)
R_O = Vector((0.0, 0.0, D.HUB_Z))
R_Z = Vector((-math.sin(TILT), 0.0, math.cos(TILT)))
R_X = Vector((math.cos(TILT), 0.0, math.sin(TILT)))
R_Y = Vector((0.0, 1.0, 0.0))
PSI = [math.radians(90.0 * k + 20.0) for k in range(4)]
R_TIP, CHORD, CONE, HINGE = 8180.0, 530.0, math.radians(3.5), 380.0


def RW(x, y, z):
    return R_O + R_X * x + R_Y * y + R_Z * z


def BP(k, r, t=0.0, z=0.0, lead=0.0):
    """a point of blade k's own frame: r out along it, t toward its leading edge, z up the mast; lead: degrees ahead"""
    a = PSI[k] + math.radians(lead)
    return RW(r * math.cos(a) - t * math.sin(a), r * math.sin(a) + t * math.cos(a), z)


def rod(a, b, r, seg=10):
    a, b = Vector(a), Vector(b)
    return [hs.circle(a, b - a, r, 0.0, seg), hs.circle(a, b - a, r, (b - a).length, seg)]


def bar(a, b, w, h, up):
    """a flat bar from a to b, w across, h along `up`"""
    a, b, up = Vector(a), Vector(b), Vector(up).normalized()
    s = (b - a).cross(up).normalized()
    return [[p + s * (w / 2 * i) + up * (h / 2 * j) for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))] for p in (a, b)]


def ball(c, r, seg=10):
    c = Vector(c)
    return [[c + Vector((r * math.sin(math.pi * j / 6) * math.cos(2 * math.pi * i / seg), r * math.sin(math.pi * j / 6) * math.sin(2 * math.pi * i / seg),
                         r * math.cos(math.pi * j / 6))) for i in range(seg)] for j in range(1, 6)]


def blade_ring(k, r_, n=13):
    f = (r_ - 1130.0) / 150.0
    grow = min(1.0, max(0.0, f))
    grow = grow * grow * (3.0 - 2.0 * grow)
    c = 300.0 + (CHORD - 300.0) * grow
    th = 0.20 + (0.095 - 0.20) * grow                         # thick at the cuff, 9.5 per cent beyond
    sweep = drop = 0.0
    if r_ > 7650.0:                                           # the tip: swept back 20 degrees, tapered, turned down
        u = (r_ - 7650.0) / (R_TIP - 7650.0)
        sweep = (r_ - 7650.0) * math.tan(math.radians(20.0))
        c *= 1.0 - 0.4 * u
        drop = max(0.0, r_ - 7850.0) * math.tan(math.radians(12.0))
    tw = math.radians(13.0 - 18.0 * r_ / R_TIP)
    zc = max(0.0, r_ - HINGE) * math.tan(CONE) - drop
    ring = []
    for i in range(2 * n):
        s = 0.5 * (1.0 - math.cos(math.pi * (i if i <= n else 2 * n - i) / n))
        yt = th * c * 5.0 * (0.2969 * math.sqrt(s) - 0.1260 * s - 0.3516 * s * s + 0.2843 * s ** 3 - 0.1036 * s ** 4)
        camber = 0.012 * c * 4.0 * s * (1.0 - s)
        t0 = (0.25 - s) * c - sweep
        z0 = camber + (yt if i <= n else -yt)
        ring.append(BP(k, r_, t0 * math.cos(tw) - z0 * math.sin(tw), zc + t0 * math.sin(tw) + z0 * math.cos(tw)))
    return ring


def build(b):
    CLAY, DARK, STEEL = b.clay, b.dark, b.steel
    tilt = hs.empty('mast_tilt', R_O)
    tilt.rotation_euler = (0.0, -TILT, 0.0)
    bpy.context.view_layer.update()
    mrh = hs.empty('main_rotor', R_O)
    mrh.parent = tilt
    mrh.matrix_parent_inverse = tilt.matrix_world.inverted()
    mrh.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    def r_revolve(name, profile, m, seg=48, parent=None, closed=False):
        """a profile [(radius, height up the mast from the hub)] turned about the mast"""
        return hs.finish(hs.revolve(name, profile, at=R_O, axis=R_Z, seg=seg, start=R_X, closed=closed), 0.0, m, parent=parent)

    # ---------------------------------------------------------------- standing still
    r_revolve('mast_guide', [(0.0, -548.0), (150.0, -548.0), (150.0, -528.0), (118.0, -512.0), (99.0, -498.0), (99.0, -262.0), (112.0, -255.0),
                             (112.0, -240.0), (0.0, -240.0)], STEEL, seg=56)
    r_revolve('swashplate_stationary', [(120.0, -238.0), (236.0, -238.0), (252.0, -228.0), (252.0, -198.0), (236.0, -188.0), (120.0, -188.0)],
              CLAY, seg=64, closed=True)
    sk, lugs = [], []
    for a_deg in (0.0, 120.0, 240.0):
        a = math.radians(a_deg)
        e = lambda r_, z, a=a: RW(r_ * math.cos(a), r_ * math.sin(a), z)       # noqa: E731
        lugs.append(bar(e(238.0, -213.0), e(300.0, -213.0), 56.0, 44.0, R_Z))
        sk.append(rod(e(272.0, -548.0), e(272.0, -395.0), 34.0, 14))             # the servo's cylinder, its rod, its rod end
        sk.append(rod(e(272.0, -395.0), e(272.0, -232.0), 14.0, 10))
        sk.append(ball(e(272.0, -213.0), 24.0))
    hs.finish(hs.skins('swashplate_lugs', lugs), 2.0, CLAY)
    hs.finish(hs.skins('servo_rods', sk), 0.0, STEEL)
    e = lambda r_, z: RW(-r_, 0.0, z)                                            # noqa: E731  (the stationary scissors, aft)
    hs.finish(hs.skins('scissors_stationary', [bar(e(150.0, -520.0), e(330.0, -400.0), 46.0, 20.0, R_Y.cross(R_X)),
                                               bar(e(330.0, -400.0), e(250.0, -216.0), 40.0, 18.0, R_Y.cross(R_X))]), 1.5, CLAY)

    # ---------------------------------------------------------------- turning
    r_revolve('swashplate_rotating', [(126.0, -186.0), (262.0, -186.0), (286.0, -174.0), (286.0, -150.0), (262.0, -138.0), (126.0, -138.0)],
              CLAY, seg=64, parent=mrh, closed=True)
    r_revolve('rotor_shaft', [(0.0, -242.0), (74.0, -242.0), (74.0, -128.0), (96.0, -118.0), (96.0, -96.0), (0.0, -96.0)], DARK, seg=40, parent=mrh)
    r_revolve('hub_barrel', [(0.0, -96.0), (150.0, -96.0), (186.0, -82.0), (198.0, -44.0), (198.0, 44.0), (186.0, 82.0), (150.0, 96.0), (0.0, 96.0)],
              CLAY, seg=56, parent=mrh)
    r_revolve('slip_ring_cap', [(0.0, 150.0), (150.0, 150.0), (166.0, 176.0), (146.0, 216.0), (86.0, 240.0), (0.0, 247.0)], CLAY, seg=40, parent=mrh)
    arm_sec = bt.round_poly([(-128.0, -104.0), (128.0, -104.0), (128.0, 104.0), (-128.0, 104.0)], 46.0, 5)
    swl, links, horns, dampers, pins, weights, sciss = [], [], [], [], [], [], []
    for k in range(4):
        # the hub's arm: a housing with turned corners out to the bearing's cover
        arm = [[BP(k, r_, t * sc, z * sc) for t, z in arm_sec] for r_, sc in ((120.0, 1.0), (430.0, 1.0), (456.0, 1.06), (486.0, 1.06), (500.0, 0.9))]
        bt.finish_smooth(hs.rings(f'hub_arm_{k}', arm), CLAY, parent=mrh, sharp_deg=32.0)
        # the spindle: turned about the blade's own line
        prof = [(430.0, 70.0), (520.0, 86.0), (556.0, 86.0), (590.0, 68.0), (790.0, 60.0), (830.0, 80.0), (905.0, 80.0)]
        sp = [[BP(k, r_, rad * math.cos(2 * math.pi * i / 24), rad * math.sin(2 * math.pi * i / 24)) for i in range(24)] for r_, rad in prof]
        bt.finish_smooth(hs.rings(f'spindle_{k}', sp), STEEL, parent=mrh, sharp_deg=32.0)
        # the cuff: two plates gripping the blade's root, and the two pins through them
        for sz, nm in ((1, 'upper'), (-1, 'lower')):
            pl = [[BP(k, r_, t, sz * z) for t, z in ((-hw, 30.0), (hw, 30.0), (hw, 58.0), (-hw, 58.0))] for r_, hw in ((870.0, 96.0), (960.0, 150.0), (1150.0, 168.0))]
            hs.finish(hs.rings(f'cuff_{nm}_{k}', pl), 5.0, CLAY, parent=mrh)
        for t in (-86.0, 86.0):
            pins.append([hs.circle(BP(k, 1050.0, t, -82.0), R_Z, 31.0, 0.0, 16), hs.circle(BP(k, 1050.0, t, -82.0), R_Z, 31.0, 164.0, 16)])
        # the pitch horn, out ahead of the spindle; its link down to the rotating swashplate, a lug there
        h0, h1 = BP(k, 560.0, 60.0, -10.0), BP(k, 352.0, 262.0, -34.0)
        horns.append(bar(h0, h1, 62.0, 44.0, R_Z))
        lug = BP(k, 304.0, 0.0, -162.0, lead=40.0)
        swl.append(bar(BP(k, 262.0, 0.0, -162.0, lead=40.0), BP(k, 330.0, 0.0, -162.0, lead=40.0), 60.0, 40.0, R_Z))
        links.append(rod(lug + R_Z * 14.0, h1 - R_Z * 30.0, 17.0, 12))
        links.append(ball(lug, 27.0))
        links.append(ball(h1 - R_Z * 6.0, 27.0))
        # the damper beside the spindle, on its trailing side
        d0, d1 = BP(k, 236.0, -196.0, 26.0), BP(k, 772.0, -150.0, 26.0)
        dampers.append(rod(d0, d0.lerp(d1, 0.62), 42.0, 16))
        dampers.append(rod(d0.lerp(d1, 0.62), d1, 21.0, 12))
        dampers.append(ball(d0, 34.0))
        dampers.append(ball(d1, 34.0))
        horns.append(bar(BP(k, 760.0, -40.0, 26.0), BP(k, 772.0, -165.0, 26.0), 56.0, 40.0, R_Z))          # the spindle's lug for it
        # the bifilar's arm between two blades, a pair of weights at its end
        b0, b1 = BP(k, 70.0, 0.0, 124.0, lead=45.0), BP(k, 436.0, 0.0, 124.0, lead=45.0)
        weights.append(bar(b0, b1, 118.0, 26.0, R_Z))
        for dz in (-58.0, 14.0):
            w0 = BP(k, 384.0, 0.0, 124.0 + dz, lead=45.0)
            weights.append([hs.circle(w0, R_Z, 60.0, 0.0, 20), hs.circle(w0, R_Z, 60.0, 44.0, 20)])
    hs.finish(hs.skins('swashplate_rotating_lugs', swl), 2.0, CLAY, parent=mrh)
    hs.finish(hs.skins('pitch_links', links), 0.0, STEEL, parent=mrh)
    hs.finish(hs.skins('pitch_horns', horns), 4.0, CLAY, parent=mrh)
    hs.finish(hs.skins('dampers', dampers), 0.0, CLAY, parent=mrh)
    hs.finish(hs.skins('blade_pins', pins), 2.0, STEEL, parent=mrh)
    hs.finish(hs.skins('bifilar', weights), 3.0, CLAY, parent=mrh)
    for s in (1, -1):                                         # the rotating scissors, a pair
        e = lambda r_, z, s=s: RW(0.0, s * r_, z)            # noqa: E731
        sciss.append(bar(e(96.0, -108.0), e(214.0, -112.0), 44.0, 18.0, R_Z))
        sciss.append(bar(e(214.0, -112.0), e(206.0, -160.0), 44.0, 18.0, R_Y))
    hs.finish(hs.skins('scissors_rotating', sciss), 1.5, CLAY, parent=mrh)

    # ---------------------------------------------------------------- the blades
    rs = [1130.0, 1160.0, 1200.0, 1240.0, 1280.0] + [1280.0 + (7650.0 - 1280.0) * q / 30 for q in range(1, 31)] + [7650.0 + (R_TIP - 7650.0) * q / 10 for q in range(1, 11)]
    for k in range(4):
        bl = hs.rings(f'main_blade_{k}', [blade_ring(k, r_) for r_ in rs])
        bt.blade_data(bl, 26, lambda i: 0.5 * (1.0 - math.cos(math.pi * (i if i <= 13 else 26 - i) / 13)),
                      lambda j: (rs[min(j, len(rs) - 1)] - rs[0]) / (R_TIP - rs[0]))
        bt.finish_smooth(bl, CLAY, parent=mrh)
