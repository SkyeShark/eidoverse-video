"""eidoblend.props.houseplants.plants: three houseplants, each its species, in real pots, and a watering can (Blender).
Millimetres in every table, the scene in metres; x across, y back, z up (a plant faces -y).

    from eidoblend.props.hardsurface import masses as hs
    from eidoblend.props.houseplants import plants as P
    hs.start('plants', orient=False)
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    g = P.Garden()                                   # what stands; bounds(x, y, z) mm -> True where a leaf may go
    P.rubber_plant(g, 0.0, 0.0, clay)                # Ficus elastica: three stems in a glazed pot
    P.monstera(g, 700.0, 0.0, clay)                  # Monstera deliciosa on a coir pole, a terracotta pot and saucer
    P.corn_plant(g, -700.0, 0.0, clay)               # Dracaena fragrans 'Massangeana': three canes in a fibre-clay planter
    P.watering_can(300.0, -400.0, 0.0, clay, toward=90.0)

THE SPECIES:
  RUBBER PLANT, Ficus elastica: thick oval leaves in a spiral up an unbranched stem, the young ones steep, the old ones
      level; each blade a boat folded at a pale midrib with an abrupt drip tip; the new leaf's red sheath a spear at
      each stem's top. Three stems of three heights in one glazed stoneware pot, as they are sold.
  MONSTERA, Monstera deliciosa: blades HANGING from long petioles, slit from the margin between the veins, a few holes
      by the midrib; the stem climbing a coir pole (coconut fibre bound with a spiral thread), petioles sheathing the
      stem, two aerial roots down into the soil, green wire ties; a thrown terracotta pot on its saucer.
  CORN PLANT, Dracaena fragrans 'Massangeana': ringed canes as thick as a wrist, cut flat at staggered heights, each top
      putting out shoots in their dry sheaths, each shoot a fountain of soft strap leaves a hand wide that arch, crease
      and twist; a top dressing of expanded-clay pebbles in a tapered fibre-clay planter.
HOW: growth as parameters, young at the tip; leaves are thin CURVED SOLIDS (kit.Skin: the midrib sunk above and proud
beneath); no mirror twins, no even spacing; every blade placed by its plant's own rule, then asked whether it would pass
through a blade, a stem or a cane already standing in the Garden, or leave its bounds, and turned until it does not.
The leaves carry 'leafdata' (along, across, which leaf, age; the underside's age below zero) and 'leafq' (the vein's
field) for their material (houseplants.look). Parts are named <prefix>_<part> (plant_rubber_leaves, plant_monstera_pole
...), so a look finds them by name.
"""

import bisect
import math

import bmesh
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

from ..hardsurface import masses as hs
from . import kit as K

V3 = K.V3
ZUP = V3(0, 0, 1)
MM = hs.MM


def polar(az, el):
    """a unit vector: azimuth from the front (-y) turning toward +x, elevation above the floor (degrees)"""
    a, e = math.radians(az), math.radians(el)
    return V3(math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))


def az_el(d):
    return math.degrees(math.atan2(d.x, -d.y)), math.degrees(math.asin(max(-1.0, min(1.0, d.z))))


class Garden:
    """What already stands, for the blades placed after it: stems, canes, poles and blades as one BVH. bounds(x, y, z)
    (mm) -> True where a blade may be; the default keeps blades off the floor (z >= floor + 30 mm). One Garden for
    several plants makes each plant's blades clear the others'."""

    def __init__(self, bounds=None, floor=0.0):
        self.V, self.F, self.bvh = [], [], None
        self.turned = self.crossing = self.torn = 0
        self.bounds = bounds or (lambda x, y, z, f=floor: z >= f + 30.0)

    def stand_faces(self, vs, fs):
        base = len(self.V)
        self.V.extend(vs)
        self.F.extend(tuple(base + i for i in f) for f in fs)
        if self.F:
            self.bvh = BVHTree.FromPolygons(self.V, self.F)

    def stand_rings(self, rl, every=1):
        """a stem, a cane or a pole stands: its rings (mm), as what a blade may not pass through"""
        rl = rl[::every] + ([rl[-1]] if (len(rl) - 1) % every else [])
        n = len(rl[0])
        vs = [Vector(p) * MM for r in rl for p in r]
        self.stand_faces(vs, [(i * n + k, i * n + (k + 1) % n, (i + 1) * n + (k + 1) % n, (i + 1) * n + k)
                              for i in range(len(rl) - 1) for k in range(n)])

    def crosses(self, skin, keep=None):
        """how many face pairs of this blade pass through what already stands"""
        if self.bvh is None:
            return 0
        vs, fs = skin.proxy(keep)
        return len(BVHTree.FromPolygons(vs, fs).overlap(self.bvh)) if fs else 0

    def within(self, skin):
        return all(self.bounds(v.co.x * 1e3, v.co.y * 1e3, v.co.z * 1e3) for v in skin.bm.verts)

    def choose(self, make, tries, keep=None):
        """the first of the tries (each a dict of changes to the blade as first meant) that stays in bounds and passes
        through nothing; failing that, the one that crosses least -> the skin (now standing)"""
        best = None
        for k, tr in enumerate(tries):
            sk = make(**tr)
            if not self.within(sk):
                sk.bm.free()
                continue
            c = self.crosses(sk, keep)
            if c == 0:
                if best:
                    best[1].bm.free()
                self.turned += int(k > 0)
                self.stand_faces(*sk.proxy(keep))
                return sk
            if best is None or c < best[0]:
                if best:
                    best[1].bm.free()
                best = (c, sk)
            else:
                sk.bm.free()
        if best is None:                                        # (nothing stays in bounds: the first, and it is said)
            best = (1, make(**tries[0]))
            print('[houseplants] a blade leaves its bounds', tries[0])
        self.crossing += 1
        self.stand_faces(*best[1].proxy(keep))
        return best[1]


def close_leaves(name, into, clay, sharp=55.0):
    return K.soft(hs.obj(name, into), clay, sharp=sharp)


# ------------------------------------------------------------------------------------- a blade with one midrib
# 31 stations along a blade, closer together where the outline turns most (by the petiole and at the tip)
SS = (0.0, 0.008, 0.02, 0.04, 0.065, 0.095, 0.13, 0.17, 0.215, 0.265, 0.32, 0.38, 0.44, 0.5, 0.56, 0.62, 0.675, 0.725, 0.77, 0.81, 0.845, 0.875, 0.9, 0.922, 0.94, 0.955,
      0.967, 0.977, 0.985, 0.992, 1.0)
VS = (-1.0, -0.88, -0.7, -0.5, -0.3, -0.14, -0.045, 0.0, 0.045, 0.14, 0.3, 0.5, 0.7, 0.88, 1.0)


def blade(p0, az, el, L, W, outline, bend=20.0, bend_pow=1.4, kink=None, side=0.0, roll=0.0, twist=0.0, fold=(20.0, 10.0), cup=0.4,
          wave=(0.0, 2.0, 0.0), th=0.6, rib=(0.0, 3.0), groove=(0.0, 2.0), drip=0.0, ident=0.0, age=0.0, ss=SS, vs=VS):
    """a leaf blade as ONE skin. Its midrib leaves p0 toward (az, el) and bends DOWN by `bend` degrees along its length
    (as s ** bend_pow; kink (where, share, half-width): part of the bend gathered into a crease), swings sideways by
    `side`, and the blade rolls about its midrib (roll, then `twist` more by the tip). Across: each half rises from
    the midrib at fold[0] (base) .. fold[1] (tip) degrees and flattens by `cup` toward its margin; the margin waves
    (wave: mm, how many waves, phase). th: thickness; rib (mm proud beneath, half-width); groove (mm sunk above, half-
    width); drip: the last 7 % bent down this much more."""
    sk = K.Skin()
    axis = ZUP.cross(polar(az, 0.0)).normalized()               # a positive turn about it pitches a forward vector DOWN
    d0, n0 = polar(az, el), polar(az, el + 90.0)

    def frame(s):
        g = s ** bend_pow
        if kink:
            g = (1.0 - kink[1]) * g + kink[1] * K.smooth(s, kink[0] - kink[2], kink[0] + kink[2])
        q_ = Quaternion(ZUP, math.radians(-side * s)) @ Quaternion(axis, math.radians(bend * g + drip * K.smooth(s, 0.93, 1.0)))
        t = q_ @ d0
        return t, Quaternion(t, math.radians(roll + twist * s)) @ (q_ @ n0)
    p, rows, prev = Vector(p0), [], 0.0
    hw = W / 2.0
    for s in ss:
        if s > prev:
            p = p + frame((s + prev) / 2.0)[0] * (L * (s - prev))
            prev = s
        t, n = frame(s)
        b = t.cross(n)
        w = hw * K.table(outline, s)
        f0 = math.radians(K.lerp(fold[0], fold[1], s))
        k_ = -f0 * cup / w if w > 1e-6 else 0.0
        row = []
        for v in vs:
            q = w * abs(v)
            if abs(k_) > 1e-9:
                a_, c_ = (math.sin(f0 + k_ * q) - math.sin(f0)) / k_, (math.cos(f0) - math.cos(f0 + k_ * q)) / k_
            else:
                a_, c_ = q * math.cos(f0), q * math.sin(f0)
            rel = q / hw
            lift = c_ + wave[0] * math.sin(2.0 * math.pi * (wave[1] * s + wave[2] + (0.27 if v < 0 else 0.0))) * rel * rel
            lift -= groove[0] * math.exp(-(q / groove[1]) ** 2) * (1.0 - 0.7 * s)
            P = p + b * (a_ if v >= 0 else -a_) + n * lift
            row.append(sk.point(P, th / 2.0, th / 2.0 + rib[0] * math.exp(-(q / rib[1]) ** 2) * (1.0 - 0.75 * s), (s, 0.5 + 0.5 * v, ident, age), n))
        rows.append(row)
    sk.grid(rows)
    return sk


# ------------------------------------------------------------------------------------------ pots, soil, pebbles
def pebbles(name, at, r, z, seed, clay, lo=9.5, hi=16.0, avoid=()):
    """a top dressing of expanded-clay pebbles: one bed of them shoulder to shoulder, a few lying on the bed (small
    detached pieces, smooth-faced, in a few sizes, seated: none through the pot's wall or in a cane)"""
    bm = bmesh.new()
    pitch, row, k = (lo + hi) * 0.5 * 0.96, 0, 0
    y = -r
    while y <= r:
        x = -r + (pitch * 0.5 if row % 2 else 0.0)
        while x <= r:
            k += 1
            for layer in (0, 1):
                if layer and K.hash01(k, seed, 9) > 0.2:
                    continue
                rr = K.lerp(lo, hi, K.hash01(k, seed, layer)) * 0.5
                px, py = x + K.sgn01(k, seed, 2 + layer) * pitch * 0.22, y + K.sgn01(k, seed, 4 + layer) * pitch * 0.22
                if math.hypot(px, py) > r - rr - 1.0 or any(math.hypot(px - ax, py - ay) < ar + rr * 0.5 for ax, ay, ar in avoid):
                    continue
                sq = Matrix.Diagonal((1.0, 0.82 + 0.16 * K.hash01(k, seed, 6), 0.7 + 0.2 * K.hash01(k, seed, 7), 1.0))
                ro = Quaternion(V3(K.sgn01(k, seed, 11), K.sgn01(k, seed, 12), K.sgn01(k, seed, 13) + 1e-3).normalized(), K.hash01(k, seed, 14) * 6.283).to_matrix().to_4x4()
                at_ = Vector(at) + V3(px, py, z + rr * 0.45 + layer * (lo + hi) * 0.33 + K.sgn01(k, seed, 15) * 1.2)
                bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rr * MM, matrix=Matrix.Translation(at_ * MM) @ ro @ sq)
            x += pitch
        y += pitch * 0.866
        row += 1
    return K.soft(hs.obj(name, bm), clay, sharp=80.0)


# a thrown terracotta pot: a tapered wall, a rim band 50 deep that steps out, a rounded lip, a drain hole; (radius,
# height) from its own foot, a closed profile
TERRACOTTA = [(12.0, 0.0), (93.0, 0.0), (97.0, 4.0), (139.5, 212.0), (141.0, 214.0), (149.0, 216.0), (151.0, 221.0), (152.0, 258.0), (151.0, 263.0), (148.0, 265.0),
              (144.0, 265.0), (141.0, 263.0), (140.0, 258.0), (87.0, 14.0), (84.0, 12.0), (12.0, 12.0)]
SAUCER = [(0.0, 0.0), (126.0, 0.0), (130.0, 3.0), (160.0, 33.0), (160.0, 36.0), (157.0, 37.0), (152.0, 36.0), (124.0, 9.0), (0.0, 9.0)]
# a glazed stoneware cylinder on a foot ring, its plant still in the grower's pot inside it (the liner's rim shows)
GLAZED = [(0.0, 6.0), (118.0, 6.0), (120.0, 0.0), (142.0, 0.0), (150.0, 6.0), (152.0, 16.0), (160.0, 292.0), (159.0, 298.0), (155.0, 300.0), (151.0, 299.0),
          (149.0, 294.0), (141.5, 22.0), (136.0, 16.0), (0.0, 16.0)]
LINER = [(141.2, 200.0), (143.5, 278.0), (147.0, 280.0), (148.0, 283.0), (146.5, 285.0), (143.0, 285.5), (141.5, 284.0), (142.3, 278.0), (140.0, 200.0)]
# a large tapered planter of fibre clay with a broad flat rim
PLANTER = [(0.0, 5.0), (128.0, 5.0), (130.0, 0.0), (148.0, 0.0), (152.0, 5.0), (198.0, 372.0), (199.0, 378.0), (197.0, 380.0), (180.0, 380.0), (177.0, 378.0),
           (176.0, 372.0), (135.0, 20.0), (130.0, 16.0), (0.0, 16.0)]


# ------------------------------------------------------------------------------------------------ the rubber plant
FICUS = [(0.0, 0.0), (0.012, 0.11), (0.03, 0.2), (0.06, 0.34), (0.1, 0.52), (0.15, 0.68), (0.21, 0.82), (0.28, 0.92), (0.35, 0.975), (0.42, 1.0), (0.5, 0.99), (0.58, 0.95),
         (0.65, 0.88), (0.72, 0.78), (0.79, 0.64), (0.85, 0.5), (0.9, 0.36), (0.935, 0.24), (0.96, 0.13), (0.978, 0.065), (0.99, 0.03), (1.0, 0.0)]


def rubber_plant(g, cx, cy, clay, z0=0.0, N='plant_rubber'):
    """Ficus elastica, its pot standing at (cx, cy, z0) mm: parts <N>_pot, _pot_liner, _soil, _leaves, _stems"""
    K.soft(hs.revolve(N + '_pot', GLAZED, at=V3(cx, cy, z0), seg=72), clay)
    K.soft(hs.revolve(N + '_pot_liner', LINER, at=V3(cx, cy, z0), seg=72, closed=True), clay)
    soil = z0 + 268.0
    # three stems in the one pot, of three heights, each leaning a little out of the group; stout stems, leaves a
    # quarter of a metre long and half as wide, close set
    stems = (dict(at=(-34.0, 26.0), h=1160.0, lean=(-150.0, 3.0), bare=0.2, L=272.0, turn=20.0, seed=11),
             dict(at=(42.0, 6.0), h=900.0, lean=(75.0, 5.0), bare=0.22, L=258.0, turn=140.0, seed=12),
             dict(at=(-10.0, -44.0), h=640.0, lean=(-10.0, 6.5), bare=0.18, L=240.0, turn=260.0, seed=13))
    K.soft(K.lumps(N + '_soil', (cx, cy, z0), 142.0, soil, soil - 70.0, 3.5, 14.0, 5, rings=24, seg=80, crown=5.0,
                   hole=[(s['at'][0], s['at'][1], 20.0) for s in stems]), clay, sharp=80.0)
    into, limbs, grown = bmesh.new(), [], []
    for j, st in enumerate(stems):                              # the stems first: a blade may not pass through any of them
        base = V3(cx + st['at'][0], cy + st['at'][1], soil - 40.0)
        out = polar(st['lean'][0], 0.0)
        H = st['h'] + 40.0
        path = [base + ZUP * (H * u) + out * (st['h'] * math.tan(math.radians(st['lean'][1])) * u ** 1.4)
                + polar(st['lean'][0] + 90.0, 0.0) * (7.0 * math.sin(2.6 * u + j)) for u in [i / 40.0 for i in range(41)]]
        # the leaves' nodes: none on the bare foot (their scars are rings there), closer together toward the tip
        zs, z = [], st['h']
        while z > st['h'] * st['bare']:
            zs.append(z)
            z -= 28.0 + 22.0 * min(1.0, (st['h'] - z) / 240.0) + 5.0 * K.sgn01(len(zs), st['seed'])
        scars = []
        while z > 50.0:
            scars.append(z)
            z -= 48.0 + 8.0 * K.sgn01(len(scars), st['seed'], 3)

        def radius(s, zs=zs, scars=scars, H=H):
            z_ = s * H - 40.0
            r = K.lerp(11.5, 5.2, max(0.0, z_ / (H - 40.0)) ** 0.85)
            return r * (1.0 + 0.11 * sum(math.exp(-((z_ - zn) / 2.4) ** 2) for zn in zs + scars))
        rl = K.limb_rings(K.resample(path, 5.0), radius, seg=14, caps=(0.0, 0.5))
        limbs.append(rl)
        g.stand_rings(rl, every=6)
        grown.append((st, path, zs, radius, H))
    for j, (st, path, zs, radius, H) in enumerate(grown):
        def at_height(z_, path=path, H=H):
            f = (z_ + 40.0) / H * 40.0
            i = min(39, int(f))
            return path[i].lerp(path[i + 1], f - i), (path[i + 1] - path[i]).normalized()
        n = len(zs)
        for k, zk in enumerate(zs):
            u = k / max(1, n - 1)                              # 0 the newest leaf at the tip, 1 the oldest
            az = st['turn'] + k * 137.5 + 9.0 * K.sgn01(k, st['seed'], 1)
            el = K.lerp(64.0, 6.0, K.smooth(u) ** 0.9) + 5.0 * K.sgn01(k, st['seed'], 2)
            grow = (0.5, 0.8)[k] if k < 2 else 1.0 - 0.17 * u + 0.05 * K.sgn01(k, st['seed'], 4)
            L = st['L'] * grow
            W = L * (0.54 + 0.03 * K.sgn01(k, st['seed'], 5))
            lp = (34.0 + 24.0 * min(1.0, 2.0 * u)) * (0.75 if k < 2 else 1.0)
            c = at_height(zk)[0]
            rs = radius((zk + 40.0) / H)

            def make(daz=0.0, d_el=0.0, k=k, u=u, az=az, el=el, L=L, W=W, lp=lp, c=c, rs=rs, j=j):
                a = az + daz
                e = max(-12.0, el + d_el)
                tip = c + polar(a, 0.0) * (rs - 1.5) + polar(a, e + 6.0) * lp
                sk = blade(tip, a, e - 3.0, L, W, FICUS, bend=10.0 + 44.0 * u + 8.0 * K.sgn01(k, j, 6), bend_pow=1.3, side=10.0 * K.sgn01(k, j, 7),
                           roll=11.0 * K.sgn01(k, j, 8), twist=6.0 * K.sgn01(k, j, 9), fold=(K.lerp(21.0, 10.0, u), K.lerp(11.0, 5.0, u)), cup=0.45,
                           wave=(1.6 + 1.6 * u, 2.2, K.hash01(k, j, 10)), th=0.9, rib=(1.6, 2.8), groove=(0.55, 2.4), drip=38.0, ident=K.hash01(k, j, 21), age=u)
                sk.petiole = (c + polar(a, 0.0) * (rs - 2.5), tip, a, e)
                return sk
            sk = g.choose(make, [dict(daz=d, d_el=e_) for e_ in (0.0, 8.0, -8.0) for d in (0.0, 16.0, -16.0, 32.0, -32.0, 48.0, -48.0)])
            p_a, p_b, a, e = sk.petiole
            limbs.append(K.limb_rings(K.resample([p_a, p_a.lerp(p_b, 0.5) + ZUP * 1.6, p_b + polar(a, e - 3.0) * 4.0], 4.0),
                                      lambda s: 3.5 - 0.6 * s + 1.1 * math.exp(-(s / 0.12) ** 2), seg=10, caps=(0.0, 0.7)))
            g.torn += K.thicken(sk, into)
        # the new leaf's sheath: a spear standing on the stem's tip, leaning with the youngest leaf
        tip, tt = at_height(st['h'])
        sd = (tt + polar(st['turn'] + 170.0, 0.0) * 0.16).normalized()
        sl = 96.0 + 30.0 * K.hash01(j, 77)
        limbs.append(K.limb_rings([tip - sd * 4.0 + sd * (sl * i / 14.0) + polar(st['turn'] + 170.0, 0.0) * (5.0 * (i / 14.0) ** 2) for i in range(15)],
                                  lambda s: 0.5 + 4.6 * (1.0 - s) ** 0.8 * (0.82 + 0.18 * math.sin(3.1 * s)), seg=10, caps=(0.0, 0.9)))
    close_leaves(N + '_leaves', into, clay)
    K.soft(hs.skins(N + '_stems', limbs), clay, sharp=60.0)


# --------------------------------------------------------------------------------------------------- the monstera
# one blade in units of its midrib (the petiole's junction to the tip): a heart wider than its midrib is long, its two
# basal lobes reaching a third of a midrib BEHIND the junction. The half outline, from the far end of the sinus' edge
# round to the tip:
MON_OUT = ((-0.26, 0.045), (-0.32, 0.11), (-0.345, 0.2), (-0.31, 0.31), (-0.22, 0.42), (-0.08, 0.51), (0.1, 0.575), (0.28, 0.59), (0.45, 0.555), (0.62, 0.475),
           (0.77, 0.36), (0.89, 0.22), (0.96, 0.1), (1.0, 0.0))
MON_EDGES = (0.0, 0.2, 0.335, 0.47, 0.605, 0.74, 1.0)          # where one primary vein's field ends and the next begins, along the outline
MON_Q = (-1.0, -0.95, -0.86, -0.7, -0.45, -0.15, 0.15, 0.45, 0.7, 0.86, 0.95, 1.0)      # (twelve rays a field: a tongue's end stays round)
MON_T = (0.0, 0.02, 0.05, 0.085, 0.12, 0.145, 0.17, 0.2, 0.23, 0.255, 0.28, 0.32, 0.37, 0.42, 0.47, 0.52, 0.57, 0.63, 0.69, 0.75, 0.81, 0.87, 0.92, 0.96, 0.985, 1.0)
MON_LINE = K.spline([V3(x, y, 0.0) for x, y in MON_OUT], 10)
MON_ACC = K.arc_lengths(MON_LINE)


def mon_outline(a):
    """the half outline at the share a of its own length (unit midrib)"""
    d = a * MON_ACC[-1]
    j = max(0, min(len(MON_LINE) - 2, bisect.bisect_left(MON_ACC, d) - 1))
    seg = MON_ACC[j + 1] - MON_ACC[j]
    p = MON_LINE[j].lerp(MON_LINE[j + 1], (d - MON_ACC[j]) / seg if seg > 1e-12 else 0.0)
    return p.x, p.y


def mon_vein(a):
    """a ray of the blade: (where it leaves the midrib, its end on the outline: x, y), unit midrib. The basal veins all
    leave the junction; further on a vein leaves the midrib at 80 degrees, falling to 38 by the tip. The same for both
    sides of a blade, so its two halves are one sheet along the midrib."""
    ox, oy = mon_outline(a)
    if ox <= 0.12:
        return 0.0, ox, oy
    phi = math.radians(80.0 - 42.0 * K.smooth((ox - 0.12) / 0.88))
    return min(1.0, max(0.0, ox - oy / math.tan(phi))), ox, oy


def monstera_blade(J, az, el, L, cuts, roll=0.0, bend=14.0, ears_up=6.0, drop=12.0, wide=(1.0, 1.0), droop=(), ident=0.0, age=0.0, seed=0):
    """a Monstera blade as ONE skin. J: where the petiole meets it; its midrib leaves J toward (az, el) (el below zero:
    it hangs). The blade is a fan of RAYS, each from the midrib out to the margin along a vein's direction; a ray that
    runs between two veins' fields is where the blade slits and where it is holed: there the two fields' edges are one
    edge until the hole or the slit opens (so the blade is one sheet). cuts: {(side, edge index): (t_in or None, half
    gap mm, flare, hole or None)}: the slit from t_in (0 the midrib, 1 the margin) to the margin, its half-width, how
    it widens (+) or closes (-) toward the margin; hole: (t0, t1, half-width mm). wide: each side's width; droop: how
    far each field's free tongue hangs (degrees), by field. The blade is nearly flat and smooth: it swells a little
    between its veins, and its midrib lies in a broad shallow channel."""
    sk = K.Skin()
    t0 = polar(az, el)
    n0 = Quaternion(t0, math.radians(roll)) @ polar(az, el + 90.0)
    b0 = t0.cross(n0)
    # the midrib's own curve: it droops toward the tip, and BEHIND the junction the basal lobes rise (a shallow funnel
    # round the petiole): frames along it, by x in mm
    XS = [(-0.42 + 1.46 * i / 80.0) * L for i in range(81)]

    def pitch(x):
        return bend * (x / L) ** 1.5 if x >= 0.0 else ears_up * (-x / (0.35 * L)) ** 1.5
    i0 = min(range(81), key=lambda i: abs(XS[i]))
    T = [Quaternion(b0, -math.radians(pitch(x))) @ t0 for x in XS]
    NN = [Quaternion(b0, -math.radians(pitch(x))) @ n0 for x in XS]
    C = [None] * 81
    C[i0] = Vector(J) - t0 * XS[i0]
    for i in range(i0 + 1, 81):
        C[i] = C[i - 1] + (T[i - 1] + T[i]) * (0.5 * (XS[i] - XS[i - 1]))
    for i in range(i0 - 1, -1, -1):
        C[i] = C[i + 1] - (T[i + 1] + T[i]) * (0.5 * (XS[i + 1] - XS[i]))

    def on_spine(x):
        f = min(79.999, max(0.0, (x / L + 0.42) / 1.46 * 80.0))
        i = int(f)
        return C[i].lerp(C[i + 1], f - i), NN[i].lerp(NN[i + 1], f - i).normalized()

    def gap(cut, t):
        if cut is None:
            return 0.0
        tin, g_, flare, hole = cut
        h = 0.0
        if tin is not None and t > tin:
            u = (t - tin) / 0.07
            h = g_ * (math.sqrt(max(0.0, 1.0 - (1.0 - u) ** 2)) if u < 1.0 else 1.0)
            h *= 1.0 + flare * max(0.0, t - tin - 0.07) / max(1e-6, 1.0 - tin - 0.07)
        if hole and hole[0] < t < hole[1]:
            tc, dt = (hole[0] + hole[1]) / 2.0, (hole[1] - hole[0]) / 2.0
            h = max(h, hole[2] * math.sqrt(max(0.0, 1.0 - ((t - tc) / dt) ** 2)))
        return h
    tins = sorted({c[0] for c in cuts.values() if c and c[0] is not None})
    TS = sorted(set(MON_T) | {round(t + d, 4) for t in tins for d in (0.008, 0.022)})       # (so a slit's inner end is ROUND, not a notch)
    f0, f1 = math.radians(3.0), math.radians(-drop)
    kf = (f1 - f0) / (0.59 * L)
    for sd, ws in ((1.0, wide[0]), (-1.0, wide[1])):
        for fi in range(len(MON_EDGES) - 1):
            aL, aR = MON_EDGES[fi], MON_EDGES[fi + 1]
            cL = cuts.get((sd, fi)) if fi > 0 else None
            cR = cuts.get((sd, fi + 1)) if fi + 1 < len(MON_EDGES) - 1 else None
            tinL = cL[0] if cL and cL[0] is not None else 1.0
            tinR = cR[0] if cR and cR[0] is not None else 1.0
            oL, oR = mon_outline(aL), mon_outline(aR)
            half = math.hypot(oR[0] - oL[0], (oR[1] - oL[1]) * ws) * L / 2.0
            dr = math.sin(math.radians(droop[fi] if fi < len(droop) else 0.0))
            rays = []
            for q in MON_Q:
                a = aL * (1.0 - q) / 2.0 + aR * (1.0 + q) / 2.0
                tin = tinL * (1.0 - q) / 2.0 + tinR * (1.0 + q) / 2.0
                v0, va, vb = mon_vein(a), mon_vein(min(1.0, a + 0.004)), mon_vein(max(0.0, a - 0.004))

                def R(v, t, ws=ws):
                    return (v[0] + (v[1] - v[0]) * t) * L, v[2] * t * L * ws
                x1_, y1_ = R(v0, 1.0)
                raylen = max(1e-6, math.hypot(x1_ - v0[0] * L, y1_))

                def corner(qq):
                    return 0.0 if qq <= 0.45 else 1.0 - math.sqrt(max(0.0, 1.0 - ((qq - 0.45) / 0.55) ** 2))
                tmax = max(0.5, 1.0 - (0.34 * half / raylen) * ((corner(-q) if tinL < 1.0 else 0.0) + (corner(q) if tinR < 1.0 else 0.0)))
                ray = []
                for t in TS:
                    tp = t if (t <= tin or tin >= 1.0) else tin + (t - tin) * (tmax - tin) / (1.0 - tin)
                    x, y = R(v0, tp)
                    xa, ya = R(va, tp)
                    xb, yb = R(vb, tp)
                    dl = math.hypot(xa - xb, ya - yb)
                    push = gap(cL, t) * (1.0 - q) / 2.0 - gap(cR, t) * (1.0 + q) / 2.0
                    if dl > 1e-9 and push:
                        x, y = x + (xa - xb) / dl * push, max(0.0, y + (ya - yb) / dl * push)
                    c3, n3 = on_spine(x)
                    lat, rise = (math.sin(f0 + kf * y) - math.sin(f0)) / kf, (math.cos(f0) - math.cos(f0 + kf * y)) / kf
                    u = max(0.0, (tp - tin) / (1.0 - tin)) if tin < 1.0 else 0.0
                    lift = rise + 0.006 * L * math.sin(math.pi * abs(q) / 2.0) ** 2 * K.smooth(t, 0.08, 0.3) * (1.0 - 0.5 * K.smooth(t, 0.8, 1.0))   # the blade swells between its veins (level across a field's edge: no crease)
                    lift -= dr * raylen * u * u                                                                              # a free tongue hangs
                    lift += 0.008 * L * math.sin(2.0 * math.pi * (5.5 * a + seed * 0.37 + (0.2 if sd < 0 else 0.0))) * t ** 3    # the margin is never flat
                    lift -= 0.0022 * L * math.exp(-(y / (0.022 * L)) ** 2)                                                   # the midrib's channel, above
                    P = c3 + b0 * (sd * lat) + n3 * lift
                    rib = 0.0085 * L * math.exp(-(y / (0.016 * L)) ** 2) * max(0.0, 1.0 - 0.62 * x / L)                      # and its ridge, beneath
                    ray.append(sk.point(P, 0.3, 0.3 + rib, (min(1.0, max(0.0, (x / L + 0.35) / 1.35)), 0.5 + sd * 0.5 * min(1.0, y / (0.6 * L)), ident, age), n3, q=q))
                rays.append(ray)
            for r0, r1 in zip(rays, rays[1:]):
                for j in range(len(TS) - 1):
                    sk.face((r0[j], r1[j], r1[j + 1], r0[j + 1]))
    return sk


def monstera_cuts(n_left, n_right, holes, L, seed):
    """which of a blade's five between-vein edges are slit on each side (a young blade none, a grown one all five),
    how deep, how wide; `holes`: how many of them carry a hole by the midrib as well"""
    order = {0: (), 1: (3,), 2: (2, 4), 3: (2, 3, 4), 4: (2, 3, 4, 5), 5: (1, 2, 3, 4, 5)}
    deep = {1: 0.52, 2: 0.42, 3: 0.37, 4: 0.42, 5: 0.47}
    cuts = {}
    for sd, n in ((1.0, n_left), (-1.0, n_right)):
        for e in range(1, 6):
            slit = e in order[n]
            hole = holes > 0 and e in (2, 3, 4)[:holes] and K.hash01(e, seed, int(sd) + 5) > 0.25
            if not (slit or hole):
                continue
            tin = min(MON_T, key=lambda t: abs(t - (deep[e] + 0.05 * K.sgn01(e, seed, int(sd) + 2)))) if slit else None
            cuts[(sd, e)] = (tin, (4.2 + 1.6 * K.hash01(e, seed, 8)) * L / 300.0, 0.7 * K.sgn01(e, seed, int(sd) + 9) - 0.05,
                             (0.145, 0.255, (3.0 + 1.2 * K.hash01(e, seed, 3)) * L / 300.0) if hole else None)
    return cuts


# the leaves, oldest first: small and whole below, larger and more deeply slit as the plant climbed. h: the node above
# the soil; az, el, lp: the petiole's way and length; L: the blade's midrib; nl, nr: slits on its two sides; holes;
# hang: the blade's own slope, below level; roll
MONSTERA_LEAVES = (dict(h=40.0, az=96.0, el=26.0, lp=165.0, L=150.0, nl=0, nr=0, holes=0, hang=-34.0, roll=8.0),
                   dict(h=86.0, az=-78.0, el=36.0, lp=205.0, L=176.0, nl=0, nr=1, holes=0, hang=-40.0, roll=-10.0),
                   dict(h=136.0, az=52.0, el=42.0, lp=250.0, L=205.0, nl=2, nr=1, holes=0, hang=-30.0, roll=6.0),
                   dict(h=190.0, az=-128.0, el=50.0, lp=270.0, L=222.0, nl=2, nr=3, holes=0, hang=-44.0, roll=12.0),
                   dict(h=250.0, az=22.0, el=50.0, lp=330.0, L=250.0, nl=3, nr=3, holes=1, hang=-38.0, roll=-8.0),
                   dict(h=310.0, az=-52.0, el=58.0, lp=360.0, L=270.0, nl=4, nr=3, holes=1, hang=-46.0, roll=-14.0),
                   dict(h=368.0, az=80.0, el=60.0, lp=400.0, L=286.0, nl=4, nr=4, holes=2, hang=-42.0, roll=10.0),
                   dict(h=424.0, az=-14.0, el=67.0, lp=440.0, L=302.0, nl=5, nr=4, holes=2, hang=-54.0, roll=5.0),
                   dict(h=470.0, az=38.0, el=76.0, lp=370.0, L=262.0, nl=4, nr=5, holes=1, hang=-30.0, roll=-6.0))


def monstera(g, cx, cy, clay, z0=0.0, N='plant_monstera', leaves=MONSTERA_LEAVES):
    """Monstera deliciosa on its coir pole, its saucer standing at (cx, cy, z0) mm: parts <N>_saucer, _pot, _soil,
    _pole, _leaves, _stems (stem, petioles, aerial roots), _ties"""
    K.soft(hs.revolve(N + '_saucer', SAUCER, at=V3(cx, cy, z0), seg=72), clay)
    K.soft(hs.revolve(N + '_pot', TERRACOTTA, at=V3(cx, cy, z0 + 9.0), seg=72, closed=True), clay)
    soil = z0 + 246.0
    pole_at, stem_y = V3(cx, cy + 38.0, z0), cy - 4.0
    K.soft(K.lumps(N + '_soil', (cx, cy, z0), 136.0, soil, soil - 60.0, 3.5, 14.0, 7, rings=24, seg=80, crown=6.0,
                   hole=[(0.0, 38.0, 36.0), (5.0, -26.0, 22.0)]), clay, sharp=80.0)
    # the coir pole: a stick wound in coconut fibre, bound with a thread that draws a shallow spiral in it, its top shaggy
    rl = []
    for i in range(160):
        z = soil - 40.0 + 6.0 * i
        rl.append([pole_at + V3(math.cos(2 * math.pi * k / 32), math.sin(2 * math.pi * k / 32), 0.0)
                   * (29.0 + 4.0 * (K.round_noise(k, 32, (z - z0) / 26.0, 3) - 0.5) + 1.6 * (K.round_noise(k, 32, (z - z0) / 7.0, 4, 6.0) - 0.5)
                      - 1.6 * math.exp(-(((((z - z0) / 42.0 - k / 32.0) % 1.0) - 0.5) / 0.09) ** 2)) + ZUP * (z - z0) for k in range(32)])
    top = soil - 40.0 + 6.0 * 159
    for a in (25.0, 50.0, 70.0, 84.0):
        rl.append([pole_at + V3(math.cos(2 * math.pi * k / 32), math.sin(2 * math.pi * k / 32), 0.0) * ((29.0 + 3.0 * (K.round_noise(k, 32, a, 5) - 0.5)) * math.cos(math.radians(a)))
                   + ZUP * (top - z0 + 24.0 * math.sin(math.radians(a))) for k in range(32)])
    K.soft(hs.rings(N + '_pole', rl), clay, sharp=70.0)
    g.stand_rings(rl, every=8)
    # the stem: out of the soil in front of the pole and up it, a node (a ring) where each leaf leaves
    spath = K.spline([V3(cx + 6.0, cy - 30.0, soil - 30.0), V3(cx + 4.0, cy - 22.0, soil + 30.0), V3(cx, stem_y - 2.0, soil + 110.0), V3(cx, stem_y, soil + 300.0),
                      V3(cx, stem_y, soil + 505.0)], 12)
    nodes = [soil + lf['h'] for lf in leaves]

    def stem_r(s, z0_=soil - 30.0, z1=soil + 505.0):
        z = z0_ + (z1 - z0_) * s
        return (13.6 - 2.4 * s) * (1.0 + 0.1 * sum(math.exp(-((z - zn) / 3.0) ** 2) for zn in nodes))
    limbs = [K.limb_rings(K.resample(spath, 5.0), stem_r, seg=16, caps=(0.0, 0.7))]

    def stem_at(z):
        i = min(range(len(spath) - 1), key=lambda i: abs((spath[i].z + spath[i + 1].z) / 2.0 - z))
        a, b = spath[i], spath[i + 1]
        return a.lerp(b, min(1.0, max(0.0, (z - a.z) / (b.z - a.z))) if abs(b.z - a.z) > 1e-9 else 0.0)
    into = bmesh.new()
    n = len(leaves)
    for k, lf in enumerate(leaves):
        age = 1.0 - k / (n - 1.0)
        c = stem_at(soil + lf['h'])
        cuts = monstera_cuts(lf['nl'], lf['nr'], lf['holes'], lf['L'], 40 + k)

        def make(daz=0.0, dh=0.0, dl=1.0, k=k, lf=lf, c=c, cuts=cuts, age=age):
            a = lf['az'] + daz
            D = polar(a, lf['el'])
            Jn = c + polar(a, 0.0) * 9.0 + D * (lf['lp'] * dl)
            ab, eb = a + 9.0 * K.sgn01(k, 61), lf['hang'] + dh
            sk = monstera_blade(Jn, ab, eb, lf['L'], cuts, roll=lf['roll'], bend=10.0 + 10.0 * K.hash01(k, 62), ears_up=4.0 + 5.0 * K.hash01(k, 63),
                                drop=8.0 + 8.0 * K.hash01(k, 64), wide=(1.0, 0.94 + 0.1 * K.hash01(k, 65)), droop=[4.0 + 10.0 * K.hash01(k, 66 + i) for i in range(6)],
                                ident=K.hash01(k, 67), age=age, seed=k)
            tb = polar(ab, eb)
            sk.joint = (a, D, Jn, tb, Quaternion(tb, math.radians(lf['roll'])) @ polar(ab, eb + 90.0))
            return sk
        sk = g.choose(make, [dict(daz=d, dh=h_, dl=l_) for l_ in (1.0, 1.12, 0.88) for h_ in (0.0, 10.0, -10.0) for d in (0.0, 15.0, -15.0)])
        a, D, Jn, tb, nb = sk.joint
        # the petiole: it sheathes the stem at its foot (a channel on its upper side for a third of its length), arches
        # a little under the blade's weight, and swells into the KNEE that turns the blade to hang
        lp = (Jn - c - polar(a, 0.0) * 9.0).length
        rb, re = lf['L'] * 0.026, lf['L'] * 0.013
        p0 = c + polar(a, 0.0) * 6.0
        pts = [p0 - ZUP * 6.0, p0 + ZUP * (0.13 * lp) + polar(a, 0.0) * (0.05 * lp), p0 + D * (0.55 * lp) - ZUP * (0.025 * lp),
               Jn - D * 26.0 - nb * (re * 0.6), Jn - D * 7.0 - nb * (re * 0.9) + tb * 2.0, Jn + tb * 9.0 - nb * (re * 0.75)]
        limbs.append(K.limb_rings(K.resample(K.spline(pts, 10), 6.0), lambda s, rb=rb, re=re: K.lerp(rb, re, s) * (1.0 + 0.16 * math.exp(-((s - 0.94) / 0.035) ** 2)),
                                  seg=12, up0=polar(a + 180.0, 30.0), flat=lambda s: 0.6 * (1.0 - K.smooth(s, 0.22, 0.42)), caps=(0.0, 0.8)))
        g.torn += K.thicken(sk, into)
    close_leaves(N + '_leaves', into, clay)
    # two aerial roots: from a node, out past the stem and down into the soil
    for zn, a, reach in ((soil + 136.0, -150.0, 70.0), (soil + 250.0, 140.0, 95.0)):
        p0 = stem_at(zn)
        h2 = polar(a, 0.0)
        pts = [p0, p0 + polar(a, -8.0) * 34.0, p0 + polar(a, -40.0) * (reach * 0.8) - ZUP * (0.35 * (zn - soil)), V3(p0.x + h2.x * reach, p0.y + h2.y * reach, soil + 14.0),
               V3(p0.x + h2.x * (reach + 8.0), p0.y + h2.y * (reach + 8.0), soil - 14.0)]
        limbs.append(K.limb_rings(K.resample(K.spline(pts, 10), 6.0), lambda s: 3.6 - 0.8 * s, seg=10))
    K.soft(hs.skins(N + '_stems', limbs), clay, sharp=60.0)
    # two ties of green coated wire round the pole and the stem
    ties = []
    for zt, tw in ((soil + 165.0, 4.0), (soil + 385.0, -5.0)):
        loop = [V3(cx + 33.5 * math.sin(math.radians(g_)), cy + 23.0 - 46.0 * math.cos(math.radians(g_)), zt + tw * math.cos(math.radians(g_))) for g_ in range(0, 360, 9)]
        rr = [[p + nn * (1.05 * math.cos(2 * math.pi * q_ / 8)) + bb * (1.05 * math.sin(2 * math.pi * q_ / 8)) for q_ in range(8)] for p, tt_, nn, bb in K.pt_frames(loop + [loop[0]], (0, 0, 1))]
        ties.append(rr[:-1] + [rr[0]])
    K.soft(K.loops(N + '_ties', ties), clay)


# ------------------------------------------------------------------------------------------------- the corn plant
DRAC = [(0.0, 0.27), (0.03, 0.3), (0.1, 0.52), (0.2, 0.78), (0.32, 0.95), (0.42, 1.0), (0.55, 0.96), (0.7, 0.8), (0.82, 0.56), (0.9, 0.34), (0.95, 0.17), (0.98, 0.07), (1.0, 0.0)]
DSS = (0.0, 0.015, 0.035, 0.06, 0.09, 0.125, 0.165, 0.21, 0.26, 0.31, 0.36, 0.41, 0.46, 0.51, 0.56, 0.61, 0.66, 0.71, 0.76, 0.805, 0.845, 0.88, 0.91, 0.935, 0.955, 0.972, 0.986, 1.0)
DVS = (-1.0, -0.9, -0.72, -0.5, -0.28, -0.1, 0.0, 0.1, 0.28, 0.5, 0.72, 0.9, 1.0)
# the canes (where, height, radius foot and top, lean, seed) and their heads (which way the shoot leaves the cane, how
# far under the cut, its longest leaf, how many leaves): canes as thick as a wrist, each head a lush fountain of soft
# leaves a hand wide that arch from the heart out
CORN_CANES = (dict(at=(-30.0, 40.0), h=1010.0, r=(34.0, 31.0), lean=(160.0, 1.2), seed=21, heads=((-76.0, 58.0, 480.0, 22), (98.0, 42.0, 450.0, 20))),
              dict(at=(50.0, -32.0), h=520.0, r=(30.0, 28.0), lean=(40.0, 2.0), seed=22, heads=((-22.0, 44.0, 430.0, 18),)),
              dict(at=(-56.0, -50.0), h=205.0, r=(27.0, 26.0), lean=(-120.0, 2.5), seed=23, heads=((38.0, 34.0, 260.0, 10),)))


def corn_plant(g, cx, cy, clay, z0=0.0, N='plant_dracaena', canes=CORN_CANES):
    """Dracaena fragrans 'Massangeana', its planter standing at (cx, cy, z0) mm: parts <N>_pot, _soil, _pebbles,
    _leaves, _canes, _shoots"""
    K.soft(hs.revolve(N + '_pot', PLANTER, at=V3(cx, cy, z0), seg=80), clay)
    soil = z0 + 338.0
    K.soft(K.lumps(N + '_soil', (cx, cy, z0), 172.5, soil, soil - 80.0, 3.0, 30.0, 9, hole=[(c_['at'][0], c_['at'][1], 36.0) for c_ in canes]), clay, sharp=80.0)
    pebbles(N + '_pebbles', (cx, cy, z0), 170.0, soil - z0 + 1.0, 31, clay, avoid=[(c_['at'][0], c_['at'][1], c_['r'][0]) for c_ in canes])
    into, limbs, cane_sk, grown = bmesh.new(), [], [], []
    SEG = 28
    for j, cn in enumerate(canes):                              # the canes first: a blade may not pass through any of them
        base = V3(cx + cn['at'][0], cy + cn['at'][1], soil)
        lean = polar(cn['lean'][0], 0.0) * math.tan(math.radians(cn['lean'][1]))

        def centre(z, base=base, lean=lean):
            return base + ZUP * z + lean * max(0.0, z)
        # the bark: a ring (a leaf's scar) every two centimetres or so, never evenly; the cane a little out of round
        ridges, z = [], 9.0
        while z < cn['h'] - 6.0:
            ridges.append(z)
            z += 20.0 + 7.0 * K.sgn01(len(ridges), cn['seed'])
        rl = []
        nz = int((cn['h'] + 40.0) / 3.5)
        for i in range(nz + 1):
            z = -40.0 + (cn['h'] + 40.0) * i / nz
            r = K.lerp(cn['r'][0], cn['r'][1], max(0.0, z) / cn['h'])
            ridge = max(math.exp(-((z - zr) / 1.5) ** 2) for zr in ridges)
            above = [z - zr for zr in ridges if z >= zr]
            lip = 0.5 * math.exp(-min(above) / 5.0) if above else 0.0
            rl.append([centre(z) + V3(math.cos(2 * math.pi * k / SEG), math.sin(2 * math.pi * k / SEG), 0.0)
                       * (r + 1.0 * ridge + lip + 1.7 * (K.round_noise(k, SEG, z / 90.0, cn['seed']) - 0.5) + 0.5 * (K.round_noise(k, SEG, z / 9.0, cn['seed'] + 1, 5.0) - 0.5))
                       for k in range(SEG)])
        # the cut top: sawn flat, the bark's edge a little proud, the pith a little sunk
        rt = cn['r'][1]
        for rr, dz in ((rt - 1.0, 1.2), (rt - 4.5, 0.6), (rt * 0.55, -0.5), (rt * 0.2, -1.1)):
            rl.append([centre(cn['h']) + V3(math.cos(2 * math.pi * k / SEG), math.sin(2 * math.pi * k / SEG), 0.0) * rr + ZUP * dz for k in range(SEG)])
        cane_sk.append(rl)
        g.stand_rings(rl, every=12)
        grown.append((cn, centre, rt))
    for j, (cn, centre, rt) in enumerate(grown):
        for hi, (haz, drop_, Lmax, nleaf) in enumerate(cn['heads']):
            # a shoot: out of the cane's side just under the cut, turning up, tapering into the heart where the leaves'
            # own bases hide its tip; shingled with the dry sheaths of the leaves it has dropped (shallow uneven steps)
            c0 = centre(cn['h'] - drop_)
            pts = [c0, c0 + polar(haz, 12.0) * (rt + 6.0), c0 + polar(haz, 12.0) * (rt + 6.0) + polar(haz, 46.0) * 26.0]
            pts.append(pts[-1] + polar(haz, 70.0) * (34.0 + 5.0 * nleaf))
            sp = K.resample(K.spline(pts, 10), 4.0)
            limbs.append(K.limb_rings(sp, lambda s, hi=hi, j=j: 16.5 - 10.5 * s ** 1.3 + (1.1 * ((s * 7.3 + 0.6 * math.sin(9.0 * s + hi + j)) % 1.0) * (1.0 - s) if s > 0.15 else 0.0),
                                      seg=18, caps=(0.0, 0.5)))
            tip, axis = sp[-1], (sp[-1] - sp[-3]).normalized()
            eu = axis.cross(polar(haz + 90.0, 0.0)).normalized()
            ev = axis.cross(eu)
            for k in range(nleaf):
                u = k / (nleaf - 1.0)                           # 0 the newest, upright in the heart; 1 the oldest, hanging
                phi = math.radians(k * 137.5 + 40.0 * hi + 9.0 * K.sgn01(k, cn['seed'], hi))
                ek = math.radians(4.0 + 78.0 * u ** 1.05)
                rad = eu * math.cos(phi) + ev * math.sin(phi)
                az0, el0 = az_el(axis * math.cos(ek) + rad * math.sin(ek))
                grow = (0.36, 0.56, 0.76)[k] if k < 3 else 1.0 - 0.16 * u + 0.06 * K.sgn01(k, cn['seed'], hi + 3)
                L = Lmax * grow
                W = L * (0.225 if k >= 2 else 0.15)
                p0 = tip - axis * (3.6 * k) + rad * (2.5 + 6.0 * u)
                sgn = 1.0 if K.hash01(k, cn['seed'], hi + 5) > 0.5 else -1.0

                def make(daz=0.0, mb=1.0, ml=1.0, k=k, u=u, az0=az0, el0=el0, L=L, W=W, p0=p0, sgn=sgn, j=j, hi=hi):
                    return blade(p0, az0 + daz, el0, L * ml, W * (0.5 + 0.5 * ml), DRAC, bend=(24.0 + 94.0 * u ** 1.1) * mb, bend_pow=1.25,
                                 kink=(0.4 + 0.1 * K.hash01(k, j, hi + 7), 0.38, 0.07) if u > 0.42 else None, side=8.0 * K.sgn01(k, j, hi + 8),
                                 roll=7.0 * K.sgn01(k, j, hi + 9), twist=sgn * (8.0 + 24.0 * u), fold=(58.0 - 18.0 * u, 4.0), cup=0.3,
                                 wave=(2.5 + 6.0 * u, 3.3, K.hash01(k, j, hi + 10)), th=0.6, rib=(0.4, 6.0), drip=18.0 * u, ident=K.hash01(k, j, hi + 21), age=u, ss=DSS, vs=DVS)
                tries = [dict(daz=d_, mb=m_) for m_ in (1.0, 1.14, 0.86) for d_ in (0.0, 13.0, -13.0, 26.0, -26.0)]
                tries += [dict(daz=d_, mb=m_, ml=l_) for l_ in (0.84, 0.7) for m_ in (1.0, 1.2) for d_ in (0.0, 20.0, -20.0)]     # (a leaf by a wall is a shorter leaf)
                sk = g.choose(make, tries, keep=lambda dt: dt[0] >= 0.34)          # (in the heart the leaves sheathe one another: asked from a third along)
                g.torn += K.thicken(sk, into)
    close_leaves(N + '_leaves', into, clay)
    K.soft(hs.skins(N + '_canes', cane_sk), clay, sharp=50.0)
    K.soft(hs.skins(N + '_shoots', limbs), clay, sharp=45.0)


# ---------------------------------------------------------------------------------------------- the watering can
def watering_can(cx, cy, z0, clay, toward=90.0, N='watering_can'):
    """one moulding: a body that widens upward, a long spout rising from low on its front, an open hook of a handle
    from the rim's back; standing at (cx, cy, z0) mm, its spout toward `toward` (degrees, as polar()). One mass: the
    body and the spout joined, the spout's bore cut ONCE through its tip and the body's wall"""
    body = [(0.0, 3.0), (33.0, 3.0), (35.0, 0.0), (41.0, 0.0), (43.5, 3.0), (60.0, 132.0), (61.0, 137.0), (60.0, 139.5), (58.3, 139.0), (57.8, 134.0), (41.6, 6.0), (39.0, 5.0), (0.0, 5.0)]
    C = V3(cx, cy, z0)
    f, bk = polar(toward, 0.0), polar(toward + 180.0, 0.0)
    can = hs.revolve(N + '_body', body, at=C, seg=64)
    line = [C + f * 30.0 + ZUP * 40.0, C + f * 45.0 + ZUP * 46.0, C + f * 62.0 + ZUP * 56.0, C + f * 150.0 + ZUP * 128.0, C + f * 262.0 + ZUP * 226.0, C + f * 296.0 + ZUP * 252.0]
    sp = K.resample(K.spline(line, 10), 6.0)
    tip_dir = (sp[-1] - sp[-2]).normalized()
    can = hs.boolean(can, hs.rings(N + '_spout', K.limb_rings(sp[2:], lambda s: 15.5 - 10.4 * s ** 0.8, seg=20)), 'UNION')
    hp = K.resample(K.spline([C + bk * 57.0 + ZUP * 133.0, C + bk * 72.0 + ZUP * 142.0, C + bk * 96.0 + ZUP * 132.0, C + bk * 106.0 + ZUP * 96.0, C + bk * 100.0 + ZUP * 44.0,
                              C + bk * 97.0 + ZUP * 24.0], 10), 5.0)
    can = hs.boolean(can, hs.rings(N + '_handle', K.limb_rings(hp, lambda s: 8.5 - 1.5 * s, seg=16, up0=(0, 0, 1), squash=0.42, caps=(0.0, 0.9))), 'UNION')
    can = hs.boolean(can, hs.rings(N + '_bore', K.limb_rings(sp + [sp[-1] + tip_dir * 8.0], lambda s: 13.6 - 10.0 * s ** 0.8, seg=20)), 'DIFFERENCE')
    can.name = N
    return K.soft(can, clay, sharp=42.0)
