"""Ring lofts, quad-grid caps and port bridges: the designed topology of every organic cage.

A TUBE is rings of K vertices at stations along a curve: ring i, vertex k sits at c_i + r_i(theta_k) (cos theta_k n_i
+ sin theta_k b_i), the frame (n, b, t) right-handed (n x b = t) and rotation-minimizing along the curve, rolled to an
optional reference direction (theta = 0 points along it: an arm's aboral side, a body's back). Quads
(i,k) (i,k+1) (i+1,k+1) (i+1,k) wind counter-clockwise seen from outside.

Every vertex carries anatomical attributes (subdivision-safe: no wrapping values): 'part' one-hot over the creature's
regions, 'st' = (s, cos theta, sin theta, side) with s the normalized arclength along its own chain.

A CAP closes a ring of K = 4s with an s x s quad grid (a Coons patch over the ring, domed along the axis): no fans, no
poles at the tip. A PORT removes a block of faces from a tube's grid and bridges its boundary loop to another tube's
root ring through fillet rings: 2(a+b) boundary edges for an a x b block.
"""
import numpy as np

from .mesh import QuadMesh


def rmf(points, ref=None):
    """rotation-minimizing frames (double reflection, Wang et al. 2008) along a polyline: (n, b, t) per point, n rolled
    so the first frame's n points along ref (projected off the tangent); returns three (N, 3) arrays"""
    P = np.asarray(points, np.float64)
    N = len(P)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    if ref is None:
        ref = np.array([0.0, 1.0, 0.0]) if abs(T[0, 1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    r0 = np.asarray(ref, np.float64) - np.dot(ref, T[0]) * T[0]
    r0 /= np.linalg.norm(r0)
    R = np.zeros_like(P)
    R[0] = r0
    for i in range(N - 1):
        v1 = P[i + 1] - P[i]
        c1 = v1 @ v1
        if c1 < 1e-24:
            R[i + 1] = R[i]
            continue
        rL = R[i] - (2.0 / c1) * (v1 @ R[i]) * v1
        tL = T[i] - (2.0 / c1) * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        R[i + 1] = rL - (2.0 / c2) * (v2 @ rL) * v2 if c2 > 1e-24 else rL
        R[i + 1] -= (R[i + 1] @ T[i + 1]) * T[i + 1]
        R[i + 1] /= np.linalg.norm(R[i + 1])
    B = np.cross(T, R)                  # n x b = t  with n = R:  b = t x n
    return R, B, T


def resample(points, count):
    """count points evenly by arclength along a Catmull-Rom spline through the control points"""
    P = np.asarray(points, np.float64)
    if len(P) == 2:
        t = np.linspace(0, 1, count)[:, None]
        return P[0] * (1 - t) + P[1] * t
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    dense = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = Q[i], Q[i + 1], Q[i + 2], Q[i + 3]
        for u in np.linspace(0, 1, 64, endpoint=False):
            u2, u3 = u * u, u * u * u
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2
                                + (-p0 + 3 * p1 - 3 * p2 + p3) * u3))
    dense.append(P[-1])
    D = np.array(dense)
    seg = np.linalg.norm(np.diff(D, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    st = np.linspace(0, s[-1], count)
    return np.column_stack([np.interp(st, s, D[:, k]) for k in range(3)])


class Tube:
    """rings[i, k] = vertex id; the mesh (V, Q, attrs) before welding with neighbours"""

    def __init__(self, centers, K, radius, ref=None, part=0, n_parts=1, side=0.0, s_range=(0.0, 1.0),
                 theta0=0.0):
        """radius(i, s, theta) -> r (vectorized over theta arrays); centers (N, 3)"""
        C = np.asarray(centers, np.float64)
        self.K = K
        self.N = len(C)
        n, b, t = rmf(C, ref)
        self.frames = (n, b, t)
        self.centers = C
        seg = np.linalg.norm(np.diff(C, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        s = s / max(s[-1], 1e-12)
        s = s_range[0] + s * (s_range[1] - s_range[0])
        self.s = s
        th = theta0 + np.arange(K) * (2 * np.pi / K)
        self.theta = th
        V = np.zeros((self.N, K, 3))
        for i in range(self.N):
            r = np.broadcast_to(radius(i, s[i], th), th.shape)
            V[i] = C[i] + r[:, None] * (np.cos(th)[:, None] * n[i] + np.sin(th)[:, None] * b[i])
        self.rings = np.arange(self.N * K).reshape(self.N, K)
        i = np.arange(self.N - 1)[:, None]
        k = np.arange(K)[None, :]
        k1 = (k + 1) % K
        Q = np.stack([self.rings[i, k], self.rings[i, k1], self.rings[i + 1, k1], self.rings[i + 1, k]], -1)
        onehot = np.zeros((self.N * K, n_parts))
        onehot[:, part] = 1.0
        st = np.column_stack([np.repeat(s, K), np.tile(np.cos(th), self.N), np.tile(np.sin(th), self.N),
                              np.full(self.N * K, side)])
        self.mesh = QuadMesh(V.reshape(-1, 3), Q.reshape(-1, 4), {'part': onehot, 'st': st})


def grid_boundary(s, t=None):
    """the (i, j) cells of an (s+1) x (t+1) grid's boundary loop, counter-clockwise in (i, j): 2(s+t) entries"""
    t = s if t is None else t
    loop = [(0, j) for j in range(t)] + [(i, t) for i in range(s)] + [(s, j) for j in range(t, 0, -1)] + \
           [(i, 0) for i in range(s, 0, -1)]
    return loop


def cap(mesh: QuadMesh, ring, axis, dome=0.0, flip=False, shape=None):
    """close the ring (K = 2(s+t) vertex ids, in loop order) with an s x t quad grid (square s = t = K/4 by default):
    interior points by a Coons patch over the ring, lifted dome * (1 - rho^2) along axis (rho the normalized distance
    from the centre). Returns the new mesh and the grid's vertex ids (s+1, t+1). The winding is the one whose normals
    face along axis."""
    K = len(ring)
    if shape is None:
        assert K % 4 == 0, K
        s = t = K // 4
    else:
        s, t = shape
        assert 2 * (s + t) == K, (K, shape)
    loop = grid_boundary(s, t)
    G = -np.ones((s + 1, t + 1), np.int64)
    for kk, (i, j) in enumerate(loop):
        G[i, j] = ring[kk]
    V = mesh.V
    # Coons patch: the four boundary curves as functions of the grid parameter
    def bpos(i, j):
        return V[G[i, j]]
    newV, attr_new = [], {k: [] for k in mesh.attrs}
    nid = len(V)
    axis = np.asarray(axis, np.float64)
    axis = axis / np.linalg.norm(axis)
    for i in range(1, s):
        for j in range(1, t):
            u, v = i / s, j / t
            p = ((1 - v) * bpos(i, 0) + v * bpos(i, t) + (1 - u) * bpos(0, j) + u * bpos(s, j)
                 - ((1 - u) * (1 - v) * bpos(0, 0) + u * (1 - v) * bpos(s, 0) + (1 - u) * v * bpos(0, t)
                    + u * v * bpos(s, t)))
            rho2 = ((2 * u - 1) ** 2 + (2 * v - 1) ** 2) / 2.0
            p = p + axis * dome * (1 - rho2)
            newV.append(p)
            # attributes: the same Coons blend of the boundary's values
            for k, a in mesh.attrs.items():
                ga = lambda ii, jj: a[G[ii, jj]]
                attr_new[k].append((1 - v) * ga(i, 0) + v * ga(i, t) + (1 - u) * ga(0, j) + u * ga(s, j)
                                   - ((1 - u) * (1 - v) * ga(0, 0) + u * (1 - v) * ga(s, 0) + (1 - u) * v * ga(0, t)
                                      + u * v * ga(s, t)))
            G[i, j] = nid
            nid += 1
    Qc = []
    for i in range(s):
        for j in range(t):
            q = [G[i, j], G[i + 1, j], G[i + 1, j + 1], G[i, j + 1]]
            Qc.append(q[::-1] if flip else q)
    Vn = np.vstack([V] + ([np.array(newV)] if newV else []))
    attrs = {k: np.vstack([a] + ([np.array(attr_new[k])] if attr_new[k] else [])) for k, a in mesh.attrs.items()}
    out = QuadMesh(Vn, np.vstack([mesh.Q, np.array(Qc)]), attrs)
    # the winding: TOPOLOGICAL (the ring's edges run opposite to the faces already using them), the axis only lifts
    # the dome; with no existing faces on the ring, the one whose normals face along axis
    ringset = set(int(x) for x in ring)
    d = np.stack([mesh.Q, np.roll(mesh.Q, -1, axis=1)], -1).reshape(-1, 2)
    existing = {(int(a), int(b)) for a, b in d if int(a) in ringset and int(b) in ringset}
    Qa = np.array(Qc)
    dc = np.stack([Qa, np.roll(Qa, -1, axis=1)], -1).reshape(-1, 2)
    if existing:
        clash = any((int(a), int(b)) in existing for a, b in dc)
        if clash and not flip:
            return cap(mesh, ring, axis, dome, flip=True, shape=shape)
        return out, G
    fn = out.face_normals()[len(mesh.Q):]
    if (fn @ axis).sum() < 0 and not flip:
        return cap(mesh, ring, axis, dome, flip=True, shape=shape)
    return out, G


def reduce_ring(mesh: QuadMesh, ring, inner_pos, mid_pull=0.5):
    """a 4 -> 2 REDUCTION strip after `ring` (K vertex ids, K % 4 == 0, the far ring of the tube it ends: its faces
    use its edges backward): per unit of four outer edges o0..o4 and two inner i0 i1 i2, one middle vertex m and four
    quads (o0 o1 m i0) (o1 o2 o3 m) (o3 o4 i2 m) (i0 m i2 i1), all quads, every inner edge twice and opposed. The inner
    ring (K/2, positions inner_pos) keeps the outer ring's orientation, so strips chain and caps close them. m sits
    mid_pull of the way from o2 toward i1. Returns the mesh and the inner ring's ids."""
    R = np.asarray(ring)
    K = len(R)
    assert K % 4 == 0, K
    n0 = len(mesh.V)
    K2 = K // 2
    inner = np.arange(n0, n0 + K2)
    mids = np.arange(n0 + K2, n0 + K2 + K // 4)
    Vin = np.asarray(inner_pos, np.float64).reshape(K2, 3)
    Vm = np.zeros((K // 4, 3))
    attrs_in = {k: np.zeros((K2, a.shape[1])) for k, a in mesh.attrs.items()}
    attrs_m = {k: np.zeros((K // 4, a.shape[1])) for k, a in mesh.attrs.items()}
    Q = []
    for u in range(K // 4):
        o = [R[(4 * u + j) % K] for j in range(5)]
        i0, i1, i2 = inner[(2 * u) % K2], inner[(2 * u + 1) % K2], inner[(2 * u + 2) % K2]
        m = mids[u]
        Vm[u] = mesh.V[o[2]] * (1 - mid_pull) + Vin[2 * u + 1] * mid_pull
        Q += [[o[0], o[1], m, i0], [o[1], o[2], o[3], m], [o[3], o[4], i2, m], [i0, m, i2, i1]]
        for k, a in mesh.attrs.items():
            attrs_m[k][u] = 0.5 * (a[o[2]] + a[o[1]] * 0.5 + a[o[3]] * 0.5)
    for j in range(K2):
        for k, a in mesh.attrs.items():
            attrs_in[k][j] = a[R[(2 * j) % K]]
    V = np.vstack([mesh.V, Vin, Vm])
    attrs = {k: np.vstack([a, attrs_in[k], attrs_m[k]]) for k, a in mesh.attrs.items()}
    return QuadMesh(V, np.vstack([mesh.Q, np.array(Q)]), attrs), inner


def boundary_loop(mesh: QuadMesh, start=None):
    """the ordered boundary loops of an open mesh (each a vertex id list, oriented like the faces' winding)"""
    d = np.stack([mesh.Q, np.roll(mesh.Q, -1, axis=1)], -1).reshape(-1, 2)
    key = {(a, b) for a, b in d}
    nxt = {}
    for a, b in d:
        if (b, a) not in key:          # a directed edge with no twin is on a boundary
            nxt[a] = b
    loops, seen = [], set()
    for a in list(nxt):
        if a in seen:
            continue
        loop = [a]
        seen.add(a)
        b = nxt[a]
        while b != a:
            loop.append(b)
            seen.add(b)
            b = nxt[b]
        loops.append(loop)
    return loops


def remove_faces(mesh: QuadMesh, face_ids):
    keep = np.ones(len(mesh.Q), bool)
    keep[np.asarray(face_ids, np.int64)] = False
    return QuadMesh(mesh.V, mesh.Q[keep], mesh.attrs)


def bridge(mesh: QuadMesh, loop_a, loop_b, rings=2, shape=None):
    """join two vertex loops of equal length with `rings` intermediate rings of quads. loop_a must run the way its
    faces' boundary runs (boundary_loop order); loop_b is aligned to it by the cyclic shift and direction minimising
    the summed vertex distance. Intermediate points: Hermite-like blend p(u) = (1-h)A + hB + shape(u, A, B), h the
    smoothstep of u. Attributes blend linearly."""
    A = np.asarray(loop_a)
    B = np.asarray(loop_b)
    assert len(A) == len(B), (len(A), len(B))
    K = len(A)
    V = mesh.V
    best = None
    for direction in (1, -1):
        Bd = B[::direction]
        for sh in range(K):
            Bs = np.roll(Bd, -sh)
            cost = np.linalg.norm(V[A] - V[Bs], axis=1).sum()
            if best is None or cost < best[0]:
                best = (cost, Bs)
    Bs = best[1]
    ids = [A]
    newV = []
    attrs_new = {k: [] for k in mesh.attrs}
    nid = len(V)
    for r in range(1, rings + 1):
        u = r / (rings + 1)
        h = u * u * (3 - 2 * u)
        P = (1 - h) * V[A] + h * V[Bs]
        if shape is not None:
            P = P + shape(u, V[A], V[Bs])
        newV.append(P)
        for k, a in mesh.attrs.items():
            attrs_new[k].append((1 - u) * a[A] + u * a[Bs])
        ids.append(np.arange(nid, nid + K))
        nid += K
    ids.append(Bs)
    Qn = []
    for r in range(len(ids) - 1):
        a, b = ids[r], ids[r + 1]
        for k in range(K):
            k1 = (k + 1) % K
            # loop_a runs with its faces, so the bridge faces run against it: (a[k1], a[k], b[k], b[k1])
            Qn.append([a[k1], a[k], b[k], b[k1]])
    Vn = np.vstack([V] + newV) if newV else V
    attrs = {k: np.vstack([a] + attrs_new[k]) if attrs_new[k] else a for k, a in mesh.attrs.items()}
    return QuadMesh(Vn, np.vstack([mesh.Q, np.array(Qn)]), attrs), ids
