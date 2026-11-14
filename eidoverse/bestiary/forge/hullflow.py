"""The grid-volume machinery shared by the creature volumes built from photographs (W2c's canid head, W2d's wolf body):
2D silhouette rasters, dense grids, the constrained curvature FLOW that rounds a hull between its outer and inner
limits, the redistances, the GRID member's divisor and the on-disk cache.

W2d moved these out of heads/canid_hull.py unchanged (the head volume is bit-identical after the move: work/bestiary/
wolf/scratch_w2d/head_bitcheck.py rebuilds the head's three cached volumes into a fresh cache and compares them array
for array with the W2c check's), and added flow_wp: the same scheme as flow(), written as a Warp kernel (the body's
grids are 10-25 M voxels: numpy took ~4.5 s a step at 18 M, the kernel ~1 s on the CPU device and a few ms on a GPU),
with an optional mirror plane at the first index of axis 0 (a symmetric half built once, its other half mirrored).

THE FLOW (canid_hull's docstring has its derivation): phi_t = (kappa - F) |grad phi|, kappa the mean curvature (the
sum of the principal curvatures, central differences), F an inflation pressure (upwind Godunov norm for outward
motion), each step clamped between the lower (outer limits) and upper (inner limits) bounds; redistanced every
`reinit` steps.
"""
import hashlib
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CACHE = os.environ.get('BESTIARY_CACHE') or os.path.join(REPO, 'work', 'bestiary', 'cache')


# ============================================================================================ 2D silhouettes
def poly_sdf_image(poly, lo, hi, res):
    """the 2D signed distance (mm, negative inside) of the closed polygon `poly` (k, 2) on the raster [lo, hi] (u, v)
    at res mm per pixel: returns (image (nu, nv), lo, res); inside by the even-odd rule at the pixel centres"""
    from matplotlib.path import Path
    from scipy import ndimage as nd
    lo = np.asarray(lo, float)
    hi = np.asarray(hi, float)
    nu, nv = (np.ceil((hi - lo) / res).astype(int) + 1)
    U, V = np.meshgrid(lo[0] + np.arange(nu) * res, lo[1] + np.arange(nv) * res, indexing='ij')
    inside = Path(np.asarray(poly, float)).contains_points(np.column_stack([U.ravel(), V.ravel()])).reshape(nu, nv)
    dout = nd.distance_transform_edt(~inside)
    din = nd.distance_transform_edt(inside)
    return ((dout - din) + np.where(inside, 0.5, -0.5)) * res, lo, res


def sample2(img, lo, res, u, v):
    """bilinear sample of a poly_sdf_image at (u, v) mm (clamped to the raster; outside it the far value grows by the
    distance to the raster)"""
    from scipy import ndimage as nd
    fu = (np.asarray(u, float) - lo[0]) / res
    fv = (np.asarray(v, float) - lo[1]) / res
    cu = np.clip(fu, 0, img.shape[0] - 1)
    cv = np.clip(fv, 0, img.shape[1] - 1)
    s = nd.map_coordinates(img, [cu.ravel(), cv.ravel()], order=1, mode='nearest').reshape(np.shape(u))
    return s + np.hypot(fu - cu, fv - cv) * res


def offset_polyline(P, dist, interior):
    """the polyline P (k, 2) moved along its normal toward `interior` (a point) by dist (k,) mm (negative: outward)"""
    P = np.asarray(P, float)
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    N = np.stack([-T[:, 1], T[:, 0]], -1)
    sgn = np.sign(np.sum((np.asarray(interior, float) - P) * N, axis=1))
    sgn[sgn == 0] = 1.0
    return P + N * (sgn * np.asarray(dist, float))[:, None]


def resample_closed(P, step):
    P = np.vstack([P, P[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    n = max(8, int(s[-1] / step))
    t = np.linspace(0, s[-1], n, endpoint=False)
    return np.column_stack([np.interp(t, s, P[:, k]) for k in range(2)])


def inward_normals_closed(P):
    """unit normals of the closed polygon P pointing inside (by its orientation)"""
    T = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    area2 = float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))
    N = np.stack([-T[:, 1], T[:, 0]], -1)
    return N if area2 > 0 else -N


# ============================================================================================ the grid
class Grid:
    """a dense grid over the head in the palate frame (mm): index (i, j, k) at (d0 + i h, q0 + j h, x0 + k h)"""

    def __init__(self, lo, hi, h):
        self.lo = np.asarray(lo, float)
        self.h = float(h)
        self.n = tuple(int(np.ceil((hi[a] - lo[a]) / h)) + 1 for a in range(3))
        self.d = self.lo[0] + np.arange(self.n[0]) * h
        self.q = self.lo[1] + np.arange(self.n[1]) * h
        self.x = self.lo[2] + np.arange(self.n[2]) * h

    def mesh(self):
        return np.meshgrid(self.d, self.q, self.x, indexing='ij')


def ball_bounds(G, inner, outer):
    """upper bound from the inner balls (the shape must contain each: phi <= |x - c| - r) and lower bound from the
    outer balls (the shape must exclude each: phi >= r - |x - c|), restricted to each ball's neighbourhood"""
    up = np.full(G.n, np.inf, np.float32)
    lo = np.full(G.n, -np.inf, np.float32)
    for arr, balls, sign in ((up, inner, 1.0), (lo, outer, -1.0)):
        for c, r in balls:
            c = np.asarray(c, float)
            reach = r + 4.0 * G.h
            sl = []
            for a, ax in enumerate((G.d, G.q, G.x)):
                i0 = max(0, int(np.floor((c[a] - reach - G.lo[a]) / G.h)))
                i1 = min(G.n[a], int(np.ceil((c[a] + reach - G.lo[a]) / G.h)) + 1)
                sl.append(slice(i0, i1))
            if any(s.start >= s.stop for s in sl):
                continue
            D, Q, X = np.meshgrid(G.d[sl[0]], G.q[sl[1]], G.x[sl[2]], indexing='ij')
            dist = np.sqrt((D - c[0]) ** 2 + (Q - c[1]) ** 2 + (X - c[2]) ** 2)
            if sign > 0:
                arr[tuple(sl)] = np.minimum(arr[tuple(sl)], dist - r)
            else:
                arr[tuple(sl)] = np.maximum(arr[tuple(sl)], r - dist)
    return up, lo


def redistance(phi, h):
    """signed distance (mm) to phi's zero set: each voxel's nearest interface voxel (scipy's EDT on the interface
    mask), its foot point s - phi(s) grad / |grad|^2, the distance to that foot point, the sign kept"""
    from scipy import ndimage as nd
    s = phi < 0
    iface = np.zeros_like(s)
    for a in range(3):
        ch = s != np.roll(s, 1, axis=a)
        sl = [slice(None)] * 3
        sl[a] = slice(0, 1)
        ch[tuple(sl)] = False
        iface |= ch
        iface |= np.roll(ch, -1, axis=a)
    g = np.stack(np.gradient(phi, h), 0)
    gl2 = np.maximum(np.sum(g * g, 0), 1e-12)
    idx = nd.distance_transform_edt(~iface, return_distances=False, return_indices=True)
    I = tuple(idx[a] for a in range(3))
    foot = [idx[a] * h - (phi[I] * g[a][I] / gl2[I]) for a in range(3)]
    pos = np.indices(phi.shape) * h
    dist = np.sqrt(sum((pos[a] - foot[a]) ** 2 for a in range(3)))
    return np.where(s, -dist, dist).astype(np.float32)


def curvature_term(phi, h):
    """kappa |grad phi| (central differences): the mean-curvature flow's speed term"""
    p = np.pad(phi, 1, mode='edge')
    c = p[1:-1, 1:-1, 1:-1]
    dx = (p[2:, 1:-1, 1:-1] - p[:-2, 1:-1, 1:-1]) / (2 * h)
    dy = (p[1:-1, 2:, 1:-1] - p[1:-1, :-2, 1:-1]) / (2 * h)
    dz = (p[1:-1, 1:-1, 2:] - p[1:-1, 1:-1, :-2]) / (2 * h)
    dxx = (p[2:, 1:-1, 1:-1] - 2 * c + p[:-2, 1:-1, 1:-1]) / (h * h)
    dyy = (p[1:-1, 2:, 1:-1] - 2 * c + p[1:-1, :-2, 1:-1]) / (h * h)
    dzz = (p[1:-1, 1:-1, 2:] - 2 * c + p[1:-1, 1:-1, :-2]) / (h * h)
    dxy = (p[2:, 2:, 1:-1] - p[2:, :-2, 1:-1] - p[:-2, 2:, 1:-1] + p[:-2, :-2, 1:-1]) / (4 * h * h)
    dxz = (p[2:, 1:-1, 2:] - p[2:, 1:-1, :-2] - p[:-2, 1:-1, 2:] + p[:-2, 1:-1, :-2]) / (4 * h * h)
    dyz = (p[1:-1, 2:, 2:] - p[1:-1, 2:, :-2] - p[1:-1, :-2, 2:] + p[1:-1, :-2, :-2]) / (4 * h * h)
    g2 = dx * dx + dy * dy + dz * dz
    num = (dxx * (dy * dy + dz * dz) + dyy * (dx * dx + dz * dz) + dzz * (dx * dx + dy * dy)
           - 2 * dx * dy * dxy - 2 * dx * dz * dxz - 2 * dy * dz * dyz)
    return num / np.maximum(g2, 1e-8), np.sqrt(g2)


def flow(phi, lower, upper, pressure, h, steps, dt, reinit=20, log=None):
    """the constrained flow: phi_t = kappa |grad| - F |grad| (|grad| the upwind Godunov norm for the pressure), each
    step clamped to [lower, upper]; redistanced every `reinit` steps; returns phi and the per-chunk max change"""
    hist = []
    phi = np.minimum(np.maximum(phi, lower), upper).astype(np.float32)
    for it in range(steps):
        kg, gn = curvature_term(phi, h)
        p = np.pad(phi, 1, mode='edge')
        c = p[1:-1, 1:-1, 1:-1]
        gp = np.zeros_like(c)
        for a in range(3):
            sl_f = [slice(1, -1)] * 3
            sl_b = [slice(1, -1)] * 3
            sl_f[a] = slice(2, None)
            sl_b[a] = slice(0, -2)
            dm = (c - p[tuple(sl_b)]) / h
            dpp = (p[tuple(sl_f)] - c) / h
            # outward motion (F > 0, phi decreases): Godunov for speed > 0
            gp += np.maximum(np.maximum(dm, 0) ** 2, np.minimum(dpp, 0) ** 2)
        gp = np.sqrt(gp)
        new = phi + dt * (kg - pressure * gp)
        new = np.minimum(np.maximum(new, lower), upper)
        if (it + 1) % reinit == 0 or it == steps - 1:
            band = np.abs(new) < 6 * h
            hist.append(float(np.abs(new - phi)[band].max()) if band.any() else 0.0)
            new = np.minimum(np.maximum(redistance(new, h), lower), upper)
            if log:
                log(f'[hull]   flow step {it + 1}/{steps}: max |dphi| in the band {hist[-1]:.4f} mm')
        phi = new.astype(np.float32)
    return phi, hist


def sample3(phi, G, P):
    """phi trilinear at points P (..., 3) mm (d, q, x)"""
    from scipy import ndimage as nd
    P = np.asarray(P, float)
    f = ((P.reshape(-1, 3) - G.lo) / G.h).T
    return nd.map_coordinates(phi, f, order=1, mode='nearest').reshape(P.shape[:-1])


def surface_x(phi, G, d, q, x0=0.0, reach=95.0, step=0.25):
    """the skin's lateral position at (d, q): the first zero crossing marching +x from x0 (arrays d, q)"""
    d, q = np.broadcast_arrays(np.asarray(d, float), np.asarray(q, float))
    t = np.arange(x0, reach, step)
    P = np.stack([np.repeat(d[..., None], len(t), -1), np.repeat(q[..., None], len(t), -1),
                  np.broadcast_to(t, d.shape + (len(t),))], -1)
    f = sample3(phi, G, P)
    out = np.full(d.shape, np.nan)
    inside = f < 0
    for idx in np.ndindex(d.shape):
        ii = inside[idx]
        if not ii.any():
            continue
        j0 = int(np.argmax(ii))
        j1 = j0 + int(np.argmax(~ii[j0:])) if (~ii[j0:]).any() else len(t) - 1
        fa, fb = f[idx][j1 - 1], f[idx][j1]
        out[idx] = t[j1 - 1] + step * fa / (fa - fb) if fb != fa else t[j1]
    return out


def surface_along(phi, G, P0, dirn, reach=40.0, step=0.25):
    """from P0 (n, 3) along dirn (n, 3) unit: the first outside crossing (the skin) beyond P0"""
    P0, dirn = np.atleast_2d(P0).astype(float), np.atleast_2d(dirn).astype(float)
    t = np.arange(0.0, reach, step)
    P = P0[:, None, :] + t[None, :, None] * dirn[:, None, :]
    f = sample3(phi, G, P)
    out = P0.copy()
    for i in range(len(P0)):
        pos = f[i] > 0
        if not pos.any():
            continue
        j = int(np.argmax(pos))
        if j == 0:
            out[i] = P0[i]
            continue
        fa, fb = f[i, j - 1], f[i, j]
        out[i] = P0[i] + dirn[i] * (t[j - 1] + step * (-fa) / (fb - fa))
    return out


def curve_dist(pts, C, sl=1.0):
    """distance from pts (n, 3) to the polyline C (k, 3), and the arclength fraction of the nearest point"""
    from scipy.spatial import cKDTree
    C = np.asarray(C, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    n = max(2, int(s[-1] / (0.25 * sl)) + 1)
    t = np.linspace(0, s[-1], n)
    D = np.column_stack([np.interp(t, s, C[:, k]) for k in range(3)])
    dist, j = cKDTree(D).query(pts)
    return dist, t[j] / max(s[-1], 1e-9)


def ellipsoid_sd(P, c, axes, half):
    """iq's bound-corrected ellipsoid estimate (sdf.sd_ellipsoid), axes (3, 3) rows = the local axes"""
    q = (P - c) @ np.asarray(axes, float).T
    l = q / np.asarray(half, float)
    k0 = np.linalg.norm(l, axis=-1)
    k1 = np.linalg.norm(l / np.asarray(half, float), axis=-1)
    return np.where(k1 > 1e-12, k0 * (k0 - 1.0) / np.maximum(k1, 1e-12), -min(half))


# ============================================================================================ Warp: distances, flow
import warp as wp  # noqa: E402


@wp.kernel
def k_mesh_dist(mesh: wp.uint64, lo: wp.vec3, h: float, ny: int, nz: int, maxd: float,
                out: wp.array(dtype=wp.float32)):
    """the unsigned distance from each grid point to the triangle mesh (maxd where none is nearer)"""
    tid = wp.tid()
    i = tid // (ny * nz)
    j = (tid // nz) % ny
    k = tid % nz
    p = lo + wp.vec3(float(i) * h, float(j) * h, float(k) * h)
    q = wp.mesh_query_point_no_sign(mesh, p, maxd)
    if q.result:
        out[tid] = wp.length(p - wp.mesh_eval_position(mesh, q.face, q.u, q.v))
    else:
        out[tid] = maxd


def exact_distance(phi, G, maxd):
    """phi's zero set triangulated (marching cubes, its linear interpolation of the grid), every grid point's exact
    distance to it (Warp's BVH), phi's sign: the redistance the GRID member's bound needs (the foot-point estimate's
    errors left cells of slope 1.4-2.7)"""
    from skimage.measure import marching_cubes
    V, F, _, _ = marching_cubes(phi, 0.0, spacing=(G.h, G.h, G.h))
    V = (V + G.lo).astype(np.float32)
    m = wp.Mesh(points=wp.array(V, dtype=wp.vec3), indices=wp.array(F.astype(np.int32).ravel(), dtype=wp.int32))
    n = int(np.prod(G.n))
    out = wp.zeros(n, dtype=wp.float32)
    wp.launch(k_mesh_dist, dim=n, inputs=[m.id, wp.vec3(*G.lo.astype(np.float32)), float(G.h), int(G.n[1]),
                                          int(G.n[2]), float(maxd), out])
    dist = out.numpy().reshape(G.n)
    return np.where(phi < 0, -dist, dist).astype(np.float32)


def finish(phi, G, clamp, blur, sym=False):
    """the grid as the GRID member takes it: the exact distance to phi's zero set, the far field clamped to clamp (lo,
    hi) mm (the producer's part, sdf_grid.md), blurred by blur mm (a blurred distance keeps |grad| <= 1); sym: axis
    0's first sample is a mirror plane (a symmetric half), so the blur reflects there"""
    from scipy import ndimage as nd
    lo, hi = clamp
    f = exact_distance(phi, G, max(abs(lo), abs(hi)) + 2.0)
    f = np.clip(f, lo, hi)
    f = nd.gaussian_filter(f, blur / G.h, mode=['mirror', 'nearest', 'nearest'] if sym else 'nearest')
    return f.astype(np.float32)


def grid_bound(V, h):
    """sdf_grid.md's divisor for these values (per cell the root sum of squares of the steepest edge per axis)"""
    s = []
    for a in range(3):
        e = np.abs(np.diff(V, axis=a)) / h
        others = [b for b in range(3) if b != a]
        m = None
        for o0 in (slice(0, -1), slice(1, None)):
            for o1 in (slice(0, -1), slice(1, None)):
                sl = [slice(None)] * 3
                sl[others[0]], sl[others[1]] = o0, o1
                m = e[tuple(sl)] if m is None else np.maximum(m, e[tuple(sl)])
        s.append(m.astype(np.float64))
    return float(np.sqrt(s[0] ** 2 + s[1] ** 2 + s[2] ** 2).max())


@wp.func
def _nb(i: int, n: int, sym: int):
    """a neighbour index on one axis: clamped at both ends (np.pad 'edge'), or mirrored at index 0 (sym: the plane of
    symmetry through the first sample, phi[-1] = phi[1])"""
    if i < 0:
        if sym == 1:
            return wp.min(-i, n - 1)
        return 0
    if i > n - 1:
        return n - 1
    return i


@wp.kernel
def k_flow_step(phi: wp.array3d(dtype=wp.float32), lo: wp.array3d(dtype=wp.float32),
                up: wp.array3d(dtype=wp.float32), pr: wp.array3d(dtype=wp.float32), h: float, dt: float, sym: int,
                band: float, out: wp.array3d(dtype=wp.float32)):
    """one step of flow()'s scheme: kappa |grad| (central differences, edge-clamped) minus F times the upwind Godunov
    |grad| for outward motion, clamped to [lo, up]. band > 0: a NARROW BAND, only voxels within band of the zero set
    move and kappa is clipped to 2 / h (W2d b3: away from the skin the interior level sets near a medial surface, where
    kappa runs to infinity, crossed zero between redistances and opened voids inside the body)"""
    i, j, k = wp.tid()
    nx = phi.shape[0]
    ny = phi.shape[1]
    nz = phi.shape[2]
    if band > 0.0:
        if wp.abs(phi[i, j, k]) > band:
            out[i, j, k] = wp.min(wp.max(phi[i, j, k], lo[i, j, k]), up[i, j, k])
            return
    im = _nb(i - 1, nx, sym)
    ip = _nb(i + 1, nx, sym)
    jm = _nb(j - 1, ny, 0)
    jp = _nb(j + 1, ny, 0)
    km = _nb(k - 1, nz, 0)
    kp = _nb(k + 1, nz, 0)
    c = phi[i, j, k]
    dx = (phi[ip, j, k] - phi[im, j, k]) / (2.0 * h)
    dy = (phi[i, jp, k] - phi[i, jm, k]) / (2.0 * h)
    dz = (phi[i, j, kp] - phi[i, j, km]) / (2.0 * h)
    dxx = (phi[ip, j, k] - 2.0 * c + phi[im, j, k]) / (h * h)
    dyy = (phi[i, jp, k] - 2.0 * c + phi[i, jm, k]) / (h * h)
    dzz = (phi[i, j, kp] - 2.0 * c + phi[i, j, km]) / (h * h)
    dxy = (phi[ip, jp, k] - phi[ip, jm, k] - phi[im, jp, k] + phi[im, jm, k]) / (4.0 * h * h)
    dxz = (phi[ip, j, kp] - phi[ip, j, km] - phi[im, j, kp] + phi[im, j, km]) / (4.0 * h * h)
    dyz = (phi[i, jp, kp] - phi[i, jp, km] - phi[i, jm, kp] + phi[i, jm, km]) / (4.0 * h * h)
    g2 = dx * dx + dy * dy + dz * dz
    num = (dxx * (dy * dy + dz * dz) + dyy * (dx * dx + dz * dz) + dzz * (dx * dx + dy * dy)
           - 2.0 * dx * dy * dxy - 2.0 * dx * dz * dxz - 2.0 * dy * dz * dyz)
    kg = num / wp.max(g2, 1.0e-8)
    if band > 0.0:
        kg = wp.clamp(kg, -2.0 / h, 2.0 / h)
    a = (c - phi[im, j, k]) / h
    b = (phi[ip, j, k] - c) / h
    gp = wp.max(wp.max(a, 0.0) * wp.max(a, 0.0), wp.min(b, 0.0) * wp.min(b, 0.0))
    a = (c - phi[i, jm, k]) / h
    b = (phi[i, jp, k] - c) / h
    gp = gp + wp.max(wp.max(a, 0.0) * wp.max(a, 0.0), wp.min(b, 0.0) * wp.min(b, 0.0))
    a = (c - phi[i, j, km]) / h
    b = (phi[i, j, kp] - c) / h
    gp = gp + wp.max(wp.max(a, 0.0) * wp.max(a, 0.0), wp.min(b, 0.0) * wp.min(b, 0.0))
    new = c + dt * (kg - pr[i, j, k] * wp.sqrt(gp))
    out[i, j, k] = wp.min(wp.max(new, lo[i, j, k]), up[i, j, k])


def redistance_sym(phi, h, sym):
    """redistance() on a symmetric half (sym: the mirror plane through the first sample of axis 0): the half is
    mirrored to the full shape, redistanced, and cut back (the foot points across the plane are found)"""
    if not sym:
        return redistance(phi, h)
    full = np.concatenate([phi[:0:-1], phi], axis=0)
    return redistance(full, h)[phi.shape[0] - 1:]


def flow_wp(phi, lower, upper, pressure, h, steps, dt, reinit=20, log=None, sym=False, device=None, band=0.0):
    """flow() as a Warp kernel (the same scheme and clamps, float32 in a different order: not bit-identical to the
    numpy path, which the head keeps); sym: axis 0's first sample is a mirror plane (the grid holds the x >= 0 half of
    a symmetric shape); band > 0: the narrow band (k_flow_step). Returns phi and the per-chunk max change in the 6 h
    band"""
    dev = device or wp.get_preferred_device()
    hist = []
    lo_np = np.ascontiguousarray(lower, np.float32)
    up_np = np.ascontiguousarray(upper, np.float32)
    phi = np.minimum(np.maximum(phi, lo_np), up_np).astype(np.float32)
    L = wp.array(lo_np, dtype=wp.float32, device=dev)
    U = wp.array(up_np, dtype=wp.float32, device=dev)
    Pr = wp.array(np.ascontiguousarray(pressure, np.float32), dtype=wp.float32, device=dev)
    A = wp.array(phi, dtype=wp.float32, device=dev)
    B = wp.zeros(phi.shape, dtype=wp.float32, device=dev)
    done = 0
    while done < steps:
        n = min(reinit, steps - done)
        prev = A.numpy().copy()             # a copy: on the CPU device numpy() is a view of the ping-pong buffer
        for _ in range(n):
            wp.launch(k_flow_step, dim=phi.shape, inputs=[A, L, U, Pr, float(h), float(dt), int(bool(sym)),
                                                          float(band), B], device=dev)
            A, B = B, A
        done += n
        new = A.numpy()
        near = np.abs(new) < 6 * h
        hist.append(float(np.abs(new - prev)[near].max()) if near.any() else 0.0)
        new = np.minimum(np.maximum(redistance_sym(new, h, sym), lo_np), up_np).astype(np.float32)
        A = wp.array(new, dtype=wp.float32, device=dev)
        if log:
            log(f'[hull]   flow step {done}/{steps}: max |dphi| in the band over the last {n} steps {hist[-1]:.4f} mm')
    return A.numpy(), hist


# ============================================================================================ cache
def cache_key(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=lambda o: np.asarray(o).tolist()).encode()).hexdigest()[:16]


def cached(name, key, build, log=print):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f'{name}_{key}.npz')
    if os.path.exists(path):
        z = np.load(path, allow_pickle=False)
        return {k: z[k] for k in z.files}
    t = time.time()
    out = build()
    np.savez_compressed(path, **out)
    log(f'[hull] built {name} in {time.time() - t:.0f}s -> {path}')
    return out
