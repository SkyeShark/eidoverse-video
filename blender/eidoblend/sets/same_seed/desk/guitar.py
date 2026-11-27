"""eidoblend.sets.same_seed.desk.guitar: the acoustic guitar leaning on the wall (Blender). Millimetres.

A steel-string DREADNOUGHT from the type's published dimensions: body 508 long, lower bout 396, waist 274, upper bout
292, 124 deep at the tail tapering to 102 at the neck; scale 645 mm, the neck joining at the 14th fret, 20 frets placed
by d_n = L (1 - 2^(-n/12)); nut 44 wide. Real construction: the body a HOLLOW box (3 mm top and back, 2.5 sides) whose
soundhole opens on its dark inside; the bridge with its slotted saddle and six pins; the fingerboard glued on the neck
and over the body to the 20th fret; frets as half-round wire seated in it; the neck, heel and headstock one mahogany
mass, the headstock pitched back 14 degrees; six tuners (bushing and post on the face, enclosed gear and button behind);
six strings from the pins over the saddle and nut to the posts. Its own space: the neck along +y from the body's tail
at y 0, the top's face at z 0 facing +z, x across; then leant against the back wall to the right of the desk, under
the poster, its back to the wall, its tail on the floor.

    guitar.build(ns)
"""


def build(ns):
    (M, Matrix, V3, Vector, Y1, bmesh, bpy, bx, fin, hs, math, rev, settle) = (
        ns[k] for k in ('M', 'Matrix', 'V3', 'Vector', 'Y1', 'bmesh', 'bpy', 'bx', 'fin', 'hs', 'math', 'rev', 'settle'))
    SPRUCE = M('guitar_spruce_top', (0.62, 0.48, 0.3), 0.35)
    BACKW = M('guitar_rosewood_back_sides', (0.12, 0.06, 0.035), 0.3)
    NECKW = M('guitar_mahogany_neck', (0.3, 0.15, 0.08), 0.35)
    BOARD_W = M('guitar_ebony_board_bridge', (0.03, 0.025, 0.022), 0.4)
    BONE = M('guitar_bone_nut_saddle', (0.8, 0.77, 0.68), 0.35)
    NICKEL = M('guitar_frets_nickel', (0.7, 0.7, 0.68), 0.25, 1.0)
    CHROMEG = M('guitar_tuners_chrome', (0.75, 0.75, 0.75), 0.15, 1.0)
    STRING = M('guitar_strings_bronze_steel', (0.7, 0.6, 0.45), 0.25, 1.0)
    GUARD = M('guitar_pickguard_tortoise', (0.2, 0.08, 0.03), 0.25)

    GL = 508.0
    OUT_Y = [0, 4, 12, 30, 55, 90, 130, 170, 205, 240, 270, 300, 330, 365, 400, 430, 455, 475, 490, 500, 506, 508]
    OUT_W = [0, 50, 90, 128, 158, 182, 195, 198, 190, 172, 152, 140, 137, 141, 146, 145, 138, 124, 104, 80, 50, 0]


    def catmull(pts, n):
        """a smooth curve through pts (Catmull-Rom), resampled to n points evenly by arc length"""
        P = [Vector(p) for p in pts]
        dense = []
        for i in range(len(P) - 1):
            p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
            for k in range(20):
                t = k / 20.0
                dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
        dense.append(P[-1])
        L_ = [0.0]
        for a_, b_ in zip(dense, dense[1:]):
            L_.append(L_[-1] + (b_ - a_).length)
        out, j = [], 0
        for k in range(n):
            s = L_[-1] * k / (n - 1)
            while j < len(L_) - 2 and L_[j + 1] < s:
                j += 1
            f = (s - L_[j]) / max(L_[j + 1] - L_[j], 1e-9)
            out.append(dense[j].lerp(dense[j + 1], f))
        return out


    half = catmull([(w_, y_) for w_, y_ in zip(OUT_W, OUT_Y)], 70)                       # tail -> neck, the right half
    OUTLINE = [(p.x, p.y) for p in half] + [(-p.x, p.y) for p in reversed(half[1:-1])]     # a closed loop, counter-clockwise


    def inset(loop, d):
        """a closed 2D loop moved inward by d (its own normals, averaged at each point)"""
        out = []
        n = len(loop)
        for i in range(n):
            a_, b_ = Vector(loop[i - 1]), Vector(loop[(i + 1) % n])
            t = (b_ - a_).normalized()
            out.append((loop[i][0] - t.y * d, loop[i][1] + t.x * d))
        return out


    def depth(y):
        return 124.0 - 22.0 * (y / GL)


    IN = inset(OUTLINE, 2.5)
    body = hs.rings('guitar_body', [[V3(x_, y_, -depth(y_)) for x_, y_ in OUTLINE], [V3(x_, y_, 0.0) for x_, y_ in OUTLINE]])
    cav = hs.rings('guitar_cavity', [[V3(x_, y_, -depth(y_) + 3.0) for x_, y_ in IN], [V3(x_, y_, -3.0) for x_, y_ in IN]])
    body = hs.boolean(body, cav, 'DIFFERENCE')
    SH_Y, SH_R = 360.0, 50.0                                 # (its edge 8 below the fingerboard's end)
    body = hs.boolean(body, hs.cyl('soundhole', (0.0, SH_Y, 5.0), (0.0, SH_Y, -8.0), SH_R * 2.0, seg=72), 'DIFFERENCE')
    g_body = fin(body, 2.0, BACKW)
    g_body.data.materials.append(SPRUCE)                     # (slot 1: the top's face, by its faces)
    for p_ in g_body.data.polygons:
        if p_.normal.z > 0.9 and p_.center.z > -0.0015:
            p_.material_index = 1
    g_parts = [g_body]
    # the bracing seen through the soundhole: two X braces under the top and the label's patch on the back
    xb = []
    for s_ in (-1.0, 1.0):
        a_ = math.radians(s_ * 49.0)
        d_ = V3(math.sin(a_), math.cos(a_), 0.0)
        c_ = V3(0.0, 300.0, -3.0)
        p0_, p1_ = c_ - d_ * 170.0, c_ + d_ * 150.0
        n_ = V3(-d_.y, d_.x, 0.0)
        xb.append([[p0_ - n_ * 3.5, p1_ - n_ * 3.5, p1_ + n_ * 3.5, p0_ + n_ * 3.5], [p0_ - n_ * 3.0 + V3(0, 0, -13.0), p1_ - n_ * 3.0 + V3(0, 0, -13.0), p1_ + n_ * 3.0 + V3(0, 0, -13.0), p0_ + n_ * 3.0 + V3(0, 0, -13.0)]])
    g_parts.append(fin(hs.skins('guitar_x_braces', xb), 0.0, M('guitar_spruce_braces', (0.6, 0.5, 0.35), 0.6)))
    # THE BRIDGE: its plan (152 x 30) cut by its section (9 high in the middle, its wings down to 4)
    BR_Y0, BR_Y1 = 190.0, 220.0
    br = hs.prism_plan('guitar_bridge', hs.rrect(-76.0, BR_Y0, 76.0, BR_Y1, 4.0, 3), 0.0, 12.0)
    br = hs.boolean(br, hs.prism_side('guitar_bridge_section', [(-80.0, -1.0), (80.0, -1.0), (80.0, 3.5), (76.0, 4.0), (55.0, 4.5), (40.0, 9.0), (-40.0, 9.0), (-55.0, 4.5), (-76.0, 4.0), (-80.0, 3.5)],
                                      BR_Y0 - 5.0, BR_Y1 + 5.0), 'INTERSECT')
    SAD_Y = 214.0
    br = hs.boolean(br, hs.box('guitar_saddle_slot', (-37.5, SAD_Y - 1.6, 5.0), (37.5, SAD_Y + 1.6, 12.0)), 'DIFFERENCE')
    PIN_Y = 200.0
    br = hs.boolean(br, hs.skins('guitar_pin_holes', [[hs.circle(V3((i - 2.5) * 10.4, PIN_Y, h_), (0, 0, 1), 2.6, 0.0, 16) for h_ in (-2.0, 12.0)] for i in range(6)]), 'DIFFERENCE')
    g_parts.append(fin(br, 1.0, BOARD_W))
    saddle = [[V3(px, SAD_Y + py, pz) for px, py, pz in ((x_, -1.5, 5.2), (x_, 1.5, 5.2), (x_, 1.5, 11.4), (x_, 1.0, 12.4), (x_, -0.4, 12.6), (x_, -1.5, 11.6))] for x_ in (-37.2, 37.2)]
    g_parts.append(fin(hs.rings('guitar_saddle', saddle), 0.0, BONE))
    pins = [rev([(2.5, -1.0), (2.5, 9.0), (3.1, 9.0), (3.2, 10.6), (2.6, 11.8), (1.2, 12.4), (0.0, 12.5)], V3((i - 2.5) * 10.4, PIN_Y, 0.0), (0, 0, 1), 16) for i in range(6)]
    g_parts.append(fin(hs.skins('guitar_bridge_pins', pins), 0.0, M('guitar_pins_ebony', (0.03, 0.03, 0.03), 0.3)))
    # the pickguard: a thin teardrop on the treble side of the soundhole, 0.6 thick, its edge round the rosette
    pg = [(-72.0 + 40.0 * math.cos(2 * math.pi * k_ / 48) * (1.0 + 0.2 * math.sin(2 * math.pi * k_ / 48)), 288.0 + 62.0 * math.sin(2 * math.pi * k_ / 48)) for k_ in range(48)]
    g_parts.append(fin(hs.prism_plan('guitar_pickguard', pg, 0.0, 0.6), 0.0, GUARD))       # (clear of the soundhole's rosette)
    # THE FINGERBOARD: from the nut (44 wide) to over the body at the 20th fret (56), 6 thick, its arrises eased
    SCALE = 645.0
    D14 = SCALE * (1.0 - 2.0 ** (-14.0 / 12.0))
    NUT_Y = GL + D14                                         # the nut's face toward the frets
    FB_END = NUT_Y - SCALE * (1.0 - 2.0 ** (-20.0 / 12.0)) - 6.0


    def fb_half(y):
        return 22.0 + (NUT_Y - y) / (NUT_Y - FB_END) * 6.0


    g_parts.append(fin(hs.prism_plan('guitar_fingerboard', [(fb_half(FB_END), FB_END), (fb_half(NUT_Y), NUT_Y), (-fb_half(NUT_Y), NUT_Y), (-fb_half(FB_END), FB_END)], 0.0, 6.0), 0.8, BOARD_W))
    frets = []
    for n_ in range(1, 21):
        y_ = NUT_Y - SCALE * (1.0 - 2.0 ** (-n_ / 12.0))
        hw_ = fb_half(y_) - 0.6
        frets.append([hs.circle(V3(x_, y_, 6.0), (1, 0, 0), r_, 0.0, 12) for x_, r_ in ((-hw_, 0.6), (-hw_ + 0.8, 1.2), (hw_ - 0.8, 1.2), (hw_, 0.6))])
    g_parts.append(fin(hs.skins('guitar_frets', frets), 0.0, NICKEL))
    NUT_T = 6.0
    g_parts.append(fin(hs.box('guitar_nut', (-22.0, NUT_Y, 0.0), (22.0, NUT_Y + NUT_T, 8.6)), 0.8, BONE))
    # THE NECK: a C-section shaft (56 wide and 23 deep at the body, 44 and 21 at the nut), the heel down the body's end
    # to its back, the headstock pitched back 14 degrees from the nut: ONE mass
    ring_n = []
    for k_ in range(15):
        y_ = GL - 4.0 + (NUT_Y + NUT_T + 6.0 - GL + 4.0) * k_ / 14
        t_ = min(max((y_ - GL) / (NUT_Y - GL), 0.0), 1.0)
        w2, dd = 28.0 - 6.0 * t_, 23.0 - 2.0 * t_
        ring_n.append([V3(w2 * math.cos(math.pi * q / 16), y_, -dd * math.sin(math.pi * q / 16)) for q in range(17)])
    neck = hs.rings('guitar_neck', ring_n)
    heel = hs.prism_side('guitar_heel', [(GL - 6.0, 0.0), (GL + 70.0, 0.0), (GL + 70.0, -24.0), (GL + 48.0, -30.0), (GL + 30.0, -55.0), (GL + 22.0, -85.0), (GL + 20.0, -depth(GL) + 1.0),
                                         (GL - 6.0, -depth(GL) + 1.0)], -27.0, 27.0)
    # (prism_side takes (x, z) outlines extruded along y: the heel's side outline is in (y, z), so it is built across
    #  x and turned a quarter about z)
    settle(heel)
    heel.data.transform(Matrix.Translation(Vector((0.0, 0.0, 0.0))) @ Matrix(((0, -1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
    bmh = bmesh.new()
    bmh.from_mesh(heel.data)
    bmesh.ops.recalc_face_normals(bmh, faces=bmh.faces)
    bmh.to_mesh(heel.data)
    bmh.free()
    neck = hs.boolean(neck, heel, 'UNION')
    HS_P = V3(0.0, NUT_Y + NUT_T, 0.0)                       # the headstock's pivot: behind the nut, on the face's line
    hs_plan = [(-24.0, -2.0), (-37.0, 22.0), (-40.0, 60.0), (-42.0, 150.0), (-40.0, 180.0), (-30.0, 186.0), (30.0, 186.0), (40.0, 180.0), (42.0, 150.0), (40.0, 60.0), (37.0, 22.0), (24.0, -2.0)]
    hstock = hs.prism_plan('guitar_headstock', [(x_, NUT_Y + NUT_T + y_) for x_, y_ in hs_plan], -15.0, 0.0)
    settle(hstock)
    HS_R = Matrix.Translation(HS_P * hs.MM) @ Matrix.Rotation(math.radians(-14.0), 4, 'X') @ Matrix.Translation(-HS_P * hs.MM)
    hstock.data.transform(HS_R)
    neck = hs.boolean(neck, hstock, 'UNION')
    g_parts.append(fin(neck, 1.5, NECKW))
    # the tuners, in the headstock's own frame (posts 26 off the middle at 40, 78, 116 along it)
    tn = []
    TUN = [(s_ * 26.0, NUT_Y + NUT_T + yy) for s_ in (-1.0, 1.0) for yy in (40.0, 78.0, 116.0)]
    for px, py in TUN:
        tn.append(rev([(0.0, 0.0), (5.6, 0.0), (5.6, 2.2), (4.6, 3.0), (0.0, 3.0)], V3(px, py, 0.0), (0, 0, 1), 6))                    # the bushing (a hex nut)
        tn.append(rev([(0.0, 0.0), (3.0, 0.0), (3.0, 13.0), (2.6, 14.0), (0.0, 14.2)], V3(px, py, 2.0), (0, 0, 1), 16))                # the post
        s_ = 1.0 if px > 0 else -1.0
        tn.append(bx((px - 8.0, py - 10.0, -15.0 - 12.0), (px + 9.0 * s_ * 0 + 8.0, py + 10.0, -15.0)))                                 # the gear's housing
        tn.append([hs.circle(V3(px + s_ * 8.0, py, -21.0), (s_, 0, 0), 2.0, h_, 12) for h_ in (0.0, 14.0)])                            # the shaft
        tn.append([[V3(px + s_ * (20.0 + bx_), py + by_, -21.0 + bz_) for bx_, by_ in hs.rrect(0.0, -7.0, 18.0, 7.0, 6.0, 4)] for bz_ in (-2.6, 2.6)])  # the button
    tuners = hs.skins('guitar_tuners', tn)
    settle(tuners)
    tuners.data.transform(HS_R)
    g_parts.append(fin(tuners, 0.0, CHROMEG))
    # THE STRINGS: from each pin over the saddle and the nut to its post (gauges .012 - .053 in)
    GAUGE = [1.35, 1.07, 0.81, 0.61, 0.41, 0.31]
    strs = []
    for i in range(6):
        xs = (i - 2.5) * 10.4
        xn = (i - 2.5) * 7.4
        px, py = TUN[[0, 1, 2, 5, 4, 3][i]]                  # (the outer strings to the posts nearest the nut: none cross)
        post = HS_R @ (V3(px, py, 9.0) * hs.MM) / hs.MM
        path = [V3(xs, PIN_Y, 5.0), V3(xs, PIN_Y + 2.0, 9.2), V3(xs * 0.98, SAD_Y, 12.6 + GAUGE[i] / 2), V3(xn, NUT_Y + 0.5, 8.6 + GAUGE[i] / 2), post]
        r_ = GAUGE[i] / 2.0
        dirs = [(path[1] - path[0])] + [(path[min(j + 1, len(path) - 1)] - path[j - 1]) for j in range(1, len(path) - 1)] + [(path[-1] - path[-2])]
        strs.append([hs.circle(p_, d_.normalized(), r_, 0.0, 6, (1, 0, 0)) for p_, d_ in zip(path, dirs)])      # (rings started on x: no twist)
    g_parts.append(fin(hs.skins('guitar_strings', strs), 0.0, STRING))
    g_parts.append(fin(hs.revolve('guitar_endpin', [(0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (4.0, 5.0), (4.0, 10.0), (5.5, 12.0), (5.0, 14.0), (0.0, 14.5)], at=V3(0.0, 0.0, -depth(0.0) / 2), axis=(0, -1, 0), seg=20), 0.0,
                   M('guitar_pins_ebony')))

    # ============================================================================================ LEANT ON THE WALL
    # a quarter turn up (the neck to +z, the top to the room), then its top end leant 13 degrees to the wall and turned 9
    # about the upright; seated: its lowest point on the floor, its furthest-back point 2 mm off the wall
    R_ = Matrix.Rotation(math.radians(9.0), 4, 'Z') @ Matrix.Rotation(math.radians(90.0 - 13.0), 4, 'X')
    for o_ in g_parts:
        settle(o_)
        o_.data.transform(R_)
    bpy.context.view_layer.update()
    pts_ = [v.co.copy() for o_ in g_parts for v in o_.data.vertices]
    dz_ = -min(p.z for p in pts_)
    dy_ = (Y1 - 2.0) * hs.MM - max(p.y for p in pts_)
    for o_ in g_parts:
        o_.data.transform(Matrix.Translation(Vector((2.40, dy_, dz_))))
    print('GUITAR leant: its top at z', round(max(p.z for p in pts_) + dz_, 3), '; its front-most point at y', round(min(p.y for p in pts_) + dy_, 3), flush=True)
