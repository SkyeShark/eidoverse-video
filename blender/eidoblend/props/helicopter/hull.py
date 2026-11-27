"""eidoblend.props.helicopter.hull: the airframe's skin, its hollow, its openings, their glass and frames.

ONE lofted skin from the nose's bill to the tail (datum.HULL), hollowed by a liner a wall's thickness inside it
(datum.CAVITY: the cockpit and the cabin, a flat floor, a ceiling); every opening cut SQUARE through that wall, so the
wall left between two openings IS the post between them; each pane is the skin's own patch set into its opening, held
by a retainer strip and its screws with a seal under it (the windshields, the chin and overhead windows), or by a pale
moulded seal that is the frame (the gunner and cockpit-door windows). The skin's faces are sorted for the look: the
painted skin, the liner (faces that look INTO the hollow), the floor. Leaves b.surf: the uncut skin to ask.
"""

from __future__ import annotations

import bpy
from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from ..hardsurface.sections import stations
from . import datum as D


def hull_skin(name):
    xs = (stations(D.X_FACE, D.X_B_POST, 45.0, D.HULL_MUST) + stations(D.X_B_POST, D.X_TAPER, 140.0, D.HULL_MUST)[1:]
          + stations(D.X_TAPER, D.X_TAIL, 70.0, D.HULL_MUST)[1:])
    return bt.loft_body(name, D.HULL, xs, front=D.nose_rings())


def side_pts(outline, sgn):
    """an outline in the side view as points in that side's own plane (sgn +1 the right, -1 the left)"""
    return [Vector((x, sgn * D.W, z)) for x, z in outline]


def build(b):
    CLAY, GLASS, RUBBER, LINER, FLOOR = b.clay, b.glass, b.rubber, b.liner, b.floor
    # ---------------------------------------------------------------- the skin and the hollow
    hull = hull_skin('hull')
    ref = hull_skin('hull_ref')                               # the uncut skin, to ask (swept away at the end)
    bpy.context.view_layer.update()
    SURF = bt.Surface(ref)
    b.surf = SURF
    cx = stations(D.CAV_X0, D.X_CABIN0, 60.0, D.HULL_MUST) + stations(D.X_CABIN0, D.CAV_X1, 300.0, [D.DOOR_X0, D.DOOR_X1])[1:]
    hull = hs.boolean(hull, hs.rings('cavity', [D.CAVITY.ring(x) for x in cx]), 'DIFFERENCE')

    # ---------------------------------------------------------------- the openings: (name, cutter's outline, how it is cut)
    OPENINGS = []                                             # (name, pts on the cutter's plane, direction OUT of the skin, glass?)
    door = hs.rrect(D.DOOR_X0, D.DOOR_Z0, D.DOOR_X1, D.DOOR_Z1, 60.0)
    cdw = bt.round_poly(D.COCKPIT_DOOR_WINDOW, 70.0)
    for sgn, sd in ((1, 'r'), (-1, 'l')):
        out = (0.0, float(sgn), 0.0)
        OPENINGS.append((f'cabin_doorway_{sd}', side_pts(door, sgn), out, False))
        for i, (x0, z0, x1, z1) in enumerate(D.GUNNER_PANES):
            OPENINGS.append((f'gunner_window_{sd}_{i}', side_pts(hs.rrect(x0, z0, x1, z1, 90.0), sgn), out, True))
        OPENINGS.append((f'cockpit_door_window_{sd}', side_pts(cdw, sgn), out, True))
        # the side windshield: the quadrilateral between the centre post and the A-pillar, set in from both and from its
        # sill and head, cut square to its own plane
        pb, pt = Vector((D.WS_FOOT[0], sgn * D.WS_FOOT[1], D.WS_FOOT[2])), Vector((D.WS_HEAD[0], sgn * D.WS_HEAD[1], D.WS_HEAD[2]))
        ab, at_ = Vector((D.A_FOOT[0], sgn * D.A_FOOT[1], D.A_FOOT[2])), Vector((D.A_HEAD[0], sgn * D.A_HEAD[1], D.A_HEAD[2]))
        nrm = (at_ - pb).cross(ab - pt)
        nrm.normalize()
        if nrm.z < 0.0:
            nrm = -nrm
        cen = (pb + pt + ab + at_) / 4.0
        u, v, nrm = bt.basis(nrm, (1.0, 0.0, 0.0))
        quad = [((p - cen).dot(u), (p - cen).dot(v)) for p in (pb, pt, at_, ab)]
        area = sum(quad[i][0] * quad[(i + 1) % 4][1] - quad[(i + 1) % 4][0] * quad[i][1] for i in range(4))
        ins = []                                              # each edge moved in by the frame's width, corners re-met
        for i in range(4):
            a, b_, c = Vector(quad[i - 1]), Vector(quad[i]), Vector(quad[(i + 1) % 4])
            e0, e1 = (b_ - a).normalized(), (c - b_).normalized()
            n0, n1 = Vector((-e0.y, e0.x)) * (1 if area > 0 else -1), Vector((-e1.y, e1.x)) * (1 if area > 0 else -1)
            a0, b1 = a + n0 * D.PANE_INSET, b_ + n1 * D.PANE_INSET
            den = e0.x * e1.y - e0.y * e1.x
            t = ((b1.x - a0.x) * e1.y - (b1.y - a0.y) * e1.x) / den
            ins.append(a0 + e0 * t)
        OPENINGS.append((f'windshield_{sd}', bt.on_plane(cen, u, v, bt.round_poly([(p.x, p.y) for p in ins], 38.0)), tuple(nrm), True))
        # the overhead pane, cut down through the roof
        oh = bt.round_poly([(x, sgn * y) for x, y in D.OVERHEAD_WINDOW], 40.0)
        OPENINGS.append((f'overhead_window_{sd}', [Vector((x, y, 1500.0)) for x, y in oh], (0.0, 0.0, 1.0), True))
        # the chin window, cut square to the nose's lower side
        cn = Vector((D.CHIN['normal'][0], sgn * D.CHIN['normal'][1], D.CHIN['normal'][2])).normalized()
        cu, cv, cn = bt.basis(cn, (1.0, 0.0, 0.0))
        if cv.z < 0.0:
            cv = -cv
        c_at = Vector((D.CHIN['at'][0], sgn * D.CHIN['at'][1], D.CHIN['at'][2]))
        OPENINGS.append((f'chin_window_{sd}', bt.on_plane(c_at, cu, cv, bt.round_poly(D.CHIN['outline'], 80.0)), tuple(cn), True))
    # the centre windshield: between the posts, on the 45 degree plane from the foot to the head
    su = Vector((1.0, 0.0, 1.0)).normalized()
    s_len = (Vector(D.WS_HEAD) - Vector(D.WS_FOOT)).length
    c_out = bt.round_poly([(D.PANE_INSET + 6.0, -D.CENTRE_PANE_HALF), (s_len - D.PANE_INSET, -D.CENTRE_PANE_HALF),
                           (s_len - D.PANE_INSET, D.CENTRE_PANE_HALF), (D.PANE_INSET + 6.0, D.CENTRE_PANE_HALF)], 36.0)
    OPENINGS.append(('windshield_c', [Vector((D.WS_FOOT[0], 0.0, D.WS_FOOT[2])) + su * a + Vector((0.0, 1.0, 0.0)) * b_ for a, b_ in c_out],
                     (-0.7071, 0.0, 0.7071), True))
    # (a cutter goes only a wall's thickness IN, so it never comes out again through the far side)
    for name, pts, out, _glass in OPENINGS:
        hull = hs.boolean(hull, bt.prism('cut_' + name, pts, out, -140.0, 400.0), 'DIFFERENCE')
    bt.finish_smooth(hull, CLAY)
    # what each face of it IS, for its materials: the painted skin (and the openings' cut edges); the liner (faces that
    # look INTO the hollow); the floor
    hull.data.materials.append(LINER)
    hull.data.materials.append(FLOOR)
    n_liner = n_floor = 0
    for p in hull.data.polygons:
        c = p.center / hs.MM
        _loc, nrm, dist = SURF.near(c)
        if dist > 20.0 and nrm.dot(p.normal) < -0.35 and D.CAV_X0 - 5.0 <= c.x <= D.CAV_X1 + 5.0:
            if p.normal.z > 0.7 and c.z < D.floor_z(c.x) + 30.0:
                p.material_index, n_floor = 2, n_floor + 1
            else:
                p.material_index, n_liner = 1, n_liner + 1
    print(f'[helicopter] hull: {len(hull.data.polygons)} faces; {n_liner} of the liner, {n_floor} of the floor')

    # ---------------------------------------------------------------- each opening's glass, retainer, seal and screws
    STRIP = [(-13.0, -1.5), (-13.0, 2.6), (-11.5, 3.5), (30.5, 3.5), (32.0, 2.6), (32.0, -1.5)]       # the retainer: 45 wide, 3.5 proud
    SEAL = [(-25.0, -9.0), (-25.0, -2.5), (-22.0, 0.6), (-14.0, 0.6), (-12.0, -1.5), (-12.0, -9.0)]   # the bead between glass and strip
    PALE = [(-9.0, -1.5), (-9.0, 3.0), (-6.5, 5.0), (9.0, 5.0), (12.0, 2.5), (12.0, -1.5)]            # a moulded seal that IS the frame
    for name, pts, out, glass in OPENINGS:
        path = bt.border(SURF, pts, out)
        if len(path) < 8:
            print(f'[helicopter] no border for {name}')
            continue
        if not glass:
            continue
        bt.pane('pane_' + name, hull_skin('solid_' + name), SURF, bt.prism('keep_' + name, pts, out, -140.0, 400.0), GLASS)
        if name.startswith(('gunner', 'cockpit_door')):
            bt.frame('seal_' + name, path, PALE, RUBBER)
        else:
            bt.frame('strip_' + name, path, STRIP, CLAY)
            bt.frame('seal_' + name, path, SEAL, RUBBER)
            bt.screws('screws_' + name, path, CLAY, s=10.0, h=3.5, pitch=48.0)
