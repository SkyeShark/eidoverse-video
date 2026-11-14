"""H4 (the rig builder, 11-01; the lead's H4 brief, mesh items 2 and 3): THE LOW'S LOCAL ROWS. The shipped LOW is the
cage at its level-0 limit (h3_build): every vertex a cage vertex's limit point, ~18 mm apart on hm08's body. Where the
clay turns faster than that spacing the low chords it: the gluteal cleft (a slot ~10 mm wide and ~15 mm deep, its
walls spanned by one narrow quad a side, so the bake's rays fall back and the welded normal at its bottom faces straight
out of the slot), the front of the crotch (the clay's hollow between the genitocrural folds spanned by one 25 mm quad a
side) and the breast's outer rings (16 spokes, 20-30 mm apart round the inframammary fold: a polygonal silhouette in
close-ups). Probes: h4/rig_notes/probes p01-p04.

THE CLAY STAYS. The cage (identity's control) and the HIGH (the bake's surface, its level-4 limit cached in h3/high)
are untouched: only the LOW gains rows. Every new low vertex is a point of the cage's limit surface at a parametric
spot (parent quad, u, v): its position is the level-4 limit there (bilinear in the level-4 sub-quad, ~1 mm), so the
low still lies on the clay and stays LINEAR in the cage (dV_low = M dV_cage, HUMAN_PLAN §2.7: a row of M is the
bilinear weights times the level-4 limit operator's rows), and its UV is the parent quad's corner UVs at the same
(u, v): the H3b layout is kept, charts, pack, stack and mirror, nothing re-packed.

THE EDIT, offset_ring(S): a new vertex on every edge with exactly one end in the vertex set S (at t from the S end),
each quad touching S split by its template, so the mesh stays all quads and conforming (a quad has 0, 2 or 4 such
edges: a closed quad mesh admits no single-loop terminator, the parity of its faces' edge counts):
    2 crossed edges, opposite   PASS   (s1 s2 M2 M1) (M1 M2 c d)                       no pole
    2 crossed edges, adjacent   CORNER (k N X M) (N . . X) (X . . M) round their shared corner k: X a 3-pole, the
                                       corner opposite k a 5-pole (k in S: S's chain ends; k outside: a turn)
    4 crossed edges             CROSS  four quads round a centre X (two diagonal corners in S)
So the offset ring round a vertex chain is a closed loop at half the spacing on both sides of it, its two ends closed by
corner pairs: round the back midline it gives each wall of the cleft a row and the crotch's hollow its columns, round
every other spoke of the breast it doubles the spokes. Several rings apply in turn, each on the last one's output.

    offset_ring(Q, par, cuv, S, t=0.5) -> (Q, par, cuv, new)       (new: [(id, key, kind, parent quad, (u, v))])
    LimitEval(V4, Q4, par4, levels=4).at(p, u, v)                    the level-4 limit at a HIGH quad's (u, v)
    low_to_high_quads(Q, Q_high, hid)                                each LOW quad's HIGH quad and corner order
"""
import collections

import numpy as np

VERSION = 'h4-lowref-1'


def _edge(a, b):
    return (a, b) if a < b else (b, a)


def offset_ring(Q, par, cuv, S, t=0.5, n_vertices=None, edge_t=None):
    """the offset loop round the vertex set S (module docstring). Q (m, 4) quads; par (m,) each quad's ORIGINAL parent;
    cuv (m, 4, 2) each corner's (u, v) in its parent; S a set of vertex ids. A new vertex on every edge (a, b) with a in
    S, b not, at t from a (edge_t: {(a, b): t} per edge, a the S end); new ids from n_vertices up. Returns (Q2, par2,
    cuv2, new) where a split quad keeps its index for its first child (the others appended) and new = [(id, key, kind,
    parent, (u, v))]: key ('e', a, b) a on S, or ('x', the quad's corner ids in order) for a template's inner vertex"""
    Q = np.asarray(Q, np.int64)
    S = set(int(v) for v in S)
    n0 = int(Q.max()) + 1 if n_vertices is None else int(n_vertices)
    nxt = [n0]
    new = []
    evert = {}

    def ev(a, b, pq, ua, ub):
        """the edge (a, b) vertex (a in S), created once; its (u, v) in quad pq from the corners' (ua, ub)"""
        key = _edge(a, b)
        tt = t if edge_t is None else edge_t.get((a, b), t)
        uv = (1.0 - tt) * np.asarray(ua) + tt * np.asarray(ub)
        if key not in evert:
            evert[key] = nxt[0]
            new.append((nxt[0], ('e', a, b), 'edge', int(par[pq]), tuple(float(x) for x in uv)))
            nxt[0] += 1
        return evert[key], uv

    def xv(pq, uv):
        vid = nxt[0]
        new.append((vid, ('x',) + tuple(int(v) for v in Q[pq]), 'inner', int(par[pq]), tuple(float(x) for x in uv)))
        nxt[0] += 1
        return vid

    Q2 = [tuple(int(v) for v in q) for q in Q]
    par2 = list(int(p) for p in par)
    cuv2 = [np.asarray(c, np.float64).copy() for c in cuv]
    for qi in range(len(Q)):
        q = [int(v) for v in Q[qi]]
        ins = [v in S for v in q]
        cr = [ins[k] != ins[(k + 1) % 4] for k in range(4)]          # edge k = (q[k], q[k+1]) crossed
        nc = sum(cr)
        if nc == 0:
            continue
        C = cuv[qi]
        mids = {}
        for k in range(4):
            if cr[k]:
                a, b = q[k], q[(k + 1) % 4]
                ka, kb = k, (k + 1) % 4
                if not ins[ka]:
                    a, b, ka, kb = b, a, kb, ka                       # a is the S end
                vid, uv = ev(a, b, qi, C[ka], C[kb])
                mids[k] = (vid, uv)
        kids = []
        if nc == 2:
            ks = [k for k in range(4) if cr[k]]
            if (ks[1] - ks[0]) % 4 == 2:
                # PASS: rotate so the crossed edges are 1 (q1 q2) and 3 (q3 q0)
                r = (ks[0] - 1) % 4
                qq = [q[(j + r) % 4] for j in range(4)]
                cc = [C[(j + r) % 4] for j in range(4)]
                m1, u1 = mids[(1 + r) % 4]
                m3, u3 = mids[(3 + r) % 4]
                kids = [((qq[0], qq[1], m1, m3), (cc[0], cc[1], u1, u3)),
                        ((m3, m1, qq[2], qq[3]), (u3, u1, cc[2], cc[3]))]
            else:
                # CORNER round the shared corner k: crossed edges (k-1, k) and (k, k+1) in corner terms
                kc = ks[1] if (ks[1] - ks[0]) % 4 == 1 else ks[0]       # the edge index starting at the shared corner
                # shared corner = q[kc]; its edges: (q[kc], q[kc+1]) = edge kc and (q[kc-1], q[kc]) = edge kc-1
                r = kc
                qq = [q[(j + r) % 4] for j in range(4)]                 # qq[0] the shared corner
                cc = [C[(j + r) % 4] for j in range(4)]
                mN, uN = mids[r % 4]                                   # on (qq0, qq1)
                mM, uM = mids[(r - 1) % 4]                             # on (qq3, qq0)
                # X: the parallelogram's fourth corner on (k, N, ., M) (the quad's centre for t = 0.5 on a square: the
                # small quad at k is t x t), pulled 30 % toward the corners' centroid so it stays inside a skewed child
                uX = 0.7 * (np.asarray(uN) + np.asarray(uM) - np.asarray(cc[0])) + 0.3 * np.mean(np.asarray(cc), 0)
                X = xv(qi, uX)
                kids = [((qq[0], mN, X, mM), (cc[0], uN, uX, uM)),
                        ((mN, qq[1], qq[2], X), (uN, cc[1], cc[2], uX)),
                        ((X, qq[2], qq[3], mM), (uX, cc[2], cc[3], uM))]
        elif nc == 4:
            uv0, uv1, uv2, uv3 = (np.asarray(mids[k][1]) for k in range(4))
            uX = 0.25 * (uv0 + uv1 + uv2 + uv3)
            X = xv(qi, uX)
            m = [mids[k][0] for k in range(4)]
            u = [np.asarray(mids[k][1]) for k in range(4)]
            kids = [((q[0], m[0], X, m[3]), (C[0], u[0], uX, u[3])),
                    ((m[0], q[1], m[1], X), (u[0], C[1], u[1], uX)),
                    ((X, m[1], q[2], m[2]), (uX, u[1], C[2], u[2])),
                    ((m[3], X, m[2], q[3]), (u[3], uX, u[2], C[3]))]
        else:
            raise AssertionError(f'quad {qi} has {nc} crossed edges')
        for j, (qq_, cc_) in enumerate(kids):
            arr = np.array([np.asarray(x, np.float64) for x in cc_])
            if j == 0:
                Q2[qi] = tuple(int(v) for v in qq_)
                cuv2[qi] = arr
            else:
                Q2.append(tuple(int(v) for v in qq_))
                par2.append(int(par[qi]))
                cuv2.append(arr)
    return np.array(Q2, np.int64), np.array(par2, np.int64), np.array(cuv2), new


def subquad_params(levels=4):
    """the (u, v) of each level-L sub-quad's corners in its cage quad, in subdiv_sharp's layout (quad (v0 v1 v2 v3) ->
    (v0 e01 f e30), (v1 e12 f e01), (v2 e23 f e12), (v3 e30 f e23), children of one parent adjacent): (4^L, 4, 2)"""
    quads = [np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])]
    for _ in range(levels):
        nxt = []
        for P in quads:
            P0, P1, P2, P3 = P
            e01, e12, e23, e30 = (P0 + P1) / 2, (P1 + P2) / 2, (P2 + P3) / 2, (P3 + P0) / 2
            f = (P0 + P1 + P2 + P3) / 4
            nxt += [np.array([P0, e01, f, e30]), np.array([P1, e12, f, e01]), np.array([P2, e23, f, e12]),
                    np.array([P3, e30, f, e23])]
        quads = nxt
    return np.array(quads)


class LimitEval:
    """the level-L limit mesh (V4, Q4, par4: subdiv_sharp.subdivide's, children of one cage quad contiguous in its
    recursive layout) evaluated at a cage quad's (u, v): the bilinear blend of the sub-quad holding (u, v)"""

    def __init__(self, V4, Q4, par4, levels=4):
        self.V4, self.Q4 = np.asarray(V4, np.float64), np.asarray(Q4, np.int64)
        self.L = levels
        self.n = 2 ** levels
        self.T = subquad_params(levels)
        nsub = len(self.T)
        assert len(self.Q4) % nsub == 0
        assert (np.asarray(par4)[::nsub] == np.arange(len(self.Q4) // nsub)).all(), 'the limit mesh is not in layout order'
        lo = self.T.min(1)
        self.cell = np.zeros((self.n, self.n), np.int64)
        idx = np.floor(lo * self.n + 0.5).astype(np.int64)
        self.cell[idx[:, 0], idx[:, 1]] = np.arange(nsub)

    def at(self, p, u, v):
        p = np.atleast_1d(np.asarray(p, np.int64))
        u = np.clip(np.atleast_1d(np.asarray(u, np.float64)), 0.0, 1.0)
        v = np.clip(np.atleast_1d(np.asarray(v, np.float64)), 0.0, 1.0)
        i = np.minimum((u * self.n).astype(np.int64), self.n - 1)
        j = np.minimum((v * self.n).astype(np.int64), self.n - 1)
        k = self.cell[i, j]
        T = self.T[k]                                         # (n, 4, 2)
        w = np.clip(1.0 - np.abs(u[:, None] - T[:, :, 0]) * self.n, 0.0, 1.0) * \
            np.clip(1.0 - np.abs(v[:, None] - T[:, :, 1]) * self.n, 0.0, 1.0)
        w /= np.maximum(w.sum(1, keepdims=True), 1e-12)
        sub = p * len(self.T) + k
        P = self.V4[self.Q4[sub]]                             # (n, 4, 3)
        return np.einsum('nk,nkd->nd', w, P), sub, w


def low_to_high_quads(Q, Q_high, hid):
    """each LOW quad's HIGH quad (or -1) and, per LOW corner, the HIGH corner index holding it (hid: LOW vertex -> HIGH
    vertex, -1 where the LOW has no twin)"""
    key = {frozenset(int(v) for v in q): i for i, q in enumerate(np.asarray(Q_high).tolist())}
    hq = -np.ones(len(Q), np.int64)
    corner = -np.ones((len(Q), 4), np.int64)
    for i, q in enumerate(np.asarray(Q).tolist()):
        hv = [int(hid[v]) for v in q]
        if min(hv) < 0:
            continue
        j = key.get(frozenset(hv))
        if j is None:
            continue
        hq[i] = j
        hqv = list(Q_high[j])
        corner[i] = [hqv.index(h) for h in hv]
    return hq, corner


PARAM = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])


def to_high_uv(uv, corner):
    """a LOW quad's (u, v) (n, 2) to its HIGH quad's frame: the square's symmetry taking LOW corner k to the HIGH corner
    corner[k] (bilinear in the corner images, exact for an affine map)"""
    uv = np.atleast_2d(uv)
    u, v = uv[:, 0], uv[:, 1]
    w = np.column_stack([(1 - u) * (1 - v), u * (1 - v), u * v, (1 - u) * v])
    return w @ PARAM[np.asarray(corner)]


def chain_along_midline(V, Q, mir, start, stop_fn, step_fn=None):
    """the midline vertex chain from start: each step the midline neighbour (mir[w] == w) not yet taken that step_fn
    prefers (default: the lower one); stops when stop_fn(vertex) is true (that vertex excluded)"""
    nbr = collections.defaultdict(set)
    for q in np.asarray(Q).tolist():
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            nbr[a].add(b)
            nbr[b].add(a)
    out = [int(start)]
    while True:
        c = out[-1]
        cand = [w for w in nbr[c] if mir[w] == w and w not in out]
        if not cand:
            break
        w = min(cand, key=lambda x: V[x, 1]) if step_fn is None else step_fn(out, cand)
        if stop_fn(w):
            break
        out.append(int(w))
    return out
