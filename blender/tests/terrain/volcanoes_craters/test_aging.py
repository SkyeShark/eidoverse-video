"""Package 9 (second half): the processes after the shapes, in plain Python with numpy (no Blender, no GPU).

    python blender/tests/terrain/volcanoes_craters/test_aging.py

  lava walkers   DOWNFLOW deterministic per seed (the design's check): the same seed and salt give the same passage
                 to the bit, another seed a different one; on a gentle plateau with bumps the flow runs downhill as a
                 tongue (the perturbation follows the local drop; walkers pond in hollows up to the flow's
                 thickness), not a puddle round its vent; its surface is level-topped with a front at 30-40
                 degrees
  lakes          volcano_lakes keeps a dry crater dry and its depression open, fills small pits with sediment,
                 holds a real basin as a lake, and a playa crater floor comes out flat over the asked fraction
  caldera lake   the lake stands at its own level and the caldera's walls above it are not buried (the basin that
                 holds the lake is not filled to the rim's lowest notch)
  islands        stack_piles sets Wizard Island's cinder cone on its lava platform, above the water
  apron          volcano_plain fills the low ground the vent's flows reach and leaves a valley behind a range crest
                 alone (filled, it dammed into a lake)
Exit status 0 when every check passes.
"""
import math
import sys
import time
import types

import numpy as np

import _common as C

V, I = C.import_solvers()
RESULTS = []


def check(name, ok, detail):
    RESULTS.append((bool(ok), name))
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)


def grid(n, cell, x0=None, y0=None):
    x0 = -0.5 * n * cell if x0 is None else x0
    y0 = -0.5 * n * cell if y0 is None else y0
    c = (np.arange(n) + 0.5) * cell
    X, Y = np.meshgrid(x0 + c, y0 + c)
    return X, Y, types.SimpleNamespace(x0=x0, y0=y0, cell=cell, n=n, band=16, index=0, xy=lambda: (X, Y),
                                       index_of=lambda x, y: ((x - x0) / cell - 0.5, (y - y0) / cell - 0.5))


def test_walkers():
    n, cell = 256, 10.0
    X, Y, _ = grid(n, cell)
    h = 2000.0 - 0.03 * Y + 6.0 * V.fbm(X, Y, 600.0, 4, octaves=3)
    a = V.lava_walkers(h, cell, (128, 40), 300, 2000.0, 1.0, seed=7, salt=3, dh_rel=1.5, pond_m=15.0)
    b = V.lava_walkers(h, cell, (128, 40), 300, 2000.0, 1.0, seed=7, salt=3, dh_rel=1.5, pond_m=15.0)
    c = V.lava_walkers(h, cell, (128, 40), 300, 2000.0, 1.0, seed=8, salt=3, dh_rel=1.5, pond_m=15.0)
    check('lava walkers: deterministic per seed (same seed and salt: identical to the bit; another seed differs)',
          np.array_equal(a, b) and not np.array_equal(a, c),
          f'max |a - b| {np.abs(a - b).max():.1e}, cells differing for another seed {int((a != c).sum())}')
    from eidoblend.terrain.solvers.hillslope import gaussian_blur
    g = gaussian_blur(h, 0.5 * 600.0 / cell)
    P = V.lava_walkers(g, cell, (128, 40), 400, 2000.0, 2.5, seed=1, salt=0, dh_rel=1.5, pond_m=15.0)
    jj, ii = np.nonzero(P > 0.01)
    run = (jj.max() - 40) * cell
    check('lava flow on a gentle bumpy plateau: the walkers run downhill (north) most of their length, no puddle',
          run > 1200.0, f'the paths reach {run:.0f} m north of the vent (length 2000 m)')
    T, F = V.lava_surface(P, cell, 15.0, X, Y, 0.01, None, 0.3, 0.0, 0.0, 3, width_m=400.0)
    rows = np.nonzero(F.max(axis=1) > 0.5)[0]
    width = float(np.median((F > 0.5).sum(axis=1)[rows])) * cell
    s = C.slope_deg(T, cell)
    top = F > 0.98
    edge = (F > 0.2) & (F < 0.8)
    check('lava flow: a tongue (long; the asked width about the walkers\' spread), level-topped, steep margins',
          (rows.max() - rows.min()) * cell > 2.0 * width and 200.0 < width < 1000.0
          and float(np.percentile(s[top], 50)) < 6.0 and float(np.percentile(s[edge], 50)) > 20.0,
          f'length {(rows.max() - rows.min()) * cell:.0f} m, width {width:.0f} m (asked 400), top slope p50 '
          f'{np.percentile(s[top], 50):.1f} deg, margin slope p50 {np.percentile(s[edge], 50):.1f} deg')


def test_lakes():
    n, cell = 200, 5.0
    X, Y, lv = grid(n, cell)
    base = 100.0 - 0.01 * Y
    r1 = np.hypot(X + 200.0, Y)
    crater = np.where(r1 < 120.0, -40.0 * (1.0 - (r1 / 120.0) ** 2), 0.0)       # a 40 m deep bowl
    r2 = np.hypot(X - 220.0, Y - 150.0)
    basin = np.where(r2 < 150.0, -25.0 * (1.0 - (r2 / 150.0) ** 2), 0.0)       # a broad 25 m basin
    pits = -2.0 * (np.hypot(X - 100.0, Y + 250.0) < 12.0)                         # a 2 m pit
    h = (base + crater + basin + pits).astype(np.float32)
    f = {'h': h.copy(), 'deposit': np.zeros_like(h)}
    V.op_volcano_lakes(f, lv, dict(dry=[dict(at=(-200.0, 0.0), radius_m=130.0)], min_depth_m=5.0), 1)
    w = f['water']
    dh = f['h'] - h
    check('lakes: a dry crater keeps its depression and holds no water; a real basin holds a lake; a 2 m pit fills',
          float(w[r1 < 100.0].max()) == 0.0 and float(dh[r1 < 100.0].max()) == 0.0
          and float(w[r2 < 60.0].min()) > 5.0 and float(dh[np.hypot(X - 100.0, Y + 250.0) < 10.0].min()) > 1.5,
          f'crater water {w[r1 < 100.0].max():.1f} m, fill {dh[r1 < 100.0].max():.1f} m; basin water '
          f'{w[r2 < 60.0].min():.1f}-{w[r2 < 60.0].max():.1f} m; pit filled {dh[np.hypot(X - 100, Y + 250) < 10].min():.2f} m')
    f2 = {'h': h.copy(), 'deposit': np.zeros_like(h)}
    V.op_volcano_lakes(f2, lv, dict(dry=[dict(at=(-200.0, 0.0), radius_m=130.0, playa_frac=0.3)],
                                    mode='sediment'), 1)
    flat = (C.slope_deg(f2['h'].astype(np.float64), cell) < 1.5)[r1 < 125.0]
    bowl = (h[r1 < 125.0] < (base[r1 < 125.0] - 0.05))
    frac = float((flat & bowl).sum()) / max(float(bowl.sum()), 1.0)
    check('lakes: a playa crater floor is filled flat over about the asked 30 % of the bowl; mode sediment fills '
          'the basin', 0.22 < frac < 0.38 and float(f2['water'].max()) == 0.0
          and float((f2['h'] - h)[r2 < 60.0].min()) > 5.0,
          f'flat floor {frac:.2f} of the bowl, water {f2["water"].max():.1f} m')


def test_caldera_lake():
    n, cell = 256, 40.0
    X, Y, lv = grid(n, cell)
    edifice = V.stratovolcano(X, Y, height_m=1600.0, radius_m=20000.0, upper_slope_deg=17.0,
                              crater_radius_m=300.0)['height']
    out = V.caldera_collapse(X, Y, edifice, (0.0, 0.0), 4500.0, float(np.mean(edifice[np.abs(np.hypot(X, Y) - 4500.0)
                                                                                     < cell])), 0.0)
    rim = float(np.mean(edifice[np.abs(np.hypot(X, Y) - 4500.0) < cell]))
    floor = rim - 980.0
    out = V.caldera_collapse(X, Y, edifice, (0.0, 0.0), 4500.0, rim, floor, scallops=6, scallop_amp=0.06)
    f = {'h': out['height'].astype(np.float32), 'deposit': np.zeros((n, n), np.float32),
         'caldera_rim_m': np.full((n, n), rim, np.float32)}
    V.op_caldera_lake(f, lv, dict(below_rim_m=389.0, centre=(0.0, 0.0)), 1)
    lake = rim - 389.0
    s = C.slope_deg(f['h'] + f['water'], cell)
    R = np.hypot(X, Y)
    wall = (R > 3000.0) & (R < 4600.0)
    buried = float((f['h'] - out['height'])[wall & (f['water'] < 0.01)].max())
    check('caldera lake: the lake at its own level, the walls above it left standing (not filled to the notch)',
          abs(float(np.median((f['h'] + f['water'])[f['water'] > 0.01])) - lake) < 1.0 and buried < 1.0
          and float(np.percentile(s[wall], 99.5)) < 70.0,
          f'lake {np.median((f["h"] + f["water"])[f["water"] > 0.01]):.1f} m (asked {lake:.1f}); fill on the dry '
          f'walls up to {buried:.2f} m; wall slope p99.5 {np.percentile(s[wall], 99.5):.1f} deg')


def test_islands():
    n, cell = 300, 10.0
    X, Y, _ = grid(n, cell)
    floor = 0.0
    ground = np.full(X.shape, floor)
    p = V.CRATER_LAKE
    cones = [dict(c, at=(c['at'][0] - p['centre'][0] + 2950.0, c['at'][1] - p['centre'][1] + 280.0))
             for c in p['inner_cones']]
    h = V.stack_piles(ground, X, Y, cones, floor)
    plat = float(cones[0]['width_m'] * cones[0]['hw_ratio'])
    top = float(h.max())
    check("islands: the cinder cone stands on its lava platform (Wizard Island: 230 m above the platform's top)",
          top > floor + plat + 150.0, f'platform top {floor + plat:.0f} m, island summit {top:.0f} m')


def test_apron():
    n, cell = 256, 40.0
    X, Y, lv = grid(n, cell)
    R = np.hypot(X, Y)
    # a range ring 2.5-4 km out with a valley behind its crest, below the plain
    ring = 600.0 * np.exp(-((R - 3200.0) / 500.0) ** 2)
    behind = np.where(R > 3600.0, -200.0 * np.exp(-((R - 4300.0) / 350.0) ** 2), 0.0)
    h = (ring + behind).astype(np.float32)
    f = {'h': h.copy(), 'deposit': np.zeros_like(h)}
    params = dict(plain_m=100.0, plain_blend_m=10.0, basin_m=2000.0)
    from eidoblend.terrain.solvers import fluvial as FL
    ctx = types.SimpleNamespace(device=FL.device('twin'), pins=None, prepass=None, shared={}, log=print)
    V.op_volcano_plain(f, lv, params, 1, ctx=ctx)
    inside = float(np.median(f['h'][R < 2000.0]))
    back = float(np.max((f['h'] - h)[(R > 4100.0) & (R < 4500.0)]))
    check('apron: the plain fills the low ground the vent reaches, not the valley behind the range crest',
          abs(inside - 100.0) < 15.0 and back < 0.5,
          f'inside the ring {inside:.1f} m (plain 100 m); behind the crest raised by {back:.2f} m')


def main():
    t0 = time.time()
    for t in (test_walkers, test_lakes, test_caldera_lake, test_islands, test_apron):
        t()
    bad = [r for r in RESULTS if not r[0]]
    print(f'{len(RESULTS) - len(bad)} of {len(RESULTS)} checks pass; {time.time() - t0:.1f} s')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
