"""eidoblend.sets.same_seed.lab.furniture: the lab's furniture and what lies on it (Blender): a standing-height bench and
its drawer pedestal, a screen, keyboard and mouse, the small computer and the power strip they hang on, two mugs, a
clipboard and its pen, the whiteboard, and a task chair left turned toward the room's middle. Millimetres, the room's own
space.

Each piece is real construction: sections with their thickness, parts that meet as they are joined, a load path to the
floor, a cable from every thing that needs one. The bench: a 30 mm top on a welded frame of 50 x 50 tube, six legs on
levelling feet, rails under the top, low stretchers at the ends and along the back. The pedestal: a steel drawer unit on
four twin-wheel castors, three overlay fronts with bow handles, a lock. The screen: a 27 inch panel leaning back 5
degrees on a flat neck and foot. The keyboard: a wedge of a case with every key a cap on the 19.05 mm pitch. The mugs:
thrown and glazed, a handle luted on, the drink its own body. The clipboard: hardboard with a pressed-steel clip, a few
sheets, the top one not quite square and lifting at a corner; a stick pen across it. The whiteboard: enamelled steel in
an aluminium frame, a tray with four markers and an eraser, a sheet under two magnets. The chair: a polished five-star
base on castors, the gas column, the mechanism and its paddle, a moulded seat shell with a piped cushion, the back's
upright, a padded back in its shell.
"""

import math

import bmesh
from mathutils import Vector

from ....props.hardsurface import masses as hs
from . import kit as K

V3 = K.V3
ZUP = V3(0, 0, 1)
X1 = 4000.0                                                     # the right wall's face (the whiteboard hangs on it)
BX0, BX1, BY0, BY1, BTOP = 300.0, 2900.0, 800.0, 1600.0, 900.0  # the bench's top: what things are set down on
FBX, FBY = 2000.0, 1440.0                                      # the floor box (shell.py)


def tube_rings(a, b, w, h, r, up):
    """a hollow section seen from outside, as two rings: h along `up`, w across"""
    a, b = Vector(a), Vector(b)
    t = (b - a).normalized()
    v = (Vector(up) - t * Vector(up).dot(t)).normalized()
    u = v.cross(t)
    return [[p + u * s + v * q for s, q in hs.rrect(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0, r, n=3)] for p in (a, b)]


def turned(profile, at, axis=(0, 0, 1), seg=24, start=None):
    """the rings of a profile [(radius, height)] turned about an axis: one closed skin for hs.skins"""
    return [hs.circle(at, axis, max(r, 1e-4), h, seg, start) for r, h in profile]


def cable(pts, r, seg=10, step=7.0):
    return K.limb_rings(K.resample(K.spline(pts, 10), step), r, seg=seg)


def castor_skins(at, yaw, d=50.0, top=62.0):
    """a twin-wheel hooded castor: its swivel axis stands at `at`, its wheels trail the way `yaw` (degrees) by a third
    of their diameter: two wheels on one axle, a web between them up to the swivel, a hood over both, the stem up into
    what it carries"""
    at = Vector((at[0], at[1], 0.0))
    ef = V3(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.0)
    es = V3(-ef.y, ef.x, 0.0)
    A = at - ef * (0.36 * d) + ZUP * (d / 2.0)
    ww, gap = 0.2 * d, 0.16 * d
    sk = []
    for sg in (-1.0, 1.0):                                      # the wheels: a rounded tread, a dished face
        sk.append(turned([(0.0, 0.0), (d * 0.3, 0.0), (d * 0.34, 1.2), (d / 2.0 - 2.0, 1.2), (d / 2.0, 3.0), (d / 2.0, ww - 2.0), (d / 2.0 - 2.0, ww), (0.0, ww)],
                         A + es * (sg * gap / 2.0), es * sg, 28))

    def side(poly, hw):
        return [[A + ef * f + ZUP * z + es * s for f, z in poly] for s in (-hw, hw)]
    R0, R1 = d / 2.0 + 1.2, d / 2.0 + 3.6
    arc = [math.radians(a) for a in range(-20, 201, 13)]
    sk.append(side([(R1 * math.cos(a), R1 * math.sin(a)) for a in arc] + [(R0 * math.cos(a), R0 * math.sin(a)) for a in arc[::-1]], gap / 2.0 + ww + 1.2))
    sk.append(side([(-0.22 * d, -0.2 * d), (0.22 * d, -0.2 * d), (0.52 * d, 0.3 * d), (0.52 * d, 0.56 * d), (0.2 * d, 0.56 * d), (-0.24 * d, 0.3 * d)], gap / 2.0 - 0.6))
    sk.append(turned([(0.0, d * 0.98), (d * 0.24, d * 0.98), (d * 0.24, top - 1.5), (d * 0.2, top), (0.0, top)], at, (0, 0, 1), 20))
    sk.append(turned([(0.0, top - 2.0), (5.5, top - 2.0), (5.5, top + 20.0), (0.0, top + 20.0)], at, (0, 0, 1), 12))
    return sk


def place(parts, yaw, at, about=(0.0, 0.0, 0.0)):
    """things built round their own origin, turned (degrees about z) and set where they stand"""
    for o_ in parts:
        K.turn(o_, about, (0, 0, 1), yaw)
        K.move(o_, at)
    return parts


def polar_xy(deg):
    return V3(math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0)


def seat_ring(z, sc, front=0.0):
    """the chair seat's plan (a rounded square 480 x 470) at a height, scaled; front: how far its front edge is let down"""
    out = []
    for i in range(48):
        a = 2.0 * math.pi * i / 48.0
        c, s = math.cos(a), math.sin(a)
        x, y = 240.0 * sc * math.copysign(abs(c) ** 0.62, c), 235.0 * sc * math.copysign(abs(s) ** 0.62, s)
        out.append(V3(x, y - 8.0, z - front * K.smooth(-y, 110.0, 235.0) ** 2))
    return out


def back_ring(z, sc, half, y_off, wide=220.0):
    """the chair back's section at a height: it wraps the sitter (its sides come forward), leans back 9 degrees, and
    swells forward at the small of the back"""
    y0 = 236.0 + (z - 545.0) * math.tan(math.radians(9.0)) - 15.0 * math.exp(-((z - 665.0) / 95.0) ** 2) + y_off
    out = []
    for i in range(44):
        a = 2.0 * math.pi * i / 44.0
        c, s = math.cos(a), math.sin(a)
        x = wide * sc * math.copysign(abs(c) ** 0.5, c)
        out.append(V3(x, y0 + half * math.copysign(abs(s) ** 0.75, s) - 40.0 * (x / wide) ** 2, z))
    return out


def build(hs_, K_, CLAY, DARK, chair_at=(1200.0, -750.0), chair_yaw=-140.0):
    """every piece into hs.col. chair_at / chair_yaw: where the chair stands (mm) and how it is turned (degrees)"""
    # ------------------------------------------------------------------------------------------------- the bench
    # a standing-height workbench: a 30 mm top on a welded frame of 50 x 50 tube: six legs on levelling feet, rails
    # under the top all round, low stretchers at the ends and along the back (the front left open for feet)
    hs.finish(hs.box('bench_top', (BX0, BY0, BTOP - 30.0), (BX1, BY1, BTOP)), 3.0, CLAY)
    LEGX, LEGY, ZT = (BX0 + 65.0, (BX0 + BX1) / 2.0, BX1 - 65.0), (BY0 + 75.0, BY1 - 75.0), BTOP - 30.0
    legs, rails, low, feet = [], [], [], []
    for x in LEGX:
        for y in LEGY:
            legs.append(tube_rings((x, y, 38.0), (x, y, ZT), 50.0, 50.0, 5.0, (0, 1, 0)))
            feet.append(turned([(0.0, 0.0), (22.0, 0.0), (23.0, 1.5), (23.0, 6.0), (20.0, 8.0), (6.0, 8.0), (6.0, 40.0), (0.0, 40.0)], (x, y, 0.0), seg=28))
            feet.append(turned([(0.0, 26.0), (9.5, 26.0), (9.5, 34.0), (0.0, 34.0)], (x, y, 0.0), seg=6))        # the jam nut under the leg
        rails.append(tube_rings((x, LEGY[0] + 25.0, ZT - 15.0), (x, LEGY[1] - 25.0, ZT - 15.0), 50.0, 30.0, 4.0, (0, 0, 1)))
        low.append(tube_rings((x, LEGY[0] + 25.0, 160.0), (x, LEGY[1] - 25.0, 160.0), 40.0, 40.0, 4.0, (0, 0, 1)))
    for xa, xb in zip(LEGX, LEGX[1:]):
        for y in LEGY:
            rails.append(tube_rings((xa + 25.0, y, ZT - 15.0), (xb - 25.0, y, ZT - 15.0), 50.0, 30.0, 4.0, (0, 0, 1)))
        low.append(tube_rings((xa + 25.0, LEGY[1], 160.0), (xb - 25.0, LEGY[1], 160.0), 40.0, 40.0, 4.0, (0, 0, 1)))
    hs.finish(hs.skins('bench_legs', legs), 0.0, CLAY)
    hs.finish(hs.skins('bench_rails', rails), 0.0, CLAY)
    hs.finish(hs.skins('bench_stretchers', low), 0.0, CLAY)
    hs.finish(hs.skins('bench_feet', feet), 0.0, CLAY)
    # the pedestal under its right end: a steel drawer unit on four castors: a body, three overlay fronts with a 3 mm gap
    # between them, a bow handle on each, a lock in the top one, a cap on top (it stands clear in front of the back
    # stretcher, y 1505)
    PX0, PX1, PY0, PY1, PZ0, PZ1 = 2330.0, 2750.0, 940.0, 1495.0, 62.0, 562.0
    hs.finish(hs.box('pedestal_body', (PX0, PY0 + 18.0, PZ0), (PX1, PY1, PZ1)), 2.0, CLAY)
    hs.finish(hs.box('pedestal_cap', (PX0 - 2.5, PY0, PZ1), (PX1 + 2.5, PY1 + 2.5, PZ1 + 12.0)), 3.0, CLAY)
    fronts, handles = [], []
    for z0, z1 in ((PZ0 + 3.0, PZ0 + 223.0), (PZ0 + 226.0, PZ0 + 360.0), (PZ0 + 363.0, PZ0 + 497.0)):
        fronts.append(((PX0 + 2.0, PY0, z0), (PX1 - 2.0, PY0 + 18.0, z1)))
        zc, xc = z1 - 34.0, (PX0 + PX1) / 2.0
        handles.append(K.limb_rings(K.resample(hs.fillet_path([V3(xc - 64.0, PY0 + 3.0, zc), V3(xc - 64.0, PY0 - 24.0, zc), V3(xc + 64.0, PY0 - 24.0, zc),
                                                               V3(xc + 64.0, PY0 + 3.0, zc)], 9.0, n=6), 4.0), 4.0, seg=12))
    hs.finish(K.boxes('pedestal_fronts', fronts), 1.5, CLAY)
    hs.finish(hs.skins('pedestal_handles', handles), 0.0, CLAY)
    hs.finish(hs.skins('pedestal_lock', [turned([(0.0, -2.0), (9.5, -2.0), (9.5, 2.0), (8.5, 3.0), (0.0, 3.0)], (PX1 - 34.0, PY0, PZ0 + 470.0), (0, -1, 0), 24)]), 0.0, CLAY)
    sk = []
    for i, (x, y) in enumerate(((PX0 + 45.0, PY0 + 70.0), (PX1 - 45.0, PY0 + 70.0), (PX0 + 45.0, PY1 - 50.0), (PX1 - 45.0, PY1 - 50.0))):
        sk += castor_skins((x, y), (205.0, 160.0, 250.0, 118.0)[i], d=50.0, top=PZ0)
    hs.finish(hs.skins('pedestal_castors', sk), 0.6, CLAY)

    # ---------------------------------------------------------------------------- the screen, the computer, the power
    # a 27 inch screen on its stand: the panel housing with the display let 0.8 into its face, the electronics' bulge
    # behind, a hinge block, a flat neck leaning back to a flat foot. The panel leans back 5 degrees.
    SX, SYF, SZ0, SW, SH = 2200.0, 1378.0, BTOP + 112.0, 614.0, 366.0
    body = hs.prism_side('screen_body', hs.rrect(SX - SW / 2.0, SZ0, SX + SW / 2.0, SZ0 + SH, 6.0, n=5), SYF, SYF + 12.0)
    body = hs.boolean(body, hs.box('screen_pocket', (SX - SW / 2.0 + 8.0, SYF - 5.0, SZ0 + 22.0), (SX + SW / 2.0 - 8.0, SYF + 0.8, SZ0 + SH - 8.0)), 'DIFFERENCE')
    panel = [hs.finish(body, 0.8, CLAY),
             hs.finish(hs.box('screen_glass', (SX - SW / 2.0 + 8.2, SYF + 0.15, SZ0 + 22.2), (SX + SW / 2.0 - 8.2, SYF + 0.8, SZ0 + SH - 8.2)), 0.0, DARK),
             hs.finish(hs.prism_side('screen_back', hs.rrect(SX - 165.0, SZ0 + 70.0, SX + 165.0, SZ0 + 290.0, 26.0, n=6), SYF + 12.0, SYF + 42.0), 9.0, CLAY)]
    HINGE = (SX, SYF + 50.0, SZ0 + 180.0)
    for o_ in panel:
        K.turn(o_, HINGE, (1, 0, 0), -5.0)                     # (its head goes back, +y: a negative turn about +x)
    hs.finish(hs.box('screen_hinge', (SX - 36.0, SYF + 36.0, SZ0 + 138.0), (SX + 36.0, SYF + 66.0, SZ0 + 222.0)), 3.0, CLAY)
    hs.finish(hs.sweep('screen_neck', [V3(SX, SYF + 58.0, SZ0 + 150.0), V3(SX, SYF + 96.0, BTOP + 6.0)], hs.rrect(-35.0, -7.0, 35.0, 7.0, 4.0, n=3), up=(0, 1, 0)), 0.0, CLAY)
    hs.finish(hs.prism_plan('screen_foot', hs.rrect(SX - 125.0, SYF - 40.0, SX + 125.0, SYF + 160.0, 22.0, n=6), BTOP, BTOP + 9.0), 1.5, CLAY)
    # the computer it shows: a small box behind the screen's right, a rounded square with a power button
    CX0, CY0 = 2585.0, 1335.0
    hs.finish(hs.prism_plan('computer_case', hs.rrect(CX0, CY0, CX0 + 180.0, CY0 + 180.0, 16.0, n=6), BTOP + 2.0, BTOP + 38.0), 2.0, CLAY)
    hs.finish(hs.skins('computer_feet_and_button', [turned([(0.0, 0.0), (12.0, 0.0), (12.0, 2.5), (0.0, 2.5)], (CX0 + 30.0 + 120.0 * i, CY0 + 30.0 + 120.0 * j, BTOP), seg=16)
                                                    for i in (0, 1) for j in (0, 1)]
                       + [turned([(0.0, -0.5), (5.0, -0.5), (5.0, 1.2), (4.0, 1.8), (0.0, 1.8)], (CX0 + 150.0, CY0, BTOP + 20.0), (0, -1, 0), 16)]), 0.0, CLAY)
    # the power strip along the bench's back edge: five sockets (their wells cut once each), a rocker at one end
    PSX0, PSX1, PSY, PSZ = 1560.0, 1900.0, 1508.0, BTOP
    strip = hs.prism_section('power_strip', hs.rrect(PSY, PSZ, PSY + 58.0, PSZ + 40.0, 7.0, n=5), PSX0, PSX1)
    wells = []
    for i in range(5):
        xw = PSX0 + 64.0 + 56.0 * i
        strip = hs.boolean(strip, hs.cyl(f'well_{i}', (xw, PSY + 29.0, PSZ + 23.0), (xw, PSY + 29.0, PSZ + 60.0), 39.0, seg=40), 'DIFFERENCE')
        wells.append(turned([(0.0, 22.8), (18.5, 22.8), (18.5, 24.0), (0.0, 24.0)], (xw, PSY + 29.0, PSZ), seg=24))
    hs.finish(strip, 0.6, CLAY)
    hs.finish(hs.skins('power_strip_wells_dark', wells), 0.0, DARK)
    hs.finish(hs.box('power_strip_rocker', (PSX0 + 12.0, PSY + 18.0, PSZ + 39.0), (PSX0 + 34.0, PSY + 40.0, PSZ + 43.5)), 1.2, CLAY)
    # two plugs in it (the screen's, the computer's): a round body in its well, the cable leaving its back
    plugs = []
    for i in (1, 3):
        xw = PSX0 + 64.0 + 56.0 * i
        plugs.append(turned([(0.0, 25.0), (17.8, 25.0), (17.8, 46.0), (15.0, 52.0), (9.0, 56.0), (0.0, 56.0)], (xw, PSY + 29.0, PSZ), seg=28))
    hs.finish(hs.skins('power_plugs', plugs), 0.0, CLAY)
    # the cables, each from what needs it to what feeds it, lying on the bench the way a cable lies
    cab = [cable([V3(PSX0 + 120.0, PSY + 29.0, PSZ + 54.0), V3(PSX0 + 150.0, PSY + 60.0, PSZ + 40.0), V3(1900.0, PSY + 66.0, PSZ + 5.0), V3(2060.0, 1500.0, PSZ + 4.0),
                  V3(SX - 60.0, SYF + 60.0, PSZ + 30.0), V3(SX - 70.0, SYF + 36.0, SZ0 + 96.0)], 3.4),                    # the screen's power
           cable([V3(PSX0 + 232.0, PSY + 29.0, PSZ + 54.0), V3(PSX0 + 262.0, PSY + 62.0, PSZ + 36.0), V3(2100.0, 1578.0, PSZ + 4.0), V3(2480.0, 1570.0, PSZ + 4.0),
                  V3(CX0 + 60.0, CY0 + 200.0, PSZ + 12.0), V3(CX0 + 60.0, CY0 + 176.0, PSZ + 20.0)], 3.4),                # the computer's power
           cable([V3(SX + 60.0, SYF + 36.0, SZ0 + 96.0), V3(SX + 66.0, SYF + 70.0, PSZ + 40.0), V3(SX + 150.0, SYF + 150.0, PSZ + 4.5), V3(CX0 + 40.0, CY0 + 215.0, PSZ + 6.0),
                  V3(CX0 + 110.0, CY0 + 205.0, PSZ + 16.0), V3(CX0 + 110.0, CY0 + 176.0, PSZ + 20.0)], 3.0),              # the picture, screen to computer
           cable([V3(PSX1 - 4.0, PSY + 29.0, PSZ + 20.0), V3(PSX1 + 36.0, PSY + 46.0, PSZ + 5.0), V3(1955.0, 1596.0, PSZ + 4.5), V3(1966.0, 1604.6, PSZ - 2.0),
                  V3(1975.0, 1607.0, 860.0), V3(1990.0, 1612.0, 500.0), V3(1998.0, 1590.0, 110.0), V3(FBX, FBY + 92.0, 12.0), V3(FBX, FBY + 80.0, 6.0)], 3.8)]   # the strip's own lead, down to the floor box
    hs.finish(hs.skins('bench_cables', cab), 0.0, CLAY)

    # ----------------------------------------------------------------------------------------- keyboard, mouse
    # a full-size keyboard: a wedge of a case, its keys on the 19.05 mm pitch they are always on, every key a cap with
    # drafted sides
    KU, KX0, KY0, KW, KD = 19.05, 1951.0, 1007.0, 458.0, 136.0
    case = hs.prism_section('keyboard_case', [(KY0, BTOP), (KY0 + KD, BTOP), (KY0 + KD, BTOP + 19.0), (KY0 + KD - 5.0, BTOP + 21.5), (KY0 + 4.0, BTOP + 10.0), (KY0, BTOP + 7.0)],
                            KX0, KX0 + KW)
    case = hs.boolean(case, hs.prism_plan('keyboard_plan', hs.rrect(KX0, KY0, KX0 + KW, KY0 + KD, 9.0, n=5), BTOP - 5.0, BTOP + 40.0), 'INTERSECT')
    hs.finish(case, 1.0, CLAY)
    tilt = math.atan2(11.5, 127.0)
    KV, KN = V3(0.0, math.cos(tilt), math.sin(tilt)), V3(0.0, -math.sin(tilt), math.cos(tilt))
    KO = V3(KX0 + 10.0, KY0 + 4.0, BTOP + 10.0)                # the key field's front left corner, on the case's sloping top
    ROWS = (14.0, 33.05, 52.1, 71.15, 90.2, 116.85)             # the rows' middles, front to back: space, shift, home, qwerty, numbers, F keys
    keys = []

    def key(u0, row, wu=1.0, tall=1):
        """a key whose left edge is u0 units along, in a row; wu units wide; tall: it spans this row and the one behind"""
        x0, x1 = u0 * KU + 0.6, (u0 + wu) * KU - 0.6
        y0, y1 = ROWS[row] - 8.9, ROWS[row] + 8.9 + (KU if tall == 2 else 0.0)
        keys.append([[KO + V3(x, 0.0, 0.0) + KV * y + KN * w for x, y in ((x0 + i, y0 + f), (x1 - i, y0 + f), (x1 - i, y1 - b), (x0 + i, y1 - b))]
                     for w, i, f, b in ((0.8, 0.0, 0.0, 0.0), (2.6, 0.0, 0.0, 0.0), (8.2, 2.4, 1.6, 3.0))])

    def run(u0, row, widths):
        for w_ in widths:
            key(u0, row, w_)
            u0 += w_

    key(0.0, 5)
    for u0 in (2.0, 6.5, 11.0):
        run(u0, 5, (1.0,) * 4)
    run(0.0, 4, (1.0,) * 13 + (2.0,))
    run(0.0, 3, (1.5,) + (1.0,) * 12 + (1.5,))
    run(0.0, 2, (1.75,) + (1.0,) * 11 + (2.25,))
    run(0.0, 1, (2.25,) + (1.0,) * 10 + (2.75,))
    run(0.0, 0, (1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25))
    for r in (5, 4, 3):                                         # the block of nine above the arrows
        run(15.5, r, (1.0, 1.0, 1.0))
    key(16.5, 1)
    run(15.5, 0, (1.0, 1.0, 1.0))
    run(19.0, 4, (1.0, 1.0, 1.0, 1.0))                          # the number pad
    run(19.0, 3, (1.0, 1.0, 1.0))
    run(19.0, 2, (1.0, 1.0, 1.0))
    key(22.0, 2, tall=2)
    run(19.0, 1, (1.0, 1.0, 1.0))
    run(19.0, 0, (2.0, 1.0))
    key(22.0, 0, tall=2)
    hs.finish(hs.skins('keyboard_keys', keys), 0.5, CLAY)
    hs.finish(hs.skins('keyboard_cable', [cable([V3(KX0 + 229.0, KY0 + KD - 1.0, BTOP + 12.0), V3(KX0 + 232.0, KY0 + KD + 40.0, BTOP + 3.0), V3(2390.0, 1250.0, BTOP + 2.5),
                                                 V3(2560.0, 1290.0, BTOP + 2.5), V3(CX0 + 150.0, CY0 + 210.0, BTOP + 8.0), V3(CX0 + 150.0, CY0 + 176.0, BTOP + 14.0)], 2.0, seg=8)]),
              0.0, CLAY)
    # the mouse: one moulded back, flat beneath, a wheel in a slot cut once
    MX, MY = 2530.0, 1040.0
    rl = []
    for s, hw, ht in ((0.0, 10.0, 6.0), (0.03, 19.0, 13.0), (0.12, 27.0, 24.0), (0.3, 31.0, 36.0), (0.45, 31.0, 38.0), (0.62, 29.5, 33.0), (0.8, 28.0, 24.0), (0.93, 25.0, 16.0),
                      (0.985, 18.0, 10.0), (1.0, 9.0, 5.0)):
        y = MY + 112.0 * s
        ring = [V3(MX - hw * 0.86, y, BTOP + 0.2), V3(MX + hw * 0.86, y, BTOP + 0.2)]
        ring += [V3(MX + hw * math.cos(math.radians(a)), y, BTOP + 2.2 + (ht - 2.2) * math.sin(math.radians(a)) ** 0.85) for a in range(0, 181, 15)]
        rl.append(ring)
    mouse = hs.boolean(hs.rings('mouse_body', rl), hs.box('mouse_slot', (MX - 4.2, MY + 74.0, BTOP + 12.0), (MX + 4.2, MY + 100.0, BTOP + 60.0)), 'DIFFERENCE')
    K.soft(mouse, CLAY, sharp=50.0)
    hs.finish(hs.skins('mouse_wheel', [turned([(0.0, -3.4), (9.0, -3.4), (10.5, -2.0), (10.5, 2.0), (9.0, 3.4), (0.0, 3.4)], (MX, MY + 86.0, BTOP + 19.0), (1, 0, 0), 28)]), 0.0, CLAY)

    # ------------------------------------------------------------------------------------------------- two mugs
    # a straight white one with coffee left in it, a taller one with a tea bag's string over its rim (thrown and glazed:
    # a wall of 4 mm, a foot ring, the handle luted on: ONE mass; the drink is its own closed body, let a hair into the
    # wall)
    def mug(name, at, profile, handle, turn, drink):
        C = V3(at[0], at[1], BTOP)
        out = polar_xy(turn)
        body_ = hs.revolve(name, profile, at=C, seg=56)
        hp = K.resample(K.spline([C + out * r + ZUP * z for r, z in handle], 10), 3.0)
        body_ = hs.boolean(body_, hs.rings(name + '_handle', K.limb_rings(hp, 6.2, seg=14, up0=tuple(out), squash=0.68)), 'UNION')
        K.soft(body_, CLAY, sharp=50.0)
        K.soft(hs.revolve(name + '_drink', drink, at=C, seg=56), CLAY, sharp=50.0)
        return C, out

    mug('mug_a', (700.0, 1200.0), [(0.0, 4.0), (28.0, 4.0), (30.0, 0.0), (38.0, 0.0), (40.5, 3.0), (41.0, 8.0), (41.0, 92.0), (40.4, 95.0), (39.0, 96.0), (37.6, 95.0), (37.0, 92.0),
                                    (37.0, 9.0), (35.0, 7.0), (0.0, 7.0)], [(38.5, 76.0), (52.0, 80.0), (66.0, 68.0), (69.0, 50.0), (61.0, 31.0), (47.0, 22.0), (38.5, 24.0)], 215.0,
        [(0.0, 71.0), (33.0, 71.0), (36.3, 71.6), (37.2, 72.8), (37.2, 8.0), (0.0, 8.0)])
    C2, out2 = mug('mug_b', (950.0, 1050.0), [(0.0, 4.0), (22.0, 4.0), (24.0, 0.0), (31.0, 0.0), (34.0, 3.0), (36.0, 10.0), (41.0, 60.0), (43.0, 104.0), (42.4, 107.0), (41.0, 108.0),
                                               (39.6, 107.0), (39.0, 104.0), (37.0, 60.0), (32.0, 12.0), (29.0, 9.0), (0.0, 9.0)],
                   [(39.0, 86.0), (54.0, 92.0), (69.0, 80.0), (72.0, 58.0), (62.0, 36.0), (46.0, 26.0), (36.5, 28.0)], 330.0,
                   [(0.0, 82.0), (35.0, 82.0), (37.4, 82.6), (38.3, 83.8), (37.2, 60.0), (32.2, 12.5), (0.0, 10.0)])
    # the tea bag's string: out of the tea, over the rim, down the outside to its paper tag
    sd = polar_xy(330.0 - 115.0)
    st = [C2 + sd * 14.0 + ZUP * 80.0, C2 + sd * 30.0 + ZUP * 96.0, C2 + sd * 40.6 + ZUP * 108.6, C2 + sd * 43.8 + ZUP * 104.0, C2 + sd * 43.6 + ZUP * 84.0, C2 + sd * 42.2 + ZUP * 66.0]
    hs.finish(hs.skins('mug_b_string', [K.limb_rings(K.resample(K.spline(st, 10), 2.5), 0.45, seg=6)]), 0.0, CLAY)
    tg = sd.cross(ZUP)
    hs.finish(hs.rings('mug_b_tag', [[C2 + sd * (42.0 + q) + tg * s + ZUP * z for s, z in ((-12.0, 40.0), (12.0, 40.0), (12.0, 68.0), (-12.0, 68.0))] for q in (0.15, 0.55)]),
              0.0, CLAY)

    # ------------------------------------------------------------------------------------- the clipboard and its pen
    # a hardboard with round corners; on it a pressed-steel clip: a base riveted through the board, a jaw hinged on a
    # spring wire, its lip in rubber corner guards, its tail a lifted tab with the hole it hangs by; under the jaw a few
    # sheets, the top one not quite square and lifting at a corner (paper bends, it does not stretch); across it a stick
    # pen. Built round its own origin (the board's middle), then turned and laid on the bench.
    cl = [hs.finish(hs.prism_plan('clipboard_board', hs.rrect(-114.5, -159.0, 114.5, 159.0, 9.0, n=5), 0.0, 3.2), 0.5, CLAY),
          hs.finish(hs.box('clipboard_paper_stack', (-105.0, -150.0, 3.2), (105.0, 147.0, 3.9)), 0.0, CLAY)]
    sheet, pb = K.Skin(), bmesh.new()
    rows = []
    for j in range(19):
        row = []
        for i in range(15):
            x, y = -105.0 + 210.0 * i / 14.0, -150.0 + 297.0 * j / 18.0
            lift = 11.0 * K.smooth(x, 10.0, 105.0) ** 1.5 * K.smooth(-y, 55.0, 150.0) ** 1.6 + 0.3 * (1.0 + math.sin(x / 40.0 + 1.0)) * K.smooth(-y, -140.0, 100.0)
            c_, s_ = math.cos(math.radians(1.4)), math.sin(math.radians(1.4))                # (not quite square under the clip)
            xr, yr = x * c_ - (y - 140.0) * s_, 140.0 + x * s_ + (y - 140.0) * c_
            row.append(sheet.point(V3(xr - lift * 0.04, yr + lift * 0.06, 3.98 + lift), 0.05, 0.05, up=(0.0, 0.0, 1.0)))
        rows.append(row)
    sheet.grid(rows)
    K.thicken(sheet, pb)
    cl.append(K.soft(hs.obj('clipboard_sheet', pb), CLAY, sharp=60.0))
    cl.append(hs.finish(K.boxes('clipboard_clip_base', [((-50.0, 142.0, 3.2), (50.0, 159.0, 4.4)), ((-50.0, 148.0, 4.4), (-44.0, 156.0, 11.5)), ((44.0, 148.0, 4.4), (50.0, 156.0, 11.5))]),
                        0.3, CLAY))
    jaw_line = [(124.0, 5.4), (128.0, 4.1), (133.0, 4.9), (140.0, 8.2), (150.0, 12.2), (162.0, 16.6), (174.0, 22.0), (181.0, 26.4)]       # (along the board, up): lip, hinge, tail
    jaw = []
    for i, (y, z) in enumerate(jaw_line):
        a, b = jaw_line[max(i - 1, 0)], jaw_line[min(i + 1, len(jaw_line) - 1)]
        t = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        jaw.append((y - t.y * 1.0, z + t.x * 1.0))
    jw = hs.prism_section('clipboard_clip_jaw', jaw_line + jaw[::-1], -76.0, 76.0)
    jw = hs.boolean(jw, hs.prism_plan('jaw_plan', [(-76.0, 118.0), (76.0, 118.0), (76.0, 147.0), (58.0, 156.0), (31.0, 160.0), (27.0, 178.0), (20.0, 184.0), (-20.0, 184.0),
                                                   (-27.0, 178.0), (-31.0, 160.0), (-58.0, 156.0), (-76.0, 147.0)], -5.0, 40.0), 'INTERSECT')
    jw = hs.boolean(jw, hs.cyl('jaw_hole', (0.0, 171.0, -5.0), (0.0, 171.0, 40.0), 9.5, seg=24), 'DIFFERENCE')
    cl.append(hs.finish(jw, 0.25, CLAY))
    cl.append(hs.finish(hs.cyl('clipboard_clip_spring', (-51.0, 152.0, 9.4), (51.0, 152.0, 9.4), 3.2, seg=16), 0.0, CLAY))
    cl.append(hs.finish(K.boxes('clipboard_clip_guards', [((-78.0, 119.0, 3.4), (-64.0, 132.0, 7.4)), ((64.0, 119.0, 3.4), (78.0, 132.0, 7.4))]), 1.4, CLAY))
    cl.append(hs.finish(hs.skins('clipboard_rivets', [turned([(0.0, 0.0), (3.4, 0.0), (3.0, 1.0), (1.8, 1.6), (0.0, 1.8)], (sx * 32.0, 150.5, 4.4), seg=14) for sx in (-1, 1)]),
                        0.0, CLAY))
    place(cl, -14.0, (1315.0, 1110.0, BTOP))
    # the pen: a stick ballpoint, laid down across the sheet: a cone, a barrel, the plug at its end; its cap's clip
    pn = [hs.finish(hs.revolve('pen_barrel', [(0.0, 0.0), (0.5, 0.0), (1.1, 3.0), (2.3, 9.0), (3.7, 22.0), (3.9, 24.0), (3.9, 128.0), (3.5, 129.5), (3.5, 141.0), (2.8, 142.5),
                                              (0.0, 142.5)], at=V3(-71.0, 0.0, 3.9), axis=(1, 0, 0), seg=20), 0.0, CLAY),
          hs.finish(hs.box('pen_clip', (22.0, -1.3, 8.5), (60.0, 1.3, 9.4)), 0.3, CLAY),
          hs.finish(hs.box('pen_clip_root', (56.0, -1.6, 3.9), (62.0, 1.6, 9.4)), 0.4, CLAY)]
    place(pn, 38.0, (1315.0 + 6.0, 1110.0 - 6.0, BTOP + 4.1))  # (on the upper sheet where it lies flat, clip up)

    # --------------------------------------------------------------------------------------------- the whiteboard
    # on the right wall: an enamelled steel sheet in an aluminium frame with moulded corners, a pen tray along its foot
    # holding four markers and a felt eraser, a sheet of paper under two magnets
    WY0, WY1, WZ0, WZ1 = 200.0, 2200.0, 950.0, 1950.0
    WC = V3(X1, (WY0 + WY1) / 2.0, (WZ0 + WZ1) / 2.0)
    hs.finish(hs.box('board_surface', (X1 - 12.3, WY0 + 5.0, WZ0 + 5.0), (X1 - 3.0, WY1 - 5.0, WZ1 - 5.0)), 0.0, CLAY)
    hs.finish(K.frame_loop('board_frame', WC, (0, 1, 0), (0, 0, 1), (-1, 0, 0), (WY1 - WY0) / 2.0, (WZ1 - WZ0) / 2.0,
                           [(8.0, 0.0), (8.0, 14.0), (6.0, 17.0), (2.0, 18.0), (-12.0, 18.0), (-12.0, 12.8), (0.0, 12.8), (0.0, 0.0)]), 0.0, CLAY)
    hs.finish(K.boxes('board_corners', [((X1 - 19.0, y - (9.0 if sy < 0 else 22.0), z - (9.0 if sz < 0 else 22.0)), (X1, y + (22.0 if sy < 0 else 9.0), z + (22.0 if sz < 0 else 9.0)))
                                        for y, sy in ((WY0, -1), (WY1, 1)) for z, sz in ((WZ0, -1), (WZ1, 1))]), 4.0, CLAY)
    TY0, TY1, TZ = 320.0, 2080.0, WZ0 - 34.0
    hs.finish(hs.prism_side('board_tray', [(X1 - 2.0, TZ + 36.0), (X1 - 2.0, TZ), (X1 - 78.0, TZ), (X1 - 78.0, TZ + 14.0), (X1 - 75.5, TZ + 14.0), (X1 - 75.5, TZ + 2.5),
                                           (X1 - 4.5, TZ + 2.5), (X1 - 4.5, TZ + 36.0)], TY0, TY1), 0.3, CLAY)
    hs.finish(K.boxes('board_tray_ends', [((X1 - 79.0, TY0 - 3.0, TZ - 1.0), (X1 - 1.5, TY0, TZ + 15.5)), ((X1 - 79.0, TY1, TZ - 1.0), (X1 - 1.5, TY1 + 3.0, TZ + 15.5))]), 1.0, CLAY)
    mk = []
    for i, (y, lean) in enumerate(((520.0, 0.02), (700.0, -0.05), (905.0, 0.03), (1720.0, -0.02))):
        ax = V3(lean, 1.0, 0.0).normalized()
        mk.append(turned([(0.0, 0.0), (7.4, 0.0), (8.2, 1.5), (8.2, 94.0), (9.0, 95.0), (9.0, 132.0), (8.2, 134.0), (5.5, 136.0), (0.0, 136.0)], (X1 - 30.0 - 9.0 * (i % 2), y, TZ + 2.5 + 9.0),
                         ax, 20))
    hs.finish(hs.skins('board_markers', mk), 0.0, CLAY)
    hs.finish(K.boxes('board_eraser', [((X1 - 64.0, 1240.0, TZ + 2.5), (X1 - 14.0, 1352.0, TZ + 13.0)), ((X1 - 61.0, 1243.0, TZ + 13.0), (X1 - 17.0, 1349.0, TZ + 34.0))]), 3.0, CLAY)
    hs.finish(hs.skins('board_magnets', [turned([(0.0, 0.0), (15.0, 0.0), (15.0, 5.0), (12.5, 7.5), (0.0, 8.0)], (X1 - 12.3 - 0.3 * int(pin), y, z), (-1, 0, 0), 24)
                                         for y, z, pin in ((1756.0, 1786.0, True), (1952.0, 1790.0, True), (420.0, 1880.0, False), (462.0, 1868.0, False))]), 0.0, CLAY)
    sheet, pb = K.Skin(), bmesh.new()
    rows = []
    for j in range(17):
        row = []
        for i in range(13):
            y, z = 1750.0 + 210.0 * i / 12.0, 1800.0 - 297.0 * j / 16.0
            off = 0.25 + 7.0 * K.smooth(1800.0 - z, 120.0, 297.0) ** 1.7 * (0.6 + 0.4 * K.smooth(y, 1750.0, 1960.0))       # (it hangs off the board at its foot)
            row.append(sheet.point(V3(X1 - 12.3 - off, y, z), 0.05, 0.05, up=(-1.0, 0.0, 0.0)))
        rows.append(row)
    sheet.grid(rows)
    K.thicken(sheet, pb)
    K.soft(hs.obj('board_sheet', pb), CLAY, sharp=60.0)

    # ------------------------------------------------------------------------------------------------- the chair
    # a task chair, left where its sitter turned it: a polished five-star base cast in one piece on twin-wheel castors,
    # the gas column in its telescoping shroud, the mechanism's housing and its paddle under a moulded seat shell, an
    # upholstered cushion with a piped seam, the back's flat upright, a padded back in its shell. Built round the
    # column's foot, facing its own -y, then turned.
    ch = []
    hub = hs.revolve('chair_base', [(0.0, 118.0), (33.0, 118.0), (38.0, 123.0), (38.0, 166.0), (33.0, 172.0), (0.0, 172.0)], seg=40)
    tips = []
    for k in range(5):
        a = math.radians(90.0 + 72.0 * k + 18.0)
        er, et = V3(math.cos(a), math.sin(a), 0.0), V3(-math.sin(a), math.cos(a), 0.0)
        rl = []
        for r, w, h, zt in ((24.0, 48.0, 40.0, 164.0), (80.0, 44.0, 36.0, 150.0), (160.0, 38.0, 30.0, 128.0), (240.0, 33.0, 25.0, 108.0), (296.0, 31.0, 23.0, 97.0), (318.0, 26.0, 21.0, 95.0),
                            (326.0, 14.0, 14.0, 93.0)):
            rl.append([er * r + et * u + ZUP * (zt - h / 2.0 + v) for u, v in hs.rrect(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0, min(w, h) * 0.32, n=4)])
        hub = hs.boolean(hub, hs.rings(f'chair_spoke_{k}', rl), 'UNION')
        hub = hs.boolean(hub, hs.cyl(f'chair_boss_{k}', tuple(er * 300.0 + ZUP * 64.0), tuple(er * 300.0 + ZUP * 100.0), 27.0, seg=24), 'UNION')
        tips.append(er * 300.0)
    ch.append(hs.finish(hub, 1.5, CLAY))
    sk = []
    for k, tp in enumerate(tips):
        sk += castor_skins((tp.x, tp.y), (200.0, 265.0, 20.0, 110.0, 325.0)[k], d=60.0, top=66.0)
    ch.append(hs.finish(hs.skins('chair_castors', sk), 0.6, CLAY))
    ch.append(hs.finish(hs.revolve('chair_column', [(0.0, 170.0), (31.0, 170.0), (31.0, 250.0), (28.0, 252.0), (28.0, 330.0), (25.0, 332.0), (25.0, 406.0), (0.0, 406.0)], seg=40), 0.8,
                        CLAY))
    ch.append(hs.finish(hs.box('chair_mechanism', (-100.0, -95.0, 404.0), (100.0, 80.0, 448.0)), 7.0, CLAY))
    ch.append(hs.finish(hs.skins('chair_lever', [K.limb_rings(K.resample(hs.fillet_path([V3(80.0, -20.0, 426.0), V3(170.0, -20.0, 426.0), V3(228.0, -24.0, 418.0)], 30.0, n=6), 6.0),
                                                              4.2, seg=12, caps=(0.0, 0.6)),
                                                 K.box_rings((214.0, -37.0, 413.0), (262.0, -11.0, 420.0)),
                                                 turned([(0.0, 366.0), (22.0, 366.0), (25.0, 370.0), (25.0, 407.0), (0.0, 407.0)], (0.0, -62.0, 0.0), seg=28)]), 1.2, CLAY))
    ch.append(K.soft(hs.rings('chair_seat_shell', [seat_ring(446.0, 0.62), seat_ring(449.0, 0.84), seat_ring(456.0, 0.95), seat_ring(466.0, 0.99)]), CLAY, sharp=45.0))
    ch.append(K.soft(hs.rings('chair_seat_cushion', [seat_ring(466.0, 1.0), seat_ring(472.0, 1.022, 2.0), seat_ring(486.0, 1.03, 6.0), seat_ring(503.0, 1.022, 12.0),
                                                     seat_ring(514.0, 0.985, 16.0), seat_ring(519.0, 0.93, 17.0), seat_ring(521.0, 0.8, 15.0), seat_ring(518.0, 0.5, 8.0),
                                                     seat_ring(516.5, 0.15, 3.0)]), CLAY, sharp=45.0))
    pp = seat_ring(486.0, 1.036, 6.0)
    ch.append(K.soft(K.loops('chair_seat_piping', [[[p + (Vector((p.x, p.y + 8.0, 0.0)).normalized()) * (1.9 * math.cos(2 * math.pi * q_ / 8)) + ZUP * (1.9 * math.sin(2 * math.pi * q_ / 8))
                                                     for q_ in range(8)] for p in pp + [pp[0]]]]), CLAY))
    ch.append(hs.finish(hs.sweep('chair_back_upright', hs.fillet_path([V3(0.0, 60.0, 430.0), V3(0.0, 232.0, 432.0), V3(0.0, 268.0, 560.0), V3(0.0, 296.0, 770.0)], 60.0, n=8),
                                 hs.rrect(-30.0, -5.0, 30.0, 5.0, 3.0, n=3), up=(0, 1, -1)), 0.0, CLAY))
    BZ = ((545.0, 0.76, 0.5), (552.0, 0.9, 0.8), (570.0, 0.985, 1.0), (640.0, 1.0, 1.0), (780.0, 1.0, 1.0), (900.0, 0.985, 1.0), (935.0, 0.95, 0.9), (949.0, 0.88, 0.72),
          (955.0, 0.74, 0.45))
    ch.append(K.soft(hs.rings('chair_back_cushion', [back_ring(z, sc, 22.0 * th_, 0.0) for z, sc, th_ in BZ]), CLAY, sharp=45.0))
    ch.append(K.soft(hs.rings('chair_back_shell', [back_ring(z + (4.0 if i < 2 else -4.0 if i > 6 else 0.0), sc * 0.962, 9.0 * th_, 24.0, 214.0) for i, (z, sc, th_) in enumerate(BZ)]),
                     CLAY, sharp=45.0))
    ch.append(hs.finish(hs.box('chair_back_mount', (-48.0, 262.0, 600.0), (48.0, 306.0, 772.0)), 5.0, CLAY))
    place(ch, chair_yaw, (chair_at[0], chair_at[1], 0.0))
