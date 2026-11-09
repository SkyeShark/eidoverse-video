"""Design measurement (not the implementation): the stream-power backbone of research.md 3.1(a) as Blender 5.2 compute
kernels, to see (1) what it costs at film resolutions and (2) what it looks like with enough cells per valley
(1024^2 direct, and coarse-to-fine 256 -> 512 -> 1024 with the hillslope length shrunk per level).

Three passes per step, each a 3x3 gather (research.md 3.1 a):
  wsum  : every cell's total downhill weight sum_k max(slope_k, 0)^p      (so neighbours can split their area)
  incise: area gather from the higher neighbours (one Jacobi step), incision K A^m S toward the steepest
          neighbour, clamped at the lowest neighbour, plus uplift; the map edge is base level (0 m)
  creep : nonlinear creep (Roering 1999), isotropic 9-point weights, flux capped at `cap` x linear

    bash run_blender.sh gpu_spl.py <out_dir>
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, r'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender')
from eidoblend.fx._gpu import ComputeContext  # noqa: E402

COMMON = r'''
const ivec2 OFF[8] = ivec2[8](ivec2(-1,-1), ivec2(0,-1), ivec2(1,-1), ivec2(-1,0), ivec2(1,0), ivec2(-1,1),
                              ivec2(0,1), ivec2(1,1));
const float LEN[8] = float[8](1.41421356, 1.0, 1.41421356, 1.0, 1.0, 1.41421356, 1.0, 1.41421356);
const float WISO[8] = float[8](0.16666667, 0.66666667, 0.16666667, 0.66666667, 0.66666667, 0.16666667, 0.66666667,
                               0.16666667);
bool inside(ivec2 q, ivec2 n) { return q.x >= 0 && q.y >= 0 && q.x < n.x && q.y < n.y; }
bool edge(ivec2 p, ivec2 n) { return p.x == 0 || p.y == 0 || p.x == n.x - 1 || p.y == n.y - 1; }
'''

WSUM = COMMON + r'''
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float hc = texelFetch(st, p, 0).x;
  float ws = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q = p + OFF[k];
    if (!inside(q, n)) continue;
    float s = (hc - texelFetch(st, q, 0).x) / (LEN[k] * uDx);
    if (s > 0.0) ws += pow(s, uP);
  }
  imageStore(outW, p, vec4(ws, 0.0, 0.0, 0.0));
}
'''

INCISE = COMMON + r'''
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float hc = c.x;
  float A = uDx * uDx;
  float smax = 0.0;
  float hlow = hc;
  for (int k = 0; k < 8; k++) {
    ivec2 q = p + OFF[k];
    if (!inside(q, n)) continue;
    vec4 cq = texelFetch(st, q, 0);
    float d = LEN[k] * uDx;
    if (cq.x > hc) {
      float wq = texelFetch(wsumT, q, 0).x;
      A += cq.y * pow((cq.x - hc) / d, uP) / max(wq, 1e-20);
    }
    smax = max(smax, (hc - cq.x) / d);
    hlow = min(hlow, cq.x);
  }
  vec4 par = texelFetch(parT, p, 0);           // U (m/yr), K, Sc (tan), unused
  float hn = max(hc - uDt * par.y * pow(A, uM) * smax, min(hlow, hc)) + uDt * par.x;
  if (edge(p, n)) hn = 0.0;
  imageStore(outS, p, vec4(hn, A, 0.0, 0.0));
}
'''

CREEP = COMMON + r'''
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float hc = c.x;
  float sc = texelFetch(parT, p, 0).z;
  float acc = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q = p + OFF[k];
    if (!inside(q, n)) continue;
    float hq = texelFetch(st, q, 0).x;
    float s = (hq - hc) / (LEN[k] * uDx);
    float f = min(1.0 / max(1.0 - (s / sc) * (s / sc), 1e-9), uCap);
    acc += WISO[k] * f * (hq - hc);
  }
  float hn = hc + uDtSub * uD * acc / (uDx * uDx);
  if (edge(p, n)) hn = 0.0;
  imageStore(outS, p, vec4(hn, c.y, 0.0, 0.0));
}
'''


THERMAL = COMMON + r'''
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float hc = c.x;
  float scc = texelFetch(parT, p, 0).z;
  float dh = 0.0;
  for (int k = 0; k < 8; k++) {                       // symmetric pair exchanges: mass is conserved
    ivec2 q = p + OFF[k];
    if (!inside(q, n)) continue;
    float hq = texelFetch(st, q, 0).x;
    float t = 0.5 * (scc + texelFetch(parT, q, 0).z) * LEN[k] * uDx;
    float ex = max(abs(hc - hq) - t, 0.0);
    dh -= sign(hc - hq) * uRate * ex;
  }
  float hn = hc + dh;
  if (edge(p, n)) hn = 0.0;
  imageStore(outS, p, vec4(hn, c.y, 0.0, 0.0));
}
'''


def spectral_noise(n, beta, seed, kmax=None):
    rng = np.random.default_rng(seed)
    kx = np.fft.rfftfreq(n) * n
    ky = np.fft.fftfreq(n) * n
    k = np.hypot(ky[:, None], kx[None, :])
    k[0, 0] = 1.0
    amp = k ** (-beta / 2.0)
    if kmax is not None:
        amp[k > kmax] = 0.0
    amp[0, 0] = 0.0
    f = np.fft.irfft2(amp * np.exp(1j * rng.uniform(0, 2 * np.pi, amp.shape)), s=(n, n))
    return (f - f.min()) / (f.max() - f.min())


def sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def catmull_up2(a):
    """x2 upsample, separable Catmull-Rom, cell-centred."""
    def up1(a, axis):
        a = np.moveaxis(a, axis, 0)
        P = np.concatenate([a[:1], a[:1], a, a[-1:], a[-1:]], 0)
        def cr(p0, p1, p2, p3, t):
            return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
        n = a.shape[0]
        lo = cr(P[0:n], P[1:n + 1], P[2:n + 2], P[3:n + 3], 0.75)      # sample at i - 0.25
        hi = cr(P[1:n + 1], P[2:n + 2], P[3:n + 3], P[4:n + 4], 0.25)  # sample at i + 0.25
        out = np.empty((2 * n,) + a.shape[1:], a.dtype)
        out[0::2] = lo
        out[1::2] = hi
        return np.moveaxis(out, 0, axis)
    return up1(up1(a, 0), 1)


class Solver:
    def __init__(self, ctx):
        self.ctx = ctx
        common = dict(local=(16, 16, 1), image_type='FLOAT_2D', image_format='RGBA32F')
        self.k_w = ctx.kernel(WSUM, samplers=['st'], images=['outW'], push=[('FLOAT', 'uDx'), ('FLOAT', 'uP')],
                              sampler_types={'st': 'FLOAT_2D'}, **common)
        self.k_i = ctx.kernel(INCISE, samplers=['st', 'wsumT', 'parT'], images=['outS'],
                              push=[('FLOAT', 'uDx'), ('FLOAT', 'uP'), ('FLOAT', 'uDt'), ('FLOAT', 'uM')],
                              sampler_types={'st': 'FLOAT_2D', 'wsumT': 'FLOAT_2D', 'parT': 'FLOAT_2D'}, **common)
        self.k_c = ctx.kernel(CREEP, samplers=['st', 'parT'], images=['outS'],
                              push=[('FLOAT', 'uDx'), ('FLOAT', 'uDtSub'), ('FLOAT', 'uD'), ('FLOAT', 'uCap')],
                              sampler_types={'st': 'FLOAT_2D', 'parT': 'FLOAT_2D'}, **common)
        self.k_t = ctx.kernel(THERMAL, samplers=['st', 'parT'], images=['outS'],
                              push=[('FLOAT', 'uDx'), ('FLOAT', 'uRate')],
                              sampler_types={'st': 'FLOAT_2D', 'parT': 'FLOAT_2D'}, **common)

    def run(self, h, U, K, Sc, dx, D, dt, steps, m=0.5, p=1.0, cap=5.0, thermal=0, rate=0.06):
        n = h.shape[0]
        st = np.zeros((n, n, 4), np.float32)
        st[..., 0] = h
        st[..., 1] = dx * dx
        par = np.zeros((n, n, 4), np.float32)
        par[..., 0], par[..., 1], par[..., 2] = U, K, Sc
        S0 = self.ctx.texture2d_from(st)
        S1 = self.ctx.texture2d_from(st)
        W = self.ctx.texture2d_from(np.zeros((n, n, 4), np.float32))
        P = self.ctx.texture2d_from(par)
        g = (int(np.ceil(n / 16)), int(np.ceil(n / 16)), 1)
        sub = int(np.ceil(dt / (0.9 * dx * dx / (3.4 * D * cap))))
        t0 = time.perf_counter()
        for it in range(steps):
            self.k_w.run(g, samplers={'st': S0}, images={'outW': W}, uDx=dx, uP=p)
            self.k_i.run(g, samplers={'st': S0, 'wsumT': W, 'parT': P}, images={'outS': S1}, uDx=dx, uP=p, uDt=dt, uM=m)
            S0, S1 = S1, S0
            for _ in range(sub):
                self.k_c.run(g, samplers={'st': S0, 'parT': P}, images={'outS': S1}, uDx=dx, uDtSub=dt / sub, uD=D,
                             uCap=cap)
                S0, S1 = S1, S0
            for _ in range(thermal):
                self.k_t.run(g, samplers={'st': S0, 'parT': P}, images={'outS': S1}, uDx=dx, uRate=rate)
                S0, S1 = S1, S0
        out = self.ctx.read(S0).reshape(n, n, 4)
        sec = time.perf_counter() - t0
        return out[..., 0].astype(np.float64), out[..., 1].astype(np.float64), sec, sub


def fields(n, seed, Umax, K0, kn):
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
    fade = sm(0.0, 0.18, np.minimum(xx, 1 - xx)) * sm(0.0, 0.18, np.minimum(yy, 1 - yy))
    U = Umax * (0.35 + 0.65 * spectral_noise(n, 4.0, seed, kmax=6 * n // 256)) * fade
    U *= 0.8 + 0.4 * spectral_noise(n, 2.5, seed + 4, kmax=48 * n // 256)
    Sc = np.tan(np.radians(36.0)) * (0.85 + 0.3 * spectral_noise(n, 3.0, seed + 1, kmax=40 * n // 256))
    K = K0 * (1.0 + kn * (2.0 * spectral_noise(n, 2.0, seed + 6, kmax=64 * n // 256) - 1.0))
    return U, K, Sc


def main():
    out_dir = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '.'
    os.makedirs(out_dir, exist_ok=True)
    ctx = ComputeContext()
    sol = Solver(ctx)
    size = 20000.0
    Umax, K0, kn, seed = 3e-3, 1.5e-5, 0.6, 3
    report = {}
    # every input field made ONCE at the finest grid and box-averaged down, so all levels see the same uplift,
    # erodibility and threshold (the previous run regenerated them per level: different random phases per size)
    U2, K2, Sc2 = fields(2048, seed, Umax, K0, kn)
    dome2 = 600.0 * U2 / U2.max() * (0.6 + 0.4 * spectral_noise(2048, 3.0, seed + 5))

    def at(a, n):
        f = 2048 // n
        return a.reshape(n, f, n, f).mean(axis=(1, 3))

    schedules = {'Dconst': [0.03, 0.03, 0.03, 0.03], 'Dshrink': [0.03, 0.03, 0.0075, 0.002]}
    plan = [(256, 1000.0, 2000), (512, 500.0, 1000), (1024, 250.0, 2000), (2048, 125.0, 2000)]
    for tag, Ds in schedules.items():
        h = at(dome2, 256)
        for lvl, (n, dt, steps) in enumerate(plan):
            dx = size / n
            if lvl > 0:
                h = catmull_up2(h)
                h += 2.0 * (at(spectral_noise(2048, 2.0, seed + 20 + lvl), n) - 0.5)
            U, K, Sc = at(U2, n), at(K2, n), at(Sc2, n)
            h, A, sec, sub = sol.run(h, U, K, Sc, dx, Ds[lvl], dt=dt, steps=steps, thermal=4)
            key = f'{tag}_{n}'
            np.savez_compressed(os.path.join(out_dir, key + '.npz'), h=h.astype(np.float32), A=A.astype(np.float32),
                                dx=dx)
            report[key] = {'sec': round(sec, 2), 'steps': steps, 'creep_sub': sub, 'D': Ds[lvl], 'max': float(h.max())}
            print(key, report[key], flush=True)
    print('RESULT ' + json.dumps(report), flush=True)


main()
