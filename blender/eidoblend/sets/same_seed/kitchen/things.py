"""eidoblend.sets.same_seed.kitchen.things: what the family left (Blender). Millimetres.

  homework   on the table: a sewn composition book (two boards, the block, a cloth tape round its spine), the worksheet,
             coloured pencils (six-sided sticks sharpened to a cone: the scallops where the cone leaves the six flats
             are the cut itself)
  glass      a plain tumbler (wall, rolled lip, thick foot) with milk in it
  school bag a soft sack standing where it was dropped: body, front pocket, two zips over the top with their pulls,
             padded straps down its back, a carry loop, a piped seam round its base
  by the sink  a dish rack (coated wire on a moulded drain tray; plates, two tumblers upside down), the washing-up
             liquid; a kettle on the cooker; a roll of paper towels on its stand
  basil      a pot of basil on the window's stool (eidoblend.props.houseplants.basil), drawn from the same random stream
             as the things before it

    things.build(ns)         # after cabinets and table (it reads CT, YF, RIM, TP, BURN, PF, TTOP, STOOL)
"""

from ....props.houseplants import basil


def build(ns):
    (BURN, CT, GLASS, Matrix, PF, RIM, STOOL, TP, TTOP, V3, Vector, Y1, YF, bx, fin, hs, math, place) = (
        ns[k] for k in ('BURN', 'CT', 'GLASS', 'Matrix', 'PF', 'RIM', 'STOOL', 'TP', 'TTOP', 'V3', 'Vector', 'Y1', 'YF', 'bx', 'fin', 'hs', 'math',
                        'place'))
    import random

    RNG = random.Random(11)
    TZ = TTOP                                                     # the table's top


    def tube(path, r, seg=8):
        """a round rod along a path, as a skin (rotation-minimising frames, 04.6)"""
        return [[p + n * (r * math.cos(2 * math.pi * k / seg)) + b * (r * math.sin(2 * math.pi * k / seg)) for k in range(seg)] for p, t, n, b in hs.frames(path)]


    def flat(name, cx, cy, w, h, deg, z0, z1):
        c_, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        return hs.prism_plan(name, [(cx + px * c_ - py * s_, cy + px * s_ + py * c_) for px, py in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))], z0, z1)


    # ============================================================================================ THE HOMEWORK
    # two sheets (letter paper, 216 x 279): the one being read lies over (680, -200), its head away from the reader at
    # (900, 300); a finished one under it, askew
    fin(flat('homework_sheet_done', 640.0, -236.0, 216.0, 279.0, 171.0, TZ, TZ + 0.2), 0.0)
    fin(flat('homework_sheet', 680.0, -200.0, 216.0, 279.0, 184.0, TZ + 0.2, TZ + 0.45), 0.0)
    # the composition book, shut: 190 x 247, 9 thick
    NB = [bx((0.6, 1.0, 1.5), (189.0, 246.0, 8.1)), bx((0.0, 0.0, 0.3), (190.0, 247.0, 1.5)), bx((0.0, 0.0, 8.1), (190.0, 247.0, 9.3))]
    tape = [(25.0, 9.3), (25.0, 9.6), (-0.4, 9.6), (-0.4, 0.0), (25.0, 0.0), (25.0, 0.3), (-0.1, 0.3), (-0.1, 9.3)]
    NB.append([[V3(x, y, z) for x, z in tape] for y in (-0.2, 247.2)])
    place(fin(hs.skins('homework_composition_book', NB), 0.0), (1085.0, -590.0, TZ), math.radians(14.0))


    def pencil(name, length, eraser):
        """a six-sided pencil lying on one flat, its point at its own origin, along +x; 6.9 across the flats"""
        R = 6.9 / math.sqrt(3.0)
        body = hs.prism_section(name, [(R * math.cos(math.radians(60.0 * k)), R * math.sin(math.radians(60.0 * k))) for k in range(6)], 0.0, length)
        cone = hs.revolve(name + '_cut', [(0.0, -0.5), (0.35, 0.0), (1.05, 3.4), (1.1, 3.6), (4.6, 20.0), (4.6, length + 2.0), (0.0, length + 2.0)], at=V3(0, 0, 0), axis=(1, 0, 0), seg=36)
        body = hs.boolean(body, cone, 'INTERSECT')
        out = [fin(body, 0.0)]
        if eraser:                                                  # the ferrule's band with its two crimps, the rubber in it
            fer = [(0.0, 0.0), (3.75, 0.0), (3.75, 2.2), (3.5, 2.6), (3.5, 3.4), (3.75, 3.8), (3.75, 8.6), (3.5, 9.0), (3.5, 9.8), (3.75, 10.2), (3.75, 13.0), (3.35, 13.0), (3.35, 20.0), (2.9, 21.4),
                   (1.8, 22.0), (0.0, 22.0)]
            out.append(fin(hs.revolve(name + '_ferrule_and_rubber', fer, at=V3(length - 1.0, 0, 0), axis=(1, 0, 0), seg=24), 0.0))
        return out


    for nm, at, yaw, length, er in (('pencil_school', (870.0, -300.0), 31.0, 172.0, True), ('pencil_red', (1010.0, -112.0), -38.0, 158.0, False), ('pencil_blue', (960.0, -470.0), 80.0, 141.0, False)):
        for o in pencil(nm, length, er):
            place(o, (at[0], at[1], TZ + 6.9 / 2.0), math.radians(yaw))
    # a rubber: a block cut on the slant at both ends
    place(fin(hs.prism_side('homework_rubber', [(0.0, 0.0), (48.0, 0.0), (55.0, 11.0), (7.0, 11.0)], 0.0, 21.0), 1.6), (852.0, -128.0, TZ), math.radians(-20.0))

    # ============================================================================================ THE GLASS
    GC = V3(1450.0, -150.0, TZ)
    fin(hs.revolve('glass', [(0.0, 0.8), (24.0, 0.0), (29.5, 0.5), (31.0, 2.5), (31.2, 8.0), (37.6, 122.5), (38.0, 124.4), (37.2, 125.0), (36.2, 124.5), (35.6, 122.5), (29.0, 12.5), (27.0, 10.6), (0.0, 10.0)],
                   at=GC, seg=64), 0.0, GLASS)
    fin(hs.revolve('glass_milk', [(0.0, 10.3), (26.8, 10.9), (28.7, 12.8), (32.7, 78.0), (31.2, 77.2), (0.0, 77.0)], at=GC, seg=64), 0.0)

    # ============================================================================================ THE SCHOOL BAG
    # built standing on its own middle, its front to +y; then turned to face the room and stood by the child's chair.
    # ONE surface function is what the body is and what its seams, zip and piping lie on
    BH = 430.0
    BODY = ((0.0, 150.0, 95.0, 70.0, 5.0), (0.15, 152.0, 105.0, 72.0, 4.6), (0.5, 148.0, 101.0, 70.0, 4.0), (0.8, 132.0, 82.0, 66.0, 3.2), (0.93, 104.0, 56.0, 57.0, 2.7), (1.0, 62.0, 24.0, 40.0, 2.3))


    def body_at(t):
        """(half width, half depth in front, half depth behind, squareness) at the height t 0..1: between the table's rows"""
        for a, b in zip(BODY, BODY[1:]):
            if t <= b[0]:
                f = (t - a[0]) / (b[0] - a[0])
                f = f * f * (3.0 - 2.0 * f)
                return [a[i] + (b[i] - a[i]) * f for i in range(1, 5)]
        return list(BODY[-1][1:])


    def bag_pt(th, t, out=0.0):
        """a point of the body's surface: th round it (0 its right side, 90 degrees its front), t up it; `out` proud of it"""
        t = max(0.0, min(1.0, t))
        w, df, db, e = body_at(t)
        c_, s_ = math.cos(th), math.sin(th)
        # cloth half full hangs in broad dents between what fills it: two slow waves round it and up it, none at its
        # base or at its crown, where seams hold it
        soft = 1.0 + math.sin(math.pi * t) ** 1.5 * (0.045 * math.sin(2.0 * th + 4.4 * t + 0.7) + 0.03 * math.sin(3.0 * th - 6.0 * t))
        x = (w * soft + out) * math.copysign(abs(c_) ** (2.0 / e), c_)
        y = ((df if s_ > 0 else db) * soft + out) * math.copysign(abs(s_) ** (2.0 / e), s_)
        z = BH * t
        return V3(x, y - 0.105 * z - 34.0 * t * t, z)              # it leans back 6 degrees and its top sags back


    NTH = 56
    rl = [[bag_pt(2 * math.pi * k / NTH, 0.0) * 1.0 for k in range(NTH)]]
    rl[0] = [V3(p.x * 0.9, p.y * 0.9, 0.0) for p in rl[0]]
    rl.append([V3(p.x * 0.985, p.y * 0.985, 7.0) for p in [bag_pt(2 * math.pi * k / NTH, 0.0) for k in range(NTH)]])
    for i in range(1, 27):
        rl.append([bag_pt(2 * math.pi * k / NTH, 0.04 + 0.96 * i / 26.0) for k in range(NTH)])
    top_c = bag_pt(0.0, 1.0)
    rl.append([V3(p.x * 0.45, top_c.y + (p.y - top_c.y) * 0.45, BH + 7.0) for p in rl[-1]])
    bag = [hs.rings('school_bag_body', rl)]
    # the front pocket: a second sack sewn on the front, low
    PK = ((0.6, 40.0), (0.9, 52.0), (1.0, 78.0), (1.0, 150.0), (0.97, 225.0), (0.93, 262.0), (0.8, 283.0), (0.5, 293.0))


    def pocket_pt(th, i, out=0.0):
        s, z = PK[i]
        c_, s_ = math.cos(th), math.sin(th)
        front = bag_pt(math.pi / 2, z / BH)
        return V3(s * (112.0 + out) * math.copysign(abs(c_) ** (2.0 / 3.6), c_), front.y - 22.0 + s * (56.0 + out) * math.copysign(abs(s_) ** (2.0 / 3.0), s_), z)


    bag.append(hs.rings('school_bag_pocket', [[pocket_pt(2 * math.pi * k / 40, i) for k in range(40)] for i in range(len(PK))]))
    # the zips: a raised chain of teeth over the top of the body from side to side, and one over the pocket's top; a
    # slider and a cord pull on each
    ZSEC = hs.rrect(-1.3, -2.6, 1.3, 2.6, 1.0, n=2)
    zmain = [bag_pt(0.0, 0.42 + 0.58 * i / 16.0, 1.2) for i in range(17)]
    zmain += [V3(x, top_c.y, z) for x, z in ((46.0, BH + 4.6), (28.0, BH + 8.2), (0.0, BH + 8.2), (-28.0, BH + 8.2), (-46.0, BH + 4.6))]      # over the crown
    zmain += [bag_pt(math.pi, 1.0 - 0.58 * i / 16.0, 1.2) for i in range(17)]
    bag.append(hs.sweep('school_bag_zip', zmain, ZSEC, up=(0, 1, 0)))
    pyc = bag_pt(math.pi / 2, 293.0 / BH).y - 22.0                 # the pocket's own middle, at its top
    zpk = [pocket_pt(0.0, i, 1.2) for i in (3, 4, 5, 6)] + [V3(57.0, pyc, 294.6), V3(-57.0, pyc, 294.6)] + [pocket_pt(math.pi, i, 1.2) for i in (6, 5, 4, 3)]
    bag.append(hs.sweep('school_bag_pocket_zip', hs.fillet_path(zpk, 30.0, n=5), ZSEC, up=(0, 1, 0)))
    sk = []
    for p, d in ((zmain[11], Vector((0.55, 0.3, -0.78))), (zmain[19], Vector((-0.5, 0.35, -0.8))), (zpk[1] + Vector((3.0, 4.0, 0.0)), Vector((0.5, 0.45, -0.74)))):
        d = d.normalized()
        sk.append(bx((p.x - 5.0, p.y - 3.5, p.z - 3.5), (p.x + 5.0, p.y + 3.5, p.z + 4.5)))
        sk.append(tube([p + d * 4.0, p + d * 26.0], 1.3, 8))
        q = p + d * 34.0
        sk.append([hs.circle(q - d * 9.0, d, 2.0, 0.0, 10), hs.circle(q - d * 6.0, d, 4.2, 0.0, 10), hs.circle(q + d * 7.0, d, 4.6, 0.0, 10), hs.circle(q + d * 10.0, d, 2.4, 0.0, 10)])
    bag.append(hs.skins('school_bag_pulls', sk))
    # a piped seam round the base panel; the carry loop; two padded straps down the back, standing off it as they fell
    seam = [bag_pt(2 * math.pi * k / NTH, 62.0 / BH, 0.8) for k in range(NTH)]
    rlp = []
    for k, p in enumerate(seam):
        t = (seam[(k + 1) % NTH] - seam[k - 1]).normalized()
        rlp.append(hs.circle(p, t, 2.0, 0.0, 8, (0, 0, 1)))
    bag.append(hs.rings('school_bag_base_piping', rlp + [rlp[0]], caps=False))
    back_top = bag_pt(-math.pi / 2, 0.955)
    loop_p = [back_top + Vector((46.0 * math.cos(math.radians(a)), 0.0, -8.0 + 44.0 * math.sin(math.radians(a)))) for a in range(180, -1, -15)]
    bag.append(hs.sweep('school_bag_carry_loop', loop_p, hs.rrect(-1.6, -12.5, 1.6, 12.5, 1.2, n=2), up=(0, 1, 0)))
    for sx in (-1, 1):
        b1, b2, b3 = bag_pt(-math.pi / 2, 0.9), bag_pt(-math.pi / 2, 0.5), bag_pt(-math.pi / 2, 0.1)
        sp_ = [V3(sx * 52.0, b1.y - 6.0, b1.z), V3(sx * 84.0, b2.y - 52.0, b2.z + 30.0), V3(sx * 118.0, b2.y - 44.0, b2.z - 80.0), V3(sx * 139.0, b3.y - 10.0, b3.z)]
        bag.append(hs.sweep(f'school_bag_strap_{int(sx > 0)}', hs.fillet_path(sp_, 70.0, n=8), hs.rrect(-6.5, -31.0, 6.5, 31.0, 5.5, n=3), up=(1, 0, 0)))
    for o in bag:
        place(fin(o, 0.0), (2340.0, 60.0, 0.0), math.radians(152.0))

    # ============================================================================================ BY THE SINK
    # the drain tray and the wire rack on it, right of the sink; three plates in its slots, two tumblers upside down
    DX0, DX1, DY0_, DY1_ = 1395.0, 1815.0, YF + 96.0, YF + 436.0
    tray = hs.box('dish_tray', (DX0, DY0_, CT), (DX1, DY1_, CT + 22.0))
    tray = hs.boolean(tray, hs.box('dish_tray_well', (DX0 + 9.0, DY0_ + 9.0, CT + 5.0), (DX1 - 9.0, DY1_ - 9.0, CT + 40.0)), 'DIFFERENCE')
    fin(tray, 2.5)
    RZ0, RZ1 = CT + 8.0, CT + 118.0                                # the rack's runners and its rim
    for nm, z, ins in (('dish_rack_rim', RZ1, 16.0), ('dish_rack_runner', RZ0, 26.0)):
        pts = [V3(px, py, z) for px, py in hs.rrect(DX0 + ins, DY0_ + ins, DX1 - ins, DY1_ - ins, 34.0, n=6)]
        rlr = []
        for k, p in enumerate(pts):
            t = (pts[(k + 1) % len(pts)] - pts[k - 1]).normalized()
            rlr.append(hs.circle(p, t, 2.6, 0.0, 8, (0, 0, 1)))
        fin(hs.rings(nm, rlr + [rlr[0]], caps=False), 0.0)
    sk = []
    for i in range(12):                                             # the uprights round it, from the runner out to the rim
        x = DX0 + 52.0 + (DX1 - DX0 - 104.0) * i / 11.0
        for yr, yn in ((DY0_ + 26.0, DY0_ + 16.0), (DY1_ - 26.0, DY1_ - 16.0)):
            sk.append(tube([V3(x, yr, RZ0), V3(x, yn, RZ1)], 1.9, 6))
    for j in range(8):
        y = DY0_ + 52.0 + (DY1_ - DY0_ - 104.0) * j / 7.0
        for xr, xn in ((DX0 + 26.0, DX0 + 16.0), (DX1 - 26.0, DX1 - 16.0)):
            sk.append(tube([V3(xr, y, RZ0), V3(xn, y, RZ1)], 1.9, 6))
    for i in range(14):                                             # the cross wires of its floor
        x = DX0 + 40.0 + (DX1 - DX0 - 80.0) * i / 13.0
        sk.append(tube([V3(x, DY0_ + 27.0, RZ0 + 3.0), V3(x, DY1_ - 27.0, RZ0 + 3.0)], 1.9, 6))
    SLOTS = [DX0 + 70.0 + 27.0 * i for i in range(8)]
    for x in SLOTS:                                                 # the plate slots: a hairpin of wire standing in the floor for each
        sk.append(tube(hs.fillet_path([V3(x, DY0_ + 60.0, RZ0 + 3.0), V3(x, DY0_ + 60.0, RZ0 + 78.0), V3(x, DY0_ + 100.0, RZ0 + 78.0), V3(x, DY0_ + 100.0, RZ0 + 3.0)], 14.0, n=5), 1.9, 6))
    fin(hs.skins('dish_rack_wires', sk), 0.0)
    PLATE = [(0.0, 0.0), (44.0, 0.0), (48.0, 1.2), (50.0, 5.0), (82.0, 7.5), (124.0, 20.5), (130.0, 21.6), (131.5, 23.2), (130.0, 24.6), (122.0, 24.0), (82.0, 11.6), (48.0, 9.0), (0.0, 8.4)]
    for i, x in enumerate((SLOTS[1], SLOTS[2], SLOTS[5])):
        ax = Vector((1.0, 0.0, 0.16 if i < 2 else -0.14)).normalized()
        fin(hs.revolve(f'dish_plate_{i}', PLATE, at=V3(x + 2.2, DY0_ + 172.0, RZ0 + 133.0), axis=ax, seg=64), 0.0)
    TUMB = [(0.0, 0.8), (24.0, 0.0), (29.5, 0.5), (31.0, 2.5), (31.2, 8.0), (36.6, 108.5), (37.0, 110.4), (36.2, 111.0), (35.2, 110.5), (34.6, 108.5), (29.0, 12.5), (27.0, 10.6), (0.0, 10.0)]
    for i, (x, y) in enumerate(((DX1 - 80.0, DY0_ + 92.0), (DX1 - 84.0, DY1_ - 96.0))):
        fin(hs.revolve(f'dish_tumbler_{i}', TUMB, at=V3(x, y, RZ0 + 6.0 + 111.0), axis=(0, 0, -1), seg=48), 0.0, GLASS)
    # the washing-up liquid on the sink's deck: a waisted bottle, broader than it is deep, a push-pull cap; a sponge
    soap = hs.revolve('soap_bottle', [(0.0, 0.0), (36.0, 0.0), (40.0, 3.0), (41.0, 18.0), (40.0, 60.0), (34.0, 96.0), (33.0, 112.0), (36.5, 138.0), (37.0, 160.0), (33.0, 180.0), (21.0, 193.0),
                                      (15.0, 197.0), (15.0, 206.0), (17.0, 207.0), (17.0, 215.0), (14.0, 217.0), (14.0, 223.0), (10.0, 225.0), (7.0, 233.0), (6.0, 241.0), (0.0, 242.0)],
                      at=V3(0, 0, 0), seg=48)
    soap.data.transform(Matrix.Diagonal((1.0, 0.62, 1.0, 1.0)))
    place(fin(soap, 0.0), (TP.x + 118.0, TP.y + 4.0, RIM), math.radians(-12.0))
    fin(hs.skins('sponge', [bx((TP.x + 178.0, TP.y - 38.0, RIM), (TP.x + 288.0, TP.y + 30.0, RIM + 22.0)), bx((TP.x + 178.6, TP.y - 37.4, RIM + 22.0), (TP.x + 287.4, TP.y + 29.4, RIM + 29.0))]), 3.0)

    # ============================================================================================ THE KETTLE
    # on the cooker's small back coil: a spun body with its lid and knob, a spout drawn from its side, a bail over the top
    KX, KY = BURN[1][0], BURN[1][1]
    KC = V3(KX, KY, PF + 12.6)                                     # on the coil's top
    fin(hs.revolve('kettle_body', [(0.0, 0.0), (86.0, 0.0), (94.0, 3.0), (98.0, 12.0), (98.0, 38.0), (94.0, 60.0), (82.0, 82.0), (62.0, 98.0), (47.0, 105.0), (47.0, 107.5), (45.0, 108.0), (42.0, 114.0),
                                   (24.0, 121.0), (9.0, 123.0), (7.0, 130.0), (12.0, 135.0), (14.5, 142.0), (12.0, 149.0), (5.0, 152.5), (0.0, 153.0)], at=KC, seg=64), 0.0)
    kd = Vector((0.82, -0.57, 0.0))                                # the spout looks forward and to the right
    sp0, sp1, sp2 = KC + kd * 84.0 + Vector((0, 0, 36.0)), KC + kd * 136.0 + Vector((0, 0, 72.0)), KC + kd * 152.0 + Vector((0, 0, 122.0))
    rls = []
    for i in range(9):
        f = i / 8.0
        p = sp0 * (1 - f) ** 2 + sp1 * (2 * f * (1 - f)) + sp2 * f * f
        t = ((sp1 - sp0) * (1 - f) + (sp2 - sp1) * f).normalized()
        rls.append(hs.circle(p, t, 19.0 - 9.5 * f ** 0.8, 0.0, 20, (0, 0, 1)))
    fin(hs.rings('kettle_spout', rls), 0.0)
    bail = [KC + kd * (-70.0 * math.cos(math.radians(a))) + Vector((0, 0, 86.0 + 120.0 * math.sin(math.radians(a)))) for a in range(0, 181, 12)]      # its feet in the shoulder
    fin(hs.sweep('kettle_bail', bail, hs.rrect(-4.5, -8.0, 4.5, 8.0, 3.5, n=3), up=(kd.y, -kd.x, 0.0)), 0.0)

    # ============================================================================================ THE PAPER TOWELS
    PT = V3(-640.0, Y1 - 205.0, CT)
    fin(hs.revolve('towel_stand', [(0.0, 0.0), (76.0, 0.0), (78.0, 2.0), (78.0, 9.0), (74.0, 12.0), (9.0, 13.0), (7.5, 16.0), (7.5, 312.0), (10.0, 316.0), (12.0, 322.0), (10.0, 329.0), (4.0, 333.0),
                                   (0.0, 333.5)], at=PT, seg=48), 0.0)
    fin(hs.revolve('towel_roll', [(20.0, 13.0), (66.0, 13.0), (68.0, 15.0), (68.0, 291.0), (66.0, 293.0), (20.0, 293.0)], at=PT, seg=64, closed=True), 0.0)

    # ============================================================================================ THE BASIL
    # a 9 cm pot on its saucer on the window's stool, behind the sink's right bowl (the stool is 85 deep: the saucer
    # stands 8 over its nose and touches the sash); no blade reaches into the sash
    basil.build(V3(1470.0, Y1 + 3.0, STOOL), RNG, ns['CLAY'], y_max=Y1 + 40.0)
