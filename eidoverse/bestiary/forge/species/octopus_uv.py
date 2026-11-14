"""The octopus cage's UVs: seams from the cage's own structure, LSCM + ARAP per island, two texture sets.

SET 'head' (2048): the mantle and head (cut ventrally), the apex cap, the crown's top and bottom layers in eight
sectors each (the bottom's with an eighth of the mouth's lip), the funnel (unrolled), the eyes' hidden tucks.
SET 'arms' (2048): ONE arm tube (cut at its margin ring and along its oral midline), all eight STACKED on it (the
arms are identical by construction; per-arm variation comes at runtime in the shader).
"""
import numpy as np

from .. import uv as U

BAND_FOLD = 37.0        # degrees: the back's junction band is cut off while it folds this far against the crown (seams)


def seams(info, cage):
    K = info['K']
    S = []
    loop_edges = lambda ring: [(int(ring[i]), int(ring[(i + 1) % len(ring)])) for i in range(len(ring))]
    body = info['body']
    S += loop_edges(body[0])                        # the apex island's rim
    S += loop_edges(body[-1])                       # the head ring: body | crown top
    # the COLLAR (the mantle's front): mantle | head as two islands. One island from the apex to the crown fanned past
    # a full turn beyond the neck and laid the head's UVs over the mantle's (t08's anisotropy map: an overlapping lobe,
    # the crumpled eye region and the smears round the funnel). The last ring behind the eyes' blocks (the mantle's
    # free margin lies just behind the eyes, octopus.collar). r4 took the narrowest intact ring for its neck; v4's
    # mantle runs into the head without one and its rings lean, so that ring lay past the eyes, four short of the head
    # ring: the mantle's island took the whole body with both eye holes and the head band fell into four strips (t08
    # v4 check)
    lo, hi = int(0.35 * len(body)), int(0.92 * len(body))
    for er in info['eye_rings']:
        on = np.nonzero(np.isin(body, er[0]).any(1))[0]
        if len(on):
            hi = min(hi, int(on.min()))
    i_col = max(hi, lo + 1) - 1
    S += loop_edges(body[i_col])
    info['collar_ring'] = i_col
    # the head band (collar to crown) halved on its DORSAL midline (column 0 runs between the eyes): one eye hole per
    # half; three holes in one band still folded its unwrap (t08)
    for i in range(i_col, len(body) - 1):
        a, b = int(body[i, 0]), int(body[i + 1, 0])
        if a >= 0 and b >= 0:
            S.append((a, b))
    kb = K // 2                                     # the ventral (back) midline
    S += [(int(body[i, kb]), int(body[i + 1, kb])) for i in range(len(body) - 1)
          if body[i, kb] >= 0 and body[i + 1, kb] >= 0]
    # where the midline meets the funnel's block (its rectangle, fr[0]) the cut carries on through the block's two
    # body-side bands to the funnel's own seam at the footprint (fr[2]); the rings correspond vertex for vertex. A cut
    # ending two bands short of the hole left a slit in the middle of the surface, and ARAP folded the head band over
    # itself there (t08: 486 overlapping texels beside the funnel, under t14's jagged smears). No rings: the cage was
    # built without its funnel port (build_cage says why)
    fr = info['funnel_rings']
    for v in (body[:, kb] if len(fr) else []):
        m = np.nonzero(fr[0] == v)[0]
        if v >= 0 and len(m):
            S += [(int(fr[r][m[0]]), int(fr[r + 1][m[0]])) for r in range(2)]
    # the crown in SECTORS: the top layer cut down every web's middle column (one of them the back's), an arm's aboral
    # half and two half webs to an island; the bottom down every arm's oral midline, the arm tube's own oral cut carried
    # on through the layer, the mouth's reduction strips and its lip to the rim (a web's underside, two half arms and an
    # eighth of the mouth to an island). Whole, each layer wraps eight half tubes: v4's deep webs and thick arms folded
    # both at every ARAP depth, and LSCM laid 108 texels over themselves (t08 v4)
    top, bot, mr = info['top'], info['bot'], info['mouth_rings']
    sect = K // len(info['arm_rings'])
    for j in range(len(info['arm_rings'])):
        kw = (sect * (j + 1)) % K                   # web j's middle column (to its rim: the margin crosses rows, -1 past
        S += [(int(top[r, kw]), int(top[r + 1, kw])) for r in range(top.shape[0] - 1)     # a column's end, crown v5)
              if top[r, kw] >= 0 and top[r + 1, kw] >= 0]
        c = sect // 2 + sect * j                    # arm j's centre column
        S += [(int(bot[r, c]), int(bot[r + 1, c])) for r in range(bot.shape[0] - 1)]
        chain = [int(bot[0, c])] + [int(rg[c >> (m + 1)]) for m, rg in enumerate(info['mouth_red'])]
        S += list(zip(chain[:-1], chain[1:]))
        i_m = int(np.nonzero(mr[0] == chain[-1])[0][0])
        S += [(int(mr[m][i_m]), int(mr[m + 1][i_m])) for m in range(5)]
    # the BACK's junction BAND (crown v5b): where a top column's junction is a concave fold (the mantle resting on the
    # crown's back face; octopus.build_cage pins a row on its crease, info['crease_row']), the rows from the head ring
    # to the crease lie on the mantle's underside and the seat, folded back against the crown top beyond them, and on
    # round the ring the first row stays folded where the ring climbs the mantle's sides: in the crown top's sectors
    # ARAP laid that band over itself at every depth (crown v5's islands 5 / 6 shipped as LSCM, the band's texels at
    # 0.33 of the island's density). The band is cut off: per quad between columns k and k + 1 its rows 0 .. rq (the
    # deeper crease of the two, else row 1), over the crease columns' run grown round the ring while the band's last
    # quad stands more than BAND_FOLD off the next row's, within the crease's two sectors (v5b's cage: quads 48-79,
    # 37-122 deg at the ring's corners; past the D webs' middle seams the next sectors' bands fold less and lie flat
    # under ARAP), mirrored; its own island each side of the back's midline seam
    cr = info.get('crease_row')
    if cr is not None and (cr > 0).any():
        Vc = cage.V
        sect_ = K // len(info['arm_rings'])
        rq = [max(int(cr[k]), int(cr[(k + 1) % K]), 1) for k in range(K)]

        def qn(a, b, c, d):
            n = np.cross(Vc[c] - Vc[a], Vc[d] - Vc[b])
            return n / max(np.linalg.norm(n), 1e-20)

        def folds(k):
            k1, r = (k + 1) % K, rq[k]
            if min(top[r - 1, k], top[r - 1, k1], top[r + 1, k], top[r + 1, k1]) < 0:
                return False
            return qn(top[r - 1, k], top[r - 1, k1], top[r, k1], top[r, k]) @ \
                qn(top[r, k], top[r, k1], top[r + 1, k1], top[r + 1, k]) < np.cos(np.radians(BAND_FOLD))
        inb = np.array([cr[k] > 0 and cr[(k + 1) % K] > 0 for k in range(K)])
        grow = True
        while grow:
            grow = False
            for k in range(K):              # (into quad k across column k or k + 1, never a sector's seam column)
                if not inb[k] and ((inb[(k - 1) % K] and k % sect_) or (inb[(k + 1) % K] and (k + 1) % sect_)) and \
                        folds(k):
                    inb[k] = grow = True
        inb |= inb[(K - 1 - np.arange(K)) % K]          # quad k's mirror image is quad K - 1 - k
        for k in np.nonzero(inb)[0]:
            k1 = (k + 1) % K
            S.append((int(top[rq[k], k]), int(top[rq[k], k1])))
            r_lo, r_hi = (sorted((rq[k], rq[k1])) if inb[k1] else (0, rq[k]))     # on along the next quad's, or the
            S += [(int(top[r, k1]), int(top[r + 1, k1])) for r in range(r_lo, r_hi)]   # run's end down to the ring
            if not inb[(k - 1) % K]:
                S += [(int(top[r, k]), int(top[r + 1, k])) for r in range(rq[k])]
    S += [(int(a), int(b)) for a, b in info['creases']]        # web rims: top | bottom
    # the arms' bare runs from each web's meeting point out to the tube's first ring (crown v5: the top and bottom
    # layers meet along them as along the rims; left joined, every top sector would join its two bottom neighbours)
    S += [(int(a), int(b)) for a, b in info.get('side_seams', [])]
    for rings in info['arm_rings']:
        S += loop_edges(rings[0])                   # crown | arm tube
        S += [(int(rings[i][12]), int(rings[i + 1][12])) for i in range(len(rings) - 1)]   # the oral midline
        # the tube in 3 lengths (a whole arm is one long sliver on a square sheet: t08 left 83 % of it empty)
        n = len(rings)
        for cut in (int(n * 0.30), int(n * 0.62)):
            S += loop_edges(rings[cut])
        # the tip's domed cap its own island: the oral cut stopped at its rim, so the whole closed end had to flatten
        # round one point (a 2 pi cone): ARAP folded it and LSCM squeezed it (t08: the arm set lost 16 % of its density)
        S += loop_edges(rings[-1])
    if len(fr):
        S += loop_edges(fr[2])                      # body | funnel (at the footprint)
        S += [(int(fr[m][0]), int(fr[m + 1][0])) for m in range(2, len(fr) - 1)]
        S += loop_edges(fr[-1])                     # the lumen's cap its own island (the arm tips' 2 pi cone again)
    # the mouth: the lip's rim | the opening's wall (a strip, cut down one side) | the cap at its end (the arm tips'
    # cone once more): mostly behind the beak
    S += loop_edges(mr[5])
    S += [(int(mr[m][0]), int(mr[m + 1][0])) for m in range(5, len(mr) - 1)]
    S += loop_edges(mr[-1])
    for er in info['eye_rings']:
        S += loop_edges(er[0])                      # body | the eye's lid (a tight fold: its own island)
        S += loop_edges(er[3])                      # the lid's edge | the hidden tuck (er: loop, halfway, fold, edge..)
        # a seam from the eye's hole down its body column to the crown ring: holes opening onto nothing made the head
        # band's unwrap fold over itself round the eyes (t08: 4.7 % of the head set's texels overlapping)
        pos = np.argwhere(np.isin(body, er[0]))
        if len(pos):
            i_max = int(pos[:, 0].max())
            ang = pos[:, 1] * (2 * np.pi / K)
            k_mid = int(round(np.angle(np.exp(1j * ang).mean()) / (2 * np.pi / K))) % K
            for i in range(i_max, len(body) - 1):
                a, b = int(body[i, k_mid]), int(body[i + 1, k_mid])
                if a >= 0 and b >= 0:
                    S.append((a, b))
    return S


def unwrap(cage, info, size=2048, pad=8, arap_iters=8, log=print):
    S = seams(info, cage)
    lab = U.islands(cage.Q, S)
    Vn, Qn, orig = U.split(cage.V, cage.Q, lab, S)
    n_isl = lab.max() + 1
    # which islands are arms (any vertex of an arm region): region ids 3.. are arms
    part = cage.attrs['part'].argmax(1)
    isl_arm = np.zeros(n_isl, int) - 1
    for f in range(len(cage.Q)):
        r = part[cage.Q[f]].max()
        if r >= 3:
            isl_arm[lab[f]] = r - 3
    UVn = np.zeros((len(Vn), 2))
    dens = {}
    tris_of = {}
    for i in range(n_isl):
        fq = np.nonzero(lab == i)[0]
        F = U._tri(Qn[fq])
        vs = np.unique(F)
        loc = -np.ones(len(Vn), np.int64)
        loc[vs] = np.arange(len(vs))
        Fl = loc[F]
        P = Vn[vs]
        uv = U.lscm(P, Fl)
        # ARAP evens the texel density but is not injective (it can fold an island over itself) and not always the
        # better map: per island, the depth whose worst-direction texel footprint is smallest among those that lie
        # flat (t08: ARAP folded the arm tip and the head band beside the funnel, and stretched the apex cap 2:1).
        # Arms 1..7 skip it: they take arm 0's UVs below
        if arap_iters and isl_arm[i] <= 0:
            best, cand, done = None, uv, 0
            for it in (0, 2, max(arap_iters // 2, 3), arap_iters):
                if it > done:
                    cand, done = U.arap(P, Fl, cand, it - done), it
                if U.self_overlap(cand, Fl):
                    continue
                fp = U.footprint(P, Fl, cand)
                if best is None or fp < best[0]:
                    best = (fp, it, cand)
            if best is None:
                log(f'[uv] ⚠ island {i}: every ARAP depth folded it, LSCM kept')
                best = (U.footprint(P, Fl, uv), 0, uv)
            uv = best[2]
            if best[1] != arap_iters:
                log(f'[uv] island {i}: ARAP {best[1]} (worst-direction footprint p95 {best[0]:.2f})')
        # orientation: keep the triangles counter-clockwise in UV
        d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
        if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
            uv[:, 0] = -uv[:, 0]
        UVn[vs] = uv
        dens[i] = U.island_density(P, Fl, uv)
        tris_of[i] = (vs, Fl)
    # the sets: arms -> one island (arm 0's) stacked; head -> the rest
    arm_isl = [i for i in range(n_isl) if isl_arm[i] >= 0]
    head_isl = [i for i in range(n_isl) if isl_arm[i] < 0]
    # the eyes' tucks lie behind the eyeballs, never seen: a quarter of the density; the mouth's wall and cap behind
    # the beak, glimpsed past it: half. Their texels go back to the skin
    shares = {}
    for er in info['eye_rings']:
        shares.update({int(lab[f]): 0.25 for f in np.nonzero(np.isin(cage.Q, er[4]).any(1))[0]})
    mr = info['mouth_rings']
    shares.update({int(lab[f]): 0.5 for f in np.nonzero(np.isin(cage.Q, np.concatenate(mr[6:])).any(1))[0]})
    share = lambda i: shares.get(i, 1.0)
    sets = {}
    for name, ids in (('head', head_isl), ('arms', [i for i in arm_isl if isl_arm[i] == 0])):
        if not ids:
            continue
        area = sum(0.5 * np.linalg.norm(np.cross(Vn[tris_of[i][0]][tris_of[i][1][:, 1]] - Vn[tris_of[i][0]][tris_of[i][1][:, 0]],
                                                 Vn[tris_of[i][0]][tris_of[i][1][:, 2]] - Vn[tris_of[i][0]][tris_of[i][1][:, 0]]),
                                        axis=1).sum() for i in ids)
        # the density: start at ~70 % fill, then grow or shrink until the packed height fills ~97 % of the sheet
        px_per_m = np.sqrt(0.70 * size * size / area)
        uvs = [UVn[tris_of[i][0]] for i in ids]
        for _ in range(12):
            scales = [px_per_m * share(i) / dens[i] for i in ids]
            try:
                packed, used = U.pack(uvs, scales, size, pad)
            except ValueError:
                used = 9.9
            if 0.93 <= used <= 0.985:
                break
            px_per_m *= (0.97 / used) ** 0.5 if used < 9.0 else 0.8
        else:
            scales = [px_per_m * share(i) / dens[i] for i in ids]
            packed, used = U.pack(uvs, scales, size, pad)
            while used > 1.0:
                px_per_m *= 0.97
                packed, used = U.pack(uvs, [px_per_m * share(i) / dens[i] for i in ids], size, pad)
        for i, pk in zip(ids, packed):
            UVn[tris_of[i][0]] = pk
        sets[name] = dict(islands=ids, px_per_m=float(px_per_m), used=float(used))
        log(f'[uv] set {name}: {len(ids)} islands, {px_per_m:.0f} px/m ({1000/px_per_m:.3f} mm/texel), '
            f'height used {used*100:.0f} %')
    # arms 1..7 STACKED on arm 0 by EXACT correspondence: the arms are built by one loop in one order, so the i-th face
    # of arm j is the i-th face of arm 0 rotated, and its corners take arm 0's corners' UVs one for one. Matching by
    # position was ambiguous wherever two copies of a seam vertex share a point: across islands at the length cuts
    # (t11b's pale zigzags) and WITHIN an island along its oral cut (t14: a brown stripe between the sucker rows,
    # triangles stretched across the island's width). The rotated corners are checked against arm 0's.
    from .octopus import arm_azimuths
    az = arm_azimuths()[info['order']]                 # azimuth of arm j (column order)
    face_arm = np.array([isl_arm[lab[f]] for f in range(len(cage.Q))])
    f0 = np.nonzero(face_arm == 0)[0]
    worst = 0.0
    for j in range(1, int(face_arm.max()) + 1):
        fj = np.nonzero(face_arm == j)[0]
        assert len(fj) == len(f0), f'arm {j}: {len(fj)} faces against arm 0\'s {len(f0)}'
        d = az[0] - az[j]
        c, s = np.cos(d), np.sin(d)
        R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])    # rotation about +Y by d (z toward x for d > 0)
        cj, c0 = Qn[fj].reshape(-1), Qn[f0].reshape(-1)
        worst = max(worst, float(np.linalg.norm(Vn[cj] @ R.T - Vn[c0], axis=1).max()))
        UVn[cj] = UVn[c0]
    log(f'[uv] arms stacked on arm 0 by face correspondence: worst rotated corner {worst*1000:.3f} mm')
    face_set = np.array(['arms' if isl_arm[lab[f]] >= 0 else 'head' for f in range(len(cage.Q))])
    return dict(V=Vn, Q=Qn, orig=orig, UV=UVn, label=lab, isl_arm=isl_arm, sets=sets, face_set=face_set)
