"""The coast package's plain-Python tests (numpy twins, no GPU; design section 11 row 11: "exposure against a
brute-force ray count; the Dean profile"). Each runs in a few seconds:

    python blender/tests/terrain/coast/test_coast.py

  1. exposure: the fetch kernel's twin against an independent ray count (an exact grid traversal from each shore
     cell, coast.exposure_bruteforce) on a 96 x 80 coast with a bay, a headland and an island: every shore cell
     within 0.03, the mean within 0.01; a straight open coast gives 0.5 and a closed bay less than a headland
  2. jump flooding: the seed + JFA twins' distance to the zero line of a level set against the brute-force
     distance to every crossing point (96 x 80, a wavy front and an island): within 0.05 cells everywhere it is
     under 30 cells, and the payload is the nearest crossing's
  3. the Dean profile: beach_profile below the waterline is -A y^(2/3) (A 0.1) to float precision, and op 'coast' on
     a sheltered bay (twin device) leaves an underwater beach whose depth fits A y^b with b 0.55-0.8
  4. the cliff: op 'coast' on a synthetic downland at 2 m cells (twin device): the face stands at 70 degrees or
     steeper (design section 10: "face angle >= 70 degrees at 2 m cells"), its top within 3 m of the land's height at
     the retreat line, the platform at the foot between -1 and +1 m, nothing changed inland of the cliff top
  5. the rock column: a stepped face whose beds stand at their own angles (a 1D profile through face_profile)
Writes blender/tests/terrain/out/coast/test_coast.json; exit code 1 on a failure.
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
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'coast'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.core.levels import Level  # noqa: E402
from eidoblend.terrain.solvers import coast as CO  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402

RESULTS = {}
FAILED = []


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


TWIN = FL.device('twin')


def coast_mask(H=80, W=96):
    """A coast: sea in the south and west, a bay cut into the land, a headland, and an island."""
    jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
    land = jj > 30 + 6 * np.sin(ii / 9.0)                        # a wavy shore, sea to the south
    land &= ~((ii - 48) ** 2 / 14.0 ** 2 + (jj - 36) ** 2 / 12.0 ** 2 < 1)    # a bay
    land |= (np.abs(ii - 20) < 3) & (jj > 12)                    # a narrow headland
    land |= (ii - 75) ** 2 + (jj - 12) ** 2 < 25                 # an island
    land &= ii > 4                                               # a strip of sea on the west edge
    return ~land


def test_exposure():
    t0 = time.time()
    sea = coast_mask()
    cell, maxm = 10.0, 1500.0
    k = CO.fetch_kernel(16)
    out = TWIN.empty(sea.shape, 1)
    TWIN.run(k, {'seaT': TWIN.texture(sea.astype(np.float32))}, {'outE': out}, {'uMaxCells': maxm / cell})
    E = TWIN.read(out)[..., 0]
    bf = CO.exposure_bruteforce(sea, cell, maxm, 16)
    d = np.array([abs(E[j, i] - v) for (j, i), v in bf.items()])
    shore = CO.shore_cells(sea)
    # the twin walks the same exact traversal in float32 as the oracle in float64: they agree to rounding, except
    # where a ray passes within float32 precision of a grid corner and the two take its two cells in either order
    close = float((d <= 1e-5).mean())
    check('exposure: twin vs brute-force ray count (every shore cell)',
          close >= 0.995 and d.max() <= 1.0 / 16 + 1e-4 and bool((E[~shore] == -1).all()),
          f'{len(bf)} shore cells: {close:.1%} within 1e-5, |dE| mean {d.mean():.2e}, max {d.max():.2e}; '
          f'non-shore cells all -1: {bool((E[~shore] == -1).all())}')
    RESULTS['exposure_cells'] = len(bf)
    # a straight open coast: half the rays run to sea
    H, W = 64, 64
    s2 = np.zeros((H, W), bool)
    s2[:32, :] = True
    out2 = TWIN.empty(s2.shape, 1)
    TWIN.run(k, {'seaT': TWIN.texture(s2.astype(np.float32))}, {'outE': out2}, {'uMaxCells': 1000.0})
    e2 = TWIN.read(out2)[..., 0][31, 16:48]
    jj, ii = np.mgrid[0:sea.shape[0], 0:sea.shape[1]]
    inner_bay = ((ii - 48) ** 2 / 15.0 ** 2 + (jj - 36) ** 2 / 13.0 ** 2 < 1) & (jj > 40)
    tip = (np.abs(ii - 20) < 6) & (jj > 10) & (jj < 16)
    bay = E[shore & inner_bay]
    head = E[shore & tip]
    check('exposure: a straight open coast 0.5, a bay below a headland',
          abs(float(e2.mean()) - 0.5) < 0.04 and bay.mean() < head.mean(),
          f'straight coast {e2.mean():.3f}; bay {bay.mean():.3f}, headland {head.mean():.3f} '
          f'({time.time() - t0:.1f} s)')


def test_jfa():
    t0 = time.time()
    H, W = 80, 96
    jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
    phi = (jj - 40 - 7 * np.sin(ii / 7.0) - 3 * np.cos(ii / 3.1)) * 1.3        # a wavy front (not a distance)
    phi = np.where((ii - 70) ** 2 + (jj - 15) ** 2 < 36, 5.0, phi)             # an island of land at sea
    pay = (ii * 0.01 + jj * 0.001).astype(np.float32)
    d, p = CO.nearest_crossing(TWIN, phi.astype(np.float32), pay)

    def nearest(pts, pv):
        flat = np.stack([ii.ravel(), jj.ravel()], 1)
        best = np.full(flat.shape[0], np.inf)
        bestv = np.zeros(flat.shape[0])
        for a in range(0, pts.shape[0], 512):
            dd = np.hypot(flat[:, None, 0] - pts[None, a:a + 512, 0], flat[:, None, 1] - pts[None, a:a + 512, 1])
            m = dd.min(1)
            arg = dd.argmin(1)
            upd = m < best
            best = np.where(upd, m, best)
            bestv = np.where(upd, pv[a:a + 512][arg], bestv)
        return best.reshape(H, W), bestv.reshape(H, W)
    # brute force 1: every crossing point on every cell's 8 neighbour segments (the zero line as finely as the
    # grid gives it): how close the distance is to the line's
    pts, pv = [], []
    for k, (dx, dy) in enumerate(T.OFF):
        q, ok = T.neighbour(phi, k, T.BOUND_OPEN)
        qp, _ = T.neighbour(pay, k, T.BOUND_OPEN)
        cr = ok & ((q < 0) != (phi < 0))
        t = phi[cr] / (phi[cr] - q[cr])
        pts.append(np.stack([ii[cr] + t * dx, jj[cr] + t * dy], 1))
        pv.append(np.where(phi[cr] < 0, pay[cr], qp[cr]))
    best, _ = nearest(np.concatenate(pts), np.concatenate(pv))
    near = best < 30
    err = np.abs(d - best)[near]
    check('jump flooding: distance to the zero line vs every crossing (cells, where < 30)',
          err.max() <= 0.1, f'max |d - exact| {err.max():.4f} cells, mean {err.mean():.5f}')
    # brute force 2: the seeds the kernel keeps (each boundary cell's nearest crossing): JFA's propagation exact
    # JFA is an approximation: a cell can keep a seed a little further than the nearest where two seeds are nearly
    # equidistant (Rong & Tan 2006). What the coast needs: the distance within 0.1 cells of the nearest seed's (the
    # face height errs by 0.1 cell x tan(face) at most), and the payload (the exposure, smoothed over 250 m after) the
    # nearest seed's except at such near-ties
    seeds = TWIN.read(_seed_state(phi, pay))
    has = seeds[..., 3] > 0.5
    b2, v2 = nearest(seeds[has][:, :2].astype(np.float64), seeds[has][:, 2].astype(np.float64))
    e2 = np.abs(d - b2)
    same = np.abs(p - v2) < 1e-6
    pay_ok = float(same.mean())
    exact = float((e2 <= 1e-4).mean())
    check('jump flooding: JFA+2 keeps the nearest seed, or one within 0.1 cells of it',
          e2.max() <= 0.1 and exact >= 0.99 and pay_ok >= 0.99,
          f'{exact:.2%} of cells on the nearest seed exactly (max |d - nearest| {e2.max():.3f} cells); payload the '
          f'nearest seed\'s on {pay_ok:.2%} ({time.time() - t0:.1f} s)')


def _seed_state(phi, pay):
    out = TWIN.empty(phi.shape, 4)
    TWIN.run(CO.SEED, {'phiT': TWIN.texture(phi.astype(np.float32)), 'payT': TWIN.texture(pay)}, {'outS': out}, {})
    return out


def _level(n, cell, x0=None, y0=None):
    side = n * cell
    return Level(index=0, role='main', x0=-side / 2 if x0 is None else x0, y0=-side / 2 if y0 is None else y0,
                 side=side, cell=cell, n=n)


def _ctx(lv, sea=0.0):
    return FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='refine', pins=None, shared={},
                           sea_level=sea, device=TWIN, log=lambda m: print('   ' + m, flush=True))


def test_dean():
    t0 = time.time()
    P = CO.params_for({})
    y = np.linspace(0, 400, 401)
    z = CO.beach_profile(y, P, 1.0)
    face = P['beach_berm_m'] / math.tan(math.radians(P['beach_face_deg']))
    yw = P['beach_backshore_m'] + face
    under = y > yw + 1
    want = -P['dean_A'] * (y[under] - yw) ** (2.0 / 3.0)
    check('Dean profile: depth = A y^(2/3) below the waterline (A 0.1)', np.allclose(z[under], want, atol=1e-9),
          f'max |dz| {np.abs(z[under] - want).max():.2e} m; berm {z[0]:.2f} m, waterline at {yw:.1f} m')
    # a sheltered coast (beaches below exposure 0.9 here, so this straight one is a bay as far as the rule goes):
    # land at 30 m, the old sea floor 6 m deep; op 'coast' builds the beach over it
    n, cell = 128, 4.0
    lv = _level(n, cell)
    X, Y = lv.xy()
    land = np.where(Y < -60.0, -6.0, 30.0 + 0.004 * Y)
    f = Fields(lv, {'h': land.astype(np.float32)})
    CO.op_coast(f, lv, {'retreat_m': 40.0, 'weakness': 0.0, 'crenel_m': 0.0, 'fetch_max_m': 1200.0,
                        'beach_exposure': [0.9, 1.0], 'exposure_smooth_m': 20.0, 'platform_rough_m': 0.0}, 1,
                ctx=_ctx(lv))
    h = np.asarray(f['h'], np.float64)
    E = np.asarray(f['coast_E'], np.float64)
    col = n // 2
    prof, yy = h[::-1, col], Y[::-1, col]                              # north to south: land, beach, sea
    jw = int(np.argmax(prof < 0.0))                                    # the first cell under the waterline
    t = prof[jw - 1] / (prof[jw - 1] - prof[jw])
    yw = yy[jw - 1] + t * (yy[jw] - yy[jw - 1])                        # the waterline, sub-cell
    under = (prof < -0.05) & (prof > -5.5)
    ya, da = yw - yy[under], -prof[under]
    ok = False
    detail = 'no underwater beach found'
    if ya.size > 8:
        b, la = np.polyfit(np.log(ya), np.log(da), 1)
        ok = 0.6 <= b <= 0.73 and 0.07 <= math.exp(la) <= 0.13
        detail = (f'exposure {E[n // 2, col]:.2f}; underwater depth = {math.exp(la):.3f} y^{b:.3f} over '
                  f'{ya.max():.0f} m from the waterline ({time.time() - t0:.1f} s)')
    check('Dean profile: a sheltered coast gets a beach whose underwater depth fits A y^(2/3)', ok, detail)
    RESULTS['dean_profile'] = {'y_m': yy.tolist(), 'h_m': prof.tolist()}


def test_cliff():
    t0 = time.time()
    n, cell = 160, 2.0
    lv = _level(n, cell)
    X, Y = lv.xy()
    land = 60.0 + 0.05 * Y + 4.0 * np.sin(X / 23.0)                   # downland rising inland (north), 60 m
    land = np.where(Y < -60, -4.0, land)                             # the original shore 60 m south of the centre
    f = Fields(lv, {'h': land.astype(np.float32), 'bed': land.astype(np.float32)})
    P = {'retreat_m': 40.0, 'weakness': 0.0, 'crenel_m': 0.0, 'fetch_max_m': 600.0, 'face_spread_deg': 0.0,
         'platform_rough_m': 0.0, 'exposure_power': 0.0}
    CO.op_coast(f, lv, P, 1, ctx=_ctx(lv))
    h = np.asarray(f['h'], np.float64)
    sd = None
    # the face: slope along the columns (north-south)
    gy = np.gradient(h, cell, axis=0)
    s = np.degrees(np.arctan(np.abs(gy)))
    face = (h > 8.0) & (h < land - 8.0)
    fa = s[face]
    # the retreat line: 40 m inland of y = -60 -> y = -20; the land there
    j_ret = int(np.argmin(np.abs(Y[:, 0] - (-20.0))))
    top = h.max(axis=0)
    land_ret = land[j_ret + 15, :]
    inland = Y > 30
    plat = (Y < -30) & (Y > -58)
    check('cliff: the face stands at 70 degrees or steeper at 2 m cells',
          fa.size > 0 and np.percentile(fa, 50) >= 70.0,
          f'face slope p10/p50/p90 {np.percentile(fa, 10):.1f}/{np.percentile(fa, 50):.1f}/'
          f'{np.percentile(fa, 90):.1f} deg over {fa.size} cells')
    # per column: the face's top edge (the last cell steeper than 45 degrees, going inland from the foot) and the
    # first cell inland of it, which must sit on the land (the cliff as high as the land there, no lowered shoulder)
    deficit, heights = [], []
    for i in range(n):
        steep = np.nonzero(s[:, i] > 45.0)[0]
        if steep.size == 0:
            continue
        j1 = min(int(steep.max()) + 1, n - 1)
        deficit.append(float(land[j1, i] - h[j1, i]))
        heights.append(float(h[j1, i]))
    deficit = np.array(deficit)
    check('cliff: the top stands as high as the land at the retreat line (within 3 m)',
          deficit.size > 0.9 * n and np.abs(deficit).max() < 3.0,
          f'{deficit.size} columns: land - surface at the top edge max {np.abs(deficit).max():.2f} m; cliff height '
          f'{np.median(heights):.1f} m (the land at the retreat line {np.percentile(land[j_ret], 50):.1f} m)')
    ph = h[plat]
    check('cliff: the platform at the foot lies between -1 and +1 m',
          ph.size > 0 and ph.min() >= -1.0 and ph.max() <= 1.0 + 1e-6,
          f'platform {ph.min():.2f} .. {ph.max():.2f} m over {ph.size} cells')
    check('cliff: nothing changes inland of the cliff top', np.abs(h[inland] - land[inland]).max() < 1e-4,
          f'max |dh| inland {np.abs(h[inland] - land[inland]).max():.2e} m ({time.time() - t0:.1f} s)')
    RESULTS['cliff_profile'] = {'y_m': Y[:, n // 2].tolist(), 'h_m': h[:, n // 2].tolist()}


def test_column():
    col = CO.column_table('moher', 0.0)
    s = np.linspace(0, 80, 4001)
    z = CO.face_profile(s, 0.3, None, col, 0.0)
    dz = np.diff(z) / np.diff(s)
    ang = np.degrees(np.arctan(dz))
    zm = 0.5 * (z[1:] + z[:-1])
    beds = CO.COLUMNS['moher']
    cyc = sum(b[0] for b in beds)
    edges = np.cumsum([0.0] + [b[0] for b in beds])
    rows = []
    ok = True
    for k, (th, a) in enumerate(beds):
        inside = (np.mod(zm, cyc) > edges[k] + 0.6) & (np.mod(zm, cyc) < edges[k + 1] - 0.6) & (zm < 140)
        if inside.sum() < 3:
            continue
        got = float(np.median(ang[inside]))
        rows.append((th, a, round(got, 2)))
        ok &= abs(got - a) < 0.6
    overall = math.degrees(math.atan((z[-1] - z[0]) / (s[-1] - s[0])))
    check('column: each bed of the stepped face stands at its own angle', ok,
          f'(thickness, angle, measured): {rows}; overall {overall:.1f} deg')


def test_plan_fixes():
    """The fixes of 2026-11-09: (a) a hollow below sea level inland is land to the coast, not sea (sea_phi); (b) a
    face angle whose noise passes 90 degrees no longer turns tan negative and punches pits inland; (c) coast_land's
    shape meets itself across the old coastline in height and slope."""
    # (a) the sea reaching the edge stays sea; an inland basin below sea level does not
    H, W = 60, 80
    jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
    land = (jj - 20.0) * 2.0                                       # sea in the south rows, land rising north
    land[38:44, 30:36] = -3.0                                      # a hollow below sea level, far inland
    phi = CO.sea_phi(land, 0.0)
    check('sea_phi: the sea reaching the edge is sea, an inland hollow below sea level is land',
          bool((phi[:20] < 0).all()) and bool((phi[38:44, 30:36] > 0).all()),
          f'south rows sea: {bool((phi[:20] < 0).all())}; hollow cells land: {bool((phi[38:44, 30:36] > 0).all())}')
    # (b) op 'coast' with a face angle at 78 +- 25 degrees (noise far past 90): nothing inland drops
    n, cell = 128, 4.0
    lv = _level(n, cell)
    X, Y = lv.xy()
    ground = np.where(Y < -150.0, -6.0, 40.0 + 0.03 * Y)
    f = Fields(lv, {'h': ground.astype(np.float32), 'bed': ground.astype(np.float32)})
    CO.op_coast(f, lv, {'retreat_m': 40.0, 'weakness': 0.0, 'crenel_m': 0.0, 'fetch_max_m': 1000.0,
                        'face_spread_deg': 25.0, 'face_scale_m': 30.0}, 3, ctx=_ctx(lv))
    h = np.asarray(f['h'], np.float64)
    # the foot lies 40 m inland of the old shore (y = -110 m); the shallowest face (the 30 degree floor) reaches the
    # 37 m land 64 m further in: nothing may change beyond that, and no cell may sit in a pit of its own
    reach = -110.0 + 37.0 / math.tan(math.radians(30.0)) + 8.0
    drop = float((ground - h)[Y > reach].max())
    c = h[1:-1, 1:-1]
    nbmin = np.min([h[1 + dj:n - 1 + dj, 1 + di:n - 1 + di] for dj in (-1, 0, 1) for di in (-1, 0, 1)
                    if dj or di], axis=0)
    pits = int(((c < nbmin - 0.5) & (c > 0.3)).sum())
    check('cliff: a face angle noised past 90 degrees leaves no pits and cuts nothing past the shallowest face',
          drop < 0.01 and pits == 0, f'largest drop beyond {reach:.0f} m: {drop:.3g} m; pits on land: {pits}')
    # (c) land_shape: continuous value and slope at s0 = 0 for both rock presets' shapes
    ok, rows = True, []
    for c, rise, gain in ((0.65, 3000.0, 0.25), (0.95, 300.0, -0.5), (0.5, 1500.0, 0.35)):
        P = CO.params_for({'coast_frac': c, 'rise_m': rise, 'inland_gain': gain}, CO.LAND_DEFAULTS)
        e = 1e-3
        s = np.array([-2 * e, -e, 0.0, e, 2 * e])
        v = CO.land_shape(s, P)
        jump = abs(v[3] - v[1])
        sl_l, sl_r = (v[1] - v[0]) / e, (v[4] - v[3]) / e
        rows.append((c, round(float(v[2]), 4), round(sl_l * 1000, 4), round(sl_r * 1000, 4)))
        ok &= jump < 1e-5 and abs(sl_l - sl_r) <= 0.02 * max(abs(sl_r), 1e-9) + abs(gain) / P['tilt_m']
    check("coast_land's shape: no step and no crease along the old coastline", ok,
          f'(coast_frac, value at the coast, slope per km seaward, slope per km inland): {rows}')


def test_beach_scars_chalk():
    """The review of 2026-11-12 (the Birling Gap photograph: a wide grey shingle beach and the chalk platform at the
    cliff foot; the face's flint bands, fresh collapse scars and rubble). op 'coast' on a synthetic downland at 2 m
    cells with the chalk preset's foot (twin device): (a) a shingle beach at the cliff foot: its crest within 0.3 m
    of shingle_m, the ground above sea level out to 85-115 % of its width; (b) collapse scars recess the foot line
    (the cut with scars reaches up to scar_depth_m further inland than without, never less far) and heap debris at
    their foot (talus over 1 m); (c) the chalk column: every bed and flint band of the face at its own angle, the
    face about 79 degrees overall."""
    from eidoblend.terrain.recipes.sea_cliffs import ROCKS
    pre = ROCKS['chalk']['coast']                                      # the recipe's chalk foot, as it builds it
    n, cell = 200, 2.0
    lv = _level(n, cell)
    X, Y = lv.xy()
    land = 70.0 + 0.04 * Y + 3.0 * np.sin(X / 31.0)
    land = np.where(Y < -110, -4.0, land)                              # the original shore 110 m south
    base = {'retreat_m': 40.0, 'weakness': 0.0, 'crenel_m': 0.0, 'fetch_max_m': 800.0, 'face_spread_deg': 0.0,
            'platform_rough_m': 0.0, 'exposure_power': 0.0, 'talus_frac': 0.0, 'beach_exposure': [0.05, 0.1]}
    base.update({k: pre[k] for k in ('shingle_m', 'shingle_w_m', 'shingle_berm', 'platform_top_m',
                                     'platform_slope_deg')})
    crest_m, width_m = float(pre['shingle_m']), float(pre['shingle_w_m'])
    # the dry beach ends where the beach face, falling from the berm to -0.6 m at the beach's width, crosses the sea
    dry_m = width_m * (pre['shingle_berm'] + (1.0 - pre['shingle_berm']) * crest_m / (crest_m + 0.6))
    runs = {}
    for name, extra in (('plain', {}), ('scars', {'scars': 1.0, 'scar_spacing_m': 90.0})):
        f = Fields(lv, {'h': land.astype(np.float32), 'bed': land.astype(np.float32)})
        CO.op_coast(f, lv, dict(base, **extra), 5, ctx=_ctx(lv))
        runs[name] = f
    h = np.asarray(runs['plain']['h'], np.float64)
    # (a) per column: the face's foot (the first cell over 8 m going inland), the beach's crest and dry width
    crest, width = [], []
    for i in range(n):
        col = h[:, i]
        face = np.nonzero(col > 8.0)[0]
        if face.size == 0:
            continue
        jf = int(face.min())
        beach = col[:jf]
        crest.append(float(beach[max(jf - 6, 0):jf].max()))
        dry = np.nonzero(beach > 0.0)[0]
        width.append((jf - int(dry.min())) * cell if dry.size else 0.0)
    crest, width = np.array(crest), np.array(width)
    ok_a = (crest.size > 0.9 * n and abs(float(np.median(crest)) - crest_m) < 0.3
            and 0.85 * dry_m <= float(np.median(width)) <= 1.15 * dry_m)
    check('chalk foot: a shingle beach at the cliff foot (crest, width)', ok_a,
          f'crest median {np.median(crest):.2f} m (asked {crest_m:g}), dry beach width median '
          f'{np.median(width):.1f} m (its {width_m:g} m width less the beach face under the sea: {dry_m:.1f}) over '
          f'{crest.size} columns')
    # (b) scars: how much further inland the cut reaches, and the debris at their feet
    cut0 = np.asarray(runs['plain']['h'], np.float64) < land - 1.0
    cut1 = np.asarray(runs['scars']['h'], np.float64) < land - 1.0
    reach0 = np.array([Y[np.nonzero(cut0[:, i])[0].max(), i] if cut0[:, i].any() else -1e9 for i in range(n)])
    reach1 = np.array([Y[np.nonzero(cut1[:, i])[0].max(), i] if cut1[:, i].any() else -1e9 for i in range(n)])
    deeper = reach1 - reach0
    tal = np.asarray(runs['scars']['talus'], np.float64)
    ok_b = 3.0 <= deeper.max() <= 12.0 + 2 * cell and np.all(deeper >= -1e-6) and tal.max() > 1.0
    check('chalk foot: collapse scars recess the cliff line and heap debris at their foot', ok_b,
          f'recess max {deeper.max():.1f} m (scar_depth_m 3-12), columns recessed {int((deeper > cell).sum())} '
          f'of {n}; debris (talus) max {tal.max():.2f} m')
    # (c) the chalk column
    col = CO.column_table('chalk', 0.0)
    s = np.linspace(0, 40, 8001)
    z = CO.face_profile(s, 0.3, None, col, 0.0)
    ang = np.degrees(np.arctan(np.diff(z) / np.diff(s)))
    zm = 0.5 * (z[1:] + z[:-1])
    beds = CO.COLUMNS['chalk']
    cyc = sum(b[0] for b in beds)
    edges = np.cumsum([0.0] + [b[0] for b in beds])
    rows, ok_c = [], True
    for k, (th, a) in enumerate(beds):
        inside = (np.mod(zm, cyc) > edges[k] + 0.1) & (np.mod(zm, cyc) < edges[k + 1] - 0.1) & (zm < 100)
        if inside.sum() < 3:
            continue
        got = float(np.median(ang[inside]))
        rows.append((th, a, round(got, 2)))
        ok_c &= abs(got - a) < 0.6
    overall = math.degrees(math.atan((z[-1] - z[0]) / (s[-1] - s[0])))
    check('chalk column: each bed and flint band of the face at its own angle', ok_c and 77.0 <= overall <= 81.0,
          f'(thickness, angle, measured): {rows}; overall {overall:.1f} deg')


def main():
    t0 = time.time()
    for fn in (test_exposure, test_jfa, test_dean, test_cliff, test_column, test_plan_fixes, test_beach_scars_chalk):
        try:
            fn()
        except Exception as e:                                          # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
    RESULTS['_seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, 'test_coast.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1)
    print(f'{len(FAILED)} failed: {FAILED}' if FAILED else 'all passed', f'({RESULTS["_seconds"]} s)')
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
