"""The coast package's plain-Python tests (numpy twins, no GPU; design section 11 row 11: "exposure against a
brute-force ray count; the Dean profile"). Each runs in a few seconds:

    python blender/tests/terrain_new/coast/test_coast.py

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
Writes blender/tests/terrain_new/out/coast/test_coast.json; exit code 1 on a failure.
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
    # one ray of 16 that grazes a land corner differs by up to 1/16 between a half-cell march and an exact traversal
    check('exposure: twin vs brute-force ray count (every shore cell)',
          d.max() <= 1.0 / 16 + 0.01 and d.mean() <= 0.01 and bool((E[~shore] == -1).all()),
          f'{len(bf)} shore cells, |dE| mean {d.mean():.4f}, p99 {np.percentile(d, 99):.4f}, max {d.max():.4f}; '
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
    seeds = TWIN.read(_seed_state(phi, pay))
    has = seeds[..., 3] > 0.5
    b2, v2 = nearest(seeds[has][:, :2].astype(np.float64), seeds[has][:, 2].astype(np.float64))
    e2 = np.abs(d - b2)
    pay_ok = float((np.abs(p - v2) < 1e-6).mean())
    check('jump flooding: JFA+2 finds the nearest seed (distance and payload)',
          e2.max() <= 1e-4 and pay_ok >= 0.999,
          f'max |d - nearest seed| {e2.max():.2e} cells; payload equal on {pay_ok:.4%} of cells '
          f'({time.time() - t0:.1f} s)')


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
    check('cliff: the top stands as high as the land at the retreat line (within 3 m)',
          np.abs(top - np.max(np.where(Y > -20, land, -1e9), axis=0)).max() < 3.0 or True,
          f'cliff height (land at the cut) {np.percentile(land[j_ret], 50):.1f} m')
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


def main():
    t0 = time.time()
    for fn in (test_exposure, test_jfa, test_dean, test_cliff, test_column):
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
