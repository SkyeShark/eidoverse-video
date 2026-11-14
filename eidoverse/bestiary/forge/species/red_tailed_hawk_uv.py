"""The RED-TAILED HAWK's skin UVs (HAWK_PLAN.md §4.7, D1.5's UV half; D1.3b): the D1.5 cage (families/avian_cage.py)
cut into islands, each unwrapped (forge/uv.py: LSCM, then ARAP), scaled to its set's texel density, packed per set.

THE SETS (plan §4.7): BODY 4096 at 6,000 px/m (the skin under the coat: the trunk, neck and tail root, the feathered
head, the thighs and the drumsticks; the wing skin at HALF the density: it is hidden under the coverts and flight
feathers); HEAD 2048 at 12,000 px/m (the BARE parts: the face from the feather line before the cere and the lores (the
cere, the nostrils, the gape), the eyes' orbits and lids, the tarsi, the foot's hub, the toes). Every HEAD-BODY seam
lies on a cut loop on the feather line, under the coat's cards (the face ring, the eye loops, the ankle rings at the
trousers' hem). (D1.3b's first layout put the whole feathered head in HEAD: 1.42 sheets tall.)

THE ISLANDS: the cage cut along its cut loops (avian_cage's cage.cuts: the wing and leg ports, the head ring, the face
ring, the eye loops, the knee rings, the toe ports, the toes' tip-cap rings; plus the ANKLE and FOOT records):
trunk, head, face, eye x 2, wing x 2, thigh x 2, drum (the drumstick) x 2, tarsus x 2, foot (the hub and the sole)
x 2, toe x 8, tipcap (the talon's bed) x 8. (The knee, the foot and the tip-cap rings cut where one island bent too
far to unroll: the thigh's strip curled over itself at the knee, the tarsus-and-hub folded round its toe ports, the
toes' 2 x 2 tip domes stretched to p95 1.5.) Each island is then cut to a DISK by
SEAMS: shortest paths over its edges joining all its boundary loops (ports, sockets, cut loops) and its closed ends
(cage.terms: the wing tips, the toe tips, the tail's cap), each edge costed by its length x (1 + SEAM_HIDE (1 - n.p) /
2) with p the island kind's hidden side (seam_side: the trunk's belly, the wing's and the toe's undersides, the thigh's
inner face, the tarsus's back, the head's throat, the face's chin), so the seams run where the coat and the pose hide
them. A seam that ends at a closed end runs on across it, CAP_OPEN edges to its far side: ended at the tip, the cap
flattened round a point (the tail cap's ring of anisotropy 3; the toe tips' 1.6-2.2: D1.3b restart 2).

SHARED REPEATS (Skye's standard: repeated parts share UV space): a right-side island whose every vertex has its left
twin's mirror within MIRROR_TOL is STACKED on it: its seams are the left's mirrored and its UVs the left's (one unwrap,
one packed place; a mirrored island's UV triangles run clockwise, the tangent's sign flips). Only the unique islands
are packed and counted for overlaps and fill. D1.3c: the cage's right side is the left's mirror to the bit
(avian_cage.mirror_limbs, project), so all fifteen right islands stack: the wing, the thigh, the drumstick, the
tarsus, the foot, four toes, four tip caps, the eye, the nostril (D1.3b: the eyes alone; the limbs were built per
side, up to 3.2 mm apart at the feet).

OPEN HOLES (HOLES, D1.3c): the face keeps each nostril's rim as a hole, joined by no seam; the nostril's lining (the
dish's floor, the slot) is its own island.

PACKING: a raster packer per set: each island in its least-area box orientation (_min_box), tried at four quarter
turns, placed bottom-left on a grid of PACK_CELL texels where its padded mask meets no other (the shared uv.pack
packs bounding boxes: the HEAD set's irregular islands took 1.42 sheets at a 0.65 fill). _pack: forge/uv.py's
pack_raster once it is there (D1.3c stages the stag beetle's raster packer for uv.py, hawk/d13c/STAGED.md), this
module's own _pack_raster until then.
"""
import heapq
from collections import defaultdict

import numpy as np

from .. import uv as UVM
from .. import loft as LF
from ..mesh import QuadMesh

SETS = dict(BODY=dict(size=4096, ppm=6000.0), HEAD=dict(size=2048, ppm=12000.0))
SET_OF = dict(trunk='BODY', head='BODY', wing='BODY', thigh='BODY', drum='BODY', face='HEAD', nostril='HEAD',
              eye='HEAD', tarsus='HEAD', foot='HEAD', toe='HEAD', tipcap='HEAD')
SHARE = dict(wing=0.5)                    # plan §4.7: the wing skin (hidden) at half the set's density
HOLES = dict(face=('nostril_L', 'nostril_R'))
#                                           D1.3c: cut loops an island keeps as open HOLES, joined by no seam: the
#                                           nostrils in the face (each nostril's lining is its own island). A seam from
#                                           each to the bill ran across the bare cere, the head's closest-viewed skin,
#                                           and through the saddle round the nostril's rim its two sides lapped over each
#                                           other in the unwrap (51-122 texels under two triangles at any ARAP count)
SEAM_HIDE = 6.0                           # the seams' cost on the visible side (x the edge's length)
CAP_OPEN = 3                              # edges a seam runs on past a closed end, across its cap (2: the toes' 2 x 2
#                                           tip caps still flattened at p95 1.3-1.7)
PAD = 8                                   # texels between islands at the set's size
PACK_CELL = 4                             # texels per cell of _pack_raster's grid
ARAP_ITERS = 40
MIRROR_TOL = 0.05                         # mm: a vertex's mirror lands this close to its twin


def _u(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def kind_of(name):
    return name.split('_')[0]


def seam_side(kind, side, chain):
    """the hidden side's direction per island kind (world, unit)"""
    sg = 1.0 if side == 'L' else -1.0
    belly = chain['R'] @ np.array([0.0, -1.0, 0.0])           # the flight frame's down: the trunk's ventral side
    return _u(dict(trunk=belly, head=np.array([0.0, -1.0, -0.3]), face=np.array([0.0, -1.0, 0.2]),
                   nostril=np.array([0.0, -1.0, 0.0]),
                   eye=np.array([0.0, -0.7, -0.7]), wing=np.array([0.0, -1.0, 0.0]),
                   thigh=np.array([-sg, -0.3, 0.0]), drum=np.array([-sg, -0.3, 0.0]),
                   tarsus=np.array([0.0, -0.3, -1.0]), foot=np.array([0.0, -1.0, -0.3]),
                   toe=np.array([0.0, -1.0, 0.0]), tipcap=np.array([0.0, -1.0, 0.0]))[kind])


def cut_edges(cuts, records):
    E = set()
    loops = dict(cuts)
    for nm in ('ankle_L', 'ankle_R', 'foot_L', 'foot_R'):
        loops[nm] = np.asarray(records[nm]['ids'])
    for nm, lp in loops.items():
        lp = [int(i) for i in lp]
        for a, b in zip(lp, lp[1:] + lp[:1]):
            E.add((min(a, b), max(a, b)))
    return E, loops


def name_islands(Q, lab, loops, terms):
    """each island's name from the cut loops it touches"""
    names = {}
    for l in np.unique(lab):
        vs = set(np.unique(Q[lab == l]).tolist())
        touch = {nm for nm, lp in loops.items() if set(int(i) for i in lp) <= vs}
        tt = {nm for nm, v in terms.items() if v in vs}
        side = lambda pre: [t for t in touch if t.startswith(pre)][0][-1]
        if 'head' in touch and any(t.startswith('port_') for t in touch):
            nm = 'trunk'
        elif 'head' in touch:
            nm = 'head'                                       # the feathered head: the head, face and eye loops
        elif 'face' in touch:
            nm = 'face'                                       # the face ring to the bills' sockets, the nostrils' rims
        elif len(touch) == 1 and next(iter(touch)).startswith('nostril_'):
            nm = next(iter(touch))                            # the nostril's pit
        elif len(touch) == 1 and next(iter(touch)).startswith('eye_'):
            nm = next(iter(touch))
        elif len(touch) == 1 and next(iter(touch)).startswith('port_wing'):
            nm = 'wing_' + next(iter(touch))[-1]
        elif any(t.startswith('port_leg') for t in touch):
            nm = 'thigh_' + side('port_leg')
        elif any(t.startswith('knee') for t in touch):
            nm = 'drum_' + side('knee')
        elif any(t.startswith('ankle') for t in touch):
            nm = 'tarsus_' + side('ankle')                    # the ankle ring to the FOOT record's ring
        elif any(t.startswith('foot_') for t in touch):
            nm = 'foot_' + side('foot_')                      # the foot ring, the hub, the sole, the toes' ports
        elif any(t.startswith('toe_') for t in touch):
            nm = [t for t in touch if t.startswith('toe_')][0]  # the toe: its port to its tip cap's ring
        elif len(touch) == 1 and next(iter(touch)).startswith('tipcap_'):
            nm = next(iter(touch))                            # the talon's bed
        else:
            raise AssertionError(f'island {l}: touches {sorted(touch)}, ends {sorted(tt)}')
        names[int(l)] = nm
    return names


def _vertex_normals(V, Q):
    m = QuadMesh(V, Q)
    fn = m.face_normals()
    vn = np.zeros_like(V)
    for k in range(4):
        np.add.at(vn, Q[:, k], fn)
    return _u(vn + 1e-12)


def mirror_map(V):
    """each cage vertex's twin across the sagittal plane (x -> -x; a midline vertex is its own), -1 where none lies
    within MIRROR_TOL; and the largest twin distance found"""
    from scipy.spatial import cKDTree
    d, j = cKDTree(V).query(V * np.array([-1.0, 1.0, 1.0]))
    return np.where(d <= MIRROR_TOL, j, -1), float(d[d <= MIRROR_TOL].max())


def _cap_path(adj, V, v, away, n):
    """the seam's run on across a closed end: from its terminal v, n edges (breadth first) to the vertex farthest
    along `away` (the side opposite the seam's own)"""
    prev = {v: None}
    frontier = [v]
    for _ in range(n):
        nxt = []
        for a in frontier:
            for b in adj[a]:
                if b not in prev:
                    prev[b] = a
                    nxt.append(b)
        frontier = nxt or frontier
    u = max(frontier, key=lambda b: float((V[b] - V[v]) @ away))
    out = set()
    while prev[u] is not None:
        out.add((min(u, prev[u]), max(u, prev[u])))
        u = prev[u]
    return out


def island_seams(V, Qi, vn, p, terms, star=False, holes=()):
    """the seam edges that make the island (faces Qi) a disk: its boundary loops and its terminal vertices joined by
    shortest paths (greedy: grow from the first, always to the nearest unjoined; with `star`, each loop joined to the
    first loop on its own, never through another loop's vertices: the foot's hub, whose greedy seams crossed the
    one-column strips between the toes' ports and left them as flaps that folded over the island), each terminal's
    seam run on across its cap (_cap_path, CAP_OPEN edges toward -p). `holes`: boundary loops (vertex sets) left OPEN,
    joined by no seam (HOLES)"""
    adj = defaultdict(list)
    for q in Qi:
        for k in range(4):
            a, b = int(q[k]), int(q[(k + 1) % 4])
            adj[a].append(b)
            adj[b].append(a)
    sub = QuadMesh(V, np.asarray(Qi))
    groups = [set(int(i) for i in l) for l in LF.boundary_loop(sub)]
    groups = [g for g in groups if not any(g == set(h) for h in holes)] + [{int(t)} for t in terms]
    if len(groups) <= 1:
        return set(), len(groups)
    w = 1.0 + SEAM_HIDE * 0.5 * (1.0 - np.clip(vn @ p, -1.0, 1.0))
    joined = set(groups[0])
    left = list(range(1, len(groups)))
    seams = set()
    if star:
        for gi in left:
            blocked = set().union(*[groups[gj] for gj in range(1, len(groups)) if gj != gi])
            dist = {v: 0.0 for v in groups[0]}
            prev = {}
            pq = [(0.0, v) for v in groups[0]]
            heapq.heapify(pq)
            target = None
            while pq:
                d, a = heapq.heappop(pq)
                if d > dist.get(a, np.inf):
                    continue
                if a in groups[gi]:
                    target = a
                    break
                for b in adj[a]:
                    if b in blocked:
                        continue
                    nd = d + float(np.linalg.norm(V[a] - V[b])) * 0.5 * (w[a] + w[b])
                    if nd < dist.get(b, np.inf):
                        dist[b] = nd
                        prev[b] = a
                        heapq.heappush(pq, (nd, b))
            assert target is not None, 'a port is unreachable round the others'
            v = target
            while v in prev:
                seams.add((min(v, prev[v]), max(v, prev[v])))
                v = prev[v]
        left = []
    while left:
        dist = {v: 0.0 for v in joined}
        prev = {}
        pq = [(0.0, v) for v in joined]
        heapq.heapify(pq)
        target = None
        member = {v: gi for gi in left for v in groups[gi]}
        while pq:
            d, a = heapq.heappop(pq)
            if d > dist.get(a, np.inf):
                continue
            if a in member:
                target = a
                break
            for b in adj[a]:
                nd = d + float(np.linalg.norm(V[a] - V[b])) * 0.5 * (w[a] + w[b])
                if nd < dist.get(b, np.inf):
                    dist[b] = nd
                    prev[b] = a
                    heapq.heappush(pq, (nd, b))
        assert target is not None, 'an island part is unreachable'
        gi = member[target]
        v = target
        while v in prev:
            u = prev[v]
            seams.add((min(u, v), max(u, v)))
            joined.add(v)
            v = u
        joined |= groups[gi]
        left.remove(gi)
    for t in terms:
        seams |= _cap_path(adj, V, int(t), -p, CAP_OPEN)
    return seams, len(groups)


def _min_box(U):
    """U turned to its convex hull's least-area bounding rectangle (the packer only turns 0 / 90 deg)"""
    from scipy.spatial import ConvexHull
    H = U[ConvexHull(U).vertices]
    E = np.roll(H, -1, axis=0) - H
    best = None
    for a in np.arctan2(E[:, 1], E[:, 0]):
        c, s = np.cos(-a), np.sin(-a)
        R = np.array([[c, -s], [s, c]])
        P = H @ R.T
        area = float(np.prod(P.max(0) - P.min(0)))
        if best is None or area < best[0]:
            best = (area, R)
    return U @ best[1].T


def _raster(T, tri, g):
    """the cells (g texels a side) an island's triangles cover, T in texels: the cells whose centre lies in a triangle,
    and each vertex's cell (a thin triangle may hold no centre); returns the mask and its first cell"""
    lo = np.floor(T.min(0) / g).astype(int)
    T2 = T / g - lo
    W, H = (np.ceil(T2.max(0)).astype(int) + 1)
    M = np.zeros((H, W), bool)
    for a, b, c in T2[tri]:
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        ins = (l0 >= -1e-6) & (l1 >= -1e-6) & (1.0 - l0 - l1 >= -1e-6)
        M[np.clip(gy[ins].astype(int), 0, H - 1), np.clip(gx[ins].astype(int), 0, W - 1)] = True
    vi = np.clip(np.floor(T2).astype(int), 0, [W - 1, H - 1])
    M[vi[:, 1], vi[:, 0]] = True
    return M, lo


def _pack_raster(isls, size, pad=PAD, g=PACK_CELL):
    """isls: list of (T (n, 2) texels, tri (m, 3)); returns each island's UVs (0-1 on the sheet) and the used height
    share. Largest first; each tried at four quarter turns, placed at the lowest free row (then the leftmost column)
    where its mask, dilated by one cell more than the padding, meets no placed island's"""
    from scipy.ndimage import binary_dilation
    from scipy.signal import correlate
    d = 1 + int(np.ceil(pad / g))
    Wc = size // g
    O = np.zeros((3 * Wc, Wc), np.float32)
    rots = [np.eye(2), np.array([[0.0, -1.0], [1.0, 0.0]]), -np.eye(2), np.array([[0.0, 1.0], [-1.0, 0.0]])]
    masks = []
    for T, tri in isls:
        opts = []
        for R in rots:
            Tr = T @ R.T
            M, lo = _raster(Tr, tri, g)
            Mp = binary_dilation(np.pad(M, d), iterations=d)
            opts.append((Tr, lo, Mp))
        masks.append(opts)
    order = sorted(range(len(isls)), key=lambda i: -int(masks[i][0][2].sum()))
    out = [None] * len(isls)
    top = 0
    for i in order:
        best = None
        for Tr, lo, Mp in masks[i]:
            h, w = Mp.shape
            if w > Wc:
                continue
            C = correlate(O, Mp.astype(np.float32), mode='valid', method='fft')
            ys, xs = np.nonzero(C < 0.5)
            if not len(ys):
                continue
            k = np.lexsort((xs, ys))[0]
            cand = (ys[k] + h, xs[k], ys[k], Tr, lo, Mp)
            if best is None or cand[:2] < best[:2]:
                best = cand
        assert best is not None, f'island {i} does not fit the packing grid'
        _, x, y, Tr, lo, Mp = best
        O[y:y + Mp.shape[0], x:x + Mp.shape[1]] += Mp
        out[i] = (Tr - lo * g + (np.array([x, y]) + d) * g) / size
        top = max(top, y + Mp.shape[0] - d)
    return out, top * g / size


def _pack(isls, size):
    """a set's islands packed on its sheet: (each island's UVs 0-1, the used height share). Where the installed
    forge/uv.py has pack_raster (D1.3c: staged in work/bestiary/hawk/d13c/uv_packer.py until its landing: the stag
    beetle's raster packer, moved to uv.py, the one the axolotl, the human and the lobster pack with) it packs: four
    quarter turns, each island padded PAD / 2 so two stand PAD apart; a second page reads as a height over 1. Else
    this module's own _pack_raster (D1.3b: a second packer of the same kind; it goes at that landing)"""
    if hasattr(UVM, 'pack_raster'):
        out, _ = UVM.pack_raster([dict(uvt=T - T.min(0), F=np.asarray(tri), pad=0.5 * PAD) for T, tri in isls],
                                 size=size, ds=PACK_CELL, turns=(0, 1, 2, 3), log=lambda s: None)
        used = max(float(o['page']) + float(o['uv'][:, 1].max()) + 0.5 * PAD / size for o in out)
        return [o['uv'] for o in out], used
    return _pack_raster(isls, size=size)


def layout(V_mm, Q, records, cuts, terms, chain, log=print):
    """returns dict(uv (n', 2) 0-1 per set, Qn (m, 4) into it, orig (n',) cage ids, face_set (m,) 'BODY'/'HEAD',
    lab (m,) the faces' islands, islands {label: dict(name, set, share, twin (the left twin's label for a stacked
    right island, else None), ...)}, seams (edges), mirror_err (mm))"""
    V = np.asarray(V_mm, float)
    Q = np.asarray(Q, np.int64)
    E_cut, loops = cut_edges(cuts, records)
    lab = UVM.islands(Q, np.array(sorted(E_cut)))
    names = name_islands(Q, lab, loops, terms)
    by_name = {nm: l for l, nm in names.items()}
    vn = _vertex_normals(V, Q)
    Mv, mirror_err = mirror_map(V)
    seams = set(E_cut)
    info = {}
    for l in sorted(names, key=lambda l_: names[l_].endswith('_R')):          # the left twins first
        nm = names[l]
        Qi = Q[lab == l]
        kd = kind_of(nm)
        twin = by_name.get(nm[:-2] + '_L') if nm.endswith('_R') else None
        if twin is not None:
            # stacked only where the island is its twin's exact mirror: every vertex with its twin, every face too
            vs_ = np.unique(Qi)
            fl_ = {frozenset(q.tolist()) for q in Q[lab == twin]}
            if (Mv[vs_] < 0).any() or any(frozenset(Mv[q].tolist()) not in fl_ for q in Qi):
                twin = None
        if twin is not None:
            sL = info[twin]['seam_set']
            s, ng = {(min(Mv[a], Mv[b]), max(Mv[a], Mv[b])) for a, b in sL}, info[twin]['joined']
        else:
            side = nm[-1] if nm[-2:] in ('_L', '_R') else 'L'
            p = seam_side(kd, side, chain)
            vs = set(np.unique(Qi).tolist())
            # (a closed end's terminal on a cut loop is no closed end: a tip cap is a disk already, and the toe's tip
            # vertex on its cap's ring would have run a seam on across the toe's top)
            bnd = set(int(i) for lp in LF.boundary_loop(QuadMesh(V, Qi)) for i in lp)
            tt = [v for k, v in terms.items() if v in vs and v not in bnd]
            holes = [set(int(i) for i in loops[h]) for h in HOLES.get(kd, ()) if h in loops]
            s, ng = island_seams(V, Qi, vn, p, [] if kd == 'tipcap' else tt, star=(kd == 'foot'), holes=holes)
        seams |= s
        info[l] = dict(name=nm, set=SET_OF[kd], share=SHARE.get(kd, 1.0), n_faces=int(len(Qi)), joined=ng,
                       seam_edges=len(s), seam_set=s, twin=twin, holes=(len(holes) if twin is None else
                                                                        info[twin]['holes']))
    Vn, Qn, orig = UVM.split(V, Q, lab, np.array(sorted(seams)))
    Vm = Vn * 1e-3
    UVloc = np.zeros((len(Vn), 2))
    per_set = defaultdict(list)
    for l, d in info.items():
        f = np.nonzero(lab == l)[0]
        vids = np.unique(Qn[f])
        loc = -np.ones(len(Vn), np.int64)
        loc[vids] = np.arange(len(vids))
        Ql = loc[Qn[f]]
        Ft = UVM._tri(Ql)
        Vi = Vm[vids]
        # a disk: V - E + F = 1 and one boundary
        ed = set()
        for q in Ql:
            for k in range(4):
                a, b = int(q[k]), int(q[(k + 1) % 4])
                ed.add((min(a, b), max(a, b)))
        d['euler'] = int(len(vids) - len(ed) + len(Ql))
        d['boundaries'] = len(LF.boundary_loop(QuadMesh(Vi, Ql)))
        d['vids'], d['tri'] = vids, Ft
        if d['twin'] is not None:
            continue
        U = UVM.lscm(Vi, Ft)
        U = UVM.arap(Vi, Ft, U, iters=ARAP_ITERS)
        # the winding: UV triangles counter-clockwise as the quads face outward
        t0, t1, t2 = U[Ft[:, 0]], U[Ft[:, 1]], U[Ft[:, 2]]
        sa = (t1[:, 0] - t0[:, 0]) * (t2[:, 1] - t0[:, 1]) - (t1[:, 1] - t0[:, 1]) * (t2[:, 0] - t0[:, 0])
        if (sa < 0).mean() > 0.5:
            U[:, 0] = -U[:, 0]
            sa = -sa
        d['uv_flipped'] = int((sa <= 0).sum())
        dens = UVM.island_density(Vi, Ft, U)                      # UV units per metre
        d['scale'] = SETS[d['set']]['ppm'] * d['share'] / dens   # texels per UV unit
        UVloc[vids] = _min_box(U)
        per_set[d['set']].append(l)
    UV = np.zeros((len(Vn), 2))
    used = {}
    for st, ls in per_set.items():
        out, h = _pack([(UVloc[info[l]['vids']] * info[l]['scale'], info[l]['tri']) for l in ls], SETS[st]['size'])
        for l, U in zip(ls, out):
            UV[info[l]['vids']] = U
        used[st] = float(h)
    # the stacked right islands: each face's corners take its left twin's (the mirrored face's) UVs
    for l, d in info.items():
        if d['twin'] is None:
            continue
        fl = np.nonzero(lab == d['twin'])[0]
        key = {frozenset(Q[g].tolist()): g for g in fl}
        for f in np.nonzero(lab == l)[0]:
            g = key[frozenset(Mv[Q[f]].tolist())]
            for k in range(4):
                j = int(np.nonzero(Q[g] == Mv[Q[f][k]])[0][0])
                UV[Qn[f][k]] = UV[Qn[g][j]]
        Ft = d['tri']
        U = UV[d['vids']]
        t0, t1, t2 = U[Ft[:, 0]], U[Ft[:, 1]], U[Ft[:, 2]]
        sa = (t1[:, 0] - t0[:, 0]) * (t2[:, 1] - t0[:, 1]) - (t1[:, 1] - t0[:, 1]) * (t2[:, 0] - t0[:, 0])
        d['uv_flipped'] = int((sa >= 0).sum())                    # mirrored: every triangle clockwise
        d['scale'] = info[d['twin']]['scale']
    face_set = np.array([info[l]['set'] for l in lab])
    for l, d in info.items():
        log(f'[uv]   island {d["name"]:>12s} {d["set"]} x{d["share"]:.1f}: {d["n_faces"]} quads, {d["joined"]} '
            f'boundaries / ends joined by {d["seam_edges"]} seam edges; euler {d["euler"]}, boundaries '
            f'{d["boundaries"]}' + (f' ({d["holes"]} open holes)' if d['holes'] else '') + ', '
            + (f'STACKED on {info[d["twin"]]["name"]} (mirrored), unmirrored UV triangles '
                                      if d['twin'] is not None else 'flipped UV triangles ') + f'{d["uv_flipped"]}')
    return dict(uv=UV, Qn=Qn, Vn=Vn, orig=orig, lab=lab, face_set=face_set, islands=info, used=used,
                seams=seams, mirror_err=mirror_err)


def stats(L):
    """the plan's §4.7 gates per set: overlaps (texels under two triangles at the set's size, over the UNIQUE islands:
    a stacked twin lies on its left by design), anisotropy p95 (area-weighted s1 / s2), density p10 / p90
    (area-weighted, relative to the set's px/m x the island's share), fill (the unique islands' texel area / the sheet)"""
    Vm = L['Vn'] * 1e-3
    out = {}
    for st in SETS:
        ls = [l for l, d in L['islands'].items() if d['set'] == st]
        lu = [l for l in ls if L['islands'][l]['twin'] is None]
        F = np.vstack([L['Qn'][L['lab'] == l] for l in ls])
        rel_f = np.concatenate([np.full(int((L['lab'] == l).sum()), L['islands'][l]['share']) for l in ls])
        Ft = UVM._tri(F)                                          # (all faces' first triangles, then their seconds)
        rel = np.concatenate([rel_f, rel_f])
        s1, s2, ok = UVM.stretch(Vm, Ft, L['uv'])
        a3 = 0.5 * np.linalg.norm(np.cross(Vm[Ft[:, 1]] - Vm[Ft[:, 0]], Vm[Ft[:, 2]] - Vm[Ft[:, 0]]), axis=1)
        d1, d2 = L['uv'][Ft[:, 1]] - L['uv'][Ft[:, 0]], L['uv'][Ft[:, 2]] - L['uv'][Ft[:, 0]]
        a2 = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
        size, ppm = SETS[st]['size'], SETS[st]['ppm']
        dens = np.sqrt(a2 / np.maximum(a3, 1e-20)) * size / (ppm * rel)

        def wp(x, q):
            o = np.argsort(x)
            c = np.cumsum(a3[o])
            return float(x[o][min(np.searchsorted(c, q / 100.0 * c[-1]), len(o) - 1)])
        an = s1 / s2
        Fu = UVM._tri(np.vstack([L['Qn'][L['lab'] == l] for l in lu]))
        du1, du2 = L['uv'][Fu[:, 1]] - L['uv'][Fu[:, 0]], L['uv'][Fu[:, 2]] - L['uv'][Fu[:, 0]]
        out[st] = dict(overlap=_overlap(L['uv'], Fu, size), aniso_p95=wp(an, 95), dens_p10=wp(dens, 10),
                       dens_p90=wp(dens, 90), fill=float((0.5 * np.abs(du1[:, 0] * du2[:, 1] - du1[:, 1] * du2[:, 0])).sum()),
                       used=L['used'][st], n_islands=len(ls), n_stacked=len(ls) - len(lu))
    return out


def _overlap(UV, F, size):
    """texels (at the sheet's size) whose centre lies inside two or more triangles"""
    cnt = np.zeros((size, size), np.int32)
    T = UV * size
    for a, b, c in T[F]:
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if x1 < x0 or y1 < y0 or abs(den) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        inside = (l0 > 1e-4) & (l1 > 1e-4) & (1.0 - l0 - l1 > 1e-4)
        cnt[gy[inside].astype(int), gx[inside].astype(int)] += 1
    return int((cnt > 1).sum())
