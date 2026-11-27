"""eidoblend.props.carbine.top: what stands on the carbine's rails: the red-dot optic (a machined tube with a cast
middle carrying the turrets, bored through) in its ring mount clamped by a cross-bolt, and the folding backup rear sight.
Built by high.build after front.py (millimetres; the optic's axis is z = +61, the rail's tooth tops z = +31)."""

from __future__ import annotations

import math

from ..hardsurface.masses import arc, boolean, box, cyl, detail, finish, lathe, prism_section, prism_side, rrect


def build(CLAY):
    # ---- THE OPTIC: ONE mass, bored through
    opt = lathe('optic', [(77, 26), (77, 32), (92, 32), (92.5, 30), (132, 30), (132.5, 27), (163, 27), (163.5, 33), (197, 33), (200, 31), (200, 27)], z=61.0)
    opt = boolean(opt, prism_section('optic_middle', rrect(-16.5, 45.5, 16.5, 77, 7.0, n=8), 93, 131), 'UNION')
    opt = boolean(opt, cyl('turret_top_boss', (112, 0, 70), (112, 0, 82), 20.0, seg=32), 'UNION')
    opt = boolean(opt, cyl('turret_side_boss', (112, -10, 61), (112, -21, 61), 20.0, seg=32), 'UNION')
    opt = boolean(opt, cyl('battery_boss', (150, -8, 52), (150, -22, 46), 17.0, seg=32), 'UNION')
    opt = boolean(opt, cyl('optic_bore', (70, 0, 61), (210, 0, 61), 23.0, seg=40), 'DIFFERENCE')
    finish(opt, 0.6, CLAY)
    # the turret caps, the battery cap and the brightness knob (details.py replaces them with knurled ones)
    finish(cyl('turret_top_cap', (112, 0, 82), (112, 0, 92), 16.0, seg=32), 0.6, CLAY)
    finish(cyl('turret_side_cap', (112, -21, 61), (112, -30, 61), 16.0, seg=32), 0.6, CLAY)
    finish(cyl('battery_cap', (150, -22, 46), (150, -28, 43.4), 15.0, seg=32), 0.6, CLAY)
    knob = cyl('brightness_knob', (79, 0, 84), (92, 0, 84), 17.0, seg=40)
    for k in range(20):
        a_ = 2 * math.pi * k / 20
        knob = detail(knob, cyl(f'knurl{k}', (78, 8.6 * math.cos(a_), 84 + 8.6 * math.sin(a_)), (93, 8.6 * math.cos(a_), 84 + 8.6 * math.sin(a_)), 1.6, seg=8), 'DIFFERENCE')
    finish(knob, 0.2, CLAY)
    finish(lathe('objective_lens', [(190, 1), (190, 23), (191.5, 23), (191.5, 1)], z=61.0), 0.0, CLAY)
    finish(lathe('ocular_lens', [(84, 1), (84, 23), (85.5, 23), (85.5, 1)], z=61.0), 0.0, CLAY)
    # ---- ITS MOUNT: a ring round the front tube on a base clamped to the rail by a cross-bolt with a knob
    mount = boolean(prism_side('optic_mount', [(134, 40), (163, 40), (163, 80), (134, 80)], -19, 19),
                    prism_section('mount_sec', [(19, 38), (19, 61)] + arc(0, 61, 19.0, 0, 180, 24) + [(-19, 38)], 120, 180), 'INTERSECT')
    mount = boolean(mount, prism_side('mount_base', [(92, 28.2), (163, 28.2), (163, 41), (108, 41), (100, 37), (92, 37)], -15.5, 15.5), 'UNION')
    mount = detail(mount, cyl('mount_bore', (120, 0, 61), (180, 0, 61), 27.0, seg=40), 'DIFFERENCE')     # (the tube fills it)
    mount = detail(mount, box('mount_split', (130, -1.0, 74), (170, 1.0, 90)), 'DIFFERENCE')
    mount = detail(mount, box('mount_rail_way', (80, -10.8, 20), (175, 10.8, 31.2)), 'DIFFERENCE')    # (the rail fills it)
    finish(mount, 0.6, CLAY)
    finish(cyl('mount_cross_bolt', (127, -17.5, 33.5), (127, 17.5, 33.5), 6.0, seg=20), 0.3, CLAY)
    finish(cyl('mount_knob', (127, -24, 33.5), (127, -15.5, 33.5), 11.0, seg=24), 0.6, CLAY)
    for sgn in (-1, 1):
        finish(cyl(f'mount_ring_screw_{sgn}', (148, sgn * 6, 79), (148, sgn * 6, 81.5), 5.0, seg=16), 0.2, CLAY)
    # ---- THE BACKUP REAR SIGHT: a base clamped to the rail, the aperture's drum, the windage knob
    rs = prism_side('rear_sight', [(26, 31.2), (86, 31.2), (80, 47), (56, 47), (48, 49.5), (30, 49.5), (26, 45)], -13, 13)
    rs = boolean(rs, cyl('rs_drum', (38, -15, 40.5), (38, 15, 40.5), 17.5, seg=32), 'UNION')
    rs = boolean(rs, box('rs_sight_way', (20, -3.0, 41), (52, 3.0, 60)), 'DIFFERENCE')
    finish(rs, 1.4, CLAY)
    finish(cyl('rs_windage_knob', (38, -21, 40.5), (38, -15, 40.5), 14.0, seg=24), 0.5, CLAY)
    finish(cyl('rs_windage_stem', (26, -17, 44), (20, -17, 44), 3.5, seg=12), 0.2, CLAY)
    ap = boolean(prism_side('rs_aperture', [(36, 41), (40, 41), (40, 55), (36, 55)], -2.8, 2.8), cyl('ap_hole', (30, 0, 51.5), (46, 0, 51.5), 2.0, seg=16), 'DIFFERENCE')
    finish(ap, 0.3, CLAY)
    finish(cyl('rs_cross_bolt', (68, -16, 37), (68, 16, 37), 7.0, seg=20), 0.4, CLAY)
