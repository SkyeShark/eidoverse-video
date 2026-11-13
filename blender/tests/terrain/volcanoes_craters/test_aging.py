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
  aa flows       (the review's fixes) margins and front steep, full thickness at the cone's foot and none on the cone,
                 levees above the channel, a compound flow's units spreading in lobes
  lake limits    (the review's fixes) at most max_lakes, the largest; none beyond lake_radius_m; none over
                 max_area_m2
  caldera notch  (the review's fixes) a valley cut back through the rim below the lake's asked level: the lake
                 stands under the notch and stays in the caldera
  closed basin   (second pass) a crater's drainage routed with the crater kept a sink (basins_kept): nothing pours
                 over its rim (routed over its filled surface, the whole catchment did, and cut a breach)
  streaks        (second pass) radial_streaks: unit RMS in range, gone beyond it, no seam, running downslope
  breaches       (second pass) cinder cones breached toward the ground's downhill azimuth, the field unchanged
  outline        (second pass) the caldera's polygon and embayments: a few bights, a less round rim, the same floor
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


def test_aa_flows():
    """The review's fixes (2026-11-12): an aa flow's steep front and margins, broad levees, full thickness at its
    vent, and a compound flow's lobes."""
    n, cell = 640, 9.765625
    X, Y, lv = grid(n, cell, -3125.0, -1500.0)
    ground = 2000.0 - 0.025 * Y + 4.0 * V.fbm(X, Y, 1200.0, 5, octaves=4)
    cone = dict(at=(0.0, 0.0), width_m=1420.0, hw_ratio=0.188, crater_ratio=0.26, flank_deg=28.0, crest_round_m=6.0)
    i0, j0 = int(3125.0 / cell), int(1500.0 / cell)
    h0 = V.piles_on(ground, X, Y, [cone], [float(ground[j0, i0])])
    vent = dict(at=[0.0, 730.0], length_m=6000.0, thickness_m=22.0, age=0.05, dh_m=2.5, width_m=900.0, walkers=600)
    shape = dict(dh_factor=0.25, front_deg=35.0, levee=0.3, levee_frac=0.1, rough=0.0, stop_spread=0.3,
                 front_spread=1.0, vent_taper=0.0, no_climb=True)
    out = {}
    for units in (1, 5):
        f = {'h': h0.astype(np.float32), 'bed': h0.astype(np.float32)}
        V.op_lava_flows(f, lv, dict(shape, vents=[dict(vent)], units=units), 1)
        out[units] = (f['h'].astype(np.float64) - h0, f['lava'].astype(np.float64))
    T, F = out[1]
    s = C.slope_deg(h0 + T, cell)
    edge = (F > 0.2) & (F < 0.75)
    near = np.hypot(X, Y - 900.0) < 120.0                       # just beyond the cone's foot, on the flow's axis
    inner = (F > 0.9) & (np.abs(X) < 120.0) & (Y > 2000.0) & (Y < 3000.0)
    margin_top = float(np.percentile(T[(F > 0.9) & (F < 0.97)], 75)) if ((F > 0.9) & (F < 0.97)).any() else 0.0
    check('aa flow: rubble margins standing steep (35 degrees asked; the old soft margin was a 7-15 degree ramp), '
          'full thickness at the cone\'s foot, levees above the channel',
          float(np.median(s[edge])) > 30.0 and float(np.median(T[near])) > 0.8 * 22.0
          and margin_top > float(np.median(T[inner])) + 1.0,
          f'margin slope p50 {np.median(s[edge]):.1f} deg; thickness at the foot {np.median(T[near]):.1f} m (22); '
          f'levee {margin_top:.1f} m over a channel of {np.median(T[inner]):.1f} m')
    climbed = float(T[np.hypot(X, Y) < 500.0].max())
    check('aa flow: none of it on the cone it left', climbed < 0.5, f'lava on the cone\'s flanks up to {climbed:.2f} m')
    a1, a5 = float((out[1][1] > 0.5).sum()), float((out[5][1] > 0.5).sum())
    check('aa flow: a compound flow (five units) spreads in lobes beside and beyond the first', a5 > 1.25 * a1,
          f'footprint {a1 * cell * cell / 1e6:.2f} km2 with one unit, {a5 * cell * cell / 1e6:.2f} km2 with five')


def test_caldera_lake_notch():
    """The review's fixes (2026-11-12): a valley cut back through the rim below the asked lake level: the lake stands
    under that notch and stays in the caldera (it ran out over the flank)."""
    n, cell = 256, 40.0
    X, Y, lv = grid(n, cell)
    edifice = V.stratovolcano(X, Y, height_m=1600.0, radius_m=20000.0, upper_slope_deg=17.0,
                              crater_radius_m=300.0)['height']
    rim = float(np.mean(edifice[np.abs(np.hypot(X, Y) - 4500.0) < cell]))
    out = V.caldera_collapse(X, Y, edifice, (0.0, 0.0), 4500.0, rim, rim - 980.0, scallops=6, scallop_amp=0.06)
    h = out['height'].copy()
    ax = (np.abs(X) < 150.0) & (Y > 3000.0)                      # a valley north through the rim, 500 m under it
    h = np.where(ax, np.minimum(h, rim - 500.0 - 0.01 * (Y - 3000.0)), h)
    f = {'h': h.astype(np.float32), 'deposit': np.zeros((n, n), np.float32),
         'caldera_rim_m': np.full((n, n), rim, np.float32), 'caldera_floor': out['floor'].astype(np.float32)}
    V.op_caldera_lake(f, lv, dict(below_rim_m=389.0, centre=(0.0, 0.0)), 1)
    wet_out = float(f['water'][np.hypot(X, Y) > 5200.0].max())
    level = float(np.median((f['h'] + f['water'])[f['water'] > 0.01]))
    check('caldera lake: under a notch cut below its asked level, the lake stands under the notch and stays inside',
          wet_out == 0.0 and level < rim - 500.0 and abs(float(np.median(f['caldera_lake_m'])) - level) < 0.5,
          f'lake at {level - rim:.0f} m under the rim (asked -389, the notch -500 and falling outward); water beyond '
          f'the rim {wet_out:.1f} m')


def test_lake_limits():
    n, cell = 256, 50.0
    X, Y, lv = grid(n, cell)
    h = np.full(X.shape, 500.0)
    basins = [((-3000.0, 0.0), 900.0), ((3000.0, 0.0), 700.0), ((0.0, 3000.0), 600.0), ((0.0, -3000.0), 500.0),
              ((-4500.0, 4500.0), 1500.0), ((4500.0, -4500.0), 400.0)]
    for (bx, by), rb in basins:
        r = np.hypot(X - bx, Y - by)
        h = h + np.where(r < rb, -30.0 * (1.0 - (r / rb) ** 2), 0.0)
    f = {'h': h.astype(np.float32), 'deposit': np.zeros(X.shape, np.float32)}
    V.op_volcano_lakes(f, lv, dict(min_depth_m=5.0, min_area_m2=1.0e5, max_area_m2=5.0e6, max_lakes=3,
                                   lake_radius_m=5000.0, centre=(0.0, 0.0)), 1)
    wet = [bool(f['water'][np.hypot(X - bx, Y - by) < 0.3 * rb].max() > 1.0) for (bx, by), rb in basins]
    check('lakes: at most max_lakes, the largest that qualify; none beyond lake_radius_m (filled with sediment); a '
          'basin over max_area_m2 filled', wet == [True, True, True, False, False, False]
          and float((f['h'] - h)[np.hypot(X + 4500.0, Y - 4500.0) < 300.0].min()) > 20.0,
          f'water in the six basins (0.9, 0.7, 0.6, 0.5 km radius near; 1.5 km too big; 0.4 km beyond the reach): '
          f'{wet}')


def test_closed_basin():
    """The review's fixes, second pass (2026-11-12): a closed crater's drainage is routed with the crater a sink
    (basins_kept), not over its surface filled to the spill, which poured the whole crater's catchment over the rim's
    lowest point and cut a breach there (Meteor Crater's seed 1, south-west rim)."""
    from eidoblend.terrain.solvers import hydro as HY
    n, cell = 200, 10.0
    X, Y, _ = grid(n, cell)
    R = 500.0
    r = np.hypot(X, Y)
    rim = 20.0 + 6.0 * np.cos(np.arctan2(X, Y) - 0.6)              # the rim lowest toward one side
    h = 100.0 - 0.01 * Y + np.where(r < R, rim - 120.0 * (1.0 - (r / R) ** 2), rim * np.exp(-((r - R) / 300.0) ** 2))
    h = h + 0.4 * V.fbm(X, Y, 60.0, 3, octaves=2)                   # small pits everywhere
    filled = HY.fill_depressions(h)[0]
    kept = V.basins_kept(h, filled, 1.0)
    ring = np.abs(r - R) < 1.5 * cell
    A = {}
    for name, s in (('filled', filled), ('kept', kept)):
        rec, w, term = HY.route(HY.routing_surface(s), method='d8')
        A[name] = HY.accumulate(rec, w, term).reshape(h.shape) * cell * cell
    crater = float(np.pi * R * R)
    shallow = (filled - h > 1e-4) & (r > 1.3 * R)
    check('closed basin: routed with the crater kept a sink, no drainage pours over its rim (filled to the spill, the '
          "whole crater's catchment did); the plain's shallow pits are still filled",
          float(A['filled'][ring].max()) > 0.5 * crater and float(A['kept'][ring].max()) < 0.05 * crater
          and np.array_equal(kept[shallow], filled[shallow]) and float((kept - h)[r < 0.5 * R].max()) < 1e-6,
          f"largest area crossing the rim: {A['filled'][ring].max() / crater:.2f} of the crater filled, "
          f"{A['kept'][ring].max() / crater:.3f} kept")


def test_radial_streaks():
    """Radial streaks (the gullies' seed on a cone or a crater wall): unit RMS inside their radius range, fading out
    beyond it, continuous across north (periodic in azimuth: no seam), running downslope (far more variation round the
    cone than along a radius)."""
    n, cell = 400, 50.0
    X, Y, _ = grid(n, cell)
    s = V.radial_streaks(X, Y, (0.0, 0.0), (40, 160), 0.6, (1000.0, 8000.0), 3, 7)
    r = np.hypot(X, Y)
    inside, outside = (r > 2000.0) & (r < 6000.0), r > 11400.0          # faded out half a band (x 2^0.5) beyond 8 km
    a = np.radians(np.linspace(-179.0, 179.0, 4000))
    ring = V.radial_streaks(3000.0 * np.sin(a), 3000.0 * np.cos(a), (0.0, 0.0), (40, 160), 0.6, (1000.0, 8000.0), 3, 7)
    # the seam: two points 0.002 degrees apart across south (azimuth +-180) against the same step elsewhere
    pair = np.radians(np.array([179.999, -179.999, 90.0, 90.002]))
    pv = V.radial_streaks(3000.0 * np.sin(pair), 3000.0 * np.cos(pair), (0.0, 0.0), (40, 160), 0.6,
                          (1000.0, 8000.0), 3, 7)
    seam = abs(float(pv[0] - pv[1])) / max(abs(float(pv[2] - pv[3])), 1e-3)
    rr = np.linspace(2000.0, 6000.0, 400)
    line = V.radial_streaks(np.zeros_like(rr), rr, (0.0, 0.0), (40, 160), 0.6, (1000.0, 8000.0), 3, 7)
    along = float(np.mean(np.abs(np.diff(line)))) / (rr[1] - rr[0])
    across = float(np.mean(np.abs(np.diff(ring)))) / (3000.0 * (a[1] - a[0]))
    check('radial streaks: unit RMS in their range, gone beyond it, no seam at azimuth 180, running down the cone',
          0.7 < float(np.std(s[inside])) < 1.3 and float(np.abs(s[outside]).max()) < 1e-6 and seam < 3.0
          and across > 10.0 * along,
          f'RMS {np.std(s[inside]):.2f} inside, {np.abs(s[outside]).max():.1e} beyond; the step across the seam '
          f'{seam:.2f} x an ordinary step; change per metre across / along {across / max(along, 1e-12):.0f}')


def test_breach_toward():
    """Cinder cones breached toward the ground's downhill azimuth (breach_toward_deg); the field's cones otherwise
    the same (their own seeds draw the direction)."""
    base = dict(window=(-5000.0, -5000.0, 10000.0), count=17, width_m=(330.0, 1400.0), breach_fraction=0.4,
                vent_lines=3, line_spread_m=1400.0, seed=4)
    a = V.cinder_field(**base)
    b = V.cinder_field(**base, breach_toward_deg=25.0, breach_spread_deg=50.0)
    same = all(ca['at'] == cb['at'] and ca['width_m'] == cb['width_m'] for ca, cb in zip(a, b)) and len(a) == len(b)
    off = [abs((cb['breach_azimuth_deg'] - 25.0 + 180.0) % 360.0 - 180.0) for cb in b if 'breach_azimuth_deg' in cb]
    check('cinder field: breaches open within 50 degrees of the downhill azimuth; the cones are where they were',
          bool(same and off and max(off) <= 50.0 + 1e-9),
          f'{len(off)} breached, the furthest {max(off or [0]):.0f} degrees off downhill; cones unchanged: {same}')


def test_caldera_outline():
    """The caldera's outline (the review's 'pie-crust' rim, then a lobed cloud): a rounded polygon with a few
    embayments (embayment_outline: zero mean, a few bights, the ring between them untouched) in place of scallops."""
    a = np.radians(np.arange(0.0, 360.0, 0.25))
    e = V.embayment_outline(a, 3, (0.04, 0.09), (18.0, 38.0), 5)
    raised = e > float(np.min(e)) + 0.005
    bights = int(np.sum(raised[1:] & ~raised[:-1]) + (1 if (raised[0] and not raised[-1]) else 0))
    bays_ok = abs(float(np.mean(e))) < 1e-3 and bights in (2, 3)          # two may merge into one broader bight
    n, cell = 300, 40.0
    X, Y, _ = grid(n, cell)
    edifice = V.stratovolcano(X, Y, height_m=1600.0, radius_m=20000.0, upper_slope_deg=17.0,
                              crater_radius_m=300.0)['height']
    rim = float(np.mean(edifice[np.abs(np.hypot(X, Y) - 4700.0) < cell]))
    kw = dict(scallops=0, radius_noise=0.0, edge_noise=0.0, elongation=1.2, elongation_azimuth_deg=72.0, seed=3)
    plain = V.caldera_collapse(X, Y, edifice, (0.0, 0.0), 4700.0, rim, rim - 980.0, **kw)
    shaped = V.caldera_collapse(X, Y, edifice, (0.0, 0.0), 4700.0, rim, rim - 980.0,
                                polygon=dict(sides=5, strength=0.5, azimuth_deg=15.0, roundness=0.1),
                                embayments=dict(count=3, amp=[0.04, 0.09], width_deg=[18.0, 38.0]), **kw)
    sd = []
    for out in (plain, shaped):
        _az, rr, _z = C.rim_crests(out['height'], X, Y, (0.0, 0.0), 2500.0, 7500.0, 5.0)
        fl = out['floor'] > 0.5
        sd.append((float(np.std(rr)), float(np.sqrt(fl.sum() * cell * cell / np.pi))))
    check('caldera outline: a few embayments (zero mean, the ring between them untouched); the polygon and bays make '
          'the rim less round than the plain oval, the floor keeping its size',
          bays_ok and sd[1][0] > sd[0][0] and abs(sd[1][1] / sd[0][1] - 1.0) < 0.05,
          f'{bights} bights, mean {np.mean(e):.1e}; rim radius s.d. {sd[0][0]:.0f} m (oval) -> {sd[1][0]:.0f} m; '
          f'floor radius {sd[0][1]:.0f} -> {sd[1][1]:.0f} m')


def test_furrows():
    """The review's fixes, third pass (2026-11-13): the gullies' seed as sparse wandering furrows (radial_streaks
    sparse, wander_m) and the cone's erodibility gathered into them (furrow_k_factor). Seeded by straight radial
    streaks with K alike everywhere, the cone came out a sunburst of straight spokes, a washboard from the foot."""
    kw = dict(k_range=(20, 90), decay=0.5, r_range_m=(1000.0, 8000.0), bands=3, seed=5)
    a = np.radians(np.arange(0.0, 360.0, 0.05))
    lags = {}
    for wm in (0.0, 150.0):
        rings = [V.radial_streaks(r * np.sin(a), r * np.cos(a), (0.0, 0.0), wander_m=wm, wander_scale_m=1500.0, **kw)
                 for r in (3000.0, 3400.0)]
        # per 45-degree sector, the shift (degrees) that best matches the outer ring's pattern to the inner one's
        out = []
        for s0 in range(8):
            sl = slice(s0 * a.size // 8, (s0 + 1) * a.size // 8)
            u, v = rings[0][sl] - rings[0][sl].mean(), rings[1][sl] - rings[1][sl].mean()
            best = max(range(-60, 61), key=lambda k: float(np.dot(u[60:-60], np.roll(v, k)[60:-60])))
            out.append(abs(best) * 0.05)
        lags[wm] = out
    # (without wander the two rings differ only by their bands' mix: shifts under a quarter degree)
    straight = max(lags[0.0]) <= 0.25
    bends = sum(1 for d in lags[150.0] if d >= 1.0) >= 3
    sp = V.radial_streaks(4000.0 * np.sin(a), 4000.0 * np.cos(a), (0.0, 0.0), sparse=0.6, **kw)
    full = V.radial_streaks(4000.0 * np.sin(a), 4000.0 * np.cos(a), (0.0, 0.0), **kw)
    share, expect = float(np.mean(sp < 0.0)), float(np.mean(full < -0.6))
    check('furrows: wander bends the streaks down the cone (straight spokes without it); sparse keeps only the '
          'troughs, the planes between them at 0',
          straight and bends and float(sp.max()) <= 0.0 and abs(share - expect) < 1e-9 and 0.1 < share < 0.45,
          f'shift between rings 3.0 and 3.4 km per sector: straight {max(lags[0.0]):.2f} deg, wandering '
          f'{", ".join(f"{d:.2f}" for d in lags[150.0])} deg; furrows over {share:.2f} of the ring')
    n, cell = 300, 40.0
    X, Y, lv = grid(n, cell)
    p = dict(V.AGE_DEFAULTS, centre=(0.0, 0.0), seed_streaks=[
        dict(amp_m=4.0, k=[20, 90], decay=0.5, r_m=[1000.0, 4000.0], bands=3, wander_m=100.0, sparse=0.6,
             k_floor=0.15)])
    fk = V.furrow_k_factor(lv, p, 3)
    r = np.hypot(X, Y)
    on = (r > 1500.0) & (r < 3500.0)
    fur = V._streak_set(lv, (0.0, 0.0), p['seed_streaks'][0], 3, 0) < -0.6
    check('furrows: the erodibility gathered into the furrows (k_floor on the planes between), alike beyond the '
          "furrows' reach", float(fk.min()) >= 0.15 - 1e-9 and float(np.median(fk[on & fur])) > 0.8
          and float(np.median(fk[on & ~fur])) < 0.5 and float(fk[r > 5300.0].min()) > 1.0 - 1e-6
          and V.furrow_k_factor(lv, dict(V.AGE_DEFAULTS), 3) is None,
          f'K factor in the furrows {np.median(fk[on & fur]):.2f}, between them {np.median(fk[on & ~fur]):.2f}, '
          f'beyond 5.3 km {fk[r > 5300.0].min():.2f}')


def test_flow_bury_spread():
    """The review's fixes, third pass: a flow fills the gullies it runs over (bury: they printed through its top as
    stripes) and spreads where the ground levels out (spread_slope_deg: at one width all the way it ran as a
    straight-sided ribbon)."""
    n, cell = 320, 12.5
    X, Y, lv = grid(n, cell, -2000.0, -500.0)
    # a flank at 12 degrees for 1.5 km, easing to a 2-degree plain, with gullies 6 m deep every 150 m running down it
    yy = Y + 500.0
    t12, t2 = math.tan(math.radians(12.0)), math.tan(math.radians(2.0))
    base = 1500.0 - np.where(yy < 1500.0, t12 * yy, t12 * 1500.0 + t2 * (yy - 1500.0))
    ground = base - 6.0 * (0.5 + 0.5 * np.cos(2.0 * math.pi * X / 150.0)) ** 4
    vent = dict(at=[0.0, -400.0], length_m=3200.0, thickness_m=12.0, age=0.0, dh_m=1.5, width_m=500.0, walkers=500)
    shape = dict(dh_factor=0.25, front_deg=35.0, levee=0.0, levee_frac=0.1, rough=0.0, stop_spread=0.0,
                 front_spread=0.0, vent_taper=0.0, no_climb=False, units=1)
    out = {}
    for name, extra in (('plain', {}), ('bury+spread', dict(bury=True, spread_slope_deg=6.0))):
        f = {'h': ground.astype(np.float32), 'bed': ground.astype(np.float32)}
        V.op_lava_flows(f, lv, dict(shape, vents=[dict(vent)], **extra), 2)
        out[name] = (f['h'].astype(np.float64), f['lava'].astype(np.float64))
    h1, F1 = out['bury+spread']
    h0, _F0 = out['plain']
    core = (F1 > 0.95) & (yy > 300.0) & (yy < 2400.0)

    def across(hh, m):
        # the surface's relief across the flow: each row's range within the flow's core (the slope along it is
        # the same across a row)
        vals = [float(np.ptp(hh[j][m[j]])) for j in range(n) if m[j].sum() > 8]
        return float(np.median(vals)) if vals else float('nan')
    ground_relief = across(ground, core)
    rows = yy[:, 0]
    w_steep = float(np.median([(F1[j] > 0.5).sum() for j in range(n) if 300.0 < rows[j] < 900.0])) * cell
    w_flat = float(np.median([(F1[j] > 0.5).sum() for j in range(n) if 2000.0 < rows[j] < 2400.0])) * cell
    check('lava flow: buried gullies (the flow top level across, the ground under it gullied); wider where the '
          'ground levels out', across(h1, core) < 0.35 * ground_relief and across(h0, core) > 0.6 * ground_relief
          and w_flat > 1.3 * w_steep,
          f'relief across the flow: ground {ground_relief:.1f} m, flow top {across(h1, core):.1f} m buried, '
          f'{across(h0, core):.1f} m without; width {w_steep:.0f} m on the 12-degree flank, {w_flat:.0f} m on the plain')


def test_lava_rubble():
    """The review's fixes, third pass: the flows' clinker on the fine levels (lava_rubble): only where the lava field
    lies, into h and bed, and on a parent and its x2 child the inherited rubble plus the child's own finer detail
    equal the rubble at the child's cells (a world function: no stacking, no seam)."""
    from eidoblend.terrain.core.fields import Fields
    from eidoblend.terrain.core.levels import Level
    parent = Level(0, 'hero', -256.0, -256.0, 512.0, 2.0, 256)
    child = Level(1, 'hero', -128.0, -128.0, 256.0, 1.0, 256, parent=0)
    Xp, Yp = parent.xy()
    lava = np.clip((200.0 - np.hypot(Xp - 40.0, Yp)) / 40.0, 0.0, 1.0).astype(np.float32)   # a flow 400 m across
    base = (500.0 + 0.02 * Yp).astype(np.float32)
    prm = dict(scales_m=[8.0, 3.0, 1.2], amps_m=[1.2, 0.6, 0.3])
    fp = Fields(parent, {'h': base, 'bed': base, 'lava': lava})
    V.OPS['lava_rubble'](fp, parent, prm, 5)
    add_p = fp['h'] - base
    off = add_p[lava == 0.0]
    on = add_p[lava >= 1.0]
    fc = fp.inherit(child)
    V.OPS['lava_rubble'](fc, child, prm, 5)
    Xc, Yc = child.xy()
    gc = Fields(parent, {'h': base, 'bed': base, 'lava': lava}).inherit(child)
    want = gc['h'] + np.clip(1.6 * gc['lava'], 0.0, 1.0) * V.lava_rubble(Xc, Yc, prm['scales_m'], prm['amps_m'], 5)
    inner = np.clip(1.6 * gc['lava'], 0.0, 1.0) >= 1.0
    err = float(np.abs(fc['h'] - want)[inner].max())
    check('lava rubble: clinker 1-8 m only on the flow, rock (h and bed); on a parent and child the same world '
          'function (inherited + the finer detail)', float(np.abs(off).max()) == 0.0 and 0.3 < float(np.ptp(on)) < 4.0
          and np.array_equal(fp['h'], fp['bed']) and err < 0.25,
          f'relief on the flow {np.ptp(on):.2f} m, off it {np.abs(off).max():.2f} m; child vs direct within the flow: '
          f'max {err:.3f} m (Catmull-Rom of the parent\'s rubble)')


def test_cone_rills():
    """The review's fixes, third pass: rills down a cinder cone's flanks (cone_rills): on the flank only (the rim and
    the toe's break untouched), about the asked spacing apart, fainter on an old cone, cut into the scoria (not below
    bed), the same world function on a parent and its child."""
    from eidoblend.terrain.core.fields import Fields
    from eidoblend.terrain.core.levels import Level
    cone = dict(at=(0.0, 0.0), width_m=1420.0, hw_ratio=0.188, crater_ratio=0.26, flank_deg=28.0, crest_round_m=6.0,
                seed=3)
    parent = Level(0, 'hero', -800.0, -800.0, 1600.0, 4.0, 400)
    child = Level(1, 'hero', -400.0, -800.0, 800.0, 2.0, 400, parent=0)
    Xp, Yp = parent.xy()
    base = (2000.0 + V.cinder_cone(Xp, Yp, **cone)).astype(np.float32)
    prm = dict(cones=[dict(cone)], depth_m=1.5, spacing_m=25.0)
    fp = Fields(parent, {'h': base, 'bed': np.full_like(base, 2000.0)})
    V.OPS['cone_rills'](fp, parent, prm, 2)
    cut = base - fp['h']
    r = np.hypot(Xp, Yp)
    rim, toe, flank = r < 0.26 * 710.0 * 1.1, r > 715.0, (r > 300.0) & (r < 520.0)
    a = np.radians(np.arange(0.0, 360.0, 0.05))
    ring = V.cone_rills(410.0 * np.sin(a), 410.0 * np.cos(a), [dict(cone)], 1.5, 25.0, 2)
    on = ring > 0.2
    n_rills = int(np.sum(on & ~np.roll(on, 1)))
    old = V.cone_rills(410.0 * np.sin(a), 410.0 * np.cos(a), [dict(cone, kappa_t_m2=600.0)], 1.5, 25.0, 2)
    fc = fp.inherit(child)
    V.OPS['cone_rills'](fc, child, prm, 2)
    Xc, Yc = child.xy()
    gc = Fields(parent, {'h': base, 'bed': np.full_like(base, 2000.0)}).inherit(child)
    want = gc['h'] - V.cone_rills(Xc, Yc, [dict(cone)], 1.5, 25.0, 2)
    err = float(np.abs(fc['h'] - want).max())
    spacing = 2.0 * math.pi * 410.0 / max(n_rills, 1)
    check('cone rills: on the flank only (rim and toe untouched), 15-60 m apart, fainter on an old cone, the same '
          'world function on a parent and child', float(cut[rim].max()) == 0.0 and float(cut[toe].max()) == 0.0
          and 0.8 < float(cut[flank].max()) <= 3.0 and 15.0 < spacing < 60.0 and float(old.max()) < 0.5 * float(ring.max())
          and err < 0.05,
          f'deepest on the flank {cut[flank].max():.2f} m, at the rim {cut[rim].max():.2f}, past the toe '
          f'{cut[toe].max():.2f}; {n_rills} rills round the 410 m ring ({spacing:.0f} m apart); an old cone\'s '
          f'deepest {old.max():.2f} m against {ring.max():.2f}; child vs direct {err:.3f} m')


def test_hero_pits():
    """The review's fixes, third pass: hero_pits 'keep' leaves a hero level's small hollows as they are (filled, they
    lay as dead-flat patches at the walker's feet); a main level still fills them."""
    n, cell = 200, 0.5
    X, Y, lv = grid(n, cell)
    h = 100.0 + 0.02 * Y + 0.15 * V.fbm(X, Y, 6.0, 9, octaves=2)          # a gentle slope with puddle-sized hollows
    out = {}
    for role in ('main', 'hero'):
        lv.role = role
        f = {'h': h.astype(np.float32), 'deposit': np.zeros(X.shape, np.float32)}
        V.op_volcano_lakes(f, lv, dict(min_depth_m=5.0, hero_pits='keep'), 1)
        out[role] = float(np.sum(f['h'] - h > 1e-3)) / h.size
    del lv.role
    check('lakes: a hero level keeps its own hollows with hero_pits keep, a main level fills them',
          out['hero'] == 0.0 and out['main'] > 0.01,
          f'filled: {out["main"]:.3f} of the main level, {out["hero"]:.3f} of the hero level')


def main():
    t0 = time.time()
    for t in (test_walkers, test_lakes, test_caldera_lake, test_islands, test_apron, test_aa_flows,
              test_caldera_lake_notch, test_lake_limits, test_closed_basin, test_radial_streaks, test_breach_toward,
              test_caldera_outline, test_furrows, test_flow_bury_spread, test_lava_rubble, test_cone_rills,
              test_hero_pits):
        t()
    bad = [r for r in RESULTS if not r[0]]
    print(f'{len(RESULTS) - len(bad)} of {len(RESULTS)} checks pass; {time.time() - t0:.1f} s')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
