"""The detail package's GPU tests (Blender, through a GPU slot):

    bash run_blender.sh blender/tests/terrain/detail/test_detail_gpu.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

  1. parity: one dispatch of every kernel (pipes_flux, pipes_water, pipes_transport, pipes_thermal, breakup) against
     its numpy twin on a 96 x 80 field with pins, in the open, periodic and pinned modes, within 1e-4 x the range of
     every output channel (the design's test), with random rain (the PCG hash) and edge outflow switched on; the ground
     as the kernels hold it, a base 500 cells up plus a change
  2. conservation on the GPU over 3,000 steps at 128^2, heights 500+ cells: with closed edges and with periodic ones,
     ground + suspended sediment is conserved (its net change against what was moved) and the water follows its budget
     exactly (each step: W' = (W + rain) (1 - Ke dt))
  3. a multi-step run on the GPU against the twins (300 steps, 64^2): compared by numbers, not texels
  4. costs at 1024^2: one pipe-model step (four passes), a whole hydraulic level (3,000 steps), the breakup dispatch
     and its relaxation
Writes blender/tests/terrain/out/detail/gpu_tests.json; exit code 1 on a failure.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import gpu as G  # noqa: E402
from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core.levels import Level  # noqa: E402
from eidoblend.terrain.solvers import hydraulic as HY  # noqa: E402
from eidoblend.terrain.solvers import detail as DT  # noqa: E402

RESULTS = {}
FAILED = []
F = np.float32
SHAPE = (80, 96)


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def pipe_inputs(seed=1, shape=SHAPE):
    """The ground as base + change (the kernels' form): a rough base of 500-520 cells (far from 0, so the precision
    matters), a change of +-0.5 cells, water, sediment, the cohesive top under it, fluxes, sources and pins."""
    b0 = 500.0 + T.random_field(shape, 0.0, 20.0, seed, smooth=2)
    dl = T.random_field(shape, -0.5, 0.5, seed + 7, smooth=1)
    d = T.random_field(shape, 0.0, 0.05, seed + 1)
    s = T.random_field(shape, 0.0, 0.01, seed + 2)
    bed = dl - T.random_field(shape, 0.0, 0.5, seed + 3)
    fa = T.rgba(*[T.random_field(shape, 0.0, 2.0, seed + 10 + c) for c in range(4)])
    fb = T.rgba(*[T.random_field(shape, 0.0, 2.0, seed + 20 + c) for c in range(4)])
    src = T.rgba(T.random_field(shape, 0.5, 1.5, seed + 4), T.random_field(shape, 0.0, 0.01, seed + 5),
                 T.random_field(shape, 0.05, 1.0, seed + 6))
    pw, ph = T.pin_pattern(shape, seed, band=4, value=(-1.0, 1.0))
    return {'st': T.rgba(dl, d, s, bed), 'base': T.rgba(b0), 'fa': fa, 'fb': fb, 'src': src,
            'pin': T.rgba(pw, ph)}


def pipe_uniforms(mode, cover=0.5):
    p = HY.defaults({'rain_cover': cover})
    return HY.uniforms(p, 17, 3, mode, outflow=True)


def pick(name, u):
    return {k: u[k] for k in HY.spec(name).uniforms}


def sub(d, names):
    return {k: d[k] for k in names}


def report(name, rep):
    check(name, rep['ok'], f"worst {rep['worst']:.3g}")
    if not rep['ok']:
        print(T.report_text(rep), flush=True)


def test_parity():
    for label, mode in T.BOUNDARY_CASES:
        inp = pipe_inputs(seed=11 + mode)
        u = pipe_uniforms(mode)
        report(f'parity pipes_flux {label}',
               T.parity('pipes_flux', sub(inp, ('st', 'base', 'fa', 'fb', 'src')), pick('pipes_flux', u)))
        report(f'parity pipes_water {label}',
               T.parity('pipes_water', sub(inp, ('st', 'base', 'fa', 'fb', 'src', 'pin')), pick('pipes_water', u)))
        st2 = T.run_twin('pipes_water', sub(inp, ('st', 'base', 'fa', 'fb', 'src', 'pin')),
                         pick('pipes_water', u))['outS']
        report(f'parity pipes_transport {label}',
               T.parity('pipes_transport', {'st2': st2, 'st0': inp['st'], 'fa': inp['fa'], 'fb': inp['fb'],
                                            'src': inp['src']}, pick('pipes_transport', u)))
        b0 = 500.0 + T.random_field(SHAPE, 0.0, 60.0, 31 + mode, smooth=1)
        dl = T.random_field(SHAPE, -1.0, 1.0, 36 + mode)
        bed = dl - T.random_field(SHAPE, 0.0, 1.0, 32 + mode)
        par = T.rgba(T.random_field(SHAPE, 0.5, 3.0, 33 + mode), T.random_field(SHAPE, 0.65, 0.75, 34 + mode))
        tacc = T.rgba(T.random_field(SHAPE, -1.0, 1.0, 35 + mode))
        # outT.y is the rounding carried to the next pass (Kahan): one float32 rounding, whose "range" is itself a
        # rounding, so it is left out here; the conservation test below is what it is for
        report(f'parity pipes_thermal {label}',
               T.parity('pipes_thermal', {'st': T.rgba(dl, inp['st'][..., 1], inp['st'][..., 2], bed),
                                          'base': T.rgba(b0), 'par': par, 'pin': inp['pin'], 'tacc': tacc},
                        {'uRate': 0.06, 'uBound': mode}, channels={'outS': [0, 1, 2, 3], 'outT': [0]}))
    # breakup: world noise far from the origin, joints, bedding with dip
    p = DT._params(DT.BREAKUP, {'bedding': {'spacing_m': 6.0, 'width_m': 2.0, 'strength': 0.6, 'depth_m': 0.8,
                                            'dip_deg': 3.0, 'azimuth_deg': 30.0}}, 'breakup')
    for cell in (0.5, 4.0):
        lv = Level(0, 'hero', 40123.0, -25311.0, 96 * cell, cell, 96)
        terms, nt, bu = DT.breakup_terms(p, lv, seed=5)
        h = T.random_field(SHAPE, 0.0, 300.0, 41, smooth=2)
        u = DT.breakup_uniforms(p, lv, nt, bu)
        report(f'parity breakup (cell {cell} m, 40 km from the origin)',
               T.parity(DT.breakup_kernel(), {'st': T.rgba(h), 'terms': terms}, u, twin=DT.breakup))  # st first


def model_inputs(b):
    shape = b.shape
    src = T.rgba(np.ones(shape, F), None, np.full(shape, 0.5, F))
    par = T.rgba(np.full(shape, HY.BIG_TAN, F), np.full(shape, 0.7, F))
    return src, par, np.zeros(shape + (4,), F)


def run_gpu_steps(b, bed, p, mode, outflow, steps, every):
    """The model on the GPU from ground b (cell units); records (step, water total, sum of change + sediment)."""
    src, par, pin = model_inputs(b)
    run = HY.PipeRunGPU(b, bed, src, par, pin)
    rec = []
    for i in range(steps):
        run.step(p, i, 7, mode, outflow)
        if (i + 1) % every == 0:
            st = run.state()
            rec.append((i + 1, float(st[..., 1].sum(dtype=np.float64)), HY.mass(st, run.accum())))
    return run, rec


def slope_terrain(n, seed=3, base=500.0):
    """A synthetic test slope in cell units: a tilted plane with valleys and bumps (rain gathers, rills cut), lifted
    by `base` cells (a hero level's heights are hundreds of cells)."""
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    b = base + 0.45 * jj + 3.0 * np.sin(ii / n * 6.0) + T.random_field((n, n), 0.0, 2.0, seed, smooth=3)
    return b.astype(F)


def test_conservation():
    n = 128
    p = HY.defaults({'rain_cover': 1.0})
    for label, mode in (('closed', T.BOUND_OPEN), ('periodic', T.BOUND_PERIODIC)):
        b = slope_terrain(n) if mode == T.BOUND_OPEN else (500.0 + T.random_field((n, n), 0.0, 30.0, 5, smooth=3)
                                                          ).astype(F)
        run, rec = run_gpu_steps(b, b - 0.3, p, mode, False, 3000, 100)
        # the water budget, step by step: W' = (W + n^2 rain dt) (1 - Ke dt)
        W = 0.0
        rain = float(F(p['rain']) * F(p['dt'])) * n * n
        keep = float(F(max(F(1) - F(p['Ke']) * F(p['dt']), F(0))))
        worst_w = 0.0
        k = 0
        for i in range(1, 3001):
            W = (W + rain) * keep
            if k < len(rec) and rec[k][0] == i:
                worst_w = max(worst_w, abs(rec[k][1] - W) / W)
                k += 1
        # the ground's change plus the suspended sediment sums to 0: what is lost, against what was moved
        st = run.state()
        gross = float(np.abs(st[..., 0]).astype(np.float64).sum())
        net = max(abs(r[2]) for r in rec)
        check(f'GPU conservation, {label} edges, 3000 steps at 128^2: ground + sediment', net / gross < 1e-5,
              f'net change {net:.2e} cells^3 against {gross:.1f} cells^3 moved ({net / gross:.2e}); the ground moved '
              f'up to {np.abs(st[..., 0]).max():.3f} cells')
        check(f'GPU conservation, {label} edges: the water budget (rain in, evaporation out)', worst_w < 2e-5,
              f'worst relative error {worst_w:.2e}, water {rec[-1][1]:.2f} vs {W:.2f} cells^3')


def test_multistep_vs_twins():
    n = 64
    p = HY.defaults({'roughness': 0.0})
    b = slope_terrain(n, 9)
    src, par, pin = model_inputs(b)
    run = HY.PipeRunGPU(b, b.copy(), src, par, pin)
    for i in range(300):
        run.step(p, i, 7, T.BOUND_OPEN, True)
    g = run.state()
    tw, _ = HY.run_numpy(b, b.copy(), src, par, pin, p, seed=7, mode=T.BOUND_OPEN, outflow=True, steps=300)
    out = {}
    for name, a in (('gpu', g), ('twin', tw)):
        dh = a[..., 0]
        out[name] = dict(wear_p99=float(np.percentile(-dh, 99)), water=float(a[..., 1].sum()),
                         eroded=float(np.maximum(-dh, 0).sum()), deposited=float(np.maximum(dh, 0).sum()))
    rel = {k: abs(out['gpu'][k] - out['twin'][k]) / max(abs(out['twin'][k]), 1e-9) for k in out['gpu']}
    check('300 steps on the GPU vs the twins (64^2): totals within 5 %', max(rel.values()) < 0.05,
          {'gpu': out['gpu'], 'twin': out['twin'], 'relative': rel})


def test_costs():
    n = 1024
    p = HY.defaults()
    b = slope_terrain(n, 4)
    src, par, pin = model_inputs(b)
    run = HY.PipeRunGPU(b, b.copy(), src, par, pin)
    for i in range(20):
        run.step(p, i, 1, T.BOUND_OPEN, True)
    run.state()
    t0 = time.perf_counter()
    steps = 500
    for i in range(steps):
        run.step(p, 20 + i, 1, T.BOUND_OPEN, True)
    run.state()
    per_step = (time.perf_counter() - t0) / steps * 1000.0
    lv = Level(0, 'hero', -260.0, 1380.0, n * 0.5, 0.5, n)
    t0 = time.perf_counter()
    R, kf, sc, D = DT.strength(DT._params(DT.BREAKUP, None, 'breakup'), lv, b * 0.5, seed=1)
    t_strength = (time.perf_counter() - t0) * 1000.0
    t0 = time.perf_counter()
    DT.relax(b, b.copy(), sc, 0.7, 400, 0.06)
    t_relax = (time.perf_counter() - t0) * 1000.0
    RESULTS['costs'] = dict(pipe_step_ms_1024=round(per_step, 3),
                            hydraulic_level_3000_steps_s=round(per_step * 3.0, 2),
                            breakup_dispatch_ms_1024=round(t_strength, 1),
                            relax_400_iterations_ms_1024=round(t_relax, 1), compile_ms=dict(G.COMPILE_MS))
    check('a pipe-model step at 1024^2 costs at most 2 ms (four passes)', per_step <= 2.0, f'{per_step:.3f} ms')
    print('[costs]', RESULTS['costs'], flush=True)


def main():
    RESULTS['gpu'] = G.init()
    for t in (test_parity, test_conservation, test_multistep_vs_twins, test_costs):
        try:
            t()
        except Exception as e:                                  # noqa: BLE001
            traceback.print_exc()
            check(t.__name__, False, f'{type(e).__name__}: {e}')
    with open(os.path.join(OUT, 'gpu_tests.json'), 'w') as f:
        json.dump({'failed': FAILED, 'results': RESULTS}, f, indent=1, default=str)
    print(f'[detail gpu tests] {len(RESULTS) - len(FAILED) - 1} passed, {len(FAILED)} failed: {FAILED}', flush=True)
    if FAILED:
        sys.stdout.flush()
        os._exit(1)                     # (sys.exit with GPU textures alive crashed Blender's teardown once)


main()
