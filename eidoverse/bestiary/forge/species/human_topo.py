"""HUMAN H1: quad-mesh TOPOLOGY helpers for the baseline cage (the GNM-topology head and the designed body).

    Topo(Q, n)                          edges, edge -> quads, vertex -> quads, valence, neighbours, boundary
    Topo.straight(prev, cur)            the edge-loop continuation through a valence-4 vertex (the neighbour sharing no
                                        quad with prev), None at a pole or the boundary
    Topo.loop_from(a, b)                the closed edge loop through the edge (a, b), or None
    Topo.block(c, w, a, b)              a REGULAR a x b block of quads centred on vertex c (a, b even), its rows along c -> w:
                                        the (a+1) x (b+1) vertex grid, or None if it meets a pole
    Topo.side_of(loop, seed_quad)       the quads on the seed's side of a closed loop (a flood fill that never crosses it)
    band(O, n_inner, units_at, new_id)  one REDUCTION BAND under a closed outer loop O: 4 -> 2 units at the given centres
                                        (outer loop positions), passes elsewhere; returns the inner loop, the quads, the
                                        units' middle vertices and, per inner vertex, the outer position it hangs from
    unit_centres(n_o, n_i, front, back, forbidden)   symmetric unit centres (a mirror pair for every unit off the midline,
                                        one centred on the back midline when the per-half reduction is odd), evenly spread,
                                        never on a forbidden apex (the band above's inner apexes: a doublet)
"""
import collections

import numpy as np


class Topo:
    def __init__(self, Q, n=None):
        self.Q = np.asarray(Q, np.int64)
        self.n = int(self.Q.max()) + 1 if n is None else int(n)
        self.emap = collections.defaultdict(list)
        self.vq = collections.defaultdict(list)
        for qi, q in enumerate(self.Q.tolist()):
            for k in range(4):
                a, b = q[k], q[(k + 1) % 4]
                self.emap[(min(a, b), max(a, b))].append(qi)
                self.vq[q[k]].append(qi)
        self.nbr = collections.defaultdict(set)
        for (a, b) in self.emap:
            self.nbr[a].add(b)
            self.nbr[b].add(a)
        self.val = np.zeros(self.n, int)
        for v, s in self.nbr.items():
            self.val[v] = len(s)
        self.bnd = set()
        for e, lst in self.emap.items():
            if len(lst) == 1:
                self.bnd.update(e)
        self.qset = [set(q) for q in self.Q.tolist()]

    def quads_with(self, *vs):
        out = set(self.vq[vs[0]])
        for v in vs[1:]:
            out &= set(self.vq[v])
        return sorted(out)

    def straight(self, prev, cur):
        if self.val[cur] != 4 or cur in self.bnd:
            return None
        qp = [qi for qi in self.vq[cur] if prev in self.qset[qi]]
        for w in self.nbr[cur]:
            if w != prev and not any(w in self.qset[qi] for qi in qp):
                return w
        return None

    def loop_from(self, a, b, maxn=2000):
        L = [a, b]
        while len(L) < maxn:
            w = self.straight(L[-2], L[-1])
            if w is None:
                return None
            if w == L[0]:
                return L
            L.append(w)
        return None

    def fourth(self, a, b, c):
        """the fourth corner of the quad holding a, b, c (b the corner between a and c), or None"""
        for qi in self.quads_with(a, b, c):
            q = self.Q[qi].tolist()
            rest = [v for v in q if v not in (a, b, c)]
            if len(rest) == 1:
                return rest[0]
        return None

    def block(self, c, w, a, b):
        """an a x b block of quads centred on c, its first axis (a quads) along c -> w; G[i][j] for i in 0..a, j in 0..b
        (c at (a/2, b/2)); None if any vertex of the block (its boundary included) is a pole or on the boundary"""
        assert a % 2 == 0 and b % 2 == 0
        if self.val[c] != 4 or w not in self.nbr[c]:
            return None
        # the perpendicular at c: a neighbour of c sharing a quad with w
        perp = [x for x in self.nbr[c] if x != w and any(x in self.qset[qi] for qi in self.quads_with(c, w))]
        if not perp:
            return None
        p = perp[0]
        G = {}
        G[(0, 0)] = c

        def run(start, first, n):
            out = [start, first]
            while len(out) < n + 1:
                nx = self.straight(out[-2], out[-1])
                if nx is None:
                    return None
                out.append(nx)
            return out
        ax_p = run(c, w, a // 2)
        opp_w = self.straight(w, c)
        ax_m = run(c, opp_w, a // 2) if opp_w is not None else None
        bx_p = run(c, p, b // 2)
        opp_p = self.straight(p, c)
        bx_m = run(c, opp_p, b // 2) if opp_p is not None else None
        if None in (ax_p, ax_m, bx_p, bx_m):
            return None
        for k in range(1, a // 2 + 1):
            G[(k, 0)] = ax_p[k]
            G[(-k, 0)] = ax_m[k]
        for k in range(1, b // 2 + 1):
            G[(0, k)] = bx_p[k]
            G[(0, -k)] = bx_m[k]
        # fill the four quadrants, each cell's fourth corner from its three known ones
        for si in (1, -1):
            for sj in (1, -1):
                for i in range(1, a // 2 + 1):
                    for j in range(1, b // 2 + 1):
                        x = self.fourth(G[(si * (i - 1), sj * j)], G[(si * (i - 1), sj * (j - 1))],
                                        G[(si * i, sj * (j - 1))])
                        if x is None:
                            return None
                        G[(si * i, sj * j)] = x
        out = np.array([[G[(i - a // 2, j - b // 2)] for j in range(b + 1)] for i in range(a + 1)], np.int64)
        if any(self.val[v] != 4 or v in self.bnd for v in out.ravel().tolist()):
            return None
        if len(set(out.ravel().tolist())) != out.size:
            return None
        return out

    def side_of(self, loop, seed_quad):
        """the quads reachable from seed_quad without crossing an edge of the closed loop"""
        cut = set()
        L = list(loop)
        for a, b in zip(L, L[1:] + L[:1]):
            cut.add((min(a, b), max(a, b)))
        seen = np.zeros(len(self.Q), bool)
        seen[seed_quad] = True
        stack = [seed_quad]
        while stack:
            qi = stack.pop()
            q = self.Q[qi].tolist()
            for k in range(4):
                e = (min(q[k], q[(k + 1) % 4]), max(q[k], q[(k + 1) % 4]))
                if e in cut:
                    continue
                for qj in self.emap[e]:
                    if not seen[qj]:
                        seen[qj] = True
                        stack.append(qj)
        return seen


def grid_loop(G):
    """the boundary loop of a block's vertex grid G (a+1, b+1), in order round the block, and its interior"""
    a, b = G.shape[0] - 1, G.shape[1] - 1
    loop = [G[0, j] for j in range(b)] + [G[i, b] for i in range(a)] + [G[a, j] for j in range(b, 0, -1)] + \
           [G[i, 0] for i in range(a, 0, -1)]
    inner = G[1:a, 1:b].ravel().tolist()
    return [int(v) for v in loop], [int(v) for v in inner]


def unit_centres(n_o, n_i, front, back, forbidden=(), midline_unit='back'):
    """the centres (outer loop positions) of the 4 -> 2 units that take a closed loop of n_o vertices to n_i, mirror
    symmetric about the loop's front and back midline positions (front, back: their indices; the loop runs front -> one
    side -> back -> the other side). A unit's centre is its middle outer vertex (its apex, valence 3 after the band);
    it covers the outer positions centre-2 .. centre+2. Returns the sorted centres"""
    assert (n_o - n_i) % 2 == 0
    nu = (n_o - n_i) // 2
    half = (back - front) % n_o                       # the outer edges on the side front -> back
    forb = set(int(f) % n_o for f in forbidden)
    centres = []
    if nu % 2 == 1:
        c = back if midline_unit == 'back' else front
        centres.append(c % n_o)
        nu -= 1
    k = nu // 2                                       # mirror pairs
    # the free stretch on one side: from front + 2 (clear of a front unit's reach) to back - 3 (clear of the back's)
    lo = 3
    hi = half - (5 if centres and centres[0] == back % n_o else 3)
    if k:
        ideal = [lo + (hi - lo) * (j + 0.5) / k for j in range(k)]
        chosen = []
        prev = lo - 4
        for j, x in enumerate(ideal):
            cands = sorted(range(prev + 4, hi + 1), key=lambda s: abs(s - x))
            ok = None
            for s in cands:
                pa, pb = (front + s) % n_o, (front - s) % n_o
                if pa in forb or pb in forb:
                    continue
                # leave room for the units still to place
                if s + 4 * (k - 1 - j) > hi:
                    continue
                ok = s
                break
            assert ok is not None, 'no unit position avoids the forbidden apexes'
            chosen.append(ok)
            prev = ok
        for s in chosen:
            centres.append((front + s) % n_o)
            centres.append((front - s) % n_o)
    return sorted(centres)


def band_pattern(n_o, centres):
    """the inner loop's hang positions (the outer position each inner vertex hangs from, walking from the first
    position that starts a token) for units at `centres`: what band() will build, without building it"""
    cs = sorted(int(c) % n_o for c in centres)
    covered = np.zeros(n_o, int)
    start_of = set()
    for c in cs:
        for d in range(-2, 2):
            covered[(c + d) % n_o] += 1
        start_of.add((c - 2) % n_o)
    s0 = 0
    while covered[s0] and s0 not in start_of:
        s0 += 1
    hang, o, steps = [s0], s0, 0
    while steps < n_o:
        if o % n_o in start_of:
            hang += [(o + 2) % n_o] + ([(o + 4) % n_o] if steps + 4 < n_o else [])
            o, steps = o + 4, steps + 4
        else:
            if steps + 1 < n_o:
                hang.append((o + 1) % n_o)
            o, steps = o + 1, steps + 1
    return hang


def band(O, n_i, centres, new_id, inner_ids=None):
    """a reduction band under the closed outer loop O (vertex ids, in order; the band's quads are wound so each outer
    edge (O[k], O[k+1]) is traversed O[k+1] -> O[k], i.e. against the loop, as a quad on the far side of the loop from
    the band runs it O[k] -> O[k+1]). centres: unit centres (outer positions). new_id(): a fresh vertex id; inner_ids: an
    EXISTING inner loop to end on instead (in walk order: inner_ids[0] under the walk's first position, band_pattern's
    hang[0]). Returns dict(inner=[ids] (closed, inner[0] under O[start]), quads, mids=[(m, outer centre, inner apex)],
    hang=[outer position each inner vertex hangs from], apex_inner=[inner positions of the units' inner apexes])"""
    n_o = len(O)
    cs = sorted(int(c) % n_o for c in centres)
    nu = len(cs)
    assert n_o - 2 * nu == n_i, (n_o, nu, n_i)
    if inner_ids is not None:
        assert len(inner_ids) == n_i
        it = iter(list(inner_ids))
        fresh = new_id

        def inner_id():
            return next(it)
    else:
        fresh = new_id
        inner_id = new_id
    covered = np.zeros(n_o, int)
    start_of = {}
    for c in cs:
        for d in range(-2, 2):
            covered[(c + d) % n_o] += 1
        start_of[(c - 2) % n_o] = c
    assert covered.max() <= 1, 'units overlap'
    # start the walk at an outer position that begins a token (a pass or a unit's first edge)
    s0 = 0
    while covered[s0] and s0 not in start_of:
        s0 += 1
    new_id = inner_id
    inner = [new_id()]
    hang = [s0]
    quads, mids, apex = [], [], []
    o = s0
    steps = 0
    while steps < n_o:
        if o % n_o in start_of:
            m = fresh()
            o0, o1, o2, o3, o4 = (O[(o + d) % n_o] for d in range(5))
            i0 = inner[-1]
            i1 = new_id()
            i2 = new_id() if steps + 4 < n_o else inner[0]
            # (o0 o1 m i0) (o1 o2 o3 m) (o3 o4 i2 m) (i0 m i2 i1): the outer edges run o1->o0 etc. (against the loop)
            quads += [(o1, o0, i0, m), (o2, o1, m, o3), (o4, o3, m, i2), (i0, i1, i2, m)]
            mids.append((m, (o + 2) % n_o, len(inner)))
            apex.append(len(inner))
            inner.append(i1)
            hang.append((o + 2) % n_o)
            if i2 != inner[0]:
                inner.append(i2)
                hang.append((o + 4) % n_o)
            o += 4
            steps += 4
        else:
            i0 = inner[-1]
            i1 = new_id() if steps + 1 < n_o else inner[0]
            quads.append((O[(o + 1) % n_o], O[o % n_o], i0, i1))
            if i1 != inner[0]:
                inner.append(i1)
                hang.append((o + 1) % n_o)
            o += 1
            steps += 1
    assert len(inner) == n_i, (len(inner), n_i)
    return dict(inner=inner, quads=quads, mids=mids, hang=hang, apex_inner=apex)
