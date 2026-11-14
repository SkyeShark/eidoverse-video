"""Wind and sand on the GPU (Blender 5.2, gpu.compute), package 8's tests (DESIGN.md section 11):

    bash run_blender.sh blender/tests/terrain/wind_sand/test_gpu.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

  - parity: each kernel (dune_shadow, dune_activate, dune_transport, and the avalanche source) in one dispatch
    against its numpy twin, on a non-square 96 x 80 field with pins, in every boundary mode (core/twins.parity:
    max |gpu - twin| <= 1e-4 x the range); and the integer hash: the plan records (lift, hop, landing hop) and the
    transported sand IDENTICAL to the twin's, record for record
  - many iterations: the GPU loop and the twin loop from one start stay identical for 40 iterations (or the first
    iteration where they part is reported)
  - sand mass conserved on the GPU: a periodic 512^2 field under three winds for 3000 iterations
  - one wind gives slip faces on the lee side: of the steep cells (> 24 degrees) of a transverse field, nearly all
    face downwind and almost none upwind
  - the four wind regimes give four dune families (barchan, transverse, linear, star), told apart by sand cover,
    separate dune bodies, crest orientation and its coherence, and the slip faces' directions
  - cost: one iteration at 1024^2, and the design's 20,000 iterations at 1024^2 (<= 60 s)

Results: out/wind_sand/gpu_tests.json, and the four families' fields in out/wind_sand/regimes_test/ for
sheet_regimes.py --tag test.
"""
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
sys.path.insert(0, HERE)
import plain_import  # noqa: E402

plain_import.install()
OUT = os.path.normpath(os.path.join(plain_import.OUT, '..', 'wind_sand'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import gpu as G  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import aeolian as A  # noqa: E402
import dune_measures as DM  # noqa: E402

FAILED = []
RESULTS = {}
SHAPE = (80, 96)


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def fields(seed=0):
    bed = T.random_field(SHAPE, 0.0, 5.0, seed=seed + 1, smooth=2)
    sand = np.maximum(T.random_field(SHAPE, -2.0, 6.0, seed=seed + 2, smooth=2), 0.0)
    return np.stack([bed, sand], -1).astype(np.float32)


def steering(seed=10, steer_deg=25.0, turn_deg=10.0):
    """A Steering on the test grid: three smooth random fields of about unit variance, clipped at +-2."""
    n = np.stack([np.clip(3.0 * T.random_field(SHAPE, -1.0, 1.0, seed=seed + k, smooth=6), -2.0, 2.0)
                  for k in range(3)])
    return A.Steering(n, steer_deg, turn_deg)


def test_parity():
    """Each kernel in one dispatch against its twin, with the wind unturned and steered (the `wind` input: each
    cell's own turn, and the transport's box of hops around every turn)."""
    st = fields(3)
    pw, ph = T.pin_pattern(SHAPE, seed=4, band=4, value=(0.0, 6.0))
    pins = np.stack([pw, ph], -1).astype(np.float32)
    aval = G.kernel(source=A.AVALANCHE_SRC, name='dune_avalanche')
    stg = steering()
    worst = {}
    exact_plan, exact_sand, n_cases = 0, 0, 0
    for mode_name, mode in T.BOUNDARY_CASES:
        for d, rise in ((0.0, 'upwind'), (37.0, 'sand'), (225.0, 'sand'), (301.0, 'upwind')):
            for steered in (False, True):
                wind, turn = stg.for_wind(d) if steered else (A.unturned(SHAPE), (0.0, 0.0))
                tag = f'{mode_name} {d:g}' + (' steered' if steered else '')
                p = A.params_for({'p_lift': 0.3, 'long_factor': 2.0, 'speedup': 0.6, 'lift_boost': 4.0,
                                  'rise': rise, 'speed_from_m': 0.5, 'speed_ref_m': 4.0,
                                  'speed_pow': 3 if d == 225.0 else (2 if d == 37.0 else 1)})
                u = A.uniforms_for(p, 4.0, d, 7, 11, mode, turn)
                r = T.parity('dune_shadow', {'st': st, 'wind': wind}, u['dune_shadow'])
                worst[f'dune_shadow {tag}'] = r['worst']
                sh = A.twin_shadow({'st': st, 'wind': wind}, u['dune_shadow'])['outShadow']
                r = T.parity('dune_activate', {'st': st, 'shadow': sh, 'wind': wind}, u['dune_activate'])
                worst[f'dune_activate {tag}'] = r['worst']
                # the integer hash: the GPU's plan records equal the twin's exactly
                k = G.kernel('dune_activate')
                outp = G.empty(SHAPE, channels=4)
                G.run(k, None, samplers={'st': G.texture(st), 'shadow': G.texture(sh), 'wind': G.texture(wind)},
                      images={'outPlan': outp}, uniforms=u['dune_activate'])
                gp = G.read(outp)
                tp = A.twin_activate({'st': st, 'shadow': sh, 'wind': wind}, u['dune_activate'])['outPlan']
                exact_plan += int(np.array_equal(gp, tp))
                r = T.parity('dune_transport', {'st': st, 'plan': tp}, u['dune_transport'])
                worst[f'dune_transport {tag}'] = r['worst']
                kt = G.kernel('dune_transport')
                outs = G.empty(SHAPE, fmt='RG32F')
                G.run(kt, None, samplers={'st': G.texture(st), 'plan': G.texture(tp)}, images={'outSt': outs},
                      uniforms=u['dune_transport'])
                exact_sand += int(np.array_equal(G.read(outs), A.twin_transport({'st': st, 'plan': tp},
                                                                                 u['dune_transport'])['outSt']))
                n_cases += 1
        ua = A.uniforms_for(A.params_for({'creep': 0.01}), 4.0, 0.0, 0, 0, mode)['dune_avalanche']
        r = T.parity(aval, {'st': st, 'pins': pins if mode == T.BOUND_PINNED else np.zeros_like(pins)}, ua)
        worst[f'dune_avalanche {mode_name}'] = r['worst']
    w = max(worst.values())
    check('kernels_match_twins_every_boundary_mode', w <= 1e-4,
          {'worst |gpu - twin| / range': w, 'per case': {k: float(f'{v:.3g}') for k, v in worst.items()}})
    check('integer_hash_plans_identical', exact_plan == n_cases,
          f'{exact_plan} of {n_cases} cases: every plan record (lift, hop x, hop y, landing hop) equal to the twin')
    check('gather_identical_to_twin', exact_sand == n_cases,
          f'{exact_sand} of {n_cases} cases: transported sand bit-identical to the twin')


def test_many_iterations():
    st = fields(5)
    p = {'hop_cells': 3.0}
    res = {}
    for name, stg in (('unturned', None), ('steered', steering(seed=30))):
        g = A.SandSim(st[..., 0], st[..., 1], 4.0, T.BOUND_PERIODIC, p, seed=9, steer=stg)
        t = A.TwinSim(st[..., 0], st[..., 1], 4.0, T.BOUND_PERIODIC, p, seed=9, steer=stg)
        first, worst = None, 0.0
        sched = A.schedule(A.KINDS['star']['winds'], 40, 10, 8.0, 9, gust=4, spread_deg=20.0, with_wind=True)
        it = 0
        for d, b, w in sched:
            for _ in range(b):
                if it >= 40:
                    break
                g.step(d, w)
                t.step(d, w)
                gs = g.read()[1]
                diff = float(np.abs(gs - t.st[..., 1]).max())
                worst = max(worst, diff)
                if diff > 0 and first is None:
                    first = it
                it += 1
        res[name] = {'max |gpu - twin| sand, m': worst, 'first iteration that differs': first, 'iterations': it}
    check('gpu_and_twin_loops_agree_40_iterations', max(r['max |gpu - twin| sand, m'] for r in res.values()) <= 1e-4,
          res)


def test_mass_gpu():
    n, cell = 512, 4.0
    lv = L.Level(0, 'main', 0.0, 0.0, n * cell, cell, n)
    p = A.resolve_params({'kind': 'star', 'sand_m': 8.0, 'spacing_m': 200.0})
    bed, sand = A.start_fields(lv, p, seed=2, period_m=lv.side)
    sim = A.SandSim(bed, sand, cell, T.BOUND_PERIODIC, p, seed=3)
    tot0 = float(np.sum(sand, dtype=np.float64))
    t0 = time.perf_counter()
    it = sim.run(p['winds'], 3000)
    b, s = sim.read()
    rel = float(np.sum(s, dtype=np.float64) / tot0 - 1.0)
    check('sand_mass_conserved_gpu', abs(rel) <= 1e-5, {'grid': f'{n}^2 periodic', 'iterations': it,
                                                        'relative change of the total': rel,
                                                        'seconds': round(time.perf_counter() - t0, 2)})


BOX = {
    'barchan': dict(sand_m=1.0, spacing_m=150.0, supply_var=0.5),
    'transverse': dict(sand_m=6.0, spacing_m=150.0),
    'linear': dict(sand_m=6.0, spacing_m=200.0),
    'star': dict(sand_m=8.0, spacing_m=200.0),
}


def run_kind(kind, iters, n=256, cell=4.0, seed=11):
    """The kind on a periodic box; then one more wind cycle block by block, collecting the slip faces' aspects at
    the end of each block (a star dune's faces point every way over a cycle, not at any one moment)."""
    lv = L.Level(0, 'main', 0.0, 0.0, n * cell, cell, n)
    p = A.resolve_params(dict(BOX[kind], kind=kind))
    bed, sand = A.start_fields(lv, p, seed=3, period_m=lv.side)
    bed[:] = 0.0
    sim = A.SandSim(bed, sand, cell, T.BOUND_PERIODIC, p, seed=seed)
    done = sim.run(p['winds'], iters)
    faces = []
    for d, b in A.cycle_blocks(p['winds'], int(p['block'])):
        for _ in range(b):
            sim.step(d)
        done += b
        bb, ss = sim.read()
        slope, aspect, _gx, _gy = DM.slope_aspect(bb + ss, cell)
        faces.append(aspect[slope > 20.0])
    b, s = sim.read()
    s = A.denoise(s, float(p['smooth_cells']), periodic=True)
    return p, b + s, s, done, np.concatenate(faces)


def test_families():
    out = os.path.join(OUT, 'regimes_test')
    os.makedirs(out, exist_ok=True)
    m = {}
    for kind in ('barchan', 'transverse', 'linear', 'star'):
        t0 = time.perf_counter()
        p, h, s, done, faces = run_kind(kind, 18000)
        cell = 4.0
        thick = 0.25 * p['slab_cells'] * cell
        meas = DM.summary(h, cell, s, p['winds'], thick_m=thick)
        main = max(p['winds'], key=lambda w: w[1])[0]
        horns, nb = DM.horns_downwind(s, cell, main, max(thick, 0.5))
        cyc_n, cyc_dirs = DM.lee_peaks_of(faces)
        meas.update(iters=done, seconds=round(time.perf_counter() - t0, 2), spacing_m=A.spacing_peak(h, cell),
                    relief_m=float(np.ptp(h)), horns_downwind_share=horns, horn_bodies=nb,
                    cycle_lee_peaks=cyc_n, cycle_lee_dirs=cyc_dirs)
        m[kind] = meas
        np.savez_compressed(os.path.join(out, f'{kind}.npz'), iters=np.array([done]), h=h[None].astype(np.float32),
                            sand=s[None].astype(np.float32), cell=cell)
        with open(os.path.join(out, f'{kind}.json'), 'w') as f:
            json.dump(dict(kind=kind, params={k: v for k, v in p.items() if not callable(v)}, n=256, cell=cell,
                           measures=[meas]), f, indent=1, default=str)
    # one wind: slip faces on the lee side (transverse ridges)
    tr = m['transverse']
    check('one_wind_slip_faces_on_the_lee', tr['lee_lee_share'] >= 0.8 and tr['lee_stoss_share'] <= 0.1,
          {'steep cells facing downwind': tr['lee_lee_share'], 'facing upwind': tr['lee_stoss_share'],
           'mean aspect of the steep cells vs downwind, deg': tr['lee_mean_offset_deg']})
    # the four families, each by what defines it
    b, li, st = m['barchan'], m['linear'], m['star']
    downwind = (A.KINDS['transverse']['winds'][0][0] + 180.0) % 360.0
    tr_axis = DM.axis_offset(tr['gradient_dir_deg'], downwind)
    lin_axis = DM.axis_offset(li['gradient_dir_deg'], 90.0)        # resultant from 180: crests N-S, gradient E-W
    fam = {
        'barchan: separate crescents on bare ground, horns downwind (cover < 0.5, >= 10 bodies, the footprint '
        'ahead of the mass in >= 70 % of them)':
            b['sand_cover'] < 0.5 and b['bodies'] >= 10 and b['horns_downwind_share'] >= 0.7,
        'transverse: a continuous sheet of ridges across the wind (cover >= 0.6, gradient within 30 deg of the '
        'wind, lee faces only)': tr['sand_cover'] >= 0.6 and tr_axis <= 30.0 and tr['lee_lee_share'] >= 0.8,
        'linear: ridges along the resultant (coherence >= 0.5, crests within 20 deg of north-south, 2 lee '
        'directions)': li['coherence'] >= 0.5 and lin_axis <= 20.0 and li['lee_peaks'] == 2,
        # (over the cycle or at its end: since the gusts, the steering and the speed-up's power spread a star
        # field's faces over every direction, the weakest wind's family can stand out only in the field it leaves)
        'star: no ridge direction (coherence < 0.3, against linear\'s >= 0.5) and slip faces in 3 or more '
        'directions over a wind cycle or at its end':
            st['coherence'] < 0.3 and max(st['cycle_lee_peaks'], st['lee_peaks']) >= 3,
    }
    check('four_regimes_four_families', all(fam.values()),
          {'families': fam,
           'measures': {k: {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in mm.items()
                            if kk in ('sand_cover', 'bodies', 'coherence', 'gradient_dir_deg', 'lee_peaks',
                                      'lee_peak_dirs', 'lee_lee_share', 'lee_stoss_share', 'lee_mean_offset_deg',
                                      'horns_downwind_share', 'horn_bodies', 'cycle_lee_peaks', 'cycle_lee_dirs',
                                      'slope_p99', 'relief_m', 'spacing_m', 'iters', 'seconds')}
                        for k, mm in m.items()}})


def test_cost():
    n, cell = 1024, 8.0
    lv = L.Level(0, 'main', 0.0, 0.0, n * cell, cell, n)
    res = {}
    for kind in ('star', 'transverse'):
        p = A.resolve_params({'kind': kind})
        bed, sand = A.start_fields(lv, p, seed=2, period_m=lv.side)
        sim = A.SandSim(bed, sand, cell, T.BOUND_PERIODIC, p, seed=3)
        sim.run(p['winds'], 50)                                 # compile, warm up
        G.sync(sim.st.src)
        t0 = time.perf_counter()
        it = sim.run(p['winds'], 2000)
        G.sync(sim.st.src)
        ms = (time.perf_counter() - t0) * 1000.0 / it
        res[kind] = dict(ms_per_iteration=round(ms, 3), passes_per_iteration=3 + int(p['aval_passes']),
                         seconds_for_20000=round(ms * 20.0, 1))
    check('dune_model_20000_iterations_1024_under_60s', max(r['seconds_for_20000'] for r in res.values()) <= 60.0,
          dict(res, kernel_compile_ms={k: v for k, v in G.COMPILE_MS.items() if k.startswith('dune')}))


def main():
    t0 = time.perf_counter()
    args = plain_import.script_args()
    only = args[args.index('--only') + 1].split(',') if '--only' in args else None
    path = os.path.join(OUT, 'gpu_tests.json')
    if only and os.path.exists(path):                    # rerun some tests, keep the others' recorded results
        with open(path, encoding='utf-8') as f:
            RESULTS.update(json.load(f))
    RESULTS['gpu'] = G.init()
    tests = (test_parity, test_many_iterations, test_mass_gpu, test_families, test_cost)
    for fn in tests:
        if only and fn.__name__[5:] not in only:
            continue
        t = time.perf_counter()
        try:
            fn()
        except Exception:                                          # noqa: BLE001
            check(fn.__name__ + '_ran', False, traceback.format_exc()[-2000:])
        RESULTS.setdefault('seconds_per_test', {})[fn.__name__] = round(time.perf_counter() - t, 2)
    FAILED[:] = [k for k, v in RESULTS.items() if isinstance(v, dict) and 'ok' in v and not v['ok']]
    RESULTS['failed'] = FAILED
    RESULTS['seconds'] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(OUT, 'gpu_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"[wind_sand gpu] {'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} in {RESULTS['seconds']} s",
          flush=True)


main()
