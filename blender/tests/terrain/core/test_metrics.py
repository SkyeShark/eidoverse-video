"""core/metrics.py tests, plain Python (system Python with numpy; Blender's works too):

    python blender/tests/terrain/core/test_metrics.py

1. every reference JSON's slope percentiles (p10, p50, p90, p99; main and context files) reproduced within 0.1 deg
   from the 16-bit PNG, and its relief and hypsometric integral
2. synthetic fields with known answers: a drained cone has no closed depressions, a dug pit is one depression of
   the dug area, white noise is full of them; label() equals a brute-force flood fill; resample_box keeps means and
   equals brute-force area weights; the spectrum finds a 500 m corrugation and the knee of a broken power law;
   anisotropy is ~1 for axis-aligned ridges and small for an isotropic field; texel-wide cliffs are counted
3. the full metrics of every main reference, recorded in out/core/reference_metrics.json (the judge calibrates its
   bands on them)
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plain_import  # noqa: E402

OUT = plain_import.install()
sys.path.insert(0, plain_import.REFERENCE_DIR)

import numpy as np  # noqa: E402

import landform_refs as R  # noqa: E402
from eidoblend.terrain.core import grid, metrics as M  # noqa: E402

FAILED = []
RESULTS = {}


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def test_reference_slopes():
    rows = []
    worst = 0.0
    for name in R.names():
        for ctx in (False, True):
            try:
                h, meta = R.load(name, context=ctx)
            except FileNotFoundError:
                continue
            want = meta['shape_stats']
            got = M.slope_stats(grid.from_north_up(h), meta['pixel_size_m'])
            d = {k: abs(got['slope_deg_' + k] - want['slope_deg_' + k]) for k in ('p10', 'p50', 'p90', 'p99')}
            dm = abs(got['slope_deg_mean'] - want['slope_deg_mean'])
            dhi = abs(got['hypsometric_integral'] - want['hypsometric_integral'])
            drel = abs(got['relief_m'] - want['relief_m'])
            worst = max(worst, max(d.values()))
            rows.append({'ref': name + ('_context' if ctx else ''), 'pixel_m': meta['pixel_size_m'],
                         'max_dslope_deg': round(max(d.values()), 4), 'dmean_deg': round(dm, 4),
                         'dHI': round(dhi, 5), 'drelief_m': round(drel, 3)})
            ok = max(d.values()) <= 0.1 and dhi <= 0.002 and drel <= 0.5
            if not ok:
                print('   ', rows[-1], 'want', want, 'got', got)
            check(f"reference_slopes_{rows[-1]['ref']}", ok,
                  f"max |dp| {max(d.values()):.4f} deg, |dHI| {dhi:.5f}, |drelief| {drel:.3f} m")
    RESULTS['reference_slope_rows'] = rows
    check('reference_slopes_count', len(rows) >= 28, f'{len(rows)} reference files, worst {worst:.4f} deg')


def test_depressions():
    n, cell = 128, 10.0
    jj, ii = np.mgrid[0:n, 0:n]
    r = np.hypot(ii - 63.5, jj - 63.5) * cell
    cone = 500.0 - r * 0.5
    frac, count, thr, _ = M.depressions(cone, cell)
    check('depressions_cone_none', frac == 0.0 and count == 0, (frac, count))
    pit = cone.copy()
    hole = (np.abs(ii - 40) <= 3) & (np.abs(jj - 80) <= 3)
    pit[hole] -= 25.0                                             # a 7 x 7 pit 25 m deep (the threshold is 1 m)
    frac, count, thr, depth = M.depressions(pit, cell)
    check('depressions_one_pit', count == 1 and abs(frac - hole.mean()) < 0.6 * hole.mean(),
          {'count': count, 'frac': frac, 'dug': float(hole.mean()), 'threshold_m': thr})
    shallow = cone.copy()
    shallow[hole] -= 0.5                                          # under the 1 m threshold: not counted
    check('depressions_shallow_ignored', M.depressions(shallow, cell)[1] == 0)
    noise = np.random.default_rng(3).random((128, 128)) * 50.0
    frac, count, _, _ = M.depressions(noise, cell)
    check('depressions_noise_many', count > 50 and frac > 0.05, (frac, count))


def _bfs_count(mask):
    seen = np.zeros_like(mask)
    count = 0
    h, w = mask.shape
    for j in range(h):
        for i in range(w):
            if mask[j, i] and not seen[j, i]:
                count += 1
                st = [(j, i)]
                seen[j, i] = True
                while st:
                    a, b = st.pop()
                    for da in (-1, 0, 1):
                        for db in (-1, 0, 1):
                            y, x = a + da, b + db
                            if 0 <= y < h and 0 <= x < w and mask[y, x] and not seen[y, x]:
                                seen[y, x] = True
                                st.append((y, x))
    return count


def test_label():
    rng = np.random.default_rng(9)
    ok = True
    for t in range(6):
        mask = rng.random((40 + t, 57)) < (0.3 + 0.08 * t)
        lab, n = M.label(mask)
        same = n == _bfs_count(mask)
        # every pair of 8-neighbours inside the mask shares a label
        for dj, di in M.PAIR_DIRS:
            sa, sb = M.pair_slices(dj, di, mask.shape)
            both = mask[sa] & mask[sb]
            same = same and bool(np.all(lab[sa][both] == lab[sb][both]))
        ok = ok and same and lab[~mask].max(initial=0) == 0
    check('label_matches_flood_fill', ok)


def test_resample():
    rng = np.random.default_rng(4)
    a = rng.random((100, 120))
    b = grid.resample_box(a, 1.0, 4.0)
    check('resample_box_integer', b.shape == (25, 30) and np.allclose(b, grid.box_down(a, 4)))
    c = grid.resample_box(a, 7.8125, 8.0)                         # a 1024-cell 8 km field to 8 m pixels, in small
    want = np.zeros(c.shape)
    r = 8.0 / 7.8125
    W = np.zeros((c.shape[0], a.shape[0]))
    for k in range(c.shape[0]):
        lo, hi = k * r, (k + 1) * r
        for i in range(a.shape[0]):
            W[k, i] = max(0.0, min(hi, i + 1) - max(lo, i)) / r
    W2 = np.zeros((c.shape[1], a.shape[1]))
    for k in range(c.shape[1]):
        lo, hi = k * r, (k + 1) * r
        for i in range(a.shape[1]):
            W2[k, i] = max(0.0, min(hi, i + 1) - max(lo, i)) / r
    want = W @ a @ W2.T
    check('resample_box_fractional_area_weights', np.allclose(c, want, atol=1e-12),
          {'shape': list(c.shape), 'max_err': float(np.abs(c - want).max())})
    check('resample_box_constant', np.allclose(grid.resample_box(np.full((64, 64), 3.5), 1.0, 1.7), 3.5))


def test_spectrum_and_anisotropy():
    n, cell = 256, 10.0
    x, y = grid.cell_centres(0.0, 0.0, cell, n)
    corr = 20.0 * np.sin(2 * np.pi * (x * 0.6 + y * 0.8) / 500.0) + np.random.default_rng(1).normal(0, 0.5, (n, n))
    wl, P = M.radial_spectrum(corr, cell)
    sl, knee, s1, s2, peak = M.spectrum_summary(wl, P, cell, n * cell)
    check('spectrum_peak_500m', 400.0 <= peak <= 620.0, {'peak_m': peak})
    # a broken power law: amplitude k^-1 (power k^-2) longer than 400 m, power k^-6 shorter
    rng = np.random.default_rng(2)
    ky = np.fft.fftfreq(512, d=cell)
    kx = np.fft.rfftfreq(512, d=cell)
    k = np.hypot(ky[:, None], kx[None, :])
    k[0, 0] = 1.0
    kk = 1.0 / 400.0
    amp = np.where(k < kk, k ** -1.0, kk ** -1.0 * (k / kk) ** -3.0)
    amp[0, 0] = 0
    z = np.fft.irfft2(amp * np.exp(2j * np.pi * rng.random(amp.shape)), s=(512, 512))
    wl, P = M.radial_spectrum(z, cell)
    sl, knee, s1, s2, peak = M.spectrum_summary(wl, P, cell, 512 * cell)
    check('spectrum_knee_400m', 250.0 <= knee <= 650.0 and s1 > s2, {'knee_m': knee, 'slope_long': s1,
                                                                     'slope_short': s2})
    ridges = 30.0 * np.sin(2 * np.pi * x / 300.0)                  # ridges along the y axis: aspects 0 / 180 deg
    a4, a8 = M.aspect_anisotropy(ridges, cell)
    waffle = ridges + 30.0 * np.sin(2 * np.pi * y / 300.0)        # ridges on both axes: grid-locked, no 2-fold
    hw = M.aspect_harmonics(waffle, cell)
    # an isotropic field: white noise under an isotropic Gaussian (a cone is not: a square holds more of its
    # diagonal aspects than its axial ones)
    rng = np.random.default_rng(6)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    kk = np.hypot(np.fft.fftfreq(n, d=cell)[:, None], np.fft.fftfreq(n, d=cell)[None, :])
    iso = np.real(np.fft.ifft2(f * np.exp(-0.5 * (kk * 60.0 * 2 * np.pi) ** 2))) * 3000.0
    b4, b8 = M.aspect_anisotropy(iso, cell)
    check('anisotropy_axis_ridges_high', a4 > 0.9, {'A4': a4, 'A8': a8})
    # sin x + sin y: gradients on the axes and (where both cosines peak) the diagonals; no single direction
    check('anisotropy_waffle_grid_locked', hw[4] > 0.2 and hw[2] < 0.05, hw)
    check('anisotropy_isotropic_field_low', b4 < 0.05 and b8 < 0.05, {'A4': b4, 'A8': b8})
    step = np.where(x > 1280, 100.0, 0.0)                         # a one-texel 100 m wall at 10 m cells: 84 deg
    cp = M.cliff_pairs(step, cell)
    check('cliff_pairs_counts_a_wall', 0.0 < cp < 0.02, cp)


def test_reference_metrics():
    table = {}
    t0 = time.perf_counter()
    for name in R.names():
        h, meta = R.load(name)
        t = time.perf_counter()
        m = M.metrics(grid.from_north_up(h), meta['pixel_size_m'])
        m['seconds'] = round(time.perf_counter() - t, 2)
        table[name] = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in m.items()}
        print(f"   {name:24s} p50 {m['slope_p50']:5.1f} p99 {m['slope_p99']:5.1f} dep {m['depression_area_frac']:.4f} "
              f"({m['depression_count']}) spec {m['spectrum_slope']:.2f} knee {m['spectrum_knee_m']:.0f} m "
              f"A4 {m['anisotropy_4']:.3f} A8 {m['anisotropy_8']:.3f} cliffs {m['cliff_pair_frac']:.5f} "
              f"[{m['seconds']} s]", flush=True)
    with open(os.path.join(OUT, 'reference_metrics.json'), 'w', encoding='utf-8') as f:
        json.dump(table, f, indent=1)
    check('reference_metrics_all', len(table) == len(R.names()) and all(np.isfinite(v['spectrum_slope'])
                                                                        for v in table.values()),
          f'{len(table)} references in {time.perf_counter() - t0:.1f} s')


def main():
    t0 = time.perf_counter()
    for fn in (test_reference_slopes, test_depressions, test_label, test_resample, test_spectrum_and_anisotropy,
               test_reference_metrics):
        t = time.perf_counter()
        try:
            fn()
        except Exception:                                          # noqa: BLE001
            import traceback
            check(fn.__name__ + '_ran', False, traceback.format_exc()[-1500:])
        print(f'  ({fn.__name__}: {time.perf_counter() - t:.1f} s)', flush=True)
    RESULTS['failed'] = FAILED
    RESULTS['seconds'] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(OUT, 'metrics_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"[metrics] {'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} in {RESULTS['seconds']} s")
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
