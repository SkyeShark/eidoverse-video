"""The axolotl's fins as thin membranes (AXOLOTL_PLAN.md §5.6): the clay's SHELL patches (AX2). Life mm in the plan frame
of the bind (heads/caudate.Body's frame); families/sprawl.py scales them to metres at x4 and moves their vertices with
the body's pose (each vertex rides its root's station).

THE HEIGHTS (AX2's call at the vent, species/axolotl.py profile.fin_call_x2): the tail's TOTAL depth wins (§2.2's p08
profile and the literature's 25.8 mm at 0.60-0.66: p08's tail reads as mostly core with low fins), the core is AX0b's
shared reading (p01 backlit, crisp near the vent), so behind 0.60 the fins are the total less the core, the ventral fin
rig.vfin_share of them (from 0 at the vent). Over the trunk the dorsal fin is p01's own (profile.dorsal_fin over
profile.fin_scale) times profile.fin_scale_x2 (the fins' ratio to p01's along the tail at the shared core), blended
into the tail's over fin_blend_x2 so it never steps at the vent.

THE PATCHES: each fin a planar strip on the midline (x = 0) from its ROOT, buried `bury` mm inside the body under the
body's dorsal or ventral outline (caudate.Body.top_bot) but never past the core's mid-depth (the thin tail tip), to
its MARGIN, ROWS rows across, a column every `step` mm; the
half-thickness eases from the root's to the margin's (fins.half_thickness, [E]: the backlit render gates it at AX9).
The tail tip closes both fins to its point.
"""
import numpy as np

ROWS = 8
STEP = 1.6          # mm between columns (life)
BURY = 1.2          # mm the root lies under the body's outline


def _smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def heights(spec, body, s):
    """(dorsal, ventral) fin heights in mm at station s (the module docstring)"""
    from ..families import sprawl as SPR
    pr, st, rg = spec['profile'], spec['stations'], spec['rig']
    TL = spec['a1']['TL']
    s = float(s)
    origin, vent = st['fin_origin'], st['vent']
    own = np.asarray(pr['dorsal_fin'], np.float64)
    own = np.column_stack([own[:, 0], own[:, 1] / pr['fin_scale']])
    slope = (own[-1, 1] - own[-2, 1]) / (own[-1, 0] - own[-2, 0])

    def trunk(s_):
        if s_ <= origin:
            return 0.0
        v = np.interp(s_, own[:, 0], own[:, 1]) if s_ <= own[-1, 0] else own[-1, 1] + slope * (s_ - own[-1, 0])
        # the fin rises from nothing at its origin (p01's first row sits at 0.20)
        return pr['fin_scale_x2'] * v * _smooth01((s_ - origin) / 0.03)

    def tail(s_):
        s_ = max(s_, vent)
        tot = np.interp(s_, *np.asarray(pr['tail_total'], np.float64).T)
        if s_ > pr['tail_total'][-1][0]:                    # the last row (0.98) to the point at 1
            tot = pr['tail_total'][-1][1] * (1.0 - s_) / (1.0 - pr['tail_total'][-1][0])
        fins = max(tot - SPR.core_depth(spec, s_), 0.0)
        vs = rg['vfin_share'] * _smooth01((s_ - vent) / (pr['fin_blend_x2'][1] - vent))
        return (1.0 - vs) * fins, vs * fins

    a, b = pr['fin_blend_x2']
    if s <= a:
        d, v = trunk(s), 0.0
    elif s >= b:
        d, v = tail(s)
    else:
        w = _smooth01((s - a) / (b - a))
        dt, vt = tail(s)
        d = (1 - w) * trunk(s) + w * dt
        v = vt if s > vent else 0.0
    if s <= vent:
        v = 0.0
    return d * TL, v * TL


def patches(spec, body):
    """the dorsal and the ventral fin as SHELL patches: each (V (n, 3) mm, F (m, 3), half-thickness (n,) mm, stations
    (n,) of each vertex's root)"""
    TL = spec['a1']['TL']
    st = spec['stations']
    th_root, th_margin = spec['fins']['half_thickness']
    out = {}
    for name, s_a in (('dorsal', st['fin_origin']), ('ventral', st['vent'])):
        n_col = int(np.ceil((1.0 - s_a) * TL / STEP)) + 1
        ss = np.linspace(s_a, 1.0, n_col)
        V, H, S = [], [], []
        for s in ss:
            top, bot = body.top_bot(min(s, 0.9995))
            d, v = heights(spec, body, s)
            h = d if name == 'dorsal' else v
            # the root never passes the core's mid-depth: near the tail tip the core is thinner than BURY, and a root
            # buried the full BURY crossed it, so each fin poked out of the far side and the two shells printed an
            # arrowhead at the tip (the AX2 restart's look)
            mid = 0.5 * (top + bot)
            if s >= 1.0 - 1e-9:
                y_root = y_out = mid
            elif name == 'dorsal':
                y_root, y_out = max(top - BURY, mid), top + h
            else:
                y_root, y_out = min(bot + BURY, mid), bot - h
            z = float(body.z(s))
            for r in range(ROWS + 1):
                f = r / ROWS
                V.append((0.0, y_root + (y_out - y_root) * f, z))
                H.append(th_root + (th_margin - th_root) * f)
                S.append(s)
        V = np.array(V)
        F = []
        for c in range(n_col - 1):
            for r in range(ROWS):
                a0 = c * (ROWS + 1) + r
                b0 = (c + 1) * (ROWS + 1) + r
                F += [[a0, b0, b0 + 1], [a0, b0 + 1, a0 + 1]]
        out[name] = (V, np.array(F, np.int64), np.array(H), np.array(S))
    return out
