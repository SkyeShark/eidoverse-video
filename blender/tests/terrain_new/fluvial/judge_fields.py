"""Judge what gen.py made, in plain Python (numpy + Pillow): the judge package's verdict beside the reference, the
level seams, and a hillshade sheet.

    python blender/tests/terrain_new/fluvial/judge_fields.py <out_dir> <tag> [<tag> ...]

Per tag: <tag>_verdict.json (the judge's numbers, bands, verdict; the meadow, which has no reference, gets its own
checks: slope p99 under 15 degrees, no closed depressions), <tag>_seams.json (every child level against its parent:
|dh| on the child's edge ring <= 0.05 m and the slope jump there <= 3 degrees, the design's numbers), and
<tag>_sheet.png (the reference's hillshade and the generated main level's at the reference pixel, north up, with a
2 km crop of each at full resolution; then every level's hillshade).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from eidoblend.terrain.core import grid as Gd  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
from eidoblend.terrain.core import metrics as M  # noqa: E402
from judge import judge, refs  # noqa: E402

REF_OF = {'fluvial_range': 'san_gabriel_mountains', 'rolling_hills': 'palouse_hills', 'meadow': None}


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def shade(h, cell, size=None):
    hs = IO.hillshade(np.asarray(h, np.float64), cell)
    img = Image.fromarray(np.ascontiguousarray(IO.to_u8(hs)[::-1]))          # north up
    if size:
        img = img.resize((size, size), Image.LANCZOS)
    return img.convert('RGB')


def levels_of(path):
    d = np.load(path)
    out = []
    i = 0
    while f'L{i}_window' in d.files:
        w = d[f'L{i}_window']
        f = {k[len(f'L{i}_'):]: d[k] for k in d.files if k.startswith(f'L{i}_') and not k.endswith('_window')}
        out.append(dict(x0=w[0], y0=w[1], side=w[2], cell=w[3], n=int(w[4]), fields=f))
        i += 1
    return out


def seams(levels):
    """Each child level against its parent (the design's seam numbers)."""
    rows = []
    for c, p in zip(levels[1:], levels[:-1]):
        i0 = int(round((c['x0'] - p['x0']) / p['cell']))
        j0 = int(round((c['y0'] - p['y0']) / p['cell']))
        m = int(round(c['side'] / p['cell']))
        up = Gd.crop_upsample2(p['fields']['h'], i0, j0, m, 'catmull').astype(np.float64)
        hc = np.asarray(c['fields']['h'], np.float64)
        ring = np.zeros(hc.shape, bool)
        ring[0, :] = ring[-1, :] = ring[:, 0] = ring[:, -1] = True
        dh = float(np.abs(hc - up)[ring].max())
        sc = Gd.slope_deg(hc, c['cell'])
        sp = Gd.slope_deg(up, c['cell'])
        ring2 = np.zeros(hc.shape, bool)
        ring2[1, 1:-1] = ring2[-2, 1:-1] = ring2[1:-1, 1] = ring2[1:-1, -2] = True
        jump = float(np.abs(sc - sp)[ring | ring2].max())
        inner = float(np.abs(hc - up)[16:-16, 16:-16].mean()) if hc.shape[0] > 40 else None
        rows.append(dict(child_cell_m=float(c['cell']), edge_max_dh_m=dh, edge_slope_jump_deg=jump,
                         interior_mean_detail_m=inner, ok=dh <= 0.05 and jump <= 3.0))
    return rows


def meadow_checks(path):
    d = np.load(path)
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    m = M.metrics(h, cell)
    ok = m['slope_p99'] < 15.0 and m['depression_area_frac'] <= 0.001
    return dict(numbers=m, checks=dict(slope_p99_under_15=m['slope_p99'] < 15.0,
                                       no_pits=m['depression_area_frac'] <= 0.001), passed=ok)


def sheet(tag, out_dir, ref_name, levels, verdict_lines):
    d = np.load(os.path.join(out_dir, tag + '.npz'))
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    W = 520
    tiles = []
    if ref_name:
        ref = refs.load(ref_name)
        gen_px = Gd.resample_box(h, cell, ref.pixel) if ref.pixel > cell * 1.0001 else h
        tiles += [(f'reference: {ref.title} ({ref.pixel:g} m)', shade(ref.h, ref.pixel, W)),
                  (f'generated main level at {ref.pixel:g} m', shade(gen_px, ref.pixel, W))]
        n_r = int(round(2000.0 / ref.pixel))
        n_g = int(round(2000.0 / cell))
        cr = ref.h[ref.h.shape[0] // 2 - n_r // 2:ref.h.shape[0] // 2 + n_r // 2,
                   ref.h.shape[1] // 2 - n_r // 2:ref.h.shape[1] // 2 + n_r // 2]
        cg = h[h.shape[0] // 2 - n_g // 2:h.shape[0] // 2 + n_g // 2, h.shape[1] // 2 - n_g // 2:h.shape[1] // 2 + n_g // 2]
        tiles += [('reference, central 2 km', shade(cr, ref.pixel, W)),
                  (f'generated, central 2 km at {cell:.3g} m', shade(cg, cell, W))]
    else:
        tiles += [(f'generated main level ({cell:.3g} m)', shade(h, cell, W))]
    for i, lv in enumerate(levels):
        tiles.append((f"level {i}: {lv['side']:g} m at {lv['cell']:.3g} m", shade(lv['fields']['h'], lv['cell'], W)))
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    head = 26 + 18 * len(verdict_lines)
    img = Image.new('RGB', (cols * (W + 8) + 8, head + rows * (W + 30) + 8), (24, 24, 24))
    dr = ImageDraw.Draw(img)
    f = font(15)
    y = 6
    dr.text((8, y), tag, fill=(255, 255, 255), font=font(18))
    y += 24
    for ln in verdict_lines:
        dr.text((8, y), ln, fill=(220, 220, 220), font=f)
        y += 18
    for k, (label, t) in enumerate(tiles):
        x = 8 + (k % cols) * (W + 8)
        yy = head + (k // cols) * (W + 30)
        dr.text((x, yy), label, fill=(230, 230, 230), font=f)
        img.paste(t, (x, yy + 22))
    path = os.path.join(out_dir, tag + '_sheet.png')
    img.save(path)
    return path


def main():
    out_dir, tags = sys.argv[1], sys.argv[2:]
    for tag in tags:
        rec = json.load(open(os.path.join(out_dir, tag + '_record.json'), encoding='utf-8'))
        recipe = rec['item']['recipe']
        ref_name = REF_OF.get(recipe)
        field = os.path.join(out_dir, tag + '.npz')
        lines = []
        if ref_name:
            v = judge(field, ref_name, label=tag)
            v.save(os.path.join(out_dir, tag + '_verdict.json'))
            print(v.table(), flush=True)
            for r in v.rows:
                if r['passed'] is None:
                    continue
                lines.append(f"{'PASS' if r['passed'] else 'FAIL'}  {r['metric']}: gen {r['gen']:.4g}  ref "
                             f"{r['ref']:.4g}  band {r['band']}" if isinstance(r['gen'], (int, float)) and
                             isinstance(r['ref'], (int, float)) else f"{r['metric']}: {r['passed']}")
            lines.insert(0, f"verdict vs {ref_name}: {'PASS' if v.passed else 'FAIL'}  ({len(v.failures)} failures)")
        else:
            mc = meadow_checks(field)
            json.dump(mc, open(os.path.join(out_dir, tag + '_verdict.json'), 'w'), indent=1)
            n = mc['numbers']
            lines.append(f"meadow: slope p50 {n['slope_p50']:.1f} p90 {n['slope_p90']:.1f} p99 {n['slope_p99']:.1f} "
                         f"(p99 < 15: {mc['checks']['slope_p99_under_15']}), relief {n['relief_m']:.2f} m, "
                         f"closed depressions {n['depression_area_frac']:.4f}")
            print(lines[-1])
        levels = levels_of(os.path.join(out_dir, tag + '_levels.npz'))
        sm = seams(levels)
        json.dump(sm, open(os.path.join(out_dir, tag + '_seams.json'), 'w'), indent=1)
        for r in sm:
            print(f"  seam {r['child_cell_m']:.3g} m: edge |dh| {r['edge_max_dh_m']:.4f} m, slope jump "
                  f"{r['edge_slope_jump_deg']:.2f} deg, detail {r['interior_mean_detail_m']}", flush=True)
        lines.append('seams: ' + ', '.join(f"{r['child_cell_m']:.3g} m |dh| {r['edge_max_dh_m']:.3f} jump "
                                          f"{r['edge_slope_jump_deg']:.2f}" for r in sm))
        lines.append(f"run {rec['seconds']} s: " + ', '.join(f"L{i} {l.get('seconds')}" for i, l in
                                                             enumerate(rec['run'].get('levels', []))))
        print(sheet(tag, out_dir, ref_name, levels, lines))


main()
