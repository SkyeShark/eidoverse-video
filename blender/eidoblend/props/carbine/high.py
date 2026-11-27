"""eidoblend.props.carbine.high: the carbine's HIGH (and, from the same tables, its LOW), built part by part.

    from eidoblend.props.carbine import high
    col = high.build()            # in the open scene: the collection 'carbine_high', 64 parts, about 499 k triangles
    col = high.build(low=True)    # the low: 'carbine_low', the same 64 parts, about 21 k triangles once finished

SPACE: millimetres in every table: x forward from the receiver's rear face, z up from the bore's axis, y to the
carbine's LEFT (the scene is in metres; when built every part's own mesh is in the carbine's space, its object at
identity). The upper and the lower receiver are each ONE forging: the intersection of the side outline's prism with
the section's, features forged in, cuts machined through, and their edges rounded by edge group (a forging's soft outer
radius, a fillet where a forged-in feature meets the body, crisp machining: masses.finish_forged). Separate hardware
stays separate: pins, the dust cover on its hinge rod, the forward assist's plunger, the charging handle. The front half,
the optic and the sights, the pistol grip and the parts the camera sees close (trigger, magazine, the stock's latch and
butt, knurled small parts) are front.py, top.py, grip.py and details.py, built in that order.
The low (low=True) is the same construction: round parts take the radial count their chord sagitta allows (0.12 mm),
and what the bake carries is left out (knurls, pin holes, bores the carbine hides, ribs).
"""

from __future__ import annotations

import math

from ..hardsurface import masses as hs
from ..hardsurface.masses import (EG_BODY, EG_CUT, EG_FEATURE, EG_MACHINED, arc, boolean, box, cyl, detail, finish,
                                  finish_forged, prism_section, prism_side, rrect, tagged)
from . import details, front, grip, top


def build(low: bool = False, name: str = None, sag_mm: float = 0.12):
    """Build the carbine's high (or its low) in the open scene. Returns the parts' collection ('carbine_high' or
    'carbine_low' unless `name` says otherwise)."""
    hs.start(name or ('carbine_low' if low else 'carbine_high'), low=low, sag_mm=sag_mm)
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    _receivers(clay)
    _rear(clay)
    front.build(clay)
    top.build(clay)
    grip.build(clay)
    details.build(clay)
    hs.sweep_tmp()
    hs.apply_transforms()
    print(f'[carbine] {"low" if low else "high"}: {len(hs.col.objects)} parts, '
          f'{sum(len(o.data.polygons) for o in hs.col.objects if o.type == "MESH"):,} faces')
    return hs.col


def _receivers(CLAY):
    # ======================================================================================== THE UPPER RECEIVER
    # its section: the bolt's tube (33 mm round on the bore's axis), flat sides below it down to the split, and above it
    # the rail's riser with the rail's own dovetail (21.2 mm across the top, 45 degree undercuts to a 15.7 mm neck)
    a_low = math.degrees(math.asin(-11.8 / 16.5))
    a_top = math.degrees(math.asin(12.6 / 16.5))
    right = [(-y, z) for y, z in arc(0, 0, 16.5, a_low, a_top, 20)]                    # the right side's arc, bottom to top
    sec = [(-11.5, -14.0)] + right + [(-7.85, 12.6), (-7.85, 25.4), (-10.6, 28.15), (-10.6, 31.0),
                                      (10.6, 31.0), (10.6, 28.15), (7.85, 25.4), (7.85, 12.6)] + [(-y, z) for y, z in right[::-1]] + [(11.5, -14.0)]
    side = [(3, -14), (205, -14), (205, 31), (18, 31), (18, 27), (12, 27), (6, 21), (3, 12)]
    upper = boolean(tagged(prism_side('upper_receiver', side, -40, 40), EG_BODY), tagged(prism_section('upper_sec', sec, -20, 240), EG_BODY), 'INTERSECT')
    # forged in: the forward assist's housing (a cylinder angled down toward the front), the brass deflector, which fairs
    # down into the tube and forward into the port's raised frame; a web under the housing; the dust cover's hinge lugs
    upper = boolean(upper, tagged(cyl('fa_housing', (14, -15.5, 5.0), (60, -11.0, 2.6), 15.0), EG_FEATURE), 'UNION')
    defl = tagged(prism_side('deflector', [(86, 2), (90, 8), (104, 22), (107, 22), (107, -8), (96, -8), (88, -3)], -19.5, -9.0), EG_FEATURE)
    upper = boolean(upper, defl, 'UNION')
    frame = boolean(tagged(prism_side('port_frame', [(105, -9), (201, -9), (201, 15), (105, 15)], -17.0, -9.0), EG_FEATURE),
                    tagged(box('port_frame_in', (109, -30, -6.5), (198.5, -5, 12.5)), EG_CUT), 'DIFFERENCE')
    upper = boolean(upper, frame, 'UNION')
    upper = boolean(upper, tagged(prism_side('fa_web', [(16, -2), (58, -3), (62, -9), (60, -13.5), (14, -13.5)], -17.5, -9.0), EG_FEATURE), 'UNION')
    upper = boolean(upper, tagged(box('hinge_lug_a', (104, -19.2, -12.5), (110, -9, -8.5)), EG_FEATURE), 'UNION')
    upper = boolean(upper, tagged(box('hinge_lug_b', (198, -19.2, -12.5), (204, -9, -8.5)), EG_FEATURE), 'UNION')
    # cut: the rail's slots (teeth 4.72 long, 10.0076 apart, 3 mm deep), the charging handle's channel, the ejection port
    k = 0
    while 22.0 + k * 10.0076 + 5.3 < 204:
        x = 22.0 + k * 10.0076
        upper = boolean(upper, tagged(box(f'slot{k}', (x, -20, 28.0), (x + 5.29, 20, 40)), EG_MACHINED), 'DIFFERENCE')
        k += 1
    # (the low: the port lies under the closed dust cover, the bores inside the carbine: the bake's)
    upper = detail(upper, tagged(box('port', (110, -30, -6.0), (198, -9.5, 12.0)), EG_CUT), 'DIFFERENCE')
    upper = detail(upper, tagged(cyl('bolt_bore', (-10, 0, 0), (230, 0, 0), 25.4), EG_CUT), 'DIFFERENCE')
    upper = detail(upper, tagged(cyl('fa_bore', (0, -17.2, 5.75), (40, -13.3, 3.6), 8.0), EG_CUT), 'DIFFERENCE')

    def upper_edges(ka, kb, convex):
        """the rail's machined teeth crisp (0.3), machined openings 0.4, the forging's outer contours 0.8 and its own
        inside corners 1.2, and a fillet of 1.5 where a forged-in mass meets the body"""
        if EG_MACHINED in (ka, kb):
            return 0.3
        if EG_CUT in (ka, kb):
            return 0.4
        if ka == kb == EG_BODY:
            return 0.8 if convex else 1.2
        return 0.8 if convex else 1.5

    finish_forged(upper, upper_edges, CLAY)
    # its hardware
    finish(cyl('forward_assist_plunger', (6, -17.9, 6.1), (30, -14.3, 4.2), 7.6), 0.4, CLAY)
    finish(cyl('forward_assist_button', (4, -18.2, 6.25), (9, -17.4, 5.85), 11.5), 0.6, CLAY)
    # the dust cover: PRESSED SHEET: a panel with a raised central pad, a rolled edge round the hinge rod, its latch
    cover = prism_side('dust_cover', [(110.5, -8.5), (197.5, -8.5), (197.5, 11.5), (110.5, 11.5)], -18.2, -17.2)
    cover = detail(cover, prism_side('cover_pad', [(118, -3), (190, -3), (190, 8.5), (118, 8.5)], -19.0, -17.6), 'UNION')
    cover = boolean(cover, cyl('cover_roll', (111, -17.6, -10.5), (197, -17.6, -10.5), 5.0, seg=24), 'UNION')
    cover = detail(cover, box('cover_latch', (148, -20.0, 3.0), (158, -17.4, 8.0)), 'UNION')
    finish(cover, 0.3, CLAY)
    finish(cyl('dust_cover_hinge_rod', (108, -17.6, -10.5), (200, -17.6, -10.5), 3.0, seg=24), 0.0, CLAY)
    ch = boolean(prism_side('charging_handle', [(10, 22), (36, 22), (36, 26), (18, 26.6), (18, 30), (10, 30)], -18, 18),
                 box('ch_grip_cut', (19, -8, 20), (40, 8, 40)), 'DIFFERENCE')
    finish(ch, 0.6, CLAY)

    # ======================================================================================== THE LOWER RECEIVER
    # two widths in one forging: the fire-control part (22.4 mm) and the magazine well's trunk (27.6 mm), the round ring
    # for the receiver extension at the rear, the raised fence round the magazine release on the right; the rear sweeps
    # in a curve under the takedown pin, the well's front has its flared lip, the guard's rear ear comes down behind the
    # trigger with its back edge vertical at x = 62.3, where the grip's front face stands against it
    side_l = [(3, -14), (200, -14), (200, -24), (197, -56), (199.5, -63), (198, -67), (190, -67), (122, -75), (108, -76), (108, -52),
              (76, -52), (75, -70), (73, -80), (62.3, -80), (62.3, -47), (28, -47), (22, -46), (15, -43), (9, -39), (5, -34), (3, -28)]
    lower = boolean(tagged(prism_side('lower_receiver', side_l, -11.2, 11.2), EG_BODY), tagged(box('keep_rear', (-50, -30, -120), (110, 30, 10)), EG_BODY), 'INTERSECT')
    well = boolean(tagged(prism_side('well_trunk', side_l, -13.8, 13.8), EG_FEATURE), tagged(box('keep_front', (106, -30, -120), (260, 30, 10)), EG_FEATURE), 'INTERSECT')
    lower = boolean(lower, well, 'UNION')
    lower = boolean(lower, tagged(cyl('extension_ring', (-15, 0, -1), (5, 0, -1), 38.0), EG_FEATURE), 'UNION')
    ring_out = tagged(prism_side('fence_out', rrect(110, -48, 136, -22, 5.0), -16.0, -12.0), EG_FEATURE)
    ring_in = tagged(prism_side('fence_in', rrect(113, -45, 133, -25, 3.0), -30.0, -10.0), EG_CUT)
    lower = boolean(lower, boolean(ring_out, ring_in, 'DIFFERENCE'), 'UNION')
    # cut: the magazine well through, the fire-control pocket from above, the extension's thread bore, the pin holes
    # (the low keeps the well and the slots a lens sees; the pocket, the bore and the pins' holes are under other parts)
    lower = boolean(lower, tagged(box('magazine_well', (113, -11.4, -120), (189, 11.4, 5)), EG_CUT), 'DIFFERENCE')
    lower = detail(lower, tagged(box('fire_control_pocket', (30, -7.5, -44), (106, 7.5, 5)), EG_CUT), 'DIFFERENCE')
    lower = detail(lower, tagged(cyl('extension_bore', (-30, 0, -1), (12, 0, -1), 30.0), EG_CUT), 'DIFFERENCE')
    for nm, x, z, d in (('takedown', 37, -19, 6.4), ('pivot', 170, -20, 6.4), ('selector', 56, -33, 9.6), ('hammer', 83, -38, 4.0),
                        ('trigger', 74, -44, 4.0), ('mag_catch', 118, -33, 10.0)):
        lower = detail(lower, tagged(cyl('hole_' + nm, (x, -40, z), (x, 40, z), d, seg=32), EG_CUT), 'DIFFERENCE')
    lower = detail(lower, tagged(box('auto_sear_window', (57, -30, -21), (63, 30, -17)), EG_CUT), 'DIFFERENCE')
    lower = detail(lower, tagged(box('guard_slot_rear', (60, -4.6, -90), (77, 4.6, -70)), EG_CUT), 'DIFFERENCE')
    lower = detail(lower, tagged(box('guard_slot_front', (107, -4.6, -90), (114, 4.6, -72)), EG_CUT), 'DIFFERENCE')
    # the trigger's slot through the floor of the fire-control part: the blade comes down through it (details.py)
    lower = boolean(lower, tagged(box('trigger_slot', (79.5, -3.5, -60), (100.5, 3.5, -40)), EG_CUT), 'DIFFERENCE')
    lower = boolean(lower, tagged(prism_side('well_front_rib', [(193, -22), (199.5, -24), (197, -56), (191, -56)], -15.0, 15.0), EG_FEATURE), 'UNION')
    lower = boolean(lower, tagged(prism_side('pivot_band', [(110, -17), (200, -17), (200, -22.5), (110, -22.5)], -14.8, 14.8), EG_FEATURE), 'UNION')
    lower = boolean(lower, tagged(box('bolt_catch_boss', (96, 10.5, -36), (112, 14.6, -14)), EG_FEATURE), 'UNION')
    lower = boolean(lower, tagged(box('magazine_catch_slot', (112, 12.0, -38), (140, 30, -29)), EG_CUT), 'DIFFERENCE')
    # the grip's boss: a wedge under the receiver's rear, 12.6 mm wide: a vertical front face behind the trigger guard and
    # an angled face square to the grip's axis (raked 34 degrees), the grip screw's threaded hole in it; the grip's pocket
    # sits over it (grip.py)
    lower = boolean(lower, tagged(prism_side('grip_boss', [(58.0, -40.0), (58.0, -66.0), (29.8, -47.0), (29.8, -40.0)], -6.3, 6.3), EG_FEATURE), 'UNION')
    lower = detail(lower, tagged(cyl('grip_boss_thread', (44.1, 0, -57.3), (52.2, 0, -45.3), 5.6, seg=24), EG_CUT), 'DIFFERENCE')

    def lower_edges(ka, kb, convex):
        """machined cuts 0.5; the forging's outer contours 1.2 and its own inside corners 1.5; a forged-in mass's own
        outer edges 1.0 and the fillet where it meets the body 2.0"""
        if EG_CUT in (ka, kb):
            return 0.5
        if ka == kb == EG_BODY:
            return 1.2 if convex else 1.5
        return 1.0 if convex else 2.0

    finish_forged(lower, lower_edges, CLAY)
    # its hardware: the pins (heads proud on the right), the selector's shaft, the magazine release's button, the guard
    for nm, x, z, d, proud in (('takedown_pin', 37, -19, 6.3, 1.2), ('pivot_pin', 170, -20, 6.3, 1.2), ('hammer_pin', 83, -38, 3.9, 0.3),
                               ('trigger_pin', 74, -44, 3.9, 0.3), ('selector_shaft', 56, -33, 9.4, 0.8)):
        w = 13.8 if x > 108 else 11.2
        finish(cyl(nm, (x, -w - proud, z), (x, w + proud, z), d, seg=32), 0.3, CLAY)
    btn = boolean(cyl('magazine_release_button', (118, -15.0, -33), (118, -11.0, -33), 9.4, seg=32), box('btn_keep', (112, -30, -40), (124, 0, -26)), 'INTERSECT')
    finish(btn, 0.4, CLAY)
    # the trigger guard: ONE part: the strap and its two end lugs, each filling its slot between the receiver's ears and
    # carrying its pin
    guard = prism_side('trigger_guard', [(63.3, -79.6), (113.4, -79.6), (113.4, -73.6), (112.4, -72.6), (108.6, -72.6), (107.6, -73.6), (107.6, -76.0),
                                         (106.6, -76.8), (77.6, -76.8), (76.6, -76.0), (76.6, -71.6), (75.6, -70.6), (64.3, -70.6), (63.3, -71.6)], -4.4, 4.4)
    finish(cyl('guard_pin_rear', (70, -11.6, -76.5), (70, 11.6, -76.5), 3.2, seg=24), 0.2, CLAY)
    finish(cyl('guard_pin_front', (110.5, -14.2, -74), (110.5, 14.2, -74), 3.2, seg=24), 0.2, CLAY)
    finish(guard, 0.5, CLAY)
    # the left side's controls (separate parts): the bolt catch's paddle, the selector's lever (on SAFE: pointing
    # forward, at the word), the magazine catch's bar
    finish(prism_side('bolt_catch', [(98, -12), (108, -12), (109, -22), (106, -34), (100, -34), (97, -22)], 14.6, 17.6), 0.8, CLAY)
    finish(prism_side('selector_lever', [(60, -29.5), (52, -29.5), (51, -33), (52, -36.5), (72, -35), (74, -33), (72, -31)], 12.0, 15.2), 0.8, CLAY)
    finish(prism_side('magazine_catch', [(113, -30), (139, -30), (139, -37), (113, -37)], 12.4, 14.4), 0.5, CLAY)


def _rear(CLAY):
    # ======================================================================================== THE REAR: extension, stock
    # the receiver extension (a tube on z = -1, ending inside the stock), the castle nut, the end plate
    ext = detail(cyl('receiver_extension', (-171, 0, -1), (4, 0, -1), 29.6), cyl('ext_bore', (-167, 0, -1), (10, 0, -1), 25.0), 'DIFFERENCE')
    ext = boolean(ext, box('ext_rail', (-171, -4.5, -22), (-12, 4.5, -8)), 'UNION')
    finish(ext, 0.4, CLAY)
    nut = cyl('castle_nut', (-9.5, 0, -1), (-2.5, 0, -1), 34.5)
    for k in range(6):
        a_ = math.radians(60 * k)
        nut = boolean(nut, box(f'nut_notch{k}', (-9.6, 16.0 * math.cos(a_) - 2.2, -1 + 16.0 * math.sin(a_) - 2.2),
                               (-6.0, 16.0 * math.cos(a_) + 2.2, -1 + 16.0 * math.sin(a_) + 2.2)), 'DIFFERENCE')
    nut = detail(nut, cyl('nut_bore', (-12, 0, -1), (0, 0, -1), 29.0), 'DIFFERENCE')          # (a ring on the tube)
    finish(nut, 0.3, CLAY)
    plate_ = detail(prism_section('end_plate', [(-13.5, -19), (-13.5, 8), (-9, 15), (9, 15), (13.5, 8), (13.5, -19), (9, -24), (-9, -24)], -2.5, 0.4),
                    cyl('plate_hole', (-10, 0, -1), (10, 0, -1), 30.0), 'DIFFERENCE')
    finish(plate_, 0.4, CLAY)
    # the stock: ONE moulded shell: its side outline x its "A" section (a round top over the tube, cheeks sloping in to a
    # narrow lower web), the butt flared, hollow on the tube; then its slots CUT: three rows as recesses, the long slot
    # through
    side_s = [(-9, 18), (-175, 18), (-178, 14), (-178.5, 0), (-171, -104), (-168, -107), (-160, -103), (-126, -58), (-124.5, -57.5), (-122, -72),
              (-88, -48), (-45, -48), (-45, -45), (-42, -45), (-42, -25), (-9, -25)]
    sec_s = [(10.5, -115), (10.5, -46), (17.0, -22)] + arc(0, -1, 19.0, -20, 200, 28) + [(-17.0, -22), (-10.5, -46), (-10.5, -115)]
    stock = boolean(prism_side('stock', side_s, -40, 40), prism_section('stock_sec', sec_s, -200, 10), 'INTERSECT')
    butt = boolean(prism_side('butt', [(-175, 18), (-178, 14), (-178.5, 0), (-171, -104), (-168, -107), (-164, -104), (-170, 0), (-168, 18)], -22, 22),
                   prism_section('butt_sec', [(-22, -110), (-22, 5), (-17, 19), (17, 19), (22, 5), (22, -110)], -200, 10), 'INTERSECT')
    stock = boolean(stock, butt, 'UNION')
    stock = detail(stock, cyl('stock_bore', (-170, 0, -1), (10, 0, -1), 30.2), 'DIFFERENCE')        # (the tube fills it)
    stock = detail(stock, box('stock_rail_way', (-170, -4.8, -24), (10, 4.8, -8)), 'DIFFERENCE')
    for r_, z_ in enumerate((-2, -9, -16)):
        for c_, x_ in enumerate((-168, -138, -108, -79, -50)):
            if r_ == 2 and c_ == 4:
                continue
            for sgn in (-1, 1):
                # ONE cutter per slot: its round-ended outline as one prism
                st_ = 30 if hs.low() else 15
                ends = [(x_ + 23 + 2.0 * math.cos(math.radians(a_)), z_ + 2.0 * math.sin(math.radians(a_))) for a_ in range(-90, 91, st_)]
                ends += [(x_ + 2 + 2.0 * math.cos(math.radians(a_)), z_ + 2.0 * math.sin(math.radians(a_))) for a_ in range(90, 271, st_)]
                y_a, y_b = (16.5, 30.0) if sgn > 0 else (-30.0, -16.5)
                stock = boolean(stock, prism_side(f'slot_{r_}{c_}{sgn}', ends, y_a, y_b), 'DIFFERENCE')
    stock = boolean(stock, box('long_slot', (-164, -30, -31), (-130, 30, -25)), 'DIFFERENCE')
    stock = boolean(stock, box('sling_slot', (-170, -30, -100), (-164, 30, -70)), 'DIFFERENCE')
    finish(stock, 1.6, CLAY)
    finish(cyl('stock_lock_pin', (-70, 0, -60), (-70, 0, -44), 9.0, seg=24), 0.5, CLAY)
