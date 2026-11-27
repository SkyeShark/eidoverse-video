"""eidoblend.sets.town.layout: the town's plan, built. Blender; eidoblend.sets.town.build() is this module's build().

THE TOWN'S OWN SPACE: x along the main road (y = -14, 11 m wide, a kerbed median with lamps and palms), streets along
x every 40-46 m (YSTREETS), cross streets along y every 46-78 m, extent (ex, ey) metres of blocks; z = 0 the ground.
Beyond the blocks the town does not stop at a ruled line: its streets run on as tracks, and houses run on along them,
fewer and further apart, each on its walled lot, among walled plots and palm groves, for `edge` metres.

Every kind of thing draws from a stream of chance of its own (the seed's), so changing one never moves another. Each
building is made once (a pool of designs per kind) and placed many times: blocks of flats over shops on the main
roads, blocks of flats, low houses on the back streets. The blocks are lots: a pavement and its banded kerb along
each street, a wall down the block's middle between the yards, each house's yard behind it with what is kept there
(a tree, a palm, a car, a shed, junk, washing), a passage closed by a steel gate. The mosque stands on its square
with stalls along it; concrete poles carry the wires, some a transformer or a lamp; cars at the kerbs; dishes on the
roofs, all turned to one satellite.

DAMAGE is an option, off by default: an intact town. damage=True places strikes from the seed (about one per 3 ha of
town), or give them: [(x, y, reach), ...]. Round each strike the buildings are struck (fronts blown off, corners
brought down, roofs holed, walls scarred), the street is cratered and strewn, cars are burnt, poles down, its pale
fall lies on everything (the materials read each object's 'tn_dust'), concrete barriers close the road; a line of
blast walls stands where the main road enters. Without damage none of this is built.

Every placed building carries object properties: tn_dust (0..1, how near a strike it stands; 0 when intact), tn_w,
tn_d, tn_h (its lot and height), tn_in (1 inside the town's blocks, 0 on its edge).
"""
import math
import random

import bpy

from . import kit as K
from . import materials as MT
from . import signs as SG
from . import street as ST
from .house import House
from .materials import M
from .mb import MB, catenary

# the streets along x: (y, width); the main road is the 11 m one. A town of another height keeps those inside it
YSTREETS = [(-146.0, 6.0), (-100.0, 6.0), (-58.0, 7.0), (-14.0, 11.0), (30.0, 7.0), (74.0, 6.0), (118.0, 6.0), (150.0, 6.0)]
MOSQUE = (-78.0, -22.0, 36.0, 71.0)                              # its square: x0, x1, y0, y1
DISH_TURN = math.radians(205.0) + math.pi                        # every dish in a town looks at the same satellite
ASPHALT_PAST = (30.0, 10.0)                                      # how far the asphalt runs past the outer streets: x, y


class Town:
    """what build() made: group (the parent, or None), collection, objects by kind (parts), strikes, the streets
    (ystreets, xstreets), paved (where the asphalt ends), stats; views() lenses on it"""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def views(self):
        from .views import views
        return views(self)


def plan_strikes(rng, ex, ey, n=None):
    """strikes placed by a stream of the seed: about one per 3.15 ha of blocks, each with its reach"""
    n = max(1, int(round(ex * ey / 31500.0))) if n is None else n
    out = []
    for _ in range(80 * n):
        if len(out) >= n:
            break
        x, y = rng.uniform(-ex / 2 + 20.0, ex / 2 - 20.0), rng.uniform(-ey / 2 + 10.0, ey / 2 - 10.0)
        r = rng.uniform(28.0, 45.0)
        if all(math.hypot(x - a, y - b) > 0.8 * (r + c) for a, b, c in out):
            out.append((round(x, 1), round(y, 1), round(r, 1)))
    return out


def crater(b, rng, cx, cy, r, z=0.03):
    """where a bomb met the street: a dished pit with a lip of what it threw up, pieces thrown out round it (a pit is
    its rim and its lit wall, never a black disc)"""
    n = 18
    prof = [(1.9, 0.0), (1.45, 0.10), (1.12, 0.34), (0.94, 0.28), (0.7, 0.10), (0.42, 0.03), (0.15, 0.0)]
    wob = [rng.uniform(0.8, 1.2) for _ in range(n)]
    P = [[(cx + r * q * wob[k] * math.cos(2 * math.pi * k / n), cy + r * q * wob[k] * math.sin(2 * math.pi * k / n), z + h * (r / 3.0) * rng.uniform(0.7, 1.3) - (0.04 if q > 1.8 else 0.0))
          for k in range(n)] for q, h in prof]
    base = b.verts([p for row in P for p in row])
    for j in range(len(prof) - 1):
        for k in range(n):
            a, c_ = base + j * n + k, base + j * n + (k + 1) % n
            b.face((a, c_, c_ + n, a + n), 'crater' if j >= 3 else 'rubble', True)
    b.face([base + (len(prof) - 1) * n + k for k in range(n)], 'crater', True)
    for _ in range(int(14 + 6 * r)):
        a, d = rng.uniform(0.0, 6.283), r * (0.9 + rng.random() ** 1.5 * 2.6)
        s = rng.uniform(0.12, 0.5)
        K.chunk(b, rng, (cx + d * math.cos(a), cy + d * math.sin(a), z + s * 0.14), s, rng.choice(('rubble', 'concrete', 'road')), rng.choice(('lump', 'shard')))


def _yard_trees(R, kind, c, parent, log):
    """the yard trees: placers put(name, x, y, rot) -> object. kind 'built' (the town's own broad-leaved tree, four
    designs), 'seedthree' (SeedThree's apple, three grown individuals placed as linked copies; an error without a
    SeedThree checkout), 'auto' (SeedThree's when a checkout is found, else built)"""
    if kind in ('auto', 'seedthree'):
        try:
            from ...trees import make_seed_tree, find_seedthree
            find_seedthree()
            kind = 'seedthree'
        except (ImportError, RuntimeError) as e:
            if kind == 'seedthree':
                raise
            log(f'[town] yard trees: the built tree ({e})')
            kind = 'built'
    if kind == 'seedthree':
        store = bpy.data.collections.new('town_tree_store')                # the grown individuals, hidden, unparented
        bpy.context.scene.collection.children.link(store)
        store.hide_render = store.hide_viewport = True
        grown = []
        for k, (seed, dials) in enumerate(((11, {'height': 4.2}), (23, {'height': 3.6}), (37, {'height': 4.8}))):
            grown.append(make_seed_tree(species='apple', seed=seed, dials=dials, location=(0.0, 0.0, -1000.0 - 50.0 * k),
                                        level='LOD1', collection=store, name=f'town_yard_apple_{k}', fruit=False, wind=False))
        tris = [sum(len(o.data.polygons) for v in g['objects'].values() for o in v if o.type == 'MESH') for g in grown]
        log(f'[town] yard trees: SeedThree apple at LOD1, {len(grown)} individuals of {tris} faces')

        def put(name, x, y, rot, rng):
            g = make_seed_tree.duplicate(grown[rng.randrange(len(grown))], location=(x, y, 0.0), rotation=rot, collection=c,
                                         name=name)
            if parent is not None:
                g['object'].parent = parent
            return g['object']
        return put, 'seedthree'
    meshes = [ST.tree(R(4, k)).mesh(f'tree_{k}', M) for k in range(4)]

    def put(name, x, y, rot, rng):
        o = bpy.data.objects.new(name, meshes[rng.randrange(len(meshes))])
        c.objects.link(o)
        o.location, o.rotation_euler = (x, y, 0.0), (0.0, 0.0, rot)
        if parent is not None:
            o.parent = parent
        return o
    return put, 'built'


def build(collection=None, parent=None, seed=7, extent=(840.0, 300.0), damage=False, signs=None, sign_font=None,
          yard_trees='auto', things=True, masks=True, air=True, edge=170.0, ystreets=None, mosque='auto', log=print):
    """Build the town into `collection` (made and linked into the scene when None), its objects parented to `parent`
    (an Empty you move to carry it; None: placed in the town's own metres).

    seed        every stream of chance; extent (ex, ey) the blocks' size in metres (the edge runs on past it)
    damage      False (an intact town), True (strikes placed by the seed), or [(x, y, reach), ...]
    signs       None (painted boards) or what the shop signs say: words or pictures (signs.prepare); sign_font a
                file of eidoverse/assets/fonts/ or a path
    yard_trees  'auto' | 'seedthree' | 'built' (_yard_trees); the palms are the town's own (no date palm in SeedThree)
    things      the CC0 models people leave about (things.place; fetched by ID on first use)
    masks       the per-face masks the materials read (masks.annotate); air: the haze volume (world.air)
    edge        metres of the town's edge past its blocks; ystreets [(y, width)] (default: YSTREETS inside the
                extent); mosque 'auto' (its square when the extent holds it), None, or (x0, x1, y0, y1)
    -> Town"""
    import time
    t0 = time.time()
    ex_, ey = float(extent[0]), float(extent[1])
    if collection is None:
        collection = bpy.data.collections.new('town')
        bpy.context.scene.collection.children.link(collection)
    c = collection

    def R(stream, k=0):
        """a stream of chance of its own for each kind of thing: changing one never moves another"""
        return random.Random(seed * 1000003 + stream * 7919 + k)
    if damage is True:
        strikes = plan_strikes(R(14), ex_, ey)
    elif damage:
        strikes = [tuple(float(v) for v in s) for s in damage]
    else:
        strikes = []
    YST = [tuple(s) for s in (ystreets if ystreets is not None else [s for s in YSTREETS if abs(s[0]) <= ey / 2 + 2.0])]
    if len(YST) < 2:
        raise ValueError(f'[town] extent {extent}: it needs two streets along x at least (have {YST}); give ystreets=')
    if mosque == 'auto':
        mq = MOSQUE if (MOSQUE[0] > -ex_ / 2 + 10 and MOSQUE[1] < ex_ / 2 - 10 and any(MOSQUE[2] > a[0] and MOSQUE[3] < b_[0]
                                                                                 for a, b_ in zip(YST, YST[1:]))) else None
    else:
        mq = tuple(mosque) if mosque else None

    def struck(x, y):
        return min((math.hypot(x - sx, y - sy) / sr for sx, sy, sr in strikes), default=1e9)

    parts = {'buildings': [], 'dishes': [], 'trees': [], 'palms': [], 'cars': [], 'poles': [], 'lamps': [], 'stalls': [], 'other': []}

    def put(name, me, x, y, rot=0.0, z=0.0, kind='other'):
        o = bpy.data.objects.new(name, me)
        c.objects.link(o)
        o.location, o.rotation_euler = (x, y, z), (0.0, 0.0, rot)
        if parent is not None:
            o.parent = parent
        parts[kind].append(o)
        return o
    House.signs = SG.prepare(signs, sign_font)
    MT.SIGNS[:] = House.signs
    MT.STRIKES[:] = strikes
    MT.PAVED[:] = [ex_ / 2 + ASPHALT_PAST[0], ey / 2 + ASPHALT_PAST[1]]          # where each street's asphalt ends
    MT.SAND_REACH[:] = [ASPHALT_PAST[0] + 4.0, ASPHALT_PAST[1] + 2.0]
    # ---------------------------------------------------------------- the buildings, each made once
    kinds = ('A', 'B', 'C') + (('HA', 'HC', 'SA', 'SC') if strikes else ())
    pools = {k: [] for k in ('A', 'B', 'C', 'HA', 'HC', 'SA', 'SC')}
    order = list(pools)
    r = R(1)

    def make(pool, k, w, d, annex, floors, shops, dmg, low):
        if pool not in kinds:
            return
        h = House(R(10 + order.index(pool), k), w, d, floors, shops, dmg, low, annex)
        pools[pool].append((h.mesh(f'town_{pool}_{k:02d}', M), h.anchors, w, h.d, h.zf[h.F]))
    AX = (0.0, 3.4, 3.8, 4.4)                                        # how deep the low rooms behind a house run
    for k in range(11):                                              # blocks of flats over shops
        make('A', k, r.uniform(9.5, 17.0), r.uniform(9.0, 11.5), r.choice(AX), r.choice((2, 3, 3, 3, 4, 4, 5)), True, 0, False)
    for k in range(9):                                               # blocks of flats
        make('B', k, r.uniform(9.5, 16.0), r.uniform(8.6, 11.5), r.choice(AX), r.choice((2, 2, 3, 3, 4)), False, 0, False)
    for k in range(14):                                              # low houses
        make('C', k, r.uniform(7.5, 12.5), r.uniform(6.8, 10.0), r.choice(AX[1:] + (0.0,)) if k % 4 else 0.0, r.choice((1, 1, 2, 2)), False, 0, True)
    for k, dm in enumerate((1, 1, 1, 2, 2, 2, 3, 3, 4)):            # blocks as a strike left them
        make('HA', k, r.uniform(10.0, 17.0), r.uniform(9.0, 11.5), r.choice(AX), r.choice((2, 3, 3, 4, 4, 5)), r.random() < 0.6, dm, False)
    for k, dm in enumerate((2, 2, 3, 4, 4, 1)):                      # low houses as a strike left them
        make('HC', k, r.uniform(7.5, 12.0), r.uniform(6.8, 10.0), r.choice(AX), r.choice((1, 2, 2)), False, dm, True)
    for k in range(4):                                               # scarred: a hole or two
        make('SA', k, r.uniform(9.5, 16.0), r.uniform(9.0, 11.5), r.choice(AX), r.choice((2, 3, 3, 4)), r.random() < 0.6, 5, False)
    for k in range(3):
        make('SC', k, r.uniform(7.5, 12.0), r.uniform(6.8, 10.0), r.choice(AX), r.choice((1, 2)), False, 5, True)
    log(f'[town] {sum(len(v) for v in pools.values())} building designs in {time.time() - t0:.1f} s')
    # ---------------------------------------------------------------- what is placed many times in the streets
    r = R(2)
    cars = [ST.car('saloon').mesh('car_saloon', M), ST.car('saloon').mesh('car_saloon_b', M), ST.car('pickup').mesh('car_pickup', M),
            ST.car('pickup', load='sacks', rng=r).mesh('car_pickup_sacks', M), ST.car('pickup', load='boxes', rng=r).mesh('car_pickup_boxes', M),
            ST.car('van').mesh('car_van', M)]
    wrecks = [ST.car('saloon', burnt=True).mesh('car_saloon_burnt', M), ST.car('pickup', burnt=True).mesh('car_pickup_burnt', M),
              ST.car('van', burnt=True).mesh('car_van_burnt', M)] if strikes else []
    palms = [ST.palm(R(3, k)).mesh(f'palm_{k}', M) for k in range(5)]
    far_palms = [ST.palm(R(3, 10 + k), light=True).mesh(f'palm_far_{k}', M) for k in range(3)]
    put_tree, tree_kind = _yard_trees(R, yard_trees, c, parent, log)
    dishes = [ST.dish(False).mesh('dish', M), ST.dish(True).mesh('dish_dark', M), ST.dish(False, 1.5).mesh('dish_big', M)]
    poles = {k: ST.pole(R(5, i), k).mesh(f'pole_{k}', M) for i, k in enumerate(('plain', 'transformer', 'lamp'))}
    lamp = ST.lamp_post(True).mesh('lamp_post', M)
    stalls = [ST.stall(R(6, k)).mesh(f'stall_{k}', M) for k in range(5)]
    bikes = [ST.bicycle('bike_red').mesh('bicycle_red', M), ST.bicycle('bike_blue').mesh('bicycle_blue', M)]
    twall = ST.t_wall().mesh('t_wall', M) if strikes else None
    # ---------------------------------------------------------------- the streets
    rng = R(7)
    xstreets = []
    x = -ex_ / 2
    while x < ex_ / 2:
        xstreets.append((x, rng.choice((5.0, 6.0, 6.0, 7.0))))
        x += rng.uniform(46.0, 78.0)
    PX, PY = MT.PAVED
    g = MB()
    g.quad((-1600, -1600, 0), (1600, -1600, 0), (1600, 1600, 0), (-1600, 1600, 0), 'ground')
    for yc, wd in YST:
        g.quad((-PX, yc - wd / 2, 0.03), (PX, yc - wd / 2, 0.03), (PX, yc + wd / 2, 0.03), (-PX, yc + wd / 2, 0.03), 'road')
    for xc, wd in xstreets:
        g.quad((xc - wd / 2, -PY, 0.025), (xc + wd / 2, -PY, 0.025), (xc + wd / 2, PY, 0.025), (xc - wd / 2, PY, 0.025), 'road:y')
    st = MB()                                                        # pavements, kerbs, yard walls, wires, what a strike left in the road
    n_b = n_i = 0
    rows = {}                                                        # each street side's buildings: (x0, x1, front line, how high)

    def house_at(pick, ox, oy, rot, in_town=True):
        """one building placed by its front's left corner, turned by rot (0: its front looks toward -y); its dishes"""
        nonlocal n_b, n_i
        me, anchors, w, d, hz = pick
        cs, sn = math.cos(rot), math.sin(rot)
        o = put(f'bld.{n_b:04d}', me, ox, oy, rot, kind='buildings')
        o['tn_dust'] = max(0.0, min(1.0, 1.15 - struck(ox + cs * w / 2 - sn * d / 2, oy + sn * w / 2 + cs * d / 2) / 1.2)) if in_town else 0.0
        o['tn_w'], o['tn_d'], o['tn_h'], o['tn_in'] = w, d, hz, 1 if in_town else 0
        n_b += 1
        for (ax_, ay_, az_) in anchors:
            if rng.random() < (0.85 if me.name[5] != 'H' else 0.4):
                put(f'dish.{n_i:05d}', dishes[rng.choice((0, 0, 1, 1, 1, 2))], ox + cs * ax_ - sn * ay_, oy + sn * ax_ + cs * ay_,
                    DISH_TURN + rng.uniform(-0.12, 0.12), az_, kind='dishes')
                n_i += 1
        return o

    def house(pick, x, yy, side, in_town=True):
        """on a street of the town: side 0, its front at yy looking -y; side 1, looking +y"""
        return house_at(pick, x, yy, 0.0, in_town) if side == 0 else house_at(pick, x + pick[2], yy, math.pi, in_town)
    for bi in range(len(YST) - 1):
        (ya, wa), (yb, wb) = YST[bi], YST[bi + 1]
        y0, y1 = ya + wa / 2, yb - wb / 2
        pwa, pwb = (2.4 if wa > 9 else 1.5), (2.4 if wb > 9 else 1.5)          # the pavement: wider on the main road
        ym = (y0 + y1) / 2.0
        for xi in range(len(xstreets) - 1):
            (xa, xwa), (xb, xwb) = xstreets[xi], xstreets[xi + 1]
            x0, x1 = xa + xwa / 2, xb - xwb / 2
            for yy, sgn, pw in ((y0, 1.0, pwa), (y1, -1.0, pwb)):   # a pavement and its banded kerb along each street
                lo_, hi_ = sorted((yy, yy + sgn * pw))
                st.box((x0, lo_, 0.0), (x1, hi_, 0.14), 'walk', skip='z-')
                lo_, hi_ = sorted((yy - sgn * 0.18, yy))
                st.box((x0 - 0.18, lo_, 0.0), (x1 + 0.18, hi_, 0.16), 'kerb', skip='z-')
            in_square = mq is not None and not (x1 < mq[0] or x0 > mq[1] or y1 < mq[2] or y0 > mq[3])
            wall_m = rng.choice(('block', 'plaster_w', 'plaster_w', 'brick'))
            if not in_square:
                st.run([(x0 + 0.3, ym - 0.1), (x1 - 0.3, ym - 0.1)], 0.2, 0.0, 2.1, wall_m, top='concrete')         # the wall down the block's middle, between the yards
                for xe in (x0 + 0.1, x1 - 0.3):                     # and the block's two ends, on the lanes
                    st.box((xe, y0 + pwa + 0.3, 0.0), (xe + 0.2, y1 - pwb - 0.3, 2.1), wall_m, skip='z-', top='concrete')
            for side, yy, yst, wst_ in ((0, y0 + pwa, ya, wa), (1, y1 - pwb, yb, wb)):
                x = x0 + rng.uniform(0.0, 1.5)
                main, second = wst_ > 9, wst_ > 6.5
                deep = abs(ym - yy) - 0.5                           # how deep a house may be here
                dy = 1.0 if side == 0 else -1.0
                while x < x1 - 7.5:
                    if rng.random() < 0.05:                         # an empty lot: rubbish, a heap of spoil
                        gap = rng.uniform(5.0, 10.0)
                        if x + gap < x1 and not in_square:
                            K.heap(st, rng, x + gap / 2, yy + dy * rng.uniform(3.0, 6.0), rng.uniform(1.2, 2.4), rng.uniform(1.0, 2.0), rng.uniform(0.4, 0.9), 0.0,
                                   pieces=rng.randrange(6, 14), field=False, m='ground')
                            if rng.random() < 0.5:
                                K.junk(st, rng, x + gap * rng.uniform(0.2, 0.8), yy + dy * rng.uniform(1.0, 3.0), 0.0)
                        x += gap
                        continue
                    lowrow = (not main) and (rng.random() < (0.3 if second else 0.75))
                    if strikes:
                        s_ = struck(x + 6.0, yy + dy * 5.0)
                        if (s_ < 0.75 and rng.random() < 0.9) or (s_ < 1.15 and rng.random() < 0.55):
                            pool = 'HC' if lowrow else 'HA'
                        elif (s_ < 1.9 and rng.random() < 0.5) or rng.random() < 0.015:
                            pool = 'SC' if lowrow else 'SA'
                        else:
                            pool = None
                    else:
                        pool = None
                    if pool is None:
                        if lowrow:
                            pool = 'C'
                        else:
                            pool = 'A' if (main and rng.random() < 0.85) or (second and rng.random() < 0.45) else 'B'
                    fit = [q for q in pools[pool] if q[3] <= deep] or [min(pools[pool], key=lambda q: q[3])]
                    pick = fit[rng.randrange(len(fit))]
                    me, anchors, w, d, hz = pick
                    if x + w > x1:
                        break
                    if in_square and not (x + w < mq[0] or x > mq[1] or (yy + d if side == 0 else yy) < mq[2] or (yy if side == 0 else yy - d) > mq[3]):
                        x += w + 1.0                                # the mosque's square is kept clear
                        continue
                    house(pick, x, yy, side)
                    rows.setdefault((yst, side), []).append((x, x + w, yy, hz))
                    # its yard, what is left of the lot behind it: its own ground, a wall down one side, what is kept there
                    yback = yy + dy * d
                    depth = abs(ym - yback) - 0.1
                    gap = rng.choice((0.0, 0.0, 0.0, 1.2, 2.5))
                    if depth > 0.8 and not in_square:
                        lo_, hi_ = sorted((yback, ym - 0.1 * dy))
                        st.quad((x, lo_, 0.012), (x + w + gap, lo_, 0.012), (x + w + gap, hi_, 0.012), (x, hi_, 0.012), 'walk' if rng.random() < 0.22 else 'yard')
                        st.box((x - 0.1, lo_, 0.0), (x + 0.1, hi_, rng.uniform(1.8, 2.3)), wall_m, skip='z-y-y+', top='concrete')
                        if depth > 2.4:
                            cx_, cy_ = x + rng.uniform(1.5, max(1.6, w - 1.5)), yback + dy * rng.uniform(1.2, max(1.3, depth - 1.2))
                            k = rng.random()
                            if k < 0.26:
                                parts['trees'].append(put_tree(f'tree.{n_i:05d}', cx_, cy_, rng.uniform(0, 6.28), rng))
                            elif k < 0.46:
                                put(f'palm.{n_i:05d}', palms[rng.randrange(len(palms))], cx_, cy_, rng.uniform(0, 6.28), kind='palms')
                            elif k < 0.54 and depth > 5.0 and w > 6.0:
                                put(f'car.{n_i:05d}', cars[rng.randrange(len(cars))], x + w / 2, yback + dy * depth / 2, rng.choice((0.0, math.pi)) + rng.uniform(-0.1, 0.1), kind='cars')
                            elif k < 0.64 and depth > 3.2:          # a shed against the back wall, a sheet of zinc for its roof
                                sx_, sw_ = x + rng.uniform(0.3, max(0.4, w - 4.0)), rng.uniform(2.4, 3.6)
                                ya_, yb_ = sorted((ym - dy * 0.2, ym - dy * min(2.6, depth - 0.4)))
                                st.box((sx_, ya_, 0.0), (sx_ + sw_, yb_, 2.1), 'block', skip='z-')
                                st.box((sx_ - 0.2, ya_ - 0.2, 2.1), (sx_ + sw_ + 0.2, yb_ + 0.2, 2.16), 'zinc_old')
                            elif k < 0.80:
                                K.junk(st, rng, cx_, cy_, 0.0)
                            elif k < 0.90 and depth > 3.0:
                                K.washing(st, rng, (x + 0.8, cy_), (x + min(w - 0.8, 5.5), cy_), 0.0, lines=1)
                            n_i += 1
                            if rng.random() < 0.04:                 # a child's bicycle, left where it was dropped
                                bx, by = x + rng.uniform(1.0, w - 1.0), yback + dy * rng.uniform(0.6, 1.2)
                                o = put(f'bicycle.{n_i:05d}', bikes[rng.randrange(2)], bx, by, 0.0, 0.15)
                                o.rotation_euler = (math.radians(82.0), 0.0, rng.uniform(0, 6.28))
                    if gap > 0.0 and not in_square:                 # the passage beside it: closed at the street by a wall and a steel gate
                        yf0, yf1 = sorted((yy, yy + dy * 0.2))
                        st.box((x + w, yf0, 0.0), (x + w + gap, yf1, 2.2), wall_m, skip='z-x-x+', top='concrete')
                        st.box((x + w + 0.15, yf0 - 0.03, 0.05), (x + w + gap - 0.15, yf0 + 0.02, 1.95), rng.choice(('door_green', 'door_blue', 'door_grey', 'door_rust')), skip='y+')
                    x += w + gap
    log(f'[town] {n_b} buildings placed on {len(YST) - 1} rows of blocks, {len(xstreets)} cross streets ({time.time() - t0:.1f} s)')
    # ---------------------------------------------------------------- the mosque on its square; the market beside it
    rng = R(8)
    if mq is not None:
        put('mosque', ST.mosque(rng).mesh('mosque', M), mq[0] + 20.0, mq[2] + 12.0, 0.0)
        st.box((mq[0], mq[2], 0.0), (mq[1], mq[3], 0.12), 'walk', skip='z-')
        for k in range(6):
            put(f'palm.sq{k}', palms[k % len(palms)], mq[0] + 4.0 + k * 9.6 + rng.uniform(-1.0, 1.0), mq[2] + 2.2 + (k % 2) * 1.2, rng.uniform(0, 6.28), kind='palms')
        for k in range(9):                                           # stalls down the square's open side and along its street
            put(f'stall.sq{k}', stalls[rng.randrange(len(stalls))], mq[1] - 4.0 - (k % 2) * 4.4 + rng.uniform(-0.4, 0.4), mq[2] + 7.0 + (k // 2) * 5.6 + rng.uniform(-0.5, 0.5),
                math.pi / 2 * (1 if k % 2 else -1) + rng.uniform(-0.12, 0.12), 0.12, kind='stalls')
        ys_ = max((s for s in YST if s[0] < mq[2]), key=lambda s: s[0], default=None)
        if ys_ is not None:
            for k in range(7):
                put(f'stall.st{k}', stalls[rng.randrange(len(stalls))], mq[0] - 40.0 + k * 4.8 + rng.uniform(-0.5, 0.5), ys_[0] + ys_[1] / 2 - 1.3,
                    rng.uniform(-0.1, 0.1), 0.03, kind='stalls')         # (along the street's edge, on its asphalt)
    # ---------------------------------------------------------------- poles and their wires; lamps; cars; palms
    rng = R(9)
    for yc, wd in YST:
        main = wd > 9
        prev = None
        x = -ex_ / 2 + rng.uniform(0, 20)
        py = yc + wd / 2 + 0.7
        while x < ex_ / 2:
            if any(abs(x - xc) < xw / 2 + 1.0 for xc, xw in xstreets):
                x += 4.0
            fallen = strikes and struck(x, py) < 0.55 and rng.random() < 0.6
            kind = rng.choice(('plain', 'plain', 'plain', 'transformer', 'lamp', 'lamp')) if not main else rng.choice(('plain', 'plain', 'transformer'))
            o = put(f'pole.{int(x)}.{int(yc)}', poles[kind], x, py, kind='poles')
            if fallen:                                               # brought down across the street, its wires with it
                o.rotation_euler = (math.radians(rng.uniform(62.0, 84.0)) * rng.choice((-1, 1)), 0.0, rng.uniform(-0.5, 0.5))
                prev = None
            else:
                if prev is not None:
                    for dy, z in ((-0.8, 9.1), (0.0, 9.62), (0.8, 9.1), (-0.5, 8.36), (0.5, 8.36)):
                        st.path(catenary((prev, py + dy, z), (x, py + dy, z), rng.uniform(0.35, 0.9), 6), 0.014, 'wire', n=3)
                prev = x
                for q in range(rng.randrange(0, 3)):                 # a line down to a house on each side
                    side = rng.choice((0, 1))
                    hits = [f for f in rows.get((yc, 1 - side), []) if f[0] - 4.0 < x < f[1] + 4.0]
                    if hits:
                        f = hits[0]
                        tx = min(max(x + rng.uniform(-5.0, 5.0), f[0] + 0.5), f[1] - 0.5)
                        st.path(catenary((x, py, 8.3), (tx, f[2], min(f[3] - 0.3, rng.uniform(3.5, 7.5))), rng.uniform(0.3, 0.8), 5), 0.008, 'wire', n=3)
            x += rng.uniform(26.0, 34.0)
        if main:                                                     # the main road's median: kerbed, a lamp every 32 m, a palm between
            edges = sorted([-PX] + [e for xc, xw in xstreets for e in (xc - xw / 2 - 1.5, xc + xw / 2 + 1.5)] + [PX])
            for a, e in zip(edges[::2], edges[1::2]):
                if e - a < 3.0:
                    continue
                st.box((a, yc - 0.42, 0.0), (e, yc + 0.42, 0.18), 'median', skip='z-')
                st.run([(a, yc - 0.6), (e, yc - 0.6), (e, yc + 0.6), (a, yc + 0.6)], 0.18, 0.0, 0.2, 'kerb:y', closed=True)
                xl = a + rng.uniform(4.0, 10.0)
                while xl < e - 3.0:
                    if struck(xl, yc) > 0.35:
                        put(f'lamp.{int(xl)}', lamp, xl, yc, kind='lamps')
                    xp = xl + 16.0 + rng.uniform(-3.0, 3.0)
                    if xp < e - 2.0 and rng.random() < 0.6 and struck(xp, yc) > 0.5:
                        put(f'palm.med{int(xp)}', palms[rng.randrange(len(palms))], xp, yc, rng.uniform(0, 6.28), 0.15, kind='palms')
                    xl += 32.0
        x = -ex_ / 2 + rng.uniform(0, 15)
        while x < ex_ / 2:                                           # cars at the kerb, a few on the move; wrecks where it struck
            near = struck(x, yc)
            burnt = bool(wrecks) and near < 1.0 and rng.random() < 0.6
            side = rng.choice((-1, 1))
            if burnt:
                put(f'car.{int(x)}.{int(yc)}', wrecks[rng.randrange(len(wrecks))], x, yc + rng.uniform(-wd / 3, wd / 3), rng.uniform(0, 6.28), kind='cars')['tn_dust'] = 1.0
            elif near > 0.5:
                moving = rng.random() < (0.3 if main else 0.12)
                off = (wd / 4 + (0.3 if main else 0.0)) if moving else (wd / 2 - 1.15)
                put(f'car.{int(x)}.{int(yc)}', cars[rng.randrange(len(cars))], x, yc + side * off, (math.pi if side > 0 else 0.0) + rng.uniform(-0.04, 0.04), 0.03, kind='cars')
            x += rng.uniform(8.0, 36.0) * (0.6 if main else 1.0)
    # ---------------------------------------------------------------- where it struck: the street cratered, strewn with what was thrown
    rng = R(11)
    for sx, sy, sr in strikes:
        yc, wd = min(YST, key=lambda s: abs(s[0] - sy))
        for q in range(2):                                           # one crater in the nearest street, one where it fell
            cx_, cy_ = (sx + rng.uniform(-0.3, 0.3) * sr, yc + rng.uniform(-0.25, 0.25) * wd) if q == 0 else (sx + rng.uniform(-0.4, 0.4) * sr, sy + rng.uniform(-0.4, 0.4) * sr)
            crater(st, rng, cx_, cy_, rng.uniform(1.8, 3.2))
        for _ in range(rng.randrange(5, 9)):                         # what the buildings shed into the street
            a, d = rng.uniform(0.0, 6.283), sr * rng.uniform(0.15, 0.9)
            px, py = sx + d * math.cos(a), sy + d * math.sin(a)
            if any(abs(py - s[0]) < s[1] / 2 + 2.5 for s in YST) or any(abs(px - s[0]) < s[1] / 2 + 1.0 for s in xstreets):
                K.heap(st, rng, px, py, rng.uniform(1.4, 3.0), rng.uniform(1.2, 2.4), rng.uniform(0.35, 0.9), 0.03, pieces=rng.randrange(10, 22), plates=rng.randrange(0, 2))
    if strikes:
        ym_ = max(YST, key=lambda s: s[1])                           # a line of blast walls on the main road, east of the middle
        for k in range(9):
            put(f't_wall.{k}', twall, 0.467 * ex_ / 2 + (k % 5) * 1.24, ym_[0] + (ym_[1] / 2 + 0.9) * (1 if k < 5 else -1), 0.0, 0.14)
    # ---------------------------------------------------------------- the town's edge: it thins out, it does not stop
    rng = R(12)
    X0, X1, Y0, Y1 = -ex_ / 2 - 34.0, ex_ / 2 + 34.0, -ey / 2 - 14.0, ey / 2 + 14.0
    taken = []
    EDGE = float(edge)

    def edge_spot(reach, r_):
        """a place past the town's edge, likelier near it than far; r_: the room the thing needs"""
        for _ in range(30):
            d = EDGE * rng.random() ** 1.6 * reach + 6.0
            if rng.random() < (ex_ + 2 * d) / (ex_ + ey + 4 * d):
                x_, y_ = rng.uniform(X0 - d, X1 + d), (Y1 + d if rng.random() < 0.5 else Y0 - d)
            else:
                x_, y_ = (X1 + d if rng.random() < 0.5 else X0 - d), rng.uniform(Y0 - d, Y1 + d)
            if any(abs(y_ - s[0]) < s[1] / 2 + r_ and (x_ < X0 or x_ > X1) for s in YST) or any(abs(x_ - s[0]) < s[1] / 2 + r_ and (y_ < Y0 or y_ > Y1) for s in xstreets):
                continue                                             # (the roads run out through here)
            if all(math.hypot(x_ - tx, y_ - ty) > r_ + tr for tx, ty, tr in taken):
                taken.append((x_, y_, r_))
                return x_, y_
        return None
    # the streets run on out of the town as tracks, and the houses run on along them, fewer and further apart, each on
    # its walled lot: a town's edge is its own streets going on until nobody has built there yet
    lots = []

    def lot_free(bx):
        return all(bx[2] + 1.5 < q[0] or bx[0] - 1.5 > q[2] or bx[3] + 1.5 < q[1] or bx[1] - 1.5 > q[3] for q in lots)

    def along_track(axis, c0, wd, start, sgn, length):
        """axis 'x': a track along x at y = c0, leaving the town at x = start toward sgn; 'y': the same, turned"""
        for side in (-1, 1):
            s = rng.uniform(1.0, 12.0)
            while s < length - 12.0:
                keep = (1.0 - s / length) ** 1.3
                if rng.random() > 0.12 + 0.7 * keep:
                    s += rng.uniform(8.0, 26.0)
                    continue
                pick = pools['C'][rng.randrange(len(pools['C']))] if rng.random() < 0.8 else pools['B'][rng.randrange(len(pools['B']))]
                w, d = pick[2], pick[3]
                off = wd * 0.5 + rng.uniform(1.0, 3.5)              # from the track's middle to its front
                a = start + sgn * s if sgn > 0 else start + sgn * (s + w)
                if axis == 'x':
                    bx, at, front = ((a, c0 + off, a + w, c0 + off + d), (a, c0 + off, 0.0), 'S') if side > 0 else ((a, c0 - off - d, a + w, c0 - off), (a + w, c0 - off, math.pi), 'N')
                else:
                    bx, at, front = ((c0 + off, a, c0 + off + d, a + w), (c0 + off, a + w, -math.pi / 2), 'W') if side > 0 else \
                        ((c0 - off - d, a, c0 - off, a + w), (c0 - off, a, math.pi / 2), 'E')
                ms, mb = rng.uniform(0.8, 3.0), rng.uniform(2.5, 9.0)
                lot = {'S': (bx[0] - ms, bx[1], bx[2] + ms, bx[3] + mb), 'N': (bx[0] - ms, bx[1] - mb, bx[2] + ms, bx[3]),
                       'W': (bx[0], bx[1] - ms, bx[2] + mb, bx[3] + ms), 'E': (bx[0] - mb, bx[1] - ms, bx[2], bx[3] + ms)}[front]
                if not lot_free(lot):
                    s += rng.uniform(4.0, 10.0)
                    continue
                lots.append(lot)
                taken.append(((lot[0] + lot[2]) / 2, (lot[1] + lot[3]) / 2, 0.55 * max(lot[2] - lot[0], lot[3] - lot[1])))
                house_at(pick, at[0], at[1], at[2], in_town=False)
                c_ = [(lot[0], lot[1]), (lot[2], lot[1]), (lot[2], lot[3]), (lot[0], lot[3])]
                u_path = {'S': (1, 2, 3, 0), 'N': (3, 0, 1, 2), 'W': (0, 1, 2, 3), 'E': (2, 3, 0, 1)}[front]       # its wall: round three sides, open to the track
                st.run([c_[q] for q in u_path], 0.2, 0.0, rng.uniform(1.5, 2.2), rng.choice(('block', 'block', 'plaster_w', 'brick')), top='concrete')
                g.quad((lot[0], lot[1], 0.012), (lot[2], lot[1], 0.012), (lot[2], lot[3], 0.012), (lot[0], lot[3], 0.012), 'yard')
                k = rng.random()
                px, py = rng.uniform(lot[0] + 1.0, lot[2] - 1.0), rng.uniform(lot[1] + 1.0, lot[3] - 1.0)
                if not (bx[0] - 1.0 < px < bx[2] + 1.0 and bx[1] - 1.0 < py < bx[3] + 1.0):
                    if k < 0.4:
                        put(f'palm.e{len(lots)}', far_palms[rng.randrange(len(far_palms))], px, py, rng.uniform(0, 6.28), kind='palms')
                    elif k < 0.6:
                        parts['trees'].append(put_tree(f'tree.e{len(lots)}', px, py, rng.uniform(0, 6.28), rng))
                    elif k < 0.75:
                        K.junk(st, rng, px, py, 0.0)
                s += w + 2 * ms + rng.uniform(0.5, 8.0)
    x_lo, x_hi = xstreets[0][0] - xstreets[0][1] / 2 - 2.0, xstreets[-1][0] + xstreets[-1][1] / 2 + 2.0     # where the town's last blocks end
    for yc, wd in YST:
        for sgn in (-1.0, 1.0):
            length = EDGE * rng.uniform(0.55, 1.0)
            a, e = sorted((sgn * PX, sgn * (PX + length)))
            g.quad((a, yc - wd * 0.35, 0.02), (e, yc - wd * 0.35, 0.02), (e, yc + wd * 0.35, 0.02), (a, yc + wd * 0.35, 0.02), 'track')
            start = x_hi if sgn > 0 else x_lo
            along_track('x', yc, wd, start, sgn, length + PX - abs(start))
    for xc, wd in xstreets:
        for sgn in (-1.0, 1.0):
            length = EDGE * rng.uniform(0.35, 0.95)
            a, e = sorted((sgn * PY, sgn * (PY + length)))
            g.quad((xc - wd * 0.35, a, 0.02), (xc + wd * 0.35, a, 0.02), (xc + wd * 0.35, e, 0.02), (xc - wd * 0.35, e, 0.02), 'track:y')
            along_track('y', xc, wd, sgn * (ey / 2 + 14.0), sgn, length)
    n_plots = max(1, int(round(26 * (ex_ + ey) * EDGE / ((840.0 + 300.0) * 170.0))))
    for k in range(n_plots):                                         # walled plots: something growing, or nothing yet
        w, d = rng.uniform(18.0, 46.0), rng.uniform(16.0, 40.0)
        p = edge_spot(1.0, max(w, d) * 0.6)
        if not p:
            continue
        if rng.random() < 0.7:
            st.run([(p[0] - w / 2, p[1] - d / 2), (p[0] + w / 2, p[1] - d / 2), (p[0] + w / 2, p[1] + d / 2), (p[0] - w / 2, p[1] + d / 2)], 0.25, 0.0, rng.uniform(0.9, 1.7),
                   rng.choice(('block', 'brick', 'plaster_w')), closed=True, top='concrete')
        fm = rng.choice(('field', 'field', 'field_dry', 'yard'))
        nrow = max(2, int(w / rng.uniform(4.0, 8.0)))
        for q in range(nrow):                                        # its beds, with the paths between them
            xa_, xb_ = p[0] - w / 2 + 1.0 + (w - 2.0) * q / nrow, p[0] - w / 2 + 1.0 + (w - 2.0) * (q + 1) / nrow - 0.7
            g.quad((xa_, p[1] - d / 2 + 1.0, 0.015), (xb_, p[1] - d / 2 + 1.0, 0.015), (xb_, p[1] + d / 2 - 1.0, 0.015), (xa_, p[1] + d / 2 - 1.0, 0.015), fm)
        for q in range(rng.randrange(0, 5)):
            put(f'palm.f{k}.{q}', far_palms[rng.randrange(len(far_palms))], p[0] + rng.uniform(-w / 2, w / 2), p[1] + rng.choice((-1, 1)) * (d / 2 - 1.0), rng.uniform(0, 6.28), kind='palms')
    for k in range(max(1, int(round(7 * n_plots / 26.0)))):         # palm groves
        p = edge_spot(0.9, 22.0)
        if not p:
            continue
        for q in range(rng.randrange(9, 17)):
            a, d = rng.uniform(0.0, 6.283), 20.0 * math.sqrt(rng.random())
            put(f'palm.g{k}.{q}', far_palms[rng.randrange(len(far_palms))], p[0] + d * math.cos(a), p[1] + d * math.sin(a), rng.uniform(0, 6.28), kind='palms')
    ground = put('town_ground', g.mesh('town_ground', M), 0.0, 0.0)
    streets = put('town_streets', st.mesh('town_streets', M), 0.0, 0.0)
    log(f'[town] streets, edge and ground ({time.time() - t0:.1f} s)')
    # every placed thing its own number for how near a strike it stands (its materials lay the strike's fall on it by
    # that); the masks from the geometry; the CC0 things a town leaves about; the dust in the air
    for o in c.objects:
        if o.get('tn_dust') is None:
            o['tn_dust'] = 0.0 if o.name in ('town_ground', 'town_streets') else max(0.0, min(1.0, 1.15 - struck(o.location.x, o.location.y) / 1.2))
    if masks:
        from . import masks as MK
        MK.annotate(c, log)
    counts = {}
    if things:
        from . import things as TH
        counts = TH.place(c, parent, R(13), strikes, YST, mq, log)
    air_o = None
    if air:
        from . import world as TW
        air_o = TW.air(c, parent)
    meshes = {o.data for o in c.all_objects if o.type == 'MESH' and o.name != 'town_air'}
    placed = sum(len(o.data.polygons) for o in c.all_objects if o.type == 'MESH' and o.name != 'town_air')
    stats = dict(buildings=n_b, objects=len(c.all_objects), meshes=len(meshes), unique_faces=sum(len(m.polygons) for m in meshes),
                 placed_faces=placed, strikes=len(strikes), yard_trees=tree_kind, things=counts, seconds=round(time.time() - t0, 1))
    log(f'[town] built: {stats}')
    return Town(group=parent, collection=c, parts=dict(parts, ground=ground, streets=streets, air=air_o), strikes=strikes,
                ystreets=YST, xstreets=xstreets, mosque=mq, paved=tuple(MT.PAVED), extent=(ex_, ey), seed=seed, stats=stats)
