"""UVs for a cage (numpy + scipy sparse): seams -> islands -> LSCM -> ARAP -> one texel density -> packed.

  islands(Q, seams)          faces joined across every edge that is not a seam (or a boundary); returns a face label
  split(V, Q, label)         each island its own vertices (seam vertices duplicated per island side): per-corner
                             indices into a new vertex list, plus each new vertex's original id
  lscm(V, F, pin)            the least-squares conformal map of a disk-like triangle island (2 pinned vertices)
  arap(V, F, UV, iters)      as-rigid-as-possible refinement (local SVD fits, global sparse solve): conformal maps
                             shrink far regions; ARAP evens the area so one texel density holds across the island
  pack(islands, size, pad)   islands scaled to one density (3D area), rotated 0/90, placed by a skyline packer
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.sparse.csgraph import connected_components


def islands(Q, seams):
    """face labels: quads joined through shared edges that are not seams"""
    m = len(Q)
    d = np.stack([Q, np.roll(Q, -1, axis=1)], -1).reshape(-1, 2)
    key = np.sort(d, axis=1)
    fid = np.repeat(np.arange(m), 4)
    seam = set()
    for a, b in np.asarray(seams).reshape(-1, 2).tolist():
        seam.add((min(a, b), max(a, b)))
    E, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    is_seam = np.array([(int(a), int(b)) in seam for a, b in E])
    order = np.argsort(inv, kind='stable')
    ie, ff = inv[order], fid[order]
    rows, cols = [], []
    i = 0
    while i < len(ie):
        j = i
        while j + 1 < len(ie) and ie[j + 1] == ie[i]:
            j += 1
        if j > i and not is_seam[ie[i]]:
            for a in range(i, j + 1):
                for b in range(a + 1, j + 1):
                    rows.append(ff[a])
                    cols.append(ff[b])
        i = j + 1
    G = sp.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(m, m))
    n, lab = connected_components(G, directed=False)
    return lab


def split(V, Q, label, seams=None):
    """CUT the mesh along its seams: each vertex gets one copy per FAN of its incident faces, fans separated by seam
    edges (and by island labels). A seam that only slits an island (an arm tube cut along its length) opens too:
    splitting per island alone left t08's arm a closed sock that LSCM crushed into a disk.
    Returns Vn (n', 3), Qn (m, 4) into Vn, orig (n',) original ids."""
    seam = set()
    if seams is not None:
        for a, b in np.asarray(seams).reshape(-1, 2).tolist():
            seam.add((min(a, b), max(a, b)))
    n = len(V)
    # incident (face, corner) lists per vertex
    inc = [[] for _ in range(n)]
    for f in range(len(Q)):
        for k in range(4):
            inc[int(Q[f, k])].append((f, k))
    Qn = -np.ones_like(Q)
    orig = []
    for v in range(n):
        fc = inc[v]
        if not fc:
            continue
        # two incident faces join at v when they share an edge (v, w) that is not a seam and have the same label
        edges_of = []
        for f, k in fc:
            q = Q[f]
            edges_of.append({int(q[(k + 1) % 4]), int(q[(k - 1) % 4])})
        parent = list(range(len(fc)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for i in range(len(fc)):
            for j in range(i + 1, len(fc)):
                if label[fc[i][0]] != label[fc[j][0]]:
                    continue
                for w in edges_of[i] & edges_of[j]:
                    if (min(v, w), max(v, w)) not in seam:
                        parent[find(i)] = find(j)
        groups = {}
        for i, (f, k) in enumerate(fc):
            r = find(i)
            if r not in groups:
                groups[r] = len(orig)
                orig.append(v)
            Qn[f, k] = groups[r]
    orig = np.array(orig)
    return V[orig], Qn, orig


def _tri(Q):
    return np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])


def lscm(V, F, pin=None):
    """least-squares conformal map (Levy et al. 2002) of a triangle island; pin: two vertex ids (defaults: the two
    mutually farthest boundary-ish vertices). Returns UV (n, 2)"""
    n = len(V)
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1 = p1 - p0
    e2 = p2 - p0
    x = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-20)
    nrm = np.cross(e1, e2)
    area2 = np.linalg.norm(nrm, axis=1)
    z = nrm / np.maximum(area2[:, None], 1e-20)
    y = np.cross(z, x)
    # local 2D coordinates of the three corners
    q = np.zeros((len(F), 3, 2))
    q[:, 1, 0] = np.linalg.norm(e1, axis=1)
    q[:, 2, 0] = (e2 * x).sum(1)
    q[:, 2, 1] = (e2 * y).sum(1)
    s = np.sqrt(np.maximum(area2, 1e-30))
    # W_j = (x_k - x_l, y_k - y_l) complex per corner j (opposite edge), divided by sqrt(area)
    Wr = np.zeros((len(F), 3))
    Wi = np.zeros((len(F), 3))
    for j in range(3):
        k, l = (j + 1) % 3, (j + 2) % 3
        Wr[:, j] = (q[:, l, 0] - q[:, k, 0]) / s
        Wi[:, j] = (q[:, l, 1] - q[:, k, 1]) / s
    if pin is None:
        a = int(np.argmin(V[:, 0] + V[:, 1] * 1e-3))
        d = np.linalg.norm(V - V[a], axis=1)
        b = int(np.argmax(d))
        a = int(np.argmax(np.linalg.norm(V - V[b], axis=1)))
        pin = (a, b)
    free = np.ones(n, bool)
    free[list(pin)] = False
    fidx = -np.ones(n, np.int64)
    fidx[free] = np.arange(free.sum())
    nf = int(free.sum())
    rows, cols, vals = [], [], []
    br = np.zeros(2 * len(F))
    pin_uv = {pin[0]: np.array([0.0, 0.0]), pin[1]: np.array([1.0, 0.0])}
    for j in range(3):
        vj = F[:, j]
        t = np.arange(len(F))
        for (row_off, wr, wi) in ((0, Wr[:, j], -Wi[:, j]), (len(F), Wi[:, j], Wr[:, j])):
            # real row: Wr u - Wi v ; imag row: Wi u + Wr v
            fr = fidx[vj]
            m = fr >= 0
            rows += list(t[m] + row_off)
            cols += list(fr[m])
            vals += list(wr[m])
            rows += list(t[m] + row_off)
            cols += list(fr[m] + nf)
            vals += list(wi[m])
            for pv, puv in pin_uv.items():
                mp = vj == pv
                br[t[mp] + row_off] -= wr[mp] * puv[0] + wi[mp] * puv[1]
    A = sp.csr_matrix((vals, (rows, cols)), shape=(2 * len(F), 2 * nf))
    sol = spla.lsqr(A, br, atol=1e-12, btol=1e-12, iter_lim=20000)[0]
    UV = np.zeros((n, 2))
    UV[free, 0] = sol[:nf]
    UV[free, 1] = sol[nf:]
    for pv, puv in pin_uv.items():
        UV[pv] = puv
    return UV


def arap(V, F, UV, iters=10):
    """as-rigid-as-possible parameterization refinement (Liu et al. 2008), cotangent weights"""
    n = len(V)
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    x = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-20)
    nrm = np.cross(e1, e2)
    z = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-20)
    y = np.cross(z, x)
    X = np.zeros((len(F), 3, 2))
    X[:, 1, 0] = np.linalg.norm(e1, axis=1)
    X[:, 2, 0] = (e2 * x).sum(1)
    X[:, 2, 1] = (e2 * y).sum(1)
    # cotangent weights per half-edge (edge opposite corner c)
    cot = np.zeros((len(F), 3))
    for c in range(3):
        a, b = (c + 1) % 3, (c + 2) % 3
        u, v = X[:, a] - X[:, c], X[:, b] - X[:, c]
        cr = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
        cot[:, c] = (u * v).sum(1) / np.maximum(np.abs(cr), 1e-20)
    cot = np.clip(cot, -1e3, 1e3)
    rows, cols, vals = [], [], []
    for c in range(3):
        a, b = (c + 1) % 3, (c + 2) % 3
        w = 0.5 * cot[:, c]
        ia, ib = F[:, a], F[:, b]
        rows += [ia, ib, ia, ib]
        cols += [ib, ia, ia, ib]
        vals += [-w, -w, w, w]
    L = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    # pin vertex 0 to remove the translation null space
    L = L.tolil()
    L[0, :] = 0
    L[0, 0] = 1.0
    L = L.tocsc()
    solve = spla.factorized(L)
    U = UV.copy()
    for _ in range(iters):
        # local: best rotation per triangle (2x2 SVD of the Jacobian)
        Rs = np.zeros((len(F), 2, 2))
        S = np.zeros((len(F), 2, 2))
        for c in range(3):
            a, b = (c + 1) % 3, (c + 2) % 3
            du = U[F[:, a]] - U[F[:, b]]
            dx = X[:, a] - X[:, b]
            S += 0.5 * cot[:, c, None, None] * du[:, :, None] * dx[:, None, :]
        Uu, sig, Vt = np.linalg.svd(S)
        R = Uu @ Vt
        flip = np.linalg.det(R) < 0
        Uu[flip, :, 1] *= -1
        R = Uu @ Vt
        # global: L U = b
        bx = np.zeros((n, 2))
        for c in range(3):
            a, b = (c + 1) % 3, (c + 2) % 3
            w = 0.5 * cot[:, c]
            dx = X[:, a] - X[:, b]
            rd = np.einsum('fij,fj->fi', R, dx) * w[:, None]
            np.add.at(bx, F[:, a], rd)
            np.add.at(bx, F[:, b], -rd)
        bx[0] = U[0]
        U = np.column_stack([solve(bx[:, 0]), solve(bx[:, 1])])
    return U


def stretch(V, F, UV):
    """per triangle, the singular values (s1 >= s2) of the map from UV to the surface: s1/s2 is the ANISOTROPY (1 =
    a texel lands as a square; organic-references materials guide §4: measure angle and area stretch per island)"""
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    t0, t1, t2 = UV[F[:, 0]], UV[F[:, 1]], UV[F[:, 2]]
    E = np.stack([p1 - p0, p2 - p0], -1)                  # (m, 3, 2)
    D = np.stack([t1 - t0, t2 - t0], -1)                  # (m, 2, 2)
    det = D[:, 0, 0] * D[:, 1, 1] - D[:, 0, 1] * D[:, 1, 0]
    ok = np.abs(det) > 1e-18
    Dinv = np.zeros_like(D)
    Dinv[ok, 0, 0], Dinv[ok, 1, 1] = D[ok, 1, 1] / det[ok], D[ok, 0, 0] / det[ok]
    Dinv[ok, 0, 1], Dinv[ok, 1, 0] = -D[ok, 0, 1] / det[ok], -D[ok, 1, 0] / det[ok]
    J = E @ Dinv                                          # (m, 3, 2): metres per UV unit
    s = np.linalg.svd(J, compute_uv=False)                # (m, 2)
    return s[:, 0], np.maximum(s[:, 1], 1e-20), ok


def footprint(V, F, UV, q=95.0):
    """the island's worst-direction texel footprint: per triangle s1 (metres per UV unit along its most stretched
    direction) at the island's mean density, its AREA-weighted q-th percentile (1 = every texel lands square and the
    same size; sliver triangles carry their area, not a vote)"""
    s1, _, ok = stretch(V, F, UV)
    x = (s1 * island_density(V, F, UV))[ok]
    w = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)[ok]
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][min(np.searchsorted(cw, q / 100.0 * cw[-1]), len(o) - 1)])


def self_overlap(UV, F, res=768):
    """texels covered by more than one triangle when the island is rasterised ALONE at res over its bounding box (the
    bar is 0: two surface points sharing a texel bake into each other)"""
    lo = UV.min(0)
    s = (res - 1) / max(float((UV.max(0) - lo).max()), 1e-12)
    T = (UV - lo) * s
    cnt = np.zeros((res, res), np.int32)
    for a, b, c in T[F]:
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, res - 1), min(y1, res - 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if x1 < x0 or y1 < y0 or abs(den) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        inside = (l0 > 1e-4) & (l1 > 1e-4) & (1.0 - l0 - l1 > 1e-4)
        cnt[gy[inside].astype(int), gx[inside].astype(int)] += 1
    return int((cnt > 1).sum())


def island_density(V, F, UV):
    a3 = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1).sum()
    d1, d2 = UV[F[:, 1]] - UV[F[:, 0]], UV[F[:, 2]] - UV[F[:, 0]]
    a2 = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum()
    return np.sqrt(a2 / max(a3, 1e-20))


def pack(isl_uvs, isl_scale, size=2048, pad=8):
    """isl_uvs: list of (n_i, 2) UV arrays (any units), isl_scale: list of factors turning them into texels at the
    target density. Places each island (rotated 0/90 to keep the skyline low) and returns the UVs in 0-1 and the used
    height share. A skyline packer over the texel grid, islands sorted tallest first."""
    boxes = []
    for i, (U, s) in enumerate(zip(isl_uvs, isl_scale)):
        T = (U - U.min(0)) * s
        w, h = T.max(0) + 2 * pad
        if w > h:                       # lay islands flat
            T = np.column_stack([T[:, 1], T.max(0)[0] - T[:, 0]])
            w, h = h, w
        boxes.append((i, T, int(np.ceil(w)), int(np.ceil(h))))
    order = sorted(boxes, key=lambda b: -b[3])
    sky = np.zeros(size, np.int64)
    out = [None] * len(isl_uvs)
    for i, T, w, h in order:
        best = None
        for x in range(0, size - w + 1, 4):
            y = int(sky[x:x + w].max())
            if best is None or y < best[1]:
                best = (x, y)
        if best is None:
            raise ValueError(f'island {i} ({w}x{h} texels) wider than the sheet')
        x, y = best
        sky[x:x + w] = y + h
        out[i] = (T + np.array([x + pad, y + pad])) / size
    used = sky.max() / size
    return out, used
