"""H3b (the lead's H3b brief, item 1; HUMAN_PLAN §7's BODY row; Skye's rule, asked 10-04, 10-05, 10-15 and 10-27: repeated
and scaled / rotated parts share the largest copy's UV shells unless unique AO needs the texels): THE STACK GATE on the
human's LOW. Step scripts: work/bestiary/human/h3b/h3b_stack.py (detection, the measures, the AO decisions) and h3b_uv.py
(the shells, the shape checks, the gate).

THE REPEATS, from the evidence (forge probes h3b p01 / p02):
  * the DIGITS: each finger's and toe's skin from hm08's skin weights (finger<d>-* / toe<d>-*, the cage's body ids mapped
    to hm08's by c2h), its ROOT RING the most proximal closed edge loop round the digit's axis, its PIECE the quads distal
    to that ring (the nail patch included);
  * the NAILS: each nail patch inside its collar (h2b's nail folds: recs['nails'], loop + inner);
  * groups by TOPOLOGY SIGNATURE (quads, vertices, valences) and a vertex-for-vertex ISOMORPHISM (a rotation-system BFS
    from each candidate start half-edge of the copy's ring / collar against a fixed one of the primary's, kept when every
    quad maps onto a quad, the best by the similarity residual); non-isomorphic look-alikes (toes 1, 4, 5, the thumb)
    get an ICP shape similarity (rotation + uniform scale on the vertex clouds) and their AO through it.
  The PRIMARY of a group is its largest member (by the LOW's area); the plan's primaries for the nails (§7: "the 4
  fingernails on one shell and the thumbnail on its own ... toes 2-5 with their nails likewise"): the largest of fingers
  2-5 / toes 2-5.

THE MEASURES per copy against its primary, at corresponding points on the HIGH's level-4 limit (the mesh the bake's rays
meet): |dAO| (cosine rays to 25 mm, 256 a point), |dCavity| (2.5 mm), the relative thickness (the shape diameter), the
noise floor (the copy against its own right mirror, an exact mirror: any difference is the rays' noise); the similarity
residual; the STACKED ANISOTROPY of the vertex-for-vertex share (the copy's triangles against the primary's).

THE RULE (decide; h3b-stack-2, the forge builder's successor, on probes p04 / p05): a copy stacks when
  1. ITS AO WEIGHT, |dAO| p95 x sqrt(the part's area in cm2), is at most AO_WEIGHT_BAR (0.25). "Unique AO needs the
     texels" is a question about what can be seen: for a part this small the eye detects contrast x sqrt(area) (Piper's
     law of spatial summation), so a 0.1 difference across a 6 mm nail is not the same claim as 0.1 across a finger. The
     measured parts fall in two groups with a wide gap: every nail 0.01-0.15, every skin part (a whole digit or one
     finger or toe segment) 0.43-5.2. (h3b-stack-1's bar, |dAO| p95 <= 0.05, was the instrument's noise floor x 3: it says
     a difference can be detected, not that it needs texels. Under it only the middle and ring nails stack.)
  2. its shell can be shared: isomorphic to the primary (the shared chart is laid on its own vertices), and then, in the
     UV step, its BOUNDARY-ANCHORED CHART (anchored_chart: the copy's own surface mapped into the primary's chart outline,
     the corners anchored, the boundary by the copy's arc length, the inside by the house's pinned ARAP) unfolds (no
     flipped triangle, anisotropy p95 <= ANISO_BAR) and passes the DECODE check.
THE DECODE CHECK ON AN ORGANIC REPEAT (p04): the nails are not copies of each other. Their highs' normals differ by 13-25
deg p95 after the similarity fit, which no map can remove (C5-UV's hard-surface copies were exact, so its verification
could hold them to 2 deg; that bar has no meaning here). What a stack must do is KEEP THE COPY'S OWN SHAPE: decode_error
reads the primary's tangent normal in the copy's frame against the copy's own high, and the copy passes when that error's
p95 is under the two nails' INTRINSIC difference (the primary's high normal, rotated by the similarity, against the
copy's own, same UV): the stacked copy then reads closer to its own high than its primary is. The read with a FLAT map (the
copy's own LOW alone) is reported beside it. For this to hold the LOW must carry each nail's own shape: THE NAIL IS ITS
OWN SMOOTHING GROUP (nail_normals: its vertices take the high's normal just inside the plate, split from the skin at
the collar, where a UV seam splits the vertex anyway), so the skin round a nail no longer leans its rim's normals and
the map goes nearly flat (tilt p50 7.5 -> 3.7 deg).
THE GATE (gate; the lead's definition): every member of a repeat group shares its primary's shells or keeps its own with a
recorded AO reason. A part measured NOT to be a repeat (another topology, or a shape that fails as the group's primary)
is listed with that evidence, outside the groups. Anything else fails; a member with its own shells and no AO reason
fails, and the UV step proves it with a plant.
"""
import collections

import numpy as np

AO_WEIGHT_BAR = 0.25
ANISO_BAR = 1.8
DIGITS =[f'finger{d}' for d in range(1, 6)] + [f'toe{d}' for d in range(1, 6)]
NAIL_OF = dict(finger1='thumb', finger2='index', finger3='middle', finger4='ring', finger5='little', toe1='toe1',
               toe2='toe2', toe3='toe3', toe4='toe4', toe5='toe5')
VERSION = 'h3b-stack-2'


# ============================================================================================ topology helpers
def rotation_order(Q, verts):
    """per vertex its neighbours in the quads' rotation order (the quads' winding): a list; an open fan at a boundary
    vertex starts at its boundary edge"""
    nxt = collections.defaultdict(dict)
    for q in np.asarray(Q).tolist():
        for k in range(4):
            v, a, b = q[k], q[(k + 1) % 4], q[(k - 1) % 4]
            nxt[v][a] = b
    order = {}
    for v in verts:
        m = nxt[v]
        if not m:
            order[v] = []
            continue
        starts = set(m) - set(m.values())
        cur = next(iter(starts)) if starts else min(m)
        seq = [cur]
        while cur in m and m[cur] not in seq:
            cur = m[cur]
            seq.append(cur)
        order[v] = seq
    return order


def bfs_labels(order, start, ref):
    """the canonical labelling from the half-edge start -> ref: BFS, each vertex's neighbours in its rotation order from
    the one it was reached from. Returns the vertices in label order"""
    lab = {start: 0}
    came = {start: ref}
    queue = collections.deque([start])
    seq = [start]
    while queue:
        v = queue.popleft()
        nb = order[v]
        r = came[v]
        if r in nb:
            i = nb.index(r)
            nb = nb[i:] + nb[:i]
        for w in nb:
            if w not in lab:
                lab[w] = len(lab)
                came[w] = v
                queue.append(w)
                seq.append(w)
    return seq


def signature(Q, quads, nbr):
    qs = np.asarray(quads, np.int64)
    vs = np.unique(np.asarray(Q)[qs])
    vset = set(vs.tolist())
    val = collections.Counter(len([1 for w in nbr[v] if w in vset]) for v in vs.tolist())
    return (len(qs), len(vs), tuple(sorted(val.items())))


def umeyama(A, B):
    """the similarity (s, R, t) taking A onto B index for index; returns s, R, t, rms"""
    ca, cb = A.mean(0), B.mean(0)
    X, Y = A - ca, B - cb
    U, S, Vt = np.linalg.svd(Y.T @ X / len(A))
    D = np.eye(3)
    if np.linalg.det(U @ Vt) < 0:
        D[2, 2] = -1.0
    R = U @ D @ Vt
    s = float(np.trace(np.diag(S) @ D) / max((X ** 2).sum() / len(A), 1e-30))
    t = cb - s * R @ ca
    return s, R, t, float(np.sqrt(((s * (A @ R.T) + t - B) ** 2).sum(1).mean()))


def size_of(P):
    return float(np.sqrt(np.linalg.eigvalsh(np.cov((P - P.mean(0)).T)).max())) * 2.0


def iso_map(Q, low, quads_c, ring_c, quads_p, ring_p):
    """the vertex-for-vertex isomorphism copy -> primary (dict), the best by the similarity residual among the copy's
    start half-edges on its ring (both directions) against the primary's (ring_p[0] -> ring_p[1]); None if none"""
    Qp = np.asarray(Q)[quads_p]
    sp_ = bfs_labels(rotation_order(Qp, np.unique(Qp).tolist()), int(ring_p[0]), int(ring_p[1]))
    qkp = set(frozenset(q) for q in Qp.tolist())
    Qc = np.asarray(Q)[quads_c]
    oc = rotation_order(Qc, np.unique(Qc).tolist())
    best = None
    for i in range(len(ring_c)):
        for dirn in (1, -1):
            sc = bfs_labels(oc, int(ring_c[i]), int(ring_c[(i + dirn) % len(ring_c)]))
            if len(sc) != len(sp_):
                continue
            m = dict(zip(sc, sp_))
            if not all(frozenset(m[v] for v in q) in qkp for q in Qc.tolist()):
                continue
            rms = umeyama(low[sc], low[sp_])[3]
            if best is None or rms < best[0]:
                best = (rms, m)
    return None if best is None else best[1]


def tri_jacobian_aniso(Pa, Pb):
    """per triangle pair (Pa (t, 3, 3) -> Pb (t, 3, 3)): the singular values' ratio of the linear map between them in
    their own planes (scale-free)"""
    def loc(P):
        e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
        x = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-20)
        n = np.cross(e1, e2)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
        y = np.cross(n, x)
        M = np.stack([np.stack([(e1 * x).sum(1), (e2 * x).sum(1)], 1), np.stack([(e1 * y).sum(1), (e2 * y).sum(1)], 1)],
                     1)
        return M
    Ma, Mb = loc(Pa), loc(Pb)
    det = Ma[:, 0, 0] * Ma[:, 1, 1] - Ma[:, 0, 1] * Ma[:, 1, 0]
    ok = np.abs(det) > 1e-14
    inv = np.zeros_like(Ma)
    inv[:, 0, 0], inv[:, 0, 1], inv[:, 1, 0], inv[:, 1, 1] = Ma[:, 1, 1], -Ma[:, 0, 1], -Ma[:, 1, 0], Ma[:, 0, 0]
    inv /= np.where(ok, det, 1.0)[:, None, None]
    s = np.linalg.svd(Mb @ inv, compute_uv=False)
    an = np.where(ok, s[:, 0] / np.maximum(s[:, 1], 1e-20), 99.0)
    return an, 0.5 * np.abs(det)


def wq(x, w, q):
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][min(np.searchsorted(cw, q / 100.0 * cw[-1]), len(o) - 1)])


def stacked_aniso(low, Q, quads_c, m):
    """the anisotropy of the vertex-for-vertex share: p50 / p95 (area-weighted on the copy)"""
    Qc = np.asarray(Q)[quads_c]
    F = np.concatenate([Qc[:, [0, 1, 2]], Qc[:, [0, 2, 3]]])
    Fp = np.vectorize(m.get)(F)
    an, ar = tri_jacobian_aniso(low[F], low[Fp])
    return wq(an, ar, 50), wq(an, ar, 95)


def icp_similarity(A, B, iters=60):
    """the similarity taking cloud A onto cloud B with no correspondence: PCA starts (4 sign choices, right-handed), ICP
    with Umeyama's scale; returns (symmetric rms / B's size, the scale, A mapped)"""
    from scipy.spatial import cKDTree
    tb = cKDTree(B)
    ca, cb = A.mean(0), B.mean(0)
    Ua = np.linalg.svd(A - ca, full_matrices=False)[2]
    Ub = np.linalg.svd(B - cb, full_matrices=False)[2]
    sa = np.sqrt(((A - ca) ** 2).sum(1).mean())
    sb = np.sqrt(((B - cb) ** 2).sum(1).mean())
    best = None
    for s0 in (1.0, -1.0):
        for s1 in (1.0, -1.0):
            D = np.diag([s0, s1, 1.0])
            R = Ub.T @ D @ Ua
            if np.linalg.det(R) < 0:
                D[2, 2] = -1.0
                R = Ub.T @ D @ Ua
            X = (A - ca) @ R.T * (sb / sa) + cb
            for _ in range(iters):
                _, j = tb.query(X)
                s_, R_, t_, _ = umeyama(X, B[j])
                X = s_ * X @ R_.T + t_
            d, _ = tb.query(X)
            d2, _ = cKDTree(X).query(B)
            rms = float(np.sqrt(0.5 * (d ** 2).mean() + 0.5 * (d2 ** 2).mean()))
            if best is None or rms < best[0]:
                best = (rms, float(np.sqrt(((X - X.mean(0)) ** 2).sum(1).mean()) / sa), X)
    return best[0] / size_of(B), best[1], best[2]


# ============================================================================================ the repeats
def digit_weights(low, bmap, c2h, side='L'):
    """per digit the summed hm08 skin weight of its bones (finger<d>-*.<side> / toe<d>-*.<side>) per LOW vertex"""
    from . import human_ref as HR
    d = HR.mh_data()
    W = d['W'].tocsc()
    h_of = -np.ones(len(low), np.int64)
    ok = np.asarray(c2h) >= 0
    h_of[np.asarray(bmap)[ok]] = np.asarray(c2h)[ok]
    out = {}
    for dg in DIGITS:
        js = [j for j, b in enumerate(d['bones']) if b.startswith(dg + '-') and b.endswith('.' + side)]
        wv = np.asarray(W[:, js].sum(1)).ravel()
        x = np.zeros(len(low))
        x[h_of >= 0] = wv[h_of[h_of >= 0]]
        out[dg] = x
    return out


def find_digits(low, Q, dw, log=print):
    """per digit (the left side): its root ring (the most proximal closed edge loop round its axis that splits off a
    piece holding >= 90 % of the digit's weight region) and its piece (the quads distal to the ring). Returns {digit:
    dict(root, quads)}"""
    from . import human_hmcage as HC2
    from . import human_topo as HT
    T = HT.Topo(Q, len(low))
    loops = HC2.all_loops(T, maxn=200)
    out = {}
    for dg in DIGITS:
        w = dw[dg]
        reg = w > 0.5
        if reg.sum() < 10:
            continue
        P = low[reg]
        c = P.mean(0)
        ax = np.linalg.svd(P - c)[2][0]
        far = P[np.argmax(np.linalg.norm(P - c, axis=1))]
        if (far - c) @ ax < 0:
            ax = -ax
        cand = []
        for L in loops:
            if len(L) > 24 or not (w[L] > 0.05).all():
                continue
            info = HC2.loop_info(low, L)
            if abs(info['n'] @ ax) < 0.7 or info['r'] > 20.0:
                continue
            if np.linalg.norm((info['c'] - c) - ((info['c'] - c) @ ax) * ax) > 12.0:
                continue
            cand.append((float((info['c'] - c) @ ax), L))
        cand.sort(key=lambda t: t[0])
        for t, L in cand:
            rset = set((min(a, b), max(a, b)) for a, b in zip(L, L[1:] + L[:1]))
            seen = np.zeros(len(Q), bool)
            best = None
            for q0 in np.nonzero(reg[Q].any(1))[0]:
                if seen[q0]:
                    continue
                st, comp = [q0], []
                seen[q0] = True
                while st and len(comp) < 6000:
                    q = st.pop()
                    comp.append(q)
                    row = Q[q].tolist()
                    for k in range(4):
                        e = (min(row[k], row[(k + 1) % 4]), max(row[k], row[(k + 1) % 4]))
                        if e in rset:
                            continue
                        for qj in T.emap[e]:
                            if not seen[qj]:
                                seen[qj] = True
                                st.append(qj)
                hold = reg[np.unique(Q[comp])].sum() / reg.sum()
                if best is None or hold > best[0]:
                    best = (hold, comp)
            if best is not None and best[0] >= 0.9 and len(best[1]) < 1200:
                out[dg] = dict(root=[int(v) for v in L], quads=np.array(sorted(best[1]), np.int64),
                               hold=float(best[0]))
                break
    log(f'[stack] digits: ' + ', '.join(f'{d} K{len(v["root"])} {len(v["quads"])}q' for d, v in out.items()))
    return out


def nail_patches(Q, recs, side='L'):
    out = {}
    for dg, nm in NAIL_OF.items():
        r = recs['nails'].get(f'nail_{nm}_{side}')
        if r is None:
            continue
        vs = set(r['loop']) | set(r['inner'])
        out[dg] = dict(quads=np.nonzero(np.isin(Q, list(vs)).all(1))[0], root=[int(v) for v in r['loop']])
    return out


def digit_segments(low, Q, dg, digit, w_of, nail_quads=()):
    """a digit's quads (digit: dict(quads)) split by hm08's phalanx bones: the heaviest of finger<d>-<k> / toe<d>-<k> over
    each quad's corners, the nail patch left out (it is no skin of a segment). w_of(prefix) -> per LOW vertex that bone's
    weight. Returns {'<digit>-<k>': quads}"""
    from . import human_ref as HR
    bones = sorted({b.split('-')[1].split('.')[0] for b in HR.mh_data()['bones'] if b.startswith(dg + '-') and
                    b.endswith('.L')})
    nq = set(int(q) for q in nail_quads)
    qs = np.array([q for q in np.asarray(digit['quads']).tolist() if q not in nq], np.int64)
    lab = np.argmax(np.stack([w_of(f'{dg}-{b}')[Q[qs]].sum(1) for b in bones], 1), 1)
    return {f'{dg}-{b}': qs[lab == k] for k, b in enumerate(bones) if (lab == k).sum() >= 4}


def repeat_groups(low, Q, pieces, kind, log=print, primaries=None):
    """the isomorphic groups among the pieces (dict name -> dict(quads, root)) and each copy's map to its primary.
    primaries: names allowed as a group's primary (the plan's), else the largest member. Returns a list of
    dict(kind, primary, members, signature, maps {copy: {copy vertex: primary vertex}})"""
    from . import human_topo as HT
    T = HT.Topo(Q, len(low))
    qa = 0.5 * np.linalg.norm(np.cross(low[Q[:, 2]] - low[Q[:, 0]], low[Q[:, 3]] - low[Q[:, 1]]), axis=1)
    by = collections.defaultdict(list)
    for nm, p in pieces.items():
        by[signature(Q, p['quads'], T.nbr)].append(nm)
    groups = []
    for sig, names in by.items():
        if len(names) < 2:
            continue
        allowed = [n for n in names if primaries is None or n in primaries] or names
        prim = max(allowed, key=lambda n: float(qa[pieces[n]['quads']].sum()))
        maps = {}
        for o in names:
            if o == prim:
                continue
            m = iso_map(Q, low, pieces[o]['quads'], pieces[o]['root'], pieces[prim]['quads'], pieces[prim]['root'])
            if m is not None:
                maps[o] = m
        groups.append(dict(kind=kind, primary=prim, members=sorted(names), signature=[int(sig[0]), int(sig[1])],
                           maps=maps))
        log(f'[stack] {kind} group {sorted(names)} (signature {sig[0]} quads, {sig[1]} vertices): primary {prim}, '
            f'isomorphic copies {sorted(maps)}')
    return groups


# ============================================================================================ the drivers (Warp)
_K = {}


def _kernels():
    if _K:
        return _K
    import warp as wp

    @wp.func
    def cosdir(n: wp.vec3, r1: float, r2: float):
        a = wp.vec3(0.0, 0.0, 1.0)
        if wp.abs(n[2]) > 0.9:
            a = wp.vec3(1.0, 0.0, 0.0)
        t1 = wp.normalize(wp.cross(n, a))
        t2 = wp.cross(n, t1)
        phi = 6.283185307 * r1
        sr = wp.sqrt(r2)
        return wp.normalize(t1 * (sr * wp.cos(phi)) + t2 * (sr * wp.sin(phi)) + n * wp.sqrt(wp.max(0.0, 1.0 - r2)))

    @wp.func
    def conedir(n: wp.vec3, r1: float, r2: float, cmax: float):
        a = wp.vec3(0.0, 0.0, 1.0)
        if wp.abs(n[2]) > 0.9:
            a = wp.vec3(1.0, 0.0, 0.0)
        t1 = wp.normalize(wp.cross(n, a))
        t2 = wp.cross(n, t1)
        ct = 1.0 - r2 * (1.0 - cmax)
        st = wp.sqrt(wp.max(0.0, 1.0 - ct * ct))
        phi = 6.283185307 * r1
        return wp.normalize(t1 * (st * wp.cos(phi)) + t2 * (st * wp.sin(phi)) + n * ct)

    @wp.kernel
    def k_drivers(mesh: wp.uint64, vn: wp.array(dtype=wp.vec3), fidx: wp.array(dtype=wp.int32),
                  pts: wp.array(dtype=wp.vec3), seed: int, n_ao: int, ao_r: float, n_cav: int, cav_r: float,
                  n_thk: int, thk_max: float, cmax: float, o_ao: wp.array(dtype=float), o_cav: wp.array(dtype=float),
                  o_thk: wp.array(dtype=float)):
        i = wp.tid()
        q = wp.mesh_query_point_no_sign(mesh, pts[i], 0.05)
        if not q.result:
            return
        P = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        j0 = fidx[3 * q.face]
        j1 = fidx[3 * q.face + 1]
        j2 = fidx[3 * q.face + 2]
        n = wp.normalize(vn[j0] * q.u + vn[j1] * q.v + vn[j2] * (1.0 - q.u - q.v))
        st = wp.rand_init(seed, i)
        o = P + n * 0.0001
        vis = float(0.0)
        for k in range(n_ao):
            h = wp.mesh_query_ray(mesh, o, cosdir(n, (float(k % 16) + wp.randf(st)) / 16.0,
                                                  (float(k / 16) + wp.randf(st)) / float(n_ao / 16)), ao_r)
            if not h.result:
                vis += 1.0
        o_ao[i] = vis / float(n_ao)
        vc = float(0.0)
        for k in range(n_cav):
            h = wp.mesh_query_ray(mesh, o, cosdir(n, wp.randf(st), wp.randf(st)), cav_r)
            if not h.result:
                vc += 1.0
        o_cav[i] = vc / float(n_cav)
        oi = P - n * 0.0001
        ds = wp.vector(dtype=float, length=32)
        for k in range(32):
            ds[k] = thk_max
        for k in range(n_thk):
            h = wp.mesh_query_ray(mesh, oi, conedir(-n, wp.randf(st), wp.randf(st), cmax), thk_max)
            if h.result:
                ds[k] = h.t
        for a in range(1, 32):
            x = ds[a]
            b = a - 1
            while b >= 0 and ds[b] > x:
                ds[b + 1] = ds[b]
                b = b - 1
            ds[b + 1] = x
        o_thk[i] = 0.5 * (ds[15] + ds[16])
    _K['drivers'] = k_drivers
    return _K


class Drivers:
    """AO / cavity / thickness at points on the HIGH's level-4 limit (V4 mm, Q4), the bake's definitions with more rays"""

    def __init__(self, V4, Q4):
        import warp as wp
        self.wp = wp
        V = (np.asarray(V4, np.float64) / 1000.0).astype(np.float32)
        Q = np.asarray(Q4, np.int64)
        F = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]).astype(np.int32)
        fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]).astype(np.float64)
        vn = np.zeros((len(V), 3))
        for k in range(3):
            np.add.at(vn, F[:, k], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)
        self.vn_np = vn
        self.V_np = V.astype(np.float64) * 1000.0
        self.mesh = wp.Mesh(points=wp.array(V, dtype=wp.vec3), indices=wp.array(F.ravel(), dtype=wp.int32))
        self.vn = wp.array(vn.astype(np.float32), dtype=wp.vec3)
        self.fid = wp.array(F.ravel(), dtype=wp.int32)
        self.k = _kernels()['drivers']

    def at(self, P_mm, seed):
        wp = self.wp
        pts = wp.array((np.asarray(P_mm, np.float64) / 1000.0).astype(np.float32), dtype=wp.vec3)
        n = len(P_mm)
        ao, cav, thk = wp.zeros(n, dtype=float), wp.zeros(n, dtype=float), wp.zeros(n, dtype=float)
        wp.launch(self.k, dim=n, inputs=[self.mesh.id, self.vn, self.fid, pts, int(seed), 256, 0.025, 128, 0.0025, 32,
                                         0.05, float(np.cos(np.radians(25.0))), ao, cav, thk])
        return ao.numpy().astype(np.float64), cav.numpy().astype(np.float64), thk.numpy().astype(np.float64) * 1000.0


def vertex_area(low, Q):
    qa = 0.5 * np.linalg.norm(np.cross(low[Q[:, 2]] - low[Q[:, 0]], low[Q[:, 3]] - low[Q[:, 1]]), axis=1)
    va = np.zeros(len(low))
    for k in range(4):
        np.add.at(va, Q[:, k], qa / 4.0)
    return va


def measure_pair(low, Q, mir, drv, quads_c, m=None, cloud_p=None, quads_p=None):
    """the measures of a copy against its primary: with an isomorphism m at corresponding vertices; without one (a
    look-alike), through the ICP similarity (each copy vertex against the primary's level-4 point nearest its mapped
    position). Returns a dict"""
    va = vertex_area(low, Q)
    vo = np.unique(Q[quads_c])
    w = va[vo]
    out = {}
    if m is not None:
        vp = np.array([m[int(v)] for v in vo], np.int64)
        s, R, t, rms = umeyama(low[vo], low[vp])
        out.update(residual_rel=round(rms / size_of(low[vp]), 4), scale_of_primary=round(1.0 / s, 4))
        a50, a95 = stacked_aniso(low, Q, quads_c, m)
        out['shared_aniso'] = dict(p50=round(a50, 3), p95=round(a95, 3))
        Pp = low[vp]
    else:
        vp_all = np.unique(Q[quads_p])
        r, s, X = icp_similarity(low[vo], low[vp_all])
        out.update(icp_rms_rel=round(r, 4), scale_of_primary=round(1.0 / s, 4))
        from scipy.spatial import cKDTree
        _, j = cKDTree(low[vp_all]).query(X)
        Pp = low[vp_all][j]
    ao_o, cav_o, thk_o = drv.at(low[vo], 1)
    ao_p, cav_p, thk_p = drv.at(Pp, 2)
    ao_m, cav_m, _ = drv.at(low[np.asarray(mir)[vo]], 3)
    d_ao, n_ao = np.abs(ao_o - ao_p), np.abs(ao_o - ao_m)
    d_cav, n_cav = np.abs(cav_o - cav_p), np.abs(cav_o - cav_m)
    r_thk = np.abs(thk_o - thk_p) / np.maximum(thk_p, 1e-6)
    out.update(area_cm2=round(float(w.sum()) / 100.0, 2),
               dAO=dict(p50=round(wq(d_ao, w, 50), 4), p95=round(wq(d_ao, w, 95), 4), max=round(float(d_ao.max()), 4)),
               ao_weight=round(wq(d_ao, w, 95) * float(np.sqrt(w.sum() / 100.0)), 4),
               noise_AO_p95=round(wq(n_ao, w, 95), 4),
               dCavity=dict(p50=round(wq(d_cav, w, 50), 4), p95=round(wq(d_cav, w, 95), 4)),
               noise_cavity_p95=round(wq(n_cav, w, 95), 4),
               dThickness_rel=dict(p50=round(wq(r_thk, w, 50), 3), p95=round(wq(r_thk, w, 95), 3)))
    out['_dAO_v'] = (vo, d_ao)
    return out


def decide_ao(meas, isomorphic):
    """the first two tests of the rule (the AO, the topology): (True, None) = a stack candidate (its shape is checked in
    the UV step), else (False, [reasons])"""
    why = []
    if meas['ao_weight'] > AO_WEIGHT_BAR:
        why.append(f'ao: weight {meas["ao_weight"]:.3f} > {AO_WEIGHT_BAR} (|dAO| p95 {meas["dAO"]["p95"]:.3f} x sqrt('
                   f'{meas["area_cm2"]} cm2); noise floor {meas["noise_AO_p95"]:.3f})')
    if not isomorphic:
        why.append('topology: not isomorphic to the primary (a shared shell is laid on corresponding vertices; '
                   'a stack would need a topology edit)')
    return (not why), (why or None)


# ============================================================================================ the shared shell (UV step)
def patch_boundary(Qc):
    """the boundary loop of a disk patch (quads Qc, the winding's direction) and its corners (boundary vertices in 1 or
    3 of the patch's quads: where a quad patch's outline turns)"""
    und = collections.Counter()
    for q in np.asarray(Qc).tolist():
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            und[(min(a, b), max(a, b))] += 1
    nxt = {}
    for q in np.asarray(Qc).tolist():
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            if und[(min(a, b), max(a, b))] == 1:
                nxt[a] = b
    start = min(nxt)
    loop = [start]
    while nxt[loop[-1]] != start:
        loop.append(nxt[loop[-1]])
    nq = collections.Counter(v for q in np.asarray(Qc).tolist() for v in q)
    corners = [v for v in loop if nq[v] in (1, 3)]
    return loop, corners


def anchored_chart(Vc, Qc_local, m_local, uv_prim, log=None):
    """THE SHARED SHELL of a stacked copy: the copy's own surface (Vc (n, 3) its vertices, Qc_local its quads in local
    ids; m_local copy local id -> the primary's local id) mapped into the primary's chart OUTLINE (uv_prim: the
    primary's UVs by its local ids, page units): the corners anchored at the primary's corners, every other boundary
    vertex on the primary's boundary polyline at the copy's own arc-length fraction between its corners, the inside by
    the house's pinned ARAP from a harmonic start. Returns (uv (n, 2), dict(aniso95, scale p10 / p90, flipped))"""
    from . import stag_beetle_uv as BU
    Qc_local = np.asarray(Qc_local, np.int64)
    loop, corners = patch_boundary(Qc_local)
    if len(corners) < 3:
        corners = loop[::max(len(loop) // 4, 1)][:4]
    n = len(Vc)
    U = np.full((n, 2), np.nan)
    cpos = [loop.index(c) for c in corners]
    order = sorted(range(len(cpos)), key=lambda i: cpos[i])
    cpos = [cpos[i] for i in order]
    corners = [corners[i] for i in order]
    # the primary's boundary as its own loop through the corresponding vertices
    for ci in range(len(corners)):
        a_i, b_i = cpos[ci], cpos[(ci + 1) % len(cpos)]
        seg = [loop[(a_i + k) % len(loop)] for k in range((b_i - a_i) % len(loop) + 1)]
        segp = [m_local[v] for v in seg]
        L3 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Vc[seg], axis=0), axis=1))])
        t = L3 / max(L3[-1], 1e-12)
        Pp = uv_prim[segp]
        Lp = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))])
        tp = Lp / max(Lp[-1], 1e-12)
        for k, v in enumerate(seg):
            j = int(np.clip(np.searchsorted(tp, t[k]) - 1, 0, len(tp) - 2))
            f = (t[k] - tp[j]) / max(tp[j + 1] - tp[j], 1e-12)
            U[v] = Pp[j] * (1.0 - f) + Pp[j + 1] * f
    pin = np.array(loop, np.int64)
    F = np.concatenate([Qc_local[:, [0, 1, 2]], Qc_local[:, [0, 2, 3]]])
    # a harmonic start (uniform weights over the quads' edges) with the boundary fixed, then the pinned ARAP
    free = np.setdiff1d(np.arange(n), pin)
    if len(free):
        import scipy.sparse as sp
        import scipy.sparse.linalg as spl
        E = set()
        for q in Qc_local.tolist():
            for k in range(4):
                a, b = q[k], q[(k + 1) % 4]
                E.add((min(a, b), max(a, b)))
        E = np.array(sorted(E))
        Wm = sp.coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()
        L = sp.diags(np.asarray(Wm.sum(1)).ravel()) - Wm
        Lff = L[free][:, free].tocsc()
        Lfb = L[free][:, pin]
        for c in range(2):
            U[free, c] = spl.spsolve(Lff, -(Lfb @ U[pin, c]))
        U = BU.arap_pinned(Vc, F, U, pin, U[pin], iters=40)
    met = BU.chart_metrics(Vc, F, U)
    return U, met


def engine_frames(V, F, UV, N):
    """per vertex the engine's TBN inputs (forge/bake.low_frames: the TANGENT x y z w the glb exports)"""
    from .. import bake as BK
    _, TAN = BK.low_frames(V, F, UV, N)
    return TAN


def nail_normals(low, vs, high_normal, inset_mm=0.6):
    """THE NAIL AS ITS OWN SMOOTHING GROUP (the module's docstring): per vertex of a nail patch (vs: its LOW vertex ids;
    low mm) the high's normal read inset_mm inside the plate, toward the patch's centre (the rim's own point sits on
    the fold, where the high's normal turns fast). Returns (len(vs), 3) unit normals"""
    P = np.asarray(low)[np.asarray(vs)]
    c = P.mean(0)
    d = c - P
    return high_normal(P + inset_mm * d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9))


def high_normals_near(V4, Q4, centres, radius_mm=8.0):
    """a nearest-vertex normal lookup on the level-4 limit (V4 mm, Q4), built only within radius_mm of the given points
    (nails and tips): returns high_normal(P mm) -> unit normals"""
    from scipy.spatial import cKDTree
    near = cKDTree(np.asarray(centres)).query(V4, distance_upper_bound=radius_mm)[0] < radius_mm
    Qs = Q4[near[Q4[:, 0]]]
    fn = np.cross(V4[Qs[:, 2]] - V4[Qs[:, 0]], V4[Qs[:, 3]] - V4[Qs[:, 1]])
    vn = np.zeros_like(V4)
    for k in range(4):
        np.add.at(vn, Qs[:, k], fn)
    vs = np.unique(Qs)
    nrm = vn[vs] / np.maximum(np.linalg.norm(vn[vs], axis=1, keepdims=True), 1e-20)
    tree = cKDTree(V4[vs])
    return lambda P: nrm[tree.query(P)[1]]


def decode_error(Vp, Fp, UVp, Np, TANp, Vc, Fc, UVc, Nc, TANc, high_normal, n_samples=6, R=None):
    """THE DECODE CHECK of a stacked copy, before any bake: on sample points of the copy's triangles, the primary's
    tangent normal at the same UV (its high's normal written in its own engine frame) read back in the copy's engine
    frame, against the copy's own high normal there (high_normal(P mm (k, 3)) -> unit normals: the level-4 limit's).
    The primary decoded on itself is the method's own floor. Returns (copy errors deg, self errors deg, the copy's FLAT
    errors deg: its own LOW normals against its high, the map left out; the INTRINSIC difference deg: the primary's high
    normal rotated by R, the similarity primary -> copy, against the copy's own at the same UV; None without R)"""
    rng = np.random.default_rng(7)

    def frames_at(V, F, UV, N, TAN, f, b):
        c = F[f]
        Nn = N[c] / np.linalg.norm(N[c], axis=-1, keepdims=True)
        Tn = TAN[c][..., :3] / np.linalg.norm(TAN[c][..., :3], axis=-1, keepdims=True)
        w = TAN[c][..., 3]
        n = (b[..., None] * Nn).sum(1)
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        t = (b[..., None] * Tn).sum(1)
        t /= np.linalg.norm(t, axis=1, keepdims=True)
        bb = (b[..., None] * (np.cross(Nn, Tn) * w[..., None])).sum(1)
        bb /= np.linalg.norm(bb, axis=1, keepdims=True)
        P = (b[..., None] * V[c]).sum(1)
        u = (b[..., None] * UV[c]).sum(1)
        return P, u, t, bb, n

    def locate(UVt, Ft, u):
        """the triangle of the layout holding each point u, and its barycentrics (nearest triangle if outside)"""
        A, B, C = UVt[Ft[:, 0]], UVt[Ft[:, 1]], UVt[Ft[:, 2]]
        out_f = np.zeros(len(u), np.int64)
        out_b = np.zeros((len(u), 3))
        for i, p in enumerate(u):
            den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
            den = np.where(np.abs(den) < 1e-20, 1e-20, den)
            l0 = ((B[:, 1] - C[:, 1]) * (p[0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (p[1] - C[:, 1])) / den
            l1 = ((C[:, 1] - A[:, 1]) * (p[0] - C[:, 0]) + (A[:, 0] - C[:, 0]) * (p[1] - C[:, 1])) / den
            l2 = 1.0 - l0 - l1
            worst = np.minimum(np.minimum(l0, l1), l2)
            f = int(np.argmax(worst))
            bb = np.clip(np.array([l0[f], l1[f], l2[f]]), 0.0, 1.0)
            out_f[i] = f
            out_b[i] = bb / bb.sum()
        return out_f, out_b

    def run(Vs, Fs, UVs, Ns, Ts):
        fsel = np.repeat(np.arange(len(Fs)), n_samples)
        r = rng.random((len(fsel), 2))
        r = np.where(r.sum(1, keepdims=True) > 1.0, 1.0 - r, r)
        bary = np.column_stack([1.0 - r.sum(1), r[:, 0], r[:, 1]]) * 0.96 + 0.04 / 3.0
        P_c, u, t_c, b_c, n_c = frames_at(Vs, Fs, UVs, Ns, Ts, fsel, bary)
        fp, bp = locate(UVp, Fp, u)
        P_p, _, t_p, b_p, n_p = frames_at(Vp, Fp, UVp, Np, TANp, fp, bp)
        nh_p = high_normal(P_p)
        nts = np.stack([(nh_p * t_p).sum(1), (nh_p * b_p).sum(1), (nh_p * n_p).sum(1)], 1)
        dec = t_c * nts[:, :1] + b_c * nts[:, 1:2] + n_c * nts[:, 2:3]
        dec /= np.linalg.norm(dec, axis=1, keepdims=True)
        nh_c = high_normal(P_c)
        intr = None
        if R is not None:
            intr = np.degrees(np.arccos(np.clip((((R @ nh_p.T).T) * nh_c).sum(1), -1.0, 1.0)))
        return (np.degrees(np.arccos(np.clip((dec * nh_c).sum(1), -1.0, 1.0))),
                np.degrees(np.arccos(np.clip((n_c * nh_c).sum(1), -1.0, 1.0))), intr)
    e_c, flat_c, intr_c = run(Vc, Fc, UVc, Nc, TANc)
    return e_c, run(Vp, Fp, UVp, Np, TANp)[0], flat_c, intr_c


def stack_pair(Vp, Fp, uvp, Np, Vc, Qc_local, Fc, m_local, Nc, high_normal):
    """one copy against one primary (charts in the same units): its anchored chart and the two checks. Returns (uv,
    a dict of the measures, the list of reasons it cannot stack: empty when it can)"""
    uv_c, met = anchored_chart(Vc, Qc_local, m_local, uvp)
    TANp = engine_frames(Vp / 1000.0, Fp, uvp, Np)
    TANc = engine_frames(Vc / 1000.0, Fc, uv_c, Nc)
    idx = np.array([m_local[j] for j in range(len(Vc))], np.int64)
    R = umeyama(Vp[idx], Vc)[1]
    err, self_err, flat, intr = decode_error(Vp, Fp, uvp, Np, TANp, Vc, Fc, uv_c, Nc, TANc, high_normal, R=R)
    e95, f95, i95 = float(np.percentile(err, 95)), float(np.percentile(flat, 95)), float(np.percentile(intr, 95))
    row = dict(anchored_aniso95=round(float(met['aniso95']), 3), anchored_scale=[round(float(met['s10']), 3),
                                                                                  round(float(met['s90']), 3)],
               flipped=int(met['flipped']), decode_p50=round(float(np.median(err)), 3), decode_p95=round(e95, 3),
               intrinsic_p95=round(i95, 3), flat_p95=round(f95, 3),
               decode_self_p95=round(float(np.percentile(self_err, 95)), 3))
    why = []
    if met['flipped'] or met['aniso95'] > ANISO_BAR:
        why.append(f'shape: the anchored chart\'s anisotropy p95 {met["aniso95"]:.3f} (bar {ANISO_BAR}), flipped '
                   f'{met["flipped"]}')
    if e95 >= i95:
        why.append(f'decode: the shared map p95 {e95:.2f} deg is no closer to the copy\'s own high than its primary is '
                   f'({i95:.2f})')
    return uv_c, row, why


# ============================================================================================ the gate
def gate(groups, shells, reasons, not_repeats=None):
    """THE STACK GATE (the lead's definition): every member of every repeat group shares its primary's shells
    (shells[kind:member] == 'stacked:<primary>') or keeps its own with a recorded AO reason (reasons[kind:member] holds a
    line starting 'ao:'). not_repeats {kind:member: evidence}: parts measured not to be repeats, listed with their
    evidence and outside the groups. Returns (ok, rows)"""
    rows = []
    ok = True
    for g in groups:
        for mbr in g['members']:
            if mbr == g['primary']:
                rows.append(dict(kind=g['kind'], member=mbr, role='primary', shells='own'))
                continue
            key = f'{g["kind"]}:{mbr}'
            sh = shells.get(key, 'own')
            why = reasons.get(key)
            good = sh.startswith('stacked') or any(str(w).startswith('ao:') for w in (why or []))
            ok &= good
            rows.append(dict(kind=g['kind'], member=mbr, role='copy', primary=g['primary'], shells=sh, reasons=why,
                             ok=good))
    for key, ev in (not_repeats or {}).items():
        kind, mbr = key.split(':')
        good = bool(ev)
        ok &= good
        rows.append(dict(kind=kind, member=mbr, role='not a repeat', shells='own', reasons=[ev], ok=good))
    return ok, rows
