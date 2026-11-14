"""FIT: where accessories seat on a creature, computed offline against the creature's block-out SDF
(work/bestiary/patches/accessories_fit.md). Per socket, a SEAT FRAME and a SEAT TABLE go into the socket's seat node
(glTF extras); the runtime matches a prop's own fit data (its opening, its probes) to them, so one prop serves every
creature.

    R, o, n = seat(prog, near, axis_out, forward, tilt)     the seat: the skin's top along a tilted up, and its frame
    T = seat_table(prog, o, R, depths)                      the skin's section below the seat, per depth
    pl = hat_placement(T, opening, depth=None, scale=None)  a hat's depth, offset and per-axis scale on that table
    M = placement_matrix(o, R, pl)                          prop -> creature (4 x 4)
    d = clearance(prog, M, probes)                          the prop's probes' skin distances
    pl, rep = fit_hat(prog, o, R, T, prop_fit)              placed AND checked (deepened until clear): the validated
                                                            depth the export stores per (socket, prop)
    rig = eye_rig(prog, eyes, forward, up)                  glasses on any eye pair (bridge, spacing, splay, hooks)

sdf.Program.project takes the OUTWARD direction: from outside it marches against it, from inside along it.
"""
import numpy as np

DEFAULT_DEPTH_SHARE_OF_TABLE = 0.45     # the default seat: 45 % of the way down the measured table


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def frame(up, forward):
    """columns (x, y, z): y = up, z = forward made perpendicular to it, x = y cross z (the wearer's left)"""
    y = unit(up)
    f = np.asarray(forward, np.float64)
    z = unit(f - y * np.dot(f, y))
    return np.column_stack([np.cross(y, z), y, z])


def slerp_dir(a, b, w):
    """the direction w of the way from a to b"""
    a, b = unit(a), unit(b)
    ang = np.arccos(np.clip(np.dot(a, b), -1.0, 1.0))
    if ang < 1e-9:
        return a
    return unit(np.sin((1.0 - w) * ang) * a + np.sin(w * ang) * b)


def support(prog, near, up, radius=0.04, n=33, lift=0.08, rounds=10):
    """the skin's highest point along `up` around `near`: parallel rays down `up` from an n x n disc of starts above
    it, re-centred on the best hit each round: while that hit lies at the disc's rim the top is beyond it (same radius,
    moved), else the disc narrows to 4 grid steps; returns the point and the skin's normal there (the octopus at
    tilt 1: the top lies 46 mm from the apex, past a 40 mm disc: a fixed narrowing stalled at the rim, 9.7 degrees
    off). A ray whose sphere trace stalls (status 1: a SWEEP's slope-corrected field is compressed x33.7 above the
    octopus's mantle apex, the egg's r ~ sqrt(s) end) ends in the projector's Newton step on the skin's nearest
    point: a true skin point, so it competes too (counting status 0 only, the apex itself was never a candidate:
    tilt 0 seated 18.8 mm off it, 16 degrees off up)"""
    y = unit(up)
    e1 = unit(np.cross(y, [0.0, 0.0, 1.0] if abs(y[2]) < 0.9 else [1.0, 0.0, 0.0]))
    e2 = np.cross(y, e1)
    c = np.asarray(near, np.float64)
    best = None
    for _ in range(rounds):
        g = np.linspace(-radius, radius, n)
        U, V = np.meshgrid(g, g)
        m = (U ** 2 + V ** 2) <= radius ** 2
        o = c + y * lift + U[m][:, None] * e1 + V[m][:, None] * e2
        p, st = prog.project(o, np.tile(y, (len(o), 1)), maxd=2.0 * lift)
        ok = (st <= 1) & (np.abs(prog.eval(p)) < 1.0e-5)
        if not ok.any():
            break
        best = p[ok][int(np.argmax(p[ok] @ y))]
        w = best - c
        off = np.linalg.norm(w - y * np.dot(w, y))
        c = best
        if off > 0.8 * radius:
            continue
        if radius < 2.0e-4:
            break
        radius = 4.0 * radius / (n - 1)
    if best is None:
        raise ValueError('support: no ray met the skin')
    return best, unit(prog.normals(best[None])[0])


def seat(prog, near, axis_out, forward, tilt=0.55, world_up=(0.0, 1.0, 0.0), max_off_deg=2.0):
    """a seat on a rounded top (a mantle's apex, a skull's crown): up = the part's outward axis turned `tilt` of the
    way toward world up; origin = the skin's highest point along it near `near`; forward = the creature's forward made
    perpendicular. Returns (R (3, 3): columns x y z, origin (3,), the skin normal at the origin). On a smooth convex
    top the skin's normal at its highest point IS up: more than max_off_deg off means the support search did not
    find the top, and the seat is refused rather than shipped crooked"""
    up = slerp_dir(axis_out, world_up, tilt)
    o, n = support(prog, near, up)
    off = float(np.degrees(np.arccos(np.clip(np.dot(unit(n), up), -1.0, 1.0))))
    if off > max_off_deg:
        raise ValueError(f'seat: the skin normal at the support point is {off:.1f} deg off up (tilt {tilt}): '
                         f'not the top of the skin along it')
    return frame(up, forward), o, n


def section(prog, origin, R, depth, n=96, rmax=0.25, rounds=3):
    """the skin's section by the plane `depth` below the seat (perpendicular to R[:, 1]): the first crossing outward
    along n rays in the plane from a centre, re-centred on the ring's area centroid `rounds` times. Returns
    dict(points, centre, rx, rz (semi-axes along R[:, 0], R[:, 2]), cx, cz (the extents' centre in the seat frame),
    r_mean (the circle of the same area), ok (every ray found the skin))"""
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    o = np.asarray(origin, np.float64)
    c = o - y * depth
    ang = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    d = np.cos(ang)[:, None] * x + np.sin(ang)[:, None] * z
    for _ in range(rounds):
        p, st = prog.project(np.tile(c, (n, 1)), d, maxd=rmax)
        q = np.column_stack([(p - o) @ x, (p - o) @ z])
        q1 = np.roll(q, -1, axis=0)
        cr = q[:, 0] * q1[:, 1] - q1[:, 0] * q[:, 1]
        A = 0.5 * cr.sum()
        cq = ((q + q1) * cr[:, None]).sum(0) / (6.0 * A)
        c = o + x * cq[0] - y * depth + z * cq[1]
    lo, hi = q.min(0), q.max(0)
    return dict(points=p, centre=c, rx=float(0.5 * (hi[0] - lo[0])), rz=float(0.5 * (hi[1] - lo[1])),
                cx=float(0.5 * (hi[0] + lo[0])), cz=float(0.5 * (hi[1] + lo[1])),
                r_mean=float(np.sqrt(abs(A) / np.pi)), ok=bool((st == 0).all()))


def seat_table(prog, origin, R, depths, n=96):
    """rows (depth, rx, rz, cx, cz, r_mean) of the skin's section below the seat (metres, the seat frame); rows whose
    rays failed are dropped"""
    rows = []
    for dp in depths:
        s = section(prog, origin, R, float(dp), n)
        if s['ok']:
            rows.append([float(dp), s['rx'], s['rz'], s['cx'], s['cz'], s['r_mean']])
    return np.array(rows)


def monotone_rows(T):
    """the table's leading rows while r_mean grows (a hat's opening must meet one section per size)"""
    keep = 1
    while keep < len(T) and T[keep, 5] > T[keep - 1, 5]:
        keep += 1
    return T[:keep]


def hat_placement(table, opening, depth=None, scale=None, max_aniso=1.25):
    """a hat's opening (rx, rz: its semi-axes on its seat plane, prop space) on a seat table. Given a depth, the
    scale follows (each axis matched to the section there); given a scale, the depth follows (where the section's
    mean semi-axis equals the scaled opening's mean). The axes' ratio is clamped to max_aniso by GROWING the smaller
    (a hat may sit loose, never inside the skin); sy = sqrt(sx sz) keeps the hat's proportions. Returns
    dict(depth, translation (seat frame: the opening's centre), scale (3,))"""
    T = np.asarray(table, np.float64)
    ox, oz = float(opening['rx']), float(opening['rz'])
    if depth is None:
        rm = np.sqrt(T[:, 1] * T[:, 2])
        if not np.all(np.diff(rm) > 0):
            raise ValueError('the seat table does not grow with depth: give a depth (or monotone_rows)')
        depth = float(np.interp(np.sqrt(ox * oz) * float(scale), rm, T[:, 0]))
    rx, rz, cx, cz = (float(np.interp(depth, T[:, 0], T[:, k])) for k in (1, 2, 3, 4))
    sx, sz = rx / ox, rz / oz
    if sx > sz * max_aniso:
        sz = sx / max_aniso
    elif sz > sx * max_aniso:
        sx = sz / max_aniso
    return dict(depth=depth, translation=[cx, -depth, cz], scale=[sx, float(np.sqrt(sx * sz)), sz])


def placement_matrix(origin, R, pl):
    """prop space -> creature space: the seat frame, the opening's offset in it, the per-axis scale"""
    M = np.eye(4)
    M[:3, :3] = R @ np.diag(pl['scale'])
    M[:3, 3] = np.asarray(origin, np.float64) + R @ np.asarray(pl['translation'], np.float64)
    return M


def clearance(prog, M, probes):
    """the probes (n, 3, prop space) through M: their skin distances (m; negative = inside the skin)"""
    P = np.asarray(probes, np.float64).reshape(-1, 3)
    return prog.eval(P @ M[:3, :3].T + M[:3, 3]).astype(np.float64)


def fit_hat(prog, origin, R, table, prop_fit, depth=None, scale=None, clear=0.0015, contact=0.0015, headroom=0.005,
            auto=True, step=0.001):
    """a hat placed and CHECKED: at the requested depth (or size, else DEFAULT_DEPTH_SHARE_OF_TABLE down the table),
    then with `auto` deeper by `step` until the brim's underside probes clear the skin by `clear` (a breathing mantle
    moves its skin ~1 mm against the hat), the opening's probes touch it within `contact`, and the crown keeps
    `headroom` over the skin's top. Returns (placement, report): the report's depth is what the export stores as the
    socket's validated depth for this prop"""
    T = np.asarray(table, np.float64)
    if depth is None and scale is None:
        depth = DEFAULT_DEPTH_SHARE_OF_TABLE * float(T[-1, 0])
    d = hat_placement(T, prop_fit['opening'], depth=depth, scale=scale)['depth']
    while True:
        pl = hat_placement(T, prop_fit['opening'], depth=d)
        M = placement_matrix(origin, R, pl)
        cb = clearance(prog, M, prop_fit['probes']['brim_under'])
        co = clearance(prog, M, prop_fit['probes']['opening'])
        room = float(prop_fit['crown_inner_height']) * pl['scale'][1] - d
        rep = dict(depth=float(d), brim_min=float(cb.min()), contact_max=float(np.abs(co).max()), headroom=room,
                   ok=bool(cb.min() >= clear and np.abs(co).max() <= contact and room >= headroom))
        if rep['ok'] or not auto or d + step > T[-1, 0] + 1e-12:
            return pl, rep
        d += step


def eye_rig(prog, eyes, forward, up=(0.0, 1.0, 0.0), standoff=0.003, hook_back=0.035, bridge_lift=0.5):
    """glasses on an eye pair: eyes = [(centre, radius, optical axis) for the left, then the right]. The BRIDGE is the
    skin met from the eyes' midpoint along their mean axis turned `bridge_lift` of the way toward up (forward-facing
    eyes: the nose's root; lateral eyes: over the head between them). Each TEMPLE rests on the skin hook_back behind
    its eye, along the eye's outward side. Returns a dict (world, metres): bridge, bridge_normal, spacing, and per
    eye: centre, radius, axis, splay (degrees about up from forward, + toward the creature's left), pitch (degrees
    up), exit (where the optical axis leaves the skin: a mound or a brow can stand past the eyeball), lens (its centre,
    standoff off the exit), hook"""
    f, u = unit(forward), unit(up)
    left = np.cross(u, f)
    (cL, rL, aL), (cR, rR, aR) = eyes
    mid = 0.5 * (np.asarray(cL, np.float64) + np.asarray(cR, np.float64))
    d = slerp_dir(unit(unit(aL) + unit(aR)), u, bridge_lift)
    p, st = prog.project(mid[None], d[None], maxd=0.2)
    out = dict(bridge=p[0], bridge_normal=unit(prog.normals(p[:1])[0]), bridge_ok=bool(st[0] == 0),
               spacing=float(np.linalg.norm(np.asarray(cL) - np.asarray(cR))), eyes=[])
    for (c, r, a), side in (((cL, rL, aL), 1.0), ((cR, rR, aR), -1.0)):
        a = unit(a)
        c = np.asarray(c, np.float64)
        lat = a - f * np.dot(a, f) - u * np.dot(a, u)
        lat = unit(lat) if np.linalg.norm(lat) > 1e-3 else left * side
        h, sth = prog.project((c - f * hook_back)[None], lat[None], maxd=0.2)
        # the axis's exit through the skin: from the eye's centre outward (the octopus's mound stands 5.7 mm past its
        # eyeball: a lens set off the eyeball sat inside the skin)
        x, stx = prog.project(c[None], a[None], maxd=0.1)
        out['eyes'].append(dict(centre=c, radius=float(r), axis=a,
                                splay=float(np.degrees(np.arctan2(np.dot(a, left), np.dot(a, f)))),
                                pitch=float(np.degrees(np.arcsin(np.clip(np.dot(a, u), -1.0, 1.0)))),
                                exit=x[0], lens=x[0] + a * standoff, hook=h[0],
                                hook_ok=bool(sth[0] == 0) and bool(stx[0] == 0)))
    return out
