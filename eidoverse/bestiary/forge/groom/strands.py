"""GUIDES AND STRANDS as Warp kernels (HAIR_STUDY §9.2 step 4; WOLF_PLAN §5.2 step 2).

A strand is K points (root first) in one (S, K) array. Growth FOLLOWS THE SURFACE: each step finds the closest point
on the base's welded low (wp.mesh_query_point_no_sign), reads the local normal and the local flow there, and steps
along d = cos(theta) n + sin(theta) c, theta the elevation profile from the normal (the spec's "lift": theta_root at
the root to theta_tip at the tip, a power curve, per-strand jitter), plus gravity's droop. So a coat lies along a
curved body as combed fur does, instead of standing off it by the curvature's sag (a straight 45 mm strand on the 60 mm
mantle would stand ~15 mm proud at its tip), and a strand that leaves the arm's flow for the mantle's turns with it.

Operators then run in the spec's order, each a kernel over every point (per-strand parameters come in as arrays the
caller computes from the spec and the stable hashes, so the kernels stay generic):
  clump    strands pulled toward their clump guide's matching point, weight strength x t^profile (tips converge)
  wave     a sideways sine along the strand's binormal, amplitude x t (curl / wave)
  frizz    hashed per-point jitter x t^2
  settle   inextensibility (segment lengths restored from the root out) + collision: no point closer to the skin than
           the margin (pushed out along the closest face's normal)

Coat round 3 (10-30): THE COAT'S EDGE. Round 2's shaggy laid 6 % of its strands out over bare skin, 8 mm past the edge
(p50): where a strand left the coat the flow ran along the edge and GRAVITY's droop pointed into the bare zone (the arms'
lower flanks over the sucker side and the oral web: work/bestiary/coat/g5/g5_groom/scratch/s01_*_g4.json). k_grow
now takes a GUARD field (per welded vertex: the direction into the bare zone, its length the guard's weight, 1 at the
coat's edge falling to 0 a band inside it: groom.py builds it from fields.edge_distance_w): within the band, the part
of each step that heads into the bare zone turns along the edge instead, the step's lift and length kept, so the
coat's lower edge combs along the body the way a pelt's edge lies, instead of hanging over skin it does not cover.

(B3, HAIR_FUR H2) FREE-HANGING GROWTH: hair that hangs past the head. k_grow keeps every step on the surface, which is
right for fur and wrong for a bob: past the scalp a strand must leave the skin and fall. A HANG group grows with
k_hang against an SDF of the head + neck + shoulders (SDF: a dense grid built once per base from the skin's winding
number, trilinear in the kernels, its gradient by central differences):
  attach    for its first attach_mm a strand COMBS along the flow at its own height over the SDF (it rises from the root to
            `offset` over the first half of that: the crown's strands lie on top of the hairline's, the layered volume a
            real head of hair has from stacking: the style writes offset_mm as a field)
  free      past it the strand integrates under gravity with a stiffness that falls along it (a cantilever profile:
            stiff0 x (1 - s)^stiff_pow over the free part), every step pushed out of the SDF to its floor
  relax     k_hang_relax: position-based settling (gravity on the free part, follow-the-leader inextensibility from the
            root, the SDF floor) so strands drape over the skull and hang instead of keeping the growth's arcs
The groom gates every point against the SDF (none inside; the floor's margin reported).

(B3) THE CUT: cut_strands ends each strand where it first falls below a cut line (a height per azimuth of the head
frame, jittered per strand), resampled along its own path: the bob's blunt line, the fringe's line above the brows.
"""
import numpy as np
import warp as wp

wp.set_module_options({'enable_backward': False})


@wp.func
def _surf(mesh: wp.uint64, Nw: wp.array(dtype=wp.vec3), Fw: wp.array(dtype=wp.int32), flow: wp.array(dtype=wp.vec3),
          p: wp.vec3):
    """closest point on the low: (point, interpolated normal, flow at the point, face normal)"""
    q = wp.mesh_query_point_no_sign(mesh, p, 10.0)
    f = q.face
    u = q.u
    v = q.v
    i0 = Fw[f * 3 + 0]
    i1 = Fw[f * 3 + 1]
    i2 = Fw[f * 3 + 2]
    s = wp.mesh_eval_position(mesh, f, u, v)
    n = wp.normalize(Nw[i0] * u + Nw[i1] * v + Nw[i2] * (1.0 - u - v))
    c = flow[i0] * u + flow[i1] * v + flow[i2] * (1.0 - u - v)
    c = c - n * wp.dot(c, n)
    lc = wp.length(c)
    if lc > 1.0e-9:
        c = c / lc
    p0 = wp.mesh_eval_position(mesh, f, 1.0, 0.0)
    p1 = wp.mesh_eval_position(mesh, f, 0.0, 1.0)
    p2 = wp.mesh_eval_position(mesh, f, 0.0, 0.0)
    fn = wp.normalize(wp.cross(p1 - p0, p2 - p0))
    return s, n, c, fn


@wp.func
def _guard(mesh: wp.uint64, Fw: wp.array(dtype=wp.int32), guard: wp.array(dtype=wp.vec3), p: wp.vec3):
    """(coat round 3) the coat-edge guard at the closest point: the direction into the bare zone x its weight"""
    q = wp.mesh_query_point_no_sign(mesh, p, 10.0)
    f = q.face
    i0 = Fw[f * 3 + 0]
    i1 = Fw[f * 3 + 1]
    i2 = Fw[f * 3 + 2]
    return guard[i0] * q.u + guard[i1] * q.v + guard[i2] * (1.0 - q.u - q.v)


@wp.kernel
def k_grow(mesh: wp.uint64, Nw: wp.array(dtype=wp.vec3), Fw: wp.array(dtype=wp.int32), flow: wp.array(dtype=wp.vec3),
           root: wp.array(dtype=wp.vec3), length: wp.array(dtype=wp.float32), th0: wp.array(dtype=wp.float32),
           th1: wp.array(dtype=wp.float32), thp: wp.array(dtype=wp.float32), grav: wp.array(dtype=wp.float32),
           gdir: wp.vec3, margin: float, K: int, guard: wp.array(dtype=wp.vec3), P: wp.array(dtype=wp.vec3)):
    s = wp.tid()
    p = root[s]
    P[s * K] = p
    seg = length[s] / float(K - 1)
    for k in range(1, K):
        sp = _surf(mesh, Nw, Fw, flow, p)
        n = sp[1]
        c = sp[2]
        t = (float(k) - 0.5) / float(K - 1)
        th = th0[s] + (th1[s] - th0[s]) * wp.pow(t, thp[s])
        d = n * wp.cos(th) + c * wp.sin(th)
        d = wp.normalize(d + gdir * (grav[s] * t))
        # (coat round 3) the coat's edge: within the guard's band the step's part heading into the bare zone turns
        # along the edge (toward the side the flow leans to), its lift and its length kept
        g = _guard(mesh, Fw, guard, p)
        g = g - n * wp.dot(g, n)
        w = wp.min(wp.length(g), 1.0)
        dn = wp.dot(d, n)
        dt = d - n * dn
        ldt = wp.length(dt)
        if w > 1.0e-6 and ldt > 1.0e-9:
            e = wp.normalize(g)
            de = wp.dot(dt, e)
            if de > 0.0:
                dt2 = dt - e * (de * w)
                l2 = wp.length(dt2)
                if l2 < 0.25 * ldt:
                    a = wp.cross(n, e)
                    if wp.dot(a, c) < 0.0:
                        a = -a
                    dt2 = dt2 + a * (0.25 * ldt)
                    l2 = wp.length(dt2)
                d = wp.normalize(n * dn + dt2 * (ldt / l2))
        p = p + d * seg
        # no point under the skin: push out along the closest face's normal
        sq = _surf(mesh, Nw, Fw, flow, p)
        h = wp.dot(p - sq[0], sq[3])
        if h < margin:
            p = p + sq[3] * (margin - h)
        P[s * K + k] = p


@wp.kernel
def k_clump(P: wp.array(dtype=wp.vec3), G: wp.array(dtype=wp.vec3), clump: wp.array(dtype=wp.int32),
            strength: wp.array(dtype=wp.float32), profile: float, K: int):
    i = wp.tid()
    s = i / K
    k = i - s * K
    c = clump[s]
    if c < 0 or k == 0:
        return
    t = float(k) / float(K - 1)
    w = strength[s] * wp.pow(t, profile)
    off = P[s * K] - G[c * K]
    target = G[c * K + k] + off * (1.0 - w)
    P[i] = P[i] * (1.0 - w) + target * w


@wp.kernel
def k_wave(mesh: wp.uint64, Nw: wp.array(dtype=wp.vec3), Fw: wp.array(dtype=wp.int32), flow: wp.array(dtype=wp.vec3),
           P: wp.array(dtype=wp.vec3), amp: wp.array(dtype=wp.float32), freq: wp.array(dtype=wp.float32),
           phase: wp.array(dtype=wp.float32), K: int, Q: wp.array(dtype=wp.vec3)):
    i = wp.tid()
    s = i / K
    k = i - s * K
    if k == 0:
        Q[i] = P[i]
        return
    t = float(k) / float(K - 1)
    a = P[s * K + wp.max(k - 1, 0)]
    b = P[s * K + wp.min(k + 1, K - 1)]
    d = wp.normalize(b - a)
    sp = _surf(mesh, Nw, Fw, flow, P[i])
    bn = wp.cross(sp[1], d)
    lb = wp.length(bn)
    if lb > 1.0e-9:
        bn = bn / lb
    Q[i] = P[i] + bn * (amp[s] * t * wp.sin(6.2831853 * freq[s] * t + phase[s]))


@wp.func
def _h(x: wp.uint32):
    """lowbias32 to [0, 1)"""
    x = x ^ (x >> wp.uint32(16))
    x = x * wp.uint32(0x7FEB352D)
    x = x ^ (x >> wp.uint32(15))
    x = x * wp.uint32(0x846CA68B)
    x = x ^ (x >> wp.uint32(16))
    return float(x >> wp.uint32(8)) / 16777216.0


@wp.kernel
def k_frizz(P: wp.array(dtype=wp.vec3), amp: wp.array(dtype=wp.float32), seed: int, K: int):
    i = wp.tid()
    s = i / K
    k = i - s * K
    if k == 0:
        return
    t = float(k) / float(K - 1)
    j = wp.uint32(i) * wp.uint32(3) + wp.uint32(seed) * wp.uint32(7919)
    r = wp.vec3(_h(j) - 0.5, _h(j + wp.uint32(1)) - 0.5, _h(j + wp.uint32(2)) - 0.5)
    P[i] = P[i] + r * (2.0 * amp[s] * t * t)


@wp.kernel
def k_settle(mesh: wp.uint64, Nw: wp.array(dtype=wp.vec3), Fw: wp.array(dtype=wp.int32), flow: wp.array(dtype=wp.vec3),
             P: wp.array(dtype=wp.vec3), length: wp.array(dtype=wp.float32), margin: float, K: int):
    s = wp.tid()
    seg = length[s] / float(K - 1)
    prev = P[s * K]
    for k in range(1, K):
        p = P[s * K + k]
        d = p - prev
        ld = wp.length(d)
        if ld > 1.0e-12:
            p = prev + d * (seg / ld)
        sq = _surf(mesh, Nw, Fw, flow, p)
        h = wp.dot(p - sq[0], sq[3])
        if h < margin:
            p = p + sq[3] * (margin - h)
        P[s * K + k] = p
        prev = p


@wp.kernel
def k_height(mesh: wp.uint64, Nw: wp.array(dtype=wp.vec3), Fw: wp.array(dtype=wp.int32), flow: wp.array(dtype=wp.vec3),
             P: wp.array(dtype=wp.vec3), H: wp.array(dtype=wp.float32), FACE: wp.array(dtype=wp.int32)):
    """signed height of every point above the low (along the closest face's normal) and that face"""
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, P[i], 10.0)
    sq = _surf(mesh, Nw, Fw, flow, P[i])
    H[i] = wp.dot(P[i] - sq[0], sq[3])
    FACE[i] = q.face


@wp.kernel
def k_closest(mesh: wp.uint64, Nw: wp.array(dtype=wp.vec3), Fw: wp.array(dtype=wp.int32), flow: wp.array(dtype=wp.vec3),
              P: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.vec3), N: wp.array(dtype=wp.vec3)):
    """the true closest point on the low and the interpolated normal there"""
    i = wp.tid()
    sp = _surf(mesh, Nw, Fw, flow, P[i])
    S[i] = sp[0]
    N[i] = sp[1]


def closest(surf, X):
    """(closest skin point, interpolated normal there) of every point (n, 3), as float64 arrays"""
    d = surf.device
    n = len(X)
    S = wp.zeros(n, dtype=wp.vec3, device=d)
    N = wp.zeros(n, dtype=wp.vec3, device=d)
    wp.launch(k_closest, dim=n, device=d,
              inputs=[*surf.args(), wp.array(np.asarray(X, np.float32), dtype=wp.vec3, device=d), S, N])
    return S.numpy().astype(np.float64), N.numpy().astype(np.float64)


@wp.kernel
def k_query(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), FACE: wp.array(dtype=wp.int32),
            BU: wp.array(dtype=wp.float32), BV: wp.array(dtype=wp.float32), H: wp.array(dtype=wp.float32)):
    """(coat round 3) the closest face, its barycentrics and the signed height along that face's normal"""
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, P[i], 10.0)
    FACE[i] = q.face
    BU[i] = q.u
    BV[i] = q.v
    s = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
    p0 = wp.mesh_eval_position(mesh, q.face, 1.0, 0.0)
    p1 = wp.mesh_eval_position(mesh, q.face, 0.0, 1.0)
    p2 = wp.mesh_eval_position(mesh, q.face, 0.0, 0.0)
    H[i] = wp.dot(P[i] - s, wp.normalize(wp.cross(p1 - p0, p2 - p0)))


def query(surf, X):
    """(coat round 3) every point's closest skin point as (face, barycentrics (n, 3), signed height): the welded low's
    faces are the base's faces in order (Fw = wid[F]), so (face, bary) reads any fields expression (fields.Pts)"""
    d = surf.device
    X = np.ascontiguousarray(np.asarray(X, np.float32).reshape(-1, 3))
    n = len(X)
    F = wp.zeros(n, dtype=wp.int32, device=d)
    U = wp.zeros(n, dtype=wp.float32, device=d)
    V = wp.zeros(n, dtype=wp.float32, device=d)
    H = wp.zeros(n, dtype=wp.float32, device=d)
    if n:
        wp.launch(k_query, dim=n, device=d, inputs=[surf.mesh.id, wp.array(X, dtype=wp.vec3, device=d), F, U, V, H])
    u, v = U.numpy().astype(np.float64), V.numpy().astype(np.float64)
    return F.numpy().astype(np.int64), np.column_stack([u, v, 1.0 - u - v]), H.numpy().astype(np.float64)


class Surface:
    """the welded low on a Warp device, with its normals and the flow (what every kernel here queries)"""

    def __init__(self, base, flow_v, device=None):
        self.device = device or wp.get_preferred_device()
        d = self.device
        self.mesh = wp.Mesh(points=wp.array(base.Vw.astype(np.float32), dtype=wp.vec3, device=d),
                            indices=wp.array(base.Fw.astype(np.int32).reshape(-1), dtype=wp.int32, device=d))
        self.Nw = wp.array(base.Nw.astype(np.float32), dtype=wp.vec3, device=d)
        self.Fw = wp.array(base.Fw.astype(np.int32).reshape(-1), dtype=wp.int32, device=d)
        self.flow = wp.array(np.asarray(flow_v, np.float32), dtype=wp.vec3, device=d)

    def args(self):
        return [self.mesh.id, self.Nw, self.Fw, self.flow]


def _f32(a, d):
    return wp.array(np.ascontiguousarray(a, np.float32), dtype=wp.float32, device=d)


def grow(surf, root, length, th0, th1, thp, grav, K, gdir=(0.0, -1.0, 0.0), margin=2.0e-4, guard=None):
    """grow strands from roots (S, 3) with per-strand length (m), elevation from the normal (radians: root, tip, power)
    and gravity; guard: (coat round 3) the coat-edge guard per welded vertex (None: no guard); returns a device array
    (S * K) of vec3"""
    d = surf.device
    S = len(root)
    P = wp.zeros(S * K, dtype=wp.vec3, device=d)
    if S == 0:
        return P
    nw = surf.Nw.shape[0]
    g = np.zeros((nw, 3), np.float32) if guard is None else np.ascontiguousarray(guard, np.float32)
    wp.launch(k_grow, dim=S, device=d,
              inputs=[*surf.args(), wp.array(np.asarray(root, np.float32), dtype=wp.vec3, device=d),
                      _f32(length, d), _f32(th0, d), _f32(th1, d), _f32(thp, d), _f32(grav, d),
                      wp.vec3(*[float(x) for x in gdir]), float(margin), int(K), wp.array(g, dtype=wp.vec3, device=d), P])
    return P


def clump(P, G, clump_id, strength, profile, K):
    d = P.device
    S = P.shape[0] // K
    wp.launch(k_clump, dim=S * K, device=d,
              inputs=[P, G, wp.array(np.asarray(clump_id, np.int32), dtype=wp.int32, device=d), _f32(strength, d),
                      float(profile), int(K)])


def wave(surf, P, amp, freq, phase, K):
    d = P.device
    Q = wp.zeros_like(P)
    wp.launch(k_wave, dim=P.shape[0], device=d,
              inputs=[*surf.args(), P, _f32(amp, d), _f32(freq, d), _f32(phase, d), int(K), Q])
    return Q


def frizz(P, amp, seed, K):
    wp.launch(k_frizz, dim=P.shape[0], device=P.device, inputs=[P, _f32(amp, P.device), int(seed), int(K)])


def settle(surf, P, length, K, margin=2.0e-4, iters=2):
    S = P.shape[0] // K
    for _ in range(iters):
        wp.launch(k_settle, dim=S, device=P.device, inputs=[*surf.args(), P, _f32(length, P.device), float(margin), int(K)])


def heights(surf, P):
    """(signed height above the low, closest welded face) of every point"""
    n = P.shape[0]
    H = wp.zeros(n, dtype=wp.float32, device=P.device)
    FACE = wp.zeros(n, dtype=wp.int32, device=P.device)
    wp.launch(k_height, dim=n, device=P.device, inputs=[*surf.args(), P, H, FACE])
    return H.numpy(), FACE.numpy()


# ================================================================================================ (B3) the SDF
@wp.kernel
def k_sdf_build(mesh: wp.uint64, o: wp.vec3, h: float, maxd: float, phi: wp.array3d(dtype=wp.float32)):
    i, j, k = wp.tid()
    p = o + wp.vec3(float(i), float(j), float(k)) * h
    q = wp.mesh_query_point_sign_winding_number(mesh, p, maxd, 2.0, 0.5)
    if q.result:
        s = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        phi[i, j, k] = wp.length(p - s) * q.sign
    else:
        phi[i, j, k] = maxd


@wp.func
def _phi(phi: wp.array3d(dtype=wp.float32), o: wp.vec3, h: float, p: wp.vec3):
    """the SDF at p, trilinear (clamped to the grid: its border lies far outside the skin)"""
    nx = phi.shape[0]
    ny = phi.shape[1]
    nz = phi.shape[2]
    q = (p - o) / h
    x = wp.clamp(q[0], 0.0, float(nx - 1) - 0.0001)
    y = wp.clamp(q[1], 0.0, float(ny - 1) - 0.0001)
    z = wp.clamp(q[2], 0.0, float(nz - 1) - 0.0001)
    i = int(x)
    j = int(y)
    k = int(z)
    fx = x - float(i)
    fy = y - float(j)
    fz = z - float(k)
    c00 = phi[i, j, k] * (1.0 - fx) + phi[i + 1, j, k] * fx
    c10 = phi[i, j + 1, k] * (1.0 - fx) + phi[i + 1, j + 1, k] * fx
    c01 = phi[i, j, k + 1] * (1.0 - fx) + phi[i + 1, j, k + 1] * fx
    c11 = phi[i, j + 1, k + 1] * (1.0 - fx) + phi[i + 1, j + 1, k + 1] * fx
    c0 = c00 * (1.0 - fy) + c10 * fy
    c1 = c01 * (1.0 - fy) + c11 * fy
    return c0 * (1.0 - fz) + c1 * fz


@wp.func
def _phi_grad(phi: wp.array3d(dtype=wp.float32), o: wp.vec3, h: float, p: wp.vec3):
    """the SDF's unit gradient at p (central differences over one cell)"""
    gx = _phi(phi, o, h, p + wp.vec3(h, 0.0, 0.0)) - _phi(phi, o, h, p - wp.vec3(h, 0.0, 0.0))
    gy = _phi(phi, o, h, p + wp.vec3(0.0, h, 0.0)) - _phi(phi, o, h, p - wp.vec3(0.0, h, 0.0))
    gz = _phi(phi, o, h, p + wp.vec3(0.0, 0.0, h)) - _phi(phi, o, h, p - wp.vec3(0.0, 0.0, h))
    g = wp.vec3(gx, gy, gz)
    lg = wp.length(g)
    if lg > 1.0e-12:
        return g / lg
    return wp.vec3(0.0, 1.0, 0.0)


@wp.func
def _floor(offset: float, rise: float, margin: float, arc: float):
    """a strand's floor over the SDF at arc length `arc`: its offset reached over `rise` from the root, plus the margin"""
    x = wp.clamp(arc / wp.max(rise, 1.0e-6), 0.0, 1.0)
    return offset * x * x * (3.0 - 2.0 * x) + margin


@wp.kernel
def k_sdf_sample(phi: wp.array3d(dtype=wp.float32), o: wp.vec3, h: float, P: wp.array(dtype=wp.vec3),
                 out: wp.array(dtype=wp.float32)):
    i = wp.tid()
    out[i] = _phi(phi, o, h, P[i])


class SDF:
    """(B3) a signed distance grid of a base's skin (negative inside), over a box (lo, hi) at spacing h (m)"""

    def __init__(self, base, lo, hi, h=2.5e-3, device=None, maxd=0.3, cache=None, close_mm=0.0):
        self.device = device or wp.get_preferred_device()
        self.lo = np.asarray(lo, np.float64)
        self.hi = np.asarray(hi, np.float64)
        self.h = float(h)
        n = np.ceil((self.hi - self.lo) / self.h).astype(np.int64) + 1
        self.shape = tuple(int(x) for x in n)
        key = f'{base.sha1[:12]}_{"_".join(f"{x:.4f}" for x in (*self.lo, *self.hi))}_{self.h:.5f}'
        self.key = key
        phi = None
        if cache:
            import os
            p = os.path.join(cache, f'sdf_{key}.npz')
            if os.path.exists(p):
                phi = np.load(p)['phi']
        if phi is None:
            d = self.device
            mesh = wp.Mesh(points=wp.array(base.V.astype(np.float32), dtype=wp.vec3, device=d),
                           indices=wp.array(base.F.astype(np.int32).reshape(-1), dtype=wp.int32, device=d),
                           support_winding_number=True)
            arr = wp.zeros(self.shape, dtype=wp.float32, device=d)
            wp.launch(k_sdf_build, dim=self.shape, device=d,
                      inputs=[mesh.id, wp.vec3(*[float(x) for x in self.lo]), self.h, float(maxd), arr])
            phi = arr.numpy()
            if cache:
                import os
                os.makedirs(cache, exist_ok=True)
                np.savez_compressed(os.path.join(cache, f'sdf_{key}.npz'), phi=phi)
        self.phi_raw = phi.astype(np.float32)
        self.close_mm = float(close_mm)
        if close_mm > 0:
            import os
            self.key = key + f'_c{close_mm:g}'
            pc = os.path.join(cache, f'sdf_{self.key}.npz') if cache else None
            if pc and os.path.exists(pc):
                phi = np.load(pc)['phi']                     # the closing cached too (it costs minutes on a busy CPU)
            else:
                phi = self.closed(phi, close_mm * 1e-3)
                if pc:
                    np.savez_compressed(pc, phi=phi)
        self.phi_np = phi.astype(np.float32)
        self.phi = wp.array(self.phi_np, dtype=wp.float32, device=self.device)

    def closed(self, phi, r):
        """(B3, g02) the solid CLOSED by r (a dilation then an erosion of {phi < 0}): the slot behind the ear and other
        crevices narrower than ~2 r fill, so hair lies over the ear instead of threading the 2-3 mm gap the grid cannot
        resolve (g02: 75 points of 63 strands caught there, 8.9 mm deep). Newly solid voxels take minus their distance to
        the closed solid's outside; voxels outside keep the smaller of their own value and their distance to it"""
        from scipy import ndimage as nd
        rv = max(int(round(r / self.h)), 1)
        zz, yy, xx = np.mgrid[-rv:rv + 1, -rv:rv + 1, -rv:rv + 1]
        ball = (xx * xx + yy * yy + zz * zz) <= rv * rv
        solid = phi < 0
        cs = nd.binary_erosion(nd.binary_dilation(solid, ball), ball, border_value=0) | solid
        new = cs & ~solid
        out = phi.copy()
        d_in = nd.distance_transform_edt(cs) * self.h
        d_out = nd.distance_transform_edt(~cs) * self.h
        out[new] = -np.maximum(d_in[new] - 0.5 * self.h, 0.25 * self.h)
        outside = ~cs
        out[outside] = np.minimum(phi[outside], np.maximum(d_out[outside] - 0.5 * self.h, 0.0))
        self.closed_voxels = int(new.sum())
        return out

    def args(self):
        return [self.phi, wp.vec3(*[float(x) for x in self.lo]), self.h]

    def sample(self, X):
        X = np.ascontiguousarray(np.asarray(X, np.float32).reshape(-1, 3))
        out = wp.zeros(len(X), dtype=wp.float32, device=self.device)
        if len(X):
            wp.launch(k_sdf_sample, dim=len(X), device=self.device,
                      inputs=[*self.args(), wp.array(X, dtype=wp.vec3, device=self.device), out])
        return out.numpy().astype(np.float64)


# ================================================================================================ (B3) hang growth
@wp.kernel
def k_hang(mesh: wp.uint64, Nw: wp.array(dtype=wp.vec3), Fw: wp.array(dtype=wp.int32), flow: wp.array(dtype=wp.vec3),
           phi: wp.array3d(dtype=wp.float32), o: wp.vec3, hgrid: float,
           root: wp.array(dtype=wp.vec3), length: wp.array(dtype=wp.float32), attach: wp.array(dtype=wp.float32),
           offset: wp.array(dtype=wp.float32), th0: wp.array(dtype=wp.float32), stiff0: wp.array(dtype=wp.float32),
           stiff_pow: float, gdir: wp.vec3, margin: float, K: int, P: wp.array(dtype=wp.vec3)):
    s = wp.tid()
    p = root[s]
    P[s * K] = p
    L = length[s]
    seg = L / float(K - 1)
    att = wp.min(attach[s], L)
    rise = 0.5 * att
    sp0 = _surf(mesh, Nw, Fw, flow, p)
    d_prev = wp.normalize(sp0[1] * wp.cos(th0[s]) + sp0[2] * wp.sin(th0[s]))
    for k in range(1, K):
        arc = float(k) * seg
        sp = _surf(mesh, Nw, Fw, flow, p)
        c = sp[2]
        ph = _phi(phi, o, hgrid, p)
        g = _phi_grad(phi, o, hgrid, p)
        fl = _floor(offset[s], rise, margin, arc)
        d = d_prev
        if arc <= att:
            # comb along the flow at the strand's own height over the SDF (rising to its offset)
            cc = c - g * wp.dot(c, g)
            lc = wp.length(cc)
            if lc > 1.0e-9:
                cc = cc / lc
            else:
                cc = d_prev
            corr = wp.clamp((fl - ph) / seg, -1.0, 1.0)
            # the comb blends in over the first few mm (the root leaves the skin at its lift angle)
            w = wp.clamp(arc / wp.max(0.25 * att, 1.0e-6), 0.0, 1.0)
            d = wp.normalize(d_prev * (1.0 - w) + (cc + g * corr) * w)
        else:
            u = wp.clamp((arc - att) / wp.max(L - att, 1.0e-6), 0.0, 1.0)
            st = stiff0[s] * wp.pow(1.0 - u, stiff_pow)
            d = wp.normalize(d_prev * st + gdir * (1.0 - st))
        q = p + d * seg
        ph2 = _phi(phi, o, hgrid, q)
        if ph2 < fl:
            q = q + _phi_grad(phi, o, hgrid, q) * (fl - ph2)
        dd = q - p
        ld = wp.length(dd)
        if ld > 1.0e-12:
            d_prev = dd / ld
        p = q
        P[s * K + k] = p


@wp.kernel
def k_hang_relax(phi: wp.array3d(dtype=wp.float32), o: wp.vec3, hgrid: float, P: wp.array(dtype=wp.vec3),
                 length: wp.array(dtype=wp.float32), attach: wp.array(dtype=wp.float32),
                 offset: wp.array(dtype=wp.float32), gdir: wp.vec3, gstep: float, margin: float, iters: int,
                 bend: float, K: int):
    s = wp.tid()
    L = length[s]
    seg = L / float(K - 1)
    att = wp.min(attach[s], L)
    rise = 0.5 * att
    for it in range(iters):
        # gravity on the free part (none on the combed part: it lies where the comb put it)
        for k in range(1, K):
            arc = float(k) * seg
            x = wp.clamp((arc - 0.6 * att) / wp.max(0.4 * att, 1.0e-6), 0.0, 1.0)
            P[s * K + k] = P[s * K + k] + gdir * (gstep * x * x * (3.0 - 2.0 * x))
        # a light bending smoothing (keeps the drape from kinking where it leaves the skull)
        if bend > 0.0:
            for k in range(2, K - 1):
                a = P[s * K + k - 1]
                b = P[s * K + k + 1]
                P[s * K + k] = P[s * K + k] * (1.0 - bend) + (a + b) * (0.5 * bend)
        # follow the leader from the root: segment lengths restored, the SDF floor
        prev = P[s * K]
        for k in range(1, K):
            p = P[s * K + k]
            dd = p - prev
            ld = wp.length(dd)
            if ld > 1.0e-12:
                p = prev + dd * (seg / ld)
            fl = _floor(offset[s], rise, margin, float(k) * seg)
            ph = _phi(phi, o, hgrid, p)
            if ph < fl:
                p = p + _phi_grad(phi, o, hgrid, p) * (fl - ph)
                dd = p - prev
                ld = wp.length(dd)
                if ld > 1.0e-12:
                    p = prev + dd * (seg / ld)
            P[s * K + k] = p
            prev = p


@wp.kernel
def k_sdf_push(phi: wp.array3d(dtype=wp.float32), o: wp.vec3, hgrid: float, P: wp.array(dtype=wp.vec3),
               length: wp.array(dtype=wp.float32), attach: wp.array(dtype=wp.float32),
               offset: wp.array(dtype=wp.float32), margin: float, K: int, fscale: wp.array(dtype=wp.float32)):
    """every point at or above its strand's floor over the SDF (pushed along the gradient), lengths restored.
    (B3c) fscale: a per-POINT scale of the strand's offset (S * K; ones = as before), so a floor can change along a
    strand (the side's hair holds its offset over the temple and drops it over the protruding ear)"""
    s = wp.tid()
    L = length[s]
    seg = L / float(K - 1)
    rise = 0.5 * wp.min(attach[s], L)
    prev = P[s * K]
    for k in range(1, K):
        p = P[s * K + k]
        fl = _floor(offset[s] * fscale[s * K + k], rise, margin, float(k) * seg)
        pushed = p
        for _a in range(4):
            for _r in range(3):
                ph = _phi(phi, o, hgrid, p)
                if ph < fl:
                    p = p + _phi_grad(phi, o, hgrid, p) * (fl - ph)
            pushed = p
            dd = p - prev
            ld = wp.length(dd)
            if ld > 1.0e-12:
                p = prev + dd * (seg / ld)
        # (g03) where restoring the length takes the point back inside (a concave corner next to the root: the nape),
        # the pushed point stands: a segment a little long beats a point in the skin
        if _phi(phi, o, hgrid, p) < 0.0:
            p = pushed
        P[s * K + k] = p
        prev = p


def hang(surf, sdf, root, length, attach, offset, th0, stiff0, stiff_pow, K, gdir=(0.0, -1.0, 0.0), margin=1.0e-3):
    """(B3) grow hanging strands (see k_hang); returns a device array (S * K) of vec3"""
    d = surf.device
    S = len(root)
    P = wp.zeros(S * K, dtype=wp.vec3, device=d)
    if S == 0:
        return P
    wp.launch(k_hang, dim=S, device=d,
              inputs=[*surf.args(), *sdf.args(), wp.array(np.asarray(root, np.float32), dtype=wp.vec3, device=d),
                      _f32(length, d), _f32(attach, d), _f32(offset, d), _f32(th0, d), _f32(stiff0, d),
                      float(stiff_pow), wp.vec3(*[float(x) for x in gdir]), float(margin), int(K), P])
    return P


def hang_relax(sdf, P, length, attach, offset, K, gdir=(0.0, -1.0, 0.0), gstep=1.0e-3, margin=1.0e-3, iters=40,
               bend=0.15):
    S = P.shape[0] // K
    if S == 0:
        return
    d = P.device
    wp.launch(k_hang_relax, dim=S, device=d,
              inputs=[*sdf.args(), P, _f32(length, d), _f32(attach, d), _f32(offset, d),
                      wp.vec3(*[float(x) for x in gdir]), float(gstep), float(margin), int(iters), float(bend), int(K)])


def sdf_push(sdf, P, length, attach, offset, K, margin=1.0e-3, fscale=None):
    S = P.shape[0] // K
    if S == 0:
        return
    d = P.device
    fs = np.ones(S * K, np.float32) if fscale is None else np.asarray(fscale, np.float32).reshape(-1)
    wp.launch(k_sdf_push, dim=S, device=d,
              inputs=[*sdf.args(), P, _f32(length, d), _f32(attach, d), _f32(offset, d), float(margin), int(K),
                      _f32(fs, d)])


def resample_paths(P, Lnew):
    """(B3) strands (S, K, 3) each resampled to K points at equal arc length over [0, Lnew_s] along its own path"""
    S, K = P.shape[:2]
    seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
    arc = np.concatenate([np.zeros((S, 1)), np.cumsum(seg, 1)], 1)
    tq = np.linspace(0.0, 1.0, K)
    out = np.empty_like(P)
    for s in range(S):
        q = tq * min(Lnew[s], arc[s, -1])
        for d in range(3):
            out[s, :, d] = np.interp(q, arc[s], P[s, :, d])
    return out


def cut_strands(P, center, curve, jitter, mirror=True):
    """(B3) the cut line: per strand, the arc length where it first falls below the line's height (metres over the head
    centre's height, per azimuth: curve [[az_deg, dy_mm], ...], |az| when mirrored) plus its jitter (metres); returns
    (new lengths, cut mask). A strand that never falls below the line keeps its length"""
    S, K = P.shape[:2]
    rel = P - np.asarray(center)[None, None, :]
    az = np.degrees(np.arctan2(rel[..., 0], rel[..., 2]))
    if mirror:
        az = np.abs(az)
    cv = np.asarray(curve, np.float64)
    ycut = np.interp(az, cv[:, 0], cv[:, 1]) * 1e-3 + jitter[:, None]
    below = rel[..., 1] < ycut
    below[:, 0] = False
    seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
    arc = np.concatenate([np.zeros((S, 1)), np.cumsum(seg, 1)], 1)
    hit = below.any(1)
    k1 = np.argmax(below, axis=1)
    L = arc[:, -1].copy()
    rows = np.nonzero(hit)[0]
    if len(rows):
        k1h = k1[rows]
        y0 = rel[rows, k1h - 1, 1] - ycut[rows, k1h - 1]
        y1 = rel[rows, k1h, 1] - ycut[rows, k1h]
        f = np.clip(y0 / np.maximum(y0 - y1, 1e-12), 0.0, 1.0)
        L[rows] = arc[rows, k1h - 1] + f * seg[rows, k1h - 1]
    return L, hit
