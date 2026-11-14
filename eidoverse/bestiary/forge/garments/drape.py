"""THE DRAPE: a position-based cloth solve in Warp (Warp 1.18 here has no warp.sim and Newton is not installed:
HUMAN_PLAN §6.8's first decision, made: an XPBD-style kernel set of our own).

The cloth is the garment's triangle mesh, CUT to its rest shape (pattern.rest_shape on the T rest: every edge's rest
length and every bending pair's rest distance read there). It starts at that rest shape on the T body; the body is then
moved to the drape pose (the arms lowered to the A-pose over the first `ramp` seconds, the collider refitted every
frame) and the cloth follows under gravity until it settles. So the folds are the drape's own: the sleeve's fabric
gathering under a lowered arm, a straight trouser leg breaking on the shoe, a shirt hanging from the bust.

Per substep (Jacobi, averaged corrections, over-relaxed by omega):
    predict    v += g dt; v *= (1 - damping); x += v dt
    stretch    every edge back toward its rest length (stiffness k_stretch, a jersey a little softer)
    bend       every pair of vertices across an interior edge toward its rest distance (k_bend: the fabric's weight)
    self       vertices nearer than 2 x thickness and not neighbours in the rest shape pushed apart (a hash grid)
    collide    against every collider (the posed body, the shoes): inside or within thickness -> out along the face
               normal to thickness, with Coulomb-like friction on the tangential step (mu)
    pins       inverse mass 0 (a trouser's waistband held at the waist)
"""
import numpy as np
import warp as wp

from . import meshops as mo

wp.set_module_options({'enable_backward': False})

FABRIC = {   # k_stretch, k_bend, thickness (m), friction, areal density (kg/m2): measured weights of the cloths
    # high_detail (B2b): how much of the high drape's fine relief the bake keeps (a pressed poplin is smooth: round 1
    # baked all of it and the white shirt read crumpled and blotched)
    'jersey': dict(k_stretch=1.0, k_bend=0.035, thick=0.0015, mu=0.45, gsm=0.16, high_detail=0.75),
    'poplin': dict(k_stretch=1.0, k_bend=0.06, thick=0.0012, mu=0.35, gsm=0.12, high_detail=0.35),
    'twill': dict(k_stretch=1.0, k_bend=0.12, thick=0.0018, mu=0.40, gsm=0.28, high_detail=0.7),
}


@wp.kernel
def k_predict(x: wp.array(dtype=wp.vec3), v: wp.array(dtype=wp.vec3), xp: wp.array(dtype=wp.vec3),
              w: wp.array(dtype=float), g: wp.vec3, dt: float, damp: float):
    i = wp.tid()
    xp[i] = x[i]
    if w[i] > 0.0:
        vi = (v[i] + g * dt) * (1.0 - damp)
        v[i] = vi
        x[i] = x[i] + vi * dt


@wp.kernel
def k_dist(x: wp.array(dtype=wp.vec3), w: wp.array(dtype=float), pairs: wp.array(dtype=wp.vec2i),
           rest: wp.array(dtype=float), k: float, compress: float, delta: wp.array(dtype=wp.vec3),
           cnt: wp.array(dtype=float)):
    c = wp.tid()
    i = pairs[c][0]
    j = pairs[c][1]
    wi = w[i]
    wj = w[j]
    if wi + wj <= 0.0:
        return
    d = x[i] - x[j]
    L = wp.length(d)
    if L < 1.0e-9:
        return
    e = L - rest[c]
    s = k
    if e < 0.0:
        s = k * compress          # cloth buckles rather than resisting compression
    corr = d * (s * e / (L * (wi + wj)))
    wp.atomic_add(delta, i, -corr * wi)
    wp.atomic_add(delta, j, corr * wj)
    wp.atomic_add(cnt, i, 1.0)
    wp.atomic_add(cnt, j, 1.0)


@wp.kernel
def k_apply(x: wp.array(dtype=wp.vec3), delta: wp.array(dtype=wp.vec3), cnt: wp.array(dtype=float), omega: float):
    i = wp.tid()
    if cnt[i] > 0.0:
        x[i] = x[i] + delta[i] * (omega / cnt[i])
    delta[i] = wp.vec3(0.0)
    cnt[i] = 0.0


@wp.kernel
def k_self(grid: wp.uint64, x: wp.array(dtype=wp.vec3), xr: wp.array(dtype=wp.vec3), w: wp.array(dtype=float),
           r: float, rest_far: float, delta: wp.array(dtype=wp.vec3), cnt: wp.array(dtype=float)):
    i = wp.tid()
    p = x[i]
    q = wp.hash_grid_query(grid, p, r)
    j = int(0)
    while wp.hash_grid_query_next(q, j):
        if j != i:
            d = p - x[j]
            L = wp.length(d)
            if L < r and L > 1.0e-9 and wp.length(xr[i] - xr[j]) > rest_far:
                wp.atomic_add(delta, i, d * (0.5 * (r - L) / L))
                wp.atomic_add(cnt, i, 1.0)


@wp.kernel
def k_collide(mesh: wp.uint64, x: wp.array(dtype=wp.vec3), xp: wp.array(dtype=wp.vec3), w: wp.array(dtype=float),
              th: float, mu: float, hit: wp.array(dtype=int)):
    i = wp.tid()
    if w[i] <= 0.0:
        return
    p = x[i]
    r = wp.mesh_query_point_sign_normal(mesh, p, th * 6.0)
    if r.result:
        c = wp.mesh_eval_position(mesh, r.face, r.u, r.v)
        n = wp.mesh_eval_face_normal(mesh, r.face)
        sd = wp.dot(p - c, n)
        if r.sign < 0.0:
            sd = -wp.length(p - c)
        if sd < th:
            pn = p + n * (th - sd)
            dx = pn - xp[i]
            dt = dx - n * wp.dot(dx, n)
            lt = wp.length(dt)
            # friction: the tangential step shrinks by mu (static below a small slip)
            if lt > 0.0:
                pn = pn - dt * wp.min(1.0, mu)
            x[i] = pn
            hit[i] = 1


@wp.kernel
def k_vel(x: wp.array(dtype=wp.vec3), xp: wp.array(dtype=wp.vec3), v: wp.array(dtype=wp.vec3), dt: float,
          vmax: float):
    i = wp.tid()
    vi = (x[i] - xp[i]) / dt
    s = wp.length(vi)
    if s > vmax:
        vi = vi * (vmax / s)
    v[i] = vi


@wp.kernel
def k_pin(x: wp.array(dtype=wp.vec3), w: wp.array(dtype=float), tgt: wp.array(dtype=wp.vec3), tether: float):
    i = wp.tid()
    if w[i] <= 0.0:
        x[i] = tgt[i]
    elif tether > 0.0:
        # the HIGH's tether: the fine drape keeps the low's large shape (its folds grow on it, it does not slide off)
        x[i] = x[i] + (tgt[i] - x[i]) * tether


def bend_pairs(F):
    """the vertices across every interior edge"""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    O = np.concatenate([F[:, 2], F[:, 0], F[:, 1]])
    key = np.sort(E, axis=1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    key, O = key[o], O[o]
    same = np.all(key[1:] == key[:-1], axis=1)
    idx = np.nonzero(same)[0]
    P = np.column_stack([O[idx], O[idx + 1]])
    return P[P[:, 0] != P[:, 1]]


class Collider:
    def __init__(self, V, F, dev):
        self.F = np.asarray(F, np.int32)
        self.pts = wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev)
        self.mesh = wp.Mesh(points=self.pts, indices=wp.array(self.F.ravel(), dtype=wp.int32, device=dev))

    def update(self, V):
        self.pts.assign(np.asarray(V, np.float32))
        self.mesh.refit()


def drape(X_rest, F, fabric, colliders, frames=150, fps=60, substeps=10, iters=16, ramp=(0.0, 1.0), pins=None,
          pin_target=None, damping=0.02, settle=60, self_collide=True, log=print, X_start=None, compress=0.15,
          tether=0.0):
    """X_rest (n, 3) the rest shape (lengths read here); colliders: list of (V_at(t) callable or array, F); t in [0, 1]
    over the ramp. Returns the draped positions and the solve's numbers."""
    wp.init()
    dev = 'cuda:0' if wp.is_cuda_available() else 'cpu'
    fb = FABRIC[fabric] if isinstance(fabric, str) else fabric
    n = len(X_rest)
    E = mo.edges(F)
    BP = bend_pairs(F)
    rest_e = np.linalg.norm(X_rest[E[:, 0]] - X_rest[E[:, 1]], axis=1)
    rest_b = np.linalg.norm(X_rest[BP[:, 0]] - X_rest[BP[:, 1]], axis=1)
    X0 = X_rest if X_start is None else X_start
    x = wp.array(np.asarray(X0, np.float32), dtype=wp.vec3, device=dev)
    xr = wp.array(np.asarray(X_rest, np.float32), dtype=wp.vec3, device=dev)
    v = wp.zeros(n, wp.vec3, device=dev)
    xp = wp.zeros(n, wp.vec3, device=dev)
    wv = np.ones(n, np.float32)
    if pins is not None:
        wv[pins] = 0.0
    w = wp.array(wv, dtype=float, device=dev)
    tgt = wp.array(np.asarray(X0 if pin_target is None else pin_target, np.float32), dtype=wp.vec3, device=dev)
    pe = wp.array(E.astype(np.int32), dtype=wp.vec2i, device=dev)
    pb = wp.array(BP.astype(np.int32), dtype=wp.vec2i, device=dev)
    re = wp.array(rest_e.astype(np.float32), dtype=float, device=dev)
    rb = wp.array(rest_b.astype(np.float32), dtype=float, device=dev)
    delta = wp.zeros(n, wp.vec3, device=dev)
    cnt = wp.zeros(n, float, device=dev)
    hit = wp.zeros(n, int, device=dev)
    cols = [(fn, Collider(fn(0.0) if callable(fn) else fn, Fc, dev)) for fn, Fc in colliders]
    th = fb['thick'] + 0.0015
    grid = wp.HashGrid(64, 64, 64, device=dev) if self_collide else None
    rself = 2.0 * fb['thick'] + 0.002
    dt = 1.0 / fps / substeps
    g = wp.vec3(0.0, -9.81, 0.0)
    total = frames + settle
    for fr in range(total):
        t = min(1.0, max(0.0, (fr / fps - ramp[0]) / max(1e-6, ramp[1] - ramp[0])))
        for fn, c in cols:
            if callable(fn):
                c.update(fn(t))
        damp = damping if fr < frames else 0.15
        for s in range(substeps):
            wp.launch(k_predict, n, [x, v, xp, w, g, dt, damp], device=dev)
            if grid is not None and s % 2 == 0:
                grid.build(x, rself)
            for it in range(iters):
                wp.launch(k_dist, len(E), [x, w, pe, re, fb['k_stretch'], compress, delta, cnt], device=dev)
                wp.launch(k_apply, n, [x, delta, cnt, 1.5], device=dev)
                wp.launch(k_dist, len(BP), [x, w, pb, rb, fb['k_bend'], 1.0, delta, cnt], device=dev)
                wp.launch(k_apply, n, [x, delta, cnt, 1.0], device=dev)
                if grid is not None and it == iters - 1:
                    wp.launch(k_self, n, [grid.id, x, xr, w, rself, 3.0 * rself, delta, cnt], device=dev)
                    wp.launch(k_apply, n, [x, delta, cnt, 1.0], device=dev)
                for fn, c in cols:
                    wp.launch(k_collide, n, [c.mesh.id, x, xp, w, th, fb['mu'], hit], device=dev)
                wp.launch(k_pin, n, [x, w, tgt, float(tether)], device=dev)
            wp.launch(k_vel, n, [x, xp, v, dt, 3.0], device=dev)
    X = x.numpy().astype(np.float64)
    L = np.linalg.norm(X[E[:, 0]] - X[E[:, 1]], axis=1)
    strain = L / np.maximum(rest_e, 1e-9) - 1.0
    sp = np.linalg.norm(v.numpy(), axis=1)
    rep = dict(vertices=n, edges=len(E), bend_pairs=len(BP), frames=total, substeps=substeps, iters=iters,
               strain_p1=float(np.percentile(strain, 1)), strain_p50=float(np.percentile(strain, 50)),
               strain_p99=float(np.percentile(strain, 99)), contact_share=float(hit.numpy().mean()),
               speed_max=float(sp.max()), fast_verts=int((sp > 0.5).sum()), fastest_at=X[int(np.argmax(sp))].tolist())
    log(f'[drape] {n} v, {len(E)} edges, {len(BP)} bend pairs, {total} frames x {substeps} x {iters}: strain p1 / p50 / '
        f'p99 {rep["strain_p1"]:.3f} / {rep["strain_p50"]:.3f} / {rep["strain_p99"]:.3f}, contact share '
        f'{rep["contact_share"]:.2f}, final speed max {rep["speed_max"]:.3f} m/s ({rep["fast_verts"]} over 0.5, the '
        f'fastest at {np.round(rep["fastest_at"], 3).tolist()})')
    return X, rep
