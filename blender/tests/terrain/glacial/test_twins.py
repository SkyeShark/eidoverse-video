"""The glacial package's plain-Python tests (numpy twins, no GPU; each under 5 s):

    python blender/tests/terrain/glacial/test_twins.py

  1. the jump flood's twin against the brute-force lower envelope at 64^2: every cell's nearest seed (distance
     metric) and its trough target (height metric), and the four best streams per cell
  2. the ice discharge on the twin device, iterated to convergence, closes its mass balance (accumulation + inflow
     - realised ablation = outflow) within 1e-6, with and without ice entering at the window's edge
  3. the cross-section prof(rho): continuous at the floor's edge, the lip and the shoulder's edge, never falling
     outward; the judge's U-fit (judge/family._walls) on a section of the recipe's profile lands in the design's
     1.5-2.5 while the lip stands at 70 degrees or more
  4. graded_fill: the fill's top falls down-valley by at least the grade, never lowers a floor, and at each
     glacier's end reaches the river below it
  5. best_donor: every cell's donor drains into it, and it is the largest of them
  6. wall_flutes: the couloir-and-rib pattern runs down the fall line (it changes at least twice as fast across
     the slope as down it), the couloirs a minority of the wall (10-35 %)
Writes blender/tests/terrain/out/glacial/twin_tests.json; exit code 1 on a failure.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import glacial as G  # noqa: E402
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402

OUT = os.path.join(TN, 'out', 'glacial')
RESULTS, FAILED = {}, []
F32 = np.float32


def check(name, cond, detail=None, seconds=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail, 'seconds': seconds}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else '') +
          (f' ({seconds:.2f} s)' if seconds is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


PROF = G.profile_uniforms({'u_exponent': 2.4, 'floor_frac': 0.25, 'floor_rise': 0.06, 'shoulder_width': 1.5,
                           'shoulder_rise': 0.3, 'upper_wall': 1.5})


def seeds(n0, n1, cell, n_streams=8, per=10, seed=3):
    """Random seed cells in streams (each a short random walk), with their trough data: (cand0, seedA, seedB,
    flat indices)."""
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


def test_jump_flood():
    t0 = time.perf_counter()
    dev = FL.device('twin')
    n0 = n1 = 64
    cell = 10.0
    cand0, A, B, idx = seeds(n0, n1, cell)
    for metric, name in ((1, 'distance'), (0, 'trough target')):
        cT, _, _ = G.jump_flood_run(dev, cand0, A, B, cell, PROF, G.jfa_steps(n0, n0), metric)
        cand = dev.read(cT)
        got = G.decode_best(cand, A, B, cell, PROF, metric, slot='all')
        want = G.brute_force(idx, A, B, cell, PROF, metric, per_stream=True)
        tol = 1e-3 * max(1.0, float(np.nanmax(np.abs(np.where(np.isfinite(want), want, 0)))))
        first = np.abs(got[..., 0] - want[..., 0]) <= tol
        four = np.all((np.abs(got - want) <= tol) | (np.isinf(got) & np.isinf(want)), axis=-1)
        check(f'jump flood twin vs brute force, {name}: nearest', first.mean() >= 0.995,
              f'{first.mean() * 100:.2f} % of cells exact (worst {np.max(np.abs(got[..., 0] - want[..., 0])):.3g})')
        check(f'jump flood twin vs brute force, {name}: four best streams', four.mean() >= 0.98,
              f'{four.mean() * 100:.2f} % of cells have all four exact')
    RESULTS['jump flood twin vs brute force, distance: nearest']['seconds'] = round(time.perf_counter() - t0, 2)


def surface(n=96, cell=50.0, seed=5):
    """A filled routing surface: a tilted dome of rough ground (heights 0-2500 m)."""
    rng = np.random.default_rng(seed)
    jj, ii = np.mgrid[0:n, 0:n]
    r = np.hypot(ii - n / 2, jj - n * 0.3) / n
    h = 2500.0 * np.exp(-3.0 * r * r) + 300.0 * T.random_field((n, n), 0, 1, seed, smooth=3)
    h = h + 0.5 * rng.random((n, n))
    filled, _ = HY.fill_depressions(h)
    return HY.routing_surface(filled).astype(F32), cell


def test_mass_balance():
    dev = FL.device('twin')
    surf, cell = surface()
    recv = G.d8_receivers(surf, cell)
    params = {'ela_m': 1500.0}
    b = G.mass_balance(surf, 0.0, params)
    n = surf.shape[0]
    rng = np.random.default_rng(1)
    q_in = np.zeros((n, n), F32)
    q_in[0, rng.integers(0, n, 6)] = rng.uniform(1e5, 1e6, 6).astype(F32)
    for name, qi in (('no inflow', None), ('inflow at the edge', q_in)):
        t0 = time.perf_counter()
        Q, it = G.ice_flux_converge(dev, surf, b, cell, recv, 0.0, Q_in=qi, params=params, check=32)
        bud = G.flux_budget(Q, b, recv, cell, params, Q_in=qi)
        check(f'ice flux mass balance closes ({name})', abs(bud['rel_residual']) <= 1e-6 and bud['outflow'] > 0,
              f"accumulation {bud['accumulation']:.4g} + inflow {bud['inflow']:.4g} - ablation {bud['ablation']:.4g}"
              f" = outflow {bud['outflow']:.4g} (residual {bud['rel_residual']:.2e}, {it} iterations, glaciated "
              f"{(Q > 0).mean() * 100:.1f} %)", round(time.perf_counter() - t0, 2))


def test_profile():
    t0 = time.perf_counter()
    u = PROF
    eps = 1e-6
    ff, sw = u['uFloorFrac'], u['uShW']
    jumps = [abs(float(G.prof(np.array([x + eps]), u, np.float64)[0] - G.prof(np.array([x - eps]), u, np.float64)[0]))
             for x in (ff, 1.0, 1.0 + sw)]
    rho = np.linspace(0, 6, 6001)
    p = G.prof(rho, u, np.float64)
    check('profile continuous at the floor edge, the lip and the shoulder edge', max(jumps) < 1e-4,
          f'jumps {[round(j, 6) for j in jumps]}')
    check('profile never falls outward', bool(np.all(np.diff(p) >= -1e-12)))
    from judge import family as FA
    W = H = 600.0
    t = np.arange(-3500, 3500.1, 4.0)
    rr = np.abs(t) / W
    z = np.maximum(H * G.prof(rr, u, np.float64), G.fillz(rr, 0.0, H, u, np.float64))
    z = np.minimum(z, 700.0 + math.tan(math.radians(35.0)) * np.abs(t))
    bs = [w[0] for w in FA._walls(t, z)]
    lip = math.degrees(math.atan(u['uB'] * H / ((1 - ff) * W)))
    check('the judge reads the profile as a U (b 1.5-2.5) with walls to 70 degrees at the lip',
          all(1.5 <= b <= 2.5 for b in bs) and lip >= 70.0, f'b {[round(b, 2) for b in bs]}, lip {lip:.1f} deg',
          round(time.perf_counter() - t0, 2))


def test_graded_fill():
    t0 = time.perf_counter()
    surf, cell = surface(n=80, cell=40.0, seed=9)
    recv = G.d8_receivers(surf, cell)
    A, _ = G.ice_flux_converge(FL.device('twin'), surf, np.ones_like(surf), cell, recv, 0.0,
                               params={'ice_width_m': 0.0}, check=32)
    mask = A >= 30 * cell * cell
    st = G.streams(mask, recv, A)
    idx = st['idx']
    jj, ii = np.divmod(idx, surf.shape[1])
    x, y = (ii + 0.5) * cell, (jj + 0.5) * cell
    rng = np.random.default_rng(2)
    zc = surf.ravel()[idx].astype(np.float64)
    zf = zc - rng.uniform(0, 120, idx.size)                                       # an uneven, overdeepened floor
    grade = 0.012
    fill = G.graded_fill(zf, np.zeros(idx.size), x, y, st, grade, outlet=zc)
    top = zf + fill
    rc = st['rcv']
    has = rc >= 0
    L = np.hypot(x - x[np.maximum(rc, 0)], y - y[np.maximum(rc, 0)])
    drop = top - top[np.maximum(rc, 0)]
    ok = np.all(drop[has] >= grade * L[has] - 1e-6)
    ends = ~has
    check('graded fill falls down-valley by at least the grade, never lowers a floor, and meets the river at '
          'each glacier\'s end', bool(ok) and bool(np.all(fill >= 0)) and bool(np.all(top[ends] >= zc[ends] - 1e-9)),
          f'{idx.size} seeds, {int(has.sum())} links, {int(ends.sum())} ends, fill max {fill.max():.1f} m',
          round(time.perf_counter() - t0, 2))


def test_best_donor():
    t0 = time.perf_counter()
    surf, cell = surface(n=64, cell=40.0, seed=4)
    recv = G.d8_receivers(surf, cell)
    A, _ = G.ice_flux_converge(FL.device('twin'), surf, np.ones_like(surf), cell, recv, 0.0,
                               params={'ice_width_m': 0.0}, check=32)
    up = G.best_donor(recv, A)
    n0, n1 = surf.shape
    r = recv.ravel().astype(np.int64)
    a = A.ravel()
    q = np.arange(n0 * n1)
    tgt = np.full(n0 * n1, -1, np.int64)                       # each cell's receiver cell (-1 none)
    for k in range(8):
        sel = r == k
        tgt[sel] = G._flat_neighbour(q[sel], k, n0, n1)
    has = tgt >= 0
    amax = np.full(n0 * n1, -1.0)                              # the largest donor's area at each receiver
    np.maximum.at(amax, tgt[has], a[q[has]])
    d = up
    drains = np.where(d >= 0, tgt[np.maximum(d, 0)] == q, amax < 0)
    largest = np.where(d >= 0, a[np.maximum(d, 0)] >= amax, True)
    bad = int((~drains | ~largest).sum())
    check('best_donor: each cell\'s donor drains into it and is its largest', bad == 0, f'{bad} bad of {n0 * n1}',
          round(time.perf_counter() - t0, 2))


def test_flutes():
    t0 = time.perf_counter()
    from eidoblend.terrain.core import levels as L
    lv = L.plan_levels(1000.0, 128, (0.0, 0.0), None, None, None)[0]
    X, Y = lv.xy()
    h = 0.8 * X + 0.1 * Y + 50.0 * np.sin(Y / 200.0)              # a slope falling west, its contours wavy
    f = G.wall_flutes(h, lv, {}, 1)
    across = float(np.abs(np.diff(f, axis=0)).mean())             # along y: across the fall line
    along = float(np.abs(np.diff(f, axis=1)).mean())              # along x: down the fall line
    weak = float((f < 0).mean())
    check('wall flutes run down the fall line, couloirs a minority of the wall',
          across >= 2.0 * along and 0.1 <= weak <= 0.35,
          f'change across / along the fall line {across / max(along, 1e-12):.1f}, couloirs {weak * 100:.0f} %',
          round(time.perf_counter() - t0, 2))


def main():
    for fn in (test_jump_flood, test_mass_balance, test_profile, test_graded_fill, test_best_donor, test_flutes):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception as e:                                         # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
        took = time.perf_counter() - t0
        check(f'{fn.__name__} under 5 s', took < 5.0, f'{took:.2f} s')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'twin_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(results=RESULTS, failed=FAILED), f, indent=1)
    print(f"{len(RESULTS) - len(FAILED)}/{len(RESULTS)} passed", flush=True)
    sys.exit(1 if FAILED else 0)


main()
