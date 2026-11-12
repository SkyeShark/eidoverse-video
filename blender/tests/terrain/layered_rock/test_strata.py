"""The layered-rock package's plain-Python tests (numpy twins, no GPU; design section 11 row 10):

    python blender/tests/terrain/layered_rock/test_strata.py

  1. the composite threshold on a synthetic column gives each layer its own angle in a 1D profile: a 165 m wall in
     a five-layer column (weak 30 / strong 75 / weak 35 / strong 80 / weak 40 degrees) at 1 m cells, standing 8
     degrees steeper than the column in every layer, its foot held at the base, relaxed by strata_threshold + the
     exchange with the failed rock carried off; every layer's slope, away from its contacts, within 2 degrees of its
     own angle (rock only), and the run through each layer within 1.5 cells of thickness / tan(theta); and the
     column's own wall is exactly its stability limit (no excess at its angles, excess 2 degrees steeper)
  2. debris at repose: a cliff of strong rock (80 degrees) over a bench, its foot NOT held: the failed rock gathers
     at the foot as talus standing at the repose angle (34 +- 2.5 degrees) while the cliff above stands
  3. the tables: K(zs) and tan(zs) equal the bed holding zs everywhere 0.5 m or more from a contact, R(zs) equals the
     exact integral of dz / tan(theta) to 1e-6 m, R grows monotonically and continues linearly past the column
  4. the K(z) lookup of route_incise's twin: one route_incise step with the column and with K pre-multiplied per cell
     by col.k_at(h - zoff) and no column gives the same heights (the twin reads the column as the kernel does)
  5. meander geometry: Kinoshita courses at sinuosity 1.5, 2.5 and 3.5 (no variation) measure that sinuosity within
     2 %, their down-valley bend wavelength within 6 % of wavelength / sinuosity, and every course (also with the
     default variation) keeps its necks wider than four channel widths; a course passes through its point and
     runs along its azimuth; the smoothed walk has no loops
  6. weathering (strata_weather): a strong cap over a weak slope over a strong bench; the cap retreats at least 40 m,
     the bench and the cap's top stay flat (0.5 m), the cap's wall stays a cliff (70+ degrees), the weak slope a slope
Writes blender/tests/terrain/out/layered_rock/strata_tests.json; exit code 1 on a failure.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'layered_rock'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import rivers as RV  # noqa: E402
from eidoblend.terrain.solvers import strata as S  # noqa: E402

F32 = np.float32
RESULTS = {}
FAILED = []


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


TEST_COLUMN = [(40.0, 2.0, 30.0, 'shale', 'weak 30'), (30.0, 0.3, 75.0, 'sandstone', 'strong 75'),
               (40.0, 1.5, 35.0, 'shale', 'weak 35'), (25.0, 0.2, 80.0, 'sandstone', 'strong 80'),
               (30.0, 1.0, 40.0, 'shale', 'weak 40')]


def profile_run(col, h, pin_w, pin_h, cell, carry_off=True, repose_deg=34.0, max_iter=60000, tol=1e-5, rate=0.3):
    """Relax a (1, W) profile with the composite threshold on the twin device (strata_threshold, then threshold.glsl's
    exchange) until no cell moves (max |dh| over 100 iterations under 100 tol metres). carry_off: each iteration's
    net gains are carried off (the failed rock leaves, as the river at a wall's foot takes it in the erosion runs),
    so the wall relaxes in place to the composite limit; otherwise the debris stays (mass conserved). A 1-row field
    has only the west and east pairs, so the exchange is stable up to rate 0.375."""
    dev = FL.device('twin')
    z = np.zeros_like(h)
    fields = {'h': h, 'bed': h.copy()}
    pins = dict(pin_w=pin_w, pin_h=pin_h, A_in=z, qs_in=z)
    zoff = np.zeros_like(h)
    run = S.StrataRun(dev, cell, fields, T.rgba(z, z, z + 1.0, z), pins, col, zoff, None, 2,
                      math.tan(math.radians(repose_deg)))
    prev = dev.read(run.S.src)[..., 0].copy()
    it = 0
    for it in range(1, max_iter + 1):
        before = dev.read(run.S.src) if carry_off else None
        run.threshold(1, rate)
        if carry_off:
            st = dev.read(run.S.src)
            st[..., 0] = np.minimum(st[..., 0], before[..., 0])
            run.S.src = dev.texture(st)
            m = dev.read(run.M.src)
            m[..., 2:] = 0.0
            run.M.src = dev.texture(m)
        if it % 100 == 0:
            cur = dev.read(run.S.src)[..., 0]
            if float(np.max(np.abs(cur - prev))) < tol * 100:
                prev = cur
                break
            prev = cur.copy()
    st = dev.read(run.S.src)
    mk = dev.read(run.M.src)
    return st[0, :, 0].astype(np.float64), mk[0], it


def excess(col, h, cell, loose=None, repose_deg=34.0):
    """strata_threshold's twin on a (1, W) or (H, W) field (zoff 0)."""
    z = np.zeros_like(h, dtype=F32)
    mk = T.rgba(z, z, z, z if loose is None else np.asarray(loose, F32))
    out = T.run_twin('strata_threshold', {'st': np.asarray(h, F32), 'zoff': z, 'mk': mk, 'rtab': col.table_texture()},
                     {'uDx': cell, 'uRZ0': col.z0, 'uRDz': col.dz, 'uRN': len(col.R),
                      'uRepose': math.tan(math.radians(repose_deg)), 'uBound': T.BOUND_PINNED})
    return out['outP'][..., 0]


def relax_outflow(col, h, pin_w, pin_h, cell, rate=0.3, max_iter=40000, tol=1e-6):
    """The composite threshold with the failed rock leaving as it falls: every cell loses its share of the isotropic
    exchange (threshold.glsl's formula, rate WISO (h - h_k) (phi + phi_k) / 2 to each lower neighbour) and its inflow
    is carried off, so an over-steep wall fails in place down to the composite limit (in the erosion runs the river
    at the wall's foot takes the debris; the exchange alone, mass conserving, carries it down cell by cell)."""
    h = np.asarray(h, F32).copy()
    it = 0
    for it in range(1, max_iter + 1):
        phi = excess(col, h, cell)
        out = np.zeros_like(h)
        for k in range(8):
            hq, ok = T.neighbour(h, k, T.BOUND_PINNED)
            pq, _ = T.neighbour(phi, k, T.BOUND_PINNED)
            x = F32(rate) * T.WISO[k] * (h - hq) * (F32(0.5) * (phi + pq))
            out = out + np.where(ok & (h > hq), np.maximum(x, F32(0)), F32(0))
        hn = T.pin_apply(h - out, pin_w, pin_h).astype(F32)
        moved = float(np.max(np.abs(hn - h)))
        h = hn
        if moved < tol:
            break
    return h[0].astype(np.float64), it


def analytic_profile(col, x, x_foot, cell, steeper_deg=0.0):
    """The column's equilibrium wall x(z) = x_foot - R(z) (each layer at its own angle, or steeper_deg steeper),
    sampled as h(x) on the cells."""
    zz = np.linspace(0.0, col.top_m, 20001)
    if steeper_deg:
        ang = np.degrees(np.arctan(col.tan_at(zz))) + steeper_deg
        inv = 1.0 / np.tan(np.radians(np.clip(ang, 1.0, 89.5)))
        R = np.concatenate([[0.0], np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(zz))])
    else:
        R = col.run_at(zz) - col.run_at(0.0)
    xr = x_foot - R                                       # the wall's position at each height
    return np.interp(x * cell, xr[::-1], zz[::-1], left=col.top_m, right=0.0)


def test_profile():
    col = S.column(TEST_COLUMN)
    cell = 1.0
    W = 420
    x = np.arange(W)
    step = 330
    # the stability limit: the analytic wall x = R(z) stands; 2 degrees steeper in every layer fails in every layer
    stat = []
    ok_static = True
    for dg in (-2.0, 0.0, 2.0):
        hp = analytic_profile(col, x, step, cell, dg)[None, :]
        phi = excess(col, hp, cell)[0]
        zc = hp[0]
        per = []
        for d in col.layers:
            inner = (zc > d['base_m'] + 2.0) & (zc < d['top_m'] - 2.0) & (x < step)
            per.append(round(float(phi[inner].max()) if inner.any() else -1.0, 4))
        good = all(v > 0.01 for v in per) if dg > 0 else all(v <= 0.01 for v in per)
        ok_static = ok_static and good
        stat.append(dict(steeper_deg=dg, max_excess_per_layer=per, ok=good))
    check('composite threshold: the column\'s own wall is exactly its stability limit', ok_static, stat)
    # the start: the wall 8 degrees steeper than the column in every layer (each layer over its threshold, so each
    # must fail back to its own angle; a vertical step needed 40,000 iterations and 23 s for the same answer)
    h = analytic_profile(col, x, step, cell, 8.0).astype(F32)[None, :]
    pin_w = (x >= step).astype(F32)[None, :]
    pin_h = np.zeros_like(h)
    t0 = time.time()
    # every layer is at its angle after 2,000 iterations (1.7 s); a 1e-6 m tolerance never triggered (float32
    # jitter), so the run went to 40,000
    prof, iters = relax_outflow(col, h, pin_w, pin_h, cell, max_iter=4000, tol=1e-4)
    secs = time.time() - t0
    sl = np.degrees(np.arctan(np.abs(np.diff(prof)) / cell))         # the slope between cells i and i + 1
    zmid = 0.5 * (prof[1:] + prof[:-1])
    rows = []
    ok = True
    for d in col.layers:
        b, t = d['base_m'], d['top_m']
        inner = (zmid > b + 2.0) & (zmid < t - 2.0) & (np.arange(W - 1) < step - 1)
        if inner.sum() < 2:
            rows.append(dict(layer=d['name'], cells=int(inner.sum()), ok=False))
            ok = False
            continue
        med = float(np.median(sl[inner]))
        # the run: horizontal distance between the profile's crossings of the layer's base and top (the top layer:
        # 0.5 m under the plateau, which is the layer's top all along)
        tt = t - 0.5 if t >= col.top_m - 1e-6 else t
        xb = float(np.interp(b, prof[::-1], x[::-1].astype(float)))
        xt = float(np.interp(tt, prof[::-1], x[::-1].astype(float)))
        run_m = abs(xb - xt) * cell
        want = (tt - b) / math.tan(math.radians(d['Sc_deg']))
        good = abs(med - d['Sc_deg']) <= 2.0 and abs(run_m - want) <= 1.5 * cell
        ok = ok and good
        rows.append(dict(layer=d['name'], Sc_deg=d['Sc_deg'], slope_median=round(med, 2), cells=int(inner.sum()),
                         run_m=round(run_m, 2), run_want_m=round(want, 2), ok=good))
    check('composite threshold: each layer at its own angle in a 1D profile (a 165 m wall 8 degrees over the '
          'column, relaxed)', ok,
          dict(layers=rows, iterations=iters, seconds=round(secs, 1)))
    return prof


def test_talus():
    col = S.column([(60.0, 1.0, 32.0, 'shale', 'bench'), (60.0, 0.2, 80.0, 'sandstone', 'cliff')])
    cell = 1.0
    W = 300
    x = np.arange(W)
    # a bench at zs 40 (inside the lower layer) with a 80 m wall of the upper rock standing on it at x < 150
    h = np.where(x < 150, 120.0, 40.0).astype(F32)[None, :]
    h = np.where(x < 150, h, 40.0).astype(F32)
    pin_w = np.zeros_like(h)
    pin_w[0, -1] = 1.0                                                # the far end of the bench held, nothing else
    pin_h = h.copy()
    prof, mk, iters = profile_run(col, h, pin_w, pin_h, cell, carry_off=False, rate=0.12, max_iter=80000)
    loose = mk[:, 3].astype(np.float64)
    sl = np.degrees(np.arctan(np.abs(np.diff(prof)) / cell))
    lm = 0.5 * (loose[1:] + loose[:-1])
    zmid = 0.5 * (prof[1:] + prof[:-1])
    apron = (lm > 3.0) & (zmid > 44.0)                                # the talus cone's face, off its toe
    top_talus = float(prof[loose > 0.5].max()) if (loose > 0.5).any() else 40.0
    cliff = (lm < 0.5) & (zmid > max(top_talus + 4.0, 64.0)) & (zmid < 116.0)    # the strong rock above the apron
    med_a = float(np.median(sl[apron])) if apron.sum() > 3 else float('nan')
    med_c = float(np.median(sl[cliff])) if cliff.sum() > 0 else float('nan')
    vol = float(loose.sum() * cell)
    ok = abs(med_a - 34.0) <= 2.5 and med_c >= 75.0
    check('debris rests at repose below a standing cliff', ok,
          dict(apron_slope_median=round(med_a, 2), apron_cells=int(apron.sum()), cliff_slope_median=round(med_c, 2),
               cliff_cells=int(cliff.sum()), talus_m2=round(vol, 1), iterations=iters))


def test_weathering():
    """Weathering (strata_weather): a strong cap over a weak slope over a strong bench. The weak rock wears back, the
    cap fails over it and retreats, the bench below stays flat, the cap's top stays flat, the cap's wall stays a
    cliff. Each step wears about 1.3 % of a cell off the weak slope, as the canyon's first pass does (0.84 m on its
    62.5 m cells); while it retreats the weak slope stands up to ~10 degrees over its static angle (undercutting
    against failure), so it is checked as a slope within 12 degrees of its angle (test_profile checks the static
    angle)."""
    col = S.column([(40.0, 0.2, 75.0, 'sandstone', 'bench'), (60.0, 3.0, 30.0, 'shale', 'slope'),
                    (40.0, 0.2, 80.0, 'sandstone', 'cap')])
    W, H, cell = 120, 4, 2.0
    x = np.arange(W)
    h = np.repeat(np.where(x < 70, 140.0, 40.0).astype(F32)[None, :], H, 0)
    dev = FL.device('twin')
    z = np.zeros_like(h)
    pw = np.zeros_like(h)
    pw[:, -1] = 1.0
    pins = dict(pin_w=pw, pin_h=h.copy(), A_in=z, qs_in=z)
    K0 = 1.5e-6
    run = S.StrataRun(dev, cell, {'h': h, 'bed': h.copy()}, T.rgba(z, z + K0, z + 1.0, z), pins, col, z, None, 2,
                      math.tan(math.radians(34.0)), (5e-4, math.tan(math.radians(30.0)), K0, 1e-3, 0.0))
    t0 = time.time()
    for _ in range(2500):
        run.weather_pass(18.0)
        run.threshold(3, 0.12)
    r = dev.read(run.S.src)[H // 2, :, 0].astype(np.float64)
    front = int(np.argmax(r < 139.0))
    sl = np.degrees(np.arctan(np.abs(np.diff(r)) / cell))
    zmid = 0.5 * (r[1:] + r[:-1])
    weak = (zmid > 46.0) & (zmid < 94.0)
    cap = (zmid > 104.0) & (zmid < 136.0)
    bench = float(np.max(np.abs(r[100:118] - 40.0)))
    top = float(np.max(np.abs(r[:max(front - 4, 1)] - 140.0)))
    med_w = float(np.median(sl[weak])) if weak.any() else float('nan')
    med_c = float(np.median(sl[cap])) if cap.any() else float('nan')
    ok = ((70 - front) * cell >= 40.0 and bench <= 0.5 and top <= 0.5 and 30.0 - 3.0 <= med_w <= 30.0 + 12.0
          and med_c >= 70.0)
    check('weathering: a cap retreats over its weak layer, the bench and the cap top stay flat', ok,
          dict(retreat_m=(70 - front) * cell, bench_max_dev_m=round(bench, 3), cap_top_max_dev_m=round(top, 3),
               weak_slope_median=round(med_w, 2), cap_wall_median=round(med_c, 2), seconds=round(time.time() - t0, 1)))


def test_tables():
    col = S.column('colorado_plateau')
    rng = np.random.default_rng(3)
    zs = rng.uniform(-50.0, col.top_m + 50.0, 20000)
    edges = np.array([f[0] for f in col.fine] + [col.fine[-1][1]])
    near = np.min(np.abs(zs[:, None] - edges[None, :]), axis=1) < col.dz
    zc = np.clip(zs, 0.0, col.top_m - 1e-9)
    idx = np.clip(np.searchsorted(edges, zc, side='right') - 1, 0, len(col.fine) - 1)
    k_exact = np.array([col.fine[i][2] for i in idx])
    t_exact = np.array([col.fine[i][3] for i in idx])
    kf = col.k_at(zs)
    tf = col.tan_at(zs)
    err_k = float(np.max(np.abs(kf - k_exact)[~near]))
    err_t = float(np.max(np.abs(tf - t_exact)[~near]))
    inv = np.array([1.0 / f[3] for f in col.fine])
    cum = np.concatenate([[0.0], np.cumsum(np.diff(edges) * inv)])

    def R_exact(z):
        if z <= 0:
            return z * inv[0]
        if z >= col.top_m:
            return cum[-1] + (z - col.top_m) * inv[-1]
        k = int(np.searchsorted(edges, z, side='right') - 1)
        return cum[k] + (z - edges[k]) * inv[k]
    grid_z = col.zs[::7]
    err_R = float(np.max(np.abs(col.run_at(grid_z) - np.array([R_exact(z) for z in grid_z]))))
    far = np.array([-300.0, col.top_m + 300.0])
    err_far = float(np.max(np.abs(col.run_at(far) - np.array([R_exact(z) for z in far]))))
    mono = bool(np.all(np.diff(col.R) > 0))
    ok = err_k <= 1e-9 and err_t <= 1e-9 and err_R <= 1e-6 and err_far <= 1e-6 and mono
    check('column tables: K, tan and R against the beds', ok,
          dict(column=col.name, beds=len(col.fine), table=len(col.R), max_err_K=err_k, max_err_tan=err_t,
               max_err_R_m=err_R, max_err_R_beyond_m=err_far, monotonic=mono))
    for name in S.COLUMNS:
        c = S.column(name)
        print(c.describe(), flush=True)


def test_route_incise_column():
    """The twin of route_incise reads the column as K x k_at(h - zoff): one step with the column vs the same step
    with K pre-multiplied per cell and no column."""
    col = S.column('colorado_plateau')
    shape = (80, 96)
    rng = np.random.default_rng(5)
    h = (300.0 + 1400.0 * T.random_field(shape, 0, 1, 7, smooth=3)).astype(F32)
    zoff = (-50.0 + 30.0 * T.random_field(shape, 0, 1, 8, smooth=4)).astype(F32)
    A = T.random_field(shape, 100.0, 1e6, 9)
    qs = T.random_field(shape, 0.0, 50.0, 10)
    K = (1.5e-5 * (0.6 + 0.8 * T.random_field(shape, 0, 1, 11, smooth=2))).astype(F32)
    U = np.zeros(shape, F32)
    G = (0.5 * T.random_field(shape, 0, 1, 12, smooth=2)).astype(F32)
    pw, ph = T.pin_pattern(shape, 3, band=3, value=(300.0, 1700.0))
    mk = T.rgba(np.zeros(shape, F32), np.zeros(shape, F32), np.zeros(shape, F32), np.zeros(shape, F32))
    from eidoblend.terrain.solvers import fluvial  # noqa: F401
    ws = fluvial.flow_weights({'st': T.rgba(h)}, {'uDx': 12.0, 'uP': 1.0, 'uBound': T.BOUND_PINNED})['outW']
    base = dict(st=T.rgba(h, A, qs, np.zeros(shape, F32)), wsumT=ws, pin=T.rgba(pw, ph, np.zeros(shape, F32),
                                                                              np.zeros(shape, F32)), mk=mk)
    uni = dict(uDx=12.0, uDt=150.0, uM=0.5, uN=1.0, uP=1.0, uSlope=1, uPitFill=1, uPitEps=1e-3,
               uBound=T.BOUND_PINNED)
    a = fluvial.route_incise(dict(base, par=T.rgba(U, K, np.ones(shape, F32), G), kcol=np.asarray(col.K, F32)[None, :, None],
                                  zoff=zoff[..., None]),
                             dict(uni, uColZ0=F32(col.z0), uColDz=F32(col.dz), uColN=len(col.K)))
    Kz = (K * col.k_at(h.astype(np.float64) - zoff)).astype(F32)
    b = fluvial.route_incise(dict(base, par=T.rgba(U, Kz, np.ones(shape, F32), G), kcol=np.zeros((1, 1, 1), F32),
                                  zoff=np.zeros((1, 1, 1), F32)),
                             dict(uni, uColZ0=F32(0), uColDz=F32(1), uColN=0))
    d = float(np.max(np.abs(a['outS'][..., 0] - b['outS'][..., 0])))
    rng_h = float(np.ptp(a['outS'][..., 0]))
    moved = float(np.max(np.abs(a['outS'][..., 0] - h)))
    check('K(z) lookup: route_incise twin with the column = K x col.k_at(h - zoff)', d <= 1e-4 * rng_h,
          dict(max_abs_m=d, range_m=rng_h, max_step_change_m=moved, table=len(col.K)))


def test_meanders():
    rows = []
    ok = True
    for sig in (1.5, 2.5, 3.5):
        lam = 1200.0
        pts = RV.kinoshita((0.0, 0.0), 90.0, 40000.0, wavelength_m=lam, sinuosity=sig, skew=0.03, vary=0.0, seed=1)
        m = RV.metrics(pts, wavelength_hint=lam)
        want_wl = lam / sig
        good = (abs(m['sinuosity'] / sig - 1.0) <= 0.02 and abs(m['wavelength_m'] / want_wl - 1.0) <= 0.06
                and m['neck_m'] > 4 * 40.0)
        ok = ok and good
        rows.append(dict(sinuosity_target=sig, sinuosity=round(m['sinuosity'], 4), wavelength_m=round(m['wavelength_m'], 1),
                         wavelength_want_m=round(want_wl, 1), neck_m=round(m['neck_m'], 1),
                         theta0_deg=round(math.degrees(RV.theta0_for(sig, 0.03)), 2), ok=good))
    for seed in (1, 2, 3):
        pts = RV.kinoshita((500.0, -300.0), 250.0, 30000.0, wavelength_m=1100.0, sinuosity=3.0, vary=0.15, seed=seed)
        m = RV.metrics(pts, wavelength_hint=1100.0)
        d0 = float(np.min(np.hypot(pts[:, 0] - 500.0, pts[:, 1] + 300.0)))
        chord = pts[-1] - pts[0]
        az = math.degrees(math.atan2(chord[0], chord[1])) % 360.0
        good = m['neck_m'] > 4 * 40.0 and d0 < 2.0 and abs((az - 250.0 + 180) % 360 - 180) < 2.0 \
            and 2.6 < m['sinuosity'] < 3.4
        ok = ok and good
        rows.append(dict(seed=seed, vary=0.15, sinuosity=round(m['sinuosity'], 3), neck_m=round(m['neck_m'], 1),
                         through_m=round(d0, 3), azimuth_deg=round(az, 2), ok=good))
    w = RV.walk((0.0, 0.0), 45.0, 30000.0, wiggle_deg=12.0, wiggle_wavelength_m=3000.0, seed=4)
    mw = RV.metrics(w)
    good_w = 1.0 < mw['sinuosity'] < 1.15 and mw['neck_m'] > 1000.0
    ok = ok and good_w
    rows.append(dict(walk=True, sinuosity=round(mw['sinuosity'], 4), neck_m=round(mw['neck_m'], 1), ok=good_w))
    # a growing train (growth 0.55): the stages' sinuosity rises to the final course's, which is the fixed course
    # itself, and every bend keeps its down-valley place (the crossings of the valley axis move little)
    p = dict(kind='kinoshita', through=(0.0, 0.0), flow_azimuth_deg=90.0, wavelength_m=7000.0, sinuosity=3.8,
             vary=0.3, flat=0.02, growth=0.55, growth_stages=6, length_m=20000.0)
    rv = RV.make_river(p, 1, 12000.0)
    fixed, _ = RV.course(dict(p, growth=1.0), 1, 12000.0)
    sins = [RV.metrics(pts)['sinuosity'] for _f, pts, _s in rv.stages] + [RV.metrics(rv.final_course[0])['sinuosity']]

    def crossings(pts):
        y = pts[:, 1]
        k = np.nonzero(np.sign(y[1:]) != np.sign(y[:-1]))[0]
        return pts[k, 0]
    c0, c1 = crossings(rv.stages[0][1]), crossings(rv.final_course[0])
    inner = c1[np.abs(c1) < 6000.0]
    shift = float(np.median([np.min(np.abs(c0 - x)) for x in inner])) if len(inner) and len(c0) else float('inf')
    wl_dv = 7000.0 / 3.8
    good_g = (all(b > a for a, b in zip(sins, sins[1:])) and np.array_equal(rv.final_course[0], fixed)
              and shift < 0.15 * wl_dv)
    ok = ok and good_g
    rows.append(dict(growth=0.55, stage_sinuosity=[round(v, 2) for v in sins], final_is_fixed_course=bool(
        np.array_equal(rv.final_course[0], fixed)), crossing_shift_median_m=round(shift, 1),
        shift_limit_m=round(0.15 * wl_dv, 1), ok=good_g))
    check('meander curve geometry (Kinoshita sinuosity, wavelength, necks; the walk)', ok, rows)


def main():
    t0 = time.time()
    for fn in (test_tables, test_route_incise_column, test_meanders, test_profile, test_talus, test_weathering):
        try:
            fn()
        except Exception as e:                                    # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
    RESULTS['_seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, 'strata_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} ({RESULTS['_seconds']} s)")
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
