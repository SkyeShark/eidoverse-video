"""Sheets and numbers for the detail package's real_place runs (plain Python, no GPU):

    python -I blender/tests/terrain_new/detail/sheets.py --tag lb1 [--variants upsampled,detail,full]

Per hero level, a hillshade sheet (the NW light the references use): the variants side by side and the real ground
(swissALTI3D 0.5 m resampled to the level, lauterbrunnen_truth.py), whole level and a 1:1 crop around the eye spot;
and the numbers:
  landform   each hero level box-averaged to the main level's 8 m pixel against the main level itself in the same
             window: slope p10 / p50 / p90 / p99, relief, hypsometric integral, the mean and RMS height difference
             (the design's test: detail added without moving the landform, within 1 %)
  realism    at the level's own cell, on the ground the real tiles cover: slope p50 / p90 / p99 and the relief below
             the parent pixel (std of h minus its box average over 4 cells), variants against the real ground,
             split into floor (under 10 degrees on the main level), slope (10-45) and rock (over 45)
Writes out/detail/sheets/<tag>_L<i>.png and out/detail/<tag>_numbers.json.
"""
import json
import os
import site
import sys

sys.path.append(site.getusersitepackages())
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import numpy as np  # noqa: E402

from eidoblend.terrain.core import grid as GR  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
from eidoblend.terrain.core import metrics as M  # noqa: E402
from eidoblend.terrain.core.levels import Level  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail'))
RUNS = os.path.join(OUT, 'runs')
TRUTH = os.path.join(OUT, 'truth')


def load_run(tag, variant):
    d = os.path.join(RUNS, f'{tag}_{variant}')
    with open(os.path.join(d, 'run.json')) as f:
        rec = json.load(f)
    plan = [Level.from_dict(x) for x in rec['plan']]
    fields = []
    for lv in plan:
        with np.load(os.path.join(d, f'L{lv.index}.npz')) as z:
            fields.append({k: z[k] for k in z.files})
    return plan, fields, rec


def crop_of(parent, child):
    """The child's window in the parent's cells: (i0, j0, m)."""
    return (int(round((child.x0 - parent.x0) / parent.cell)), int(round((child.y0 - parent.y0) / parent.cell)),
            int(round(child.side / parent.cell)))


def slope_pcts(h, cell, mask=None):
    s = GR.slope_deg(h, cell)
    if mask is not None:
        s = s[mask]
    if s.size == 0:
        return None
    return [round(float(v), 2) for v in np.percentile(s, [10, 50, 90, 99])]


def aligned(main, lv):
    """The main pixels wholly inside a hero window: (main i0, j0, count, hero offset oi, oj, hero cells per pixel)."""
    f = int(round(main.cell / lv.cell))
    i0 = int(np.ceil((lv.x0 - main.x0) / main.cell - 1e-9))
    j0 = int(np.ceil((lv.y0 - main.y0) / main.cell - 1e-9))
    oi = int(round((main.x0 + i0 * main.cell - lv.x0) / lv.cell))
    oj = int(round((main.y0 + j0 * main.cell - lv.y0) / lv.cell))
    m = min((lv.n - oi) // f, (lv.n - oj) // f)
    return i0, j0, m, oi, oj, f


def landform(plan, fields):
    """Each hero level at the main pixel against the main level in the same window."""
    main = next(lv for lv in plan if lv.role == 'main')
    hm = np.asarray(fields[main.index]['h'], np.float64)
    out = {}
    for lv in plan:
        if lv.role != 'hero':
            continue
        h = np.asarray(fields[lv.index]['h'], np.float64)
        i0, j0, m, oi, oj, f = aligned(main, lv)
        hb = GR.box_down(h[oj:oj + m * f, oi:oi + m * f], f)
        ref = hm[j0:j0 + m, i0:i0 + m]
        a, b = M.slope_stats(hb, main.cell), M.slope_stats(ref, main.cell)
        row = {}
        for k in ('slope_deg_p10', 'slope_deg_p50', 'slope_deg_p90', 'slope_deg_p99', 'relief_m',
                  'hypsometric_integral'):
            row[k] = dict(hero=round(a[k], 4), main=round(b[k], 4), rel=round((a[k] - b[k]) / max(abs(b[k]), 1e-9), 5))
        d = hb - ref
        row['mean_dh_m'] = round(float(d.mean()), 4)
        row['rms_dh_m'] = round(float(np.sqrt((d ** 2).mean())), 4)
        out[lv.index] = row
    return out


def _box(a, r):
    a = np.asarray(a, np.float64)
    for axis in (0, 1):
        n = a.shape[axis]
        idx = np.clip(np.arange(-r, n + r), 0, n - 1)
        c = np.cumsum(np.take(a, idx, axis=axis), axis=axis)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        a = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis) - np.take(c, np.arange(n), axis=axis)) \
            / (2 * r + 1)
    return a


def at_main_pixel(plan, fields, lv):
    """A hero level's h box-averaged onto the main level's 8 m pixels it covers wholly."""
    main = next(x for x in plan if x.role == 'main')
    i0, j0, m, oi, oj, f = aligned(main, lv)
    return GR.box_down(np.asarray(fields[lv.index]['h'], np.float64)[oj:oj + m * f, oi:oi + m * f], f), main.cell


def landform_vs(plan, fields, base):
    """The detail's own effect on the landform: each hero level at the main pixel against the same level without
    the detail stages (`base`, the upsampled run), with the acceptance rule: slope percentiles within max(1 %, 0.25
    deg), relief within 1 %, hypsometric integral within 0.01; and the main level itself unchanged."""
    main = next(x for x in plan if x.role == 'main')
    out = {'main_level_identical': bool(np.array_equal(np.asarray(fields[main.index]['h']),
                                                       np.asarray(base[main.index]['h'])))}
    ok_all = out['main_level_identical']
    for lv in plan:
        if lv.role != 'hero':
            continue
        a, cell = at_main_pixel(plan, fields, lv)
        b, _ = at_main_pixel(plan, base, lv)
        ma, mb = M.slope_stats(a, cell), M.slope_stats(b, cell)
        row, ok = {}, True
        for k in ('slope_deg_p10', 'slope_deg_p50', 'slope_deg_p90', 'slope_deg_p99'):
            d = ma[k] - mb[k]
            tol = max(0.01 * abs(mb[k]), 0.25)
            row[k] = dict(detail=round(ma[k], 3), without=round(mb[k], 3), diff=round(d, 3), tol=round(tol, 3),
                          ok=abs(d) <= tol)
            ok = ok and abs(d) <= tol
        d = ma['relief_m'] - mb['relief_m']
        row['relief_m'] = dict(detail=round(ma['relief_m'], 2), without=round(mb['relief_m'], 2),
                               rel=round(d / mb['relief_m'], 5), ok=abs(d) <= 0.01 * mb['relief_m'])
        d = ma['hypsometric_integral'] - mb['hypsometric_integral']
        row['hypsometric_integral'] = dict(detail=round(ma['hypsometric_integral'], 4),
                                           without=round(mb['hypsometric_integral'], 4), diff=round(d, 4),
                                           ok=abs(d) <= 0.01)
        ok = ok and row['relief_m']['ok'] and row['hypsometric_integral']['ok']
        row['mean_dh_m'] = round(float((a - b).mean()), 4)
        row['rms_dh_m'] = round(float(np.sqrt(((a - b) ** 2).mean())), 4)
        row['ok'] = ok
        out[lv.index] = row
        ok_all = ok_all and ok
    out['ok'] = ok_all
    return out


def zones(plan, fields, lv):
    """floor / slope / rock masks on a level: the slope of its surface smoothed over the main pixel (8 m), so they
    mark the landform, not the detail (pass the same fields for every variant)."""
    main = next(x for x in plan if x.role == 'main')
    r = max(1, int(round(main.cell / lv.cell / 2)))
    s = GR.slope_deg(_box(fields[lv.index]['h'], r), lv.cell)
    return {'floor': s < 10.0, 'slope': (s >= 10.0) & (s < 45.0), 'rock': s >= 45.0}


def sub_pixel_relief(h, k=4):
    """h minus h smoothed (two box passes of radius k / 2 cells: a tent about k cells wide). A plane smooths to itself,
    so on a steep wall this is roughness, not slope. Cropped to whole k x k blocks."""
    n = (h.shape[0] // k) * k
    r = max(1, k // 2)
    s = _box(_box(h, r), r)
    return (h - s)[:n, :n]


def realism(plan, fields, truth, lv, zone_fields=None):
    zs = zones(plan, zone_fields or fields, lv)
    h = np.asarray(fields[lv.index]['h'], np.float64)
    ok = np.isfinite(truth)
    t = np.where(ok, truth, np.nanmean(truth))
    n4 = (lv.n // 4) * 4
    full = _box(ok.astype(np.float64), 6)[:n4, :n4] > 0.9999     # the smoothing's reach is covered too
    rows = {}
    for zn, z in zs.items():
        m = z & ok
        m[:2, :] = m[-2:, :] = m[:, :2] = m[:, -2:] = False
        if m.sum() < 500:
            continue
        rh, rt = sub_pixel_relief(h), sub_pixel_relief(t)
        mm = m[:n4, :n4] & full                     # only 4 x 4 blocks the real tiles cover wholly
        rows[zn] = dict(cells=int(m.sum()), slope=slope_pcts(h, lv.cell, m), slope_real=slope_pcts(t, lv.cell, m),
                        relief_below_4_cells=round(float(rh[mm].std()), 4),
                        relief_below_4_cells_real=round(float(rt[mm].std()), 4))
    return rows


def hs(h, cell):
    return IO.to_u8(IO.hillshade(h, cell, azimuth_deg=315.0, altitude_deg=40.0))


def sheet(tag, plan, runs, truth, lv, focus):
    cols = []
    names = list(runs) + (['real'] if truth is not None else [])
    full = []
    crop = []
    n = lv.n
    fx, fy = focus
    ci = int(np.clip(round((fx - lv.x0) / lv.cell - 0.5), 150, n - 150))
    cj = int(np.clip(round((fy - lv.y0) / lv.cell - 0.5), 150, n - 150))
    for nm in names:
        if nm == 'real':
            h = np.where(np.isfinite(truth), truth, np.nanmean(truth))
        else:
            h = np.asarray(runs[nm][lv.index]['h'], np.float64)
        img = hs(h, lv.cell)
        if nm == 'real':
            img = np.where(np.isfinite(truth), img, 0).astype(np.uint8)
        full.append(img[::2, ::2][::-1])                                  # north up, half size
        crop.append(img[cj - 150:cj + 150, ci - 150:ci + 150][::-1])
        cols.append(nm)
    gap = np.full((full[0].shape[0], 6), 255, np.uint8)
    top = np.concatenate(sum([[f, gap] for f in full], [])[:-1], 1)
    gap2 = np.full((300, 6), 255, np.uint8)
    cr = np.concatenate(sum([[np.repeat(np.repeat(c, 1, 0), 1, 1), gap2] for c in crop], [])[:-1], 1)
    pad = np.zeros((300, top.shape[1] - cr.shape[1]), np.uint8) if top.shape[1] > cr.shape[1] else None
    if pad is not None:
        cr = np.concatenate([cr, pad], 1)
    img = np.concatenate([top, np.full((6, top.shape[1]), 255, np.uint8), cr], 0)
    os.makedirs(os.path.join(OUT, 'sheets'), exist_ok=True)
    p = os.path.join(OUT, 'sheets', f'{tag}_L{lv.index}.png')
    IO.write_png(p, np.ascontiguousarray(img))
    return p, cols


def main():
    a = plain_import.script_args()
    get = (lambda k, d: a[a.index(k) + 1] if k in a else d)
    tag = get('--tag', 'lb1')
    variants = get('--variants', 'upsampled,detail,full').split(',')
    runs, plan, recs = {}, None, {}
    for v in variants:
        p, f, rec = load_run(tag, v)
        runs[v], plan, recs[v] = f, p, rec
    focus = recs[variants[0]]['focus'][0]
    numbers = dict(tag=tag, landform={}, landform_vs_upsampled={}, realism={}, sheets={})
    for v in variants:
        numbers['landform'][v] = landform(plan, runs[v])
        if v != 'upsampled' and 'upsampled' in runs:
            lv_ = landform_vs(plan, runs[v], runs['upsampled'])
            numbers['landform_vs_upsampled'][v] = lv_
            print(f"[landform vs upsampled] {v}: {'PASS' if lv_['ok'] else 'FAIL'}; main level identical "
                  f"{lv_['main_level_identical']}; " + '; '.join(
                      f"L{i}: " + ', '.join(f"{k.replace('slope_deg_', '')} {r['diff']:+.2f}" for k, r in row.items()
                                            if k.startswith('slope'))
                      + f", relief {row['relief_m']['rel'] * 100:+.2f}%, HI {row['hypsometric_integral']['diff']:+.4f}"
                      + f", rms dh {row['rms_dh_m']:.2f} m" for i, row in lv_.items() if isinstance(i, int)),
                  flush=True)
    for lv in plan:
        if lv.role != 'hero':
            continue
        tp = os.path.join(TRUTH, f'real_L{lv.index}.npz')
        is_lb = recs[variants[0]].get('recipe', 'real_place') == 'real_place'    # the truth is Lauterbrunnen's
        truth = np.load(tp)['h'] if (is_lb and os.path.exists(tp)) else None
        if truth is not None and np.isfinite(truth).mean() > 0.2:
            numbers['realism'][lv.index] = {v: realism(plan, runs[v], truth, lv, runs[variants[0]])
                                            for v in variants}
        else:
            truth = None
        p, cols = sheet(tag, plan, runs, truth, lv, focus)
        numbers['sheets'][lv.index] = dict(path=p, columns=cols, level=str(lv))
        print(f'[sheets] {p}: {cols}', flush=True)
    with open(os.path.join(OUT, f'{tag}_numbers.json'), 'w') as f:
        json.dump(numbers, f, indent=1)
    for v in variants:
        for i, row in numbers['landform'][v].items():
            print(f"[landform] {v:9s} L{i}: " + ', '.join(f"{k.replace('slope_deg_', '')} {r['rel'] * 100:+.2f}%"
                                                       for k, r in row.items() if isinstance(r, dict))
                  + f", mean dh {row['mean_dh_m']:+.3f} m, rms {row['rms_dh_m']:.3f} m", flush=True)


if __name__ == '__main__':
    main()
