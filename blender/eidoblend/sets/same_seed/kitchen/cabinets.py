"""eidoblend.sets.same_seed.kitchen.cabinets: the cupboards, the worktop, the sink and its tap, the dishwasher, the
cooker and its hood (Blender). Millimetres; the room's own space.

  cupboards   American face-frame cupboards, painted: a box 610 deep with a FRAME of 38 mm stiles and rails on its
              front; doors and drawer fronts 19 thick LAPPING the frame's openings by 12.7 all round, frame-and-panel
              doors with a knob at the corner by the meeting edge, the knuckle of a hinge beside each door; a toe space
              114 high, 76 back. The worktop's top at 914. Wall cupboards 305 deep, 457 above the worktop, to 2438.
  worktop     post-formed laminate (the rolled nose, the coved upstand at the wall): ONE section run along the wall,
              cut for the sink
  sink, tap   a two-bowl stainless sink let into the worktop on its rim; a single-lever tap with a pull-out spout
  dishwasher, cooker, hood   the cooker's one-piece top with its raised rim and four coils in their drip bowls, the back
              guard with its black control panel, six knobs and a clock, the door with its window (smoked glass with a
              clear coat) and its flat chrome handle, the drawer under it; the hood's slanted face and its visor; the
              dishwasher beside it: console, door, kick
Every front has its thickness and stands off what it covers; doors lap, drawers lap, the worktop lies on the boxes and
runs past the doors; knobs, hinges and handles are seated on what carries them.

    cabinets.build(ns)       # after shell; adds CT, YF, RIM, TP, BURN, PF for the things on the worktop and the cooker
"""


def build(ns):
    (DARK, GLASS, V3, Vector, WCX, X0, X1, Y1, bx, fin, frame_loop, hs, math, rev) = (
        ns[k] for k in ('DARK', 'GLASS', 'V3', 'Vector', 'WCX', 'X0', 'X1', 'Y1', 'bx', 'fin', 'frame_loop', 'hs', 'math', 'rev'))
    CT, BOX_TOP, KICK = 914.0, 876.0, 114.0
    FY, FT = Y1 - 610.0, 19.0                                     # the base frames' front; frames, doors and drawer fronts are 19 thick
    DYF = FY - FT                                                 # the base doors' faces
    UFY = Y1 - 305.0                                              # the wall cupboards' frames
    UZ0, UZ1 = 1372.0, 2438.0
    LAP, STILE, RAIL = 12.7, 38.0, 57.0
    RX0, RX1 = -1539.0, -777.0                                    # the cooker's bay (30 in)
    DWX0, DWX1 = -167.0, 443.0                                    # the dishwasher's (24 in)
    KNOB_C = [(0.0, 0.0), (8.5, 0.0), (8.5, 1.5), (6.0, 3.5), (5.5, 9.0), (7.0, 13.0), (11.5, 16.0), (15.5, 19.5), (16.0, 22.5), (15.0, 25.5), (11.0, 28.0), (5.0, 29.3), (0.0, 29.5)]
    BARREL = [(0.0, -30.0), (2.5, -29.5), (3.4, -27.5), (2.6, -26.2), (4.5, -26.0), (4.5, 26.0), (2.6, 26.2), (3.4, 27.5), (2.5, 29.5), (0.0, 30.0)]
    knobs, hinges = [], []


    def fronts(name, slabs, doors, y0):
        """the fronts of one cupboard, one object: plain slabs (drawer fronts) and five-piece doors [(x0, x1, z0, z1)],
        each door ONE mass cut back to its panel (04.20: all the fields one closed cutter)"""
        mass = hs.skins(name, [bx((a, y0, c), (b, y0 + FT, d)) for a, b, c, d in slabs + doors])
        if doors:
            mass = hs.boolean(mass, hs.skins(name + '_fields', [bx((a + RAIL, y0 - 6.0, c + RAIL), (b - RAIL, y0 + 9.5, d - RAIL)) for a, b, c, d in doors]), 'DIFFERENCE')
        return fin(mass, 0.7)


    def hinge_pair(xe, side, z0, z1, yface):
        """two knuckles beside a door's hinge edge at xe (side -1: the frame is to its left), each on its leaf on the frame"""
        for zc in (z0 + 62.0, z1 - 62.0):
            hinges.append(rev(BARREL, V3(xe + side * 5.2, yface - 6.0, zc), (0, 0, 1), 16))
            hinges.append(bx((xe + side * 19.5, yface - 1.6, zc - 25.0), (xe + side * 1.2, yface + 0.3, zc + 25.0)))


    def doors_in(a, b, z0, z1):
        """the door or pair of doors lapping the opening a..b: [(x0, x1, z0, z1, hinge side)]"""
        if b - a > 430.0:
            m = (a + b) / 2.0
            return [(a - LAP, m - 1.5, z0 - LAP, z1 + LAP, -1), (m + 1.5, b + LAP, z0 - LAP, z1 + LAP, 1)]
        return [(a - LAP, b + LAP, z0 - LAP, z1 + LAP, -1)]


    def cupboard(name, x0, x1, z0, z1, rows, yf, base, box_top=None):
        """one face-frame cupboard. rows [(z0, z1, kind)] the frame's openings, bottom up: 'door', 'drawer', 'false' (a
        fixed front: the sink's). yf: its frame's front. base: knobs high on the doors (a base cupboard) or low (a wall one).
        box_top: where its box ends, if lower than its frame (the sink's: the bowls hang in it)"""
        g, yd = 0.3, yf - FT
        a, b = x0 + STILE, x1 - STILE
        fr = hs.box(name + '_frame', (x0 + g, yf, z0), (x1 - g, yf + FT, z1))
        fr = hs.boolean(fr, hs.skins(name + '_openings', [bx((a, yf - 6.0, r0), (b, yf + FT + 6.0, r1)) for r0, r1, _ in rows]), 'DIFFERENCE')
        fin(fr, 0.5)
        fin(hs.box(name + '_box', (x0 + g, yf + FT, z0 + (0.0 if base else 12.0)), (x1 - g, Y1, box_top or z1)), 0.0)
        slabs, drs = [], []
        for r0, r1, kind in rows:
            if kind == 'door':
                for dx0, dx1, dz0, dz1, hs_ in doors_in(a, b, r0, r1):
                    drs.append((dx0, dx1, dz0, dz1))
                    kx = (dx1 - RAIL / 2.0) if hs_ < 0 else (dx0 + RAIL / 2.0)          # on the stile by the meeting (or latch) edge
                    knobs.append(rev(KNOB_C, V3(kx, yd, dz1 - 64.0 if base else dz0 + 64.0), (0, -1, 0), 20))
                    hinge_pair(dx0 if hs_ < 0 else dx1, hs_, dz0, dz1, yf)
            else:
                slabs.append((a - LAP, b + LAP, r0 - LAP, r1 + LAP))
                if kind == 'drawer':
                    knobs.append(rev(KNOB_C, V3((a + b) / 2.0, yd, (r0 + r1) / 2.0), (0, -1, 0), 20))
        fronts(name + '_fronts', slabs, drs, yd)


    # ------------------------------------------------------------------ the base run
    D1 = [(153.0, 686.0, 'door'), (724.0, 838.0, 'drawer')]       # a drawer over doors
    D4 = [(153.0, 305.3, 'drawer'), (343.3, 495.7, 'drawer'), (533.7, 686.0, 'drawer'), (724.0, 838.0, 'drawer')]
    SINK_ROWS = [(153.0, 686.0, 'door'), (724.0, 838.0, 'false')]
    BASES = (('base_a', -2987.0, -2301.0, D1), ('base_b', -2301.0, RX0, D1), ('base_drawers', RX1, DWX0, D4), ('base_sink', DWX1, 1357.0, SINK_ROWS), ('base_c', 1357.0, 2119.0, D1))
    for nm, x0, x1, rows in BASES:
        # (the sink's cupboard box stops at 690, below the bowls)
        cupboard(nm, x0, x1, KICK, BOX_TOP, rows, FY, True, box_top=690.0 if nm == 'base_sink' else None)
    fin(hs.box('base_filler_left', (X0, FY, KICK), (-2987.3, FY + FT, BOX_TOP)), 0.5)
    for nm, x0, x1 in (('toe_kick_left', X0, RX0), ('toe_kick_drawers', RX1, DWX0), ('toe_kick_right', DWX1, 2119.0)):
        fin(hs.box(nm, (x0, FY + 76.0, 0.0), (x1 - 0.3, FY + 92.0, KICK + 3.0)), 0.5)
    fin(hs.box('base_end_foot', (2119.0 - 19.0, FY + 76.0, 0.0), (2119.0 - 0.3, Y1, KICK + 3.0)), 0.5)

    # ------------------------------------------------------------------ the wall run
    WALLS = (('wall_a', -2987.0, -2301.0, UZ0), ('wall_b', -2301.0, RX0, UZ0), ('wall_over_hood', RX0, RX1, 1828.0), ('wall_c', RX1, 14.0, UZ0), ('wall_d', 1786.0, 2119.0, UZ0),
             ('wall_over_fridge', 2119.0, 2987.0, 1828.0))
    for nm, x0, x1, z0 in WALLS:
        cupboard(nm, x0, x1, z0, UZ1, [(z0 + STILE, UZ1 - STILE, 'door')], UFY, False)
    fin(hs.box('wall_filler_left', (X0, UFY, UZ0), (-2987.3, UFY + FT, UZ1)), 0.5)
    fin(hs.box('wall_filler_right', (2987.3, UFY, 1828.0), (X1, UFY + FT, UZ1)), 0.5)
    fin(hs.skins('cupboard_knobs', knobs), 0.0)
    fin(hs.skins('cupboard_hinges', hinges), 0.0)

    # ------------------------------------------------------------------ the worktop
    # one section: a rolled nose with the least of a raised lip, the deck, a cove up into the upstand, the upstand's rounded
    # top against the wall; 648 from wall to nose, 40 at the nose; the cooker stands between its two lengths
    YF = Y1 - 648.0
    CTR = ([(Y1, BOX_TOP)] + hs.arc(YF + 6.0, BOX_TOP + 6.0, 6.0, 270.0, 180.0, 4) + hs.arc(YF + 11.0, CT - 8.5, 11.0, 180.0, 90.0, 6) +
           [(YF + 24.0, CT + 2.0), (YF + 36.0, CT + 0.9), (YF + 48.0, CT + 0.2), (YF + 62.0, CT)] + hs.arc(Y1 - 31.0, CT + 12.0, 12.0, 270.0, 360.0, 6) +
           hs.arc(Y1 - 16.0, 1013.0, 3.0, 180.0, 90.0, 3) + [(Y1, 1016.0)])
    fin(hs.prism_section('worktop_left', CTR, X0, RX0 - 1.5), 0.0)
    SX0, SX1, SY0, SY1 = WCX - 419.0, WCX + 419.0, YF + 57.0, YF + 590.0           # the sink: 838 x 533 (33 x 21 in)
    top = hs.prism_section('worktop_right', CTR, RX1 + 1.5, 2131.0)
    top = hs.boolean(top, hs.prism_plan('sink_cutout', hs.rrect(SX0 + 10.0, SY0 + 10.0, SX1 - 10.0, SY1 - 10.0, 28.0), 850.0, 940.0), 'DIFFERENCE')
    fin(top, 0.0)

    # ------------------------------------------------------------------ the sink
    # pressed stainless: a rim lying on the worktop, two bowls with round corners and a drawn floor falling to its waste, a
    # deck behind them for the tap. (Under the worktop it is a solid: no lens goes there, 00.29.)
    RIM = CT + 5.2


    def bowl(name, x0, y0, x1, y1):
        rl = []
        for z, i, r in ((RIM + 8.0, -1.0, 56.0), (RIM - 6.0, 0.0, 55.0), (760.0, 9.0, 50.0), (749.0, 12.0, 48.0), (741.0, 14.5, 46.0), (734.5, 19.0, 42.0), (730.8, 26.0, 38.0), (729.4, 34.0, 34.0),
                        (728.6, 62.0, 60.0), (726.6, 120.0, 50.0)):
            rr = min(r, (x1 - x0) / 2.0 - i - 1.0, (y1 - y0) / 2.0 - i - 1.0)
            rl.append([V3(px, py, z) for px, py in hs.rrect(x0 + i, y0 + i, x1 - i, y1 - i, rr, n=8)])
        return hs.rings(name, rl)


    sink = hs.prism_plan('sink', hs.rrect(SX0, SY0, SX1, SY1, 38.0, n=8), 705.0, RIM)
    BOWLS = ((SX0 + 38.0, SY0 + 32.0, WCX - 19.0, SY1 - 95.0), (WCX + 19.0, SY0 + 32.0, SX1 - 38.0, SY1 - 95.0))
    for k, (x0, y0, x1, y1) in enumerate(BOWLS):
        sink = hs.boolean(sink, bowl(f'sink_bowl_{k}', x0, y0, x1, y1), 'DIFFERENCE')
        sink = hs.boolean(sink, hs.cyl(f'sink_waste_{k}', ((x0 + x1) / 2.0, (y0 + y1) / 2.0, 690.0), ((x0 + x1) / 2.0, (y0 + y1) / 2.0, 735.0), 89.0, seg=48), 'DIFFERENCE')
    fin(sink, 2.2)
    STRAINER = [(0.0, -19.0), (43.5, -19.0), (44.5, 0.0), (57.0, 0.0), (57.0, 1.6), (48.0, 2.4), (45.0, 1.4), (42.5, -13.5), (12.0, -15.5), (7.0, -15.5), (5.5, -2.0), (10.5, -1.0),
                (11.5, 2.0), (8.0, 4.5), (0.0, 5.0)]
    for k, (x0, y0, x1, y1) in enumerate(BOWLS):
        fin(hs.revolve(f'sink_strainer_{k}', STRAINER, at=V3((x0 + x1) / 2.0, (y0 + y1) / 2.0, 726.4), seg=48), 0.0)

    # ------------------------------------------------------------------ the tap
    # on the deck behind the bowls' divide: a round body with a banded cap, a looped lever leaning back from it, the spout
    # rising forward from its side: a tube that is the pull-out hose's handle, swelling to a spray head whose nozzle looks
    # down into the bowl; a soap pump's cap beside it
    TP = V3(WCX, SY1 - 49.0, RIM)
    fin(hs.revolve('tap_body', [(0.0, 0.0), (30.0, 0.0), (30.5, 2.5), (27.5, 6.0), (25.0, 8.0), (25.0, 98.0), (26.0, 100.0), (26.0, 104.0), (25.0, 106.0), (25.0, 130.0), (23.0, 139.0),
                                (17.0, 146.0), (8.0, 150.5), (0.0, 151.5)], at=TP, seg=48), 0.0)
    sd, wd = Vector((0.0, 0.574, 0.819)), Vector((1.0, 0.0, 0.0))  # the lever's plane: up and back; across
    nd = sd.cross(wd).normalized()
    # the lever: a cast loop, as thick as a finger, 86 long: two straight sides and two round ends, so its section never
    # folds on itself
    LL, LB = 86.0, 12.5
    stad = [(LB + (LL - 2 * LB) * i / 6, LB) for i in range(6)] + [(LL - LB + LB * math.cos(math.pi / 2 - math.pi * i / 10), LB * math.sin(math.pi / 2 - math.pi * i / 10)) for i in range(10)]
    stad += [(LL - LB - (LL - 2 * LB) * i / 6, -LB) for i in range(6)] + [(LB + LB * math.cos(-math.pi / 2 - math.pi * i / 10), LB * math.sin(-math.pi / 2 - math.pi * i / 10)) for i in range(10)]
    loop = [TP + Vector((0.0, 0.0, 139.0)) + sd * s_ + wd * w_ for s_, w_ in stad]
    SEC = hs.rrect(-4.4, -6.5, 4.4, 6.5, 3.4, n=3)
    rl = []
    for k, p in enumerate(loop):
        t = (loop[(k + 1) % len(loop)] - loop[k - 1]).normalized()
        b_ = t.cross(nd).normalized()
        rl.append([p + b_ * u + nd * v for u, v in SEC])
    fin(hs.rings('tap_lever', rl + [rl[0]], caps=False), 0.0)
    dsp = Vector((0.0, -0.883, 0.469))                             # the spout's line: forward and up, 28 degrees
    S0 = TP + Vector((0.0, -12.0, 50.0))
    fin(hs.revolve('tap_spout', [(0.0, 0.0), (17.5, 0.0), (17.5, 26.0), (15.0, 30.0), (15.0, 106.0), (16.4, 107.0), (16.4, 110.0), (15.0, 111.0), (15.0, 160.0), (16.5, 168.0), (21.0, 186.0),
                                 (22.5, 204.0), (22.5, 232.0), (20.0, 242.0), (12.0, 248.0), (0.0, 249.0)], at=S0, axis=dsp, seg=40), 0.0)
    ndn = Vector((0.0, -0.34, -0.94)).normalized()
    fin(hs.revolve('tap_nozzle', [(0.0, 0.0), (13.0, 0.0), (13.0, 26.0), (11.5, 29.0), (0.0, 29.0)], at=S0 + dsp * 218.0, axis=ndn, seg=32), 0.0)
    fin(hs.revolve('soap_pump_cap', [(0.0, 0.0), (27.0, 0.0), (28.0, 3.0), (24.0, 10.0), (12.0, 14.0), (11.0, 24.0), (9.0, 26.0), (0.0, 26.5)], at=TP + Vector((-92.0, 0.0, 0.0)), seg=40), 0.0)

    # ------------------------------------------------------------------ the dishwasher
    # built in under the worktop: a control console across its top (a latch in a pocket, push buttons, a dial), the door's
    # panel held in its trim, a kick panel set back under it
    dx0, dx1 = DWX0 + 3.0, DWX1 - 3.0
    fin(hs.box('dishwasher_body', (dx0 + 2.0, DYF + 24.0, 22.0), (dx1 - 2.0, Y1, BOX_TOP - 6.0)), 0.0)
    con = hs.box('dishwasher_console', (dx0, DYF - 9.0, 742.0), (dx1, DYF + 26.0, BOX_TOP - 8.0))
    lx = (dx0 + dx1) / 2.0 - 60.0
    con = hs.boolean(con, hs.box('dishwasher_latch_pocket', (lx - 96.0, DYF - 20.0, 778.0), (lx + 96.0, DYF + 7.0, 824.0)), 'DIFFERENCE')
    fin(con, 2.5)
    fin(hs.box('dishwasher_latch', (lx - 80.0, DYF - 6.0, 792.0), (lx + 80.0, DYF + 9.0, 808.0)), 2.5)
    sk = [bx((lx + 122.0 + 27.0 * i, DYF - 11.5, 791.0), (lx + 142.0 + 27.0 * i, DYF - 6.0, 803.0)) for i in range(5)]
    fin(hs.skins('dishwasher_buttons', sk), 1.2)
    fin(hs.revolve('dishwasher_dial', [(0.0, 0.0), (23.0, 0.0), (23.0, 3.0), (21.0, 5.0), (17.0, 5.5), (16.0, 15.0), (14.0, 18.0), (0.0, 18.5)], at=V3(dx1 - 62.0, DYF - 9.0, 800.0),
                   axis=(0, -1, 0), seg=40), 0.0)
    door = hs.box('dishwasher_door', (dx0, DYF - 6.0, 158.0), (dx1, DYF + 24.0, 738.0))
    door = hs.boolean(door, hs.box('dishwasher_door_field', (dx0 + 13.0, DYF - 12.0, 171.0), (dx1 - 13.0, DYF - 3.4, 725.0)), 'DIFFERENCE')
    fin(door, 2.0)
    fin(hs.box('dishwasher_kick', (dx0, DYF + 12.0, 24.0), (dx1, DYF + 30.0, 152.0)), 2.5)
    fin(hs.box('dishwasher_foot', (dx0 + 12.0, DYF + 60.0, 0.0), (dx1 - 12.0, DYF + 90.0, 26.0)), 0.0, DARK)

    # ------------------------------------------------------------------ the cooker
    rx0, rx1, rcx = RX0 + 1.0, RX1 - 1.0, (RX0 + RX1) / 2.0
    fin(hs.box('cooker_body', (rx0 + 4.0, DYF + 29.0, 30.0), (rx1 - 4.0, Y1 - 6.0, 890.0)), 2.0)
    fin(hs.box('cooker_foot', (rx0 + 14.0, DYF + 48.0, 0.0), (rx1 - 14.0, Y1 - 10.0, 34.0)), 0.0, DARK)
    # its top: one pressing, a rolled front apron, a rim all round a shallow pan, four openings for the drip bowls
    CY0 = DYF - 25.0                                              # the apron's face stands over the door's
    TOPSEC = [(Y1 - 8.0, 868.0), (CY0 + 4.0, 868.0), (CY0, 872.0)] + hs.arc(CY0 + 14.0, CT - 14.0, 14.0, 180.0, 90.0, 6) + [(Y1 - 8.0, CT)]
    ctop = hs.prism_section('cooker_top', TOPSEC, rx0, rx1)
    PY0, PY1 = CY0 + 30.0, Y1 - 72.0                               # the pan
    ctop = hs.boolean(ctop, hs.prism_plan('cooker_pan', hs.rrect(rx0 + 22.0, PY0, rx1 - 22.0, PY1, 26.0, n=6), CT - 8.0, CT + 20.0), 'DIFFERENCE')
    BURN = ((rx0 + 196.0, PY0 + 148.0, 100.0), (rx0 + 196.0, PY1 - 124.0, 76.0), (rx1 - 196.0, PY1 - 124.0, 76.0), (rx1 - 196.0, PY0 + 148.0, 100.0))      # (x, y, the coil's radius)
    ctop = hs.boolean(ctop, hs.skins('cooker_bowl_holes', [[hs.circle(V3(bx_, by_, z), (0, 0, 1), R + 12.0, 0.0, 48) for z in (840.0, CT + 5.0)] for bx_, by_, R in BURN]), 'DIFFERENCE')
    fin(ctop, 2.2)
    PF = CT - 8.0                                                 # the pan's floor
    for k, (bx_, by_, R) in enumerate(BURN):
        fin(hs.revolve(f'cooker_drip_bowl_{k}', [(0.0, -34.0), (26.0, -34.0), (R - 16.0, -28.0), (R + 9.0, -3.0), (R + 16.0, -0.3), (R + 16.0, 2.2), (R + 10.5, 3.4), (R + 7.0, 1.5),
                                                 (R - 18.0, -24.0), (26.0, -30.0), (0.0, -30.0)], at=V3(bx_, by_, PF), seg=64), 0.0)
        # the coil: a tube wound flat from the middle out, 12.5 a turn, its outer end at the back, where the terminal is;
        # each end turns down into the bowl
        turns = (R - 18.0) / 12.5
        n = int(turns * 36)
        pts = []
        for i in range(n + 1):
            th = math.radians(10.0 * (i - n)) + math.pi / 2.0
            r_ = 18.0 + 12.5 * (10.0 * i / 360.0)
            pts.append(V3(bx_ + r_ * math.cos(th), by_ + r_ * math.sin(th), PF + 9.0))

        def dive(p, t):
            """a quarter turn down from a level run p along t"""
            t = Vector((t.x, t.y, 0.0)).normalized()
            return [p + t * (9.0 * math.sin(math.radians(a))) - Vector((0.0, 0.0, 9.0 * (1.0 - math.cos(math.radians(a))))) for a in (18.0, 36.0, 54.0, 72.0, 90.0)] + \
                   [p + t * 9.0 - Vector((0.0, 0.0, 22.0))]
        head = dive(pts[0], pts[0] - pts[1])[::-1]
        tail = dive(pts[-1], pts[-1] - pts[-2])
        coil = hs.sweep(f'cooker_coil_{k}', head + pts + tail, [(3.7 * math.cos(2 * math.pi * j / 10), 3.7 * math.sin(2 * math.pi * j / 10)) for j in range(10)], up=None)
        fin(coil, 0.0)
    # the back guard: a sheet-steel upstand leaning a little back, its black panel in a bright frame, six knobs, a clock
    SL = 14.0 / 130.0                                             # the face's lean


    def yface(z):
        return Y1 - 60.0 + SL * (z - 964.0)


    fin(hs.prism_section('cooker_back_guard', [(Y1 - 60.0, CT - 2.0), (Y1 - 60.0, 964.0), (yface(1094.0), 1094.0), (yface(1094.0) + 4.0, 1098.0), (Y1 - 8.0, 1098.0), (Y1 - 8.0, CT - 2.0)], rx0, rx1), 1.5)
    fin(hs.prism_section('cooker_control_panel', [(yface(972.0) - 7.0, 972.0), (yface(1086.0) - 7.0, 1086.0), (yface(1086.0) + 1.0, 1086.0), (yface(972.0) + 1.0, 972.0)], rx0 + 6.0, rx1 - 6.0), 1.2)
    nrm = Vector((0.0, -1.0, SL)).normalized()
    sk = [rev([(0.0, 0.0), (20.0, 0.0), (20.0, 2.0), (18.5, 4.0), (15.5, 4.5), (15.0, 13.0), (13.5, 16.0), (0.0, 16.5)], V3(rcx + ox, yface(1036.0) - 7.0, 1036.0), nrm, 24)
          for ox in (-296.0, -238.0, -146.0, 146.0, 238.0, 296.0)]
    sk.append(rev([(0.0, 0.0), (24.0, 0.0), (24.0, 2.5), (21.0, 3.6), (0.0, 3.6)], V3(rcx, yface(1034.0) - 7.0, 1034.0), nrm, 32))
    fin(hs.skins('cooker_knobs_and_clock', sk), 0.0)
    fin(frame_loop('cooker_clock_frame', rcx - 88.0, rcx + 88.0, 1000.0, 1068.0, 5.0, 5.0, 5.0, 5.0, [(0.0, -0.5), (0.0, 2.0), (0.25, 2.6), (0.75, 2.6), (1.0, 2.0), (1.0, -0.5)],
                   lambda x, z, v: V3(x, yface(z) - 7.0 - v, z)), 0.0)


    def handle(name, cx_, hw, z, yd):
        """a flat bright bar across a door on two stand-offs: one piece"""
        h_ = hs.box(name, (cx_ - hw, yd - 38.0, z - 11.0), (cx_ + hw, yd - 29.0, z + 11.0))
        for s in (-1.0, 1.0):
            h_ = hs.boolean(h_, hs.box(name + '_post', (cx_ + s * hw - s * 30.0, yd - 33.0, z - 8.0), (cx_ + s * hw - s * 4.0, yd + 3.0, z + 8.0)), 'UNION')
        return fin(h_, 2.2)


    OD = DYF - 15.0                                               # the oven door's face
    od = hs.box('cooker_door', (rx0 + 5.0, OD, 300.0), (rx1 - 5.0, DYF + 29.0, 862.0))
    WIN = [(rcx + px, pz) for px, pz in hs.rrect(-252.0, 560.0, 252.0, 750.0, 16.0, n=6)]
    od = hs.boolean(od, hs.prism_side('cooker_window_field', WIN, OD - 6.0, OD + 4.0), 'DIFFERENCE')
    fin(od, 4.0)
    fin(hs.prism_side('cooker_window_glass', [(rcx + (px - rcx) * 0.994, 655.0 + (pz - 655.0) * 0.985) for px, pz in WIN], OD + 1.6, OD + 6.0), 0.0, GLASS)
    handle('cooker_door_handle', rcx, 338.0, 832.0, OD)
    fin(hs.box('cooker_door_latch', (rx0 + 52.0, OD - 7.0, 788.0), (rx0 + 64.0, OD + 2.0, 812.0)), 1.5)
    fin(hs.box('cooker_drawer', (rx0 + 5.0, OD, 42.0), (rx1 - 5.0, DYF + 29.0, 290.0)), 4.0)
    handle('cooker_drawer_handle', rcx, 318.0, 262.0, OD)

    # ------------------------------------------------------------------ the hood
    # under the short cupboard over the cooker: a box against the cupboard with a slanted face (its louvres and two
    # switches are drawn by the look: 3 mm slots at 7 m), a visor under it; hollow below, a filter in it and a lamp's lens
    HZ = 1828.0
    HSEC = [(Y1, HZ), (Y1 - 300.0, HZ), (Y1 - 410.0, HZ - 98.0), (Y1 - 410.0, HZ - 102.0), (Y1 - 448.0, HZ - 106.0), (Y1 - 452.0, HZ - 112.0), (Y1 - 452.0, HZ - 160.0), (Y1 - 448.0, HZ - 166.0), (Y1, HZ - 166.0)]
    hood = hs.prism_section('hood', HSEC, rx0, rx1)
    hood = hs.boolean(hood, hs.box('hood_hollow', (rx0 + 24.0, Y1 - 424.0, HZ - 190.0), (rx1 - 24.0, Y1 - 24.0, HZ - 131.0)), 'DIFFERENCE')
    fin(hood, 2.0)
    fin(hs.box('hood_filter', (rx0 + 60.0, Y1 - 300.0, HZ - 138.0), (rx1 - 60.0, Y1 - 40.0, HZ - 130.0)), 1.0)
    fin(hs.box('hood_lamp_lens', (rcx - 100.0, Y1 - 408.0, HZ - 137.0), (rcx + 100.0, Y1 - 322.0, HZ - 130.0)), 2.0)
    fin(hs.box('hood_nameplate', (rcx - 140.0, Y1 - 453.6, HZ - 147.0), (rcx + 140.0, Y1 - 451.0, HZ - 125.0)), 0.5)
    ns.update(CT=CT, YF=YF, RIM=RIM, TP=TP, BURN=BURN, PF=PF)
