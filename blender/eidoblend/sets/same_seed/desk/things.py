"""eidoblend.sets.same_seed.desk.things: what is the person's, on the desk and the floor (Blender). Millimetres.

  the HEADPHONES: closed-back studio headphones (round cups, velour pads, a forked yoke, a padded spring-steel band),
    laid down on their side on the desk as one does: the band flat, the cups on their rims; the lead from the left cup
    to the grommet
  the MUG: a stoneware mug (82 across, 96 high, 4 mm wall, an unglazed foot ring, a rolled lip), its handle fused on,
    cold coffee two thirds up (its own surface, clear of the wall)
  the PAGES: two A4 sheets, the lyrics on the top one (folded in half once and opened: it lies in a shallow valley, its
    far corner curling), 0.12 thick, UV 0..1 over the sheet for the handwriting (the look's)
  the RUG: 3.0 x 1.8 m, 9 thick, its edges eased, a knotted fringe at the two short ends, in front of the desk under the
    chair; the chair stands on it

    things.build(ns)         # after furniture and computer; adds PAGE_AT, PAGE_YAW (the lyrics' page), RUG_T (its pile)
"""


def build(ns):
    (CABLE, CHROME, DTOP, GX, GY, M, Matrix, V3, Vector, bmesh, fin, hs, math, settle) = (
        ns[k] for k in ('CABLE', 'CHROME', 'DTOP', 'GX', 'GY', 'M', 'Matrix', 'V3', 'Vector', 'bmesh', 'fin', 'hs', 'math', 'settle'))
    STEELHP = M('headphone_spring_steel', (0.55, 0.55, 0.56), 0.3, 1.0)
    HPPLAST = M('headphone_plastic_black', (0.03, 0.03, 0.03), 0.35)
    VELOUR = M('headphone_velour_grey', (0.08, 0.08, 0.085), 0.95)
    PADLEATH = M('headphone_band_leatherette', (0.02, 0.02, 0.02), 0.45)
    CERAMIC = M('mug_stoneware_glaze', (0.55, 0.32, 0.22), 0.15)
    COFFEE = M('coffee', (0.03, 0.015, 0.008), 0.05)
    PAPER = M('paper_lyrics', (0.85, 0.84, 0.8), 0.85)
    RUGM = M('rug_wool', (0.4, 0.18, 0.14), 0.95)
    FRINGE = M('rug_fringe_cotton', (0.75, 0.72, 0.64), 0.9)

    # ============================================================================================ THE HEADPHONES
    # their own space as worn: the cups' axes along x (centres at x +-90), the band over the top in the x-z plane
    CUPX = 90.0
    hp = []
    for s_ in (-1.0, 1.0):
        ax_ = V3(s_, 0.0, 0.0)
        c_ = V3(s_ * CUPX, 0.0, 0.0)
        # the cup: a turned shell, its baffle toward the head; its outer face a slightly dished cap with a raised rim
        hp.append(fin(hs.revolve(f'headphone_cup_{"lr"[s_ > 0]}', [(0.0, 31.0), (28.0, 31.5), (33.0, 33.0), (38.0, 31.5), (42.5, 27.0), (45.0, 19.0), (45.0, 6.0), (44.0, 2.0), (41.0, 0.0), (0.0, 0.0)],
                                 at=c_, axis=ax_, seg=72), 0.0, HPPLAST))
        # the pad: velour round a foam ring, 24 proud of the baffle toward the head, its opening 52 across
        pad = [(27.0, 1.0), (27.5, -10.0), (29.0, -19.0), (32.0, -23.0), (38.5, -24.5), (45.0, -23.0), (48.5, -19.0), (50.0, -10.0), (49.0, -1.0), (45.0, 1.5), (31.0, 1.5)]
        hp.append(fin(hs.revolve(f'headphone_pad_{"lr"[s_ > 0]}', pad, at=c_, axis=ax_, seg=72, closed=True), 0.0, VELOUR))      # (negative h: toward the head)
        # the yoke: a fork of flat bar round the cup from its two pivots (front and back at its equator) up to the slider
        yk = [V3(s_ * (CUPX + 12.0), -52.0, -4.0), V3(s_ * (CUPX + 12.0), -52.0, 28.0)] + \
             [V3(s_ * (CUPX + 12.0), -52.0 * math.cos(math.pi * k_ / 10), 28.0 + 30.0 * math.sin(math.pi * k_ / 10)) for k_ in range(1, 10)] + \
             [V3(s_ * (CUPX + 12.0), 52.0, 28.0), V3(s_ * (CUPX + 12.0), 52.0, -4.0)]
        hp.append(fin(hs.sweep(f'headphone_yoke_{"lr"[s_ > 0]}', hs.fillet_path(yk, 6.0, 4), [(-2.2, -5.0), (2.2, -5.0), (2.2, 5.0), (-2.2, 5.0)], up=(1, 0, 0)), 0.6, HPPLAST))
        for yy in (-52.0, 52.0):                              # the pivots: a screw boss through the yoke into the cup's rim
            hp.append(fin(hs.revolve(f'headphone_pivot_{"lr"[s_ > 0]}_{int(yy)}', [(0.0, 0.0), (5.0, 0.0), (5.0, 5.5), (3.5, 7.0), (0.0, 7.0)],
                                     at=V3(s_ * (CUPX + 10.0), yy * 0.86, 0.0), axis=(0, 1 if yy > 0 else -1, 0), seg=24), 0.0, CHROME))
        # the slider: a flat steel strip from the yoke's crown up into the band's end
        hp.append(fin(hs.box(f'headphone_slider_{"lr"[s_ > 0]}', (s_ * (CUPX + 12.0) - 1.0, -6.0, 56.0), (s_ * (CUPX + 12.0) + 1.0, 6.0, 92.0)), 0.0, STEELHP))
    # the band: spring steel 28 wide, 2.5 thick, a half ellipse from the sliders' tops over the head; under its crown the
    # cushion (a padded tube of leatherette, 34 wide, 12 thick)
    arc =[V3((CUPX + 12.0) * math.cos(math.pi * k_ / 32), 0.0, 86.0 + 150.0 * math.sin(math.pi * k_ / 32)) for k_ in range(33)]
    hp.append(fin(hs.sweep('headphone_band', arc, [(-1.25, -14.0), (1.25, -14.0), (1.25, 14.0), (-1.25, 14.0)], up=(0, 1, 0)), 0.8, STEELHP))
    cush = [V3((CUPX + 12.0 - 7.2) * math.cos(math.pi * (0.22 + 0.56 * k_ / 20)), 0.0, 86.0 + (150.0 - 7.2) * math.sin(math.pi * (0.22 + 0.56 * k_ / 20))) for k_ in range(21)]
    cush_sec = [(6.0 * math.cos(2 * math.pi * q / 20), 17.0 * math.sin(2 * math.pi * q / 20)) for q in range(20)]        # (its back against the band's inner face)
    hp.append(fin(hs.sweep('headphone_cushion', cush, cush_sec, up=(0, 1, 0)), 0.0, PADLEATH))
    # laid down: turned onto its side (the band to the back), tipped until the band's crown rests on the desk as well as
    # the two cups' rims; then turned to lie between the lamp's clamp and the screen's base
    HP_R = Matrix.Rotation(math.radians(160.0), 4, 'Z') @ Matrix.Rotation(math.radians(-(90.0 + 6.5)), 4, 'X')
    for o_ in hp:
        settle(o_)
        o_.data.transform(HP_R)
    zmin = min((v.co.z for o_ in hp for v in o_.data.vertices))
    for o_ in hp:
        o_.data.transform(Matrix.Translation(Vector((0.47, 0.47, DTOP * hs.MM - zmin))))
    # the lead: out of the left cup's foot, a loose loop on the oak, back to the grommet
    lc = Vector((0.47, 0.47, 0.0)) * 1000.0 + (HP_R @ V3(-CUPX - 10.0, 0.0, -44.0) * hs.MM) * 1000.0
    lp_ = [V3(lc.x, lc.y, DTOP + 2.0), V3(lc.x - 40.0, lc.y - 90.0, DTOP + 2.0), V3(lc.x + 60.0, lc.y - 150.0, DTOP + 2.0), V3(lc.x + 170.0, lc.y - 60.0, DTOP + 2.0),
           V3(GX - 120.0, GY - 60.0, DTOP + 2.0), V3(GX - 30.0, GY + 15.0, DTOP + 2.5), V3(GX - 26.0, GY + 20.0, DTOP - 60.0)]
    fin(hs.sweep('headphone_lead', hs.fillet_path(lp_, 35.0, 8), [(2.0 * math.cos(2 * math.pi * q / 10), 2.0 * math.sin(2 * math.pi * q / 10)) for q in range(10)]), 0.0, CABLE)

    # ============================================================================================ THE MUG
    MUG_AT = V3(1455.0, 395.0, DTOP)
    MUG = [(0.0, 2.5), (33.5, 2.5), (35.0, 0.6), (36.5, 0.0), (38.5, 0.0), (39.8, 1.2), (40.6, 5.0), (41.0, 14.0), (41.0, 90.0), (40.8, 93.5), (40.0, 95.5), (38.8, 96.0),
           (37.6, 95.4), (37.0, 93.0), (37.0, 14.0), (36.0, 9.5), (33.0, 7.6), (0.0, 7.0)]
    fin(hs.revolve('mug', MUG, at=MUG_AT, axis=(0, 0, 1), seg=64), 0.0, CERAMIC)
    hpath = [MUG_AT + V3(38.0, 0.0, 80.0), MUG_AT + V3(56.0, 0.0, 80.0), MUG_AT + V3(66.0, 0.0, 66.0), MUG_AT + V3(66.0, 0.0, 40.0), MUG_AT + V3(56.0, 0.0, 26.0), MUG_AT + V3(38.0, 0.0, 26.0)]
    fin(hs.sweep('mug_handle', hs.fillet_path(hpath, 12.0, 8), [(4.6 * math.cos(2 * math.pi * q / 20), 7.0 * math.sin(2 * math.pi * q / 20)) for q in range(20)], up=(0, 1, 0)), 0.0, CERAMIC)
    fin(hs.revolve('mug_coffee', [(0.0, 7.6), (32.5, 7.9), (36.0, 12.0), (36.6, 16.0), (36.6, 62.0), (0.0, 62.0)], at=MUG_AT, axis=(0, 0, 1), seg=64), 0.0, COFFEE)

    # ============================================================================================ THE PAGES
    PAGE_AT, PAGE_YAW = V3(330.0, 235.0, DTOP), math.radians(-11.0)


    def sheet(name, w, h, nx, ny, lift, thick=0.12):
        """a sheet of paper w x h (mm) about its own middle, its top face lifted by lift(u, v) (u, v in 0..1), closed by its
        underside 'thick' below and its four edges; UV 0..1 over its top face (u along w, v along h)"""
        bm = bmesh.new()
        uvl_ = bm.loops.layers.uv.verify()
        top_ = [[bm.verts.new((((i / nx) - 0.5) * w * hs.MM, ((j / ny) - 0.5) * h * hs.MM, lift(i / nx, j / ny) * hs.MM)) for i in range(nx + 1)] for j in range(ny + 1)]
        bot_ = [[bm.verts.new((v_.co.x, v_.co.y, v_.co.z - thick * hs.MM)) for v_ in row] for row in top_]
        for j in range(ny):
            for i in range(nx):
                f_ = bm.faces.new((top_[j][i], top_[j][i + 1], top_[j + 1][i + 1], top_[j + 1][i]))
                for lp, (a_, b_) in zip(f_.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    lp[uvl_].uv = (a_ / nx, b_ / ny)
                bm.faces.new((bot_[j][i], bot_[j + 1][i], bot_[j + 1][i + 1], bot_[j][i + 1]))
        rt = [top_[0][i] for i in range(nx + 1)] + [top_[j][nx] for j in range(1, ny + 1)] + [top_[ny][i] for i in range(nx - 1, -1, -1)] + [top_[j][0] for j in range(ny - 1, 0, -1)]
        rb = [bot_[0][i] for i in range(nx + 1)] + [bot_[j][nx] for j in range(1, ny + 1)] + [bot_[ny][i] for i in range(nx - 1, -1, -1)] + [bot_[j][0] for j in range(ny - 1, 0, -1)]
        for k_ in range(len(rt)):
            bm.faces.new((rt[k_], rb[k_], rb[(k_ + 1) % len(rb)], rt[(k_ + 1) % len(rt)]))
        return hs.obj(name, bm)


    def folded_once(u, v):
        """folded in half across its middle and opened: a valley along v = 0.5, its ends lifting 3.5 mm; the far right
        corner curling up a further 4 mm over its last 50 mm"""
        z = 0.12 + 3.5 * (2.0 * abs(v - 0.5)) ** 1.6
        cu = max(0.0, (u - 0.72) / 0.28) * max(0.0, (v - 0.8) / 0.2)
        return z + 4.0 * cu ** 2


    def flat_page(u, v):
        """the sheet underneath: flat on the oak (its underside 0.01 over it), its near edge lifting where it was handled"""
        return 0.13 + 0.8 * max(0.0, (0.15 - v) / 0.15) ** 2


    under = sheet('page_under', 210.0, 297.0, 12, 16, flat_page)
    settle(under)
    under.data.transform(Matrix.Translation(Vector((PAGE_AT.x + 38.0, PAGE_AT.y + 44.0, DTOP)) * hs.MM) @ Matrix.Rotation(math.radians(9.0), 4, 'Z'))
    fin(under, 0.0, M('paper_plain', (0.85, 0.85, 0.82), 0.85))
    lyr = sheet('page_lyrics', 210.0, 297.0, 21, 30, folded_once)
    settle(lyr)
    lyr.data.transform(Matrix.Translation(Vector((PAGE_AT.x, PAGE_AT.y, DTOP + 0.15)) * hs.MM) @ Matrix.Rotation(PAGE_YAW, 4, 'Z'))
    fin(lyr, 0.0, PAPER)                                      # (its sheet UV stays first; fin adds 'box_1m')

    # ============================================================================================ THE RUG
    RUG_X0, RUG_X1, RUG_Y0, RUG_Y1, RUG_T = -1300.0, 1700.0, -1880.0, -80.0, 9.0
    fin(hs.prism_plan('rug', hs.rrect(RUG_X0, RUG_Y0, RUG_X1, RUG_Y1, 18.0, 4), 0.0, RUG_T), 3.0, RUGM)
    import random as _r
    rr = _r.Random(11)
    fr = []
    for xe, s_ in ((RUG_X0, -1.0), (RUG_X1, 1.0)):
        n_t = int((RUG_Y1 - RUG_Y0 - 60.0) / 24.0)
        for k_ in range(n_t):
            y0_ = RUG_Y0 + 30.0 + 24.0 * k_ + rr.uniform(-3.0, 3.0)
            L_ = 62.0 + rr.uniform(-8.0, 8.0)
            bend = rr.uniform(-14.0, 14.0)
            pts = []
            for q in range(7):
                t_ = q / 6.0
                pts.append(V3(xe + s_ * (-6.0 + L_ * t_), y0_ + bend * t_ * t_, 1.6 + 2.2 * (1.0 - t_) * (1.0 - t_)))
            r0 = 1.9
            fr.append([hs.circle(p_, ((pts[min(q + 1, 6)] - pts[max(q - 1, 0)]).normalized()), r0 * (1.0 - 0.25 * q / 6.0) if q < 6 else 1.0, 0.0, 6, (0, 0, 1)) for q, p_ in enumerate(pts)])
            knot = pts[1]
            fr.append([hs.circle(knot + V3(s_ * h_, 0.0, 0.0), (s_, 0.0, 0.0), r_, 0.0, 8, (0, 0, 1)) for h_, r_ in ((-3.5, 1.9), (-2.0, 3.2), (2.0, 3.2), (3.5, 1.9))])
    fin(hs.skins('rug_fringe', fr), 0.0, FRINGE)
    ns.update(PAGE_AT=PAGE_AT, PAGE_YAW=PAGE_YAW, RUG_T=RUG_T)
