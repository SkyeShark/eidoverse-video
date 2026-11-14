"""HUMAN H1: the FIT of the baseline cage and its limit clay (HUMAN_PLAN §2.2, §2.7; the lead's H1 decision 2).

THE FAIRED FIT is the default (the H0 review: exact interpolation folds the inner eye corner and the helix): the wolf's
W2j form (canid_cage.fit_cage), the control points V minimising
    sum_v w_v |(A V)_v - T_v|^2 + sum_v lam_v |(L V)_v|^2
A the limit positions of the cage's own vertices (subdiv_sharp.limit_operator, through the creases' levels), L the
umbrella Laplacian, w: features W_FEAT, the rest 1; LAMBDA PER CAGE DENSITY: lam_v = LAM0 (H_REF / h_v)^4, h_v the mean
edge length at v, because |L V| grows with h^2 at a given curvature (H0: lam 0.2 passed the lids at the dense box's ~2.4
mm spacing and over-smoothed them at the plan box's ~1.6x coarser one, where 0.05 and 0.02 passed), eased to LAM_CREASE
/ LAM0 of that at crease vertices. In passes, each re-targeting the FREE vertices at the reference's closest point to
their limit point (they slide along it); the features stay on their traced targets. THE LOW is the cage on its limit
(level 0): low = A V (the lead's decision 1).

    fit(cage, sharp, targets, held, retarget, levels, log) -> controls, report
    limit(cage, controls, sharp, levels) -> the limit clay (QuadMesh, its parent quads)
"""
import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS

FIT = dict(w_feat=40.0, w_free=1.0, lam0=0.2, h_ref=2.4, lam_crease=0.02, passes=4, levels=3, mu=0.2, slide=1.0)
# mu: a uniform RELATIVE fairness mu |L (V - T)|^2, the control net's Laplacian against the target net's own: with the
# shape fairness eased in coarse regions (lam ~ 1e-5 at 20 mm edges) the inversion went ill-conditioned there and the
# controls ran up to 57 mm from their targets round the ear's rim and the plugs, the limit still through the targets
# (H1's first head: a tube out of the concha, sheets behind the helix). Relative to the targets' shape it suppresses
# the control net's oscillation at every density and flattens no curvature the targets carry


def umbrella(Q, n):
    E = np.unique(np.sort(np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]]), axis=1), axis=0)
    Adj = sp.csr_matrix((np.ones(2 * len(E)), (np.concatenate([E[:, 0], E[:, 1]]), np.concatenate([E[:, 1], E[:, 0]]))),
                        shape=(n, n))
    deg = np.asarray(Adj.sum(1)).ravel()
    return (sp.eye(n) - sp.diags(1.0 / np.maximum(deg, 1)) @ Adj).tocsr(), E


def lam_per_vertex(V, E, fit=FIT):
    """lam_v = lam0 min(1, (h_ref / h_v)^4) with h_v the mean length of v's edges: the fairness eased where the cage is
    coarser than the dense face (H0: lam 0.2 over-smoothed the plan box's lids), never raised past the tested lam0
    where it is denser (H1's first fit raised it as h^-4: lam ~150 at the inner canthus' 0.5 mm edges overpowered the
    held features and printed a blade-like fin)"""
    n = len(V)
    el = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    s = np.bincount(E[:, 0], el, n) + np.bincount(E[:, 1], el, n)
    c = np.bincount(E[:, 0], None, n) + np.bincount(E[:, 1], None, n)
    h = s / np.maximum(c, 1)
    return fit['lam0'] * np.minimum(1.0, (fit['h_ref'] / np.maximum(h, 1e-3)) ** 4), h


def fit(cage, sharp, targets, held, retarget=None, mirror=None, mid=None, levels=None, fit_=None, log=print,
        A=None):
    """the faired fit (the module's docstring). cage: QuadMesh of the TARGET positions (its topology is the cage's);
    targets (n, 3); held (bool n): features held at weight w_feat; retarget(P, free_mask) -> new targets for the free
    vertices (closest points on the reference) or None; mirror: the full cage's mirror map (controls averaged with their
    mirror against round-off), mid: midline vertex ids (x = 0). Returns controls (n, 3), report"""
    fz = dict(FIT, **(fit_ or {}))
    levels = fz['levels'] if levels is None else levels
    t0 = time.time()
    n = len(cage.V)
    if A is None:
        A, _ = SS.limit_operator(cage, sharp, levels)
    Lp, E = umbrella(cage.Q, n)
    lam, h = lam_per_vertex(cage.V, E, fz)
    on_crease = np.zeros(n, bool)
    for (a, b) in sharp:
        on_crease[a] = on_crease[b] = True
    lam = np.where(on_crease, lam * fz['lam_crease'] / fz['lam0'], lam)
    LtL = (Lp.T @ sp.diags(lam) @ Lp).tocsr()
    w = np.where(held, fz['w_feat'], fz['w_free'])
    T = np.asarray(targets, np.float64).copy()
    T0 = T.copy()
    rep = dict(passes=[])
    V = T.copy()
    # the relative fairness PER DENSITY too: mu (h_ref / h)^2, capped at mu. Uniform, it held the body's coarse tubes
    # (24-48 round, 10-20 mm apart) to their target net's shape and fought the outward correction the limit needs to
    # reach the targets there: the body's limit sat 1.75 mm p95 inside its targets, the head's 0.18 (H1's first figure)
    mu_v = fz['mu'] * np.minimum(1.0, (fz['h_ref'] / np.maximum(h, 1e-3)) ** 2)
    LL = (Lp.T @ sp.diags(mu_v) @ Lp).tocsr()
    for ps in range(fz['passes']):
        Sys = (A.T @ sp.diags(w) @ A + LtL + LL).tocsc()
        lu = spla.splu(Sys)
        rhs = A.T @ (w[:, None] * T) + LL @ T
        V = np.column_stack([lu.solve(rhs[:, k]) for k in range(3)])
        if mid is not None:
            V[mid, 0] = 0.0
        P = A @ V
        dev = np.linalg.norm(P - T, axis=1)
        row = dict(feat_max=float(dev[held].max()) if held.any() else 0.0,
                   feat_p95=float(np.percentile(dev[held], 95)) if held.any() else 0.0,
                   free_med=float(np.median(dev[~held])), free_p95=float(np.percentile(dev[~held], 95)))
        rep['passes'].append(row)
        log(f'[fit] pass {ps}: features within {row["feat_max"]:.3f} mm of their targets (p95 {row["feat_p95"]:.3f}); '
            f'free limit points {row["free_med"]:.3f} median, {row["free_p95"]:.3f} p95 off theirs')
        if retarget is not None and ps < fz['passes'] - 1:
            Tn = retarget(P, ~held)
            # a target slides along the reference by at most one local edge length from where it was placed: a limit
            # point in a bowl or behind a fold finds its closest point ACROSS the fold (the tragus, the head behind
            # the auricle), and pass after pass pulled the ear into a tube and a sheet (H1's first ear)
            slide = np.linalg.norm(Tn - T0, axis=1)
            ok = slide <= fz.get('slide', 1.0) * h
            T = np.where((held | ~ok)[:, None], T, Tn)
            if mid is not None:
                T[mid, 0] = 0.0
            row['refused'] = int((~ok & ~held).sum())
    if mirror is not None:
        Vm = V[mirror] * np.array([-1.0, 1.0, 1.0])
        V = 0.5 * (V + Vm)
        if mid is not None:
            V[mid, 0] = 0.0
    rep['time'] = time.time() - t0
    rep['lam_range'] = [float(lam.min()), float(np.median(lam)), float(lam.max())]
    rep['h_range'] = [float(h.min()), float(np.median(h)), float(h.max())]
    rep['targets'] = T
    rep['low'] = A @ V
    return V, rep


def limit(cage, V, sharp, levels=3):
    """the limit clay: the cage with controls V subdivided `levels` levels and pushed to the limit; (QuadMesh, the
    ancestor cage quad of each limit quad)"""
    lim, s_e, par, _ = SS.subdivide(QuadMesh(V, cage.Q), sharp, levels)
    return lim, par
