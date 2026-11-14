"""THE NECKTIE: a four-in-hand in repp silk, a PROP ON THE CHEST SEAT (socket_chest, spine_05, at the suprasternale: the
old `tie: true|color`), made for the collared shirt it is worn with. (B2b, the lead's call 11-08: "a real tie: a knot
lofted as a four-in-hand and a draped blade"; round 1's was a flat plank with a box knot standing 2 cm off the throat.)

  the KNOT    lofted down from the collar's roll: D sections (a flat back against the band and, below it, the placket; a
              domed front), 40 / 47 mm wide at the top (F / M) narrowing to 23 / 26 at the bottom, 42 / 49 mm tall,
              15 / 18 mm thick at the top (TIE); leaning 3 mm (a four-in-hand is asymmetric); its top at the roll,
              tucked under the collar's wings (collar_over_knot pushes the fall's front over it)
  the BLADE   from inside the knot's bottom to the tip at the belt: 2 mm narrower than the knot's bottom there, widening
              over 22 cm to the blade's width (60 mm F, 75 mm M), ending in a 90 deg point; DRAPED (drape.py: a stiff
              interlined strip, pinned under the knot) against the shirt and the body, from the taut line over the
              chest; then given its thickness (two sheets 3 mm apart, rolled edges); its top 3 cm carries the DIMPLE
              (the blade's middle folded back 2.5 mm under the knot)
  skinned     by transfer from the shirt's FULL mesh (the knot takes the collar's weights, the blade the front's); the seat
              recorded in the glb's extras
"""
import numpy as np

from . import meshops as mo

# (B2b, after the engine's close view beside refs/tie/Necktie_Four-in-Hand_knot.jpg: the first knot read as a narrow box
# with the band's button showing over it) the knot's top ~0.65 of the blade's widest, as tall as it is wide
TIE = {'F': dict(w_top=0.040, w_bot=0.023, knot_h=0.042, th_top=0.015, th_bot=0.010, blade=0.060),
       'M': dict(w_top=0.047, w_bot=0.026, knot_h=0.049, th_top=0.018, th_bot=0.011, blade=0.075)}
SILK = dict(k_stretch=1.0, k_bend=0.45, thick=0.0016, mu=0.55, gsm=0.20)


def _front_profile(shirt_V, shirt_F, xs, ys):
    """the shirt's front z at (x, y), from ahead (rays toward -Z)"""
    from .outfit import _ray_hits
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    O = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, 0.8)])
    D = np.tile([0.0, 0.0, -1.0], (X.size, 1))
    hit, hp = _ray_hits(shirt_V, shirt_F, O, D, 1.5)
    z = np.where(hit, hp[:, 2], -np.inf).reshape(X.shape)
    return z


def build(fr, shirt, sex='F'):
    """shirt: the forged collared shirt (T rest: V, F incl. the collar, collar_range / part / top_drop, XT_low, F_low)"""
    from . import drape as dr
    d = TIE['F' if sex == 'F' else 'M']
    SV, SF = shirt['V'], shirt['F']
    c0, c1 = (int(x) for x in shirt['collar_range'])
    part = np.asarray(shirt['collar_part'])
    CV = SV[c0:c1]
    stand = CV[part == 0]
    top_drop = np.asarray(shirt['collar_top_drop'])[part == 0]
    # the band's FRONT at the centre: its top row's and seam row's points near x = 0 on the front half (|x| alone also
    # took the centre back's column, whose top is 4 cm higher: the dry run's knot rose to the chin)
    zmid = 0.5 * (stand[:, 2].min() + stand[:, 2].max())
    fr_top = stand[(top_drop < 1e-4) & (np.abs(stand[:, 0]) < 0.012) & (stand[:, 2] > zmid)]
    fr_bot = stand[(top_drop > 0.9 * top_drop.max()) & (np.abs(stand[:, 0]) < 0.012) & (stand[:, 2] > zmid)]
    y_roll = float(fr_top[:, 1].max())
    z_band_top = float(fr_top[:, 2].max())
    y_seam = float(fr_bot[:, 1].mean())
    z_band_bot = float(fr_bot[:, 2].max())
    knot_top = y_roll - 0.002                # at the roll: the band and its button are under the knot
    ys_k = knot_top - d['knot_h'] * np.linspace(0, 1, 9)
    # the knot's back: the band's front above its seam, the shirt's front (the placket) below it, +1 mm
    zf = _front_profile(SV, SF, np.array([0.0]), ys_k)[0]

    def z_back(y):
        zb = np.interp(y, [y_seam, y_roll], [z_band_bot, z_band_top])
        zs = np.interp(y, ys_k[::-1], zf[::-1])
        return np.maximum(zb, np.where(np.isfinite(zs), zs, zb)) + 0.001
    # ---------------------------------------------------------------- the knot (D sections)
    ring = 24
    secs = len(ys_k)
    a = np.linspace(0, 2 * np.pi, ring, endpoint=False)
    KV = []
    for s_i, y in enumerate(ys_k):
        u = s_i / (secs - 1)
        hw = 0.5 * (d['w_top'] + (d['w_bot'] - d['w_top']) * u ** 0.8)
        th = d['th_top'] + (d['th_bot'] - d['th_top']) * u
        xc = -0.003 * u                                     # the lean
        x = hw * np.sign(np.cos(a)) * np.abs(np.cos(a)) ** 0.6
        sn = np.sin(a)
        zfront = th * np.abs(sn) ** 0.75 * (1.0 - 0.10 * (np.abs(x) / hw) ** 2)
        zz = np.where(sn > 0, zfront, -0.0015 * np.abs(sn))  # a domed front, a near flat back
        # the top's corners round over toward the band
        if s_i == 0:
            zz = zz * 0.55
        KV.append(np.column_stack([xc + x, np.full(ring, y), z_back(np.array([y]))[0] + 0.0015 + zz]))
    KV = np.array(KV)
    kV = KV.reshape(-1, 3)
    kF = []
    for s_i in range(secs - 1):
        for j in range(ring):
            p0, p1 = s_i * ring + j, s_i * ring + (j + 1) % ring
            kF += [(p0, p1, p0 + ring), (p1, p1 + ring, p0 + ring)]
    ct = len(kV)
    kV = np.concatenate([kV, [KV[0].mean(0) + [0, 0.0015, 0]]])
    for j in range(ring):
        kF.append((ct, (j + 1) % ring, j))
    kF = np.array(kF, np.int64)
    kU = np.concatenate([np.repeat(np.linspace(0, 1, secs), ring), [0.0]])          # down the knot
    kX = np.concatenate([np.tile(np.cos(a), secs), [0.0]])                           # across (front: sin > 0)
    # ---------------------------------------------------------------- the blade: rest (flat), start (taut), drape
    y0 = ys_k[-1] + 0.006                                    # inside the knot's bottom
    tip_y = fr.waist_y - 0.065 + 0.010
    Lb = y0 - tip_y
    w0 = d['w_bot'] - 0.002         # inside the knot's bottom (wider, its corners stood out of the knot: a bar, dry run)
    ncol = 9
    ds = 0.008
    s = np.arange(0.0, Lb + 1e-9, ds)
    w_s = w0 + (d['blade'] - w0) * np.clip(s / 0.22, 0, 1)
    # the point: the last half width narrows to the tip
    pt0 = Lb - d['blade'] / 2
    w_s = np.where(s > pt0, w_s * np.clip((Lb - s) / max(1e-6, Lb - pt0), 0.02, 1.0), w_s)
    nr = len(s)
    xr = (np.linspace(-0.5, 0.5, ncol)[None, :] * w_s[:, None])
    # the taut start: the centre line from the knot down over the shirt's front (max over the blade's width, + 4 mm)
    ys = y0 - s
    zprof = _front_profile(SV, SF, np.linspace(-d['blade'] / 2, d['blade'] / 2, 7), ys).max(0)
    zprof = np.where(np.isfinite(zprof), zprof, z_back(np.array([y0]))[0]) + 0.004
    zk = float(KV[-1][:, 2].mean())
    zc = np.maximum(zprof, zk)
    # upper hull in (y, z) from the knot down (the line a hanging strip takes over the chest), then straight down
    order = np.argsort(ys)
    Y, Z = ys[order], zc[order]
    hull = []
    for q in zip(Y, Z):
        while len(hull) >= 2:
            (y1, z1), (y2, z2) = hull[-2], hull[-1]
            if (y2 - y1) * (q[1] - z1) - (z2 - z1) * (q[0] - y1) >= 0:
                hull.pop()
            else:
                break
        hull.append(q)
    H = np.array(hull)
    zt = np.interp(ys, H[:, 0], H[:, 1])
    Xst =np.stack([np.column_stack([xr[i], np.full(ncol, ys[i]), np.full(ncol, zt[i])]) for i in range(nr)])
    # the flat rest: the same strip laid straight (the lengths along the start's centre line)
    arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(ys), np.diff(zt)))])
    Xr = np.stack([np.column_stack([xr[i], np.full(ncol, y0 - arc[i]), np.full(ncol, zk)]) for i in range(nr)])
    gF = []
    for i in range(nr - 1):
        for j in range(ncol - 1):
            p0, p1 = i * ncol + j, i * ncol + j + 1
            gF += [(p0, p0 + ncol, p1), (p1, p0 + ncol, p1 + ncol)]
    gF = np.array(gF, np.int64)
    cols = [(shirt['XT_low'], shirt['F_low']), (fr.Vw, fr.Fw)]
    Xd, rep = dr.drape(Xr.reshape(-1, 3), gF, SILK, cols, frames=90, settle=60, ramp=(0.0, 0.0), pins=np.arange(ncol),
                       X_start=Xst.reshape(-1, 3), pin_target=Xst.reshape(-1, 3), self_collide=False, log=lambda *_: None)
    Xd = Xd.reshape(nr, ncol, 3)
    # the dimple: the blade's middle folded back under the knot (3 cm, fading)
    dim = np.clip(1.0 - s / 0.03, 0, 1)[:, None] * np.exp(-(np.linspace(-1, 1, ncol)[None, :] / 0.28) ** 2) * 0.0025
    Xd[:, :, 2] -= dim
    # ---------------------------------------------------------------- thickness: two sheets, rolled edges, the tip
    from .body import vertex_normals
    M = Xd.reshape(-1, 3)
    Nm = vertex_normals(M, gF)
    if Nm[:, 2].mean() < 0:
        Nm = -Nm
    th = 0.0015
    front, back = M + Nm * th, M - Nm * th
    V = [front, back]
    F = [gF, gF[:, ::-1] + len(M)]
    nV = 2 * len(M)
    # the rolled edges (both long sides and the bottom's two point edges): a half-round of 3 rows between the sheets
    edge_ids = [np.arange(nr) * ncol, np.arange(nr) * ncol + ncol - 1]
    eV, eF = [], []
    for e_k, ids in enumerate(edge_ids):
        out = M[ids] - M[ids - 1 if e_k else ids + 1]
        out -= Nm[ids] * np.einsum('ij,ij->i', out, Nm[ids])[:, None]
        out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-12
        rows = [front[ids]]
        for ang in (np.pi / 3, 2 * np.pi / 3):
            rows.append(M[ids] + Nm[ids] * th * np.cos(ang) + out * th * np.sin(ang) * 0.9)
        rows.append(back[ids])
        base = nV + sum(len(x) for x in eV)
        R = np.concatenate(rows[1:3])
        eV.append(R)
        idx = [ids, base + np.arange(len(ids)), base + len(ids) + np.arange(len(ids)), ids + len(M)]
        for r_ in range(3):
            A_, B_ = idx[r_], idx[r_ + 1]
            for i in range(len(ids) - 1):
                q = [(A_[i], A_[i + 1], B_[i]), (A_[i + 1], B_[i + 1], B_[i])]
                eF += q if e_k == 1 else [t[::-1] for t in q]
    V = np.concatenate(V + eV)
    F = np.concatenate(F + [np.array(eF, np.int64)])
    # the tip row's front and back sheets closed
    last = (nr - 1) * ncol + np.arange(ncol)
    tF = []
    for j in range(ncol - 1):
        tF += [(last[j], last[j] + len(M), last[j + 1]), (last[j + 1], last[j] + len(M), last[j + 1] + len(M))]
    F = np.concatenate([F, np.array(tF, np.int64)])
    bU = np.concatenate([np.repeat(s / Lb, ncol)] * 2 + [np.zeros(sum(len(x) for x in eV))])
    # ---------------------------------------------------------------- one mesh: the knot, the blade
    allV = np.concatenate([kV, V])
    allF = np.concatenate([kF, F + len(kV)])
    piece = np.concatenate([np.zeros(len(kV), int), np.ones(len(V), int)])
    # OUTWARD per face: a face whose normal ray meets the tie again within 2 cm points inward
    from .outfit import _ray_hits
    n = np.cross(allV[allF[:, 1]] - allV[allF[:, 0]], allV[allF[:, 2]] - allV[allF[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-20
    c = allV[allF].mean(1)
    hit, _ = _ray_hits(allV, allF, c + n * 2e-4, n, 0.02)
    allF[hit] = allF[hit][:, ::-1]
    tag = dict(piece=piece, u=np.concatenate([kU, bU]), x=np.concatenate([kX, np.zeros(len(V))]))
    rec = dict(knot_top=[0.0, float(knot_top), float(z_back(np.array([knot_top]))[0])], tip_y=float(tip_y),
               width=float(d['blade']), knot=d, seat='socket_chest', drape=rep)
    return allV, allF, tag, rec


def collar_over_knot(shirt, tie_V, tie_F, tie_piece, clear=0.0025, reach=0.025):
    """the shirt with its collar's FALL pushed over the knot (the wings lie on the knot's top corners, as a real
    collar's do): every fall vertex inside the knot or nearer than `clear` goes out along the knot's normal to `clear`,
    the push eased over the fall within `reach` of it. Returns a copy of the shirt dict."""
    from .body import vertex_normals
    sh = dict(shirt)
    V = shirt['V'].copy()
    c0, c1 = (int(x) for x in shirt['collar_range'])
    fall = np.nonzero(np.asarray(shirt['collar_part']) == 1)[0] + c0
    kF = tie_F[(tie_piece[tie_F] == 0).all(1)]
    q, t, bc, sd = mo.closest_on_mesh(tie_V, kF, V[fall])
    Nk = vertex_normals(tie_V, kF)
    n = np.einsum('nk,nkj->nj', bc, Nk[kF[t]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    push = np.clip(clear - sd, 0.0, None)
    push = np.where(np.linalg.norm(V[fall] - q, axis=1) < 0.03, push, 0.0)
    disp = n * push[:, None]
    # ease: each fall vertex takes the largest push within `reach`, decayed
    from scipy.spatial import cKDTree
    P = V[fall]
    tree = cKDTree(P)
    big = push > 0
    if big.any():
        out = np.zeros_like(P)
        for i in np.nonzero(big)[0]:
            nb = tree.query_ball_point(P[i], reach)
            # a smooth (cosine) falloff over 25 mm: the 12 mm square one crumpled the wing over the man's larger knot
            w = 0.5 + 0.5 * np.cos(np.pi * np.clip(np.linalg.norm(P[nb] - P[i], axis=1) / reach, 0, 1))
            cand = disp[i][None, :] * w[:, None]
            better = np.linalg.norm(cand, axis=1) > np.linalg.norm(out[nb], axis=1)
            out[np.array(nb)[better]] = cand[better]
        V[fall] = P + out
    from . import maps
    sh['V'] = V
    sh['N'], sh['TAN'] = maps.frames(V, shirt['F'], shirt['UV'])
    sh['rec'] = dict(shirt['rec'], collar_over_knot_mm=float(push.max() * 1000))
    return sh
