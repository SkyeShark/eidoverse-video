"""eidoblend.sets.same_seed.kitchen.table: the table, the three chairs and the child's cushion (Blender). Millimetres.

THE TABLE: a farmhouse table: a top of boards between two breadboard ends, pegged; four TURNED legs, each one stick: a
square block where the aprons are tenoned in, the lathe's shoulder cut into the block's corners, a long vase, a ring and
a foot; aprons set back from the legs' faces. Its top at z 740, 1500 x 900 over (900, -450) (TTOP: where things are set
down). THE CHAIRS: rod-back Windsors: a saddled plank seat; four bamboo-turned legs socketed up into it, splayed, tied by
four stretchers; two back posts and seven spindles socketed down into it, a bent tablet between the posts' tops (seat
445 high, 430 wide, 870 over all); one pulled out for the child, with a cushion on it.

    table.build(ns)          # adds TTOP for the things on the table
"""


def build(ns):
    (V3, Vector, bx, fin, hs, math, place, rev, trim) = (ns[k] for k in ('V3', 'Vector', 'bx', 'fin', 'hs', 'math', 'place', 'rev', 'trim'))
    TCX, TCY, TTOP = 900.0, -450.0, 740.0
    TL, TW_, TT = 1500.0, 900.0, 30.0
    BB = 72.0                                                     # the breadboard ends' width
    z0, z1 = TTOP - TT, TTOP
    # a glued-up top: five boards of unequal width, each arris eased 1.2 mm, butted 0.2 apart; planed after the glue-up
    # but not perfectly: hair-fine lips of 0.05-0.15 mm between them, which raking noon light finds. The bake carries them
    # onto the table's low (a joint 2.4 wide is 3+ texels at the table atlas's 2 px/mm). The top's face stays at z 740.
    BOARDS = (168.0, 192.0, 176.0, 200.0, 164.0)                   # across the top, y from the front (-900) back to 0
    LIPS = (0.0, -0.12, -0.03, -0.1, -0.05)                       # (none above 740: what lies on it stays where it lay)
    yb, sk = TCY - TW_ / 2, []
    for w_, lip in zip(BOARDS, LIPS):
        sk.append(bx((TCX - TL / 2 + BB + 0.4, yb + 0.1, z0), (TCX + TL / 2 - BB - 0.4, yb + w_ - 0.1, z1 + lip)))
        yb += w_
    fin(hs.skins('table_top_boards', sk), 1.2)
    sk = []
    for s in (-1.0, 1.0):
        xa, xb = TCX + s * (TL / 2 - BB), TCX + s * TL / 2
        fin(hs.box(f'table_top_breadboard_{int(s > 0)}', (min(xa, xb), TCY - TW_ / 2 - 1.0, z0), (max(xa, xb), TCY + TW_ / 2 + 1.0, z1)), 3.0)
        for dy in (-330.0, 0.0, 330.0):                             # the pegs through its tenons, a hair proud
            sk.append(rev([(0.0, -4.0), (4.6, -4.0), (4.6, 0.2), (3.8, 0.7), (0.0, 0.8)], V3(TCX + s * (TL / 2 - BB + 24.0), TCY + dy, z1), (0, 0, 1), 16))
    fin(hs.skins('table_pegs', sk), 0.0)
    LX, LY, BLK = 640.0, 370.0, 70.0                              # the legs' centres from the table's; their block
    LEG = [(0.0, 0.0), (17.0, 0.0), (20.0, 4.0), (22.0, 30.0), (21.0, 44.0), (17.5, 52.0), (16.0, 58.0), (18.5, 64.0), (24.0, 70.0), (26.0, 78.0), (24.5, 86.0), (20.5, 92.0), (19.5, 98.0),
           (20.5, 120.0), (25.0, 240.0), (29.5, 380.0), (32.5, 450.0), (33.0, 480.0), (31.5, 502.0), (27.0, 516.0), (24.0, 524.0), (26.5, 531.0), (31.0, 535.5), (33.5, 541.0), (32.0, 547.0),
           (28.0, 551.5), (27.0, 556.0), (29.0, 560.5), (36.0, 566.0), (60.0, 574.0), (60.0, z0 + 2.0), (0.0, z0 + 2.0)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx_, cy_ = TCX + sx * LX, TCY + sy * LY
            leg = hs.box(f'table_leg_{int(sx > 0)}{int(sy > 0)}', (cx_ - BLK / 2, cy_ - BLK / 2, 0.0), (cx_ + BLK / 2, cy_ + BLK / 2, z0))
            leg = hs.boolean(leg, hs.revolve('table_leg_turning', LEG, at=V3(cx_, cy_, -1.0), seg=48), 'INTERSECT')
            fin(leg, 0.8)
    AZ0, AT, SET = z0 - 100.0, 22.0, 12.0                          # the aprons: 100 deep, 22 thick, 12 back from the legs' faces
    for sy in (-1, 1):
        yo = TCY + sy * (LY + BLK / 2 - SET)                        # its outer face
        fin(hs.box(f'table_apron_long_{int(sy > 0)}', (TCX - LX + BLK / 2 - 10.0, min(yo, yo - sy * AT), AZ0), (TCX + LX - BLK / 2 + 10.0, max(yo, yo - sy * AT), z0)), 2.0)
    for sx in (-1, 1):
        xo = TCX + sx * (LX + BLK / 2 - SET)
        fin(hs.box(f'table_apron_short_{int(sx > 0)}', (min(xo, xo - sx * AT), TCY - LY + BLK / 2 - 10.0, AZ0), (max(xo, xo - sx * AT), TCY + LY - BLK / 2 + 10.0, z0)), 2.0)

    # ============================================================================================ THE CHAIRS
    # built about its own middle on the floor, the sitter facing +y; then turned and stood in its place
    SEAT_Z, SEAT_T, TILT = 445.0, 40.0, math.radians(2.2)          # the seat's top at its front; its thickness; it leans back


    def outline(s, n=48):
        """the seat's plan at a scale s: broad and round-cornered at the front, narrower behind"""
        out = []
        for k in range(n):
            th = 2.0 * math.pi * k / n
            c_, s_ = math.cos(th), math.sin(th)
            x = 205.0 * math.copysign(abs(c_) ** (2.0 / 3.2), c_)
            y = 200.0 * math.copysign(abs(s_) ** (2.0 / 3.2), s_)
            out.append((s * x * (1.0 + 0.07 * y / 200.0), s * y, th))
        return out


    def tilt(p):
        """a point of the level seat, leaned back about the seat's front edge"""
        y, z = p.y - 200.0, p.z - SEAT_Z
        return V3(p.x, 200.0 + y * math.cos(TILT) + z * math.sin(TILT), SEAT_Z - y * math.sin(TILT) + z * math.cos(TILT))


    def seat_top(x, y):
        """the height of the seat's upper face over a point of its plan (level seat): for what stands in it"""
        r = math.hypot(x / 205.0, y / 200.0)
        return SEAT_Z - 12.0 * max(0.0, 1.0 - r * r) * (1.0 - 0.75 * max(0.0, -y / 200.0) ** 1.5)


    BAMBOO = lambda r, h: [(r * 0.955, h - 9.0), (r * 1.01, h - 2.6), (r * 0.9, h), (r * 1.01, h + 2.6), (r * 0.955, h + 9.0)]      # noqa: E731  (a node: a cut between two swells)


    def turned(p0, p1, r0, r1, nodes, swell=1.12, end0=None, end1=None, seg=20):
        """a bamboo-turned stick from p0 to p1 (mm), r0 at p0 to r1 at p1, fattest between; nodes: where its rings are, as
        fractions of its length. end0 / end1: a round end's rise there (None: cut square: the end is inside its socket)"""
        p0, p1 = Vector(p0), Vector(p1)
        L = (p1 - p0).length
        prof = [(0.0, 0.0)] if end0 is None else [(0.0, -end0), (r0 * 0.55, -end0 * 0.8), (r0 * 0.9, -end0 * 0.35)]
        prof.append((r0, 0.0))
        for i in range(1, 12):
            f = i / 12.0
            r = (r0 + (r1 - r0) * f) * (1.0 + (swell - 1.0) * math.sin(math.pi * f))
            if any(abs(f - nf) < 0.035 for nf in nodes):
                continue
            prof.append((r, L * f))
        for nf in nodes:
            r = (r0 + (r1 - r0) * nf) * (1.0 + (swell - 1.0) * math.sin(math.pi * nf))
            prof += BAMBOO(r, L * nf)
        prof = [prof[0]] + sorted(prof[1:], key=lambda q: q[1]) if end0 is None else sorted(prof, key=lambda q: q[1])
        prof.append((r1, L))
        prof += [(0.0, L)] if end1 is None else [(r1 * 0.9, L + end1 * 0.35), (r1 * 0.55, L + end1 * 0.8), (0.0, L + end1)]
        return rev(prof, p0, (p1 - p0).normalized(), seg)


    def chair(name, at, yaw):
        made = []
        # the seat: its outline carried up through its section (a deep under-bevel, the arris, the rolled top edge) and in
        # over the saddle; the saddle is shallow toward the back, where the sticks enter, and deepest under the sitter
        rl = [[tilt(V3(x, y, SEAT_Z - SEAT_T + dz)) for x, y, _ in outline(s)] for s, dz in ((0.80, 0.0), (0.93, 7.0), (0.985, 17.0), (1.0, 25.0), (0.995, 32.0), (0.975, 37.5), (0.94, 40.0))]
        for s, scoop in ((0.86, 1.0), (0.74, 4.5), (0.58, 8.5), (0.40, 11.0), (0.20, 11.8)):
            rl.append([tilt(V3(x, y, SEAT_Z - scoop * (1.0 - 0.75 * max(0.0, -math.sin(th)) ** 1.5 - 0.3 * max(0.0, math.sin(th)) ** 4))) for x, y, th in outline(s)])
        made.append(fin(hs.rings(name + '_seat', rl), 0.0))
        # the legs: from a foot outside the seat's plan up into the seat (the top 26 of each is its tenon, in the plank)
        joints = {}
        legs = []
        for sx in (-1, 1):
            for tag, (jx, jy), (fx, fy) in (('front', (150.0, 125.0), (212.0, 212.0)), ('rear', (135.0, -138.0), (186.0, -288.0))):
                top = tilt(V3(sx * jx, jy, SEAT_Z - 14.0))
                foot = V3(sx * fx, fy, 0.0)
                ax = (top - foot).normalized()
                legs.append(turned(foot - ax * 14.0, top, 11.0, 12.5, (0.2, 0.52, 0.8), swell=1.2))
                joints[(sx, tag)] = (foot, ax)
        legs_o = trim(hs.skins(name + '_legs', legs))
        made.append(fin(legs_o, 0.0))

        def on_leg(sx, tag, z):
            foot, ax = joints[(sx, tag)]
            return foot + ax * (z / ax.z)
        st = [turned(on_leg(-1, 'front', 262.0), on_leg(1, 'front', 262.0), 8.0, 8.0, (0.5,), swell=1.4), turned(on_leg(-1, 'rear', 250.0), on_leg(1, 'rear', 250.0), 8.0, 8.0, (0.5,), swell=1.4)]
        for sx in (-1, 1):
            st.append(turned(on_leg(sx, 'front', 150.0), on_leg(sx, 'rear', 165.0), 8.0, 8.0, (0.5,), swell=1.4))
        made.append(fin(hs.skins(name + '_stretchers', st), 0.0))
        # the back: two posts raked back and flaring a little, a bent tablet housed between their tops, seven spindles
        rake = Vector((0.0, -math.sin(math.radians(11.0)), math.cos(math.radians(11.0))))

        def post_at(sx, z):
            """a post's axis at the height z"""
            base = tilt(V3(sx * 146.0, -150.0, seat_top(sx * 146.0, -150.0)))      # (15 mm of plank outside the post at the seat's corner)
            d = Vector((sx * 0.066, rake.y, rake.z)).normalized()
            return base + d * ((z - base.z) / d.z)
        posts = []
        for sx in (-1, 1):
            b0 = post_at(sx, SEAT_Z - 34.0)
            posts.append(turned(b0, post_at(sx, 872.0), 13.0, 9.6, (0.3, 0.52, 0.74), swell=1.05, end1=7.0))
        made.append(fin(hs.skins(name + '_posts', posts), 0.0))
        CZ0, CZ1, BOW = 786.0, 858.0, 30.0                          # the tablet's lower and upper edge; how far its middle bows back
        rl = []
        lo, hi = post_at(1, CZ0), post_at(1, CZ1)
        for i in range(25):
            u = -1.0 + 2.0 * i / 24.0
            ring = []
            for t_, h_ in ((-7.0, 0.07), (-5.0, 0.0), (5.0, 0.0), (7.0, 0.07), (7.0, 0.93), (5.0, 1.0), (-5.0, 1.0), (-7.0, 0.93)):      # 14 thick, its edges eased
                pz = lo.lerp(hi, h_ * (1.0 + 0.06 * u * u))        # (its ends rise a little to the posts)
                ring.append(V3(u * pz.x, pz.y - BOW * (1.0 - u * u) + t_, pz.z))
            rl.append(ring)
        made.append(fin(hs.rings(name + '_crest', rl), 0.0))
        sp = []
        for i in range(7):                                          # the nine sticks of the back stand evenly: 36.5 apart at the seat
            x = -109.5 + 36.5 * i
            y = -172.0 + 0.0010 * x * x
            b0 = tilt(V3(x, y, seat_top(x, y) - 18.0))
            u = x * 1.1 / post_at(1, CZ0).x
            lo = post_at(1, CZ0 + 9.0)
            t1 = V3(u * lo.x, lo.y - BOW * (1.0 - u * u), lo.z)
            sp.append(turned(b0, t1, 5.4, 4.2, (0.42,), swell=1.3, seg=12))
        made.append(fin(hs.skins(name + '_spindles', sp), 0.0))
        for o in made:
            place(o, at, yaw)
        return made


    chair('chair_child', (1980.0, -400.0, 0.0), math.radians(110.0))                      # pulled out from the table's end and turned
    chair('chair_front', (300.0, -1150.0, 0.0), math.radians(-4.0))
    chair('chair_end', (-110.0, -440.0, 0.0), math.radians(-87.0))

    # the child's cushion: a tie-on pad, piped round its seam, sat into the saddle of the pulled-out chair
    CUSH = [(0.90, 0.0), (0.975, 4.0), (1.0, 11.0), (1.0, 20.0), (0.965, 28.0), (0.88, 33.5), (0.72, 36.5), (0.45, 38.0), (0.15, 38.6)]


    def cush_xy(s, k, n=48):
        th = 2.0 * math.pi * k / n
        c_, s_ = math.cos(th), math.sin(th)
        return s * 172.0 * math.copysign(abs(c_) ** (2.0 / 4.2), c_), s * 168.0 * math.copysign(abs(s_) ** (2.0 / 4.2), s_) + 14.0


    pad = hs.rings('chair_child_cushion', [[tilt(V3(*cush_xy(s, k), SEAT_Z - 9.0 + dz)) for k in range(48)] for s, dz in CUSH])
    place(fin(pad, 0.0), (1980.0, -400.0, 0.0), math.radians(110.0))
    seam = [tilt(V3(*cush_xy(1.0, k), SEAT_Z - 9.0 + 15.5)) for k in range(48)]
    rl = []
    for k, p in enumerate(seam):
        t = (seam[(k + 1) % 48] - seam[k - 1]).normalized()
        rl.append(hs.circle(p, t, 2.4, 0.0, 8, (0, 0, 1)))
    place(fin(hs.rings('chair_child_cushion_piping', rl + [rl[0]], caps=False), 0.0), (1980.0, -400.0, 0.0), math.radians(110.0))
    ns.update(TTOP=TTOP)
