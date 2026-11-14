"""AX5 (work/bestiary/research/AXOLOTL_PLAN.md §8 and §11's row; CROSSBREED_DESIGN.md §2.4 and §7.1 rule 5): THE
AXOLOTL'S UVs on the accepted AX4 cage (work/bestiary/axolotl/cage_ax04_animal.npz, _fins.npz, _eyes.npz) and AX3's
records (seams.json): one BODY set (4096) and one EYE set (256), every repeat stacked on its largest copy, and the texel
density the pack realises, printed and FROZEN. The step script is work/bestiary/tests/ax05_uv.py.

THE STACKS (AX3's similarity groups; Skye's rule, memory feedback_stack_identical_parts_uvs: "simply repeatedly use the UV
shells for the largest/highest pixel space ones"). A COPY takes its PRIMARY's UVs corner for corner through a vertex
correspondence (copy_faces); only primaries are packed, and only primaries bake (AX7); every copy still occludes.
  - The right limbs on the left. The cage's right limb is the left's exact mirror, vertex for vertex (x -> -x, quads
    reversed), so its triangles land on the left's reversed and the tangent's sign flips (glTF TANGENT w = -1).
  - The six rami's STALKS (graft ring to last ring) on gill_1_L's, the largest. The cage's rami are similar copies of r1
    as SURFACES: their centrelines are similar to 0.005 mm x4 and every ring is a circle. But each ring's vertex 0 follows
    its own port frame (seams.json's ring rule), so against r1's, r2's rings sit rolled -5.85 deg about the stalk and
    r3's -42.1 deg. The correspondence takes the ring-index shift that leaves the least roll (RAMUS_SHIFT): 0 for r2,
    one 30 deg step for r3, leaving 12.07 deg. AX3's seam_k (3 / 3 / 4) is the same choice. On a circular section a
    constant roll maps the tube onto itself, so the copy's surface is the primary's under the similarity and the roll:
    what a stalk bakes from its own shape (normal, cavity, curvature, thickness, height) is right on the copy too. Only
    what depends on the angle round the stalk sits rolled, by up to 12 deg on r3 (an AO from the comb's filaments, if a
    bake carries one). The gates print the roll, the stack map's residual and the clay under it.
  - The rami's tip CAPS. A 3 x 3 grid on a 12-ring has only quarter-turn symmetry, so r3's one-step shift cannot carry
    it. r1_L's cap is the primary for r1 and r2 (r2's shift is 0); r3_L's TIP is r3's own (an island of its own): AX7b,
    its LAST BAND with its cap (the AX7 check found r3's last band, on the ring-shifted stack beside its own cap,
    decoding up to 10.2 deg off and a x1.8 luminance step at the cap's rim: the cap's quarter-turn faces shape the last
    ring's normals, which a 30 deg shift does not carry); the right sides are mirrored.
  - The fins' right faces on their left faces (one pigment layer seen from both sides, plan §8). Each membrane column is
    [the left root .. the left rows, the rim, the right root .. the right rows], the right face the left's exact
    mirror. The rim's shared vertex is split per face, so each face has its own tangent and normal there.
  - The right eyeball on the left, in the EYE set.
  - The 276 filaments on their four templates (axolotl_gills.template_low: plan §5.7's LOD0). Every instance is its
    template turned, scaled and moved (exact), and each template is laid at its LARGEST instance's scale.
  UNIQUE: the body (plan §8: a mirrored seam down a glossy wet back would show).

THE SEAMS (designed; plan §8 and CROSSBREED §2.4: a tube cut is an island boundary, a length seam runs on the kind's
hidden line and meets each ring at its record's seam_k):
  - THE BODY: the ventral midline from the lower lip to the tail tip (ventral_cut: a shortest path hugging x = 0 through
    the poll's, the tail root's and the tail mid's seam_k vertices, all three on the ventral midline); the three body
    rings; the lip loop (the mouth bag is its own island at SHARE['bag']); each eye port's edge ring (the tuck and the
    socket cap under the ball are hidden: SHARE['hidden']); each gill socket's PORT LOOP; the copy rings (the limbs'
    footprints, the rami's graft rings). A gill socket's fillet is a short tube standing out of the head: flattened with
    the trunk, its hole collapsed to a point and the sheet overlapped itself (10-29, the first trial). So each fillet is
    its own strip, cut on the column from its graft ring's seam_k vertex to the port loop.
  - THE LIMBS (left): the footprint ring, the axilla / forearm / hand (groin / shank / foot) rings, AX4's length seam on
    one column (ring_seam_*, through every record's seam_k). The hand (foot) past its ring goes to the chart splitter
    below, with the palmar side as the cheap side.
  - THE RAMUS (r1_L): the graft ring, the column through seam_k to the last ring, and the last ring (the cap's rim);
    r3_L's cap rim too.
  - THE EYE: the visible cap (every face with a corner in front of the port's edge ring) and the hidden back.
THE CHARTS (charts_for): each island is flattened by a direct LSCM (stag_beetle_uv.lscm_direct), then by ARAP whose every
global step is cut back so no triangle's signed area turns negative (arap_injective). Plain ARAP folded the trunk round
its holes from its 4th iteration (10-29). If an island still fails the bars (a flipped triangle, a self-overlap,
anisotropy p95 over CHART_ANISO, the scale's area-weighted p10 / p90 outside +- CHART_SCALE), it first gets hole bridges
(bridge_holes: the cheapest path from each hole to the boundary, over the hidden side), then the beetle's normalised-cut
bisection (stag_beetle_uv.fiedler_split: seams kept; creases and the hidden side cheap), until it passes.
THE PACK (stag_beetle_uv.pack: raster masks, an FFT feasibility scan, bottom-left, quarter turns). Every island is padded
by its thickness / 8 within PAD texels a side (memory feedback_texture_budget_fix_islands_not_sets: an island stops
resolving at mip log2(thickness)), and stacked islands by STACK_PAD times that. THE DENSITY is the highest that packs
on one 4096 page, at most DENSITY_CAP; AX5 freezes it, and every ring record reads it (AX11).
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.sparse.csgraph import connected_components, dijkstra

from .. import uv as UVm
from . import stag_beetle_uv as BU

SIZE = 4096                 # the BODY set
EYE_SIZE = 256              # the EYE set: both eyes stacked, the eye's own material (plan §8)
DENSITY_CAP = 5650.0        # px/m at x4: seams.json's sag records put the poll's worst chord at 1.962 texels and the tail
#                             mid's at 1.959 at 5,560, so both reach the 2-texel bar (plan §6.1) at ~5,667; a margin under it
SHARE = dict(visible=1.0, bag=0.5, hidden=1.0 / 16.0)
#                           (texel density shares: the mouth bag at plan §8's weight 0.25 of area = 0.5 linear, as the
#                           octopus's mouth wall; HIDDEN faces get no texels by the plan, so they take a token 1/16:
#                           valid UVs and tangents, about 1/256 of the area)
CLASSES = ('visible', 'bag', 'hidden')
CHART_ANISO = 1.25          # per chart (area-weighted p95; the layout's gate is p95 <= 1.2): the beetle's B5 bar ...
CHART_SCALE = 0.10          # ... and the local scale's area-weighted p10 / p90 within +-10 % of its mean: REPORTED
CHART_ANISO_HARD = 1.6      # a designed island is split only past these (or on a flip or an overlap): the elbow's and the
CHART_SCALE_HARD = 0.25     # knee's spans miss the soft bars by a little (a bent tube does not unroll without shear), and
#                             splitting them only scattered seams (10-29's first run: 31 forelimb charts); the plan's own
#                             bar is the layout's p95
PAD = (3, 8)                # texels a side: round(thickness / 8) clipped to this (the beetle's B5)
STACK_PAD = 1.5             # stacked islands: more padding (plan §8, the memory's rule)
ARAP_ITERS = 60
VENTRAL_X = 10.0            # the ventral cut's cost per mm x4 off the midline (it stays on x = 0: 10-29's trial)
BRIDGE_UP = 4.0             # a bridge's cost per unit of the edge facing away from the hidden side
RAMUS_K = 12
RAMUS_RINGS = 19            # rings from the graft ring to the last, then the 3 x 3 cap's 4 inner vertices (AX7b: 19, was
#                             18: the bowed stalk's first clean share moved from 0.2425 to 0.17, AX3)
RAMUS_SHIFT = {1: 0, 2: 0, 3: 1}   # each ramus's ring-index shift onto r1's (the least roll: -5.85 deg / +12.07 deg)
EYE_EDGE_MARGIN = 2.0       # deg: a ball face with a corner within this of the port's edge ring (or in front) is the cap


# ============================================================================================ small helpers
def loop_edges(ids):
    ids = [int(i) for i in ids]
    return {(min(a, b), max(a, b)) for a, b in zip(ids, ids[1:] + ids[:1])}


def path_edges(ids):
    ids = [int(i) for i in ids]
    return {(min(a, b), max(a, b)) for a, b in zip(ids[:-1], ids[1:])}


def edge_set(Q):
    d = np.stack([Q, np.roll(Q, -1, axis=1)], -1).reshape(-1, 2)
    return {(min(int(a), int(b)), max(int(a), int(b))) for a, b in d}


def graph(n, E, cost, use=None):
    use = np.ones(len(E), bool) if use is None else use
    return sp.coo_matrix((np.r_[cost[use], cost[use]], (np.r_[E[use, 0], E[use, 1]], np.r_[E[use, 1], E[use, 0]])),
                         shape=(n, n)).tocsr()


def shortest_path(G, a, b):
    """edge list of the cheapest path a -> b (a ValueError when there is none)"""
    dist, pred = dijkstra(G, indices=int(a), return_predecessors=True)
    if not np.isfinite(dist[int(b)]):
        raise ValueError(f'no path {a} -> {b}')
    out, v = [], int(b)
    while v != int(a):
        u = int(pred[v])
        out.append((min(u, v), max(u, v)))
        v = u
    return out[::-1]


def signed_area(U, F):
    d1, d2 = U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]
    return 0.5 * (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])


def tri_area(V, F):
    return 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)


def wq(x, w, q):
    """the area-weighted q-th percentile"""
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][min(np.searchsorted(cw, q / 100.0 * cw[-1]), len(o) - 1)])


# ============================================================================================ ARAP, injective
def _arap_setup(V, F):
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
    return X, np.clip(cot, -1e3, 1e3)


def max_step(U0, U1, F, keep=0.9):
    """the largest alpha in (0, 1] keeping every triangle's signed area positive on U0 + alpha (U1 - U0), given U0 all
    positive (each area is a quadratic in alpha: its first root in (0, 1] bounds the step), times keep when bounded"""
    D = U1 - U0
    p, q = U0[F[:, 1]] - U0[F[:, 0]], U0[F[:, 2]] - U0[F[:, 0]]
    dp, dq = D[F[:, 1]] - D[F[:, 0]], D[F[:, 2]] - D[F[:, 0]]
    cr = lambda u, v: u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]      # noqa: E731
    A, Bq, C = cr(dp, dq), cr(p, dq) + cr(dp, q), cr(p, q)
    alpha = np.ones(len(F))
    lin = np.abs(A) < 1e-14 * np.maximum(np.abs(C), 1e-30)
    with np.errstate(divide='ignore', invalid='ignore'):
        t_lin = -C / Bq
        disc = Bq * Bq - 4.0 * A * C
        sq = np.sqrt(np.maximum(disc, 0.0))
        r1, r2 = (-Bq - sq) / (2.0 * A), (-Bq + sq) / (2.0 * A)
    m = lin & (Bq < 0) & (t_lin > 0)
    alpha[m] = np.minimum(alpha[m], t_lin[m])
    qd = ~lin & (disc >= 0)
    for r in (r1, r2):
        mm = qd & (r > 0) & (r <= 1.0)
        alpha[mm] = np.minimum(alpha[mm], r[mm])
    am = float(alpha.min())
    return 1.0 if am >= 1.0 else keep * am


def arap_injective(V, F, UV, iters=ARAP_ITERS, tol=1e-8):
    """ARAP (Liu et al. 2008; uv.arap's local and global steps, cotangent weights) from a fold-free start, every global
    step cut back to the largest share that keeps each triangle's signed area positive. The energy still falls: for the
    new rotations it is convex in U, so a point on the segment from the old solution to the new one is no worse than the
    old. Returns (UV, the step shares taken)"""
    n = len(V)
    X, cot = _arap_setup(V, F)
    rows, cols, vals = [], [], []
    for c in range(3):
        a, b = (c + 1) % 3, (c + 2) % 3
        w = 0.5 * cot[:, c]
        rows += [F[:, a], F[:, b], F[:, a], F[:, b]]
        cols += [F[:, b], F[:, a], F[:, a], F[:, b]]
        vals += [-w, -w, w, w]
    L = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tolil()
    L[0, :] = 0
    L[0, 0] = 1.0
    solve = spla.factorized(L.tocsc())
    U = UV.copy()
    steps = []
    for _ in range(iters):
        S = np.zeros((len(F), 2, 2))
        for c in range(3):
            a, b = (c + 1) % 3, (c + 2) % 3
            S += 0.5 * cot[:, c, None, None] * (U[F[:, a]] - U[F[:, b]])[:, :, None] * (X[:, a] - X[:, b])[:, None, :]
        Uu, _, Vt = np.linalg.svd(S)
        flip = np.linalg.det(Uu @ Vt) < 0
        Uu[flip, :, 1] *= -1
        R = Uu @ Vt
        bx = np.zeros((n, 2))
        for c in range(3):
            a, b = (c + 1) % 3, (c + 2) % 3
            rd = np.einsum('fij,fj->fi', R, X[:, a] - X[:, b]) * (0.5 * cot[:, c])[:, None]
            np.add.at(bx, F[:, a], rd)
            np.add.at(bx, F[:, b], -rd)
        bx[0] = U[0]
        U1 = np.column_stack([solve(bx[:, 0]), solve(bx[:, 1])])
        al = max_step(U, U1, F)
        Un = U + al * (U1 - U)
        mv = float(np.abs(Un - U).max())
        U = Un
        steps.append(al)
        if mv < tol * max(float(np.abs(U).max()), 1e-12):
            break
    return U, steps


def unwrap(Vc, Fc):
    """LSCM, oriented counter-clockwise, then the injective ARAP. Returns (UV in V's units, steps or None, why)"""
    U = BU.lscm_direct(Vc, Fc)
    sa = signed_area(U, Fc)
    if sa.sum() < 0:
        U[:, 0] = -U[:, 0]
        sa = -sa
    if (sa <= 0).any():
        return U, None, f'LSCM flipped {int((sa <= 0).sum())}'
    U, steps = arap_injective(Vc, Fc, U)
    return U, steps, ''


def overlap_texels(U, F, px_per_unit):
    """the chart's self-overlap rasterised at about its own texel size (at most 2048 across)"""
    ext = float((U.max(0) - U.min(0)).max()) * px_per_unit
    return UVm.self_overlap(U, F, res=int(np.clip(ext, 128, 2048)))


def chart_ok(met, ov):
    """the soft bars (reported)"""
    return (met['flipped'] == 0 and ov == 0 and met['aniso95'] <= CHART_ANISO and met['s10'] >= 1.0 - CHART_SCALE
            and met['s90'] <= 1.0 + CHART_SCALE)


def chart_hard_ok(met, ov):
    """the bars a designed island must pass to stay whole: no flip, no overlap, not far past the soft bars"""
    return (met['flipped'] == 0 and ov == 0 and met['aniso95'] <= CHART_ANISO_HARD and
            met['s10'] >= 1.0 - CHART_SCALE_HARD and met['s90'] <= 1.0 + CHART_SCALE_HARD)


def face_components(Qs, cut=frozenset()):
    """the connected components of the quads Qs over shared edges not in cut: a list of index arrays into Qs"""
    m = len(Qs)
    E, QE, ef = BU.quad_edges(Qs)
    inner = (ef[:, 1] >= 0) & np.array([(int(a), int(b)) not in cut for a, b in E])
    G = sp.coo_matrix((np.ones(int(inner.sum())), (ef[inner, 0], ef[inner, 1])), shape=(m, m))
    nc, lab = connected_components(G, directed=False)
    return [np.nonzero(lab == k)[0] for k in range(nc)]


def boundary_edges(Qs):
    """the edges used by one quad of Qs only"""
    E, _, ef = BU.quad_edges(Qs)
    return {(int(a), int(b)) for a, b in E[ef[:, 1] < 0]}


def hidden_cost(V, Qs, hidden):
    """per edge of Qs (BU.quad_edges' order): its length x (1 + BRIDGE_UP x how much it faces away from the hidden side)"""
    E, _, ef = BU.quad_edges(Qs)
    fn, _ = BU.quad_normals(V, Qs)
    en = fn[ef[:, 0]] + np.where(ef[:, 1:2] >= 0, fn[np.maximum(ef[:, 1], 0)], 0.0)
    en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-20)
    h = np.asarray(hidden, np.float64) / np.linalg.norm(hidden)
    return E, ef, np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * (1.0 + BRIDGE_UP * np.clip(-(en @ h), 0.0, 1.0))


# ============================================================================================ the designed seams
def ventral_cut(V, Q, bid, B, rec, part, regions):
    """the body's ventral cut: the cheapest edge path, hugging x = 0 (VENTRAL_X), from the lower lip's midline vertex
    through the poll's, the tail root's and the tail mid's seam_k vertices to the tail's tip vertex, over body vertices
    outside the mouth bag. Returns (edges, the stops)"""
    n = len(V)
    E, _, _ = BU.quad_edges(Q)
    L = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    body = np.zeros(n, bool)
    body[bid] = True
    lip = [int(bid[i]) for i in B['mouth_loop'] if abs(V[bid[i], 0]) < 1e-6]
    lip_lo = min(lip, key=lambda v: V[v, 1])
    stops = [lip_lo] + [int(bid[B[f'ring_{k}'][rec[k]['seam_k']]]) for k in ('poll', 'tail_root', 'tail_mid')]
    mid = body & (np.abs(V[:, 0]) < 1e-3)
    stops.append(int(np.nonzero(mid)[0][np.argmin(V[mid, 2])]))
    ok = body & (part != regions.index('body_mouth'))
    ok[lip_lo] = True
    G = graph(n, E, L * (1.0 + VENTRAL_X * np.abs(V[E, 0]).mean(1)), ok[E[:, 0]] & ok[E[:, 1]])
    cut = []
    for a, b in zip(stops[:-1], stops[1:]):
        cut += shortest_path(G, a, b)
    return cut, stops


def body_seams(V, Q, bid, B, rec, part, regions):
    """the body's designed seams on the welded animal (V: x4 mm). Returns (seams, info): info['ventral'], the stops,
    info['sockets'] {name: dict(faces, cut)}, info['hidden_faces'] (each eye's tuck and socket cap)"""
    cut, stops = ventral_cut(V, Q, bid, B, rec, part, regions)
    S = set(cut)
    for k in ('ring_poll', 'ring_tail_root', 'ring_tail_mid'):
        S |= loop_edges(bid[B[k]])
    S |= loop_edges(bid[B['mouth_loop']])
    hidden = []
    for s in 'LR':
        S |= loop_edges(bid[B[f'port_eye_{s}_edge']])
        inner = set(bid[np.concatenate([B[f'port_eye_{s}_edge'], B[f'port_eye_{s}_tuck'], B[f'port_eye_{s}_cap']])].tolist())
        deep = set(bid[np.concatenate([B[f'port_eye_{s}_tuck'], B[f'port_eye_{s}_cap']])].tolist())
        hidden += [f for f in range(len(Q)) if set(Q[f].tolist()) <= inner and set(Q[f].tolist()) & deep]
    for nm in ('gill_1_L', 'gill_1_R', 'gill_2_L', 'gill_2_R', 'gill_3_L', 'gill_3_R', 'limb_fore_L', 'limb_fore_R',
               'limb_hind_L', 'limb_hind_R'):
        S |= loop_edges(bid[B[f'copy_{nm}']])
    # the gill sockets: each fillet its own strip, cut on the column from its graft ring's seam_k vertex to the port loop
    n = len(V)
    sockets = {}
    for nm in ('gill_1_L', 'gill_1_R', 'gill_2_L', 'gill_2_R', 'gill_3_L', 'gill_3_R'):
        loop = bid[B[f'port_{nm}_loop']]
        S |= loop_edges(loop)
        rings = np.concatenate([B[f'port_{nm}_{k}'] for k in ('loop', 'fillet_0', 'fillet_1', 'copy')])
        own = set(bid[rings].tolist())
        faces = np.array([f for f in range(len(Q)) if set(Q[f].tolist()) <= own])
        i_seam = int(np.nonzero(B[f'copy_{nm}_match'] == rec[nm]['seam_k'])[0][0])
        start = int(bid[B[f'copy_{nm}'][i_seam]])
        Es = np.array(sorted(edge_set(Q[faces]) - loop_edges(loop) - loop_edges(bid[B[f'copy_{nm}']])))
        G = graph(n, Es, np.linalg.norm(V[Es[:, 0]] - V[Es[:, 1]], axis=1))
        dist = dijkstra(G, indices=start)
        end = int(loop[np.argmin(dist[loop])])
        cut_s = shortest_path(G, start, end)
        S |= set(cut_s)
        sockets[nm] = dict(faces=faces, cut=cut_s, start=start)
    return S, dict(ventral=cut, stops=stops, sockets=sockets, hidden_faces=np.array(sorted(set(hidden))))


def limb_seams(V, FL, HL, off, down=(0.0, -1.0, 0.0)):
    """the left limbs' designed seams (animal ids: off['fore'], off['hind'] the files' offsets): the footprint, the three
    graft rings, AX4's length seam (one column through every record's seam_k). THE HAND (FOOT) past its ring: each digit
    its own island, cut off at its base (the web quads between the digits, every corner on the end ring, stay with the
    palm) and down its palmar column (the cheapest path over the side facing down) from its base's lowest vertex to its
    tip; the palm cut on its palmar side from the hand ring's seam vertex (AX4's seam path's end) to the nearest digit
    base. Returns (seams, info)"""
    S, info = set(), {}
    for Z, kind, rings in ((FL, 'fore', ('axilla', 'forearm', 'hand')), (HL, 'hind', ('groin', 'shank', 'foot'))):
        o = off[kind]
        S |= loop_edges(Z[f'ring_footprint_{kind}_L'] + o)
        for r in rings:
            S |= loop_edges(Z[f'ring_{r}_L'] + o)
        path = Z[f'ring_seam_{kind}_L'] + o
        S |= path_edges(path)
        pod_ring = Z[f'ring_{rings[-1]}_L'] + o
        assert int(path[-1]) in set(pod_ring.tolist()), 'AX4\'s seam path ends on the hand (foot) ring'
        # the autopod: the faces past the hand ring (its component over every edge but the ring's)
        QL = Z['Q'][:len(Z['Q']) // 2] + o
        regs = [str(r) for r in Z['regions']]
        part = Z['part'].argmax(1)
        fr = np.array([np.bincount(part[q - o], minlength=len(regs)).argmax() for q in QL])
        pod = (fr == regs.index('palm')) | (fr == regs.index('digit'))
        comps = face_components(QL[pod], loop_edges(pod_ring))
        end = set((Z[f'ring_end_{kind}_L'] + o).tolist())
        pod_f = np.nonzero(pod)[0]
        pod_f = pod_f[max(comps, key=lambda c: int((fr[pod_f[c]] == regs.index('digit')).sum()))]
        dig = pod_f[fr[pod_f] == regs.index('digit')]
        web = np.array([f for f in dig if set(QL[f].tolist()) <= end], np.int64)
        dig = np.setdiff1d(dig, web)
        digits = []
        for comp in face_components(QL[dig]):
            fs = dig[comp]
            base = boundary_edges(QL[fs])
            S |= base
            bv = np.unique(np.array(sorted(base)).ravel())
            vs = np.unique(QL[fs].ravel())
            tip = int(vs[np.argmax(np.linalg.norm(V[vs] - V[bv].mean(0), axis=1))])
            E, ef, cost = hidden_cost(V, QL[fs], down)
            use = np.array([(int(a), int(b)) not in base for a, b in E])
            inner = np.unique(E[use].ravel())
            cand = bv[np.isin(bv, inner)]           # (a base corner with only base edges has no way into the digit)
            start = int(cand[np.argmin(V[cand, 1])])
            cut = shortest_path(graph(len(V), E, cost, use), start, tip)
            S |= set(cut)
            digits.append(dict(base=bv, cut=cut, tip=tip))
        palm = np.setdiff1d(pod_f, dig)
        E, ef, cost = hidden_cost(V, QL[palm], down)
        bases = set().union(*[set(d['base'].tolist()) for d in digits])
        ban = loop_edges(pod_ring)
        use = np.array([(int(a), int(b)) not in ban for a, b in E])
        dist = dijkstra(graph(len(V), E, cost, use), indices=int(path[-1]))
        bl = np.array(sorted(bases))
        end_v = int(bl[np.argmin(dist[bl])])
        pcut = shortest_path(graph(len(V), E, cost, use), int(path[-1]), end_v)
        S |= set(pcut)
        info[kind] = dict(seam=path, rings={r: Z[f'ring_{r}_L'] + o for r in rings},
                          footprint=Z[f'ring_footprint_{kind}_L'] + o, digits=digits, palm_cut=pcut,
                          webs=len(web))
    return S, info


def ramus_seams(off_r1, off_r3, seam_k):
    """r1_L's stalk: the graft ring, the length seam on column seam_k, the cap's rim; r3_L's TIP's rim (AX7b: one ring
    before the cap, so r3's last band is its own with the cap; before, the cap's rim)"""
    K, n = RAMUS_K, RAMUS_RINGS
    S = loop_edges(off_r1 + np.arange(K))
    S |= path_edges(off_r1 + np.arange(n) * K + seam_k)
    S |= loop_edges(off_r1 + (n - 1) * K + np.arange(K))
    S |= loop_edges(off_r3 + (n - 2) * K + np.arange(K))
    return S


# ============================================================================================ the copies
def copy_faces(Q, prim_faces, phi):
    """for each primary face the copy face whose corners are phi of the primary's, and the corner map: the copy's corner
    j takes the primary's corner cmap[j]. phi: a vertex map over the combined mesh (-1 off the primary)"""
    key = {}
    for i, q in enumerate(Q.tolist()):
        key.setdefault(tuple(sorted(q)), i)
    cf, cm = [], []
    for f in prim_faces:
        img = phi[Q[f]]
        if (img < 0).any():
            raise ValueError(f'face {f}: a corner has no image')
        g = key[tuple(sorted(img.tolist()))]
        cf.append(g)
        cm.append([int(np.nonzero(img == v)[0][0]) for v in Q[g]])
    return np.array(cf, np.int64), np.array(cm, np.int64)


def ramus_phi(n_total, off_src, off_dst, shift, rings=True, cap_inner=True):
    """the vertex map of one ramus onto another (local index r * K + c -> r * K + (c + shift) % K; the cap's inner
    vertices identity, valid only for shift 0)"""
    phi = -np.ones(n_total, np.int64)
    K, n = RAMUS_K, RAMUS_RINGS
    if rings:
        r, c = np.divmod(np.arange(n * K), K)
        phi[off_src + np.arange(n * K)] = off_dst + r * K + (c + shift) % K
    if cap_inner:
        assert shift == 0, 'the cap cannot follow a ring shift that is not a quarter turn'
        phi[off_src + n * K + np.arange(4)] = off_dst + n * K + np.arange(4)
    return phi


# ============================================================================================ the charts
def boundary_loops(V, Qs, seams):
    """the split chart's boundary loops in original vertex ids: edges with one face in the set, and seam edges inside"""
    E, _, ef = BU.quad_edges(Qs)
    b = ef[:, 1] < 0
    inner = np.array([(int(a), int(c)) in seams for a, c in E]) & ~b
    be = E[b | inner]
    if not len(be):
        return []
    n = len(V)
    _, lb = connected_components(sp.coo_matrix((np.ones(len(be)), (be[:, 0], be[:, 1])), shape=(n, n)), directed=False)
    out = {}
    for v in np.unique(be.ravel()):
        out.setdefault(int(lb[v]), []).append(int(v))
    return list(out.values())


def bridge_holes(V, Q, faces, seams, hidden):
    """connect every hole of the chart to its outer boundary (the longest loop): repeatedly the cheapest interior path,
    cost = length x (1 + BRIDGE_UP x how much the edge faces away from the hidden side). Returns the new seam edges"""
    Qs = Q[faces]
    E, _, ef = BU.quad_edges(Qs)
    fn, _ = BU.quad_normals(V, Qs)
    en = fn[ef[:, 0]] + np.where(ef[:, 1:2] >= 0, fn[np.maximum(ef[:, 1], 0)], 0.0)
    en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-20)
    h = np.zeros(3) if hidden is None else np.asarray(hidden, np.float64) / np.linalg.norm(hidden)
    cost = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) * (1.0 + BRIDGE_UP * np.clip(-(en @ h), 0.0, 1.0))
    ss, added = set(seams), set()
    while True:
        loops = boundary_loops(V, Qs, ss)
        if len(loops) <= 1:
            return added
        outer = max(loops, key=len)
        interior = (ef[:, 1] >= 0) & np.array([(int(a), int(c)) not in ss for a, c in E])
        G = graph(len(V), E, cost, interior)
        dist, pred, _ = dijkstra(G, indices=outer, return_predecessors=True, min_only=True)
        best = None
        for lp in loops:
            if lp is outer:
                continue
            lp = np.asarray(lp)
            k = int(lp[np.argmin(dist[lp])])
            if np.isfinite(dist[k]) and (best is None or dist[k] < best[0]):
                best = (dist[k], k)
        if best is None:
            return added
        v = best[1]
        while pred[v] >= 0:
            u = int(pred[v])
            e = (min(u, v), max(u, v))
            ss.add(e)
            added.add(e)
            v = u


def charts_for(V, Q, faces, seams, sharp, hidden, px_per_unit, log=print, name='', max_depth=12, min_faces=6):
    """the charts of one designed island (module docstring): unwrap; on a HARD failure (chart_hard_ok) bridge the holes
    once, then bisect (stag_beetle_uv.fiedler_split) until each passes; the soft bars (chart_ok) are reported. Returns a
    list of dict(faces (global), Vc, Fc (tris), orig, Qc, fq, uv (V's units), metrics, overlap, steps, note)"""
    out = []
    todo = [(np.asarray(faces, np.int64), 0, frozenset(), False)]
    while todo:
        fs, depth, extra, bridged = todo.pop()
        ss = seams | extra
        Vc, Fc, orig, Qc, fq = BU._sub(V, Q, fs, ss)
        U, steps, why = unwrap(Vc, Fc)
        met = BU.chart_metrics(Vc, Fc, U)
        ov = overlap_texels(U, Fc, px_per_unit) if not why else 1
        good = not why and chart_hard_ok(met, ov)
        if good or len(fs) < min_faces or depth >= max_depth:
            soft = not why and chart_ok(met, ov)
            note = '' if soft else (f'{"kept" if good else "KEPT OVER THE HARD BARS"} past the soft bars ({why or ""} '
                                    f'aniso {met["aniso95"]:.3f}, scale {met["s10"]:.3f}-{met["s90"]:.3f}, flipped '
                                    f'{met["flipped"]}, overlap {ov})')
            if note:
                log(f'[uv]   {name}: a {len(fs)}-face chart {note}')
            out.append(dict(faces=fs, Vc=Vc, Fc=Fc, orig=orig, Qc=Qc, fq=fq, uv=U, metrics=met, overlap=ov,
                            steps=steps, note=note))
            continue
        if not bridged and len(boundary_loops(V, Q[fs], ss)) > 1:
            br = bridge_holes(V, Q, fs, ss, hidden)
            log(f'[uv]   {name}: {len(fs)} faces failed ({why or "bars"}: aniso {met["aniso95"]:.3f}, scale '
                f'{met["s10"]:.3f}-{met["s90"]:.3f}, flipped {met["flipped"]}, overlap {ov}); {len(br)} bridge edges')
            todo.append((fs, depth, frozenset(extra | br), True))
            continue
        groups = BU.fiedler_split(V, Q, fs, sharp, hidden, ss, None)
        log(f'[uv]   {name}: {len(fs)} faces failed ({why or "bars"}: aniso {met["aniso95"]:.3f}, scale '
            f'{met["s10"]:.3f}-{met["s90"]:.3f}, flipped {met["flipped"]}, overlap {ov}); split into '
            f'{[len(g) for g in groups]}')
        for g in groups:
            todo.append((np.asarray(g, np.int64), depth + 1, extra, bridged))
    return out


def template_chart(Vt, Ft, ring):
    """a filament template's chart: its tube cut down column 0 (root ring to the last ring, then the edge to the tip),
    LSCM + the injective ARAP. Vt in any units. Returns (Vc, Fc, orig, UV)"""
    n_ring = (len(Vt) - 1) // ring
    tip = len(Vt) - 1
    col = [k * ring for k in range(n_ring)]
    # split: the faces right of the cut (whose corner on column 0 pairs with column ring - 1) take new copies
    new = {v: len(Vt) + i for i, v in enumerate(col)}
    Fc = Ft.copy()
    for f, tri in enumerate(Ft):
        if any(v in new for v in tri) and any((v % ring) == ring - 1 for v in tri if v != tip):
            Fc[f] = [new.get(v, v) for v in tri]
    Vc = np.vstack([Vt, Vt[col]])
    orig = np.concatenate([np.arange(len(Vt)), col])
    U, _, why = unwrap(Vc, Fc)
    if why:
        raise ValueError(f'a filament template would not flatten: {why}')
    return Vc, Fc, orig, U


# ============================================================================================ the pack
def island_pads(islands):
    """per island its pad: round(thickness / 8) within PAD, x STACK_PAD when stacked"""
    for isl in islands:
        th = BU.thickness_texels(isl['uvt'], isl['F'])
        p = float(np.clip(round(th / 8.0), *PAD))
        isl['thick'] = th
        isl['pad'] = int(round(p * (STACK_PAD if isl.get('stacked') else 1.0)))
    return islands


def pack_density(charts, size, cap, log=print, lo=None, tries=7):
    """the highest density (px/m at x4; charts' uv in x4 mm, each with its 'share' and 'stacked') at which every chart
    packs on ONE size^2 page, at most cap: the cap first, then a bisection. Returns (density, placed, fill, islands)"""
    def build(D):
        isl = []
        for c in charts:
            uvt = c['uv'] * (D / 1000.0) * SHARE[c['cls']]
            isl.append(dict(uvt=uvt - uvt.min(0), F=c['Fc'], stacked=c.get('stacked', False)))
        return island_pads(isl)

    def attempt(D):
        isl = build(D)
        try:
            placed, fill = BU.pack(isl, size=size, log=log)
        except ValueError as ex:
            return None, None, isl, str(ex)
        return placed, fill, isl, ''

    D = cap
    placed, fill, isl, why = attempt(D)
    if placed is not None and len(fill) == 1:
        log(f'[uv] pack at the cap {D:.0f} px/m: one page, occupancy {fill[0] * 100:.1f} %')
        return D, placed, fill, isl
    lo = lo or 0.8 * cap
    hi = cap
    best = None
    for _ in range(tries):
        D = 0.5 * (lo + hi)
        placed, fill, isl, why = attempt(D)
        fits = placed is not None and len(fill) == 1
        log(f'[uv] pack at {D:.0f} px/m: ' + (f'one page, occupancy {fill[0] * 100:.1f} %' if fits else
                                             f'{len(fill) if fill else "-"} pages {why}'))
        if fits:
            best = (D, placed, fill, isl)
            lo = D
        else:
            hi = D
    if best is None:
        raise ValueError(f'nothing packs one {size} page down to {lo:.0f} px/m')
    return best


# ============================================================================================ the stack checks
def umeyama(A, B, allow_reflection=False):
    """the similarity (s, R, t) taking A onto B index for index (least squares); reflections allowed on request.
    Returns s, R, t and the residual per point"""
    ca, cb = A.mean(0), B.mean(0)
    X, Y = A - ca, B - cb
    U, S, Vt = np.linalg.svd(Y.T @ X / len(A))
    D = np.eye(3)
    if not allow_reflection and np.linalg.det(U @ Vt) < 0:
        D[2, 2] = -1.0
    R = U @ D @ Vt
    s = float(np.trace(np.diag(S) @ D) / max((X ** 2).sum() / len(A), 1e-30))
    t = cb - s * R @ ca
    return s, R, t, np.linalg.norm(s * (A @ R.T) + t - B, axis=1)


def rolled_residual(P, C, K=RAMUS_K):
    """a ramus copy against the primary under the similarity of their ring centres and a per-ring roll about each
    ring's own axis (the stalk surfaces' map, module docstring): (scale, the mean roll in deg, the residual per vertex
    of the rings)"""
    nr = len(P) // K
    cp = np.array([P[r * K:(r + 1) * K].mean(0) for r in range(nr)])
    cc = np.array([C[r * K:(r + 1) * K].mean(0) for r in range(nr)])
    s, R, t, _ = umeyama(cp, cc)
    A = s * (P[:nr * K] @ R.T) + t
    ca_all = np.array([A[r * K:(r + 1) * K].mean(0) for r in range(nr)])
    res, rolls = np.zeros(nr * K), []
    for r in range(nr):
        a, b = A[r * K:(r + 1) * K], C[r * K:(r + 1) * K]
        ca, cb = a.mean(0), b.mean(0)
        ax = np.linalg.svd(a - ca)[2][2]
        along = ca_all[min(r + 1, nr - 1)] - ca_all[max(r - 1, 0)]       # every ring's axis toward the tip, so the
        ax = ax if ax @ along >= 0 else -ax                                # rolls share one sense
        ang = []
        for j in range(K):
            x = a[j] - ca - ax * ((a[j] - ca) @ ax)
            y = b[j] - cb - ax * ((b[j] - cb) @ ax)
            ang.append(np.arctan2(np.cross(x, y) @ ax, x @ y))
        th = float(np.angle(np.mean(np.exp(1j * np.array(ang)))))
        Kx = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]])
        Rr = np.eye(3) + np.sin(th) * Kx + (1.0 - np.cos(th)) * Kx @ Kx
        res[r * K:(r + 1) * K] = np.linalg.norm((a - ca) @ Rr.T + cb - b, axis=1)
        rolls.append(np.degrees(th))
    return s, float(np.mean(rolls)), res
