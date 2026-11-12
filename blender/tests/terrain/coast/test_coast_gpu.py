"""The coast package's GPU tests (Blender, through a GPU slot):

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain/coast/test_coast_gpu.py

  1. parity: ONE dispatch of each coast kernel against its numpy twin on a non-square 96 x 80 field (design section
     2.5: within 1e-4 x the output's range): coast_fetch_16 (a coast with a bay, a narrow headland and an island),
     coast_seed (a wavy level set with an island, a payload), coast_jfa at steps 1, 4 and 16 on that seed state
  2. the whole jump flood (seed + JFA+2 schedule) on the GPU against the twin device: the distance to the zero line
     within 1e-4 cells
  3. op 'coast' on the GPU against the twin device on a synthetic downland coast (256^2 at 4 m: the shore plan, the
     retreat, the face, the platform, beaches): the surface within 0.05 m on 99.9 % of cells (world noise on the GPU
     agrees with numpy to 5e-6 of its range; a cell whose level set sits within that of zero may fall either side)
  4. cost: the shore plan (fetch over 20 km + two jump floods) at 1024^2 on the Seven Sisters reference's coast at
     23.4 m cells (the coarsest level of a film sea_cliffs run)
Writes blender/tests/terrain/out/coast/gpu_tests.json; exit code 1 on a failure.
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
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'coast'))
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, '..', 'reference'))

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.core.levels import Level  # noqa: E402
from eidoblend.terrain.solvers import coast as CO  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402

RESULTS = {}
FAILED = []
F32 = np.float32
GPU = FL.device('gpu')
TWIN = FL.device('twin')


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def parity(kernel, inputs, uniforms, out_shapes, tol=1e-4):
    got, want = {}, {}
    for dev, res in ((GPU, got), (TWIN, want)):
        tex = {k: dev.texture(v) for k, v in inputs.items()}
        outs = {k: dev.empty(shp[:2], shp[2]) for k, shp in out_shapes.items()}
        dev.run(kernel, tex, outs, uniforms)
        for k, t in outs.items():
            res[k] = dev.read(t)
    return T.compare(got, want, tol), got, want


def coast_mask(H=80, W=96):
    jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
    land = jj > 30 + 6 * np.sin(ii / 9.0)
    land &= ~((ii - 48) ** 2 / 14.0 ** 2 + (jj - 36) ** 2 / 12.0 ** 2 < 1)
    land |= (np.abs(ii - 20) < 3) & (jj > 12)
    land |= (ii - 75) ** 2 + (jj - 12) ** 2 < 25
    land &= ii > 4
    return ~land


def wavy_phi(H=80, W=96):
    jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
    phi = (jj - 40 - 7 * np.sin(ii / 7.0) - 3 * np.cos(ii / 3.1)) * 1.3
    phi = np.where((ii - 70) ** 2 + (jj - 15) ** 2 < 36, 5.0, phi)
    return phi.astype(F32), (ii * 0.01 + jj * 0.001).astype(F32)


def test_parity():
    sea = coast_mask().astype(F32)
    shape = sea.shape
    k = CO.fetch_kernel(16)
    rep, got, want = parity(k, {'seaT': sea}, {'uMaxCells': 150.0}, {'outE': shape + (1,)})
    g, w = got['outE'][..., 0], want['outE'][..., 0]
    shore = w >= 0
    d = np.abs(g - w)[shore]
    check('parity coast_fetch_16 (exact grid traversal, 16 rays to 150 cells)', rep['ok'],
          f"worst {rep['worst']:.3g} of the range; shore cells {int(shore.sum())}, |dE| max {d.max():.2e}; "
          f"non-shore -1 on both: {bool((g[~shore] == -1).all())}")
    phi, pay = wavy_phi()
    rep, got, _ = parity(CO.SEED, {'phiT': phi, 'payT': pay}, {}, {'outS': shape + (4,)})
    check('parity coast_seed (sub-cell zero crossings + payload)', rep['ok'], f"worst {rep['worst']:.3g}")
    st = got['outS']
    for step in (16, 4, 1):
        rep, _, _ = parity(CO.JFA, {'st': st}, {'uStep': step}, {'outS': shape + (4,)})
        check(f'parity coast_jfa step {step}', rep['ok'], f"worst {rep['worst']:.3g}")


def test_flood():
    phi, pay = wavy_phi()
    dg, pg = CO.nearest_crossing(GPU, phi, pay)
    dt, pt = CO.nearest_crossing(TWIN, phi, pay)
    fin = np.isfinite(dt)
    e = np.abs(dg - dt)[fin]
    check('jump flood GPU vs twin: distance to the zero line within 1e-4 cells', e.max() <= 1e-4 and
          bool((np.isfinite(dg) == fin).all()),
          f'max |d_gpu - d_twin| {e.max():.2e} cells; payload equal on {float((np.abs(pg - pt) < 1e-6).mean()):.4%}')


def synthetic_coast(n=256, cell=4.0):
    side = n * cell
    lv = Level(index=0, role='main', x0=-side / 2, y0=-side / 2, side=side, cell=cell, n=n)
    X, Y = lv.xy()
    land = 55.0 + 0.04 * Y + 9.0 * np.sin(X / 61.0) + 4.0 * np.cos(X / 23.0 + Y / 37.0)
    shore = -150.0 + 60.0 * np.sin(X / 170.0) + 25.0 * np.cos(X / 53.0)      # headlands and bays
    land = np.where(Y < shore, -5.0 - 0.01 * (shore - Y), land)
    return lv, land


def test_op():
    lv, land = synthetic_coast()
    out = {}
    for dev in (GPU, TWIN):
        f = Fields(lv, {'h': land.astype(F32), 'bed': land.astype(F32)})
        ctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='grow', pins=None, shared={},
                              sea_level=0.0, device=dev, log=lambda m: print('   ' + m, flush=True))
        t0 = time.perf_counter()
        CO.op_coast(f, lv, {'retreat_m': 80.0, 'fetch_max_m': 4000.0, 'weakness': 0.3, 'stacks': 0.5,
                            'beach_exposure': [0.38, 0.46]}, 3, ctx=ctx)
        out[dev.name] = (np.asarray(f['h'], np.float64), time.perf_counter() - t0)
    hg, hw = out['gpu'][0], out['twin'][0]
    d = np.abs(hg - hw)
    frac = float((d <= 0.05).mean())
    check("op 'coast' on the GPU vs the twin device (256^2 at 4 m)", frac >= 0.999,
          f'{frac:.4%} of cells within 0.05 m (p99 {np.percentile(d, 99):.3g} m, max {d.max():.3g} m); '
          f'gpu {out["gpu"][1]:.2f} s, twin {out["twin"][1]:.2f} s')
    np.savez_compressed(os.path.join(OUT, 'gpu_op_coast.npz'), land=land.astype(F32), h_gpu=hg.astype(F32),
                        h_twin=hw.astype(F32))


def test_cost():
    import landform_refs as LR
    h, _meta = LR.load('seven_sisters')
    h = np.asarray(h, np.float64)[::-1]                           # row 0 = south
    n = 1024
    cell = 24000.0 / n
    # the reference's 6 km coast placed in a 24 km window (the coarsest level): the rest land behind, sea in front
    big = np.full((n, n), 40.0)
    m = int(round(6000.0 / cell))
    j0 = i0 = (n - m) // 2
    small = h[::max(1, h.shape[0] // m)][:m, ::max(1, h.shape[1] // m)][:, :m]
    big[j0:j0 + small.shape[0], i0:i0 + small.shape[1]] = small
    big[:j0, :] = -5.0
    lv = Level(index=0, role='context', x0=-12000.0, y0=-12000.0, side=24000.0, cell=cell, n=n)
    P = CO.params_for({})
    GPU.read(GPU.texture(np.zeros((4, 4), F32)))
    t0 = time.perf_counter()
    d0, E, info = CO.plan_shore(GPU, CO.sea_phi(big, 0.0), cell, P)
    t_plan = time.perf_counter() - t0
    phi = d0.astype(np.float64) - 300.0
    t1 = time.perf_counter()
    CO.nearest_crossing(GPU, np.where(phi < 0, np.minimum(phi, -1e-3), np.maximum(phi, 1e-3)).astype(F32))
    t_flood = time.perf_counter() - t1
    RESULTS['cost'] = dict(cells=n, cell_m=round(cell, 2), shore_cells=info.get('shore_cells'),
                           plan_s=round(t_plan, 3), second_flood_s=round(t_flood, 3),
                           exposure_p10_p50_p90=[info.get('exposure_p10'), info.get('exposure_p50'),
                                                 info.get('exposure_p90')])
    check('cost: the shore plan at 1024^2 (fetch over 20 km + jump flood) under 2 s', t_plan < 2.0,
          f"{t_plan:.2f} s for {info.get('shore_cells')} shore cells; a second jump flood {t_flood:.2f} s")


def main():
    t0 = time.time()
    for fn in (test_parity, test_flood, test_op, test_cost):
        try:
            fn()
        except Exception as e:                                        # noqa: BLE001
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
    RESULTS['seconds'] = round(time.time() - t0, 1)
    RESULTS['failed'] = FAILED
    from eidoblend.terrain.core import gpu as G
    RESULTS['compile_ms'] = {k: v for k, v in dict(G.COMPILE_MS).items() if 'coast' in k}
    with open(os.path.join(OUT, 'gpu_tests.json'), 'w') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f'[coast.gpu] {len(FAILED)} failed: {FAILED}' if FAILED else '[coast.gpu] all passed', flush=True)
    os._exit(1 if FAILED else 0)


main()
