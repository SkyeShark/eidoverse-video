"""THE CONNECTING HOSE of the first full cyborg octopus (C5b, the lead's decision 4; C5c, his decisions 1-3;
work/bestiary/research/CYBORG_PLAN.md A.2.2 feed lines, A.4.2 hoses across knuckles, the lead's A.9 decision 6: both
ends on a plate or a mount, never a free end): one braided hose from the mantle's plates to the mech tentacle's flange,
its OWN MESH (it crosses onto the arm's STACKED texels, so it is geometry, not paint; forge/cyborg.py stays read only),
its own fittings seated ON the plate and on the flange's collar, saddle-pad clamps along the arm.

  THE ROUTE    from a plate of the default look (the front-left plate: no feed port on it, the nearest to the arm) down
               the mantle's flank and the head's side under the eye to the arm's aboral midline at its root, then along
               that midline to the flange: a shortest path over the plated octopus's low (scipy's Dijkstra on its edge
               graph), every other plate, the feed lines, the eye and its lids, the web and the oral side priced out of
               it, then smoothed on the skin
  THE HOLDS    the plate FITTING (the tentacle's own boss and 45 deg ferrule, copied from its low, its texels stacked)
               seated on the plate (its boss sunk below the skin all round); four CLAMPS (C5c: forge/cyborg_pads.py, soft
               rubber saddle pads whose undersides are the skin's own surface, the strap over the hose, its tabs riveted
               to the pad's shoulders) at the middles of segments CLAMP_SEG, each pad vertex on the skin's weights under
               it; the INLET PORT on the collar (C5b), its own copy of the tentacle's fitting mirrored to lean back
               toward the body, 50 deg round the chord on the creature's side and 2 mm past the tentacle's own boss, rigid
               on bone 7 (the collar's bone)
  THE RUNS     (C5c) the hose comes down off the fitting onto the skin within DESCEND_N r and LIES on it (its weights
               the skin's under it, smoothed along it near the breathing bones: W_SIG) to the arm, climbing into each
               pad's cradle over RAMP_N r;
               between two clamps a span LIES on the skin unless the arm bends concave under it in the reference pose:
               there the hose's length as laid on the straight arm makes an ARCH (its bow h sin^2: it leaves each pad
               along its axis), a different size per span and per seed, never a festoon; one lying span carries a gentle
               lateral S-turn; the last span rises over joint 7 and the soft roll into the port
  THE TUBE     assembled in the recipe seed's REFERENCE pose (the rest pose at t 0: the replaced arm's proximal half holds
               still in time there, only the breathing moves it): every bind point carried there by its weights, the
               arches and the pads drawn there, then resampled, framed (rotation-minimizing) and ringed there; each ring
               and each pad vertex goes back to the bind by the inverse of its own packed skin matrix, so the runtime's
               skinning shows the reference pose's hose exactly; cached by seed (hose_for_seed)
  THE SLEEVE   its own small tiling set (REPEAT along and round): the tentacle's braid (cyborg_limb BRAID, the same
               16 carriers and lay as its hose) on the rubber row (forge/cyborg.py cyb_gasket, read only), composed from
               the braid's own height field, no bake; the fittings keep the tentacle's set (its material); the pads,
               straps and rivets their own small set (cyborg_pads.pad_maps)

Read with numpy and scipy (warp's CPU device for the rays and the closest points).
"""
import math
import os

import numpy as np

from . import cyborg_limb as CL
from . import cyborg_octopus as CO

TAU = 2.0 * math.pi
REPO = CO.REPO
PLATE_DEFAULT = 12          # the default look's front-left plate (row 2, the flank +X): no feed port, nearest the arm
EYE_CLEAR = 0.027           # the route keeps this far from the eye's centre (the eyeball 15 mm, its lids to 1.35 Re)
FEED_CLEAR = 0.008          # and this far from every feed line's centreline
PLATE_CLEAR = 0.004         # and this far outside every other plate's outline


def plate_geometry(plates_pkl, low, device='cpu'):
    """the plate layout's plates and feed lines in the creature's frame: each plate's outline (its chart polygon cast
    on the canonical low through the body chart, forge/cyborg.py read only), centre, normal; each feed line's chart
    route cast likewise. Returns dict(plates [dict(index, outline (n, 3), centre, normal, heads (m, 3))], feed [(kind,
    polyline (n, 3))], chart)"""
    import pickle
    from . import cyborg as CY
    with open(plates_pkl, 'rb') as f:
        P = pickle.load(f)
    lay = P['layout']
    ch = CY.body_chart(low, device=device)
    out = []
    fas = lay.get('fasteners') or []
    for p in lay['plates']:
        poly = np.asarray(p['poly_uw'], np.float64)
        ol = ch.from_uw(poly)
        c = np.asarray(p['centre'], np.float64)
        _, _, nrm, _ = ch.tangents(np.asarray(p['centre_uw'], np.float64)[None])
        heads = np.array([np.asarray(h['p'], np.float64) for h in fas if int(h['plate']) == int(p['index'])])
        hD = float(np.median([h['D'] for h in fas])) if fas else 0.0
        out.append(dict(index=int(p['index']), outline=ol, centre=c, normal=nrm[0], uw=poly,
                        centre_uw=np.asarray(p['centre_uw'], np.float64), Lu=float(p['Lu']), Lw=float(p['Lw']),
                        heads=heads.reshape(-1, 3), head_D=hD, raw=p))
    feed = []
    fd = lay.get('feed') or {}
    for ln in fd.get('lines', []):
        L = float(ln.get('length', 0.05))
        lam = np.linspace(0.0, 1.0, max(8, int(L / 1.0e-3)))
        feed.append((ln['kind'], ln.get('side'), ch.from_uw(CY.feed_route_uw(ln, lam))))
    return dict(plates=out, feed=feed, chart=ch, layout=lay)


def _point_in_poly2(P, poly):
    """points (n, 2) inside a closed polygon (m, 2), even-odd"""
    x, y = P[:, 0], P[:, 1]
    inside = np.zeros(len(P), bool)
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        cond = (a[1] > y) != (b[1] > y)
        xc = a[0] + (y - a[1]) * (b[0] - a[0]) / np.where(np.abs(b[1] - a[1]) < 1e-30, 1e-30, b[1] - a[1])
        inside ^= cond & (x < xc)
    return inside


def _seg_dist2(P, A, B):
    """the distance from points P (n, 2) to segments A-B (m, 2): (n,) the least"""
    d = np.full(len(P), np.inf)
    for a, b in zip(A, B):
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-30), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    return d


def fitting_site(geo, plate, r_boss, margin=None):
    """the plate fitting's site: the chart point inside the plate, its boss clear of the plate's seams (its outline,
    shrunk by the boss radius and a margin) and its fastener heads (a head diameter clear of the boss's rim), toward the
    plate's front (+u, the head) and its lateral edge, the farthest from everything among those. Returns (point, normal,
    uw, clearances)"""
    ch = geo['chart']
    p = geo['plates'][plate]
    margin = p['head_D'] if margin is None else margin
    uw0 = p['centre_uw']
    poly = p['uw']
    hu = ch.to_uw(p['heads']) if len(p['heads']) else np.zeros((0, 2))
    best = None
    for du in np.linspace(-0.5, 0.5, 41) * p['Lu']:
        for dw in np.linspace(-0.5, 0.5, 61) * p['Lw']:
            q = uw0 + np.array([du, dw])
            if not _point_in_poly2(q[None], poly)[0]:
                continue
            c_seam = float(_seg_dist2(q[None], poly, np.roll(poly, -1, 0))[0]) - r_boss
            c_head = float(np.min(np.linalg.norm(hu - q, axis=1))) - r_boss - 0.5 * p['head_D'] if len(hu) else 1.0
            if c_seam < margin or c_head < margin:
                continue
            score = min(c_seam, c_head) + 0.25 * du - 0.05 * dw     # the front (+u), the flank (-w: +X here)
            if best is None or score > best[0]:
                best = (score, q, c_seam, c_head)
    if best is None:
        raise ValueError(f'plate {plate}: no site for a {r_boss * 1e3:.1f} mm boss clear of its seams and heads')
    _, q, cs, chd = best
    pt = ch.from_uw(q[None])[0]
    _, _, nrm, _ = ch.tangents(q[None])
    return pt, nrm[0], q, dict(seam=cs, head=chd)


def edge_graph(V, F, cost):
    """the low's edge graph weighted by length x the mean vertex price"""
    import scipy.sparse as sp
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    w = np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1) * 0.5 * (cost[e[:, 0]] + cost[e[:, 1]])
    n = len(V)
    return sp.coo_matrix((np.concatenate([w, w]), (np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]]))),
                         shape=(n, n)).tocsr()


def arm_top(oct_, j, s, lift=0.0):
    """points on arm j's aboral midline at shares s (the bind): the centreline point (the joint polyline at s), the
    aboral axis there (the joints' y frames interpolated, made normal to the chord), and the skin's top along it (a ray
    against the low); lifted `lift` along it"""
    from .species import octopus as O
    from .species import octopus_rig as OR
    js = OR.arm_joint_s(O.low_spec(O.SPEC))
    b = oct_.arm_bind(j)
    P, Rw = b['P'], b['Rw']
    s = np.atleast_1d(np.asarray(s, np.float64))
    k = np.clip(np.searchsorted(js, s, side='right') - 1, 0, len(js) - 2)
    a = ((s - js[k]) / (js[k + 1] - js[k]))[:, None]
    c = P[k] + a * (P[k + 1] - P[k])
    t = P[k + 1] - P[k]
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    y = (1 - a) * Rw[k][:, :, 1] + a * Rw[k + 1][:, :, 1]
    y -= np.einsum('ij,ij->i', y, t)[:, None] * t
    y /= np.linalg.norm(y, axis=1, keepdims=True)
    hit = _ray_low(oct_, c, y, 0.06)
    return hit + lift * y, y, t, c


_RAYMESH = {}


def _ray_low(oct_, org, dirs, tmax):
    """first hits of rays against the low (warp, CPU device): (n, 3), nan where none"""
    import warp as wp
    from . import cyborg as CY
    key = id(oct_)
    if key not in _RAYMESH:
        _RAYMESH[key] = CY._mesh(oct_.low['V'], oct_.F, 'cpu')
    mesh = _RAYMESH[key]
    org = np.atleast_2d(np.asarray(org, np.float64))
    dirs = np.atleast_2d(np.asarray(dirs, np.float64))
    m = len(org)
    ot = wp.zeros(m, dtype=float, device='cpu')
    of = wp.zeros(m, dtype=wp.int32, device='cpu')
    wp.launch(CY.k_rays, dim=m, inputs=[mesh.id, wp.array(org.astype(np.float32), dtype=wp.vec3, device='cpu'),
                                        wp.array(dirs.astype(np.float32), dtype=wp.vec3, device='cpu'),
                                        wp.array(np.full(m, float(tmax), np.float32), dtype=float, device='cpu'), ot,
                                        of], device='cpu')
    t_, f_ = ot.numpy().astype(np.float64), of.numpy()
    return np.where((f_ >= 0)[:, None], org + t_[:, None] * dirs, np.nan)


def mech_islands(path=None):
    """the mech tentacle's island index (work/bestiary/cyborg_c5b/mech_islands.json: per island its region, piece, body
    and vertex / face ranges in the shipped glb's order, from cyborg_limb.make_asset) and its hose's design numbers"""
    import json
    path = path or os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5b', 'mech_islands.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def copy_islands(mech, islands, which):
    """the glb's triangles of the named islands, re-indexed: V, N, TAN (x, y, z, w), UV (the forge's v up: 1 - glTF v),
    F. which(island) -> bool"""
    sel = [it for it in islands if which(it)]
    assert sel, 'no island matched'
    vid = np.concatenate([np.arange(*it['v']) for it in sel])
    fid = np.concatenate([np.arange(*it['f']) for it in sel])
    remap = -np.ones(len(mech.V), np.int64)
    remap[vid] = np.arange(len(vid))
    F = remap[mech.F[fid]]
    assert (F >= 0).all(), 'an island face outside its vertex range'
    UV = np.column_stack([mech.UV[vid, 0], 1.0 - mech.UV[vid, 1]])
    return dict(V=mech.V[vid].copy(), N=mech.N[vid].copy(), TAN=mech.TAN[vid].copy(), UV=UV, F=F,
                pieces=sorted({it['piece'] for it in sel}))


def place(part, R, t, o=None, s=1.0, mirror_x=None):
    """a copied part moved: (mirrored across the plane x = mirror_x in its own frame, winding and handedness flipped),
    scaled by s about o, rotated by R, translated to t: p' = t + R s (p - o)"""
    V, N, T = part['V'].copy(), part['N'].copy(), part['TAN'].copy()
    F = part['F'].copy()
    if mirror_x is not None:
        V[:, 0] = 2.0 * mirror_x - V[:, 0]
        N[:, 0] = -N[:, 0]
        T[:, 0] = -T[:, 0]
        T[:, 3] = -T[:, 3]
        F = F[:, ::-1].copy()
    o = np.zeros(3) if o is None else np.asarray(o, np.float64)
    R = np.asarray(R, np.float64)
    return dict(V=np.asarray(t, np.float64) + (s * (V - o)) @ R.T, N=N @ R.T,
                TAN=np.column_stack([T[:, :3] @ R.T, T[:, 3]]), UV=part['UV'].copy(), F=F, pieces=part['pieces'])


def hermite(p0, t0, p1, t1, n, bow=None, h=0.0, k0=1.0, k1=1.0, bp=1.0):
    """a cubic Hermite from p0 (tangent t0) to p1 (tangent t1), its tangents scaled by the chord (times k0, k1), plus an
    optional bow h sin^2(pi u^bp) along `bow`: (n, 3) points, u from 0 to 1. The bow has zero slope at both ends, so an
    arch leaves each hold along that hold's own tangent (C5b check: h sin(pi u) left every clamp face at ~25 deg, a cusp
    at each clamp); its extra length for a given h is the same as sin(pi u)'s to first order (h^2 pi^2 / 4c both). bp > 1
    moves its crest toward p1 (to u = 0.5^(1 / bp))"""
    c = float(np.linalg.norm(p1 - p0))
    u = np.linspace(0.0, 1.0, n)[:, None]
    h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    P = h00 * p0 + h10 * c * k0 * t0 + h01 * p1 + h11 * c * k1 * t1
    if bow is not None and h:
        P = P + h * np.sin(np.pi * u ** bp) ** 2 * np.asarray(bow, np.float64)
    return P


def _arclen(P):
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())


def rmf(P, ref):
    """rotation-minimizing frames along a polyline (the double reflection method, Wang et al. 2008): tangents T and the
    normals E1 transported from ref made normal to the first tangent"""
    P = np.asarray(P, np.float64)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    e = np.asarray(ref, np.float64) - T[0] * (np.asarray(ref, np.float64) @ T[0])
    e /= np.linalg.norm(e)
    E = [e]
    for i in range(len(P) - 1):
        v1 = P[i + 1] - P[i]
        c1 = v1 @ v1
        if c1 < 1e-24:
            E.append(E[-1])
            continue
        rL = E[-1] - (2.0 / c1) * (v1 @ E[-1]) * v1
        tL = T[i] - (2.0 / c1) * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        r_ = rL - (2.0 / c2) * (v2 @ rL) * v2 if c2 > 1e-24 else rL
        r_ -= T[i + 1] * (r_ @ T[i + 1])
        E.append(r_ / np.linalg.norm(r_))
    return T, np.array(E)


def resample(P, max_step, max_turn=0.15):
    """a polyline resampled: steps at most max_step and turning at most max_turn (rad) each. C5f (the lead's call 7):
    the steps spread EVENLY in the metric max(1 / max_step, kappa / max_turn) ds, the fewest that keep both bars, each
    the same share of it (so each keeps both). The greedy walk before laid every step at its bar and left what remained
    to the last one, up to 1.3 x max_step: arch 1's 1.37-1.52 mm step near its end on seeds 6, 12 and 15, where the
    swim's turn bar failed (the C5e check)"""
    P = np.asarray(P, np.float64)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    T = np.gradient(P, s, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    kap = np.linalg.norm(np.gradient(T, s, axis=0), axis=1)
    rate = np.maximum(1.0 / max_step, kap / max_turn)
    mu = np.concatenate([[0.0], np.cumsum(0.5 * (rate[1:] + rate[:-1]) * np.diff(s))])
    n = max(1, int(math.ceil(mu[-1] - 1e-9)))
    t = np.interp(np.linspace(0.0, mu[-1], n + 1), mu, s)
    return np.column_stack([np.interp(t, s, P[:, k]) for k in range(3)]), t


_CLOSEST = {}


def skin_closest(oct_, pts):
    """the closest point of the low to each point: (points (n, 3), face, Warp's barycentrics u, v)"""
    import warp as wp
    from .species import octopus_suckers as OS
    key = id(oct_)
    if key not in _CLOSEST:
        _CLOSEST[key] = wp.Mesh(points=wp.array(np.asarray(oct_.low['V'], np.float32), dtype=wp.vec3, device='cpu'),
                                indices=wp.array(np.asarray(oct_.F, np.int32).ravel(), dtype=wp.int32, device='cpu'))
    fc, u, v = OS.mesh_closest(_CLOSEST[key], np.asarray(pts, np.float64), 0.05)
    assert (fc >= 0).all(), 'a hose point with no skin within 5 cm'
    X = OS.bary_eval(oct_.low['V'], oct_.F, fc, u, v)
    return X, fc, u, v


def skin_frames(oct_, fc, u, v):
    """the low's interpolated (glb) normal and skin weights at closest points: normals (n, 3), joints (n, 4), weights
    (n, 4) (the three corners' influences merged, the top four kept continuously: rig.limit_influences)"""
    from . import rig as RG
    from .species import octopus_suckers as OS
    nV = len(oct_.low['V'])
    N = OS.bary_eval(oct_.N[:nV], oct_.F, fc, u, v)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    nJ = len(oct_.rig.jnames)
    Wd = np.zeros((len(fc), nJ))
    c = oct_.F[fc]
    for corner, b in ((0, u), (1, v), (2, 1.0 - u - v)):
        for slot in range(4):
            np.add.at(Wd, (np.arange(len(fc)), oct_.J[c[:, corner], slot]), b * oct_.W[c[:, corner], slot])
    J, W = RG.limit_influences(Wd, 4)
    return N, J.astype(np.int64), W.astype(np.float64)


def smooth_on_skin(oct_, P, step=2.0e-3, iters=40, alpha=0.5):
    """a skin path resampled at `step` and smoothed (Laplacian, its ends held), each pass projected back onto the low"""
    P = np.asarray(P, np.float64)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    n = max(3, int(round(s[-1] / step)) + 1)
    t = np.linspace(0.0, s[-1], n)
    Q = np.column_stack([np.interp(t, s, P[:, k]) for k in range(3)])
    for _ in range(iters):
        Q[1:-1] = (1 - alpha) * Q[1:-1] + alpha * 0.5 * (Q[:-2] + Q[2:])
        Q[1:-1] = skin_closest(oct_, Q[1:-1])[0]
    return Q


def plan_route(oct_, geo, arm, plate, start, s_join, log=print):
    """the shortest path over the low (Dijkstra) from the plate fitting's foot to arm `arm`'s aboral midline at share
    s_join, every vertex priced: x60 within PLATE_CLEAR of another plate's outline or inside it (its outline projected on
    its tangent plane), x60 within FEED_CLEAR of a feed line, x400 within EYE_CLEAR of the left eye's centre (and the
    right's), x400 on the right side or on another arm's tube, x40 facing down (the oral side, under the web). Returns
    the path's vertex ids and points"""
    from scipy.sparse.csgraph import dijkstra
    V, F = oct_.low['V'], oct_.F
    n = len(V)
    vn = np.zeros((n, 3))
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for c in range(3):
        np.add.at(vn, F[:, c], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)
    cost = np.ones(n)
    for p in geo['plates']:
        if p['index'] == plate:
            continue
        c, nr = p['centre'], p['normal']
        near = np.linalg.norm(V - c, axis=1) < 0.06
        e1 = np.cross(nr, [0.0, 1.0, 0.0])
        if np.linalg.norm(e1) < 1e-6:
            e1 = np.cross(nr, [1.0, 0.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(nr, e1)
        pr = lambda X: np.column_stack([(X - c) @ e1, (X - c) @ e2])
        poly = pr(p['outline'])
        Q = pr(V[near])
        bad = _point_in_poly2(Q, poly) | (_seg_dist2(Q, poly, np.roll(poly, -1, 0)) < PLATE_CLEAR)
        idx = np.nonzero(near)[0][bad]
        cost[idx] = np.maximum(cost[idx], 60.0)
    for _, _, pl in geo['feed']:
        from scipy.spatial import cKDTree
        d, _ = cKDTree(pl).query(V)
        cost[d < FEED_CLEAR] = np.maximum(cost[d < FEED_CLEAR], 60.0)
    W = oct_.rig.worlds()
    for nm in ('eye_L', 'eye_R'):
        E = W[oct_.rig.index[nm]][:3, 3]
        cost[np.linalg.norm(V - E, axis=1) < EYE_CLEAR] = 400.0
    cost[V[:, 0] < -0.004] = 400.0
    # the funnel (its axis from fa to fb, radii fra..frb) and a band round it: the siphon breathes, and a hose over it
    # reads as plugged into it
    from .species import octopus as O
    fa, fb, fra, frb = O.funnel_geom(O.SPEC)
    ax = fb - fa
    tf = np.clip(((V - fa) @ ax) / (ax @ ax), 0.0, 1.0)
    df = np.linalg.norm(V - (fa + tf[:, None] * ax), axis=1)
    cost[df < (fra + (frb - fra) * tf) + 0.008] = 400.0
    reg_v = np.full(n, -1)
    for r_ in range(int(oct_.region.max()) + 1):
        reg_v[np.unique(F[oct_.region == r_])] = r_
    other = (reg_v >= 3) & (reg_v != 3 + arm)
    cost[other] = 400.0
    cost[vn[:, 1] < -0.35] = np.maximum(cost[vn[:, 1] < -0.35], 40.0)
    # the low carries split copies at its UV seams: the graph runs on the welded vertices (one per position)
    key = np.round(V / 1.0e-7).astype(np.int64)
    _, rep, wid = np.unique(key, axis=0, return_index=True, return_inverse=True)
    wid = wid.reshape(-1)
    cw = np.zeros(len(rep))
    np.maximum.at(cw, wid, cost)
    G = edge_graph(V[rep], wid[F], cw)
    src = int(wid[np.argmin(np.linalg.norm(V - start, axis=1))])
    tgt_pt = arm_top(oct_, arm, [s_join])[0][0]
    tgt = int(wid[np.argmin(np.linalg.norm(V - tgt_pt, axis=1))])
    dist, pred = dijkstra(G, indices=src, return_predecessors=True)
    path = [tgt]
    while path[-1] != src:
        path.append(int(pred[path[-1]]))
        if path[-1] < 0:
            raise ValueError('no route')
    path = rep[np.array(path[::-1])]
    tgt = path[-1]
    dist = {tgt: dist[wid[tgt]]}
    log(f'[hose] route: {len(path)} vertices, {np.linalg.norm(np.diff(V[path], axis=0), axis=1).sum() * 1e3:.1f} mm over '
        f'the skin, priced length {dist[tgt] * 1e3:.1f}; the prices on it: max {cost[path].max():.0f}')
    return np.array(path), V[path], cost


# ============================================================================================ the hose built
RIDE_GAP = -0.18e-3         # a lying run's underside nominally 0.18 mm into the skin (the contact window: pressed in at
                            # most SADDLE_SINK, off it at most the seat bar, as the pads and the roll are judged; where it
                            # bridges a valley under the eye at BEND_STILL it stood 0.39 mm off at 0.1, c05c)
SIDES = 12                  # the sleeve's sides (U5 at 0.15 mm on a 4.2 mm hose; the tentacle's own hose carries 8)
SLACK = 0.03                # an arch's rest length over the farthest its holds come apart in motion, at least
SADDLE_SINK = 0.6e-3        # a clamp's saddle and the plate fitting's boss sunk this far under the skin at their seat
PORT_PHI = 50.0             # deg: the bulkhead's inlet port round the chord from the collar's top toward the creature's
                            # side the arm lies on (an L arm's +X: the side the hero stations look at), short of the
                            # collar's lug (-78..-101 deg there)
PORT_DX = 2.0e-3            # and along it past the tentacle's own boss (the most the collar's span takes), so the hose
                            # leaving its back-leaning ferrule clears the soft roll (p15: the port 0.29 mm off the roll,
                            # 4.6 mm off the original fitting, 1.6 mm off the lug, 1.3 mm off the collar's ends and screws,
                            # 1.1 mm off the band, 6.9 mm off the tentacle's hose; the outlet's line 0.23 mm off the roll)
TILE_PERIODS = 8            # the sleeve's tile along: this many braid periods (it repeats seamlessly along and round)
RING_STEP = 1.2e-3          # C5d: a ring at most this far from the next (the runtime cable bends the hose with the skin:
                            # its tightest designed bend, 7.3 mm, turns 9.4 deg per step here; C5c's 1.6 r turned 15-50
                            # deg per step in the swim)
BELLOWS = dict(pitch=0.71, amp=0.12, compress=(0.60, 1.15))
                            # C5f (the lead's call 5): an ARCH (the span over joint 2, clamp 1 to clamp 2) is a CONVOLUTED
                            # section. The swim presses its pads' chord from ~38.7 to ~27.5 mm with ~41 mm of hose between
                            # them, and held along the pads no curve of that length avoids an omega loop (C5e: 7.42-7.52 mm
                            # at best; drawn, a 12 mm curl at 6.6 mm, the C5e check's k_swim_hero). Whole convolutions of
                            # about `pitch` x r between its plain ends (BELLOWS_END x r at each pad's face), their valleys
                            # `amp` x r in (the crests at r: never past the hose's envelope), a ring every quarter pitch; the
                            # runtime keeps its length over its chord at its rest ratio, within `compress` of its rest length
                            # (runtime/cyborg_cable.js: a bellows span), so the convolutions bunch and the arch keeps its
                            # rest shape: a flex section across the joint, as braided convoluted hose is made
BELLOWS_END = 0.8           # x r: the plain hose at each end of a bellows (the ring knots 0.8 r outside each pad's face)


def _ease(u, e=0.25):
    return CL._ramp(u, True, True, e)


def taubin(P, iters=12, lam=0.5, mu=-0.53):
    """a polyline smoothed by Taubin's lambda|mu passes (its two ends held): the short kinks go, the long bends stay
    (no Laplacian shrink). C5b check: the riding run's base path (the closest points on the faceted low, offset along
    the interpolated normals) turned up to 13 deg per 1.1 mm (a 5 mm bend radius, 1.2 r) where it crossed the low's
    facet edges"""
    Q = np.asarray(P, np.float64).copy()
    for _ in range(iters):
        for f in (lam, mu):
            Q[1:-1] = Q[1:-1] + f * (0.5 * (Q[:-2] + Q[2:]) - Q[1:-1])
    return Q


def keep_off(P, A, B, C, clear, hold=1, iters=6):
    """a polyline's points (its first and last `hold` held) pushed out along the skin's face normal until each stands at
    least `clear` off the skin (triangles A, B, C: the skin posed as the polyline is), then Taubin-smoothed, a few rounds:
    a rise from the skin into a hold that a free curve would cut into the skin where the skin is concave (C5b check: the
    rise into clamp 1, drawn as a hermite, dipped 0.75 mm into the valley at the arm's root)"""
    from scipy.spatial import cKDTree
    Q = np.asarray(P, np.float64).copy()
    tree = cKDTree((A + B + C) / 3.0)
    sl = slice(hold, len(Q) - hold)
    clear = np.broadcast_to(np.asarray(clear, np.float64), (len(Q),))[sl]
    for it in range(iters + 1):
        sd, ti = CO.point_tri_near(Q[sl], A, B, C, k=32, tree=tree)
        n = np.cross(B[ti] - A[ti], C[ti] - A[ti])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
        push = np.maximum(clear - sd, 0.0)
        if not (push > 1e-7).any():
            break
        Q[sl] += push[:, None] * n
        if it < iters:                                   # the last round pushes only: every point keeps its clearance
            # (the smoothing holds the same `hold` points at each end: smoothing all but the two end points turned
            # the rise's held ferrule tangent into a 1.8 mm bend at the port, c05c)
            Q[hold - 1:len(Q) - hold + 1] = taubin(Q[hold - 1:len(Q) - hold + 1], iters=4)
    return Q


# ============================================================================================ C5c: the hose rebuilt
CLAMP_SEG = (1, 2, 4, 6)    # the clamps (saddle pads) on these segments, at CLAMP_AT of each (0 its proximal joint, 1 its
CLAMP_AT = (0.50, 0.35, 0.68, 0.58)  # distal): the span over joint 2 (the rest pose's largest bend, +5..+10 deg concave in
                            # every seed), the span over joints 3-4 (+0..+8: its humps clear of the pads' ramps), the span
                            # over joints 5-6 (straight: the lying run with its S-turn), the rise over joint 7 and the
                            # soft roll into the inlet port (cyborg_c5c p06: the arm's proximal half holds still in time in
                            # every seed; only the breathing and the swim rig move it)
THETA_MIN = 2.0             # deg: a joint bending concave this much or more in the reference pose gives the hose slack over it
ARCH_K = 0.45               # the slack: ARCH_K x (the arm's top radius there + r) x the bend (rad): the hose laid straight is
                            # that much longer than the arm's top over the bent joint (the LBS skin itself stretches at the
                            # arm's root where the body drops, so the skin's own lengths cannot say it)
ARCH_JOINT = 2              # Stage 3: the span over this joint arches whatever the rest pose's own bend there: the swim presses
ARCH_BEND = (3.7, 10.3)     # its pads' chord ~30 %, which only C5f's bellows takes (lying, C5e's omega came back: 6.7 mm at ring
                            # 291). On the rest pose's tent the joint is convex, -6 deg on every seed, so the slack reads a
                            # seeded design bend (deg): the spread the rest poses' own bends had before the tent
SHORT_SPAN = 0.060          # a span between pads shorter than this ARCHES from pad to pad over its bend; a longer one lies
HUMP_W = 7.0                # on the skin with a HUMP over each bend, its feet this many r apart round the joint
HUMP_WS = (7.0, 8.0)        # Stage 4: per seed and hump, its feet this many r apart (never nearer the joint than HUMP_W:
                            # the lifts' feet near joint 4 dipped into the skin in the swim)
HUMP_SLACK = (1.0, 1.5)     # and its slack this many times the bend's own
JOIN_DS = 0.035             # the route reaches the arm's top midline this far (in s) short of clamp 1
BEND_MIN = 8.0e-3           # the curves' tightest bend (the C5b check's smoothness bar: 7.3 mm) where the skin breathes
BEND_STILL = 7.6e-3         # and where the rest motion holds the skin under it still (the body, the head, the arm)
BEND_DESCENT = 8.4e-3       # the descent from the plate fitting, on the breathing mantle (it closed 7.7 mm to 7.1, c05c)
BREATHING = ('mantle_1', 'mantle_2', 'funnel')  # the bones the rest motion moves under the hose: the mantle's breathing
S_SPAN = 2                  # the span (from 0: clamps 1-2, 2-3, 3-4) that lies on the skin with the S-turn
S_AMP = 1.5                 # the S-turn's lateral swing (x r) off the arm's top midline and back, zero slope at both clamps
                            # (C5d: C5c's 0.85, a 3.6 mm swing, read only in the hero still)
MEANDER_SPAN = 1            # C5d (the lead's call 3): the long run (clamps 2-4, 117 mm, ruler-straight in C5c) gets NATURAL
MEANDER_AMP = 0.75          # SLACK: lateral meanders (seeded bumps of the profile, each up to this x r, half-widths
MEANDER_W = (0.14, 0.24)    # MEANDER_W of the span: bends of 15 mm and gentler; zero value and slope at both clamps,
MEANDER_N = (2, 4)          # alternating sides, this many) and a few small LIFTS (free humps: seeded places, widths LIFT_W r
LIFT_N = (1, 3)             # and slack LIFT_EX m, this many), different per seed, mostly still lying
LIFT_W = (4.5, 7.0)         # (Stage 4: 6-9 r found no room beside the tent's hump at joint 3; 4.5 r = 19 mm, 7 r = 30)
LIFT_EX = (0.12e-3, 0.40e-3)
LIFT_GAP = 2.0              # Stage 4: a lift's base at least this many r from the run's ends and from every other hump
LIFT_JOINT = 3.0            # and each of its feet this many r off every joint (a foot near a bending joint dips: h1)
LOOP_JOINT = 4              # Stage 4 (h3): the first lift is a SERVICE LOOP centred on this joint of the long run, as the
LOOP_W = (7.0, 8.0)         # hump over joint 3 is centred on its joint: its feet this many r apart round the joint
LOOP_SHIFT = 0.5            # and its centre seeded within this many r of it
LOOP_GROWTH = 1.5           # (h3c) its slack the seeded share plus this many times its feet's chord growth over the
                            # motion: at 1.0 (h3) its last free ring stood -0.082 .. +0.111 mm off the skin through the swim
                            # over the 16 seeds (seeds 5 and 7 under it), the far foot 3 rings before ramp 4a
DESCEND_N = 4.4             # the descent from the plate fitting's ferrule onto the skin spans this many r of the skin path
                            # (C5b: 8 r, a 5-6 mm flight over the mantle for ~35 mm; at 3.6 r its tightest bend, 7.7 mm
                            # in the reference pose, closed to 7.1 mm as the mantle breathed)
W_SIG = 3.5                 # the lying runs' weights (the skin's under each ring) smoothed along the hose by a Gaussian of
                            # this many r, easing to none over the ramps into each pad (the pad, the hose in its cradle and
                            # the strap take the skin's own there): where the mantle's bones meet, the skin's weights turn
                            # over 9 mm and the breathing tilted the rings 3.3 deg off the tube (c05c)
RISE_CLEAR = 0.40e-3        # the rise into the port kept this far off the flange's pieces (the soft roll, the collar, its
                            # ends, screws, band and boss, rigid on bone 7) and off the skin (c05c: the hermite from clamp
                            # 6 to the port cut 2.5 mm into the soft roll; C5b's rise passed the roll at 0.25 mm)
RAMP_N = 2.8                # the hose climbs from lying on the skin into a pad's cradle (PAD T r higher) over this many r
RAMP_BACK = 1.5             # Stage 3: clamp 1's ramp starts this many r earlier still: it bridges the crease at joint 1
FERRULE_LEAN = 70.0         # deg: the plate fitting's ferrule off its boss's axis (the tentacle's own leans 45)


def limit_bends(Q, keep, bend_min, hold=1, rounds=40):
    """a polyline (its first and last `hold` points held) relaxed where it bends tighter than bend_min: shrinking passes on
    the tight stretch (each point drawn toward its neighbours' mean: the curve lifts out of a valley it cannot follow,
    bridging it, or rounds a corner), then keep(Q) (the push back off whatever it must clear), until no bend is tighter
    or `rounds` run out"""
    Q = np.asarray(Q, np.float64).copy()
    bm = np.broadcast_to(np.asarray(bend_min, np.float64), (len(Q),))[1:-1]
    for _ in range(rounds):
        rad_l, _ = _bend_radius(Q)
        if (rad_l >= bm).all():
            break
        tight = np.zeros(len(Q), bool)
        tight[1:-1] = rad_l < bm
        tight = np.convolve(tight.astype(float), np.ones(9), mode='same') > 0
        tight[:hold] = False
        tight[len(Q) - hold:] = False
        for _ in range(4):
            sm_ = 0.5 * (Q[:-2] + Q[2:])
            Q[1:-1] = np.where(tight[1:-1, None], 0.5 * Q[1:-1] + 0.5 * sm_, Q[1:-1])
        Q = keep(Q)
    return Q


def _bend_radius(P):
    """per interior point of a polyline its bend radius (m): the mean step over the turn"""
    d = np.diff(P, axis=0)
    sg = np.linalg.norm(d, axis=1)
    t = d / np.maximum(sg[:, None], 1e-20)
    c = np.clip((t[1:] * t[:-1]).sum(1), -1.0, 1.0)
    ang = np.arccos(c)
    return 0.5 * (sg[1:] + sg[:-1]) / np.maximum(ang, 1e-9), np.degrees(ang)


_RAYS = {}


def _ray_mesh(key, V, F, org, dirs, tmax):
    """first hits of rays against a triangle mesh (warp, CPU device), cached by key: points (n, 3) and faces (n,), nan /
    -1 where none"""
    import warp as wp
    from . import cyborg as CY
    if key not in _RAYS:
        _RAYS[key] = CY._mesh(V, F, 'cpu')
    mesh = _RAYS[key]
    org = np.atleast_2d(np.asarray(org, np.float64))
    dirs = np.atleast_2d(np.asarray(dirs, np.float64))
    m = len(org)
    ot = wp.zeros(m, dtype=float, device='cpu')
    of = wp.zeros(m, dtype=wp.int32, device='cpu')
    wp.launch(CY.k_rays, dim=m, inputs=[mesh.id, wp.array(org.astype(np.float32), dtype=wp.vec3, device='cpu'),
                                        wp.array(dirs.astype(np.float32), dtype=wp.vec3, device='cpu'),
                                        wp.array(np.full(m, float(tmax), np.float32), dtype=float, device='cpu'), ot,
                                        of], device='cpu')
    t_, f_ = ot.numpy().astype(np.float64), of.numpy()
    return np.where((f_ >= 0)[:, None], org + t_[:, None] * dirs, np.nan), f_


_CLOSEST_REF = {}


def _closest_ref(key, V, F, pts, maxd=0.05):
    """the closest point of a posed copy of the low (V, F) to each point: (points, face, u, v)"""
    import warp as wp
    from .species import octopus_suckers as OS
    if key not in _CLOSEST_REF:
        _CLOSEST_REF[key] = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device='cpu'),
                                    indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device='cpu'))
    fc, u, v = OS.mesh_closest(_CLOSEST_REF[key], np.asarray(pts, np.float64), maxd)
    assert (fc >= 0).all(), 'a point with no posed skin within reach'
    return OS.bary_eval(V, F, fc, u, v), fc, u, v


def s_turn(u):
    """the S-turn's lateral profile over a span, u in [0, 1]: sin 2 pi u - sin 4 pi u / 2 (zero value and zero slope at
    both ends: the hose leaves each clamp along its axis), peak 1.3 at u ~0.33 / 0.67"""
    u = np.asarray(u, np.float64)
    return np.sin(TAU * u) - 0.5 * np.sin(2.0 * TAU * u)


def build_hose(oct_, mech, geo, arm=CO.ARM_DEFAULT, plate=PLATE_DEFAULT, islands=None, motion=None, ref_worlds=None,
               seed=None, log=print):
    """THE HOSE (C5c, the lead's decisions 1-3) for one REFERENCE POSE (ref_worlds: the octopus's node worlds at the
    recipe seed's rest pose, t 0; the hose is cached by seed: hose_for_seed). Built in that pose and carried back to the
    bind ring by ring (each by the inverse of its own packed skin matrix: the runtime shows the reference tube exactly):
      the plate FITTING (the tentacle's boss, its ferrule leaned FERRULE_LEAN) on its plate; the hose leaves its ferrule
        and comes DOWN onto the skin within DESCEND_N r of the skin path (C5b: 8 r, a 5-6 mm flight), then LIES on the
        skin (its weights the skin's under it, smoothed along it: W_SIG) down the mantle's flank, under the eye, over the
        web onto the arm's top;
      four CLAMPS (forge/cyborg_pads.py: saddle pads on the skin, the strap over the hose) on segments CLAMP_SEG at
        CLAMP_AT, the hose climbing into each pad's cradle over RAMP_N r;
      between the clamps the SPANS, from the reference pose's own bends: a short span over a concave bend of THETA_MIN
        or more ARCHES from pad to pad (its slack ARCH_K x (the arm's top radius + r) x the bend: a different size per
        span and seed, never a festoon), a long one LIES on the skin with a HUMP over each such bend, the span S_SPAN
        lies flat with one gentle lateral S-turn (S_AMP r); the last span RISES from the last clamp over joint 7 and the
        soft roll into the inlet PORT (the tentacle's fitting mirrored on the collar, rigid on bone 7, C5b's), kept
        RISE_CLEAR off the flange's pieces and the skin;
      every curve relaxed until no bend is tighter than BEND_MIN.
    motion(names): the nodes' worlds over every frame the spans' slack is checked on (the seed's rest motion and the
    swim rig). Returns dict(sleeve, hard (the tentacle's set: the fittings), pads (the pads' set: pads, straps, rivets),
    joints, record, ...)"""
    from . import cyborg_pads as PD
    from . import rig as RG
    I = islands or mech_islands()
    r = float(I['r8'])
    isl = I['islands']
    j = arm
    b = oct_.arm_bind(j)
    P, Rw = b['P'], b['Rw']
    M = oct_.chord_M(j)
    C = np.einsum('kab,kbc->kac', Rw, M)
    from .species import octopus as O
    from .species import octopus_rig as OR
    js = OR.arm_joint_s(O.low_spec(O.SPEC))
    bone = lambda k: oct_.bone[f'arm{j}_{k:02d}']
    Vlow, F = oct_.low['V'], oct_.F
    nV = len(Vlow)
    assert ref_worlds is not None, 'C5c: the hose is built in a reference pose'
    Msk = oct_.rig.skin_mats(ref_worlds)
    Vref = CO.lbs(Vlow, oct_.J[:nV], oct_.W[:nV], Msk)
    import hashlib
    key_ref = ('ref', id(oct_), hashlib.sha1(np.ascontiguousarray(Vref).tobytes()).hexdigest())   # the whole posed skin:
    # the body's vertices are the same in every seed's pose (only the arms differ), so a part of it named every seed alike
    Mw = lambda wd_: sum(w_ * Msk[k_] for k_, w_ in wd_.items())
    to_ref = lambda wd_, p_: (Mw(wd_) @ np.append(p_, 1.0))[:3]

    def rot_ref(wd_, v_):
        u_ = Mw(wd_)[:3, :3] @ v_
        return u_ / np.linalg.norm(u_)

    def wdict(Jr, Wr):
        return {int(a_): float(w_) for a_, w_ in zip(Jr, Wr) if w_ > 0}

    def blend(wa, wb, t_):
        out = {}
        for k_, v_ in wa.items():
            out[k_] = out.get(k_, 0.0) + (1.0 - t_) * v_
        for k_, v_ in wb.items():
            out[k_] = out.get(k_, 0.0) + t_ * v_
        top = sorted(out.items(), key=lambda kv: -kv[1])[:4]
        s_ = sum(v_ for _, v_ in top)
        return {k_: v_ / s_ for k_, v_ in top}

    def ref_feet(pts):
        """the reference pose's skin under points (closest): foot, its normal (the bind's interpolated normal turned by
        the foot's blended linear part), its skin weights"""
        X, fc_, u_, v_ = _closest_ref(key_ref, Vref, F, pts)
        Nb, Jf, Wf = skin_frames(oct_, fc_, u_, v_)
        Nr = np.array([rot_ref(wdict(Jf[i_], Wf[i_]), Nb[i_]) for i_ in range(len(X))])
        return X, Nr, Jf, Wf
    # ---------------------------------------------------------------- the plate fitting and the route (bind)
    stations = [js[k] + f_ * (js[k + 1] - js[k]) for k, f_ in zip(CLAMP_SEG, CLAMP_AT)]
    fitting = copy_islands(mech, isl, lambda it: it['region'] == 'fitting')
    pt, nrm, uw, clr = fitting_site(geo, plate, 1.55 * r)
    s_join = stations[0] - JOIN_DS
    _, Pskin, _ = plan_route(oct_, geo, j, plate, pt, s_join, log=log)
    Pskin = smooth_on_skin(oct_, Pskin)
    d_init = Pskin[min(8, len(Pskin) - 1)] - Pskin[0]
    X_f = d_init - nrm * (d_init @ nrm)
    X_f /= np.linalg.norm(X_f)
    R_f = np.column_stack([X_f, nrm, np.cross(X_f, nrm)])
    xf = float(I['x_fitting'])
    y_low = float(fitting['V'][:, 1].min())
    o_f = np.array([xf, y_low + SADDLE_SINK, 0.0])
    E_a, d0_a = np.asarray(I['E']), np.asarray(I['d0'])
    # the plate fitting's FERRULE leans FERRULE_LEAN off the boss's axis, not the tentacle's 45 deg (its foot turns
    # about its base on the boss's top, inside the boss): the hose leaves 20 deg off the plate and lies down on the
    # mantle within DESCEND_N r without curling (at 45 deg it rose and turned over in 3.2 mm bends, or flew 5-6 mm
    # over the mantle for 35 mm as C5b's did)
    lean = math.radians(FERRULE_LEAN) - math.acos(float(np.clip(d0_a[1], -1.0, 1.0)))
    ax_l = np.cross(np.array([0.0, 1.0, 0.0]), d0_a)
    ax_l /= np.linalg.norm(ax_l)
    K_ = np.array([[0.0, -ax_l[2], ax_l[1]], [ax_l[2], 0.0, -ax_l[0]], [-ax_l[1], ax_l[0], 0.0]])
    R_l = np.eye(3) + math.sin(lean) * K_ + (1.0 - math.cos(lean)) * (K_ @ K_)
    is_fer = np.concatenate([np.full(it_['v'][1] - it_['v'][0], 'ferrule' in it_['piece'])
                             for it_ in isl if it_['region'] == 'fitting'])
    fit2 = dict(fitting, V=fitting['V'].copy(), N=fitting['N'].copy(), TAN=fitting['TAN'].copy())
    fit2['V'][is_fer] = E_a + (fitting['V'][is_fer] - E_a) @ R_l.T
    fit2['N'][is_fer] = fitting['N'][is_fer] @ R_l.T
    fit2['TAN'][is_fer, :3] = fitting['TAN'][is_fer, :3] @ R_l.T
    d0_a = R_l @ d0_a
    # C5f (the lead's call 10): the plate fitting CLOSED, by cyborg_feed.collar_mesh's construction (C3e's: the boss's
    # wall from its top on down under the skin all round, its top one fan, the ferrule capped with its back chamfered,
    # every vertex on the fitting's own texels) at the hose's own seat (SADDLE_SINK). Copied as it was (fit2: the
    # tentacle's islands, whose collar buries part of the boss and the ferrule's back) it stood on the plate with its
    # boss ring split and a stray shard beside the ferrule (the C3e check's sheets_hosefit/collars_fitting.png); fit2
    # still gives the ferrule's axis the hose's run follows
    from types import SimpleNamespace
    from . import cyborg_feed as CF
    cfx = SimpleNamespace(I=I, mech=mech, r8=r, low=dict(V=np.asarray(Vlow, np.float64)), F_head=F)
    plate_fit = CF.collar_mesh(cfx, dict(r=r, S=pt, x=R_f[:, 0], y=R_f[:, 1], z=R_f[:, 2]), sink=SADDLE_SINK)
    to_plate = lambda q: pt + (np.asarray(q) - o_f) @ R_f.T
    _, fcf, uf, vf = skin_closest(oct_, pt[None])
    _, Jff, Wff = skin_frames(oct_, fcf, uf, vf)
    fitw = wdict(Jff[0], Wff[0])
    # ---------------------------------------------------------------- the path on the skin (bind)
    # the route reaches the arm's top midline at s_join, JOIN_DS short of clamp 1; from there the ARM PART runs along the
    # top midline (arm_top, every 0.0025 in s, the stations on it exactly) to clamp 4; the join relaxed on the skin
    s_arm = np.unique(np.concatenate([np.arange(s_join, stations[-1], 0.0025), stations]))
    top, yv, tv, cv_ = arm_top(oct_, j, s_arm)
    n_rt = len(Pskin)
    Ps = np.vstack([Pskin[:-1], top])
    i_st = [n_rt - 1 + int(np.argmin(np.abs(s_arm - s_c))) for s_c in stations]
    a_j, b_j = max(1, n_rt - 1 - 10), min(len(Ps) - 1, n_rt - 1 + 10)
    for _ in range(16):
        Ps[a_j:b_j] = 0.5 * Ps[a_j:b_j] + 0.25 * (Ps[a_j - 1:b_j - 1] + Ps[a_j + 1:b_j + 1])
        Ps[a_j:b_j] = skin_closest(oct_, Ps[a_j:b_j])[0]
    assert i_st[0] > b_j, 'clamp 1 inside the relaxed join'
    sr_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Ps, axis=0), axis=1))])
    Xs, fc, uu, vv = skin_closest(oct_, Ps)
    Ns, Js, Ws = skin_frames(oct_, fc, uu, vv)
    from scipy.spatial import cKDTree
    # the arm's joint polyline length between two shares (rigid bones: the same in every pose): a span's run as laid
    # along the straight arm
    seg_L = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum_L = np.concatenate([[0.0], np.cumsum(seg_L)])
    centre_at = lambda s_: float(np.interp(s_, js[:len(cum_L)], cum_L))
    # the S-turn on span S_SPAN: a lateral swing on the skin between its two clamps (zero at both, zero slope there)
    ia, ib = i_st[S_SPAN], i_st[S_SPAN + 1]
    uS = (sr_[ia:ib + 1] - sr_[ia]) / (sr_[ib] - sr_[ia])
    tg = np.gradient(Xs, axis=0)
    tg /= np.linalg.norm(tg, axis=1, keepdims=True)
    lat = np.cross(tg, Ns)
    lat /= np.linalg.norm(lat, axis=1, keepdims=True)
    side_x = 1.0 if CO.ARM_LABELS[j][0] == 'L' else -1.0
    sgn_ = side_x * np.sign(lat[(ia + ib) // 2, 0] or 1.0)
    Xs2 = Xs.copy()
    Xs2[ia:ib + 1] += (sgn_ * S_AMP * r * s_turn(uS))[:, None] * lat[ia:ib + 1]
    # C5d (the lead's call 3): the long run's MEANDERS: seeded bumps cos^2(pi x / 2) of the lateral profile (centres
    # 0.26-0.74 of the span, half-widths MEANDER_W kept inside it: zero value and slope at both clamps), sizes and
    # sides differing per seed; laid on the skin like the S-turn
    rng_m = np.random.default_rng(7919 * int(seed or 0) + 101)
    ma, mb = i_st[MEANDER_SPAN], i_st[MEANDER_SPAN + 1]
    uM = (sr_[ma:mb + 1] - sr_[ma]) / (sr_[mb] - sr_[ma])
    nm_b = int(rng_m.integers(MEANDER_N[0], MEANDER_N[1]))
    cs_m = np.linspace(0.30, 0.70, nm_b) + rng_m.uniform(-0.04, 0.04, nm_b)
    prof_m = np.zeros_like(uM)
    sg_m = 1.0 if rng_m.random() < 0.5 else -1.0
    for q_m, c_m in enumerate(cs_m):
        hw_m = min(rng_m.uniform(*MEANDER_W), c_m - 0.02, 0.98 - c_m)
        x_m = np.clip((uM - c_m) / hw_m, -1.0, 1.0)
        prof_m += sg_m * (-1.0) ** q_m * rng_m.uniform(0.4, 1.0) * MEANDER_AMP * np.cos(0.5 * np.pi * x_m) ** 2
    Xs2[ma:mb + 1] += (prof_m * r)[:, None] * lat[ma:mb + 1]
    Xs, fc, uu, vv = skin_closest(oct_, Xs2)
    Ns, Js, Ws = skin_frames(oct_, fc, uu, vv)
    off = r + RIDE_GAP
    W_of = [wdict(Js[i_], Ws[i_]) for i_ in range(len(Xs))]
    # the LYING curve in the reference pose, exactly on its skin: each skin point carried there by its own barycentrics
    # (the reference pose's triangle), its normal the bind's turned by the point's blended linear part, the hose's axis
    # `off` out along it; smoothed (Taubin: the faceted low's closest points kink at its edges) and kept off the skin
    from .species import octopus_suckers as OS
    X_ref = OS.bary_eval(Vref, F, fc, uu, vv)
    N_ref = np.array([rot_ref(W_of[i_], Ns[i_]) for i_ in range(len(Xs))])

    def keep_off_ref(D_, clear):
        """a reference-pose polyline kept `clear` (per point) off the reference skin (its ends held)"""
        tree_ = cKDTree(D_)
        fsel = tree_.query(Vref[F].mean(1), distance_upper_bound=0.04)[0] < np.inf
        Fr_ = F[fsel]
        return keep_off(D_, Vref[Fr_[:, 0]], Vref[Fr_[:, 1]], Vref[Fr_[:, 2]], clear)

    def ref_height(pts):
        """points' signed distances off the reference skin (the hose's AXIS heights: a ring's underside is r lower)"""
        pts = np.atleast_2d(pts)
        tree_ = cKDTree(pts)
        fsel = tree_.query(Vref[F].mean(1), distance_upper_bound=0.04)[0] < np.inf
        Fr_ = F[fsel]
        # (32 candidate faces: with 12, a point over the arm's root's long faces read a farther face, 0.3-0.8 mm off)
        return CO.point_tri_near(pts, Vref[Fr_[:, 0]], Vref[Fr_[:, 1]], Vref[Fr_[:, 2]], k=32)[0]

    def eased_clear(Q, h_a, h_b, n_out=None):
        """a clearance profile along a join from its first point's height h_a to its last's h_b (eased), 0.05 mm under
        both: keep_off then lifts only what the straight hermite cuts into the skin, never past its own ends (a
        clearance over an end's own height bent the join against its held end: a fold)"""
        u_ = np.linspace(0.0, 1.0, len(Q))
        e_ = np.array([_ease(x_) for x_ in u_])
        return h_a + (h_b - h_a) * e_ - 0.05e-3
    # a hose of radius r cannot follow a valley tighter than BEND_MIN: rounds of Taubin and a push back off the skin
    # until no bend along it is tighter (it bridges such a valley, its underside lifting a little off its floor)
    # (BEND_MIN where the skin under it breathes, the mantle's bones moving it: the breathing closed a 7.7 mm bend to
    # 7.1; BEND_STILL where the rest motion holds it still: a valley under the eye bridged at BEND_MIN lifted the run 0.5
    # mm off the skin, c05c)
    breathes = np.array([sum(w_ for k_, w_ in wd_.items() if oct_.rig.jnames[k_].startswith(BREATHING)) > 0.02
                         for wd_ in W_of])
    bend_need = np.where(np.convolve(breathes.astype(float), np.ones(15), mode='same') > 0, BEND_MIN, BEND_STILL)
    keep_l = lambda Q_: keep_off_ref(Q_, off - 0.02e-3)
    lie_ref = limit_bends(keep_l(taubin(X_ref + N_ref * off, iters=20)), keep_l, bend_need)
    # then SETTLED: the smoothing lifts the run out of every short valley (0.5 mm under the eye with bends of 22 mm
    # there, c05c), so the run is let down along the skin's normal onto its lying height by a SMOOTH pull (each point's
    # height over it, spread by a Gaussian of two points so no point moves alone: point by point the pull left 14 deg
    # corners), halved round any point it would bring nearer the skin than its lying height or bend tighter than 1.15 x
    # its bar (the rings, resampled between these points, see a corner more sharply), a few rounds
    g_ = np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2)
    g_ /= g_.sum()
    sm_ = lambda x_: np.convolve(np.pad(x_, 6, mode='edge'), g_, mode='valid')
    for _ in range(12):
        d_ = np.maximum(ref_height(lie_ref) - off, 0.0)
        if d_[1:-1].max() < 0.03e-3:
            break
        t_ = sm_(d_)
        t_[[0, -1]] = 0.0
        for _ in range(6):
            Qt_ = lie_ref - t_[:, None] * N_ref
            bad_ = ref_height(Qt_) < off - 0.03e-3
            bad_[1:-1] |= _bend_radius(Qt_)[0] < 1.15 * bend_need[1:-1]
            bad_ = (np.convolve(bad_.astype(float), np.ones(7), mode='same') > 0) & (t_ > 0)
            if not bad_.any():
                break
            t_ = np.where(bad_, 0.5 * t_, t_)
            t_ = np.minimum(t_, sm_(t_) * 1.5)
            t_[[0, -1]] = 0.0
        lie_ref = lie_ref - t_[:, None] * N_ref
    lift_ = ref_height(lie_ref) - off
    top_ = np.argsort(-lift_)[:6]
    log(f'[hose] seed {seed}: the lying curve over its lying height by at most ' + ', '.join(
        f'{lift_[i_] * 1e3:.2f} mm (point {i_}, bend {_bend_radius(lie_ref)[0][max(min(i_ - 1, len(lie_ref) - 3), 0)] * 1e3:.1f}'
        f' / {bend_need[i_] * 1e3:.1f})' for i_ in top_))
    sl_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(lie_ref, axis=0), axis=1))])
    # the replaced arm's bends in the reference pose: per joint the chord frames' relative pitch (+ concave: the child
    # points up off its parent, the arm's top shortened over the joint)
    Wa_ref = ref_worlds[[oct_.rig.index[f'arm{j}_{k:02d}'] for k in range(CO.N_JOINTS)]]
    Cr = np.einsum('kab,kbc->kac', Wa_ref[:, :3, :3], M)
    pitch = np.zeros(CO.N_JOINTS)
    for k in range(1, CO.N_JOINTS - 1):
        d_ = Cr[k - 1].T @ Cr[k][:, 0]
        pitch[k] = math.degrees(math.atan2(d_[1], d_[0]))
    # ---------------------------------------------------------------- the clamps (reference pose)
    pd = PD.PAD
    L_pad = pd['L'] * r
    clamps = []
    for ci, (k, s_c, i_c) in enumerate(zip(CLAMP_SEG, stations, i_st)):
        a0, a1 = max(i_c - 3, 0), min(i_c + 3, len(lie_ref) - 1)
        x_ax = lie_ref[a1] - lie_ref[a0]
        x_ax /= np.linalg.norm(x_ax)
        foot, n_r, Jc, Wc = ref_feet(lie_ref[i_c][None])
        y_ax = n_r[0] - x_ax * (n_r[0] @ x_ax)
        y_ax /= np.linalg.norm(y_ax)
        z_ax = np.cross(x_ax, y_ax)
        wk = wdict(Jc[0], Wc[0])
        # the hose's axis over the pad: its cradle's floor PAD T r over the skin under it
        c0 = foot[0] + y_ax * ((1.0 + pd['T']) * r * 1.004)
        Rk = np.column_stack([x_ax, y_ax, z_ax])

        def skin_y(x_, z_, c0=c0, Rk=Rk):
            o_ = c0 + Rk @ np.array([x_, 2.5 * r, z_])
            hit, _ = _ray_mesh(key_ref, Vref, F, o_[None], -Rk[:, 1][None], 0.04)
            if not np.isfinite(hit).all():
                X_, _, _, _ = _closest_ref(key_ref, Vref, F, (c0 + Rk @ np.array([x_, -r, z_]))[None])
                hit = X_
            return float((hit[0] - c0) @ Rk[:, 1])
        pad_l = PD.pad_mesh(r, skin_y)
        strap_l, sites = PD.strap_mesh(r)
        rivs = [PD.rivet_mesh(r, s_) for s_ in sites]
        to_w = lambda Q: c0 + np.asarray(Q) @ Rk.T
        hu_ = ref_height(to_w(pad_l['V'][pad_l['part'] == 0])) - pd['seat']
        log(f'[hose]   clamp {k}: the pad\'s underside off its seat by {hu_.min() * 1e3:+.3f}..{hu_.max() * 1e3:+.3f} mm '
            f'as drawn')
        clamps.append(dict(k=k, s=s_c, i=i_c, c=c0, R=Rk, w=wk, foot=foot[0],
                           pad=dict(pad_l, V=to_w(pad_l['V']), N=pad_l['N'] @ Rk.T),
                           strap=dict(strap_l, V=to_w(strap_l['V']), N=strap_l['N'] @ Rk.T),
                           rivets=[dict(rv, V=to_w(rv['V']), N=rv['N'] @ Rk.T) for rv in rivs],
                           faces=(c0 - 0.5 * L_pad * x_ax, c0 + 0.5 * L_pad * x_ax)))
    # ---------------------------------------------------------------- the spans: arch or lying (reference pose)
    face_a = [cl['faces'][1] for cl in clamps[:-1]]
    face_b = [cl['faces'][0] for cl in clamps[1:]]
    n_ramp = RAMP_N * r
    seg_idx = lambda a_s, b_s: (int(np.searchsorted(sl_, a_s)), int(np.searchsorted(sl_, b_s)))
    spans = []
    carry = None
    if motion is not None:
        jn_all = oct_.rig.jnames
        names_m = sorted({jn_all[k_] for cl in clamps for k_ in cl['w']} | {f'arm{j}_{CO.J0:02d}'})
        Wm = motion(names_m)
        Mm = np.einsum('tjab,jbc->tjac', Wm, np.stack([oct_.rig.ibm[oct_.bone[n_]] for n_ in names_m]))
        cm = {oct_.bone[n_]: i_ for i_, n_ in enumerate(names_m)}

        def carry(wd_, p_):
            M_ = sum(w_ * Mm[:, cm[k_]] for k_, w_ in wd_.items())
            return np.einsum('tij,j->ti', M_[:, :3, :3], p_) + M_[:, :3, 3]
    from_ref = lambda wd_, q_: (np.linalg.inv(Mw(wd_)) @ np.append(q_, 1.0))[:3]
    r_top = lambda s_: float(np.linalg.norm(arm_top(oct_, j, [s_])[0][0] - arm_top(oct_, j, [s_])[3][0]))
    arch_bend = float(np.random.default_rng(6151 * int(seed or 0) + 41).uniform(*ARCH_BEND))
    excess_of = lambda k_: ARCH_K * (r_top(js[k_]) + r) * math.radians(max(pitch[k_], arch_bend if k_ == ARCH_JOINT else 0.0))
    for si in range(len(clamps) - 1):
        ca, cb = clamps[si], clamps[si + 1]
        # the joints under the span and their concave bends in the reference pose: a SHORT span over a bend arches from
        # pad to pad, a long one lies on the skin with a HUMP over each bend (its slack the bend's: the arm's top over
        # the joint is (r_top + r) x the bend shorter than the hose laid straight along it, ARCH_K of it); a span with
        # no bend of THETA_MIN lies flat (the S_SPAN with its S-turn)
        ks = [k_ for k_ in range(1, CO.N_JOINTS - 1) if ca['s'] < js[k_] < cb['s']]
        bends = {k_: float(pitch[k_]) for k_ in ks}
        conc = [k_ for k_ in ks if pitch[k_] >= THETA_MIN or k_ == ARCH_JOINT]
        d_ref = float(np.linalg.norm(face_b[si] - face_a[si]))
        pa_b, pb_b = from_ref(ca['w'], face_a[si]), from_ref(cb['w'], face_b[si])
        d_max = d_ref
        if carry is not None:
            d_max = max(d_ref, float(np.linalg.norm(carry(cb['w'], pb_b) - carry(ca['w'], pa_b), axis=1).max()))
        ex = sum(excess_of(k_) for k_ in conc)
        if si != S_SPAN and conc and d_ref < SHORT_SPAN:
            spans.append(dict(i=si, a=ca['k'], b=cb['k'], kind='arch', joints=conc, bends=bends, d_ref=d_ref,
                              d_max=d_max, excess=ex, L_inst=d_ref + ex))
        else:
            spans.append(dict(i=si, a=ca['k'], b=cb['k'], kind='lie', joints=conc if si != S_SPAN else [], bends=bends,
                              d_ref=d_ref, d_max=d_max, excess=ex if si != S_SPAN else 0.0))
    # ---------------------------------------------------------------- the lying runs and their humps (reference pose)
    # the lying parts: the body's (from DESCEND_N r to clamp 1's ramp) and each lying span's (between its ramps)
    i0 = int(np.searchsorted(sl_, DESCEND_N * r))
    # (Stage 3: ride 0 ends RAMP_BACK r before clamp 1's ramp: on the rest pose's tent the arm's top creases at joint 1,
    # just where the ramp began, and a run held down in the crease turned 18 deg in three rings; the ramp now bridges it)
    runs = [('ride0', i0, int(np.searchsorted(sl_, sl_[clamps[0]['i']] - 0.5 * L_pad - n_ramp - RAMP_BACK * r)))]
    for sp in spans:
        if sp['kind'] == 'lie':
            a_ = int(np.searchsorted(sl_, sl_[clamps[sp['i']]['i']] + 0.5 * L_pad + n_ramp))
            b_ = int(np.searchsorted(sl_, sl_[clamps[sp['i'] + 1]['i']] - 0.5 * L_pad - n_ramp))
            runs.append((f'ride{sp["i"] + 1}', a_, b_))
    fit_ref = lie_ref
    humps = {}                                                           # run name -> [(a, b, k, excess)]
    for sp in spans:
        if sp['kind'] != 'lie' or not sp['joints']:
            continue
        nm_ = f'ride{sp["i"] + 1}'
        a_r, b_r = [(a_, b_) for n_, a_, b_ in runs if n_ == nm_][0]
        # (Stage 4: on the rest pose's tent every seed bends joint 3 by the same 3.9 deg, so its hump was one shape on
        # all 16 seeds: its width and its slack are now seeded, the slack never under the bend's own (C5c: "a different
        # size per span and per seed, never a festoon"), the width at least HUMP_W, its feet no nearer the joint)
        rng_j = np.random.default_rng(6151 * int(seed or 0) + 53 + 7 * sp['i'])
        for k_ in sp['joints']:
            w_j, f_j = rng_j.uniform(*HUMP_WS), rng_j.uniform(*HUMP_SLACK)
            ic = n_rt - 1 + int(np.argmin(np.abs(s_arm - js[k_])))
            ha = int(np.searchsorted(sl_, sl_[ic] - 0.5 * w_j * r))
            hb = int(np.searchsorted(sl_, sl_[ic] + 0.5 * w_j * r))
            ha, hb = max(ha, a_r + 3), min(hb, b_r - 3)
            if hb - ha < 6:
                continue
            humps.setdefault(nm_, []).append((ha, hb, k_, excess_of(k_) * f_j))
            log(f'[hose] seed {seed}: the hump at joint {k_}: {w_j:.2f} r wide, slack x{f_j:.2f} the bend\'s '
                f'({excess_of(k_) * f_j * 1e3:.2f} mm)')
        sp['humps'] = [dict(joint=k_, s=float(js[k_]), excess=e_, base=float(sl_[hb_] - sl_[ha_]))
                       for ha_, hb_, k_, e_ in humps.get(nm_, [])]
    # C5d (the lead's call 3): the long run's small LIFTS: free humps at seeded places (their bases clear of each
    # other, of the bends' humps and of the ramps), seeded widths and slack (bows of 1-2.5 mm): the runtime bows them
    # (Stage 4: on the rest pose's tent every seed has the same hump at joint 3, at the run's start, and a lift drawn in
    # 0.2-0.8 of the run, refused within 3 r of it or of the run's ends, found room on 1 seed of 16 (8 before the tent).
    # Its centre is now drawn over the FREE places only: the run less LIFT_GAP r at its ends and round every hump, less
    # half its width. And its slack keeps its seeded share over its feet's chord in EVERY frame of the motion (the rest
    # motion and the swim): the most that chord grows past its rest length is added to it. A lift the swim pulled
    # nearly taut lay flat and its last rings met the skin: the official hoses on the tent, seed 15's hump100 -0.069 mm
    # at its last ring (gate 7), r3's seed 1 hump101 +0.021 mm, taut 99.6 %)
    # (Stage 4, h1's c05c: lifts placed so, all in the long run's free end, failed the swim on 5 of 8 seeds, each at its
    # LAST ring (-0.002 .. -0.035 mm): their far feet sat within a few millimetres of joint 4, whose bending lifts the
    # skin under them. So a lift's feet keep LIFT_JOINT r off every joint)
    # (Stage 4, h2's c05c: lifts so placed all found room only on the S-turn's run, and failed gate 9 on 7 of 8 seeds at
    # the last lying ring before them (bends 6.1-7.3 mm in the swim, turns 8-10 deg per step), seed 6's first free ring
    # 0.038 mm into the skin: a free lift's ends on a straight run are where the motion kinks or dips the hose. The hump
    # over joint 3 never failed, on any seed of either run: its feet stand 3.5-4 r either side of its joint and the bend
    # happens under it. So the first lift is a SERVICE LOOP centred on joint LOOP_JOINT of the long run, its feet LOOP_W
    # r apart round it, its centre within LOOP_SHIFT r (the place draw), its slack the seeded share plus its feet's chord
    # growth over the motion; further lifts take only the long run's free places, as before the tent)
    lift_spans = [i_ for i_ in (MEANDER_SPAN,) if spans[i_]['kind'] == 'lie']
    if lift_spans:
        rng_l = np.random.default_rng(6151 * int(seed or 0) + 37)
        rng_o = np.random.default_rng(6151 * int(seed or 0) + 61)
        joint_sl = [float(sl_[n_rt - 1 + int(np.argmin(np.abs(s_arm - js[k_])))]) for k_ in range(1, CO.N_JOINTS - 1)
                    if s_arm[0] <= js[k_] <= s_arm[-1]]
        taken = {f'ride{i_ + 1}': [(sl_[ha_], sl_[hb_]) for ha_, hb_, _, _ in humps.get(f'ride{i_ + 1}', [])]
                 for i_ in lift_spans}

        def chord_growth(ha_, hb_):
            """the most its feet (the lying run's points, skinned by their weights) come apart over the motion past
            their rest distance (m; 0 without a motion)"""
            if carry is None:
                return 0.0
            pa_, pb_ = from_ref(W_of[ha_], fit_ref[ha_]), from_ref(W_of[hb_], fit_ref[hb_])
            d_ = np.linalg.norm(carry(W_of[hb_], pb_) - carry(W_of[ha_], pa_), axis=1)
            return max(0.0, float(d_.max()) - float(np.linalg.norm(fit_ref[hb_] - fit_ref[ha_])))
        n_l = int(rng_l.integers(LIFT_N[0], LIFT_N[1]))
        for q_l in range(n_l):
            w_l = rng_l.uniform(*LIFT_W) * r
            u_l = rng_l.uniform(0.0, 1.0)
            e_l = rng_l.uniform(*LIFT_EX)
            if q_l == 0:
                # the service loop over joint LOOP_JOINT (h3): the long run's, its centre the joint's place on the run
                # shifted by the place draw, its feet clear of the run's ends (3 rings) and of the other humps (LIFT_GAP)
                nm_ = f'ride{MEANDER_SPAN + 1}'
                a_r, b_r = [(a_, b_) for n_, a_, b_ in runs if n_ == nm_][0]
                w_o = rng_o.uniform(*LOOP_W) * r
                s_j = float(sl_[n_rt - 1 + int(np.argmin(np.abs(s_arm - js[LOOP_JOINT])))])
                c_l = s_j + (2.0 * u_l - 1.0) * LOOP_SHIFT * r
                s0_, s1_ = c_l - 0.5 * w_o, c_l + 0.5 * w_o
                ha, hb = int(np.searchsorted(sl_, s0_)), int(np.searchsorted(sl_, s1_))
                ha, hb = max(ha, a_r + 3), min(hb, b_r - 3)
                clash = any(sl_[ha] < t1 + LIFT_GAP * r and t0 - LIFT_GAP * r < sl_[hb] for t0, t1 in taken[nm_])
                if hb - ha < 6 or clash:
                    log(f'[hose] seed {seed}: lift 1 of {n_l}, the loop over joint {LOOP_JOINT} ({w_o / r:.1f} r wide): '
                        f'no room on {nm_}')
                    continue
                g_ = chord_growth(ha, hb)
                log(f'[hose] seed {seed}: lift 1 of {n_l}: the loop over joint {LOOP_JOINT}, {w_o / r:.2f} r wide '
                    f'({(sl_[hb] - sl_[ha]) * 1e3:.1f} mm as clipped), centred {(c_l - s_j) * 1e3:+.1f} mm off the joint, at '
                    f'{(c_l - sl_[a_r]) * 1e3:.1f} mm of its {(sl_[b_r] - sl_[a_r]) * 1e3:.1f} on {nm_}, slack {e_l * 1e3:.2f} '
                    f'mm + {LOOP_GROWTH:g} x its chord\'s growth over the motion {g_ * 1e3:.2f} mm')
                humps.setdefault(nm_, []).append((ha, hb, 100, e_l + LOOP_GROWTH * g_))
                taken[nm_].append((sl_[ha], sl_[hb]))
                continue
            gap_ = LIFT_GAP * r + 0.5 * w_l
            gj_ = LIFT_JOINT * r
            free = []
            for i_ in lift_spans:
                nm_ = f'ride{i_ + 1}'
                a_r, b_r = [(a_, b_) for n_, a_, b_ in runs if n_ == nm_][0]
                fr_ = [(sl_[a_r] + gap_, sl_[b_r] - gap_)]
                # (its centre's forbidden places: within gap_ of a hump, or a foot within gj_ of a joint)
                cut = [(t0 - gap_, t1 + gap_) for t0, t1 in taken[nm_]]
                cut += [(s_j - gj_ + sg_ * 0.5 * w_l, s_j + gj_ + sg_ * 0.5 * w_l) for s_j in joint_sl for sg_ in (1, -1)]
                for c0, c1 in cut:
                    fr_ = [iv for f0, f1 in fr_ for iv in ((f0, min(f1, c0)), (max(f0, c1), f1))]
                free += [(f0, f1, nm_, a_r, b_r) for f0, f1 in fr_ if f1 > f0]
            room = sum(f1 - f0 for f0, f1, *_ in free)
            if room <= 0.0:
                log(f'[hose] seed {seed}: lift {q_l + 1} of {n_l} ({w_l / r:.1f} r wide): no room left on the runs')
                continue
            x_ = u_l * room
            c_l, nm_, a_r, b_r = free[-1][1], *free[-1][2:]
            for f0, f1, n2_, a2_, b2_ in free:
                if x_ <= f1 - f0:
                    c_l, nm_, a_r, b_r = f0 + x_, n2_, a2_, b2_
                    break
                x_ -= f1 - f0
            s0_, s1_ = c_l - 0.5 * w_l, c_l + 0.5 * w_l
            ha, hb = int(np.searchsorted(sl_, s0_)), int(np.searchsorted(sl_, s1_))
            g_ = chord_growth(ha, hb)
            log(f'[hose] seed {seed}: lift {q_l + 1} of {n_l}: {w_l / r:.1f} r wide on {nm_} at {(c_l - sl_[a_r]) * 1e3:.1f} '
                f'mm of its {(sl_[b_r] - sl_[a_r]) * 1e3:.1f} (room {room * 1e3:.1f} mm on the runs), slack {e_l * 1e3:.2f} '
                f'mm + its chord\'s growth over the motion {g_ * 1e3:.2f} mm')
            e_l += g_
            humps.setdefault(nm_, []).append((ha, hb, 100 + q_l, e_l))
            taken[nm_].append((s0_, s1_))
        for i_ in lift_spans:
            nm_ = f'ride{i_ + 1}'
            humps.get(nm_, []).sort()
            spans[i_]['humps'] = [dict(joint=k_, s=float(js[k_]) if k_ < 100 else float(sl_[(ha_ + hb_) // 2]),
                                       excess=e_, base=float(sl_[hb_] - sl_[ha_]), lift=k_ >= 100)
                                  for ha_, hb_, k_, e_ in humps.get(nm_, [])]
    # ---------------------------------------------------------------- the centreline pieces (reference pose)
    pieces = []                                                          # (name, points (ref), weight rule)

    def lying(nm_, a_, b_):
        """a lying run's pieces: the run on the skin, with a HUMP over each bend in it: from its foot to its foot, a
        hermite along the run's tangents bowed up (h sin^2) along the skin's normal there by the slack it carries (its
        length the run's between the feet + the bend's excess), skinned across its two feet's weights"""
        out, at = [], a_
        hs_ = sorted(humps.get(nm_, []))
        for q_, (ha, hb, k_, e_) in enumerate(hs_):
            out.append((f'{nm_}.{q_}', fit_ref[at:ha + 1], ('lie', at)))
            ta = fit_ref[ha + 1] - fit_ref[ha - 1]
            tb = fit_ref[hb + 1] - fit_ref[hb - 1]
            ta, tb = ta / np.linalg.norm(ta), tb / np.linalg.norm(tb)
            up = N_ref[(ha + hb) // 2]
            L_need = float(np.linalg.norm(np.diff(fit_ref[ha:hb + 1], axis=0), axis=1).sum()) + e_
            lo_, hi_ = 0.0, 0.05
            for _ in range(40):
                mid = 0.5 * (lo_ + hi_)
                if _arclen(hermite(fit_ref[ha], ta, fit_ref[hb], tb, 64, up, mid)) < L_need:
                    lo_ = mid
                else:
                    hi_ = mid
            Hm = hermite(fit_ref[ha], ta, fit_ref[hb], tb, 64, up, hi_)
            for h_ in (spans):
                for hd in h_.get('humps', []):
                    if hd['joint'] == k_:
                        hd.update(bow=hi_, L=_arclen(Hm))
            out.append((f'hump{k_}', Hm, ('blend', W_of[ha], W_of[hb])))
            at = hb
        out.append((f'{nm_}.{len(hs_)}' if hs_ else nm_, fit_ref[at:b_ + 1], ('lie', at)))
        return out
    # the fitting's run inside its ferrule and the descent onto the skin
    run0 = np.array([to_plate(E_a - 0.6 * r * d0_a + t_ * 1.55 * r * d0_a) for t_ in np.linspace(0.0, 1.0, 5)])
    run0_ref = np.array([to_ref(fitw, q_) for q_ in run0])
    t_A0 = rot_ref(fitw, R_f @ d0_a)
    p_d1 = fit_ref[i0]
    t_d1 = fit_ref[min(i0 + 2, len(fit_ref) - 1)] - fit_ref[max(i0 - 2, 0)]
    t_d1 /= np.linalg.norm(t_d1)
    # the descent: a hermite from the ferrule's mouth (its 45 deg lean) to the lying run, kept off the skin by a clearance
    # easing from the mouth's own height to lying (keep_off holds both ends)
    D_ = hermite(run0_ref[-1], t_A0, p_d1, t_d1, 40)
    h_m = ref_height(D_[[0, -1]])
    clr_D = eased_clear(D_, float(h_m[0]), float(h_m[1]))
    D_ = limit_bends(keep_off_ref(D_, clr_D), lambda Q_: keep_off_ref(Q_, clr_D), BEND_DESCENT, hold=2)
    pieces.append(('fit', run0_ref, ('fixed', fitw)))
    pieces.append(('descend', D_, ('blend', fitw, W_of[i0])))
    pieces += lying('ride0', runs[0][1], runs[0][2])
    run_of = {nm_: (a_, b_) for nm_, a_, b_ in runs}

    def ramp(p_a, t_a, p_b, t_b, n=24, rising=True, bridge=False):
        """a ramp between a lying point and a pad's face (or back down): a hermite kept off the skin, its clearance
        eased from the one end's own height to the other's (lying, the pad's cradle), then relaxed where it bends
        tighter than BEND_STILL, as the descent is. (Stage 3: on the rest pose's tent the hermite into pad 1 cuts the
        skin's shoulder; keep_off's 0.49 mm push, its ends held, went into the ramp's first five steps: a 4.3 mm bend)
        bridge (clamp 1's ramp, RAMP_BACK): the clearance only the lower end's height, not the eased climb to the pad's:
        over the crease that line pushed the ramp's tail straight along the pad's axis, a corner 3 rings before the face"""
        R_ = hermite(p_a, t_a, p_b, t_b, n)
        h_ = ref_height(R_[[0, -1]])
        clr_ = eased_clear(R_, float(h_[0]), float(h_[1]))
        if bridge:
            clr_ = np.minimum(clr_, float(h_.min()) - 0.05e-3)
        return limit_bends(keep_off_ref(R_, clr_), lambda Q_: keep_off_ref(Q_, clr_), BEND_STILL, hold=2)
    for ci, cl in enumerate(clamps):
        # into the pad: from the lying run's end (the previous ride, or the previous clamp's arch / ramp) to its face
        x_ax = cl['R'][:, 0]
        ent, ext = cl['faces']
        if ci == 0 or spans[ci - 1]['kind'] == 'lie':
            nm_prev = 'ride0' if ci == 0 else f'ride{ci}'
            a_, b_ = run_of[nm_prev]
            p_a = fit_ref[b_]
            t_a = fit_ref[b_] - fit_ref[b_ - 2]
            t_a /= np.linalg.norm(t_a)
            pieces.append((f'ramp{cl["k"]}a', ramp(p_a, t_a, ent, x_ax, bridge=ci == 0), ('blend', W_of[b_], cl['w'])))
        pieces.append((f'clamp{cl["k"]}', np.array([ent + t_ * (ext - ent) for t_ in np.linspace(0.0, 1.0, 5)]),
                       ('fixed', cl['w'])))
        if ci == len(clamps) - 1:
            break
        sp = spans[ci]
        nx = clamps[ci + 1]
        if sp['kind'] == 'lie':
            a_, b_ = run_of[f'ride{ci + 1}']
            p_b = fit_ref[a_]
            t_b = fit_ref[a_ + 2] - fit_ref[a_]
            t_b /= np.linalg.norm(t_b)
            pieces.append((f'ramp{cl["k"]}b', ramp(ext, x_ax, p_b, t_b, rising=False), ('blend', cl['w'], W_of[a_])))
            pieces += lying(f'ride{ci + 1}', a_, b_)
        else:
            # the ARCH: from this pad's exit face to the next's entry face, its bow (h sin^2) giving the installed
            # length, up along the two pads' mean up axis
            pa, pb = ext, nx['faces'][0]
            ta, tb = x_ax, nx['R'][:, 0]
            up = cl['R'][:, 1] + nx['R'][:, 1]
            up /= np.linalg.norm(up)
            lo_, hi_ = 0.0, 0.05
            for _ in range(40):
                mid = 0.5 * (lo_ + hi_)
                if _arclen(hermite(pa, ta, pb, tb, 96, up, mid)) < sp['L_inst']:
                    lo_ = mid
                else:
                    hi_ = mid
            A_ = hermite(pa, ta, pb, tb, 96, up, hi_)
            sp.update(bow=hi_, L=_arclen(A_))
            pieces.append((f'arch{cl["k"]}', A_, ('blend', cl['w'], nx['w'])))
    # the last span: the RISE from clamp 4 over joint 7 and the soft roll into the inlet port (C5b's port)
    P7, C7 = P[CO.J0], C[CO.J0]
    to7 = lambda q: P7 + np.asarray(q) @ C7.T
    d0_p = np.asarray(I['d0'])                  # the port is the tentacle's own fitting (its ferrule at 45 deg), mirrored
    d_back = np.array([-d0_p[0], d0_p[1], 0.0])
    Rx_ = lambda a_: np.array([[1.0, 0.0, 0.0], [0.0, math.cos(a_), -math.sin(a_)], [0.0, math.sin(a_), math.cos(a_)]])
    R_p = max((Rx_(math.radians(sg_ * PORT_PHI)) for sg_ in (-1.0, 1.0)),
              key=lambda R__: side_x * (C7 @ (R__ @ np.array([0.0, 1.0, 0.0])))[0])
    mir_ = lambda q: np.column_stack([2.0 * xf - np.atleast_2d(q)[:, 0], np.atleast_2d(q)[:, 1:]])
    move_ = lambda q: (np.atleast_2d(q) + np.array([PORT_DX, 0.0, 0.0])) @ R_p.T
    port = place(place(fitting, np.eye(3), np.zeros(3), mirror_x=xf), R_p, R_p @ np.array([PORT_DX, 0.0, 0.0]))
    coll = [it_ for it_ in isl if it_['region'] == 'collar']
    cF = np.concatenate([mech.F[it_['f'][0]:it_['f'][1]] for it_ in coll])
    cA, cB, cC = (mech.V[cF[:, i_]] for i_ in range(3))
    boss_v = np.concatenate([np.full(it_['v'][1] - it_['v'][0], 'ferrule' not in it_['piece'])
                             for it_ in isl if it_['region'] == 'fitting'])
    ob_v = np.concatenate([np.arange(*it_['v']) for it_ in isl if it_['region'] == 'fitting'
                           and 'ferrule' not in it_['piece']])
    seat0 = float(CO.point_tri_near(mech.V[ob_v], cA, cB, cC, k=12)[0].min())
    seat_p = float(CO.point_tri_near(port['V'][boss_v], cA, cB, cC, k=12)[0].min())
    n_p = R_p @ np.array([0.0, 1.0, 0.0])
    port = place(port, np.eye(3), -(seat_p - seat0) * n_p)
    E_port = move_(mir_(E_a))[0] - (seat_p - seat0) * n_p
    flange_fit = place(port, C7, P7)
    d0_m = R_p @ d_back
    w7 = {bone(CO.J0): 1.0}
    c4 = clamps[-1]
    exit_flange = to7(E_port + 0.95 * r * d0_m)
    pa, pb = c4['faces'][1], to_ref(w7, exit_flange)
    ta, tb = c4['R'][:, 0], -rot_ref(w7, C7 @ d0_m)
    up = c4['R'][:, 1] + rot_ref(w7, C7[:, 1])
    up /= np.linalg.norm(up)
    d_ref4 = float(np.linalg.norm(pb - pa))
    d_max4 = d_ref4
    if carry is not None:
        d_max4 = max(d_ref4, float(np.linalg.norm(carry(w7, exit_flange) - carry(c4['w'], from_ref(c4['w'], pa)),
                                                  axis=1).max()))
    need4 = (1.0 + SLACK) * d_max4
    # what the rise must clear: the flange's pieces (rigid on bone 7, posed into the reference pose) and the skin
    fl_f = np.concatenate([mech.F[it_['f'][0]:it_['f'][1]] for it_ in isl
                           if it_['region'] in ('roll', 'collar', 'collar_end', 'screw', 'band', 'boss', 'fitting')])
    M7r = Mw(w7)
    Vfl = to7(mech.V) @ M7r[:3, :3].T + M7r[:3, 3]
    tree4 = cKDTree(hermite(pa, ta, pb, tb, 96))
    # (the arm's skin past the cut ring left out: the runtime hides it under the flange, and kept off it the rise kinked
    # beside the port, c05c seeds 2-3)
    near4 = tree4.query(Vref[F].mean(1), distance_upper_bound=0.04)[0] < np.inf
    near4[CO.cut_arm(oct_, j)['distal']] = False
    sk4 = F[near4]
    A4s = np.concatenate([Vfl[fl_f[:, 0]], Vref[sk4[:, 0]]])
    B4s = np.concatenate([Vfl[fl_f[:, 1]], Vref[sk4[:, 1]]])
    C4s = np.concatenate([Vfl[fl_f[:, 2]], Vref[sk4[:, 2]]])
    # the rise: the hermite with a bow (its end tangent the ferrule's axis), then LIFTED over the flange: in chord 7's
    # frame (rigid on bone 7) every point standing nearer the flange's pieces than r + RISE_CLEAR (the exact distance to
    # their triangles, posed) pushed straight out from the arm's axis by what it lacks, spread into a gentle swell, and
    # kept off the skin, then relaxed where it bends tighter than BEND_STILL (its first and last three points held: the
    # pad's axis, the ferrule's), a few rounds. The hermite alone ran back along the ferrule's axis, which passes the
    # soft roll closer than r, 2.5 mm into it; a push along the nearest face's normal kinked it at the port (a 3 mm
    # bend); a radial test on the flange's binned envelope read the roll's crest beside its end faces (a 2 mm need where
    # C5b's rise cleared by 0.25); C5b's rise swept round the arm over the roll and dove into the ferrule along bends of
    # 12 mm (c05c p12)
    FAf, FBf, FCf = Vfl[fl_f[:, 0]], Vfl[fl_f[:, 1]], Vfl[fl_f[:, 2]]
    tree_f = cKDTree((FAf + FBf + FCf) / 3.0)
    lack = lambda Q_: np.maximum(r + RISE_CLEAR - CO.point_tri_near(Q_, FAf, FBf, FCf, k=32, tree=tree_f)[0], 0.0)
    M7i = np.linalg.inv(M7r)
    to_asset = lambda Q_: ((np.asarray(Q_) @ M7i[:3, :3].T + M7i[:3, 3]) - P7) @ C7
    from_asset = lambda q_: to7(q_) @ M7r[:3, :3].T + M7r[:3, 3]
    # the bow's height and the place of its crest chosen first: the lowest bow (from the slack's least) whose curve
    # stands RISE_CLEAR off the flange by itself (within 0.05 mm, the dive into the port's mouth apart) and bends no
    # tighter than BEND_STILL with the pad's run before it and the ferrule's after it; the lift below then only trims (a
    # curve drawn low and lifted over the roll after kinked where the lift ended at the port, c05c seeds 2-4)
    ext_a = np.array([pa - ta * 1.0e-3, pa - ta * 0.5e-3])
    ext_b = np.array([pb + tb * 0.5e-3, pb + tb * 1.0e-3])
    # (and off the skin by its eased clearance, judged on the drawn curve too: a push off the skin afterwards bent the
    # rise's last millimetres to 1.7 mm, c05c seeds 2 and 7)
    h_a = float(ref_height(pa[None])[0])
    clr_sk = np.minimum(r + RISE_CLEAR, h_a + (r + RISE_CLEAR - h_a) * np.array(
        [_ease(min(x_ / 0.25, 1.0)) for x_ in np.linspace(0.0, 1.0, 120)]))
    skA, skB, skC = Vref[sk4[:, 0]], Vref[sk4[:, 1]], Vref[sk4[:, 2]]
    tree_s = cKDTree((skA + skB + skC) / 3.0)
    sk_lack_of = lambda Q_: clr_sk - CO.point_tri_near(Q_, skA, skB, skC, k=32, tree=tree_s)[0]
    cands = []
    for bp in (1.0, 1.6, 2.4):
        for h_ in np.arange(0.0, 8.01e-3, 0.25e-3):
            Q_ = hermite(pa, ta, pb, tb, 120, up, h_, bp=bp)
            if _arclen(Q_) < need4:
                continue
            uq_ = np.linspace(0.0, 1.0, len(Q_))
            ok_u = (uq_ > 0.10) & (uq_ < 0.92)                 # the dive into the port's mouth apart (see keep4)
            need_ = float(max(lack(Q_[ok_u]).max(), sk_lack_of(Q_)[3:-3].max()))
            bend_ = float(_bend_radius(np.vstack([ext_a, Q_, ext_b]))[0].min())
            cands.append(((need_ <= 0.05e-3) and (bend_ >= BEND_STILL), -h_ if need_ <= 0.05e-3 else -need_, bp, h_,
                          Q_, need_, bend_))
            if need_ <= 0.05e-3:
                break
    _, _, bp_r, hi_, A4, need_r, bend_r = max(cands, key=lambda c_: (c_[0], c_[1]))
    log(f'[hose] seed {seed}: the rise\'s bow {hi_ * 1e3:.2f} mm, crest power {bp_r}: the lift it still needs over the '
        f'flange {need_r * 1e3:+.3f} mm, its tightest bend {bend_r * 1e3:.1f} mm; per crest power, the least need: ' +
        ', '.join(f'{bp}: ' + min((f'{c_[5] * 1e3:+.2f} at {c_[3] * 1e3:.2f} (bend {c_[6] * 1e3:.1f})' for c_ in cands
                                  if c_[2] == bp), key=lambda t_: float(t_.split(' ')[0])) for bp in (1.0, 1.6, 2.4)))
    g4 = np.exp(-0.5 * (np.arange(-8, 9) / 3.0) ** 2)
    g4 /= g4.sum()

    def keep4(Q_):
        q_ = to_asset(Q_)
        lift = lack(Q_)
        # the lift spread into a gentle swell (a cone of slope 0.3 over each point's need, then a Gaussian of three
        # points, never under the need): the roll's proximal face is steep, and a lift that started at one point
        # kinked the rise there (a 2.4 mm bend, c05c)
        s4 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q_, axis=0), axis=1))])
        sw_ = (lift[None, :] - 0.3 * np.abs(s4[:, None] - s4[None, :])).max(1)
        sw_ = np.convolve(np.pad(sw_, 8, mode='edge'), g4, mode='valid')
        u_ = s4 / s4[-1]
        # (eased off over the first 15 % and the last 8 %: the pad's run at one end, and at the other the dive into the
        # port, whose mouth sits on the collar: held to the clearance there the rise folded over itself, c05c)
        taper = np.array([_ease(min(x_ / 0.15, 1.0)) * _ease(min((1.0 - x_) / 0.08, 1.0)) for x_ in u_])
        lift = np.maximum(lift, sw_) * taper
        lift[:3] = lift[-3:] = 0.0
        rho_ = np.hypot(q_[:, 1], q_[:, 2])
        q_[:, 1:] *= ((rho_ + lift) / np.maximum(rho_, 1e-9))[:, None]
        return from_asset(q_)

    def keep4s(Q_):
        """off the skin first (keep_off smooths as it pushes), then the lift over the flange last"""
        return keep4(keep_off(Q_, skA, skB, skC, clr_sk, hold=3))
    # (only where the chosen curve still lacks clearance: run on a curve that already stood clear, the rounds of
    # pushing and smoothing bent its last millimetres into the ferrule to 2.2 mm, c05c seeds 2 and 7)
    # (the push only where the drawn curve comes within 0.1 mm of the flange or the skin: short of RISE_CLEAR by 0.06
    # mm, seed 7's pushed rise bent to 1.7 mm)
    uA_ = np.linspace(0.0, 1.0, len(A4))
    if (lack(A4[(uA_ > 0.10) & (uA_ < 0.92)]).max() > RISE_CLEAR - 0.1e-3
            or sk_lack_of(A4)[3:-3].max() > RISE_CLEAR - 0.1e-3):
        A4 = limit_bends(keep4s(A4), keep4s, BEND_STILL, hold=3)
        for _ in range(4):
            A4 = keep4s(A4)
    rise_clear = CO.point_tri_near(A4, A4s, B4s, C4s, k=32)[0] - r
    spans.append(dict(i=len(clamps) - 1, a=c4['k'], b='port', kind='rise', d_ref=d_ref4, d_max=d_max4, L_inst=need4,
                      bow=hi_, crest_power=bp_r, L=_arclen(A4), clear_min=float(rise_clear[3:-3].min()),
                      bend_min=float(_bend_radius(A4)[0].min())))
    pieces.append(('rise', A4, ('blend', c4['w'], w7)))
    run_end = np.array([to7(E_port + t_ * r * d0_m) for t_ in np.linspace(0.95, -0.6, 5)])
    pieces.append(('flange', np.array([to_ref(w7, q_) for q_ in run_end]), ('fixed', w7)))
    # ---------------------------------------------------------------- the polyline (reference pose) and its weights
    Pc, Wj, span_of, ends_of = [], [], [], []
    for name, Q, rule in pieces:
        a_ = len(Pc)
        first = None
        for i_, q in enumerate(Q):
            if rule[0] == 'fixed':
                w_ = dict(rule[1])
            elif rule[0] == 'blend':
                w_ = blend(rule[1], rule[2], _ease(i_ / max(len(Q) - 1, 1)))
            else:
                w_ = W_of[rule[1] + i_]
            q = np.asarray(q, np.float64)
            if Pc and np.linalg.norm(q - Pc[-1]) < 1e-7:
                first = len(Pc) - 1 if first is None else first
                continue
            first = len(Pc) if first is None else first
            Pc.append(q)
            Wj.append(w_)
        span_of.append((name, a_, len(Pc)))
        ends_of.append((name, first, len(Pc) - 1))
    Pc = np.array(Pc)
    s_src = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pc, axis=0), axis=1))])
    # the rings: a ring at both faces of every hold and one 0.8 r outside each (the tube leaves a pad along its axis: its
    # first step samples that, not the ramp's or the arch's curve further on); between those knots each interval
    # resampled on its own (steps at most 1.6 r, turning at most 0.10 rad each)
    knots = sorted({float(s_src[i_]) for nm_, f_, l_ in ends_of if f_ is not None and
                    (nm_.startswith('clamp') or nm_ == 'flange') for i_ in (f_, l_)})
    out_k = [float(k_ + sg_ * 0.8 * r) for k_ in knots for sg_ in (-1.0, 1.0)]
    kn2 = np.unique(np.concatenate([[0.0, s_src[-1]], knots, [k_ for k_ in out_k if 0.0 < k_ < s_src[-1]]]))
    # C5f (the lead's call 5): every ARCH a convoluted section (BELLOWS): between the knots BELLOWS_END r off each pad's
    # face, whole convolutions of about BELLOWS['pitch'] r, its rings every quarter pitch (the plain ends at the same step)
    bel = []
    for nm_, f_, l_ in ends_of:
        if nm_.startswith('arch') and f_ is not None:
            sa_, sb_ = float(s_src[f_]), float(s_src[l_])
            ia_, ib_ = sa_ + BELLOWS_END * r, sb_ - BELLOWS_END * r
            n_cv = max(1, int(round((ib_ - ia_) / (BELLOWS['pitch'] * r))))
            bel.append(dict(piece=nm_, s0=sa_, s1=sb_, i0=ia_, i1=ib_, n=n_cv, pitch=(ib_ - ia_) / n_cv))
    sr_parts = [np.zeros(1)]
    for ka, kb in zip(kn2[:-1], kn2[1:]):
        if kb - ka < 1e-7:
            continue
        sub_s = np.unique(np.concatenate([[ka], s_src[(s_src > ka) & (s_src < kb)], [kb]]))
        sub_P = np.column_stack([np.interp(sub_s, s_src, Pc[:, k_]) for k_ in range(3)])
        bl_ = [b_ for b_ in bel if b_['s0'] - 1e-7 <= ka and kb <= b_['s1'] + 1e-7]
        _, ts_ = resample(sub_P, (0.25 * bl_[0]['pitch'] if bl_ else RING_STEP) * (1.0 + 1e-9), 0.10)
        sr_parts.append(np.interp(ts_, np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(sub_P, axis=0),
                                                                                         axis=1))]), sub_s - ka) + ka)
    sr2 = np.unique(np.concatenate(sr_parts))
    sr2 = sr2[np.concatenate([[True], np.diff(sr2) > 1e-7])]
    from scipy.interpolate import CubicSpline
    Pr = CubicSpline(s_src, Pc, axis=0)(sr2)
    # C5f: over each pad the tube ON THE PAD'S AXIS, or lifted off it, never dropped or shifted aside. The cradle is a
    # straight cylinder of radius r round c0 + t x (PAD L r long; the axis 0.4 % of r over its floor: ~17 um of play),
    # but the spline through the polyline already bends into the ramps on the pad's ends: there a ramp, still rising off
    # the skin, ran up to ~23 um under the axis and the tube's facets 3-6 um into the cradle's lip ahead of clamp 1 (C5e
    # too: c05c's hold check reads the ring vertices alone, +0.002 mm there in C5e, -0.000 once the even ring spacing,
    # the lead's call 7, put ring 251 on that lip). A ring over a pad keeps only its lift off the axis (an arch leaving)
    for cl in clamps:
        x_, y_ = cl['R'][:, 0], cl['R'][:, 1]
        d_ = Pr - cl['c']
        t_ = d_ @ x_
        off_ = d_ - t_[:, None] * x_
        over_ = (np.abs(t_) <= 0.5 * L_pad + 1e-9) & (np.linalg.norm(off_, axis=1) < r)
        Pr[over_] = cl['c'] + t_[over_, None] * x_ + np.maximum(off_[over_] @ y_, 0.0)[:, None] * y_
    kk = np.clip(np.searchsorted(s_src, sr2), 1, len(Pc) - 1)
    tt = np.clip((sr2 - s_src[kk - 1]) / np.maximum(s_src[kk] - s_src[kk - 1], 1e-12), 0.0, 1.0)
    W_ring = [blend(Wj[k_ - 1], Wj[k_], float(t_)) for k_, t_ in zip(kk, tt)]
    ring_pieces = {}
    for nm_, a_, b_ in span_of:
        if b_ > a_:
            in_ = np.nonzero((sr2 >= s_src[a_] - 1e-9) & (sr2 <= s_src[b_ - 1] + 1e-9))[0]
            if len(in_):
                ring_pieces[nm_] = [int(in_.min()), int(in_.max())]
    # the rings' WEIGHTS: every ring on the skin (the lying runs, the ramps, the clamps' runs, and a ring between two
    # pieces beside one of them) takes the skin's weights under its centre in the reference pose, smoothed along the hose
    # by a Gaussian of W_SIG r that eases to none over each ramp into a pad (so the hose in its cradle, the pad and the
    # strap take the skin's own there); the plate fitting's run and the port's keep theirs (fixed); every free piece
    # between (the descent, the arches, the humps, the rise) blends, eased, from the ring before it to the ring after it
    n_r = len(Pr)
    name_of = np.array([''] * n_r, dtype=object)
    for nm_, (a_, b_) in sorted(ring_pieces.items(), key=lambda kv: kv[1][0]):
        name_of[a_:b_ + 1] = nm_
    on_ = np.array([str(n_).startswith(('ride', 'ramp', 'clamp')) for n_ in name_of])
    gap_ = name_of == ''
    on_[1:-1] |= gap_[1:-1] & (on_[:-2] | on_[2:])
    # (and the descent's: on weights blended from the plate fitting's to the lying run's the breathing pressed its last
    # rings 0.11 mm into the skin and tilted its rings 4.4 deg off the tube where the blend turned, c05c)
    on_ |= name_of == 'descend'
    on_[1:-1] |= gap_[1:-1] & (on_[:-2] | on_[2:])
    fixed_ = np.array([str(n_) in ('fit', 'flange') for n_ in name_of])
    i_on = np.nonzero(on_)[0]
    _, _, Jn_, Wn_ = ref_feet(Pr[i_on])
    keys_ = sorted({int(a_) for row, wr in zip(Jn_, Wn_) for a_, w_ in zip(row, wr) if w_ > 0})
    kc_ = {k_: q for q, k_ in enumerate(keys_)}
    Wm_ = np.zeros((len(i_on), len(keys_)))
    for q, (row, wr) in enumerate(zip(Jn_, Wn_)):
        for a_, w_ in zip(row, wr):
            if w_ > 0:
                Wm_[q, kc_[int(a_)]] += w_
    s_cl = np.array([0.5 * (sr2[ring_pieces[f'clamp{cl["k"]}'][0]] + sr2[ring_pieces[f'clamp{cl["k"]}'][1]])
                     for cl in clamps])
    d_cl = np.abs(sr2[i_on][:, None] - s_cl[None, :]).min(1)
    # (only where the skin breathes, within 15 mm of a ring on the mantle's breathing bones: elsewhere the skin under
    # the hose holds still in the rest motion, and smoothed weights at the arm's root pressed it 1 mm further into the
    # skin at the bind, c05c)
    br_k = np.array([oct_.rig.jnames[k_].startswith(BREATHING) for k_ in keys_])
    br_r = Wm_[:, br_k].sum(1) > 0.02 if br_k.any() else np.zeros(len(i_on), bool)
    near_br = (np.abs(sr2[i_on][:, None] - sr2[i_on][br_r][None, :]) < 0.015).any(1) if br_r.any() else br_r
    sig_ = W_SIG * r * np.clip((d_cl - 0.5 * L_pad) / (n_ramp + r), 0.0, 1.0) * near_br
    chain_ = np.concatenate([[0], np.cumsum(np.diff(i_on) > 1)])
    W_new = [None] * n_r
    for c_ in np.unique(chain_):
        qs = np.nonzero(chain_ == c_)[0]
        ss = sr2[i_on[qs]]
        G = np.exp(-0.5 * ((ss[None, :] - ss[:, None]) / np.maximum(sig_[qs], 1e-6)[:, None]) ** 2)
        Ws_ = (G @ Wm_[qs]) / G.sum(1, keepdims=True)
        for q, row in zip(qs, Ws_):
            top = sorted(((keys_[k_], float(v_)) for k_, v_ in enumerate(row) if v_ > 1e-6), key=lambda kv: -kv[1])[:4]
            s_ = sum(v_ for _, v_ in top)
            W_new[i_on[q]] = {k_: v_ / s_ for k_, v_ in top}
    for i_ in np.nonzero(fixed_)[0]:
        W_new[i_] = dict(W_ring[i_])
    i_ = 0
    while i_ < n_r:
        if W_new[i_] is not None:
            i_ += 1
            continue
        j_ = i_
        while j_ < n_r and W_new[j_] is None:
            j_ += 1
        wa, sa = (W_new[i_ - 1], sr2[i_ - 1]) if i_ > 0 else (W_ring[i_], sr2[i_])
        wb, sb = (W_new[j_], sr2[j_]) if j_ < n_r else (W_ring[j_ - 1], sr2[j_ - 1])
        for q in range(i_, j_):
            W_new[q] = blend(wa, wb, _ease(min(max((sr2[q] - sa) / max(sb - sa, 1e-12), 0.0), 1.0)))
        i_ = j_
    W_ring = W_new
    T_, E1 = rmf(Pr, rot_ref(fitw, nrm))
    E2 = np.cross(T_, E1)
    ang = np.linspace(0.0, TAU, SIDES + 1)
    # C5f: each ring's radius (r; a bellows' rings r (1 - amp sin^2(pi u / pitch)), u from its first knot) and the
    # profile's slope, which tilts the sleeve's normals along the hose (n ~ radial - r'(s) t: the convolutions shade)
    r_ring, dr_ring = np.full(len(sr2), r), np.zeros(len(sr2))
    for b_ in bel:
        u_ = sr2 - b_['i0']
        m_ = (u_ >= -1e-9) & (sr2 <= b_['i1'] + 1e-9)
        ph_ = np.pi * u_[m_] / b_['pitch']
        r_ring[m_] = r * (1.0 - BELLOWS['amp'] * np.sin(ph_) ** 2)
        dr_ring[m_] = -r * BELLOWS['amp'] * (np.pi / b_['pitch']) * np.sin(2.0 * ph_)
        b_['rings'] = [int(np.nonzero(m_)[0].min()), int(np.nonzero(m_)[0].max())]
    rad_ = np.cos(ang)[None, :, None] * E1[:, None, :] + np.sin(ang)[None, :, None] * E2[:, None, :]
    Vt = Pr[:, None, :] + r_ring[:, None, None] * rad_
    Nt = (rad_ - dr_ring[:, None, None] * T_[:, None, :]) / np.sqrt(1.0 + dr_ring ** 2)[:, None, None]
    nr, nc = len(Pr), SIDES + 1
    Pb = 1.25 * TAU * r / CL.BRAID['carriers']
    L_tile = TILE_PERIODS * Pb
    UVt = np.stack([np.tile(np.linspace(0.0, 1.0, nc)[None, :], (nr, 1)), np.tile((sr2 / L_tile)[:, None], (1, nc))],
                   -1).reshape(-1, 2)
    Ft = []
    for a_ in range(nr - 1):
        for c_ in range(SIDES):
            p00, p01, p10, p11 = a_ * nc + c_, a_ * nc + c_ + 1, (a_ + 1) * nc + c_, (a_ + 1) * nc + c_ + 1
            Ft += [(p00, p10, p11), (p00, p11, p01)]
    Ft = np.array(Ft, np.int64)
    Vt = Vt.reshape(-1, 3)
    Nt = Nt.reshape(-1, 3)
    fn = np.cross(Vt[Ft[:, 1]] - Vt[Ft[:, 0]], Vt[Ft[:, 2]] - Vt[Ft[:, 0]])
    if (np.einsum('ij,ij->i', fn, Nt[Ft[:, 0]]) < 0).mean() > 0.5:
        Ft = Ft[:, ::-1].copy()
    # ---------------------------------------------------------------- the hardware's weights (reference pose)
    # the pads: each vertex the skin's weights under it; the straps and rivets: their clamp's rings' (along its axis), so
    # the pad rides the skin and the strap holds the hose
    pad_W, hw_W = [], {}
    for cl in clamps:
        X_, _, Jp, Wp = ref_feet(cl['pad']['V'])
        pad_W.append([wdict(Jp[i_], Wp[i_]) for i_ in range(len(X_))])
        ra_, rb_ = ring_pieces[f'clamp{cl["k"]}']
        xr_ = (Pr[ra_:rb_ + 1] - cl['c']) @ cl['R'][:, 0]

        def w_at(v_, ra_=ra_, xr_=xr_, cl=cl):
            x_ = float((v_ - cl['c']) @ cl['R'][:, 0])
            q = int(np.clip(np.searchsorted(xr_, x_) - 1, 0, len(xr_) - 2))
            t_ = float(np.clip((x_ - xr_[q]) / max(xr_[q + 1] - xr_[q], 1e-12), 0.0, 1.0))
            return blend(W_ring[ra_ + q], W_ring[ra_ + q + 1], t_)
        for nm_, prt in [(f'strap {cl["k"]}', cl['strap'])] + [(f'rivet {cl["k"]}.{q_}', rv)
                                                                  for q_, rv in enumerate(cl['rivets'])]:
            hw_W[nm_] = [w_at(v_) for v_ in prt['V']]
    Wv = [[W_ring[i_]] * nc for i_ in range(nr)]
    used = sorted({k_ for w_ in W_ring for k_ in w_} | {k_ for cl in clamps for k_ in cl['w']} | {bone(CO.J0)}
                  | set(fitw) | {k_ for pw in pad_W for w_ in pw for k_ in w_}
                  | {k_ for wl in hw_W.values() for w_ in wl for k_ in w_})
    jn = [oct_.rig.jnames[k_] for k_ in used]
    col = {k_: i_ for i_, k_ in enumerate(used)}

    def pack(wd_):
        items = sorted(wd_.items(), key=lambda kv: -kv[1])[:4]
        J4 = [col[k_] for k_, _ in items] + [col[items[0][0]]] * (4 - len(items))
        W4 = [v_ for _, v_ in items] + [0.0] * (4 - len(items))
        s_ = sum(W4)
        return J4, [w_ / s_ for w_ in W4]

    def back_to_bind(V_, N_, packs):
        """reference-pose vertices back to the bind, each by the inverse of the skin matrix its packed weights make in
        the reference pose (its normal by that matrix's linear part's inverse)"""
        Vb_, Nb_ = V_.copy(), N_.copy()
        for i_, (J4, W4) in enumerate(packs):
            Mr = sum(w_ * Msk[used[c_]] for c_, w_ in zip(J4, W4) if w_ > 0.0)
            Mi = np.linalg.inv(Mr)
            Vb_[i_] = Mi[:3, :3] @ V_[i_] + Mi[:3, 3]
            n_ = Mi[:3, :3] @ N_[i_]
            Nb_[i_] = n_ / np.linalg.norm(n_)
        return Vb_, Nb_
    JWv = [pack(Wv[i_][k_]) for i_ in range(nr) for k_ in range(nc)]
    Vt, Nt = back_to_bind(Vt, Nt, JWv)
    from . import bake as BK
    _, TANt = BK.low_frames(Vt, Ft, UVt, Nt)
    Jt = np.array([a_ for a_, _ in JWv], np.int64)
    Wt_ = np.array([b_ for _, b_ in JWv], np.float64)
    # the tentacle's set: the plate fitting (bind, on the skin's weights at its site) and the port (rigid on bone 7)
    hard = []
    for nm_, part, wd in (('plate fitting', plate_fit, fitw), ('flange port', flange_fit, w7)):
        J4, W4 = pack(wd)
        hard.append(dict(part, name=nm_, J=np.tile(J4, (len(part['V']), 1)), W=np.tile(W4, (len(part['V']), 1))))
    cat = lambda H_, key: np.concatenate([h_[key] for h_ in H_])
    offs = np.cumsum([0] + [len(h_['V']) for h_ in hard])
    hardM = dict(V=cat(hard, 'V'), N=cat(hard, 'N'), TAN=cat(hard, 'TAN'), UV=cat(hard, 'UV'), J=cat(hard, 'J'),
                 W=cat(hard, 'W'), F=np.concatenate([h_['F'] + o_ for h_, o_ in zip(hard, offs[:-1])]),
                 parts=[(h_['name'], int(o_), int(o_ + len(h_['V']))) for h_, o_ in zip(hard, offs[:-1])])
    # the pads' set: per clamp its pad, its strap and rivets, each vertex on its two-pose weights
    padp = []
    for cl, pw in zip(clamps, pad_W):
        pk = [pack(w_) for w_ in pw]
        Vb_, Nb_ = back_to_bind(cl['pad']['V'], cl['pad']['N'], pk)
        padp.append(dict(name=f'pad {cl["k"]}', V=Vb_, N=Nb_, UV=cl['pad']['UV'], F=cl['pad']['F'],
                         J=np.array([a_ for a_, _ in pk], np.int64), W=np.array([b_ for _, b_ in pk], np.float64),
                         underside=np.nonzero(cl['pad']['part'] == 0)[0]))
        for nm_, prt in [(f'strap {cl["k"]}', cl['strap'])] + [(f'rivet {cl["k"]}.{q_}', rv)
                                                                  for q_, rv in enumerate(cl['rivets'])]:
            pk = [pack(w_) for w_ in hw_W[nm_]]
            Vb_, Nb_ = back_to_bind(prt['V'], prt['N'], pk)
            padp.append(dict(name=nm_, V=Vb_, N=Nb_, UV=prt['UV'], F=prt['F'],
                             J=np.array([a_ for a_, _ in pk], np.int64), W=np.array([b_ for _, b_ in pk], np.float64)))
    for p_ in padp:
        _, p_['TAN'] = BK.low_frames(p_['V'], p_['F'], p_['UV'], p_['N'])
    offs = np.cumsum([0] + [len(h_['V']) for h_ in padp])
    padM = dict(V=cat(padp, 'V'), N=cat(padp, 'N'), TAN=cat(padp, 'TAN'), UV=cat(padp, 'UV'), J=cat(padp, 'J'),
                W=cat(padp, 'W'), F=np.concatenate([h_['F'] + o_ for h_, o_ in zip(padp, offs[:-1])]),
                parts=[(h_['name'], int(o_), int(o_ + len(h_['V']))) for h_, o_ in zip(padp, offs[:-1])])
    # ---------------------------------------------------------------- the smoothness in the reference pose
    rad_, turn_ = _bend_radius(Pr)
    face_ang = []
    for cl in clamps:
        rp = ring_pieces[f'clamp{cl["k"]}']
        for i_e, sgn in ((rp[0], 1), (rp[1], -1)):
            a_, b_ = (i_e - 1, i_e) if sgn > 0 else (i_e, i_e + 1)
            if 0 <= a_ and b_ < nr:
                t_ = Pr[b_] - Pr[a_]
                face_ang.append(math.degrees(math.acos(min(1.0, abs(t_ @ cl['R'][:, 0]) / np.linalg.norm(t_)))))
    rec = dict(arm=f'arm{j}', label=CO.ARM_LABELS[j], plate=plate, seed=seed, r_mm=r * 1e3, sides=SIDES, rings=nr,
               length_mm=_arclen(Pr) * 1e3, lying_mm=sum(_arclen(Q) for nm_, Q, _ in pieces if nm_.startswith('ride')) * 1e3,
               fitting=dict(site=pt.tolist(), normal=nrm.tolist(), clear_mm={k_: v_ * 1e3 for k_, v_ in clr.items()},
                            closed=dict(construction='cyborg_feed.collar_mesh (C5f)',
                                        skin_low_mm=plate_fit['rim']['skin_low'] * 1e3,
                                        wall_bottom_mm=plate_fit['rim']['bottom'] * 1e3,
                                        flipped=int(plate_fit['rim']['flipped']))),
               clamps=[dict(k=cl['k'], s=round(float(cl['s']), 5), segment=f'arm{j}_{cl["k"]:02d}',
                            weights={oct_.rig.jnames[k_]: round(w_, 4) for k_, w_ in
                                     sorted(cl['w'].items(), key=lambda kv: -kv[1])}) for cl in clamps],
               pad=dict(PD.PAD), spans=[{k_: (round(v_ * 1e3, 3) if isinstance(v_, float) and k_ not in
                                              ('i', 'end_tangent', 'crest_power') else v_) for k_, v_ in sp.items()}
                                        for sp in spans],
               s_turn=dict(span=S_SPAN, amp_mm=S_AMP * r * 1e3, profile='sin 2 pi u - sin 4 pi u / 2'),
               descend_mm=DESCEND_N * r * 1e3, ramp_mm=RAMP_N * r * 1e3,
               drawn_in='the reference rest pose (the recipe seed at t 0): the centreline assembled, resampled and framed '
                        'there, each ring and each pad vertex carried back to the bind by its own skin matrix',
               ring_pieces=ring_pieces, hard_parts=hardM['parts'], pad_parts=padM['parts'],
               pad_underside={p_['name']: [int(v_) for v_ in p_['underside']] for p_ in padp if 'underside' in p_},
               smooth_ref=dict(turn_max_deg=float(turn_.max()), bend_min_mm=float(rad_.min() * 1e3),
                               clamp_face_max_deg=float(max(face_ang) if face_ang else 0.0)),
               tile=dict(periods=TILE_PERIODS, length_mm=L_tile * 1e3, Pb_mm=Pb * 1e3),
               # C5f: the convoluted sections (their rings, the profile, each ring's design radius: c05c reads them)
               bellows=[dict(piece=b_['piece'], rings=b_['rings'], convolutions=int(b_['n']), pitch_mm=b_['pitch'] * 1e3,
                             amp=BELLOWS['amp'], compress=list(BELLOWS['compress']), ring_step_mm=0.25 * b_['pitch'] * 1e3,
                             r_mm=[float(x_) * 1e3 for x_ in r_ring[b_['rings'][0]:b_['rings'][1] + 1]]) for b_ in bel])
    log(f'[hose] seed {seed}: {rec["length_mm"]:.1f} mm long ({rec["lying_mm"]:.1f} lying on the skin), {nr} rings x '
        f'{SIDES}; clamps at s ' + ', '.join(f'{cl["s"]:.3f}' for cl in clamps) + '; spans ' +
        ', '.join(f'{sp["a"]}->{sp["b"]} {sp["kind"]}' + (f' (bow {sp["bow"] * 1e3:.1f} mm, {sp["L"] * 1e3:.1f} on '
                                                          f'{sp["d_ref"] * 1e3:.1f}, excess '
                                                          f'{sp.get("excess", 0.0) * 1e3:.2f})' if 'bow' in sp else
                                                          f' (excess {sp.get("excess", 0.0) * 1e3:.2f} mm)')
                  for sp in spans) +
        f'; in the reference pose: turn per step at most {turn_.max():.1f} deg, tightest bend {rad_.min() * 1e3:.1f} mm, '
        f'clamp faces at most {rec["smooth_ref"]["clamp_face_max_deg"]:.1f} deg')
    return dict(sleeve=dict(V=Vt, N=Nt, TAN=TANt, UV=UVt, F=Ft, J=Jt, W=Wt_), hard=hardM, pads=padM, joints=jn,
                joint_ids=used, record=rec, centre_ref=Pr, s=sr2, ring_w=W_ring, clamps=clamps, spans=spans,
                plate_fit=plate_fit, flange_fit=flange_fit, skin_path=Ps, r=r, L_tile=L_tile, Pb=Pb, ring_r=r_ring,
                bellows=bel)


# ============================================================================================ the sleeve's set
def tentacle_hose_texels(mech, islands, maps_dir=None):
    """the tentacle's own hose texels (its islands of region 'hose', rasterised on its shipped 2048 x 1024 set): linear
    albedo, roughness and AO samples, the calibration the sleeve is matched to"""
    from PIL import Image, ImageDraw
    d = maps_dir or os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5')
    alb = np.asarray(Image.open(os.path.join(d, 'T_mech_tentacle_albedo.png'))).astype(np.float64) / 255.0
    orm = np.asarray(Image.open(os.path.join(d, 'T_mech_tentacle_orm.png'))).astype(np.float64) / 255.0
    H_, W_ = alb.shape[:2]
    mask = Image.new('L', (W_, H_), 0)
    dr = ImageDraw.Draw(mask)
    for it in islands:
        if it['region'] != 'hose' or 'end' in it['piece']:
            continue
        for f in mech.F[it['f'][0]:it['f'][1]]:
            uv = mech.UV[f]
            dr.polygon([(float(u_ * W_), float(v_ * H_)) for u_, v_ in uv], fill=255)
    m = np.asarray(mask) > 0
    m = m & (np.roll(m, 2, 0) & np.roll(m, -2, 0) & np.roll(m, 2, 1) & np.roll(m, -2, 1))    # off the islands' rims
    lin = alb[m][:, :3] ** 2.2                                                                # the house's encoding
    return dict(albedo=lin, rough=orm[m][:, 1], ao=orm[m][:, 0], n=int(m.sum()))


def sleeve_maps(r, px, calib=None):
    """THE SLEEVE's tile: the tentacle's braid (cyborg_limb.material's hose: 16 carriers each way, over and under, the
    period 1.25 x the tow width along) round the whole hose and TILE_PERIODS periods along, at the tentacle's texel
    density, on the rubber row (forge/cyborg.py cyb_gasket, read only) as the tentacle composes it (base x (0.80 + 0.35
    crown), roughness 0.70 - 0.16 crown, the braid's height into the normal); matched to the tentacle's own hose texels
    (calib: their albedo and AO medians). Returns the maps (uint8: albedo sRGB x^(1/2.2) as the house writes it, normal,
    ORM, masks) and the record"""
    N_ = CL.BRAID['carriers']
    Pb = 1.25 * TAU * r / N_
    L_tile = TILE_PERIODS * Pb
    W_ = int(round(TAU * r * px))
    H_ = int(round(L_tile * px))
    i = (np.arange(W_) + 0.5) / W_
    jv = (np.arange(H_) + 0.5) / H_
    U, Vv = np.meshgrid(i, jv)                              # Vv: v up (the forge's), row 0 = v near 0 here
    phi = TAU * U
    s = L_tile * Vv
    phA = N_ * phi / TAU + s / Pb
    phB = N_ * phi / TAU - s / Pb
    fA, fB = phA - np.floor(phA), phB - np.floor(phB)
    topA = (np.floor(phA) + np.floor(phB)) % 2 == 0
    crown = np.where(topA, np.sin(np.pi * fA), np.sin(np.pi * fB))
    tow_tx = TAU * r / N_ * px
    amp = float(CL._ss(tow_tx, 2.5, 4.0))
    hb = 0.5 + amp * (np.maximum(crown, 0.0) ** 0.6 - 0.5)
    height = CL.BRAID['depth'] * 2.0 * r * (hb - 0.5)
    rows = CL._rows()
    base = rows['rubber']['base'][None, None, :] * (0.80 + 0.35 * hb)[..., None]
    rough = 0.70 - 0.16 * hb
    ao = np.ones_like(hb)
    if calib is not None:
        g = np.median(calib['albedo'], axis=0) / np.maximum(np.median(base.reshape(-1, 3), axis=0), 1e-6)
        base = base * g[None, None, :]
        ao = ao * float(np.median(calib['ao']))
        rough = rough + (float(np.median(calib['rough'])) - float(np.median(rough)))
    base = np.clip(base, 0.013, 0.87)
    # the height's gradient (periodic both ways) in metres per metre along u (round) and v (along)
    du, dv = TAU * r / W_, L_tile / H_
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2.0 * du)
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2.0 * dv)
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    enc = lambda x: np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8)
    flipv = lambda a: a[::-1]                               # image row 0 is v = 1
    maps = dict(albedo=flipv(enc(base ** (1.0 / 2.2))), normal=flipv(enc(n * 0.5 + 0.5)),
                orm=flipv(enc(np.stack([ao, np.clip(rough, 0.04, 1.0), np.zeros_like(ao)], -1))),
                masks=np.zeros((H_, W_, 4), np.uint8))
    rec = dict(size=[W_, H_], px_per_m=px, carriers=N_, period_mm=Pb * 1e3, tile_mm=L_tile * 1e3,
               tow_tx=tow_tx, albedo_gain=None if calib is None else [round(float(v), 4) for v in g],
               ao=float(np.median(ao)), rough_median=float(np.median(rough)),
               calib=None if calib is None else dict(texels=calib['n'], albedo=np.median(calib['albedo'], 0).round(4).tolist(),
                                                     rough=round(float(np.median(calib['rough'])), 4),
                                                     ao=round(float(np.median(calib['ao'])), 4)))
    return maps, rec


# ============================================================================================ the glb
def export_glb(path, oct_, HO, maps, pmaps, mech_maps_name='mech_tentacle'):
    """THE HOSE as a skinned glb: one mesh, three primitives sharing its vertex set: the SLEEVE (its own tiling set, a
    REPEAT sampler: material cyborg_hose_sleeve, extras bestiary 'cyborg'), the HARDWARE (the two fittings: copies of the
    tentacle's islands, their UVs on its set: material 'mech_tentacle' carrying no maps, extras shares 'mech_tentacle':
    the runtime gives it the mounted tentacle's own material) and the PADS (C5c: the saddle pads, straps and rivets on
    their own small set, pmaps: material cyborg_hose_pads); the skin's joints the octopus's bones by name with the
    octopus's inverse binds (the runtime binds the mesh to the creature's own bones by name: one skeleton per creature);
    the record in the extras"""
    from . import gltf
    from . import rig as RG
    sl, hd, pdm = HO['sleeve'], HO['hard'], HO['pads']
    g = gltf.GLB()
    g.j['samplers'].append({'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497})
    rep = len(g.j['samplers']) - 1
    tex = []
    for key, fmt in (('albedo', 'png'), ('normal', 'png'), ('orm', 'png'), ('masks', 'png')):
        ti = g.texture(maps[key], fmt=fmt)
        g.j['textures'][ti]['sampler'] = rep
        tex.append(ti)
    m_sl = g.material('cyborg_hose_sleeve', base=tex[0], normal=tex[1], orm=tex[2], volume_tex=tex[3], extras=dict(
        bestiary='cyborg', part='cyborg_hose', masks=tex[3],
        masks_channels='R primary tint region (none: the rubber sleeve), G accent, B emissive, A wear (none)',
        sampler='REPEAT along and round: one tile is the whole circumference and a whole number of braid periods',
        rows='forge/cyborg.py cyb_gasket (the rubber row) with cyborg_limb BRAID, matched to the tentacle\'s hose'))
    m_hd = g.material(mech_maps_name, extras=dict(bestiary='cyborg', part='cyborg_hose', shares=mech_maps_name,
                                                  note='the fittings are copies of the mech tentacle\'s own islands: '
                                                       'their UVs are on its set; the runtime renders them with the '
                                                       'mounted tentacle\'s material'))
    ptex = [g.texture(pmaps[key], fmt='png') for key in ('albedo', 'normal', 'orm', 'masks')]
    m_pd = g.material('cyborg_hose_pads', base=ptex[0], normal=ptex[1], orm=ptex[2], volume_tex=ptex[3], extras=dict(
        bestiary='cyborg', part='cyborg_hose', masks=ptex[3],
        masks_channels='R primary tint region (none), G accent, B emissive, A wear (none)',
        rows='forge/cyborg.py cyb_gasket (the pads), cyb_steel black oxide (the straps), cyb_steel bare (the rivets)',
        note='the saddle pads, straps and rivets: every clamp\'s texels stacked on one 256 x 256 sheet'))
    # the skeleton: the octopus's bones the skin names, each with its whole parent chain (so a viewer poses them at
    # the bind), the inverse binds the octopus's
    rg = oct_.rig
    need = set()
    for nm in HO['joints']:
        i = rg.index[nm]
        while i >= 0:
            need.add(i)
            i = rg.parent[i]
    W = rg.worlds()
    sk = RG.Skeleton()
    order = [i for i in rg.order if i in need]
    for i in order:
        p = rg.parent[i]
        sk.add(rg.names[i], rg.names[p] if p >= 0 and p in need else None, W[i][:3, 3], W[i][:3, :3])
    skin, jnodes = g.skeleton(sk)
    jidx = {nm: k for k, nm in enumerate(sk.names)}
    remap = np.array([jidx[nm] for nm in HO['joints']])
    V = np.concatenate([sl['V'], hd['V'], pdm['V']])
    N = np.concatenate([sl['N'], hd['N'], pdm['N']])
    T = np.concatenate([sl['TAN'], hd['TAN'], pdm['TAN']])
    UV = np.concatenate([sl['UV'], hd['UV'], pdm['UV']])
    J4 = remap[np.concatenate([sl['J'], hd['J'], pdm['J']])]
    W4 = np.concatenate([sl['W'], hd['W'], pdm['W']])
    o_h, o_p = len(sl['V']), len(sl['V']) + len(hd['V'])
    mesh = g.mesh('cyborg_hose', V, N, T, UV, [(sl['F'], m_sl), (hd['F'] + o_h, m_hd), (pdm['F'] + o_p, m_pd)],
                  joints=J4, weights=W4)
    g.node('cyborg_hose', mesh=mesh, skin=skin, root=True)
    rec = dict(HO['record'])
    rec.update(part='cyborg_hose', family='cyborg_hose', units='m', up='+Y', forward='+Z',
               joints=list(HO['joints']), skin_note='the octopus\'s own bones by name (one skeleton per creature)',
               triangles=dict(sleeve=int(len(sl['F'])), hardware=int(len(hd['F'])), pads=int(len(pdm['F']))),
               vertex_offsets=dict(sleeve=0, hardware=int(o_h), pads=int(o_p), end=int(len(V))),
               ends=dict(plate=f'plate {HO["record"]["plate"]} of the default look (a port seated on it)',
                         flange=f'the inlet port on {HO["record"]["arm"]}_07\'s collar (the tentacle\'s fitting mirrored)'))
    return g.save(path, extras=dict(bestiary=rec))


# ============================================================================================ C5c: one hose per seed
HOSE_DIR = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5b', 'hose')
FEED_DIR = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c3', 'feed')
OCT_GLB = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5b', 'assembled', 'octopus.glb')


def hose_asset(chain, seed):
    """the hose's asset name for a recipe seed (the runtime block's name, patches/cyborg_c5b_recipe.md)"""
    return f'cyborg_hose_{chain}_s{int(seed)}'


def _sha1(path):
    import hashlib
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


class HoseContext:
    """what every seed's hose reads, loaded once: the assembled octopus (t13's cut export of the plated octopus), its
    low, the mech tentacle, the plates' geometry, the tentacle's islands and hose texels, the replaced arm's ground
    profile, the swim rig's times; and the inputs' sha1s the cache keys on"""

    def __init__(self, arm=CO.ARM_DEFAULT, oct_glb=OCT_GLB, feed=FEED_DIR, log=print):
        self.arm = arm
        self.oct_ = CO.Octopus(oct_glb, os.path.join(feed, 'low.npz'))
        self.mech = CO.Mech()
        P_bind = self.oct_.arm_bind(arm)['P']
        self.H = CO.ground_profile(self.mech.table, np.linalg.norm(np.diff(P_bind, axis=0), axis=1),
                                   reach=self.oct_.flesh_reach(arm))
        self.geo = plate_geometry(os.path.join(feed, 'cyborg_plates.pkl'),
                                  dict(V=self.oct_.low['V'], F=self.oct_.F, region=self.oct_.region))
        self.I = mech_islands()
        _, self.ts_swim = CO.swim_arm_frames(self.oct_, arm)
        here = os.path.dirname(os.path.abspath(__file__))
        # (C5f: and cyborg_feed.py, whose collar_mesh builds the plate fitting)
        self.inputs = {os.path.basename(p_): _sha1(p_)[:12] for p_ in (
            oct_glb, CO.MECH_GLB, os.path.join(feed, 'cyborg_plates.pkl'),
            os.path.join(here, 'cyborg_hose.py'), os.path.join(here, 'cyborg_pads.py'),
            os.path.join(here, 'cyborg_octopus.py'), os.path.join(here, 'cyborg_cable.py'),
            os.path.join(here, 'cyborg_feed.py'))}
        self.log = log

    def ref_worlds(self, seed):
        return CO.rest_frame(self.oct_, seed, 0.0, replaced=self.arm, H=self.H)

    def motion(self, seed):
        ts = np.arange(0.0, 60.0, 0.1)

        def f(names):
            """the nodes' worlds over the seed's rest motion (60 s at 10 fps) and the swim rig"""
            return np.concatenate([CO.rest_node_worlds(self.oct_, names, [seed], ts, H=self.H, replaced=self.arm),
                                   CO.swim_node_worlds(self.oct_, names, self.ts_swim)])
        return f


def hose_for_seed(seed, ctx=None, out_dir=HOSE_DIR, force=False, log=print):
    """THE HOSE FOR A RECIPE SEED (the lead's C5c decision 3): rebuilt for the seed's own reference pose (its rest pose
    at t 0) at assembly and CACHED by seed: out_dir/<hose_asset>.glb with its record beside it, rebuilt when absent or
    when any input's sha1 (the assembled octopus, the mech tentacle, the plates, this module, cyborg_pads.py,
    cyborg_octopus.py, cyborg_cable.py) differs from the one its record keeps; C5d: its glb carries the CABLE's data
    (forge/cyborg_cable.py, the extras' bestiary.cable: the runtime re-makes the hose on the skin from it every frame;
    the record beside it leaves it out). Returns (glb path, record)"""
    import json
    ctx = ctx or HoseContext(log=log)
    chain = f'arm{ctx.arm}'
    name = hose_asset(chain, seed)
    os.makedirs(out_dir, exist_ok=True)
    glb = os.path.join(out_dir, name + '.glb')
    recp = os.path.join(out_dir, name + '.json')
    if not force and os.path.exists(glb) and os.path.exists(recp):
        with open(recp, encoding='utf-8') as f:
            old = json.load(f)
        if old.get('inputs') == ctx.inputs:
            return glb, old
    mo = ctx.motion(seed)
    rw = ctx.ref_worlds(seed)
    HO = build_hose(ctx.oct_, ctx.mech, ctx.geo, ctx.arm, islands=ctx.I, motion=mo, ref_worlds=rw, seed=seed, log=log)
    from . import cyborg_cable as CC
    HO['record']['cable'] = CC.cable_data(ctx, HO, rw, log=log)
    from . import cyborg_pads as PD
    calib = tentacle_hose_texels(ctx.mech, ctx.I['islands'])
    maps, srec = sleeve_maps(HO['r'], float(ctx.I['px']), calib)
    pmaps, prec = PD.pad_maps(float(ctx.I['px']))
    export_glb(glb, ctx.oct_, HO, maps, pmaps)
    rec = dict(record={k_: v_ for k_, v_ in HO['record'].items() if k_ != 'cable'}, sleeve=srec, pads=prec,
               inputs=ctx.inputs, asset=name, seed=int(seed))
    with open(recp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rec, f, indent=1, default=float)
    return glb, rec
