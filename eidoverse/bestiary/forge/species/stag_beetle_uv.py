"""B5 UVs for the beetle (the Bestiary lead's round 10-28; CROSSBREED §7.3, BEETLE_PLAN §4.7, the house texture-budget rules:
memory feedback_texture_budget_fix_islands_not_sets, feedback_stack_identical_parts_uvs).

THE DENSITY: 9,257 px/m at x10 (0.108 mm a texel; 92.57 texels per life mm) on every surface that SHOWS at rest. The house
rules applied before any set is counted:
  1. STACKING. Mirrored and repeated pieces share their master's shells (stag_beetle_parts' instances: the R side through
     the tangent sign, claw b turned). Masters of IDENTICAL topology that are SIMILAR under rotation + uniform scale
     (Umeyama on the lows, vertex for vertex, residual under SIMILAR_TOL of the piece's size) share the LARGEST one's
     shells (the four lamellae, the tarsomeres, the claws, the sleeves): the smaller copies simply get more density.
  2. HIDDEN MEANS HIDDEN. Each face's visibility at rest is measured (rays from its samples over its hemisphere against
     every placed piece; visibility.py-style, Warp): a face no ray leaves is OCCLUDED (under the elytra, behind the
     pronotum's hind margin) or BURIED (inside another piece: the condyles' sunk ends, the eye's base, the coxae in their
     sockets). Hidden faces are split out of the seen islands (one seen face makes a whole island pack at full weight)
     and pack at DENSITY_HIDDEN of the one density.
  3. ISLANDS. Seams on the kind's hidden line and on creases: a TUBE (an elongated genus-0 piece: leg segments, antenna,
     palps, claws) is cut along ONE meridian, pole to pole, its path the cheapest on the hidden side; every other chart is
     bisected (the face graph's Fiedler vector, the normalised-cut sweep; crease edges and hidden-side edges cheap to cut)
     until it unwraps within the bars. Each chart: a direct LSCM, then ARAP (metric, so its scale is the one density);
     bars per chart: a disk, no flipped triangle, no self-overlap, anisotropy p95 <= CHART_ANISO, the local scale within
     +-CHART_SCALE of 1 at p10 / p90 (area weighted).
  4. SLEEVES (the graft rings): an analytic STRIP, the proximal (graft) ring one straight UV edge, the length seam on its
     hidden (caudomedial) column: the ring meets a straight UV edge (CROSSBREED §7.1 rule 5).
  5. PACKING by raster masks (an occupancy bitmap at 1/PACK_DS, FFT feasibility, bottom-left), largest first, on as many
     4096 pages as the islands need; every island padded by its THICKNESS (2 x its largest inscribed circle: an island
     stops resolving at mip log2(thickness)), between PAD_MIN and PAD_MAX texels a side.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.sparse.csgraph import connected_components, dijkstra

from .. import uv as UVm

PX_PER_M = 9257.0
TEX_PER_MM = PX_PER_M * 10.0 / 1000.0          # texels per LIFE mm (built and exported at x10)
SIZE = 4096
DENSITY_HIDDEN = dict(visible=1.0, occluded=0.5, buried=0.25)
CHART_ANISO = 1.25                  # per chart (area-weighted p95); the gate is the whole layout's p95 <= 1.2
CHART_SCALE = 0.10
MIX_SPLIT = (0.15, 2.0)             # a chart whose seen share lies between this and 1 - this, with at least the second
#                                     value in mm^2 (life) hidden, is split along the class boundary; else it packs at the
#                                     density of what it mostly is (seen if >= the first share is seen)
SIMILAR_TOL = 0.04
PAD_MIN, PAD_MAX = 3, 8
PACK_DS = 4
HIDDEN_DIR = dict(head=(0.0, -1.0, 0.0), eye=None, mandible=(0.0, -1.0, 0.0), antenna=(0.0, -1.0, 0.0),
                  mouthparts=(0.0, -1.0, 0.0), pronotum=(0.0, -1.0, 0.0), scutellum=(0.0, -1.0, 0.0),
                  elytron=(0.0, -1.0, 0.0), venter=(0.0, 1.0, 0.0), coxa=(-0.7, -0.7, 0.0), trochanter=(-0.7, -0.7, 0.0),
                  femur=(-0.7, -0.7, 0.0), tibia=(-0.7, -0.7, 0.0), tarsus=(-0.6, -0.8, 0.0), claw=(0.0, -1.0, 0.0),
                  membrane=(-0.7, -0.7, 0.0))


# ============================================================================================ topology helpers
def tris_of(Q, V):
    """two triangles per quad along the shorter diagonal (QuadMesh.tris's rule: the export's split); returns (F, quad id)"""
    d02 = np.linalg.norm(V[Q[:, 0]] - V[Q[:, 2]], axis=1)
    d13 = np.linalg.norm(V[Q[:, 1]] - V[Q[:, 3]], axis=1)
    s = d02 <= d13
    Fa = np.where(s[:, None], Q[:, [0, 1, 2]], Q[:, [0, 1, 3]])
    Fb = np.where(s[:, None], Q[:, [0, 2, 3]], Q[:, [1, 2, 3]])
    return np.concatenate([Fa, Fb]), np.concatenate([np.arange(len(Q)), np.arange(len(Q))])


def quad_edges(Q):
    """unique edges E (sorted pairs), per quad its 4 edge ids, per edge its faces (-1 when one)"""
    d = np.stack([Q, np.roll(Q, -1, axis=1)], -1).reshape(-1, 2)
    key = np.sort(d, axis=1)
    E, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    QE = inv.reshape(-1, 4)
    ef = np.full((len(E), 2), -1, np.int64)
    fid = np.repeat(np.arange(len(Q)), 4)
    order = np.argsort(inv, kind='stable')
    fe, ff = inv[order], fid[order]
    first = np.ones(len(fe), bool)
    first[1:] = fe[1:] != fe[:-1]
    ef[fe[first], 0] = ff[first]
    ef[fe[~first], 1] = ff[~first]
    return E, QE, ef


def quad_normals(V, Q):
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    a = np.linalg.norm(n, axis=1)
    return n / np.maximum(a, 1e-20)[:, None], 0.5 * a


def chart_topology(Q, faces):
    """(is a disk, boundary loops, Euler characteristic) of the face subset"""
    q = Q[faces]
    E, QE, ef = quad_edges(q)
    nv = len(np.unique(q))
    chi = nv - len(E) + len(q)
    b = ef[:, 1] < 0
    loops = 0
    if b.any():
        be = E[b]
        n = int(be.max()) + 1
        G = sp.coo_matrix((np.ones(len(be)), (be[:, 0], be[:, 1])), shape=(n, n))
        nc, lab = connected_components(G, directed=False)
        loops = len(np.unique(lab[np.unique(be.ravel())]))
    return (chi == 1 and loops == 1), loops, chi


# ============================================================================================ the per-chart unwrap
def lscm_direct(V, F, pin=None):
    """least-squares conformal map with a direct sparse solve (uv.lscm's system, its normal equations): two pinned
    vertices, the farthest pair of the boundary-ish extremes"""
    n = len(V)
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    x = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-20)
    nrm = np.cross(e1, e2)
    area2 = np.linalg.norm(nrm, axis=1)
    z = nrm / np.maximum(area2[:, None], 1e-20)
    y = np.cross(z, x)
    q = np.zeros((len(F), 3, 2))
    q[:, 1, 0] = np.linalg.norm(e1, axis=1)
    q[:, 2, 0] = (e2 * x).sum(1)
    q[:, 2, 1] = (e2 * y).sum(1)
    s = np.sqrt(np.maximum(area2, 1e-30))
    Wr = np.zeros((len(F), 3))
    Wi = np.zeros((len(F), 3))
    for j in range(3):
        k, l_ = (j + 1) % 3, (j + 2) % 3
        Wr[:, j] = (q[:, l_, 0] - q[:, k, 0]) / s
        Wi[:, j] = (q[:, l_, 1] - q[:, k, 1]) / s
    if pin is None:
        a = int(np.argmin(V[:, 0] + V[:, 1] * 1e-3 + V[:, 2] * 1e-6))
        b = int(np.argmax(np.linalg.norm(V - V[a], axis=1)))
        a = int(np.argmax(np.linalg.norm(V - V[b], axis=1)))
        pin = (a, b)
    L = float(np.linalg.norm(V[pin[1]] - V[pin[0]]))
    pin_uv = {pin[0]: np.array([0.0, 0.0]), pin[1]: np.array([L, 0.0])}
    free = np.ones(n, bool)
    free[list(pin)] = False
    fidx = -np.ones(n, np.int64)
    fidx[free] = np.arange(free.sum())
    nf = int(free.sum())
    rows, cols, vals = [], [], []
    br = np.zeros(2 * len(F))
    t = np.arange(len(F))
    for j in range(3):
        vj = F[:, j]
        for (row_off, wr, wi) in ((0, Wr[:, j], -Wi[:, j]), (len(F), Wi[:, j], Wr[:, j])):
            fr = fidx[vj]
            m = fr >= 0
            rows += [t[m] + row_off, t[m] + row_off]
            cols += [fr[m], fr[m] + nf]
            vals += [wr[m], wi[m]]
            for pv, puv in pin_uv.items():
                mp = vj == pv
                br[t[mp] + row_off] -= wr[mp] * puv[0] + wi[mp] * puv[1]
    A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(2 * len(F), 2 * nf))
    sol = spla.spsolve((A.T @ A).tocsc(), A.T @ br)
    UV = np.zeros((n, 2))
    UV[free, 0], UV[free, 1] = sol[:nf], sol[nf:]
    for pv, puv in pin_uv.items():
        UV[pv] = puv
    return UV


def chart_metrics(V, F, UV):
    """area-weighted anisotropy p95, local scale p10 / p90 (texels or mm per mm: the map's metric scale), flipped count,
    the mean scale"""
    s1, s2, ok = UVm.stretch(V, F, UV)          # metres-per-UV singular values (here mm per UV unit)
    a3 = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    d1, d2 = UV[F[:, 1]] - UV[F[:, 0]], UV[F[:, 2]] - UV[F[:, 0]]
    sa = 0.5 * (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    flipped = int((sa < 0).sum())
    aniso = np.where(ok, s1 / np.maximum(s2, 1e-20), 99.0)
    scale = np.where(ok, 1.0 / np.sqrt(np.maximum(s1 * s2, 1e-30)), 0.0)    # UV units per mm (area scale's root)

    def wq(x, q):
        o = np.argsort(x)
        cw = np.cumsum(a3[o])
        return float(x[o][min(np.searchsorted(cw, q / 100.0 * cw[-1]), len(o) - 1)])
    mean = float(np.sqrt(np.abs(sa).sum() / max(a3.sum(), 1e-30)))
    return dict(aniso95=wq(aniso, 95.0), s10=wq(scale, 10.0) / max(mean, 1e-30), s90=wq(scale, 90.0) / max(mean, 1e-30),
                flipped=flipped, mean=mean)


def unwrap_chart(Vc, Fc, iters=16):
    """LSCM then ARAP; the map flipped to positive orientation when LSCM mirrored it. Returns (UV in mm, metrics)"""
    U = lscm_direct(Vc, Fc)
    d1, d2 = U[Fc[:, 1]] - U[Fc[:, 0]], U[Fc[:, 2]] - U[Fc[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        U[:, 0] = -U[:, 0]
    U = UVm.arap(Vc, Fc, U, iters=iters)
    d1, d2 = U[Fc[:, 1]] - U[Fc[:, 0]], U[Fc[:, 2]] - U[Fc[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        U[:, 0] = -U[:, 0]
    return U, chart_metrics(Vc, Fc, U)


def chart_ok(met, overlap):
    return (met['flipped'] == 0 and overlap == 0 and met['aniso95'] <= CHART_ANISO and met['s10'] >= 1.0 - CHART_SCALE
            and met['s90'] <= 1.0 + CHART_SCALE)


# ============================================================================================ seams
def _sub(V, Q, faces, seam_set):
    """the chart's own vertex copies (split along seam edges inside it): returns (Vc, Fc (tris), corner map (tri corner ->
    global vertex), tri -> quad)"""
    q = Q[faces]
    lab = np.zeros(len(q), np.int64)
    seams = np.array(sorted(seam_set), np.int64).reshape(-1, 2) if seam_set else None
    Vn, Qn, orig = UVm.split(V, q, lab, seams)
    F, fq = tris_of(Qn, Vn)
    return Vn, F, orig, Qn, fq


def tube_axis(V):
    c = V.mean(0)
    w, U = np.linalg.eigh(np.cov((V - c).T))
    return c, U[:, 2], w[2] / max(w[1], 1e-12)


def meridian_seam(V, Q, faces, hidden):
    """the cheapest edge path between the chart's two axial extremes (pole to pole), costs = length x (1 + 4 x how much
    the edge faces the viewer: 1 - n.h on the hidden side), so the seam runs along the hidden line"""
    q = Q[faces]
    E, QE, ef = quad_edges(q)
    vs = np.unique(q)
    c, ax, _ = tube_axis(V[vs])
    t = (V[vs] - c) @ ax
    a, b = int(vs[np.argmin(t)]), int(vs[np.argmax(t)])
    fn, _ = quad_normals(V, q)
    en = fn[ef[:, 0]] + np.where(ef[:, 1:2] >= 0, fn[np.maximum(ef[:, 1], 0)], 0.0)
    en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-20)
    h = np.zeros(3) if hidden is None else np.asarray(hidden, np.float64) / np.linalg.norm(hidden)
    face_view = 1.0 - (en @ h) if hidden is not None else np.ones(len(E))
    cost = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * (1.0 + 2.0 * face_view)
    n = len(V)
    G = sp.coo_matrix((np.r_[cost, cost], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()
    dist, pred = dijkstra(G, indices=a, return_predecessors=True)
    path = []
    v = b
    while v != a and v >= 0:
        u = int(pred[v])
        if u < 0:
            return set()
        path.append((min(u, v), max(u, v)))
        v = u
    return set(path)


def fiedler_split(V, Q, faces, sharp_set, hidden, seams=None, fclass=None):
    """two (or more, when a side falls apart) face sets: the face graph's normalised-cut sweep on its Fiedler vector; the
    graph never joins faces across a seam already cut (seams); edges cheap to cut where creased, across a visibility class
    boundary (fclass: per GLOBAL face), on the hidden side, or across a high dihedral"""
    q = Q[faces]
    E, QE, ef = quad_edges(q)
    inner = ef[:, 1] >= 0
    if seams:
        inner &= np.array([(int(a), int(b)) not in seams for a, b in E])
    fn, fa = quad_normals(V, q)
    i0, i1 = ef[inner, 0], ef[inner, 1]
    dih = np.arccos(np.clip((fn[i0] * fn[i1]).sum(1), -1.0, 1.0))
    w = np.exp(-dih / 0.35)
    ee = E[inner]
    key = [(int(a), int(b)) for a, b in ee]
    crease = np.array([k in sharp_set for k in key], bool)
    w = np.where(crease, w * 0.1, w)
    if fclass is not None:
        fc = fclass[faces]
        w = np.where(fc[i0] != fc[i1], w * 0.15, w)
    if hidden is not None:
        # how much the edge faces away from the hidden direction (1: the seen side, 0: the hidden side): hidden-side
        # edges cost 0.35 of a seen one, so the cut runs there
        h = np.asarray(hidden, np.float64) / np.linalg.norm(hidden)
        en = fn[i0] + fn[i1]
        en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-20)
        seen = np.clip(0.5 - 0.5 * (en @ h), 0.0, 1.0)
        w = w * (0.35 + 0.65 * seen)
    m = len(q)
    W = sp.coo_matrix((np.r_[w, w], (np.r_[i0, i1], np.r_[i1, i0])), shape=(m, m)).tocsr()
    d = np.asarray(W.sum(1)).ravel() + 1e-12
    Dm = sp.diags(1.0 / np.sqrt(d))
    Lsym = sp.eye(m) - Dm @ W @ Dm
    try:
        if m < 600:
            vals, vecs = np.linalg.eigh(Lsym.toarray())
            f = vecs[:, 1]
        else:
            vals, vecs = spla.eigsh(Lsym.tocsc(), k=2, sigma=-1e-3, which='LM')
            f = vecs[:, np.argsort(vals)[1]]
    except Exception:
        c, ax, _ = tube_axis(V[np.unique(q)])
        f = (V[q].mean(1) - c) @ ax
    f = f / np.sqrt(d)
    o = np.argsort(f)
    # the sweep: the normalised cut of each prefix (20 .. 80 % of the area)
    pos = np.empty(m, np.int64)
    pos[o] = np.arange(m)
    area_cum = np.cumsum(fa[o]) / fa.sum()
    best, best_k = np.inf, m // 2
    vol = d[o].cumsum()
    tot = d.sum()
    # cut weight for each prefix: edges with one end in the prefix
    pa, pb = pos[i0], pos[i1]
    lo, hi = np.minimum(pa, pb), np.maximum(pa, pb)
    cut = np.zeros(m + 1)
    np.add.at(cut, lo + 1, w)
    np.add.at(cut, hi + 1, -w)
    cut = np.cumsum(cut)[1:]
    for k in range(m - 1):
        if not (0.2 <= area_cum[k] <= 0.8):
            continue
        nc = cut[k] / vol[k] + cut[k] / max(tot - vol[k], 1e-12)
        if nc < best:
            best, best_k = nc, k
    A = np.zeros(m, bool)
    A[o[:best_k + 1]] = True
    out = []
    for side in (A, ~A):
        fs = np.nonzero(side)[0]
        # keep each side connected over the graph's own edges (a side that falls apart gives several groups)
        Gs = sp.coo_matrix((np.ones(len(i0)), (i0, i1)), shape=(m, m)).tocsr()[fs][:, fs]
        nc_, lab = connected_components(Gs, directed=False)
        out.append((fs, lab, nc_))
    groups = []
    for fs, lab, nc_ in out:
        for c in range(nc_):
            groups.append(faces[fs[lab == c]])
    return groups


def chart_class(face_class, area, faces):
    """the chart's packing class: seen (0) when at least MIX_SPLIT[0] of its area is seen, else the hidden class with more
    area (1 occluded, 2 buried); and whether it is MIXED enough to split along the class boundary"""
    a = area[faces]
    fc = face_class[faces]
    tot = max(a.sum(), 1e-12)
    seen = a[fc == 0].sum() / tot
    hid = a[fc > 0].sum()
    mixed = (MIX_SPLIT[0] <= seen <= 1.0 - MIX_SPLIT[0]) and hid >= MIX_SPLIT[1]
    if seen >= MIX_SPLIT[0]:
        return 0, mixed
    return (1 if a[fc == 1].sum() >= a[fc == 2].sum() else 2), mixed


# ============================================================================================ the master's charts
def unwrap_master(V, Q, sharp, face_class, hidden, log=print, name='', max_depth=14, min_faces=10):
    """charts for one master: the whole piece first; a closed elongated piece (a tube) is cut along ONE meridian on its
    hidden line; then every chart that is not a disk, fails the bars (chart_ok) or MIXES seen and hidden faces
    (chart_class) is bisected (fiedler_split: seams kept, creases and class boundaries cheap) until it passes. A chart
    with a flipped triangle or a self-overlap is split down to single quads if it must (a quad always lies flat); a chart
    only over the distortion bars stops at min_faces. Returns charts dict(faces, Vc, Fc, orig, Qc, uv (mm), metrics, cls,
    tube)"""
    sharp_set = {(min(a, b), max(a, b)) for (a, b) in sharp}
    _, area = quad_normals(V, Q)
    todo = [(np.arange(len(Q)), 0, frozenset(), True)]
    charts = []
    while todo:
        faces, depth, seams, first = todo.pop()
        seams_in = {e for e in seams if True}
        Vc, Fc, orig, Qc, fq = _sub(V, Q, faces, seams_in)
        disk, loops, chi = chart_topology(Qc, np.arange(len(Qc)))
        if not disk and first and not seams:
            vs = np.unique(Q[faces])
            _, _, elong = tube_axis(V[vs])
            if loops == 0 and chi == 2 and elong > 2.5:
                cut = meridian_seam(V, Q, faces, hidden)
                if cut:
                    todo.append((faces, depth, frozenset(cut), False))
                    continue
        split = False
        U, met, ov = None, None, None
        if not disk:
            split = True
        else:
            try:
                U, met = unwrap_chart(Vc, Fc)
                ov = UVm.self_overlap(U, Fc, res=512) if met['flipped'] == 0 else 1
            except Exception as ex:                      # a singular system: split it
                met, ov = dict(aniso95=99.0, s10=0.0, s90=9.0, flipped=1, mean=0.0), 1
                log(f'[uv]   {name}: unwrap failed on {len(faces)} faces ({ex}); split')
            cls, mixed = chart_class(face_class, area, faces)
            hard = met['flipped'] > 0 or ov > 0
            soft = not chart_ok(dict(met, flipped=0), 0)
            if hard and len(faces) > 1:
                split = True
            elif (soft or mixed) and len(faces) >= min_faces and depth < max_depth:
                split = True
        if split and len(faces) > 1:
            groups = fiedler_split(V, Q, faces, sharp_set, hidden, seams, face_class)
            if len(groups) >= 2:
                for g in groups:
                    todo.append((g, depth + 1, seams, False))
                continue
        if U is None:
            log(f'[uv]   {name}: a {len(faces)}-face chart that is no disk (loops {loops}, chi {chi}) could not split')
            continue
        if not chart_ok(met, ov):
            log(f'[uv]   {name}: chart of {len(faces)} faces kept over the bars (aniso {met["aniso95"]:.2f}, scale '
                f'{met["s10"]:.2f}-{met["s90"]:.2f}, flipped {met["flipped"]}, overlap {ov})')
        cls, _ = chart_class(face_class, area, faces)
        charts.append(dict(faces=faces, Vc=Vc, Fc=Fc, orig=orig, Qc=Qc, uv=U, metrics=met, overlap=ov, cls=cls,
                           tube=bool(seams)))
    return charts


def arap_pinned(V, F, UV, pin, pin_uv, iters=24):
    """ARAP (uv.arap's local / global steps) with the `pin` vertices held at pin_uv (Dirichlet rows): the graft ring held
    on its straight edge while the rest of the sleeve relaxes"""
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
        rows += [F[:, a], F[:, b], F[:, a], F[:, b]]
        cols += [F[:, b], F[:, a], F[:, a], F[:, b]]
        vals += [-w, -w, w, w]
    L = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tolil()
    pin = np.asarray(pin, np.int64)
    for i in pin:
        L[i, :] = 0
        L[i, i] = 1.0
    solve = spla.factorized(L.tocsc())
    U = UV.copy()
    U[pin] = pin_uv
    for _ in range(iters):
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
        bx = np.zeros((n, 2))
        for c in range(3):
            a, b = (c + 1) % 3, (c + 2) % 3
            w = 0.5 * cot[:, c]
            dx = X[:, a] - X[:, b]
            rd = np.einsum('fij,fj->fi', R, dx) * w[:, None]
            np.add.at(bx, F[:, a], rd)
            np.add.at(bx, F[:, b], -rd)
        bx[pin] = pin_uv
        U = np.column_stack([solve(bx[:, 0]), solve(bx[:, 1])])
    return U


def sleeve_strip(V, Q, K, hidden, axis, graft=True):
    """an open K x 3-ring sleeve as one strip, the length seam at the column facing the hidden direction: started as the
    straight strip (u = the proximal ring's arc length, v = the mean column length), then relaxed by ARAP; a GRAFT sleeve
    holds its proximal (graft) ring on that straight edge (arap_pinned), so the ring meets one straight UV edge while the
    tapered rest fans out (a short tapered band is a cone's annular sector: held straight everywhere it shears by its
    taper, the reviewer's R11). Returns a chart"""
    n = len(V)
    nr = n // K
    rings = [np.arange(r * K, (r + 1) * K) for r in range(nr)]
    ax = np.asarray(axis, np.float64) / np.linalg.norm(axis)
    order = np.argsort([float(V[r].mean(0) @ ax) for r in rings])
    rings = [rings[i] for i in order]
    c0 = V[rings[0]].mean(0)
    h = np.asarray(hidden, np.float64) / np.linalg.norm(hidden)
    k0 = int(np.argmax((V[rings[0]] - c0) @ h))
    cols = [(k0 + j) % K for j in range(K + 1)]
    P0 = V[rings[0]][cols]
    u = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P0, axis=0), axis=1))]
    vrow = [0.0]
    for r in range(1, nr):
        vrow.append(vrow[-1] + float(np.mean(np.linalg.norm(V[rings[r]] - V[rings[r - 1]], axis=1))))
    Vc, UVc, idx = [], [], {}
    for r in range(nr):
        for j, k in enumerate(cols):
            idx[(r, j)] = len(Vc)
            Vc.append(V[rings[r][k]])
            UVc.append((u[j], vrow[r]))
    Vc, UVc = np.array(Vc), np.array(UVc)
    orig = np.array([rings[r][k] for r in range(nr) for k in cols])
    Qc = []
    for r in range(nr - 1):
        for j in range(K):
            Qc.append([idx[(r, j)], idx[(r, j + 1)], idx[(r + 1, j + 1)], idx[(r + 1, j)]])
    Qc = np.array(Qc, np.int64)
    # the orientation of the source quads (the strip's first quad against the nearest source quad's normal)
    sq = np.asarray(Q)
    ctr = Vc[Qc].mean(1)
    j = int(np.argmin(np.linalg.norm(V[sq].mean(1) - ctr[0], axis=1)))
    ns = np.cross(V[sq[j, 2]] - V[sq[j, 0]], V[sq[j, 3]] - V[sq[j, 1]])
    nq = np.cross(Vc[Qc[0, 2]] - Vc[Qc[0, 0]], Vc[Qc[0, 3]] - Vc[Qc[0, 1]])
    if ns @ nq < 0:
        Qc = Qc[:, ::-1].copy()
    F, fq = tris_of(Qc, Vc)
    d1, d2 = UVc[F[:, 1]] - UVc[F[:, 0]], UVc[F[:, 2]] - UVc[F[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        UVc[:, 0] = u.max() - UVc[:, 0]
    row0 = np.array([idx[(0, j)] for j in range(K + 1)])
    if graft:
        UVc = arap_pinned(Vc, F, UVc, row0, UVc[row0].copy())
    else:
        UVc = UVm.arap(Vc, F, UVc, iters=24)
    met = chart_metrics(Vc, F, UVc)
    return dict(faces=np.arange(len(Q)), Vc=Vc, Fc=F, orig=orig, Qc=Qc, uv=UVc, metrics=met, overlap=0, cls=0,
                tube=True, strip=True, graft_edge=np.array([idx[(0, j)] for j in range(K + 1)]))


# ============================================================================================ similarity stacking
def umeyama(A, B):
    """the similarity (s, R, t) taking A onto B (index for index) in least squares; returns s, R, t, rms"""
    ca, cb = A.mean(0), B.mean(0)
    X, Y = A - ca, B - cb
    C = Y.T @ X / len(A)
    U, S, Vt = np.linalg.svd(C)
    D = np.eye(3)
    if np.linalg.det(U @ Vt) < 0:
        D[2, 2] = -1.0
    R = U @ D @ Vt
    var = (X ** 2).sum() / len(A)
    s = float(np.trace(np.diag(S) @ D) / max(var, 1e-30))
    t = cb - s * R @ ca
    rms = float(np.sqrt(((s * (A @ R.T) + t - B) ** 2).sum(1).mean()))
    return s, R, t, rms


def similar_groups(masters, log=print):
    """masters of identical topology similar under rotation + uniform scale share the largest's shells: {name: primary}"""
    by_topo = {}
    for m in masters:
        if m['kind'] == 'sleeve':                  # a graft sleeve shares only with graft sleeves (its straight ring edge)
            key = ('sleeve', bool(m.get('graft')), len(m['Q']), m['Q'].tobytes())
        else:
            key = ('shell', len(m['Q']), m['Q'].tobytes(), len(m['sharp']))
        by_topo.setdefault(key, []).append(m)
    share = {}
    for key, ms in by_topo.items():
        if len(ms) < 2:
            continue
        area = lambda m: float(np.sum(np.linalg.norm(np.cross(m['low'][m['Q'][:, 2]] - m['low'][m['Q'][:, 0]],  # noqa
                                                                 m['low'][m['Q'][:, 3]] - m['low'][m['Q'][:, 1]]), axis=1)))
        ms = sorted(ms, key=lambda m: -area(m))
        left = list(ms)
        while left:
            p = left.pop(0)
            size = float(np.sqrt(np.linalg.eigvalsh(np.cov((p['low'] - p['low'].mean(0)).T)).max())) * 2.0
            keep = []
            for o in left:
                s, R, t, rms = umeyama(o['low'], p['low'])
                if rms / max(size, 1e-9) <= SIMILAR_TOL and np.linalg.det(R) > 0:
                    share[o['name']] = (p['name'], s, rms / size)
                else:
                    keep.append(o)
            left = keep
    for o, (p, s, r) in sorted(share.items()):
        log(f'[uv] stack: {o} shares {p}\'s shells (scale {1.0 / s:.3f} of it, residual {r * 100:.2f} % of its size)')
    return share


# ============================================================================================ packing
def island_mask(uvt, F, pad, ds=PACK_DS):
    """the island's raster at 1/ds (texel uvs uvt, already offset to start at pad), dilated by pad"""
    from scipy import ndimage as nd
    W = int(np.ceil((uvt[:, 0].max() + pad) / ds)) + 1
    H = int(np.ceil((uvt[:, 1].max() + pad) / ds)) + 1
    m = np.zeros((H, W), bool)
    T = uvt / ds
    for a, b, c in T[F]:
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W - 1), min(y1, H - 1)
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            m[int(np.clip(a[1], 0, H - 1)), int(np.clip(a[0], 0, W - 1))] = True
            continue
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        ins = (l0 > -0.75) & (l1 > -0.75) & (1.0 - l0 - l1 > -0.75)        # conservative: any texel it touches
        m[gy[ins].astype(int), gx[ins].astype(int)] = True
    r = int(np.ceil(pad / ds))
    if r > 0:
        m = nd.binary_dilation(m, structure=np.ones((3, 3), bool), iterations=r)
    return m


def thickness_texels(uvt, F):
    """2 x the island's largest inscribed circle (texels), from its raster's distance transform"""
    from scipy import ndimage as nd
    m = island_mask(uvt, F, 0, ds=1)
    if m.sum() == 0:
        return 1.0
    d = nd.distance_transform_edt(m)
    return float(2.0 * d.max())


def pack(islands, size=SIZE, ds=PACK_DS, log=print):
    """islands: list of dict(uvt (texel units, min at 0), F, pad); places each (rotations 0/90/180/270) on the first page
    where it fits bottom-left by an FFT feasibility scan of the occupancy bitmap; opens pages as needed. Returns per island
    (page, uv01) and the pages' fill"""
    from scipy.signal import fftconvolve
    G = size // ds
    pages = []
    out = [None] * len(islands)
    order = sorted(range(len(islands)), key=lambda i: -float(np.ptp(islands[i]['uvt'][:, 0]) *
                                                              np.ptp(islands[i]['uvt'][:, 1])))
    for i in order:
        isl = islands[i]
        best = None
        for rot in (0, 1):
            T = isl['uvt'].copy()
            for _ in range(rot):
                T = np.column_stack([T[:, 1], -T[:, 0]])
            T = T - T.min(0) + isl['pad']
            m = island_mask(T, isl['F'], isl['pad'], ds)
            if m.shape[0] > G or m.shape[1] > G:
                continue
            for pg in range(len(pages) + 1):
                occ = pages[pg] if pg < len(pages) else np.zeros((G, G), bool)
                ov = fftconvolve(occ.astype(np.float32), m[::-1, ::-1].astype(np.float32), mode='valid')
                ok = np.argwhere(ov < 0.5)
                if not len(ok):
                    continue
                k = np.lexsort((ok[:, 1], ok[:, 0]))[0]
                y, x = int(ok[k, 0]), int(ok[k, 1])
                cand = (pg, y + m.shape[0], x, rot, T, m, y)
                if best is None or (cand[0], cand[1], cand[2]) < (best[0], best[1], best[2]):
                    best = cand
                break
        if best is None:
            raise ValueError(f'island {i} does not fit a {size} page')
        pg, _, x, rot, T, m, y = best
        if pg == len(pages):
            pages.append(np.zeros((G, G), bool))
        pages[pg][y:y + m.shape[0], x:x + m.shape[1]] |= m
        uvp = T + np.array([x * ds, y * ds])
        out[i] = dict(page=pg, uv=uvp / size, rot=rot)
    fill = [float(p.mean()) for p in pages]
    return out, fill
