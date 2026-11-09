"""The masks package's acceptance tests (DESIGN.md section 11, package 4), on the real reference DEMs and on synthetic
fields with known answers. Plain Python and numpy (no Blender, no GPU):

    python blender/tests/terrain_new/masks/test_masks.py [-k name]      # (the test_* functions suit pytest too)

Each test prints its numbers; the run writes them to out/masks/test_results.json.

    slope_matches_reference_json   slope p10/p50/p90/p99 of every reference within 0.1 deg of its JSON
    curvature_curvatures_exact     profile / plan of a paraboloid and a ridge equal their formulas; a V-valley's
                                   bend is 0.8 tan(side) at any scale
    curvature_picks_its_scale      on a field of 1.6 km valleys carved by 160 m gullies, concave_20m finds the
                                   gullies and concave_200m the valleys
    curvature_on_references        the concave masks lie on valley cells and the convex ones on divides, at 20 m and
                                   200 m, on the five sheet references
    occlusion_sane                 a plane is open sky; a V-valley's floor matches its analytic sky view; on the
                                   references gorges and valleys are darker than ridges; the 2 x 2 far field stays
                                   within 0.03 (99th percentile) of a full-resolution march
    wetness_sane                   valley cells wetter than divides; water is 1; wetness rises with area at a fixed
                                   slope
    scale_independence             each mask means the same on the field upsampled 2 x (Catmull-Rom), at half the
                                   cell, normalised by the original
    stack_no_frame                 a stacked main tile shows no frame of curvature or occlusion at its border
    stack_rings                    a design-shaped stack (context, main, hero levels at 2 m and 0.5 m): every mask
                                   meets its parent at the seam; the cost per level
    periodic_tile                  on a periodic tile every mask moves with a roll of the field
    api                            names, attributes, errors that name the nearest valid mask, skipped inputs
"""
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as F  # noqa: E402

M, R = F.M, F.R
RESULTS = {}


def record(name, **kw):
    RESULTS.setdefault(name, {}).update(kw)


# ---------------------------------------------------------------- slope against the references' own numbers
def test_slope_matches_reference_json():
    worst = 0.0
    rows = {}
    for name in R.names():
        for ctx in (False, True):
            try:
                h, lv, meta = F.reference_level(name, context=ctx)
            except FileNotFoundError:
                continue
            m = M.compute({'h': h}, lv.cell, lv.x0, lv.y0, names=['slope'])
            s = m['slope'].astype(np.float64)
            got = np.percentile(s, [10, 50, 90, 99])
            ss = meta['shape_stats']
            want = np.array([ss['slope_deg_p10'], ss['slope_deg_p50'], ss['slope_deg_p90'], ss['slope_deg_p99']])
            d = np.abs(got - want)
            worst = max(worst, float(d.max()))
            rows[name + ('_context' if ctx else '')] = dict(got=[round(float(v), 2) for v in got],
                                                           json=want.tolist(), max_diff=round(float(d.max()), 3))
            assert d.max() <= 0.1, f'{name} context={ctx}: slope percentiles {got} vs JSON {want}'
    record('slope_matches_reference_json', references=len(rows), worst_diff_deg=round(worst, 3), rows=rows)
    print(f'  slope: {len(rows)} DEMs, worst percentile difference {worst:.3f} deg (bar 0.1)')


# ---------------------------------------------------------------- curvature
def _grid(n, cell):
    c = (np.arange(n) + 0.5 - n / 2) * cell
    return np.meshgrid(c, c)


def test_curvature_curvatures_exact():
    n, cell = 96, 2.0
    X, Y = _grid(n, cell)
    a = 0.004
    hp = M.pad_level(-a * (X ** 2 + Y ** 2), 1, cell)          # a dome: both curvatures +2a everywhere (Hessian)
    kp, kt = M.curvatures(hp, cell)
    sl = (slice(4, -4), slice(4, -4))
    e_dome = max(float(np.abs(kp[1:-1, 1:-1][sl] - 2 * a).max()), float(np.abs(kt[1:-1, 1:-1][sl] - 2 * a).max()))
    hp = M.pad_level(-a * X ** 2 + 0.3 * Y, 1, cell)            # a ridge along y, tilted: profile 0, plan +2a
    kp, kt = M.curvatures(hp, cell)
    # gradient along y (0.3) and across x (-2 a x): s points mostly along y, so -d2h/ds2 ~ 0 and -d2h/dn2 ~ 2a near
    # the crest
    crest = np.abs(X) < 6.0
    e_ridge_plan = float(np.abs(kt[1:-1, 1:-1][crest] - 2 * a).max())
    e_ridge_prof = float(np.abs(kp[1:-1, 1:-1][crest]).max())
    bends = {}
    for sigma in (20.0, 200.0):                                  # a V-valley with 30-degree sides, at two scales
        cellv = sigma / 10.0
        n2 = 400
        Xv, _ = _grid(n2, cellv)
        hv = np.tan(math.radians(30.0)) * np.abs(Xv) + 0.01 * _grid(n2, cellv)[1]
        m = M.compute({'h': hv}, cellv, names=[f'curv_plan_{M.scale_suffix(sigma)}',
                                               f'curv_profile_{M.scale_suffix(sigma)}'])
        k = m[f'curv_plan_{M.scale_suffix(sigma)}'] + m[f'curv_profile_{M.scale_suffix(sigma)}']
        bends[sigma] = float(-k[n2 // 2, n2 // 2 - 1:n2 // 2 + 1].mean() * sigma)
    want = 2.0 * math.tan(math.radians(30.0)) / math.sqrt(2.0 * math.pi)
    record('curvature_curvatures_exact', dome_err=e_dome, ridge_plan_err=e_ridge_plan, ridge_profile_err=e_ridge_prof,
           v_valley_bend={str(k): round(v, 4) for k, v in bends.items()}, v_valley_bend_formula=round(want, 4))
    print(f'  curvatures: dome err {e_dome:.2e}, ridge plan err {e_ridge_plan:.2e}, ridge profile {e_ridge_prof:.2e}; '
          f'V-valley bend {bends} vs 0.8 tan 30 = {want:.3f}')
    assert e_dome < 1e-5 and e_ridge_plan < 2e-4 and e_ridge_prof < 2e-4     # float32: 1e-5 of 2a = 0.008
    for v in bends.values():
        assert abs(v - want) < 0.03, f'V-valley bend {v} vs {want}'


def test_curvature_picks_its_scale():
    """1.6 km valleys (relief 300 m) carved by 160 m gullies (relief 24 m, sides up to 25 degrees), at 4 m cells:
    which troughs does each scale's concave mask sit in?"""
    n, cell = 800, 4.0
    X, Y = _grid(n, cell)
    big = 150.0 * np.cos(2 * math.pi * X / 1600.0)               # valleys where cos = -1
    small = 12.0 * np.cos(2 * math.pi * (X + 0.6 * Y) / 160.0)
    h = big + small + 0.05 * Y
    m = M.compute({'h': h}, cell, names=['concave_20m', 'convex_20m', 'concave_200m', 'convex_200m'])
    in_gully = np.cos(2 * math.pi * (X + 0.6 * Y) / 160.0) < -0.7
    on_gully_crest = np.cos(2 * math.pi * (X + 0.6 * Y) / 160.0) > 0.7
    in_valley = np.cos(2 * math.pi * X / 1600.0) < -0.9
    on_ridge = np.cos(2 * math.pi * X / 1600.0) > 0.9
    k = (slice(60, -60), slice(60, -60))
    r = dict(
        concave20_in_gullies=float(m['concave_20m'][k][in_gully[k]].mean()),
        concave20_on_gully_crests=float(m['concave_20m'][k][on_gully_crest[k]].mean()),
        concave200_in_valleys=float(m['concave_200m'][k][in_valley[k]].mean()),
        concave200_on_ridges=float(m['concave_200m'][k][on_ridge[k]].mean()),
        convex200_on_ridges=float(m['convex_200m'][k][on_ridge[k]].mean()),
        concave200_gully_vs_crest=float(m['concave_200m'][k][in_gully[k]].mean()
                                        - m['concave_200m'][k][on_gully_crest[k]].mean()),
    )
    record('curvature_picks_its_scale', **{a: round(b, 3) for a, b in r.items()})
    print('  scale pick: ' + ', '.join(f'{a} {b:.2f}' for a, b in r.items()))
    assert r['concave20_in_gullies'] > 0.6 and r['concave20_on_gully_crests'] < 0.05
    assert r['concave200_in_valleys'] > 0.6 and r['concave200_on_ridges'] < 0.05 and r['convex200_on_ridges'] > 0.6
    assert abs(r['concave200_gully_vs_crest']) < 0.05            # the 200 m scale does not see the gullies


def _valley_ridge_cells(fields, lv):
    A = fields['A']
    valley = A >= 1.0e5                                        # 0.1 km^2 and more: valley floors and channels
    divide = A <= 1.5 * lv.cell * lv.cell                      # nothing drains in: divides and crests
    return valley, divide


def test_curvature_on_references():
    rows = {}
    for name in F.SHEET_REFS:
        fl, lv, meta = F.reference_stack(name)
        ms = M.compute_stack(fl, lv, names=['concave_20m', 'convex_20m', 'concave_200m', 'convex_200m'],
                             params=F.params_for(name))
        m = ms[1]
        valley, divide = _valley_ridge_cells(fl[1], lv[1])
        row = {}
        for s in ('20m', '200m'):
            cc, cv = m[f'concave_{s}'], m[f'convex_{s}']
            row[s] = dict(concave_valley=round(float(cc[valley].mean()), 3), concave_all=round(float(cc.mean()), 3),
                          convex_divide=round(float(cv[divide].mean()), 3), convex_all=round(float(cv.mean()), 3),
                          concave_divide=round(float(cc[divide].mean()), 3),
                          convex_valley=round(float(cv[valley].mean()), 3))
        rows[name] = row
        print(f'  {name}: ' + '; '.join(f'{s} concave valley {r["concave_valley"]:.2f} (all {r["concave_all"]:.2f}, '
                                        f'divide {r["concave_divide"]:.2f}), convex divide {r["convex_divide"]:.2f} '
                                        f'(all {r["convex_all"]:.2f}, valley {r["convex_valley"]:.2f})'
                                        for s, r in row.items()))
    # concave - convex must sit clearly higher on valley cells than on divides wherever the scale has content. (A
    # one-sided lift is no test at 200 m: many divide cells are small crests inside 200 m valleys, and a plateau's
    # divides are flat at that scale; nor at 20 m on Fuji's 40 m cells, which cannot resolve 20 m.)
    for name, row in rows.items():
        for s, r in row.items():
            r['signed_gap'] = round((r['concave_valley'] - r['convex_valley'])
                                    - (r['concave_divide'] - r['convex_divide']), 3)
            if r['concave_all'] < 0.02 and r['convex_all'] < 0.02:
                r['no_content'] = True                           # nothing at that scale (dunes, badlands at 200 m)
                continue
            assert r['signed_gap'] > 0.2, f'{name} {s}: the curvature masks do not separate valleys and divides {r}'
    record('curvature_on_references', rows=rows)


# ---------------------------------------------------------------- occlusion
def test_occlusion_sane():
    out = {}
    n, cell = 200, 5.0
    X, Y = _grid(n, cell)
    plane = 0.2 * X + 0.1 * Y
    o = M.sky_view(np.zeros((n, n)), cell, 300.0)
    out['flat_min'] = float(o.min())
    assert o.min() > 0.999
    # an infinite V-valley, sides at 30 degrees: from its floor the horizon in azimuth a stands at
    # atan(tan30 |cos a|) (cos: x across the valley); along the valley 0
    th = math.radians(30.0)
    hv = np.tan(th) * np.abs(X)
    o = M.sky_view(hv, cell, 2000.0, outside=None)
    floor = o[n // 2 - 1:n // 2 + 1, n // 2].mean()               # centre: far from the ends (open sky beyond them)
    az = np.linspace(0, 2 * math.pi, 3600, endpoint=False)
    want = 1.0 - np.mean(np.sin(np.arctan(math.tan(th) * np.abs(np.cos(az)))))
    out.update(v_floor=float(floor), v_floor_analytic=float(want))
    assert abs(floor - want) < 0.01, f'V floor sky view {floor} vs {want}'
    # a plane slope: the sky view of a cell on an infinite plane tilted at b: 1 - mean(sin(max(0, atan(tan b cos a))))
    o = M.sky_view(plane, cell, 400.0)
    b = math.atan(math.hypot(0.2, 0.1))
    want_p = 1.0 - np.mean(np.sin(np.maximum(0.0, np.arctan(math.tan(b) * np.cos(az)))))
    mid = o[60:140, 60:140]
    out.update(plane_mid=float(mid.mean()), plane_analytic=float(want_p))
    assert abs(mid.mean() - want_p) < 0.01
    # the references: gorges and valleys under the sky of the ridges; the far-field shortcut against a full march
    rows = {}
    for name in F.SHEET_REFS:
        fl, lv, meta = F.reference_stack(name)
        S = M.StackSampler([(lv[0].x0, lv[0].y0, lv[0].cell, fl[0]['h'])])
        h = fl[1]['h']
        o = M.sky_view(h, lv[1].cell, 500.0, lv[1].x0, lv[1].y0, outside=S)
        full = M.sky_view(h, lv[1].cell, 500.0, lv[1].x0, lv[1].y0, outside=S, near_cells=100000)
        valley, divide = _valley_ridge_cells(fl[1], lv[1])
        d = np.abs(o - full)
        rows[name] = dict(valley=round(float(o[valley].mean()), 3), divide=round(float(o[divide].mean()), 3),
                          min=round(float(o.min()), 3), max=round(float(o.max()), 3),
                          far_field_err_mean=round(float(d.mean()), 4), far_field_err_p99=round(float(np.percentile(d, 99)), 4))
        assert 0.0 <= o.min() and o.max() <= 1.0
        # valleys under less sky than divides everywhere; by a tenth where the relief is deep (Fuji's apron channels
        # are shallow cuts in open ground: 0.91 against 0.94)
        margin = 0.1 if name in ('lauterbrunnen', 'grand_canyon_toroweap') else 0.01
        assert rows[name]['valley'] < rows[name]['divide'] - margin, f'{name}: valleys not darker {rows[name]}'
        assert rows[name]['far_field_err_p99'] < 0.03
        print(f'  occlusion {name}: valley {rows[name]["valley"]:.3f} < divide {rows[name]["divide"]:.3f}; '
              f'far field err mean {rows[name]["far_field_err_mean"]:.4f} p99 {rows[name]["far_field_err_p99"]:.4f}')
    # Toroweap's inner gorge: the floor below 700 m altitude (the river at 500 m, walls to 1400 m)
    fl, lv, _ = F.reference_stack('grand_canyon_toroweap')
    o = M.compute_stack(fl, lv, names=['occlusion'])[1]['occlusion']
    gorge = fl[1]['h'] < 600.0
    out['toroweap_gorge_floor'] = float(o[gorge].mean())
    assert out['toroweap_gorge_floor'] < 0.6
    record('occlusion_sane', **out, references=rows)
    print(f'  occlusion: plane {out["plane_mid"]:.4f} (analytic {out["plane_analytic"]:.4f}), V floor '
          f'{out["v_floor"]:.4f} (analytic {out["v_floor_analytic"]:.4f}), Toroweap gorge floor '
          f'{out["toroweap_gorge_floor"]:.3f}')


# ---------------------------------------------------------------- wetness
def test_wetness_sane():
    rows = {}
    for name in F.SHEET_REFS:
        fl, lv, meta = F.reference_stack(name)
        m = M.compute_stack(fl, lv, names=['wetness', 'slope'], params=F.params_for(name))[1]
        w = m['wetness']
        valley, divide = _valley_ridge_cells(fl[1], lv[1])
        rows[name] = dict(valley=round(float(w[valley].mean()), 3), divide=round(float(w[divide].mean()), 3),
                          mean=round(float(w.mean()), 3))
        if 'water' in fl[1]:      # a shore's first 0.3 m of depth fades in; the outer 16 cells are pinned to the
            inner = np.zeros(w.shape, bool)                   # parent's masks (the context has no lakes here)
            inner[16:-16, 16:-16] = True
            rows[name]['water_min'] = round(float(w[(fl[1]['water'] >= 0.3) & inner].min()), 3)
            assert rows[name]['water_min'] == 1.0
        assert 0.0 <= w.min() and w.max() <= 1.0
        assert rows[name]['valley'] > rows[name]['divide'] + 0.3, f'{name}: {rows[name]}'
        print(f'  wetness {name}: valley {rows[name]["valley"]:.2f}, divide {rows[name]["divide"]:.2f}, '
              f'mean {rows[name]["mean"]:.2f}' + (f', water {rows[name]["water_min"]}' if 'water_min' in rows[name]
                                                  else ''))
    # monotone in area at a fixed slope
    n, cell = 64, 10.0
    X, Y = _grid(n, cell)
    h = 0.2 * Y
    A = np.broadcast_to(np.logspace(2, 7, n)[None, :], (n, n)).copy()
    norms = M.Norms(cell_m=cell, h_lo=0.0, h_hi=1.0, flow_lo=1.0, flow_hi=6.0, twi_lo=3.0, twi_hi=12.0)
    w = M.compute({'h': h, 'A': A}, cell, names=['wetness'], norms=norms)['wetness'][n // 2]
    assert np.all(np.diff(w) >= -1e-6)
    record('wetness_sane', references=rows, monotone_in_area=True)


# ---------------------------------------------------------------- scale independence
SCALE_FREE = ['slope', 'northness', 'eastness', 'height_norm', 'curv_profile_20m', 'curv_plan_20m', 'convex_20m',
              'concave_20m', 'convex_200m', 'concave_200m', 'peaks', 'flow', 'channels', 'wetness', 'occlusion',
              'rock', 'rock_toe', 'snow', 'vegetation']


def upsample2(h):
    """Catmull-Rom x 2, cell-centred (DESIGN.md 2.4: how a child level inherits h)."""
    ny, nx = h.shape
    fy = (np.arange(2 * ny) + 0.5) / 2.0 - 0.5
    fx = (np.arange(2 * nx) + 0.5) / 2.0 - 0.5
    FX, FY = np.meshgrid(fx, fy)
    return M._catmull_rom(np.asarray(h, np.float64), FX, FY)


def box2(a):
    ny, nx = a.shape
    return a[:ny // 2 * 2, :nx // 2 * 2].reshape(ny // 2, 2, nx // 2, 2).mean(axis=(1, 3))


def test_scale_independence():
    rows = {}
    for name, (ci, cj, half) in {'lauterbrunnen': (420, 440, 180), 'grand_canyon_toroweap': (560, 560, 180),
                                 'badlands_sd': (500, 450, 180), 'great_sand_dunes': (500, 500, 180),
                                 'mount_fuji': (500, 500, 180)}.items():
        h_full, lv, meta = F.reference_level(name)
        h = h_full[cj - half:cj + half, ci - half:ci + half]
        c = lv.cell
        hf = upsample2(h)
        P = F.params_for(name, channel_area_m2=2.0e4)              # a fixed channel area: the per-level one is LOD
        A, _ = F.drainage_area(h, c)
        Af, _ = F.drainage_area(hf, c / 2)
        base = {'h': h, 'A': A}
        if name in F.SAND_TILES:
            base['sand'] = np.full(h.shape, F.SAND_TILES[name])
        fine = {'h': hf, 'A': Af}
        if 'sand' in base:
            fine['sand'] = np.full(hf.shape, F.SAND_TILES[name])
        norms = M.norms_from(base, c, P)
        names = SCALE_FREE if c <= 10.0 else [n for n in SCALE_FREE if '20m' not in n]
        mc = M.compute(base, c, names=names, norms=norms, params=P, strict=False)
        mf = M.compute(fine, c / 2, names=names, norms=norms, params=P, strict=False)
        row = {}
        k = (slice(12, -12), slice(12, -12))                      # the edges extrapolate differently at each cell
        # rivers: where the coarse area is ten times the threshold, a channel at both cells (the fine one a line
        # half a coarse cell wide, so the block's maximum). On divergent ground an area threshold is resolution-
        # dependent by nature (MFD gives a cell its upslope length times its own width): that part of channels is
        # level-of-detail, as the design defines it per level, and is reported, not held to the bar.
        river = (A >= 10 * P.channel_area_m2)[k]
        fmax = mf['channels'].reshape(h.shape[0], 2, h.shape[1], 2).max(axis=(1, 3))[k]
        row['channels_on_rivers'] = dict(coarse=round(float(mc['channels'][k][river].mean()), 3),
                                         fine_block_max=round(float(fmax[river].mean()), 3), cells=int(river.sum()))
        for nm in names:
            if nm not in mc:
                continue
            a = np.asarray(mc[nm], np.float64)[k]
            b = box2(np.asarray(mf[nm], np.float64))[k]
            if nm.startswith('curv_'):
                sc = float(nm.split('_')[-1][:-1])
                a, b = a * sc, b * sc                               # as a bend: the dimensionless change of slope
            if nm == 'slope':
                row[nm] = dict(p50=round(float(np.median(b) - np.median(a)), 2),
                               p90=round(float(np.percentile(b, 90) - np.percentile(a, 90)), 2),
                               mean_abs=round(float(np.abs(a - b).mean()), 3))
                continue
            corr = float(np.corrcoef(a.ravel(), b.ravel())[0, 1]) if a.std() > 1e-9 and b.std() > 1e-9 else 1.0
            row[nm] = dict(mean_abs=round(float(np.abs(a - b).mean()), 4), mean_a=round(float(a.mean()), 4),
                           mean_b=round(float(b.mean()), 4), corr=round(corr, 3))
        rows[name] = row
    record('scale_independence', rows=rows, bars=SCALE_BARS)
    bad = []
    for name, row in rows.items():
        line = []
        for nm, r in row.items():
            if nm == 'slope':
                line.append(f'slope dp50 {r["p50"]:+.2f} dp90 {r["p90"]:+.2f}')
                if abs(r['p50']) > 1.0 or abs(r['p90']) > 1.5:
                    bad.append((name, nm, r))
                continue
            if nm == 'channels_on_rivers':
                line.append(f'rivers {r["coarse"]:.2f}/{r["fine_block_max"]:.2f}')
                if r['cells'] and name not in F.SAND_TILES and min(r['coarse'], r['fine_block_max']) < 0.9:
                    bad.append((name, nm, r))                    # (on dune sand channels are off by design)
                continue
            line.append(f'{nm} {r["mean_abs"]:.3f}/{r["corr"]:.2f}')
            if nm == 'channels':
                continue
            mean_bar, corr_bar = SCALE_BARS.get(nm, SCALE_BARS['geometry'])
            if r['mean_abs'] > mean_bar or (r['corr'] < corr_bar and max(abs(r['mean_a']), abs(r['mean_b'])) > 0.01):
                bad.append((name, nm, r))
        print(f'  {name}: ' + ', '.join(line))
    assert not bad, f'masks that change meaning on a 2 x resampled field: {bad}'


# (mean |difference|, correlation) bars: the geometry masks are exact up to the interpolation (aspect flips sign
# across every sharp crest, so a 2 x 2 average across one mixes +1 and -1: 0.05 for northness and eastness); the
# drainage masks carry the router's own resolution dependence (MFD dispersion on divergent ground); rock_toe and
# vegetation are smoothstep rules on thresholded inputs (a 40-degree rock cell flips with the interpolated slope)
SCALE_BARS = {'geometry': (0.03, 0.95), 'northness': (0.05, 0.95), 'eastness': (0.05, 0.95), 'flow': (0.08, 0.85),
              'wetness': (0.08, 0.9), 'rock_toe': (0.08, 0.85), 'vegetation': (0.08, 0.85)}


# ---------------------------------------------------------------- the stack and its seams
def test_stack_no_frame():
    rows = {}
    for name in F.SHEET_REFS:
        fl, lv, meta = F.reference_stack(name)
        m = M.compute_stack(fl, lv, names=['convex_20m', 'concave_20m', 'occlusion', 'convex', 'concave'],
                            params=F.params_for(name))[1]
        row = {}
        for nm in ('convex_20m', 'concave_20m', 'convex', 'concave', 'occlusion'):
            v = m[nm]
            edge = np.concatenate([v[:3].ravel(), v[-3:].ravel(), v[:, :3].ravel(), v[:, -3:].ravel()])
            inner = v[40:-40, 40:-40]
            row[nm] = dict(edge=round(float(edge.mean()), 4), inner=round(float(inner.mean()), 4))
        rows[name] = row
        for nm, r in row.items():
            if nm == 'occlusion':
                assert abs(r['edge'] - r['inner']) < 0.15, f'{name} {nm}: {r}'
            else:
                assert r['edge'] < 2.0 * r['inner'] + 0.02, f'{name} {nm}: a frame at the border {r}'
    record('stack_no_frame', rows=rows)
    print('  stack border vs interior: ' + '; '.join(f'{n} convex_20m {r["convex_20m"]["edge"]:.3f}/'
                                                   f'{r["convex_20m"]["inner"]:.3f}' for n, r in rows.items()))


def test_stack_rings():
    """A design-shaped stack (Lauterbrunnen's 32 m context and 8 m main tile, hero levels of 1024^2 at 2 m and
    0.5 m): every mask but aspect meets its parent at the seam (the outermost two cells), the hero levels' masks stay
    in range, and the cost per level is recorded."""
    fields, levels, meta = F.hero_stack('lauterbrunnen')
    P = F.params_for('lauterbrunnen')
    t0 = time.time()
    ms = M.compute_stack(fields, levels, params=P)
    total = time.time() - t0
    seams = {}
    for i in range(1, len(ms)):
        c, p, lc = ms[i], ms[i - 1], levels[i]
        n = c.shape[0]
        edge = np.zeros(c.shape, bool)
        edge[:2, :] = edge[-2:, :] = edge[:, :2] = edge[:, -2:] = True
        X, Y = np.meshgrid(lc.x0 + (np.arange(c.shape[1]) + 0.5) * lc.cell, lc.y0 + (np.arange(n) + 0.5) * lc.cell)
        worst = {}
        for nm in c:
            if nm == 'aspect' or nm not in p:
                continue
            pv = M.StackSampler([(p.x0, p.y0, p.cell, p[nm])])(X[edge], Y[edge], cubic=False)
            scale = 90.0 if nm == 'slope' else (max(1.0, float(np.abs(p[nm]).max())) if nm in MASKS_IN_METRES else 1.0)
            worst[nm] = float(np.nanmean(np.abs(pv - c[nm][edge]))) / scale
        seams[f'{lc.cell:g} m in {p.cell:g} m'] = {k: round(v, 5) for k, v in worst.items()}
        bad = {k: v for k, v in worst.items() if v > 0.005}
        assert not bad, f'ring {i}: masks that do not meet their parent at the seam {bad}'
    for m in ms[2:]:
        for nm in ('slope', 'occlusion', 'rock', 'rock_toe', 'vegetation', 'wetness', 'flow'):
            v = m[nm]
            assert np.isfinite(v).all() and v.min() >= 0.0 and v.max() <= (90.0 if nm == 'slope' else 1.0)
    per_level = [dict(cell=l.cell, n=int(m.shape[0]), seconds={k: round(v, 2) for k, v in m.seconds.items()})
                 for l, m in zip(levels, ms)]
    record('stack_rings', total_seconds=round(total, 2), per_level=per_level, seam_mean_abs=seams)
    print(f'  stack of {len(ms)} levels in {total:.1f}s: ' + ', '.join(f'{d["cell"]:g} m {d["seconds"]["total"]:.2f}s'
                                                                  for d in per_level))
    print('  seams (outermost 2 cells vs parent, worst mask): ' + ', '.join(
        f'{k}: {max(v.values()):.4f}' for k, v in seams.items()))


MASKS_IN_METRES = ('height', 'wear', 'deposit', 'talus', 'sand', 'water', 'strata')


def test_periodic_tile():
    n, cell = 128, 6.0
    i = np.arange(n)
    I, J = np.meshgrid(i, i)
    h = (30 * np.sin(2 * math.pi * I / n) * np.cos(4 * math.pi * J / n) + 12 * np.sin(2 * math.pi * (3 * I + 2 * J) / n)
         + 5 * np.cos(2 * math.pi * 7 * J / n))
    P = M.MaskParams(wrap=(True, True), occlusion_radius_m=200.0)
    names = ['slope', 'northness', 'convex_20m', 'concave', 'peaks', 'occlusion', 'rock', 'rock_toe']
    a = M.compute({'h': h}, cell, names=names, params=P)
    # a roll by whole boxes of the widest decimation (peaks: 150 m on 6 m cells box-averages by 8), so the boxes see
    # the same cells
    roll = (32, 64)
    b = M.compute({'h': np.roll(h, roll, axis=(0, 1))}, cell, names=names, params=P, norms=a.norms)
    per = {nm: float(np.abs(np.roll(a[nm], roll, axis=(0, 1)) - b[nm]).max()) for nm in names}
    worst = max(per.values())
    record('periodic_tile', worst=worst, per_mask=per)
    print(f'  periodic tile: worst difference after a roll {worst:.2e} ' + str({k: f'{v:.1e}' for k, v in per.items()}))
    assert worst < 1e-3


def test_api():
    n, cell = 48, 4.0
    X, Y = _grid(n, cell)
    h = 0.3 * X + 5 * np.sin(Y / 30.0)
    m = M.compute({'h': h}, cell)                                # defaults: absent inputs skipped, said why
    assert 'flow' in m.skipped and 'wear' in m.skipped and 'slope' in m
    assert all(v.dtype == np.float32 and v.shape == (n, n) for v in m.values())
    assert m.attributes()[0][0].startswith('eido_')
    try:
        M.compute({'h': h}, cell, names=['wetness'])
        raise AssertionError('a named mask without its input must raise')
    except KeyError as e:
        assert "'A'" in str(e)
    try:
        M.parse_name('slop')
        raise AssertionError('an unknown mask must raise')
    except KeyError as e:
        assert 'slope' in str(e)
    assert M.parse_name('concave_200m') == ('concave', 200.0) and M.parse_name('convex_2p5m') == ('convex', 2.5)
    assert M.channel_area_for_cell(0.5) == 1000.0 and M.channel_area_for_cell(8.0) == 1.0e6

    class Fields(dict):                                          # core's Fields: a dict with its level attached
        pass
    f = Fields(h=h)
    f.level = dict(x0=100.0, y0=-50.0, cell=cell, role='main')
    m2 = M.compute(f, names=['slope', 'strata'], params=M.MaskParams(strata=dict(dip_deg=1.0, azimuth_deg=90.0)))
    assert m2.cell == cell and m2.x0 == 100.0
    zs_want = h - math.tan(math.radians(1.0)) * (-50.0 + (np.arange(n) + 0.5) * cell)[:, None]
    assert np.abs(m2['strata'] - zs_want).max() < 1e-3
    record('api', ok=True, default_names=len(M.DEFAULT_NAMES))
    print(f'  api: {len(M.DEFAULT_NAMES)} default masks, errors name the nearest, Fields with .level accepted')


TESTS = [test_api, test_curvature_curvatures_exact, test_curvature_picks_its_scale, test_periodic_tile,
         test_slope_matches_reference_json, test_curvature_on_references, test_occlusion_sane, test_wetness_sane,
         test_stack_no_frame, test_stack_rings, test_scale_independence]


def main():
    only = sys.argv[sys.argv.index('-k') + 1] if '-k' in sys.argv else ''
    failed = []
    for t in TESTS:
        if only and only not in t.__name__:
            continue
        t0 = time.time()
        print(f'{t.__name__} ...')
        try:
            t()
            print(f'  ok ({time.time() - t0:.1f}s)')
            RESULTS.setdefault(t.__name__.replace('test_', ''), {})['seconds'] = round(time.time() - t0, 1)
        except AssertionError as e:
            failed.append(t.__name__)
            print(f'  FAILED: {e}')
            RESULTS.setdefault(t.__name__.replace('test_', ''), {})['failed'] = str(e)[:500]
    os.makedirs(F.OUT, exist_ok=True)
    path = os.path.join(F.OUT, 'test_results.json')
    old = {}
    if only and os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
    old.update(RESULTS)
    with open(path, 'w') as f:
        json.dump(old, f, indent=1)
    print('FAILED: ' + ', '.join(failed) if failed else 'all passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
