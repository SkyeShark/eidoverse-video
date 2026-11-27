"""eidoblend.sets.same_seed.desk.books: the books on the shelves (Blender). Millimetres.

Poly Haven has one encyclopedia set as a glTF: it is one run on the wide shelf; the rest are built from how books are
made: a HARDCOVER is a case (two 2.5 mm boards and a rounded spine) holding a separate block inset 3 mm at head, tail
and fore-edge; a PAPERBACK one block in its card cover, its spine corners rounded; RING BINDERS (the songs, a
songwriter's) a stiff case round a mechanism. Shelves are filled from a few families with ordered, irregular rhythm:
upright runs of near heights, a leaning book against a run's end, a flat stack, gaps, the photo frame; every book sits
on its board (by the boards' ray heights) and inset 20 behind its front edge. Each shelf's books are two objects
(covers / page blocks), each cover carrying its own colour in the attribute 'book_tint' (a restrained palette per
family) for the look.

    books.build(ns)          # after models (cc0, B1, B2)
"""


def build(ns):
    (B1, B2, M, V3, cc0, fin, hs, math) = (ns[k] for k in ('B1', 'B2', 'M', 'V3', 'cc0', 'fin', 'hs', 'math'))
    import colorsys
    import random

    RB = random.Random(25)
    COVERS = M('book_cover_cloth_card', (0.3, 0.25, 0.2), 0.7)
    PAGES = M('book_pages_paper', (0.8, 0.77, 0.68), 0.9)


    def tint(family):
        if family == 'paper':
            h_, s_, v_ = RB.random(), RB.uniform(0.35, 0.7), RB.uniform(0.35, 0.8)
        elif family == 'cloth':
            h_, s_, v_ = RB.choice((0.6, 0.98, 0.33, 0.08, 0.12, 0.0, 0.55)), RB.uniform(0.25, 0.6), RB.uniform(0.12, 0.42)
        elif family == 'art':
            h_, s_, v_ = RB.uniform(0.05, 0.12), RB.uniform(0.0, 0.15), RB.choice((0.85, 0.08, 0.75, 0.2))
        else:                                                 # binders
            h_, s_, v_ = RB.choice((0.62, 0.0, 0.0, 0.3)), RB.uniform(0.0, 0.6), RB.uniform(0.05, 0.3)
        return colorsys.hsv_to_rgb(h_, s_, v_)


    class Shelf:
        """one board's row: O its front-left corner on the board (mm), A along the row, B into the shelf, the books' spines
        toward -B"""

        def __init__(self, O, A, B, length):
            self.O, self.A, self.B, self.L = V3(*O), V3(*A).normalized(), V3(*B).normalized(), length

        def P(self, u, v, w):
            return self.O + self.A * u + self.B * (v + 20.0) + V3(0.0, 0.0, w)


    BOOKS = {}                                                # object name -> (cover skins, page skins, [(bbox lo, hi, tint)])


    def book_rings(t, d, h, hard):
        """a book in its own frame (u across its thickness, centred; v from the spine's crown into the shelf; w up): the
        cover's rings and the block's (None for a paperback, which is one block)"""
        sb = min(t * 0.12, 4.0) if hard else 0.0
        if hard:
            outer = [(-t / 2, d)] + [((t / 2) * math.sin(math.radians(p_)), sb * (1.0 - math.cos(math.radians(p_)))) for p_ in range(-90, 91, 15)] + [(t / 2, d)]
            ti = t / 2 - 2.5
            inner = [(ti, d)] + [(ti * math.sin(math.radians(p_)), 2.5 + sb * (1.0 - math.cos(math.radians(p_)))) for p_ in range(90, -91, -15)] + [(-ti, d)]
            cover = outer + inner
            block = [(-ti + 0.05, 2.5 + sb + 0.3), (ti - 0.05, 2.5 + sb + 0.3), (ti - 0.05, d - 3.0), (-ti + 0.05, d - 3.0)]
            return cover, block
        r = min(2.0, t / 4.0)
        cover = [(-t / 2 + r - r * math.cos(math.radians(a_)), r - r * math.sin(math.radians(a_))) for a_ in range(0, 91, 30)] + \
                [(t / 2 - r + r * math.cos(math.radians(a_)), r - r * math.sin(math.radians(a_))) for a_ in range(90, -1, -30)] + [(t / 2, d), (-t / 2, d)]
        cover = [(u, v) for u, v in cover]
        return cover, None


    def put_book(shelf, key, u0, t, d, h, family, hard, lean=0.0, lying_z=None):
        """a book at u0 along the row (its left face), standing (or leant `lean` degrees onto its left neighbour about its
        bottom-left edge; or lying flat, its underside at lying_z)"""
        cover, block = book_rings(t, d, h, hard)
        col = tint(family)

        def to_world(u, v, w):
            if lying_z is not None:                          # lying: its height along the row, its thickness up
                return shelf.P(u0 + w, v, lying_z + u + t / 2)
            uu = u + t / 2
            if lean:
                c_, s_ = math.cos(math.radians(lean)), math.sin(math.radians(lean))
                uu, w = uu * c_ - w * s_, uu * s_ + w * c_
            return shelf.P(u0 + uu, v, w)
        sk = BOOKS.setdefault(key, ([], [], []))
        rings = [[to_world(u, v, w) for u, v in cover] for w in (0.0, h)]
        sk[0].append(rings)
        pts = [p for r_ in rings for p in r_]
        if block:
            sk[1].append([[to_world(u, v, w) for u, v in block] for w in (3.0, h - 3.0)])
        lo = V3(min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)) * hs.MM
        hi = V3(max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)) * hs.MM
        sk[2].append((lo, hi, col))


    def fill(shelf, key, plan):
        """plan: a list of ('run', n, family, (h0, h1), (t0, t1), (d0, d1)), ('gap', mm), ('lean', family, h, t, d),
        ('stack', n, family), ('skip', mm)"""
        u = 4.0
        for item in plan:
            kind = item[0]
            if kind == 'run':
                _, n, fam, hr, tr, dr = item
                hard = fam in ('cloth', 'art', 'binder')
                h_base = RB.uniform(*hr)
                for _k in range(n):
                    t = RB.uniform(*tr)
                    h = min(max(h_base + RB.uniform(-14.0, 14.0), hr[0]), hr[1])
                    if u + t > shelf.L - 4.0:
                        return
                    put_book(shelf, key, u, t, RB.uniform(*dr), h, fam, hard)
                    u += t + RB.uniform(0.3, 1.6)
            elif kind == 'lean':
                _, fam, h, t, d = item
                gap = min(h * math.sin(math.radians(14.0)), shelf.L - u - t - 6.0)
                if gap < 15.0:
                    continue
                ang = math.degrees(math.asin(gap / h))
                put_book(shelf, key, u + gap, t, d, h, fam, fam in ('cloth', 'art'), lean=ang)
                u += gap + t * math.cos(math.radians(ang)) + 8.0
            elif kind == 'stack':
                _, n, fam = item
                h0 = RB.uniform(230.0, 300.0)
                if u + h0 > shelf.L - 4.0:
                    continue
                z = 0.0
                for k_ in range(n):
                    t = RB.uniform(14.0, 32.0)
                    h = h0 - k_ * RB.uniform(6.0, 22.0)
                    put_book(shelf, key, u + (h0 - h) / 2 + RB.uniform(-4.0, 4.0), t, RB.uniform(150.0, 200.0) - k_ * 8.0, h, fam, fam != 'paper', lying_z=z)
                    z += t + 0.2
                u += h0 + 10.0
            elif kind in ('gap', 'skip'):
                u += item[1]


    # THE WIDE SHELF on the left wall: its row runs along +y, into the shelf is -x (its front edge at x -2487)
    WIDE = dict(O=lambda z: (-2487.0, 1656.0, z * 1000.0), A=(0, 1, 0), B=(-1, 0, 0), L=1048.0, key='books_wide')
    NARROW = dict(O=lambda z: (1088.0, 2487.0, z * 1000.0), A=(1, 0, 0), B=(0, 1, 0), L=544.0, key='books_narrow')
    PLANS = {
        ('books_wide', 0): [('run', 6, 'binder', (300.0, 315.0), (45.0, 75.0), (285.0, 295.0)), ('gap', 30.0), ('stack', 4, 'art'), ('run', 5, 'art', (290.0, 310.0), (14.0, 26.0), (230.0, 245.0))],
        ('books_wide', 1): [('skip', 575.0), ('run', 9, 'cloth', (215.0, 245.0), (24.0, 48.0), (145.0, 165.0)), ('lean', 'cloth', 232.0, 34.0, 155.0)],
        ('books_wide', 2): [('run', 16, 'paper', (178.0, 200.0), (12.0, 32.0), (108.0, 128.0)), ('gap', 40.0), ('stack', 3, 'paper'), ('run', 10, 'paper', (178.0, 200.0), (12.0, 32.0), (108.0, 128.0))],
        ('books_wide', 3): [('run', 7, 'cloth', (220.0, 250.0), (22.0, 45.0), (150.0, 165.0)), ('run', 8, 'paper', (180.0, 205.0), (14.0, 30.0), (110.0, 130.0)), ('lean', 'paper', 196.0, 22.0, 120.0),
                            ('gap', 90.0), ('run', 6, 'cloth', (205.0, 235.0), (20.0, 40.0), (140.0, 160.0))],
        ('books_narrow', 0): [('run', 4, 'binder', (300.0, 315.0), (50.0, 80.0), (285.0, 295.0)), ('stack', 3, 'art')],
        ('books_narrow', 1): [('run', 14, 'paper', (178.0, 200.0), (12.0, 30.0), (108.0, 128.0)), ('lean', 'paper', 190.0, 20.0, 118.0)],
        ('books_narrow', 2): [('run', 8, 'cloth', (215.0, 245.0), (24.0, 46.0), (145.0, 165.0)), ('gap', 60.0), ('stack', 2, 'cloth')],
        ('books_narrow', 3): [('stack', 4, 'paper'), ('skip', 30.0), ('run', 5, 'cloth', (200.0, 230.0), (20.0, 40.0), (140.0, 160.0))],
        ('books_narrow', 4): [('skip', 120.0), ('stack', 3, 'art')],
    }
    for S, boards in ((WIDE, B1), (NARROW, B2)):
        for bi, bz in enumerate(boards):
            plan = PLANS.get((S['key'], bi))
            if plan:
                fill(Shelf(S['O'](bz), S['A'], S['B'], S['L']), S['key'], plan)
    for key, (cov, pag, info) in BOOKS.items():
        oc = fin(hs.skins(key + '_covers', cov), 0.6, COVERS)
        if pag:
            fin(hs.skins(key + '_page_blocks', pag), 0.4, PAGES)
        ca = oc.data.color_attributes.new('book_tint', 'FLOAT_COLOR', 'POINT')
        for v_ in oc.data.vertices:
            c_ = v_.co
            col = next((t_ for lo, hi, t_ in info if lo.x - 1e-4 <= c_.x <= hi.x + 1e-4 and lo.y - 1e-4 <= c_.y <= hi.y + 1e-4 and lo.z - 1e-4 <= c_.z <= hi.z + 1e-4), (0.3, 0.3, 0.3))
            ca.data[v_.index].color = (*col, 1.0)
        print('BOOKS', key, len(info), 'books', flush=True)
    # THE ENCYCLOPEDIA SET (CC0) on the wide shelf's second board, its spines to the room; the photo frame on the third
    if len(B1) > 1:
        # (the set ships along its x, spines on its -y side at y -0.101, from x -0.019: turned so the spines face the room,
        #  their faces 20 behind the board's front edge like the built books')
        cc0('book_encyclopedia_set_01', '1k', 'encyclopedia_run', (-2.487 - 0.02 - 0.101, 1.656 + 0.012 + 0.019, B1[1]), yaw=90.0, seat=B1[1])
    if len(B2) > 2:
        # (the frame ships facing +x, its stand behind it: turned to face the room, a little toward the desk)
        cc0('standing_picture_frame_01', '1k', 'photo_frame', (1.50, 2.487 + 0.09, B2[2]), yaw=-104.0, seat=B2[2])
