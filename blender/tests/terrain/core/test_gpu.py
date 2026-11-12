"""The terrain core's GPU runner tests (Blender, through a GPU slot):

    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain/core/test_gpu.py

  1. round trip: numpy -> texture -> numpy is bit-exact (R32F, RG32F, RGBA32F; 3 channels padded; non-square;
     negative, huge, tiny, inf and nan values), and so is a copy kernel (texelFetch -> imageStore)
  2. frames: texel (x, y) is array [row y, column x], row 0 = south; groups=None covers a non-square image
  3. the PCG hashes and u01 of common.glsl equal core/twins.py bit for bit
  4. ping-pong: an increment kernel run 10 times through PingPong.swap()
  5. mistakes fail loudly and name the nearest declared binding
  6. the sample kernel (the design probe's creep, sample_creep.glsl) equals its twin within 1e-4 x range on a
     96 x 80 field with pins, in the open, periodic and pinned modes; and so do its increments (hn - h); two mutants
     of it (a neighbour dropped, i and j swapped) fail
  7. world noise on the GPU (world_noise.field_gpu) equals its numpy twin for every field kind, far from the origin,
     periodic and warped; uplift shapes on the GPU equal numpy's; the 1024^2 costs stay under the design's 1 s
Writes blender/tests/terrain/out/core/gpu_tests.json; exit code 1 on a failure.
"""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plain_import  # noqa: E402

OUT = plain_import.install()

import numpy as np  # noqa: E402

from eidoblend.terrain.core import gpu as G  # noqa: E402
from eidoblend.terrain.core import twins as T  # noqa: E402
import sample_creep_twin as SC  # noqa: E402

RESULTS = {}
FAILED = []


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def bits(a):
    return np.ascontiguousarray(a, np.float32).view(np.uint32)


COPY = '''//! sampler src
//! image dst rgba32f
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  if (!inside(p, textureSize(src, 0))) return;
  imageStore(dst, p, texelFetch(src, p, 0));
}'''

AXES = '''//! image dst rgba32f
//! uniform int uW
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  if (!inside(p, imageSize(dst))) return;
  imageStore(dst, p, vec4(float(p.x), float(p.y), float(p.x + p.y * uW), 1.0));
}'''

HASH = '''//! image dstA rgba32f
//! image dstB rgba32f
//! uniform int uIter
//! uniform int uSeed
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = imageSize(dstA);
  if (!inside(p, n)) return;
  uint v = uint(p.x + p.y * n.x);
  uint a = pcg(v);
  uint b = cell_hash(p, uIter, uSeed);
  uint c = pcg2(v, uint(uSeed));
  imageStore(dstA, p, vec4(float(a >> 16u), float(a & 65535u), float(b >> 16u), float(b & 65535u)));
  imageStore(dstB, p, vec4(float(c >> 16u), float(c & 65535u), u01(b), u01(a)));
}'''

INC = '''//! sampler src
//! image dst rgba32f
//! uniform float uAdd
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  if (!inside(p, textureSize(src, 0))) return;
  vec4 c = texelFetch(src, p, 0);
  imageStore(dst, p, c + vec4(uAdd, 0.0, 0.0, 1.0));
}'''


def test_roundtrip():
    rng = np.random.default_rng(5)
    H, W = 80, 96
    for ch in (1, 2, 3, 4):
        a = (rng.standard_normal((H, W, ch)) * 1000.0).astype(np.float32)
        a.flat[0] = 3.4e38
        a.flat[1] = -1e-30
        a.flat[2] = np.inf
        a.flat[3] = -np.inf
        a.flat[4] = 1e-41                                   # subnormal
        if a.size > 5:
            a.flat[5] = np.nan
        t = G.texture(a)
        r = G.read(t)
        want = a if ch != 3 else np.concatenate([a, np.zeros((H, W, 1), np.float32)], axis=2)
        same = r.shape == want.shape and np.array_equal(bits(r), bits(want))
        check(f'roundtrip_upload_read_{ch}ch', same, {'shape': list(r.shape), 'format': t.format})
    a = (rng.standard_normal((H, W, 4)) * 1e4).astype(np.float32)
    k = G.kernel(source=COPY, name='t_copy')
    src = G.texture(a)
    dst = G.like(src)
    G.run(k, None, samplers={'src': src}, images={'dst': dst})
    r = G.read(dst)
    check('roundtrip_copy_kernel_exact', np.array_equal(bits(r), bits(a)))
    big = (rng.random((1024, 1024, 4)) * 5000).astype(np.float32)
    t0 = time.perf_counter()
    tb = G.texture(big)
    t1 = time.perf_counter()
    rb = G.read(tb)
    t2 = time.perf_counter()
    check('roundtrip_1024_rgba_exact', np.array_equal(bits(rb), bits(big)),
          {'upload_ms': round((t1 - t0) * 1000, 2), 'read_ms': round((t2 - t1) * 1000, 2)})


def test_axes():
    H, W = 80, 96
    k = G.kernel(source=AXES, name='t_axes')
    dst = G.empty((H, W))
    G.run(k, None, images={'dst': dst}, uniforms={'uW': W})
    r = G.read(dst)
    jj, ii = np.mgrid[0:H, 0:W]
    ok = (np.array_equal(r[..., 0], ii.astype(np.float32)) and np.array_equal(r[..., 1], jj.astype(np.float32))
          and np.array_equal(r[..., 2], (ii + jj * W).astype(np.float32)))
    check('frames_texel_xy_is_array_col_row', ok, {'shape': list(r.shape), 'groups': k.groups_for((H, W))})


def test_hash():
    H, W = 80, 96
    k = G.kernel(source=HASH, name='t_hash')
    a_t, b_t = G.empty((H, W)), G.empty((H, W))
    it, seed = 37, -12345
    G.run(k, None, images={'dstA': a_t, 'dstB': b_t}, uniforms={'uIter': it, 'uSeed': seed})
    A, B = G.read(a_t), G.read(b_t)
    jj, ii = np.mgrid[0:H, 0:W]
    v = (ii + jj * W).astype(np.uint32)
    a = T.pcg(v)
    b = T.cell_hash((H, W), it, seed)
    c = T.pcg2(v, seed)

    def split(x):
        return (x >> np.uint32(16)).astype(np.float32), (x & np.uint32(65535)).astype(np.float32)
    ok_a = all(np.array_equal(g, w) for g, w in zip((A[..., 0], A[..., 1]), split(a)))
    ok_b = all(np.array_equal(g, w) for g, w in zip((A[..., 2], A[..., 3]), split(b)))
    ok_c = all(np.array_equal(g, w) for g, w in zip((B[..., 0], B[..., 1]), split(c)))
    ok_u = np.array_equal(B[..., 2], T.u01(b)) and np.array_equal(B[..., 3], T.u01(a))
    check('pcg_bit_exact', ok_a and ok_b and ok_c, {'pcg': ok_a, 'cell_hash': ok_b, 'pcg2': ok_c})
    check('u01_bit_exact', ok_u)


def test_pingpong():
    H, W = 80, 96
    a = T.rgba(T.random_field((H, W), 0, 10, 3))
    k = G.kernel(source=INC, name='t_inc')
    pp = G.PingPong(a)
    for _ in range(10):
        G.run(k, None, samplers={'src': pp.src}, images={'dst': pp.dst}, uniforms={'uAdd': 0.5})
        pp.swap()
    r = pp.read()
    ok = np.allclose(r[..., 0], a[..., 0] + 5.0, atol=1e-5) and np.array_equal(r[..., 3], np.full((H, W), 10.0,
                                                                                                    np.float32))
    check('pingpong_10_swaps', ok)


def test_errors():
    k = G.kernel(source=INC, name='t_inc')
    src, dst = G.empty((8, 8)), G.empty((8, 8))
    cases = {
        'missing_uniform': lambda: G.run(k, None, samplers={'src': src}, images={'dst': dst}),
        'misspelt_sampler': lambda: G.run(k, None, samplers={'scr': src}, images={'dst': dst}, uniforms={'uAdd': 1}),
        'same_texture_read_write': lambda: G.run(k, None, samplers={'src': src}, images={'dst': src},
                                                 uniforms={'uAdd': 1}),
        'format_mismatch': lambda: G.run(k, None, samplers={'src': src}, images={'dst': G.empty((8, 8), 1)},
                                         uniforms={'uAdd': 1}),
        'bad_header': lambda: G.kernel(source='//! uniform double uX\n//! image o\nvoid main() {}', name='t_bad'),
        'no_such_kernel': lambda: G.kernel('route_insice_no_such'),
        'compile_error': lambda: G.kernel(source='//! image o\nvoid main() { imageStore(o, ivec2(0), vec4(nope)); }',
                                          name='t_compile_error'),
    }
    msgs = {}
    for name, fn in cases.items():
        try:
            fn()
            msgs[name] = None
        except Exception as e:                                     # noqa: BLE001
            msgs[name] = f'{type(e).__name__}: {e}'[:300]
    for name, m in msgs.items():
        check(f'error_{name}', m is not None, m)
    check('error_misspelt_names_nearest', msgs['misspelt_sampler'] is not None and "'src'" in msgs['misspelt_sampler'])


def test_sample_creep_parity():
    k = G.kernel(path=SC.KERNEL)
    worst = 0.0
    for label, mode in T.BOUNDARY_CASES:
        inp = SC.inputs((80, 96), seed=11)
        uni = SC.uniforms(mode)
        rep = T.parity(k, inp, uni)
        print(T.report_text(rep), flush=True)
        # the increments too: an axis mix-up or a dropped neighbour shows in hn - h even when hn's range hides it
        tex = {n: G.texture(a) for n, a in inp.items()}
        out = G.empty((80, 96))
        G.run(k, None, samplers=tex, images={'outS': out}, uniforms=uni)
        got = G.read(out)
        want = T.run_twin(SC.sample_creep, inp, uni, spec=k.spec)['outS']
        free = inp['pin'][..., 0] < 1e-6 if mode == T.BOUND_PINNED else np.ones((80, 96), bool)
        dg = np.where(free, got[..., 0] - inp['st'][..., 0], 0)[..., None]
        dw = np.where(free, want[..., 0] - inp['st'][..., 0], 0)[..., None]
        drep = T.compare({'dh': dg}, {'dh': dw}, tol=1e-4)
        worst = max(worst, rep['worst'], drep['worst'])
        check(f'sample_creep_parity_{label}', rep['ok'] and drep['ok'],
              {'worst_h': rep['worst'], 'worst_dh': drep['worst'], 'dh_range_m': drep['channels'][0]['range'],
               'gpu_ms': rep['gpu_ms']})
    RESULTS['sample_creep_worst_ratio'] = worst
    # the test has teeth: mutants of the kernel (one neighbour dropped; i and j swapped in the neighbour fetch)
    # must fail against the same twin
    with open(SC.KERNEL, encoding='utf-8') as f:
        src = f.read()
    mutants = {'drops_one_neighbour': src.replace('k < 8', 'k < 7'),
               'swaps_i_and_j': src.replace('texelFetch(st, q, 0)', 'texelFetch(st, ivec2(q.y, q.x), 0)')}
    for label, msrc in mutants.items():
        assert msrc != src, label
        mk = G.kernel(source=msrc, name='sample_creep_mutant_' + label)
        rep = T.parity(mk, SC.inputs((80, 96), seed=11), SC.uniforms(T.BOUND_OPEN), twin=SC.sample_creep)
        check(f'parity_rejects_mutant_{label}', not rep['ok'], {'worst_ratio': rep['worst']})


def test_world_noise_gpu():
    """world_noise.field_gpu (the production path) against field() (its numpy twin), every kind, on a level far
    from the origin; GPU uplift against numpy uplift; the 1024^2 costs against the design's <= 1 s per level."""
    from eidoblend.terrain.core import compose as C
    from eidoblend.terrain.core import levels as L
    from eidoblend.terrain.core import world_noise as N
    lv = L.Level(0, 'main', -40000.0, 25000.0, 96 * 41.7, 41.7, 96)
    x, y = lv.xy()
    side = lv.side
    specs = {
        'gradient': {'kind': 'gradient', 'wavelength_m': 350.0},
        'fbm6': {'kind': 'fbm', 'wavelength_m': 2000.0, 'octaves': 6, 'seed': 3},
        'ridged': {'kind': 'ridged', 'wavelength_m': 900.0, 'octaves': 4, 'amp': 2.0, 'offset': -1.0},
        'periodic': {'kind': 'fbm', 'wavelength_m': N.snap_wavelength(500.0, side), 'octaves': 3, 'period_m': side},
        'K_three_scales': {'kind': 'sum', 'offset': 1.0, 'terms': [
            {'kind': 'fbm', 'wavelength_m': 2000.0, 'octaves': 2, 'amp': 0.6},
            {'kind': 'fbm', 'wavelength_m': 300.0, 'octaves': 2, 'amp': 0.6, 'seed': 1},
            {'kind': 'fbm', 'wavelength_m': 50.0, 'octaves': 2, 'amp': 0.6, 'seed': 2}]},
        'product': {'kind': 'product', 'terms': [{'kind': 'fbm', 'wavelength_m': 1500.0},
                                                 {'kind': 'const', 'value': 2.5},
                                                 {'kind': 'gradient', 'wavelength_m': 700.0, 'offset': 1.0}]},
        'warp': {'kind': 'warp', 'amp_m': 400.0, 'wavelength_m': 1200.0, 'seed': 5,
                 'of': {'kind': 'ridged', 'wavelength_m': 600.0, 'octaves': 3}},
    }
    worst = 0.0
    for label, spec in specs.items():
        g = N.field_gpu(spec, lv, seed=7)
        c = N.field(spec, x, y, seed=7).astype(np.float32)
        rep = T.compare({'f': g[..., None]}, {'f': c[..., None]})
        worst = max(worst, rep['worst'])
        check(f'world_noise_gpu_parity_{label}', rep['ok'], {'ratio': rep['worst'],
                                                              'range': rep['channels'][0]['range']})
    for kind, sp in (('ridge', {'kind': 'ridge', 'centre': [-38000, 27000], 'azimuth_deg': 30, 'length_m': 3000,
                                'width_m': 1500, 'spurs': 4}),
                     ('massif', {'kind': 'massif', 'centre': [-38000, 27000], 'radius_m': 1800, 'peaks': 4})):
        ug = C.uplift(sp, x, y, seed=3, level=lv)
        uc = C.uplift(sp, x, y, seed=3)
        rep = T.compare({'u': ug[..., None].astype(np.float32)}, {'u': uc[..., None].astype(np.float32)})
        check(f'uplift_gpu_parity_{kind}', rep['ok'], {'ratio': rep['worst']})
    big = L.Level(0, 'main', -4000.0, -4000.0, 8000.0, 8000.0 / 1024, 1024)
    timing = {}
    for label in ('fbm6', 'K_three_scales', 'warp'):
        N.field_gpu(specs[label], big, seed=1)                     # warm (compiles once)
        t = time.perf_counter()
        N.field_gpu(specs[label], big, seed=1)
        timing[label] = round((time.perf_counter() - t) * 1000.0, 1)
    X, Y = big.xy()
    t = time.perf_counter()
    C.uplift({'kind': 'ridge', 'length_m': 7000, 'width_m': 3000, 'spurs': 6}, X, Y, seed=2, level=big)
    timing['uplift_ridge'] = round((time.perf_counter() - t) * 1000.0, 1)
    t = time.perf_counter()
    N.fbm(X, Y, 2000.0, 1, seed=1)
    timing['numpy_one_lattice'] = round((time.perf_counter() - t) * 1000.0, 1)
    RESULTS['world_noise_1024_ms'] = timing
    check('world_noise_1024_under_1s', all(v < 1000.0 for k, v in timing.items() if k != 'numpy_one_lattice'),
          timing)


def main():
    t0 = time.perf_counter()
    info = G.init()
    RESULTS['platform'] = info
    print('[gpu]', info, flush=True)
    for fn in (test_roundtrip, test_axes, test_hash, test_pingpong, test_errors, test_sample_creep_parity,
               test_world_noise_gpu):
        try:
            fn()
        except Exception:                                          # noqa: BLE001
            check(fn.__name__ + '_ran', False, traceback.format_exc()[-1500:])
    RESULTS['compile_ms'] = dict(G.COMPILE_MS)
    RESULTS['seconds'] = round(time.perf_counter() - t0, 2)
    RESULTS['failed'] = FAILED
    with open(os.path.join(OUT, 'gpu_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"[gpu] {'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} in {RESULTS['seconds']} s; "
          f"compile ms {RESULTS['compile_ms']}", flush=True)
    os._exit(1 if FAILED else 0)


main()
