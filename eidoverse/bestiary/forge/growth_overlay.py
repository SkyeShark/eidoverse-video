"""GROWTHS OVER A FINISHED BASE (the crystal beetle's round, 10-29): forge/growth.py's crystals planned on a base whose
skin is already baked and painted, dressed in two passes that name no species.

Why not the octopus's way (the crystals as voxel strokes in the sculpt, baked with the skin): a base like the stag beetle
bakes per master (a voxel macro field of its creased limit, a micro relief composed per sub-sample, AO and cavity as rays
on the limit itself: work/bestiary/beetle/b07_bake.py), so a crystal's stroke has no shared field to join; and a growth
LOOK should change a base's texels only where it grows (as calib's frozen convexity record keeps a look from re-measuring
its base). So the base's own bake and maps stay as they are, and these passes add the growths:

  growths_drivers  THE GROWTHS MESH's bake, analytic. growth.low_mesh's trimmed prisms ARE the crystals' faces (the
                   octopus's voxel bake rounds them by a voxel; these stay exact: hard chitin's crisp edges by
                   construction), so a texel's low point is its high point; AO and cavity are cosine rays against every
                   crystal (each a convex polytope: its side, tip and base planes, an exact ray clip, ray_prism) and the
                   base's skin (its limit as a mesh). Then growth.run_growths (the octopus's look code, unchanged: one draw
                   per facet, the tarnish, edge wear, the root gradient, the growth steps) makes its maps.
  skin_overlay     THE FEET in the base's own texels: the GROWTH pack baked into the skin. Per covered texel within reach
                   of a crystal, at the base's own high point (its bake's position) and on its composed normal:
                     * HIDDEN under a crystal: the crystal's surface there (the growths mesh covers it, so a slit at the
                       junction shows crystal, never bare skin);
                     * THE DRUSE: a narrow ring of small crystals crowding each crystal's foot (REF R11's self-occluding
                       roots; real druse on its matrix: the small crystals carpet the substrate and the large ones rise
                       out of them), Worley cells, each a steep facet of its own tilt, glossy (the glints a drusy matrix
                       shows), darker than the crystal (in each other's shade) and dark in its crevices, the ring's edge
                       broken cell by cell (on the ice families it reads as rime: their colour carries the frost layer);
                     * THE BREACH: a STAR CRACK round each piece (displacive growth: a crystal growing inside a hard
                       layer cracks it, as salts spall stone and selenite blades crack clay): kinked radial cracks from
                       the piece's footprint plus broken concentric arcs, tapering, darkened, their walls tilted toward
                       their line (a groove) with a paler lip (the fracture's inner layer), and the shell risen a little
                       round the emergence;
                     * the crystals' OCCLUSION on the skin (the same polytope rays): the contact darkening;
                   and the GROWTH pack: R the crystal's share (the druse, the hidden texels: the runtime holds the skin's
                   own terms off them), G iridescence, B the emissive mask (the druse's, faint; the cracks' when
                   crack_glow > 0), A the pulse phase (the nearest crystal's random).
                   Looks tried on the way (the crystal builder's renders, 10-30): Worley flakes with glowing cracks read
                   as a glowing hexagonal net round a lavender foam; smooth meandering radials read as the legs of a
                   tick on the elytra. The star crack and the narrow glossy druse are what read as crystal breaking out
                   of chitin.
The texel frames are the engine's own (material.low_at: the shader's interpolated TBN), so every composed normal decodes
exactly. Units: the base's (metres; the beetle at x10).
"""
import numpy as np
import warp as wp

from . import growth as GR
from . import material as M
from . import proc

wp.set_module_options({'enable_backward': False})    # forward-only kernels (as the forge's)

NO_HIT = wp.constant(1.0e9)


# ----------------------------------------------------------------------------------------------------- ray clips
@wp.func
def ray_prism(o: wp.vec3, d: wp.vec3, a: wp.vec3, b: wp.vec3, R: float, h: float, spin: float, sides: int,
              tmax: float):
    """the entry distance of the ray o + t d (t in [0, tmax]) into growth.py's prism (sd_prism's solid: the N side
    planes at the apothem, the base plane, the tip's N planes or a flat top), NO_HIT when it misses. Cyrus-Beck on the
    convex polytope"""
    ax = b - a
    L = wp.length(ax)
    if L < 1.0e-9:
        return NO_HIT
    n = ax / L
    e1 = GR.onb_e1(n)
    e2 = GR.onb_e2(n)
    u = e1 * wp.cos(spin) + e2 * wp.sin(spin)
    v = wp.cross(n, u)
    A = R * wp.cos(3.141592653589793 / float(sides))
    hh = wp.clamp(h, 0.0, L)
    q = o - a
    t0 = float(0.0)
    t1 = tmax
    # the base: -n . q <= 0
    den = -wp.dot(n, d)
    num = wp.dot(n, q)
    if wp.abs(den) < 1.0e-12:
        if num < 0.0:
            return NO_HIT
    elif den > 0.0:
        t1 = wp.min(t1, num / den)
    else:
        t0 = wp.max(t0, num / den)
    sector = 6.283185307179586 / float(sides)
    for k in range(sides):
        th = float(k) * sector
        m = u * wp.cos(th) + v * wp.sin(th)
        # the side: m . q <= A
        den = wp.dot(m, d)
        num = A - wp.dot(m, q)
        if wp.abs(den) < 1.0e-12:
            if num < 0.0:
                return NO_HIT
        elif den > 0.0:
            t1 = wp.min(t1, num / den)
        else:
            t0 = wp.max(t0, num / den)
        if hh > 1.0e-9:
            # the tip face k: hh (m . q) + A (n . q) <= A L
            w = m * hh + n * A
            den = wp.dot(w, d)
            num = A * L - wp.dot(w, q)
            if wp.abs(den) < 1.0e-12:
                if num < 0.0:
                    return NO_HIT
            elif den > 0.0:
                t1 = wp.min(t1, num / den)
            else:
                t0 = wp.max(t0, num / den)
        if t0 > t1:
            return NO_HIT
    if hh <= 1.0e-9:
        den = wp.dot(n, d)
        num = L - wp.dot(n, q)
        if wp.abs(den) < 1.0e-12:
            if num < 0.0:
                return NO_HIT
        elif den > 0.0:
            t1 = wp.min(t1, num / den)
        else:
            t0 = wp.max(t0, num / den)
    if t0 > t1:
        return NO_HIT
    return t0


@wp.func
def cos_dir(n: wp.vec3, u1: float, u2: float):
    """a cosine-weighted direction about the unit n (Malley: a disc sample lifted onto the hemisphere)"""
    r = wp.sqrt(u1)
    ph = 6.283185307179586 * u2
    t = GR.onb_e1(n)
    s = GR.onb_e2(n)
    return wp.normalize(t * (r * wp.cos(ph)) + s * (r * wp.sin(ph)) + n * wp.sqrt(wp.max(0.0, 1.0 - u1)))


@wp.func
def occluded(o: wp.vec3, d: wp.vec3, tmax: float, grid: wp.uint64, rq: float, gA: wp.array(dtype=wp.vec3),
             gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4), own: int, skin: wp.uint64, use_skin: int):
    """True when the ray meets a crystal (but `own`: a convex crystal cannot shade its own faces' outward rays) or the
    skin within tmax"""
    qy = wp.hash_grid_query(grid, o, tmax + rq)
    i = int(0)
    while wp.hash_grid_query_next(qy, i):
        if i == own:
            continue
        q = gQ[i]
        if q[3] < 0.5:
            continue
        if ray_prism(o, d, gA[i], gB[i], q[0], q[1], q[2], int(q[3]), tmax) < tmax:
            return True
    if use_skin != 0:
        sq = wp.mesh_query_ray(skin, o, d, tmax)
        if sq.result:
            return True
    return False


@wp.func
def occlusion(p: wp.vec3, n: wp.vec3, nray: int, tmax: float, seed: int, tid: int, grid: wp.uint64, rq: float,
              gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4), own: int,
              skin: wp.uint64, use_skin: int, eps: float):
    """the share of nray cosine rays (stratified, hashed per texel) that stay open over tmax"""
    open_ = float(0.0)
    o = p + n * eps
    for k in range(nray):
        u1 = (float(k) + proc.u01(proc.hash3i(tid, k, 1, seed))) / float(nray)
        u2 = proc.u01(proc.hash3i(tid, k, 2, seed))
        dd = cos_dir(n, u1, u2)
        if not occluded(o, dd, tmax, grid, rq, gA, gB, gQ, own, skin, use_skin):
            open_ = open_ + 1.0
    return open_ / float(nray)


# ----------------------------------------------------------------------------------------------------- the growths mesh
@wp.kernel
def k_growth_drivers(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3),
                     lnrm: wp.array(dtype=wp.vec3), ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4),
                     grid: wp.uint64, rq: float, gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3),
                     gQ: wp.array(dtype=wp.vec4), skin: wp.uint64, n_ao: int, ao_r: float, n_cav: int, cav_r: float,
                     eps: float, seed: int, fam_code: int, o_nrm: wp.array(dtype=wp.vec4), o_ao: wp.array(dtype=float),
                     o_cav: wp.array(dtype=float), o_pos: wp.array(dtype=wp.vec3), o_mat: wp.array(dtype=wp.int32)):
    """per atlas texel: the low's point is the crystal's face (exact); AO and cavity rays from the first covered
    sub-sample (the face's own crystal skipped, attr[0] = its instance index), the normal +z in tangent space"""
    tid = wp.tid()
    x = tid % size
    y = tid // size
    inv = 1.0 / float(ss)
    hits = int(0)
    for i in range(ss):
        for j in range(ss):
            if hits > 0:
                continue
            lo = M.low_at(uv_mesh, float(x) + (float(i) + 0.5) * inv, float(y) + (float(j) + 0.5) * inv, lpos, lnrm,
                          ltan, lattr)
            if lo.ok == 0:
                continue
            own = int(lo.attr[0] + 0.5)
            o_ao[tid] = occlusion(lo.p, lo.n, n_ao, ao_r, seed, tid, grid, rq, gA, gB, gQ, own, skin, 1, eps)
            o_cav[tid] = occlusion(lo.p, lo.n, n_cav, cav_r, seed + 7, tid, grid, rq, gA, gB, gQ, own, skin, 1, eps)
            o_pos[tid] = lo.p
            o_nrm[tid] = wp.vec4(0.0, 0.0, 1.0, 1.0)
            o_mat[tid] = fam_code
            hits = 1


def growths_drivers(lm, inst, skin_V, skin_F, n_ao=32, ao_r=0.0125, n_cav=12, cav_r=0.0025, eps=2.0e-5, seed=4107,
                    ss=2, log=print):
    """the growths mesh's DRIVERS, analytic (the module notes): lm = growth.low_mesh(...) with N and TAN (bake.low_frames)
    and face_crystal; inst = growth.instances(cr) (every crystal, the occluders); skin = the base's limit (V, F) as the
    skin occluder. Returns image-order drivers for growth.run_growths: normal (+z, coverage in w), ao, cavity, height 0,
    curvature 0, position, mat (the family id at full weight: voxel.lab_pack's id0 | 255 << 16)"""
    import time
    t0 = time.time()
    size = int(lm['size'])
    F = np.asarray(lm['F'], np.int64)
    attr = np.zeros((len(lm['V']), 4))
    vc = np.zeros(len(lm['V']), np.int64)
    vc[F.ravel()] = np.repeat(np.asarray(lm['face_crystal'], np.int64), 3)
    # the crystal entry -> its instance index (instances() drops the carves; low_mesh's face_crystal counts entries)
    attr[:, 0] = np.asarray(lm['inst_of'], np.int64)[vc] if 'inst_of' in lm else vc
    uvm = M.uv_bvh(F, lm['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(lm['V'], F, lm['N'], lm['TAN'], attr)
    grid, rq, gA, gB, gQ, gZ = GR.gpu_instances(inst)
    skin = wp.Mesh(points=wp.array(np.asarray(skin_V, np.float32), dtype=wp.vec3),
                   indices=wp.array(np.asarray(skin_F, np.int32).ravel(), dtype=wp.int32))
    fam = int(np.asarray(inst['z'])[0, 3]) if len(inst['z']) else 0
    n = size * size
    o_nrm, o_ao, o_cav = wp.zeros(n, dtype=wp.vec4), wp.ones(n, dtype=float), wp.ones(n, dtype=float)
    o_pos, o_mat = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.int32)
    wp.launch(k_growth_drivers, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr, grid.id, float(rq), gA, gB, gQ,
                                               skin.id, int(n_ao), float(ao_r), int(n_cav), float(cav_r), float(eps),
                                               int(seed), fam | (255 << 16), o_nrm, o_ao, o_cav, o_pos, o_mat])
    wp.synchronize()
    img = lambda a, k: (np.asarray(a.numpy()).reshape(size, size, k) if k > 1 else         # noqa: E731
                        np.asarray(a.numpy()).reshape(size, size))[::-1].copy()
    nrm = img(o_nrm, 4)
    cov = nrm[..., 3] > 0
    out = dict(normal=nrm.astype(np.float32), ao=img(o_ao, 1).astype(np.float32),
               cavity=img(o_cav, 1).astype(np.float32), height=np.zeros((size, size), np.float32),
               curvature=np.zeros((size, size), np.float32), position=img(o_pos, 3).astype(np.float32),
               mat=img(o_mat, 1).astype(np.int32))
    log(f'[growth_overlay] growths drivers {size}^2 x ss {ss}: {int(cov.sum()):,} texels, AO p50 '
        f'{np.median(out["ao"][cov]):.3f} (p5 {np.percentile(out["ao"][cov], 5):.3f}), cavity p50 '
        f'{np.median(out["cavity"][cov]):.3f}; {time.time() - t0:.1f}s')
    return out


# ----------------------------------------------------------------------------------------------------- the feet
@wp.struct
class Feet:
    druse_w: float        # the druse's reach past the crystal's surface, in its R
    druse_cell: float     # the druse's Worley cell (m)
    druse_tilt: float     # the micro-crystals' facet tilt (rad, at most)
    druse_dark: float     # the druse's albedo against the crystal's (small facets in each other's shade)
    crack_n: int          # radial cracks per piece (at most; at least half of it)
    crack_len: float      # a crack's reach past the piece's footprint, in the piece's dominant R (at most)
    crack_w: float        # a crack's half width at its root (m; it tapers to a third at its tip)
    crack_wander: float   # its meander (rad)
    groove: float         # the crack's walls' tilt toward its line (rad)
    lift: float           # the shell's rise round the emergence (rad)
    crack_glow: float     # the cracks' emissive mask (0: dark cracks)
    frac: wp.vec3         # the fracture's inner layer (linear albedo): the crack walls' lip
    ao_r: float           # the crystals' occlusion reach (m)
    n_ao: int             # its rays
    texel: float          # the skin's texel (m)
    seed: int


@wp.func
def nearest_same(p: wp.vec3, grid: wp.uint64, rq: float, gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3),
                 gQ: wp.array(dtype=wp.vec4), gP: wp.array(dtype=wp.int32), part: int):
    """(distance, index) of the nearest crystal of this part (its exact signed distance), (1e9, -1) when none within
    the query's reach"""
    best = float(1.0e9)
    bi = int(-1)
    qy = wp.hash_grid_query(grid, p, rq)
    i = int(0)
    while wp.hash_grid_query_next(qy, i):
        if gP[i] != part:
            continue
        q = gQ[i]
        if q[3] < 0.5:
            continue
        d = GR.sd_prism(p, gA[i], gB[i], q[0], q[1], q[2], int(q[3]))
        if d < best:
            best = d
            bi = i
    return wp.vec2(best, float(bi))


@wp.func
def sd_one(p: wp.vec3, i: int, gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4)):
    q = gQ[i]
    return GR.sd_prism(p, gA[i], gB[i], q[0], q[1], q[2], int(q[3]))


@wp.func
def grad_one(p: wp.vec3, i: int, gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4),
             h: float):
    gx = sd_one(p + wp.vec3(h, 0.0, 0.0), i, gA, gB, gQ) - sd_one(p - wp.vec3(h, 0.0, 0.0), i, gA, gB, gQ)
    gy = sd_one(p + wp.vec3(0.0, h, 0.0), i, gA, gB, gQ) - sd_one(p - wp.vec3(0.0, h, 0.0), i, gA, gB, gQ)
    gz = sd_one(p + wp.vec3(0.0, 0.0, h), i, gA, gB, gQ) - sd_one(p - wp.vec3(0.0, 0.0, h), i, gA, gB, gQ)
    g = wp.vec3(gx, gy, gz)
    lg = wp.length(g)
    if lg < 1.0e-12:
        return wp.vec3(0.0, 1.0, 0.0)
    return g / lg


@wp.func
def tilt(n: wp.vec3, dirn: wp.vec3, ang: float):
    """n turned by ang toward the tangent direction dirn (projected off n)"""
    t = dirn - n * wp.dot(dirn, n)
    lt = wp.length(t)
    if lt < 1.0e-9:
        return n
    return wp.normalize(n * wp.cos(ang) + (t / lt) * wp.sin(ang))


@wp.func
def rotate_like(v: wp.vec3, a: wp.vec3, b: wp.vec3):
    """v turned by the rotation that takes the unit a onto the unit b (Rodrigues; the identity when they agree)"""
    c = wp.dot(a, b)
    k = wp.cross(a, b)
    s = wp.length(k)
    if s < 1.0e-9:
        return v
    k = k / s
    return v * c + wp.cross(k, v) * s + k * (wp.dot(k, v) * (1.0 - c))


@wp.func
def wrap_pi(a: float):
    return a - 6.283185307179586 * wp.floor((a + 3.141592653589793) / 6.283185307179586)


@wp.func
def radial_cracks(p: wp.vec3, c0: wp.vec3, n0: wp.vec3, R0: float, pk: int, P: Feet):
    """THE BREACH's cracks round one piece (the module notes): crack_n / 2 .. crack_n radial cracks from its dominant
    crystal's root c0 (normal n0, radius R0), each at its own angle (the piece's hash), meandering, tapering from its root
    at the footprint (1.1 R0) to its tip; returns (the crack's weight, the signed side of its line (+1 / -1: which wall),
    the tangential distance from the root, the in-plane direction away from the line) as a vec4 + the direction via
    the caller's frame: (m, side, r, theta)"""
    e1 = GR.onb_e1(n0)
    e2 = GR.onb_e2(n0)
    qv = p - c0
    qt = qv - n0 * wp.dot(qv, n0)
    r = wp.length(qt)
    th = wp.atan2(wp.dot(qt, e2), wp.dot(qt, e1))
    foot = 1.1 * R0
    nh = proc.hash3i(pk, 0, 0, P.seed + 61)
    half = P.crack_n // 2
    nc = half + int(proc.u01(nh) * float(P.crack_n - half + 1))
    nc = wp.min(nc, P.crack_n)
    rot = 6.283185307179586 * proc.u01(proc.hash3i(pk, 0, 1, P.seed + 61))
    best = float(0.0)
    side = float(0.0)
    seg = 0.45 * R0                                   # a radial's KINKS: a polyline of segments seg long
    for k in range(P.crack_n):
        if k >= nc:
            continue
        thk = 6.283185307179586 * (float(k) + 0.6 * (proc.u01(proc.hash3i(pk, k, 2, P.seed + 61)) - 0.5)) / \
            float(nc) + rot
        Lk = foot + R0 * P.crack_len * (0.35 + 0.65 * proc.u01(proc.hash3i(pk, k, 3, P.seed + 61)))
        # (cr r2c: smooth meandering radials read as the legs of a tick on the elytra; a fracture runs in straight
        # stretches and kinks) the node angles jittered per segment, the line straight between them
        js = wp.floor(r / seg)
        fj = r / seg - js
        jt0 = proc.u01(proc.hash3i(pk, k, 5000 + int(js), P.seed + 63)) - 0.5
        jt1 = proc.u01(proc.hash3i(pk, k, 5001 + int(js), P.seed + 63)) - 0.5
        thm = thk + P.crack_wander * (jt0 + (jt1 - jt0) * fj) * 2.0
        dth = wrap_pi(th - thm)
        if wp.abs(dth) > 1.5707963:
            continue
        dperp = r * wp.sin(wp.abs(dth))
        t = wp.clamp((r - foot) / wp.max(Lk - foot, 1.0e-6), 0.0, 1.0)
        w = wp.max(P.crack_w * (1.0 - 0.67 * t), 0.75 * P.texel)
        m = (1.0 - GR._ss(0.5 * w, 0.5 * w + wp.max(0.75 * w, P.texel), dperp)) * \
            (1.0 - GR._ss(0.85, 1.0, t)) * GR._ss(0.7 * foot, foot, r)
        if m > best:
            best = m
            side = 1.0
            if dth < 0.0:
                side = -1.0
    # the CONCENTRIC arcs a brittle shell adds round an emergence (a star crack: the radials alone read as legs):
    # one ring per piece between the radials' roots and tips, broken into arcs by a hash over its angle
    rr = foot + R0 * (0.45 + 0.5 * proc.u01(proc.hash3i(pk, 0, 7, P.seed + 61)))
    na = 9.0
    ai = wp.floor((th + 3.141592653589793) / 6.283185307179586 * na)
    keep = proc.u01(proc.hash3i(pk, int(ai), 8, P.seed + 61))
    wob = 0.18 * R0 * (proc.u01(proc.hash3i(pk, int(ai), 9, P.seed + 61)) - 0.5)
    wr = wp.max(0.6 * P.crack_w, 0.75 * P.texel)
    dr_ = wp.abs(r - rr - wob)
    if keep < 0.55:
        mr = 1.0 - GR._ss(0.5 * wr, 0.5 * wr + wp.max(0.75 * wr, P.texel), dr_)
        if mr > best:
            best = mr
            side = 0.0
    return wp.vec4(best, side, r, th)


@wp.kernel
def k_feet(tex: wp.array(dtype=wp.vec2), uv_mesh: wp.uint64, ss: int, lpos: wp.array(dtype=wp.vec3),
           lnrm: wp.array(dtype=wp.vec3), ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4),
           hgt: wp.array(dtype=float), alb: wp.array(dtype=wp.vec3), nrm_t: wp.array(dtype=wp.vec3),
           orm: wp.array(dtype=wp.vec3), grid: wp.uint64, rq: float, gA: wp.array(dtype=wp.vec3),
           gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4), gZ: wp.array(dtype=wp.vec4),
           gP: wp.array(dtype=wp.int32), gC0: wp.array(dtype=wp.vec3), gN0: wp.array(dtype=wp.vec3),
           gR0: wp.array(dtype=float), part: int, FT: wp.array(dtype=wp.float32), P: Feet,
           o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3),
           o_grow: wp.array(dtype=wp.vec4), o_dbg: wp.array(dtype=wp.vec4)):
    """THE FEET on one texel of the base (the module notes): tex = its centre in texel units (kernel rows: y = v x H);
    alb (linear), nrm_t (tangent), orm (AO, base roughness, coat roughness): the base's own values there; hgt its bake's
    height (the high point = the low point + n x height); gC0 / gN0 / gR0 per crystal: its PIECE's dominant root, normal
    and radius (the breach's centre). Writes the composed albedo, tangent normal, ORM and the GROWTH pack; o_dbg =
    (druse share, crack, lift angle, crystal occlusion) for my eyes"""
    tid = wp.tid()
    inv = 1.0 / float(ss)
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_o = wp.vec3(0.0)
    acc_g = wp.vec4(0.0)
    acc_d = wp.vec4(0.0)
    hits = int(0)
    tn0 = nrm_t[tid]
    a0 = alb[tid]
    r0 = orm[tid]
    occ = float(-1.0)
    for si in range(ss):
        for sj in range(ss):
            lo = M.low_at(uv_mesh, tex[tid][0] - 0.5 + (float(si) + 0.5) * inv,
                          tex[tid][1] - 0.5 + (float(sj) + 0.5) * inv, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            p = lo.p + lo.n * hgt[tid]
            nb = M.to_world(lo, tn0)                      # the base's composed normal (its micro relief)
            nm = lo.n                                     # the macro normal (the low's)
            if occ < 0.0:
                # the crystals' occlusion of the sky here (every crystal: a neighbouring part's shades this one too)
                occ = 1.0 - occlusion(p, nm, P.n_ao, P.ao_r, P.seed, tid, grid, rq, gA, gB, gQ, -1, grid, 0,
                                      0.5 * P.texel)
            ns = nearest_same(p, grid, rq, gA, gB, gQ, gP, part)
            dc = ns[0]
            ci = int(ns[1])
            col = a0
            n_out = nb
            ao_t = r0[0] * (1.0 - occ)
            rough_b = r0[1]
            rough_c = r0[2]
            share = float(0.0)
            emis = float(0.0)
            irid = float(0.0)
            phase = float(0.0)
            crack = float(0.0)
            lift_a = float(0.0)
            if ci >= 0:
                q = gQ[ci]
                Rc = q[0]
                g = grad_one(p, ci, gA, gB, gQ, 0.25 * P.texel)
                # the crystal's own surface next to this point: its material there (growth_material, the octopus's look)
                pp = p - g * dc
                gs = GR.growth_surface(pp, grid, rq, gA, gB, gQ, gZ)
                fam = int(gZ[ci][3] + 0.5)
                gm = GR.growth_material(gs, fam, FT, r0[0], 0.0, 0.0, nm[1], P.texel, a0)
                o = fam * 43
                phase = gm.phase
                rel = dc / wp.max(Rc, 1.0e-6)
                if dc < 0.0:
                    # hidden under the crystal (the growths mesh covers it): its colour and roughness on the skin's own
                    # macro normal, so a slit at the junction shows crystal and the coarse mips blend into the druse round
                    # it without the crystal's inner gradient field (cr04 r2: six bright sectors under every crystal)
                    share = 1.0
                    col = gm.col
                    n_out = nm
                    rough_b = gm.rough
                    rough_c = gm.rough
                    emis = gm.emis
                    irid = gm.irid
                else:
                    # THE BREACH round this crystal's PIECE (its dominant's root): the shell risen round the emergence
                    # (normals tilted away from it, fading over 1.5 R0) and radial cracks (radial_cracks), each a groove
                    # whose walls tilt toward its line, dark, a paler lip on the walls (the fracture's inner layer)
                    c0 = gC0[ci]
                    n0 = gN0[ci]
                    R0 = gR0[ci]
                    rc = radial_cracks(p, c0, n0, R0, int(gZ[ci][2] + 0.5), P)
                    crack = rc[0]
                    r = rc[2]
                    th = rc[3]
                    e1 = GR.onb_e1(n0)
                    e2 = GR.onb_e2(n0)
                    radial = e1 * wp.cos(th) + e2 * wp.sin(th)
                    tang = e2 * wp.cos(th) - e1 * wp.sin(th)              # (toward larger angles)
                    lift_a = P.lift * (1.0 - GR._ss(1.1 * R0, 2.6 * R0, r)) * GR._ss(0.0, 0.5 * R0, dc)
                    n_out = tilt(nb, radial, lift_a)
                    # the groove: a wall at angle above the line (side +1) tilts toward smaller angles, and back
                    n_out = tilt(n_out, tang * (-rc[1]), P.groove * crack)
                    lip = crack * (1.0 - crack) * 4.0                     # (the walls' middle band)
                    col = a0 + (P.frac - a0) * (0.30 * lip)
                    col = col * (1.0 - 0.65 * crack)
                    ao_t = ao_t * (1.0 - 0.5 * crack)
                    rough_b = rough_b + (0.80 - rough_b) * crack
                    rough_c = rough_c + (0.80 - rough_c) * crack
                    emis = P.crack_glow * FT[o + 18] * crack
                    # THE DRUSE: small crystals crowding each crystal's foot (Worley cells), each a steep facet of its
                    # own tilt, glossy (the glints a drusy matrix shows), darker than the crystal (in each other's shade)
                    # and dark in its crevices; the crust's edge broken cell by cell
                    dcl = proc.cellular3(p / P.druse_cell, 1.0, P.seed + 41)
                    d1 = dcl.rand
                    d2 = proc.u01(proc.hash3i(dcl.cell[0], dcl.cell[1], dcl.cell[2], P.seed + 47))
                    d3 = proc.u01(proc.hash3i(dcl.cell[0], dcl.cell[1], dcl.cell[2], P.seed + 53))
                    thr = P.druse_w * (0.35 + 0.95 * d1)
                    dr = 1.0 - GR._ss(0.8 * thr, thr, rel)
                    tdir = GR.onb_e1(nm) * wp.cos(6.2832 * d2) + GR.onb_e2(nm) * wp.sin(6.2832 * d2)
                    n_d = tilt(nm, tdir, P.druse_tilt * (0.45 + 0.55 * d3))
                    crev = 1.0 - GR._ss(0.0, 0.10, dcl.edge)
                    cd = gm.col * (P.druse_dark * (0.55 + 0.9 * d1) * (1.0 - 0.7 * crev))
                    share = dr
                    col = col + (cd - col) * dr
                    n_out = wp.normalize(n_out + (n_d - n_out) * dr)
                    rd = 0.06 + 0.30 * d2 + 0.4 * crev
                    rough_b = rough_b + (rd - rough_b) * dr
                    rough_c = rough_c + (rd - rough_c) * dr
                    ao_t = ao_t * (1.0 - 0.45 * crev * dr)
                    emis = emis + (0.15 * gm.emis - emis) * dr
                    irid = gm.irid * dr
            acc_a = acc_a + col
            acc_n = acc_n + M.to_tangent(lo, n_out)
            acc_o = acc_o + wp.vec3(wp.clamp(ao_t, 0.0, 1.0), wp.clamp(rough_b, 0.02, 1.0), wp.clamp(rough_c, 0.02, 1.0))
            acc_g = acc_g + wp.vec4(share, irid, wp.clamp(emis, 0.0, 1.0), phase)
            acc_d = acc_d + wp.vec4(share, crack, lift_a, occ)
            hits = hits + 1
    if hits == 0:
        o_alb[tid] = a0
        o_nrm[tid] = tn0
        o_orm[tid] = r0
        o_grow[tid] = wp.vec4(0.0)
        return
    fh = float(hits)
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = acc_o / fh
    o_grow[tid] = acc_g / fh
    o_dbg[tid] = acc_d / fh


def feet_params(**kw):
    """the FEET's parameters (Feet) with the builder's defaults [I], in metres at the beetle's x10"""
    P = Feet()
    d = dict(druse_w=0.45, druse_cell=0.0009, druse_tilt=0.75, druse_dark=0.55, crack_n=9, crack_len=1.5,
             crack_w=0.00018, crack_wander=0.12, groove=0.45, lift=0.12, crack_glow=0.0, frac=(0.30, 0.19, 0.10),
             ao_r=0.0125, n_ao=24, texel=1.0 / 9257.0, seed=5501)
    d.update(kw)
    for k, v in d.items():
        setattr(P, k, wp.vec3(*v) if k == 'frac' else (int(v) if k in ('n_ao', 'seed', 'crack_n') else float(v)))
    d['breach_w'] = 1.1 + d['crack_len']             # the reach the candidates need, in the largest dominant's R
    return P, d


def uv_bvh_wh(F, UV, W, H):
    """material.uv_bvh for a W x H page (texel units: x = u W, y = v H)"""
    corner = np.asarray(F, np.int32).ravel()
    luv = np.asarray(UV, np.float64)[corner] * np.array([W, H], np.float64)
    return wp.Mesh(points=wp.array(np.column_stack([luv, np.zeros(len(luv))]).astype(np.float32), dtype=wp.vec3),
                   indices=wp.array(np.arange(len(luv), dtype=np.int32), dtype=wp.int32))


def skin_overlay(texels, low, W, H, hgt, alb, nrm_t, orm, inst, part_of, part, params, ss=2, log=print):
    """THE FEET (the module notes) on a list of the base's texels: texels (n, 2) their (x, y) in kernel rows (y = v H,
    centres at +0.5); low = dict(V, F, UV, N, TAN) of the ONE placed piece those texels belong to on this page; hgt,
    alb (linear), nrm_t (tangent), orm per texel; inst = growth.instances(cr) (every crystal), part_of (n_inst,) each
    crystal's part index, part = this piece's. Returns per texel (albedo linear, tangent normal, orm, growth pack, dbg)"""
    import time
    t0 = time.time()
    P, d = params
    if not len(texels):
        z3, z4 = np.zeros((0, 3), np.float32), np.zeros((0, 4), np.float32)
        return z3, z3, z3, z4, z4
    uvm = uv_bvh_wh(low['F'], low['UV'], W, H)
    lpos, lnrm, ltan, lattr = M.corner_arrays(low['V'], low['F'], low['N'], low['TAN'], np.zeros((len(low['V']), 4)))
    grid, rq, gA, gB, gQ, gZ = GR.gpu_instances(inst)
    rq = float(rq + d['breach_w'] * float(np.asarray(inst['q'])[:, 0].max()) + d['ao_r'])
    grid.build(wp.array((0.5 * (np.asarray(inst['a']) + np.asarray(inst['b']))).astype(np.float32), dtype=wp.vec3), rq)
    gP = wp.array(np.asarray(part_of, np.int32), dtype=wp.int32)
    # each crystal's PIECE: its dominant (the piece's first instance: instances() keeps the plan's order) root, normal, R
    pc = np.asarray(inst['z'])[:, 2].round().astype(np.int64)
    first = {}
    for i, k in enumerate(pc):
        first.setdefault(int(k), i)
    dom = np.asarray([first[int(k)] for k in pc], np.int64)
    gC0 = wp.array(np.asarray(inst['root'], np.float32)[dom], dtype=wp.vec3)
    gN0 = wp.array(np.asarray(inst['n'], np.float32)[dom], dtype=wp.vec3)
    gR0 = wp.array(np.asarray(inst['q'], np.float32)[dom, 0], dtype=float)
    FT = wp.array(GR.family_table(), dtype=wp.float32)
    n = len(texels)
    outs = [wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec3),
            wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)]
    arr3 = lambda a: wp.array(np.asarray(a, np.float32).reshape(-1, 3), dtype=wp.vec3)       # noqa: E731
    wp.launch(k_feet, dim=n, inputs=[wp.array(np.asarray(texels, np.float32), dtype=wp.vec2), uvm.id, int(ss), lpos, lnrm,
                                     ltan, lattr, wp.array(np.asarray(hgt, np.float32), dtype=float), arr3(alb),
                                     arr3(nrm_t), arr3(orm), grid.id, rq, gA, gB, gQ, gZ, gP, gC0, gN0, gR0, int(part), FT,
                                     P] + outs)
    wp.synchronize()
    res = [o.numpy() for o in outs]
    log(f'[growth_overlay] feet on {n:,} texels (part {part}): druse share > 0.5 on {(res[3][:, 0] > 0.5).sum():,}, '
        f'cracks > 0.5 on {(res[4][:, 1] > 0.5).sum():,}, crystal occlusion p95 {np.percentile(res[4][:, 3], 95):.3f}; '
        f'{time.time() - t0:.1f}s')
    return res
