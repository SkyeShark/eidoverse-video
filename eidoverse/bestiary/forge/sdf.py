"""The shape: a signed-distance PROGRAM evaluated on the GPU (Warp). A creature part's anatomy is a list of primitives
folded left to right with smooth booleans; the cage and the high are PROJECTED onto its zero set, so the designed
topology carries the anatomical shape (DESIGN.md: shape -> topology -> detail).

Primitives (each with an op: 0 smooth union, 1 smooth subtraction, 2 smooth intersection, and a blend radius k):
  ELLIPSOID   centre, rotation (3 x 3, columns = local axes), radii            (the cheap bound-corrected estimate)
  ROUNDCONE   a, b, ra, rb                                                       (exact)
  SWEEP       a dense centreline (nodes: position, frame normal, radius r0, polar harmonics a2 phi2 a3 phi3 a4, and an
              aspect (the b-axis scale)): the GLOBAL closest point on the polyline, the frame and profile interpolated
              at it, d = |q| - r(theta_q). Continuous across nodes by construction (no per-segment caps or frames:
              SPECIMEN's loft lesson). The ends are capped by the round-cone rule of the end segments.
  SHELL       an unsigned distance to a patch mesh minus a per-vertex half-thickness (Warp BVH): thin membranes (a web,
              a fin, an ear) that a closed primitive cannot describe. CONTINUOUS (opt-in per member, Program.shell's
              continuous=True: par[3] = 1, par[4] = its largest half-thickness): the least over the sheet's faces of
              |p - cp_f| - ht(cp_f), cp_f the closest point of face f (sd_shell_c). The default rule subtracts the
              half-thickness at the ONE closest point, so where that point jumps across a curled sheet's medial surface
              the field steps by the two half-thicknesses' difference (the wolf's ear base, W2w); each term here is
              continuous in p, so their least is, and with a constant half-thickness it is the default rule's value
  TORUS       centre, axis, ring radius R, tube radius r                         (exact: lips, rims, collars)
  REVOLVE     a closed profile polygon of (r, y) revolved about an axis through a centre (exact: the nearest point of
              a surface of revolution lies in the query's own meridian plane, so the distance is the 2D distance from
              (r, y) to the profile, signed by its crossing parity; segments ON the axis close the polygon and are not
              surface). The profile lives in the node arrays like SWEEP's (no new kernel arguments): hats, helmets,
              cups, lenses, bottles, horn rings, any lathe part
  OFFSET      the COAT: a coat-depth grid c (metres; trilinear, clamped to its box) turns everything before it into
              its envelope, d <- (d - s c) / (1 + s g), with s the coat scale and g a bound on |grad c|, so the field
              stays a distance bound. The LAST primitive, a group of its own with op 3 (ENVELOPE), never culled; the
              grid rides on the end of the shell thickness array (no new kernel arguments): fur over an approved skin
  PSWEEP      a swept POLYGON: SWEEP's centreline and foot point (with its own stored node tangents), the section a
              closed 2D polygon blended point by point between K key sections, scaled and turned per node, offset by
              a corner radius rho (the stored polygons are the CORE, the section shrunk by rho: section_core); the
              ends flat (the planes through the end nodes) and rounded with it. The exact 2D distance in the foot
              point's plane, divided by a host bound on its Lipschitz factor (the section's motion along the axis,
              the frame's turn, the curvature: sdf_psweep.md). The keys ride in the node arrays as REVOLVE's profile
              does (no new kernel arguments): mandibles, femora, keels, crests, claws
  ROUNDBOX    centre, rotation (3 x 3, columns = local axes), half extents, corner radius   (exact: lamellae, coxae)
Smooth booleans are the polynomial smin family (k in metres; k = 0 is the hard boolean).

GROUPS: consecutive primitives with the same group id combine among themselves first (each by its own op and k), and
the finished group then folds into the running result by the GROUP's op and k. Folding many overlapping primitives one
by one with smin COMPOUNDS (smin(d, d, k) = d - k/4 per step: eight arms meeting under a crown sank the oral surface
~2.8 cm, t04); a group of arms unions hard among itself and blends with the body once.
ROUND members (op ROUND = 5, crown v6 / v6b): a group of them combines by the n-ary ROUND UNION of radius r (their k,
one r per group, optionally a radius field: Program.begin_group's round_field), max(r, d1) - |((r - d_i)_+)_i| over
every member (Mercury's fOpUnionRound, n-ary): exact where at most one member lies within r of the point, a rounded
blend where two do (a quarter circle of radius r where two planes meet square), symmetric in its members (no order and
no switching "second nearest": C1 wherever d1 < r), and it never adds material farther than r from the members however
many meet (n members all within r fill a point only within r (1 - 1/sqrt(n)) of every one of them; smin's fill grows
with each member). Where the radius is 0 the group is its members' hard union (combine's op 5). The smooth union that
does not compound (the octopus's arm roots: saddles over the crown, the oral side as the hard union left it).
"""
import numpy as np
import warp as wp

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile

ELLIPSOID, ROUNDCONE, SWEEP, SHELL, TORUS, REVOLVE, OFFSET, PSWEEP, ROUNDBOX = 0, 1, 2, 3, 4, 5, 6, 7, 8
UNION, SUBTRACT, INTERSECT, ENVELOPE = 0, 1, 2, 3     # ENVELOPE is the OFFSET primitive's own op (combine())
NPAR = 32         # per primitive: its parameters, [20..22] the group, [24..29] its padded AABB


@wp.func
def smin(a: float, b: float, k: float):
    if k <= 0.0:
        return wp.min(a, b)
    h = wp.clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


@wp.func
def smax(a: float, b: float, k: float):
    return -smin(-a, -b, k)


@wp.func
def sd_ellipsoid(p: wp.vec3, c: wp.vec3, ax: wp.vec3, ay: wp.vec3, az: wp.vec3, r: wp.vec3):
    q = p - c
    l = wp.vec3(wp.dot(q, ax) / r[0], wp.dot(q, ay) / r[1], wp.dot(q, az) / r[2])
    k0 = wp.length(l)
    l2 = wp.vec3(l[0] / r[0], l[1] / r[1], l[2] / r[2])
    k1 = wp.length(l2)
    if k1 < 1.0e-12:
        return -wp.min(r[0], wp.min(r[1], r[2]))
    return k0 * (k0 - 1.0) / k1


@wp.func
def sd_roundcone(p: wp.vec3, a: wp.vec3, b: wp.vec3, r1: float, r2: float):
    # iq's exact round cone
    ba = b - a
    l2 = wp.dot(ba, ba)
    if l2 < 1.0e-14:
        # a zero-length cone is a ball (the formula degenerates to -r everywhere: t09's papillae became cubes)
        return wp.length(p - a) - wp.max(r1, r2)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / wp.max(l2, 1.0e-20)
    pa = p - a
    y = wp.dot(pa, ba)
    z = y - l2
    xv = pa * l2 - ba * y
    x2 = wp.dot(xv, xv)
    y2 = y * y * l2
    z2 = z * z * l2
    k = wp.sign(rr) * rr * rr * x2
    if wp.sign(z) * a2 * z2 > k:
        return wp.sqrt(x2 + z2) * il2 - r2
    if wp.sign(y) * a2 * y2 < k:
        return wp.sqrt(x2 + y2) * il2 - r1
    return (wp.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1


@wp.func
def sd_torus(p: wp.vec3, c: wp.vec3, n: wp.vec3, R: float, r: float):
    # exact: the distance to the ring of radius R about axis n through c, less the tube radius r
    q = p - c
    y = wp.dot(q, n)
    x = wp.length(q - n * y)
    return wp.length(wp.vec2(x - R, y)) - r


@wp.func
def sd_revolve(p: wp.vec3, start: int, count: int, c: wp.vec3, a: wp.vec3, node_p: wp.array(dtype=wp.vec3),
               node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4)):
    # exact: (r, y) in the point's meridian plane against the closed profile polygon. node_p[i] = (r_i, y_i, 1 when
    # segment i (point i -> i + 1, the last closing to 0) lies ON the axis: it closes the polygon, it is not surface);
    # node_n[i] = (the segment's edge, 1 / |edge|^2); every 8th point carries its chunk's bounding circle (node_r: r, y,
    # radius) and box (node_h: y min, y max, r max): a chunk farther than the best so far is skipped for the distance,
    # and one the +r ray cannot cross (the point outside its y range, or right of all of it) for the parity
    w = p - c
    y = wp.dot(w, a)
    r = wp.length(w - a * y)
    rt = wp.max(r, 1.0e-9)              # the parity from just off the axis: a point ON it never counts the axis segment
    best = float(1.0e30)
    sgn = float(1.0)
    j0 = int(0)
    while j0 < count:
        j1 = wp.min(j0 + 8, count)
        cb = node_r[start + j0]
        hb = node_h[start + j0]
        dc = wp.length(wp.vec2(r - cb[0], y - cb[1])) - cb[2]
        near = int(1)
        if dc > 0.0 and dc * dc > best:
            near = 0
        cross = int(1)
        if y < hb[0] or y > hb[1] or rt > hb[2]:
            cross = 0
        if near == 1 or cross == 1:
            for i in range(j0, j1):
                v = node_p[start + i]
                e = node_n[start + i]
                wx = r - v[0]
                wy = y - v[1]
                if near == 1 and v[2] < 0.5:
                    t = wp.clamp((wx * e[0] + wy * e[1]) * e[2], 0.0, 1.0)
                    bx = wx - e[0] * t
                    by = wy - e[1] * t
                    best = wp.min(best, bx * bx + by * by)
                if cross == 1:
                    k = i + 1
                    if k == count:
                        k = 0
                    u = node_p[start + k]
                    # iq's crossing rule (half-open in y, so a vertex at the point's height counts once): the segment
                    # passes the point's height with the point on its left going up, or on its right going down
                    nc = int(0)
                    if y >= v[1]:
                        nc = nc + 1
                    if y < u[1]:
                        nc = nc + 1
                    if e[0] * wy > e[1] * (rt - v[0]):
                        nc = nc + 1
                    if nc == 3 or nc == 0:
                        sgn = -sgn
        j0 = j0 + 8
    return sgn * wp.sqrt(best)


@wp.func
def node_tangent(j: int, start: int, count: int, node_p: wp.array(dtype=wp.vec3)):
    ja = wp.max(j - 1, start)
    jb = wp.min(j + 1, start + count - 1)
    return wp.normalize(node_p[jb] - node_p[ja])


@wp.func
def foot_g(p: wp.vec3, s: float, start: int, count: int, node_p: wp.array(dtype=wp.vec3)):
    """g(s) = (p - C(s)) . T(s) at the global segment parameter s (C piecewise linear, T interpolated node tangents:
    continuous), zero at the foot point"""
    j = wp.min(int(wp.floor(s)), count - 2)
    u = s - float(j)
    a = node_p[start + j]
    b = node_p[start + j + 1]
    c = a + (b - a) * u
    t = wp.normalize(node_tangent(start + j, start, count, node_p) * (1.0 - u)
                     + node_tangent(start + j + 1, start, count, node_p) * u)
    return wp.dot(p - c, t)


@wp.func
def sd_sweep(p: wp.vec3, start: int, count: int, node_p: wp.array(dtype=wp.vec3),
             node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4)):
    # the closest point on the polyline: the initial guess. CHUNKED: every 8 segments carry a bounding sphere (the
    # chunk's middle node, its radius in node_h[chunk start].w); a chunk wholly farther than the best so far is
    # skipped (the narrow band's tens of millions of evaluations: t07 took 139 s brute force)
    best = float(1.0e30)
    bj = int(start)
    bu = float(0.0)
    end = start + count - 1
    j0 = start
    while j0 < end:
        jm = wp.min(j0 + 4, end)
        dc = wp.length(p - node_p[jm]) - node_h[j0][3]
        if dc > 0.0 and dc * dc > best:
            j0 = j0 + 8
            continue
        for j in range(j0, wp.min(j0 + 8, end)):
            a = node_p[j]
            b = node_p[j + 1]
            ab = b - a
            u = wp.clamp(wp.dot(p - a, ab) / wp.max(wp.dot(ab, ab), 1.0e-20), 0.0, 1.0)
            d2 = wp.length_sq(p - (a + ab * u))
            if d2 < best:
                best = d2
                bj = j
                bu = u
        j0 = j0 + 8
    # THE FOOT POINT: the root of g(s) = (p - C(s)) . T(s) near the guess, by bisection. On the concave side of a
    # polyline the closest point JUMPS between segments (their regions overlap past each node: the t02 debug's 0.44 mm
    # field step); the root with the continuous tangent field is unique and continuous inside the curvature radius
    s0 = float(bj - start) + bu
    smax = float(count - 1) - 1.0e-6
    lo = wp.max(s0 - 2.0, 0.0)
    hi = wp.min(s0 + 2.0, smax)
    glo = foot_g(p, lo, start, count, node_p)
    ghi = foot_g(p, hi, start, count, node_p)
    s = s0
    if glo > 0.0 and ghi < 0.0:
        for it in range(24):
            mid = 0.5 * (lo + hi)
            if foot_g(p, mid, start, count, node_p) > 0.0:
                lo = mid
            else:
                hi = mid
        s = 0.5 * (lo + hi)
    elif glo <= 0.0 and lo <= 0.0:
        s = 0.0                     # before the start: the end node (a hemisphere cap through |q|)
    elif ghi >= 0.0 and hi >= smax:
        s = smax
    bj = start + wp.min(int(wp.floor(s)), count - 2)
    bu = s - float(bj - start)
    a = node_p[bj]
    b = node_p[bj + 1]
    c = a + (b - a) * bu
    t = wp.normalize(node_tangent(bj, start, count, node_p) * (1.0 - bu)
                     + node_tangent(bj + 1, start, count, node_p) * bu)
    n = wp.normalize(node_n[bj] * (1.0 - bu) + node_n[bj + 1] * bu)
    n = wp.normalize(n - t * wp.dot(n, t))
    bb = wp.cross(t, n)
    ra = node_r[bj] * (1.0 - bu) + node_r[bj + 1] * bu        # r0, a2, phi2, aspect
    ha = node_h[bj] * (1.0 - bu) + node_h[bj + 1] * bu        # a3, phi3, a4, (unused)
    q = p - c
    qn = wp.dot(q, n)
    qb = wp.dot(q, bb)
    th = wp.atan2(qb, qn)
    r = ra[0] * (1.0 + ra[1] * wp.cos(2.0 * (th - ra[2])) + ha[0] * wp.cos(3.0 * (th - ha[1])) + ha[2] * wp.cos(4.0 * th))
    # the aspect squeezes the b direction (an oval section) through the profile radius
    asp = ra[3]
    cs = wp.cos(th)
    sn = wp.sin(th)
    r = r * asp / wp.sqrt(asp * asp * cs * cs + sn * sn)
    # the TRUE distance to the polyline (continuous everywhere; past either end it is the distance to the end node, a
    # hemisphere of the end radius): never only the component across the segment, which jumps at joints. Divided by
    # sqrt(1 + (dr/dl)^2): where the radius changes fast along the axis (an egg's rounded end) |q| - r runs up to
    # 1.6x the true distance (t07: sphere tracing overshot into the mantle); exact for a round cone, safe elsewhere
    seg = wp.length(node_p[bj + 1] - node_p[bj])
    slope = (node_r[bj + 1][0] - node_r[bj][0]) / wp.max(seg, 1.0e-9)
    return (wp.length(q) - r) / wp.sqrt(1.0 + slope * slope)


@wp.func
def psweep_g(p: wp.vec3, s: float, start: int, count: int, node_p: wp.array(dtype=wp.vec3),
             node_h: wp.array(dtype=wp.vec4)):
    # foot_g with a PSWEEP's own node tangents (node_h.xyz): g(s) = (p - C(s)) . T(s), zero at the foot point
    j = wp.min(int(wp.floor(s)), count - 2)
    u = s - float(j)
    a = node_p[start + j]
    b = node_p[start + j + 1]
    ta = node_h[start + j]
    tb = node_h[start + j + 1]
    t = wp.normalize(wp.vec3(ta[0], ta[1], ta[2]) * (1.0 - u) + wp.vec3(tb[0], tb[1], tb[2]) * u)
    return wp.dot(p - (a + (b - a) * u), t)


@wp.func
def psweep_foot(p: wp.vec3, start: int, count: int, node_p: wp.array(dtype=wp.vec3), node_h: wp.array(dtype=wp.vec4)):
    # the foot point by sd_sweep's rule (the chunked closest segment, then the root of g by bisection within two
    # segments of it, clamped at the ends), with the PSWEEP's stored tangents: its global segment parameter s. Its own
    # function, so that sd_sweep's code, and with it every program built today, stays bit for bit as it was
    best = float(1.0e30)
    bj = int(start)
    bu = float(0.0)
    end = start + count - 1
    j0 = start
    while j0 < end:
        jm = wp.min(j0 + 4, end)
        dc = wp.length(p - node_p[jm]) - node_h[j0][3]
        if dc > 0.0 and dc * dc > best:
            j0 = j0 + 8
            continue
        for j in range(j0, wp.min(j0 + 8, end)):
            a = node_p[j]
            b = node_p[j + 1]
            ab = b - a
            u = wp.clamp(wp.dot(p - a, ab) / wp.max(wp.dot(ab, ab), 1.0e-20), 0.0, 1.0)
            d2 = wp.length_sq(p - (a + ab * u))
            if d2 < best:
                best = d2
                bj = j
                bu = u
        j0 = j0 + 8
    s0 = float(bj - start) + bu
    s_end = float(count - 1) - 1.0e-6
    lo = wp.max(s0 - 2.0, 0.0)
    hi = wp.min(s0 + 2.0, s_end)
    glo = psweep_g(p, lo, start, count, node_p, node_h)
    ghi = psweep_g(p, hi, start, count, node_p, node_h)
    s = s0
    if glo > 0.0 and ghi < 0.0:
        for it in range(24):
            mid = 0.5 * (lo + hi)
            if psweep_g(p, mid, start, count, node_p, node_h) > 0.0:
                lo = mid
            else:
                hi = mid
        s = 0.5 * (lo + hi)
    elif glo <= 0.0 and lo <= 0.0:
        s = 0.0
    elif ghi >= 0.0 and hi >= s_end:
        s = s_end
    return s


@wp.func
def sd_psweep(p: wp.vec3, cs: int, nc: int, ks: int, m: int, nk: int, rho: float, div: float,
              node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
              node_h: wp.array(dtype=wp.vec4)):
    # the centreline [cs, cs + nc) as SWEEP stores it, node_r = (scale u, scale v, twist, key position), node_h = (its
    # tangent, SWEEP's chunk radius); the nk key sections [ks, ks + nk m) of m points each as REVOLVE stores its
    # profile: node_p (x, y, 0), node_n (the edge to the next point, 1 / |edge|^2), every 8th point its chunk's circle
    # (node_r: x, y, radius) and box (node_h: y min, y max, x max). A blend of two keys keeps every point inside the
    # blend of their chunks' bounds
    s = psweep_foot(p, cs, nc, node_p, node_h)
    bj = cs + wp.min(int(wp.floor(s)), nc - 2)
    bu = s - float(bj - cs)
    a = node_p[bj]
    b = node_p[bj + 1]
    c = a + (b - a) * bu
    ta = node_h[bj]
    tb = node_h[bj + 1]
    t = wp.normalize(wp.vec3(ta[0], ta[1], ta[2]) * (1.0 - bu) + wp.vec3(tb[0], tb[1], tb[2]) * bu)
    n = wp.normalize(node_n[bj] * (1.0 - bu) + node_n[bj + 1] * bu)
    n = wp.normalize(n - t * wp.dot(n, t))
    bb = wp.cross(t, n)
    ra = node_r[bj] * (1.0 - bu) + node_r[bj + 1] * bu        # su, sv, twist, key position
    q = p - c
    qn = wp.dot(q, n)
    qb = wp.dot(q, bb)
    ct = wp.cos(ra[2])
    st = wp.sin(ra[2])
    x = ct * qn + st * qb                 # the point turned by -twist into the section's own axes
    y = ct * qb - st * qn
    su = ra[0]
    sv = ra[1]
    sm = wp.max(su, sv)
    kf = wp.clamp(ra[3], 0.0, float(nk - 1))
    i0 = wp.min(int(kf), wp.max(nk - 2, 0))
    w = kf - float(i0)
    k0 = ks + i0 * m
    k1 = ks + wp.min(i0 + 1, nk - 1) * m
    # the signed 2D distance to the core polygon (keys i0 and i0 + 1 blended point by point at w, then scaled): the
    # closest segment, and the parity of the +x ray's crossings by iq's rule, REVOLVE's method and chunk culling
    best = float(1.0e30)
    sgn = float(1.0)
    j0 = int(0)
    while j0 < m:
        j1 = wp.min(j0 + 8, m)
        ca = node_r[k0 + j0]
        cb = node_r[k1 + j0]
        ha = node_h[k0 + j0]
        hb = node_h[k1 + j0]
        dc = wp.length(wp.vec2(x - (ca[0] + (cb[0] - ca[0]) * w) * su, y - (ca[1] + (cb[1] - ca[1]) * w) * sv)) - \
            (ca[2] + (cb[2] - ca[2]) * w) * sm
        near = int(1)
        if dc > 0.0 and dc * dc > best:
            near = 0
        cross = int(1)
        if y < (ha[0] + (hb[0] - ha[0]) * w) * sv or y > (ha[1] + (hb[1] - ha[1]) * w) * sv or \
                x > (ha[2] + (hb[2] - ha[2]) * w) * su:
            cross = 0
        if near == 1 or cross == 1:
            for i in range(j0, j1):
                va = node_p[k0 + i]
                vb = node_p[k1 + i]
                ea = node_n[k0 + i]
                eb = node_n[k1 + i]
                vx = (va[0] + (vb[0] - va[0]) * w) * su
                vy = (va[1] + (vb[1] - va[1]) * w) * sv
                ex = (ea[0] + (eb[0] - ea[0]) * w) * su
                ey = (ea[1] + (eb[1] - ea[1]) * w) * sv
                wx = x - vx
                wy = y - vy
                if near == 1:
                    tt = wp.clamp((wx * ex + wy * ey) / wp.max(ex * ex + ey * ey, 1.0e-30), 0.0, 1.0)
                    bx = wx - ex * tt
                    by = wy - ey * tt
                    best = wp.min(best, bx * bx + by * by)
                if cross == 1:
                    kn = i + 1
                    if kn == m:
                        kn = 0
                    ua = node_p[k0 + kn]
                    ub = node_p[k1 + kn]
                    uy = (ua[1] + (ub[1] - ua[1]) * w) * sv
                    nx = int(0)
                    if y >= vy:
                        nx = nx + 1
                    if y < uy:
                        nx = nx + 1
                    if ex * wy > ey * wx:
                        nx = nx + 1
                    if nx == 3 or nx == 0:
                        sgn = -sgn
        j0 = j0 + 8
    d2 = sgn * wp.sqrt(best)
    # the flat ends: the half-spaces past the planes through the end nodes, normal to the end tangents; iq's
    # extrusion (the larger inside, the corner's length outside), then the corner radius
    t0 = node_h[cs]
    t1 = node_h[cs + nc - 1]
    da = wp.max(wp.dot(node_p[cs] - p, wp.normalize(wp.vec3(t0[0], t0[1], t0[2]))),
                wp.dot(p - node_p[cs + nc - 1], wp.normalize(wp.vec3(t1[0], t1[1], t1[2]))))
    ext = wp.length(wp.vec2(wp.max(d2, 0.0), wp.max(da, 0.0))) + wp.min(wp.max(d2, da), 0.0)
    return (ext - rho) / div


@wp.func
def sd_roundbox(p: wp.vec3, c: wp.vec3, ax: wp.vec3, ay: wp.vec3, az: wp.vec3, h: wp.vec3, r: float):
    # exact (iq's rounded box): q = |R^T (p - c)| - (h - r), d = |max(q, 0)| + min(max(q), 0) - r
    w = p - c
    qx = wp.abs(wp.dot(w, ax)) - (h[0] - r)
    qy = wp.abs(wp.dot(w, ay)) - (h[1] - r)
    qz = wp.abs(wp.dot(w, az)) - (h[2] - r)
    return wp.length(wp.vec3(wp.max(qx, 0.0), wp.max(qy, 0.0), wp.max(qz, 0.0))) + \
        wp.min(wp.max(qx, wp.max(qy, qz)), 0.0) - r


@wp.func
def sd_shell(p: wp.vec3, mesh: wp.uint64, thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32),
             tri_base: int, maxd: float):
    q = wp.mesh_query_point_no_sign(mesh, p, maxd)
    if not q.result:
        return maxd
    cp = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
    f = tri_base + q.face * 3
    w = 1.0 - q.u - q.v
    ht = thick[tri[f]] * q.u + thick[tri[f + 1]] * q.v + thick[tri[f + 2]] * w
    return wp.length(p - cp) - ht


@wp.func
def tri_closest_bary(p: wp.vec3, a: wp.vec3, b: wp.vec3, c: wp.vec3):
    # the closest point of the triangle abc to p, as its barycentric weights on (a, b, c): Ericson's Voronoi-region test
    # (Real-Time Collision Detection 5.1.5), the regions in his order (vertex a, vertex b, edge ab, vertex c, edge ac,
    # edge bc, the face), a near-zero denominator (a degenerate edge or face) read as 1 so the weights stay finite (the
    # W2w fresh eyes' CPU reference, check_w2w_fresh/shell_minface.py closest_on_tris, does the same)
    ab = b - a
    ac = c - a
    ap = p - a
    d1 = wp.dot(ab, ap)
    d2 = wp.dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return wp.vec3(1.0, 0.0, 0.0)
    bp = p - b
    d3 = wp.dot(ab, bp)
    d4 = wp.dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return wp.vec3(0.0, 1.0, 0.0)
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        den = d1 - d3
        if wp.abs(den) <= 1.0e-30:
            den = 1.0
        v = d1 / den
        return wp.vec3(1.0 - v, v, 0.0)
    pc = p - c
    d5 = wp.dot(ab, pc)
    d6 = wp.dot(ac, pc)
    if d6 >= 0.0 and d5 <= d6:
        return wp.vec3(0.0, 0.0, 1.0)
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        den = d2 - d6
        if wp.abs(den) <= 1.0e-30:
            den = 1.0
        w = d2 / den
        return wp.vec3(1.0 - w, 0.0, w)
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        den = (d4 - d3) + (d5 - d6)
        if wp.abs(den) <= 1.0e-30:
            den = 1.0
        w = (d4 - d3) / den
        return wp.vec3(0.0, 1.0 - w, w)
    den = va + vb + vc
    if wp.abs(den) <= 1.0e-30:
        den = 1.0
    v = vb / den
    w = vc / den
    return wp.vec3(1.0 - v - w, v, w)


@wp.func(inline=False)
def sd_shell_c(p: wp.vec3, mesh: wp.uint64, thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32),
               tri_base: int, ht_max: float, maxd: float, s0: float):
    # the CONTINUOUS SHELL (opt-in: Program.shell(continuous=True)): g(p) = the least over the sheet's faces f of
    # |p - cp_f| - ht(cp_f), cp_f the closest point of face f to p, ht interpolated there. Each term is continuous in p
    # (the closest point of a triangle moves continuously with p, ht is linear on the face), so their least is;
    # sd_shell's single closest point jumps where it crosses a curled sheet's medial surface, and its ht with it.
    # s0 = sd_shell(p), computed first by program() exactly as for any SHELL, is the closest face's own term, so
    # g <= s0, and a face can be lower only where |p - cp_f| < s0 + ht(cp_f) <= s0 + ht_max: the mesh's own BVH query
    # of that radius (plus 1 um against float32 rounding) visits every candidate. Warp's SPHERE query (an exact
    # sphere-box broad phase, then only the faces whose closest point lies within the radius): at the wolf's ear it
    # returns exactly the faces the reach needs (p50 107 at the skin where the closest point jumps), where the box query
    # of the same half-width returned 753, and it ran 2x faster on the GPU (W2x t1_kernel.py). Beyond maxd (no face
    # within it) the value stays maxd, as sd_shell's. (s0 is passed in, not recomputed here: with a second inlined
    # sd_shell in program() the CUDA build of every default SHELL's value moved by 1-2 ulp, up to 6 um at near-ties
    # of the closest face: W2x t2_parity.py, the first staging.) NOT INLINED (inline=False): inlined, this loop's
    # code grew program() enough that the CUDA build of grad()'s six program() calls changed, and with the flag off
    # the props' normals moved by ulps (peaked_cap 555 / top_hat 295 of 30,000, p99 0.01 deg, all values identical);
    # a call kept out of line leaves program()'s own code as it was (W2x t2_parity.py on cuda:0)
    if s0 >= maxd:
        return s0
    best = s0
    r = s0 + ht_max + 1.0e-6
    m = wp.mesh_get(mesh)
    query = wp.mesh_query_sphere(mesh, p, r)
    fi = int(0)
    while wp.mesh_query_next(query, fi):
        a = m.points[m.indices[fi * 3]]
        b = m.points[m.indices[fi * 3 + 1]]
        c = m.points[m.indices[fi * 3 + 2]]
        bw = tri_closest_bary(p, a, b, c)
        t = tri_base + fi * 3
        h = thick[tri[t]] * bw[0] + thick[tri[t + 1]] * bw[1] + thick[tri[t + 2]] * bw[2]
        best = wp.min(best, wp.length(p - (a * bw[0] + b * bw[1] + c * bw[2])) - h)
    return best


@wp.func
def coat_depth(p: wp.vec3, thick: wp.array(dtype=wp.float32), base: int, nx: int, ny: int, nz: int, org: wp.vec3,
               inv_cell: float):
    # the OFFSET's grid, thick[base + (i * ny + j) * nz + k] = c at org + (i, j, k) * cell: trilinear, the point
    # clamped to the grid's box (continuous everywhere, so the grid's gradient bound holds outside the box too)
    q = (p - org) * inv_cell
    x = wp.clamp(q[0], 0.0, float(nx - 1))
    y = wp.clamp(q[1], 0.0, float(ny - 1))
    z = wp.clamp(q[2], 0.0, float(nz - 1))
    i = wp.min(int(x), nx - 2)
    j = wp.min(int(y), ny - 2)
    k = wp.min(int(z), nz - 2)
    fx = x - float(i)
    fy = y - float(j)
    fz = z - float(k)
    acc = float(0.0)
    for c in range(8):
        di = c & 1
        dj = (c >> 1) & 1
        dk = (c >> 2) & 1
        w = (fx if di == 1 else 1.0 - fx) * (fy if dj == 1 else 1.0 - fy) * (fz if dk == 1 else 1.0 - fz)
        acc = acc + w * thick[base + ((i + di) * ny + (j + dj)) * nz + (k + dk)]
    return acc


@wp.func
def combine(d: float, di: float, o: int, k: float):
    if o == 0:
        return smin(d, di, k)
    if o == 1:
        return smax(d, -di, k)
    if o == 3:
        # ENVELOPE (the OFFSET's group): di = s c(p) and k = s g. |grad d| <= 1 and |grad di| <= s g, so the
        # division keeps the field a distance bound
        return (d - di) / (1.0 + k)
    if o == 5:
        # a ROUND member (crown v6b): its group's running value is the members' HARD union, the round union of
        # radius 0, which round_end returns where the group's radius is 0 (crown v6 let op 5 fall to smax below: a
        # radius field easing to 0 would have INTERSECTED the arms beyond it)
        return wp.min(d, di)
    return smax(d, di, k)


ROUND = 5         # crown v6: a ROUND member's op (its group's n-ary round union of radius = its k; round_end)


@wp.func
def round_radius(p: wp.vec3, par: wp.array(dtype=wp.float32), o: int, r_in: float):
    """a ROUND member's radius at p: its k (r_in), or with a RADIUS FIELD (par[o + 8] = 1; Program.begin_group's
    round_field) easing (smoothstep) from r_in to par[o + 17] as the distance from the centre par[o + 9..11], its
    axes scaled by par[o + 12..14], runs from par[o + 15] to par[o + 16] (C1 in p, at most r_in: the culling's bound)"""
    if par[o + 8] < 0.5:
        return r_in
    q = p - wp.vec3(par[o + 9], par[o + 10], par[o + 11])
    t = wp.clamp((wp.length(wp.vec3(q[0] * par[o + 12], q[1] * par[o + 13], q[2] * par[o + 14])) - par[o + 15]) /
                 wp.max(par[o + 16] - par[o + 15], 1.0e-9), 0.0, 1.0)
    return r_in + (par[o + 17] - r_in) * t * t * (3.0 - 2.0 * t)


@wp.func
def round_end(g: float, gmin: float, acc: float, r: float):
    """a finished group's value: a ROUND group's (r > 0) max(r, d1) - sqrt(sum_i (r - d_i)_+^2), from its nearest
    member d1 = gmin and that sum acc; any other group's own running value g (a ROUND group's where its radius is 0:
    the hard union, combine's op 5)"""
    if r <= 0.0:
        return g
    return wp.max(r, gmin) - wp.sqrt(acc)


@wp.func
def aabb_dist(p: wp.vec3, lo: wp.vec3, hi: wp.vec3):
    q = wp.vec3(wp.max(wp.max(lo[0] - p[0], p[0] - hi[0]), 0.0), wp.max(wp.max(lo[1] - p[1], p[1] - hi[1]), 0.0),
                wp.max(wp.max(lo[2] - p[2], p[2] - hi[2]), 0.0))
    return wp.length(q)


@wp.func
def program(p: wp.vec3, n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
            kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
            node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
            node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
            tri: wp.array(dtype=wp.int32)):
    # par[o + 20] = group id, par[o + 21] = the group's op, par[o + 22] = the group's k (read at the group's first
    # primitive); within a group each primitive combines by its own op and k. par[o + 24..29] = the primitive's
    # padded AABB: a UNION member whose box lies farther than the result before its group plus the group's blend
    # cannot touch the result and is skipped (the narrow band's ~90M evaluations: most primitives are far from most
    # points)
    d = float(1.0e9)
    gd = float(1.0e9)
    gmin = float(1.0e9)         # a ROUND group's nearest member, its sum of (r - d_i)_+^2 and its radius (0: none)
    gacc = float(0.0)
    gr = float(0.0)
    d_before = float(1.0e9)
    first_group = int(1)
    for i in range(n_prim):
        o = i * 32
        gid = par[o + 20]
        new_group = int(0)
        if i == 0:
            new_group = 1
        elif par[o - 32 + 20] != gid:
            new_group = 1
        if new_group == 1 and i > 0:
            # fold the finished group into the result with ITS op and k (stored at its first primitive)
            j = i - 1
            while j > 0 and par[(j - 1) * 32 + 20] == par[j * 32 + 20]:
                j = j - 1
            gd = round_end(gd, gmin, gacc, gr)
            if first_group == 1:
                d = gd
                first_group = 0
            else:
                d = combine(d, gd, int(par[j * 32 + 21]), par[j * 32 + 22])
        if new_group == 1:
            d_before = d
            gd = float(1.0e9)
            gmin = float(1.0e9)
            gacc = float(0.0)
            gr = float(0.0)
        di = float(1.0e9)
        skip = int(0)
        if (op[i] == 0 or op[i] == 5) and int(par[o + 21]) == 0 and first_group == 0:
            # (a ROUND member is kept wherever its box lies within its radius of p: farther it adds nothing to the
            # norm, and were it the nearest member its group's value would stand past d_before + the group's k)
            reach = d_before + par[o + 22]
            if op[i] == 5:
                reach = wp.max(reach, kk[i])
            if aabb_dist(p, wp.vec3(par[o + 24], par[o + 25], par[o + 26]),
                         wp.vec3(par[o + 27], par[o + 28], par[o + 29])) > reach + 1.0e-4:
                skip = 1
        if skip == 1:
            di = float(1.0e9)
        elif kind[i] == 0:
            di = sd_ellipsoid(p, wp.vec3(par[o], par[o + 1], par[o + 2]),
                              wp.vec3(par[o + 3], par[o + 4], par[o + 5]), wp.vec3(par[o + 6], par[o + 7], par[o + 8]),
                              wp.vec3(par[o + 9], par[o + 10], par[o + 11]),
                              wp.vec3(par[o + 12], par[o + 13], par[o + 14]))
        elif kind[i] == 1:
            di = sd_roundcone(p, wp.vec3(par[o], par[o + 1], par[o + 2]), wp.vec3(par[o + 3], par[o + 4], par[o + 5]),
                              par[o + 6], par[o + 7])
        elif kind[i] == 2:
            di = sd_sweep(p, int(par[o]), int(par[o + 1]), node_p, node_n, node_r, node_h)
        elif kind[i] == 3:
            di = sd_shell(p, shells[int(par[o])], thick, tri, int(par[o + 1]), par[o + 2])
            if par[o + 3] > 0.5:
                # a CONTINUOUS shell (Program.shell(continuous=True)): refined from that value, par[o + 4] its largest
                # half-thickness
                di = sd_shell_c(p, shells[int(par[o])], thick, tri, int(par[o + 1]), par[o + 4], par[o + 2], di)
        elif kind[i] == 4:
            di = sd_torus(p, wp.vec3(par[o], par[o + 1], par[o + 2]), wp.vec3(par[o + 3], par[o + 4], par[o + 5]),
                          par[o + 6], par[o + 7])
        elif kind[i] == 5:
            di = sd_revolve(p, int(par[o]), int(par[o + 1]), wp.vec3(par[o + 2], par[o + 3], par[o + 4]),
                            wp.vec3(par[o + 5], par[o + 6], par[o + 7]), node_p, node_n, node_r, node_h)
        elif kind[i] == 6:
            di = coat_depth(p, thick, int(par[o]), int(par[o + 1]), int(par[o + 2]), int(par[o + 3]),
                            wp.vec3(par[o + 4], par[o + 5], par[o + 6]), par[o + 7]) * par[o + 8]
        elif kind[i] == 7:
            di = sd_psweep(p, int(par[o]), int(par[o + 1]), int(par[o + 2]), int(par[o + 3]), int(par[o + 4]),
                           par[o + 5], par[o + 6], node_p, node_n, node_r, node_h)
        elif kind[i] == 8:
            di = sd_roundbox(p, wp.vec3(par[o], par[o + 1], par[o + 2]), wp.vec3(par[o + 3], par[o + 4], par[o + 5]),
                             wp.vec3(par[o + 6], par[o + 7], par[o + 8]), wp.vec3(par[o + 9], par[o + 10], par[o + 11]),
                             wp.vec3(par[o + 12], par[o + 13], par[o + 14]), par[o + 15])
        if new_group == 1:
            gd = di
        else:
            gd = combine(gd, di, op[i], kk[i])
        if op[i] == 5:
            # a ROUND member: its group's nearest member and the norm's sum (round_end makes the group's value from
            # them; combine's hard union for op 5 is the value where the radius is 0); the radius at p (one field per
            # group: Program.begin_group)
            gr = round_radius(p, par, o, kk[i])
            gmin = wp.min(gmin, di)
            gacc = gacc + wp.max(gr - di, 0.0) * wp.max(gr - di, 0.0)
    # the last group
    j = n_prim - 1
    while j > 0 and par[(j - 1) * 32 + 20] == par[j * 32 + 20]:
        j = j - 1
    gd = round_end(gd, gmin, gacc, gr)
    if first_group == 1:
        d = gd
    else:
        d = combine(d, gd, int(par[j * 32 + 21]), par[j * 32 + 22])
    return d


@wp.kernel
def k_eval(pts: wp.array(dtype=wp.vec3), out: wp.array(dtype=wp.float32), n_prim: int,
           kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
           par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
           node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
           thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    i = wp.tid()
    out[i] = program(pts[i], n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)


@wp.func
def grad(p: wp.vec3, h: float, n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
         kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3),
         node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
         shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    ex = wp.vec3(h, 0.0, 0.0)
    ey = wp.vec3(0.0, h, 0.0)
    ez = wp.vec3(0.0, 0.0, h)
    gx = program(p + ex, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri) - \
        program(p - ex, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    gy = program(p + ey, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri) - \
        program(p - ey, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    gz = program(p + ez, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri) - \
        program(p - ez, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    return wp.vec3(gx, gy, gz) / (2.0 * h)


@wp.kernel
def k_project(pts: wp.array(dtype=wp.vec3), dirs: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.vec3),
              status: wp.array(dtype=wp.int32), n_prim: int, kind: wp.array(dtype=wp.int32),
              op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
              node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
              node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
              tri: wp.array(dtype=wp.int32)):
    """move each point along its direction (either way) to the field's zero: sphere-trace toward the surface, then
    bisect the bracket; status 0 = projected along the ray, 1 = Newton fallback (no crossing within maxd), 2 = failed"""
    i = wp.tid()
    p0 = pts[i]
    d = wp.normalize(dirs[i])
    f0 = program(p0, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    sgn = float(-1.0)
    if f0 < 0.0:
        sgn = 1.0                       # inside: march outward along d
    t = float(0.0)
    f = f0
    ok = int(0)
    lo = float(0.0)
    hi = float(0.0)
    for it in range(96):
        step = wp.max(wp.abs(f) * 0.8, 2.0e-6)
        tn = t + step
        if tn > maxd:
            break
        fn = program(p0 + d * (sgn * tn), n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                     tri)
        if (fn > 0.0) != (f0 > 0.0):
            lo = t
            hi = tn
            ok = 1
            break
        t = tn
        f = fn
    if ok == 1:
        for it in range(40):
            mid = 0.5 * (lo + hi)
            fm = program(p0 + d * (sgn * mid), n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                         thick, tri)
            if (fm > 0.0) == (f0 > 0.0):
                lo = mid
            else:
                hi = mid
        out[i] = p0 + d * (sgn * 0.5 * (lo + hi))
        status[i] = 0
        return
    # Newton to the nearest surface point
    p = p0
    for it in range(32):
        fp = program(p, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
        g = grad(p, 2.0e-5, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
        gl = wp.length_sq(g)
        if gl < 1.0e-12:
            break
        p = p - g * (fp / gl)
        if wp.abs(fp) < 1.0e-7:
            break
    out[i] = p
    fp = program(p, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    status[i] = 1
    if wp.abs(fp) > 1.0e-4:
        status[i] = 2


@wp.kernel
def k_normal(pts: wp.array(dtype=wp.vec3), h: float, out: wp.array(dtype=wp.vec3), n_prim: int,
             kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
             par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
             node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
             thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    i = wp.tid()
    out[i] = wp.normalize(grad(pts[i], h, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                               tri))


class Program:
    """build a primitive list on the host, then evaluate / project on the GPU"""

    def __init__(self):
        self.kind, self.op, self.k, self.par = [], [], [], []
        self.node_p, self.node_n, self.node_r, self.node_h = [], [], [], []
        self.shell_meshes, self.shell_thick, self.shell_tri = [], [], []
        self._dev = None
        self.names = []
        self._group = None
        self._next_gid = 0

    def begin_group(self, op=UNION, k=0.0, round_field=None):
        """the primitives added until end_group() combine among themselves first (each by its own op and k: give the
        members k = 0 for a hard union), then the group folds into the result by this op and k. round_field = (centre,
        axis scales (3,), d0, d1, r_out): the group's ROUND members' radius eases (smoothstep) from their k to
        r_out <= k as the distance from the centre, its axes scaled, runs from d0 to d1 (round_radius; one field per
        group)"""
        self._group = (self._next_gid, op, k)
        self._round_field = round_field
        self._next_gid += 1

    def end_group(self):
        self._group = None
        self._round_field = None

    def _add(self, kind, op, k, params, name, aabb=None):
        assert not (self.kind and self.kind[-1] == OFFSET), \
            f'{name!r} after the OFFSET: the coat envelope is the last primitive (offset_grid)'
        gop = op if self._group is None else self._group[1]      # the op the primitive's group folds by
        assert (kind == OFFSET) == (op == ENVELOPE) and (kind == OFFSET) == (gop == ENVELOPE), \
            "op 3 (ENVELOPE) belongs to the OFFSET alone: as a primitive's op and as its group's (begin_group)"
        assert gop != ROUND and (op != ROUND or (self._group is not None and self._group[1] == UNION and k > 0.0)), \
            f'{name!r}: ROUND (op 5) is a member op inside a UNION group, k its radius > 0 (a group never folds by it)'
        if self._group is not None and self.par and self.par[-1][20] == self._group[0]:
            assert (op == ROUND) == (self.op[-1] == ROUND) and (op != ROUND or k == self.k[-1]), \
                f'{name!r}: a ROUND group is ROUND members of one radius throughout (round_end)'
        p = np.zeros(NPAR, np.float32)
        p[:len(params)] = params
        if op == ROUND and getattr(self, '_round_field', None) is not None:
            c_, sc_, d0_, d1_, ro_ = self._round_field
            assert len(params) <= 8 and d1_ > d0_ >= 0.0 and 0.0 <= ro_ <= k, \
                f'{name!r}: a round_field needs par 8-17 free, d1 > d0 >= 0 and 0 <= r_out <= k (the culling bound)'
            p[8:18] = [1.0, c_[0], c_[1], c_[2], sc_[0], sc_[1], sc_[2], d0_, d1_, ro_]
        if aabb is not None:                # padded bounds for the culling (no bounds: never culled)
            lo, hi = aabb
            p[24:27] = np.asarray(lo) - 1e-4
            p[27:30] = np.asarray(hi) + 1e-4
        else:
            p[24:27] = -1e9
            p[27:30] = 1e9
        if self._group is not None:
            p[20], p[21], p[22] = self._group
        else:                               # a group of one: combines by its own op and k, as before groups
            p[20], p[21], p[22] = self._next_gid, op, k
            self._next_gid += 1
        self.kind.append(kind)
        self.op.append(op)
        self.k.append(k)
        self.par.append(p)
        self.names.append(name)
        self._dev = None
        return len(self.kind) - 1

    def ellipsoid(self, c, radii, axes=None, op=UNION, k=0.0, name=''):
        R = np.eye(3) if axes is None else np.asarray(axes, np.float64)
        R = R / np.linalg.norm(R, axis=0, keepdims=True)
        rm = float(np.max(radii))
        c = np.asarray(c, np.float64)
        return self._add(ELLIPSOID, op, k, list(c) + list(R[:, 0]) + list(R[:, 1]) + list(R[:, 2]) + list(radii), name,
                         aabb=(c - rm, c + rm))

    def roundcone(self, a, b, ra, rb, op=UNION, k=0.0, name=''):
        a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
        lo = np.minimum(a - ra, b - rb)
        hi = np.maximum(a + ra, b + rb)
        return self._add(ROUNDCONE, op, k, list(a) + list(b) + [ra, rb], name, aabb=(lo, hi))

    def sweep(self, points, normals, r0, a2=0.0, phi2=0.0, a3=0.0, phi3=0.0, a4=0.0, aspect=1.0, op=UNION, k=0.0,
              name=''):
        """points (N, 3) dense centreline; normals (N, 3) frame normals (theta = 0); the profile arrays per node
        (scalars broadcast)"""
        P = np.asarray(points, np.float64)
        N = len(P)
        bc = lambda v: np.broadcast_to(np.asarray(v, np.float64), (N,))
        start = len(self.node_p)
        for i in range(N):
            self.node_p.append(P[i])
            self.node_n.append(np.asarray(normals[i], np.float64))
        self.node_r += list(np.column_stack([bc(r0), bc(a2), bc(phi2), bc(aspect)]))
        # node_h.w at each chunk start (every 8 segments): the chunk's bounding radius about its middle node
        chunk_r = np.zeros(N)
        for j in range(0, N - 1, 8):
            jm = min(j + 4, N - 1)
            chunk_r[j] = float(np.max(np.linalg.norm(P[j:min(j + 9, N)] - P[jm], axis=1)))
        self.node_h += list(np.column_stack([bc(a3), bc(phi3), bc(a4), chunk_r]))
        rmax = float(np.max(bc(r0) * (1 + np.abs(bc(a2)) + np.abs(bc(a3)) + np.abs(bc(a4))) * np.maximum(1, bc(aspect))))
        return self._add(SWEEP, op, k, [start, N], name, aabb=(P.min(0) - rmax, P.max(0) + rmax))

    def torus(self, c, axis, R, r, op=UNION, k=0.0, name=''):
        c = np.asarray(c, np.float64)
        n = np.asarray(axis, np.float64)
        n = n / np.linalg.norm(n)
        return self._add(TORUS, op, k, list(c) + list(n) + [R, r], name, aabb=(c - (R + r), c + (R + r)))

    def revolve(self, profile, center, axis, op=UNION, k=0.0, name='', axis_tol=1.0e-7, check=True):
        """profile: a closed polygon (n, 2) of (r, y): r >= 0 its distance from the axis, y its height along it from
        the centre (a repeated closing point is dropped; either orientation), revolved about `axis` through `center`.
        Segments lying ON the axis (both ends at r <= axis_tol) close the polygon and are not surface: a lathe curve
        from the axis back to the axis is closed by its own last-to-first edge. check: the polygon must be simple
        (the crossing parity is only a sign for a simple polygon; an O(n^2) host test, skipped above 6000 points).
        Exact; dense profiles are cheap (every 8 segments are culled as a chunk)."""
        Pr = np.asarray(profile, np.float64).reshape(-1, 2).copy()
        if len(Pr) > 3 and np.allclose(Pr[0], Pr[-1], rtol=0.0, atol=1e-12):
            Pr = Pr[:-1]
        n = len(Pr)
        assert n >= 3, 'a REVOLVE profile needs at least three points'
        assert Pr[:, 0].min() >= -axis_tol, 'a REVOLVE profile lies on the r >= 0 side of its axis'
        Pr[:, 0] = np.maximum(Pr[:, 0], 0.0)
        Q = np.roll(Pr, -1, axis=0)
        E = Q - Pr
        L2 = (E * E).sum(1)
        assert L2.min() > 1e-24, 'a zero-length REVOLVE profile segment'
        if check and n <= 6000:
            bad = Program.profile_crossings(Pr)
            assert bad == 0, f'REVOLVE profile {name!r} crosses itself ({bad} segment pairs)'
        on_axis = (Pr[:, 0] <= axis_tol) & (Q[:, 0] <= axis_tol)
        start = len(self.node_p)
        self.node_p += list(np.column_stack([Pr, on_axis.astype(np.float64)]))
        self.node_n += list(np.column_stack([E, 1.0 / L2]))
        R4 = np.zeros((n, 4))
        H4 = np.zeros((n, 4))
        for j in range(0, n, 8):
            Vc = Pr[np.arange(j, min(j + 8, n) + 1) % n]        # the chunk's points, its last segment's end included
            cc = 0.5 * (Vc.min(0) + Vc.max(0))
            R4[j] = [cc[0], cc[1], float(np.linalg.norm(Vc - cc, axis=1).max()) * (1.0 + 1e-6) + 1e-9, 0.0]
            H4[j] = [Vc[:, 1].min(), Vc[:, 1].max(), Vc[:, 0].max(), 0.0]
        self.node_r += list(R4)
        self.node_h += list(H4)
        c = np.asarray(center, np.float64)
        a = np.asarray(axis, np.float64)
        a = a / np.linalg.norm(a)
        rmax, ylo, yhi = float(Pr[:, 0].max()), float(Pr[:, 1].min()), float(Pr[:, 1].max())
        e0, e1 = c + a * ylo, c + a * yhi
        ext = rmax * np.sqrt(np.clip(1.0 - a * a, 0.0, 1.0))   # a disc of radius rmax about a, along each world axis
        return self._add(REVOLVE, op, k, [start, n] + list(c) + list(a) + [rmax, ylo, yhi], name,
                         aabb=(np.minimum(e0, e1) - ext, np.maximum(e0, e1) + ext))

    @staticmethod
    def profile_crossings(P):
        """properly crossing segment pairs of the closed polygon P (n, 2) (0 = simple; touching and collinear
        overlaps are not counted)"""
        P = np.asarray(P, np.float64)
        n = len(P)
        A, B = P, np.roll(P, -1, axis=0)

        def orient(p, q, s):
            return (q[..., 0] - p[..., 0]) * (s[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (s[..., 0] - p[..., 0])
        bad = 0
        j = np.arange(n)[None, :]
        for s0 in range(0, n, 256):
            i = np.arange(s0, min(s0 + 256, n))[:, None]
            Ai, Bi, Aj, Bj = A[i], B[i], A[j], B[j]
            hit = (orient(Ai, Bi, Aj) * orient(Ai, Bi, Bj) < 0) & (orient(Aj, Bj, Ai) * orient(Aj, Bj, Bi) < 0)
            bad += int((hit & (j > i)).sum())
        return bad

    @staticmethod
    def section_core(polygon, rho):
        """a PSWEEP section's CORE: the sharp-cornered polygon (n, 2) offset inward by rho (each edge's line moved rho
        inward, neighbours intersected). Offset by rho again, as the PSWEEP's surface is, the core gives back the
        polygon's edges with its convex corners rounded by rho and its reflex corners sharp. Refused where rho makes an
        edge vanish or turn, or the core cross itself"""
        P = np.asarray(polygon, np.float64).reshape(-1, 2)
        if len(P) > 3 and np.allclose(P[0], P[-1], rtol=0.0, atol=1e-12):
            P = P[:-1]
        assert rho >= 0.0, 'section_core: rho >= 0'
        if rho == 0.0:
            return P.copy()
        E = np.roll(P, -1, axis=0) - P
        area2 = float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))
        nin = np.sign(area2) * np.column_stack([-E[:, 1], E[:, 0]]) / np.linalg.norm(E, axis=1)[:, None]
        na, nb = np.roll(nin, 1, axis=0), nin           # the inward normals of the edges into and out of each vertex
        cab = np.sum(na * nb, axis=1)
        assert cab.min() > -0.99, 'section_core: a corner turns back on itself'
        C = P + rho * (na + nb) / (1.0 + cab)[:, None]
        assert (np.sum((np.roll(C, -1, axis=0) - C) * E, axis=1) > 0.0).all() and Program.profile_crossings(C) == 0, \
            f'section_core: rho {rho} is too large for this polygon (an edge vanishes or the core crosses itself)'
        return C

    @staticmethod
    def psweep_bound(P, T, Nn, S, sc, tw, kk, rho):
        """the PSWEEP's Lipschitz terms per segment, from its end values alone (patches/sdf_psweep.md). With u in
        [0, 1] along segment j, the field before its division obeys |grad|^2 <= 1 + (B_j / (gam_j - r curv_j))^2 at a
        distance r from the centreline. B_j bounds the section's speed across the foot point's plane per unit length:
        its own motion (key blend, scale, twist), the frame's turn about the axis, and the segment's slant against the
        interpolated tangent. gam_j bounds e_j . T(u) from below, curv_j bounds |dT/du| / L_j from above. A dict: B,
        B_own (the section's own motion alone), omega (the frame's turn per unit length), gam, curv, reach (the core's
        farthest point from the centreline, plus rho)"""
        K, M = S.shape[:2]
        E = P[1:] - P[:-1]
        L = np.linalg.norm(E, axis=1)
        e = E / L[:, None]
        dot = lambda a, b: np.einsum('ij,ij->i', a, b)
        nrm = lambda a: np.linalg.norm(a, axis=1)
        T0, T1, n0, n1 = T[:-1], T[1:], Nn[:-1], Nn[1:]
        cT = 0.5 * nrm(T0 + T1)                                     # the least |(1 - u) T0 + u T1|
        cn = 0.5 * nrm(n0 + n1)
        tau = nrm(T1 - T0) / cT                                     # |dT/du|
        aT = 2.0 * np.arcsin(np.minimum(0.5 * nrm(T1 - T0), 1.0))   # the angles T and the normal turn through
        an = 2.0 * np.arcsin(np.minimum(0.5 * nrm(n1 - n0), 1.0))
        nu = (np.abs(dot(n0, T1) + dot(n1, T0)) / 4.0 + np.abs(dot(n0, T0)) + np.abs(dot(n1, T1))) / cT   # |n~ . T|
        assert (cn > nu).all(), 'PSWEEP: a frame normal turns onto the axis within a segment'
        dn = n1 - n0
        beta = np.arcsin(np.minimum(nu / cn, 1.0))
        # the frame's turn about T per unit u, |n' . b| = |n~' . b - (T' . b)(n~ . T)| / |n~ - T (n~ . T)|
        om = (np.minimum(np.abs(dot(dn, np.cross(T0, n0))), np.abs(dot(dn, np.cross(T1, n1))))
              + nrm(dn) * (aT + an + beta) + tau * nu) / np.sqrt(cn ** 2 - nu ** 2)
        R = np.zeros((len(L), M))
        V = np.zeros((len(L), M))
        Vo = np.zeros((len(L), M))
        for j in range(len(L)):
            ka, kb = float(kk[j]), float(kk[j + 1])
            klo, khi = min(ka, kb), max(ka, kb)
            if K == 1:
                Bm, dK = np.abs(S[0]), np.zeros((M, 2))
            else:
                def blend(kq):
                    a = min(int(kq), K - 2)
                    return S[a] + (S[a + 1] - S[a]) * (kq - a)
                # the blended core's largest |x|, |y| per point over the segment (at its ends or at a key between), and
                # the largest change per unit key position
                Bm = np.max(np.abs(np.stack([blend(ka), blend(kb)] + [S[i] for i in range(K) if klo < i < khi])), 0)
                dK = np.max(np.stack([np.abs(S[a + 1] - S[a])
                                      for a in range(min(int(klo), K - 2), min(int(khi), K - 2) + 1)]), axis=0)
            Sm = np.maximum(sc[j], sc[j + 1])
            R[j] = np.linalg.norm(Bm * Sm, axis=1)                    # each core point's reach over the segment
            Vo[j] = abs(tw[j + 1] - tw[j]) * R[j] + np.linalg.norm(np.abs(sc[j + 1] - sc[j]) * Bm
                                                                     + Sm * abs(kb - ka) * dK, axis=1)
            V[j] = Vo[j] + om[j] * R[j]
        # the slant: T(u) runs along the great circle from T0 to T1, so its angle to e is largest at an end
        gam = np.minimum(dot(e, T0), dot(e, T1))
        slant = np.maximum(nrm(np.cross(e, T0)), nrm(np.cross(e, T1)))
        return dict(B=V.max(1) / L + slant, B_own=Vo.max(1) / L, omega=om / L, slant=slant, gam=gam, curv=tau / L,
                    reach=float(R.max()) + rho)

    @staticmethod
    def psweep_band_ok(P, T, rho_max):
        """the band (radius rho_max about the centreline) is whole: no end plane cuts the band disc of a node or of a
        segment's middle, and centreline points more than pi rho_max apart along it are more than 2 rho_max apart"""
        Tm = T[:-1] + T[1:]
        C = np.concatenate([P, 0.5 * (P[:-1] + P[1:])])
        Ta = np.concatenate([T, Tm / np.linalg.norm(Tm, axis=1, keepdims=True)])
        tol = 1e-9 + 1e-6 * (float(np.abs(P).max()) + rho_max)
        for pe, te, sg in ((P[0], T[0], -1.0), (P[-1], T[-1], 1.0)):
            side = sg * ((C - pe) @ te) + rho_max * np.linalg.norm(np.cross(Ta, te), axis=1)
            if side.max() > tol:
                return False, f'an end plane cuts the band (by {side.max():.3g} m)'
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        if len(P) <= 4096:
            for i0 in range(0, len(P), 256):
                i = np.arange(i0, min(i0 + 256, len(P)))
                far = np.abs(s[i, None] - s[None, :]) > np.pi * rho_max
                if (far & (np.linalg.norm(P[i, None] - P[None, :], axis=2) <= 2.0 * rho_max)).any():
                    return False, 'the band overlaps itself (the centreline comes back within two band radii)'
        return True, ''

    def psweep(self, points, sections, rho=0.0, key=0.0, scale=1.0, twist=0.0, normal=None, band=None, op=UNION,
               k=0.0, name='', check=True):
        """a swept POLYGON (kind 7). points (N, 3): the centreline, dense as SWEEP's (the foot point and the frame
        interpolate between nodes, and each node's turn raises the divisor); its node tangents are its own (the
        three-point rule, stored in node_h.xyz), so the ends are second order. sections (K, M, 2) or (M, 2): the key
        sections' CORE polygons in metres, x along the frame normal and y along t x n, point i of every key blended with
        point i of the next (simple, one orientation; a sharp-cornered section's core is section_core(polygon, rho)),
        offset by rho. Per node (a scalar broadcasts): key in 0..K-1 (keys floor(key) and the next, blended at its
        fraction); scale: one number, (su, sv), (N,) isotropic per node (N > 2) or (N, 2), all > 0, multiplying the
        core's x and y (rho kept); twist in radians (the section turned from the normal toward t x n). normal: None (a
        rotation-minimising frame from the world axis least along the first tangent), one start normal (carried by the
        same frame) or (N, 3) per node. The ends are flat, the planes through the end nodes normal to the end tangents,
        rounded by rho. The kernel divides the exact 2D distance by par[6], a bound on its Lipschitz factor within
        par[7] of the centreline: the band, the reach plus `band` (by default the reach again, halved down to 0 until
        the checks pass; an explicit band is refused instead). check: the keys and their blends simple (O(M^2)). Two
        host checks are skipped above a size: the crossing tests of the keys and their blends above 4000 points per
        key, and the band's self-overlap test above 4096 nodes"""
        f32 = lambda a: np.asarray(a, np.float64).astype(np.float32).astype(np.float64)      # what the kernel reads
        P = f32(np.asarray(points, np.float64).reshape(-1, 3))
        N = len(P)
        assert N >= 2 and np.linalg.norm(np.diff(P, axis=0), axis=1).min() > 1e-9, \
            'a PSWEEP centreline: two nodes or more, no zero-length segment'
        S = np.asarray(sections, np.float64)
        S = S[None] if S.ndim == 2 else S
        assert S.ndim == 3 and S.shape[2] == 2, 'PSWEEP sections: (K, M, 2) or (M, 2)'
        if S.shape[1] > 3 and np.allclose(S[:, 0], S[:, -1], rtol=0.0, atol=1e-12):
            S = S[:, :-1]                                           # a repeated closing point
        S = f32(S)
        K, M = S.shape[:2]
        assert M >= 3, 'a PSWEEP section needs three points'
        kq = f32(np.broadcast_to(np.asarray(key, np.float64), (N,)))
        sc = np.asarray(scale, np.float64)
        sc = f32(np.broadcast_to(np.column_stack([sc, sc]) if sc.shape == (N,) and N != 2 else sc, (N, 2)))
        tw = f32(np.broadcast_to(np.asarray(twist, np.float64), (N,)))
        assert sc.min() > 0.0 and rho >= 0.0, 'PSWEEP: scales > 0, rho >= 0'
        assert kq.min() >= 0.0 and kq.max() <= K - 1, f'PSWEEP: key positions lie in 0..{K - 1}'
        # the node tangents, stored in node_h.xyz for the kernel to interpolate: the three-point rule on the chord
        # lengths, central for even spacing and second order at the ends (node_tangent's one-sided chord would tilt
        # a flat end by half a node's turn: 54 um at a 16 mm reach on b02's arc); then the frame normals
        h = np.linalg.norm(np.diff(P, axis=0), axis=1)
        if N == 2:
            T = np.tile((P[1] - P[0]) / h[0], (2, 1))
        else:
            h0, h1 = h[:-1, None], h[1:, None]
            T = np.zeros((N, 3))
            T[1:-1] = (h0 ** 2 * (P[2:] - P[1:-1]) + h1 ** 2 * (P[1:-1] - P[:-2])) / (h0 * h1 * (h0 + h1))
            a, b = h[0], h[1]
            T[0] = -(2 * a + b) / (a * (a + b)) * P[0] + (a + b) / (a * b) * P[1] - a / (b * (a + b)) * P[2]
            a, b = h[-1], h[-2]
            T[-1] = (2 * a + b) / (a * (a + b)) * P[-1] - (a + b) / (a * b) * P[-2] + a / (b * (a + b)) * P[-3]
        Ts = f32(T / np.linalg.norm(T, axis=1, keepdims=True))     # stored, as the kernel reads them
        T = Ts / np.linalg.norm(Ts, axis=1, keepdims=True)          # their directions, for the host's frame and checks
        nv = None if normal is None else np.asarray(normal, np.float64)
        if nv is None or nv.shape == (3,):
            n = np.eye(3)[int(np.argmin(np.abs(T[0])))] if nv is None else nv
            n = n - T[0] * float(n @ T[0])
            assert np.linalg.norm(n) > 1e-6, 'the PSWEEP start normal lies along the first tangent'
            Nn = np.zeros((N, 3))
            Nn[0] = n / np.linalg.norm(n)
            for j in range(1, N):                   # parallel transport: the least rotation taking T[j - 1] to T[j]
                ax, ca = np.cross(T[j - 1], T[j]), float(T[j - 1] @ T[j])
                sa = float(np.linalg.norm(ax))
                n = Nn[j - 1]
                if sa > 1e-12:
                    ax = ax / sa
                    n = n * ca + np.cross(ax, n) * sa + ax * float(ax @ n) * (1.0 - ca)
                n = n - T[j] * float(n @ T[j])
                Nn[j] = n / np.linalg.norm(n)
        else:
            Nn = nv.reshape(N, 3) - T * np.sum(nv.reshape(N, 3) * T, axis=1, keepdims=True)
            assert np.linalg.norm(Nn, axis=1).min() > 1e-6, 'a PSWEEP normal lies along its node tangent'
            Nn = Nn / np.linalg.norm(Nn, axis=1, keepdims=True)
        Nn = f32(Nn)
        # the keys: one orientation, no zero edge, simple, and simple blended (the parity is a sign only for a simple
        # polygon; a positive scale and a turn keep it simple)
        area2 = lambda Q: np.sum(Q[..., 0] * np.roll(Q[..., 1], -1, axis=-1)
                                 - np.roll(Q[..., 0], -1, axis=-1) * Q[..., 1], axis=-1)       # twice the signed area
        a2 = area2(S)
        assert (a2 > 0).all() or (a2 < 0).all(), 'PSWEEP keys: one orientation, none of zero area'
        Ek = np.roll(S, -1, axis=1) - S
        L2k = (Ek * Ek).sum(2)
        assert L2k.min() > 1e-24, 'a zero-length PSWEEP section edge'
        for i in range(K - 1):
            for wq in (0.25, 0.5, 0.75):
                Sb = S[i] + (S[i + 1] - S[i]) * wq
                assert area2(Sb) * a2[0] > 0.0 and (not check or M > 4000 or Program.profile_crossings(Sb) == 0), \
                    f'PSWEEP {name!r}: keys {i} and {i + 1} blended at {wq} collapse or cross themselves'
        if check and M <= 4000:
            for i in range(K):
                assert Program.profile_crossings(S[i]) == 0, f'PSWEEP {name!r}: key {i} crosses itself'
        # the divisor, for the widest band the checks pass
        bd = Program.psweep_bound(P, T, Nn, S, sc, tw, kq, rho)
        reach = bd['reach']
        for b in ([float(band)] if band is not None else [reach, 0.5 * reach, 0.25 * reach, 0.0]):
            H = bd['gam'] - (reach + b) * bd['curv']
            ok, why = bool(H.min() >= 0.2), f'the centreline turns too sharply for the band (H {H.min():.3f} < 0.2)'
            if ok:
                ok, why = Program.psweep_band_ok(P, T, reach + b)
            if ok:
                break
        assert ok, f'PSWEEP {name!r}: {why}, band {b:.4g} m beyond the reach {reach:.4g} m'
        D = max(1.0, float(np.sqrt(1.0 + (bd['B'] / H) ** 2).max()))
        D32 = np.float32(D)
        if float(D32) < D:
            D32 = np.nextafter(D32, np.float32(np.inf))             # the stored divisor rounds up, never down
        cs = len(self.node_p)
        self.node_p += list(P)
        self.node_n += list(Nn)
        self.node_r += list(np.column_stack([sc, tw, kq]))
        chunk_r = np.zeros(N)                                       # node_h.w at each chunk start, as SWEEP's
        for j in range(0, N - 1, 8):
            chunk_r[j] = float(np.max(np.linalg.norm(P[j:min(j + 9, N)] - P[min(j + 4, N - 1)], axis=1))) * \
                (1.0 + 1e-6) + 1e-9
        self.node_h += list(np.column_stack([Ts, chunk_r]))
        ks = len(self.node_p)
        for i in range(K):
            self.node_p += list(np.column_stack([S[i], np.zeros(M)]))
            self.node_n += list(np.column_stack([Ek[i], 1.0 / L2k[i]]))
            R4, H4 = np.zeros((M, 4)), np.zeros((M, 4))
            pad = 1e-6 * float(np.abs(S[i]).max()) + 1e-9
            for j in range(0, M, 8):
                Vc = S[i][np.arange(j, min(j + 8, M) + 1) % M]     # the chunk's points, its last segment's end too
                cc = 0.5 * (Vc.min(0) + Vc.max(0))
                R4[j] = [cc[0], cc[1], float(np.linalg.norm(Vc - cc, axis=1).max()) * (1.0 + 1e-6) + 1e-9, 0.0]
                H4[j] = [Vc[:, 1].min() - pad, Vc[:, 1].max() + pad, Vc[:, 0].max() + pad, 0.0]
            self.node_r += list(R4)
            self.node_h += list(H4)
        assert ks + K * M < 2 ** 24, 'PSWEEP node indices ride in float32 par: they must stay below 2^24'
        return self._add(PSWEEP, op, k, [cs, N, ks, M, K, rho, float(D32), reach + b], name,
                         aabb=(P.min(0) - reach, P.max(0) + reach))

    def roundbox(self, c, half, r=0.0, axes=None, op=UNION, k=0.0, name=''):
        """a box with rounded edges and corners (kind 8, exact): centre c, axes (3 x 3, columns = the local axes,
        orthonormal), half extents `half` (the rounded box's own), corner radius 0 <= r <= the least half extent"""
        R = np.eye(3) if axes is None else np.asarray(axes, np.float64)
        R = R / np.linalg.norm(R, axis=0, keepdims=True)
        assert np.abs(R.T @ R - np.eye(3)).max() < 1e-6, 'ROUNDBOX axes: orthonormal columns'
        h = np.asarray(half, np.float64).reshape(3)
        assert h.min() > 0.0 and 0.0 <= r <= h.min(), 'ROUNDBOX: half extents > 0 and 0 <= r <= the least of them'
        c = np.asarray(c, np.float64)
        ext = np.abs(R) @ h                                         # the box's corners along each world axis
        return self._add(ROUNDBOX, op, k, list(c) + list(R[:, 0]) + list(R[:, 1]) + list(R[:, 2]) + list(h) + [r],
                         name, aabb=(c - ext, c + ext))

    def shell(self, V, F, half_thickness, op=UNION, k=0.0, maxd=0.05, name='', continuous=False):
        """SHELL (kind 3): the patch mesh (V, F) thickened by a per-vertex half-thickness. continuous=True (opt-in) is
        sd_shell_c, the least over the faces within reach of |p - cp_f| - ht(cp_f): continuous where the closest point
        jumps across a curled sheet with a varying half-thickness (the default rule steps there), at the cost of one
        BVH sphere query of radius (the default value + the largest half-thickness) per evaluation and a closest
        point per face it returns. Off, the member's parameters are exactly as before (par[3], par[4] stay 0)"""
        V = np.asarray(V, np.float32)
        F = np.asarray(F, np.int32)
        m = wp.Mesh(points=wp.array(V, dtype=wp.vec3), indices=wp.array(F.ravel(), dtype=wp.int32))
        tri_base = sum(len(t) for t in self.shell_tri)
        th_base = sum(len(t) for t in self.shell_thick)
        self.shell_meshes.append(m)
        self.shell_thick.append(np.broadcast_to(np.asarray(half_thickness, np.float32), (len(V),)).copy())
        self.shell_tri.append((F.ravel() + th_base).astype(np.int32))
        hmax = float(np.max(self.shell_thick[-1]))
        params = [len(self.shell_meshes) - 1, tri_base, maxd]
        if continuous:
            params += [1.0, hmax]         # par[3] the flag, par[4] the reach's half-thickness (float32 exact)
        return self._add(SHELL, op, k, params, name, aabb=(V.min(0) - hmax, V.max(0) + hmax))

    def offset_grid(self, origin, cell, values, g, scale=1.0, name='coat'):
        """the COAT, the LAST primitive: everything added so far becomes its envelope, d <- (d - scale c) / (1 + scale
        g). values (nx, ny, nz): coat depths in metres, values[i, j, k] at origin + cell (i, j, k), sampled trilinearly
        with the point clamped to the grid's box; g bounds |grad c| of that interpolant (coat.lipschitz_bound of the
        float32 values: the division needs it to keep the field a distance bound). scale 0 is the bare skin, 1 the
        coat, about 0.3 the coat pressed under a hat; k = scale g is baked into the program, so another scale is
        another program. A group of its own (op ENVELOPE, never culled). The values ride on the end of the shell
        thickness array (no new kernel arguments), their base index in float32 par, so it must stay below 2^24"""
        assert self._group is None, 'offset_grid outside begin_group/end_group: the envelope is a group of its own'
        assert self.kind, 'offset_grid needs a skin before it'
        V = np.array(values, dtype=np.float32, order='C')      # a copy: g and the checks hold for what is stored
        assert V.ndim == 3 and min(V.shape) >= 2 and np.isfinite(V).all(), 'values: a finite (nx, ny, nz) grid, n >= 2'
        assert cell > 0.0 and scale >= 0.0, 'cell > 0 and scale >= 0'
        # a cheap NECESSARY check of g: the interpolant's gradient reaches every grid edge's slope (the sufficient
        # bound is coat.lipschitz_bound's)
        V64 = V.astype(np.float64)
        steep = max(float(np.abs(np.diff(V64, axis=a)).max()) for a in range(3)) / cell
        assert g >= steep * (1.0 - 1.0e-6), f'g {g:.4f} is below the steepest grid edge ({steep:.4f}): not a bound'
        base = sum(len(t) for t in self.shell_thick)
        assert base < 2 ** 24, "the grid's base index rides in float32 par: it must stay below 2^24"
        self.shell_thick.append(V.ravel())
        nx, ny, nz = V.shape
        o = np.asarray(origin, np.float64)
        return self._add(OFFSET, ENVELOPE, float(scale * g), [base, nx, ny, nz, o[0], o[1], o[2], 1.0 / cell, scale],
                         name)

    def device(self):
        if self._dev is None:
            assert OFFSET not in self.kind[:-1], 'the OFFSET (the coat envelope) must be the last primitive'
            f32 = lambda a: wp.array(np.asarray(a, np.float32), dtype=wp.float32)
            v3 = lambda a: wp.array(np.asarray(a, np.float32).reshape(-1, 3) if len(a) else np.zeros((1, 3),
                                    np.float32), dtype=wp.vec3)
            v4 = lambda a: wp.array(np.asarray(a, np.float32).reshape(-1, 4) if len(a) else np.zeros((1, 4),
                                    np.float32), dtype=wp.vec4)
            self._dev = dict(
                n=len(self.kind),
                kind=wp.array(np.asarray(self.kind, np.int32), dtype=wp.int32),
                op=wp.array(np.asarray(self.op, np.int32), dtype=wp.int32),
                k=f32(self.k), par=f32(np.concatenate(self.par)),
                node_p=v3(self.node_p), node_n=v3(self.node_n), node_r=v4(self.node_r), node_h=v4(self.node_h),
                shells=wp.array(np.asarray([m.id for m in self.shell_meshes] or [0], np.uint64), dtype=wp.uint64),
                thick=f32(np.concatenate(self.shell_thick) if self.shell_thick else [0.0]),
                tri=wp.array(np.concatenate(self.shell_tri) if self.shell_tri else np.zeros(3, np.int32),
                             dtype=wp.int32))
        return self._dev

    def _args(self):
        d = self.device()
        return [d['n'], d['kind'], d['op'], d['k'], d['par'], d['node_p'], d['node_n'], d['node_r'], d['node_h'],
                d['shells'], d['thick'], d['tri']]

    def eval(self, pts):
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.float32)
        wp.launch(k_eval, dim=len(P), inputs=[P, out] + self._args())
        return out.numpy()

    def project(self, pts, dirs, maxd=0.05):
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        D = wp.array(np.asarray(dirs, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.vec3)
        st = wp.zeros(len(P), dtype=wp.int32)
        wp.launch(k_project, dim=len(P), inputs=[P, D, float(maxd), out, st] + self._args())
        return out.numpy().astype(np.float64), st.numpy()

    def normals(self, pts, h=2.0e-5):
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.vec3)
        wp.launch(k_normal, dim=len(P), inputs=[P, float(h), out] + self._args())
        return out.numpy().astype(np.float64)
