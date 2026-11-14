"""H3 (HUMAN_PLAN §7 and §9.2's H3; the lead's H3 brief to the forge builder): THE HUMAN'S UVs on the LOW (h3_build's
LOW cage at level 0: the shipped mesh), two sets: HEAD 4096 (unique) and BODY 4096 (the trunk unique; one arm with its
hand and one leg with its foot, shared by left and right). The step script is work/bestiary/human/h3/h3_uv.py.

THE ISLANDS. Every graft ring and port is an island boundary (plan §6.2 "tube cuts are island boundaries"; the lead's
"the rings and ports as island boundaries"): the neck ring (the HEAD | BODY seam itself), the ear rings, the scalp, horn
and gill ports, the armscye, elbow, wrist, hip, knee, ankle and waist rings, the back and sacral ports, the 20 nail-fold
collars. Inside the head, GNM's own groups: its 'mouth_sock' (the mouth bag, at 1/2 density: plan §7; GNM's own layout
keeps it an island of its own too), its 'eye_sockets' (the lid tucks, at 1/4), its 'hockey_mask' (the FACE) and the neck
bands between GNM's cut loop and the neck ring (the NECK island, graded: plan §7's ~5,500 px/m against the face's
~10,500); the rest of the head is the SCALP. SHARE holds each class's density over the set's.
THE CUTS (a tube needs one, an island must flatten): the head follows GNM's artists (its gnm_head.npz layout: one cut up
the back of the neck and over the crown to the hairline, the face whole in the middle; h3 forge probes p21): the SCALP
and the NECK cut on the back midline. The TRUNK splits front | back: side seams down the mid-axillary lines from each
armscye's lowest point to the waist and on to each hip ring's lateral point, shoulder seams from each armscye's top over
the trapezius to the neck ring, and the crotch seam between the hip rings' medial points. The ARM and LEG tubes cut on
their inner (medial) lines. Each path is the cheapest along the edges inside its island, cost = length x (1 + K x how
much the face is seen from where it should not be), the left solved and the right mirrored vertex for vertex.
THE CHARTS: axolotl_uv.charts_for (LSCM, injective ARAP; on a hard failure the hole bridges, then the normalised-cut
bisection) per designed island; the hands and feet go to it whole, their palms and soles as the cheap side.
(v4, the H3 successor, 10-30) THE FACE IS ONE CHART: GNM's artists' layout as the fold-free start (its island 1, the
mouth sock with the inner lips, joins our mouth island), relaxed by slim() (symmetric Dirichlet, local-global, a
fold-bounded line search, the holes scaffolded) and best_shape()'s MIPS + area. Any other flip-free chart past the soft
bars gets slim() and best_shape() before the house splitter. Designed seams on natural lines: the skin under the jaw
joins the NECK island (plan §7's step at "the jaw's shadow"), each EAR splits front | back along its helix rim, each
FOOT into its sole (with the toes' undersides) and its dorsum (one seam down its inner side from the ankle ring), and an
INFRAMAMMARY seam from each side seam to the sternum's. Known: the HEAD set's anisotropy p95 stays over the house's 1.2
with the face whole (the nose's sides and the ears' fronts: ~1.25); v3 met it only by cutting the face into 14 charts.
THE MIRROR: only the LEFT limbs (arm, hand, leg, foot, their nails) are charted and packed; each right quad takes its
mirror quad's corner UVs (the right limb is the left's exact mirror, vertex for vertex), so its tangent's handedness
flips (glTF TANGENT w = -1) and its texels are the left's.
THE PACK: stag_beetle_uv.pack (raster masks, FFT bottom-left, quarter turns) per set; each island padded by its
thickness / 8 within PAD texels; the density the highest that packs one page, at most CAP x 1.0 (the HEAD's face) or the
plan's BODY density x 1.10.
(v5, the H3b forge builder, 10-30) THE DIGITS: each finger's and toe's root ring (recs['digit_rings'], from
human_stack.find_digits) is an island border, each digit cut once from its ring to its nail collar along the side its
neighbour hides; the HAND without its digits splits into its palm and dorsum (by the fingernails' mean normal).
pack_contact replaces the bottom-left pack (max-contact placement, the minimum-area rectangle's four turns, exact masks;
the density search tries past its bisection); center_scales centres each chart's scale spread on 1 (the density gate);
quad_diagonals picks each quad's split so both UV triangles stay positive (H3's fixed 0-2 split folded 13); the stacked
copies (human_stack: the shells of their primary) are skipped by the pack and placed by their primary's transform.
(v6, the H3b forge builder's successor, 10-30) THE SEAT AND THE HIP CAP ON THE MIRROR: the plan sized BODY from
Lund-Browder's regions (1.069 m2 for the woman at 75 % fill: its 3,431 px/m), the buttocks and the thigh tops counted in
the legs; the built hip rings sit low on the thigh, so the unique trunk carried them (1.133 m2: the 6 % of density that
no pack could find, h3b scratch q03 / q05). Each buttock (seat_L / R: a seam along the edge loop under the back's lower
port to the sacral ring, the natal cleft on the midline) and each thigh top (hipcap_L / R: a seam along the inguinal crease
from the hip ring's medial point to the side seam) now share the left's texels, as the limbs do; the belly and the low
back stay unique. center_classes centres a class's p10 / p90 across its charts; pack_set takes the plan's density as its
target and tries several placement orders at each density (a greedy pack's success depends on them as much as on the
density). PAD's cap 6: each island is dilated by its pad + 1 and two neighbours' dilations may not touch, so the cap of 8
kept big islands 18-24 texels apart against the house's "padding is 8 texels" (HUMAN_PLAN §7), 6.2 % of the page; at 6 the
gutter is 14-20 texels, still past the rule.
"""
import collections

import numpy as np
from scipy.sparse.csgraph import connected_components, dijkstra
import scipy.sparse as sp

from . import axolotl_uv as AU
from . import stag_beetle_uv as BU

SIZE = 4096
SHARE = dict(face=1.0, scalp=0.8, neck=0.55, ear=0.9, mouth=0.5, lid=0.25, nostril=0.5, trunk=1.0, limb=1.0, hand=1.0,
             foot=1.0, nail=1.0)
# (v3. The first layout bisected the face and the scalp into many charts: the face's LSCM flipped inside the NOSTRIL
# POCKETS, and the scalp without the face is an ANNULUS whose flattening overlapped itself (h3 uv log 00:51). v2 tried
# GNM's own layout for face + scalp as one island (its per-corner UVs, one cut up the back and over the crown): a valid
# embedding but anisotropy p95 2.78 on our heads (its artists squeezed the crown on purpose; probes p22-p23), past the
# house's 1.2. So: the nostril pockets cut off at their rims (GNM's rim polygon in its UV layout, the H1 gates' rule),
# the face's border smoothed (GNM's hockey-mask group runs in quad steps), and the scalp cut into LEFT and RIGHT halves
# on the midline both ways, up the back over the crown to the hairline and from the chin down to the neck band)
CAP = dict(HEAD=11000.0, BODY=dict(F=3431.0 * 1.10, M=3231.0 * 1.10))     # px/m at share 1 (plan §7's densities)
PAD = (3, 6)                # (v6) per island: its dilation in the pack, so a gutter is the sum of two (the docstring)
CUT_K = 6.0
FACE_SCAFFOLD_W = 0.005     # (v4b) the face's hole scaffold weight: 0.02 held the lips' and nostrils' rims (aniso95 1.43
#                             against 1.37 free, where the mouth's rims overlapped); a lighter scaffold still bounds folds
SEAM_LOOPS = True           # (v4g) every designed cut along the edge loops (cut_path delegates to cut_path_loops) ...
SEAM_TURN = 4.0             # ... a turn costing 4 mean edges (the fold seam's setting)
LOOP_TURN = 8.0             # (v4f) cut_path_loops' turn (mean edges) and pull (per mean edge of distance from the jaw region's
JAW_PULL = 2.0              # upper edge) for the JAW line; FOLD_TURN the fold seam's. Probe p27's sweep (F): under the chin
FOLD_TURN = 4.0             # GNM's loops cross the jaw line, so a jaw seam must turn: 12 turns in 56 edges here (the per-quad
#                             labels turned at nearly every edge; turn 3 / pull 3 still 24); the only turn-free loop lies too
#                             low (38 quads above the band). The fold follows a real crease with 3 turns in 12 edges at 4,
#                             and at 6 or more its cheapest path jumps to a straight line on convex skin (rejected)
FOLD_SEAM = True            # (v4d) off: as a vertex path it ran a staircase across the front of the chest under the breasts
#                             (p26_uv_regions_F_parts.png), and without it BODY's anisotropy p95 is 1.210 (the breast halves
#                             4.3 % of the set over 1.2). (v4e) on again, along the edge loops (cut_path_loops)
SEAT_MIRROR = True          # (v6) the buttocks and thigh tops on the mirror (the module's docstring); off: H3's unique trunk
SEAT_BAND_MM = 45.0         # (v6) the seat's top seam leaves the side seam at most this far under the back's lower port


# ============================================================================================ small helpers
def loop_edges(ids):
    ids = [int(i) for i in ids]
    return {(min(a, b), max(a, b)) for a, b in zip(ids, ids[1:] + ids[:1])}


def quad_edge_map(Q):
    """edge (min, max) -> list of quads"""
    em = collections.defaultdict(list)
    for qi, q in enumerate(Q.tolist()):
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            em[(min(a, b), max(a, b))].append(qi)
    return em


def components(Q, quads, seams, em):
    """the connected components of the quads (indices) joined across edges that are not seams"""
    quads = np.asarray(quads, np.int64)
    pos = -np.ones(len(Q), np.int64)
    pos[quads] = np.arange(len(quads))
    rows, cols = [], []
    for e, lst in em.items():
        if len(lst) != 2 or e in seams:
            continue
        a, b = pos[lst[0]], pos[lst[1]]
        if a >= 0 and b >= 0:
            rows.append(a)
            cols.append(b)
    G = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(quads), len(quads)))
    n, lab = connected_components(G, directed=False)
    return [quads[lab == k] for k in range(n)]


def vertex_normals(V, Q):
    fn = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    N = np.zeros_like(V)
    for k in range(4):
        np.add.at(N, Q[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)


def clay_normals(low, Q, nh, nh_high, lim_V, lim_Q, n_high, mir=None, mirror_from=0):
    """THE LOW'S SHADING NORMALS FROM THE CLAY (the H3 forge builder's successor, 10-30): each LOW vertex takes the HIGH
    clay's limit normal at the same vertex (h3_build's two cages share ids: the head's GNM ids below nh_high, the body's
    shifted by the ear edit's appended vertices nh_high .. nh); the appended ones take a harmonic fill over the LOW's edges
    from their shared neighbours; vertices from mirror_from on (the body: its limbs share texels) are made exact mirrors
    through mir. The level-3 limit's first n_high vertices are the HIGH cage's own limit points (forge probe p31: equal
    to 1e-12 mm), so its quad-area normals there are the clay's. Why: the level-0 LOW's facet normals turn up to 18 deg
    (p99) from the clay (ear rims, lips, fingers), the bake writes that turn into the map, and an island edge or a mip
    shows it (the lobe's hem, forge probes p29-p31); with the clay's own normals the map carries only the detail.
    Returns unit normals (n, 3)"""
    import scipy.sparse.linalg as spl
    nV = len(low)
    Ql = np.asarray(lim_Q, np.int64)
    Nl = vertex_normals(np.asarray(lim_V, np.float64), Ql)[:n_high]
    hid = np.full(nV, -1, np.int64)
    hid[:nh_high] = np.arange(nh_high)
    hid[nh:] = np.arange(nh, nV) - nh + nh_high
    assert hid.max() < n_high, 'the LOW and HIGH cages do not share the body'
    N = np.zeros((nV, 3))
    has = hid >= 0
    N[has] = Nl[hid[has]]
    free = np.nonzero(~has)[0]
    if len(free):
        E = set()
        for q in np.asarray(Q, np.int64).tolist():
            for k in range(4):
                a, b = q[k], q[(k + 1) % 4]
                E.add((min(a, b), max(a, b)))
        E = np.array(sorted(E), np.int64)
        W = sp.coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
                          shape=(nV, nV)).tocsr()
        L = sp.diags(np.asarray(W.sum(1)).ravel()) - W
        Lff = L[free][:, free].tocsc()
        Lfb = L[free][:, has]
        for c in range(3):
            N[free, c] = spl.spsolve(Lff, -(Lfb @ N[has, c]))
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
    if mir is not None:
        M = np.array([-1.0, 1.0, 1.0])
        idx = np.arange(mirror_from, nV)
        Ns = 0.5 * (N[idx] + N[np.asarray(mir)[idx]] * M)
        N[idx] = Ns / np.maximum(np.linalg.norm(Ns, axis=1, keepdims=True), 1e-20)
    return N


def fold_report(low, Q, N):
    """per LOW quad, the angle (deg) between its own normal (the diagonals' cross) and the mean of its corners' given
    normals (the clay's): over 90 a fold against the clay"""
    Q = np.asarray(Q, np.int64)
    fn = np.cross(low[Q[:, 2]] - low[Q[:, 0]], low[Q[:, 3]] - low[Q[:, 1]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)
    cn = N[Q].mean(1)
    cn /= np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-20)
    return np.degrees(np.arccos(np.clip((fn * cn).sum(1), -1.0, 1.0)))


def cut_path(V, Q, quads, seams, a, b, cost_fn):
    """the cheapest edge path from vertex set a to vertex set b over the edges of the given quads that are not seams
    (a seam's own vertices may be passed through only at the ends); cost_fn(edge (k, 2) ids) -> weights. Returns its
    edges (min, max). (v4g: with SEAM_LOOPS every designed cut goes through cut_path_loops, so it keeps to the edge
    loops: the side and sternum seams stepped where they ran diagonal to the grid, p28)"""
    if SEAM_LOOPS:
        return cut_path_loops(V, Q, quads, seams, a, b, cost_fn, turn_pen=SEAM_TURN)
    q = Q[np.asarray(quads, np.int64)]
    E = set()
    for row in q.tolist():
        for k in range(4):
            u, v = row[k], row[(k + 1) % 4]
            E.add((min(u, v), max(u, v)))
    E = np.array(sorted(e for e in E if e not in seams), np.int64)
    w = cost_fn(E)
    n = len(V)
    G = sp.coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()
    a = list(a)
    dist, pred, src = dijkstra(G, indices=a, return_predecessors=True, min_only=True)
    bb = min(b, key=lambda v: dist[v])
    if not np.isfinite(dist[bb]):
        raise ValueError(f'no cut path from {a[:3]} to {list(b)[:3]}')
    out, v = set(), int(bb)
    while int(pred[v]) >= 0:
        u = int(pred[v])
        out.add((min(u, v), max(u, v)))
        v = u
    return out


def cut_path_loops(V, Q, quads, seams, a, b, cost_fn, turn_pen=3.0):
    """(v4e) cut_path that FOLLOWS EDGE LOOPS: a Dijkstra over directed edges, so a step that continues straight through
    a vertex (the next edge shares no quad with the last: along the loop) costs only its edge, and a turn adds turn_pen
    x the mean edge length. A vertex Dijkstra on a quad mesh zigzags wherever its line runs diagonal to the grid (the
    jaw's and the chest's staircases, p26); this one keeps to the artists' loops and turns only where it must. Returns
    the path's edges (min, max)"""
    import heapq
    q = Q[np.asarray(quads, np.int64)]
    eq = collections.defaultdict(set)
    for qi, row in zip(np.asarray(quads, np.int64).tolist(), q.tolist()):
        for k in range(4):
            u, v = row[k], row[(k + 1) % 4]
            eq[(min(u, v), max(u, v))].add(qi)
    E = np.array(sorted(e for e in eq if e not in seams), np.int64)
    if not len(E):
        raise ValueError('no edges')
    w = cost_fn(E)
    wd = {(int(u), int(v)): float(c) for (u, v), c in zip(E.tolist(), w)}
    adj = collections.defaultdict(list)
    for (u, v) in wd:
        adj[u].append(v)
        adj[v].append(u)
    lmean = float(np.mean(np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)))
    tgt = set(int(x) for x in b)
    best = {}
    heap = []
    for s in a:
        s = int(s)
        for v in adj[s]:
            c = wd[(min(s, v), max(s, v))]
            if c < best.get((s, v), np.inf):
                best[(s, v)] = c
                heapq.heappush(heap, (c, s, v))
    prev = {}
    end = None
    while heap:
        c, u, v = heapq.heappop(heap)
        if c > best.get((u, v), np.inf):
            continue
        if v in tgt:
            end = (u, v)
            break
        quv = eq[(min(u, v), max(u, v))]
        for x in adj[v]:
            if x == u:
                continue
            e2 = (min(v, x), max(v, x))
            straight = not (eq[e2] & quv)
            c2 = c + wd[e2] + (0.0 if straight else turn_pen * lmean)
            if c2 < best.get((v, x), np.inf):
                best[(v, x)] = c2
                prev[(v, x)] = (u, v)
                heapq.heappush(heap, (c2, v, x))
    if end is None:
        raise ValueError(f'no loop path from {list(a)[:3]} to {list(b)[:3]}')
    out, st = set(), end
    while st is not None:
        u, v = st
        out.add((min(u, v), max(u, v)))
        st = prev.get(st)
    return out


def path_turns(edges, em):
    """the number of turns along an edge path (consecutive edges sharing a quad), and its edge count"""
    adj = collections.defaultdict(list)
    for a, b in edges:
        adj[a].append((a, b))
        adj[b].append((a, b))
    turns = 0
    for v, es in adj.items():
        if len(es) == 2:
            if set(em[es[0]]) & set(em[es[1]]):
                turns += 1
    return turns, len(edges)


def mirror_edges(edges, mir):
    return {(min(int(mir[a]), int(mir[b])), max(int(mir[a]), int(mir[b]))) for a, b in edges}


# ============================================================================================ the islands
def gnm_layout(TH, Q):
    """GNM's artists' layout on our cage (v4): per cage quad its GNM corner UVs in the quad's own corner order (NaN where
    the quad is not GNM's: the ear edit's strip, the body) and GNM's UV island (0 the head, 1 the mouth sock with the
    inner lips; -1 not GNM's). Returns dict(quv (nq, 4, 2), qisl (nq,))"""
    from . import human_ref as HR
    gd = HR.gnm_data()
    tk = {tuple(sorted(t)): i for i, t in enumerate(gd['F'].tolist())}
    look = {}
    for qi, q in enumerate(gd['Q'].tolist()):
        cq = [int(TH.g2c[v]) for v in q]
        if min(cq) < 0:
            continue
        a, b, c, d = q
        gi = next(int(gd['island'][tk[tuple(sorted(t))]]) for t in ((a, b, c), (a, c, d), (a, b, d), (b, c, d))
                  if tuple(sorted(t)) in tk)
        look[frozenset(cq)] = (cq, gd['QUV'][qi], gi)
    quv = np.full((len(Q), 4, 2), np.nan)
    qisl = -np.ones(len(Q), np.int64)
    for qi, q in enumerate(np.asarray(Q).tolist()):
        hit = look.get(frozenset(int(v) for v in q))
        if hit is None:
            continue
        ids, cuv, gi = hit
        quv[qi] = [cuv[ids.index(int(v))] for v in q]
        qisl[qi] = gi
    return dict(quv=quv, qisl=qisl)


def design(V, Q, mir, n_head_q, recs, TH, grp, log=print, gnm=None):
    """the designed islands on the LOW (V: its positions, Q: its quads, the head's n_head_q first; recs: h3_build's
    records; TH: the head topology with the ear edit; grp: GNM's groups per cage vertex, plus 'nostril_pocket'; gnm:
    gnm_layout's, whose island 1 joins the mouth (v4)). Returns
    dict(isl: per quad its island id, names, cls (per island: SHARE's key), set (per island 'HEAD' / 'BODY'), seams (the
    edge set), mirror_of (per island: the left island it copies, or -1), hidden (per island: the cheap side's direction
    or None), loops, cuts)"""
    nq = len(Q)
    em = quad_edge_map(Q)
    VN = vertex_normals(V, Q)
    head_q = np.arange(n_head_q)
    body_q = np.arange(n_head_q, nq)
    # ---- the rings and ports
    loops = dict(neck=list(TH.neck_ring))
    for s in ('L', 'R'):
        loops[f'ear_{s}'] = list(recs['head'][f'ear_{s}']['loop'])
    for nm, r in recs['head'].items():
        if r.get('kind') in ('scalp', 'horn', 'gill'):
            loops[nm] = list(r['loop'])
    for nm, ids in recs['body_rings'].items():
        loops[nm] = list(ids)
    for nm, r in recs['nails'].items():
        loops[nm] = list(r['loop'])
    for nm, ids in recs.get('digit_rings', {}).items():
        # (v5, H3b) each finger's and toe's ROOT RING (human_stack.find_digits: the most proximal edge loop round the
        # digit's axis) is an island border: a UV seam on the digit's root crease, not a graft ring (K 10-14)
        loops[nm] = list(ids)
    seams = set()
    for ids in loops.values():
        seams |= loop_edges(ids)
    # ---- the head's regions (GNM's groups) as provisional labels on the head's main component only (the ears and the
    # ports inside their rings stay whole), stray fragments joined to their largest neighbour, the borders seams
    ring_comps = components(Q, head_q, seams, em)
    main = max(ring_comps, key=len)
    in_main = np.zeros(nq, bool)
    in_main[main] = True
    hl = np.array(['scalp'] * n_head_q, dtype=object)
    Qh = Q[head_q]
    hl[grp['hockey_mask'][Qh].all(1)] = 'face'
    # the face's border smoothed: a quad takes the label most of its edge neighbours carry (two passes)
    for _ in range(2):
        new = hl.copy()
        for qi in range(n_head_q):
            if not in_main[qi]:
                continue
            q = Q[qi]
            c = collections.Counter()
            for k in range(4):
                e = (min(int(q[k]), int(q[(k + 1) % 4])), max(int(q[k]), int(q[(k + 1) % 4])))
                for qj in em[e]:
                    if qj != qi and qj < n_head_q and in_main[qj] and e not in seams:
                        c[hl[qj]] += 1
            if c and c.most_common(1)[0][1] >= 3 and c.most_common(1)[0][0] != hl[qi]:
                new[qi] = c.most_common(1)[0][0]
        hl = new
    pocket = grp['nostril_pocket'][Qh].any(1)         # (the rule marks the tubes' inner vertices: the quads round them)
    hl[pocket & (V[Qh].mean(1)[:, 0] > 0)] = 'nostril_L'
    hl[pocket & (V[Qh].mean(1)[:, 0] < 0)] = 'nostril_R'
    old_n = min(min(TH.ear[s][k]) for s in ('L', 'R') for k in ('A', 'R', 'B'))
    band = np.zeros(len(V), bool)
    band[len(TH.gv):old_n] = True                     # the neck bands' own vertices (and the neck ring)
    hl[band[Qh].any(1)] = 'neck'
    hl[grp['mouth_sock'][Qh].all(1)] = 'mouth'
    if gnm is not None:
        # (v4) GNM's own island 1 (the mouth sock AND the inner lips beside it, 58 quads past the sock group) goes with
        # the mouth: left in the face, those quads' layout sits in GNM's other island and folded the face's chart
        hl[gnm['qisl'][:n_head_q] == 1] = 'mouth'
    sock = grp['eye_sockets'][Qh].all(1)
    hl[sock & (V[Qh].mean(1)[:, 0] > 0)] = 'lid_L'
    hl[sock & (V[Qh].mean(1)[:, 0] < 0)] = 'lid_R'
    # (v4b) THE JAW'S SHADOW (plan §7: the density steps on "the jaw's shadow, and the neck ring"): the skin under the
    # jaw, face or scalp, joins the NECK island (graded 0.55). Under the chin the face's chart sheared to 1.5 (h3 v4a:
    # 2.7 % of the HEAD set over 1.2 there). A quad goes when it faces down (n_y < -0.45), lies below the mouth by 15 mm
    # and in front of the neck's axis (the nape and the occiput's underside stay scalp)
    qn = np.cross(V[Qh[:, 2]] - V[Qh[:, 0]], V[Qh[:, 3]] - V[Qh[:, 1]])
    qn /= np.maximum(np.linalg.norm(qn, axis=1, keepdims=True), 1e-20)
    qc_h = V[Qh].mean(1)
    mouth_v = Qh[hl == 'mouth'].ravel()
    y_mouth = float(V[mouth_v, 1].min()) if len(mouth_v) else float(qc_h[:, 1].min())
    z_axis = float(V[list(TH.neck_ring), 2].mean())
    jaw = in_main[:n_head_q] & np.isin(hl, ['face', 'scalp']) & (qn[:, 1] < -0.45) & (qc_h[:, 1] < y_mouth - 15.0) & \
        (qc_h[:, 2] > z_axis)
    # (v4d) the line itself SMOOTH: per quad the labels above cut the quad grid diagonally into a sawtooth along the
    # whole jaw (p26_uv_regions_F_head.png). Instead: the cheapest edge path along the n_y = -0.45 contour between its
    # two lateral ends (cost length x (1 + 25 |n_y + 0.45|): a straight edge loop beats a zigzag, so the path takes
    # the jaw's own loop where GNM's artists laid one), and the neck side flood-filled from the neck band through the
    # down-facing skin below the mouth without crossing it
    cand = in_main[:n_head_q] & np.isin(hl, ['face', 'scalp']) & (qc_h[:, 1] < y_mouth - 15.0) & \
        (qc_h[:, 2] > z_axis - 10.0) & (qn[:, 1] < -0.1)
    cand_q = np.nonzero(cand)[0]
    jaw_done = False
    log(f'[uv] the jaw\'s shadow: {len(cand_q)} candidate quads (the per-quad rule: {int(jaw.sum())})')
    if len(cand_q) > 20:
        # the contour n_y = -0.45 has two branches under the chin (the jaw line, where the face turns under, and the
        # chin-neck angle below it, along the band's top): the line wanted is the UPPER one, the per-quad jaw region's
        # edge against the face and scalp above it; the path hugs it (cost: length x (1 + 3 x its distance from that
        # edge in mean edge lengths)) along the loops
        jset = set(np.nonzero(jaw)[0].tolist())
        up_v = set()
        for e, lst in em.items():
            if len(lst) == 2 and lst[0] < n_head_q and lst[1] < n_head_q:
                a_, b_ = lst
                if (a_ in jset) != (b_ in jset):
                    o_ = b_ if a_ in jset else a_
                    if hl[o_] in ('face', 'scalp') and in_main[o_] and qc_h[o_, 1] > qc_h[a_ if a_ in jset else b_, 1]:
                        up_v |= set(e)
        near_ = np.array(sorted(up_v), np.int64)
        log(f'[uv]   {len(near_)} vertices on the jaw region\'s upper edge')
        if len(near_) > 4:
            from scipy.spatial import cKDTree
            tree_ = cKDTree(V[near_])
            lm_ = float(np.mean([np.linalg.norm(V[a] - V[b]) for a, b in list(em)[:2000]]))
            jl = [int(near_[np.argmax(V[near_, 0])])]
            jr = [int(near_[np.argmin(V[near_, 0])])]
            jcost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * \
                (1.0 + JAW_PULL * tree_.query(0.5 * (V[E[:, 0]] + V[E[:, 1]]))[0] / lm_)            # noqa: E731
            try:
                jpath = cut_path_loops(V, Q, cand_q, seams, jl, jr, jcost, turn_pen=LOOP_TURN)
                log(f'[uv]   the jaw path: {path_turns(jpath, em)[0]} turns in {len(jpath)} edges')
                # the region it bounds: the skin below the mouth in front of the neck's axis, closed at each end of the
                # path by a loop path down to the neck band, flooded from the band's front quads
                allow = in_main[:n_head_q] & np.isin(hl, ['face', 'scalp']) & (qc_h[:, 1] < y_mouth - 15.0) & \
                    (qc_h[:, 2] > z_axis - 25.0)
                allow_q = np.nonzero(allow)[0]
                band_q = np.nonzero(hl == 'neck')[0]
                band_v = sorted(set(Qh[band_q].ravel().tolist()))
                lcost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)                # noqa: E731
                barrier = set(jpath)
                for end_ in (jl, jr):
                    barrier |= cut_path_loops(V, Q, allow_q, seams | jpath, end_, band_v, lcost)
                inc = np.zeros(nq, bool)
                inc[allow_q] = True
                lab_neck = np.zeros(nq, bool)
                lab_neck[:n_head_q] = hl == 'neck'
                front = [int(q) for q in band_q if qc_h[q, 2] > z_axis]
                touch = sum(1 for qi in front for k in range(4) for qj in
                            em[(min(int(Q[qi][k]), int(Q[qi][(k + 1) % 4])), max(int(Q[qi][k]), int(Q[qi][(k + 1) % 4])))]
                            if qj < n_head_q and inc[qj])
                log(f'[uv]   the flood: {len(front)} front band quads, {len(allow_q)} allowed quads, {touch} allowed '
                    f'neighbours of the band; the barrier {len(barrier)} edges; y_mouth {y_mouth:.1f}, the band\'s top '
                    f'y {float(qc_h[band_q, 1].max()):.1f}, the allowed y {float(qc_h[allow_q, 1].min()):.1f}-'
                    f'{float(qc_h[allow_q, 1].max()):.1f}')
                while front:
                    nxt_ = []
                    for qi in front:
                        q = Q[qi]
                        for k in range(4):
                            e = (min(int(q[k]), int(q[(k + 1) % 4])), max(int(q[k]), int(q[(k + 1) % 4])))
                            if e in barrier or e in seams:
                                continue
                            for qj in em[e]:
                                if qj < n_head_q and inc[qj] and not lab_neck[qj]:
                                    lab_neck[qj] = True
                                    nxt_.append(qj)
                    front = nxt_
                took = lab_neck[:n_head_q] & allow
                if took.sum() > 3.0 * max(jaw.sum(), 1):
                    log(f'[uv]   the flood leaked ({int(took.sum())} quads): the per-quad rule')
                    took[:] = False
                log(f'[uv]   a {len(jpath)}-edge loop path along the contour; the flood from the neck band took '
                    f'{int(took.sum())} candidate quads')
                if took.sum() > 0.25 * jaw.sum():
                    hl[took] = 'neck'
                    jaw_done = True
                    log(f'[uv] the jaw\'s shadow: the neck took {int(took.sum())} quads under the path (the per-quad '
                        f'rule would take {int(jaw.sum())})')
            except ValueError as ex:
                log(f'[uv] the jaw path failed ({ex}): the per-quad rule')
    if not jaw_done:
        hl[jaw] = 'neck'
    for _ in range(4):                                # fragments: each label's pieces but its largest join a neighbour
        region_seams = {e for e, lst in em.items() if len(lst) == 2 and in_main[lst[0]] and in_main[lst[1]] and
                        hl[lst[0]] != hl[lst[1]]}
        pieces = components(Q, main, seams | region_seams, em)
        biggest = {}
        for pc in pieces:
            lab = hl[pc[0]]
            if lab not in biggest or len(pc) > len(biggest[lab]):
                biggest[lab] = pc
        moved = 0
        for pc in pieces:
            lab = hl[pc[0]]
            if pc is biggest[lab]:
                continue
            nbl = collections.Counter()
            pcs = set(pc.tolist())
            for qi in pc.tolist():
                q = Q[qi]
                for k in range(4):
                    e = (min(int(q[k]), int(q[(k + 1) % 4])), max(int(q[k]), int(q[(k + 1) % 4])))
                    for qj in em[e]:
                        if qj not in pcs and in_main[qj]:
                            nbl[hl[qj]] += 1
            if nbl:
                hl[pc] = nbl.most_common(1)[0][0]
                moved += 1
        if not moved:
            break
    for e, lst in em.items():
        if len(lst) == 2 and in_main[lst[0]] and in_main[lst[1]] and hl[lst[0]] != hl[lst[1]]:
            seams.add(e)
    # ---- the components so far, named by their region / the rings they meet
    comps = components(Q, np.arange(nq), seams, em)
    loop_of = {}
    for nm, ids in loops.items():
        for e in loop_edges(ids):
            loop_of[e] = nm

    def bounds(cq):
        """the loops a component's boundary runs on"""
        cnt = collections.Counter()
        for qi in cq.tolist():
            q = Q[qi]
            for k in range(4):
                a, b = int(q[k]), int(q[(k + 1) % 4])
                e = (min(a, b), max(a, b))
                if e in loop_of:
                    cnt[loop_of[e]] += 1
        return cnt
    names, isl = [], -np.ones(nq, np.int64)
    for cq in comps:
        bd = bounds(cq)
        if cq[0] < n_head_q:
            reg = collections.Counter(hl[cq]).most_common(1)[0][0]
            if len(bd) == 1 and next(iter(bd)) != 'neck' and (next(iter(bd)).startswith('ear_') or
                                                              recs['head'].get(next(iter(bd)), {}).get('kind')):
                nm = next(iter(bd))                                   # an ear inside its ring, or a port's plug
                nm = nm if nm.startswith('ear_') else 'plug_' + nm
            else:
                nm = reg
        else:
            keys = set(bd)
            dig = [k for k in keys if k.startswith('digit_')]
            if len(keys) == 1 and (next(iter(keys)).startswith('nail_') or
                                   next(iter(keys)) in recs.get('plugs', {})):
                k0 = next(iter(keys))
                nm = k0 if k0.startswith('nail_') else 'plug_' + k0
            elif len(dig) == 1 and not any(k.startswith(('wrist_', 'ankle_')) for k in keys):
                nm = dig[0][len('digit_'):]                           # (v5) a finger or toe inside its root ring
            elif 'neck' in keys and 'waist' in keys:
                nm = 'trunk_up'
            elif 'waist' in keys and any(k.startswith('hip_') for k in keys):
                nm = 'trunk_lo'
            else:
                side = 'L' if V[Q[cq]].mean((0, 1))[0] > 0 else 'R'
                if f'armscye_{side}' in keys and f'elbow_{side}' in keys:
                    nm = f'uparm_{side}'
                elif f'elbow_{side}' in keys and f'wrist_{side}' in keys:
                    nm = f'forearm_{side}'
                elif f'wrist_{side}' in keys:
                    nm = f'hand_{side}'
                elif f'hip_{side}' in keys and f'knee_{side}' in keys:
                    nm = f'thigh_{side}'
                elif f'knee_{side}' in keys and f'ankle_{side}' in keys:
                    nm = f'shank_{side}'
                elif f'ankle_{side}' in keys:
                    nm = f'foot_{side}'
                else:
                    nm = 'body_' + '_'.join(sorted(keys))
        k = len(names)
        names.append(nm)
        isl[cq] = k
    assert (isl >= 0).all()
    cnt = collections.Counter(names)
    dup = [n for n, c in cnt.items() if c > 1]
    if dup:
        log(f'[uv] islands sharing a name before the cuts (expected for the regions split by holes): {dup}')
    idx = {n: i for i, n in enumerate(names)}

    def iq(nm):
        return np.nonzero(isl == idx[nm])[0]
    cuts = {}
    # ---- (v4b) two islands split in two along a designed line: each EAR into its front (lateral) and back (cranial)
    # faces along the helix rim (one chart whole sheared to 1.555: 2.5 % of the HEAD set over 1.2); each FOOT into its
    # sole with the toes' undersides and its dorsum with the toes' tops (the house splitter left a 404-face chart at
    # 1.587 and 13 charts). sub[q] tags the split-off piece ('back', 'sole') for the naming after the cuts
    sub = np.array([''] * nq, dtype=object)
    qn_all = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    qn_all /= np.maximum(np.linalg.norm(qn_all, axis=1, keepdims=True), 1e-20)

    def split_two(nm, is_b, tag):
        """the island's quads split by is_b (per global quad: True -> the tagged piece): a quad takes the label of 3 or
        more of its edge neighbours (two passes), each label's pieces but its largest go to the other label, the line
        between the labels becomes a seam. Returns the seam's vertices"""
        cq = iq(nm)
        pos = -np.ones(nq, np.int64)
        pos[cq] = np.arange(len(cq))
        nb = [[] for _ in cq]
        pairs = []
        for e, lst in em.items():
            if len(lst) == 2 and pos[lst[0]] >= 0 and pos[lst[1]] >= 0 and e not in seams:
                a, b = int(pos[lst[0]]), int(pos[lst[1]])
                nb[a].append(b)
                nb[b].append(a)
                pairs.append((a, b, e))
        lab = np.asarray(is_b, bool)[cq].copy()
        for _ in range(2):
            new = lab.copy()
            for k in range(len(cq)):
                c1 = sum(1 for j in nb[k] if lab[j])
                if c1 >= 3:
                    new[k] = True
                elif len(nb[k]) - c1 >= 3:
                    new[k] = False
            lab = new
        for val in (True, False):
            rr = [a for a, b, _ in pairs if lab[a] == val and lab[b] == val]
            cc = [b for a, b, _ in pairs if lab[a] == val and lab[b] == val]
            Gs = sp.coo_matrix((np.ones(len(rr)), (rr, cc)), shape=(len(cq), len(cq)))
            ncomp, cl = connected_components(Gs, directed=False)
            sel = np.nonzero(lab == val)[0]
            if not len(sel):
                continue
            big = np.bincount(cl[sel]).argmax()
            lab[sel[cl[sel] != big]] = not val
        line = set()
        for a, b, e in pairs:
            if lab[a] != lab[b]:
                seams.add(e)
                line |= set(e)
        sub[cq[lab]] = tag
        log(f'[uv] {nm} split: {int(lab.sum())} quads {tag}, {int((~lab).sum())} kept; the line {len(line)} vertices')
        return line
    head_c = V[:len(TH.gv)].mean(0)
    for s_ in ('L', 'R'):
        nm_e = f'ear_{s_}'
        if nm_e not in idx:
            continue
        lp = np.asarray(loops[nm_e])
        r_ = recs['head'][nm_e]
        rn = np.asarray(r_.get('normal', np.cross(V[lp[len(lp) // 4]] - V[lp[0]], V[lp[len(lp) // 2]] - V[lp[0]])),
                        np.float64)
        rn /= np.linalg.norm(rn)
        if rn @ (V[lp].mean(0) - head_c) < 0:
            rn = -rn
        split_two(nm_e, qn_all @ rn < 0.0, 'back')
    qkey = {frozenset(int(v) for v in q): qi for qi, q in enumerate(Q.tolist())}
    qmir = np.array([qkey.get(frozenset(int(mir[v]) for v in q), -1) for q in Q.tolist()], np.int64)
    sole_line = {}
    if 'foot_L' in idx:
        sole_line['L'] = split_two('foot_L', qn_all[:, 1] < -0.6, 'sole')
        # the right foot is the left's mirror quad for quad (its UVs are the left's): its split is the left's, mirrored
        sole_line['R'] = split_two('foot_R', np.array([sub[qmir[q]] == 'sole' if qmir[q] >= 0 else False
                                                       for q in range(nq)]), 'sole')
    if 'hand_L' in idx and recs.get('digit_rings'):
        # (v5, H3b) THE HAND without its digits (their root rings are borders) splits into its PALM and its DORSUM
        # along its edges and through the webs: a quad is the palm's when its normal points away from the fingernails'
        # mean normal (the dorsal direction); the right hand is the left's mirror, quad for quad
        dn = np.mean([recs['nails'][f'nail_{k}_L']['normal'] for k in ('index', 'middle', 'ring', 'little')], axis=0)
        dn = dn / np.linalg.norm(dn)
        split_two('hand_L', qn_all @ dn < 0.0, 'palm')
        split_two('hand_R', np.array([sub[qmir[q]] == 'palm' if qmir[q] >= 0 else False for q in range(nq)]), 'palm')

    def ring_pick(nm, key):
        ids = loops[nm]
        return [int(ids[int(np.argmax([key(V[v]) for v in ids]))])]
    # ---- the head: the SCALP on the midline both ways (up the back over the crown to the hairline, as GNM's artists
    # cut it; and from the chin down to the neck band), the NECK band on the back midline
    mid = set(np.nonzero(mir == np.arange(len(V)))[0].tolist())
    # (off the midline 10 x: a cut may step round a port on the midline, the forehead's horn, and still keep to it)
    mid_cost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * \
        np.where([(a in mid and b in mid) for a, b in E], 1.0, 10.0)                       # noqa: E731
    neck_ids = loops['neck']
    back_neck = [int(min(neck_ids, key=lambda v: V[v, 2] if v in mid else 1e9))]
    sc = iq('scalp')
    sc_v = set(Q[sc].ravel().tolist())
    nk = iq('neck')
    nk_v = set(Q[nk].ravel().tolist())
    shared = sorted(sc_v & nk_v)                    # GNM's cut loop: the scalp's lower edge, the neck island's upper
    fc_v = set(Q[iq('face')].ravel().tolist())
    border = list(sc_v & fc_v)

    def near(cands, best, r=12.0):
        """the candidates within r mm of the best one (a cut may end on any: a corner of the region whose every edge
        lies on its border cannot be reached by an interior edge)"""
        p = V[best]
        return sorted((int(v) for v in cands if np.linalg.norm(V[v] - p) <= r), key=lambda v: np.linalg.norm(V[v] - p))
    # (the ends: the face's border highest and lowest near the midline; the forehead's horn port can sit on the midline
    # between the face and the scalp, so the hairline's end need not be a midline vertex)
    top_back = near(shared, int(min((v for v in shared if v in mid), key=lambda v: V[v, 2])), 6.0)
    top_front = near(shared, int(max((v for v in shared if v in mid), key=lambda v: V[v, 2])), 6.0)
    hair = near(border, int(max(border, key=lambda v: V[v, 1] - 2.0 * abs(V[v, 0]))))
    chin = near(border, int(min(border, key=lambda v: V[v, 1] + 2.0 * abs(V[v, 0]))))
    cuts['neck'] = cut_path(V, Q, nk, seams, back_neck, top_back, mid_cost)
    # the chin's cut first (the scalp wraps under the jaw: an annulus round the face), kept to the scalp in front of the
    # neck's axis (else a detour round a midline strip of face could wrap round the back of the neck), then the back's
    zc = float(V[neck_ids, 2].mean())
    sc_front = np.array([q for q in sc.tolist() if V[Q[q]].mean(0)[2] > zc], np.int64)
    if any(v in mid and V[v, 2] > zc for v in (fc_v & nk_v)):
        # (v4b: the jaw's skin is the neck's) the face meets the neck at the front midline: the scalp is a horseshoe
        # already, the back cut alone halves it
        log('[uv] the face meets the neck at the front midline: no chin cut needed')
    else:
        try:
            cuts['scalp_front'] = cut_path(V, Q, sc_front, seams, chin, top_front, mid_cost)
        except ValueError:
            log('[uv] no chin cut path: the back cut alone halves the scalp')
    cuts['scalp_back'] = cut_path(V, Q, sc, seams | cuts.get('scalp_front', set()), top_back, hair, mid_cost)
    # ---- the trunk: the side, shoulder and crotch seams (left; the right mirrored)
    side_cost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * \
        (1.0 + CUT_K * np.abs(0.5 * (VN[E[:, 0], 2] + VN[E[:, 1], 2])))                   # noqa: E731
    down_cost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * \
        (1.0 + CUT_K * np.clip(0.5 + 0.5 * (VN[E[:, 0], 1] + VN[E[:, 1], 1]) * 0.5, 0.0, 1.0))  # noqa: E731
    tu, tl = iq('trunk_up'), iq('trunk_lo')
    waist_side = ring_pick('waist', lambda p: p[0])
    c_side = cut_path(V, Q, tu, seams, ring_pick('armscye_L', lambda p: -p[1]), waist_side, side_cost)
    c_sh = cut_path(V, Q, tu, seams, ring_pick('armscye_L', lambda p: p[1]), [v for v in neck_ids if V[v, 0] > 0],
                    side_cost)
    c_lo = cut_path(V, Q, tl, seams, waist_side, ring_pick('hip_L', lambda p: p[0]), side_cost)
    hipL = loops['hip_L']
    crotch_a = [int(min(hipL, key=lambda v: abs(V[v, 0]) + 0.2 * V[v, 1]))]
    c_cr = cut_path(V, Q, tl, seams, crotch_a, [int(mir[crotch_a[0]])], down_cost)
    for nm, es in (('side_L', c_side), ('shoulder_L', c_sh), ('side_lo_L', c_lo)):
        cuts[nm] = es
        cuts[nm.replace('_L', '_R')] = mirror_edges(es, mir)
    cuts['crotch'] = c_cr
    # (v2) the upper front trunk on its midline too, the sternum: whole, the breasts' curvature kept its chart at
    # anisotropy p95 1.37 and the BODY set at 1.226 (bar 1.2)
    front_neck = [int(max((v for v in neck_ids if v in mid), key=lambda v: V[v, 2]))]
    front_waist = [int(max((v for v in loops['waist'] if v in mid), key=lambda v: V[v, 2]))]
    tu_front = np.array([q for q in tu if VN[Q[q]].mean(0)[2] > 0.0], np.int64)
    cuts['sternum'] = cut_path(V, Q, tu_front, seams | c_side | mirror_edges(c_side, mir) | c_sh |
                               mirror_edges(c_sh, mir), front_neck, front_waist, mid_cost)
    # (v4b) THE INFRAMAMMARY FOLD (left; the right mirrored): from the side seam to the sternum's, along the concave
    # crease under the breast (the man: the pectoral's lower border), so the chest's dome flattens with a free lower edge
    # (each upper-front half sheared to 1.34-1.37 whole: 2.9 % of the BODY set over 1.2). Cost: length x (1 + 40 mm x the
    # edge's mean 2H), clipped to 0.15-4 (concave cheap); the path kept 15-170 mm under the chest's most forward point
    from .. import bake_mesh as BMH
    H2 = BMH.mean_curvature2(V, np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]), VN)
    tuf = np.array([q for q in tu_front if V[Q[q]].mean(0)[0] > 0], np.int64)
    apex = int(max(set(Q[tuf].ravel().tolist()), key=lambda v: V[v, 2]))
    ya = float(V[apex, 1])
    tuf_b = np.array([q for q in tuf if V[Q[q], 1].max() <= ya - 5.0], np.int64)
    in_band = lambda v: ya - 170.0 <= V[v, 1] <= ya - 15.0                         # noqa: E731
    side_v = sorted({int(v) for e in c_side for v in e if in_band(v)})
    st_v = sorted({int(v) for e in cuts['sternum'] for v in e if in_band(v)})
    # (v4g) a DART, not a cut to the sternum: run on to the midline, the concave crease between the breasts drew the
    # path up into the cleavage in spikes and the two sides crossed at the sternum (p28_seams_F.png). It ends under the
    # breast instead, at the fold's concave skin a little medial of the chest's most forward point (a notch in the
    # island's boundary, not an interior slit: the octopus's rule is about slits that reach no boundary)
    xa = float(V[apex, 0])
    tv_ = sorted({int(v) for v in Q[tuf_b].ravel().tolist() if in_band(v) and H2[v] < 0.0 and
                  abs(V[v, 0] - 0.55 * xa) < 0.12 * abs(xa)})
    if tv_:
        st_v = tv_
    fold_cost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * \
        np.clip(1.0 + 40.0 * 0.5 * (H2[E[:, 0]] + H2[E[:, 1]]), 0.15, 4.0)       # noqa: E731
    try:
        es = cut_path_loops(V, Q, tuf_b, seams | c_side | cuts['sternum'] | c_sh, side_v, st_v, fold_cost,
                            turn_pen=FOLD_TURN)
        fv = np.array(sorted({v for e in es for v in e}))
        msg = (f'{len(es)} edges, {path_turns(es, em)[0]} turns, {ya - V[fv, 1].max():.0f}-{ya - V[fv, 1].min():.0f} mm '
               f'under the chest\'s most forward point; its vertices\' 2H p50 {np.median(H2[fv]) * 1000:.1f} /m')
        if not FOLD_SEAM:
            log(f'[uv] the inframammary seam is off (FOLD_SEAM; the path found: {msg})')
        elif np.median(H2[fv]) < 0.0:
            cuts['fold_L'] = es
            cuts['fold_R'] = mirror_edges(es, mir)
            log(f'[uv] the inframammary seam: {msg}')
        else:
            # (v4c) only along a real crease: the man's cheapest path ran across his upper belly 109-127 mm under the
            # chest, on convex skin (2H +8.4 / m): no fold there, so no seam
            log(f'[uv] no inframammary seam: the path is not a crease ({msg})')
    except ValueError as ex:
        log(f'[uv] no inframammary seam ({ex})')

    # ---- (v6, H3b) THE SEAT AND THE HIP CAP (left; the right mirrored; the module's docstring has why). The back: along
    # the horizontal loop under the lower port from the side seam to the sacral ring, then the natal cleft on the midline
    # from the ring to the crotch seam. The front: from the hip ring's medial point up the inguinal crease (concave cheap,
    # the fold seam's cost) to the same point of the side seam, so what stays unique is one clean band
    if SEAT_MIRROR and 'sacral' in loops and 'back_lower_L' in loops:
        pieces = components(Q, tl, seams | c_lo | mirror_edges(c_lo, mir) | c_cr, em)
        lo_f = max(pieces, key=lambda c: float(np.mean(VN[Q[c].ravel(), 2])))
        lo_b = min(pieces, key=lambda c: float(np.mean(VN[Q[c].ravel(), 2])))
        y_port = float(V[loops['back_lower_L'], 1].min())
        side_all = sorted({int(v) for e in c_lo for v in e})
        side_v = [v for v in side_all if y_port - SEAT_BAND_MM <= V[v, 1] <= y_port - 2.0]
        sac = [int(v) for v in loops['sacral']]
        sac_v = [v for v in sac if V[v, 0] > 1.0 and V[v, 1] < y_port]
        flat_cost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)                  # noqa: E731
        c_seat = cut_path_loops(V, Q, lo_b, seams | c_lo | c_cr, side_v, sac_v, flat_cost, turn_pen=2.0 * SEAM_TURN)
        sv = [v for v in sorted({int(v) for e in c_seat for v in e}) if v in side_v]
        cleft_top = [min((v for v in sac if v in mid), key=lambda v: V[v, 1])]
        cr_mid = sorted({int(v) for e in c_cr for v in e if int(v) in mid})
        c_cleft = cut_path(V, Q, lo_b, seams | c_cr | c_seat | mirror_edges(c_seat, mir), cleft_top, cr_mid, mid_cost)
        groin_cost = lambda E: np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * \
            np.clip(1.0 + 40.0 * 0.5 * (H2[E[:, 0]] + H2[E[:, 1]]), 0.15, 4.0)                 # noqa: E731
        # (the groin starts on the hip ring or the crotch seam near the ring's medial point: that corner itself may have
        # no interior edge in the front piece)
        lo_f_v = set(Q[lo_f].ravel().tolist())
        cr_v = {int(v) for e in c_cr for v in e if v in lo_f_v}
        g_start = near((set(int(v) for v in hipL) & lo_f_v) | cr_v, crotch_a[0], 30.0)
        c_groin = cut_path_loops(V, Q, lo_f, seams | c_cr | c_lo, g_start, sv, groin_cost, turn_pen=FOLD_TURN)
        for nm, es in (('seat_L', c_seat), ('groin_L', c_groin)):
            cuts[nm] = es
            cuts[nm.replace('_L', '_R')] = mirror_edges(es, mir)
        cuts['cleft'] = c_cleft
        log(f'[uv] the seat and the hip cap: the seat seam {path_turns(c_seat, em)} (turns, edges) at y '
            f'{V[sorted({v for e in c_seat for v in e}), 1].min():.0f}-{V[sorted({v for e in c_seat for v in e}), 1].max():.0f}, '
            f'the cleft {len(c_cleft)} edges, the groin {path_turns(c_groin, em)} from y '
            f'{V[sorted({v for e in c_groin for v in e}), 1].min():.0f} to the side seam at y {V[sv[0], 1]:.0f}')

    # ---- the limbs' inner lines (left; the right mirrored)
    def medial_cost(axis_from, axis_to, toward):
        """cheap where the face looks toward `toward` (perpendicular to the limb's axis)"""
        ax = axis_to - axis_from
        ax /= np.linalg.norm(ax)
        m = toward - (toward @ ax) * ax
        m /= np.linalg.norm(m)

        def f(E):
            n = 0.5 * (VN[E[:, 0]] + VN[E[:, 1]])
            seen = 0.5 - 0.5 * (n @ m)                      # 0 facing the medial side, 1 facing away
            return np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * (1.0 + CUT_K * seen)
        return f, m

    def ring_c(nm):
        return V[loops[nm]].mean(0)
    for limb, r0, r1, toward in (('uparm_L', 'armscye_L', 'elbow_L', None), ('forearm_L', 'elbow_L', 'wrist_L', None),
                                 ('thigh_L', 'hip_L', 'knee_L', np.array([-1.0, 0.0, 0.0])),
                                 ('shank_L', 'knee_L', 'ankle_L', np.array([-1.0, 0.0, -0.3]))):
        c0, c1 = ring_c(r0), ring_c(r1)
        if toward is None:                                  # the arm: toward the trunk's axis, and down
            tw = np.array([0.0, c0[1], 0.0]) - 0.5 * (c0 + c1)
            toward = tw / np.linalg.norm(tw) + np.array([0.0, -0.5, 0.0])
        f, m = medial_cost(c0, c1, toward / np.linalg.norm(toward))
        a = ring_pick(r0, lambda p: (p - c0) @ m)
        b = ring_pick(r1, lambda p: (p - c1) @ m)
        es = cut_path(V, Q, iq(limb), seams, a, b, f)
        cuts[limb] = es
        cuts[limb.replace('_L', '_R')] = mirror_edges(es, mir)
    # (v4b) the foot's DORSUM is an annulus between the ankle ring and the sole's line: one seam from the ankle ring's
    # medial point down the foot's inner side (the leg's own seam runs down the inner shank) to the sole's line
    if 'foot_L' in idx and sole_line.get('L'):
        dq = np.array([q for q in iq('foot_L') if sub[q] != 'sole'], np.int64)
        ank = loops['ankle_L']
        a = [int(min(ank, key=lambda v: V[v, 0]))]

        def foot_cost(E):
            nn = 0.5 * (VN[E[:, 0]] + VN[E[:, 1]])
            return np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * (1.0 + CUT_K * (0.5 + 0.5 * nn[:, 0]))
        es = cut_path(V, Q, dq, seams, a, sorted(sole_line['L']), foot_cost)
        cuts['foot_L'] = es
        cuts['foot_R'] = mirror_edges(es, mir)
    # (v5, H3b) THE DIGITS' SEAMS: a finger or toe inside its root ring is a tube capped at its tip, its nail patch cut
    # out: one seam from the root ring to the nail collar along the side that faces its neighbour (the next digit toward
    # the little one; the little finger's and the fifth toe's toward the fourth), where the neighbour hides it, a little
    # toward the palm / sole; the right mirrored. Cost: length x (1 + CUT_K x how much the edge faces away from that side)
    nxt_d = dict(finger1='finger2', finger2='finger3', finger3='finger4', finger4='finger5', finger5='finger4',
                 toe1='toe2', toe2='toe3', toe3='toe4', toe4='toe5', toe5='toe4')
    nail_d = dict(finger1='thumb', finger2='index', finger3='middle', finger4='ring', finger5='little', toe1='toe1',
                  toe2='toe2', toe3='toe3', toe4='toe4', toe5='toe5')
    for dname in sorted(nxt_d):
        nm_d = f'{dname}_L'
        if nm_d not in idx or f'digit_{dname}_L' not in loops or f'digit_{nxt_d[dname]}_L' not in loops:
            continue
        ring = loops[f'digit_{dname}_L']
        collar = loops[f'nail_{nail_d[dname]}_L']
        dq_ = iq(nm_d)
        c0 = V[ring].mean(0)
        ax_d = V[np.unique(Q[dq_])].mean(0) - c0
        ax_d /= np.linalg.norm(ax_d)
        lat = V[loops[f'digit_{nxt_d[dname]}_L']].mean(0) - c0
        lat -= (lat @ ax_d) * ax_d
        lat /= np.linalg.norm(lat)
        dors = np.asarray(recs['nails'][f'nail_{nail_d[dname]}_L']['normal'], np.float64)
        dors -= (dors @ ax_d) * ax_d
        dors /= np.linalg.norm(dors)
        hd = lat - 0.3 * dors
        hd /= np.linalg.norm(hd)

        def digit_cost(E, hd=hd):
            nn = 0.5 * (VN[E[:, 0]] + VN[E[:, 1]])
            return np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * (1.0 + CUT_K * (0.5 - 0.5 * (nn @ hd)))
        es = cut_path(V, Q, dq_, seams, ring, collar, digit_cost)
        cuts[f'digit_{dname}_L'] = es
        cuts[f'digit_{dname}_R'] = mirror_edges(es, mir)
    for es in cuts.values():
        seams |= es
    # ---- the islands after the cuts (the trunk falls into its front and back)
    comps = components(Q, np.arange(nq), seams, em)
    names2, isl2 = [], -np.ones(nq, np.int64)
    for cq in comps:
        base = names[isl[cq[0]]]
        tag = collections.Counter(sub[cq].tolist()).most_common(1)[0][0]
        if tag == 'back':
            base = base.replace('ear_', 'earback_')
        elif tag == 'sole':
            base = base.replace('foot_', 'sole_')
        elif tag == 'palm':
            base = base.replace('hand_', 'palm_')
        if base == 'trunk_lo':
            # (v6) a trunk_lo piece that reaches a hip ring and NOT the waist is the seat (back) or the hip cap (front), on
            # the mirror; the belly touches both hip rings' medial ends, and reaches the waist
            side = 'L' if V[Q[cq]].mean((0, 1))[0] > 0 else 'R'
            keys = bounds(cq)
            if SEAT_MIRROR and f'hip_{side}' in keys and 'waist' not in keys:
                base = ('hipcap_' if float(np.mean(VN[Q[cq].ravel(), 2])) > 0 else 'seat_') + side
        if base in ('trunk_up', 'trunk_lo'):
            base += '_F' if float(np.mean(VN[Q[cq].ravel(), 2])) > 0 else '_B'
        if base == 'scalp':
            base += '_L' if float(np.mean(V[Q[cq].ravel(), 0])) > 0 else '_R'
        k = len(names2)
        names2.append(base)
        isl2[cq] = k
    # names unique (a region split by its holes keeps one name per piece: suffixes)
    seen_n = collections.Counter()
    for i, nm in enumerate(names2):
        seen_n[nm] += 1
        if seen_n[nm] > 1:
            names2[i] = f'{nm}#{seen_n[nm]}'

    def cls_of(nm):
        b = nm.split('#')[0]
        if b in ('face', 'neck', 'mouth'):
            return b
        if b.startswith('scalp'):
            return 'scalp'
        if b.startswith('lid_'):
            return 'lid'
        if b.startswith('nostril_'):
            return 'nostril'
        if b.startswith('ear_') or b.startswith('earback_'):
            return 'ear'
        if b.startswith('nail_'):
            return 'nail'
        if b.startswith('hand_') or b.startswith('palm_') or b.startswith('finger'):
            return 'hand'
        if b.startswith('foot_') or b.startswith('sole_') or b.startswith('toe'):
            return 'foot'
        if b.startswith('trunk_') or b.startswith('plug_back') or b == 'plug_sacral':
            return 'trunk'
        if b.startswith('plug_'):
            return 'plug'
        return 'limb'
    cls = [cls_of(nm) for nm in names2]
    sets = ['HEAD' if np.any(isl2[:n_head_q] == i) else 'BODY' for i in range(len(names2))]
    # a head port's plug takes its surroundings' share
    for i, nm in enumerate(names2):
        if cls[i] == 'plug':
            cq = np.nonzero(isl2 == i)[0]
            vs = set(Q[cq].ravel().tolist())
            around = collections.Counter()
            for e, lst in em.items():
                if len(lst) == 2 and (isl2[lst[0]] == i) != (isl2[lst[1]] == i):
                    j = lst[1] if isl2[lst[0]] == i else lst[0]
                    around[cls[isl2[j]]] += 1
            cls[i] = around.most_common(1)[0][0] if around else 'scalp'
    # the mirror: a right limb island copies the left one of the same name. (v6) The back's port plugs too: back_upper_R and
    # back_lower_R are exact mirrors of the left's, with nothing unique to bake (the plan's "mirrored parts share UV shells"),
    # and they are ports: what shows there is a graft or plain skin. The midline plugs (back_shell, sacral) have no twin;
    # plugs are not stacked ACROSS regions: each continues its own region's skin, and a shared shell would show as a patch
    mirror_of = [-1] * len(names2)
    nid = {nm: i for i, nm in enumerate(names2)}
    for i, nm in enumerate(names2):
        if sets[i] == 'BODY' and ('_R' in nm) and not nm.startswith('trunk'):
            left = nm.replace('_R', '_L')
            if left in nid:
                mirror_of[i] = nid[left]
    hidden = [np.array([0.0, -1.0, 0.0]) if c in ('hand', 'foot') else None for c in cls]
    log(f'[uv] designed islands: {len(names2)} ({sum(1 for s in sets if s == "HEAD")} HEAD, '
        f'{sum(1 for s in sets if s == "BODY")} BODY, {sum(1 for m in mirror_of if m >= 0)} of them right copies); '
        f'cuts (edges / turns) {", ".join(f"{k} {len(v)}/{path_turns(v, em)[0]}" for k, v in cuts.items())}')
    return dict(isl=isl2, names=names2, cls=cls, set=sets, seams=seams, mirror_of=mirror_of, hidden=hidden,
                loops=loops, cuts=cuts)


# ============================================================================================ SLIM (H3 v4)
def _tri_frames(V, F):
    """per triangle: its area and the inverse of its edge matrix in a local orthonormal 2-D frame (the map's Jacobian is
    the UV edge matrix times it), and the 2 x 3 gradient operator of a linear function over the triangle"""
    V = np.asarray(V, np.float64)
    e1, e2 = V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]
    n = np.cross(e1, e2)
    A = 0.5 * np.linalg.norm(n, axis=1)
    x1 = np.linalg.norm(e1, axis=1)
    b1 = e1 / np.maximum(x1, 1e-30)[:, None]
    b2 = np.cross(n / np.maximum(2.0 * A, 1e-30)[:, None], b1)
    X = np.zeros((len(F), 2, 2))
    X[:, 0, 0] = x1
    X[:, 0, 1] = (e2 * b1).sum(1)
    X[:, 1, 1] = (e2 * b2).sum(1)
    det = X[:, 0, 0] * X[:, 1, 1]
    Xi = np.zeros_like(X)
    Xi[:, 0, 0] = X[:, 1, 1] / np.where(np.abs(det) < 1e-30, 1e-30, det)
    Xi[:, 0, 1] = -X[:, 0, 1] / np.where(np.abs(det) < 1e-30, 1e-30, det)
    Xi[:, 1, 1] = X[:, 0, 0] / np.where(np.abs(det) < 1e-30, 1e-30, det)
    D = np.array([[-1.0, 1.0, 0.0], [-1.0, 0.0, 1.0]])
    G = np.einsum('tkj,kv->tjv', Xi, D)               # (t, 2 columns x / y, 3 vertices): grad of u = G u_t
    return A, G


def _jac(U, F, G):
    """per triangle the 2 x 2 Jacobian: rows the gradients of u and v"""
    Ut = U[F]                                           # (t, 3, 2)
    return np.einsum('tcv,tvi->tic', G, Ut)            # J[t, i (u / v), c (x / y)]


def _sd_energy(J, A):
    s = np.linalg.svd(J, compute_uv=False)
    with np.errstate(divide='ignore', invalid='ignore'):
        e = (s ** 2).sum(1) + (1.0 / np.maximum(s, 1e-300) ** 2).sum(1)
    det = J[:, 0, 0] * J[:, 1, 1] - J[:, 0, 1] * J[:, 1, 0]
    e = np.where(det > 0, e, np.inf)
    return float((A * e).sum() / A.sum())


def _max_step(U, d, F):
    """the largest t in (0, inf) for which every triangle's signed UV area stays positive along U + t d"""
    p1, p2 = U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]
    q1, q2 = d[F[:, 1]] - d[F[:, 0]], d[F[:, 2]] - d[F[:, 0]]
    cr = lambda a, b: a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]          # noqa: E731
    c0, c1, c2 = cr(p1, p2), cr(p1, q2) + cr(q1, p2), cr(q1, q2)
    t = np.full(len(F), np.inf)
    lin = np.abs(c2) < 1e-20
    with np.errstate(divide='ignore', invalid='ignore'):
        tl = np.where(lin & (c1 < 0), -c0 / c1, np.inf)
        disc = c1 * c1 - 4.0 * c2 * c0
        sq = np.sqrt(np.maximum(disc, 0.0))
        r1 = (-c1 - sq) / (2.0 * c2)
        r2 = (-c1 + sq) / (2.0 * c2)
    r1 = np.where(r1 > 0, r1, np.inf)
    r2 = np.where(r2 > 0, r2, np.inf)
    tq = np.where((~lin) & (disc >= 0), np.minimum(r1, r2), np.inf)
    t = np.minimum(np.where(lin, tl, tq), t)
    return float(t.min()) if len(t) else np.inf


def _boundary_loops_tri(F):
    """the chart's boundary loops (vertex lists), each in its triangles' own direction"""
    und = collections.Counter()
    for t in F.tolist():
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            und[(min(a, b), max(a, b))] += 1
    nxt = {}
    for t in F.tolist():
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            if und[(min(a, b), max(a, b))] == 1:
                nxt[a] = b
    loops, seen = [], set()
    for a in nxt:
        if a in seen:
            continue
        lp, v = [], a
        while v not in seen and v in nxt:
            seen.add(v)
            lp.append(v)
            v = nxt[v]
        loops.append(lp)
    return loops


def _ear_clip(P):
    """a simple polygon's triangulation by ear clipping (P (k, 2), counter-clockwise): local index triples"""
    idx = list(range(len(P)))
    tris = []

    def a2(a, b, c):
        return (P[b, 0] - P[a, 0]) * (P[c, 1] - P[a, 1]) - (P[b, 1] - P[a, 1]) * (P[c, 0] - P[a, 0])

    def inside(m, a, b, c):
        return a2(a, b, m) > 0 and a2(b, c, m) > 0 and a2(c, a, m) > 0
    while len(idx) > 3:
        n = len(idx)
        best = None
        for k in range(n):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % n]
            ar = a2(a, b, c)
            if ar <= 0:
                continue
            if any(inside(m, a, b, c) for m in idx if m not in (a, b, c)):
                continue
            best = k
            break
        if best is None:                                # a degenerate remainder: the largest convex corner
            best = int(np.argmax([a2(idx[k - 1], idx[k], idx[(k + 1) % n]) for k in range(n)]))
        tris.append((idx[best - 1], idx[best], idx[(best + 1) % len(idx)]))
        idx.pop(best)
    tris.append(tuple(idx))
    return [t for t in tris if a2(*t) > 0]


def hole_scaffold(F, U):
    """the triangles that fill every HOLE of the chart (each boundary loop but the one enclosing the largest UV area),
    ear-clipped in the layout U: the scaffold slim() keeps positive, so a hole's rim can move but never cross itself"""
    loops = _boundary_loops_tri(np.asarray(F, np.int64))
    if len(loops) <= 1:
        return np.zeros((0, 3), np.int64)

    def parea(lp):
        p = U[lp]
        return 0.5 * float((p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]).sum())
    outer = max(loops, key=lambda lp: abs(parea(lp)))
    out = []
    for lp in loops:
        if lp is outer or len(lp) < 3:
            continue
        lp = list(lp) if parea(lp) > 0 else list(lp)[::-1]
        for a, b, c in _ear_clip(U[lp]):
            out.append((lp[a], lp[b], lp[c]))
    return np.array(out, np.int64).reshape(-1, 3)


def slim(V, F, U0, iters=40, tol=1e-6, log=None, scaffold=True, scaffold_w=0.02):
    """SLIM (Rabinovich, Poranne, Panozzo, Sorkine-Hornung 2017: scalable locally injective mappings) on the symmetric
    Dirichlet energy |J|^2 + |J^-1|^2, from a FOLD-FREE start U0 (every triangle positive): per iteration the local step
    (each Jacobian's closest rotation R and the energy's reweighting W = U diag(w) U^T, w_i^2 = (s_i - s_i^-3) /
    (s_i - 1)), the global step (the area-weighted least squares |W (J - R)|^2 over every UV, one vertex pinned), then a
    line search no longer than 0.8 x the step that first collapses a triangle (so the map stays fold-free), halved until
    the true energy falls. The energy is infinite at a fold, so the start must be fold-free (GNM's layout is; an LSCM
    with flips is not). SCAFFOLD (after Jiang et al. 2017's bijective scaffolds, kept fixed here): every hole is filled
    with triangles ear-clipped in U0 (hole_scaffold), at rest in their U0 shape and weighted scaffold_w x their area;
    they take part in the line search's fold bound, so a hole's rim (the mouth's, a nostril's) can move but never cross
    itself (h3 probe p25: without them the mouth's rims overlapped by 60k texels). Returns (U, energies; 4 an isometry)"""
    import scipy.sparse.linalg as spla
    F = np.asarray(F, np.int64)
    U = np.asarray(U0, np.float64).copy()
    A, G = _tri_frames(V, F)
    keep = A > 1e-14
    F, A, G = F[keep], A[keep], G[keep]
    if scaffold:
        Fs = hole_scaffold(F, U)
        if len(Fs):
            As, Gs = _tri_frames(np.column_stack([U, np.zeros(len(U))]), Fs)
            ok = As > 1e-14
            Fs, As, Gs = Fs[ok], As[ok] * scaffold_w, Gs[ok]
            F, A, G = np.vstack([F, Fs]), np.concatenate([A, As]), np.concatenate([G, Gs])
            if log:
                log(f'[slim] scaffold: {len(Fs)} triangles in the holes')
    n = len(U)
    J = _jac(U, F, G)
    E = _sd_energy(J, A)
    hist = [E]
    if not np.isfinite(E):
        raise ValueError('slim: the start has a folded triangle')
    sqA = np.sqrt(A)
    t_idx = np.arange(len(F))
    pin = int(F[0, 0])
    for it in range(iters):
        Uu, s, Vt = np.linalg.svd(J)
        dR = np.linalg.det(Uu @ Vt)
        Uu[dR < 0, :, 1] *= -1.0
        s = np.where(dR[:, None] < 0, s * np.array([1.0, -1.0]), s)
        R = Uu @ Vt
        sa = np.abs(s)
        with np.errstate(divide='ignore', invalid='ignore'):
            w2 = np.where(np.abs(sa - 1.0) < 1e-6, 4.0, (sa - sa ** -3.0) / (sa - 1.0))
        w = np.sqrt(np.clip(w2, 1e-8, 1e8))
        W = np.einsum('tij,tj,tkj->tik', Uu, w, Uu)          # (t, 2, 2) symmetric
        # rows: per triangle, per column c (x, y), per component i: sqrt(A) (W[i,0] G_c . u + W[i,1] G_c . v)
        rows, cols, vals, rhs = [], [], [], []
        r = 0
        for c in range(2):
            for i in range(2):
                rid = r + 4 * t_idx
                for k in range(3):
                    rows += [rid, rid]
                    cols += [F[:, k], n + F[:, k]]
                    vals += [sqA * W[:, i, 0] * G[:, c, k], sqA * W[:, i, 1] * G[:, c, k]]
                rhs.append((rid, sqA * (W[:, i, 0] * R[:, 0, c] + W[:, i, 1] * R[:, 1, c])))
                r += 1
        m = 4 * len(F)
        big = float(np.sqrt(A.sum())) * 10.0
        rows += [np.array([m, m + 1])]
        cols += [np.array([pin, n + pin])]
        vals += [np.array([big, big])]
        M = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(m + 2, 2 * n))
        b = np.zeros(m + 2)
        for rid, v in rhs:
            b[rid] = v
        b[m], b[m + 1] = big * U[pin, 0], big * U[pin, 1]
        z = spla.spsolve((M.T @ M).tocsc(), M.T @ b)
        Un = np.column_stack([z[:n], z[n:]])
        d = Un - U
        tmax = _max_step(U, d, F)
        t = min(1.0, 0.8 * tmax)
        while t > 1e-10:
            Jn = _jac(U + t * d, F, G)
            En = _sd_energy(Jn, A)
            if En < E:
                break
            t *= 0.5
        if t <= 1e-10:
            break
        U = U + t * d
        J = Jn
        rel = (E - En) / E
        E = En
        hist.append(E)
        if log:
            log(f'[slim] it {it}: energy {E:.5f} (step {t:.3f}, cap {tmax:.3f})')
        if rel < tol:
            break
    return U, hist


def mips_relax(V, F, U0, beta=0.3, iters=600, tol=1e-7, scaffold=True, mem=10, log=None):
    """(v4c) the SHAPE-first relaxation: area-weighted sum over the triangles of (s1/s2 + s2/s1) + beta (s1 s2 +
    1/(s1 s2)) (Hormann and Greiner's MIPS with an area term: conformal distortion first, scale second; smaller beta
    lets the scale wander to buy shape), by L-BFGS with the fold-bounded line search of slim() (no step past 0.8 x the
    first collapse of any triangle, the hole scaffold's included), from a FOLD-FREE start. The house's gate reads
    anisotropy (s1/s2) p95 per set and the density per class within +-10 %: symmetric Dirichlet holds the scale to
    +-6 % on the face and leaves its shear (h3 v4b: the face 1.372, 4.6 % of the HEAD set over 1.2). Returns (U, E)"""
    F = np.asarray(F, np.int64)
    U = np.asarray(U0, np.float64).copy()
    A, G = _tri_frames(V, F)
    keep = A > 1e-14
    F, A, G = F[keep], A[keep], G[keep]
    w = A / A.sum()
    Fs = hole_scaffold(F, U) if scaffold else np.zeros((0, 3), np.int64)
    if len(Fs):
        # the scaffold carries the same barrier at a small weight, at rest in its start shape: with no energy its
        # triangles (pressed thin by slim's rims) capped every step (the face did not move, v4c's first try)
        As, Gs = _tri_frames(np.column_stack([U, np.zeros(len(U))]), Fs)
        ok = As > 1e-14
        F = np.vstack([F, Fs[ok]])
        G = np.concatenate([G, Gs[ok]])
        w = np.concatenate([w, 0.005 * As[ok] / A.sum()])
    Fall = F

    def eg(X):
        J = _jac(X, F, G)
        det = J[:, 0, 0] * J[:, 1, 1] - J[:, 0, 1] * J[:, 1, 0]
        if (det <= 0).any():
            return np.inf, None
        fro = (J ** 2).sum((1, 2))
        E = float((w * (fro / det + beta * (det + 1.0 / det))).sum())
        cof = np.stack([np.stack([J[:, 1, 1], -J[:, 1, 0]], -1), np.stack([-J[:, 0, 1], J[:, 0, 0]], -1)], 1)
        dJ = 2.0 * J / det[:, None, None] - (fro / det ** 2)[:, None, None] * cof + \
            beta * (1.0 - 1.0 / det ** 2)[:, None, None] * cof
        gt = np.einsum('tic,tcv->tvi', dJ * w[:, None, None], G)
        g = np.zeros_like(X)
        np.add.at(g, F, gt)
        return E, g
    E, g = eg(U)
    if not np.isfinite(E):
        raise ValueError('mips_relax: the start has a folded triangle')
    S, Y = [], []
    E0 = E
    le = float(np.linalg.norm(U[F[:, 1]] - U[F[:, 0]], axis=1).mean())      # the first step moves 1 % of an edge
    for it in range(iters):
        q = g.ravel().copy()
        al = []
        for s, y in reversed(list(zip(S, Y))):
            rho = 1.0 / float(y @ s)
            a = rho * float(s @ q)
            q -= a * y
            al.append((rho, a))
        if S:
            q *= float(S[-1] @ Y[-1]) / float(Y[-1] @ Y[-1])
        else:
            q *= 0.01 * le / max(float(np.abs(q).max()), 1e-30)
        for (s, y), (rho, a) in zip(zip(S, Y), reversed(al)):
            b = rho * float(y @ q)
            q += s * (a - b)
        d = -q.reshape(-1, 2)
        slope = float(g.ravel() @ d.ravel())
        if slope >= 0:
            S, Y = [], []
            d = -g * (0.01 * le / max(float(np.abs(g).max()), 1e-30))
            slope = float(g.ravel() @ d.ravel())
        t = min(1.0, 0.8 * _max_step(U, d, Fall))
        En, gn = np.inf, None
        while t > 1e-14:
            En, gn = eg(U + t * d)
            if En <= E + 1e-4 * t * slope:
                break
            t *= 0.5
        if gn is None or t <= 1e-14:
            break
        s, y = (t * d).ravel(), (gn - g).ravel()
        if float(y @ s) > 1e-18:
            S.append(s)
            Y.append(y)
            if len(S) > mem:
                S.pop(0)
                Y.pop(0)
        U = U + t * d
        rel = (E - En) / max(abs(E), 1e-30)
        E, g = En, gn
        if rel < tol and it > 20:
            break
    if log:
        log(f'[mips] beta {beta}: {it + 1} iterations, energy {E0:.5f} -> {E:.5f}')
    return U, E


def best_shape(Vc, Fc, U, px_mm, betas=(0.6, 0.3, 0.15), smin=0.91, smax=1.09, log=None, name=''):
    """(v4c) mips_relax at each beta from the fold-free U; the result with the lowest anisotropy p95 whose scale p10 /
    p90 stay within [smin, smax] and that neither folds nor overlaps (U itself if none beats it). Returns (U, metrics,
    overlap, the beta or None)"""
    met = BU.chart_metrics(Vc, Fc, U)
    best = (U, met, AU.overlap_texels(U, Fc, px_mm), None)
    for b in betas:
        try:
            U2, _ = mips_relax(Vc, Fc, U, beta=b)
        except ValueError:
            continue
        m2 = BU.chart_metrics(Vc, Fc, U2)
        ok_s = m2['s10'] >= smin and m2['s90'] <= smax
        ov2 = AU.overlap_texels(U2, Fc, px_mm) if (ok_s and m2['flipped'] == 0) else -1
        if log:
            log(f'[uv]   {name}: MIPS beta {b}: aniso95 {m2["aniso95"]:.3f}, scale {m2["s10"]:.3f}-{m2["s90"]:.3f}, '
                f'flipped {m2["flipped"]}, overlap {ov2 if ov2 >= 0 else "-"}')
        if ok_s and m2['flipped'] == 0 and ov2 == 0 and m2['aniso95'] < best[1]['aniso95']:
            best = (U2, m2, 0, b)
    return best


# ============================================================================================ charts, pack, corners
def cap_holes(Vc, Fc):
    """the chart with each HOLE (every boundary loop but the longest) capped by a fan from a centre vertex at the loop's
    mean, wound to match the chart: a disk to flatten, so a hole's free boundary cannot fold over its neighbours (the
    face's eyes, mouth and nostrils overlapped the skin round them, h3 uv 01:2x). Returns (V', F', n_original)"""
    from collections import defaultdict
    directed = {}
    cnt = defaultdict(int)
    for t in Fc.tolist():
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            cnt[(min(a, b), max(a, b))] += 1
            directed[(a, b)] = True
    bedges = [(a, b) for (a, b) in directed if cnt[(min(a, b), max(a, b))] == 1]
    nxt = {a: b for a, b in bedges}
    loops, seen = [], set()
    for a in nxt:
        if a in seen:
            continue
        lp, v = [], a
        while v not in seen:
            seen.add(v)
            lp.append(v)
            v = nxt.get(v, a)
            if v == a:
                break
        loops.append(lp)
    if len(loops) <= 1:
        return Vc, Fc, len(Vc)
    length = lambda lp: float(np.linalg.norm(Vc[lp] - Vc[np.roll(lp, -1)], axis=1).sum())     # noqa: E731
    outer = max(loops, key=length)
    V2, F2 = [Vc], [Fc]
    n = len(Vc)
    for lp in loops:
        if lp is outer:
            continue
        c = n
        n += 1
        V2.append(Vc[lp].mean(0, keepdims=True))
        # each boundary edge runs a -> b in its chart triangle: the cap's triangle runs b -> a
        F2.append(np.array([[nxt[a], a, c] for a in lp], np.int64))
    return np.vstack(V2), np.vstack(F2), len(Vc)


def unwrap_repair(Vc, Fc, rings=2):
    """axolotl_uv.unwrap with the holes capped (cap_holes) and a local repair: LSCM; where it flips a few triangles (a
    hole's concave corner: the mouth's, an inner eye corner's) those triangles' vertices and `rings` rings round them
    relaxed by the house's pinned ARAP (stag_beetle_uv.arap_pinned, the rest pinned), then the injective ARAP over the
    whole chart; the caps dropped. Returns (UV of the chart's vertices, why): why '' when flip-free"""
    Vo, Fo = Vc, Fc
    Vc, Fc, n0 = cap_holes(Vo, Fo)
    U, why = _unwrap_repair(Vc, Fc, rings)
    return U[:n0], why


def _unwrap_repair(Vc, Fc, rings=2):
    U = BU.lscm_direct(Vc, Fc)
    sa = AU.signed_area(U, Fc)
    if sa.sum() < 0:
        U[:, 0] = -U[:, 0]
        sa = -sa
    for _ in range(3):
        flipped = np.nonzero(sa <= 0)[0]
        if not len(flipped):
            break
        nb = collections.defaultdict(set)
        for t in Fc.tolist():
            for a in t:
                nb[a] |= set(t)
        free = set(Fc[flipped].ravel().tolist())
        for _ in range(rings):
            nx = set()
            for v in free:
                nx |= nb[v]
            free |= nx
        pin = np.array(sorted(set(range(len(Vc))) - free), np.int64)
        U = BU.arap_pinned(Vc, Fc, U, pin, U[pin], iters=40)
        sa = AU.signed_area(U, Fc)
        rings += 1
    if (sa <= 0).any():
        return U, f'LSCM flipped {int((sa <= 0).sum())} after the repair'
    U, _ = AU.arap_injective(Vc, Fc, U)
    return U, ''


def face_chart(V, Q, faces, seams, gnm, px_mm, log=print, name='face'):
    """(v4) the FACE whole: GNM's artists' layout as the fold-free start (each split vertex its quads' GNM corner UV,
    scaled to the island's area), relaxed by slim() with its hole scaffold (the eyes, the mouth, the nostrils). Probe
    p25 (F): GNM raw aniso95 1.975, scale 0.77-1.16; the house's injective ARAP from it moved 1.7 %; LSCM flipped 188
    (the nostrils' crescent holes); SLIM + scaffold 1.454, scale 0.908-1.072, 0 overlaps"""
    Vc, Fc, orig, Qc, fq = BU._sub(V, Q, faces, seams)
    acc = np.zeros((len(Vc), 2))
    cnt = np.zeros(len(Vc))
    for j, qi in enumerate(np.asarray(faces).tolist()):
        for k in range(4):
            if not np.isnan(gnm['quv'][qi, k, 0]):
                acc[int(Qc[j][k])] += gnm['quv'][qi, k]
                cnt[int(Qc[j][k])] += 1
    if (cnt == 0).any():
        raise ValueError(f'{name}: {int((cnt == 0).sum())} split vertices have no GNM UV')
    U = acc / cnt[:, None]
    sa = AU.signed_area(U, Fc)
    U *= np.sqrt(AU.tri_area(Vc, Fc).sum() / max(np.abs(sa).sum(), 1e-30))
    if (AU.signed_area(U, Fc) <= 0).any():
        raise ValueError(f'{name}: GNM\'s layout folds {int((AU.signed_area(U, Fc) <= 0).sum())} triangles here')
    U, hist = slim(Vc, Fc, U, iters=80, scaffold_w=FACE_SCAFFOLD_W)
    met = BU.chart_metrics(Vc, Fc, U)
    ov = AU.overlap_texels(U, Fc, px_mm)
    note = '' if AU.chart_ok(met, ov) else (f'kept whole past the soft bars (SLIM from GNM\'s layout: aniso '
                                             f'{met["aniso95"]:.3f}, scale {met["s10"]:.3f}-{met["s90"]:.3f})')
    log(f'[uv]   {name}: GNM\'s layout + SLIM ({len(hist) - 1} iterations, energy {hist[0]:.3f} -> {hist[-1]:.3f}): '
        f'aniso95 {met["aniso95"]:.3f}, scale {met["s10"]:.3f}-{met["s90"]:.3f}, flipped {met["flipped"]}, overlap {ov}')
    if met['flipped'] or ov:
        raise ValueError(f'{name}: the SLIM face chart folds ({met["flipped"]}) or overlaps ({ov})')
    U3, met3, ov3, b3 = best_shape(Vc, Fc, U, px_mm)
    if b3 is not None:
        log(f'[uv]   {name}: MIPS (beta {b3}): aniso95 {met["aniso95"]:.3f} -> {met3["aniso95"]:.3f}, scale '
            f'{met3["s10"]:.3f}-{met3["s90"]:.3f}')
        U, met, ov = U3, met3, ov3
        note = '' if AU.chart_ok(met, ov) else (f'kept whole past the soft bars (GNM\'s layout + SLIM + MIPS: aniso '
                                                 f'{met["aniso95"]:.3f}, scale {met["s10"]:.3f}-{met["s90"]:.3f})')
    return [dict(faces=np.asarray(faces), Vc=Vc, Fc=Fc, orig=orig, Qc=Qc, fq=fq, uv=U, metrics=met, overlap=ov,
                 steps=None, note=note)]


PINCH_TRIS = 16             # (v6) a chart's overlap this small is a local pinch: charts_human cuts it out, not the island


def overlap_tris(U, F, px):
    """the triangles of a chart that share a texel with another (a raster at px texels per unit, inset barycentrics, so
    triangles sharing an edge never count): axolotl_uv.overlap_texels' test, naming the triangles"""
    T = (U - U.min(0)) * px
    owner = {}
    bad = set()
    for t in range(len(F)):
        a, b, c = T[F[t]]
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-14:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        ins = (l0 > 1e-4) & (l1 > 1e-4) & (1.0 - l0 - l1 > 1e-4)
        for k in zip(gx[ins].astype(int).tolist(), gy[ins].astype(int).tolist()):
            if k in owner:
                bad |= {owner[k], t}
            else:
                owner[k] = t
    return sorted(bad)


def charts_human(V, Q, faces, seams, hidden, px_mm, log=print, name=''):
    """one island's charts: whole when unwrap_repair passes the house's hard bars (axolotl_uv.chart_hard_ok: no flip, no
    overlap, anisotropy and scale within its hard limits), else the house's own splitting (axolotl_uv.charts_for).
    (v4) A flip-free chart past the SOFT bars is relaxed by slim() from itself and kept when that lowers its anisotropy
    without an overlap. (v6) A LOCAL PINCH: when a flip-free chart fails on an overlap of a few triangles, only their quads
    come out as their own small charts and the rest is charted whole. The house's splitter bisects the whole island to chase
    such a spot: the woman's foot, 7 triangles between its little toe and its sole, went to 9 charts"""
    Vc, Fc, orig, Qc, fq = BU._sub(V, Q, faces, seams)
    U, why = unwrap_repair(Vc, Fc)
    if not why:
        met = BU.chart_metrics(Vc, Fc, U)
        ov = AU.overlap_texels(U, Fc, px_mm)
        if met['flipped'] == 0 and not AU.chart_ok(met, ov):
            try:
                U2, hist = slim(Vc, Fc, U, iters=60)
                met2 = BU.chart_metrics(Vc, Fc, U2)
                ov2 = AU.overlap_texels(U2, Fc, px_mm)
                log(f'[uv]   {name}: SLIM from the injective ARAP: aniso95 {met["aniso95"]:.3f} -> {met2["aniso95"]:.3f}, '
                    f'scale {met2["s10"]:.3f}-{met2["s90"]:.3f}, flipped {met2["flipped"]}, overlap {ov2}')
                # (v4b) the hard bars first (a SLIM chart that clears an overlap wins even at a slightly higher
                # anisotropy: trunk_up_F 1.340 with 21 texels doubled against 1.351 clean), then the anisotropy
                rank = lambda m_, o_: (not AU.chart_hard_ok(m_, o_), m_['aniso95'])     # noqa: E731
                if met2['flipped'] == 0 and ov2 == 0 and rank(met2, ov2) < rank(met, ov):
                    U, met, ov = U2, met2, ov2
            except ValueError as ex:
                log(f'[uv]   {name}: SLIM skipped ({ex})')
            if met['flipped'] == 0 and ov == 0 and not AU.chart_ok(met, ov):
                U3, met3, ov3, b3 = best_shape(Vc, Fc, U, px_mm)
                if b3 is not None:
                    log(f'[uv]   {name}: MIPS (beta {b3}): aniso95 {met["aniso95"]:.3f} -> {met3["aniso95"]:.3f}, scale '
                        f'{met3["s10"]:.3f}-{met3["s90"]:.3f}')
                    U, met, ov = U3, met3, ov3
        if AU.chart_hard_ok(met, ov):
            soft = AU.chart_ok(met, ov)
            note = '' if soft else (f'kept whole past the soft bars (aniso {met["aniso95"]:.3f}, scale {met["s10"]:.3f}-'
                                    f'{met["s90"]:.3f})')
            if note:
                log(f'[uv]   {name}: a {len(faces)}-face chart {note}')
            return [dict(faces=np.asarray(faces), Vc=Vc, Fc=Fc, orig=orig, Qc=Qc, fq=fq, uv=U, metrics=met, overlap=ov,
                         steps=None, note=note)]
        bad = overlap_tris(U, Fc, px_mm) if (ov and met['flipped'] == 0) else []
        if 0 < len(bad) <= PINCH_TRIS:
            f_arr = np.asarray(faces, np.int64)
            cut = sorted({int(f_arr[int(np.asarray(fq)[t])] ) for t in bad})
            rest = np.setdiff1d(f_arr, np.array(cut, np.int64))
            em = quad_edge_map(Q)
            patches = components(Q, np.array(cut, np.int64), seams, em)
            if len(components(Q, rest, seams, em)) == 1:
                log(f'[uv]   {name}: a local pinch, {len(bad)} triangles in {len(cut)} quads (overlap {ov}): those quads '
                    f'out as {len(patches)} small chart(s), the rest whole')
                out = charts_human(V, Q, rest, seams, hidden, px_mm, log=log, name=name)
                for p_ in patches:
                    out += charts_human(V, Q, np.asarray(p_, np.int64), seams, hidden, px_mm, log=log, name=name + ' pinch')
                return out
        log(f'[uv]   {name}: whole after the repair, past the hard bars (aniso {met["aniso95"]:.3f}, scale '
            f'{met["s10"]:.3f}-{met["s90"]:.3f}, overlap {ov}): the house\'s splitting')
    else:
        log(f'[uv]   {name}: {why}: the house\'s splitting')
    return AU.charts_for(V, Q, faces, seams, set(), hidden, px_mm, log=log, name=name)


def chart_all(V, Q, D, px_mm, log=print, gnm=None):
    """the charts of every primary island (not the right copies): per island charts_human's charts (the FACE by
    face_chart when GNM's layout is given); px_mm {set: texels per mm} sizes each chart's own overlap raster"""
    out = {}
    for i, nm in enumerate(D['names']):
        if D['mirror_of'][i] >= 0:
            continue
        faces = np.nonzero(D['isl'] == i)[0]
        if nm == 'face' and gnm is not None:
            out[i] = face_chart(V, Q, faces, D['seams'], gnm, px_mm[D['set'][i]], log=log, name=nm)
            continue
        out[i] = charts_human(V, Q, faces, D['seams'], D['hidden'][i], px_mm[D['set'][i]], log=log, name=nm)
    return out


def min_rect_angle(P):
    """the turn (radians) that sets a 2-D point set's minimum-area bounding rectangle axis-aligned (rotating calipers on
    its convex hull)"""
    from scipy.spatial import ConvexHull
    try:
        h = P[ConvexHull(P).vertices]
    except Exception:
        return 0.0
    best = (np.inf, 0.0)
    for i in range(len(h)):
        e = h[(i + 1) % len(h)] - h[i]
        a = -np.arctan2(e[1], e[0])
        c, s = np.cos(a), np.sin(a)
        q = h @ np.array([[c, -s], [s, c]]).T
        ar = np.ptp(q[:, 0]) * np.ptp(q[:, 1])
        if ar < best[0]:
            best = (ar, a)
    return best[1]


def raster_mask(uvt, F, pad, ds):
    """an island's occupancy at 1/ds of the texel grid: its triangles rasterised at texel resolution (PIL, edges
    included), dilated by a disk of radius pad (+1 texel of margin for the edge texels), any texel of a cell marking it.
    Returns (mask, the texel offset that places uvt at its origin)"""
    from PIL import Image as _I, ImageDraw as _D
    from scipy import ndimage as nd
    r = pad + 1
    T = uvt - uvt.min(0) + r
    W = int(np.ceil((T[:, 0].max() + r + 1) / ds)) * ds
    H = int(np.ceil((T[:, 1].max() + r + 1) / ds)) * ds
    im = _I.new('L', (W, H), 0)
    dr = _D.Draw(im)
    for t in T[np.asarray(F)]:
        dr.polygon([tuple(p) for p in t], fill=255, outline=255)
    m = np.asarray(im) > 0
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    m = nd.binary_dilation(m, structure=(xx ** 2 + yy ** 2) <= r * r + 0.5)
    return m.reshape(H // ds, ds, W // ds, ds).any((1, 3)), T - uvt


def pack_contact(islands, size=SIZE, ds=4, order=None, cache=None, bias=0.0):
    """(v5, H3b) THE PACK: islands (dict uvt texels, F, pad) largest first, each in the four quarter turns of its
    minimum-area rectangle's orientation; every feasible position (FFT correlation of the occupancy with the island's
    dilated mask, no overlap) scored by the share of the island's outline that touches occupied cells or the page's
    edge (max contact, then bottom-left). On H3's own BODY charts it packs 3,256 px/m where the house's bottom-left pack
    with two turns packed 3,052 (h3b forge scratch q03; extra angles and mirror flips did not help). Returns (per island
    dict(uv page 0..1, angle), the occupancy) or (None, occupancy) when an island does not fit.
    (v6) order: the placement order (default largest box first); cache: a dict that keeps each island's four turned
    masks and their transforms between orders at one density (the masks are most of the cost). An island that fits
    in none of its four turns is tried at every 15 degrees before the pack gives up: a jagged island (the foot with its toe
    webs) can have room that no quarter turn of its bounding box reaches. bias: a pull toward the page's origin added to
    the contact score, which keeps the free space in one piece where contact alone scatters large islands"""
    from scipy import ndimage as nd
    G = size // ds
    occ = np.zeros((G, G), np.float32)
    if order is None:
        order = sorted(range(len(islands)), key=lambda i: -float(np.ptp(islands[i]['uvt'][:, 0]) *
                                                                 np.ptp(islands[i]['uvt'][:, 1])))
    out = [None] * len(islands)
    ring_s = np.ones((3, 3), bool)
    cache = {} if cache is None else cache
    for i in order:
        it = islands[i]
        Bp = np.pad(occ, 1, constant_values=1.0)
        FO = np.fft.rfft2(occ)
        FB = np.fft.rfft2(Bp)
        best = None
        for k in range(28):
            if k == 4 and best is not None:
                break
            if k >= 4 and (k - 4) % 6 == 0:
                continue                                       # (the extra angles, 15 degree steps; the quarter turns are done)
            if (i, k) not in cache:
                a = min_rect_angle(it['uvt']) + (k * np.pi / 2 if k < 4 else (k - 4) * np.pi / 12)
                c, s = np.cos(a), np.sin(a)
                P = it['uvt'] @ np.array([[c, -s], [s, c]]).T
                m, off = raster_mask(P, it['F'], it['pad'], ds)
                h, w = m.shape
                if h > G or w > G:
                    cache[(i, k)] = None
                else:
                    mp = np.pad(m, 1)
                    ring = nd.binary_dilation(mp, structure=ring_s) & ~mp
                    cache[(i, k)] = (a, P, off, m, np.fft.rfft2(m.astype(np.float32), s=(G, G)),
                                     np.fft.rfft2(ring.astype(np.float32), s=(G + 2, G + 2)), max(int(ring.sum()), 1))
            if cache[(i, k)] is None:
                continue
            a, P, off, m, Fm, Fr, n_ring = cache[(i, k)]
            h, w = m.shape
            ov = np.fft.irfft2(FO * np.conj(Fm), s=(G, G))[:G - h + 1, :G - w + 1]
            feas = ov < 0.5
            if not feas.any():
                continue
            ct = np.fft.irfft2(FB * np.conj(Fr), s=(G + 2, G + 2))[:G - h + 1, :G - w + 1]
            sc_map = np.where(feas, ct, -1.0) / n_ring
            if bias > 0.0:
                gy, gx = np.mgrid[0:sc_map.shape[0], 0:sc_map.shape[1]]
                sc_map = np.where(feas, sc_map - bias * (gx + gy) / (2.0 * G), -9.0)
            ys, xs = np.nonzero(sc_map >= sc_map.max() - 1e-6)
            j = np.lexsort((xs, ys))[0]
            y, x = int(ys[j]), int(xs[j])
            sc = (float(sc_map[y, x]), -y * G - x)
            if best is None or sc > best[0]:
                best = (sc, y, x, a, m, P + off)
        if best is None:
            cache.setdefault('failed', collections.Counter())[i] += 1
            return None, float(occ.mean())
        _, y, x, a, m, T = best
        occ[y:y + m.shape[0], x:x + m.shape[1]] = np.maximum(occ[y:y + m.shape[0], x:x + m.shape[1]], m)
        out[i] = dict(page=0, uv=(T + np.array([x * ds, y * ds])) / size, rot=float(a))
    return out, float(occ.mean())


def pack_set(charts, D, which, cap, log=print, tries=7, skip=(), target=None, orders=40):
    """the highest density (px/m at share 1, uv in mm) at which every chart of the set packs one SIZE page, at most cap:
    returns (density, per chart (island, k) its placement, fill). (v5) pack_contact, and since a greedy pack's success
    is not monotonic in the density, after the bisection four densities a little above its best are tried too. skip:
    islands not packed (the stacked copies: their shells are their primaries').
    (v6) target: a density to reach first (the plan's): tried with `orders` placement orders (the largest box first, by
    true area, then the box order with each key jittered log-normally, fixed seeds), then 1 % steps above it while
    they pack and 1 % steps below it until one does; without a target the bisection as before"""
    items = [(i, k, c) for i, cl in charts.items() if D['set'][i] == which and i not in skip for k, c in enumerate(cl)]

    def islands_at(Dn):
        isl = []
        for i, k, c in items:
            uvt = c['uv'] * (Dn / 1000.0) * SHARE[D['cls'][i]]
            th = BU.thickness_texels(uvt - uvt.min(0), c['Fc'])
            isl.append(dict(uvt=uvt - uvt.min(0), F=c['Fc'], pad=int(np.clip(round(th / 8.0), *PAD))))
        return isl

    def attempt(Dn):
        placed, fill = pack_contact(islands_at(Dn), size=SIZE)
        if placed is None:
            return None, None, 'an island did not fit'
        return placed, [fill], ''

    def attempt_orders(Dn):
        isl = islands_at(Dn)
        box = np.array([float(np.ptp(it['uvt'][:, 0]) * np.ptp(it['uvt'][:, 1])) for it in isl])

        def true_area(it):
            d1, d2 = it['uvt'][it['F'][:, 1]] - it['uvt'][it['F'][:, 0]], it['uvt'][it['F'][:, 2]] - it['uvt'][it['F'][:, 0]]
            return float(0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum())
        area = np.array([true_area(it) for it in isl])
        cache = {}
        for j in range(orders):
            if j == 0:
                key = box
            elif j == 1:
                key = area
            else:
                key = box * np.exp(0.35 * np.random.default_rng(100 + j).standard_normal(len(box)))
            bias = (0.0, 0.0, 0.15, 0.4)[j % 4]
            placed, fill = pack_contact(isl, size=SIZE, order=[int(a) for a in np.argsort(-key)], cache=cache, bias=bias)
            if placed is not None:
                log(f'[uv] {which}: at {Dn:.0f} px/m order {j} (bias {bias}) packs, occupancy {fill * 100:.1f} %')
                return placed, [fill]
        worst = [(f'{D["names"][items[i_][0]]}/{items[i_][1]} {int(np.ptp(isl[i_]["uvt"][:, 0]))} x '
                  f'{int(np.ptp(isl[i_]["uvt"][:, 1]))} texels', n_)
                 for i_, n_ in cache.get('failed', collections.Counter()).most_common(4)]
        log(f'[uv] {which}: at {Dn:.0f} px/m no order of {orders} packs; failed on {worst}')
        return None, None
    if target is not None:
        Dn = min(target, cap)
        placed, fill = attempt_orders(Dn)
        if placed is not None:
            best = (Dn, {(i, k): p for (i, k, _), p in zip(items, placed)}, fill)
            while best[0] * 1.01 <= cap:
                Dn = best[0] * 1.01
                placed, fill = attempt_orders(Dn)
                if placed is None:
                    break
                best = (Dn, {(i, k): p for (i, k, _), p in zip(items, placed)}, fill)
            return best
        while Dn > 0.5 * target:
            Dn *= 0.99
            placed, fill = attempt_orders(Dn)
            if placed is not None:
                return Dn, {(i, k): p for (i, k, _), p in zip(items, placed)}, fill
        raise ValueError(f'{which} does not pack one page down to {Dn:.0f} px/m')
    placed, fill, why = attempt(cap)
    if placed is not None:
        log(f'[uv] {which}: packs at the cap {cap:.0f} px/m: occupancy {fill[0] * 100:.1f} %')
        return cap, {(i, k): p for (i, k, _), p in zip(items, placed)}, fill
    lo, hi, best = 0.5 * cap, cap, None
    for _ in range(tries):
        Dn = 0.5 * (lo + hi)
        placed, fill, why = attempt(Dn)
        ok = placed is not None
        log(f'[uv] {which}: at {Dn:.0f} px/m ' + (f'one page, occupancy {fill[0] * 100:.1f} %' if ok else why))
        if ok:
            best = (Dn, {(i, k): p for (i, k, _), p in zip(items, placed)}, fill)
            lo = Dn
        else:
            hi = Dn
    if best is None:
        raise ValueError(f'{which} does not pack one page down to {lo:.0f} px/m')
    for f in (1.004, 1.008, 1.012, 1.016):
        Dn = best[0] * f
        if Dn > cap:
            break
        placed, fill, why = attempt(Dn)
        log(f'[uv] {which}: (above the bisection) at {Dn:.0f} px/m ' +
            (f'one page, occupancy {fill[0] * 100:.1f} %' if placed is not None else why))
        if placed is not None:
            best = (Dn, {(i, k): p for (i, k, _), p in zip(items, placed)}, fill)
    return best


def center_scales(charts, log=print):
    """(v5, H3b) each chart's UVs scaled so its local scale's area-weighted p10 and p90 sit symmetric about 1 (their
    arithmetic midpoint 1, as the band is): the class density gate reads p10 / p90 of the scale against +-10 %, and a
    chart whose spread fits the band but sits off-centre failed it (H3's woman's lids: s10 0.908 / s90 1.099 of a chart
    whose p10 read 0.893 of the target; a geometric centring left them at 0.909 / 1.101). Returns {(island, k): the
    factor}"""
    out = {}
    for i, cl in charts.items():
        for k, c in enumerate(cl):
            a3 = AU.tri_area(c['Vc'], c['Fc'])
            a2 = np.abs(AU.signed_area(c['uv'], c['Fc']))
            ok = a3 > 1e-12
            if ok.sum() < 3:
                continue
            s = np.sqrt(a2[ok] / a3[ok])
            w = a3[ok]
            o = np.argsort(s)
            cw = np.cumsum(w[o])
            p10 = s[o][np.searchsorted(cw, 0.10 * cw[-1])]
            p90 = s[o][min(np.searchsorted(cw, 0.90 * cw[-1]), len(o) - 1)]
            f = 2.0 / max(p10 + p90, 1e-20)
            c['uv'] = c['uv'] * f
            out[(i, k)] = float(f)
    big = sorted(out.items(), key=lambda kv: -abs(np.log(kv[1])))[:5]
    log(f'[uv] the charts\' scales centred: the largest factors ' + ', '.join(f'{i}/{k} x{f:.4f}' for (i, k), f in big))
    return out


def center_classes(charts, D, classes=('lid',), log=print):
    """(v6, H3b) a class's charts scaled by ONE factor so the class's own area-weighted p10 and p90 sit symmetric about 1:
    the gate reads the class, not its charts, and two charts each centred alone can still leave the pair off-centre (the
    woman's lids: p10 / p90 0.909 / 1.101, which fit the +-10 % band only when centred together)"""
    for cls in classes:
        s_all, w_all = [], []
        ids = [i for i in charts if D['cls'][i] == cls]
        for i in ids:
            for c in charts[i]:
                a3 = AU.tri_area(c['Vc'], c['Fc'])
                a2 = np.abs(AU.signed_area(c['uv'], c['Fc']))
                ok = a3 > 1e-12
                s_all.append(np.sqrt(a2[ok] / a3[ok]))
                w_all.append(a3[ok])
        if not s_all:
            continue
        s, w = np.concatenate(s_all), np.concatenate(w_all)
        o = np.argsort(s)
        cw = np.cumsum(w[o])
        p10 = s[o][np.searchsorted(cw, 0.10 * cw[-1])]
        p90 = s[o][min(np.searchsorted(cw, 0.90 * cw[-1]), len(o) - 1)]
        f = 2.0 / max(p10 + p90, 1e-20)
        for i in ids:
            for c in charts[i]:
                c['uv'] = c['uv'] * f
        log(f'[uv] the class {cls}: p10 / p90 {p10:.3f} / {p90:.3f}, all its charts x{f:.4f}')


def quad_diagonals(Q, quv, V):
    """(v5, H3b) per quad the diagonal its two triangles share, False (0-2) or True (1-3): the one whose two UV triangles
    are both positive and the smaller one larger; on a tie the shorter 3-D diagonal (the charts' own split,
    stag_beetle_uv.tris_of). H3 shipped 0-2 everywhere while the charts were solved on the shorter diagonal: 13 UV
    triangles folded where a quad's UV is not convex (the mouth corners, the ear band's folded quads, one toe; the H3
    check: 88 / 45 / 10 doubled texels)"""
    P = np.asarray(quv, np.float64)

    def a2(a, b, c):
        return (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    t012, t023 = a2(P[:, 0], P[:, 1], P[:, 2]), a2(P[:, 0], P[:, 2], P[:, 3])
    t013, t123 = a2(P[:, 0], P[:, 1], P[:, 3]), a2(P[:, 1], P[:, 2], P[:, 3])
    # each quad's own orientation in the layout: its polygon's signed area (either split sums to it; a mirrored right
    # copy's quads run clockwise, its tangent's w -1)
    sign = np.where(t012 + t023 >= 0.0, 1.0, -1.0)
    s02 = np.minimum(t012 * sign, t023 * sign)
    s13 = np.minimum(t013 * sign, t123 * sign)
    d02 = np.linalg.norm(V[Q[:, 0]] - V[Q[:, 2]], axis=1)
    d13 = np.linalg.norm(V[Q[:, 1]] - V[Q[:, 3]], axis=1)
    use13 = np.where((s02 > 0) & (s13 > 0), d13 < d02, s13 > s02)
    return use13


def quad_tris(Q, use13):
    """the two triangles of each quad on its chosen diagonal: (F (2 n, 3) as local corner indices 0..3 per quad, in the
    order quad 0 .. n-1 first triangles, then the second ones)"""
    t1 = np.where(use13[:, None], np.array([0, 1, 3]), np.array([0, 1, 2]))
    t2 = np.where(use13[:, None], np.array([1, 2, 3]), np.array([0, 2, 3]))
    return t1, t2


def similarity_2d(A, B):
    """the 2-D similarity (s R, t) taking A onto B in least squares (a chart's mm layout onto its placed page UVs:
    exact up to rounding); returns a function"""
    ca, cb = A.mean(0), B.mean(0)
    X, Y = A - ca, B - cb
    U, S, Vt = np.linalg.svd(Y.T @ X)
    d = np.sign(np.linalg.det(U @ Vt))
    Dm = np.diag([1.0, d])
    R = U @ Dm @ Vt
    s = float(np.trace(np.diag(S) @ Dm) / max((X ** 2).sum(), 1e-30))
    return lambda P: (s * (np.asarray(P) - ca) @ R.T) + cb


def corner_uvs(Q, D, charts, placed):
    """per quad its 4 corners' UVs (0..1 on its set's page): each primary chart's corners from its placement (the chart's
    split-vertex UVs through its triangles' quads), each right copy's from its mirror quad, corner for corner"""
    quv = np.full((len(Q), 4, 2), np.nan)
    for (i, k), p in placed.items():
        c = charts[i][k]
        uv = p['uv']                                    # the chart's split vertices, page 0..1
        qn = c['Qc']                                    # the chart's quads in its split-vertex ids
        faces = c['faces']                              # the chart's global quads (same order as Qc)
        quv[faces] = uv[qn]
    # the right copies
    key = {frozenset(int(v) for v in q): qi for qi, q in enumerate(Q.tolist())}
    return quv, key


def mirror_corners(Q, mir, D, quv, key):
    """each right copy's corners from its mirror quad's (in place)"""
    for i, m in enumerate(D['mirror_of']):
        if m < 0:
            continue
        for qi in np.nonzero(D['isl'] == i)[0]:
            q = Q[qi]
            ql = key[frozenset(int(mir[v]) for v in q)]
            lq = Q[ql].tolist()
            for k in range(4):
                quv[qi, k] = quv[ql, lq.index(int(mir[q[k]]))]
    return quv
