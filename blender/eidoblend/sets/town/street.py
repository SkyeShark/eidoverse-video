"""eidoblend.sets.town.street: what stands in the town's streets and yards. Blender (mathutils); each function returns
a mesh builder (mb.MB). Metres; each thing in its own space, standing on z = 0.

    car(kind, burnt)      a saloon, a pickup, a van: ONE lofted body each: sections along its length with a sill, a
                          waist, a belt line and a narrower roof, its wheel arches cut in the sill line, its screens and
                          side glass as the body's own faces, wheels in the arches (what a car is from 70 m: a pale body,
                          a dark screen at each end of a paler roof); burnt: a shell sitting on its rims
    palm(rng, light)      a date palm: a thin ringed trunk and a BALL of sixty fronds set round it by the golden angle,
                          the young ones standing, the old ones hanging, each a rachis with its leaflets in a V along it;
                          a few bunches of dates; light: fewer fronds and leaflets, for the far edge
    tree(rng)             a broad-leaved yard tree: a rounded crown of several masses with a broken edge of leaf sprays
    dish()                an offset dish on its pole, its feed on its arm
    pole(rng), lamp_post(two)   a concrete pole with its arms and insulators (a transformer on some); a road's lamp
    mosque(rng)           a neighbourhood mosque: a hall with pointed windows, a portal, a pointed dome on its drum and
                          two small ones, a minaret with its gallery and cap, a walled yard
    stall(rng), bicycle(), t_wall()   a market stall under its awning; a child's bicycle; a blast wall's section
"""
import math

from mathutils import Vector

from . import kit as K
from .mb import MB, catenary, place


def lerp_tab(tab, x):
    if x <= tab[0][0]:
        return tab[0][1]
    for (x0, v0), (x1, v1) in zip(tab, tab[1:]):
        if x <= x1:
            return v0 + (v1 - v0) * (x - x0) / (x1 - x0)
    return tab[-1][1]


# ================================================================================================ cars
CARS = {
    'saloon': dict(
        axles=(-1.35, 1.35), wr=0.31, track=0.74,
        zl=[(-2.2, 0.78), (-2.1, 0.88), (-1.25, 0.93), (-1.05, 0.90), (0.95, 0.88), (1.1, 0.85), (2.0, 0.74), (2.2, 0.62)],
        zr=[(-2.2, 0.80), (-2.1, 0.90), (-1.25, 0.95), (-0.7, 1.40), (0.3, 1.42), (0.95, 0.90), (1.1, 0.87), (2.0, 0.76), (2.2, 0.64)],
        hr=[(-2.2, 0.60), (-2.1, 0.76), (-1.25, 0.76), (-0.7, 0.62), (0.3, 0.62), (0.95, 0.76), (2.0, 0.74), (2.2, 0.58)],
        hw=[(-2.2, 0.68), (-2.1, 0.83), (-1.0, 0.85), (1.0, 0.85), (2.0, 0.82), (2.2, 0.66)],
        st=[-2.2, -2.1, -1.9, -0.7, -0.3, -0.22, 0.3, 0.62, 0.95, 1.9, 2.05, 2.2], top_glass=((-1.25, -0.7), (0.3, 0.95)), side_glass=((-0.7, -0.3), (-0.22, 0.3))),
    'pickup': dict(
        axles=(-1.6, 1.6), wr=0.36, track=0.76, cab_back=-0.25,
        zl=[(-0.25, 1.0), (1.55, 1.0), (1.7, 0.98), (2.45, 0.88), (2.6, 0.76)],
        zr=[(-0.25, 1.70), (1.0, 1.72), (1.55, 1.03), (1.7, 1.0), (2.45, 0.9), (2.6, 0.78)],
        hr=[(-0.25, 0.66), (1.0, 0.66), (1.55, 0.78), (2.45, 0.76), (2.6, 0.62)],
        hw=[(-0.25, 0.87), (1.5, 0.87), (2.45, 0.84), (2.6, 0.7)],
        st=[-0.25, 0.28, 0.36, 1.0, 1.28, 1.55, 2.3, 2.47, 2.6], top_glass=((1.0, 1.55),), side_glass=((-0.25, 0.28), (0.36, 1.0))),
    'van': dict(
        axles=(-1.45, 1.5), wr=0.33, track=0.78,
        zl=[(-2.45, 1.0), (1.55, 1.05), (2.0, 1.0), (2.35, 0.9), (2.45, 0.7)],
        zr=[(-2.45, 1.86), (-2.3, 1.94), (1.45, 1.95), (2.05, 1.08), (2.35, 0.94), (2.45, 0.72)],
        hr=[(-2.45, 0.78), (1.45, 0.78), (2.05, 0.82), (2.45, 0.66)],
        hw=[(-2.45, 0.86), (-2.35, 0.9), (2.0, 0.9), (2.35, 0.86), (2.45, 0.72)],
        st=[-2.45, -2.35, -0.6, -0.52, 0.4, 0.48, 1.45, 1.75, 2.05, 2.3, 2.45], top_glass=((1.45, 2.05),), side_glass=((-2.1, -0.6), (-0.52, 0.4), (0.48, 1.45))),
}


def car(kind='saloon', burnt=False, load=None, rng=None):
    S = CARS[kind]
    b = MB()
    PA, GL = ('car_burnt', 'car_in') if burnt else ('car', 'car_glass')
    sink = 0.13 if burnt else 0.0                                  # (a burnt car sits on its rims)
    base, zc, r_arch = 0.2, S['wr'], S['wr'] + 0.07

    def zb(x):
        z = base
        for xa in S['axles']:
            if abs(x - xa) < r_arch:
                z = max(z, zc + math.sqrt(r_arch ** 2 - (x - xa) ** 2))
        return z
    xs = set(S['st'])
    for xa in S['axles']:
        for q in (-0.97, -0.72, -0.38, 0.0, 0.38, 0.72, 0.97):
            xs.add(round(xa + q * r_arch, 3))
    x_lo, x_hi = S['st'][0], S['st'][-1]
    xs = sorted(x for x in xs if x_lo <= x <= x_hi)
    rings = []
    for x in xs:
        hw, hr, zl, zr = lerp_tab(S['hw'], x), lerp_tab(S['hr'], x), lerp_tab(S['zl'], x), lerp_tab(S['zr'], x)
        end = min(x - x_lo, x_hi - x)
        zbb = zb(x) + (0.12 if end < 0.05 else 0.0)
        right = [(0.0, zbb), (0.8 * hw, zbb), (hw, min(zbb + 0.13, zl - 0.1)), (hw, min(max(zbb + 0.2, 0.6), zl - 0.04)), (0.965 * hw, zl), (hr, max(zl + 0.01, zr - 0.06)),
                 (0.72 * hr, zr), (0.0, zr)]
        ring = [(x, y, z - sink) for y, z in right] + [(x, -y, z - sink) for y, z in right[-2:0:-1]]
        rings.append(ring)
    n = len(rings[0])
    base_i = b.verts([p for r in rings for p in r])

    def inside(x0, x1, spans):
        return any(a - 1e-6 <= x0 and x1 <= c + 1e-6 for a, c in spans)
    for s in range(len(xs) - 1):
        tg, sg = inside(xs[s], xs[s + 1], S['top_glass']), inside(xs[s], xs[s + 1], S['side_glass'])
        for k in range(n):
            if k in (0, n - 1):
                m = 'steel_dark'
            elif k in (4, 9):
                m = GL if sg else PA                               # (beside a screen this strip is the pillar)
            elif k in (5, 6, 7, 8):
                m = GL if tg else PA
            else:
                m = PA
            a, c = base_i + s * n + k, base_i + s * n + (k + 1) % n
            b.face((a, c, c + n, a + n), m, True)
    b.poly(rings[-1], PA)                                          # its nose
    if 'cab_back' in S:                                            # a pickup: the cab's back, its window; then the bed
        back = rings[0]
        b.poly(reversed(back), PA)
        x = S['cab_back'] - 0.005
        b.quad((x, 0.5, 1.12 - sink), (x, -0.5, 1.12 - sink), (x, -0.5, 1.55 - sink), (x, 0.5, 1.55 - sink), GL)
        x0, x1, zf_, zt = -2.6, S['cab_back'], 0.62 - sink, 1.04 - sink
        b.box((x0, -0.80, zf_ - 0.04), (x1, 0.80, zf_), 'car_bed', skip='z-')
        for sy in (-1, 1):
            b.box((x0, min(sy * 0.8, sy * 0.87), 0.46 - sink), (x1, max(sy * 0.8, sy * 0.87), zt), PA, skip='x+')
        b.box((x0 - 0.05, -0.87, 0.5 - sink), (x0, 0.87, zt), PA)
        b.box((x0 + 0.1, -0.55, 0.3 - sink), (x1, 0.55, zf_ - 0.04), 'steel_dark', skip='z+x+')
        if load and rng is not None:                               # what it carries
            for _ in range(rng.randrange(3, 7)):
                px, py = rng.uniform(x0 + 0.4, x1 - 0.4), rng.uniform(-0.5, 0.5)
                if load == 'sacks':
                    b.lathe([(0.02, 0.0), (0.26, 0.05), (0.3, 0.16), (0.24, 0.27), (0.02, 0.3)], (px, py, zf_ + rng.uniform(0.0, 0.25)), 'sack', n=8)
                elif load == 'barrels':
                    K.barrel(b, px, py, zf_, rng.choice(('barrel_blue', 'barrel_rust')))
                else:
                    s_ = rng.uniform(0.35, 0.6)
                    b.box((px - s_ / 2, py - s_ / 2, zf_), (px + s_ / 2, py + s_ / 2, zf_ + s_ * rng.uniform(0.6, 1.0)), rng.choice(('cardboard', 'crate', 'wood_pale')), skip='z-')
    else:
        b.poly(reversed(rings[0]), PA)
    hwf, hwb = lerp_tab(S['hw'], x_hi), lerp_tab(S['hw'], -2.6 if 'cab_back' in S else x_lo)
    xb = -2.65 if 'cab_back' in S else x_lo
    b.box((x_hi - 0.02, -hwf - 0.06, 0.3 - sink), (x_hi + 0.09, hwf + 0.06, 0.5 - sink), 'bumper', skip='x-')
    b.box((xb - 0.09, -hwb - 0.06, 0.3 - sink), (xb + 0.02, hwb + 0.06, 0.5 - sink), 'bumper', skip='x+')
    zh = lerp_tab(S['zl'], x_hi) - 0.05 - sink
    for sy in (-1, 1):
        b.box((x_hi - 0.03, sy * hwf * 0.9 - 0.14, zh - 0.07), (x_hi + 0.012, sy * hwf * 0.9 + 0.14, zh + 0.05), 'car_in' if burnt else 'lamp_clear', skip='x-')
        b.box((xb - 0.012, sy * hwb * 0.92 - 0.1, 0.62 - sink), (xb + 0.03, sy * hwb * 0.92 + 0.1, 0.8 - sink), 'car_in' if burnt else 'lamp_red', skip='x+')
    r = S['wr'] * (0.62 if burnt else 1.0)
    for xa in S['axles']:
        for sy in (-1, 1):
            M = place((xa, sy * S['track'], r), 0.0, math.pi / 2.0)
            if burnt:
                b.lathe([(0.05, -0.08), (r, -0.09), (r, 0.09), (0.05, 0.08)], (0.0, 0.0, 0.0), 'car_burnt', n=12, M=M)
            else:
                b.lathe([(r * 0.62, -0.1), (r * 0.93, -0.105), (r, -0.06), (r, 0.06), (r * 0.93, 0.105), (r * 0.62, 0.1)], (0.0, 0.0, 0.0), 'tyre', n=14, M=M)
                b.lathe([(0.02, -0.085 * sy), (r * 0.6, -0.095 * sy)] if sy > 0 else [(r * 0.6, 0.095), (0.02, 0.085)], (0.0, 0.0, 0.0), 'hub', n=10, M=M)
    return b


# ================================================================================================ trees
def palm(rng, hgt=None, light=False):
    """light: a palm for the far edge of the town (fewer fronds, two leaflets a length where the near ones have
    three: a lighter level built as such, not decimated)"""
    b = MB()
    hgt = hgt or rng.uniform(6.5, 11.5)
    lean = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), 0.0)) * rng.uniform(0.0, 0.9)
    n = 16
    pts = [Vector((0, 0, -0.2)) + lean * (s / n) ** 2 + Vector((0, 0, (hgt + 0.2) * s / n)) for s in range(n + 1)]
    b.path(pts, lambda t: (0.34 - 0.10 * min(1.0, t * 5.0)) * (1.0 - 0.12 * t) + (0.07 if t > 0.94 else 0.0), 'palm_trunk', n=9)
    top = pts[-1]
    N = rng.randrange(62, 78) if not light else rng.randrange(40, 48)
    per = 3 if not light else 2
    for k in range(N):
        q = k / (N - 1.0)                                          # 0 the youngest, at the heart; 1 the oldest, hanging
        az = k * 2.39996 + rng.uniform(-0.15, 0.15)                # the golden angle
        el = math.radians(80.0 - 132.0 * q ** 0.85 + rng.uniform(-7.0, 7.0))
        Lf = rng.uniform(3.3, 4.4) * (0.55 + 0.45 * min(1.0, q * 3.0))
        dead = q > 0.9 and rng.random() < 0.6
        m = 'frond_dead' if dead else ('frond_old' if q > 0.62 else 'frond')
        rad = Vector((math.cos(az), math.sin(az), 0.0))
        tan = Vector((-math.sin(az), math.cos(az), 0.0))
        nseg = 9
        p = top + rad * 0.22 + Vector((0, 0, 0.1 - 0.5 * q))
        spine = [p]
        droop = rng.uniform(0.9, 1.5) + (0.8 if dead else 0.0)
        for s in range(nseg):
            e = el - droop * ((s + 0.5) / nseg) ** 1.6
            p = p + (rad * math.cos(e) + Vector((0, 0, math.sin(e)))) * (Lf / nseg)
            spine.append(p)
        b.path(spine[::2] + ([spine[-1]] if nseg % 2 else []), lambda t: 0.028 - 0.02 * t, 'frond_old' if not dead else 'frond_dead', n=3)
        for s in range(nseg):
            a, c = spine[s], spine[s + 1]
            t = (c - a).normalized()
            up = t.cross(tan)                                      # the frond's own 'up': square to its rachis
            sfrac = (s + 0.5) / nseg
            ll = 0.52 * math.sin(math.pi * (0.12 + 0.86 * sfrac)) ** 0.7
            for j in range(per):
                o = a.lerp(c, (j + rng.uniform(0.2, 0.8)) / per)
                for sg in (-1.0, 1.0):
                    tip = o + (t * 0.55 + tan * sg * 0.75 + up * (0.34 - 0.5 * sfrac)).normalized() * ll * rng.uniform(0.85, 1.1) - Vector((0, 0, 0.1 * ll))
                    b.poly((o - t * (0.035 if not light else 0.055), o + t * (0.035 if not light else 0.055), tip), m)
    for k in range(rng.randrange(0, 5)):                           # bunches of dates under the crown
        az = rng.uniform(0.0, 6.283)
        rad = Vector((math.cos(az), math.sin(az), 0.0))
        p0 = top + rad * 0.25 - Vector((0, 0, 0.3))
        p1 = p0 + rad * rng.uniform(0.5, 0.9) - Vector((0, 0, rng.uniform(0.5, 1.0)))
        b.path([p0, p0.lerp(p1, 0.5) + Vector((0, 0, 0.2)), p1], 0.02, 'dates', n=3)
        b.lathe([(0.02, -0.42), (0.11, -0.32), (0.13, -0.12), (0.06, 0.0)], tuple(p1), 'dates', n=6)
    return b


def tree(rng):
    b = MB()
    hgt = rng.uniform(3.2, 5.5)
    top = Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), hgt * 0.55))
    b.path([Vector((0, 0, -0.1)), Vector((top.x * 0.3, top.y * 0.3, hgt * 0.3)), top], lambda t: 0.19 - 0.08 * t, 'trunk', n=7)
    masses = []
    for k in range(rng.randrange(4, 8)):
        a = rng.uniform(0.0, 6.283)
        d = rng.uniform(0.3, 1.5)
        c = top + Vector((d * math.cos(a), d * math.sin(a), rng.uniform(0.2, 1.7)))
        r = rng.uniform(1.0, 1.9)
        masses.append((c, r))
        b.path([top - Vector((0, 0, 0.3)), top.lerp(c, 0.6), c], lambda t: 0.09 - 0.05 * t, 'trunk', n=5)
        nu, nv = 10, 7
        P = []
        for j in range(1, nv):
            row = []
            for i in range(nu):
                th, ph = 2 * math.pi * i / nu, math.pi * j / nv
                rr = r * 0.9 * (1.0 + rng.uniform(-0.12, 0.12))
                row.append(c + Vector((rr * math.sin(ph) * math.cos(th), rr * math.sin(ph) * math.sin(th), 0.72 * rr * math.cos(ph))))
            P.append(row)
        base = b.grid(P[::-1], 'leaf', smooth=True, wrap_u=True)
        b.face([base + (nv - 2) * nu + i for i in range(nu)], 'leaf', True)
        b.face([base + i for i in reversed(range(nu))], 'leaf', True)
    # its leaves: sprays all over each mass and standing a little off it, each a twig's worth, turned every way, so
    # the crown's edge is leaves and light comes through it
    for c, r in masses:
        for _ in range(150):
            th, ph = rng.uniform(0.0, 6.283), math.acos(rng.uniform(-0.55, 1.0))
            d = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), 0.72 * math.cos(ph)))
            o = c + d * r * rng.uniform(0.9, 1.16)
            a1 = d.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))))
            if a1.length < 1e-3:
                continue
            a1.normalize()
            a2 = (d.cross(a1) + d * rng.uniform(-0.5, 0.5)).normalized()
            s = rng.uniform(0.16, 0.3)
            b.poly((o - a1 * s - a2 * s * 0.5, o + a1 * s - a2 * s * 0.5, o + a2 * s * 1.3), 'leaf' if rng.random() < 0.85 else 'leaf_dry')
    return b


# ================================================================================================ small things
def dish(dark=False, size=1.0):
    """an offset dish on its pole: built looking along -y and up; the town turns every one the same way"""
    b = MB()
    m = 'dish_dark' if dark else 'dish'
    b.tube((0.0, 0.06, 0.0), (0.0, 0.06, 0.95), 0.028, 'steel_dark', n=6)
    c = Vector((0.0, -0.1, 1.02))
    M = place(c, 0.0, math.radians(52.0), 0.0, size)
    R = 0.5
    b.lathe([(0.03, 0.0003), (0.2, 0.0125), (0.36, 0.04), (R, 0.078)], (0.0, 0.0, 0.0), m, n=16, M=M)
    b.lathe([(R, 0.078), (R + 0.012, 0.07), (R, 0.062)], (0.0, 0.0, 0.0), m, n=16, M=M)       # its rolled rim
    b.box((-0.07, -0.02, 0.9), (0.07, 0.1, 1.06), 'steel_dark')                              # the clamp behind it
    a, f = M @ Vector((0.0, -R, 0.078)), M @ Vector((0.0, -0.12, 0.66))
    b.beam(a, f, 0.02, 0.02, 'steel_dark')
    b.lathe([(0.03, -0.05), (0.035, 0.0), (0.03, 0.07), (0.015, 0.09)], (0.0, 0.0, 0.0), 'plastic_white', n=6, M=place(f, 0.0, math.radians(52.0 + 180.0)))
    return b


def pole(rng, kind='plain'):
    """a concrete pole 9.5 m: two arms across the street's line with their insulators; some carry a transformer, some
    a lamp on an arm. Its wires hang from (0, -0.8 | 0 | 0.8, 9.1) and (0, -0.5 | 0.5, 8.35): the layout strings them"""
    b = MB()
    b.tube((0, 0, -0.3), (0, 0, 9.5), 0.17, 'pole', n=8, r1=0.10)
    for z, half in ((8.95, 0.9), (8.2, 0.6)):
        b.beam((0, -half, z), (0, half, z), 0.07, 0.07, 'steel_dark')
        for sy in (-1, 1):
            b.beam((0.0, sy * half * 0.7, z), (0.0, sy * 0.1, z - 0.45), 0.012, 0.04, 'steel_dark')
    for y, z in ((-0.8, 8.95), (0.0, 9.5), (0.8, 8.95), (-0.5, 8.2), (0.5, 8.2)):
        b.lathe([(0.03, 0.0), (0.05, 0.04), (0.03, 0.07), (0.05, 0.1), (0.02, 0.14)], (0.0, y, z + 0.035 if z < 9.4 else z - 0.04), 'insulator', n=6)
    if kind == 'transformer':
        b.beam((-0.45, -0.3, 5.6), (0.45, -0.3, 5.6), 0.06, 0.06, 'steel_dark')
        b.beam((-0.45, 0.3, 5.6), (0.45, 0.3, 5.6), 0.06, 0.06, 'steel_dark')
        b.box((0.2, -0.28, 5.63), (0.78, 0.28, 6.5), 'zinc_old')
        for q in range(5):                                         # its cooling fins
            b.box((0.78, -0.24 + q * 0.12, 5.7), (0.86, -0.22 + q * 0.12, 6.4), 'zinc_old', skip='x-')
        for q in (-0.15, 0.0, 0.15):
            b.lathe([(0.03, 0.0), (0.05, 0.06), (0.03, 0.12), (0.05, 0.18), (0.015, 0.24)], (0.5, q, 6.5), 'insulator', n=6)
            b.path([Vector((0.5, q, 6.74)), Vector((0.25, q * 2.0, 7.6)), Vector((0.0, q * 3.3, 8.2))], 0.008, 'wire', n=3)
    elif kind == 'lamp':
        side = rng.choice((-1.0, 1.0))
        b.path([Vector((0, 0, 7.6)), Vector((0, side * 0.5, 8.0)), Vector((0, side * 1.2, 8.15)), Vector((0, side * 1.8, 8.12))], 0.03, 'steel_dark', n=5)
        b.box((-0.13, side * 1.8 - 0.32, 8.03), (0.13, side * 1.8 + 0.32, 8.14), 'lamp_head', mats={'z-': 'lamp_clear'})
    return b


def lamp_post(two=True):
    """a road's lamp: a tapered steel column of 9 m, one arm or two over the lanes, a lantern at each"""
    b = MB()
    b.box((-0.2, -0.2, 0.0), (0.2, 0.2, 0.25), 'concrete', skip='z-')
    b.tube((0, 0, 0.2), (0, 0, 9.0), 0.11, 'zinc', n=8, r1=0.055)       # (galvanised: 'zinc', never the old corrugated sheet)
    for side in ((-1.0, 1.0) if two else (1.0,)):
        b.path([Vector((0, 0, 8.9)), Vector((0, side * 0.35, 9.35)), Vector((0, side * 1.0, 9.55)), Vector((0, side * 1.7, 9.5))], 0.035, 'zinc', n=5)
        b.box((-0.14, min(side * 1.5, side * 2.25), 9.4), (0.14, max(side * 1.5, side * 2.25), 9.53), 'lamp_head', mats={'z-': 'lamp_clear'})
    return b


def bicycle(m='bike_red'):
    """a child's bicycle: 16 inch wheels, a diamond frame, its bars, its saddle, two small wheels to hold it up. Built
    upright along x; laid down or leant by its placing."""
    b = MB()
    r = 0.2

    def wheel(x, rr=r, y=0.0, n=14):
        M = place((x, y, rr), 0.0, math.pi / 2.0)
        b.lathe([(rr - 0.03, -0.014), (rr - 0.006, -0.02), (rr, 0.0), (rr - 0.006, 0.02), (rr - 0.03, 0.014), (rr - 0.034, 0.0), (rr - 0.03, -0.014)], (0, 0, 0), 'tyre', n=n, M=M)
        for q in range(4):
            a = q * math.pi / 4.0
            d = Vector((math.cos(a), 0.0, math.sin(a))) * (rr - 0.03)
            b.beam(Vector((x, y, rr)) - d, Vector((x, y, rr)) + d, 0.004, 0.004, 'chrome')
    wheel(-0.36)
    wheel(0.36)
    ra, bb, sc, ht, hb, fa = Vector((-0.36, 0, 0.2)), Vector((-0.03, 0, 0.21)), Vector((-0.15, 0, 0.5)), Vector((0.24, 0, 0.56)), Vector((0.265, 0, 0.44)), Vector((0.36, 0, 0.2))
    for a, c, rad in ((ra, bb, 0.011), (bb, sc, 0.015), (sc, ht, 0.014), (bb, hb, 0.016), (ra, sc, 0.009), (hb, fa, 0.012), (ht, hb, 0.017)):
        b.tube(a, c, rad, m, n=5)
    b.tube(sc, sc + Vector((-0.035, 0, 0.1)), 0.011, 'chrome', n=5)
    b.box((-0.3, -0.05, 0.6), (-0.1, 0.05, 0.635), 'tyre')
    b.tube(ht, ht + Vector((-0.02, 0, 0.12)), 0.011, 'chrome', n=5)
    b.beam((0.22, -0.2, 0.68), (0.22, 0.2, 0.68), 0.02, 0.02, 'chrome')
    for sy in (-1, 1):
        b.box((0.19, sy * 0.2 - 0.04, 0.665), (0.25, sy * 0.2 + 0.04, 0.695), 'tyre')
        b.beam((-0.03, sy * 0.05, 0.21), (-0.03 + sy * 0.08, sy * 0.07, 0.21 - sy * 0.06), 0.012, 0.012, 'chrome')
        b.box((-0.06 + sy * 0.08, sy * 0.06, 0.2 - sy * 0.06 - 0.01), (0.0 + sy * 0.08, sy * 0.12, 0.2 - sy * 0.06 + 0.01), 'tyre')
        b.beam((-0.36, sy * 0.02, 0.2), (-0.36, sy * 0.15, 0.06), 0.01, 0.01, 'chrome')
        wheel(-0.36, 0.055, sy * 0.15, n=8)
    return b


def stall(rng):
    """a market stall: four poles, an awning lashed over them and sagging, a table under it, crates of what is sold"""
    b = MB()
    w, d = rng.uniform(2.2, 3.2), rng.uniform(1.6, 2.2)
    hf, hb = rng.uniform(2.0, 2.3), rng.uniform(2.3, 2.6)
    for x in (-w / 2, w / 2):
        b.tube((x, -d / 2, 0), (x, -d / 2, hf), 0.022, 'steel_dark', n=5)
        b.tube((x, d / 2, 0), (x, d / 2, hb), 0.022, 'steel_dark', n=5)
    am = rng.choice(('awn:0', 'awn:1', 'awn:2', 'awn:3', 'awn:4', 'awn:5', 'tarp_blue', 'tarp_sand', 'tarp_white', 'tarp_green'))
    nu, nv = 5, 4
    sag = rng.uniform(0.06, 0.2)
    P = [[(-w / 2 - 0.25 + (w + 0.5) * i / nu, -d / 2 - 0.35 + (d + 0.5) * j / nv, hf + (hb - hf) * j / nv - sag * math.sin(math.pi * i / nu) * math.sin(math.pi * j / nv)
           - (0.12 if j == 0 else 0.0)) for i in range(nu + 1)] for j in range(nv + 1)]
    b.grid(P, am, smooth=True)
    b.box((-w / 2 + 0.1, -d / 2 + 0.1, 0.72), (w / 2 - 0.1, d / 2 - 0.5, 0.76), 'wood_pale')
    for x in (-w / 2 + 0.15, w / 2 - 0.15):
        for y in (-d / 2 + 0.15, d / 2 - 0.55):
            b.beam((x, y, 0.0), (x, y, 0.72), 0.04, 0.04, 'wood', up=(1.0, 0.0, 0.0))
    x = -w / 2 + 0.3
    while x < w / 2 - 0.5:
        cw = rng.uniform(0.4, 0.6)
        y0 = rng.uniform(-d / 2 + 0.15, -d / 2 + 0.3)
        z = 0.76
        for lay in range(rng.randrange(1, 3)):
            b.box((x, y0, z), (x + cw, y0 + 0.36, z + 0.2), rng.choice(('crate', 'wood_pale', 'plastic_red', 'plastic_blue')), skip='z-',
                  top=rng.choice(('fruit_orange', 'fruit_red', 'fruit_green', 'fruit_yellow', 'fruit_green')))
            z += 0.2
        x += cw + rng.uniform(0.03, 0.15)
    for _ in range(rng.randrange(0, 4)):                           # sacks on the ground by it
        b.lathe([(0.02, 0.0), (0.24, 0.04), (0.3, 0.2), (0.26, 0.42), (0.1, 0.55), (0.02, 0.56)], (rng.uniform(-w / 2, w / 2), d / 2 - rng.uniform(0.0, 0.4), 0.0), 'sack', n=8)
    return b


def t_wall():
    """one section of a blast wall: 3.6 m of concrete on a spread foot, a lifting eye's recess at its head"""
    b = MB()
    prof = [(-0.6, 0.0), (0.6, 0.0), (0.6, 0.25), (0.18, 0.7), (0.12, 3.6), (-0.12, 3.6), (-0.18, 0.7), (-0.6, 0.25)]
    for (ya, za), (yb, zb_) in zip(prof, prof[1:] + prof[:1]):
        b.quad((0.6, ya, za), (-0.6, ya, za), (-0.6, yb, zb_), (0.6, yb, zb_), 'concrete')
    b.poly([(-0.6, y, z) for y, z in reversed(prof)], 'concrete')
    b.poly([(0.6, y, z) for y, z in prof], 'concrete')
    return b


# ================================================================================================ the mosque
def _arch(b, P, a0, a1, b0, bs, depth, m, back, n=5):
    """a pointed opening in a wall already built round its box (a0..a1, b0..its point): the two spandrels that make
    the box an arch, its curved reveal, its jambs, and what stands at its back"""
    am, hw = (a0 + a1) / 2.0, (a1 - a0) / 2.0
    rise = hw * 1.1
    bt = bs + rise
    left = [(am - hw * math.cos(math.radians(90.0 * k / n)) ** 0.8, bs + rise * math.sin(math.radians(90.0 * k / n))) for k in range(n + 1)]     # springing -> point
    right = [(2 * am - a, z) for a, z in reversed(left)]
    b.poly([P(a, z) for a, z in left] + [P(a0, bt)], m)
    b.poly([P(a, z) for a, z in right] + [P(a1, bt)], m)
    curve = left + right[1:]
    for (a_, z_), (c_, y_) in zip(curve, curve[1:]):
        b.quad(P(a_, z_, depth), P(c_, y_, depth), P(c_, y_), P(a_, z_), m)
    b.quad(P(a0, b0), P(a0, b0, depth), P(a0, bs, depth), P(a0, bs), m)
    b.quad(P(a1, b0, depth), P(a1, b0), P(a1, bs), P(a1, bs, depth), m)
    b.quad(P(a0, b0), P(a1, b0), P(a1, b0, depth), P(a0, b0, depth), m)
    b.poly([P(a0, b0, depth), P(a1, b0, depth)] + [P(a, z, depth) for a, z in reversed(curve)], back)
    return bt


def _arched_wall(b, P0, u, n, L, z0, h, m, ops):
    """a wall with pointed openings [(a0, a1, b0, springing, depth, what stands at its back)]"""
    def P(a, bb, dp=0.0):
        return (P0[0] + u[0] * a - n[0] * dp, P0[1] + u[1] * a - n[1] * dp, z0 + bb)
    boxes = [tuple(round(v, 6) for v in (o[0], o[1], o[2], o[3] + (o[1] - o[0]) / 2.0 * 1.1)) for o in ops]
    xs = sorted({0.0, round(L, 6)} | {q for o in boxes for q in o[:2]})      # (rounded: two openings' equal heights are
    zs = sorted({0.0, round(h, 6)} | {q for o in boxes for q in o[2:]})      #  one grid line, not two a hair apart)
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            a0, a1, b0, b1 = xs[i], xs[i + 1], zs[j], zs[j + 1]
            if any(o[0] <= a0 + 1e-6 and a1 <= o[1] + 1e-6 and o[2] <= b0 + 1e-6 and b1 <= o[3] + 1e-6 for o in boxes):
                continue
            b.quad(P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1), m)
    for o in ops:
        _arch(b, P, o[0], o[1], o[2], o[3], o[4], m, o[5])
    return P


def _pointed_dome(b, c, r, m, n=20, tall=1.15):
    """a dome that swells a little past its drum and draws up to a point; its finial"""
    prof = [(r, 0.0), (r * 1.05, r * 0.14), (r * 1.04, r * 0.34), (r * 0.94, r * 0.58), (r * 0.74, r * 0.82), (r * 0.48, r * 1.0), (r * 0.22, r * 1.11), (0.04, r * tall + 0.02)]
    b.lathe(prof, c, m, n=n)
    zt = r * tall
    b.lathe([(0.03, 0.0), (0.03, 0.16 * r), (0.09 * r, 0.21 * r), (0.03, 0.27 * r), (0.06 * r, 0.32 * r), (0.02, 0.37 * r), (0.02, 0.52 * r)], (c[0], c[1], c[2] + zt), 'gold', n=8)


def mosque(rng):
    b = MB()
    MQ, CO = 'mosque', 'concrete'
    W, D, HH = 14.0, 12.0, 6.6
    walls = (((0, 0), (1, 0), (0, -1), W), ((W, 0), (0, 1), (1, 0), D), ((W, D), (-1, 0), (0, 1), W), ((0, D), (0, -1), (-1, 0), D))
    for q, (P0, u, n, L) in enumerate(walls):
        k = 4 if L > 13 else 3
        ops = [(L * (i + 0.5) / k - 0.6, L * (i + 0.5) / k + 0.6, 1.5, 3.9, 0.22, 'glass') for i in range(k)]
        if q == 0:                                                 # the portal stands in front of the middle of this one
            ops = [o for o in ops if abs((o[0] + o[1]) / 2.0 - L / 2.0) > 2.6]
        _arched_wall(b, P0, u, n, L, 0.3, HH - 0.3, MQ, ops)
    b.box((-0.25, -0.25, 0.0), (W + 0.25, D + 0.25, 0.3), CO, skip='z-')                      # its plinth
    b.box((-0.3, -0.3, HH), (W + 0.3, D + 0.3, HH + 0.35), MQ, skip='z-', top='roof')          # its cornice and roof
    b.run([(-0.3, -0.3), (W + 0.3, -0.3), (W + 0.3, D + 0.3), (-0.3, D + 0.3)], 0.25, HH + 0.35, HH + 1.1, MQ, closed=True)
    b.run([(-0.3, -0.3), (W + 0.3, -0.3), (W + 0.3, D + 0.3), (-0.3, D + 0.3)], 0.25, HH + 1.1, HH + 1.18, 'tile_band', closed=True)
    # the portal: a tall gate standing proud of the hall, a pointed recess in it with the doors at its back
    px0, px1, pd, ph = W / 2 - 2.6, W / 2 + 2.6, 1.3, 8.4
    for (P0, u, n, L, ops) in (((px0, -pd), (1, 0), (0, -1), px1 - px0, [(1.0, 4.2, 0.0, 4.2, 0.9, 'door_green')]), ((px1, -pd), (0, 1), (1, 0), pd, []),
                               ((px0, 0.0), (0, -1), (-1, 0), pd, [])):
        _arched_wall(b, P0, u, n, L, 0.0, ph, MQ, ops)
    b.box((px0 - 0.12, -pd - 0.12, ph), (px1 + 0.12, 0.0, ph + 0.3), MQ, skip='z-')
    b.quad((px1, 0.0, HH), (px0, 0.0, HH), (px0, 0.0, ph), (px1, 0.0, ph), MQ)                 # its back, above the hall's roof
    b.quad((px0 + 0.5, -pd - 0.012, ph - 1.3), (px1 - 0.5, -pd - 0.012, ph - 1.3), (px1 - 0.5, -pd - 0.012, ph - 0.5), (px0 + 0.5, -pd - 0.012, ph - 0.5), 'tile_band')
    for q in range(3):                                             # its steps
        b.box((px0 + 0.6, -pd - 0.35 * (q + 1), 0.0), (px1 - 0.6, -pd - 0.35 * q, 0.3 * (3 - q) / 3.0), CO, skip='z-y+')
    for sx in (px0 + 0.5, px1 - 0.5):                              # two small domes on the portal's shoulders
        b.lathe([(0.75, 0.0), (0.75, 0.5)], (sx, -pd / 2, ph + 0.3), MQ, n=12)
        _pointed_dome(b, (sx, -pd / 2, ph + 0.8), 0.75, 'dome_blue', n=12)
    # the dome: an eight-sided drum with a band of tile, the pointed dome on it
    cx, cy, r = W / 2, D / 2 + 0.5, 3.7
    b.lathe([(r + 0.25, 0.0), (r + 0.25, 0.3), (r, 0.3), (r, 1.25)], (cx, cy, HH + 0.35), MQ, n=24)
    b.lathe([(r + 0.02, 1.25), (r + 0.02, 1.75)], (cx, cy, HH + 0.35), 'tile_band', n=24)
    b.lathe([(r + 0.1, 1.75), (r + 0.1, 1.95), (r, 1.95)], (cx, cy, HH + 0.35), MQ, n=24)
    _pointed_dome(b, (cx, cy, HH + 2.3), r, 'dome', n=24)
    for k in range(8):                                             # the drum's windows, between its piers
        a = 2 * math.pi * (k + 0.5) / 8
        M = place((cx + (r + 0.005) * math.cos(a), cy + (r + 0.005) * math.sin(a), HH + 0.75), a + math.pi / 2.0)
        b.box((-0.3, -0.03, 0.0), (0.3, 0.03, 0.75), 'glass', M=M)
    # the minaret: a square foot, a tapering shaft with bands of tile, a gallery on corbels, a lantern, a pointed cap
    mx, my = -1.9, D - 1.6
    b.box((mx - 1.25, my - 1.25, 0.0), (mx + 1.25, my + 1.25, 4.2), MQ, skip='z-')
    b.lathe([(1.5, 4.2), (1.05, 5.0), (1.0, 9.0)], (mx, my, 0.0), MQ, n=12)
    b.lathe([(1.01, 9.0), (1.0, 9.6)], (mx, my, 0.0), 'tile_band', n=12)
    b.lathe([(0.99, 9.6), (0.92, 15.0), (1.1, 15.3), (1.1, 15.5), (1.45, 15.95), (1.55, 16.0), (1.55, 16.15), (0.8, 16.15)], (mx, my, 0.0), MQ, n=12)
    for k in range(12):                                            # the gallery's rail: a kerb, posts, a rail
        a0_, a1_ = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
        p, q = Vector((mx + 1.5 * math.cos(a0_), my + 1.5 * math.sin(a0_), 0.0)), Vector((mx + 1.5 * math.cos(a1_), my + 1.5 * math.sin(a1_), 0.0))
        b.beam(p + Vector((0, 0, 17.05)), q + Vector((0, 0, 17.05)), 0.07, 0.07, MQ)
        b.beam(p + Vector((0, 0, 16.15)), p + Vector((0, 0, 17.05)), 0.06, 0.06, MQ, up=(1.0, 0.0, 0.0))
        b.beam(p + Vector((0, 0, 16.6)), q + Vector((0, 0, 16.6)), 0.04, 0.04, MQ)
    b.lathe([(0.8, 16.15), (0.74, 19.4), (0.95, 19.6), (0.95, 19.75)], (mx, my, 0.0), MQ, n=12)
    b.lathe([(0.76, 17.9), (0.76, 18.4)], (mx, my, 0.0), 'tile_band', n=12)
    _pointed_dome(b, (mx, my, 19.75), 0.9, 'dome', n=12, tall=1.6)
    for k in range(3):                                             # its loudspeakers, on the gallery
        a = 0.6 + k * 2.1
        c = Vector((mx + 1.45 * math.cos(a), my + 1.45 * math.sin(a), 17.25))
        b.lathe([(0.05, 0.0), (0.07, 0.12), (0.24, 0.42), (0.25, 0.45)], (0, 0, 0), 'speaker', n=10, M=place(c, a - math.pi / 2.0, -math.pi / 2.0))
    # its yard: a low wall with piers and a rail, open before the portal
    X0, X1, Y0, Y1 = -5.5, W + 4.5, -7.0, D + 3.0
    for line in ([(px0 - 0.5, Y0), (X0, Y0), (X0, Y1), (X1, Y1), (X1, Y0), (px1 + 0.5, Y0)],):
        b.run(line[::-1], 0.3, 0.0, 0.7, MQ, top=CO)
        for a, c in zip(line, line[1:]):
            d = Vector((c[0] - a[0], c[1] - a[1], 0.0))
            k = max(1, int(d.length / 3.2))
            for q in range(k + 1):
                p = Vector((a[0], a[1], 0.0)) + d * (q / k)
                b.box((p.x - 0.22, p.y - 0.22, 0.0), (p.x + 0.22, p.y + 0.22, 2.0), MQ, skip='z-')
                if q < k:
                    p2 = Vector((a[0], a[1], 0.0)) + d * ((q + 1) / k)
                    for z in (1.1, 1.75):
                        b.beam(p + Vector((0, 0, z)), p2 + Vector((0, 0, z)), 0.04, 0.04, 'door_blue')
                    for s in range(1, 5):
                        pm = p.lerp(p2, s / 5.0)
                        b.beam(pm + Vector((0, 0, 0.7)), pm + Vector((0, 0, 1.85)), 0.025, 0.025, 'door_blue', up=(1.0, 0.0, 0.0))
    return b
