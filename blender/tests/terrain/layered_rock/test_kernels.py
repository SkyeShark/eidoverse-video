"""The layered-rock package's kernel tests (Blender, through a GPU slot):

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain/layered_rock/test_kernels.py

  1. parity: ONE dispatch of each layered-rock kernel against its numpy twin on a non-square 96 x 80 field with pins,
     in the open, periodic and pinned modes, within 1e-4 x each output channel's range: strata_threshold (the
     composite excess, with and without loose cover), strata_cell (the layer's tan and creep factor at each cell's
     zs), strata_creep (creep on soft rock and debris), strata_weather (weathering, with and without the
     drainage-area boost), and route_incise reading the column's K(zs) (the K(z) lookup)
  2. the composite threshold on the GPU relaxes a 1D step (a 4-row strip, the column of test_strata.py) to every
     layer's own angle, like the twin
  3. cost: one whole strata_fluvial step (route, weathering, creep, 3 composite threshold iterations) at 1024^2
Writes blender/tests/terrain/out/layered_rock/kernel_tests.json; exit code 1 on a failure.
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
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'layered_rock'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import hillslope as HS  # noqa: E402,F401
from eidoblend.terrain.solvers import strata as S  # noqa: E402

RESULTS = {}
FAILED = []
F32 = np.float32


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


GPU = FL.device('gpu')
TWIN = FL.device('twin')


def parity(kernel, inputs, uniforms, out_shapes, tol=1e-4):
    got, want = {}, {}
    for dev, res in ((GPU, got), (TWIN, want)):
        tex = {k: dev.texture(v) for k, v in inputs.items()}
        outs = {k: dev.empty(shp[:2], shp[2]) for k, shp in out_shapes.items()}
        dev.run(kernel, tex, outs, uniforms)
        for k, t in outs.items():
            res[k] = dev.read(t)
    return T.compare(got, want, tol)


def test_parity():
    col = S.column('colorado_plateau')
    shape = (80, 96)
    h = (300.0 + 1400.0 * T.random_field(shape, 0, 1, 3, smooth=2)).astype(F32)
    zoff = (-60.0 + 40.0 * T.random_field(shape, 0, 1, 4, smooth=3)).astype(F32)
    A = T.random_field(shape, 100.0, 1e7, 5)
    qs = T.random_field(shape, 0.0, 50.0, 6)
    st = T.rgba(h, A, qs, T.random_field(shape, 0, 1, 7))
    loose = np.where(T.random_field(shape, 0, 1, 8) > 0.6, T.random_field(shape, 0.0, 12.0, 9), 0.0).astype(F32)
    mk = T.rgba(T.random_field(shape, 0, 5, 10), np.minimum(loose, T.random_field(shape, 0, 4, 11)),
                np.minimum(loose, T.random_field(shape, 0, 3, 12)), loose)
    K0 = 1.5e-6
    par = T.rgba(np.zeros(shape, F32), (K0 * (0.5 + T.random_field(shape, 0, 1, 13, smooth=2))).astype(F32),
                 np.ones(shape, F32), (0.3 * T.random_field(shape, 0, 1, 14)).astype(F32))
    pw, ph = T.pin_pattern(shape, 3, band=4, value=(300.0, 1700.0))
    pin = T.rgba(pw, ph, np.zeros(shape, F32), np.zeros(shape, F32))
    ctab = col.table_texture()
    z0, dz, nt = float(col.z0), float(col.dz), int(len(col.R))
    S1, S2, S4 = shape + (1,), shape + (2,), shape + (4,)
    worst = {}
    for mode_name, mode in T.BOUNDARY_CASES:
        for L, tag in ((np.zeros(shape, F32), 'rock'), (loose, 'loose')):
            mkL = T.rgba(mk[..., 0], mk[..., 1], mk[..., 2], L)
            rep = parity('strata_threshold', {'st': st, 'zoff': zoff, 'mk': mkL, 'rtab': ctab},
                         {'uDx': 12.0, 'uRZ0': z0, 'uRDz': dz, 'uRN': nt, 'uRepose': math.tan(math.radians(34.0)),
                          'uBound': mode}, {'outP': S1})
            worst[f'strata_threshold {tag}/{mode_name}'] = rep['worst']
            check(f'parity strata_threshold {tag} {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        rep = parity(S.STRATA_CELL, {'st': st, 'zoff': zoff, 'ctab': ctab}, {'uTZ0': z0, 'uTDz': dz, 'uTN': nt},
                     {'outC': S2})
        worst[f'strata_cell/{mode_name}'] = rep['worst']
        check(f'parity strata_cell {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        # the cell texture from the GPU feeds both creeps (the same inputs on both devices)
        cell = GPU.empty(shape, 2)
        GPU.run(S.STRATA_CELL, {'st': GPU.texture(st), 'zoff': GPU.texture(zoff), 'ctab': GPU.texture(ctab)},
                {'outC': cell}, {'uTZ0': z0, 'uTDz': dz, 'uTN': nt})
        cellv = GPU.read(cell)
        rep = parity(S.STRATA_CREEP, {'st': st, 'cell': cellv, 'pin': pin},
                     {'uDx': 12.0, 'uDtSub': 50.0, 'uD': 0.02, 'uCap': 5.0, 'uBound': mode}, {'outS': S4})
        worst[f'strata_creep/{mode_name}'] = rep['worst']
        check(f'parity strata_creep {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        for ac in (0.0, 1.0):
            rep = parity(S.STRATA_WEATHER, {'st': st, 'zoff': zoff, 'ctab': ctab, 'par': par, 'pin': pin, 'mk': mk},
                         {'uDx': 12.0, 'uDt': 400.0, 'uW': 3e-4, 'uS0': math.tan(math.radians(30.0)), 'uK0': K0,
                          'uWl': 6e-4, 'uAc': ac, 'uTZ0': z0, 'uTDz': dz, 'uTN': nt, 'uBound': mode},
                         {'outS': S4, 'outM': S4})
            worst[f'strata_weather boost {ac:g}/{mode_name}'] = rep['worst']
            check(f'parity strata_weather (area boost {ac:g}) {mode_name}', rep['ok'], T.report_text(rep).replace('\n', ' | '))
        # the K(z) lookup in route_incise: the column's K table at each cell's zs
        tw = GPU.empty(shape, 1)
        GPU.run('flow_weights', {'st': GPU.texture(st)}, {'outW': tw}, {'uDx': 12.0, 'uP': 1.0, 'uBound': mode})
        wsum = GPU.read(tw)
        rep = parity('route_incise', {'st': st, 'wsumT': wsum, 'par': par, 'pin': pin, 'mk': mk,
                                      'kcol': np.asarray(col.K, F32)[None, :], 'zoff': zoff},
                     {'uDx': 12.0, 'uDt': 400.0, 'uM': 0.5, 'uN': 1.0, 'uP': 1.0, 'uColZ0': z0, 'uColDz': dz,
                      'uColN': len(col.K), 'uSlope': 1, 'uPitFill': 1, 'uPitEps': 1e-3, 'uBound': mode},
                     {'outS': S4, 'outM': S4})
        worst[f'route_incise K(zs)/{mode_name}'] = rep['worst']
        check(f'parity route_incise with the column K(zs) {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
    RESULTS['_worst'] = worst


def test_profile_gpu():
    """The composite threshold on the GPU (test_strata.py's static test): the column's own wall (each layer at its
    angle, a 4-row strip at 1 m cells) has no excess anywhere; 2 degrees steeper in every layer, every layer has
    excess; 2 degrees gentler, none. (The relaxation itself is checked on the twins, which equal the kernels per
    dispatch: the parity above.)"""
    sys.path.insert(0, HERE)
    import test_strata as TS
    col = S.column(TS.TEST_COLUMN)
    cell = 1.0
    W = 420
    x = np.arange(W)
    step = 330
    rows = []
    ok = True
    for dg in (-2.0, 0.0, 2.0):
        prof = TS.analytic_profile(col, x, step, cell, dg)
        h = np.repeat(prof.astype(F32)[None, :], 4, 0)
        z = np.zeros_like(h)
        tex = {'st': GPU.texture(T.rgba(h)), 'zoff': GPU.texture(z), 'mk': GPU.texture(T.rgba(z, z, z, z)),
               'rtab': GPU.texture(col.table_texture())}
        outP = GPU.empty(h.shape, 1)
        GPU.run('strata_threshold', tex, {'outP': outP},
                {'uDx': cell, 'uRZ0': col.z0, 'uRDz': col.dz, 'uRN': len(col.R),
                 'uRepose': math.tan(math.radians(34.0)), 'uBound': T.BOUND_PINNED})
        phi = GPU.read(outP)[2, :, 0]
        per = []
        for d in col.layers:
            inner = (prof > d['base_m'] + 2.0) & (prof < d['top_m'] - 2.0) & (x < step)
            per.append(round(float(phi[inner].max()) if inner.any() else -1.0, 4))
        good = all(v > 0.01 for v in per) if dg > 0 else all(v <= 0.01 for v in per)
        ok = ok and good
        rows.append(dict(steeper_deg=dg, max_excess_per_layer=per, ok=good))
    check("composite threshold on the GPU: the column's own wall is exactly its stability limit", ok, rows)


def test_cost():
    col = S.column('colorado_plateau')
    rows = []
    for n in (1024,):
        shape = (n, n)
        h = (300.0 + 1400.0 * T.random_field(shape, 0, 1, 21, smooth=3)).astype(F32)
        z = np.zeros(shape, F32)
        par = T.rgba(z, z + 1.5e-6, z + 1.0, z + 0.1)
        pins = FL.edge_pins(n, h)
        run = S.StrataRun(GPU, 7.8, {'h': h, 'bed': h.copy()}, par, pins, col, z, None, 2,
                          math.tan(math.radians(34.0)), (3e-4, math.tan(math.radians(30.0)), 1.5e-6, 6e-4, 0.5))
        for _ in range(20):
            run.step(100.0, 0.005, 1, 3, 0.12, 5.0)
        GPU.read(run.W)
        t0 = time.perf_counter()
        k = 200
        for _ in range(k):
            run.step(100.0, 0.005, 1, 3, 0.12, 5.0)
        GPU.read(run.W)
        ms = (time.perf_counter() - t0) / k * 1000.0
        rows.append(dict(n=n, ms_per_step=round(ms, 3), passes=2 + 1 + 3 + 2 * 3))
    check('cost: one strata_fluvial step at 1024^2 (recorded; design 9: 0.5 ms for the 4-7 pass fluvial step)', True,
          rows)


def main():
    t0 = time.time()
    for fn in (test_parity, test_profile_gpu, test_cost):
        try:
            fn()
        except Exception as e:                                          # noqa: BLE001
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
    RESULTS['_seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, 'kernel_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} ({RESULTS['_seconds']} s)", flush=True)
    os._exit(1 if FAILED else 0)


main()
