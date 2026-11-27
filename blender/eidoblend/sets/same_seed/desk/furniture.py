"""eidoblend.sets.same_seed.desk.furniture: the desk (Blender). Millimetres; the room's own space.

A solid oak top, 1600 x 700 x 28, its arrises rounded 3 and its corners 6 in plan, on a WELDED frame of black
powder-coated square tube (40 x 40 legs, 40 x 20 rails on edge under the top, mitred and ground: one mass), adjustable
glides under the legs, the top fixed through the rails' plates; a 60 mm cable grommet through the top at the back right
(its ring and slotted cap), where the screen's and the computer's leads go down. The top's face at z 740, its middle
over (900, 300).

    furniture.build(ns)      # adds DCX, DCY, DTOP, DD (the top's middle, face and depth), GX, GY (the grommet)
"""


def build(ns):
    (DARK, M, V3, bx, fin, hs, rev) = (ns[k] for k in ('DARK', 'M', 'V3', 'bx', 'fin', 'hs', 'rev'))
    DCX, DCY, DTOP = 900.0, 300.0, 740.0
    DW, DD, DT = 1600.0, 700.0, 28.0
    OAK = M('desk_oak_top', (0.42, 0.28, 0.16), 0.45)
    STEEL = M('desk_steel_black_powdercoat', (0.035, 0.035, 0.037), 0.5)
    top = hs.prism_plan('desk_top', [(DCX + x_, DCY + y_) for x_, y_ in hs.rrect(-DW / 2, -DD / 2, DW / 2, DD / 2, 6.0, 4)], DTOP - DT, DTOP)
    GX, GY = DCX + 560.0, DCY + 270.0                         # the grommet, 80 in from the back edge
    top = hs.boolean(top, hs.cyl('grommet_hole', (GX, GY, DTOP - DT - 5.0), (GX, GY, DTOP + 5.0), 60.0, seg=48), 'DIFFERENCE')
    fin(top, 3.0, OAK)
    fin(hs.revolve('desk_grommet_ring', [(29.8, -DT + 1.0), (29.8, 0.0), (39.0, 0.0), (39.5, 1.2), (38.0, 2.0), (27.0, 2.0), (27.0, -DT + 1.0)],
                   at=V3(GX, GY, DTOP), axis=(0, 0, 1), seg=64, closed=True), 0.0, DARK)          # (pressed into the hole, its flange on the oak)
    cap = hs.revolve('desk_grommet_cap', [(0.0, 0.6), (26.5, 0.6), (26.5, 2.6), (25.0, 3.2), (0.0, 3.2)], at=V3(GX, GY, DTOP), axis=(0, 0, 1), seg=64)
    cap = hs.boolean(cap, hs.box('grommet_slot', (GX - 40.0, GY + 9.0, DTOP), (GX + 40.0, GY + 30.0, DTOP + 5.0)), 'DIFFERENCE')      # (its cable slot, to the back)
    fin(cap, 0.4, DARK)
    # THE FRAME: legs inset 40 from the top's edges; rails 40 deep (on edge) x 20 thick right under the top, flush with the
    # legs' outer faces; ONE mass (the legs and rails welded, the welds ground flush), the tube's arrises rounded 2.5
    L, RH, RT = 40.0, 40.0, 20.0
    lx0, lx1 = DCX - DW / 2 + 40.0, DCX + DW / 2 - 40.0 - L
    ly0, ly1 = DCY - DD / 2 + 40.0, DCY + DD / 2 - 40.0 - L
    zt = DTOP - DT
    pieces = []
    for xx in (lx0, lx1):
        for yy in (ly0, ly1):
            pieces.append(bx((xx, yy, 12.0), (xx + L, yy + L, zt)))
    for yy in (ly0, ly1 + L - RT):                           # the long rails, front and back
        pieces.append(bx((lx0 + 1.0, yy, zt - RH), (lx1 + L - 1.0, yy + RT, zt)))
    for xx in (lx0 + L / 2 - RT / 2, lx1 + L / 2 - RT / 2):  # the short rails at the ends
        pieces.append(bx((xx, ly0 + 1.0, zt - RH), (xx + RT, ly1 + L - 1.0, zt)))
    frame = hs.skins('desk_frame_parts', pieces[:1])
    for k_, p_ in enumerate(pieces[1:]):
        frame = hs.boolean(frame, hs.skins(f'desk_frame_piece_{k_}', [p_]), 'UNION')
    fin(frame, 2.5, STEEL)
    # the glides: a threaded stem into the leg's welded-in nut, a black foot under it (the leg stands 12 off the floor)
    gl = []
    for xx in (lx0, lx1):
        for yy in (ly0, ly1):
            c_ = V3(xx + L / 2, yy + L / 2, 0.0)
            gl.append(rev([(0.0, 0.0), (15.0, 0.0), (16.0, 1.5), (16.0, 5.5), (14.0, 7.0), (6.0, 7.5), (0.0, 7.5)], c_, (0, 0, 1), 40))
            gl.append([hs.circle(c_, (0, 0, 1), 4.0, h_, 16) for h_ in (7.0, 14.0)])
    fin(hs.skins('desk_glides', gl), 0.0, DARK)
    ns.update(DCX=DCX, DCY=DCY, DTOP=DTOP, DD=DD, GX=GX, GY=GY)
