"""eidoblend.sets.same_seed.desk.computer: the computer on and under the desk (Blender). Millimetres; the room's space.

Each built from what the product is (a screen as a designed product: a bezel lip round a recessed panel, its aperture a
UV island of its own, 0..1 over the lit area, unmirrored, for the look's screen picture):
  the MONITOR: a 27-inch 16:9 panel (597 x 336 active, 614 x 364 overall: 7.5 mm bezels, a 20 mm chin), its back a
    shallow shell with the electronics' housing on it, tilted back 3 degrees on its hinge; the stand: a neck of rounded
    section with its cable hole, a flat base; the power and display leads from its ports down through the neck's hole
    and across to the grommet. The screen's face near y 500, its lit area z 912..1248
  the KEYBOARD: full size (ANSI, 104 keys at 19.05 mm pitch), cylindrical-dished caps sculpted by row, floating over a
    sloped deck on their switches; on a felt desk mat with the MOUSE (ambidextrous, wireless: split buttons, wheel,
    thumb buttons); the COMPUTER: a mid tower on the floor under the desk's right end, its lead to the wall.

    computer.build(ns)       # after furniture (DCX, DTOP, GX, GY); adds CABLE (the leads' clay)
"""


def build(ns):
    (DCX, DTOP, GX, GY, M, Matrix, V3, Y1, bmesh, bx, fin, hs, math, place, rev, settle, trim) = (
        ns[k] for k in ('DCX', 'DTOP', 'GX', 'GY', 'M', 'Matrix', 'V3', 'Y1', 'bmesh', 'bx', 'fin', 'hs', 'math', 'place', 'rev', 'settle', 'trim'))
    PLASTIC = M('monitor_plastic_black', (0.03, 0.03, 0.032), 0.45)
    SCREEN = M('screen_panel', (0.02, 0.022, 0.025), 0.15)
    ALU = M('monitor_base_alu_dark', (0.12, 0.12, 0.125), 0.35, 1.0)
    CABLE = M('cable_black', (0.02, 0.02, 0.02), 0.5)
    KEYCAP = M('keycap_pbt_black', (0.035, 0.035, 0.037), 0.55)
    KDECK = M('keyboard_case_alu_grey', (0.18, 0.18, 0.19), 0.4, 1.0)
    SWITCH = M('key_switch_housing', (0.02, 0.02, 0.02), 0.4)
    FELT = M('desk_mat_felt_grey', (0.12, 0.12, 0.13), 0.95)
    TOWER = M('pc_case_steel_black', (0.03, 0.03, 0.033), 0.4)

    # ============================================================================================ THE MONITOR
    # its own space: x across (+ to the right as one faces it), y back from its face (the bezel's front at y 0), z up from
    # the lit area's middle; placed at (900, 497, 1080) facing -y
    MON_AT = V3(DCX, 497.0, 1080.0)
    AW, AH = 597.0, 336.0
    BX0, BX1, BZ0, BZ1 = -307.0, 307.0, -AH / 2 - 20.0, AH / 2 + 7.5
    body = hs.skins('monitor_body', [[[V3(px, y_, pz) for px, pz in hs.rrect(BX0, BZ0, BX1, BZ1, 4.0, 4)] for y_ in (0.0, 10.0)]])
    body = hs.boolean(body, hs.skins('monitor_back_housing', [[[V3(px, y_, pz) for px, pz in hs.rrect(-215.0, -AH / 2 - 15.0, 215.0, 70.0, 24.0, 6)] for y_ in (8.0, 26.0)]]), 'UNION')
    body = hs.boolean(body, hs.skins('monitor_back_housing_b', [[[V3(px, y_, pz) for px, pz in hs.rrect(-195.0, -AH / 2 - 5.0, 195.0, 50.0, 18.0, 6)] for y_ in (25.0, 40.0)]]), 'UNION')
    body = hs.boolean(body, hs.box('monitor_aperture', (-AW / 2 - 0.3, -2.0, -AH / 2 - 0.3), (AW / 2 + 0.3, 1.4, AH / 2 + 0.3)), 'DIFFERENCE')
    # the ports, cut up into the housing's underside (HDMI, HDMI, DisplayPort; the mains inlet)
    ports = [bx((x0_, 12.0, -AH / 2 - 22.0), (x0_ + w_, 22.0 if w_ < 25 else 24.0, -AH / 2 - 8.0)) for x0_, w_ in ((-120.0, 16.0), (-96.0, 16.0), (-70.0, 19.0), (90.0, 28.0))]
    body = hs.boolean(body, hs.skins('monitor_ports', ports), 'DIFFERENCE')
    mon_parts = [fin(body, 1.0, PLASTIC)]
    scr = fin(hs.box('monitor_screen', (-AW / 2, 0.8, -AH / 2), (AW / 2, 1.38, AH / 2)), 0.0, SCREEN)        # (in its pocket, 0.8 behind the bezel's face)
    bm_ = bmesh.new()                                         # the screen's own UV: 0..1 over the lit area, as seen from the front
    bm_.from_mesh(scr.data)
    uv_ = bm_.loops.layers.uv.verify()
    for f_ in bm_.faces:
        for lp in f_.loops:
            lp[uv_].uv = ((lp.vert.co.x / hs.MM + AW / 2) / AW, (lp.vert.co.z / hs.MM + AH / 2) / AH)
    bm_.to_mesh(scr.data)
    bm_.free()
    mon_parts.append(scr)
    # the power LED and the button under the chin's right end
    mon_parts.append(fin(hs.revolve('monitor_power_button', [(0.0, 0.0), (4.0, 0.0), (4.0, 1.2), (3.2, 1.8), (0.0, 1.9)], at=V3(255.0, 6.0, BZ0), axis=(0, 0, -1), seg=24), 0.0, PLASTIC))
    mon_parts.append(fin(hs.box('monitor_power_led', (262.0, -0.2, BZ0 + 8.0), (264.0, 0.5, BZ0 + 9.2)), 0.0, M('led_white')))
    # the hinge block on the housing's back, its tilt pivot
    HINGE = V3(0.0, 52.0, -40.0)
    mon_parts.append(fin(hs.box('monitor_hinge', (-40.0, 39.0, -75.0), (40.0, 62.0, -15.0)), 2.0, PLASTIC))
    for o_ in mon_parts:                                      # tilted back 3 degrees about the hinge (its top away from the viewer)
        settle(o_)
        o_.data.transform(Matrix.Translation(HINGE * hs.MM) @ Matrix.Rotation(math.radians(-3.0), 4, 'X') @ Matrix.Translation(-HINGE * hs.MM))
    # the stand: the neck (a rounded section 70 x 28, a 40 x 24 cable hole through it) from the base to the hinge
    NZ0 = DTOP - MON_AT.z + 14.0                              # the base's top (local)
    neck = hs.prism_plan('monitor_neck', [(x_, 64.0 + y_) for x_, y_ in hs.rrect(-35.0, -14.0, 35.0, 14.0, 9.0, 5)], NZ0 - 1.0, -10.0)
    neck = hs.boolean(neck, hs.skins('neck_hole', [[[V3(px, y_, pz) for px, pz in hs.rrect(-20.0, NZ0 + 40.0, 20.0, NZ0 + 64.0, 10.0, 6)] for y_ in (40.0, 90.0)]]), 'DIFFERENCE')
    neck = hs.boolean(neck, hs.box('neck_head', (-38.0, 50.0, -60.0), (38.0, 66.0, -20.0)), 'UNION')
    mon_parts.append(fin(neck, 1.5, ALU))
    mon_parts.append(fin(hs.prism_plan('monitor_base', [(x_, 58.0 + y_) for x_, y_ in hs.rrect(-130.0, -98.0, 130.0, 98.0, 40.0, 8)], NZ0 - 14.0, NZ0), 3.0, ALU))
    for o_ in mon_parts:
        place(o_, MON_AT)
    # the leads: from the ports under the housing, down behind the neck, through its hole, onto the desk and to the grommet
    for k_, (px, r_) in enumerate(((-61.0, 3.0), (104.0, 3.6))):
        p0 = MON_AT + V3(px, 17.0, -AH / 2 - 12.0)                      # (in its port)
        pts = [p0, p0 + V3(0.0, 2.0, -30.0), V3(MON_AT.x + px * 0.15, MON_AT.y + 64.0, MON_AT.z + NZ0 + 52.0), V3(MON_AT.x + px * 0.1, MON_AT.y + 105.0, DTOP + r_ + 1.0),
               V3(MON_AT.x + 200.0 + 40.0 * k_, MON_AT.y + 140.0, DTOP + r_), V3(GX - 15.0 + 10.0 * k_, GY + 2.0, DTOP + r_ + 2.0),
               V3(GX - 6.0 + 9.0 * k_, GY + 19.0, DTOP + r_ + 2.5), V3(GX - 6.0 + 9.0 * k_, GY + 19.0, DTOP - 60.0)]      # (down through the cap's slot)
        fin(hs.sweep(f'monitor_lead_{k_}', hs.fillet_path(pts, 30.0, 8), [(r_ * math.cos(2 * math.pi * q / 12), r_ * math.sin(2 * math.pi * q / 12)) for q in range(12)]), 0.0, CABLE)

    # ============================================================================================ THE DESK MAT
    MAT_AT = V3(DCX + 60.0, 190.0, DTOP)
    fin(hs.prism_plan('desk_mat', [(MAT_AT.x + x_, MAT_AT.y + y_) for x_, y_ in hs.rrect(-400.0, -150.0, 400.0, 150.0, 12.0, 4)], DTOP, DTOP + 3.0), 1.0, FELT)

    # ============================================================================================ THE KEYBOARD
    # its own space: x across, y back (away from the typist), z up from the desk mat; placed centred at (840, 175)
    U = 19.05
    KB_AT = V3(840.0, 172.0, DTOP + 3.0 + 1.0)                 # (on its four feet, 1 over the mat)
    ROWS = [  # (row y in units from the front row's centre, [(x in units of the key's left edge, width u, height u)], tilt deg, row name)
        (5.5, [(0, 1, 1)] + [(2 + i, 1, 1) for i in range(4)] + [(6.5 + i, 1, 1) for i in range(4)] + [(11 + i, 1, 1) for i in range(4)] + [(15.25 + i, 1, 1) for i in range(3)], 7.0, 'F'),
        (4.0, [(i, 1, 1) for i in range(13)] + [(13, 2, 1)] + [(15.25 + i, 1, 1) for i in range(3)] + [(18.5 + i, 1, 1) for i in range(4)], 7.0, 'R1'),
        (3.0, [(0, 1.5, 1)] + [(1.5 + i, 1, 1) for i in range(12)] + [(13.5, 1.5, 1)] + [(15.25 + i, 1, 1) for i in range(3)] + [(18.5 + i, 1, 1) for i in range(3)] + [(21.5, 1, 2)], 3.0, 'R2'),
        (2.0, [(0, 1.75, 1)] + [(1.75 + i, 1, 1) for i in range(11)] + [(12.75, 2.25, 1)] + [(18.5 + i, 1, 1) for i in range(3)], 0.0, 'R3'),
        (1.0, [(0, 2.25, 1)] + [(2.25 + i, 1, 1) for i in range(10)] + [(12.25, 2.75, 1)] + [(16.25, 1, 1)] + [(18.5 + i, 1, 1) for i in range(3)] + [(21.5, 1, 2)], -3.0, 'R4'),
        (0.0, [(0, 1.25, 1), (1.25, 1.25, 1), (2.5, 1.25, 1), (3.75, 6.25, 1), (10, 1.25, 1), (11.25, 1.25, 1), (12.5, 1.25, 1), (13.75, 1.25, 1)] + [(15.25 + i, 1, 1) for i in range(3)]
         + [(18.5, 2, 1), (20.5, 1, 1)], -6.0, 'R5'),
    ]
    KW, KX0 = 22.5 * U, -11.25 * U                           # the key field: 428.6 wide, centred on x 0
    KY0 = -3.25 * U + 0.5 * U                                 # the front row's centre (y)


    def deck_z(y):
        """the deck's top under the keys: 15 at the front of the case, rising 3 degrees toward the back"""
        return 15.0 + (y + 72.0) * math.tan(math.radians(3.2))


    case_plan = hs.prism_plan('kb_case', [(x_, y_) for x_, y_ in hs.rrect(-223.0, -72.0, 223.0, 72.0, 7.0, 4)], 0.0, 40.0)
    case_side = hs.prism_section('kb_case_wedge', [(-80.0, -1.0), (80.0, -1.0), (80.0, deck_z(80.0)), (-80.0, deck_z(-80.0))], -230.0, 230.0)
    case = hs.boolean(case_plan, case_side, 'INTERSECT')
    # the key well: the deck stands 2 below the case's rim round the keys (a lip 5.5 wide all round the field)
    well = hs.skins('kb_well', [[[V3(x_, y_, deck_z(y_) - 2.0 + (0.0 if h_ == 0 else 30.0)) for x_, y_ in hs.rrect(KX0 - 4.0, KY0 - 0.5 * U - 4.0, KX0 + KW + 4.0, KY0 + 6.0 * U + 4.0, 3.0, 3)] for h_ in (0, 1)]])
    case = hs.boolean(case, well, 'DIFFERENCE')
    kb = [fin(case, 1.6, KDECK)]
    caps_sk, dish_sk, sw_sk = [], [], []


    def keycap(x0u, wu, hu, yc, tilt):
        """one cap: a rounded skirt 0.95 narrower than its pitch, rising 7.6 to a top inset 2.6 a side and 1.6 / 3.4 front /
        back, its top tilted by the row's sculpt; returns its skin and its dish (a cylinder along y, 0.8 below the top's
        middle, for keys under 2 u)"""
        x0 = KX0 + x0u * U + 0.48
        x1 = KX0 + (x0u + wu) * U - 0.48
        y0 = yc - 0.5 * U + 0.48 - (hu - 1) * U
        y1 = yc + 0.5 * U - 0.48
        zb = deck_z(yc) + 3.2                                 # (the cap's foot: its switch stands 3.2 off the deck)
        h = 7.6
        t = math.tan(math.radians(tilt))
        ycm = (y0 + y1) / 2

        def ring(ix0, iy0, ix1, iy1, r, z, tilted):
            return [V3(px, py, z + (t * (py - ycm) if tilted else 0.0)) for px, py in hs.rrect(ix0, iy0, ix1, iy1, r, 3)]
        rl = [ring(x0, y0, x1, y1, 1.0, zb, False), ring(x0, y0, x1, y1, 1.0, zb + 0.8, False),
              ring(x0 + 1.6, y0 + 1.0, x1 - 1.6, y1 - 1.8, 2.2, zb + h - 1.0, True), ring(x0 + 2.6, y0 + 1.6, x1 - 2.6, y1 - 3.4, 2.6, zb + h, True)]
        dish = None
        if wu < 2.0 and hu == 1:
            R_ = 38.0
            cx_, ctop = (x0 + x1) / 2, zb + h + t * ((y0 + 1.6 + y1 - 3.4) / 2 - ycm)
            n_ = V3(0.0, math.cos(math.radians(tilt)), math.sin(math.radians(tilt)))
            c0 = V3(cx_, ycm, ctop) + V3(0.0, -math.sin(math.radians(tilt)), math.cos(math.radians(tilt))) * (R_ - 0.8)
            dish = [hs.circle(c0 - n_ * 14.0, n_, R_, 0.0, 64), hs.circle(c0 + n_ * 14.0, n_, R_, 0.0, 64)]
        sw = bx(((x0 + x1) / 2 - 7.0, ycm - 7.0, deck_z(yc) - 2.3), ((x0 + x1) / 2 + 7.0, ycm + 7.0, zb + 0.6))      # (from the well's floor)
        return rl, dish, sw


    for yr, keys, tilt, rname in ROWS:
        yc = KY0 + yr * U
        for (x0u, wu, hu) in keys:
            rl, dish, sw = keycap(x0u, wu, hu, yc, tilt)
            caps_sk.append(rl)
            if dish:
                dish_sk.append(dish)
            sw_sk.append(sw)
    caps = hs.skins('keyboard_keycaps', caps_sk)
    caps = hs.boolean(caps, hs.skins('keyboard_dishes', dish_sk), 'DIFFERENCE')
    kb.append(fin(caps, 0.35, KEYCAP))
    kb.append(fin(hs.skins('keyboard_switches', sw_sk), 0.0, SWITCH))
    # the feet: two rubber pads at the front, two folded legs at the back (folded flat in their pockets)
    feet = [rev([(0.0, 0.0), (6.0, 0.0), (6.0, 1.6), (5.0, 2.2), (0.0, 2.2)], V3(sx * 190.0, -55.0, -1.0), (0, 0, 1), 20) for sx in (-1.0, 1.0)]
    feet += [bx((sx * 190.0 - 22.0, 52.0, -1.0), (sx * 190.0 + 22.0, 64.0, 0.6)) for sx in (-1.0, 1.0)]
    kb.append(fin(hs.skins('keyboard_feet', feet), 0.0, M('rubber_black', (0.02, 0.02, 0.02), 0.8)))
    for o_ in kb:
        place(o_, KB_AT, yaw=math.radians(-2.0))

    # ============================================================================================ THE MOUSE
    # its own space: x forward (to its nose), y to its left, z up from the mat; an ellipse-sectioned shell lofted along its
    # length (half-height H, half-width W at each station), cut flat underneath (the base), its buttons split by a 0.7 mm
    # groove down the middle and a seam across, the wheel in its slot, two thumb buttons on the left; placed at (1180, 190)
    MS = [(-1.5, 4.0, 8.0), (0.0, 10.0, 18.0), (3.0, 18.0, 24.0), (10.0, 27.0, 29.0), (22.0, 34.0, 31.0), (38.0, 38.5, 32.0), (54.0, 39.0, 31.5), (70.0, 37.0, 30.5),
          (84.0, 33.5, 29.5), (97.0, 29.0, 28.0), (107.0, 24.0, 25.5), (113.0, 18.5, 21.0), (117.0, 11.0, 13.0), (118.5, 4.0, 5.0)]
    shell = hs.loft('mouse_shell', [(x_, 0.0, w_, h_, 2.7) for x_, h_, w_ in MS], n=48)
    trim(shell, (0.0, 0.0, 1.5), (0.0, 0.0, -1.0))                       # (flat underneath, 1.5 up: the base plate under it)
    # (three cuts, one boolean each: cutters that overlap one another in ONE exact boolean empty the shell)
    shell = hs.boolean(shell, hs.box('mouse_split', (62.0, -0.35, 12.0), (125.0, 0.35, 50.0)), 'DIFFERENCE')          # between the buttons
    shell = hs.boolean(shell, hs.sweep('mouse_seam', [V3(62.0 - 0.006 * a_ * a_, a_, 35.0) for a_ in range(-36, 37, 3)],
                                       [(-0.35, -15.0), (0.35, -15.0), (0.35, 15.0), (-0.35, 15.0)], up=(0, 0, 1)), 'DIFFERENCE')   # the seam across, an arc
    shell = hs.boolean(shell, hs.box('mouse_wheel_slot', (83.0, -4.6, 18.0), (105.0, 4.6, 50.0)), 'DIFFERENCE')
    ms = [fin(shell, 0.3, PLASTIC)]
    ms.append(fin(hs.prism_plan('mouse_base', [(x_, y_) for x_, y_ in hs.rrect(2.0, -27.0, 114.0, 27.0, 14.0, 6)], 0.0, 2.2), 0.6, M('mouse_base_plastic', (0.05, 0.05, 0.05), 0.6)))
    WH = V3(94.0, 0.0, 22.5)                                              # (its tyre 4 proud of the shell)
    wheel = [rev([(0.0, -3.4), (9.0, -3.4), (10.6, -2.6), (11.2, -1.2), (11.2, 1.2), (10.6, 2.6), (9.0, 3.4), (0.0, 3.4)][::-1], WH, (0, 1, 0), 40)]
    for k_ in range(24):                                                  # the tyre's ribs
        a_ = 2 * math.pi * k_ / 24
        c_ = WH + V3(11.0 * math.cos(a_), 0.0, 11.0 * math.sin(a_))
        wheel.append([[c_ + V3(-0.7 * math.sin(a_) * 0 + dx_ * math.cos(a_ + math.pi / 2), dy_, dx_ * math.sin(a_ + math.pi / 2)) for dx_, dy_ in ((-0.8, -2.8), (0.8, -2.8), (0.8, 2.8), (-0.8, 2.8))],
                      [c_ + V3(0.9 * math.cos(a_) + dx_ * math.cos(a_ + math.pi / 2), dy_, 0.9 * math.sin(a_) + dx_ * math.sin(a_ + math.pi / 2)) for dx_, dy_ in ((-0.6, -2.6), (0.6, -2.6), (0.6, 2.6), (-0.6, 2.6))]])
    ms.append(fin(hs.skins('mouse_wheel', wheel), 0.0, M('rubber_black')))
    thumb = []
    for xa, xb_ in ((48.0, 64.0), (67.0, 82.0)):                          # two thumb buttons standing 1.2 off the left flank
        th_ = []
        for k_ in range(7):
            x_ = xa + (xb_ - xa) * k_ / 6
            th_.append([V3(x_, 28.4 + dy, 21.0 + dz) for dy, dz in ((0.0, -2.6), (1.6, -2.4), (2.2, 0.0), (1.6, 2.4), (0.0, 2.6))])
        thumb.append(th_)
    ms.append(fin(hs.skins('mouse_thumb_buttons', thumb), 0.0, PLASTIC))
    for o_ in ms:
        place(o_, V3(1185.0, 150.0, DTOP + 3.0), yaw=math.radians(90.0 - 6.0))

    # ============================================================================================ THE COMPUTER (a mid tower)
    # 210 wide, 450 deep, 470 high, on four rubber feet under the desk's right end, its front to the room: a steel case
    # rounded 3, the front a separate panel 6 proud with its perforated field (in the look's maps), the power button and
    # the top's ports at the front; its power lead along the floor to the double socket under the window's right
    TW_AT = V3(1430.0, 330.0, 0.0)
    case_t = hs.box('pc_case', (-105.0, -225.0, 14.0), (105.0, 225.0, 484.0))
    fin(case_t, 3.0, TOWER)
    fp = hs.box('pc_front_panel', (-105.0, -231.0, 14.0), (105.0, -225.0, 484.0))
    fp = hs.boolean(fp, hs.box('pc_front_field_cut', (-80.0, -233.0, 60.0), (80.0, -229.5, 440.0)), 'DIFFERENCE')
    fin(fp, 2.0, TOWER)
    tw = [case_t, fp]
    tw.append(fin(hs.box('pc_front_field', (-80.0, -230.0, 60.0), (80.0, -228.5, 440.0)), 0.0, M('pc_front_mesh', (0.02, 0.02, 0.02), 0.6)))
    tw.append(fin(hs.revolve('pc_power_button', [(0.0, 0.0), (9.0, 0.0), (9.0, 2.5), (8.0, 3.2), (0.0, 3.4)], at=V3(0.0, -195.0, 484.0), axis=(0, 0, 1), seg=32), 0.0, PLASTIC))
    tw.append(fin(hs.skins('pc_feet', [rev([(0.0, 0.0), (14.0, 0.0), (14.0, 12.0), (12.0, 14.0), (0.0, 14.0)], V3(sx * 80.0, sy * 190.0, 0.0), (0, 0, 1), 24)
                                       for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)]), 0.0, M('rubber_black')))
    ports_t = hs.box('pc_top_ports_plate', (-40.0, -215.0, 484.0), (40.0, -170.0, 485.5))
    tw.append(fin(ports_t, 0.4, PLASTIC))
    for o_ in tw:
        place(o_, TW_AT)
    lead = [TW_AT + V3(40.0, 225.0, 300.0), TW_AT + V3(40.0, 260.0, 260.0), TW_AT + V3(60.0, 300.0, 4.0), V3(1150.0, 1400.0, 4.0), V3(930.0, 2700.0, 4.0),
            V3(835.0, Y1 - 60.0, 4.0), V3(835.0, Y1 - 25.0, 120.0), V3(835.5, Y1 - 12.0, 300.0)]
    fin(hs.sweep('pc_power_lead', hs.fillet_path(lead, 60.0, 8), [(3.5 * math.cos(2 * math.pi * q / 12), 3.5 * math.sin(2 * math.pi * q / 12)) for q in range(12)]), 0.0, CABLE)
    fin(hs.revolve('socket_plug', [(0.0, 0.0), (19.0, 0.0), (19.5, 2.0), (19.5, 18.0), (17.0, 22.0), (8.0, 24.0), (0.0, 24.0)], at=V3(835.5, Y1 - 11.5, 300.0), axis=(0, -1, 0), seg=40), 0.0,
        M('switch_plastic_white'))      # (the Schuko plug in the double socket's right outlet)
    ns.update(CABLE=CABLE)
