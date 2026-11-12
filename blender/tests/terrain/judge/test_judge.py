"""The judge's tests, plain Python (system Python with numpy; nothing here needs Blender or a GPU):

    python blender/tests/terrain/judge/test_judge.py [--quick]

1. every reference judged against itself passes, with every banded row measurable on it
2. every reference resampled (Catmull-Rom) to 1024 cells over its own extent, as a recipe agent's film-quality
   tile at the reference's extent would be, judged against the reference passes: the matching path (a non-integer
   box average back to the reference's pixel) and every family reader on a field that is not the reference's bytes
3. Ekigar's triage heightfields fail, for the reasons the triage named: the alpine range (Lauterbrunnen: relief in
   tile fractions, nothing drains, needles, V not U, no hanging valleys), the volcano (Fuji: a stamp on a flat
   plane, nothing drains, flank aspects not radial) and the star dunes (Great Sand Dunes: a honeycomb of closed
   bowls, slip faces past the angle of repose, too many lee directions). Skipped (and said so) when the triage
   cache is not on this machine (triage/scenes.py CACHE or TRIAGE_CACHE)
4. synthetic shapes with known answers: a Pike crater's d/D and rim/D; a Wood cinder cone's H/W and flank p90; an
   exponential cone's monotone profile and radial aspects; a U trough (b ~ 2) against a V valley (b ~ 1); a stepped
   canyon wall's benches; the basin read (a lake, an infilled crater floor, a bowl); the radar chain softens a
   sharp ridge; the anisotropy band fails a grid-combed field against the San Gabriels and passes a rotated copy of
   the San Gabriels
Writes blender/tests/terrain/out/judge/test_judge.json; exit code 1 on a failure.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)

import numpy as np  # noqa: E402

from judge import judge, refs, family as F, generic as G, match as MA  # noqa: E402

OUT = os.path.join(TN, 'out', 'judge')
RESULTS, FAILED = {}, []
QUICK = '--quick' in sys.argv


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


# ----------------------------------------------------------------------------------------- 1, 2: references ---

def test_references_against_themselves():
    for name in refs.names():
        ref = refs.load(name)
        v = judge((ref.h, ref.pixel), name, label='itself', source_chain=False)
        unmeasurable = [r['metric'] for r in v.rows if r['kind'] != 'info' and r['band'] == 'not measurable']
        check(f'self_{name}', v.passed and not unmeasurable,
              f'{len(v.judged)} bands' + (f'; failures {v.failures}' if v.failures else '')
              + (f'; not measurable: {unmeasurable}' if unmeasurable else ''))


def test_references_at_1024_cells():
    for name in refs.names():
        ref = refs.load(name)
        n = 1024
        cell = ref.extent / n
        h = MA.cubic_resample(ref.h, ref.pixel, cell, n)
        v = judge((h, cell), name, label='1024 cells', source_chain=False)
        check(f'resampled_1024_{name}', v.passed, f'{cell:.3f} m cells, {len(v.judged)} bands'
              + (f'; failures {v.failures}' if v.failures else ''))


# -------------------------------------------------------------------------------------- 3: Ekigar's triage ---

EKIGAR = {
    # subject: (reference, the failures the triage's reasons must show up as, at least `need` of them)
    'mountainRange_alpine': ('lauterbrunnen', ['relief_m', 'bowl_area_frac', 'slope_p50', 'u_exponent',
                                               'hanging_step_m', 'hypsometric_integral'], 5),
    'volcano': ('mount_fuji', ['frac_slope_lt5', 'depression_area_frac', 'radial_aspect_frac', 'slope_p99',
                               'hypsometric_integral'], 4),
    'duneField_star': ('great_sand_dunes', ['bowl_area_frac', 'slip_face_p99', 'slope_p99', 'lee_aspect_peaks',
                                            'slope_p50'], 4),
}


def triage_cache():
    sys.path.insert(0, os.path.join(TN, 'triage'))
    try:
        import scenes                                                   # the triage's own cache location
        return scenes.CACHE
    except Exception:                                                   # noqa: BLE001
        return os.environ.get('TRIAGE_CACHE', '')
    finally:
        sys.path.pop(0)


def load_triage(cache, name):
    d = np.load(os.path.join(cache, name + '.npz'), allow_pickle=False)
    m = json.loads(str(d['meta']))
    z = d['height'].astype(np.float64) * m['vs'] * m['W']             # Ekigar's field units: z = h x 0.3 x W
    return z, m['W'] / z.shape[0]                                       # row 0 = south, as the terrain frame


def test_ekigar_fails():
    cache = triage_cache()
    if not cache or not os.path.isdir(cache):
        RESULTS['ekigar'] = {'ok': True, 'detail': f'SKIPPED: no triage cache at {cache!r}'}
        print(f'[SKIP] ekigar: no triage cache at {cache!r} (run triage/generate.py, or set TRIAGE_CACHE)')
        return
    for subject, (ref_name, reasons, need) in EKIGAR.items():
        path = os.path.join(cache, subject + '.npz')
        if not os.path.exists(path):
            check(f'ekigar_{subject}', False, f'{path} missing')
            continue
        z, cell = load_triage(cache, subject)
        v = judge((z, cell), ref_name, label='Ekigar ' + subject)
        failed = {r['metric'] for r in v.judged if not r['passed']}
        hit = [k for k in reasons if k in failed]
        check(f'ekigar_{subject}_fails', not v.passed and len(hit) >= need,
              f'vs {ref_name}: FAIL on {sorted(failed)}; the triage\'s reasons among them: {hit} ({len(hit)} of '
              f'{len(reasons)}, needed {need})')
        RESULTS[f'ekigar_{subject}_fails']['table'] = v.table()


# ---------------------------------------------------------------------------------------- 4: synthetic ---

def _grid(n, cell):
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    return (ii - (n - 1) / 2) * cell, (jj - (n - 1) / 2) * cell


def test_crater_reader():
    n, cell = 400, 5.0
    x, y = _grid(n, cell)
    r = np.hypot(x, y)
    D = 1000.0
    R = D / 2
    d, rim = 0.2 * D, 0.036 * D
    bowl = np.where(r < R, -d + rim + (d) * (r / R) ** 2, 0.0)                    # rim crest at r = R
    ejecta = np.where(r >= R, rim * (np.maximum(r, 1) / R) ** -3, 0.0)
    h = 1000.0 + np.where(r < R, bowl, ejecta)
    f = F.crater(h, cell)
    ok = (abs(f['crater_D_m'] - D) < 0.06 * D and abs(f['crater_d_over_D'] - 0.2) < 0.02
          and abs(f['rim_height_over_D'] - 0.036) < 0.01)
    check('crater_reader_pike', ok, {k: round(v, 3) for k, v in f.items() if isinstance(v, float)})


def test_cone_reader():
    n, cell = 400, 5.0
    x, y = _grid(n, cell)
    r = np.hypot(x, y)
    W, H = 800.0, 0.18 * 800.0                                               # Wood: H / W 0.18
    rc = 0.2 * W                                                             # crater 0.4 W across
    flank = np.clip((W / 2 - r) / (W / 2 - rc), 0, 1) * H
    crater = np.where(r < rc, H - 0.3 * H * (1 - (r / rc) ** 2), 0)
    h = 2000.0 + np.where(r < rc, crater, flank)
    f = F.cinder_cones(h, cell)
    exp_slope = math.degrees(math.atan(H / (W / 2 - rc)))
    ok = f.get('cone_count', 0) >= 1 and abs(f['cone_hw_max'] - 0.18) < 0.03 and abs(f['cone_flank_p90'] - exp_slope) < 4
    check('cone_reader_wood', ok, {**{k: round(v, 3) for k, v in f.items() if isinstance(v, float)},
                                   'flank_expected_deg': round(exp_slope, 1)})


def test_volcano_reader():
    n, cell = 500, 40.0
    x, y = _grid(n, cell)
    r = np.hypot(x, y)
    H, lam, rc = 3700.0, 3700.0 / math.tan(math.radians(33)), 400.0
    Rm = 9000.0
    z = H * (np.exp(-(r - rc) / lam) - math.exp(-(Rm - rc) / lam)) / (1 - math.exp(-(Rm - rc) / lam))
    h = 500.0 + np.clip(np.where(r < rc, H - 150 * (1 - (r / rc) ** 2), z), 0, None)
    f = F.volcano(h, cell)
    ok = f['profile_spearman'] <= -0.9 and f['radial_aspect_frac'] > 0.95
    check('volcano_reader_exponential_cone', ok, {k: round(v, 3) for k, v in f.items() if isinstance(v, float)})


def _valley(kind, n=300, cell=10.0):
    x, y = _grid(n, cell)
    ax = np.abs(x)
    if kind == 'U':
        z = np.where(ax < 600, 800.0 * (ax / 600.0) ** 2, 800.0 + (ax - 600) * 0.15)
    else:
        z = np.where(ax < 600, 800.0 * (ax / 600.0), 800.0 + (ax - 600) * 0.15)
    return 500.0 + z - y * 0.02                                              # the floor falls gently north to south


def test_u_reader():
    fu = F.alpine_valley(_valley('U'), 10.0)
    fv = F.alpine_valley(_valley('V'), 10.0)
    check('u_reader_parabola_vs_v', 1.7 <= fu['u_exponent'] <= 2.3 and 0.8 <= fv['u_exponent'] <= 1.2,
          {'U': round(fu['u_exponent'], 2), 'V': round(fv['u_exponent'], 2)})


def test_bench_reader():
    x = np.arange(0, 1500, 4.0)
    z = np.zeros_like(x)
    level, xi = 0.0, 0.0
    steps = [(60, 150), (80, 120), (40, 100), (100, 90)]                 # (riser height m, tread width m)
    knots = [(0.0, 0.0)]
    for rise, tread in steps:
        xi += rise / math.tan(math.radians(70))
        level += rise
        knots.append((xi, level))
        xi += tread
        knots.append((xi, level))
    knots.append((xi + 200 / math.tan(math.radians(70)), level + 200))
    kx, kz = zip(*knots)
    z = np.interp(x, kx, kz)
    b = F._benches(x, z, 4.0)
    check('bench_reader_four_steps', b == 4, f'{b} benches counted on a wall of 4 treads')


def test_basins():
    n, cell = 200, 5.0
    x, y = _grid(n, cell)
    r = np.hypot(x, y)
    tilt = 100.0 + x * 0.05                                                  # drains east to west
    bowl = tilt - np.clip(60.0 * (1 - (r / 250.0) ** 2), 0, None)             # paraboloid, D / R = 0.24
    flat = tilt - np.clip(np.minimum(60.0, 60.0 * (1 - (r / 250.0)) * 3), 0, None)   # steep walls, flat floor
    lake_h = bowl.copy()
    lake = r < 120
    lake_h[lake] = float(bowl[lake].max())
    b_bowl, b_flat, b_lake = G.basins(bowl, cell), G.basins(flat, cell), G.basins(lake_h, cell, lake)
    ok = (b_bowl['bowl_count'] == 1 and b_flat['flat_basin_count'] == 1 and b_flat['bowl_count'] == 0
          and b_lake['bowl_count'] == 0)
    check('basins_bowl_flat_lake', ok, {'bowl': b_bowl, 'flat floor': b_flat, 'lake': b_lake})


def test_radar_chain():
    """A field with detail the 30 m radar cannot see (ridges 2 km apart under 25 m ripples) loses it through the
    chain; the reference's own data is left alone with source_chain=False (the chain twice would soften twice)."""
    ref = refs.load('namib_linear_dunes')
    n = 2000
    cell = ref.extent / n
    x, y = _grid(n, cell)
    sharp = (400.0 + 80.0 * np.abs(((x / 2000.0) % 1.0) - 0.5) * 2 + 2.0 * np.sin(2 * math.pi * x / 25.0)
             * np.sin(2 * math.pi * y / 31.0))
    m = MA.match(sharp, cell, ref)
    box = G.grid.resample_box(sharp, cell, ref.pixel, ref.h.shape[0])
    p99_box = float(np.percentile(G.grid.slope_deg(box, ref.pixel), 99))
    p99_m = float(np.percentile(G.grid.slope_deg(m.gen, m.pixel), 99))
    same = MA.match(ref.h, ref.pixel, ref, source_chain=False)
    check('radar_chain_softens', p99_m < p99_box - 2.0 and any('same chain' in s for s in m.notes)
          and np.array_equal(same.gen, ref.h),
          {'p99 box-averaged to 10 m': round(p99_box, 1), 'p99 through the radar chain': round(p99_m, 1),
           'notes': m.notes})


def test_anisotropy_band():
    ref = refs.load('san_gabriel_mountains')
    n, cell = 1000, ref.pixel
    x, y = _grid(n, cell)
    rng = np.random.default_rng(4)
    combed = (1300 + 400 * np.abs(np.sin(x / 300.0)) + 400 * np.abs(np.sin(y / 340.0))
              + rng.normal(0, 3, (n, n)))
    v = judge((combed, cell), ref, label='axis-combed')
    rows = {r['metric']: r for r in v.rows}
    combed_fails = not rows['anisotropy_4']['passed'] or not rows['anisotropy_8']['passed']
    rot = np.ascontiguousarray(np.rot90(ref.h))                               # the real range turned 90 degrees
    v2 = judge((rot, cell), ref, label='rotated')
    rows2 = {r['metric']: r for r in v2.rows}
    check('anisotropy_band_combing', combed_fails and rows2['anisotropy_4']['passed'] and rows2['anisotropy_8']['passed'],
          {'combed A4/A8': (round(rows['anisotropy_4']['gen'], 3), round(rows['anisotropy_8']['gen'], 3)),
           'bands': (rows['anisotropy_4']['band'], rows['anisotropy_8']['band']),
           'rotated A4/A8': (round(rows2['anisotropy_4']['gen'], 3), round(rows2['anisotropy_8']['gen'], 3))})


def main():
    t0 = time.time()
    for f in (test_crater_reader, test_cone_reader, test_volcano_reader, test_u_reader, test_bench_reader,
              test_basins, test_radar_chain, test_anisotropy_band, test_ekigar_fails,
              test_references_against_themselves):
        try:
            f()
        except Exception as e:                                          # noqa: BLE001 - a crash is a failure
            import traceback
            traceback.print_exc()
            check(f.__name__, False, f'{type(e).__name__}: {e}')
    if not QUICK:
        try:
            test_references_at_1024_cells()
        except Exception as e:                                          # noqa: BLE001
            import traceback
            traceback.print_exc()
            check('test_references_at_1024_cells', False, f'{type(e).__name__}: {e}')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'test_judge.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(results=RESULTS, failed=FAILED, seconds=round(time.time() - t0, 1)), f, indent=1, default=str)
    print(f"\n{len(RESULTS) - len(FAILED)}/{len(RESULTS)} passed in {time.time() - t0:.0f}s"
          + (f"; FAILED: {', '.join(FAILED)}" if FAILED else ''))
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
