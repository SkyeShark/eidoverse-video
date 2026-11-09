"""The design's GPU benchmark (design_probes/gpu_bench.py, section 1.2) re-run through the terrain core's runner,
plus what the core adds: the sample creep pass, texture upload and readback, per-kernel compile time in a fresh
process, and world-noise fields. Writes out/core/gpu_bench.json with the design's numbers beside ours.

    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain_new/core/bench_gpu.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plain_import  # noqa: E402

OUT = plain_import.install()

import numpy as np  # noqa: E402

from eidoblend.terrain.core import gpu as G  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core import world_noise as N  # noqa: E402
import sample_creep_twin as SC  # noqa: E402

DESIGN = os.path.join(plain_import.WORKTREE, 'blender', 'tests', 'terrain_new', 'design_probes', 'results.json')

# the design probe's kernel, unchanged but for the runner's //! header
BENCH = r'''//! sampler hIn
//! image hOut rgba32f
//! uniform float uDt
//! uniform float uK
//! uniform float uU
//! uniform float uDx
//! uniform float uCell
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


def per_step(kernel, n, S, make_bindings):
    """(GPU ms per dispatch, Python issue ms per dispatch, readback ms): S and 2S dispatches with the same final
    readback; the difference is S dispatches of GPU time free of the readback's cost (the design's method)."""
    a, b, extra, uni = make_bindings(n)
    for _ in range(20):
        G.run(kernel, None, samplers=dict(extra, **{kernel.spec.samplers[0]: a}),
              images={next(iter(kernel.spec.images)): b}, uniforms=uni)
        a, b = b, a
    G.read(a)
    T, issue = {}, {}
    for s in (S, 2 * S):
        t = time.perf_counter()
        for _ in range(s):
            G.run(kernel, None, samplers=dict(extra, **{kernel.spec.samplers[0]: a}),
                  images={next(iter(kernel.spec.images)): b}, uniforms=uni)
            a, b = b, a
        issue[s] = time.perf_counter() - t
        G.read(a)
        T[s] = time.perf_counter() - t
    t = time.perf_counter()
    r = G.read(a)
    t_read = time.perf_counter() - t
    return {'ms_per_step': round((T[2 * S] - T[S]) / S * 1000.0, 4),
            'python_issue_ms_per_step': round(issue[S] / S * 1000.0, 4), 'readback_ms': round(t_read * 1000, 1),
            'finite': bool(np.isfinite(r).all())}


def main():
    info = G.init()
    out = {'platform': info, 'date': time.strftime('%Y-%m-%d %H:%M')}
    t = time.perf_counter()
    kb = G.kernel(source=BENCH, name='bench_stream_power', common=False)
    out['compile_ms_bench_kernel_cold'] = round((time.perf_counter() - t) * 1000, 2)
    t = time.perf_counter()
    kc = G.kernel(path=SC.KERNEL)
    out['compile_ms_sample_creep_with_common_cold'] = round((time.perf_counter() - t) * 1000, 2)

    def bench_bindings(n):
        rng = np.random.default_rng(1)
        a = np.zeros((n, n, 4), np.float32)
        a[..., 0] = rng.random((n, n)) * 100.0
        a[..., 1] = 1.0
        a[..., 2] = 0.125
        return G.texture(a), G.texture(a), {}, dict(uDt=100.0, uK=1e-5, uU=1e-3, uDx=10.0, uCell=100.0)

    out['bench'] = {}
    for n in (512, 1024, 2048, 4096):
        S = 1000 if n <= 1024 else (400 if n == 2048 else 100)
        out['bench'][str(n)] = per_step(kb, n, S, bench_bindings)
        print('bench', n, out['bench'][str(n)], flush=True)

    def creep_bindings(n):
        inp = SC.inputs((n, n), seed=3)
        st = G.texture(inp['st'])
        return st, G.like(st), {'par': G.texture(inp['par']), 'pin': G.texture(inp['pin'])}, \
            SC.uniforms(1, cell=10.0, D=0.5)

    out['sample_creep'] = {}
    for n in (1024, 2048):
        out['sample_creep'][str(n)] = per_step(kc, n, 1000 if n == 1024 else 400, creep_bindings)
        print('sample_creep', n, out['sample_creep'][str(n)], flush=True)

    out['transfer_ms'] = {}
    for n in (1024, 2048):
        for ch in (1, 4):
            a = np.random.default_rng(2).random((n, n, ch)).astype(np.float32)
            t = time.perf_counter()
            tex = G.texture(a)
            G.sync(tex)
            up = (time.perf_counter() - t) * 1000
            t = time.perf_counter()
            G.read(tex)
            rd = (time.perf_counter() - t) * 1000
            out['transfer_ms'][f'{n}_{ch}ch'] = {'upload': round(up, 1), 'read': round(rd, 1)}
    print('transfer', out['transfer_ms'], flush=True)

    out['world_noise_ms'] = {}
    spec = {'kind': 'fbm', 'wavelength_m': 2000.0, 'octaves': 6}
    for n in (1024, 2048):
        lv = L.Level(0, 'main', -4000.0, -4000.0, 8000.0, 8000.0 / n, n)
        N.field_gpu(spec, lv, 1)
        t = time.perf_counter()
        N.field_gpu(spec, lv, 1)
        out['world_noise_ms'][f'fbm6_{n}'] = round((time.perf_counter() - t) * 1000, 1)
    print('world noise', out['world_noise_ms'], flush=True)

    for n in (512, 1024):                                       # the same step in numpy, for the ratio
        rng = np.random.default_rng(1)
        h = rng.random((n, n)) * 100.0
        Aa = np.ones((n, n))
        W = np.full((n, n), 0.125)
        offs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        reps = 3
        t = time.perf_counter()
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
        out[f'numpy_{n}_ms_per_step'] = round((time.perf_counter() - t) / reps * 1000.0, 1)
    out['compile_ms'] = dict(G.COMPILE_MS)
    try:
        with open(DESIGN, encoding='utf-8') as f:
            d = json.load(f)['gpu_bench2']
        out['design_probe'] = {k: d[k] for k in ('512', '1024', '2048', '4096', 'numpy_512', 'numpy_1024')}
    except (OSError, KeyError, ValueError):
        out['design_probe'] = None
    with open(os.path.join(OUT, 'gpu_bench.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    print('RESULT ' + json.dumps(out), flush=True)
    os._exit(0)


main()
