"""eidoblend.sets.same_seed.kitchen.shell: the kitchen's shell, window, door, trim and fixtures (Blender). Millimetres;
the room's own space (x across, y to the back wall, z up from the floor).

A family's eat-in kitchen in a timber-framed house: plastered walls, a 9 ft ceiling, a boxed SOFFIT over the cupboards
on the back wall, a TWIN DOUBLE-HUNG WINDOW over the sink (its casing mitred at the head and standing on the stool, the
stool notched round the jambs with its horns past the casing, the apron under it, the sashes in their tracks between
stop and parting bead, a sash lock and lifts, a roller shade drawn a hand's width in each half), a two-panel door to the
hall on the right wall (hung on three butts, a brass knob on its rose), colonial base boards with a shoe, two ceiling
fittings (a white pan, an opal glass bowl, a turned finial), a clock over the window at a few minutes past noon, the
light switch and three duplex sockets. Trim is modelled, seated and ended; every joint is what it is.

    shell.build(ns)          # ns: kit.begin()'s namespace; adds WCX, STOOL, frame_loop for the later groups
"""


def build(ns):
    (DARK, GLASS, HT, TW, TWB, V3, Vector, X0, X1, Y0, Y1, bx, fin, hs, math, offset2, rev, screw_skins) = (
        ns[k] for k in ('DARK', 'GLASS', 'HT', 'TW', 'TWB', 'V3', 'Vector', 'X0', 'X1', 'Y0', 'Y1', 'bx', 'fin', 'hs', 'math', 'offset2', 'rev',
                        'screw_skins'))
    # ============================================================================================ THE SHELL
    WCX = 900.0                                                   # the window's middle: behind him (he stands at x 900), over the sink
    FX0, FX1, FZ0, FZ1 = 110.0, 1690.0, 1090.0, 2079.0            # the window frame's outside
    JT, FD = 19.0, 165.0                                          # its jambs' thickness, its depth through the wall
    SILL, HEAD = 1114.0, 2060.0                                   # the sashes stand between these
    MUL0, MUL1 = 870.0, 930.0                                     # the mullion between the two units
    STOOL = 1112.0                                                # the stool's top (the room's "window sill")
    DY0, DY1, DZ0, DZ1 = 250.0, 1063.0, 10.0, 2042.0              # the door's leaf on the right wall: 813 x 2032 (2 ft 8 x 6 ft 8)

    back = hs.box('wall_back', (X0 - TW, Y1, 0.0), (X1 + TW, Y1 + TWB, HT))
    back = hs.boolean(back, hs.box('window_opening', (FX0 - 10.0, Y1 - 50.0, FZ0 - 5.0), (FX1 + 10.0, Y1 + TWB + 50.0, FZ1 + 6.0)), 'DIFFERENCE')
    fin(back)
    fin(hs.box('wall_left', (X0 - TW, Y0 - TW, 0.0), (X0, Y1, HT)))
    right = hs.box('wall_right', (X1, Y0 - TW, 0.0), (X1 + TW, Y1, HT))
    right = hs.boolean(right, hs.box('door_opening', (X1 - 50.0, DY0 - 25.0, -50.0), (X1 + TW + 50.0, DY1 + 25.0, DZ1 + 28.0)), 'DIFFERENCE')
    fin(right)
    fin(hs.box('wall_front_unseen', (X0, Y0 - TW, 0.0), (X1, Y0, HT)))      # (the look hides it from the camera only)
    fin(hs.box('room_floor', (X0 - TW, Y0 - TW, -150.0), (X1 + TW, Y1 + TWB, 0.0)))
    fin(hs.box('room_ceiling', (X0 - TW, Y0 - TW, HT), (X1 + TW, Y1 + TWB, HT + 200.0)))
    # the soffit: a framed, plastered box closing the space over the wall cupboards (their tops at 2438), the back wall's
    # whole length; its lower arris is a plasterer's corner bead
    SOF_Z, SOF_D = 2438.0, 355.0
    fin(hs.box('soffit', (X0 - 3.0, Y1 - SOF_D, SOF_Z), (X1 + 3.0, Y1 + 3.0, HT + 3.0)), 3.0)


    def PB(a, z, v):
        """on the back wall: a along x; v proud of the plaster, toward the room"""
        return V3(a, Y1 - v, z)


    def PBin(a, z, v):
        """in the window's frame: v its depth behind the plaster"""
        return V3(a, Y1 + v, z)


    def PR(a, z, v):
        """on the right wall: a along y; v proud of the plaster, toward the room"""
        return V3(X1 - v, a, z)


    def PRin(a, z, v):
        return V3(X1 + v, a, z)


    def u_loop(name, a0, a1, bottom, top, prof, P):
        """a moulding up one side of an opening, across its head and down the other, MITRED at the two corners, its two
        ends cut square at `bottom`. prof [(u, v)]: u out from the opening's edge (negative: into the opening), v as P
        takes it"""
        rl = [[P(a + s * u, zt + sz * u, v) for u, v in prof] for a, s, zt, sz in ((a0, -1.0, bottom, 0.0), (a0, -1.0, top, 1.0), (a1, 1.0, top, 1.0), (a1, 1.0, bottom, 0.0))]
        return hs.rings(name, rl)


    def frame_loop(name, x0, x1, z0, z1, wl, wr, wb, wt, prof, P):
        """a frame round a rectangle, one section carried round it (a sash). prof [(a, v)]: a 0..1 across a member from its
        outer edge to its inner, v its depth; the members' widths: left wl, right wr, bottom wb, top wt"""
        rl = [[P(cx_ + sx * a * wx, cz_ + sz * a * wz, v) for a, v in prof]
              for cx_, sx, wx, cz_, sz, wz in ((x0, 1.0, wl, z0, 1.0, wb), (x1, -1.0, wr, z0, 1.0, wb), (x1, -1.0, wr, z1, -1.0, wt), (x0, 1.0, wl, z1, -1.0, wt))]
        return hs.rings(name, rl + [rl[0]], caps=False)


    def torus(name, at, axis, R, r, seg=32, n=12):
        ax = Vector(axis).normalized()
        big = hs.circle(at, ax, R, 0.0, seg)
        rl = []
        for k, p in enumerate(big):
            t = (big[(k + 1) % seg] - big[k - 1]).normalized()
            rl.append(hs.circle(p, t, r, 0.0, n, ax))
        return hs.rings(name, rl + [rl[0]], caps=False)


    # ============================================================================================ THE WINDOW
    # a wooden twin double-hung unit: two side jambs, a head, a sill and a mullion; in each half a lower sash in the inner
    # track and an upper in the outer, their meeting rails lapped; inside stops; the casing, stool and apron of the room
    fin(hs.box('window_jamb_l', (FX0, Y1, FZ0), (FX0 + JT, Y1 + FD, FZ1)), 0.8)
    fin(hs.box('window_jamb_r', (FX1 - JT, Y1, FZ0), (FX1, Y1 + FD, FZ1)), 0.8)
    fin(hs.box('window_head', (FX0 + JT, Y1, HEAD), (FX1 - JT, Y1 + FD, FZ1)), 0.8)
    fin(hs.box('window_sill', (FX0 + JT, Y1 + 50.0, FZ0), (FX1 - JT, Y1 + FD + 35.0, SILL)), 0.8)
    fin(hs.box('window_mullion', (MUL0, Y1, FZ0), (MUL1, Y1 + FD, HEAD)), 0.8)
    # (the casing: an inner bead, a hollow, a long swell to a back band; 70 wide: the same section round the door)
    CASING = [(0.0, 0.0), (0.0, 9.5), (1.5, 12.0), (4.5, 13.2), (8.0, 12.6), (11.0, 11.0), (15.0, 10.4), (20.0, 11.0), (34.0, 13.2), (48.0, 15.8), (57.0, 17.2), (63.0, 17.2), (67.0, 16.0),
              (69.5, 13.0), (70.0, 10.0), (70.0, 0.0)]
    SASH = [(0.0, 0.0), (0.78, 0.0), (0.84, 1.8), (0.92, 6.6), (1.0, 9.0), (1.0, 13.0), (0.8, 22.0), (0.8, 35.0), (0.0, 35.0)]     # (a, depth): ovolo inside, the glass, a putty line outside
    STOP = [(0.0, 12.0), (-8.5, 12.0), (-11.0, 14.5), (-11.0, 50.0), (0.0, 50.0)]
    fin(u_loop('window_casing', FX0 + JT - 5.0, FX1 - JT + 5.0, STOOL, HEAD + 5.0, CASING, PB), 0.0)
    fin(hs.box('window_mullion_casing', (MUL0 + 5.0, Y1 - 10.0, STOOL), (MUL1 - 5.0, Y1, HEAD + 5.0)), 1.5)
    # the stool: one board, notched round the jambs, its horns 20 past the casing, its nose 18 proud of it
    cx0, cx1 = FX0 + JT - 5.0 - 70.0, FX1 - JT + 5.0 + 70.0       # the casing's outer edges
    stool = hs.prism_plan('window_stool', [(cx0 - 20.0, Y1 - 35.0), (cx1 + 20.0, Y1 - 35.0), (cx1 + 20.0, Y1), (FX1 - JT, Y1), (FX1 - JT, Y1 + 50.0), (FX0 + JT, Y1 + 50.0),
                                           (FX0 + JT, Y1), (cx0 - 20.0, Y1)], STOOL - 19.0, STOOL)
    fin(stool, 3.0)
    fin(hs.prism_section('window_apron', [(Y1 - v, STOOL - 19.0 - (70.0 - u) * 57.0 / 70.0) for u, v in CASING], cx0, cx1), 0.0)
    hw_sk = []                                                    # the window's small hardware, one object
    for k, (a, b) in enumerate(((FX0 + JT, MUL0), (MUL1, FX1 - JT))):
        fin(u_loop(f'window_stops_{k}', a, b, STOOL, HEAD, STOP, PBin), 0.0)
        # 946 between sill and head; the meeting rails lap 30: each sash 488 high
        lo = frame_loop(f'window_sash_lower_{k}', a + 1.5, b - 1.5, SILL, SILL + 488.0, 45.0, 45.0, 70.0, 30.0, SASH, lambda x, z, v: V3(x, Y1 + 50.0 + v, z))
        up = frame_loop(f'window_sash_upper_{k}', a + 1.5, b - 1.5, HEAD - 488.0, HEAD, 45.0, 45.0, 30.0, 50.0, SASH, lambda x, z, v: V3(x, Y1 + 95.0 + v, z))
        fin(lo, 0.0)
        fin(up, 0.0)
        fin(hs.box(f'window_glass_lower_{k}', (a + 38.0, Y1 + 59.5, SILL + 62.0), (b - 38.0, Y1 + 62.5, SILL + 488.0 - 22.0)), 0.0, GLASS)
        fin(hs.box(f'window_glass_upper_{k}', (a + 38.0, Y1 + 104.5, HEAD - 488.0 + 22.0), (b - 38.0, Y1 + 107.5, HEAD - 42.0)), 0.0, GLASS)
        # the parting bead, seen on each jamb above the lower sash
        for s, xx in ((1.0, a), (-1.0, b)):
            hw_sk.append(bx((xx, Y1 + 85.6, SILL + 488.5), (xx + s * 10.0, Y1 + 94.4, HEAD - 0.5)))
        # the sash lock on the meeting rails: its base and cam on the lower sash, its keeper on the upper
        mx, mz = (a + b) / 2.0, SILL + 488.0
        hw_sk.append(bx((mx - 31.0, Y1 + 57.0, mz), (mx + 31.0, Y1 + 77.0, mz + 3.2)))
        hw_sk.append(rev([(0.0, 3.0), (7.0, 3.0), (7.0, 9.0), (5.5, 11.0), (0.0, 11.0)], V3(mx, Y1 + 67.0, mz)))
        cam = [(-6.0, -7.0), (6.0, -7.0), (8.0, 0.0), (7.0, 16.0), (10.0, 24.0), (9.0, 33.0), (3.0, 37.0), (-3.0, 33.0), (-5.0, 20.0), (-8.0, 4.0)]      # (the thumb lever, swung shut)
        ca_, sa_ = math.cos(math.radians(-68.0)), math.sin(math.radians(-68.0))
        hw_sk.append([[V3(mx + px * ca_ - py * sa_, Y1 + 67.0 + px * sa_ + py * ca_, mz + zz) for px, py in cam] for zz in (5.2, 9.4)])
        hw_sk.append(bx((mx - 21.0, Y1 + 95.6, mz + 0.2), (mx + 21.0, Y1 + 103.4, mz + 7.5)))      # (on the upper rail's ledge inside its glass)
        # two lifts on the lower sash's bottom rail: a screwed plate with a turned-out lip
        lift = [(50.0, 1136.0), (50.0, 1166.0), (47.6, 1166.5), (47.6, 1149.0), (42.0, 1147.5), (37.5, 1150.0), (36.0, 1155.0), (33.4, 1154.6), (34.6, 1148.0), (39.0, 1144.2), (45.0, 1143.6), (47.8, 1136.0)]
        for dx in (-190.0, 190.0):
            hw_sk.append([[V3(mx + dx + sx, Y1 + yy, zz) for yy, zz in lift] for sx in (-22.0, 22.0)])
        # a roller shade in each half, a hand's width drawn: its roll on two brackets, the cloth off the back of the roll,
        # a slat in its hem, a ring on a cord
        ry, rz, drop = Y1 + 30.0, 2030.0, 205.0                     # (the roll hangs clear under the head's stop)
        fin(hs.cyl(f'shade_roll_{k}', (a + 16.5, ry, rz), (b - 16.5, ry, rz), 31.0, seg=32), 0.6)
        fin(hs.box(f'shade_cloth_{k}', (a + 18.0, ry + 14.6, rz - drop), (b - 18.0, ry + 15.3, rz + 2.0)), 0.0)
        fin(hs.box(f'shade_hem_{k}', (a + 18.0, ry + 12.2, rz - drop - 26.0), (b - 18.0, ry + 17.6, rz - drop + 0.5)), 2.0)
        for s, xx in ((1.0, a + 11.2), (-1.0, b - 11.2)):
            hw_sk.append(bx((xx, Y1 + 13.0, rz - 17.0), (xx + s * 3.0, Y1 + 47.0, rz + 17.0)))
            hw_sk.append(rev([(0.0, 0.0), (4.0, 0.0), (4.0, 3.2), (0.0, 3.2)], V3(xx + s * 2.6, ry, rz), (s, 0.0, 0.0), 16))
        fin(hs.cyl(f'shade_cord_{k}', (mx, ry + 15.0, rz - drop - 25.0), (mx, ry + 15.0, rz - drop - 62.0), 1.8, seg=8), 0.0)
        fin(torus(f'shade_ring_{k}', V3(mx, ry + 15.0, rz - drop - 76.0), (0, 1, 0), 15.0, 2.6), 0.0)
    fin(hs.skins('window_hardware', hw_sk), 0.5)

    # ============================================================================================ THE DOOR
    # on the right wall, to the hall; it swings into the kitchen on three butts, so this side shows the leaf flush in its
    # frame, the hinge knuckles, the brass knob on its rose. A two-panel leaf: stiles and three rails round two flat
    # panels set back, a tall one over the lock rail and a short one under it: ONE mass with its two fields cut back by
    # one closed cutter
    jy0, jy1 = DY0 - 3.0, DY1 + 3.0                               # the jambs' faces: 3 clear of the leaf
    fin(hs.box('door_jamb_latch', (X1, jy0 - JT, 0.0), (X1 + TW, jy0, DZ1 + 22.0)), 0.8)
    fin(hs.box('door_jamb_hinge', (X1, jy1, 0.0), (X1 + TW, jy1 + JT, DZ1 + 22.0)), 0.8)
    fin(hs.box('door_jamb_head', (X1, jy0, DZ1 + 3.0), (X1 + TW, jy1, DZ1 + 22.0)), 0.8)
    fin(u_loop('door_stops', jy0, jy1, 0.0, DZ1 + 3.0, [(0.0, 35.5), (-8.5, 35.5), (-11.0, 38.0), (-11.0, 70.0), (0.0, 70.0)], PRin), 0.0)
    fin(u_loop('door_casing', jy0 - 5.0, jy1 + 5.0, 0.0, DZ1 + 8.0, CASING, PR), 0.0)
    leaf = hs.box('door_leaf', (X1, DY0, DZ0), (X1 + 35.0, DY1, DZ1))
    ROWS = ((DZ0 + 240.0, DZ0 + 800.0), (DZ0 + 1010.0, DZ0 + 1902.0))      # bottom rail 240, lock rail 210 (the knob at 914 is on it), top rail 120
    leaf = hs.boolean(leaf, hs.skins('door_fields', [bx((X1 - 6.0, DY0 + 120.0, r0), (X1 + 9.0, DY1 - 120.0, r1)) for r0, r1 in ROWS]), 'DIFFERENCE')
    fin(leaf, 2.0)                                                # (the one bevel is the arris of the leaf and the sticking round each panel)
    KNUCKLE = [(0.0, -46.5), (4.0, -46.5), (5.5, -45.0)]
    for zz in (-27.0, -8.8, 8.8, 27.0):
        KNUCKLE += [(5.5, zz - 0.4), (5.0, zz - 0.2), (5.0, zz + 0.2), (5.5, zz + 0.4)]
    KNUCKLE += [(5.5, 45.0), (4.0, 46.5), (0.0, 46.5)]
    fin(hs.skins('door_hinges', [rev(KNUCKLE, V3(X1 - 5.6, DY1 + 1.5, zc), (0, 0, 1), 16) for zc in (DZ0 + 178.0, (DZ0 + DZ1) / 2.0, DZ1 - 127.0)]), 0.0)
    KNOB = [(0.0, 0.0), (31.0, 0.0), (32.5, 1.5), (32.5, 4.5), (30.0, 7.0), (13.0, 8.0), (11.0, 11.0), (11.0, 26.0), (13.0, 30.0), (20.0, 34.0), (25.5, 40.0), (27.0, 47.0), (26.0, 54.0),
            (21.0, 59.5), (12.0, 62.5), (0.0, 63.5)]
    fin(hs.revolve('door_knob', KNOB, at=V3(X1, DY0 + 60.0, 914.0), axis=(-1, 0, 0), seg=48), 0.0)
    fin(hs.box('door_backing', (X1 + 80.0, DY0 - 30.0, 0.0), (X1 + TW + 5.0, DY1 + 30.0, DZ1 + 30.0)), 0.0, DARK)      # (the hall's side: nothing is seen past the leaf)

    # ============================================================================================ BASE BOARDS
    # a colonial base 83 high with its shoe at the floor, along the walls where no cupboard stands; it ends square against
    # the door's casing
    BASE = [(0.0, 0.0), (27.0, 0.0), (27.0, 4.0), (25.0, 10.0), (21.0, 15.0), (16.0, 18.0), (14.0, 19.0), (14.0, 56.0), (13.0, 66.0), (10.5, 73.0), (7.0, 77.0), (5.5, 80.5), (4.5, 83.0), (0.0, 83.0)]
    for nm, a, b in (('base_right_front', V3(X1, Y0, 0), V3(X1, jy0 - 5.0 - 70.0, 0)), ('base_right_back', V3(X1, jy1 + 5.0 + 70.0, 0), V3(X1, Y1, 0)),
                     ('base_left', V3(X0, Y1 - 610.0, 0), V3(X0, Y0, 0)), ('base_front', V3(X0, Y0, 0), V3(X1, Y0, 0))):
        fin(hs.sweep(nm, [a, b], BASE, up=(0, 0, 1)), 0.0)

    # ============================================================================================ THE LIGHTS, THE CLOCK, SWITCH AND SOCKETS
    # a ceiling fitting of the plainest kind, twice: a white steel pan on the ceiling, an opal glass bowl hung under it on a
    # centre stud, a turned finial nut holding it
    BOWL = [(168.0, 24.0), (171.0, 31.0), (172.0, 44.0), (168.0, 66.0), (154.0, 90.0), (128.0, 111.0), (92.0, 126.0), (52.0, 134.0), (22.0, 136.5), (9.0, 137.0)]
    for nm, cx_, cy_ in (('table', 900.0, -450.0), ('work', -800.0, 1500.0)):
        C = V3(cx_, cy_, HT)
        fin(hs.revolve(f'ceiling_light_{nm}_pan', [(0.0, 0.0), (150.0, 0.0), (153.0, 2.5), (153.0, 20.0), (150.0, 26.0), (140.0, 28.0), (0.0, 28.0)], at=C, axis=(0, 0, -1), seg=64), 0.0)
        inner = offset2(BOWL, 3.0)                                  # 3 mm of glass, inside
        fin(hs.revolve(f'ceiling_light_{nm}_bowl', BOWL + inner[::-1], at=C, axis=(0, 0, -1), seg=64, closed=True), 0.0)
        fin(hs.revolve(f'ceiling_light_{nm}_finial', [(0.0, 120.0), (4.0, 120.0), (4.0, 137.2), (12.0, 137.4), (14.0, 139.5), (14.0, 143.0), (11.0, 147.0), (7.0, 150.0), (6.0, 155.0),
                                                     (7.5, 159.0), (6.0, 163.0), (2.5, 166.0), (0.0, 166.5)], at=C, axis=(0, 0, -1), seg=24), 0.0)
    # the clock over the window, at a few minutes past noon: a moulded case with its rim, a domed glass, two hands
    CK = V3(WCX, Y1, 2288.0)
    fin(hs.revolve('clock_case', [(0.0, 0.0), (111.0, 0.0), (115.0, 4.0), (115.0, 29.0), (113.0, 34.0), (108.0, 37.0), (103.0, 35.0), (100.5, 30.0), (100.0, 21.0), (0.0, 21.0)],
                   at=CK, axis=(0, -1, 0), seg=64), 0.0)
    fin(hs.revolve('clock_glass', [(0.0, 31.5), (60.0, 30.6), (100.3, 28.0), (100.3, 30.0), (60.0, 32.8), (0.0, 33.8)], at=CK, axis=(0, -1, 0), seg=64), 0.0, GLASS)


    def hand(name, deg, length, w0, w1, tail, h0, h1):
        s, c = math.sin(math.radians(deg)), math.cos(math.radians(deg))
        pts = [(-w0, -tail), (w0, -tail), (w1, length - 3.0), (0.0, length), (-w1, length - 3.0)]
        return hs.prism_side(name, [(CK.x + px * c + pz * s, CK.z - px * s + pz * c) for px, pz in pts], CK.y - h1, CK.y - h0)


    fin(hand('clock_hand_hour', 2.0, 55.0, 4.2, 2.6, 14.0, 23.0, 24.0), 0.0)
    fin(hand('clock_hand_minute', 24.0, 84.0, 3.0, 1.6, 18.0, 25.0, 26.0), 0.0)
    fin(hs.revolve('clock_hub', [(0.0, 21.0), (6.5, 21.0), (6.5, 26.5), (5.0, 28.0), (0.0, 28.4)], at=CK, axis=(0, -1, 0), seg=24), 0.0)
    # the light switch by the door's latch side; three duplex sockets over the worktop's upstand
    swy, swz = jy0 - 5.0 - 70.0 - 75.0, 1220.0
    fin(hs.box('switch_plate', (X1 - 5.5, swy - 35.0, swz - 57.0), (X1, swy + 35.0, swz + 57.0)), 2.2)
    fin(hs.prism_side('switch_toggle', [(X1 - 5.0, swz - 4.6), (X1 - 5.0, swz + 4.6), (X1 - 16.0, swz + 12.4), (X1 - 17.6, swz + 10.2), (X1 - 17.6, swz + 6.4)], swy - 3.2, swy + 3.2), 0.8)
    sk = screw_skins(V3(X1 - 5.5, swy, swz + 30.0), (-1, 0, 0), 3.2, 1.6) + screw_skins(V3(X1 - 5.5, swy, swz - 30.0), (-1, 0, 0), 3.2, 1.6)
    SOCKETS = (-2560.0, -470.0, 1930.0)
    for i, sx in enumerate(SOCKETS):
        fin(hs.box(f'socket_plate_{i}', (sx - 35.0, Y1 - 5.5, 1118.0 - 57.0), (sx + 35.0, Y1, 1118.0 + 57.0)), 2.2)
        for dz in (-19.5, 19.5):                                    # each outlet's face: a round cut flat top and bottom, standing 1.6 out of the plate
            face = [(17.0 * math.cos(math.radians(a_)), max(-13.5, min(13.5, 17.0 * math.sin(math.radians(a_))))) for a_ in range(0, 360, 15)]
            sk.append([[V3(sx + fx, Y1 - yy, 1118.0 + dz + fz) for fx, fz in face] for yy in (5.0, 7.1)])
        sk += screw_skins(V3(sx, Y1 - 5.5, 1118.0), (0, -1, 0), 3.2, 1.6)
    fin(hs.skins('plate_screws_and_outlets', sk), 0.0)
    ns.update(WCX=WCX, STOOL=STOOL, frame_loop=frame_loop, torus=torus)
