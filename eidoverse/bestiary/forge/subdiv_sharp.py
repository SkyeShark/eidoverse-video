"""B3g (the lead, 10-27): SEMI-SHARP Catmull-Clark subdivision of a pure-quad mesh (DeRose, Kass & Truong 1998, "Subdivision
Surfaces in Character Animation", SIGGRAPH '98, section 3), one sparse matrix per level like the forge's subdiv.py (which
holds infinitely sharp creases only and is shared with the octopus: this module imports mesh.QuadMesh and leaves subdiv.py
alone).

THE RULES (DKT 1998 3.1-3.3). Every edge carries a sharpness s >= 0 (0 smooth, np.inf infinitely sharp; a boundary edge is
infinitely sharp). At each level:
  face point   the corners' mean
  edge point   s >= 1: the sharp rule, the midpoint (v0 + v1) / 2; s = 0: the smooth rule (v0 + v1 + f0 + f1) / 4;
               0 < s < 1: (1 - s) smooth + s sharp (the fractional blend)
  vertex point with n_c incident edges of s > 0 and s_v their mean sharpness, w = min(s_v, 1):
               n_c <= 1   the smooth rule (n-2)/n P + sum(u)/n^2 + sum(f)/n^2 (a dart is smooth)
               n_c == 2   w (3/4 P + 1/8 (u_a + u_b)) + (1 - w) smooth (u_a, u_b: the two crease neighbours)
               n_c >= 3   w P + (1 - w) smooth (a corner)
  sharpness    each edge splits in two; a child's sharpness falls by one level: 'uniform' max(s - 1, 0) for both halves,
               or 'chaikin' (DKT 3.3's variable sharpness along a crease, OpenSubdiv's Chaikin rule): the half at vertex v
               of an edge whose crease continues through v along exactly one other crease edge e' takes
               max((3 s + s') / 4 - 1, 0), so a sharpness that varies along a loop varies smoothly at every level.
So an edge of integer sharpness s is sharp for its first s levels and smooth after: the limit surface rounds it at the
scale of the cage spacing / 2^s (a radius that halves per unit of sharpness; fractional s interpolates).

THE LIMIT. Once no edge is sharp (after ceil(max s) levels, boundaries excepted) every vertex's limit position is the
standard Catmull-Clark mask (n^2 P + 4 sum(e) + sum(f)) / (n (n + 5)) (e the edge neighbours, f the quads' opposite
corners); limit_matrix() returns it as a sparse operator, so a subdivided mesh can be pushed onto the limit surface exactly.

FITTING (fit_controls): every quantity above is linear in the cage positions for fixed sharpness, so the limit positions
of the cage's own vertices are A V0 with A sparse (the levels' operators composed, then the limit mask): solving
A V0 = T makes the limit surface INTERPOLATE target points T at the cage's vertices (with the creases' rounding in A).

Layout per level (subdiv.py's): [vertex points (n), edge points (E), face points (m)]; quad (v0 v1 v2 v3) becomes (v0 e01
f e30), (v1 e12 f e01), (v2 e23 f e12), (v3 e30 f e23), children of one parent adjacent (4f .. 4f+3).
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh import QuadMesh


def edge_keys(E):
    """a dict (a, b) -> edge id for the sorted pairs E"""
    return {(int(a), int(b)): i for i, (a, b) in enumerate(np.asarray(E).tolist())}


def sharpness_per_edge(mesh, sharp):
    """sharp: dict {(a, b): s} (vertex pairs in any order) or an (E,) array aligned with mesh.edges(); returns the per-edge
    array (missing pairs 0) and the edge list"""
    E, QE = mesh.edges()
    if isinstance(sharp, dict):
        s = np.zeros(len(E))
        key = edge_keys(E)
        miss = 0
        for (a, b), v in sharp.items():
            i = key.get((min(a, b), max(a, b)))
            if i is None:
                miss += 1
                continue
            s[i] = max(s[i], float(v))
        if miss:
            raise ValueError(f'sharpness given for {miss} vertex pairs that are not edges of the mesh')
        return s, E, QE
    s = np.asarray(sharp, np.float64)
    assert len(s) == len(E), 'a per-edge sharpness array must align with mesh.edges()'
    return s.copy(), E, QE


def level(mesh: QuadMesh, s_e, rule='chaikin'):
    """one semi-sharp Catmull-Clark level. s_e: per-edge sharpness aligned with mesh.edges(). Returns the operator S (n1 x n),
    the new quads Q1 and the new per-edge sharpness aligned with QuadMesh(., Q1).edges()"""
    n, m = len(mesh.V), len(mesh.Q)
    E, QE = mesh.edges()
    nE = len(E)
    ef = mesh.edge_faces(E, QE)
    bnd = ef[:, 1] < 0
    s = np.asarray(s_e, np.float64).copy()
    s[bnd] = np.inf
    w_e = np.clip(s, 0.0, 1.0)                                   # the edge rule's blend (1: sharp)
    w_e[bnd] = 1.0
    # ---- face points
    Sf = sp.csr_matrix((np.full(4 * m, 0.25), (np.repeat(np.arange(m), 4), mesh.Q.ravel())), shape=(m, n))
    # ---- edge points: (1 - w) (v0 + v1 + f0 + f1) / 4 + w (v0 + v1) / 2
    cv = (1.0 - w_e) * 0.25 + w_e * 0.5
    Aev = sp.csr_matrix((np.repeat(cv, 2), (np.repeat(np.arange(nE), 2), E.ravel())), shape=(nE, n))
    inter = np.nonzero(~bnd)[0]
    cf = (1.0 - w_e[inter]) * 0.25
    Aef = sp.csr_matrix((np.repeat(cf, 2), (np.repeat(inter, 2), ef[inter].ravel())), shape=(nE, m))
    Se = Aev + Aef @ Sf
    # ---- vertex points
    val = np.bincount(E.ravel(), minlength=n).astype(np.float64)
    crease_e = s > 0.0
    n_c = np.bincount(E[crease_e].ravel(), minlength=n)
    s_fin = np.where(np.isinf(s), 1.0e3, s)                      # (a mean over an infinite edge stays >= 1)
    s_sum = np.bincount(E[crease_e].ravel(), weights=np.repeat(s_fin[crease_e], 2), minlength=n)
    s_v = np.where(n_c > 0, s_sum / np.maximum(n_c, 1), 0.0)
    w_v = np.where(n_c >= 2, np.clip(s_v, 0.0, 1.0), 0.0)
    is_crease = n_c == 2
    is_corner = n_c >= 3
    nn = np.maximum(val, 1.0)
    on_bnd = np.bincount(E[bnd].ravel(), minlength=n) > 0
    # the smooth rule's weights (a boundary vertex never takes it: its two boundary edges give w = 1)
    sm = (1.0 - w_v) * (~on_bnd)
    diag = sm * (nn - 2.0) / nn + np.where(is_crease, w_v * 0.75, 0.0) + np.where(is_corner, w_v * 1.0, 0.0)
    a, b = E[:, 0], E[:, 1]
    w_ab = sm[a] / nn[a] ** 2 + np.where(is_crease[a] & crease_e, w_v[a] * 0.125, 0.0)   # row a, column b
    w_ba = sm[b] / nn[b] ** 2 + np.where(is_crease[b] & crease_e, w_v[b] * 0.125, 0.0)   # row b, column a
    Avu = sp.csr_matrix((np.concatenate([w_ab, w_ba]), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(n, n))
    fr = mesh.Q.ravel()
    Avf = sp.csr_matrix((sm[fr] / nn[fr] ** 2, (fr, np.repeat(np.arange(m), 4))), shape=(n, m))
    Sv = sp.diags(diag) + Avu + Avf @ Sf
    S = sp.vstack([Sv, Se, Sf]).tocsr()
    # ---- the new topology (subdiv.py's)
    v = mesh.Q
    e = QE + n
    f = (np.arange(m) + n + nE)[:, None]
    Q1 = np.concatenate([np.column_stack([v[:, 0], e[:, 0], f[:, 0], e[:, 3]]),
                         np.column_stack([v[:, 1], e[:, 1], f[:, 0], e[:, 0]]),
                         np.column_stack([v[:, 2], e[:, 2], f[:, 0], e[:, 1]]),
                         np.column_stack([v[:, 3], e[:, 3], f[:, 0], e[:, 2]])])
    Q1 = Q1[np.arange(4 * m).reshape(4, m).T.ravel()]
    # ---- the children's sharpness: parent edge i = (a, b) -> (a, n+i) and (n+i, b)
    s_child_a = np.maximum(s - 1.0, 0.0)
    s_child_b = s_child_a.copy()
    if rule == 'chaikin':
        # at vertex v with exactly two crease edges i and j: the half of i at v takes (3 s_i + s_j) / 4 - 1
        ce = np.nonzero(crease_e & ~np.isinf(s))[0]
        if len(ce):
            inc = {}
            for i in np.nonzero(crease_e)[0].tolist():
                for vv in (int(E[i, 0]), int(E[i, 1])):
                    inc.setdefault(vv, []).append(i)
            for i in ce.tolist():
                for end, vv in ((0, int(E[i, 0])), (1, int(E[i, 1]))):
                    lst = inc.get(vv, [])
                    if len(lst) == 2:
                        j = lst[0] if lst[1] == i else lst[1]
                        sj = s[j] if not np.isinf(s[j]) else s[i]
                        val_ = max((3.0 * s[i] + sj) / 4.0 - 1.0, 0.0)
                        if end == 0:
                            s_child_a[i] = val_
                        else:
                            s_child_b[i] = val_
    s_child_a[np.isinf(s)] = np.inf
    s_child_b[np.isinf(s)] = np.inf
    mesh1 = QuadMesh(np.zeros((n + nE + m, 3)), Q1)
    E1, _ = mesh1.edges()
    key1 = edge_keys(E1)
    s1 = np.zeros(len(E1))
    for i in np.nonzero((s_child_a > 0) | (s_child_b > 0))[0].tolist():
        a_, b_, ep = int(E[i, 0]), int(E[i, 1]), n + i
        s1[key1[(min(a_, ep), max(a_, ep))]] = s_child_a[i]
        s1[key1[(min(ep, b_), max(ep, b_))]] = s_child_b[i]
    return S, Q1, s1


def limit_matrix(mesh: QuadMesh, s_e=None):
    """the Catmull-Clark LIMIT mask as a sparse (n x n) operator: smooth vertices (n^2 P + 4 sum e + sum f) / (n (n + 5)),
    crease vertices (two sharp edges) (u_a + 4 P + u_b) / 6, corners and boundary corners P. s_e (per edge) marks edges
    still sharp; with none sharp every vertex takes the smooth mask"""
    n = len(mesh.V)
    E, QE = mesh.edges()
    sharp = np.zeros(len(E), bool) if s_e is None else (np.asarray(s_e) > 0)
    ef = mesh.edge_faces(E, QE)
    sharp = sharp | (ef[:, 1] < 0)
    val = np.bincount(E.ravel(), minlength=n).astype(np.float64)
    n_c = np.bincount(E[sharp].ravel(), minlength=n)
    smooth = n_c <= 1
    crease = n_c == 2
    corner = n_c >= 3
    nn = np.maximum(val, 1.0)
    den = nn * (nn + 5.0)
    rows, cols, data = [], [], []
    idx = np.arange(n)
    # the centre
    rows.append(idx)
    cols.append(idx)
    data.append(np.where(smooth, nn * nn / den, np.where(crease, 4.0 / 6.0, 1.0)))
    # edge neighbours
    a, b = E[:, 0], E[:, 1]
    for p, q in ((a, b), (b, a)):
        wq = np.where(smooth[p], 4.0 / den[p], np.where(crease[p] & sharp, 1.0 / 6.0, 0.0))
        rows.append(p)
        cols.append(q)
        data.append(wq)
    # the quads' opposite corners (smooth vertices only)
    Q = mesh.Q
    for k in range(4):
        p, q = Q[:, k], Q[:, (k + 2) % 4]
        rows.append(p)
        cols.append(q)
        data.append(np.where(smooth[p], 1.0 / den[p], 0.0))
    L = sp.csr_matrix((np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    L.sum_duplicates()
    return L


def subdivide(mesh: QuadMesh, sharp, levels, rule='chaikin', keep=False, to_limit=True):
    """semi-sharp subdivision: `levels` levels from the cage (sharp: dict of vertex pairs or a per-edge array). Returns the
    final QuadMesh (positions pushed onto the limit surface when to_limit and no edge is still sharp), its per-edge sharpness,
    each final quad's ancestor quad in the cage, and (keep) the list of per-level operators"""
    s_e, _, _ = sharpness_per_edge(mesh, sharp)
    cur = QuadMesh(mesh.V, mesh.Q)
    parent = np.arange(len(mesh.Q))
    ops = []
    for _ in range(levels):
        S, Q1, s_e = level(cur, s_e, rule)
        cur = QuadMesh(S @ cur.V, Q1)
        parent = np.repeat(parent, 4)
        if keep:
            ops.append(S)
    if to_limit:
        L = limit_matrix(cur, s_e)
        cur = QuadMesh(L @ cur.V, cur.Q)
    return cur, s_e, parent, ops


def limit_operator(mesh: QuadMesh, sharp, levels, rule='chaikin'):
    """A (n0 x n0, sparse): the limit positions of the cage's own vertices as a linear map of the cage's positions (the
    levels' operators composed right to left on the cage vertices' rows only, then the limit mask at the last level)"""
    s_e, _, _ = sharpness_per_edge(mesh, sharp)
    cur = QuadMesh(np.zeros((len(mesh.V), 3)), mesh.Q)
    ops = []
    for _ in range(levels):
        S, Q1, s_e = level(cur, s_e, rule)
        ops.append(S)
        cur = QuadMesh(np.zeros((S.shape[0], 3)), Q1)
    n0 = len(mesh.V)
    B = limit_matrix(cur, s_e)[:n0]
    for S in ops[::-1]:
        B = (B @ S).tocsr()
    return B, s_e


def fit_controls(mesh: QuadMesh, sharp, targets, levels, rule='chaikin', fixed=None):
    """the cage positions whose limit surface passes through `targets` (n0 x 3) at the cage's vertices: A V0 = T (A from
    limit_operator); fixed (bool n0, optional): vertices whose control positions are given by mesh.V instead (their
    targets ignored). Returns V0 and the residual's max"""
    A, _ = limit_operator(mesh, sharp, levels, rule)
    T = np.asarray(targets, np.float64)
    if fixed is None or not np.any(fixed):
        lu = spla.splu(A.tocsc())
        V0 = np.column_stack([lu.solve(T[:, k]) for k in range(3)])
    else:
        fr = np.nonzero(~fixed)[0]
        fx = np.nonzero(fixed)[0]
        Af = A[fr][:, fr].tocsc()
        rhs = T[fr] - A[fr][:, fx] @ mesh.V[fx]
        lu = spla.splu(Af)
        V0 = mesh.V.copy()
        V0[fr] = np.column_stack([lu.solve(rhs[:, k]) for k in range(3)])
    res = float(np.abs(A @ V0 - T).max()) if fixed is None else float(np.abs((A @ V0 - T)[~fixed]).max())
    return V0, res
