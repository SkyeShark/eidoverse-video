"""Research prototype (not the implementation): the same physics as spl_gather.py (stream power + uplift + nonlinear
hillslope creep), solved the FastScape way (Braun & Willett 2013): single steepest-descent receivers, exact drainage
area by accumulating down the receiver tree, and the implicit O(n) height update
    h_i <- (h_i + U dt + F_i h_receiver) / (1 + F_i),   F_i = K A_i^m dt / distance_i   (n = 1)
which is stable at any dt. The tree walks are vectorised by tree depth (pointer jumping gives every cell its number
of hops to the outlet; each depth level is then one numpy operation), so there is no per-cell Python loop.
Single-cell pits are lifted to their lowest neighbour each step; bigger closed basins stay outlets until captured.

    python spl_implicit.py [N] [steps] [dt_years] [D]
        writes out/spl_implicit_<N>_D<D>.npz/.json and out/hillshade_spl_implicit_<N>_D<D>.png
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import terrain_metrics as TM  # noqa: E402
from spl_gather import OFF, spectral_noise, shifts, nonlinear_diffusion, reference_op_ms  # noqa: E402

OUT = os.path.join(HERE, 'out')


def receivers(h, dist, boundary):
    N = h.shape[0]
    nb = shifts(np.pad(h, 1, mode='constant', constant_values=np.inf), N, N)
    s = np.stack([(h - nb[k]) / dist[k] for k in range(8)])
    kr = s.argmax(0)
    smax = np.take_along_axis(s, kr[None], 0)[0]
    dr = np.array([o[0] for o in OFF])[kr]
    dc = np.array([o[1] for o in OFF])[kr]
    rr, cc = np.mgrid[0:N, 0:N]
    rcv = ((rr + dr) * N + (cc + dc)).ravel()
    d = dist[kr].ravel()
    root = (boundary | (smax <= 0)).ravel()
    idx = np.arange(N * N)
    rcv[root] = idx[root]
    d[root] = 1.0
    return rcv, d, root


def levels(rcv):
    """Hops from every cell to its outlet by pointer jumping, then the cells grouped by hop count."""
    idx = np.arange(rcv.size)
    anc = rcv.copy()
    depth = (anc != idx).astype(np.int64)
    while True:
        nxt = anc[anc]
        if np.array_equal(nxt, anc):
            break
        depth = depth + depth[anc]
        anc = nxt
    order = np.argsort(depth, kind='stable')
    off = np.concatenate([[0], np.cumsum(np.bincount(depth))])
    return order, off


def run(N=512, steps=300, dt=10000.0, D=0.5, cap=5.0, size_m=20000.0, seed=3, log_every=50):
    dx = size_m / N
    dist = np.array([np.hypot(dr, dc) * dx for dr, dc in OFF])
    yy, xx = np.mgrid[0:N, 0:N] / (N - 1)
    edge = np.clip(np.minimum.reduce([xx, 1 - xx, yy, 1 - yy]) / 0.18, 0, 1) ** 1.5
    U = 1e-3 * (0.35 + 0.65 * spectral_noise(N, 4.0, seed, kmax=6)) * edge
    U *= 0.8 + 0.4 * spectral_noise(N, 2.5, seed + 4, kmax=48)
    Sc = np.tan(np.radians(36.0)) * (0.85 + 0.3 * spectral_noise(N, 3.0, seed + 1, kmax=40))
    K, m = 4e-6, 0.5
    h = 30.0 * spectral_noise(N, 2.5, seed + 2)
    boundary = np.zeros((N, N), bool)
    boundary[0, :] = boundary[-1, :] = boundary[:, 0] = boundary[:, -1] = True
    h[boundary] = 0.0
    Uf = U.ravel()
    t0 = time.perf_counter()
    for it in range(steps):
        nb = shifts(np.pad(h, 1, mode='constant', constant_values=np.inf), N, N)
        low = np.min(np.stack(nb), 0)
        pit = (low >= h) & ~boundary
        h = np.where(pit, low + 1e-3, h)                       # single-cell pits drain over their lowest rim
        rcv, d, root = receivers(h, dist, boundary)
        order, off = levels(rcv)
        A = np.full(N * N, dx * dx)
        for L in range(len(off) - 2, 0, -1):                   # accumulate area from the tips down
            ids = order[off[L]:off[L + 1]]
            np.add.at(A, rcv[ids], A[ids])
        F = K * A ** m * dt / d
        hf = h.ravel() + dt * Uf
        hf[boundary.ravel()] = 0.0
        for L in range(1, len(off) - 1):                       # implicit update from the outlets up
            ids = order[off[L]:off[L + 1]]
            hf[ids] = (hf[ids] + F[ids] * hf[rcv[ids]]) / (1.0 + F[ids])
        h = nonlinear_diffusion(hf.reshape(N, N), dx, D, Sc, dt, cap)
        h[boundary] = 0.0
        if log_every and (it + 1) % log_every == 0:
            print(f'step {it + 1} ({(it + 1) * dt / 1e6:.2f} Myr): max {h.max():.0f} m, mean {h.mean():.0f} m, '
                  f'{len(off) - 1} levels, {(time.perf_counter() - t0) / (it + 1) * 1000:.0f} ms/step', flush=True)
    return h, A.reshape(N, N), dx, time.perf_counter() - t0


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 512
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    dt = float(sys.argv[3]) if len(sys.argv) > 3 else 10000.0
    D = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
    os.makedirs(OUT, exist_ok=True)
    ref0 = reference_op_ms(N)
    h, A, dx, sec = run(N, steps, dt, D)
    ref1 = reference_op_ms(N)
    tag = f'spl_implicit_{N}_D{D:g}'
    np.savez_compressed(os.path.join(OUT, tag + '.npz'), height=h.astype(np.float32), area=A.astype(np.float32),
                        dx=dx)
    Image.fromarray(TM.hillshade(h, dx)).save(os.path.join(OUT, f'hillshade_{tag}.png'))
    met = TM.metrics(h, dx)
    ms = sec / steps * 1000
    met.update({'steps': steps, 'dt_years': dt, 'seconds': round(sec, 1), 'ms_per_step': round(ms, 1),
                'plain_op_ms': round(0.5 * (ref0 + ref1), 3),
                'step_cost_in_plain_ops': round(ms / (0.5 * (ref0 + ref1)), 0)})
    with open(os.path.join(OUT, tag + '.json'), 'w') as f:
        json.dump(met, f, indent=1)
    print(json.dumps(met, indent=1))
