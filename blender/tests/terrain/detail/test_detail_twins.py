"""The detail package's plain-Python tests (numpy twins, no GPU; each under 5 s):

    python -I blender/tests/terrain/detail/test_detail_twins.py      (or in Blender, the same file)

  1. the pipe model conserves water plus sediment (twins, 64^2, 400 steps): closed edges and periodic ones; ground +
     suspended sediment against the material moved, and the water budget step by step
  2. the thermal pass: mass conserved; loose debris relaxes to its repose angle; cohesive ground under an
     out-of-reach threshold never moves; a rock step steeper than its threshold fails back to it
  3. rock breakup: world space (two overlapping windows agree), seeds, the relief bands telescope across the levels
     (each feature's relief applied once), joint lines run along their strike and cover about width / spacing
  4. the gully octave's stripes run down the flow
  5. planation: residual knobs on a plain at the datum
  6. the hydraulic op on a synthetic hillside above a plain: the wear gathers into rills, a fan settles at the foot,
     the border band ends exactly on the start surface, the water's wet field follows the channels
  7. unknown parameters name the nearest
Writes blender/tests/terrain/out/detail/twin_tests.json; exit code 1 on a failure.
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
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core import grid as GR  # noqa: E402
from eidoblend.terrain.core.levels import Level  # noqa: E402
from eidoblend.terrain.solvers import hydraulic as HY  # noqa: E402
from eidoblend.terrain.solvers import detail as DT  # noqa: E402

F = np.float32
RESULTS = {}
FAILED = []


def check(name, cond, detail=None, seconds=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail, 'seconds': seconds}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else '')
          + (f' ({seconds:.2f} s)' if seconds is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def model_inputs(b, erod=0.5):
    shape = b.shape
    src = T.rgba(np.ones(shape, F), None, np.full(shape, erod, F))
    par = T.rgba(np.full(shape, HY.BIG_TAN, F), np.full(shape, 0.7, F))
    return src, par, np.zeros(shape + (4,), F)


def hillside(n, seed=3, base=500.0):
    """Cell units: a slope rising north over the southern 60 % with bumps, a flat plain below it."""
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    rise = np.clip(jj - 0.35 * n, 0.0, None) * 0.55
    b = base + rise + 1.5 * np.sin(ii / n * 7.0) * (rise > 0) + T.random_field((n, n), 0.0, 0.6, seed, smooth=2)
    return b.astype(F)


# --------------------------------------------------------------------------------------------- 1. conservation ---

def test_conservation():
    n, steps = 64, 400
    p = HY.defaults({'rain_cover': 1.0, 'roughness': 0.0})
    for label, mode in (('closed', T.BOUND_OPEN), ('periodic', T.BOUND_PERIODIC)):
        t0 = time.perf_counter()
        b = hillside(n) if mode == T.BOUND_OPEN else (500.0 + T.random_field((n, n), 0.0, 30.0, 5, smooth=3)).astype(F)
        src, par, pin = model_inputs(b)
        rec = []
        st, ta = HY.run_numpy(b, b - 0.3, src, par, pin, p, seed=7, mode=mode, outflow=False, steps=steps, record=rec)
        gross = float(np.abs(st[..., 0]).astype(np.float64).sum())
        net = max(abs(r[2]) for r in rec)
        W, worst = 0.0, 0.0
        rain = float(F(p['rain']) * F(p['dt'])) * n * n
        keep = float(F(max(F(1) - F(p['Ke']) * F(p['dt']), F(0))))
        for r in rec:
            W = (W + rain) * keep
            worst = max(worst, abs(r[1] - W) / W)
        sec = time.perf_counter() - t0
        check(f'twins conserve ground + sediment, {label} edges ({steps} steps, {n}^2)', net / max(gross, 1e-9) < 1e-6,
              f'net {net:.2e} cells^3 against {gross:.1f} moved ({net / max(gross, 1e-9):.1e})', sec)
        check(f'twins: the water budget, {label} edges', worst < 1e-5, f'worst relative error {worst:.1e}')


# ----------------------------------------------------------------------------------------------- 2. thermal ---

def thermal_run(b0, bed, sc, rep, iters, mode=T.BOUND_OPEN):
    return DT.relax(b0, bed, sc, rep, iters, 0.06, backend='numpy', mode=mode)


def test_thermal():
    t0 = time.perf_counter()
    n = 48
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    base = np.full((n, n), 300.0, F)
    # a cone of loose debris (8 cells high, 2:1) on a flat cohesive base
    cone = np.maximum(8.0 - 0.5 * np.hypot(ii - 24, jj - 24), 0.0) * 2.0
    b0 = (base + cone).astype(F)
    rep = math.tan(math.radians(35.0))
    dl, bed_rel, net = thermal_run(b0, base, np.full((n, n), 1e3, F), rep, 1500)
    h = b0.astype(np.float64) + dl
    slopes = []
    for k in range(8):
        hq, ok = T.neighbour(h, k)
        loose = (h - (b0 + bed_rel)) > 0.05
        slopes.append(np.where(ok & loose, (h - hq) / T.LEN[k], 0.0))
    s = np.degrees(np.arctan(np.max(slopes, axis=0)))
    on = s > 1.0
    p99, smax = float(np.percentile(s[on], 99)), float(s.max())
    mass = float(dl.astype(np.float64).sum() + 0.0)
    check('thermal: a debris cone relaxes to its repose angle', p99 <= 36.0 and smax <= 36.0,
          f'loose ground steepest-pair slope p99 {p99:.1f} deg, max {smax:.1f} deg after 1500 passes (repose 35; '
          f'it closes in geometrically: 37.2 at 600, 35.0 at 3000)')
    check('thermal: the debris is conserved', abs(mass) < 1e-4 * float(np.abs(dl).sum()),
          f'net {mass:.2e} against {float(np.abs(dl).sum()):.1f} moved')
    # cohesive ground under an out-of-reach threshold does not move, however steep
    wall = (300.0 + np.where(ii > 24, 40.0, 0.0)).astype(F)
    dl2, _b, _n = thermal_run(wall, wall, np.full((n, n), 1e3, F), rep, 50)
    check('thermal: cohesive ground with no reachable threshold stays put', float(np.abs(dl2).max()) == 0.0,
          f'max change {float(np.abs(dl2).max()):.2e}')
    # a rock step steeper than its threshold fails back to it, and the debris gathers below
    sc = math.tan(math.radians(60.0))
    step = (300.0 + np.where(ii > 24, 12.0, 0.0)).astype(F)
    dl3, bed3, net3 = thermal_run(step, step, np.full((n, n), sc, F), rep, 1500)
    h3 = step + dl3.astype(np.float64)
    rock = (h3 - (step + bed3)) < 0.05                                 # cohesive ground at the surface
    sl = np.degrees(np.arctan(np.abs(np.diff(h3[n // 2]))))
    rk = rock[n // 2][1:] & rock[n // 2][:-1]
    check('thermal: a rock step fails back to its threshold, talus below',
          sl[rk].max() <= 61.0 and net3.max() > 1.0,
          f'steepest rock pair {sl[rk].max():.1f} deg (threshold 60), talus up to {net3.max():.2f} cells',
          time.perf_counter() - t0)


# ------------------------------------------------------------------------------------------------ 3. breakup ---

def test_breakup():
    t0 = time.perf_counter()
    p = DT._params(DT.BREAKUP, None, 'breakup')
    cell = 1.0
    h = T.random_field((96, 96), 0.0, 200.0, 2, smooth=3)
    a = Level(0, 'hero', 1000.0, -3000.0, 96 * cell, cell, 96)
    b = Level(0, 'hero', 1000.0 + 17 * cell, -3000.0 + 5 * cell, 96 * cell, cell, 96)
    Ra, ka, sa, Da = DT.strength(p, a, h, 3, backend='numpy')
    hb = np.zeros_like(h)
    hb[:91, :79] = h[5:, 17:]
    Rb, kb, sb, Db = DT.strength(p, b, hb, 3, backend='numpy')
    err = float(np.abs(Ra[5:, 17:] - Rb[:91, :79]).max())
    check('breakup: two overlapping windows agree (world space)', err < 1e-5, f'max |dR| {err:.1e}')
    Rc = DT.strength(p, a, h, 4, backend='numpy')[0]
    check('breakup: another seed gives other rock', float(np.abs(Rc - Ra).mean()) > 0.1,
          f'mean |dR| {float(np.abs(Rc - Ra).mean()):.2f}')
    check('breakup: strength about unit-scaled (std 0.25-0.6), kfac positive',
          0.25 <= float(Ra.std()) <= 0.6 and float(ka.min()) > 0.0,
          f'R std {float(Ra.std()):.2f}, kfac {float(ka.min()):.2f}..{float(ka.max()):.2f}')
    # the relief bands telescope: summed over hero levels 4, 2, 1, 0.5 m a feature gets r(size/0.5) - r(size/8)
    worst = 0.0
    for size in list(p['scales_m']) + [js['width_m'] for js in p['joints']] + [0.9, 2.7, 33.0]:
        tot = sum(DT.band(size, c) for c in (4.0, 2.0, 1.0, 0.5))
        want = DT.resolvable(size, 0.5) - DT.resolvable(size, 8.0)
        worst = max(worst, abs(tot - want))
    check('breakup: each feature\'s relief is added once across the levels (bands telescope)', worst < 1e-12,
          f'worst {worst:.1e}')
    # joint lines: along the strike, covering about width / spacing
    pj = DT._params(DT.BREAKUP, {'scales_m': (50.0,), 'scale_amps': (0.0,), 'bedding': None,
                                 'joints': ({'strike_deg': 30.0, 'spacing_m': 12.0, 'width_m': 2.0, 'stretch': 6.0,
                                             'strength': 1.0, 'depth_m': 1.0},)}, 'breakup')
    lv = Level(0, 'hero', 0.0, 0.0, 128 * 0.5, 0.5, 128)
    Rj = DT.strength(pj, lv, np.zeros((128, 128)), 9, backend='numpy')[0].astype(np.float64)
    on = -Rj > 0.25
    gy, gx = np.gradient(-Rj)
    w = np.hypot(gx, gy)
    ang = (np.degrees(np.arctan2(gy, gx)) - 30.0) % 180.0          # gradient direction against the strike
    across = float(w[(np.abs(ang - 90.0) < 30.0)].sum() / max(w.sum(), 1e-12))
    check('breakup: joint lines run along their strike', across > 0.6,
          f'{across * 100:.0f} % of the line field\'s gradient is across the strike')
    frac = float(on.mean())
    check('breakup: joint lines cover about width / spacing of the ground', 0.05 <= frac <= 0.35,
          f'{frac * 100:.1f} % (2 m lines every 12 m, segments on about half their length: about 8-17 %)',
          time.perf_counter() - t0)
    RESULTS['joint_line_area'] = frac


# -------------------------------------------------------------------------------------------------- 4. gully ---

def test_gully():
    t0 = time.perf_counter()
    n, cell = 128, 1.0
    lv = Level(0, 'hero', 200.0, 400.0, n * cell, cell, n)
    X, Y = lv.xy()
    h = 0.4 * (X - X.min())                                         # a plane rising east: the flow runs west
    g, mask = DT.gully_relief(lv, h, DT._params(DT.GULLY, {'octaves': 1}, 'gully'), seed=1)
    gy, gx = np.gradient(g)
    ratio = float(np.abs(gy).mean() / max(np.abs(gx).mean(), 1e-12))
    check('gully: the stripes run down the flow (relief changes across it, not along it)', ratio > 2.0,
          f'mean |d/dy| / |d/dx| = {ratio:.1f}; mask {mask.mean():.2f} on a 21.8-degree plane',
          time.perf_counter() - t0)


# ---------------------------------------------------------------------------------------------- 5. planation ---

def test_planation():
    t0 = time.perf_counter()
    n, cell = 128, 20.0
    lv = Level(0, 'main', -1280.0, -1280.0, n * cell, cell, n)
    h = T.random_field((n, n), 0.0, 300.0, 4, smooth=3).astype(np.float64) + 100.0
    f = {'h': h.copy()}
    DT.op_planation(f, lv, {'datum_m': 150.0, 'tilt_deg': 0.0}, seed=2, log=lambda m: None, backend='numpy')
    flat = np.abs(f['h'] - 150.0) < 6.0
    hi = f['h'] > 160.0
    check('planation: most ground planed to the datum, residual knobs standing above it',
          0.35 <= float(flat.mean()) <= 0.95 and 0.02 <= float(hi.mean()) <= 0.5,
          f'{flat.mean() * 100:.0f} % within 6 m of the datum, {hi.mean() * 100:.0f} % above it',
          time.perf_counter() - t0)


# ---------------------------------------------------------------------------------------------- 6. the op ---

def test_op_hydraulic():
    t0 = time.perf_counter()
    n, cell = 96, 1.0
    lv = Level(1, 'hero', 3000.0, -800.0, n * cell, cell, n, parent=0)        # a hero level: pinned band
    h = hillside(n, seed=5, base=0.0).astype(np.float64) * cell + 1200.0
    f = {'h': h.copy()}
    HY.op_hydraulic(f, lv, {'steps': 900}, seed=3, backend='numpy', log=lambda m: None)
    wear = f['wear'].ravel()
    top = np.sort(wear)[::-1]
    share = float(top[:int(0.05 * top.size)].sum() / max(top.sum(), 1e-12))
    check('hydraulic op: the wear gathers into rills (5 % of the cells hold over half of it)', share > 0.5,
          f'{share * 100:.0f} %; deepest {wear.max():.2f} m')
    jj = np.mgrid[0:n, 0:n][0]
    foot = (jj > 0.2 * n) & (jj < 0.4 * n)
    dep_foot = float(f['deposit'][foot].sum())
    dep_all = float(f['deposit'].sum())
    check('hydraulic op: sediment settles at the foot of the slope (a fan)', dep_foot > 0.3 * dep_all and dep_foot > 0,
          f'{dep_foot:.1f} of {dep_all:.1f} m^3-per-cell deposited in the foot band')
    edge = np.concatenate([f['h'][0], f['h'][-1], f['h'][:, 0], f['h'][:, -1]])
    edge0 = np.concatenate([h[0], h[-1], h[:, 0], h[:, -1]])
    check('hydraulic op: the border band ends exactly on the start surface', float(np.abs(edge - edge0).max()) < 1e-9,
          f'max |dh| on the edge {float(np.abs(edge - edge0).max()):.1e} m')
    wet = f['wet']
    slope = (jj > 0.45 * n) & (GR.border_ramp(n, 16) == 0)
    rills = slope & (f['wear'] >= np.percentile(f['wear'][slope], 95))
    ridges = slope & (f['wear'] <= np.percentile(f['wear'][slope], 50))
    ratio = float(wet[rills].mean() / max(wet[ridges].mean(), 1e-12))
    check('hydraulic op: the wet field follows the rills', wet.min() >= 0.0 and ratio > 2.0,
          f'wet in the rills / between them = {ratio:.1f}', time.perf_counter() - t0)


# ------------------------------------------------------------------------------------------------ 8. anchor ---

def test_anchor():
    """The anchor (on a 1 m hero level three levels under an 8 m main tile: scale 12 m) keeps a rill two cells wide and
    removes a bump 40 m across (the levels above hold that), and the change's 8 m-pixel means shrink to a fraction."""
    t0 = time.perf_counter()
    n = 128
    lv = Level(5, 'hero', 0.0, 0.0, n * 1.0, 1.0, n, parent=4, depth=-3)       # 1 m cells, main cell 8 m
    scale = HY.anchor_scale_m(lv) / lv.cell
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    rill = -0.5 * np.exp(-((ii - 40.3) / 0.8) ** 2)                 # 1-2 cells wide
    broad = 2.0 * np.exp(-(((ii - 90.0) / 18.0) ** 2 + ((jj - 64.0) / 18.0) ** 2))   # 40 m across
    a = HY.anchor(rill + broad, scale)
    kept_rill = float(-a[20:108, 40].mean() / max(-rill[20:108, 40].mean(), 1e-9))
    kept_broad = float(np.abs(a[54:74, 80:100]).mean() / np.abs(broad[54:74, 80:100]).mean())
    px_before = np.abs(GR.box_down(rill + broad, 8)).max()
    px_after = np.abs(GR.box_down(a, 8)).max()
    check('anchor: rills stay, broad change goes (scale 12 m: 1.5 main pixels of 8 m)',
          kept_rill > 0.75 and kept_broad < 0.25 and scale == 12.0,
          f'the 2-cell rill keeps {kept_rill * 100:.0f} % of its depth, the 40 m bump {kept_broad * 100:.1f} %')
    check('anchor: the change at the main pixel shrinks', px_after <= 0.25 * px_before,
          f'largest 8 m pixel mean {px_after:.3f} m, from {px_before:.3f} m', time.perf_counter() - t0)


# ------------------------------------------------------------------------------------------------ 7. params ---

def test_params():
    msgs = []
    for fn, args in ((HY.defaults, ({'rougness': 1},)), (DT._params, (DT.BREAKUP, {'spred_deg': 3}, 'breakup'))):
        try:
            fn(*args)
            msgs.append(None)
        except KeyError as e:
            msgs.append(str(e))
    check('unknown parameters name the nearest', all(m and ('roughness' in m or 'spread_deg' in m) for m in msgs),
          msgs)


def main():
    for t in (test_conservation, test_thermal, test_breakup, test_gully, test_planation, test_op_hydraulic,
              test_anchor, test_params):
        try:
            t()
        except Exception as e:                                   # noqa: BLE001
            traceback.print_exc()
            check(t.__name__, False, f'{type(e).__name__}: {e}')
    with open(os.path.join(OUT, 'twin_tests.json'), 'w') as f:
        json.dump({'failed': FAILED, 'results': RESULTS}, f, indent=1, default=str)
    print(f'[detail twin tests] {sum(1 for r in RESULTS.values() if isinstance(r, dict) and r.get("ok"))} passed, '
          f'{len(FAILED)} failed: {FAILED}', flush=True)
    if FAILED:
        sys.exit(1)


main()
