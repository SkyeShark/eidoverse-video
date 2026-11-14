"""HUMAN H2: the BODY CAGE on MakeHuman's own artist mesh (hm08 / MPFB2 core assets, CC0), below the head's K 48 neck
ring (HUMAN_PLAN §2.4, §6.2; the lead's H2 brief: "build the body's cage the way the head's works, from an artist's
topology ... Route the graft rings ... and the ports into it with local loop edits, keeping poles off the deformation
zones"; the body study, research/game_study/HUMAN_BODY_STUDY.md §5).

WHY hm08's own mesh: the head reads well because its cage IS GNM's artist topology, fitted to GNM's own surface (nearly
the identity). H1's body was a designed box (a shoulder yoke, a 64-column trunk, a crotch bridge, K 48 tubes) whose rows
bridged the gluteal cleft, squeezed where the thighs touch and ignored the forms. hm08 is MakeHuman's subdivision-ready
base mesh: 164 3-poles and 156 5-poles placed for flow, concentric breast loops, a navel, the gluteal cleft's
converging columns, the leg root along the bikini line (the gluteal fold at the back, the inguinal crease in front),
20 spans round every limb section (the study's measures). Its targets are its own vertices on MakeHuman's phenotype at
the baseline (human_pheno), so the body's fit is nearly the identity too.

THE LOCAL EDITS (all else is hm08's, quad for quad):
  NECK    hm08 is cut at its neck loop X near the base's flare (K 42: the highest loop leaving every sex's head ring room
          for the strips); hm08's head and upper neck go. Between the head's neck ring (K 48, the HEAD | BODY seam,
          human_head) and X: plain K 48 strips (at least two, so the band's poles stay out of the ring's collar), then
          ONE reduction band 48 -> 42 onto X, its three 4 -> 2 units over the back half of the neck, 60 deg apart (the
          nape: the throat and the sternocleidomastoids stay clean; hm08 has its own neck-base poles there). Their
          targets on the ONE neck blend (NeckConform: GNM owns the neck to the ring; under it hm08's own neck,
          conformed to the ring, eases back to hm08 exactly a little under X)
  WAIST   hm08's waist loops are K 42 (2 + 2 x 20). A ring needs K = 0 mod 4, and a mirrored loop changes by 2 only with
          one unit ON a midline. So the trunk between hm08's loop P (the first K 42 loop under the breasts' structure)
          and Q (the last above the navel's) is spliced: P -> a 42 -> 44 band -> A, B, RING, D, E (K 44, horizontal
          sections of the reference, the ring in the middle with two plain strips each side) -> a 44 -> 42 band -> Q.
          Both units sit on the FRONT midline (the epigastrium, and over the navel beside hm08's own navel poles): the
          back carries the four back ports and the shell. The ring sits at the natural waist, ~60 mm over the
          omphalion: hm08's navel structure fills the omphalion's level, and the ports fit above the ring as H1 placed
          them (the plan's "at the omphalion's level" is moved; a decision for the lead). Where P dips toward the
          planar ring (the man's flanks, along the costal margin) P and the two hm08 rows over it slide up their own
          columns on the reference until the strips from the ring up come out even (space_columns; the woman's
          columns are left as they are)
  RINGS   on hm08's own K 20 loops: the armscye (the first arm loop distal of the axilla's apex), the elbow, the wrist;
          the hip (the first full leg loop under the crotch: the leg root), the knee, the ankle (the study-T-style
          mid-limb cuts are an option, H2['cut_rings'], off: see there). Each loop FLATTENED onto its least-squares
          plane (every vertex slid along its column on the reference to the plane), the loops either side relaxed on
          the reference; vertex order is hm08's (the artist's spacing; only the planarity is gated, plan §2.7)
  PORTS   regular a x b blocks of hm08's back quads (every vertex and the one-ring round the block valence 4, clear of
          the rings' collars and of each other), re-placed as H1's were (human_body.place_plugs: a planar ring at equal
          angles on the skin, the interior by a Coons patch): back_upper L / R over the scapulae's medial borders,
          back_shell on the midline between them and the waist splice, back_lower L / R on the posterior flanks at the
          iliac crest UNDER the waist ring (the ring at the natural waist leaves no room above it: a decision for the
          lead, since a lower-body graft at the waist then takes the lumbar pair with it), the sacral plug over the
          sacrum. Their K follow hm08's ~18 mm grid at H1's sizes in mm (4 x 4 = K 16; the shell 6 x 6 = K 24 where it
          fits)

    topology(log) -> BodyTopo2 (both sexes: hm08's topology; the loops found on the woman's phenotype by rules)
    place(BT, sex, V_ref, smooth, head, log) -> targets (BT.n, 3), records
"""
import collections

import numpy as np

from . import human_ref as HR
from . import human_topo as HT

VERSION = 'h2b-body-hm08-3'     # -2: the waist's crushed columns re-spaced (space_columns; the man's cage only);
                                # -3 (H2b): the nail folds (NAILS, find_nail_beds, nail_beds; h2_build --round h2b)
H2 = dict(
    neck_spacing=11.0,          # mm: the neck strips between the head's ring and X, about hm08's own neck spacing
    neck_min_plain=2,           # plain K 48 loops under the ring (the ring's collar clean of the band's apexes)
    neck_strip_min=8.0,         # mm: the shortest neck strip X may leave under a head's ring
    waist_new=5,                # A, B, RING, D, E
    ring_t=dict(upperarm=0.60, elbow=0.80, wrist=1.78, thigh=0.62, knee=0.80, ankle=1.72),
    # the study-T-style mid-limb cuts (upper arm, thigh) as rings of their own: OFF. Three loops clear of the
    # elbow and the knee rings they land at chain 0.51 (4.6 mm out of plane) and 0.52 (10.0 mm: every thigh loop
    # between the hip and the knee is 6.6-10 mm out of plane on hm08); the plan's elbow and knee rings serve the
    # stump grafts until one needs a mid-limb cut
    cut_rings=False,
    relax_rings=2,              # loops each side of a flattened ring relaxed on the reference
    relax_iters=40,
    # mm: NeckConform's zone reaches this far under X's deepest vertex (hm08's base flare and the trapezius' first
    # loop ease back to hm08 over it: the man's 17 mm gap at the back of the ring then adds at most ~0.3 to the nape's
    # slope, under hm08's own increase into the flare, so the profile bends one way) [E: H2, looked at]
    neck_conform_extra=30.0,
    # the share of the way each reduction unit's 3-pole moves off its flat corner toward its neighbour off the band
    # (ease_units): 0.3 of a ~5-10 mm edge opens the kite's ~177 deg corner toward ~150 deg [E: H2, looked at]
    unit_ease=0.3,
    # space_columns: a column over the waist splice is re-spaced when hm08's first row over P is more than
    # waist_space_ratio[0] times the splice's strip under it (fully from [1]); the man's flanks read 3.0-7.0 (a
    # crease), his back 1.9-2.2 and the woman 0.7-1.95 (clean) [E: look:h2, measured on both sexes and looked at];
    # waist_space_rows of hm08's rows over P slide with it (the next one is held); the weights are smoothed round P
    # by waist_space_smooth passes of a [1 2 1] / 4 kernel (one column's weight next to its neighbour's 0 sheared their
    # quads by up to 29 mm in the first try's numbers)
    waist_space_ratio=(2.5, 4.0),
    waist_space_rows=2,
    waist_space_smooth=2,
)
# the ports: a x b blocks (quads; the first that fits), where (x mm off the midline; y mm from a reference height:
# a landmark's, or the waist splice's loops P / Q, the woman's reference). The waist ring sits at the natural waist
# (the WAIST note above), so the lumbar pair goes under it, on the posterior flanks at the iliac crest, and the shell on
# the midline between the scapular pair and the splice's top loop P
PORTS = (
    dict(name='back_upper', kind='back_limb', blocks=((4, 4),), at=('axilla', 75.0, 40.0)),
    dict(name='back_shell', kind='back', blocks=((6, 6), (4, 4)), at=('P', 0.0, 60.0), mid=True),
    dict(name='back_lower', kind='back_limb', blocks=((4, 4),), at=('Q', 100.0, -45.0)),
    dict(name='sacral', kind='tail_base', blocks=((4, 4),), at=('crotch', 0.0, 120.0), mid=True),
)


class BodyTopo2:
    pass


# ============================================================================================ loops
def all_loops(T, maxn=400):
    """every closed edge loop of the quad mesh (vertex lists), each once"""
    seen = set()
    loops = []
    for (a, b) in list(T.emap.keys()):
        if (a, b) in seen:
            continue
        L = T.loop_from(a, b, maxn=maxn)
        if L is None:
            continue
        for x, y in zip(L, L[1:] + L[:1]):
            seen.add((min(x, y), max(x, y)))
        loops.append(L)
    return loops


def loop_info(V, L):
    P = V[L]
    c = P.mean(0)
    U, s, Vt = np.linalg.svd(P - c)
    n = Vt[2]
    planar = float(np.abs((P - c) @ n).max())
    r = float(np.linalg.norm((P - c) - np.outer((P - c) @ n, n), axis=1).mean())
    return dict(c=c, n=n, planar=planar, r=r, K=len(L))


def order_from_front(V, L, axis_up=np.array([0.0, 1.0, 0.0])):
    """a closed midline loop (round the trunk or the neck) re-ordered to start at its FRONT midline vertex (x 0, the
    larger z) and to turn toward +x first"""
    L = list(L)
    mid = [i for i, v in enumerate(L) if abs(V[v, 0]) < 1e-6]
    assert len(mid) == 2, f'a midline loop must cross the midline twice ({len(mid)})'
    i0 = max(mid, key=lambda i: V[L[i], 2])
    L = L[i0:] + L[:i0]
    if V[L[1], 0] < 0:
        L = [L[0]] + L[1:][::-1]
    return L


def order_limb_loop(V, L, front=np.array([0.0, 0.0, 1.0])):
    """a limb loop re-ordered to start at its most anterior vertex"""
    L = list(L)
    i0 = int(np.argmax(V[L] @ front))
    return L[i0:] + L[:i0]


def arc_params(P, closed=True):
    """normalised arc-length parameters of a closed polyline's vertices (0 at the first)"""
    Q = np.vstack([P, P[:1]]) if closed else P
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    return s[:-1] / s[-1] if closed else s / s[-1]


# ============================================================================================ the topology
def topology(V_rules, log=print, neck_rings=None):
    """hm08's body topology with the edits (the module's docstring). V_rules: all hm08 vertices of a reference body (mm)
    whose positions the loop rules read (the woman's solved phenotype); the same topology serves both sexes.
    neck_rings: {sex: (ring centre, ring normal, that sex's V_ref)}: X is chosen so that every sex has room under its
    head's ring for the neck strips (H2['neck_min_plain'] + 1 strips of at least H2['neck_strip_min'] mm each)"""
    d = HR.mh_data()
    nb = d['nb']
    Q0 = d['Q']
    B = HR.MHBody('F', V_rules)
    V = B.Vb
    part = B.part
    T = HT.Topo(Q0, nb)
    loops = all_loops(T)
    info = [loop_info(V, L) for L in loops]
    L_ = HR.mh_landmarks(B, log=lambda *a: None)
    lmy = {k: float(V[v, 1]) for k, v in L_.items()}
    J = B.joints
    # ---- midline loops round the neck and the trunk (they cross x 0 twice), by height of the front midline vertex
    midl = []
    for L, inf in zip(loops, info):
        xs = V[L, 0]
        if abs(inf['c'][0]) > 1.0 or (np.abs(xs) < 1e-6).sum() != 2:
            continue
        if not np.isin(part[L], ('neck', 'trunk', 'head')).all():
            continue
        Lf = order_from_front(V, L)
        midl.append(dict(inf, ids=Lf, y_front=float(V[Lf[0], 1])))
    midl.sort(key=lambda r: -r['y_front'])
    # ---- the NECK: K 42 loops between the jaw and the base; X = the lowest whose radius is within 10 % of the
    # narrowest's (the base's flare starts under it: radii 50.5 -> 55.4 -> 60.0 -> 66.9 mm on the woman)
    neck = [r for r in midl if r['K'] == 42 and lmy['suprasternale'] - 30.0 < r['y_front'] < lmy['suprasternale'] + 120.0]
    r_min = min(r['r'] for r in neck)
    cand = [r for r in neck if r['r'] <= 1.10 * r_min]
    X = min(cand, key=lambda r: r['y_front'])
    if neck_rings:
        # the room under each head's ring: X the HIGHEST neck loop (least flare) whose centre lies at least the strips'
        # minimum length down the ring's axis for every sex (the first rule left 16 mm on the woman: three strips of
        # 4 mm against hm08's ~11 mm)
        need = (H2['neck_min_plain'] + 1) * H2['neck_strip_min']

        def room(r):
            out = []
            for sx, (oc, on, Vs_) in neck_rings.items():
                c = Vs_[r['ids']].mean(0)
                out.append(float((oc - c) @ on))
            return min(out)
        ok = [r for r in neck if room(r) >= need and r['r'] <= 1.35 * r_min]
        assert ok, f'no hm08 neck loop leaves {need:.0f} mm under the head rings'
        X = max(ok, key=lambda r: r['y_front'])
        log(f'[hmcage] the room under the head rings: X leaves {room(X):.1f} mm (need {need:.0f})')
    log(f'[hmcage] neck loops K 42: {len(neck)}, radii {np.round([r["r"] for r in neck], 1).tolist()}; X at front y '
        f'{X["y_front"]:.1f} r {X["r"]:.1f}')
    # ---- the WAIST: P the highest K 42 trunk loop under the nipple's height, Q the lowest K 42 above the navel's loop
    chest_y = float(V[np.array(range(8434, 8466)), 1].mean())
    trunk42 = [r for r in midl if r['K'] == 42 and r['y_front'] < chest_y - 20.0 and r['y_front'] > lmy['crotch']]
    navel = [r for r in midl if r['K'] != 42 and lmy['crotch'] < r['y_front'] < chest_y - 40.0]
    y_nav = max(r['y_front'] for r in navel) if navel else lmy['omphalion']
    above = [r for r in trunk42 if r['y_front'] > y_nav + 10.0]
    P = max(above, key=lambda r: r['y_front'])
    Qw = min(above, key=lambda r: r['y_front'])
    between = [r for r in above if Qw['y_front'] < r['y_front'] < P['y_front']]
    log(f'[hmcage] waist: P front y {P["y_front"]:.1f}, Q {Qw["y_front"]:.1f} (the navel loop {y_nav:.1f}); '
        f'{len(between)} hm08 loops between them replaced by {H2["waist_new"]}')
    # ---- the quads kept: everything on the trunk's side of X, less the strip between P and Q
    top_v = int(np.argmax(V[:, 1]))
    seed_head = T.vq[top_v][0]
    head_side = T.side_of(X['ids'], seed_head)
    # a quad between P and Q: one holding P's front vertex and Q's side... flood from a quad just under P (its corners
    # all on P or below it, on the front)
    Pset, Qset = set(P['ids']), set(Qw['ids'])
    seed_w = None
    for qi in T.vq[P['ids'][0]]:
        q = Q0[qi]
        others = [v for v in q if v not in Pset]
        if others and all(V[v, 1] < V[P['ids'][0], 1] - 1.0 for v in others):
            seed_w = qi
            break
    assert seed_w is not None
    # the flood must stop at both loops
    cut = set()
    for Lc in (P['ids'], Qw['ids']):
        for a, b in zip(Lc, Lc[1:] + Lc[:1]):
            cut.add((min(a, b), max(a, b)))
    seen = np.zeros(len(Q0), bool)
    seen[seed_w] = True
    stack = [seed_w]
    while stack:
        qi = stack.pop()
        q = Q0[qi].tolist()
        for k in range(4):
            e = (min(q[k], q[(k + 1) % 4]), max(q[k], q[(k + 1) % 4]))
            if e in cut:
                continue
            for qj in T.emap[e]:
                if not seen[qj]:
                    seen[qj] = True
                    stack.append(qj)
    waist_q = seen
    keep_q = ~head_side & ~waist_q
    log(f'[hmcage] hm08 quads: {len(Q0)}; the head side of X {int(head_side.sum())}, the waist strip '
        f'{int(waist_q.sum())}; kept {int(keep_q.sum())}')
    # ---- re-index the kept hm08 vertices
    Qk = Q0[keep_q]
    hv = np.unique(Qk)
    h2c = -np.ones(nb, np.int64)
    h2c[hv] = np.arange(len(hv))
    n = [len(hv)]

    def new_id():
        n[0] += 1
        return n[0] - 1
    Qc = [tuple(int(h2c[v]) for v in q) for q in Qk.tolist()]
    tag = {}
    # ---- the NECK strips: the head ring (48 placeholders, index 0 the front midline, turning toward +x), the plain
    # loops, the band onto X
    K_ring = 48
    ring_h = [new_id() for _ in range(K_ring)]
    for v in ring_h:
        tag[v] = 'neck_ring'
    BT = BodyTopo2()
    BT.neck_plain = None              # set by place() once the ring's height is known: count fixed here (see below)
    # the count of plain loops: from the woman's ring height estimate (GNM's mid-neck at ~ the stature less 0.17) is
    # not known here; the plain loops are a topology choice, so fixed: neck_min_plain + 1 (the band's outer loop)
    n_plain = H2['neck_min_plain'] + 1
    neck_loops = [ring_h]
    for i in range(n_plain):
        Lp = [new_id() for _ in range(K_ring)]
        for v in Lp:
            tag[v] = 'neck'
        prev = neck_loops[-1]
        for k in range(K_ring):
            k1 = (k + 1) % K_ring
            Qc.append((prev[k], prev[k1], Lp[k1], Lp[k]))
        neck_loops.append(Lp)
    O = neck_loops[-1]
    back = K_ring // 2
    # the units over the back half of the neck, 60 deg apart (side by side at back -4 / 0 / +4 their quads were
    # crowded into a third of the back and folded on the man: look/dbg_M_neck_wire.png of the first build)
    centres = [back - 8, back, back + 8]
    hang = HT.band_pattern(K_ring, centres)
    Xc = [int(h2c[v]) for v in X['ids']]
    # X re-ordered so its vertex k sits under the outer position hang[k] (the walk's order): X from its front midline,
    # turning toward +x, rotated so its first vertex is under hang[0]
    n_i = len(Xc)
    assert n_i == K_ring - 2 * len(centres)
    s_hang = np.array(hang, np.float64) / K_ring
    # X's own arc parameters from its front midline
    sX = arc_params(V[X['ids']])
    # the rotation of X that best matches hang's parameters
    best = None
    for sh in range(n_i):
        idx = [(k + sh) % n_i for k in range(n_i)]
        cost = float(np.abs(((sX[idx] - s_hang + 0.5) % 1.0) - 0.5).sum())
        if best is None or cost < best[0]:
            best = (cost, idx)
    Xw = [Xc[i] for i in best[1]]
    Bn = HT.band(O, n_i, centres, new_id, inner_ids=Xw)
    Qc += Bn['quads']
    for (m, _, _) in Bn['mids']:
        tag[m] = 'neck'
    BT.neck_band = dict(outer=O, inner=Xw, centres=centres, hang=Bn['hang'], mids=Bn['mids'])
    BT.neck_loops = neck_loops
    BT.X = Xc
    BT.X_h = X['ids']
    # ---- the WAIST splice
    K_w = 44
    Pc = [int(h2c[v]) for v in P['ids']]
    Qwc = [int(h2c[v]) for v in Qw['ids']]
    new_loops = []
    for i in range(H2['waist_new']):
        Lw = [new_id() for _ in range(K_w)]
        for v in Lw:
            tag[v] = 'waist'
        new_loops.append(Lw)
    for a, b in zip(new_loops[:-1], new_loops[1:]):
        for k in range(K_w):
            k1 = (k + 1) % K_w
            Qc.append((a[k], a[k1], b[k1], b[k]))
    # the two bands, each one unit centred on the FRONT midline (outer position 0) of its K 44 loop
    wb = {}
    for key, outer, inner_h in (('upper', new_loops[0], P['ids']), ('lower', new_loops[-1], Qw['ids'])):
        cs = [0]
        hg = HT.band_pattern(K_w, cs)
        s_h = np.array(hg, np.float64) / K_w
        sI = arc_params(V[inner_h])
        best = None
        for sh in range(42):
            idx = [(k + sh) % 42 for k in range(42)]
            cost = float(np.abs(((sI[idx] - s_h + 0.5) % 1.0) - 0.5).sum())
            if best is None or cost < best[0]:
                best = (cost, idx)
        inner_c = [int(h2c[inner_h[i]]) for i in best[1]]
        Bw = HT.band(outer, 42, cs, new_id, inner_ids=inner_c)
        Qc += Bw['quads']
        for (m, _, _) in Bw['mids']:
            tag[m] = 'waist'
        wb[key] = dict(outer=outer, inner=inner_c, inner_h=[inner_h[i] for i in best[1]], hang=Bw['hang'],
                       mids=Bw['mids'])
    BT.waist_loops = new_loops
    BT.waist_ring = new_loops[H2['waist_new'] // 2]
    BT.waist_bands = wb
    BT.P, BT.Qw = Pc, Qwc
    BT.P_h, BT.Q_h = P['ids'], Qw['ids']
    BT.Q = np.array(Qc, np.int64)
    BT.hm_quads = np.nonzero(keep_q)[0]          # body quad j < len(hm_quads) is hm08's quad hm_quads[j]; the rest new
    BT.n = n[0]
    BT.h2c = h2c
    BT.c2h = -np.ones(BT.n, np.int64)
    BT.c2h[:len(hv)] = hv
    BT.tag = tag
    BT.ring_h = ring_h
    # parts per cage vertex (hm08's skin-weight parts; new vertices by their tags)
    pmap = dict(trunk='trunk', neck='neck', head='neck', arm_L='arms', arm_R='arms', hand_L='hands', hand_R='hands',
                leg_L='legs', leg_R='legs', foot_L='feet', foot_R='feet')
    BT.part = np.array(['trunk'] * BT.n, dtype=object)
    BT.part[:len(hv)] = [pmap[p] for p in part[hv]]
    for v, t in tag.items():
        BT.part[v] = 'neck' if t in ('neck', 'neck_ring') else 'trunk'
    TT = HT.Topo(BT.Q, BT.n)
    BT.topo = TT
    # ---- the MIRROR map, by topology: hm08's own for its vertices; the new loops (indexed from the front midline
    # toward +x) k <-> -k; a band's middle vertex <-> the middle vertex of the unit at the mirrored centre
    import os
    hmir = np.arange(len(d['V']))
    with open(os.path.join(HR.MH_DIR, 'mesh_metadata', 'hm08.mirror'), encoding='utf-8') as fh:
        for ln in fh:
            p = ln.split()
            if len(p) >= 2:
                hmir[int(p[0])] = int(p[1])
    mir = -np.ones(BT.n, np.int64)
    mir[:len(hv)] = h2c[hmir[hv]]
    assert (mir[:len(hv)] >= 0).all(), 'the kept hm08 vertices are not mirror closed'
    for Lq in neck_loops + new_loops:
        Kq = len(Lq)
        for k, v in enumerate(Lq):
            mir[v] = Lq[(-k) % Kq]
    for mids, Kq in ((Bn['mids'], K_ring), (wb['upper']['mids'], K_w), (wb['lower']['mids'], K_w)):
        bc = {c: m for (m, c, _) in mids}
        for (m, c, _) in mids:
            mir[m] = bc[(-c) % Kq]
    assert (mir >= 0).all() and (mir[mir] == np.arange(BT.n)).all(), 'the cage mirror map is not an involution'
    BT.mirror = mir
    BT.hm_mirror = hmir
    # ---- the LIMB rings on hm08's K 20 loops (left; the right by hm08's mirror map)
    BT.rings = {}
    arm_axis = np.array([J['l-shoulder'], J['l-elbow'], J['l-hand']])
    leg_axis = np.array([J['l-upper-leg'], J['l-knee'], J['l-ankle']])

    def chain_t(A, p):
        best_t, best_d = 0.0, np.inf
        for s in range(len(A) - 1):
            a, b = A[s], A[s + 1]
            ab = b - a
            f = float(np.clip((p - a) @ ab / (ab @ ab), 0, 1))
            dd = float(np.linalg.norm(p - (a + f * ab)))
            if dd < best_d:
                best_t, best_d = s + f, dd
        return best_t
    limb = {'arm': [], 'leg': []}
    for L, inf in zip(loops, info):
        if inf['K'] != 20 or inf['c'][0] < 1.0:
            continue
        # every vertex regular (Topo.loop_from never tests the loop's FIRST vertex: the first build's armscye carried
        # a pole there, h2_gates' ring row 1/1)
        if (T.val[L] != 4).any():
            continue
        pp = collections.Counter(part[L]).most_common(1)[0][0]
        if pp in ('arm_L', 'hand_L') and (part[L] != 'trunk').all():
            limb['arm'].append(dict(ids=L, t=chain_t(arm_axis, inf['c']), **inf))
        elif pp in ('leg_L',) and np.isin(part[L], ('leg_L', 'trunk', 'foot_L')).all():
            limb['leg'].append(dict(ids=L, t=chain_t(leg_axis, inf['c']), **inf))
    for k in limb:
        limb[k].sort(key=lambda r: r['t'])
    # the armscye: the first arm loop (lowest t) all of whose vertices lie distal of the axilla's apex along the arm
    ax_arm = (arm_axis[1] - arm_axis[0]) / np.linalg.norm(arm_axis[1] - arm_axis[0])
    p_ax = V[L_['axilla']]
    arm_ok = [r for r in limb['arm'] if ((V[r['ids']] - p_ax) @ ax_arm).min() > 2.0 and r['t'] < 0.6]
    pick = dict(armscye=min(arm_ok, key=lambda r: r['t']))
    # the hip: the first leg loop all of whose vertices lie under the crotch (the leg's root, just distal of it)
    leg_ok = [r for r in limb['leg'] if V[r['ids'], 1].max() < lmy['crotch'] - 2.0 and r['t'] < 0.5]
    pick['hip'] = min(leg_ok, key=lambda r: r['t'])
    # the rest nearest their chain parameters, the joints' rings first; a cut ring keeps three loops (its collar and a
    # free loop) from any ring already on its limb
    for nm in ('elbow', 'wrist', 'knee', 'ankle') + (('upperarm', 'thigh') if H2['cut_rings'] else ()):
        t = H2['ring_t'][nm]
        lst = limb['arm'] if nm in ('upperarm', 'elbow', 'wrist') else limb['leg']
        taken = [lst.index(pick[k]) for k in pick if pick[k] in lst]
        ok = [i for i in range(len(lst)) if all(abs(i - j) >= 3 for j in taken)]
        pick[nm] = lst[min(ok, key=lambda i: abs(lst[i]['t'] - t))]
    used_ids = set()
    for nm, r in pick.items():
        ids = order_limb_loop(V, r['ids'])
        assert not (set(ids) & used_ids), f'ring {nm} shares vertices with another ring'
        used_ids |= set(ids)
        BT.rings[nm] = dict(kind='leg_fore' if nm in ('armscye', 'upperarm', 'elbow', 'wrist') else 'leg_hind',
                            hm=ids, ids=[int(h2c[v]) for v in ids], t=float(r['t']), K=len(ids),
                            planar_hm08=float(r['planar']))
        log(f'[hmcage] ring {nm:9s} K {len(ids)} at chain t {r["t"]:.3f}, hm08 planarity {r["planar"]:.2f} mm')
    # rings must keep their collars apart: their one-rings disjoint
    ring_list = list(BT.rings.items())
    for i, (a, ra) in enumerate(ring_list):
        ca = set(ra['ids'])
        for v in ra['ids']:
            ca |= TT.nbr[v]
        for b, rb in ring_list[i + 1:]:
            cb = set(rb['ids'])
            for v in rb['ids']:
                cb |= TT.nbr[v]
            assert not (ca & cb), f'the collars of rings {a} and {b} touch'
    BT.limb_loops = limb
    BT.landmarks_rule = L_
    log(f'[hmcage] the body cage (before mirroring nothing: hm08 is whole): {BT.n} vertices, {len(BT.Q)} quads; '
        f'neck band 48 -> 42 units at {centres} (the back is {back}); waist K 44 x {H2["waist_new"]}')
    return BT


# ============================================================================================ the ports
def find_ports(BT, V_rules_cage, log=print):
    """the port blocks on the cage's topology: per port the regular a x b block nearest its spot (left side; the right
    by the mirror), clear of poles one ring round it, of the rings' collars and of the other ports. V_rules_cage: the
    cage's target positions (the woman's) the spots are measured on. Returns {name: dict(kind, grid, mid, side)}"""
    TT = BT.topo
    V = V_rules_cage
    L = BT.landmarks_rule
    ys = {k: float(V[BT.h2c[v], 1]) for k, v in L.items() if BT.h2c[v] >= 0}
    ys['P'] = float(V[BT.P, 1].mean())
    ys['Q'] = float(V[BT.Qw, 1].mean())
    # what a port's block and its one-ring may not touch: every ring's vertices and their one-rings (the collars), the
    # bands' middle vertices and their one-rings; the waist's other new loops are an ordinary grid at the back
    wl = BT.waist_loops
    iw = wl.index(BT.waist_ring)
    used = set()
    for ids in [r['ids'] for r in BT.rings.values()] + [[int(v) for v in BT.mirror[r['ids']]] for r in BT.rings.values()] \
            + [BT.waist_ring, wl[iw - 1], wl[iw + 1]]:
        for v in ids:
            used |= TT.nbr[v] | {v}
    for (m, _, _) in BT.waist_bands['upper']['mids'] + BT.waist_bands['lower']['mids'] + BT.neck_band['mids']:
        used |= TT.nbr[m] | {m}
    out = {}
    mir = BT.mirror
    for p in PORTS:
        base, dx, dy = p['at']
        want = np.array([0.0 if p.get('mid') else dx, ys[base] + dy, 0.0])
        G = None
        for (a, b) in p['blocks']:
            G = _port_block(TT, V, want, a, b, p.get('mid', False), used, mir)
            if G is not None:
                break
        assert G is not None, f'no regular block for {p["name"]} near {np.round(want, 1)}'
        a, b = G.shape[0] - 1, G.shape[1] - 1
        # a later port may not touch this one's BLOCK (its own one-quad collar may meet this one's: on hm08's ~18 mm
        # grid, collars kept apart left no room for the shell between the scapular pair and the waist splice)
        blk = set(G.ravel().tolist())
        used |= blk | set(mir[list(blk)].tolist())
        # rows run DOWN the back (the first axis along -y, row 0 the top: human_body.place_plugs' convention, whose
        # midline frame tangent G[0, 0] - G[-1, 0] then points up the back)
        if abs(V[G[-1, 0], 1] - V[G[0, 0], 1]) < abs(V[G[0, -1], 1] - V[G[0, 0], 1]):
            G = G.T.copy()
        if V[G[-1, 0], 1] > V[G[0, 0], 1]:
            G = G[::-1].copy()
        if p.get('mid'):
            # the midline block's columns from the midline toward +x: keep the half x >= 0 as human_body's place_plugs
            # reads a midline plug (its 'grid' the left half including the midline column)
            j0 = [j for j in range(G.shape[1]) if abs(V[G[0, j], 0]) < 1e-6]
            assert len(j0) == 1, 'a midline block must have one midline column'
            j0 = j0[0]
            left = G[:, j0:] if V[G[0, -1], 0] > 0 else G[:, :j0 + 1][:, ::-1]
            out[p['name']] = dict(kind=p['kind'], grid=left.copy(), mid=True, side='M', full=G)
        else:
            out[p['name'] + '_L'] = dict(kind=p['kind'], grid=G, mid=False, side='L')
            GR = mir[G][:, ::-1]
            out[p['name'] + '_R'] = dict(kind=p['kind'], grid=GR, mid=False, side='R')
        log(f'[hmcage] port {p["name"]}: a {a} x {b} block at {np.round(V[G[a // 2, b // 2]], 1).tolist()} '
            f'(K {2 * (a + b)}; wanted near x {want[0]:.0f}, y {want[1]:.0f})')
    return out


def port_records(BT, P, ports):
    """the ports' records ON hm08's skin, nothing moved: each block's boundary loop (a midline port's full loop: its
    left half, then the mirror of the right), K, centre, normal and radius of the loop's best-fit plane, its planarity
    (largest distance off the plane over the mean radius). H1's re-placement (a planar ring at equal angles projected on
    the skin, the interior by a Coons patch) dragged hm08's vertices on the sacrum's saddle into a sharp diamond over the
    top of the cleft (look/dbg_M_sacrum.png of the sixth build); H1's lead had already given a port's flat seat to the
    graft that uses it, and hm08's quads lie on the skin as they are"""
    mir = BT.mirror
    out = {}
    for name, pl in ports.items():
        G = pl['full'] if pl['mid'] else pl['grid']
        loop, inner = HT.grid_loop(G)
        X = P[loop]
        c = X.mean(0)
        U, s, Vt = np.linalg.svd(X - c)
        n = Vt[2]
        if n[2] > 0:
            n = -n                          # every port is on the back: its outward normal points to -z
        r = np.linalg.norm((X - c) - np.outer((X - c) @ n, n), axis=1)
        out[name] = dict(kind=pl['kind'], K=len(loop), loop=[int(v) for v in loop], inner=[int(v) for v in inner],
                         mid=pl['mid'], side=pl['side'], centre=c.tolist(), normal=n.tolist(), radius=float(r.mean()),
                         planarity=float(np.abs((X - c) @ n).max() / r.mean()), off_skin=0.0)
    return out


def _port_block(TT, V, want, a, b, mid, used, mir):
    """the regular a x b block (all its vertices and its one-ring valence 4, none of them in `used`) on the back nearest
    `want` (x, y); a midline block is its own mirror"""
    cand = np.argsort(np.linalg.norm(V[:, [0, 1]] - want[[0, 1]], axis=1))
    cand = [int(c) for c in cand[:600] if V[c, 2] < 0.0][:120]
    for c in cand:
        if mid and abs(V[c, 0]) > 1e-6:
            continue
        if not mid and V[c, 0] < 5.0:
            continue
        for w in sorted(TT.nbr[c], key=lambda w: -abs(V[w, 1] - V[c, 1]) / max(np.linalg.norm(V[w] - V[c]), 1e-9))[:2]:
            Gt = TT.block(c, w, a, b)
            if Gt is None:
                continue
            blk = set(Gt.ravel().tolist())
            ring = set()
            for v in blk:
                ring |= TT.nbr[v]
            ring -= blk
            if any(TT.val[v] != 4 for v in ring):
                continue
            if (blk | ring) & used:
                continue
            if mid and set(mir[Gt.ravel()].tolist()) != blk:
                continue
            return Gt
    return None


# ============================================================================================ placing
def section_points(tm, o, n, centre, s_vals, front=np.array([0.0, 0.0, 1.0]), side=np.array([1.0, 0.0, 0.0]),
                   radius=260.0, n_dense=721):
    """points on the reference's section by the plane (o, n) at the normalised arc parameters s_vals, measured from the
    section's FRONT point (the ray from centre along `front` projected) turning toward `side`: rays from centre in the
    plane at dense angles, their hits chained into the section polyline"""
    e1 = front - (front @ n) * n
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    if e2 @ side < 0:
        e2 = -e2
    th = np.linspace(0.0, 2 * np.pi, n_dense, endpoint=False)
    D = np.cos(th)[:, None] * e1[None, :] + np.sin(th)[:, None] * e2[None, :]
    O = np.repeat(np.asarray(centre, np.float64)[None, :], len(th), 0)
    t, f, b = tm.ray(O, D, radius * 3.0)
    ok = t > 0
    assert ok.all(), f'{int((~ok).sum())} section rays missed'
    X = O + t[:, None] * D
    sx = arc_params(X)
    s_vals = np.asarray(s_vals, np.float64) % 1.0
    Xc = np.vstack([X, X[:1]])
    sc = np.concatenate([sx, [1.0]])
    return np.column_stack([np.interp(s_vals, sc, Xc[:, k]) for k in range(3)])


def place(BT, sex, V_ref, smooth, head, log=print):
    """the body's TARGETS for one sex (cage ids of BT). V_ref: all hm08 vertices of the sex's reference (mm);
    smooth=(Vs, Fs, quad): its smooth surface; head: dict(ring=(48, 3) the head's neck ring in the body frame (index 0 the
    front midline, turning toward +x), gnm_tm, neck_axis (o, n) of GNM's mid-neck plane). Returns dict(P, records)"""
    Vs, Fs, _ = smooth
    tm = HR.TriMesh(Vs, Fs)
    nb_k = int((BT.c2h >= 0).sum())
    P = np.full((BT.n, 3), np.nan)
    P[:nb_k] = V_ref[BT.c2h[:nb_k]]
    recs = {}
    # ---- the neck: the ring (the head's), the plain loops and the band's outer loop between it and X, on the ONE neck
    # blend (NeckConform: hm08's own neck conformed to the ring, on GNM and tangent to it there, hm08 exactly L deeper);
    # hm08's targets in the zone (X among them) move with it. Its rays read hm08 without its head (near the ring at the
    # front they would meet hm08's own jaw)
    ring = np.asarray(head['ring'], np.float64)
    P[BT.ring_h] = ring
    part_v = HR.MHBody(sex, V_ref).part
    head_q = (part_v[np.asarray(HR.mh_data()['Q'], np.int64)] == 'head').all(1)
    tm_h = HR.TriMesh(Vs, Fs[~head_q[np.asarray(smooth[2], np.int64)]])
    blend = NeckConform(ring, P[BT.X], head['gnm_tm'], tm_h, H2['neck_conform_extra'])
    P0_hm = P[:nb_k].copy()
    P[:nb_k] = conform_points(blend.prm, P[:nb_k])
    mv = np.linalg.norm(P[:nb_k] - P0_hm, axis=1)
    blend.report.update(moved_max=float(mv.max()), moved_n=int((mv > 0.05).sum()))
    Xp = P[BT.X]
    cX = Xp.mean(0)
    nl = BT.neck_loops
    n_new = len(nl) - 1
    # arc parameters: the ring's (from its front vertex), the band's outer loop's from X through the band pattern
    sR = arc_params(ring)
    hang = BT.neck_band['hang']
    Xw_pos = P[BT.neck_band['inner']]
    # the inner loop's parameters from ITS front midline vertex
    sXw = arc_params(Xw_pos)
    jf = int(np.argmin(np.abs(Xw_pos[:, 0]) + 1e3 * (Xw_pos[:, 2] < cX[2])))
    sXw = (sXw - sXw[jf]) % 1.0
    K = len(ring)
    sO = np.full(K, np.nan)
    for k, hpos in enumerate(hang):
        sO[hpos] = sXw[k]
    for k in range(K):
        if np.isnan(sO[k]):
            a_, b_ = sO[(k - 1) % K], sO[(k + 1) % K]
            if b_ < a_:
                b_ += 1.0
            sO[k] = (0.5 * (a_ + b_)) % 1.0
    # the loops between: the curves' parameter t evenly from the ring (0) to X (1); their arc fractions eased from the
    # ring's to the band's outer loop's (both run 0 -> 1 from the front midline toward +x; unwrapped before mixing)
    sRu = np.unwrap(sR * 2 * np.pi) / (2 * np.pi)
    sOu = np.unwrap(sO * 2 * np.pi) / (2 * np.pi)
    sOu = sOu - np.round(sOu[0] - sRu[0])
    for i in range(1, n_new + 1):
        w_ = i / n_new                               # the outer loop (i = n_new) takes the band's parameters
        s_i = (1 - w_) * sRu + w_ * sOu
        P[nl[i]] = blend.points(i / (n_new + 1.0), s_i % 1.0)
    # the band's middle vertices: on their unit's apex curve, halfway from the outer loop to X
    t_out = n_new / (n_new + 1.0)
    for (m, c, ai) in BT.neck_band['mids']:
        P[m] = blend.points(0.5 * (t_out + 1.0), np.array([sO[c]]), symmetric=False)[0]
    recs['neck_blend'] = dict(blend.report, params=blend.params())
    # ---- the waist: A, B, RING, D, E on horizontal sections of the smooth reference between P and Q
    # the loops' PLANES eased from P's best-fit plane to Q's (hm08's waist loops lean: P's front sits 42 mm over its
    # back, Q's 21 mm; horizontal sections crowded P and Q at the front and printed a ledge across the woman's belly,
    # look/dbg_F_abdomen.png of the sixth build); the ring between them is planar by construction. The planes are read
    # from hm08's own P and Q BEFORE P's crushed columns are re-spaced (space_columns), so the ring keeps its plane
    def fit_plane(X):
        c = X.mean(0)
        n = np.linalg.svd(X - c)[2][2]
        return c, (n if n[1] > 0 else -n)
    cP_, nP_ = fit_plane(P[BT.P])
    cQ_, nQ_ = fit_plane(P[BT.Qw])
    nR_ = (nP_ + nQ_) / np.linalg.norm(nP_ + nQ_)
    recs['waist_spacing'] = space_columns(BT, P, tm, 0.5 * (cP_ + cQ_), nR_, log=log)
    Pp, Qp = P[BT.P], P[BT.Qw]
    yP, yQ = float(Pp[:, 1].mean()), float(Qp[:, 1].mean())
    nW = len(BT.waist_loops)
    sP = arc_params(Pp)
    sQ = arc_params(Qp)

    def outer_params(band, s_inner_src, inner_pos):
        Kw = len(band['outer'])
        so = np.full(Kw, np.nan)
        # the inner loop's vertices in walk order: their parameters from their own front midline
        sI = arc_params(inner_pos)
        jf = int(np.argmin(np.abs(inner_pos[:, 0]) + 1e3 * (inner_pos[:, 2] < 0.0)))
        sI = (sI - sI[jf]) % 1.0
        for k, hpos in enumerate(band['hang']):
            so[hpos] = sI[k]
        for k in range(Kw):
            if np.isnan(so[k]):
                a_, b_ = so[(k - 1) % Kw], so[(k + 1) % Kw]
                if b_ < a_:
                    b_ += 1.0
                so[k] = (0.5 * (a_ + b_)) % 1.0
        return so
    sA = outer_params(BT.waist_bands['upper'], sP, P[BT.waist_bands['upper']['inner']])
    sE = outer_params(BT.waist_bands['lower'], sQ, P[BT.waist_bands['lower']['inner']])
    # the loops between the bands: hm08's own column distribution (the mean of A's and E's, which carry P's and Q's
    # through the band pattern), its spacing smoothed round the loop (a Gaussian of 3 columns) so the unit's two extra
    # columns spread over the front instead of crowding the midline. (Evenly spaced middle loops met hm08's denser
    # front columns with a jog at both band rows: lines across the belly, look/dbg_F_abdomen_targets.png of the seventh
    # build; the unit's spacing copied the length of the splice printed a line up the front midline, the sixth)
    sAu = np.unwrap(sA * 2 * np.pi) / (2 * np.pi)
    sEu = np.unwrap(sE * 2 * np.pi) / (2 * np.pi)
    sEu = sEu - np.round(sEu[0] - sAu[0])
    s_avg = 0.5 * (sAu + sEu)
    gaps = np.diff(np.append(s_avg, s_avg[0] + 1.0))
    Kw0 = len(gaps)
    ker = np.exp(-0.5 * (np.arange(-9, 10) / 3.0) ** 2)
    ker /= ker.sum()
    gs = np.array([np.sum(ker * gaps[(k + np.arange(-9, 10)) % Kw0]) for k in range(Kw0)])
    gs /= gs.sum()
    s_mid = (s_avg[0] + np.concatenate([[0.0], np.cumsum(gs)[:-1]])) % 1.0
    # P's and Q's OWN shapes eased into the splice: hm08's loops are far from planar (P 18.5 mm off its plane on the
    # woman, 32.8 on the man; Q 9.5 / 22.1), so planar sections next to them left strips 3 to 29 mm tall (the man's 4 to
    # 50) and printed a crease along P across the belly and the flanks (look/dbg_F_abdomen.png of the eighth build).
    # Each loop above the ring takes P's deviation from P's own plane section at its arc fractions, weighted linearly
    # from 1 at P to 0 at the ring (2/3 on A, 1/3 on B), so a column's strips share its height evenly; below it Q's, the
    # same way; the ring stays planar. (A cubic ease, 0.74 / 0.26, closed the man's A-B strip to 0.3 mm on his flank,
    # where P dips 30 mm under its plane: a sliver of aspect 9.6)
    sPp, sQp = arc_params(Pp), arc_params(Qp)

    def deviation(X, sX, c_, n_, s_):
        return NeckConform._on(X, sX, s_) - section_points(tm, c_, n_, c_, s_)
    for i, Lw in enumerate(BT.waist_loops):
        f = (i + 1) / (nW + 1.0)
        o_ = (1 - f) * cP_ + f * cQ_
        n_ = (1 - f) * nP_ + f * nQ_
        n_ /= np.linalg.norm(n_)
        s_i = sA if i == 0 else (sE if i == nW - 1 else s_mid)
        pts = section_points(tm, o_, n_, o_, s_i)
        if i != nW // 2:
            u = f / 0.5 if f < 0.5 else (1.0 - f) / 0.5
            wgt = 1.0 - u
            dev = deviation(Pp, sPp, cP_, nP_, s_i) if f < 0.5 else deviation(Qp, sQp, cQ_, nQ_, s_i)
            pts = tm.closest(pts + wgt * dev)[0]
        # exact mirror symmetry (vertex k <-> K - k; the front and back midline on x 0)
        Kw = len(Lw)
        M = np.array([-1.0, 1.0, 1.0])
        for k in range(1, Kw // 2):
            pts[Kw - k] = pts[k] * M
        pts[0, 0] = pts[Kw // 2, 0] = 0.0
        P[Lw] = pts
    for key in ('upper', 'lower'):
        bd = BT.waist_bands[key]
        for (m, c, ai) in bd['mids']:
            mid = 0.5 * (P[bd['outer'][c]] + P[bd['inner'][ai]])
            q = tm.closest(mid[None, :])[0][0]
            q[0] = 0.0
            P[m] = q
    Rw = P[BT.waist_ring]
    recs['waist'] = dict(kind='body_region', K=len(BT.waist_ring), loop=[int(v) for v in BT.waist_ring],
                         y=float(Rw[:, 1].mean()))
    # the reduction units' two 3-poles eased off their flat corners (ease_units)
    ease_units(BT.topo, P, BT.neck_band, None)
    for key in ('upper', 'lower'):
        ease_units(BT.topo, P, BT.waist_bands[key], lambda X: tm.closest(X)[0])
    assert not np.isnan(P).any(), 'a body vertex has no target'
    # ---- the limb rings flattened (left; the right is their mirror), the loops either side relaxed on the reference
    TT = BT.topo
    mir = BT.mirror
    M = np.array([-1.0, 1.0, 1.0])
    held = np.zeros(BT.n, bool)
    held[BT.ring_h] = True
    held[BT.waist_ring] = True
    near = set()
    for nm, r in BT.rings.items():
        ids = np.array(r['ids'])
        Pf, info = flatten_ring(TT, P, ids, tm)
        P[ids] = Pf
        P[mir[ids]] = Pf * M
        held[ids] = held[mir[ids]] = True
        recs[nm] = dict(kind=r['kind'], K=len(ids), loop=[int(v) for v in ids], planarity_before=info['before'],
                        planarity_after=info['after'], moved_max=info['moved_max'])
        cur = set(int(v) for v in ids)
        for _ in range(H2['relax_rings']):
            nx = set()
            for v in cur:
                nx |= TT.nbr[v]
            cur |= nx
        near |= cur
    near = np.array(sorted(v for v in near if not held[v]), np.int64)
    P = relax_on(TT, P, near, tm, mir, iters=H2['relax_iters'])
    # exact mirror symmetry (the neck band's side units were projected one by one: 8-9 um apart)
    P = 0.5 * (P + P[mir] * M)
    P[mir == np.arange(BT.n), 0] = 0.0
    return dict(P=P, recs=recs, held=held, tm=tm, blend=blend)


# ============================================================================================ the nail folds (H2b)
# THE NAIL FOLDS (HUMAN_PLAN §2.4 "nail-fold loops round each nail bed (the nail is a part, §2.6)"; §2.6 "20 rigid nail
# plates in nail-fold collars, a SOCKET"). hm08 already draws every nail, topology AND form: on each digit's dorsal tip
# a patch of quads bounded by four 3-poles (the plate's corners) with loops round it, the plate a little proud of the
# skin with the fold's groove round it; H2's clay carries them (h2b/scratch/p13_nails.py, p14_nailbeds.py; under a raking
# light at 60 mm: look/regions_<sex>.png). The collar is the patch's boundary loop as hm08 draws it (K 10 on the thumb,
# 14 on the fingers, 12 on the toes: even, so K_low = 2 K is 0 mod 4, plan §2.7), recorded where it lies like the back
# ports (a fingertip is no plane: planarity 0.03-0.14), not held in the fit (held, the small quads at the thumb's and
# fingers' tips folded 14 / 22 clay triangles). The beds are NOT set in: a 0.45 / 0.6 mm seat (the plate's thickness)
# turned hm08's plate into a sunken socket on the clay (regions_M.png of the second H2b build); when the nail becomes
# its own part (§2.6) the skin's plate is what it replaces, and its seat is set then
NAILS = dict(depth=dict(finger=0.0, toe=0.0),
             digits=dict(thumb=('l-finger-1-2', 'l-finger-1-3'), index=('l-finger-2-3', 'l-finger-2-4'),
                         middle=('l-finger-3-3', 'l-finger-3-4'), ring=('l-finger-4-3', 'l-finger-4-4'),
                         little=('l-finger-5-3', 'l-finger-5-4'), toe1=('l-toe-1-2', 'l-toe-1-3'),
                         toe2=('l-toe-2-3', 'l-toe-2-4'), toe3=('l-toe-3-3', 'l-toe-3-4'), toe4=('l-toe-4-3', 'l-toe-4-4'),
                         toe5=('l-toe-5-3', 'l-toe-5-4')))


def find_nail_beds(sex, V_ref, log=print):
    """the 10 nail beds of the left hand and foot on hm08's topology (hm08 vertex ids; the right by hm08's mirror): per
    digit the four 3-poles near the distal segment joined pole to pole by straight edge runs into a 4-cycle, its boundary
    loop (the collar) and the patch's inner vertices (the smaller side of the loop). Returns {digit: dict(loop, inner,
    poles)}"""
    B = HR.MHBody(sex, V_ref)
    V, J = B.Vb, B.joints
    T = HT.Topo(B.Q, len(V))
    out = {}
    for dig, (j3, j4) in NAILS['digits'].items():
        a, b = np.asarray(J[j3]), np.asarray(J[j4])
        ax = (b - a) / np.linalg.norm(b - a)
        seg = float(np.linalg.norm(b - a))
        t = (V - a) @ ax
        r = np.linalg.norm((V - a) - np.outer(t, ax), axis=1)
        sel = np.nonzero((t > -0.5 * seg) & (t < 2.5 * seg) & (r < 16.0))[0]
        poles = set(int(v) for v in sel if T.val[v] == 3)
        runs = {}
        for p in poles:
            for w in T.nbr[p]:
                path = [p, w]
                while len(path) < 12 and path[-1] not in poles:
                    nx = T.straight(path[-2], path[-1])
                    if nx is None:
                        break
                    path.append(nx)
                if path[-1] in poles and path[-1] != p:
                    runs[(p, path[-1])] = path
        cyc = None
        for (p, q) in runs:
            for (q0, r_) in runs:
                if q0 != q or r_ == p:
                    continue
                for (r0, s_) in runs:
                    if r0 == r_ and s_ not in (p, q) and (s_, p) in runs:
                        cyc = (p, q, r_, s_)
                        break
                if cyc:
                    break
            if cyc:
                break
        assert cyc is not None, f'no nail bed found on the {dig}'
        loop = []
        for u, w in zip(cyc, cyc[1:] + cyc[:1]):
            loop += runs[(u, w)][:-1]
        lset = set(loop)
        pos = {v: i for i, v in enumerate(loop)}
        sides = []
        for q0 in T.quads_with(loop[0], loop[1]):
            seen, stack = {q0}, [q0]
            while stack and len(seen) < 400:
                q = B.Q[stack.pop()].tolist()
                for k in range(4):
                    e = (q[k], q[(k + 1) % 4])
                    if e[0] in lset and e[1] in lset and abs(pos[e[0]] - pos[e[1]]) in (1, len(loop) - 1):
                        continue
                    for qj in T.emap[(min(e), max(e))]:
                        if qj not in seen:
                            seen.add(qj)
                            stack.append(qj)
            sides.append(seen)
        bed = min(sides, key=len)
        inner = sorted(set(np.asarray(B.Q[sorted(bed)]).ravel().tolist()) - lset)
        out[dig] = dict(loop=[int(v) for v in loop], inner=[int(v) for v in inner], poles=[int(v) for v in cyc],
                        quads=len(bed))
    log(f'[hmcage] the nail beds: ' + ', '.join(f'{k} K {len(v["loop"])} ({v["quads"]} quads)' for k, v in out.items()))
    return out


def nail_beds(BT, P, beds, tm, log=print):
    """the nail folds on the body's targets (cage ids), in place on a copy: each bed's inner vertices set in along the
    reference's normal (NAILS['depth']: 0, the plates as hm08 draws them), both sides (hm08's mirror); the collars
    recorded where they lie. beds: from find_nail_beds (hm08 ids). Returns dict(P, recs (loop / inner as BODY cage ids:
    h2_build maps them into the whole cage), held (the collars' and beds' body ids, for a caller that holds them: H2b's
    build does not))"""
    P = P.copy()
    mir = BT.mirror
    h2c = BT.h2c
    # the reference's outward sense (its triangles' winding), as h2_build orients the cage
    vn_all = tm.normals()
    s_out = 1.0 if float(np.mean(np.einsum('ij,ij->i', tm.V - tm.V.mean(0), vn_all))) > 0 else -1.0
    recs = {}
    held = []
    for dig, b in beds.items():
        loop = h2c[np.asarray(b['loop'])]
        inner = h2c[np.asarray(b['inner'])]
        assert (loop >= 0).all() and (inner >= 0).all(), f'the {dig} nail bed is not in the cage'
        depth = NAILS['depth']['toe' if dig.startswith('toe') else 'finger']
        for side_ids_loop, side_ids_inner, side in ((loop, inner, 'L'), (mir[loop], mir[inner], 'R')):
            _, f2, b2 = tm.closest(P[side_ids_inner])
            n2 = s_out * tm.normal_at(f2, b2)
            P[side_ids_inner] = P[side_ids_inner] - depth * n2
            Xs = P[side_ids_loop]
            cs = Xs.mean(0)
            ns = np.linalg.svd(Xs - cs)[2][2]
            rs = np.linalg.norm((Xs - cs) - np.outer((Xs - cs) @ ns, ns), axis=1)
            dev = (Xs - cs) @ ns
            recs[f'nail_{dig}_{side}'] = dict(kind='nail', K=int(len(side_ids_loop)), K_low=int(2 * len(side_ids_loop)),
                                              loop=[int(v) for v in side_ids_loop],
                                              inner=[int(v) for v in side_ids_inner], centre=cs.tolist(),
                                              normal=(ns if ns @ n2.mean(0) > 0 else -ns).tolist(),
                                              radius=float(rs.mean()),
                                              planarity=float((dev.max() - dev.min()) / 2.0 / rs.mean()), depth=depth,
                                              side=side)
            held += [int(v) for v in side_ids_loop] + [int(v) for v in side_ids_inner]
    M = np.array([-1.0, 1.0, 1.0])
    P = 0.5 * (P + P[mir] * M)
    P[mir == np.arange(BT.n), 0] = 0.0
    log(f'[hmcage] the nail folds: {len(recs)} collars recorded where they lie (K ' +
        ', '.join(sorted(set(f'{r["K"]}' for r in recs.values()))) + '), the beds set in '
        f'{NAILS["depth"]["finger"]} / {NAILS["depth"]["toe"]} mm (fingers / toes)')
    return dict(P=P, recs=recs, held=np.array(sorted(set(held)), np.int64))


def ease_units(TT, P, band, project, ease=None):
    """a band's 4 -> 2 units with their 3-poles eased off their flat corners, in place: each unit's outer apex o2
    (valence 3 on the outer loop) and inner apex i1 (valence 3 on the inner loop) sit between their loop neighbours, so
    the quads they share with the unit's middle vertex m have a ~180 deg corner there (the kite under the neck band's o2:
    171-177 deg) and the clay printed a small nick at every unit (look/p11_unit_F.png of the eighth build: a short
    bright arc over the kite). Each moves `ease` (H2['unit_ease']) of the way to its one neighbour off the band (away
    from m), then onto the surface by `project` (or not: the neck's zone is a field, and the move is ~1.5 mm)"""
    ease = H2['unit_ease'] if ease is None else ease
    outer, inner = band['outer'], band['inner']
    on_outer, on_inner = set(outer), set(inner)
    for (m, c, ai) in band['mids']:
        for v, own in ((outer[c], on_outer), (inner[ai], on_inner)):
            off = [w for w in TT.nbr[v] if w not in own and w != m]
            if len(off) != 1:
                continue
            X = P[v] + ease * (P[off[0]] - P[v])
            P[v] = project(X[None, :])[0] if project is not None else X
    return P


def space_columns(BT, P, tm, o, n, log=print):
    """THE WAIST'S CRUSHED COLUMNS RE-SPACED, in place, before the splice's loops are placed on P. The splice's three
    strips over the ring share P's height over the ring's plane (o, n). Where hm08's loop P dips toward the ring (the
    man's flanks: P follows the costal margin ~90 mm down from its front peak, while the ring is planar) they shrank to
    4-6 mm under hm08's own 27-34 mm rows, and the fit, interpolating its targets through rows ~7 x denser than the
    ones over them, rang into a crease along P / A on both flanks (look:h2's scratch_h2_review/look/
    p03_M_heat_waist_loops.png, the clay's normal 78 deg off the reference's there; the turntable showed the line at
    108-132 deg). Each column (P's vertex v, the H2['waist_space_rows'] hm08 vertices straight over it, the next one
    held) has those vertices slid along it so that its intervals from the held vertex down to the ring (its rows' and
    the splice's three strips) come out even, by the weight w: the ramp of hm08's first row over the splice's strip from
    H2['waist_space_ratio'][0] (w 0) to [1] (w 1), smoothed round P (H2['waist_space_smooth']), so only crushed columns
    move (the woman's ratios stay under 2: she is untouched). A column that meets a pole over P stops under it (the
    pole held); one whose own P vertex is a pole (the band's apex, hm08's 5-pole beside it: the front, where nothing is
    crushed) does not move. The moved vertices go back onto the reference: the rows are re-spaced, the surface keeps
    its shape. P is walked from its front midline (vertex k mirrors K - k); the left side drives, the right mirrors.
    Returns the record (printed)"""
    lo, hi = H2['waist_space_ratio']
    nrow = H2['waist_space_rows']
    TT = BT.topo
    mir = BT.mirror
    nb_k = int((BT.c2h >= 0).sum())
    Pl = [int(x) for x in BT.P]
    K = len(Pl)
    Pset = set(Pl)

    def straight(prev, cur):
        # the neighbour of cur sharing no quad with the edge (prev, cur): the column's next vertex
        shared = set()
        for qi in set(TT.vq[prev]) & set(TT.vq[cur]):
            shared |= set(int(x) for x in BT.Q[qi])
        nxt = [w for w in TT.nbr[cur] if w not in shared]
        return nxt[0] if len(nxt) == 1 else None
    rec = dict(columns=0, moved=0, ratio_max=0.0, slide_max=0.0)
    cols, hs, wr = {}, np.zeros(K), np.zeros(K)
    for k in range(K // 2 + 1):                      # the front midline, the left side, the back midline
        v = Pl[k]
        hs[k] = float((P[v] - o) @ n)
        up = [w for w in TT.nbr[v] if w < nb_k and w not in Pset]
        if len(up) != 1 or TT.val[v] != 4:
            continue
        col = [v, up[0]]
        while len(col) < nrow + 2:
            nx = straight(col[-2], col[-1])
            if nx is None or nx >= nb_k or TT.val[col[-1]] != 4:
                break
            col.append(nx)
        seg = np.linalg.norm(np.diff(P[col], axis=0), axis=1)
        ratio = float(seg[0] / max(hs[k] / 3.0, 1e-6))
        rec['ratio_max'] = max(rec['ratio_max'], ratio)
        rec['columns'] += 1
        cols[k] = col
        wr[k] = float(np.clip((ratio - lo) / (hi - lo), 0.0, 1.0))
    for k in range(K // 2 + 1, K):
        wr[k] = wr[K - k]
    ws = wr.copy()
    for _ in range(H2['waist_space_smooth']):
        ws = 0.25 * np.roll(ws, 1) + 0.5 * ws + 0.25 * np.roll(ws, -1)
    goes = {}
    for k, col in cols.items():
        w = float(ws[k])
        if w <= 1e-3:
            continue
        X = P[col]
        seg = np.linalg.norm(np.diff(X, axis=0), axis=1)
        m = len(col) - 2                               # the column's rows over P that slide (the last vertex held)
        T = hs[k] + float(seg.sum())
        S = np.concatenate([[0.0], np.cumsum(seg)])
        # the even arcs from v up (the ring at -h, the held vertex at T - h): v, then its rows, one interval apart
        s_new = (3.0 + np.arange(m + 1)) * T / (m + 4.0) - hs[k]
        s_go = S[:-1] + w * (s_new - S[:-1])
        for j in range(m + 1):
            goes[col[j]] = np.array([np.interp(s_go[j], S, X[:, c]) for c in range(3)])
        rec['moved'] += 1
        rec['slide_max'] = max(rec['slide_max'], float(s_go[0]))
    left = Pl[:K // 2 + 1]
    strip0 = min(float((P[v] - o) @ n) for v in left) / 3.0
    if goes:
        ids = np.array(sorted(goes), np.int64)
        Y = tm.closest(np.array([goes[int(i)] for i in ids]))[0]
        M = np.array([-1.0, 1.0, 1.0])
        for i, y in zip(ids, Y):
            if mir[i] == i:
                y = y.copy()
                y[0] = 0.0
            P[i] = y
            P[mir[i]] = y * M
    rec['strip_min_before'] = strip0
    rec['strip_min_after'] = min(float((P[v] - o) @ n) for v in left) / 3.0
    log(f'[hmcage] the waist columns: {rec["moved"]} of {rec["columns"]} (one side and the midline) re-spaced (hm08\'s '
        f'first row over the splice\'s strip up to {rec["ratio_max"]:.1f} x; ramp {lo}-{hi}); the thinnest strip over '
        f'the ring {strip0:.1f} -> {rec["strip_min_after"]:.1f} mm; P slid up to {rec["slide_max"]:.1f} mm')
    return rec


def relax_on(TT, P, ids, tm, mir, iters=40, lam=0.5):
    """the vertices ids relaxed on the reference (umbrella steps pulled back to the closest point), their mirrors set
    to the mirrored positions after each step (the left side drives: ids with x >= 0)"""
    P = P.copy()
    M = np.array([-1.0, 1.0, 1.0])
    ids = np.asarray(ids, np.int64)
    left = ids[P[ids, 0] >= -1e-9]
    nb_list = [np.array(sorted(TT.nbr[int(v)]), np.int64) for v in left]
    midm = mir[left] == left
    for _ in range(iters):
        avg = np.array([P[nb].mean(0) for nb in nb_list])
        X = P[left] + lam * (avg - P[left])
        X = tm.closest(X)[0]
        X[midm, 0] = 0.0
        P[left] = X
        P[mir[left]] = X * M
    return P


def flatten_ring(TT, P, ids, tm, iters=4):
    """a ring's vertices slid along their columns on the reference onto the loop's least-squares plane: each vertex
    moved along the tangent toward its column neighbour by its distance off the plane over the tangent's component on
    the normal, then back onto the surface; repeated. Returns the new positions and the planarity before / after
    (max distance off the plane, mm) and the largest move"""
    X = P[ids].copy()
    X0 = X.copy()
    c = X.mean(0)
    U, s, Vt = np.linalg.svd(X - c)
    n = Vt[2]
    before = float(np.abs((X - c) @ n).max())
    ring = set(int(v) for v in ids)
    # each vertex's column direction: its neighbour off the ring (either side), the one most along the normal
    col = np.zeros_like(X)
    for i, v in enumerate(ids):
        offs = [w for w in TT.nbr[int(v)] if w not in ring]
        dirs = [P[w] - P[v] for w in offs]
        dd = max(dirs, key=lambda dv: abs(dv @ n) / max(np.linalg.norm(dv), 1e-9))
        col[i] = dd / np.linalg.norm(dd)
    for _ in range(iters):
        dist = (X - c) @ n
        cn = col @ n
        step = -dist / np.where(np.abs(cn) > 0.2, cn, np.sign(cn + 1e-12) * 0.2)
        X = X + step[:, None] * col
        X = tm.closest(X)[0]
        c = X.mean(0)
        U, s, Vt = np.linalg.svd(X - c)
        n = Vt[2]
    # the last residual onto the plane itself (a planar ring by construction; it leaves the skin by the rest)
    X = X - np.outer((X - c) @ n, n)
    after = float(np.abs((X - c) @ n).max())
    return X, dict(before=before, after=after, moved_max=float(np.linalg.norm(X - X0, axis=1).max()))


def conform_offset(prm, P):
    """NeckConform's field at the points P (prm: its params(), so the gates rebuild it from the records): the radial
    offset (mm), the radial unit directions, the depth along the neck under the ring's centre"""
    P = np.atleast_2d(np.asarray(P, np.float64))
    c, A, e1, e2 = (np.asarray(prm[k], np.float64) for k in ('c', 'A', 'e1', 'e2'))
    D = P - c
    dep = -(D @ A)
    R = D + np.outer(dep, A)
    r = np.maximum(np.linalg.norm(R, axis=1), 1e-9)
    dirs = R / r[:, None]
    th = np.arctan2(dirs @ e2, dirs @ e1)
    tk = np.asarray(prm['th'], np.float64)
    g = np.interp(th, tk, np.asarray(prm['g'], np.float64), period=2 * np.pi)
    s = np.interp(th, tk, np.asarray(prm['s'], np.float64), period=2 * np.pi)
    d0 = np.interp(th, tk, np.asarray(prm['d0'], np.float64), period=2 * np.pi)
    L = float(prm['L'])
    u = np.clip((dep - d0) / L, 0.0, 1.0)
    off = g * (2 * u ** 3 - 3 * u ** 2 + 1) + s * L * (u ** 3 - 2 * u ** 2 + u)
    return off, dirs, dep


def conform_points(prm, P):
    """the points P moved by NeckConform's field (identity from L under the ring down)"""
    off, dirs, _ = conform_offset(prm, P)
    return np.atleast_2d(np.asarray(P, np.float64)) + off[:, None] * dirs


class NeckConform:
    """the ONE blend of the neck's references (the lead's brief: "Decide which reference owns the neck and blend once,
    measured"). GNM OWNS the neck down to the head's ring (on GNM's mid-neck plane: the head cage is GNM's own); under it
    the neck is hm08's OWN surface CONFORMED to the ring: round the neck (per angle about the axis from X's centre to
    the ring's), hm08's radius plus an offset that equals the ring's radial gap to hm08 at the ring and the gap's slope
    (GNM's radius slope less hm08's, just under the ring), eased to zero offset and zero slope L mm deeper (the cubic
    Hermite g H0(u) + s L H1(u), u the depth under the ring at that angle over L; L reaches H2['neck_conform_extra'] mm
    under X's deepest vertex). So the neck leaves the ring ON GNM and TANGENT to it, keeps hm08's own forms down the zone
    (the throat, the nape, the base's flare into the trapezius) and is hm08 exactly from L down. X and the hm08 targets
    between X and L move by the same field: the reference is conformed, not met by a second surface; the strips between
    the ring and X lie on it (the chord between the ring's point and X's at each arc fraction, pushed radially onto it).
    WHY, after four tries: radii blended by a weight read GNM's lower neck, which flares into GNM's OWN shoulders, and
    printed a collar; curves in eased planes ended on X's plane, off X's vertices, and printed a ledge; one cubic per
    angle from the ring (tangent to GNM) to X (tangent to hm08) read neither reference between, so where the two disagree
    it had to bend: the man's ring stands 17 mm outside his hm08 neck at the back, with both surfaces sloping back
    under it, and the cubic came forward 5 mm and went back: a ridge at the ring over a groove at X, his nape's collar
    (scratch/p06_neck_sagittal.py, look/p06_neck_sagittal_M.png of the eighth build). Closing the gap in the phenotype
    solve moved the landmarks the head's placement reads (human_pheno, SEAM's note).
    Printed: the references' gap at the seam (the ring to hm08), the slope mismatch, L, how far hm08's targets moved."""

    def __init__(self, ring, Xo, tm_g, tm_h, extra):
        self.ring = np.asarray(ring, np.float64)
        Xo = np.asarray(Xo, np.float64)
        self.tm_g, self.tm_h = tm_g, tm_h
        c = self.ring.mean(0)
        A = c - Xo.mean(0)
        A /= np.linalg.norm(A)
        e1 = np.array([0.0, 0.0, 1.0]) - A[2] * A
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(A, e1)
        if e2[0] < 0:
            e2 = -e2
        self.c, self.A, self.e1, self.e2 = c, A, e1, e2
        D = self.ring - c
        dep = -(D @ A)
        R = D + np.outer(dep, A)
        rr = np.linalg.norm(R, axis=1)
        dirs = R / rr[:, None]
        th = np.arctan2(dirs @ e2, dirs @ e1)
        rH0, rH3 = self._radius(tm_h, dep, dirs), self._radius(tm_h, dep + 3.0, dirs)
        rG0, rG3 = self._radius(tm_g, dep, dirs), self._radius(tm_g, dep + 3.0, dirs)
        assert np.isfinite(rH0 + rH3 + rG0 + rG3).all(), 'a neck ray missed a reference'
        g = rr - rH0
        s = ((rG3 - rG0) - (rH3 - rH0)) / 3.0
        o = np.argsort(th)
        self.prm = dict(c=c, A=A, e1=e1, e2=e2, th=th[o], g=g[o], s=s[o], d0=dep[o], L=1.0)
        # L: under X's deepest vertex (its depth under the ring at its own angle) by `extra`
        DX = Xo - c
        depX = -(DX @ A)
        RX = DX + np.outer(depX, A)
        thX = np.arctan2(RX @ e2, RX @ e1)
        d0X = np.interp(thX, th[o], dep[o], period=2 * np.pi)
        self.prm['L'] = float((depX - d0X).max() + extra)
        self.Xo = conform_points(self.prm, Xo)
        self.sR = arc_params(self.ring)
        self.sX = arc_params(self.Xo)
        self.report = dict(L=self.prm['L'], gap=dict(p95=float(np.percentile(np.abs(g), 95)), max=float(np.abs(g).max()),
                                                       front=float(g[np.argmax(self.ring[:, 2])]),
                                                       back=float(g[np.argmin(self.ring[:, 2])])),
                           slope=dict(p95=float(np.percentile(np.abs(s), 95)), max=float(np.abs(s).max())),
                           ring_gnm_err=float(np.abs(rG0 - rr).max()))

    def _radius(self, tm, depth, dirs):
        O = self.c[None, :] - np.asarray(depth, np.float64)[:, None] * self.A[None, :]
        t, _, _ = tm.ray(O, dirs, 400.0)
        return np.where(t > 0, t, np.nan)

    def params(self):
        return {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in self.prm.items()}

    @staticmethod
    def _on(poly, s_poly, s):
        """the points at arc fractions s on a closed polyline whose vertices sit at s_poly"""
        Pc = np.vstack([poly, poly[:1]])
        sc = np.concatenate([s_poly, [1.0]])
        s = np.asarray(s, np.float64) % 1.0
        return np.column_stack([np.interp(s, sc, Pc[:, k]) for k in range(3)])

    def points(self, t, s_vals, symmetric=True):
        """the zone's points at t (0 the ring, 1 X, conformed) for the arc fractions s_vals: the chord between the
        ring's point and X's at each s, pushed radially onto the conformed hm08; symmetric: the loop is indexed from the
        front midline (vertex k <-> K - k mirrored exactly about x 0)"""
        s = np.asarray(s_vals, np.float64) % 1.0
        q = (1.0 - t) * self._on(self.ring, self.sR, s) + t * self._on(self.Xo, self.sX, s)
        off, dirs, dep = conform_offset(self.prm, q)
        rH = self._radius(self.tm_h, dep, dirs)
        assert np.isfinite(rH).all(), 'a neck ray missed hm08'
        out = self.c[None, :] - dep[:, None] * self.A[None, :] + (rH + off)[:, None] * dirs
        if symmetric:
            K = len(out)
            M = np.array([-1.0, 1.0, 1.0])
            for k in range(1, (K + 1) // 2):
                out[K - k] = out[k] * M
            out[0, 0] = 0.0
            if K % 2 == 0:
                out[K // 2, 0] = 0.0
        return out


def neck_align(Vs, Fs, S_, C_, gV, gF, off=30.0):
    """the z shift that centres GNM's lower neck on the body reference's (human_body.neck_align's rule, on H2's
    reference): the arc-length centroids of their sections on the plane parallel to the neck base plane (through the
    suprasternale S_ and the cervicale C_, level left to right) `off` mm over it. Returns (dz, body centroid, GNM's)"""
    nb = np.cross(np.array([1.0, 0.0, 0.0]), C_ - S_)
    nb /= np.linalg.norm(nb)
    if nb[1] < 0:
        nb = -nb
    o = 0.5 * (S_ + C_) + off * nb
    cents = []
    for VV, FF in ((Vs, Fs), (gV, gF)):
        S, _ = HR.plane_section(VV, FF, o, nb)
        S = S[np.linalg.norm(S.mean(1) - o, axis=1) < 140.0]
        lp = max(HR.section_loops(S), key=len)
        Pl = np.vstack([lp, lp[:1]])
        seg = np.linalg.norm(np.diff(Pl, axis=0), axis=1)
        cents.append(((0.5 * (Pl[1:] + Pl[:-1])) * seg[:, None]).sum(0) / seg.sum())
    return float(cents[0][2] - cents[1][2]), cents[0], cents[1]
