"""Catmull-Clark subdivision of a pure-quad mesh as one sparse matrix per level (scipy), so positions AND every
per-vertex attribute ride through with the same operator: V1 = S @ V0, A1 = S @ A0.

New vertex layout per level: [vertex points (n), edge points (E), face points (m)]. Each quad (v0 v1 v2 v3) with
edges e01 e12 e23 e30 and face point f becomes (v0 e01 f e30), (v1 e12 f e01), (v2 e23 f e12), (v3 e30 f e23), all
counter-clockwise like their parent.

Rules: interior edge (v0 + v1 + fa + fb) / 4; boundary edge the midpoint (a crease); interior vertex of valence n
(n-2)/n P + sum(u)/n^2 + sum(f)/n^2; boundary vertex 3/4 P + 1/8 (u0 + u1); a boundary corner (two boundary edges, one
face) stays put.

CREASES (sharp edges inside the surface: a web's rim, a fin's edge, where two sheets of a thin membrane meet): a crease
edge takes the boundary rules: its edge point the midpoint; a vertex on exactly two crease edges the curve rule
3/4 P + 1/8 (u0 + u1); on three or more a corner (stays); on one, smooth (a dart). Each crease edge splits into two
crease edges at the next level. Without them the limit surface pulls a membrane's rim back inside the membrane and
projection drops points through the far face (t05's web margins).
"""
import numpy as np
import scipy.sparse as sp

from .mesh import QuadMesh


def level(mesh: QuadMesh, creases=None):
    """one Catmull-Clark level; creases: (c, 2) vertex pairs (sharp edges) or None. Returns S, the new quads and the
    new crease pairs"""
    n, m = len(mesh.V), len(mesh.Q)
    E, QE = mesh.edges()
    nE = len(E)
    ef = mesh.edge_faces(E, QE)
    boundary_e = ef[:, 1] < 0
    crease_e = np.zeros(nE, bool)
    if creases is not None and len(creases):
        key = {(min(a, b), max(a, b)): i for i, (a, b) in enumerate(E.tolist())}
        for a, b in np.asarray(creases).tolist():
            i = key.get((min(a, b), max(a, b)))
            if i is not None:
                crease_e[i] = True
    sharp_e = boundary_e | crease_e         # crease edges take the boundary rules
    # face points: the corners' mean
    rows = np.repeat(np.arange(m), 4)
    Sf = sp.csr_matrix((np.full(4 * m, 0.25), (rows, mesh.Q.ravel())), shape=(m, n))
    # edge points
    ri = np.repeat(np.arange(nE), 2)
    wv = np.where(np.repeat(sharp_e, 2), 0.5, 0.25)
    Aev = sp.csr_matrix((wv, (ri, E.ravel())), shape=(nE, n))
    inter = np.nonzero(~sharp_e)[0]
    Aef = sp.csr_matrix((np.full(2 * len(inter), 0.25), (np.repeat(inter, 2), ef[inter].ravel())), shape=(nE, m))
    Se = Aev + Aef @ Sf
    # vertex points
    val = np.bincount(E.ravel(), minlength=n).astype(np.float64)          # edges per vertex
    bcount = np.bincount(E[sharp_e].ravel(), minlength=n)                 # sharp (boundary or crease) edges per vertex
    fval = np.bincount(mesh.Q.ravel(), minlength=n).astype(np.float64)    # faces per vertex
    on_boundary = np.bincount(E[boundary_e].ravel(), minlength=n) > 0
    # the vertex rules: smooth (0 or 1 sharp edges: a dart is smooth), crease/boundary curve (exactly 2), corner (3+,
    # or a boundary corner with one face)
    is_b = bcount == 2
    corner = (bcount >= 3) | (on_boundary & (fval == 1) & (bcount == 2) & (val == 2))
    is_b = is_b & ~corner
    smooth = ~is_b & ~corner
    # interior: (n-2)/n P + sum u / n^2 + sum f / n^2
    nn = np.maximum(val, 1.0)
    diag = np.where(smooth, (nn - 2.0) / nn, np.where(corner, 1.0, 0.75))
    # neighbours through edges
    a, b = E[:, 0], E[:, 1]
    w_int_a = np.where(smooth[a], 1.0 / nn[a] ** 2, 0.0)
    w_int_b = np.where(smooth[b], 1.0 / nn[b] ** 2, 0.0)
    # curve-rule vertices take only their sharp neighbours, 1/8 each (corners none)
    w_bnd_a = np.where(is_b[a] & sharp_e, 0.125, 0.0)
    w_bnd_b = np.where(is_b[b] & sharp_e, 0.125, 0.0)
    Avu = sp.csr_matrix((np.concatenate([w_int_a + w_bnd_a, w_int_b + w_bnd_b]),
                         (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(n, n))
    # faces around smooth vertices: sum f / n^2
    fr = mesh.Q.ravel()
    wf = np.where(smooth[fr], 1.0 / nn[fr] ** 2, 0.0)
    Avf = sp.csr_matrix((wf, (fr, np.repeat(np.arange(m), 4))), shape=(n, m))
    Sv = sp.diags(diag) + Avu + Avf @ Sf
    S = sp.vstack([Sv, Se, Sf]).tocsr()
    # new topology
    v = mesh.Q
    e = QE + n
    f = (np.arange(m) + n + nE)[:, None]
    Q1 = np.concatenate([
        np.column_stack([v[:, 0], e[:, 0], f[:, 0], e[:, 3]]),
        np.column_stack([v[:, 1], e[:, 1], f[:, 0], e[:, 0]]),
        np.column_stack([v[:, 2], e[:, 2], f[:, 0], e[:, 1]]),
        np.column_stack([v[:, 3], e[:, 3], f[:, 0], e[:, 2]])])
    # keep children of one parent adjacent (quad f's four children at 4f..4f+3): parent ids stay recoverable
    order = np.arange(4 * m).reshape(4, m).T.ravel()
    Q1 = Q1[order]
    # the crease edges' halves (vertex a - its edge point - vertex b)
    ce = np.nonzero(crease_e)[0]
    new_creases = np.concatenate([np.column_stack([E[ce, 0], ce + n]), np.column_stack([ce + n, E[ce, 1]])]) \
        if len(ce) else np.zeros((0, 2), np.int64)
    return S, Q1, new_creases


def subdivide(mesh: QuadMesh, levels=1, keep_matrix=False, creases=None):
    """returns the subdivided mesh (attributes carried; the crease pairs of the last level in attrs-free form as
    mesh.creases) and, if asked, the composed operator from the input's vertices (sparse, (n_out, n_in)), and each
    output quad's ancestor quad in the input"""
    cur = mesh
    Stot = None
    parent = np.arange(len(mesh.Q))
    cr = creases
    for _ in range(levels):
        S, Q1, cr = level(cur, cr)
        V1 = S @ cur.V
        A1 = {k: S @ v for k, v in cur.attrs.items()}
        parent = np.repeat(parent, 4)
        cur = QuadMesh(V1, Q1, A1)
        if keep_matrix:
            Stot = S if Stot is None else S @ Stot
    cur.creases = cr
    if keep_matrix:
        return cur, Stot, parent
    return cur, parent
