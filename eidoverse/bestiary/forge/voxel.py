"""SDF VOXEL SCULPTING (Skye 10-20: "sdf style voxel sculpting ... for highpolies"; the ice Roman bust's pipeline:
primitives fused and filleted as SDF grids, clay and carve passes of balls, smoothed and relevelled).

The HIGH is a sparse narrow-band signed-distance grid on the GPU (a Warp index volume: the active voxels' topology,
plus a writable float array of their values), initialised from the analytic block-out (sdf.Program) and then SCULPTED
by brush kernels:
  balls(centres, radii, 'add'|'carve', k)   clay added / carved with a fillet (smooth min/max), via a hash grid
  smooth(iters, strength, region)           a 6-neighbour mean, eased by a region weight
  offset(d)                                 grow or shrink
  redistance(iters=None)                    Eikonal re-initialisation (the "relevel": booleans leave the band's values
                                            off true distance; smoothing a ragged band tears it): the interface layer
                                            frozen, the rest solved outward over the whole band
SAMPLING is hybrid: trilinear inside the band, the analytic block-out outside it (all sculpting stays inside the band
by construction: a brush's reach must be less than the band).

MATERIAL IDS (DESIGN.md "GROWTH families"; work/bestiary/patches/material_ids_v2.md): one uint8 per voxel naming the
owner of the voxel's nearest surface. Every voxel starts as skin (0); a stroke batch writes its id wherever it WINS
(add: its distance d < the field v; carve: -d > v), so a label boundary sits on the fillet's crease. Smoothing, the
offset and the relevel move values only (crisp families can be held still by id); vmat votes the ids round a point
with trilinear weights (the bake's per-texel id).

    S = SparseSDF(prog, lo, hi, voxel=0.0003, band=0.0018)
    S.balls(C, R, 'add', k=0.0008); S.smooth(2, 0.5); S.redistance()
    S.strokes(STROKE_PRISM6, A, B, R, h, 'add', k, rc=spins, mat=growth.FAMILY_ID['ice'])
    S.eval(points); S.normals(points); S.project(points, dirs); S.materials(points)   (the bake and previews)
"""
import time

import numpy as np
import warp as wp

from . import growth as GR_
from . import sdf as S_

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile


# ---------------------------------------------------------------------------------------------------- sampling
@wp.func
def vlookup(vol: wp.uint64, val: wp.array(dtype=wp.float32), i: int, j: int, k: int):
    idx = wp.volume_lookup_index(vol, i, j, k)
    if idx < 0:
        return float(1.0e9)
    return val[idx]


@wp.func
def vsample(vol: wp.uint64, val: wp.array(dtype=wp.float32), p: wp.vec3):
    """trilinear over the 8 surrounding voxels; 1e9 if any is outside the band"""
    q = wp.volume_world_to_index(vol, p)
    i0 = int(wp.floor(q[0]))
    j0 = int(wp.floor(q[1]))
    k0 = int(wp.floor(q[2]))
    fx = q[0] - float(i0)
    fy = q[1] - float(j0)
    fz = q[2] - float(k0)
    acc = float(0.0)
    for c in range(8):
        dx = c & 1
        dy = (c >> 1) & 1
        dz = (c >> 2) & 1
        v = vlookup(vol, val, i0 + dx, j0 + dy, k0 + dz)
        if v > 1.0e8:
            return float(1.0e9)
        w = (fx if dx == 1 else 1.0 - fx) * (fy if dy == 1 else 1.0 - fy) * (fz if dz == 1 else 1.0 - fz)
        acc = acc + w * v
    return acc


@wp.func
def hybrid(p: wp.vec3, vol: wp.uint64, val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32),
           op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
           node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
           node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
           tri: wp.array(dtype=wp.int32)):
    v = vsample(vol, val, p)
    if v < 1.0e8:
        return v
    return S_.program(p, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)


@wp.func
def hgrad(p: wp.vec3, h: float, vol: wp.uint64, val: wp.array(dtype=wp.float32), n_prim: int,
          kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
          par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
          node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
          thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    ex = wp.vec3(h, 0.0, 0.0)
    ey = wp.vec3(0.0, h, 0.0)
    ez = wp.vec3(0.0, 0.0, h)
    gx = hybrid(p + ex, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri) - \
        hybrid(p - ex, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    gy = hybrid(p + ey, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri) - \
        hybrid(p - ey, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    gz = hybrid(p + ez, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri) - \
        hybrid(p - ez, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    return wp.vec3(gx, gy, gz) / (2.0 * h)


@wp.func
def bspline_w(t: float):
    s = 1.0 - t
    return wp.vec4(s * s * s / 6.0, (3.0 * t * t * t - 6.0 * t * t + 4.0) / 6.0,
                   (-3.0 * t * t * t + 3.0 * t * t + 3.0 * t + 1.0) / 6.0, t * t * t / 6.0)


@wp.func
def bspline_dw(t: float):
    s = 1.0 - t
    return wp.vec4(-0.5 * s * s, 0.5 * (3.0 * t * t - 4.0 * t), 0.5 * (-3.0 * t * t + 2.0 * t + 1.0), 0.5 * t * t)


@wp.func
def vgrad_cubic(vol: wp.uint64, val: wp.array(dtype=wp.float32), p: wp.vec3):
    """the gradient of the uniform cubic B-spline through the 4x4x4 voxels around p (index-space units; the direction
    is what the normals use). C2-continuous: trilinear gradients jump at every voxel face, which printed a voxel
    checker on small curved features (t10's sucker cups) even with a voxel-wide central difference. w = 0 when a
    voxel is outside the band"""
    q = wp.volume_world_to_index(vol, p)
    i0 = int(wp.floor(q[0]))
    j0 = int(wp.floor(q[1]))
    k0 = int(wp.floor(q[2]))
    wx = bspline_w(q[0] - float(i0))
    wy = bspline_w(q[1] - float(j0))
    wz = bspline_w(q[2] - float(k0))
    dx = bspline_dw(q[0] - float(i0))
    dy = bspline_dw(q[1] - float(j0))
    dz = bspline_dw(q[2] - float(k0))
    g = wp.vec3(0.0)
    for c in range(4):
        for b in range(4):
            for a in range(4):
                v = vlookup(vol, val, i0 - 1 + a, j0 - 1 + b, k0 - 1 + c)
                if v > 1.0e8:
                    return wp.vec4(0.0, 0.0, 0.0, 0.0)
                g = g + wp.vec3(dx[a] * wy[b] * wz[c], wx[a] * dy[b] * wz[c], wx[a] * wy[b] * dz[c]) * v
    return wp.vec4(g[0], g[1], g[2], 1.0)


@wp.func
def hnormal(p: wp.vec3, h: float, vol: wp.uint64, val: wp.array(dtype=wp.float32), n_prim: int,
            kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
            par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
            node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
            thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """the surface normal: the B-spline gradient inside the band, central differences of the hybrid field outside"""
    g4 = vgrad_cubic(vol, val, p)
    if g4[3] > 0.5:
        g = wp.vec3(g4[0], g4[1], g4[2])
        if wp.length(g) > 1.0e-12:
            return wp.normalize(g)
    return wp.normalize(hgrad(p, h, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                              thick, tri))


@wp.kernel
def k_heval(pts: wp.array(dtype=wp.vec3), out: wp.array(dtype=wp.float32), vol: wp.uint64,
            val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
            kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3),
            node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
            shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    i = wp.tid()
    out[i] = hybrid(pts[i], vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)


@wp.kernel
def k_hnormal(pts: wp.array(dtype=wp.vec3), h: float, out: wp.array(dtype=wp.vec3), vol: wp.uint64,
              val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32),
              op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
              node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
              node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
              tri: wp.array(dtype=wp.int32)):
    i = wp.tid()
    out[i] = wp.normalize(hgrad(pts[i], h, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                                shells, thick, tri))


@wp.kernel
def k_hproject(pts: wp.array(dtype=wp.vec3), dirs: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.vec3),
               status: wp.array(dtype=wp.int32), vol: wp.uint64, val: wp.array(dtype=wp.float32), n_prim: int,
               kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
               par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
               node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
               thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """along the direction (either way) to the zero: march in steps of 0.8 |f| (at least 0.2 voxel... the caller's
    maxd bounds it), bisect the bracket. status 0 found, 1 none within maxd (the point is returned unmoved)"""
    i = wp.tid()
    p0 = pts[i]
    d = wp.normalize(dirs[i])
    f0 = hybrid(p0, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    sgn = float(-1.0)
    if f0 < 0.0:
        sgn = 1.0
    t = float(0.0)
    f = f0
    lo = float(0.0)
    hi = float(0.0)
    ok = int(0)
    for it in range(160):
        step = wp.max(wp.abs(f) * 0.8, 5.0e-6)
        tn = t + step
        if tn > maxd:
            break
        fn = hybrid(p0 + d * (sgn * tn), vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                    thick, tri)
        if (fn > 0.0) != (f0 > 0.0):
            lo = t
            hi = tn
            ok = 1
            break
        t = tn
        f = fn
    if ok == 1:
        for it in range(32):
            mid = 0.5 * (lo + hi)
            fm = hybrid(p0 + d * (sgn * mid), vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                        shells, thick, tri)
            if (fm > 0.0) == (f0 > 0.0):
                lo = mid
            else:
                hi = mid
        out[i] = p0 + d * (sgn * 0.5 * (lo + hi))
        status[i] = 0
    else:
        out[i] = p0
        status[i] = 1


# ---------------------------------------------------------------------------------------------------- brushes
STROKE_CONE = 0      # round cone a -> b, radii ra -> rb
STROKE_CYL = 1       # cylinder from a to b, radius ra, edges rounded by rb
STROKE_TORUS = 2     # torus centred at a, axis toward b, major radius ra, minor radius rb
STROKE_ECONE = 3     # elliptic cone: apex a, axis toward b (length |b - a|), half-angles ra about the world-level
                     # horizontal and rb about the vertical (radians): an eye's aperture in one smooth shape (a
                     # union of balls printed every ball into the lid's bake, t14)
STROKE_PRISM6 = 4    # growth.sd_prism, EXACT: a hexagonal prism from its base a to its apex b, circumradius ra, a
                     # pyramidal tip of height rb (0: flat), turned by rc about its axis (crystals, ice shards)
STROKE_PRISM4 = 5    # the same with a square section (bismuth's hopper terraces)
MAT_SKIN = 0         # every voxel starts as skin; an 'add' batch without an id writes it
MAT_KEEP = 255       # a batch that writes no id (a carve's default: its walls show what it cut into)
assert (GR_.STROKE_PRISM6, GR_.STROKE_PRISM4, GR_.MAT_SKIN, GR_.MAT_KEEP) == (4, 5, 0, 255)


@wp.func
def sd_stroke(p: wp.vec3, kind: int, a: wp.vec3, b: wp.vec3, ra: float, rb: float, rc: float):
    if kind >= 4:
        sides = 6
        if kind == 5:
            sides = 4
        return GR_.sd_prism(p, a, b, ra, rb, rc, sides)
    if kind == 1:
        ax = b - a
        h = 0.5 * wp.length(ax)
        n = ax / wp.max(2.0 * h, 1.0e-12)
        q = p - 0.5 * (a + b)
        y = wp.dot(q, n)
        x = wp.length(q - n * y)
        dx = x - (ra - rb)
        dy = wp.abs(y) - (h - rb)
        return wp.min(wp.max(dx, dy), 0.0) + wp.length(wp.vec2(wp.max(dx, 0.0), wp.max(dy, 0.0))) - rb
    if kind == 2:
        n = wp.normalize(b - a)
        q = p - a
        y = wp.dot(q, n)
        x = wp.length(q - n * y)
        return wp.length(wp.vec2(x - ra, y)) - rb
    if kind == 3:
        ax = b - a
        len_e = wp.length(ax)
        n = ax / wp.max(len_e, 1.0e-12)
        e_h = wp.normalize(wp.cross(wp.vec3(0.0, 1.0, 0.0), n))
        e_u = wp.cross(n, e_h)
        q = p - a
        z_e = wp.dot(q, n)
        r_e = wp.length(q)
        ang_h = wp.atan2(wp.abs(wp.dot(q, e_h)), wp.max(z_e, 1.0e-9)) / ra
        ang_v = wp.atan2(wp.abs(wp.dot(q, e_u)), wp.max(z_e, 1.0e-9)) / rb
        # the angular excess in the ellipse metric, as a distance bound (0.85: the metric's anisotropy)
        d_e = (wp.sqrt(ang_h * ang_h + ang_v * ang_v) - 1.0) * wp.min(ra, rb) * r_e * 0.85
        if z_e <= 0.0:
            d_e = wp.max(d_e, 0.5 * r_e)
        return wp.max(d_e, z_e - len_e)
    return S_.sd_roundcone(p, a, b, ra, rb)


@wp.func
def stroke_reach(kind: int, ra: float, rb: float, L: float):
    if kind == 1 or kind >= 4:
        return ra                       # (a prism lies within its circumradius of its axis segment)
    if kind == 2:
        return ra + rb
    if kind == 3:
        return L * wp.tan(wp.min(wp.max(ra, rb), 1.4))
    return wp.max(ra, rb)


@wp.kernel
def k_stroke_box(vol: wp.uint64, kind: wp.array(dtype=wp.int32), A: wp.array(dtype=wp.vec3),
                 B: wp.array(dtype=wp.vec3), ra: wp.array(dtype=wp.float32), rb: wp.array(dtype=wp.float32),
                 pad: float, lo_out: wp.array(dtype=wp.vec3i), hi_out: wp.array(dtype=wp.vec3i)):
    """a stroke's padded box in index space (its reach plus pad round the segment a-b), inclusive"""
    t = wp.tid()
    a = A[t]
    b = B[t]
    r = stroke_reach(kind[t], ra[t], rb[t], wp.length(b - a)) + pad
    lo = wp.volume_world_to_index(vol, wp.vec3(wp.min(a[0], b[0]) - r, wp.min(a[1], b[1]) - r, wp.min(a[2], b[2]) - r))
    hi = wp.volume_world_to_index(vol, wp.vec3(wp.max(a[0], b[0]) + r, wp.max(a[1], b[1]) + r, wp.max(a[2], b[2]) + r))
    lo_out[t] = wp.vec3i(int(wp.floor(lo[0])), int(wp.floor(lo[1])), int(wp.floor(lo[2])))
    hi_out[t] = wp.vec3i(int(wp.ceil(hi[0])), int(wp.ceil(hi[1])), int(wp.ceil(hi[2])))


@wp.kernel
def k_scatter(vol: wp.uint64, kind: wp.array(dtype=wp.int32), A: wp.array(dtype=wp.vec3), B: wp.array(dtype=wp.vec3),
              ra: wp.array(dtype=wp.float32), rb: wp.array(dtype=wp.float32), pad: float,
              sid: wp.array(dtype=wp.int32), tlo: wp.array(dtype=wp.vec3i), thi: wp.array(dtype=wp.vec3i),
              rc: wp.array(dtype=wp.float32), dmin: wp.array(dtype=wp.float32)):
    """STROKE-LOCAL, one thread per TILE (at most SCATTER_TILE^3 voxels) of a stroke's padded box: every active voxel
    in it takes the exact minimum of the strokes' distances (atomic_min); a separate pass blends it into the field.
    t09's per-voxel hash queries over 70M voxels took 227 s for 30k strokes; one thread per stroke walked a wide
    stroke's 1-4M voxels alone (the hat's bow: 21 s for 56 strokes, and 12-23 min stalls with the GPU shared, t19b).
    rc: per-stroke spin (the prism kinds; the others ignore it)"""
    t = wp.tid()
    s = sid[t]
    a = A[s]
    b = B[s]
    lo = tlo[t]
    hi = thi[t]
    for i in range(lo[0], hi[0] + 1):
        for j in range(lo[1], hi[1] + 1):
            for k in range(lo[2], hi[2] + 1):
                idx = wp.volume_lookup_index(vol, i, j, k)
                if idx >= 0:
                    p = wp.volume_index_to_world(vol, wp.vec3(float(i), float(j), float(k)))
                    d = sd_stroke(p, kind[s], a, b, ra[s], rb[s], rc[s])
                    if d < pad:
                        wp.atomic_min(dmin, idx, d)


SCATTER_TILE = 16          # voxels per tile edge in k_scatter


@wp.kernel
def k_apply(val: wp.array(dtype=wp.float32), dmin: wp.array(dtype=wp.float32), mode: int, k: float,
            mat: wp.array(dtype=wp.uint8), mid: int):
    """the batch's union blended into the field; the batch's material id written where the batch WINS (its own
    distance below the field before the blend: the label boundary is the fillet's crease, where d = v). MAT_KEEP (255)
    writes nothing"""
    t = wp.tid()
    d = dmin[t]
    if d > 1.0e8:
        return
    v = val[t]
    if mode == 0:
        val[t] = S_.smin(v, d, k)
        if d < v and mid != 255:
            mat[t] = wp.uint8(mid)
    else:
        val[t] = S_.smax(v, -d, k)
        if -d > v and mid != 255:
            mat[t] = wp.uint8(mid)


@wp.kernel
def k_smooth(ijk: wp.array(dtype=wp.vec3i), src: wp.array(dtype=wp.float32), dst: wp.array(dtype=wp.float32),
             vol: wp.uint64, weight: wp.array(dtype=wp.float32), strength: float, mat: wp.array(dtype=wp.uint8),
             idw: wp.array(dtype=wp.float32)):
    t = wp.tid()
    c = ijk[t]
    v = src[t]
    acc = float(0.0)
    n = float(0.0)
    for a in range(6):
        di = 0
        dj = 0
        dk = 0
        if a == 0:
            di = 1
        elif a == 1:
            di = -1
        elif a == 2:
            dj = 1
        elif a == 3:
            dj = -1
        elif a == 4:
            dk = 1
        else:
            dk = -1
        u = vlookup(vol, src, c[0] + di, c[1] + dj, c[2] + dk)
        if u < 1.0e8:
            acc = acc + u
            n = n + 1.0
    if n > 0.0:
        s = strength * weight[t] * idw[int(mat[t])]      # (idw: per material id; crystal facets 0 stay crisp)
        dst[t] = v * (1.0 - s) + (acc / n) * s
    else:
        dst[t] = v


@wp.kernel
def k_relevel_init(ijk: wp.array(dtype=wp.vec3i), phi0: wp.array(dtype=wp.float32), vol: wp.uint64, vs: float,
                   dist: wp.array(dtype=wp.float32), mat: wp.array(dtype=wp.uint8), idw: wp.array(dtype=wp.float32)):
    """the relevel's INTERFACE LAYER, frozen (the subcell fix of Russo & Smereka 2000): a voxel with a sign change to
    one of its 6 neighbours keeps its distance to the interface from the local linear estimate phi0 / |grad phi0|
    (central differences, so the estimate is smooth from voxel to voxel; exact for a plane at any slope and any
    |grad phi0|), capped by the nearest crossing found along an axis (along an axis crossed on both sides, a feature
    under two voxels thick, the nearer crossing's one-sided difference). A voxel whose material id weighs 0 (idw:
    growth.relevel_table's crisp families, where a prism stroke wrote EXACT distances) is frozen at its sculpted value
    wherever it lies. Every other voxel gets 1e9 (k_relevel_solve solves it)"""
    t = wp.tid()
    c = ijk[t]
    v = phi0[t]
    dist[t] = float(1.0e9)
    if idw[int(mat[t])] <= 0.0:
        dist[t] = v                         # a HELD id: frozen at the sculpted value (data for its neighbours' solve)
        return
    if v == 0.0:
        dist[t] = 0.0
        return
    pos = v > 0.0
    g2 = float(0.0)
    cap = float(1.0e9)
    cross = int(0)
    for a in range(3):
        di = 0
        dj = 0
        dk = 0
        if a == 0:
            di = 1
        elif a == 1:
            dj = 1
        else:
            dk = 1
        m = vlookup(vol, phi0, c[0] - di, c[1] - dj, c[2] - dk)
        p = vlookup(vol, phi0, c[0] + di, c[1] + dj, c[2] + dk)
        hm = m < 1.0e8
        hp = p < 1.0e8
        cm = hm and ((m > 0.0) != pos)
        cp = hp and ((p > 0.0) != pos)
        if cm:
            cross = 1
            cap = wp.min(cap, vs * wp.abs(v) / wp.abs(v - m))
        if cp:
            cross = 1
            cap = wp.min(cap, vs * wp.abs(v) / wp.abs(p - v))
        g = float(0.0)
        if hm and hp:
            if cm and cp:
                g = wp.max(wp.abs(v - m), wp.abs(p - v))
            else:
                g = 0.5 * wp.abs(p - m)
        elif hm:
            g = wp.abs(v - m)
        elif hp:
            g = wp.abs(p - v)
        g2 = g2 + g * g
    if cross == 1:
        dist[t] = wp.sign(v) * wp.min(wp.abs(v) * vs / wp.max(wp.sqrt(g2), 1.0e-6 * vs), cap)


# |value| of a voxel the relevel has not reached yet: a value inside the band (vlookup reads 1e9 outside it, and every
# band-edge test is > 1e8), far above any distance in it
RELEVEL_UNKNOWN = wp.constant(1.0e6)


@wp.kernel
def k_relevel_seed(phi0: wp.array(dtype=wp.float32), dist: wp.array(dtype=wp.float32), cutoff: float,
                   val: wp.array(dtype=wp.float32)):
    """the relevel's start: the interface layer at its distance, every other voxel within the cutoff UNKNOWN with its
    sign; beyond the cutoff the sculpted value stands (held by k_relevel_solve)"""
    t = wp.tid()
    d0 = dist[t]
    if d0 < 1.0e8:
        val[t] = d0
    elif wp.abs(phi0[t]) >= cutoff:
        val[t] = phi0[t]
    elif phi0[t] < 0.0:
        val[t] = -RELEVEL_UNKNOWN
    else:
        val[t] = RELEVEL_UNKNOWN


@wp.kernel
def k_relevel_finish(phi0: wp.array(dtype=wp.float32), val: wp.array(dtype=wp.float32), mat: wp.array(dtype=wp.uint8),
                     idw: wp.array(dtype=wp.float32)):
    """a voxel the sweeps did not reach (or a band-edge voxel, never solved) gets its sculpted value back; a voxel whose
    material id weighs 0 < w < 1 (idw) keeps w of its relevelled change (1: all of it, untouched here; 0: held)"""
    t = wp.tid()
    if wp.abs(val[t]) > 0.5 * RELEVEL_UNKNOWN:
        val[t] = phi0[t]
    w = idw[int(mat[t])]
    if w > 0.0 and w < 1.0:
        val[t] = phi0[t] + (val[t] - phi0[t]) * w


@wp.func
def upwind2(s: float, n1: float, n2: float, vs: float):
    """one axis side's upwind datum for the local solve, (value, spacing): second order, (4 n1 - n2) / 3 at 2/3 of the
    spacing (the one-sided (3u - 4 n1 + n2) / 2h), where the next voxel out exists and the data fall monotonically
    toward the interface (across it too: a signed distance runs straight through); else first order, (n1, vs)"""
    a1 = s * n1
    if n2 < 1.0e8:
        a2 = s * n2
        if a2 <= a1:
            return wp.vec2((4.0 * a1 - a2) / 3.0, vs * 2.0 / 3.0)
    return wp.vec2(a1, vs)


@wp.func
def axis_datum(s: float, m1: float, p1: float, m2: float, p2: float, vs: float, order: int):
    """the axis's upwind side is the one nearer the interface (the smaller s * value)"""
    if s * m1 <= s * p1:
        if order == 2:
            return upwind2(s, m1, m2, vs)
        return wp.vec2(s * m1, vs)
    if order == 2:
        return upwind2(s, p1, p2, vs)
    return wp.vec2(s * p1, vs)


@wp.kernel
def k_relevel_solve(ijk: wp.array(dtype=wp.vec3i), src: wp.array(dtype=wp.float32), dst: wp.array(dtype=wp.float32),
                    dist: wp.array(dtype=wp.float32), phi0: wp.array(dtype=wp.float32), cutoff: float, vol: wp.uint64,
                    vs: float, order: int):
    """one Jacobi sweep of the Eikonal |grad phi| = 1 off the frozen interface layer: each voxel takes the Godunov
    upwind LOCAL SOLVE of its neighbours' values (Rouy & Tourin 1992, Zhao 2005's update; in parallel, Jeong & Whitaker
    2008's fast iterative method): sweep n reaches the n-th ring of voxels off the layer (its values over-read until
    a later sweep brings their neighbours in), where a pseudo-time step of 0.4 voxel only creeps toward it. The sign is
    the voxel's own (no voxel off the layer has a neighbour across the interface) and the layer is held, so nothing
    here can move the zero set. order 2: second-order one-sided differences where the data allow. Voxels beyond the
    cutoff hold their sculpted value (they serve only as data)"""
    t = wp.tid()
    d0 = dist[t]
    if d0 < 1.0e8:
        dst[t] = d0                         # the interface layer: held
        return
    if wp.abs(phi0[t]) >= cutoff:
        dst[t] = src[t]                     # beyond the cutoff: the sculpted value stands
        return
    c = ijk[t]
    v = src[t]
    xm = vlookup(vol, src, c[0] - 1, c[1], c[2])
    xp = vlookup(vol, src, c[0] + 1, c[1], c[2])
    ym = vlookup(vol, src, c[0], c[1] - 1, c[2])
    yp = vlookup(vol, src, c[0], c[1] + 1, c[2])
    zm = vlookup(vol, src, c[0], c[1], c[2] - 1)
    zp = vlookup(vol, src, c[0], c[1], c[2] + 1)
    if xm > 1.0e8 or xp > 1.0e8 or ym > 1.0e8 or yp > 1.0e8 or zm > 1.0e8 or zp > 1.0e8:
        dst[t] = v                          # the band's edge: left as it is
        return
    s = float(1.0)
    if v < 0.0:
        s = -1.0
    xm2 = float(1.0e9)
    xp2 = float(1.0e9)
    ym2 = float(1.0e9)
    yp2 = float(1.0e9)
    zm2 = float(1.0e9)
    zp2 = float(1.0e9)
    if order == 2:
        xm2 = vlookup(vol, src, c[0] - 2, c[1], c[2])
        xp2 = vlookup(vol, src, c[0] + 2, c[1], c[2])
        ym2 = vlookup(vol, src, c[0], c[1] - 2, c[2])
        yp2 = vlookup(vol, src, c[0], c[1] + 2, c[2])
        zm2 = vlookup(vol, src, c[0], c[1], c[2] - 2)
        zp2 = vlookup(vol, src, c[0], c[1], c[2] + 2)
    qa = axis_datum(s, xm, xp, xm2, xp2, vs, order)
    qb = axis_datum(s, ym, yp, ym2, yp2, vs, order)
    qc = axis_datum(s, zm, zp, zm2, zp2, vs, order)
    # sorted by the datum's value: an axis joins the solve once the solution passes its value
    if qb[0] < qa[0]:
        tmp = qa
        qa = qb
        qb = tmp
    if qc[0] < qb[0]:
        tmp = qb
        qb = qc
        qc = tmp
        if qb[0] < qa[0]:
            tmp = qa
            qa = qb
            qb = tmp
    u = qa[0] + qa[1]
    if u > qb[0]:
        wa = 1.0 / (qa[1] * qa[1])
        wb = 1.0 / (qb[1] * qb[1])
        sw = wa + wb
        sv = wa * qa[0] + wb * qb[0]
        sq = wa * qa[0] * qa[0] + wb * qb[0] * qb[0]
        u = (sv + wp.sqrt(wp.max(sv * sv - sw * (sq - 1.0), 0.0))) / sw
        if u > qc[0]:
            wc = 1.0 / (qc[1] * qc[1])
            sw = sw + wc
            sv = sv + wc * qc[0]
            sq = sq + wc * qc[0] * qc[0]
            u = (sv + wp.sqrt(wp.max(sv * sv - sw * (sq - 1.0), 0.0))) / sw
    dst[t] = s * u


@wp.kernel
def k_add(val: wp.array(dtype=wp.float32), d: float, weight: wp.array(dtype=wp.float32)):
    t = wp.tid()
    val[t] = val[t] - d * weight[t]


@wp.kernel
def k_eval_points(prog_pts: wp.array(dtype=wp.vec3), out: wp.array(dtype=wp.float32), n_prim: int,
                  kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
                  par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
                  node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
                  thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    i = wp.tid()
    out[i] = S_.program(prog_pts[i], n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)


@wp.kernel
def k_trace(origin0: wp.vec3, du: wp.vec3, dv: wp.vec3, dirv: wp.vec3, size: int, tmax: float, light: wp.vec3,
            min_step: float, grad_h: float, out: wp.array(dtype=wp.vec3), vol: wp.uint64,
            val: wp.array(dtype=wp.float32),
            n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
            par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
            node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
            thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """GPU eyes for the SDF high: orthographic sphere tracing of the hybrid field, gradient normals, SDF AO"""
    tid = wp.tid()
    px = tid % size
    py = tid // size
    o = origin0 + du * (float(px) + 0.5) + dv * (float(py) + 0.5)
    t = float(0.0)
    t_prev = float(0.0)
    f = hybrid(o, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    hit = int(0)
    for it in range(768):
        if f < 0.0:
            hit = 1
            break
        step = wp.max(f * 0.8, min_step)
        t_prev = t
        t = t + step
        if t > tmax:
            break
        f = hybrid(o + dirv * t, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                   tri)
    if hit == 0:
        out[tid] = wp.vec3(0.105, 0.105, 0.12)
        return
    # the crossing lies within the last full step (t07: a 2-step bracket missed it after an overshoot)
    lo = t_prev
    hi = t
    for it in range(20):
        mid = 0.5 * (lo + hi)
        fm = hybrid(o + dirv * mid, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                    thick, tri)
        if fm > 0.0:
            lo = mid
        else:
            hi = mid
    p = o + dirv * hi
    # the B-spline normal (trilinear gradients jump at voxel faces: t09/t10's stippled sucker cups)
    n = hnormal(p, grad_h, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    # SDF ambient occlusion (iq): how much the field falls short of free space along the normal
    occ = float(0.0)
    sca = float(1.0)
    for a in range(6):
        hs = 0.0006 + 0.0022 * float(a)
        dd = hybrid(p + n * hs, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                    tri)
        occ = occ + (hs - dd) * sca
        sca = sca * 0.75
    ao = wp.clamp(1.0 - 9.0 * occ / 0.012, 0.0, 1.0)
    key = wp.max(wp.dot(n, light), 0.0)
    fill = wp.max(wp.dot(n, -dirv), 0.0)
    shade = (0.14 + 0.62 * key + 0.30 * fill) * (0.35 + 0.65 * ao)
    out[tid] = wp.vec3(0.86, 0.84, 0.80) * shade


def trace_views(field, out_png, views=('side', 'front', 'top', 'threeq'), size=1024, center=None, span=None,
                label=''):
    """sphere-traced views of a SparseSDF (or a plain Program: wrap it with a 1-voxel dummy grid); center/span frame
    the shot (m), else the grid's bounds"""
    from PIL import Image, ImageDraw
    from .render import basis
    tiles = []
    lo = field.origin
    hi = field.origin + field.ijk.numpy().max(0) * field.vs
    ctr = np.asarray(center, np.float64) if center is not None else (lo + hi) / 2
    for vname in views:
        if isinstance(vname, str):
            right, upv, cam = basis(vname)
        else:                           # a direction toward the camera (world up kept up)
            cam = np.asarray(vname, np.float64) / np.linalg.norm(vname)
            right = np.cross(np.array([0.0, 1.0, 0.0]), cam)
            right /= np.linalg.norm(right)
            upv = np.cross(cam, right)
            vname = 'toward ' + ' '.join(f'{c:+.2f}' for c in cam)
        sp = span if span is not None else float(np.linalg.norm(hi - lo)) * 0.75
        pix = sp / size
        far = float(np.linalg.norm(hi - lo)) + 0.05
        origin0 = ctr - right * sp / 2 + upv * sp / 2 + cam * far
        light = cam * 0.55 + upv * 0.65 + right * 0.35
        light /= np.linalg.norm(light)
        out = wp.zeros(size * size, dtype=wp.vec3)
        wp.launch(k_trace, dim=size * size, inputs=[wp.vec3(*origin0), wp.vec3(*(right * pix)), wp.vec3(*(-upv * pix)),
                                                    wp.vec3(*(-cam)), size, 2.0 * far, wp.vec3(*light),
                                                    float(max(pix * 0.3, field.vs * 0.25)), float(field.vs * 0.9), out]
                  + field._args())
        img = (np.clip(out.numpy().reshape(size, size, 3), 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
        im = Image.fromarray(img)
        ImageDraw.Draw(im).text((6, 6), f'{label} {vname}  frame {sp:.3f} m', fill=(240, 240, 240))
        tiles.append(im)
    sheet = Image.new('RGB', (size * len(tiles), size))
    for i, t_ in enumerate(tiles):
        sheet.paste(t_, (i * size, 0))
    sheet.save(out_png)
    return out_png


# ---------------------------------------------------------------------------------------------------- material ids
@wp.struct
class LabAcc:
    """a vote over material ids: up to four ids and their summed weights (a fifth id adds to the fourth's weight)"""
    i0: int
    i1: int
    i2: int
    i3: int
    w0: float
    w1: float
    w2: float
    w3: float


@wp.func
def lab_new():
    a = LabAcc()
    a.i0 = -1
    a.i1 = -1
    a.i2 = -1
    a.i3 = -1
    a.w0 = 0.0
    a.w1 = 0.0
    a.w2 = 0.0
    a.w3 = 0.0
    return a


@wp.func
def lab_add(a: LabAcc, lab: int, w: float):
    o = a
    if w <= 0.0:
        return o
    if o.i0 == lab or o.i0 < 0:
        o.i0 = lab
        o.w0 = o.w0 + w
    elif o.i1 == lab or o.i1 < 0:
        o.i1 = lab
        o.w1 = o.w1 + w
    elif o.i2 == lab or o.i2 < 0:
        o.i2 = lab
        o.w2 = o.w2 + w
    else:
        if o.i3 < 0:
            o.i3 = lab
        o.w3 = o.w3 + w
    return o


@wp.func
def vmat(vol: wp.uint64, mat: wp.array(dtype=wp.uint8), p: wp.vec3, acc: LabAcc, scale: float):
    """the ids round p added to the vote: each of the 8 corners of p's cell gives its trilinear weight (x scale) to
    its id (a corner outside the band counts as MAT_SKIN: the analytic block-out is skin). Across a label boundary the
    weights ramp over one voxel: an antialiased edge, not a staircase"""
    q = wp.volume_world_to_index(vol, p)
    i0 = int(wp.floor(q[0]))
    j0 = int(wp.floor(q[1]))
    k0 = int(wp.floor(q[2]))
    fx = q[0] - float(i0)
    fy = q[1] - float(j0)
    fz = q[2] - float(k0)
    o = acc
    for c in range(8):
        dx = c & 1
        dy = (c >> 1) & 1
        dz = (c >> 2) & 1
        idx = wp.volume_lookup_index(vol, i0 + dx, j0 + dy, k0 + dz)
        lab = int(0)
        if idx >= 0:
            lab = int(mat[idx])
        w = (fx if dx == 1 else 1.0 - fx) * (fy if dy == 1 else 1.0 - fy) * (fz if dz == 1 else 1.0 - fz)
        o = lab_add(o, lab, w * scale)
    return o


@wp.func
def lab_pack(a: LabAcc):
    """the vote's two heaviest ids for the material pass, packed in an int32: id0 | id1 << 8 | round(255 w0 / (w0 +
    w1)) << 16. 0 = all skin (an empty or skin-only vote); a single growth id packs with runner-up 0 at weight 0"""
    b0 = a.i0
    v0 = a.w0
    if a.w1 > v0:
        b0 = a.i1
        v0 = a.w1
    if a.w2 > v0:
        b0 = a.i2
        v0 = a.w2
    if a.w3 > v0:
        b0 = a.i3
        v0 = a.w3
    if b0 < 0 or v0 <= 0.0:
        return int(0)
    b1 = int(0)
    v1 = float(0.0)
    if a.i0 >= 0 and a.i0 != b0 and a.w0 > v1:
        b1 = a.i0
        v1 = a.w0
    if a.i1 >= 0 and a.i1 != b0 and a.w1 > v1:
        b1 = a.i1
        v1 = a.w1
    if a.i2 >= 0 and a.i2 != b0 and a.w2 > v1:
        b1 = a.i2
        v1 = a.w2
    if a.i3 >= 0 and a.i3 != b0 and a.w3 > v1:
        b1 = a.i3
        v1 = a.w3
    if b0 == 0 and v1 <= 0.0:
        return int(0)
    f = v0 / wp.max(v0 + v1, 1.0e-12)
    return b0 | (b1 << 8) | (int(f * 255.0 + 0.5) << 16)


@wp.kernel
def k_vmat(pts: wp.array(dtype=wp.vec3), vol: wp.uint64, mat: wp.array(dtype=wp.uint8), out: wp.array(dtype=wp.int32)):
    i = wp.tid()
    out[i] = lab_pack(vmat(vol, mat, pts[i], lab_new(), 1.0))


# ---------------------------------------------------------------------------------------------------- the grid
@wp.kernel
def k_extra_dist(pts: wp.array(dtype=wp.vec3), grid: wp.uint64, C: wp.array(dtype=wp.vec3),
                 R: wp.array(dtype=wp.float32), reach: float, out: wp.array(dtype=wp.float32)):
    """the distance from each point to the nearest planned-stroke sphere's surface (1e9 beyond reach)"""
    t = wp.tid()
    p = pts[t]
    d = float(1.0e9)
    q = wp.hash_grid_query(grid, p, reach)
    i = int(0)
    while wp.hash_grid_query_next(q, i):
        d = wp.min(d, wp.length(p - C[i]) - R[i])
    out[t] = d


class SparseSDF:
    def __init__(self, prog, lo, hi, voxel=0.0003, band=0.0018, chunk=8_000_000, log=print, keep=None, extra=None):
        """keep(points (n, 3)) -> bool mask: an optional region filter on the coarse cells (the grid lives only where
        detail will be baked: the octopus's head and crown and the ONE arm its stacked arm island bakes from).
        extra = (centres (n, 3), radii (n,)): the planned strokes' bounding spheres; the band grows to contain them
        (t10: suckers stand ~6 mm off the skin, the +-2.5 mm band sliced them flat at its voxel-staircase edge)"""
        self._extra = None
        self.act_pad = 0.0
        if extra is not None and len(extra[0]):
            # every planned stroke's bounding sphere, grown by a margin so the field around a tall feature is carried
            # by voxels (the analytic block-out beyond the band does not know the feature)
            self.act_pad = 0.0015
            Ce = np.asarray(extra[0], np.float32).reshape(-1, 3)
            Re = np.asarray(extra[1], np.float32).reshape(-1) + self.act_pad
            self._extra = (wp.array(Ce, dtype=wp.vec3), wp.array(Re, dtype=wp.float32), float(Re.max()))
        t0 = time.time()
        self.prog = prog
        self.vs = float(voxel)
        self.band = float(band)
        self.origin = np.asarray(lo, np.float64)
        hi = np.asarray(hi, np.float64)
        vs = self.vs
        # 1. coarse cells (64 voxels) near the surface
        C = 64 * vs
        nC = np.ceil((hi - self.origin) / C).astype(int)
        g = np.stack(np.meshgrid(*[np.arange(n) for n in nC], indexing='ij'), -1).reshape(-1, 3)
        cc = self.origin + (g + 0.5) * C
        if keep is not None:
            m0 = keep(cc)
            g, cc = g[m0], cc[m0]
        f = self._eval_prog(cc, chunk)
        near = (np.abs(f) < band + C * 0.8661) | (self._extra_dist(cc, C * 0.8661 + vs) < C * 0.8661 + vs)
        cells = g[near]
        # 2. blocks (8 voxels) inside the kept cells
        b8 = np.stack(np.meshgrid(*[np.arange(8)] * 3, indexing='ij'), -1).reshape(-1, 3)
        blocks = (cells[:, None, :] * 8 + b8[None]).reshape(-1, 3)
        bc = self.origin + (blocks + 0.5) * (8 * vs)
        fb = self._eval_prog(bc, chunk)
        hb = 8 * vs * 0.8661
        in_band = np.abs(fb) < band + hb
        near_x = self._extra_dist(bc, hb + vs) < hb + vs
        keep_b = in_band | near_x
        blocks, near_x = blocks[keep_b], near_x[keep_b]
        # 3. voxels inside the kept blocks, kept where |f| < band or (in blocks a stroke sphere touches) inside one
        ijk_all, val_all = [], []
        per = max(1, chunk // 512)
        for s in range(0, len(blocks), per):
            vox = (blocks[s:s + per, None, :] * 8 + b8[None]).reshape(-1, 3)
            pv = self.origin + vox * vs
            fv = self._eval_prog(pv, chunk)
            m = np.abs(fv) < band
            bx = np.repeat(near_x[s:s + per], 512)
            if bx.any():
                m[bx] |= self._extra_dist(pv[bx], 2 * vs) < 2 * vs
            ijk_all.append(vox[m].astype(np.int32))
            val_all.append(fv[m].astype(np.float32))
        ijk = np.concatenate(ijk_all)
        vals = np.concatenate(val_all)
        self.vol = wp.Volume.allocate_by_voxels(wp.array(ijk, dtype=wp.vec3i), voxel_size=vs,
                                                translation=tuple(self.origin))
        order = self.vol.get_voxels().numpy()
        # the values in the volume's own index order (rebuild a lookup from the allocated order)
        key = lambda a: (a[:, 0].astype(np.int64) << 42) ^ ((a[:, 1].astype(np.int64) & 0x1FFFFF) << 21) ^ \
            (a[:, 2].astype(np.int64) & 0x1FFFFF)
        k_src = key(ijk)
        srt = np.argsort(k_src)
        pos = np.searchsorted(k_src[srt], key(order))
        self.ijk = wp.array(order.astype(np.int32), dtype=wp.vec3i)
        self.val = wp.array(vals[srt][pos], dtype=wp.float32)
        self.n = len(order)
        self.ones = wp.array(np.ones(self.n, np.float32), dtype=wp.float32)
        self.mat = wp.zeros(self.n, dtype=wp.uint8)       # MATERIAL IDS: every voxel starts as skin (MAT_SKIN)
        self._idw1 = wp.array(np.ones(256, np.float32), dtype=wp.float32)
        log(f'[voxel] {self.n:,} voxels at {vs*1000:.2f} mm, band +-{band*1000:.1f} mm '
            f'({len(cells)} cells, {len(blocks)} blocks) in {time.time()-t0:.1f}s')

    # -------------------------------------------------------------------------------------------- internals
    def _extra_dist(self, pts, pad):
        """distance to the nearest planned-stroke sphere (1e9 when none is within its radius + pad)"""
        if self._extra is None:
            return np.full(len(pts), 1.0e9, np.float32)
        Ce, Re, rmax = self._extra
        reach = float(rmax + pad)
        grid = wp.HashGrid(128, 128, 128)
        grid.build(Ce, reach)
        out = []
        for s in range(0, len(pts), 8_000_000):
            P = wp.array(np.asarray(pts[s:s + 8_000_000], np.float32), dtype=wp.vec3)
            o = wp.zeros(len(P), dtype=wp.float32)
            wp.launch(k_extra_dist, dim=len(P), inputs=[P, grid.id, Ce, Re, reach, o])
            out.append(o.numpy())
        return np.concatenate(out) if out else np.zeros(0, np.float32)

    def _eval_prog(self, pts, chunk):
        out = []
        for s in range(0, len(pts), chunk):
            out.append(self.prog.eval(pts[s:s + chunk]))
        return np.concatenate(out) if out else np.zeros(0, np.float32)

    def _args(self):
        return [self.vol.id, self.val] + self.prog._args()

    # -------------------------------------------------------------------------------------------- queries
    def eval(self, pts):
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.float32)
        wp.launch(k_heval, dim=len(P), inputs=[P, out] + self._args())
        return out.numpy()

    def normals(self, pts, h=None):
        h = h or 0.5 * self.vs
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.vec3)
        wp.launch(k_hnormal, dim=len(P), inputs=[P, float(h), out] + self._args())
        return out.numpy().astype(np.float64)

    def project(self, pts, dirs, maxd=0.01):
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        D = wp.array(np.asarray(dirs, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.vec3)
        st = wp.zeros(len(P), dtype=wp.int32)
        wp.launch(k_hproject, dim=len(P), inputs=[P, D, float(maxd), out, st] + self._args())
        return out.numpy().astype(np.float64), st.numpy()

    def positions(self):
        return self.origin + self.ijk.numpy().astype(np.float64) * self.vs

    def materials(self, pts):
        """the packed material vote at points (lab_pack: id0 | id1 << 8 | weight << 16; & 255 gives the dominant id)"""
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.int32)
        wp.launch(k_vmat, dim=len(P), inputs=[P, self.vol.id, self.mat, out])
        return out.numpy()

    def _idw(self, id_weights):
        if id_weights is None:
            return self._idw1
        w = np.asarray(id_weights, np.float32).reshape(-1)
        assert len(w) == 256, 'id_weights: one weight per material id (256)'
        return wp.array(w, dtype=wp.float32)

    # -------------------------------------------------------------------------------------------- brushes
    def balls(self, centres, radii, mode='add', k=0.0005):
        """clay ('add') or carve balls, filleted by k (a ball is a round cone of zero length)"""
        C = np.asarray(centres, np.float32).reshape(-1, 3)
        self.strokes(STROKE_CONE, C, C, radii, radii, mode, k)

    def capsules(self, A, B, ra, rb=None, mode='add', k=0.0005):
        """round-cone clay ('add') or carve strokes a-b with radii ra -> rb, filleted by k"""
        self.strokes(STROKE_CONE, A, B, ra, ra if rb is None else rb, mode, k)

    def strokes(self, kind, A, B, ra, rb, mode='add', k=0.0005, rc=None, mat=None):
        """one batch of strokes of a kind (STROKE_CONE / _CYL / _TORUS / _ECONE / _PRISM6 / _PRISM4, per stroke or one
        for all), unioned among themselves exactly, then added (smooth union) or carved (smooth subtraction) with
        fillet k. Every voxel within the band's reach of a stroke takes the exact union, so the field stays a distance
        bound wherever the band or a planned stroke's activation reaches (a sphere tracer's step there cannot cross a
        stroke). rc: per-stroke spin (the prisms; the other kinds ignore it). mat: the batch's MATERIAL ID, written
        where the batch wins; None = MAT_SKIN for an add, MAT_KEEP (no write) for a carve"""
        A = np.asarray(A, np.float32).reshape(-1, 3)
        B = np.asarray(B, np.float32).reshape(-1, 3)
        if not len(A):
            return
        n = len(A)
        kind = np.broadcast_to(np.asarray(kind, np.int32), (n,)).copy()
        ra = np.broadcast_to(np.asarray(ra, np.float32), (n,)).copy()
        rb = np.broadcast_to(np.asarray(rb, np.float32), (n,)).copy()
        rc = np.zeros(n, np.float32) if rc is None else np.broadcast_to(np.asarray(rc, np.float32), (n,)).copy()
        mid = (MAT_SKIN if mode == 'add' else MAT_KEEP) if mat is None else int(mat)
        assert 0 <= mid <= 255, mid
        dmin = wp.full(self.n, 1.0e9, dtype=wp.float32)
        pad = float(self.band + self.act_pad + 2 * k + self.vs)
        args = [self.vol.id, wp.array(kind, dtype=wp.int32), wp.array(A, dtype=wp.vec3), wp.array(B, dtype=wp.vec3),
                wp.array(ra, dtype=wp.float32), wp.array(rb, dtype=wp.float32), pad]
        # each stroke's padded box cut into tiles of SCATTER_TILE^3 voxels, one thread each
        lo_d, hi_d = wp.zeros(n, dtype=wp.vec3i), wp.zeros(n, dtype=wp.vec3i)
        wp.launch(k_stroke_box, dim=n, inputs=args + [lo_d, hi_d])
        lo, hi = lo_d.numpy().astype(np.int64), hi_d.numpy().astype(np.int64)
        T = SCATTER_TILE
        nt = np.maximum((hi - lo + 1 + T - 1) // T, 1)
        cnt = nt.prod(1)
        sid = np.repeat(np.arange(n), cnt)
        off = np.arange(int(cnt.sum())) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        nts = nt[sid]
        tile = np.column_stack([off // (nts[:, 1] * nts[:, 2]), (off // nts[:, 2]) % nts[:, 1], off % nts[:, 2]])
        tlo = lo[sid] + tile * T
        thi = np.minimum(tlo + T - 1, hi[sid])
        wp.launch(k_scatter, dim=len(sid), inputs=args + [wp.array(sid.astype(np.int32), dtype=wp.int32),
                                                          wp.array(tlo.astype(np.int32), dtype=wp.vec3i),
                                                          wp.array(thi.astype(np.int32), dtype=wp.vec3i),
                                                          wp.array(rc, dtype=wp.float32), dmin])
        wp.launch(k_apply, dim=self.n, inputs=[self.val, dmin, 0 if mode == 'add' else 1, float(k), self.mat, mid])

    def smooth(self, iters=1, strength=0.5, weight=None, id_weights=None):
        """id_weights: (256,) a weight per material id (growth.smooth_table(): crystal facets 0, so they stay crisp)"""
        w = self.ones if weight is None else wp.array(np.asarray(weight, np.float32), dtype=wp.float32)
        idw = self._idw(id_weights)
        tmp = wp.zeros_like(self.val)
        for _ in range(iters):
            wp.launch(k_smooth, dim=self.n, inputs=[self.ijk, self.val, tmp, self.vol.id, w, float(strength),
                                                    self.mat, idw])
            self.val, tmp = tmp, self.val

    def offset(self, d, weight=None):
        w = self.ones if weight is None else wp.array(np.asarray(weight, np.float32), dtype=wp.float32)
        wp.launch(k_add, dim=self.n, inputs=[self.val, float(d), w])

    def redistance(self, iters=None, order=2, id_weights=None):
        """the RELEVEL: |grad phi| = 1 restored in the band, the zero set held where the sculpt put it. The interface
        layer (the voxels with a sign change to a 6-neighbour) is frozen at its subcell distance (k_relevel_init); every
        other voxel starts UNKNOWN (k_relevel_seed: the sculpt's values under-read the distance where |grad phi| < 1, so
        a solve seeded with them would creep up over many sweeps), then `iters` Jacobi sweeps of the Godunov local solve
        run outward from the layer (k_relevel_solve): sweep n reaches every voxel n axis steps off the layer. A voxel
        still unknown after the last sweep (or on the band's edge) gets its sculpted value back (k_relevel_finish).
        Only voxels within the BAND are solved (|phi0| < band + 2 voxels); beyond it the sculpted values stand: an
        activation sphere's far air, 30-60 voxels off any surface, where the sweeps ran away (the Jacobi update with
        second-order data is not monotone: 51 mm wrong after 32 sweeps, 510 m after 64, in a 14.5 mm ball of air; the
        sculpt's lid bowls printed holes into the eye's views, v4).
        iters: the sweeps; None (the default) enough for every voxel within the band (~21 for +-2.5 mm at 0.3 mm).
        A few sweeps leave a seam where the last ring reached meets the sculpted values it hands back, about a
        millimetre off the surface: three hold the bake's normals (the cubic B-spline's 4^3 support), but the bake's
        curvature (its Laplacian reads 1.08 mm off the surface) prints that seam as terraces (t20 (b2)).
        id_weights: (256,) a weight per material id (growth.relevel_table()). 0 HOLDS that id's voxels at their sculpted
        values, frozen like the interface layer and read by their neighbours' solve (the crisp families: a prism
        stroke wrote EXACT distances there, and the layer's subcell estimate, exact for a plane, is not across a
        facet edge); 1 relevels them (None: every id 1, the relevel as without ids); between, w of the change"""
        if iters is not None and iters <= 0:
            return
        phi0 = wp.clone(self.val)
        idw = self._idw(id_weights)
        cutoff = self.band + 2.0 * self.vs
        if iters is None:
            # a voxel d off the layer is at most sqrt(3) d / voxel axis steps from it, and d can exceed |phi0| by the
            # sculpt's under-read (|grad phi0| ~0.8 over a blend): 1.25 cutoff / voxel * sqrt(3), plus two
            iters = min(int(np.ceil(1.7321 * 1.25 * cutoff / self.vs)) + 2, 64)
        dist = wp.empty_like(self.val)
        wp.launch(k_relevel_init, dim=self.n, inputs=[self.ijk, phi0, self.vol.id, self.vs, dist, self.mat, idw])
        wp.launch(k_relevel_seed, dim=self.n, inputs=[phi0, dist, float(cutoff), self.val])
        tmp = wp.zeros_like(self.val)
        for _ in range(iters):
            wp.launch(k_relevel_solve, dim=self.n, inputs=[self.ijk, self.val, tmp, dist, phi0, float(cutoff),
                                                           self.vol.id, self.vs, int(order)])
            self.val, tmp = tmp, self.val
        wp.launch(k_relevel_finish, dim=self.n, inputs=[phi0, self.val, self.mat, idw])
