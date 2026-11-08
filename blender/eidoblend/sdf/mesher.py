"""Dual contouring of a signed distance field, sparse, in numpy: the SDF's surface as a quad mesh at film resolution.

The engine raymarched each SDF per pixel. In EEVEE an SDF solid has to be geometry to take real light, shadows,
depth and reflections, so the field is sampled on a grid and contoured. This is the method of our own SDF truck
mesher (Desktop/sdf-dualcontour-mesh/truck_mesh.html), vectorised and made sparse:

  1. the grid is cut into bricks of B^3 cells; a coarse pass evaluates the field at each brick's centre and keeps
     the bricks the surface can reach (|d| <= lipschitz * half-diagonal + half a voxel);
  2. each kept brick evaluates its (B+1)^3 corners and OWNS the edges that start at its B^3 lower corners, so every
     grid edge is tested exactly once and no global de-duplication of corners is needed;
  3. an edge whose corners change sign is a crossing: its point by linear interpolation, its normal from the
     field's gradient there (Hermite data);
  4. each cell touching a crossing gets one vertex: the minimiser of the QEF sum (n.(x - p))^2, regularised toward
     the crossings' mass point and clamped to the cell, so sharp creases and corners land where they are;
  5. each crossing edge emits the quad of its four cells, wound so the face normal points out of the solid.

The field functions are callables, so the same code meshes GLSL (GPU) and Python (numpy) SDFs.
"""

from __future__ import annotations

import math
import time

import numpy as np

# per edge axis: the four cells (offsets) around an edge, in winding order A, B, C, D. ABCD faces +x for x edges,
# -y for y edges and +z for z edges (AB x BC); a quad is flipped where that is not outward.
_EDGE_CELLS = {
    0: [(0, -1, -1), (0, 0, -1), (0, 0, 0), (0, -1, 0)],
    1: [(-1, 0, -1), (0, 0, -1), (0, 0, 0), (-1, 0, 0)],
    2: [(-1, -1, 0), (0, -1, 0), (0, 0, 0), (-1, 0, 0)],
}


class Contour:
    """The result: verts (V, 3) and quads (F, 4) in the SDF's local frame, plus what produced them."""

    def __init__(self, verts, quads, voxel, dims, origin, stats):
        self.verts = verts
        self.quads = quads
        self.voxel = voxel
        self.dims = dims
        self.origin = origin
        self.stats = stats


def _empty(voxel, dims, bmin, stats, t_start):
    stats['seconds'] = round(time.perf_counter() - t_start, 3)
    stats.setdefault('quads', 0)
    return Contour(np.zeros((0, 3), np.float32), np.zeros((0, 4), np.int32), voxel, dims, bmin, stats)


def active_bricks(dist_fn, bmin, nb, B, voxel, lipschitz):
    """(M, 3) brick indices whose centre distance says the surface may pass through them."""
    bi, bj, bk = np.meshgrid(np.arange(nb[0]), np.arange(nb[1]), np.arange(nb[2]), indexing='ij')
    idx = np.stack([bi, bj, bk], -1).reshape(-1, 3)
    centres = bmin + (idx + 0.5) * (B * voxel)
    dc = dist_fn(centres.astype(np.float32))
    reach = lipschitz * (math.sqrt(3.0) * 0.5 * B * voxel) + 0.5 * voxel
    return idx[np.abs(dc) <= reach]


def refine_crossings(dist_fn, start, ax, d0, d1, voxel, iso=0.0, iterations=3):
    """Where along each grid edge the field really crosses iso: regula falsi (Illinois) from the corner values.

    Linear interpolation of the corner values is exact only where the field is linear along the edge. Near a crease
    (a box edge, a boolean cut, a panel gap) the SDF bends inside the edge and the interpolated crossing lands up to
    a third of a voxel off, which rounds every sharp feature. Each iteration is one batch evaluation."""
    t = d0 / (d0 - d1)
    if iterations <= 0 or len(t) == 0:
        return t
    a, fa = np.zeros_like(t), d0.copy()
    b, fb = np.ones_like(t), d1.copy()
    last = np.zeros(len(t), np.int8)
    step = np.zeros((len(t), 3))
    step[np.arange(len(t)), ax] = voxel
    for _ in range(int(iterations)):
        ft = np.asarray(dist_fn((start + step * t[:, None]).astype(np.float32)), np.float64) - iso
        keep_b = (ft < 0) == (fa < 0)                       # the root lies in [t, b]: t replaces a
        a = np.where(keep_b, t, a)
        fa = np.where(keep_b, ft, fa)
        b = np.where(keep_b, b, t)
        fb = np.where(keep_b, fb, ft)
        # Illinois: an end kept twice in a row has its value halved, so the bracket shrinks from both sides
        fb = np.where(keep_b & (last == 1), fb * 0.5, fb)
        fa = np.where(~keep_b & (last == -1), fa * 0.5, fa)
        last = np.where(keep_b, 1, -1).astype(np.int8)
        den = fb - fa
        t_new = np.where(np.abs(den) > 1e-30, (a * fb - b * fa) / np.where(np.abs(den) > 1e-30, den, 1.0), 0.5 * (a + b))
        t = np.where(ft == 0.0, t, np.clip(t_new, a, b))
    return t


def dual_contour(dist_fn, grad_fn, bmin, bmax, voxel, brick=8, lipschitz=1.5, qef_lambda=0.01, grad_h=None,
                 chunk_points=1 << 22, iso=0.0, refine=3, log=None):
    """Contour the level set dist_fn = iso inside [bmin, bmax] (local coordinates) at the given voxel size.

    dist_fn(points (N, 3) float32) -> (N,) distances; grad_fn(points, h) -> (N, 3) gradients. `refine` regula falsi
    iterations place each edge crossing on the real field (sharp creases); 0 keeps linear interpolation."""
    t_start = time.perf_counter()
    bmin = np.asarray(bmin, np.float64)
    bmax = np.asarray(bmax, np.float64)
    voxel = float(voxel)
    iso = float(iso)
    B = int(brick)
    nb = np.maximum(1, np.ceil((bmax - bmin) / (voxel * B) - 1e-9).astype(np.int64))
    dims = nb * B                                       # whole bricks (the clip box keeps the field positive)
    nx, ny, nz = (int(d) for d in dims)
    SX, SY = nx + 1, ny + 1                             # key strides
    stats = {'dims': (nx, ny, nz), 'voxel': voxel, 'brick': B}

    if iso != 0.0:
        field = lambda p: np.asarray(dist_fn(p), np.float64) - iso      # noqa: E731
    else:
        field = dist_fn
    act = active_bricks(field, bmin, nb, B, voxel, lipschitz)
    stats['bricks'] = int(len(act))
    stats['bricks_total'] = int(np.prod(nb))
    if len(act) == 0:
        return _empty(voxel, dims, bmin, stats, t_start)

    o = np.arange(B + 1)
    oi, oj, ok = np.meshgrid(o, o, o, indexing='ij')
    offs = np.stack([oi, oj, ok], -1).reshape(-1, 3)        # (B+1)^3 local corners, [i][j][k] order
    per = len(offs)
    step = max(1, chunk_points // per)
    e_key, e_ax, e_d0, e_d1 = [], [], [], []
    n_eval = 0
    for s in range(0, len(act), step):
        bs = act[s:s + step]                                 # (m, 3)
        base = bs * B                                        # global corner index of each brick's origin
        cpos = bmin + (base[:, None, :] + offs[None]) * voxel
        D = np.asarray(field(cpos.reshape(-1, 3).astype(np.float32)), np.float64).reshape(len(bs), B + 1, B + 1, B + 1)
        n_eval += D.size
        neg = D < 0
        lo = (slice(None), slice(0, B), slice(0, B), slice(0, B))
        for ax in range(3):
            hi = [slice(None), slice(0, B), slice(0, B), slice(0, B)]
            hi[ax + 1] = slice(1, B + 1)
            cross = neg[lo] != neg[tuple(hi)]
            b_, i_, j_, k_ = np.nonzero(cross)
            if len(b_) == 0:
                continue
            gi = base[b_, 0] + i_
            gj = base[b_, 1] + j_
            gk = base[b_, 2] + k_
            e_key.append(np.stack([gi, gj, gk], -1))
            e_ax.append(np.full(len(gi), ax, np.int8))
            e_d0.append(D[lo][b_, i_, j_, k_])
            e_d1.append(D[tuple(hi)][b_, i_, j_, k_])
    stats['corners'] = int(n_eval)
    if not e_key:
        return _empty(voxel, dims, bmin, stats, t_start)
    e_ijk = np.concatenate(e_key)
    e_ax = np.concatenate(e_ax)
    e_d0 = np.concatenate(e_d0)
    e_d1 = np.concatenate(e_d1)
    e_in = e_d0 < 0
    e_start = bmin + e_ijk * voxel
    t = refine_crossings(dist_fn, e_start, e_ax.astype(np.int64), e_d0, e_d1, voxel, iso, refine)
    e_p = e_start.copy()
    e_p[np.arange(len(t)), e_ax] += t * voxel
    t_sample = time.perf_counter()
    stats['edges'] = int(len(e_ijk))

    # Hermite normals: a narrow stencil, or crossings near a crease average both faces' normals and round it off
    gh = grad_h if grad_h is not None else max(2e-5, 0.04 * voxel)
    g = np.asarray(grad_fn(e_p.astype(np.float32), gh), np.float64)
    gl = np.linalg.norm(g, axis=1)
    e_n = g / np.maximum(gl, 1e-20)[:, None]
    bad = ~np.isfinite(e_n).all(axis=1) | (gl < 1e-12)
    e_n[bad] = 0.0
    t_grad = time.perf_counter()

    # cells around each crossing edge: their keys, column by column (no (E, 4, 3) array: a fine fractal or a large
    # car has tens of millions of crossings)
    E = len(e_ijk)
    offs = np.array([[_EDGE_CELLS[ax][c] for c in range(4)] for ax in range(3)], np.int64)   # (axis, corner, 3)
    keys = np.empty((E, 4), np.int64)
    cell_ok = np.empty((E, 4), bool)
    for c in range(4):
        cij = e_ijk + offs[e_ax, c]
        cell_ok[:, c] = ((cij >= 0) & (cij < dims)).all(axis=1)
        keys[:, c] = cij[:, 0] + SX * (cij[:, 1] + SY * cij[:, 2])
        del cij
    cells, inv = np.unique(keys[cell_ok], return_inverse=True)
    nC = len(cells)
    vid = np.full((E, 4), -1, np.int64)
    vid[cell_ok] = inv
    del inv

    # the QEF sums per cell, accumulated one corner column at a time straight from the edge arrays
    def acc(weights_fn):
        out = np.zeros(nC)
        for c in range(4):
            sel = cell_ok[:, c]
            out += np.bincount(vid[sel, c], weights=weights_fn(sel), minlength=nC)
        return out
    cnt = acc(lambda s: None)
    mass = np.stack([acc(lambda s, a=a: e_p[s, a]) for a in range(3)], -1) / cnt[:, None]
    nd = np.sum(e_n * e_p, axis=1)
    axx, ayy, azz = (acc(lambda s, a=a: e_n[s, a] ** 2) for a in range(3))
    axy = acc(lambda s: e_n[s, 0] * e_n[s, 1])
    axz = acc(lambda s: e_n[s, 0] * e_n[s, 2])
    ayz = acc(lambda s: e_n[s, 1] * e_n[s, 2])
    bx, by, bz = (acc(lambda s, a=a: e_n[s, a] * nd[s]) for a in range(3))
    del nd
    # rhs = A^T b - A^T A mass; (A^T A + lambda I) x = rhs by Cramer's rule (symmetric positive definite: lambda > 0)
    mx, my, mz = mass[:, 0], mass[:, 1], mass[:, 2]
    rx = bx - (axx * mx + axy * my + axz * mz)
    ry = by - (axy * mx + ayy * my + ayz * mz)
    rz = bz - (axz * mx + ayz * my + azz * mz)
    lam = qef_lambda * np.maximum(cnt, 1.0)
    a, d, f = axx + lam, ayy + lam, azz + lam          # [[a, b, c], [b, d, e], [c, e, f]]
    b_, c_, e_ = axy, axz, ayz
    co0 = d * f - e_ * e_
    co1 = c_ * e_ - b_ * f
    co2 = b_ * e_ - c_ * d
    det = a * co0 + b_ * co1 + c_ * co2
    det = np.where(np.abs(det) > 1e-30, det, 1e-30)
    xs = np.stack([(co0 * rx + co1 * ry + co2 * rz),
                   (co1 * rx + (a * f - c_ * c_) * ry + (b_ * c_ - a * e_) * rz),
                   (co2 * rx + (b_ * c_ - a * e_) * ry + (a * d - b_ * b_) * rz)], -1) / det[:, None]
    del axx, ayy, azz, axy, axz, ayz, bx, by, bz, rx, ry, rz, co0, co1, co2, det, a, d, f
    verts = mass + xs
    del xs
    cxi = cells % SX
    cyi = (cells // SX) % SY
    czi = cells // (SX * SY)
    cmin = bmin + np.stack([cxi, cyi, czi], -1) * voxel
    verts = np.minimum(np.maximum(verts, cmin), cmin + voxel)
    bad = ~np.isfinite(verts).all(axis=1)
    verts[bad] = mass[bad]
    t_qef = time.perf_counter()

    full = cell_ok.all(axis=1)
    q = vid[full]
    inside0 = e_in[full]
    ax_f = e_ax[full]
    rev = np.where(ax_f == 1, inside0, ~inside0)
    q[rev] = q[rev][:, ::-1]
    quads = q.astype(np.int32)
    stats.update(cells=int(nC), quads=int(len(quads)), open_edges=int((~full).sum()),
                 t_sample=round(t_sample - t_start, 3), t_grad=round(t_grad - t_sample, 3),
                 t_qef=round(t_qef - t_grad, 3), seconds=round(time.perf_counter() - t_start, 3))
    if log:
        log(f'[sdf.mesher] {nx}x{ny}x{nz} @ {voxel * 1000:.2f} mm: {stats["bricks"]}/{stats["bricks_total"]} bricks, '
            f'{stats["corners"]} corner samples, {stats["quads"]} quads in {stats["seconds"]} s')
    return Contour(verts.astype(np.float32), quads, voxel, dims, bmin, stats)


def components(quads, n_verts):
    """Connected-component label of every vertex (quads joined through shared vertices), union-find in numpy."""
    parent = np.arange(n_verts, dtype=np.int64)

    def find(x):
        while True:
            px = parent[x]
            if np.array_equal(px, x):
                return x
            parent[x] = parent[px]
            x = parent[x]
    edges = np.concatenate([quads[:, [0, 1]], quads[:, [1, 2]], quads[:, [2, 3]]]).astype(np.int64)
    while True:
        ra, rb = find(edges[:, 0]), find(edges[:, 1])
        lo, hi = np.minimum(ra, rb), np.maximum(ra, rb)
        moving = lo != hi
        if not moving.any():
            break
        np.minimum.at(parent, hi[moving], lo[moving])
    return find(np.arange(n_verts, dtype=np.int64))


def drop_small_components(c, min_quads):
    """The contour without its pieces of fewer than min_quads quads (fractal dust, interior bubbles of a distance
    estimator); the stats record how many quads went."""
    if len(c.quads) == 0:
        return c
    lab = components(c.quads, len(c.verts))
    ql = lab[c.quads[:, 0]]
    _u, inv, cnt = np.unique(ql, return_inverse=True, return_counts=True)
    keep = cnt[inv] >= int(min_quads)
    used = np.zeros(len(c.verts), bool)
    used[c.quads[keep].ravel()] = True
    remap = np.cumsum(used) - 1
    stats = dict(c.stats, quads_dropped=int((~keep).sum()), components=int(len(_u)),
                 components_kept=int((cnt >= int(min_quads)).sum()))
    stats['quads'] = int(keep.sum())
    return Contour(c.verts[used], remap[c.quads[keep]].astype(np.int32), c.voxel, c.dims, c.origin, stats)


def quad_corner_points(verts, quads, inset=0.3):
    """Points just inside each quad from each corner (for crease-keeping corner normals): (F, 4, 3)."""
    v = verts[quads]
    c = v.mean(axis=1, keepdims=True)
    return v + inset * (c - v)
