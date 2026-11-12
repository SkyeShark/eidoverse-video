"""The terrain's ring mesh (design section 8): one Blender mesh that draws every level as a ring (the level's window
minus its child's window), so vertex density falls off with distance from the focus. Seams are stitched, the
outermost ring has a skirt, the masks are point attributes, and height_at / normal_at read exactly its triangles.

    rm = build_rings(levels, heights, attributes={'slope': [a0, a1, ...]}, cores=True)
    rm.height_at(x, y)              # metres at Blender (x, y), on rm's triangles; floats or arrays
    rm.normal_at(x, y)              # the shading normal there
    obj = make_object(rm, 'terrain')

No bpy until make_object, so the geometry and its tests run in plain Python.

Frames (design 2.1). Blender axes, metres. A level is a square window: its south-west corner (x0, y0), n cells of
`cell` metres; its field values sit at the cell centres x = x0 + (i + 0.5) cell, y = y0 + (j + 0.5) cell, arrays
[row j, column i] with row 0 the south edge. Every window lies on its parent's cell grid and halves its cell, so every
window edge is a whole number of finest cells from the outermost window's corner. The rings are built on that
integer lattice, so a position two rings share is the same number in both.

Rings. A ring's vertices sit on its level's cell corners every `stride` cells (stride = n / mesh_res, rounded: 2 at
1024 cells), plus the lines its seams need (its hole's edges, its parent's lines). With cores=True (a focus is set)
the finest level is also drawn as cores: half its side at half the stride, down to stride 1, so triangles stay a few
pixels wide all the way to the camera. Each grid quad is split along its (i, j) - (i+1, j+1) diagonal, and the
triangles are written explicitly, so the split never depends on Blender's tessellation.

Heights. A vertex takes its level's field at the cell corner, by Catmull-Rom (weights -1, 9, 9, -1 over 16 per axis,
the interpolant the levels are upsampled with); mask attributes are bilinear there.

Seams. A ring's outermost vertex row lies on its parent ring's hole edge and takes the parent's straight edge there
(the linear interpolation of the two parent vertices); where the two rings have a vertex at the same place it is one
shared vertex. The parent's quads along the hole are drawn as fans through the child's in-between vertices, so no
T-junction is left. A fan lies in the plane of the triangle it replaces (to the float32 rounding of its in-between
vertices, which height_at follows exactly). A seam creases no more than an ordinary lattice line of the coarser ring
(tests/terrain/mesh_api/test_seam_crease.py); blending a ring toward its parent's surface near its border
(geomorphing) was measured and made the seam itself sharper, because it carries the parent's coarser facets inside.

Skirt. The outermost ring hangs a vertical skirt from its border (its own vertices, so the border's smooth shading
stays as it is) down to SKIRT_DROP_M below the lowest border vertex, so a low camera never sees under the world.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MESH_RES = 512               # vertices per side a level is drawn at: stride = round(n / MESH_RES)
SKIRT_DROP_M = 50.0          # the skirt's bottom, below the lowest border vertex
_CR = np.array([-1.0, 9.0, 9.0, -1.0]) / 16.0      # Catmull-Rom at a cell corner (half way between two centres)
_CR_OFF = np.array([-2, -1, 0, 1])
_BL = np.array([0.5, 0.5])                          # bilinear at a cell corner
_BL_OFF = np.array([-1, 0])


# ------------------------------------------------------------------------------------------------ windows ---

@dataclass(frozen=True)
class Window:
    """A level's square window: south-west corner (x0, y0), n cells of `cell` metres."""
    x0: float
    y0: float
    cell: float
    n: int

    @property
    def side(self):
        return self.cell * self.n


def as_window(level):
    """A Window from a level: anything with x0, y0, cell and n (attributes or keys), or the tuple
    (x0, y0, side, cell, n) of design 2.2."""
    if isinstance(level, Window):
        return level
    if isinstance(level, dict):
        return Window(float(level['x0']), float(level['y0']), float(level['cell']), int(level['n']))
    if all(hasattr(level, k) for k in ('x0', 'y0', 'cell', 'n')):
        return Window(float(level.x0), float(level.y0), float(level.cell), int(level.n))
    x0, y0, _side, cell, n = level
    return Window(float(x0), float(y0), float(cell), int(n))


@dataclass
class _IWin:
    """A window on the integer lattice (units of the finest cell from the outermost window's corner)."""
    x0: int
    y0: int
    ci: int                  # cell, in units
    n: int

    @property
    def x1(self):
        return self.x0 + self.n * self.ci

    @property
    def y1(self):
        return self.y0 + self.n * self.ci


def _integer_windows(windows):
    """(origin (X, Y) metres, unit metres, [_IWin]) for nested windows; raises if a window is off its parent's grid
    or a cell is not the finest cell times a power of two."""
    u = min(w.cell for w in windows)
    X, Y = windows[0].x0, windows[0].y0
    out = []
    for k, w in enumerate(windows):
        ci = w.cell / u
        if abs(ci - round(ci)) > 1e-6 * ci or round(ci) & (round(ci) - 1):
            raise ValueError(f'level {k}: cell {w.cell} m is not the finest cell {u} m times a power of two')
        fx, fy = (w.x0 - X) / u, (w.y0 - Y) / u
        if abs(fx - round(fx)) > 1e-5 or abs(fy - round(fy)) > 1e-5:
            raise ValueError(f'level {k}: window corner ({w.x0}, {w.y0}) is not on the finest cell grid from the '
                             f'outermost corner ({X}, {Y}); levels must be snapped to their parent cell grid')
        out.append(_IWin(int(round(fx)), int(round(fy)), int(round(ci)), int(w.n)))
    for k in range(1, len(out)):
        p, c = out[k - 1], out[k]
        if not (p.x0 <= c.x0 and c.x1 <= p.x1 and p.y0 <= c.y0 and c.y1 <= p.y1):
            raise ValueError(f'level {k} is not inside level {k - 1}')
        if (c.x0 - p.x0) % p.ci or (c.y0 - p.y0) % p.ci or (c.x1 - p.x0) % p.ci or (c.y1 - p.y0) % p.ci:
            raise ValueError(f'level {k}: window edges are not on level {k - 1}\'s cell grid')
    return (X, Y), u, out


# --------------------------------------------------------------------------------------------------- rings ---

@dataclass
class RingSpec:
    """One ring: the window (integer units), its vertex spacing (units) and the level whose field it draws."""
    level: int
    x0: int
    y0: int
    x1: int
    y1: int
    sp: int

    def as_list(self):
        return [self.level, self.x0, self.y0, self.x1, self.y1, self.sp]


def plan_rings(iwins, mesh_res=MESH_RES, cores=False):
    """The rings for nested integer windows: one per level at stride round(n / mesh_res), then (cores=True) the finest
    level again at half the side and half the stride, down to stride 1, centred in it and on its parent's lattice."""
    rings = []
    for k, w in enumerate(iwins):
        stride = max(1, int(round(w.n / float(mesh_res))))
        rings.append(RingSpec(k, w.x0, w.y0, w.x1, w.y1, stride * w.ci))
    if cores:
        k = len(iwins) - 1
        w = iwins[k]
        while rings[-1].sp > w.ci:
            P = rings[-1]
            sp = max(w.ci, (P.sp // 2) // w.ci * w.ci)
            side = (P.x1 - P.x0) // 2 // P.sp * P.sp
            margin = 2 * P.sp
            if side < 8 * sp or side > (P.x1 - P.x0) - 2 * margin:
                break
            cx, cy = (P.x0 + P.x1) / 2.0, (P.y0 + P.y1) / 2.0

            def snap(c, lo, hi):              # on the parent's lattice, at least `margin` inside it
                v = lo + int(round((c - side / 2.0 - lo) / P.sp)) * P.sp
                top = lo + (hi - margin - side - lo) // P.sp * P.sp
                return min(max(v, lo + margin), top)
            x0, y0 = snap(cx, P.x0, P.x1), snap(cy, P.y0, P.y1)
            rings.append(RingSpec(k, x0, y0, x0 + side, y0 + side, sp))
    return rings


@dataclass
class _Ring:
    spec: RingSpec
    hole: tuple              # (x0, y0, x1, y1) of the next ring's window, or None
    xs: np.ndarray           # lattice lines (integer units), ascending
    ys: np.ndarray
    idx: np.ndarray          # (len(ys), len(xs)) global vertex index, -1 inside the hole
    own: np.ndarray          # (len(ys), len(xs)) bool: vertices this ring adds (the rest are its parent's)
    v0: int                  # index of this ring's first own vertex
    hole_lines: tuple = None  # (jb, jt, il, ir): lattice rows / columns of the hole's bottom, top, left, right
    Z: np.ndarray = None     # (len(ys), len(xs)) heights as written (float32 values held in float64)
    xm: np.ndarray = None    # lattice lines in metres, as written (float32 values held in float64)
    ym: np.ndarray = None


def _find(sorted_arr, values):
    """Index of each value in a sorted integer array (they must be present)."""
    i = np.searchsorted(sorted_arr, values)
    i = np.minimum(i, len(sorted_arr) - 1)
    if not np.all(sorted_arr[i] == values):
        raise AssertionError('ring lattice: a seam line is missing from the parent lattice')
    return i


def _topology(specs, skirt):
    """Lattices, vertex indices and triangles of the rings (no heights). Returns (rings, n_vertices, triangles,
    skirt perimeter vertex indices or None). The order is a pure function of the specs, so terrain_height_at can
    rebuild it from the layout stored on the object."""
    rings = []
    nv = 0
    for k, s in enumerate(specs):
        hole = None
        if k + 1 < len(specs):
            c = specs[k + 1]
            hole = (c.x0, c.y0, c.x1, c.y1)
            if not (s.x0 < c.x0 and c.x1 < s.x1 and s.y0 < c.y0 and c.y1 < s.y1):
                raise ValueError(f'ring {k + 1} must lie strictly inside ring {k} (got {c.as_list()} in '
                                 f'{s.as_list()})')
        P = rings[k - 1] if k else None
        xs = [np.arange(s.x0, s.x1 + 1, s.sp, dtype=np.int64), np.array([s.x0, s.x1], np.int64)]
        ys = [np.arange(s.y0, s.y1 + 1, s.sp, dtype=np.int64), np.array([s.y0, s.y1], np.int64)]
        if hole:
            xs.append(np.array([hole[0], hole[2]], np.int64))
            ys.append(np.array([hole[1], hole[3]], np.int64))
        if P is not None:                     # the parent's lines that meet this ring's border: shared vertices
            xs.append(P.xs[(P.xs >= s.x0) & (P.xs <= s.x1)])
            ys.append(P.ys[(P.ys >= s.y0) & (P.ys <= s.y1)])
        xs = np.unique(np.concatenate(xs))
        ys = np.unique(np.concatenate(ys))
        ny, nx = len(ys), len(xs)
        used = np.ones((ny, nx), bool)
        if hole:
            inx = (xs > hole[0]) & (xs < hole[2])
            iny = (ys > hole[1]) & (ys < hole[3])
            used &= ~(iny[:, None] & inx[None, :])
        idx = np.full((ny, nx), -1, np.int64)
        if P is not None:
            jb, jt = _find(P.ys, np.array([s.y0, s.y1]))
            il, ir = _find(P.xs, np.array([s.x0, s.x1]))
            ipx = np.searchsorted(P.xs, xs).clip(0, len(P.xs) - 1)
            mx = P.xs[ipx] == xs
            jpy = np.searchsorted(P.ys, ys).clip(0, len(P.ys) - 1)
            my = P.ys[jpy] == ys
            idx[0, mx] = P.idx[jb, ipx[mx]]
            idx[-1, mx] = P.idx[jt, ipx[mx]]
            idx[my, 0] = P.idx[jpy[my], il]
            idx[my, -1] = P.idx[jpy[my], ir]
            if np.any(idx[0, mx] < 0) or np.any(idx[-1, mx] < 0) or np.any(idx[my, 0] < 0) or np.any(idx[my, -1] < 0):
                raise AssertionError(f'ring {k}: a shared seam vertex is unused in its parent')
        own = used & (idx < 0)
        cnt = int(own.sum())
        idx[own] = nv + np.arange(cnt)
        lines = None
        if hole:
            jb, jt = _find(ys, np.array([hole[1], hole[3]]))
            il, ir = _find(xs, np.array([hole[0], hole[2]]))
            lines = (int(jb), int(jt), int(il), int(ir))
        rings.append(_Ring(s, hole, xs, ys, idx, own, nv, lines))
        nv += cnt
    tris = [_ring_triangles(r, rings[k + 1] if k + 1 < len(rings) else None) for k, r in enumerate(rings)]
    tris = np.concatenate(tris).astype(np.int64)
    perim = None
    if skirt:
        idx = rings[0].idx
        perim = np.concatenate([idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]])   # CCW from above
    return rings, nv, tris, perim


def _fan(p, q, r, mids):
    pts = [q] + list(mids) + [r]
    return [(p, pts[t], pts[t + 1]) for t in range(len(pts) - 1)]


def _ring_triangles(r, child):
    xs, ys, idx = r.xs, r.ys, r.idx
    a = idx[:-1, :-1]
    b = idx[:-1, 1:]
    c = idx[1:, 1:]
    d = idx[1:, :-1]
    keep_abc = np.ones(a.shape, bool)
    keep_acd = np.ones(a.shape, bool)
    fans = []
    if r.hole:
        hx0, hy0, hx1, hy1 = r.hole
        qin_x = (xs[:-1] + xs[1:] > 2 * hx0) & (xs[:-1] + xs[1:] < 2 * hx1)
        qin_y = (ys[:-1] + ys[1:] > 2 * hy0) & (ys[:-1] + ys[1:] < 2 * hy1)
        in_hole = qin_y[:, None] & qin_x[None, :]
        keep_abc &= ~in_hole
        keep_acd &= ~in_hole
        jb, jt = _find(ys, np.array([hy0, hy1]))
        il, ir = _find(xs, np.array([hx0, hx1]))
        C = child
        cxs, cys, cidx = C.xs, C.ys, C.idx
        for i in range(il, ir):                                   # the quads along the hole's bottom and top
            lo = np.searchsorted(cxs, xs[i], 'right')
            hi = np.searchsorted(cxs, xs[i + 1], 'left')
            # below the hole (row jb-1): its top edge d-c on the hole; (a, c, d) fans from a, c -> d (x falling)
            keep_acd[jb - 1, i] = False
            fans += _fan(a[jb - 1, i], c[jb - 1, i], d[jb - 1, i], cidx[0, lo:hi][::-1])
            # above the hole (row jt): its bottom edge a-b on the hole; (a, b, c) fans from c, a -> b (x rising)
            keep_abc[jt, i] = False
            fans += _fan(c[jt, i], a[jt, i], b[jt, i], cidx[-1, lo:hi])
        for j in range(jb, jt):                                   # the quads along the hole's left and right
            lo = np.searchsorted(cys, ys[j], 'right')
            hi = np.searchsorted(cys, ys[j + 1], 'left')
            # left of the hole (column il-1): its right edge b-c on the hole; (a, b, c) fans from a, b -> c (y rising)
            keep_abc[j, il - 1] = False
            fans += _fan(a[j, il - 1], b[j, il - 1], c[j, il - 1], cidx[lo:hi, 0])
            # right of the hole (column ir): its left edge d-a on the hole; (a, c, d) fans from c, d -> a (y falling)
            keep_acd[j, ir] = False
            fans += _fan(c[j, ir], d[j, ir], a[j, ir], cidx[lo:hi, -1][::-1])
    out = [np.stack([a[keep_abc], b[keep_abc], c[keep_abc]], 1),
           np.stack([a[keep_acd], c[keep_acd], d[keep_acd]], 1)]
    if fans:
        out.append(np.array(fans, np.int64).reshape(-1, 3))
    return np.concatenate(out)


# ------------------------------------------------------------------------------------------------ sampling ---

def _taps(lines, w, kind):
    """Cell indices (len, taps) and weights (taps,) that evaluate a cell-centred field at cell-corner lines."""
    off = (lines - w.x0) if kind[1] == 'x' else (lines - w.y0)
    if np.any(off % w.ci):
        raise AssertionError('a ring vertex is not on its level\'s cell corners')
    m = off // w.ci
    o, wt = (_CR_OFF, _CR) if kind[0] == 'cr' else (_BL_OFF, _BL)
    return np.clip(m[:, None] + o[None, :], 0, w.n - 1), wt


def _sample(arr, w, xs, ys, kind):
    """A level's (n, n) cell-centred array at the corner lattice xs x ys: (len(ys), len(xs)); heights ('cr') in
    float64, masks ('bl') in float32. Rows are gathered first and the columns as rows of the transpose (contiguous
    copies: a column gather of a row-major array is several times slower)."""
    dt = np.float64 if kind == 'cr' else np.float32
    a = np.asarray(arr)
    ix, wx = _taps(xs, w, (kind, 'x'))
    iy, wy = _taps(ys, w, (kind, 'y'))
    t = a[iy[:, 0], :].astype(dt) * dt(wy[0])
    for q in range(1, len(wy)):
        t += a[iy[:, q], :] * dt(wy[q])
    tt = np.ascontiguousarray(t.T)
    z = tt[ix[:, 0], :] * dt(wx[0])
    for b in range(1, len(wx)):
        z += tt[ix[:, b], :] * dt(wx[b])
    return z.T


def _lattice_bilinear(a, my, mx):
    """A cell-centred (n, n) array's bilinear value at the cell corners my x mx (corner m sits between cells m - 1
    and m; edges clamped): (len(my), len(mx)) float32. Rows first, then the columns as rows of the transpose."""
    a = np.asarray(a, np.float32)
    n = a.shape[0]
    t = a[np.clip(my - 1, 0, n - 1)] + a[np.clip(my, 0, n - 1)]
    t = np.ascontiguousarray(t.T)
    z = t[np.clip(mx - 1, 0, n - 1)] + t[np.clip(mx, 0, n - 1)]
    z *= np.float32(0.25)
    return z.T


def _seam_override(Z, r, P, Pvals):
    """Set ring r's outer border on Z (its lattice) to its parent's straight edge. Pvals: the parent's values on its
    lattice (len(P.ys), len(P.xs))."""
    s = r.spec
    jb, jt = _find(P.ys, np.array([s.y0, s.y1]))
    il, ir = _find(P.xs, np.array([s.x0, s.x1]))
    Z[0, :] = np.interp(r.xs, P.xs, Pvals[jb, :])
    Z[-1, :] = np.interp(r.xs, P.xs, Pvals[jt, :])
    Z[:, 0] = np.interp(r.ys, P.ys, Pvals[:, il])
    Z[:, -1] = np.interp(r.ys, P.ys, Pvals[:, ir])


# ---------------------------------------------------------------------------------------------- ring mesh ---

class RingMesh:
    """The rings of one terrain: vertices (V, 3) float32, triangles (T, 3), point attributes {name: (V,) float32},
    the skirt's triangles last (terrain_triangles of them before it), and height_at / normal_at on them."""

    def __init__(self, origin, unit, windows, specs, rings, verts, tris, n_terrain_tris, attrs, skirt):
        self.origin = origin
        self.unit = unit
        self.windows = windows
        self.specs = specs
        self.rings = rings
        self.verts = verts
        self.tris = tris
        self.terrain_triangles = n_terrain_tris
        self.attrs = attrs
        self.skirt = skirt
        self._vn = None

    # metres <-> lattice -------------------------------------------------------------------------------------
    def _m(self, v, axis):
        return np.float32(self.origin[axis] + np.asarray(v, np.float64) * self.unit).astype(np.float64)

    @property
    def triangle_count(self):
        return int(len(self.tris))

    def bounds(self):
        """(xmin, ymin, xmax, ymax) of the outermost window, metres."""
        r = self.rings[0]
        return float(r.xm[0]), float(r.ym[0]), float(r.xm[-1]), float(r.ym[-1])

    def layout(self):
        """What rebuilds this mesh's lattices from the object (JSON-able)."""
        return dict(origin=[float(self.origin[0]), float(self.origin[1])], unit=float(self.unit),
                    windows=[[w.x0, w.y0, w.cell, w.n] for w in self.windows],
                    rings=[s.as_list() for s in self.specs], skirt=self.skirt is not None,
                    skirt_drop_m=(self.skirt or {}).get('drop_m', SKIRT_DROP_M))

    # locating points ----------------------------------------------------------------------------------------
    def ring_of(self, x, y):
        """The index of the finest ring whose window holds each point (clamped to the outermost window)."""
        x, y = self._clamp(x, y)
        out = np.zeros(x.shape, np.int64)
        for k in range(1, len(self.rings)):
            r = self.rings[k]
            inside = (x >= r.xm[0]) & (x <= r.xm[-1]) & (y >= r.ym[0]) & (y <= r.ym[-1])
            out[inside] = k
        return out

    def _clamp(self, x, y):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        x, y = np.broadcast_arrays(x, y)
        xmin, ymin, xmax, ymax = self.bounds()
        return np.clip(x, xmin, xmax).ravel(), np.clip(y, ymin, ymax).ravel()

    def _locate(self, r, x, y):
        i = np.clip(np.searchsorted(r.xm, x, 'right') - 1, 0, len(r.xm) - 2)
        j = np.clip(np.searchsorted(r.ym, y, 'right') - 1, 0, len(r.ym) - 2)
        fx = (x - r.xm[i]) / (r.xm[i + 1] - r.xm[i])
        fy = (y - r.ym[j]) / (r.ym[j + 1] - r.ym[j])
        return i, j, fx, fy

    def height_at(self, x, y):
        """Metres at Blender (x, y) on this mesh's triangles: the finest ring that holds the point, its quad, the
        (i, j) - (i+1, j+1) diagonal, and in a seam fan the fan's own triangle. Points outside the outermost window
        read its edge. Floats or arrays."""
        shape = np.broadcast(np.asarray(x), np.asarray(y)).shape
        xf, yf = self._clamp(x, y)
        which = self.ring_of(xf, yf)
        out = np.empty(xf.shape, np.float64)
        for k, r in enumerate(self.rings):
            sel = which == k
            if not sel.any():
                continue
            px, py = xf[sel], yf[sel]
            i, j, fx, fy = self._locate(r, px, py)
            Z = r.Z
            ha, hb, hc, hd = Z[j, i], Z[j, i + 1], Z[j + 1, i + 1], Z[j + 1, i]
            lower = fx >= fy
            z = np.where(lower, ha + fx * (hb - ha) + fy * (hc - hb), ha + fy * (hd - ha) + fx * (hc - hd))
            if r.hole is not None:
                self._fans(r, self.rings[k + 1], px, py, i, j, lower, z)
            out[sel] = z
        return float(out[0]) if shape == () else out.reshape(shape)

    @staticmethod
    def _fans(r, C, x, y, i, j, lower, z):
        """The seam fan rule, in place on z: a point in a triangle that was fanned through the child's border
        vertices lies on the ray from the fan's apex through it to the hole edge; the edge there is the child's
        border (piecewise linear through its vertices as written), so z runs linearly from the apex to that point.
        This is the fan's sub-triangle exactly (the diagonal rule differs from it by the float32 rounding of the
        in-between vertices)."""
        jb, jt, il, ir = r.hole_lines
        xm, ym, Z = r.xm, r.ym, r.Z
        inx = (i >= il) & (i < ir)
        iny = (j >= jb) & (j < jt)
        cases = (
            # below the hole: (a, c, d) fanned from a = (i, jb-1) to the edge y = ym[jb]: the child's bottom row
            ((j == jb - 1) & inx & ~lower, 'y', lambda m: (xm[i[m]], ym[jb - 1], Z[jb - 1, i[m]]), ym[jb],
             C.xm, C.Z[0, :]),
            # above the hole: (a, b, c) fanned from c = (i+1, jt+1) to the edge y = ym[jt]: the child's top row
            ((j == jt) & inx & lower, 'y', lambda m: (xm[i[m] + 1], ym[jt + 1], Z[jt + 1, i[m] + 1]), ym[jt],
             C.xm, C.Z[-1, :]),
            # left of the hole: (a, b, c) fanned from a = (il-1, j) to the edge x = xm[il]: the child's left column
            ((i == il - 1) & iny & lower, 'x', lambda m: (xm[il - 1], ym[j[m]], Z[j[m], il - 1]), xm[il],
             C.ym, C.Z[:, 0]),
            # right of the hole: (a, c, d) fanned from c = (ir+1, j+1) to the edge x = xm[ir]: the child's right column
            ((i == ir) & iny & ~lower, 'x', lambda m: (xm[ir + 1], ym[j[m] + 1], Z[j[m] + 1, ir + 1]), xm[ir],
             C.ym, C.Z[:, -1]),
        )
        for m, axis, apex, edge, line_pos, line_z in cases:
            if not m.any():
                continue
            qx, qy, qz = apex(m)
            if axis == 'y':                       # the edge is a row: the ray meets it at y = edge
                s = (y[m] - qy) / (edge - qy)
                hit = qx + (x[m] - qx) / np.maximum(s, 1e-300)
            else:                                 # a column: at x = edge
                s = (x[m] - qx) / (edge - qx)
                hit = qy + (y[m] - qy) / np.maximum(s, 1e-300)
            ze = np.interp(hit, line_pos, line_z)
            z[m] = qz + s * (ze - qz)

    def vertex_normals(self):
        """Per-vertex shading normals, as Blender computes them for smooth shading: the corner-angle-weighted sum of
        the unit face normals of every triangle at the vertex (skirt excluded), normalised."""
        if self._vn is None:
            V = len(self.verts)
            acc = np.zeros((V, 3), np.float64)
            T = self.tris[:self.terrain_triangles]
            for s in range(0, len(T), 1 << 20):
                t = T[s:s + (1 << 20)]
                p = [self.verts[t[:, q]].astype(np.float64) for q in range(3)]
                fn = np.cross(p[1] - p[0], p[2] - p[0])
                fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-300)
                for q in range(3):
                    e1 = p[(q + 1) % 3] - p[q]
                    e2 = p[(q + 2) % 3] - p[q]
                    cosang = np.einsum('ij,ij->i', e1, e2) / np.maximum(
                        np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1), 1e-300)
                    ang = np.arccos(np.clip(cosang, -1.0, 1.0))
                    for ax in range(3):
                        acc[:, ax] += np.bincount(t[:, q], weights=fn[:, ax] * ang, minlength=V)
            acc /= np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-300)
            self._vn = acc
        return self._vn

    def normal_at(self, x, y, smooth=True):
        """The surface normal at Blender (x, y): smooth=True the shading normal (the triangle's vertex normals blended
        by barycentric weight; a seam fan reads the corners of the triangle it subdivides), smooth=False the
        triangle's own face normal. (..., 3) unit vectors."""
        shape = np.broadcast(np.asarray(x), np.asarray(y)).shape
        xf, yf = self._clamp(x, y)
        which = self.ring_of(xf, yf)
        out = np.empty((len(xf), 3), np.float64)
        vn = self.vertex_normals() if smooth else None
        for k, r in enumerate(self.rings):
            sel = which == k
            if not sel.any():
                continue
            i, j, fx, fy = self._locate(r, xf[sel], yf[sel])
            lower = (fx >= fy)[:, None]
            if smooth:
                na, nb, nc, nd = (vn[r.idx[j, i]], vn[r.idx[j, i + 1]], vn[r.idx[j + 1, i + 1]], vn[r.idx[j + 1, i]])
                fxc, fyc = fx[:, None], fy[:, None]
                n = np.where(lower, na * (1 - fxc) + nb * (fxc - fyc) + nc * fyc,
                             na * (1 - fyc) + nc * fxc + nd * (fyc - fxc))
            else:
                Z = r.Z
                ha, hb, hc, hd = Z[j, i], Z[j, i + 1], Z[j + 1, i + 1], Z[j + 1, i]
                dx = r.xm[i + 1] - r.xm[i]
                dy = r.ym[j + 1] - r.ym[j]
                gx = np.where(lower[:, 0], (hb - ha) / dx, (hc - hd) / dx)
                gy = np.where(lower[:, 0], (hc - hb) / dy, (hd - ha) / dy)
                n = np.stack([-gx, -gy, np.ones_like(gx)], 1)
            out[sel] = n / np.linalg.norm(n, axis=1, keepdims=True)
        return out[0] if shape == () else out.reshape(shape + (3,))

    # checks ---------------------------------------------------------------------------------------------------
    def open_edges(self):
        """Edges of the terrain triangles (skirt excluded) used by one triangle only, as (E, 2) vertex pairs. On a
        stitched mesh these are exactly the outermost window's border."""
        T = self.tris[:self.terrain_triangles]
        e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
        e.sort(axis=1)
        key = e[:, 0] * len(self.verts) + e[:, 1]
        uk, cnt = np.unique(key, return_counts=True)
        one = uk[cnt == 1]
        return np.stack([one // len(self.verts), one % len(self.verts)], 1)

    def t_junctions(self):
        """How many (edge, vertex) pairs have a vertex lying strictly inside a terrain triangle's edge it is not an end
        of: the T-junctions a rasteriser can open into cracks. Every vertex is on the lattice and only axis-aligned
        edges can pass through another lattice point, so each such edge is checked against the vertices on its line
        (exact: shared lattice positions are the same float32 numbers)."""
        V = self.verts[:len(self.verts) if self.skirt is None else self.skirt['first_vertex']]
        T = self.tris[:self.terrain_triangles]
        e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
        e = np.unique(np.sort(e, axis=1), axis=0)
        ux, rx = np.unique(V[:, 0], return_inverse=True)
        uy, ry = np.unique(V[:, 1], return_inverse=True)
        bad = 0
        for fixed, free, nfree in ((rx, ry, len(uy)), (ry, rx, len(ux))):
            keys = np.sort(fixed.astype(np.int64) * (nfree + 1) + free)
            ee = e[fixed[e[:, 0]] == fixed[e[:, 1]]]
            base = fixed[ee[:, 0]].astype(np.int64) * (nfree + 1)
            lo = np.minimum(free[ee[:, 0]], free[ee[:, 1]])
            hi = np.maximum(free[ee[:, 0]], free[ee[:, 1]])
            between = np.searchsorted(keys, base + hi, 'left') - np.searchsorted(keys, base + lo, 'right')
            bad += int(between.sum())
        return bad


def build_rings(levels, heights, attributes=None, cores=False, mesh_res=MESH_RES, skirt=True,
                skirt_drop_m=SKIRT_DROP_M):
    """The ring mesh of nested levels (coarsest first).

    levels      windows (see as_window), each inside the one before, on its cell grid, cell halved
    heights     per level, its (n, n) cell-centred height array (metres, row 0 south)
    attributes  {name: [per-level (n, n) array or None]}: point attributes, bilinear at the vertices (0 where None)
    cores       draw the finest level again at half the side and stride, down to stride 1 (when there is a focus)
    mesh_res    vertices per side a level is drawn at (stride = round(n / mesh_res))
    skirt       hang the outermost ring's skirt, skirt_drop_m below its lowest border vertex
    """
    windows = [as_window(l) for l in levels]
    origin, unit, iwins = _integer_windows(windows)
    specs = plan_rings(iwins, mesh_res=mesh_res, cores=cores)
    return _assemble(origin, unit, windows, iwins, specs, heights, attributes or {}, skirt, skirt_drop_m)


def _assemble(origin, unit, windows, iwins, specs, heights, attributes, skirt, skirt_drop_m):
    rings, nv, tris, perim = _topology(specs, skirt)
    names = list(attributes)
    verts = np.zeros((nv, 3), np.float32)
    vals = {n: np.zeros(nv, np.float32) for n in names}
    level_attr = np.zeros(nv, np.float32)
    hole_lines = None
    for k, r in enumerate(rings):
        s = r.spec
        w = iwins[s.level]
        h = heights[s.level]
        if h is None or np.shape(h) != (w.n, w.n):
            raise ValueError(f'level {s.level}: heights must be ({w.n}, {w.n}), got {np.shape(h)}')
        Z = _sample(h, w, r.xs, r.ys, 'cr')
        if k:
            _seam_override(Z, r, rings[k - 1], rings[k - 1].Z)
        r.Z = Z.astype(np.float32).astype(np.float64)
        r.xm = np.float32(origin[0] + r.xs * unit).astype(np.float64)
        r.ym = np.float32(origin[1] + r.ys * unit).astype(np.float64)
        own = r.own
        sl = slice(r.v0, r.v0 + int(own.sum()))      # a ring's own vertices are numbered in row-major order
        jj, ii = np.nonzero(own)
        verts[sl, 0] = r.xm[ii]
        verts[sl, 1] = r.ym[jj]
        verts[sl, 2] = r.Z[jj, ii]
        level_attr[sl] = s.level
        if not names:
            continue
        # masks: bilinear at the ring's lattice; its border then takes the parent's straight edge, interpolated
        # along the parent's hole line (only the in-between vertices are this ring's own: the rest are the parent's)
        mx = (r.xs - w.x0) // w.ci
        my = (r.ys - w.y0) // w.ci
        P = rings[k - 1] if k else None
        new_lines = {}
        for n in names:
            arrs = attributes[n]
            a = arrs[s.level] if s.level < len(arrs) else None
            lat = (_lattice_bilinear(a, my, mx) if a is not None
                   else np.zeros((len(r.ys), len(r.xs)), np.float32))
            if P is not None:
                hl = hole_lines[n]
                lat[0, :] = np.interp(r.xs, P.xs, hl['b'])
                lat[-1, :] = np.interp(r.xs, P.xs, hl['t'])
                lat[:, 0] = np.interp(r.ys, P.ys, hl['l'])
                lat[:, -1] = np.interp(r.ys, P.ys, hl['r'])
            vals[n][sl] = lat[own]
            if r.hole is not None:                  # this ring's values along its hole's lines, for its child
                jb, jt, il, ir = r.hole_lines
                new_lines[n] = dict(b=lat[jb, :].copy(), t=lat[jt, :].copy(), l=lat[:, il].copy(),
                                    r=lat[:, ir].copy())
        hole_lines = new_lines
    n_terrain = len(tris)
    skirt_info = None
    if perim is not None:
        top = verts[perim]
        zb = float(top[:, 2].min()) - float(skirt_drop_m)
        bot = top.copy()
        bot[:, 2] = zb
        m = len(perim)
        t0 = nv + np.arange(m)
        b0 = nv + m + np.arange(m)
        t1 = np.roll(t0, -1)
        b1 = np.roll(b0, -1)
        st = np.concatenate([np.stack([t0, b0, b1], 1), np.stack([t0, b1, t1], 1)])
        verts = np.concatenate([verts, top, bot])
        for n in names:
            vals[n] = np.concatenate([vals[n], vals[n][perim], vals[n][perim]])
        level_attr = np.concatenate([level_attr, level_attr[perim], level_attr[perim]])
        tris = np.concatenate([tris, st])
        skirt_info = dict(drop_m=float(skirt_drop_m), bottom_z=zb, first_vertex=int(nv))
    vals['level'] = level_attr
    return RingMesh(origin, unit, windows, specs, rings, verts, tris.astype(np.int32), n_terrain, vals, skirt_info)


def rebuild(layout, verts):
    """A RingMesh (geometry only: height_at, normal_at) from a layout() and the vertex positions read back from the
    mesh, e.g. after a .blend is reopened. The vertex order is a pure function of the layout."""
    windows = [Window(float(a), float(b), float(c), int(d)) for a, b, c, d in layout['windows']]
    origin, unit, iwins = _integer_windows(windows)
    specs = [RingSpec(*map(int, s)) for s in layout['rings']]
    rings, nv, tris, perim = _topology(specs, layout.get('skirt', True))
    verts = np.asarray(verts, np.float32).reshape(-1, 3)
    if len(verts) < nv:
        raise ValueError(f'the mesh has {len(verts)} vertices; its layout needs {nv}')
    for r in rings:
        r.xm = np.float32(origin[0] + r.xs * unit).astype(np.float64)
        r.ym = np.float32(origin[1] + r.ys * unit).astype(np.float64)
        Z = np.zeros(r.idx.shape)
        used = r.idx >= 0
        Z[used] = verts[r.idx[used], 2]
        r.Z = Z
    skirt = (dict(drop_m=layout.get('skirt_drop_m', SKIRT_DROP_M), first_vertex=int(nv))
             if perim is not None else None)
    return RingMesh(origin, unit, windows, specs, rings, verts[:nv], tris.astype(np.int32), len(tris), {}, skirt)


# ------------------------------------------------------------------------------------------------- blender ---

def make_object(rm, name='terrain', collection=None, uv=True, smooth=True):
    """The Blender object of a RingMesh: triangles written explicitly, a 'UVMap' in world metres (u = x, v = y, the
    planar projection's frame for tangent-space normal maps), every attribute as a FLOAT point attribute
    'eido_<name>', smooth shading on the terrain and flat on the skirt. Linked into `collection` (default the
    scene's). Returns the object."""
    import bpy
    V = len(rm.verts)
    T = len(rm.tris)
    me = bpy.data.meshes.new(name)
    me.vertices.add(V)
    me.vertices.foreach_set('co', rm.verts.ravel())
    me.loops.add(3 * T)
    me.loops.foreach_set('vertex_index', rm.tris.ravel())
    me.polygons.add(T)
    me.polygons.foreach_set('loop_start', np.arange(0, 3 * T, 3, dtype=np.int32))
    me.update(calc_edges=True)
    if uv:
        layer = me.uv_layers.new(name='UVMap')
        layer.uv.foreach_set('vector', rm.verts[rm.tris.ravel(), :2].ravel())
    for n, arr in rm.attrs.items():
        att = me.attributes.new('eido_' + n, 'FLOAT', 'POINT')
        att.data.foreach_set('value', np.asarray(arr, np.float32))
    if smooth:
        sharp = np.zeros(T, bool)
        sharp[rm.terrain_triangles:] = True
        att = me.attributes.get('sharp_face') or me.attributes.new('sharp_face', 'BOOLEAN', 'FACE')
        att.data.foreach_set('value', sharp)
    obj = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def read_vertices(obj):
    """(V, 3) float32 vertex positions of a mesh object (object space)."""
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)
