"""eidoblend.sets.town.house: one building of the town, whole or as a strike left it. Blender (mathutils; the mesh
through mb.MB). Metres; the building's own space: its front along y = 0 looking toward -y (the street), x along the
street from 0 to w, its lot running back to y = d.

    from eidoblend.sets.town.house import House
    h = House(random.Random(7), w=14.5, d=10.5, floors=4, shops=True, dmg=0, low=False, annex=4.0)
    me = h.mesh('block_shops', materials.M)          # h.anchors: where a dish may stand; h.zf: each floor's height

WHAT IT IS: a reinforced-concrete FRAME on a grid of bays (columns at the grid's nodes, a beam under the slab on every
grid line, a 0.2 m slab at each floor), filled in with hollow-block walls and plastered. Its facades follow a grammar of
bays and storeys: openings reserved first and built as true recesses with their reveals, frames and sills; a wall has
its thickness wherever its section can be seen; everything stands on something; nothing hidden is built.

THE MODEL: every bay of the grid, storey by storey, is a ROOM under its slab, a room OPEN TO THE SKY (its slab gone,
its walls broken off in courses), a storey BEING BUILT (frame and half-laid block), or nothing. A house is designed
first (never one box: a lower wing, a terrace, a stair head, a room on the roof, a storey begun and left), then
STRUCK (dmg), and only then built: so a slab knows whether its edge was cast that way or torn, a wall knows whether its
far side was always the street or was somebody's room, and the frame is built exactly where it shows.
dmg: 0 whole; 1 its front blown off over two or three bays; 2 a corner brought down; 3 half of it down; 4 a shell
through the roof; 5 scarred (a hole or two through its walls). What a strike does: the block walls go and the frame
stands; slab edges are bitten and pieces of slab hang by their steel; upper floors come down as tilted slabs on a
heap; the rooms stand open, still painted, with what was in them.
"""
import math

from mathutils import Matrix, Vector

from . import kit as K
from .mb import MB, arc, place
from .signs import N_BOARDS, lay_words

H, SLAB, WALL, PART, COL = 3.1, 0.20, 0.25, 0.15, 0.35
SIDES = (('S', 0, -1), ('E', 1, 0), ('N', 0, 1), ('W', -1, 0))
PAINTS = ['in_white', 'in_cream', 'in_blue', 'in_green', 'in_pink', 'in_white', 'in_cream']


def ev(prof, a):
    """a broken edge's height at a"""
    if a <= prof[0][0]:
        return prof[0][1]
    for (a0, b0), (a1, b1) in zip(prof, prof[1:]):
        if a <= a1:
            return b0 if a1 - a0 < 1e-9 else b0 + (b1 - b0) * (a - a0) / (a1 - a0)
    return prof[-1][1]


def jag(rng, L, base, amp, lo=0.0, hi=1e9, q=0.2, run=(0.2, 0.7)):
    """how a block wall breaks: along its courses, in steps. -> [(a, height)], a rising from 0 to L"""
    f = base if callable(base) else (lambda a: base)

    def lvl(a):
        return min(hi, max(lo, q * round((f(a) + rng.uniform(-amp, amp)) / q)))
    pts = [(0.0, lvl(0.0))]
    a = 0.0
    while a < L - 1e-6:
        a2 = min(L, a + rng.uniform(*run))
        pts.append((a2, pts[-1][1]))
        if a2 < L - 0.15:
            b2 = lvl(a2)
            if abs(b2 - pts[-1][1]) > 1e-6:
                a2 = a2 + rng.uniform(0.02, 0.1)
                pts.append((a2, b2))
        a = a2
    return pts


def broken_top(rng, L, h):
    """the top edge of a wall that lost its upper part: not a row of teeth (a battlement) but ONE break, as walls go: a
    bite out of its middle, or a run down from one standing end, or a stump; and that line stepped along the block
    courses"""
    kind = rng.choice(('bite', 'bite', 'down_l', 'down_r', 'stump'))
    top, low = h * rng.uniform(0.6, 1.0), h * rng.uniform(0.04, 0.35)
    c, e = rng.uniform(0.3, 0.7) * L, rng.uniform(1.2, 2.4)
    if kind == 'bite':
        def f(a):
            return low + (top - low) * min(1.0, abs(a - c) / (0.55 * L)) ** e
    elif kind == 'stump':
        def f(a):
            return low * 1.4
    else:
        def f(a):
            t = a / L if kind == 'down_l' else 1.0 - a / L
            return top + (low - top) * t ** (1.0 / e)
    return jag(rng, L, f, 0.14, 0.0, h, run=(0.2, 0.55))


def hole_prof(rng, L, h, gone):
    """a wall with a hole blown through it, or most of it gone: -> (the top edge of what stands below the hole, the
    bottom edge of what hangs above it); where the two meet there is no hole. A block wall breaks round its blocks:
    both edges run level along a course and step at a joint, never on straight slants"""
    q = 0.2
    if gone:
        ac, hw = L / 2.0 + rng.uniform(-0.3, 0.3), L * rng.uniform(0.56, 0.95)
        zl, zh = rng.choice((0.0, 0.0, 0.0, 0.2, 0.4)), h - rng.choice((0.0, 0.0, 0.2, 0.4, 0.6))
    else:
        ac, hw = rng.uniform(0.3, 0.7) * L, rng.uniform(0.2, 0.42) * L
        zl, zh = rng.choice((0.0, 0.2, 0.6, 1.0)), min(h, rng.uniform(0.62, 1.0) * h)
    zm = q * round(rng.uniform(0.38, 0.6) * h / q)
    skew = rng.uniform(-0.5, 0.5)                                 # (a blast's hole leans: wider low on one side)
    lo, hi = [], []
    a = 0.0
    while a < L - 1e-6:
        a2 = min(L, a + rng.choice((0.2, 0.2, 0.4, 0.4, 0.6)))
        if L - a2 < 0.15:
            a2 = L
        s = ((a + a2) / 2.0 - ac) / hw
        if abs(s) >= 1.0:
            l_ = g = zm
        else:
            k = math.sqrt(1.0 - s * s)
            l_ = min(zm, max(0.0, q * round((zm - (zm - zl) * k * (1.0 + skew * s) + rng.uniform(-0.22, 0.22)) / q)))
            g = max(zm, min(h, q * round((zm + (zh - zm) * k * (1.0 - skew * s) + rng.uniform(-0.22, 0.22)) / q)))
        for prof, v in ((lo, l_), (hi, g)):
            prof.append((a + (0.03 if a > 0 else 0.0), v))
            prof.append((a2, v))
        a = a2
    return lo, hi


def ragged_rect(rng, x0, y0, x1, y1, modes, depth):
    """a bay's slab in plan, counter-clockwise from its south-west corner: straight where it was cast to an edge or
    runs on into the next bay, bitten in where it was torn -> (its points, what the edge leaving each point is)"""
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    C = {'S': ((x0, y0), (x1, y0)), 'E': ((x1, y0), (x1, y1)), 'N': ((x1, y1), (x0, y1)), 'W': ((x0, y1), (x0, y0))}
    order = 'SENW'
    pts, kinds = [], []
    for q_, s in enumerate(order):
        (ax, ay), (bx, by) = C[s]
        torn = modes[s] == 'torn'
        if torn and modes[order[q_ - 1]] == 'torn':                # a corner with both its sides torn goes too
            f = min(0.45, rng.uniform(*depth) / math.hypot(cx - ax, cy - ay))
            pts.append((ax + (cx - ax) * f, ay + (cy - ay) * f))
        else:
            pts.append((ax, ay))
        kinds.append(modes[s])
        if torn:
            n = max(3, int(math.hypot(bx - ax, by - ay) / 0.45))
            d = rng.uniform(*depth)
            for k in range(1, n):
                t = (k + rng.uniform(-0.3, 0.3)) / n
                d = min(depth[1], max(depth[0], d + rng.uniform(-0.35, 0.35)))
                px, py = ax + (bx - ax) * t, ay + (by - ay) * t
                f = min(0.8, d / max(0.3, math.hypot(cx - px, cy - py)))
                pts.append((px + (cx - px) * f, py + (cy - py) * f))
                kinds.append('torn')
    return pts, kinds


def chains(edges):
    """directed edges [((x, y), (x, y))] joined end to end -> [(points, closed)], straight runs merged"""
    nxt = {}
    for a, c in edges:
        nxt.setdefault(a, []).append(c)
    ends = {c for _, c in edges}
    out = []

    def follow(a):
        pts = [a]
        while nxt.get(a):
            a = nxt[a].pop()
            pts.append(a)
            if a == pts[0]:
                return pts, True
        return pts, False
    for s in [a for a, _ in edges if a not in ends]:               # an open run starts where nothing arrives
        while nxt.get(s):
            out.append(follow(s))
    for a in list(nxt):
        while nxt[a]:
            out.append(follow(a))
    res = []
    for pts, closed in out:
        keep = []
        n = len(pts) - (1 if closed else 0)
        for k in range(n):
            if closed or 0 < k < n - 1:
                p, a, c = pts[k], pts[(k - 1) % n], pts[(k + 1) % n]
                if abs((p[0] - a[0]) * (c[1] - p[1]) - (p[1] - a[1]) * (c[0] - p[0])) < 1e-9:
                    continue                                       # a point on a straight run
            keep.append(pts[k])
        if len(keep) >= 2:
            res.append((keep, closed))
    return res


class House:
    signs = []                                                     # the shop signs (signs.prepare(): the layout sets them)

    def __init__(self, rng, w, d, floors, shops=False, dmg=0, low=False, annex=0.0):
        """w x d: its main part on the street; annex: how deep a range of low rooms and small courts runs on behind it
        (from the air no house there is one box, and no yard is empty)"""
        self.rng, self.w, self.d, self.F, self.shops, self.dmg, self.low, self.annex = rng, w, d, floors, shops, dmg, low, annex
        self.b = MB()
        self.anchors = []                                          # where a dish may stand: (x, y, z)
        self._grid()
        self._massing()
        self._strike()
        self._finishes()
        self._plan()
        self._slabs()
        self._walls()
        self._frame()
        self._balconies()
        self._parapets()
        self._roof_things()
        self._insides()
        self._fallen()

    # ------------------------------------------------------------------------------------------ the grid
    def _grid(self):
        rng, w, d, F = self.rng, self.w, self.d, self.F
        nb, ndm = max(2, round(w / 3.7)), max(2, round(d / 4.2))
        nd = ndm + (1 if self.annex > 0 else 0)
        self.nb, self.nd, self.ndm = nb, nd, ndm
        self.cells = [(i, j) for i in range(nb) for j in range(nd)]
        self.si, self.sj = rng.randrange(nb), ndm - 1              # the stair's bay: at the back of the main part
        wts = [rng.uniform(0.86, 1.14) for _ in range(nb)]         # (no two bays quite alike; the stair's narrower)
        if nb >= 3:
            wts[self.si] = 0.74
        xs = [0.0]
        for q in wts:
            xs.append(xs[-1] + w * q / sum(wts))
        xs[-1] = w
        wts = [rng.uniform(0.9, 1.1) for _ in range(ndm)]
        ys = [0.0]
        for q in wts:
            ys.append(ys[-1] + d * q / sum(wts))
        ys[-1] = d
        if self.annex > 0:
            ys.append(d + self.annex)
        self.d = ys[-1]                                            # (from here on: the whole depth it stands on)
        self.xs, self.ys = xs, ys
        self.plinth = 0.15 if self.shops else rng.choice((0.3, 0.45, 0.6))
        zf = [self.plinth]
        for f in range(F):
            zf.append(zf[-1] + ((3.75 if self.shops else H) if f == 0 else H))
        zf.append(zf[-1] + 2.55)                                   # the roof's own storey: a stair head, a room up there
        self.zf = zf
        self.ov = rng.choice((0.0, 0.0, 0.6, 0.8)) if (self.shops and F >= 2) else 0.0      # the upper floors step out over the pavement
        self.band = rng.choice((0.08, 0.1, 0.12)) if not self.low else rng.choice((0.1, 0.3, 0.45))   # a slab's edge proud of the wall; a low house's eave
        self.slots = [('H', i, j) for j in range(nd + 1) for i in range(nb)] + [('V', i, j) for i in range(nb + 1) for j in range(nd)]

    def Y(self, j, f):
        """a grid line across the building at storey f: the front line steps out above the ground floor"""
        return self.ys[j] if j > 0 else (-self.ov if f >= 1 else 0.0)

    def Yl(self, j, L):
        """the same for the slab at level L (it carries the storey above it)"""
        return self.ys[j] if j > 0 else (-self.ov if L >= 1 else 0.0)

    def cells_of(self, kind, i, j):
        """the bays on a wall line's two sides: (south or west, north or east)"""
        if kind == 'H':
            return ((i, j - 1) if j >= 1 else None), ((i, j) if j < self.nd else None)
        return ((i - 1, j) if i >= 1 else None), ((i, j) if i < self.nb else None)

    def slots_of(self, c):
        i, j = c
        return {'S': ('H', i, j), 'N': ('H', i, j + 1), 'W': ('V', i, j), 'E': ('V', i + 1, j)}

    # ------------------------------------------------------------------------------------------ the design
    def _massing(self):
        rng, F, nb, nd = self.rng, self.F, self.nb, self.ndm
        n0 = {c: F for c in self.cells}
        cap0 = {}
        r = rng.random()
        if F >= 2 and nd >= 3 and r < 0.26:                        # a lower range behind: a terrace at the back
            drop = rng.choice((1, 1, 2)) if F >= 3 else 1
            for i in range(nb):
                n0[(i, nd - 1)] = F - drop
        elif F >= 2 and nb >= 3 and r < 0.46:                      # one end lower
            e = rng.choice((0, nb - 1))
            for j in range(nd):
                n0[(e, j)] = F - 1
        elif F >= 2 and r < 0.62:                                  # a back corner stepped down
            n0[(rng.choice((0, nb - 1)), nd - 1)] = max(1, F - rng.choice((1, 1, 2)))
        elif nb >= 3 and nd >= 3 and r < 0.74:                     # a light court let into the back
            n0[(rng.randrange(1, nb - 1), nd - 1)] = 0
        if self.annex > 0:                                         # behind it: low rooms (a kitchen, a store), and small courts between
            for i in range(nb):
                n0[(i, nd)] = 1 if rng.random() < 0.62 else 0
        tops = [c for c in self.cells if n0[c] == F]
        mains = [c for c in tops if c[1] < nd] or tops
        back = max(j for _, j in mains)
        st = [c for c in mains if c[1] == back]
        if (self.si, self.sj) not in st:
            self.si, self.sj = rng.choice(st)
        n0[(self.si, self.sj)] = F + 1                             # the stair's head
        self.stair = (self.si, self.sj)
        free = [c for c in tops if c != self.stair]
        if free and rng.random() < (0.5 if self.low else 0.28):    # a room built on the roof
            near = [c for c in free if abs(c[0] - self.si) + abs(c[1] - self.sj) == 1] or free
            n0[rng.choice(near)] = F + 1
        free = [c for c in free if n0[c] == F]
        # a storey begun and left: block half laid, or (seldom) its frame standing; on one roof in seven, over three bays
        # at most (more, and from the air the town reads as pergolas)
        if free and rng.random() < 0.14:
            c0 = rng.choice(free)
            kind = rng.choice(('frame', 'build', 'build', 'build'))
            got = 0
            for c in free:
                if got < 3 and abs(c[0] - c0[0]) <= 1 and abs(c[1] - c0[1]) <= (1 if rng.random() < 0.5 else 0) and rng.random() < 0.8:
                    cap0[c] = kind
                    got += 1
        self.n0, self.cap0 = n0, cap0

    def st(self, c, f):
        """what stands in bay c at storey f: 'R' a room under its slab; 'U' a room open to the sky; 'C' a storey being
        built; 'N' nothing"""
        if c is None or c not in self.n1:
            return 'N'
        n = self.n1[c]
        if f < n:
            return 'R'
        if f == n:
            cp = self.cap1.get(c)
            if cp == 'roofless':
                return 'U'
            if cp in ('frame', 'build'):
                return 'C'
        return 'N'

    def was(self, c, f):
        return c is not None and c in self.n0 and f < self.n0[c]

    def paint(self, c, f):
        return PAINTS[(c[0] * 3 + c[1] * 5 + f * 7 + self.seed) % len(PAINTS)]

    # ------------------------------------------------------------------------------------------ the strike
    def _strike(self):
        rng, F, nb, nd, dmg = self.rng, self.F, self.nb, self.nd, self.dmg
        self.seed = rng.randrange(1000)
        n1, cap1, wst, bite = dict(self.n0), dict(self.cap0), {}, set()
        self.blown = None
        if dmg == 1:                                               # its front blown off over two or three bays
            k0 = rng.randrange(0, nb - 1) if nb > 2 else 0
            k1 = min(nb - 1, k0 + rng.randrange(1, 3))
            f0 = rng.randrange(0, max(1, F - 1))
            self.blown = (k0, k1, f0)
            for f in range(f0, F):
                for k in range(k0, k1 + 1):
                    if self.n0[(k, 0)] > f:
                        wst[(f, 'H', k, 0)] = 'gone' if (k0 < k < k1 or rng.random() < 0.65) else 'hole'
                        bite.add((f + 1, k, 0, 'S'))
                        if f >= 1:
                            bite.add((f, k, 0, 'S'))
                if k0 == 0 and rng.random() < 0.5:
                    wst[(f, 'V', 0, 0)] = rng.choice(('hole', 'gone'))
                if k1 == nb - 1 and rng.random() < 0.5:
                    wst[(f, 'V', nb, 0)] = rng.choice(('hole', 'gone'))
            if rng.random() < 0.5:                                 # and the roof over its top rooms came down
                for k in range(k0, k1 + 1):
                    if n1[(k, 0)] == F and (k, 0) not in cap1:
                        n1[(k, 0)], cap1[(k, 0)] = F - 1, 'roofless'
        elif dmg in (2, 3):                                        # a corner brought down; or half of it
            ci, cj = rng.choice((0, nb - 1)), rng.choice((0, nd - 1))
            reach = rng.uniform(1.4, 2.2) * (1.6 if dmg == 3 else 1.0)
            for c in self.cells:
                dist = math.hypot(c[0] - ci, c[1] - cj)
                if dist < reach and self.n0[c] > 0:
                    keep = max(0, min(self.n0[c], int(dist / reach * (F + 0.5) + rng.uniform(-0.6, 0.3))))
                    if keep < self.n0[c]:
                        n1[c] = keep
                        cap1.pop(c, None)
                        if rng.random() < (0.3 if dist < reach * 0.45 else 0.6):      # (at its heart nothing stands; at its edge walls do)
                            cap1[c] = 'roofless'
        elif dmg == 4:                                             # a shell through the roof
            top = [c for c in self.cells if self.n0[c] == F and c not in cap1 and F >= 1]
            if top:
                c0 = rng.choice(top)
                for c in top:
                    if c == c0 or (abs(c[0] - c0[0]) + abs(c[1] - c0[1]) == 1 and rng.random() < 0.45):
                        n1[c], cap1[c] = F - 1, 'roofless'
        elif dmg == 5:                                             # scarred: a hole or two through its walls
            for _ in range(rng.randrange(1, 4)):
                f = rng.randrange(F)
                if rng.random() < 0.7:
                    wst[(f, 'H', rng.randrange(nb), 0)] = 'hole'
                else:
                    wst[(f, 'V', rng.choice((0, nb)), rng.randrange(nd))] = 'hole'
        self.n1, self.cap1 = n1, cap1
        if dmg in (2, 3, 4):                                       # what stood next to the fall has lost walls too
            for f in range(F + 1):
                for s in self.slots:
                    A, B = self.cells_of(*s)
                    for X_, O_ in ((A, B), (B, A)):
                        if self.st(X_, f) == 'R' and self.was(O_, f) and self.st(O_, f) != 'R':
                            r = rng.random()
                            if r < 0.5:
                                wst[(f,) + s] = 'hole' if r < 0.3 else 'gone'
                        elif self.st(X_, f) == 'R' and O_ is None and any(self.n1[c] < self.n0[c] and abs(c[0] - X_[0]) + abs(c[1] - X_[1]) <= 1 for c in self.cells):
                            if rng.random() < 0.3:
                                wst[(f,) + s] = 'hole'
        self.wst, self.bite = wst, bite
        self.opened = set()                                        # rooms a wall has gone from: their insides are built
        for c in self.cells:
            for f in range(n1[c]):
                if any(wst.get((f,) + s) in ('hole', 'gone') for s in self.slots_of(c).values()):
                    self.opened.add((c, f))

    def _finishes(self):
        rng = self.rng
        hit = self.dmg in (1, 2, 3, 4)
        self.PL = 'plaster_dmg' if hit else 'plaster'
        brick = self.low and rng.random() < 0.3
        if brick:
            self.PL = 'brick'
        side = rng.random()
        self.PLs = self.PL if side < 0.5 else ('block' if side < 0.85 else 'brick')       # a wall on the lot's line is often left bare
        self.PLb = self.PL if rng.random() < 0.55 else self.PLs
        self.PL2 = 'plaster_b' if (not hit and not brick and rng.random() < 0.3) else self.PL   # a second colour: the ground floor, the balconies
        self.CO = 'concrete'
        self.band_m = self.PL if rng.random() < 0.6 else 'concrete'
        self.hp = rng.choice((0.5, 0.7, 0.9, 0.9, 1.05))           # the roof's parapet
        self.par_m = rng.choice((self.PL, self.PL, self.PL, 'block', 'claustra'))
        self.frame_m = rng.choice(('frame_alu', 'frame_alu', 'frame_white', 'frame_wood'))
        self.door_m = rng.choice(('door_green', 'door_blue', 'door_brown', 'door_grey', 'door_rust'))
        self.hoods = rng.random() < 0.35
        self.canopy = self.shops and rng.random() < 0.4            # one concrete canopy the length of the shops
        self.canopy_on = self.canopy and self.blown is None and self.dmg not in (2, 3)
        self.blinds = rng.random() < 0.5                           # roller blinds in the windows, as there

    # ------------------------------------------------------------------------------------------ the facades' plan
    def _plan(self):
        rng, F, nb, nd = self.rng, self.F, self.nb, self.nd
        fac = {}
        ent = self.si if nb > 2 else rng.randrange(nb)
        self.ent = ent
        up, wcol = [], []
        for i in range(nb):
            r = rng.random()
            up.append('win' if (i == ent and nb > 2) else 'balc' if r < 0.40 else 'win2' if r < 0.54 else 'blank' if r < 0.59 else 'win')
            wcol.append(rng.choice((1.0, 1.2, 1.2, 1.4, 1.6)))
        if F >= 2 and 'balc' not in up and rng.random() < 0.8:
            up[rng.choice([i for i in range(nb) if i != ent] or [0])] = 'balc'
        self.balc_kind = rng.choice(('solid', 'solid', 'solid', 'rail', 'claustra'))
        self.balc_round = rng.random() < 0.3
        for f in range(F):
            for i in range(nb):
                if f == 0 and self.shops and i != ent:
                    spec = dict(type='shop', shut=rng.randrange(6), open=rng.choice((0.0, 0.0, 0.0, 0.0, 0.0, 0.35, 0.8)),
                                awn=(rng.randrange(6) if (not self.canopy and rng.random() < 0.5) else None), sign=rng.random() < 0.85)
                elif f == 0 and i == ent:
                    spec = dict(type='door')
                elif f == 0:
                    spec = dict(type='win', w=wcol[i], sill=1.1)
                else:
                    spec = dict(type=up[i], w=wcol[i], sill=0.95)
                spec['shutter'] = rng.choice((0.0, 0.0, 0.0, 0.3, 0.6, 1.0)) if self.blinds else 0.0
                spec['ac'] = rng.random() < 0.12
                fac[(f, 'H', i, 0)] = spec
            for i in range(nb):                                    # the back: fewer and smaller
                fac[(f, 'H', i, nd)] = dict(type='win', w=rng.choice((0.8, 1.0, 1.2)), sill=1.0, shutter=0.0, ac=rng.random() < 0.1) if rng.random() < 0.55 else dict(type='blank')
            for j in range(nd):                                    # the sides: on the lot's line, mostly blind
                for i_ in (0, nb):
                    fac[(f, 'V', i_, j)] = dict(type='win', w=0.8, sill=1.2, shutter=0.0, ac=False) if rng.random() < 0.2 else dict(type='blank')
        self.fac = fac
        self.balc = {}                                             # (storey, bay) of every balcony's door that still stands
        self.roof_door = set()

    # ------------------------------------------------------------------------------------------ slabs
    def has_slab(self, c, L):
        if c is None or c not in self.n1:
            return False
        if L == 0:
            return self.n0[c] >= 1 or c in self.cap0
        return self.n1[c] >= L

    def had_slab(self, c, L):
        if c is None or c not in self.n0:
            return False
        if L == 0:
            return self.n0[c] >= 1 or c in self.cap0
        return self.n0[c] >= L

    def _slabs(self):
        b, rng, xs, zf, F = self.b, self.rng, self.xs, self.zf, self.F
        for L in range(0, F + 2):
            for c in self.cells:
                if not self.has_slab(c, L):
                    continue
                i, j = c
                x0, x1, yA, yB = xs[i], xs[i + 1], self.Yl(j, L), self.Yl(j + 1, L)
                zt = zf[L]
                zb = zt - SLAB if L else 0.0                       # (the ground floor's slab is the plinth, down to the ground)
                modes = {}
                for s, di, dj in SIDES:
                    nbc = (i + di, j + dj)
                    if self.has_slab(nbc, L):
                        modes[s] = 'shared'
                    elif (L >= 1 and self.had_slab(nbc, L)) or (L, i, j, s) in self.bite:
                        modes[s] = 'torn'
                    else:
                        modes[s] = 'clean'
                top_vis = (L == self.n1[c]) or ((c, L) in self.opened)
                bot_vis = L >= 1 and (((c, L - 1) in self.opened) or (j == 0 and L == 1 and self.ov > 0))
                torn = [s for s in 'SENW' if modes[s] == 'torn']
                band = 0.0 if L == 0 else self.band
                if not top_vis and not bot_vis and not torn:       # only its edge shows: a band proud of the wall
                    for s in 'SENW':
                        if modes[s] != 'clean':
                            continue
                        if band <= 0.0:
                            (ax, ay), (bx, by) = {'S': ((x0, yA), (x1, yA)), 'E': ((x1, yA), (x1, yB)), 'N': ((x1, yB), (x0, yB)), 'W': ((x0, yB), (x0, yA))}[s]
                            b.quad((ax, ay, zb), (bx, by, zb), (bx, by, zt), (ax, ay, zt), self.CO)
                        elif s in 'SN':
                            ew = band if modes['W'] == 'clean' else 0.0
                            ee = band if modes['E'] == 'clean' else 0.0
                            lo, hi = ((x0 - ew, yA - band, zb), (x1 + ee, yA, zt)) if s == 'S' else ((x0 - ew, yB, zb), (x1 + ee, yB + band, zt))
                            b.box(lo, hi, self.band_m, skip=('y+' if s == 'S' else 'y-') + ('x-' if modes['W'] == 'shared' else '') + ('x+' if modes['E'] == 'shared' else ''))
                        else:
                            lo, hi = ((x1, yA, zb), (x1 + band, yB, zt)) if s == 'E' else ((x0 - band, yA, zb), (x0, yB, zt))
                            b.box(lo, hi, self.band_m, skip=('x-' if s == 'E' else 'x+') + 'y-y+')
                    continue
                ex = {s: (band if modes[s] == 'clean' else 0.0) for s in modes}
                collapse = any(L >= 1 and self.had_slab((i + di, j + dj), L) and not self.has_slab((i + di, j + dj), L) for s, di, dj in SIDES)
                pts, kinds = ragged_rect(rng, x0 - ex['W'], yA - ex['S'], x1 + ex['E'], yB + ex['N'], modes, (0.2, 1.3) if collapse else (0.12, 0.85))
                if L == self.n0[c] and self.n1[c] == self.n0[c] and c not in self.cap1:
                    tm = 'roof'                                    # a roof, as it was built
                elif c in self.cap1 and self.cap1[c] in ('frame', 'build') and L == self.n1[c]:
                    tm = self.CO
                elif L == self.n0[c]:
                    tm = 'roof_dmg'
                else:
                    tm = 'floor'                                   # a floor nobody was meant to see from above
                b.poly([(x, y, zt) for x, y in pts], tm)
                if L >= 1:
                    b.poly([(x, y, zb) for x, y in reversed(pts)], 'ceiling')
                n = len(pts)
                for k in range(n):
                    if kinds[k] == 'shared':
                        continue
                    (ax, ay), (bx, by) = pts[k], pts[(k + 1) % n]
                    b.quad((ax, ay, zb), (bx, by, zb), (bx, by, zt), (ax, ay, zt), 'concrete_broken' if kinds[k] == 'torn' else (self.band_m if L else self.CO))
                    if kinds[k] == 'torn' and L >= 1 and rng.random() < 0.55:
                        # the ceiling's plaster hangs from the broken edge in scallops, as on every open floor's upper
                        # edge. A coat of plaster IS a sheet: one face, two centimetres thick there
                        d1, d2 = rng.uniform(0.05, 0.42), rng.uniform(0.05, 0.42)
                        b.poly(((ax, ay, zb), (bx, by, zb), (bx, by, zb - d2 * 0.4), ((ax + bx) / 2.0, (ay + by) / 2.0, zb - max(d1, d2)), (ax, ay, zb - d1 * 0.3)), 'ceiling')
                if L >= 1:
                    for s in torn:                                 # what is left of it hangs by its steel
                        self._hanging(c, L, s, (x0, yA, x1, yB), tm, big=collapse)

    def _hanging(self, c, L, s, rect, tm, big):
        b, rng = self.b, self.rng
        if rng.random() > (0.8 if big else 0.6):
            return
        x0, y0, x1, y1 = rect
        (ax, ay), (bx, by), o = {'S': ((x0, y0), (x1, y0), (0.0, -1.0)), 'E': ((x1, y0), (x1, y1), (1.0, 0.0)), 'N': ((x1, y1), (x0, y1), (0.0, 1.0)),
                                 'W': ((x0, y1), (x0, y0), (-1.0, 0.0))}[s]
        side = math.hypot(bx - ax, by - ay)
        drop = self.zf[L] - self.zf[L - 1]
        for _ in range(2 if (big and rng.random() < 0.5) else 1):
            wp = rng.uniform(0.9, max(1.0, min(2.8, side * 0.8)))
            lp = rng.uniform(0.9, max(1.0, min(2.7, drop - 0.45)))
            t = rng.uniform(0.25, 0.75)
            pull = rng.uniform(0.25, 0.6)
            hx, hy = ax + (bx - ax) * t - o[0] * pull, ay + (by - ay) * t - o[1] * pull
            ov_ = Vector((o[0], o[1], 0.0))
            xv = ov_.cross(Vector((0.0, 0.0, 1.0)))
            M0 = Matrix(((xv.x, ov_.x, 0.0, hx), (xv.y, ov_.y, 0.0, hy), (0.0, 0.0, 1.0, self.zf[L] - 0.02), (0.0, 0.0, 0.0, 1.0)))
            M = M0 @ Matrix.Rotation(-math.radians(rng.uniform(50.0, 86.0)), 4, 'X') @ Matrix.Rotation(rng.uniform(-0.12, 0.12), 4, 'Z')
            out = [(x, y + lp / 2.0) for x, y in K.ragged(rng, wp, lp, 7, 0.3)]
            b.plate(out, M, SLAB * 0.9, tm, 'concrete_broken', 'ceiling')
            for q in range(rng.randrange(2, 5)):                   # its steel: out of the slab's edge and down
                e = (q / 3.0 - 0.5) * wp * 0.8
                p0 = M0 @ Vector((e, -0.15, -0.08))
                b.path([p0, p0 + ov_ * 0.35 - Vector((0, 0, rng.uniform(0.05, 0.3))), p0 + ov_ * rng.uniform(0.3, 0.7) - Vector((0, 0, rng.uniform(0.5, 1.2)))], 0.011, 'rebar', n=3)

    # ------------------------------------------------------------------------------------------ walls
    def wall(self, P0, u, n, L, z0, h, t, mo, mi=None, ops=(), prof=None, mc='block', spec=None, broken=False, col_m=None):
        """one wall panel between two columns. P0: where its OUTER face starts in plan; u: along it (unit); n: out of it
        (unit); it is t thick, inward. mo, mi: its outer and inner faces (mi None: nobody sees its inside, and an
        opening is a recess with something at its back; mi given: its room stands open and an opening goes through).
        ops: [(a0, a1, b0, b1, depth, kind)] reserved first. prof: (lo, hi) for a wall that was hit: what
        stands is below lo and above hi, broken in courses; its section shows its block (mc)."""
        b = self.b
        ux, uy, nx, ny = u[0], u[1], n[0], n[1]

        def P(a, bb, dp=0.0):
            return (P0[0] + ux * a - nx * dp, P0[1] + uy * a - ny * dp, z0 + bb)
        if prof is None:
            cw = COL / 2.0 + 0.03                                   # where the wall is left bare, the frame shows in it
            xs_ = sorted({0.0, L} | {o[k] for o in ops for k in (0, 1)} | ({cw, L - cw} if col_m else set()))
            zs_ = sorted({0.0, h} | {o[k] for o in ops for k in (2, 3)})
            for i in range(len(xs_) - 1):
                for j in range(len(zs_) - 1):
                    a0, a1, b0, b1 = xs_[i], xs_[i + 1], zs_[j], zs_[j + 1]
                    if a1 - a0 < 1e-6 or b1 - b0 < 1e-6:
                        continue
                    if any(o[0] <= a0 + 1e-6 and a1 <= o[1] + 1e-6 and o[2] <= b0 + 1e-6 and b1 <= o[3] + 1e-6 for o in ops):
                        continue
                    if mo:
                        b.quad(P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1), col_m if (col_m and (a1 <= cw + 1e-6 or a0 >= L - cw - 1e-6)) else mo)
                    if mi:
                        b.quad(P(a1, b0, t), P(a0, b0, t), P(a0, b1, t), P(a1, b1, t), mi)
            for o in ops:
                a0, a1, b0, b1, dp, kind = o
                rv = t if mi else dp
                rm = mo or mi
                b.quad(P(a0, b0), P(a1, b0), P(a1, b0, rv), P(a0, b0, rv), rm)
                b.quad(P(a0, b1, rv), P(a1, b1, rv), P(a1, b1), P(a0, b1), rm)
                b.quad(P(a0, b0), P(a0, b0, rv), P(a0, b1, rv), P(a0, b1), rm)
                b.quad(P(a1, b0, rv), P(a1, b0), P(a1, b1), P(a1, b1, rv), rm)
                self._fill(P, o, spec or {}, through=bool(mi), broken=broken)
            return P
        lo, hi = prof
        mi = mi or mo
        A = sorted({a for a, _ in lo} | ({a for a, _ in hi} if hi else set()))
        for k in range(len(A) - 1):
            a0, a1 = A[k], A[k + 1]
            if a1 - a0 < 1e-6:
                continue
            l0, l1 = ev(lo, a0), ev(lo, a1)
            g0, g1 = (ev(hi, a0), ev(hi, a1)) if hi else (h, h)
            gap = (g0 - l0 > 1e-3) or (g1 - l1 > 1e-3)             # is there a hole over this stretch at all
            if not gap and hi:
                l0 = l1 = g0 = g1 = h * 0.5
            if l0 > 1e-3 or l1 > 1e-3:
                if mo:
                    b.quad(P(a0, 0.0), P(a1, 0.0), P(a1, l1), P(a0, l0), mo)
                b.quad(P(a1, 0.0, t), P(a0, 0.0, t), P(a0, l0, t), P(a1, l1, t), mi)
                if gap or not hi:
                    b.quad(P(a0, l0), P(a1, l1), P(a1, l1, t), P(a0, l0, t), mc)
            if hi and (g0 < h - 1e-3 or g1 < h - 1e-3):
                if mo:
                    b.quad(P(a0, g0), P(a1, g1), P(a1, h), P(a0, h), mo)
                b.quad(P(a1, g1, t), P(a0, g0, t), P(a0, h, t), P(a1, h, t), mi)
                if gap:
                    b.quad(P(a0, g0, t), P(a1, g1, t), P(a1, g1), P(a0, g0), mc)
        for a_, sgn in ((0.0, -1), (L, 1)):                        # its two ends, where it broke from the column
            l_ = ev(lo, a_)
            if l_ > 1e-3 and not hi:
                if sgn < 0:
                    b.quad(P(a_, 0.0, t), P(a_, 0.0), P(a_, l_), P(a_, l_, t), mc)
                else:
                    b.quad(P(a_, 0.0), P(a_, 0.0, t), P(a_, l_, t), P(a_, l_), mc)
        return P

    def wbox(self, P, a0, a1, b0, b1, d0, d1, m, skip='', top=None):
        """a box in a wall's own measures: along it a0..a1, up it b0..b1, from depth d0 to d1 (negative: proud of it)"""
        p = [P(a0, b0, d0), P(a1, b0, d0), P(a1, b0, d1), P(a0, b0, d1), P(a0, b1, d0), P(a1, b1, d0), P(a1, b1, d1), P(a0, b1, d1)]
        self.b.hexa(p, m, skip, top)

    def _fill(self, P, o, spec, through, broken):
        """what stands in an opening: a window's frame and panes, a door, a shutter; or, where it was hit, a dark hole"""
        b, rng = self.b, self.rng
        a0, a1, b0, b1, dp, kind = o
        fm = self.frame_m
        if kind in ('none', 'dark'):                                # a doorway in a partition: through, or onto a dark room
            if not through:
                b.quad(P(a0, b0, dp), P(a1, b0, dp), P(a1, b1, dp), P(a0, b1, dp), 'void')
            return
        if kind == 'shop':
            op = spec.get('open', 0.0) if not broken else rng.choice((0.0, 1.0, 1.0))
            zc = b0 + (b1 - b0) * op                                # the shutter's foot
            sm = f"shutter:{spec.get('shut', 0)}"
            if op < 0.98:
                b.quad(P(a0, zc, dp), P(a1, zc, dp), P(a1, b1, dp), P(a0, b1, dp), sm)
                self.wbox(P, a0, a1, zc, zc + 0.06, dp - 0.025, dp, 'steel_dark', skip='y+')
            if op > 0.02 and not through:                           # the shop behind it, dark
                b.quad(P(a0, b0, dp + 0.9), P(a1, b0, dp + 0.9), P(a1, zc, dp + 0.9), P(a0, zc, dp + 0.9), 'void')
                b.quad(P(a0, b0, dp), P(a1, b0, dp), P(a1, b0, dp + 0.9), P(a0, b0, dp + 0.9), 'floor')
                b.quad(P(a0, b0, dp), P(a0, b0, dp + 0.9), P(a0, zc, dp + 0.9), P(a0, zc, dp), 'in_white')
                b.quad(P(a1, b0, dp + 0.9), P(a1, b0, dp), P(a1, zc, dp), P(a1, zc, dp + 0.9), 'in_white')
            return
        if through and (broken or kind != 'door'):
            if rng.random() < 0.4 and kind in ('win', 'balc'):       # a frame still in it, the glass gone
                for bar in ((a0, a0 + 0.05, b0, b1), (a1 - 0.05, a1, b0, b1), (a0 + 0.05, a1 - 0.05, b1 - 0.05, b1)):
                    self.wbox(P, bar[0], bar[1], bar[2], bar[3], dp, dp + 0.04, fm)
            return
        if kind == 'door':
            dm = spec.get('m', self.door_m)
            fan = b1 - 0.38 if (b1 - b0) > 2.2 else b1
            b.quad(P(a0 + 0.05, b0, dp), P(a1 - 0.05, b0, dp), P(a1 - 0.05, fan, dp), P(a0 + 0.05, fan, dp), dm)
            for bar in ((a0, a0 + 0.05, b0, b1), (a1 - 0.05, a1, b0, b1), (a0 + 0.05, a1 - 0.05, b1 - 0.05, b1), (a0 + 0.05, a1 - 0.05, fan - 0.03, fan + 0.03)):
                self.wbox(P, bar[0], bar[1], bar[2], bar[3], dp - 0.02, dp + 0.03, dm, skip='y+')
            if a1 - a0 > 1.0:
                self.wbox(P, (a0 + a1) / 2 - 0.02, (a0 + a1) / 2 + 0.02, b0, fan, dp - 0.012, dp, dm, skip='y+')
            if fan < b1:
                b.quad(P(a0 + 0.05, fan, dp + 0.02), P(a1 - 0.05, fan, dp + 0.02), P(a1 - 0.05, b1 - 0.05, dp + 0.02), P(a0 + 0.05, b1 - 0.05, dp + 0.02), 'glass')
            return
        if broken:                                                  # the glass gone, the room dark behind it
            b.quad(P(a0, b0, dp + 0.3), P(a1, b0, dp + 0.3), P(a1, b1, dp + 0.3), P(a0, b1, dp + 0.3), 'void')
            for q_, bar in enumerate(((a0, a0 + 0.05, b0, b1), (a1 - 0.05, a1, b0, b1), (a0 + 0.05, a1 - 0.05, b1 - 0.05, b1), (a0 + 0.05, a1 - 0.05, b0, b0 + 0.05))):
                if rng.random() < 0.6:
                    self.wbox(P, bar[0], bar[1], bar[2], bar[3], dp, dp + 0.04, fm, skip='y+')
            return
        # a window or a balcony's door: its frame, a mullion (a rail across a door), the panes set back in it
        bars = [(a0, a0 + 0.05, b0, b1), (a1 - 0.05, a1, b0, b1), (a0 + 0.05, a1 - 0.05, b0, b0 + 0.05), (a0 + 0.05, a1 - 0.05, b1 - 0.05, b1)]
        if a1 - a0 > 0.85:
            am = (a0 + a1) / 2.0
            bars.append((am - 0.03, am + 0.03, b0 + 0.05, b1 - 0.05))
        if kind == 'balc':
            bars.append((a0 + 0.05, a1 - 0.05, b0 + 0.9, b0 + 0.96))
        for bar in bars:
            self.wbox(P, bar[0], bar[1], bar[2], bar[3], dp, dp + 0.045, fm, skip='y+')
        b.quad(P(a0 + 0.05, b0 + 0.05, dp + 0.03), P(a1 - 0.05, b0 + 0.05, dp + 0.03), P(a1 - 0.05, b1 - 0.05, dp + 0.03), P(a0 + 0.05, b1 - 0.05, dp + 0.03), 'glass')
        sh = spec.get('shutter', 0.0)
        if sh > 0.02:                                               # a roller blind let down in front of it
            zs = b1 - (b1 - b0) * sh
            b.quad(P(a0 + 0.02, zs, dp - 0.03), P(a1 - 0.02, zs, dp - 0.03), P(a1 - 0.02, b1, dp - 0.03), P(a0 + 0.02, b1, dp - 0.03), f"shutter:{(self.seed + 5) % 6}")
            self.wbox(P, a0 + 0.02, a1 - 0.02, zs - 0.04, zs, dp - 0.045, dp - 0.02, 'frame_alu')

    def _ops(self, spec, L, h, f):
        """a bay's openings from its plan"""
        t = spec.get('type', 'blank')
        if t == 'shop':
            return [(0.28, L - 0.28, 0.02, 2.75, 0.14, 'shop')]
        if t == 'door':
            return [(L / 2.0 - 0.6, L / 2.0 + 0.6, 0.0, min(2.45, h - 0.2), 0.2, 'door')]
        if t == 'win':
            ww = min(spec.get('w', 1.2), L - 0.7)
            s = spec.get('sill', 0.95)
            return [(L / 2.0 - ww / 2.0, L / 2.0 + ww / 2.0, s, min(s + 1.25, h - 0.25), 0.16, 'win')]
        if t == 'win2' and L > 3.0:
            out = []
            for q in (0.27, 0.73):
                out.append((L * q - 0.42, L * q + 0.42, 0.95, 2.2, 0.16, 'win'))
            return out
        if t == 'win2':
            return [(L / 2.0 - 0.6, L / 2.0 + 0.6, 0.95, 2.2, 0.16, 'win')]
        if t == 'balc':
            dw = min(1.4, L - 1.0)
            out = [(L * 0.42 - dw / 2.0, L * 0.42 + dw / 2.0, 0.02, 2.2, 0.16, 'balc')]
            if L > 3.9:
                out.append((L - 1.25, L - 0.45, 0.95, 2.2, 0.16, 'win'))
            return out
        return []

    def _dress(self, P, spec, ops, L, h, f, front, n, u, P0, z0):
        """what is fixed to a bay's wall outside: a sill under each window, a hood over some, a cooler's condenser on
        its brackets, a shop's sign and awning, a door's steps"""
        b, rng = self.b, self.rng
        t = spec.get('type', 'blank')
        for (a0, a1, b0, b1, dp, kind) in ops:
            if kind == 'win':
                self.wbox(P, a0 - 0.06, a1 + 0.06, b0 - 0.07, b0, -0.06, 0.1, self.CO, skip='y+')
                if self.hoods and front:
                    self.wbox(P, a0 - 0.12, a1 + 0.12, b1 + 0.03, b1 + 0.11, -0.3, 0.0, self.CO, skip='y+')
                if spec.get('ac') and b0 > 0.7:
                    a = min(L - 0.5, a1 + 0.1) if a1 + 0.9 < L else a0 - 0.5
                    c = P(a, b0 - 0.75, -0.19)
                    M = Matrix(((u[0], -n[0], 0.0, c[0]), (u[1], -n[1], 0.0, c[1]), (0.0, 0.0, 1.0, c[2]), (0.0, 0.0, 0.0, 1.0)))
                    K.condenser(b, M)
        if t == 'shop':
            a0, a1 = 0.28, L - 0.28
            self.wbox(P, a0 - 0.08, a0, 0.02, 2.75, -0.02, 0.14, 'frame_alu', skip='y+')       # the shutter's guides
            self.wbox(P, a1, a1 + 0.08, 0.02, 2.75, -0.02, 0.14, 'frame_alu', skip='y+')
            self.wbox(P, 0.15, L - 0.15, -self.plinth + 0.0, 0.0, -0.3, 0.0, self.CO, skip='y+z-')      # its step
            if spec.get('sign'):
                # its sign: a boxed board over the shutter; or, where the shops share a canopy, standing on its edge.
                # The board carries the picture or the words the town was given (signs.prepare), else plain paint
                hh = min(0.72, (L - 0.6) * 0.3125)
                if self.canopy_on:
                    zs0, d0, d1 = 3.13, -1.35, -1.27
                else:
                    zs0, d0, d1 = 2.84, -0.09, 0.0
                zs1 = zs0 + hh if self.canopy_on else min(h - 0.06, zs0 + hh)
                self.wbox(P, 0.3, L - 0.3, zs0, zs1, d0, d1, 'frame_alu', skip='' if self.canopy_on else 'y+')
                k = rng.randrange(len(self.signs) if self.signs else N_BOARDS)
                sg = self.signs[k] if self.signs else {}
                face = f'sign:{k}' if sg.get('image') else f'sign_board:{k}'
                b.quad(P(0.34, zs0 + 0.04, d0 - 0.004), P(L - 0.34, zs0 + 0.04, d0 - 0.004), P(L - 0.34, zs1 - 0.04, d0 - 0.004), P(0.34, zs1 - 0.04, d0 - 0.004),
                       face, uv=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
                if sg.get('polys'):
                    lay_words(b, P, sg, (0.34, zs0 + 0.04, L - 0.34, zs1 - 0.04), d0 - 0.012, f'sign_text:{k}')
            if spec.get('awn') is not None:                         # canvas on a light frame, a valance hanging at its edge
                am = f"awn:{spec['awn']}"
                out, zt, ze = rng.uniform(1.1, 1.6), 2.78, 2.3
                self.b.grid([[P(0.12 + (L - 0.24) * k / 4.0, zt - (zt - ze) * q / 2.0 - 0.04 * math.sin(math.pi * k / 4.0) * (q > 0), -0.02 - out * q / 2.0) for k in range(5)]
                             for q in range(3)], am, smooth=True, flip=True)
                for k in range(8):                                  # the valance, in tongues
                    k0, k1 = 0.12 + (L - 0.24) * k / 8.0, 0.12 + (L - 0.24) * (k + 1) / 8.0
                    b.poly([P(k0, ze, -0.02 - out), P(k1, ze, -0.02 - out), P(k1, ze - 0.16, -0.02 - out), P((k0 + k1) / 2.0, ze - 0.24, -0.02 - out), P(k0, ze - 0.16, -0.02 - out)], am)
                for a in (0.14, L - 0.14):
                    b.beam(P(a, zt - 0.05, 0.0), P(a, ze, -0.02 - out), 0.025, 0.025, 'steel_dark')
                    b.beam(P(a, zt - 0.9, 0.0), P(a, ze, -0.02 - out), 0.02, 0.02, 'steel_dark')
        if t == 'door' and f == 0:
            k = max(1, int(round(self.plinth / 0.15)))
            for q in range(k):                                      # its steps: each its own tread, down to the pavement
                self.wbox(P, L / 2.0 - 0.85, L / 2.0 + 0.85, -self.plinth, -self.plinth * q / k, -0.3 * (q + 1), -0.3 * q, self.CO, skip='y+z-')
            self.wbox(P, L / 2.0 - 0.95, L / 2.0 + 0.95, min(2.6, h - 0.15), min(2.7, h - 0.05), -0.75, 0.0, self.CO, skip='y+')

    def _walls(self):
        b, rng, xs, zf, F, nb, nd = self.b, self.rng, self.xs, self.zf, self.F, self.nb, self.nd
        hit = self.dmg in (1, 2, 3, 4)
        for f in range(F + 1):
            z0, hs = zf[f], zf[f + 1] - zf[f]
            h = hs - SLAB
            for s in self.slots:
                kind, i, j = s
                A, B = self.cells_of(kind, i, j)
                sa, sb = self.st(A, f), self.st(B, f)
                if sa in 'NC' and sb in 'NC':
                    continue
                if kind == 'H':
                    pa, pb = (xs[i], self.Y(j, f)), (xs[i + 1], self.Y(j, f))
                else:
                    pa, pb = (xs[i], self.Y(j, f)), (xs[i], self.Y(j + 1, f))
                L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
                state = self.wst.get((f,) + s, 'ok')
                if sa in 'RU' and sb in 'RU':                       # a partition between two rooms
                    oa, ob = (A, f) in self.opened or sa == 'U', (B, f) in self.opened or sb == 'U'
                    if not (oa or ob):
                        continue                                    # (nobody can see it)
                    n = (0.0, 1.0) if kind == 'H' else (1.0, 0.0)   # out of A, into B: its 'outer' face is B's wall
                    u = (-n[1], n[0])
                    P0 = pa if (u[0] * (pb[0] - pa[0]) + u[1] * (pb[1] - pa[1])) > 0 else pb
                    P0 = (P0[0] + n[0] * PART / 2.0, P0[1] + n[1] * PART / 2.0)
                    ma, mb = self.paint(A, f), self.paint(B, f)
                    if sa == 'U' and sb == 'U':
                        if rng.random() < 0.6:                      # (a thin partition between two fallen rooms mostly went with them)
                            self.wall(P0, u, n, L, z0, h, PART, mb, ma, prof=(broken_top(rng, L, h * rng.choice((0.3, 0.6, 1.0))), None))
                    elif state in ('hole', 'gone'):
                        self.wall(P0, u, n, L, z0, h, PART, mb, ma, prof=hole_prof(rng, L, h, state == 'gone'))
                    else:
                        ops = [(L * 0.3 - 0.45, L * 0.3 + 0.45, 0.0, 2.05, 0.1, 'none')] if (L > 2.2 and rng.random() < 0.55) else []
                        if oa and ob:
                            self.wall(P0, u, n, L, z0, h, PART, mb, ma, ops)
                        elif ob:
                            self.wall(P0, u, n, L, z0, h, PART, mb, None, [(o[0], o[1], o[2], o[3], 0.1, 'dark') for o in ops])
                        else:
                            self.wall(P0, u, n, L, z0, h, PART, None, ma, [])
                    continue
                # one side is a room, the other is air
                ins, out_, s_in = (A, B, sa) if sa in 'RU' else (B, A, sb)
                n = ((0.0, 1.0) if ins == A else (0.0, -1.0)) if kind == 'H' else ((1.0, 0.0) if ins == A else (-1.0, 0.0))
                u = (-n[1], n[0])
                P0 = pa if (u[0] * (pb[0] - pa[0]) + u[1] * (pb[1] - pa[1])) > 0 else pb
                indoors = self.was(out_, f)                         # its far side was a room until the strike
                front = kind == 'H' and j == 0
                if indoors:
                    mo, t = self.paint(out_, f), PART
                elif out_ is None:
                    mo, t = (self.PL if front else self.PLb if kind == 'H' else self.PLs), WALL
                    if front and f == 0:
                        mo = self.PL2
                else:
                    mo, t = self.PL, WALL                           # over the house's own lower roof
                mi = self.paint(ins, f)
                if s_in == 'U':                                     # broken off in courses, open to the sky
                    self.wall(P0, u, n, L, z0, h, t, mo, mi, prof=(broken_top(rng, L, h), None))
                    continue
                opened = (ins, f) in self.opened
                if state in ('hole', 'gone'):
                    if state == 'gone' and rng.random() < 0.3:
                        continue
                    self.wall(P0, u, n, L, z0, h, t, mo, mi, prof=hole_prof(rng, L, h, state == 'gone'))
                    continue
                if indoors:
                    ops = [(L * 0.3 - 0.45, L * 0.3 + 0.45, 0.0, 2.05, 0.1, 'dark')] if (L > 2.2 and rng.random() < 0.4 and not opened) else []
                    self.wall(P0, u, n, L, z0, h, t, mo, mi if opened else None, ops)
                    continue
                spec = self.fac.get((f,) + s) if out_ is None else None
                if spec is None:                                    # a wall the plan did not know: on the roof, or over a terrace
                    if f == F and ins not in self.roof_door and out_ is not None and self.st(out_, f - 1) == 'R' and self.n1.get(out_) == f:
                        spec = dict(type='door', m=self.door_m)
                        self.roof_door.add(ins)
                    elif rng.random() < 0.4:
                        spec = dict(type='win', w=0.9, sill=1.0, shutter=0.0, ac=False)
                    else:
                        spec = dict(type='blank')
                ops = self._ops(spec, L, h, f)
                P = self.wall(P0, u, n, L, z0, h, t, mo, mi if opened else None, ops, spec=spec, broken=hit and rng.random() < 0.75,
                              col_m=self.CO if mo in ('block', 'brick') else None)
                self._dress(P, spec, ops, L, h, f, front, n, u, P0, z0)
                if spec.get('type') == 'balc' and front and f >= 1:
                    self.balc[(f, i)] = True

    # ------------------------------------------------------------------------------------------ the frame, where it shows
    def _frame(self):
        b, rng, xs, zf, F, nb, nd = self.b, self.rng, self.xs, self.zf, self.F, self.nb, self.nd

        def expo(c, f):
            s = self.st(c, f)
            return s in 'UC' or (s == 'R' and (c, f) in self.opened)
        for f in range(F + 1):
            z0, z1 = zf[f], zf[f + 1]
            for i in range(nb + 1):
                for j in range(nd + 1):
                    around = [(i + di, j + dj) for di in (-1, 0) for dj in (-1, 0)]
                    around = [c for c in around if c in self.n1]
                    if not any(expo(c, f) for c in around):
                        continue
                    # (a finger's width inside the wall's face: where the wall still stands its plaster covers the frame)
                    cx = min(max(xs[i], COL / 2.0 + 0.02), self.w - COL / 2.0 - 0.02)
                    cy = min(max(self.Y(j, f), self.Y(0, f) + COL / 2.0 + 0.02), self.d - COL / 2.0 - 0.02)
                    under = any(self.st(c, f) == 'R' for c in around)       # a slab rests on it
                    built = any(self.cap1.get(c) in ('frame', 'build') and self.st(c, f) == 'C' for c in around)
                    if under:
                        b.box((cx - COL / 2, cy - COL / 2, z0), (cx + COL / 2, cy + COL / 2, z1 - SLAB), self.CO, skip='z-z+')
                    elif built:
                        full = any(self.cap1.get(c) == 'frame' for c in around) or rng.random() < 0.6
                        K.stub(b, rng, cx, cy, z0, (z1 - z0) if full else rng.uniform(0.5, 1.6), bars=4, w=COL)
                    else:                                           # snapped, its steel standing out of it
                        K.stub(b, rng, cx, cy, z0, (z1 - z0) * rng.uniform(0.35, 1.0), bars=rng.randrange(3, 6), w=COL)
            for s in self.slots:
                kind, i, j = s
                A, B = self.cells_of(kind, i, j)
                if not ((A in self.n1 and expo(A, f)) or (B in self.n1 and expo(B, f))):
                    continue
                slab = self.st(A, f) == 'R' or self.st(B, f) == 'R'
                framed = any(self.cap1.get(c) == 'frame' and self.st(c, f) == 'C' for c in (A, B) if c in self.n1)
                if not (slab or framed):
                    continue
                zt = z1 - SLAB if slab else z1
                zb = z1 - 0.5
                if kind == 'H':
                    y = min(max(self.Y(j, f), self.Y(0, f) + 0.17), self.d - 0.17)
                    b.box((xs[i] + COL / 2, y - 0.15, zb), (xs[i + 1] - COL / 2, y + 0.15, zt), self.CO, skip='x-x+' + ('z+' if slab else ''))
                else:
                    x = min(max(xs[i], 0.17), self.w - 0.17)
                    b.box((x - 0.15, self.Y(j, f) + COL / 2, zb), (x + 0.15, self.Y(j + 1, f) - COL / 2, zt), self.CO, skip='y-y+' + ('z+' if slab else ''))
        # block half laid for the storey being built: clean courses, stepped where the day's work stopped
        for c, cp in self.cap1.items():
            if cp != 'build':
                continue
            f = self.n1[c]
            if f > F:
                continue
            for sd, (kind, i, j) in self.slots_of(c).items():
                A, B = self.cells_of(kind, i, j)
                other = B if A == c else A
                if other in self.n1 and self.st(other, f) != 'N':
                    continue
                if rng.random() < 0.3:
                    continue
                n = {'S': (0.0, -1.0), 'N': (0.0, 1.0), 'W': (-1.0, 0.0), 'E': (1.0, 0.0)}[sd]
                u = (-n[1], n[0])
                pa, pb = ((xs[i], self.Y(j, f)), (xs[i + 1], self.Y(j, f))) if kind == 'H' else ((xs[i], self.Y(j, f)), (xs[i], self.Y(j + 1, f)))
                P0 = pa if (u[0] * (pb[0] - pa[0]) + u[1] * (pb[1] - pa[1])) > 0 else pb
                L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
                self.wall(P0, u, n, L, zf[f], zf[f + 1] - zf[f], 0.2, 'block', 'block', prof=(jag(rng, L, rng.uniform(0.6, 1.8), 0.25, 0.2, 2.2, run=(0.8, 2.0)), None))

    # ------------------------------------------------------------------------------------------ balconies
    def _balconies(self):
        b, rng, xs, zf = self.b, self.rng, self.xs, self.zf
        self.balc_dish = False
        for f in range(1, self.F):
            k = 0
            while k < self.nb:
                if not self.balc.get((f, k)):
                    k += 1
                    continue
                k1 = k
                while k1 + 1 < self.nb and self.balc.get((f, k1 + 1)):
                    k1 += 1
                xa, xb = xs[k] + 0.12, xs[k1 + 1] - 0.12
                yf = self.Y(0, f)
                out = rng.choice((1.05, 1.2, 1.3))
                z = zf[f] - 0.03
                R = 0.45 if self.balc_round else 0.0
                if R:
                    line = [(xa, yf)] + arc((xa + R, yf - out + R), R, 180.0, 270.0, 4) + arc((xb - R, yf - out + R), R, 270.0, 360.0, 4) + [(xb, yf)]
                else:
                    line = [(xa, yf), (xa, yf - out), (xb, yf - out), (xb, yf)]
                b.prism(line, z - 0.14, z, self.CO, top='floor', sides=[True] * (len(line) - 1) + [False])       # its slab, cast out from the floor's
                pm = self.PL2
                if self.balc_kind == 'solid':
                    b.run(line, 0.12, z, z + 0.95, pm, top=self.CO)
                elif self.balc_kind == 'claustra':
                    b.run(line, 0.12, z, z + 0.3, pm)
                    b.run(line, 0.1, z + 0.3, z + 0.9, 'claustra')
                    b.run(line, 0.14, z + 0.9, z + 0.97, self.CO)
                else:                                               # a kerb, posts, three rails
                    b.run(line, 0.1, z, z + 0.12, self.CO)
                    for q in (0.4, 0.68, 0.96):
                        for a, c in zip(line, line[1:]):
                            b.beam((a[0], a[1], z + q), (c[0], c[1], z + q), 0.03, 0.03, 'steel_paint')
                    nseg = max(2, int((xb - xa) / 0.9))
                    for q in range(nseg + 1):
                        px = xa + (xb - xa) * q / nseg
                        py = yf - out if (not R or (xa + R < px < xb - R)) else yf - out + R
                        b.beam((px, py, z + 0.1), (px, py, z + 0.96), 0.03, 0.03, 'steel_paint', up=(1.0, 0.0, 0.0))
                if rng.random() < 0.3 and not R:                    # washing over its parapet: side by side, nothing over anything
                    px = xa + rng.uniform(0.3, 0.8)
                    while True:
                        ww = rng.choice((0.5, 0.6, 0.8, 1.0, 1.4))
                        if px + ww > xb - 0.3:
                            break
                        K.rug_over(b, rng, (px + ww / 2.0, yf - out), (1.0, 0.0), (0.0, -1.0), z + 0.95, 0.12, rng.choice(K.CLOTH), w=ww)
                        px += ww + rng.uniform(0.08, 0.5)
                if not self.balc_dish and rng.random() < 0.18:      # one family's dish, on its balcony
                    self.balc_dish = True
                    self.anchors.append((rng.uniform(xa + 0.4, xb - 0.4), yf - out + 0.35, z))
                k = k1 + 1
        if self.canopy_on:                                          # the shops' canopy, cast with the first floor
            z = self.zf[0] + 3.0
            b.box((-0.1, -1.35, z), (self.w + 0.1, 0.0, z + 0.12), self.CO, skip='y+')

    # ------------------------------------------------------------------------------------------ the roofs' edges
    def _parapets(self):
        b, xs, zf, F = self.b, self.xs, self.zf, self.F
        levels = sorted({self.n1[c] for c in self.cells if self.n1[c] >= 1})
        self.roofs = {}                                             # level -> its bays that are a roof as built
        for L in levels:
            edges = []
            for c in self.cells:
                if self.n1[c] != L or self.n0[c] != L or c in self.cap1:
                    continue
                self.roofs.setdefault(L, []).append(c)
                i, j = c
                x0, x1, y0, y1 = round(xs[i], 3), round(xs[i + 1], 3), round(self.Yl(j, L), 3), round(self.Yl(j + 1, L), 3)
                for s, di, dj in SIDES:
                    nbc = (i + di, j + dj)
                    if nbc in self.n1:
                        if self.n1[nbc] > L or (self.n1[nbc] == L):
                            continue                                # a higher part's wall stands here, or the roof runs on
                        if self.n0[nbc] >= L:
                            continue                                # that side fell: the parapet went with it
                    if (L, i, j, s) in self.bite:
                        continue
                    edges.append({'S': ((x0, y0), (x1, y0)), 'E': ((x1, y0), (x1, y1)), 'N': ((x1, y1), (x0, y1)), 'W': ((x0, y1), (x0, y0))}[s])
            top = L == F + 1
            hp = 0.14 if top else (self.hp if L == F else min(self.hp, 0.9))
            for pts, closed in chains(edges):
                if top:
                    b.run(pts, 0.15, zf[L], zf[L] + hp, self.CO, closed=closed)
                else:
                    b.run(pts, 0.2, zf[L], zf[L] + hp, self.par_m, closed=closed, top=self.CO)
                    b.run(pts, 0.2, zf[L] + hp, zf[L] + hp + 0.06, self.CO, closed=closed)        # its coping
                self._par = getattr(self, '_par', []) + [(L, pts, closed, hp)]
        # a low wall across the roof between two households' halves, a gap left in it to step through (in a crowded
        # quarter every roof is cut into yards)
        rng = self.rng
        rf = set(self.roofs.get(F, []))
        if len(rf) >= 4 and rng.random() < 0.45:
            cands = [i for i in range(1, self.nb) if sum(1 for j in range(self.nd) if (i - 1, j) in rf and (i, j) in rf) >= 2]
            if cands:
                i = rng.choice(cands)
                js = [j for j in range(self.nd) if (i - 1, j) in rf and (i, j) in rf]
                gap = rng.choice(js)
                for j in js:
                    ya, yb = self.Yl(j, F) + (0.2 if (i, j - 1) not in rf else 0.0), self.Yl(j + 1, F) - (0.2 if (i, j + 1) not in rf else 0.0)
                    if j == gap:
                        yb -= 1.1
                    if yb - ya > 0.4:
                        b.box((xs[i] - 0.08, ya, zf[F]), (xs[i] + 0.08, yb, zf[F] + self.hp * 0.85), self.par_m, skip='z-', top=self.CO)

    # ------------------------------------------------------------------------------------------ what lives on the roofs
    def _roof_things(self):
        b, rng, xs, zf, F = self.b, self.rng, self.xs, self.zf, self.F
        taken = []

        def spot(c, L, r, tries=10, edge=None):
            i, j = c
            x0, x1, y0, y1 = xs[i] + 0.4 + r, xs[i + 1] - 0.4 - r, self.Yl(j, L) + 0.4 + r, self.Yl(j + 1, L) - 0.4 - r
            if x1 <= x0 or y1 <= y0:
                return None
            for _ in range(tries):
                x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
                if edge == 'corner':
                    x, y = rng.choice((x0, x1)), rng.choice((y0, y1))
                if all(math.hypot(x - tx, y - ty) > r + tr for tx, ty, tr in taken):
                    taken.append((x, y, r))
                    return x, y
            return None
        top = self.roofs.get(F + 1, [])
        main = [c for L, cs in self.roofs.items() if L <= F for c in cs]
        lvl = {c: self.n1[c] for c in main}
        if not main and not top:
            return
        tank_m = lambda: rng.choice(('tank_white', 'tank_white', 'tank_black', 'tank_blue', 'tank_black'))    # noqa: E731
        n_tanks = 0
        for c in top:                                               # the tank on the stair's head, where the pressure is
            if rng.random() < 0.55:
                p = spot(c, F + 1, 0.7)
                if p:
                    z = zf[F + 1]
                    if rng.random() < 0.6:
                        b.box((p[0] - 0.6, p[1] - 0.6, z), (p[0] + 0.6, p[1] + 0.6, z + 0.2), 'block', skip='z-')
                        K.tank_poly(b, p[0], p[1], z + 0.2, tank_m())
                    else:
                        K.tank_steel(b, rng, p[0], p[1], z, rng.uniform(-0.1, 0.1), rng.choice(('zinc', 'zinc_old', 'rust')))
                    n_tanks += 1
            if rng.random() < 0.3:
                p = spot(c, F + 1, 0.2)
                if p:
                    K.antenna(b, rng, p[0], p[1], zf[F + 1])
        if not main:
            return
        pick = lambda: rng.choice(main)                             # noqa: E731
        for _ in range(rng.choice((1, 1, 2)) if n_tanks == 0 else rng.choice((0, 0, 1))):
            c = pick()
            p = spot(c, lvl[c], 0.8)
            if not p:
                continue
            z, k = zf[lvl[c]], rng.random()
            if k < 0.45:
                hs_ = rng.choice((0.6, 0.9, 1.2, 1.6))
                K.stand(b, p[0], p[1], z, 1.15, 1.15, hs_)
                K.tank_poly(b, p[0], p[1], z + hs_, tank_m())
            elif k < 0.75:
                hs_ = rng.choice((0.5, 0.8, 1.2))
                K.stand(b, p[0], p[1], z, 1.25, 1.25, hs_)
                K.tank_steel(b, rng, p[0], p[1], z + hs_, 0.0, rng.choice(('zinc', 'zinc_old', 'rust', 'tank_red')))
            else:
                hs_ = 0.3
                K.tank_lying(b, p[0], p[1], z, rng.choice((0.0, math.pi / 2.0)), rng.choice(('zinc', 'zinc_old', 'tank_red')))
            # its pipe: down from it, across the roof to the edge, and over (the pale lines every roof there has)
            i, j = c
            ex = xs[i] + 0.3 if p[0] - xs[i] < xs[i + 1] - p[0] else xs[i + 1] - 0.3
            sgn = 1.0 if ex > p[0] else -1.0
            ye = min(max(p[1] + 0.2 + rng.uniform(1.0, 2.5) * rng.choice((-1, 1)), self.Yl(j, lvl[c]) + 0.3), self.Yl(j + 1, lvl[c]) - 0.3)
            b.path([Vector((p[0] + sgn * 0.3, p[1] + 0.2, z + hs_ + 0.05)), Vector((p[0] + sgn * 0.62, p[1] + 0.2, z + hs_ - 0.1)), Vector((p[0] + sgn * 0.66, p[1] + 0.2, z + 0.05)),
                    Vector((ex, p[1] + 0.2, z + 0.05)), Vector((ex, ye, z + 0.05))], 0.028, rng.choice(('plastic_white', 'plastic_white', 'zinc_old')), n=4)
        for _ in range(rng.choice((0, 1, 1, 2, 2, 3, 4))):          # coolers, in ones and twos: the white boxes of every roof there
            c = pick()
            p = spot(c, lvl[c], 0.75)
            if p:
                K.cooler(b, p[0], p[1], zf[lvl[c]], rng.choice((0.0, math.pi / 2.0, math.pi, -math.pi / 2.0)))
        if rng.random() < (0.85 if self.low else 0.65):             # washing
            c = max(main, key=lambda q: (xs[q[0] + 1] - xs[q[0]]) * (self.ys[q[1] + 1] - self.ys[q[1]]) * rng.uniform(0.6, 1.0))
            i, j = c
            L = lvl[c]
            x0, x1, y0, y1 = xs[i] + 0.6, xs[i + 1] - 0.6, self.Yl(j, L) + 0.7, self.Yl(j + 1, L) - 0.7
            if x1 - x0 > 1.6 and y1 - y0 > 0.4:
                y = rng.uniform(y0, y1)
                if (i + 1, j) in lvl and lvl[(i + 1, j)] == L and rng.random() < 0.6:
                    x1 = xs[i + 2] - 0.6                            # across two bays
                K.washing(b, rng, (x0, y), (x1, y), zf[L], lines=rng.choice((1, 2, 2)))
                taken.append(((x0 + x1) / 2.0, y, (x1 - x0) / 2.0))
        for kind, pr in (('solar', 0.16), ('bed', 0.22), ('table', 0.14), ('shade', 0.18), ('junk', 0.6), ('junk', 0.35), ('blocks', 0.14), ('antenna', 0.4), ('bed', 0.1),
                         ('junk', 0.15)):
            if rng.random() > pr:
                continue
            c = pick()
            L = lvl[c]
            z = zf[L]
            if kind == 'shade':
                p = spot(c, L, 1.5)
                if p:
                    K.shade(b, rng, p[0] - 1.3, p[1] - 1.1, p[0] + 1.3, p[1] + 1.1, z)
                    if rng.random() < 0.6:
                        K.table_and_chairs(b, rng, p[0], p[1], z)
                continue
            p = spot(c, L, {'solar': 1.3, 'bed': 1.1, 'table': 1.1, 'junk': 1.0, 'blocks': 0.9, 'antenna': 0.2}[kind])
            if not p:
                continue
            if kind == 'solar':
                K.solar_heater(b, p[0], p[1], z, math.pi)
            elif kind == 'bed':
                K.bed(b, rng, p[0], p[1], z, rng.choice((0.0, math.pi / 2.0)) + rng.uniform(-0.1, 0.1))
            elif kind == 'table':
                K.table_and_chairs(b, rng, p[0], p[1], z)
            elif kind == 'junk':
                K.junk(b, rng, p[0], p[1], z)
            elif kind == 'blocks':
                K.block_pile(b, rng, p[0], p[1], z, rng.uniform(0.0, 1.5))
            else:
                K.antenna(b, rng, p[0], p[1], z)
        for _ in range(rng.choice((1, 1, 2, 2, 3))):                # where the dishes stand (the town turns them all one way)
            c = pick()
            p = spot(c, lvl[c], 0.55)
            if p:
                self.anchors.append((p[0], p[1], zf[lvl[c]]))
        for _ in range(rng.randrange(1, 3)):                        # a vent, a soil pipe's head
            c = pick()
            p = spot(c, lvl[c], 0.15, edge='corner')
            if p:
                b.tube((p[0], p[1], zf[lvl[c]]), (p[0], p[1], zf[lvl[c]] + rng.uniform(0.5, 0.9)), 0.05, 'zinc_old', n=6)
        if rng.random() < 0.3 and F in self.roofs:                  # the next storey's columns, begun: all round the roof's edge
            for i in range(self.nb + 1):
                for j in range(self.nd + 1):
                    around = [(i + di, j + dj) for di in (-1, 0) for dj in (-1, 0)]
                    if not any(c in self.roofs[F] for c in around) or any(c in self.n1 and self.n1[c] > F for c in around):
                        continue
                    if rng.random() < 0.8:
                        cx = min(max(xs[i], 0.36), self.w - 0.36)
                        cy = min(max(self.Yl(j, F), self.Yl(0, F) + 0.36), self.d - 0.36)
                        K.stub(b, rng, cx, cy, zf[F], rng.uniform(0.5, 1.3))
        for (L, pts, closed, hp) in getattr(self, '_par', []):     # a carpet aired over a parapet
            if L <= F and rng.random() < 0.22 and len(pts) >= 2:
                k = rng.randrange(len(pts) - 1)
                a, c = Vector(pts[k]), Vector(pts[k + 1])
                if (c - a).length > 2.6:
                    u = (c - a).normalized()
                    K.rug_over(b, rng, a.lerp(c, rng.uniform(0.3, 0.7)), u, (u.y, -u.x), zf[L] + hp + 0.06, 0.2)

    # ------------------------------------------------------------------------------------------ in the opened rooms
    def _insides(self):
        b, rng, xs, zf = self.b, self.rng, self.xs, self.zf
        for (c, f) in sorted(self.opened):
            i, j = c
            x0, x1, y0, y1 = xs[i] + 0.2, xs[i + 1] - 0.2, self.Y(j, f) + 0.2, self.Y(j + 1, f) - 0.2
            if rng.random() < 0.75:
                K.furniture(b, rng, x0, y0, x1, y1, zf[f], zf[f + 1] - zf[f] - SLAB)
            # along each wall that went: a band of what it was, lying on the floor's very edge and over it (an open
            # floor carries its wall as a ridge of rubble along its lip)
            X0, X1, Y0, Y1 = xs[i] + 0.04, xs[i + 1] - 0.04, self.Y(j, f) + 0.04, self.Y(j + 1, f) - 0.04
            for sd, s in self.slots_of(c).items():
                if self.wst.get((f,) + s) not in ('hole', 'gone'):
                    continue
                if sd in 'SN':
                    yy = Y0 + 0.4 if sd == 'S' else Y1 - 0.4
                    K.heap(b, rng, (X0 + X1) / 2.0, yy, (X1 - X0) / 2.0 * rng.uniform(0.75, 1.0), rng.uniform(0.6, 1.0), rng.uniform(0.3, 0.6), zf[f],
                           pieces=rng.randrange(10, 18), paints=(self.PL, self.paint(c, f)), clip=(X0, Y0, X1, Y1), field=False, over=0.3)
                else:
                    xx = X0 + 0.4 if sd == 'W' else X1 - 0.4
                    K.heap(b, rng, xx, (Y0 + Y1) / 2.0, rng.uniform(0.6, 1.0), (Y1 - Y0) / 2.0 * rng.uniform(0.75, 1.0), rng.uniform(0.3, 0.6), zf[f],
                           pieces=rng.randrange(10, 18), paints=(self.PL, self.paint(c, f)), clip=(X0, Y0, X1, Y1), field=False, over=0.3)
        for c in self.cells:                                        # on a floor that is the top now: what fell onto it
            n = self.n1[c]
            if n >= self.n0[c] or n < 1:
                continue
            i, j = c
            x0, x1, y0, y1 = xs[i] + 0.25, xs[i + 1] - 0.25, self.Yl(j, n) + 0.25, self.Yl(j + 1, n) - 0.25
            lost = self.n0[c] - n
            K.heap(b, rng, (x0 + x1) / 2.0 + rng.uniform(-0.4, 0.4), (y0 + y1) / 2.0 + rng.uniform(-0.4, 0.4), (x1 - x0) * 0.46, (y1 - y0) * 0.46,
                   min(1.5, 0.35 + 0.3 * lost), zf[n], pieces=rng.randrange(12, 22), plates=rng.randrange(1, 3), paints=(self.PL, self.paint(c, n)),
                   clip=(x0, y0, x1, y1), field=False, plate_top='roof_dmg')
            if self.cap1.get(c) == 'roofless' and rng.random() < 0.5:
                K.furniture(b, rng, x0, y0, x1, y1, zf[n], 2.9)

    # ------------------------------------------------------------------------------------------ at its foot
    def _fallen(self):
        b, rng, xs, zf = self.b, self.rng, self.xs, self.zf
        down = [c for c in self.cells if self.n1[c] < self.n0[c]]
        if down and self.dmg in (2, 3):
            vol = sum((self.n0[c] - self.n1[c]) * (1.0 if self.n1[c] == 0 else 0.35) for c in down)
            gx = sum((xs[c[0]] + xs[c[0] + 1]) / 2.0 for c in down) / len(down)
            gy = sum((self.ys[c[1]] + self.ys[c[1] + 1]) / 2.0 for c in down) / len(down)
            ex = max(xs[c[0] + 1] for c in down) - min(xs[c[0]] for c in down)
            ey = max(self.ys[c[1] + 1] for c in down) - min(self.ys[c[1]] for c in down)
            gx += (gx - self.w / 2.0) * 0.25                        # it spills outward, away from what still stands
            gy += (gy - self.d / 2.0) * 0.25
            rx, ry = ex / 2.0 + rng.uniform(1.6, 2.8), ey / 2.0 + rng.uniform(1.6, 2.8)
            h = min(4.6, 0.9 + 0.55 * vol ** 0.65, 0.55 * min(rx, ry))
            K.heap(b, rng, gx, gy, rx, ry, h, 0.0, pieces=int(30 + 10 * rx * ry ** 0.5), plates=rng.randrange(3, 7),
                   paints=(self.PL, PAINTS[self.seed % 7], PAINTS[(self.seed + 3) % 7]), plate_top='floor')
            for c in down:                                          # the floors that came down, one on another
                if self.n1[c] != 0:
                    continue
                cx, cy = (xs[c[0]] + xs[c[0] + 1]) / 2.0, (self.ys[c[1]] + self.ys[c[1] + 1]) / 2.0
                hz = h * (1.0 - K.smooth(min(1.0, math.hypot((cx - gx) / rx, (cy - gy) / ry)))) ** 1.1
                for k in range(min(self.n0[c], 4)):
                    last = k == min(self.n0[c], 4) - 1
                    K.slab_piece(b, rng, (cx + rng.uniform(-0.8, 0.8), cy + rng.uniform(-0.8, 0.8), hz + 0.25 + 0.4 * k),
                                 (xs[c[0] + 1] - xs[c[0]]) * rng.uniform(0.7, 1.0), (self.ys[c[1] + 1] - self.ys[c[1]]) * rng.uniform(0.7, 1.0),
                                 0.3, 'roof_dmg' if last else 'floor', rz=rng.uniform(-0.3, 0.3))
        if self.blown is not None:                                  # under a blown front: its walls, on the pavement
            k0, k1, f0 = self.blown
            cx = (xs[k0] + xs[k1 + 1]) / 2.0
            n_f = self.F - f0
            K.heap(b, rng, cx + rng.uniform(-0.6, 0.6), -1.2, (xs[k1 + 1] - xs[k0]) / 2.0 + rng.uniform(0.8, 1.8), rng.uniform(2.0, 3.0), min(2.2, 0.5 + 0.35 * n_f), 0.0,
                   pieces=int(26 + 8 * (k1 - k0 + 1) * n_f), plates=rng.randrange(2, 5), paints=(self.PL, self.PL, PAINTS[self.seed % 7]), plate_top=self.PL)
        if self.dmg == 4:
            pass

    def mesh(self, name, material):
        return self.b.mesh(name, material)
