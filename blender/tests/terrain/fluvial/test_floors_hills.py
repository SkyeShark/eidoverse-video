"""The fluvial package's valley floors and soil hillslopes on synthetic ground with known answers (plain Python, the
numpy twins; no Blender):

    python blender/tests/terrain/fluvial/test_floors_hills.py

  valley_floor (solvers/fluvial.py)
    1. a straight V valley (walls at 35 degrees, a 2 % fall) draining 2, 12.5 and 50 km2: the flat floor (cells
       within 1 m of the floor's centre line height) is width_m (A / A_ref)^0.5 wide, within 25 %
    2. the floor falls downstream (its centre line monotone), the fill is counted in `deposit`, and no closed
       depression is left (the filled surface's spill-fill adds under 1 mm anywhere)
    3. a tributary joining the aggraded trunk: its mouth is backfilled to the trunk's floor, so no pit there
  soil_hills (solvers/hillslope.py)
    4. channels every 300 m: off the channels the Laplacian of h is -U/D = -8 relief / spacing^2 within 10 %
       (the steady state of linear creep), the hills are convex (curvature < 0 at every crest) and the relief is
       the knob's within 15 %
    5. with asymmetry 0.4 and the wind from the west, the east-facing (lee) slopes are steeper than the
       west-facing ones by about (1 + a) / (1 - a) on the mean gradient, and the crests move east
    6. seed_m on level ground: the swales form (local relief over the spacing at least 0.4 x the knob) and the
       surface drains (the spill-fill adds under 2 cm: what is left is the iterative solve's residue, a few
       cells a centimetre deep that shrink with more iterations and that run.py's end stage fills; before the
       swales were held down to their outlets, whole swale segments were dammed as deep as the rise cap)
    7. head_soft 2: a channel starting halfway down a hillside makes no cone-shaped funnel at its head (the
       steepest slope within 15 m of the head at most 0.85 x the one with the hold at full strength from its first
       cell), and where the channel is fully held the two agree within 0.5 m
    8. hold_deposit_m: an alluvial floor (deposit 3 m) inside a soil-mantled valley stays flat (under 1 cm), where
       without it the solve domes it (over 10 cm)
    9. rill_width_m 0.45 on a 0.15 m level: a smooth Gaussian groove rill_depth_m deep (within 2 cm), its
       half-depth width 2.355 sigma (within 20 %), no one-cell slot down its middle (the centre under 1 cm below
       its neighbours' mean), its walls under 12 degrees
       rill_cut: a child level cutting rills on its parent's cut surface (rill_cut inherited) cuts them once: the
       same depth within 5 mm, not two levels' depths stacked
       a closed hollow 0.6 m deep between two swales 60 m apart is solved as hillslope (under 10 % of it flatter than
       0.05 degrees, no closed depression left over 2 cm), not held flat at its fill level
  incise (solvers/fluvial.py)
   10. a base-level fall along a straight course over a hilly upland: the channel is cut to the upland's grade minus
       drop_m (within 15 %), the cut falls off away from the course (a valley), and 900 m and more from it the
       ground is as a control run without the fall left it (|dh| under 0.5 m: the knickpoints climbed only as far
       as the time allowed)
   11. head_m and taper_m: the river rises inside the window and its fall eases in: at the head the cut is under a
       quarter of the drop, it grows over the taper, below it is over 0.6 of the drop, and above the head the
       ground is untouched (under 0.5 m)
       the 'incised' field on a refining level: a slot 30 m deep with 40-degree walls, graded at 0.7 m/km, keeps
       its floor (under 1 cm) through 400 steps, where unheld it fills from its walls (over 0.5 m)
  uplift (solvers/fluvial.py)
   12. the regional background's cut on a 192 km window: half to 85 % of it unuplifted lowland, 95 % of that
       connected to the window's edge (so it drains; no closed basins filling), where without the cut under 5 %
       is
  run.py grow_levels
   13. a three-level plan with grow_levels 2: the first two levels grow (the uplift runs, the controller steers),
       the third refines (the lock, no uplift)
Writes blender/tests/terrain/out/fluvial/floors_hills_tests.json; exit code 1 on a failure.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'fluvial'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import hillslope as HS  # noqa: E402
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402

DEV = FL.device('twin')
RES = {}
FAILED = []


def check(name, ok, detail):
    RES[name] = dict(ok=bool(ok), detail=detail)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)
    if not ok:
        FAILED.append(name)


def ctx_of(lv):
    return FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='grow', device=DEV, log=lambda m: None)


def v_valley(n=160, cell=10.0, area_km2=50.0):
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h = 0.02 * (y - lv.y0) + np.tan(np.radians(35.0)) * np.abs(x)
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32)})
    A, _ = HY.route_to_convergence(DEV, HY.routing_surface(HY.fill_depressions(h)[0]), cell)
    f['A'] = np.where(np.abs(x) < 0.6 * cell, A + area_km2 * 1e6, A).astype(np.float32)
    return lv, f, x, y, h


def test_floor_widths():
    rows = []
    ok = True
    for akm2 in (2.0, 12.5, 50.0):
        lv, f, x, y, h0 = v_valley(area_km2=akm2)
        want = 120.0 * (akm2 * 1e6 / 5e7) ** 0.5
        FL.op_valley_floor(f, lv, {'width_m': 120.0, 'area_ref_m2': 5e7, 'area_min_m2': 1e6, 'cross_slope': 0.0,
                                   'toe_cells': 0.0}, ctx=ctx_of(lv))
        h = np.asarray(f['h'], np.float64)
        j = h.shape[0] // 2
        row = h[j] - h[j].min()
        got = float(np.sum(row < 1.0) * lv.cell)
        rows.append((akm2, round(want, 1), got))
        ok &= abs(got - want) <= 0.25 * want + lv.cell
    check('valley_floor: the floor is width_m (A / A_ref)^0.5 wide', ok,
          '; '.join(f'{a:g} km2: want {w} m, got {g:.0f} m' for a, w, g in rows))


def test_floor_drains():
    lv, f, x, y, h0 = v_valley(area_km2=50.0)
    FL.op_valley_floor(f, lv, {'width_m': 120.0, 'area_ref_m2': 5e7, 'area_min_m2': 1e6}, ctx=ctx_of(lv))
    h = np.asarray(f['h'], np.float64)
    centre = h[:, h.shape[1] // 2]
    mono = bool(np.all(np.diff(centre[20:-20]) > 0))           # rising northward = falling downstream (south)
    dep = np.asarray(f['deposit'], np.float64)
    counted = float(np.max(np.abs((h - h0) - dep)))
    filled, _ = HY.fill_depressions(h)
    pits = float(np.max(filled - h))
    check('valley_floor: the floor falls downstream, deposit is the fill, no pits', mono and counted < 1e-3 and
          pits < 1e-3, f'centre line monotone {mono}; |fill - deposit| max {counted:.2e} m; spill-fill max '
                       f'{pits:.2e} m')


def test_tributary_backfill():
    n, cell = 160, 10.0
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    trunk = 0.02 * (y - lv.y0) + np.tan(np.radians(35.0)) * np.abs(x)
    # a tributary valley from the east, its floor falling west at 6 % to the trunk's channel
    yt = 200.0
    trib = 0.02 * (yt - lv.y0) + 0.06 * np.maximum(x, 0.0) + np.tan(np.radians(30.0)) * np.abs(y - yt)
    h = np.minimum(trunk, np.where(x > 0, trib, np.inf))
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32)})
    A, _ = HY.route_to_convergence(DEV, HY.routing_surface(HY.fill_depressions(h)[0]), cell)
    A = np.where(np.abs(x) < 0.6 * cell, A + 5e7, A)
    A = np.where((np.abs(y - yt) < 0.6 * cell) & (x > 0), A + 3e6, A)
    f['A'] = A.astype(np.float32)
    FL.op_valley_floor(f, lv, {'width_m': 120.0, 'area_ref_m2': 5e7, 'area_min_m2': 1e6}, ctx=ctx_of(lv))
    hn = np.asarray(f['h'], np.float64)
    filled, _ = HY.fill_depressions(hn)
    pits = float(np.max(filled - hn))
    j = int(round((yt - lv.y0) / cell - 0.5))
    mouth = hn[j, n // 2 + 3:n // 2 + 12] - hn[j, n // 2]
    check('valley_floor: a tributary mouth backfills to the trunk floor (no pit)', pits < 1e-3 and
          bool(np.all(np.diff(mouth) >= -1e-6)),
          f'spill-fill max {pits:.2e} m; the tributary floor over the trunk channel going upstream: '
          f'{np.round(mouth, 2).tolist()}')


def hills(asym=0.0, n=128, cell=10.0, relief=25.0):
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h = 0.01 * (y - lv.y0) + relief * np.abs(np.sin(np.pi * x / 300.0))
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32)})
    A, _ = HY.route_to_convergence(DEV, HY.routing_surface(HY.fill_depressions(h)[0]), cell)
    f['A'] = A
    HS.op_soil_hills(f, lv, {'valley_spacing_m': 300.0, 'relief_m': relief, 'channel_frac': 0.25,
                             'asymmetry': asym, 'wind_from_deg': 270.0, 'iter_scale': 3.0}, ctx=ctx_of(lv))
    return lv, f, x, y, np.asarray(f['h'], np.float64), A >= 0.25 * 300.0 ** 2


def test_soil_steady():
    lv, f, x, y, h, chan = hills()
    C = HS.soil_convexity(25.0, 300.0)
    lap = np.zeros_like(h)
    for k in range(8):
        dx, dy = FL.T.OFF[k]
        hq = np.roll(np.roll(h, -dy, 0), -dx, 1)
        lap += FL.T.WISO[k] * (hq - h)
    lap /= lv.cell ** 2
    near = chan.copy()
    for _ in range(2):
        near = near | np.roll(near, 1, 0) | np.roll(near, -1, 0) | np.roll(near, 1, 1) | np.roll(near, -1, 1)
    inner = np.zeros_like(chan)
    inner[8:-8, 8:-8] = True
    sel = inner & ~near
    med = float(np.median(lap[sel]))
    rows = h[40:-40] - 0.01 * (y[40:-40] - lv.y0)
    relief = float(np.median(rows.max(axis=1) - rows.min(axis=1)))
    check('soil_hills: steady linear creep between the channels (Laplacian -U/D, convex, relief)',
          abs(med + C) <= 0.1 * C and abs(relief - 25.0) <= 0.15 * 25.0 and med < 0,
          f'median Laplacian {med:.3g} /m against {-C:.3g}; hill relief {relief:.1f} m (knob 25)')


def test_soil_asymmetry():
    lv, f, x, y, h, chan = hills(asym=0.4)
    gx = np.gradient(h, lv.cell, axis=1)
    inner = (slice(20, -20), slice(20, -20))
    g = gx[inner]
    lee = float(np.mean(-g[g < -0.02]))                        # facing east: the lee of a west wind
    stoss = float(np.mean(g[g > 0.02]))
    ratio = lee / stoss
    want = (1.4 / 0.6) ** 0.5                                  # crest moved: L_lee / L_stoss = sqrt((1-a)/(1+a))
    sym = hills(asym=0.0)[4]
    j = h.shape[0] // 2
    col = slice(lv.n // 2 + 2, lv.n // 2 + 28)                 # between the channels at 0 and +300 m
    shift = (int(np.argmax(h[j, col])) - int(np.argmax(sym[j, col]))) * lv.cell
    check('soil_hills: lee slopes steeper with the wind from the west, crests moved east',
          ratio > 1.25 and shift > 0, f'lee {np.degrees(np.arctan(lee)):.1f} deg vs stoss '
                                      f'{np.degrees(np.arctan(stoss)):.1f} deg (ratio {ratio:.2f}, about {want:.2f} '
                                      f'expected), crest {shift:+.0f} m')


def test_soil_seed():
    n, cell = 128, 0.5
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h = 10.0 + 0.002 * y                                       # level ground, a 0.1 degree fall to the north
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32)})
    HS.op_soil_hills(f, lv, {'valley_spacing_m': 16.0, 'relief_m': 0.8, 'channel_frac': 0.25, 'seed_m': 0.3,
                             'seed_max_cell_m': 1.0, 'rise_cap': 0.8, 'iter_scale': 2.0}, seed=3, ctx=ctx_of(lv))
    hn = np.asarray(f['h'], np.float64) - 0.002 * y
    k = int(16.0 / cell)
    inner = hn[16:-16, 16:-16]
    loc = [float(np.ptp(inner[j:j + k, i:i + k])) for j in range(0, inner.shape[0] - k, k // 2)
           for i in range(0, inner.shape[1] - k, k // 2)]
    filled, _ = HY.fill_depressions(np.asarray(f['h'], np.float64))
    pits = float(np.max(filled - np.asarray(f['h'], np.float64)))
    med = float(np.median(loc))
    check('soil_hills: seed_m makes swales on level ground, and they drain', med >= 0.4 * 0.8 and pits < 0.02,
          f'local relief over 16 m: median {med:.2f} m (knob 0.8); spill-fill max {pits:.3f} m')


def test_incise():
    n, cell = 128, 20.0
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h0 = 80.0 + 0.004 * x + 6.0 * np.sin(x / 70.0) * np.cos(y / 55.0)       # a hilly upland falling west
    fl = {'K': 4e-5, 'valley_spacing_m': 300.0, 'threshold_deg': 35.0}
    years, stages = 20000.0, 4
    f = Fields(lv, {'h': h0.astype(np.float32), 'bed': h0.astype(np.float32)})
    ctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='grow', device=DEV, log=lambda m: None)
    drop = 40.0
    FL.op_incise(f, lv, {'kind': 'polyline', 'points': [[1400.0, -200.0], [-1400.0, -200.0]], 'through': [0.0, -200.0],
                         'width_m': 40.0, 'drop_m': drop, 'years': years, 'stages': stages, 'fluvial': fl},
                 seed=1, ctx=ctx)
    h = np.asarray(f['h'], np.float64)
    # the control: the same physics for the same steps, without the fall (the synthetic upland erodes on its own)
    c = Fields(lv, {'h': h0.astype(np.float32), 'bed': h0.astype(np.float32)})
    cctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='grow', device=DEV, log=lambda m: None)
    dt = 1000.0 * cell / FL.CELL_REF_M
    FL.op_fluvial(c, lv, dict(fl, relief_m=None, lock=False, steps=max(int(round(years / dt)), stages),
                              min_steps=1), seed=1, ctx=cctx)
    hc = np.asarray(c['h'], np.float64)
    inc = ctx.shared['incise']
    on = (np.abs(y + 200.0) < 15.0) & (np.abs(x) < 900.0)
    bed = inc['bed_m'] + inc['gradient'] * x[on]                # the course runs west: arc length = -x
    cut_to = float(np.median(h[on] - bed))
    d = np.abs(y + 200.0)
    near = float(np.mean((hc - h)[(d > 40.0) & (d < 140.0) & (np.abs(x) < 900.0)]))
    mid = float(np.mean((hc - h)[(d > 300.0) & (d < 450.0) & (np.abs(x) < 900.0)]))
    far = float(np.max(np.abs(hc - h)[(d >= 900.0) & (np.abs(x) < 900.0)]))
    ok = abs(cut_to) <= 0.15 * drop and near > mid >= -0.5 and far < 0.5
    check('incise: the course cut to grade - drop, a valley about it, the far upland as without the fall', ok,
          f'channel {cut_to:+.1f} m from the final bed (drop {drop:g} m); cut beyond the control run: 40-140 m off '
          f'{near:.1f} m, 300-450 m off {mid:.1f} m; |dh| beyond 900 m max {far:.2f} m')


def test_incise_head():
    """head_m and taper_m: the course rises inside the window and its fall eases in, so the head is a shallow
    valley deepening downstream, not a pit as deep as the drop."""
    n, cell = 128, 20.0
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h0 = 80.0 + 0.004 * x + 6.0 * np.sin(x / 70.0) * np.cos(y / 55.0)
    fl = {'K': 4e-5, 'valley_spacing_m': 300.0, 'threshold_deg': 35.0}
    years, stages, drop = 20000.0, 4, 40.0
    f = Fields(lv, {'h': h0.astype(np.float32), 'bed': h0.astype(np.float32)})
    ctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='grow', device=DEV, log=lambda m: None)
    FL.op_incise(f, lv, {'kind': 'polyline', 'points': [[1400.0, -200.0], [-1400.0, -200.0]], 'through': [0.0, -200.0],
                         'width_m': 40.0, 'drop_m': drop, 'years': years, 'stages': stages, 'fluvial': fl,
                         'head_m': 800.0, 'taper_m': 600.0}, seed=1, ctx=ctx)
    c = Fields(lv, {'h': h0.astype(np.float32), 'bed': h0.astype(np.float32)})
    cctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='grow', device=DEV, log=lambda m: None)
    dt = 1000.0 * cell / FL.CELL_REF_M
    FL.op_fluvial(c, lv, dict(fl, relief_m=None, lock=False, steps=max(int(round(years / dt)), stages),
                              min_steps=1), seed=1, ctx=cctx)
    cut = np.asarray(c['h'], np.float64) - np.asarray(f['h'], np.float64)
    on = np.abs(y + 200.0) < 15.0
    at = [float(np.max(cut[on & (np.abs(x - xc) < 40.0)])) for xc in (780.0, 600.0, 400.0, 200.0, -300.0, -800.0)]
    upstream = float(np.max(np.abs(cut[(x > 900.0) & (np.abs(y + 200.0) < 60.0)])))
    ok = at[0] < 0.25 * drop and at[0] < at[1] < at[2] and min(at[3:]) > 0.6 * drop and upstream < 0.5
    check('incise head_m / taper_m: the river rises in the window, its fall easing in (no pit at the head)', ok,
          f'cut under the control run at 780, 600, 400, 200, -300, -800 m: {np.round(at, 1).tolist()} (drop '
          f'{drop:g} m); above the head max |dh| {upstream:.2f} m')


def test_regional_cut():
    """The uplift's regional background with cut: separate massifs, the lowland between them unuplifted and
    connected to the window's edge (so it drains: no closed basins filling)."""
    n = 256
    lv = L.Level(0, 'context', -96000.0, -96000.0, 192000.0, 750.0, n)
    reg = {'kind': 'fbm', 'fraction': 0.42, 'wavelength_m': 14000.0, 'texture': 0.6, 'octaves': 3, 'blend': 0.1}
    u0 = FL.composite_uplift({'regional': dict(reg)}, lv, 1, DEV)
    u1 = FL.composite_uplift({'regional': dict(reg, cut=1.25)}, lv, 1, DEV)
    low = u1 <= 1e-9
    reach = np.zeros_like(low)
    reach[0, :], reach[-1, :], reach[:, 0], reach[:, -1] = low[0, :], low[-1, :], low[:, 0], low[:, -1]
    for _ in range(4 * n):
        grown = reach.copy()
        grown[1:, :] |= reach[:-1, :]
        grown[:-1, :] |= reach[1:, :]
        grown[:, 1:] |= reach[:, :-1]
        grown[:, :-1] |= reach[:, 1:]
        grown &= low
        if np.array_equal(grown, reach):
            break
        reach = grown
    frac = float(low.mean())
    conn = float(reach.sum() / max(low.sum(), 1))
    ok = 0.5 <= frac <= 0.85 and conn >= 0.95 and float((u0 <= 1e-9).mean()) < 0.05 and float(u1.max()) > 0.1
    check('uplift regional cut: lowlands unuplifted between the massifs and connected to the edge', ok,
          f'lowland {frac:.2f} of the window (no cut: {float((u0 <= 1e-9).mean()):.2f}), {conn:.3f} of it connected '
          f'to the edge; the massifs reach {float(u1.max()):.2f} of the range uplift (no cut {float(u0.max()):.2f}), '
          f'mean {float(u1.mean()):.3f} (no cut {float(u0.mean()):.3f})')


def head_slope(soft):
    """A channel starting halfway down a hillside (a V valley falling south; the channel's area grows from its
    head): the soil hillslopes' steepest slope within 3 cells of the head, and the solution."""
    n, cell = 96, 5.0
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h = 0.05 * (y - lv.y0) + 0.15 * np.abs(x)
    a_ch = 0.25 * 120.0 ** 2
    yh = 40.0                                                  # the head
    line = np.abs(x) < 0.6 * cell
    A = np.full(h.shape, cell * cell)
    A = np.where(line & (y <= yh), a_ch * (1.0 + (yh - y) / 60.0), A)
    A = np.where(line & (y > yh), a_ch * np.exp(-(y - yh) / 40.0), A)
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32), 'A': A.astype(np.float32)})
    HS.op_soil_hills(f, lv, {'valley_spacing_m': 120.0, 'relief_m': 6.0, 'channel_frac': 0.25, 'flow_exponent': 1.0,
                             'head_soft': soft, 'rise_cap': 2.0, 'iter_scale': 3.0}, ctx=ctx_of(lv))
    hn = np.asarray(f['h'], np.float64)
    gy, gx = np.gradient(hn, cell)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    near = np.hypot(x, y - yh) <= 3.0 * cell
    return float(s[near].max()), hn, x, y


def test_soil_heads():
    hard, h1, x, y = head_slope(1.0)
    soft, h2, _, _ = head_slope(2.0)
    far = (y < -120.0) & (np.abs(x) < 100.0)
    same = float(np.max(np.abs(h1 - h2)[far]))
    check('soil_hills head_soft: a channel head is no cone-shaped funnel (its hold eases in)',
          soft <= 0.85 * hard and same < 0.5,
          f'steepest slope within 15 m of the head: {soft:.1f} deg eased against {hard:.1f} deg held at once; '
          f'where the channel is fully held downstream the two differ by at most {same:.2f} m')


def test_soil_floor_hold():
    """hold_deposit_m: an alluvial floor (deposit) inside a soil-mantled valley stays flat."""
    n, cell = 128, 5.0
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    floor = np.abs(x) < 40.0
    h = 0.01 * (y - lv.y0) + np.where(floor, 0.0, np.tan(np.radians(15.0)) * (np.abs(x) - 40.0))
    dep = np.where(floor, 3.0, 0.0)
    out = {}
    for hold in (None, 0.3):
        f = Fields(lv, {'h': h.astype(np.float32), 'bed': (h - dep).astype(np.float32),
                        'deposit': dep.astype(np.float32)})
        HS.op_soil_hills(f, lv, {'valley_spacing_m': 200.0, 'relief_m': 8.0, 'channel_frac': 0.25,
                                 'hold_deposit_m': hold, 'iter_scale': 2.0}, ctx=ctx_of(lv))
        hn = np.asarray(f['h'], np.float64)
        inner = floor & (np.abs(y) < 200.0)
        out[hold] = float(np.max(np.abs(hn - h)[inner]))
    check('soil_hills hold_deposit_m: an alluvial floor stays flat', out[0.3] < 0.01 and out[None] > 0.1,
          f'the floor moved at most {out[0.3]:.3f} m held, {out[None]:.2f} m not')


def test_rill_width():
    """rill_width_m: the rills are smooth Gaussian grooves rill_width_m wide (sigma) and rill_depth_m deep on a
    0.15 m level, no one-cell slot in their middle."""
    n, cell = 128, 0.15
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h = 0.02 * (y - lv.y0)
    a_ch = 0.25 * 30.0 ** 2
    A = np.where(np.abs(x - 0.5 * cell) < 0.1 * cell, a_ch * 1.01, cell * cell)     # one column of cells
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32), 'A': A.astype(np.float32)})
    HS.op_soil_hills(f, lv, {'valley_spacing_m': 30.0, 'relief_m': 1.0, 'channel_frac': 0.25, 'flow_exponent': 1.0,
                             'blend': 0.0, 'rill_depth_m': 0.12, 'rill_max_cell_m': 0.7, 'rill_width_m': 0.45,
                             'rill_growth_max': 1.5}, ctx=ctx_of(lv))
    d = h - np.asarray(f['h'], np.float64)
    j = n // 2
    prof = d[j]
    c = int(np.argmax(prof))
    depth = float(prof[c])
    fwhm = float(np.sum(prof >= 0.5 * depth) * cell)
    slot = float(prof[c] - 0.5 * (prof[c - 1] + prof[c + 1]))
    gy, gx = np.gradient(np.asarray(f['h'], np.float64)[16:-16, 16:-16], cell)
    smax = float(np.degrees(np.arctan(np.max(np.abs(gx)))))
    want = 2.355 * 0.45
    ok = abs(depth - 0.12) <= 0.02 and abs(fwhm - want) <= 0.2 * want + cell and slot < 0.01 and smax < 12.0
    check('soil_hills rill_width_m: smooth grooves of the set width and depth', ok,
          f'depth {depth:.3f} m (0.12), half-depth width {fwhm:.2f} m ({want:.2f}), centre over its neighbours '
          f'{slot * 100:.2f} cm, steepest wall {smax:.1f} deg')


def test_incised_held():
    """An incised river's channel (the 'incised' field op_incise writes) stays where it arrives on a refining level:
    a slot 30 m deep with 40-degree walls, graded at 0.7 m/km, does not fill from its walls."""
    n, cell = 96, 10.0
    lv = L.Level(1, 'context', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    slot = np.abs(x) < 15.0
    h = 0.0007 * (y - lv.y0) + np.where(slot, 0.0, 30.0 * np.clip((np.abs(x) - 15.0) / 36.0, 0.0, 1.0)) + 50.0
    out = {}
    for held in (False, True):
        f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32)})
        if held:
            f['incised'] = slot.astype(np.float32)
        ctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='refine', device=DEV,
                              pins=FL.edge_pins(n, h.astype(np.float32)), log=lambda m: None)
        FL.op_fluvial(f, lv, {'K': 4e-5, 'valley_spacing_m': 300.0, 'threshold_deg': 30.0, 'lock': False,
                              'refine_steps': 400, 'dt_ref_yr': 1000.0}, seed=1, ctx=ctx)
        inner = slot & (np.abs(y) < 300.0)
        out[held] = float(np.max(np.asarray(f['h'], np.float64)[inner] - h[inner]))
    check('fluvial refine: an incised channel is held where it arrives', out[True] < 0.01 and out[False] > 0.5,
          f'the slot floor rose at most {out[True]:.3f} m held, {out[False]:.2f} m not')


def test_rills_once():
    """A child level that cuts rills first takes its parent's out (rill_cut): the rill is rill_depth_m deep on the
    child, not two levels' depths stacked."""
    n, cell = 96, 0.3
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    h = 0.02 * (y - lv.y0)
    a_ch = 0.25 * 30.0 ** 2
    line = np.abs(x - 0.5 * cell) < 0.1 * cell
    A = np.where(line, a_ch * 1.01, cell * cell)
    prm = {'valley_spacing_m': 30.0, 'relief_m': 1.0, 'channel_frac': 0.25, 'flow_exponent': 1.0, 'blend': 0.0,
           'rill_depth_m': 0.12, 'rill_max_cell_m': 0.7, 'rill_width_m': 0.6, 'rill_growth_max': 1.3}
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32), 'A': A.astype(np.float32)})
    HS.op_soil_hills(f, lv, prm, ctx=ctx_of(lv))
    once = float(np.max(h - np.asarray(f['h'], np.float64)))
    # the same level again, as a child that inherited its parent's cut surface and rill_cut
    g = Fields(lv, {'h': np.asarray(f['h'], np.float32), 'bed': np.asarray(f['h'], np.float32),
                    'A': A.astype(np.float32), 'rill_cut': np.asarray(f['rill_cut'], np.float32)})
    HS.op_soil_hills(g, lv, prm, ctx=ctx_of(lv))
    twice = float(np.max(h - np.asarray(g['h'], np.float64)))
    check('soil_hills rill_cut: a finer level cuts the rill once, not on top of its parent\'s', abs(twice - once) < 0.005,
          f'rill depth {once:.3f} m on the parent, {twice:.3f} m on the child')


def test_soil_hollows():
    """A closed hollow on a soil hillslope is no flat after the solve: its cells are hillslope (water crosses it
    along one path), so it is domed, not held at its fill level."""
    n, cell = 128, 2.0
    lv = L.Level(0, 'main', -n * cell / 2, -n * cell / 2, n * cell, cell, n)
    x, y = lv.xy()
    # two swales 60 m apart (the spacing: the hills between them rise the knob's relief, under the rise cap) and a
    # closed hollow 0.6 m deep between them
    groove = np.minimum(np.abs(x + 20.0), np.abs(x - 40.0))
    h = 0.01 * (y - lv.y0) - 1.0 * np.clip(1.0 - groove / 6.0, 0.0, 1.0) \
        - 0.6 * np.exp(-((x - 10.0) ** 2 + (y - 20.0) ** 2) / (2 * 8.0 ** 2))
    f = Fields(lv, {'h': h.astype(np.float32), 'bed': h.astype(np.float32)})
    # iter_scale 8: a 128-cell grid gets one coarse level, and the hollow starts 0.6 m under its rim (a seeded
    # level's hollows start filled, at their rim)
    HS.op_soil_hills(f, lv, {'valley_spacing_m': 60.0, 'relief_m': 1.0, 'channel_frac': 0.25, 'rise_cap': 1.5,
                             'iter_scale': 8.0}, ctx=ctx_of(lv))
    hn = np.asarray(f['h'], np.float64)
    gy, gx = np.gradient(hn, cell)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    pit = np.hypot(x - 10.0, y - 20.0) < 10.0
    flat = float(np.mean(s[pit] < 0.05))
    filled, _ = HY.fill_depressions(hn)
    check('soil_hills: a closed hollow is solved, not left a flat', flat < 0.1 and float(np.max(filled - hn)) < 0.02,
          f'{100 * flat:.1f} % of the hollow flatter than 0.05 degrees; spill-fill max '
          f'{float(np.max(filled - hn)):.3f} m')


def test_grow_levels():
    from eidoblend.terrain import run as RUN
    from eidoblend.terrain.core.recipe import Recipe, Stage
    plan = L.plan_levels(1280.0, 64, (0.0, 0.0), 4, None, None)
    R = Recipe('t', 'test', defaults={'grow_levels': 2}, stages=[
        Stage('uplift', {'shape': {'kind': 'dome', 'centre': [0.0, 0.0], 'radius_m': 2000.0}, 'U_m_per_yr': 2e-4,
                         'start_m': 20.0}, levels='all'),
        Stage('fluvial', {'K': 4e-5, 'valley_spacing_m': 300.0, 'age_myr': 0.05, 'relief_m': 30.0,
                          'refine_steps': 40}, levels='all')])
    info = {}
    RUN.run_levels(plan, R, {}, R.stages, seed=1, log=lambda m: None, device='twin', cache=False, info=info)
    roles = [r['role'] for r in info['shared']['fluvial_log'] if r.get('prepass') is None]
    ok = roles == ['grow', 'grow', 'refine']
    check('run.py grow_levels 2: levels 0 and 1 grow, level 2 refines', ok, f'roles by level {roles}')


def main():
    for fn in (test_floor_widths, test_floor_drains, test_tributary_backfill, test_soil_steady, test_soil_asymmetry,
               test_soil_seed, test_soil_heads, test_soil_floor_hold, test_rill_width, test_rills_once,
               test_soil_hollows, test_incise, test_incise_head, test_incised_held, test_regional_cut,
               test_grow_levels):
        try:
            fn()
        except Exception as e:                                         # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
    RES['failed'] = FAILED
    with open(os.path.join(OUT, 'floors_hills_tests.json'), 'w', encoding='utf-8') as fh:
        json.dump(RES, fh, indent=1)
    print(f'[fluvial.floors_hills] {len(FAILED)} failed: {FAILED}' if FAILED else '[fluvial.floors_hills] all passed')
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
