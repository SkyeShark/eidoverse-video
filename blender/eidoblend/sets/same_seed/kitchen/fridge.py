"""eidoblend.sets.same_seed.kitchen.fridge: the refrigerator and what is stuck on it (Blender). Millimetres.

A top-freezer refrigerator, 750 wide, 1690 high: a sheet-steel case; two pressed doors, the freezer's about three
eighths of the height, each a little proud of the case on its gasket, their edges rolled; on each a long moulded handle
that lies on the door and cranks out into a grip beside the gap between the doors (the freezer's grip low, the other's
high: both at the hand); a hinge cap on the case's top corner, a hinge bracket between the doors and one under them; a
louvred kick grille under the lower door; papers and a child's drawing held by magnets. It stands in the corner by the
right wall, its hinges on the wall's side. No maker's badge.

    fridge.build(ns)
"""


def build(ns):
    (DARK, V3, Y1, bx, fin, hs, math, rev) = (ns[k] for k in ('DARK', 'V3', 'Y1', 'bx', 'fin', 'hs', 'math', 'rev'))
    FX0_, FX1_ = 2184.0, 2934.0
    FCB, FCF = Y1 - 40.0, Y1 - 710.0                              # the case's back and front
    FDB, FDF = FCF - 12.0, FCF - 74.0                             # the doors' backs (on the gasket) and faces
    FTOP = 1690.0
    fin(hs.box('fridge_case', (FX0_, FCF, 22.0), (FX1_, FCB, FTOP)), 3.0)
    DOORS = (('lower', 104.0, 1086.0), ('upper', 1098.0, 1686.0))
    for nm, z0, z1 in DOORS:
        fin(hs.box(f'fridge_door_{nm}', (FX0_ + 2.0, FDF, z0), (FX1_ - 2.0, FDB, z1)), 9.0, None, 4)
        fin(hs.box(f'fridge_gasket_{nm}', (FX0_ + 16.0, FDB - 2.0, z0 + 14.0), (FX1_ - 16.0, FCF + 1.0, z1 - 14.0)), 0.0, DARK)
    # the handles: one section, 30 x 11, carried down each door's face on the left
    HSEC = hs.rrect(-5.5, -15.0, 5.5, 15.0, 4.0, n=4)
    hx, yl, yg = FX0_ + 40.0, FDF - 5.2, FDF - 35.0                 # the handle's line; lying on the door; out at the grip
    fin(hs.sweep('fridge_handle_upper', hs.fillet_path([V3(hx, yl, 1672.0), V3(hx, yl, 1452.0), V3(hx, yg, 1410.0), V3(hx, yg, 1138.0), V3(hx, yl + 1.0, 1108.0)], 16.0, n=6), HSEC, up=(1, 0, 0)), 0.0)
    fin(hs.sweep('fridge_handle_lower', hs.fillet_path([V3(hx, yl + 1.0, 1078.0), V3(hx, yg, 1048.0), V3(hx, yg, 800.0), V3(hx, yl, 758.0), V3(hx, yl, 432.0)], 16.0, n=6), HSEC, up=(1, 0, 0)), 0.0)
    fin(hs.box('fridge_hinge_cap', (FX1_ - 78.0, FDF + 8.0, FTOP - 2.0), (FX1_ - 5.0, FCF + 16.0, FTOP + 19.0)), 5.0)
    fin(hs.box('fridge_hinge_middle', (FX1_ - 52.0, FDF + 6.0, 1087.5), (FX1_ - 9.0, FCF + 2.0, 1096.5)), 1.0)
    fin(hs.box('fridge_hinge_bottom', (FX1_ - 52.0, FDF + 6.0, 92.0), (FX1_ - 9.0, FCF + 2.0, 102.5)), 1.0)
    # the kick grille: a dark frame, five louvres leaning down and out
    fin(hs.box('fridge_grille_back', (FX0_ + 10.0, FCF - 3.0, 26.0), (FX1_ - 10.0, FCF + 2.0, 98.0)), 0.0, DARK)
    sk = []
    for k in range(5):
        zc = 36.0 + 13.0 * k
        sk.append([[V3(x, FCF - 3.0 + dy, zc + dz) for dy, dz in ((-9.0, -5.0), (-7.6, -6.2), (1.0, 3.4), (-0.4, 4.6))] for x in (FX0_ + 14.0, FX1_ - 14.0)])
    fin(hs.skins('fridge_grille_louvres', sk), 0.0)
    fin(hs.skins('fridge_feet', [rev([(0.0, 0.0), (17.0, 0.0), (18.0, 1.5), (18.0, 7.0), (9.0, 9.0), (9.0, 24.0), (0.0, 24.0)], V3(x, FCF + 40.0, 0.0), (0, 0, 1), 20) for x in (FX0_ + 48.0, FX1_ - 48.0)]), 0.0)


    # ------------------------------------------------------------------ what is on it
    def sheet(name, cx, cz, w, h, deg, curl=6.0, y=FDF):
        """a sheet of paper held flat to the door by its top, its lower edge standing a little off it (16.79: it bends one
        way only, along its height)"""
        c_, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        rl = []
        for i in range(9):
            v = i / 8.0                                            # 0 at the bottom edge
            off = 0.35 + curl * (1.0 - v) ** 3
            row = []
            for u, d in ((-0.5, off), (0.5, off), (0.5, off - 0.3), (-0.5, off - 0.3)):
                px, pz = u * w, (v - 0.5) * h
                row.append(V3(cx + px * c_ - pz * s_, y - d, cz + px * s_ + pz * c_))
            rl.append(row)
        return fin(hs.rings(name, rl), 0.0)


    sheet('fridge_drawing', 2575.0, 1410.0, 279.0, 216.0, 2.5, curl=7.0)
    sheet('fridge_school_letter', 2620.0, 815.0, 216.0, 279.0, -1.8, curl=4.0)
    sheet('fridge_shopping_list', 2372.0, 905.0, 105.0, 190.0, 3.0, curl=9.0)
    MAG = [(0.0, 0.0), (15.0, 0.0), (15.0, 4.0), (13.5, 6.4), (12.6, 6.8), (12.6, 9.6), (11.0, 11.2), (0.0, 11.6)]
    sk = [rev(MAG, V3(x, FDF - 0.3, z), (0, -1, 0), 20) for x, z in ((2452.0, 1497.0), (2698.0, 1507.0), (2620.0, 940.0), (2372.0, 988.0), (2470.0, 640.0), (2800.0, 1265.0))]
    fin(hs.skins('fridge_magnets', sk), 0.0)
    fin(hs.skins('fridge_photo_magnets', [bx((2306.0, FDF - 4.0, 1250.0), (2392.0, FDF + 0.2, 1312.0)), bx((2318.0, FDF - 4.0, 1168.0), (2382.0, FDF + 0.2, 1238.0))]), 1.2)
