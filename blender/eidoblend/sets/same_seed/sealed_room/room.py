"""eidoblend.sets.same_seed.sealed_room.room: the sealed room's shell and fixtures, built with the hard-surface kit
(eidoblend.props.hardsurface.masses). Tables in millimetres; the room's own space: x across (the lenses look along +y),
y to the back wall, z up from the floor; the scene in metres.

    from eidoblend.props.hardsurface import masses as hs
    from eidoblend.sets.same_seed.sealed_room import room
    hs.start('sealed_room', orient=False)
    room.build(hs, clay, dark)

A room in an old government building: painted concrete BLOCK walls on three sides (the fourth, wall_front_unseen,
shuts the room behind the lenses), a vinyl tile floor, a painted concrete ceiling, a rubber cove base; two window
openings closed with 6 mm STEEL PLATES bolted over them above their old precast sills; a pressed-steel door frame with a
flush steel door that has no handle on this side (a blanked lock, a kick plate, a narrow lite, a parallel-arm closer);
3/4 inch EMT conduit on one-hole straps from the switch beside the door to a ceiling box, on to the light's end and
along the ceiling to the camera's corner; the switch, the boxes and their covers; a stamped return grille over its
duct. Each piece is built as it is made: sections with their thickness, parts that meet as they are joined, a fastener
wherever something is fastened. The bench (bench.py), the stool, the camera and the light (Poly Haven models, placed by
the look) are not built here.
"""

import math
import random

from mathutils import Vector

X0, X1, Y0, Y1, HT, TW = -2500.0, 2500.0, -1850.0, 2750.0, 2600.0, 190.0     # 13 courses of 200 mm to the ceiling
DXL, DXR, DZT = 700.0, 1716.0, 2200.0          # the door's masonry opening (a 915 x 2134 door in a 51 mm frame)
GX0, GX1, GZ0, GZ1 = 2030.0, 2374.0, 2178.0, 2322.0     # the vent's duct mouth
SWX, SWZ = 1866.0, 1220.0                      # the switch
J1 = (1866.0, 2450.0)                          # the ceiling box
CAM = (X0, 2450.0, 2300.0)                     # the camera's base, on the left wall
LCY = -300.0                                   # the light's axis (it runs along x)
X_END = 456.0                                  # the conduit ends at the light's end
RC, OFF = 11.7, 19.0                           # the conduit's radius; its axis off the surface
WINDOWS = (('window_back', 'back', -1900.0, -700.0), ('window_left', 'left', -300.0, 900.0))


def V3(x, y, z):
    return Vector((x, y, z))


def build(hs, CLAY, DARK, seed=5):
    """Every part into hs.col (the room's collection), each finished with its one bevel. seed: the bolts' turns."""
    rng = random.Random(seed)

    def bolt_skins(at, axis, af=17.0, head=7.0, wr=15.0, wt=2.5):
        """a hex head on its washer, standing along `axis` from `at`, turned as it happened to stop"""
        ax = Vector(axis).normalized()
        n0 = ax.orthogonal().normalized()
        a = rng.uniform(0.0, math.pi / 3.0)
        st = n0 * math.cos(a) + ax.cross(n0) * math.sin(a)
        R = af / math.sqrt(3.0)
        return [[hs.circle(at, ax, wr, 0.0, 20), hs.circle(at, ax, wr, wt, 20)],
                [hs.circle(at, ax, R, wt, 6, st), hs.circle(at, ax, R, wt + head - 1.2, 6, st), hs.circle(at, ax, R * 0.86, wt + head, 6, st)]]

    def screw_skins(at, axis, r=3.6, h=2.2):
        return [[hs.circle(at, axis, r, 0.0, 12), hs.circle(at, axis, r, h * 0.45, 12), hs.circle(at, axis, r * 0.62, h, 12)]]

    def rim_loop(name, cx, cz, hw, hh, prof, y_face):
        """a moulding run round a rectangle on the back wall's side, mitred at its corners: prof [(u out from the
        opening's edge, v proud of the face toward the room)]"""
        rl = [[V3(cx + sx * (hw + u), y_face - v, cz + sz * (hh + u)) for u, v in prof] for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
        return hs.rings(name, rl, caps=False)

    # ---------------------------------------------------------------------------------------------- the shell
    back = hs.box('wall_back', (X0 - TW, Y1, 0.0), (X1 + TW, Y1 + TW, HT))
    back = hs.boolean(back, hs.box('door_opening', (DXL, Y1 - 50.0, -50.0), (DXR, Y1 + TW + 50.0, DZT)), 'DIFFERENCE')
    back = hs.boolean(back, hs.box('vent_duct', (GX0, Y1 - 50.0, GZ0), (GX1, Y1 + 140.0, GZ1)), 'DIFFERENCE')
    hs.finish(back, 0.0, CLAY)
    hs.finish(hs.box('wall_left', (X0 - TW, Y0 - TW, 0.0), (X0, Y1, HT)), 0.0, CLAY)
    hs.finish(hs.box('wall_right', (X1, Y0 - TW, 0.0), (X1 + TW, Y1, HT)), 0.0, CLAY)
    hs.finish(hs.box('wall_front_unseen', (X0, Y0 - TW, 0.0), (X1, Y0, HT)), 0.0, CLAY)     # (hidden from the camera only)
    hs.finish(hs.box('room_floor', (X0 - TW, Y0 - TW, -150.0), (X1 + TW, Y1 + TW, 0.0)), 0.0, CLAY)
    hs.finish(hs.box('room_ceiling', (X0 - TW, Y0 - TW, HT), (X1 + TW, Y1 + TW, HT + 200.0)), 0.0, CLAY)
    hs.finish(hs.box('door_backing', (DXL, Y1 + 146.0, 0.0), (DXR, Y1 + TW + 5.0, DZT)), 0.0, DARK)
    hs.finish(hs.box('vent_duct_dark', (GX0, Y1 + 100.0, GZ0), (GX1, Y1 + 139.0, GZ1)), 0.0, DARK)
    # the rubber cove base along the three walls (its toe on the floor), stopping at the door's frame
    BASE = [(0.0, 0.0), (12.0, 0.0), (12.0, 1.5), (5.0, 6.0), (3.2, 14.0), (3.2, 98.0), (2.2, 100.0), (0.0, 100.0)]
    for nm, a, b in (('cove_base_back_l', V3(DXL, Y1, 0), V3(X0, Y1, 0)), ('cove_base_back_r', V3(X1, Y1, 0), V3(DXR, Y1, 0)),
                     ('cove_base_left', V3(X0, Y1, 0), V3(X0, Y0, 0)), ('cove_base_right', V3(X1, Y0, 0), V3(X1, Y1, 0))):
        hs.finish(hs.sweep(nm, [a, b], BASE, up=(0, 0, 1)), 0.0, CLAY)

    # ------------------------------------------------------------------------------------ the windows, sealed
    # each opening closed by a 6 mm steel plate lapping the wall by 70 mm on three sides, standing on the old sill
    # (a precast stool: it is what says a window was here), held by anchor bolts every quarter metre
    def sealed_window(name, wall, a0, a1, z0=1000.0, z1=2000.0):
        lap, ins = 70.0, 40.0
        p0, p1, q1 = a0 - lap, a1 + lap, z1 + lap
        if wall == 'back':
            plate = hs.box(name + '_plate', (p0, Y1 - 6.0, z0 + 2.0), (p1, Y1, q1))
            sill = hs.box(name + '_sill', (a0 - 60.0, Y1 - 38.0, z0 - 50.0), (a1 + 60.0, Y1, z0))
            at = lambda a, z: V3(a, Y1 - 6.0, z)                  # noqa: E731
            ax = (0, -1, 0)
        else:
            plate = hs.box(name + '_plate', (X0, p0, z0 + 2.0), (X0 + 6.0, p1, q1))
            sill = hs.box(name + '_sill', (X0, a0 - 60.0, z0 - 50.0), (X0 + 38.0, a1 + 60.0, z0))
            at = lambda a, z: V3(X0 + 6.0, a, z)                  # noqa: E731
            ax = (1, 0, 0)
        hs.finish(plate, 0.8, CLAY)
        hs.finish(sill, 5.0, CLAY)
        nh = max(2, int(round((p1 - p0 - 2 * ins) / 250.0)))
        nv = max(2, int(round((q1 - z0 - 2 * ins) / 250.0)))
        sk = []
        for i in range(nh + 1):
            a = p0 + ins + (p1 - p0 - 2 * ins) * i / nh
            sk += bolt_skins(at(a, z0 + 2.0 + ins), ax) + bolt_skins(at(a, q1 - ins), ax)
        for j in range(1, nv):
            z = z0 + 2.0 + ins + (q1 - z0 - 2.0 - 2 * ins) * j / nv
            sk += bolt_skins(at(p0 + ins, z), ax) + bolt_skins(at(p1 - ins, z), ax)
        hs.finish(hs.skins(name + '_bolts', sk), 0.0, CLAY)

    for name, wall, a0, a1 in WINDOWS:
        sealed_window(name, wall, a0, a1)

    # ----------------------------------------------------------------------------------------------- the door
    # a pressed-steel ("hollow metal") frame, double rabbet, 51 mm faces, mitred at the head; the door hangs in the far
    # rabbet and opens AWAY from the room, so this side shows the frame's face, 40 mm of rabbet, the stop, and the
    # door's flush face 98 mm back: no hinges, and no handle: a blanked lock prep, a kick plate, a narrow lite, the
    # closer's arm
    yF = Y1 - 2.0                                              # the frame's face stands 2 mm proud of the blocks
    FRAME = [(0.0, 0.0), (51.0, 0.0), (51.0, 40.0), (67.0, 40.0), (67.0, 97.0), (51.0, 97.0), (51.0, 146.0), (0.0, 146.0)]
    hs.finish(hs.rings('door_frame', [[V3(DXL + u, yF + v, 0.0) for u, v in FRAME], [V3(DXL + u, yF + v, DZT - u) for u, v in FRAME],
                                      [V3(DXR - u, yF + v, DZT - u) for u, v in FRAME], [V3(DXR - u, yF + v, 0.0) for u, v in FRAME]]), 1.2, CLAY)
    LX0, LX1, LZ0, LZ1 = DXL + 53.5, DXR - 53.5, 10.0, DZT - 54.0
    yD = yF + 98.5                                             # the leaf's face on this side
    hs.finish(hs.box('door_leaf', (LX0, yD, LZ0), (LX1, yD + 45.0, LZ1)), 1.0, CLAY)
    hs.finish(hs.box('door_lock_blank', (LX1 - 112.0, yD - 2.0, 910.0), (LX1 - 42.0, yD, 1130.0)), 0.6, CLAY)
    hs.finish(hs.box('door_kick_plate', (LX0 + 25.0, yD - 1.2, 30.0), (LX1 - 25.0, yD, 284.0)), 0.3, CLAY)
    sk = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            sk += screw_skins(V3(LX1 - 77.0 + sx * 25.0, yD - 2.0, 1020.0 + sz * 98.0), (0, -1, 0), 3.2, 1.6)
    kx0, kx1 = LX0 + 40.0, LX1 - 40.0
    for i in range(7):
        x = kx0 + (kx1 - kx0) * i / 6.0
        sk += screw_skins(V3(x, yD - 1.2, 45.0), (0, -1, 0), 3.0, 1.4) + screw_skins(V3(x, yD - 1.2, 269.0), (0, -1, 0), 3.0, 1.4)
    sk += screw_skins(V3(kx0, yD - 1.2, 157.0), (0, -1, 0), 3.0, 1.4) + screw_skins(V3(kx1, yD - 1.2, 157.0), (0, -1, 0), 3.0, 1.4)
    hs.finish(hs.skins('door_screws', sk), 0.0, CLAY)
    lcx, lcz = LX1 - 190.0, 1567.0
    hs.finish(rim_loop('door_lite_rim', lcx, lcz, 50.0, 317.0, [(0.0, 0.0), (0.0, 3.0), (3.0, 5.5), (17.0, 5.5), (22.0, 1.0), (22.0, 0.0)], yD), 0.0, CLAY)
    hs.finish(hs.box('door_lite_glass', (lcx - 50.0, yD - 1.0, lcz - 317.0), (lcx + 50.0, yD + 0.5, lcz + 317.0)), 0.0, DARK)
    # the closer, parallel-arm: its body on the door under the head, its two arms folded along the door to a shoe under
    # the frame's stop
    cz0, cz1 = DZT - 67.0 - 33.0 - 60.0, DZT - 67.0 - 33.0
    xp = LX0 + 110.0
    hs.finish(hs.box('door_closer_body', (LX0 + 45.0, yD - 48.0, cz0), (LX0 + 275.0, yD, cz1)), 6.0, CLAY)
    hs.finish(hs.cyl('door_closer_pinion', (xp, yD - 24.0, cz1 - 2.0), (xp, yD - 24.0, cz1 + 9.5), 22.0, seg=24), 1.0, CLAY)
    BAR = [(-11.0, -2.5), (11.0, -2.5), (11.0, 2.5), (-11.0, 2.5)]
    hs.finish(hs.sweep('door_closer_arm', [V3(xp - 14.0, yD - 24.0, cz1 + 12.0), V3(xp + 262.0, yD - 26.0, cz1 + 12.0)], BAR, up=(0, 0, 1)), 1.0, CLAY)
    hs.finish(hs.sweep('door_closer_forearm', [V3(xp + 262.0, yD - 26.0, cz1 + 19.0), V3(xp + 48.0, yD - 31.0, cz1 + 19.0)],
                       [(-9.0, -2.5), (9.0, -2.5), (9.0, 2.5), (-9.0, 2.5)], up=(0, 0, 1)), 1.0, CLAY)
    hs.finish(hs.cyl('door_closer_elbow', (xp + 250.0, yD - 26.0, cz1 + 8.0), (xp + 250.0, yD - 26.0, cz1 + 24.0), 12.0, seg=16), 0.5, CLAY)
    hs.finish(hs.box('door_closer_shoe', (xp + 30.0, yF + 44.0, DZT - 67.0 - 9.0), (xp + 90.0, yF + 92.0, DZT - 67.0)), 1.5, CLAY)
    hs.finish(hs.cyl('door_closer_shoe_pin', (xp + 60.0, yF + 67.5, cz1 + 14.0), (xp + 60.0, yF + 67.5, DZT - 67.0 - 8.0), 12.0, seg=16), 0.5, CLAY)

    # -------------------------------------------------------------------------------------------- the conduit
    # 3/4 inch EMT on one-hole straps, 19 mm off the surface so it runs straight into its boxes: from the switch beside
    # the door up to a box on the ceiling; from that box on to the light's end, and along the ceiling to the camera
    RING = [(RC * math.cos(2 * math.pi * k / 24), RC * math.sin(2 * math.pi * k / 24)) for k in range(24)]

    def conduit(name, pts, r_bend=115.0):
        hs.finish(hs.sweep(name, hs.fillet_path(pts, r_bend, n=10), RING), 0.0, CLAY)

    def connector(name, at, t):
        """a set-screw connector: the collar where a conduit enters a box"""
        prof = [(RC + 0.2, 0.0), (14.8, 0.0), (14.8, 6.0), (13.6, 7.0), (13.6, 20.0), (15.6, 20.0), (15.6, 23.0), (RC + 0.2, 23.0)]
        hs.finish(hs.revolve(name, prof, at=at, axis=t, seg=32, closed=True), 0.0, CLAY)

    def strap_skins(P, t, n):
        """a one-hole strap over the conduit at P (the conduit runs along t; n points off the surface), and its screw"""
        P, t, n = Vector(P), Vector(t).normalized(), Vector(n).normalized()
        b = t.cross(n)
        ri, ro, hb = RC + 0.4, RC + 2.2, -OFF
        pts = [(ro + 24.0, hb), (ro + 24.0, hb + 1.8), (ro, hb + 1.8)]
        pts += [(ro * math.cos(math.radians(a)), ro * math.sin(math.radians(a))) for a in range(0, 181, 15)]
        pts += [(-ro, hb), (-ri, hb)]
        pts += [(ri * math.cos(math.radians(a)), ri * math.sin(math.radians(a))) for a in range(180, -1, -15)]
        pts += [(ri, hb)]
        sk = [[[P + t * w + b * s + n * h for s, h in pts] for w in (-9.5, 9.5)]]
        return sk + screw_skins(P + b * (ro + 13.0) + n * (hb + 1.8), n, 4.0, 2.4)

    conduit('conduit_switch_to_box', [V3(SWX, Y1 - OFF, SWZ + 53.0), V3(SWX, Y1 - OFF, HT - OFF), V3(SWX, J1[1] + 53.0, HT - OFF)])
    conduit('conduit_box_to_light', [V3(SWX, J1[1] - 53.0, HT - OFF), V3(SWX, LCY, HT - OFF), V3(X_END + 4.0, LCY, HT - OFF)])
    conduit('conduit_box_to_camera', [V3(J1[0] - 53.0, J1[1], HT - OFF), V3(X0 + OFF, J1[1], HT - OFF), V3(X0 + OFF, CAM[1], CAM[2] + 52.0)])
    connector('connector_switch', V3(SWX, Y1 - OFF, SWZ + 51.0), (0, 0, 1))
    connector('connector_box_from_switch', V3(SWX, J1[1] + 51.0, HT - OFF), (0, 1, 0))
    connector('connector_box_to_light', V3(SWX, J1[1] - 51.0, HT - OFF), (0, -1, 0))
    connector('connector_box_to_camera', V3(J1[0] - 51.0, J1[1], HT - OFF), (-1, 0, 0))
    connector('connector_light', V3(X_END + 2.0, LCY, HT - OFF), (1, 0, 0))
    connector('connector_camera', V3(X0 + OFF, CAM[1], CAM[2] + 50.0), (0, 0, 1))
    sk = []
    for z in (1500.0, 2150.0):
        sk += strap_skins((SWX, Y1 - OFF, z), (0, 0, 1), (0, -1, 0))
    for y in (2000.0, 1100.0, 200.0):
        sk += strap_skins((SWX, y, HT - OFF), (0, 1, 0), (0, 0, -1))
    for x in (1300.0, 900.0):
        sk += strap_skins((x, LCY, HT - OFF), (1, 0, 0), (0, 0, -1))
    for x in (1400.0, 500.0, -400.0, -1300.0, -2200.0):
        sk += strap_skins((x, J1[1], HT - OFF), (1, 0, 0), (0, 0, -1))
    hs.finish(hs.skins('conduit_straps', sk), 0.0, CLAY)
    # the switch's box (a drawn "handy box") with its cover and toggle; the square box on the ceiling with its blank cover
    hs.finish(hs.box('switch_box', (SWX - 27.0, Y1 - 46.0, SWZ - 51.0), (SWX + 27.0, Y1, SWZ + 51.0)), 5.0, CLAY)
    hs.finish(hs.box('switch_cover', (SWX - 30.0, Y1 - 47.8, SWZ - 54.0), (SWX + 30.0, Y1 - 46.0, SWZ + 54.0)), 0.6, CLAY)
    hs.finish(hs.box('switch_boss', (SWX - 9.0, Y1 - 50.5, SWZ - 15.0), (SWX + 9.0, Y1 - 47.8, SWZ + 15.0)), 1.2, CLAY)
    hs.finish(hs.prism_side('switch_toggle', [(SWX - 3.2, SWZ - 4.5), (SWX + 3.2, SWZ - 4.5), (SWX + 3.2, SWZ + 4.5), (SWX - 3.2, SWZ + 4.5)],
                            Y1 - 62.0, Y1 - 50.0), 1.0, CLAY)
    hs.finish(hs.box('ceiling_box', (J1[0] - 51.0, J1[1] - 51.0, HT - 38.0), (J1[0] + 51.0, J1[1] + 51.0, HT)), 2.5, CLAY)
    hs.finish(hs.box('ceiling_box_cover', (J1[0] - 52.0, J1[1] - 52.0, HT - 39.8), (J1[0] + 52.0, J1[1] + 52.0, HT - 38.0)), 0.6, CLAY)
    sk = screw_skins(V3(SWX, Y1 - 47.8, SWZ + 42.0), (0, -1, 0), 3.2, 1.8) + screw_skins(V3(SWX, Y1 - 47.8, SWZ - 42.0), (0, -1, 0), 3.2, 1.8)
    sk += screw_skins(V3(J1[0] - 38.0, J1[1] + 38.0, HT - 39.8), (0, 0, -1), 3.2, 1.8) + screw_skins(V3(J1[0] + 38.0, J1[1] - 38.0, HT - 39.8), (0, 0, -1), 3.2, 1.8)
    hs.finish(hs.skins('box_cover_screws', sk), 0.0, CLAY)

    # ----------------------------------------------------------------------------------------------- the vent
    # a stamped return grille over its duct: a frame lapping the wall, fixed blades tilted down, two screws
    gcx, gcz, ghw, ghh = (GX0 + GX1) / 2, (GZ0 + GZ1) / 2, (GX1 - GX0) / 2, (GZ1 - GZ0) / 2
    hs.finish(rim_loop('vent_frame', gcx, gcz, ghw - 4.0, ghh - 4.0, [(0.0, -8.0), (0.0, 4.0), (2.0, 6.0), (26.0, 6.0), (30.0, 2.0), (30.0, 0.0),
                                                                    (4.0, 0.0), (4.0, -8.0)], Y1), 0.0, CLAY)
    ca, sa = math.cos(math.radians(40.0)), math.sin(math.radians(40.0))
    blades = None
    for k in range(11):
        z = GZ0 + 9.0 + k * 12.6
        yc_ = Y1 + 5.0
        d, n_ = (-ca, -sa), (sa, -ca)
        sec = [(yc_ + sd * d[0] * 8.0 + sn * n_[0] * 0.6, z + sd * d[1] * 8.0 + sn * n_[1] * 0.6) for sd, sn in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        bl = hs.prism_section(f'vent_blade_{k}', sec, GX0 + 1.0, GX1 - 1.0)
        blades = bl if blades is None else hs.boolean(blades, bl, 'UNION')
    blades.name = 'vent_blades'
    hs.finish(blades, 0.0, CLAY)
    hs.finish(hs.skins('vent_screws', screw_skins(V3(GX0 - 12.0, Y1 - 6.0, gcz), (0, -1, 0), 3.4, 1.8)
                       + screw_skins(V3(GX1 + 12.0, Y1 - 6.0, gcz), (0, -1, 0), 3.4, 1.8)), 0.0, CLAY)
