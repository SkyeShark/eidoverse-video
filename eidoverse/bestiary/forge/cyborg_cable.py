"""THE HOSE AS A SKIN-RIDING CABLE, the forge's side (the lead's C5d call 2; runtime/cyborg_cable.js; patches/
cyborg_c5d_bestiary.md): the per-seed hose (forge/cyborg_hose.py build_hose, drawn in the seed's reference pose) turned
into the CABLE'S DATA the runtime re-makes the hose from every frame, on the creature's rendered skin:

  ANCHORS   skin points as a triangle of the low (its three vertices in the skin's shared vertex set) and its
            barycentrics: the closest point of the reference pose's skin (the cut's pinned weights, as the runtime skins
            it; the replaced arm's hidden distal triangles left out)
  RINGS     per ring one of: RIGID in a frame (the plate fitting's skin blend, bone 7's for the port, a clamp's frame)
            with its coordinates there; ANCHORED on an anchor with its offset in the anchor triangle's frame (e1 its first
            edge, n its normal, e2 = n x e1: its centre exactly where the reference pose drew it, and r + its clearance off
            that triangle in any motion); FREE (a span's)
  FRAMES    'blend' (the plate fitting: the skin weights of its site), 'bone' (arm<j>_07: the port, rigid as the
            tentacle), 'clamp' (four anchors under a pad's corners: their mean and the frame they span)
  SPANS     every run of free rings between two fixed ones (the descent, the ramps, the arches, the humps, the rise): its
            rest arc length, each ring's rest arc fraction, its ends' tangents and up axes (rigid in a frame, or in its end
            ring's anchor frame), its crest power, and its LOWER BOUNDS (each free ring's skin point under it, anchored,
            and for the rise the flange's pieces under it, rigid on bone 7): the clearance its rest pose had, at most
            r + BOUND_MARGIN; C5e: its REST SHAPE (rest_shape: its rod's nodes at rest in the frame of its chord and its
            ends' up axes, the runtime's initial shape and tether target)
  RING_S    C5e: each ring's rest arc length along the hose (a free span the skin pulls taut borrows hose from the
            lying run it lands on: the runtime's borrowEval)
  RUN_TOT   C5f: each lying run's rest path length as the runtime's relay lays it (a run whose path the skin shortens
            slides the difference into the hump beside it: relay's lend, the lead's call 8)
  RING_R    C5f: each ring's radius where a convoluted section makes them differ (cyborg_hose BELLOWS, the lead's call
            5); such a span is marked 'bellows': the runtime keeps its length over its chord at the rest ratio
  PADS      C5e: every vertex RIGID in its clamp frame (pad, strap, rivets; C5d anchored the underside on the skin
            and blended the flanks by height, and the swim shortened pad 1 by 11-18 %)
  CONTACTS  per pad its footprint in the bind space (the skin shader's contact AO and, C5e, its contact shadow): C5e,
            centre, axes and half-sizes all from the underside's bind points
The data rides in the hose glb's extras (bestiary.cable), built with the hose at assembly (cyborg_hose.hose_for_seed).

Read with numpy and scipy (warp's CPU device for the closest points).
"""
import math

import numpy as np

from . import cyborg_hose as CH
from . import cyborg_octopus as CO

BOUND_MARGIN = 0.12e-3      # a free ring's lower bound: the clearance its rest pose had over the skin, at most r + this
FLANGE_MARGIN = 0.20e-3     # and over the flange's pieces (the rise): at most r + this
BOUND_TOL = 0.03e-3         # (the bound sits this far under the rest height: the reference pose never lifts)
FIT_RUN = 1.55              # the plate fitting's run inside its ferrule (x r: cyborg_hose's run0)
PORT_RUN = 1.55             # and the port's (run_end: 0.95 r out to 0.6 r in)
CLAMP_BLEND = 4.0           # x r: the anchored rings this far either side of a clamp drawn toward its rigid frame (the ramp
                            # and a little more: over the ramp's 2.8 r alone the swim's 30 % shrink of the root's skin bent
                            # the blend to 6.9 mm by clamp 1, s12)
CLAMP_PAST = 0.45           # x r: the rings this far past a clamp's faces ride its rigid frame too
LIE_CLEAR = 0.04e-3         # an anchored ring's contact: it clears its foot and its lips by r + this (C5d s22)
LIP_DEG = (-100.0, -75.0, -50.0, -25.0, 25.0, 50.0, 75.0, 100.0)   # its lips: rays this far off straight down
LIP_REACH = 2.2             # x r: within this far of its rest centre
RUN_SMOOTH = 1              # the runtime's (cyborg_cable.js): a run's control points smoothed this many times
ROD_STEP_MM = 1.0           # C5e: the runtime's rod (cyborg_cable.js ROD.step): a span's segments at most this long (mm),
ROD_NR = (16, 72)           # their count within this range


def assemble_assets(block, assets=None, ctx=None, out_dir=None, log=print):
    """ASSEMBLY (the lead's C5d call 2, the C5c check's 'nothing builds a missing seed'): the engine's asset map for a
    runtime block (recipe.resolve_runtime's: its cyborg parts): every hose part's glb built ON DEMAND for its seed (the
    part's seed, else the block's) by cyborg_hose.hose_for_seed, cached by seed and its inputs' sha1s (rebuilt when absent
    or when an input changed), its cable's data in its extras; the map {asset name: path} gains each. Returns the map"""
    out = dict(assets or {})
    for part in (block.get('cyborg') or {}).get('parts', []):
        if part.get('kind') != 'hose':
            continue
        seed = int(part.get('seed', block.get('seed', 1)))
        name = CH.hose_asset(part.get('chain', 'arm7'), seed)
        if part.get('asset') not in (None, name):
            log(f'[assembly] the hose part names {part.get("asset")}: the seed {seed} gives {name}')
        kw = {} if out_dir is None else dict(out_dir=out_dir)
        glb, rec = CH.hose_for_seed(seed, ctx, log=log, **kw)
        out[name] = glb
        log(f'[assembly] {name}: {glb}' + (' (cable)' if 'cable' in (rec.get('record') or {}) or rec.get('cable') else ''))
    return out


def _closest(key, V, F, P):
    """closest points of the triangles (V, F) to points P: (face, barycentrics (n, 3), the points)"""
    X, fc, u, v = CH._closest_ref(key, V, F, np.asarray(P, np.float64))
    return fc, np.column_stack([u, v, 1.0 - u - v]), X


def anchor_frame(A, B, n):
    """an anchor's frame (the runtime's): n the skin's SMOOTH normal there (its corners' skinned normals blended by the
    barycentrics), e1 its triangle's first edge made normal to n, e2 = n x e1"""
    e1 = (B - A) - ((B - A) * n).sum(-1, keepdims=True) * n
    e1 = e1 / np.linalg.norm(e1, axis=-1, keepdims=True)
    return e1, n, np.cross(n, e1)


def bary(P, A, B, C):
    """barycentrics (n, 3) of points P on triangles A, B, C"""
    v0, v1, v2 = B - A, C - A, P - A
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return np.column_stack([1.0 - v - w, v, w])


def clamp_frame(P4):
    """the runtime's clamp frame from its four anchors (back-left, front-left, back-right, front-right): 4x4"""
    ex = (P4[1] + P4[3]) - (P4[0] + P4[2])
    ex /= np.linalg.norm(ex)
    ez0 = (P4[2] + P4[3]) - (P4[0] + P4[1])
    ey = np.cross(ez0, ex)
    ey /= np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = ex, ey, ez, P4.mean(0)
    return M


def cable_data(ctx, HO, ref_worlds, log=print):
    """THE CABLE'S DATA for one built hose (HO: cyborg_hose.build_hose's result in the seed's reference pose ref_worlds)"""
    oct_, j = ctx.oct_, ctx.arm
    r = float(HO['r'])
    rec = HO['record']
    Pr = np.asarray(HO['centre_ref'], np.float64)
    s = np.asarray(HO['s'], np.float64)
    N = len(Pr)
    rg = oct_.rig
    nV = len(oct_.low['V'])
    # the reference skin as the runtime skins it: the cut's ring and the ring before pinned to joint 7
    cutrec = CO.cut_arm(oct_, j)
    J_pin, W_pin = CO.pinned_weights(oct_, cutrec)
    Msk = rg.skin_mats(ref_worlds)
    Vref = CO.lbs(oct_.low['V'], J_pin[:nV], W_pin[:nV], Msk)
    keep = np.ones(len(oct_.F), bool)
    keep[cutrec['distal']] = False
    Fk = oct_.F[keep]
    # the reference skin's SMOOTH normals as the runtime skins them (the bind normals by the skin matrices' linear parts)
    Nref = np.zeros((nV, 3))
    for c in range(4):
        w_ = W_pin[:nV, c]
        m_ = w_ > 0
        Nref[m_] += w_[m_, None] * np.einsum('nij,nj->ni', Msk[J_pin[:nV][m_, c], :3, :3], oct_.N[:nV][m_])
    Nref /= np.linalg.norm(Nref, axis=1, keepdims=True)
    import hashlib
    key = ('cable', hashlib.sha1(np.ascontiguousarray(Vref).tobytes()).hexdigest())
    anchors, skin_v, aP = [], {}, []

    def add_anchors(tri, bc):
        """anchors on triangles tri (n, 3: the low's vertex indices) at barycentrics bc: their indices (their reference
        points kept in aP)"""
        out = []
        for t_, b_ in zip(tri, bc):
            for v_ in t_:
                skin_v.setdefault(int(v_), len(skin_v))
            anchors.append([skin_v[int(t_[0])], skin_v[int(t_[1])], skin_v[int(t_[2])], float(b_[0]), float(b_[1]),
                            float(b_[2])])
            aP.append((np.asarray(b_, np.float64)[:, None] * Vref[np.asarray(t_)]).sum(0))
            out.append(len(anchors) - 1)
        return np.array(out, np.int64)

    def anchor(P, phong=True):
        """anchors under points P (n, 3) on the reference skin: the foot whose SMOOTH normal points at the point (Phong's
        projection, from the closest point, a few casts back along the normal: the offset then lies along the normal the
        runtime turns, so neighbouring rings on different triangles move alike; the closest point's triangle normals
        turned them apart by up to 1.5 mm in the swim, s13), its triangle and barycentrics, the frame there. Returns
        (indices, feet, e1, n, e2)"""
        P = np.asarray(P, np.float64)
        fc, bc, X = _closest(key, Vref, Fk, P)
        if phong:
            for _ in range(8):
                tri = Fk[fc]
                n_ = (bc[:, :, None] * Nref[tri]).sum(1)
                n_ /= np.linalg.norm(n_, axis=1, keepdims=True)
                hit, fh = CH._ray_mesh(key + ('rays',), Vref, Fk, P + 1.0e-6 * n_, -n_, 0.08)
                ok = (fh >= 0) & np.isfinite(hit).all(1)
                if not ok.any():
                    break
                bc2 = bary(hit[ok], Vref[Fk[fh[ok], 0]], Vref[Fk[fh[ok], 1]], Vref[Fk[fh[ok], 2]])
                moved = np.linalg.norm(hit[ok] - X[ok], axis=1)
                fc[ok], bc[ok], X[ok] = fh[ok], np.clip(bc2, 0.0, 1.0) / np.clip(bc2, 0.0, 1.0).sum(1, keepdims=True), \
                    hit[ok]
                if moved.max() < 1.0e-9:
                    break
        tri = Fk[fc]
        out = add_anchors(tri, bc)
        A, B = Vref[tri[:, 0]], Vref[tri[:, 1]]
        X = (bc[:, :, None] * Vref[tri]).sum(1)
        n_ = (bc[:, :, None] * Nref[tri]).sum(1)
        n_ /= np.linalg.norm(n_, axis=1, keepdims=True)
        e1, n, e2 = anchor_frame(A, B, n_)
        return np.array(out), X, e1, n, e2

    def local3(D, e1, n, e2):
        return np.column_stack([(D * e1).sum(1), (D * n).sum(1), (D * e2).sum(1)])
    # ---------------------------------------------------------------- the frames
    w_of = HO['ring_w']
    names = rg.jnames
    fitw = w_of[0]
    w7 = w_of[N - 1]
    frames = [dict(kind='blend', bones=[names[k] for k in fitw], w=[float(v) for v in fitw.values()]),
              dict(kind='bone', bone=f'arm{j}_{CO.J0:02d}')]
    Mfit = sum(w_ * Msk[k_] for k_, w_ in fitw.items())
    M7 = Msk[oct_.bone[f'arm{j}_{CO.J0:02d}']]
    assert set(w7) == {oct_.bone[f'arm{j}_{CO.J0:02d}']}, 'the port ring is not rigid on bone 7'
    to_bind = lambda M, P: (np.linalg.inv(M) @ np.c_[P, np.ones(len(P))].T).T[:, :3]
    dir_bind = lambda M, D: D @ np.linalg.inv(M[:3, :3]).T
    # ---------------------------------------------------------------- the rings' kinds
    rp = rec['ring_pieces']
    piece = np.array([''] * N, dtype=object)
    for nm_, (a_, b_) in rp.items():
        piece[a_:b_ + 1] = nm_
    kind = np.full(N, -1)
    ref = np.zeros(N, np.int64)
    loc = np.zeros((N, 3))
    fit_n = s <= FIT_RUN * r + 1e-4
    flg_n = s >= s[-1] - PORT_RUN * r - 1e-4
    kind[fit_n] = 0
    kind[flg_n] = 0
    ref[flg_n] = 1
    loc[fit_n] = to_bind(Mfit, Pr[fit_n])
    loc[flg_n] = to_bind(M7, Pr[flg_n])
    clamps = HO['clamps']
    cf_of = {}
    pads = []
    under_of = {}
    for ci, cl in enumerate(clamps):
        # the clamp frame: the rigid frame that best fits the skin under the pad (its underside vertices' anchors: their
        # rest places in the frame, least squares, the runtime's polar decomposition); at the reference it is the frame
        # four corner anchors span. (Four corners alone: through the swim the skin under pad 1 rose 1.55 mm and slid 2.2
        # mm in their frame, s21, and the rigid clamp sank into it)
        V_pad = np.asarray(cl['pad']['V'], np.float64)
        part = np.asarray(cl['pad']['part'])
        Q = (V_pad - cl['c']) @ cl['R']                      # the pad in the forge's clamp frame (x along, y up)
        und = np.nonzero(part == 0)[0]
        hx, hz = Q[und, 0].max(), Q[und, 2].max()
        corners = []
        for sx, sz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            d2 = (Q[und, 0] - 0.8 * sx * hx) ** 2 + (Q[und, 2] - 0.8 * sz * hz) ** 2
            corners.append(int(np.nonzero(und == und[int(d2.argmin())])[0][0]))
        ai_u, Xu, e1u, nu, e2u = anchor(V_pad[und])
        under_of[cl['k']] = (und, ai_u, Xu, e1u, nu, e2u)
        Mc = clamp_frame(Xu[corners])
        fi = len(frames)
        frames.append(dict(kind='clamp', anchors=[int(a_) for a_ in ai_u],
                           loc=[float(x_) for x_ in ((Xu - Mc[:3, 3]) @ Mc[:3, :3]).ravel()]))
        cf_of[cl['k']] = (fi, Mc)
        # the clamp's rings: its piece's, and the rings at its two faces (the piece boundaries give a face ring to the
        # neighbouring ramp: anchored, it parted from the clamp's rigid run in the swim, a 57 deg kink, s13)
        a_, b_ = rp[f'clamp{cl["k"]}']
        from . import cyborg_pads as PD_
        # (and the ring just past each face: the pad's rounded end under it, a ring anchored there dipped 0.05 mm into
        # it, s15)
        half = 0.5 * PD_.PAD['L'] * r + CLAMP_PAST * r
        cand = np.arange(max(a_ - 3, 0), min(b_ + 4, N))
        Qc = (Pr[cand] - cl['c']) @ cl['R']
        inside = (np.abs(Qc[:, 0]) <= half) & (np.hypot(Qc[:, 1], Qc[:, 2]) < 0.5e-3)
        rings_c = np.union1d(np.arange(a_, b_ + 1), cand[inside])
        kind[rings_c] = 0
        ref[rings_c] = fi
        loc[rings_c] = (Pr[rings_c] - Mc[:3, 3]) @ Mc[:3, :3]
        pads.append((cl, fi, Mc))
    # the lying runs AND the ramps into the pads ride the skin ring by ring (a ramp is the lying hose climbing into its
    # pad's cradle: its 12 mm cannot take what the skin under it gains or loses as the arm bends, 4.5 mm in the swim,
    # without buckling into 2-3 mm bends, s12); the arches, the humps, the descent and the rise are the FREE spans
    anch = ('ride', 'ramp')
    for i in range(N):
        if kind[i] >= 0:
            continue
        nm_ = str(piece[i])
        if nm_.startswith(anch):
            kind[i] = 1
        elif nm_:
            kind[i] = 2
        else:                                                  # a ring between two pieces
            nb = [str(piece[q]) for q in (i - 1, i + 1) if 0 <= q < N]
            kind[i] = 2 if any(x and not x.startswith(anch + ('clamp', 'fit', 'flange')) for x in nb) else 1
    # the anchored rings
    ia = np.nonzero(kind == 1)[0]
    ai, X, e1, n, e2 = anchor(Pr[ia])
    ref[ia] = ai
    loc[ia] = local3(Pr[ia] - X, e1, n, e2)
    a_frame = {int(i_): (int(a_), X[q], e1[q], n[q], e2[q]) for q, (i_, a_) in enumerate(zip(ia, ai))}
    # each anchored ring's CONTACT (C5d s22): through the swim the skin round the arm's root opened under the lying run
    # (rings drawn at rest on a crease's lips, 0.8 mm over its floor along their foot's normal, stood 0.5-0.75 mm off the
    # skin there once the crease opened) and closed on others. Beside its foot each anchored ring keeps the skin points
    # round its lower half at rest (rays from its rest centre in its cross-section's plane, LIP_DEG off straight down,
    # within LIP_REACH r): per frame it stands at the lowest height along its foot's normal that clears every one of them
    # by r + LIE_CLEAR (the runtime's contact), plus its REST LIFT over that height (a lying ring's what its rest pose
    # stood over its contact, within LIFT_RIDE; a ramp's its climb)
    Tl = np.zeros_like(Pr)
    Tl[1:-1] = Pr[2:] - Pr[:-2]
    Tl[0], Tl[-1] = Pr[1] - Pr[0], Pr[-1] - Pr[-2]
    Tl /= np.linalg.norm(Tl, axis=1, keepdims=True)
    rho = r + LIE_CLEAR
    th_ = np.radians(np.asarray(LIP_DEG, np.float64))
    u_ = n - (n * Tl[ia]).sum(1, keepdims=True) * Tl[ia]
    u_ /= np.linalg.norm(u_, axis=1, keepdims=True)
    w_ = np.cross(Tl[ia], u_)
    org = np.repeat(Pr[ia], len(th_), 0)
    dirs = (-np.cos(th_)[None, :, None] * u_[:, None] + np.sin(th_)[None, :, None] * w_[:, None]).reshape(-1, 3)
    hit, fh = CH._ray_mesh(key + ('rays',), Vref, Fk, org, dirs, LIP_REACH * r)
    okh = (fh >= 0) & np.isfinite(hit).all(1)
    lip_a = np.full(len(org), -1, np.int64)
    if okh.any():
        tri_h = Fk[fh[okh]]
        bc_h = np.clip(bary(hit[okh], Vref[tri_h[:, 0]], Vref[tri_h[:, 1]], Vref[tri_h[:, 2]]), 0.0, 1.0)
        bc_h /= bc_h.sum(1, keepdims=True)
        lip_a[okh] = add_anchors(tri_h, bc_h)
    lip_a = lip_a.reshape(len(ia), len(th_))
    c_count = np.zeros(N, np.int64)
    c_list = []
    lift = np.zeros(N)
    n_held = 0
    for q, i_ in enumerate(ia):
        lst = [int(ai[q])] + [int(x_) for x_ in lip_a[q] if x_ >= 0]
        c_count[i_] = len(lst)
        c_list += lst
        Bq = Pr[i_] - loc[i_, 1] * n[q]
        hc = -np.inf
        for a2 in lst:
            d_ = Bq - aP[a2]
            dn_ = float(d_ @ n[q])
            disc = dn_ * dn_ - float(d_ @ d_) + rho * rho
            if disc >= 0.0:
                hc = max(hc, -dn_ + np.sqrt(disc))
        if not np.isfinite(hc):
            hc = rho
        n_held += int(hc > np.sqrt(max(rho * rho - loc[i_, 0] ** 2 - loc[i_, 2] ** 2, 0.0)) + 1e-6)
        # (the whole rest lift kept, the lying rings' too: clipped to 0.12 mm, ring 153's step bent the rest pose to
        # 6.4 mm, s12; the rest pose is its rest curve exactly)
        lift[i_] = loc[i_, 1] - hc
    c_start = np.concatenate([[0], np.cumsum(c_count)])
    log(f'[cable] contact: {len(c_list)} contact points on {len(ia)} anchored rings ({n_held} held by a lip at rest)')
    # the rings the runtime FAIRS by each clamp (the ramps, and the two lying rings next to each: gate 7's lying bar
    # leaves a run's last two rings out): through the swim the skin came down into clamp 1 at 21 deg to its axis while
    # the ramp climbed 1.6 mm to it, and laid on the skin the hose turned 14 deg at one ring (s23); faired it leaves the
    # skin's valley as a stiff hose does, never under its contact
    sm_ = np.zeros(N)
    is_ramp = np.array([str(p_).startswith('ramp') for p_ in piece])
    for i_ in ia:
        near_ramp = is_ramp[max(i_ - 2, 0):i_ + 3].any()
        if is_ramp[i_] or str(piece[i_]) == '' or (str(piece[i_]).startswith('ride') and near_ramp):
            sm_[i_] = 1.0
    # and each faired ring's REST DETAIL: its rest centre's offset, in its anchor's frame, from the Hermite the runtime
    # draws its stretch on at rest (relay's fairStretch, term by term: the run's control points smoothed RUN_SMOOTH
    # times, the stretch between the held points either side, the tangents from the points beyond them, the rings at
    # their arc fractions): the runtime adds it back, so the rest pose is its rest curve and a pose bends the stretch as
    # its Hermite bends (re-drawn on the bare Hermite the ramps lost their designed climbs: 12.7 deg at ring 488 at rest)
    fair_d = np.zeros((N, 3))
    run_tot = []
    i = 0
    while i < N:
        if kind[i] != 1:
            i += 1
            continue
        a_r = i
        while i + 1 < N and kind[i + 1] == 1:
            i += 1
        b_r = i
        i += 1
        if b_r - a_r < 2:
            continue
        pre_ = 0
        while pre_ < 2 and a_r - pre_ - 1 >= 0 and kind[a_r - pre_ - 1] == 0:
            pre_ += 1
        post_ = 0
        while post_ < 2 and b_r + post_ + 1 < N and kind[b_r + post_ + 1] == 0:
            post_ += 1
        idx = np.arange(a_r - pre_, b_r + post_ + 1)
        RPr = Pr[idx].copy()
        for _ in range(RUN_SMOOTH):
            T_ = RPr.copy()
            RPr[pre_ + 1:pre_ + (b_r - a_r)] = 0.25 * (T_[pre_:pre_ + (b_r - a_r) - 1] + 2 * T_[pre_ + 1:pre_ + (b_r - a_r)]
                                                      + T_[pre_ + 2:pre_ + (b_r - a_r) + 1])
        M_ = len(idx)
        k = 1
        while k <= M_ - 2:
            if not (kind[idx[k]] == 1 and sm_[idx[k]] > 0):
                k += 1
                continue
            k2 = k
            while k2 + 1 <= M_ - 2 and kind[idx[k2 + 1]] == 1 and sm_[idx[k2 + 1]] > 0:
                k2 += 1
            A_, B_ = k - 1, k2 + 1
            unit_ = lambda v_: v_ / np.linalg.norm(v_)
            u0_ = unit_(RPr[A_] - RPr[A_ - 1]) if A_ >= 1 else unit_(RPr[B_] - RPr[A_])
            u1_ = unit_(RPr[B_ + 1] - RPr[B_]) if B_ <= M_ - 2 else unit_(RPr[B_] - RPr[A_])
            cs_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(RPr[A_:B_ + 1], axis=0), axis=1))])
            t_ = cs_ / cs_[-1]
            L_ = np.linalg.norm(RPr[B_] - RPr[A_])
            for q_ in range(1, B_ - A_):
                tt = t_[q_]
                h00, h10 = 2 * tt ** 3 - 3 * tt ** 2 + 1, tt ** 3 - 2 * tt ** 2 + tt
                h01, h11 = -2 * tt ** 3 + 3 * tt ** 2, tt ** 3 - tt ** 2
                Hq = h00 * RPr[A_] + h10 * L_ * u0_ + h01 * RPr[B_] + h11 * L_ * u1_
                ring = int(idx[A_ + q_])
                _, _, e1f, nf, e2f = a_frame[ring]
                dq = RPr[A_ + q_] - Hq
                fair_d[ring] = [dq @ e1f, dq @ nf, dq @ e2f]
            k = k2 + 2
        # C5f (the lead's call 8): the run's REST path length as the runtime's relay lays it (its control points
        # smoothed, every faired stretch on its rest rings: relay's fairing returns them there at rest): where the skin
        # shortens a run's path below it, the runtime slides the difference into the hump beside it (relay's lend)
        RPt = RPr.copy()
        fz = np.array([kind[q_] == 1 and sm_[q_] > 0 for q_ in idx])
        fz[[0, -1]] = False
        RPt[fz] = Pr[idx[fz]]
        run_tot.append([int(a_r), float(np.linalg.norm(np.diff(RPt[pre_:pre_ + (b_r - a_r) + 1], axis=0), axis=1).sum())])
    # the BLEND by each clamp: an anchored ring within CLAMP_BLEND (along the hose, at rest) of a clamp's face is drawn
    # toward where the clamp's rigid frame carries it, wholly at the face, smoothly to none at CLAMP_BLEND: the skin
    # under and round a pad stretches and shrinks with the arm (by 1.3 mm round clamp 2 in the swim) while the clamp
    # holds its length, and a ring anchored just past its face folded back over it (a 128 deg turn, s14)
    blend = []
    for cl, fi, Mc in pads:
        rc = np.nonzero((kind == 0) & (ref == fi))[0]
        for e_, sgn in ((rc.min(), -1), (rc.max(), 1)):
            q = e_ + sgn
            while 0 <= q < N and kind[q] == 1 and abs(s[q] - s[e_]) < CLAMP_BLEND * r:
                u_ = abs(s[q] - s[e_]) / (CLAMP_BLEND * r)
                w_ = 1.0 - u_ * u_ * (3.0 - 2.0 * u_)
                lq = (Pr[q] - Mc[:3, 3]) @ Mc[:3, :3]
                blend.append([int(q), int(fi), *map(float, lq), float(w_)])
                q += sgn
    # each LYING RUN's rings laid along its anchors at their rest arc fractions (the runtime's relay): per interior ring
    # its fraction of the run's rest polyline from its first ring to its last
    frac_r = np.zeros(N)
    i = 0
    while i < N:
        if kind[i] != 1:
            i += 1
            continue
        j_ = i
        while j_ + 1 < N and kind[j_ + 1] == 1:
            j_ += 1
        if j_ - i >= 2:
            cs_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pr[i:j_ + 1], axis=0), axis=1))])
            frac_r[i:j_ + 1] = cs_ / cs_[-1]
        i = j_ + 1
    # ---------------------------------------------------------------- the spans
    Tc = np.zeros_like(Pr)
    Tc[1:-1] = Pr[2:] - Pr[:-2]
    Tc[0], Tc[-1] = Pr[1] - Pr[0], Pr[-1] - Pr[-2]
    Tc /= np.linalg.norm(Tc, axis=1, keepdims=True)
    crest = {sp_['b']: sp_ for sp_ in HO['spans']}
    fl_f, fl_V = None, None
    spans = []
    i = 0
    while i < N:
        if kind[i] != 2:
            i += 1
            continue
        a_ = i
        while i < N and kind[i] == 2:
            i += 1
        b_ = i - 1
        A_, B_ = a_ - 1, b_ + 1
        assert A_ >= 0 and B_ < N, 'a free span at the hose\'s end'
        seg = np.linalg.norm(np.diff(Pr[A_:B_ + 1], axis=0), axis=1)
        L0 = float(seg.sum())
        frac = (np.cumsum(seg)[:-1] / L0).tolist()

        def end_specs(e, out_dir):
            """the end ring e's tangent (along the hose) and up axis: rigid in its frame or in its anchor frame"""
            t_ = Tc[e]
            if kind[e] == 0:
                f_ = int(ref[e])
                if f_ == 0:
                    M_ = Mfit
                    tl, ul = dir_bind(M_, t_[None])[0], dir_bind(M_, np.asarray(rec['fitting']['normal'])[None])[0]
                    ul = np.asarray(rec['fitting']['normal'], np.float64)
                    tl = tl / np.linalg.norm(tl)
                elif f_ == 1:
                    P7b, C7b = CO.flange_frame(oct_, j)
                    tl = dir_bind(M7, t_[None])[0]
                    tl = tl / np.linalg.norm(tl)
                    ul = C7b[:, 1]
                else:
                    Mc_ = frames_M[f_]
                    k_ = [cl_['k'] for cl_, f2, _ in pads if f2 == f_][0]
                    cl_ = [c_ for c_ in clamps if c_['k'] == k_][0]
                    tl = Mc_[:3, :3].T @ cl_['R'][:, 0]
                    if tl @ (Mc_[:3, :3].T @ t_) < 0:
                        tl = -tl
                    ul = Mc_[:3, :3].T @ cl_['R'][:, 1]
                return ['frame', f_, *map(float, tl)], ['frame', f_, *map(float, ul)]
            a2, Xa, e1a, na, e2a = a_frame[int(e)]
            tl = np.array([t_ @ e1a, t_ @ na, t_ @ e2a])
            return ['anchor', a2, *map(float, tl)], ['anchor', a2]
        frames_M = {f_: M_ for _, f_, M_ in pads}
        ta, ua = end_specs(A_, 1)
        tb, ub = end_specs(B_, -1)
        nm_set = {str(piece[q]) for q in range(a_, b_ + 1)} - {''}
        bp = float(crest['port']['crest_power']) if 'rise' in nm_set and 'port' in crest else 1.0
        # the lower bounds: each free ring's skin point under it (anchored), the clearance its rest pose had there (at
        # most r + BOUND_MARGIN, never more than the rest height less BOUND_TOL); the rise also over the flange
        fr = np.arange(a_, b_ + 1)
        bi, Xb, _, nb_, _ = anchor(Pr[fr])
        hb = ((Pr[fr] - Xb) * nb_).sum(1)
        bounds = dict(ring=[int(q) for q in fr], kind=[1] * len(fr), ref=[int(q) for q in bi], loc=[0.0] * (6 * len(fr)),
                      clear=[float(min(h_ - BOUND_TOL, r + BOUND_MARGIN)) for h_ in hb])
        if 'rise' in nm_set:
            if fl_f is None:
                isl = ctx.I['islands']
                fl_f = np.concatenate([ctx.mech.F[it_['f'][0]:it_['f'][1]] for it_ in isl
                                       if it_['region'] in ('roll', 'collar', 'collar_end', 'screw', 'band', 'boss')])
                P7b, C7b = CO.flange_frame(oct_, j)
                fl_V = P7b + ctx.mech.V @ C7b.T                 # the flange's pieces in the bind
            Vfl = (M7 @ np.c_[fl_V, np.ones(len(fl_V))].T).T[:, :3]
            sd, ti = CO.point_tri_near(Pr[fr], Vfl[fl_f[:, 0]], Vfl[fl_f[:, 1]], Vfl[fl_f[:, 2]], k=32)
            A3, B3, C3 = Vfl[fl_f[ti, 0]], Vfl[fl_f[ti, 1]], Vfl[fl_f[ti, 2]]
            q3 = CO.closest_on_tri(Pr[fr], A3, B3, C3)
            n3 = np.cross(B3 - A3, C3 - A3)
            n3 /= np.linalg.norm(n3, axis=1, keepdims=True)
            n3 *= np.sign(((Pr[fr] - q3) * n3).sum(1))[:, None]
            h3 = ((Pr[fr] - q3) * n3).sum(1)
            near = h3 < r + 3.0e-3
            for q_, ok in zip(range(len(fr)), near):
                if not ok:
                    continue
                pb = to_bind(M7, q3[q_][None])[0]
                nb2 = dir_bind(M7, n3[q_][None])[0]
                nb2 /= np.linalg.norm(nb2)
                bounds['ring'].append(int(fr[q_]))
                bounds['kind'].append(0)
                bounds['ref'].append(1)
                bounds['loc'] += [*map(float, pb), *map(float, nb2)]
                bounds['clear'].append(float(min(h3[q_] - BOUND_TOL, r + FLANGE_MARGIN)))
        # the shape: an arch or a hump between two holds the arm brings together (the swim pressed arch 1's pads from 42
        # to 33 mm) takes the least-bending curve of its length (the runtime's ELASTICA: a Hermite and a sin^2 bow bent to
        # 4 mm there, the least-bending curve to 8.2 mm); the descent and the rise keep the forge's Hermite and bow (the
        # rise's crest power clears the soft roll by itself at rest: drawn as an elastica and lifted over the roll it
        # kinked at the port, 2.8 mm, s12)
        model = 'elastica' if all(x.startswith(('arch', 'hump')) for x in nm_set) else 'hermite'
        # C5e: the span's REST SHAPE for the runtime's rod (cyborg_cable.js rodSolve): its NR + 1 nodes at equal arc
        # fractions of its rest polyline (NR the runtime's: ceil(L0 / ROD_STEP_MM) within ROD_NR), in the frame of its
        # rest chord (x), its ends' up axes' mean made normal to it (y: as the runtime takes them, rigid in their frames
        # or the end anchors' normals, here at the reference pose) and x cross y (z), with the chord's length: the
        # runtime carries it by its ends as the rod's initial shape and its tether's target (no mirror flip, no lean axis)
        Mf_ = {0: Mfit, 1: M7, **frames_M}

        def up_w(e, spec):
            u_ = Mf_[spec[1]][:3, :3] @ np.asarray(spec[2:5], np.float64) if spec[0] == 'frame' else a_frame[int(e)][3]
            return u_ / np.linalg.norm(u_)
        nR_ = int(min(ROD_NR[1], max(ROD_NR[0], math.ceil(L0 * 1e3 / ROD_STEP_MM))))
        ex_ = Pr[B_] - Pr[A_]
        d_rest = float(np.linalg.norm(ex_))
        ex_ = ex_ / d_rest
        up_ = up_w(A_, ua) + up_w(B_, ub)
        ey_ = up_ - (up_ @ ex_) * ex_
        ey_ /= np.linalg.norm(ey_)
        ez_ = np.cross(ex_, ey_)
        cs_r = np.concatenate([[0.0], np.cumsum(seg)])
        tq_ = np.linspace(0.0, cs_r[-1], nR_ + 1)
        G_ = np.column_stack([np.interp(tq_, cs_r, Pr[A_:B_ + 1, k_]) for k_ in range(3)]) - Pr[A_]
        rest_ = np.column_stack([G_ @ ex_, G_ @ ey_, G_ @ ez_])
        spans.append(dict(first=int(a_), last=int(b_), L0=L0, frac=frac, k0=1.0, k1=1.0, bp=bp, ta_spec=ta,
                          tb_spec=tb, ua_spec=ua, ub_spec=ub, lift_w=float(np.clip(4.0 * r / L0, 0.08, 0.5)),
                          bounds=bounds, pieces=sorted(nm_set), model=model,
                          rest=[float(x_) for x_ in rest_.ravel()], rest_d=d_rest))
        # C5f (the lead's call 5): a CONVOLUTED arch (cyborg_hose BELLOWS): the runtime keeps its length over its chord
        # at the rest ratio, within `compress` of its rest length, its rings at their rest fractions (they bunch)
        if nm_set and nm_set <= {b_['piece'] for b_ in HO.get('bellows') or []}:
            spans[-1].update(bellows=True, compress=[float(x_) for x_ in CH.BELLOWS['compress']])
    # ---------------------------------------------------------------- the pads, straps and rivets
    from . import bake as BK
    P_kind, P_frame, P_ref, P_loc, P_nrm, P_link, P_w, P_rig, P_tan = [], [], [], [], [], [], [], [], []
    contacts = []

    def tans(prt, R_):
        """a part's tangents in the reference pose (the bake's frames on its UVs), in the clamp frame, with their sign"""
        _, T4 = BK.low_frames(np.asarray(prt['V'], np.float64), np.asarray(prt['F'], np.int64),
                              np.asarray(prt['UV'], np.float64), np.asarray(prt['N'], np.float64))
        return np.column_stack([T4[:, :3] @ R_, T4[:, 3]])
    for cl, fi, Mc in pads:
        R_, o_ = Mc[:3, :3], Mc[:3, 3]
        V_pad = np.asarray(cl['pad']['V'], np.float64)
        N_pad = np.asarray(cl['pad']['N'], np.float64)
        part = np.asarray(cl['pad']['part'])
        base = len(P_kind)
        Lc = (V_pad - o_) @ R_
        Nc = N_pad @ R_
        P_tan += list(tans(cl['pad'], R_))
        for prt in [cl['strap']] + list(cl['rivets']):
            P_tan += list(tans(prt, R_))
        und, ai_u, Xu, e1u, nu, e2u = under_of[cl['k']]
        for v_ in range(len(V_pad)):
            # C5e: every pad vertex RIGID in its clamp frame (the lead's C5e call: the pads rigid in every motion; C5d
            # anchored the underside on the skin and blended the flanks, and the swim shortened pad 1 by 11-18 %)
            P_frame.append(fi)
            P_nrm.append(Nc[v_])
            P_rig.append(Lc[v_])
            P_kind.append(0)
            P_ref.append(-1)
            P_link.append(-1)
            P_w.append(0.0)
            P_loc.append(Lc[v_])
        for prt in [cl['strap']] + list(cl['rivets']):
            Vp_ = np.asarray(prt['V'], np.float64)
            Np_ = np.asarray(prt['N'], np.float64)
            for v_ in range(len(Vp_)):
                P_kind.append(0)
                P_frame.append(fi)
                P_ref.append(-1)
                P_loc.append((Vp_[v_] - o_) @ R_)
                P_nrm.append(Np_[v_] @ R_)
                P_link.append(-1)
                P_w.append(0.0)
                P_rig.append((Vp_[v_] - o_) @ R_)
        # the contact: the underside's footprint in the bind (its anchors' bind points)
        tri_u = np.array([anchors[a2][:3] for a2 in ai_u])
        inv_sv = np.array(sorted(skin_v, key=skin_v.get))
        bc_u = np.array([anchors[a2][3:] for a2 in ai_u])
        Pb = (bc_u[:, :, None] * oct_.low['V'][inv_sv[tri_u]]).sum(1)
        Qb = (V_pad[und] - cl['c']) @ cl['R']
        xb_ = Pb[Qb[:, 0].argmax()] - Pb[Qb[:, 0].argmin()]
        xb_ /= np.linalg.norm(xb_)
        cen = Pb.mean(0)
        dev = Pb - cen
        nb3 = np.linalg.svd(dev)[2][2]
        if nb3 @ (cl['R'][:, 1]) < 0:
            nb3 = -nb3
        # C5e: the footprint wholly from the BIND points (the C5d check: its half-sizes came from the reference pose,
        # 6.12 x 6.54 mm on every pad, its centre and axes from the bind, and the underside's bind points stood up to
        # 1.6-2.0 mm outside it): the axis made to lie in the footprint's plane, z = n x x as the shader takes it, the
        # centre the middle of the points' extents along both, the half-sizes those extents' halves
        xb_ = xb_ - (xb_ @ nb3) * nb3
        xb_ /= np.linalg.norm(xb_)
        zb_ = np.cross(nb3, xb_)
        ub_, wb_ = dev @ xb_, dev @ zb_
        cen = cen + 0.5 * (ub_.max() + ub_.min()) * xb_ + 0.5 * (wb_.max() + wb_.min()) * zb_
        contacts.append(dict(k=int(cl['k']), c=[*map(float, cen)], x=[*map(float, xb_)], n=[*map(float, nb3)],
                             hl=float(0.5 * (ub_.max() - ub_.min())), hw=float(0.5 * (wb_.max() - wb_.min()))))
    sl_tan = np.asarray(HO['sleeve']['TAN'], np.float64)
    data = dict(version=1, r=r, sides=int(rec['sides']), rings=int(N), skin='octopus_head',
                skin_verts=[int(v_) for v_ in sorted(skin_v, key=skin_v.get)],
                anchors=[float(x_) if q % 6 >= 3 else int(x_) for a_ in anchors for q, x_ in enumerate(a_)],
                frames=frames, ring_kind=[int(k_) for k_ in kind], ring_ref=[int(x_) for x_ in ref],
                ring_loc=[float(x_) for x_ in loc.ravel()], ring_blend=blend,
                ring_frac=[float(x_) for x_ in frac_r], spans=spans,
                rho=float(rho), ring_contact_start=[int(x_) for x_ in c_start], ring_contact=c_list,
                ring_lift=[float(x_) for x_ in lift], ring_fair=[float(x_) for x_ in sm_],
                ring_s=[float(x_) for x_ in s],
                ring_fair_d=[float(x_) for x_ in fair_d.ravel()],
                # C5f: each lying run's rest path as relay lays it (the lend into a hump, call 8); each ring's radius
                # where a convoluted section makes them differ (call 5: the sleeve's rings and normals follow it)
                run_tot=run_tot,
                **({'ring_r': [float(x_) for x_ in HO['ring_r']]} if HO.get('ring_r') is not None
                   and float(np.ptp(HO['ring_r'])) > 0.0 else {}),
                e1_0=[0, *map(float, np.asarray(rec['fitting']['normal'], np.float64))],
                tan_w=float(np.sign(np.median(sl_tan[:, 3])) or 1.0),
                pads=dict(n=len(P_kind), kind=P_kind, frame=P_frame, ref=P_ref,
                          loc=[float(x_) for v_ in P_loc for x_ in v_], nrm=[float(x_) for v_ in P_nrm for x_ in v_],
                          link=P_link, w=P_w, rig=[float(x_) for v_ in P_rig for x_ in v_],
                          tan=[float(x_) for v_ in P_tan for x_ in v_]),
                contacts=contacts)
    log(f'[cable] {N} rings: {int((kind == 0).sum())} rigid, {int((kind == 1).sum())} anchored, {int((kind == 2).sum())} '
        f'free in {len(spans)} spans ({", ".join("+".join(sp_["pieces"]) for sp_ in spans)}); {len(anchors)} anchors on '
        f'{len(skin_v)} skin vertices; {len(P_kind)} pad vertices ({sum(1 for k_ in P_kind if k_ == 1)} anchored, '
        f'{sum(1 for k_ in P_kind if k_ == 2)} blended)')
    return data
