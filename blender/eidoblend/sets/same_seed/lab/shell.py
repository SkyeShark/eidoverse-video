"""eidoblend.sets.same_seed.lab.shell: the lab's shell (Blender): the walls, the WINDOW WALL (frames, panes, two opening
sashes, the board, five roller blinds, two panel radiators), the hung tile ceiling and its fittings, the skirting, the
floor box. Millimetres; the room's own space: x across, y to the window wall, z up from the floor.

A research office on an upper floor, a lab full of light: the whole back wall above the sill is ONE RIBBON OF GLAZING,
white plaster, a hung tile ceiling, radiators under the sill. The lenses look along +y, so this wall is behind every
shot and gets real sections: a glazed wall is a panel assembly (panes in gaskets in beads in frames); its trim, seats
and terminals are explicit. Five bays, unequal, with no frame member where a head stands in the close shots (x -500 ..
900): a wide fixed pane there, an opening sash on each side of it (one tilted open, its stay holding it), a fixed pane to
each end; face-fixed roller blinds over the head; two steel panel radiators (two panels deep, fluted fronts, punched
grilles, a thermostatic valve and a lockshield, fed from the floor); a 600 mm T-grid ceiling of tegular tiles with
eight LED panels, a square air diffuser, four sprinklers and a smoke detector.
"""

import math

X0, X1, Y0, Y1, HT = -4000.0, 4000.0, -2000.0, 3000.0, 2800.0
TW, TB = 150.0, 320.0                                          # a partition; the outside wall
WX0, WX1, WZ0, WZ1 = -3600.0, 3600.0, 870.0, 2500.0            # the ribbon's masonry opening
YF, FD, FB = Y1 + 190.0, 70.0, 40.0                            # the frames' room face (a 190 mm reveal), their depth, a frame body's face
BAYS = [(-3600.0, -1900.0, 'fixed'), (-1900.0, -1000.0, 'tilt'), (-1000.0, 1400.0, 'fixed'), (1400.0, 2300.0, 'turn'), (2300.0, 3600.0, 'fixed')]
BLIND_HEM = [2536.0, 2536.0, 1960.0, 1500.0, 1250.0]           # each blind's hem: up where the plants and the open sash are, lower toward the screen
TILT = 5.5                                                      # the tilted sash, degrees (its head 150 mm into the room)
AX, AZ, AN = (1, 0, 0), (0, 0, 1), (0, -1, 0)                   # the window wall's own axes: along, up, proud toward the room
RADIATORS = ((-3250.0, -1650.0), (600.0, 2200.0))               # x extents of the two radiators
FBX, FBY = 2000.0, 1440.0                                      # the floor box, between the bench's middle legs and its pedestal


def build(hs, K, CLAY, DARK):
    """every part of the shell into hs.col"""
    V3 = K.V3
    # ------------------------------------------------------------------------------------- walls, floor, slab
    back = hs.box('wall_back', (X0 - TW, Y1, 0.0), (X1 + TW, Y1 + TB, HT + 300.0))
    back = hs.boolean(back, hs.box('window_opening', (WX0, Y1 - 50.0, WZ0), (WX1, Y1 + TB + 50.0, WZ1)), 'DIFFERENCE')
    hs.finish(back, 3.0, CLAY)                                 # (a plastered arris: a 3 mm round, not a knife)
    hs.finish(hs.box('wall_left', (X0 - TW, Y0 - TW, 0.0), (X0, Y1, HT + 300.0)), 0.0, CLAY)
    hs.finish(hs.box('wall_right', (X1, Y0 - TW, 0.0), (X1 + TW, Y1, HT + 300.0)), 0.0, CLAY)
    hs.finish(hs.box('wall_front_unseen', (X0, Y0 - TW, 0.0), (X1, Y0, HT + 300.0)), 0.0, CLAY)     # (hidden from the camera only)
    hs.finish(hs.box('room_floor', (X0 - TW, Y0 - TW, -150.0), (X1 + TW, Y1 + TB, 0.0)), 0.0, CLAY)
    hs.finish(hs.box('room_slab', (X0 - TW, Y0 - TW, HT + 300.0), (X1 + TW, Y1 + TB, HT + 500.0)), 0.0, CLAY)   # the floor above: it shuts the void over the tiles
    # the skirting: 95 x 15 with a round top, one run along the right wall, the window wall and the left wall, mitred in
    # the two corners
    SKIRT = [(0.0, 0.0), (15.0, 0.0), (15.0, 89.0), (14.2, 92.0), (12.0, 94.2), (9.0, 95.0), (0.0, 95.0)]
    hs.finish(K.mitred('skirting', [V3(X1, Y0, 0), V3(X1, Y1, 0), V3(X0, Y1, 0), V3(X0, Y0, 0)], SKIRT), 0.0, CLAY)

    # ----------------------------------------------------------------------------------------- the window wall
    # the board: 30 thick, its nose rounded and 40 into the room, with horns past the reveal; it butts the frames' face
    nose = [(YF, 870.0), (Y1 - 36.0, 870.0), (Y1 - 40.0, 874.0), (Y1 - 40.0, 888.0)]
    nose += [(Y1 - 28.0 - 12.0 * math.cos(math.radians(a)), 888.0 + 12.0 * math.sin(math.radians(a))) for a in (22.5, 45.0, 67.5, 90.0)]
    nose += [(YF, 900.0)]
    board = hs.prism_section('window_board', nose, WX0 - 30.0, WX1 + 30.0)
    board = hs.boolean(board, hs.prism_plan('board_plan', [(WX0 - 30.0, Y1 - 50.0), (WX1 + 30.0, Y1 - 50.0), (WX1 + 30.0, Y1), (WX1, Y1), (WX1, YF + 10.0),
                                                           (WX0, YF + 10.0), (WX0, Y1), (WX0 - 30.0, Y1)], 860.0, 910.0), 'INTERSECT')
    hs.finish(board, 1.0, CLAY)
    # the pressed sill outside, seen through the glass along the panes' foot
    hs.finish(hs.prism_section('window_sill_outside', [(YF + FD - 4.0, 872.0), (Y1 + TB + 35.0, 858.0), (Y1 + TB + 35.0, 838.0), (Y1 + TB + 33.0, 838.0),
                                                       (Y1 + TB + 33.0, 856.0), (YF + FD - 4.0, 870.0)], WX0, WX1), 0.0, CLAY)
    # the frame: one body round the opening, a mullion body at each bay's edge; each pane in its own bead (room side)
    # and leg (weather side), a gasket between bead and glass
    WCZ, WHH = (WZ0 + WZ1) / 2.0, (WZ1 - WZ0) / 2.0
    hs.finish(K.frame_loop('window_frame', (0.0, YF, WCZ), AX, AZ, AN, (WX1 - WX0) / 2.0, WHH, [(0.0, 0.0), (-FB, 0.0), (-FB, -FD), (0.0, -FD)]), 0.8, CLAY)
    hs.finish(K.boxes('window_mullions', [((b[0] - 15.0, YF, WZ0 + FB), (b[0] + 15.0, YF + FD, WZ1 - FB)) for b in BAYS[1:]]), 0.8, CLAY)
    BEAD = [(0.0, -1.5), (-13.0, -1.5), (-15.0, -3.5), (-15.0, -22.0), (0.0, -22.0)]          # (set 1.5 back from the body's face: its own shadow line)
    LEG = [(0.0, -50.0), (-15.0, -50.0), (-15.0, -70.0), (0.0, -70.0)]
    GASKET = [(-12.5, -22.0), (-16.5, -22.0), (-16.5, -25.0), (-12.5, -25.0)]
    # an opening sash: it laps the frame's face by 10, stands 18 proud of it, and holds its own pane
    SASH = [(10.0, 1.0), (10.0, 18.0), (-48.0, 18.0), (-50.0, 16.0), (-50.0, -4.0), (-35.0, -4.0), (-35.0, -32.0), (-50.0, -32.0), (-50.0, -52.0), (-6.0, -52.0), (-6.0, 1.0)]
    SASH_GASKET = [(-47.5, -4.0), (-51.5, -4.0), (-51.5, -7.0), (-47.5, -7.0)]

    def bay_rect(i):
        """the daylight a bay's bodies leave: x0, x1, z0, z1"""
        xl, xr, _kind = BAYS[i]
        return xl + (FB if i == 0 else 15.0), xr - (FB if i == len(BAYS) - 1 else 15.0), WZ0 + FB, WZ1 - FB

    def tilted(p, pivot, deg):
        """a point turned about the +x axis through the pivot (the sash's foot): its head comes INTO the room (-y)"""
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        y, z = p[1] - pivot[1], p[2] - pivot[2]
        return V3(p[0], pivot[1] + y * c - z * s, pivot[2] + y * s + z * c)

    beads, gaskets, panes, caps = [], [], [], []
    for i, (xl, xr, kind) in enumerate(BAYS):
        bx0, bx1, bz0, bz1 = bay_rect(i)
        C, hw, hh = V3((bx0 + bx1) / 2.0, YF, (bz0 + bz1) / 2.0), (bx1 - bx0) / 2.0, (bz1 - bz0) / 2.0
        if kind == 'fixed':
            beads += [K.loop_rings(C, AX, AZ, AN, hw, hh, BEAD), K.loop_rings(C, AX, AZ, AN, hw, hh, LEG)]
            gaskets.append(K.loop_rings(C, AX, AZ, AN, hw, hh, GASKET))
            panes.append(((bx0 + 5.0, YF + 25.0, bz0 + 5.0), (bx1 - 5.0, YF + 49.0, bz1 - 5.0)))
            continue
        # an opening sash (tilt-and-turn): hung on the left, its handle on the right stile; the handle points DOWN when
        # it is shut and UP when it is tilted (the hardware says what state the window is in)
        up = kind == 'tilt'
        pv = (C.x, YF, bz0 - 10.0)                             # the hinge line: the sash's foot on the frame's face
        hx, hz = bx1 - 20.0, 1480.0
        made = [hs.finish(K.frame_loop(f'window_sash_{i}_frame', C, AX, AZ, AN, hw, hh, SASH), 0.8, CLAY),
                hs.finish(K.frame_loop(f'window_sash_{i}_gasket', C, AX, AZ, AN, hw, hh, SASH_GASKET), 0.0, DARK),
                hs.finish(hs.box(f'window_sash_{i}_glass', (bx0 + 39.0, YF + 7.0, bz0 + 39.0), (bx1 - 39.0, YF + 29.0, bz1 - 39.0)), 0.0, DARK),
                hs.finish(hs.prism_side(f'window_sash_{i}_handle_rose', hs.rrect(hx - 14.0, hz - 33.0, hx + 14.0, hz + 33.0, 13.0, n=5), YF - 27.0, YF - 18.0), 1.2, CLAY),
                hs.finish(hs.cyl(f'window_sash_{i}_handle_neck', (hx, YF - 26.0, hz), (hx, YF - 47.0, hz), 15.0, seg=24), 0.0, CLAY),
                hs.finish(hs.prism_side(f'window_sash_{i}_handle', hs.rrect(hx - 10.5, hz - 13.0 if up else hz - 126.0, hx + 10.5, hz + 126.0 if up else hz + 13.0, 10.0, n=6),
                                        YF - 58.0, YF - 46.0), 2.5, CLAY)]
        if up:
            for o_ in made:
                K.turn(o_, pv, (1, 0, 0), TILT)
            # the stay that holds a tilted sash: a flat arm from the frame's head to the sash's head, on the hinge side
            a = V3(bx0 + 30.0, YF + 16.0, bz1 + 2.0)
            b = tilted((bx0 + 300.0, YF + 16.0, bz1 - 16.0), pv, TILT)
            hs.finish(hs.sweep(f'window_sash_{i}_stay', [a, b], [(-8.0, -1.5), (8.0, -1.5), (8.0, 1.5), (-8.0, 1.5)], up=(1, 0, 0)), 0.4, CLAY)
        # the two corner bearings' covers, on the mullion's face beside the hinge stile (clear of the sash's own edge)
        caps += [((bx0 - 30.0, YF - 20.0, bz0 + 20.0), (bx0 - 12.0, YF + 0.5, bz0 + 110.0)), ((bx0 - 30.0, YF - 20.0, bz1 - 110.0), (bx0 - 12.0, YF + 0.5, bz1 - 20.0))]
    hs.finish(K.loops('window_beads', beads), 0.0, CLAY)
    hs.finish(K.loops('window_gaskets', gaskets), 0.0, DARK)
    hs.finish(K.boxes('window_glass', panes), 0.0, DARK)
    hs.finish(K.boxes('window_hinge_covers', caps), 2.0, CLAY)

    # -------------------------------------------------------------------------------------- the roller blinds
    # face-fixed on the wall over the head, so a sash can tilt behind a drawn blind: a 38 mm tube in two brackets, the
    # cloth rolled on it and hanging from its WALL side, a flat-oval hem bar, an endless cord at the right end
    def cord(name, pts, r=1.3, seg=8, closed=True):
        rl = [[p + n * (r * math.cos(2 * math.pi * k / seg)) + b * (r * math.sin(2 * math.pi * k / seg)) for k in range(seg)] for p, t, n, b in K.pt_frames(pts, (1, 0, 0))]
        if closed:
            return K.loops(name, [rl + [rl[0]]])
        return hs.rings(name, rl)

    def blind(i, hem):
        xl, xr, _kind = BAYS[i]
        xa = xl - 60.0 if i == 0 else xl + 5.0                 # as wide as its bay; the two end ones lap the reveal by 60
        xb = xr + 60.0 if i == len(BAYS) - 1 else xr - 5.0
        ya, za = Y1 - 48.0, 2590.0                             # the tube's axis
        r = math.sqrt(19.0 ** 2 + max(0.0, 1750.0 - (za - hem)) * 0.55 / math.pi)       # the tube and what is still rolled on it
        yf = ya + r                                            # the cloth leaves the roll on the wall side
        hs.finish(hs.cyl(f'blind_{i}_roll', (xa + 18.0, ya, za), (xb - 22.0, ya, za), 2.0 * r, seg=40), 0.0, CLAY)
        hs.finish(hs.box(f'blind_{i}_cloth', (xa + 20.0, yf - 0.3, hem), (xb - 24.0, yf + 0.3, za)), 0.0, CLAY)
        hs.finish(hs.prism_section(f'blind_{i}_hem_bar', hs.rrect(yf - 4.5, hem - 14.0, yf + 4.5, hem + 10.0, 4.4, n=4), xa + 17.0, xb - 21.0), 0.6, CLAY)
        # the idle end's plug, the control end's cord wheel in its housing, and the two brackets on the wall
        hs.finish(hs.revolve(f'blind_{i}_end_plug', [(0.0, 0.0), (15.0, 0.0), (15.0, 5.0), (13.0, 6.0), (0.0, 6.0)], at=V3(xa + 18.0, ya, za), axis=(-1, 0, 0), seg=32), 0.0, CLAY)
        hs.finish(hs.revolve(f'blind_{i}_cord_wheel', [(0.0, 0.0), (26.0, 0.0), (28.0, 2.0), (28.0, 17.0), (26.0, 19.0), (0.0, 19.0)], at=V3(xb - 22.0, ya, za), axis=(1, 0, 0),
                             seg=40), 0.0, CLAY)
        br = []
        for xw in (xa + 9.0, xb - 3.0):
            br += [((xw - 20.0, Y1 - 2.0, za - 30.0), (xw + 20.0, Y1, za + 30.0)), ((xw - 1.0, ya - 24.0, za - 22.0), (xw + 1.0, Y1 - 2.0, za + 22.0))]
        hs.finish(K.boxes(f'blind_{i}_brackets', br), 0.3, CLAY)
        xc, zb = xb - 12.0, 1330.0 + 40.0 * (i % 2)
        loop = [V3(xc, ya - 15.0 * math.cos(math.radians(a)), zb - 15.0 * math.sin(math.radians(a))) for a in range(0, 181, 15)]     # down the room side, round, up the wall side
        loop += [V3(xc, ya + 15.0 * math.cos(math.radians(a)), za + 15.0 * math.sin(math.radians(a))) for a in range(0, 181, 15)]    # and over the wheel
        hs.finish(cord(f'blind_{i}_cord', loop), 0.0, CLAY)

    for i, hem in enumerate(BLIND_HEM):
        blind(i, hem)

    # -------------------------------------------------------------------------------- the radiators under the board
    # a steel panel radiator, two panels deep (100 mm): a front panel pressed in upright flutes a third of a decimetre
    # apart, a punched grille on top, a cover at each end, a thermostatic valve at one foot and a lockshield at the
    # other, each on its pipe out of the floor through a collar (it hangs on the wall and is fed from the floor)
    def radiator(k, xa, xb, z0=170.0, h=500.0):
        yb = Y1 - 38.0                                         # the back panel's rear: 38 off the wall, on its brackets
        yf = yb - 100.0
        n = int(round((xb - xa - 30.0) / 33.33))
        pitch = (xb - xa - 30.0) / n
        out = [(xa, yf + 12.0), (xa, yf)]
        for i in range(n):
            xm = xa + 15.0 + pitch * (i + 0.5)
            out += [(xm - 7.0, yf), (xm - 2.5, yf + 3.5), (xm + 2.5, yf + 3.5), (xm + 7.0, yf)]
        out += [(xb, yf), (xb, yf + 12.0)]
        hs.finish(hs.prism_plan(f'radiator_{k}_front', out, z0 + 12.0, z0 + h - 12.0), 1.2, CLAY)
        hs.finish(hs.box(f'radiator_{k}_back', (xa, yb - 12.0, z0 + 12.0), (xb, yb, z0 + h - 12.0)), 1.2, CLAY)
        hs.finish(hs.box(f'radiator_{k}_fins_dark', (xa + 20.0, yf + 14.0, z0 + 30.0), (xb - 20.0, yb - 14.0, z0 + h - 30.0)), 0.0, DARK)
        hs.finish(K.boxes(f'radiator_{k}_ends', [((xa - 1.2, yf + 2.0, z0 + 5.0), (xa, yb - 2.0, z0 + h - 2.0)), ((xb, yf + 2.0, z0 + 5.0), (xb + 1.2, yb - 2.0, z0 + h - 2.0)),
                                                 ((xa - 1.2, yf - 1.2, z0 + h - 15.0), (xb + 1.2, yf, z0 + h - 1.5)), ((xa - 1.2, yb, z0 + h - 15.0), (xb + 1.2, yb + 1.2, z0 + h - 1.5))]),
                  0.3, CLAY)
        us = [xa - 1.2, xa + 22.0]
        while us[-1] + 16.0 < xb - 22.0:
            us += [us[-1] + 6.0, us[-1] + 16.0]
        us = us[:-1] if len(us) % 2 == 1 else us               # (ends on a bar, not on a slot)
        us.append(xb + 1.2)
        vs = [yf - 1.2, yf + 9.0, yf + 43.0, yf + 57.0, yf + 91.0, yb + 1.2]
        hs.finish(K.plate(f'radiator_{k}_grille', us, vs, lambda i, j: not (j in (1, 3) and i % 2 == 1 and 0 < i < len(us) - 2), z0 + h - 1.5, z0 + h), 0.0, CLAY)
        yv, zv = yb - 50.0, z0 + 32.0
        hs.finish(hs.revolve(f'radiator_{k}_valve', [(0.0, 0.0), (9.0, 0.0), (9.0, 26.0), (14.0, 28.0), (14.0, 48.0), (11.0, 50.0), (11.0, 56.0), (21.0, 58.0), (25.0, 62.0),
                                                     (25.0, 118.0), (23.0, 132.0), (18.0, 138.0), (0.0, 138.0)], at=V3(xb + 1.0, yv, zv), axis=(1, 0, 0), seg=40), 0.0, CLAY)
        hs.finish(hs.revolve(f'radiator_{k}_lockshield', [(0.0, 0.0), (9.0, 0.0), (9.0, 26.0), (14.0, 28.0), (14.0, 46.0), (10.0, 48.0), (10.0, 58.0), (8.0, 60.0), (0.0, 60.0)],
                             at=V3(xa - 1.0, yv, zv), axis=(-1, 0, 0), seg=40), 0.0, CLAY)
        sk = []
        for xp in (xb + 39.0, xa - 38.0):
            hs.finish(hs.cyl(f'radiator_{k}_pipe_{int(xp > xa)}', (xp, yv, -20.0), (xp, yv, zv + 6.0), 15.0, seg=24), 0.0, CLAY)
            sk.append([hs.circle(V3(xp, yv, 0.0), (0, 0, 1), 22.0, 0.0, 32), hs.circle(V3(xp, yv, 0.0), (0, 0, 1), 22.0, 2.5, 32), hs.circle(V3(xp, yv, 0.0), (0, 0, 1), 12.0, 7.0, 32)])
        hs.finish(hs.skins(f'radiator_{k}_floor_collars', sk), 0.0, CLAY)

    for k, (xa, xb) in enumerate(RADIATORS):
        radiator(k, xa, xb)

    # ------------------------------------------------------------------------------------------------ the ceiling
    # a hung tile ceiling: a 24 mm T grid at 600, laid out from the room's middle so the cut tiles at opposite walls are
    # equal (400 at every wall), a wall angle round the room, TEGULAR tiles (their faces hang 6 mm below the grid, so
    # every grid line is a real groove), eight lay-in LED panels, an air diffuser, sprinklers, a smoke detector
    GXS = [-3600.0 + 600.0 * i for i in range(13)]
    GYS = [-1600.0 + 600.0 * j for j in range(8)]
    ZG = HT + 0.8                                              # the grid rests on the wall angle
    hs.finish(K.mitred('ceiling_wall_angle', [V3(X0, Y0, HT), V3(X1, Y0, HT), V3(X1, Y1, HT), V3(X0, Y1, HT)],
                       [(0.0, 0.0), (24.0, 0.0), (24.0, 0.8), (0.8, 0.8), (0.8, 22.0), (0.0, 22.0)], closed=True), 0.0, CLAY)
    TEE = [(-12.0, 0.0), (12.0, 0.0), (12.0, 0.8), (0.5, 0.8), (0.5, 38.0), (-0.5, 38.0), (-0.5, 0.8), (-12.0, 0.8)]
    sk = [[[V3(x, gy + u, ZG + v) for u, v in TEE] for x in (X0 + 1.0, X1 - 1.0)] for gy in GYS]                    # the main runners, wall to wall
    ycuts = [Y0 + 1.0] + [v for gy in GYS for v in (gy - 12.0, gy + 12.0)] + [Y1 - 1.0]
    for gx in GXS:                                             # the cross tees, cut between the runners
        for ya_, yb_ in zip(ycuts[0::2], ycuts[1::2]):
            sk.append([[V3(gx + u, y, ZG + v) for u, v in TEE] for y in (ya_, yb_)])
    hs.finish(hs.skins('ceiling_grid', sk), 0.0, CLAY)
    CX = [X0] + GXS + [X1]
    CY = [Y0] + GYS + [Y1]
    PANELS = {(i, j) for i in (2, 5, 8, 11) for j in (2, 5)}   # cells whose middle is x = -2700, -900, 900, 2700; y = -700, 1100
    DIFFUSER, SPRINKLERS, DETECTOR = (6, 6), ((4, 4), (9, 4), (4, 1), (9, 1)), (7, 3)
    tiles, frames_, diffs, backs = [], [], [], []
    for i in range(len(CX) - 1):
        for j in range(len(CY) - 1):
            xa, xb, ya_, yb_ = CX[i], CX[i + 1], CY[j], CY[j + 1]
            # what each edge rests on: the wall angle (24 wide, from the wall) or half a tee (12, from the grid line)
            ex0, ex1 = (24.0 if i == 0 else 12.0), (24.0 if i == len(CX) - 2 else 12.0)
            ey0, ey1 = (24.0 if j == 0 else 12.0), (24.0 if j == len(CY) - 2 else 12.0)
            cx, cy = (xa + xb) / 2.0, (ya_ + yb_) / 2.0
            if (i, j) in PANELS:
                C = V3(cx, cy, ZG + 0.8)
                frames_.append(K.loop_rings(C, (1, 0, 0), (0, 1, 0), (0, 0, -1), (xb - xa) / 2.0 - 3.0, (yb_ - ya_) / 2.0 - 3.0,
                                            [(0.0, 0.0), (-14.0, 0.0), (-14.0, -1.5), (-11.0, -1.5), (-11.0, -10.0), (0.0, -10.0)]))
                diffs.append(((xa + 15.0, ya_ + 15.0, ZG + 2.3), (xb - 15.0, yb_ - 15.0, ZG + 4.8)))
                backs.append(((xa + 13.0, ya_ + 13.0, ZG + 4.8), (xb - 13.0, yb_ - 13.0, ZG + 10.8)))
                continue
            if (i, j) == DIFFUSER:
                continue
            fx0, fx1, fy0, fy1 = xa + ex0 + 1.5, xb - ex1 - 1.5, ya_ + ey0 + 1.5, yb_ - ey1 - 1.5       # the face that hangs between the flanges
            bx0, bx1, by0, by1 = xa + 3.0, xb - 3.0, ya_ + 3.0, yb_ - 3.0                                 # the body that lies on them
            tiles.append([[V3(fx0, fy0, HT - 6.0), V3(fx1, fy0, HT - 6.0), V3(fx1, fy1, HT - 6.0), V3(fx0, fy1, HT - 6.0)],
                          [V3(fx0, fy0, ZG + 0.8), V3(fx1, fy0, ZG + 0.8), V3(fx1, fy1, ZG + 0.8), V3(fx0, fy1, ZG + 0.8)],
                          [V3(bx0, by0, ZG + 0.8), V3(bx1, by0, ZG + 0.8), V3(bx1, by1, ZG + 0.8), V3(bx0, by1, ZG + 0.8)],
                          [V3(bx0, by0, ZG + 16.0), V3(bx1, by0, ZG + 16.0), V3(bx1, by1, ZG + 16.0), V3(bx0, by1, ZG + 16.0)]])
    hs.finish(hs.skins('ceiling_tiles', tiles), 1.0, CLAY)
    hs.finish(K.loops('ceiling_panel_frames', frames_), 0.0, CLAY)
    hs.finish(K.boxes('ceiling_panel_diffusers', diffs), 0.0, CLAY)
    hs.finish(K.boxes('ceiling_panel_backs', backs), 0.0, CLAY)

    def cell_mid(c):
        return (CX[c[0]] + CX[c[0] + 1]) / 2.0, (CY[c[1]] + CY[c[1] + 1]) / 2.0

    # the air diffuser: a lay-in square of four nested cones round a middle pan, each cone a pressed blade leaning out
    dx, dy = cell_mid(DIFFUSER)
    rl = [K.loop_rings(V3(dx, dy, ZG + 0.8), (1, 0, 0), (0, 1, 0), (0, 0, -1), 297.0, 297.0, [(0.0, 0.0), (-22.0, 0.0), (-22.0, -1.2), (0.0, -1.2)])]
    for k in range(4):
        hwk = 262.0 - 62.0 * k
        rl.append(K.loop_rings(V3(dx, dy, ZG + 0.8), (1, 0, 0), (0, 1, 0), (0, 0, -1), hwk, hwk, [(0.0, 4.0), (-34.0, -24.0), (-35.0, -23.2), (-1.0, 4.8)]))
    hs.finish(K.loops('ceiling_diffuser', rl), 0.0, CLAY)
    hs.finish(hs.box('ceiling_diffuser_pan', (dx - 42.0, dy - 42.0, ZG - 3.0), (dx + 42.0, dy + 42.0, ZG - 1.8)), 0.3, CLAY)
    hs.finish(hs.box('ceiling_diffuser_neck_dark', (dx - 290.0, dy - 290.0, ZG + 24.0), (dx + 290.0, dy + 290.0, ZG + 30.0)), 0.0, DARK)
    # sprinklers (an escutcheon, the frame, the deflector) and the smoke detector, each let into its tile's middle
    for k, c in enumerate(SPRINKLERS):
        sx, sy = cell_mid(c)
        hs.finish(hs.revolve(f'ceiling_sprinkler_{k}', [(0.0, 6.0), (35.0, 6.0), (35.0, 0.0), (33.0, -2.0), (16.0, -4.0), (11.0, -6.0), (11.0, -20.0), (6.0, -24.0), (4.0, -36.0),
                                                        (13.0, -37.0), (13.0, -38.5), (0.0, -38.5)], at=V3(sx, sy, HT - 6.0), seg=32), 0.0, CLAY)
    sx, sy = cell_mid(DETECTOR)
    hs.finish(hs.revolve('ceiling_smoke_detector', [(0.0, 5.0), (52.0, 5.0), (52.0, -10.0), (50.0, -12.0), (49.0, -13.0), (49.0, -16.0), (50.0, -17.0), (50.0, -22.0), (44.0, -32.0),
                                                    (30.0, -40.0), (0.0, -42.0)], at=V3(sx, sy, HT - 6.0), seg=48), 0.0, CLAY)

    # ---------------------------------------------------------------------------------------------- the floor box
    # where the bench's power goes into the floor: a lid in its frame, a cable outlet at one edge
    hs.finish(K.frame_loop('floor_box_frame', (FBX, FBY, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1), 110.0, 110.0, [(0.0, -2.0), (0.0, 2.0), (-10.0, 2.0), (-10.0, -2.0)]), 0.3, CLAY)
    hs.finish(hs.box('floor_box_lid', (FBX - 100.0, FBY - 100.0, -2.0), (FBX + 100.0, FBY + 100.0, 1.2)), 0.3, CLAY)
    hs.finish(hs.prism_section('floor_box_outlet', [(FBY + 62.0, 1.2), (FBY + 100.0, 1.2), (FBY + 100.0, 9.0), (FBY + 92.0, 14.0), (FBY + 70.0, 14.0), (FBY + 62.0, 9.0)],
                               FBX - 34.0, FBX + 34.0), 1.5, CLAY)
