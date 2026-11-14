"""Design measurement (not the implementation): what a 3x3-stencil erosion step costs as a Blender 5.2 compute
dispatch in headless Blender, per step, at 512^2 .. 4096^2, ping-ponging two RGBA32F 2D textures; plus the cost of
reading the result back to numpy. The kernel does the work of one stream-power gather step (8 neighbour reads,
slopes, MFD area gather, incision, uplift), so its time stands for one solver pass.

    bash run_blender.sh gpu_bench.py
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
from eidoblend.fx._gpu import ComputeContext  # noqa: E402

SRC = r'''
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(hIn, 0);
  if (p.x >= n.x || p.y >= n.y) return;
  vec4 c = texelFetch(hIn, p, 0);
  float h = c.x;
  float best = 0.0;
  float acc = uCell;
  float wsum = 0.0;
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) continue;
      ivec2 q = (p + ivec2(dx, dy) + n) % n;
      vec4 v = texelFetch(hIn, q, 0);
      float d = length(vec2(dx, dy)) * uDx;
      best = max(best, (h - v.x) / d);
      acc += max((v.x - h) / d, 0.0) * v.y * v.z;
      wsum += max((h - v.x) / d, 0.0);
    }
  }
  float hn = h - uDt * uK * sqrt(acc) * best + uDt * uU;
  imageStore(hOut, p, vec4(hn, acc, 1.0 / max(wsum, 1e-6), 1.0));
}
'''


def main():
    ctx = ComputeContext()
    import gpu
    out = {'platform': [gpu.platform.vendor_get(), gpu.platform.renderer_get(), gpu.platform.version_get()]}
    k = ctx.kernel(SRC, samplers=['hIn'], images=['hOut'],
                   push=[('FLOAT', 'uDt'), ('FLOAT', 'uK'), ('FLOAT', 'uU'), ('FLOAT', 'uDx'), ('FLOAT', 'uCell')],
                   local=(16, 16, 1), image_type='FLOAT_2D', image_format='RGBA32F',
                   sampler_types={'hIn': 'FLOAT_2D'})
    for N in (512, 1024, 2048, 4096):
        rng = np.random.default_rng(1)
        a = np.zeros((N, N, 4), np.float32)
        a[..., 0] = rng.random((N, N)) * 100.0
        a[..., 1] = 1.0
        a[..., 2] = 0.125
        A = ctx.texture2d_from(a)
        B = ctx.texture2d_from(a)
        groups = (int(np.ceil(N / 16)), int(np.ceil(N / 16)), 1)
        uni = dict(uDt=100.0, uK=1e-5, uU=1e-3, uDx=10.0, uCell=100.0)
        for i in range(20):                                   # warm-up (shader compile, first dispatches)
            k.run(groups, samplers={'hIn': A}, images={'hOut': B}, **uni)
            A, B = B, A
        ctx.read(A)
        S = 1000 if N <= 1024 else (400 if N == 2048 else 100)
        T = {}
        issue = {}
        for s in (S, 2 * S):                                  # same final readback, two step counts: the difference is
            t = time.perf_counter()                           # the GPU time of S steps, free of the readback's cost
            for i in range(s):
                k.run(groups, samplers={'hIn': A}, images={'hOut': B}, **uni)
                A, B = B, A
            issue[s] = time.perf_counter() - t
            r = ctx.read(A)
            T[s] = time.perf_counter() - t
        t = time.perf_counter()
        ctx.read(A)
        t_read = time.perf_counter() - t
        out[str(N)] = {'ms_per_step': round((T[2 * S] - T[S]) / S * 1000.0, 4),
                       'python_issue_ms_per_step': round(issue[S] / S * 1000.0, 4),
                       'readback_ms': round(t_read * 1000, 1), 'finite': bool(np.isfinite(r).all())}
        print(N, out[str(N)], flush=True)
    # the same step in numpy at 512 and 1024, for the ratio
    for N in (512, 1024):
        rng = np.random.default_rng(1)
        h = rng.random((N, N)) * 100.0
        Aa = np.ones((N, N))
        W = np.full((N, N), 0.125)
        offs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        t = time.perf_counter()
        reps = 5
        for _ in range(reps):
            best = np.zeros_like(h)
            acc = np.full_like(h, 100.0)
            wsum = np.zeros_like(h)
            for dr, dc in offs:
                v = np.roll(np.roll(h, -dr, 0), -dc, 1)
                va = np.roll(np.roll(Aa, -dr, 0), -dc, 1)
                vw = np.roll(np.roll(W, -dr, 0), -dc, 1)
                d = np.hypot(dr, dc) * 10.0
                best = np.maximum(best, (h - v) / d)
                acc += np.maximum((v - h) / d, 0.0) * va * vw
                wsum += np.maximum((h - v) / d, 0.0)
            h = h - 100.0 * 1e-5 * np.sqrt(acc) * best + 0.1
            Aa = acc
            W = 1.0 / np.maximum(wsum, 1e-6)
        out['numpy_' + str(N)] = {'ms_per_step': round((time.perf_counter() - t) / reps * 1000.0, 1)}
        print('numpy', N, out['numpy_' + str(N)], flush=True)
    print('RESULT ' + json.dumps(out), flush=True)


main()
