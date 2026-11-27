"""eidoblend.props.helicopter.doors: the cabin doors slid aft on their tracks; the cockpit doors' hardware.

Each cabin door is one panel 1.77 m long with two tall windows in pale moulded seals (both faces) and a pull handle in
a pressed recess; it hangs from a rail along the roof's edge and rides a track under the sill, both running from the
doorway's front to where the door lies open. The gunner's panes slide on two rails. The cockpit door: two hinges on its
raked front edge and a flush latch handle, laid on the skin by asking it (needs hull.py's b.surf).
"""

from __future__ import annotations

from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from . import datum as D


def build(b):
    CLAY, GLASS, RUBBER, STEEL = b.clay, b.glass, b.rubber, b.steel
    SURF_H = getattr(b, 'surf', None)
    if SURF_H is None:
        raise RuntimeError('helicopter doors: the hull must be built first (it asks the hull where its skin is)')
    DOOR_LEN, GAP, TH = 1770.0, 16.0, 42.0
    for sgn, sd in ((1, 'r'), (-1, 'l')):
        x0 = D.DOOR_X1 + 22.0                                  # slid fully aft: its front edge just clear of the doorway
        ya, yb = sgn * (D.W + GAP), sgn * (D.W + GAP + TH)
        panel = hs.prism_side(f'cabin_door_{sd}', hs.rrect(x0, D.DOOR_Z0 + 8.0, x0 + DOOR_LEN, D.DOOR_Z1 + 6.0, 55.0), min(ya, yb), max(ya, yb))
        for i, (wx0, wz0, wx1, wz1) in enumerate(D.DOOR_WINDOWS):
            panel = hs.boolean(panel, hs.prism_side(f'door_cut_{sd}_{i}', hs.rrect(x0 + wx0, wz0, x0 + wx1, wz1, 85.0), -3000.0, 3000.0), 'DIFFERENCE')
        # the pressed recess its pull handle sits in, on the outside
        panel = hs.boolean(panel, hs.prism_side(f'door_handle_cut_{sd}', hs.rrect(x0 + 60.0, 760.0, x0 + 150.0, 1000.0, 22.0),
                                                min(yb - sgn * 16.0, yb + sgn * 60.0), max(yb - sgn * 16.0, yb + sgn * 60.0)), 'DIFFERENCE')
        hs.finish(panel, 3.0, CLAY)
        hs.finish(hs.skins(f'door_handle_{sd}', [[hs.circle(Vector((x0 + 105.0, yb - sgn * 6.0, 790.0)), (0, 0, 1), 8.0, 0.0, 10),
                                                  hs.circle(Vector((x0 + 105.0, yb - sgn * 6.0, 790.0)), (0, 0, 1), 8.0, 180.0, 10)]]), 0.0, STEEL)
        for i, (wx0, wz0, wx1, wz1) in enumerate(D.DOOR_WINDOWS):                # each window: its pane, and the moulded seal that holds it, both faces
            ym = (ya + yb) / 2.0
            hs.finish(hs.prism_side(f'door_pane_{sd}_{i}', hs.rrect(x0 + wx0 - 10.0, wz0 - 10.0, x0 + wx1 + 10.0, wz1 + 10.0, 92.0), ym - 3.5, ym + 3.5), 0.0, GLASS)
            for face, dirn in ((yb, sgn), (ya, -sgn)):
                path = [(Vector((x, face, z)), Vector((0.0, float(dirn), 0.0))) for x, z in bt.round_poly(hs.rrect(x0 + wx0, wz0, x0 + wx1, wz1, 85.0), 0.0)]
                bt.frame(f'door_seal_{sd}_{i}_{"o" if dirn == sgn else "i"}', path, [(-12.0, -1.5), (-12.0, 3.0), (-9.0, 5.5), (9.0, 5.5), (13.0, 2.5), (13.0, -1.5)], RUBBER)
        # the upper rail along the roof's edge and the lower track under the sill
        xa, xb = D.DOOR_X0 - 40.0, x0 + DOOR_LEN + 30.0
        up = [(D.W - 4.0, D.DOOR_Z1 + 22.0), (D.W + 66.0, D.DOOR_Z1 + 22.0), (D.W + 72.0, D.DOOR_Z1 + 30.0), (D.W + 72.0, D.DOOR_Z1 + 70.0), (D.W + 60.0, D.DOOR_Z1 + 82.0),
              (D.W - 4.0, D.DOOR_Z1 + 96.0)]
        hs.finish(hs.rings(f'door_rail_upper_{sd}', [[Vector((x, sgn * y, z)) for y, z in up] for x in (xa, xb)]), 2.0, CLAY)
        lo = [(D.W - 4.0, D.DOOR_Z0 - 40.0), (D.W + 60.0, D.DOOR_Z0 - 40.0), (D.W + 64.0, D.DOOR_Z0 - 34.0), (D.W + 64.0, D.DOOR_Z0 - 14.0), (D.W + 44.0, D.DOOR_Z0 - 8.0),
              (D.W - 4.0, D.DOOR_Z0 - 8.0)]
        hs.finish(hs.rings(f'door_track_lower_{sd}', [[Vector((x, sgn * y, z)) for y, z in lo] for x in (xa, xb)]), 1.5, CLAY)
        hang = []                                              # the door's two hangers up into the rail, its two rollers in the track
        for dx in (150.0, DOOR_LEN - 150.0):
            hang.append([[Vector((x0 + dx + ex, sgn * (D.W + GAP + 8.0 + ey), z)) for ex, ey in ((-36.0, 0.0), (36.0, 0.0), (36.0, 26.0), (-36.0, 26.0))]
                         for z in (D.DOOR_Z1 - 4.0, D.DOOR_Z1 + 40.0)])
            hang.append([[Vector((x0 + dx + ex, sgn * (D.W + GAP + 8.0 + ey), z)) for ex, ey in ((-30.0, 0.0), (30.0, 0.0), (30.0, 24.0), (-30.0, 24.0))]
                         for z in (D.DOOR_Z0 - 22.0, D.DOOR_Z0 + 20.0)])
        hs.finish(hs.skins(f'door_hangers_{sd}', hang), 2.0, CLAY)
        # the gunner's panes' two rails (they slide forward on them)
        for nm, z in (('upper', D.GUNNER_PANES[0][3] + 34.0), ('lower', D.GUNNER_PANES[0][1] - 34.0)):
            rail = [(D.W - 3.0, z - 13.0), (D.W + 13.0, z - 13.0), (D.W + 16.0, z - 9.0), (D.W + 16.0, z + 9.0), (D.W + 13.0, z + 13.0), (D.W - 3.0, z + 13.0)]
            hs.finish(hs.rings(f'gunner_rail_{nm}_{sd}', [[Vector((x, sgn * y, zz)) for y, zz in rail] for x in (-2150.0, D.GUNNER_PANES[1][2] + 40.0)]), 1.0, CLAY)
        # the cockpit door's two hinges on its raked front edge, and its latch handle
        hw = []
        for zh in (330.0, 1180.0):
            xh = D.X_A_FOOT + (zh - D.A_FOOT[2]) * (D.A_HEAD[0] - D.A_FOOT[0]) / (D.A_HEAD[2] - D.A_FOOT[2]) if zh > D.A_FOOT[2] else -3492.0
            h = SURF_H.hit(Vector((xh + 12.0, sgn * 2600.0, zh)), (0.0, -float(sgn), 0.0))
            if h is None:
                continue
            p, n = h
            t = Vector((0.0, 0.0, 1.0))
            s = n.cross(t).normalized()
            hw.append([[p + s * a + t * b_ + n * c for a, b_ in ((-34.0, -26.0), (34.0, -26.0), (34.0, 26.0), (-34.0, 26.0))] for c in (-2.0, 7.0)])
            hw.append([hs.circle(p + n * 9.0 - t * 30.0, t, 9.0, 0.0, 10), hs.circle(p + n * 9.0 - t * 30.0, t, 9.0, 60.0, 10)])
        hl = SURF_H.hit(Vector((-2660.0, sgn * 2600.0, 500.0)), (0.0, -float(sgn), 0.0))
        if hl is not None:
            p, n = hl
            t = Vector((1.0, 0.0, 0.0))
            s = n.cross(t).normalized()
            hw.append([[p + t * a + s * b_ + n * c for a, b_ in ((-56.0, -17.0), (56.0, -17.0), (56.0, 17.0), (-56.0, 17.0))] for c in (-2.0, 6.0)])
        if hw:
            hs.finish(hs.skins(f'cockpit_door_hardware_{sd}', hw), 1.5, CLAY)
