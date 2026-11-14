"""MESH OPERATIONS for the garments (triangle meshes; per-vertex attribute arrays carried through every op).

    edges(F) -> unique edges (e, 2); adjacency(F, n) -> neighbour lists
    components(F, n, barrier) -> label per vertex (flood fill over edges, barrier vertices not crossed)
    subdivide(V, F, A) -> midpoint 4-split, attributes averaged on each edge
    cut(V, F, f, A) -> the region f >= 0 with the iso-line made an exact boundary: crossings near a vertex (t < snap)
                       move that vertex onto the line, the rest split the triangle (no slivers under snap x the edge)
    boundary_loops(F) -> ordered closed loops of boundary vertices
    compact(V, F, A) -> unused vertices dropped
    laplacian(V, F) -> uniform umbrella operator (sparse)
"""
import numpy as np
import scipy.sparse as sp


def edges(F):
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    return np.unique(np.sort(E, axis=1), axis=0)


def adjacency(F, n):
    E = edges(F)
    A = sp.coo_matrix((np.ones(len(E) * 2), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()
    return A


def laplacian(V, F):
    A = adjacency(F, len(V))
    A.data[:] = 1.0
    d = np.asarray(A.sum(1)).ravel()
    return sp.diags(1.0 / np.maximum(d, 1)) @ A - sp.eye(len(V))


def components(F, n, barrier=None):
    E = edges(F)
    if barrier is not None:
        b = np.zeros(n, bool)
        b[np.asarray(barrier)] = True
        E = E[~(b[E[:, 0]] | b[E[:, 1]])]
    A = sp.coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(n, n))
    k, lab = sp.csgraph.connected_components(A, directed=False)
    return lab


def compact(V, F, A=None):
    used = np.unique(F)
    remap = -np.ones(len(V), np.int64)
    remap[used] = np.arange(len(used))
    out = (V[used], remap[F])
    if A is not None:
        out += ({k: v[used] for k, v in A.items()},)
    return out + (used,)


def subdivide(V, F, A=None):
    """midpoint 4-split; A: {name: (n, ...) array} averaged on edges (a categorical attribute should be carried as
    floats and rounded by the caller)"""
    E = edges(F)
    n = len(V)
    key = {(int(a), int(b)): n + i for i, (a, b) in enumerate(E)}
    V2 = np.concatenate([V, 0.5 * (V[E[:, 0]] + V[E[:, 1]])])

    def m(a, b):
        return key[(a, b) if a < b else (b, a)]
    F2 = []
    for a, b, c in F:
        ab, bc, ca = m(a, b), m(b, c), m(c, a)
        F2 += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
    F2 = np.array(F2, np.int64)
    A2 = None
    if A is not None:
        A2 = {k: np.concatenate([v, 0.5 * (v[E[:, 0]] + v[E[:, 1]])]) for k, v in A.items()}
    return V2, F2, A2


def cut(V, F, f, A=None, snap=0.22):
    """keep f >= 0; the iso-line f = 0 becomes the boundary"""
    V = V.copy()
    f = np.asarray(f, float).copy()
    A = {k: v.copy() for k, v in (A or {}).items()}
    # 1. snap: a crossing within snap of an edge end moves that end onto the line
    for _ in range(3):
        E = edges(F)
        fa, fb = f[E[:, 0]], f[E[:, 1]]
        cr = (fa >= 0) != (fb >= 0)
        if not cr.any():
            break
        Ec = E[cr]
        t = f[Ec[:, 0]] / (f[Ec[:, 0]] - f[Ec[:, 1]])
        moved = np.zeros(len(V), bool)
        V0, A0 = V.copy(), {k: v.copy() for k, v in A.items()}        # every crossing read off the pass's start
        for (a, b), tt in zip(Ec, t):
            if moved[a] or moved[b]:
                continue
            if tt < snap:
                v = a
            elif tt > 1 - snap:
                v = b
            else:
                continue
            V[v] = V0[a] + tt * (V0[b] - V0[a])
            for k in A:
                A[k][v] = A0[k][a] + tt * (A0[k][b] - A0[k][a])
            f[v] = 0.0
            moved[v] = True
        if not moved.any():
            break
    # 2. split the triangles the line still crosses
    newV, newA, newf = [], {k: [] for k in A}, []
    ekey = {}

    def xpt(a, b):
        k = (a, b) if a < b else (b, a)
        if k not in ekey:
            t = f[a] / (f[a] - f[b])
            if t <= 1e-9:
                return a
            if t >= 1 - 1e-9:
                return b
            ekey[k] = len(V) + len(newV)
            newV.append(V[a] + t * (V[b] - V[a]))
            for kk in A:
                newA[kk].append(A[kk][a] + t * (A[kk][b] - A[kk][a]))
            newf.append(0.0)
        return ekey[k]
    out = []
    pos = f >= 0
    for tri in F:
        s = pos[tri]
        if s.all():
            out.append(tri)
            continue
        if not s.any():
            continue
        # rotate so the odd one out is first
        for r in range(3):
            t3 = np.roll(tri, -r)
            s3 = pos[t3]
            if s3.sum() == 1 and s3[0]:
                a, b, c = t3
                # one inside: a, crossings on ab and ac (a zero-valued b or c counts as inside: skip none)
                out.append((a, xpt(a, b), xpt(a, c)))
                break
            if s3.sum() == 2 and not s3[0]:
                a, b, c = t3
                xab, xac = xpt(a, b), xpt(a, c)
                out += [(xab, b, c), (xab, c, xac)]
                break
    if newV:
        V = np.concatenate([V, np.array(newV)])
        f = np.concatenate([f, np.array(newf)])
        for k in A:
            A[k] = np.concatenate([A[k], np.array(newA[k])])
    F2 = np.array(out, np.int64)
    F2 = F2[(F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 2] != F2[:, 0])]
    F2 = F2[tri_area(V, F2) > 1e-12]
    V2, F2, A2, used = compact(V, F2, A)
    return V2, F2, A2, f[used]


def split_line(V, F, f, A=None, edge_ok=None, snap=0.2, fixed=None):
    """(B2b) the iso-line f = 0 inserted as an EDGE CHAIN, both sides kept (a seam between two panels, where cut() keeps
    one side): every edge the line crosses (edge_ok(a, b) true for its two vertex ids, if given) gets a vertex on it
    (or, within snap of an end, that end moves onto the line, unless it is `fixed` (an opening's rim)); every face is
    re-triangulated around its split edges (two split edges: 3 triangles; one: 2). Face labels by the field's sign are
    then exact: round 1's per-face labels left saw-toothed panel borders, and the seams' ridges drawn along them read
    as notches. Returns (V, F, A, f)."""
    V = V.copy()
    f = np.asarray(f, float).copy()
    f[np.abs(f) < 1e-9] = 0.0                    # already on the line (an earlier line's vertex): never a 0-length edge
    A = {k: v.copy() for k, v in (A or {}).items()}
    fx = np.zeros(len(V), bool) if fixed is None else np.asarray(fixed, bool).copy()

    def crossing(E):
        fa, fb = f[E[:, 0]], f[E[:, 1]]
        cr = ((fa > 0) & (fb < 0)) | ((fa < 0) & (fb > 0))
        if edge_ok is not None:
            cr &= edge_ok(E[:, 0], E[:, 1])
        return cr
    # 1. snap the near ends (read off the pass's start)
    E = edges(F)
    cr = crossing(E)
    Ec = E[cr]
    t = f[Ec[:, 0]] / (f[Ec[:, 0]] - f[Ec[:, 1]])
    V0, A0 = V.copy(), {k: v.copy() for k, v in A.items()}
    moved = np.zeros(len(V), bool)
    for (a, b), tt in zip(Ec, t):
        if moved[a] or moved[b]:
            continue
        # a fixed end moves too when the crossing is within 3 % of the edge of it (a sliver is worse than 0.3 mm)
        if tt < snap and (not fx[a] or tt < 0.03):
            v = a
        elif tt > 1 - snap and (not fx[b] or tt > 0.97):
            v = b
        else:
            continue
        V[v] = V0[a] + tt * (V0[b] - V0[a])
        for k in A:
            A[k][v] = A0[k][a] + tt * (A0[k][b] - A0[k][a])
        f[v] = 0.0
        moved[v] = True
    # 2. a vertex on every edge still crossed
    E = edges(F)
    cr = crossing(E)
    newid = {}
    newV, newA = [], {k: [] for k in A}
    for a, b in E[cr]:
        tt = f[a] / (f[a] - f[b])
        newid[(int(a), int(b))] = len(V) + len(newV)
        newV.append(V[a] + tt * (V[b] - V[a]))
        for k in A:
            newA[k].append(A[k][a] + tt * (A[k][b] - A[k][a]))
    if newV:
        V = np.concatenate([V, np.array(newV)])
        f = np.concatenate([f, np.zeros(len(newV))])
        for k in A:
            A[k] = np.concatenate([A[k], np.array(newA[k])])

    def mid(a, b):
        return newid.get((a, b) if a < b else (b, a))
    out = []
    for tri in F:
        a, b, c = (int(x) for x in tri)
        m = [mid(a, b), mid(b, c), mid(c, a)]
        n = sum(x is not None for x in m)
        if n == 0:
            out.append((a, b, c))
            continue
        # rotate so the pattern starts at edge 0
        for r in range(3):
            vv = (a, b, c)[r:] + (a, b, c)[:r]
            mm = m[r:] + m[:r]
            if n == 1 and mm[0] is not None:
                x = mm[0]
                out += [(vv[0], x, vv[2]), (x, vv[1], vv[2])]
                break
            if n == 2 and mm[0] is not None and mm[1] is not None:
                x, y_ = mm[0], mm[1]          # on (v0 v1) and (v1 v2): v1 alone on its side
                out += [(x, vv[1], y_), (vv[0], x, y_), (vv[0], y_, vv[2])]
                break
            if n == 3:
                x, y_, z = mm
                out += [(vv[0], x, z), (x, vv[1], y_), (z, y_, vv[2]), (x, y_, z)]
                break
    F2 = np.array(out, np.int64)
    F2 = F2[tri_area(V, F2) > 1e-14]
    return V, F2, A, f


def boundary_loops(F):
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    s = np.sort(E, axis=1)
    u, inv, cnt = np.unique(s, axis=0, return_inverse=True, return_counts=True)
    bd = E[cnt[inv.ravel()] == 1]              # directed boundary edges (the triangle's own orientation)
    nxt = {int(a): int(b) for a, b in bd}
    loops, seen = [], set()
    for a in list(nxt):
        if a in seen:
            continue
        loop, v = [], a
        while v not in seen and v in nxt:
            seen.add(v)
            loop.append(v)
            v = nxt[v]
        loops.append(np.array(loop, np.int64))
    return loops


def tri_area(V, F):
    return 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)


def closest_on_mesh(V, F, P):
    """closest points on the triangle mesh (V, F) to P (Warp BVH, CPU or GPU): (points, tri ids, bary (n, 3), signed
    distance by the face normal)"""
    import warp as wp
    wp.init()
    dev = 'cuda:0' if wp.is_cuda_available() else 'cpu'
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=dev))
    p = wp.array(np.asarray(P, np.float32), dtype=wp.vec3, device=dev)
    n = len(P)
    q = wp.zeros(n, wp.vec3, device=dev)
    tid = wp.zeros(n, wp.int32, device=dev)
    bc = wp.zeros(n, wp.vec3, device=dev)
    sd = wp.zeros(n, wp.float32, device=dev)
    wp.launch(_k_closest, dim=n, inputs=[m.id, p, q, tid, bc, sd], device=dev)
    return q.numpy().astype(np.float64), tid.numpy().astype(np.int64), bc.numpy().astype(np.float64), \
        sd.numpy().astype(np.float64)


def _kernels():
    import warp as wp

    @wp.kernel
    def k(mesh: wp.uint64, p: wp.array(dtype=wp.vec3), q: wp.array(dtype=wp.vec3), tid: wp.array(dtype=wp.int32),
          bc: wp.array(dtype=wp.vec3), sd: wp.array(dtype=wp.float32)):
        i = wp.tid()
        r = wp.mesh_query_point_sign_normal(mesh, p[i], 10.0)
        if r.result:
            c = wp.mesh_eval_position(mesh, r.face, r.u, r.v)
            q[i] = c
            tid[i] = r.face
            bc[i] = wp.vec3(r.u, r.v, 1.0 - r.u - r.v)
            sd[i] = r.sign * wp.length(p[i] - c)
    return k


_k_closest = _kernels()
