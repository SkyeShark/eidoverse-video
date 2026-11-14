"""HUMAN H1: the HEAD of the baseline cage on GNM's OWN TOPOLOGY (HUMAN_PLAN §2.3, §6.2; the lead's H1 decisions 1-4).

WHY GNM's topology, not a designed box layout (10-28, the restarted H1 builder): the box layout (H0's dense_groove2 carried
on by the first H1 run) tangled at the eye, the nose and the ear and printed a fin across the upper lid and sheets behind
the ear (h1/look/head_fit_F_features_clay.png of 05:52). GNM Head v3's skin (Apache-2.0) is a production quad mesh whose
loops already lie on every feature the lead's decision 3 asks for: the lid margins round to their canthi (taken from the
lids' own shape: the loops ARE the lid), the alar-facial groove, the vermilion and the lip roll into a closed mouth sock,
the nostril tubes, the ear's folds as loops (no helix crease); 114 poles, placed by its artists off the deformation loops.
Its targets are GNM's own vertices, so the identity map (plan §3.2) is exactly linear: the cage's target of vertex v at
any identity is GNM's vertex v (a fixed barycentric point where a vertex is new or re-placed). Above the mid-neck ring it
is 10,140 quads: 20.3k triangles at level 0, about the plan's §8 head budget of 20k (the lead's ~7-8k was the box
layout's need).

THE CHANGES TO GNM's skin:
  NECK    cut at the GNM neck loop (110 vertices) whose lowest point clears the mid-neck plane by cut_clear on both
          sexes; under it two REDUCTION BANDS (110 -> 78 -> 48: 4 -> 2 units, mirror symmetric, one centred on the nape
          where the per-half count is odd), relaxed on GNM's neck, then one PLAIN strip (the bands' poles stay off the
          ring) to the NECK RING: K 48 points at equal angles about the neck's axis on the mid-neck plane (the section
          ANSUR's neck circumference is taken on, the plane GNM's head was conditioned on), so the ring is planar by
          construction; it is the HEAD | BODY seam, shared with the body
  PLUGS   regular blocks of GNM's quads (no two touching) re-placed as PORTS: the block's boundary loop on a planar ring
          at equal angles (vertex 0 on the port frame's tangent), its interior by a Coons patch, the two rings of
          vertices round it relaxed on the surface: the scalp ports (3 pairs, 4 x 4, K 16), the horns (mid on the
          midline, left and right on the frontal eminences, 4 x 4, K 16), the gills (3 a side in a row behind the jaw
          angle, 4 x 2 vertical slits, K 12). The GILLS are recorded where they lie (asis, H2b): GNM's own 4 x 2 blocks,
          nothing moved, their loop's plane, radius and planarity read off the skin (as the body's back ports are,
          human_hmcage.port_records). Re-placed on round planar rings they printed the lumpy patch behind both ears
          that H1 and H2 carried: a slit block pulled into a circle held ~0.2 mm off the curved neck creased its outline
          (the clay's normal 6-11 deg off GNM's at p95, 24 at p99, 40 at the worst; the scalp and horn ports 1.5-2.0 at
          p95, as GNM's own glabella: h2b/scratch/p04_gills.py)
  EARS    the auricle's attachment loop (GNM's ears group border) is the ear's root ring, K as GNM draws it
Everything else is GNM's, vertex for vertex.

    topology(log) -> HeadTopo (shared by both sexes: the same quads, the same blocks, the same bands)
    place(topo, g, log) -> targets (n, 3) on the identity g, the records (rings, plugs, regions)
"""
import numpy as np

from . import human_ref as HR
from . import human_topo as HT

VERSION = 'h3-head-gnm-5'       # -5: the ear ring's LOW feathered by distance (no fold at the lobe; the EAR RING note)
                                # -2: the gills recorded where they lie (asis); -3: head_rules (the reference
                                # symmetrised, lid_rule: plan §3.3's lid margins on their lid spheres), caruncle_ids;
                                # -4 (H3, opt-in): topology(ear_ring=True) the K 44 ear root ring (the EAR RING note at
                                # the module's end), place(rules=('commissure',)) the mouth corners (commissure_rule)
HEAD = dict(
    cut_clear=12.0,                 # mm: the cut loop's lowest point over the mid-neck plane, on every baseline identity
    bands=(78, 48),                 # the rings under the cut loop: 110 -> 78 -> the K 48 neck ring
    band_t=0.35,                    # the 78-ring's height: this fraction of the way from the cut loop down to the ring
    plain_t=0.45,                   # the plain strip's upper ring (48): this fraction of the 78-ring's height
    K_neck=48,
    plug_radius=0.9,                # a port ring's radius over its block boundary's mean distance from the block's centre
    relax_ring=2,                   # the rings of vertices round a port relaxed on the surface
)
# the ports: where (offsets in mm from GNM landmarks, on the left; the right mirrored), the block (a x b quads, its first
# axis along the direction named), kind and K = 2 (a + b)
PLUGS = (
    dict(name='scalp_0', kind='scalp', at=('v', (26.0, 6.0, 44.0)), block=(4, 4), axis='z'),
    dict(name='scalp_1', kind='scalp', at=('v', (30.0, 0.0, 2.0)), block=(4, 4), axis='z'),
    dict(name='scalp_2', kind='scalp', at=('v', (28.0, -10.0, -40.0)), block=(4, 4), axis='z'),
    dict(name='horn_mid', kind='horn', at=('g', (0.0, 34.0, -2.0)), block=(4, 4), axis='y', mid=True),
    dict(name='horn_L', kind='horn', at=('g', (34.0, 40.0, -10.0)), block=(4, 4), axis='y'),
    # the gills: three vertical slits (4 x 2: 4 quads up the neck) in a row going back from behind the jaw angle,
    # ~16 mm apart and ~50 mm over the neck ring (above the bands); stacked 12 mm apart as 2 x 4 blocks, their round
    # rings overlapped under the earlobe and creased the clay (H1's first head views); asis: recorded where they lie
    # (the module's PLUGS note)
    dict(name='gill_0', kind='gill', at=('go_L', (-2.0, -8.0, -12.0)), block=(4, 2), axis='y', asis=True),
    dict(name='gill_1', kind='gill', at=('go_L', (-5.0, -5.0, -28.0)), block=(4, 2), axis='y', asis=True),
    dict(name='gill_2', kind='gill', at=('go_L', (-8.0, -2.0, -44.0)), block=(4, 2), axis='y', asis=True),
)


class HeadTopo:
    pass


def _gnm_neck_loops(T, g):
    """GNM's closed loops round the neck (front midline -> ...), each as an ordered vertex list"""
    V = g.V
    mid = np.nonzero(g.mirror == np.arange(len(g.mirror)))[0]
    o, n = HR.neck_plane(g.joints)
    loops, seen = [], set()
    used = set(np.unique(T.Q).tolist())
    for v in mid:
        if v not in used or V[v, 2] < o[2] + 10.0 or abs((V[v] - o) @ n) > 90.0:
            continue
        for w in T.nbr[v]:
            d = V[w] - V[v]
            if abs(d[0]) < 0.3 * np.linalg.norm(d):
                continue
            L = T.loop_from(v, w)
            if L is None or len(L) != 110:
                continue
            k = frozenset(L)
            if k in seen:
                continue
            seen.add(k)
            loops.append(L)
    return loops


def topology(log=print, ear_ring=False):
    """the head cage's topology on GNM's template (identity-free): the kept GNM quads, the bands, the plug blocks;
    ear_ring (H3): the ears' root strips re-meshed round a clean K 44 graft ring (_ear_ring_edit)"""
    g0 = HR.GNMRef()
    co = np.load(HR.os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', 'gnm_conditioned.npz'))
    gs = [HR.GNMRef(co['F']), HR.GNMRef(co['M'])]
    T = HT.Topo(g0.Q, len(g0.V))
    # ---- the cut loop: the lowest 110-loop whose every vertex clears both sexes' mid-neck planes by cut_clear
    loops = _gnm_neck_loops(T, g0)
    best = None
    for L in loops:
        clear = min(float(((gg.V[L] - HR.neck_plane(gg.joints)[0]) @ HR.neck_plane(gg.joints)[1]).min()) for gg in gs)
        if clear >= HEAD['cut_clear'] and (best is None or clear < best[0]):
            best = (clear, L)
    assert best is not None, 'no GNM neck loop clears the mid-neck planes'
    clear, L = best
    # front midline first, then the loop's direction so the head's quads run it forward
    mid = g0.mirror == np.arange(len(g0.mirror))
    fr = max((i for i, v in enumerate(L) if mid[v]), key=lambda i: g0.V[L[i], 2])
    L = L[fr:] + L[:fr]
    top_v = int(np.argmax(g0.V[:, 1]))
    seed = T.vq[top_v][0]
    keep = T.side_of(L, seed)
    a, b = L[0], L[1]
    qk = [qi for qi in T.quads_with(a, b) if keep[qi]][0]
    q = T.Q[qk].tolist()
    ia = q.index(a)
    if q[(ia + 1) % 4] != b:                      # the head's quad runs b -> a: reverse the loop (front stays first)
        L = [L[0]] + L[1:][::-1]
    back = [i for i, v in enumerate(L) if mid[v] and i != 0]
    assert len(back) == 1, back
    back = back[0]
    log(f'[head] cut at GNM\'s neck loop of {len(L)} vertices, clearing the mid-neck planes by {clear:.1f} mm; '
        f'{int(keep.sum())} GNM quads kept')
    # ---- re-index: the kept GNM vertices first (sorted), then the new ones
    Qk = T.Q[keep]
    gv = np.unique(Qk)
    g2c = -np.ones(len(g0.V), np.int64)
    g2c[gv] = np.arange(len(gv))
    n = len(gv)
    new_mirror = {}

    def new_id():
        nonlocal n
        n += 1
        return n - 1
    Qc = [tuple(g2c[x] for x in q) for q in Qk.tolist()]
    O = [int(g2c[v]) for v in L]
    ring_ids, hangs, apexes = [O], [], []
    forb = ()
    front, bk = 0, back
    for nb in HEAD['bands']:
        cs = HT.unit_centres(len(O), nb, front, bk, forbidden=forb)
        B = HT.band(O, nb, cs, new_id)
        Qc += B['quads']
        # the band's inner loop starts under the outer position B['hang'][0]; rotate it to start under the front
        hang = B['hang']
        inner = B['inner']
        j0 = hang.index(front) if front in hang else int(np.argmin([(h - front) % len(O) for h in hang]))
        inner = inner[j0:] + inner[:j0]
        hang = hang[j0:] + hang[:j0]
        bj = [k for k, h in enumerate(hang) if h == bk]
        assert bj, 'the band\'s inner loop has no vertex under the back midline'
        hangs.append((hang, B['mids']))
        apexes.append([inner.index(B['inner'][ai]) for ai in B['apex_inner']])
        forb = apexes[-1]
        O = inner
        front, bk = 0, bj[0]
        ring_ids.append(O)
    # a PLAIN strip under the last band: the band's inner apexes (valence 3) sit on its inner loop, so without it the
    # neck ring carried 37 poles and its collar 57 (H1's first gates)
    plain = [new_id() for _ in range(len(O))]
    for k in range(len(O)):
        k1 = (k + 1) % len(O)
        Qc.append((O[k1], O[k], plain[k], plain[k1]))
    ring_ids.append(plain)
    neck_ring = plain
    assert len(neck_ring) == HEAD['K_neck']
    log(f'[head] neck bands: {" -> ".join(str(len(r)) for r in ring_ids)} (the last the neck ring)')
    # ---- the mirror map: GNM's for kept vertices; the bands' by position along their loops
    mir = -np.ones(n, np.int64)
    gm = g0.mirror
    mir[:len(gv)] = g2c[gm[gv]]
    assert (mir[:len(gv)] >= 0).all(), 'the kept GNM set is not mirror closed'
    TH = HeadTopo()
    TH.Q = np.array(Qc, np.int64)
    TH.n = n
    TH.gv = gv
    TH.g2c = g2c
    TH.rings = ring_ids
    TH.hangs = hangs
    TH.neck_ring = neck_ring
    TH.cut = L
    TH.mir = mir
    # the bands' mirror: ring r's vertex k <-> its position mirrored about front (0) and back
    for r in ring_ids[1:]:
        nr = len(r)
        for k, v in enumerate(r):
            mir[v] = r[(-k) % nr]
    # the units' middle vertices: paired by their outer centres (mirror positions about the front, index 0)
    for bi, (hang, mids) in enumerate(hangs):
        no = len(ring_ids[bi])
        pos = {c: m for (m, c, _) in mids}
        for c, m in pos.items():
            mir[m] = pos.get((-c) % no, m)
    assert (mir >= 0).all(), 'unpaired vertices in the mirror map'
    assert (mir[mir] == np.arange(n)).all(), 'the mirror map is not an involution'
    TH.mid = np.nonzero(mir == np.arange(n))[0]
    # ---- the plug blocks (topology only: chosen on the template, the same GNM vertices on every identity)
    TT = HT.Topo(TH.Q, n)
    Lm = HR.gnm_landmarks()
    TH.plugs = {}
    used = set()
    for p in PLUGS:
        lm, off = p['at']
        want = g0.V[Lm[lm]] + np.array(off, np.float64)
        G = _find_block(TT, g0, TH, want, p, 'L', used)
        # the block, its one-ring and their mirrors are taken: no later port may touch them
        blk = set(G.ravel().tolist())
        for v in list(blk):
            blk |= TT.nbr[v]
        used |= blk | set(TH.mir[list(blk)].tolist())
        if p.get('mid'):
            names = {'M': (p['name'], G)}
        else:
            base = p['name'][:-2] if p['name'].endswith('_L') else p['name']
            # the right block: the left block's exact mirror (its columns reversed, so its loop winds the same way
            # seen from outside)
            names = {'L': (base + '_L', G), 'R': (base + '_R', TH.mir[G][:, ::-1])}
        for side, (name, GG) in names.items():
            loop, inner = HT.grid_loop(GG)
            TH.plugs[name] = dict(kind=p['kind'], grid=GG, loop=loop, inner=inner, K=len(loop),
                                  mid=bool(p.get('mid')), side=side, spec=p)
    log(f'[head] ports: {", ".join(f"{k} K {v["K"]}" for k, v in TH.plugs.items())}')
    # ---- the ear root rings: the ears group's border in the kept cage
    TH.ear_root = {}
    ears = g0.grp['ears']
    for side, sgn in (('L', 1.0), ('R', -1.0)):
        inner = np.zeros(n, bool)
        sel = ears[gv] & (np.sign(g0.V[gv, 0]) == sgn)
        inner[:len(gv)] = sel
        qin = inner[TH.Q].all(1)
        edges = []
        for (a_, b_), lst in TT.emap.items():
            if len(lst) == 2 and qin[lst[0]] != qin[lst[1]]:
                edges.append((a_, b_))
        loop = HR.chain(edges)
        TH.ear_root[side] = loop
    log(f'[head] ear root rings: K {len(TH.ear_root["L"])} (left), {len(TH.ear_root["R"])} (right)')
    TH.topo = TT
    TH.quads_gnm = int(keep.sum())
    TH.V_tpl = np.full((TH.n, 3), np.nan)                 # the template's positions (GNM's mean head) of the kept vertices
    TH.V_tpl[:len(gv)] = g0.V[gv]
    TH.ear = None
    if ear_ring:
        _ear_ring_edit(TH, g0, log)
    return TH


def _find_block(TT, g0, TH, want, p, side, used=frozenset()):
    """the regular block nearest `want` on the template: the kept vertex nearest it with a regular a x b block whose
    first axis is the grid direction nearest the named world axis; clear of poles one ring round it, and of `used` (the
    earlier ports' blocks and collars)"""
    a, b = p['block']
    V = np.zeros((TH.n, 3))
    V[:len(TH.gv)] = g0.V[TH.gv]
    ax = dict(x=np.array([1.0, 0, 0]), y=np.array([0, 1.0, 0]), z=np.array([0, 0, 1.0]))[p['axis']]
    cand = np.argsort(np.linalg.norm(V[:len(TH.gv)] - want, axis=1))[:60]
    mid = set(TH.mid.tolist())
    for c in cand.tolist():
        if p.get('mid') and c not in mid:
            continue
        if not p.get('mid') and c in mid:
            continue
        nb = sorted(TT.nbr[c], key=lambda w: -abs((V[w] - V[c]) @ ax) / max(np.linalg.norm(V[w] - V[c]), 1e-9))
        for w in nb[:2]:
            G = TT.block(c, w, a, b)
            if G is None or (set(G.ravel().tolist()) & set(used)):
                continue
            # a one-ring margin of regular vertices round the block (the port's collar)
            ring = set()
            for v in G.ravel().tolist():
                ring |= TT.nbr[v]
            ring -= set(G.ravel().tolist())
            if any(TT.val[v] != 4 for v in ring):
                continue
            if p.get('mid'):
                # the block must be its own mirror
                if set(TH.mir[G.ravel()].tolist()) != set(G.ravel().tolist()):
                    continue
            return G
    raise RuntimeError(f'no regular {a} x {b} block near {np.round(want, 1)} for {p["name"]} ({side})')


def outward_sign(g, ids=None):
    """+1 if GNM's vertex normals (its winding) point out of the head, else -1: the sign that turns them away from the
    skin's centroid on average"""
    ids = np.arange(len(g.V)) if ids is None else ids
    vn = g.tm.normals()
    d = np.einsum('ij,ij->i', g.V[ids] - g.V[ids].mean(0), vn[ids])
    return 1.0 if float(np.mean(d)) > 0 else -1.0


def _ray_hits(g, O, D):
    t, f, bb = g.tm.ray(O, D)
    ok = t > 0
    P = O + np.where(ok, t, 0.0)[:, None] * D
    return P, f, bb, ok


def plane_ring(g, c, n0, t0, K, radius, closest=None, planar_tol=0.015, ray=None):
    """a PLANAR port ring of K points round the surface point c (outward normal n0), vertex 0 on the port frame's
    tangent t0, at equal parametric angles: a circle of `radius` in the tangent plane projected onto the surface
    (closest points), then flattened toward those points' least-squares plane only as far as the planarity bar needs
    (each point's distance off the plane scaled so the largest is planar_tol of the mean radius: the gate's 0.02 r_bar
    with a margin), each point at its own angle and in-plane radius. A closed planar curve cannot lie on a cylinder (the
    neck's side) or a saddle, so the ring leaves the skin by the rest of the sag, about r^2 / 4R less the tolerance (a
    full flattening left the back's 38 mm ports 2 mm off the skin and printed craters: H1's first figure); the cage
    holds the ring and the skin round it follows. Returns the points (K, 3), the plane origin, the frame and the ring's
    largest distance off the surface"""
    closest = g.closest if closest is None else closest
    t0 = t0 - (t0 @ n0) * n0
    t0 = t0 / np.linalg.norm(t0)
    t1 = np.cross(n0, t0)
    ang = np.linspace(0.0, 2 * np.pi, K, endpoint=False)
    C = c[None, :] + radius * (np.cos(ang)[:, None] * t0[None, :] + np.sin(ang)[:, None] * t1[None, :])
    S = closest(C)[0]
    o = S.mean(0)
    U, s, Vt = np.linalg.svd(S - o)
    nrm = Vt[2] if Vt[2] @ n0 > 0 else -Vt[2]
    u0 = t0 - (t0 @ nrm) * nrm
    u0 /= np.linalg.norm(u0)
    u1 = np.cross(nrm, u0)
    rho = np.linalg.norm((S - o) - np.outer((S - o) @ nrm, nrm), axis=1)
    dev = (S - o) @ nrm
    if planar_tol is None and ray is not None:
        # ON the skin at exact equal angles: each point the skin's hit along -n from over its circle point (a closest
        # point slides sideways on a saddle: 13.9 mm off over the sacral cleft)
        Cn = o[None, :] + rho.mean() * (np.cos(ang)[:, None] * u0[None, :] + np.sin(ang)[:, None] * u1[None, :])
        H = 3.0 * float(rho.mean())
        t_, _, _ = ray(Cn + H * nrm[None, :], np.repeat(-nrm[None, :], K, 0))
        ok = t_ > 0
        P = np.where(ok[:, None], Cn + (H - np.where(ok, t_, H))[:, None] * nrm[None, :], S)
        devp = (P - o) @ nrm
        return P, o, dict(normal=nrm, t0=u0, t1=u1, origin=o, radius=float(rho.mean()),
                          off_skin=float(np.linalg.norm(closest(P)[0] - P, axis=1).max()),
                          planarity=float((devp.max() - devp.min()) / 2.0 / rho.mean()))
    scale = 1.0 if planar_tol is None else min(1.0, planar_tol * float(rho.mean()) / max(float(np.abs(dev).max()),
                                                                                        1e-12))
    P = o[None, :] + rho[:, None] * (np.cos(ang)[:, None] * u0[None, :] + np.sin(ang)[:, None] * u1[None, :]) + \
        (scale * dev)[:, None] * nrm[None, :]
    off = float(np.linalg.norm(closest(P)[0] - P, axis=1).max())
    return P, o, dict(normal=nrm, t0=u0, t1=u1, origin=o, radius=float(rho.mean()), off_skin=off,
                      planarity=float(np.abs(scale * dev).max() / rho.mean()))


def place(TH, g, log=print, sex='', rules=()):
    """the head cage's TARGETS on the identity g: GNM's own vertices, the bands and the neck ring by rays about the neck's
    axis, the ports re-placed; symmetrised. Returns dict(P (n, 3), records). H3: with TH's ear edit (topology
    ear_ring=True) the edit's vertices are placed on the skin (_ear_place) and P_low is returned beside P: the targets
    of the shipped LOW, whose ear rings lie in their planes (ear_low); P stays on the skin (the HIGH's targets).
    rules: 'commissure' (commissure_rule: the mouth corners' free targets toward GNM's template layout)"""
    n = TH.n
    P = np.full((n, 3), np.nan)
    P[:len(TH.gv)] = g.V[TH.gv]
    o_n, n_n = HR.neck_plane(g.joints)
    e1, e2, _ = HR.plane_basis(n_n, np.array([0.0, 0.0, 1.0]))      # e1 ~ +z (front), e2 = n x e1 (the left)
    # the axis' angle and height of every cut-loop vertex
    L = TH.rings[0]
    X = P[L]
    h_cut = (X - o_n) @ n_n
    th_cut = np.arctan2((X - o_n) @ e2, (X - o_n) @ e1)

    def hit(theta, h):
        O_ = o_n[None, :] + h[:, None] * n_n[None, :]
        D_ = np.cos(theta)[:, None] * e1[None, :] + np.sin(theta)[:, None] * e2[None, :]
        Pp, f, bb, ok = _ray_hits(g, O_, D_)
        assert ok.all(), 'a neck ray missed GNM'
        return Pp
    # unwrap the cut loop's angles (front 0, the left half positive)
    thu = np.unwrap(th_cut)
    # ring 1 (78) and the units' middle vertices: angles subsampled from the cut loop, heights band_t of the way down
    (hang1, mids1), (hang2, mids2) = TH.hangs
    r1 = TH.rings[1]
    th1 = thu[hang1]
    h1 = h_cut[hang1] * (1.0 - HEAD['band_t'])
    # smooth ring 1's angles toward even spacing between its neighbours (the subsampling leaves steps at the units)
    K = HEAD['K_neck']
    # equal angles from the front midline, turning the way the cut loop turns (the ring's vertices follow its order)
    sgn = 1.0 if thu[len(thu) // 4] - thu[0] > 0 else -1.0
    th_ring = sgn * np.linspace(0.0, 2 * np.pi, K, endpoint=False)
    # ring 1 interpolates between the cut loop's angle at its outer vertex and the ring's (its own share of the way)
    P[r1] = hit(th1, h1)
    P[TH.neck_ring] = hit(th_ring, np.zeros(K))
    for (m, c, ai) in mids1:
        P[m] = hit(np.array([thu[c]]), np.array([h_cut[c] * (1.0 - 0.5 * HEAD['band_t'])]))[0]
    th1u = np.unwrap(np.arctan2((P[r1] - o_n) @ e2, (P[r1] - o_n) @ e1))
    h1v = (P[r1] - o_n) @ n_n
    # the plain strip's upper ring (the last band's inner loop): the neck ring's angles, at plain_t of ring 1's height
    rA = TH.rings[2]
    o1_ = np.argsort(th1u)
    h_at = lambda th: np.interp(th, th1u[o1_], h1v[o1_], period=2 * np.pi)       # noqa: E731
    P[rA] = hit(th_ring, HEAD['plain_t'] * h_at(th_ring))
    hAv = (P[rA] - o_n) @ n_n
    for (m, c, ai) in mids2:
        P[m] = hit(np.array([th1u[c]]), np.array([0.5 * (h1v[c] + HEAD['plain_t'] * h_at(th1u[c]))]))[0]
    # the bands' free vertices (the 78-ring and the units' middles) relaxed on GNM's neck between the cut loop and the
    # neck ring (both held): the rays at subsampled angles left an uneven net under the jaw, and the clay was lumpy there
    TT = TH.topo
    bfree = np.array(sorted(set(r1) | set(m for (m, _, _) in mids1) | set(m for (m, _, _) in mids2)), np.int64)
    nb_list = [np.array(sorted(TT.nbr[v]), np.int64) for v in bfree]
    for _ in range(40):
        avg = np.array([P[nb].mean(0) for nb in nb_list])
        P[bfree] = g.closest(P[bfree] + 0.5 * (avg - P[bfree]))[0]
    # ---- the ports: re-placed on planar rings
    recs = {}
    moved = np.zeros(n, bool)
    s_out = outward_sign(g, TH.gv)
    for name, pl in TH.plugs.items():
        G = pl['grid']
        a, b = G.shape[0] - 1, G.shape[1] - 1
        loop = pl['loop']
        cen = P[G.ravel()].mean(0)
        _, f0, b0 = g.closest(cen[None, :])
        c = g.bary_to_3d(f0, b0)[0]
        n0 = s_out * g.normal_at(f0, b0)[0]
        # the frame's tangent: along the block's first axis (rows)
        t0 = P[G[-1, b // 2]] - P[G[0, b // 2]]
        if pl['spec'].get('asis'):
            # recorded where it lies (GNM's own vertices; the PLUGS note): the loop's best plane, mean radius and
            # planarity (half the spread off that plane over the mean radius, as plane_ring reports it)
            Pl = P[loop]
            oc = Pl.mean(0)
            nrm = np.linalg.svd(Pl - oc)[2][2]
            nrm = nrm if nrm @ n0 > 0 else -nrm
            rho = np.linalg.norm((Pl - oc) - np.outer((Pl - oc) @ nrm, nrm), axis=1)
            dev = (Pl - oc) @ nrm
            tt = t0 - (t0 @ nrm) * nrm
            recs[name] = dict(kind=pl['kind'], K=len(loop), loop=loop, inner=pl['inner'], centre=c.tolist(),
                              normal=nrm.tolist(), t0=(tt / np.linalg.norm(tt)).tolist(), radius=float(rho.mean()),
                              off_skin=0.0, mid=pl['mid'], side=pl['side'], asis=True,
                              planarity=float((dev.max() - dev.min()) / 2.0 / rho.mean()))
            continue
        r0 = float(np.mean(np.linalg.norm(P[loop] - c, axis=1))) * HEAD['plug_radius']
        Rp, orig, frame = plane_ring(g, c, n0, t0, len(loop), r0)
        cur = P[loop]
        # wind the ring like the block's loop, then rotate it to the nearest assignment
        def sarea(Z):
            Z2 = np.column_stack([(Z - c) @ frame['t0'], (Z - c) @ frame['t1']])
            return 0.5 * np.sum(Z2[:, 0] * np.roll(Z2[:, 1], -1) - np.roll(Z2[:, 0], -1) * Z2[:, 1])
        if np.sign(sarea(Rp)) != np.sign(sarea(cur)):
            Rp = Rp[::-1]
            idx = list(range(len(loop)))[::-1]
        else:
            idx = list(range(len(loop)))
        best = None
        for sh in range(len(loop)):
            cand = np.roll(Rp, -sh, axis=0)
            cost = float(np.linalg.norm(cand - cur, axis=1).sum())
            if best is None or cost < best[0]:
                best = (cost, cand, sh)
        Rp = best[1]
        P[loop] = Rp
        # the interior: a Coons patch over the new boundary, projected onto the surface
        GG = np.zeros((a + 1, b + 1, 3))
        for i in range(a + 1):
            for j in range(b + 1):
                GG[i, j] = P[G[i, j]]
        for i in range(1, a):
            for j in range(1, b):
                u, w = i / a, j / b
                X_ = ((1 - w) * GG[i, 0] + w * GG[i, b] + (1 - u) * GG[0, j] + u * GG[a, j]
                      - ((1 - u) * (1 - w) * GG[0, 0] + u * (1 - w) * GG[a, 0] + (1 - u) * w * GG[0, b] +
                         u * w * GG[a, b]))
                P[G[i, j]] = g.closest(X_[None, :])[0][0]
        moved[G.ravel()] = True
        recs[name] = dict(kind=pl['kind'], K=len(loop), loop=loop, inner=pl['inner'], centre=c.tolist(),
                          normal=frame['normal'].tolist(), t0=frame['t0'].tolist(), radius=frame['radius'],
                          off_skin=frame['off_skin'], mid=pl['mid'], side=pl['side'])
    # relax the vertices round each port (HEAD['relax_ring'] rings) on the surface: the block's boundary moved
    TT = TH.topo
    held = moved.copy()
    held[TH.neck_ring] = True
    near = set()
    for name, pl in TH.plugs.items():
        if pl['spec'].get('asis'):
            continue                                  # nothing moved: GNM's own vertices round it stay
        fr_ = set(pl['grid'].ravel().tolist())
        cur = set(fr_)
        for _ in range(HEAD['relax_ring']):
            nx = set()
            for v in cur:
                nx |= TT.nbr[v]
            cur |= nx
        near |= (cur - fr_)
    near = np.array(sorted(v for v in near if not held[v]), np.int64)
    for _ in range(30):
        avg = np.array([P[list(TT.nbr[v])].mean(0) for v in near])
        Xn = P[near] + 0.5 * (avg - P[near])
        P[near] = g.closest(Xn)[0]
    # ---- (H3) the ear edit's vertices on the skin, the root band relaxed on GNM
    if getattr(TH, 'ear', None):
        P = _ear_place(TH, g, P, log=log, sex=sex)
    # ---- symmetrise (the baseline is symmetric; GNM's components carry a little asymmetry)
    mir = TH.mir
    M = np.array([-1.0, 1.0, 1.0])
    P = 0.5 * (P + P[mir] * M)
    P[TH.mid, 0] = 0.0
    assert not np.isnan(P).any(), 'a head vertex has no target'
    if 'commissure' in rules:
        P = commissure_rule(TH, g, P, log=log, sex=sex)
    # ---- the neck ring's record
    Rn = P[TH.neck_ring]
    cc = Rn.mean(0)
    dev = np.abs((Rn - cc) @ n_n)
    recs['neck'] = dict(kind='head_region', K=len(TH.neck_ring), loop=list(TH.neck_ring), centre=cc.tolist(),
                        normal=n_n.tolist(), planar_mm=float(dev.max()))
    for side in ('L', 'R'):
        recs[f'ear_{side}'] = dict(kind='ear', K=len(TH.ear_root[side]), loop=list(TH.ear_root[side]))
    P_low = P
    if getattr(TH, 'ear', None):
        keep = [r['loop'] for nm, r in recs.items() if isinstance(r, dict) and r.get('loop') is not None
                and r.get('kind') in ('scalp', 'horn', 'gill', 'head_region')]
        P_low, ear_recs = ear_low(TH, P, log=log, sex=sex, keep=keep)
        recs.update(ear_recs)
    log(f'[head] {sex} placed: neck ring {len(TH.neck_ring)} round, planar to {dev.max():.3f} mm, circumference '
        f'{HR.hull_perimeter(np.column_stack([(Rn - cc) @ e1, (Rn - cc) @ e2])):.1f} mm (the tape)')
    return dict(P=P, P_low=P_low, recs=recs, plane=(o_n, n_n))


def caruncle_ids(rings=5, medial=0.5, height=2.2):
    """the CARUNCLE's region on GNM's topology (H2b; the plan's "the caruncle at en", §2.3): medial of the lid margin's
    end at the globe (H0's en, vertex 555) GNM's skin folds into a recess whose tip is the commissure (gnm_landmarks
    en_c, 633): the rings 1-5 of exterior vertices outside the margin step medially round it (h2b/scratch/p11_wedge.py).
    Those rings' vertices medial of en (by `medial` mm) within `height` mm of its height, on GNM's template: GNM vertex
    ids, left (the right by GNM's mirror). A RECORD for the material and the bake (the caruncle's wet pink); its form
    is GNM's"""
    d = HR.gnm_data()
    V0 = d['T']
    fz = np.load(HR.os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h0', 'probe1', 'gnm_features.npz'))
    T = HT.Topo(d['Q'], len(V0))
    ext = d['grp']['skin_exterior'] & ~d['grp']['eye_sockets']
    en = HR.gnm_landmarks()['en_L']
    dist = np.full(len(V0), -1)
    cur = [int(v) for v in fz['margin_v']]
    for v in cur:
        dist[v] = 0
    for k in range(1, rings + 1):
        nx = []
        for v in cur:
            for w in T.nbr[v]:
                if dist[w] < 0 and ext[w]:
                    dist[w] = k
                    nx.append(w)
        cur = nx
    enc = HR.gnm_landmarks()['en_c_L']
    sel = (dist >= 1) & (V0[:, 0] < V0[en, 0] + medial) & (V0[:, 0] > V0[enc, 0] - medial) & \
        (np.abs(V0[:, 1] - V0[en, 1]) < height)
    return np.nonzero(sel)[0]


def head_rules(g, log=print, sex=''):
    """the conditioned GNM head as the baseline cage carries it, IN PLACE (H2b): SYMMETRISED (the baseline is symmetric:
    place() symmetrises the targets, so the regional gates read the cage against the same symmetric surface instead of
    GNM's own asymmetry: the man's conditioned face is 1.66 mm asymmetric at p95 over the hockey mask, and the
    symmetric clay read 0.72 mm off it there), then the lid rule (lid_rule). Returns lid_rule's record"""
    M = np.array([-1.0, 1.0, 1.0])
    V = 0.5 * (g.V + g.V[g.mirror] * M)
    V[g.mirror == np.arange(len(V)), 0] = 0.0
    g.V = V
    g._tm = None
    return lid_rule(g, log=log, sex=sex)


LID_RULE = dict(globe=24.156, lid=1.0, feather=(0.55, 0.25, 0.08))


def lid_rule(g, log=print, sex=''):
    """plan §3.3's eye rule on GNM's surface, IN PLACE (H2b; the H2 gate: "the lid margin on the lid sphere within 0.2
    mm"): each eye's lid margin loop (H0's margin_v, mirrored for the right) moved radially onto the lid sphere, the
    24.2 mm globe (Bekerman 2014) plus the lid's 1 mm, centred where it fits the margin best (human_ref.fit_globe); the
    rings of GNM's vertices beside the margin (both sides: the lid skin and the conjunctival sac) take LID_RULE's
    feather of the move of the margin vertex they are nearest by graph. H1's clay held the margin as GNM drew it: rms
    0.20 / 0.26, max 0.48 / 0.54 mm off its sphere. The regional gates read the head WITH this edit (plan §9.1).
    Returns the record (per eye: centre, the move's max, the residual after)"""
    fz = np.load(HR.os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h0', 'probe1', 'gnm_features.npz'))
    d = HR.gnm_data()
    T = HT.Topo(d['Q'], len(g.V))
    rec = {}
    D = np.zeros_like(g.V)
    sides = (('L', np.asarray(fz['margin_v'], np.int64)), ('R', g.mirror[np.asarray(fz['margin_v'], np.int64)]))
    for side, mv in sides:
        c, rr = HR.fit_globe(g.V[mv], LID_RULE['globe'], LID_RULE['lid'])
        R = LID_RULE['globe'] / 2.0 + LID_RULE['lid']
        P = g.V[mv]
        Dm = c + (P - c) * (R / np.linalg.norm(P - c, axis=1))[:, None] - P
        D[mv] = Dm
        # the feather: BFS rings from the margin, each vertex taking its nearest margin vertex's move
        src = {int(v): i for i, v in enumerate(mv)}
        cur = list(src)
        seen = set(cur)
        for w_ in LID_RULE['feather']:
            nx = {}
            for v in cur:
                for u in T.nbr[v]:
                    if u not in seen and u not in nx:
                        nx[u] = src[v]
            for u, i in nx.items():
                D[u] = w_ * Dm[i]
                src[u] = i
            seen |= set(nx)
            cur = list(nx)
        rec[side] = dict(centre=c.tolist(), rms_before=float(np.sqrt((rr ** 2).mean())),
                         max_before=float(np.abs(rr).max()), move_max=float(np.linalg.norm(Dm, axis=1).max()))
    g.V = g.V + D
    g._tm = None
    for side, mv in sides:
        _, rr = HR.fit_globe(g.V[mv], LID_RULE['globe'], LID_RULE['lid'])
        rec[side]['max_after'] = float(np.abs(rr).max())
    log(f'[head] {sex} the lid rule: the margins onto their lid spheres (24.2 mm globe + 1 mm): max off '
        f'{rec["L"]["max_before"]:.2f} / {rec["R"]["max_before"]:.2f} -> {rec["L"]["max_after"]:.3f} / '
        f'{rec["R"]["max_after"]:.3f} mm (moves up to {max(rec["L"]["move_max"], rec["R"]["move_max"]):.2f} mm, '
        f'feathered over {len(LID_RULE["feather"])} rings)')
    return rec


def feature_masks(TH, g0=None):
    """per cage vertex: its GNM region labels (for the held features and the gates): the lid margins, the vermilion,
    the nostril rims, the ear root; GNM's groups carried onto the kept vertices"""
    g0 = HR.GNMRef() if g0 is None else g0
    grp = {k: np.zeros(TH.n, bool) for k in g0.grp}
    for k, m in g0.grp.items():
        grp[k][:len(TH.gv)] = m[TH.gv]
    return grp


# ============================================================================================ H3: the local surface
def closest_on_tris(P, A, B, C):
    """per point its closest point on triangles (Ericson's regions), float64: P (n, 3) against A, B, C (m, 3) or
    (n, k, 3) (each point its own k). Returns the points (n, m|k, 3) and their distances"""
    P = np.asarray(P, np.float64)[:, None, :]
    ab, ac, ap = B - A, C - A, P - A
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = P - B
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = P - C
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    den = va + vb + vc
    den = np.where(np.abs(den) < 1e-30, 1e-30, den)
    R = A + (vb / den)[..., None] * ab + (vc / den)[..., None] * ac
    zero = 0.0 * P
    sd = lambda a, b: a / np.where(np.abs(b) < 1e-30, 1e-30, b)               # noqa: E731
    R = np.where(((vc <= 0) & (d1 >= 0) & (d3 <= 0))[..., None], A + sd(d1, d1 - d3)[..., None] * ab, R)
    R = np.where(((vb <= 0) & (d2 >= 0) & (d6 <= 0))[..., None], A + sd(d2, d2 - d6)[..., None] * ac, R)
    R = np.where(((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0))[..., None],
                 B + sd(d4 - d3, (d4 - d3) + (d5 - d6))[..., None] * (C - B), R)
    R = np.where(((d1 <= 0) & (d2 <= 0))[..., None], A + zero, R)
    R = np.where(((d3 >= 0) & (d4 <= d3))[..., None], B + zero, R)
    R = np.where(((d6 >= 0) & (d5 <= d6))[..., None], C + zero, R)
    return R, np.linalg.norm(R - P, axis=-1)


class LocalSurface:
    """an identity's GNM triangles within `radius` of a centre, for exact float64 closest points (Warp's float32 BVH at
    head height cannot resolve a 0.01 mm finite-difference step) that never snap across a fold: with a normal hint a
    candidate triangle must face within acos(dot) of it (the auricle's back against the head in the groove behind the
    ear; the two lips at the mouth's corner)"""

    def __init__(self, V, F, centre, radius, knn=24):
        from scipy.spatial import cKDTree
        V = np.asarray(V, np.float64)
        F = np.asarray(F, np.int64)
        tc = V[F].mean(1)
        sel = np.nonzero(np.linalg.norm(tc - np.asarray(centre), axis=1) < radius)[0]
        self.A, self.B, self.C = V[F[sel, 0]], V[F[sel, 1]], V[F[sel, 2]]
        n = np.cross(self.B - self.A, self.C - self.A)
        self.N = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
        self.tree = cKDTree(tc[sel])
        self.knn = min(knn, len(sel))

    def project(self, X, hint=None, dot=0.3):
        """(closest points (n, 3), their triangles' unit normals (n, 3)); hint: per point a unit normal the triangle
        must agree with (dot), else the nearest is taken"""
        X = np.asarray(X, np.float64)
        _, idx = self.tree.query(X, k=self.knn)
        R, d = closest_on_tris(X, self.A[idx], self.B[idx], self.C[idx])
        if hint is not None:
            ok = (self.N[idx] * np.asarray(hint)[:, None, :]).sum(-1) > dot
            d = np.where(ok | ~ok.any(1, keepdims=True), d, np.inf)
        j = np.argmin(d, axis=1)
        ar = np.arange(len(X))
        return R[ar, j], self.N[idx][ar, j]


# ============================================================================================ H3: THE EAR RING
# THE EAR RING (the lead's H3 call 1: "the EAR RING to K = 0 mod 4 with a frame record like the other rings (centre,
# normal, t0), planar within the ring bar: a local loop edit in GNM's ear topology; it is a graft ring, because ear swaps
# are a remix"). GNM's root ring (its 'ears' group border) is K 42 with two valence-5 poles on it and five in its collar,
# planarity 0.166 F / 0.125 M (3.7 / 3.0 mm off its plane). No straight edge loop at the root closes with K = 0 mod 4
# (the only K 40 runs up on the antihelix), and the root is not planar on the skin: no plane's section of the clay
# encircles the auricle near it (the best plane's section wanders 7 mm median, 16 mm max from the root: the groove
# behind the auricle is deep, the notch at the lobe's front dips), and flatten_ring reaches planarity on the skin only
# by sliding vertices 10-30 mm (h3/forge_notes/probes p01-p05).
# THE EDIT (topology, both sexes, every identity): the strip of quads between the root L0 and the next loop out L1
# (42 / 42) re-meshed as L0 <-band- A -plain- R -plain- B -band-> L1: the house's 4 -> 2 units (human_topo.band), one
# per band, each placed where the old loop's own irregular vertices take its poles (the unit's middle inner vertex on a
# vertex that keeps two edges away from the strip, its ends where possible on one that keeps none: L1's corner); R, the
# ring, K 44, every vertex valence 4; its collar carries the two units' outer apexes (valence 3), the neck ring's 37 for
# comparison. The vertex 0 of the ring is the one nearest 'up' in the ring's plane on GNM's template.
# THE PLACE (each identity, _ear_place): A, R, B start at a quarter, half and three quarters of the way from L0 to L1
# along the angle about the root's axis, then L0, A, R, B, L1 relax on GNM between L-1 and L2 (held): all on the skin,
# the clay unchanged. THE LOW (ear_low): R projected onto its best plane, lid_rule's feather (0.55, 0.25, 0.08) over the
# rings beside it, so the shipped low's ring is planar by construction and its frame is recorded; the HIGH keeps the
# skin targets (the build fits both), so the bake carries GNM's own ear root in the normal map and the clay Skye called
# "good head and ears" is the high.
# THE FEATHER BY DISTANCE (h3-head-gnm-5, the forge builder's successor, 10-30): the feather over graph rings folded the
# LOW at the lobe. There the rows L1 .. Lm2 bunch along the lobe's lower edge about 0.5 mm apart, R's move swings from
# 3.85 mm in to 2.97 mm out along the lobe's arc (F; M 3.15 / 1.18; the arc is where R leaves its least-squares plane
# most: 3.91 mm against 2.13 elsewhere), and a move decaying over three rings 0.5 mm apart is a slope over 1: row B's
# lowest quads turned 92-125 deg from the clay (forge probes p29-p32: a bright hem along the lobe's rim in every look).
# Now every head vertex within feather_mm of the ring moves along the ring's normal by the ring's move at the nearest
# point of R's polyline (linear along its edges, so exact at R) times a Wendland falloff of its distance to it, so the
# slope stays under 1 and the LOW cannot fold; the move fades to 0 within keep_mm of every other port's loop (the gills
# sit 8.9-12 mm from the ear ring on the skin and are recorded there). R itself is still projected exactly. No plane
# fixes the lobe (weighting its arc x30 leaves 2.0 mm there and puts 5.5 mm behind the ear: probe p32).
EAR = dict(K=44, frac=(0.25, 0.5, 0.75), region=55.0, feather=(0.55, 0.25, 0.08), phi_smooth=0.08,
           unit_rings=3, unit_floor=30.0, unit_slide=0.05, unit_nfev=400,
           feather_mm=15.0, keep_mm=(2.5, 8.0))


def _boundary_loop(TT, inside_q):
    """the one closed loop of edges between the quads in inside_q and those out of it"""
    edges = [e for e, lst in TT.emap.items() if len(lst) == 2 and inside_q[lst[0]] != inside_q[lst[1]]]
    loops = HR.chain(edges, multi=True)
    assert len(loops) == 1 and len(loops[0]) == len(edges), \
        f'not one closed loop ({len(loops)} chains over {len(edges)} edges)'
    return [int(v) for v in loops[0]]


def _ear_ring_edit(TH, g0, log=print):
    """the K 44 ear root ring (the EAR RING note): TH's quads, vertex count, mirror map, topology and ear_root changed in
    place; TH.ear = {side: the loops (L-1, L0, A, R, B, L1, L2), the units, the ring in record order}"""
    import collections
    TT = TH.topo
    Q = TH.Q
    n0 = TH.n
    gv = TH.gv
    Vt = TH.V_tpl
    ears = g0.grp['ears']
    inner = np.zeros(n0, bool)
    inner[:len(gv)] = ears[gv] & (g0.V[gv, 0] > 0)              # the left ear (+x)
    qin = inner[Q].all(1)
    L0 = _boundary_loop(TT, qin)
    s0 = set(L0)
    S = np.array([(not qin[qi]) and any(v in s0 for v in Q[qi]) for qi in range(len(Q))])
    L1 = _boundary_loop(TT, qin | S)
    s1 = set(L1)
    assert set(Q[S].ravel().tolist()) <= (s0 | s1), 'the root strip has vertices off its two loops'
    Sm = np.array([qin[qi] and any(v in s0 for v in Q[qi]) for qi in range(len(Q))])
    Lm1 = _boundary_loop(TT, qin & ~Sm)
    S2 = np.array([(not qin[qi]) and (not S[qi]) and any(v in s1 for v in Q[qi]) for qi in range(len(Q))])
    L2 = _boundary_loop(TT, qin | S | S2)
    # (the annulus the edit's vertices are placed in: two loops further each way, held)
    sm1, s2_ = set(Lm1), set(L2)
    Sm2 = np.array([qin[qi] and not Sm[qi] and any(v in sm1 for v in Q[qi]) for qi in range(len(Q))])
    Lm2 = _boundary_loop(TT, qin & ~Sm & ~Sm2)
    S3 = np.array([(not qin[qi]) and not (S[qi] or S2[qi]) and any(v in s2_ for v in Q[qi]) for qi in range(len(Q))])
    L3 = _boundary_loop(TT, qin | S | S2 | S3)
    old_quads = Q[Sm2 | Sm | S | S2 | S3].copy()
    # the root strip's RUNGS (its edges from L0 to L1): the correspondence the new rows are lofted along
    rungs = sorted({(int(q[k]), int(q[(k + 1) % 4])) if int(q[k]) in s0 else (int(q[(k + 1) % 4]), int(q[k]))
                    for q in Q[S] for k in range(4)
                    if (int(q[k]) in s0) != (int(q[(k + 1) % 4]) in s0)})
    # counter-clockwise about the root's outward normal, on the template
    c = Vt[L0].mean(0)
    nrm = np.linalg.svd(Vt[L0] - c)[2][2]
    nrm = nrm if nrm[0] > 0 else -nrm
    e1 = np.cross(nrm, [0.0, 0.0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(nrm, e1)

    def ccw(L):
        X = Vt[L] - c
        u, w = X @ e1, X @ e2
        if 0.5 * np.sum(u * np.roll(w, -1) - np.roll(u, -1) * w) > 0:
            return list(L)
        return [L[0]] + list(L[1:])[::-1]
    L0, L1, Lm1, L2, Lm2, L3 = ccw(L0), ccw(L1), ccw(Lm1), ccw(L2), ccw(Lm2), ccw(L3)
    # each loop vertex's edges away from the strip once it goes
    nb = collections.defaultdict(set)
    for qi in np.nonzero(~S)[0]:
        q = Q[qi]
        for k in range(4):
            nb[int(q[k])].add(int(q[(k + 1) % 4]))
            nb[int(q[k])].add(int(q[(k - 1) % 4]))
    away = {v: len(nb[v]) - 2 for v in L0 + L1}

    def triple(L, name, key_of):
        """the unit's inner (i0, i1, i2) on loop L: i1 (no band edge) where L keeps two edges away (-> valence 4), the
        best by key_of(j) among those; L rotated to start at i0"""
        n = len(L)
        cands = [j for j in range(n) if away[L[j]] == 2]
        if not cands:
            log(f'[head] ear ring: {name} keeps no vertex with two edges away from the strip; the unit\'s middle sits '
                f'on a valence-3 pole')
            cands = list(range(n))
        j = min(cands, key=key_of)
        return L[j - 1:] + L[:j - 1] if j >= 1 else L[-1:] + L[:-1]
    # WHERE THE UNITS GO: both at one place (each unit shifts its row by two positions, so units apart offset the rows by
    # two spacings between them and sheared the thin strips to ~10 deg: h3 gates, the first build, the head's angle p1
    # 33 -> 12; units three positions apart sheared 24 quads under 25 deg: p15), at L1's corner, where the unit's ends
    # cancel L1's own valences, and L0's cancelling vertex nearest it. A 4 -> 2 unit wants its band about an edge long
    # and the root strip is only 2.5-3.7 mm wide there (h3 probes p16): _ear_units_relax opens the units' quads after
    # the loft
    def ends0(j):
        n = len(L1)
        return -(int(away[L1[j - 1]] == 0) + int(away[L1[(j + 1) % n]] == 0))
    L1r = triple(L1, 'L1', key_of=ends0)
    L0r = triple(L0, 'L0', key_of=lambda j: float(np.linalg.norm(Vt[L0[j]] - Vt[L1r[1]])))
    K = EAR['K']
    assert K - 2 == len(L0) == len(L1), (K, len(L0), len(L1))
    nid = [n0]

    def new():
        nid[0] += 1
        return nid[0] - 1
    A = [new() for _ in range(K)]
    R = [new() for _ in range(K)]
    B = [new() for _ in range(K)]
    bA = HT.band(A, len(L0), [2], new, inner_ids=L0r)
    # B's indices aligned with A's (the plain strips join A[k], R[k], B[k]): B's band starts where A's row passes L1r[0]
    # on the template (the bands built from index 0 each put the units at different angles and twisted the strips)
    sp_ = _strip_params(L0, L1, rungs, Vt)
    tA = _row_params(K, L0r, bA['hang'], sp_['p0'])
    hang0 = HT.band_pattern(K, [2])                          # B's band from index 0: the hang positions it will use
    best = None
    for dl in range(K):                                      # B's rotation: the least misalignment of its row with A's
        tB_ = _row_params(K, L1r, [(dl + h) % K for h in hang0], sp_['p1'], inv=sp_['phi_inv'])
        mis = float(np.abs(((tB_ - tA) + 0.5) % 1.0 - 0.5).sum())
        if best is None or mis < best[0]:
            best = (mis, dl)
    dlt = best[1]
    bB = HT.band(B[dlt:] + B[:dlt], len(L1), [2], new, inner_ids=L1r)
    hangB = [(dlt + h) % K for h in bB['hang']]
    quadsL = list(bA['quads']) + list(bB['quads'])
    for k in range(K):
        k1 = (k + 1) % K
        quadsL.append((A[k], A[k1], R[k1], R[k]))
        quadsL.append((R[k], R[k1], B[k1], B[k]))
    left_new = list(range(n0, nid[0]))
    off = len(left_new)
    mir0 = TH.mir

    def mapR(v):
        return v + off if v >= n0 else int(mir0[v])
    quadsR = [tuple(mapR(v) for v in q[::-1]) for q in quadsL]
    # the right ear's strip: the left strip's mirror quads
    qkey = {frozenset(int(v) for v in q): qi for qi, q in enumerate(Q.tolist())}
    SR = [qkey[frozenset(int(mir0[v]) for v in Q[qi])] for qi in np.nonzero(S)[0]]
    kill = S.copy()
    kill[SR] = True
    Qn = np.vstack([Q[~kill], np.array(quadsL, np.int64), np.array(quadsR, np.int64)])
    n1 = n0 + 2 * off
    mir = np.concatenate([mir0, np.zeros(2 * off, np.int64)])
    for v in left_new:
        mir[v] = v + off
        mir[v + off] = v
    TH.Q = Qn
    TH.n = n1
    TH.mir = mir
    TH.topo = HT.Topo(Qn, n1)
    TH.V_tpl = np.vstack([Vt, np.full((2 * off, 3), np.nan)])
    TH.ear = {}
    for side, f in (('L', lambda v: v), ('R', mapR)):
        TH.ear[side] = dict(Lm2=[f(v) for v in Lm2], Lm1=[f(v) for v in Lm1], L0=[f(v) for v in L0],
                            A=[f(v) for v in A], R=[f(v) for v in R], B=[f(v) for v in B], L1=[f(v) for v in L1],
                            L2=[f(v) for v in L2], L3=[f(v) for v in L3],
                            L0r=[f(v) for v in L0r], L1r=[f(v) for v in L1r], hangA=list(bA['hang']),
                            hangB=list(hangB), mA=f(bA['mids'][0][0]), mB=f(bB['mids'][0][0]),
                            apex=[f(A[2]), f(B[(dlt + 2) % K])], rungs=[(f(a_), f(b_)) for a_, b_ in rungs],
                            old_quads=np.array([[f(int(v)) for v in q] for q in old_quads], np.int64))
    # the ring's vertex 0: nearest 'up' in its plane on the template (placed there by the identity-free _ear_place)
    P0 = _ear_place(TH, g0, TH.V_tpl.copy(), log=lambda *a: None, sex='template')
    for side in ('L', 'R'):
        e = TH.ear[side]
        X = P0[e['R']]
        cc = X.mean(0)
        nn = np.linalg.svd(X - cc)[2][2]
        up = np.array([0.0, 1.0, 0.0]) - (np.array([0.0, 1.0, 0.0]) @ nn) * nn
        k0 = int(np.argmax((X - cc) @ up))
        e['ring'] = e['R'][k0:] + e['R'][:k0]
        TH.ear_root[side] = e['ring']
    TH.V_tpl = P0
    val = TH.topo.val
    eL = TH.ear['L']
    pol = lambda ids: sum(1 for v in ids if val[v] != 4)                     # noqa: E731
    assert pol(eL['R']) == 0, 'the ear ring carries a pole'
    log(f'[head] ear ring edit: the root strips ({int(S.sum())} quads a side) re-meshed L0 {len(L0)} <- A {K} - R {K} - '
        f'B {K} -> L1 {len(L1)}: {off} vertices and {len(quadsL)} quads a side; poles on R {pol(eL["R"])}, A '
        f'{pol(eL["A"])}, B {pol(eL["B"])}, L0 {pol(eL["L0"])} (was {sum(1 for v in L0 if TT.val[v] != 4)}), L1 '
        f'{pol(eL["L1"])} (was {sum(1 for v in L1 if TT.val[v] != 4)})')


def _strip_params(L0, L1, rungs, P):
    """the root strip's loft parameters on positions P: each loop's arc-length parameter (t0 on L0, t1 on L1, from its
    vertex 0, rising), the rungs' monotone map phi: t0 -> t1 and its inverse, and on_loop(t, tt, X) evaluating a closed
    polyline at parameters"""
    def params(L):
        X = P[L]
        seg = np.linalg.norm(np.roll(X, -1, axis=0) - X, axis=1)
        return np.concatenate([[0.0], np.cumsum(seg)[:-1]]) / seg.sum(), X
    t0, X0 = params(L0)
    t1, X1 = params(L1)
    p0 = {v: t0[i] for i, v in enumerate(L0)}
    p1 = {v: t1[i] for i, v in enumerate(L1)}
    pr = sorted((p0[a_], p1[b_]) for a_, b_ in rungs)
    a_t = np.array([x for x, _ in pr])
    b_t = np.unwrap(np.array([y for _, y in pr]) * 2 * np.pi) / (2 * np.pi)
    assert np.all(np.diff(b_t) >= -1e-9), 'the root strip\'s rungs do not run in order'
    # the rungs' map has a JUMP where an old corner quad holds three L1 vertices over one of L0 and a FLAT where one
    # holds three of L0 under one of L1; rows lofted through them tore (2-deg quads beside the units): the map sampled
    # finely and its offset from the identity smoothed by a circular moving average over EAR['phi_smooth'] of the loop
    # (a moving average of a monotone map stays monotone)
    a_ext0 = np.concatenate([a_t - 1.0, a_t, a_t + 1.0])
    b_ext0 = np.concatenate([b_t - 1.0, b_t, b_t + 1.0])
    ns = 2048
    ts = np.arange(ns) / ns
    off = np.interp(ts, a_ext0, b_ext0) - ts
    w = max(1, int(round(EAR['phi_smooth'] * ns)))
    ker = np.ones(w) / w
    off_s = np.convolve(np.concatenate([off[-w:], off, off[:w]]), ker, mode='same')[w:w + ns]
    a_t, b_t = ts, ts + off_s
    a_ext = np.concatenate([a_t - 1.0, a_t, a_t + 1.0])
    b_ext = np.concatenate([b_t - 1.0, b_t, b_t + 1.0])

    def phi(t):
        return np.interp(np.asarray(t) % 1.0, a_ext, b_ext)

    def phi_inv(t):
        base = np.floor(b_t[0])
        return np.interp((np.asarray(t) - base) % 1.0 + base, b_ext, a_ext) % 1.0

    def on_loop(t, tt, X):
        te = np.concatenate([tt, [1.0]])
        Xe = np.vstack([X, X[:1]])
        t = np.asarray(t) % 1.0
        return np.column_stack([np.interp(t, te, Xe[:, k]) for k in range(3)])
    return dict(t0=t0, X0=X0, t1=t1, X1=X1, p0=p0, p1=p1, phi=phi, phi_inv=phi_inv, on_loop=on_loop)


def _row_params(K, inner, hang, pmap, inv=None):
    """a new loop's K parameters (on L0's scale): under each of its band's inner vertices that vertex's parameter (inv
    maps it onto L0's scale), the rest (the unit's outer middles) between their neighbours"""
    tt = np.full(K, np.nan)
    for j, h in enumerate(hang):
        tt[h % K] = pmap[inner[j]] if inv is None else inv(pmap[inner[j]])
    idx = np.nonzero(~np.isnan(tt))[0]
    un = np.unwrap(tt[idx] * 2 * np.pi) / (2 * np.pi)
    return np.interp(np.arange(K), np.concatenate([idx - K, idx, idx + K]),
                     np.concatenate([un - 1.0, un, un + 1.0])) % 1.0


def _ear_place(TH, g, P, log=print, sex=''):
    """the ear edit's vertices on the identity g (the EAR RING note's PLACE), the left ear solved and the right mirrored;
    P (n, 3) with GNM's kept vertices set: changed in place and returned.
    GNM's own loops stay where GNM puts them (L0, L1 and beyond: the identity map stays exactly GNM's there); the three
    new rows are LOFTED inside the old root strip: each L0 vertex at its arc-length parameter t0, each L1 vertex at its
    t1, the strip's rungs (its old L0 -> L1 edges) a monotone correspondence t0 -> t1; the row at fraction s across the
    strip is (1 - s) L0(t) + s L1(phi(t)), pulled onto GNM (a normal hint from the strip's own face, so a point in the
    groove behind the auricle never snaps onto the auricle's back). Rows at different fractions cannot cross (an
    umbrella relax projected in 3D bunched and crossed them at the front of the root, the crease along the tragus and
    the helix's crus; a Tutte map in the strip's LSCM flattening overlapped where the annulus folds: h3 probes p15).
    Each new loop's vertices sit at the parameters of the old loop vertices its band hangs them from (A under L0, B
    under L1), the units' outer middles between their neighbours, R midway between A and B"""
    TT = TH.topo
    M = np.array([-1.0, 1.0, 1.0])
    e = TH.ear['L']
    sp_ = _strip_params(e['L0'], e['L1'], e['rungs'], P)
    t0, X0, t1, X1, phi, on_loop = sp_['t0'], sp_['X0'], sp_['t1'], sp_['X1'], sp_['phi'], sp_['on_loop']
    tA0 = _row_params(len(e['A']), e['L0r'], e['hangA'], sp_['p0'])
    tB0 = _row_params(len(e['B']), e['L1r'], e['hangB'], sp_['p1'], inv=sp_['phi_inv'])
    # the rows' remaining misalignment (A's band wants A over L0's vertices, B's band B over L1's, the plain strips A,
    # R and B in line) shared evenly by the four strips L0-A, A-R, R-B, B-L1
    dAB = ((tB0 - tA0) + 0.5) % 1.0 - 0.5
    tA, tR, tB = (tA0 + 0.25 * dAB) % 1.0, (tA0 + 0.5 * dAB) % 1.0, (tA0 + 0.75 * dAB) % 1.0
    surf = LocalSurface(g.V, g.F, X0.mean(0), EAR['region'] + 20.0)
    s_out = outward_sign(g, TH.gv)                          # GNM's winding: +1 if its face normals point out
    for ids, tt, s in ((e['A'], tA, EAR['frac'][0]), (e['R'], tR, EAR['frac'][1]), (e['B'], tB, EAR['frac'][2])):
        Pa = on_loop(tt, t0, X0)
        Pb = on_loop(phi(tt), t1, X1)
        # the strip's own face at each point (along the loop x across the strip), turned outward (the left ear's root
        # strip faces +x all round: the cheek, the temple, the mastoid, under the lobe) and into GNM's winding
        Pa2 = on_loop(tt + 0.01, t0, X0)
        nh = np.cross(Pa2 - Pa, Pb - Pa)
        nh /= np.maximum(np.linalg.norm(nh, axis=1, keepdims=True), 1e-30)
        nh *= (np.sign(nh[:, 0]) * s_out)[:, None]
        P[ids] = surf.project((1.0 - s) * Pa + s * Pb, nh)[0]
    for m in (e['mA'], e['mB']):
        nbm = sorted(TT.nbr[m])
        _, hn = surf.project(P[nbm])
        P[m] = surf.project(P[nbm].mean(0, keepdims=True), hn.mean(0, keepdims=True))[0][0]
    P = _ear_units_relax(TH, P, surf, s_out, log=log, sex=sex)
    # the right ear: the mirror of every vertex the left's placement set (the relax moves GNM's L0 / L1 too; mirroring
    # only the new rows let place()'s symmetrise average half the relax away)
    left = np.array(sorted(set(e['L0'] + e['A'] + e['R'] + e['B'] + e['L1'] + [e['mA'], e['mB']])), np.int64)
    P[TH.mir[left]] = P[left] * M
    return P


def _ear_units_relax(TH, P, surf, s_out, log=print, sex=''):
    """the bands' 4 -> 2 units opened (the left ear; P changed in place and returned): the edit's vertices within
    EAR['unit_rings'] of either unit (the rows L0, A, R, B, L1 and the units' middles; GNM's loops beyond stay) slide on
    GNM, fitted by least squares so no corner of a quad touching them stays under EAR['unit_floor'] (each slide weighted
    EAR['unit_slide'] per mm): the band widens locally where the root strip is narrow (the commissure rule's method:
    float64 tangent offsets, LocalSurface's projection with each vertex's own normal as the hint).
    KNOWN (h3_build's fold gate, 10-30): the corner angles are unsigned, so a quad turned over with every corner over
    the floor costs nothing; 3 of the units' quads a side (0.35-0.5 mm2, the ear's front root) end 123-163 deg from the
    clay. An orientation residual against the skin's normal at each quad's centre was tried and dropped: these quads
    span the root's groove, the nearest skin point of a centre often lies on the far wall, and the term dragged the
    band 9-15 mm (the fold gate rose to 50-58 quads)"""
    from scipy.optimize import least_squares
    TT = TH.topo
    Q = TH.Q
    e = TH.ear['L']
    edit = set(e['L0'] + e['A'] + e['R'] + e['B'] + e['L1'] + [e['mA'], e['mB']])
    seed = {e['mA'], e['mB']} | set(TT.nbr[e['mA']]) | set(TT.nbr[e['mB']])
    cur = set(seed)
    for _ in range(EAR['unit_rings']):
        nx = set()
        for v in cur:
            nx |= TT.nbr[v]
        cur |= nx
    free = np.array(sorted(v for v in cur if v in edit), np.int64)
    quads = np.array(sorted({q for v in free for q in TT.vq[int(v)]}), np.int64)
    A0 = quad_angles(P[Q[quads]])
    _, N0 = surf.project(P[free])
    t1 = np.cross(N0, [0.0, 1.0, 0.0])
    t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
    t2 = np.cross(N0, t1)
    base = P[free].copy()

    def moved(x):
        Pn = P.copy()
        Pn[free] = surf.project(base + x[0::2, None] * t1 + x[1::2, None] * t2, N0)[0]
        return Pn

    def resid(x):
        A = quad_angles(moved(x)[Q[quads]])
        return np.concatenate([np.clip(EAR['unit_floor'] - A, 0, None).ravel(), EAR['unit_slide'] * x])
    sol = least_squares(resid, np.zeros(2 * len(free)), diff_step=0.01, max_nfev=EAR['unit_nfev'])
    Pn = moved(sol.x)
    A1 = quad_angles(Pn[Q[quads]])
    TH.ear_units_rec = dict(free=len(free), quads=len(quads), min_before=float(A0.min()), min_after=float(A1.min()),
                            under25_before=int((A0.min(1) < 25).sum()), under25_after=int((A1.min(1) < 25).sum()),
                            slide_max=float(np.nanmax(np.linalg.norm(Pn[free] - P[free], axis=1))))
    r = TH.ear_units_rec
    log(f'[head] {sex} the ear bands\' units opened: {r["free"]} vertices over {r["quads"]} quads; min angle '
        f'{r["min_before"]:.1f} -> {r["min_after"]:.1f} deg, quads under 25 deg {r["under25_before"]} -> '
        f'{r["under25_after"]}; slid up to {r["slide_max"]:.2f} mm on GNM')
    return Pn


def ear_low(TH, P, log=print, sex='', keep=()):
    """the shipped LOW's targets (the EAR RING note's LOW): each ring projected onto its best plane, the move feathered
    over the vertices round it by distance (THE FEATHER BY DISTANCE; feather_mm None: lid_rule's feather over graph
    rings, as h3-head-gnm-4), fading to 0 within keep_mm of the loops in keep (the other ports' vertex ids); the frame
    records. Returns (P_low, records)"""
    TT = TH.topo
    P_low = P.copy()
    recs = {}
    keep_ids = np.unique(np.concatenate([np.asarray(k, np.int64) for k in keep])) if len(keep) else np.zeros(0, int)
    for side, sgn in (('L', 1.0), ('R', -1.0)):
        e = TH.ear[side]
        ring = e['ring']
        X = P[ring]
        c = X.mean(0)
        nrm = np.linalg.svd(X - c)[2][2]
        nrm = nrm if nrm[0] * sgn > 0 else -nrm
        dev = (X - c) @ nrm
        rho = np.linalg.norm((X - c) - np.outer(dev, nrm), axis=1)
        D = -np.outer(dev, nrm)
        Dall = np.zeros_like(P)
        if EAR.get('feather_mm'):
            R_ = float(EAR['feather_mm'])
            k0, k1 = EAR['keep_mm']
            dk = np.linalg.norm(P[:, None, :] - X[None, :, :], axis=2)            # (n, K): to each ring vertex
            near = np.nonzero(dk.min(1) < R_)[0]
            # the ring's move at the NEAREST POINT of its closed polyline, linear along each edge: exact at R, so the
            # rows bunched beside it (0.5 mm at the lobe) move with it. (A Gaussian average of R's moves, the first
            # try, missed R's own by 0.65 mm next to the lobe arc's peak: a slope of 1.22 and 6 folded quads.)
            Xb = np.roll(X, -1, axis=0)
            AB = Xb - X
            Pn = P[near]
            t = np.clip(((Pn[:, None, :] - X[None]) * AB[None]).sum(2) / (AB * AB).sum(1)[None], 0.0, 1.0)
            dseg = np.linalg.norm(Pn[:, None, :] - (X[None] + t[..., None] * AB[None]), axis=2)
            kk = dseg.argmin(1)
            tt = t[np.arange(len(near)), kk]
            mv = -((1.0 - tt) * dev[kk] + tt * np.roll(dev, -1)[kk])           # along nrm
            r = np.minimum(dseg[np.arange(len(near)), kk] / R_, 1.0)
            w = (1.0 - r) ** 4 * (4.0 * r + 1.0)                                # Wendland C2: 1 at the ring, 0 at R_
            if len(keep_ids):
                dkeep = np.linalg.norm(P[near][:, None, :] - P[keep_ids][None, :, :], axis=2).min(1)
                s = np.clip((dkeep - k0) / (k1 - k0), 0.0, 1.0)
                w = w * s * s * (3.0 - 2.0 * s)
                dring_keep = float(np.linalg.norm(X[:, None, :] - P[keep_ids][None, :, :], axis=2).min())
                assert dring_keep >= k1, f'a kept port loop {dring_keep:.1f} mm from the ear ring (keep {k1} mm)'
            Dall[near] = (w * mv)[:, None] * nrm[None, :]
            Dall[ring] = D
            # the slope of the move along the LOW's edges round it (bar < 1: then the LOW cannot fold)
            Ed = np.array([(a, b) for a in near for b in TT.nbr[a] if b > a], np.int64)
            sl = np.linalg.norm(Dall[Ed[:, 0]] - Dall[Ed[:, 1]], axis=1) / np.maximum(
                np.linalg.norm(P[Ed[:, 0]] - P[Ed[:, 1]], axis=1), 1e-9)
            fe = dict(moved=int((np.linalg.norm(Dall, axis=1) > 1e-6).sum()), slope_max=float(sl.max()),
                      slope_p99=float(np.percentile(sl, 99)))
        else:
            Dall[ring] = D
            src = {v: i for i, v in enumerate(ring)}
            cur, seen = list(ring), set(ring)
            for w in EAR['feather']:
                nx = {}
                for v in cur:
                    for u in TT.nbr[v]:
                        if u not in seen and u not in nx:
                            nx[u] = src[v]
                for u, i in nx.items():
                    Dall[u] = w * D[i]
                    src[u] = i
                seen |= set(nx)
                cur = list(nx)
            fe = dict(moved=int((np.linalg.norm(Dall, axis=1) > 1e-6).sum()))
        P_low = P_low + Dall
        Xl = P_low[ring]
        cl = Xl.mean(0)
        t0 = (Xl[0] - cl) - ((Xl[0] - cl) @ nrm) * nrm
        t0 /= np.linalg.norm(t0)
        recs[f'ear_{side}'] = dict(kind='ear', K=len(ring), loop=[int(v) for v in ring], centre=cl.tolist(),
                                   normal=nrm.tolist(), t0=t0.tolist(), radius=float(rho.mean()), side=side,
                                   planarity_skin=float((dev.max() - dev.min()) / 2.0 / rho.mean()),
                                   off_plane_max_skin=float(np.abs(dev).max()), low_flat=True,
                                   collar_poles=[int(v) for v in e['apex']], feather=fe)
    rl = recs['ear_L']
    how = (f'feathered by distance ({EAR["feather_mm"]:.0f} mm, Wendland; {rl["feather"]["moved"]} vertices moved, the '
           f'slope along the LOW\'s edges max {rl["feather"]["slope_max"]:.2f} / p99 {rl["feather"]["slope_p99"]:.2f}, '
           f'bar < 1; clear of {len(keep)} port loops by {EAR["keep_mm"][0]:.0f} mm)'
           if EAR.get('feather_mm') else f'feathered over {len(EAR["feather"])} rings')
    log(f'[head] {sex} the ear rings K {rl["K"]}: on the skin {rl["off_plane_max_skin"]:.2f} mm off their planes at most '
        f'(planarity {rl["planarity_skin"]:.3f}, r {rl["radius"]:.1f} mm); the LOW\'s rings in their planes, {how}')
    return P_low, recs


# ============================================================================================ H3: THE MOUTH CORNERS
# THE MOUTH CORNERS (the lead's H3 call 2: "the woman's mouth-corner quads, which thinned to a 7 deg corner in H2b (the
# man's to 21 deg), relaxed back toward H2's 31-37 deg with the clay unchanged by eye"). H2b's eye holds moved GNM's
# conditioned face so the commissure's quads compressed (H2 30.7 -> H2b 6.2 deg F at the corner sliver, 25-33 -> 15-23
# round it). Umbrella relaxing makes it worse (the neighbours' centroid lies on the crushed line: h3 probes p07). So the
# FREE targets within `rings` of each corner's two sliver quads (GNM's vertices: the held lips stay) slide on GNM, fitted
# by least squares toward the corner angles of GNM's own TEMPLATE layout (its artists': the sliver 35.4 deg there),
# every corner pushed up to its quad's template minimum (capped at `floor`), each slide weighted (w_slide per mm); in
# float64 on a local projector that never snaps across the lip (LocalSurface), the left corner solved and the right
# mirrored (p11: F 6.2 -> ~28 deg, M 18.6 -> ~30, slides under 1 mm, on GNM)
COMMISSURE = dict(seed_gnm=(4573, 5155, 5154, 4554, 4555, 4572), rings=3, floor=30.0, w_match=0.05, w_floor=1.0,
                  w_slide=0.1, region=14.0, max_nfev=600)


def quad_angles(P4):
    """the corner angles (deg) of quads given as (..., 4, 3) corner positions"""
    a = np.roll(P4, 1, axis=-2) - P4
    b = np.roll(P4, -1, axis=-2) - P4
    c = (a * b).sum(-1) / (np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1) + 1e-30)
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def commissure_rule(TH, g, P, log=print, sex=''):
    """the mouth corners (the MOUTH CORNERS note) on the targets P (symmetric): returns P with the corners' free targets
    moved; TH.commissure_rec holds the angles before / after"""
    from scipy.optimize import least_squares
    cfg = COMMISSURE
    TT = TH.topo
    Q = TH.Q
    M = np.array([-1.0, 1.0, 1.0])
    fz = np.load(HR.os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h0', 'probe1', 'gnm_features.npz'))
    held = np.zeros(TH.n, bool)
    for key in ('margin_v', 'vermilion_v', 'inner_lip_v'):
        ids = TH.g2c[fz[key]]
        ids = ids[ids >= 0]
        held[ids] = True
        held[TH.mir[ids]] = True
    cur = set(int(TH.g2c[v]) for v in cfg['seed_gnm'])
    seed_q = {q for v in cur for q in TT.vq[v] if all(int(x) in cur for x in Q[q])}
    for _ in range(cfg['rings']):
        nx = set()
        for v in cur:
            nx |= TT.nbr[v]
        cur |= nx
    free = np.array(sorted(v for v in cur if not held[v]), np.int64)
    quads = np.array(sorted({q for v in free for q in TT.vq[int(v)]}), np.int64)
    Aref = quad_angles(TH.V_tpl[Q[quads]])
    assert not np.isnan(Aref).any(), 'a corner quad has no template position'
    A0 = quad_angles(P[Q[quads]])
    surf = LocalSurface(g.V, g.F, P[free].mean(0), cfg['region'])
    _, N0 = surf.project(P[free])
    t1 = np.cross(N0, [0.0, 1.0, 0.0])
    t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
    t2 = np.cross(N0, t1)
    base = P[free].copy()
    floor = np.minimum(cfg['floor'], Aref.min(1, keepdims=True))

    def moved(x):
        Pn = P.copy()
        Pn[free] = surf.project(base + x[0::2, None] * t1 + x[1::2, None] * t2, N0)[0]
        return Pn

    def resid(x):
        A = quad_angles(moved(x)[Q[quads]])
        return np.concatenate([cfg['w_match'] * (A - Aref).ravel(), cfg['w_floor'] * np.clip(floor - A, 0, None).ravel(),
                               cfg['w_slide'] * x])
    sol = least_squares(resid, np.zeros(2 * len(free)), diff_step=0.01, max_nfev=cfg['max_nfev'])
    Pn = moved(sol.x)
    Pn[TH.mir[free]] = Pn[free] * M
    A1 = quad_angles(Pn[Q[quads]])
    sq = sorted(int(q) for q in seed_q)
    pos = [int(np.nonzero(quads == q)[0][0]) for q in sq]
    TH.commissure_rec = dict(seed_quads=sq, free=len(free), quads=len(quads),
                             free_ids=[int(v) for v in free] + [int(TH.mir[v]) for v in free],
                             seed_before=[float(A0[i].min()) for i in pos], seed_after=[float(A1[i].min()) for i in pos],
                             seed_template=[float(Aref[i].min()) for i in pos],
                             region_min=(float(A0.min()), float(A1.min()), float(Aref.min())),
                             region_p5=(float(np.percentile(A0.min(1), 5)), float(np.percentile(A1.min(1), 5)),
                                        float(np.percentile(Aref.min(1), 5))),
                             under25=(int((A0.min(1) < 25).sum()), int((A1.min(1) < 25).sum())),
                             slide_max=float(np.linalg.norm(Pn - P, axis=1).max()))
    r = TH.commissure_rec
    log(f'[head] {sex} the mouth corners: {r["free"]} free targets a side over {r["quads"]} quads toward GNM\'s template; '
        f'the slivers {np.round(r["seed_before"], 1).tolist()} -> {np.round(r["seed_after"], 1).tolist()} deg (template '
        f'{np.round(r["seed_template"], 1).tolist()}); the corner\'s min {r["region_min"][0]:.1f} -> '
        f'{r["region_min"][1]:.1f}, p5 {r["region_p5"][0]:.1f} -> {r["region_p5"][1]:.1f}; quads under 25 deg '
        f'{r["under25"][0]} -> {r["under25"][1]}; slid up to {r["slide_max"]:.2f} mm on GNM')
    return Pn
