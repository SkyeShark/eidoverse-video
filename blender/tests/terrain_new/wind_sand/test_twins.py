"""Wind and sand in plain Python (system Python with numpy, no GPU): the slab model's twins.

    python blender/tests/terrain_new/wind_sand/test_twins.py

  - every twin's outputs match its kernel's //! declarations (the three kernel files and the avalanche source)
  - the transport gather equals the scatter it stands for (aeolian.scatter_step), slab for slab, in all three
    boundary modes, for 24 wind directions and three hop lengths, on a non-square 96 x 80 field
  - sand mass: conserved on a periodic grid through every pass (transport, avalanche, whole iterations); on an open
    grid it falls by exactly the slabs blown off the edge
  - the avalanche moves only sand, never more than a cell holds, and relaxes a sand pile to its angle of repose
  - the hop dithering is unbiased: the mean integer hop equals the real hop vector for any direction
  - the shadow of a ridge lies in its lee, inside the 15-degree line, and nowhere on the stoss side
  - determinism: one seed gives the same field bit for bit, another seed a different one
Each test runs in well under the design's 5 s. Results: out/wind_sand/twin_tests.json.
"""
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
OUT = os.path.normpath(os.path.join(plain_import.OUT, '..', 'wind_sand'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import gpu as G  # noqa: E402 - parse_spec / load_source need no GPU
from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import aeolian as A  # noqa: E402

FAILED = []
RESULTS = {}
SHAPE = (80, 96)                                   # non-square, so an axis mix-up fails


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def fields(seed=0, sand_hi=6.0):
    bed = T.random_field(SHAPE, 0.0, 5.0, seed=seed + 1, smooth=2)
    sand = np.maximum(T.random_field(SHAPE, -2.0, sand_hi, seed=seed + 2, smooth=2), 0.0)
    return bed, sand.astype(np.float32)


def st_of(bed, sand):
    return np.stack([bed, sand], -1).astype(np.float32)


def test_declarations():
    bed, sand = fields()
    st = st_of(bed, sand)
    u = A.uniforms_for(A.params_for(), 4.0, 225.0, 3, 9, T.BOUND_OPEN)
    sh = T.run_twin('dune_shadow', {'st': st}, u['dune_shadow'])
    plan = T.run_twin('dune_activate', {'st': st, 'shadow': sh['outShadow']}, u['dune_activate'])
    tr = T.run_twin('dune_transport', {'st': st, 'plan': plan['outPlan']}, u['dune_transport'])
    spec = G.parse_spec(A.AVALANCHE_SRC, 'dune_avalanche')
    av = T.run_twin(A.twin_avalanche, {'st': tr['outSt'], 'pins': np.zeros(SHAPE + (2,), np.float32)},
                    u['dune_avalanche'], spec=spec)
    shapes = {k: list(v[next(iter(v))].shape) for k, v in (('dune_shadow', sh), ('dune_activate', plan),
                                                              ('dune_transport', tr), ('dune_avalanche', av))}
    check('twins_match_kernel_declarations', True, shapes)
    for name in ('dune_shadow', 'dune_activate', 'dune_transport'):
        s = G.load_source(name)[2]
        check(f'{name}_uniforms_fit_push_constants', s.push_bytes() <= G.PUSH_LIMIT_BYTES,
              f'{s.push_bytes()} bytes')
    check('dune_avalanche_uniforms_fit_push_constants', spec.push_bytes() <= G.PUSH_LIMIT_BYTES,
          f'{spec.push_bytes()} bytes')


def test_gather_equals_scatter():
    bed, sand = fields(4)
    st = st_of(bed, sand)
    worst, lifted_tot, landed_tot, lost_tot, cases = 0.0, 0.0, 0.0, 0.0, 0
    t0 = time.perf_counter()
    for bound in (T.BOUND_OPEN, T.BOUND_PERIODIC, T.BOUND_PINNED):
        for hop in (1.5, 3.0, 4.7):
            for d in range(0, 360, 15):
                # long hops on (and overlapping the short ones at hop 1.5), the lift boost on
                p = A.params_for({'hop_cells': hop, 'p_lift': 0.3, 'long_factor': 2.0, 'speedup': 0.6,
                                  'lift_boost': 1.0})
                u = A.uniforms_for(p, 4.0, float(d), d, 17, bound)
                sh = A.twin_shadow({'st': st}, u['dune_shadow'])['outShadow']
                plan = A.twin_activate({'st': st, 'shadow': sh}, u['dune_activate'])['outPlan']
                g = A.twin_transport({'st': st, 'plan': plan}, u['dune_transport'])['outSt'][..., 1]
                s = A.scatter_step(st, plan, None, int(p['max_hops']), bound)
                worst = max(worst, float(np.abs(g.astype(np.float64) - s).max()))
                lifted = plan[..., 0].astype(np.float64)
                lost = float(lifted[plan[..., 3] < 0].sum())
                lifted_tot += float(lifted.sum())
                lost_tot += lost
                landed_tot += float(g.sum(dtype=np.float64) - (sand.sum(dtype=np.float64) - lifted.sum()))
                cases += 1
    check('transport_gather_equals_scatter', worst <= 1e-6 * float(sand.max()),
          {'cases': cases, 'worst |gather - scatter| m': worst, 'largest sand m': float(sand.max()),
           'seconds': round(time.perf_counter() - t0, 2)})
    check('every_lifted_slab_lands_once_or_leaves', abs(lifted_tot - lost_tot - landed_tot) <= 1e-6 * lifted_tot,
          {'lifted m': lifted_tot, 'landed m': landed_tot, 'blown off open edges m': lost_tot})


def test_mass():
    bed, sand = fields(7)
    tot0 = float(sand.sum(dtype=np.float64))
    t0 = time.perf_counter()
    sim = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {'hop_cells': 3.3}, seed=21)
    sim.run(A.KINDS['star']['winds'], 60, block=10)
    rel = float(sim.st[..., 1].sum(dtype=np.float64)) / tot0 - 1.0
    check('sand_mass_conserved_periodic', abs(rel) <= 1e-5,
          {'iterations': sim.it, 'relative change': rel, 'seconds': round(time.perf_counter() - t0, 2)})
    # open: what is lost is exactly what the plans say left the grid
    sim = A.TwinSim(bed, sand, 4.0, T.BOUND_OPEN, {'hop_cells': 3.3, 'aval_passes': 0}, seed=21)
    lost = 0.0
    for it in range(20):
        sim.step(225.0)
        pl = sim.last_plan
        lost += float(pl[..., 0][pl[..., 3] < 0].sum(dtype=np.float64))
    after = float(sim.st[..., 1].sum(dtype=np.float64))
    check('sand_mass_open_loses_only_outflow', abs(tot0 - lost - after) <= 1e-5 * tot0,
          {'start m': tot0, 'blown off m': lost, 'end m': after, 'residual m': tot0 - lost - after})


def test_avalanche():
    bed, sand = fields(9, sand_hi=12.0)
    u = A.uniforms_for(A.params_for({'creep': 0.0}), 2.0, 0.0, 0, 0, T.BOUND_PERIODIC)['dune_avalanche']
    uc = A.uniforms_for(A.params_for({'creep': 0.02}), 2.0, 0.0, 0, 0, T.BOUND_PERIODIC)['dune_avalanche']
    pins = np.zeros(SHAPE + (2,), np.float32)
    noisy = st_of(np.zeros(SHAPE, np.float32), 5.0 + T.random_field(SHAPE, -0.2, 0.2, seed=5))   # slab noise only
    smooth = noisy
    for _ in range(30):
        smooth = A.twin_avalanche({'st': smooth, 'pins': pins}, uc)['outSt']
    rough0 = float(np.abs(np.diff(noisy[..., 1], axis=1)).mean())
    rough1 = float(np.abs(np.diff(smooth[..., 1], axis=1)).mean())
    rel = float(smooth[..., 1].sum(dtype=np.float64) / noisy[..., 1].sum(dtype=np.float64) - 1.0)
    check('creep_smooths_slab_noise_and_conserves', rough1 < 0.8 * rough0 and abs(rel) <= 1e-5,
          {'mean |dh| between neighbours before': rough0, 'after 30 passes': rough1, 'relative mass change': rel})
    pins = np.zeros(SHAPE + (2,), np.float32)
    st = st_of(bed, sand)
    out = A.twin_avalanche({'st': st, 'pins': pins}, u)['outSt']
    rel = float(out[..., 1].sum(dtype=np.float64) / sand.sum(dtype=np.float64) - 1.0)
    check('avalanche_conserves_sand', abs(rel) <= 1e-6, {'relative change, one pass': rel})
    check('avalanche_never_moves_rock', np.array_equal(out[..., 0], st[..., 0]) and
          bool(np.all(out[..., 1][sand == 0] >= 0.0)) and bool(np.all(out[..., 1] >= 0.0)))
    bare = sand == 0
    gave = (out[..., 1] < sand - 1e-7) & bare
    check('avalanche_bare_cells_give_nothing', not gave.any())
    # a sand cone on a flat bed relaxes to the angle of repose
    n, cell = 64, 2.0
    jj, ii = np.mgrid[0:n, 0:n]
    r = np.hypot(ii - 31.5, jj - 31.5) * cell
    cone = np.maximum(40.0 - r * 1.5, 0.0).astype(np.float32)        # 56 degrees
    st = st_of(np.zeros((n, n), np.float32), cone)
    pins = np.zeros((n, n, 2), np.float32)
    t0 = time.perf_counter()
    for _ in range(400):
        st = A.twin_avalanche({'st': st, 'pins': pins}, u)['outSt']
    gy, gx = np.gradient(st[..., 1].astype(np.float64), cell)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    p99 = float(np.percentile(s[st[..., 1] > 0.5], 99))
    check('avalanche_relaxes_to_repose', 29.0 <= p99 <= 34.0,
          {'cone flanks before deg': 56.3, 'p99 after 400 passes deg': round(p99, 2), 'repose deg': 31.0,
           'mass change': float(st[..., 1].sum(dtype=np.float64) / cone.sum(dtype=np.float64) - 1.0),
           'seconds': round(time.perf_counter() - t0, 2)})


def test_dither():
    worst = 0.0
    n = 400
    h = T.pcg(np.arange(n * n, dtype=np.int64))
    for d in range(0, 360, 10):
        for L in (1.7, 3.0, 4.35):
            hop = A.transport_dir(float(d)) * L
            vx, vy = A._hop_choice(h, np.float32(hop[0]), np.float32(hop[1]))
            err = math.hypot(float(vx.mean()) - hop[0], float(vy.mean()) - hop[1])
            worst = max(worst, err)
    check('hop_dither_unbiased_any_direction', worst <= 0.01,
          {'worst |mean hop - real hop| cells over 108 cases of 160000 sources': worst})


def test_shadow():
    n, cell = 96, 2.0
    jj, ii = np.mgrid[0:SHAPE[0], 0:n]
    x = ii * cell
    ridge = np.where(x < 80.0, x * math.tan(math.radians(12.0)), 80.0 * math.tan(math.radians(12.0))
                     - (x - 80.0) * math.tan(math.radians(32.0)))                 # stoss 12, lee 32 degrees
    ridge = np.maximum(ridge, 0.0).astype(np.float32)
    st = st_of(np.zeros_like(ridge), ridge)
    p = A.params_for({'shadow_lo_deg': 15.0, 'shadow_deg': 15.0, 'shadow_reach': 40})
    u = A.uniforms_for(p, cell, 270.0, 0, 0, T.BOUND_OPEN)['dune_shadow']      # a west wind: sand moves east
    sh = A.twin_shadow({'st': st}, u)['outShadow'][..., 0]
    row = sh[SHAPE[0] // 2]
    crest = 40
    top = float(ridge.max())
    # the lee: shadowed down to where the 15-degree line from the crest meets the ground (within the reach)
    lee_end = crest + int((top / math.tan(math.radians(15.0))) / cell)
    stoss_clear = bool(np.all(row[1:crest] == 0.0))
    lee_dark = bool(np.all(row[crest + 1:min(lee_end - 1, crest + 40)] == 1.0))
    beyond = bool(np.all(row[min(lee_end + 2, n - 1):] == 0.0)) if lee_end + 2 < crest + 40 else True
    check('shadow_in_the_lee_only', stoss_clear and lee_dark and beyond,
          {'stoss clear': stoss_clear, 'lee shadowed to the 15-degree line': lee_dark, 'clear beyond it': beyond,
           'crest col': crest, '15-degree line meets the ground at col': lee_end})


def test_determinism():
    bed, sand = fields(11)
    a = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {}, seed=3)
    b = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {}, seed=3)
    c = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {}, seed=4)
    for s in (a, b, c):
        s.run([(200.0, 1.0)], 15, block=15)
    check('same_seed_same_field', np.array_equal(a.st, b.st))
    check('other_seed_other_field', not np.array_equal(a.st, c.st))


def main():
    t0 = time.perf_counter()
    for fn in (test_declarations, test_gather_equals_scatter, test_mass, test_avalanche, test_dither, test_shadow,
               test_determinism):
        t = time.perf_counter()
        try:
            fn()
        except Exception:                                          # noqa: BLE001
            check(fn.__name__ + '_ran', False, traceback.format_exc()[-1500:])
        sec = time.perf_counter() - t
        RESULTS.setdefault('seconds_per_test', {})[fn.__name__] = round(sec, 2)
        print(f'  ({fn.__name__}: {sec:.1f} s)', flush=True)
    RESULTS['failed'] = FAILED
    RESULTS['seconds'] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(OUT, 'twin_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"[wind_sand twins] {'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} in {RESULTS['seconds']} s")
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
