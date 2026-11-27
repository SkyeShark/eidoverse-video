"""eidoblend.sets.town.kit: what stands on a roof, what a room held, and what a strike leaves on the ground. Blender
(mathutils); each function writes into a mesh builder (mb.MB) at a place. Metres.

Each piece is built as the thing is made: a tank is a moulded shell with its ribs and its lid, standing on a stand of
angle iron with a brace on every side; a cooler is a pan, four posts, a lid and three pads, with its duct going into
the roof; washing hangs folded over a slack line between two posts; an iron bed, a table and plastic chairs, a shade
on four posts, a solar heater, an aerial, blocks stacked for the storey to come.
RUBBLE: a heap is a slumped mound at the angle loose stuff lies at, with its pieces ON it: many small, few large (a
power law), blocks that came out of the walls whole, shards of slab lying flat on the slope, the biggest pieces low;
and a thin field of small pieces thrown past its foot.
"""
import math

from mathutils import Vector

from .mb import catenary, place

CLOTH = ['cloth0', 'cloth0', 'cloth1', 'cloth2', 'cloth3', 'cloth4', 'cloth5', 'cloth6', 'cloth7', 'cloth8']


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


# ================================================================================================ rubble
def chunk(b, rng, c, s, m, kind='lump', rz=None):
    """one broken piece about s across, lying at c as it fell: a lump of concrete, a hollow block out of a wall
    (0.4 x 0.2 x 0.2, or half of one), a shard of slab"""
    if kind == 'block':
        hx, hy, hz, jit = 0.2 * rng.choice((1.0, 1.0, 0.5)), 0.1, 0.1, 0.06
    elif kind == 'shard':
        hx, hy, hz, jit = s / 2.0, s * rng.uniform(0.28, 0.45), min(0.1, s * 0.16), 0.22
    else:
        hx, hy, hz, jit = s / 2.0, s * rng.uniform(0.3, 0.5), s * rng.uniform(0.2, 0.4), 0.32
    M = place(c, rng.uniform(0.0, 6.283) if rz is None else rz, rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5))
    p = []
    for sx, sy, sz in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
        p.append(M @ Vector((hx * (sx + rng.uniform(-jit, jit) * 2.0), hy * (sy + rng.uniform(-jit, jit) * 2.0), hz * (sz + rng.uniform(-jit, jit) * 2.0))))
    b.hexa(p, m)


def ragged(rng, w, d, n=8, jit=0.28):
    """a broken piece of slab's outline about w x d, counter-clockwise. A slab breaks along lines: some of its edges
    are still the straight edges it was cast with, the others are broken: bitten in unevenly, and where two broken
    edges meet the corner is gone (points spread evenly round a square would make every piece an octagon)"""
    hw, hd = w / 2.0, d / 2.0
    C = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    broken = [rng.random() < 0.62 for _ in range(4)]
    if not any(broken):
        broken[rng.randrange(4)] = True
    out = []
    for k in range(4):
        a, c = C[k], C[(k + 1) % 4]
        if broken[k] and broken[k - 1]:
            f = rng.uniform(0.12, 0.4)
            g = rng.uniform(0.0, 0.2)
            out.append((a[0] * (1.0 - f), a[1] * (1.0 - g)))
        else:
            out.append(a)
        if broken[k]:
            m = rng.randrange(1, 4)
            for q in range(1, m + 1):
                t = (q + rng.uniform(-0.3, 0.3)) / (m + 1)
                bite = rng.uniform(0.03, jit)
                out.append(((a[0] + (c[0] - a[0]) * t) * (1.0 - bite), (a[1] + (c[1] - a[1]) * t) * (1.0 - bite)))
    return out


def slab_piece(b, rng, c, w, d, tilt, top, side='concrete_broken', bottom='ceiling', thick=0.2, rz=None, rx=None):
    """a piece of floor or wall lying where it came down (or leaning): top is what was its face"""
    M = place(c, rng.uniform(0.0, 6.283) if rz is None else rz, rng.uniform(-tilt, tilt) if rx is None else rx, rng.uniform(-tilt, tilt) * 0.6)
    b.plate(ragged(rng, w, d), M, thick, top, side, bottom)
    return M


def heap(b, rng, cx, cy, rx, ry, h, z0=0.0, pieces=None, plates=0, paints=(), clip=None, field=True, m='rubble', plate_top='floor', over=0.0):
    """what came down, lying as loose stuff lies. rx, ry: its half-widths; h: its height; paints: the colours its
    plaster was (a few pieces show them); clip: (x0, y0, x1, y1) nothing may lie outside (a floor's edge); over: how
    far a piece may hang over that edge"""
    nseg, nring = 20, 6
    ph = [rng.uniform(0.0, 6.283) for _ in range(5)]

    def R(th):
        e = 1.0 / math.sqrt((math.cos(th) / rx) ** 2 + (math.sin(th) / ry) ** 2)
        return e * (1.0 + 0.20 * math.sin(2.0 * th + ph[0]) + 0.12 * math.sin(3.0 * th + ph[1]) + 0.07 * math.sin(5.0 * th + ph[2]))

    def Hh(rho, th):
        return h * (1.0 - smooth(rho)) ** 1.1 * (1.0 + 0.22 * math.sin(3.0 * th + ph[3]) * rho + 0.12 * math.sin(4.0 * th + ph[4]) * rho)

    def inside(x, y, pad=0.0):
        return clip is None or (clip[0] + pad <= x <= clip[2] - pad and clip[1] + pad <= y <= clip[3] - pad)

    def clamp(x, y):
        if clip is None:
            return x, y
        return min(max(x, clip[0] + 0.02), clip[2] - 0.02), min(max(y, clip[1] + 0.02), clip[3] - 0.02)
    P = []
    for q in range(nring, -1, -1):                                 # from its foot in to its top
        rho = max(q / nring, 0.06)
        row = []
        for k in range(nseg):
            th = 2.0 * math.pi * k / nseg
            r = R(th) * rho
            x, y = clamp(cx + r * math.cos(th), cy + r * math.sin(th))
            z = z0 + Hh(rho, th) + (rng.uniform(-0.07, 0.07) * math.sqrt(h) if 0 < q < nring else 0.0) - (0.03 if q == nring else 0.0)
            row.append((x + rng.uniform(-0.05, 0.05) * (q < nring), y + rng.uniform(-0.05, 0.05) * (q < nring), z))
        P.append(row)
    base = b.grid(P, m, smooth=True, wrap_u=True)
    b.face([base + nring * nseg + k for k in range(nseg)], m, True)
    n = pieces if pieces is not None else int(14 + 7.0 * rx * ry)
    kinds = ('lump', 'lump', 'lump', 'block', 'block', 'shard', 'shard')
    for _ in range(n):
        th = rng.uniform(0.0, 6.283)
        s = min(1.15, 0.16 * rng.random() ** -0.55)                # many small, few large
        rho = min(1.2, rng.uniform(0.1, 1.15) ** 0.75 + 0.25 * max(0.0, s - 0.35))      # the big ones roll furthest down
        r = R(th) * rho
        x, y = cx + r * math.cos(th), cy + r * math.sin(th)
        if not inside(x, y, max(0.0, s * 0.5 - over)):
            continue
        kd = rng.choice(kinds)
        mm = rng.choice(paints) if (paints and kd != 'block' and rng.random() < 0.22) else ('block' if kd == 'block' else rng.choice(('rubble', 'concrete', 'concrete_broken')))
        chunk(b, rng, (x, y, z0 + Hh(min(rho, 1.0), th) + s * 0.14), s, mm, kd)
    for _ in range(plates):                                        # shards of slab, flat on the slope
        th = rng.uniform(0.0, 6.283)
        rho = rng.uniform(0.15, 0.75)
        r = R(th) * rho
        x, y = cx + r * math.cos(th), cy + r * math.sin(th)
        w = rng.uniform(1.1, min(3.4, 0.9 * (rx + ry)))
        if not inside(x, y, w * 0.5):
            continue
        slope = math.atan2(h, 0.7 * (rx + ry))
        M = place((x, y, z0 + Hh(rho, th) + 0.16), th, 0.0, slope * rng.uniform(0.5, 1.3) + rng.uniform(-0.15, 0.15))
        b.plate(ragged(rng, w, w * rng.uniform(0.55, 0.9)), M, 0.2, rng.choice(paints) if (paints and rng.random() < 0.4) else plate_top, 'concrete_broken', 'ceiling')
    if field and clip is None:                                     # thrown past its foot: small, thinning out
        for _ in range(n // 2):
            th = rng.uniform(0.0, 6.283)
            r = R(th) * (1.0 + rng.random() ** 1.6 * 1.3)
            s = rng.uniform(0.1, 0.32)
            chunk(b, rng, (cx + r * math.cos(th), cy + r * math.sin(th), z0 + s * 0.12), s, rng.choice(('rubble', 'concrete', 'block')), rng.choice(('lump', 'block', 'shard')))


# (a strike's pale dust on the ground is no geometry: it is in the ground's and the roads' own materials, by
#  materials.strike_field)


# ================================================================================================ on the roof
def stand(b, x, y, z, w, d, h, m='steel_dark'):
    """a stand of angle iron: four legs, a frame round their heads, slats across, a brace up each side"""
    L = 0.05
    c = [(x + sx * w / 2.0, y + sy * d / 2.0) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for px, py in c:
        b.beam((px, py, z), (px, py, z + h), L, L, m, up=(1.0, 0.0, 0.0))
        b.box((px - 0.07, py - 0.07, z), (px + 0.07, py + 0.07, z + 0.012), m, skip='z-')
    for k in range(4):
        (ax, ay), (bx, by) = c[k], c[(k + 1) % 4]
        b.beam((ax, ay, z + h - L / 2.0), (bx, by, z + h - L / 2.0), L, L, m)
        if h > 0.5:                                                # a flat bar from one leg's foot to the next leg's head
            b.beam((ax, ay, z + 0.1), (bx, by, z + h - 0.1), 0.012, 0.04, m)
    for q in (0.25, 0.5, 0.75):
        b.beam((x - w / 2.0 + w * q, y - d / 2.0, z + h - 0.015), (x - w / 2.0 + w * q, y + d / 2.0, z + h - 0.015), 0.05, 0.03, m)


def tank_poly(b, x, y, z, m='tank_white'):
    """a moulded water tank, a thousand litres: two ribs pressed round it, a shoulder, a screwed lid"""
    b.lathe([(0.52, 0.0), (0.55, 0.04), (0.55, 0.38), (0.53, 0.41), (0.55, 0.44), (0.55, 0.80), (0.53, 0.83), (0.55, 0.86), (0.55, 1.06), (0.46, 1.17), (0.25, 1.23)], (x, y, z), m, n=14)
    b.lathe([(0.25, 1.23), (0.25, 1.28), (0.21, 1.295), (0.02, 1.30)], (x, y, z), 'tank_cap', n=14)
    return 1.30


def tank_steel(b, rng, x, y, z, rz=0.0, m='zinc'):
    """a galvanised tank of pressed panels: its rim, its hatch, the pipe in at the top"""
    M = place((x, y, z), rz)
    s, h = rng.choice((0.5, 0.6, 0.6)), rng.choice((0.9, 1.0, 1.2))
    b.box((-s, -s, 0.0), (s, s, h), m, skip='z-', M=M)
    for sx, sy, u in ((-1, 0, (0, 1)), (1, 0, (0, 1)), (0, -1, (1, 0)), (0, 1, (1, 0))):
        a = Vector((sx * s - u[0] * s, sy * s - u[1] * s, h))
        c = Vector((sx * s + u[0] * s, sy * s + u[1] * s, h))
        b.beam(M @ a, M @ c, 0.05, 0.05, m)
    b.box((-0.25, -0.25, h), (0.2, 0.2, h + 0.045), m, skip='z-', M=M)
    b.tube(M @ Vector((s * 0.6, s * 0.6, h)), M @ Vector((s * 0.6, s * 0.6, h + 0.28)), 0.022, 'steel_dark', n=5)
    return h


def tank_lying(b, x, y, z, rz=0.0, m='zinc', L=1.8, r=0.45):
    """a tank lying in two cradles: dished ends, its filler on top"""
    M = place((x, y, z + r + 0.22), rz) @ place((-L / 2.0, 0.0, 0.0), 0.0, 0.0, math.pi / 2.0)
    b.lathe([(0.02, 0.0), (r * 0.68, 0.035), (r * 0.95, 0.11), (r, 0.2), (r, L - 0.2), (r * 0.95, L - 0.11), (r * 0.68, L - 0.035), (0.02, L)], (0.0, 0.0, 0.0), m, n=14, M=M)
    M2 = place((x, y, z), rz)
    for q in (-0.55, 0.55):
        b.box((q - 0.07, -r * 0.8, 0.0), (q + 0.07, r * 0.8, 0.34), 'concrete', skip='z-', M=M2)
    b.tube(M2 @ Vector((0.3, 0.0, 2 * r + 0.2)), M2 @ Vector((0.3, 0.0, 2 * r + 0.3)), 0.07, 'steel_dark', n=6)


def cooler(b, x, y, z, rz=0.0):
    """an evaporative cooler: a pan, four corner posts, a lid, a wetted pad in three sides, its duct out of the fourth
    and down through the roof; on short legs"""
    M = place((x, y, z), rz)
    s, z0, z1 = 0.45, 0.3, 1.2
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.beam(M @ Vector((sx * (s - 0.03), sy * (s - 0.03), 0.0)), M @ Vector((sx * (s - 0.03), sy * (s - 0.03), z0)), 0.04, 0.04, 'steel_dark', up=(1.0, 0.0, 0.0))
            b.beam(M @ Vector((sx * s, sy * s, z0)), M @ Vector((sx * s, sy * s, z1)), 0.07, 0.07, 'cooler', up=(1.0, 0.0, 0.0))
    b.box((-s + 0.02, -s + 0.02, z0 + 0.1), (s - 0.02, s - 0.02, z1 - 0.06), 'cooler_pad', skip='z-z+', M=M)
    b.box((-s - 0.02, -s - 0.02, z0), (s + 0.02, s + 0.02, z0 + 0.12), 'cooler', M=M)
    b.box((-s - 0.02, -s - 0.02, z1 - 0.07), (s + 0.02, s + 0.02, z1), 'cooler', skip='z-', M=M)
    b.box((-0.2, s - 0.02, z0 + 0.25), (0.2, s + 0.42, z0 + 0.65), 'zinc_old', skip='y-', M=M)
    b.box((-0.2, s + 0.02, 0.0), (0.2, s + 0.42, z0 + 0.25), 'zinc_old', skip='z-z+', M=M)


def condenser(b, M):
    """a split unit's outdoor half: its case, the fan's grille, two feet; M places it (it looks along its own -y)"""
    b.box((-0.4, -0.15, 0.06), (0.4, 0.15, 0.61), 'ac', M=M)
    ring = [M @ Vector((-0.1 + 0.21 * math.cos(2 * math.pi * k / 12), -0.158, 0.335 + 0.21 * math.sin(2 * math.pi * k / 12))) for k in range(12)]
    b.poly(ring, 'ac_fan')
    for q in (-0.3, 0.3):
        b.box((q - 0.03, -0.17, 0.0), (q + 0.03, 0.17, 0.06), 'steel_dark', skip='z+', M=M)


def solar_heater(b, x, y, z, rz=0.0):
    """a thermosiphon heater: two glazed collectors on a frame at forty degrees, its tank lying along their top"""
    M = place((x, y, z), rz)
    T = M @ place((0.0, -0.75, 0.25), 0.0, math.radians(40.0))
    b.box((-1.0, 0.0, 0.0), (1.0, 1.9, 0.07), 'frame_alu', top='solar', M=T)
    top = T @ Vector((0.0, 1.95, 0.25))
    M3 = place(top, rz) @ place((-0.75, 0.0, 0.0), 0.0, 0.0, math.pi / 2.0)
    b.lathe([(0.02, 0.0), (0.2, 0.03), (0.24, 0.1), (0.24, 1.4), (0.2, 1.47), (0.02, 1.5)], (0.0, 0.0, 0.0), 'tank_white', n=10, M=M3)
    for sx in (-0.9, 0.9):
        a = M @ Vector((sx, 0.7, 0.0))
        b.beam(a, T @ Vector((sx, 1.8, 0.0)), 0.04, 0.04, 'steel_dark', up=(1.0, 0.0, 0.0))
        b.beam(M @ Vector((sx, -0.7, 0.0)), T @ Vector((sx, 0.05, 0.0)), 0.04, 0.04, 'steel_dark', up=(1.0, 0.0, 0.0))
        b.beam(M @ Vector((sx, -0.7, 0.03)), a + Vector((0.0, 0.0, 0.03)), 0.04, 0.04, 'steel_dark')


def cloth_on_line(b, rng, a, c, drop, m, back=None):
    """one thing hung over a line from a to c (two points on the line): folded over it, the front hanging `drop`, the
    back less; it bellies a little, as wet cloth does"""
    a, c = Vector(a), Vector(c)
    u = (c - a)
    w = u.length
    u = u / w
    n = Vector((-u.y, u.x, 0.0))
    back = drop * rng.uniform(0.25, 0.95) if back is None else back
    mid = (a + c) / 2.0
    belly = rng.uniform(0.02, 0.06)
    for sgn, dz in ((1.0, drop), (-1.0, back)):
        o = n * (0.012 * sgn)
        top = [a + o, mid + o, c + o]
        bot = [a + o - Vector((0, 0, dz)) + u * rng.uniform(0.0, 0.04), mid + o + n * (belly * sgn) - Vector((0, 0, dz * rng.uniform(0.96, 1.03))),
               c + o - Vector((0, 0, dz)) - u * rng.uniform(0.0, 0.04)]
        for k in range(2):
            pts = (bot[k], bot[k + 1], top[k + 1], top[k]) if sgn > 0 else (bot[k + 1], bot[k], top[k], top[k + 1])
            b.poly(pts, m)
    b.quad(a + n * 0.012, c + n * 0.012, c - n * 0.012, a - n * 0.012, m)


def washing(b, rng, p0, p1, z, posts=True, lines=2):
    """washing on the roof: two posts with a bar across each, slack lines between them, what a family wears on them"""
    p0, p1 = Vector((p0[0], p0[1], z)), Vector((p1[0], p1[1], z))
    u = (p1 - p0).normalized()
    n = Vector((-u.y, u.x, 0.0))
    hgt, half = 1.85, 0.3 if lines > 1 else 0.0
    if posts:
        for p in (p0, p1):
            b.tube(p, p + Vector((0, 0, hgt)), 0.025, 'steel_dark', n=5)
            if lines > 1:
                b.beam(p + Vector((0, 0, hgt)) - n * (half + 0.05), p + Vector((0, 0, hgt)) + n * (half + 0.05), 0.03, 0.03, 'steel_dark')
    for q in range(lines):
        off = n * (half * (2 * q - 1) if lines > 1 else 0.0)
        pts = catenary(p0 + off + Vector((0, 0, hgt)), p1 + off + Vector((0, 0, hgt)), rng.uniform(0.08, 0.2), 8)
        b.path(pts, 0.004, 'wire', n=3)
        k = rng.uniform(0.04, 0.3)                                 # along the line, 0..1
        L = (p1 - p0).length
        while k < 0.9:
            w = rng.choice((0.35, 0.45, 0.5, 0.6, 0.7, 0.9, 1.4, 1.9)) / L
            if k + w > 0.96:
                break
            i0, i1 = k * 8.0, (k + w) * 8.0
            a = pts[int(i0)].lerp(pts[min(int(i0) + 1, 8)], i0 - int(i0))
            c = pts[int(i1)].lerp(pts[min(int(i1) + 1, 8)], i1 - int(i1))
            wide = w * L > 1.2
            cloth_on_line(b, rng, a, c, rng.uniform(0.9, 1.3) if wide else rng.uniform(0.35, 0.85), rng.choice(('cloth0', 'cloth0', 'rug:0', 'rug:1', 'cloth3')) if wide else rng.choice(CLOTH))
            k += w + rng.uniform(0.02, 0.22) / L * 3.0


def rug_over(b, rng, P, u, n, zt, t, m=None, w=None):
    """a carpet, or a sheet, aired over a parapet: down its inside, across its top, down its outside, its hem not
    quite level and standing a little off the wall at its foot (P: a point on the parapet's OUTER face at its middle;
    u along it; n out of it; zt the parapet's top)"""
    P, u, n = Vector((P[0], P[1], 0.0)), Vector((u[0], u[1], 0.0)), Vector((n[0], n[1], 0.0))
    w = w or rng.uniform(1.2, 2.2)
    m = m or rng.choice(('rug:0', 'rug:1', 'rug:2', 'rug:3', 'cloth1', 'cloth8'))
    z = Vector((0, 0, zt + 0.012))
    d_out, d_in = rng.uniform(0.45, 1.05), rng.uniform(0.25, 0.6)
    cols = [P + u * (w * (k / 3.0 - 0.5)) for k in range(4)]
    hem = [d_out * rng.uniform(0.9, 1.06) for _ in range(4)]
    out_top = [c + n * 0.015 + z for c in cols]
    out_bot = [c + n * (0.02 + rng.uniform(0.0, 0.05)) + z - Vector((0, 0, hem[k])) for k, c in enumerate(cols)]
    in_top = [c - n * (t + 0.015) + z for c in cols]
    in_bot = [c - n * (t + 0.02) + z - Vector((0, 0, d_in)) for c in cols]
    b.grid([out_bot, out_top, in_top, in_bot], m, smooth=False)


def bed(b, rng, x, y, z, rz=0.0):
    """an iron bed on the roof, where people sleep in summer: its frame, its legs, a mattress or the bare frame"""
    M = place((x, y, z), rz)
    for sx in (-0.45, 0.45):
        for sy in (-0.95, 0.95):
            b.beam(M @ Vector((sx, sy, 0.0)), M @ Vector((sx, sy, 0.45 if sy < 0 else 0.75)), 0.035, 0.035, 'steel_paint', up=(1.0, 0.0, 0.0))
        b.beam(M @ Vector((sx, -0.95, 0.4)), M @ Vector((sx, 0.95, 0.4)), 0.035, 0.035, 'steel_paint')
    for sy, zz in ((-0.95, 0.4), (0.95, 0.4), (0.95, 0.72)):
        b.beam(M @ Vector((-0.45, sy, zz)), M @ Vector((0.45, sy, zz)), 0.035, 0.035, 'steel_paint')
    if rng.random() < 0.7:
        b.box((-0.44, -0.93, 0.42), (0.44, 0.93, 0.54), 'mattress' if rng.random() < 0.6 else rng.choice(CLOTH), skip='z-', M=M)
    else:
        for q in range(-4, 5):
            b.beam(M @ Vector((-0.45, q * 0.2, 0.4)), M @ Vector((0.45, q * 0.2, 0.4)), 0.02, 0.01, 'steel_paint')


def chair(b, M, m='plastic_white'):
    for sx in (-0.19, 0.19):
        for sy in (-0.19, 0.19):
            b.beam(M @ Vector((sx, sy, 0.0)), M @ Vector((sx * 0.9, sy * 0.9, 0.43)), 0.03, 0.03, m, up=(1.0, 0.0, 0.0))
    b.box((-0.22, -0.22, 0.42), (0.22, 0.22, 0.455), m, M=M)
    b.box((-0.22, 0.19, 0.455), (0.22, 0.225, 0.85), m, skip='z-', M=M @ place((0, 0, 0), 0.0, -0.12))


def table_and_chairs(b, rng, x, y, z):
    M = place((x, y, z), rng.uniform(0.0, 6.28))
    for sx in (-0.32, 0.32):
        for sy in (-0.32, 0.32):
            b.beam(M @ Vector((sx, sy, 0.0)), M @ Vector((sx, sy, 0.7)), 0.035, 0.035, 'plastic_white', up=(1.0, 0.0, 0.0))
    b.box((-0.4, -0.4, 0.7), (0.4, 0.4, 0.735), 'plastic_white', M=M)
    for k in range(rng.randrange(2, 5)):
        a = k * math.pi / 2.0 + rng.uniform(-0.3, 0.3)
        chair(b, M @ place((0.75 * math.sin(a), -0.75 * math.cos(a), 0.0), a + math.pi + rng.uniform(-0.4, 0.4)), rng.choice(('plastic_white', 'plastic_white', 'plastic_blue', 'plastic_red')))


def shade(b, rng, x0, y0, x1, y1, z, m=None, hgt=2.3):
    """a shade on four posts: a frame of light section, cloth or a tarpaulin lashed over it and sagging between"""
    for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        b.tube((px, py, z), (px, py, z + hgt), 0.03, 'steel_dark', n=5)
    for a, c in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        b.beam((a[0], a[1], z + hgt), (c[0], c[1], z + hgt), 0.04, 0.04, 'steel_dark')
    m = m or rng.choice(('tarp_sand', 'tarp_blue', 'tarp_green', 'tarp_white', 'cloth3', 'awn:4'))
    nu, nv = 5, 4
    sag = rng.uniform(0.08, 0.25)
    P = [[(x0 - 0.1 + (x1 - x0 + 0.2) * i / nu, y0 - 0.1 + (y1 - y0 + 0.2) * j / nv,
           z + hgt + 0.03 - sag * math.sin(math.pi * i / nu) * math.sin(math.pi * j / nv) + rng.uniform(-0.02, 0.02)) for i in range(nu + 1)] for j in range(nv + 1)]
    b.grid(P, m, smooth=True)


def stub(b, rng, x, y, z, h=0.9, bars=4, w=0.3):
    """a column begun for a storey never built: its concrete as far as it was poured, its steel waiting, bent"""
    b.box((x - w / 2, y - w / 2, z), (x + w / 2, y + w / 2, z + h), 'concrete', skip='z-')
    for k in range(bars):
        sx, sy = ((-1, -1), (1, -1), (1, 1), (-1, 1), (0, -1), (0, 1))[k % 6]
        p0 = Vector((x + sx * (w / 2 - 0.04), y + sy * (w / 2 - 0.04), z + h - 0.02))
        ln = rng.uniform(0.5, 1.0)
        lean = Vector((rng.uniform(-0.18, 0.18), rng.uniform(-0.18, 0.18), 0.0))
        b.path([p0, p0 + Vector((0, 0, ln * 0.5)) + lean * 0.3, p0 + Vector((0, 0, ln)) + lean], 0.009, 'rebar', n=3)


def block_pile(b, rng, x, y, z, rz=0.0):
    """blocks stacked for the storey to come, some taken"""
    M = place((x, y, z), rz)
    for lay in range(rng.randrange(2, 5)):
        nx_, ny_ = rng.randrange(2, 5), rng.randrange(2, 4)
        for i in range(nx_):
            for j in range(ny_):
                if lay and rng.random() < 0.25:
                    continue
                b.box((i * 0.41, j * 0.205, lay * 0.2), (i * 0.41 + 0.4, j * 0.205 + 0.2, lay * 0.2 + 0.195), 'block', skip='z-', M=M)


def barrel(b, x, y, z, m='barrel_blue', lying=None):
    M = None if lying is None else place((x, y, z + 0.29), lying, 0.0, math.pi / 2.0)
    c = (x, y, z) if M is None else (0.0, 0.0, -0.44)
    b.lathe([(0.27, 0.0), (0.29, 0.02), (0.29, 0.28), (0.3, 0.3), (0.29, 0.32), (0.29, 0.56), (0.3, 0.58), (0.29, 0.6), (0.29, 0.86), (0.27, 0.88)], c, m, n=12, cap1=m, cap0=m, M=M)


def junk(b, rng, x, y, z):
    """what gets left on a roof: a drum, tyres, boards, a box, a gas bottle"""
    for _ in range(rng.randrange(2, 5)):
        px, py = x + rng.uniform(-0.9, 0.9), y + rng.uniform(-0.9, 0.9)
        k = rng.random()
        if k < 0.25:
            barrel(b, px, py, z, rng.choice(('barrel_blue', 'barrel_rust', 'barrel_rust')), lying=rng.uniform(0, 3.14) if rng.random() < 0.3 else None)
        elif k < 0.45:
            for q in range(rng.randrange(1, 4)):
                b.lathe([(0.2, 0.0), (0.3, 0.02), (0.33, 0.09), (0.3, 0.17), (0.2, 0.19)], (px, py, z + q * 0.19), 'tyre', n=10)
        elif k < 0.7:
            a = rng.uniform(0.0, 3.14)
            for q in range(rng.randrange(2, 6)):
                o = Vector((px + q * 0.12 * math.sin(a), py - q * 0.12 * math.cos(a), z + 0.02 + 0.01 * q))
                ln = rng.uniform(1.2, 2.6)
                d = Vector((math.cos(a + rng.uniform(-0.08, 0.08)), math.sin(a + rng.uniform(-0.08, 0.08)), 0.0)) * ln / 2.0
                b.beam(o - d, o + d, 0.1, 0.025, rng.choice(('wood', 'wood_pale')))
        elif k < 0.88:
            s = rng.uniform(0.3, 0.6)
            b.box((-s / 2, -s / 2, 0.0), (s / 2, s / 2, s * rng.uniform(0.5, 1.0)), rng.choice(('cardboard', 'crate', 'wood_pale')), skip='z-', M=place((px, py, z), rng.uniform(0, 3.14)))
        else:
            b.lathe([(0.14, 0.0), (0.15, 0.03), (0.15, 0.42), (0.1, 0.52), (0.04, 0.55), (0.04, 0.6)], (px, py, z), rng.choice(('tank_blue', 'tank_red', 'zinc_old')), n=8)


def antenna(b, rng, x, y, z):
    """a television aerial on a thin mast"""
    h = rng.uniform(2.5, 4.5)
    b.tube((x, y, z), (x, y, z + h), 0.018, 'steel_dark', n=4, smooth=False)
    a = rng.uniform(0.0, 6.28)
    u, n = Vector((math.cos(a), math.sin(a), 0.0)), Vector((-math.sin(a), math.cos(a), 0.0))
    c = Vector((x, y, z + h - 0.12))
    b.beam(c - u * 0.6, c + u * 0.6, 0.02, 0.02, 'zinc')
    for q in range(6):
        p = c + u * (-0.55 + q * 0.22)
        w = 0.34 - 0.03 * q
        b.beam(p - n * w, p + n * w, 0.012, 0.012, 'zinc')


def ladder(b, a, c, m='steel_dark', w=0.42):
    """a ladder from a up to c: two stiles and its rungs every 0.28 m"""
    a, c = Vector(a), Vector(c)
    t = (c - a)
    L = t.length
    t = t / L
    s = t.cross(Vector((0, 0, 1)))
    s = (s if s.length > 1e-3 else Vector((1, 0, 0))).normalized() * (w / 2.0)
    for sg in (-1, 1):
        b.beam(a + s * sg, c + s * sg, 0.04, 0.025, m, up=tuple(s))
    k = 0.25
    while k < L - 0.1:
        p = a + t * k
        b.beam(p - s, p + s, 0.02, 0.02, m)
        k += 0.28


# ================================================================================================ in the rooms
def furniture(b, rng, x0, y0, x1, y1, z, h):
    """what a room held, where it stood: against its walls, a carpet on its floor, a fan under its ceiling. Nobody is
    shown: this is theirs."""
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    if rng.random() < 0.6:
        rw, rd = min(2.6, (x1 - x0) * 0.6), min(1.8, (y1 - y0) * 0.5)
        M = place((cx + rng.uniform(-0.3, 0.3), cy + rng.uniform(-0.3, 0.3), z + 0.012), rng.uniform(-0.1, 0.1))
        b.quad(M @ Vector((-rw / 2, -rd / 2, 0)), M @ Vector((rw / 2, -rd / 2, 0)), M @ Vector((rw / 2, rd / 2, 0)), M @ Vector((-rw / 2, rd / 2, 0)), f'rug:{rng.randrange(4)}')
    k = rng.random()
    yb = y1 - 0.2                                                  # against the back wall
    if k < 0.35:                                                   # a wardrobe, its door hanging open
        xw = rng.uniform(x0 + 0.3, max(x0 + 0.31, x1 - 1.5))
        b.box((xw, yb - 0.55, z), (xw + 1.2, yb, z + 1.9), 'wood', skip='z-')
        b.box((0.0, -0.02, 0.05), (0.58, 0.0, 1.85), 'wood', M=place((xw + 1.2, yb - 0.56, z), rng.uniform(-2.2, -0.6)))
    elif k < 0.65:                                                 # shelves
        xw = rng.uniform(x0 + 0.3, max(x0 + 0.31, x1 - 1.3))
        for q in (0.0, 1.0):
            b.box((xw + q * 0.96, yb - 0.3, z), (xw + q * 0.96 + 0.04, yb, z + 1.5), 'wood_pale', skip='z-')
        for q in range(4):
            b.box((xw, yb - 0.3, z + 0.1 + q * 0.45), (xw + 1.0, yb, z + 0.13 + q * 0.45), 'wood_pale')
    elif k < 0.85:                                                 # a bed
        bed(b, rng, rng.uniform(x0 + 0.8, x1 - 0.8), yb - 1.1, z, rng.uniform(-0.15, 0.15))
    if rng.random() < 0.4:                                         # a fan under the ceiling
        c = Vector((cx, cy, z + h - 0.32))
        b.tube(c, c + Vector((0, 0, 0.32)), 0.015, 'steel_dark', n=4, smooth=False)
        b.lathe([(0.02, -0.05), (0.09, -0.04), (0.09, 0.04), (0.02, 0.05)], tuple(c), 'frame_white', n=8)
        a0 = rng.uniform(0, 2.0)
        for q in range(3):
            a = a0 + q * 2.094
            d = Vector((math.cos(a), math.sin(a), 0.0))
            b.beam(c + d * 0.08, c + d * 0.62 - Vector((0, 0, rng.uniform(0.0, 0.12))), 0.12, 0.008, 'frame_white')
