"""Design measurement (not the implementation): does a direction-free slope estimate remove the grid combing of the
research prototype's stream-power runs (research.md section 8.2, runs I / J2)?

Same model and parameters as research/proto/spl_gather.py (m = 0.5, n = 1, MFD area by one Jacobi gather per step,
nonlinear creep, uplift + rough dome start), with three changes, each switchable:
  slope  'd8'   : the research's steepest-descent slope over the 8 neighbours (underestimates |grad h| by up to 7.6 %
                  for planes between the 8 directions, so valleys along the 8 directions cut faster)
         'iso'  : max(Rouy-Tourin upwind |grad h| from the 4 one-sided differences, the D8 steepest slope): exact for
                  a plane in any orientation, and still the along-channel slope of a one-cell channel on a diagonal
  area   'mfd1' : weights ~ downhill slope (research)
         'quinn': weights ~ downhill slope^1.1 x contour length (0.5 cardinal, 0.354 diagonal; Quinn et al. 1991)
  creep  'face4': the research's 4-face nonlinear creep
         'iso9' : the same flux law on 8 neighbours with the isotropic 9-point weights (2/3 cardinal, 1/6 diagonal)
  edge   'min'  : uplift fade = min(distance to each edge) (the research's: 45-degree creases)
         'smooth': product of two smoothsteps (no creases)
Incision is clamped at the LOWEST neighbour (iso) or the steepest receiver (d8).

    python spl_iso.py <tag> <slope> <area> <creep> <edge> [N steps D K Umax dt k_noise]
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

RES = r'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/terrain_new/research'
sys.path.insert(0, os.path.join(RES, 'tools'))
sys.path.insert(0, os.path.join(RES, 'proto'))
import terrain_metrics as TM  # noqa: E402
from spl_gather import spectral_noise  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
OFF = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
OPP = [7, 6, 5, 4, 3, 2, 1, 0]
CARD = [1, 3, 4, 6]


def sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def creep(h, dx, D, Sc, dt, cap, mode):
    w = np.array([1 / 6, 2 / 3, 1 / 6, 2 / 3, 2 / 3, 1 / 6, 2 / 3, 1 / 6])
    dist = np.array([np.hypot(a, b) for a, b in OFF])
    k_eff = (4.0 if mode == 'face4' else 10.0 / 3.0)
    sub = int(np.ceil(dt / (0.9 * dx * dx / (k_eff * D * cap))))
    ddt = dt / sub
    N0, N1 = h.shape
    for _ in range(sub):
        P = np.pad(h, 1, mode='edge')
        if mode == 'face4':
            gx = (P[1:-1, 2:] - P[1:-1, 1:-1]) / dx
            gy = (P[2:, 1:-1] - P[1:-1, 1:-1]) / dx
            Sce = 0.5 * (Sc + np.pad(Sc, 1, mode='edge')[1:-1, 2:])
            Scs = 0.5 * (Sc + np.pad(Sc, 1, mode='edge')[2:, 1:-1])
            qx = D * gx * np.minimum(1.0 / np.maximum(1.0 - (gx / Sce) ** 2, 1e-9), cap)
            qy = D * gy * np.minimum(1.0 / np.maximum(1.0 - (gy / Scs) ** 2, 1e-9), cap)
            qxp = np.pad(qx, ((0, 0), (1, 0)))[:, :-1]
            qyp = np.pad(qy, ((1, 0), (0, 0)))[:-1, :]
            h = h + ddt * (qx - qxp + qy - qyp) / dx
        else:
            PS = np.pad(Sc, 1, mode='edge')
            acc = np.zeros_like(h)
            for k, (dr, dc) in enumerate(OFF):
                hk = P[1 + dr:1 + dr + N0, 1 + dc:1 + dc + N1]
                sck = 0.5 * (Sc + PS[1 + dr:1 + dr + N0, 1 + dc:1 + dc + N1])
                s = (hk - h) / (dist[k] * dx)
                f = np.minimum(1.0 / np.maximum(1.0 - (s / sck) ** 2, 1e-9), cap)
                acc += w[k] * f * (hk - h)
            h = h + ddt * D * acc / (dx * dx)
    return h


def run(slope='iso', area='quinn', creep_mode='iso9', edge='smooth', N=256, steps=2500, size_m=20000.0, seed=3,
        D=0.04, K=1e-5, Umax=3e-3, dt=1000.0, k_noise=0.6, cap=5.0):
    dx = size_m / N
    dist = np.array([np.hypot(dr, dc) * dx for dr, dc in OFF])
    clen = np.array([0.354 if dr and dc else 0.5 for dr, dc in OFF])
    yy, xx = np.mgrid[0:N, 0:N] / (N - 1)
    if edge == 'min':
        fade = np.clip(np.minimum.reduce([xx, 1 - xx, yy, 1 - yy]) / 0.18, 0, 1) ** 1.5
    else:
        fade = sm(0.0, 0.18, np.minimum(xx, 1 - xx)) * sm(0.0, 0.18, np.minimum(yy, 1 - yy))
    U = Umax * (0.35 + 0.65 * spectral_noise(N, 4.0, seed, kmax=6)) * fade
    U *= 0.8 + 0.4 * spectral_noise(N, 2.5, seed + 4, kmax=48)
    Sc = np.tan(np.radians(36.0)) * (0.85 + 0.3 * spectral_noise(N, 3.0, seed + 1, kmax=40))
    if k_noise > 0:
        K = K * (1.0 + k_noise * (2.0 * spectral_noise(N, 2.0, seed + 6, kmax=64) - 1.0))
    h = 600.0 * U / U.max() * (0.6 + 0.4 * spectral_noise(N, 3.0, seed + 5))
    h[0, :] = h[-1, :] = h[:, 0] = h[:, -1] = 0.0
    A = np.full((N, N), dx * dx)
    t0 = time.perf_counter()
    for it in range(steps):
        P = np.pad(h, 1, mode='constant', constant_values=1e9)
        nb = [P[1 + dr:1 + dr + N, 1 + dc:1 + dc + N] for dr, dc in OFF]
        s = np.stack([(h - nb[k]) / dist[k] for k in range(8)])
        if area == 'quinn':
            w = np.maximum(s, 0.0) ** 1.1 * clen[:, None, None]
        else:
            w = np.maximum(s, 0.0)
        tot = w.sum(0)
        w /= np.where(tot > 0, tot, 1.0)
        Qp = np.pad(w * A[None], ((0, 0), (1, 1), (1, 1)))
        A = np.full((N, N), dx * dx)
        for k, (dr, dc) in enumerate(OFF):
            A += Qp[OPP[k], 1 + dr:1 + dr + N, 1 + dc:1 + dc + N]
        kr = s.argmax(0)
        S8 = np.maximum(np.take_along_axis(s, kr[None], 0)[0], 0.0)
        if slope == 'iso':
            sx = np.maximum(np.maximum(s[3], s[4]), 0.0)          # drops to W and E, already / dx
            sy = np.maximum(np.maximum(s[1], s[6]), 0.0)          # drops to N and S
            S = np.maximum(np.hypot(sx, sy), S8)
            floor = np.min(np.stack(nb), 0)                       # never below the lowest neighbour
        else:
            S = S8
            floor = h - S8 * dist[kr]
        h = np.maximum(h - dt * K * np.sqrt(A) * S, np.minimum(floor, h)) + dt * U
        h = creep(h, dx, D, Sc, dt, cap, creep_mode)
        h[0, :] = h[-1, :] = h[:, 0] = h[:, -1] = 0.0
        if (it + 1) % 500 == 0:
            print(f'step {it + 1}: max {h.max():.0f} m, {(time.perf_counter() - t0) / (it + 1) * 1000:.1f} ms/step',
                  flush=True)
    return h, A, dx, time.perf_counter() - t0


if __name__ == '__main__':
    tag, slope, area, creep_mode, edge = sys.argv[1:6]
    extra = [float(v) for v in sys.argv[6:]]
    keys = ['N', 'steps', 'D', 'K', 'Umax', 'dt', 'k_noise']
    kw = {k: (int(v) if k in ('N', 'steps') else v) for k, v in zip(keys, extra)}
    os.makedirs(OUT, exist_ok=True)
    h, A, dx, sec = run(slope, area, creep_mode, edge, **kw)
    np.savez_compressed(os.path.join(OUT, tag + '.npz'), height=h.astype(np.float32), area=A.astype(np.float32), dx=dx)
    Image.fromarray(TM.hillshade(h, dx)).save(os.path.join(OUT, f'hs_{tag}.png'))
    met = TM.metrics(h, dx)
    met.update({'seconds': round(sec, 1), 'config': [slope, area, creep_mode, edge, kw]})
    with open(os.path.join(OUT, tag + '.json'), 'w') as f:
        json.dump(met, f, indent=1)
    print(json.dumps(met))
