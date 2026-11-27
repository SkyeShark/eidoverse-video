"""eidoblend.props.helicopter.cabin: inside: the cabin and the cockpit.

    a troop seat  hangs from the ceiling on two tube posts that lean back; a tube frame carries a cloth pan; two tube
                  legs fold down from its front to fittings in the floor's tracks; a tall cloth back with a headrest
                  folded over its top; a four-point harness to a round buckle. Eight of them: one at each door facing
                  OUT (seat_door_l: its pan's top 445 above the floor, at x 120, y -700), one at each gunner's window,
                  four across the rear facing forward. Each under its own Empty (seat_<where>).
    the floor     seat tracks let into it fore and aft, lashing rings in pans on a 0.5 m grid, a scuff plate at each sill
    overhead      two rails the seats hang from, a bar across at the doors, two dome lights
    the cockpit   two armoured seats (a bucket with wings) on rails, cushions and headrests; the cyclic and the
                  collective; the instrument panel with four displays under its glare shield; the console between the
                  seats, the overhead console
"""

from __future__ import annotations

import math

from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from ..hardsurface.sections import stations
from . import datum as D


def frame_of(at, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    fw, lf = Vector((c, s, 0.0)), Vector((-s, c, 0.0))

    def W(u, v, z):
        return Vector((at[0], at[1], 0.0)) + fw * u + lf * v + Vector((0.0, 0.0, z))
    return W


def tube(pts, r, seg=10, bend=None):
    path = hs.fillet_path(pts, bend, n=5) if bend else [Vector(p) for p in pts]
    return [[p + n * (r * math.cos(2 * math.pi * i / seg)) + b * (r * math.sin(2 * math.pi * i / seg)) for i in range(seg)] for p, t, n, b in hs.frames(path)]


def cloth(W, grid, thick):
    """a sheet over a grid of points [[(u, v, z)]], as a closed slab: rows across, each row a loop"""
    rows = []
    for row in grid:
        top = [W(*p) for p in row]
        rows.append(top + [p - Vector((0.0, 0.0, thick)) for p in top][::-1])
    return rows


def build(b):
    CLAY, DARK, FABRIC, GLASS, RUBBER, STEEL = b.clay, b.dark, b.fabric, b.glass, b.rubber, b.steel

    def seat(name, at, yaw, belts=True):
        W = frame_of(at, yaw)
        e = hs.empty(name, (at[0], at[1], 0.0))
        tubes, straps = [], []
        for v in (-236.0, 236.0):
            tubes.append(tube([W(-196.0, v, 6.0), W(-262.0, v, 1240.0), W(-276.0, v, D.CEIL - 8.0)], 15.0, bend=120.0))       # the back post, up to its hanger
            tubes.append(tube([W(206.0, v, 448.0), W(-70.0, v, 8.0)], 11.0))                                                 # the folding leg
            tubes.append(tube([W(-196.0, v, 0.0), W(-196.0, v, 30.0)], 26.0, seg=14))                                        # the floor fittings
            tubes.append(tube([W(-70.0, v, 0.0), W(-70.0, v, 22.0)], 20.0, seg=12))
        tubes.append(tube([W(60.0, -236.0, 232.0), W(60.0, 236.0, 232.0)], 9.0))                                             # the legs' cross tube
        loop = hs.fillet_path([W(-210.0, -236.0, 452.0), W(214.0, -236.0, 452.0), W(214.0, 236.0, 452.0), W(-210.0, 236.0, 452.0)], 70.0, n=6)
        tubes.append(tube(loop, 12.5, seg=10))
        tubes.append(tube([W(-262.0, -236.0, 1236.0), W(-262.0, 236.0, 1236.0)], 12.0))                                      # the back's top tube
        hs.finish(hs.skins(name + '_frame', tubes), 0.0, CLAY, parent=e)
        # the pan's cloth: laced to the frame, sagging a little in its middle
        pan = [[(-205.0 + 412.0 * a, -228.0 + 456.0 * b_, 458.0 - 16.0 * (1.0 - (2 * a - 1) ** 2) * (1.0 - (2 * b_ - 1) ** 4)) for b_ in [q / 10 for q in range(11)]]
               for a in [q / 8 for q in range(9)]]
        bt.finish_smooth(hs.rings(name + '_pan', cloth(W, pan, 5.0)), FABRIC, parent=e)
        # the back's cloth between the posts, hollowed a little; the headrest folded over its top
        back = []
        for a in [q / 12 for q in range(13)]:
            z = 470.0 + (1150.0 - 470.0) * a
            u0 = -196.0 - 66.0 * (z - 6.0) / 1234.0
            back.append([(u0 + 13.0 - 14.0 * (1.0 - (2 * b_ - 1) ** 2), -226.0 + 452.0 * b_, z) for b_ in [q / 10 for q in range(11)]])
        rows = []
        for row in back:
            top = [W(*p) for p in row]
            rows.append(top + [W(p[0] - 6.0, p[1], p[2]) for p in row][::-1])
        bt.finish_smooth(hs.rings(name + '_back', rows), FABRIC, parent=e)
        hr = bt.round_poly([(-250.0, 1010.0), (-214.0, 1004.0), (-212.0, 1196.0), (-262.0, 1246.0), (-292.0, 1236.0), (-272.0, 1040.0)], 16.0, 4)
        bt.finish_smooth(hs.rings(name + '_headrest', [[W(u, v, z) for u, z in hr] for v in (-150.0, 150.0)]), FABRIC, parent=e, sharp_deg=40.0)
        if belts:                                             # the harness lying as it is left: two lap straps, two shoulder straps, the buckle
            for sv in (-1.0, 1.0):
                straps.append([[W(u, sv * v + dv, z + dz) for dv, dz in ((-22.0, 0.0), (22.0, 0.0), (22.0, 3.0), (-22.0, 3.0))]
                               for u, v, z in ((-190.0, 224.0, 462.0), (-120.0, 150.0, 452.0), (-10.0, 40.0, 446.0))])
                straps.append([[W(u + du, sv * v + dv, z) for dv, du in ((-22.0, 0.0), (22.0, 0.0), (22.0, 3.0), (-22.0, 3.0))]
                               for u, v, z in ((-252.0, 70.0, 1120.0), (-228.0, 62.0, 760.0), (-196.0, 48.0, 480.0), (-60.0, 26.0, 449.0))])
            hs.finish(hs.skins(name + '_harness', straps), 0.0, RUBBER, parent=e)
            hs.finish(hs.revolve(name + '_buckle', [(0.0, 0.0), (30.0, 0.0), (33.0, 5.0), (33.0, 16.0), (26.0, 21.0), (0.0, 21.0)], at=W(-20.0, 0.0, 446.0), seg=20),
                      0.0, STEEL, parent=e)
        return e

    seat('seat_door_l', (120.0, -700.0), -90.0, belts=False)   # facing out of the left door, its harness off
    seat('seat_door_r', (120.0, 700.0), 90.0)
    seat('seat_gunner_l', (-1420.0, -700.0), -90.0)
    seat('seat_gunner_r', (-1420.0, 700.0), 90.0)
    for i, y in enumerate((-795.0, -265.0, 265.0, 795.0)):     # the rear row, facing forward, their backs to the bulkhead
        seat(f'seat_rear_{i}', (1150.0, y), 180.0)

    # ---------------------------------------------------------------- the floor
    tracks, pans, rings_ = [], [], []
    for y in (-936.0, -464.0, 464.0, 936.0):                   # seat tracks: a lipped channel, flush, its slot dark
        tracks.append([[Vector((x, y + dy, dz)) for dy, dz in ((-17.0, -1.0), (17.0, -1.0), (17.0, 2.2), (6.0, 2.2), (6.0, 0.6), (-6.0, 0.6), (-6.0, 2.2), (-17.0, 2.2))]
                       for x in (D.X_CABIN0 + 30.0, D.X_CABIN1 - 30.0)])
    hs.finish(hs.skins('floor_seat_tracks', tracks), 0.0, STEEL)
    for x in stations(-2150.0, 1290.0, 508.0):
        for y in (-700.0, -235.0, 235.0, 700.0):
            if abs(x - 120.0) < 140.0 and abs(abs(y) - 700.0) < 1.0:
                continue                                       # (under the door seats' own fittings)
            c = Vector((x, y, 0.0))
            pans.append([hs.circle(c, (0, 0, 1), r_, h_, 20) for r_, h_ in ((58.0, -1.0), (58.0, 2.0), (50.0, 2.6), (44.0, 1.0), (44.0, -1.0))])
            ring_path = [c + Vector((30.0 * math.cos(a), 30.0 * math.sin(a), 5.5)) for a in [2 * math.pi * q / 16 for q in range(17)]]
            rings_.append(tube(ring_path[:-1] + [ring_path[0]], 4.5, seg=6))
    hs.finish(hs.skins('floor_lashing_pans', pans), 0.0, CLAY)
    hs.finish(hs.skins('floor_lashing_rings', rings_), 0.0, STEEL)
    for sgn, sd in ((1, 'r'), (-1, 'l')):                      # the sills' scuff plates, turned down over the edge
        y0, y1 = sgn * (D.W - D.WALL - 60.0), sgn * (D.W + 4.0)
        sec = [(D.DOOR_X0 + 8.0, 0.0), (D.DOOR_X1 - 8.0, 0.0)]
        prof = [(y0, -1.0), (y0, 3.0), (y1 - sgn * 6.0, 3.0), (y1, 0.0), (y1, D.DOOR_Z0 - 30.0), (y1 - sgn * 3.0, D.DOOR_Z0 - 30.0), (y1 - sgn * 3.0, -1.0)]
        hs.finish(hs.rings(f'sill_plate_{sd}', [[Vector((x, y, z)) for y, z in prof] for x, _ in sec]), 0.6, STEEL)

    # ---------------------------------------------------------------- overhead
    over = []
    for y in (-464.0, 464.0):
        over.append(tube([Vector((D.X_CABIN0 + 80.0, y, D.CEIL - 14.0)), Vector((D.X_CABIN1 - 60.0, y, D.CEIL - 14.0))], 13.0))
    # the bar across at the doors' forward end (clear of the head of whoever sits at a door)
    over.append(tube([Vector((-640.0, -1020.0, D.CEIL - 60.0)), Vector((-640.0, 1020.0, D.CEIL - 60.0))], 19.0, seg=14))
    for y in (-1020.0, 1020.0):
        over.append(tube([Vector((-640.0, y, D.CEIL - 60.0)), Vector((-640.0, y, D.CEIL))], 26.0, seg=12))
    hs.finish(hs.skins('ceiling_rails', over), 0.0, CLAY)
    lamps = []
    for x in (-1500.0, 600.0):
        lamps.append([hs.circle(Vector((x, 0.0, D.CEIL)), (0, 0, -1), r_, h_, 18) for r_, h_ in ((62.0, 0.0), (62.0, 14.0), (48.0, 26.0), (0.1, 30.0))])
    hs.finish(hs.skins('cabin_dome_lights', lamps), 0.0, GLASS)

    # ---------------------------------------------------------------- the cockpit
    for sgn, sd in ((1, 'r'), (-1, 'l')):
        yc = sgn * 560.0
        # the armoured seat: a bucket (pan, back, two wings) on its rails; cushions; a headrest
        side_o = bt.round_poly([(-3270.0, 300.0), (-2880.0, 300.0), (-2836.0, 360.0), (-2748.0, 1020.0), (-2800.0, 1060.0), (-2840.0, 1040.0),
                                (-2930.0, 420.0), (-3270.0, 396.0)], 30.0, 4)
        bucket = hs.rings(f'pilot_seat_bucket_{sd}', [[Vector((x, yc + dy, z)) for x, z in side_o] for dy in (-250.0, 250.0)])
        hs.finish(bucket, 8.0, CLAY)
        for sw in (-1, 1):                                     # the wings: armour plates standing proud of the bucket's sides
            wing = bt.round_poly([(-3180.0, 330.0), (-2850.0, 330.0), (-2750.0, 1010.0), (-2800.0, 1040.0), (-3040.0, 760.0), (-3190.0, 560.0)], 40.0, 4)
            y_ = yc + sw * 262.0
            hs.finish(hs.rings(f'pilot_seat_wing_{sd}_{sw}', [[Vector((x, y_ + dy, z)) for x, z in wing] for dy in (-9.0, 9.0)]), 3.0, CLAY)
        cush = bt.round_poly([(-3250.0, 396.0), (-2940.0, 420.0), (-2944.0, 470.0), (-3250.0, 452.0)], 18.0, 4)
        bt.finish_smooth(hs.rings(f'pilot_seat_cushion_{sd}', [[Vector((x, yc + dy, z)) for x, z in cush] for dy in (-225.0, 225.0)]), FABRIC, sharp_deg=40.0)
        bcush = bt.round_poly([(-2938.0, 440.0), (-2858.0, 1000.0), (-2906.0, 1010.0), (-2992.0, 452.0)], 18.0, 4)
        bt.finish_smooth(hs.rings(f'pilot_seat_back_cushion_{sd}', [[Vector((x, yc + dy, z)) for x, z in bcush] for dy in (-215.0, 215.0)]), FABRIC, sharp_deg=40.0)
        head = bt.round_poly([(-2846.0, 1030.0), (-2816.0, 1180.0), (-2876.0, 1190.0), (-2908.0, 1034.0)], 20.0, 4)
        bt.finish_smooth(hs.rings(f'pilot_seat_headrest_{sd}', [[Vector((x, yc + dy, z)) for x, z in head] for dy in (-130.0, 130.0)]), FABRIC, sharp_deg=40.0)
        rails = [tube([Vector((-3260.0, yc + dy, 20.0)), Vector((-2800.0, yc + dy, 20.0))], 16.0) for dy in (-200.0, 200.0)]
        rails += [tube([Vector((x, yc + dy, 20.0)), Vector((x + 30.0, yc + dy, 318.0))], 14.0) for dy in (-200.0, 200.0) for x in (-3220.0, -2920.0)]
        hs.finish(hs.skins(f'pilot_seat_rails_{sd}', rails), 0.0, CLAY)
        # the cyclic stick and the collective lever
        sticks = [tube([Vector((-3330.0, yc, 10.0)), Vector((-3350.0, yc, 330.0)), Vector((-3300.0, yc, 520.0))], 12.0, bend=80.0),
                  tube([Vector((-2960.0, yc - sgn * 0.0 - 300.0, 60.0)), Vector((-3190.0, yc - 300.0, 300.0))], 14.0)]
        hs.finish(hs.skins(f'pilot_controls_{sd}', sticks), 0.0, DARK)
        grip = bt.round_poly([(-3322.0, 505.0), (-3282.0, 510.0), (-3270.0, 640.0), (-3312.0, 646.0)], 14.0, 4)
        bt.finish_smooth(hs.rings(f'cyclic_grip_{sd}', [[Vector((x, yc + dy, z)) for x, z in grip] for dy in (-19.0, 19.0)]), DARK, sharp_deg=40.0)
    # the instrument panel under its glare shield (as wide as the windshields leave room for at each station); the
    # console; the overhead console
    hood = bt.round_poly([(-3745.0, 608.0), (-3470.0, 840.0), (-3440.0, 824.0), (-3452.0, 798.0), (-3500.0, 790.0), (-3725.0, 592.0)], 10.0, 3)
    hs.finish(hs.rings('glare_shield', [[Vector((x, s_ * (430.0 + 90.0 * (x + 3745.0) / 305.0), z)) for x, z in hood] for s_ in (-1.0, 1.0)]), 4.0, DARK)
    face = [(-3492.0, 786.0), (-3560.0, 480.0), (-3640.0, 480.0), (-3640.0, 660.0), (-3520.0, 790.0)]
    hs.finish(hs.rings('instrument_panel', [[Vector((x, y, z)) for x, z in face] for y in (-600.0, 600.0)]), 3.0, DARK)
    screens = []
    for yc_ in (-470.0, -255.0, 255.0, 470.0):                 # four displays, standing a little proud, tilted with the face
        screens.append([[Vector((-3492.0 - 68.0 * (786.0 - z) / 306.0 + 3.0 + dx, yc_ + dy, z)) for dy, z in ((-92.0, 560.0), (92.0, 560.0), (92.0, 745.0), (-92.0, 745.0))]
                        for dx in (0.0, 5.0)])
    hs.finish(hs.skins('instrument_displays', screens), 1.0, GLASS)
    cons = bt.round_poly([(-3560.0, 0.0), (-2900.0, 0.0), (-2900.0, 420.0), (-3010.0, 470.0), (-3540.0, 520.0)], 14.0, 3)
    hs.finish(hs.rings('centre_console', [[Vector((x, y, z)) for x, z in cons] for y in (-165.0, 165.0)]), 4.0, DARK)
    hs.finish(hs.box('overhead_console', (-3080.0, -190.0, 1372.0), (-2520.0, 190.0, 1432.0)), 10.0, DARK)
