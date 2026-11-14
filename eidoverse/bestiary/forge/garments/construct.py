"""THE CONSTRUCTION on the draped cloth: what a garment is made of besides its panels.

  rims      every opening turned back (a hem, a sleeve's hem, a cuff's edge, a neckband, a waistband's top): the edge
            row doubled inward by the cloth's thickness and up the inside by the hem's width, so an opening shows its
            folded edge and its inside, never a paper-thin edge (the inner strip shares the outer hem's texels)
  collar    the shirts' turn-down collar on the neckline: a STAND (3.2 cm, hugging the neck 2 mm off) and a FALL folded
            over it (4.2 cm at the back, longer to the COLLAR POINTS at the front, a V between them), kept 2 mm over the
            shirt's own surface
  buttons   the placket's (7 down the front from the collar's band, 9.5 cm apart), the collar band's and each cuff's: 11 mm
            four-hole discs (the holes are the bake's), proud of the cloth by 2 mm, riding the closest cloth point
The SEAMS (shoulder, side, armscye, inseam / outseam, the placket's edges, the yoke) are lines in UV space at the islands'
borders and the placket's offsets: the bake draws their ridges and stitches (maps.py).
"""
import numpy as np

from . import meshops as mo
from .body import vertex_normals


def rim(V, F, loop, width, thick):
    """the turn-back strip inside an opening: returns (new vertices, new faces (indices into V + new), map new -> the
    outer vertex whose texel it shares)"""
    n = vertex_normals(V, F)
    A = mo.adjacency(F, len(V))
    lset = set(int(i) for i in loop)
    k = len(loop)
    # (B2b) the strip's inward direction from the LOOP's own tangent (n x t), only its sign from the neighbours: the
    # neighbours' mean alone zigzagged where the opening curves hard (the crew neck's back: a frayed band in the engine)
    P = V[loop]
    t = np.roll(P, -2, 0) + np.roll(P, -1, 0) - np.roll(P, 1, 0) - np.roll(P, 2, 0)
    nl = n[loop].copy()
    for _ in range(3):
        nl = 0.5 * nl + 0.25 * (np.roll(nl, 1, 0) + np.roll(nl, -1, 0))
    nl /= np.linalg.norm(nl, axis=1, keepdims=True) + 1e-12
    dirs = np.cross(nl, t)
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True) + 1e-12
    ref = []
    for v in loop:
        nb = [j for j in A.indices[A.indptr[v]:A.indptr[v + 1]] if j not in lset]
        ref.append((V[nb].mean(0) - V[v]) if nb else -n[v])
    if np.sum(np.einsum('ij,ij->i', dirs, np.array(ref))) < 0:
        dirs = -dirs
    for _ in range(3):
        dirs = 0.5 * dirs + 0.25 * (np.roll(dirs, 1, 0) + np.roll(dirs, -1, 0))
    dirs -= nl * np.einsum('ij,ij->i', dirs, nl)[:, None]
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True) + 1e-12
    base = len(V)
    r1 = V[loop] - n[loop] * thick                        # the fold: straight under the edge
    r2 = V[loop] - n[loop] * thick + dirs * width         # the hem's inside, up the cloth
    NV = np.concatenate([r1, r2])
    NF = []
    for i in range(k):
        a, b = loop[i], loop[(i + 1) % k]
        c, d = base + i, base + (i + 1) % k
        e, f = base + k + i, base + k + (i + 1) % k
        NF += [(a, c, b), (b, c, d), (c, e, d), (d, e, f)]
    NF = np.array(NF, np.int64)
    # the inside strip faces the body (against the cloth's outward normal)
    AV = np.concatenate([V, NV])
    inner = NF[2::4]
    fn = np.cross(AV[inner[:, 1]] - AV[inner[:, 0]], AV[inner[:, 2]] - AV[inner[:, 0]])
    if np.sum(np.einsum('ij,ij->i', fn, -n[loop])) < 0:
        NF = NF[:, ::-1]
    share = np.concatenate([loop, loop])
    return NV, NF, share


def collar(neck_loop_pts, neck_axis_pt, up, shirt_V, shirt_F, stand=0.032, fall=0.042, point=0.075, n_around=None):
    """the stand and fall on the neckline (the loop's points in order round the neck); returns (V, F, rows, cols)"""
    P = np.asarray(neck_loop_pts, float)
    P = np.concatenate([P, P[:1]])          # the collar opened at the loop's start (centre back): a strip, one island
    k = len(P)
    up = up / np.linalg.norm(up)
    out = P - neck_axis_pt
    out -= up[None, :] * (out @ up)[:, None]
    out /= np.linalg.norm(out, axis=1, keepdims=True)
    ang = np.arctan2(out[:, 0], out[:, 2])                 # 0 at the front
    front = np.clip(1.0 - np.abs(ang) / np.radians(55), 0.0, 1.0) ** 1.5
    rows = []
    rows.append(P + out * 0.0005)
    rows.append(P + up * (stand * 0.5) - out * 0.002)
    rows.append(P + up * stand - out * 0.001)                         # the stand's top
    rows.append(P + up * (stand + 0.003) + out * 0.003)               # the fold
    drop = fall + (point - fall) * front
    vee = np.clip(np.abs(ang) / np.radians(9), 0.0, 1.0)              # the V between the points
    drop = drop * (0.15 + 0.85 * vee)
    for s in (0.35, 0.7, 1.0):
        rows.append(P + up[None, :] * (stand + 0.003 - drop * s)[:, None]
                    + out * (0.006 + 0.012 * s + 0.010 * front * s)[:, None])
    V = np.concatenate(rows)
    nr = len(rows)
    # keep the fall over the shirt (2 mm)
    q, _, _, sd = mo.closest_on_mesh(shirt_V, shirt_F, V)
    fallm = np.repeat(np.arange(nr) >= 4, k)
    low = fallm & (sd < 0.002)
    nrm = (V - q) / (np.abs(sd)[:, None] + 1e-12) * np.sign(sd)[:, None]
    V[low] = q[low] + nrm[low] * 0.002
    F = []
    for i in range(nr - 1):
        for j in range(k - 1):
            a, b = i * k + j, i * k + j + 1
            F += [(a, b, a + k), (b, b + k, a + k)]
    F = np.array(F, np.int64)
    return V, F, nr, k


COLLAR = {   # (B2b) a point collar's measures (stand height, the fall's width at the back, the point's length, the tip's
    # distance from the centre line, the stand's gap to the neck at its top)
    'F': dict(stand=0.030, fall=0.040, point=0.068, tip_x=0.052, gap=0.0045),
    'M': dict(stand=0.034, fall=0.044, point=0.075, tip_x=0.058, gap=0.0045),
}


def collar2(neck_pts, axis_c, up, skin, shirt, dims, n_col=120, ns=4, nf=7):
    """(B2b) THE SHIRT COLLAR, stand and fall (round 1's strip read as a flared band: no fall over the stand, no
    points). neck_pts: the shirt's neckline loop (A-pose, any order); axis_c, up: the neck's axis; skin: (V, F) the
    neck's skin (skin_HEAD + skin_BODY, A-pose); shirt: (V, F) the draped shirt; dims: COLLAR[sex].
      the STAND  rises from the neckline `stand` along the neck, drawn in to `gap` off the skin at its top (a stand is
                 cut smaller at the top than at the seam), closed at the centre front (the band's button)
      the FALL   turns over at the stand's top (the roll), goes down over the stand 2.5 mm off it, past the neckline and
                 onto the shirt 2.5 mm over it (a march along the shirt's surface away from the neck), `fall` wide at
                 the back, widening over the shoulders to the POINTS (`point` long, their tips `tip_x` off the centre
                 line); its front edges run from the roll beside the button down to the tips: the collar's V
    Returns (V, F, tag) with tag = dict(part (0 stand, 1 fall), t (the stand's height / the fall's depth, 0-1),
    top_drop (m below the stand's top along the neck, the stand's points), front (the band's front point))."""
    from scipy.spatial import cKDTree
    up = up / np.linalg.norm(up)
    P = np.asarray(neck_pts, float)

    def ang_of(Q):
        o = Q - axis_c
        o = o - np.outer(o @ up, up)
        return np.arctan2(o[:, 0], o[:, 2])              # 0 at the front, + the body's left (+X)
    a = ang_of(P)
    o = np.argsort(a)
    a, P = a[o], P[o]
    a_ext = np.concatenate([a - 2 * np.pi, a, a + 2 * np.pi])
    P_ext = np.concatenate([P, P, P])

    def neckline(ang):
        return np.column_stack([np.interp(ang, a_ext, P_ext[:, k]) for k in range(3)])
    Vs, Fs = skin
    Ns = _vnormals(Vs, Fs)

    def to_skin(Q, d):
        q, t, bc, _ = mo.closest_on_mesh(Vs, Fs, Q)
        n = np.einsum('nk,nkj->nj', bc, Ns[Fs[t]])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        return q + n * np.asarray(d)[:, None], n
    # ---------------------------------------------------------------- the stand (closed at the centre front)
    e0 = 0.012
    ang_s = np.linspace(e0, 2 * np.pi - e0, n_col)
    ang_s = np.where(ang_s > np.pi, ang_s - 2 * np.pi, ang_s)
    B0 = neckline(ang_s)
    _, n0 = to_skin(B0, np.zeros(len(B0)))
    q0, _, _, _ = mo.closest_on_mesh(Vs, Fs, B0)
    d0 = np.maximum(np.einsum('ij,ij->i', B0 - q0, n0), dims['gap'])
    rows, nrm_rows = [], []
    for k in range(ns + 1):
        u = k / ns
        Q = B0 + up * (dims['stand'] * u) - n0 * 0.0
        R, n = to_skin(Q, d0 + (dims['gap'] - d0) * u)
        if k == 0:
            R = B0 - n0 * 0.001                          # the seam: just inside the shirt's neckline
        rows.append(R)
        nrm_rows.append(n)
    S = np.array(rows)                                    # (ns + 1, n_col, 3)
    Sn = np.array(nrm_rows)
    # ---------------------------------------------------------------- the fall's profiles (per column angle)
    Xs, Fsh = shirt
    Nsh = _vnormals(Xs, Fsh)

    def fall_profile(ang):
        """per angle: the polyline from the roll down the stand and over the shirt (2.5 mm off), with arc lengths"""
        top = np.stack([np.interp(ang, ang_s_sorted, S[ns][order_s][:, kk]) for kk in range(3)], -1)
        pts = []
        for k in range(ns, -1, -1):
            R = np.stack([np.interp(ang, ang_s_sorted, S[k][order_s][:, kk]) for kk in range(3)], -1)
            n = np.stack([np.interp(ang, ang_s_sorted, Sn[k][order_s][:, kk]) for kk in range(3)], -1)
            n /= np.linalg.norm(n, axis=-1, keepdims=True)
            pts.append(R + n * (0.0025 + 0.0015 * (k == ns)))
        roll = top + up * 0.0015 + np.stack([np.interp(ang, ang_s_sorted, Sn[ns][order_s][:, kk]) for kk in range(3)], -1) * 0.0012
        pts.insert(0, roll)
        # the march over the shirt from the neckline, away from the neck, 4 mm steps
        q, t, bc, _ = mo.closest_on_mesh(Xs, Fsh, pts[-1])
        cur = q
        outd = cur - axis_c
        outd -= np.outer(outd @ up, up)
        outd /= np.linalg.norm(outd, axis=1, keepdims=True)
        for _ in range(26):
            q, t, bc, _ = mo.closest_on_mesh(Xs, Fsh, cur)
            n = np.einsum('nk,nkj->nj', bc, Nsh[Fsh[t]])
            n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
            dvec = outd - n * np.einsum('ij,ij->i', outd, n)[:, None] - up * 0.25
            dvec -= n * np.einsum('ij,ij->i', dvec, n)[:, None]
            dvec /= np.linalg.norm(dvec, axis=1, keepdims=True) + 1e-12
            nxt = q + dvec * 0.004
            q2, t2, bc2, _ = mo.closest_on_mesh(Xs, Fsh, nxt)
            n2 = np.einsum('nk,nkj->nj', bc2, Nsh[Fsh[t2]])
            n2 /= np.linalg.norm(n2, axis=1, keepdims=True) + 1e-12
            pts.append(q2 + n2 * 0.0025)
            cur = q2
        L = np.array(pts)                                 # (m, n, 3)
        seg = np.linalg.norm(np.diff(L, axis=0), axis=-1)
        s = np.concatenate([np.zeros((1, L.shape[1])), np.cumsum(seg, axis=0)])
        return L, s
    order_s = np.argsort(ang_s)
    ang_s_sorted = ang_s[order_s]
    # the fall's outline in (|angle| from the front, depth): the front edge from the roll beside the button (a_r) to
    # the tip (a_pt); the outer edge `fall` at the back widening to `point` at the tip
    r_tip = 0.085
    a_pt = float(np.arcsin(np.clip(dims['tip_x'] / r_tip, 0, 0.95)))
    a_r = 0.10

    def width(aa):
        x = np.clip((np.pi / 2 - aa) / (np.pi / 2 - a_pt), 0.0, 1.0)
        return dims['fall'] + (dims['point'] - dims['fall']) * x * x * (3 - 2 * x)
    rowsF, tagt = [], []
    for j in range(nf + 1):
        t = j / nf
        ae = a_r + (a_pt - a_r) * t                       # this row's front end
        u = np.linspace(0.0, 1.0, n_col)
        aa = np.where(u <= 0.5, ae + (np.pi - ae) * (u / 0.5), ae + (np.pi - ae) * ((1 - u) / 0.5))
        sg = np.where(u <= 0.5, 1.0, -1.0)
        ang = np.where(u <= 0.5, aa, -aa)
        L, s = fall_profile(ang)
        depth = t * width(np.maximum(aa, a_pt)) + 0.0 * sg
        Pj = np.stack([np.array([np.interp(depth[c], s[:, c], L[:, c, kk]) for c in range(len(ang))]) for kk in range(3)], -1)
        rowsF.append(Pj)
        tagt.append(np.full(len(ang), t))
    Fa = np.array(rowsF)
    # ---------------------------------------------------------------- the mesh
    V = np.concatenate([S.reshape(-1, 3), Fa.reshape(-1, 3)])
    F = []
    nS = (ns + 1) * n_col
    for base, nr in ((0, ns + 1), (nS, nf + 1)):
        for i in range(nr - 1):
            for c in range(n_col - 1):
                p0, p1 = base + i * n_col + c, base + i * n_col + c + 1
                F += [(p0, p1, p0 + n_col), (p1, p1 + n_col, p0 + n_col)]
    F = np.array(F, np.int64)
    # outward: the stand's faces away from the neck's skin, the fall's away from what it lies on (the stand under its
    # top, the shirt under its edge). (B2b: a horizontal 'away from the neck's axis' vote flipped the man's fall, which
    # faces up over his shoulders: it rendered back-lit grey, the engine's close view)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    c = V[F].mean(1)
    stand_f = np.all(F < nS, axis=1)
    q1, _, _, _ = mo.closest_on_mesh(Vs, Fs, c[stand_f])
    SFc = []
    for i in range(ns):
        for c_ in range(n_col - 1):
            p0, p1 = i * n_col + c_, i * n_col + c_ + 1
            SFc += [(p0, p1, p0 + n_col), (p1, p1 + n_col, p0 + n_col)]
    under_V = np.concatenate([S.reshape(-1, 3), Xs])
    under_F = np.concatenate([np.array(SFc, np.int64), Fsh + nS])
    q2, _, _, _ = mo.closest_on_mesh(under_V, under_F, c[~stand_f])
    ref = np.zeros_like(c)
    ref[stand_f] = c[stand_f] - q1
    ref[~stand_f] = c[~stand_f] - q2
    flip = np.einsum('ij,ij->i', fn, ref) < 0
    for m in (stand_f, ~stand_f):
        if flip[m].mean() > 0.5:
            F[m] = F[m][:, ::-1]
    part = np.concatenate([np.zeros(nS, int), np.ones(len(V) - nS, int)])
    tt = np.concatenate([np.repeat(np.arange(ns + 1) / ns, n_col), np.concatenate(tagt)])
    top_drop = np.concatenate([np.repeat((1 - np.arange(ns + 1) / ns) * dims['stand'], n_col), np.zeros(len(V) - nS)])
    k_front = int(np.argmin(np.abs(ang_s)))
    front = S[ns // 2 + 1, k_front].copy()
    return V, F, dict(part=part, t=tt, top_drop=top_drop, front=front, n_col=n_col, ns=ns, nf=nf)


def _vnormals(V, F):
    return vertex_normals(V, F)


def button(c, n, t, r=0.0055, h=0.0022, seg=16):
    """a disc button at c on the cloth's normal n (t a tangent): a domed top, a rim, a short side"""
    n = n / np.linalg.norm(n)
    t = t - n * (t @ n)
    t /= np.linalg.norm(t)
    b = np.cross(n, t)
    a = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    ring = np.cos(a)[:, None] * t + np.sin(a)[:, None] * b
    rows = [c + ring * r * 0.98, c + ring * r + n * h * 0.7, c + ring * r * 0.8 + n * h, c + ring * r * 0.3 + n * h * 0.9]
    V = np.concatenate(rows + [[c + n * h * 0.85]])
    F = []
    for i in range(len(rows) - 1):
        for j in range(seg):
            a0, a1 = i * seg + j, i * seg + (j + 1) % seg
            F += [(a0, a1, a0 + seg), (a1, a1 + seg, a0 + seg)]
    ci = len(V) - 1
    last = (len(rows) - 1) * seg
    for j in range(seg):
        F.append((last + j, last + (j + 1) % seg, ci))
    return V, np.array(F, np.int64)
