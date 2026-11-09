"""The twin harness in plain Python (system Python with numpy, no GPU):

    python blender/tests/terrain_new/core/test_twins.py

  - the common.glsl mirrors: neighbour shifts equal explicit index loops in all three boundary modes (non-square),
    OFF / LEN / WISO / opp agree with each other, PCG equals an independent pure-Python PCG, u01 is in [0, 1)
  - run_twin checks a twin's outputs against the kernel file's //! declarations (missing / extra / wrong shape fail)
  - the sample creep twin at 128^2: periodic with uniform Sc conserves the total height (the flux is symmetric), the
    pinned mode holds weight-1 pins exactly, and each run takes well under the design's 5 s
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

from eidoblend.terrain.core import gpu as G  # noqa: E402 - parse_spec / load_source need no GPU
from eidoblend.terrain.core import twins as T  # noqa: E402
import sample_creep_twin as SC  # noqa: E402

FAILED = []
RESULTS = {}


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def test_primitives():
    h, w = 7, 11
    a = np.arange(h * w, dtype=np.float32).reshape(h, w)
    ok = True
    for mode in (T.BOUND_OPEN, T.BOUND_PERIODIC, T.BOUND_PINNED):
        for k in range(8):
            v, m = T.neighbour(a, k, mode, fill=-1.0)
            dx, dy = T.OFF[k]
            for j in range(h):
                for i in range(w):
                    qi, qj = i + dx, j + dy
                    if mode == T.BOUND_PERIODIC:
                        qi, qj = qi % w, qj % h
                    inside = 0 <= qi < w and 0 <= qj < h
                    want = a[qj, qi] if inside else -1.0
                    ok = ok and (v[j, i] == want) and (m[j, i] == inside)
    check('twins_neighbour_equals_index_loops', ok)
    check('twins_tables_consistent', all(T.OFF[T.opp(k)] == (-T.OFF[k][0], -T.OFF[k][1]) for k in range(8)) and
          np.allclose(T.LEN, [np.hypot(*o) for o in T.OFF], atol=1e-6) and
          np.allclose(T.WISO, [1 / 6 if o[0] and o[1] else 2 / 3 for o in T.OFF], atol=1e-6) and
          abs(float(T.WISO.sum()) - 10 / 3) < 1e-5)

    def pcg_py(v):
        state = (v * 747796405 + 2891336453) & 0xFFFFFFFF
        word = (((state >> ((state >> 28) + 4)) ^ state) * 277803737) & 0xFFFFFFFF
        return ((word >> 22) ^ word) & 0xFFFFFFFF
    vals = [0, 1, 2, 12345, 0xFFFFFFFF, 2 ** 31, 987654321]
    check('twins_pcg_equals_pure_python', [int(x) for x in T.pcg(np.array(vals, np.int64))] ==
          [pcg_py(v) for v in vals])
    hh = T.cell_hash((80, 96), 7, -3)
    u = T.u01(hh)
    check('twins_u01_range_and_spread', float(u.min()) >= 0.0 and float(u.max()) < 1.0 and abs(float(u.mean()) - 0.5)
          < 0.02, [float(u.min()), float(u.max()), float(u.mean())])
    pw, ph = T.pin_pattern((80, 96), 1)
    hp = T.pin_apply(np.zeros((80, 96), np.float32), pw, ph)
    check('twins_pin_apply', np.array_equal(hp[pw == 1.0], ph[pw == 1.0]) and np.all(hp[pw == 0.0] == 0.0))


def test_spec_checks():
    spec = G.load_source(path=SC.KERNEL)[2]
    inp = SC.inputs((64, 64), seed=2)
    uni = SC.uniforms(T.BOUND_OPEN)
    out = T.run_twin(SC.sample_creep, inp, uni, spec=spec)
    check('run_twin_against_declarations', set(out) == set(spec.images) and out['outS'].shape == (64, 64, 4))
    errs = {}
    for label, fn in {
        'missing_output': lambda s, u: {},
        'extra_output': lambda s, u: {'outS': np.zeros((64, 64, 4)), 'other': np.zeros((64, 64, 4))},
        'wrong_channels': lambda s, u: {'outS': np.zeros((64, 64))},
    }.items():
        try:
            T.run_twin(fn, inp, uni, spec=spec)
            errs[label] = None
        except (KeyError, ValueError) as e:
            errs[label] = str(e)
    try:
        T.run_twin(SC.sample_creep, {'st': inp['st']}, uni, spec=spec)
        errs['missing_sampler'] = None
    except KeyError as e:
        errs['missing_sampler'] = str(e)
    check('run_twin_rejects_mismatches', all(errs.values()), errs)
    check('spec_parse', spec.samplers == ['st', 'par', 'pin'] and spec.images == {'outS': 'RGBA32F'} and
          spec.uniforms['uBound'] == 'int' and spec.local == (16, 16) and spec.push_bytes() == 20, repr(spec))


def test_sample_creep_twin():
    n = 128
    inp = SC.inputs((n, n), seed=5)
    inp['par'][..., 2] = np.tan(np.radians(35.0))                  # uniform Sc: the pair flux is symmetric
    uni = SC.uniforms(T.BOUND_PERIODIC, cell=10.0, D=0.5)
    t = time.perf_counter()
    st = inp['st'].copy()
    for _ in range(20):
        out = T.run_twin(SC.sample_creep, dict(inp, st=st), uni)['outS']
        st = out
    sec = time.perf_counter() - t
    h0 = inp['st'][..., 0].astype(np.float64).sum()
    h1 = st[..., 0].astype(np.float64).sum()
    rel = abs(h1 - h0) / abs(h0)
    check('sample_creep_twin_periodic_conserves', rel < 1e-6, {'relative change of the total': rel,
                                                              'steps': 20})
    check('sample_creep_twin_speed_128', sec < 5.0, f'{sec:.2f} s for 20 steps at 128^2')
    pinned = T.run_twin(SC.sample_creep, inp, SC.uniforms(T.BOUND_PINNED))['outS'][..., 0]
    full = inp['pin'][..., 0] == 1.0
    check('sample_creep_twin_pins_hold', np.array_equal(pinned[full], inp['pin'][..., 1][full]))
    sm0 = float(np.abs(np.diff(inp['st'][..., 0], axis=1)).mean())
    sm1 = float(np.abs(np.diff(st[..., 0], axis=1)).mean())
    check('sample_creep_twin_smooths', sm1 < sm0, {'mean |dh| between neighbours before': sm0, 'after': sm1})


def main():
    t0 = time.perf_counter()
    for fn in (test_primitives, test_spec_checks, test_sample_creep_twin):
        t = time.perf_counter()
        try:
            fn()
        except Exception:                                          # noqa: BLE001
            check(fn.__name__ + '_ran', False, traceback.format_exc()[-1500:])
        print(f'  ({fn.__name__}: {time.perf_counter() - t:.1f} s)', flush=True)
    RESULTS['failed'] = FAILED
    RESULTS['seconds'] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(OUT, 'twin_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"[twins] {'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} in {RESULTS['seconds']} s")
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
