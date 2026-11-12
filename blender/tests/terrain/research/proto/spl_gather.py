"""Research prototype (not the implementation): stream-power river incision + tectonic uplift + threshold hillslopes
on a numpy grid, in the local 'gather' form of Schott et al.'s GPU shaders (github.com/H-Schott/StreamPowerErosion,
data/shaders/spe_shader.glsl, MIT). Per step every cell
  1. gathers drainage area from its upslope neighbours (multiple-flow-direction weights ~ slope^flow_p): one Jacobi
     iteration of the flow-accumulation equation per step, so area lags the terrain by a step (temporal coherence),
  2. cuts down by dt * K * A^m * S^n toward its steepest lower neighbour, never below that neighbour,
  3. rises by dt * U (the uplift map is what the artist paints: where mountains should be),
  4. hillslopes: nonlinear diffusion (Roering et al. 1999), flux = D S / (1 - (S/Sc)^2) on the cell faces, so
     slopes creep up to the threshold angle Sc and no further (capped at `cap` times the linear flux).
     limiter='minplus' instead clips every cell to (lowest neighbour + Sc * distance): cheap, but it is a chamfer
     distance, so every hillslope becomes a facet facing one of 8 directions (the zebra hillshade; kept to show it).
Every operation reads only the 3x3 neighbourhood, so each step is one fragment-shader pass per field on a GPU without
compute shaders (Blender 5.2), and plain array shifts in numpy.

    python spl_gather.py [N] [steps] [diffusion|minplus] [D] [K] [Umax] [dt] [flat|dome] [k_noise]
        e.g. run J of research.md section 8:  python spl_gather.py 256 2000 diffusion 0.04 2e-5 2e-3 1000 dome 0.6
        writes out/spl_gather_<tag>.npz/.json and out/hillshade_spl_gather_<tag>.png (tag from the arguments)
Units: metres and years (D m^2/yr, K 1/yr for m = 0.5, Umax m/yr, dt yr).
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

OUT = os.path.join(HERE, 'out')
OFF = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]     # (d row, d col)
OPP = [7, 6, 5, 4, 3, 2, 1, 0]                                                       # the opposite direction


def spectral_noise(n, beta, seed, kmax=None):
    """Periodic fractional-Brownian noise by spectral synthesis, power ~ |k|^-beta, scaled to [0, 1]."""
    rng = np.random.default_rng(seed)
    kx = np.fft.rfftfreq(n) * n
    ky = np.fft.fftfreq(n) * n
    k = np.hypot(ky[:, None], kx[None, :])
    k[0, 0] = 1.0
    amp = k ** (-beta / 2.0)
    if kmax is not None:
        amp[k > kmax] = 0.0
    amp[0, 0] = 0.0
    spec = amp * np.exp(1j * rng.uniform(0, 2 * np.pi, amp.shape))
    f = np.fft.irfft2(spec, s=(n, n))
    return (f - f.min()) / (f.max() - f.min())


def shifts(P, ny, nx):
    return [P[1 + dr:1 + dr + ny, 1 + dc:1 + dc + nx] for dr, dc in OFF]


def nonlinear_diffusion(h, dx, D, Sc, dt, cap=50.0):
    """Roering et al. (1999) hillslope creep on the 4 cell faces, explicit, sub-stepped to stay stable."""
    sub = int(np.ceil(dt / (0.9 * dx * dx / (4.0 * D * cap))))
    ddt = dt / sub
    for _ in range(sub):
        P = np.pad(h, 1, mode='edge')
        gx = (P[1:-1, 2:] - P[1:-1, 1:-1]) / dx                    # east face
        gy = (P[2:, 1:-1] - P[1:-1, 1:-1]) / dx                    # south face
        Sce = 0.5 * (Sc + np.pad(Sc, 1, mode='edge')[1:-1, 2:])
        Scs = 0.5 * (Sc + np.pad(Sc, 1, mode='edge')[2:, 1:-1])
        qx = D * gx * np.minimum(1.0 / np.maximum(1.0 - (gx / Sce) ** 2, 1e-9), cap)
        qy = D * gy * np.minimum(1.0 / np.maximum(1.0 - (gy / Scs) ** 2, 1e-9), cap)
        qxp = np.pad(qx, ((0, 0), (1, 0)))[:, :-1]                 # the west face of each cell
        qyp = np.pad(qy, ((1, 0), (0, 0)))[:-1, :]                 # the north face
        h = h + ddt * (qx - qxp + qy - qyp) / dx
    return h


def run(N=512, steps=1500, size_m=20000.0, seed=3, log_every=250, limiter='diffusion', D=0.5, cap=5.0,
        K=4e-6, Umax=1e-3, dt=2000.0, init='flat', k_noise=0.0):
    """D (m^2/yr) sets the valley spacing with K: the advection/diffusion length sqrt(D/K) (Perron et al. 2009)
    must span several cells, or a channel forms at every grid line (corduroy).
    init='flat' starts from 30 m of noise; init='dome' from the uplift map itself as a rough 600 m dome (the way
    World Machine / Gaea erode a primitive), which seeds an irregular network instead of parallel edge gullies."""
    dx = size_m / N
    dist = np.array([np.hypot(dr, dc) * dx for dr, dc in OFF])
    # the painted input: uplift up to Umax where the range should be, falling to 0 at the map edge (the sea)
    yy, xx = np.mgrid[0:N, 0:N] / (N - 1)
    edge = np.clip(np.minimum.reduce([xx, 1 - xx, yy, 1 - yy]) / 0.18, 0, 1) ** 1.5
    U = Umax * (0.35 + 0.65 * spectral_noise(N, 4.0, seed, kmax=6)) * edge
    U *= 0.8 + 0.4 * spectral_noise(N, 2.5, seed + 4, kmax=48)  # some uplift texture breaks parallel drainage
    Sc = np.tan(np.radians(36.0)) * (0.85 + 0.3 * spectral_noise(N, 3.0, seed + 1, kmax=40))
    m, n = 0.5, 1.0
    if k_noise > 0:   # erodibility varies in space (Schott et al.'s shader multiplies k by a noise buffer)
        K = K * (1.0 + k_noise * (2.0 * spectral_noise(N, 2.0, seed + 6, kmax=64) - 1.0))
    if init == 'dome':
        h = 600.0 * U / U.max() * (0.6 + 0.4 * spectral_noise(N, 3.0, seed + 5))
    else:
        h = 30.0 * spectral_noise(N, 2.5, seed + 2)            # near-flat start, some roughness
    h[0, :] = h[-1, :] = h[:, 0] = h[:, -1] = 0.0
    A = np.full((N, N), dx * dx)
    t0 = time.perf_counter()
    for it in range(steps):
        P = np.pad(h, 1, mode='constant', constant_values=1e9)     # nothing flows off the map except at the edge rows
        nb = shifts(P, N, N)
        s = np.stack([(h - nb[k]) / dist[k] for k in range(8)])   # downhill slope toward each neighbour
        w = np.maximum(s, 0.0)                                     # flow weights ~ slope^1 (multiple directions)
        tot = w.sum(0)
        w /= np.where(tot > 0, tot, 1.0)
        Qp = np.pad(w * A[None], ((0, 0), (1, 1), (1, 1)))
        A = np.full((N, N), dx * dx)
        for k, (dr, dc) in enumerate(OFF):                         # gather what the neighbours send this way
            A += Qp[OPP[k], 1 + dr:1 + dr + N, 1 + dc:1 + dc + N]
        kr = s.argmax(0)
        S = np.maximum(np.take_along_axis(s, kr[None], 0)[0], 0.0)
        h_recv = h - S * dist[kr]
        h = np.maximum(h - dt * K * np.sqrt(A) * S, h_recv) + dt * U  # m = 0.5, n = 1
        if limiter == 'minplus':
            for _ in range(2):
                nb = shifts(np.pad(h, 1, mode='constant', constant_values=1e9), N, N)
                h = np.minimum(h, np.min(np.stack([nb[k] + Sc * dist[k] for k in range(8)]), 0))
        else:
            h = nonlinear_diffusion(h, dx, D, Sc, dt, cap)
        h[0, :] = h[-1, :] = h[:, 0] = h[:, -1] = 0.0
        if log_every and (it + 1) % log_every == 0:
            print(f'step {it + 1}: max {h.max():.0f} m, mean {h.mean():.0f} m, '
                  f'{(time.perf_counter() - t0) / (it + 1) * 1000:.1f} ms/step', flush=True)
    sec = time.perf_counter() - t0
    return h, A, dx, sec


def reference_op_ms(N, reps=50):
    """The time of one plain full-grid numpy op (a*b+c) right now, to express a step's cost machine-independently."""
    a = np.random.rand(N, N)
    t = time.perf_counter()
    for _ in range(reps):
        a = a * 1.0000001 + 1e-9
    return (time.perf_counter() - t) / reps * 1000.0


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 512
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    limiter = sys.argv[3] if len(sys.argv) > 3 else 'diffusion'
    D = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
    K = float(sys.argv[5]) if len(sys.argv) > 5 else 4e-6
    Umax = float(sys.argv[6]) if len(sys.argv) > 6 else 1e-3
    dt = float(sys.argv[7]) if len(sys.argv) > 7 else 2000.0
    init = sys.argv[8] if len(sys.argv) > 8 else 'flat'
    k_noise = float(sys.argv[9]) if len(sys.argv) > 9 else 0.0
    os.makedirs(OUT, exist_ok=True)
    ref0 = reference_op_ms(N)
    h, A, dx, sec = run(N, steps, limiter=limiter, D=D, K=K, Umax=Umax, dt=dt, init=init, k_noise=k_noise)
    ref1 = reference_op_ms(N)
    tag = f'spl_gather_{N}_{limiter}_D{D:g}' + ('' if (K, Umax, dt, init) == (4e-6, 1e-3, 2000.0, 'flat')
                                                 else f'_K{K:g}_U{Umax:g}_dt{dt:g}_{init}')
    tag += f'_kn{k_noise:g}' if k_noise > 0 else ''
    np.savez_compressed(os.path.join(OUT, tag + '.npz'), height=h.astype(np.float32), area=A.astype(np.float32),
                        dx=dx)
    Image.fromarray(TM.hillshade(h, dx)).save(os.path.join(OUT, f'hillshade_{tag}.png'))
    met = TM.metrics(h, dx)
    ms = sec / steps * 1000
    met.update({'steps': steps, 'seconds': round(sec, 1), 'ms_per_step': round(ms, 1),
                'plain_op_ms': round(0.5 * (ref0 + ref1), 3),
                'step_cost_in_plain_ops': round(ms / (0.5 * (ref0 + ref1)), 0)})
    with open(os.path.join(OUT, tag + '.json'), 'w') as f:
        json.dump(met, f, indent=1)
    print(json.dumps(met, indent=1))
