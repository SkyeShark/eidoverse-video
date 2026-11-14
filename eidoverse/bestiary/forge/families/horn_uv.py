"""THE HORN'S UVS: one texture set for a pair of horns, with the plan's three kinds of reuse
(work/bestiary/research/DEER_PLAN.md §5.4; craft guide ch. 07: 07.2 plan the reuse first, 07.3 unique texels where
the occlusion depends on the place, 07.6 seams where they hide, 07.14 unwrap by construction, 07.31-07.33 stacks;
Skye's notes feedback_stack_identical_parts_uvs / feedback_texture_budget_fix_islands_not_sets; HIGH_TO_LOW "UVs").

    L = layout(skel, cage, size, cap)      the islands of a cage (horn_cage.cage), packed on ONE size^2 page
    M = split_mesh(cage, L)                the low as it ships: vertices split at the UV seams, triangles, welded
                                           normals, which triangles the bake reads (primaries only)

THE ISLANDS of an antler, few and large:
  beam_a, beam_b   the beam's tube, cut along ONE column that no fork's block touches and across at one ring (the
                   whole strip is 0.95 m: longer than a 2048 page at the set's density). UNIQUE (the hero rule)
  burr             the rim's four rows as their own strip (the burr template: its nodules need the texels)
  <tine>           a hero tine's shaft (brow, tray): UNIQUE
  <class>          ONE TEMPLATE per tine class (the preset's `classes`): the largest member's shaft is unwrapped and
                   baked; every other member takes its texels by its own (along, around) coordinates: the row's
                   share of the shaft, the column from the seam. Members of a class are drawn with one ring table
                   (horn_cage), so on the slice this is corner for corner
  <tine>.saddle    each fork's saddle with its 4 -> 2 reducer: UNIQUE (every fork's crotch shadow and blend are its
                   own: 07.3), cut in the crotch and unwrapped LSCM -> ARAP (a cone band keeps its sector)
  caps, seal       quad-grid domes, LSCM -> ARAP; the seal at half density (it sits on the pedicle)
The right horn is the left one mirrored AS DATA (x negated, winding turned, tangent w negated): it shares every
texel, so the pair costs one set (`mirror()`).

STRIPS ARE UNWRAPPED BY CONSTRUCTION from the branch's own measured section (07.14): x = the arc length round the
section from the seam, centred; y = the station along the branch. No solver, no fold, and the same function gives
the LODs their UVs in the same texels.
"""
import numpy as np

from .. import uv as UVT
from ..species import stag_beetle_uv as BU          # the house's raster packer (FFT feasibility scan), used as is
from . import horn as H

TWO_PI = 2.0 * np.pi
SHARE = dict(seal=0.5)                              # texel density shares; everything else 1


def _radius_grid(br, s, TH):
    v = [np.asarray(br.lerp(getattr(br, k), s))[:, None] for k in br.FIELDS]
    return H.section_radius(v[0], v[1], v[2], v[3], v[4], v[5], v[6], TH)


def section_arc(br, s, phi, th0, n=144):
    """the arc length round a branch's own section at stations s (M,) from the seam angle th0 to th0 + phi (M,;
    phi may pass 2 pi by a column), and the girth there"""
    s = np.asarray(s, np.float64)
    phi = np.asarray(phi, np.float64)
    g = np.linspace(0.0, TWO_PI, n + 1)
    TH = np.broadcast_to(th0 + g[None, :], (len(s), n + 1))
    r = _radius_grid(br, s, TH)
    x, y = r * np.cos(TH), r * np.sin(TH)
    cum = np.concatenate([np.zeros((len(s), 1)), np.cumsum(np.hypot(np.diff(x, axis=1), np.diff(y, axis=1)), axis=1)],
                         axis=1)
    turns = np.floor(phi / TWO_PI + 1e-12)
    turns = np.where(np.abs(phi - TWO_PI) < 1e-9, 0.0, turns)
    f = np.clip((phi - turns * TWO_PI) / TWO_PI * n, 0.0, n)
    j = np.minimum(np.floor(f).astype(int), n - 1)
    u = f - j
    rows = np.arange(len(s))
    return turns * cum[:, -1] + cum[rows, j] * (1.0 - u) + cum[rows, j + 1] * u, cum[:, -1]


def _unstraddle(phi, period):
    """per quad (n, 4): the corners of a quad that spans the seam are moved to the strip's far edge"""
    st = (phi.max(1) - phi.min(1)) > 0.5 * period
    return np.where(st[:, None] & (phi < 0.5 * period), phi + period, phi)


def strip_corners(br, s_v, th_v, Qs, th_seam):
    """corner UVs (n, 4, 2) in metres of a tube's quads Qs by construction: x the arc length round the branch's own
    section from the seam column (centred on the strip's middle line), y the station"""
    s = s_v[Qs]
    phi = np.mod(th_v[Qs] - th_seam, TWO_PI)
    phi[phi > TWO_PI - 1e-7] = 0.0
    phi = _unstraddle(phi, TWO_PI)
    arc, girth = section_arc(br, s.ravel(), phi.ravel(), th_seam)
    return np.stack([(arc - 0.5 * girth).reshape(-1, 4), s], -1)


def _tris_of(Qs, d02):
    """triangles of quads as the exporter splits them (mesh.QuadMesh.tris: the shorter diagonal), quad by quad:
    (2n, 3), the two triangles of quad i at rows 2i and 2i + 1"""
    a = np.where(d02[:, None], Qs[:, [0, 1, 2]], Qs[:, [0, 1, 3]])
    b = np.where(d02[:, None], Qs[:, [0, 2, 3]], Qs[:, [1, 2, 3]])
    return np.stack([a, b], 1).reshape(-1, 3)


def solve_island(V, Qs, d02, cut=None, iters=14):
    """a disk-like island's corner UVs (n, 4, 2) in metres: cut along `cut` (edges), LSCM, scaled to the 3D area,
    ARAP. Returns the corners and the island's own report"""
    ids, inv = np.unique(Qs, return_inverse=True)
    Ql = inv.reshape(Qs.shape)
    Vn, Qn, orig = UVT.split(V[ids], Ql, np.zeros(len(Ql), int),
                             seams=None if cut is None else np.searchsorted(ids, np.asarray(cut)))
    F = _tris_of(Qn, d02)
    U = UVT.lscm(Vn, F)
    a3 = 0.5 * np.linalg.norm(np.cross(Vn[F[:, 1]] - Vn[F[:, 0]], Vn[F[:, 2]] - Vn[F[:, 0]]), axis=1).sum()
    d1, d2 = U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]
    sa = 0.5 * (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum()
    U = U * np.sqrt(a3 / max(abs(sa), 1e-30))
    if sa < 0:
        U[:, 0] = -U[:, 0]
    U = UVT.arap(Vn, F, U, iters=iters)
    return U[Qn]


def aniso95(V, Qs, d02, corners):
    """an island's area-weighted p95 of s1 / s2 (the texel's worst stretch: 1 = square)"""
    F = _tris_of(np.arange(4 * len(Qs)).reshape(-1, 4), d02)
    P3 = V[Qs].reshape(-1, 3)
    s1, s2, ok = UVT.stretch(P3, F, corners.reshape(-1, 2))
    a3 = 0.5 * np.linalg.norm(np.cross(P3[F[:, 1]] - P3[F[:, 0]], P3[F[:, 2]] - P3[F[:, 0]]), axis=1)
    o = np.argsort((s1 / s2)[ok])
    cw = np.cumsum(a3[ok][o])
    return float((s1 / s2)[ok][o][min(np.searchsorted(cw, 0.95 * cw[-1]), len(o) - 1)])


def relax(V, Qs, d02, corners, iters=12):
    """a by-construction island evened out by ARAP from where it lies: its corners welded where they share a vertex
    AND a place (so its seams stay open), the solve started from the construction"""
    key = np.column_stack([Qs.ravel(), np.round(corners.reshape(-1, 2) * 1.0e7).astype(np.int64)])
    uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    Qn = inv.reshape(-1, 4)
    U = UVT.arap(V[uniq[:, 0]], _tris_of(Qn, d02), corners.reshape(-1, 2)[first], iters=iters)
    return U[Qn]


def _grid_lookup(G, rc, period):
    """corner UVs from a (rows, period + 1, 2) grid for corners at (row, col) pairs rc (n, 4, 2), the seam's quads
    taking the far column"""
    col = _unstraddle(rc[..., 1].astype(np.float64), period).astype(int)
    return G[rc[..., 0], col]


ORDERS = ('area', 'long', 'cells')


def _nest(PA, FA, PB, FB, pad, ds=4):
    """the shift t that seats wedge B, turned half round (p -> t - p), against wedge A's slanted edge (texels): the
    two masks, each grown by its pad, do not meet; their tops are level (B's wide base beside A's tip); on the side
    of A that gives the narrower pair"""
    a0 = PA.min(0) - pad
    mA = BU.island_mask(PA - a0, FA, pad, ds)
    b0 = (-PB).min(0) - pad
    mB = BU.island_mask(-PB - b0, FB, pad, ds)
    (hA, wA), (hB, wB) = mA.shape, mB.shape
    H = max(hA, hB)
    can = np.zeros((H, wA + 2 * wB), bool)
    can[H - hA:, wB:wB + wA] = mA
    best = None
    for slide in (range(0, wB + 1), range(wA + wB, wA - 1, -1)):          # from the left of A; from its right
        last = None
        for dx in slide:
            if (can[H - hB:, dx:dx + wB] & mB).any():
                break
            last = dx
        if last is not None:
            width = max(wB + wA, last + wB) - min(wB, last)
            if best is None or width < best[0]:
                best = (width, last)
    dx = best[1]
    return a0 - b0 + np.array([(dx - wB) * ds, (hA - hB) * ds], np.float64)


def split_at_paths(Qs, paths):
    """the quads Qs (n, 4) as the connected parts that the vertex paths leave (an edge on a path joins nothing):
    a list of index arrays, the part holding quad 0 first"""
    cut = set()
    for p in paths:
        cut |= {(min(int(a), int(b)), max(int(a), int(b))) for a, b in zip(p[:-1], p[1:])}
    edge = {}
    for i, q in enumerate(np.asarray(Qs)):
        for a, b in zip(q, np.roll(q, -1)):
            e = (min(int(a), int(b)), max(int(a), int(b)))
            if e not in cut:
                edge.setdefault(e, []).append(i)
    nb = [[] for _ in range(len(Qs))]
    for pair in edge.values():
        if len(pair) == 2:
            nb[pair[0]].append(pair[1])
            nb[pair[1]].append(pair[0])
    comp = -np.ones(len(Qs), int)
    n = 0
    for i0 in range(len(Qs)):
        if comp[i0] >= 0:
            continue
        comp[i0] = n
        todo = [i0]
        while todo:
            for j in nb[todo.pop()]:
                if comp[j] < 0:
                    comp[j] = n
                    todo.append(j)
        n += 1
    return [np.nonzero(comp == k)[0] for k in range(n)]


def _enclosed(occ):
    """the free cells the occupancy ENCLOSES (not reaching the page's border), or None
    (work/bestiary/human/aletheia/head_low/s31_uv_pack.py holes_of, copied)"""
    from scipy import ndimage
    lab, n = ndimage.label(~occ)
    if n == 0:
        return None
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    inner = np.setdiff1d(np.arange(1, n + 1), edge)
    return np.isin(lab, inner) if len(inner) else None


def pack_page(pk, size, ds=4, order='area', seq=None, place='contact'):
    """the islands `pk` (dicts of uvt in texels, F, pad) on ONE size^2 page, or None. The stag beetle's raster packer
    (stag_beetle_uv.pack: an FFT feasibility scan of the occupancy bitmap, its island_mask) with three changes a set
    of TAPERING strips needs (07.25 "try several orders ... replace a packer that plateaus"): all four quarter turns
    (a spindle turned half round nests head to tail in the gap beside another's tip: turns 0 / 90 alone packed this
    set at 3,447 px/m, 55.9 % full), a choice of orders, and the PLACEMENT RULE:
      'contact'  the head round's (work/bestiary/human/aletheia/head_low/s31_uv_pack.py `place`, the technique
                 copied; HIGH_TO_LOW "UVs": 69.8 -> 71.4 % on the head with it alone): an island that fits inside a
                 region the others ENCLOSE goes there first (a fork's hole in a beam strip takes the tip caps and the
                 seal), else to the free spot whose outline touches the most occupied cells or the page's border;
                 ties go low, then left
      'top'      where its top edge comes lowest (the first rule here: 3,595 px/m, 60.7 % full on D1)"""
    from scipy import ndimage
    from scipy.signal import fftconvolve
    G = size // ds
    occ = np.zeros((G, G), bool)
    key = dict(area=lambda e: -float(np.ptp(e['uvt'][:, 0]) * np.ptp(e['uvt'][:, 1])),
               long=lambda e: -float(max(np.ptp(e['uvt'][:, 0]), np.ptp(e['uvt'][:, 1]))),
               cells=lambda e: -float(e.get('cells', 0.0)))[order]
    out = [None] * len(pk)
    f32 = lambda a: np.asarray(a, np.float32)                                              # noqa: E731
    for i in (sorted(range(len(pk)), key=lambda i: key(pk[i])) if seq is None else seq):
        e = pk[i]
        best = None
        hole = _enclosed(occ) if place == 'contact' else None
        for rot in range(4):
            if rot >= len(e['masks']):
                T = e['uvt'].copy()
                for _ in range(rot):
                    T = np.column_stack([-T[:, 1], T[:, 0]])
                T = T - T.min(0) + e['pad']
                e['masks'].append((T, BU.island_mask(T[:e['n_own']], e['F'], e['pad'], ds)))
            T, m = e['masks'][rot]
            if m.shape[0] > G or m.shape[1] > G:
                continue
            free = fftconvolve(f32(occ), f32(m[::-1, ::-1]), mode='valid') < 0.5
            if not free.any():
                continue
            if place == 'contact':
                in_hole = False
                if hole is not None:
                    ih = fftconvolve(f32(~hole), f32(m[::-1, ::-1]), mode='valid') < 0.5
                    if (free & ih).any():
                        free, in_hole = free & ih, True
                mp = np.pad(m, 1)
                ring = ndimage.binary_dilation(mp) & ~mp
                ct = fftconvolve(f32(np.pad(occ, 1, constant_values=True)), f32(ring[::-1, ::-1]), mode='valid')
                score = np.where(free, np.rint(ct), -1.0)
                y, x = divmod(int(np.argmax(score)), score.shape[1])    # the first maximum in row order: low, left
                cand = ((0 if in_hole else 1, -float(score[y, x]), int(y), int(x), rot), int(y), int(x), rot)
            else:
                ok = np.argwhere(free)
                tops = ok[:, 0] + m.shape[0]
                k = np.lexsort((ok[:, 1], tops))[0]
                cand = ((int(tops[k]), int(ok[k, 1]), int(ok[k, 0]), rot), int(ok[k, 0]), int(ok[k, 1]), rot)
            if best is None or cand[0] < best[0]:
                best = cand
        if best is None:
            return None
        _, y, x, rot = best
        T, m = pk[i]['masks'][rot]
        occ[y:y + m.shape[0], x:x + m.shape[1]] |= m
        out[i] = dict(uv=(T + np.array([x * ds, y * ds])) / size, rot=rot)
    return out, float(occ.mean())


def conformal_fill(V, F, pin, pin_uv, flip=False):
    """the least-squares conformal map (LSCM, Levy et al. 2002) of a triangle patch (V (n, 3), F (t, 3)) with the
    vertices `pin` HELD at pin_uv (n_pin, 2) and every other vertex free: (n, 2). Angles are kept as well as the
    held outline lets them; the scale is free. flip: the held outline runs the other way round in UV than on the
    surface (a mirrored chart)"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    V, F = np.asarray(V, np.float64), np.asarray(F)
    n, T = len(V), len(F)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    l1 = np.linalg.norm(b - a, axis=1)
    e1 = (b - a) / np.maximum(l1, 1e-30)[:, None]
    nrm = np.cross(b - a, c - a)
    A2 = np.linalg.norm(nrm, axis=1)                                     # twice the area
    e2 = np.cross(nrm / np.maximum(A2, 1e-30)[:, None], e1)
    x = np.column_stack([np.zeros(T), l1, ((c - a) * e1).sum(1)])        # each triangle in its own plane
    y = np.column_stack([np.zeros(T), np.zeros(T), ((c - a) * e2).sum(1)])
    w = 1.0 / np.sqrt(np.maximum(A2, 1e-30))
    Wr = np.column_stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]]) * w[:, None]
    Wi = np.column_stack([y[:, 2] - y[:, 1], y[:, 0] - y[:, 2], y[:, 1] - y[:, 0]]) * w[:, None]
    rows, cols = np.repeat(np.arange(T), 3), F.ravel()
    # sum_j W_j (u_j + i v_j) = 0 per triangle: its real part, then its imaginary part
    M = coo_matrix((np.concatenate([Wr.ravel(), -Wi.ravel(), Wi.ravel(), Wr.ravel()]),
                    (np.concatenate([rows, rows, rows + T, rows + T]),
                     np.concatenate([cols, cols + n, cols, cols + n]))), shape=(2 * T, 2 * n)).tocsc()
    pin = np.asarray(pin, int)
    P = np.asarray(pin_uv, np.float64).copy()
    if flip:
        P[:, 1] = -P[:, 1]
    free = np.setdiff1d(np.arange(n), pin)
    Mf = M[:, np.concatenate([free, free + n])]
    rhs = -(M[:, np.concatenate([pin, pin + n])] @ np.concatenate([P[:, 0], P[:, 1]]))
    sol = spsolve((Mf.T @ Mf).tocsc(), Mf.T @ rhs)
    U = np.zeros((n, 2))
    U[pin] = P
    U[free, 0], U[free, 1] = sol[:len(free)], sol[len(free):]
    if flip:
        U[:, 1] = -U[:, 1]
    return U


def _cells(rc, period):
    """per quad of a (row, column) grid: its cell (the least row, the least column, the seam's quads at the far
    column) and whether its corners 0-2 are the diagonal that runs up the rows as the columns grow"""
    col = _unstraddle(rc[..., 1].astype(np.float64), period).astype(int)
    row = rc[..., 0]
    k0 = np.argmin(row * (period + 2) + col, axis=1)
    return row.min(1), col.min(1), (k0 % 2) == 0


def layout(skel, c, size=2048, cap=4200.0, mode='default', log=print, tries=14, saddle='halves',
           places=('contact', 'top'), shares=None):
    """the UV islands of a cage `c` (horn_cage.cage), packed. mode: 'default' the preset's classes; 'hero' every tine
    its own texels (close-ups); 'crowd' every tine on one template (distant herds). saddle: 'beam' each fork's
    saddle inside its beam piece's island (in the hole its block left: no seam round the fork's foot), 'halves' as
    two islands, 'whole' as one star (the first layout). places: the packer's placement rules to try.
    Returns a dict: corner (nq, 4, 2) UVs in 0-1 (v up), island (nq,), d02 (nq,: the diagonal each quad is split
    along), islands (the table), density (px/m), fill, size, and what a second LOD needs to land in the same texels
    (`charts`)"""
    mesh = c['mesh']
    V, Q, lab, S = mesh.V, mesh.Q, c['labels'].astype(str), c['islands']
    s_v, th_v = c['s'], c['theta']
    nq = len(Q)
    d02 = np.linalg.norm(V[Q[:, 0]] - V[Q[:, 2]], axis=1) <= np.linalg.norm(V[Q[:, 1]] - V[Q[:, 3]], axis=1)
    beam = skel['beam'] if skel.family == 'antler' else skel.branches[0]
    isl = []                 # dict(name, kind, quads, corners (metres), share, of (the template's index or None))
    rings = S['beam']['rings']
    K = rings.shape[1]
    row_of = -np.ones(len(V), int)
    col_of = -np.ones(len(V), int)
    for r in range(rings.shape[0]):
        ok = rings[r] >= 0
        row_of[rings[r][ok]] = r
        col_of[rings[r][ok]] = np.arange(K)[ok]
    # ------------------------------------------------------------------ the beam's seam column
    # one column no fork's block touches (a block is a hole in the tube), on a reducer unit's boundary (the beam's
    # own 4 -> 2 reducer has an edge from the outer to the inner ring only every fourth column)
    # THE BEAM'S SEAM: a column whose vertices all exist (it may run along a block's edge, where the saddle's own
    # border is; never through a block), on a reducer unit's boundary, and of those the one nearest the beam's
    # back-medial side (theta 225 deg: theta 0 is the tines' front, 90 the outer side on the left antler), the
    # side a viewer in front of or beside the stag sees least (07.6). On D1 the five blocks leave columns 4, 8 and
    # 16 of 24: column 16, at 240 deg
    qb = np.nonzero(lab == 'beam')[0]
    rq = row_of[Q[qb]]
    th_cols = np.asarray(S['beam']['theta'])
    cand = [k for k in range(0, K, 4 if K % 4 == 0 else 1) if (rings[:, k] >= 0).all()]
    assert cand, 'no beam column is free of the fork blocks'
    k_seam = min(cand, key=lambda k: abs(np.angle(np.exp(1j * (th_cols[k] - 1.25 * np.pi)))))
    # (fix round 1: the cage picks the same column by the same rule and starts the beam top's reducers on it)
    assert int(S['beam'].get('k_seam', k_seam)) == k_seam, ('the cage and the layout chose different seams',
                                                             S['beam'].get('k_seam'), k_seam)
    th_beam = float(th_cols[k_seam])
    # ------------------------------------------------------------------ burr (its rows: `nb` below), the beam's pieces
    # THE BEAM IS CUT ACROSS INTO NEAR-RECTANGLES (07.7 "a few cuts purely for packing"): the TRUNK (from the burr
    # to the first whole ring where the girth is within 12 % of the beam's own, 16 -> 124 mm on D1: it is 1.5x as
    # wide as the rest), the tube above it in equal pieces no longer than a page holds at the cap density, and the
    # TOP (past the beam's reducer: a spindle, like a tine). Two pieces (16 -> 505 -> tip) packed at 3,536 px/m,
    # 59 % full: the trunk's flare and the top's taper each held a band of the page empty
    st = np.asarray(S['beam']['s'])
    top_q = np.nonzero(lab == 'beam_top')[0]
    whole = np.array([(rings[r] >= 0).all() for r in range(rings.shape[0])])
    # the burr's last row (the beam over the rim): the cage says how many rows it drew the burr with (11-12: five,
    # horn_cage.BURR_ROWS; the first drawing's four where a cage does not say)
    nb = int(S['beam'].get('burr_rows', 4)) - 1
    g_ref = beam.girth(float(st[nb] + 0.4 * (st[-1] - st[nb])))
    r_trunk = next((r for r in range(nb + 1, len(st) - 1) if whole[r] and beam.girth(float(st[r])) <= 1.12 * g_ref), nb)
    n_p = max(1, int(np.ceil((st[-1] - st[r_trunk]) / (0.92 * size / cap))))
    cuts = [nb] + ([r_trunk] if r_trunk > nb else [])
    for j in range(1, n_p):
        want = st[r_trunk] + (st[-1] - st[r_trunk]) * j / n_p
        cuts.append(int(min((r for r in range(cuts[-1] + 1, len(st) - 1) if whole[r]), key=lambda r: abs(st[r] - want))))
    cuts.append(len(st) - 1)
    rmax, rmin = rq.max(1), rq.min(1)
    burr_q = qb[rmax <= nb]
    pieces = [(f'beam_{chr(97 + j)}', qb[(rmin >= a) & (rmax <= b)]) for j, (a, b) in enumerate(zip(cuts[:-1], cuts[1:]))]
    # the burr is a FLANGE (the seal's edge r 30 mm, the rim 39, the beam over it 34, in 16 mm): laid out as a
    # straight strip its rows shear 28 mm against each other over 5 mm (anisotropy p95 8.5, measured). A cone band
    # keeps its sector (HIGH_TO_LOW "UVs"): cut at the beam's seam column, LSCM -> ARAP
    # ... and in THREE segments round the beam: whole, the band unrolls as a 100 degree arc whose box is five times
    # its area; a third of it is nearly straight (a wall cut at its turns, HIGH_TO_LOW "UVs" on the head's plates)
    cb = (col_of[Q[burr_q]] - k_seam) % K
    cb0 = np.where((cb.max(1) - cb.min(1)) > K // 2, cb.max(1), cb.min(1))
    n_seg = 3
    for j in range(n_seg):
        m_ = (cb0 * n_seg // K) == j
        isl.append(dict(name=f'burr_{chr(97 + j)}', kind='sector', quads=burr_q[m_],
                        corners=solve_island(V, Q[burr_q[m_]], d02[burr_q[m_]]), share=1.0, of=None))
    tine_names = [nm for nm, d in S.items() if d.get('kind') == 'tine']
    # each fork's saddle belongs to the beam piece that holds the most of its port's loop
    p_verts = {nm_: set(np.unique(Q[q_]).tolist()) for nm_, q_ in pieces}
    owner = {tn: max(p_verts, key=lambda nm_: sum(int(v_) in p_verts[nm_] for v_ in S[tn]['saddle'][0]))
             for tn in tine_names}

    def lay_saddles(nm_, q_, cs0, cs):
        """A FORK'S SADDLE LIES IN THE HOLE ITS BLOCK LEFT IN THE BEAM'S STRIP (saddle='beam'). The port's loop is
        the hole's own outline: the loop stays where the tube's corners put it and the saddle's inner vertices are
        the least-squares CONFORMAL map with that outline held (conformal_fill): angles kept, so texels stay
        square, and the SCALE gives. It must: a saddle is a collar with more skin than the hole it stands on (a
        fillet is saddle-curved: no cut makes it lie flat without overlap), so its texels are smaller on the
        surface toward ring C; the scale's p5 / p50 / p95 per fork is returned and reported.
        TRIED AND MEASURED FIRST (build/look/h07_uv_f / _g / _h): the outline drawn in and ARAP over the whole
        piece keeps the lengths, squashes ring C to a slit and crumples the crotch end (8 flipped triangles, 8,904
        texels covered twice); each column drawn straight in at one scale shears (the pieces' anisotropy p95
        1.8-2.4).
        The saddle is taken as far as ring C, where the tine's own tube begins; the REDUCER above it goes with the
        shaft's wedges (in the hole too it crumpled: h07_uv_f). No seam is left round a fork's foot, the strips
        have no holes, no saddle is an island: 29 islands -> 19.
        cs0 / cs: the tube's corners by construction / as they stand (relaxed or not). Returns the piece's quads and
        corners with its forks' saddles, and per fork the texel scale's p5 / p50 / p95 against the tube's"""
        pair = {}
        for qq, c0, c1 in zip(Q[q_], cs0, cs):
            for v_, a_, b_ in zip(qq, c0, c1):
                pair.setdefault(int(v_), []).append((a_, b_))
        Ft = _tris_of(np.arange(4 * len(q_)).reshape(-1, 4), d02[q_])   # which way round the tube's chart runs
        P2 = cs.reshape(-1, 2)
        g1, g2 = P2[Ft[:, 1]] - P2[Ft[:, 0]], P2[Ft[:, 2]] - P2[Ft[:, 0]]
        turn = float((g1[:, 0] * g2[:, 1] - g1[:, 1] * g2[:, 0]).sum())
        qs_all, cs_all, joined = [q_], [cs], {}
        for tn in tine_names:
            if owner[tn] != nm_:
                continue
            sad = [np.asarray(r) for r in S[tn]['saddle']]
            loop = sad[0]
            # the loop's places by the strip's construction. A block may lie against the beam's seam column (D1's
            # crown_c) or against a cross cut (D1's bay: its block's upper edge IS the trunk's cut ring): its hole
            # is then a NOTCH in the strip's edge, and a loop vertex there takes the place on the BLOCK's side
            # (the tube's quads beside the block give it only the far edge's place, or none in this piece)
            phi = np.mod(th_v[loop] - th_beam, TWO_PI)
            phi[phi > TWO_PI - 1e-7] = 0.0
            on = col_of[loop] == k_seam
            assert (~on).sum() >= 3, (tn, 'a fork block astride the beam\'s seam')
            phi[on] = 0.0 if float(phi[~on].mean()) < np.pi else TWO_PI
            arc, girth = section_arc(beam, s_v[loop], phi, th_beam)
            Lc = np.column_stack([arc - 0.5 * girth, s_v[loop]])
            # ... carried to where the tube's corners stand now: the corner itself where the piece has one at that
            # place, else (a notch's open side) by the affine map the loop's other vertices make
            L2 = np.full_like(Lc, np.nan)
            for j, v_ in enumerate(loop):
                for a_, b_ in pair.get(int(v_), ()):
                    if np.linalg.norm(a_ - Lc[j]) < 1.0e-6:
                        L2[j] = b_
            have = ~np.isnan(L2[:, 0])
            if not have.all():
                A_ = np.linalg.lstsq(np.column_stack([Lc[have], np.ones(int(have.sum()))]), L2[have], rcond=None)[0]
                L2[~have] = np.column_stack([Lc[~have], np.ones(int((~have).sum()))]) @ A_
            sv = np.unique(np.concatenate(sad))
            in_s = np.zeros(len(V), bool)
            in_s[sv] = True
            qs_ = np.array([i_ for i_ in np.nonzero(lab == tn + '.saddle')[0] if in_s[Q[i_]].all()], int)
            loc = -np.ones(len(V), int)
            loc[sv] = np.arange(len(sv))
            Fs = loc[_tris_of(Q[qs_], d02[qs_])]
            if 'K_rows' in S[tn]:
                # FIX ROUND 1: the saddle ends AT ring C (the shaft's wedges start there), so ring C is HELD too: the
                # hole's own outline scaled about its middle by lambda = ring C's length over the hole's (ring C's
                # texels then come out near the set's density), vertex j of ring C on loop vertex j's line from the
                # middle (the cage ties ring C's vertex j to the loop's vertex j: every column of the saddle runs
                # straight in, nothing twists). With ring C free the conformal fill collapsed it to a sliver where a
                # tine leaves at a slant (the tray, both crown tines: 15 flipped triangles, 26,802 texels twice,
                # the first `_v4` trial). The bridge rings between: the conformal fill; a straight ruling of each
                # column if that flips anything
                # WHERE RING C GOES: the hole's outline OFFSET INWARD by each column's own 3D length (loop vertex j
                # to ring C vertex j over the bridge rings), times one kappa <= 1 (the largest that leaves the inner
                # polygon simple, wound as the hole, and 4 mm across): the saddle's natural flat shape, long on the
                # crotch side and short on the open side. (The hole scaled about its middle, the trial before, ruled
                # the crotch side's 30-50 mm columns into 10-20 mm: anisotropy p95 3.4-4.3, uv_f1beam.log)
                cum = np.zeros((len(sad), len(loop)))
                for r_ in range(1, len(sad)):
                    cum[r_] = cum[r_ - 1] + np.linalg.norm(V[sad[r_]] - V[sad[r_ - 1]], axis=1)
                hcol = cum[-1]
                ar = 0.5 * float(np.sum(L2[:, 0] * np.roll(L2[:, 1], -1) - np.roll(L2[:, 0], -1) * L2[:, 1]))
                e_in = np.roll(L2, -1, axis=0) - L2
                e_in /= np.maximum(np.linalg.norm(e_in, axis=1, keepdims=True), 1e-12)
                nl = np.column_stack([-e_in[:, 1], e_in[:, 0]]) * (1.0 if ar > 0 else -1.0)   # inward, per edge
                nv = nl + np.roll(nl, 1, axis=0)                                              # per vertex: miter
                nv /= np.maximum((nv * nl).sum(1, keepdims=True), 1e-6)

                def simple_ok(P_):
                    a_ = 0.5 * float(np.sum(P_[:, 0] * np.roll(P_[:, 1], -1) - np.roll(P_[:, 0], -1) * P_[:, 1]))
                    if a_ * ar <= 0.0 or abs(a_) < 1.6e-5:
                        return False
                    A_, B_ = P_, np.roll(P_, -1, axis=0)
                    n_ = len(P_)
                    for i_ in range(n_):
                        for j_ in range(i_ + 2, n_):
                            if i_ == 0 and j_ == n_ - 1:
                                continue
                            d1, d2 = B_[i_] - A_[i_], B_[j_] - A_[j_]
                            den = d1[0] * d2[1] - d1[1] * d2[0]
                            if abs(den) < 1e-18:
                                continue
                            w_ = A_[j_] - A_[i_]
                            t1 = (w_[0] * d2[1] - w_[1] * d2[0]) / den
                            t2 = (w_[0] * d1[1] - w_[1] * d1[0]) / den
                            if 0.0 < t1 < 1.0 and 0.0 < t2 < 1.0:
                                return False
                    return True
                kap = 1.0
                while kap > 0.2 and not simple_ok(L2 + kap * hcol[:, None] * nv):
                    kap *= 0.93
                C2 = L2 + kap * hcol[:, None] * nv
                pins = np.concatenate([loc[loop], loc[sad[-1]]])
                Us = conformal_fill(V[sv], Fs, pins, np.vstack([L2, C2]), flip=turn < 0.0)
                e1_, e2_ = Us[Fs[:, 1]] - Us[Fs[:, 0]], Us[Fs[:, 2]] - Us[Fs[:, 0]]
                sgn = np.sign(e1_[:, 0] * e2_[:, 1] - e1_[:, 1] * e2_[:, 0])
                if (sgn != np.sign(np.median(sgn))).any():
                    # the conformal fill flipped a triangle: each column RULED at its own 3D shares instead
                    for r_ in range(1, len(sad) - 1):
                        Us[loc[sad[r_]]] = L2 + (cum[r_] / np.maximum(hcol, 1e-12))[:, None] * (C2 - L2)
                    joined.setdefault('_ruled', []).append(tn)
                joined.setdefault('_kappa', {})[tn] = round(kap, 3)
            else:
                Us = conformal_fill(V[sv], Fs, loc[loop], L2, flip=turn < 0.0)
            a3 = 0.5 * np.linalg.norm(np.cross(V[sv][Fs[:, 1]] - V[sv][Fs[:, 0]], V[sv][Fs[:, 2]] - V[sv][Fs[:, 0]]),
                                      axis=1)
            e1, e2 = Us[Fs[:, 1]] - Us[Fs[:, 0]], Us[Fs[:, 2]] - Us[Fs[:, 0]]
            sc = np.sqrt(np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) * 0.5 / np.maximum(a3, 1e-30))
            o = np.argsort(sc)
            cw = np.cumsum(a3[o]) / a3.sum()
            qs_all.append(qs_)
            cs_all.append(Us[loc[Q[qs_]]])
            joined[tn] = [round(float(sc[o][np.searchsorted(cw, p_)]), 2) for p_ in (0.05, 0.5, 0.95)]
        return np.concatenate(qs_all), np.concatenate(cs_all), joined

    for nm_, q_ in pieces:
        cs0 = strip_corners(beam, s_v, th_v, Q[q_], th_beam)
        cs = cs0
        a0_ = aniso95(V, Q[q_], d02[q_], cs0)
        if a0_ > 1.25:
            # the construction assumes a straight tube. D1's trunk turns 41 degrees at the brow on a radius of its
            # own thickness (the outer side 76 mm long, the inner 28, the strip 52 for both: p95 1.93) and its
            # vertices by the forks stand out on the saddles: ARAP evens it out, starting from the construction
            cr = relax(V, Q[q_], d02[q_], cs0)
            a1_ = aniso95(V, Q[q_], d02[q_], cr)
            log(f'[horn_uv] {nm_}: anisotropy p95 {a0_:.2f} by construction, {a1_:.2f} relaxed')
            cs = cr if a1_ < a0_ else cs0
        joined = {}
        if saddle == 'beam':
            q_, cs, joined = lay_saddles(nm_, q_, cs0, cs)
            log(f'[horn_uv] {nm_} with its forks\' saddles laid in (fork: texel scale p5 / p50 / p95) {joined}: '
                f'anisotropy p95 {aniso95(V, Q[q_], d02[q_], cs):.2f}')
        isl.append(dict(name=nm_, kind='strip', quads=q_, corners=cs, share=1.0, of=None, forks=joined))
    if len(top_q):
        # the top as TWO HALF WEDGES (see the tines below): the strip's own middle line is the second cut
        ct = strip_corners(beam, s_v, th_v, Q[top_q], th_beam)
        left = ct[..., 0].mean(1) < 0.0
        for half, m_ in (('a', left), ('b', ~left)):
            isl.append(dict(name=f'beam_top.{half}', kind='strip', quads=top_q[m_], corners=ct[m_], share=1.0, of=None,
                            wedge=half))
    charts = dict(beam=dict(th_seam=th_beam, k_seam=k_seam, s_cuts=[float(st[r]) for r in cuts]))
    # ------------------------------------------------------------------ caps and the seal
    for nm in sorted(set(lab)):
        if nm.endswith('.cap') or nm == 'seal':
            q = np.nonzero(lab == nm)[0]
            isl.append(dict(name=nm, kind='cap', quads=q, corners=solve_island(V, Q[q], d02[q]),
                            share=SHARE.get(nm, 1.0), of=None))
    # ------------------------------------------------------------------ the tines: saddle (unique) + shaft
    tines = [nm for nm, d in S.items() if d.get('kind') == 'tine']
    pr_cls = skel.preset.get('classes', {})
    cls = {}
    for nm in tines:
        k_ = next((k for k, m in pr_cls.items() if nm in m), 'hero')
        cls[nm] = 'hero' if mode == 'hero' else ('all' if mode == 'crowd' else k_)
    grids, shafts = {}, {}
    for nm in tines:
        d = S[nm]
        br = skel[nm]
        if 'K_rows' in d:
            # THE CAGE OF FIX ROUND 1 (horn_cage `shaft_k`): the shaft starts AT ring C (tilted, un-tilting) and
            # changes K on the way (24 -> 16 -> 12): every shaft quad, its reducers' included, takes the strip's
            # construction by its own vertices' (station, angle) from the crotch column (each ring's first vertex,
            # where every reducer leaves an edge straight up); the halves part at the strip's middle line (each
            # ring's middle vertex: a pattern boundary too). A class member takes its template's corners QUAD FOR
            # QUAD (one topology: asserted by each corner's ring and place in it)
            rows = [np.asarray(r) for r in d['shaft']]
            key = {}
            for r_, row in enumerate(rows):
                key.update({int(v_): (r_, j_) for j_, v_ in enumerate(row)})
            for k_, rd_ in enumerate(d.get('reducers', [])):
                key.update({int(v_): (1000 + k_, j_) for j_, v_ in enumerate(np.asarray(rd_['mids']))})
            th_seam = float(th_v[rows[0][0]])
            qs = np.nonzero(lab == nm)[0]
            cs = strip_corners(br, s_v, th_v, Q[qs], th_seam)
            hf = np.where(cs[..., 0].mean(1) < 0.0, 0, 1)
            area = float(0.5 * np.linalg.norm(np.cross(V[Q[qs, 2]] - V[Q[qs, 0]], V[Q[qs, 3]] - V[Q[qs, 1]]),
                                              axis=1).sum())
            shafts[nm] = dict(quads=qs, corners=cs, half=hf, area=area, th_seam=th_seam,
                              keys=[tuple(key[int(v_)] for v_ in qq) for qq in Q[qs]], v2=True)
            q = np.nonzero(lab == nm + '.saddle')[0]
            if saddle == 'corners':
                # A SADDLE IN FOUR BANDS, cut up the columns that leave the port loop's four corners (the block's
                # corners on the beam): each band is 8 or 4 of the loop's edges wide and the saddle's rings tall, a
                # near-trapezoid that LSCM -> ARAP lays nearly flat, and small enough to go into the hole its own
                # block leaves in the beam's strip (the packer seats an island in an ENCLOSED hole first). Laid IN
                # the hole whole (saddle='beam'), every fork's fill flipped and its ruled fallback stretched the
                # saddle's texels 3.4-4.3 : 1 (fix round 1's first trial, build/tmp/fix1/uv_f1beam.log)
                sad = [np.asarray(r) for r in d['saddle']]
                lp = sad[0]
                rr_ = row_of[lp]
                # the corners are where the loop turns: its step before and after point along different grid axes
                corner = [j_ for j_ in range(len(lp))
                          if (rr_[(j_ - 1) % len(lp)] == rr_[j_]) != (rr_[(j_ + 1) % len(lp)] == rr_[j_])]
                assert len(corner) == 4, (nm, 'a port loop with corners', corner)
                parts = split_at_paths(Q[q], [[int(r[j_]) for r in sad] for j_ in corner])
                assert len(parts) == 4, (nm, 'the saddle did not part in four', [len(p_) for p_ in parts])
                for h_, qh in zip('abcd', parts):
                    isl.append(dict(name=f'{nm}.saddle.{h_}', kind='sector', quads=q[qh],
                                    corners=solve_island(V, Q[q[qh]], d02[q[qh]]), share=1.0, of=None))
            if saddle in ('whole', 'halves'):
                sad = [np.asarray(r) for r in d['saddle']]
                jc = int(np.nonzero(sad[-1] == rows[0][0])[0][0])
                Kc = len(sad[0])
                path = [int(r[jc]) for r in sad]
                if saddle == 'whole':
                    cut = np.array([[a, b] for a, b in zip(path[:-1], path[1:])])
                    isl.append(dict(name=nm + '.saddle', kind='sector', quads=q,
                                    corners=solve_island(V, Q[q], d02[q], cut=cut), share=1.0, of=None))
                else:
                    path_o = [int(r[(jc + Kc // 2) % Kc]) for r in sad]
                    parts = split_at_paths(Q[q], [path, path_o])
                    assert len(parts) == 2, (nm, 'the saddle did not part in two', [len(p_) for p_ in parts])
                    for h_, qh in zip('ab', parts):
                        isl.append(dict(name=f'{nm}.saddle.{h_}', kind='sector', quads=q[qh],
                                        corners=solve_island(V, Q[q[qh]], d02[q[qh]]), share=1.0, of=None))
            continue
        rows = [np.asarray(r) for r in d['shaft']]
        Ks = len(rows[0])
        red = d.get('reducer')
        ang0 = np.angle(np.exp(1j * th_v[rows[0]]))                 # the start ring's angles about the tine: 0 = crotch
        if red is not None:
            # the cut runs up a reducer unit's boundary (outer vertex 4u to inner vertex 2u), the one nearest the crotch
            inner = np.asarray(red['inner'])
            u_s = int(np.argmin(np.abs(np.angle(np.exp(1j * th_v[inner[::2]])))))
            j_seam = int(np.nonzero(rows[0] == inner[2 * u_s])[0][0])
            Rr = np.asarray(red['outer'])
            sad = [np.asarray(r) for r in d['saddle']]
            jc = int(np.nonzero(sad[-1] == Rr[4 * u_s])[0][0])
            path = [int(r[jc]) for r in sad] + [int(inner[2 * u_s])]
        else:
            j_seam = int(np.argmin(np.abs(ang0)))
            sad = [np.asarray(r) for r in d['saddle']]
            jc = int(np.nonzero(sad[-1] == rows[0][j_seam])[0][0])
            path = [int(r[jc]) for r in sad]
        q = np.nonzero(lab == nm + '.saddle')[0]
        if saddle == 'beam':
            pass                                    # it lies in its beam piece's island (join_saddles)
        elif saddle == 'whole':
            cut = np.array([[a, b] for a, b in zip(path[:-1], path[1:])])
            isl.append(dict(name=nm + '.saddle', kind='sector', quads=q,
                            corners=solve_island(V, Q[q], d02[q], cut=cut), share=1.0, of=None))
        else:
            # A SADDLE IS TWO ARCHES. Seen from the tine's axis a saddle is a WASHER (the port's loop of 2(a + b)
            # beam edges outside, the tine's ring inside, nearly flat): cut once it unrolls as a four-pointed star
            # with a hole, 45 % of its box, and the five of them held a fifth of the page for 6.6 % of its texels
            # (build/look/h07_uv_d.png). Cut again along the line OPPOSITE the crotch (where the shaft's own second
            # seam, the wedges' middle line, already runs) each half is an arch that nests against its neighbours
            Kc = len(sad[0])
            if red is not None:
                nu = len(inner) // 2
                u_o = (u_s + nu // 2) % nu
                jo = int(np.nonzero(sad[-1] == Rr[4 * u_o])[0][0])
                path_o = [int(r[jo]) for r in sad] + [int(inner[2 * u_o])]
            else:
                jo = (jc + Kc // 2) % Kc
                path_o = [int(r[jo]) for r in sad]
            parts = split_at_paths(Q[q], [path, path_o])
            assert len(parts) == 2, (nm, 'the saddle did not part in two', [len(p_) for p_ in parts])
            for h_, qh in zip('ab', parts):
                isl.append(dict(name=f'{nm}.saddle.{h_}', kind='sector', quads=q[qh],
                                corners=solve_island(V, Q[q[qh]], d02[q[qh]]), share=1.0, of=None))
        # the shaft's own grid: rows x (Ks + 1) columns counted from the seam in the sense the angle grows
        th_seam = float(th_v[rows[1][j_seam]])
        sense = 1 if np.angle(np.exp(1j * (th_v[rows[1][(j_seam + 1) % Ks]] - th_seam))) > 0 else -1
        ids = np.stack([r[(j_seam + sense * np.arange(Ks + 1)) % Ks] for r in rows])          # (R, Ks + 1)
        phi = np.mod(th_v[ids] - th_seam, TWO_PI)
        phi[:, 0], phi[:, -1] = 0.0, TWO_PI
        arc, girth = section_arc(br, s_v[ids].ravel(), phi.ravel(), th_seam)
        G = np.stack([(arc - 0.5 * girth).reshape(ids.shape), s_v[ids]], -1)
        qs = np.nonzero(lab == nm)[0]
        r_of, c_of = -np.ones(len(V), int), -np.ones(len(V), int)
        for r_, row in enumerate(ids):
            r_of[row[:Ks]] = r_
            c_of[row[:Ks]] = np.arange(Ks)
        rc = np.stack([r_of[Q[qs]], c_of[Q[qs]]], -1)
        assert (rc >= 0).all(), nm
        sm = s_v[ids[:, :Ks]].mean(1)
        area = float(0.5 * np.linalg.norm(np.cross(V[Q[qs, 2]] - V[Q[qs, 0]], V[Q[qs, 3]] - V[Q[qs, 1]]), axis=1).sum())
        # each row's share of the shaft, counted from the FIRST RING OF THE RING TABLE (row 1) to the last: row 0 is
        # the reducer's tilted inner ring, which stands at its own place on every tine (share < 0)
        shafts[nm] = dict(G=G, rc=rc, quads=qs, Ks=Ks, frac=(sm - sm[1]) / (sm[-1] - sm[1]), area=area, ids=ids,
                          th_seam=th_seam, sense=sense)
        grids[nm] = G
        if saddle == 'beam' and red is not None:
            # THE REDUCER GOES WITH THE SHAFT: ring C to the shaft's first ring is the tine's own tube, so its quads
            # take the strip's construction (the same arc-length rule as the grid: the two meet on the shaft's first
            # ring) and belong to the wedge of their side. `keys` name each corner by its ring (C 0, the shaft's
            # first ring 1, a unit's middle vertex 2) and its place round the tine counted from the seam in ring
            # C's steps: a stacked member's reducer takes its template's corner of the same name
            kinds_ = {}
            for t_, vs_ in enumerate((Rr, inner, np.asarray(red['mids']))):
                kinds_.update({int(v_): t_ for v_ in vs_})
            qr = np.array([i_ for i_ in q if all(int(v_) in kinds_ for v_ in Q[i_])], int)
            s4 = s_v[Q[qr]]
            ph = np.mod(th_v[Q[qr]] - th_seam, TWO_PI)
            ph[ph > TWO_PI - 1e-7] = 0.0
            ph = _unstraddle(ph, TWO_PI)
            arc, girth = section_arc(br, s4.ravel(), ph.ravel(), th_seam)
            typ = np.array([[kinds_[int(v_)] for v_ in qq] for qq in Q[qr]])
            shafts[nm]['reducer'] = dict(quads=qr, corners=np.stack([(arc - 0.5 * girth).reshape(-1, 4), s4], -1),
                                         keys=typ * 1000 + np.rint(ph / (TWO_PI / len(Rr))).astype(int),
                                         half=np.where(ph.mean(1) < np.pi, 0, 1))
    # A SHAFT IS TWO HALF WEDGES: a tapering tube unrolls as a spindle (wide base, pointed tip, both edges slanted),
    # and spindles leave half their box empty however they are turned. Cut again along the strip's own middle line
    # (the column opposite the crotch seam) each half is a wedge with ONE straight edge, and two wedges head to tail
    # are a rectangle. Both halves keep the strip's own (around, along) axes, so the tangent frame is the same on
    # both sides of the new seam (nothing for a normal map to show), and each half's taper shear is halved
    def halves(nm, G, rc, quads, Ks, of=None, template=None, red_on=None):
        _, mc, _ = _cells(rc, Ks)
        ids_ = []
        rd = shafts[nm].get('reducer')
        if rd is not None and red_on is not None:
            # a stacked member's reducer: its template's corners, name for name
            uv_t = {int(k_): c_ for kq, cq in zip(red_on['keys'], red_on['corners']) for k_, c_ in zip(kq, cq)}
            rd = dict(rd, corners=np.array([[uv_t[int(k_)] for k_ in kq] for kq in rd['keys']]))
        for h_, m_ in (('a', mc < Ks // 2), ('b', mc >= Ks // 2)):
            ids_.append(len(isl))
            qd, cn = quads[m_], _grid_lookup(G, rc[m_], Ks)
            if rd is not None:
                mr = rd['half'] == len(ids_) - 1
                qd, cn = np.concatenate([qd, rd['quads'][mr]]), np.concatenate([cn, rd['corners'][mr]])
            isl.append(dict(name=f'{nm}.{h_}', kind='strip', quads=qd, corners=cn,
                            share=1.0, of=None if of is None else of[len(ids_) - 1], template=template, wedge=h_))
        return ids_

    def halves_v2(nm, cs, hf, of=None, template=None):
        """a fix-round-1 shaft's two half wedges from its corners by construction (or its template's)"""
        ids_ = []
        qd = shafts[nm]['quads']
        for h_, hv in (('a', 0), ('b', 1)):
            ids_.append(len(isl))
            m_ = hf == hv
            isl.append(dict(name=f'{nm}.{h_}', kind='strip', quads=qd[m_], corners=cs[m_], share=1.0,
                            of=None if of is None else of[len(ids_) - 1], template=template, wedge=h_))
        return ids_

    # the classes: the largest member is the template; the others read its grid at their own rows' shares
    stacked = {}
    for k_ in sorted(set(cls.values())):
        members = [nm for nm in tines if cls[nm] == k_]
        if k_ == 'hero':
            for nm in members:
                sh = shafts[nm]
                if sh.get('v2'):
                    halves_v2(nm, sh['corners'], sh['half'])
                else:
                    halves(nm, sh['G'], sh['rc'], sh['quads'], sh['Ks'])
            continue
        prim = max(members, key=lambda nm: shafts[nm]['area'])
        shp = shafts[prim]
        if shp.get('v2'):
            ti = halves_v2(prim, shp['corners'], shp['half'], template=k_)
        else:
            ti = halves(prim, shp['G'], shp['rc'], shp['quads'], shp['Ks'], template=k_)
        cap_t = next(i for i, d_ in enumerate(isl) if d_['name'] == prim + '.cap')
        for nm in members:
            if nm == prim:
                continue
            sh = shafts[nm]
            if sh.get('v2'):
                # one topology, quad for quad: the member wears its template's corners and diagonals (07.33)
                assert sh['keys'] == shp['keys'], (nm, 'a class member\'s shaft is not its template\'s topology')
                halves_v2(nm, shp['corners'], shp['half'], of=ti)
                d02[sh['quads']] = d02[shp['quads']]
                stacked[nm] = dict(template=prim, same_rows=True)
            else:
                assert sh['Ks'] == shp['Ks'], (nm, 'a class shares its column count')
                # the member's grid = the template's, read at the member's own row shares. A class is drawn with one
                # ring table (horn_cage), so on the slice the rows are the template's own, row for row
                ft = shp['frac']
                same = len(sh['frac']) == len(ft) and np.abs(sh['frac'][1:] - ft[1:]).max() < 1e-6
                if same:
                    Gm = shp['G']
                else:
                    j = np.clip(np.searchsorted(ft, sh['frac'], side='right') - 1, 0, len(ft) - 2)
                    u = np.clip((sh['frac'] - ft[j]) / np.maximum(ft[j + 1] - ft[j], 1e-12), 0.0, 1.0)
                    Gm = shp['G'][j] * (1.0 - u)[:, None, None] + shp['G'][j + 1] * u[:, None, None]
                halves(nm, Gm, sh['rc'], sh['quads'], sh['Ks'], of=ti, red_on=shp.get('reducer'))
                stacked[nm] = dict(template=prim, same_rows=bool(same))
                if same:
                    # 07.33: a copy is split along the template's own diagonal, cell by cell
                    tr, tc, t02 = _cells(shp['rc'], shp['Ks'])
                    up_t = np.zeros((len(ft), shp['Ks']), bool)
                    up_t[tr, tc] = d02[shp['quads']] == t02
                    mr, mc, m02 = _cells(sh['rc'], sh['Ks'])
                    d02[sh['quads']] = m02 == up_t[mr, mc]
            # its cap rides the template's cap, grid node for grid node
            ci = next(i for i, d_ in enumerate(isl) if d_['name'] == nm + '.cap')
            Gt, Gm_ = np.asarray(S[prim]['cap']), np.asarray(S[nm]['cap'])
            if Gt.shape == Gm_.shape:
                uv_t = {}
                for qq, cc in zip(Q[isl[cap_t]['quads']], isl[cap_t]['corners']):
                    for v_, c_ in zip(qq, cc):
                        uv_t[int(v_)] = c_
                node = {int(Gm_[i, j]): uv_t[int(Gt[i, j])] for i in range(Gt.shape[0]) for j in range(Gt.shape[1])}
                isl[ci]['corners'] = np.array([[node[int(v_)] for v_ in qq] for qq in Q[isl[ci]['quads']]])
                isl[ci]['of'] = cap_t
    # DENSITY BY VISIBILITY (fix round 1; Skye's VEGA note "pack to ~75 %+ and weight density by visibility", craft
    # guide 07.18-07.24: hero areas up, half-hidden ones down): `shares` maps a rule to an island's texel share,
    # 'beam' the beam's pieces, 'beam_top' its top, 'burr', 'saddle' (a fork's pieces), 'cap' (tip caps), 'tine'
    # (the shafts' wedges). A stacked copy rides its template's share. None: every share as above
    for d_ in isl:
        nm_ = d_['name']
        for key_, v_ in (shares or {}).items():
            hit = dict(beam=nm_.startswith('beam_') and not nm_.startswith('beam_top'),
                       beam_top=nm_.startswith('beam_top.') and not nm_.endswith('.cap'), burr=nm_.startswith('burr_'),
                       saddle='.saddle' in nm_, cap=nm_.endswith('.cap'),
                       tine=d_.get('wedge') is not None and not nm_.startswith('beam_top')).get(key_, False)
            if hit:
                d_['share'] = float(v_)
    # ------------------------------------------------------------------ pack the primaries on one page
    owners = [i for i, d_ in enumerate(isl) if d_['of'] is None]
    riders = {i: [j for j, d_ in enumerate(isl) if d_['of'] == i] for i in owners}
    # WEDGES GO IN PAIRS, made here and packed as one piece: two half strips of the same hand, the second turned half
    # round, slanted edge to slanted edge, tops level: a rectangle. (Left to the packer, which seats each island
    # where its top comes lowest, the halves landed apart: 3,550 px/m, build/look/h07_uv_c.png)
    units = []
    for h_ in ('a', 'b'):
        w = sorted([i for i in owners if isl[i].get('wedge') == h_],
                   key=lambda i: -float(np.ptp(isl[i]['corners'][..., 1])))
        units += [w[k:k + 2] for k in range(0, len(w), 2)]
    units += [[i] for i in owners if isl[i].get('wedge') is None]
    thick = {}

    def tri_f(n_, off=0):
        k = np.arange(n_)[:, None] * 4 + off
        return np.concatenate([k + np.array([[0, 1, 2]]), k + np.array([[0, 2, 3]])])

    def build(D):
        out = []
        for u_ in units:
            for i in u_:
                if i not in thick:                   # 2 x the largest inscribed circle, read once at 4 cells a mm
                    q4 = isl[i]['corners'].reshape(-1, 2) * 4000.0
                    thick[i] = BU.thickness_texels(q4 - q4.min(0), tri_f(len(isl[i]['quads']))) / 4000.0
            # gutters by the island's thickness (HIGH_TO_LOW "UVs"): 8 px a side, 4 under 64 px
            pad = 8 if min(thick[i] * D * isl[i]['share'] for i in u_) >= 64 else 4
            tex = lambda i: isl[i]['corners'].reshape(-1, 2) * D * isl[i]['share']               # noqa: E731
            xf = [(1.0, np.zeros(2))]                # per island of the unit: p -> sign * p + shift
            if len(u_) == 2:
                P0, P1 = tex(u_[0]), tex(u_[1])
                xf.append((-1.0, _nest(P0, tri_f(len(P0) // 4), P1, tri_f(len(P1) // 4), pad)))
            pts, F, segs, n_own = [], [], [], 0
            for (sg, sh_), i in zip(xf, u_):        # the unit's own points first (the mask's triangles) ...
                p = sg * tex(i) + sh_
                segs.append((i, n_own, len(p)))
                F.append(tri_f(len(p) // 4, n_own))
                pts.append(p)
                n_own += len(p)
            off = n_own
            for (sg, sh_), i in zip(xf, u_):        # ... then the stacked copies, which ride their template
                for j in riders[i]:
                    p = sg * isl[j]['corners'].reshape(-1, 2) * D * isl[i]['share'] + sh_
                    segs.append((j, off, len(p)))
                    pts.append(p)
                    off += len(p)
            uvt = np.concatenate(pts)
            uvt = uvt - uvt[:n_own].min(0)
            F = np.concatenate(F)
            a_, b_, c_ = uvt[F[:, 0]], uvt[F[:, 1]], uvt[F[:, 2]]
            out.append(dict(uvt=uvt, F=F, n_own=n_own, masks=[], pad=pad, segs=segs, unit=u_, cells=float(
                0.5 * np.abs((b_ - a_)[:, 0] * (c_ - a_)[:, 1] - (b_ - a_)[:, 1] * (c_ - a_)[:, 0]).sum())))
        return out

    def attempt(D):
        pk = build(D)
        for place in places:
            for order in ORDERS:
                got = pack_page(pk, size, order=order, place=place)
                if got is not None:
                    return got[0], [got[1]], pk, f'{order} / {place}'
        # then the 'cells' order shaken (each island's size x a random factor): `tries` seeded orders
        rng = np.random.default_rng(int(D))
        size_ = np.array([e['cells'] for e in pk])
        for t_ in range(tries):
            seq = list(np.argsort(-size_ * np.exp(rng.normal(0.0, 0.45, len(pk)))))
            for place in places:
                got = pack_page(pk, size, seq=seq, place=place)
                if got is not None:
                    return got[0], [got[1]], pk, f'shaken {t_} / {place}'
        return None

    best, lo_d, hi_d = None, 0.55 * cap, cap
    got = attempt(cap)
    if got is not None:
        best = (cap,) + got
    else:
        for _ in range(7):
            D = 0.5 * (lo_d + hi_d)
            got = attempt(D)
            log(f'[horn_uv] pack at {D:.0f} px/m: ' + (f'fits (order {got[3]})' if got else 'no'))
            if got:
                best, lo_d = (D,) + got, D
            else:
                hi_d = D
    assert best is not None, f'nothing packs one {size} page down to {lo_d:.0f} px/m'
    D, placed, fill, pk, order = best
    corner = np.zeros((nq, 4, 2))
    island = -np.ones(nq, int)
    for pl, e in zip(placed, pk):
        uv = np.asarray(pl['uv'])
        for (j, start, n_) in e['segs']:
            corner[isl[j]['quads']] = uv[start:start + n_].reshape(-1, 4, 2)
            island[isl[j]['quads']] = j
        for i in e['unit']:
            isl[i].update(pad=e['pad'], thick=float(thick[i] * D * isl[i]['share']), rot=int(pl['rot']))
    assert (island >= 0).all(), 'a quad without an island'
    # every triangle keeps its turn (no mirrored or folded texel: 07.16 "verify triangle by triangle")
    # (the triangles that SHIP: a reducer's middle quad is three collinear ring vertices and the middle one in a
    # developed strip, and only its shipped diagonal splits it into two real triangles)
    flips = 0
    for d_ in isl:
        q = d_['quads']
        Ft = _tris_of(np.arange(4 * len(q)).reshape(-1, 4), d02[q])
        P2 = corner[q].reshape(-1, 2)
        a, b, c_ = P2[Ft[:, 0]], P2[Ft[:, 1]], P2[Ft[:, 2]]
        d_['flips'] = int((((b - a)[:, 0] * (c_ - a)[:, 1] - (b - a)[:, 1] * (c_ - a)[:, 0]) <= 0).sum())
        flips += d_['flips']
    table = []
    for i, d_ in enumerate(isl):
        q = d_['quads']
        F = _tris_of(np.arange(4 * len(q)).reshape(-1, 4), d02[q])
        P3 = V[Q[q]].reshape(-1, 3)
        U2 = corner[q].reshape(-1, 2) * size
        s1, s2, ok = UVT.stretch(P3, F, U2)
        a3 = 0.5 * np.linalg.norm(np.cross(P3[F[:, 1]] - P3[F[:, 0]], P3[F[:, 2]] - P3[F[:, 0]]), axis=1)
        o = np.argsort((s1 / s2)[ok])
        cw = np.cumsum(a3[ok][o])
        an95 = float((s1 / s2)[ok][o][min(np.searchsorted(cw, 0.95 * cw[-1]), len(o) - 1)])
        table.append(dict(name=d_['name'], kind=d_['kind'], quads=int(len(q)), area_cm2=round(float(a3.sum()) * 1e4, 2),
                          px_per_m=round(float(UVT.island_density(P3, F, U2)), 0), aniso_p95=round(an95, 3),
                          of=None if d_['of'] is None else isl[d_['of']]['name'], template=d_.get('template'),
                          pad=d_.get('pad'), thick_px=None if d_.get('thick') is None else round(d_['thick'], 1)))
    return dict(corner=corner, island=island, d02=d02, islands=table, density=float(D), fill=float(fill[0]), size=size,
                flips=flips, stacked=stacked, charts=charts, mode=mode, names=[d_['name'] for d_ in isl],
                primary=np.array([isl[i]['of'] is None for i in island]))


def split_mesh(c, L):
    """the low as it ships: (V, N, UV, F, orig, tri_island, tri_bake). Vertices are split wherever a vertex carries
    two UVs (seams, stacked copies); N are the WELDED mesh's normals (a seam must not shade); tri_bake marks the
    triangles the bake reads: unique islands and each stack's template, never a stacked copy"""
    mesh = c['mesh']
    V, Q = mesh.V, mesh.Q
    Nw = mesh.vertex_normals()
    Nw = Nw / np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-30)
    key = np.column_stack([Q.ravel(), np.round(L['corner'].reshape(-1, 2) * (1 << 22)).astype(np.int64)])
    uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    orig = uniq[:, 0].astype(np.int64)
    UV = L['corner'].reshape(-1, 2)[first]
    Qn = inv.reshape(-1, 4)
    F = _tris_of(Qn, L['d02'])
    tq = np.repeat(np.arange(len(Q)), 2)
    return dict(V=V[orig], N=Nw[orig], UV=UV, F=F, orig=orig, tri_quad=tq, tri_island=L['island'][tq],
                tri_bake=L['primary'][tq], Q=Qn)


def mirror(M):
    """the RIGHT horn from the left one, as data: x negated, the winding turned, the same UVs (so the pair shares
    every texel); a tangent's w is negated by the frames' own rule (bake.low_frames reads the turned winding)"""
    out = dict(M)
    m = np.array([-1.0, 1.0, 1.0])
    out['V'], out['N'] = M['V'] * m, M['N'] * m
    out['F'] = M['F'][:, [0, 2, 1]]
    return out


# ------------------------------------------------------------------------------- a LOD in LOD0's texture set
def _closest_on_tri(p, a, b, c):
    """the closest point on triangles (a, b, c) to points p, broadcast over leading axes (..., 3)
    (forge/cyborg_octopus.py closest_on_tri, copied: that module pulls the octopus's whole rig in)"""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = p - b
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = p - c
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    safe = lambda x: np.where(np.abs(x) < 1e-30, 1e-30, x)                                 # noqa: E731
    den = safe(va + vb + vc)
    q = a + ab * (vb / den)[..., None] + ac * (vc / den)[..., None]
    t = (d4 - d3) / safe((d4 - d3) + (d5 - d6))
    q = np.where(((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0))[..., None], b + (c - b) * t[..., None], q)
    t = d2 / safe(d2 - d6)
    q = np.where(((vb <= 0) & (d2 >= 0) & (d6 <= 0))[..., None], a + ac * t[..., None], q)
    q = np.where(((d6 >= 0) & (d5 <= d6))[..., None], c, q)
    t = d1 / safe(d1 - d3)
    q = np.where(((vc <= 0) & (d1 >= 0) & (d3 <= 0))[..., None], a + ab * t[..., None], q)
    q = np.where(((d3 >= 0) & (d4 <= d3))[..., None], b, q)
    q = np.where(((d1 <= 0) & (d2 <= 0))[..., None], a, q)
    return q


def _stem(label):
    """'brow.saddle' -> 'brow'; 'beam_top.cap' -> 'beam_top'; 'beam' -> 'beam'"""
    return label.split('.')[0]


def lod_layout(c, c0, L0, log=print, k=96):
    """A LOD'S UVS IN LOD0'S TEXELS (one texture set serves every LOD: nothing is baked again). The LOD cage `c`
    (horn_cage.cage(..., lod, uv_ref=L0['charts']['beam'])) is our own drawing from the same ring and K tables, so
    its vertices are not LOD0's; each of its quads takes ONE island of LOD0's layout (the island of the LOD0
    triangle nearest its middle, among those of its own branch or of the fork it stands on), and each corner the UV
    of the closest point of THAT island (barycentric on LOD0's shipped triangles). A corner past the island's
    border lands on the border: the quad stays inside one island's texels (no quad ever reads across a gutter).
    A stacked member's quads follow the member's own LOD0 quads, so they land on the template's texels.
    k: how many of LOD0's triangles (nearest by CENTROID) each point is tried against. A rigid part's rings stand up
    to 65 mm apart, so its triangles are slivers 6 x 65 mm whose centroids lie far from their own corners: with
    k = 24 the triangle that held a seam corner's second image ranked 33rd (centroid 25 mm away, the point itself
    0.03 mm) and the corner took the wrong side of the seam.
    Returns a layout dict split_mesh() takes (corner, island, d02, primary, names, islands, size, density) with
    `lod_report`: the corners' distance to LOD0 (mm), the texel stretch against LOD0's own, flipped triangles"""
    from scipy.spatial import cKDTree
    m0, m1 = c0['mesh'], c['mesh']
    V0, Q0, V1, Q1 = m0.V, m0.Q, m1.V, m1.Q
    lab0, lab1 = c0['labels'].astype(str), c['labels'].astype(str)
    # LOD0's shipped triangles with their corner UVs
    d0 = np.asarray(L0['d02'], bool)
    ca = np.where(d0[:, None], [0, 1, 2], [0, 1, 3])
    cb = np.where(d0[:, None], [0, 2, 3], [1, 2, 3])
    cor = np.stack([ca, cb], 1).reshape(-1, 3)                           # (2 nq0, 3) corner slots
    tq = np.repeat(np.arange(len(Q0)), 2)
    P = V0[Q0[tq[:, None], cor]]                                         # (nt, 3, 3)
    U = np.asarray(L0['corner'])[tq[:, None], cor]                       # (nt, 3, 2)
    t_isl, t_stem = np.asarray(L0['island'])[tq], np.array([_stem(s_) for s_ in lab0[tq]])
    cen = P.mean(1)
    # the home island of each LOD quad: the island of the nearest LOD0 triangle of its own branch, or (a saddle or
    # a quad at a fork) of the branch it stands on
    stems = sorted(set(t_stem))
    ok_for = {s_: [s_] for s_ in stems}
    for s_ in stems:
        if s_ not in ('beam', 'beam_top', 'seal'):
            ok_for[s_] = [s_, 'beam']
    ok_for['beam'] = [s_ for s_ in stems if s_ != 'seal']
    ok_for['beam_top'] = ['beam_top', 'beam']
    mid = V1[Q1].mean(1)
    home = -np.ones(len(Q1), int)
    uv_mid = np.zeros((len(Q1), 2))
    size_px = float(L0['size'])

    def bary_uv(tri_, q_):
        """the UV of points q_ (m, 3) lying on LOD0's shipped triangles tri_ (m,), by their barycentrics"""
        a_, b_, c_ = P[tri_, 0], P[tri_, 1], P[tri_, 2]
        v0, v1, v2 = b_ - a_, c_ - a_, q_ - a_
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
        w1 = np.clip((d11 * d20 - d01 * d21) / den, 0.0, 1.0)
        w2 = np.clip((d00 * d21 - d01 * d20) / den, 0.0, 1.0 - w1)
        return U[tri_, 0] * (1.0 - w1 - w2)[:, None] + U[tri_, 1] * w1[:, None] + U[tri_, 2] * w2[:, None]

    for lb in sorted(set(lab1)):
        mq = np.nonzero(lab1 == lb)[0]
        st_ = _stem(lb)
        if lb.endswith('.cap') or lb == 'seal':
            cand = np.nonzero(lab0[tq] == lb)[0]                          # a cap rides its own cap
        elif lb.endswith('.saddle'):
            cand = np.nonzero(np.isin(t_stem, [st_, 'beam']) & ~np.char.endswith(lab0[tq], '.cap'))[0]
        else:
            cand = np.nonzero(np.isin(t_stem, ok_for.get(st_, [st_])) & ~np.char.endswith(lab0[tq], '.cap')
                              & ((t_stem == st_) | np.char.endswith(lab0[tq], '.saddle') | (st_ != 'beam')))[0]
        assert len(cand), (lb, 'no LOD0 triangle for this label')
        _, j = cKDTree(cen[cand]).query(mid[mq], k=min(k, len(cand)))
        j = np.asarray(j).reshape(len(mq), -1)
        tri = cand[j]
        qp = _closest_on_tri(mid[mq][:, None, :], P[tri, 0], P[tri, 1], P[tri, 2])
        r_ = np.arange(len(mq))
        best = np.linalg.norm(mid[mq][:, None, :] - qp, axis=2).argmin(1)
        home[mq] = t_isl[tri[r_, best]]
        uv_mid[mq] = bary_uv(tri[r_, best], qp[r_, best])
    # each corner: a point of the home island, its UV by the triangle's barycentrics. NOT simply the closest point:
    # (1) A SEAM HAS TWO IMAGES: a corner on a seam of its home island (the beam strip's lengthwise cut) is as near
    #     to the island's one edge as to the other, and "the closest" took either: the quad then spanned the whole
    #     strip (62 flipped triangles on LOD1, build/tmp/now/h12_wires_a.png);
    # (2) A CUT THE LOD HAS NO COLUMN ON (a saddle's cut: its horseshoe island): a quad that straddles it had
    #     corners on both sides of the gap (5 / 23 flipped triangles left on LOD1 / LOD2, h12_wires_d.png).
    # One rule for both: the corner takes the candidate with the least  distance + `lam` x (how far its UV lies
    # from its own quad's middle, in metres at the island's density); then, in that PLACE of the set (within
    # `jump` in UV), the nearest point. On a seam the distances tie and the quad's own side wins; past a cut the
    # near edge of the cut (a few mm away) wins over the true place a whole island away, so the quad is drawn up
    # to the cut and stays on one side. lam < 1 keeps every other corner where it is (moving toward the middle
    # costs 1 in distance and saves lam). The second step gives a vertex ONE UV in all its quads (the first step
    # alone gave each quad its own: 2,030 split vertices on LOD1 where 1,440 are wanted).
    lam, jump = 0.35, 12.0 / L0['size']
    isl_px = np.array([float(r_.get('px_per_m', L0['density'])) for r_ in L0['islands']])
    corner = np.zeros((len(Q1), 4, 2))
    dist = np.zeros((len(Q1), 4))

    def corners_in(i, mq, uvm):
        """the corners of quads mq laid in island i by the rule above; uvm (m, 2) their middles' UV in that island"""
        ti = np.nonzero(t_isl == i)[0]
        pts = V1[Q1[mq]].reshape(-1, 3)
        _, j = cKDTree(cen[ti]).query(pts, k=min(k, len(ti)))
        j = np.asarray(j).reshape(len(pts), -1)
        tri = ti[j]
        a, b, cc = P[tri, 0], P[tri, 1], P[tri, 2]
        qp = _closest_on_tri(pts[:, None, :], a, b, cc)
        dd = np.linalg.norm(pts[:, None, :] - qp, axis=2)
        kk = tri.shape[1]
        uv_all = bary_uv(tri.ravel(), qp.reshape(-1, 3)).reshape(len(pts), kk, 2)
        away = np.linalg.norm(uv_all - np.repeat(uvm, 4, axis=0)[:, None, :], axis=2) * size_px / isl_px[i]
        r = np.arange(len(pts))
        b0 = (dd + lam * away).argmin(1)
        place = np.linalg.norm(uv_all - uv_all[r, b0][:, None, :], axis=2) <= jump
        best = np.where(place, dd, np.inf).argmin(1)
        return uv_all[r, best].reshape(-1, 4, 2), dd[r, best].reshape(-1, 4)

    for i in np.unique(home):
        mq = np.nonzero(home == i)[0]
        corner[mq], dist[mq] = corners_in(i, mq, uv_mid[mq])
    d02 = np.linalg.norm(V1[Q1[:, 0]] - V1[Q1[:, 2]], axis=1) <= np.linalg.norm(V1[Q1[:, 1]] - V1[Q1[:, 3]], axis=1)
    size = L0['size']

    def least_area(cu, dq):
        """the smaller signed UV area (px^2) of a quad's two shipped triangles"""
        u_ = cu * size
        out_ = []
        for (i0, i1, i2) in (((0, 1, 2), (0, 2, 3)) if dq else ((0, 1, 3), (1, 2, 3))):
            e1_, e2_ = u_[i1] - u_[i0], u_[i2] - u_[i0]
            out_.append(0.5 * (e1_[0] * e2_[1] - e1_[1] * e2_[0]))
        return min(out_)

    # A QUAD LEFT WITHOUT AREA IN ITS HOME ISLAND goes to the island of its own branch that gives it the most. A
    # coarse LOD's quad at a tine's root can have its middle nearest one half strip while two of its corners lie
    # past that strip's end: both then took the strip's corner point (LOD2: one triangle of crown_a with 0.0 px^2,
    # its two corners 12 mm apart in space). The home is a choice; the area says when it was the wrong one
    stem_of = np.array([_stem(nm) for nm in L0['names']])
    rehomed = 0
    # (fix round 1: a coarse LOD's saddle quad reaches from the beam to the tine, and LOD0's saddle now ends at ring
    # C with the shaft's halves above it: LOD2's crown_c saddle quad found no area in any island of its own tine
    # (three corners on one point of crown_c.a); the beam's pieces are tried for a saddle's quads too)
    beam_isl = np.array([str(nm).startswith('beam_') and not str(nm).startswith('beam_top') for nm in L0['names']])
    for q in np.nonzero([least_area(corner[q_], d02[q_]) <= 0.25 for q_ in range(len(Q1))])[0]:
        best_i, best_a, best_c, best_d = home[q], least_area(corner[q], d02[q]), corner[q], dist[q]
        for i in np.nonzero((stem_of == _stem(lab1[q])) | (beam_isl & lab1[q].endswith('.saddle')))[0]:
            ti = np.nonzero(t_isl == i)[0]
            if i == home[q] or not len(ti) or str(L0['names'][i]).endswith('.cap') != lab1[q].endswith('.cap'):
                continue
            _, j = cKDTree(cen[ti]).query(mid[q], k=min(k, len(ti)))
            tri = ti[np.atleast_1d(j)]
            qm = _closest_on_tri(mid[q][None, None, :], P[tri, 0][None], P[tri, 1][None], P[tri, 2][None])[0]
            jb = int(np.linalg.norm(qm - mid[q], axis=1).argmin())
            cu, dd_ = corners_in(i, np.array([q]), bary_uv(tri[jb:jb + 1], qm[jb:jb + 1]))
            if least_area(cu[0], d02[q]) > best_a:
                best_i, best_a, best_c, best_d = i, least_area(cu[0], d02[q]), cu[0], dd_[0]
        if best_i != home[q]:
            home[q], corner[q], dist[q] = best_i, best_c, best_d
            rehomed += 1
    F = _tris_of(np.arange(4 * len(Q1)).reshape(-1, 4), d02)
    P3, U2 = V1[Q1].reshape(-1, 3), corner.reshape(-1, 2) * size
    e1, e2 = U2[F[:, 1]] - U2[F[:, 0]], U2[F[:, 2]] - U2[F[:, 0]]
    a2 = 0.5 * (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    a3 = 0.5 * np.linalg.norm(np.cross(P3[F[:, 1]] - P3[F[:, 0]], P3[F[:, 2]] - P3[F[:, 0]]), axis=1)
    dens = np.sqrt(np.maximum(a2, 0.0) / np.maximum(a3, 1e-30))          # px/m per triangle
    prim0 = np.zeros(len(L0['names']), bool)
    prim0[np.unique(np.asarray(L0['island'])[np.asarray(L0['primary'], bool)])] = True
    rep = dict(quads=int(len(Q1)), triangles=int(2 * len(Q1)), islands_used=int(len(np.unique(home))),
               corner_to_lod0_mm=dict(p50=round(float(np.percentile(dist, 50)) * 1000, 3),
                                      p95=round(float(np.percentile(dist, 95)) * 1000, 3),
                                      max=round(float(dist.max()) * 1000, 3)),
               flipped_triangles=int((a2 <= 0.0).sum()), quads_rehomed=int(rehomed),
               density_vs_lod0=dict(p5=round(float(np.percentile(dens, 5) / L0['density']), 3),
                                    p50=round(float(np.percentile(dens, 50) / L0['density']), 3),
                                    p95=round(float(np.percentile(dens, 95) / L0['density']), 3)))
    log(f'[horn_uv] LOD{c.get("lod")} on LOD0\'s set: {rep}')
    return dict(corner=corner, island=home, d02=d02, primary=prim0[home], names=list(L0['names']),
                islands=L0['islands'], size=size, density=L0['density'], stacked=L0.get('stacked', {}),
                charts=L0['charts'], mode=L0.get('mode'), lod_report=rep, flips=rep['flipped_triangles'],
                fill=L0.get('fill'))
