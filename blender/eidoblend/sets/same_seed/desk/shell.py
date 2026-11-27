"""eidoblend.sets.same_seed.desk.shell: the desk room's shell, window, door, trim and fixtures (Blender). Millimetres;
the room's own space (x across, y to the back wall, z up from the floor).

A flat's room in a brick-and-plaster apartment block at night: plastered walls, an oak floor, white trim. The back wall
is the outside wall; in it a TWO-CASEMENT tilt-and-turn window (white uPVC, double glazed, a fixed mullion), set back in
a plastered reveal, its window board inside, a compact panel radiator under it, curtains drawn back on a rod; on the
right wall the DOOR in a wrap-round lining with architraves (a flush rebated leaf, a lever handle, two knuckle hinges on
the room side, as it opens in); skirting round the room, mitred at its corners and ended against the architraves; the
sockets and the switch (Schuko frames). Outside: the night (Poly Haven's CC0 HDRI hansaplatz, lit flats across a
square), reprojected onto a backdrop as seen from the room (camera only). One mass per part (booleans with one closed
cutter), radii in millimetres, glazing as panels in gaskets and beads, glass with its thickness.

    shell.build(ns)          # ns: kit.begin()'s namespace (ns['LIB'] gives the night's HDRI)
"""


def build(ns):
    (CEIL, CHROME, DARK, FLOOR, GASKET, GLASS, HT, LIB, M, PVC, RAD, SPACER, SWITCHES, TRIM, TW, TWB, V3, Vector, WALL, WCX, X0, X1, Y0,
     Y1, bmesh, bpy, bx, fin, frame_loop, hs, math, mitre_sweep, offset2, rev, u_loop) = (
        ns[k] for k in ('CEIL', 'CHROME', 'DARK', 'FLOOR', 'GASKET', 'GLASS', 'HT', 'LIB', 'M', 'PVC', 'RAD', 'SPACER', 'SWITCHES', 'TRIM', 'TW',
                        'TWB', 'V3', 'Vector', 'WALL', 'WCX', 'X0', 'X1', 'Y0', 'Y1', 'bmesh', 'bpy', 'bx', 'fin', 'frame_loop', 'hs', 'math',
                        'mitre_sweep', 'offset2', 'rev', 'u_loop'))
    # ============================================================================================ WALLS, FLOOR, CEILING
    WX0, WX1 = WCX - 700.0, WCX + 700.0                     # the window's masonry opening: 1400 wide
    WZ0, WZ1 = 875.0, 2310.0                                # the parapet's top (under the board) and the lintel
    FY0, FD = Y1 + 200.0, 70.0                              # the window frame: its room face 200 back in the reveal, 70 deep
    BOARD = 900.0                                           # the window board's top
    DY0, DY1 = 193.0, 1067.0                                # the door: its lining's outer faces (along y) on the right wall
    DZ1 = 1992.0                                            # the lining head's top

    back = hs.box('wall_back', (X0 - TW, Y1, 0.0), (X1 + TW, Y1 + TWB, HT))
    back = hs.boolean(back, hs.box('window_opening', (WX0, Y1 - 50.0, WZ0), (WX1, Y1 + TWB + 50.0, WZ1)), 'DIFFERENCE')
    fin(back, 0.0, WALL)
    fin(hs.box('wall_left', (X0 - TW, Y0 - TW, 0.0), (X0, Y1, HT)), 0.0, WALL)
    right = hs.box('wall_right', (X1, Y0 - TW, 0.0), (X1 + TW, Y1, HT))
    right = hs.boolean(right, hs.box('door_opening', (X1 - 50.0, DY0, -50.0), (X1 + TW + 50.0, DY1, DZ1)), 'DIFFERENCE')
    fin(right, 0.0, WALL)
    _front = fin(hs.box('wall_front_unseen', (X0, Y0 - TW, 0.0), (X1, Y0, HT)), 0.0, WALL)       # (the lens looks through it:
    _front.visible_camera = False                                                               #  unseen by the camera, it still
    _front['what'] = 'the room front wall: hidden from camera rays only; it closes the room for light, shadow and reflection'      # closes the room)
    fin(hs.box('room_floor', (X0 - TW, Y0 - TW, -150.0), (X1 + TW, Y1 + TWB, 0.0)), 0.0, FLOOR)
    fin(hs.box('room_ceiling', (X0 - TW, Y0 - TW, HT), (X1 + TW, Y1 + TWB, HT + 200.0)), 0.0, CEIL)


    def PB(a, z, y):
        """on the back wall's window: a along x, z up, y absolute (mm)"""
        return V3(a, y, z)


    # ============================================================================================ THE WINDOW
    # The frame (Blendrahmen): 52 wide members, 70 deep, its inner 10 cut back where the sash laps it; a fixed mullion 84
    # wide in the middle. In each half a sash (Fluegel): 60 wide members, 62 deep, its room face 6 proud of the frame's and
    # lapping it by 8 (a 2 mm shadow gap against the frame's step), its outer arris rounded; inside it the glazing bead (18
    # wide, clipped in: its own part, its joint a line), the black gasket, the sealed unit (4 + 16 + 4 mm: two panes, the
    # aluminium spacer between them at their edge, hidden behind the bead).
    FX0, FX1, FZ0, FZ1 = WX0 + 10.0, WX1 - 10.0, BOARD, WZ1 - 10.0
    FW, MW = 52.0, 84.0
    FRAME = [(0.0, 0.0), (0.78, 0.0), (0.808, 1.5), (0.808, 58.0), (1.0, 58.0), (1.0, FD), (0.0, FD)]
    fin(frame_loop('window_frame', FX0, FX1, FZ0, FZ1, FW, FW, FW, FW, FRAME, lambda x, z, v: PB(x, z, FY0 + v)), 0.8, PVC)
    fin(hs.prism_plan('window_mullion', [(WCX + px, FY0 + py) for px, py in ((-32.0, 0.0), (32.0, 0.0), (32.0, 58.0), (42.0, 58.0), (42.0, FD), (-42.0, FD), (-42.0, 58.0), (-32.0, 58.0))],
                      FZ0 + FW * 0.808 - 1.0, FZ1 - FW * 0.808 + 1.0), 0.8, PVC)
    SASH = [(0.0, 3.0), (0.03, 0.6), (0.08, 0.0), (0.94, 0.0), (1.0, 2.5), (1.0, 62.0), (0.0, 62.0)]
    BEAD = [(0.0, 0.0), (0.7, 0.0), (0.9, 2.5), (1.0, 7.0), (1.0, 20.0), (0.0, 20.0)]
    SW, BW = 60.0, 18.0
    hw = []
    for k, (a, b) in enumerate(((FX0 + FW, WCX - MW / 2), (WCX + MW / 2, FX1 - FW))):
        sx0, sx1, sz0, sz1 = a - 8.0, b + 8.0, FZ0 + FW - 8.0, FZ1 - FW + 8.0          # the sash laps the frame by 8
        sy = FY0 - 6.0                                                                    # its room face 6 proud of the frame's
        fin(frame_loop(f'window_sash_{k}', sx0, sx1, sz0, sz1, SW, SW, SW, SW, SASH, lambda x, z, v, sy=sy: PB(x, z, sy + v)), 0.6, PVC)
        bx0, bx1, bz0, bz1 = sx0 + SW, sx1 - SW, sz0 + SW, sz1 - SW
        fin(frame_loop(f'window_bead_{k}', bx0, bx1, bz0, bz1, BW, BW, BW, BW, BEAD, lambda x, z, v, sy=sy: PB(x, z, sy + 2.0 + v)), 0.0, PVC)
        gy = sy + 22.0                                                                    # the unit's room-side face
        gx0, gx1, gz0, gz1 = bx0 + 0.5, bx1 - 0.5, bz0 + 0.5, bz1 - 0.5                  # its edge against the sash's inner face
        fin(frame_loop(f'window_gasket_{k}', bx0 + BW - 3.0, bx1 - BW + 3.0, bz0 + BW - 3.0, bz1 - BW + 3.0, 5.0, 5.0, 5.0, 5.0,
                       [(0.0, 0.0), (1.0, 0.0), (1.0, 2.0), (0.0, 2.0)], lambda x, z, v, gy=gy: PB(x, z, gy - 2.0 + v)), 0.0, GASKET)
        fin(hs.box(f'window_pane_in_{k}', (gx0, gy, gz0), (gx1, gy + 4.0, gz1)), 0.0, GLASS)
        fin(hs.box(f'window_pane_out_{k}', (gx0, gy + 20.0, gz0), (gx1, gy + 24.0, gz1)), 0.0, GLASS)
        fin(frame_loop(f'window_spacer_{k}', gx0 + 0.5, gx1 - 0.5, gz0 + 0.5, gz1 - 0.5, 13.0, 13.0, 13.0, 13.0,
                       [(0.0, 0.0), (1.0, 0.0), (1.0, 16.0), (0.0, 16.0)], lambda x, z, v, gy=gy: PB(x, z, gy + 4.0 + v)), 0.0, SPACER)
        # the handle (an "olive") on the meeting stile at 1550, its lever down (shut): a rounded rose, a neck, a cranked lever
        hx = (sx1 - SW / 2) if k == 0 else (sx0 + SW / 2)
        hz = 1550.0
        rose = [(hx + max(-15.0, min(15.0, 19.0 * math.cos(math.radians(t)))), hz + max(-37.0, min(37.0, 41.0 * math.sin(math.radians(t))))) for t in range(0, 360, 10)]
        hw.append([[V3(px, sy - zz, pz) for px, pz in rose] for zz in (0.0, 9.0)])
        hw.append([hs.circle(V3(hx, sy - 9.0, hz), (0, -1, 0), r_, h_, 20) for r_, h_ in ((10.0, 0.0), (10.0, 14.0), (8.5, 20.0))])
        lev = []
        for i in range(13):                                  # the lever: a flattened oval section, 112 long, narrowing to its tip
            t = i / 12.0
            zc = hz + 6.0 - 114.0 * t
            rw, rd = 9.5 - 2.0 * t, 6.5 - 1.0 * t
            yc = sy - 9.0 - 26.0 + 4.0 * t
            lev.append([V3(hx + rw * math.cos(math.radians(a_)), yc + rd * math.sin(math.radians(a_)), zc) for a_ in range(0, 360, 20)])
        lev.append([V3(hx + 4.0 * math.cos(math.radians(a_)), sy - 9.0 - 22.0 + 2.0 * math.sin(math.radians(a_)), hz - 112.0) for a_ in range(0, 360, 20)])
        hw.append(lev)
        # the hinge covers at the outer corners (the turn's side): rounded caps on frame and sash
        cx = sx0 + 12.0 if k == 0 else sx1 - 12.0
        for zc_ in (sz0 + 30.0, sz1 - 30.0):
            hw.append(bx((cx - 9.0, sy - 7.0, zc_ - 28.0), (cx + 9.0, sy, zc_ + 28.0)))
    fin(hs.skins('window_handles_and_hinges', hw), 0.0, PVC)
    # THE WINDOW BOARD inside: 25 thick, from the frame to 30 proud of the wall, its ears 40 past the reveal on the wall face
    # (notched round the reveal), its arrises rounded 3
    fin(hs.prism_plan('window_board', [(WX0 - 40.0, Y1 - 30.0), (WX1 + 40.0, Y1 - 30.0), (WX1 + 40.0, Y1), (WX1, Y1), (WX1, FY0), (WX0, FY0), (WX0, Y1),
                                       (WX0 - 40.0, Y1)], BOARD - 25.0, BOARD), 3.0, M('window_board_stone', (0.6, 0.58, 0.55), 0.35))
    # the outside sill: a pressed aluminium sheet falling outward from under the frame, its drip turned down
    fin(hs.prism_section('window_sill_outside', [(FY0 + FD - 5.0, FZ0 - 2.0), (Y1 + TWB + 45.0, FZ0 - 27.0), (Y1 + TWB + 45.0, FZ0 - 57.0), (Y1 + TWB + 42.0, FZ0 - 57.0),
                                                 (Y1 + TWB + 42.0, FZ0 - 30.0), (FY0 + FD - 5.0, FZ0 - 5.0)], WX0 + 2.0, WX1 - 2.0), 0.0, SPACER)

    # ============================================================================================ THE NIGHT OUTSIDE
    # A slab 6 m out, its face mapped from the panorama by the direction from the room's eye (the middle of the room at
    # 1.45 m): the CC0 HDRI is seen through the window as it would be from in here (no flat photograph pasted on a card).
    NIGHT_HDR = LIB.hdri('hansaplatz', '4k')
    # (the panorama was taken at street level: seen from the room's eye at 1.45 its ground-floor shop signs would stand
    #  legible in the window. The room is a first-floor flat: its eye 2.8 m above the panorama's, so the window holds the
    #  upper storeys' lit windows, the roofline and the night sky across the square)
    EYE = Vector((WCX * hs.MM, 0.0, 1.45 - 2.8))
    LON0 = 0.52                                             # the panorama's column that lies straight out of the window
    nb = bmesh.new()
    NX, NZ = 48, 24
    uvl = nb.loops.layers.uv.verify()
    gf = [[nb.verts.new(((WCX - 4000.0 + 8000.0 * i / NX) * hs.MM, 9.0, (100.0 + 4400.0 * j / NZ) * hs.MM)) for i in range(NX + 1)] for j in range(NZ + 1)]
    gb = [[nb.verts.new((v_.co.x, 9.02, v_.co.z)) for v_ in row] for row in gf]
    for j in range(NZ):
        for i in range(NX):
            f = nb.faces.new((gf[j][i], gf[j][i + 1], gf[j + 1][i + 1], gf[j + 1][i]))
            for lp in f.loops:
                d = lp.vert.co - EYE
                lp[uvl].uv = (LON0 + math.atan2(d.x, d.y) / (2 * math.pi), 0.5 + math.atan2(d.z, math.hypot(d.x, d.y)) / math.pi)
            nb.faces.new((gb[j][i], gb[j + 1][i], gb[j + 1][i + 1], gb[j][i + 1]))
    ring_f = [gf[0][i] for i in range(NX + 1)] + [gf[j][NX] for j in range(1, NZ + 1)] + [gf[NZ][i] for i in range(NX - 1, -1, -1)] + [gf[j][0] for j in range(NZ - 1, 0, -1)]
    ring_b = [gb[0][i] for i in range(NX + 1)] + [gb[j][NX] for j in range(1, NZ + 1)] + [gb[NZ][i] for i in range(NX - 1, -1, -1)] + [gb[j][0] for j in range(NZ - 1, 0, -1)]
    for k_ in range(len(ring_f)):
        nb.faces.new((ring_f[k_], ring_b[k_], ring_b[(k_ + 1) % len(ring_b)], ring_f[(k_ + 1) % len(ring_f)]))
    night = hs.obj('night_outside', nb)
    mn = bpy.data.materials.new('desk.night_outside_hansaplatz')
    mn.use_nodes = True
    nt = mn.node_tree
    for n_ in list(nt.nodes):
        if n_.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n_)
    ti = nt.nodes.new('ShaderNodeTexImage')
    ti.image = bpy.data.images.load(NIGHT_HDR, check_existing=True)
    ti.interpolation, ti.extension = 'Cubic', 'REPEAT'
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(ti.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], next(n_ for n_ in nt.nodes if n_.type == 'OUTPUT_MATERIAL').inputs[0])
    for c_ in list(night.users_collection):
        c_.objects.unlink(night)
    hs.col.objects.link(night)
    night.data.materials.append(mn)
    night.visible_shadow = False
    night['what'] = 'the night outside: CC0 Poly Haven HDRI hansaplatz (4k) reprojected from the room eye; camera only, casts nothing'
    _nb = bmesh.new()
    _nb.from_mesh(night.data)
    hs.REPORT.append((night.name, sum(1 for e in _nb.edges if not e.is_manifold), 0.0, len(night.data.polygons)))
    _nb.free()

    # ============================================================================================ THE RADIATOR
    # A compact panel radiator, type 22 (two water panels, convector fins between them, a slotted top grille, side covers):
    # 1200 long, 600 high, 100 deep, hung 45 off the wall under the window; its front panel pressed with vertical channels
    # every 33.3 mm (36 of them), stopped by the plain headers top and bottom; the thermostat head on its right end, the two
    # pipes down into the floor through their collars.
    RX0, RX1, RZ0, RZ1 = WCX - 600.0, WCX + 600.0, 150.0, 750.0
    RYB = Y1 - 45.0                                          # its back
    RYF = RYB - 100.0                                        # its front
    plan = [(RX0, RYF + 18.0)]
    NCH = 36
    per = (RX1 - RX0) / NCH
    for c_ in range(NCH):
        x0_ = RX0 + c_ * per
        for t_, d_ in ((0.0, 0.0), (0.18, 0.0), (0.26, 1.4), (0.34, 3.6), (0.42, 4.6), (0.5, 4.8), (0.58, 4.6), (0.66, 3.6), (0.74, 1.4), (0.82, 0.0)):
            plan.append((x0_ + t_ * per, RYF + d_))
    plan += [(RX1, RYF), (RX1, RYF + 18.0)]
    front = hs.prism_plan('radiator_front_panel', plan, RZ0 + 8.0, RZ1 - 8.0)
    front = hs.boolean(front, hs.skins('radiator_headers', [bx((RX0, RYF, RZ0), (RX1, RYF + 18.0, RZ0 + 42.0)), bx((RX0, RYF, RZ1 - 42.0), (RX1, RYF + 18.0, RZ1))]), 'UNION')
    fin(front, 2.0, RAD)
    fin(hs.box('radiator_back_panel', (RX0, RYB - 18.0, RZ0), (RX1, RYB, RZ1)), 2.0, RAD)
    fins = []
    for c_ in range(int((RX1 - RX0) / 25.0)):                 # the convector fins between the panels, seen through the grille
        xf = RX0 + 12.5 + 25.0 * c_
        fins.append(bx((xf - 0.4, RYF + 19.0, RZ0 + 40.0), (xf + 0.4, RYB - 19.0, RZ1 - 6.0)))
    fin(hs.skins('radiator_fins', fins), 0.0, RAD)
    grille = hs.box('radiator_grille', (RX0 - 2.0, RYF - 1.0, RZ1), (RX1 + 2.0, RYB + 1.0, RZ1 + 2.0))
    slots = []
    for c_ in range(int((RX1 - RX0 - 40.0) / 12.0)):
        xs = RX0 + 20.0 + 12.0 * c_
        slots.append(bx((xs, RYF + 14.0, RZ1 - 5.0), (xs + 5.0, RYB - 14.0, RZ1 + 7.0)))
    grille = hs.boolean(grille, hs.skins('radiator_slots', slots), 'DIFFERENCE')
    fin(grille, 0.8, RAD)
    for nm_, xe in (('l', RX0 - 2.0), ('r', RX1)):
        fin(hs.prism_section(f'radiator_side_cover_{nm_}', hs.rrect(RYF - 1.0, RZ0, RYB + 1.0, RZ1 + 2.0, 6.0, 4), xe, xe + 2.0), 0.6, RAD)
    TH = V3(RX1 + 2.0, RYF + 48.0, RZ1 - 55.0)               # the thermostat head on the valve, out of the right end
    fin(hs.revolve('radiator_thermostat', [(0.0, 0.0), (15.0, 0.0), (15.0, 14.0), (20.0, 16.0), (25.0, 20.0), (25.5, 30.0), (25.0, 70.0), (23.0, 76.0), (19.0, 79.0), (0.0, 80.0)],
                   at=TH, axis=(1, 0, 0), seg=40), 0.0, SWITCHES)
    ribs = []
    for c_ in range(16):
        a_ = 2 * math.pi * c_ / 16
        ribs.append(bx((TH.x + 32.0, TH.y + 24.4 * math.cos(a_) - 1.6, TH.z + 24.4 * math.sin(a_) - 1.6), (TH.x + 72.0, TH.y + 26.6 * math.cos(a_) + 1.6, TH.z + 26.6 * math.sin(a_) + 1.6)))
    fin(hs.skins('radiator_thermostat_grip', ribs), 0.0, SWITCHES)
    pp = []
    for xp in (RX1 - 35.0, RX1 - 85.0):                       # the two pipes (15 copper, painted) and their floor collars
        pp.append([hs.circle(V3(xp, RYB - 50.0, z_), (0, 0, 1), 7.5, 0.0, 16) for z_ in (-20.0, RZ0 + 10.0)])
        pp.append(rev([(0.0, 0.0), (17.0, 0.0), (17.0, 3.0), (15.0, 9.0), (9.0, 11.0), (0.0, 11.0)], V3(xp, RYB - 50.0, 0.0), (0, 0, 1), 32))
    fin(hs.skins('radiator_pipes_and_collars', pp), 0.0, RAD)

    # ============================================================================================ THE CURTAINS
    # A rod on two brackets 140 over the lintel, ball finials; two lined curtains drawn back to either side of the window,
    # hung from rings: a uniform cloth 1.6 thick whose plan is a run of pleats from the heading (regular, deep) that open
    # and slacken toward the hem (16.80: folds from the support, faded in); the hem 15 above the floor.
    RODZ, RODY = WZ1 + 140.0, Y1 - 95.0
    ROD0, ROD1 = WX0 - 360.0, WX1 + 360.0
    rod = [[hs.circle(V3(ROD0, RODY, RODZ), (1, 0, 0), 10.0, h_, 24) for h_ in (0.0, ROD1 - ROD0)]]
    for xe, s_ in ((ROD0, -1.0), (ROD1, 1.0)):
        rod.append(rev([(0.0, 0.0), (8.0, 0.5), (14.0, 4.0), (19.0, 12.0), (20.0, 20.0), (19.0, 28.0), (14.0, 36.0), (8.0, 39.5), (0.0, 40.0)], V3(xe, RODY, RODZ), (s_, 0, 0), 24))
    for xb in (ROD0 + 120.0, ROD1 - 120.0):                 # the brackets: a wall plate, an arm, a saddle under the rod
        rod.append(rev([(0.0, 0.0), (28.0, 0.0), (28.0, 6.0), (24.0, 9.0), (0.0, 9.0)], V3(xb, Y1, RODZ), (0, -1, 0), 32))
        rod.append([hs.circle(V3(xb, Y1 - 9.0, RODZ), (0, -1, 0), 7.0, h_, 16) for h_ in (0.0, 95.0 - 9.0)])
        rod.append(rev([(0.0, 0.0), (13.0, 0.0), (14.0, 6.0), (12.0, 10.0), (0.0, 10.0)], V3(xb, RODY, RODZ - 22.0), (0, 0, 1), 24))
    ROD_M = M('curtain_rod_black_steel', (0.05, 0.05, 0.05), 0.35, 1.0)
    fin(hs.skins('curtain_rod', rod), 0.0, ROD_M)


    def curtain(name, xa, xb, lead_right):
        """a curtain gathered between xa and xb (mm) along the rod: its plan at each height a pleated line with the cloth's
        thickness; the pleats' depth grows toward the hem; the leading edge (toward the window) falls straight"""
        rl = []
        n_pl = int((xb - xa) / 95.0)
        top, hem = RODZ - 22.0, 15.0
        for k_ in range(31):
            z_ = top - (top - hem) * (k_ / 30.0) ** 1.15
            t = (top - z_) / (top - hem)
            amp = 42.0 + 14.0 * t
            NP = n_pl * 12
            line = []
            for i in range(NP + 1):
                u = i / NP
                wob = 1.0 + 0.12 * math.sin(3.1 * u * n_pl + 1.3) * t
                line.append((xa + (xb - xa) * u, RODY - 4.0 - amp * wob * (0.5 - 0.5 * math.cos(2 * math.pi * n_pl * u))))
            if lead_right:
                line.append((xb + 25.0 * (1.0 - 0.4 * t), RODY - 4.0))
            else:
                line.insert(0, (xa - 25.0 * (1.0 - 0.4 * t), RODY - 4.0))
            other = offset2(line, 1.6)
            rl.append([V3(x_, y_, z_) for x_, y_ in line] + [V3(x_, y_, z_) for x_, y_ in other[::-1]])
        return hs.rings(name, rl)


    CLOTH = M('curtain_linen', (0.45, 0.42, 0.38), 0.85)
    ring_sk = []
    for nm_, xa_, xb_, lr in (('left', ROD0 + 30.0, WX0 + 40.0, True), ('right', WX1 - 40.0, ROD1 - 30.0, False)):
        fin(curtain(f'curtain_{nm_}', xa_, xb_, lr), 0.0, CLOTH)
        n_pl = int((xb_ - xa_) / 95.0)
        for i in range(n_pl + 1):                            # a ring over every back fold, where its hook takes the heading
            xr = xa_ + (xb_ - xa_) * i / n_pl
            big = hs.circle(V3(xr, RODY, RODZ - 2.0), (1, 0, 0), 15.0, 0.0, 24)
            ring_sk.append([hs.circle(p, (big[(q + 1) % 24] - big[q - 1]).normalized(), 2.2, 0.0, 8, (1, 0, 0)) for q, p in enumerate(big)] + [hs.circle(big[0], (big[1] - big[-1]).normalized(), 2.2, 0.0, 8, (1, 0, 0))])
    rs = bmesh.new()
    for rl_ in ring_sk:
        hs._skin(rs, rl_, close_u=True, caps=False)
    fin(hs.obj('curtain_rings', rs), 0.0, ROD_M)

    # ============================================================================================ THE DOOR
    # In the right wall, to the hall: a wrap-round lining (jambs and head 20 thick across the wall), architraves 70 wide and
    # 12 thick on the room face, mitred at the head; the leaf flush and rebated (its 15 lip laps the frame by 13 on three
    # sides), on two knuckle hinges on the room side (it opens in), a lever handle on a round rose, the key rose under it
    # (its keyhole cut); 7 under the leaf.
    fin(hs.box('door_lining_front', (X1, DY0, 0.0), (X1 + TW, DY0 + 20.0, DZ1)), 0.8, TRIM)
    fin(hs.box('door_lining_back', (X1, DY1 - 20.0, 0.0), (X1 + TW, DY1, DZ1)), 0.8, TRIM)
    fin(hs.box('door_lining_head', (X1, DY0 + 20.0, DZ1 - 20.0), (X1 + TW, DY1 - 20.0, DZ1)), 0.8, TRIM)


    def PR(a, z, v):
        """on the right wall: a along y, z up; v proud of the plaster, toward the room"""
        return V3(X1 - v, a, z)


    ARCH = [(0.0, 0.0), (0.0, 9.5), (1.2, 11.4), (3.5, 12.0), (64.0, 12.0), (68.0, 10.8), (70.0, 8.0), (70.0, 0.0)]
    fin(u_loop('door_architrave', DY0 + 20.0, DY1 - 20.0, 0.0, DZ1 - 20.0, ARCH, PR), 0.0, TRIM)
    LF = X1 - 12.0 - 15.0                                     # the leaf's room face (its lip lies on the architrave's)
    LY0, LY1, LZ1 = DY0 + 20.0 - 13.0, DY1 - 20.0 + 13.0, DZ1 - 20.0 + 13.0
    leaf = hs.box('door_leaf', (LF, LY0, 7.0), (X1 - 12.0, LY1, LZ1))
    leaf = hs.boolean(leaf, hs.box('door_leaf_body', (LF + 1.0, DY0 + 20.0 + 3.0, 7.0), (X1 - 12.0 + 25.0, DY1 - 20.0 - 3.0, DZ1 - 20.0 - 3.0)), 'UNION')
    fin(leaf, 2.5, M('door_lacquer_white', (0.74, 0.74, 0.72), 0.3))
    KN = [(0.0, 0.0), (7.5, 0.0), (7.5, 58.0), (7.0, 59.5), (7.0, 60.5), (7.5, 62.0), (7.5, 118.0), (6.5, 120.0), (4.0, 121.5), (0.0, 122.0)]
    fin(hs.skins('door_hinges', [rev(KN, V3(LF - 7.0, LY0 + 4.0, zc_ - 61.0), (0, 0, 1), 24) for zc_ in (260.0, 1700.0)]), 0.0, CHROME)
    HZ, HY = 1050.0, DY1 - 20.0 - 3.0 - 55.0                  # the handle 55 in from the lock's edge
    ROSE = [(0.0, 0.0), (26.0, 0.0), (26.0, 5.0), (24.5, 8.0), (20.0, 9.0), (0.0, 9.0)]
    hd = [rev(ROSE, V3(LF, HY, HZ), (-1, 0, 0), 48), rev(ROSE, V3(LF, HY, HZ - 72.0), (-1, 0, 0), 48),
          [hs.circle(V3(LF, HY, HZ), (-1, 0, 0), r_, h_, 24) for r_, h_ in ((9.0, 9.0), (9.0, 50.0), (9.5, 56.0))],
          [hs.circle(V3(LF - 52.0, HY, HZ), (-1, 0, 0), r_, h_, 20) for r_, h_ in ((9.5, 0.0), (9.5, 10.0), (11.0, 13.0), (9.5, 21.0))]]
    lever = [hs.circle(V3(LF - 64.0, HY + 8.0 - 136.0 * (i / 14.0), HZ), (0, -1, 0), 9.5 - 1.0 * (i / 14.0), 0.0, 20) for i in range(15)]
    lever.append(hs.circle(V3(LF - 64.0, HY - 134.0, HZ), (0, -1, 0), 4.0, 0.0, 20))
    hd.append(lever)
    handle = hs.skins('door_handle', hd)
    KEY = [(-4.0, 2.0), (-4.0, 6.0), (-2.0, 8.0), (2.0, 8.0), (4.0, 6.0), (4.0, 2.0), (2.5, 0.0), (2.5, -10.0), (-2.5, -10.0), (-2.5, 0.0)]
    handle = hs.boolean(handle, hs.skins('door_keyhole_cut', [[[V3(xx, HY + px, HZ - 72.0 + pz) for px, pz in KEY] for xx in (LF - 12.0, LF + 3.0)]]), 'DIFFERENCE')
    fin(handle, 0.0, CHROME)
    fin(hs.box('door_backing', (X1 + 30.0, DY0 + 20.0, 0.0), (X1 + TW - 10.0, DY1 - 20.0, DZ1 - 20.0)), 0.0, DARK)      # (the hall: nothing is seen past the leaf)

    # ============================================================================================ SKIRTING
    # 80 high, 15 thick, a rounded top (white painted): one run along the right wall's back part, the back wall and the left
    # wall, mitred at the two corners; one run along the right wall's front part; both ended square against the door's
    # architraves (16.63: trim seated and ended)
    SK = [(0.0, 0.0), (15.0, 0.0), (15.0, 62.0), (14.2, 68.0), (12.0, 73.5), (8.5, 77.5), (4.5, 79.6), (0.0, 80.0)]
    fin(mitre_sweep('skirting_back_and_sides', [(X1, DY1 + 50.0), (X1, Y1), (X0, Y1), (X0, Y0)], SK), 0.0, TRIM)
    fin(mitre_sweep('skirting_right_front', [(X1, Y0), (X1, DY0 - 50.0)], SK), 0.0, TRIM)

    # ============================================================================================ SOCKETS AND THE SWITCH
    # Schuko frames (80 x 80 x 9, corners rounded 8; a two-gang 151 long) round inserts: each a round well 40 across and 16
    # deep with its two pin holes and earth clips; the switch a rocker in its frame. Sockets 300 over the floor, the switch
    # at 1050 by the door's latch side.


    def on_wall(c_, u, n, px, pz, h=0.0):
        return c_ + u * px + Vector((0.0, 0.0, pz)) + n * h


    def socket(name, at, n, u, gang=1):
        n, u = Vector(n), Vector(u)
        w = 80.0 + 71.0 * (gang - 1)
        fr = hs.skins(name + '_frame', [[[on_wall(at, u, n, px, pz, h_) for px, pz in hs.rrect(-w / 2, -40.0, w / 2, 40.0, 8.0, 4)] for h_ in (0.0, 9.0)]])
        centres = [at + u * ((g_ - (gang - 1) / 2.0) * 71.0) for g_ in range(gang)]
        fr = hs.boolean(fr, hs.skins(name + '_cut', [[[on_wall(c_, u, n, px, pz, h_) for px, pz in hs.rrect(-28.0, -28.0, 28.0, 28.0, 3.0, 2)] for h_ in (-2.0, 12.0)] for c_ in centres]), 'DIFFERENCE')
        fin(fr, 1.2, SWITCHES)
        for k_, c_ in enumerate(centres):
            ins = hs.skins(f'{name}_insert_{k_}', [[[on_wall(c_, u, n, px, pz, h_) for px, pz in hs.rrect(-27.5, -27.5, 27.5, 27.5, 3.0, 2)] for h_ in (-20.0, 11.0)]])
            well = [[hs.circle(c_ + n * h_, n, 20.0, 0.0, 48) for h_ in (-5.0, 14.0)]]
            for dx in (-9.5, 9.5):
                well.append([hs.circle(c_ + u * dx + n * h_, n, 2.4, 0.0, 12) for h_ in (-12.0, -4.0)])
            ins = hs.boolean(ins, hs.skins(f'{name}_well_{k_}', well), 'DIFFERENCE')
            fin(ins, 0.8, SWITCHES)
            fin(hs.skins(f'{name}_earth_clips_{k_}', [[[on_wall(c_, u, n, px, s_ * pz, h_) for px, pz in ((-5.0, 17.0), (5.0, 17.0), (5.0, 20.5), (-5.0, 20.5))] for h_ in (-5.0, 8.0)]
                                                       for s_ in (1.0, -1.0)]), 0.0, CHROME)


    socket('socket_back_desk', V3(800.0, Y1, 300.0), (0, -1, 0), (1, 0, 0), gang=2)
    socket('socket_back_left', V3(-2300.0, Y1, 300.0), (0, -1, 0), (1, 0, 0))
    socket('socket_back_right', V3(2350.0, Y1, 300.0), (0, -1, 0), (1, 0, 0))
    socket('socket_left_wall', V3(X0, 900.0, 300.0), (1, 0, 0), (0, -1, 0))
    socket('socket_right_wall', V3(X1, DY1 + 300.0, 300.0), (-1, 0, 0), (0, 1, 0))
    SWZ, SWY = 1050.0, DY1 + 50.0 + 110.0
    swf = hs.skins('switch_frame', [[[on_wall(V3(X1, SWY, SWZ), Vector((0, 1, 0)), Vector((-1, 0, 0)), px, pz, h_) for px, pz in hs.rrect(-40.0, -40.0, 40.0, 40.0, 8.0, 4)] for h_ in (0.0, 9.0)]])
    swf = hs.boolean(swf, hs.skins('switch_cut', [bx((X1 - 12.0, SWY - 28.0, SWZ - 28.0), (X1 + 2.0, SWY + 28.0, SWZ + 28.0))]), 'DIFFERENCE')
    fin(swf, 1.2, SWITCHES)
    rk = []                                                  # the rocker: 54 square, pressed at its foot (the light is off)
    for j in range(7):
        zz = -27.0 + 54.0 * j / 6.0
        proud = 11.0 + 2.4 * (zz / 27.0) + 0.6 * (1.0 - (zz / 27.0) ** 2)
        rk.append([V3(X1 - (2.0 if abs(px) > 26.5 else proud), SWY + px, SWZ + zz) for px in (-27.0, -26.0, -20.0, 0.0, 20.0, 26.0, 27.0)] +
                  [V3(X1 + 1.0, SWY + px, SWZ + zz) for px in (27.0, -27.0)])
    fin(hs.rings('switch_rocker', rk), 0.0, SWITCHES)
    hs.sweep_tmp()
