"""eidoblend.props.carbine.front: the carbine's front half: the barrel, the slip ring, the gas tube, the rail fore-end
with its four rails and vents, the front sight base, the sling swivel, the flash hider. Built by high.build after the
receivers (millimetres; x forward from the receiver's rear face, z up from the bore)."""

from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from ..hardsurface import masses as hs
from ..hardsurface.masses import MM, boolean, box, cyl, detail, finish, lathe, obj, prism_side


def stadium(name, a, b, dia, axis, depth, seg=32):
    """A slot's cutter: the stadium round the segment a -> b (mm), dia wide, run from a's plane out along axis for
    depth mm (and 2 mm back). (The low keeps the high's 32: fewer left a vent's end open on the low tube's facets.)"""
    a, b, w = Vector(a), Vector(b), Vector(axis).normalized()
    u = (b - a).normalized()
    v = w.cross(u)
    h = seg // 2
    ring = [b + (u * math.cos(math.pi * (k / h - 0.5)) + v * math.sin(math.pi * (k / h - 0.5))) * dia / 2 for k in range(h + 1)]
    ring += [a + (u * math.cos(math.pi * (k / h + 0.5)) + v * math.sin(math.pi * (k / h + 0.5))) * dia / 2 for k in range(h + 1)]
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((p - w * 2.0) * MM) for p in ring])
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[q for q in r['geom'] if isinstance(q, bmesh.types.BMVert)], vec=w * (depth + 2.0) * MM)
    return obj(name, bm)


def build(CLAY):
    LOW = hs.low()
    # the barrel (steel): chamber end in the receiver, under the fore-end, the sight's seat, the step-down, the muzzle thread
    finish(detail(lathe('barrel', [(196, 25), (222, 25), (222, 19.2), (380, 19.2), (380, 19.0), (428, 19.0), (428, 17.5), (462, 17.5), (463, 15.0),
                                    (485, 15.0), (486, 17.2), (538, 17.2), (538, 14.0), (555, 14.0)]),
                   cyl('bore', (190, 0, 0), (560, 0, 0), 5.7, seg=24), 'DIFFERENCE'), 0.3, CLAY)
    # the slip ring (tapered, five grooves down its taper: the low's are the bake's) and the handguard cap; the gas tube
    ring_profile = [(203, 30), (203, 52), (206, 53)]
    for k_ in range(0 if LOW else 5):
        x_ = 206.5 + k_ * 3.1
        d_ = 53.0 - (x_ - 206.0) * 0.5
        ring_profile += [(x_, d_), (x_ + 0.5, d_ - 2.2), (x_ + 1.5, d_ - 2.2), (x_ + 2.0, d_ - 1.0)]
    ring_profile += [(222, 45), (224, 45), (224, 30)]
    finish(lathe('delta_ring', ring_profile, seg=64), 0.0, CLAY)
    finish(lathe('handguard_cap', [(375, 20), (375, 52), (379.5, 52), (380, 46), (380, 20)]), 0.3, CLAY)
    finish(cyl('gas_tube', (200, 0, 16.5), (398, 0, 16.5), 4.6, seg=20), 0.0, CLAY)
    # the rail fore-end: ONE mass: a tube round the barrel with its four rails standing out of it (clear overlaps), then
    # the bore, the rail slots and the vents CUT (the low keeps the high's 64 round the tube and 48 in its bore)
    ras = cyl('rail_fore_end', (225, 0, 1.5), (375, 0, 1.5), 47.0, seg=64, keep=True)
    for nm, lo, hi in (('top', (225, -10.6, 18), (375, 10.6, 31)), ('bottom', (225, -10.6, -31), (375, 10.6, -15)),
                       ('right', (225, -30.6, -9.1), (375, -18, 12.1)), ('left', (225, 18, -9.1), (375, 30.6, 12.1))):
        ras = boolean(ras, box('rail_' + nm, lo, hi), 'UNION')
    ras = boolean(ras, cyl('ras_bore', (215, 0, 1.5), (385, 0, 1.5), 40.0, seg=48, keep=True), 'DIFFERENCE')
    k = 0
    while 228.0 + k * 10.0076 + 5.3 < 374:
        x = 228.0 + k * 10.0076
        slots = box(f'rs_t{k}', (x, -20, 28.0), (x + 5.29, 20, 40))
        for nm, lo, hi in (('b', (x, -20, -40), (x + 5.29, 20, -28.0)), ('r', (x, -40, -20), (x + 5.29, -27.6, 20)), ('l', (x, 27.6, -20), (x + 5.29, 40, 20))):
            slots = boolean(slots, box(f'rs_{nm}{k}', lo, hi), 'UNION')
        ras = boolean(ras, slots, 'DIFFERENCE')
        k += 1
    for i_, x in enumerate((240, 261, 282, 303, 324, 345, 366)):               # the upper vents: slanted slots
        for sgn in (-1, 1):
            ras = boolean(ras, stadium(f'vent_u{i_}{sgn}', (x - 3.0, 0, 1.5), (x + 3.0, 0, 1.5), 6.5, (0, sgn * 40, 40), 45.0), 'DIFFERENCE')
    for i_, x in enumerate((243, 261, 279, 297, 315, 333, 350, 366)):          # the lower vents: round
        for sgn in (-1, 1):
            ras = boolean(ras, cyl(f'vent_d{i_}{sgn}', (x, 0, 1.5), (x + 0.001, sgn * 40, -38.5), 9.0, seg=20), 'DIFFERENCE')
    finish(ras, 0.3, CLAY)
    # the front sight base: ONE forging: the A-frame's side outline with its window cut, the two clamp bands round the
    # barrel, the post's housing with its ears, the bayonet lug; the barrel's seat cut through
    fsb = boolean(prism_side('front_sight_base', [(380, 22), (410, 64), (414, 66), (423, 66), (425, 62), (427, 14), (380, 14)], -6.5, 6.5),
                  prism_side('fsb_window', [(391, 24), (407, 47), (414, 47), (414, 36), (419, 33), (419, 24)], -20, 20), 'DIFFERENCE')
    fsb = boolean(fsb, cyl('fsb_band_rear', (380, 0, 0), (396, 0, 0), 30.0), 'UNION')
    fsb = boolean(fsb, cyl('fsb_band_front', (412, 0, 0), (428, 0, 0), 30.0), 'UNION')
    fsb = boolean(fsb, box('fsb_web', (380, -6.5, -2), (428, 6.5, 22)), 'UNION')
    fsb = boolean(fsb, prism_side('bayonet_lug', [(418, -10), (436, -10), (437, -16), (434, -22), (420, -22)], -4.5, 4.5), 'UNION')
    fsb = boolean(fsb, box('lug_neck', (420, -4.5, -14), (428, 4.5, 0)), 'UNION')
    fsb = boolean(fsb, box('ear_gap', (409, -3.6, 55), (426, 3.6, 80)), 'DIFFERENCE')
    fsb = detail(fsb, cyl('fsb_seat', (370, 0, 0), (440, 0, 0), 19.0), 'DIFFERENCE')            # (the barrel fills it)
    finish(fsb, 0.8, CLAY)
    finish(cyl('front_sight_post', (418, 0, 52), (418, 0, 64.5), 2.6, seg=16), 0.0, CLAY)
    for x in (388, 420):
        finish(cyl(f'fsb_taper_pin_{x}', (x, -15.5, -11.5), (x, 15.5, -11.5), 3.2, seg=16), 0.2, CLAY)
    sw = boolean(prism_side('sling_swivel', [(384, -12), (396, -12), (397, -20), (393, -25), (387, -25), (383, -20)], -9, 9),
                 box('swivel_in', (386, -6.5, -23), (394, 6.5, -14)), 'DIFFERENCE')         # (an opening: the low's too)
    finish(sw, 0.8, CLAY)
    # the flash hider: turned, slots over the top (closed underneath); the crush washer's collar behind it
    fh = lathe('flash_hider', [(540, 13), (540, 20.5), (548, 20.5), (549, 18.5), (551.5, 18.5), (552.5, 22.0), (580, 22.0), (582, 20.0), (582, 13)])
    fh = boolean(fh, cyl('fh_bore', (556, 0, 0), (590, 0, 0), 11.0, seg=24), 'DIFFERENCE')
    for k, ang in enumerate((-66, -33, 0, 33, 66)):
        a_ = math.radians(90 + ang)
        for dx in (563.0, 568.0, 573.0, 577.0):
            fh = boolean(fh, cyl(f'fh_slot{k}{dx}', (dx, 4 * math.cos(a_), 4 * math.sin(a_)), (dx + 0.001, 20 * math.cos(a_), 20 * math.sin(a_)), 3.2, seg=16), 'DIFFERENCE')
    finish(fh, 0.3, CLAY)
