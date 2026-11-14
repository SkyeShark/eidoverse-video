"""THE HOOF'S LOWS AND THEIR UVS, authored on the generator's own lines (WORKING_RULES 2; HIGH_TO_LOW.md; DEER_PLAN
§6.4-§6.5; work/bestiary/deer/hooves/build_NOTES.md steps 5-6). No algorithm decides the topology: every vertex is
a point of the claw's form at a chosen (tubule, ring).

THE CLAW. Columns run down tubules (coronet to ground, then in under the claw to the sole's middle line), rings
round the claw on lines of equal v. A capsule is RIGID (one joint), so it carries loops only where its outline
turns:
  columns   K = 2 n round the claw, closer where the plan outline and the coronet turn tighter (the toe, the heel):
            placed so every chord sags alike (column_knots)
  the wall  ONE band from the tuck's top (under the skin) to the ground ring wherever the wall is the ruled line
            (the dorsal and abaxial wall: a straight tubule needs no ring between its ends); the heel's columns,
            where the bulb bulges, and the hollowed axial columns carry the coronet ring and one or two more
  under     the bearing rim's inner edge, one ring in the sole's trough, the spine; the bulb's columns the rings
            of its rounded underside instead
A ring that stops ends in triangles (a strip between two columns of unequal rings is zipped by parameter); the two
sides of the sole meet on shared spine vertices. Islands: the wall (one strip, its seam down an axial column in the
cleft), the sole + bulb underside (a disc inside the ground ring; the bearing edge is a hard edge and the seam).

THE DEWCLAW (one template): 12 sides, rings where its rounded end turns, a pole at its tip; one island, its seam
down the face that lies against the leg.

    low = claw_low(F, HL)            dict: V, F (triangles), poly (the authored quads and triangles), isl (island
                                     per vertex), N, uvm (the islands' flat maps in METRES, one density), region
                                     (per triangle), names
    dew = dewclaw_low(p, HL)         the same, in the template's own frame
    pack = nest([...], W, H, pad)    the islands nested into a W x H texel sheet at the highest one density
    foot = instances(...)            the foot's capsules from the two primaries: mirror, rotate, scale
"""
import numpy as np

from . import hoof as HF
from .. import uv as UVM

REGIONS = ('wall', 'wall_bulb', 'sole', 'bulb_under', 'dewclaw')


def column_knots(F, n, rings=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0), under=(0.061, 0.234), report=None):
    """the n + 1 shares f (0 the dorsal ridge and toe tip .. 1 the heel's middle) of a claw's columns, the same on
    both halves (the two sides of the sole meet on shared spine vertices): EQUAL MEASURED SAG ACROSS EVERY GAP.
    A gap between two columns is judged by the most the form's own rings stand off the chord across it: the wall's
    rings at `rings` (v) and the roll under the bulb's equator at `under` (t), on both halves; a ring on the cleft's
    hidden wall, or under the sole, counts a third (its bar is three times a seen one's: claw_low). The knots are
    placed so that every gap's worst is the same level: each gap is grown from the last knot until it reaches the
    level, and the level is found by bisection so that n gaps reach the heel. `report` (a dict) takes the level.

    (11-10 to 11-12 the knots were spaced by 1 / sqrt(curvature x speed) of six curves, smoothed, with a floor that
    kept columns on the straight flanks. MEASURED PER GAP on 11-12 (work/bestiary/deer/hooves/build_NOTES.md G5): the
    cleft's flat wall had gaps of 0.01-0.03 mm while the gap beside the dorsal ridge stood at 0.45 mm, the toe's
    inner face at 0.52 and the heel's last gap at 0.44, against the bar's 0.337: columns were spent where nothing
    turns, and the bulb's p95 sag stayed at 0.43 mm whatever the rings did.)"""
    N = 2001
    fd = np.linspace(0.0, 1.0, N)
    curves = []
    for half in ('ab', 'ax'):
        cq = F.column(fd, half)
        wb = cq['wb']
        w_wall = np.ones(N) if half == 'ab' else \
            1.0 - (2.0 / 3.0) * HF._ss(0.26, 0.34, fd) * (1.0 - HF._ss(0.4, 0.6, wb))
        curves += [(F.wall(cq, v), w_wall) for v in rings]
        curves += [(F.under(cq, t)[0], 1.0 / 3.0 + (2.0 / 3.0) * wb) for t in under]
    Wc = [np.concatenate([[0.0], np.cumsum(w)]) for _, w in curves]

    def cost(a, b):
        out = 0.0
        for (P, _), cw in zip(curves, Wc):
            q = P[a:b + 1] - P[a]
            d = q[-1]
            t = np.clip(q @ d / max(float(d @ d), 1e-30), 0.0, 1.0)
            out = max(out, float(np.linalg.norm(q - t[:, None] * d, axis=1).max()) * (cw[b + 1] - cw[a]) / (b + 1 - a))
        return out

    def fill(level):
        """the knots when every gap is grown until its sag reaches `level`: (indices, the last gap's own sag)"""
        ks, a = [0], 0
        while a < N - 1:
            lo, hi = a + 1, min(a + 2, N - 1)
            while hi < N - 1 and cost(a, hi) <= level:             # gallop, then bisect
                lo, hi = hi, min(a + 2 * (hi - a), N - 1)
            if cost(a, hi) <= level:
                lo = hi
            else:
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if cost(a, mid) <= level:
                        lo = mid
                    else:
                        hi = mid
            ks.append(lo)
            a = lo
            if len(ks) > 4 * n + 8:
                break
        return ks

    lo_l, hi_l = 0.0, cost(0, N - 1)
    best = None
    for _ in range(40):
        mid = 0.5 * (lo_l + hi_l)
        ks = fill(mid)
        if len(ks) - 1 <= n:
            hi_l, best = mid, ks
        else:
            lo_l = mid
        if hi_l - lo_l < 1e-4 * hi_l:
            break
    ks = best if best is not None else fill(hi_l)
    while len(ks) - 1 < n:                                         # (a level a hair too high: split the widest gap)
        i = int(np.argmax(np.diff(ks)))
        ks.insert(i + 1, (ks[i] + ks[i + 1]) // 2)
    if report is not None:
        report.update(level_HL=float(hi_l), gaps_HL=[float(cost(a, b)) for a, b in zip(ks[:-1], ks[1:])])
    f = fd[np.asarray(ks)]
    f[0], f[-1] = 0.0, 1.0
    return f


def _take(col, idx):
    return {k: (v[idx] if isinstance(v, np.ndarray) else v) for k, v in col.items()}


def _zip(ia, pa, ib, pb, eps=1e-9):
    """the polygons between two vertex columns ordered by parameter (first and last parameters equal): a quad where
    both step together, a triangle where one column has a ring the other has not"""
    out, i, j = [], 0, 0
    while i < len(ia) - 1 or j < len(ib) - 1:
        na = pa[i + 1] if i < len(ia) - 1 else np.inf
        nb = pb[j + 1] if j < len(ib) - 1 else np.inf
        if abs(na - nb) <= eps:
            out.append((ia[i], ib[j], ib[j + 1], ia[i + 1]))
            i, j = i + 1, j + 1
        elif na < nb:
            out.append((ia[i], ib[j], ia[i + 1]))
            i += 1
        else:
            out.append((ia[i], ib[j], ib[j + 1]))
            j += 1
    return out


def _normals(V, T):
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-30)


def _unwrap(V, T, iters=20):
    """one island flat, in metres at the surface's own scale (LSCM, then ARAP, then scaled so its area is the
    surface's: one density by construction); wound as the surface (no mirrored texels)"""
    ids = np.unique(T)
    loc = np.full(int(T.max()) + 1, -1)
    loc[ids] = np.arange(len(ids))
    Vl, Tl = V[ids], loc[T]
    U = UVM.lscm(Vl, Tl)
    U = UVM.arap(Vl, Tl, U, iters=iters)
    d1, d2 = U[Tl[:, 1]] - U[Tl[:, 0]], U[Tl[:, 2]] - U[Tl[:, 0]]
    a2 = 0.5 * (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    if a2.sum() < 0.0:
        U = U * np.array([-1.0, 1.0])
        a2 = -a2
    a3 = 0.5 * np.linalg.norm(np.cross(Vl[Tl[:, 1]] - Vl[Tl[:, 0]], Vl[Tl[:, 2]] - Vl[Tl[:, 0]]), axis=1)
    U = U * np.sqrt(a3.sum() / max(a2.sum(), 1e-30))
    out = np.zeros((len(V), 2))
    out[ids] = U - U.min(0)
    return out, int((a2 <= 0.0).sum())


def _triangulate(V, polys, mids):
    """triangles of the authored polygons; a quad is split along the diagonal whose middle lies nearer the form's
    own point at the quad's middle (mids: per polygon, or None for a triangle), so a twisted quad folds the way
    the surface curves"""
    T, src = [], []
    for i, (pl, m) in enumerate(zip(polys, mids)):
        if len(pl) == 3:
            T.append(pl)
            src.append(i)
            continue
        a, b, c, d = pl
        if m is None or np.linalg.norm(0.5 * (V[a] + V[c]) - m) <= np.linalg.norm(0.5 * (V[b] + V[d]) - m):
            T += [(a, b, c), (a, c, d)]
        else:
            T += [(a, b, d), (b, c, d)]
        src += [i, i]
    return np.asarray(T, np.int32), np.asarray(src, np.int32)


# -------------------------------------------------------------------------------------------------- the claw
def claw_low(F, HL, n=14, tol=0.0032, seams=(('ax', 0.53),), split_sole=False, log=None):
    """THE PRIMARY CLAW'S LOW (the +X claw; its partner is the mirror). n: columns per half (K = 2 n); tol: the
    sag a ring is spent on, as a share of HL (0.0032 = 0.33 mm on the stag = half a pixel at 1 m, 1080 lines);
    seams: the tubules the wall's map is cut along, each (half, f): one seam in the cleft makes the wall one strip,
    a second splits it in two (the islands then nest tighter; the material is painted from 3-D drivers, so a seam
    carries no break in the pattern). split_sole (11-11, fix round 1): the underside's map cut along the sole's
    middle line (the spine, the bottom of the trough, seen only from below), so it is two long thin halves that nest
    into the wall fans' hollows instead of one leaf beside them (the sheet's fill: check1 found 67 % against 75 %)"""
    p = F.p
    knots = {}
    f = column_knots(F, n, report=knots)
    col = F.ring(f, f[1:-1][::-1])
    K = 2 * n
    wb = col['wb']
    # WHAT A RING IS SPENT ON, MEASURED PER COLUMN (11-11, fix round 1). The wall is a SHELL now: each column bows
    # out of its ruled line (ClawForm.bulge, up to 0.04 HL = 4.1 mm on the flank and the toe), and the heel's columns
    # carry the bulb's bulge. A column gets the fewest equal steps in v (1, 2 or 4: their rings line up, so a ring
    # that stops ends in a triangle beside a column with more) whose chords stay within `tol` of the column's own
    # curve, the tuck's step included. The axial wall behind the toe lies in the cleft against the other claw and is
    # never seen side on: its hollow (1 mm) is left to the bake, as before (a bar 3 x tol there). (11-10: the ruled
    # wall needed no ring between the tuck and the ground except on the bulb; 274 triangles a claw)
    # (11-12, FIX ROUND 2, check 2's failure 7: THE RULE HAD A SILENT CAP. steps() tried 1, 2 and 4 EQUAL steps and
    # returned 4 when 4 still missed the bar: 21 of 28 columns sat there, the seen surfaces sagged 0.46 mm at p95
    # against the bar's 0.337, the outline 0.57 px at the named view, and the report said "to half a pixel". Two
    # changes. (1) THE RINGS ARE PLACED BY THE SAG, not at equal shares: a bowed column turns most at its bow's peak
    # and least at its ends, so equal steps spend their chords where the wall is straightest. The three rings of a
    # 4-step column stand at ONE set of v round the claw (a ring is a line of equal growth, a fair loop), searched
    # on a grid of 0.02 for the least worst chord sag over the seen columns; a 2-step column takes the middle one.
    # (2) THE COUNT GOES ON AND THE CAP SPEAKS: a column that still misses with 4 takes 8 (each step halved), and
    # whatever misses with 8 is printed and returned (`low['ring_rule']`), never passed in silence.)
    GV = np.linspace(0.0, 1.0, 51)                                 # the grid the rings may stand on
    hid = np.array([bool(col['half'][k] == 1 and col['f'][k] > 0.30 and wb[k] < 0.5) for k in range(K)])
    bars = tol * np.where(hid, 3.0, 1.0)
    tops = -0.9 * p['coronet_tuck'] / col['L']

    def chord_dev(P):
        """the most a polyline's points stand off the chord between its ends"""
        d_ = P[-1] - P[0]
        q_ = P - P[0]
        t_ = np.clip(q_ @ d_ / max(d_ @ d_, 1e-30), 0.0, 1.0)
        return float(np.linalg.norm(q_ - t_[:, None] * d_, axis=1).max())

    D = np.zeros((K, len(GV), len(GV)))                            # D[k, i, j]: column k's chord sag from GV[i] to GV[j]
    d_tuck = np.zeros(K)
    for k in range(K):
        vq = np.concatenate([np.linspace(tops[k], 0.0, 9)[:-1], np.linspace(0.0, 1.0, 201)])
        Pq = F.wall(_take(col, np.full(len(vq), k)), vq)
        d_tuck[k] = chord_dev(Pq[:9])
        Pw = Pq[8:]                                                # v 0 .. 1 in steps of 0.005: GV[i] is Pw[4 i]
        for i in range(len(GV) - 1):
            for j in range(i + 1, len(GV)):
                D[k, i, j] = chord_dev(Pw[4 * i:4 * j + 1])
    last = len(GV) - 1
    need = np.array([k for k in range(K) if not hid[k] and D[k, 0, last] > bars[k]], int)
    best = (np.inf, None)
    if len(need):
        for i2 in range(8, last - 7):
            for i1 in range(4, i2 - 3):
                a_ = np.maximum(D[need, 0, i1], D[need, i1, i2])
                for i3 in range(i2 + 4, last - 3):
                    j_ = float(np.maximum(a_, np.maximum(D[need, i2, i3], D[need, i3, last])).max())
                    if j_ < best[0]:
                        best = (j_, (i1, i2, i3))
    i1, i2, i3 = best[1] if best[1] is not None else (12, 25, 38)
    V4 = [0.0, float(GV[i1]), float(GV[i2]), float(GV[i3]), 1.0]
    V8 = sorted(V4 + [0.5 * (a_ + b_) for a_, b_ in zip(V4[:-1], V4[1:])])

    def dev_of(k, nodes):
        idx = [int(round(v_ * last)) for v_ in nodes]
        if all(abs(GV[i_] - v_) < 1e-9 for i_, v_ in zip(idx, nodes)):
            return max(D[k, a_, b_] for a_, b_ in zip(idx[:-1], idx[1:]))
        vq = np.linspace(0.0, 1.0, 801)                            # the 8-step nodes lie between the grid's
        Pw = F.wall(_take(col, np.full(len(vq), k)), vq)
        return max(chord_dev(Pw[int(round(a_ * 800)):int(round(b_ * 800)) + 1]) for a_, b_ in zip(nodes[:-1], nodes[1:]))

    def steps(k):
        for m, nodes in ((1, [0.0, 1.0]), (2, [0.0, V4[2], 1.0]), (4, V4), (8, V8)):
            dev = dev_of(k, nodes)
            if dev <= bars[k]:
                return m, nodes, dev
        return 8, V8, dev
    # ---- each column's rings: (nominal parameter, the generator's own parameter)
    wall_rows, under_rows = [], []
    m_cols, dev_cols = [], []
    for k in range(K):
        # the low's top ring 10 % short of the high's tuck: a low edge ON the high's own edge bakes a line of misses
        top = (-1.0, float(tops[k]))
        m, nodes, dev = steps(k)
        m_cols.append(m)
        dev_cols.append(dev)
        if m == 1:
            wall_rows.append([top, (1.0, 1.0)])
        else:
            wall_rows.append([top] + [(float(v_), float(v_)) for v_ in nodes])
        # under the claw (seen only when the foot lifts): the bulb's rounded underside in three steps of its
        # quarter turn; the sole's columns the rim's inner edge and the spine (the trough between them is baked:
        # a ring in it bought 0.5 mm of sag inside a hollow nobody sees in outline, for 56 triangles)
        # (11-12, fix round 2: the quarter turn was in three steps of 30 deg; behind the heel, where the equator
        # stands 10 mm up, a 30 deg chord sags 0.33-0.48 mm: the underside's p95 0.46 against the bar's 0.337 (seen
        # from behind whenever the foot lifts). Four steps of 22.5 deg: 0.56 of that)
        if wb[k] > 0.5:
            A = p['bulb_under']
            under_rows.append([(0.0, 0.0)] + [(nom, A * (1.0 - np.cos(np.radians(a))))
                                              for nom, a in ((0.06, 22.5), (0.23, 45.0), (0.5, 67.5), (0.8, 90.0))]
                              + [(1.0, 1.0)])
        else:
            under_rows.append([(0.0, 0.0), (0.15, float(col['t_r'][k])), (1.0, 1.0)])
    miss = [(k, dev_cols[k] / bars[k]) for k in range(K) if dev_cols[k] > bars[k] * (1.0 + 1e-9)]
    ring_rule = dict(nodes4=V4, nodes8=V8, bar_HL=float(tol), steps=m_cols, dev_over_bar=[float(dev_cols[k] / bars[k])
                                                                                          for k in range(K)],
                     hidden=[bool(x) for x in hid], tuck_dev_over_bar=[float(d_tuck[k] / bars[k]) for k in range(K)],
                     at_cap=[dict(column=int(k), f=float(col['f'][k]), half=int(col['half'][k]), dev_over_bar=float(r_))
                             for k, r_ in miss], worst4=float(best[0] / tol) if np.isfinite(best[0]) else 0.0,
                     gap_level_over_bar=float(knots['level_HL'] / tol),
                     gaps_over_bar=[float(g_ / tol) for g_ in knots['gaps_HL']])
    V, isl, vcol, vpar = [], [], [], []

    def add(P, island, k, par):
        V.append(P)
        isl.append(island)
        vcol.append(k)
        vpar.append(par)
        return len(V) - 1

    def wall_pt(k, v):
        return HF.to_world(F.wall(_take(col, np.array([k])), np.array([v]))[0], HL)

    def under_pt(k, t):
        return HF.to_world(F.under(_take(col, np.array([k])), np.array([t]))[0][0], HL)

    # ---- the wall: one strip per seam, each from its seam column round the claw to the next seam's
    k_seams = []
    for half, fq in seams:
        ks = np.arange(0, n + 1) if half == 'ab' else np.arange(n + 1, K)
        k_seams.append(int(ks[np.argmin(np.abs(col['f'][ks] - fq))]))
    k_seams = sorted(set(k_seams))
    strips = []
    for i, k0 in enumerate(k_seams):
        cnt = (k_seams[(i + 1) % len(k_seams)] - k0) % K or K
        strips.append([(k0 + j) % K for j in range(cnt + 1)])
    U_ISL = len(strips)                                            # the island under the claw
    polys, pcols, preg = [], [], []
    ring_pairs = []                                                # (the wall's ground-ring vertex, its column)
    for si, strip in enumerate(strips):
        wall_ids = [[add(wall_pt(k, v), si, k, v) for _, v in wall_rows[k]] for k in strip]
        ring_pairs += [(ids[-1], k) for ids, k in zip(wall_ids, strip)]
        for i in range(len(strip) - 1):
            ka, kb = strip[i], strip[i + 1]
            for pl in _zip(wall_ids[i], [r[0] for r in wall_rows[ka]], wall_ids[i + 1], [r[0] for r in wall_rows[kb]]):
                polys.append(pl)
                pcols.append((ka, kb, 0))
                preg.append(1 if 0.5 * (wb[ka] + wb[kb]) > 0.5 else 0)
    # ---- under the claw: a disc; the two halves' columns end on shared spine vertices. With split_sole each half
    # has its own copies of the spine and of the two columns the halves share (the ridge's, 0, and the heel's, n):
    # the abaxial half is island U_ISL (columns 0..n), the axial half U_ISL + 1 (columns n..K-1 and back to 0)
    def under_half(cols_, island, spine_):
        ids_ = {}
        for k in cols_:
            ids = [add(under_pt(k, t), island, k, 1.0 + t) for _, t in under_rows[k][:-1]]
            key = k if k <= n else K - k
            if key not in spine_:
                spine_[key] = add(under_pt(k, 1.0), island, k, 2.0)
            ids_[k] = ids + [spine_[key]]
        return ids_

    def under_polys(ids_, pairs_):
        for k, kb in pairs_:
            for pl in _zip(ids_[k], [r[0] for r in under_rows[k]], ids_[kb], [r[0] for r in under_rows[kb]]):
                if len(set(pl)) < len(pl):
                    pl = tuple(dict.fromkeys(pl))
                    if len(pl) < 3:
                        continue
                polys.append(pl)
                pcols.append((k, kb, 1))
                preg.append(3 if 0.5 * (wb[k] + wb[kb]) > 0.5 else 2)

    if split_sole:
        ids_a = under_half(range(0, n + 1), U_ISL, {})
        ids_b = under_half(list(range(n, K)) + [0], U_ISL + 1, {})
        under_polys(ids_a, [(k, k + 1) for k in range(n)])
        under_polys(ids_b, [(k, (k + 1) % K) for k in range(n, K)])
        under_ids = [ids_a[k] if k <= n else ids_b[k] for k in range(K)]
        under_copies = {0: ids_b[0], n: ids_b[n]}                  # the second copies of the shared columns
    else:
        ids_a = under_half(range(K), U_ISL, {})
        under_polys(ids_a, [(k, (k + 1) % K) for k in range(K)])
        under_ids = [ids_a[k] for k in range(K)]
        under_copies = {}
    n_isl = U_ISL + (2 if split_sole else 1)
    V = np.asarray(V, np.float64)
    isl, vcol, vpar = np.asarray(isl), np.asarray(vcol), np.asarray(vpar)
    # ---- each quad's own point on the form (the middle of its columns and rings), for the diagonal
    mids = []
    for pl, (ka, kb, island) in zip(polys, pcols):
        if len(pl) != 4:
            mids.append(None)
            continue
        ha, hb = int(col['half'][ka]), int(col['half'][kb])
        fa, fb = float(col['f'][ka]), float(col['f'][kb])
        half = ha if ha == hb else (hb if fa in (0.0, 1.0) else ha)
        cm = F.column(np.array([0.5 * (fa + fb)]), 'ab' if half == 0 else 'ax')
        par = float(np.mean(vpar[list(pl)]))
        mids.append(HF.to_world(F.wall(cm, np.array([par]))[0], HL) if island == 0 else
                    HF.to_world(F.under(cm, np.array([par - 1.0]))[0][0], HL))
    T, src = _triangulate(V, polys, mids)
    T = _oriented(V, T)
    region = np.asarray(preg)[src]
    # ---- normals: the wall's own (smooth all round: a seam's two copies shade as one) and the underside's own,
    # run together round the bulb, where the ground ring is a soft equator and not an edge. Along the bearing edge
    # each side's normal is turned `edge_soft` of the way toward the two sides' mean: the high's edge is worn round
    # and chipped back, and a ray square to the wall at the edge passes under it (measured: 34 % of the first bake's
    # missed texels lay within 2 mm of the ground); the baked normal map takes the turn back out
    edge_soft = 0.5
    under_v = isl >= U_ISL
    # (the underside's normals welded too: with split_sole its two halves' copies along the spine and the shared
    # columns shade as one, the trough's bottom being smooth on the high)
    Ni = _welded_normals(V, T[~under_v[T[:, 0]]]) * (~under_v)[:, None] + \
        _welded_normals(V, T[under_v[T[:, 0]]]) * under_v[:, None]
    N = Ni.copy()
    for a, k in ring_pairs:
        b = under_ids[k][0]
        m = Ni[a] + Ni[b]
        m /= max(np.linalg.norm(m), 1e-30)
        w_ = max(float(wb[k]), edge_soft)
        for q in [a, b] + ([under_copies[k][0]] if k in under_copies else []):
            x = (1.0 - w_) * Ni[q] + w_ * m
            N[q] = x / max(np.linalg.norm(x), 1e-30)
    # ---- the flat maps
    uvm = np.zeros((len(V), 2))
    flipped = 0
    for i_ in range(n_isl):
        Ti = T[isl[T[:, 0]] == i_]
        u, bad = _unwrap(V, Ti)
        uvm[isl == i_] = u[isl == i_]
        flipped += bad
    edges = set()
    for pl in polys:
        for a, b in zip(pl, pl[1:] + pl[:1]):
            edges.add((min(a, b), max(a, b)))
    low = dict(V=V, F=T, N=N, isl=isl, uvm=uvm, region=region, poly=polys, edges=np.asarray(sorted(edges), np.int32),
               f=f, K=K, seam_columns=k_seams, under_island=U_ISL, flipped=flipped, vcol=vcol, vpar=vpar,
               rings=dict(wall=[len(r) for r in wall_rows], under=[len(r) for r in under_rows]), wall_steps=m_cols,
               ring_rule=ring_rule)
    if log:
        log(f'[low] claw: the wall\'s steps per column (1 / 2 / 4 / 8): {m_cols.count(1)} / {m_cols.count(2)} / '
            f'{m_cols.count(4)} / {m_cols.count(8)}; the rings of a 4-step column at v {[round(v_, 2) for v_ in V4[1:-1]]} '
            f'(placed by the sag: the worst seen column\'s chords within {ring_rule["worst4"]:.2f} of the bar, '
            f'{tol * HL * 1e3:.3f} mm)')
        log(f'[low] claw: the columns\' gaps (equal measured sag across each, seen rings; a hidden ring counts a third): '
            f'every gap within {ring_rule["gap_level_over_bar"]:.2f} of the bar'
            + ('' if ring_rule['gap_level_over_bar'] <= 1.0 else ': OVER THE BAR: n is too small for this bar'))
        if miss:
            log(f'[low] claw: THE CAP BINDS on {len(miss)} columns (8 steps still miss the bar): '
                + ', '.join(f'column {k} (f {col["f"][k]:.2f}, {"ax" if col["half"][k] else "ab"}) x{r_:.2f}'
                            for k, r_ in miss))
        else:
            log('[low] claw: no column at the cap: every column\'s chords are within its bar')
        log(f'[low] claw: K {K} columns, {len(V)} vertices, {len(T)} triangles ({sum(len(q) == 4 for q in polys)} '
            f'quads + {sum(len(q) == 3 for q in polys)} triangles authored); wall seams at columns {k_seams} (f '
            f'{[round(float(col["f"][k]), 2) for k in k_seams]}, half {[int(col["half"][k]) for k in k_seams]}); '
            f'flipped UV triangles {flipped}')
    return low


def _welded_normals(V, T):
    """area-weighted vertex normals with vertices at one place summed together (a UV seam's copies shade as one)"""
    key = np.round(V / 1e-9).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    acc = np.zeros((int(inv.max()) + 1, 3))
    for k in range(3):
        np.add.at(acc, inv[T[:, k]], fn)
    return acc[inv] / np.maximum(np.linalg.norm(acc[inv], axis=1, keepdims=True), 1e-30)


def _oriented(V, T):
    """the triangles wound outward: the low is open at the tuck's top, so the sign comes from the volume about its
    own centroid with that opening capped by its ring's mean (a small term)"""
    c = V.mean(0)
    vol = np.einsum('ij,ij->i', V[T[:, 0]] - c, np.cross(V[T[:, 1]] - c, V[T[:, 2]] - c)).sum()
    return T if vol > 0 else T[:, ::-1].copy()


# -------------------------------------------------------------------------------------------------- the dewclaw
def pad_knots(p, K, floor=0.35):
    """the angles of a dewclaw's K columns round its section: 0 and pi (the pad's side edges, where the seams run)
    are columns; the rest share the two faces by equal chord sag (column_knots' rule). Returns (theta, the index of
    the column at pi)"""
    th = np.linspace(0.0, 2.0 * np.pi, 4001)
    P, _ = HF.dewclaw_form(p, w=np.array([0.25]), theta=th)
    P = P[0, :, :2]
    d = np.gradient(P, th, axis=0)
    v = np.linalg.norm(d, axis=1)
    td = d / np.maximum(v[:, None], 1e-12)
    dens = np.sqrt(np.maximum(np.linalg.norm(np.gradient(td, th, axis=0), axis=1) * v, 0.0))
    from scipy.ndimage import gaussian_filter1d
    dens = gaussian_filter1d(dens, 25.0, mode='wrap')
    dens = dens + floor * dens.mean()
    c = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(th))])
    c_pi = float(np.interp(np.pi, th, c))
    n1 = int(np.clip(round(K * c_pi / c[-1]), 3, K - 3))
    q = np.concatenate([np.linspace(0.0, c_pi, n1 + 1)[:-1], np.linspace(c_pi, c[-1], K - n1 + 1)[:-1]])
    return np.interp(q, c, th), n1


def dewclaw_low(p, HL, K=12, rows=(0.0, 0.45, 0.72, 0.88, 0.97), log=None):
    """THE DEWCLAW TEMPLATE'S LOW, its own frame (metres; +z along it, +y outward): K sides (closer round the
    pad's two side edges, where its section turns), the tuck's top ring, rings where its rounded end turns, a pole
    at the tip. Two islands, the outer face and the face against the leg, their seams down the pad's side edges
    (one island with a pole in it stretched 2:1 at the tip: measured, anisotropy p95 1.99)"""
    w = np.concatenate([[-0.9 * p['dew_tuck']], rows, [1.0]])      # 10 % short of the high's tuck (as the claw's)
    theta, h = pad_knots(p, K)
    P, vv = HF.dewclaw_form(p, n_round=K, w=w, theta=theta)
    R = len(w) - 1                                                  # rings (the last row is the pole)
    V, polys, isl = [], [], []
    for i_, ks in enumerate((list(range(0, h + 1)), [k % K for k in range(h, K + 1)])):
        ids = np.zeros((R, len(ks)), int)
        for r in range(R):
            for i, k in enumerate(ks):
                ids[r, i] = len(V)
                V.append(P[r, k] * HL)
                isl.append(i_)
        pole = len(V)
        V.append(P[R].mean(0) * HL)
        isl.append(i_)
        for r in range(R - 1):
            for i in range(len(ks) - 1):
                polys.append((ids[r, i], ids[r, i + 1], ids[r + 1, i + 1], ids[r + 1, i]))
        for i in range(len(ks) - 1):
            polys.append((ids[R - 1, i], ids[R - 1, i + 1], pole))
    V = np.asarray(V, np.float64)
    isl = np.asarray(isl)
    T, src = _triangulate(V, polys, [None] * len(polys))
    T = _oriented(V, T)
    # normals: smooth over the whole pad (the seams' two copies and the pole's shade as one)
    key = np.round(V / (1e-7 * max(HL, 1e-9))).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    acc = np.zeros((int(inv.max()) + 1, 3))
    for k in range(3):
        np.add.at(acc, inv[T[:, k]], fn)
    N = acc[inv] / np.maximum(np.linalg.norm(acc[inv], axis=1, keepdims=True), 1e-30)
    uvm = np.zeros((len(V), 2))
    flipped = 0
    for i_ in (0, 1):
        u, bad = _unwrap(V, T[isl[T[:, 0]] == i_])
        uvm[isl == i_] = u[isl == i_]
        flipped += bad
    edges = set()
    for pl in polys:
        for a, b in zip(pl, pl[1:] + pl[:1]):
            edges.add((min(a, b), max(a, b)))
    low = dict(V=V, F=T, N=N, isl=isl, uvm=uvm, region=np.full(len(T), 4), poly=polys,
               edges=np.asarray(sorted(edges), np.int32), K=K, flipped=flipped)
    if log:
        log(f'[low] dewclaw: K {K}, {len(V)} vertices, {len(T)} triangles; flipped UV triangles {flipped}')
    return low


# -------------------------------------------------------------------------------------------------- packing
def _mask(U, T, s, step, rot):
    """an island's footprint on a coarse grid (cells of `step` texels) at s texels a metre, turned by rot degrees:
    (mask, the turned UVs in texels with their minimum at the grid's origin)"""
    from PIL import Image, ImageDraw
    c, sn = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    X = (U @ np.array([[c, sn], [-sn, c]])) * s
    X = X - X.min(0)
    w, h = np.ceil(X.max(0) / step).astype(int) + 1
    im = Image.new('L', (int(w), int(h)), 0)
    d = ImageDraw.Draw(im)
    for a, b, c_ in X[T] / step:
        d.polygon([tuple(a), tuple(b), tuple(c_)], fill=255, outline=255)
    return np.asarray(im) > 0, X


def nest(islands, W, H, pad=8, step=2, rots=tuple(range(0, 360, 15)), iters=12, tries=4, log=None):
    """islands: [(U (n, 2) metres, T triangles)] at one scale. Finds the highest density s (texels a metre) at
    which they all nest into W x H texels with `pad` texels between them and to the border, each turned to one of
    `rots`, placed largest first at the lowest free place (so a small island settles into a large one's hollow).
    Returns (s, [(rot, tx, ty)], fill): texel = turn(U) * s + (tx, ty)"""
    from scipy.ndimage import binary_dilation
    from scipy.signal import fftconvolve
    def flat_area(U, T):
        d1, d2 = U[T[:, 1]] - U[T[:, 0]], U[T[:, 2]] - U[T[:, 0]]
        return float(0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum())

    areas = [flat_area(U, T) for U, T in islands]
    span = [float(np.ptp(U, axis=0).max()) for U, T in islands]
    rng = np.random.default_rng(3)
    # the orders tried at each density: largest first by area, by reach, then a few shuffles (a greedy nest's
    # result hangs on its order: the two-seam hoof sheet went from 61 to its best fill on a shuffle)
    orders = [list(np.argsort([-x for x in areas])), list(np.argsort([-x for x in span]))] + \
        [list(rng.permutation(len(islands))) for _ in range(tries)]
    gw, gh = W // step, H // step
    m = max(1, int(np.ceil(pad / (2.0 * step))))                   # each island grown by half the gap
    mb = max(1, int(np.ceil(pad / step)) - m)                      # the border's band: with m, `pad` to the edge
    area = sum(areas)

    def attempt(s):
        for order in orders:
            pl = attempt_order(s, order)
            if pl is not None:
                return pl
        return None

    def attempt_order(s, order):
        occ = np.zeros((gh, gw), bool)
        occ[:mb], occ[-mb:], occ[:, :mb], occ[:, -mb:] = True, True, True, True
        place = [None] * len(islands)
        for i in order:
            U, T = islands[i]
            best = None
            for rot in rots:
                mk, X = _mask(U, T, s, step, rot)
                hh, ww = mk.shape
                if hh + 2 * m > gh or ww + 2 * m > gw:
                    continue
                mk = binary_dilation(np.pad(mk, m), iterations=m)
                hit = fftconvolve(occ.astype(np.float32), mk[::-1, ::-1].astype(np.float32), mode='valid') > 0.5
                ys, xs = np.nonzero(~hit)
                if not len(ys):
                    continue
                j = np.lexsort((xs, ys))[0]
                top = ys[j] + mk.shape[0]
                if best is None or (top, xs[j]) < best[0]:
                    best = ((top, xs[j]), rot, int(ys[j]), int(xs[j]), mk)
            if best is None:
                return None
            _, rot, y0, x0, mk = best
            occ[y0:y0 + mk.shape[0], x0:x0 + mk.shape[1]] |= mk
            place[i] = (rot, (x0 + m) * step, (y0 + m) * step)
        return place

    lo, hi = 0.0, np.sqrt(W * H / area)
    best = None
    for _ in range(iters):
        s = 0.5 * (lo + hi)
        pl = attempt(s)
        if pl is None:
            hi = s
        else:
            lo, best = s, pl
    fill = area * lo * lo / (W * H)
    if log:
        log(f'[uv] nested {len(islands)} islands into {W} x {H}: {lo:.0f} texels a metre '
            f'({1e3 / lo:.3f} mm a texel), fill {fill * 100:.1f} %')
    return lo, best, fill


def placed(U, s, rot, tx, ty, W, H):
    """an island's UVs in 0-1 over the W x H sheet (forge v up) from nest()'s placement"""
    c, sn = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    X = (U @ np.array([[c, sn], [-sn, c]])) * s
    X = X - X.min(0) + np.array([tx, ty])
    return X / np.array([W, H], float)


# -------------------------------------------------------------------------------------------------- instances
def mirror_x(part):
    """a capsule's exact mirror across the foot's midline: the same texels (the pair stacks), the winding
    reversed, the tangent's handedness flipped"""
    M = np.array([-1.0, 1.0, 1.0])
    out = dict(part, V=part['V'] * M, N=part['N'] * M, F=part['F'][:, ::-1].copy())
    if 'TAN' in part:
        out['TAN'] = np.column_stack([part['TAN'][:, :3] * M, -part['TAN'][:, 3]])
    return out


def partner(part, F, HL):
    """the primary claw's low placed as its partner on the foot (hoof.pair: mirrored, then scaled about the pair's
    centre): the same texels"""
    _, s, c = HF.pair(F, HL)[1]
    return moved(mirror_x(part), t=c * (1.0 - s), scale=s)


def moved(part, R=None, t=None, scale=1.0):
    """a capsule turned by R, scaled about the origin and moved: the same texels. R is a rotation, or a rotation
    with a mirror in it (det -1: the medial dewclaw's frame, hoof.dewclaw_frames): then the capsule is mirrored AS
    DATA, as mirror_x does it: the winding turned, the tangent's handedness flipped"""
    R = np.eye(3) if R is None else np.asarray(R, float)
    t = np.zeros(3) if t is None else np.asarray(t, float)
    flip = np.linalg.det(R) < 0.0
    out = dict(part, V=(part['V'] * scale) @ R.T + t, N=part['N'] @ R.T)
    if flip:
        out['F'] = part['F'][:, ::-1].copy()
    if 'TAN' in part:
        out['TAN'] = np.column_stack([part['TAN'][:, :3] @ R.T, -part['TAN'][:, 3] if flip else part['TAN'][:, 3]])
    return out


def merged(parts):
    """capsules as one mesh: V, N, TAN, UV, F, and `part` (per triangle: the index into parts)"""
    out, n0 = dict(V=[], N=[], TAN=[], UV=[], F=[], part=[], region=[]), 0
    for i, pt in enumerate(parts):
        for k in ('V', 'N', 'TAN', 'UV'):
            out[k].append(pt[k])
        out['F'].append(pt['F'] + n0)
        out['part'].append(np.full(len(pt['F']), i))
        out['region'].append(pt['region'])
        n0 += len(pt['V'])
    return {k: np.concatenate(v) for k, v in out.items()}
