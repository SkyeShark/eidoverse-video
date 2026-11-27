"""eidoblend.props.houseplants.basil: a pot of sweet basil (Ocimum basilicum) on its saucer (Blender). Millimetres.

    import random
    from eidoblend.props.hardsurface import masses as hs
    from eidoblend.props.houseplants import basil
    hs.start('basil', orient=False)
    basil.build((0.0, 0.0, 0.0), random.Random(11), hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0))

A 9 cm moulded pot with its rim band on a saucer, the compost 12 mm below the rim; eight stems (the mint family's square
stem), each with five pairs of leaves in opposite pairs, each pair across the one below, large below and small at the
tip; each blade domed either side of its midrib, widest a third along, a blunt point, on a short stalk, its tip
falling. Parts: basil_saucer, basil_pot, basil_compost, basil_stems, basil_leaves. rng: the random stream the stems and
leaves are drawn from (the same stream gives the same plant); y_max: no blade reaches past it (mm: a window's glass
behind the pot).
"""

import math

import bmesh
from mathutils import Vector

from ..hardsurface import masses as hs


def _fin(o, m):
    """finished with no bevel, its hard arrises (past 32 degrees) marked sharp so its flats shade flat"""
    o = hs.finish(o, 0.0, m, segments=3)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(32.0):
            e.smooth = False
    bm.to_mesh(o.data)
    bm.free()
    return o


def _tube(path, r, seg=8):
    """a round rod along a path, as a skin (rotation-minimising frames)"""
    return [[p + n * (r * math.cos(2 * math.pi * k / seg)) + b * (r * math.sin(2 * math.pi * k / seg)) for k in range(seg)] for p, t, n, b in hs.frames(path)]


def leaf(base, along, up, L, W):
    """one basil blade as a thin closed skin: its midrib from `base` along `along`, drooping; domed either side of the
    midrib (the edges lower than the rib), widest a third along, a blunt point: seventeen sections, each square to the
    rib where it is, eleven points across, each half puffed up between rib and margin, the margin rolled under"""
    along = along.normalized()
    side = along.cross(up).normalized()
    nrm = side.cross(along).normalized()
    rings_ = []

    def rib(u):
        return base + along * (L * u * (1.0 - 0.08 * u * u)) + nrm * (L * (0.10 * math.sin(math.pi * u * 0.85) - 0.30 * u * u))
    for i in range(17):
        u = 0.02 + 0.97 * (i / 16.0) ** 0.9
        w = W * 1.48 * (u ** 0.62) * ((1.0 - u) ** 0.5) + 0.2
        mid = rib(u)
        tan = (rib(min(1.0, u + 0.02)) - rib(max(0.0, u - 0.02))).normalized()
        nl = side.cross(tan).normalized()                       # the blade's own up, here
        top, bot = [], []
        for j in range(11):
            v = -1.0 + 2.0 * j / 10.0
            dome = (0.13 * math.sin(math.pi * abs(v)) ** 1.2 - 0.15 * abs(v) ** 2.2 - 0.045 * math.exp(-(v / 0.16) ** 2)) * w
            p = mid + side * (w * v * (1.0 - 0.05 * abs(v))) + nl * dome
            top.append(p + nl * 0.25)
            bot.append(p - nl * 0.25)
        rings_.append(top + bot[::-1])
    return rings_


def build(at, rng, clay, y_max=None):
    """the pot of basil standing at `at` (mm) -> (saucer, pot, compost, stems, leaves) objects"""
    BP = Vector(at)
    parts = [_fin(hs.revolve('basil_saucer', [(0.0, 0.0), (37.0, 0.0), (43.5, 2.0), (46.0, 10.0), (44.4, 10.6), (41.5, 4.0), (36.0, 2.4), (0.0, 2.4)], at=BP, seg=48), clay),
             # the pot: its wall up, the rim's band, the lip, back down its inside, its floor
             _fin(hs.revolve('basil_pot', [(0.0, 2.4), (31.0, 2.4), (40.0, 66.0), (42.5, 66.5), (43.0, 79.0), (41.6, 80.0), (40.4, 79.0), (38.2, 66.0), (29.6, 5.0),
                                           (0.0, 5.0)], at=BP, seg=48), clay),
             _fin(hs.revolve('basil_compost', [(0.0, 56.0), (36.5, 56.0), (38.0, 67.0), (33.0, 69.5), (16.0, 70.6), (0.0, 71.0)], at=BP, seg=32), clay)]
    stems, leaves = [], []
    for s in range(8):
        a0 = 2 * math.pi * (s + rng.uniform(-0.25, 0.25)) / 8.0
        r0 = rng.uniform(6.0, 20.0)
        root = BP + Vector((r0 * math.cos(a0), r0 * math.sin(a0) * 0.8, 68.0))
        lean = Vector((math.cos(a0) * rng.uniform(0.16, 0.34), min(0.02, math.sin(a0) * rng.uniform(0.05, 0.2) - 0.1), 1.0)).normalized()   # (leaning to -y)
        H = rng.uniform(105.0, 170.0)
        path = [root - Vector((0, 0, 8.0))] + [root + lean * (H * f) + Vector((lean.x, lean.y, 0.0)) * (26.0 * f * f) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
        stems.append(_tube(path, 1.6, 4))                       # (four-sided: the mint family's square stem)
        twist = rng.uniform(0.0, math.pi)
        for n_, f in enumerate((0.3, 0.52, 0.72, 0.88, 1.0)):
            node = root + lean * (H * f) + Vector((lean.x, lean.y, 0.0)) * (26.0 * f * f)
            size = (1.0, 1.05, 0.86, 0.6, 0.3)[n_] * rng.uniform(0.85, 1.1)
            for half in (0, 1):
                ang = twist + n_ * math.pi / 2.0 + half * math.pi + rng.uniform(-0.25, 0.25)
                out = Vector((math.cos(ang), math.sin(ang), rng.uniform(0.25, 0.7) if n_ < 4 else 1.2)).normalized()
                pet = 12.0 * size + 2.0
                if y_max is not None and (node + out * (pet + 74.0 * size)).y > y_max:
                    out = Vector((out.x, -abs(out.y), out.z))      # (a leaf that would reach past y_max grows the other way)
                stems.append(_tube([node, node + out * pet], 0.9, 5))
                roll = rng.uniform(-0.3, 0.3)                   # no two blades lie square to the light
                leaves.append(leaf(node + out * (pet - 1.0), out, Vector((math.sin(roll) * -out.y, math.sin(roll) * out.x, math.cos(roll))),
                                   74.0 * size, 27.0 * size))
    parts.append(_fin(hs.skins('basil_stems', stems), clay))
    parts.append(_fin(hs.skins('basil_leaves', leaves), clay))
    return parts
