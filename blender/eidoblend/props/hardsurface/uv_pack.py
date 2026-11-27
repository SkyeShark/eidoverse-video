"""eidoblend.props.hardsurface.uv_pack: a raster UV packer (Blender's own packer leaves about 40 % of a hard-surface
atlas empty; this one fills 58-78 %).

    from eidoblend.props.hardsurface import uv_pack
    fill = uv_pack.pack(objs, {o.name: [weight per face] for o in objs}, N=1024, gutter=2)

Islands are found by UV connectivity, each turned to its smallest bounding rectangle and scaled by a texel-density
weight per face (a hidden face small, a printed one large). They are dropped largest footprint first into a bitmap of
the atlas (N x N cells) at one common scale: rectangle-like islands are tested with a summed-area table, irregular ones
(rings, frames, L shapes) with an FFT overlap test against their exact footprint, so small islands nest in the holes of
big ones. A binary search finds the largest scale at which everything fits; the leftover room is then spread between
the islands. Footprints are rasterised conservatively and grown by `gutter` cells, so islands never touch. A seen island
narrower than three cells is stretched across to three (a thin edge gets texels of its own), so an island never takes
fewer cells than its footprint at a vanishing scale (`least_cells`): when those alone outgrow the atlas, `pack` raises a
ValueError instead of searching. Islands of the objects named in `top` are laid as long rows across the top of the map
instead (a strap's strips). Cost: the carbine's prep, its 1,009 islands packed at N = 1024, takes about 12 minutes; at
N = 512 about 5.
"""

import math

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.geometry import convex_hull_2d


def islands_of(bm, uv):
    """Faces grouped into UV islands: neighbours across an edge whose two UV ends agree on both sides."""
    parent = list(range(len(bm.faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        f1, f2 = lf
        same = True
        for v in e.verts:
            u1 = next(lp[uv].uv for lp in f1.loops if lp.vert == v)
            u2 = next(lp[uv].uv for lp in f2.loops if lp.vert == v)
            if (u1 - u2).length > 1e-6:
                same = False
                break
        if same:
            a, b = find(f1.index), find(f2.index)
            if a != b:
                parent[a] = b
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f.index)
    return list(groups.values())


class Island:
    def __init__(self, bm, uv, faces, weight):
        self.bm, self.uv, self.weight = bm, uv, weight
        self.loops = [lp for i in faces for lp in bm.faces[i].loops]
        pts = np.array([tuple(lp[uv].uv) for lp in self.loops], np.float64)
        idx = {id(lp): k for k, lp in enumerate(self.loops)}
        tris = []
        for i in faces:
            ls = [idx[id(lp)] for lp in bm.faces[i].loops]
            for j in range(1, len(ls) - 1):
                tris.append((ls[0], ls[j], ls[j + 1]))
        self.tris = np.array(tris, np.int64)
        # turn to the smallest bounding rectangle (rotating calipers over the hull)
        hull = [pts[i] for i in convex_hull_2d([Vector(p) for p in pts])]
        best = (1e30, 0.0)
        for k in range(len(hull)):
            ex, ey = hull[(k + 1) % len(hull)] - hull[k]
            if abs(ex) + abs(ey) < 1e-12:
                continue
            a = -math.atan2(ey, ex)
            c, s = math.cos(a), math.sin(a)
            q = pts @ np.array([[c, s], [-s, c]])
            area = np.ptp(q[:, 0]) * np.ptp(q[:, 1])
            if area < best[0]:
                best = (area, a)
        c, s = math.cos(best[1]), math.sin(best[1])
        q = pts @ np.array([[c, s], [-s, c]])
        if np.ptp(q[:, 1]) > np.ptp(q[:, 0]):              # lie long side along u
            q = q @ np.array([[0.0, 1.0], [-1.0, 0.0]])
        self.q = (q - q.min(axis=0)) * weight              # rest shape: weighted, rotated, at the origin
        a2 = self.q[self.tris]
        self.area = 0.5 * np.abs((a2[:, 1, 0] - a2[:, 0, 0]) * (a2[:, 2, 1] - a2[:, 0, 1]) -
                                 (a2[:, 1, 1] - a2[:, 0, 1]) * (a2[:, 2, 0] - a2[:, 0, 0])).sum()
        self.box = float(np.ptp(self.q[:, 0]) * np.ptp(self.q[:, 1]))

    MIN_CELLS = 3.0

    def footprint(self, scale_cells, k, gutter):
        """Cell coordinates of the loops for quarter turn k, and the conservative footprint grown by the gutter. A seen
        island narrower than MIN_CELLS is stretched across to it (only across: its length keeps the common scale)."""
        q = self.q * scale_cells
        if self.weight >= 0.1:
            for ax in (0, 1):
                ext = np.ptp(q[:, ax])
                if ext < self.MIN_CELLS:
                    q = q.copy()
                    q[:, ax] = (q[:, ax] - q[:, ax].min()) * (self.MIN_CELLS / max(ext, 1e-6))
        for _ in range(k):
            q = q @ np.array([[0.0, 1.0], [-1.0, 0.0]])
        pad = gutter + 1
        p = q - q.min(axis=0) + pad
        w = int(math.ceil(p[:, 0].max() + pad))
        h = int(math.ceil(p[:, 1].max() + pad))
        m = np.zeros((h, w), bool)
        infl = 0.71                                        # a cell any triangle touches has its centre this close
        for t in p[self.tris]:
            x0, x1 = int(math.floor(t[:, 0].min() - infl)), int(math.ceil(t[:, 0].max() + infl))
            y0, y1 = int(math.floor(t[:, 1].min() - infl)), int(math.ceil(t[:, 1].max() + infl))
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            inside = np.ones(X.shape, bool)
            a, b, c = t
            sgn = 1.0 if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) >= 0 else -1.0
            for p0, p1 in ((a, b), (b, c), (c, a)):
                ex, ey = p1 - p0
                L = math.hypot(ex, ey)
                if L > 1e-12:
                    inside &= sgn * (ex * (Y - p0[1]) - ey * (X - p0[0])) / L >= -infl
            m[y0:y1 + 1, x0:x1 + 1] |= inside
        for _ in range(gutter):
            n = m.copy()
            n[1:, :] |= m[:-1, :]
            n[:-1, :] |= m[1:, :]
            n[:, 1:] |= m[:, :-1]
            n[:, :-1] |= m[:, 1:]
            n[1:, 1:] |= m[:-1, :-1]
            n[1:, :-1] |= m[:-1, 1:]
            n[:-1, 1:] |= m[1:, :-1]
            n[:-1, :-1] |= m[1:, 1:]
            m = n
        return p, m


ORDERS = {
    'box': lambda isl: -isl.box,                                   # biggest footprint first
    'side': lambda isl: -max(np.ptp(isl.q[:, 0]), np.ptp(isl.q[:, 1])),
    'short': lambda isl: -min(np.ptp(isl.q[:, 0]), np.ptp(isl.q[:, 1])),
}


def _pack(islands, scale_cells, N, gutter, rule='top', occ0=None):
    occ = np.zeros((N, N), bool) if occ0 is None else occ0.copy()
    sat, occ_f = None, None
    out = []
    for isl in islands:
        best = None
        rect_like = None
        for k in range(4):
            p, m = isl.footprint(scale_cells, k, gutter)
            h, w = m.shape
            if h > N or w > N:
                continue
            if rect_like is None:
                rect_like = m.mean() > 0.9
            if rect_like and k > 1:
                break
            if rect_like:
                if sat is None:
                    sat = np.zeros((N + 1, N + 1), np.int32)
                    sat[1:, 1:] = occ.cumsum(0, dtype=np.int32).cumsum(1, dtype=np.int32)
                tot = sat[h:, w:] - sat[:-h, w:] - sat[h:, :-w] + sat[:-h, :-w]
                free = tot == 0
            else:
                if occ_f is None:
                    occ_f = np.fft.rfft2(occ.astype(np.float64))
                pad = np.zeros((N, N))
                pad[:h, :w] = m
                corr = np.fft.irfft2(occ_f * np.conj(np.fft.rfft2(pad)), s=(N, N))
                free = corr[:N - h + 1, :N - w + 1] < 0.5
            ys, xs = np.nonzero(free)
            if not len(ys):
                continue
            if rule == 'top':                                  # lowest top edge, then leftmost
                key = (ys + h, xs)
            elif rule == 'bottom':                             # classic bottom-left: lowest bottom edge
                key = (ys, xs)
            else:                                              # 'corner': nearest the origin corner
                key = (np.maximum(ys + h, xs + w), ys + h + xs + w)
            i = np.lexsort((key[1], key[0]))[0]
            cand = (int(key[0][i]), int(key[1][i]), int(ys[i]), k, p, m, int(xs[i]))
            if best is None or cand[:2] < best[:2]:
                best = cand
        if best is None:
            return None
        _, _, y, k, p, m, x = best
        occ[y:y + m.shape[0], x:x + m.shape[1]] |= m
        sat, occ_f = None, None
        out.append((isl, p + (x, y), x, y, m))
    return out, occ


def _pack_any(islands, scale, N, gutter, combos, occ0=None):
    for order, rule in combos:
        fit = _pack(sorted(islands, key=ORDERS[order]), scale, N, gutter, rule, occ0)
        if fit is not None:
            return fit
    return None


def _spread(placed, N, H):
    """Give the islands the leftover room instead of leaving it blank on one side: their origins scale away from the
    corner as far as the region (N wide, H tall) allows. An island inside another's box rides along with it. Bisects
    back if anything would touch."""
    boxes = [(x, y, x + m.shape[1], y + m.shape[0]) for (_, _, x, y, m) in placed]
    parent = []
    for i, bi in enumerate(boxes):
        best = None
        for j, bj in enumerate(boxes):
            if i != j and bj[0] <= bi[0] and bj[1] <= bi[1] and bj[2] >= bi[2] and bj[3] >= bi[3] and bj != bi:
                a = (bj[2] - bj[0]) * (bj[3] - bj[1])
                if best is None or a < best[0]:
                    best = (a, j)
        parent.append(best[1] if best else -1)

    def root(i):
        while parent[i] >= 0:
            i = parent[i]
        return i
    roots = sorted({root(i) for i in range(len(placed))})
    ax = min([(N - (boxes[r][2] - boxes[r][0])) / boxes[r][0] for r in roots if boxes[r][0] > 0] or [1.0])
    ay = min([(H - (boxes[r][3] - boxes[r][1])) / boxes[r][1] for r in roots if boxes[r][1] > 0] or [1.0])
    ax, ay = max(ax, 1.0), max(ay, 1.0)

    def layout(t):
        fx, fy = 1 + t * (ax - 1), 1 + t * (ay - 1)
        new = {r: (int(boxes[r][0] * fx), int(boxes[r][1] * fy)) for r in roots}
        return [(boxes[i][0] + new[root(i)][0] - boxes[root(i)][0], boxes[i][1] + new[root(i)][1] - boxes[root(i)][1])
                for i in range(len(placed))]

    def fits(pos):
        occ = np.zeros((H, N), np.uint8)
        for (x, y), (_, _, _, _, m) in zip(pos, placed):
            h, w = m.shape
            if x < 0 or y < 0 or x + w > N or y + h > H:
                return False
            occ[y:y + h, x:x + w] += m
        return occ.max() <= 1
    t = 1.0
    if not fits(layout(1.0)):
        lo, hi = 0.0, 1.0
        for _ in range(9):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if fits(layout(mid)) else (lo, mid)
        t = lo
    pos = layout(t)
    return [(isl, p + (nx - x, ny - y), nx, ny, m) for (isl, p, x, y, m), (nx, ny) in zip(placed, pos)], t


def least_cells(islands, gutter=2):
    """The cells the islands' footprints take at their smallest: at a vanishing scale a seen island is stretched to
    MIN_CELLS across both ways and a hidden one shrinks to a point, each still ringed by its gutter. More than the atlas
    holds means no scale fits."""
    return sum(int(isl.footprint(1e-3 / max(float(np.ptp(isl.q, axis=0).max()), 1e-12), 0, gutter)[1].sum()) for isl in islands)


def pack(objs, face_weights, N=1024, gutter=2, log=print, combos=(('box', 'corner'), ('box', 'bottom'), ('box', 'top')),
         top=()):
    """Pack every UV island of objs (meshes with one active UV layer) into the unit square at the largest common
    scale. face_weights: {object name: [weight per face]} (an island takes its largest). Returns the share of the
    square covered by islands."""
    bms, islands = [], []
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv.active
        fw = face_weights[o.name]
        for faces in islands_of(bm, uv):
            isl = Island(bm, uv, faces, max(fw[i] for i in faces))
            isl.obj = o.name
            islands.append(isl)
        bms.append((o, bm))
    occ0 = np.zeros((N, N), bool)
    rows, placed_top, s_top = N, [], 0.0
    strips = [i for i in islands if i.obj in top]
    if strips:
        longest = max(np.ptp(i.q[:, 0]) for i in strips)
        strips = [i for i in strips if np.ptp(i.q[:, 0]) > 0.3 * longest]      # the end caps pack with the rest
        s_top = (N - 2 * (gutter + 2)) / longest
        for isl in sorted(strips, key=lambda i: -np.ptp(i.q[:, 0])):
            p, m = isl.footprint(s_top, 0, gutter)
            h, w = m.shape
            rows -= h
            x = (N - w) // 2
            occ0[rows:rows + h, x:x + w] |= m
            placed_top.append((isl, p + (x, rows), x, rows, m))
    rest = [i for i in islands if not any(i is t[0] for t in placed_top)]
    least = least_cells(rest, gutter)
    if least > N * rows:
        raise ValueError(f'uv_pack: {len(rest)} islands need at least {least:,} cells at their smallest, more than the '
                         f'{N * rows:,} cells of {N} x {N} left to them: pack with more cells')
    total = sum(isl.area for isl in rest)
    s0 = math.sqrt(0.75 * rows / N / total) * N             # cells per rest unit at ~75 % of the room left
    lo, hi = 0.90 * s0, 1.12 * s0
    fit = _pack_any(rest, lo, N, gutter, combos, occ0)
    tries = 0
    while fit is None:                                      # make sure the low end fits
        lo *= 0.9
        tries += 1
        if tries > 40:
            raise ValueError(f'uv_pack: {len(rest)} islands do not fit {N} x {N} cells: pack with more cells')
        fit = _pack_any(rest, lo, N, gutter, combos, occ0)
    best = (lo, fit)
    for _ in range(6):
        mid = (lo + hi) / 2
        fit = _pack_any(rest, mid, N, gutter, combos, occ0)
        if fit is None:
            hi = mid
        else:
            lo, best = mid, (mid, fit)
    scale, (placed, occ) = best
    placed, t = _spread(placed, N, rows)
    for isl, p, *_ in placed_top + placed:
        for lp, c in zip(isl.loops, p / N):
            lp[isl.uv].uv = Vector(c)
    for o, bm in bms:
        bm.to_mesh(o.data)
        bm.free()
    covered = (sum(isl.area for isl in rest) * (scale / N) ** 2 +
               sum(isl.area for isl in strips) * (s_top / N) ** 2)
    log(f'[uv_pack] {len(islands)} islands ({len(strips)} rows across the top): {covered * 100:.1f} % of the square is '
        f'island; leftover room spread {t * 100:.0f} %')
    return covered
