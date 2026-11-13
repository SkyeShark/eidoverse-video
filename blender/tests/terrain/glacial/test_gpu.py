"""The glacial package's GPU tests (Blender, through a GPU slot):

    python blender/tests/terrain/glacial/slot.py blender/tests/terrain/glacial/test_gpu.py

  1. parity: ONE dispatch of each kernel against its numpy twin on a non-square 96 x 80 field, within 1e-4 x each
     output channel's range: ice_flux (D8 receivers, and the water's MFD weights at p 1 and 1.3) in the open,
     periodic and pinned modes; jump_flood (the target and the distance metrics, at jumps 16, 4 and 1, from a
     half-flooded state: the candidates' metrics compared, since a last-bit tie between two seeds can rank them
     either way); u_carve (shoulders, the cap, three cirques; open and pinned)
  2. the ice discharge iterated to convergence on the GPU closes its mass balance within 1e-5
  3. the jump flood on the GPU against the brute-force lower envelope at 128^2 (distance and trough target): the
     nearest seed exact in >= 99.5 % of cells, all four best streams in >= 98 %
  4. the trough on a synthetic valley: a river valley (V, 30-degree sides, three tributaries a side, its river 600 m
     over the fill's grade line as the recipe's trunk river stands bench_m over it, falling to its outlet over the
     last 2 km) carved by carve_level with alpine_valley's glacial stage; before and after, the judge's family
     numbers (judge/family.alpine_valley) and four sections across the trunk between the tributaries: the V's U
     exponent under 1.5; the carved trunk a box trough (its floor level across, its walls at 60 degrees or more over
     most of their height, standing 300 m or more within 250 m of the floor), the tributaries hanging at least 100
     m, the trough near its width (the judge's U exponent is recorded: a box trough reads 3-8 there, as
     Lauterbrunnen's middle reach does, 5.1 and 5.4)
  5. cost: the whole carve (discharge, centrelines, cirques, jump flood, carve, walls) on a 1024^2 level
Writes blender/tests/terrain/out/glacial/gpu_tests.json; exit code 1 on a failure.
"""
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import glacial as G  # noqa: E402
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402
from judge import family as FA  # noqa: E402

OUT = os.path.join(TN, 'out', 'glacial')
RESULTS, FAILED = {}, []
F32 = np.float32
GPU = FL.device('gpu')
TWIN = FL.device('twin')
PROF = G.profile_uniforms({'floor_frac': 0.25, 'wall_toe': 0.3, 'wall_lip': 0.2, 'floor_rise': 0.06,
                           'shoulder_width': 1.5, 'shoulder_rise': 0.3, 'upper_wall': 1.5})


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def run_both(kernel, inputs, uniforms, out_shapes):
    got, want = {}, {}
    for dev, res in ((GPU, got), (TWIN, want)):
        tex = {k: dev.texture(v) for k, v in inputs.items()}
        outs = {k: dev.empty(shp[:2], shp[2]) for k, shp in out_shapes.items()}
        dev.run(kernel, tex, outs, uniforms)
        for k, t in outs.items():
            res[k] = dev.read(t)
    return got, want


def seeds(n0, n1, cell, n_streams=8, per=12, seed=3):
    rng = np.random.default_rng(seed)
    cand = np.full((n0, n1, 4), -1.0, F32)
    A = np.zeros((n0, n1, 4), F32)
    B = np.zeros((n0, n1, 4), F32)
    B[..., 0] = 1.0
    used = []
    for s in range(n_streams):
        i, j = int(rng.integers(4, n1 - 4)), int(rng.integers(4, n0 - 4))
        W = rng.uniform(4.0, 12.0) * cell
        for _ in range(per):
            if j * n1 + i not in used:
                used.append(j * n1 + i)
                cand[j, i, 0] = j * n1 + i
                A[j, i] = ((i + 0.5 + rng.uniform(-0.4, 0.4)) * cell, (j + 0.5 + rng.uniform(-0.4, 0.4)) * cell,
                           rng.uniform(0.0, 300.0), rng.uniform(100.0, 400.0))
                B[j, i] = (W * rng.uniform(0.8, 1.2), s, rng.uniform(0.0, 30.0), rng.uniform(0.0, 20.0))
            i = int(np.clip(i + rng.integers(-1, 2), 0, n1 - 1))
            j = int(np.clip(j + rng.integers(-1, 2), 0, n0 - 1))
    return cand, A, B, np.array(used, np.int64)


def seeds_c(cand, seed=5):
    """A random seedC for the seed cells of cand: floor share factors 0.4-1.2, fans 0.2-2, shoulder cuts 0-0.3."""
    rng = np.random.default_rng(seed)
    C = G.default_seed_c(cand.shape)
    at = cand[..., 0] >= 0
    k = int(at.sum())
    C[at] = np.stack([rng.uniform(0.4, 1.2, k), rng.uniform(0.2, 2.0, k), rng.uniform(0.0, 0.3, k),
                      np.zeros(k)], 1).astype(F32)
    return C


# ------------------------------------------------------------------------------------------------- 1. parity ---

def test_parity():
    shape = (80, 96)
    cell = 10.0
    h = T.random_field(shape, 0.0, 400.0, 1, smooth=2)
    Q = T.random_field(shape, 0.0, 1e6, 2)
    b = T.random_field(shape, -6.0, 2.0, 3, smooth=1)
    rng = np.random.default_rng(4)
    q_in = np.where(rng.random(shape) > 0.97, rng.uniform(1e5, 1e6, shape), 0.0).astype(F32)
    recv = G.d8_receivers(h, cell)
    for mode_name, mode in T.BOUNDARY_CASES:
        tw = GPU.empty(shape, 1)
        for p in (1.0, 1.3):
            GPU.run('flow_weights', {'st': GPU.texture(h)}, {'outW': tw}, {'uDx': cell, 'uP': p, 'uBound': mode})
            wsum = GPU.read(tw)
            for d8, w in ((1, recv), (0, wsum)):
                if d8 and p != 1.0:
                    continue
                uni = {'uDx': cell, 'uP': p, 'uWref': 750.0, 'uQw': 5e7, 'uWexp': 0.4, 'uLmax': 3000.0, 'uD8': d8,
                       'uBound': mode}
                got, want = run_both('ice_flux', {'st': h, 'wT': w, 'qT': Q, 'mb': T.rgba(b, q_in)}, uni,
                                     {'outQ': shape + (1,)})
                rep = T.compare(got, want, 1e-4)
                check(f"parity ice_flux {'D8' if d8 else f'MFD p={p:g}'} {mode_name}", rep['ok'],
                      f"worst {rep['worst']:.3g}")
    # the jump flood: from a half-flooded state (the GPU's own, so both devices start alike)
    cand0, A, B, idx = seeds(shape[0], shape[1], cell)
    C = seeds_c(cand0)
    for metric in (0, 1):
        cT, _, _ = G.jump_flood_run(GPU, cand0, A, B, cell, PROF, [32, 16], metric, seedC=C)
        mid = GPU.read(cT)
        for step in (16, 4, 1):
            got, want = run_both('jump_flood', {'candT': mid, 'seedA': A, 'seedB': B, 'seedC': C},
                                 dict(PROF, uStep=step, uDx=cell, uMetric=metric), {'outC': shape + (4,)})
            mg = G.decode_best(got['outC'], A, B, cell, PROF, metric, slot='all', seedC=C)
            mw = G.decode_best(want['outC'], A, B, cell, PROF, metric, slot='all', seedC=C)
            fin = np.isfinite(mw)
            rng_ = float(np.ptp(mw[fin])) if fin.any() else 1.0
            same_valid = np.array_equal(np.isfinite(mg), fin)
            err = float(np.max(np.abs(mg[fin] - mw[fin]))) / max(rng_, 1e-9) if fin.any() else 0.0
            ident = float((got['outC'] == want['outC']).all(axis=-1).mean())
            check(f"parity jump_flood {'target' if metric == 0 else 'distance'} step {step}",
                  same_valid and err <= 1e-4, f'metric worst {err:.3g} of the range; candidates identical in '
                                              f'{ident * 100:.2f} % of cells')
    # the U-carve
    cT, _, _ = G.jump_flood_run(GPU, cand0, A, B, cell, PROF, G.jfa_steps(96, 96), 0, seedC=C)
    cand = GPU.read(cT)
    hs = T.random_field(shape, 0.0, 700.0, 7, smooth=2)
    bed = hs - T.random_field(shape, 0.0, 5.0, 8)
    pw, ph = T.pin_pattern(shape, 9, band=4, value=(0.0, 700.0))
    cq = np.array([[200.0, 300.0, 100.0, 900.0, 0.6, 0.8, 120.0, 160.0, 0.3, 2.1, 0.15],
                   [700.0, 500.0, 50.0, 600.0, -1.0, 0.0, 90.0, 120.0, 4.0, 1.0, 0.2],
                   [450.0, 650.0, 150.0, 700.0, 0.0, -1.0, 100.0, 140.0, 5.5, 3.3, 0.1]])
    lv0 = L.plan_levels(96 * cell, 96, (48 * cell, 48 * cell), None, None, None)[0]
    cqt = G.cirque_texture(cq + np.array([lv0.x0, lv0.y0] + [0.0] * 9), lv0)
    for mode_name, mode in (('open', T.BOUND_OPEN), ('pinned', T.BOUND_PINNED)):
        uni = dict(G.carve_uniforms({'floor_frac': 0.25, 'wall_toe': 0.3, 'wall_lip': 0.2, 'floor_rise': 0.06,
                                     'shoulder_width': 1.5, 'shoulder_rise': 0.3, 'upper_wall': 1.5, 'cut': 0.6,
                                     'cut_width': 2.0, 'cap_join_m': 40.0, 'shoulder_cut_width': 2.0}),
                   uDx=cell, uJoin=60.0, uTrim=20.0, uMorAt=0.35, uMorW=0.07, uNCirq=3, uCirqExp=2.0, uCirqFloor=0.35,
                   uCirqOpen=2.5, uCirqTilt=0.14, uBound=mode)
        got, want = run_both('u_carve', {'candT': cand, 'seedA': A, 'seedB': B, 'seedC': C, 'st': T.rgba(hs, bed),
                                         'cirq': cqt, 'pin': T.rgba(pw, ph)}, uni,
                             {'outS': shape + (4,), 'outM': shape + (4,)})
        rep = T.compare(got, want, 1e-4)
        check(f'parity u_carve {mode_name}', rep['ok'], T.report_text(rep).replace('\n', ' | '))


# -------------------------------------------------------------------------------------- 2. the mass balance ---

def test_mass_balance():
    n, cell = 192, 50.0
    jj, ii = np.mgrid[0:n, 0:n]
    r = np.hypot(ii - n / 2, jj - n * 0.3) / n
    h = 2500.0 * np.exp(-3.0 * r * r) + 300.0 * T.random_field((n, n), 0, 1, 5, smooth=3)
    filled, _ = HY.fill_depressions(h)
    surf = HY.routing_surface(filled).astype(F32)
    recv = G.d8_receivers(surf, cell)
    params = {'ela_m': 1500.0}
    b = G.mass_balance(surf, 0.0, params)
    t0 = time.perf_counter()
    Q, it = G.ice_flux_converge(GPU, surf, b, cell, recv, 0.0, params=params)
    secs = time.perf_counter() - t0
    bud = G.flux_budget(Q, b, recv, cell, params)
    check('ice flux mass balance closes on the GPU', abs(bud['rel_residual']) <= 1e-5 and bud['outflow'] > 0,
          f"accumulation {bud['accumulation']:.4g} - ablation {bud['ablation']:.4g} = outflow {bud['outflow']:.4g} "
          f"(residual {bud['rel_residual']:.2e}; {it} iterations, {secs:.2f} s at {n}^2)")


# ---------------------------------------------------------------------------------- 3. the jump flood exact ---

def test_jump_flood_exact():
    n, cell = 128, 10.0
    cand0, A, B, idx = seeds(n, n, cell, n_streams=14, per=16, seed=11)
    C = seeds_c(cand0, seed=12)
    for metric, name in ((1, 'distance'), (0, 'trough target')):
        cT, _, _ = G.jump_flood_run(GPU, cand0, A, B, cell, PROF, G.jfa_steps(n, n), metric, seedC=C)
        got = G.decode_best(GPU.read(cT), A, B, cell, PROF, metric, slot='all', seedC=C)
        want = G.brute_force(idx, A, B, cell, PROF, metric, per_stream=True, seedC=C)
        tol = 1e-3 * max(1.0, float(np.max(np.where(np.isfinite(want), np.abs(want), 0))))
        first = np.abs(got[..., 0] - want[..., 0]) <= tol
        four = np.all((np.abs(got - want) <= tol) | (np.isinf(got) & np.isinf(want)), axis=-1)
        check(f'jump flood on the GPU vs brute force at 128^2, {name}', first.mean() >= 0.995 and four.mean() >= 0.98,
              f'nearest exact in {first.mean() * 100:.2f} % of cells, all four in {four.mean() * 100:.2f} %')


# ------------------------------------------------------------------------------ 4. the U fit on a synthetic V ---

def synthetic_valley(n=256, cell=31.25, bench=0.0):
    """A river valley 8 km long draining north: the trunk at x = 0 (1.2 % gradient, the recipe's floor_grade, plus
    `bench` m eased in over the 2 km above the north edge: the recipe's trunk river stands bench_m over the line its
    trough's fill grades along), 30-degree V sides up to ridges 2.4 km high at +-3.5 km, and three V tributaries a
    side square to the trunk, graded to it."""
    lv = L.plan_levels(n * cell, n, (0.0, 0.0), None, None, None)[0]
    X, Y = lv.xy()
    left = lv.side / 2 - Y                                             # the distance to the north edge
    q = np.clip(left / 2000.0, 0.0, 1.0)
    river = 200.0 + 0.012 * left + bench * q * q * (3.0 - 2.0 * q)
    tan30 = math.tan(math.radians(30.0))
    h = river + tan30 * np.abs(X)
    for side in (-1.0, 1.0):
        for yt in (-2500.0, 0.0, 2500.0):
            d = np.abs(Y - yt)
            along = np.clip(side * X, 0.0, None)
            trib = river + 0.08 * along + 0.7 * tan30 * d               # a V valley climbing away from the trunk
            h = np.where(side * X > 300.0, np.minimum(h, np.maximum(trib, river + tan30 * 300.0)), h)
    h = np.minimum(h, 2600.0) + 2.0 * T.random_field((n, n), 0, 1, 3, smooth=2)
    return lv, h.astype(F32)


def box_sections(h, lv, ys=(-1500.0, -1000.0, 1000.0, 1500.0), half=1500.0):
    """Sections across the synthetic trunk (it runs north along x = 0) at the given y: per section the floor's width
    (within 10 m of its lowest point), the wall's height 250 m out from the floor's edge (the lower of the two
    sides) and the share of the walls' height (floor to lip: the first point past the steepest where the slope
    falls under 30 degrees) that stands at 60 degrees or more."""
    X, Y = lv.xy()
    xs = X[0]
    out = []
    for y in ys:
        j = int(np.argmin(np.abs(Y[:, 0] - y)))
        sel = np.abs(xs) <= half
        x, z = xs[sel], np.asarray(h, np.float64)[j, sel]
        k0 = int(np.argmin(z))
        zf = float(z[k0])
        lo, hi = k0, k0
        while lo > 0 and z[lo - 1] <= zf + 10.0:
            lo -= 1
        while hi < len(z) - 1 and z[hi + 1] <= zf + 10.0:
            hi += 1
        rise, steep = [], []
        for side, e in ((-1, lo), (1, hi)):
            idx = np.arange(e, -1, -1) if side < 0 else np.arange(e, len(z))
            d = np.abs(x[idx] - x[e])
            w = z[idx] - zf
            rise.append(float(np.interp(250.0, d, w)))
            sl = np.degrees(np.arctan(np.gradient(w, d + 1e-9)))
            km = int(np.argmax(sl))
            after = np.nonzero(sl[km:] < 30.0)[0]
            ks = km + int(after[0]) if after.size else len(w) - 1
            dz = np.diff(w[:ks + 1])
            steep.append(float(dz[sl[1:ks + 1] >= 60.0].sum() / max(w[ks], 1e-6)))
        out.append(dict(y=y, floor_m=float(x[hi] - x[lo]), rise_250_m=min(rise), steep=min(steep)))
    return out


def test_u_fit():
    from eidoblend.terrain.recipes import alpine_valley as AV
    # 15.6 m cells: a cliff of 600 m at 80 degrees runs 100-150 m, which the coarsest level's 31 m cells sample in
    # four (the box reads as 60-70 degree walls there, its edges smoothed by the slope estimate itself)
    lv, h = synthetic_valley(n=512, cell=15.625, bench=600.0)
    before = FA.alpine_valley(np.asarray(h, np.float64), lv.cell)
    fields = Fields(lv, {'h': h.copy(), 'bed': h.copy()})
    ctx = FL.StageContext(plan=[lv], index=0, level=lv, prepass=None, fresh=False, role='grow',
                          pins=FL.edge_pins(lv.n, h), shared={}, seed=1, base_elevation_m=0.0, device=GPU,
                          log=lambda m: print(m, flush=True))
    # alpine_valley's glacial stage as the recipe resolves it (its cross-section, overdeepening, shoulder cut, head
    # taper), the trough 600 m deep in this 2.4 km range, the whole valley glaciated
    _, stages = AV.ALPINE_VALLEY.resolve({})
    params = dict([s for s in stages if s.op == 'glacial'][0].params, ela_m=600.0, trough_depth_m=600.0,
                  cirques=False, channel_area_m2=1.0e6)
    rec = G.carve_level(fields, lv, params, 1, ctx, GPU)
    after = FA.alpine_valley(np.asarray(fields['h'], np.float64), lv.cell)
    np.savez_compressed(os.path.join(OUT, 'synthetic_valley.npz'), before=h, after=np.asarray(fields['h'], F32),
                        cell=lv.cell)
    check('trough on a synthetic valley: the V is no U before the carve (b under 1.5)',
          before.get('u_exponent', 9) < 1.5, f"b {before.get('u_exponent', float('nan')):.2f}")
    secs = box_sections(fields['h'], lv)
    floor = float(np.median([s['floor_m'] for s in secs]))
    rise = float(np.median([s['rise_250_m'] for s in secs]))
    steep = float(np.median([s['steep'] for s in secs]))
    b = after.get('u_exponent', float('nan'))
    check('trough on a synthetic valley: the carved trunk is a box trough (a level floor, walls at 60 degrees or '
          'more over most of their height, 300 m or more within 250 m of the floor)',
          200.0 <= floor <= 1000.0 and rise >= 300.0 and steep >= 0.5,
          f"median floor {floor:.0f} m wide, {rise:.0f} m at 250 m from it, {steep * 100:.0f} % of the walls' height "
          f"at 60 deg or more ({[(round(s['floor_m']), round(s['rise_250_m']), round(s['steep'], 2)) for s in secs]});"
          f" the judge's U exponent {b:.2f} (sections {after.get('u_exponents')}), depth "
          f"{after.get('trough_depth_m', 0):.0f} m; carve {rec.get('seeds')} seeds, {rec.get('streams')} streams, "
          f"{rec.get('seconds')}")
    check('trough on a synthetic valley: tributaries hang >= 100 m', after.get('hanging_step_m', 0) >= 100.0,
          f"largest step {after.get('hanging_step_m', 0):.0f} m, {after.get('hanging_count', 0)} of 100 m or more; "
          f"notches {after.get('notch_heights_m')}")
    tw = float(params['trough_width_m'])
    check(f"trough on a synthetic valley: the trough near its {tw:.0f} m width (half to twice: the judge measures "
          f"to the walls' shoulders)", 0.5 * tw <= after.get('trough_width_m', 0) <= 2.0 * tw,
          f"{after.get('trough_width_m', 0):.0f} m")


# ------------------------------------------------------------------------------------------------- 5. cost ---

def test_cost():
    lv, h = synthetic_valley(n=1024, cell=31.25)
    fields = Fields(lv, {'h': h.copy(), 'bed': h.copy()})
    ctx = FL.StageContext(plan=[lv], index=0, level=lv, prepass=None, fresh=False, role='grow',
                          pins=FL.edge_pins(lv.n, h), shared={}, seed=1, base_elevation_m=0.0, device=GPU,
                          log=lambda m: None)
    params = dict(ela_m=600.0, shoulder_width=1.5, cut=0.6, cut_width=2.0)
    t0 = time.perf_counter()
    rec = G.carve_level(fields, lv, params, 1, ctx, GPU)
    secs = time.perf_counter() - t0
    RESULTS['cost'] = {'ok': True, 'detail': dict(seconds=round(secs, 2), parts=rec.get('seconds'),
                                                  seeds=rec.get('seeds'), jfa_steps=rec.get('jfa_steps'))}
    print(f'[cost] carve 1024^2: {secs:.2f} s {rec.get("seconds")}', flush=True)


def main():
    for fn in (test_parity, test_mass_balance, test_jump_flood_exact, test_u_fit, test_cost):
        try:
            fn()
        except Exception as e:                                         # noqa: BLE001
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'gpu_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(results=RESULTS, failed=FAILED), f, indent=1, default=str)
    print(f"{len(RESULTS) - len(FAILED)}/{len(RESULTS)} passed", flush=True)
    os._exit(1 if FAILED else 0)


main()
