"""HUMAN H1: the WHOLE baseline cage: the head half (human_head, in GNM's chart) and the body half (human_body, on the
pinned MakeHuman) joined at the shared neck ring, made consistent in orientation, mirrored about the midline (the
midline vertices shared) into ONE closed quad cage; its records: the held features, the creases, the regions, the graft
rings and ports with their K (HUMAN_PLAN §6.2).

    mirror(Qh, P, mid, sharp, n) -> V (n_full, 3), Q, mir, sharp_full
    orient(Q, P, ref_normal) -> Q with every quad facing like the reference (propagated, then the global sign)
"""
import numpy as np


def mirror(Qh, P_half, mid_ids, sharp_h, n_half=None):
    """the full cage from the half (x >= 0): the half's vertices, then the mirrored copies of the non-midline ones;
    the mirrored quads reversed (a reflection flips the winding); the creases copied. mir[v] = v's mirror vertex"""
    n = len(P_half) if n_half is None else n_half
    is_mid = np.zeros(n, bool)
    is_mid[np.asarray(mid_ids, int)] = True
    off = np.cumsum(~is_mid) - 1 + n
    mir_h = np.where(is_mid, np.arange(n), off)
    n_full = n + int((~is_mid).sum())
    V = np.zeros((n_full, 3))
    V[:n] = P_half
    V[mid_ids, 0] = 0.0
    Pm = np.asarray(P_half, np.float64).copy()
    Pm[:, 0] *= -1.0
    V[mir_h[~is_mid]] = Pm[~is_mid]
    Qh = np.asarray(Qh, int)
    Q = np.vstack([Qh, mir_h[Qh][:, ::-1]])
    mir = np.zeros(n_full, int)
    mir[:n] = mir_h
    mir[mir_h] = np.arange(n)
    sharp = {}
    for (a, b), s in sharp_h.items():
        sharp[(min(a, b), max(a, b))] = s
        ma, mb = mir_h[a], mir_h[b]
        sharp[(min(ma, mb), max(ma, mb))] = s
    return V, Q, mir, sharp


def assemble(TH, Ph, BT, Pb_full, Qb_full, mir_b, half_top):
    """the WHOLE cage: the head (TH: its quads, mirror map; Ph its targets in the body frame) and the full body (its
    targets, quads and mirror map from mirror()) joined at the K 48 neck ring: the body's top neck ring (the half
    BT.neck[-1], index k <-> the head ring's index half_top[k]; their mirrors <-> the mirrored indices) takes the head's
    vertices. Returns V (n, 3), Q, mir, the body's id map (body id -> cage id) and the head's count"""
    nh = TH.n
    nb = len(Pb_full)
    bmap = -np.ones(nb, np.int64)
    ring_h = TH.neck_ring
    for k, v in enumerate(BT.neck[-1]):
        j = half_top[k]
        bmap[v] = ring_h[j]
        bmap[mir_b[v]] = ring_h[(-j) % len(ring_h)]
    rest = np.nonzero(bmap < 0)[0]
    bmap[rest] = nh + np.arange(len(rest))
    n = nh + len(rest)
    V = np.zeros((n, 3))
    V[:nh] = Ph
    V[bmap[rest]] = Pb_full[rest]
    Q = np.vstack([np.asarray(TH.Q, np.int64), bmap[np.asarray(Qb_full, np.int64)]])
    mir = np.zeros(n, np.int64)
    mir[:nh] = TH.mir
    mir[bmap[rest]] = bmap[mir_b[rest]]
    return V, Q, mir, bmap, nh


def orient(Q, P, ref_normal):
    """every quad wound consistently: propagated across shared edges from a seed (a quad and its neighbour run their
    shared edge in opposite directions), then the whole flipped if most quads face against ref_normal(centres)"""
    Q = np.asarray(Q, int).copy()
    m = len(Q)
    emap = {}
    for qi, q in enumerate(Q.tolist()):
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            emap.setdefault((min(a, b), max(a, b)), []).append(qi)
    nbr = [[] for _ in range(m)]
    for lst in emap.values():
        if len(lst) == 2:
            nbr[lst[0]].append(lst[1])
            nbr[lst[1]].append(lst[0])
    seen = np.zeros(m, bool)
    flips = 0
    for seed in range(m):
        if seen[seed]:
            continue
        seen[seed] = True
        stack = [seed]
        while stack:
            qi = stack.pop()
            dq = {(Q[qi][k], Q[qi][(k + 1) % 4]) for k in range(4)}
            for qj in nbr[qi]:
                if seen[qj]:
                    continue
                dj = {(Q[qj][k], Q[qj][(k + 1) % 4]) for k in range(4)}
                if dq & dj:                                   # the same directed edge: qj runs the wrong way
                    Q[qj] = Q[qj][::-1]
                    flips += 1
                seen[qj] = True
                stack.append(qj)
    cen = P[Q].mean(1)
    fn = np.cross(P[Q[:, 2]] - P[Q[:, 0]], P[Q[:, 3]] - P[Q[:, 1]])
    rn = ref_normal(cen)
    agree = np.einsum('ij,ij->i', fn, rn) > 0
    if agree.mean() < 0.5:
        Q = Q[:, ::-1].copy()
        agree = ~agree
    return Q, float(agree.mean()), flips
