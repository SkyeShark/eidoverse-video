"""THE SHOES: a plain-toe DERBY (the old outfit's shoes, a leather upper on a rubber-and-leather sole), built on the body's
own foot at its phenotype (refs/shoes: the Bluecher photo).

  the LAST:   the foot's signed distance on a 1.5 mm grid (the welded skin, the leg clipped at the collar), blurred
              (sigma 6 mm: the toes merge into one toe box, the ankle's bones soften) and offset outward 4 mm (sock +
              leather + lining), the toe region drawn 14 mm forward (a shoe is longer than the foot it holds)
  the UPPER:  a designed low, not a meshed field: RINGS across the foot's axis (heel -> toe, closer at both ends), each a
              ray-cast section of the last at fixed angles round its centroid, fan caps at heel and toe; then CUT by
              the welt's plane (the sole takes everything below) and by the throat (a vertical elliptic cylinder round
              the ankle: the derby's opening, a natural curve where it meets the instep)
  the SOLE:   the welt's boundary loop pushed out 3 mm (the welt's ledge), dropped to the tread (forefoot 10 mm,
              heel 14 mm under the foot: the slope is the toe spring), a flat tread cap
The lacing, the quarters over the vamp, the eyelets, the counter's seam and the welt's stitching are the bake's height
field (maps.py), not geometry.
"""
import numpy as np
import warp as wp
from scipy import ndimage

from . import meshops as mo

SHOE = dict(grid=0.0015, blur=0.006, offset=0.004, toe_ext=0.014, welt_up=0.006, welt_out=0.003, sole_fore=0.010,
            sole_heel=0.014, rings=40, around=44, throat_rx=0.044, throat_rz=0.050, collar_y=0.068, throat_fwd=0.012)


def _sdf_grid(Vw, Fw, lo, hi, h):
    wp.init()
    dev = 'cuda:0' if wp.is_cuda_available() else 'cpu'
    m = wp.Mesh(points=wp.array(Vw.astype(np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(Fw.astype(np.int32).ravel(), dtype=wp.int32, device=dev))
    n = np.ceil((hi - lo) / h).astype(int) + 1
    xs = [lo[k] + h * np.arange(n[k]) for k in range(3)]
    P = np.stack(np.meshgrid(*xs, indexing='ij'), -1).reshape(-1, 3)
    out = wp.zeros(len(P), float, device=dev)
    wp.launch(_k_sd, len(P), [m.id, wp.array(P.astype(np.float32), dtype=wp.vec3, device=dev), out], device=dev)
    return out.numpy().reshape(n), xs


@wp.kernel
def _k_sd(mesh: wp.uint64, p: wp.array(dtype=wp.vec3), out: wp.array(dtype=float)):
    i = wp.tid()
    r = wp.mesh_query_point_sign_normal(mesh, p[i], 1.0)
    if r.result:
        c = wp.mesh_eval_position(mesh, r.face, r.u, r.v)
        out[i] = r.sign * wp.length(p[i] - c)
    else:
        out[i] = 1.0


class Last:
    def __init__(self, fr, side='L', p=SHOE):
        Vw = fr.Vw
        sg = 1.0 if side == 'L' else -1.0
        foot = (Vw[:, 1] < 0.16) & (np.sign(Vw[:, 0]) == sg) & (np.abs(Vw[:, 0]) > 0.03)
        Pf = Vw[foot & (Vw[:, 1] < 0.10)]
        self.heel = Pf[np.argmin(Pf[:, 2])]
        self.toe = Pf[np.argmax(Pf[:, 2])]
        self.floor = float(Vw[foot, 1].min())
        ank = Vw[fr.ring_w[f'ankle_{side}']]
        self.ankle = ank.mean(0)
        lo = np.array([Pf[:, 0].min() - 0.03, self.floor - 0.02, self.heel[2] - 0.025])
        hi = np.array([Pf[:, 0].max() + 0.03, 0.15, self.toe[2] + p['toe_ext'] + 0.03])
        sd, xs = _sdf_grid(Vw, fr.Fw, lo, hi, p['grid'])
        # the leg clipped at the collar's height: above it, outside
        Y = xs[1][None, :, None]
        sd = np.maximum(sd, Y - (self.floor + p['collar_y'] + 0.03))
        sd = ndimage.gaussian_filter(sd, p['blur'] / p['grid'])
        self.sd, self.xs, self.lo, self.h = sd - p['offset'], xs, lo, p['grid']
        a = self.toe - self.heel
        a[1] = 0.0
        self.axis = a / np.linalg.norm(a)
        self.side_v = np.cross([0.0, 1.0, 0.0], self.axis)
        self.length = float(np.linalg.norm((self.toe - self.heel)[[0, 2]]))
        self.p = p
        self.sg = sg

    def sample(self, P):
        """the last's field at P (the toe drawn forward: the front third read from behind)"""
        P = np.asarray(P, float).copy()
        t = (P - self.heel) @ self.axis
        t0 = 0.62 * self.length
        ext = self.p['toe_ext']
        u = np.clip((t - t0) / (self.length + ext - t0), 0.0, 1.0)
        P = P - self.axis[None, :] * (ext * u)[:, None]
        g = (P - self.lo) / self.h
        # the toe box: 5 mm more room over the toes (a shoe's toe stands above the toes, never on them)
        return ndimage.map_coordinates(self.sd, g.T, order=1, mode='constant', cval=1.0) - 0.005 * np.sin(np.pi * 0.5 * u)

    def welt_y(self, P):
        """the welt's height: level under the foot, rising 9 mm over the toe's last fifth (the toe spring)"""
        t = ((np.asarray(P) - self.heel) @ self.axis) / self.length
        return self.floor + self.p['welt_up'] + 0.009 * np.clip((t - 0.8) / 0.25, 0, 1) ** 2


def upper(fr, side='L', p=SHOE):
    L = Last(fr, side, p)
    nr, na = p['rings'], p['around']
    s = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, nr + 2))[1:-1]          # closer at the heel and the toe
    T = -0.012 + s * (L.length + p['toe_ext'] + 0.024)
    rings, cents = [], []
    phi = np.linspace(0.0, 2 * np.pi, na, endpoint=False)
    for t in T:
        base = L.heel + L.axis * t
        # the section's centre: the inside points' centroid on a coarse (side, y) grid
        sv, yv = np.meshgrid(np.linspace(-0.08, 0.08, 41), np.linspace(L.floor - 0.01, L.floor + 0.13, 36))
        P = base[None, :] * [1, 0, 1] + L.side_v[None, :] * sv.reshape(-1, 1) + np.array([0, 1, 0]) * yv.reshape(-1, 1)
        ins = L.sample(P) < 0
        if ins.sum() < 6:
            rings.append(None)
            continue
        c = P[ins].mean(0)
        dirs = np.cos(phi)[:, None] * np.array([0, 1.0, 0]) + np.sin(phi)[:, None] * L.side_v[None, :]
        r = np.linspace(0.0, 0.12, 481)
        Q = c[None, None, :] + dirs[:, None, :] * r[None, :, None]
        f = L.sample(Q.reshape(-1, 3)).reshape(na, len(r))
        out = np.argmax(f > 0, axis=1)
        k = np.maximum(out, 1)
        f0, f1 = f[np.arange(na), k - 1], f[np.arange(na), k]
        rr = r[k - 1] + (r[k] - r[k - 1]) * (f0 / np.where(f0 - f1 == 0, -1e-9, f0 - f1))
        rings.append(c[None, :] + dirs * rr[:, None])
        cents.append(c)
    R = [x for x in rings if x is not None]
    V = np.concatenate(R)
    F = []
    for i in range(len(R) - 1):
        for j in range(na):
            a, b = i * na + j, i * na + (j + 1) % na
            c, d = a + na, b + na
            F += [(a, c, b), (b, c, d)]
    # caps: the heel and toe tips
    heel_tip = R[0].mean(0) - L.axis * 0.004
    toe_tip = R[-1].mean(0) + L.axis * 0.004
    hi, ti = len(V), len(V) + 1
    V = np.concatenate([V, [heel_tip, toe_tip]])
    last0 = (len(R) - 1) * na
    for j in range(na):
        F.append((hi, j, (j + 1) % na))
        F.append((ti, last0 + (j + 1) % na, last0 + j))
    F = np.array(F, np.int64)
    # orientation: outward
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    cen = V.mean(0)
    if np.sum(np.einsum('ij,ij->i', n, V[F].mean(1) - cen)) < 0:
        F = F[:, ::-1]
    # the welt plane and the throat
    V, F, _, _ = mo.cut(V, F, V[:, 1] - L.welt_y(V))
    ac = L.ankle + L.axis * p['throat_fwd'] * 0.0
    d = V - ac
    ex = d @ L.side_v
    ez = d @ L.axis
    fwd = np.where(ez > 0, p['throat_rz'] + p['throat_fwd'], p['throat_rz'])
    ell = np.sqrt((ex / p['throat_rx']) ** 2 + (ez / fwd) ** 2) - 1.0
    yc = L.floor + p['collar_y'] - 0.018 * np.clip(-ez / p['throat_rz'], 0, 1) ** 0 * 0.0
    keep = np.maximum(ell * 0.05, yc - V[:, 1])
    V, F, _, _ = mo.cut(V, F, keep)
    lab = mo.components(F, len(V))
    big = np.bincount(lab[F[:, 0]]).argmax()
    V, F, _ = mo.compact(V, F[lab[F[:, 0]] == big])[:3]
    return V, F, L


def sole(L, Vu, Fu, p=SHOE):
    """the sole from the upper's welt loop: the ledge out, the edge down to the tread (toe spring), a flat cap"""
    loops = mo.boundary_loops(Fu)
    wl = min(loops, key=lambda l: Vu[l, 1].mean())
    W = Vu[wl]
    c = W.mean(0)
    out = W - c
    out[:, 1] = 0
    out /= np.linalg.norm(out, axis=1, keepdims=True)
    t = ((W - L.heel) @ L.axis) / L.length
    drop = p['sole_heel'] + (p['sole_fore'] - p['sole_heel']) * np.clip((t - 0.25) / 0.5, 0, 1)
    # the tread follows the welt's toe spring
    tread_y = L.welt_y(W) - p['welt_up'] - drop
    rows = [W, W + out * p['welt_out'], W + out * p['welt_out'] + [0, -0.002, 0]]
    rows.append(np.column_stack([rows[-1][:, 0], tread_y + 0.002, rows[-1][:, 2]]))
    rows.append(np.column_stack([W[:, 0] + out[:, 0] * (p['welt_out'] - 0.0015), tread_y,
                                 W[:, 2] + out[:, 2] * (p['welt_out'] - 0.0015)]))
    n = len(W)
    V = np.concatenate(rows)
    F = []
    for i in range(len(rows) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            F += [(a, a + n, b), (b, a + n, b + n)]
    cen = np.array([rows[-1][:, 0].mean(), rows[-1][:, 1].mean(), rows[-1][:, 2].mean()])
    ci = len(V)
    V = np.concatenate([V, [cen]])
    base = (len(rows) - 1) * n
    for j in range(n):
        F.append((ci, base + (j + 1) % n, base + j))
    F = np.array(F, np.int64)
    nrm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.sum(np.einsum('ij,ij->i', nrm, V[F].mean(1) - V.mean(0))) < 0:
        F = F[:, ::-1]
    return V, F


def build(fr, side='L', p=SHOE):
    Vu, Fu, L = upper(fr, side, p)
    Vs, Fs = sole(L, Vu, Fu, p)
    return dict(upper=(Vu, Fu), sole=(Vs, Fs), last=L, tread_y=float(Vs[:, 1].min()))
